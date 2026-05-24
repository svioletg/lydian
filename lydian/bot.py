"""Handles bot setup and execution."""
import asyncio
import inspect
import logging
import os
import sys
import traceback
from argparse import ArgumentParser
from datetime import UTC, datetime
from getpass import getpass

import discord
from benedict import benedict
from discord.ext import commands, tasks
from dotenv import load_dotenv
from loguru import logger
from rich.prompt import Confirm

from lydian.cogs.debug import DebugCog
from lydian.cogs.general import GeneralCog
from lydian.cogs.util import embed_error, embed_info
from lydian.cogs.voice import VoiceCog
from lydian.config import config
from lydian.console import bot_console
from lydian.const import (
    CONFIG_PATH,
    DATA_DIR,
    DL_DIR,
    DOTENV_PATH,
    LOGS_DIR,
    PERMISSIONS_PATH,
    PROJECT_VERSION,
    LogLevel,
    clear_tmp_dir,
    create_directories,
    debug_context,
    screen,
    setup_logger,
)
from lydian.errors import AbortCommand
from lydian.perms import PERMISSIONS_DEFAULT, perms
from lydian.util import dirsize, get_background_tasks, get_leaves

load_dotenv('.env')

class InterceptHandler(logging.Handler):
    """Handles redirecting logs for the ``discord`` module to ``loguru``."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        if record.funcName.startswith('_'):
            level = LogLevel.DEBUG

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = 'importlib' in filename and '_bootstrap' in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Redirect discord.py logs to our logger
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(config.logging.level)
# These generate huge debug logs
logging.getLogger('discord.gateway').setLevel(logging.INFO)
logging.getLogger('discord.http').setLevel(logging.INFO)
discord_logger.addHandler(InterceptHandler())

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    intents=intents,
    command_prefix=config.prefix,
)
debug_context['bot'] = bot

@bot.event
async def on_message(message: discord.Message) -> None:
    """Called when a message is created and sent."""
    if message.author.bot:
        return
    ctx = await bot.get_context(message)
    if ctx.command:
        if not isinstance(message.author, discord.Member):
            return
        if not perms.can_invoke(ctx.command.name, message.author):
            await ctx.send(embed=embed_info('You do not have the permissions needed for this command.'))
            return
    await bot.invoke(ctx)

@bot.event
async def on_error(event: str, *_: object, **__: object) -> None:
    """Handles non-command exceptions raised by events."""
    exc = sys.exc_info()[1]

    if isinstance(exc, AbortCommand):
        return

    logger.error(f'An error occurred during event {event!r}')
    logger.error(f'{exc}\n{''.join(traceback.format_exception(exc)).strip()}')

@bot.event
async def on_command_error(ctx: commands.Context, exc: Exception) -> None:
    """Handles exceptions raised during command execution."""
    if isinstance(exc, (commands.errors.CommandNotFound, AbortCommand)):
        return

    if isinstance(exc, commands.errors.CommandInvokeError):
        # Will clutter up the traceback, just use the exception this was raised from
        exc = exc.original

    await ctx.send(embed=embed_error('An unexpected error occurred.', 'Check logs for details.'))
    logger.error(f'{exc}\n{''.join(traceback.format_exception(exc)).strip()}')

@bot.event
async def on_ready() -> None:  # noqa: D103
    logger.info(f'Logged in as {bot.user}')
    logger.info('*** Ready! ***')

async def thread_bot() -> None:
    """Returns the ``Coroutine`` thread for the bot."""
    logger.debug('Starting bot thread...')
    async with bot:
        # Add cogs
        await bot.add_cog(GeneralCog(bot))
        await bot.add_cog(VoiceCog(bot))
        if config.debug:
            await bot.add_cog(DebugCog(bot))

        debug_context['cog'] = {name.removesuffix('Cog').lower():cog for name, cog in bot.cogs.items()}
        debug_context['tasks'] = benedict(get_background_tasks(bot))
        debug_context['tasklist'] = list(get_leaves(debug_context['tasks'], tasks.Loop))

        # Start
        logger.info('Logging in; wait for "Ready!" before running commands')

        target_env_var: str = 'LYDIAN_DEBUG_TOKEN' if config.debug else 'LYDIAN_TOKEN'
        if not (token := os.environ.get(target_env_var)):
            logger.error(f'No bot token found, please set the {target_env_var} environment variable')
            return

        debug_context['bot-start-time'] = datetime.now(UTC)
        try:
            await bot.start(token)
        except discord.LoginFailure as e:
            if 'Improper token' in str(e):
                logger.error('Bad token given; check your'
                    + f' {'LYDIAN_DEBUG_TOKEN' if config.debug else 'LYDIAN_TOKEN'} value')
            else:
                logger.opt(exception=e).error(f'Failed to log in: {e}')

async def thread_console() -> None:
    """Returns the ``Coroutine`` thread for the interactive console."""
    while not bot.user:  # noqa: ASYNC110
        # For ignoring ASYNC110: Login failures cause issues with a running console, so we need to make sure the bot is
        # logged in first, and since `await bot.start()` blocks until's connection is closed, we have no way of ensuring
        # that through an event alone. This is the only way to do this for now.
        await asyncio.sleep(1)

    bot_console.bot = bot
    await bot_console.start_loop(catch=True)

def prompt_bot_setup() -> bool:
    """Prompts the user to setup Lydian in the current working directory and returns whether the user confirmed."""
    if Confirm.ask('Do you want to setup Lydian in this directory?'):
        if not CONFIG_PATH.exists():
            CONFIG_PATH.touch()
            screen.print(f'Created file: {CONFIG_PATH}')
        if not PERMISSIONS_PATH.exists():
            PERMISSIONS_DEFAULT.to_yaml(PERMISSIONS_PATH)
            screen.print(f'Created file: {PERMISSIONS_PATH}')
        if not DATA_DIR.exists():
            DATA_DIR.mkdir()
            screen.print(f'Created directory: {DATA_DIR}')
        if not DOTENV_PATH.exists():
            screen.print('No .env file found; creating one now.')
            token: str = getpass('Enter or paste your bot token: ', echo_char='*')
            DOTENV_PATH.write_text(f'LYDIAN_TOKEN={token.strip()}\n')
            screen.print(f'Created file: {DOTENV_PATH}')
        return True
    return False

async def async_main() -> int:
    """Initializes the logger and starts the bot."""
    if not CONFIG_PATH.exists():
        screen.print('"lydian-config.toml" not found in this directory.')
        return 1 if prompt_bot_setup() else 0

    setup_logger(
        config.logging.level,
        logs_dir=LOGS_DIR,
        log_in_utc=config.logging.utc,
    )

    logger.debug('Logging started')
    logger.info(f'Lydian v{PROJECT_VERSION}')

    if config.logging.utc:
        logger.info('Log times are set to UTC')
    else:
        logger.info("Log times are set to the system's local time")

    if (config.media_dir_warn_threshold > -1) \
        and (media_size_total := dirsize(DL_DIR)) > config.media_dir_warn_threshold:
        logger.warning(f'Media directory is taking up {media_size_total} bytes, exceeding the threshold of'
        + f' {config.media_dir_warn_threshold}')

    logger.info('Starting...')

    if config.debug:
        logger.warning('*** Debug mode is enabled! ***')

    create_directories()
    clear_tmp_dir()

    _, pending = await asyncio.wait(
        (asyncio.create_task(thread_bot()), asyncio.create_task(thread_console())),
        return_when=asyncio.FIRST_COMPLETED,
    )

    tasklist: list[tasks.Loop] = debug_context['tasklist']

    for task in tasklist:
        if (internal := task.get_task()) and internal.done():
            _ = internal.exception()

    for task in pending:
        task.cancel()

    return 0

@logger.catch(onerror=lambda _: sys.exit(1))
def main() -> None:  # noqa: D103
    parser = ArgumentParser(description='Starts the Lydian Discord bot if given no arguments.')
    parser.add_argument('-V', '--version', action='store_true',
        help='Prints the currently installed Lydian version and exits.')

    args = parser.parse_args()
    print_version: bool = args.version

    if print_version:
        screen.print(f'Lydian v{PROJECT_VERSION}')
        sys.exit()

    sys.exit(asyncio.run(async_main()))
