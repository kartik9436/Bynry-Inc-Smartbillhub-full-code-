#!/usr/bin/env python3
"""Recover every message key and its English from the CALL SITES.

WHY THIS EXISTS — DEF-717
-------------------------
Lanes are banned from editing the eleven locale catalogues, so all session they
handed keys to the coordinator as `newkeys-<lane>.json` in the scratchpad. Three
of those files were then LOST when the scratchpad was reaped, taking 350+ keys
with them.

The bitter part is the precedent. `10-scripts/i18n_fanin.py` — the tool that
CONSUMES those files — was moved into this directory earlier the same day for
exactly this reason; its docstring says *"the scratchpad is not durable; the
repo is"* and records that it had been rewritten from scratch three times. **The
tool was saved and the data it eats was left where the tool had been dying.**

So this script does not read a handoff file at all. It reads what actually
survived: `t("some.key", { defaultValue: "English sentence" })` in the frontend
source. Those call sites are in git, they cannot be reaped, and they cannot go
stale relative to the code — they ARE the code.

WHAT IT GUARANTEES
------------------
1. **Only genuinely missing keys.** Anything already in `en.json` is skipped, so
   output is the work remaining, never a re-statement of the catalogue.
2. **One English per key, or a loud refusal.** Two call sites giving one key
   different defaults is a real conflict a human must settle — it is reported
   and the key is withheld, never silently resolved by taking the first.
3. **Test files are ignored.** A default written in a `.test.tsx` is fixture
   text, not product copy.
4. **Output is fan-in shaped** — `{key: {"en": text}}` — so it pipes straight
   into `i18n_fanin.py` once the other ten languages are filled in.

USAGE
    python3 10-scripts/i18n_extract_defaults.py            # report
    python3 10-scripts/i18n_extract_defaults.py -o out.json

⚠ It recovers the ENGLISH ONLY. The other ten languages are still translation
work; this just means losing a handoff file costs nothing but the translations,
which were never in those files either.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "07-frontend" / "src"
EN = SRC / "i18n" / "locales" / "en.json"

#: `t("key", { ... defaultValue: "text" ... })`. Non-greedy to the first `}` so a
#: nested object ends the match rather than swallowing the file.
CALL = re.compile(
    r"""\bt\(\s*["'`](?P<key>[A-Za-z0-9_.]+)["'`]\s*,\s*\{(?P<opts>[^{}]*)\}""",
    re.S,
)
DEFAULT = re.compile(r"""defaultValue\s*:\s*(?P<q>["'])(?P<text>(?:\\.|(?!(?P=q)).)*)(?P=q)""", re.S)


def extract() -> tuple[dict[str, dict[str, str]], dict[str, set[str]], int]:
    known = set(json.loads(EN.read_text(encoding="utf-8")))
    found: dict[str, str] = {}
    conflicts: dict[str, set[str]] = {}
    sites = 0
    for path in sorted(SRC.rglob("*.ts*")):
        if ".test." in path.name or ".spec." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        for call in CALL.finditer(text):
            found_default = DEFAULT.search(call.group("opts"))
            if not found_default:
                continue
            sites += 1
            key = call.group("key")
            # ⚠ **`unicode_escape` MANGLES EVERY NON-ASCII CHARACTER IT RECOVERS
            # (DEF-768).** This read
            # `.group("text").encode().decode("unicode_escape")`, and `.encode()`
            # produces UTF-8 BYTES which `unicode_escape` then decodes as
            # latin-1 — so a literal em-dash comes back `â\x80\x94` and `·`
            # comes back `Â·`. Measured: 23 of 75 strings on one real handoff.
            # ⚠ **AND THE BLAST RADIUS IS THE WHOLE POINT.** This script exists to
            # RECOVER keys after a handoff file is lost (DEF-717), and its output
            # is fan-in shaped — so the next lane that loses a handoff writes
            # mojibake into all ELEVEN catalogues in one command, and G15 passes,
            # because mojibake is not English. `json.loads` handles both an
            # escape sequence and a literal UTF-8 character, which is what the
            # source actually contains.
            english = json.loads('"' + found_default.group("text") + '"')
            if key in known:
                continue
            if key in found and found[key] != english:
                conflicts.setdefault(key, {found[key]}).add(english)
                continue
            found[key] = english
    for key in conflicts:
        found.pop(key, None)
    return {k: {"en": v} for k, v in sorted(found.items())}, conflicts, sites


def main(argv: list[str]) -> int:
    batch, conflicts, sites = extract()
    print(f"scanned {sites} call site(s) carrying a defaultValue")
    print(f"{len(batch)} key(s) used in code and MISSING from en.json")
    if conflicts:
        print(f"\n⚠ {len(conflicts)} key(s) WITHHELD — one key, two different English strings.")
        print("   A human settles these; taking the first would pick a winner by file order.")
        for key, texts in sorted(conflicts.items()):
            print(f"   {key}")
            for one in sorted(texts):
                print(f"       {one!r}")
    if "-o" in argv:
        out = pathlib.Path(argv[argv.index("-o") + 1])
        out.write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
