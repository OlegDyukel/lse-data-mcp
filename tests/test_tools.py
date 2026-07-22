"""Tests for MCP tool-to-SDK mappings using a fake upstream client."""

from typing import Any

import pytest
from lse import LSEError

from lse_data_mcp import tools


class FakeClient:
    """Small recording fake for the official SDK."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.error: LSEError | None = None

    def _record(self, name: str, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append((name, args, kwargs))
        if self.error is not None:
            raise self.error
        return [{"source": name}]

    def candles(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("candles", *args, **kwargs)

    def company_profiles(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("company_profiles", *args, **kwargs)

    def fundamentals(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("fundamentals", *args, **kwargs)

    def insider_trades(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("insider_trades", *args, **kwargs)

    def dividends(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("dividends", *args, **kwargs)

    def economic_calendar(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._record("economic_calendar", *args, **kwargs)


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(tools, "get_client", lambda: client)
    return client


def test_get_candles_maps_arguments(fake_client: FakeClient) -> None:
    result = tools.get_candles("AAPL", "1h", start="2026-01-01", limit=50, order="desc")

    assert result == [{"source": "candles"}]
    assert fake_client.calls == [
        (
            "candles",
            ("AAPL", "1h"),
            {
                "start": "2026-01-01",
                "end": None,
                "limit": 50,
                "order": "desc",
            },
        )
    ]


def test_get_candles_validates_limit(fake_client: FakeClient) -> None:
    with pytest.raises(ValueError, match="limit must be between"):
        tools.get_candles("AAPL", limit=0)

    assert fake_client.calls == []


def test_symbol_tools_reject_blank_symbol(fake_client: FakeClient) -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        tools.get_company_profile("  ")

    assert fake_client.calls == []


def test_get_company_profile_maps_upstream_method(fake_client: FakeClient) -> None:
    result = tools.get_company_profile(" AAPL ", limit=3)

    assert result == [{"source": "company_profiles"}]
    assert fake_client.calls == [("company_profiles", ("AAPL",), {"limit": 3})]


def test_get_fundamentals_maps_upstream_method(fake_client: FakeClient) -> None:
    result = tools.get_fundamentals("MSFT", limit=4)

    assert result == [{"source": "fundamentals"}]
    assert fake_client.calls == [("fundamentals", ("MSFT",), {"limit": 4})]


def test_get_insider_transactions_maps_upstream_method(fake_client: FakeClient) -> None:
    result = tools.get_insider_transactions("AAPL", transaction_type="P-Purchase")

    assert result == [{"source": "insider_trades"}]
    assert fake_client.calls == [
        (
            "insider_trades",
            ("AAPL",),
            {
                "type": "P-Purchase",
                "start": None,
                "end": None,
                "order": "desc",
                "limit": 200,
            },
        )
    ]


def test_get_dividends_maps_filters(fake_client: FakeClient) -> None:
    result = tools.get_dividends("AAPL", start="2026-01-01", order="asc", limit=10)

    assert result == [{"source": "dividends"}]
    assert fake_client.calls == [
        (
            "dividends",
            ("AAPL",),
            {
                "start": "2026-01-01",
                "end": None,
                "order": "asc",
                "limit": 10,
            },
        )
    ]


def test_get_economic_calendar_maps_filters(fake_client: FakeClient) -> None:
    result = tools.get_economic_calendar(
        region="US",
        event="CPI",
        start="2026-07-01",
        released_only=True,
        limit=25,
    )

    assert result == [{"source": "economic_calendar"}]
    assert fake_client.calls == [
        (
            "economic_calendar",
            (),
            {
                "region": "US",
                "event": "CPI",
                "start": "2026-07-01",
                "end": None,
                "released_only": True,
                "order": "asc",
                "limit": 25,
            },
        )
    ]


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (401, "invalid key", "authentication failed"),
        (403, "forbidden table", "subscription does not permit"),
        (429, "quota window exceeded", "rate limit was reached"),
        (0, "request failed: timed out", "request timed out"),
        (0, "connection refused", "could not be reached"),
        (503, "unavailable", "temporarily unavailable"),
    ],
)
def test_upstream_errors_are_actionable(
    fake_client: FakeClient, status: int, message: str, expected: str
) -> None:
    fake_client.error = LSEError(status, message)

    with pytest.raises(RuntimeError, match=expected):
        tools.get_candles("AAPL")


def test_upstream_error_redacts_api_key(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    api_key = "synthetic-secret-value"
    monkeypatch.setenv("LSE_API_KEY", api_key)
    fake_client.error = LSEError(400, f"bad request for {api_key}")

    with pytest.raises(RuntimeError) as error:
        tools.get_candles("AAPL")

    assert api_key not in str(error.value)
    assert "[redacted]" in str(error.value)
