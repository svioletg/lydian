"""Holds the :py:class:`BotConsole` class to handle console command while running the bot."""
import shlex
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

from discord.ext import commands
from humanize import precisedelta
from loguru import logger
from maybetype import Err, Ok, Result
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from lydian.config import config
from lydian.const import console, debug_context
from lydian.perms import perms
from lydian.util import wrap_paragraphs

if TYPE_CHECKING:
    from lydian.cogs.voice import VoiceCog

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
            help: str | None = None,  # noqa: A002
        ) -> None:
        """Initializes a new ``ConsoleCommand``.

        :param func: The function to wrap as a command.
        :param name: A name to give this command, defaulting to the function's name minus any group prefix.
        :param group: A single group or tuple of nested group names to put this command under.
        :param help: The string shown when using the ``help`` command on this command. Defaults to ``func``'s
            docstring.
        """
        self.func = func
        self.group = group if isinstance(group, tuple) else (group,)
        self.name = name or (
            cast('str', func.__name__) if not self.group else  # ty:ignore[unresolved-attribute]
            cast('str', func.__name__).removeprefix('_'.join(self.group) + '_')  # ty:ignore[unresolved-attribute]
        )
        self.help: str | None = help or func.__doc__

    def __call__(self, *args: object, **kwargs: object) -> None:
        """Calls the wrapped function after parsing ``args`` from potentially string values."""
        self.func(*args, **kwargs)

def command(name: str | None = None, **kwargs: Any) -> Callable[Callable[..., None], ConsoleCommand]:  # noqa: ANN401
    """Decorates a function into a :py:class:`CommandFunc`, intended for use on :py:class:`BotConsole` methods."""
    def wrapper(func: Callable[..., None]) -> ConsoleCommand:
        return ConsoleCommand(func, name, **kwargs)
    return wrapper

class BotConsole:
    """Handles the bot's console command prompt loop."""

    def __init__(self, bot: commands.Bot | None, *, prompt: str = '> ') -> None:
        """Initializes a ``BotConsole`` instance.

        :param bot: The Discord bot object to assign to this console. Can be given ``None`` to use an
            ``AsyncMock`` object instead for testing purposes.
        :param prompt: The string to show at the beginning of each input prompt.
        """
        self.bot = bot or AsyncMock(commands.Bot)
        self.prompt = prompt

        # Can't get ty to properly work with a recursive value type here so we're just using Any for now, see docstring
        self.commands: dict[str, Any] = {}
        """A map of command or group names to either a ``CommandFunc`` or another dictionary just like this one."""

        for name in dir(self):
            if not isinstance(func := getattr(self, name), ConsoleCommand):
                continue
            depth = self.commands
            # Set name for if func.group is empty
            for part in func.group if isinstance(func.group, tuple) else (func.group,):
                if part not in self.commands:
                    self.commands[part] = {}
                depth = self.commands[part]
            depth[func.name] = func

    # TODO(svioletg): Add method to create CLI-style command signature from function signature
    # https://github.com/svioletg/lydian-discord-bot/issues/2

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
                    user_input: str = await session.prompt_async(self.prompt)
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
                    command(self, *args)
                case Err(message):
                    logger.warning(message)

    #region COMMANDS

    @command()
    def help(self, command: str | None = None) -> None:
        """Prints information on all commands if no argument is given, or describes a given command."""
        help_str: str = ''
        if not command:
            for name, func in self.commands.items():
                # TODO(svioletg): Need to support groups
                wrapped_help: str = '\n'.join(wrap_paragraphs(
                    func.help or '(no description)',
                    80,
                    initial_indent='    ',
                    subsequent_indent='    ',
                ))
                help_str += f'{name}\n{wrapped_help}\n\n'

        console.print(help_str.strip())

    @command(group='debug')
    def debug_read(self, expr: str, *, log: bool = False) -> None:
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
    def uptime(self) -> None:
        """Prints how long the bot has been running for."""
        console.print(f'Bot has been running for {precisedelta(datetime.now(UTC) - debug_context['bot-start-time'])}')

    #endregion COMMANDS
