## 1. Bundle directory

- [x] 1.1 Create `mcpb/manifest.json` with `server.type: "uv"`, the `user_config.api_key` block
      (`sensitive: true`, `required: true`), and `mcp_config.env.LSE_API_KEY` bound to it
- [x] 1.2 Create `mcpb/pyproject.toml` declaring `[project]` with `dependencies = ["lse-data-mcp==X.Y.Z"]`
      and **no** `[build-system]` table, so `uv` treats it as a virtual project
- [x] 1.3 Create `mcpb/src/server.py` — a launcher that imports and calls `lse_data_mcp.cli.main`,
      carrying no server logic of its own
- [x] 1.4 Create `mcpb/.mcpbignore` so the packed bundle stays around 2 KB
- [x] 1.5 Confirm the packed bundle contains no module from `src/lse_data_mcp/`
      (`desktop-bundle` — "The bundle cannot drift from a published release")
      — packed 2.1 kB / 3 files: `manifest.json`, `pyproject.toml`, `src/server.py`. Nothing else.

## 2. Version generation

- [x] 2.1 Write the step that reads `version` from the root `pyproject.toml` and writes it into
      `mcpb/manifest.json` and the `==` pin in `mcpb/pyproject.toml`
      — `scripts/sync_bundle_version.py`, a script rather than inline workflow YAML so that
      task 4.2's local pack generates the same way the release does
- [x] 2.2 Verify the generated manifest version equals the root `pyproject.toml` version, and that
      neither file needs hand-editing at release time
      — `--check` exits 1 on a stale pin, the write path repairs it, and re-running is a no-op
- [x] 2.3 Wire `python scripts/sync_bundle_version.py --check` into `.github/workflows/ci.yml`, so a
      version bump that forgets the bundle fails on the pull request rather than at release time
      (added during implementation; not in the original plan)

## 3. Release pipeline

      — added as a step in the `quality` job, so it runs on all three Python versions
- [x] 3.1 Commit the pending `github-release` job in `.github/workflows/release.yml` first — this
      change builds on it and it is currently only staged
      — landed as its own commit, 9c9a460, ahead of the bundle work
- [x] 3.2 Add a `bundle` job: pin `@anthropic-ai/mcpb` to an exact version, run the generation step
      from 2.1, then `mcpb validate` and `mcpb pack`; upload the `.mcpb` as a workflow artifact.
      No `permissions:` block — it must stay read-only
      — **pass an explicit output path**: `mcpb pack mcpb/ dist/lse-data-mcp.mcpb`. With no second
      argument the CLI names the archive after the *directory* (`mcpb.mcpb`), which would not match
      the `releases/latest/download/lse-data-mcp.mcpb` URL task 5.1 links to. Found 2026-08-19.
      Note `mcpb validate` takes the manifest path (`mcpb/manifest.json`), not the directory.
      — uses the runner's preinstalled Node via `npx`, adding no new pinned action
- [x] 3.3 Change `github-release` to `needs: [publish-pypi, bundle]`, download the artifact, and pass
      the file to `gh release create` so the release is created with its asset already attached
      — the asset is passed to `gh release create` itself, so the release is never briefly
      visible without it
- [x] 3.4 Run `actionlint .github/workflows/release.yml`
      — actionlint 1.7.12, clean on both `release.yml` and `ci.yml`
- [x] 3.5 Confirm `bundle` holds no write permission and that `github-release` remains the only job
      with `contents: write`

## 4. Verification on a real host

      — `bundle` carries no `permissions:` block, so it inherits the workflow default
      `contents: read`; `github-release` remains the only job with `contents: write`
- [x] 4.1 Run `mcpb validate mcpb/` locally and confirm it passes
      — "Manifest schema validation passes!" under `@anthropic-ai/mcpb@2.1.2`
- [x] 4.2 Run `mcpb pack` locally and inspect the artifact against tasks 1.5 and 2.2
      — 2.1 kB packed, 3 files, declared version 0.1.3 matching the root `pyproject.toml`
- [ ] 4.3 **Settle the open `uv` question**: install the packed bundle in Claude Desktop on a machine
      with no `uv` on `PATH`. Record the outcome in this change before proceeding
      — *documentary evidence only, still to be confirmed empirically:* MCPB's own
      `hello-world-uv` README states the uv runtime "downloads the correct Python version for the
      user's platform" and "works cross-platform without user setup", and MANIFEST.md notes
      `mcp_config` is optional for `type: "uv"` because the host manages execution. That points to
      the host supplying `uv`, which is the branch where §5.1 ships a plain button — but the design
      says settle this on a real host, so it stays open
      — **EVIDENCE 2026-08-19, and it contradicts the documentation.** Installed on macOS with
      Claude Desktop: the extension resolved and built a venv, but `main.log` shows the spawned
      binary was `/Users/olegdiukel/.local/bin/uv` — the *user's* uv. `.venv/pyvenv.cfg` records
      `uv = 0.12.0`, matching the user's `uv --version` exactly, and no uv binary ships inside
      `Claude.app`. Claude Desktop imports the login-shell PATH rather than running with a bare
      GUI environment, so "works without user setup" holds only where uv is already installed.
      Still unproven: whether it falls back to downloading uv when none is found. That needs the
      binary temporarily renamed and the app restarted — until then, assume the prerequisite is
      real and ship §5.1 on the second branch (stated prerequisite, or no button).
