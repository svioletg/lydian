"""Configuration handling for Lydian."""
import os
import re
import sys
import textwrap
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import Field, asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, Self, cast
from zoneinfo import ZoneInfo

import tomlkit as tm
from benedict.core import unflatten
from dotenv import load_dotenv
from maybetype import maybe
from tomlkit.exceptions import ConvertError
from tomlkit.items import Item as TOMLItem
from tomlkit.toml_document import TOMLDocument

from lydian.const import CONFIG_PATH, LogLevel
from lydian.util import DataclassUpdateMixin, get_dataclass_fields

TOML_KEY_REGEX: re.Pattern[str] = re.compile(r'^\[?([\w.-]+)\]?', flags=re.MULTILINE)
TOML_TABLE_KEY_REGEX: re.Pattern[str] = re.compile(r'\[([\w.-]+)\]', flags=re.MULTILINE)

load_dotenv()

def _toml_encoder(obj: object) -> TOMLItem:
    if isinstance(obj, ZoneInfo):
        return tm.string(maybe(obj.tzname(None)).unwrap(f'Failed to get tzname from ZoneInfo: {obj!r}'))
    if is_dataclass(obj) and not isinstance(obj, type):
        tb = tm.table()
        tb.update({k.replace('_', '-'):v for k, v in asdict(obj).items()})
        return tb
    raise ConvertError(f'Cannot convert object of type {type(obj)}: {obj!r}')

tm.register_encoder(_toml_encoder)  # ty:ignore[invalid-argument-type]

def _default_command_aliases() -> dict[str, list[str]]:
    return {
        'join': ['j'],
        'leave': ['l'],
    }

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
        'envconv': lambda s: LogLevel(s.upper()),
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

    - ``env``: Environment variable name (without the ``LYDIAN_`` prefix) corresponding to this field
    - ``envconv``: Function which takes ``str`` and returns the field's type, used to convert string values when
      updating configuration from enviornment variables; has no effect if ``env`` is not present
    """

    prefix: str = '-'
    debug: bool = field(
        default=False,
        doc='Enables various commands and features intended for developers.'
            + ' Will also override the log level to "DEBUG".',
        metadata={'env': 'DEBUG', 'envconv': env_to_bool},
    )
    command_aliases: dict[str, list[str]] = field(default_factory=_default_command_aliases)
    max_filesize: int = field(default=20_000_000,
        doc='Maximum filesize in bytes for media that can be downloaded by the bot.')
    vote_skipping: VoteSkippingConfig = field(default_factory=VoteSkippingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_toml(cls, fp: str | Path) -> Self:
        """Creates a config object from a TOML file.

        Shortcut for creating the instance then using :py:meth:`update_from_toml`.
        """
        inst = cls()
        inst.update_from_toml(fp)
        return inst

    def to_toml(self, fp: str | Path | None = None) -> str:
        """Returns this object converted into a TOML string.

        If ``fp`` is not ``None``, the TOML string will also be written to the file at that path.
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

            doc.add(toml_key, getattr(self, fld.name))

        toml_string: str = add_comments_to_toml(doc.as_string(), comments) + '\n'

        if fp:
            Path(fp).write_text(toml_string, encoding='utf-8')

        return toml_string

    def update_from_environment(self, env: Mapping[str, str] | None = None) -> None:
        """Updates the config using values from environment variables prefixed ``LYDIAN_``.

        Environment variables prefixed with ``LYDIAN_`` that do not correspond to a config key are ignored.

        :param env: If ``None``, the current OS environment is used. A ``str`` to ``str`` mapping can be given to use
            instead, e.g. for testing.
        """
        # An empty dictionary should still be allowed if passed
        env = maybe(env).unwrap_or(os.environ)

        supported_fields: dict[str, Field] = {k:v for k, v in get_dataclass_fields(self).items() if 'env' in v.metadata}
        update_map: dict[str, Any] = {}
        for name, fld in supported_fields.items():
            if not (env_val := env.get(f'LYDIAN_{fld.metadata['env']}')):
                continue

            # Fall back on the field type as a constructor if no converter is specified, but don't convert if envconv
            # has been explicitly set to None
            val = env_val if not (converter := fld.metadata.get('envconv', fld.type)) else converter(env_val)

            if not isinstance(val, cast('type', fld.type)):
                raise TypeError(f'Invalid type for field "{name}": {val!r}')

            update_map[name] = val

        self.update(unflatten(update_map, '.'))

    def update_from_toml(self, fp: str | Path, *, missing_ok: bool = True) -> None:
        """Update the config using values from a TOML file.

        :param missing_ok: Whether to ignore keys in the TOML that don't correspond to any ``Config`` fields.
            If ``False``, ``KeyError`` is raised.
        """
        with open(fp, 'r', encoding='utf-8') as f:
            loaded: TOMLDocument = tm.load(f)
        self.update(loaded.unwrap(), missing_ok=missing_ok)

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
        if (m := TOML_KEY_REGEX.match(ln)) and ((key := f'{table_prefix}{m.group(1)}') in comment_map):
            key_line_map[key] = n
        last_line = ln

    line_offset: int = 0
    for key, lineno in key_line_map.items():
        if comment_inline := comment_map[key].get('inline'):
            toml_lines[lineno + line_offset] = toml_lines[lineno + line_offset] + f' # {comment_inline}'
        if comment_pre := comment_map[key].get('pre'):
            comment: list[str] = textwrap.wrap(
                comment_pre,
                width=comment_width,
                initial_indent='# ',
                subsequent_indent='# ',
            )
            toml_lines = toml_lines[:lineno + line_offset] + comment + toml_lines[lineno + line_offset:]
            line_offset += len(comment)
        if comment_post := comment_map[key].get('post'):
            comment: list[str] = textwrap.wrap(
                comment_post,
                width=comment_width,
                initial_indent='# ',
                subsequent_indent='# ',
            )
            toml_lines = toml_lines[:1 + lineno + line_offset] + comment + toml_lines[1 + lineno + line_offset:]
            line_offset += len(comment)

    return '\n'.join(toml_lines)

CONFIG_DEFAULT = Config()

config = Config() if not (CONFIG_PATH.exists()) else Config.from_toml(CONFIG_PATH)
config.update_from_environment(os.environ)

def main() -> int:
    """Write the default configuration as TOML to a given file path."""
    toml: str = Config().to_toml()
    if len(sys.argv) < 2:  # noqa: PLR2004
        print(toml)  # noqa: T201
        return 0
    fp: Path = Path(sys.argv[1])
    fp.write_text(toml, 'utf-8')
    print(f'Default configuration written to: {fp}')  # noqa: T201
    return 0

if __name__ == '__main__':
    sys.exit(main())
