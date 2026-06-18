import re
from typing import cast

import pytest

from lydian import const


@pytest.mark.parametrize(('pattern', 'content', 'expected_title'),
    [
        (const.MD_H1_REGEX, '# Header Level 1', ' Header Level 1'),
        (const.MD_H1_REGEX, '#Header Level 1', 'Header Level 1'),
        (const.MD_H2_REGEX, '## Header Level 2', ' Header Level 2'),
        (const.MD_H2_REGEX, '##Header Level 2', 'Header Level 2'),
        (const.MD_H3_REGEX, '### Header Level 3', ' Header Level 3'),
        (const.MD_H3_REGEX, '###Header Level 3', 'Header Level 3'),
    ],
)
def test_markdown_header_regex(pattern: re.Pattern[str], content: str, expected_title: str | None) -> None:
    m = pattern.search(content)
    if expected_title is None:
        assert m is None
        return
    m = cast('re.Match[str]', m)
    assert m.group('title') == expected_title
