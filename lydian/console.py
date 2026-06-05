"""Holds the :py:class:`BotConsole` class to handle console commands while running the bot."""
import asyncio
import inspect
import shlex
from asyncio.tasks import Task
from collections.abc import Callable
from datetime import UTC, datetime
from itertools import zip_longest
from types import EllipsisType, NoneType
from typing import TYPE_CHECKING, Annotated, Any, Protocol, Self, Union, cast, get_args, get_origin
from unittest.mock import AsyncMock

from benedict import benedict
from discord.ext import tasks
from discord.ext.commands import Bot
from humanize import precisedelta
from loguru import logger
from maybetype import Err, Ok, Result
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.markup import escape

from lydian import __version__
from lydian.config import config
from lydian.const import debug_context, screen, setup_logger
from lydian.perms import perms
from lydian.update import check_for_updates
from lydian.util import expect, get_annotation, is_annotated, join_trailing, tabulate, wrap_paragraphs

if TYPE_CHECKING:
    from ty_extensions import Intersection

    from lydian.cogs.voice import VoiceCog

class Named(Protocol):
    """Protocol for types which have a ``__name__`` string attribute."""

    __name__: str

class Arg:
    """Customizes a positional argument to a :py:class:`ConsoleCommand` function.

    .. important::
        The ``name`` attribute will be unset until processed in a :py:class:`ConsoleCommand`, at which point if not
        already set it is defaulted to the parameter's original name.
    """

    def __init__(self,
            name: str | None = None,
            *,
            doc: str = '',
            parse: Callable[[str], Any] | None = None,
            default: Any | EllipsisType = ...,  # noqa: ANN401
        ) -> None:
        """Initializes a new ``Arg``.

        :param name: A custom name to use in help text and as the keyword for this argument, if applicable. Underscores
            will be automatically converted to hyphens to make it kebab-cased.
        :param doc: A string of help text to describe this argument.
        :param parse: A function to convert this argument value from the raw string given to the desired type.
            If ``None``, the parameter's type annotation will be called with the argument string.
            When given with a variable parameter (like ``*args``), ``parse`` will be mapped onto each string.
        :param default: A default to give this argument, or ``...`` to provide no default. This will be overwritten by
            the actual default of the parameter if one is present, so this is largely intended to be used for giving
            variable parameters a default value, thus making them optional.
        """
        self.name: str
        if name:
            self.name = name.replace('_', '-')
        self.doc: str = doc
        self.parse: Callable[[str], Any] | None = parse
        self.default: Any | EllipsisType = default

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.__class__.__name__}(name={self.name!r})'

