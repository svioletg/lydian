from pathlib import Path
from typing import Any

import pytest
import tomlkit as tm

from lydian.config import Config, LogLevel, env_to_bool
from lydian.const import TESTS_DIR


def test_init() -> None:
    assert Config()

def test_update() -> None:
    inst = Config()
    new_vote_percentage: int = 70
    inst.vote_skipping.percentage = new_vote_percentage

    inst.update({'prefix': '$', 'logging': {'log_level': 'ERROR'}, 'vote_skipping': {'enabled': False}})
    assert inst.prefix == '$'
    assert inst.logging.log_level == 'ERROR'
    assert inst.vote_skipping.enabled is False
    # Assert only the given fields were updated
    assert inst.vote_skipping.percentage == new_vote_percentage

def test_dump(tmpdir: Path) -> None:
    inst = Config()
    toml_dest: Path = tmpdir / 'config.toml'

    assert (dumped := inst.to_toml(toml_dest)) == inst.to_toml()
    assert toml_dest.read_text('utf-8') == dumped

    # Check that it can be parsed back into valid TOML to begin with before trying the specialized stuff
    assert (parsed := tm.parse(dumped))
    assert inst.prefix == parsed['prefix']
    assert inst.vote_skipping.enabled == parsed['vote-skipping']['enabled']
    assert inst.logging.log_level == parsed['logging']['log-level']
    assert inst.debug == parsed['debug']

def test_env_to_bool() -> None:
    assert env_to_bool('0') is env_to_bool('false') is env_to_bool('faLSE') is False
    assert env_to_bool('1') is env_to_bool('true') is env_to_bool('trUE') is True

def test_update_from_toml() -> None:
    inst = Config()

    inst.update_from_toml((TESTS_DIR / 'config-modified.toml').read_text('utf-8'))
    assert inst.prefix == '$'
    assert inst.vote_skipping.threshold_type == 'exact'
    assert inst.vote_skipping.exact == 2  # noqa: PLR2004
    assert inst.logging.log_level == 'WARNING'

def test_update_from_environment() -> None:
    inst = Config()

    env: dict[str, Any] = {'LYDIAN_LOG_LEVEL': 'WARNING'}

    inst.update_from_environment(env)
    assert isinstance(inst.logging.log_level, LogLevel)
    assert inst.logging.log_level == 'WARNING'

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
