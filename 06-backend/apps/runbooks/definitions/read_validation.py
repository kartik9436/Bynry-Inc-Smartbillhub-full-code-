# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-033 (EP-RBS-05) — CR-075 wave R′: runbook 21, *Read
#           validation on arrival* — six steps over a landed interval batch,
#           four read and two write.
# Rules:    BR-RBS-002 (a Check is constructed with no writer — this is an
#           Action and holds one named port) · BR-RBS-003 (dry and live are ONE
#           code path) · BR-RBS-004 (an Action always produces a PLAN first) ·
#           BR-RBS-009 (scope resolved ONCE and pinned) · BR-RBS-010 (every
#           record states the rule that decided it, in words a clerk can read) ·
#           BR-RBS-011 (a failure names its fix route) · BR-RBS-012 (a guard is
#           absolute and runs before any step) · BR-RBS-019 (the declared unit
#           of work is the METER-DAY, never the interval) · BR-RBS-020 (the
#           report is composed at close and frozen) · BR-RBS-021 (twelve
#           blocks) · BR-RBS-022 (a write is a named port; a work item is the
#           ENGINE's) · BR-RBS-023 (a step declares its mode) · BR-RBS-027 (a
#           stopped run reads *Never reached* on every later step) ·
#           BR-RBS-035 / RB-042 (a volume runbook keeps a row for what it acted
#           on and a COUNT for the rest) · BR-RBS-039 (every foreign read
#           through a seam this module owns) · BR-MET-020 (a service with no
#           figure has its threshold rules SKIPPED AND REPORTED) · RBR-18
#           (read validation walks the meter-day; billing never asks about an
#           interval) · RBR-03 (policy lives in Settings, never on a card) ·
#           US-MET-010 (the person who commits a reading is the person who
#           certifies it) · CLAUDE.md hard rule 3 (a consumption ALWAYS carries
#           an explicit unit) · hard rule 8 (an address lives on premises) ·
#           hard-won law 2 · law 7 · law 14 · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_033_read_validation.py ·
#           06-backend/tests/test_rbs_reads_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/metering_seam.py ·
#           apps/metering/selectors.py (interval_batch · meter_normals ·
#           read_validation_overview) ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-121-read-validation-on-arrival.md
# ───────────────────────────────────────────────────────
"""Runbook 21 — **Read exceptions** (the card calls it *Read validation on
arrival*; `RB-121` says the screen name is what the library and every wireframe
draw, so that is this definition's `name`).

An interval batch lands overnight. This rolls it up to the meter-day, runs the
utility's own validation figures over it, estimates the short gaps by policy,
queues the long ones for a person, and says how many meter-days billing can
rely on.

THE ONE NUMBER THIS RUNBOOK IS ABOUT
--------------------------------------
**176,640 intervals become 1,840 records.** That is `BR-RBS-019` and `RBR-18`
in one sentence, and it is a rule rather than a preference: *"a per-interval
savepoint over 176,640 rows would be the bottleneck"*. The rollup happens on
the OWNING side of the seam (`apps.metering.selectors.interval_batch`), so
1,840 rows cross rather than 176,640 and this file never sees an interval at
all.

⚠ **AND THE ROLLUP CARRIES ITS UNIT, WHICH IS THE RULE MOST LIKELY TO BITE
HERE** (CLAUDE.md hard rule 3). Adding up 96 numbers and reporting the total
without saying what it measures produces a figure nobody can check and nobody
can bill. Every meter-day crosses with `unit`; a meter-day whose own intervals
DISAGREE about their unit carries `unit_conflict`, has **no** total at all, and
is queued for a person rather than summed into nonsense.

WHO STARTS IT, AND WHY THAT IS NOT THE EVENT THE CARD NAMES
------------------------------------------------------------
`RB-121`'s trigger row reads ⚡ `batch.landed` — *"The trigger is its arrival,
not a clock."* **A person or a schedule starts this runbook.**
`batch.landed` is emitted by nothing — zero occurrences anywhere in the backend,
verified again 2026-09-07 — and it is `CR-069`'s work, currently scoped to
nobody. `models.py` already rules that *"a runbook whose only trigger is an
unbuilt event is not runnable, and a screen must SAY so rather than offering a
Run ▶ that refuses"*, so this declares **manual and schedule**, both of which
wait on nothing, and the event joins them the day it exists. That is the same
disposition wave Q′ recorded for runbooks 20 and 22; it is repeated rather than
cross-referenced because a lane reading only this file needs it.

"NOTHING HAS LANDED" IS AN ANSWER, AND IT IS STEP 1
----------------------------------------------------
PO ruling 2026-09-06, verbatim: *"we should complete our runbooks, if we need to
do a check of integration and APIs, we should do it, in absence of API
conenctions you will not find anything and you can stop the job saying APi or
conenct not available; that is a valid case and state for us"*. Step 1 asks
where tonight's intervals come from and the run **STOPS** when the answer is
nowhere: one red chain cell naming what is missing and five honestly reading
*Never reached* (`BR-RBS-027`), no KPI strip over a run that examined nothing,
and the word *failed* nowhere.

⚠ **TWO DOORS, WHICH IS WAVE `P`'s LESSON APPLIED RATHER THAN REDISCOVERED.**
A clerk whose head-end file is already staged does not need to be told the AMI
link is not wired up. So the doors are **a live meter connection** (`meters_mdm`
or `meters_neptune360`) and **an interval batch already in the product** — a
`read_import_batches` row at `ami_replay`, staged or validated and NOT posted,
which is exactly what *a landed batch* means to a runbook that plans before it
acts. The run stops only when BOTH are shut.

WHAT IT PLANS AND WHAT IT ACTUALLY WRITES TODAY
------------------------------------------------
**Nothing is written, and the reason is not that a wave has not got to it.**
`write_read` **binds no writer at all**, and its own port declaration says why:
metering's event-read door certifies the reading as the acting HUMAN
(`US-MET-010`: *"the acting user committing the wizard IS the person certifying
the entry"*), and **an automation may not sign a meter reading.** That is
`DEF-RBS-4331`, and it is a rule rather than a gap in the schedule.

⚠ **THE PORT IS CALLED ANYWAY AND ITS OWN REFUSAL IS RECORDED AS THE OUTCOME.**
There is no `if is_bound` branch: `BR-RBS-003` makes dry and live ONE code path
differing only in whether the writer is bound, and a branch would be a second
path proving nothing about the first. So the KPI tile reads **To validate**
rather than *Validated* — a tile saying **1,802 Validated** over a run that
wrote nothing is the most dangerous sentence this screen could print.

FIVE PLACES THIS DIVERGES FROM `RB-121`, EACH STAMPED
-------------------------------------------------------
1. **The KPI strip says *To validate* / *To estimate* while nothing is
   written**, where the card's words are *Validated* and *Estimated*. The
   card's words return the day a writer is bound — which, for this port,
   needs a ruling about who certifies an automated reading and not a wave.
2. **The card's own two figures do not agree about the interval size.** Step 1
   says *"96 intervals become one meter-day"* — which is 15-minute data — and
   the *stated absences* section says *"interval reads arrive hourly"* and that
   fifteen-minute reads would *"quadruple every figure on this card"*. Both
   cannot be true of one batch. **This runbook assumes NEITHER**: it counts the
   intervals it was actually given, reports the count per meter-day, and reads a
   gap from the SPACING of the timestamps rather than from an assumed cadence.
   Reported rather than resolved — the card is the acceptance check and only its
   author can say which figure is right.
3. **`Most estimates per run` is not a parameter, it is the CAP.** The card
   gives 200 as a parameter; the cap is a column on the runbook row
   (`runbooks.cap`) and duplicating it would be two copies of one policy, which
   is `RBR-03` exactly. Step 4 READS it, and — per `BR-RBS-006` — a run over the
   cap **REFUSES**; it never truncates.
4. **Step 6's work items are COUNTED, not raised.** `raise_work_item` is an
   ENGINE act and its upsert is `CR-075` task `H1`, which is phase 4. Until it
   lands the queued rows are readable on this run's own result screen and are
   not yet gathered into `RBS-007` — not lost, only ungathered.
5. **The chain is drawn only when the run STOPPED.** The frame draws a run that
   finished; a stopped run is a state it does not cover, and the chain is the
   only block that can say *this step never ran*.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
Hard-won law 7's second habit — and three of the four answers are numbers on
the screen rather than sentences in this docstring.

* **A run that examined nothing and a run that found nothing wrong must not
  read the same.** Every step returns a `checked` mapping; the KPI strip carries
  the interval count and the meter-day count beside the outcome counts, so
  *1,840 meter-days, 0 exceptions* and *0 meter-days* are different screens.
* **A meter with no history is not a meter with a normal of zero.**
  `meter_normals` answers `None` and this runbook cannot estimate from it —
  those meter-days are QUEUED, and `estimates_impossible_no_history` carries
  the number.
* **A service with no validation figures is not a service that passed.**
  `BR-MET-020`: threshold rules are SKIPPED AND REPORTED, and
  `services_with_no_limits` names them on the screen. A check reporting zero
  over a scope it silently excludes is `G32`'s shape — 0 unresolved, truthfully,
  over 21 live refusals.
* **A row the importer could not read is not a meter-day.**
  `intervals_unreadable` travels from the seam, so 176,640 in and 1,840 out
  reconcile with a third number rather than by subtraction nobody can perform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import integrations_seam, metering_seam

KEY = "read_validation"

# ── the door work arrives through ─────────────────────────────────────────
#
# The meter manifests, verified against `06-backend/apps/integrations/manifests/`
# and named as VALUES rather than imported: a manifest key crossing the seam is
# data, and importing `apps.integrations.manifests` is exactly what `G115`
# refuses (`BR-RBS-039`).
# ⚠ `meters_mdm` — the one card that read *Itron / Sensus* — BECAME TWO in
# `CR-110-BRC04`, and Badger BEACON joined them as connector 07. All three
# are head-ends of the same shape (`BR-INT-037`), so all three belong here.
METER_PROVIDER_KEYS = (
    "meters_neptune360",
    "meters_badger",
    "meters_itron",
    "meters_sensus",
)

# ── what one meter-day can turn out to be ─────────────────────────────────
#
# ⚠ **`planned` IS NOT `skipped`, AND NEITHER IS `queued`.** A planned read is
# one this run WOULD write; a queued one is one a person has to decide; a
# skipped one is one nothing is going to do. `BR-RBS-035` counts every outcome
# including the ones with no record row, so a word collapsing two of them would
# make the totals unreadable.
OUTCOME_WRITTEN = "written"
OUTCOME_PLANNED = "planned"
OUTCOME_ESTIMATED = "estimated"
OUTCOME_QUEUED = "queued"
OUTCOME_SKIPPED = "skipped"

# ── why a meter-day is queued for a person ────────────────────────────────

ISSUE_SILENT = "silent"
ISSUE_GAP_TOO_LONG = "gap_too_long"
ISSUE_ROLLOVER = "rollover"
ISSUE_HIGH = "high"
ISSUE_LOW = "low"
ISSUE_UNIT_CONFLICT = "unit_conflict"
ISSUE_NO_UNIT = "no_unit"
ISSUE_NO_HISTORY = "no_history"
ISSUE_OVER_THE_CAP = "over_the_cap"

#: What a clerk calls each one. ⚠ **NO RULE ID AND NO DATABASE ID REACHES A
#: SCREEN** (B14 rules 31 and 32); the rule travels in `ReportRow.meta`, which
#: no block draws.
ISSUE_LABELS = {
    ISSUE_SILENT: "Silent meter",
    ISSUE_GAP_TOO_LONG: "Gap too long to estimate",
    ISSUE_ROLLOVER: "Rollover",
    ISSUE_HIGH: "Above the high limit",
    ISSUE_LOW: "Below the low limit",
    ISSUE_UNIT_CONFLICT: "Two units in one day",
    ISSUE_NO_UNIT: "No unit on the meter",
    ISSUE_NO_HISTORY: "No history to estimate from",
    ISSUE_OVER_THE_CAP: "Over the estimate limit",
}

# ── the steps, in the card's own order ────────────────────────────────────

STEP_GATHER = "gather_the_batch_and_roll_it_up"
STEP_LIMITS = "check_high_low_and_rollover"
STEP_GAPS = "find_the_gaps"
STEP_ESTIMATE = "estimate_the_short_gaps_by_policy"
STEP_WRITE = "write_validated_meter_days_as_reads"
STEP_RAISE = "raise_exceptions_as_work_items"

STEP_LABELS = {
    STEP_GATHER: "Gather the batch and roll it up",
    STEP_LIMITS: "Check high, low and rollover",
    STEP_GAPS: "Find the gaps",
    STEP_ESTIMATE: "Estimate the short gaps by policy",
    STEP_WRITE: "Write validated meter-days as reads",
    STEP_RAISE: "Raise exceptions as work items",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-07.** A fix route resolving to nothing is
# a dead button over a live finding — hard-won law 2's mirror, the shape that
# left the customer portal with two working doors out of eight — and nothing in
# the backend suite can see it, because a string is a string. Tenant-relative:
# the shell prefixes `/:tenant/`.
FIX_READS = "reads"
FIX_ASSETS = "assets"
FIX_SETTINGS = "settings/read-validation"


def _decimal(raw: Any) -> Decimal | None:
    """A stored quantity as a `Decimal`, or `None` where there is none.

    ⚠ **NEVER A FLOAT** (CLAUDE.md hard rule 2's sibling for quantities). The
    seam hands quantities across as canonical strings for exactly this reason,
    and `float("1140.3")` is where a utility's totals stop tying out.
    """
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):  # pragma: no cover — the seam quantizes
        return None


@dataclass(frozen=True)
class MeterDay:
    """One meter, one day, and what this run decided about it.

    ⚠ **`quantity` AND `unit` TRAVEL TOGETHER OR NOT AT ALL** (hard rule 3). A
    `quantity` with `unit = None` is refused at construction, because a number
    with no unit is the exact thing this runbook exists not to hand billing.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `asset_id` is the handle the port needs; `meter_no` is the number painted on
    the box, which is what a clerk and a field crew can act on.
    """

    asset_id: str
    meter_no: str
    channel: str
    day: str
    intervals: int
    quantity: Decimal | None
    unit: str | None
    outcome: str
    issue: str | None
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str
    last_good_day: str | None = None
    estimated_from: str | None = None
    service: str | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a meter-day with no reason says nothing to anybody")
        if self.quantity is not None and not self.unit:
            raise ValueError(
                f"meter {self.meter_no!r} on {self.day} carries a quantity and no unit. "
                "CLAUDE.md hard rule 3: a consumption always carries an EXPLICIT unit and "
                "one is never assumed — a rolled-up total that dropped its unit is a number "
                "nobody can check."
            )
        if not self.fix_route.strip():
            raise ValueError(
                f"meter {self.meter_no!r} names no fix route. BR-RBS-011: a failure names its "
                "fix route, and a failure with no route is a defect in the runbook — a clerk "
                "reads what is wrong and has nowhere to go."
            )

    @property
    def quantity_text(self) -> str:
        """The day's total AS A CLERK READS IT — the number and its unit.

        Never the bare number. `1,140` on a screen beside `860` invites a
        comparison that is only meaningful when both are gallons, and this is
        the one place that can promise they are.
        """
        if self.quantity is None:
            return "—"
        return f"{self.quantity.normalize():f} {self.unit}"

    def as_row(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "meter_no": self.meter_no,
            "channel": self.channel,
            "day": self.day,
            "intervals": self.intervals,
            "quantity": None if self.quantity is None else str(self.quantity),
            "unit": self.unit,
            "quantity_text": self.quantity_text,
            "outcome": self.outcome,
            "issue": self.issue,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
            "last_good_day": self.last_good_day,
            "estimated_from": self.estimated_from,
            "service": self.service,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration. A step reporting nothing over an empty batch
    and a step reporting nothing over a batch with no exceptions are the same
    sentence with very different meanings, and a check whose output cannot tell
    a reader which is which is worse than no check at all (hard-won law 7).

    `reached` is `False` on every step after a stop — what the chain draws as
    `notReached`, rather than a blank cell, which reads as *nothing wrong*.
    """

    reached: bool = True
    stop: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "reached": self.reached,
            "plan": list(self.plan),
            "checked": dict(self.checked),
        }
        if self.stop is not None:
            out["stop"] = dict(self.stop)
        return out


