"""Debugging or testing commands for development purposes."""
from discord import Embed
from discord.ext import commands
from loguru import logger

from lydian.cogs.util import confirm, embed_error, embed_info, embed_ok, embed_warn
from lydian.config import config


def debug_enabled(_ctx: commands.Context) -> bool:
    """Returns whether debug mode is currently enabled in the config."""
    return config.debug

class DebugCog(commands.Cog):
    """Debugging or testing commands for development purposes."""

    @commands.command(checks=[debug_enabled])
    async def sendinfo(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_info` to make the embed."""
        await ctx.send(embed=embed_info('Information', 'Some general event has occurred.'))

    @commands.command(checks=[debug_enabled])
    async def sendok(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_ok` to make the embed."""
        await ctx.send(embed=embed_ok('Success', 'Everything is OK.'))

    @commands.command(checks=[debug_enabled])
    async def sendwarn(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_warn` to make the embed."""
        await ctx.send(embed=embed_warn('Warning', 'Something unexpected happened.'))

    @commands.command(checks=[debug_enabled])
    async def senderror(self, ctx: commands.Context) -> None:
        """Send a test message using :py:func:`lydian.cogs.util.embed_error` to make the embed."""
        await ctx.send(embed=embed_error('Error', 'Something failed.'))

    @commands.command(checks=[debug_enabled])
    async def promptyn(self, ctx: commands.Context, prompt_timeout: float | None = None) -> None:
        """Sends a message with button components.

        Accepts an optional argument to override the timeout in seconds.
        """
        response = await confirm(ctx, embed_info('Continue?'), prompt_timeout=prompt_timeout)
        match response:
            case True:
                await ctx.send(embed=embed_info('Confirmed.'))
            case False:
                await ctx.send(embed=embed_info('Cancelled.'))
            case _:
                await ctx.send(embed=embed_info('Prompt timed out.'))

    @commands.command(checks=[debug_enabled])
    async def fail(self, _ctx: commands.Context) -> None:
        """Raises a ``ValueError``."""
        logger.debug('Raising ValueError...')
        raise ValueError('Testing, testing!')
        logger.debug('Raised ValueError; this message should not be visible!')

    @commands.command(checks=[debug_enabled])
    async def bigembed(self, ctx: commands.Context) -> None:
        """Sends a variety of messages with more complicated ``discord.Embed``s."""
        embed = Embed(title='Test Embed', description='Description')

        for n in range(25):
            embed.add_field(name=f'inline embed #{n + 1}', value='value')

        await ctx.send(embed=embed)

        embed = Embed(title='Test Embed', description='Description')

        for n in range(25):
            embed.add_field(name=f'non-inline embed #{n + 1}', value='value', inline=False)

        await ctx.send(embed=embed)