class ConsoleCommand:
    """A wrapper object for functions meant as :py:class:`BotConsole` commands.

    Calling a ``ConsoleCommand`` instance will call the wrapped function after parsing the arguments using the present
    annotations, if any.
    """

    def __init__(self,
            func: Callable[..., None],
            name: str | None = None,
            *,
            enabled: bool = True,
            group: str | tuple[str, ...] = (),
            doc: str | None = None,
            console: BotConsole | None = None,
        ) -> None:
        """Initializes a new ``ConsoleCommand``.

        :param func: The function to wrap as a command.
        :param name: A name to give this command, defaulting to the function's name minus any group prefix.
        :param enable: Whether this command should be enabled in the console it is added to. If ``False``,
            the command will not be registered to the console and calling :py:meth:`invoke` will return immediately.
        :param group: A single group or tuple of nested group names to put this command under.
        :param doc: A string to use to describe this command for the ``help`` command. Will use ``func``'s docstring if
            not given.
        :param console: The :py:class:`BotConsole` object this command belongs to. ``None`` by default; set
            automatically if registered to a console.
        """
        self.func = cast('Intersection[Callable[..., None], Named]', self.validate(func))
        self.enabled = enabled
        self.group = group if isinstance(group, tuple) else (group,)
        self.name = name or (
            self.func.__name__ if not self.group else
            self.func.__name__.removeprefix('_'.join(self.group) + '_')
        )
        self.doc: str | None = doc or func.__doc__
        self.console = console

        self.func_sig: inspect.Signature = inspect.signature(func)
        self.arginfo: dict[str, Arg] = {}

        for param in self.func_sig.parameters.values():
            if param.name == 'self':
                continue
            arginfo = get_annotation(param.annotation) or Arg()
            if not hasattr(arginfo, 'name'):
                arginfo.name = param.name.replace('_', '-')
            if param.default is not inspect.Parameter.empty:
                arginfo.default = param.default
            self.arginfo[param.name] = self.arginfo[arginfo.name] = arginfo

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
                # Only allow functions with positional-only and keyword-only parameters
                #
                # This helps ease work later and there generally isn't a use for
                # positional-or-keyword parameters in a command context
                raise TypeError('Command function parameters must be positional-only or keyword-only:'
                    + f' {param!r} in {func}')

        return func

    @property
    def qualified_name(self) -> str:
        """The command's name prefixed with its groups, separated by spaces."""
        return join_trailing(self.group, ' ', trail_single=True) + self.name

    @property
    def cli_signature(self) -> str:
        """A CLI-style command signature created from the wrapped function's signature."""
        parts: list[str] = []
        for param in self.func_sig.parameters.values():
            if param.name == 'self':
                continue
            arginfo: Arg = self.arginfo[param.name]
            name: str = arginfo.name
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                name = f'{name}...'
            if arginfo.default is ...:
                # Required parameter
                name = f'<{name}>'
            elif param.annotation is bool:
                # Flag parameter
                name = f'[--{name}]' if arginfo.default is False else f'[--no-{name}]'
            else:
                # Optional parameter
                name = f'[{f'--{name}=' if param.kind is inspect.Parameter.KEYWORD_ONLY else name}]'
            parts.append(name)

        return f'{self.qualified_name} {' '.join(parts)}'.strip()

    @property
    def help(self) -> str:
        """Returns the string printed when using the ``help`` command on this command (or showing all)."""
        return f'{self.cli_signature}\n' + '\n'.join(wrap_paragraphs(
            self.doc or '(no description)',
            80,
            initial_indent='    ',
            subsequent_indent='    ',
        ))

    def parse_raw_args(self, *raw_args: str) -> Result[tuple[list[Any], dict[str, Any]], str]:  # noqa: C901, PLR0915
        """Parses raw string argument values into values ready to call the wrapped function with.

        If parsing was successful, returns ``Ok`` of a tuple of the parsed positional argument values, and a dictionary
        of parsed keyword arguments. If parsing failed because of user input error, returns ``Err`` with an error
        message. If parsing failed because of invalid command function defintions or otherwise an error outside the
        user's control, ``ValueError`` or ``TypeError`` may be raised.
        """
        positional: list[inspect.Parameter] = []
        keyword: dict[str, inspect.Parameter] = {}

        for param in self.func_sig.parameters.values():
            if param.name == 'self':
                continue
            if param.kind in [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.VAR_POSITIONAL]:
                positional.append(param)
            else:
                keyword[param.name] = param

        pos_vals: list[str] = []
        kw_vals: list[str] = []

        for s in raw_args:
            if s.startswith('--'):
                kw_vals.append(s.removeprefix('--'))
            else:
                pos_vals.append(s)

        parsed_args: list[Any] = []
        parsed_kwargs: dict[str, Any] = {}

        for n, (value, param) in enumerate(zip_longest(pos_vals, positional, fillvalue=None)):
            if param is None:
                return Err(f'Unexpected additional argument: {value!r}')
            argtype, arginfo = cast('tuple[Any, Arg]', get_args(param.annotation)) if is_annotated(param.annotation) \
                else (param.annotation, self.arginfo[param.name])
            if value is None:
                if arginfo.default is ...:
                    return Err('Missing required positional argument(s):'
                        + f' {', '.join(p.name for p in positional[n:])}')
                if param.kind is inspect.Parameter.VAR_POSITIONAL:
                    parsed_args.extend(arginfo.default)
                    break
                parsed_args.append(arginfo.default)
                continue
            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                remaining: tuple[str, ...] = tuple(pos_vals[n:])
                parser: Callable[[str], Any] = (arginfo and arginfo.parse) or argtype  # ty:ignore[invalid-assignment]
                parsed_args.extend(tuple(map(parser, remaining)))
                break
            if get_origin(argtype) is Union:
                t_args = get_args(argtype)
                if t_args[1] is not NoneType:
                    raise TypeError(f'Command function parameter unions can only be T | None: {argtype} (in {param!r})')
                argtype = t_args[0]
            parser: Callable[[str], Any] = (arginfo and arginfo.parse) or argtype  # ty:ignore[invalid-assignment]
            try:
                parsed_args.append(parser(value))
            except (TypeError, ValueError) as e:
                return Err(f"Failed to parse value for argument '{arginfo.name}': {e.__class__.__name__}: {e}")

        for kwarg in kw_vals:
            split: list[str] = kwarg.split('=', maxsplit=1)
            name: str = split[0]
            if not (param := keyword.get(name.removeprefix('no-').replace('-', '_'))):
                return Err(f'Unexpected keyword argument: --{kwarg}')
            if (param.annotation is bool) and (len(split) == 1):
                # No value is fine for a flag, check for --flag or --no-flag
                parsed_kwargs[param.name] = not name.startswith('no-')
                continue
            value: str = split[1]
            arginfo: Arg = self.arginfo[name]
            parser: Callable[[str], Any] = (arginfo and arginfo.parse) or param.annotation  # ty:ignore[invalid-assignment]
            parsed_value = parser(value)
            try:
                parsed_kwargs[param.name] = parsed_value
            except (TypeError, ValueError) as e:
                return Err(f"Failed to parse value for argument '{arginfo.name}': {e.__class__.__name__}: {e}")

        return Ok((parsed_args, parsed_kwargs))

    def invoke(self, *raw_args: str) -> None:
        """Calls this command with string arguments parsed from console input or logs an error.

        The command function is called with the ``console`` attribute as the first argument, so that the ``self``
        parameter in the function corresponds to its console and not the function.
        """
        if not self.enabled:
            return

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
        attrs['prompt_prefix'] = '> '
        attrs['commands'] = benedict(keypath_separator=' ')
        attrs['commandlist'] = []

        new_cls = super().__new__(cls, name, bases, attrs)

        # Register commands
        for attr in new_cls.__mro__[0].__dict__.values():
            if not isinstance(attr, ConsoleCommand):
                continue
            if not attr.enabled:
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

    bot: Bot
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

    async def start_loop(self, *, catch: bool = False) -> None:
        """Starts the console loop, returning when the ``stop`` command is issued or EOF is sent.

        :param catch: Whether to catch all exceptions raised from a command and log them instead of propagating.
        """
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
                    try:
                        command.invoke(*args)
                    except Exception as e:
                        if catch:
                            logger.opt(exception=e).error(f'Unexpected error while invoking command: {user_input}')
                        else:
                            raise
                case Err(message):
                    logger.warning(message)

