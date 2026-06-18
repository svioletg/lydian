"""Voice-related commands."""
import asyncio
from collections import UserList
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from math import ceil
from pathlib import Path
from random import randint
from typing import Any, ClassVar, Literal, Self, cast, override

import discord
import yt_dlp
from discord.ext import commands, tasks
from loguru import logger
from maybetype import Err, Ok, Result, maybe
from yt_dlp.utils import DownloadError

from lydian.cogs.util import alias_from_config, confirm, embed_error, embed_info, embed_ok
from lydian.config import config
from lydian.const import (
    COLOR_ESCAPE_REGEX,
    DL_DIR,
    EMBED_COLOR_INFO,
    GH_ISSUES,
    QUEUE_MAX_PER_PAGE,
    YTDL_DOWNLOAD_PROGRESS_REGEX,
    EmojiStr,
)
from lydian.errors import AbortCommand, FileSizeLimitError, MediaQueueLimitError
from lydian.util import BasicLock, Cache, Stopwatch, expect, format_duration, mention


class YTDLLogHandler:
    """Basic class implementing ``debug``, ``info``, and ``warning`` methods to handle YoutubeDL logging.

    YoutubeDL logs both "debug" and "info" level messages using the ``debug`` method of its logger, this class allows
    distinguishing between the two properly and instead calling the appropriate ``loguru.Logger`` methods.
    """

    def debug(self, msg: str) -> None:  # noqa: D102
        if 'File is larger than max-filesize' in msg:
            raise FileSizeLimitError(msg.removeprefix('[download] '))
        if msg.startswith('[debug]'):
            logger.opt(depth=2).debug('[YoutubeDL] ' + msg)
        else:
            self.info(msg)

    def info(self, msg: str) -> None:  # noqa: D102
        if YTDL_DOWNLOAD_PROGRESS_REGEX.search(msg):
            return
        logger.opt(depth=2).info('[YoutubeDL] ' + msg)

    def warning(self, msg: str) -> None:  # noqa: D102
        logger.opt(depth=2).warning('[YoutubeDL] ' + msg)

    def error(self, msg: str) -> None:  # noqa: D102
        logger.opt(depth=2).error('[YoutubeDL]', msg)

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
    'allowed_extractors': config.media_filter.allowed_extractors,
}

