"""FastMCP server definition and command-line entry point."""

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from lse_data_mcp.tools import (
    get_bond_yields,
    get_candles,
    get_company_profile,
    get_cot,
    get_dividends,
    get_economic_calendar,
    get_financial_reports,
    get_fundamentals,
    get_insider_transactions,
    get_option_candles,
    get_options,
    get_options_flow,
    get_reference,
    get_series,
    get_splits,
)

mcp = FastMCP(
    name="LSE Data Community Adapter",
    instructions=(
        "Read-only access to London Strategic Edge market data. "
        "The user must supply their own API key, through 'lse-data-mcp login' or LSE_API_KEY, "
        "and comply with the provider's terms."
    ),
)

_TOOLS: tuple[Callable[..., Any], ...] = (
    get_candles,
    get_company_profile,
    get_fundamentals,
    get_insider_transactions,
    get_dividends,
    get_splits,
    get_cot,
    get_bond_yields,
    get_financial_reports,
    get_options,
    get_option_candles,
    get_options_flow,
    get_economic_calendar,
    get_series,
    get_reference,
)

_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

for tool in _TOOLS:
    mcp.tool(annotations=_READ_ONLY_ANNOTATIONS)(tool)


def main() -> None:
    """Run the server over standard input/output for local MCP clients."""
    mcp.run(transport="stdio")
