import re
from typing import cast

import pytest

from lydian import const


def test_color_escape_regex() -> None:
    colored_octal = '\033[0;33mWARNING:\033[0m Less than \033[0;100m\033[0;36m80%\033[0m disk space remaining.'
    colored_hex = '\x1b[0;33mWARNING:\x1b[0m Less than \x1b[0;100m\x1b[0;36m80%\x1b[0m disk space remaining.'
    stripped = 'WARNING: Less than 80% disk space remaining.'
    assert const.COLOR_ESCAPE_REGEX.sub('', colored_octal) == stripped
    assert const.COLOR_ESCAPE_REGEX.sub('', colored_hex) == stripped

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

@pytest.mark.parametrize(('text', 'should_match'),
    [
        ('[download]   0.1% of    1.51MiB at  Unknown B/s ETA Unknown', True),
        ('[download]   0.2% of    1.51MiB at  Unknown B/s ETA Unknown', True),
        ('[download]   0.5% of    1.51MiB at    1.50MiB/s ETA 00:01', True),
        ('[download]   1.0% of    1.51MiB at    2.96MiB/s ETA 00:00', True),
        ('[download]   2.0% of    1.51MiB at    4.45MiB/s ETA 00:00', True),
        ('[download]   4.1% of    1.51MiB at    3.43MiB/s ETA 00:00', True),
        ('[download]   8.2% of    1.51MiB at    1.16MiB/s ETA 00:01', True),
        ('[download]  16.5% of    1.51MiB at    2.07MiB/s ETA 00:00', True),
        ('[download]  33.0% of    1.51MiB at    2.27MiB/s ETA 00:00', True),
        ('[download]  66.1% of    1.51MiB at    2.26MiB/s ETA 00:00', True),
        ('[download] 100.0% of    1.51MiB at    2.72MiB/s ETA 00:00', True),
        ('[download] 100% of    1.51MiB in 00:00:00 at 2.30MiB/s', False),
        ('abcxyz', False),
    ],
)
def test_ytdl_download_progress_regex(text: str, should_match: bool) -> None:
    assert should_match is (const.YTDL_DOWNLOAD_PROGRESS_REGEX.match(text) is not None)