ytdl = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    """A ``YoutubeDL``-based audio source to use in voice channels."""

    def __init__(self, source: discord.AudioSource, *, data: dict[str, str], volume: float = 0.5) -> None:
        super().__init__(source, volume)

        self.data: dict[str, str] = data
        self.title: str | None = data.get('title')
        self.url: str | None = data.get('url')
        self.file: Path = Path(ytdl.prepare_filename(data))

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

    # Non-media-related
    user_id: int | None = None
    """The ID of the Discord user who requested this item, if any."""

    def __str__(self) -> str:  # noqa: D105
        return f'MediaItem({self.title!r}, {self.url!r}, duration={self.duration!r})'

    @property
    def duration_str(self) -> str:
        """Return a formatted string of the duration, returning '?:??' if no duration is set."""
        return format_duration(ceil(self.duration)) if self.duration else '?:??'

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
    def from_url(cls, url: str, *, user: int | discord.Member | None = None, cache: bool = True) -> tuple[Self, ...]:
        """Returns a tuple of ``MediaItem`` objects created from the info extracted from ``url`` by yt-dlp.

        If multiple entries are extracted from ``url``, the resulting ``MediaItem`` objects will only have the
        ``title`` and ``url`` fields filled.

        :param user: A ``discord.Member`` object or a Discord user's ID to set as the ``user_id`` attribute for every
            returned item.
        :param cache: If ``True``, cached info will be used instead of requesting the information for ``url`` again if
            the URL exists in the cache and is not expired, otherwise the result of this extraction will be cached.
            If ``False``, the cache is not used.
        """
        if isinstance(user, discord.Member):
            user = user.id

        info: dict[str, Any] = cls._url_info_cache.get_or_set(url, lambda: ytdl.extract_info(url, download=False)) \
            if cache \
            else ytdl.extract_info(url, download=False)
        return tuple(
            cls.from_ytdl_extracted(cached).set_user(user) \
                if cache and (cached := cls._url_info_cache.get(entry.get('original_url', entry['url']))) \
                else cls.from_ytdl_extracted(entry).set_user(user) \
            for entry in info.get('entries', [info])
        )

    def add_embed_field(self, embed: discord.Embed, title_prefix: str = '', *, inline: bool = False) -> discord.Embed:
        """Adds this item as a field to a ``discord.Embed`` object, then returns it back."""
        return embed.add_field(
            name=f'{title_prefix}{self.title}',
            value=
                (f'Queued by {mention(self.user_id)}\n' if self.user_id else '')
                + (f'({self.duration_str}) ' if self.duration else '') + self.url,
            inline=inline,
        )

    def embed(self, title_prefix: str = '', *, timestamp: float | None = None) -> discord.Embed:
        """Returns a ``discord.Embed`` for this item.

        :param timestamp: The current timestamp of this track to show as relative to the duration.
        """
        timestamp_str: str | None = maybe(timestamp).then(format_duration)
        time_display: str = f'Time: {timestamp_str} / {self.duration_str}' \
            if timestamp_str else f'Duration: {self.duration_str}'
        return discord.Embed(
            title=title_prefix + self.title,
            description=
                (f'Queued by {mention(self.user_id)}\n' if self.user_id else '')
                + f'{time_display}\n'
                + self.url,
            color=EMBED_COLOR_INFO,
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

        return self.from_ytdl_extracted(new_info).set_user(self.user_id)

    def refresh(self, *, store_cache: bool = True) -> Self:
        """Re-extracts information from this object's ``url`` and updates fields with the info accordingly.

        Returns a reference to this object.
        If the extracted information has multiple entries, the first entry is used.

        :param store_cache: Whether to store the resulting extracted information into the cache. Note that the cache is
            not used to retrieve any information for this method, it will *always* make a request.
        """
        for k, v in self.refresh_copy(store_cache=store_cache).__dict__.items():
            setattr(self, k, v)

        return self

    def set_user(self, user: int | discord.User | None = None) -> Self:
        """Sets the ``user_id`` attribute and returns a reference to this instance.

        :param user: Either the user's ID, or a ``discord.User`` object to get the ID from.
        """
        if isinstance(user, discord.User):
            self.user_id = user.id
        else:
            self.user_id = user
        return self

class MediaQueue(UserList[MediaItem]):
    """Queue for keeping track of what media is playing or to be played.

    The ``maxlen`` argument is strict, :py:class:`MediaQueueLimitError` will be raised if trying to append to or extend
    the queue would exceed its limit.
    """

    def __init__(self, initlist: Sequence[MediaItem] | None = None, *, maxlen: int | None = None) -> None:
        if maxlen == 0:
            # This just makes it easier to check "self.maxlen" instead of "self.maxlen is not None"
            raise ValueError('MediaQueue maxlen cannot be 0')
        if initlist and maxlen and (len(initlist) > maxlen):
            raise ValueError(f'initlist is too large ({len(initlist)}) for MediaQueue with maxlen {maxlen}')
        self.maxlen: int | None = maxlen
        super().__init__(initlist=initlist)

    def __repr__(self) -> str:  # noqa: D105
        return f'{self.__class__.__name__}({self.data}, maxlen={self.maxlen})'

    @override
    def append(self, item: MediaItem) -> None:
        if self.maxlen and (len(self) >= self.maxlen):
            raise MediaQueueLimitError('Cannot append to full MediaQueue')
        super().append(item)

    @override
    def extend(self, other: Iterable[MediaItem]) -> None:
        """Extend the right side of the deque with elements from the iterable.

        .. note::
            ``iterable`` will consumed so the length can be checked.
        """
        sequence: Sequence[MediaItem] = list(other)
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

    def extendleft(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the left side of the deque with elements from the iterable.

        .. note::
            ``iterable`` will consumed so the length can be checked.
        """
        sequence: Sequence[MediaItem] = list(iterable)
        if self.maxlen and ((len(self) + len(sequence)) > self.maxlen):
                raise MediaQueueLimitError('Cannot extend MediaQueue, length of iterable would exceed limit')
        self.data = [*iterable, *self]

    def extendleft_max(self, iterable: Iterable[MediaItem]) -> None:
        """Extend the left side of the deque with elements from the iterable until ``maxlen`` is reached."""
        try:
            for i in iterable:
                self.insert(0, i)
        except MediaQueueLimitError:
            pass

    @override
    def insert(self, i: int, item: MediaItem) -> None:
        if self.maxlen and (len(self) >= self.maxlen):
            raise MediaQueueLimitError('Cannot insert into full MediaQueue')
        super().insert(i, item)

    def move(self, source: int, dest: int) -> None:
        """Moves an item at index ``source`` to index ``dest``."""
        if dest >= len(self):
            raise IndexError(f'dest is out of MediaQueue range: {dest}')
        self.insert(dest, self.pop(source))

    def popleft(self) -> MediaItem:
        """Pops the item at the front of the list."""
        return self.pop(0)

    def poprandom(self) -> MediaItem:
        """Pops a random item in the list and returns it."""
        return self.pop(randint(0, len(self) - 1))

@dataclass
class VoteSkip:
    """Dataclass for vote-skipping data."""

    threshold: int
    """How many users are needed to skip a track based on ``threshold_type``."""
    threshold_type: Literal['percentage', 'exact']
    """How to treat ``threshold``."""
    voted: set[int] = field(default_factory=set)
    """A set of user IDs who have voted to skip the current track."""

    def remaining(self, channel: discord.VoiceChannel | discord.StageChannel) -> int:
        """Returns how many more votes are needed to skip the current track.

        The returned value will not go below zero.
        """
        threshold: int = self.threshold
        if self.threshold_type == 'percentage':
            threshold = ceil((threshold / 100) * len(channel.members))

        return max(0, threshold - len(self.voted))

def _assert_discord_member(user: discord.User | discord.Member) -> discord.Member:
    """Returns a ``discord.User | discord.Member`` value casted to ``discord.Member``.

    Raises ``TypeError`` if ``user`` is not a ``discord.Member``.
    """
    if not isinstance(user, discord.Member):
        raise TypeError(f'Expected discord.Member instance: {user!r}')
    return user

def _assert_voice_client(vc: discord.VoiceProtocol | None) -> discord.VoiceClient:
    """Returns a ``discord.VoiceProtocol | None`` value casted to ``discord.VoiceClient``.

    If ``vc`` is ``None`` or not a ``discord.VoiceClient``, a ``TypeError`` is raised.
    """
    return cast('discord.VoiceClient', maybe(vc) \
        .filter(lambda x: isinstance(x, discord.VoiceClient)) \
        .unwrap(TypeError(f'Expected VoiceClient instance: {vc!r}')))

class VoiceCog(commands.Cog):
    """Voice-related commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

        # Media
        self.queue = MediaQueue(maxlen=config.max_queue_length)
        self.queue_advance_lock = BasicLock('QueueAdvanceLock')
        """Whether the queue is allowed to be advanced right now. Used as a lock for :py:meth:`advance_queue`."""
        self.now_playing: MediaItem | None = None
        """The :py:class:`MediaItem`, if any, that is currently being played by the bot."""
        self.now_playing_timer: Stopwatch = Stopwatch()
        self.stopped_track: MediaItem | None = None
        """Stores the currently playing track when ``-stop`` is used.

        Set back to ``None`` when the track is played again.
        """
        self.voteskip: VoteSkip | None = VoteSkip(
            config.vote_skipping.percentage
                if config.vote_skipping.threshold_type == 'percentage'
                else config.vote_skipping.exact,
            config.vote_skipping.threshold_type,
        ) if config.vote_skipping.enabled else None

        # States
        self.alone: bool = False
        """Whether the bot is the only user connected to a voice channel."""
        self.inactive: bool = False
        """Whether the bot is both not playing any media and the queue is empty.

        For this purpose, the bot being paused still counts as playing media. The bot connecting to a voice channel
        without having been in one previously will also set this to ``False``.
        """
        self.shuffle: bool = False
        """If ``True``, a random item is pulled from the queue instead of the next one when advancing."""
        self.loop: Literal['track', 'queue', False] = False
        """What looping mode the player is in, ``False`` if not looping."""

        # Timers/counters
        self.time_inactive: int = 0
        """An amount in seconds since the bot stopped playing audio and has had an empty queue."""
        self.time_alone: int = 0
        """An amount in seconds that the bot has been the only user in its voice channel."""

        # Internal
        self._manual_stop: bool = False
        self._play_calls: asyncio.Queue[tuple[commands.Context, str]] = asyncio.Queue()
        """Tuples of context objects and URLs that are waiting to be processed by :py:meth:`play`."""

        # Start tasks
        self.task_tick_timers.start()
        self.task_handle_play_requests.start()

    #region LISTENERS

    @commands.Cog.listener()
    async def on_voice_state_update(self,
            member: discord.Member,
            before: discord.VoiceState,
            after: discord.VoiceState,
        ) -> None:
        """Called when a member changes their ``VoiceState``."""
        if not self.bot.voice_clients:
            return
        bot_joined: bool = (member.id == expect(self.bot.user).id) \
            and (before.channel is None) \
            and (after.channel is not None)
        if bot_joined:
            self.inactive = False
        voice = _assert_voice_client(self.bot.voice_clients[0])
        self.alone = len(voice.channel.members) == 1

    #endregion LISTENERS

    #region TASKS

    @tasks.loop(seconds=1)
    async def task_tick_timers(self) -> None:
        """Handles increasing or resetting counters."""
        self.time_inactive += 1 if self.inactive else (-self.time_inactive)
        self.time_alone += 1 if self.alone else (-self.time_alone)

        if self.bot.voice_clients:
            voice = _assert_voice_client(self.bot.voice_clients[0])
            # Handle auto disconnect timers
            self.inactive = (not self.queue) and (not voice.is_playing()) and (not voice.is_paused())
            if (config.inactivity_timeout is not None) and self.time_inactive >= config.inactivity_timeout:
                logger.info(f'Bot has been inactive for {self.time_inactive} seconds; disconnecting')
                await voice.disconnect()
            elif (config.lonely_timeout is not None) and self.time_alone >= config.lonely_timeout:
                logger.info(f'Bot has been alone for {self.time_alone} seconds; disconnecting')
                await voice.disconnect()

    @tasks.loop(seconds=5)
    async def task_handle_play_requests(self) -> None:  # noqa: C901
        """Continuously checks for any queued calls to ``-play`` and handles them one at a time, in order."""
        if not self.bot.user:
            return
        first_loop: bool = True
        while True:
            if not first_loop:
                self._play_calls.task_done()
            ctx, url = await self._play_calls.get()
            first_loop = False
            if (remaining := self._play_calls.qsize()):
                logger.debug(f'{remaining} more queued call(s) after this')

            if len(self.queue) == self.queue.maxlen:
                await ctx.send(embed=embed_info('Queue is full.',
                    f'Limit is currently set to {config.max_queue_length} entries.'))
                continue

            # Filter URL
            if not config.filter_media_url(url):
                await ctx.send(embed=embed_info("This URL is not allowed by the bot's configuration."))
                continue

            logger.info(f'Extracting info from URL: {url}')
            progress_msg: discord.Message = await ctx.send(embed=embed_info('Getting media info...', url))

            result = await self._try_to_queue(ctx, url)
            if not result:
                await progress_msg.edit(embed=result.unwrap_err())
                continue

            items: tuple[MediaItem, ...] = result.unwrap()

            self.queue.extend(items)

            logger.info(f'Added {len(items)} item(s) to the media queue')
            for i in items:
                logger.debug(f'Added to media queue: {i}')

            # Start running the queue if nothing is playing
            just_started: bool = False
            if not self.now_playing:
                just_started = True
                skipped: int | None = await self.advance_queue(ctx)

            if (len(items) == 1) and not just_started:
                item = items[0]
                await progress_msg.edit(
                    embed=embed_ok(f'{EmojiStr.IN} Queued at position #{len(self.queue)}: {item.title}', item.url),
                )
            else:
                if just_started:
                    items = items[(skipped or 0) + 1:]
                if not items:
                    await progress_msg.delete()
                    continue
                end_pos: int = len(self.queue)
                start_pos: int = end_pos - len(items)
                await progress_msg.edit(
                    embed=embed_ok(
                        f'{EmojiStr.IN} Queued {len(items)} items from position #{start_pos + 1} to #{end_pos}',
                    ),
                )

    @task_tick_timers.error
    @task_handle_play_requests.error
    async def on_task_exception(self, exc: BaseException) -> Any:  # noqa: ANN401 ; error decorator expects Any return type
        """Handles unhandled exceptions raised in background tasks."""
        logger.opt(exception=exc).error('Unhandled exception in background task')
        logger.error('The task will need to be manually restarted. Use the "tasks list" command to find the failed'
            + ' task, then run "tasks start" followed by that task\'s ID to do so. If you continue to encounter this'
            + ' error, please check for existing bug reports and make a new one if needed (include the above'
            + f' traceback) at: {GH_ISSUES}')

    #endregion TASKS

    async def _resume_or_start(self, ctx: commands.Context, voice: discord.VoiceClient) -> None:
        if voice.is_paused():
            logger.info('Resuming paused player')
            voice.resume()
            self.now_playing_timer.unpause()
            return
        if (not voice.is_playing()) and self.stopped_track:
            # Start running the queue again if stopped
            await self.advance_queue(ctx, play_now=self.stopped_track)
            self.stopped_track = None
            return
        await ctx.send(embed=embed_info('The player is not paused.', 'Use `-play <URL>` to queue something up.'))

    async def _try_to_queue(self, ctx: commands.Context, url: str) -> Result[tuple[MediaItem, ...], discord.Embed]:  # noqa: PLR0911
        author = _assert_discord_member(ctx.author)

        try:
            items: tuple[MediaItem, ...] = await asyncio.get_event_loop().run_in_executor(None,
                lambda: MediaItem.from_url(url, user=author))
        except DownloadError as e:
            msg: str = COLOR_ESCAPE_REGEX.sub('', e.msg or '')
            logger.error(f'URL info extraction failed: {msg}')
            if 'No suitable extractor found for URL' in msg:
                return Err(embed_info("No suitable extractor found for this URL with the bot's current configuration."))
            else:
                return Err(embed_error('Failed to get URL information', f'From yt-dlp: {msg}'))

        # Check against the duration limit, if any
        if (len(items) == 1) and config.max_duration:
            item = items[0]
            if (item.duration is None) and not config.max_duration_allow_unknown:
                return Err(embed_info("Cannot queue; this media's duration is unknown",
                    'Allowing unknown durations is currently disabled'))
            elif (item.duration is not None) and item.duration > config.max_duration:
                return Err(embed_info('Media exceeds the duration limit',
                    f'{format_duration(item.duration)} > {format_duration(config.max_duration)}\n{item.url}'))

        # Reject if the items won't fit in the queue
        if config.max_queue_length and (len(self.queue) + len(items) > config.max_queue_length):
            return Err(embed_info('Playlist is too long to fit in the queue.', f'Limit: {config.max_queue_length}'))

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
                    return Err(embed_info('Cancelling.'))
                case _:
                    return Err(embed_info('Confirmation timed out; cancelling.'))

        return Ok(items)

    async def advance_queue(self, ctx: commands.Context, *, play_now: MediaItem | None = None) -> int | None:  # noqa: C901
        """Plays the next item in the queue, returning how many items had to be skipped or ``None`` if locked.

        If the queue is empty and ``play_now`` is ``None``, 0 is returned.
        If the bot is paused or playing audio, it will be stopped and the current media is skipped.
        If the queue item cannot be played (e.g. due to filesize or duration limit), the next item will be tried until
        either the player starts successfully or the queue is empty. The count of how many times this occurs is
        returned.

        .. important::
            It is assumed that the bot is connected voice when calling this method, otherwise ``TypeError`` will be
            raised. If whether there is a connection is not reasonably guaranteed, the check should happen before
            calling this.

        :param ctx: A ``discord.ext.commands.Context`` object, needed to send messages.
        :param play_now: A ``MediaItem`` to play right now instead of the next item in the queue.
        """
        if self.queue_advance_lock:
            return None

        progress_msg: discord.Message | None = None
        skipped: int = -1
        while True:
            skipped += 1
            with self.queue_advance_lock:
                voice = _assert_voice_client(ctx.voice_client)

                if voice.is_playing() or voice.is_paused():
                    voice.stop()

                if (not self.queue) and (not play_now):
                    return 0

                item = play_now or (self.queue.poprandom() if self.shuffle else self.queue.popleft())
                # Make sure play_now is consumed so it doesn't try to queue on the next loop
                play_now = None

                if progress_msg:
                    await progress_msg.edit(embed=embed_info('Getting media info...', item.url))
                else:
                    progress_msg = await ctx.send(embed=embed_info('Getting media info...', item.url))

                if (not item.duration) or (not item.thumbnail_url):
                    logger.debug(f'Refreshing MediaItem info: {item}')
                    item.refresh()

                # Check against the duration limit, if any
                if config.max_duration:
                    if (item.duration is None) and not config.max_duration_allow_unknown:
                        await ctx.send(embed=embed_info("Cannot queue; this media's duration is unknown",
                            f'Allowing unknown durations is currently disabled\n{item.url}'))
                        continue
                    if (item.duration is not None) and item.duration > config.max_duration:
                        await ctx.send(embed=embed_info('Media exceeds the duration limit',
                            f'{format_duration(item.duration)} > {format_duration(config.max_duration)}\n{item.url}'))
                        continue

                logger.debug(f'Getting YTDLSource from: {item.url}')
                await progress_msg.edit(embed=embed_info('Downloading...', item.url))

                try:
                    source = await YTDLSource.from_url(item.url, stream=config.stream_media)
                except FileSizeLimitError as e:
                    await progress_msg.edit(embed=embed_info('File is larger than the set filesize limit.'))
                    logger.info(e)
                    continue

                await progress_msg.delete()

                logger.info(f'Playing: {item}')
                voice.play(source, after=lambda e: self.on_player_stop(ctx, exc=e))
                self.now_playing = item
                self.now_playing_timer.reset()

                await self.nowplaying.invoke(ctx)

                break

        return skipped

    def loop_state_embed(self, description: str | None = None) -> discord.Embed:
        """Returns an embed describing the current ``self.loop`` state."""
        match self.loop:
            case 'track':
                return embed_info(f'{EmojiStr.LOOP} Looping the current track.', description)
            case 'queue':
                return embed_info(f'{EmojiStr.LOOP_ONE} Looping the queue.', description)
            case False:
                return embed_info('Not looping.', description)

    def on_player_stop(self, ctx: commands.Context, exc: Exception | None) -> None:
        """Callback for the voice client's ``.play()`` method ``after`` callback.

        :param exc: An exception raised during playback which caused the player to halt, if any.
        """
        logger.debug('Player has stopped')

        play_now: MediaItem | None = self.now_playing if self.loop == 'track' else None
        self.now_playing = None

        if exc:
            logger.error(f'An exception interrupted the player: {exc}')
            raise exc

        if not self._manual_stop:
            self._manual_stop = False
            asyncio.run_coroutine_threadsafe(self.advance_queue(ctx, play_now=play_now), self.bot.loop).result()
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
    async def join(self, _ctx: commands.Context) -> None:
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
            await ctx.send(embed=self.now_playing.embed(
                f'{f'{EmojiStr.SHUFFLE} ' if self.shuffle else ''}{EmojiStr.PLAY} Playing: ',
                timestamp=self.now_playing_timer.elapsed(),
            ))
        else:
            await ctx.send(embed=embed_info('Nothing is playing.'))

    @alias_from_config
    @commands.command(aliases=[])
    async def play(self, ctx: commands.Context, url: str | None = None) -> None:
        """Plays media, adds media to the queue, or resumes the player if paused.

        If the player is paused, the command can be used without any arguments to resume it.
        """
        voice = _assert_voice_client(ctx.voice_client)

        # Treat this as a "resume" command if no URL is given
        if not url:
            await self._resume_or_start(ctx, voice)
            return

        if self._play_calls.qsize():
            await ctx.send(embed=embed_info('Your play request is pending.'), ephemeral=True, delete_after=10)

        await self._play_calls.put((ctx, url))

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
        self.now_playing_timer.pause()

    async def _check_queue_index_arg(self, ctx: commands.Context, index: int) -> bool:
        if not 1 <= index <= len(self.queue):
            await ctx.send(embed=embed_info('Queue index out of range.'))
            return False
        return True

    @alias_from_config
    @commands.command(aliases=[])
    async def move(self, ctx: commands.Context,
            source: int = commands.parameter(displayed_name='from'),
            dest: int = commands.parameter(displayed_name='to'),
        ) -> None:
        """Moves an item to a new position in the queue.

        :param source: The queue index of the item you want to move.
        :param dest: The new index you want to move the item to.
        """
        if not (await self._check_queue_index_arg(ctx, source) and await self._check_queue_index_arg(ctx, dest)):
            return

        target = self.queue[source - 1]
        self.queue.move(source - 1, dest - 1)
        await ctx.send(embed=embed_info(f'Moved "{target.title}" from position #{source} to #{dest}'))

    @alias_from_config
    @commands.command(aliases=[])
    async def remove(self, ctx: commands.Context, index: int) -> None:
        """Removes an item at the given index from the queue."""
        if not await self._check_queue_index_arg(ctx, index):
            return

        self.queue.remove(item := self.queue[index - 1])
        await ctx.send(embed=embed_ok(f'{EmojiStr.OUT} Removed item from position #{index}: {item.title}', item.url))

    @alias_from_config
    @commands.command(aliases=[])
    async def skip(self, ctx: commands.Context) -> None:
        """Skips the currently playing media."""
        to_skip: MediaItem | None = self.now_playing or self.stopped_track

        if not to_skip:
            await ctx.send(embed=embed_info('Nothing to skip.'))
            return

        voice = _assert_voice_client(ctx.voice_client)

        if self.voteskip:
            if ctx.author.id in self.voteskip.voted:
                remaining: int = self.voteskip.remaining(voice.channel)
                await ctx.send(embed=embed_info(
                    'You have already voted to skip.',
                    f'{remaining} more vote(s) needed\nVoted: {', '.join(map(mention, self.voteskip.voted))}',
                ))
                return
            self.voteskip.voted.add(ctx.author.id)
            remaining: int = self.voteskip.remaining(voice.channel) \
                - int(any(expect(self.bot.user).id == m.id for m in voice.channel.members))
            await ctx.send(embed=embed_info(
                f'{_assert_discord_member(ctx.author).display_name} voted to skip this track.',
                f'{remaining} more vote(s) needed\nVoted: {', '.join(map(mention, self.voteskip.voted))}',
            ))
            if remaining > 0:
                return

        self.stopped_track = None

        await ctx.send(
            embed=embed_info(f'{EmojiStr.SKIP} Skipping...', f'*{to_skip.title}*\n{to_skip.url}'),
            delete_after=10,
        )
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
    @commands.command('loop', aliases=[])
    async def toggle_loop(self, ctx: commands.Context, state: Literal['track', 'queue', 'off'] | None = None) -> None:
        """Sets the looping state of the player.

        ``"track"`` loops the current track, ``"queue"`` loops the full queue, ``"off"`` disables looping.
        Giving no argument shows the current loop state.
        """
        if state is not None:
            self.loop = False if state == 'off' else state
            logger.info(f'Updated player loop state: {self.loop!r}')

        await ctx.send(embed=self.loop_state_embed(
            'Showing the current loop state; pass an argument to start or stop looping.' if state is None else None,
        ))

    @alias_from_config
    @commands.command('shuffle', aliases=[])
    async def toggle_shuffle(self, ctx: commands.Context, state: Literal['on', 'off'] | None = None) -> None:
        """Turns shuffle mode on or off, or shows whether shuffle is enabled if a state is not given.

        When active, a random item is chosen from the existing media queue when a track finishes or is skipped.
        """
        if state is None:
            await ctx.send(embed=embed_info(
                f'Shuffle is currently {'enabled' if self.shuffle else 'disabled'}.',
                'Use `shuffle on` or `shuffle off` to change this.',
            ))
            return
        self.shuffle = state == 'on'
        await ctx.send(embed=embed_info(f'{EmojiStr.SHUFFLE} Shuffle {'enabled' if self.shuffle else 'disabled'}.'))

    @alias_from_config
    @commands.command('queue', aliases=[])
    async def show_queue(self, ctx: commands.Context, page: int = 1) -> None:
        """Shows the queue."""
        if page < 1:
            await ctx.send(embed=embed_info('Page index must be more than zero.'))
            return

        pages: int = ceil(len(self.queue) / QUEUE_MAX_PER_PAGE) or 1

        if page > pages:
            await ctx.send(embed=embed_info('Page index out of range, showing the last page.'))
            page = pages

        queue_slice: tuple[MediaItem, ...]
        embed_desc: str
        page_start: int
        page_end: int

        if pages == 1:
            page_start = 0
            queue_slice = tuple(self.queue)
            embed_desc = f'Showing {len(self.queue)} item(s)'
        else:
            page_start, page_end = QUEUE_MAX_PER_PAGE * (page - 1), QUEUE_MAX_PER_PAGE * page
            queue_slice = tuple(self.queue)[page_start:page_end]
            embed_desc = f'Showing items #{page_start + 1} to #{min(page_end, len(self.queue))}' \
                + f' out of {len(self.queue)}'

        if self.shuffle:
            embed_desc += f'\n{EmojiStr.SHUFFLE} **Shuffle is enabled**'

        queue_embed = discord.Embed(
            title='Queue' + (f' (Page {page}/{pages})' if pages > 1 else ''),
            description=embed_desc,
            color=EMBED_COLOR_INFO,
        )

        if self.now_playing:
            self.now_playing.add_embed_field(queue_embed, 'Now playing: ')

        if self.stopped_track:
            self.stopped_track.add_embed_field(queue_embed, 'Stopped: ')

        for n, item in enumerate(queue_slice, start=page_start + 1):
            item.add_embed_field(queue_embed, f'#{n}. ')

        await ctx.send(embed=queue_embed)

    @alias_from_config
    @commands.command('clear', aliases=[])
    async def clear_queue(self, ctx: commands.Context) -> None:
        """Clears the queue."""
        self.queue.clear()
        self.stopped_track = None
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
        self.inactive = False
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