# ── reading the run's own context ─────────────────────────────────────────


def _batch(ctx) -> dict[str, Any] | None:
    """The interval batch this run is pinned to, already rolled up.

    A run that names no batch takes the most recently landed one, which is what
    a person starting the run by hand means by *last night's file*. A run that
    NAMES one takes that one or nothing — never a different file, because
    silently validating something else is how reads a clerk never looked at
    reach a bill.
    """
    return metering_seam.interval_batch(ctx.params.get("batch"))


def _subject_id(row: dict[str, Any]) -> str:
    """The pinned subject's id — meter, channel and day, which IS the unit of work.

    ⚠ **IT IS NOT A DATABASE ID AND IT IS NOT DRAWN ANYWHERE** (B14 rule 31).
    The Records table draws `meter_no` and `day` in their own columns; this is
    the engine's handle, and it is composed rather than random so a re-run over
    the same batch pins the same set.
    """
    return f"{row['meter_no']}|{row['channel']}|{row['day']}"


def _stopped(ctx) -> dict[str, Any] | None:
    """The stop an earlier step recorded, or `None`. Read by every step after it."""
    for key in (STEP_GATHER, STEP_ESTIMATE):
        result = ctx.set_results.get(key) or {}
        stop = result.get("stop")
        if stop:
            return dict(stop)
    return None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _plan(ctx) -> list[dict[str, Any]]:
    """The plan as the LAST step that touched it left it.

    Steps 2 to 4 each rewrite the whole plan rather than annotating rows in
    place, so the plan a later step reads is always one object with one author.
    Two steps editing one list is how a meter-day ends up carrying the issue
    from one rule and the outcome from another.
    """
    for key in (STEP_ESTIMATE, STEP_GAPS, STEP_LIMITS):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


