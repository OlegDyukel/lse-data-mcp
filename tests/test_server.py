"""Tests for the public MCP tool surface."""

import pytest

from lse_data_mcp import server


@pytest.mark.anyio
async def test_server_registers_the_read_only_tool_surface() -> None:
    registered = await server.mcp.list_tools()

    assert {tool.name for tool in registered} == {
        "get_candles",
        "get_company_profile",
        "get_fundamentals",
        "get_insider_transactions",
        "get_dividends",
        "get_splits",
        "get_cot",
        "get_bond_yields",
        "get_financial_reports",
        "get_options",
        "get_option_candles",
        "get_options_flow",
        "get_series",
        "get_economic_calendar",
        "get_reference",
    }
    for tool in registered:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is True


@pytest.mark.anyio
async def test_tool_output_schema_allows_fastmcp_optional_note_default() -> None:
    """FastMCP serializes an omitted optional output field as ``None``."""
    registered = await server.mcp.list_tools()

    for tool in registered:
        assert tool.outputSchema is not None
        note_schema = tool.outputSchema["properties"]["note"]
        assert {"type": "null"} in note_schema["anyOf"]


def test_every_tool_is_registered_as_a_coroutine() -> None:
    """FastMCP awaits async tools and calls sync ones inline, stalling the loop."""
    tools = server.mcp._tool_manager.list_tools()

    assert tools
    for tool in tools:
        assert tool.is_async, f"{tool.name} would block the event loop for the whole request"


def test_main_uses_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    transports: list[str] = []
    monkeypatch.setattr(
        server.mcp,
        "run",
        lambda *, transport: transports.append(transport),
    )

    server.main()

    assert transports == ["stdio"]


async def _description(name: str) -> str:
    registered = await server.mcp.list_tools()
    tool = next(tool for tool in registered if tool.name == name)
    assert tool.description is not None
    return tool.description


@pytest.mark.anyio
async def test_fundamentals_description_warns_the_snapshot_price_is_stale() -> None:
    """``current_price`` and everything derived from it lag ``updated_at``."""
    description = await _description("get_fundamentals")

    assert "updated_at" in description
    assert "get_candles" in description
    for derived in ("market_cap", "pe_ratio", "dividend_yield"):
        assert derived in description


@pytest.mark.anyio
async def test_dividends_description_distinguishes_the_four_date_fields() -> None:
    """``start``/``end`` filter the ex-date only, and the labels are unreliable."""
    description = await _description("get_dividends")

    for field in ("effective_date", "declaration_date", "record_date", "payment_date"):
        assert field in description
    assert "dividend_type" in description
    assert "frequency" in description


@pytest.mark.anyio
async def test_insider_transactions_description_warns_about_codes_and_price() -> None:
    """Direction is ``acquisition_or_disposition``; exercises report ``price`` 0."""
    description = await _description("get_insider_transactions")

    assert "M-Exempt" in description
    assert "acquisition_or_disposition" in description
    assert "F-InKind" in description
    assert "price" in description
