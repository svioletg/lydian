"""General-purpose utility/"helper" functions and classes.

This module should not import any other modules from the package other than ``errors``, to ensure its contents can be
used by any module.
"""
import re
import textwrap
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from dataclasses import Field, fields, is_dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from math import ceil, floor
from pathlib import Path
from time import perf_counter_ns
from types import EllipsisType, TracebackType
from typing import Annotated, Any, ClassVar, Literal, cast, get_args, get_origin, overload
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks
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

    def update(self,  # noqa: C901
            d: dict[str, Any],
            *,
            on_missing: Callable[[str], None] | Literal['raise', 'continue'] = 'continue',
        ) -> None:
        """Updates field values as per ``d``, attempting to convert values to the correct type.

        :param on_missing: What to do when encountering a key present in ``d`` that is not present in the dataclass
            being updated. ``'continue'`` skips the key silently, ``raise`` raises ``KeyError`` with the key value, or
            if given a ``Callable``, it is called with the key value before skipping the key.
        """
        if not hasattr(self, '__dataclass_fields__'):
            raise AttributeError(
                f'{self.__class__.__name__} must be mixed into a class that has __dataclass_fields__: {self!r}',
            )

        for k, v in d.items():
            k = k.replace('-', '_')  # noqa: PLW2901
            if not (fld := cast('dict[str, Field[Any]]', self.__dataclass_fields__).get(k)):
                if callable(on_missing):
                    on_missing(k)
                    continue
                if on_missing == 'continue':
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
                    getattr(self, k).update(v, on_missing=on_missing)
                else:
                    getattr(self, k).update(v)
            # If the field is a Literal then just because it's the right type doesn't mean it's the right value
            elif isinstance(v, typ) and not is_literal:
                setattr(self, k, v)
            else:
                converted = fld.metadata.get('converter', typ)(v)
                if is_literal and (converted not in t_args):
                    raise ValueError(f'Expected one of {','.join(repr(i) for i in t_args)}: {converted!r}')
                setattr(self, k, converted)

class FromStr:
    """Provides various methods for converting string values of an expected pattern to other types."""

    filesize_units: ClassVar[dict[str, int]] = {
        'b': 1,
        'kb': 1000,
        'kib': 1024,
        'mb': 1000 * 1000,
        'mib': 1024 * 1024,
        'gb': 1000 * 1000 * 1000,
        'gib': 1024 * 1024 * 1024,
    }

    filesize_regex: ClassVar[re.Pattern[str]] = re.compile(
        r'^(?P<n>[\d,]+\.?\d+) ?(?P<unit>b|[kmg]i?b)$',
        flags=re.IGNORECASE,
    )

    @classmethod
    def filesize(cls, value: str | int) -> int:
        """Parses a filesize string into an ``int`` representing bytes, or returns the value if given ``int``.

        The calculated bytes will be floored to ``int``.
        Any of the following units can be given with or without a space after the number, and are case-insensitive:

        - ``b``: Bytes
        - ``kb``: Kilobytes
        - ``kib``: Kibibytes
        - ``mb``: Megabytes
        - ``mib``: Mebibytes
        - ``gb``: Gigabytes
        - ``gib``: Gibibytes
        """
        if isinstance(value, int):
            return value
        if not (m := cls.filesize_regex.match(value)):
            raise ValueError(f'Filesize string does not match expected pattern: {value!r}')
        return floor(float(m.group('n').replace(',', '')) * cls.filesize_units[m.group('unit').lower()])

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

def expect[T](value: T | None) -> T:
    """Returns ``value``, raising ``ValueError`` if ``None``."""
    if value is None:
        raise ValueError('None')
    return value

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
        return f'{ceil(h)}:{ceil(m):02d}:{ceil(s):02d}'
    return f'{ceil(m)}:{ceil(s):02d}'

