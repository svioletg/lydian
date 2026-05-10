"""Exception classes for Lydian."""

class AbortCommand(Exception):  # noqa: N818 ; similar semantics to the built-in StopIteration, seems reasonable
    """Raised to abort a bot command. Silently ignored by the bot's error handler."""
class AssuranceError(Exception):
    """Raised when :py:func:`lydian.util.assure` is passed ``False``."""
class FileSizeLimitError(Exception):
    """Raised when yt-dlp extraction is aborted due to exceeding the configured filesize limit."""
class MediaQueueLimitError(Exception):
    """Raised when trying to append to or extend the media queue beyond its limit."""
