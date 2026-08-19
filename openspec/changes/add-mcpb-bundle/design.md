## Context

See `proposal.md` — Why. Constraints discovered while this was first designed, all still current:

| Fact | Consequence |
|---|---|
| Claude Desktop installs from a `.mcpb` release asset, not a deeplink | A build pipeline is required; there is no URL-only shortcut |
| MCPB's traditional Python bundling "cannot portably bundle compiled dependencies" | `keyring` rules that mode out; the `uv` server type is the only viable one |
| Env var takes precedence over the credential store in the existing resolution order | The bundle needs no change to `src/` to bypass the Keychain |
| Claude Desktop is a sandboxed host | The OS credential store may refuse it outright |

Changed since the original plan: `release.yml` now grows a `github-release` job (currently staged,
uncommitted) that creates the release and already holds `contents: write`. The original design
called for a separate `attach` job; that is now redundant.

## Goals / Non-Goals

**Goals:**

- One write-privileged job in the release workflow, not two.
- A release is never visible without its bundle attached.
- Bundle version and dependency pin generated from one source, never hand-synced.

**Non-Goals:**

- No Docker image, HTTP transport, or MCP registry submission.
- No change to `src/`, the tool surface, or credential resolution.
- No redesign of the README beyond one button.

## Decisions

### Bundle ships a pointer, not the server

`mcpb/` contains a manifest, a dependency declaration pinning `lse-data-mcp==X.Y.Z`, an
`.mcpbignore`, and a launcher that imports the installed package. Roughly 2 KB packed.

*Why not vendor the source?* A bundle carrying its own copy can diverge from what PyPI serves under
the same version number, which is exactly the drift the spec forbids. A pointer cannot.

### `mcpb/pyproject.toml` declares `[project]` with no `[build-system]`

This is what makes `uv` treat the directory as a *virtual project* — an environment to resolve
rather than a package to build. It matches the official `hello-world-uv` example. Adding a
`[build-system]` table would make `uv` attempt to build the bundle directory and fail.

### Version and pin are generated at build time from the root `pyproject.toml`

One source of truth. A release cannot ship a manifest whose version disagrees with the package.

*Alternative rejected:* hand-editing `mcpb/manifest.json` per release — the same class of omission
that left v0.1.2 and v0.1.3 without GitHub releases at all.

### The key is `required: true`, with no credential-store fallback

```json
"user_config": {
  "api_key": { "type": "string", "title": "London Strategic Edge API key",
               "sensitive": true, "required": true }
},
"mcp_config": { "env": { "LSE_API_KEY": "${user_config.api_key}" } }
```

*Why not fall back to the credential store?* On a sandboxed host a blank field produces a confusing
"cannot reach credential store" error at the first tool call. Blocking install until a key is
entered leaves exactly one documented path, and bundle users never touch `lse-data-mcp login`.

### Attachment folds into `github-release` rather than a separate job

New `bundle` job — pins `@anthropic-ai/mcpb`, generates the manifest version and pin, runs
`mcpb validate` then `mcpb pack`, uploads the `.mcpb` as a workflow artifact. No write permissions,
consistent with the workflow's least-privilege pattern (the `build` job deliberately holds no
`id-token` because packaging executes project code).

`github-release` then takes `needs: [publish-pypi, bundle]`, downloads the artifact, and passes the
file to `gh release create` so the release is *born* with its asset.

```
build ──┬──▶ publish-pypi ──┐
        │                   ├──▶ github-release  (contents: write)
        └──▶ bundle ────────┘
```

*Why gate on `publish-pypi`?* The bundle pins a version that `uv` resolves on the user's machine at
install time. Attaching it before PyPI has the package would ship a bundle pinning something that
does not exist yet.

*Alternative rejected:* a separate `attach` job running after `github-release`. It adds a second
write-privileged job and opens a window where the release exists without its asset.

### `contents: write` introduces no new privilege

It arrives with the pending `github-release` job regardless of this change. Worth stating plainly:
it remains the only write privilege in the repository, held by one job that performs no checkout.

## Risks / Trade-offs

**Claude Desktop may not supply its own `uv`** → Settled by verification, not by reading. Install
the packed bundle on a machine with no `uv` on `PATH`. Both outcomes are already specified
(`desktop-bundle` — "The documented install path states its prerequisites"), so this changes which
branch ships, not the design. The button is the last task and is gated on the answer.

**A new external dependency on `@anthropic-ai/mcpb`** → Pinned to an exact version, same as every
other action in the workflow. It runs in the no-write `bundle` job.

**A bundle user is pinned to the release they downloaded** → Intentional; it is the drift guarantee.
They upgrade by downloading the next bundle, exactly as with any other desktop application.

**The bundle becomes a supported install path** → Claude Desktop's manifest schema can change under
us. Mitigated by `mcpb validate` running in CI on every release, so a schema break fails the
release rather than shipping a broken asset.

## Migration Plan

Additive; nothing to migrate. Rollback is deleting the release asset and reverting the README
button — the PyPI path is untouched and remains the primary install route.

## Open Questions

None that block implementation. The `uv` question above is a verification step, not a design gap.
