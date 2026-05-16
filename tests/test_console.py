from typing import Annotated
from unittest.mock import AsyncMock

import pytest
from maybetype import Err, Ok

from lydian.console import Arg, BotConsole, ConsoleCommand, command
from lydian.const import console as screen


class Console(BotConsole):  # noqa: D101
    def __init__(self) -> None:
        self.bot = AsyncMock()

    @command()
    def noargs(self, /) -> None:
        pass

    @command()
    def echo(self, text: str, /) -> None:
        screen.print(text)

    @command()
    def repeat(self, text: str, n: int = 1, /) -> None:
        screen.print(text * n)

    @command(group='math')
    def add(self, a: int, b: int, /) -> None:
        screen.print(f'Result: {a + b}')

    @command(group='math')
    def sign(self, n: int, /, *, keep_zero: bool = True) -> None:
        if keep_zero and (n == 0):
            screen.print('0')
        else:
            screen.print(f'{1 if n >= 0 else -1}')

    @command()
    def testparsing(self, nums: Annotated[list[int], Arg(parse=lambda s: [int(i) for i in s.split(',')])], /) -> None:
        screen.print(nums)

@pytest.fixture
def console() -> Console:
    return Console()

def test_init_base_fail() -> None:
    with pytest.raises(NotImplementedError):
        BotConsole()

def test_command_validate() -> None:
    def valid_a(a: int, /) -> None:
        screen.print(a)

    def valid_b(a: int, /, *, b: str = '') -> None:
        screen.print(a, b)

    def invalid_a(a: int) -> None:
        screen.print(a)

    def invalid_b(a: int, b: str = '') -> None:
        screen.print(a, b)

    def invalid_c(a: int, /, b: str = '') -> None:
        screen.print(a, b)

    assert ConsoleCommand.validate(valid_a) is valid_a
    assert ConsoleCommand.validate(valid_b) is valid_b

    with pytest.raises(TypeError):
        assert not ConsoleCommand.validate(invalid_a)

    with pytest.raises(TypeError):
        assert not ConsoleCommand.validate(invalid_b)

    with pytest.raises(TypeError):
        assert not ConsoleCommand.validate(invalid_c)

def test_command_signature(console: Console) -> None:
    assert console.noargs.signature == 'noargs'
    assert console.echo.signature == 'echo <text>'
    assert console.repeat.signature == 'repeat <text> [n]'
    assert console.add.signature == 'math add <a> <b>'
    assert console.sign.signature == 'math sign <n> [--no-keep_zero]'

@pytest.mark.parametrize(('s', 'expected'),
    [
        ('asdf', 'Unrecognized command: asdf'),
        ('asdf zcxv', 'Unrecognized command: asdf'),
        ('noargs', ('noargs', [])),
        ('echo word', ('echo', ['word'])),
        ('repeat word', ('repeat', ['word'])),
        ('repeat word 2', ('repeat', ['word', '2'])),
        ('add 1 2', 'Unrecognized command: add'),
        ('math add 1 2', ('add', ['1', '2'])),
    ],
)
def test_parse_input(console: Console, s: str, expected: tuple[str, list[str]] | str) -> None:
    match console.parse_input(s):
        case Ok((command, args)):
            assert (command.name, args) == expected
        case Err(message):
            assert message == expected

def test_parse_raw_args(console: Console) -> None:
    assert console.noargs.parse_raw_args() == Ok(([], {}))
    assert console.noargs.parse_raw_args('a') == Err("Unexpected additional argument: 'a'")

    assert console.echo.parse_raw_args() == Err('Missing required positional argument(s): text')
    assert console.echo.parse_raw_args('echo') == Ok((['echo'], {}))
    assert console.echo.parse_raw_args('echo', '--repeat=2') == Err('Unexpected keyword argument: --repeat=2')

    assert console.add.parse_raw_args('1', '2') == Ok(([1, 2], {}))

    assert console.testparsing.parse_raw_args('1,2,3') == Ok(([[1, 2, 3]], {}))