def get_annotation(typ: object) -> Any | None:  # noqa: ANN401
    """Returns the second type argument if ``typ`` is ``typing.Annotated``, otherwise returns ``None``."""
    try:
        return get_args(typ)[1] if get_origin(typ) is Annotated else None
    except IndexError:
        return None

def get_background_tasks(bot: commands.Bot) -> dict[str, dict[str, tasks.Loop]]:
    """Returns a dictionary of cog names to a dictionary of background task coroutines by their names."""
    return {
        cog_name:{name:attr for name, attr in cog.__dict__.items() if isinstance(attr, tasks.Loop)}
        for cog_name, cog in bot.cogs.items()
    }

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

@overload
def get_leaves[T](tree: Mapping[Any, Any], typ: type[T]) -> Generator[T]: ...
@overload
def get_leaves(tree: Mapping[Any, Any], typ: None = None) -> Generator[Any]: ...
def get_leaves[T](tree: Mapping[Any, Any], typ: type[T] | None = None) -> Generator[T] | Generator[Any]:
    """Returns every non-mapping (or a specific type) value in an arbitrarily nested mapping.

    :param typ: A type to use in ``isinstance`` checks determining whether a value is considered a leaf.
        If ``None``, the value is simply checked to not be a mapping instance.
    """
    # Returns two booleans, one for whether this value is a leaf, and one for whether we should descend into this value
    # This prevents unnecessarily checking for a Mapping instance a second time if `typ` is None
    is_leaf: Callable[[Any], tuple[bool, bool]] = (lambda v: (not isinstance(v, Mapping), True)) \
        if typ is None else (lambda v: (isinstance(v, typ), isinstance(v, Mapping)))

    def search(d: Mapping[Any, Any]) -> Generator:
        for v in d.values():
            take, descend = is_leaf(v)
            if take:
                yield v
            elif descend:
                yield from search(v)

    yield from search(tree)

def is_annotated(typ: object) -> bool:
    """Returns whether ``typ``'s type origin is ``typing.Annotated``.

    .. note::
        There's no way to annotate ``typ`` is accepting ``typing.Annotated`` specifically, so it just accepts
        ``object``.
    """
    return get_origin(typ) is Annotated

@overload
def iter_columns[T](data: Sequence[Sequence[T]], default: EllipsisType = ...) -> Generator[tuple[T, ...]]: ...
@overload
def iter_columns[T, U](data: Sequence[Sequence[T]], default: U) -> Generator[tuple[T | U, ...]]: ...
def iter_columns[T, U](
        data: Sequence[Sequence[T]],
        default: U | EllipsisType = ...,
    ) -> Generator[tuple[T | U, ...]]:
    """Yields columns from a two-dimensional sequence.

    ``default`` will fill empty cells row or column lengths are not consistent, otherwise ``IndexError`` is raised.
    """
    def get_cell(row: int, column: int, default: U) -> T | U:
        try:
            return data[row][column]
        except IndexError:
            return default

    height: int = len(data)
    width: int = len(data[0]) if default is ... else max(map(len, data))

    yield from (
        tuple(data[row][column] if default is ... else get_cell(row, column, default) for row in range(height))
        for column in range(width)
    )

def join_trailing(s: Iterable[str], sep: str, *, trail_single: bool = False) -> str:
    """Same as ``str.join()``, but adds an additional ``sep`` at the end if any joining was performed.

    :param trail_single: Add a trailing ``sep`` even if there's only one item in ``s``.
    """
    return sep.join(seq := list(s)) + (sep if len(seq) > (0 if trail_single else 1) else '')

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

def partition[T](predicate: Callable[[T], bool], it: Iterable[T]) -> tuple[list[T], list[T]]:
    """Separates the items of ``it`` into two lists based on whether ``predicate`` returns ``True``.

    The left list contains every item for which ``predicate(i)`` is ``True``, the right list contains the opposite.
    """
    yes: list[T] = []
    no: list[T] = []
    for i in it:
        (yes if predicate(i) else no).append(i)
    return yes, no

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

