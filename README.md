# Lydian (Discord Bot) <!-- omit in toc -->

![Required Python version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fsvioletg%2Flydian%2Frefs%2Fheads%2Fmain%2Fpyproject.toml
)
![Build status, main branch](https://img.shields.io/github/actions/workflow/status/svioletg/lydian/lint-test.yml?branch=main&label=build%20(main)
)
![Build status, dev branch](https://img.shields.io/github/actions/workflow/status/svioletg/lydian/lint-test.yml?branch=dev&label=build%20(dev)
)

> [!WARNING]
> Lydian is currently in a beta state, before its v1.0.0 release it may be unstable or subject to
> a number of bugs. [Pre-releases](https://github.com/svioletg/lydian/releases) should
> work reasonably well, but it should likely be kept to smaller servers for the time being.

Lydian is a Discord bot for playing music. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to
extract info and download media from URLs, and thus will support [any source that yt-dlp
supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). Lydian does not support
Spotify links. Use the `-help` command to see all available commands, or `-help <command>` to see
information on a specific command. The bot's queue only clears when `-clear` is used or the bot is
shut down.

Bug reports, feature suggestions, questions: <https://github.com/svioletg/lydian/issues>

Project board: <https://github.com/users/svioletg/projects/6/views/1>

Docs: <https://lydian.readthedocs.io/en/latest/>

> [!IMPORTANT]
> Lydian is designed to be used in only one server at a time. Trying to play music in two or more
> different servers at once may cause unexpected issues and is unsupported for the time being.

## Contents <!-- omit in toc -->

- [Setup: Discord](#setup-discord)
- [Setup: Lydian](#setup-lydian)
  - [Setup with `uv`](#setup-with-uv)
  - [Setup without `uv`](#setup-without-uv)
- [Usage: Running the bot](#usage-running-the-bot)
- [Usage: Bot console commands](#usage-bot-console-commands)
  - [`debug read`](#debug-read)
  - [`help`](#help)
  - [`stop`](#stop)
  - [`uptime`](#uptime)
- [Usage: CLI commands](#usage-cli-commands)
  - [`clear-dl`](#clear-dl)
  - [`logs latest`](#logs-latest)
- [URL and extractor filtering](#url-and-extractor-filtering)
- [Permissions](#permissions)
- [Debug Mode](#debug-mode)

## Setup: Discord

Follow the instructions here: <https://discordpy.readthedocs.io/en/stable/discord.html>

The bot permissions you'll need to tick are:

- Read Messages/View Channels
- Send Messages
- Embed Links
- Connect
- Speak

## Setup: Lydian

Lydian requires Python 3.14 or higher. If you haven't installed Python or aren't sure how to manage
multiple versions or virtual environments, using
[uv](https://docs.astral.sh/uv/getting-started/installation/) is recommended.

You will need to install [git](https://git-scm.com/install/) to install Lydian as a python package.

### Setup with `uv`

<details><summary>Click to show</summary>

1. Install uv per the "Standalone installer" instructions here:
   <https://docs.astral.sh/uv/getting-started/installation/>
2. Run `uv python install 3.14`.
3. Create a directory to run Lydian in, then navigate to it in your terminal.
4. Run `uv venv` to create a virtual environment, which will keep Lydian contained to your current
   directory.
5. Run `uv pip install git+https://github.com/svioletg/lydian.git` to install Lydian
   in this directory.
   - This will install the most recent available version of Lydian. If you want to install a
     specific version, add an `@` to the end of the URL followed by a
     [tag name](https://github.com/svioletg/lydian/tags).
6. Once installed, run `uv run lydian --version` and ensure it outputs "Lydian v[your version]"

You can now start the bot by running `uv run lydian` in this directory, at which points it should
handle the rest of the setup via a few prompts. You can also use `uv run lydian-manage` or
`uv run lydian-cli` for a small collection of Lydian-related utilities. Keep in mind that you will
need to preface every Lydian command with `uv run` and ensure you are in this directory.

Lydian can be updated in the future by running the same installation command above with the `-U`
option: `uv pip install -U git+https://github.com/svioletg/lydian.git`

</details>

### Setup without `uv`

<details><summary>Click to show</summary>

The bot is structured as a Python package, so you can install it using `pip`:

```bash
pip install git+https://github.com/svioletg/lydian.git
```

This will install Lydian and its commands (`lydian` and `lydian-manage`) to your virtual environment
if one is active, otherwise it'll be available in your global Python environment. The bot can be
updated in the future by running this same command with `-U` added after `install`.

```bash
pip install -U git+https://github.com/svioletg/lydian.git
```

</details>

You must provide your bot's token via the `LYDIAN_TOKEN` environment variable. The recommended way
to do this is by creating a text file called `.env` in the directory you'll run the bot from, and
write in `LYDIAN_TOKEN=<token>` where `<token>` should be replaced with your real bot token. Running
`lydian` without a `lydian-config.toml` file present in the current directory will give you a prompt
to input your token into, and the `.env` file will be created automatically.

> [!NOTE]
> Make sure that the file is named *exactly* `.env`, and not `.env.txt` or anything else. If you're
> using Windows or macOS, file extensions may be hidden in your file browser by default.
> - [Showing file extensions on
>   Windows](https://support.microsoft.com/en-us/windows/common-file-name-extensions-in-windows-da4a4430-8e76-89c5-59f7-1cdbbc75cb01)
> - [Showing file extensions on
>   macOS](https://support.apple.com/guide/mac-help/show-or-hide-filename-extensions-on-mac-mchlp2304/mac)

## Usage: Running the bot

Use the `lydian` command to start running the bot. If `lydian-config.toml` is not in your current
directory, you'll be asked if you want to create the necessary files automatically. If it *is*
present, the bot should start up normally. You should make a folder somewhere on your PC, for
example named `lydian`, then when Lydian installed, run the `lydian` command in that directory to
set it up.

The bot can be stopped either by using the `stop` command or hitting Ctrl+D while focused on the
window, after which the bot will try to shut itself down cleanly. If this isn't working for some
reason, you should be able to hit Ctrl+C to send a keyboard interrupt and forcibly stop the process.

## Usage: Bot console commands

> [!NOTE]
> All commands starting with `debug` require [debug mode](#debug-mode) to use.

### `debug read`

> [!WARNING]
> This command uses the `eval()` function, which is [unsafe to use with untrusted user
> input](https://nedbatchelder.com/blog/201206/eval_really_is_dangerous) and enables potentially
> destructive actions. You should be using a separate bot token for debug mode (set with
> `LYDIAN_DEBUG_TOKEN`), and as long as you're only running the bot locally on a secure machine this
> shouldn't be an issue.

Prints the result of an expression to stdout, or logs it as a DEBUG-level log if the `--log` flag is
given. This command has access to the `config` object, `perms` object, and a `dbg` dictionary which
stores references to various things specifically for debugging or development usage, as well as
Python's built-ins. For convenience, `?` can be used in place of `dbg.` at the beginning of the
expression, e.g. `?bot.user` is parsed as `dbg.bot.user`.

Arguments:
  - expression (string)

Options:
  - `--log` (flag)

Example:

```log
> debug read dbg.cog.voice.queue
debug_context['cog.voice.queue'] == MediaQueue([])
> debug read --log dbg.cog.voice.queue
[2026-04-30 00:51:30] [bot::thread_console/DEBUG]: debug_context['cog.voice.queue'] == MediaQueue([])
```

### `help`

Shows a description for a given command, or all commands if given no arguments.

Arguments:
  - command name (string) [optional]

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

## Permissions

Role-based permissions are handled separately from `lydian-config.toml`, in an optional
YAML file called `permissions.yml` kept in the same directory as the TOML config. YAML is slightly
more complex than TOML, but its usage here should be relatively straightforward. You can read about
it at [yaml.info](https://www.yaml.info/learn/index.html).

> [!NOTE]
> If `permissions.yml` is not found, no permissions are applied; i.e. all commands will be available
> to any user.
>
> Just like the config, permission rules are only loaded once when the bot starts up. If you make
> any changes to `permissions.yml` you want reflected, you'll need to stop the bot and start it
> again.

The basics to know as far as we're concerned are:

1. Instead of `key = value`, YAML uses a colon, e.g. `key: value`.
2. Boolean values can be either `true`/`false` or `yes`/`no`
3. YAML lists are written with hyphens, basically acting as bullet points for each item.

    ```yaml
    list:
      - "item 1"
      - "item 2"
    ```

4. YAML key values can contain more keys, creating nested tables ("mappings") indicated by
   indentation

    ```yaml
    top-category:
      subcategory-1:
        a: 1
        b: "two"
        c: true
      subcategory-2:
        a: 4
        b: "five"
        c: false
    ```

`commands` is a mapping of command names to a list (`roles`) and a `whitelist` key. `roles` accepts
a list of either role names (as a string) or role IDs (as an integer). Using IDs is recommended
since role names can change, while an ID will always point to the same role—you can use comments
(any text written after `#` on a line) to make a note of the role's name by its ID. An empty list
can be given by giving the key and no value, e.g. `roles:`.

`whitelist` can be either `true` or `false`: if `true` (whitelisting), only either those with any of
the listed roles can use this command, if `false` (blacklisting) only those *without* the listed
roles can use this command.

`commands` also accepts a `.default` key with the same structure described above, which defines
fallback rules to use when a command does not have any rules defined. The default rules are...

```yaml
  .default:
    whitelist: no
    roles:
```

...meaning any user with any or no roles can use any command without defined permissions.

Example:

```yaml
commands:
  .default:
    whitelist: false
    roles:
  remove:
    whitelist: true
    roles:
      - 'mod'
  skip:
    whitelist: true
    roles:
      - 1500575589361520640 # "Can Skip" role
```

This indicates:

- `-remove` can only be used by users with a role named `mod`
- `-skip` can only be used by users that have a role with the ID `1500575589361520640`
- For all other commands that aren't listed here, `.default` is used, in which any user regardless
  of roles can use them

## Debug Mode

Debug mode can be enabled either by setting the `LYDIAN_DEBUG` environment variable to `1` or by
setting `debug` to `true` in `lydian-config.toml`. This will:

- Use the `LYDIAN_DEBUG_TOKEN` environment variable's value instead of `LYDIAN_TOKEN` for the bot
  token
- Enable bot commands from the `DebugCog` commands cog; see <!-- TODO: add docs link to cogs.debug.DebugCog -->
- Enable debug-only console commands (see [Usage: CLI commands](#usage-cli-commands))
