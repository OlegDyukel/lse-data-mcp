"""Creation and lifecycle of the upstream London Strategic Edge client."""

from functools import lru_cache

from lse import LSE

from lse_data_mcp.config import get_api_key, get_timeout_seconds


@lru_cache(maxsize=1)
def get_client() -> LSE:
    """Create one lazy SDK client for the lifetime of the MCP process."""
    return LSE(api_key=get_api_key(), timeout=get_timeout_seconds())
