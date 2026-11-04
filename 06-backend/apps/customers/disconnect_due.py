# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-030 (S90 · DSC-02) — the disconnect register and its cases.
#           Screens: S90 (the register, Accounts blueprint p140)
# Change:   PO 2026-09-20, verbatim: *"Something has to read cut dates daily and
#           surface what's due… A case due last week stops looking identical to
#           one due next month. The clerk stops being the scheduler."*
#           Screen half: a DUE NOW view on the register. Job half:
#           `apps/customers/disconnect_schedule.py`.
# Rules:    BR-CUS-039 (the tiers; nothing is cut before tier 3 with proof) ·
#           BR-TEN-043 (the event date is an ARGUMENT, never a wall clock) ·
#           CLAUDE.md hard rule 1 (tenant scoping — every queryset here filters
#           `tenant_id` and runs under RLS FORCE) · `NFR-3` (nothing here builds
#           a list to count it; the counts are `COUNT(*)` and the filter is a
#           `WHERE`, so the register still pages in SQL)
# Defects:  DEF-CUS-6055 — *"the register's DUE TO CUT tile counts cases that
#           are already cut"*, whose own remedy is the reason this module
#           exists: **one predicate, read by the tile, by the list and by the
#           job**, so none of the three can drift from the other two.
# Tests:    06-backend/tests/test_w7_worklists.py :: test_dsc_every_kpi_tile_equals_the_rows_of_its_own_segment (EXTENDED, not a second check) · 10-scripts/po20260921_cut_date_watch_walkthrough.mjs
# Impacts:  apps/customers/disconnect_reads.py (the `due` filter, the row's
#           `cut_due` fact and the `dues` vocabulary) ·
#           apps/customers/disconnect_schedule.py (the daily watch) ·
#           07-frontend/src/features/customers/disconnect/list/CutDateCell.tsx
# ───────────────────────────────────────────────────────
"""WHEN a scheduled cut is due — and whether it has already happened.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE GAP THIS CLOSES, IN THE PO'S OWN WORDS.                            ║
║  *"A case due last week stops looking identical to one due next month."* ║
╚══════════════════════════════════════════════════════════════════════════╝
Until today the register had exactly one opinion about a cut date: whether it
fell inside the next seven days (`disconnect_reads._within_the_week`). That
function is honest and its own docstring says what it costs:

    "⚠ **A SCHEDULED CUT WHOSE DATE HAS PASSED IS IN NEITHER** — it is not
     accented and it is not counted — which is what the caption says and is
     not obviously what a clerk wants."

So a cut booked for last Monday rendered in the same plain text as one booked
for next month, sat in no tile, and was found only by somebody remembering it.

────────────────────────────────────────────────────────────────────────────
⚠ NOTHING IN THIS MODULE ACTS. IT ANSWERS A QUESTION ABOUT A DATE.
────────────────────────────────────────────────────────────────────────────
**No function here cuts a supply, advances a tier, writes a notice or moves a
case out of its state.** Turning a date into an automatic disconnection is not
what was approved — the PO asked for the due work to be SURFACED, not executed
— and this product has never taken a supply off anybody without a person
pressing a button. Whether an unattended job may ever perform a cut is a
question (`OQ-CUS-12525`), not something a lane infers from a schedule existing.

────────────────────────────────────────────────────────────────────────────
⚠ WHY *ALREADY CUT* IS PART OF THE PREDICATE AND NOT A CALLER'S PROBLEM
────────────────────────────────────────────────────────────────────────────
`DEF-CUS-6055`'s general shape, in the register's own words:

    "a date that records WHEN something happened keeps matching a window that
     was meant to mean WHEN IT WILL."

`cut_scheduled_for` is NOT cleared by a cut — correctly, it is the record of
when the supply was booked to go off — so a case that was cut on Sunday goes on
satisfying *"the date has arrived"* for ever. The tile that counted a pure date
window said **2** over two households whose supply was already off, while the
list beside it showed none.

The fix is not a second exclusion bolted onto each reader. It is that
`due_status()` takes the case's STATE as well as its date and answers
`already_cut` — so every caller gets the exclusion by construction, and the
tile, the filter and the job are three readings of ONE function.

────────────────────────────────────────────────────────────────────────────
⚠ WHAT THIS SKIPS, COUNTED RATHER THAN IMPLIED (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
A check that cannot cover its whole subject must print what it skipped beside
what it checked, *"because a declared blind spot with no NUMBER attached is
indistinguishable from an empty one."* `due_register()` therefore returns a
`skipped` block with a count for each reason a case was not considered:

  * `no_cut_date`   — nothing has been scheduled, so nothing can be due.
  * `already_cut`   — the supply is off; the date is history (`DEF-CUS-6055`).
  * `reconnecting`  — the customer has paid and a visit is owed; that is the
                      RECONNECTIONS tile's work and not a cut waiting to happen.
  * `left_the_list` — `stopped`, `restored` and `closed_out` never reach here;
                      `open_cases()` excludes the first two and `DEF-CUS-5777`
                      is the open row on the third.

⚠ **`closed_out` IS THE SKIP THIS MODULE CANNOT COUNT, AND IT SAYS SO RATHER
THAN PRETENDING TO.** `disconnect_reads.LIST_EXCLUDED_CASE_STATES` excludes TWO
states where `disconnects.CLOSED_CASE_STATES` holds THREE — a divergence filed
as `DEF-CUS-5777` and deliberately not fixed here, because changing which rows
the register holds is that defect's job and not this one's. A closed-out case
with a past cut date therefore reaches `due_status()` and is answered on its
date. The number is in `skipped["left_the_list"]` as **unknown**, with the
defect id beside it, so a reader can tell an untested zero from a measured one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.customers import disconnects

# ════════════════════════════════════════════════════════════════════════════
# THE FIVE ANSWERS
# ════════════════════════════════════════════════════════════════════════════
#: The date has passed and the supply is still on. This is the one the product
#: could not say before today.
DUE_OVERDUE = "overdue"
#: The date is today. `BR-TEN-043` — *today* is the tenant's business day, taken
#: from the caller's `as_of` and never from a wall clock in this file.
DUE_TODAY = "due_today"
#: The date is in the future. A row a clerk does not have to think about yet.
DUE_AHEAD = "ahead"
#: There is a case and nobody has booked a date on it.
DUE_NONE = "no_date"
#: The supply is already off, or a reconnection visit is owed. The date on the
#: row is HISTORY (`DEF-CUS-6055`) and this module refuses to read it as a plan.
DUE_DONE = "done"

DUE_STATUSES: tuple[str, ...] = (DUE_OVERDUE, DUE_TODAY, DUE_AHEAD, DUE_NONE, DUE_DONE)

#: The two statuses that mean *a person has to look at this today*. Named ONCE
#: because the filter, the counts and the daily watch all ask the same question,
#: and three literal copies of one set is how a tile and its list come to
#: disagree (`DEF-CUS-6055`, exactly).
DUE_NOW_STATUSES: tuple[str, ...] = (DUE_OVERDUE, DUE_TODAY)

# ════════════════════════════════════════════════════════════════════════════
# THE FILTER VOCABULARY — `f.due` on `GET /disconnects`
# ════════════════════════════════════════════════════════════════════════════
#: ⛔ **THIS IS A FILTER AND NOT `?segment=`, AND THE DIFFERENCE IS WHY IT IS
#: BUILDABLE.** `disconnect_reads` §3 refuses every segment but `all` because
#: B18 §5.8.2's six segments are not mutually exclusive and no rule ranks them
#: (`OQ-374`). A FILTER asks *does this row answer X* and needs no ranking, no
#: exclusivity and no precedence: a case that is overdue AND at notice AND held
#: answers all three and is hidden by none of them. Nothing here decides any
#: part of the open question, and `?segment=` still refuses everything but
#: `all`.
FILTER_DUE_NOW = "due_now"
FILTER_OVERDUE = "overdue"
DUE_FILTER_VALUES: tuple[str, ...] = (FILTER_DUE_NOW, FILTER_OVERDUE)

#: What each filter value matches, as statuses. One mapping, so the SQL branch
#: and the Python answer cannot part company.
DUE_FILTER_STATUSES: dict[str, tuple[str, ...]] = {
    FILTER_DUE_NOW: DUE_NOW_STATUSES,
    FILTER_OVERDUE: (DUE_OVERDUE,),
}

#: The clerk's word for each view. THREE WORDS OR FEWER — a chip is a LABEL and
#: B14 rule 33 caps a label at three words with no sentence. The screen may
#: translate these; it never invents one, because `BR-SHL-010` makes the served
#: vocabulary the only vocabulary.
DUE_FILTER_LABELS: dict[str, str] = {
    FILTER_DUE_NOW: "Due now",
    FILTER_OVERDUE: "Overdue",
}

#: ⛔ A parked wizard draft has raised no case, so it has no date and can answer
#: no `due` question. `parks_queryset` returns NONE for this filter rather than
#: everything, which is `BR-SHL-011`'s posture and the same rule `f.state`
#: already follows across the two row sources.
PARKED_DISCONNECT_HAS_NO_CUT_DATE: dict[str, Any] = {
    "code": "parked_disconnect_has_no_cut_date",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nobody has booked a cut on this one. A parked draft holds what was typed and "
        "creates nothing — no case, no notice, no cut date — so it can be neither due "
        "nor overdue until somebody picks it back up and runs it."
    ),
}

#: ⚠ **THE ONE SKIP THIS MODULE CANNOT PUT A NUMBER ON.** See the module
#: docstring. Carried on every register result so a reader never has to INFER an
#: absence — the posture `disconnects.NO_SCHEDULER` and
#: `ladder.LADDER_UNAVAILABLE` already take.
CLOSED_OUT_COUNT_UNKNOWN: dict[str, Any] = {
    "code": "closed_out_cases_not_separable",
    "br_ref": "DEF-CUS-5777",
    "detail": (
        "This register counts the cases the disconnects list holds, and that list excludes "
        "two finished states where the module declares three — `closed_out` is missing from "
        "the exclusion and has been since August. So a closed-out case with a cut date in "
        "the past is counted here as overdue. How many there are is not measured, because "
        "changing which rows the list holds belongs to DEF-CUS-5777 and not to this module."
    ),
}


# ════════════════════════════════════════════════════════════════════════════
# THE PREDICATE — one function, three readers
# ════════════════════════════════════════════════════════════════════════════
def due_status(*, cut_scheduled_for: date | None, state: Any, as_of: date) -> str:
    """Which of the five answers this case has, on `as_of`.

    ⚠ **THE STATE IS AN ARGUMENT AND IT IS NOT OPTIONAL.** A pure date test is
    `DEF-CUS-6055` — *"a date that records WHEN something happened keeps
    matching a window that was meant to mean WHEN IT WILL"* — and it is the
    whole reason this function takes two facts rather than one.

    ⚠ **`as_of` IS THE TENANT'S BUSINESS DAY, PASSED IN.** `BR-TEN-043`: the
    moment is named by the caller. Nothing in this module reads a clock, so the
    tile, the row, the filter and the nightly watch can all be asked about the
    SAME day and cannot answer it differently.
    """
    if str(state) in (disconnects.STATE_CUT, disconnects.STATE_RECONNECTING):
        return DUE_DONE
    if cut_scheduled_for is None:
        return DUE_NONE
    if cut_scheduled_for < as_of:
        return DUE_OVERDUE
    if cut_scheduled_for == as_of:
        return DUE_TODAY
    return DUE_AHEAD


def days_overdue(*, cut_scheduled_for: date | None, state: Any, as_of: date) -> int | None:
    """How many days late, or `None` when the case is not overdue.

    A whole number of calendar days, NOT business days. `cut_date.py` counts the
    statutory notice period in business days because a regulator's clock works
    that way; *how late are we* is a plain elapsed-time question a clerk asks
    out loud, and answering it in business days would print `4` over a date nine
    days ago.
    """
    if due_status(cut_scheduled_for=cut_scheduled_for, state=state, as_of=as_of) != DUE_OVERDUE:
        return None
    assert cut_scheduled_for is not None  # narrowed by the status above
    return (as_of - cut_scheduled_for).days


def due_fact(*, case: Any, as_of: date) -> dict[str, Any]:
    """The `cut_due` block a register ROW carries.

    Three fields and no prose:
      * `status` — one of `DUE_STATUSES`; the screen maps it to a word.
      * `days_overdue` — a whole number, or `None`.
      * `as_of` — the day it was decided against, so a cached page cannot claim
        a freshness it does not have.

    ⚠ **NO SENTENCE IS SERVED HERE.** B14 rule 33 caps what reaches a screen by
    what the text is FOR, and the screen is where that budget is spent — a
    server-side sentence would arrive pre-spent and untranslatable. The
    `unavailable` blocks elsewhere in this surface are ABSENCES, which is a
    different thing and is why they carry prose and this does not.
    """
    if case is None:
        return {"status": DUE_NONE, "days_overdue": None, "as_of": as_of.isoformat()}
    scheduled = getattr(case, "cut_scheduled_for", None)
    state = getattr(case, "state", None)
    return {
        "status": due_status(cut_scheduled_for=scheduled, state=state, as_of=as_of),
        "days_overdue": days_overdue(cut_scheduled_for=scheduled, state=state, as_of=as_of),
        "as_of": as_of.isoformat(),
    }


# ════════════════════════════════════════════════════════════════════════════
# THE ROW SET — expressed as SQL, so `NFR-3` survives
# ════════════════════════════════════════════════════════════════════════════
def due_cases(*, as_of: date, want: str = FILTER_DUE_NOW):
    """The open cases answering `want`, as a LAZY queryset.

    ⚠ **A `WHERE`, NEVER A PYTHON FILTER — `NFR-3` IS THE DELIVERABLE.** The
    register pages in SQL since `DEF-CUS-5755`, and a `due` filter that built
    every case to test a date would hand that back: correct at a utility of
    3,000 accounts and thirteen times short of T5's 40,000. Both halves of
    `due_status` are stored columns, so both are expressible — the date as a
    comparison and the state as an exclusion — and nothing is returned to Python
    to decide.

    ⚠ **THE EXCLUSION IS THE SAME TWO STATES `due_status` ANSWERS `done` FOR**,
    written once here and once there because one is SQL and one is Python. The
    test asserts they agree over every case in the fixture; two expressions of
    one rule is exactly how a list and a detail come to disagree, and the only
    defence is a check that compares them.
    """
    from apps.customers import disconnect_reads

    rows = disconnect_reads.open_cases().exclude(
        state__in=(disconnects.STATE_CUT, disconnects.STATE_RECONNECTING)
    )
    statuses = DUE_FILTER_STATUSES.get(want, DUE_NOW_STATUSES)
    if DUE_OVERDUE in statuses and DUE_TODAY in statuses:
        return rows.filter(cut_scheduled_for__lte=as_of)
    if DUE_OVERDUE in statuses:
        return rows.filter(cut_scheduled_for__lt=as_of)
    if DUE_TODAY in statuses:  # pragma: no cover - no filter value asks for this alone
        return rows.filter(cut_scheduled_for=as_of)
    return rows.none()  # pragma: no cover - `want` is validated by the caller


def due_account_ids(*, as_of: date, want: str = FILTER_DUE_NOW):
    """The same set as ACCOUNT IDS, for the register's `WHERE account_id IN (…)`.

    A subquery and not a list: `_open_case_account_ids` takes the identical
    posture one module over, and for the identical reason — *"it can be asked of
    the database as a `WHERE account_id IN (SELECT …)` and never returns a row
    to Python."*
    """
    return due_cases(as_of=as_of, want=want).values("account_id")


# ════════════════════════════════════════════════════════════════════════════
# THE REGISTER — what the screen counts and what the watch reports
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DueCase:
    """One case the watch found. The CASE NUMBER, never a database id (B14 rule
    31) — this travels into a log line and a report a person reads."""

    case_no: str
    account_no: str
    status: str
    cut_scheduled_for: str
    days_overdue: int | None


def due_register(*, as_of: date) -> dict[str, Any]:
    """Everything a reader needs about cut dates on ONE day, in ONE pass.

    Returns `{"as_of", "overdue", "due_today", "due_now", "cases", "skipped",
    "unavailable"}`.

    ⚠ **THE COUNTS AND THE LIST COME FROM THE SAME PASS, WHICH IS
    `DEF-CUS-6055`'s REMEDY APPLIED RATHER THAN RESTATED.** That defect's own
    prevention reads: *"A tile that is a door into a list must be counted by the
    SAME predicate as the list, and the cheap general check is to assert tile ==
    len(rows of its segment)."* Here they are not two predicates that happen to
    agree — `len(cases_that_are_overdue)` IS `overdue`, by construction, and a
    test asserts the register's counts against the list route's `total` for the
    same filter so the two SURFACES cannot drift either.

    ⚠ **IT READS EVERY OPEN CASE IN THE TENANT, ONCE, DELIBERATELY.** The same
    posture `kpi_strip` records and for the same reason: a count over a whole
    set is what a KPI IS. The set is open disconnect cases — tens on a utility
    of 40,000 accounts, not tens of thousands — and `due_cases` above is the
    `WHERE` clause the PAGED list uses, so the register's own list never pays
    this.
    """
    from apps.customers import disconnect_reads, models

    cases = list(disconnect_reads.open_cases())
    skipped = {"no_cut_date": 0, "already_cut": 0, "reconnecting": 0}
    due: list[tuple[Any, str]] = []
    for case in cases:
        state = str(getattr(case, "state", ""))
        status = due_status(
            cut_scheduled_for=case.cut_scheduled_for, state=state, as_of=as_of
        )
        if status == DUE_DONE:
            key = "reconnecting" if state == disconnects.STATE_RECONNECTING else "already_cut"
            skipped[key] += 1
            continue
        if status == DUE_NONE:
            skipped["no_cut_date"] += 1
            continue
        if status in DUE_NOW_STATUSES:
            due.append((case, status))
    # The ACCOUNT NUMBER a clerk would read out, in ONE query for the whole
    # finding — never one per case. `B14` rule 31: the number, never the id.
    numbers = {
        str(row["id"]): str(row["account_no"] or "")
        for row in models.Account.objects.filter(
            tenant_id=disconnects._tenant_id(),
            id__in=[case.account_id for case, _status in due],
        ).values("id", "account_no")
    }
    found = [
        DueCase(
            case_no=str(case.case_no or ""),
            account_no=numbers.get(str(case.account_id), ""),
            status=status,
            cut_scheduled_for=case.cut_scheduled_for.isoformat(),
            days_overdue=days_overdue(
                cut_scheduled_for=case.cut_scheduled_for,
                state=str(getattr(case, "state", "")),
                as_of=as_of,
            ),
        )
        for case, status in due
    ]
    overdue = [row for row in found if row.status == DUE_OVERDUE]
    today = [row for row in found if row.status == DUE_TODAY]
    return {
        "as_of": as_of.isoformat(),
        "overdue": len(overdue),
        "due_today": len(today),
        "due_now": len(found),
        # Oldest first: the one that has waited longest is the one a clerk
        # should see at the top of a log line they will read at eight in the
        # morning.
        "cases": [
            {
                "case_no": row.case_no,
                "account_no": row.account_no,
                "status": row.status,
                "cut_scheduled_for": row.cut_scheduled_for,
                "days_overdue": row.days_overdue,
            }
            for row in sorted(found, key=lambda row: row.cut_scheduled_for)
        ],
        # hard-won law 7 — what was skipped, WITH A NUMBER, beside what was
        # checked. `considered` is the denominator, so a reader can tell a
        # sweep that found nothing from a sweep that looked at nothing.
        "considered": len(cases),
        "skipped": dict(skipped),
        "unavailable": [dict(CLOSED_OUT_COUNT_UNKNOWN)],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-20 (*"Something has to read cut dates daily and
#         surface what's due"*) · Accounts blueprint p140 (the register, as an
#         image) · DEF-CUS-6055 (the tile and its list counted differently) ·
#         disconnect_reads.py §3/§4/§5 · B14 rules 31, 33, 43 · NFR-3
# generated: 2026-09-20 by lane DBLD-3 (the cut-date watcher)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) **NOTHING HERE ACTS.** No function cuts a supply, advances a
#         tier, writes a notice or moves a case out of its state. Whether an
#         unattended job may ever perform a cut is OQ-CUS-12525, OPEN, and is not
#         a thing this lane may infer from a schedule existing.
#         (2) **`closed_out` IS COUNTED AS OVERDUE AND THE NUMBER IS NOT
#         MEASURED** — `CLOSED_OUT_COUNT_UNKNOWN`, tracking DEF-CUS-5777. The
#         absence is served rather than guessed at.
#         (3) **`days_overdue` IS CALENDAR DAYS, NOT BUSINESS DAYS**, and
#         deliberately unlike `cut_date.business_days_after`. Stated because the
#         neighbouring module counts the other way for a good reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
