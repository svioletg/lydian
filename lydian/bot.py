"""Handles bot setup and execution."""
import asyncio
import logging
import os
import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.prompt import Confirm

from lydian.cogs.debug import DebugCog
from lydian.cogs.general import GeneralCog
from lydian.cogs.util import embed_error
from lydian.cogs.voice import VoiceCog
from lydian.config import config
from lydian.const import (
    CONFIG_PATH,
    LOGS_DIR,
    PROJECT_VERSION,
    clear_tmp_dir,
    console,
    create_directories,
    setup_logger,
)
from lydian.errors import AbortCommand

load_dotenv('.env')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    intents=intents,
    command_prefix=config.prefix,
    log_handler=logging.FileHandler(filename=LOGS_DIR / 'discord.log', encoding='utf-8', mode='w'),
)

event_start_console = asyncio.Event()

@bot.event
async def on_command_error(ctx: commands.Context, exc: Exception) -> None:
    """Handles exceptions raised while the bot is running."""
    try:
        if isinstance(exc, (commands.errors.CommandNotFound, AbortCommand)):
            return

        if isinstance(exc, commands.CommandInvokeError):
            # Will clutter up the traceback, just use the exception this was raised from
            exc = exc.original

        await ctx.send(embed=embed_error('An unexpected error occurred.', 'Check logs for details.'))
        logger.error(f'{exc}\n{''.join(traceback.format_exception(exc)).strip()}')
    except Exception as e:  # noqa: BLE001 ; Otherwise any exception raised in the handler is eaten and ignored
        logger.error(''.join(traceback.format_exception(e)))

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

        # Start
        logger.info('Logging in; wait for "Ready!" before running commands')

        target_env_var: str = 'LYDIAN_DEBUG_TOKEN' if config.debug else 'LYDIAN_TOKEN'
        if not (token := os.environ.get(target_env_var)):
            logger.error(f'No bot token found, please set the {target_env_var} environment variable')
            return

        event_start_console.set()
        await bot.start(token)

async def thread_console() -> None:
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
            await bot.close()
            logger.info('Bot connection closed')
            return
        logger.warning(f'Unrecognized console input: {user_input}')

async def async_main() -> int:
    """Initializes the logger and starts the bot."""
    if not CONFIG_PATH.exists():
        console.print('lydian-config.toml must be present in the current directory to run the bot.')
        console.print('If this file is found, a "lydian-data" directory will be created here if it does not exist.')
        if Confirm.ask('Create this file now?'):
            CONFIG_PATH.touch()
            console.print(f'Created empty file at: {CONFIG_PATH}')
        return 0

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

    logger.info('Starting...')

    if config.debug:
        logger.warning('Debug mode is enabled!')

    create_directories()
    clear_tmp_dir()

    _, pending = await asyncio.wait(
        (asyncio.create_task(thread_bot()), asyncio.create_task(thread_console())),
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()

    return 0

@logger.catch(onerror=lambda _: sys.exit(1))
def main() -> int:  # noqa: D103
    sys.exit(asyncio.run(async_main()))