def _cap(ctx) -> int | None:
    """The tenant's own limit, from the runbook row.

    ⚠ **IT IS A COLUMN AND NOT A PARAMETER** (`RBR-03`, and divergence 3). The
    card draws *Most estimates per run · 200* as a parameter; a parameter of
    that name would be a second copy of one policy, free to disagree with the
    one the Settings screen writes.
    """
    if ctx.run_id is None:
        return None
    return (
        models.RunbookRun.objects.filter(pk=ctx.run_id)
        .values_list("runbook__cap", flat=True)
        .first()
    )


def _as_of(ctx, batch: dict[str, Any] | None) -> date:
    """The day this run is FOR — the batch's own latest day, never a clock.

    `BR-TEN-043` and gate `G6`: a runbook does not read a wall clock, and a run
    re-run tomorrow over the same batch must reach the same answer or the pinned
    scope means nothing (`BR-RBS-009`).
    """
    stated = ctx.params.get("as_of")
    if isinstance(stated, datetime):
        return stated.date()
    if isinstance(stated, date):
        return stated
    if isinstance(stated, str) and stated:
        try:
            return date.fromisoformat(stated[:10])
        except ValueError:  # pragma: no cover — the parameter validator refuses it first
            pass
    days = sorted(one["day"] for one in ((batch or {}).get("meter_days") or []))
    return date.fromisoformat(days[-1]) if days else date(1970, 1, 1)


# ── step 1 · where tonight's intervals come from ──────────────────────────


