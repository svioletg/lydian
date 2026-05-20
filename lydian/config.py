"""Configuration handling for Lydian."""
import os
import re
import sys
import warnings
from argparse import ArgumentParser
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import Field, asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, Self, cast
from zoneinfo import ZoneInfo

import tomlkit as tm
from benedict.core import unflatten
from dotenv import load_dotenv
from maybetype import maybe
from tomlkit.exceptions import ConvertError
from tomlkit.items import InlineTable
from tomlkit.items import Item as TOMLItem
from tomlkit.toml_document import TOMLDocument

from lydian.const import CONFIG_PATH, LogLevel
from lydian.util import DataclassUpdateMixin, FromStr, get_dataclass_fields, partition, wrap_paragraphs

TOML_KEY_REGEX: re.Pattern[str] = re.compile(r'^\[?([\w.-]+)\]?', flags=re.MULTILINE)
TOML_TABLE_KEY_REGEX: re.Pattern[str] = re.compile(r'\[([\w.-]+)\]', flags=re.MULTILINE)

load_dotenv()

class UnknownConfigKeyWarning(Warning):
    """Emitted when a key is found in TOML that is not present in the :py:class:`Config` dataclass."""

    @classmethod
    def emit(cls, key: str, *, stacklevel: int = 2) -> None:
        """Emit this warning for a key with the standard warning message."""
        warnings.warn(f'Unrecognized config key in TOML: {key}', cls, stacklevel=stacklevel)

def _toml_encoder(obj: object) -> TOMLItem:
    if isinstance(obj, ZoneInfo):
        return tm.string(maybe(obj.tzname(None)).unwrap(f'Failed to get tzname from ZoneInfo: {obj!r}'))
    if is_dataclass(obj) and not isinstance(obj, type):
        tb = tm.table()
        tb.update({k.replace('_', '-'):v for k, v in asdict(obj).items()})
        return tb
    raise ConvertError(f'Cannot convert object of type {type(obj)}: {obj!r}')

tm.register_encoder(_toml_encoder)

def env_to_bool(s: str) -> bool:
    """Returns an environment variable value parsed to a ``bool``.

    - False: ``0``, ``'false'`` (any case)
    - True: ``1``, ``'true'`` (any case)
    """
    s = s.strip().lower()
    if s in ['0', 'false']:
        return False
    if s in ['1', 'true']:
        return True
    raise ValueError(f"Expected 0, 1, 'false', or 'true' for boolean environment variable: {s!r}")

def _default_command_aliases() -> dict[str, list[str]]:
    return {
        'help': ['h'],
        'join': ['j'],
        'leave': ['l'],
    }

@dataclass(kw_only=True)
class MediaFilterConfig(DataclassUpdateMixin):
    """Configuration for whitelisting or blacklisting input URLs and extractors."""

    allowed_extractors: list[str] = field(default_factory=lambda: ['default'],
        doc='A list of regular expressions which determine what yt-dlp extractors to allow.'
            + ' "default" will include almost every extractor yt-dlp has available.'
            + ' Prefix an expression with a hyphen (-) to blacklist it instead.'
            + '\nExtractor names: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md')
    allowed_urls: list[str] = field(default_factory=lambda: ['https://.*'],
        doc='A list of regular expressions which determine what URLs to allow.'
            + ' Prefix an expression with a hyphen (-) to blacklist it instead.')

@dataclass(kw_only=True)
class VoteSkippingConfig(DataclassUpdateMixin):
    """Configuration for track vote-skipping."""

    enabled: bool = True
    threshold_type: Literal['percentage', 'exact'] = 'percentage'
    percentage: int = 50
    exact: int = 3

@dataclass(kw_only=True)
class LoggingConfig(DataclassUpdateMixin):
    """Configuration for logging."""

    log_level: LogLevel = field(default=LogLevel.INFO, metadata={
        'env': 'LOG_LEVEL',
        'converter': lambda s: LogLevel(s.upper()),
    })
    utc: bool = field(default=True,
        doc="Whether to show log timestamps in UTC. If false, they are shown in your system's local time.",
        metadata={'env': 'LOG_UTC'},
    )

