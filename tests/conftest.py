import os
import shutil
from pathlib import Path

import pytest

from lydian.const import TESTS_DIR, create_directories


@pytest.fixture
def tmpdir() -> Path:
    return TESTS_DIR / 'tmp'

def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001
    create_directories()
    tests_tmp: Path = (TESTS_DIR / 'tmp')
    if tests_tmp.is_dir():
        shutil.rmtree(tests_tmp)
    tests_tmp.mkdir()

def pytest_sessionfinish(session: pytest.Session) -> None:  # noqa: ARG001
    if os.environ.get('PYTEST_KEEP_TMP') != '1':
        shutil.rmtree(TESTS_DIR / 'tmp')
