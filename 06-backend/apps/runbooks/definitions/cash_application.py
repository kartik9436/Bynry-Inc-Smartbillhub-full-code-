# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-022 · US-RBS-017 (EP-RBS-05) — CR-075 wave P: runbook 10,
#           *Cash application* — seven steps over the payments a person
#           uploaded, five read and two write.
# Rules:    BR-RBS-004 (an Action always produces a PLAN first; there is no
#           route that acts without one) · BR-RBS-002 (a Check is constructed
#           with no writer — this is an Action and holds two named ports) ·
#           BR-RBS-005 / BR-RBS-018 (a money-bearing action carries a SECOND
#           approval, and the approval must match the plan as it stands) ·
#           BR-RBS-041 (permission granted up front removes the WAIT, never the
#           plan) · BR-RBS-009 (scope resolved ONCE and pinned) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read) · BR-RBS-011 (a failure names its fix route) · BR-RBS-019 (the
#           declared unit of work) · BR-RBS-020 (the report is composed at close
#           and frozen) · BR-RBS-021 (twelve blocks) · BR-RBS-022 (a write is a
#           named port) · BR-RBS-023 (a step declares its mode) · BR-RBS-027 (a
#           stopped run reads *Never reached* on every later step) ·
#           BR-RBS-039 (every foreign read through a seam this module owns) ·
#           RBR-14 (a duplicate payment is HELD, never rejected) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 shown, CHAR(3), never a
#           float) · hard rule 4 (a payment row is append-only) · hard rule 7
#           (every money action writes audit_log — the ENGINE's, BR-RBS-015) ·
#           hard-won law 14 (a savepoint is the only option on PostgreSQL) ·
#           B14 rules 31 and 32
# Tests:    06-backend/tests/test_us_rbs_022_cash_application.py ·
#           06-backend/tests/test_rbs_money_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/payments_seam.py ·
#           apps/runbooks/seams/integrations_seam.py ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-110-cash-application.md
# ───────────────────────────────────────────────────────
"""Runbook 10 — **Cash application**.

A clerk uploads a day's payments. This finds the account each one belongs to,
plans the application in the allocation order, and **states plainly which ones
it could not place and why** — so nobody tallies 138 cheques against 72 accounts
by hand. That sentence is the deliverable, in the Product Owner's own words of
2026-09-06: *"runbook will do the chekcking and tell what all is missing so that
clark dont have to search and tally manually"*.

WHO STARTS IT, AND WHY THAT IS NOT THE EVENT THE CARD NAMES
------------------------------------------------------------
`RB-110`'s trigger row reads ⚡ `batch.landed`. **A person starts this runbook,
and the event is a later refinement** — PO ruling 2026-09-06, verbatim: *"see
here runbook cannot annouce the checks are arrive, it is human who will collect
it and uplaod in system"*. `batch.landed` is not emitted by anything
(`CR-069`), and `models.py` already rules that *"a runbook whose only trigger is
an unbuilt event is not runnable, and a screen must SAY so rather than offering
a Run ▶ that refuses"*. So this declares **manual and schedule**, both of which
wait on nothing, and the event joins them the day it exists. The card's own
`Runs · Daily 06:30` is the schedule half and is already true of this
declaration.

"NO CONNECTION" IS AN ANSWER, AND IT IS STEP 1
-----------------------------------------------
PO ruling the same day: *"in absence of API conenctions you will not find
anything and you can stop the job saying APi or conenct not available; that is a
valid case and state for us"*. **Step 1 asks where today's work comes from and
there are two doors** — a live payment-provider connection, and a file somebody
uploaded. When BOTH are shut the run **STOPS** (`RUN_STATUS_STOPPED`): the chain
draws one red cell naming what is missing and six cells honestly reading *Never
reached* (`BR-RBS-027`, `Chain.tsx`'s `notReached`). That is a designed answer,
not a crash and not an exception path.

⚠ **IT IS NOT A CONNECTION CHECK ALONE, AND THAT DISTINCTION IS THE WHOLE
POINT.** A clerk who has just uploaded a lockbox file does not need to be told
the lockbox API is not wired up — the work is in front of them. Reporting *"no
connection"* over a file somebody is waiting on would be a refusal nobody
deserved, and it is exactly the shape both of the Product Owner's corrections
that day were aimed at.

WHAT IT PLANS AND WHAT IT ACTUALLY DOES TODAY, STATED RATHER THAN IMPLIED
--------------------------------------------------------------------------
**Nothing is applied.** Two independent facts stop it, both deliberate, and each
is reported on the screen rather than left for a reader to work out:

1. **The second approval.** `BR-RBS-018`, CONFIRMED 2026-09-06 with `OQ-RBS-1732`
   closed on the PO's own words — *"every money action, no threshold"*. Cash
   application applies money, so every run of it needs a second person, whatever
   the amount. Step 6 reads `runbook_runs.approved_by` **and**
   `approved_count`: approving *"129 to apply"* and acting on 140 is the failure
   `BR-RBS-005` exists to refuse, so an approval that does not match the plan as
   it stands is treated as no approval at all.
2. **No writer is bound.** `apply_payment` and `queue_receipt` are two of the
   thirteen ports and **`CR-075` wave `L2` binds them**; until then
   `PortDeclaration.call` raises `PortNotBound`, which is the shipped behaviour
   of the dry half rather than a gap.

⚠ **THE PORT IS CALLED ANYWAY, AND THE REFUSAL IS CAUGHT — THERE IS NO
`if is_bound` BRANCH HERE.** `BR-RBS-003` says dry and live are ONE code path
differing only in whether the writer is bound; a branch on `is_bound` would be a
second path that proves nothing about the first. So step 6 calls the port on
every payment it planned and records the port's OWN refusal as the outcome. When
`L2` binds a writer, this line applies money for real with nothing else changed.

⚠ **CATCHING `PortNotBound` IS NOT HARD-WON LAW 14's TRAP.** That law is about
catching a **database** error and carrying on — on PostgreSQL the transaction is
already aborted and every later statement is lost at COMMIT. `PortNotBound` is
raised **before any SQL is issued**, so nothing is poisoned; and each record
runs inside the executor's own nested `transaction.atomic()` savepoint in any
case, which is what makes a genuine refusal survivable too.

THE FOUR PLACES THIS DIVERGES FROM `RB-110` AND ITS FRAME, EACH STAMPED
------------------------------------------------------------------------
`RB-110` and `RBS-006-R10` are the acceptance check. Where this departs, the
reason is written here rather than left for a reader to spot:

1. **The KPI strip and the by-source table say *To apply* while nothing is
   applied.** The frame's words — *Applied*, *Applied value* — are the words for
   a run that applied. A tile reading **129 Applied** over a run that applied
   nothing is the single most dangerous sentence this screen could print, and
   `ReportColumn.label` and `KpisPayload.tiles[].label` are both server-supplied,
   so the honest word costs nothing. The frame's words return the moment a
   writer is bound and a second person approves.
2. **The chain is drawn only when the run STOPPED.** The frame has seven regions
   and no chain, because it draws a run that finished. A stopped run is a state
   the frame does not cover at all, and the chain is the only block that can say
   *this step never ran* (`BR-RBS-027`). Adding it to a finished run would be a
   region the sheet does not have.
3. **The by-source table lists the sources that actually landed.** The frame
   shows Lockbox · Bank file · Portal · Kiosk. In this product an uploaded
   remittance batch carries `source_kind` `lockbox` or `csv` and nothing else —
   Portal and Kiosk are TENDERS on a recorded payment, not files anybody
   uploads. A table with two permanently empty rows would be four rows of which
   two are decoration; the frame's four are its illustration.
4. **`Most per run` is not a parameter here.** The cap is a column on the
   runbook row (`runbooks.cap`), it REFUSES the run rather than truncating it
   (`BR-RBS-006`), and `OQ-RBS-1731` closed on 2026-09-06 with the default at
   **100**. A parameter of the same name would be a second copy of one policy,
   which is `RBR-03` exactly.

WHAT WOULD MAKE THIS RUNBOOK REPORT WRONGLY, ANSWERED IN WRITING
-----------------------------------------------------------------
Hard-won law 7's second habit. **A run that examined nothing and a run that
found nothing wrong must not read the same.** So every step returns a `checked`
mapping saying how many things it looked at, the KPI strip draws the landed
count beside the planned count, and a step that could not answer a half of its
card question names that half in `checked` rather than staying silent — step 5
does, for every account whose books would not open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.boundary import PortNotBound
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    PARAM_DAYS,
    PARAM_ENUM,
    PARAM_MONEY,
    PARAM_REF_OBJECT,
    PARAM_REF_SETTING,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.definitions import _money_gate
from apps.runbooks.seams import integrations_seam, payments_seam, tenancy_seam

KEY = "cash_application"

# ── the two doors work arrives through ────────────────────────────────────
#
# The four payment-provider manifests, verified against
# `06-backend/apps/integrations/manifests/` on 2026-09-06 and named as VALUES
# rather than imported: a manifest key crossing the seam is data, and importing
# `apps.integrations.manifests` is exactly what `G115` refuses (`BR-RBS-039`).
# ⚠ `payments_card` — one generic card — BECAME FIVE NAMED PROCESSORS in
# `CR-110-BRC04` (blueprint p162: *"replaced by five named processors"*). The
# four keys became eight. Nothing about what this runbook DOES changed.
PAYMENT_PROVIDER_KEYS = (
    "bank_lockbox_file",
    "pay_invoicecloud",
    "pay_paymentus",
    "pay_uspayments",
    "pay_worldpay",
    "pay_globalpayments",
    "payments_kiosk",
    "payments_sandbox",
)

#: What a clerk calls the file a batch came in as. `source_kind` is TEXT and not
#: an enum on purpose (*"which channels a utility uses is deployment reality"*),
#: so an unknown word is title-cased rather than dropped — a source this map has
#: never seen must still appear in the by-source table.
SOURCE_LABELS = {
    "lockbox": "Lockbox",
    "csv": "Bank file",
    "portal": "Portal",
    "kiosk": "Kiosk",
}

# ── the outcomes one payment can reach ────────────────────────────────────
#
# ⚠ **`planned` IS NOT `skipped`.** A planned payment is one this run WOULD
# apply and did not, and the difference between the two words is the difference
# between *"waiting for you"* and *"nothing to do"*. `BR-RBS-035` counts every
# outcome, including the ones with no record row, so a word that collapsed two
# meanings would make the totals unreadable.
OUTCOME_APPLIED = "applied"
OUTCOME_PLANNED = "planned"
OUTCOME_NEEDS_A_PERSON = "needs_a_person"
OUTCOME_DUPLICATE_HELD = "duplicate_held"
OUTCOME_SKIPPED = "skipped"

# ── the steps, in the card's own order ────────────────────────────────────

STEP_SOURCE = "where_the_work_comes_from"
STEP_BY_ACCOUNT = "match_by_account_number"
STEP_BY_REMITTANCE = "match_by_remittance_then_name"
STEP_DUPLICATES = "check_for_a_duplicate"
STEP_BALANCE = "check_the_amount_against_the_balance"
STEP_APPLY = "apply_by_allocation_order"
STEP_RECEIPTS = "record_and_queue_receipts"

#: The chain draws one cell per step in this order, and a clerk reads the words
#: rather than the keys. Step 1's label is the card's *"Gather today's landed
#: payments"* said the way the ruling of 2026-09-06 makes true: a person brings
#: the work, or a connection does, and the step's job is to say which.
STEP_LABELS = {
    STEP_SOURCE: "Where today's work comes from",
    STEP_BY_ACCOUNT: "Match by account number",
    STEP_BY_REMITTANCE: "Match by remittance id, then name",
    STEP_DUPLICATES: "Check for a duplicate",
    STEP_BALANCE: "Check the amount against the balance",
    STEP_APPLY: "Apply by allocation order",
    STEP_RECEIPTS: "Record and queue receipts",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS, VERIFIED AGAINST
# `07-frontend/src/App.tsx` ON 2026-09-06.** A fix route that resolves to
# nothing is a dead button over a live finding — hard-won law 2's mirror, the
# shape that left the customer portal with two working doors out of eight — and
# nothing in the backend suite can see it, because a string is a string.
# Tenant-relative, exactly like `tenancy.selectors.CHECKLIST_TARGETS`: the shell
# prefixes `/:tenant/`.
FIX_RECORD_PAYMENT = "payments/record"
FIX_PAYMENTS = "payments"
FIX_INTEGRATIONS = "settings/integrations"

ZERO = Decimal("0")


@dataclass(frozen=True)
class Planned:
    """One payment in the file, and what this run decided about it.

    ⚠ **NO FIELD HERE CARRIES A DATABASE ID AS A VISIBLE VALUE** (B14 rule 31).
    `row_id` and `account_id` are handles the engine and the port need;
    `account_label` is the account NUMBER and the customer's name, which is what
    a clerk can act on. The renderer walks `columns`, so nothing outside them
    reaches a screen.

    ⚠ **`reason` IS A SENTENCE AND NEVER A RULE ID** (`BR-RBS-010`, B14 rule 32).
    The rule that decided it travels in `decided_by_rule`, which is carried in
    `ReportRow.meta` and drawn by no block.
    """

    row_id: str
    row_no: int
    source: str
    amount: Decimal | None
    currency: str
    reference: str | None
    paid_on: str | None
    account_id: str | None
    account_label: str
    confidence: str
    outcome: str
    reason: str
    decided_by_rule: str
    fix_route: str
    fix_label: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a planned payment with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"payment row {self.row_no} names no fix route. BR-RBS-011: a failure names "
                "its fix route, and a failure with no route is a defect in the runbook — a "
                "clerk reads what is wrong and has nowhere to go."
            )

    @property
    def needs_a_person(self) -> bool:
        return self.outcome in (OUTCOME_NEEDS_A_PERSON, OUTCOME_DUPLICATE_HELD)

    def as_row(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "row_no": self.row_no,
            "source": self.source,
            "amount": None if self.amount is None else str(self.amount),
            "currency": self.currency,
            "reference": self.reference,
            "paid_on": self.paid_on,
            "account_id": self.account_id,
            "account_label": self.account_label,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "reason": self.reason,
            "decided_by_rule": self.decided_by_rule,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it decided, and what it looked at.

    `checked` is not decoration. A step that reports nothing over an empty file
    and a step that reports nothing over a clean one are the same sentence with
    very different meanings, and a check whose output cannot tell a reader which
    is which is worse than no check at all (hard-won law 7).

    `reached` is `False` on every step after a stop. It is what the chain draws
    as `notReached` — *"it never ran, because something earlier stopped the
    run"* — rather than leaving a cell blank, which reads as *nothing wrong*.
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


# ── helpers ───────────────────────────────────────────────────────────────


def _money(raw: Any) -> Decimal | None:
    """A stored money string as a `Decimal`, or `None` where it will not parse.

    ⚠ **NEVER `float(...)`** — hard rule 2, and the seam hands the stored
    four-place value across as a STRING for exactly this reason. A row whose
    amount would not parse is a row a person must see, so `None` travels rather
    than a zero that would silently balance.
    """
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _stored(amount: Decimal) -> str:
    """A money figure as it is STORED — four decimals (hard rule 2).

    Every money value that travels in a payload goes through here, so a sum of
    `Decimal("0")` reaches a screen as `0.0000` rather than as `0`. The renderer
    displays two; what is written is four, and the two are different jobs.
    """
    return str(amount.quantize(Decimal("0.0001")))


def _shown(amount: Decimal, currency: str) -> str:
    """A money figure as a CLERK READS IT — two decimals, with its currency.

    ⚠ **THIS EXISTS BECAUSE THE FIRST BUILD PUT A STORED VALUE IN A SENTENCE.**
    A walkthrough of the seeded tenant printed *"182.400000 more than this
    account owes"* on the screen — the six-place container's value, in
    clerk-facing copy, which is hard rule 2 breached in the display half. It is
    the same defect `rating.selectors._display_money` records for `DEF-364`,
    where a percentage shipped as `0.015000` and a customer read `0.015000`.

    ⚠ **AND IT DOES NOT INVENT A SYMBOL.** `$` is a formatting decision the
    tenant's regional settings own and the renderer applies; a CHAR(3) code
    beside the amount is the fact this module holds. A sentence composed here
    carries the code, and a MONEY CELL — which does get the symbol — is used
    everywhere the value is a column rather than prose.
    """
    figure = amount.quantize(Decimal("0.01"))
    return f"{figure} {currency}".strip()


def _source_label(source_kind: Any) -> str:
    key = str(source_kind or "").strip().lower()
    return SOURCE_LABELS.get(key) or (key.replace("_", " ").title() if key else "Unknown")


def _stopped(ctx) -> dict[str, Any] | None:
    """The stop step 1 recorded, or `None`. Read by every step after it."""
    first = ctx.set_results.get(STEP_SOURCE) or {}
    stop = first.get("stop")
    return dict(stop) if stop else None


def _never_reached(stop: dict[str, Any]) -> dict[str, Any]:
    return _StepResult(reached=False, checked={"never_reached_because": stop["headline"]}).as_dict()


def _plan(ctx) -> list[dict[str, Any]]:
    """The plan as the LAST step that touched it left it.

    Steps 2 to 5 each rewrite the whole plan rather than annotating rows in
    place, so the plan a later step reads is always one object with one author.
    Two steps editing one list is how a record ends up carrying the reason from
    one rule and the outcome from another.
    """
    for key in (STEP_BALANCE, STEP_DUPLICATES, STEP_BY_REMITTANCE, STEP_BY_ACCOUNT):
        result = ctx.set_results.get(key) or {}
        if result.get("reached") and result.get("plan") is not None:
            return list(result["plan"])
    return []


# ── step 1 · where today's work comes from ────────────────────────────────


def step_where_the_work_comes_from(ctx, subjects) -> dict[str, Any]:
    """1 · Two doors, and the run STOPS when both are shut.

    `RB-110` step 1 reads *"Gather today's landed payments — from every
    connected source, once, pinned"*. The Product Owner's two rulings of
    2026-09-06 make that one step with two halves: a **connection** may bring
    the work, and a **person** may. This looks for both and says which it found.

    ⚠ **THE STOP IS A RESULT AND IT IS WRITTEN AS ONE.** `RUN_STATUS_STOPPED`
    already existed beside `done` and `failed`; nothing here raises, nothing
    crashes, and every later step reads *Never reached* (`BR-RBS-027`). The
    headline is one sentence a clerk can act on and it names BOTH absences,
    because *"no connection"* alone would send somebody to Settings when what
    they actually needed was to upload the file.
    """
    connections = integrations_seam.live_connections(PAYMENT_PROVIDER_KEYS)
    working = [one for one in connections if one.get("enabled") and one.get("status") == "working"]
    batch = payments_seam.import_batch(ctx.params.get("batch"))
    rows = list((batch or {}).get("rows") or [])

    checked: dict[str, Any] = {
        "payment_connections_looked_for": len(PAYMENT_PROVIDER_KEYS),
        "payment_connections_found": len(connections),
        "payment_connections_working": len(working),
        "connection_names": [one.get("display_name") or one.get("key") for one in working],
        "file_uploaded": batch is not None,
        "file_name": (batch or {}).get("file_name"),
        "file_status": (batch or {}).get("status"),
        "payments_in_the_file": len(rows),
    }

    if batch is None and not working:
        # ⚠ BOTH DOORS SHUT. The headline names both, in the order a clerk can
        # act on them: uploading a file is a two-minute job and connecting a
        # lockbox is an afternoon.
        offline = [one for one in connections if not one.get("enabled")]
        detail = (
            "A payment connection is set up and switched off."
            if offline
            else "No payment connection is set up."
        )
        return _StepResult(
            stop={
                "headline": "Nothing to work on.",
                "detail": (
                    f"{detail} Nobody has uploaded a file either, so there are no payments "
                    "to match. Upload the day's payments, or connect a payment provider."
                ),
                "fix_route": FIX_RECORD_PAYMENT,
                "fix_label": "Upload payments",
            },
            checked=checked,
        ).as_dict()

    if batch is None:
        # A connection is live and no file has been uploaded. That is a
        # different sentence and a different stop: nothing has landed YET.
        return _StepResult(
            stop={
                "headline": "Nothing has landed yet.",
                "detail": (
                    f"{', '.join(str(one) for one in checked['connection_names'])} is connected "
                    "and no payments have been uploaded for this run. Upload the day's payments, "
                    "or start this again when a file arrives."
                ),
                "fix_route": FIX_RECORD_PAYMENT,
                "fix_label": "Upload payments",
            },
            checked=checked,
        ).as_dict()

    return _StepResult(checked=checked).as_dict()


# ── steps 2 and 3 · the match ladder ──────────────────────────────────────


def _planned_from(row: dict[str, Any], batch: dict[str, Any]) -> Planned:
    """One staged row, read as a decision. **The ladder is `payments`' own.**

    `payment_import._match_row` already walks the card's ladder — account
    number, then remittance id, then name and amount — and writes
    `match_method`, `match_state` and a `match_detail` sentence per row. **This
    runbook reads that answer rather than matching again**: two implementations
    of one ladder is how a screen and a runbook end up disagreeing about whose
    money it is, and the module that owns the table owns the rule (`RBR-03`'s
    shape, one level down).

    What the runbook adds is the part no screen does: the tally, the duplicate
    window, the balance comparison, and a plan a second person approves.
    """
    source = _source_label(batch.get("source_kind"))
    # ⚠ THE CURRENCY IS THE TENANT'S AND NOT THE BATCH's. `payment_import_batch_dict`
    # carries no currency column — a remittance batch has none, `BR-TEN-042` locks a
    # utility to ONE code, and reading it off the batch produced an empty string in
    # every money sentence this runbook composes.
    currency = str(batch.get("currency") or "") or payments_seam.tenant_currency()
    amount = _money(row.get("amount"))
    method = str(row.get("match_method") or "none")
    state = str(row.get("match_state") or "error")
    detail = str(row.get("match_detail") or "").strip()
    account_id = row.get("account_id")
    reference = row.get("reference") or (row.get("raw") or {}).get("reference")

    if state == "clean" and account_id:
        return Planned(
            row_id=str(row.get("row_id")),
            row_no=int(row.get("row_no") or 0),
            source=source,
            amount=amount,
            currency=currency,
            reference=reference,
            paid_on=row.get("paid_on"),
            account_id=str(account_id),
            account_label=detail or "Matched",
            confidence="Certain",
            outcome=OUTCOME_PLANNED,
            reason=(
                "The file named the account."
                if method == "account_no"
                else "The file named the bill."
            ),
            decided_by_rule="BR-RBS-004 — an Action plans before it acts",
            fix_route=FIX_PAYMENTS,
            fix_label="Open payments →",
        )

    if method == "name_amount" and account_id:
        # ⚠ A SUGGESTION, AND THE PRODUCT REFUSES TO POST ON ONE. `CS-2`'s
        # second rule: *"a name-and-amount heuristic never commits on its own"*.
        # The card says the same thing from the other side — *"a clerk confirms
        # a guess, the runbook does not make it"*.
        return Planned(
            row_id=str(row.get("row_id")),
            row_no=int(row.get("row_no") or 0),
            source=source,
            amount=amount,
            currency=currency,
            reference=reference,
            paid_on=row.get("paid_on"),
            account_id=str(account_id),
            account_label=detail or "One likely account",
            confidence="Likely",
            outcome=OUTCOME_NEEDS_A_PERSON,
            reason="Matched on the payer's name, which is not an identifier.",
            decided_by_rule="A name is not an identifier — confirm before the money is posted",
            fix_route=FIX_RECORD_PAYMENT,
            fix_label="Pick account →",
        )

    return Planned(
        row_id=str(row.get("row_id")),
        row_no=int(row.get("row_no") or 0),
        source=source,
        amount=amount,
        currency=currency,
        reference=reference,
        paid_on=row.get("paid_on"),
        account_id=None,
        account_label="No account found",
        confidence="—",
        outcome=OUTCOME_NEEDS_A_PERSON,
        reason=detail or "Nothing in this row can be matched to an account.",
        decided_by_rule="Nothing is guessed from a reference this utility does not hold",
        fix_route=FIX_RECORD_PAYMENT,
        fix_label="Pick account →",
    )


def step_match_by_account_number(ctx, subjects) -> dict[str, Any]:
    """2 · The clean case — most of the file.

    The whole plan is built here, in one pass over the staged rows, and the
    later steps rewrite it. Splitting the ladder across two steps that each
    walked the file would ask `payments` the same question twice and let the two
    answers drift within one run.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    batch = payments_seam.import_batch(ctx.params.get("batch")) or {}
    rows = list(batch.get("rows") or [])
    plan = [_planned_from(row, batch) for row in rows]
    by_number = [one for one in plan if one.reason == "The file named the account."]
    return _StepResult(
        plan=[one.as_row() for one in plan],
        checked={
            "payments_examined": len(plan),
            "matched_by_account_number": len(by_number),
        },
    ).as_dict()


