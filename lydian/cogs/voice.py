"""Voice-related commands."""
import asyncio
import re
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import timedelta
from math import ceil
from typing import Any, ClassVar, Self, cast, override

import discord
import yt_dlp
from discord.ext import commands
from loguru import logger
from maybetype import maybe
from yt_dlp.utils import DownloadError

from lydian.cogs.util import alias_from_config, confirm, embed_error, embed_info, embed_ok
from lydian.config import config
from lydian.const import COLOR_ESCAPE_REGEX, COLOR_INFO, DL_DIR, YTDL_DOWNLOAD_PROGRESS_REGEX, EmojiStr
from lydian.errors import AbortCommand, MediaQueueLimitError
from lydian.util import BasicLock, Cache, format_duration, plural

EV_PLAYER_STOPPED_BY_COMMAND = asyncio.Event()
"""Set and cleared right after when the voice client's ``.stop()`` method is called from ``-stop``."""

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

    def error(self, msg: str) -> None:  # noqa: D102
        logger.error('[YoutubeDL]', msg)

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
    'extract_flat': 'in_playlist',
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
        """Creates a ``YTDLSource`` from a URL.

        :raises DownloadError:
            The URL could not be downloaded, e.g. the request returned a 404 error.
        """
        loop = loop or asyncio.get_event_loop()
        data: dict[str, Any] = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename: str = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, options='-vn'), data=data)

@dataclass
class MediaItem:
    """Represents a media item in the bot's queue."""

    _url_info_cache: ClassVar[Cache[str, dict[str, Any]]] = Cache(timedelta(hours=1))
    """Cache for storing URLs to yt-dlp-extracted info dictionaries."""

    title: str
    url: str
    """The web URL this item originated from (not the one being used for streaming)."""
    duration: float | None = None
    """The item's duration in seconds."""
    thumbnail_url: str | None = None

    @property
    def duration_str(self) -> str | None:
        """Return a formatted string of the duration if present."""
        if not self.duration:
            return None
        return format_duration(ceil(self.duration))

    def __copy__(self) -> Self:
        """Returns a new ``MediaItem`` with this instance's field values."""
        return self.__class__(**asdict(self))

    @classmethod
    def from_ytdl_extracted(cls, info: dict[str, Any]) -> Self:
        """Returns a ``MediaItem`` created from the dictionary returned by ``yt_dlp.YoutubeDL.extract_info``."""
        if 'entries' in info:
            # Take first entry of multiple until proper playlist limit is implemented
            info = info['entries'][0]

        return cls(
            title=info['title'],
            url=info.get('original_url', info['url']),
            duration=info.get('duration'),
            thumbnail_url=info.get('thumbnail'),
        )

    @classmethod
    def from_url(cls, url: str, *, cache: bool = True) -> tuple[Self, ...]:
        """Returns a tuple of ``MediaItem`` objects created from the info extracted from ``url`` by yt-dlp.

        If multiple entries are extracted from ``url``, the resulting ``MediaItem`` objects will only have the
        ``title`` and ``url`` fields filled.

        :param cache: If ``True``, cached info will be used instead of requesting the information for ``url`` again if
            the URL exists in the cache and is not expired, otherwise the result of this extraction will be cached.
            If ``False``, the cache is not used.
        """
        info: dict[str, Any] = cls._url_info_cache.get_or_set(url, lambda: ytdl.extract_info(url, download=False)) \
            if cache \
            else ytdl.extract_info(url, download=False)
        return tuple(
            cls.from_ytdl_extracted(cached) \
                if cache and (cached := cls._url_info_cache.get(entry.get('original_url', entry['url']))) \
                else cls.from_ytdl_extracted(entry) \
            for entry in info.get('entries', [info])
        )

    def copy(self) -> Self:
        """Returns a new ``MediaItem`` with this instance's field values."""
        return self.__copy__()

    def embed(self, title_prefix: str = '') -> discord.Embed:
        """Returns a ``discord.Embed`` for this item."""
        return discord.Embed(
            title=title_prefix + self.title,
            description=(f'({self.duration_str}) ' if self.duration else '') + self.url,
            color=COLOR_INFO,
        ).set_thumbnail(url=self.thumbnail_url)

    def refresh_copy(self, *, store_cache: bool = True) -> Self:
        """Re-extracts information from this object's ``url`` and returns a new instance from it.

        If the extracted information has multiple entries, the first entry is used.

        :param store_cache: Whether to store the resulting extracted information into the cache. Note that the cache is
            not used to retrieve any information for this method, it will *always* make a request.
        """
        new_info: dict[str, Any] = ytdl.extract_info(self.url, download=False)
        new_info = new_info.get('entries', [new_info])[0]

        if store_cache:
            self._url_info_cache.set(self.url, new_info)

        return self.from_ytdl_extracted(new_info)

    def refresh(self, *, store_cache: bool = True) -> Self:
        """Re-extracts information from this object's ``url`` and updates fields with the info accordingly.

        Returns a reference to this object.
        If the extracted information has multiple entries, the first entry is used.

        :param store_cache: Whether to store the resulting extracted information into the cache. Note that the cache is
            not used to retrieve any information for this method, it will *always* make a request.
        """
        for k, v in asdict(self.refresh_copy(store_cache=store_cache)).items():
            setattr(self, k, v)

        return self

