"""Handles user permissions for interacting with the bot."""
import sys
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar, Self

import discord
import strictyaml as yaml

from lydian.const import PERMISSIONS_PATH
from lydian.util import DataclassUpdateMixin


@dataclass
class CommandPermissions(DataclassUpdateMixin):
    """Represents permission rules for an individual bot command."""

    whitelist: bool
    roles: list[str | int] = field(default_factory=list)

    def can_invoke(self, user: discord.Member) -> bool:
        """Returns whether a user can invoke this command based on their roles or username."""
        guild_role_id_map: dict[str, int] = {r.name:r.id for r in user.guild.roles}
        user_in_rules: bool = any(
            user.get_role(role if isinstance(role, int) else guild_role_id_map[role])
            for role in self.roles
        )
        return user_in_rules if self.whitelist else not user_in_rules

def _default_command_permissions_dict() -> dict[str, CommandPermissions]:
    return {'.default': CommandPermissions(whitelist=False)}

@dataclass
class Permissions(DataclassUpdateMixin):
    """Permission rules for the bot."""

    _yaml_schema: ClassVar[yaml.Map] = yaml.Map({
        'commands': yaml.MapPattern(yaml.Str(), yaml.Map({
            'whitelist': yaml.Bool(),
            'roles': yaml.Seq(yaml.Str() | yaml.Int()) | yaml.EmptyList(),
        })),
    })

    commands: dict[str, CommandPermissions] = field(default_factory=_default_command_permissions_dict)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> Self:
        """Returns a ``Permissions`` object parsed from a YAML string."""
        inst = cls()

        document: yaml.YAML = yaml.load(yaml_str, cls._yaml_schema)
        inst.commands = inst.commands | {
            command.data:CommandPermissions(**rules.data)
            for command, rules in document['commands'].items()
        }

        return inst

    def can_invoke(self, command: str, user: discord.Member) -> bool:
        """Returns whether a user can invoke a given command.

        If the command is not found, the rules set for ``.default`` are used.

        :param user: Either a Discord username (``str``) or user ID (``int``).
        """
        return self.commands.get(command, self.commands['.default']).can_invoke(user)

    def to_document(self) -> yaml.YAML:
        """Returns this object as a ``strictyaml.YAML`` document object."""
        return yaml.as_document(asdict(self), self._yaml_schema)

    def to_yaml(self, fp: str | Path | None = None) -> str:
        """Returns this object as a YAML string, and optionally writes its content to a file.

        :param fp: If given, will write the converted YAML content to this file.
        """
        document: yaml.YAML = self.to_document()
        yaml_str: str = document.as_yaml()
        if fp:
            Path(fp).write_text(yaml_str, 'utf-8')

        return yaml_str

PERMISSIONS_DEFAULT = Permissions()

perms = Permissions.from_yaml(PERMISSIONS_PATH.read_text('utf-8')) if PERMISSIONS_PATH.exists() else Permissions()

def main() -> int:
    """Write the default permissions as YAML to a given file path."""
    parser = ArgumentParser()
    parser.add_argument('-o', '--out', type=Path,
        help='A file to write the default config to. Written to stdout if not given.')

    args = parser.parse_args()
    dest: Path | None = args.out

    yaml_str: str = Permissions().to_yaml()

    if not dest:
        print(yaml_str)  # noqa: T201
        return 0

    dest.write_text(yaml_str, 'utf-8')
    print(f'Default permissions written to: {dest}')  # noqa: T201

    return 0

if __name__ == '__main__':
    sys.exit(main())
