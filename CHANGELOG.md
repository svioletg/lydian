# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.coAm/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added function `util.format_duration()`
- Added method `util.Cache.clear()`
- Added method `cogs.voice.MediaItem.embed()`
- Added property `cogs.voice.MediaItem.duration_str`

### Changed

- `util.Cache` constructor now accepts a `default_expiration` parameter
  - Must be a `timedelta` object, will be used as the expiration date when calling the `set()` or
    `get_or_set()` methods if `expires` is `None`

## [0.3.0] - 2026-05-05

### Added

- Lydian version is now logged on bot startup
- Console input is now logged in log files
- Added config key `max-queue-length` (integer)
- Added config key `media-dir-warn-threshold` (integer)
  - If the size of the downloaded media directory exceeds this threshold, a warning is emitted at
    bot startup
  - Can be set to -1 to never emit a warning
- Added 4 bot commands:
  - `-clear`: Clears the media queue
  - `-queue`: Shows what's currently in the media queue
  - `-remove`: Removes an item from the queue at a given index
  - `-skip`: Skips the currently playing media
- Added `lydian-cli` command `clear-dl`
- Added console commands `debug read` and `debug readlog`
- Added constant `const.COLOR_ESCAPE_REGEX`
- Added constant `const.DEFAULT_DISCORD_PROMPT_TIMEOUT`
- Added class `cogs.util.ConfirmView`
- Added class `util.BasicLock`
- Added class `util.Cache`
- Added class `util.CachedObject`
- Added exception class `errors.MediaQueueLimitError`
- Added warning class `cogs.util.ConfirmViewResponseWarning`
- Added function `bot.on_error()`
- Added function `cli.abort()`
- Added function `cli.clear_dl_dir()`
- Added decorator function `cogs.util.alias_from_config()`
  ([#3](https://github.com/svioletg/lydian-discord-bot/issues/3))
- Added function `cogs.util.confirm()`
- Added function `const._stdout_log_filter()`
- Added function `util.dirsize_counted()`
- Added function `util.dirsize()`
- Added function `util.plural()`
- Added command method `cogs.debug.DebugCog.bigembed()`
- Added command method `cogs.debug.DebugCog.promptyn()`
- Added members to `const.EmojiStr`:
  - `CANCEL`
  - `CONFIRM`
  - `IN`
  - `OUT`
  - `PAUSE`
  - `PLAY`
  - `SKIP`
  - `STOP`
- Added test file `test_cogs_voice.py`
- Added tests to `test_util.py`:
  - `test_cache()`
  - `test_cached_object_init()`
  - `test_dirsize()`
  - `test_plural()`
- In module `cogs.voice`:
  - Added class `MediaItem`
  - Added class `MediaQueue`
  - Added command method `Voice.clear_queue()`
  - Added command method `Voice.remove()`
  - Added command method `Voice.show_queue()`
  - Added command method `Voice.skip()`
  - Added method `YTDLLogHandler.error()`
  - Added method `Voice.advance_queue()`
  - Added method `Voice.stop_player()`
  - Added method `Voice.on_player_stop()`

### Changed

- Media download progress messages are now completely ignored
- Traceback logs for `CommandInvokeError` exceptions will now only include the traceback for the
  original exception it was raised from, otherwise largely useless clutter is introduced
- `cogs.voice._assert_voice_client()` now more accurately raises `TypeError` instead of
  `ValueError` when its argument is `None` or not a `discord.VoiceClient`
- Switched to using `prompt-toolkit` for the bot console instead of `aioconsole`
- The logger's stdout sink is now a function that directly calls `sys.stdout.write()` to work
  around an `prompt-toolkit`'s `patch_stdout` not working as intended in combination with
  `loguru`'s logging
  - See: <https://github.com/Delgan/loguru/issues/1385>
- Lydian's data directory is no longer created when importing `const`
- All command definitions which used aliases now use the `cogs.util.alias_from_config` decorator
- Log messages now include timezone
- `util.dirsize()` now includes the 4096 bytes per each directory in its returned size
- `tests/tmp` is now cleared on test session start
- Renamed function `cli.latest()` to `cli.logs_latest()`
- Renamed function `cogs.voice.Voice.clear` to `clear_queue`

### Removed

- Removed constant `const.TOKEN_PATH`
- Removed function `bot.get_token()`
- Removed function `const.log_file_filter()`

### Fixed

- Exceptions raised inside of `bot.on_command_error` are now logged and not silently ignored
- yt-dlp error logs (calls to the `.error()` method of its logger) are now properly handled
- Command hook method `cogs.voice.VoiceCog.auto_join()` now correctly raises `AbortCommand` when the
  author is not a guild member instead of returning

## [0.2.0] - 2026-04-27

### Added

- Added config table `command_aliases`
  - Takes lists of strings to use as aliases for each command given, e.g. `join = ["j"]`
- Added config key `debug` (boolean)
  - A warning message will be logged if `debug` is `true` on bot startup
- Added config key `max-filesize` (integer)
- Added module `cogs.debug`
- Added module `cogs.voice`
- Added module `errors`
- Added enum class `const.EmojiStr`
- Added function `bot.on_command_error()` to handle command errors
- Added function `const.create_directories()`
- Added `lydian-cli` command `logs`
  - `logs latest`: Returns the most recently modified log file
- Added test to `test_util` for `util.get_dataclass_fields`

### Changed

- Renamed constant `VERSION` in module `const` to `PROJECT_VERSION`
- `config.Config.to_toml()` now adds environment variable names of each field (if applicable) to
  the beginning of each key's associated comments
- Log message timestamps are now shown in UTC if config key `logging.utc` is `true`, otherwise they
  are shown in the system's local time
- Log files now use retention instead of rotating, keeping a maximum of 10 files
- Moved and renamed mixin class `config.DataClassUpdateMixin` to `util.DataclassUpdateMixin`
- Moved enum class `config.LogLevel` to `const.LogLevel`
- Console command `stop` will now call the bot's `.close()` method and return from the thread
  instead of just calling `sys.exit()`
- Running `lydian.config` without a filename argument will now print the TOML to stdout instead of
  giving an error
- Logger "DEBUG" level color change to `cyan`
- Logger "INFO" level color changed to `normal`
- Logger "ERROR" level color changed to `light-red`

### Removed

- Removed config key `auto-remove`

### Fixed

- Fixed `const.LOG_FILE_FORMAT` not being used when setting up the file handler in
  `const.setup_logging()`
- Fixed `config.add_comments_to_toml` skipping hyphenated keys

## [0.1.0] - 2026-04-18

Initial development version.
