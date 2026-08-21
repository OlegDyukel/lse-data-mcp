"""Tests for the release-time version sync script.

The script is not part of the installed package, so it is loaded from its path
rather than imported.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sync_bundle_version.py"

# A pin pattern that ignores the surrounding prose, so reflowing a paragraph
# cannot quietly stop the rule from matching.
PIN = r"(lse-data-mcp==)[0-9][0-9.]*"


def _load() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("sync_bundle_version", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = _load()


def test_render_updates_both_readme_pin_examples() -> None:
    rendered = sync.render("9.9.9")

    readme = rendered[ROOT / "README.md"]
    assert readme.count("lse-data-mcp==9.9.9") == 2


def test_render_rewrites_every_match_when_a_rule_expects_several(
    tmp_path: pathlib.Path,
) -> None:
    target = tmp_path / "doc.md"
    target.write_text("pin lse-data-mcp==0.0.1 here\nand lse-data-mcp==0.0.1 there\n")
    rules = ((target, PIN, r"\g<1>{version}", 2),)

    rendered = sync.render("9.9.9", rules)

    assert rendered[target].count("lse-data-mcp==9.9.9") == 2


def test_render_rejects_a_file_whose_match_count_changed(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "doc.md"
    target.write_text("only one lse-data-mcp==0.0.1 pin\n")
    rules = ((target, PIN, r"\g<1>{version}", 2),)

    with pytest.raises(SystemExit, match="expected 2"):
        sync.render("9.9.9", rules)
