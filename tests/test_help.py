from typing import Any, Literal

import pytest
from discord.ext.commands import Parameter
from discord.types.embed import EmbedField

from lydian import help as cmdhelp


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
    assert cmdhelp.command_param_embed_field(param) == expected
