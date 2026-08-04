"""Storage of the API key in the operating system's own credential store.

``keyring`` delegates to Keychain on macOS, the Credential Locker on Windows,
and Secret Service or KWallet on a Linux desktop, so a stored key stays
encrypted at rest under the user's login session instead of sitting in plain
text inside an MCP client's configuration file.

A lookup can fail in two ways that must not be confused with each other, or
with success:

* the host has no credential store at all, which is usual on headless Linux;
* a store exists but this process cannot reach it, which is usual inside a
  sandbox or before the login session is unlocked.

Reporting either as "no key is configured" sends the user to re-run ``login``,
which cannot help and which may well have already succeeded. Every read
therefore returns why it found nothing, and only a store that answers
successfully with no entry counts as genuinely absent.
"""

from enum import Enum
from typing import NamedTuple

import keyring
from keyring.errors import KeyringError, NoKeyringError, PasswordDeleteError

KEYRING_SERVICE = "lse-data-mcp"
KEYRING_USERNAME = "default"


class CredentialStatus(Enum):
    """The outcome of asking the credential store for the API key."""

    STORED = "stored"
    ABSENT = "absent"
    NO_STORE = "no_store"
    INACCESSIBLE = "inaccessible"


class Credential(NamedTuple):
    """A lookup result: what was found, and why nothing was found."""

    status: CredentialStatus
    api_key: str | None


# Explaining which of the two unavailable states occurred is the whole point of
# distinguishing them: the remedies are different and neither is "log in again".
_UNAVAILABLE_REASON = {
    CredentialStatus.NO_STORE: (
        "This system has no credential store, which is usual on a headless Linux host."
    ),
    CredentialStatus.INACCESSIBLE: (
        "A credential store exists but this process cannot reach it, which is usual inside "
        "a sandbox or before the login session is unlocked. A key may already be stored; "
        "this process simply cannot read it."
    ),
}

# Redaction re-reads the key on every tool failure, and neither a stored key nor
# this process's access to the store changes while the server runs, so one
# lookup is kept for the process lifetime.
_cached: Credential | None = None


class CredentialStoreError(RuntimeError):
    """Raised when the credential store cannot complete a requested change."""


def reset_cache() -> None:
    """Forget the cached lookup so the next read consults the store again."""
    global _cached
    _cached = None


def read_credential() -> Credential:
    """Return the stored API key along with why it was or was not found."""
    global _cached
    if _cached is None:
        _cached = _read_credential()
    return _cached


def _read_credential() -> Credential:
    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except NoKeyringError:
        return Credential(CredentialStatus.NO_STORE, None)
    except KeyringError:
        # The backend's own message can carry account names and file paths, and
        # this text reaches MCP clients, so the cause is deliberately not repeated.
        return Credential(CredentialStatus.INACCESSIBLE, None)

    api_key = (stored or "").strip() or None
    if api_key is None:
        return Credential(CredentialStatus.ABSENT, None)
    return Credential(CredentialStatus.STORED, api_key)


def get_stored_api_key() -> str | None:
    """Return the stored API key, or ``None`` when there is none to read."""
    return read_credential().api_key


def describe_unavailable(status: CredentialStatus) -> str | None:
    """Explain an unreachable store, or return ``None`` when it answered fine."""
    return _UNAVAILABLE_REASON.get(status)


def store_api_key(api_key: str) -> str:
    """Persist the key and return the name of the backend that accepted it."""
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
    except KeyringError as exc:
        raise CredentialStoreError(_unavailable_message(exc)) from exc
    reset_cache()
    return describe_backend()


def delete_stored_api_key() -> bool:
    """Remove the stored key, reporting whether there was one to remove."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except PasswordDeleteError:
        reset_cache()
        return False
    except KeyringError as exc:
        raise CredentialStoreError(_unavailable_message(exc)) from exc
    reset_cache()
    return True


def _unavailable_message(exc: KeyringError) -> str:
    status = (
        CredentialStatus.NO_STORE
        if isinstance(exc, NoKeyringError)
        else CredentialStatus.INACCESSIBLE
    )
    return f"{_UNAVAILABLE_REASON[status]} Set LSE_API_KEY in the environment instead."


def describe_backend() -> str:
    """Return a human-readable name for the credential store in use."""
    backend = keyring.get_keyring()
    name = getattr(backend, "name", None)
    return str(name) if name else type(backend).__name__
