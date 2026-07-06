"""Provides tools for modifying the ``ytdl-extract-info.json`` test data."""
import json
import re
import shutil
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from benedict import benedict

from lydian.cogs.voice import ytdl
from lydian.const import TESTS_DIR, screen
from lydian.util import assure, plural

DATA_PATH: Path = TESTS_DIR / 'data/ytdl-extract-info.json'
KEY_FILTER_ALLOW: re.Pattern[str] = re.compile(r'.*')
KEY_FILTER_BLOCK: re.Pattern[str] = re.compile(fr'^({'|'.join([
    'formats',
    'thumbnails',
    'heatmap',
    'url',
    'http_headers',
])})$')  # noqa: FLY002

assure(DATA_PATH.is_file(), str(DATA_PATH))

def load(fp: str | Path = DATA_PATH) -> dict[str, Any]:
    """Loads the data from JSON."""
    with open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)

def dump(data: dict[str, Any], fp: str | Path = DATA_PATH) -> None:
    """Dumps a dictionary to the test data JSON."""
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def extract_and_filter(
        query: str,
        key_allow: str | re.Pattern[str] = KEY_FILTER_ALLOW,
        key_block: str | re.Pattern[str] = KEY_FILTER_BLOCK,
    ) -> dict[str, Any]:
    """Extracts info for a query using the provided allow and block regex to filter the resuling keys."""
    return benedict(ytdl.extract_info(query, download=False), keypath_separator='/').filter(
        lambda k, _v: bool(re.match(key_allow, cast('str', k)) and not re.match(key_block, cast('str', k))),
    )

cli = typer.Typer(no_args_is_help=True)

@cli.command('sort')
def sort_data() -> None:
    """Sorts test data alphabetically by key."""
    data = load()

    screen.print('Updating...')
    dump({k:data[k] for k in sorted(data)}, tmp := DATA_PATH.with_suffix('.new'))

    shutil.move(tmp, DATA_PATH)

    screen.print('Sorted data.')

@cli.command('store')
def store_info(
        queries: list[str],
        *,
        force: Annotated[bool, typer.Option('--force', '-f', help='Overwrite existing query data')] = False,
    ) -> None:
    """Extracts info for a query and stores it into the test data."""
    data = load()

    collected: dict[str, dict[str, Any]] = {}
    for q in queries:
        if q in collected:
            screen.print(f'Skipping duplicate query: {q}')
            continue

        if (not force) and q in data:
            screen.print(f'Data already exists for query: {q}')
            continue

        screen.print(f'Getting information for query: {q}')
        collected[q] = extract_and_filter(q)

    data.update(collected)

    screen.print('Updating...')
    dump(data, tmp := DATA_PATH.with_suffix('.new'))

    shutil.move(tmp, DATA_PATH)

    screen.print(f'Stored information for {len(collected)} {plural('quer.y.ies', len(collected))}.')

@cli.callback()
def main() -> None:  # noqa: D103
    return

if __name__ == '__main__':
    cli()
