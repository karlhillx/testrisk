"""Deterministic terminal output in tests."""

import pytest

from testgap.ui import configure_ui


@pytest.fixture(autouse=True)
def _reset_ui():
    configure_ui(color="never", quiet=False, unicode=False)
    yield
    configure_ui(color="never", quiet=False, unicode=False)
