"""Tests for construction and caching of the upstream SDK client."""

from typing import Any

import pytest

from lse_data_mcp import client as client_module


def test_get_client_passes_key_and_timeout_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    calls: list[dict[str, Any]] = []

    def fake_lse(**kwargs: Any) -> object:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(client_module, "LSE", fake_lse)
    monkeypatch.setattr(client_module, "get_api_key", lambda: "synthetic-key")
    monkeypatch.setattr(client_module, "get_timeout_seconds", lambda: 12.5)
    client_module.get_client.cache_clear()

    try:
        assert client_module.get_client() is sentinel
        assert client_module.get_client() is sentinel
        assert calls == [{"api_key": "synthetic-key", "timeout": 12.5}]
    finally:
        client_module.get_client.cache_clear()
