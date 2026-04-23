# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.coAm/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added config key `debug` (boolean)
- Added config key `max_filesize` (integer)
- Added module `cogs.debug`
- Added enum class `const.EmojiStr`
- Added `lydian-cli` command `logs`
  - `logs latest`: Returns the most recently modified log file
- Added test to `test_util` for `util.get_dataclass_fields`

### Changed

- Renamed `VERSION` in module `const` to `PROJECT_VERSION`
- `config.Config.to_toml()` now adds environment variable names of each field (if applicable) to
  the beginning of each key's associated comments
- Log message timestamps are now shown in UTC if config key `logging.utc` is `true`, otherwise they
  are shown in the system's local time
- Reduced log rotation size limit from 100 MB to 10 MB
- Moved and renamed `config.DataClassUpdateMixin` to `util.DataclassUpdateMixin`

### Removed

- Removed config key `auto-remove`

### Fixed

- Fixed `const.LOG_FILE_FORMAT` not being used when setting up the file handler in `const.setup_logging()`

## [0.1.0] - 2026-04-18

Initial development version.
