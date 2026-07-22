"""Read-only MCP tool implementations backed by the official ``lse-data`` SDK."""

import os
from typing import Any, Literal, cast

from lse import LSEError

from lse_data_mcp.client import get_client

Timeframe = Literal[
    "1s",
    "5s",
    "15s",
    "30s",
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
    "1w",
    "1mo",
]
Order = Literal["asc", "desc"]


def _validate_symbol(symbol: str) -> str:
    value = symbol.strip()
    if not value:
        raise ValueError("symbol must not be empty")
    return value


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= 5_000:
        raise ValueError("limit must be between 1 and 5,000")
    return limit


def _safe_provider_message(message: str) -> str:
    api_key = os.getenv("LSE_API_KEY", "").strip()
    if len(api_key) >= 8:
        message = message.replace(api_key, "[redacted]")
    return message[:300]


def _translate_error(operation: str, exc: LSEError) -> RuntimeError:
    status = exc.status
    message = _safe_provider_message(exc.message)
    lower_message = message.lower()
    prefix = f"London Strategic Edge request failed during {operation}"

    if status == 401:
        detail = "authentication failed; check that LSE_API_KEY is valid"
    elif status == 429 or "rate limit" in lower_message:
        detail = "the upstream rate limit was reached; wait before retrying and check usage"
    elif status in {402, 403} or any(
        term in lower_message for term in ("quota", "subscription", "forbidden table")
    ):
        detail = (
            "the API key or subscription does not permit this request; "
            "check the account's data access and remaining allowance"
        )
    elif status in {408, 504} or (
        status == 0 and any(term in lower_message for term in ("timed out", "timeout"))
    ):
        detail = "the upstream request timed out; retry later or increase LSE_TIMEOUT_SECONDS"
    elif status == 0:
        detail = "the upstream service could not be reached; check the network and retry"
    elif status >= 500:
        detail = "the upstream service is temporarily unavailable; retry later"
    else:
        detail = message or "the upstream API rejected the request"

    status_suffix = f" (status {status})" if status else ""
    return RuntimeError(f"{prefix}{status_suffix}: {detail}")


def get_candles(
    symbol: str,
    timeframe: Timeframe = "1d",
    start: str | None = None,
    end: str | None = None,
    limit: int = 200,
    order: Order = "asc",
) -> list[dict[str, Any]]:
    """Return OHLCV candles for an instrument.

    Dates may be ISO 8601 dates or timestamps accepted by the upstream API.
    """
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)

    try:
        return cast(
            list[dict[str, Any]],
            get_client().candles(
                symbol,
                timeframe,
                start=start,
                end=end,
                limit=limit,
                order=order,
            ),
        )
    except LSEError as exc:
        raise _translate_error("candles", exc) from exc


def get_company_profile(symbol: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return company profile information for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    try:
        return cast(list[dict[str, Any]], get_client().company_profiles(symbol, limit=limit))
    except LSEError as exc:
        raise _translate_error("company profile", exc) from exc


def get_fundamentals(symbol: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return fundamental data for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    try:
        return cast(list[dict[str, Any]], get_client().fundamentals(symbol, limit=limit))
    except LSEError as exc:
        raise _translate_error("fundamentals", exc) from exc


def get_insider_transactions(
    symbol: str,
    transaction_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return reported insider transactions for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    try:
        return cast(
            list[dict[str, Any]],
            get_client().insider_trades(
                symbol,
                type=transaction_type,
                start=start,
                end=end,
                order=order,
                limit=limit,
            ),
        )
    except LSEError as exc:
        raise _translate_error("insider transactions", exc) from exc


def get_dividends(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return dividend events for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    try:
        return cast(
            list[dict[str, Any]],
            get_client().dividends(
                symbol,
                start=start,
                end=end,
                order=order,
                limit=limit,
            ),
        )
    except LSEError as exc:
        raise _translate_error("dividends", exc) from exc


def get_economic_calendar(
    region: str | None = None,
    event: str | None = None,
    start: str | None = None,
    end: str | None = None,
    released_only: bool = False,
    order: Order = "asc",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return scheduled economic events, optionally filtered by region and date."""
    limit = _validate_limit(limit)
    try:
        return cast(
            list[dict[str, Any]],
            get_client().economic_calendar(
                region=region,
                event=event,
                start=start,
                end=end,
                released_only=released_only,
                order=order,
                limit=limit,
            ),
        )
    except LSEError as exc:
        raise _translate_error("economic calendar", exc) from exc