def step_match_by_remittance_then_name(ctx, subjects) -> dict[str, Any]:
    """3 · For the ones the account number does not resolve.

    The plan does not move here — step 2 already read the ladder's whole answer
    — so this step COUNTS and reports, which is what the chain cell and the
    by-source table need. It is a separate step because the card has seven and a
    clerk reads the chain to find out where a file went wrong.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    by_bill = [one for one in plan if one["reason"] == "The file named the bill."]
    by_name = [one for one in plan if one["confidence"] == "Likely"]
    nothing = [one for one in plan if one["account_id"] is None]
    return _StepResult(
        plan=plan,
        checked={
            "matched_by_remittance_id": len(by_bill),
            "suggested_by_name": len(by_name),
            "nothing_to_match_on": len(nothing),
        },
    ).as_dict()


# ── step 4 · the duplicate window ─────────────────────────────────────────


def step_check_for_a_duplicate(ctx, subjects) -> dict[str, Any]:
    """4 · Same account and same amount, inside the window.

    ⚠ **A DUPLICATE IS HELD, NEVER REJECTED** (`RBR-14`, and the card says it
    twice). The second payment is real money somebody sent; refusing it loses
    it. It is held for a person, who is the only one who can tell a file lodged
    twice from a customer who paid twice.

    ⚠ **THE WINDOW IS A PARAMETER AND ITS DEFAULT IS THE CARD's THREE DAYS.**
    It compares against payments ALREADY RECORDED, which is `OQ-RBS-1737`'s
    ruling one level down: the Product Owner moved the duplicate check from a
    computed key to *"you will find those record means you can see that it is
    duplicate"* — detection is a READ of what exists.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    window = int(ctx.params.get("duplicate_window") or 3)
    today = tenancy_seam.today()
    start = today - timedelta(days=max(window, 0))
    account_ids = sorted({one["account_id"] for one in plan if one["account_id"]})
    recorded = payments_seam.payments_recorded_between(account_ids, start, today)

    seen: dict[tuple[str, str], int] = {}
    for one in recorded:
        amount = _money(one.get("amount"))
        if amount is None or not one.get("account_id"):
            continue
        seen[(str(one["account_id"]), str(amount))] = seen.get(
            (str(one["account_id"]), str(amount)), 0
        ) + 1

    held = 0
    within_file: dict[tuple[str, str], int] = {}
    out: list[dict[str, Any]] = []
    for one in plan:
        amount = _money(one.get("amount"))
        key = (str(one["account_id"]), str(amount)) if one["account_id"] and amount else None
        row = dict(one)
        if key is not None and row["outcome"] == OUTCOME_PLANNED:
            already = seen.get(key, 0) + within_file.get(key, 0)
            if already:
                held += 1
                row["outcome"] = OUTCOME_DUPLICATE_HELD
                row["reason"] = (
                    f"The same amount was already recorded for this account "
                    f"in the last {window} day(s)."
                )
                row["decided_by_rule"] = "A duplicate payment is held, never rejected"
                row["fix_route"] = FIX_PAYMENTS
                row["fix_label"] = "Open payments →"
            within_file[key] = within_file.get(key, 0) + 1
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "window_days": window,
            "accounts_looked_up": len(account_ids),
            "payments_already_recorded_in_the_window": len(recorded),
            "duplicates_held": held,
        },
    ).as_dict()


