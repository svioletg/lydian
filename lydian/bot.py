"""Handles bot setup and execution."""
import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger
from rich.prompt import Confirm

from lydian.cogs.general import GeneralCog
from lydian.config import config
from lydian.const import CONFIG_PATH, DATA_DIR, LOGS_DIR, TMP_DIR, TOKEN_PATH, console, setup_logger

load_dotenv('.env')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    intents=intents,
    command_prefix=config.prefix,
)

def get_token() -> str | None:
    """Returns the Discord bot token from either a ``token.txt`` file or from the environment.

    If the environment variable ``LYDIAN_TOKEN`` is set, its value takes precedence over ``token.txt``.
    """
    return os.environ.get('LYDIAN_TOKEN') or (TOKEN_PATH.read_text('utf-8').strip() if TOKEN_PATH.exists() else None)

@bot.event
async def on_ready() -> None:  # noqa: D103
    logger.info(f'Logged in as {bot.user}')
    logger.info('Ready!')

async def thread_bot() -> None:
    """Returns the ``Coroutine`` thread for the bot."""
    logger.debug('Starting bot thread...')
    async with bot:
        await bot.add_cog(GeneralCog(bot))
        logger.info('Logging in...')
        if not (token := get_token()):
            logger.error(
                'Failed to find a bot token; no token.txt file present and the LYDIAN_TOKEN environment variable has'
                + ' not been set',
            )
            raise SystemExit(1)
        await bot.start(token)

async def async_main() -> int:
    """Initializes the logger and starts the bot."""
    if not CONFIG_PATH.exists():
        console.print('lydian-config.toml must be present in the current directory to run the bot.')
        if Confirm.ask('Create this file here?'):
            CONFIG_PATH.touch()
            console.print(f'Created empty file {CONFIG_PATH}')
        return 0

    setup_logger(stdout_level=config.logging.log_level, logs_dir=LOGS_DIR)

    logger.info('Starting...')

    if not DATA_DIR.is_dir():
        logger.info('Creating data directory...')
        DATA_DIR.mkdir()

    if not TMP_DIR.is_dir():
        logger.info('Creating tmp directory...')
        TMP_DIR.mkdir()

    await asyncio.gather(asyncio.create_task(thread_bot()))

    return 0

def main() -> int:  # noqa: D103
    asyncio.run(async_main())
    return 0
