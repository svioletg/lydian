import pytest

from lydian.util import FromStr


@pytest.mark.parametrize(('s', 'expected'),
    [
        ('10 b',         10),
        ('10 kb',        10_000),
        ('10 kib',       10_240),
        ('10 mb',        10_000_000),
        ('10 mib',       10_485_760),
        ('10 gb',        10_000_000_000),
        ('10 gib',       10_737_418_240),
        ('10,000 b',     10_000),
        ('10.5 kb',      10_500),
        ('10.5 kib',     10_752),
        ('10,000.5 kb',  10_000_500),
        ('10,000.5 kib', 10_240_512),
        ('10',           ValueError('Filesize string does not match expected pattern')),
        ('kb',           ValueError('Filesize string does not match expected pattern')),
        ('10 kbb',       ValueError('Filesize string does not match expected pattern')),
    ],
)
def test_filesize(s: str, expected: int | Exception) -> None:
    for i in (s, s.upper()):
        if isinstance(expected, Exception):
            with pytest.raises(expected.__class__, match=expected.args[0]):
                FromStr.filesize(i)
        else:
            assert FromStr.filesize(i) == expected
