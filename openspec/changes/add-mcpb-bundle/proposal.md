## Why

The README offers one-click install buttons for Cursor and VS Code, but not for Claude Desktop —
the most common host for an MCP server. Claude Desktop installs from a `.mcpb` release asset rather
than a deeplink, and this repository's GitHub releases carry no assets, so there is nothing to link
to. Users on Claude Desktop currently have to hand-edit `claude_desktop_config.json`.

This plan was approved on 2026-08-09 and partly delivered: the badges and the Cursor/VS Code buttons
shipped, the bundle did not. The remainder is carried here so it stops living in a dated file.

## What Changes

- Add an `mcpb/` directory that packs into a `.mcpb` bundle — a manifest plus a pinned dependency on
  the published PyPI release, carrying **no server source**.
- Extend `.github/workflows/release.yml` to build, validate, and attach the bundle to the GitHub
  release for the tag.
- Add a Claude Desktop install button to the README, **gated** on a release actually carrying the
  asset and on the open `uv` question below being settled.
- No change to `src/`, the tool surface, or the credential-resolution order. Not breaking.

## Capabilities

### New Capabilities

- `distribution/desktop-bundle`: what the Claude Desktop bundle must contain, how it obtains the
  user's API key, and the guarantee that it can never drift from a published release.

### Modified Capabilities

None. The bundle relies on the existing environment-variable-over-keyring precedence; it does not
change it.

## Impact

| Area | Effect |
|---|---|
| `mcpb/` | New directory, roughly 2 KB packed |
| `.github/workflows/release.yml` | New `bundle` job; asset attachment folded into the existing `github-release` job |
| Workflow permissions | `contents: write` — already introduced by the pending `github-release` job, so no new privilege |
| `README.md` | One button, added last |
| `src/`, `tests/`, `pyproject.toml` | Untouched |
| External | Pins `@anthropic-ai/mcpb`; adds Claude Desktop as a supported install path the project must keep working |

## Open question carried forward

MCPB documents its `uv` runtime as working "without user setup", but the reference example's
`mcp_config` uses `command: "uv"`, which implies `uv` on `PATH`. Whether Claude Desktop supplies its
own `uv` is unresolved from the documentation and decides whether the README button ships plain,
ships with a stated prerequisite, or is dropped in favour of a manual download. It is settled
empirically during implementation, not by further reading.
