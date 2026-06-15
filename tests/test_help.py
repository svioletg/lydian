from typing import TYPE_CHECKING, Any, Literal

import pytest
from discord.ext.commands import Parameter
from discord.types.embed import EmbedField

from lydian import help as cmdhelp
from lydian.const import EMBED_COLOR_INFO, EmojiStr
from lydian.util import expect

if TYPE_CHECKING:
    from tests.conftest import SampleCog


@pytest.mark.parametrize(('param_kwargs', 'expected'),
    params := [
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': str},
            {'name': '<x>', 'value': 'Type: text', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': int},
            {'name': '<x>', 'value': 'Type: integer', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': float},
            {'name': '<x>', 'value': 'Type: float', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': str | None,
            'default': None},
            {'name': '[x]', 'value': 'Type: text (optional)', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': str,
            'default': 'a'},
            {'name': '[x]', 'value': 'Type: text (optional; default: a)', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': int,
            'default': 1},
            {'name': '[x]', 'value': 'Type: integer (optional; default: 1)', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': Literal['a', 'b', 'c']},
            {'name': '<x>', 'value': 'Type: any one of: a, b, c', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.POSITIONAL_OR_KEYWORD, 'annotation': Literal['a', 'b', 'c'],
            'default': 'a'},
            {'name': '[x]', 'value': 'Type: any one of: a, b, c (optional; default: a)', 'inline': False},
        ),
        (
            {'name': 'x', 'kind': Parameter.VAR_POSITIONAL, 'annotation': str},
            {'name': '[x...]', 'value': 'Type: text (optional)', 'inline': False},
        ),
    ],
    ids=[
        f'{p['name']}-{p['kind']}-{p['annotation']}' for p, _ in params
    ],
)
def test_command_param_embed_field(param_kwargs: dict[str, Any], expected: EmbedField) -> None:
    param = Parameter(**param_kwargs)
    desc = 'An example parameter.'
    assert cmdhelp.command_param_embed_field(param) == expected
    assert cmdhelp.command_param_embed_field(param, desc) == expected | {'value': expected['value'] + f'\n{desc}'}

def test_command_help_embed(sample_cog: SampleCog) -> None:
    embed = cmdhelp.command_help_embed(sample_cog.greet)
    assert expect(embed.color).value == EMBED_COLOR_INFO
    # The title should have the cog's name but the cog_name attribute of commands isn't set until that cog is added to
    # a bot via bot.add_cog(cog), mocking complicates things more than necessary in this case so we just check for None
    assert embed.title == f'{EmojiStr.INFO} Help: {EmojiStr.GEAR} None: -greet'
    assert embed.description == '`-greet [name]`\n\nSends a greeting message, optionally using the provided name.' \
        + '\n\n**Arguments:**'

    arg_field = embed.fields[0]
    assert arg_field.name == '[name]'
    assert arg_field.value == 'Type: text (optional)'
    assert arg_field.inline is False
