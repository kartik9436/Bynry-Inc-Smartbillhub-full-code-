# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2102 — the 🔒 guard list is maintained BY HAND, and a new money
#          file joins the CODE without joining the LIST. Four recorded
#          occurrences before this gate existed, each found by a person:
#          `issue.py`, `decisions.py`, `read_analysis.py`, and on 2026-08-28
#          `resolution.py` + `resolution_catalogue.py` + `resolution_shadow.py`
#          (added by PO ruling) and the deposit lane's three.
#          DEF-2790 (2026-08-31) — this gate tested a NARROWER condition than
#          the ruling that was answered by pointing at it, and two of the five
#          files the ruling NAMED escaped it. Widened here.
# Rules:   CLAUDE.md 🔒 sensitive paths (PO 2026-08-09) · the human-review
#          protocol · `human_owned.txt`'s own header, "who watches the watchers"
#          · PO ruling 2026-08-30 "FIX THE CAUSE, NOT THE FIFTH INSTANCE"
#          (OQ-441 CLOSED)
# Impacts: 10-scripts/gates/human_owned.txt · G7 ·
#          12-governance/09-human-review-ledger.md
# ───────────────────────────────────────────────────────
"""THE REVERSE QUESTION G7 NEVER ASKS.

`G7` walks the guard list and checks each file it names. That is the forward
question — *are the guarded files behaving?* — and it is sound. **It cannot see
a file that is missing from the list**, because the list is where it starts.

So every escape of the last three weeks looks like this, in the words of
`human_owned.txt`'s own line for `read_analysis.py`:

    the file already carried HUMAN-REVIEW-PENDING and a ledger row and no glob
    here matched it — THAT IS THE THIRD TIME THIS EXACT ESCAPE HAS HAPPENED TO A
    MONEY PATH ... Three occurrences, one cause: this list is maintained by hand
    and a new money file joins the CODE without joining the LIST.

This gate asks the other way round: **a file that invokes the 🔒 human-review
protocol in its own module docstring must be matched by a glob in
`human_owned.txt`.** A file saying that of itself is the author's own statement
that the protocol applies to it; nothing else in the repo reads that statement.

WHAT "INVOKES THE PROTOCOL" MEANS — WIDENED 2026-08-31 (DEF-2790)
----------------------------------------------------------------
⚠ **THIS GATE USED TO KEY ON `HUMAN-OWNED` ALONE, AND THAT IS NOT THE CONDITION
THE PO RULED.** The ruling of 2026-08-30 (`OQ-441` CLOSED, decision log *"FIX THE
CAUSE, NOT THE FIFTH INSTANCE"*) says, verbatim:

    build a check that a file carrying `HUMAN-REVIEW-PENDING` and a
    review-ledger row is matched by some glob in `10-scripts/gates/human_owned.txt`

**`HUMAN-OWNED` and `HUMAN-REVIEW-PENDING` are different sets**, and the
difference was not academic: of the five files the ruling NAMED BY NAME,
`apps/billing/gather.py` (2,282 lines, the one impure read pass a bill run makes)
and `apps/billing/metering_seam.py` carry `HUMAN-REVIEW-PENDING` in their
docstrings and **no `HUMAN-OWNED` at all**, so the gate produced in answer to the
ruling could not see either of them. Widening to EITHER marker took the finding
set from **57 files to 62** — five the narrow marker was hiding, all five with a
review-ledger row already open.

THE LEDGER ROW IS A SECOND FINDING, NEVER A FILTER
--------------------------------------------------
⚠ **The ruling's condition is `HUMAN-REVIEW-PENDING` AND a ledger row. Applied as
an `AND` it would have SHRUNK this gate, not widened it** — 15 of the 57 files it
already reported declare the marker and have **no ledger row at all**, among them
`core/money.py` (the rounding constants), `apps/payments/idempotency.py` (the
hard-rule-6 inbound key) and `apps/payments/webhooks.py`. Filtering them out
would mean a file could leave this gate's sight **by opening no review row**,
which is a strictly easier escape than the one the ruling was closing. A guard
you defeat by doing LESS is not a guard.

So the ledger row is reported as a SECOND CLASS of finding, side by side:

  * **asked** — marker + a review-ledger row. The author enrolled the file and
    opened the row; only the glob is missing. This is the ruling's literal
    condition, and every file in it is caught.
  * **not even asked** — marker, no row. The author said the protocol applies
    and the standing record of that never opened. Worse, not better.

Both are unguarded. Both are named. Neither is silently dropped.

WHAT IT DOES NOT DO — and this is deliberate
--------------------------------------------
**It does not add anything to the list, and it must never be made to.** Adding a
file is a PROCESS EVENT and is the Product Owner's call, not a lane's — that rule
is what stops the guarded set drifting with whoever happens to be coding, and two
lanes on 2026-08-28 correctly declined to add themselves and filed instead. This
gate only makes the discrepancy VISIBLE, and counts it. `OQ-441`'s ruling says
the same thing in its own words: *"THE CHECK MUST FAIL AND NAME THE FILE — NEVER
SILENTLY APPEND."*

THE BASELINE IS A NAMED SET, NOT A NUMBER
-----------------------------------------
Measured at the tip on the day this landed: **50 files, ~38,000 lines**, and they
include exactly the categories CLAUDE.md's 🔒 line names — `core/money.py`
(*"rounding constants are HUMAN-OWNED"*), `payments/idempotency.py` (*"key
mechanics Eng-Lead 🔒"*), `payments/webhooks.py`, and eleven files under
`apps/ledger`. Re-measured after the 2026-08-31 widening: **62 files, 60,508
lines**.

A named set rather than a count, for `G52`'s reason: a count lets one file leave
the set while another joins and reports green over the swap. And not a hard zero,
because a gate that is red from birth earns a `# noqa` instead of a fix (`G44`'s
own words) — the sixty-two are the PO's to rule on, in their own time, and this
gate's job is that the sixty-third cannot arrive unnoticed.

WHY THE SELF-TEST BUILDS ITS OWN FILES
--------------------------------------
Every clause below is proved against **synthetic text written inside this
module**, not against a file in the repo. A self-test that sabotages real repo
content reports "SELF-TEST FAILED" whenever that content is already broken —
which is the loudest possible way to say nothing at all. The one clause that
does use a repo file (`A1`) asserts its precondition first and reports the
precondition, not a blind pass, when it no longer holds.
"""

