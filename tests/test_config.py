"""Tests for environment configuration."""

import pytest

from lse_data_mcp.config import (
    DEFAULT_TIMEOUT_SECONDS,
    ConfigurationError,
    get_api_key,
    get_timeout_seconds,
)


def test_get_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LSE_API_KEY", "  test-key  ")

    assert get_api_key() == "test-key"


def test_get_api_key_rejects_missing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="LSE_API_KEY is not configured"):
        get_api_key()


def test_get_timeout_seconds_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_TIMEOUT_SECONDS", raising=False)

    assert get_timeout_seconds() == DEFAULT_TIMEOUT_SECONDS


def test_get_timeout_seconds_accepts_positive_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LSE_TIMEOUT_SECONDS", " 12.5 ")

    assert get_timeout_seconds() == 12.5


@pytest.mark.parametrize("value", ["", "nope", "0", "-1", "nan", "inf"])
def test_get_timeout_seconds_rejects_invalid_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("LSE_TIMEOUT_SECONDS", value)

    with pytest.raises(ConfigurationError, match="must be a positive number"):
        get_timeout_seconds()
