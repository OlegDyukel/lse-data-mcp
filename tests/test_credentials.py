"""Tests for the operating-system credential store."""

from typing import Any

import pytest
from keyring.errors import (
    KeyringError,
    KeyringLocked,
    NoKeyringError,
    PasswordDeleteError,
    PasswordSetError,
)

from lse_data_mcp import credentials
from lse_data_mcp.credentials import CredentialStatus


class FakeKeyring:
    """Stand-in for the ``keyring`` module, recording what the store was asked."""

    def __init__(
        self,
        stored: str | None = None,
        error: KeyringError | None = None,
        backend_name: str | None = "Fake Keyring",
    ) -> None:
        self.stored = stored
        self.error = error
        self.backend_name = backend_name
        self.calls: list[tuple[str, ...]] = []

    def _check(self) -> None:
        if self.error is not None:
            raise self.error

    def get_password(self, service: str, username: str) -> str | None:
        self.calls.append(("get", service, username))
        self._check()
        return self.stored

    def set_password(self, service: str, username: str, password: str) -> None:
        self.calls.append(("set", service, username))
        self._check()
        self.stored = password

    def delete_password(self, service: str, username: str) -> None:
        self.calls.append(("delete", service, username))
        self._check()
        if self.stored is None:
            raise PasswordDeleteError("not found")
        self.stored = None

    def get_keyring(self) -> Any:
        return type("Backend", (), {"name": self.backend_name})()


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    """Install a working fake store, replacing the suite-wide isolation fixture."""
    fake = FakeKeyring()
    monkeypatch.setattr(credentials, "keyring", fake)
    credentials.reset_cache()
    return fake


def test_read_returns_the_stored_key(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = "  stored-key  "

    assert credentials.read_credential() == credentials.Credential(
        CredentialStatus.STORED, "stored-key"
    )
    assert credentials.get_stored_api_key() == "stored-key"
    assert fake_keyring.calls == [
        ("get", credentials.KEYRING_SERVICE, credentials.KEYRING_USERNAME)
    ]


@pytest.mark.parametrize("stored", [None, "", "   "])
def test_read_treats_an_empty_entry_as_absent(
    fake_keyring: FakeKeyring, stored: str | None
) -> None:
    fake_keyring.stored = stored

    assert credentials.read_credential().status is CredentialStatus.ABSENT
    assert credentials.get_stored_api_key() is None


def test_a_host_with_no_credential_store_is_not_reported_as_an_absent_key(
    fake_keyring: FakeKeyring,
) -> None:
    """A headless Linux host must degrade to LSE_API_KEY, not fail to start."""
    fake_keyring.error = NoKeyringError("no backend")

    assert credentials.read_credential() == credentials.Credential(CredentialStatus.NO_STORE, None)
    assert credentials.get_stored_api_key() is None


def test_a_store_that_refuses_this_process_is_not_reported_as_an_absent_key(
    fake_keyring: FakeKeyring,
) -> None:
    """A sandbox denied Keychain must not be told that no key was ever stored."""
    fake_keyring.error = KeyringLocked("denied")

    assert credentials.read_credential() == credentials.Credential(
        CredentialStatus.INACCESSIBLE, None
    )
    assert credentials.get_stored_api_key() is None


def test_an_unreachable_store_is_distinguished_from_an_empty_one(
    fake_keyring: FakeKeyring,
) -> None:
    """The whole point: three outcomes, not two."""
    fake_keyring.stored = None
    assert credentials.describe_unavailable(credentials.read_credential().status) is None

    fake_keyring.error = KeyringLocked("denied")
    credentials.reset_cache()
    inaccessible = credentials.describe_unavailable(credentials.read_credential().status)

    fake_keyring.error = NoKeyringError("no backend")
    credentials.reset_cache()
    no_store = credentials.describe_unavailable(credentials.read_credential().status)

    assert inaccessible is not None
    assert no_store is not None
    assert inaccessible != no_store


def test_an_unreachable_store_never_repeats_the_backend_message(
    fake_keyring: FakeKeyring,
) -> None:
    """Backend text can carry account names and paths, and this reaches clients."""
    fake_keyring.error = KeyringLocked("/Users/someone/Library/Keychains/login.keychain-db")

    reason = credentials.describe_unavailable(credentials.read_credential().status)

    assert reason is not None
    assert "someone" not in reason


def test_read_is_cached_for_the_process_lifetime(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = "stored-key"

    assert credentials.get_stored_api_key() == "stored-key"
    assert credentials.get_stored_api_key() == "stored-key"

    assert len(fake_keyring.calls) == 1


def test_reset_cache_forces_a_fresh_read(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = "first-key"
    assert credentials.get_stored_api_key() == "first-key"

    fake_keyring.stored = "second-key"
    credentials.reset_cache()

    assert credentials.get_stored_api_key() == "second-key"


def test_store_writes_the_key_and_reports_the_backend(fake_keyring: FakeKeyring) -> None:
    assert credentials.store_api_key("new-key") == "Fake Keyring"
    assert fake_keyring.stored == "new-key"


def test_store_invalidates_the_cached_read(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = "old-key"
    assert credentials.get_stored_api_key() == "old-key"

    credentials.store_api_key("new-key")

    assert credentials.get_stored_api_key() == "new-key"


def test_store_reports_an_unusable_credential_store(fake_keyring: FakeKeyring) -> None:
    fake_keyring.error = PasswordSetError("read only")

    with pytest.raises(credentials.CredentialStoreError, match="cannot reach it"):
        credentials.store_api_key("new-key")


def test_delete_removes_a_stored_key(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = "stored-key"

    assert credentials.delete_stored_api_key() is True
    assert fake_keyring.stored is None
    assert credentials.get_stored_api_key() is None


def test_delete_reports_when_there_was_nothing_to_remove(fake_keyring: FakeKeyring) -> None:
    fake_keyring.stored = None

    assert credentials.delete_stored_api_key() is False


def test_delete_reports_a_host_with_no_credential_store(fake_keyring: FakeKeyring) -> None:
    fake_keyring.error = NoKeyringError("no backend")

    with pytest.raises(credentials.CredentialStoreError, match="no credential store"):
        credentials.delete_stored_api_key()


def test_describe_backend_falls_back_to_the_class_name(fake_keyring: FakeKeyring) -> None:
    fake_keyring.backend_name = None

    assert credentials.describe_backend() == "Backend"


def test_the_stored_key_never_appears_in_a_credential_store_error(
    fake_keyring: FakeKeyring,
) -> None:
    fake_keyring.error = PasswordSetError("read only")

    with pytest.raises(credentials.CredentialStoreError) as raised:
        credentials.store_api_key("super-secret-key")

    assert "super-secret-key" not in str(raised.value)
