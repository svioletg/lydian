"""Holds the :py:class:`BotConsole` class to handle console command while running the bot."""
import inspect
import shlex
from collections.abc import Callable
from datetime import UTC, datetime
from itertools import zip_longest
from typing import TYPE_CHECKING, Annotated, Any, Protocol, Self, Union, cast, get_args, get_origin
from unittest.mock import AsyncMock

from benedict import benedict
from discord.ext import commands
from humanize import precisedelta
from loguru import logger
from maybetype import Err, Ok, Result
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from lydian.config import config
from lydian.const import console, debug_context
from lydian.perms import perms
from lydian.util import is_annotated, join_trailing, wrap_paragraphs

if TYPE_CHECKING:
    from ty_extensions import Intersection

    from lydian.cogs.voice import VoiceCog

class Named(Protocol):
    """Protocol for types which have a ``__name__`` string attribute."""

    __name__: str

class Arg:
    """Customizes a positional argument to a :py:class:`ConsoleCommand` function."""

    def __init__(self, name: str | None = None, *, doc: str = '', parse: Callable[[str], Any] | None = None) -> None:
        """Initializes a new ``Arg``.

        :param doc: A string of help text to describe this argument.
        :param parse: A function to convert this argument value from the raw string given to the desired type.
            If ``None``, the parameter's type annotation will be called with the argument string.
        """
        self.name = name
        self.doc = doc
        self.parse = parse

