from discord import Embed  # noqa: D100
from discord.ext import commands


class GeneralCog(commands.Cog):
    """General-purpose commands."""

    def __init__(self, bot: commands.bot.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def hello(self, ctx: commands.Context) -> None:
        """Test command."""
        await ctx.send(embed=Embed(title='Hello, world!'))
