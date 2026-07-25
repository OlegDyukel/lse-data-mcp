"""Tests for MCP tool-to-SDK mappings using a fake upstream client."""

import time
from typing import Any

import anyio
import pytest
from lse import LSEError

from lse_data_mcp import tools


class FakeClient:
    """Small recording fake for the official SDK."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.error: Exception | None = None

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


@pytest.mark.anyio
async def test_get_candles_maps_arguments(fake_client: FakeClient) -> None:
    result = await tools.get_candles("AAPL", "1h", start="2026-01-01", limit=50, order="desc")

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


@pytest.mark.anyio
async def test_get_candles_validates_limit(fake_client: FakeClient) -> None:
    with pytest.raises(ValueError, match="limit must be between"):
        await tools.get_candles("AAPL", limit=0)

    assert fake_client.calls == []


@pytest.mark.anyio
async def test_symbol_tools_reject_blank_symbol(fake_client: FakeClient) -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        await tools.get_company_profile("  ")

    assert fake_client.calls == []


@pytest.mark.anyio
async def test_get_company_profile_maps_upstream_method(fake_client: FakeClient) -> None:
    result = await tools.get_company_profile(" AAPL ", limit=3)

    assert result == [{"source": "company_profiles"}]
    assert fake_client.calls == [("company_profiles", ("AAPL",), {"limit": 3})]


@pytest.mark.anyio
async def test_get_fundamentals_maps_upstream_method(fake_client: FakeClient) -> None:
    result = await tools.get_fundamentals("MSFT", limit=4)

    assert result == [{"source": "fundamentals"}]
    assert fake_client.calls == [("fundamentals", ("MSFT",), {"limit": 4})]


@pytest.mark.anyio
async def test_get_insider_transactions_maps_upstream_method(fake_client: FakeClient) -> None:
    result = await tools.get_insider_transactions("AAPL", transaction_type="P-Purchase")

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


@pytest.mark.anyio
async def test_get_dividends_maps_filters(fake_client: FakeClient) -> None:
    result = await tools.get_dividends("AAPL", start="2026-01-01", order="asc", limit=10)

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


@pytest.mark.anyio
async def test_get_economic_calendar_maps_filters(fake_client: FakeClient) -> None:
    result = await tools.get_economic_calendar(
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
@pytest.mark.anyio
async def test_upstream_errors_are_actionable(
    fake_client: FakeClient, status: int, message: str, expected: str
) -> None:
    fake_client.error = LSEError(status, message)

    with pytest.raises(RuntimeError, match=expected):
        await tools.get_candles("AAPL")


@pytest.mark.anyio
async def test_upstream_error_redacts_api_key(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    api_key = "synthetic-secret-value"
    monkeypatch.setenv("LSE_API_KEY", api_key)
    fake_client.error = LSEError(400, f"bad request for {api_key}")

    with pytest.raises(RuntimeError) as error:
        await tools.get_candles("AAPL")

    assert api_key not in str(error.value)
    assert "[redacted]" in str(error.value)


@pytest.mark.anyio
async def test_upstream_call_does_not_block_the_event_loop(fake_client: FakeClient) -> None:
    def blocking_candles(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        time.sleep(0.3)
        return [{"source": "candles"}]

    fake_client.candles = blocking_candles  # type: ignore[method-assign]
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        while True:
            await anyio.sleep(0.01)
            ticks += 1

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(tick)
        result = await tools.get_candles("AAPL")
        task_group.cancel_scope.cancel()

    assert result == [{"source": "candles"}]
    assert ticks > 0, "the event loop stalled while the upstream call was in flight"


@pytest.mark.anyio
async def test_non_lse_upstream_exception_is_translated(fake_client: FakeClient) -> None:
    fake_client.error = ValueError("Expecting value: line 1 column 1 (char 0)")

    with pytest.raises(RuntimeError, match="unexpected ValueError"):
        await tools.get_candles("AAPL")


@pytest.mark.anyio
async def test_upstream_error_redacts_short_api_key(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    api_key = "sk-1234"  # shorter than the old eight-character redaction floor
    monkeypatch.setenv("LSE_API_KEY", api_key)
    fake_client.error = LSEError(400, f"bad request for {api_key}")

    with pytest.raises(RuntimeError) as error:
        await tools.get_candles("AAPL")

    assert api_key not in str(error.value)


@pytest.mark.anyio
async def test_upstream_error_redacts_key_the_live_client_was_built_with(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cached client outlives an environment change; its key must still be scrubbed."""
    monkeypatch.setattr(tools, "get_secret_values", lambda: ("key-held-by-live-client",))
    monkeypatch.setenv("LSE_API_KEY", "a-different-later-value")
    fake_client.error = LSEError(400, "bad request for key-held-by-live-client")

    with pytest.raises(RuntimeError) as error:
        await tools.get_candles("AAPL")

    assert "key-held-by-live-client" not in str(error.value)
