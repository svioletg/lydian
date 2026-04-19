"""Debugging or testing commands for development purposes."""
from discord.ext import commands

from lydian.cogs.util import embed_error, embed_info, embed_ok, embed_warn


class DebugCog(commands.Cog):
    """Debugging or testing commands for development purposes."""

    @commands.command()
    async def sendinfo(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_info` to make the embed."""
        await ctx.send(embed=embed_info('Information', 'Some general event has occurred.'))

    @commands.command()
    async def sendok(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_ok` to make the embed."""
        await ctx.send(embed=embed_ok('Success', 'Everything is OK.'))

    @commands.command()
    async def sendwarn(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_warn` to make the embed."""
        await ctx.send(embed=embed_warn('Warning', 'Something unexpected happened.'))

    @commands.command()
    async def senderror(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_error` to make the embed."""
        await ctx.send(embed=embed_error('Error', 'Something failed.'))
