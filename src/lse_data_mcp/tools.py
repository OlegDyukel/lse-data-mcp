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
OptionType = Literal["call", "put"]

# The three statements the provider documents. Closed vocabulary, so an enum in
# the tool schema stops a wrong value before it costs an API call.
ReportType = Literal["income", "balance", "cashflow"]

# The provider documents "FY" and "a quarter like Q1" without enumerating the
# rest. These five are the whole of that convention; if the vault ever serves a
# period outside it, this becomes a plain string rather than gaining a member.
ReportPeriod = Literal["FY", "Q1", "Q2", "Q3", "Q4"]

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

# One financial statement is a whole nested object, so a row here is far larger
# than a candle or a dividend and the usual 200 would truncate nearly every
# call. Twenty rows is five years of quarterly reports, or twenty years of
# annual ones, which answers most questions inside one response budget.
FINANCIAL_REPORT_LIMIT = 20


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


def _validate_optional_symbol(symbol: str | None) -> str | None:
    """Validate a symbol only when one is given; ``None`` means every symbol.

    These endpoints treat the symbol as optional upstream, and narrowing that to
    "required" here would be this adapter inventing a restriction the provider
    does not impose.
    """
    return None if symbol is None else _validate_symbol(symbol)


def _validate_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be between 1 and {MAX_ROWS:,}")
    return limit


def _validate_dataset(dataset: Dataset | None) -> Dataset | None:
    """Reject an unknown asset class locally, where upstream would return no rows."""
    if dataset is not None and dataset not in _DATASETS:
        raise ValueError(
            f"dataset {dataset!r} is not a known asset class; expected one of "
            f"{', '.join(sorted(_DATASETS))}. Note that the dataset names from "
            f"get_reference('reference') are a different vocabulary and are not accepted here."
        )
    return dataset


def _validate_days_to_expiry(min_dte: int | None, max_dte: int | None) -> None:
    for field, value in (("min_dte", min_dte), ("max_dte", max_dte)):
        if value is not None and value < 0:
            raise ValueError(f"{field} must not be negative")
    if min_dte is not None and max_dte is not None and min_dte > max_dte:
        raise ValueError("min_dte must not exceed max_dte")


def _resolve_strike(
    strike: float | None,
    strike_min: float | None,
    strike_max: float | None,
) -> float | tuple[float, float] | None:
    """Collapse the two ways of naming strikes into the single upstream argument.

    Upstream takes one strike or a ``(low, high)`` tuple in the same parameter.
    A JSON tool schema cannot express that without a polymorphic field, which a
    model reads wrongly often enough to matter, so the tool exposes one scalar
    and one explicit window and rejects any combination that means two things.
    """
    if strike is not None and (strike_min is not None or strike_max is not None):
        raise ValueError(
            "pass strike for a single strike, or strike_min with strike_max for a window, "
            "but not both"
        )
    if strike is not None:
        return strike
    if strike_min is None and strike_max is None:
        return None
    if strike_min is None or strike_max is None:
        raise ValueError("a strike window needs both strike_min and strike_max")
    if strike_min > strike_max:
        raise ValueError("strike_min must not exceed strike_max")
    return (strike_min, strike_max)


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

    US equity bars cover the extended session, 08:00-23:00 UTC (04:00-19:00
    ET), not the regular session. A daily ``close`` is therefore the last
    post-market print rather than the 16:00 ET closing auction, so it differs
    from the close quoted by most retail sources, usually by a few cents and in
    either direction. Say which close you are quoting, and do not treat a
    difference from another source as an error.

    Treat ``volume`` as indicative only. Measured Aug 2026 against Financial
    Modeling Prep over fifteen sessions of IBM, it ranged from 45% to 106% of
    that source's figure, with no stable pattern, so it does not support
    liquidity, participation or turnover claims.

    ``start`` and ``end`` filter by date. The upstream API rejects an intraday
    timestamp here, so narrow a ``1s`` or ``1m`` window by filtering the rows
    that come back.
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
    """Return a point-in-time fundamentals snapshot for a ticker.

    One row per symbol - market cap, PE, margins, 52-week range, dividend
    yield - not a history, so there is nothing here to compare across time and
    ``limit`` makes little difference.

    The row is a snapshot taken at ``updated_at``, not live. ``current_price``
    is that snapshot's price, and ``market_cap``, ``pe_ratio`` and
    ``dividend_yield`` are derived from it, so they all age together and can
    disagree with the latest close. Quote ``updated_at`` alongside them, and
    take a current price from ``get_candles`` rather than from this row.
    """
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
    """Return reported SEC Form 3/4/5 insider transactions for a ticker.

    ``transaction_type`` takes an SEC code, such as ``P-Purchase``, ``S-Sale``,
    ``M-Exempt`` or ``F-InKind``. An unrecognised value returns zero rows
    rather than an error, so a guessed code is indistinguishable from a genuine
    quiet period - prefer omitting it and filtering the rows yourself.

    Direction is ``acquisition_or_disposition`` (``A`` or ``D``), not
    ``transaction_type``: ``M-Exempt`` appears in both directions. ``price`` is
    0 on exercises and grants, so ``securities_transacted`` times ``price``
    understates value, and ``F-InKind`` is stock withheld to cover tax rather
    than an open-market sale. One filing expands into several rows - a single
    vest can produce an exercise, a withholding and a disposal - so rows are
    legs, not trades, and counting them overstates activity.

    ``start`` and ``end`` filter ``transaction_date``. ``filing_date`` is
    separate and later, and rows are ingested later still, so a window over
    recent dates keeps filling in after the fact.
    """
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
    """Return dividend events for a ticker, newest first by default.

    ``start`` and ``end`` filter ``effective_date``, the ex-date. Each row also
    carries ``declaration_date``, ``record_date`` and ``payment_date``, which
    fall in different months - a May ex-date can pay in June - so a question
    about when a dividend was *paid* is not answered by this window. Read the
    date the question actually asks about out of the row.

    ``dividend_type`` and ``frequency`` are not a controlled vocabulary: the
    same quarterly dividend appears as ``CD`` and as ``Regular``, and its
    ``frequency`` as both ``4`` and ``Quarterly``. Do not filter or group on
    either; use the dates and ``dividend_amount``.
    """
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


