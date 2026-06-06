from pathlib import Path

from lydian.const import GH_ISSUES
from tools.todos import Todo

SAMPLE_CONTENT: str = """
# TODO(a): #2
# Add multiplication and division functions.

def add(a: int, b: int) -> int:
    # TODO(a): Support float types
    return a + b

def sub(a: int, b: int) -> int:
    return a - b

# TODO: This TODO doesn't have an author...
"""

def test_parse_todos() -> None:
    parsed = Todo.parse_todos(SAMPLE_CONTENT)

    issue_and_author, only_author, no_author = parsed

    assert len(issue_and_author.issues) == 1
    assert issue_and_author.issues[0] == GH_ISSUES + '/2'
    assert issue_and_author.author == 'a'
    assert issue_and_author.header == '# TODO(a): #2'
    assert issue_and_author.content == '# TODO(a): #2\n# Add multiplication and division functions.'

    assert not only_author.issues
    assert only_author.author == 'a'
    assert only_author.header == only_author.content == '# TODO(a): Support float types'

    assert not no_author.issues
    assert no_author.author is None
    assert no_author.header == no_author.content == "# TODO: This TODO doesn't have an author..."

def test_todo_with_file() -> None:
    todo = Todo('# TODO: Fix later', (0, 17))
    assert todo.file is None
    assert todo.with_file(Path()) is todo
    assert todo.file == Path()