def step_gather_the_batch_and_roll_it_up(ctx, subjects) -> dict[str, Any]:
    """1 · Two doors, and the run STOPS when both are shut.

    ⚠ **THE STOP IS A RESULT AND IT IS WRITTEN AS ONE.** `RUN_STATUS_STOPPED`
    already exists beside `done` and `failed`; nothing here raises and every
    later step reads *Never reached* (`BR-RBS-027`). The headline names BOTH
    absences, because *"no meter connection"* alone would send somebody to
    Settings for an afternoon when the file they need is already staged.

    ⚠ **THE THREE FIGURES THAT MAKE THE ROLLUP AUDITABLE ARE ALL IN `checked`.**
    intervals in · meter-days out · intervals the importer could not read. A
    reader can then do the subtraction themselves, which is the only way
    *176,640 → 1,840* is a claim rather than an assertion.
    """
    connections = integrations_seam.live_connections(METER_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    batch = _batch(ctx)
    rows = (batch or {}).get("meter_days") or []

    checked: dict[str, Any] = {
        "meter_connections_looked_for": len(METER_PROVIDER_KEYS),
        "meter_connections_found": len(connections),
        "meter_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "batch_landed": batch is not None,
        "file_name": (batch or {}).get("file_name"),
        "batch_status": (batch or {}).get("status"),
        "intervals_in_the_batch": (batch or {}).get("intervals", 0),
        "intervals_unreadable": (batch or {}).get("intervals_unreadable", 0),
        "meter_days_out": len(rows),
        "meters_in_the_batch": (batch or {}).get("meters", 0),
        "sample_meter_days_guarded": len([one for one in rows if one.get("is_sample")]),
        "units_seen": sorted({str(one.get("unit")) for one in rows if one.get("unit")}),
        "meter_days_with_no_unit": len([one for one in rows if not one.get("unit")]),
        "meter_days_with_two_units": len([one for one in rows if one.get("unit_conflict")]),
    }

    if batch is None and ctx.params.get("batch"):
        # ⚠ **A FILE THAT WAS ASKED FOR AND IS NOT THERE IS ITS OWN SENTENCE.**
        # Telling a clerk *"nothing has landed"* when they chose a batch that
        # has since been POSTED would send them to do something already done —
        # and a posted batch is not a batch any more, its rows are reads.
        return _StepResult(
            stop={
                "headline": "That batch is not here.",
                "detail": (
                    "The interval batch this run was started with is not waiting to be "
                    "validated. It may already have been posted, or discarded. Choose the "
                    "batch to validate, or wait for the next one to land."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Choose a batch",
            },
            checked=checked,
        ).as_dict()

    if batch is None and not working:
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "A meter connection is set up and switched off."
            if offline
            else "No meter connection is set up."
        )
        return _StepResult(
            stop={
                "headline": "No intervals to validate.",
                "detail": (
                    f"{detail} No interval batch is waiting either, so there is nothing to "
                    "roll up. Connect the head-end, or upload an interval file."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Open reads",
            },
            checked=checked,
        ).as_dict()

    if batch is None:
        # A connection is live and nothing has landed. A different sentence and
        # a different stop — and on this deployment it is the honest one,
        # because nothing emits `batch.landed` and no adapter pulls a file.
        return _StepResult(
            stop={
                "headline": "Nothing has landed yet.",
                "detail": (
                    f"{', '.join(str(one) for one in checked['connection_names'])} is connected "
                    "and no intervals have arrived for this run. Start this again when a batch "
                    "lands, or upload an interval file."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Open reads",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(checked=checked).as_dict()


# ── step 2 · the importer's own validation figures ────────────────────────


def _limits_for(settings: dict[str, Any], service: str | None) -> dict[str, Any] | None:
    """This service's high/low figures, or `None` when the tenant has none.

    ⚠ **`None` IS *SKIPPED AND REPORTED*, NEVER *PASSED*** (`BR-MET-020`,
    `US-MET-011` TC-9). A service with no figure anywhere has its threshold
    rules skipped, and the runbook says so on the screen rather than validating
    against an invented limit — which would flag every reading or none of them,
    and both look exactly like a working check.
    """
    if not service:
        return None
    for entry in settings.get("services") or []:
        if entry.get("service") != service:
            continue
        if entry.get("source") == "none":
            return None
        return dict(entry)
    return None


def step_check_high_low_and_rollover(ctx, subjects) -> dict[str, Any]:
    """2 · The read importer's own validation stage, over the meter-day.

    ⚠ **THE LIMIT IS COMPARED IN ITS OWN UNIT OR IT IS NOT COMPARED AT ALL**
    (hard rule 3, `BR-MET-143`). `high_abs_value` carries `high_abs_unit`
    precisely so *50* cannot be compared with a reading in a different
    dimension; a meter-day whose unit does not match the limit's is REPORTED
    (`limit_unit_mismatch`) and not judged, because a silent comparison across
    two units is how a gas meter in CCF gets flagged against a limit in therms.

    ⚠ **A ROLLOVER IS A DROP THAT IS NOT A DROP.** A register that goes
    99,940 → 00,120 has not consumed a negative amount; it has run past its own
    digit count. A negative rolled-up day is therefore a rollover to CONFIRM
    rather than a low reading to estimate, and the two carry different fix
    routes because they have different fixes.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    settings = metering_seam.read_validation_limits()
    in_scope = {str(one.subject_id) for one in subjects}
    batch = _batch(ctx)
    rows = [one for one in ((batch or {}).get("meter_days") or []) if _subject_id(one) in in_scope]

    plan: list[dict[str, Any]] = []
    high = low = rollover = judged = 0
    unit_mismatch = 0
    no_limits: set[str] = set()
    for row in rows:
        limits = _limits_for(settings, row.get("service"))
        quantity = _decimal(row.get("quantity"))
        unit = row.get("unit")
        issue: str | None = None
        if row.get("unit_conflict"):
            issue = ISSUE_UNIT_CONFLICT
        elif not unit:
            issue = ISSUE_NO_UNIT
        elif quantity is not None and quantity < 0:
            issue = ISSUE_ROLLOVER
            rollover += 1
        elif limits is None:
            no_limits.add(str(row.get("service") or "—"))
        elif quantity is not None:
            ceiling = _decimal(limits.get("high_abs_value"))
            limit_unit = limits.get("high_abs_unit")
            if ceiling is not None and limit_unit and limit_unit != unit:
                # ⚠ A DECLARED BLIND SPOT WITH A NUMBER ATTACHED (law 7).
                unit_mismatch += 1
            elif ceiling is not None:
                judged += 1
                if quantity > ceiling:
                    issue = ISSUE_HIGH
                    high += 1
                elif quantity == 0:
                    issue = ISSUE_LOW
                    low += 1
            else:
                judged += 1
        plan.append({**row, "limit_issue": issue})

    return _StepResult(
        plan=plan,
        checked={
            "meter_days_examined": len(rows),
            "meter_days_judged_against_a_limit": judged,
            "above_the_high_limit": high,
            "at_or_below_the_low_limit": low,
            "rollovers_to_confirm": rollover,
            # ⚠ Both of these are the *reported blind spot* half. A zero here
            # means the check covered its whole subject; a number means it did
            # not, and the screen says which.
            "limit_unit_mismatch": unit_mismatch,
            "services_with_no_limits": sorted(no_limits),
        },
    ).as_dict()


# ── step 3 · the gaps ─────────────────────────────────────────────────────


def _expected_intervals(row: dict[str, Any]) -> int | None:
    """How many intervals this meter-day SHOULD hold, from its own spacing.

    ⚠ **THE CADENCE IS MEASURED, NEVER ASSUMED, AND THAT IS DIVERGENCE 2.**
    `RB-121` says *96 intervals* in one place (15-minute data) and *"interval
    reads arrive hourly"* in another. Assuming either would report a full day as
    75% missing or a quarter-day as complete. So the spacing is read off the
    timestamps this meter actually sent: the span from first to last, divided by
    the gaps between them.

    `None` when there is nothing to measure from — one reading has no spacing —
    and `None` is *unknown*, never *complete*.
    """
    first, last, count = row.get("first_at"), row.get("last_at"), int(row.get("intervals") or 0)
    if not first or not last or count < 2:
        return None
    span = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds()
    if span <= 0:
        return None
    spacing = span / (count - 1)
    if spacing <= 0:  # pragma: no cover — guarded by the span check above
        return None
    return max(int(round(86400 / spacing)), count)


def step_find_the_gaps(ctx, subjects) -> dict[str, Any]:
    """3 · Missing intervals inside a day, and meters silent all day — S-5.

    Two different facts and two different sentences. A meter that sent 68 of 96
    intervals has a gap somebody can estimate; a meter that sent nothing at all
    is either switched off, stolen, or under water, and *"silent 2 days"* is
    what a field crew is dispatched on.

    ⚠ **SILENCE IS MEASURED FROM THE LAST GOOD DAY, WHICH IS S-4** — the fact
    every exception row on this screen carries. A silent meter with no last good
    day at all has never reported, which is a different problem and says so.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    batch = _batch(ctx)
    as_of = _as_of(ctx, batch)
    normals = metering_seam.meter_normals(
        [one["asset_id"] for one in plan], as_of=as_of, days=int(ctx.params.get("baseline_days") or 90)
    )

    short = silent = complete = 0
    out: list[dict[str, Any]] = []
    for row in plan:
        expected = _expected_intervals(row)
        seen = int(row.get("intervals") or 0)
        normal = normals.get(row["asset_id"]) or {}
        missing = 0 if expected is None else max(expected - seen, 0)
        if seen == 0 or (row.get("nonzero_intervals") == 0 and row.get("zero_intervals") == 0):
            silent += 1
            gap_kind = ISSUE_SILENT
        elif missing:
            short += 1
            gap_kind = "short_gap"
        else:
            complete += 1
            gap_kind = None
        out.append(
            {
                **row,
                "expected_intervals": expected,
                "missing_intervals": missing,
                "gap_kind": gap_kind,
                "last_good_day": normal.get("last_good_day"),
                "normal_per_day": normal.get("average_per_day"),
                "normal_unit": normal.get("unit"),
                "days_silent": _days_silent(normal.get("last_good_day"), row["day"]),
            }
        )

    return _StepResult(
        plan=out,
        checked={
            "complete_meter_days": complete,
            "meter_days_with_a_short_gap": short,
            "silent_meters": silent,
            "cadence_unmeasurable": len([one for one in out if one["expected_intervals"] is None]),
            "meters_with_no_last_good_day": len(
                [one for one in out if one["last_good_day"] is None]
            ),
        },
    ).as_dict()


def _days_silent(last_good_day: str | None, day: str) -> int | None:
    """How long this meter has been quiet, or `None` when it never reported.

    `None` is not zero. A meter that has never sent a reading and a meter that
    sent one this morning are opposite facts, and both would print `0`.
    """
    if not last_good_day:
        return None
    return max((date.fromisoformat(day) - date.fromisoformat(last_good_day)).days, 0)


# ── step 4 · estimate the short gaps, and the cap ─────────────────────────


def step_estimate_the_short_gaps_by_policy(ctx, subjects) -> dict[str, Any]:
    """4 · Own 90-day average, up to the limit; longer gaps are QUEUED.

    ⚠ **THE ESTIMATE IS THE METER'S OWN NORMAL AND IT CARRIES ITS UNIT**
    (S-1, hard rule 3). A fleet average would estimate a bungalow's missing
    afternoon from a block of flats, and an estimate with no unit is a number
    that cannot be written as a read at all.

    ⚠ **A METER WITH NO HISTORY IS NOT A METER WITH A NORMAL OF ZERO.** Those
    meter-days are queued, and `estimates_impossible_no_history` carries the
    number — reporting zero would bill a gap as no consumption at all.

    ⚠ **THE CAP REFUSES THE RUN; IT NEVER TRUNCATES** (`BR-RBS-006`). A run that
    would estimate 240 meter-days against a limit of 200 STOPS and says both
    numbers. Estimating the first 200 and dropping the rest is the failure that
    looks like success: the screen would read *200 estimated* and 40 meter-days
    would silently never reach a bill.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    limit_days = int(ctx.params.get("estimate_gaps_up_to_days") or 3)
    out: list[dict[str, Any]] = []
    to_estimate = 0
    no_history = 0
    queued = 0
    validated = 0
    for row in plan:
        issue = row.get("limit_issue")
        gap_kind = row.get("gap_kind")
        days_silent = row.get("days_silent")
        normal = _decimal(row.get("normal_per_day"))
        normal_unit = row.get("normal_unit")

        if issue is not None:
            decision = (OUTCOME_QUEUED, issue)
            queued += 1
        elif gap_kind == ISSUE_SILENT and (days_silent is None or days_silent > limit_days):
            decision = (OUTCOME_QUEUED, ISSUE_SILENT if days_silent is not None else ISSUE_NO_HISTORY)
            queued += 1
        elif gap_kind is None:
            decision = (OUTCOME_PLANNED, None)
            validated += 1
        elif days_silent is not None and days_silent > limit_days:
            decision = (OUTCOME_QUEUED, ISSUE_GAP_TOO_LONG)
            queued += 1
        elif normal is None or not normal_unit:
            decision = (OUTCOME_QUEUED, ISSUE_NO_HISTORY)
            no_history += 1
            queued += 1
        else:
            decision = (OUTCOME_ESTIMATED, None)
            to_estimate += 1
        out.append({**row, "outcome": decision[0], "issue": decision[1]})

    cap = _cap(ctx)
    checked = {
        "meter_days_to_validate": validated,
        "meter_days_to_estimate": to_estimate,
        "meter_days_queued_for_a_person": queued,
        "estimates_impossible_no_history": no_history,
        "estimate_limit_days": limit_days,
        "cap": cap,
    }
    if cap is not None and to_estimate > int(cap):
        return _StepResult(
            plan=out,
            stop={
                "headline": "Too many estimates for one run.",
                "detail": (
                    f"This batch needs {to_estimate} estimates and the limit is {cap}. "
                    "Nothing has been estimated. Raise the limit, or work through the "
                    "queue first and run this again."
                ),
                "fix_route": FIX_SETTINGS,
                "fix_label": "Open read validation",
            },
            checked=checked,
        ).as_dict()
    return _StepResult(plan=out, checked=checked).as_dict()


# ── step 5 · the one write, one meter-day at a time ───────────────────────


def step_write_validated_meter_days_as_reads(ctx, subject) -> dict[str, Any]:
    """5 · Through the metering service · source AMI · estimates flagged.

    ⚠ **ONE METER-DAY, ONE SAVEPOINT** (hard-won law 14). The executor wraps
    every per-record step in a nested `transaction.atomic()`, so one refused
    meter-day rolls back to its own savepoint and the other 1,839 survive. On
    PostgreSQL that is the ONLY thing that works: without it the first
    `IntegrityError` aborts the whole transaction and every later record is lost
    at COMMIT however carefully the exception was caught — and the suite, which
    is in-memory SQLite, would stay green over all of it.

    ⚠ **THE PORT IS CALLED AND IT REFUSES BY NAME.** `write_read` binds no
    writer, and not because a wave has not reached it: metering's read door
    certifies the reading as the acting HUMAN (`US-MET-010`), and **an
    automation may not sign a meter reading** (`DEF-RBS-4331`). The refusal is
    recorded as the outcome — there is no `if is_bound` branch, because
    `BR-RBS-003` makes dry and live one code path and a branch would be a second
    path proving nothing about the first.
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A step that stops makes every later step Never reached",
            "fix_route": FIX_READS,
        }

    key = str(subject.subject_id)
    row = next((one for one in _plan(ctx) if _subject_id(one) == key), None)
    if row is None:
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "This meter-day was not in the plan.",
            "decided_by_rule": "The pinned set is resolved once and frozen",
            "fix_route": FIX_READS,
            "data": {},
        }

    day = _meter_day(row)
    if day.outcome == OUTCOME_QUEUED:
        return {
            "outcome": OUTCOME_QUEUED,
            "reason": day.reason,
            "decided_by_rule": day.decided_by_rule,
            "fix_route": day.fix_route,
            "data": day.as_row(),
        }

    try:
        ctx.port("write_read").call(
            actor=None,
            asset_id=day.asset_id,
            read_at=day.day,
            channel=day.channel,
            # ⚠ THE QUANTITY AND ITS UNIT GO THROUGH THE PORT TOGETHER, AS A
            # STRING (hard rules 2 and 3). A read written without its unit is a
            # guess wearing a number — the port's own declaration says so.
            quantity=None if day.quantity is None else str(day.quantity),
            unit=day.unit,
            source="ami",
            estimated=(day.outcome == OUTCOME_ESTIMATED),
        )
    except PortNotBound as refusal:
        # The refusal is raised before any SQL is issued, so hard-won law 14's
        # aborted-transaction trap is not in play here — and the savepoint above
        # covers the day a bound writer refuses for real.
        return {
            "outcome": OUTCOME_PLANNED if day.outcome != OUTCOME_ESTIMATED else OUTCOME_ESTIMATED,
            "reason": (
                f"{day.quantity_text} ready to write. Nothing is written yet."
                if day.outcome != OUTCOME_ESTIMATED
                else f"{day.quantity_text} ready to write, flagged as an estimate. "
                "Nothing is written yet."
            ),
            "decided_by_rule": str(refusal),
            "fix_route": FIX_READS,
            "data": day.as_row(),
        }
    written = ctx.set_results.setdefault("written", [])
    written.append(day.asset_id)
    return {
        "outcome": OUTCOME_WRITTEN,
        "reason": f"{day.quantity_text} written as a read.",
        "decided_by_rule": "A validated meter-day is handed to billing",
        "fix_route": FIX_READS,
        "data": day.as_row(),
    }


def _meter_day(row: dict[str, Any]) -> MeterDay:
    """One plan row as the object that refuses a quantity with no unit."""
    outcome = row.get("outcome") or OUTCOME_PLANNED
    issue = row.get("issue")
    quantity = _decimal(row.get("quantity"))
    unit = row.get("unit")
    normal = _decimal(row.get("normal_per_day"))
    if outcome == OUTCOME_ESTIMATED and normal is not None:
        # ⚠ THE ESTIMATE REPLACES THE PARTIAL DAY'S TOTAL AND CARRIES THE
        # NORMAL's OWN UNIT. Adding an estimate in one unit to a partial total
        # in another is the mistake this whole file is arranged to prevent.
        quantity, unit = normal, row.get("normal_unit")
    reason, rule, fix_route, fix_label = _sentence(row, issue, outcome)
    return MeterDay(
        asset_id=str(row["asset_id"]),
        meter_no=str(row.get("meter_no") or "—"),
        channel=str(row.get("channel") or ""),
        day=str(row["day"]),
        intervals=int(row.get("intervals") or 0),
        quantity=None if (issue in (ISSUE_UNIT_CONFLICT, ISSUE_NO_UNIT)) else quantity,
        unit=unit,
        outcome=outcome,
        issue=issue,
        reason=reason,
        decided_by_rule=rule,
        fix_route=fix_route,
        fix_label=fix_label,
        last_good_day=row.get("last_good_day"),
        estimated_from=(
            f"90-day average, {row.get('normal_unit')}" if outcome == OUTCOME_ESTIMATED else None
        ),
        service=row.get("service"),
    )


def _sentence(row: dict[str, Any], issue: str | None, outcome: str) -> tuple[str, str, str, str]:
    """What this meter-day says to a clerk, and the rule that decided it.

    ⚠ **THE SENTENCE NEVER CARRIES A RULE ID** (B14 rule 32) and the rule never
    reaches a screen: it rides in `ReportRow.meta`, which no block draws. And a
    REFUSAL caps at five or six words (B14 rule 33) — *"Silent 2 days"*,
    *"Gap too long"* — with the explanation in its own column.
    """
    days_silent = row.get("days_silent")
    missing = int(row.get("missing_intervals") or 0)
    if issue == ISSUE_SILENT:
        return (
            f"No intervals at all{'' if days_silent is None else f', silent {days_silent} days'}.",
            "A silent meter is a person's call, never an estimate",
            FIX_ASSETS,
            "Check meter →",
        )
    if issue == ISSUE_NO_HISTORY:
        return (
            "Nothing behind this meter to estimate from.",
            "No history is not a normal of zero",
            FIX_READS,
            "Estimate by hand →",
        )
    if issue == ISSUE_GAP_TOO_LONG:
        return (
            f"Gap of {days_silent} days is over the limit.",
            "Gaps longer than the Settings limit are queued, never estimated",
            FIX_READS,
            "Estimate by hand →",
        )
    if issue == ISSUE_ROLLOVER:
        return (
            "The register went backwards — confirm the rollover.",
            "A register past its digit count is a rollover, not a negative day",
            FIX_READS,
            "Confirm rollover →",
        )
    if issue == ISSUE_HIGH:
        return (
            "Above the utility's own high limit for this service.",
            "The high limit is the tenant's own Settings figure",
            FIX_READS,
            "Open read →",
        )
    if issue == ISSUE_LOW:
        return (
            "Nothing used all day, which the low rule flags.",
            "The low rule is the tenant's own Settings figure",
            FIX_READS,
            "Open read →",
        )
    if issue == ISSUE_UNIT_CONFLICT:
        return (
            "This day's readings are in two different units.",
            "A total across two units is not a quantity",
            FIX_ASSETS,
            "Open meter →",
        )
    if issue == ISSUE_NO_UNIT:
        return (
            "This meter states no unit, so nothing can be totalled.",
            "A consumption always carries an explicit unit",
            FIX_ASSETS,
            "Open meter →",
        )
    if outcome == OUTCOME_ESTIMATED:
        return (
            f"{missing} interval(s) missing, filled from this meter's own average.",
            "A short gap is estimated from the meter's own 90-day average",
            FIX_READS,
            "Open read →",
        )
    return (
        "Complete and inside the utility's own limits.",
        "A validated meter-day is handed to billing",
        FIX_READS,
        "Open read →",
    )


# ── step 6 · what a person is handed ──────────────────────────────────────


def step_raise_exceptions_as_work_items(ctx, subjects) -> dict[str, Any]:
    """6 · Each with the meter's last good day.

    ⚠ **A WORK ITEM IS AN ENGINE ACT AND NOT A PORT** (`BR-RBS-022`,
    `12-the-contract.md` §6). `raise_work_item` is refused BY NAME as a port
    precisely so a Check can populate the work list while holding no writer at
    all; the engine's upsert-by-fingerprint is `CR-075` task `H1`, which is
    **phase 4**. Until it lands the queued rows are readable on this run's own
    result screen and are not yet gathered into `RBS-007` with every other open
    item — the rows are not lost, only ungathered.

    So this step COUNTS what a person is being handed and reports it. It
    declares `writes=True` because the act it names is a write, exactly as the
    card marks it.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    queued = [one for one in plan if one.get("outcome") == OUTCOME_QUEUED]
    return _StepResult(
        plan=plan,
        checked={
            "queued_for_a_person": len(queued),
            "work_items_raised": 0,
            "work_list_state": (
                "The work list is built in a later wave; these are on this run's own screen."
            ),
            "every_exception_carries_its_last_good_day": all(
                one.get("last_good_day") is not None or one.get("issue") == ISSUE_NO_HISTORY
                for one in queued
            ),
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_RAISE, STEP_ESTIMATE, STEP_GAPS, STEP_LIMITS):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    """Six cells: the one that stopped the run, and the ones that never ran."""
    stopped_at = STEP_GATHER
    for key in (STEP_GATHER, STEP_ESTIMATE):
        if (view.set_results.get(key) or {}).get("stop"):
            stopped_at = key
            break
    cells = []
    seen_stop = False
    for index, key in enumerate(STEP_LABELS, start=1):
        if key == stopped_at:
            seen_stop = True
            state, note = "bad", stop["headline"]
        elif seen_stop:
            state, note = "notReached", "Never reached"
        else:
            state, note = "good", "Done"
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": state,
                "note": note,
            }
        )
    return Block(
        block="chain",
        payload={
            "label": f"The run stopped at step {[*STEP_LABELS].index(stopped_at) + 1}.",
            "cells": cells,
        },
    )


def _queued_columns() -> list[dict[str, Any]]:
    """`RB-121`'s own queued table: Meter · Account · Issue · Last good day · Fix.

    ⚠ **`Account` IS NOT A COLUMN HERE AND THE REASON IS STATED RATHER THAN
    LEFT AS AN OMISSION.** A meter-day's subject is the METER; the account is
    reached by walking meter → service point → unit → account, which is a read
    per row on a table of 1,840. The card's own account column is a
    convenience this runbook cannot pay for at its declared unit of work, and
    the fix route opens the meter, from which the account is one click. Reported
    as a divergence, not silently dropped.
    """
    return [
        {"key": "meter", "label": "Meter"},
        {"key": "day", "label": "Day"},
        {"key": "issue", "label": "Issue"},
        {"key": "last_good", "label": "Last good day"},
        {"key": "fix", "label": "Fix"},
    ]


def _queued_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    day = _meter_day(row)
    return {
        "id": f"queued-{index}",
        "cells": {
            "meter": {"kind": "text", "text": day.meter_no},
            "day": {"kind": "text", "text": day.day},
            "issue": {"kind": "text", "text": ISSUE_LABELS.get(day.issue or "", "—")},
            "last_good": {"kind": "text", "text": day.last_good_day or "Never reported"},
            "fix": {"kind": "link", "label": day.fix_label, "to": day.fix_route},
        },
        # ⚠ CARRIED, NEVER DRAWN — the renderer walks `columns`.
        # `decided_by_rule` MUST NOT reach a screen (B14 rule 32).
        "meta": {
            "decided_by_rule": day.decided_by_rule,
            "outcome": day.outcome,
            "reason": day.reason,
            "intervals": day.intervals,
        },
    }


def _estimate_columns() -> list[dict[str, Any]]:
    return [
        {"key": "meter", "label": "Meter"},
        {"key": "day", "label": "Day"},
        {"key": "gap", "label": "Gap"},
        {"key": "from", "label": "Estimated from"},
        {"key": "quantity", "label": "Quantity"},
    ]


def _estimate_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    day = _meter_day(row)
    missing = int(row.get("missing_intervals") or 0)
    return {
        "id": f"estimate-{index}",
        "cells": {
            "meter": {"kind": "text", "text": day.meter_no},
            "day": {"kind": "text", "text": day.day},
            "gap": {"kind": "text", "text": f"{missing} interval(s)"},
            "from": {"kind": "text", "text": day.estimated_from or "—"},
            # ⚠ THE NUMBER AND ITS UNIT, IN ONE CELL (hard rule 3). A column of
            # bare totals invites a comparison only this runbook can promise is
            # meaningful.
            "quantity": {"kind": "text", "text": day.quantity_text},
        },
        "meta": {"decided_by_rule": day.decided_by_rule, "outcome": day.outcome},
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states
    and one shape cannot say both:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). The
      chain draws *Never reached* on the steps that did not run, and the KPI
      strip is deliberately ABSENT: a strip reading *0 validated · 0 estimated ·
      0 queued* over a run that examined nothing is indistinguishable from a
      night on which every meter reported perfectly.
    * **finished** — `Verdict` · `KPIs` · `Breakdown` · `Records` · `Downloads`,
      which is `RB-121`'s own block list (KPIs · Records · Downloads) plus the
      verdict the header consumes and the by-issue breakdown its own queued
      table implies.

    Every name is one of the twelve (`BR-RBS-021`); no thirteenth is minted, and
    every payload carries the fields `contract.PAYLOAD_FIELDS` states — the gap
    `DEF-RBS-4352` fell through, where a report the backend accepted drew an
    error boundary instead of 835 notices.
    """
    stop = None
    for key in (STEP_GATHER, STEP_ESTIMATE):
        stop = (view.set_results.get(key) or {}).get("stop")
        if stop:
            break

    if stop:
        return [
            Block(
                block="verdict",
                payload={
                    "word": "Stopped",
                    "tone": "warning",
                    "count": stop["headline"],
                    "detail": stop["detail"],
                },
            ),
            Block(
                block="sentence",
                payload={"tone": "muted", "label": "What to do", "text": stop["detail"]},
            ),
            _chain(view, stop),
            Block(
                block="records",
                payload={
                    "columns": _queued_columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    plan = _plan_from_view(view)
    gathered = (view.set_results.get(STEP_GATHER) or {}).get("checked") or {}
    limits = (view.set_results.get(STEP_LIMITS) or {}).get("checked") or {}
    gaps = (view.set_results.get(STEP_GAPS) or {}).get("checked") or {}
    acted = any(record.outcome == OUTCOME_WRITTEN for record in view.records)

    queued = [one for one in plan if one.get("outcome") == OUTCOME_QUEUED]
    estimated = [one for one in plan if one.get("outcome") == OUTCOME_ESTIMATED]
    validated = [one for one in plan if one.get("outcome") == OUTCOME_PLANNED]
    handed = len(validated) + len(estimated)
    validated_word = "Validated" if acted else "To validate"
    estimated_word = "Estimated" if acted else "To estimate"

    by_issue: dict[str, int] = {}
    for one in queued:
        key = one.get("issue") or ISSUE_SILENT
        by_issue[key] = by_issue.get(key, 0) + 1

    return [
        Block(
            block="verdict",
            payload={
                "word": validated_word,
                "tone": "success" if not queued else "warning",
                "count": f"{len(validated)} {'validated' if acted else 'to validate'}. "
                f"{len(queued)} need you.",
                "detail": (
                    f"{gathered.get('intervals_in_the_batch', 0)} intervals → "
                    f"{gathered.get('meter_days_out', 0)} meter-days."
                    if acted
                    else "Nothing is written until a writer is bound for this runbook."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "validated",
                        "label": validated_word,
                        "value": {"kind": "text", "text": str(len(validated))},
                        "detail": None if acted else "Planned — nothing is written yet",
                    },
                    {
                        "id": "estimated",
                        "label": estimated_word,
                        "value": {"kind": "text", "text": str(len(estimated))},
                        "detail": "From each meter's own 90-day average",
                    },
                    {
                        "id": "queued",
                        "label": "Queued for you",
                        "value": {"kind": "text", "text": str(len(queued))},
                    },
                    {
                        "id": "silent",
                        "label": "Silent meters",
                        "value": {"kind": "text", "text": str(gaps.get("silent_meters", 0))},
                    },
                    {
                        "id": "handed",
                        "label": "Handed to billing",
                        "value": {"kind": "text", "text": str(handed)},
                        "detail": None if acted else "Once a writer is bound",
                    },
                    # ⚠ **THE ROLLUP IS A TILE, NOT A FOOTNOTE.** It is the one
                    # number this runbook exists to prove, and it is what tells
                    # a run that examined nothing from one that found nothing.
                    {
                        "id": "rollup",
                        "label": "Intervals rolled up",
                        "value": {
                            "kind": "text",
                            "text": (
                                f"{gathered.get('intervals_in_the_batch', 0)} → "
                                f"{gathered.get('meter_days_out', 0)}"
                            ),
                        },
                        "detail": (
                            f"{gathered.get('intervals_unreadable', 0)} could not be read"
                        ),
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "What is waiting for you",
                "columns": [
                    {"key": "issue", "label": "Issue"},
                    {"key": "count", "label": "Count", "numeric": True},
                    {"key": "happened", "label": "What happened"},
                ],
                "rows": [
                    {
                        "id": f"issue-{name}",
                        "cells": {
                            "issue": {"kind": "text", "text": ISSUE_LABELS[name]},
                            "count": {"kind": "text", "text": str(count)},
                            "happened": {
                                "kind": "text",
                                "text": "Queued for a person; nothing was estimated",
                            },
                        },
                    }
                    for name, count in sorted(by_issue.items(), key=lambda pair: -pair[1])
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _queued_columns(),
                "rows": [_queued_row(index, row) for index, row in enumerate(queued, start=1)],
                "total": len(queued),
                "chips": [
                    {"id": "all", "label": "All", "count": len(queued)},
                    *[
                        {"id": name, "label": ISSUE_LABELS[name], "count": count}
                        for name, count in sorted(by_issue.items(), key=lambda pair: -pair[1])
                    ],
                ],
                "empty": {
                    "title": "Every meter-day validated.",
                    "helper": (
                        f"{gathered.get('intervals_in_the_batch', 0)} intervals rolled up to "
                        f"{gathered.get('meter_days_out', 0)} meter-days across "
                        f"{gathered.get('meters_in_the_batch', 0)} meters. "
                        f"{limits.get('meter_days_judged_against_a_limit', 0)} were judged "
                        "against the utility's own limits. Nothing is waiting for you."
                    ),
                },
            },
        ),
        Block(
            block="row_decisions",
            payload={
                "heading": "Estimated from each meter's own average",
                "columns": _estimate_columns(),
                "rows": [
                    _estimate_row(index, row) for index, row in enumerate(estimated, start=1)
                ],
                # ⚠ **THE CHOICE IS BETWEEN TWO NAMED THINGS, WHICH IS WHAT
                # `RowDecisionsBlock` IS FOR.** An estimate will bill, flagged,
                # and `RB-121`'s design note says the utility may prefer to chase
                # an actual read first — so accepting it and asking for a real
                # read are the two doors, and they are the only two.
                "choices": [
                    {"id": "accept_estimate", "label": "Accept the estimate"},
                    {"id": "chase_a_read", "label": "Chase an actual read →"},
                ],
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "exceptions", "label": "Exceptions", "format": "csv"},
                    {"id": "estimates", "label": "Estimates", "format": "csv"},
                ]
            },
        ),
    ]


# ── the guard and the pinned scope ────────────────────────────────────────


#: Where `resolve()` leaves the guard its answer, so the guard costs no query.
SAMPLE_KEYS = "_sample_meter_days"


def _is_sample(ctx, subject) -> bool:
    """`RB-121`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    ⚠ **IT IS A GUARD AND NOT A FILTER INSIDE A READ, WHICH IS THE WHOLE
    DIFFERENCE.** A guarded subject is still pinned and still counted
    (`BR-RBS-035`), and `RBS-004.4` draws the control disabled WITH its reason
    rather than hiding it; a row quietly dropped inside `resolve()` is invisible
    on every screen and its guard is a check that can never fire.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per METER-DAY** (`BR-RBS-019`, `RBR-18`).

    ⚠ **NOT ONE PER INTERVAL, AND THAT IS THE RULE RATHER THAN THE OPTIMISATION.**
    *"Read validation walks the meter-day; billing never asks about an
    interval"* — `RBR-18`, restating `BR-RBS-019`. A run pinned on intervals
    would open 176,640 savepoints for 1,840 decisions.

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`). A batch somebody posts while
    the run is going is not re-read; the fingerprint the executor computes is
    how a later reader proves the set did not move.

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP**, and
    it is not an error. Step 1 says why in a sentence a clerk can read; a
    `resolve()` that raised would turn a designed outcome into a stack trace.
    """
    batch = _batch(ctx)
    rows = (batch or {}).get("meter_days") or []
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        _subject_id(row) for row in rows if row.get("is_sample")
    )
    return [
        SubjectRef(
            subject_type="meter_day",
            subject_id=_subject_id(row),
            label=f"{row['meter_no']} · {row['day']}",
        )
        for row in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    #: `RB-121`: *"On screen a clerk sees 'Read exceptions.'"* The definition
    #: title — *Read validation on arrival* — is the name on its card; this is
    #: the display name the library and every wireframe draw.
    name="Read exceptions",
    kind=models.KIND_ACTION,
    category="reads",
    subject_type="meter_day",
    unit_of_work="a meter-day rolled up from its intervals",
    # ⚠ MANUAL AND SCHEDULE, NOT `batch.landed` — see the module docstring. A
    # person or a schedule starts it, and the event is emitted by nothing
    # (`CR-069`).
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Reads",),
    parameters=(
        Parameter(
            name="batch",
            type=PARAM_REF_OBJECT,
            label="The interval batch",
        ),
        Parameter(
            name="high_low_limits",
            type=PARAM_REF_SETTING,
            label="High / low limits",
            setting_key="metering.read_validation",
        ),
        Parameter(
            name="rollover",
            type=PARAM_REF_SETTING,
            label="Rollover",
            setting_key="metering.read_validation.rollover",
        ),
        Parameter(
            name="estimate_gaps_up_to_days",
            type=PARAM_REF_SETTING,
            label="Estimate gaps up to",
            setting_key="metering.read_validation.est_max_consecutive",
            default=3,
        ),
        Parameter(
            name="longer_gaps",
            type=PARAM_ENUM,
            label="Longer gaps",
            required=True,
            default="queue_for_a_person",
            # ⚠ ONE CHOICE, AND IT IS A GUARD RATHER THAN A PREFERENCE.
            # `RB-121`: *"Gaps longer than the Settings limit are queued for a
            # person, never estimated."* A dropdown offering *estimate anyway*
            # would put a week of invented consumption on a bill.
            choices=("queue_for_a_person",),
        ),
        Parameter(
            name="hand_to_billing",
            type=PARAM_REF_SETTING,
            label="Hand to billing",
            setting_key="metering.read_validation.hand_to_billing",
        ),
        Parameter(
            name="baseline_days",
            type=PARAM_ENUM,
            label="Estimate from",
            default="90",
            choices=("90",),
        ),
    ),
    guards=(
        Guard(key="sample", label="Never include: Sample", applies=_is_sample),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_GATHER,
            label=STEP_LABELS[STEP_GATHER],
            mode=MODE_SET,
            run=step_gather_the_batch_and_roll_it_up,
        ),
        Step(
            key=STEP_LIMITS,
            label=STEP_LABELS[STEP_LIMITS],
            mode=MODE_SET,
            run=step_check_high_low_and_rollover,
        ),
        Step(
            key=STEP_GAPS,
            label=STEP_LABELS[STEP_GAPS],
            mode=MODE_SET,
            run=step_find_the_gaps,
        ),
        Step(
            key=STEP_ESTIMATE,
            label=STEP_LABELS[STEP_ESTIMATE],
            mode=MODE_SET,
            run=step_estimate_the_short_gaps_by_policy,
        ),
        # ⚠ THE ONLY PER-RECORD STEP, AND THE ONLY ONE THAT CALLS A PORT. One
        # meter-day, one savepoint (hard-won law 14), one record row carrying
        # the plan and the outcome together.
        Step(
            key=STEP_WRITE,
            label=STEP_LABELS[STEP_WRITE],
            mode=MODE_PER_RECORD,
            run=step_write_validated_meter_days_as_reads,
            writes=True,
        ),
        Step(
            key=STEP_RAISE,
            label=STEP_LABELS[STEP_RAISE],
            mode=MODE_SET,
            run=step_raise_exceptions_as_work_items,
            writes=True,
        ),
    ),
    ports=("write_read",),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-033 (EP-RBS-05; CR-075 wave R′)
# generated: 2026-09-07 by the CR-075 wave R′ metering-and-customers lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_033_read_validation.py · pytest tests/test_rbs_reads_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing is written — `write_read` binds NO writer at all (US-MET-010: an automation may not certify a reading), so the KPI strip says "To validate"; the card's own two interval figures disagree (96 per meter-day vs "reads arrive hourly") and this runbook measures the cadence instead of assuming either; `Most estimates per run` is the runbook row's `cap` rather than a parameter (RBR-03) and it REFUSES rather than truncating; the queued table drops the card's `Account` column, which is a read per row at this unit of work; work items are counted, not raised (wave H)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
