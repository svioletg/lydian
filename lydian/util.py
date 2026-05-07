"""General-purpose utility/"helper" functions and classes.

This module should not import any other modules from the package, to ensure its contents can be used by any module.
"""
from collections.abc import Callable, Iterable
from dataclasses import Field, fields, is_dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from time import perf_counter_ns
from types import TracebackType
from typing import Any, Literal, cast, get_args, get_origin
from zoneinfo import ZoneInfo

from maybetype import Maybe, maybe

from lydian.errors import AssuranceError


class BasicLock:
    """A basic "lock" object that can be used as a context manager.

    ```python
    lock = BasicLock()

    print(lock) # BasicLock(False)

    with lock:
        print(lock) # BasicLock(True)

    print(lock) # BasicLock(False)
    ```

    The ``name`` argument can be given to customize the ``repr``.

    ```python
    lock = BasicLock('QueueLock')
    print(lock) # QueueLock(False)
    ```
    """

    def __init__(self, name: str | None = None, *, default_state: bool = False) -> None:
        """Initializes a ``BasicLock``.

        :param name: The name to use in the lock's ``repr`` instead of the class name.
        :param default_state: What the ``state`` attribute should be set to by default and after exiting the context
            manager, using its opposite when entering.
        """
        self._default_state: bool = default_state

        self.name = name or self.__class__.__name__
        self.state: bool = default_state

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.name}({self.state})'

    def __bool__(self) -> bool:  # noqa: D105
        return self.state

    def __enter__(self) -> None:  # noqa: D105
        self.state = not self._default_state

    def __exit__(self,  # noqa: D105
            _exc_type: type[BaseException] | None,
            _exc_value: BaseException | None,
            _traceback: TracebackType | None,
        ) -> bool:
        self.state = self._default_state

        return self._default_state

class CachedObject[T]:
    """A cached object with a value and expiration date, for use by :py:class:`Cache`."""

    def __init__(self, value: T, expires: datetime | timedelta | None = None) -> None:
        """Initializes a new ``CachedObject``.

        :param expires: Optionally a date at which this cached object should be considered "expired" and discarded,
            given either as a concrete date or a ``timedelta`` applied to the current time.
        """
        self.value: T = value
        self.expires: datetime | None = (datetime.now(UTC) + expires) if isinstance(expires, timedelta) else expires

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.__class__.__name__}(value={self.value!r}, expires={self.expires})'

    def is_expired(self) -> bool:
        """Returns ``True`` if an expiration date is set and the current time is past it, otherwise ``False``."""
        return (self.expires is not None) and (datetime.now(UTC) > self.expires.astimezone(UTC))

class Cache[K, V]:
    """A simple cache."""

    def __init__(self, default_expiration: timedelta | None = None) -> None:
        self._default_expiration = default_expiration
        self._data: dict[K, CachedObject[V]] = {}

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.__class__.__name__}({self._data!r})'

    def clear(self) -> None:
        """Removes all items from the cache."""
        self._data.clear()

    def get(self, key: K) -> V | None:
        """Returns the value associated with ``key`` if it exists and has not expired, otherwise returns ``None``.

        If the key exists but is expired, the key is removed from the cache and ``None`` is returned.
        """
        if key not in self._data:
            return None
        obj = self._data[key]
        if obj.is_expired():
            del self._data[key]
            return None
        return obj.value

    def get_or_set(self, key: K, func: Callable[[], V], expires: datetime | timedelta | None = None) -> V:
        """Returns the value associated with ``key`` if it exists and has not expires, or sets it via ``func``.

        If the key does not exist or its value has expired, ``func`` is called with no arguments and its result is
        stored as the value of ``key``, the same result is then returned.

        :param expires: Expiration date to use when setting the value of a new key. An existing key's expiration date
            will not be modified. This date must be in the future from the current time, otherwise ``ValueError`` is
            raised.

        :raises ValueError:
            ``expires`` was given a date in the past.
        """
        expires = expires if expires is not None else self._default_expiration
        if expires and \
            (((datetime.now(UTC) + expires) if isinstance(expires, timedelta) else expires) < datetime.now(UTC)):
            raise ValueError(f'Expiration date for get_or_set must be a future date: {expires}')
        if (key not in self._data) or ((obj := self._data[key]).is_expired()):
            obj = CachedObject(func(), expires=expires)
            self._data[key] = obj
            return obj.value
        return obj.value

    def remove(self, key: K) -> None:
        """Removes ``key`` from the cache's keys.

        Does nothing if the key did not exist.
        """
        if key in self._data:
            del self._data[key]

    def set(self, key: K, value: V, expires: datetime | timedelta | None = None) -> None:
        """Adds or replaces the value of ``key`` with ``value`` and the given optional expiration date."""
        expires = expires if expires is not None else self._default_expiration
        self._data[key] = CachedObject(value, expires=expires)

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
    return sum(fp.stat().st_size for fp in Path(source_dir).rglob('*'))