def tabulate(  # noqa: C901
        data: Sequence[tuple[object, ...]],
        *,
        header: tuple[str, ...] | None = None,
        head_sep: str = '-',
        hsep: str = ' ',
        vsep: str = '',
        vborder: str = '',
        render: Callable[[object], str] = str,
        justify: Callable[[str, int], str] | tuple[Callable[[str, int], str], ...] | None = None,
        strip: str | re.Pattern[str] | None = None,
    ) -> str:
    """Returns a string with ``data`` formatted as a table based on the given options.

    This function assumes that all rows in ``data`` are the same length as the first.

    :param header: A row of strings to place as titles for each column before the rest of the table.
    :param head_sep: Character to repeat for the table's width between the header row and the rest of the table.
        There is no separation between the header and the rest of the table if this string is empty.
    :param hsep: Horizontal separator character to place between each column.
    :param vsep: Vertical separator character to repeat for the table's width between each row.
        No lines are placed between rows if this string is empty.
    :param vborder: Character to repeat for the table's width as the first and last lines of the table string.
    :param render: A function to use to convert each item into a string.
    :param justify: A function used to justify the string for a given cell, passed the string content and the column's
        width. Defaults to ``str.ljust``. If given a tuple of functions, each function will be used for the respective
        column.
    :param strip: A regular expression matching characters to strip out of the rendered string before calculating its
        length, e.g. for stripping non-visible characters like color escape codes.
    """
    if isinstance(strip, str):
        strip = re.compile(strip)

    justify = justify or str.ljust

    if not isinstance(justify, tuple):
        justify = (justify,) * len(data[0])

    justify = cast('tuple[Callable[[str, int], str], ...]', justify)

    rendered: list[tuple[str, ...]] = [tuple(render(cell) for cell in row) for row in data]
    col_widths: list[int] = [
        max(map(len, (strip.sub('', cell) for cell in column) if strip else column))
        for column in iter_columns(rendered)
    ]
    for n, width in enumerate(col_widths):
        if header:
            col_widths[n] = max(width, len(header[n]))

    table_width: int = sum(
        (max(colw, len(head)) for colw, head in zip(col_widths, header, strict=True)) if header else col_widths,
    ) + (len(hsep) * (len(col_widths) - 1))

    table: list[str] = [vborder * table_width] if vborder else []

    if header:
        table.append(
            hsep.join(just(cell, width) for cell, width, just in zip(header, col_widths, justify, strict=True)),
        )
        if head_sep:
            table.append(head_sep * table_width)

    for row in rendered:
        table.append(hsep.join(just(cell, width) for cell, width, just in zip(row, col_widths, justify, strict=True)))
        if vsep:
            table.append(vsep * table_width)

    if vsep:
        table.pop()

    if vborder:
        table.append(vborder * table_width)

    return '\n'.join(table)

def wrap_paragraphs(
        text: str,
        width: int,
        *,
        initial_indent: str = '',
        subsequent_indent: str = '',
        indent_mode: Literal['multi', 'single'] = 'multi',
    ) -> list[str]:
    """Returns lines of ``text`` wrapped to fit ``width`` length each, preserving original newlines.

    :param indent_mode: Whether to apply ``initial_indent`` and ``subsequent_indent`` to each paragraph individually
        (``'multi'``) or apply ``subsequent_indent`` to every following line regardless of line breaks (``'single'``).
    """
    wrapped_paras: list[list[str]] = []
    for n, paragraph in enumerate(text.splitlines()):
        wrapped_paras.append(textwrap.wrap(
            paragraph,
            width=width,
            initial_indent=(subsequent_indent if n > 0 and indent_mode == 'single' else initial_indent),
            subsequent_indent=subsequent_indent,
        ))
    return [ln for lines in wrapped_paras for ln in lines]
