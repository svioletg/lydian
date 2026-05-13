"""Handles bot setup and execution."""
import asyncio
import logging
import os
import shlex
import sys
import traceback
from datetime import UTC, datetime
from getpass import getpass
from typing import Any, cast

import discord
from discord.ext import commands
from dotenv import load_dotenv
from humanize import precisedelta
from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.prompt import Confirm

from lydian.cogs.debug import DebugCog
from lydian.cogs.general import GeneralCog
from lydian.cogs.util import embed_error, embed_info
from lydian.cogs.voice import VoiceCog
from lydian.cogs.voice import background_tasks as voice_background_tasks
from lydian.config import config
from lydian.const import (
    CONFIG_PATH,
    DATA_DIR,
    DL_DIR,
    DOTENV_PATH,
    LOGS_DIR,
    PERMISSIONS_PATH,
    PROJECT_VERSION,
    clear_tmp_dir,
    console,
    create_directories,
    debug_context,
    setup_logger,
)
from lydian.errors import AbortCommand
from lydian.perms import PERMISSIONS_DEFAULT, perms
from lydian.util import dirsize

load_dotenv('.env')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    intents=intents,
    command_prefix=config.prefix,
    log_handler=logging.FileHandler(filename=LOGS_DIR / 'discord.log', encoding='utf-8', mode='w'),
)

debug_context['bot'] = bot

event_start_console = asyncio.Event()

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
        await bot.add_cog(cog_voice := VoiceCog(bot))
        if config.debug:
            await bot.add_cog(DebugCog(bot))

        debug_context['cog.voice'] = cog_voice

        # Start
        logger.info('Logging in; wait for "Ready!" before running commands')

        target_env_var: str = 'LYDIAN_DEBUG_TOKEN' if config.debug else 'LYDIAN_TOKEN'
        if not (token := os.environ.get(target_env_var)):
            logger.error(f'No bot token found, please set the {target_env_var} environment variable')
            return

        event_start_console.set()
        debug_context['bot-start-time'] = datetime.now(UTC)
        await bot.start(token)

# TODO(svioletg): https://github.com/svioletg/lydian-discord-bot/issues/2
async def thread_console() -> None:  # noqa: C901
    """Returns the ``Coroutine`` thread for the interactive console."""
    await event_start_console.wait()

    session = PromptSession()

    logger.debug('Console is active')

    while True:
        # raw=True to allow log colorization
        with patch_stdout(raw=True):
            try:
                user_input: str = await session.prompt_async('> ')
            except EOFError:
                user_input = 'stop'

        if not user_input:
            continue

        logger.log('CONSOLE', user_input)

        if user_input == 'stop':
            logger.info('Stopping...')

            # Make sure the bot doesn't try to download any more items in queue,
            # .close() will trigger on_player_stop()
            vc = cast('VoiceCog', bot.cogs['VoiceCog'])
            vc.queue_advance_lock.state = True
            vc.queue.clear()

            await bot.close()
            logger.info('Bot connection closed')
            return

        command, *args = shlex.split(user_input)

        if command == 'uptime':
            if args:
                logger.error('Command "uptime" takes no arguments')
                continue
            console.print(
                f'Bot has been running for {precisedelta(datetime.now(UTC) - debug_context['bot-start-time'])}',
            )
            continue

        if config.debug and (command == 'debug'):
            if not args:
                logger.error('Expected sub-command after "debug"')
                continue
            command, *args = args

            if (command in ('read', 'readlog')):
                print_fn = logger.debug if command == 'readlog' else console.print
                if len(args) != 1:
                    logger.error(f'Expected single argument to console command "{command}"')
                    continue

                expr: str = args[0]

                # Can't be ast.literal_eval, we explicitly need access to some outside variables
                # This is only accessible in debug mode and will be warned about in multiple places
                try:
                    eval_globals: dict[str, Any] = {'config': config, 'perms': perms, 'dbg': debug_context}
                    print_fn(f'{expr} == {eval(expr, eval_globals)!r}')  # noqa: S307
                except Exception as e:  # noqa: BLE001
                    logger.error(f'{e.__class__.__name__}: {e}')
                continue

        logger.warning(f'Unrecognized console input: {user_input}')

def prompt_bot_setup() -> bool:
    """Prompts the user to setup Lydian in the current working directory and returns whether the user confirmed."""
    if Confirm.ask('Do you want to setup Lydian in this directory?'):
        if not CONFIG_PATH.exists():
            CONFIG_PATH.touch()
            console.print(f'Created file: {CONFIG_PATH}')
        if not PERMISSIONS_PATH.exists():
            PERMISSIONS_DEFAULT.to_yaml(PERMISSIONS_PATH)
            console.print(f'Created file: {PERMISSIONS_PATH}')
        if not DATA_DIR.exists():
            DATA_DIR.mkdir()
            console.print(f'Created directory: {DATA_DIR}')
        if not DOTENV_PATH.exists():
            console.print('No .env file found; creating one now.')
            token: str = getpass('Enter or paste your bot token: ', echo_char='*')
            DOTENV_PATH.write_text(f'LYDIAN_TOKEN={token.strip()}\n')
            console.print(f'Created file: {DOTENV_PATH}')
        return True
    return False

async def async_main() -> int:
    """Initializes the logger and starts the bot."""
    if not CONFIG_PATH.exists():
        console.print('"lydian-config.toml" not found in this directory.')
        return 1 if prompt_bot_setup() else 0

    setup_logger(
        'DEBUG' if config.debug else config.logging.log_level,
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

    for task in voice_background_tasks:
        if (internal := task.get_task()) and internal.done():
            _ = internal.exception()

    for task in pending:
        task.cancel()

    return 0

@logger.catch(onerror=lambda _: sys.exit(1))
def main() -> None:  # noqa: D103
    if len(sys.argv) > 1:
        console.print('[err]ERROR: lydian takes 0 arguments[/]')
        sys.exit(1)
    sys.exit(asyncio.run(async_main()))
