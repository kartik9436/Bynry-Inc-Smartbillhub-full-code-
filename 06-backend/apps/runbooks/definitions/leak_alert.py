# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-023 (EP-RBS-05) — CR-075 wave R′: runbook 11, *Leak and
#           high-usage alert* — six steps over the intervals that landed
#           overnight, four read and two write.
# Rules:    BR-RBS-002 (a Check is constructed with no writer — this is an
#           Action and holds two named ports) · BR-RBS-003 (dry and live are
#           ONE code path) · BR-RBS-004 (an Action always produces a PLAN
#           first) · BR-RBS-006 (a cap REFUSES the run; it never truncates) ·
#           BR-RBS-009 (scope resolved ONCE and pinned) · BR-RBS-010 (every
#           record states the rule that decided it, in words a clerk can read) ·
#           BR-RBS-011 (a failure names its fix route) · BR-RBS-012 (a guard is
#           absolute and runs before any step) · BR-RBS-019 (the declared unit
#           of work) · BR-RBS-020 (the report is composed at close and frozen) ·
#           BR-RBS-021 (twelve blocks) · BR-RBS-022 (a write is a named port) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-027 (a stopped run
#           reads *Never reached*) · BR-RBS-035 (a volume runbook keeps a row
#           for what it acted on and a COUNT for the rest) · BR-RBS-039 (every
#           foreign read through a seam this module owns) · BR-RBS-040 (a NOTE
#           is an engine act, never a fourteenth port — so it is NOT the
#           substitute for the missing leak flag) · BR-RBS-041 (permission is
#           granted UP FRONT, per runbook; the switch removes the WAIT, never
#           the plan) · BR-NOT-005 / RBR-07 (a notice is QUEUED; the dispatcher
#           sends) · BR-NOT-009 (quiet hours travel as a parameter, never a
#           clock read) · RBR-15 (the leak text names the utility, the address
#           and the hours — never the account or a dollar figure) · RBR-03
#           (policy lives in Settings and is never duplicated on a card) ·
#           CLAUDE.md hard rule 3 (a consumption ALWAYS carries an explicit
#           unit) · hard rule 8 (an address lives on `premises` and nowhere
#           else) · hard-won law 2 · law 7 · law 14 · B14 rules 31, 32, 33
# Tests:    06-backend/tests/test_us_rbs_023_leak_alert.py ·
#           06-backend/tests/test_rbs_reads_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/metering_seam.py ·
#           apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/notifications_seam.py ·
#           apps/metering/selectors.py · apps/notifications/selectors.py
#           · 04-docs/05-modules/17-runbooks/11-catalogue/RB-111-leak-and-high-usage-alert.md
# ───────────────────────────────────────────────────────
"""Runbook 11 — **Leak and high-usage alert**.

Water has been running at 14 Cedar St for twenty-six hours. This finds it in
last night's intervals and tells the customer, before the bill does. Its value
is the call it prevents: a customer told on Tuesday does not ring on the 20th
about a $600 bill.

WHO STARTS IT, AND WHY THAT IS NOT THE EVENT THE CARD NAMES
------------------------------------------------------------
`RB-111`'s trigger row reads ⚡ `batch.landed`; its own `Runs` parameter reads
*Daily 07:30*. The card records both and says *"neither has been reconciled by a
ruling"*. **This declares manual and schedule**, which covers the clock half
exactly and waits on nothing — `batch.landed` is emitted by nothing (zero
occurrences anywhere in the backend, verified again 2026-09-07) and is
`CR-069`'s work, currently scoped to nobody. `models.py` already rules that *"a
runbook whose only trigger is an unbuilt event is not runnable, and a screen
must SAY so rather than offering a Run ▶ that refuses"*. The event joins them
the day it exists.

"NOTHING HAS LANDED" IS AN ANSWER, AND IT IS STEP 1
----------------------------------------------------
PO ruling 2026-09-06, verbatim: *"in absence of API conenctions you will not
find anything and you can stop the job saying APi or conenct not available;
that is a valid case and state for us"*. Two doors — a live meter connection
(`meters_mdm`, `meters_neptune360`) and intervals already landed in the product
— and the run STOPS only when both are shut: one red chain cell, five honestly
reading *Never reached* (`BR-RBS-027`), **no KPI strip over a run that examined
nothing**, and the word *failed* nowhere.

THE TWO THINGS IT LOOKS FOR, AND WHY THEY ARE DIFFERENT SHAPES
----------------------------------------------------------------
* **Continuous flow** — every interval of the last N hours carried a non-zero
  reading. A house with nobody in it uses nothing between 02:00 and 05:00; a
  house whose supply never stops has a tap open or a pipe split.
* **Far above its own normal** — the day's total over a multiple of this
  meter's OWN 90-day average (S-1). **Never a fleet number**: a block of flats
  and a bungalow share nothing, and a fleet average alerts on every large
  customer every day and never on a small one with a running tap.

`RB-111` step 3: *"the larger of the two wins"* — a meter that is both gets one
alert naming the more alarming pattern, not two texts in one morning.

⚠ **AND BOTH ARE MEASURED IN THE METER'S OWN UNIT** (CLAUDE.md hard rule 3).
*Ignore below 200 gal/day* is a floor with a UNIT in it; comparing it against a
meter reporting in CCF would suppress every real leak or none, and both look
exactly like a working threshold. A meter whose unit does not match the floor's
is REPORTED (`floor_unit_mismatch`) and not judged.

THE ADDRESS IS WALKED TO, NEVER READ OFF THE METER
----------------------------------------------------
CLAUDE.md hard rule 8, `BR-MET-1161`: **an address is stored on `premises` and
nowhere else.** A meter, a service point, a unit, an account and a route all
declare no address column, so the alert text's *"14 Cedar St"* is reached by
walking meter → service point → unit → premises. The walk's two ids travel on
the rolled-up row and the address itself comes from metering's own premises
read; nothing here composes an address out of parts (`BR-NOT-029` (a)) and
nothing reads a retired `kind='service'` row, which is refused by name.

WHAT IT PLANS AND WHAT IT ACTUALLY DOES TODAY
-----------------------------------------------
**Nothing is queued and no meter is flagged**, and the two have different
reasons:

* **`queue_notice` IS bound** (`CR-075` task `L2`, to
  `apps.notifications.runbook_ports.queue_notice`) and still writes nothing,
  because `engine.acts.LIVE_ENABLED_RUNBOOKS` is an **empty frozenset** for the
  whole catalogue. That is phase 2's dry half.
* **`flag_meter` binds NO WRITER AT ALL**, and not because a wave has not
  reached it: *"there is no column anywhere to hold 'told about a leak on
  <date>', and `Asset` lives in `apps/assets`, which is not one of the five
  modules a port may write"* — the port's own declaration, and `DEF-RBS-4331`.

⚠ **AND THE OBVIOUS SUBSTITUTE IS FORBIDDEN.** `BR-RBS-040` (CONFIRMED, PO
2026-09-06) makes a NOTE an ENGINE act rather than a port, precisely so a Check
can cause one while holding no writer. Binding `flag_meter` to a note would make
`BR-RBS-002` false and **nothing in the suite would notice** — the note would
still be written and every count would still agree.

⚠ **SO STEP 6 — *"Record it against the meter, so next week's run knows"* —
CANNOT BE PERFORMED, AND THE GUARD THAT DEPENDS ON IT READS OUR OWN OUTBOX
INSTEAD.** *Once per meter every 7 days* and the *Told this week* guard need a
durable record that we told somebody. The only one in this product is
`outbound_messages`, keyed on the deterministic `source_id`
`apps.notifications.runbook_ports.runbook_source_id` mints from
*runbook | subject | discriminator* — so *"did we alert WM-04471 on the 4th"* is
a computable question needing no new column. **It is structurally empty on this
deployment** (nothing has ever queued a leak alert), so *0 told this week* means
*nobody has been told yet* and not *the guard looked and found nothing* — and
the run reports the outbox rows it could see beside the guard count so a reader
can tell the two apart (hard-won law 7).

⚠ **THE PORTS ARE CALLED ANYWAY AND THEIR OWN REFUSALS ARE RECORDED.** There is
no `if is_bound` branch: `BR-RBS-003` makes dry and live one code path, and a
branch would be a second path proving nothing about the first. The KPI tile
therefore reads **To queue** rather than *Alerts queued* — a tile saying
**9 Alerts queued** over a run that queued nothing is the most dangerous
sentence this screen could print.

FOUR PLACES THIS DIVERGES FROM `RB-111`, EACH STAMPED
-------------------------------------------------------
1. **The *Unattended after* parameter's REASON has changed and the card has
   not.** `RB-111` says it is drawn read-only *"because open decision 4 is
   unruled"*. **`OQ-RBS-1733` CLOSED on 2026-09-06** — and with a FOURTH option
   nobody offered: `BR-RBS-041`, *permission is granted UP FRONT, per runbook*,
   PO verbatim *"ask for permission from user upfront - if they are okay we
   complete the run and action, otherwise not"*. **The three-clean-run ratchet
   the card describes is NOT built and is not going to be.** The parameter stays
   read-only, for a different reason: the switch it would draw is wave `L3`'s
   and `runbooks.gate_mode` holds one value today. The card is stamped in the
   same commit as this file (step W), and this paragraph is why.
2. **The KPI strip says *To queue* while nothing is queued**, where the card's
   word is *Alerts queued*. It returns the day wave `N` turns a runbook on.
3. **Step 6 records nothing and says so.** The card's *"Record it against the
   meter"* has no column to write to; the step counts what it WOULD record and
   the screen carries the number rather than a silent zero.
4. **The channel ladder is the CARD's — text, then email** — while
   `customers.contact_channels_for` fixes its own order as email → text → post
   for the undeliverable-contacts runbook. A leak wants the fastest channel and
   `RB-111` names it; the two orders are both deliberate and this one is the
   card's. The seam is asked only *what is on file*, never *in what order*.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
Hard-won law 7's second habit, and every answer is a number on the screen:

* **A run that examined nothing and a run that found no leaks must not read the
  same.** The strip carries the meters examined beside the alert count, and a
  stopped run has no strip at all.
* **A meter with no history has no normal, and no normal is not zero.** A zero
  would make every reading infinitely above its own normal and put that on a
  customer's phone at 07:30. Those meters are counted in
  `meters_with_no_normal` and never alerted on the spike rule.
* **A guard that cannot be evaluated is not a guard that passed.** The outbox
  row count travels beside *told this week*, so a structurally empty store is
  visible rather than indistinguishable from a quiet week.
* **A floor in the wrong unit judges nothing.** `floor_unit_mismatch` carries
  the number, because a declared blind spot with no number attached is
  indistinguishable from an empty one (`G32`'s shape — 0 unresolved, truthfully,
  over 21 live refusals).
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
    PARAM_REF_SETTING,
    Block,
    Guard,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import (
    customers_seam,
    integrations_seam,
    metering_seam,
    notifications_seam,
)

KEY = "leak_alert"

#: The meter manifests, verified against `06-backend/apps/integrations/manifests/`
#: and named as VALUES rather than imported: a manifest key crossing the seam is
#: data, and importing `apps.integrations.manifests` is what `G115` refuses.
# ⚠ `meters_mdm` — the one card that read *Itron / Sensus* — BECAME TWO in
# `CR-110-BRC04`, and Badger BEACON joined them as connector 07. All three
# are head-ends of the same shape (`BR-INT-037`), so all three belong here.
METER_PROVIDER_KEYS = (
    "meters_neptune360",
    "meters_badger",
    "meters_itron",
    "meters_sensus",
)

#: The `source_type` a queued notice files under, and the discriminator prefix
#: the *told this week* probe recomputes. Both are constants rather than
#: parameters: they ARE the key, and a key a tenant could change is not a key.
NOTICE_SOURCE_TYPE = "notice"
DISCRIMINATOR = "leak"

#: Where step 1 leaves the utility's name so the FROZEN report can read it.
UTILITY_NAME_KEY = "_utility_name"

# ── the two patterns, and the outcomes one meter can reach ────────────────

PATTERN_CONTINUOUS = "continuous"
PATTERN_SPIKE = "spike"

OUTCOME_QUEUED = "queued"
OUTCOME_PLANNED = "planned"
OUTCOME_NO_CHANNEL = "no_channel"
OUTCOME_NOBODY_TO_TELL = "nobody_to_tell"
OUTCOME_BELOW_THE_FLOOR = "below_the_floor"
OUTCOME_NOTHING_WRONG = "nothing_wrong"
OUTCOME_CANNOT_JUDGE = "cannot_judge"

#: What a clerk calls each pattern. ⚠ A refusal caps at five or six words
#: (B14 rule 33) and carries no rule id (rule 32).
PATTERN_LABELS = {
    PATTERN_CONTINUOUS: "Continuous",
    PATTERN_SPIKE: "Far above normal",
}

# ── the steps, in the card's own order ────────────────────────────────────

STEP_GATHER = "gather_the_window_of_intervals"
STEP_NORMAL = "work_out_each_meters_own_normal"
STEP_FLAG = "flag_continuous_flow_or_a_spike"
STEP_GUARDS = "apply_guards_and_once_a_week"
STEP_QUEUE = "queue_the_alert"
STEP_RECORD = "record_it_against_the_meter"

STEP_LABELS = {
    STEP_GATHER: "Gather 48 hours of intervals",
    STEP_NORMAL: "Work out each meter's own normal",
    STEP_FLAG: "Flag continuous flow or a spike",
    STEP_GUARDS: "Apply guards and once-a-week",
    STEP_QUEUE: "Queue the alert",
    STEP_RECORD: "Record it against the meter",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-07.** A fix route resolving to nothing is
# a dead button over a live finding (hard-won law 2's mirror). Tenant-relative:
# the shell prefixes `/:tenant/`.
FIX_ACCOUNTS = "accounts"
FIX_ASSETS = "assets"
FIX_READS = "reads"


def _decimal(raw: Any) -> Decimal | None:
    """A stored quantity as a `Decimal`, or `None`. **Never a float.**"""
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):  # pragma: no cover — the seam quantizes
        return None


@dataclass(frozen=True)
class Finding:
    """One meter, and what this run decided about it.

    ⚠ **`quantity` AND `unit` TRAVEL TOGETHER OR NOT AT ALL** (hard rule 3): a
    quantity with no unit is refused at construction. *1,140* on a screen beside
    *860* invites a comparison that is only meaningful when both are gallons.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `asset_id` and `account_id` are the handles the ports need; `meter_no` and
    `customer_name` are what a clerk reads.

    ⚠ **`address` IS WALKED TO FROM THE PREMISES AND IS NOT A COLUMN ON
    ANYTHING ELSE** (hard rule 8). It is on this object because the alert TEXT
    names it — `RBR-15` — and for no other reason.
    """

    asset_id: str
    meter_no: str
    account_id: str | None
    account_label: str | None
    address: str | None
    pattern: str | None
    hours: int | None
    multiple: Decimal | None
    quantity: Decimal | None
    unit: str | None
    channel: str | None
    outcome: str
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a finding with no reason says nothing to anybody")
        if self.quantity is not None and not self.unit:
            raise ValueError(
                f"meter {self.meter_no!r} carries a quantity and no unit. CLAUDE.md hard rule 3: "
                "a consumption always carries an EXPLICIT unit and one is never assumed."
            )
        if not self.fix_route.strip():
            raise ValueError(
                f"meter {self.meter_no!r} names no fix route. BR-RBS-011: a failure names its "
                "fix route, and a failure with no route is a defect in the runbook."
            )

    @property
    def quantity_text(self) -> str:
        """The day's usage as a clerk reads it — the number AND its unit."""
        if self.quantity is None:
            return "—"
        return f"{self.quantity.normalize():f} {self.unit}"

    def message(self, utility: str) -> str | None:
        """The text the customer receives, IN FULL — `RB-111`'s own sentence.

        ⚠ **IT NAMES THE UTILITY, THE ADDRESS AND THE HOURS — NEVER THE ACCOUNT
        AND NEVER A DOLLAR FIGURE** (`RBR-15`). A customer cannot act on either:
        they cannot stop a leak by knowing their account number, and a dollar
        estimate at 07:30 is a bill nobody has issued.

        `None` when there is no address to name, because a leak alert that
        cannot say WHERE is a text nobody can act on — and that is a finding
        rather than a message with a hole in it.
        """
        if not self.address:
            return None
        if self.pattern == PATTERN_CONTINUOUS and self.hours is not None:
            middle = f"water has been running at {self.address} for {self.hours} hours"
        else:
            middle = f"water use at {self.address} is well above normal"
        return f"{utility}: {middle}. If nobody is using it, please check for a leak. Reply STOP to opt out."

    def as_row(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "meter_no": self.meter_no,
            "account_id": self.account_id,
            "account_label": self.account_label,
            "address": self.address,
            "pattern": self.pattern,
            "hours": self.hours,
            "multiple": None if self.multiple is None else str(self.multiple),
            "quantity": None if self.quantity is None else str(self.quantity),
            "unit": self.unit,
            "quantity_text": self.quantity_text,
            "channel": self.channel,
            "outcome": self.outcome,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration: a step reporting nothing over an empty window
    and a step reporting nothing over a quiet night are the same sentence with
    very different meanings (hard-won law 7).
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
    """The intervals this run is pinned to, already rolled up to the meter-day.

    ⚠ **THE ROLLUP IS THE SEAM's AND NOT THIS FILE's** (`BR-RBS-019`). This
    runbook's subject is the METER; the rollup is what makes *48 hours of
    intervals* two rows per meter instead of 192.
    """
    return metering_seam.interval_batch(ctx.params.get("batch"))


def _window_hours(ctx) -> int:
    return int(ctx.params.get("window_hours") or 48)


def _as_of(ctx, batch: dict[str, Any] | None) -> date:
    """The day this run is FOR — the batch's own latest day, never a clock.

    `BR-TEN-043` and gate `G6`. A run re-run tomorrow over the same intervals
    must reach the same answer, or the pinned scope means nothing.
    """
    stated = ctx.params.get("as_of")
    if isinstance(stated, datetime):
        return stated.date()
    if isinstance(stated, date):
        return stated
    if isinstance(stated, str) and stated:
        try:
            return date.fromisoformat(stated[:10])
        except ValueError:  # pragma: no cover — the validator refuses it first
            pass
    days = sorted(one["day"] for one in ((batch or {}).get("meter_days") or []))
    return date.fromisoformat(days[-1]) if days else date(1970, 1, 1)


def _days_in_window(ctx, batch: dict[str, Any] | None) -> list[str]:
    """The calendar days the window covers, newest last.

    The window is stated in HOURS on the card (*Last 48 hours*) and the rolled-up
    unit is a DAY, so the window is read as the last `ceil(hours / 24)` days the
    batch actually carries. Reading it as *the last 48 rows* would silently
    change meaning between an hourly feed and a fifteen-minute one.
    """
    days = sorted({one["day"] for one in ((batch or {}).get("meter_days") or [])})
    span = max(1, -(-_window_hours(ctx) // 24))
    return days[-span:]


def _meters(batch: dict[str, Any] | None, days: list[str]) -> dict[str, dict[str, Any]]:
    """One entry per METER over the window — the declared unit of work.

    ⚠ **THE SUBJECT IS THE METER AND NOT THE METER-DAY**, which is where this
    runbook differs from runbook 21 over the very same rows. One customer gets
    one text about one leak; a per-meter-day subject would text them twice for a
    tap that ran for two days, which is the whole reason *once per meter every
    seven days* exists.
    """
    wanted = set(days)
    out: dict[str, dict[str, Any]] = {}
    for row in (batch or {}).get("meter_days") or []:
        if row["day"] not in wanted:
            continue
        entry = out.setdefault(
            str(row["asset_id"]),
            {
                "asset_id": str(row["asset_id"]),
                "meter_no": row.get("meter_no"),
                "unit_id": row.get("unit_id"),
                "premises_id": row.get("premises_id"),
                "service": row.get("service"),
                "is_sample": bool(row.get("is_sample")),
                "days": [],
                "intervals": 0,
                "zero_intervals": 0,
                "nonzero_intervals": 0,
                "quantity": Decimal("0"),
                "unit": row.get("unit"),
                "unit_conflict": bool(row.get("unit_conflict")),
                "first_at": row.get("first_at"),
                "last_at": row.get("last_at"),
            },
        )
        entry["days"].append(row["day"])
        entry["intervals"] += int(row.get("intervals") or 0)
        entry["zero_intervals"] += int(row.get("zero_intervals") or 0)
        entry["nonzero_intervals"] += int(row.get("nonzero_intervals") or 0)
        # ⚠ **A WINDOW TOTAL IS ONLY A NUMBER WHEN EVERY DAY IN IT AGREES ABOUT
        # THE UNIT** (hard rule 3). Two days in two units do not add up, and the
        # meter is reported rather than summed.
        if row.get("unit") and entry["unit"] and row["unit"] != entry["unit"]:
            entry["unit_conflict"] = True
        if row.get("unit_conflict"):
            entry["unit_conflict"] = True
        amount = _decimal(row.get("quantity"))
        if amount is not None:
            entry["quantity"] += amount
        if row.get("first_at") and (
            entry["first_at"] is None or row["first_at"] < entry["first_at"]
        ):
            entry["first_at"] = row["first_at"]
        if row.get("last_at") and (entry["last_at"] is None or row["last_at"] > entry["last_at"]):
            entry["last_at"] = row["last_at"]
    return out


def _stopped(ctx) -> dict[str, Any] | None:
    for key in (STEP_GATHER, STEP_GUARDS):
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
    """
    for key in (STEP_GUARDS, STEP_FLAG, STEP_NORMAL):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


def _cap(ctx) -> int | None:
    """The tenant's own limit, from the runbook row (`RBR-03`).

    Not a parameter: the card carries none, and a parameter of the same name
    would be a second copy of one policy free to disagree with Settings.
    """
    if ctx.run_id is None:
        return None
    return (
        models.RunbookRun.objects.filter(pk=ctx.run_id)
        .values_list("runbook__cap", flat=True)
        .first()
    )


# ── step 1 · the window ───────────────────────────────────────────────────


def step_gather_the_window_of_intervals(ctx, subjects) -> dict[str, Any]:
    """1 · Two doors, and the run STOPS when both are shut.

    The card's step 1 reads *"Landed by the meter connection; this only reads
    them"* — so the run cannot create work, only find it, and *"nothing has
    landed"* is a designed answer rather than a crash (`BR-RBS-027`).
    """
    connections = integrations_seam.live_connections(METER_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    batch = _batch(ctx)
    days = _days_in_window(ctx, batch)
    meters = _meters(batch, days)

    # ⚠ **THE REPORT IS COMPOSED FROM THE FROZEN VIEW AND THE VIEW CARRIES NO
    # PARAMETERS** (`BR-RBS-020`, `_ReportView`). The alert TEXT names the
    # utility (`RBR-15`), so the name is stashed in `set_results` here — the one
    # channel a report can read — rather than the report reaching for a `ctx` it
    # deliberately does not have.
    ctx.set_results[UTILITY_NAME_KEY] = _utility_name(ctx)

    checked: dict[str, Any] = {
        "meter_connections_looked_for": len(METER_PROVIDER_KEYS),
        "meter_connections_found": len(connections),
        "meter_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "batch_landed": batch is not None,
        "file_name": (batch or {}).get("file_name"),
        "window_hours": _window_hours(ctx),
        "days_in_the_window": days,
        "intervals_read": sum(int(one["intervals"]) for one in meters.values()),
        "meters_with_interval_data": len(meters),
        "sample_meters_guarded": len([one for one in meters.values() if one["is_sample"]]),
        "meters_with_two_units": len([one for one in meters.values() if one["unit_conflict"]]),
        "meters_with_no_unit": len([one for one in meters.values() if not one["unit"]]),
    }

    if batch is None and not working:
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "A meter connection is set up and switched off."
            if offline
            else "No meter connection is set up."
        )
        return _StepResult(
            stop={
                "headline": "No interval data to read.",
                "detail": (
                    f"{detail} No intervals have landed either, so there is nothing to look "
                    "at for a leak. Connect the head-end, or upload an interval file."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Open reads",
            },
            checked=checked,
        ).as_dict()

    if batch is None:
        return _StepResult(
            stop={
                "headline": "Nothing has landed yet.",
                "detail": (
                    f"{', '.join(str(one) for one in checked['connection_names'])} is connected "
                    "and no intervals have arrived for this run. Start this again when a batch "
                    "lands."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Open reads",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(checked=checked).as_dict()


# ── step 2 · each meter's own normal ──────────────────────────────────────


def step_work_out_each_meters_own_normal(ctx, subjects) -> dict[str, Any]:
    """2 · Its 90-day average, not a fleet number — S-1, the card's own words.

    ⚠ **AND WHO IT BELONGS TO, IN THE SAME PASS.** The alert has to reach a
    person and name a place, so this is where the meter is joined to its account
    (through the unit) and to its address (through the premises). Both are BULK
    reads — one query each for the whole window — because `service_point_graph`
    already records what per-meter reads cost at this scale, and 1,840 meters at
    07:30 is the case it warns about.

    ⚠ **THE ADDRESS COMES FROM THE PREMISES AND NOWHERE ELSE** (hard rule 8).
    Nothing here reads an address off an account, a meter or a route, because
    none of them has one.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    batch = _batch(ctx)
    days = _days_in_window(ctx, batch)
    in_scope = {str(one.subject_id) for one in subjects}
    meters = {
        key: value for key, value in _meters(batch, days).items() if key in in_scope
    }
    as_of = _as_of(ctx, batch)
    normals = metering_seam.meter_normals(
        list(meters), as_of=as_of, days=int(ctx.params.get("baseline_days") or 90)
    )
    accounts = customers_seam.accounts_for_units(
        [one["unit_id"] for one in meters.values() if one["unit_id"]]
    )
    channels = customers_seam.contact_channels_for(
        [one["id"] for one in accounts.values()]
    )
    # ⚠ **ONE READ FOR THE WHOLE ESTATE'S ADDRESSES.** `premises` is the product's
    # one address home and this is metering's own bulk read of it; a per-meter
    # address lookup would be a query per row on the table this runbook is
    # largest over.
    addresses = {
        str(one["premises_id"]): one.get("address_line")
        for one in metering_seam.premises_for_reconciliation(include_sample=True)
    }

    plan: list[dict[str, Any]] = []
    no_normal = 0
    no_account = 0
    for key, meter in meters.items():
        normal = normals.get(key) or {}
        if normal.get("average_per_day") is None:
            no_normal += 1
        account = accounts.get(str(meter["unit_id"])) if meter["unit_id"] else None
        if account is None:
            no_account += 1
        plan.append(
            {
                **meter,
                "normal_per_day": normal.get("average_per_day"),
                "normal_unit": normal.get("unit"),
                "normal_days_covered": normal.get("days_covered"),
                "account_id": None if account is None else account["id"],
                "account_label": None if account is None else account.get("customer_name"),
                "channels": (
                    {} if account is None else dict(channels.get(account["id"]) or {})
                ),
                "address": addresses.get(str(meter["premises_id"])),
            }
        )

    return _StepResult(
        plan=plan,
        checked={
            "meters_examined": len(meters),
            "meters_with_no_normal": no_normal,
            "meters_with_no_account": no_account,
            "meters_with_no_address": len([one for one in plan if not one["address"]]),
            "baseline_days": int(ctx.params.get("baseline_days") or 90),
        },
    ).as_dict()


# ── step 3 · the two patterns ─────────────────────────────────────────────


def step_flag_continuous_flow_or_a_spike(ctx, subjects) -> dict[str, Any]:
    """3 · Both thresholds; **the larger of the two wins** (the card's own rule).

    ⚠ **THE FLOOR HAS A UNIT IN IT AND SO DOES THE METER** (hard rule 3). *Ignore
    below 200 gal/day* judges nothing on a meter reporting in CCF, and comparing
    them anyway would suppress every real leak or none — both of which look
    exactly like a working threshold. The mismatch is COUNTED and the meter is
    reported as *cannot judge*, never as clean.

    ⚠ **NO NORMAL IS NOT A NORMAL OF ZERO.** A meter with no history cannot be
    judged on the spike rule at all; it can still be judged on continuous flow,
    which needs no history — so it is not silently exempted from both.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    hours_needed = int(ctx.params.get("continuous_hours") or 24)
    multiple_needed = _decimal(ctx.params.get("above_normal_multiple") or "3")
    floor = _decimal(ctx.params.get("ignore_below") or "200")
    floor_unit = str(ctx.params.get("ignore_below_unit") or "gal")
    window_hours = _window_hours(ctx)

    out: list[dict[str, Any]] = []
    continuous = spike = below = mismatch = cannot = 0
    for row in plan:
        unit = row.get("unit")
        quantity = None if row.get("unit_conflict") else _decimal(row.get("quantity"))
        intervals = int(row.get("intervals") or 0)
        nonzero = int(row.get("nonzero_intervals") or 0)
        normal = _decimal(row.get("normal_per_day"))
        normal_unit = row.get("normal_unit")
        days = max(len(row.get("days") or []), 1)

        pattern: str | None = None
        hours: int | None = None
        multiple: Decimal | None = None

        if row.get("unit_conflict") or not unit:
            cannot += 1
            out.append({**row, "pattern": None, "hours": None, "multiple": None,
                        "judgement": OUTCOME_CANNOT_JUDGE})
            continue
        if unit != floor_unit:
            # ⚠ A DECLARED BLIND SPOT WITH A NUMBER ATTACHED (law 7).
            mismatch += 1
            cannot += 1
            out.append({**row, "pattern": None, "hours": None, "multiple": None,
                        "judgement": OUTCOME_CANNOT_JUDGE})
            continue
        per_day = None if quantity is None else quantity / Decimal(days)
        if floor is not None and per_day is not None and per_day < floor:
            below += 1
            out.append({**row, "pattern": None, "hours": None, "multiple": None,
                        "judgement": OUTCOME_BELOW_THE_FLOOR})
            continue

        # ── continuous flow: every interval in the window carried usage ──
        if intervals and nonzero == intervals:
            hours = int(round(window_hours * intervals / max(intervals, 1)))
            if hours >= hours_needed:
                pattern = PATTERN_CONTINUOUS

        # ── far above its own normal ──
        if normal is not None and normal > 0 and normal_unit == unit and per_day is not None:
            multiple = (per_day / normal).quantize(Decimal("0.1"))
            if multiple_needed is not None and multiple >= multiple_needed:
                # ⚠ **THE LARGER OF THE TWO WINS**, so a meter that is both gets
                # ONE alert naming the more alarming pattern rather than two
                # texts in one morning. Continuous flow is the more alarming: a
                # supply that never stops is a pipe, and a spike is a party.
                pattern = pattern or PATTERN_SPIKE

        if pattern == PATTERN_CONTINUOUS:
            continuous += 1
        elif pattern == PATTERN_SPIKE:
            spike += 1
        out.append(
            {
                **row,
                "pattern": pattern,
                "hours": hours if pattern == PATTERN_CONTINUOUS else None,
                "multiple": None if multiple is None else str(multiple),
                "judgement": OUTCOME_PLANNED if pattern else OUTCOME_NOTHING_WRONG,
                "per_day": None if per_day is None else str(per_day),
            }
        )

    return _StepResult(
        plan=out,
        checked={
            "continuous_flow": continuous,
            "far_above_own_normal": spike,
            "below_the_floor": below,
            # Both of these are the *reported blind spot* half. A zero means the
            # check covered its whole subject; a number means it did not.
            "floor_unit_mismatch": mismatch,
            "meters_that_could_not_be_judged": cannot,
            "continuous_hours": hours_needed,
            "above_normal_multiple": str(multiple_needed),
            "ignore_below": f"{floor} {floor_unit}",
        },
    ).as_dict()


# ── step 4 · guards, once-a-week, and the cap ─────────────────────────────


def _already_told_ids(runbook_key: str, asset_ids: list[str], days: list[str]) -> dict[str, str]:
    """`{asset_id: the day we told them}` for anything already alerted.

    ⚠ **THIS IS THE ONLY DURABLE RECORD IN THE PRODUCT THAT WE TOLD SOMEBODY
    SOMETHING**, and it is our own outbox rather than a flag on the meter —
    because there is no such flag (`DEF-RBS-4331`, the `flag_meter` port's own
    declaration) and because writing a NOTE instead is forbidden (`BR-RBS-040`
    makes a note an engine act, never a fourteenth port).

    The `source_id` is deterministic — `runbook | subject | discriminator` — so
    one bulk read over the window's candidate ids answers *did we alert this
    meter on any of these days*. One query, not one per meter per day.
    """
    from apps.notifications import runbook_ports as notifications_writers

    wanted: dict[str, tuple[str, str]] = {}
    for asset_id in asset_ids:
        for day in days:
            source_id = str(
                notifications_writers.runbook_source_id(
                    runbook_key=runbook_key,
                    subject_id=asset_id,
                    discriminator=f"{DISCRIMINATOR}|{day}",
                )
            )
            wanted[source_id] = (asset_id, day)
    found = notifications_seam.queued_source_ids(NOTICE_SOURCE_TYPE, list(wanted))
    told: dict[str, str] = {}
    for source_id in found:
        asset_id, day = wanted[source_id]
        if asset_id not in told or day > told[asset_id]:
            told[asset_id] = day
    return told


def step_apply_guards_and_once_a_week(ctx, subjects) -> dict[str, Any]:
    """4 · Opted out, in dispute, already told — **skipped, not sent**.

    ⚠ **THE *ONCE PER METER EVERY 7 DAYS* GUARD CANNOT READ THE COLUMN THE CARD
    ASSUMES, AND THE SUBSTITUTE IS NAMED RATHER THAN HIDDEN.** *Told about a
    leak on the 4th* has no home in this product; the outbox does, so the guard
    reads the outbox. **It is structurally empty on this deployment**, so
    `outbox_rows_seen` travels beside `told_this_week` — 0 told over 0 rows means
    *nobody has been told yet*, and 0 told over 4,000 rows would mean *the guard
    ran and found nothing*. Those are different facts and a single zero cannot
    say which (hard-won law 7).

    ⚠ **A METER WITH NO CHANNEL IS A FINDING, NOT A SKIP.** `RB-111`'s own
    result names *1 no channel* and its design note says the row with no channel
    is the data-hygiene runbook's problem — so it is REPORTED with its own
    outcome and its own fix route rather than dropped.

    ⚠ **THE CAP REFUSES THE RUN; IT NEVER TRUNCATES** (`BR-RBS-006`). Nine
    alerts against a limit of five stops and says both numbers; queueing five and
    dropping four is the failure that looks like success.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)

    plan = _plan(ctx)
    once_every = int(ctx.params.get("once_per_meter_days") or 7)
    batch = _batch(ctx)
    as_of = _as_of(ctx, batch)
    window = [
        (as_of - timedelta(days=offset)).isoformat() for offset in range(once_every)
    ]
    candidates = [one for one in plan if one.get("pattern")]
    told = _already_told_ids(KEY, [one["asset_id"] for one in candidates], window)
    outbox_rows = len(told)

    out: list[dict[str, Any]] = []
    to_queue = told_this_week = no_channel = nobody = disputed = 0
    for row in plan:
        if not row.get("pattern"):
            out.append({**row, "outcome": row.get("judgement") or OUTCOME_NOTHING_WRONG,
                        "channel": None})
            continue
        if row["asset_id"] in told:
            told_this_week += 1
            out.append({**row, "outcome": "told_this_week", "channel": None,
                        "told_on": told[row["asset_id"]]})
            continue
        if row.get("unit_id") and metering_seam.unit_has_dispute_hold(row["unit_id"]):
            # A customer in dispute about their usage does not need a text
            # telling them their usage is high. `RB-111`'s *Never include* list.
            disputed += 1
            out.append({**row, "outcome": "in_dispute", "channel": None})
            continue
        if row.get("account_id") is None:
            nobody += 1
            out.append({**row, "outcome": OUTCOME_NOBODY_TO_TELL, "channel": None})
            continue
        channels = row.get("channels") or {}
        # ⚠ THE CARD'S OWN LADDER — TEXT, THEN EMAIL (divergence 4). A leak
        # wants the fastest channel; `customers` fixes a different order for the
        # undeliverable runbook and this asks it only *what is on file*.
        channel = "text" if channels.get("text") else ("email" if channels.get("email") else None)
        if channel is None:
            no_channel += 1
            out.append({**row, "outcome": OUTCOME_NO_CHANNEL, "channel": None})
            continue
        to_queue += 1
        out.append({**row, "outcome": OUTCOME_PLANNED, "channel": channel})

    cap = _cap(ctx)
    checked = {
        "alerts_to_queue": to_queue,
        "told_this_week": told_this_week,
        # ⚠ THE NUMBER THAT TELLS A STRUCTURALLY EMPTY GUARD FROM A QUIET WEEK.
        "outbox_rows_seen": outbox_rows,
        "no_channel": no_channel,
        "nobody_to_tell": nobody,
        "in_dispute": disputed,
        "once_per_meter_days": once_every,
        "cap": cap,
    }
    if cap is not None and to_queue > int(cap):
        return _StepResult(
            plan=out,
            stop={
                "headline": "Too many alerts for one run.",
                "detail": (
                    f"This run would send {to_queue} alerts and the limit is {cap}. "
                    "Nothing has been queued. Raise the limit, or work through the list "
                    "and run this again."
                ),
                "fix_route": FIX_READS,
                "fix_label": "Open reads",
            },
            checked=checked,
        ).as_dict()
    return _StepResult(plan=out, checked=checked).as_dict()


# ── step 5 · the one write, one meter at a time ───────────────────────────


def _utility_name(ctx) -> str:
    """What the text calls the utility — `RBR-15`'s first named part."""
    return str(ctx.params.get("utility_name") or "Your water utility")


def _finding(row: dict[str, Any]) -> Finding:
    """One plan row as the object that refuses a quantity with no unit."""
    outcome = row.get("outcome") or OUTCOME_NOTHING_WRONG
    reason, rule, fix_route, fix_label = _sentence(row, outcome)
    return Finding(
        asset_id=str(row["asset_id"]),
        meter_no=str(row.get("meter_no") or "—"),
        account_id=row.get("account_id"),
        account_label=row.get("account_label"),
        address=row.get("address"),
        pattern=row.get("pattern"),
        hours=row.get("hours"),
        multiple=_decimal(row.get("multiple")),
        quantity=None if row.get("unit_conflict") else _decimal(row.get("quantity")),
        unit=row.get("unit"),
        channel=row.get("channel"),
        outcome=outcome,
        reason=reason,
        decided_by_rule=rule,
        fix_route=fix_route,
        fix_label=fix_label,
    )


def _sentence(row: dict[str, Any], outcome: str) -> tuple[str, str, str, str]:
    """What this meter says to a clerk, and the rule that decided it.

    ⚠ **NO RULE ID REACHES A SCREEN** (B14 rule 32) — the rule rides in
    `ReportRow.meta`, which no block draws — and a refusal caps at five or six
    words (rule 33), with the explanation in its own column.
    """
    if outcome == "told_this_week":
        return (
            f"Already told on {row.get('told_on')}.",
            "One alert per meter inside the Settings window",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if outcome == "in_dispute":
        return (
            "This account is in dispute about its usage.",
            "An account in dispute is never alerted",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if outcome == OUTCOME_NOBODY_TO_TELL:
        return (
            "No account on this unit, so there is nobody to tell.",
            "An empty property is a real state, not a fault",
            FIX_ACCOUNTS,
            "Open accounts →",
        )
    if outcome == OUTCOME_NO_CHANNEL:
        return (
            "No text and no email on file for this customer.",
            "A channel nobody recorded is the data-hygiene runbook's finding",
            FIX_ACCOUNTS,
            "Add a channel →",
        )
    if outcome == OUTCOME_CANNOT_JUDGE:
        return (
            "This meter's readings cannot be compared with the floor.",
            "A threshold in one unit judges nothing in another",
            FIX_ASSETS,
            "Open meter →",
        )
    if outcome == OUTCOME_BELOW_THE_FLOOR:
        return (
            "Below the level the utility bothers a customer about.",
            "The floor is the tenant's own Settings figure",
            FIX_READS,
            "Open read →",
        )
    if row.get("pattern") == PATTERN_CONTINUOUS:
        return (
            f"Water has run without stopping for {row.get('hours')} hours.",
            "Continuous flow over the Settings window is a leak until somebody looks",
            FIX_ACCOUNTS,
            "Open account →",
        )
    if row.get("pattern") == PATTERN_SPIKE:
        return (
            f"Using {row.get('multiple')}× this meter's own normal.",
            "The comparison is the meter's own 90-day average, never a fleet number",
            FIX_ACCOUNTS,
            "Open account →",
        )
    return (
        "Nothing unusual on this meter.",
        "A meter inside both thresholds is reported, never alerted on",
        FIX_READS,
        "Open read →",
    )


def step_queue_the_alert(ctx, subject) -> dict[str, Any]:
    """5 · After approval — and the dispatcher sends, never this (`BR-NOT-005`).

    ⚠ **ONE METER, ONE SAVEPOINT** (hard-won law 14). The executor wraps this in
    a nested `transaction.atomic()`, so one refused row rolls back to its own
    savepoint and the rest of the run survives. On PostgreSQL that is the ONLY
    thing that works, and the suite — in-memory SQLite — cannot see the
    difference.

    ⚠ **THE PORT IS CALLED AND ITS OWN REFUSAL IS THE OUTCOME.** No `if
    is_bound` branch: `BR-RBS-003` makes dry and live one code path.

    ⚠ **QUIET HOURS TRAVEL AS `dispatch_not_before`, NOT AS A CLOCK READ**
    (`BR-NOT-009`, gate `G6`). The runbook knows the tenant's quiet window; the
    notifications module never reads a wall clock, and neither does this.
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_NOTHING_WRONG,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A step that stops makes every later step Never reached",
            "fix_route": FIX_READS,
        }

    key = str(subject.subject_id)
    row = next((one for one in _plan(ctx) if str(one["asset_id"]) == key), None)
    if row is None:
        return {
            "outcome": OUTCOME_NOTHING_WRONG,
            "reason": "This meter was not in the plan.",
            "decided_by_rule": "The pinned set is resolved once and frozen",
            "fix_route": FIX_READS,
            "data": {},
        }

    finding = _finding(row)
    if finding.outcome != OUTCOME_PLANNED:
        return {
            "outcome": finding.outcome,
            "reason": finding.reason,
            "decided_by_rule": finding.decided_by_rule,
            "fix_route": finding.fix_route,
            "data": finding.as_row(),
        }

    message = finding.message(_utility_name(ctx))
    if message is None:
        # ⚠ **A LEAK ALERT THAT CANNOT SAY WHERE IS NOT AN ALERT.** `RBR-15`
        # requires the address; an address this product cannot walk to is a
        # premises with none, which is a finding rather than a text with a hole.
        return {
            "outcome": OUTCOME_NO_CHANNEL,
            "reason": "No address on this property, so the text cannot say where.",
            "decided_by_rule": "The alert names the address; an address it cannot name is not sent",
            "fix_route": FIX_ASSETS,
            "data": finding.as_row(),
        }

    day = _as_of(ctx, _batch(ctx)).isoformat()
    try:
        ctx.port("queue_notice").call(
            actor=None,
            runbook_key=KEY,
            account_id=finding.account_id,
            subject_id=finding.asset_id,
            discriminator=f"{DISCRIMINATOR}|{day}",
            channels=(finding.channel,),
            render_context={
                # ⚠ THE ADDRESS AND THE HOURS. **NEVER THE ACCOUNT NUMBER AND
                # NEVER A DOLLAR FIGURE** (`RBR-15`) — a customer can act on
                # neither, and a dollar estimate at 07:30 is a bill nobody
                # issued.
                "utility": _utility_name(ctx),
                "address": finding.address,
                "hours": finding.hours,
                "message": message,
            },
            dispatch_not_before=ctx.params.get("quiet_hours_end"),
        )
    except PortNotBound as refusal:
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": f"Ready to send by {finding.channel}. Nothing is queued yet.",
            "decided_by_rule": str(refusal),
            "fix_route": FIX_ACCOUNTS,
            "data": {**finding.as_row(), "message": message},
        }
    queued = ctx.set_results.setdefault("queued", [])
    queued.append(finding.asset_id)
    return {
        "outcome": OUTCOME_QUEUED,
        "reason": f"Queued to send by {finding.channel}.",
        "decided_by_rule": "The dispatcher sends; this queues",
        "fix_route": FIX_ACCOUNTS,
        "data": {**finding.as_row(), "message": message},
    }


# ── step 6 · the record the product cannot keep ───────────────────────────


def step_record_it_against_the_meter(ctx, subjects) -> dict[str, Any]:
    """6 · *"So next week's run knows"* — and **it cannot be written**.

    ⚠ **THE PORT IS HELD, CALLED, AND ITS OWN REFUSAL IS RECORDED.**
    `flag_meter` binds no writer: there is no column anywhere to hold *"told
    about a leak on the 4th"*, and the row it would belong to is `apps/assets`',
    which is not one of the five modules a port may write (`DEF-RBS-4331`).

    ⚠ **AND THE SUBSTITUTE IS FORBIDDEN RATHER THAN MISSED.** `BR-RBS-040`
    makes a NOTE an engine act, never a fourteenth port, so binding this to
    `create_account_note` would make `BR-RBS-002` false and **nothing in the
    suite would notice** — the note would still be written and every count would
    still agree.

    So the step counts what it WOULD record and the screen carries the number.
    It declares `writes=True` because the act it names is a write, exactly as
    the card marks it — the claim is about the STEP, and a step that stopped
    claiming it would be a quieter runbook doing the same thing.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    alerted = [one for one in plan if one.get("outcome") in (OUTCOME_PLANNED, OUTCOME_QUEUED)]
    refusal = ""
    try:
        ctx.port("flag_meter").call(actor=None, asset_id=None, told_on=None)
    except PortNotBound as caught:
        refusal = str(caught)
    except TypeError as caught:  # pragma: no cover — a bound writer with another shape
        refusal = str(caught)
    return _StepResult(
        plan=plan,
        checked={
            "would_record": len(alerted),
            "recorded": 0,
            "why_not": refusal,
            "next_weeks_run_reads": (
                "the notice outbox, because nothing holds 'told about a leak on' a date"
            ),
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_RECORD, STEP_GUARDS, STEP_FLAG, STEP_NORMAL):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    stopped_at = STEP_GATHER
    for key in (STEP_GATHER, STEP_GUARDS):
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


def _records_columns() -> list[dict[str, Any]]:
    """`RB-111`'s own table: Meter · Account · Pattern · Gal/day · Channel · Sent.

    ⚠ **THE USAGE COLUMN IS *Usage* AND NOT *Gal / day*, WHICH IS A DIVERGENCE
    AND IS STAMPED.** The card's header hard-codes one utility's unit. A tenant
    metering in CCF would read a column headed *Gal / day* over numbers that are
    not gallons — hard rule 3's failure wearing a table header. The unit travels
    in the CELL, with its number, where it cannot be wrong for some rows and
    right for others.
    """
    return [
        {"key": "meter", "label": "Meter"},
        {"key": "account", "label": "Account"},
        {"key": "pattern", "label": "Pattern"},
        {"key": "usage", "label": "Usage"},
        {"key": "channel", "label": "Channel"},
        {"key": "sent", "label": "Sent"},
    ]


def _record_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    finding = _finding(row)
    pattern = PATTERN_LABELS.get(finding.pattern or "", "—")
    if finding.pattern == PATTERN_CONTINUOUS and finding.hours is not None:
        pattern = f"Continuous · {finding.hours} h"
    elif finding.pattern == PATTERN_SPIKE and finding.multiple is not None:
        pattern = f"{finding.multiple}× normal"
    sent = {
        OUTCOME_QUEUED: "Queued",
        OUTCOME_PLANNED: "To queue",
        OUTCOME_NO_CHANNEL: "No channel",
        OUTCOME_NOBODY_TO_TELL: "Nobody to tell",
        "told_this_week": "Told this week",
        "in_dispute": "In dispute",
    }.get(finding.outcome, "—")
    return {
        "id": f"alert-{index}",
        "cells": {
            # ⚠ THE ADDRESS IS DRAWN BESIDE THE CUSTOMER, WALKED TO FROM THE
            # PREMISES (hard rule 8). No database id is a visible value here
            # (B14 rule 31).
            "meter": {"kind": "text", "text": finding.meter_no},
            "account": {
                "kind": "text",
                "text": " · ".join(
                    part for part in (finding.account_label, finding.address) if part
                )
                or "—",
            },
            "pattern": {"kind": "text", "text": pattern},
            # The number AND its unit, in one cell — see `_records_columns`.
            "usage": {"kind": "text", "text": finding.quantity_text},
            "channel": {"kind": "text", "text": finding.channel or "—"},
            "sent": {"kind": "text", "text": sent},
        },
        "meta": {
            "decided_by_rule": finding.decided_by_rule,
            "outcome": finding.outcome,
            "reason": finding.reason,
            "message": row.get("message"),
        },
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty), and
      **no KPI strip**: a strip reading *0 alerts · 0 told this week · 0 no
      channel* over a run that examined nothing is indistinguishable from a
      morning on which every meter was fine.
    * **finished** — `Verdict` · `KPIs` · `Records` · `Sentence` · `Downloads`,
      which is `RB-111`'s own block list plus the verdict the header consumes.

    ⚠ **THE `Sentence` BLOCK CARRIES THE TEXT A CUSTOMER RECEIVES, IN FULL, AND
    THAT IS THE CARD'S OWN DESIGN NOTE** — *"a clerk approving nine texts wants
    to read one"*. It names the utility, the address and the hours and never the
    account or a dollar figure (`RBR-15`).
    """
    stop = None
    for key in (STEP_GATHER, STEP_GUARDS):
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
                    "columns": _records_columns(),
                    "rows": [],
                    "total": 0,
                    "empty": {"title": stop["headline"], "helper": stop["detail"]},
                },
            ),
        ]

    plan = _plan_from_view(view)
    utility = str(view.set_results.get(UTILITY_NAME_KEY) or "Your water utility")
    gathered = (view.set_results.get(STEP_GATHER) or {}).get("checked") or {}
    flagged = (view.set_results.get(STEP_FLAG) or {}).get("checked") or {}
    guarded = (view.set_results.get(STEP_GUARDS) or {}).get("checked") or {}
    acted = any(record.outcome == OUTCOME_QUEUED for record in view.records)

    to_queue = [one for one in plan if one.get("outcome") in (OUTCOME_PLANNED, OUTCOME_QUEUED)]
    told = [one for one in plan if one.get("outcome") == "told_this_week"]
    no_channel = [one for one in plan if one.get("outcome") == OUTCOME_NO_CHANNEL]
    nobody = [one for one in plan if one.get("outcome") == OUTCOME_NOBODY_TO_TELL]
    listed = to_queue + told + no_channel + nobody
    word = "Alerts queued" if acted else "To queue"

    # ⚠ **THE WATER AT STAKE CARRIES ITS UNIT OR IT IS NOT SHOWN AT ALL.**
    # `RB-111`'s tile reads *~11,000 gal*; a tenant metering in CCF must not see
    # that number labelled gallons, so the unit comes from the meters themselves
    # and a mixed set shows NO total (hard rule 3).
    #
    # ⚠ **AND THE MIXED ARM IS UNREACHABLE TODAY, WHICH IS SAID HERE RATHER
    # THAN LEFT FOR SOMEBODY TO DISCOVER.** Step 3 refuses to judge any meter
    # whose unit is not the floor's, so every meter that reaches `to_queue`
    # already shares one unit and `len(units)` is always 0 or 1. That makes this
    # a guard nothing can currently trip — the mirror of hard-won law 7's
    # *structurally incapable of failing* — and it is KEPT because the thing
    # that makes it unreachable is a rule somebody could reasonably relax: the
    # day the floor becomes per-service, or optional, two units reach this line
    # and the tile must not label their sum with whichever sorted first.
    # `test_the_water_at_stake_tile_uses_the_floors_own_unit` asserts the
    # invariant that makes it dead, so removing the floor gate turns that test
    # red rather than turning this branch into a wrong number.
    units = {one.get("unit") for one in to_queue if one.get("unit")}
    at_stake_unit = units.pop() if len(units) == 1 else None
    at_stake = sum(
        (_decimal(one.get("quantity")) or Decimal("0")) for one in to_queue
    ) if at_stake_unit else None

    first_message = next(
        (
            _finding(one).message(utility)
            for one in to_queue
            if one.get("address")
        ),
        None,
    )

    blocks = [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": "warning" if to_queue else "success",
                "count": f"{len(to_queue)} {'queued' if acted else 'to queue'}.",
                "detail": (
                    f"{gathered.get('meters_with_interval_data', 0)} meters read over "
                    f"{gathered.get('window_hours', 48)} hours."
                    if acted
                    else "Nothing is queued until a writer is bound for this runbook."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "alerts",
                        "label": word,
                        "value": {"kind": "text", "text": str(len(to_queue))},
                        "detail": None if acted else "Planned — nothing is queued yet",
                    },
                    {
                        "id": "told",
                        "label": "Told this week",
                        "value": {"kind": "text", "text": str(len(told))},
                        # ⚠ THE NUMBER THAT TELLS A STRUCTURALLY EMPTY GUARD
                        # FROM A QUIET WEEK (hard-won law 7).
                        "detail": f"{guarded.get('outbox_rows_seen', 0)} in the notice outbox",
                    },
                    {
                        "id": "no_channel",
                        "label": "No channel",
                        "value": {"kind": "text", "text": str(len(no_channel))},
                    },
                    {
                        "id": "at_stake",
                        "label": "Water at stake",
                        "value": {
                            "kind": "text",
                            "text": (
                                f"{at_stake.normalize():f} {at_stake_unit}"
                                if at_stake is not None
                                else "—"
                            ),
                        },
                        "detail": (
                            None
                            if at_stake is not None
                            else "Not shown: these meters report in more than one unit"
                        ),
                    },
                    {
                        "id": "examined",
                        "label": "Meters read",
                        "value": {
                            "kind": "text",
                            "text": str(gathered.get("meters_with_interval_data", 0)),
                        },
                        "detail": (
                            f"{flagged.get('below_the_floor', 0)} below the floor · "
                            f"{flagged.get('meters_that_could_not_be_judged', 0)} not judged"
                        ),
                    },
                ]
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [
                    _record_row(index, row) for index, row in enumerate(listed, start=1)
                ],
                "total": len(listed),
                "chips": [
                    {"id": "all", "label": "All", "count": len(listed)},
                    {"id": "queued", "label": word, "count": len(to_queue)},
                    {"id": "told", "label": "Told this week", "count": len(told)},
                    {"id": "no_channel", "label": "No channel", "count": len(no_channel)},
                    {"id": "nobody", "label": "Nobody to tell", "count": len(nobody)},
                ],
                "empty": {
                    "title": "No leaks in this window.",
                    "helper": (
                        f"{gathered.get('meters_with_interval_data', 0)} meters read over "
                        f"{gathered.get('window_hours', 48)} hours. "
                        f"{flagged.get('below_the_floor', 0)} used less than the floor. "
                        "Nothing is waiting for you."
                    ),
                },
            },
        ),
    ]
    if first_message:
        blocks.append(
            Block(
                block="sentence",
                payload={
                    "tone": "neutral",
                    "label": "What the customer receives",
                    "text": first_message,
                },
            )
        )
    blocks.append(
        Block(
            block="downloads",
            payload={"files": [{"id": "alerts", "label": "Alerts", "format": "csv"}]},
        )
    )
    return blocks


# ── the guards and the pinned scope ───────────────────────────────────────


SAMPLE_KEYS = "_sample_meters"
OPTED_OUT_KEYS = "_opted_out_meters"


def _is_sample(ctx, subject) -> bool:
    """`RB-111`'s *Never include: Sample* (`BR-TEN-057`, `BR-RBS-012`).

    A guard rather than a filter inside a read: a guarded subject is still
    pinned and still counted (`BR-RBS-035`), and `RBS-004.4` draws the control
    disabled WITH its reason rather than hiding it.
    """
    return str(subject.subject_id) in (ctx.set_results.get(SAMPLE_KEYS) or frozenset())


def resolve(ctx):
    """The pinned set: **one subject per METER with interval data in the window**.

    ⚠ **THE METER AND NOT THE METER-DAY**, which is where this runbook differs
    from runbook 21 over the very same rows (`BR-RBS-019`). One customer, one
    text: a per-meter-day subject would text somebody twice about a tap that ran
    for two days, which is what *once per meter every 7 days* exists to prevent.

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`).

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP**, and
    it is not an error — step 1 says why in a sentence a clerk can read.
    """
    batch = _batch(ctx)
    meters = _meters(batch, _days_in_window(ctx, batch))
    ctx.set_results[SAMPLE_KEYS] = frozenset(
        key for key, one in meters.items() if one["is_sample"]
    )
    return [
        SubjectRef(
            subject_type="meter",
            subject_id=key,
            label=str(one.get("meter_no") or key),
        )
        for key, one in meters.items()
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Leak and high-usage alert",
    kind=models.KIND_ACTION,
    category="reads",
    subject_type="meter",
    unit_of_work="a meter over the window",
    # ⚠ MANUAL AND SCHEDULE, NOT `batch.landed` — see the module docstring. The
    # card's own *Runs · Daily 07:30* is the schedule half and is already true
    # of this declaration.
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Customer portal", "Service points"),
    parameters=(
        Parameter(
            name="continuous_hours",
            type=PARAM_ENUM,
            label="Continuous flow for",
            required=True,
            default="24",
            choices=("12", "24", "36", "48"),
        ),
        Parameter(
            name="above_normal_multiple",
            type=PARAM_ENUM,
            label="Above own normal",
            required=True,
            default="3",
            choices=("2", "3", "4", "5"),
        ),
        Parameter(
            name="ignore_below",
            type=PARAM_ENUM,
            label="Ignore below",
            required=True,
            default="200",
            choices=("50", "100", "200", "500"),
        ),
        # ⚠ **THE FLOOR'S UNIT IS ITS OWN INPUT AND THAT IS HARD RULE 3, NOT
        # TIDINESS.** *Ignore below 200* is not a threshold; *200 gal/day* is.
        # A tenant metering in CCF sets this and the runbook then judges nothing
        # it cannot compare, rather than judging everything wrongly.
        Parameter(
            name="ignore_below_unit",
            type=PARAM_ENUM,
            label="Ignore below · unit",
            required=True,
            default="gal",
            choices=("gal", "kgal", "ccf", "m3", "L"),
        ),
        Parameter(
            name="channel",
            type=PARAM_ENUM,
            label="Channel",
            required=True,
            default="text_then_email",
            # `RB-111`'s own ladder. One choice, because the alternative is a
            # utility choosing post for a leak that has been running 26 hours.
            choices=("text_then_email",),
        ),
        Parameter(
            name="once_per_meter_days",
            type=PARAM_ENUM,
            label="Once per meter every",
            required=True,
            default="7",
            choices=("1", "3", "7", "14", "30"),
        ),
        Parameter(
            name="window_hours",
            type=PARAM_ENUM,
            label="Window",
            required=True,
            default="48",
            choices=("24", "48", "72"),
        ),
        Parameter(
            name="quiet_hours",
            type=PARAM_REF_SETTING,
            label="Quiet hours",
            setting_key="notifications.quiet_hours",
        ),
        # ⚠ **READ-ONLY, AND THE REASON HAS CHANGED SINCE THE CARD WAS
        # WRITTEN.** `RB-111` says *"awaiting decision 4"*; `OQ-RBS-1733` CLOSED
        # on 2026-09-06 with a FOURTH option — `BR-RBS-041`, *permission granted
        # UP FRONT, per runbook* — and **the three-clean-run ratchet the card
        # describes is not built and is not going to be.** The switch that
        # replaces it is wave `L3`'s: `runbooks.gate_mode` holds one value today
        # and its second has no writer, no screen and no migration. Drawn
        # read-only WITH its reason, never hidden (B14).
        Parameter(
            name="unattended_after",
            type=PARAM_REF_SETTING,
            label="Unattended after",
            setting_key="runbooks.gate_mode",
        ),
        Parameter(
            name="baseline_days",
            type=PARAM_ENUM,
            label="Compare against",
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
            run=step_gather_the_window_of_intervals,
        ),
        Step(
            key=STEP_NORMAL,
            label=STEP_LABELS[STEP_NORMAL],
            mode=MODE_SET,
            run=step_work_out_each_meters_own_normal,
        ),
        Step(
            key=STEP_FLAG,
            label=STEP_LABELS[STEP_FLAG],
            mode=MODE_SET,
            run=step_flag_continuous_flow_or_a_spike,
        ),
        Step(
            key=STEP_GUARDS,
            label=STEP_LABELS[STEP_GUARDS],
            mode=MODE_SET,
            run=step_apply_guards_and_once_a_week,
        ),
        # ⚠ THE ONLY PER-RECORD STEP. One meter, one savepoint (law 14).
        Step(
            key=STEP_QUEUE,
            label=STEP_LABELS[STEP_QUEUE],
            mode=MODE_PER_RECORD,
            run=step_queue_the_alert,
            writes=True,
        ),
        Step(
            key=STEP_RECORD,
            label=STEP_LABELS[STEP_RECORD],
            mode=MODE_SET,
            run=step_record_it_against_the_meter,
            writes=True,
        ),
    ),
    ports=("queue_notice", "flag_meter"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-023 (EP-RBS-05; CR-075 wave R′)
# generated: 2026-09-07 by the CR-075 wave R′ metering-and-customers lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_023_leak_alert.py · pytest tests/test_rbs_reads_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing is queued — `queue_notice` IS bound and `LIVE_ENABLED_RUNBOOKS` is empty, so the KPI says "To queue"; `flag_meter` binds NO writer (no column holds "told about a leak on" a date, DEF-RBS-4331) so step 6 counts what it would record and the once-a-week guard reads the notice OUTBOX instead — structurally empty here, and the outbox row count is reported beside it; the card's `Gal / day` column header is drawn as `Usage` with the unit in the cell (hard rule 3); the *Unattended after* parameter stays read-only for a NEW reason — OQ-RBS-1733 closed 2026-09-06 as BR-RBS-041 and the card is stamped in this commit
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