class MediaQueue(deque[MediaItem]):
    """Queue for keeping track of what media is playing or to be played.

    The ``maxlen`` argument is strict, :py:class:`MediaQueueLimitError` will be raised if trying to append to or extend
    the queue would exceed its limit.
    """

    def __init__(self, *, maxlen: int | None = None) -> None:
        if maxlen == 0:
            # This just makes it easier to check "self.maxlen" instead of "self.maxlen is not None"
            raise ValueError('MediaQueue maxlen cannot be 0')
        super().__init__(maxlen=maxlen)

    @override
    def append(self, x: MediaItem) -> None:
        if self.maxlen and (len(self) >= self.maxlen):
            raise MediaQueueLimitError('Cannot append to full MediaQueue')
        super().append(x)

    @override
    def appendleft(self, x: MediaItem) -> None:
        if self.maxlen and (len(self) >= self.maxlen):
            raise MediaQueueLimitError('Cannot append to full MediaQueue')
        super().appendleft(x)

    @override
    def extend(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the right side of the deque with elements from the iterable.

        .. note::
            ``iterable`` will consumed so the length can be checked.
        """
        sequence: Sequence[MediaItem] = list(iterable)
        if self.maxlen and ((len(self) + len(sequence)) > self.maxlen):
                raise MediaQueueLimitError('Cannot extend MediaQueue, length of iterable would exceed limit')
        super().extend(sequence)

    def extend_max(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the right side of the deque with elements from the iterable until ``maxlen`` is reached."""
        try:
            for i in iterable:
                self.append(i)
        except MediaQueueLimitError:
            pass

    @override
    def extendleft(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the left side of the deque with elements from the iterable.

        .. note::
            ``iterable`` will consumed so the length can be checked.
        """
        sequence: Sequence[MediaItem] = list(iterable)
        if self.maxlen and ((len(self) + len(sequence)) > self.maxlen):
                raise MediaQueueLimitError('Cannot extend MediaQueue, length of iterable would exceed limit')
        super().extendleft(sequence)

    def extendleft_max(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the left side of the deque with elements from the iterable until ``maxlen`` is reached."""
        try:
            for i in iterable:
                self.appendleft(i)
        except MediaQueueLimitError:
            pass

    @override
    def insert(self, i: int, x: MediaItem) -> None:
        if self.maxlen and (len(self) >= self.maxlen):
            raise MediaQueueLimitError('Cannot insert into full MediaQueue')
        super().insert(i, x)

def _assert_voice_client(vc: discord.VoiceProtocol | None) -> discord.VoiceClient:
    """Returns a ``discord.VoiceProtocol | None`` value casted to ``discord.VoiceClient``.

    If ``vc`` is ``None`` or not a ``discord.VoiceClient``, a ``TypeError`` is raised.
    """
    return cast('discord.VoiceClient', maybe(vc) \
        .filter(lambda x: isinstance(x, discord.VoiceClient)) \
        .unwrap(TypeError(f'Expected VoiceClient instance: {vc!r}')))

class VoiceCog(commands.Cog):
    """Voice-related commands."""

    def __init__(self, bot: discord.client.Bot) -> None:
        self.bot: discord.client.Bot = bot
        self.queue = MediaQueue(maxlen=config.max_queue_length)
        self.queue_advance_lock = BasicLock('QueueAdvanceLock')
        """Whether the queue is allowed to be advanced right now. Used as a lock for :py:meth:`advance_queue`."""
        self.now_playing: MediaItem | None = None
        """The :py:class:`MediaItem`, if any, that is currently being played by the bot."""
        self.stopped_track: MediaItem | None = None
        """Stores the currently playing track when ``-stop`` is used.

        Set back to ``None`` when the track is played again.
        """

        self._manual_stop: bool = False

    async def advance_queue(self, ctx: commands.Context, *, play_now: MediaItem | None = None) -> None:
        """Plays the next item in the queue.

        Returns immediately if the queue is empty.
        If the bot is paused or playing audio, it will be stopped and the current media is skipped.

        .. important::
            It is assumed that the bot is connected voice when calling this method, otherwise ``TypeError`` will be
            raised. If whether there is a connection is not reasonably guaranteed, the check should happen before
            calling this.

        :param ctx: A ``discord.ext.commands.Context`` object, needed to send messages.
        :param play_now: A ``MediaItem`` to play right now instead of the next item in the queue.
        """
        if self.queue_advance_lock:
            return

        with self.queue_advance_lock:
            voice = _assert_voice_client(ctx.voice_client)

            if voice.is_playing() or voice.is_paused():
                voice.stop()

            if (not self.queue) and (not play_now):
                return

            item = play_now or self.queue.popleft()

            if (not item.duration) or (item.thumbnail_url):
                item.refresh()

            logger.debug(f'Getting YTDLSource from: {item.url}')
            progress_msg: discord.Message = await ctx.send(embed=embed_info('Downloading...'))
            source = await YTDLSource.from_url(item.url)
            await progress_msg.delete()

            logger.info(f'Playing: {item}')
            voice.play(source, after=lambda e: self.on_player_stop(ctx, exc=e))
            self.now_playing = item

            await ctx.send(embed=item.embed(f'{EmojiStr.PLAY} Playing: '))

    def on_player_stop(self, ctx: commands.Context, exc: Exception | None) -> None:
        """Callback for the voice client's ``.play()`` method ``after`` callback.

        :param exc: An exception raised during playback which caused the player to halt, if any.
        """
        self.now_playing = None

        if exc:
            logger.error(f'An exception interrupted the player: {exc}')
            raise exc

        if not self._manual_stop:
            self._manual_stop = False
            asyncio.run_coroutine_threadsafe(self.advance_queue(ctx), self.bot.loop).result()
        else:
            self._manual_stop = False

    def stop_player(self, voice: discord.VoiceClient) -> None:
        """Stops the player if it is playing media.

        This method should generally be used instead of directly calling ``.stop()`` on the voice client so the manual
        stop flag can be set. The flag will be unset by :py:meth:`on_player_stop`.
        """
        if self.now_playing:
            # The stopped track will be played from the beginning if -play is used after -stop
            self.stopped_track = self.now_playing
            self.now_playing = None

        self._manual_stop = True
        voice.stop()

    #region COMMANDS

    @alias_from_config
    @commands.command(aliases=[])
    async def join(self, ctx: commands.Context) -> None:
        """Joins the current voice channel."""
        # The auto_join hook covers this

    @alias_from_config
    @commands.command(aliases=[])
    async def leave(self, ctx: commands.Context) -> None:
        """Leaves the current voice channel."""
        voice = _assert_voice_client(ctx.voice_client)

        logger.info(f'Leaving voice channel: {voice.channel}')
        with self.queue_advance_lock:
            self.stop_player(voice)
            await voice.disconnect()

    @alias_from_config
    @commands.command(aliases=[])
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Shows the currently playing track."""
        if self.now_playing:
            await ctx.send(embed=self.now_playing.embed(f'{EmojiStr.PLAY} Playing: '))
        else:
            await ctx.send(embed=embed_info('Nothing is playing.'))

    @alias_from_config
    @commands.command(aliases=[])
    # TODO(svioletg): Once this is merged up into dev, deal with C901 and PLR0911  # noqa: TD003
    async def play(self, ctx: commands.Context, url: str | None = None) -> None:  # noqa: C901, PLR0911
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
            if (not voice.is_playing()) and self.stopped_track:
                # Start running the queue again if stopped
                await self.advance_queue(ctx, play_now=self.stopped_track)
                self.stopped_track = None
                return
            await ctx.send(embed=embed_info('The player is not paused.', 'Use `-play <URL>` to queue something up.'))
            return

        if len(self.queue) == self.queue.maxlen:
            await ctx.send(embed=embed_info('Queue is full.',
                f'Limit is currently set to {config.max_queue_length} entries.'))
            return

        # Otherwise, make sure it *is* a URL
        # We're preventing plain text YouTube searches for now, but it'll be implemented later
        if not re.match(r'https?://', url):
            logger.info(f'Got invalid URL: {url}')
            await ctx.send(embed=embed_info('URL must start with `http://` or `https://`.'))
            return

        logger.info(f'Extracting info from URL: {url}')
        progress_msg: discord.Message = await ctx.send(embed=embed_info('Getting media info...', url))

        try:
            items: tuple[MediaItem, ...] = await asyncio.get_event_loop().run_in_executor(None,
                lambda: MediaItem.from_url(url))
        except DownloadError as e:
            msg: str = COLOR_ESCAPE_REGEX.sub('', e.msg or '')
            logger.error(f'URL info extraction failed: {msg}')
            await progress_msg.edit(embed=embed_error('Failed to get URL information', f'{msg}'))
            return

        # Reject if the items won't fit in the queue
        if config.max_queue_length and (len(self.queue) + len(items) > config.max_queue_length):
            await progress_msg.edit(
                embed=embed_info('Playlist is too long to fit in the queue.', f'Limit: {config.max_queue_length}'),
            )
            return

        # If the playlist limit is exceeded, ask to add the max amount
        if config.max_playlist_length and (len(items) > config.max_playlist_length):
            can_add: bool | None = await confirm(ctx,
                embed_info(
                    f'Playlist is too long (limit of {config.max_playlist_length}).'
                    + f'\nAdd the first {config.max_playlist_length} items instead?',
                ),
                prompt_timeout=120.0,
            )
            match can_add:
                case True:
                    items = items[:config.max_playlist_length]
                case False:
                    await progress_msg.delete()
                    return
                case _:
                    await progress_msg.delete()
                    await ctx.send('Timed out.')
                    return

        self.queue.extend(items)

        logger.info(f'Added {len(items)} item(s) to the media queue')
        for i in items:
            logger.debug(f'Added to media queue: {i}')

        # Start running the queue if nothing is playing, otherwise add this onto the queue
        if not self.now_playing:
            await progress_msg.delete()
            await self.advance_queue(ctx)
        elif len(items) == 1:
            item = items[0]
            await progress_msg.edit(
                embed=embed_ok(f'{EmojiStr.IN} Queued at position #{len(self.queue)}: {item.title}', item.url),
            )
        else:
            end_pos: int = len(self.queue)
            start_pos: int = end_pos - len(items)
            await progress_msg.edit(
                embed=embed_ok(
                    f'{EmojiStr.IN} Queued {len(items)} items from position #{start_pos} to #{end_pos}',
                ),
            )

    @alias_from_config
    @commands.command(aliases=[])
    async def pause(self, ctx: commands.Context) -> None:
        """Pauses the currently playing media."""
        voice = _assert_voice_client(ctx.voice_client)

        if not voice.is_playing():
            await ctx.send(embed=embed_info('Nothing is playing.'))
            return

        logger.info('Pausing player')
        voice.pause()

    @alias_from_config
    @commands.command(aliases=[])
    async def remove(self, ctx: commands.Context, index: int) -> None:
        """Removes an item at the given index from the queue."""
        if not 1 <= index <= len(self.queue):
            await ctx.send(embed=embed_info('Queue index out of range.'))
            return

        self.queue.remove(item := self.queue[index - 1])
        await ctx.send(embed=embed_ok(f'{EmojiStr.OUT} Removed item from position #{index}: {item.title}', item.url))

    @alias_from_config
    @commands.command(aliases=[])
    async def skip(self, ctx: commands.Context) -> None:
        """Skips the currently playing media."""
        voice = _assert_voice_client(ctx.voice_client)

        if (not voice.is_paused()) and (not voice.is_playing()):
            if self.stopped_track:
                # Skip the stopped track
                self.stopped_track = None
            else:
                await ctx.send(embed=embed_info('Nothing to skip.'))

        await self.advance_queue(ctx)

    @alias_from_config
    @commands.command(aliases=[])
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
        self.stop_player(voice)

    @alias_from_config
    @commands.command('queue', aliases=[])
    async def show_queue(self, ctx: commands.Context) -> None:
        """Shows the queue."""
        queue_embed = discord.Embed(
            title='Queue',
            description=f'{len(self.queue)} {plural('item.s', len(self.queue))}',
            color=COLOR_INFO,
        )

        if self.now_playing:
            queue_embed.add_field(
                name=f'Now playing: {self.now_playing.title}',
                value=(f'({self.now_playing.duration_str}) ' if self.now_playing.duration else '') \
                    + self.now_playing.url,
                inline=False,
            )

        if self.stopped_track:
            queue_embed.add_field(
                name=f'Stopped: {self.stopped_track.title}',
                value=(f'({self.stopped_track.duration_str}) ' if self.stopped_track.duration else '') \
                    + self.stopped_track.url,
                inline=False,
            )

        for n, item in enumerate(self.queue, start=1):
            queue_embed.add_field(
                name=f'#{n}. {item.title}',
                value=(f'({item.duration_str}) ' if item.duration else '') + item.url,
                inline=False,
            )

        await ctx.send(embed=queue_embed)

    @alias_from_config
    @commands.command('clear', aliases=[])
    async def clear_queue(self, ctx: commands.Context) -> None:
        """Clears the queue."""
        self.queue.clear()
        await ctx.send(embed=embed_ok('Cleared the queue.'))

    #endregion COMMANDS

    #region COMMAND HOOKS

    @join.before_invoke
    @play.before_invoke
    async def auto_join(self, ctx: commands.Context) -> None:
        """Automatically joins or moves to the author's current channel."""
        if not isinstance(ctx.author, discord.Member):
            raise AbortCommand

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
    @pause.before_invoke
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

    #endregion COMMAND HOOKS
