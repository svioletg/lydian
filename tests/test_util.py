from collections.abc import Callable, Iterable
from dataclasses import Field, dataclass, field
from datetime import tzinfo
from typing import Any

import pytest
from maybetype import Nothing, Some

from lydian import util
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
