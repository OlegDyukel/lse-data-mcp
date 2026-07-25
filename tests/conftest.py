"""Shared fixtures for the test suite."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
