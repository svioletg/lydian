import os
import shutil
from pathlib import Path

import pytest

from lydian.const import TESTS_DIR


@pytest.fixture
def tmpdir() -> Path:
    return TESTS_DIR / 'tmp'

def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    (TESTS_DIR / 'tmp').mkdir(exist_ok=True)

def pytest_sessionfinish(session: pytest.Session) -> None:  # noqa: ARG001
    if os.environ.get('PYTEST_KEEP_TMP') != '1':
        shutil.rmtree(TESTS_DIR / 'tmp')
