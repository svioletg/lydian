"""Command-line tools for managing Lydian."""
import shutil
from typing import Never

import typer
from humanize import naturalsize
from rich.prompt import Confirm

from lydian.config import config
from lydian.const import DL_DIR, LOG_FILE_PATTERN, LOGS_DIR, console, setup_logger
from lydian.util import dirsize_counted


def abort(msg: str, code: int = 1) -> Never:
    """Prints ``msg`` and raises ``SystemExit`` with the given exit code."""
    console.print(msg)
    raise SystemExit(code)

cligroup_logs = typer.Typer(no_args_is_help=True)

@cligroup_logs.command('latest')
def logs_latest() -> None:
    """Returns the file path to the most recently modified log file."""
    console.print(max(
        (fp for fp in LOGS_DIR.glob('*.log') if LOG_FILE_PATTERN.match(fp.name)),
        key=lambda fp: fp.stat().st_mtime,
    ))

cli = typer.Typer(no_args_is_help=True)
cli.add_typer(cligroup_logs, name='logs')

@cli.command('clear-dl')
def clear_dl_dir() -> None:
    """Deletes all contents of the downloaded media directory."""
    dir_bytes, count = dirsize_counted(DL_DIR)
    if dir_bytes == 0:
        console.print('Directory is empty, nothing to remove.')
        return

    console.print(f'Media directory: {DL_DIR}\nSize: {naturalsize(dir_bytes)} ({count['file']} files)')
    if not Confirm.ask('Clear the directory?'):
        return
    shutil.rmtree(DL_DIR)
    DL_DIR.mkdir()
    console.print('Media directory cleared.')

@cli.callback()
def main() -> None:  # noqa: D103
    setup_logger(config.logging.log_level)

if __name__ == '__main__':
    cli()
