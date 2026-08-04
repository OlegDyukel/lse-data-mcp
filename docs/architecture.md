# Architecture

## Scope

The project is a read-only MCP adapter over the official `lse-data` Python SDK. It does not implement a second market-data API and does not persist upstream responses.

## Request flow

```text
MCP client
    │ stdio
    ▼
FastMCP server
    │ validated tool arguments
    ▼
Tool function
    │ direct SDK call
    ▼
Official lse-data client
    │ HTTPS
    ▼
London Strategic Edge API
```

## Module responsibilities

- `cli.py` is the process entry point: it starts the server when given no subcommand, so an MCP
  client only ever needs the bare command, and otherwise manages the stored key.
- `credentials.py` reads and writes the key in the operating system's credential store, treating
  an unavailable store as "no key stored" so a headless host degrades to `LSE_API_KEY`.
- `server.py` owns MCP metadata, registration, and transport startup.
- `tools.py` maps stable MCP tool names to documented SDK methods, validates arguments before
  they cost an API call, and shapes every result into the `rows`/`row_count`/`truncated` envelope.
- `client.py` lazily creates the upstream client once per process.
- `config.py` resolves the API key — environment first, then credential store — and validates the
  remaining environment configuration.

## Design constraints

1. **Read-only by default.** The first release exposes retrieval operations only.
2. **No credential proxying.** Each server process uses the operator's own API key.
3. **No plain-text secrets on disk.** The adapter writes no key of its own; `login` delegates to
   the operating system's credential store, and `.env` files stay unread.
4. **No data persistence.** The adapter returns the SDK response without storing it.
5. **Thin translation.** Business logic remains upstream; this project performs validation, naming, and error translation.
6. **Stable agent surface.** MCP tool names should remain stable even when upstream implementation details change.
7. **Group only where nothing is lost.** A tool maps to one SDK method so that every declared argument is always meaningful. Discovery endpoints are the exception: they take almost no arguments, so `get_reference` groups them behind a `resource` enum. Where a grouped argument does not apply, the tool raises rather than ignoring it — an argument silently dropped is worse than a rejected call, because the caller still believes the filter was applied.
8. **Mocked tests.** Automated tests do not call the live API or consume user quotas.

## Future transport

The initial transport is `stdio`, which is appropriate for local agent clients. A remote Streamable HTTP deployment may be considered later, but only with explicit provider permission and a design where every user authenticates with their own credentials.
