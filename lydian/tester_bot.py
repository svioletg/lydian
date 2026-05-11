"""A second bot used solely for testing Lydian during development."""
import asyncio
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

from lydian.config import config
from lydian.const import LOGS_DIR, debug_context, setup_logger

load_dotenv('.env')

intents = discord.Intents.default()
intents.message_content = True

testbot = commands.Bot(intents=intents, command_prefix=',')

@testbot.event
async def on_ready() -> None:  # noqa: D103
    logger.info(f'Test bot logged in as {testbot.user}')

TEST_PLAY_LINKS_SINGLE: list[str] = [
    'https://thecaretaker.bandcamp.com/track/a1-its-just-a-burning-memory',
    'https://thecaretaker.bandcamp.com/track/a2-we-dont-have-many-days',
    'https://thecaretaker.bandcamp.com/track/a3-late-afternoon-drifting',
    'https://thecaretaker.bandcamp.com/track/a4-childishly-fresh-eyes',
    'https://thecaretaker.bandcamp.com/track/a5-slightly-bewildered',
]

TEST_PLAY_LINKS_MULTI: list[tuple[str, int]] = [
    ('https://tobyfox.bandcamp.com/album/undertale-demo-ost', 16),
    ('https://tobyfox.bandcamp.com/album/deltarune-chapters-3-4-ost', 78),
    ('https://thecaretaker.bandcamp.com/album/an-empty-bliss-beyond-this-world', 15),
]

class Commands(commands.Cog):  # noqa: D101
    def __init__(self, bot: discord.client.Bot) -> None:
        self.bot: discord.client.Bot = bot

    @commands.command()
    async def ping(self, ctx: commands.Context) -> None:
        """Sends a test message."""
        await ctx.send('Ping!')

    @commands.command()
    async def start(self, ctx: commands.Context) -> None:
        """Begins the main test suite."""
        pre: str = config.prefix
        await ctx.send(f'{pre}sendinfo')

async def async_main() -> None:  # noqa: D103
    async with testbot:
        await testbot.add_cog(Commands(testbot))

        debug_context['testbot'] = testbot
        # os.environ.get('LYDIAN_TESTBOT_TOKEN', '') would raise an exception about an improper token,
        # which is correct, but doing this would instead raise a KeyError which makes the root cause
        # of "you don't have a test bot token set" more apparent
        await testbot.start(os.environ['LYDIAN_TESTBOT_TOKEN'])

def main() -> None:  # noqa: D103
    setup_logger(stdout_level='DEBUG', logs_dir=LOGS_DIR, log_in_utc=False)
    logger.info('Test bot starting...')
    asyncio.run(async_main())

if __name__ == '__main__':
    sys.exit(main())
