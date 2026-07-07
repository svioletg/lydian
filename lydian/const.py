"""Constant or singleton values for use across the rest of the package."""
import re
import sys
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, Literal

import loguru
from benedict import benedict
from emoji import emojize
from loguru import logger
from rich.console import Console
from rich.highlighter import Highlighter
from rich.text import Text
from rich.theme import Theme

from lydian import __version__

# GitHub URLs
GH_REPO: str = 'https://github.com/svioletg/lydian'
GH_ISSUES: str = GH_REPO + '/issues'
GH_CHANGELOG_WEB: str = GH_REPO + '/blob/main/CHANGELOG.md'
GH_CHANGELOG_RAW: str = 'https://raw.githubusercontent.com/svioletg/lydian/refs/heads/main/CHANGELOG.md'

GH_API_ROOT: str = 'https://api.github.com'
GH_REPO_API_ROOT: str = GH_API_ROOT + '/repos/svioletg/lydian'

# Paths
PACKAGE_DIR      : Path = Path(__file__).resolve().parent
""":meta hide-value:"""
TESTS_DIR        : Path = PACKAGE_DIR.parent / 'tests'
""":meta hide-value:"""
DEFAULT_DATA_DIR : Path = PACKAGE_DIR / 'lydian-data'
"""Points to a ``lydian-data`` directory under the package's installation directory.

:meta hide-value:
"""
DEFAULT_TMP_DIR  : Path = DEFAULT_DATA_DIR.parent / 'tmp'
""":meta hide-value:"""
DEFAULT_LOGS_DIR : Path = DEFAULT_DATA_DIR / 'logs'
""":meta hide-value:"""
DOTENV_PATH      : Path = Path.cwd() / '.env'
"""Points to a ``.env`` file under the current working directory.

:meta hide-value:
"""
CONFIG_PATH      : Path = Path.cwd() / 'lydian-config.toml'
"""Points to a ``lydian-config.toml`` file under the current working directory.

:meta hide-value:
"""
PERMISSIONS_PATH : Path = Path.cwd() / 'permissions.yml'
"""Points to a ``permissions.yml`` file under the current working directory.

:meta hide-value:
"""
DATA_DIR         : Path = (CONFIG_PATH.parent / 'lydian-data') if CONFIG_PATH.exists() else DEFAULT_DATA_DIR
"""Data directory as relative to the user's configuration file if it exists, or :py:data:`DEFAULT_DATA_DIR`.

:meta hide-value:
"""
TMP_DIR          : Path = DATA_DIR / 'tmp'
""":meta hide-value:"""
LOGS_DIR         : Path = DATA_DIR / 'logs'
""":meta hide-value:"""
DL_DIR           : Path = DATA_DIR / 'dl'
""":meta hide-value:"""
"""Directory for storing media downloaded by youtube-dl.

:meta hide-value:
"""

LOG_MSG_FORMAT_UTC: str = '<level>[{time:YYYY-MM-DD HH:mm:ssZZ!UTC}] [{name}::{function}/{level}]: {message}</level>'
LOG_MSG_FORMAT: str = LOG_MSG_FORMAT_UTC.replace('!UTC', '')
LOG_FILE_FORMAT: str = '{time:YYYY-MM-DDTHHmmssZZ}.log'
LOG_FILE_PATTERN: re.Pattern[str] = re.compile(
    r'^(?P<timestamp>(?P<year>\d{4})-(?P<month>\d\d)-(?P<day>\d\d)'
    + r'T(?P<hour>\d\d)(?P<minute>\d\d)(?P<second>\d\d)(?P<tz>[+-]\d+))\.log',
    flags=re.MULTILINE,
)

EMBED_COLOR_INFO: int = 0xcccccc
EMBED_COLOR_OK: int = 0x00ff00
EMBED_COLOR_WARN: int = 0xffcc00
EMBED_COLOR_ERROR: int = 0xff0000

