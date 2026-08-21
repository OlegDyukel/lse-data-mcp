#!/usr/bin/env python3
"""Generate the bundle's version and the README's pin examples from the root pyproject.toml.

The Claude Desktop bundle declares its own version and pins the package it
installs. Both must equal the version being released, and neither is worth
trusting a human to remember: v0.1.2 and v0.1.3 shipped with no GitHub release
at all because one manual release step was forgotten twice.

The README's two `lse-data-mcp==` pin examples are generated for the same
reason. Nothing breaks when they go stale, which is exactly the problem: a
reader copies the example and pins an old release without noticing.

So there is one source of truth — `version` in the root `pyproject.toml` — and
the release workflow runs this before packing.

    python scripts/sync_bundle_version.py            # write
    python scripts/sync_bundle_version.py --check    # verify, write nothing

`--check` exits non-zero when a file disagrees, which is what makes the
committed bundle files safe to read: they are either in step with the root
version or CI says so.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "mcpb"

# Each rule carries the number of matches it expects, so a file that gains or
# loses one fails the release instead of being half-rewritten.
#
# The bundle rules anchor to the start of the line, which is what keeps
# `"version"` in manifest.json from also matching `"manifest_version"` — a
# schema version that must not track the release. The README rule cannot do
# that: its pins sit mid-sentence in prose that gets reflowed, so it anchors to
# the pin itself and expects both occurrences.
RULES: tuple[tuple[pathlib.Path, str, str, int], ...] = (
    (BUNDLE / "manifest.json", r'^(  "version": ")[^"]+(")', r"\g<1>{version}\g<2>", 1),
    (BUNDLE / "pyproject.toml", r'^(version = ")[^"]+(")', r"\g<1>{version}\g<2>", 1),
    (
        BUNDLE / "pyproject.toml",
        r'^(dependencies = \["lse-data-mcp==)[^"]+("\])',
        r"\g<1>{version}\g<2>",
        1,
    ),
    (ROOT / "README.md", r"(lse-data-mcp==)[0-9][0-9.]*", r"\g<1>{version}", 2),
)


def label(path: pathlib.Path) -> str:
    """Name a path for an error message, without assuming it sits under ROOT."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def root_version() -> str:
    """Return the version this release publishes to PyPI."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version: str = pyproject["project"]["version"]
    return version


def render(
    version: str,
    rules: tuple[tuple[pathlib.Path, str, str, int], ...] = RULES,
) -> dict[pathlib.Path, str]:
    """Return the intended content of every generated file."""
    rendered: dict[pathlib.Path, str] = {}

    for path, pattern, replacement, expected in rules:
        current = rendered.get(path, path.read_text(encoding="utf-8"))
        updated, count = re.subn(
            pattern,
            replacement.format(version=version),
            current,
            flags=re.MULTILINE,
        )
        # A rule that matches the wrong number of times means the file was
        # restructured and this script silently stopped generating part of it.
        # Fail instead: a bundle pinning the wrong version, or a README teaching
        # one, is worse than a failed release.
        if count != expected:
            raise SystemExit(
                f"{label(path)}: expected {expected} match(es) for {pattern!r}, found {count}."
            )
        rendered[path] = updated

    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the generated files are in step with the root version; write nothing",
    )
    args = parser.parse_args(argv)

    version = root_version()
    rendered = render(version)
    stale = [
        path for path, content in rendered.items() if content != path.read_text(encoding="utf-8")
    ]

    if args.check:
        for path in stale:
            print(
                f"{path.relative_to(ROOT)} does not declare {version}. "
                f"Run: python scripts/sync_bundle_version.py",
                file=sys.stderr,
            )
        return 1 if stale else 0

    for path in stale:
        path.write_text(rendered[path], encoding="utf-8")
        print(f"Wrote {version} into {path.relative_to(ROOT)}.")

    if not stale:
        print(f"Bundle already declares {version}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
