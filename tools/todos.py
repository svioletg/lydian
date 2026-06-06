"""Checks for TODO comments in all ``*.py`` files in a directory."""
import itertools
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from textwrap import dedent
from typing import Self

from lydian.const import GH_ISSUES, screen
from lydian.util import expect, pos_to_linepos

PROJECT_DIR: Path = Path('lydian').absolute()
TODO_REGEX: re.Pattern[str] = re.compile(
    r'^ *(?P<header># TODO(?:\((?P<author>.+?)\))?:.*)$(?:\n *#.*$)*',
    flags=re.MULTILINE,
)
ISSUE_REGEX: re.Pattern[str] = re.compile(
    r'\bhttps://github.com/(?P<user>[\w-]+)/(?P<repo>[\w-]+)/issues/(?P<n>\d+)\b',
    flags=re.MULTILINE,
)
DEFAULT_ISSUE_LINK_TMPL: str = GH_ISSUES + '/{}'

@dataclass
class Todo:  # noqa: D101
    content: str
    span: tuple[int, int]
    """The start and end index of the original string content this TODO covers."""
    file: Path | None = None
    author: str | None = None
    issues: list[str] = field(default_factory=list)
    """URLs to any referenced issues in the TODO."""

    def __post_init__(self) -> None:  # noqa: D105
        self.content = dedent(self.content)

    @cached_property
    def header(self) -> str:
        """The first line of ``content``."""
        return self.content.split('\n', maxsplit=1)[0]

    @classmethod
    def parse_todos(cls, content: str) -> list[Self]:
        """Parses ``Todo`` objects from ``content``."""
        todos: list[Self] = []
        for m in TODO_REGEX.finditer(content):
            author: str | None = m.group('author')
            span = m.span()
            span = (span[0] + len(m.group(0).split('#')[0]), span[1])
            todos.append(cls(
                m.group(0),
                span,
                author=author,
                issues=[im.group(0) for im in ISSUE_REGEX.finditer(m.group(0))] \
                    + [DEFAULT_ISSUE_LINK_TMPL.format(s.lstrip('0')) for s in re.findall(r'#(\d+)', m.group(0))],
            ))

        return todos

    def with_file(self, file: Path) -> Self:
        """Sets this instance's ``file`` attribute and returns the instance."""
        self.file = file

        return self

def find_todos(*paths: str | Path, recursive: bool = False) -> list[Todo]:
    """Searches all ``*.py`` files in the given directories for TODO lines, returning a list of ``Todo`` objects."""
    todos: list[Todo] = []
    for fp in itertools.chain(*(Path(dp).rglob('*.py') if recursive else Path(dp).glob('*.py') for dp in paths)):
        content: str = fp.read_text('utf-8')
        todos.extend(todo.with_file(fp) for todo in Todo.parse_todos(content))

    return todos

def main() -> int:  # noqa: D103
    parser = ArgumentParser()
    parser.add_argument('source_dirs', type=Path, metavar='dirs', nargs='+')
    parser.add_argument('--recursive', '-r', action='store_true')
    parser.add_argument('--author', type=str, help='Only prints TODOs from this author.')
    parser.add_argument('--no-author', action='store_true',
        help='Only prints TODOs with no author. Overrides --author.')

    args = parser.parse_args()
    source_dirs: list[Path] = args.source_dirs
    recursive: bool = args.recursive
    author: str | None = args.author
    no_author: bool = args.no_author

    def _filter(todo: Todo) -> bool:
        if no_author and todo.author:
            return False
        if author and (todo.author != author):  # noqa: SIM103
            return False
        return True

    todos: list[Todo] = [t for t in find_todos(*source_dirs, recursive=recursive) if _filter(t)]

    if todos:
        for todo in todos:
            linepos: tuple[int, int] = pos_to_linepos(expect(todo.file).read_text('utf-8'), todo.span[0])
            screen.print(f'TODO in [bold]{todo.file}:{linepos[0] + 1}:{linepos[1] + 1}[/]: [cyan]{todo.content}[/]')
        screen.print(f'Found {len(todos)} TODOs.')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
