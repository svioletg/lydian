import pytest

from lydian.util import FromStr


def test_to_bool() -> None:
    assert FromStr.to_bool('0') is FromStr.to_bool('false') is FromStr.to_bool('faLSE') is False
    assert FromStr.to_bool('1') is FromStr.to_bool('true') is FromStr.to_bool('trUE') is True

@pytest.mark.parametrize(('s', 'expected'),
    [
        ('1 b',          1),
        ('10 b',         10),
        ('1 kb',         1_000),
        ('10 kb',        10_000),
        ('1 kib',        1_024),
        ('10 kib',       10_240),
        ('1 mb',         1_000_000),
        ('10 mb',        10_000_000),
        ('1 mib',        1_0485_76),
        ('10 mib',       10_485_760),
        ('1 gb',         1_000_000_000),
        ('10 gb',        10_000_000_000),
        ('1 gib',        1_0737_418_24),
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
