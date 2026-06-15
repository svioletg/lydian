import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, Mock

import discord
import pytest
from discord.ext import commands

from lydian.const import TESTS_DIR, create_directories


@pytest.fixture
def tmpdir() -> Path:
    return TESTS_DIR / 'tmp'

@pytest.fixture
def sample_cog() -> type[commands.Cog]:
    class SampleCog(commands.Cog):
        def __init__(self, bot: commands.Bot) -> None:
            self.bot = bot

        def bot_name(self) -> str:
            if not self.bot.user:
                raise ValueError('Bot is not online, user is None')
            return self.bot.user.name

        @commands.command()
        async def greet(self, ctx: commands.Context) -> None:
            await ctx.send('Hello!')

    return SampleCog

#region MOCKS

def mock_discord_role(
        *,
        role_id: int = 1,
        name: str = 'Role',
        hoist: bool = False,
        position: int = 0,
    ) -> Mock[discord.Role]:
    role = MagicMock(discord.Role)
    role.id = role_id
    role.name = name
    role.hoist = hoist
    role.position = position

    return role

MOCK_ATEVERYONE_ROLE: Mock[discord.Role] = mock_discord_role(role_id=0, name='@everyone')

def mock_get_role(member: discord.Member, role_id: int) -> discord.Role | None:
    for role in member.roles:
        if role.id == role_id:
            return role
    return None

def mock_discord_member(
        *,
        name: str = 'username',
        user_id: int = 0,
        nick: str = 'Nickname',
        roles: list[discord.Role] | None = None,
    ) -> MagicMock[discord.Member]:
    member = MagicMock(discord.Member)
    member.name = name
    member.id = user_id
    member.nick = nick
    member.roles = [MOCK_ATEVERYONE_ROLE] + (roles or [])
    member.guild.roles = [MOCK_ATEVERYONE_ROLE]
    member.get_role = lambda role_id: mock_get_role(member, role_id)

    return member

#endregion MOCKS

def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    create_directories()
    tests_tmp: Path = (TESTS_DIR / 'tmp')
    if tests_tmp.is_dir():
        shutil.rmtree(tests_tmp)
    tests_tmp.mkdir()

def pytest_sessionfinish(session: pytest.Session) -> None:  # noqa: ARG001
    if os.environ.get('PYTEST_KEEP_TMP') != '1':
        shutil.rmtree(TESTS_DIR / 'tmp')
