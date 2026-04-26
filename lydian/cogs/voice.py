"""Voice-related commands."""
import asyncio
from typing import Self, cast

import discord
import yt_dlp
from discord.ext import commands
from loguru import logger

from lydian.cogs.util import embed_info
from lydian.config import config
from lydian.const import DL_DIR

ytdl_format_options = {
    'format': 'bestaudio/best',
    'paths': {'home': str(DL_DIR)},
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'max_filesize': config.max_filesize,
}

ytdl = yt_dlp.YoutubeDL()

class YTDLSource(discord.PCMVolumeTransformer):
    """A ``YoutubeDL``-based audio source to use in voice channels."""

    def __init__(self, source: discord.AudioSource, *, data: dict[str, str], volume: float = 0.5) -> None:
        super().__init__(source, volume)

        self.data: dict[str, str] = data
        self.title: str | None = data.get('title')
        self.url: str | None = data.get('url')

    @classmethod
    async def from_url(cls, url: str, *, loop: asyncio.AbstractEventLoop | None = None, stream: bool = False) -> Self:
        """Creates a ``YTDLSource`` from a URL."""
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename: str = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, options='-vn'), data=data)

class VoiceCog(commands.Cog):
    """Voice-related commands."""

    def __init__(self, bot: discord.client.Bot) -> None:
        self.bot: discord.client.Bot = bot

    @commands.command(aliases=config.command_aliases.get('join', ()))
    async def join(self, ctx: commands.Context) -> None:
        """Joins the current voice channel."""
        if not isinstance(ctx.author, discord.Member):
            return

        if (not ctx.author.voice) or (not ctx.author.voice.channel):
            await ctx.send(embed=embed_info('You must be connected to a voice channel.'))
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            logger.info(f'Moving from voice channel "{ctx.voice_client.channel}" to "{channel}"')
            await cast('discord.VoiceClient', ctx.voice_client).move_to(channel)
            return

        logger.info(f'Joining voice channel: {channel}')
        await channel.connect()

    @commands.command(aliases=config.command_aliases.get('leave', ()))
    async def leave(self, ctx: commands.Context) -> None:
        """Leaves the current voice channel."""
        if not isinstance(ctx.author, discord.Member):
            return

        if (ctx.voice_client is None) or (ctx.voice_client.channel is None):
            await ctx.send(embed=embed_info('Not connected to a voice channel.'))
            return

        if (not ctx.author.voice) or (ctx.author.voice.channel != ctx.voice_client.channel):
            await ctx.send(embed=embed_info('You must be connected to the same voice channel as the bot.'))
            return

        logger.info(f'Leaving voice channel: {ctx.voice_client.channel}')
        await cast('discord.VoiceClient', ctx.voice_client).disconnect()
