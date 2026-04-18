# Lydian (Discord Bot)

Lydian is a Discord bot for playing music.

## Setup

Install [Python](https://www.python.org/) version 3.14 or higher. If you're using MacOS or Linux, I
recommend using [pyenv](https://github.com/pyenv/pyenv). The bot is structed as a Python package,
so you can install it using this command:

```bash
pip install git+https://github.com/svioletg/lydian-discord-bot.git
```

This will install Lydian and its commands to your virtual environment if one is active, otherwise
it'll be available in your global Python environment. The bot can be updated in the future by
running `pip install -U git+https://github.com/svioletg/lydian-discord-bot.git`.

## Setup: Discord

TODO

## Usage

Lydian's main command is `lydian-start`, which will start running the bot. When attempting to run,
Lydian will check for a file named `lydian-config.toml` in your current working directory (the
directory you ran the command from), and will exit with an error if one is not present. If it does
see this file, it will begin to use that directory for storing data related to the bot like logs
and downloaded media. You should make a folder somewhere on your PC, for example named `lydian`,
make a new file called `lydian-config.toml` (ensure the file extension really *is* `.toml`), then
run `lydian-start` in that folder.

The bot can be stopped either by using the `stop` command, or hitting Ctrl+C while focused on the
window.

## Usage: Console

Lydian implements a basic console that can accept some limited commands while the bot is running:

|Command |Description                           |
|--------|--------------------------------------|
|`stop`  |Attempts to shut down the bot cleanly.|
