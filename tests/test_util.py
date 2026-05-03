from collections.abc import Callable, Iterable
from dataclasses import Field, dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Literal

import pytest
from maybetype import Nothing, Some, maybe

from lydian import util
from lydian.errors import AssuranceError
from lydian.util import Cache
from tests import ReadOnlyDict

NESTED_DICT_RO: ReadOnlyDict[str, Any] = ReadOnlyDict({'a': 1, 'b': {'a': 2, 'b': {'a': 3}}, 'c': 4})

@dataclass
class SubDataclass:  # noqa: D101
    x: float = 1.5
    y: list[int] = field(default_factory=list)

@dataclass
class Dataclass:  # noqa: D101
    a: int = 1
    b: str = 'two'
    c: bool = True
    d: SubDataclass = field(default_factory=SubDataclass)

def test_assure() -> None:
    util.assure(True)  # noqa: FBT003
    with pytest.raises(AssuranceError):
        util.assure(False)  # noqa: FBT003

def test_cached_object_init() -> None:
    assert util.CachedObject(1).expires is None

    obj_expired = util.CachedObject(1, dt := datetime(2025, 1, 1, tzinfo=UTC))
    assert obj_expired.expires == dt
    assert obj_expired.is_expired()

    # Works for now but remember to update test in about 80 years
    obj_not_expired = util.CachedObject(1, dt := datetime(3000, 1, 1, tzinfo=UTC))
    assert obj_not_expired.expires == dt
    assert not obj_not_expired.is_expired()

    assert maybe(util.CachedObject(1, timedelta(days=1)).expires).unwrap().day \
        == (datetime.now(UTC) + timedelta(days=1)).day

def test_cache() -> None:
    cache: Cache[int, str] = Cache()
    assert cache.get(1) is None
    cache.set(1, 'one')
    assert cache.get(1) == 'one'
    cache.set(1, 'one', datetime(2025, 1, 1, tzinfo=UTC))
    assert cache.get(1) is None
    cache.set(1, 'one', timedelta(days=1))
    assert cache.get(1) == 'one'
    cache.remove(1)
    assert cache.get(1) is None

    cache = Cache()
    assert cache.get_or_set(1, lambda: 'one') == 'one'
    assert cache.get(1) == 'one'
    cache.remove(1)
    assert cache.get_or_set(1, lambda: 'one', timedelta(days=1)) == 'one'
    with pytest.raises(ValueError, match='must be a future date'):
        cache.get_or_set(1, lambda: 'one', datetime(2025, 1, 1, tzinfo=UTC))

def test_dirsize(tmpdir: Path) -> None:
    def write_dummy(size: int, dest: Path) -> Path:
        with open(dest, 'wb') as f:
            f.write(b'\x00' * size)
        return dest

    source_dir: Path = tmpdir / 'dirsize'
    source_dir.mkdir()
    (source_dir / 'a').mkdir()
    (source_dir / 'b').mkdir()

    file_size: int = 1000
    files_per: int = 3

    expected_count: dict[Literal['dir', 'file'], int] = {
        'dir': 2,
        'file': 3 * files_per,
    }
    expected_size: int = (expected_count['dir'] * 4096) + (expected_count['file'] * file_size)

    for d in '.ab':
        for f in 'xyz':
            write_dummy(1000, source_dir / d / f)

    assert util.dirsize(source_dir) == expected_size
    assert util.dirsize_counted(source_dir) == (expected_size, expected_count)

@pytest.mark.parametrize(('it', 'predicate', 'expected'),
    [
        (range(10), lambda n: n > 5, 6),  # noqa: PLR2004
        (range(10), lambda n: n > 10, None),  # noqa: PLR2004
    ],
)
def test_first_where[T](it: Iterable[T], predicate: Callable[[T], bool], expected: T | None) -> None:
    assert util.first_where(it, predicate) == expected

def test_get_dataclass_fields() -> None:
    dc = Dataclass()
    dc_fields: dict[str, Field] = util.get_dataclass_fields(dc)
    assert dc_fields['a'].default == dc.a
    assert dc_fields['b'].default == dc.b
    assert dc_fields['c'].default == dc.c
    assert dc_fields['d.x'].default == dc.d.x
    assert dc_fields['d.y'].default_factory() == dc.d.y  # ty:ignore[call-non-callable]

def test_maybepath() -> None:
    assert util.maybepath('qwertyuiop') is Nothing
    assert isinstance(util.maybepath('pyproject.toml'), Some)

@pytest.mark.parametrize(('word', 'singular', 'plural'),
    [
        ('item.s', 'item', 'items'),
        ('octop.us.i', 'octopus', 'octopi'),
        ('m.ouse.ice', 'mouse', 'mice'),
    ],
)
def test_plural(word: str, singular: str, plural: str) -> None:
    assert util.plural(word, 0) == util.plural(word, 2) == plural
    assert util.plural(word, 1) == singular

@pytest.mark.parametrize(('timestamp', 'format_str', 'tz', 'expected'),
    [
        (0, None, None, '1970-01-01T000000+0000'),
        (0, None, 'US/Central', '1969-12-31T180000-0600'),
        (0, '%A, %B %e, %Y at %I:%M%P', None, 'Thursday, January  1, 1970 at 12:00am'),
        (0, '%A, %B %e, %Y at %I:%M%P', 'US/Central', 'Wednesday, December 31, 1969 at 06:00pm'),
        (1776105384, None, None, '2026-04-13T183624+0000'),
        (1776105384, None, 'US/Central', '2026-04-13T133624-0500'),
        (1776105384, '%A, %B %e, %Y at %I:%M%P', None, 'Monday, April 13, 2026 at 06:36pm'),
        (1776105384, '%A, %B %e, %Y at %I:%M%P', 'US/Central', 'Monday, April 13, 2026 at 01:36pm'),
    ],
)
def test_strftimestamp(
        timestamp: float,
        format_str: str | None,
        tz: tzinfo | str | None,
        expected: str,
    ) -> None:
    kwargs: dict[str, Any] = {}
    if format_str:
        kwargs['format_str'] = format_str
    if tz:
        kwargs['tz'] = tz

    assert util.strftimestamp(timestamp, **kwargs) == expected
