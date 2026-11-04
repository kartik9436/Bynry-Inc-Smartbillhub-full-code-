#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3422 (2026-09-02) — `bell_events` has a table, an index, and a
#          writer whose docstring calls itself "the only sanctioned writer".
#          The writer hands its item to a sink nothing ever registered, so it
#          logs and returns None; nothing reads the table either. The bell says
#          "You're all caught up" and always will. Found by asking this
#          question, not by reading code.
# Rules:   CLAUDE.md hard-won law 2 (BUILT IS NOT WIRED) · law 1 (a comment
#          claiming a guarantee is not the guarantee) · law 7 (prove a guard
#          RED before trusting it green)
# Tests:   `selftest()` below — run() refuses to report until it has passed.
# ───────────────────────────────────────────────────────
"""G74 — A TABLE THIS PRODUCT DEFINES IS A TABLE SOME CODE TOUCHES.

**THE PATTERN THIS CATCHES COST THREE FINDINGS IN ONE DAY** — 2026-09-02:

  * the notification bell, above;
  * the diagnostics record, written and served by no endpoint until it was
    found (`DEF-3321`);
  * seven finished payment backends with no screen, which no single task row
    could see because each was honestly recorded as "not closed yet".

Each is the same shape: a thing is built, and the wire from it to a person is
missing. Nothing was wrong with any of the code. **The question nobody asked is
whether the thing has a reader at all.**

WHY IT IS THIS QUESTION AND NOT THE OBVIOUS ONE
------------------------------------------------
The obvious check — *does this model appear in a `selectors.py` or an `api.py`*
— was measured first and flags **40 of 143 models**. Most of those are correct:
a model reached through a related name, a through-table, a row a service walks.
A gate that fires on forty correct things is switched off within a week, and
then it protects nothing — which is the lesson a sibling lane wrote down the
same day after testing its own proposal across all 67 change requests and
finding it would fail on `CR-052`'s deliberate repetition.

So the question is narrowed to the one that cannot be answered innocently:
**is this model mentioned by ANY file that is not its own definition, a
migration, or a seeder?** A model nothing else names anywhere is not reached by
a related name, walked by a service, or read by a report. It is furniture.
Measured on the branch the day this landed: **3 of 143.**

WHAT A FINDING MEANS, AND WHAT IT DOES NOT
-------------------------------------------
A finding is *"nothing in this product touches this table"*. It is NOT a claim
that the table is wrong to exist — a table landed ahead of the story that fills
it is an ordinary, honest state. What it must not be is SILENT, because the
silence is indistinguishable from a feature that works.

So this is a RATCHET, not a wall: the three that exist are named in the
baseline with what is owed on each, and the count **may fall and may never
rise**. Fixing one means deleting its line, which is the same shape as the
other ratchets in this directory.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "06-backend"
BASELINE = pathlib.Path(__file__).with_name("g74_unread_tables_baseline.txt")

#: A file that DEFINES a model does not count as a reader of it — the question
#: is whether anything ELSE in the product touches it.
#:
#: ⚠ **A SEEDER *DOES* COUNT, AND THE FIRST DRAFT OF THIS FILE HAD IT WRONG.**
#: Excluding `sample_data.py` as well looked obviously right — a seeder writing
#: rows proves nothing about whether a person can ever see them — and it made
#: this gate report `SampleDataRun`, which the sign-up screen reads on every
#: poll through `sample_data.run_summary()`. The table is the SEEDER'S OWN
#: LEDGER rather than something it seeds, so its seeder is a legitimate reader.
#:
#: The narrower rule is kept because the wider one produced a false finding on
#: its first run, and a check that fires on correct work is switched off within
#: a week (`DEF-182`). The cost of the narrower rule is stated rather than
#: hidden: a model that ONLY a seeder touches will not be reported here. That
#: is a real gap and it is the right trade — a silent false negative costs one
#: missed table, a false positive costs the whole gate.
NOT_A_READER = ("migrations", "models.py")


def _models() -> dict[str, str]:
    """Every Django model class, mapped to the app that declares it."""
    found: dict[str, str] = {}
    for path in sorted(BACKEND.glob("apps/*/models.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"^class (\w+)\(([^)]*)\):", text, re.M):
            if "Model" in match.group(2) or "Base" in match.group(2):
                found[match.group(1)] = path.parent.name
    return found


def _unread(models: dict[str, str], extra_reader: dict[str, str] | None = None) -> list[str]:
    """Model names no file outside their own definition mentions.

    `extra_reader` is the selftest's seam: a synthetic {path: text} pair, so a
    sabotage can be applied without writing to the tree.
    """
    texts: list[str] = []
    for path in BACKEND.glob("apps/**/*.py"):
        if any(part in str(path) for part in NOT_A_READER):
            continue
        texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    for path in (BACKEND / "core").glob("*.py"):
        texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    if extra_reader:
        texts.extend(extra_reader.values())
    blob = "\n".join(texts)
    return sorted(name for name in models if not re.search(rf"\b{name}\b", blob))


def _baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    out = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0])
    return out


def selftest() -> tuple[bool, str]:
    """Law 7, both ways: it must SEE a table nothing reads, and must NOT see one
    that something does. A check whose output cannot tell pass from fail is
    worse than no check, because it is trusted (DEF-182)."""
    models = {"AaaFakeUnreadModel": "tenancy", "Tenant": "tenancy"}
    blind = _unread(models)
    if "AaaFakeUnreadModel" not in blind:
        return False, "a model nothing mentions was NOT reported — the check is blind"
    if "Tenant" in blind:
        return False, "`Tenant` was reported unread, and the whole product reads it"
    seeing = _unread(models, extra_reader={"synthetic": "AaaFakeUnreadModel.objects.all()"})
    if "AaaFakeUnreadModel" in seeing:
        return False, "one mention did not clear the finding — the check cannot be satisfied"
    return True, "3/3 clauses bite"


def run() -> tuple[str, str]:
    ok, how = selftest()
    if not ok:
        return "FAIL", f"self-test failed, so nothing below is trustworthy: {how}"
    models = _models()
    unread = _unread(models)
    known = _baseline()
    new = [n for n in unread if n not in known]
    gone = [n for n in known if n not in unread]
    detail = (
        f"law 2: {len(models)} model(s) declared; {len(unread)} that no file outside their own "
        f"definition, a migration or a seeder mentions ({len(known)} baselined). "
        f"self-test: {how}"
    )
    if gone:
        detail += (
            f" | {len(gone)} baselined table(s) now have a reader — delete them from "
            f"{BASELINE.name} to hold the gain: {', '.join(sorted(gone))}"
        )
    if new:
        return "FAIL", (
            f"{len(new)} table(s) nothing in this product touches, and not baselined: "
            f"{', '.join(f'{n} ({models[n]})' for n in new)}. A table with no reader is not "
            f"wrong to exist — it is wrong to be SILENT about, because the silence is "
            f"indistinguishable from a feature that works (law 2). Name it in "
            f"{BASELINE.name} with what is owed, or wire it. | {detail}"
        )
    return "PASS", detail


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}  {detail}")
    sys.exit(0 if status == "PASS" else 1)
