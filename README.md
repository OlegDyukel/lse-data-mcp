# lse-data-mcp

An unofficial, read-only Model Context Protocol (MCP) server for the
[London Strategic Edge](https://londonstrategicedge.com/) market-data API.

> **Status:** Alpha. The MCP tool surface may change before the first stable release.

The server lets an MCP client query London Strategic Edge data through the official
[`lse-data`](https://pypi.org/project/lse-data/) Python SDK. It runs locally over standard
input/output, uses the API key supplied by the user, returns the upstream JSON-compatible rows,
and does not cache or persist responses.

## Supported tools

All tools are declared read-only, non-destructive, and idempotent in their MCP metadata.

Every tool returns the same envelope, so a caller can always tell whether it saw the full result:

```json
{
  "rows": [{ "timestamp": "2026-01-02T00:00:00Z", "close": 187.4, "volume": 41230100 }],
  "row_count": 1,
  "truncated": false
}
```

When the rows would exceed the response budget the server returns the leading rows it can fit,
sets `"truncated": true`, and adds a `note` explaining how to narrow the request. Rows are never
silently dropped.

| Tool | What it returns | Main filters |
| --- | --- | --- |
| `get_candles` | OHLCV candles for an instrument | `symbol`, `timeframe`, `start`, `end`, `limit`, `order` |
| `get_company_profile` | Company reference and listing information | `symbol`, `limit` |
| `get_fundamentals` | Snapshot company fundamentals | `symbol`, `limit` |
| `get_insider_transactions` | Reported insider transactions | `symbol`, `transaction_type`, `start`, `end`, `limit`, `order` |
| `get_dividends` | Dividend events | `symbol`, `start`, `end`, `limit`, `order` |
| `get_splits` | Stock split events | `symbol`, `start`, `end`, `limit`, `order` |
| `get_cot` | CFTC Commitments of Traders positioning | `symbol`, `start`, `end`, `limit`, `order` |
| `get_bond_yields` | Government bond yield history per tenor | `symbol`, `start`, `end`, `limit`, `order` |
| `get_economic_calendar` | Scheduled or released economic events | `region`, `event`, `start`, `end`, `released_only`, `limit`, `order` |
| `get_reference` | Vault discovery: instruments, datasets, timeframes | `resource`, `category`, `dataset` |

`get_reference` groups five discovery endpoints — `catalog`, `datasets`, `reference`,
`vault_meta`, `options_underlyings` — behind one `resource` argument, because they take
almost no arguments between them. `category` applies only to `catalog` and `dataset` only to
`datasets`; passing either to a resource that ignores it is an **error, not a silent no-op**,
so a grouped tool can never quietly drop a filter you meant. Data tools stay one-to-one with
their SDK method, where every argument is always meaningful.

`get_reference("catalog")` covers 22,000+ instruments, so expect `truncated: true` unless you
filter by `category`.

Each call defaults to at most 200 rows. The upstream API caps a single interactive call at 5,000
rows; use `start` and `end` to request narrower windows.

`start` and `end` accept an ISO 8601 date or timestamp (`2026-01-01`, `2026-01-01T14:30:00Z`).
Anything else is rejected locally, so a malformed date costs no API call and no quota.

## Obtain an API key

1. Visit the official [London Strategic Edge data page](https://londonstrategicedge.com/data/).
2. Follow the site's prompts to obtain your own API key.
3. Store it with `lse-data-mcp login`, which prompts without echoing and saves the key to the
   operating system's own credential store.

Never commit the key to this repository or put a real key in an issue, test, example, or log.

## Requirements

- Python 3.11 or newer
- A London Strategic Edge API key

## Installation

First confirm the interpreter you are about to use is 3.11 or newer:

```bash
python3 --version
```

macOS ships an older `python3` than this project supports, so that command often reports 3.9.
Install a supported one with `brew install python@3.13`, then use it by name — `python3.13`
instead of `python3` — in the first command below. On Windows, use `py -3.13`.

```bash
git clone https://github.com/OlegDyukel/lse-data-mcp.git
cd lse-data-mcp
python3 -m venv .venv           # or python3.13 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install .
```

Activating the virtual environment is what puts `lse-data-mcp` on your `PATH`. In a shell where
you have not activated it, call it by its full path instead:
`/absolute/path/to/lse-data-mcp/.venv/bin/lse-data-mcp`.

For development, install the test and quality tools too:

```bash
python -m pip install -e ".[dev]"
```

## Supplying the API key

Store the key once, in the credential store your operating system already provides:

```bash
lse-data-mcp login     # prompts without echoing; nothing is written to a file
lse-data-mcp status    # reports where the key resolves from, without printing it
lse-data-mcp logout    # removes the stored key
```

`login` never accepts the key as a command-line argument, because anything in `argv` reaches
shell history and the process list.

| Platform | Where the key is kept |
| --- | --- |
| macOS | Keychain |
| Windows | Credential Locker |
| Linux desktop | Secret Service (GNOME Keyring) or KWallet |

The server resolves its key in this order:

1. the `LSE_API_KEY` environment variable, when set and non-empty;
2. the credential store written by `lse-data-mcp login`;
3. otherwise it reports that no key is configured and names both ways to supply one.

The environment wins so that a host injecting the key directly — a container, a CI job, or an MCP
client with its own secret manager — stays authoritative over whatever an earlier `login` left on
the machine.

**Headless hosts.** Secret Service needs a D-Bus session, so a container, an SSH session, or a
server install has no credential store to read. Those hosts fall through to `LSE_API_KEY` rather
than failing to start; set it in the environment there.

### When the server cannot find your key

`lse-data-mcp status` distinguishes three outcomes, because they need different fixes:

| `Key stored there:` | What it means | What to do |
| --- | --- | --- |
| `no` | The store answered, and holds no key | Run `lse-data-mcp login` |
| `unknown - there is no credential store to ask` | Nothing to read on this host | Set `LSE_API_KEY` |
| `unknown - this process cannot reach the credential store` | A key may be stored, but this process is not allowed to read it | Grant the process access, or set `LSE_API_KEY` |

The third case is what a sandboxed agent runner hits: the server runs in a restricted process,
macOS Keychain refuses it, and a key you stored earlier is genuinely there but unreadable. The
server reports this as unknown rather than as a missing key, so `login` is not suggested when
re-running it could not help. Grant the host process credential-store access, or pass the key
through `LSE_API_KEY` in the MCP client's environment configuration for that server.

`.env.example` is a reference only. The server deliberately does not load `.env` files: a `.env`
is plain text on disk, which is what the credential store exists to avoid.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LSE_API_KEY` | Only without a stored key | - | The user's own London Strategic Edge API key |
| `LSE_TIMEOUT_SECONDS` | No | `60` | Timeout for each upstream REST request; must be positive |
| `LSE_MAX_RESPONSE_BYTES` | No | `131072` | Serialized-JSON budget for one tool result; must be a positive whole number |

Run the installed server directly, after `lse-data-mcp login`:

```bash
lse-data-mcp
```

The equivalent module command is:

```bash
python -m lse_data_mcp
```

## MCP client configuration examples

Because the server resolves its own key, no client configuration below contains a secret. Point
the client at the virtual environment's console script, using an absolute path — the client will
not have your virtual environment on `PATH`.

**Claude Code** — `~/.claude.json`, or run
`claude mcp add lse-data -- /absolute/path/to/lse-data-mcp/.venv/bin/lse-data-mcp`:

```json
{
  "mcpServers": {
    "lse-data": {
      "command": "/absolute/path/to/lse-data-mcp/.venv/bin/lse-data-mcp"
    }
  }
}
```

**Claude Desktop** — `claude_desktop_config.json`, and **Cursor** — `~/.cursor/mcp.json` for all
projects or `.cursor/mcp.json` for one: same `mcpServers` object as above.

**Codex** — `~/.codex/config.toml`, which is TOML rather than JSON:

```toml
[mcp_servers.lse-data]
command = "/absolute/path/to/lse-data-mcp/.venv/bin/lse-data-mcp"
```

Restart the client after editing its configuration; MCP servers are spawned at client startup.

To run the package as a module instead of through the console script, use the virtual
environment's `python` with `args` of `["-m", "lse_data_mcp"]`.

Where a client offers its own secret management and you would rather use it, set `LSE_API_KEY`
through that mechanism; it takes precedence over the stored key. Prefer either of those over a
literal key in a configuration file.

## Errors and retries

The server converts upstream failures into concise tool errors:

- missing local configuration names both `lse-data-mcp login` and `LSE_API_KEY`, without printing
  any key value;
- HTTP 401 identifies an invalid or expired API key;
- subscription, access, and quota failures explain that the account cannot perform the request;
- HTTP 429 asks the client to wait before retrying;
- timeouts suggest retrying later or increasing `LSE_TIMEOUT_SECONDS`;
- network and upstream service failures are reported separately.

The server does not automatically retry rate-limited requests. This avoids adding more traffic
during an active limit and lets the MCP client decide when to retry.

## Known API, data, and subscription limitations

- A tool call returns one interactive page, with a hard maximum of 5,000 rows. This server does
  not expose bulk history/export jobs.
- A full 5,000-row page is far more JSON than an agent can usefully hold, so the server also caps
  a result at `LSE_MAX_RESPONSE_BYTES` and reports the cut through `truncated` and `note`. Raise
  the budget, or page with `start` and `end`, when a tool reports truncation.
- Available instruments, fields, history depth, entitlements, quotas, and rate limits are owned by
  London Strategic Edge and may change. Check the [official SDK documentation](https://github.com/londonstrategicedge/lse-data)
  and your account before relying on a dataset.
- The official SDK states that streaming and downloads share an allowance. Rate-limit or quota
  exhaustion can therefore be caused by activity outside this MCP process.
- The provider currently documents a free-plan allowance of 10 databank downloads per hour, with
  up to 1,000,000 rows per download. Those bulk downloads are separate from, and not exposed by,
  this server.
- The MCP surface is REST-only. Live WebSocket streaming and bulk downloads are out of scope.
  Of the SDK's REST endpoints, options (`options`, `option_candles`, `options_flow`), company
  financial statements, and the generic `economics` and `series` accessors are not yet exposed.
- `get_cot` reports a weekly survey, not a live position: the CFTC publishes on Friday for the
  preceding Tuesday, so the newest row lags the market by several days.
- `get_bond_yields` returns yields in percent, not prices. They move inversely to price, so a
  row's `high` is the day's highest yield and therefore its lowest price.
- A stock split rebases historical prices and share counts. Check `get_splits` before comparing
  any per-share figure across a window that contains one.
- Market data may be delayed, incomplete, corrected, or unavailable. It is not investment advice.

## Repository and data-safety policy

This repository must contain integration code and synthetic test data only. Do not commit:

- API keys, tokens, credentials, or populated `.env` files;
- downloaded proprietary datasets;
- real API responses containing restricted data;
- a public or hosted proxy that serves data using the maintainer's credentials.

Every user runs the adapter with their own key. Tests use recording fakes and synthetic rows; they
must never call the live API or consume an account allowance. Local MCP clients may retain tool
results in conversation history or logs, so users must configure those clients consistently with
the provider's data terms.

## Development checks

```bash
ruff format --check .
ruff check .
mypy src tests
pytest
```

GitHub Actions runs all four checks on Python 3.11, 3.12, and 3.13 for pushes and pull requests.

## Project structure

```text
src/lse_data_mcp/
├── __init__.py     # package metadata
├── __main__.py     # python -m entry point
├── cli.py          # command line: run the server, or manage the stored key
├── client.py       # lazy upstream SDK client
├── config.py       # key resolution and environment configuration
├── credentials.py  # operating-system credential store
├── server.py       # FastMCP server and tool registration
└── tools.py        # read-only market-data tools
```

## Data rights and unofficial-project disclaimer

The MIT license covers this integration code only. It does not grant rights to London Strategic
Edge data, APIs, SDKs, names, or trademarks. Review the provider's
[terms](https://londonstrategicedge.com/terms/) before using or retaining returned data; in
particular, do not redistribute or resell data unless the provider expressly permits it.

This is an independent community project. It is not affiliated with, endorsed by, sponsored by,
or maintained by London Strategic Edge.

## License

[MIT](LICENSE)