def dirsize_counted(source_dir: str | Path) -> tuple[int, dict[Literal['dir', 'file'], int]]:
    """Returns the total size of a directory's contents in bytes, and a dictionary of directory and file counts."""
    total_bytes: int = 0
    count: dict[Literal['dir', 'file'], int] = {'dir': 0, 'file': 0}
    for fp in Path(source_dir).rglob('*'):
        count['dir' if fp.is_dir() else 'file'] += 1
        total_bytes += fp.stat().st_size

    return total_bytes, count

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

def format_duration(total_seconds: float) -> str:
    """Returns seconds converted to H:M:S format, or M:S if the hour is 0."""
    h, m = divmod(total_seconds, 3600)
    m, s = divmod(m, 60)
    if h:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'

def linepos_to_pos(s: str, lineno: int, linepos: int) -> int:
    """Converts a 0-indexed line number and position to a global position in a string."""
    lines: list[str] = s.splitlines(keepends=True)
    return len(''.join(lines[:lineno])) + linepos

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

def pos_to_linepos(s: str, pos: int) -> tuple[int, int]:
    r"""Converts a global position in a string to a tuple of the line number and position within that line.

    The line and position are 0-indexed.

    >>> s = 'One\nTwo\nThree\n'
    >>> for n, char in enumerate(s):
    ...     lineno, linepos = pos_to_linepos(s, n)
    ...     assert s[n] == char == s.splitlines(keepends=True)[lineno][linepos]

    :raises IndexError:
        ``pos`` is out of range for ``s``.
    """
    _ = s[pos] # Raises IndexError if the position is out of range
    line: int = s[:pos].count('\n')
    line_pos = pos - len('\n'.join(s.splitlines()[:line]))
    return line, line_pos - (1 if line else 0)

def plural(s: str, n: int) -> str:
    """Returns a string as plural or singular based on the value of ``n``.

    ``s`` must be formatted as the singular form, followed by a dot, then followed by the plural suffix, e.g.
    ``item.s``. One dot indicates the characters after it should simply be suffixed to the string with no modification.
    An extra dot can be given to separate more specific singular and plural forms, where in ``a.b.c``, ``b`` is used as
    the singular suffix to ``a``, while ``c`` is used as the plural suffix.

    >>> assert plural('item.s', 1) == 'item'
    >>> assert plural('item.s', 2) == 'items'

    >>> assert plural('octop.us.i', 1) == 'octopus'
    >>> assert plural('octop.us.i', 2) == 'octopi'

    >>> assert plural('m.ouse.ice', 1) == 'mouse'
    >>> assert plural('m.ouse.ice', 2) == 'mice'
    """
    root, b, *c = s.split('.')
    if c:
        singular, plural = b, c[0]
    else:
        singular, plural = '', b
    return f'{root}{singular if n == 1 else plural}'

def strftimestamp(
        timestamp: float,
        format_str: str = '%Y-%m-%dT%H%M%S%z',
        *,
        tz: tzinfo | str = 'UTC',
    ) -> str:
    """Format a Unix timestamp to the given format string, converting its timezone to ``tz`` if given a value."""
    tz: tzinfo = ZoneInfo(tz) if isinstance(tz, str) else tz
    return datetime.fromtimestamp(timestamp, tz=UTC).astimezone(tz).strftime(format_str)
