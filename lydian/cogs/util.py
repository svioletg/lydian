"""Utilities specifically for use in cog modules."""
import warnings
from collections.abc import Callable, Sequence
from typing import Literal, cast

import discord.ui
from discord import ButtonStyle, Embed
from discord.ext import commands

from lydian.config import config
from lydian.const import (
    DEFAULT_DISCORD_PAGINATED_VIEW_TIMEOUT,
    DEFAULT_DISCORD_PROMPT_TIMEOUT,
    EMBED_COLOR_ERROR,
    EMBED_COLOR_INFO,
    EMBED_COLOR_OK,
    EMBED_COLOR_WARN,
    EmojiStr,
)
from lydian.errors import AbortCommand

type ViewItemCallback[T: discord.ui.Item] = Callable[[discord.Interaction, T], None]

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

class ArrowButtonsView(discord.ui.View):
    """A view with back and forward arrow buttons."""

    def __init__(self,
            back_callback: ViewItemCallback[discord.ui.Button] | None = None,
            next_callback: ViewItemCallback[discord.ui.Button] | None = None,
            *,
            timeout: float | None = None,
        ) -> None:
        super().__init__(timeout=timeout)

        self.back = back_callback or (lambda *_: None)
        self.next = next_callback or (lambda *_: None)

        self.response: Literal[-1, 1] | None = None
        """Indicates which button was clicked; -1 for back, 1 for next, ``None`` if neither has been clicked yet."""

    @discord.ui.button(emoji=EmojiStr.BACK, style=ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # noqa: D102
        self.back(interaction, button)
        self.response = -1
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(emoji=EmojiStr.PLAY, style=ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # noqa: D102
        self.next(interaction, button)
        self.response = 1
        await interaction.response.defer()
        self.stop()

    async def wait_for_response(self) -> Literal[-1, 1] | None:
        """Waits for a button to be clicked, then returns the response.

        If ``None`` is returned, the view timed out.
        """
        await self.wait()

        return self.response

class DropdownView(discord.ui.View):
    """A view with a dropdown menu for selecting one option."""

    def __init__(self, options: list[discord.SelectOption], *, timeout: float | None = None) -> None:
        super().__init__(timeout=timeout)

        for opt in options:
            self.select.append_option(opt)

    @discord.ui.select(cls=discord.ui.Select)
    async def select(self, interaction: discord.Interaction, _select: discord.ui.Select) -> None:  # noqa: D102
        await interaction.response.defer()
        self.stop()

    async def wait_for_response(self, *, disable_after: bool = True) -> str | None:
        """Waits for a choice to be selected, then returns that choice's value.

        If ``None`` is returned, the view timed out.

        :param disable_after: Whether to disable the dropdown after receiving a response. This will not be reflected in
            the message unless it is edited and resent with this view again.
        """
        await self.wait()

        choice = self.select.values[0] if self.select.values else None

        if disable_after:
            if choice:
                self.select.placeholder = choice
            self.select.disabled = True

        return choice

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

def _paginated_message_set_button_visibility(view: ArrowButtonsView, index: int, minimum: int, maximum: int) -> None:
    view.back_button.disabled = False
    view.next_button.disabled = False
    if index == minimum:
        view.back_button.disabled = True
    if index == maximum:
        view.next_button.disabled = True

async def paginated_message(
        ctx: commands.Context,
        pages: Sequence[discord.Embed],
        *,
        start: int = 0,
        footer: bool = True,
    ) -> None:
    """Sends a message with back and forward arrow buttons which can flip through the given "pages" of embeds.

    .. warning::
        This function enters an infinite loop which does not exit until the arrow button view times out, and will block
        until then. The view's timeout is set to :py:data:`const.DEFAULT_DISCORD_PAGINATED_VIEW_TIMEOUT`.

    :param start: Which page to start on.
    :param footer: Whether to add a "Page X of Y" footer to each page embed. This will be added as a new line following
        the existing footer, if any.
    """
    current: int = start

    if footer:
        for n, embed in enumerate(pages, 1):
            embed.set_footer(text=f'{f'{embed.footer.text or ''}\n' if embed.footer.text else ''}'
                + f'Page {n} of {len(pages)}')

    msg: discord.Message | None = None

    while True:
        view = ArrowButtonsView(timeout=DEFAULT_DISCORD_PAGINATED_VIEW_TIMEOUT)
        _paginated_message_set_button_visibility(view, current, 0, len(pages) - 1)
        if msg:
            await msg.edit(embed=pages[current], view=view)
        else:
            msg = await ctx.send(embed=pages[current], view=view)
        response = await view.wait_for_response()
        if response is None:
            # Timed out
            return
        current += response

def cog_emoji(cog: type[commands.Cog] | commands.Cog) -> str:
    """Returns a cog's ``emoji`` attribute if it has one, otherwise returns the default cog emoji string."""
    return getattr(cog, 'emoji', EmojiStr.GEAR)

def command_signature(command: commands.Command) -> str:
    """Returns a "signature" for a given command to display in help text."""
    sig_parts: list[str] = [f'{config.prefix}{command.name}']

    for name, param in command.clean_params.items():
        part: str = name
        if param.kind is commands.Parameter.VAR_POSITIONAL:
            part += '...'
        part = f'<{part}>' if param.required else f'[{part}]'

        sig_parts.append(part)

    return ' '.join(sig_parts)

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
