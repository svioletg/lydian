"""Configuration handling for Lydian."""
import os
import re
import sys
import textwrap
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import Field, asdict, dataclass, field, fields, is_dataclass
from enum import StrEnum
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

from lydian.const import CONFIG_PATH
from lydian.util import DataclassUpdateMixin, get_dataclass_fields

TOML_KEY_REGEX: re.Pattern[str] = re.compile(r'^\[?([\w.-]+)\]?', flags=re.MULTILINE)
TOML_TABLE_KEY_REGEX: re.Pattern[str] = re.compile(r'\[([\w.-]+)\]', flags=re.MULTILINE)

load_dotenv()

def _default_auto_remove_list() -> list[str]:
    return [
        '.m4a',
        '.mp3',
        '.mp4',
        '.ogg',
        '.opus',
        '.wav',
        '.webm',
    ]

def _toml_encoder(obj: object) -> TOMLItem:
    if isinstance(obj, ZoneInfo):
        return tm.string(maybe(obj.tzname(None)).unwrap(f'Failed to get tzname from ZoneInfo: {obj!r}'))
    if is_dataclass(obj) and not isinstance(obj, type):
        tb = tm.table()
        tb.update({k.replace('_', '-'):v for k, v in asdict(obj).items()})
        return tb
    raise ConvertError(f'Cannot convert object of type {type(obj)}: {obj!r}')

tm.register_encoder(_toml_encoder)  # ty:ignore[invalid-argument-type]

@dataclass(kw_only=True)
class VoteSkippingConfig(DataclassUpdateMixin):
    """Configuration for track vote-skipping."""

    enabled: bool = True
    threshold_type: Literal['percentage', 'exact'] = 'percentage'
    percentage: int = 50
    exact: int = 3

class LogLevel(StrEnum):  # noqa: D101
    TRACE = 'TRACE'
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

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
    debug: bool = field(default=False,
        doc='Enables various commands and features intended for developers.'
            + ' Will also override the log level to "DEBUG".',
        metadata={'env': 'DEBUG'})
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

        comments: dict[str, str] = {}
        for name, f in get_dataclass_fields(self).items():
            comment: str = f.doc or ''
            if env_var := f.metadata.get('env'):
                comment = f'[Environment variable: LYDIAN_{env_var}] ' + comment
            if comment:
                comments[name] = comment

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

def add_comments_to_toml(toml: str, comment_map: dict[str, str]) -> str:
    """Returns a TOML string with comments added to the lines preceding every key in ``comment_map``."""
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
        comment: list[str] = textwrap.wrap(comment_map[key], width=100, initial_indent='# ', subsequent_indent='# ')
        toml_lines = toml_lines[:lineno + line_offset] + comment + toml_lines[lineno + line_offset:]
        line_offset += len(comment)

    return '\n'.join(toml_lines)

CONFIG_DEFAULT = Config()

config = Config() if not (CONFIG_PATH.exists()) else Config.from_toml(CONFIG_PATH)
config.update_from_environment(os.environ)

def main() -> int:
    """Write the default configuration as TOML to a given file path."""
    if len(sys.argv) < 2:  # noqa: PLR2004
        print('Error: Provide a filename to write the default configuration to.')  # noqa: T201
        return 1
    fp: str = sys.argv[1]
    Config().to_toml(fp)
    print(f'Default configuration written to: {fp}')  # noqa: T201
    return 0

if __name__ == '__main__':
    sys.exit(main())