# Compiled regex
COLOR_ESCAPE_REGEX: re.Pattern[str] = re.compile(r'\x1b\[.*?m')
HTTP_REGEX: re.Pattern[str] = re.compile(r'^https?://')
"""Matches if a string begins with ``http://`` or ``https://``."""
DOCSTRING_PARAM_REGEX: re.Pattern[str] = re.compile(
    r'^:param (?P<name>\w+): (?P<desc>.+(?:\n    .+|\n)*)',
    flags=re.MULTILINE,
)
"""Matches ``:param ...:``-style parameter annotations in docstrings.

Named groups:
    - "name"
    - "desc"
"""
YTDL_DOWNLOAD_PROGRESS_REGEX: re.Pattern[str] = re.compile(r'\[download\].+ETA')

MD_HEADER_REGEX: re.Pattern[str] = re.compile(r'^#(?P<title>.*)$', flags=re.MULTILINE)
"""Matches a markdown header with any number of ``#`` characters.

Named groups:
    - "title": The text following the header characters, including surrounding whitespace
"""
MD_H1_REGEX: re.Pattern[str] = re.compile(r'^#(?P<title>[^#].*)$', flags=re.MULTILINE)
"""Matches level 1 markdown header.

Named groups:
    - "title": The text following the header characters, including surrounding whitespace
"""
MD_H2_REGEX: re.Pattern[str] = re.compile(r'^##(?P<title>[^#].*)$', flags=re.MULTILINE)
"""Matches a level 2 markdown header.

Named groups:
    - "title": The text following the header characters, including surrounding whitespace
"""
MD_H3_REGEX: re.Pattern[str] = re.compile(r'^###(?P<title>[^#].*)$', flags=re.MULTILINE)
"""Matches a level 3 markdown header.

Named groups:
    - "title": The text following the header characters, including surrounding whitespace
"""

# Other values
USER_AGENT: str = f'lydian-discord-bot/{__version__}'
DEFAULT_DISCORD_PROMPT_TIMEOUT: float = 60.0
DEFAULT_DISCORD_PAGINATED_VIEW_TIMEOUT: float = 60.0 * 5
EMOJI_DIGITS: tuple[str, str, str, str, str, str, str, str, str, str] = (
    emojize(':zero:', language='alias'),
    emojize(':one:', language='alias'),
    emojize(':two:', language='alias'),
    emojize(':three:', language='alias'),
    emojize(':four:', language='alias'),
    emojize(':five:', language='alias'),
    emojize(':six:', language='alias'),
    emojize(':seven:', language='alias'),
    emojize(':eight:', language='alias'),
    emojize(':nine:', language='alias'),
)
"""Digits 0-9 as emoji."""
QUEUE_MAX_PER_PAGE: int = 20

class ConsoleHighlighter(Highlighter):
    """Custom highlighter class for the ``rich`` console."""

    def highlight(self, text: Text) -> None:  # noqa: D102
        if m := re.search(fr'{str(Path.cwd()).replace('\\', '\\\\')}', str(text)):
            text.stylize('cwd', m.start(0), m.end(0))

class EmojiStr(StrEnum):
    """Strings for emoji commonly used by the bot."""

    # General
    INFO    = emojize(':information:', language='alias')
    OK      = emojize(':white_check_mark:', language='alias')
    WARN    = emojize(':warning:', language='alias')
    ERROR   = emojize(':x:', language='alias')
    CONFIRM = emojize(':heavy_check_mark:', language='alias')
    CANCEL  = emojize(':heavy_multiplication_x:', language='alias')
    GEAR    = emojize(':gear:', language='alias')

    # Media
    PLAY    = emojize(':arrow_forward:', language='alias')
    PAUSE   = emojize(':pause_button:', language='alias')
    STOP    = emojize(':stop_button:', language='alias')
    BACK    = emojize(':arrow_backward:', language='alias')
    SKIP    = emojize(':fast_forward:', language='alias')
    IN      = emojize(':inbox_tray:', language='alias')
    OUT     = emojize(':outbox_tray:', language='alias')
    SHUFFLE = emojize(':twisted_rightwards_arrows:', language='alias')
    LOOP     = emojize(':repeat:', language='alias')
    LOOP_ONE = emojize(':repeat_one:', language='alias')

    # Alphanumeric
    @classmethod
    def from_int(cls, n: int) -> str:
        """Converts an integer into digit emojis."""
        return ''.join(EMOJI_DIGITS[int(ch)] for ch in str(n).lower())

