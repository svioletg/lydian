# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version changelogs may have an extra "Overview" section before the sections defined by *Keep a
Changelog* to more briefly describe end-user changes, while the rest of the changelog more verbosely
describes internal changes. Backwards-incompatible changes will be listed at the top of the overview
section.

Module names omit the leading `lydian.` for the sake of brevity, so if a changelog references
`cogs.voice.VoiceCog`, the fully qualified path would be `lydian.cogs.voice.VoiceCog`. The two
exceptions to this are the non-`lydian` modules `tools` and `tests`, which use their fully qualified
paths. `lydian` does not contain any modules named `tools` or `tests`, to avoid confusion.

Bot commands are referred to here using the default prefix of hyphen (`-`), replace with your
configured prefix accordingly.

## [Unreleased]

### Added

- Added `title` named group to markdown header regexes in `const`
  - `const.MD_HEADER_REGEX`
  - `const.MD_H1_REGEX`
  - `const.MD_H2_REGEX`
  - `const.MD_H3_REGEX`
- Added bot command `-loop` (method `cogs.voice.VoiceCog.toggle_loop()`)
- Added enum member `const.EmojiStr.LOOP`
- Added enum member `const.EmojiStr.LOOP_ONE`
- Added attribute `cogs.voice.VoiceCog.loop`
- Added method `cogs.voice.VoiceCog.loop_state_embed()`
- Added proper handling for `discord.ext.commands.errors.BadLiteralArgument` in
  `bot.on_command_error()`

### Fixed

- Fixed markdown header regexes matching more header symbols than intended, they now correctly match
  *only* their respective header level

## [0.9.0] - 2026-06-17

### Overview

