#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2846 (2026-08-31) — THE `33 of 33` GOLDEN FIGURE EVERYTHING
#           CITES CHECKS THE DOCUMENT AND NEVER THE ENGINE, AND HALF THE GT
#           RANGE HAS NO ENGINE TEST. The harness is honest and says so in its
#           own docstring; its CITATIONS are not.
# Rules:    B5 ❄️ FROZEN (finance-signed 2026-08-08) — GT-1..61 are the
#           billing-math contract · CLAUDE.md hard-won law 1 (a comment claiming
#           a guarantee is not the guarantee) · law 7 (prove a guard goes RED)
# Impacts:  10-scripts/03-golden-verify.py (READ ONLY — never edited here) ·
#           06-backend/tests/golden/ · CLAUDE.md · README.md · 04-docs/**
# ───────────────────────────────────────────────────────
"""G64 — THE TWO GOLDEN NUMBERS MUST BE NAMEABLE APART.

WHAT WENT WRONG, IN ONE SENTENCE
--------------------------------
`33/33` is quoted across this repo — in CLAUDE.md, in the README, in module
rules, in status reports — beside the sentence *"GT-1..61 are the billing-math
contract"*, and a reader takes the pair to mean that the engine is checked
against 61 signed figures. **It is not.** They are two different numbers doing
two different jobs:

  * **DOCUMENT self-consistency — 33 checks.** `10-scripts/03-golden-verify.py`
    recomputes the workbook composites from fixtures using the ratified rules
    and checks the B5 prose fixtures for internal arithmetic consistency. It
    imports no application code. Its own docstring is exact about this: *"This
    verifies the DOCUMENTED expected values. It is QA scaffolding — it is not
    the rating engine."* It goes red when a DOCUMENT contradicts itself. **It
    cannot go red when the engine drifts.**

  * **ENGINE-VERIFIED coverage — the number this gate computes.** What actually
    hands inputs to `apps.billing.rating_seam` and asserts B5's frozen outputs
    is `06-backend/tests/golden/`. That is the number that protects a customer's
    bill, and **it is the smaller one.**

The harness never claimed otherwise. The citations did. DEF-2846 is a
correctness-of-the-record defect on the most-cited number in the repo.

WHAT THIS GATE CHECKS
---------------------
**Clause 1 — the engine number is RECORDED and cannot drift silently.** The GT
ids exercised by `06-backend/tests/golden/test_gt*.py` are computed from the
filenames and compared with `g64_engine_verified_gts.txt`. Add or delete an
engine golden test and this fails until the record moves in the same commit.
The file is the identity, not a ceiling, on the G28 pattern: it names WHICH GTs,
because "14" tells a reader nothing about whether GT-24 is one of them.

**Clause 2 — a live document that quotes the harness count must also name the
engine one.** Any file in the live set below containing `33/33` or `33 of 33`
must also contain the phrase `engine-verified`. It is deliberately a VOCABULARY
check and not a numeric one: coupling prose to the count itself would force a
documentation sweep every time somebody adds a golden test, which is the mass
shared-file rewrite law 11 exists to prevent.

WHAT IS DELIBERATELY OUT OF SCOPE, AND WHY — READ THIS BEFORE WIDENING IT
------------------------------------------------------------------------
* **`04-docs/02-decisions/04-money-math-rules.md` and `05-golden-tests.md` are
  ❄️ FROZEN** (finance-signed 2026-08-08). Both still open with *"verification
  harness green (33/33)"*, which is TRUE of the harness and is the sentence a
  reader most often turns into a claim about the engine. **Correcting them is a
  finance re-sign under HUMAN-GUIDE §6, never an inline edit** — CLAUDE.md is
  explicit — so they are excluded here and the gap is recorded in DEF-2846
  rather than quietly fixed. This is the one place this gate knowingly leaves
  the defect standing.

* **The registers, the CHANGELOG and the dated reports are excluded because they
  are the RECORD OF WHAT WAS SAID AT THE TIME.** `02-decision-log.md` alone
  carries 22 occurrences and `09-human-review-ledger.md` 24. Rewriting a signed
  ruling to read better today is not a correction, it is a forgery of the
  record; the same principle that keeps a superseded B5 draft in place with a
  stamp over it.

PROVED RED BEFORE TRUSTED GREEN (law 7)
---------------------------------------
Part 0 replays the defect on both clauses, in memory, and nothing is written to
disk: clause 1 is re-run against a doctored id set, and clause 2 against a
document body with the vocabulary stripped out. Either one failing to bite fails
this gate — a check that cannot go red is worse than no check (DEF-182).

⚠ **THIS GATE NEVER RUNS, IMPORTS OR EDITS `10-scripts/03-golden-verify.py`.**
It reads filenames and prose. No priced arithmetic is anywhere near it.

Python 3.12 stdlib only. Safe to run from any cwd.

    python3 10-scripts/gates/g64_golden_engine_coverage.py
    python3 10-scripts/gates/g64_golden_engine_coverage.py --report
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOLDEN_TESTS = REPO / "06-backend" / "tests" / "golden"
IDENTITY = Path(__file__).resolve().parent / "g64_engine_verified_gts.txt"

#: B5's signed range. GT-1..61 is the billing-math contract, quoted from the
#: ❄️ FROZEN banner; it is a constant of the freeze, not a measurement.
GT_RANGE = 61

#: The harness count, as the documents quote it. Read as a STRING to match on,
#: never as an assertion about the harness — this gate does not run it.
HARNESS_CITATION = re.compile(r"\b33\s*(?:/|of)\s*33\b")

#: The vocabulary that makes the two numbers nameable apart.
ENGINE_VOCAB = re.compile(r"engine-verified", re.I)

#: Files that describe the product TODAY. A reader takes these as current.
LIVE_DOCS = [
    "CLAUDE.md",
    "README.md",
    "CONTRIBUTING.md",
    "HUMAN-GUIDE.md",
]
LIVE_DOC_TREES = ["04-docs"]

#: ❄️ FROZEN — a finance re-sign, never an inline edit (HUMAN-GUIDE §6).
FROZEN = {
    "04-docs/02-decisions/04-money-math-rules.md",
    "04-docs/02-decisions/05-golden-tests.md",
}


def engine_verified_gts() -> dict[int, str]:
    """`{GT number: test file}` for every golden test that runs the engine.

    Keyed on the FILENAME (`test_gt24_budget_chain.py` -> 24) and not on GT ids
    found in the text, because these files quote neighbouring GTs constantly in
    their own prose — `test_gt04` discusses GT-14, `test_gt07` points at
    GT-35..50 — and a text scan reads those as coverage. That is the DEF-2846
    mistake one level down: counting a mention as a check.
    """
    found: dict[int, str] = {}
    if not GOLDEN_TESTS.is_dir():
        return found
    for path in sorted(GOLDEN_TESTS.glob("test_gt*.py")):
        m = re.match(r"test_gt(\d+)_", path.name)
        if m:
            found[int(m.group(1))] = path.name
    return found


def _recorded() -> dict[int, str]:
    if not IDENTITY.exists():
        return {}
    out: dict[int, str] = {}
    for line in IDENTITY.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        gt, _, fname = s.partition(" ")
        m = re.fullmatch(r"GT-(\d+)", gt)
        if m:
            out[int(m.group(1))] = fname.strip()
    return out


def _live_doc_paths() -> list[Path]:
    paths = [REPO / name for name in LIVE_DOCS]
    for tree in LIVE_DOC_TREES:
        paths.extend(sorted((REPO / tree).rglob("*.md")))
    return [p for p in paths if p.is_file() and str(p.relative_to(REPO)) not in FROZEN]


def _uncorrected_docs(strip_vocab: bool = False) -> list[str]:
    out = []
    for path in _live_doc_paths():
        text = path.read_text(encoding="utf-8", errors="replace")
        if not HARNESS_CITATION.search(text):
            continue
        if strip_vocab:
            text = ENGINE_VOCAB.sub("", text)
        if not ENGINE_VOCAB.search(text):
            out.append(str(path.relative_to(REPO)))
    return out


def summary() -> str:
    live = engine_verified_gts()
    ids = ", ".join(f"GT-{n}" for n in sorted(live))
    return (
        f"document self-consistency: 33 checks (10-scripts/03-golden-verify.py — it "
        f"recomputes B4/B5 figures and imports no application code, so it cannot go red "
        f"when the engine drifts). "
        f"ENGINE-VERIFIED: {len(live)} of {GT_RANGE} GTs, in {len(live)} test file(s) under "
        f"06-backend/tests/golden/ — {ids}. "
        f"The second number is the one that protects a customer's bill, and it is the "
        f"smaller one."
    )


def run() -> tuple[str, str]:
    live = engine_verified_gts()
    if not live:
        return "SKIP", "nothing to check — 06-backend/tests/golden/ holds no test_gt*.py"

    # ── CLAUSE 1 · the engine number is recorded ─────────────────────────
    recorded = _recorded()
    if live != recorded:
        added = sorted(set(live) - set(recorded))
        gone = sorted(set(recorded) - set(live))
        moved = sorted(n for n in set(live) & set(recorded) if live[n] != recorded[n])
        parts = []
        if added:
            parts.append("not recorded: " + ", ".join(f"GT-{n} ({live[n]})" for n in added))
        if gone:
            parts.append("recorded but gone: " + ", ".join(f"GT-{n}" for n in gone))
        if moved:
            parts.append("renamed: " + ", ".join(f"GT-{n} -> {live[n]}" for n in moved))
        return "FAIL", (
            f"the engine-verified GT set does not match {IDENTITY.name} — "
            + "; ".join(parts)
            + ". Move the record in the SAME commit; an engine golden test that arrives "
            "or leaves without it changes the only number that protects a bill (DEF-2846)"
        )

    # ── CLAUSE 2 · a live doc quoting the harness names the engine too ───
    bad = _uncorrected_docs()
    if bad:
        return "FAIL", (
            f"{len(bad)} live document(s) quote the harness count (33/33) and never name the "
            f"engine one, so a reader takes 'GT-1..61 are the billing-math contract' beside it "
            f"as the engine being checked against 61 signed figures (DEF-2846). It is "
            f"{len(live)} of {GT_RANGE}. Say both, and use the words 'engine-verified' for the "
            f"second: {', '.join(bad)}"
        )

    # ── PART 0 · SELF-TEST (law 7): do both clauses bite? ────────────────
    doctored = dict(live)
    doctored.pop(sorted(doctored)[0])
    if doctored == recorded:
        return "FAIL", (
            "SELF-TEST FAILED: dropping a GT from the computed set still matched the "
            "record, so clause 1 is not comparing anything"
        )
    stripped = _uncorrected_docs(strip_vocab=True)
    citing = [
        str(p.relative_to(REPO))
        for p in _live_doc_paths()
        if HARNESS_CITATION.search(p.read_text(encoding="utf-8", errors="replace"))
    ]
    if citing and not stripped:
        return "FAIL", (
            f"SELF-TEST FAILED: {len(citing)} live document(s) cite the harness count, and "
            "removing the word 'engine-verified' from all of them produced no finding — "
            "clause 2 is matching nothing and would pass on a document that never named "
            "the engine number at all"
        )

    return "PASS", (
        summary()
        + f" | clause 2: {len(citing)} live document(s) cite the harness count and every one "
        f"of them also names the engine one; self-test: stripping the vocabulary surfaces "
        f"{len(stripped)} again, so the check bites."
    )


def main() -> int:
    if "--report" in sys.argv:
        print(summary())
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
