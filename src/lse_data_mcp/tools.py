"""Read-only MCP tool implementations backed by the official ``lse-data`` SDK."""

import functools
from collections.abc import Callable
from typing import Any, Literal, cast

from anyio import to_thread
from lse import LSEError

from lse_data_mcp.client import get_client, get_secret_values

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

MAX_ROWS = 5_000
_MAX_MESSAGE_CHARS = 300


def _validate_symbol(symbol: str) -> str:
    value = symbol.strip()
    if not value:
        raise ValueError("symbol must not be empty")
    return value


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be between 1 and {MAX_ROWS:,}")
    return limit


def _safe_provider_message(message: str) -> str:
    for secret in get_secret_values():
        message = message.replace(secret, "[redacted]")
    return message[:_MAX_MESSAGE_CHARS]


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


def _unexpected_error(operation: str, exc: Exception) -> RuntimeError:
    """Wrap a failure the SDK does not report as ``LSEError``.

    The SDK leaks ``ValueError`` from decoding a malformed response body, and a
    future version may leak others. Wrapping keeps every failure redacted and
    keeps a bad upstream reply distinguishable from a bad tool argument.
    """
    name = type(exc).__name__
    detail = _safe_provider_message(str(exc))
    suffix = f": {detail}" if detail else ""
    return RuntimeError(
        f"London Strategic Edge request failed during {operation}; "
        f"unexpected {name} from the upstream client{suffix}"
    )


async def _call_upstream(
    operation: str,
    method: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Run a blocking SDK call off the event loop and normalise its failures.

    Every SDK read is synchronous ``urllib``, so calling one inline would stall
    the whole server — including cancellations and other tool calls — for up to
    ``LSE_TIMEOUT_SECONDS``.
    """
    call = functools.partial(method, *args, **kwargs)
    try:
        rows = await to_thread.run_sync(call)
    except LSEError as exc:
        raise _translate_error(operation, exc) from exc
    except Exception as exc:
        raise _unexpected_error(operation, exc) from exc
    return cast(list[dict[str, Any]], rows)


async def get_candles(
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
    return await _call_upstream(
        "candles",
        get_client().candles,
        symbol,
        timeframe,
        start=start,
        end=end,
        limit=limit,
        order=order,
    )


async def get_company_profile(symbol: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return company profile information for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    return await _call_upstream(
        "company profile",
        get_client().company_profiles,
        symbol,
        limit=limit,
    )


async def get_fundamentals(symbol: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return fundamental data for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    return await _call_upstream(
        "fundamentals",
        get_client().fundamentals,
        symbol,
        limit=limit,
    )


async def get_insider_transactions(
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
    return await _call_upstream(
        "insider transactions",
        get_client().insider_trades,
        symbol,
        type=transaction_type,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_dividends(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return dividend events for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    return await _call_upstream(
        "dividends",
        get_client().dividends,
        symbol,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_economic_calendar(
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
    return await _call_upstream(
        "economic calendar",
        get_client().economic_calendar,
        region=region,
        event=event,
        start=start,
        end=end,
        released_only=released_only,
        order=order,
        limit=limit,
    )