from __future__ import annotations

import ast
from pathlib import Path

import common

GUARD_FILE = Path(__file__).with_name("human_owned.txt")
BASELINE_FILE = Path(__file__).with_name("g53_unguarded_baseline.txt")
LEDGER_FILE = common.REPO_ROOT / "12-governance" / "09-human-review-ledger.md"

#: Either marker is the author's own statement that the 🔒 protocol applies.
#: `HUMAN-OWNED` was the only one this gate read until 2026-08-31 (DEF-2790).
MARKERS = ("HUMAN-OWNED", "HUMAN-REVIEW-PENDING")

SEARCH_ROOTS = ("06-backend/**/*.py",)
SKIP = ("__pycache__", "/tests/", "/migrations/")
MAX_NAMED = 6


def guard_globs(text: str) -> list[str]:
    """The first token of every non-comment line — the same parse G7 uses."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.split(" ", 1)[0])
    return out


def guarded_files(globs: list[str]) -> set[str]:
    """Resolved with `Path.glob`, matching G7 — `fnmatch` mishandles `**`."""
    found: set[str] = set()
    for pattern in globs:
        for path in common.REPO_ROOT.glob(pattern):
            if path.is_file():
                found.add(common.rel(path))
    return found


def markers_in_source(source: str) -> tuple[str, ...]:
    """Which protocol markers the MODULE DOCSTRING declares, in `MARKERS` order.

    The module docstring only, which is where the protocol puts them. A mention
    in a comment about some other file is not a declaration about this one.

    Takes SOURCE TEXT rather than a path so the self-test can prove every clause
    on strings it wrote itself — see the module docstring's last section.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return ()
    doc = ast.get_docstring(tree) or ""
    return tuple(m for m in MARKERS if m in doc)


