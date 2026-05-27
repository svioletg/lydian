"""General-purpose commands."""
from discord.ext import commands

from lydian.cogs.util import alias_from_config, embed_info
from lydian.const import GH_ISSUES, GH_REPO


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
