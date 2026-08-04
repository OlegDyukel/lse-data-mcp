"""Shared fixtures for the test suite."""

from typing import Any, NoReturn

import pytest
from keyring.errors import NoKeyringError

from lse_data_mcp import credentials


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _NoCredentialStore:
    """A ``keyring`` stand-in for a host with no usable credential store."""

    def _unavailable(self, *args: object, **kwargs: object) -> NoReturn:
        raise NoKeyringError("no credential store in the test environment")

    get_password = _unavailable
    set_password = _unavailable
    delete_password = _unavailable

    def get_keyring(self) -> Any:
        return type("NoBackend", (), {"name": "No Credential Store"})()


@pytest.fixture(autouse=True)
def isolated_credential_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite away from the real credential store of the host running it.

    Without this, whether a developer has run ``lse-data-mcp login`` would decide
    if the "no key configured" tests pass, and the suite could write to a real
    Keychain. Tests that need a working store replace this with their own fake.
    """
    monkeypatch.setattr(credentials, "keyring", _NoCredentialStore())
    credentials.reset_cache()
