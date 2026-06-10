"""Tools for constructing Lydian's -help command output."""
from collections.abc import Callable, Sequence
from itertools import batched

import discord
from discord.ext.commands import Cog, Command, Context

from lydian.cogs.util import embed_info, paginated_message
from lydian.const import EmojiStr
from lydian.util import cog_commands


class HelpView(discord.ui.View):
    """The main "help" view for Lydian."""

    def __init__(self,
            cogs: Sequence[type[Cog] | Cog],
            select_callback: Callable[[discord.Interaction, discord.ui.Select], None] | None = None,
            *,
            timeout: float | None = None,
        ) -> None:
        super().__init__(timeout=timeout)

        self.cogs = cogs
        self.select_callback = select_callback or (lambda *_: None)

        for cog in cogs:
            self.select.append_option(discord.SelectOption(
                label=cog.__cog_name__,
                value=(cog if isinstance(cog, type) else cog.__class__).__name__,
                description=cog.__cog_description__,
                emoji=getattr(cog, 'emoji', EmojiStr.GEAR),
            ))

    @discord.ui.select(cls=discord.ui.Select)
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:  # noqa: D102
        await interaction.response.defer()
        self.stop()

        self.select_callback(interaction, select)

async def send_help_menu(ctx: Context, cogs: Sequence[type[Cog] | Cog]) -> discord.Message:
    """Sends the main help menu and returns the sent message."""
    embed = embed_info(title=f'{EmojiStr.INFO} Help', description='Choose a category below to view its commands.')

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

    return await ctx.send(embed=embed, view=HelpView(cogs))

async def send_paginated_cog_help(ctx: Context, cog: type[Cog]) -> discord.Message:
    """Sends a paginated help message for a given cog."""
    await paginated_message(ctx, cog_help_embed(cog))

def cog_help_embed(cog: type[Cog]) -> list[discord.Embed]:
    """Returns a list of ``discord.Embed`` object showing paginated help for commands in the given cog."""
    commands: dict[str, Command] = cog_commands(cog)

    command_pages: tuple[tuple[tuple[str, Command], ...], ...] = tuple(batched(commands.items(), 20, strict=False))
    embed_pages: list[discord.Embed] = []

    for batch in command_pages:
        embed = embed_info(title=f'{EmojiStr.INFO} Help: {cog.__cog_name__}')
        embed_pages.append(embed)
        for name, command in batch:
            embed.add_field(name=name, value=command.help)

    return embed_pages
