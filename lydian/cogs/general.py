"""General-purpose commands."""
from typing import Any, cast

from discord.ext import commands
from rapidfuzz import process as fuzz

from lydian.cogs.util import alias_from_config, command_signature, embed_error, embed_info
from lydian.config import config
from lydian.const import GH_ISSUES, GH_REPO, EmojiStr
from lydian.help import send_help_menu
from lydian.util import getclass


class GeneralCog(commands.Cog):
    """General-purpose commands."""

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

    @alias_from_config
    @commands.command(aliases=[])
    async def hello(self, ctx: commands.Context) -> None:
        """Sends a simple 'Hello, world!' message to test that the bot is active."""
        await ctx.send(embed=embed_info('Hello, world!'))

    @alias_from_config
    @commands.command(aliases=[])
    async def help(self, ctx: commands.Context, command_name: str | None = None) -> None:
        """Shows help for a specified command if given, otherwise shows Lydian's full help menu."""
        if command_name is None:
            await send_help_menu(ctx, [getclass(cog) for cog in self.bot.cogs.values()])
            return
        if not (command := self.bot.all_commands.get(command_name)):
            # Use the commands set instead of all_commands so aliases aren't included
            close = fuzz.extract(command_name, (cmd.name for cmd in self.bot.commands), limit=5, score_cutoff=75)
            await ctx.send(embed=embed_error(
                f'No command named "{command_name}".',
                None if not close else f'Did you mean: {', '.join(f'"{i[0]}"' for i in close)}',
            ))
            return

        # all_commands values are typed None for the first type parameter of Command (the Cog), but in practice this
        # never seems to be the case, so just cast it
        command = cast('commands.Command[commands.Cog, Any, Any]', command)

        await ctx.send(embed=embed_info(
            f'{EmojiStr.INFO} Help: {getattr(command.cog, 'emoji', EmojiStr.GEAR)} {command.cog_name}:'
                + f' `{config.prefix}{command.name}`',
            f'{command_signature(command)}',
        ))

    @alias_from_config
    @commands.command(aliases=[])
    async def repo(self, ctx: commands.Context) -> None:
        """Sends a link to Lydian's GitHub repository."""
        await ctx.send(embed=embed_info(f"View Lydian's source on GitHub: {GH_REPO}"))

    @alias_from_config
    @commands.command(aliases=[])
    async def issues(self, ctx: commands.Context) -> None:
        """Sends a link to Lydian's issue tracker on GitHub."""
        await ctx.send(embed=embed_info(
            f'Issues: {GH_ISSUES}',
            'Use this link to submit bug reports or feature requests.',
        ))