@dataclass(kw_only=True)
class Config(DataclassUpdateMixin):
    """Dataclass which handles project-wide configuration and can save or load values via TOML.

    The ``doc`` value of a field, if not empty, will be used as a TOML comment preceding the key.

    A field's ``metadata`` will be checked for the following keys under certain circumstances:

    - ``converter``: A function which takes the value parsed from TOML and returns the field's type, allowing for things
        like filesize fields taking strings (e.g. "10 MB") and converting them to an ``int`` of bytes.
    - ``env``: Environment variable name (without the ``LYDIAN_`` prefix) corresponding to this field. Config fields
        can only be set by the environment when this key is present. Setting this key will require ``parser`` to be set
        as well, which in this case should take a ``str`` and return the expected value.
    """

    prefix: str = '-'
    debug: bool = field(default=False,
        doc='Enables various commands and features intended for developers.'
            + ' See the README for a full description of what debug mode does:'
            + ' https://github.com/svioletg/lydian-discord-bot/blob/main/README.md',
        metadata={'env': 'DEBUG'},
    )
    command_aliases: dict[str, list[str]] = field(default_factory=_default_command_aliases)
    max_duration: int = field(default=0,
        doc='Maximum duration (in seconds) of media that can be played by the bot. Set to 0 for no limit.')
    max_duration_allow_unknown: bool = field(default=False,
        doc="Whether to allow media whose duration couldn't be retrieved when max-duration is more than 0.")
    max_filesize: int = field(default=20_000_000,
        doc='Maximum filesize in bytes for media that can be downloaded by the bot.'
            + ' Will have no effect when streaming media (stream-media = true).',
        metadata={'converter': FromStr.filesize},
    )
    max_playlist_length: int = field(default=20,
        doc='Maximum number of items that can be added from a single playlist link.',
    )
    max_queue_length: int = field(default=100,
        doc='Maximum number of items that can be added to the media queue.',
    )
    media_dir_warn_threshold: int = field(default=100_000_000,
        doc='Total size in bytes that downloaded media can take up before a warning is emitted at bot'
            + ' startup. Set to -1 to disable the warning entirely.',
        metadata={'converter': FromStr.filesize},
    )
    stream_media: bool = field(default=True,
        doc='Whether to stream media instead of downloading it to disk and playing the file.',
    )
    inactivity_timeout: int = field(default=120,
        doc='How long in seconds the bot can be inactive (not playing anything and the queue is empty) before'
            + ' disconnecting. Set to -1 to never disconnect for inactivity.',
    )
    lonely_timeout: int = field(default=120,
        doc='How long in seconds the bot can be the only user in a voice channel before disconnecting.'
            + ' Set to -1 to never disconnect in this case.',
    )

    media_filter: MediaFilterConfig = field(default_factory=MediaFilterConfig)
    vote_skipping: VoteSkippingConfig = field(default_factory=VoteSkippingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_toml(cls, toml_str: str) -> Self:
        """Creates a config object from a TOML string.

        Shortcut for creating the instance then using :py:meth:`update_from_toml`.
        """
        inst = cls()
        inst.update_from_toml(toml_str)
        return inst

    def filter_media_url(self, url: str) -> bool:
        """Returns whether a given URL should be allowed to be played based on this config object's filters."""
        filter_yes, filter_no = partition(lambda s: s[0] != '-', self.media_filter.allowed_urls)
        return (True if not filter_yes else any(re.match(pattern, url) for pattern in filter_yes)) \
            and not any(re.match(pattern[1:], url) for pattern in filter_no)

    def to_toml(self, fp: str | Path | None = None, *, add_comments: bool = True) -> str:
        """Returns this object converted into a TOML string.

        If ``fp`` is not ``None``, the TOML string will also be written to the file at that path.

        :param add_comments: Whether to write comments for specified keys.
        """
        doc: tm.TOMLDocument = tm.document()
        doc.add(tm.comment('discord-vc-bot configuration'))
        doc.add(tm.nl())

        comments: dict[str, dict[str, str]] = {}
        for name, f in get_dataclass_fields(self).items():
            comments[name] = {}
            if env_var := f.metadata.get('env'):
                comments[name]['inline'] = f'env: LYDIAN_{env_var}'
            if f.doc:
                comments[name]['pre'] = f'{name.split('.')[-1]}: {f.doc}'

        for fld in fields(self):
            toml_key: str = fld.name.replace('_', '-')

            if fld.type is MediaFilterConfig:
                data: InlineTable = tm.item(asdict(getattr(self, fld.name)))
                data['allowed_extractors'] = [tm.string(s, literal=True) for s in data['allowed_extractors'].unwrap()]
                data['allowed_urls'] = [tm.string(s, literal=True) for s in data['allowed_urls'].unwrap()]
            else:
                data = getattr(self, fld.name)

            doc.add(toml_key, data)

        toml_string: str = doc.as_string() + '\n'
        if add_comments:
            toml_string = add_comments_to_toml(toml_string, comments)

        if fp:
            Path(fp).write_text(toml_string, encoding='utf-8')

        return toml_string

    def update_from_environment(self, env: Mapping[str, str] | None = None) -> None:
        """Updates the config using values from environment variables prefixed ``LYDIAN_``.

        Environment variables prefixed with ``LYDIAN_`` that do not correspond to a config key are ignored.

        :param env: If ``None``, the current OS environment is used. A ``str`` to ``str`` mapping can be given to use
            instead, e.g. for testing.
        """
        # An empty dictionary should still be allowed if passed, so no "env or os.environ"
        env = maybe(env).unwrap_or(os.environ)

        supported_fields: dict[str, Field] = {k:v for k, v in get_dataclass_fields(self).items() if 'env' in v.metadata}
        update_map: dict[str, Any] = {}
        for name, fld in supported_fields.items():
            if not (env_val := env.get(f'LYDIAN_{fld.metadata['env']}')):
                continue

            converter: Callable[[str], Any] | None
            if converter := fld.metadata.get('converter'):
                if not callable(converter):
                    raise TypeError(f'Config field "{name}" parser must be callable: {converter!r}')
            elif fld.type is bool:
                converter = env_to_bool
            else:
                converter = cast('type', fld.type)

            val = converter(env_val)

            if not isinstance(val, cast('type', fld.type)):
                raise TypeError(f'Invalid type for field "{name}": {val!r}')

            update_map[name] = val

        self.update(unflatten(update_map, '.'))

    def update_from_toml(self, toml_str: str, *, on_missing: Literal['raise', 'warn', 'continue'] = 'warn') -> None:
        """Update the config using values from a TOML string.

        :param on_missing: Whether to raise, warn, or ignore unrecognized keys.
        """
        loaded: TOMLDocument = tm.parse(toml_str)
        self.update(
            loaded.unwrap(),
            on_missing=UnknownConfigKeyWarning.emit if on_missing == 'warn' else on_missing,
        )

def add_comments_to_toml(toml: str, comment_map: dict[str, dict[str, str]], comment_width: int = 80) -> str:
    """Returns a TOML string with comments added to every key in ``comment_map``.

    :param comment_map: A dictionary which can contain any of these three keys: ``pre``, ``inline``, ``post``.
        ``pre`` will be placed before the key. ``inline`` is placed on the same line of the key, at the end of the line
        preceded by a space. ``post`` will be placed after the key.
    :param comment_width: How long any individual line of a non-inline comment can be before wrapping it to the next
        line. Inline comments are never wrapped. This width will include the leading ``# `` on each line.
    """
    toml_lines: list[str] = toml.splitlines()

    last_line: str = ''
    table_prefix: str = ''
    key_line_map: OrderedDict[str, int] = OrderedDict()
    for n, ln in enumerate(toml_lines):
        if not ln:
            table_prefix = ''
        if last_line and (last_line[0] == '['):
            table_prefix = maybe(TOML_TABLE_KEY_REGEX.match(last_line)) \
                .unwrap(f'Failed to match TOML table key name from line: {last_line}') \
                .group(1) + '.'
        if (m := TOML_KEY_REGEX.match(ln)) \
            and ((key := f'{table_prefix}{m.group(1)}'.replace('-', '_')) in comment_map):
            key_line_map[key] = n
        last_line = ln

    line_offset: int = 0
    for key, lineno in key_line_map.items():
        if comment_inline := comment_map[key].get('inline'):
            toml_lines[lineno + line_offset] = toml_lines[lineno + line_offset] + f' # {comment_inline}'
        if comment_pre := comment_map[key].get('pre'):
            comment: list[str] = wrap_paragraphs(
                comment_pre,
                width=comment_width,
                initial_indent='# ',
                subsequent_indent='#    ',
                indent_mode='single',
            )
            toml_lines = toml_lines[:lineno + line_offset] + comment + toml_lines[lineno + line_offset:]
            line_offset += len(comment)
        if comment_post := comment_map[key].get('post'):
            comment: list[str] = wrap_paragraphs(
                comment_post,
                width=comment_width,
                initial_indent='# ',
                subsequent_indent='#    ',
                indent_mode='single',
            )
            toml_lines = toml_lines[:1 + lineno + line_offset] + comment + toml_lines[1 + lineno + line_offset:]
            line_offset += len(comment)

    return '\n'.join(toml_lines)

CONFIG_DEFAULT = Config()

config = Config() if not CONFIG_PATH.exists() else Config.from_toml(CONFIG_PATH.read_text('utf-8'))
config.update_from_environment(os.environ)

def main() -> int:
    """Write the default configuration as TOML to a given file path."""
    parser = ArgumentParser()
    parser.add_argument('-o', '--out', type=Path,
        help='A file to write the default config to. Written to stdout if not given.')
    parser.add_argument('--no-comments', action='store_true',
        help='Adds no comments to the output TOML.')

    args = parser.parse_args()
    dest: Path | None = args.out
    add_comments: bool = not args.no_comments

    toml: str = Config().to_toml(add_comments=add_comments).strip() + '\n'

    if not dest:
        print(toml)  # noqa: T201
        return 0

    dest.write_text(toml, 'utf-8')
    print(f'Default configuration written to: {dest}')  # noqa: T201
    return 0

if __name__ == '__main__':
    sys.exit(main())
