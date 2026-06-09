"""Debugging or testing commands for development purposes."""
import discord
from discord import Embed
from discord.ext import commands
from loguru import logger

from lydian.cogs.util import confirm, embed_error, embed_info, embed_ok, embed_warn, paginated_message
from lydian.config import config
from lydian.const import debug_context


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

    @commands.command(checks=[debug_enabled])
    async def captureuser(self, ctx: commands.Context) -> None:
        """Stores the ``Member`` object of the command author to the debug dict under key ``'capture.user'``."""
        if not isinstance(ctx.author, discord.Member):
            raise TypeError(f'Expected type discord.Member: {ctx.author!r}')
        debug_context['capture.user'] = ctx.author
        await ctx.send(embed=embed_ok(''))

    @commands.command(checks=[debug_enabled])
    async def argstr(self, ctx: commands.Context, text: str) -> None:
        """Takes one string argument and echoes it back."""
        await ctx.send(text)

    @commands.command(checks=[debug_enabled])
    async def argint(self, ctx: commands.Context, num: int) -> None:
        """Takes one integer argument and echoes its ``repr``."""
        await ctx.send(repr(num))

    @commands.command(checks=[debug_enabled])
    async def pages(self, ctx: commands.Context) -> None:
        """Sends a paginated view."""
        pages = [
            embed_info('Page 1'),
            embed_info('Page 2'),
            embed_info('Page 3'),
            embed_info('Page 4'),
            embed_info('Page 5'),
        ]
        await paginated_message(ctx, pages)
