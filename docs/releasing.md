# Releasing

`release.yml` does the mechanical half on a `v*` tag push: it re-runs the four
checks against the tagged commit, refuses to publish when the tag and
`pyproject.toml` disagree, uploads to PyPI through Trusted Publishing, and packs
the Claude Desktop bundle. This file is the half the workflow cannot do — the
judgement calls and the one step it deliberately leaves manual.

Work top to bottom. Every step here exists because skipping it cost something.

## Before tagging

- [ ] **Confirm the payload is actually on `main`.** Do not trust that a PR was
      merged — check for the change itself, e.g.
      `grep -c "Measured Aug 2026" src/lse_data_mcp/tools.py` (nonzero). 0.1.5 was
      first prepared on a stale `main` while the PR carrying its whole point was
      still open; tagging there would have shipped the release without the
      feature it was named for. It surfaced only because the test count dropped.
- [ ] **Re-check the empirical caveats, or re-date them.** Any caveat in a tool
      description that came from measurement rather than from the upstream
      contract carries its measurement date (see the convention below). Re-run the
      comparison, then either confirm the range still holds or update both the
      number and the date. A caveat is asserted by the model on every call, so a
      stale one is repeated with confidence rather than sitting unread.
- [ ] **Bump `version` in `pyproject.toml`**, then
      `python scripts/sync_bundle_version.py` so the bundle's manifest and pin
      and the README's two `lse-data-mcp==` pin examples all follow. That one
      file is the only place the number is written by hand. `--check` verifies
      without writing; CI runs it on every push.
- [ ] **Run the four checks locally**: `ruff format --check .`, `ruff check .`,
      `mypy src tests`, `pytest`.
- [ ] **Update `README.md`** if the tool surface moved. Tool names and arguments
      are semi-stable on 0.x — a change to either needs a note under the
      versioning callout.

## Tagging

- [ ] Rehearse on TestPyPI first if the packaging changed: run the workflow
      manually (`workflow_dispatch`), which only ever targets TestPyPI.
- [ ] Push the tag: `git tag vX.Y.Z && git push origin vX.Y.Z`. Publishing is
      irreversible — a version can be yanked but never reused.

## After the workflow is green

- [ ] **Create the GitHub Release by hand**:
      `gh release create vX.Y.Z --generate-notes`. The workflow never does this,
      and it has been forgotten before — v0.1.2 and v0.1.3 have tags and no
      Release entry.
- [ ] **Verify the published artifact**, not the working tree: install the real
      version in a clean venv and read back whatever the release was for, e.g.
      the length of the docstrings that changed.

## The dated-caveat convention

Caveats that state how the upstream feed is defined are undated — the
08:00–23:00 UTC session boundary is their definition, not our observation.
Caveats that came from measurement carry the date in the string itself
("Measured Aug 2026 against a consolidated-tape source over fifteen sessions"),
in both the docstring and `README.md`. Dating turns a claim about the feed, which
goes false the day the provider changes anything, into a claim about a
measurement, which can only age.
