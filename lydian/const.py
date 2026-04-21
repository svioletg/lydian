"""Constant or singleton values for use across the rest of the package."""
import re
import sys
from enum import StrEnum
from importlib.metadata import metadata
from pathlib import Path

import loguru
from emoji import emojize
from loguru import logger
from rich.console import Console
from rich.highlighter import Highlighter
from rich.text import Text
from rich.theme import Theme

PROJECT_VERSION: str = metadata('lydian-discord-bot')['version']

# Paths
PACKAGE_DIR      : Path = Path(__file__).resolve().parent
TESTS_DIR        : Path = PACKAGE_DIR.parent / 'tests'
DEFAULT_DATA_DIR : Path = PACKAGE_DIR / 'lydian-data'
DEFAULT_TMP_DIR  : Path = DEFAULT_DATA_DIR.parent / 'tmp'
DEFAULT_LOGS_DIR : Path = DEFAULT_DATA_DIR / 'logs'
CONFIG_PATH      : Path = Path.cwd() / 'lydian-config.toml'
"""Points to a ``lydian-config.toml`` file under the current working directory.

:meta hide-value:
"""
DATA_DIR         : Path = (CONFIG_PATH.parent / 'lydian-data') if CONFIG_PATH.parent.exists() else DEFAULT_DATA_DIR
TMP_DIR          : Path = DATA_DIR / 'tmp'
LOGS_DIR         : Path = DATA_DIR / 'logs'
TOKEN_PATH       : Path = CONFIG_PATH.parent / 'token.txt'

LOG_MSG_FORMAT_UTC: str = '<level>[{time:YYYY-MM-DD HH:mm:ss!UTC} {module}/{level}] {message}</level>'
LOG_MSG_FORMAT: str = LOG_MSG_FORMAT_UTC.replace('!UTC', '')
LOG_FILE_FORMAT: str = '{time:YYYY-MM-DDTHHmmssZZ}.log'
LOG_FILE_PATTERN: re.Pattern[str] = re.compile(
    r'^(?P<timestamp>(?P<year>\d{4})-(?P<month>\d\d)-(?P<day>\d\d)'
    + r'T(?P<hour>\d\d)(?P<minute>\d\d)(?P<second>\d\d)(?P<tz>[+-]\d+))\.log',
    flags=re.MULTILINE,
)

COLOR_INFO: int = 0x00aaff
COLOR_OK: int = 0x00ff00
COLOR_WARN: int = 0xffcc00
COLOR_ERROR: int = 0xff0000

class ConsoleHighlighter(Highlighter):
    """Custom highlighter class for the ``rich`` console."""

    def highlight(self, text: Text) -> None:  # noqa: D102
        if m := re.search(fr'{Path.cwd()}', str(text)):
            text.stylize('cwd', m.start(0), m.end(0))

class EmojiStr(StrEnum):
    """Strings for emoji commonly used by the bot."""

    INFO = emojize(':information:', language='alias')
    OK = emojize(':white_check_mark:', language='alias')
    WARN = emojize(':warning:', language='alias')
    ERROR = emojize(':x:', language='alias')

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

def setup_logger(
        stdout_level: str = 'INFO',
        file_level: str = 'DEBUG',
        logs_dir: Path = DEFAULT_LOGS_DIR,
        *,
        log_in_utc: bool = False,
    ) -> 'loguru.Logger':  # noqa: UP037
    """Prepare the global ``logger`` with the given options and return a reference to it.

    All existing handlers are removed, then new ones are added based on the given arguments.

    :param stdout_level: Minimum level to use for the stdout handler.
    :param file_level: Minimum level to use for the file handler.
    :param logs_dir: Directory to save log files to.
    """
    logger.remove()

    logger.level('DEBUG', color='<cyan>')
    logger.level('INFO', color='<normal>')
    logger.level('WARNING', color='<yellow>')
    logger.level('ERROR', color='<red>')

    msg_format: str = LOG_MSG_FORMAT_UTC if log_in_utc else LOG_MSG_FORMAT

    logger.add(sys.stdout, level=stdout_level, format=msg_format, diagnose=False)
    logger.add(
        logs_dir / LOG_FILE_FORMAT,
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
    )

console: Console = setup_rich_console()

DEFAULT_DATA_DIR.mkdir(exist_ok=True)
