"""Read-only MCP tool implementations backed by the official ``lse-data`` SDK."""

import functools
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict, cast, get_args

from anyio import to_thread
from lse import LSEError

from lse_data_mcp.client import get_client, get_secret_values
from lse_data_mcp.config import get_max_response_bytes

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

# Discovery endpoints, grouped because they take no meaningful arguments between
# them. Each name maps to the SDK method of the same name.
ReferenceResource = Literal[
    "catalog",
    "datasets",
    "reference",
    "vault_meta",
    "options_underlyings",
]

# The asset classes vault_meta reports under "datasets". Held locally so an
# unknown name costs no API call, and because upstream answers one with an empty
# result rather than an error: indistinguishable from a valid class holding no
# rows. The trap is that get_reference("reference") calls its own vocabulary
# "dataset" too — dividends, insider_trades, options_flow — and the two do not
# overlap, so a name carried from one to the other silently returns nothing.
Dataset = Literal[
    "bond_futures",
    "bonds",
    "commodity",
    "corporate_bonds",
    "credit_indices",
    "crypto",
    "currency_index",
    "economics",
    "etf",
    "futures",
    "fx",
    "fx_derivatives",
    "index",
    "interest_rates",
    "options",
    "sovereign_yields",
    "stocks",
    "volatility",
]
_DATASETS: frozenset[str] = frozenset(get_args(Dataset))

# The filter each resource accepts, if any. Anything else is refused rather than
# dropped, so a grouped tool cannot silently ignore an argument the caller meant.
_REFERENCE_FILTERS: dict[str, str | None] = {
    "catalog": "category",
    "datasets": "dataset",
    "reference": None,
    "vault_meta": None,
    "options_underlyings": None,
}

MAX_ROWS = 5_000
_MAX_MESSAGE_CHARS = 300
_MAX_ECHO_CHARS = 200


class ToolResponse(TypedDict):
    """Rows plus the metadata a caller needs to know whether it saw them all."""

    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    note: NotRequired[str | None]


def _validate_symbol(symbol: str) -> str:
    value = symbol.strip()
    if not value:
        raise ValueError("symbol must not be empty")
    return value


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be between 1 and {MAX_ROWS:,}")
    return limit


def _validate_timestamp(field: str, value: str | None) -> str | None:
    """Reject a malformed date locally rather than spending an API call on it."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"{field} must be an ISO 8601 date or timestamp, for example "
            f"2026-01-01 or 2026-01-01T14:30:00Z, not {text!r}"
        ) from None
    return text


def _fit_to_budget(rows: list[dict[str, Any]], budget: int) -> tuple[list[dict[str, Any]], bool]:
    """Return the longest prefix of ``rows`` whose JSON stays within ``budget``."""
    total = 2  # the enclosing brackets
    for index, row in enumerate(rows):
        total += len(json.dumps(row, default=str)) + 1  # the row plus its separator
        if total > budget:
            # Returning zero rows would tell the model nothing, so keep the first
            # even when it alone exceeds the budget; the note explains why.
            return rows[: max(index, 1)], True
    return rows, False


def _as_rows(result: Any) -> list[dict[str, Any]]:
    """Normalise an SDK result into rows; some endpoints return a single object."""
    if isinstance(result, dict):
        return [cast(dict[str, Any], result)]
    return cast(list[dict[str, Any]], result)


def _build_response(rows: list[dict[str, Any]]) -> ToolResponse:
    budget = get_max_response_bytes()
    kept, truncated = _fit_to_budget(rows, budget)
    response: ToolResponse = {
        "rows": kept,
        "row_count": len(kept),
        "truncated": truncated,
    }
    if truncated:
        response["note"] = (
            f"Returned the first {len(kept):,} of {len(rows):,} rows to stay within the "
            f"{budget:,}-byte response budget. Narrow the window with start and end, or "
            f"lower limit, to see the rest."
        )
    return response


def _safe_provider_message(message: str) -> str:
    for secret in get_secret_values():
        message = message.replace(secret, "[redacted]")
    return message[:_MAX_MESSAGE_CHARS]


def _echoable_detail(message: str) -> str | None:
    """Return upstream text only when it plainly reads as a short error string.

    The SDK falls back to the raw response body when it is not JSON, so an HTML
    error page, an edge block page, or anything else the network decides to
    return would otherwise land verbatim in the model's context. Echo the short
    structured messages that help the caller, and drop the rest.
    """
    text = " ".join(message.split())
    if not text or len(text) > _MAX_ECHO_CHARS:
        return None
    if "<" in text or ">" in text:  # markup, not an error string
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in text):  # escapes, control bytes
        return None
    return text


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
        detail = _echoable_detail(message) or "the upstream API rejected the request"

    status_suffix = f" (status {status})" if status else ""
    return RuntimeError(f"{prefix}{status_suffix}: {detail}")


def _unexpected_error(operation: str, exc: Exception) -> RuntimeError:
    """Wrap a failure the SDK does not report as ``LSEError``.

    The SDK leaks ``ValueError`` from decoding a malformed response body, and a
    future version may leak others. Wrapping keeps every failure redacted and
    keeps a bad upstream reply distinguishable from a bad tool argument.
    """
    name = type(exc).__name__
    detail = _echoable_detail(_safe_provider_message(str(exc)))
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
) -> ToolResponse:
    """Run a blocking SDK call off the event loop and normalise its result.

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
    return _build_response(_as_rows(rows))


