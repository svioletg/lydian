from pathlib import Path

from lydian.perms import CommandPermissions, Permissions
from tests.conftest import mock_discord_member, mock_discord_role


def test_inst() -> None:
    assert Permissions()

def test_dump_load(tmpdir: Path) -> None:
    dest: Path = tmpdir / 'perms.yml'

    perms = Permissions()
    dumped: str = perms.to_yaml(dest)
    assert Permissions.from_yaml(dumped) == Permissions.from_yaml(dest.read_text('utf-8')) == perms

def test_can_invoke() -> None:
    user = mock_discord_member()
    role = mock_discord_role()
    user.guild.roles.append(role)

    perms = Permissions()
    assert perms.can_invoke('skip', user)

    perms.commands['skip'] = CommandPermissions(whitelist=True)
    assert not perms.can_invoke('skip', user)
    perms.commands['skip'].roles = [role.name]
    assert not perms.can_invoke('skip', user)
    user.roles.append(role)
    assert perms.can_invoke('skip', user)
    perms.commands['skip'].roles = [role.id]
    assert perms.can_invoke('skip', user)

    perms.commands['skip'].whitelist = False
    assert not perms.can_invoke('skip', user)
    user.roles.remove(role)
    assert perms.can_invoke('skip', user)
