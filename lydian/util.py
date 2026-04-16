"""General-purpose utility/"helper" functions and classes.

This module should not import any other modules from the package, to ensure its contents can be used by any module.
"""
from collections.abc import Callable, Iterable
from dataclasses import Field, fields, is_dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from time import perf_counter_ns
from typing import Literal
from zoneinfo import ZoneInfo

from maybetype import Maybe, maybe


class Stopwatch:
    """Tracks time over a period, by default from when the instance is created."""

    def __init__(self, *, paused: bool = False) -> None:
        """Returns a new ``Stopwatch``.

        :param paused: If ``True``, the Stopwatch is paused to begin with, meaning :py:meth:`elapsed_ns` will return 0
            until :py:meth:`resume` is called. Otherwise, the start time is set to immediately after ``__init__``
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
        """Pauses the Stopwatch.

        The elapsed time will not increase until :py:meth:`resume` is called.
        Does nothing if already paused.
        """
        if not self.is_paused:
            self._paused = True
            self._paused_at = perf_counter_ns()

    def elapsed_ns(self) -> int:
        """Nanoseconds that have elapsed."""
        if not self.start:
            return 0
        if self.is_paused:
            return self._paused_at - self.start
        return (perf_counter_ns() - self.start) - self._pause_offset

    def elapsed(self) -> float:
        """Seconds that have elapsed."""
        return self.elapsed_ns() / 1e9

    def unpause(self) -> None:
        """Unpauses the Stopwatch.

        Does nothing if not paused.
        """
        if self.is_paused:
            self._paused = False
            if not self.start:
                self.start = perf_counter_ns()
            else:
                self._pause_offset += perf_counter_ns() - self._paused_at

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
    tz = ZoneInfo(tz) if isinstance(tz, str) else tz
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone(tz).strftime(format_str)