class ConsoleCommand:
    """A wrapper object for functions meant as :py:class:`BotConsole` commands.

    Calling a ``ConsoleCommand`` instance will call the wrapped function after parsing the arguments using the present
    annotations, if any.
    """

    def __init__(self,
            func: Callable[..., None],
            name: str | None = None,
            *,
            group: str | tuple[str, ...] = (),
            doc: str | None = None,
            console: BotConsole | None = None,
        ) -> None:
        """Initializes a new ``ConsoleCommand``.

        :param func: The function to wrap as a command.
        :param name: A name to give this command, defaulting to the function's name minus any group prefix.
        :param group: A single group or tuple of nested group names to put this command under.
        :param doc: A string to use to describe this command for the ``help`` command. Will use ``func``'s docstring if
            not given.
        :param console: The :py:class:`BotConsole` object this command belongs to. ``None`` by default; set
            automatically if registered to a console.
        """
        self.func = cast('Intersection[Callable[..., None], Named]', self.validate(func))
        self.group = group if isinstance(group, tuple) else (group,)
        self.name = name or (
            self.func.__name__ if not self.group else
            self.func.__name__.removeprefix('_'.join(self.group) + '_')
        )
        self.doc: str | None = doc or func.__doc__
        self.console = console

        self.func_sig: inspect.Signature = inspect.signature(func)

    def __repr__(self) -> str:  # noqa: D105
        return f'ConsoleCommand[{self.func.__name__}{str(self.func_sig).removesuffix(' -> None')}]' \
            + f'(name={self.name!r}, group={self.group!r})'

    def __call__(self, *args: object, **kwargs: object) -> None:
        """Calls the wrapped function. Use :py:meth:`invoke` when calling the command with user input."""
        self.func(*args, **kwargs)

    @staticmethod
    def validate(func: Callable[..., None]) -> Callable[..., None]:
        """Validates that ``func`` can be used as a command function, returning the function or raising an error.

        :raises TypeError:
            Command function parameters must be either positional-only or keyword-only.
        """
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD:
                # Only allow functions will positional-only and keyword-only parameters
                #
                # This helps ease work later and there generally isn't a use for
                # positional-or-keyword parameters in a command context
                raise TypeError('Command function parameters must be positional-only or keyword-only:'
                    + f' {param!r} in {func}')

        return func

    # TODO(svioletg): Add method to create CLI-style command signature from function signature
    # https://github.com/svioletg/lydian-discord-bot/issues/2
    @property
    def signature(self) -> str:
        """A CLI-style command signature created from the wrapped function's signature."""
        qualified_name: str = join_trailing(self.group, ' ', trail_single=True) + self.name
        parts: list[str] = []
        for param in self.func_sig.parameters.values():
            if param.name == 'self':
                continue
            name: str = param.name
            if param.default is inspect.Parameter.empty:
                # Required parameter
                name = f'<{name}>'
            elif param.annotation is bool:
                # Flag parameter
                name = f'[--{name}]' if param.default is False else f'[--no-{name}]'
            else:
                # Optional parameter
                name = f'[{name if param.kind is inspect.Parameter.POSITIONAL_ONLY else f'--{name}=...'}]'
            parts.append(name)

        return f'{qualified_name} {' '.join(parts)}'.strip()

    @property
    def help(self) -> str:
        """Returns the string printed when using the ``help`` command on this command (or showing all)."""
        return f'{self.signature}\n' + '\n'.join(wrap_paragraphs(
            self.doc or '(no description)',
            80,
            initial_indent='    ',
            subsequent_indent='    ',
        ))

    def parse_raw_args(self, *raw_args: str) -> Result[tuple[list[Any], dict[str, Any]], str]:  # noqa: C901
        """Parses raw string argument values into values ready to call the wrapped function with.

        If parsing was successful, returns ``Ok`` of a tuple of the parsed positional argument values, and a dictionary
        of parsed keyword arguments. If parsing failed because of user input error, returns ``Err`` with an error
        message. If parsing failed because of invalid command function defintions or otherwise an error outside the
        user's control, ``ValueError`` or ``TypeError`` may be raised.
        """
        positional: dict[str, inspect.Parameter] = {}
        keyword: dict[str, inspect.Parameter] = {}

        for param in self.func_sig.parameters.values():
            if param.name == 'self':
                continue
            (positional if param.kind is inspect.Parameter.POSITIONAL_ONLY else keyword)[param.name] = param

        args: list[str] = []
        kwargs: list[str] = []

        for s in raw_args:
            if s.startswith('--'):
                kwargs.append(s.removeprefix('--'))
            else:
                args.append(s)

        parsed_args: list[Any] = []
        parsed_kwargs: dict[str, Any] = {}

        for n, (value, param) in enumerate(zip_longest(args, positional.values(), fillvalue=None)):
            if param is None:
                return Err(f'Unexpected additional argument: {value!r}')
            if value is None:
                if param.default is inspect.Parameter.empty:
                    return Err('Missing required positional argument(s):'
                        + f' {', '.join(p.name for p in list(positional.values())[n:])}')
                parsed_args.append(param.default)
                continue
            argtype: type = param.annotation
            if get_origin(param.annotation) is Union:
                t_args = get_args(param.annotation)
                if len(t_args) != 2:  # noqa: PLR2004
                    raise ValueError(f'Expected only two type arguments for union in {param} of {self.func}:'
                        + f' {t_args!r}')
                if t_args[1] is not None:
                    raise TypeError(f'Command function parameter unions can only be T | None: {param}')
                argtype = t_args[0]
            arginfo: Arg | None = get_args(param.annotation)[1] if is_annotated(param.annotation) else None
            parser: Callable[[str], Any] = (arginfo and arginfo.parse) or argtype  # ty:ignore[invalid-assignment]
            parsed_args.append(parser(value))

        for kwarg in kwargs:
            split: list[str] = kwarg.split('=', maxsplit=1)
            name: str = split[0]
            if not (param := keyword.get(name.removeprefix('no-'))):
                return Err(f'Unexpected keyword argument: --{kwarg}')
            if (param.annotation is bool) and (len(split) == 1):
                # No value is fine for a flag, check for --flag or --no-flag
                parsed_kwargs[param.name] = not param.default if name.startswith('no-') else param.default
                continue
            value: str = split[1]

            arginfo: Arg | None = get_args(param.annotation)[1] if is_annotated(param.annotation) else None
            parser: Callable[[str], Any] = (arginfo and arginfo.parse) or param.annotation  # ty:ignore[invalid-assignment]
            parsed_value = parser(value)
            parsed_kwargs[param.name] = parsed_value

        return Ok((parsed_args, parsed_kwargs))

    def invoke(self, *raw_args: str) -> None:
        """Calls this command with string arguments parsed from console input or logs an error.

        The command function is called with the ``console`` attribute as the first argument, so that the ``self``
        parameter in the function corresponds to its console and not the function.
        """
        match self.parse_raw_args(*raw_args):
            case Ok((args, kwargs)):
                self.func(self.console, *args, **kwargs)
            case Err(message):
                logger.error(message)

def command(name: str | None = None, **kwargs: Any) -> Callable[Callable[..., None], ConsoleCommand]:  # noqa: ANN401
    """Decorates a function into a :py:class:`CommandFunc`, intended for use on :py:class:`BotConsole` methods."""
    def wrapper(func: Callable[..., None]) -> ConsoleCommand:
        return ConsoleCommand(func, name, **kwargs)
    return wrapper

class BotConsoleMeta(type):
    """Metaclass for ``BotConsole``, handling registering commands."""

    def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> BotConsoleMeta:  # noqa: D102
        attrs['prompt'] = '> '
        attrs['commands']: benedict[str, Any] = benedict(keypath_separator=' ')
        attrs['commandlist']: list[ConsoleCommand] = []

        new_cls = super().__new__(cls, name, bases, attrs)
        for attr in new_cls.__mro__[0].__dict__.values():
            if not isinstance(attr, ConsoleCommand):
                continue
            depth = attrs['commands']
            for part in attr.group:
                if part not in attrs['commands']:
                    attrs['commands'][part] = {}
                depth = attrs['commands'][part]
            depth[attr.name] = attr
            attrs['commandlist'].append(attr)

        return new_cls

