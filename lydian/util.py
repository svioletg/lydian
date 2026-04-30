"""General-purpose utility/"helper" functions and classes.

This module should not import any other modules from the package, to ensure its contents can be used by any module.
"""
from collections.abc import Callable, Iterable
from dataclasses import Field, fields, is_dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Literal, cast, get_args, get_origin
from zoneinfo import ZoneInfo

from maybetype import Maybe, maybe

from lydian.errors import AssuranceError


class DataclassUpdateMixin:
    """Adds an ``update`` method to a dataclass which can update its contents similar to ``dict.update``."""

    def _update_with_parameterized_type(self, key: str, val: object, typ: type) -> None:
        origin = maybe(get_origin(typ)).unwrap(f'Not a parameterized type: {typ!r}')
        args = get_args(typ)
        if not isinstance(val, origin):
            raise TypeError(f'Expected type {typ}: {val!r}')

        if origin is list:
            list_type = args[0]
            for i in val:
                if not isinstance(i, list_type):
                    raise TypeError(f'Expected type {typ} in list: {i!r}')
        if origin is dict:
            kt, vt = args
            vt_args = get_args(typ)
            if vt_args:
                vt = get_origin(vt)
            for k, v in val.items():
                if not isinstance(k, kt):
                    raise TypeError(f'Expected type {kt} for dict key: {k!r}')
                if not isinstance(v, vt):
                    raise TypeError(f'Expected type {vt} for dict value of key {k!r}: {v!r}')

        setattr(self, key, val)

    def update(self, d: dict[str, Any], *, missing_ok: bool = False) -> None:  # noqa: C901
        """Updates field values as per ``d``, attempting to convert values to the correct type.

        :param missing_ok: Whether to ignore keys present in ``d`` which have no field in this dataclass.
            If ``False``, ``KeyError`` is raised.
        """
        if not hasattr(self, '__dataclass_fields__'):
            raise AttributeError(
                f'{self.__class__.__name__} must be mixed into a class that has __dataclass_fields__: {self!r}',
            )
        for k, v in d.items():
            k = k.replace('-', '_')  # noqa: PLW2901
            if not (fld := cast('dict[str, Field[Any]]', self.__dataclass_fields__).get(k)):
                if missing_ok:
                    continue
                raise KeyError(k)

            typ = cast('type', fld.type)
            t_origin = get_origin(typ)
            t_args = get_args(typ)

            if is_literal := (t_origin is Literal):
                # Making an assumption that a Literal type only consists of the same type
                typ = type(t_args[0])
            elif t_origin:
                typ = t_origin

            if hasattr(typ, 'update'):
                if t_origin is not dict:
                    getattr(self, k).update(v, missing_ok=missing_ok)
                else:
                    getattr(self, k).update(v)
            elif isinstance(v, typ):
                setattr(self, k, v)
            elif converter := fld.metadata.get('converter'):
                converted = converter(v)
                if is_literal and (converted not in t_args):
                    raise ValueError(f'Expected one of {','.join(repr(i) for i in t_args)}: {converted!r}')
                setattr(self, k, converted)
            else:
                setattr(self, k, typ(v))

class Stopwatch:
    """Tracks time over a period, by default from when the instance is created."""

    def __init__(self, *, paused: bool = False) -> None:
        """Returns a new Stopwatch.

        :param paused: If ``True``, the Stopwatch is paused to begin with, meaning :py:meth:`elapsed_ns` will return 0
            until :py:meth:`unpause` is called. Otherwise, the start time is set to immediately after ``__init__``
            finishes.
        """
        self.start: int = 0
        self._paused: bool = paused
        self._paused_at: int = 0
        self._pause_offset: int = 0

        if not self.is_paused:
            self.start = perf_counter_ns()

    @property
    def is_paused(self) -> bool:
        """Returns whether the Stopwatch is currently paused.

        This property cannot be set directly; use the :py:meth:`pause` and :py:meth:`unpause` methods.
        """
        return self._paused

    def pause(self) -> None:
        """Pauses the Stopwatch, does nothing if already paused.

        The elapsed time will not increase until :py:meth:`unpause` is called.
        """
        if not self.is_paused:
            self._paused = True
            self._paused_at = perf_counter_ns()

    def elapsed(self) -> float:
        """Seconds that have elapsed."""
        return self.elapsed_ns() / 1e9

    def elapsed_ns(self) -> int:
        """Nanoseconds that have elapsed."""
        if not self.start:
            return 0
        if self.is_paused:
            return self._paused_at - self.start
        return (perf_counter_ns() - self.start) - self._pause_offset

    def unpause(self) -> None:
        """Unpauses the Stopwatch, does nothing if not paused."""
        if self.is_paused:
            self._paused = False
            if not self.start:
                self.start = perf_counter_ns()
            else:
                self._pause_offset += perf_counter_ns() - self._paused_at

def assure(condition: bool, exc_args: str = '') -> None:  # noqa: FBT001
    """Raises :py:class:`lydian.errors.AssuranceError` if ``condition`` is ``False``, otherwise does nothing."""
    if not condition:
        raise AssuranceError(exc_args)

def dirsize(source_dir: str | Path) -> int:
    """Returns the total size of a directory's contents in bytes."""
    return sum(fp.stat().st_size for fp in Path(source_dir).rglob('*') if fp.is_file())

def get_dataclass_fields(dc: object, parents: list[str] | None = None) -> dict[str, Field]:
    """Returns a dictionary of field names (dotted if the field is a dataclass) to field objects for a dataclass.

    :param parents: Strings to prefix this dataclass' field names with, joined by dots.
    """
    parents = parents or []
    field_dict: dict[str, Field] = {}
    for f in fields(dc):  # ty:ignore[invalid-argument-type]
        field_dict[f.name if not parents else f'{'.'.join(parents)}.{f.name}'] = f
        if is_dataclass(f.type):
            field_dict = field_dict | get_dataclass_fields(f.type, [*parents, f.name])

    return field_dict

def first_where[T](it: Iterable[T], predicate: Callable[[T], bool]) -> T | None:
    """Return the first item of an iterable that returns ``True`` for ``predicate(i)``, or ``None`` if no items pass."""
    try:
        return next(filter(predicate, it))
    except StopIteration:
        return None

def maybepath(fp: str | Path, must_be: Literal['file', 'dir'] | None = None) -> Maybe[Path]:
    """Returns a ``Maybe`` predicated on whether the given file path exists.

    :param must_be: If not ``None``, additionally ensures the path is either file or directory based on the given
        argument.
    """
    check: Callable[[Path], bool]
    match must_be:
        case 'file':
            check = lambda fp: fp.is_file()  # noqa: E731
        case 'dir':
            check = lambda fp: fp.is_dir()  # noqa: E731
        case _:
            check = lambda fp: fp.exists()  # noqa: E731

    return maybe(Path(fp), check)

def strftimestamp(
        timestamp: float,
        format_str: str = '%Y-%m-%dT%H%M%S%z',
        *,
        tz: tzinfo | str = 'UTC',
    ) -> str:
    """Format a Unix timestamp to the given format string, converting its timezone to ``tz`` if given a value."""
    tz: tzinfo = ZoneInfo(tz) if isinstance(tz, str) else tz
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone(tz).strftime(format_str)
