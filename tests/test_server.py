"""Tests for the public MCP tool surface."""

import pytest

from lse_data_mcp import server


@pytest.mark.anyio
async def test_server_registers_only_six_read_only_tools() -> None:
    registered = await server.mcp.list_tools()

    assert {tool.name for tool in registered} == {
        "get_candles",
        "get_company_profile",
        "get_fundamentals",
        "get_insider_transactions",
        "get_dividends",
        "get_economic_calendar",
    }
    for tool in registered:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is True


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