async def get_splits(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = 200,
) -> ToolResponse:
    """Return stock split events, newest first by default.

    ``start`` and ``end`` filter the effective date, not the announcement date.
    Omit ``symbol`` to see splits across every instrument.

    A split rebases historical prices and share counts, so a per-share figure
    compared across one is not comparing like with like. Check for a split in
    the window before reading a price or earnings series through it.
    """
    symbol = _validate_optional_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "splits",
        get_client().splits,
        symbol,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_cot(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "asc",
    limit: int = 200,
) -> ToolResponse:
    """Return CFTC Commitments of Traders positioning, oldest first by default.

    One row per futures market per week: commercial, non-commercial and
    non-reportable long and short positions, open interest, and week-over-week
    changes. ``symbol`` is a futures market; omit it for every market.

    The CFTC publishes on Friday for the position date of the preceding
    Tuesday, so the newest row lags the market by several days. Treat it as a
    weekly positioning survey, never as a current position.
    """
    symbol = _validate_optional_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "commitments of traders",
        get_client().cot,
        symbol,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_bond_yields(
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "asc",
    limit: int = 200,
) -> ToolResponse:
    """Return government bond yield history, oldest first by default.

    Daily open, high, low and close per tenor symbol — ``US10Y``, ``DE02Y`` and
    the like — covering 31 countries back to 1990. Omit ``symbol`` for every
    tenor. Use ``get_reference('catalog', category='bonds')`` to discover which
    tenors exist.

    Values are yields in percent, not prices: they move inversely to the bond's
    price, and a "high" is the day's highest yield, which is its lowest price.
    """
    symbol = _validate_optional_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "bond yields",
        get_client().bond_yields,
        symbol,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_financial_reports(
    symbol: str | None = None,
    report_type: ReportType | None = None,
    period: ReportPeriod | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = FINANCIAL_REPORT_LIMIT,
) -> ToolResponse:
    """Return company financial statements, most recent first by default.

    ``report_type`` selects the income statement, balance sheet or cash flow
    statement; omitting it returns every type. ``period`` selects the full year
    (``FY``) or a single quarter (``Q1`` through ``Q4``). Omit ``symbol`` for
    every company.

    Each row carries the whole statement in its ``data`` field, already parsed,
    so rows are much larger here than for other tools and the default ``limit``
    is correspondingly lower. Raise it only as far as a request needs; a wide
    window will report ``truncated``.

    Filter by ``report_type`` and ``period`` rather than reading one figure out
    of an unfiltered result: income, balance and cash flow rows carry different
    fields, and an annual row is not comparable with a quarterly one.
    """
    symbol = _validate_optional_symbol(symbol)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "financial reports",
        get_client().financial_reports,
        symbol,
        report_type=report_type,
        period=period,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_options(
    underlying: str,
    option_type: OptionType | None = None,
    expiry: str | None = None,
    strike: float | None = None,
    strike_min: float | None = None,
    strike_max: float | None = None,
    min_dte: int | None = None,
    max_dte: int | None = None,
    limit: int = 200,
) -> ToolResponse:
    """Return the current option chain for an underlying, one row per contract.

    Each row carries the latest traded price, implied volatility, greeks, and
    today's volume and premium totals, plus its OSI ticker for drilling into
    ``get_option_candles``. ``underlying`` accepts a ticker or a company name
    ("AAPL", "apple", "Nvidia").

    Narrow the chain with ``expiry`` (one date), ``strike`` (one strike) or
    ``strike_min`` with ``strike_max`` (an inclusive window), and ``min_dte``
    with ``max_dte`` (a days-to-expiry window). A whole chain on a liquid name
    runs to thousands of contracts, so an unfiltered call will report
    ``truncated``; filter rather than raising ``limit``.

    This is a live snapshot, not history: it refreshes while the market is open
    and carries no timestamp of its own.
    """
    underlying = _validate_symbol(underlying)
    limit = _validate_limit(limit)
    expiry = _validate_timestamp("expiry", expiry)
    _validate_days_to_expiry(min_dte, max_dte)
    return await _call_upstream(
        "options chain",
        get_client().options,
        underlying,
        type=option_type,
        expiry=expiry,
        strike=_resolve_strike(strike, strike_min, strike_max),
        min_dte=min_dte,
        max_dte=max_dte,
        limit=limit,
    )


