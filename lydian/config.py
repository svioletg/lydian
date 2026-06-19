"""Configuration handling for Lydian."""
import os
import re
import sys
import warnings
from argparse import ArgumentParser
from collections import OrderedDict
from collections.abc import Callable, Generator, Iterable, Mapping
from dataclasses import Field, asdict, dataclass, field, fields, is_dataclass
from functools import cached_property
from pathlib import Path
from types import NoneType
from typing import Any, Literal, Self, TypedDict, Union, cast, get_args, get_origin
from zoneinfo import ZoneInfo

import tomlkit as tm
from benedict import benedict
from dotenv import load_dotenv
from maybetype import Err, Ok, Result, maybe
from tomlkit.exceptions import ConvertError
from tomlkit.items import Item as TOMLItem

from lydian.const import CONFIG_PATH, LogLevel
from lydian.util import FromStr, get_dataclass_fields, is_annotated, partition, wrap_paragraphs

TOML_KEY_REGEX: re.Pattern[str] = re.compile(r'^\[?([\w.-]+)\]?', flags=re.MULTILINE)
TOML_TABLE_KEY_REGEX: re.Pattern[str] = re.compile(r'\[([\w.-]+)\]', flags=re.MULTILINE)

load_dotenv()

TOML_NONE: str = 'n/a'
"""A special dedicated string value for representing None in TOML."""

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
        tb.update(asdict(obj))
        return tb
    raise ConvertError(f'Cannot convert object of type {type(obj)}: {obj!r}')

tm.register_encoder(_toml_encoder)

def _default_command_aliases() -> dict[str, list[str]]:
    return {
        'help': ['h'],
        'join': ['j'],
        'leave': ['l'],
    }

def to_validator[T](func: Callable[[T], bool], err: str) -> Callable[[T], Result[T, str]]:
    """Transforms ``func`` to return a result of either the passed value or an error message."""
    return lambda x: Ok(x) if func(x) else Err(err)

def _validator_min(minimum: float) -> Callable[[float], Result[object, str]]:
    return lambda x: Ok(x) if x >= minimum else Err(f'Must be >= {minimum}: {x!r}')

def _validator_max(maximum: float) -> Callable[[float], Result[object, str]]:
    return lambda x: Ok(x) if x <= maximum else Err(f'Must be <= {maximum}: {x!r}')

_validate_positive = _validator_min(0)

class ConfigFieldMeta[T](TypedDict):
    """Metadata object for :py:class:`Config` fields."""

    env: str | None
    """Environment variable name (without the ``LYDIAN_`` prefix) corresponding to this field.

    Config fields can only be set by the environment when this key is present. Setting this key will require ``parser``
    to be set as well, which in this case should take a ``str`` and return the expected value.
    """
    converter: Callable[[object], object]
    """A function which takes the value parsed from TOML or an environment variable string value and returns the field's
    type."""
    converter_env: Callable[[str], object]
    """A converter function called when parsing an environment variable string value.

    Defaults to ``converter`` if not given.
    """
    converter_toml: Callable[[object], object]
    """A converter function called when parsing a TOML value.

    Defaults to ``converter`` if not given.
    """
    validators: Iterable[Callable[[T], Result[T, str]]]
    """An iterable of functions which take the field's type (after being parsed with ``converter``) and return ``Ok``
    with the passed value if valid, or ``Err`` with a message string."""

class ConfigField[T](Field[T]):
    """Class used to specify the ``metadata`` attribute type for :py:class:`Config` fields.

    Note that ``Config`` fields are still ``Field`` instances, and are not actually instances of this class, but those
    fields are expected to use :py:class:`ConfigFieldMeta` for their ``metadata`` values, so this is used for stronger
    typing.
    """

    metadata: ConfigFieldMeta[T]

@dataclass(kw_only=True)
class MediaFilterConfig:
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
class VoteSkippingConfig:
    """Configuration for track vote-skipping."""

    enabled: bool = field(default=False,
        doc='Whether to require a number of users to vote to skip tracks. If false, any users with permission to use'
            + ' -skip can skip the track immediately.')
    threshold_type: Literal['percentage', 'exact'] = field(default='percentage',
        doc='What kind of threshold to use for vote-skipping. "percentage" uses the value given for the "percentage"'
            + ' key to calculate how many users are needed to skip based on how many are connected to the channel at'
            + ' time -skip was used, e.g. percentage = 50 means 50% of users (rounded up) need to vote in order to'
            + ' skip.'
            + '\n"exact" will use the concrete value given for the "exact" key, requiring that >= that number of'
            + ' users vote to skip regardless of how many are connected to the channel.')
    percentage: int = field(default=50,
        metadata={'validators': [_validator_min(0), _validator_max(100)]})
    exact: int = 3

