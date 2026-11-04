#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2790 (2026-08-31) — G53 keyed on `HUMAN-OWNED` while the PO
#          ruling it was pointed at named `HUMAN-REVIEW-PENDING` + a
#          review-ledger row. Two of the five files the ruling listed BY NAME
#          were invisible to it for a day, `apps/billing/gather.py` among them.
# Rules:   CLAUDE.md hard-won law 7 (prove a guard goes RED before trusting it
#          green) · law 1 (a comment claiming a guarantee is not the guarantee)
#          · DEF-182 (a check whose output cannot distinguish pass from fail is
#          worse than no check, because it is trusted)
# Impacts: 10-scripts/gates/g53_guard_list_coverage.py
# ───────────────────────────────────────────────────────
"""G53's own red-proof, executable — the guard that proves the guard-list guard fails.

WHY THIS FILE EXISTS
--------------------
`G53` was written on 2026-08-28 and its docstring said what it checked. It was
wrong about the condition it checked from the day it landed, and nothing noticed
for three days, because **the only statement of what it should do lived in a
decision-log entry and the only statement of what it did lived in its own
docstring, and no file compared the two.** That is `g12_selftest.py`'s lesson
repeated one gate over: a proof that exists as a sentence in a lane report is
not a proof, because nothing re-runs it.

So the proof is a file. It runs directly and needs nothing but Python 3.12 and
this repository:

    python3 10-scripts/gates/g53_selftest.py

TWO RULES IT FOLLOWS, BOTH LEARNED THE EXPENSIVE WAY
----------------------------------------------------
**1 · Every scenario is built from SYNTHETIC text, in a temporary directory.**
Not one case sabotages a real repo file. A self-test that breaks something the
repo has already broken reports `self-test BLIND` — a true sentence about the
wrong subject — and the run says nothing at all about the thing it was pointed
at. The first draft of this file did exactly that: four of its eleven scenarios
"passed" while every one of them was actually reporting an unrelated empty
baseline, and the flaw was visible only because the healthy control case failed
too. **Keep the healthy control case.** It is what tells you the fixture is
sound before any verdict about a break is worth reading.

**2 · Every scenario asserts on the MESSAGE, not only on the status.** A gate
that returns FAIL for the wrong reason is scored here as a failure. `DEF-182`:
a check whose output cannot distinguish pass from fail is worse than no check.

WHAT IT COVERS
--------------
  · `R1`/`R1b`/`R1c` — the DEF-2790 gap itself, from three sides: the widened
    gate names a `HUMAN-REVIEW-PENDING`-only file; the narrow gate is GREEN on
    the same input; and the narrow gate cannot even be reinstated silently,
    because clause `B1` refuses.
  · `R2` — a `HUMAN-OWNED` file with NO ledger row is still a finding. This is
    the clause that stops the ruling's `AND` being read as a filter, which would
    have let a file escape by opening no review row — an easier escape than the
    one the ruling closed.
  · `R3` — a parked name that is now guarded must be pruned from the named set.
  · `R4`, `R8` — the two self-test PRECONDITIONS: a probe no longer guarded, and
    a vanished named set. Both must say which precondition failed, never pass.
  · `R5` — a marker in a comment about ANOTHER file is not a declaration. A gate
    that names every file names none.
  · `R6`, `R7` — the guard list and the review ledger, each deleted in turn.
  · `R9`, `R10` — the classifier and the baseline parser, each sabotaged in turn,
    on a repo where nothing else is wrong.

It writes only into a temporary directory of its own and touches no repository
file, so running it can neither create nor destroy anything.
"""
from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import g53_guard_list_coverage as g53  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="g53-selftest-"))

REAL = dict(root=common.REPO_ROOT, guard=g53.GUARD_FILE, base=g53.BASELINE_FILE,
            ledger=g53.LEDGER_FILE, markers=g53.MARKERS, mis=g53.markers_in_source)

PROBE = "06-backend/apps/rating/engine.py"
GUARDED_MONEY = "06-backend/apps/ledger/posting.py"
PENDING_ONLY = "06-backend/apps/billing/gather_like.py"
OWNED_NO_ROW = "06-backend/core/money_like.py"
PLAIN = "06-backend/apps/billing/plain.py"
PARKED = "06-backend/apps/demo/already_parked.py"

PENDING_ONLY_SRC = '"""The one impure pass. 🔒 HUMAN-REVIEW-PENDING — money path."""\nX = 1\n'