async def get_option_candles(
    contract: str,
    strike: float | None = None,
    expiry: str | None = None,
    option_type: OptionType | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "asc",
    limit: int = 200,
) -> ToolResponse:
    """Return one-minute premium OHLC history for a single option contract.

    Each bar carries volume, premium and greeks averaged over the minute.

    Name the contract either way. Pass a full OSI ticker alone, as
    ``contract="AAPL260612C00205000"``, or pass the underlying with the
    contract's terms, as ``contract="AAPL"`` with ``strike=205``,
    ``expiry="2026-06-12"`` and ``option_type="call"``. Get an OSI ticker from
    ``get_options``.

    Bars are premium, not the underlying's price. The trailing days are folded
    from live prints and agree with ``get_options_flow``; older history comes
    from the compacted archive.
    """
    contract = _validate_symbol(contract)
    limit = _validate_limit(limit)
    expiry = _validate_timestamp("expiry", expiry)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "option candles",
        get_client().option_candles,
        contract,
        strike=strike,
        expiry=expiry,
        type=option_type,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_options_flow(
    underlying: str | None = None,
    option_type: OptionType | None = None,
    min_premium: float | None = None,
    expiry: str | None = None,
    max_dte: int | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "desc",
    limit: int = 200,
) -> ToolResponse:
    """Return recent option prints - time and sales - newest first by default.

    One row per trade, with its premium, implied volatility and greeks as at
    the print. Omit ``underlying`` to sweep the whole tape, which is what
    ``min_premium`` is for: every print above $250,000 across all names.

    This covers the trailing week only. For anything older, use
    ``get_option_candles``, which serves the same trades as one-minute bars.
    """
    underlying = _validate_optional_symbol(underlying)
    limit = _validate_limit(limit)
    expiry = _validate_timestamp("expiry", expiry)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    _validate_days_to_expiry(None, max_dte)
    return await _call_upstream(
        "options flow",
        get_client().options_flow,
        underlying,
        type=option_type,
        min_premium=min_premium,
        expiry=expiry,
        max_dte=max_dte,
        start=start,
        end=end,
        order=order,
        limit=limit,
    )


async def get_series(
    symbol: str,
    dataset: Dataset | None = None,
    start: str | None = None,
    end: str | None = None,
    order: Order = "asc",
    limit: int = 200,
) -> ToolResponse:
    """Return one ``(date, value)`` observation series from the vault.

    This is the general series accessor: any macro economics series, any bond
    yield tenor, and any series-shaped dataset added later. The asset class is
    resolved from the catalog, so ``get_series('cpi_yoy')`` for US inflation and
    ``get_series('US10Y')`` for the ten-year yield both work without saying
    which is which. Supply ``dataset`` only to disambiguate a symbol that two
    classes both claim.

    Use ``get_reference('datasets', dataset='economics')`` to list the economics
    series that exist, with each one's observation count and span.

    For a bond tenor this returns one value per date. ``get_bond_yields`` serves
    the same tenors as daily open, high, low and close, so prefer that when the
    intraday range matters and this when a single series is what you want.
    """
    symbol = _validate_symbol(symbol)
    _validate_dataset(dataset)
    limit = _validate_limit(limit)
    start = _validate_timestamp("start", start)
    end = _validate_timestamp("end", end)
    return await _call_upstream(
        "series",
        get_client().series,
        symbol,
        dataset=dataset,
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

    _validate_dataset(dataset)

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