class LogLevel(IntEnum):  # noqa: D101
    TRACE   = 5
    DEBUG   = 10
    INFO    = 20
    WARNING = 30
    ERROR   = 40

def clear_tmp_dir() -> None:
    """Removes all contents of the directory defined by ``const.TMP_DIR``."""
    logger.debug(f'Clearing tmp directory contents from {TMP_DIR}')

    dirs: list[Path] = []
    delcount_f: int = 0
    for fp in TMP_DIR.rglob('*'):
        if fp.is_dir():
            dirs.append(fp)
        else:
            fp.unlink()
            delcount_f += 1

    for fp in dirs:
        fp.rmdir()

    logger.debug(f'Removed {delcount_f} files and {len(dirs)} directories')

def create_directories() -> None:
    """Creates all directories needed by the bot if they do not exist."""
    for dp in (DATA_DIR, TMP_DIR, LOGS_DIR):
        if not dp.exists():
            logger.info(f'Making directory: {dp}')
            dp.mkdir()

def _stdout_log_sink(msg: loguru.Message) -> None:
    # This is a workaround to make ``prompt_toolkit``'s ``patch_stdout`` still work as intended
    # https://github.com/Delgan/loguru/issues/1385
    sys.stdout.write(msg)

def _stdout_log_filter(record: loguru.Record) -> bool:
    return record['level'].name != 'CONSOLE'

def setup_logger(
        stdout_level: int | str = 'INFO',
        file_level: int | str = 'DEBUG',
        logs_dir: str | Path | None = DEFAULT_LOGS_DIR,
        *,
        log_in_utc: bool = False,
    ) -> 'loguru.Logger':  # noqa: UP037
    """Prepare the global ``logger`` with the given options and return a reference to it.

    All existing handlers are removed, then new ones are added based on the given arguments.

    :param stdout_level: Minimum level to use for the stdout handler.
    :param file_level: Minimum level to use for the file handler.
    :param logs_dir: Directory to save log files to. ``None`` will disable file logging.
    """
    logger.remove()

    # Standard levels
    logger.level('DEBUG', color='<cyan>')
    logger.level('INFO', color='<normal>')
    logger.level('WARNING', color='<yellow>')
    logger.level('ERROR', color='<light-red>')

    # For echoing console input to log files
    try:
        # Check if it exists, an error is raised if the no is set in that case
        _ = logger.level('CONSOLE')
    except ValueError:
        logger.level('CONSOLE', no=50, color='<normal>')

    msg_format: str = LOG_MSG_FORMAT_UTC if log_in_utc else LOG_MSG_FORMAT

    logger.add(
        _stdout_log_sink,
        level=stdout_level,
        format=msg_format,
        filter=_stdout_log_filter,
        colorize=True,
        diagnose=False,
    )
    if logs_dir:
        logger.add(
            Path(logs_dir, LOG_FILE_FORMAT),
            level=file_level,
            format=msg_format,
            diagnose=False,
            retention=10,
            delay=True,
            mode='w',
        )

    return logger

def setup_rich_console() -> Console:
    """Prepares a ``rich`` console and returns it."""
    theme = Theme({
        'info': 'cyan',
        'info2': 'bright_cyan',
        'ok': 'bright_green',
        'warn': 'yellow',
        'err': 'red',
        'dim': 'grey70',
        'path': 'magenta',
        'path2': 'bright_magenta',
        'cwd': 'grey50',
    })

    return Console(
        highlighter=ConsoleHighlighter(),
        theme=theme,
        emoji=False,
    )

screen: Console = setup_rich_console()

debug_context = benedict()
debug_store: dict[str, tuple[Any, Literal['copy', 'ref']]] = {}
