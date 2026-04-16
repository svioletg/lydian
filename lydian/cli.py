"""Command-line tools for managing Lydian."""
import typer

from lydian.config import config
from lydian.const import setup_logger

cli = typer.Typer(no_args_is_help=True)

@cli.callback()
def main() -> None:  # noqa: D103
    setup_logger(config.logging.log_level)

if __name__ == '__main__':
    cli()
