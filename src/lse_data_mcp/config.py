"""Runtime configuration loaded from the process environment."""

import math
import os

from lse_data_mcp.credentials import describe_unavailable, read_credential

DEFAULT_TIMEOUT_SECONDS = 60.0

# A single interactive page can reach 5,000 rows, which is far more JSON than an
# agent can usefully hold. Cap what one tool call spends of the model's context.
DEFAULT_MAX_RESPONSE_BYTES = 128 * 1024


class ConfigurationError(RuntimeError):
    """Raised when required server configuration is missing or invalid."""


def get_api_key_if_set() -> str | None:
    """Return the configured API key, or ``None`` when it is absent.

    Redaction needs the key without the failure mode of :func:`get_api_key`, so
    resolving it stays owned by this module. The environment wins over the
    credential store, which keeps a host that injects the key directly - a
    container, a CI job, a client with its own secret manager - authoritative
    over whatever an earlier ``lse-data-mcp login`` left on the machine.
    """
    from_environment = os.getenv("LSE_API_KEY", "").strip()
    if from_environment:
        return from_environment
    return read_credential().api_key


def get_api_key() -> str:
    """Return the configured LSE API key without logging or persisting it."""
    api_key = get_api_key_if_set()
    if not api_key:
        raise ConfigurationError(_missing_api_key_message())
    return api_key


def _missing_api_key_message() -> str:
    """Explain what to do about a missing key, given why the store found none.

    Telling someone to run ``login`` when the store is simply unreachable sends
    them to re-do work that may already be done and cannot fix anything.
    """
    unavailable = describe_unavailable(read_credential().status)
    if unavailable:
        return (
            f"No London Strategic Edge API key is available. {unavailable} "
            "Set LSE_API_KEY in the MCP client's environment configuration."
        )
    return (
        "No London Strategic Edge API key is configured. Run 'lse-data-mcp login' to "
        "store your own key in this system's credential store, or set LSE_API_KEY in "
        "the MCP client's environment configuration."
    )


def get_timeout_seconds() -> float:
    """Return the timeout used for each upstream REST request."""
    raw_value = os.getenv("LSE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError("LSE_TIMEOUT_SECONDS must be a positive number.") from exc

    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigurationError("LSE_TIMEOUT_SECONDS must be a positive number.")
    return timeout


def get_max_response_bytes() -> int:
    """Return the serialized-JSON budget a single tool result may occupy."""
    raw_value = os.getenv("LSE_MAX_RESPONSE_BYTES", str(DEFAULT_MAX_RESPONSE_BYTES)).strip()
    try:
        max_bytes = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError("LSE_MAX_RESPONSE_BYTES must be a positive whole number.") from exc

    if max_bytes <= 0:
        raise ConfigurationError("LSE_MAX_RESPONSE_BYTES must be a positive whole number.")
    return max_bytes
