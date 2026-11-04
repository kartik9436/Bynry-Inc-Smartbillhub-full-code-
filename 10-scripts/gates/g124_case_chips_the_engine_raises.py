#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2596 — the bill run's step-3 case filter declares FIFTEEN case
#          kinds and the engine emits NINE. Six of the fifteen can never have a
#          row behind them, so a clerk can pick a filter, get an empty table,
#          and have no way to tell "none this run" from "this can never
#          happen". Re-measured at v2.261.4 by CR-100-BRC03 step 1 and still
#          true 26 versions after it was filed.
# Rules:   Billing blueprint §03 p041, ruled 2026-09-11 — *"A case kind the
#          engine did not raise GETS NO CHIP… The as-built screen declares
#          fifteen"* · CLAUDE.md hard-won law 2 (built is not wired — here the
#          mirror: a control wired to something that cannot occur) · law 12
#          (never hand-type a list; where one must be typed, CHECK it against
#          the thing it mirrors) · law 7 (proved RED first — `selftest()`)
# Tests:   selftest() below, which plants a dead kind in a copy of the real
#          front-end text and asserts the scanner names it, and plants a live
#          one and asserts it does not
# Impacts: 07-frontend/src/features/billing/billRunShared.tsx
#          07-frontend/src/features/billing/billRunStep23.tsx
#          06-backend/apps/billing/read_analysis.py · runs.py
# ───────────────────────────────────────────────────────
"""A case kind the screen offers as a filter must be one the engine can raise.

WHY THIS GATE EXISTS
--------------------
The bill-run review screen groups accounts by CASE KIND — *missing read*,
*unusually large*, *meter changed* — and each kind is a filter a clerk picks.
The list of kinds is typed out in the front end. The list of kinds the engine
can actually produce is typed out in the back end. **Nothing compared them**,
and they had drifted by six.

The six were `no_usage`, `overcharge`, `owes`, `past_due`, `late_fee` and
`extra_charge`. Four of them are real entries in `DECISION_CASES` — the server
would happily record a decision on one — and no code path anywhere creates a
row with that case, so the filter could never have a row behind it. Two of them
(`owes`, `past_due`) are not even in `DECISION_CASES`: a decision on one could
not have been stored if a row had somehow appeared.

⚠ **EVERY CHECK IN THIS REPOSITORY PASSED OVER IT AND ALL OF THEM WERE RIGHT
TO.** `tsc` type-checks a list of strings. The unit tests assert the families
partition the tabs — which they did, exactly, all fifteen of them. The gates
read classes, props, routes and translation keys. **The question "can this kind
ever occur" lives on the other side of the language boundary**, and no check in
this repo had ever crossed it.

WHAT IT READS — BOTH SIDES, INDEPENDENTLY
-----------------------------------------
**The EMITTED side, from Python.** Two producers and no others:

* `apps/billing/read_analysis.py` — `READ_ANALYSIS_CASES`, a tuple of
  `CASE_*` constants, each resolved to its own string literal in that file;
* `apps/billing/runs.py` — every `reason="<literal>"` on an `AccountProblem`,
  which is what `selectors.run_exception_rows` turns into a case row's `case`.

**The DECLARED side, from TypeScript.** `CASE_TABS` in
`features/billing/billRunShared.tsx` — the single list every case filter, chip
and family is derived from.

Then: **every declared id must be emitted.** The other direction is NOT a
failure — an engine kind the screen does not yet draw is a build item, and it
is reported in the PASS line rather than failed, because `casesWithoutFamily()`
already puts that one on screen where a clerk can see it.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — asked before trusting it (law 7).**
Three ways, and each is refused BY NAME rather than left to luck:

1. **The front-end scan finds nothing** — the file moved, the constant was
   renamed, the regex rotted. `declared - emitted` is then the empty set and
   the gate reports a clean PASS over a list it never read. **Refused:** an
   empty or implausibly short declared list is a FAIL, not a pass.
2. **The back-end scan finds nothing** — same shape, opposite side. That one
   fails loudly on its own (every declared id becomes a finding), but it fails
   with a misleading message, so an empty emitted set is named as the cause.
3. **The self-test cannot fail.** A scanner proved on the tree it is scanning
   proves nothing once that tree is clean. **Refused:** `selftest()` plants a
   dead kind in a COPY of the real text and requires the scanner to name it,
   and plants a live kind and requires it not to.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend" / "apps" / "billing"
READ_ANALYSIS = BACKEND / "read_analysis.py"
RUNS = BACKEND / "runs.py"
SHARED = ROOT / "07-frontend" / "src" / "features" / "billing" / "billRunShared.tsx"

#: Below this, the declared list was not really read — see hazard 1 above.
DECLARED_FLOOR = 5

_CONST = re.compile(r"^(CASE_[A-Z0-9_]+)\s*=\s*\"([a-z0-9_]+)\"", re.MULTILINE)
_TUPLE = re.compile(r"READ_ANALYSIS_CASES[^=]*=\s*\((.*?)\)", re.DOTALL)
_REASON = re.compile(r"""reason\s*=\s*["']([a-z0-9_]+)["']""")
_TABS = re.compile(r"export const CASE_TABS[^=]*=\s*\[(.*?)\n\];", re.DOTALL)
_TAB_ID = re.compile(r"""\{\s*id:\s*["']([a-z0-9_]+)["']""")

#: The constructor whose rows become case chips. ⚠ **SCOPED ON PURPOSE.**
#: `runs.py` also builds `Break(reason=…)` rows, and a break is a different
#: table, a different screen and NOT a case kind. A bare `reason="…"` scan
#: reported `rule_refused` as a tenth emitted kind on the first run of this
#: gate — a wrong answer in the safe direction, which is the kind that survives
#: longest. The rows read here are the ones `selectors.run_exception_rows`
#: turns into the chips, via `prepared.decisions`.
_DECISION_CTOR = "AccountProblem("


def _constructor_literals(text: str, ctor: str, window: int = 600) -> set[str]:
    """Every `reason="<literal>"` inside a `ctor(...)` call.

    A bounded look-ahead rather than a parser: the call is a few lines long in
    every occurrence, and a parser here would be more machinery than the
    question needs. The window is generous enough to clear the comment blocks
    that sit between `AccountProblem(` and its `reason=` in this file.
    """
    found: set[str] = set()
    at = text.find(ctor)
    while at != -1:
        match = _REASON.search(text, at, at + window)
        if match is not None:
            found.add(match.group(1))
        at = text.find(ctor, at + len(ctor))
    return found


def emitted_cases() -> tuple[set[str], list[str]]:
    """Every case kind a run can actually produce, read from the two producers.

    Returns the set and the human sentence saying where each half came from, so
    the PASS line can be checked rather than trusted.
    """
    notes: list[str] = []
    found: set[str] = set()

    text = READ_ANALYSIS.read_text(encoding="utf-8")
    constants = {name: value for name, value in _CONST.findall(text)}
    block = _TUPLE.search(text)
    analysis: set[str] = set()
    if block is not None:
        for name in re.findall(r"CASE_[A-Z0-9_]+", block.group(1)):
            if name in constants:
                analysis.add(constants[name])
    found |= analysis
    notes.append(f"{len(analysis)} from read_analysis.READ_ANALYSIS_CASES")

    # `AccountProblem(reason="<literal>")` is what becomes a case row's `case`.
    # The module also builds problems for HOLD reasons (`RUN_NO_SCOPE`,
    # `PRICING_REFUSED`, …) — those are CONSTANTS, not literals — and `Break`
    # rows, which are a different table and a different screen. Only the
    # literal form, and only inside the decision constructor.
    decisions = _constructor_literals(RUNS.read_text(encoding="utf-8"), _DECISION_CTOR)
    found |= decisions
    notes.append(f"{len(decisions)} from runs.py `AccountProblem(reason=…)` literals")

    return found, notes


def declared_cases() -> list[str]:
    """`CASE_TABS`' ids, in the order the screen draws them."""
    block = _TABS.search(SHARED.read_text(encoding="utf-8"))
    if block is None:
        return []
    return _TAB_ID.findall(block.group(1))


def dead_in(declared: list[str], emitted: set[str]) -> list[str]:
    return [one for one in declared if one not in emitted]


def selftest() -> bool:
    """Plant a dead kind in a COPY of the real text; require the scanner to
    name it. Then plant a live one and require it not to.

    ⚠ This does NOT read the tree's own verdict. A scanner self-tested against
    the tree it is scanning says nothing once that tree is clean — the exact
    *incapable of failing* shape law 7 names.
    """
    emitted, _ = emitted_cases()
    if not emitted:
        return False
    live = sorted(emitted)[0]
    planted = ["missing_read", "a_kind_no_engine_raises", live]
    findings = dead_in(planted, emitted)
    if findings != ["a_kind_no_engine_raises"]:
        return False
    return dead_in([live], emitted) == []


def run() -> tuple[str, str]:
    for path in (READ_ANALYSIS, RUNS, SHARED):
        if not path.is_file():
            return "SKIP", f"{path.relative_to(ROOT)} is not present"

    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it could not tell a planted dead case "
            "kind from a live one, so its verdict is worthless (hard-won law 7)"
        )

    emitted, notes = emitted_cases()
    declared = declared_cases()

    # Hazard 1 — an unread list must never read as a clean list.
    if len(declared) < DECLARED_FLOOR:
        return "FAIL", (
            f"CASE_TABS in {SHARED.relative_to(ROOT)} yielded {len(declared)} id(s), below the "
            f"floor of {DECLARED_FLOOR} — the constant was renamed, moved or reshaped and this "
            "gate was reading nothing. A silent empty scan is how a check reports zero over a "
            "scope it excludes"
        )
    # Hazard 2 — name the real cause rather than blaming every declared id.
    if not emitted:
        return "FAIL", (
            "no case kind could be read from read_analysis.py or runs.py, so every declared "
            "kind looks dead — the emitter scan is what is broken, not the screen"
        )

    findings = dead_in(declared, emitted)
    if findings:
        return "FAIL", (
            f"{len(findings)} case kind(s) offered as a filter that the engine cannot raise — a "
            "clerk can pick one and can never tell 'none this run' from 'this can never happen' "
            f"(DEF-2596, blueprint §03 p041): {', '.join(findings)}. Engine emits "
            f"{len(emitted)}; the screen declares {len(declared)}"
        )

    undrawn = sorted(emitted - set(declared))
    return "PASS", (
        f"all {len(declared)} case kind(s) the screen offers are raised by the engine "
        f"({len(emitted)} emitted: {'; '.join(notes)})"
        + (
            f" — {len(undrawn)} engine kind(s) the screen does not draw, reported on screen by "
            f"`casesWithoutFamily()` rather than failed here: {', '.join(undrawn)}"
            if undrawn
            else " — and the screen draws every one of them"
        )
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
