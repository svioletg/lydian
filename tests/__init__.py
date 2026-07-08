from __future__ import annotations

import re


class ShouldRaise:
    """Class used for ``pytest`` parameters that should raise an error."""

    def __init__(self, exc: type[Exception], match: str | re.Pattern[str] | None = None) -> None:
        self.exc: type[Exception] = exc
        self.match: str | re.Pattern[str] | None = match