@dataclass(kw_only=True)
class LoggingConfig:
    """Configuration for logging."""

    level: LogLevel = field(default=LogLevel.INFO,
        doc='Minimum "level" of logs to show in terminal output. In ascending order, one of:'
            + f' {',  '.join(f'"{level.name}"' for level in LogLevel)}.'
            + f'\nCan also be their corresponding integer levels: {', '.join(f'{level.value}' for level in LogLevel)}',
        metadata={'env': 'LOG_LEVEL', 'converter': lambda s: LogLevel[s.upper()]},
    )
    utc: bool = field(default=True,
        doc="Whether to show log timestamps in UTC. If false, they are shown in your system's local time.",
        metadata={'env': 'LOG_UTC'},
    )

@dataclass(kw_only=True)
class Config:
    """Dataclass which handles project-wide configuration and can save or load values via TOML.

    The ``doc`` value of a field, if not empty, will be used as a TOML comment preceding the key.
    See :py:class:`ConfigFieldMeta` for details on how a field's ``metadata`` is used.
    """

    debug: bool = field(default=False,
        doc='Enables various commands and features intended for developers.'
            + ' See the README for a full description of what debug mode does:'
            + ' https://github.com/svioletg/lydian/blob/main/README.md',
        metadata={'env': 'DEBUG'})

    # Bot personalization
    prefix: str = '-'

    # Bot functionality
    check_for_updates: bool = field(default=True,
        doc='Whether to check for new releases of Lydian at startup.',
        metadata={'env': 'CHECK_UPDATES'})

    check_for_stable_only: bool = field(default=True,
        doc='Whether to exclude pre-releases when checking for updates.',
        metadata={'env': 'CHECK_STABLE_ONLY'})

    bot_console: bool = field(default=True,
        doc="Enables Lydian's interactive console while running.",
        metadata={'env': 'BOT_CONSOLE'})

    command_aliases: dict[str, list[str]] = field(default_factory=_default_command_aliases)

    stream_media: bool = field(default=True,
        doc='Whether to stream media instead of downloading it to disk and playing the file.')

    # Limits, thresholds
    max_duration: int | None = field(default=None,
        doc=f'Maximum duration (in seconds) of media that can be played by the bot. Set to {TOML_NONE!r} for no limit.',
        metadata={'validators': [_validate_positive]})

    max_duration_allow_unknown: bool = field(default=False,
        doc="Whether to allow media whose duration couldn't be retrieved when max-duration is more than 0.")

    max_filesize: int = field(default=20_000_000,
        doc='Maximum filesize in bytes for media that can be downloaded by the bot.'
            + ' Will have no effect when streaming media (stream-media = true).',
        metadata={'converter': FromStr.to_filesize, 'validators': [_validate_positive]})

    max_playlist_length: int = field(default=20,
        doc='Maximum number of items that can be added from a single playlist link.',
        metadata={'validators': [_validate_positive]})

    max_queue_length: int = field(default=100,
        doc='Maximum number of items that can be added to the media queue.',
        metadata={'validators': [_validate_positive]})

    media_dir_warn_threshold: int | None = field(default=100_000_000,
        doc='Total size in bytes that downloaded media can take up before a warning is emitted at bot'
            + f' startup. Set to {TOML_NONE!r} to disable the warning entirely.',
        metadata={'converter': FromStr.to_filesize, 'validators': [_validator_min(-1)]})

    # Timeouts, timers
    inactivity_timeout: int | None = field(default=120,
        doc='How long in seconds the bot can be inactive (not playing anything and the queue is empty) before'
            + f' disconnecting. Set to {TOML_NONE!r} to never disconnect for inactivity.',
        metadata={'validators': [_validate_positive]})
    lonely_timeout: int | None = field(default=120,
        doc='How long in seconds the bot can be the only user in a voice channel before disconnecting.'
            + f' Set to {TOML_NONE!r} to never disconnect in this case.',
        metadata={'validators': [_validate_positive]})

    # Tables
    media_filter: MediaFilterConfig = field(default_factory=MediaFilterConfig)
    vote_skipping: VoteSkippingConfig = field(default_factory=VoteSkippingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @cached_property
    def fields(self) -> dict[str, ConfigField]:
        """A dictionary of dotted field keypaths to their field objects."""
        return cast('dict[str, ConfigField]', get_dataclass_fields(self))

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

    def set(self, keypath: str | list[str], val: object) -> None:
        """Sets an attribute by a dotted keypath or iterable of keys to the given value.

        No type checking or validation is performed by this method. ``AttribueError`` is raised if the attribute does
        not exist.
        """
        *parts, stem = keypath.split('.') if isinstance(keypath, str) else keypath

        target = self
        for p in parts:
            target = getattr(target, p)

        if not hasattr(target, stem):
            raise AttributeError(f'{keypath!r}: no attribute {stem!r} for object {target!r}')

        setattr(target, stem, val)

    def to_toml(self, fp: str | Path | None = None, *, add_comments: bool = True) -> str:
        """Returns this object converted into a TOML string.

        If ``fp`` is not ``None``, the TOML string will also be written to the file at that path.

        :param add_comments: Whether to write comments for specified keys.
        """
        doc: tm.TOMLDocument = tm.document()
        doc.add(tm.comment('discord-vc-bot configuration'))
        doc.add(tm.nl())

        comments: dict[str, dict[str, str]] = {}
        if add_comments:
            for name, f in self.fields.items():
                comments[name] = {}
                if env_var := f.metadata.get('env'):
                    comments[name]['inline'] = f'env: LYDIAN_{env_var}'
                if f.doc:
                    comments[name]['post'] = f'{name.split('.')[-1]}: {f.doc}'

        for fld in fields(self):
            if fld.type is MediaFilterConfig:
                data = tm.item(asdict(getattr(self, fld.name)))
                data['allowed_extractors'] = [tm.string(s, literal=True) for s in data['allowed_extractors'].unwrap()]
                data['allowed_urls'] = [tm.string(s, literal=True) for s in data['allowed_urls'].unwrap()]
            else:
                data = getattr(self, fld.name)

            if data is None:
                data = tm.string(TOML_NONE, literal=True)

            doc.add(fld.name, data)

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

        supported_fields: dict[str, ConfigField] = {k:v for k, v in self.fields.items() if 'env' in v.metadata}
        for name, fld in supported_fields.items():
            if not (env_val := env.get(f'LYDIAN_{fld.metadata['env']}')):
                continue

            converter: Callable[[str], Any] | None
            if converter := fld.metadata.get('converter_env', fld.metadata.get('converter')):
                if not callable(converter):
                    raise TypeError(f'Config field "{name}" parser must be callable: {converter!r}')
            elif fld.type is bool:
                converter = FromStr.to_bool
            else:
                converter = cast('type', fld.type)

            val = converter(env_val)

            if not isinstance(val, cast('type', fld.type)):
                raise TypeError(f'Invalid type for field "{name}": {val!r}')

            self.set(name, val)

    @staticmethod
    def _check_type_with_field[T](value: object, fld: ConfigField[T]) -> T | None:  # noqa: C901
        """Parses a value according to the given field and ensures it is the correct type.

        :raises TypeError:
            This value is the wrong type for this field, and the parser (if present) could not convert it to such.
        :raises ValueError:
            An invalid value was given, likely a validator failed or an unexpected value was given for a ``Literal``.
        """
        if isinstance(fld.type, str):
            raise TypeError(f'type attribute of field is str: {fld!r}')

        typ = fld.type
        t_args = get_args(typ)

        # Annotated types don't do anything special for config fields, just take the type
        if is_annotated(typ):
            typ = t_args[0]
            t_args = get_args(typ)

        # Parse
        if (t_origin := get_origin(typ) or typ) is Union:
            if not ((len(t_args) == 2) and (t_args[1] is NoneType)):  # noqa: PLR2004
                raise TypeError(f'Union types are only supported for config fields if the union is T | None: {typ!r}')
            if value == TOML_NONE:
                return None
            t_origin = t_args[0]

        parsed = fld.metadata.get('converter_toml', fld.metadata.get('converter', lambda x: x))(value)
        if (t_origin is Literal):
            if parsed not in t_args:
                raise ValueError(f'Invalid value for Literal[{', '.join(repr(i) for i in t_args)}] type: {value!r}')
        elif not isinstance(parsed, t_origin):
            raise TypeError(f'Incorrect type for config field "{fld.name}" of type {fld.type}: {value!r}')

        parsed = cast('T', parsed)

        # Validate
        for func in fld.metadata.get('validators', ()):
            if not (result := func(parsed)):
                raise ValueError(f'Invalid value for config field "{fld.name}": {result.unwrap_err()}')

        return parsed

    def update_from_toml(self, toml_str: str, *, on_missing: Literal['raise', 'warn', 'continue'] = 'warn') -> None:
        """Update the config using values from a TOML string.

        :param on_missing: Whether to raise, warn, or ignore unrecognized keys.
        """
        loaded: benedict[str, Any] = benedict(tm.parse(toml_str))
        # If a field's type is dict, it's a dynamic dictionary that we don't want to check each individual key of
        dict_field_keys: list[str] = [k for k, v in self.fields.items() if get_origin(v.type) is dict]

        to_search: Generator[str] = (
            kp for kp in loaded.keypaths()
            if not any(kp.startswith(pref + '.') for pref in dict_field_keys)
        )

        for key in to_search:
            if not (fld := self.fields.get(key)):
                match on_missing:
                    case 'raise':
                        raise KeyError(f'Unknown config key: {key}')
                    case 'warn':
                        warnings.warn(f'Unknown config key: {key}', UnknownConfigKeyWarning, stacklevel=2)
                        continue
                    case 'continue':
                        continue
                    case _:
                        raise ValueError(f'Unexpected on_missing value: {on_missing!r}')

            if hasattr(fld.type, '__dataclass_fields__'):
                # Dataclass attributes will get set through their individual keypaths
                continue

            self.set(key, self._check_type_with_field(loaded[key], fld))

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
            and ((key := f'{table_prefix}{m.group(1)}') in comment_map):
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
