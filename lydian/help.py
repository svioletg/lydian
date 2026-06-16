"""Tools for constructing Lydian's -help command output."""
from collections.abc import Callable, Sequence
from inspect import iscoroutinefunction
from itertools import batched
from types import CoroutineType, NoneType
from typing import Literal, Union, get_args, get_origin

import discord
from discord.ext.commands import Cog, Command, Context, Parameter
from discord.types.embed import EmbedField

from lydian.cogs.util import cog_emoji, command_signature, embed_error, embed_info, paginated_message
from lydian.config import config
from lydian.const import DOCSTRING_PARAM_REGEX, EmojiStr
from lydian.util import cog_commands, first_where, getclass

TYPE_NAME_MAP: dict[type, str] = {
    str: 'text',
    int: 'integer',
}

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
                emoji=cog_emoji(cog),
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
        await paginated_message(ctx, cog_help_embed(cog))

    view = HelpView(cogs, callback)
    msg = await ctx.send(embed=embed, view=view)

    return msg

def cog_help_embed(cog: type[Cog]) -> list[discord.Embed]:
    """Returns a list of ``discord.Embed`` object showing paginated help for commands in the given cog."""
    commands: dict[str, Command] = cog_commands(cog)

    command_pages: tuple[tuple[Command, ...], ...] = tuple(batched(commands.values(), 10, strict=False))
    embed_pages: list[discord.Embed] = []

    for batch in command_pages:
        embed = embed_info(title=f'{EmojiStr.INFO} Help: {cog_emoji(cog)}{cog.__cog_name__}')
        embed.set_footer(text='Use `-help <command>` for more detailed info.')
        for command in batch:
            embed.add_field(
                name=f'{command_signature(command)}',
                value=DOCSTRING_PARAM_REGEX.sub('', command.help or ''),
                inline=False,
            )

        embed_pages.append(embed)

    return embed_pages

def command_param_embed_field(param: Parameter, description: str | None = None) -> EmbedField:
    """Returns Discord embed field arguments for a command parameter."""
    is_var_pos: bool = param.kind is Parameter.VAR_POSITIONAL

    typ = param.annotation
    t_origin = get_origin(typ)
    t_args = get_args(typ)

    type_str: str = str(param.annotation)

    if t_origin is Union:
        if not ((len(t_args) == 2) and (t_args[1] is NoneType)):  # noqa: PLR2004
            raise TypeError(f'Command parameters can only be unions if they are T | None: {param.annotation}')
        typ = t_args[0]
        t_origin = get_origin(typ)
        t_args = get_args(typ)

    if t_origin is Literal:
        type_str = f'any one of: {', '.join(str(i) for i in t_args)}'
    else:
        if t_args:
            raise ValueError(f'Non-Literal or Union type "{typ}" has type argument: {t_args}')
        type_str = TYPE_NAME_MAP.get(typ, typ.__name__)

    # For VAR_POSITIONAL parameters, while param.required is True (likely since you can't specify a default for them),
    # passing no values for that arguments is considered valid, so it's more accurate to treat it as optional
    #
    # Commands that take at least 1 of a variable number of values should have one positional arg followed by the
    # variable positional arg, like (query: str, *additional_queries: str)

    if (param.default is not Parameter.empty) or is_var_pos:
        type_str += ' (optional)' if param.default in [None, Parameter.empty] \
            else f' (optional; default: {param.default})'

    name: str = param.displayed_name or param.name
    name = f'{param.name}...' if is_var_pos else param.name
    name = f'<{name}>' if param.required and not is_var_pos else f'[{name}]'

    value = f'> Type: {type_str}'
    if description:
        value += f'\n{description}'

    return {
        'name': name,
        'value': value,
        'inline': False,
    }

def command_help_embed(command: Command) -> discord.Embed:
    """Returns a ``discord.Embed`` object describing how to use a command."""
    param_help: dict[str, str] = {
        m.group('name'):m.group('desc').strip() for m in DOCSTRING_PARAM_REGEX.finditer(command.help or '')
    }

    command.help = DOCSTRING_PARAM_REGEX.sub('', command.help or '').strip()

    embed = embed_info(
        f'{EmojiStr.INFO} Help: {cog_emoji(command.cog)} {command.cog_name}:'
            + f' {config.prefix}{command.name}',
        f'`{command_signature(command)}`\n\n{command.help}' + ('\n\n**Arguments:**' if command.params else ''),
    )

    for param in command.clean_params.values():
        embed.add_field(**command_param_embed_field(param, param_help.get(param.name)))

    return embed
