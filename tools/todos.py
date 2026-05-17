"""Checks for TODO comments in all ``*.py`` files in a directory."""
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass, field
from pathlib import Path

from lydian.const import screen
from lydian.util import pos_to_linepos

PROJECT_DIR: Path = Path('lydian').absolute()
TODO_REGEX: re.Pattern[str] = re.compile(
    r'^ *(?P<header># TODO\((?P<author>.+?)\):.*)$(?:\n\s*#.*$)*',
    flags=re.MULTILINE,
)
ISSUE_REGEX: re.Pattern[str] = re.compile(
    r'\bhttps://github.com/(?P<user>[\w-]+)/(?P<repo>[\w-]+)/issues/(?P<n>\d+)\b',
    flags=re.MULTILINE,
)
DEFAULT_ISSUE_LINK_TMPL: str = 'https://github.com/svioletg/lydian-discord-bot/issues/{}'

@dataclass
class Todo:  # noqa: D101
    header: str
    """The first line of this TODO."""
    file: Path
    span: tuple[int, int]
    """The start and end index of file content this TODO covers."""
    author: str | None = None
    issues: list[str] = field(default_factory=list)
    """URLs to any referenced issues in the TODO."""

    def content(self) -> str:
        """Returns the full content of this TODO.

        This method will re-read the content from ``file`` when called.
        The returned content will include the leading ``#`` on each line, but surrounding whitespace is stripped.
        """
        return '\n'.join(ln.strip() for ln in self.file.read_text('utf-8')[self.span[0]:self.span[1] + 1].splitlines())

def find_todos(source_dir: str | Path, *, recursive: bool = False) -> list[Todo]:
    """Searches all ``*.py`` files in a directory for ``# TODO`` lines, returning a list of ``Todo`` objects."""
    source_dir = Path(source_dir)

    todos: list[Todo] = []
    for fp in (source_dir.rglob if recursive else source_dir.glob)('*.py'):
        ftext: str = fp.read_text('utf-8')
        for m in TODO_REGEX.finditer(ftext):
            header: str = m.group('header')
            author: str | None = m.group('author')
            span = m.span()
            span = (span[0] + len(m.group(0).split('#')[0]), span[1])
            todos.append(Todo(
                header,
                fp,
                span,
                author=author,
                issues=[im.group(0) for im in ISSUE_REGEX.finditer(m.group(0))] \
                    + [DEFAULT_ISSUE_LINK_TMPL.format(s.lstrip('0')) for s in re.findall(r'#(\d+)', m.group(0))],
            ))
    return todos

def main() -> int:  # noqa: D103
    parser = ArgumentParser()
    parser.add_argument('source_dir', type=Path, metavar='dir')
    parser.add_argument('--recursive', '-r', action='store_true')
    parser.add_argument('--author', type=str, help='Only prints TODOs from this author.')
    parser.add_argument('--no-author', action='store_true',
        help='Only prints TODOs with no author. Overrides --author.')

    args = parser.parse_args()
    source_dir: Path = args.source_dir
    recursive: bool = args.recursive
    author: str | None = args.author
    no_author: bool = args.no_author

    def _filter(todo: Todo) -> bool:
        if no_author and todo.author:
            return False
        if author and (todo.author != author):  # noqa: SIM103
            return False
        return True

    todos: list[Todo] = [t for t in find_todos(source_dir, recursive=recursive) if _filter(t)]

    if todos:
        for todo in todos:
            linepos: tuple[int, int] = pos_to_linepos(todo.file.read_text('utf-8'), todo.span[0])
            screen.print(f'TODO in [bold]{todo.file}:{linepos[0] + 1}:{linepos[1] + 1}[/]: [cyan]{todo.content()}[/]')
        screen.print(f'Found {len(todos)} TODOs.')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