class BotConsole(metaclass=BotConsoleMeta):
    """Base class for bot consoles."""

    bot: commands.Bot
    prompt_prefix: str
    """A string shown before each user input prompt."""
    # Can't get ty to properly work with a recursive value type here so we're just using Any for now, see docstring
    commands: benedict[str, Any]
    """A map of command or group names to either a ``CommandFunc`` or another dictionary just like this one."""
    commandlist: list[ConsoleCommand]

    def __new__(cls, *_args: object, **_kwargs: object) -> Self:  # noqa: D102
        self: Self = super().__new__(cls)
        for command in self.commandlist:
            command.console = self
        return self

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.__class__.__name__}({self.bot!r}, prompt={self.prompt_prefix!r})'

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise NotImplementedError('BotConsole is a base class that cannot be directly instanced')

    def parse_input(self, user_input: str) -> Result[tuple[ConsoleCommand, list[str]], str]:
        """Returns an ``Ok`` of the :py:class:`ConsoleCommand` and parsed arguments, or an error message."""
        argstr: str = user_input
        cmd_or_group = self.commands
        for word in user_input.split(' '):
            argstr = argstr.removeprefix(word).strip()
            if word not in cmd_or_group:
                return Err(f'Unrecognized command: {word}')
            cmd_or_group = cmd_or_group[word]
            if isinstance(cmd_or_group, ConsoleCommand):
                command = cast('ConsoleCommand', cmd_or_group)
                args: list[str] = shlex.split(argstr)
                return Ok((command, args))
        return Err(f'Expected command after group name: {word}')

    async def start_loop(self) -> None:
        """Starts the console loop, returning when the ``stop`` command is issued or EOF is sent."""
        session = PromptSession()
        logger.debug('Console is active')
        while True:
            with patch_stdout(raw=True):
                try:
                    user_input: str = await session.prompt_async(self.prompt_prefix)
                except EOFError:
                    user_input = 'stop'

            user_input = user_input.strip()

            if not user_input:
                continue

            logger.log('CONSOLE', user_input)

            if user_input == 'stop':
                logger.info('Stopping...')

                # Make sure the bot doesn't try to download any more items in queue,
                # .close() will trigger on_player_stop()
                vc = cast('VoiceCog', self.bot.cogs['VoiceCog'])
                vc.queue_advance_lock.state = True
                vc.queue.clear()

                await self.bot.close()
                logger.info('Bot connection closed')
                return

            match self.parse_input(user_input):
                case Ok((command, args)):
                    command.invoke(*args)
                case Err(message):
                    logger.warning(message)

class LydianConsole(BotConsole):
    """Handles the bot's console command prompt loop."""

    def __init__(self, bot: commands.Bot | None, *, prompt: str = '> ') -> None:
        """Initializes a ``LydianConsole`` instance.

        :param bot: The Discord bot object to assign to this console. Can be given ``None`` to use an
            ``AsyncMock`` object instead for testing purposes.
        :param prompt: The string to show at the beginning of each input prompt.
        """
        self.bot = bot or AsyncMock(commands.Bot)
        self.prompt_prefix = prompt

    #region COMMANDS

    @command()
    def sigtest(self,
            a: str,
            b: Annotated[str, Arg(parse=lambda s: s.lower())],
            c: str | None = None,
            /, *,
            d: bool = False,
            e: int = 5,
        ) -> None:
        pass

    @command()
    def help(self, name: Annotated[str | None, Arg('command')] = None, /) -> None:
        """Prints information on all commands if no argument is given, or describes a given command."""
        if name:
            if name not in (command := self.commands.get(name)):
                logger.error(f'Unknown command: {name}')
            if not isinstance(command, ConsoleCommand):
                logger.error(f'Expected command after group name: {name}')
            else:
                console.print(command.help)
        else:
            console.print('\n\n'.join(c.help for c in self.commandlist))

    @command(group='debug')
    def debug_read(self, expr: str, /, *, log: bool = False) -> None:
        """Prints the result of an expression to stdout.

        The expression will have access to Python's built-ins, the global "config" and "perms" objects, and a "dbg"
        dictionary which stores references to various things specifically for debugging or development usage.

        :param expr: The expression to evaluate.
        :param log: Whether to log this evaluation (as DEBUG-level) or just print it to the screen.
        """
        print_fn = logger.debug if log else console.print

        # Can't be ast.literal_eval, we explicitly need access to some outside variables
        # This is only accessible in debug mode and will be warned about in multiple places
        try:
            eval_globals: dict[str, Any] = {'config': config, 'perms': perms, 'dbg': debug_context}
            print_fn(f'{expr} == {eval(expr, eval_globals)!r}')  # noqa: S307
        except Exception as e:  # noqa: BLE001
            # The full traceback for this case is usually unnecessary
            logger.error(f'{e.__class__.__name__}: {e}')

    @command()
    def uptime(self, /) -> None:
        """Prints how long the bot has been running for."""
        console.print(f'Bot has been running for {precisedelta(datetime.now(UTC) - debug_context['bot-start-time'])}')

    #endregion COMMANDS

bot_console = LydianConsole(None)
