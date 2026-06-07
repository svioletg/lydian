from pathlib import Path
from typing import Any

import pytest
import tomlkit as tm

from lydian.config import Config, LogLevel
from lydian.const import TESTS_DIR


def test_init() -> None:
    assert Config()

def test_dump(tmpdir: Path) -> None:
    inst = Config()
    toml_dest: Path = tmpdir / 'config.toml'

    assert (dumped := inst.to_toml(toml_dest)) == inst.to_toml()
    assert toml_dest.read_text('utf-8') == dumped

    # Check that it can be parsed back into valid TOML to begin with before trying the specialized stuff
    assert (parsed := tm.parse(dumped))
    assert inst.prefix == parsed['prefix']
    assert inst.vote_skipping.enabled == parsed['vote_skipping']['enabled']
    assert inst.logging.level == LogLevel(parsed['logging']['level'])
    assert inst.debug == parsed['debug']

def test_update_from_toml() -> None:
    inst = Config()

    inst.update_from_toml((TESTS_DIR / 'config-modified.toml').read_text('utf-8'))
    assert inst.prefix == '$'
    assert inst.vote_skipping.threshold_type == 'literal'
    assert inst.vote_skipping.literal == 2  # noqa: PLR2004
    assert inst.logging.level.name == 'WARNING'

def test_update_from_environment() -> None:
    inst = Config()

    env: dict[str, Any] = {'LYDIAN_LOG_LEVEL': 'WARNING'}

    inst.update_from_environment(env)
    assert isinstance(inst.logging.level, LogLevel)
    assert inst.logging.level.name == 'WARNING'

@pytest.mark.parametrize(('url', 'expected'),
    [
        ('https://www.youtube.com/watch?v=hlYquwq_hZ4', True),
        ('https://music.youtube.com/watch?v=hlYquwq_hZ4', True),
        ('https://m.youtube.com/watch?v=hlYquwq_hZ4', True),
        ('https://youtu.be/hlYquwq_hZ4', True),
        ('https://www.youtube.xyz/watch?v=hlYquwq_hZ4', False),
        ('https://abc.youtube.com/watch?v=hlYquwq_hZ4', False),
        ('https://n.youtube.com/watch?v=hlYquwq_hZ4', False),
        ('https://youtube/hlYquwq_hZ4', False),
        ('https://kinggizzard.bandcamp.com/track/grow-wings-and-fly', True),
        ('https://kinggizzard.bandcamp.com/album/phantom-island', True),
        ('https://kinggizzard.bondcamp.com/track/grow-wings-and-fly', False),
        ('https://kinggizzard.bondcamp.com/album/phantom-island', False),
    ],
)
def test_filter_media_url(url: str, expected: bool) -> None:
    conf = Config()

    conf.media_filter.allowed_urls = [
        r'https://((www|music|m)\.youtube\.com|youtu\.be)/',
        r'https://soundcloud\.com/',
        r'https://.*\.bandcamp\.com/',
    ]
    assert conf.filter_media_url(url) == expected

    conf.media_filter.allowed_urls = [
        r'-https://((www|music|m)\.youtube\.com|youtu\.be)/',
        r'-https://soundcloud\.com/',
        r'-https://.*\.bandcamp\.com/',
    ]
    assert conf.filter_media_url(url) == (not expected)
