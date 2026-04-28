"""Voice-related commands."""
import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any, Self, cast, override

import discord
import yt_dlp
from discord.ext import commands
from loguru import logger
from maybetype import maybe

from lydian.cogs.util import embed_info
from lydian.config import config
from lydian.const import DL_DIR, YTDL_DOWNLOAD_PROGRESS_REGEX
from lydian.errors import AbortCommand


class YTDLLogHandler:
    """Basic class implementing ``debug``, ``info``, and ``warning`` methods to handle YoutubeDL logging.

    YoutubeDL logs both "debug" and "info" level messages using the ``debug`` method of its logger, this class allows
    distinguishing between the two properly and instead calling the appropriate ``loguru.Logger`` methods.
    """

    def debug(self, msg: str) -> None:  # noqa: D102
        if msg.startswith('[debug]'):
            logger.debug('[YoutubeDL] ' + msg)
        else:
            self.info(msg)

    def info(self, msg: str) -> None:  # noqa: D102
        if YTDL_DOWNLOAD_PROGRESS_REGEX.search(msg):
            return
        logger.info('[YoutubeDL] ' + msg)

    def warning(self, msg: str) -> None:  # noqa: D102
        logger.warning('[YoutubeDL] ' + msg)

YTDL_FORMAT_OPTIONS: dict[str, Any] = {
    'logger': YTDLLogHandler(),
    'format': 'bestaudio/best',
    'paths': {'home': str(DL_DIR)},
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'auto',
    'max_filesize': config.max_filesize,
}

ytdl = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)

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
        data: dict[str, Any] = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename: str = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, options='-vn'), data=data)

@dataclass
class MediaItem:
    """Represents a media item in the bot's queue."""

    title: str
    url: str

class MediaQueue(deque[MediaItem]):
    """Queue for keeping track of what media is playing or to be played."""

    def __init__(self, *, maxlen: int | None = None) -> None:
        super().__init__(maxlen=maxlen)
        self.locked: bool = False

    @override
    def append(self, x: MediaItem) -> None:
        self.locked = True
        super().append(x)
        self.locked = False

def _assert_voice_client(vc: discord.VoiceProtocol | None) -> discord.VoiceClient:
    """Returns a ``discord.VoiceProtocol | None`` value casted to ``discord.VoiceClient``.

    If ``vc`` is ``None`` or not a ``discord.VoiceClient``, a ``ValueError`` is raised.
    """
    return cast('discord.VoiceClient', maybe(vc) \
        .filter(lambda x: isinstance(x, discord.VoiceClient)) \
        .unwrap(f'expected VoiceClient instance: {vc!r}'))

class VoiceCog(commands.Cog):
    """Voice-related commands."""

    def __init__(self, bot: discord.client.Bot) -> None:
        self.bot: discord.client.Bot = bot
        self.queue = MediaQueue(maxlen=config.max_queue_length)

    @commands.command(aliases=config.command_aliases.get('join', ()))
    async def join(self, ctx: commands.Context) -> None:
        """Joins the current voice channel."""
        # The auto_join hook covers this

    @commands.command(aliases=config.command_aliases.get('leave', ()))
    async def leave(self, ctx: commands.Context) -> None:
        """Leaves the current voice channel."""
        voice = _assert_voice_client(ctx.voice_client)

        logger.info(f'Leaving voice channel: {voice.channel}')
        await voice.disconnect()

    @commands.command(aliases=config.command_aliases.get('play', ()))
    async def play(self, ctx: commands.Context, url: str | None = None) -> None:
        """Plays media, adds media to the queue, or resumes the player if paused.

        If the player is paused, the command can be used without any arguments to resume it.
        """
        voice = _assert_voice_client(ctx.voice_client)

        if not url:
            if voice.is_paused():
                logger.info('Resuming paused player')
                voice.resume()
                return
            await ctx.send(embed=embed_info('The player is not paused.'))
            return

        logger.info(f'Extracting info from URL: {url}')
        progress_msg: discord.Message = await ctx.send(embed=embed_info('Getting media info...', url))

        source = await YTDLSource.from_url(url)
        await progress_msg.edit(embed=embed_info(''))

        logger.info('Starting player')
        voice.play(source, signal_type='music')

        await ctx.send('Playing...')

    @commands.command(aliases=config.command_aliases.get('pause', ()))
    async def pause(self, ctx: commands.Context) -> None:
        """Pauses the currently playing media."""
        voice = _assert_voice_client(ctx.voice_client)

        if not voice.is_playing():
            await ctx.send(embed=embed_info('Nothing is playing.'))
            return

        logger.info('Pausing player')
        voice.pause()

    @commands.command(aliases=config.command_aliases.get('stop', ()))
    async def stop(self, ctx: commands.Context) -> None:
        """Stops the currently playing media.

        If ``-play`` is used after this command and the queue has not been cleared yet, it will play the stopped media
        from the beginning.
        """
        voice = _assert_voice_client(ctx.voice_client)

        if (not voice.is_playing()) and (not voice.is_paused()):
            await ctx.send(embed=embed_info('Nothing is playing.'))
            return

        logger.info('Stopping player')
        voice.stop()

    @join.before_invoke
    @play.before_invoke
    async def auto_join(self, ctx: commands.Context) -> None:
        """Automatically joins or moves to the author's current channel."""
        if not isinstance(ctx.author, discord.Member):
            return

        if (not ctx.author.voice) or (not ctx.author.voice.channel):
            await ctx.send(embed=embed_info('You must be connected to a voice channel.'))
            raise AbortCommand

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            if ctx.voice_client.channel == channel:
                return
            logger.info(f'Moving from voice channel "{ctx.voice_client.channel}" to "{channel}"')
            await cast('discord.VoiceClient', ctx.voice_client).move_to(channel)
            return

        logger.info(f'Joining voice channel: {channel}')
        await channel.connect()

    @leave.before_invoke
    @stop.before_invoke
    async def require_connection(self, ctx: commands.Context) -> None:
        """Cancels execution of the command if the author is not connected to the same voice channel as the bot."""
        if not isinstance(ctx.author, discord.Member):
            raise AbortCommand

        if (ctx.voice_client is None) or (ctx.voice_client.channel is None):
            await ctx.send(embed=embed_info('Not connected to a voice channel.'))
            raise AbortCommand

        if (not ctx.author.voice) or (ctx.author.voice.channel != ctx.voice_client.channel):
            await ctx.send(embed=embed_info('You must be connected to the same voice channel as the bot.'))
            raise AbortCommand
