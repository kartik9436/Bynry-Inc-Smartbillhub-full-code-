# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.27 (as-was where history exists; before
#           `P0.18`'s table was recording it falls back to as-is AND SAYS SO) ·
#           P2.19 (state the basis on screen — a FACT in six words, never
#           rationale).  Screens: 2·1 head.
# Rules:    brief §7.2.4 p85-p86, read as images per B14 rule 42 — RULED,
#           option (b) · B14 rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words
#           on screen) · CLAUDE.md hard rule 4's closing clause (`audit_log` is
#           NOT a permanent record of an old value, ever)
# Tests:    06-backend/tests/test_rep_p2_27_basis.py
# Impacts:  apps/customers/attribute_history.py (`as_was`) ·
#           apps/reports/runner.py · 07-frontend 2·1 head
# ───────────────────────────────────────────────────────
"""WHICH QUESTION THIS REPORT ANSWERED — THEN, OR NOW.

§7.2.4, RULED — option (b)
──────────────────────────
*"An account moves from Residential to Commercial in September. You run Revenue
by class for July. **As-is** puts July's revenue under Commercial; **as-was**
puts it under Residential. For regulatory and financial reporting as-was is
almost always right."*

⚠ **AND THE PART THAT IS NOT REVERSIBLE, WHICH IS WHY THIS MODULE EXISTS AT
ALL.** p86: *"(b) starts recording on the day it ships. **It recovers
nothing.**"* Every class change before that date is gone — overwritten in
place, with its only trace in `audit_log`, which is pruned on a schedule the PO
ruled has **no exemptions**. So a report covering any period before the table
started recording cannot answer as-was for those rows, and **no amount of
engineering will make it able to.**

WHAT A REPORT DOES ABOUT THAT, AND WHY IT IS NOT TIDIER TO HIDE IT
──────────────────────────────────────────────────────────────────
p86, verbatim: *"Where history exists it answers **as-was**, because that is
what a regulator is asking for. Where it does not — anything before the table
ships — it falls back to **as-is and says so on the face of the report**. ⚠ One
report will state **both bases** for the first year, and that is correct rather
than untidy: the alternative is a single confident basis line that is true of
half the rows."*

So `MIXED` is a first-class answer here and not an error state. A report
covering June to August 2026, with the table recording from July, is as-was for
August and as-is for June — and the honest line says both, with the COUNT of
rows it could not date. A count rather than an adjective, because *"some rows"*
is not something a regulator can act on and *"412 of 1,904 rows"* is.

⚠ **THE SENTENCE ON SCREEN IS A FACT AND IS SIX WORDS (B14 rule 33).**
*"Based on today's customer details"* is p84's own drawn wording and is five.
What must NEVER appear on screen is WHY — not the retention schedule, not the
table's ship date, not a word about `audit_log`. That is RATIONALE, rule 33
puts it at **zero words**, and CLAUDE.md hard rule 4 adds that no screen may
describe that path as a permanent record of an old value. A screen explaining
the retention policy would break rule 33 while trying to obey hard rule 4.
Everything a reader could want to know about the mechanism is in this
docstring, which is what a docstring is for.

⚠ **`P2.19` SHIPS WHICHEVER WAY THE RULING GOES, AND IT ALREADY WENT.** The
basis line is not conditional on as-was being built: p13 says *"a report that
silently answers a different question from the one asked is worse than one that
refuses"*, so an as-is-only product states **as-is**, plainly, and nobody
mistakes it for as-was. That is the case this module serves today for every
row predating the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

#: What it was at the time. What a regulator is asking for.
AS_WAS = "as_was"
#: Today's details, applied to an older period. The silent default before this.
AS_IS = "as_is"
#: Some rows each way. p86: *"correct rather than untidy."*
MIXED = "mixed"

BASES: tuple[str, ...] = (AS_WAS, AS_IS, MIXED)

#: ⚠ **FACTS, CAPPED AT SIX WORDS (B14 rule 33), AND NOT ONE WORD OF WHY.**
#: The eleven catalogues carry these under `reports.basis.<code>`; this map is
#: what the fan-in was built from and what a test counts the words of.
SENTENCES: dict[str, str] = {
    AS_IS: "Based on today's customer details",
    AS_WAS: "Based on details at the time",
    MIXED: "Two bases — see undated rows",
}


@dataclass(frozen=True)
class ReportBasis:
    """Which question this report answered, and over how many rows.

    `undated` is the count of rows that could only be answered as-is because
    the history table was not recording when they happened. It is a NUMBER and
    never a flag: p86 asks the report to say *which* rows it could not date,
    and a boolean cannot.
    """

    code: str
    dated: int = 0
    undated: int = 0

    @property
    def sentence(self) -> str:
        return SENTENCES[self.code]

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "sentence": self.sentence,
            "dated": self.dated,
            "undated": self.undated,
        }


def classify(dated: int, undated: int) -> ReportBasis:
    """The basis for a report with these two counts.

    ⚠ **ZERO ROWS IS `AS_IS`, DELIBERATELY.** An empty report has answered
    nobody's question either way, and claiming as-was over no rows is a claim
    the product cannot support. The weaker statement is the true one.
    """
    dated = max(0, int(dated))
    undated = max(0, int(undated))
    if dated and undated:
        return ReportBasis(MIXED, dated=dated, undated=undated)
    if dated and not undated:
        return ReportBasis(AS_WAS, dated=dated, undated=0)
    return ReportBasis(AS_IS, dated=0, undated=undated)


def account_class_on(account_id: Any, *, on: date) -> tuple[Any, bool]:
    """This account's class on `on`, and whether it could be DATED.

    Returns `(value, dated)`. `dated` is False when the history table was not
    recording then — which is every row before `P0.18` shipped and is not
    recoverable, ever. The caller falls back to today's value and COUNTS the
    row, which is what makes the basis line true rather than confident.

    ⚠ **IT RETURNS `None` FOR THE VALUE WHEN UNDATED RATHER THAN GUESSING.**
    The caller already has today's value in the row it is holding; inventing a
    second read of it here would be a second path to the same number and the
    two would eventually disagree.
    """
    try:
        from apps.customers import attribute_history
    except Exception:  # pragma: no cover — customers not installed in a probe
        return None, False
    row = attribute_history.as_was(account_id, on=on)
    if row is None:
        return None, False
    return getattr(row, "account_type_id", None), True


def over(account_ids: Iterable[Any], *, on: date) -> ReportBasis:
    """The basis for a whole report, counted row by row.

    ⚠ **COUNTED AND NOT SAMPLED.** A report that checked the first row and
    declared the whole thing as-was would be right most of the time and wrong
    exactly when it matters — the month the table started recording, which is
    the month somebody is most likely to be checking.
    """
    dated = undated = 0
    for account_id in account_ids:
        _, ok = account_class_on(account_id, on=on)
        if ok:
            dated += 1
        else:
            undated += 1
    return classify(dated, undated)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.27 · P2.19 (05-prototype/09 Reports Build Brief.pdf p13, p84, p85, p86 read as images per B14 rule 42)
# screens: 2·1 head
# generated: 2026-09-27 by lane REP-P2-MODEL
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p2_27_basis.py was shown red before this file existed, and again with `classify` stubbed to return AS_WAS unconditionally
# exceptions: (1) ZERO rows classifies as AS_IS, deliberately — the weaker statement is the true one · (2) `account_class_on` returns None for an undated row rather than re-reading today's value, so there is one path to that number and not two · (3) NOTHING here reaches a screen as an explanation (B14 rule 33 · hard rule 4's closing clause)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
