#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-GOV-10345 (2026-10-21) — `i18n_fanin.py` sorted the whole
#          catalogue on every write, so a 3-key change became about 470
#          reordered lines in each of the eleven catalogues.
# Rules:   CLAUDE.md hard-won law 11 (never round-trip a shared file through a
#          serializer; a diff nobody can read is a check nobody can run) ·
#          hard-won law 7 (prove a guard goes RED before trusting it green)
# Impacts: 10-scripts/i18n_fanin.py · 07-frontend/src/i18n/locales/*.json
# ───────────────────────────────────────────────────────
"""A fan-in of N keys changes exactly N lines per catalogue, and nothing moves.

The catalogues here are synthetic and deliberately UNSORTED, because the live
ones are unsorted and that is what the old tool's "sorted by key" premise got
wrong. Against the tool as it stood on 2026-10-21 (whole-file `sorted(data)`)
the first test fails with every catalogue showing far more than N changed
lines; against the in-place tool every assertion holds.

Runs both ways::

    python3 10-scripts/tests/test_def_gov_10345_fanin_in_place.py
    pytest 10-scripts/tests/test_def_gov_10345_fanin_in_place.py
"""

from __future__ import annotations

import difflib
import importlib.util
import json
import pathlib
import tempfile

TOOL = pathlib.Path(__file__).resolve().parents[1] / "i18n_fanin.py"

# Unsorted on purpose: areas interleave and keys within an area are out of order.
BASE_KEYS = [
    "reports.title",
    "billing.run.start",
    "billing.run.cancel",
    "customers.list.title",
    "billing.invoice.total",
    "customers.detail.name",
    "audit.heading",
    "reports.rateImpact.input.type.charge",
    "reports.rateImpact.input.type.rate",
]


def _load_tool(locales: pathlib.Path):
    spec = importlib.util.spec_from_file_location("i18n_fanin_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOCALES = locales
    return module


def _seed(tool, locales: pathlib.Path) -> dict[str, str]:
    before = {}
    for lang in tool.LANGS:
        data = {key: f"{lang} {key} ✓" for key in BASE_KEYS}
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        (locales / f"{lang}.json").write_text(text, encoding="utf-8")
        before[lang] = text
    return before


def _changed(before: str, after: str) -> tuple[int, int]:
    """(lines added, lines removed) between two versions of a file."""
    added = removed = 0
    for line in difflib.ndiff(before.splitlines(), after.splitlines()):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return added, removed


def _batch(tool, keys: list[str]) -> dict[str, dict[str, str]]:
    return {key: {lang: f"{lang} new {key}" for lang in tool.LANGS} for key in keys}


def _after(tool, locales):
    return {lang: (locales / f"{lang}.json").read_text(encoding="utf-8") for lang in tool.LANGS}


def test_fan_in_of_n_keys_changes_exactly_n_lines():
    new = [
        "billing.run.review",           # sibling in the middle of the file
        "field.today.title",            # a brand-new area
        "field.today.empty",            # …and its sibling from the same batch
        "reports.rateImpact.input.x",   # sibling whose anchor is the FINAL entry
    ]
    with tempfile.TemporaryDirectory() as tmp:
        locales = pathlib.Path(tmp)
        tool = _load_tool(locales)
        before = _seed(tool, locales)
        tool.apply(_batch(tool, new))
        after = _after(tool, locales)
        for lang in tool.LANGS:
            added, removed = _changed(before[lang], after[lang])
            assert (added, removed) == (len(new), 0), (
                f"{lang}.json: a fan-in of {len(new)} keys changed +{added}/-{removed} lines"
            )
            keys = list(json.loads(after[lang]))
            old_order = [k for k in keys if k in BASE_KEYS]
            assert old_order == BASE_KEYS, f"{lang}.json: existing keys moved"
            # Placement rule: next to siblings; a new area stays together.
            assert keys.index("billing.run.review") == keys.index("billing.run.cancel") + 1
            assert keys.index("field.today.empty") == keys.index("field.today.title") + 1
            assert keys[-1] == "reports.rateImpact.input.type.rate", "the final entry was displaced"


def test_overwrite_changes_only_that_line():
    with tempfile.TemporaryDirectory() as tmp:
        locales = pathlib.Path(tmp)
        tool = _load_tool(locales)
        before = _seed(tool, locales)
        tool.apply(_batch(tool, ["customers.list.title"]), allow_overwrite=("customers.list.title",))
        after = _after(tool, locales)
        for lang in tool.LANGS:
            assert _changed(before[lang], after[lang]) == (1, 1), lang


def test_retire_of_n_keys_deletes_exactly_n_lines():
    gone = ["billing.run.start", "audit.heading"]
    with tempfile.TemporaryDirectory() as tmp:
        locales = pathlib.Path(tmp)
        tool = _load_tool(locales)
        before = _seed(tool, locales)
        tool.retire(gone)
        after = _after(tool, locales)
        for lang in tool.LANGS:
            assert _changed(before[lang], after[lang]) == (0, len(gone)), lang
            assert [k for k in json.loads(after[lang])] == [k for k in BASE_KEYS if k not in gone]


def test_a_file_in_another_shape_is_refused_and_nothing_is_written():
    with tempfile.TemporaryDirectory() as tmp:
        locales = pathlib.Path(tmp)
        tool = _load_tool(locales)
        before = _seed(tool, locales)
        squashed = json.dumps(json.loads(before["ko-KR"]), ensure_ascii=False) + "\n"
        (locales / "ko-KR.json").write_text(squashed, encoding="utf-8")
        try:
            tool.apply(_batch(tool, ["field.x"]))
        except SystemExit:
            pass
        else:
            raise AssertionError("a one-line catalogue was accepted")
        for lang in tool.LANGS:
            if lang != "ko-KR":
                assert (locales / f"{lang}.json").read_text(encoding="utf-8") == before[lang], lang


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
