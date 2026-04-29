"""Voice-related commands."""
import asyncio
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Self, cast

import discord
import yt_dlp
from discord.ext import commands
from loguru import logger
from maybetype import maybe

from lydian.cogs.util import embed_info, embed_ok
from lydian.config import config
from lydian.const import DL_DIR, YTDL_DOWNLOAD_PROGRESS_REGEX, EmojiStr
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
    thumbnail_url: str | None = None

    @classmethod
    def from_ytdl_extracted(cls, info: dict[str, Any]) -> Self:
        """Returns a ``MediaItem`` created from the dictionary returned by ``yt_dlp.YoutubeDL.extract_info``."""
        return cls(
            title=info['title'],
            url=info['original_url'],
            thumbnail_url=info.get('thumbnail'),
        )

class MediaQueue(deque[MediaItem]):
    """Queue for keeping track of what media is playing or to be played."""

    def __init__(self, *, maxlen: int | None = None) -> None:
        super().__init__(maxlen=maxlen)

def _assert_voice_client(vc: discord.VoiceProtocol | None) -> discord.VoiceClient:
    """Returns a ``discord.VoiceProtocol | None`` value casted to ``discord.VoiceClient``.

    If ``vc`` is ``None`` or not a ``discord.VoiceClient``, a ``TypeError`` is raised.
    """
    return cast('discord.VoiceClient', maybe(vc) \
        .filter(lambda x: isinstance(x, discord.VoiceClient)) \
        .unwrap(TypeError(f'expected VoiceClient instance: {vc!r}')))

class VoiceCog(commands.Cog):
    """Voice-related commands."""

    def __init__(self, bot: discord.client.Bot) -> None:
        self.bot: discord.client.Bot = bot
        self.queue = MediaQueue(maxlen=config.max_queue_length)
        self.can_advance: bool = True
        """Whether the queue is allowed to be advanced right now. Used as a lock for :py:meth:`advance_queue`."""
        self.now_playing: MediaItem | None = None
        """The :py:class:`MediaItem`, if any, that is currently being played by the bot."""

    async def advance_queue(self, ctx: commands.Context, *, exc: Exception | None = None) -> None:
        """Plays the next item in the queue.

        Returns immediately if the queue is empty.
        If the bot is paused or playing audio, it will be stopped and the current media is skipped.

        .. important::
            It is assumed that the bot is connected voice when calling this method, otherwise ``TypeError`` will be
            raised. If whether there is a connection is not reasonably guaranteed, the check should happen before
            calling this.

        :param ctx: A ``discord.ext.commands.Context`` object, needed to send messages.
        :param exc: Any ``Exception`` passed to the function by the ``discord.VoiceClient``'s ``.play()`` method.
            If an exception is given, it is raised immediately the queue is not advanced.
        """
        if exc:
            raise exc

        if not self.can_advance:
            return

        if not self.queue:
            if self.now_playing:
                self.now_playing = None
                logger.info('Media queue has emptied out')
            return

        self.can_advance = False

        try:
            voice = _assert_voice_client(ctx.voice_client)

            if voice.is_playing() or voice.is_paused():
                voice.stop()
                self.now_playing = None

            item = self.queue.popleft()

            logger.debug(f'Getting YTDLSource from: {item.url}')
            source = await YTDLSource.from_url(item.url)

            logger.info(f'Playing: {item}')
            voice.play(source, after=lambda e: asyncio.run(self.advance_queue(ctx, exc=e)))
            self.now_playing = item

            await ctx.send(embed=discord.Embed(
                title=f'{EmojiStr.PLAY} Playing: {item.title}',
                description=item.url,
            ).set_thumbnail(url=item.thumbnail_url))
        finally:
            # Make sure to release the queue lock
            self.can_advance = True

    #region COMMANDS

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

        # Treat this as a "resume" command if no URL is given
        if not url:
            if voice.is_paused():
                logger.info('Resuming paused player')
                voice.resume()
                return
            await ctx.send(embed=embed_info('The player is not paused.'))
            return

        # Otherwise, make sure it *is* a URL
        # We're preventing plain text YouTube searches for now, but it'll be implemented later
        if not re.match(r'https?://', url):
            logger.info(f'Invalid URL: {url}')
            await ctx.send(embed=embed_info('URL must start with `http://` or `https://`.'))
            return

        logger.info(f'Extracting info from URL: {url}')
        progress_msg: discord.Message = await ctx.send(embed=embed_info('Getting media info...', url))

        info: dict[str, Any] = await asyncio.get_event_loop().run_in_executor(None,
            lambda: ytdl.extract_info(url, download=False))

        self.queue.append(item := MediaItem.from_ytdl_extracted(info))

        # Start running the queue if nothing is playing, otherwise add this onto the queue
        if not self.now_playing:
            await progress_msg.delete()
            await self.advance_queue(ctx)
        else:
            logger.debug(f'Appended to media queue: {item}')
            await progress_msg.edit(embed=embed_ok(f'Queued at position #{len(self.queue)}: {item.title}', item.url))

    @commands.command(aliases=config.command_aliases.get('pause', ()))
    async def pause(self, ctx: commands.Context) -> None:
        """Pauses the currently playing media."""
        voice = _assert_voice_client(ctx.voice_client)

        if not voice.is_playing():
            await ctx.send(embed=embed_info('Nothing is playing.'))
            return

        logger.info('Pausing player')
        voice.pause()

    @commands.command(aliases=config.command_aliases.get('skip', ()))
    async def skip(self, ctx: commands.Context) -> None:
        """Skips the currently playing media."""
        await self.advance_queue(ctx)

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

    @commands.command('queue', aliases=config.command_aliases.get('queue', ()))
    async def show_queue(self, ctx: commands.Context) -> None:
        """Shows the queue."""
        if not self.queue:
            await ctx.send(embed=embed_info('Queue is empty.'))

        queue_embed = discord.Embed(title='Queue', description=f'{len(self.queue)} items')
        for n, item in enumerate(self.queue, start=1):
            queue_embed.add_field(name=f'#{n}. {item.title}', value=item.url, inline=False)

        await ctx.send(embed=queue_embed)

    @commands.command(aliases=config.command_aliases.get('clear', ()))
    async def clear(self, ctx: commands.Context) -> None:
        """Clears the queue."""
        self.queue.clear()
        await ctx.send(embed=embed_ok('Cleared the queue.'))

    #endregion COMMANDS

    #region HOOKS

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
    @skip.before_invoke
    @stop.before_invoke
    async def require_connection(self, ctx: commands.Context) -> None:
        """Prevents execution of the command if the author is not connected to the same voice channel as the bot.

        This hook does not need to be used for commands which already use the :py:meth:`auto_join` hook, since that
        will join and ensure a connection.
        """
        if not isinstance(ctx.author, discord.Member):
            raise AbortCommand

        if (ctx.voice_client is None) or (ctx.voice_client.channel is None):
            await ctx.send(embed=embed_info('Not connected to a voice channel.'))
            raise AbortCommand

        if (not ctx.author.voice) or (ctx.author.voice.channel != ctx.voice_client.channel):
            await ctx.send(embed=embed_info('You must be connected to the same voice channel as the bot.'))
            raise AbortCommand

    #endregion HOOKS
