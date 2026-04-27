"""Handles bot setup and execution."""
import asyncio
import logging
import os
import sys
import traceback

import aioconsole
import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger
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
    TOKEN_PATH,
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

def get_token() -> str | None:
    """Returns the Discord bot token from either a ``token.txt`` file or from the environment.

    If the environment variable ``LYDIAN_TOKEN`` is set, its value takes precedence over ``token.txt``.
    """
    return os.environ.get('LYDIAN_TOKEN') or (TOKEN_PATH.read_text('utf-8').strip() if TOKEN_PATH.exists() else None)

@bot.event
async def on_command_error(ctx: commands.Context, exc: Exception) -> None:
    """Handles exceptions raised while the bot is running."""
    if isinstance(exc, (commands.errors.CommandNotFound, AbortCommand)):
        return

    await ctx.send(embed=embed_error('An unexpected error occurred.', 'Check logs for details.'))
    logger.error(f'{exc}\n{''.join(traceback.format_exception(exc)).strip()}')

@bot.event
async def on_ready() -> None:  # noqa: D103
    logger.info(f'Logged in as {bot.user}')
    logger.info('Ready!')

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
        if not (token := get_token()):
            logger.error(
                'Failed to find a bot token; no token.txt file present and the LYDIAN_TOKEN environment variable has'
                + ' not been set',
            )
            raise SystemExit(1)
        await bot.start(token)

async def thread_console() -> None:
    """Returns the ``Coroutine`` thread for the interactive console."""
    logger.info('Console is active')
    while True:
        user_input: str = await aioconsole.ainput()
        user_input = user_input.lower().strip()
        if not user_input:
            continue
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
        stdout_level='DEBUG' if config.debug else config.logging.log_level,
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

    await asyncio.gather(
        asyncio.create_task(thread_bot()),
        asyncio.create_task(thread_console()),
    )

    return 0

@logger.catch(onerror=lambda _: sys.exit(1))
def main() -> int:  # noqa: D103
    sys.exit(asyncio.run(async_main()))
