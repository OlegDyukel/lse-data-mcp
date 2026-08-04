"""Storage of the API key in the operating system's own credential store.

``keyring`` delegates to Keychain on macOS, the Credential Locker on Windows,
and Secret Service or KWallet on a Linux desktop, so a stored key stays
encrypted at rest under the user's login session instead of sitting in plain
text inside an MCP client's configuration file.

A headless Linux session has no Secret Service to talk to. Every read here
treats an unavailable store as "no key stored" so that such a host falls
through to ``LSE_API_KEY`` rather than failing to start.
"""

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

KEYRING_SERVICE = "lse-data-mcp"
KEYRING_USERNAME = "default"

_UNAVAILABLE = (
    "This system has no usable credential store. On a headless Linux host, run the server "
    "with LSE_API_KEY set in its environment instead."
)

# Redaction re-reads the key on every tool failure, and a stored key cannot change
# while the server process runs, so one lookup is kept for the process lifetime.
_cached_key: tuple[str | None] | None = None


class CredentialStoreError(RuntimeError):
    """Raised when the credential store cannot complete a requested change."""


def reset_cache() -> None:
    """Forget the cached lookup so the next read consults the store again."""
    global _cached_key
    _cached_key = None


def get_stored_api_key() -> str | None:
    """Return the stored API key, or ``None`` when there is none to read."""
    global _cached_key
    if _cached_key is None:
        _cached_key = (_read_stored_api_key(),)
    return _cached_key[0]


def _read_stored_api_key() -> str | None:
    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except KeyringError:
        return None
    return (stored or "").strip() or None


def store_api_key(api_key: str) -> str:
    """Persist the key and return the name of the backend that accepted it."""
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
    except KeyringError as exc:
        raise CredentialStoreError(_UNAVAILABLE) from exc
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
        raise CredentialStoreError(_UNAVAILABLE) from exc
    reset_cache()
    return True


def describe_backend() -> str:
    """Return a human-readable name for the credential store in use."""
    backend = keyring.get_keyring()
    name = getattr(backend, "name", None)
    return str(name) if name else type(backend).__name__
