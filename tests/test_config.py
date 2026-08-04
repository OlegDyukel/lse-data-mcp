"""Tests for environment configuration."""

import pytest

from lse_data_mcp import config, credentials
from lse_data_mcp.config import (
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    ConfigurationError,
    get_api_key,
    get_api_key_if_set,
    get_max_response_bytes,
    get_timeout_seconds,
)


def test_get_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LSE_API_KEY", "  test-key  ")

    assert get_api_key() == "test-key"


def test_get_api_key_falls_back_to_the_credential_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setattr(
        config,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.STORED, "stored-key"),
    )

    assert get_api_key() == "stored-key"


def test_the_environment_wins_over_the_credential_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host that injects the key directly stays authoritative over a past login."""
    monkeypatch.setenv("LSE_API_KEY", "environment-key")
    monkeypatch.setattr(
        config,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.STORED, "stored-key"),
    )

    assert get_api_key() == "environment-key"


def test_get_api_key_if_set_reports_no_key_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)

    assert get_api_key_if_set() is None


def test_get_api_key_rejects_missing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="No London Strategic Edge API key"):
        get_api_key()


def test_a_missing_key_error_names_both_ways_to_supply_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setattr(
        config,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.ABSENT, None),
    )

    with pytest.raises(ConfigurationError) as raised:
        get_api_key()

    assert "lse-data-mcp login" in str(raised.value)
    assert "LSE_API_KEY" in str(raised.value)


def test_an_unusable_credential_store_does_not_break_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The autouse fixture models a headless host; resolution must still return."""
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    credentials.reset_cache()

    assert get_api_key_if_set() is None


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


def test_get_max_response_bytes_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LSE_MAX_RESPONSE_BYTES", raising=False)

    assert get_max_response_bytes() == DEFAULT_MAX_RESPONSE_BYTES


def test_get_max_response_bytes_accepts_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LSE_MAX_RESPONSE_BYTES", " 4096 ")

    assert get_max_response_bytes() == 4096


@pytest.mark.parametrize("value", ["", "nope", "0", "-1", "1.5"])
def test_get_max_response_bytes_rejects_invalid_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("LSE_MAX_RESPONSE_BYTES", value)

    with pytest.raises(ConfigurationError, match="must be a positive whole number"):
        get_max_response_bytes()


def test_an_unreachable_store_does_not_advise_logging_in_again(
    monkeypatch: pytest.MonkeyPatch, inaccessible_credential_store: None
) -> None:
    """Re-running login cannot fix a store this process is not allowed to read."""
    monkeypatch.delenv("LSE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError) as raised:
        get_api_key()

    message = str(raised.value)
    assert "cannot reach it" in message
    assert "LSE_API_KEY" in message
    assert "lse-data-mcp login" not in message


def test_a_host_with_no_store_is_told_so_rather_than_to_log_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)

    with pytest.raises(ConfigurationError) as raised:
        get_api_key()

    message = str(raised.value)
    assert "no credential store" in message
    assert "lse-data-mcp login" not in message


def test_a_reachable_but_empty_store_still_advises_logging_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.setattr(
        config,
        "read_credential",
        lambda: credentials.Credential(credentials.CredentialStatus.ABSENT, None),
    )

    with pytest.raises(ConfigurationError, match="lse-data-mcp login"):
        get_api_key()


def test_an_unreachable_store_still_falls_through_to_the_environment(
    monkeypatch: pytest.MonkeyPatch, inaccessible_credential_store: None
) -> None:
    """Diagnostics changed; the resolution order did not."""
    monkeypatch.setenv("LSE_API_KEY", "environment-key")

    assert get_api_key() == "environment-key"
