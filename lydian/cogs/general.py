"""General-purpose commands."""
from discord.ext import commands

from lydian.cogs.util import alias_from_config, embed_info


class GeneralCog(commands.Cog):
    """General-purpose commands."""

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

    @alias_from_config
    @commands.command(aliases=[])
    async def hello(self, ctx: commands.Context) -> None:
        """Sends a simple 'Hello, world!' message to test that the bot is active."""
        await ctx.send(embed=embed_info('Hello, world!'))