#: A synthetic repository in which NOTHING is wrong: two guarded, marked files
#: with ledger rows; one ordinary file; one marked, unguarded file that is on
#: the named set, which is what a healthy real repo looks like.
HEALTHY_FILES = {
    PROBE: '"""Rating math kernel. HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 B4."""\nX = 1\n',
    GUARDED_MONEY: '"""The sole journal writer. HUMAN-OWNED · HUMAN-REVIEW-PENDING 🔒."""\nX = 1\n',
    PLAIN: '"""An ordinary read helper. Nothing sensitive here."""\nX = 1\n',
    PARKED: '"""Parked already. HUMAN-OWNED · HUMAN-REVIEW-PENDING 🔒."""\nX = 1\n',
}
HEALTHY_GUARD = [f"{PROBE} probe", f"{GUARDED_MONEY} ledger posting"]
HEALTHY_LEDGER = [PROBE, GUARDED_MONEY, PARKED]
HEALTHY_BASELINE = [PARKED]

results: list[bool] = []


def build(*, guard_lines, baseline_lines, ledger_paths, files) -> None:
    if TMP.exists():
        shutil.rmtree(TMP)
    (TMP / "10-scripts" / "gates").mkdir(parents=True)
    (TMP / "12-governance").mkdir(parents=True)
    for rel, src in files.items():
        path = TMP / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src).lstrip(), encoding="utf-8")
    (TMP / "10-scripts/gates/human_owned.txt").write_text(
        "# synthetic guard list\n" + "\n".join(guard_lines) + "\n", encoding="utf-8")
    (TMP / "10-scripts/gates/g53_unguarded_baseline.txt").write_text(
        "# synthetic named set\n" + "\n".join(baseline_lines) + "\n", encoding="utf-8")
    (TMP / "12-governance/09-human-review-ledger.md").write_text(
        "# synthetic ledger\n"
        + "".join(f"| `{p}` (NEW 🔒) | asked |\n" for p in ledger_paths), encoding="utf-8")
    common.REPO_ROOT = TMP
    g53.GUARD_FILE = TMP / "10-scripts/gates/human_owned.txt"
    g53.BASELINE_FILE = TMP / "10-scripts/gates/g53_unguarded_baseline.txt"
    g53.LEDGER_FILE = TMP / "12-governance/09-human-review-ledger.md"


def restore() -> None:
    """Put every patched name back. Nothing here may leak into the next case."""
    common.REPO_ROOT = REAL["root"]
    g53.GUARD_FILE, g53.BASELINE_FILE = REAL["guard"], REAL["base"]
    g53.LEDGER_FILE, g53.MARKERS = REAL["ledger"], REAL["markers"]
    g53.markers_in_source = REAL["mis"]


def healthy(**over):
    kw = dict(guard_lines=list(HEALTHY_GUARD), baseline_lines=list(HEALTHY_BASELINE),
              ledger_paths=list(HEALTHY_LEDGER), files=dict(HEALTHY_FILES))
    kw.update(over)
    return kw


def report(name: str, expect: str, must_say: list[str], status: str, message: str) -> None:
    said = all(s in message for s in must_say)
    ok = status == expect and said
    print(f"\n{'─' * 78}\n{name}")
    print(f"  expect {expect} saying {must_say!r}")
    print(f"  ->  {status}  {'PASS' if ok else 'UNEXPECTED'}"
          + ("" if said else "   (status matched but the MESSAGE was about something else)"))
    print(f'  "G53 guard-list-coverage {status}  {message}"')
    results.append(ok)


def scenario(name: str, expect: str, must_say: list[str], **kw) -> None:
    build(**healthy(**kw))
    status, message = g53.run()
    restore()
    report(name, expect, must_say, status, message)


