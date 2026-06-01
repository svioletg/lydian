"""Provides methods for retrieving and analyzing Lydian's GitHub releases.

All requests to GitHub's API request public information and require no token/other authorization.
"""
import sys
from datetime import datetime
from itertools import takewhile
from typing import Any

import requests
from packaging.version import Version
from requests import Response

from lydian import __version__
from lydian.const import GH_REPO, screen

GH_API_ROOT: str = 'https://api.github.com'
GH_REPO_API_ROOT: str = GH_API_ROOT + '/repos/svioletg/lydian'

def get_releases() -> list[dict[str, Any]]:
    """Returns a list of Lydian's GitHub releases."""
    response: Response = requests.get(GH_REPO_API_ROOT + '/releases', timeout=10)
    response.raise_for_status()

    return response.json()

def check_for_updates(current: str | Version | None = None, *, output: bool = True) -> bool:
    """Checks for releases with versions newer than ``current``, returning ``True`` if they exist.

    :param current: The "current" version to compare against. This parameter is available for testing purposes, but in
        normal operation should always be left as ``None``, in which case :py:data:`lydian.__version__` is used.
    :param output: Whether to print out messages regarding the version status.
    """
    if current is None:
        current = Version(__version__)
    if isinstance(current, str):
        current = Version(current)

    print_fn = screen.print if output else lambda _: None

    print_fn('Getting release information...')
    releases = get_releases()
    newer_releases = tuple(takewhile(lambda i: Version(i['tag_name']) > current, releases))
    if not newer_releases:
        print_fn(f'No releases since v{current}; you are [ok]up to date[/].')
        return False

    latest = newer_releases[0]
    latest_date: datetime = datetime.fromisoformat(latest['published_at'])

    print_fn(f'[warn]A new release is available: {latest['tag_name']} (released {latest_date})[/]')
    print_fn(f'[warn](You are {len(newer_releases)} releases behind.)[/]')
    print_fn(f'Update with pip: [bright_yellow]pip install git+{GH_REPO}.git[/]')

    return True

def main() -> int:
    """Checks if a release of Lydian is available with a newer version, returning 1 if so, otherwise 0."""
    screen.print(f'You are running Lydian v{__version__}.')
    return int(check_for_updates())

if __name__ == '__main__':
    sys.exit(main())
