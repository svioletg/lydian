"""General-purpose commands."""
from discord.ext import commands

from lydian.cogs.util import embed_info


class GeneralCog(commands.Cog):
    """General-purpose commands."""

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def hello(self, ctx: commands.Context) -> None:
        """Test command."""
        await ctx.send(embed=embed_info('Hello, world!'))