async def get_candles(
    symbol: str,
    timeframe: Timeframe = "1d",
    start: str | None = None,
    end: str | None = None,
    limit: int = 200,
    order: Order = "asc",
) -> ToolResponse:
    """Return OHLCV candles for an instrument.

    Dates may be ISO 8601 dates or timestamps accepted by the upstream API.
    """
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
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


async def get_company_profile(symbol: str, limit: int = 200) -> ToolResponse:
    """Return company profile information for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    return await _call_upstream(
        "company profile",
        get_client().company_profiles,
        symbol,
        limit=limit,
    )


async def get_fundamentals(symbol: str, limit: int = 200) -> ToolResponse:
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
) -> ToolResponse:
    """Return reported insider transactions for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
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
) -> ToolResponse:
    """Return dividend events for a ticker."""
    symbol = _validate_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "dividends",
        get_client().dividends,
        symbol,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_reference(
    resource: ReferenceResource,
    category: str | None = None,
    dataset: Dataset | None = None,
) -> ToolResponse:
    """Return vault discovery data: what instruments, datasets and timeframes exist.

    ``catalog`` lists every instrument and its history span, filtered by
    ``category`` (stocks, forex, crypto, etf, commodity, index, options,
    futures, economics, bonds). ``datasets`` lists one row per dataset and
    symbol, filtered by ``dataset``. ``reference`` lists the reference datasets,
    ``vault_meta`` describes the vault's shape, and ``options_underlyings``
    lists every underlying with listed options.

    ``category`` applies only to ``catalog`` and ``dataset`` only to
    ``datasets``; supplying either elsewhere is an error rather than ignored.
    """
    supplied = {"category": category, "dataset": dataset}
    accepted = _REFERENCE_FILTERS[resource]
    for name, value in supplied.items():
        if value is not None and name != accepted:
            allowed = f"only {accepted!r}" if accepted else "no filters"
            raise ValueError(f"resource {resource!r} does not accept {name!r}; it takes {allowed}")

    if dataset is not None and dataset not in _DATASETS:
        raise ValueError(
            f"dataset {dataset!r} is not a known asset class; expected one of "
            f"{', '.join(sorted(_DATASETS))}. Note that the dataset names from "
            f"get_reference('reference') are a different vocabulary and are not accepted here."
        )

    kwargs = {accepted: supplied[accepted]} if accepted and supplied[accepted] else {}
    return await _call_upstream(
        f"reference {resource}",
        getattr(get_client(), resource),
        **kwargs,
    )


async def get_economic_calendar(
    region: str | None = None,
    event: str | None = None,
    start: str | None = None,
    end: str | None = None,
    released_only: bool = False,
    order: Order = "asc",
    limit: int = 200,
) -> ToolResponse:
    """Return scheduled economic events, optionally filtered by region and date."""
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
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
