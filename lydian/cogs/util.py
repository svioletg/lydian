"""Utilities specifically for use in cog modules."""
import warnings
from typing import cast

import discord.ui
from discord import ButtonStyle, Embed
from discord.ext import commands

from lydian.config import config
from lydian.const import (
    DEFAULT_DISCORD_PROMPT_TIMEOUT,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_INFO,
    EMBED_COLOR_OK,
    EMBED_COLOR_WARN,
    EmojiStr,
)
from lydian.errors import AbortCommand


class ConfirmViewResponseWarning(Warning):
    """Emitted when trying to access the ``response`` attribute of a :py:class:`ConfirmView` before it has finished."""

class ConfirmView(discord.ui.View):
    """A basic Yes/No prompt for Discord messages."""

    def __init__(self, *, timeout: float | None = None) -> None:
        super().__init__(timeout=timeout or DEFAULT_DISCORD_PROMPT_TIMEOUT)
        self._response: bool | None = None

    @property
    def response(self) -> bool | None:
        """``True`` if "Yes" was clicked, ``False`` if "No", or ``None`` if the prompt timed out."""
        if not self.is_finished():
            warnings.warn(
                'Getting ConfirmView.response value before interacting has finished will always return ``None``;'\
                + ' call ConfirmView.wait() before reading',
                ConfirmViewResponseWarning,
                stacklevel=2,
            )
        return self._response

    @response.setter
    def response(self, value: bool | None) -> None:
        self._response = value

    @discord.ui.button(id=0, emoji=EmojiStr.CONFIRM, label='Yes', style=ButtonStyle.green)
    async def _yes_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._on_response(interaction)
        self.response = True

    @discord.ui.button(emoji=EmojiStr.CANCEL, label='No', style=ButtonStyle.red)
    async def _no_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._on_response(interaction)
        self.response = False

    async def _on_response(self, interaction: discord.Interaction) -> None:
        await cast('discord.InteractionResponse', interaction.response).defer()
        self.stop()

    def response_or_abort(self) -> bool:
        """Returns the ``response`` if not ``None``, otherwise raises :py:class:`~lydian.errors.AbortCommand`."""
        if self.response is None:
            raise AbortCommand
        return self.response

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

async def confirm(ctx: commands.Context, embed: Embed, *, prompt_timeout: float | None = None) -> bool | None:
    """Sends a message with a :py:class:`ConfirmView`, waits for the response, and returns it."""
    msg = await ctx.send(embed=embed, view=(prompt := ConfirmView(timeout=prompt_timeout)))
    await prompt.wait()
    await msg.edit(view=None)
    return prompt.response

def embed_info(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with the embed color defined by ``const.COLOR_INFO``."""
    return Embed(title=title, description=description, color=EMBED_COLOR_INFO)

def embed_ok(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a success icon and the embed color defined by ``const.COLOR_OK``."""
    return Embed(title=f'{EmojiStr.OK} ' + title, description=description, color=EMBED_COLOR_OK)

def embed_warn(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a warning icon and the embed color defined by ``const.COLOR_WARN``."""
    return Embed(title=f'{EmojiStr.WARN} ' + title, description=description, color=EMBED_COLOR_WARN)

def embed_error(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with an error icon and the embed color defined by ``const.COLOR_ERR``."""
    return Embed(title=f'{EmojiStr.ERROR} ' + title, description=description, color=EMBED_COLOR_ERROR)
