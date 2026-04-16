from __future__ import annotations

import re
from typing import Never


class ReadOnlyModifiedError(Exception):
    """Raised when attempting to update a ``ReadOnlyDict``."""

def _raise_for_readonly(self: ReadOnlyDict, *_: object, **__: object) -> Never:
    raise ReadOnlyModifiedError(self)

class ReadOnlyDict(dict):
    """Subclass of ``dict`` where any methods relating to updating values raises ``ReadOnlyModifiedError``."""

    __setitem__ = _raise_for_readonly
    __delitem__ = _raise_for_readonly
    pop         = _raise_for_readonly
    popitem     = _raise_for_readonly
    clear       = _raise_for_readonly
    update      = _raise_for_readonly

class ShouldRaise:
    """Class used for ``pytest`` parameters that should raise an error."""

    def __init__(self, exc: type[Exception], match: str | re.Pattern[str] | None = None) -> None:
        self.exc: type[Exception] = exc
        self.match: str | re.Pattern[str] | None = match
