"""Shared fixtures for the test suite."""

from typing import Any, NoReturn

import pytest
from keyring.errors import KeyringLocked, NoKeyringError

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


class _InaccessibleCredentialStore(_NoCredentialStore):
    """A store that exists but refuses this process, as a sandbox does."""

    def _unavailable(self, *args: object, **kwargs: object) -> NoReturn:
        raise KeyringLocked("the credential store denied this process")

    get_password = _unavailable
    set_password = _unavailable
    delete_password = _unavailable


@pytest.fixture(autouse=True)
def isolated_credential_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite away from the real credential store of the host running it.

    Without this, whether a developer has run ``lse-data-mcp login`` would decide
    if the "no key configured" tests pass, and the suite could write to a real
    Keychain. Tests that need a working store replace this with their own fake.
    """
    monkeypatch.setattr(credentials, "keyring", _NoCredentialStore())
    credentials.reset_cache()


@pytest.fixture
def inaccessible_credential_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model a sandboxed process: the store exists, but refuses this caller."""
    monkeypatch.setattr(credentials, "keyring", _InaccessibleCredentialStore())
    credentials.reset_cache()
