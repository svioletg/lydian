"""Provides methods for retrieving and analyzing Lydian's GitHub releases.

All requests to GitHub's API request public information and require no token/other authorization.
"""
import re
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from itertools import takewhile
from typing import Any, ClassVar, Literal, Self

import requests
from packaging.version import Version
from requests import Response
from rich.markup import escape

from lydian import __version__
from lydian.const import GH_REPO, screen

GH_API_ROOT: str = 'https://api.github.com'
GH_REPO_API_ROOT: str = GH_API_ROOT + '/repos/svioletg/lydian'

@dataclass
class ReleaseComment:
    """Dataclass used for specially-parsed comments from GitHub release markdown."""

    _regex: ClassVar[re.Pattern[str]] = re.compile(
        r'<!-- (?P<type>summary|important|note|warning|security): (?P<content>.+?) -->',
        flags=re.DOTALL,
    )
    _markup_map: ClassVar[dict[str, str]] = {
        'important': 'purple',
        'note': 'info',
        'warning': 'warn',
        'security': 'err',
    }

    type: Literal['summary', 'important', 'note', 'warning', 'security']
    content: str

    @property
    def style(self) -> str:
        """Returns the comment's ``rich`` markup style name, defaulting to ``'normal'``."""
        return self._markup_map.get(self.type, 'normal')

    @classmethod
    def from_body(cls, body: str) -> list[Self]:
        """Returns a list of ``ReleaseComment`` instances parsed from a release body."""
        return [cls(**m.groupdict()) for m in cls._regex.finditer(body)]  # ty:ignore[invalid-argument-type]

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

    print_fn('Checking for updates...')
    print_fn('Getting release information...')

    releases = get_releases()
    newer_releases = tuple(takewhile(lambda i: Version(i['tag_name']) > current, releases))
    if not newer_releases:
        print_fn(f'[ok]No releases since v{current}; you are up to date[/].')
        return False

    latest = newer_releases[0]
    latest_date: datetime = datetime.fromisoformat(latest['published_at'])

    print_fn(f'[info]A new release is available: {latest['tag_name']}* (released {latest_date})[/]')

    if latest['prerelease']:
        print_fn('    [warn]*This is a pre-release, and may not be stable enough for general use yet.[/]')

    for comment in ReleaseComment.from_body(latest['body']):
        wrapped: str = textwrap.fill(
            comment.content,
            width=80,
            subsequent_indent=f'{' ' * (len(comment.type) + 3)}    ',
        )
        print_fn(f'    [{comment.style}]{escape(f'[{comment.type.upper()}]')} {wrapped}[/]')

    print_fn(f'[info](You are {len(newer_releases)} releases behind.)[/]')
    print_fn(f'Details: [bright_cyan]{latest['html_url']}[/]')
    print_fn(f'Update with pip: [bright_yellow]pip install git+{GH_REPO}.git[/]')

    return True

def main() -> int:
    """Checks if a release of Lydian is available with a newer version, returning 1 if so, otherwise 0."""
    screen.print(f'You are running Lydian v{__version__}.')
    return int(check_for_updates())

if __name__ == '__main__':
    sys.exit(main())