class LydianConsole(BotConsole):
    """Handles the bot's console command prompt loop."""

    def __init__(self, bot: Bot | None, *, prompt: str = '> ') -> None:
        """Initializes a ``LydianConsole`` instance.

        :param bot: The Discord bot object to assign to this console. Can be given ``None`` to use an
            ``AsyncMock`` object instead for testing purposes.
        :param prompt: The string to show at the beginning of each input prompt.
        """
        self.bot = bot or AsyncMock(Bot)
        self.prompt_prefix = prompt

    #region COMMANDS

    @command()
    def help(self, /, *name_parts: Annotated[str, Arg('command', default=())]) -> None:
        """Prints information on all commands if no argument is given, or describes a given command."""
        name: str = ' '.join(name_parts)
        if name:
            if not (command := self.commands.get(name)):
                logger.error(f'Unknown command: {name}')
            elif not isinstance(command, ConsoleCommand):
                logger.error(f'Expected command after group name: {name}')
            else:
                screen.print(escape(command.help))
        else:
            screen.print(escape('\n\n'.join(c.help for c in self.commandlist)))

    @command(enabled=config.debug, group='debug')
    def debug_read(self, expr: str, /, *, log: bool = False) -> None:
        """Prints the result of an expression to stdout.

        The expression will have access to Python's built-ins, the global "config" and "perms" objects, and a "dbg"
        dictionary which stores references to various things specifically for debugging or development usage.

        For convenience, "?" can be used in place of "dbg." at the beginning of the expression, e.g. "?bot.user" is
        parsed as "dbg.bot.user".

        :param expr: The expression to evaluate.
        :param log: Whether to log this evaluation (as DEBUG-level) or just print it to the screen.
        """
        print_fn = logger.debug if log else screen.print

        eval_globals: dict[str, Any] = {'config': config, 'perms': perms, 'dbg': debug_context}
        parsed_expr: str = expr
        if parsed_expr[0] == '?':
            parsed_expr = parsed_expr.replace('?', 'dbg.', count=1)

        try:
            # Can't be ast.literal_eval, we explicitly need access to some outside variables
            # This is only accessible in debug mode and will be warned about in multiple places
            print_fn(f'{parsed_expr} == {eval(parsed_expr, eval_globals)!r}')  # noqa: S307
        except Exception as e:  # noqa: BLE001
            # The full traceback for this case is usually unnecessary
            logger.error(f'{e.__class__.__name__}: {e}')

    @staticmethod
    def task_status(task: Task) -> str:
        """Returns a rich-formatted string based on the task's status."""
        if task.cancelled():
            return '[warn]cancelled[/]'
        if task.done():
            if exc := task.exception():
                return f'[err]failed ({exc.__class__.__name__})[/]'
            return '[warn]done[/]'
        return '[ok]running[/]'

    @staticmethod
    def task_interval(task: tasks.Loop) -> str:
        """Returns a rich-formatted string based on the task's interval."""
        intervals: list[str] = []
        if task.time:
            return ', '.join(str(dt) for dt in task.time)
        else:
            if task.seconds:
                intervals.append(f'{task.seconds}s')
            if task.minutes:
                intervals.append(f'{task.minutes}m')
            if task.hours:
                intervals.append(f'{task.hours}h')
            return ', '.join(intervals)

    @command(group='tasks')
    def tasks_list(self, /) -> None:
        """Prints background tasks and their status."""
        status_table: list[tuple[str, str, str, str]] = [('ID', 'NAME', 'STATUS', 'INTERVAL(S)')]
        for n, task in enumerate(cast('list[tasks.Loop]', debug_context['tasklist'])):
            if not (inner_task := task.get_task()):
                status_table.append((str(hash(task)), f'(NO TASK: {task})', '', ''))
            else:
                status_table.append((
                    str(n), inner_task.get_name(), self.task_status(inner_task), self.task_interval(task),
                ))

        screen.print(tabulate(
            status_table[1:],
            header=status_table[0],
            hsep='  ',
            strip=r'\[[\w/]+\]',
        ))

    @command(group='tasks')
    def tasks_start(self, task_id: int, /) -> None:
        """Attempts to start a background task which is not running. Use ``tasks list`` to see IDs."""
        tasklist: list[tasks.Loop] = debug_context['tasklist']
        if not 0 <= task_id < len(tasklist):
            logger.error('task_id out of range')
            return
        task = tasklist[task_id]
        if task.is_running():
            logger.info(f'Task is already running: {expect(task.get_task()).get_name()}')
            return
        logger.info(f'Starting task: {expect(task.get_task()).get_name()}')
        task.start()

    @command()
    def updates(self, /) -> None:
        """Checks if any newer releases of Lydian are available."""
        check_for_updates()

    @command()
    def uptime(self, /) -> None:
        """Prints how long the bot has been running for."""
        screen.print(f'Bot has been running for {precisedelta(datetime.now(UTC) - debug_context['bot-start-time'])}')

    @command()
    def version(self, /) -> None:
        """Prints the version of Lydian that is currently running."""
        screen.print(f'Lydian v{__version__}')

    #endregion COMMANDS

bot_console = LydianConsole(None)

if __name__ == '__main__':
    setup_logger(config.logging.level)
    asyncio.run(bot_console.start_loop())
