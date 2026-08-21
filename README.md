<div align="center">
  <h1>lse-data-mcp</h1>
  <p>
    <b>An unofficial, read-only Model Context Protocol (MCP) server for the
    <a href="https://londonstrategicedge.com/">London Strategic Edge</a> market-data API.</b>
  </p>
  <div>15 tools</div>
</div>

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/lse-data-mcp?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/lse-data-mcp/) [![Python](https://img.shields.io/pypi/pyversions/lse-data-mcp?style=flat-square&logo=python&logoColor=white)](https://github.com/OlegDyukel/lse-data-mcp/blob/main/pyproject.toml) [![License](https://img.shields.io/pypi/l/lse-data-mcp?style=flat-square)](https://github.com/OlegDyukel/lse-data-mcp/blob/main/LICENSE) [![CI](https://img.shields.io/github/actions/workflow/status/OlegDyukel/lse-data-mcp/ci.yml?branch=main&style=flat-square&logo=githubactions&logoColor=white&label=CI)](https://github.com/OlegDyukel/lse-data-mcp/actions/workflows/ci.yml) [![MCP](https://img.shields.io/badge/MCP-server-6E56CF?style=flat-square)](https://modelcontextprotocol.io/)

[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=lse-data&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJsc2UtZGF0YS1tY3AiXX0=) [![Install in VS Code](https://img.shields.io/badge/Install_in_VS_Code-0098FF?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=lse-data&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22lse-data-mcp%22%5D%7D) [![Install in Claude Desktop](https://img.shields.io/badge/Install_in_Claude_Desktop-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://github.com/OlegDyukel/lse-data-mcp/releases/latest/download/lse-data-mcp.mcpb)

</div>

> **Versioning:** While the version is 0.x, tool names and arguments may still change between
> releases. Pin one — `uvx lse-data-mcp==0.1.5` — if you need the surface to stay put.

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
| `get_financial_reports` | Income, balance sheet and cash flow statements | `symbol`, `report_type`, `period`, `start`, `end`, `limit`, `order` |
| `get_options` | Current option chain for an underlying | `underlying`, `option_type`, `expiry`, `strike`, `strike_min`, `strike_max`, `min_dte`, `max_dte`, `limit` |
| `get_option_candles` | One-minute premium OHLC for one contract | `contract`, `strike`, `expiry`, `option_type`, `start`, `end`, `limit`, `order` |
| `get_options_flow` | Option prints (time and sales), trailing week | `underlying`, `option_type`, `min_premium`, `expiry`, `max_dte`, `start`, `end`, `limit`, `order` |
| `get_series` | One `(date, value)` series: economics, bond tenors | `symbol`, `dataset`, `start`, `end`, `limit`, `order` |
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

`get_financial_reports` defaults to 20 instead, because each row carries a whole statement in its
`data` field and is far larger than a candle or a dividend. Twenty rows is five years of quarterly
reports, or twenty years of annual ones.

`start` and `end` accept an ISO 8601 date or timestamp (`2026-01-01`, `2026-01-01T14:30:00Z`).
Anything else is rejected locally, so a malformed date costs no API call and no quota. On
`get_candles` the upstream API accepts the date part only; an intraday `start` or `end` is
rejected there, so narrow a `1s` or `1m` window by filtering the rows that come back.

## Data caveats

Some upstream conventions are worth knowing before you quote a number. The first two were
measured by comparing this API against other market-data sources, and both are open questions
with the provider. Every caveat below is also carried in the relevant tool's description, so the
model reads it on each call rather than only here.

- **Daily candles cover the extended session**, 08:00–23:00 UTC (04:00–19:00 ET), not the regular
  session. A daily `close` is the last post-market print rather than the 16:00 ET closing auction,
  so it differs from the close quoted by most retail sources — usually by a few cents, in either
  direction depending on post-market drift. Intraday highs and lows matched Financial Modeling
  Prep's over the same sessions (measured Aug 2026). The prices are not wrong; the session
  boundary is different.
- **Volume is indicative only.** Measured Aug 2026: across fifteen sessions of IBM, daily volume
  ranged from 45% to 106% of what Financial Modeling Prep reported for the same sessions, with no
  stable relationship to date, volume level, or bar age. The closing auction appears in some
  sessions and not others. That is two vendors disagreeing rather than proof either is wrong — but
  it is reason enough not to use this field for liquidity, participation, or turnover conclusions.
- **Fundamentals are a dated snapshot, not a live quote.** `get_fundamentals` returns one row per
  symbol, stamped `updated_at`. Its `current_price` is that snapshot's price, and `market_cap`,
  `pe_ratio` and `dividend_yield` derive from it, so all four age together and can disagree with
  the latest close. Take a current price from `get_candles`.
- **Dividend rows carry four different dates.** `start` and `end` filter `effective_date`, the
  ex-date, while `declaration_date`, `record_date` and `payment_date` sit in the row and fall in
  other months. `dividend_type` and `frequency` are not a controlled vocabulary — the same
  quarterly dividend appears as both `CD` and `Regular`, and its frequency as both `4` and
  `Quarterly` — so neither is safe to filter or group on.
- **Insider rows are filing legs, not trades.** `transaction_type` takes SEC codes
  (`P-Purchase`, `S-Sale`, `M-Exempt`, `F-InKind`); an unrecognised value returns zero rows rather
  than an error, so a wrong code looks like a quiet period. Direction is
  `acquisition_or_disposition`, not `transaction_type`. `price` is 0 on exercises and grants, and
  a single vest expands into several rows, so both value and count are easy to misread.

## Obtain an API key

1. Visit the official [London Strategic Edge data page](https://londonstrategicedge.com/data/).
2. Follow the site's prompts to obtain your own API key.
3. Store it with `uvx lse-data-mcp login`, which prompts without echoing and saves the key to
   the operating system's own credential store.

Never commit the key to this repository or put a real key in an issue, test, example, or log.

## Requirements

- A London Strategic Edge API key
- Either [`uv`](https://docs.astral.sh/uv/), or Python 3.11 or newer

## Installation

The buttons above configure Cursor and VS Code in one click; both still need a stored API key,
below. The third installs a bundle into Claude Desktop, which collects the key itself — see
[Claude Desktop](#claude-desktop). For any other client, or to run the server by hand, install it
yourself.

With [`uv`](https://docs.astral.sh/uv/getting-started/installation/) there is nothing to install:
`uvx` fetches the published package, runs it in a cached environment of its own, and brings its
own Python. Store your key, then check it:

```bash
uvx lse-data-mcp login
uvx lse-data-mcp status
```

Whichever command you use here, use the same one in your MCP client below. Mixing `uvx` with a
virtual environment means two different interpreters touch the credential store, which on macOS
raises an extra Keychain prompt — see [When the server cannot find your
key](#when-the-server-cannot-find-your-key).

Without `uv`, install the same release from PyPI with pip. Check your interpreter first: macOS
ships an older `python3` than this project supports, so that command often reports 3.9. Install a
supported one with `brew install python@3.13` and use it by name; on Windows, use `py -3.13`.

```bash
python3 --version               # must be 3.11 or newer
python3 -m venv .venv           # or python3.13 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install lse-data-mcp
```

Activating that environment is what puts `lse-data-mcp` on your `PATH`, and a client will need
its absolute path rather than the bare `uvx` command.

### Claude Desktop

The **Install in Claude Desktop** button above downloads a bundle that installs in one step, with
no configuration file to edit. Two things it will not do for you:

- **Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first.** Claude Desktop
  runs the bundle through `uv` and resolves it from your `PATH` rather than shipping its own copy.
  If the extension fails to start, this is the first thing to check.
- **Switch it on — and check it again after saving the key.** The extension arrives disabled, and
  saving the API key can switch it off a second time. While it is off, Claude reports that no such
  connector is installed, or that it has disconnected; both look like a broken install and neither
  is. The toggle is under Settings → Extensions.

Claude Desktop prompts for your API key during installation and stores it itself, encrypted. A
bundle install therefore never touches the operating system credential store and needs no `login`
command.

The bundle is deliberately small — a manifest, a dependency pin, and a launcher that does nothing
but call the installed package, around 2 KB packed. It contains no server code of its own: it pins
one exact published version and installs that from PyPI, so a bundle runs the same code as
`uvx lse-data-mcp`, and you can unzip it and read the whole thing in a minute. Claude Desktop warns
that a file-installed extension is unverified by Anthropic and runs with your user privileges. That
is true, and it is true of every local MCP server — read-only here describes the upstream API, which
has no write endpoints, not a sandbox around the process.

To work on the project rather than use it, see
[CONTRIBUTING.md](https://github.com/OlegDyukel/lse-data-mcp/blob/main/CONTRIBUTING.md).

## Supplying the API key

Store the key once, in the credential store your operating system already provides:

```bash
uvx lse-data-mcp login     # prompts without echoing; nothing is written to a file
uvx lse-data-mcp status    # reports where the key resolves from, without printing it
uvx lse-data-mcp logout    # removes the stored key
```

Drop the `uvx` prefix if you installed from source into a virtual environment.

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

### The macOS Keychain prompt

On macOS you may see a dialog like this the first time a given command reads your stored key:

> **python3.11 wants to use your confidential information stored in "lse-data-mcp" in your
> keychain.** The authenticity of "python3.11" cannot be verified. To allow this, enter the
> "login" keychain password.

This is expected, and it is macOS asking rather than this server. Keychain records which binary
created an entry and asks before letting a different one read it. The dialog names a bare
`python3.11` because that is the interpreter running the tool — under `uvx`, a Python that `uv`
manages and that macOS has no signature for.

- **Password**: your macOS login password, the one you use to unlock the Mac. Not your API key.
- **Button**: *Always Allow* records this interpreter against the entry so it stops asking.

The prompt appears at all because the command that stored the key and the command reading it are
different programs. Use one or the other consistently and it will not recur:

```bash
uvx lse-data-mcp login     # if your MCP client runs `uvx lse-data-mcp`
lse-data-mcp login         # if your client runs a virtual environment's script
```

It can return after `uv` upgrades its managed Python, since that is a new binary. If you would
rather never see it — on a shared machine, or in an automated environment — set `LSE_API_KEY` in
the MCP client's environment for this server instead, which bypasses the credential store.

`.env.example` is a reference only. The server deliberately does not load `.env` files: a `.env`
is plain text on disk, which is what the credential store exists to avoid.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LSE_API_KEY` | Only without a stored key | - | The user's own London Strategic Edge API key |
| `LSE_TIMEOUT_SECONDS` | No | `60` | Timeout for each upstream REST request; must be positive |
| `LSE_MAX_RESPONSE_BYTES` | No | `131072` | Serialized-JSON budget for one tool result; must be a positive whole number |

An MCP client starts the server for you. To run it by hand — to see a startup error directly,
say — use the same command your client does, after storing a key:

```bash
uvx lse-data-mcp
```

From a source checkout, that is `lse-data-mcp`, or `python -m lse_data_mcp` to run the package as
a module. Nothing is printed on success: the server is waiting to speak JSON-RPC over standard
input, so an empty, hanging terminal means it started correctly. Press Ctrl-C to stop it.

## MCP client configuration examples

Because the server resolves its own key, no client configuration below contains a secret, and
because `uvx` resolves the package, none of them needs a path.

**Claude Code** — `~/.claude.json`, or run `claude mcp add -s user lse-data -- uvx lse-data-mcp`,
where `-s user` registers the server for every project rather than only the current one:

```json
{
  "mcpServers": {
    "lse-data": {
      "command": "uvx",
      "args": ["lse-data-mcp"]
    }
  }
}
```

**Claude Desktop** — `claude_desktop_config.json`, and **Cursor** — `~/.cursor/mcp.json` for all
projects or `.cursor/mcp.json` for one: same `mcpServers` object as above. On Claude Desktop the
[bundle](#claude-desktop) is the easier route and edits no file; this is the manual alternative.

**Antigravity** — `~/.gemini/config/mcp_config.json`, or the same file through **… > MCP Store >
Manage MCP Servers > View raw config** in the agent panel: same `mcpServers` object as above. The
install buttons cannot help here, because a browser can only hand a link to the editor that claims
the URL scheme it names, and each VS Code fork registers its own.

**Codex** — `~/.codex/config.toml`, which is TOML rather than JSON, or run
`codex mcp add lse-data -- uvx lse-data-mcp`. That file is user-global, so there is no scope to
choose:

```toml
[mcp_servers.lse-data]
command = "uvx"
args = ["lse-data-mcp"]
```

Restart the client after editing its configuration; MCP servers are spawned at client startup.

Two things to know about `command: "uvx"`. A client launched from the desktop rather than a
terminal may not have `uvx` on its `PATH`; give the absolute path from `which uvx` if the server
fails to start. And `uvx` fetches the latest release each time its cache expires, so the server
updates itself — pin with `["lse-data-mcp==0.1.5"]` if you would rather it did not.

<details>
<summary>Pointing at a virtual environment instead</summary>

For a pip install or a source checkout, name the environment's console script directly:

```json
{
  "mcpServers": {
    "lse-data": {
      "command": "/absolute/path/to/.venv/bin/lse-data-mcp"
    }
  }
}
```

The path must be absolute: the client will not have your virtual environment on `PATH`. To run
the package as a module rather than through the console script, use that environment's `python`
with `args` of `["-m", "lse_data_mcp"]`.

</details>

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
  Every other SDK REST endpoint has a tool, with one deliberate exception. The SDK's `economics`
  is a wrapper with no endpoint of its own: without a symbol it returns `datasets("economics")`,
  and with one it calls `series(symbol, dataset="economics")`. Both are already reachable, as
  `get_reference('datasets', dataset='economics')` and `get_series(symbol, dataset='economics')`,
  so a separate tool would only give an agent two names for one operation.
- `get_options` returns a live snapshot that refreshes while the market is open, not history, and
  carries no timestamp of its own. A whole chain on a liquid name runs to thousands of contracts,
  so filter by expiry, strike or days-to-expiry rather than raising `limit`.
- `get_options_flow` covers the trailing week only. Older prints are served as one-minute bars by
  `get_option_candles`, whose bars are option premium, not the underlying's price.
- The provider does not document which date field `get_financial_reports` filters on with `start`
  and `end` — the period end, the fiscal period, or the filing date. Until that is confirmed,
  prefer `period` for selecting a fiscal period and treat a date window as approximate.
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

[MIT](https://github.com/OlegDyukel/lse-data-mcp/blob/main/LICENSE)