def main() -> int:
    scenario("G0 · BASELINE HEALTH — the synthetic repo before anything is broken.\n"
             "     If this one fails, no verdict below means anything.",
             "PASS", ["clauses bite", "1 file(s) invoke", "every one of them named in"])

    scenario("R1 · A FILE CARRYING ONLY `HUMAN-REVIEW-PENDING` (the gather.py shape),\n"
             "     with a ledger row, unguarded, not baselined",
             "FAIL", [PENDING_ONLY, "with a review-ledger row already open",
                      "never add yourself"],
             ledger_paths=HEALTHY_LEDGER + [PENDING_ONLY],
             files={**HEALTHY_FILES, PENDING_ONLY: PENDING_ONLY_SRC})

    # R1b — the SAME input through the marker set this gate keyed on until
    # 2026-08-31, with the self-test silenced so the verdict is about the FILE
    # and not about the clause that now catches the narrowing.
    build(**healthy(ledger_paths=HEALTHY_LEDGER + [PENDING_ONLY],
                    files={**HEALTHY_FILES, PENDING_ONLY: PENDING_ONLY_SRC}))
    g53.MARKERS = ("HUMAN-OWNED",)
    g53.self_test = lambda guarded: []
    old_status, old_message = g53.run()
    restore()
    importlib.reload(g53)
    report("R1b · THE REGRESSION REPRODUCED: the same repo, the same file, through the\n"
           "      marker set G53 keyed on until 2026-08-31. THIS IS DEF-2790 — the gate\n"
           "      is GREEN and the money file is not mentioned.",
           "PASS", ["1 file(s) invoke", "none new"], old_status, old_message)

    build(**healthy())
    g53.MARKERS = ("HUMAN-OWNED",)
    status, message = g53.run()
    restore()
    report("R1c · AND IT CANNOT BE PUT BACK QUIETLY: narrow the marker set with the\n"
           "      self-test in place and the gate refuses to report at all, on a repo\n"
           "      where nothing else is wrong",
           "FAIL", ["self-test BLIND: B1", "exactly the gap DEF-2790 recorded"],
           status, message)

    scenario("R2 · A FILE CARRYING `HUMAN-OWNED` AND NO LEDGER ROW (the core/money.py\n"
             "     shape) — the ledger row is a SECOND finding, never a filter. Applied\n"
             "     as a filter, a file would escape by opening no review row.",
             "FAIL", [OWNED_NO_ROW, "with NO ledger row at all"],
             files={**HEALTHY_FILES, OWNED_NO_ROW:
                    '"""Money type. Rounding constants are HUMAN-OWNED."""\nX = 1\n'})

    scenario("R3 · A BASELINED NAME THAT IS NOW GUARDED — the named set must be pruned\n"
             "     in the same diff, or it hides the next arrival",
             "FAIL", ["are now guarded", GUARDED_MONEY],
             baseline_lines=HEALTHY_BASELINE + [GUARDED_MONEY])

    scenario("R4 · THE GLOB COVERING THE SELF-TEST PROBE IS REMOVED — clause A1 becomes\n"
             "     vacuous, and the gate names the precondition instead of passing",
             "FAIL", ["self-test BLIND: A1", "no longer matched by any glob"],
             guard_lines=[f"{GUARDED_MONEY} ledger posting"])

    scenario("R5 · A COMMENT MENTIONING ANOTHER FILE'S MARKER IS NOT A DECLARATION —\n"
             "     a gate that names every file names none",
             "PASS", ["1 file(s) invoke", "none new"],
             files={**HEALTHY_FILES, "06-backend/apps/billing/mentions.py":
                    '"""Ordinary."""\n# see money.py, which is HUMAN-REVIEW-PENDING\nX = 1\n'})

    build(**healthy())
    g53.GUARD_FILE.unlink()
    status, message = g53.run()
    restore()
    report("R6 · human_owned.txt DELETED", "FAIL", ["human_owned.txt is missing"],
           status, message)

    build(**healthy())
    g53.LEDGER_FILE.unlink()
    status, message = g53.run()
    restore()
    report("R7 · 09-human-review-ledger.md DELETED — half of what this gate reads",
           "FAIL", ["09-human-review-ledger.md is missing"], status, message)

    build(**healthy())
    g53.BASELINE_FILE.unlink()
    status, message = g53.run()
    restore()
    report("R8 · THE NAMED SET DELETED — the gate must say the list is gone, not\n"
           "     report the entire backlog as brand new",
           "FAIL", ["self-test BLIND: A2b", "baseline file is MISSING"], status, message)

    build(**healthy())
    real_markers_in_source = g53.markers_in_source
    g53.markers_in_source = lambda src: tuple(
        m for m in real_markers_in_source(src) if m != "HUMAN-REVIEW-PENDING")
    status, message = g53.run()
    restore()
    importlib.reload(g53)
    report("R9 · THE CLASSIFIER SABOTAGED — HUMAN-REVIEW-PENDING silently stops\n"
           "     counting, which is precisely the bug DEF-2790 records",
           "FAIL", ["self-test BLIND: B1"], status, message)

    build(**healthy())
    real_baseline_names = g53.baseline_names
    g53.baseline_names = lambda text: {ln.strip() for ln in text.split("\n") if ln.strip()}
    status, message = g53.run()
    restore()
    importlib.reload(g53)
    report("R10 · THE BASELINE PARSER SABOTAGED so a COMMENT counts as a parked name —\n"
           "      which is how a file nobody listed would get parked silently",
           "FAIL", ["self-test BLIND: A2", "PARK A FILE NOBODY LISTED"], status, message)

    if TMP.exists():
        shutil.rmtree(TMP)

    print(f"\n{'═' * 78}")
    print(f"G53 self-test: {sum(results)}/{len(results)} scenarios behaved as expected, "
          "message included")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
