"""Utilities specifically for use in cog modules."""

from discord import Embed
from discord.ext import commands

from lydian.config import config
from lydian.const import COLOR_ERROR, COLOR_INFO, COLOR_OK, COLOR_WARN, EmojiStr


def alias_from_config[T: commands.Command](cmd: T) -> T:
    """Extends a command's ``aliases`` with the aliases defined in user configuration for that command.

    .. note::
        The command must be defined explicitly with an empty aliases list in order for this to work, like so:

        ```python
        @alias_from_config
        @commands.command(aliases=[])
        async def command(...):
        ```

        Otherwise, the aliases don't get added.
    """
    if not isinstance(cmd.aliases, list):
        raise TypeError(f'aliases must be a list for @alias_from_config decorator to work: {cmd!r}')
    cmd.aliases.extend(config.command_aliases.get(cmd.name, ()))
    return cmd

def embed_info(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with the embed color defined by ``const.COLOR_INFO``."""
    return Embed(title=title, description=description, color=COLOR_INFO)

def embed_ok(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a success icon and the embed color defined by ``const.COLOR_OK``."""
    return Embed(title=f'{EmojiStr.OK} ' + title, description=description, color=COLOR_OK)

def embed_warn(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a warning icon and the embed color defined by ``const.COLOR_WARN``."""
    return Embed(title=f'{EmojiStr.WARN} ' + title, description=description, color=COLOR_WARN)

def embed_error(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with an error icon and the embed color defined by ``const.COLOR_ERR``."""
    return Embed(title=f'{EmojiStr.ERROR} ' + title, description=description, color=COLOR_ERROR)
