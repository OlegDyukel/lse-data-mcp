"""Creation and lifecycle of the upstream London Strategic Edge client."""

from functools import lru_cache

from lse import LSE

from lse_data_mcp.config import get_api_key, get_api_key_if_set, get_timeout_seconds

_active_api_key: str | None = None


@lru_cache(maxsize=1)
def get_client() -> LSE:
    """Create one lazy SDK client for the lifetime of the MCP process.

    The REST methods this server calls only read immutable instance state, so a
    single client is safe to share across the worker threads that run them.
    """
    global _active_api_key
    api_key = get_api_key()
    client = LSE(api_key=api_key, timeout=get_timeout_seconds())
    _active_api_key = api_key
    return client


def get_secret_values() -> tuple[str, ...]:
    """Return every form of the API key that must never reach a client message.

    The cached client keeps using the key it was built with, which can drift
    from the current environment value, so both are scrubbed. Longest first, so
    that a secret containing another is replaced before its substring.
    """
    candidates = {_active_api_key, get_api_key_if_set()}
    return tuple(sorted((value for value in candidates if value), key=len, reverse=True))