- Vote-skipping is now supported, optionally requiring a minimum number of users (a percentage of
  the channel or an exact count) to use `-skip` before the current track is skipped. (#16)
  - To use it, add the `[vote_skipping]` table to your `lydian-config.toml` like below and adjust
    the values as desired.

```toml
[vote_skipping]
enabled = true
threshold_type = "percentage"
percentage = 50
literal = 3
```

### Added

- Added debug console command `debug store`
- Added debug bot command `-dropdown` (method `cogs.debug.DebugCog.dropdown()`)
- Added module `help`
- Added constant `const.DOCSTRING_PARAM_REGEX`
- Added constants `const.GH_CHANGELOG_WEB` and `const.GH_CHANGELOG_RAW`
- Added constants to `const`:
  - `MD_HEADER_REGEX`
  - `MD_H1_REGEX`
  - `MD_H2_REGEX`
  - `MD_H3_REGEX`
- Added enum members `const.EmojiStr.BACK` and `const.EmojiStr.GEAR`
- Added classes `cogs.util.ArrowButtonsView` and `cogs.util.DropdownView`
- Added class `cogs.voice.VoteSkip`
- Added attribute `cogs.voice.MediaItem.user_id` to replace `.user`
- Added method `console.LydianConsole._debug_evaluate_in_context()`
- Added functions to `cogs.util`:
  - `cog_emoji()`
  - `command_signature()`
  - `paginated_message()`
- Added functions to `util`:
  - `cog_commands()`
  - `getclass()`
  - `get_text_sections()`
  - `mention()`
- Added pytest fixtures `mock_bot` and `mock_discord_user`

### Changed

- `util.dirsize()` now only counts file sizes and ignores directories
- `cogs.voice.MediaItem` objects now store who queued the item as their `int` user ID rather than
  the actual `discord.Member` object, which allows them to be deep-copied
- Moved `update.GH_API_ROOT`, `update.GH_REPO_API_ROOT`, and `update.USER_AGENT` to `const`
  - Value of `USER_AGENT` updated to use the package's name instead of `lydian-update-checker`
- Swapped arguments of `util.first_where()` to make the predicate first, matching built-ins like
  `map` and `filter`

### Removed

- Removed attribute `cogs.voice.MediaItem.user`, (replaced by `.user_id`)

### Fixed

- Fixed `cogs.voice.MediaItem` objects always refreshing when advancing queue if their
  `thumbnail_url` attribute is truthy (incorrectly wrote
  `(not item.duration) or (item.thumbnail_url)` instead of
  `(not item.duration) or (not item.thumbnail_url)`)
- Fixed `ZoneInfo` not working correctly on systems without an IANA database by including `tzdata`
  as a dependency

## [0.8.0] - 2026-06-05

### Overview

> **Breaking changes**
>
> - Some TOML configuration keys are now properly nullable, using the `'n/a'` value to indicate
>   such.
>   - Config keys `max_duration`, `media_dir_warn_threshold`, `inactivity_timeout`, and
>     `lonely_timeout` now use `'n/a'` instead of `-1` or `0` to indicate they should be disabled

- Lydian can now optionally check for new releases at startup, toggled with the `check_for_updates`
  configuration key (or `LYDIAN_CHECK_UPDATES` environment variable).
  - You can check for updates manually by running `lydian-update`.
  - By default, pre-releases are skipped during this check. Set the `check_for_stable_only` config
    key to `false` to include pre-releases.
- The media queue now has a shuffle mode, use `-shuffle <on|off>` to enable or disable it.
- Lydian now includes exception arguments in "unexpected error" messages.
  - Full tracebacks are still only available in Lydian's logs.
- A temporary (deletes after 10 seconds) message is now sent when skipping a track

### Added

- Added config key `bot_console` (boolean)
  - env: `LYDIAN_BOT_CONSOLE`
- Added config key `check_for_updates` (boolean)
  - env: `LYDIAN_CHECK_UPDATES`
- Added config key `check_for_stable_only` (boolean)
  - env: `LYDIAN_CHECK_STABLE_ONLY`
- Added console commands `version` and `updates`
- Added module `update`
- Added debug bot commands `-argstr` and `-argint`
- Added bot commands:
  - `-issues`
  - `-repo`
  - `-shuffle`
- Added attribute `cogs.voice.VoiceCog.shuffle`
- Added attributes `converter_env` and `converter_toml` to `config.ConfigFieldMeta`
- Added command methods `cogs.debug.DebugCog.argstr()` and `cogs.debug.DebugCog.argint()`
- Added command methods `cogs.general.GeneralCog.repo()` and `cogs.general.GeneralCog.issues()`
- Added command method `cogs.voice.VoiceCog.toggle_shuffle()`
- Added method `console.LydianConsole.version()`
- Added classmethod `tools.todos.Todo.parse_todos()`
  - Parses `Todo` objects directly from a string without needing file paths
- Added method `tools.todos.Todo.with_file()`
- Added function `util.exc_str()`

### Changed

- Package version is now set dynamically using `__version__` from `__init__.py`
- Bot command `-hello` now accepts aliases
- The discord.py exceptions `BadArgument` and `MissingRequiredArgument` are now properly handled
- Logging methods in `cogs.voice.YTDLLogHandler` now log with `depth=2` for more accuracy
- Renamed in `const`:
  - `COLOR_INFO` → `EMBED_COLOR_INFO`
  - `COLOR_OK` → `EMBED_COLOR_OK`
  - `COLOR_WARN` → `EMBED_COLOR_WARN`
  - `COLOR_ERROR` → `EMBED_COLOR_ERROR`
- A status message is now sent when retrieving info for a track before downloading begins (#30)
- Tool `todos` now accepts multiple directories to search
- In `tools.todos`:
  - `Todo.content` is now an attribute and not a method
  - `Todo.header` is now a cached property and no longer accepted as a constructor argument
  - `Todo.file` is now an optional attribute
  - `find_todos()` now takes a variable positional argument `paths` instead of the single
    positional argument `source_dir`, still `str | Path`
- Moved function `config.env_to_bool()` to `util.FromStr.to_bool()`
- Renamed classmethod `util.FromStr.filesize()` to `util.FromStr.to_filesize()`
- Unexpected errors caught in `bot.on_command_error` now have their exception args sent along with
  the bot's message instead of only saying to check the logs

### Fixed

- Fixed `util.tabulate()` raising an error for empty data (#32)
- Fixed `todos` dev tool skipping `# TODO` lines with no author (#33)

## [0.7.0] - 2026-05-25

### Overview

> **Breaking changes**
>
> - TOML configuration keys now use underscores (`_`) instead of hyphens (`-`)
> - Config key `log_level` under `logging` is now `level`

- [feature] A duration limit for media items can now be set using the `max-duration` config key, which
  specifies the limit in seconds using a positive integer (setting to 0 will disable the limit)
  - `max-duration-allow-unknown` specifies whether tracks with an unknown duration can be played
    or not when a duration limit is in place, defaulting to `false`
    - If no limit is set, this key is unused and tracks of unknown duration are always allowed
    - To save time on queueing, Lydian does not fetch a track's duration until it needs to, meaning
      items queued from a playlist URL won't have their duration checked against the limit until
      they are next in line
- [feature] `lydian` can now be run with the `-V` or `--version` option to display the installed Lydian
  version and exit without starting the bot
- [feature] The "now playing" view now shows the approximate current timestamp of the playing media
  (#13)
  - Slight network delays will likely cause this number to be slightly inaccurate, but it should
    remain close enough for reference
- [fix] Fixed filesize strings in the config with single digits raising an error due to a typo in the
  regex used to match them

### Added

- Added the `-V`/`--version` option to the `lydian` package command
  - When used, Lydian's version is printed out and the script immediately exits
- Added config key `max-duration` (integer)
- Added config key `max-duration-allow-unknown` (boolean)
- Added class `config.Config.ConfigField`
- Added class `config.Config.ConfigFieldMeta`
- Added method `config.Config.set()`
- Added property `config.Config.fields`
- Added function `util.compose()`
- Added support for validator functions in `config.Config` fields, which can be given with the
  `'validators'` key of a given field's `metadata` argument as a single function or iterable of
  functions

### Changed

- Having debug mode enabled no longer forces the log level to "DEBUG" level
- `cogs.voice.MediaItem.duration_str` now returns `?:??` for an unknown duration instead of `None`
- `cogs.voice.MediaItem.embed()` now accepts an optional `timestamp` keyword argument to show the
  current time alongside its duration
- TOML configuration keys are now in `snake_case` instead of `kebab-case`; though the latter is more
  common in TOML, it's ultimately unnecessary to keep converting keys between the two cases where
  needed
- `const.LogLevel` is now an `IntEnum` subclass instead of `StrEnum`
- `config.Config` updating and loading from TOML is now handled in the class itself in a simpler
  fashion than using `util.DataclassUpdateMixin` (#26)

### Removed

- Removed mixin class `util.DataclassUpdateMixin`
  - Only used for updating the configuration object, which now handles updating in its own class

### Fixed

- Fixed single-digit filesize numbers in TOML config not matching pattern
- Queue no longer stops when encountering an error, will now skip problematic items until one can be
  played or the queue is empty (#25)

## [0.6.1] - 2026-05-25

### Fixed

- Fixed Lydian completely failing on Windows due to an issue with a path highlighter (#28)

## [0.6.0] - 2026-05-19

### Added

- Added console command group `tasks`
  - `list`: Lists background tasks assigned to the bot and their status, interval, and ID
  - `start`: Attempts to start a specified background task
- Added method `console.LydianConsole.tasks_list()`
- Added method `console.LydianConsole.tasks_start()`
- Added function `util.get_background_tasks()`
- Added function `util.get_leaves()`
- Added function `util.iter_columns()`
- Added function `util.tabulate()`
- Added keypaths for every registered cog to `debug_context`, not just `voice`
  - Keys are the cog object name with the `Cog` suffix removed and lowercased,
    e.g. `GeneralCog` → `general`
- Added `tasks` and `tasklist` keys to `debug_context`
- Console command `debug read` expression argument can now be prefixed with `?` as an alias to
  `dbg.`

### Changed

- Log messages from discord.py are now properly redirected to Lydian's logger
  - Any message originating from a private function (prefixed with `_`) are overridden to be a
    "DEBUG"-level log
- `no-` prefixes in console command flags no longer invert the flag's default, instead `no-` just
  sets its value to `False` and sets `True` otherwise
- `console.BotConsole.start_loop()` now accept a `catch` parameter
  - If `True`, exceptions raised while invoking a command are logged instead of propagating them,
    allowing the console loop to continue

### Fixed

- Changed type annotation for `cogs.voice.VoiceCog.bot` to `commands.Bot` instead of
  `discord.client.Bot` to fix sphinx error
- Fixed `ValueError` raised in `util.format_duration()` when formatting `m` or `s` with `02d` since
  they can be floats
- `TypeError` and `ValueError` raised while trying to parse console command argument values are now
  caught and displayed without killing the console
- Login failures are caught properly with a custom succinct message for improper tokens, otherwise
  logs the traceback
- Fixed "flag" keyword arguments not getting parsed correctly by the console

## [0.5.0] - 2026-05-17

### Added

- Added ability to restrict command usage to users with or without certain roles (#9)
- Added debug-only bot command `-captureuser`
  - Stores the `discord.Member` object of the command author to the `debug_context` dictionary
- Added module `console`
- Added module `perms`
- Added constant `const.PERMISSIONS_PATH`
- Added constant `const.DOTENV_PATH`
- Added class `util.FromStr`
- Added function `bot.on_message()` as a Discord event listener of the same name
- Added function `util.get_annotation()`
- Added function `util.is_annotated()`
- Added function `util.join_trailing()`
- Added functions to `tests/conftest.py`:
  - `mock_discord_role()`
  - `mock_get_role()`
  - `mock_discord_member()`
- Added command function `cogs.debug.captureuser()`
- Added function `util.wrap_paragraphs()`
- Added method `cogs.voice.VoiceCog.task_handle_play_requests()`
- Added test file `test_console.py`
- Added test file `test_perms.py`
- Added test file `test_util_fromstr.py`

### Changed

- Output of console command `debug read` now shows `repr()` of the value instead of its `str()`
  representation
- Calls to `-play` now have their context object and URL string put into a queue which is
  continuously checked and run in order, so two `-play` requests aren't handled at the same time
  (#6)
- Renamed `cogs.voice.VoiceCog.tick_timers()` to `task_tick_timers()`
- `-clear` now removes the stopped track as well
- `config.Config.from_toml()` and `config.Config.update_from_toml()` both now expect a
  TOML-formatted string instead of a file path
- Debug command `debug read` can now access the new global `perms` object
- Running the `lydian` command without a `lydian-config.toml` present will now offer to create
  `.env` and enter your token in addition to creating the TOML and `permissions.yml` files
- `config.Config` fields' `metadata` dictionary now expects the `converter` key in place of
  `envcov`, and will be used more generally
- Config key `max-filesize` now additionally accepts a string of a value and unit, like `"50 MB"` or
  `1gb`
- Renamed `const.console` to `const.screen` to further separate it from the newly added `BotConsole`

### Fixed

- Fixed wrong line position being shown for TODO lines when running the `todos` tools (#19)

## [0.4.1] - 2026-05-12

### Added

- Added package dependency `urllib3>=2.7.0,<3.0` to address CVE-2026-44431 and CVE-2026-44432

### Changed

- Renamed `cogs.voice.VoiceCog.since_alone` to `time_alone`
- Renamed `cogs.voice.VoiceCog.since_inactive` to `time_inactive`

### Fixed

- Fixed `const.DATA_DIR` being set incorrectly due to checking `CONFIG_PATH.parent.exists()` when
  the check should've been `CONFIG_PATH.exists()`

## [0.4.0] - 2026-05-10

### Added

- Added config key `max-playlist-length` (integer)
- Added config key `inactivity-timeout` (integer) (#17)
- Added config key `lonely-timeout` (integer) (#17)
- Added config table `media-filter` (#12)
  - Added key `allowed_extractors` (string list)
  - Added key `allowed_urls` (string list)
- Added constant `const.QUEUE_MAX_PER_PAGE`
- Added bot command `-move`
- Added bot command `-nowplaying`
- Added console command `uptime`
  - Prints how long the bot has been running for
- Added exception class `errors.FileSizeLimitError`
- Added function `cogs.voice._assert_discord_member`
- Added function `util.expect()`
- Added function `util.format_duration()`
- Added function `util.linepos_to_pos()`
- Added function `util.partition()`
- Added function `util.pos_to_linepos()`
- Added attribute `cogs.voice.MediaItem.user`
- Added attribute `cogs.voice.YTDLSource.file`
- Added attributes to `cogs.voice.VoiceCog`:
  - `inactive`: (`bool`) Whether the bot is "inactive", as in no media is being played and
    the queue is empty (the bot being paused still counts as playing in this context)
  - `alone`: (`bool`) Whether the bot is the only user in the voice channel it is connected to
  - `since_inactive`: (`int`) How many seconds have passed since `inactive` has been `True`
  - `since_alone`: (`int`) How many seconds have passed since `alone` has been `True`
- Added property `cogs.voice.MediaItem.duration_str`
- Added method `cogs.voice.MediaItem.add_embed_field()`
- Added method `cogs.voice.MediaItem.embed()`
- Added method `cogs.voice.MediaItem.move()`
- Added method `cogs.voice.MediaItem.set_user()`
- Added method `cogs.voice.VoiceCog.on_voice_state_update()` as a listener for the event of the
  same name
- Added method `cogs.voice.VoiceCog.tick_timers()`, a task which runs every second
- Added method `cogs.voice.VoiceCog._check_queue_index_arg()`
- Added method `cogs.voice.VoiceCog._try_to_queue()`
- Added method `config.filter_media_url()` (#12)
- Added method `util.Cache.clear()`
- Added command method `cogs.voice.VoiceCog.nowplaying()`
- Added command method `cogs.voice.VoiceCog.move()`

### Changed

- `-queue` command is now paginated, accepts an optional page index value and shows up to 20 items
  per page (#11)
- `cogs.voice.MediaQueue` is now a subclass of `UserList` rather than a `deque`
  - Now accepts an `initlist` parameter
- `cogs.voice.MediaItem` embeds now show the user that queued it, if one is set
- `cogs.voice.MediaItem.from_url` now returns a tuple of `MediaItem` objects instead of one
- `cogs.voice.MediaItem.from_url` now takes an optional `user` parameter
- `cogs.voice.VoiceCog.advance_queue()` now returns `Exception | None`
- `config.Config.update_from_toml()` parameter `missing_ok` renamed to `on_missing`, accepts the values `'raise'`,
  `'warn'`, or `'continue'`
- `util.Cache` constructor now accepts a `default_expiration` parameter
  - Must be a `timedelta` object, will be used as the expiration date when calling the `set()` or
    `get_or_set()` methods if `expires` is `None`
- `util.setup_logger()` parameter `logs_dir` now accepts `None`, in which case file logging is
  disabled
- `util.DataclassUpdateMixin.update()` parameter `missing_ok` renamed to `on_missing`, now accepts either a `Callable`
  or one of `'raise'` or `'continue'`
- yt-dlp extraction exceeding the set filesize limit will now raise `FileSizeLimitError` instead of just getting logged
  (solves #14)

### Removed

- Removed unused event constant `cogs.voice.EV_PLAYER_STOPPED_BY_COMMAND`
- Removed method `cogs.voice.MediaQueue.appendleft()`
  - Use `.insert(0, x)` instead; while technically slower than a deque, testing with `timeit` shows
    inserting to the front of a 10,000 length list still only takes some ~0.0016 seconds, which is
    more than acceptable

### Fixed

- Fixed error raised when calling `util.setup_logger()` after its already been called once due to
  setting the `CONSOLE` log level number
- `util.DataclassUpdateMixin.update()` now properly checks that the value for a `Literal`-typed
  field is correct
- Fixed "playing" message still getting sent if the the set filesize limit is exceeded during yt-dlp extraciton (#14)

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
  ([#3](https://github.com/svioletg/lydian/issues/3))
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
