"""Runtime configuration loaded from the process environment."""

import math
import os

DEFAULT_TIMEOUT_SECONDS = 60.0


class ConfigurationError(RuntimeError):
    """Raised when required server configuration is missing or invalid."""


def get_api_key() -> str:
    """Return the configured LSE API key without logging or persisting it."""
    api_key = os.getenv("LSE_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "LSE_API_KEY is not configured. Supply your own London Strategic Edge API key "
            "through the MCP client's environment configuration."
        )
    return api_key


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
