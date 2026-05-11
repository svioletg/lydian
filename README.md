# Lydian (Discord Bot) <!-- omit in toc -->

Lydian is a Discord bot for playing music. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to
extract info and download media from URLs, and thus will support [any source that yt-dlp
supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

> [!IMPORTANT]
> Lydian is intended to be used in only one server at a time. Trying to play music in
> two or more different servers at once may cause unexpected issues and is unsupported for the time
> being.

Documentation: <https://lydian-discord-bot.readthedocs.io/en/latest/>

## Contents <!-- omit in toc -->

- [Setup: Lydian](#setup-lydian)
- [Setup: Discord](#setup-discord)
- [Usage: Running the bot](#usage-running-the-bot)
- [Usage: Bot console commands](#usage-bot-console-commands)
  - [`debug read`, `debug readlog`](#debug-read-debug-readlog)
  - [`stop`](#stop)
  - [`uptime`](#uptime)
- [Usage: CLI commands](#usage-cli-commands)
  - [`clear-dl`](#clear-dl)
  - [`logs latest`](#logs-latest)
- [URL and extractor filtering](#url-and-extractor-filtering)
- [Debug Mode](#debug-mode)

## Setup: Lydian

Install [Python](https://www.python.org/) version 3.14 or higher. If you're using MacOS or Linux, I
recommend using [pyenv](https://github.com/pyenv/pyenv#installation). The bot is structed as a
Python package, so you can install it using this command:

```bash
pip install git+https://github.com/svioletg/lydian-discord-bot.git
```

This will install Lydian and its commands to your virtual environment if one is active, otherwise
it'll be available in your global Python environment. The bot can be updated in the future by
running this same command with `-U` added after `install`.

```bash
pip install -U git+https://github.com/svioletg/lydian-discord-bot.git
```

## Setup: Discord

Follow the instructions here: <https://discordpy.readthedocs.io/en/stable/discord.html>

You must provide your bot's token via the `LYDIAN_TOKEN` environment variable. The recommended way
to do this is by creating a text file called `.env` in the directory you'll run the bot from, and
write in `LYDIAN_TOKEN=<token>` where `<token>` should be replaced with your real bot token.

> [!NOTE]
> Make sure that the file is named *exactly* `.env`, and not `.env.txt` or anything else. If you're
> using Windows or macOS, file extensions may be hidden in your file browser by default.
> - [Showing file extensions on
>   Windows](https://support.microsoft.com/en-us/windows/common-file-name-extensions-in-windows-da4a4430-8e76-89c5-59f7-1cdbbc75cb01)
> - [Showing file extensions on
>   macOS](https://support.apple.com/guide/mac-help/show-or-hide-filename-extensions-on-mac-mchlp2304/mac)

## Usage: Running the bot

Use the `lydian` command to start running the bot. Lydian will check for a file named
`lydian-config.toml` in your current working directory (the directory you ran the command from), and
will exit with an error if one is not present. If it does see this file, it will begin to use that
directory for storing data related to the bot like logs and downloaded media. You should make a
folder somewhere on your PC, for example named `lydian`, make a new file called
`lydian-config.toml`, then run `lydian` in that folder.

The bot can be stopped either by using the `stop` command, or hitting Ctrl+C while focused on the
window.

## Usage: Bot console commands

Lydian implements a basic console that can accept some limited commands while the bot is running:

> [!NOTE]
> All commands starting with `debug` require [debug mode](#debug-mode) to use.

### `debug read`, `debug readlog`

> [!WARNING]
> This command uses the `eval()` function, which is [unsafe to use with untrusted user
> input](https://nedbatchelder.com/blog/201206/eval_really_is_dangerous) and enables potentially
> destructive actions. You should be using a separate bot token for debug mode (set with
> `LYDIAN_DEBUG_TOKEN`), and as long as you're only running the bot locally on a secure machine this
> shouldn't be an issue.

Prints the result of an expression to stdout, or logs it as a DEBUG-level log if using `readlog`.
`read` and `readlog` have access to the `config` object, and a `dbg` dictionary which stores
references to various things specifically for debugging or development usage, as well as Python's
built-ins.

Arguments:
  - expression (string)

Example:

```log
> debug read dbg.cog.voice.queue
debug_context['cog.voice.queue'] == MediaQueue([])
> debug readlog dbg.cog.voice.queue
[2026-04-30 00:51:30] [bot::thread_console/DEBUG]: debug_context['cog.voice.queue'] == MediaQueue([])
```

### `stop`

Attempts to shut the bot down cleanly.

Arguments: N/A

### `uptime`

Prints out how long the bot has been running for.

Arguments: N/A

## Usage: CLI commands

Lydian provides some utilities under the `lydian-cli` or `lydian-manage` commands. Either can be
used, they will behave exactly the same.

### `clear-dl`

Prints the total size being taken up by the downloaded media directory and asks if the user would
like to delete its contents.

Arguments: N/A

### `logs latest`

Prints the filepath to the most recently created log file.

Arguments: N/A

## URL and extractor filtering

The bot uses regular expressions (commonly "regex") for the user-configured input URL and yt-dlp
extractor filters. If you're unfamiliar, you can view a quick reference for regex syntax here:
<https://www.rexegg.com/regex-quickstart.php>

> List of yt-dlp extractors: <https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md>

Add `-` to the beginning of the pattern to make it a blacklisted expression.
The URL will be matched against the expression from the beginning of the string, so you don't need
account for anything after it (i.e. no need for ending every expression in `.*` or starting it with
`^`), but you *will* need to add `.*` to the end of your extractor filters to match anything
following that expression.

> [!NOTE]
> When entering these regular expressions into your config TOML, make sure to use **single quotes**
> to ensure it is treated as a "literal" string.
>
> Dots (`.`) are special character in regex, so make sure to escape any literal dots with a
> backslash.

Examples:

|Regex|Description|
|-----|-----------|
|`https://.+\.youtube\.com/`|Matches any YouTube link|
|`https://music\.youtube\.com/`|Matches only YouTube Music links|
|`https://youtu\.be/`|Matches shortened "youtu.be" share links|
|`https://.+\.bandcamp\.com/`|Matches any Bandcamp link|
|`https://kinggizzard\.bandcamp\.com/`|Matches only one artist's Bandcamp page|

## Debug Mode

Debug mode can be enabled either by setting the `LYDIAN_DEBUG` environment variable to `1` or by
setting `debug` to `true` in `lydian-config.toml`. This will:

- Use the `LYDIAN_DEBUG_TOKEN` environment variable's value instead of `LYDIAN_TOKEN` for the bot
  token
- Enable bot commands from the `DebugCog` commands cog; see <!-- TODO: add docs link to cogs.debug.DebugCog -->
- Enable debug-only console commands (see [Usage: CLI commands](#usage-cli-commands))