def declares_marker(path: Path) -> bool:
    """True when this file invokes the 🔒 protocol in its own module docstring."""
    return bool(markers_in_source(common.read_text(path)))


def ledger_text() -> str:
    return common.read_text(LEDGER_FILE) if LEDGER_FILE.is_file() else ""


def has_ledger_row(rel: str, ledger: str) -> bool:
    """A row in the human-review ledger naming this repo-relative path.

    The same substring test `G7` uses, deliberately — two gates disagreeing about
    what counts as a row would be worse than either answer.
    """
    return rel in ledger


def unguarded(guarded: set[str], ledger: str | None = None) -> list[str]:
    """Every unguarded file declaring a marker, sorted. The finding set."""
    return sorted(rel for rel, _markers, _row in scan(guarded, ledger))


def scan(guarded: set[str], ledger: str | None = None) -> list[tuple[str, tuple[str, ...], bool]]:
    """`(path, markers it declares, does the review ledger name it)` per finding."""
    if ledger is None:
        ledger = ledger_text()
    out: list[tuple[str, tuple[str, ...], bool]] = []
    for pattern in SEARCH_ROOTS:
        for path in common.REPO_ROOT.glob(pattern):
            rel = common.rel(path)
            if any(skip in f"/{rel}" for skip in SKIP):
                continue
            if rel in guarded:
                continue
            markers = markers_in_source(common.read_text(path))
            if markers:
                out.append((rel, markers, has_ledger_row(rel, ledger)))
    return sorted(out)


def baseline_names(text: str) -> set[str]:
    """The named set, parsed from baseline TEXT — comments and blanks dropped.

    Split out from `baseline()` on 2026-08-31 for the reason in the module
    docstring: the self-test proves this on a string it wrote itself. The clause
    that used to stand here asserted only that the real baseline file was
    NON-EMPTY, which is not a property of the parser at all — and it misfired
    the moment the gate was exercised against a repo with nothing parked, where
    it reported `self-test BLIND` over whatever the run was actually about.
    """
    return {
        line.strip()
        for line in text.split("\n")
        if line.strip() and not line.strip().startswith("#")
    }


def baseline() -> set[str]:
    if not BASELINE_FILE.is_file():
        return set()
    return baseline_names(common.read_text(BASELINE_FILE))


#: Synthetic modules the self-test classifies. Each is a complete Python source
#: string, so nothing here depends on the state of any real file.
_HEALTHY = '"""A file. HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒."""\n\nX = 1\n'
_PENDING_ONLY = '"""A file. 🔒 HUMAN-REVIEW-PENDING — money path."""\n\nX = 1\n'
_OWNED_ONLY = '"""A file. Rounding constants are HUMAN-OWNED."""\n\nX = 1\n'
_UNMARKED = '"""An ordinary file with no protocol markers at all."""\n\nX = 1\n'
_COMMENT_ONLY = '"""An ordinary file."""\n\n# see foo.py, which is HUMAN-OWNED\nX = 1\n'
_BROKEN = '"""HUMAN-OWNED"""\n\ndef (  # not python\n'


