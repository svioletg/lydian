"""Tools for constructing Lydian's -help command output."""
from collections.abc import Callable, Sequence
from inspect import iscoroutinefunction
from itertools import batched
from types import CoroutineType

import discord
from discord.ext.commands import Cog, Command, Context

from lydian.cogs.util import command_signature, embed_error, embed_info, paginated_message
from lydian.const import EmojiStr
from lydian.util import cog_commands, first_where, getclass


class HelpView(discord.ui.View):
    """The main "help" view for Lydian."""

    def __init__(self,
            cogs: Sequence[type[Cog] | Cog],
            choice_callback: Callable[[str | None], None] | Callable[[str | None], CoroutineType] | None = None,
            *,
            timeout: float | None = None,
        ) -> None:
        super().__init__(timeout=timeout)

        self.cogs = cogs
        self.choice_callback = choice_callback or (lambda *_: None)

        for cog in cogs:
            self.select.append_option(discord.SelectOption(
                label=cog.__cog_name__,
                value=getclass(cog).__name__,
                description=cog.__cog_description__,
                emoji=getattr(cog, 'emoji', EmojiStr.GEAR),
            ))

    @discord.ui.select(cls=discord.ui.Select)
    async def select(self, interaction: discord.Interaction, _select: discord.ui.Select) -> None:  # noqa: D102
        await interaction.response.defer()
        self.stop()

        choice = self.select.values[0] if self.select.values else None
        if iscoroutinefunction(self.choice_callback):
            await self.choice_callback(choice)  # ty:ignore[invalid-await] ; don't see where this would fail
        else:
            self.choice_callback(choice)

async def send_help_menu(ctx: Context, cogs: Sequence[type[Cog]]) -> discord.Message:
    """Sends the main help menu and returns the sent message."""
    embed = embed_info(title=f'{EmojiStr.INFO} Help', description='Choose a category below to view its commands.')

    embed.add_field(
        name='Command help syntax',
        value='Command arguments will be enclosed in either angle brackets (`<>`) or square brackets (`[]`).'
            + ' An argument in angle brackets is required, while an argument in square brackets is optional.'
            + " If the argument's name is followed by an ellipsis, it accepts multiple space-separated values."
            + ' Arguments are separated by spaces, if you need to pass an argument a value which contains a space,'
            + ' you must surround the text in quotes to ensure it is treated as one single value.',
        inline=False,
    )

    embed.add_field(name='Common commands:', value='', inline=False)

    for title, desc in (
            ('-play [url]', 'Add a track to the queue, or resume the player if paused and no URL is given'),
            ('-skip', 'Skip (or vote to skip) the current track'),
            ('-remove <index>', 'Remove the track at position <index> from the queue'),
            ('-nowplaying', "Show what's currently playing"),
            ('-queue [page]', 'Show the queue, optionally specifying which page'),
            ('-leave', 'Disconnect the bot from the current voice channel'),
        ):
        embed.add_field(name=title, value=desc, inline=True)

    msg: discord.Message
    view: HelpView

    async def callback(choice: str | None) -> None:
        view.select.placeholder = choice
        view.select.disabled = True
        await msg.edit(view=view)

        if choice is None:
            return
        cog = first_where(cogs, lambda cog: cog.__name__ == choice)
        if cog is None:
            await ctx.send(embed=embed_error(f'Failed to find cog for choice value: {choice}'))
            return
        await send_paginated_cog_help(ctx, cog)

    view = HelpView(cogs, callback)
    msg = await ctx.send(embed=embed, view=view)

    return msg

async def send_paginated_cog_help(ctx: Context, cog: type[Cog]) -> discord.Message:
    """Sends a paginated help message for a given cog."""
    await paginated_message(ctx, cog_help_embed(cog))

def cog_help_embed(cog: type[Cog]) -> list[discord.Embed]:
    """Returns a list of ``discord.Embed`` object showing paginated help for commands in the given cog."""
    commands: dict[str, Command] = cog_commands(cog)

    command_pages: tuple[tuple[Command, ...], ...] = tuple(batched(commands.values(), 10, strict=False))
    embed_pages: list[discord.Embed] = []

    for batch in command_pages:
        embed = embed_info(title=f'{EmojiStr.INFO} Help: {cog.__cog_name__}')
        embed_pages.append(embed)
        for command in batch:
            embed.add_field(name=f'`{command_signature(command)}`', value=command.help, inline=False)

    return embed_pages
