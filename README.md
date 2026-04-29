# Lydian (Discord Bot) <!-- omit in toc -->

Lydian is a Discord bot for playing music. It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to
extract info and download media from URLs, and thus will support
[any source that yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

> [!IMPORTANT]
> Lydian is intended to be used in only one server at a time. Trying to play music in two or more
> different servers at once may cause unexpected issues and is unsupported for the time being.

Documentation: <https://lydian-discord-bot.readthedocs.io/en/latest/>

## Contents <!-- omit in toc -->

- [Setup: Lydian](#setup-lydian)
- [Setup: Discord](#setup-discord)
- [Usage: Running the bot](#usage-running-the-bot)
- [Usage: Bot console commands](#usage-bot-console-commands)
- [Usage: CLI commands](#usage-cli-commands)
  - [`logs latest`](#logs-latest)

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

Lydian will look for your bot's token in one of two places, either inside a `token.txt` file in the
current directory when running the bot, or it will check if the `LYDIAN_TOKEN` environment variable
is set. The latter can also be specified in a `.env` file, which the bot will load automatically.
If both options are present, the environment variable will be used.

## Usage: Running the bot

Lydian's main command is `lydian`, which will start running the bot. When attempting to run,
Lydian will check for a file named `lydian-config.toml` in your current working directory (the
directory you ran the command from), and will exit with an error if one is not present. If it does
see this file, it will begin to use that directory for storing data related to the bot like logs
and downloaded media. You should make a folder somewhere on your PC, for example named `lydian`,
make a new file called `lydian-config.toml` (ensure the file extension really *is* `.toml`), then
run `lydian` in that folder.

The bot can be stopped either by using the `stop` command, or hitting Ctrl+C while focused on the
window.

## Usage: Bot console commands

Lydian implements a basic console that can accept some limited commands while the bot is running:

|Command |Description                           |
|--------|--------------------------------------|
|`stop`  |Attempts to shut down the bot cleanly.|

## Usage: CLI commands

Lydian provides some utilities under the `lydian-manage` command. Run `lydian-manage --help` to
view them.

### `logs latest`

Prints the filepath to the most recently created log file.

Arguments: N/A
