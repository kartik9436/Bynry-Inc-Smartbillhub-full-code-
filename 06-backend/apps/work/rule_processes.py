# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.30 (every process in the rule
#           form, served ONCE), P3.31 (`DEF-WRK-4096`: a rule stamps the label
#           the order table accepts), P3.32 (two new overnight readers), P3.33
#           (`DEF-WRK-4097`: continuous flow takes a service and a unit), P3.34
#           (six screen moments), P3.35 (the failed-job retry), P3.65 (several
#           triggers on one rule). Images 56, 57, 61, 62.
# Rules:    BR-WRK-033 (a rule raises without a person) · BR-WRK-024 (the source
#           stamp is `work_orders.source`'s own vocabulary) · BR-WRK-055 (a
#           screen moment's *No visit needed* is a recorded choice) · BR-WRK-054
#           (a failed job's retry raises itself) · BR-PAY-036 (a payment alone
#           never books a reconnection) · BR-MET-027 (the estimate limit is
#           Meter-read settings' own figure) · CLAUDE.md hard rule 3 (a
#           consumption figure carries its unit) · PO ruling 10 of 24 Sep
#           (*"every process should be able to set from the form"*) · the PO's
#           26 Sep ruling (*several triggers, any of them raises the job*)
# Tests:    06-backend/tests/test_cr168_srv4_rules.py ·
#           06-backend/tests/test_cr168_srv4_rules_pg.py (PostgreSQL)
# ───────────────────────────────────────────────────────
"""The processes a Work rule can be set on — ONE list, served once.

⚠ **WHY THIS FILE EXISTS: TWO VOCABULARIES THAT HAD TO AGREE AND DID NOT
(`DEF-WRK-4096`).** Until round 5 a rule stamped its MODULE (`payments`,
`billing`, `reads`, `accounts`) as the order's `source`, and the order table
accepts a different list — `metering.connections.WORK_ORDER_SOURCES`. Only
`assets` was spelled the same in both, by coincidence, so four of five
triggers were refused at the raise and the sweep reported `raised: 0` looking
healthy (98 leak subjects, 0 jobs). And the one that worked stamped the label
for the Assets DOOR rather than `asset_age_rule`.

**So a process's KEY IS the label the job reads.** There is no mapping table
between a "trigger" and a "source": `dunning_auto` is both what the supervisor
picks and what `Raised by` prints, and a test reads every key against
`WORK_ORDER_SOURCES` so a process the order table would refuse cannot be added
here at all.

THE THREE WAYS A PROCESS ACTS (the blueprint's ruling 10 table, decided there)
────────────────────────────────────────────────────────────────────────────
* **overnight** — no clerk is standing in the moment (a notice expiring, a
  reading run, an asset's date): the nightly sweep reads it and raises.
  `BR-WRK-033` as signed.
* **screen** — a clerk IS standing in it and the screen already offers the job
  (`BR-WRK-055`: *No visit needed* is a recorded choice). The rule's job
  arrives TICKED on that screen with the rule's name; nothing is raised
  overnight, so a clerk's untick is never overridden.
* **retry** — the product already raises the job by signed rule (`BR-WRK-054`);
  the rule shapes it (priority, assignee), never a second job.
* **arrival** — added 2026-10-22 (`BR-WRK-067`): a route finding reaches the
  server and a rule for its kind raises the job THEN, once per finding. With
  no rule nothing is raised; a person raises it by hand from the finding.

⚠ **TWELVE, NOT THIRTEEN — THE ROUTED SERVICE REQUEST IS NOT A MOMENT ANY MORE
(our reading of a PO ruling, recorded in the decision log; `DEF-WRK-9623`).**
Ruling 10 counted thirteen on 24 Sep against build `2.340.0`. The PO retired
the *route* action on 2026-09-19 (*"once requets is approved then in move in or
new connect we take all those decision"*, `customers/service_request.py`
`RETIRED_ACTIONS`); an approved request now raises a CHILD move-in or new
connection, and that child is the moment. A rule on *a service request is
routed* could never fire, and offering it would put a row on the form that
does nothing — hard-won law 2's mirror. A rule on *a customer moves in* or *a
new connection is built* covers the approved request, through its child.

⚠ **A PAYMENT ALONE NEVER BOOKS A RECONNECTION** (`BR-PAY-036`, CONFIRMED). The
reconnection process is the clerk's reconnect act, on screen; there is no
`payment_received` process, and that token stays the order table's for a
human-raised job only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.work.route_finding_models import FINDING_KINDS

#: The three ways a process acts. See the module docstring.
MOMENT_OVERNIGHT = "overnight"
MOMENT_SCREEN = "screen"
MOMENT_RETRY = "retry"
#: ⚠ **A FOURTH, `BR-WRK-067` (PO 2026-10-22): *"if a rule is set work order
#: will get created , if not user can create the work order"*.** A route
#: finding ARRIVES — nobody is standing in a screen that offers a job, and
#: waiting for 02:00 would leave a leak running all day. So the rule acts the
#: moment the finding reaches the server (`route_findings.receive`), once per
#: finding, and never overnight: the sweep has no reader for it, by design.
MOMENT_ARRIVAL = "arrival"

#: The modules a process belongs to. DERIVED from the process, never picked
#: (P3.30): the form cannot compose a module/trigger pair the server refuses.
MODULE_PAYMENTS = "payments"
MODULE_BILLING = "billing"
MODULE_ASSETS = "assets"
MODULE_READS = "reads"
MODULE_ACCOUNTS = "accounts"
MODULE_PREMISES = "premises"
MODULE_WORK = "work"

#: What each param is, so the form draws the right control and the server
#: validates the same thing. `setting` is READ-ONLY — a figure owned by another
#: settings screen, shown and never copied onto the rule (P3.32: *"two figures
#: would let estimating stop at 2 while the rule waits for 3"*).
PARAM_INT = "int"
PARAM_BOOL = "bool"
PARAM_ASSET_TYPES = "asset_types"
PARAM_SERVICE = "service"
PARAM_QUANTITY = "quantity"
PARAM_UNIT = "unit"
PARAM_SETTING = "setting"
#: One value from a CLOSED list the server serves with the param (`options`),
#: each with its own catalogue key — the form draws a picker and types no
#: literal, and the save refuses a value the list does not hold.
PARAM_CHOICE = "choice"


@dataclass(frozen=True)
class Param:
    name: str
    kind: str
    default: Any = None
    required: bool = False
    minimum: int | None = None
    #: For a `quantity`: the name of the sibling param that carries its unit
    #: (hard rule 3 — a usage figure is never a bare number).
    unit_param: str | None = None
    #: For a `choice`: the values it may hold, and the catalogue prefix each
    #: value's word lives under (`<prefix>.<value>`).
    options: tuple[str, ...] = ()
    option_key_prefix: str | None = None

    def as_wire(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "default": self.default,
            "required": self.required,
            "label_key": f"work.rules.param.{self.name}",
        }
        if self.minimum is not None:
            out["minimum"] = self.minimum
        if self.unit_param:
            out["unit_param"] = self.unit_param
        if self.options:
            out["options"] = [
                {"value": value, "label_key": f"{self.option_key_prefix}.{value}"}
                for value in self.options
            ]
        return out


@dataclass(frozen=True)
class Process:
    #: THE label the job reads — a `WORK_ORDER_SOURCES` token, nothing else.
    key: str
    module: str
    moment: str
    #: English for the terminal and the log; the screen translates `label_key`.
    label: str
    params: tuple[Param, ...] = field(default_factory=tuple)
    #: The CR-070 wave M `trigger_kind` this process was called before round 5.
    #: Read so the five rules every tenant already holds keep working; never
    #: written for a new rule.
    legacy_trigger: str | None = None

    def as_wire(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "label_key": f"work.rules.process.{self.key}",
            "module": self.module,
            "module_label_key": f"work.rules.module.{self.module}",
            #: What `Raised by` reads on a job this process raised — the key
            #: itself, in `work.orders.source.*` (one vocabulary, `DEF-WRK-4096`).
            "source_label": self.key,
            "moment": self.moment,
            "params": [param.as_wire() for param in self.params],
        }


#: ⚠ THE ORDER IS THE FORM'S ORDER — grouped by module, as ruling 10's table
#: lists them. Change it and the form's list changes with it; nothing else
#: spells this list (`RuleBuilder.tsx`'s literal is retired by lane RULES).
PROCESSES: tuple[Process, ...] = (
    Process(
        key="dunning_auto",
        module=MODULE_PAYMENTS,
        moment=MOMENT_OVERNIGHT,
        label="A final notice expires unpaid",
        params=(Param("grace_days", PARAM_INT, default=2, minimum=0),),
        legacy_trigger="final_notice_expired_unpaid",
    ),
    Process(
        key="billing_exception",
        module=MODULE_BILLING,
        moment=MOMENT_OVERNIGHT,
        label="A billing exception stays open",
        params=(Param("retryable", PARAM_BOOL, default=False),),
        legacy_trigger="billing_exception_unresolved",
    ),
    Process(
        key="asset_age_rule",
        module=MODULE_ASSETS,
        moment=MOMENT_OVERNIGHT,
        label="An asset passes its certification",
        params=(Param("asset_type_ids", PARAM_ASSET_TYPES, default=[]),),
        legacy_trigger="asset_past_certification_life",
    ),
    Process(
        key="compliance_calendar",
        module=MODULE_ASSETS,
        moment=MOMENT_OVERNIGHT,
        label="An asset's certification is due soon",
        params=(
            Param("asset_type_ids", PARAM_ASSET_TYPES, default=[]),
            # REQUIRED and no default: the drawing's *30* is an illustration
            # (B14 rule 37) and a lead time is the supervisor's to state.
            Param("days_ahead", PARAM_INT, required=True, minimum=1),
        ),
    ),
    Process(
        key="high_usage_alert",
        module=MODULE_READS,
        moment=MOMENT_OVERNIGHT,
        label="A meter shows continuous flow",
        params=(
            # REQUIRED (P3.33, `DEF-WRK-4097`): with no service the reader took
            # every meter and an electric one, which shows use every period,
            # read as a leak — 51 of the demo's 98 subjects.
            Param("service", PARAM_SERVICE, required=True),
            Param("consecutive_reads", PARAM_INT, default=3, minimum=1),
            Param("minimum_consumption", PARAM_QUANTITY, default="0", unit_param="unit"),
            # Hard rule 3: the minimum is compared only with readings in THIS
            # unit; a reading in another unit breaks the run, never converts.
            Param("unit", PARAM_UNIT, required=True),
        ),
        legacy_trigger="continuous_flow_alarm",
    ),
    Process(
        key="meter_read",
        module=MODULE_READS,
        moment=MOMENT_OVERNIGHT,
        label="A meter reaches its estimate limit",
        # READ-ONLY: Meter-read settings' own `est_max_consecutive`
        # (`BR-MET-027`), served beside the process so the form can show it.
        params=(Param("est_max_consecutive", PARAM_SETTING),),
    ),
    Process(
        key="move_in",
        module=MODULE_ACCOUNTS,
        moment=MOMENT_SCREEN,
        label="A customer moves in",
        # Was an OVERNIGHT trigger (`occupancy_completed`) that never raised a
        # job (`DEF-WRK-4096`); overnight it would have added a second visit to
        # a move-in whose clerk had already raised one or chosen *No visit
        # needed*. Ruling 10 moves it to the screen.
        legacy_trigger="occupancy_completed",
    ),
    Process(
        key="move_out",
        module=MODULE_ACCOUNTS,
        moment=MOMENT_SCREEN,
        label="A customer moves out",
    ),
    Process(
        key="transfer",
        module=MODULE_ACCOUNTS,
        moment=MOMENT_SCREEN,
        label="An account is transferred",
    ),
    Process(
        key="reconnect",
        module=MODULE_ACCOUNTS,
        moment=MOMENT_SCREEN,
        label="A paid account awaits reconnection",
    ),
    Process(
        key="new_connect",
        module=MODULE_PREMISES,
        moment=MOMENT_SCREEN,
        label="A new connection is built",
    ),
    Process(
        key="failed_outcome",
        module=MODULE_WORK,
        moment=MOMENT_RETRY,
        label="A job is accepted as failed",
    ),
    # ── `BR-WRK-067` (PO 2026-10-22) — a finding on a meter route ───────────
    # ONE process with the finding kind as its setting, not seven processes: a
    # utility writes *Leak → Leak repair, Same day* and *Broken seal → Seal
    # check* as two rules on one process, and the job's `source` is the same
    # word for both. The kind is REQUIRED — a rule on *any finding* would turn
    # every report into a job and leave nothing for a person to decide, which
    # is the half of the ruling that reads *"if not user can create the work
    # order"*.
    Process(
        key="route_finding",
        module=MODULE_READS,
        moment=MOMENT_ARRIVAL,
        label="A reader reports a route finding",
        params=(
            Param(
                "finding_kind",
                PARAM_CHOICE,
                required=True,
                options=FINDING_KINDS,
                option_key_prefix="work.findings.kind",
            ),
        ),
    ),
)

BY_KEY: dict[str, Process] = {process.key: process for process in PROCESSES}

#: CR-070 wave M's five trigger names → the process each one always meant.
LEGACY_TRIGGERS: dict[str, str] = {
    process.legacy_trigger: process.key for process in PROCESSES if process.legacy_trigger
}

#: The keys whose job the nightly sweep raises.
OVERNIGHT_KEYS: frozenset[str] = frozenset(
    process.key for process in PROCESSES if process.moment == MOMENT_OVERNIGHT
)
SCREEN_KEYS: frozenset[str] = frozenset(
    process.key for process in PROCESSES if process.moment == MOMENT_SCREEN
)
#: The keys whose rule acts when a record ARRIVES (`BR-WRK-067`).
ARRIVAL_KEYS: frozenset[str] = frozenset(
    process.key for process in PROCESSES if process.moment == MOMENT_ARRIVAL
)


def process_key(kind: Any) -> str | None:
    """A process key from either spelling — the round-5 key, or the wave M
    trigger name a rule written before round 5 still carries. None when it is
    neither, which the save refuses and the sweep logs."""
    text = str(kind or "").strip()
    if text in BY_KEY:
        return text
    return LEGACY_TRIGGERS.get(text)


def process(kind: Any) -> Process | None:
    key = process_key(kind)
    return BY_KEY.get(key) if key else None


def module_of(kind: Any) -> str | None:
    found = process(kind)
    return found.module if found else None


__all__ = [
    "ARRIVAL_KEYS",
    "BY_KEY",
    "LEGACY_TRIGGERS",
    "MOMENT_ARRIVAL",
    "MOMENT_OVERNIGHT",
    "MOMENT_RETRY",
    "MOMENT_SCREEN",
    "OVERNIGHT_KEYS",
    "PROCESSES",
    "SCREEN_KEYS",
    "Param",
    "Process",
    "module_of",
    "process",
    "process_key",
]