- [ ] 4.4 Confirm Claude Desktop prompts for the API key at install, and that leaving it blank blocks
      installation rather than deferring the error to the first tool call
      — partial 2026-08-19: the key is collected and stored by the host as
      `__encrypted__:...` in `Claude Extensions Settings/<id>.json`, so the project persists nothing.
      The blank-field behaviour was not exercised and remains untested.
- [x] 4.5 Confirm a tool call returns rows on that host, with the OS credential store never consulted
      (`desktop-bundle` — "A bundle install does not depend on the OS credential store")
      — 2026-08-19: five IBM daily candles returned in Claude Desktop, and Claude surfaced the
      extended-session and volume caveats unprompted from the `get_candles` docstring. The
      credential-store half is NOT isolated: this machine's keyring holds a key, so the env var
      merely took precedence as designed. Proving independence needs a host without one.
- [x] 4.6 Tag a release and confirm `releases/latest/download/lse-data-mcp.mcpb` resolves and that its
      declared version matches the tag
      — v0.1.4, 2026-08-19: the URL returns 200, the asset is `lse-data-mcp.mcpb` (2133 bytes), the
      manifest inside declares 0.1.4 matching the tag, its pin is `lse-data-mcp==0.1.4`, and PyPI
      serves 0.1.4. The `github-release` download-and-attach path ran for the first time here and
      worked. Gate 5.2 is therefore satisfied.

## 5. README

- [x] 5.1 **Gated on 4.3.** If Claude Desktop supplies its own `uv`, add the install button pointing at
      `releases/latest/download/lse-data-mcp.mcpb`. If it does not, either state the prerequisite
      beside the button or omit the button and document the manual download instead
      (`desktop-bundle` — "The documented install path states its prerequisites")
      — shipped 2026-08-19 on the **second** branch: the button carries a stated `uv` prerequisite.
      **This is provisional.** Evidence shows Claude Desktop resolved the user's own uv; it was
      never tested on a machine lacking one, so whether it falls back to fetching its own is still
      unknown. Over-stating the prerequisite is the safe error — it costs a line, where understating
      it strands users on a failed install. Drop the bullet if the no-uv test later comes back clean.
      The section also documents the disabled-on-install behaviour and the unverified-extension
      warning, neither of which was in the original plan and both of which a button user will meet.
- [x] 5.2 Do not add the button before 4.6 passes — no visitor should ever meet a broken link
- [x] 5.3 Add the bundle to the install-options section of the README alongside the existing
      `uvx` and editor-button paths
- [x] 5.4 Re-check the Cursor and VS Code buttons still resolve from the rendered README
      — badge images all return 200 (cursor.com deeplink SVG, both shields.io badges). The deeplink
      *targets* are app handlers, not HTTP, so those still need a human click to confirm.

## 6. Close out

- [x] 6.1 `ruff format . && ruff check . && mypy src tests && pytest` — no `src/` change is expected,
      so this is a regression check that the repository is still clean
      — 2026-08-19: ruff format (17 files), ruff check, mypy (15 files), pytest 159 passed, 99%
- [ ] 6.2 Delete `docs/superpowers/specs/2026-08-09-readme-header-and-mcpb-bundle-design.md`; this
      change supersedes it
- [ ] 6.3 Run `/openspec-archive-change add-mcpb-bundle` to fold the delta into
      `openspec/specs/distribution/desktop-bundle/spec.md`

## Findings during implementation

**An installed bundle arrives disabled.** After a successful install the host wrote
`"isEnabled": false` into `Claude Extensions Settings/<id>.json`, so no server process started,
`mcp.log` stayed 0 bytes, and Claude answered the first tool question by searching the *remote*
connector directory — which reads to a user as "the extension does not work". Observed once, not
yet confirmed as the default for every install, but if it is, the README must tell button users to
enable the extension after installing or they will hit this exact dead end.



**Signing is not a route to a quieter install screen (tested 2026-08-19).** Claude Desktop warns on
any file-installed extension: "Installing will grant this extension access to everything on your
computer. Any developer information shown has not been verified by Anthropic." Neither half is
fixable by packaging — the capability statement is accurate for any local MCP server, and
verification comes only from Anthropic's reviewed directory. `mcpb sign --self-signed` was tried
under 2.1.2: it reports success and grows the file from 2.1 kB to 4.29 kB, but the same CLI's
`verify` and `info` both then report the bundle as unsigned, and no cert/key is persisted. Do not
add a signing step to CI — it would cost a key secret for no demonstrated benefit.

**Mitigation is auditability, not reassurance.** The bundle's own design is the answer: 3 files,
no server source, one exact PyPI pin, readable end to end in a minute. Say that next to the button.

**"All requirements met"** was shown on the pre-install screen with the runtime unset, the first
positive evidence for the task 4.3 `uv` question.

## Notes

No unit tests accompany this change: it adds no code to `src/`, and the bundle's behaviour is only
observable on a real Claude Desktop host. Section 4 is the test plan, and it is manual by nature —
task 4.3 in particular cannot be automated in CI, since it requires a machine deliberately lacking
`uv`.
