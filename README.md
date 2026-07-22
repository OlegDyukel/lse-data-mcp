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

| Tool | What it returns | Main filters |
| --- | --- | --- |
| `get_candles` | OHLCV candles for an instrument | `symbol`, `timeframe`, `start`, `end`, `limit`, `order` |
| `get_company_profile` | Company reference and listing information | `symbol`, `limit` |
| `get_fundamentals` | Snapshot company fundamentals | `symbol`, `limit` |
| `get_insider_transactions` | Reported insider transactions | `symbol`, `transaction_type`, `start`, `end`, `limit`, `order` |
| `get_dividends` | Dividend events | `symbol`, `start`, `end`, `limit`, `order` |
| `get_economic_calendar` | Scheduled or released economic events | `region`, `event`, `start`, `end`, `released_only`, `limit`, `order` |

Each call defaults to at most 200 rows. The upstream API caps a single interactive call at 5,000
rows; use `start` and `end` to request narrower windows.

## Obtain an API key

1. Visit the official [London Strategic Edge data page](https://londonstrategicedge.com/data/).
2. Follow the site's prompts to obtain your own API key.
3. Expose it to the MCP server as `LSE_API_KEY` through your MCP client's environment or secret
   configuration.

Never commit the key to this repository or put a real key in an issue, test, example, or log.

## Requirements

- Python 3.11 or newer
- A London Strategic Edge API key

## Installation

Clone and install the server in a virtual environment:

```bash
git clone https://github.com/OlegDyukel/lse-data-mcp.git
cd lse-data-mcp
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

For development, install the test and quality tools too:

```bash
python -m pip install -e ".[dev]"
```

## Configuration

The server reads configuration from its process environment:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `LSE_API_KEY` | Yes | - | The user's own London Strategic Edge API key |
| `LSE_TIMEOUT_SECONDS` | No | `60` | Timeout for each upstream REST request; must be positive |

`.env.example` is a reference only. The server deliberately does not load `.env` files; the MCP
host remains responsible for secret loading.

Run the installed server directly:

```bash
LSE_API_KEY="your_own_key" lse-data-mcp
```

The equivalent module command is:

```bash
LSE_API_KEY="your_own_key" python -m lse_data_mcp
```

## MCP client configuration examples

Most desktop MCP clients accept an `mcpServers` JSON object. After installing the project, point
the client at the virtual environment's console script:

```json
{
  "mcpServers": {
    "lse-data": {
      "command": "/absolute/path/to/lse-data-mcp/.venv/bin/lse-data-mcp",
      "env": {
        "LSE_API_KEY": "your_own_key",
        "LSE_TIMEOUT_SECONDS": "60"
      }
    }
  }
}
```

Alternatively, run the package as a module from the repository:

```json
{
  "mcpServers": {
    "lse-data": {
      "command": "/absolute/path/to/lse-data-mcp/.venv/bin/python",
      "args": ["-m", "lse_data_mcp"],
      "cwd": "/absolute/path/to/lse-data-mcp",
      "env": {
        "LSE_API_KEY": "your_own_key"
      }
    }
  }
}
```

Client schemas and secret stores differ. Prefer the client's secret-management mechanism over a
literal key in a configuration file.

## Errors and retries

The server converts upstream failures into concise tool errors:

- missing local configuration identifies `LSE_API_KEY` without printing its value;
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
- Available instruments, fields, history depth, entitlements, quotas, and rate limits are owned by
  London Strategic Edge and may change. Check the [official SDK documentation](https://github.com/londonstrategicedge/lse-data)
  and your account before relying on a dataset.
- The official SDK states that streaming and downloads share an allowance. Rate-limit or quota
  exhaustion can therefore be caused by activity outside this MCP process.
- The provider currently documents a free-plan allowance of 10 databank downloads per hour, with
  up to 1,000,000 rows per download. Those bulk downloads are separate from, and not exposed by,
  this server.
- The initial MCP surface is REST-only. Live WebSocket streaming, bulk downloads, stock splits,
  options, and other SDK datasets are out of scope.
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
├── __init__.py    # package metadata
├── __main__.py    # python -m entry point
├── client.py      # lazy upstream SDK client
├── config.py      # environment configuration
├── server.py      # FastMCP server and tool registration
└── tools.py       # read-only market-data tools
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
