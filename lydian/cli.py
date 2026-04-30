"""Command-line tools for managing Lydian."""
import typer

from lydian.config import config
from lydian.const import LOG_FILE_PATTERN, LOGS_DIR, console, setup_logger

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

@cli.callback()
def main() -> None:  # noqa: D103
    setup_logger(config.logging.log_level)

if __name__ == '__main__':
    cli()
