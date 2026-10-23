"""Pytest test configuration and fixtures."""

import os
import pytest

@pytest.fixture(autouse=True)
def default_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test suite runs in mock mode by default unless explicitly overridden."""
    monkeypatch.setenv("SKEPTID_MODE", "mock")