def self_test(guarded: set[str]) -> list[tuple[str, bool, str]]:
    """Law 7 — every clause shown to bite before the gate is trusted green.

    ⚠ WIDENED 2026-08-31 (DEF-2790). The old B-clauses did not exist, so the day
    this gate began keying on `HUMAN-OWNED` alone there was nothing to notice it.
    `B1` is the clause that would have: it asserts, in one line, that a docstring
    saying only `HUMAN-REVIEW-PENDING` counts.
    """
    results: list[tuple[str, bool, str]] = []

    # ── B: the classifier, proved on text this function wrote ──────────────
    results.append(("B1", markers_in_source(_PENDING_ONLY) == ("HUMAN-REVIEW-PENDING",),
                    "a docstring carrying ONLY HUMAN-REVIEW-PENDING is a declaration"
                    if markers_in_source(_PENDING_ONLY)
                    else "HUMAN-REVIEW-PENDING alone was NOT read as a declaration — this is "
                         "exactly the gap DEF-2790 recorded (expected FAIL)"))

    results.append(("B2", markers_in_source(_OWNED_ONLY) == ("HUMAN-OWNED",),
                    "a docstring carrying ONLY HUMAN-OWNED is still a declaration"
                    if markers_in_source(_OWNED_ONLY)
                    else "widening dropped the original marker (expected FAIL)"))

    results.append(("B3", markers_in_source(_HEALTHY) == MARKERS,
                    "a docstring carrying both markers reports both"
                    if len(markers_in_source(_HEALTHY)) == 2
                    else "a file declaring both markers was mis-read (expected FAIL)"))

    results.append(("B4", markers_in_source(_UNMARKED) == (),
                    "an unmarked file is not a finding"
                    if not markers_in_source(_UNMARKED)
                    else "an UNMARKED file was reported — this gate would name every "
                         "file in the backend (expected FAIL)"))

    results.append(("B5", markers_in_source(_COMMENT_ONLY) == (),
                    "a marker in a COMMENT about another file is not a declaration"
                    if not markers_in_source(_COMMENT_ONLY)
                    else "a comment mentioning another file was read as this file's "
                         "own declaration (expected FAIL)"))

    results.append(("B6", markers_in_source(_BROKEN) == (),
                    "an unparseable file is skipped rather than crashing the gate"
                    if not markers_in_source(_BROKEN)
                    else "unparseable source did not fall through cleanly (expected FAIL)"))

    fake_ledger = "| `06-backend/apps/demo/asked.py` (NEW 🔒) | ... |"
    asked = has_ledger_row("06-backend/apps/demo/asked.py", fake_ledger)
    not_asked = has_ledger_row("06-backend/apps/demo/silent.py", fake_ledger)
    results.append(("B7", asked and not not_asked,
                    "the ledger-row test separates a file that was asked about from one that was not"
                    if asked and not not_asked
                    else ("a path NAMED in the ledger read as no row" if not asked
                          else "a path ABSENT from the ledger read as having one (expected FAIL)")))

    # ── A: the search and the baseline, against the repo ───────────────────
    probe = "06-backend/apps/rating/engine.py"
    probe_path = common.REPO_ROOT / probe
    # Precondition FIRST: a probe that is no longer guarded, or no longer
    # marked, makes clause A1 vacuous — say which, never report a blind pass.
    if not probe_path.is_file():
        results.append(("A1", False, f"probe {probe} no longer exists — pick another guarded, "
                                     "marked file (expected FAIL)"))
    elif probe not in guarded:
        results.append(("A1", False, f"probe {probe} is no longer matched by any glob in "
                                     "human_owned.txt, so withholding it proves nothing "
                                     "(expected FAIL)"))
    elif not declares_marker(probe_path):
        results.append(("A1", False, f"probe {probe} no longer declares a protocol marker, so "
                                     "withholding it proves nothing (expected FAIL)"))
    else:
        thinned = {f for f in guarded if f != probe}
        surfaced = probe in unguarded(thinned)
        results.append(("A1", surfaced,
                        f"withholding {probe} from the guarded set -> "
                        + ("reported unguarded" if surfaced
                           else "NOT reported — the gate cannot see a missing glob "
                                "(expected FAIL)")))

    synthetic_baseline = (
        "# a comment naming 06-backend/apps/should/not/count.py\n"
        "\n"
        "06-backend/apps/demo/parked.py\n"
        "   06-backend/apps/demo/indented.py   \n"
    )
    parsed = baseline_names(synthetic_baseline)
    expected = {"06-backend/apps/demo/parked.py", "06-backend/apps/demo/indented.py"}
    results.append(("A2", parsed == expected,
                    "the named set drops comments and blanks and keeps names"
                    if parsed == expected
                    else f"baseline parse returned {sorted(parsed)}, expected "
                         f"{sorted(expected)} — a comment read as a name would PARK A FILE "
                         "NOBODY LISTED (expected FAIL)"))

    results.append(("A2b", BASELINE_FILE.is_file(),
                    f"the named set lives at {BASELINE_FILE.name}"
                    if BASELINE_FILE.is_file()
                    else "the baseline file is MISSING, so every finding would read as new "
                         "and the gate would be red from birth (expected FAIL)"))

    known = baseline()
    fabricated = sorted(known | {"06-backend/apps/g53_probe_not_a_file.py"})
    caught = [f for f in fabricated if f not in known]
    results.append(("A3", caught == ["06-backend/apps/g53_probe_not_a_file.py"],
                    "a name absent from the baseline is reported as new"
                    if caught else "a new name was swallowed by the baseline (expected FAIL)"))
    return results


