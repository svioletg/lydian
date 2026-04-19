"""Utilities specifically for use in cog modules."""
from discord import Embed

from lydian.const import COLOR_ERR, COLOR_INFO, COLOR_OK, COLOR_WARN


def embed_info(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with an info icon and the embed color defined by ``const.COLOR_INFO``."""
    return Embed(title=title, description=description, color=COLOR_INFO)

def embed_ok(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a success icon and the embed color defined by ``const.COLOR_OK``."""
    return Embed(title=title, description=description, color=COLOR_OK)

def embed_warn(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with a warning icon and the embed color defined by ``const.COLOR_WARN``."""
    return Embed(title=title, description=description, color=COLOR_WARN)

def embed_error(title: str, description: str | None = None) -> Embed:
    """Returns an ``Embed`` with an error icon and the embed color defined by ``const.COLOR_ERR``."""
    return Embed(title=title, description=description, color=COLOR_ERR)
