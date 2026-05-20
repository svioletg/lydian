from typing import Annotated
from unittest.mock import AsyncMock

import pytest
from maybetype import Err, Ok

from lydian.console import Arg, BotConsole, ConsoleCommand, command
from lydian.const import screen, setup_logger


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

    @command()
    def var_positional(self, a: str, b: int, /, *c: str) -> None:
        joined: str = ' '.join(c)
        screen.print(f'a={a!r}, b={b!r}, c={joined!r}')

    @command()
    def only_var_pos(self, /, *xs: str) -> None:
        screen.print(' '.join(xs))

    @command()
    def only_var_pos_optional(self, /, *xs: Annotated[str, Arg(default=('a'))]) -> None:
        screen.print(' '.join(xs))

    @command()
    def flag_false_default(self, /, *, flag: bool = False) -> None:
        screen.print(flag)

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
    assert console.noargs.cli_signature == 'noargs'
    assert console.echo.cli_signature == 'echo <text>'
    assert console.repeat.cli_signature == 'repeat <text> [n]'
    assert console.add.cli_signature == 'math add <a> <b>'
    assert console.sign.cli_signature == 'math sign <n> [--no-keep-zero]'
    assert console.testparsing.cli_signature == 'testparsing <nums>'
    assert console.var_positional.cli_signature == 'var_positional <a> <b> <c...>'
    assert console.only_var_pos.cli_signature == 'only_var_pos <xs...>'
    assert console.only_var_pos_optional.cli_signature == 'only_var_pos_optional [xs...]'

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

    assert console.repeat.parse_raw_args('text') == Ok((['text', 1], {}))
    assert console.repeat.parse_raw_args('text', '2') == Ok((['text', 2], {}))

    assert console.add.parse_raw_args('1', '2') == Ok(([1, 2], {}))
    assert console.add.parse_raw_args('a', 'b') == \
        Err("Failed to parse value for argument 'a': ValueError: invalid literal for int() with base 10: 'a'")

    assert console.sign.parse_raw_args('1', '--no-keep-zero') == Ok(([1], {'keep_zero': False}))

    assert console.testparsing.parse_raw_args('1,2,3') == Ok(([[1, 2, 3]], {}))

    assert console.var_positional.parse_raw_args('a', '2', 'c', 'd', 'e', 'f') \
        == Ok((['a', 2, 'c', 'd', 'e', 'f'], {}))

    assert console.only_var_pos.parse_raw_args('a', 'b', 'c') == Ok((['a', 'b', 'c'], {}))

    assert console.only_var_pos_optional.parse_raw_args() == Ok((['a'], {}))
    assert console.only_var_pos_optional.parse_raw_args('a', 'b', 'c') == Ok((['a', 'b', 'c'], {}))

    assert console.flag_false_default.parse_raw_args() == Ok(([], {}))
    assert console.flag_false_default.parse_raw_args('--flag') == Ok(([], {'flag': True}))

def test_invoke(console: Console, capsys: pytest.CaptureFixture) -> None:
    setup_logger('DEBUG')

    console.noargs.invoke()
    assert capsys.readouterr().out == ''

    console.echo.invoke('text')
    assert capsys.readouterr().out == 'text\n'

    console.repeat.invoke('text', '2')
    assert capsys.readouterr().out == 'texttext\n'

    console.add.invoke('1', '2')
    assert capsys.readouterr().out == 'Result: 3\n'

    console.sign.invoke('1')
    assert capsys.readouterr().out == '1\n'
    console.sign.invoke('0')
    assert capsys.readouterr().out == '0\n'
    console.sign.invoke('0', '--no-keep-zero')
    assert capsys.readouterr().out == '1\n'
    console.sign.invoke('-1')
    assert capsys.readouterr().out == '-1\n'

    console.testparsing.invoke('1,2,3')
    assert capsys.readouterr().out == '[1, 2, 3]\n'

    console.var_positional.invoke('a', '2', 'c', 'd', 'e', 'f')
    assert capsys.readouterr().out == "a='a', b=2, c='c d e f'\n"

    console.only_var_pos.invoke('a', 'b', 'c')
    assert capsys.readouterr().out == 'a b c\n'

    console.only_var_pos_optional.invoke()
    assert capsys.readouterr().out == 'a\n'
    console.only_var_pos_optional.invoke('a', 'b', 'c')
    assert capsys.readouterr().out == 'a b c\n'