def run() -> tuple[str, str]:
    if not GUARD_FILE.is_file():
        return "FAIL", "human_owned.txt is missing — the 🔒 guard list must exist"
    if not LEDGER_FILE.is_file():
        return "FAIL", ("12-governance/09-human-review-ledger.md is missing — the human-review "
                        "protocol's standing record is half of what this gate reads")

    globs = guard_globs(common.read_text(GUARD_FILE))
    guarded = guarded_files(globs)

    blind = [(tag, detail) for tag, ok, detail in self_test(guarded) if not ok]
    if blind:
        return "FAIL", (f"self-test BLIND: {blind[0][0]} {blind[0][1]}. A guard that cannot be "
                        "shown to fail is not a guard (law 7).")

    ledger = ledger_text()
    findings = scan(guarded, ledger)
    found = [rel for rel, _m, _r in findings]
    asked = [rel for rel, _m, row in findings if row]
    not_asked = [rel for rel, _m, row in findings if not row]

    known = baseline()
    new = [f for f in found if f not in known]
    healed = sorted(known - set(found))

    if new:
        new_asked = [f for f in new if f in asked]
        new_silent = [f for f in new if f in not_asked]
        parts = []
        if new_asked:
            parts.append(f"{len(new_asked)} with a review-ledger row already open "
                         f"({common.summarize(new_asked, MAX_NAMED)})")
        if new_silent:
            parts.append(f"{len(new_silent)} with NO ledger row at all "
                         f"({common.summarize(new_silent, MAX_NAMED)})")
        return "FAIL", (
            f"{len(new)} file(s) invoke the 🔒 human-review protocol in their own docstring "
            f"({' or '.join(MARKERS)}) and no glob in human_owned.txt matches them: "
            + "; ".join(parts) + ". "
            "Adding a file to that list is a PROCESS EVENT and the PO's call, not a lane's — "
            "file it and say so, never add yourself."
        )
    if healed:
        return "FAIL", (
            f"{len(healed)} baselined file(s) are now guarded — delete them from "
            f"g53_unguarded_baseline.txt in the same diff: {common.summarize(healed, MAX_NAMED)}"
        )
    clauses = len(self_test(guarded))
    return "PASS", (
        f"{len(globs)} glob(s) guard {len(guarded)} file(s); {len(found)} file(s) invoke the "
        f"🔒 protocol and are unguarded ({len(asked)} with a review-ledger row, "
        f"{len(not_asked)} with none), every one of them named in "
        f"g53_unguarded_baseline.txt and none new; self-test: {clauses}/{clauses} clauses bite"
    )


def main() -> int:
    status, message = run()
    print(f"G53 guard-list-coverage {status}  {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