# ── step 5 · the amount against the balance ───────────────────────────────


def step_check_the_amount_against_the_balance(ctx, subjects) -> dict[str, Any]:
    """5 · Over- and short-payments flagged, **never guessed**.

    The card's own words. An overpayment above the declared amount is raised for
    a person to confirm — the money is real and applying it is a decision about
    what happens to the surplus, which is a person's call and not a rule's.

    ⚠ **AN ACCOUNT WHOSE BOOKS WILL NOT OPEN IS NAMED, NOT SKIPPED.** The seam
    answers `None` when the balance cannot be read, and this records
    *"could not read the balance"* against that ONE payment and carries on. A
    step that skipped it silently would report a clean file over an account
    nobody could price — `G32`'s shape, which reported `0 unresolved` truthfully
    over 21 live refusals.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    plan = _plan(ctx)
    over_threshold = _money(ctx.params.get("overpayment_over")) or Decimal("50.0000")

    balances: dict[str, Decimal | None] = {}
    unreadable = 0
    over = 0
    short = 0
    out: list[dict[str, Any]] = []
    for one in plan:
        row = dict(one)
        account_id = row["account_id"]
        amount = _money(row.get("amount"))
        if row["outcome"] != OUTCOME_PLANNED or not account_id or amount is None:
            out.append(row)
            continue
        if account_id not in balances:
            position = payments_seam.open_bill_position(account_id)
            balances[account_id] = (
                None if position is None else (_money(position.get("total_open")) or ZERO)
            )
        owed = balances[account_id]
        if owed is None:
            unreadable += 1
            row["outcome"] = OUTCOME_NEEDS_A_PERSON
            row["reason"] = "This account's open bills could not be read, so nothing is applied."
            row["decided_by_rule"] = "A balance that cannot be read is stated, never assumed"
            row["fix_route"] = FIX_PAYMENTS
            row["fix_label"] = "Open payments →"
            out.append(row)
            continue
        surplus = amount - owed
        if surplus > over_threshold:
            over += 1
            row["outcome"] = OUTCOME_NEEDS_A_PERSON
            row["reason"] = (
                f"{_shown(surplus, str(row.get('currency') or ''))} more than this account owes."
            )
            row["decided_by_rule"] = "An overpayment is confirmed by a person, never guessed"
            row["fix_route"] = FIX_PAYMENTS
            row["fix_label"] = "Confirm overpayment →"
        elif surplus < ZERO:
            # A short payment is APPLIED — it is a part payment and the
            # allocation order handles it. It is counted so the run can say how
            # many, which is the figure a collections clerk reads next.
            short += 1
        out.append(row)

    return _StepResult(
        plan=out,
        checked={
            "accounts_priced": len([one for one in balances.values() if one is not None]),
            "balances_that_would_not_read": unreadable,
            "overpayments_over_the_threshold": over,
            "short_payments": short,
            "overpayment_threshold": _stored(over_threshold),
        },
    ).as_dict()


# ── step 6 · apply, and the second approval ───────────────────────────────


def _approval(ctx) -> dict[str, Any]:
    """Has a second person approved THIS run, for the plan as it stands?

    `BR-RBS-018` (CONFIRMED 2026-09-06, `OQ-RBS-1732`: *"every money action, no
    threshold"*) and `BR-RBS-005` (`TC-RBS-8`) together, and both of those live
    in `_money_gate.py` so that runbooks 10 and 14 cannot hold two versions of
    one money rule. What is decided HERE is only **what the plan is**: the
    payments this run would apply, which is the number the approval must match.
    """
    planned = len([one for one in _plan(ctx) if one["outcome"] == OUTCOME_PLANNED])
    return _money_gate.second_approval(ctx, planned=planned)


def step_apply_by_allocation_order(ctx, subject) -> dict[str, Any]:
    """6 · Through the payments service, one per payment (`BR-RBS-022`).

    ⚠ **THE RUNBOOK NEVER WRITES A PAYMENT ROW.** `apply_payment` is a named
    port into `payments`' own service; the allocation order is `payments`'
    (`BR-PAY-010`) and is read from Settings, never duplicated here (`RBR-03`).
    Hard rule 4 is untouched — a correction is a new row, made by the owning
    module.

    ⚠ **PER-RECORD, SO EACH PAYMENT RUNS INSIDE ITS OWN SAVEPOINT.** The
    executor opens a nested `transaction.atomic()` around this call. On
    PostgreSQL that is the ONLY thing that lets the run continue after one
    refused row — without it the first `IntegrityError` aborts the whole
    transaction and every later application is lost at COMMIT, and the test
    suite's in-memory SQLite cannot see the difference (hard-won law 14).
    """
    if _stopped(ctx):
        return {
            "outcome": OUTCOME_SKIPPED,
            "reason": "The run stopped before this step.",
            "decided_by_rule": "A required step failing makes every later step Never reached",
        }
    by_id = {one["row_id"]: one for one in _plan(ctx)}
    row = by_id.get(str(subject.subject_id))
    if row is None:
        return {"outcome": OUTCOME_SKIPPED, "reason": "This payment is not in the plan."}
    if row["outcome"] != OUTCOME_PLANNED:
        return {
            "outcome": row["outcome"],
            "reason": row["reason"],
            "decided_by_rule": row["decided_by_rule"],
            "fix_route": row["fix_route"],
            "data": {"account": row["account_label"], "amount": row["amount"]},
        }

    approval = _approval(ctx)
    if not approval["approved"]:
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": approval["reason"],
            "decided_by_rule": "A money-bearing action carries a second approval",
            "fix_route": FIX_PAYMENTS,
            "data": {"account": row["account_label"], "amount": row["amount"]},
        }

    try:
        ctx.port("apply_payment").call(
            account_id=row["account_id"],
            amount=row["amount"],
            currency=row["currency"],
            reference=row["reference"],
            paid_on=row["paid_on"],
            source_row_id=row["row_id"],
        )
    except PortNotBound as refusal:
        # ⚠ **THE PORT IS ALWAYS CALLED AND THE PORT'S OWN REFUSAL IS THE
        # OUTCOME.** There is no `if is_bound` branch here: `BR-RBS-003` makes
        # dry and live one code path, and a branch would be a second path that
        # proves nothing about the first. Nothing is poisoned by this — the
        # refusal is raised before any SQL is issued, so hard-won law 14's
        # aborted-transaction trap is not in play, and the savepoint above
        # covers the day a bound writer refuses for real.
        return {
            "outcome": OUTCOME_PLANNED,
            "reason": "Ready to apply. Nothing is written yet.",
            "decided_by_rule": str(refusal),
            "fix_route": FIX_PAYMENTS,
            "data": {"account": row["account_label"], "amount": row["amount"]},
        }
    applied = ctx.set_results.setdefault("applied", [])
    applied.append(row["row_id"])
    return {
        "outcome": OUTCOME_APPLIED,
        "reason": "Applied in the allocation order.",
        "decided_by_rule": "The allocation order is read from Settings, never decided here",
        "fix_route": FIX_PAYMENTS,
        "data": {"account": row["account_label"], "amount": row["amount"]},
    }


def step_record_and_queue_receipts(ctx, subjects) -> dict[str, Any]:
    """7 · A receipt per applied payment, per the tenant's own rule.

    ⚠ **THE AUDIT ROW IS THE ENGINE'S AND NOT THIS STEP's** (`BR-RBS-022`,
    hard rule 7). `write_audit_row` is refused BY NAME as a port precisely so a
    runbook cannot write one; `BR-RBS-015` names the runbook as the actor and
    the platform gained `actor_kind` / `actor_label` / `actor_version` on
    2026-09-06. Binding that is task `L2`'s, and it is named in this runbook's
    report so the gap is visible rather than assumed closed.

    Queues nothing today because nothing is applied — the count is reported
    either way, so *"no receipts because no payments"* and *"no receipts because
    the queue is broken"* cannot read the same.
    """
    stop = _stopped(ctx)
    if stop:
        return _never_reached(stop)
    applied = list(ctx.set_results.get("applied") or [])
    queued = 0
    refused = ""
    for row_id in applied:
        try:
            ctx.port("queue_receipt").call(source_row_id=row_id)
            queued += 1
        except PortNotBound as refusal:
            refused = str(refusal)
            break
    return _StepResult(
        plan=_plan(ctx),
        checked={
            "payments_applied": len(applied),
            "receipts_queued": queued,
            "receipt_queue_state": refused or "queued",
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _rollup(view) -> dict[str, Any]:
    """The counts every block draws, computed once from the record outcomes."""
    counts = {
        OUTCOME_APPLIED: 0,
        OUTCOME_PLANNED: 0,
        OUTCOME_NEEDS_A_PERSON: 0,
        OUTCOME_DUPLICATE_HELD: 0,
        OUTCOME_SKIPPED: 0,
    }
    value = ZERO
    currency = ""
    for record in view.records:
        counts[record.outcome] = counts.get(record.outcome, 0) + 1
        amount = _money((record.data or {}).get("amount"))
        if amount is not None and record.outcome in (OUTCOME_APPLIED, OUTCOME_PLANNED):
            value += amount
    plan = _plan_from_view(view)
    for row in plan:
        if row.get("currency"):
            currency = str(row["currency"])
            break
    return {
        "counts": counts,
        "value": value,
        "currency": currency,
        "acted": counts[OUTCOME_APPLIED] > 0,
        "plan": plan,
    }


def _plan_from_view(view) -> list[dict[str, Any]]:
    for key in (STEP_RECEIPTS, STEP_BALANCE, STEP_DUPLICATES, STEP_BY_REMITTANCE, STEP_BY_ACCOUNT):
        result = view.set_results.get(key) or {}
        if result.get("reached") and result.get("plan"):
            return list(result["plan"])
    return []


def _chain(view, stop: dict[str, Any]) -> Block:
    """Seven cells: the one that stopped the run, and six that never ran."""
    cells = []
    for index, key in enumerate(STEP_LABELS, start=1):
        first = index == 1
        cells.append(
            {
                "id": key,
                "position": index,
                "label": STEP_LABELS[key],
                "state": "bad" if first else "notReached",
                "note": stop["headline"] if first else "Never reached",
            }
        )
    return Block(
        block="chain",
        payload={"label": "The run stopped at step 1.", "cells": cells},
    )


def _records_columns() -> list[dict[str, Any]]:
    return [
        {"key": "payment", "label": "Payment"},
        {"key": "source", "label": "Source"},
        {"key": "amount", "label": "Amount", "numeric": True},
        {"key": "account", "label": "Likeliest account"},
        {"key": "why", "label": "Why"},
        {"key": "fix", "label": "Fix"},
    ]


def _record_row(index: int, row: dict[str, Any]) -> dict[str, Any]:
    paid_on = row.get("paid_on") or ""
    reference = row.get("reference")
    payment = f"{paid_on} · ref {reference}" if reference else (paid_on or f"Row {row['row_no']}")
    # ⚠ THE PLAN CARRIES MONEY AS A STRING AND THIS CELL NEEDS A `Decimal`.
    # A first draft handed `_stored` the raw value and the run died with
    # `'str' object has no attribute 'quantize'` — found by RUNNING the seed,
    # not by any test, because every unit case here builds its plan from the
    # same strings and the report was the only place they were re-read as money.
    amount = _money(row.get("amount"))
    return {
        "id": f"row-{index}",
        "cells": {
            "payment": {"kind": "text", "text": payment},
            "source": {"kind": "text", "text": row["source"]},
            "amount": (
                {
                    "kind": "money",
                    "amount": _stored(amount),
                    "currency": row.get("currency") or "USD",
                }
                if amount is not None
                else {"kind": "text", "text": "—"}
            ),
            "account": {
                "kind": "text",
                "text": (
                    f"{row['account_label']} · {row['confidence']}"
                    if row["confidence"] not in ("—", "")
                    else row["account_label"]
                ),
            },
            "why": {"kind": "text", "text": row["reason"]},
            "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
        },
        # ⚠ CARRIED, NEVER DRAWN — the renderer walks `columns`, so nothing here
        # can reach a screen. `decided_by_rule` MUST NOT: B14 rule 32 forbids a
        # rule id in clerk-facing copy. It is here because the result file and
        # the conformance test both read it, and the report is the only frozen
        # artefact.
        "meta": {"decided_by_rule": row["decided_by_rule"], "outcome": row["outcome"]},
    }


def report(view) -> list[Block]:
    """Composed from records and counts at CLOSE, then frozen (`BR-RBS-020`).

    Two compositions, because a stopped run and a finished one are two states
    and one shape cannot say both:

    * **stopped** — `Verdict` · `Sentence` · `Chain` · `Records` (empty). The
      chain is what draws *Never reached* on the six steps that did not run, and
      the KPI strip is deliberately ABSENT: a strip reading *0 applied · $0.00 ·
      0 need a person* over a run that examined nothing is indistinguishable
      from a clean day, which is precisely the failure hard-won law 7 is about.
    * **finished** — `Verdict` · `KPIs` · `Breakdown` · `Records` · `Downloads`,
      which is `RB-110`'s own block list plus the verdict the header consumes.

    Every name is one of the twelve (`BR-RBS-021`); no thirteenth is minted.
    """
    stop = (view.set_results.get(STEP_SOURCE) or {}).get("stop")
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
                    "empty": {
                        "title": stop["headline"],
                        "helper": stop["detail"],
                    },
                },
            ),
        ]

    rollup = _rollup(view)
    counts = rollup["counts"]
    acted = rollup["acted"]
    plan = rollup["plan"]
    landed = len(plan)
    placed = counts[OUTCOME_APPLIED] if acted else counts[OUTCOME_PLANNED]
    needs = counts[OUTCOME_NEEDS_A_PERSON]
    held = counts[OUTCOME_DUPLICATE_HELD]
    currency = rollup["currency"] or "USD"
    word = "Applied" if acted else "To apply"

    by_source: dict[str, dict[str, int]] = {}
    for row in plan:
        tally = by_source.setdefault(row["source"], {"landed": 0, "placed": 0, "unmatched": 0})
        tally["landed"] += 1
        if row["outcome"] == (OUTCOME_APPLIED if acted else OUTCOME_PLANNED):
            tally["placed"] += 1
        elif row["outcome"] in (OUTCOME_NEEDS_A_PERSON, OUTCOME_DUPLICATE_HELD):
            tally["unmatched"] += 1

    unmatched = [row for row in plan if row["outcome"] in (OUTCOME_NEEDS_A_PERSON, OUTCOME_DUPLICATE_HELD)]

    return [
        Block(
            block="verdict",
            payload={
                "word": word,
                "tone": "success" if needs == 0 else "warning",
                "count": (
                    f"{placed} {'applied' if acted else 'to apply'}. "
                    f"{needs} need you."
                ),
                "detail": (
                    f"{landed} payments landed."
                    if acted
                    else "Nothing is applied until a second person approves this run."
                ),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    {
                        "id": "placed",
                        "label": word,
                        "value": {"kind": "text", "text": str(placed)},
                        "detail": None if acted else "Planned — waiting for a second approval",
                    },
                    {
                        "id": "value",
                        "label": f"{word} value",
                        "value": {
                            "kind": "money",
                            "amount": _stored(rollup["value"]),
                            "currency": currency,
                        },
                        # `BR-REP-001`: a cash-side figure reads the CLEARING
                        # date, and this is money that arrived at the bank.
                        # Stated rather than left to the renderer's fallback,
                        # which was a hardcoded "posting" for every money tile
                        # in the product (`DEF-RBS-4350`) — wrong here in the
                        # other direction from the test bill.
                        "basis": "clearing",
                    },
                    {
                        "id": "needs",
                        "label": "Need a person",
                        "value": {"kind": "text", "text": str(needs)},
                    },
                    {
                        "id": "held",
                        "label": "Duplicates held",
                        "value": {"kind": "text", "text": str(held)},
                        "detail": "Held, never rejected",
                    },
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By source",
                "columns": [
                    {"key": "source", "label": "Source"},
                    {"key": "landed", "label": "Landed", "numeric": True},
                    {"key": "placed", "label": word, "numeric": True},
                    {"key": "unmatched", "label": "Unmatched", "numeric": True},
                ],
                "rows": [
                    {
                        "id": f"source-{name}",
                        "cells": {
                            "source": {"kind": "text", "text": name},
                            "landed": {"kind": "text", "text": str(tally["landed"])},
                            "placed": {"kind": "text", "text": str(tally["placed"])},
                            "unmatched": {"kind": "text", "text": str(tally["unmatched"])},
                        },
                    }
                    for name, tally in sorted(by_source.items())
                ],
            },
        ),
        Block(
            block="records",
            payload={
                "columns": _records_columns(),
                "rows": [_record_row(index, row) for index, row in enumerate(unmatched, start=1)],
                "total": len(unmatched),
                "chips": [
                    {"id": "all", "label": "All", "count": len(unmatched)},
                    {"id": "needs", "label": "Need a person", "count": needs},
                    {"id": "held", "label": "Duplicates held", "count": held},
                ],
                "empty": {
                    "title": "Every payment found its account.",
                    "helper": f"All {landed} payments matched. Nothing is waiting for you.",
                },
            },
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "applied", "label": word, "format": "csv"},
                    {"id": "unmatched", "label": "Unmatched", "format": "csv"},
                ]
            },
        ),
    ]


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **one subject per payment in the file** (`BR-RBS-019`).

    ⚠ **THE UNIT IS THE PAYMENT AND NOT THE BATCH.** The card's *subject and
    unit of work* row reads *Payment · a day's batch*: the batch is what a
    person hands over and the PAYMENT is what gets decided, one record row and
    one savepoint each.

    ⚠ **RESOLVED ONCE AND FROZEN** (`BR-RBS-009`). A row a clerk assigns to an
    account while the run is going is not in this run's set and is not acted on;
    the fingerprint the executor computes is how a later reader proves the set
    did not move.

    ⚠ **AN EMPTY SET IS THE CORRECT ANSWER WHEN THE RUN IS ABOUT TO STOP**, and
    it is not an error. Step 1 says why in a sentence a clerk can read; a
    `resolve()` that raised would turn a designed outcome into a stack trace.
    """
    batch = payments_seam.import_batch(ctx.params.get("batch"))
    rows = list((batch or {}).get("rows") or [])
    return [
        SubjectRef(
            subject_type="payment",
            subject_id=str(row.get("row_id")),
            label=f"Row {row.get('row_no')}",
        )
        for row in rows
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Cash application",
    kind=models.KIND_ACTION,
    category="payments",
    subject_type="payment",
    unit_of_work="a landed payment",
    # ⚠ MANUAL AND SCHEDULE, NOT `batch.landed` — see the module docstring. A
    # person starts it (PO 2026-09-06) and the event is a later refinement that
    # nothing emits yet.
    triggers=(models.TRIGGER_MANUAL, models.TRIGGER_SCHEDULE),
    tags=("Finance", "Payments"),
    parameters=(
        Parameter(
            name="batch",
            type=PARAM_REF_OBJECT,
            label="The file you uploaded",
        ),
        Parameter(
            name="allocation_order",
            type=PARAM_REF_SETTING,
            label="Allocation order",
            setting_key="payments.allocation_order",
        ),
        Parameter(
            name="match_on",
            type=PARAM_ENUM,
            label="Match on",
            required=True,
            default="account_then_remittance_then_name",
            # ⚠ ONE CHOICE, AND IT IS THE LADDER `payments` ALREADY WALKS.
            # `payment_import._match_row` implements exactly this order and
            # says in its own docstring that the order *"is not a preference"*.
            # A dropdown offering an order the owning module cannot honour
            # would be worse than a dropdown of one.
            choices=("account_then_remittance_then_name",),
        ),
        Parameter(
            name="auto_apply_exact_matches",
            type=PARAM_TOGGLE,
            label="Auto-apply exact matches",
            default=True,
        ),
        Parameter(
            name="overpayment_over",
            type=PARAM_MONEY,
            label="Overpayment over",
            # ⚠ A STRING, NEVER A FLOAT. This value lives inside
            # `runbook_versions.definition`, which is `jsonb` — there is no
            # `NUMERIC(18,4)` in there and no column type will catch a float
            # (hard rule 2, `03-field-map.md` D-3). The contract refuses one.
            default="50.0000",
        ),
        Parameter(
            name="duplicate_window",
            type=PARAM_DAYS,
            label="Duplicate window",
            default=3,
        ),
        Parameter(
            name="rerun_window",
            type=PARAM_DAYS,
            label="Run the same job again after",
            # `OQ-RBS-1737`, CLOSED 2026-09-06: *"keep 24 hours time limit on
            # the same job or we can parameteise the frequency of the runs"*,
            # read as ONE control — the frequency is a parameter and 24 hours
            # is its default.
            default=1,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_SOURCE,
            label=STEP_LABELS[STEP_SOURCE],
            mode=MODE_SET,
            run=step_where_the_work_comes_from,
        ),
        Step(
            key=STEP_BY_ACCOUNT,
            label=STEP_LABELS[STEP_BY_ACCOUNT],
            mode=MODE_SET,
            run=step_match_by_account_number,
        ),
        Step(
            key=STEP_BY_REMITTANCE,
            label=STEP_LABELS[STEP_BY_REMITTANCE],
            mode=MODE_SET,
            run=step_match_by_remittance_then_name,
        ),
        Step(
            key=STEP_DUPLICATES,
            label=STEP_LABELS[STEP_DUPLICATES],
            mode=MODE_SET,
            run=step_check_for_a_duplicate,
        ),
        Step(
            key=STEP_BALANCE,
            label=STEP_LABELS[STEP_BALANCE],
            mode=MODE_SET,
            run=step_check_the_amount_against_the_balance,
        ),
        # ⚠ THE ONLY PER-RECORD STEP, AND THE ONLY ONE THAT WRITES. One payment,
        # one savepoint (hard-won law 14), one record row carrying the plan and
        # the outcome together.
        Step(
            key=STEP_APPLY,
            label=STEP_LABELS[STEP_APPLY],
            mode=MODE_PER_RECORD,
            run=step_apply_by_allocation_order,
            writes=True,
        ),
        Step(
            key=STEP_RECEIPTS,
            label=STEP_LABELS[STEP_RECEIPTS],
            mode=MODE_SET,
            run=step_record_and_queue_receipts,
            writes=True,
        ),
    ),
    ports=("apply_payment", "queue_receipt"),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-022 · US-RBS-017 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_022_cash_application.py · pytest tests/test_rbs_money_runbooks_pg.py (PostgreSQL) · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing is applied — `apply_payment` and `queue_receipt` have no writer until CR-075 task L2, and every run needs a second approval that no endpoint can yet grant; the by-source table lists the sources that actually landed (Portal and Kiosk are tenders, not uploaded files); the KPI strip and the by-source table say "To apply" while nothing is applied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
