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

from lydian import __version__
from lydian.config import config
from lydian.const import GH_REPO, screen
from lydian.util import wrap_paragraphs

GH_API_ROOT: str = 'https://api.github.com'
GH_REPO_API_ROOT: str = GH_API_ROOT + '/repos/svioletg/lydian'

@dataclass(frozen=True)
class ReleaseComment:
    """Dataclass used for specially-parsed comments from GitHub release markdown."""

    _regex: ClassVar[re.Pattern[str]] = re.compile(
        r'<!-- (?P<type>summary|important|note|warning|security):\s*(?P<content>.+?)\s*-->',
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

    def block(self, *, width: int = 80, label: Literal['inline', 'block', 'auto'] = 'auto') -> str:
        r"""Returns the comment content wrapped and marked up for printing.

        :param width: How many columns to wrap the text at.
        :param label: How the label (e.g. ``[SUMMARY]``) should be formatted. ``'inline'`` puts the label directly
            before the content with a single space following it (``[SUMMARY] Text content...``). ``'block'`` places a
            newline between the label and content (``[SUMMARY]\nText content...``). ``'auto'`` will use the ``'inline'``
            style if it can fit in one line (dictated by ``width``), otherwise the ``'block'`` style is used; if the
            content has any newlines in it already, ``'block'`` is used.
        """
        text: str = f'[{self.type.upper()}]\n{self.content}'

        indent: str

        if label == 'auto':
            label = 'block' if ('\n' in self.content) or (len(text) > width) else 'inline'

        match label:
            case 'inline':
                text = text.replace('\n', ' ', count=1)
                indent = f'{' ' * (len(self.type) + 3)}'
            case 'block':
                indent = ''
            case _:
                raise ValueError(f"argument label expected one of 'inline', 'block', 'auto': {label!r}")

        wrapped: str = '\n'.join(wrap_paragraphs(
            text,
            width=width,
            subsequent_indent=indent, # +3 for the two square brackets and a space
            indent_mode='single',
        ))

        return f'[{self.style}]{wrapped}[/]'

def get_releases(*, timeout: float = 10) -> list[dict[str, Any]]:
    """Returns a list of Lydian's GitHub releases.

    :param timeout: The timeout in seconds for the GitHub API request.

    :raises requests.exceptions.ConnectTimeout:
        The GitHub API request timed out.
    :raises requests.exceptions.HTTPError:
        The GitHub API request returned a non-200 status.
    """
    response: Response = requests.get(GH_REPO_API_ROOT + '/releases', timeout=timeout)
    response.raise_for_status()

    return response.json()

def check_for_updates(
        current: str | Version | None = None,
        *,
        stable: bool = False,
        output: bool = True,
        timeout: float = 10,
    ) -> bool:
    """Checks for releases with versions newer than ``current``, returning ``True`` if they exist.

    :param current: The "current" version to compare against. This parameter is available for testing purposes, but in
        normal operation should always be left as ``None``, in which case :py:data:`lydian.__version__` is used.
    :param stable: Whether to exclude pre-releases from the check.
    :param output: Whether to print out messages regarding the version status.
    :param timeout: The timeout in seconds for the GitHub API request.

    :raises requests.exceptions.ConnectTimeout:
        The GitHub API request timed out.
    :raises requests.exceptions.HTTPError:
        The GitHub API request returned a non-200 status.
    """
    if current is None:
        current = Version(__version__)
    if isinstance(current, str):
        current = Version(current)

    print_fn = screen.print if output else lambda _: None

    print_fn('Checking for updates...')
    print_fn('Getting release information...')

    releases = get_releases(timeout=timeout)
    newer_releases = takewhile(lambda r: Version(r['tag_name']) > current, releases)
    if stable:
        newer_releases = filter(lambda r: not r['prerelease'], newer_releases)
    newer_releases = tuple(newer_releases)

    if not newer_releases:
        print_fn(f'[ok]No {'stable ' if stable else ''}releases since v{current}; you are up to date.[/]')
        return False

    latest = newer_releases[0]
    latest_date: datetime = datetime.fromisoformat(latest['published_at'])

    tag_str: str = latest['tag_name'] + ('*' if latest['prerelease'] else '')

    print_fn(f'[info]A new release is available: {tag_str} (released {latest_date})[/]')

    if latest['prerelease']:
        print_fn('    [warn]*This is a pre-release; it may be unstable or have unexpected bugs.[/]')

    for comment in ReleaseComment.from_body(latest['body']):
        print_fn(textwrap.indent(comment.block(label='inline'), '    '))

    release_timeline_str: str = ', '.join([
        f'[ok](latest) {latest['tag_name']}[/][dim]',
        *(r['tag_name'] for r in newer_releases[1:]),
    ])

    print_fn(f'[info](You are {len(newer_releases)} release(s) behind: {release_timeline_str}[/])[/]')
    print_fn(f'Details: [bright_cyan]{latest['html_url']}[/]')
    print_fn(f'Update with pip: [bright_yellow]pip install git+{GH_REPO}.git[/]')

    return True

def main() -> int:
    """Checks if a release of Lydian is available with a newer version, returning 1 if so, otherwise 0."""
    screen.print(f'You are running Lydian v{__version__}.')
    return int(check_for_updates(stable=config.check_for_stable_only))

if __name__ == '__main__':
    sys.exit(main())
