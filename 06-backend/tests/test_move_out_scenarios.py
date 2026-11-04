# ── Trace ──────────────────────────────────────────────
# Component: THE MOVE-OUT SCENARIO SUITE — the PO's end-to-end walk, ONE
#            declarative table, ONE runner, ONE command, TWO score columns.
# Change:   PO 2026-09-19, verbatim: *"ensure you run end to end walk withmuitle
#           scenarios - deposites, settlement, bill creation etc - update all
#           premises, unit, plans , asset and acunt status etc move the pending
#           money to master account - create variosu cases and scenarios and do
#           end to end walk to ensure clark is able to perform all these task
#           from screen"*.
# Story:    US-CUS-005 (S20 move-out) · US-BIL-011 (the final bill) ·
#           US-CUS-023 §7 (the deposit-interest accrual) · US-LED-001 (the books)
# Rules:    BR-CUS-030 (a move-out closes the account) · BR-CUS-031 (the final
#           bill handoff) · BR-CUS-021 (final reads through metering's event
#           door) · BR-CUS-025 (the deposit settles EVERYTHING outstanding) ·
#           BR-CUS-050/057 (the original receipt date · the accrual) ·
#           BR-CUS-081 (settle and refund the difference) · BR-CUS-082 (a
#           surviving debt is chased, ladder restarts at TIER 1) · BR-CUS-096
#           (an open dispute HOLDS the excess) · BR-CUS-097 (a sub-account's
#           residue goes to its master) · BR-CUS-171 (a parent with open
#           children cannot be moved out) · BR-CUS-1040 (the unit's landing is
#           stated in words before the commit) · BR-BIL-004 (issued bills are
#           untouched) · BR-BIL-013 (the settlement paths) · BR-MET-036 (the
#           unit derives back to vacant) · BR-MET-044 (the plan lives on the
#           UNIT) · BR-MET-094 (a vacant unit's standby charge) ·
#           BR-MET-107 (the unbanked export credit) · BR-SHL-019 (ONE
#           transactional commit) · BR-SHL-025 (server-enforced RBAC) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7 · hard-won laws 2, 7, 14
# Blueprint: 05-prototype/02 Accounts Menu Blueprint.pdf p110–p118, READ AS
#           IMAGES (B14 rule 42). Every figure drawn there is an ILLUSTRATION
#           and never a fact to build to (B14 rule 37) — the figures asserted
#           here are the SIGNED ones (❄️ WE-7's $150.00 + $3.50 = $153.50) and
#           the ones this suite itself creates.
# Tests:    this file IS the test
# Journey:  08-qa/01-e2e/journeys/J-MVO-TWENTYSEVEN-the-move-out-scenario-suite.md
# ───────────────────────────────────────────────────────
"""**Twenty-seven move-out scenarios, declared in one table, run by one runner,
scored in TWO columns.**

═══════════════════════════════════════════════════════════════════════════
WHY ONE TABLE — THE MOVE-IN SUITE'S REASON, WHICH IS THE PO'S
═══════════════════════════════════════════════════════════════════════════
*"Otherwise scenario twelve gets a check that scenario three doesn't, and
nobody notices."* So every row of `SCENARIOS` declares a verdict for **every
one of the thirteen dimensions** in `DIMENSIONS`, and `declares()` refuses the
row at IMPORT time if one is missing — before it can be collected, run and
reported as a pass over checks nobody wrote. A row with nothing to say about a
dimension says `Silent("why")` **out loud**, and that sentence is printed in
the report where a reader can disagree with it.

═══════════════════════════════════════════════════════════════════════════
⚠ TWO SCORE COLUMNS, BECAUSE A SETTLEMENT WITH A BILL AND ONE WITHOUT ARE TWO
DIFFERENT SETTLEMENTS ABOUT ONE CUSTOMER'S MONEY
═══════════════════════════════════════════════════════════════════════════
`settlement_for` takes the final bill from its CALLER. Asked without one it —
correctly, fail-closed — answers `landing: null` with
`gaps: ["final_bill_not_stated"]`, step 4's four shortfall radios render live
and every POST behind them refuses with `no_shortfall`.

⚠ **THAT WAS EVERY ACCOUNT IN THE PRODUCT UNTIL 18:47 ON 2026-09-19, AND THIS
SUITE WAS BEING WRITTEN WHEN IT STOPPED BEING TRUE.** `1c69a87ab` landed
`billing.final_bill.preview_final_bill` — step 3's keystone, which calls the
SAME `prepare_final_bill` and the SAME `runs.price_account` the one-time
preview uses, DERIVES the other end of the window through
`cut_bill.first_unbilled_day`, and issues nothing. The wizard now hands the
figure to `GET /accounts/{id}/close-impact?final_bill=`. **Build process step
0 — check the packet is current — is what caught it, an hour after the fact.**

So the two columns are the two settlements, and both are now reachable:

  * **NO BILL** — `settlement_for(actor, id)`. Still a real state and not a
    historical one: `preview_final_bill` REFUSES when the window cannot be
    derived (no issued bill and no move-in date to start from), and a clerk on
    such an account gets exactly this.
  * **WITH BILL** — `settlement_for(actor, id, final_bill=…, as_of=…)`, which
    is the wizard's own call today.

**A dimension that does not depend on the settlement answers identically in
both** — the account's status, the unit's landing, the readings, the move
record — which is why a row can be RED in one column and GREEN in the other
without any assertion being weakened.

⚠ **AND `COMPLETE` IN A COLUMN MEANS NO FAILURE *AND* NOTHING LEFT
UNASSERTED.** A row whose landing could not be asserted in a pass is not
complete in it, however many of its other checks passed — counting it green
would report a scenario as working on the strength of the dimensions that are
not what it is about.

⚠ **NOTHING HERE STATES A FINAL BILL THE PRODUCT COULD NOT PRODUCE.** The
ORDER group drives `preview_final_bill` itself and asserts what the product
prices; every other row states a figure only so that ONE term of the
subtraction varies and the arithmetic stays checkable by hand.

═══════════════════════════════════════════════════════════════════════════
⚠ THIS SUITE IS EXPECTED TO BE PARTLY RED, AND THAT IS THE DELIVERABLE
═══════════════════════════════════════════════════════════════════════════
It is written against what the blueprint and the signed rules PROMISE, not
against what the product currently does. Every red row names something that is
not built, and the report says which keystone each one waits on. **Do not
weaken an assertion to make it green** — move the product, or move the row with
a ruling behind it.

═══════════════════════════════════════════════════════════════════════════
SAFETY — THE BETA IS NEVER OPENED
═══════════════════════════════════════════════════════════════════════════
**A move-out COMMITS.** It closes an account, ends service agreements, writes
readings and writes a permanent move record. Readings are append-only and
payments and journal lines are under CLAUDE.md hard rule 4 — **there is no
delete**, and thirteen database triggers refuse one outright.

So the throwaway utility is **a whole PostgreSQL database**, not a tenant
inside the live one: `--ds=config.settings.pgtest` puts the run on
`test_sbh_<checkout>_<digest>`, and the beta named in `DATABASE_URL` is opened
for nothing at all. Each scenario provisions its OWN tenant inside that
database through the real signup path, and `django_db` rolls the whole graph
back when the scenario ends. `10-scripts/move_out_scenarios.sh` counts the
beta's accounts, move records, payments, journal lines, invoices and parked
drafts BEFORE and AFTER anyway — a claim nobody has checked is not a safety
guarantee (hard-won law 1).

═══════════════════════════════════════════════════════════════════════════
EVERY MONEY AND REFUSAL ASSERTION READS BACK FROM POSTGRESQL
═══════════════════════════════════════════════════════════════════════════
Not from a service's return value and never from a screen. `observe()` goes to
the tables — `accounts`, `service_agreements`, `meter_reads`, `move_records`,
`payments`, `journal_lines` joined to `ledger_accounts.designation`, `units`,
`wizard_parks` — because a response that says *Closed* over a row that did not
move is the class of defect that only surfaces in front of a customer.

═══════════════════════════════════════════════════════════════════════════
HOW TO RUN IT
═══════════════════════════════════════════════════════════════════════════
    ./10-scripts/move_out_scenarios.sh

or, by hand, from `06-backend/`:

    set -a; . ./.env; set +a
    JOBS_EAGER=false .venv/bin/pytest tests/test_move_out_scenarios.py \\
        --ds=config.settings.pgtest --reuse-db -q -s

**PROVING IT CAN FAIL** (hard-won law 7 — a suite first seen green is a suite
nobody has proved): set `MOVE_OUT_BREAK=<scenario id>:<dimension>` and that one
OBSERVATION is corrupted before the checkers see it. The scenario must go RED
on exactly that dimension and on nothing else. `./10-scripts/move_out_scenarios
.sh --prove-red` does two of them for you, on two different checkers, and then
shows the same rows green again.

Corrupting the OBSERVATION rather than the DECLARATION is deliberate: it proves
the checker really reads PostgreSQL's answer and compares it, which inverting a
verdict would not.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import pytest

from apps.assets import seams as asset_seams
from apps.billing import final_bill as billing_final_bill
from apps.customers import models as customers_models
from apps.customers import move_out_settlement as mos
from apps.customers import move_reads, move_record_reads, moves
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_service
from apps.customers import services as customers_services
from apps.ledger import models as ledger_models
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.payments import models as payment_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import wizard_parks
from core import errors

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — the shared world
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    brazos,
    commit_read,
    dana,
    make_premises,
    make_unit,
    marcus,
    seed_config,
    tenant_ctx,
)

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: E402,F401

# DEF-CUS-10093 (PO 2026-10-13, option B): the final-bill draft is isolated
# here — this suite tests the close; see tests/move_out_draft_isolation.py.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

D = Decimal
ZERO = D("0")


# ═══════════════════════════════════════════════════════════════════════════
# THE CALENDAR — one clock for all twenty-seven, so no row invents its own
# ═══════════════════════════════════════════════════════════════════════════
#: The tenancy this suite closes. p110 draws `Opened 02/14/2024`; the day is
#: this suite's own and the shape is the drawing's.
OPENED = "2024-11-28"
#: ⚠ **THE DEPOSIT'S ORIGINAL RECEIPT DATE (BR-CUS-050), AND IT IS LOAD-BEARING.**
#: Fourteen completed months before `MOVE_OUT_DAY` is what makes ❄️ WE-7's
#: `$3.50` the figure BR-CUS-057 gives — see `DEPOSIT_INTEREST` below.
DEPOSIT_RECEIVED_ON = "2024-11-28"
#: The move-out day. p111: *"The last day this customer is responsible for the
#: supply."* BR-CUS-056 — the OUTGOING account pays this day.
MOVE_OUT_DAY = "2026-01-28"
#: BR-CUS-056's other half, asserted on the unit: the next occupant starts the
#: day AFTER. p114 draws `Next occupant can start 01/29/2026 at the earliest`.
NEXT_OCCUPANT_DAY = "2026-01-29"
#: The closing period `prepare_final_bill` gathers. p112 draws
#: `12/28/2025 — 01/28/2026`.
PERIOD_START = "2025-12-28"

#: ❄️ **WE-7 / GT-23, FROZEN (B5): `$150.00` held fourteen months at a 2%
#: simple annual rate earns `$3.50`, and `$153.50` is what is applied.**
#:
#: ⚠ **THIS IS A SIGNED FIGURE, NOT A TEST FIXTURE.** B4/B5 are ❄️ FROZEN and
#: changing one needs a finance re-sign through HUMAN-GUIDE §6 (CLAUDE.md law
#: 13). The three constants below are quoted, never recomputed from the
#: engine's own formula — a golden figure a test derives from the code it is
#: checking is a golden figure that can never disagree with it.
DEPOSIT_HELD = D("150.00")
DEPOSIT_RATE_PERCENT = "2.000000"
DEPOSIT_INTEREST = D("3.50")
APPLIED_WITH_INTEREST = D("153.50")

#: p112's own subtraction, as the blueprint draws it. **ILLUSTRATIONS (B14 rule
#: 37)** — used here as this suite's chosen figures because they make every
#: landing come out at a round, readable number a person can check by hand, and
#: for no other reason. No rule states any of them.
DRAWN_FINAL_BILL = D("89.10")
DRAWN_PRIOR = D("247.30")


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO PASSES — the clerk's path today, and the same path once wired
# ═══════════════════════════════════════════════════════════════════════════
MODE_TODAY = "nobill"
MODE_WIRED = "withbill"
MODES: tuple[str, ...] = (MODE_TODAY, MODE_WIRED)

#: The keystones a row can be waiting on. Printed beside every red row, so the
#: report never says *"27 scenarios, 11 red"* without saying WHAT the eleven are
#: waiting for.
#: ⚠ **LANDED 2026-09-19 18:47, `1c69a87ab`** — kept as a keystone NAME because
#: it is still what a row without a stated bill is waiting for, and because
#: `preview_final_bill` genuinely refuses on an account whose window cannot be
#: derived. It is no longer *"in flight"*; it is *"stated or not stated"*.
KEY_FINAL_BILL = "final_bill_preview"
#: ⛔ **NO ROW WAITS ON EITHER OF THESE TWO ANY MORE — PO 2026-10-11.**
#: `KEY_DISPUTE_STORE`: BR-CUS-096 is SUSPENDED, so no store reads as no
#: dispute and L2/L4/L5/D3 land. `KEY_SUPERVISOR`: SH4 waited on it for a
#: write-off p113 said needed a supervisor; since PO 2026-10-12 (*"we will not
#: write off at the time of move out"*) move-out offers no write-off at all.
#: Kept for the reason `KEY_MOVE_OUT_DRAFT_REF` below is kept.
KEY_DISPUTE_STORE = "dispute_amount_store"     # nothing stores a disputed AMOUNT
KEY_SUPERVISOR = "supervisor_role"             # the product has three roles
#: \u2705 **NO ROW WAITS ON THIS ANY MORE \u2014 CLOSED 2026-09-20** (PO ruling, option
#: A, item 9). It is KEPT in `KEYSTONES` rather than deleted, because line 3017
#: refuses a row that waits on an unknown keystone and a future row may legit-
#: imately wait on it again; a name removed the day its last user went is a name
#: the next lane re-mints under a different spelling.
KEY_MOVE_OUT_DRAFT_REF = "move_out_draft_reference"
#: ⛔ **NO ROW WAITS ON THIS ANY MORE — WITHDRAWN 2026-10-11, NOT BUILT.** E3
#: waited on the wizard sending `service_request_id`; PO 2026-09-22 (*"Option
#: (b) — remove all three permanently"*) removed the request-to-move-out door,
#: so there is no request for the wizard to send. Kept for the reason the key
#: above is kept.
KEY_WIZARD_REQUEST_LINK = "wizard_sends_service_request_id"
KEYSTONES: tuple[str, ...] = (
    KEY_FINAL_BILL,
    KEY_DISPUTE_STORE,
    KEY_SUPERVISOR,
    KEY_MOVE_OUT_DRAFT_REF,
    KEY_WIZARD_REQUEST_LINK,
)


# ═══════════════════════════════════════════════════════════════════════════
# THE THIRTEEN DIMENSIONS — every row answers all of them
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **THE LIST IS THE CONTRACT.** Adding a fourteenth makes every one of the
#: twenty-seven rows incomplete until it declares one, which is the PO's
#: *"scenario twelve gets a check that scenario three doesn't"* working as
#: intended. Do not give a dimension a default.
DIMENSIONS: tuple[str, ...] = (
    "outcome",            # did the move-out commit, or was it refused?
    "refusal_name",       # WHICH refusal, by message key and rule — never "an error"
    "landing",            # one of the five, or None with its gaps
    "settlement_money",   # outstanding · applied · net · shortfall · excess
    "deposit_interest",   # BR-CUS-057's figure, read through the real engine
    "shortfall_path",     # step 4's decision, its resolved target, and who may take it
    "books_and_payments", # journal lines and payment rows written — expected: NONE
    "account_status",     # `accounts.status` class, `closed_at`, agreements ended
    "unit_after",         # vacant · plan STAYS · meters STAY · the standby choice
    "final_reads",        # `meter_reads` by event context + `accounts.final_read_state`
    "move_record",        # a `move_records` row, and what it names
    "close_impact",       # p115's six consequences: stated or served, NEVER defaulted
    "friction",           # what a clerk has to do that they should not have to
)


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A ROW MAY DECLARE FOR A DIMENSION
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Expect:
    """An assertion. `value` is compared with what PostgreSQL actually holds.

    `only` narrows the assertion to ONE pass. A landing cannot be asserted in
    the TODAY column because the wizard states no bill there, so the landing
    rows declare `only=MODE_WIRED` and the TODAY column records the row as
    BLOCKED rather than as a failure somebody has to re-diagnose every run.
    """

    value: Any
    why: str = ""
    only: str | None = None


@dataclass(frozen=True)
class Silent:
    """**A declared non-assertion.** Printed, never hidden.

    ⚠ **THIS TYPE IS THE WHOLE REASON THE TABLE IS A TABLE.** An omitted key
    is indistinguishable from an oversight; a `Silent` carries its reason into
    the report where a reader can disagree with it. Hard-won law 7's *"a
    declared blind spot with no NUMBER attached is indistinguishable from an
    empty one"*, one layer up.
    """

    why: str


@dataclass(frozen=True)
class Report:
    """Collected and printed; the dimension's own checker decides pass/fail."""

    why: str = ""


Declaration = Expect | Silent | Report


def declares(**kwargs: Declaration) -> dict[str, Declaration]:
    """The expectation block. **Refuses a row that skips a dimension.**

    ⚠ It refuses at IMPORT time and not at assertion time, so a half-declared
    row cannot be collected, run and reported as a pass over checks nobody
    wrote. Hard-won law 7's *"structurally incapable of failing"* is exactly
    what this prevents.
    """
    missing = [name for name in DIMENSIONS if name not in kwargs]
    unknown = [name for name in kwargs if name not in DIMENSIONS]
    if missing or unknown:
        raise AssertionError(
            f"a scenario must declare every dimension: missing={missing} unknown={unknown}"
        )
    return dict(kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD A ROW NEEDS STANDING
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Estate:
    """The premises, unit, meters, money and neighbours one scenario stands on.

    Everything here is built through the OWNING service — `create_premises`,
    `create_unit`, `assign_unit_plan`, `create_account`, `posting.post` — and
    never by writing a row this product would not write itself. The two
    exceptions are named on their own fields and each says why.
    """

    #: `(asset_no, service, uom)`. **An EMPTY tuple means a unit with NO METER
    #: AT ALL**, which R4 exists to prove the move-out does not refuse — and to
    #: pin `accounts.final_read_state` to NULL for the right reason.
    meters: tuple[tuple[str, str, str], ...] = (("M-4021", "electric", "kWh"),)
    unit_label: str = "Unit A"
    unit_type: str = "residential"
    #: `metering.Unit.vacant_standby_auto` BEFORE the move-out. The clerk's
    #: step-5 choice is `Steps.standby`, and the pair is what makes the
    #: BR-MET-094 money consequence visible rather than assumed.
    standby_before: bool = False
    #: What `accounts.deposit_on_file` holds. **Written through the account
    #: row** rather than through `deposit.take`, because `take` is the MOVE-IN
    #: door's (it opens the account, takes the money and writes the register in
    #: one transaction) and there is no door that puts a deposit on an account
    #: that already exists. The register column and its BR-CUS-050 receipt date
    #: are the two facts the settlement reads, and both are set here exactly as
    #: a move-in would have left them.
    deposit: Decimal | None = None
    deposit_received_on: str = DEPOSIT_RECEIVED_ON
    #: The tenant's own BR-CUS-057 rate, written through
    #: `tenancy.save_settings_family` — the S66 Billing-defaults page a real
    #: admin uses. `None` leaves the seeded default, which is BR-CUS-057's own
    #: *"default 0%"* and therefore a real answer of zero interest.
    interest_rate_percent: str | None = None
    #: A real AR debit on ANOTHER account of the SAME customer, posted through
    #: `ledger.posting.post` — the one service allowed to write journal lines
    #: (CLAUDE.md rule 5). This is what makes `refused_other_debt` reachable.
    sibling_debt: Decimal | None = None
    #: A real AR debit on THIS account, same route: p112's `Prior balance`.
    prior_balance: Decimal | None = None
    #: A master account for this address, so `transfer` has a resolvable
    #: target — the PO's *"move the pending money to master account"*.
    with_master: bool = False
    #: Other occupying accounts on this premises, which makes the leaving one a
    #: parent under BR-CUS-171.
    sub_accounts: int = 0
    #: A service request this move-out fulfils (`BR-CUS-080`).
    from_request: bool = False
    #: Prior committed reads, so the ESTIMATE path has a history to work from.
    #: `(asset_no, day, value, consumption, days_since_prior)` — the last two
    #: are what make a row TRAILING ACTUAL rather than merely a number, and
    #: without them `estimate_missing_read` refuses `no_history`, correctly.
    read_history: tuple[tuple[str, str, str, str, int], ...] = ()


@dataclass(frozen=True)
class Steps:
    """**What the six steps asked the clerk for**, step by step.

    Declared per step rather than as one payload, because the friction check
    needs to know WHICH step each field came from, and because a reader
    comparing this with p110–p115 should be able to put their finger on the
    line.
    """

    #: Step 2 — `Moved out on`.
    moved_out_on: str = MOVE_OUT_DAY
    #: Step 2 — the final reads. `None` means the clerk keyed none, which is
    #: p111's third answer (`Due`) and a lawful close.
    final_reads: tuple[dict[str, Any], ...] | None = None
    #: Step 3 — the final bill the preview would state. `None` means the row
    #: expects no bill in EITHER column (R4's meterless unit does not).
    final_bill: Decimal | None = None
    #: Step 4 — the shortfall path, and what it needs.
    shortfall_path: str | None = None
    forwarding_address: str | None = None
    #: Step 5 — `Vacant standby`, the dropdown the PO ruled on 2026-09-19:
    #: *"give option to clark to chose from - using drop down - let him make the
    #: decision"*. `None` means the clerk left it alone.
    standby: bool | None = None
    #: Who is at the counter. `clerk` is a BILLING_CLERK, `admin` a SYSTEM
    #: ADMIN. SH4 runs as a clerk on purpose — see its own note.
    actor: str = "admin"
    #: The day the settlement accrues interest to (CR-059 CS-20 / BR-TEN-043).
    as_of: str = MOVE_OUT_DAY


@dataclass(frozen=True)
class Scenario:
    """One row. Setup, inputs, and a verdict for all thirteen dimensions."""

    id: str
    group: str
    title: str
    estate: Estate
    steps: Steps
    expect: dict[str, Declaration]
    #: Which keystones this row waits on. Printed beside every red row.
    blocked_on: tuple[str, ...] = ()
    #: `commit` (the ordinary walk), `bill_first` / `close_first` (the ORDER
    #: group's two halves) or `park_resume` (the PROCESS row).
    road: str = "commit"


# ═══════════════════════════════════════════════════════════════════════════
# THE BLOCKS THE SIX STEPS FILL, so twenty-seven rows do not retype them
# ═══════════════════════════════════════════════════════════════════════════
ONE_READ: tuple[dict[str, Any], ...] = ({"meter_no": "M-4021", "value": "52410"},)
ONE_ESTIMATE: tuple[dict[str, Any], ...] = ({"meter_no": "M-4021", "estimate": True},)

#: What a closed account's status class must be. `BR-MET-036` derives the unit
#: back to vacant from the CLASS and never from the label, which is why this is
#: the thing asserted rather than the word `closed`.
CLASS_TERMINAL = "terminal"

#: The close as p114 draws it: the account terminal, `closed_at` the move day,
#: every open service agreement ended on the same day.
CLOSED = {"behavior_class": CLASS_TERMINAL, "closed_at": MOVE_OUT_DAY, "agreements_open": 0}

#: p114's unit block, which is three separate promises and one choice:
#:   · `vacant` — BR-MET-036 derives it, nothing writes it
#:   · `plan_stays` — **p114 and BR-MET-044. The PO's own journey expected
#:     plans released; the DRAWING disagrees, and B14 rule 41 says the product
#:     matches the blueprint.** The difference is flagged in the report rather
#:     than silently resolved either way.
#:   · `meters_stay` — p114, *"They stay fitted · yes — a move-out removes
#:     nothing"*
#:   · `standby` — the clerk's step-5 dropdown (PO 2026-09-19)
def unit_after(*, standby: bool) -> dict[str, Any]:
    return {"vacant": True, "plan_stays": True, "meters_stay": True, "standby": standby}


def reads(*, taken: int = 0, state: str | None = None) -> dict[str, Any]:
    """`meter_reads` stamped with the `move_out` event context, and the
    `accounts.final_read_state` derived at close from them."""
    return {"move_out": taken, "final_read_state": state}


def record(**over: Any) -> dict[str, Any]:
    base = {"kind": "move_out", "prefix": "MVO-", "reads_committed": 0, "request_linked": False}
    base.update(over)
    return base


#: **NO BOOKS AND NO PAYMENT ROWS** — on every path but the tie-back.
#: `shortfall_decision` returns `persisted: False` and, for collect and a
#: payment plan, `posting: {posted: False}`.
#:
#: ⚠ **AMENDED 2026-10-14 (`CR-185-BRC10`).** This read *"`posting: {posted:
#: False, oq: "OQ-1250"}` … no signed row says which ledger account is debited"*
#: on EVERY path, and its own warning said *"asserted, not described, so the
#: day it starts posting the suite notices"*. That day came by ruling: the PO
#: closed `OQ-1250` → (a) (D5), so the TRANSFER path posts ONE entry of TWO
#: lines, DR AR (owner) / CR AR (tenant) — `BOOKS_MOVED` below, on SH3 only.
NO_BOOKS = {"journal_lines": 0, "payments": 0, "persisted": False, "posted": False}
BOOKS_MOVED = {"journal_lines": 2, "payments": 0, "persisted": False, "posted": True}

#: p115's six, verbatim: *"Premises occupancy afterwards, the owner on record,
#: the vacant-charge position, payment-plan progress, what happens to the
#: assets, and any master-account effect all arrive empty from the close-impact
#: read. Each is named rather than defaulted, because a blank consequence and a
#: harmless one look identical once a screen guesses."*
#:
#: ⚠ **THE ASSERTION IS `stated_or_served`, AND NEVER `empty`.** The drawing
#: says all six arrive empty; `close_impact_for` has since been wired for
#: several of them. Asserting *empty* would make the suite go RED when the
#: product got BETTER, which is a check pointed at the wrong thing (hard-won law
#: 7). What must hold either way is the rule underneath the sentence: **each of
#: the six is either a real measurement or an explicit absence, and NEVER a
#: default** — no `0`, no `false`, no dash standing in for a fact nobody took.
#: Which of the six are now served is REPORTED, because the drawing being stale
#: in the product's favour is news a reader wants.
SIX_CONSEQUENCES: tuple[str, ...] = (
    "premises_occupancy_afterwards",
    "owner_on_record",
    "vacant_charge_position",
    "payment_plan_progress",
    "what_happens_to_the_assets",
    "master_account_effect",
)


# ═══════════════════════════════════════════════════════════════════════════
# ⬛ THE TWENTY-SEVEN
# ═══════════════════════════════════════════════════════════════════════════
SCENARIOS: list[Scenario] = []

# ───────────────── LANDING · p112's five, one arithmetic ───────────────────
# ⚠ **p112, verbatim: *"How the money lands is not a choice. It is one
# subtraction, and the answer decides which case this account is in."*** So
# these five differ in ONE term each and in nothing else, and each asserts the
# arithmetic as well as the word — a landing that came out right on wrong
# figures is not a passing test.
SCENARIOS += [
    Scenario(
        id="L1",
        group="LANDING",
        title="settled — the deposit and its interest meet the bill exactly",
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT),
        steps=Steps(final_reads=ONE_READ, final_bill=APPLIED_WITH_INTEREST, standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing is refused — this is the account that closes at zero"),
            landing=Expect(mos.LANDING_SETTLED, only=MODE_WIRED,
                           why="p112 row 1: *Settled · nothing left either way*"),
            settlement_money=Expect(
                {"outstanding": "153.50", "applied": "153.50", "net": "0.00",
                 "shortfall": "0.00", "excess": "0.00", "step_4_live": False},
                only=MODE_WIRED,
                why="❄️ WE-7's $153.50 on both sides — and step 4 renders `skipped`",
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED,
                                    why="❄️ WE-7 — $150.00, 14 months, 2% simple"),
            shortfall_path=Silent("step 4 is not live on a settled close (B19 §15.9.1 row 1)"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="L2",
        group="LANDING",
        title="refund due — the bill is met and $59.05 of the deposit goes back",
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        # ✅ **NO LONGER WAITS ON `KEY_DISPUTE_STORE` — PO 2026-10-11.** This row
        # was blocked by design: with no dispute store `_open_dispute_total`
        # answered None and every excess gapped on `open_disputes_not_readable`.
        # BR-CUS-096 is SUSPENDED (*"remove it fo time being and process the
        # refund"*), so no store reads as no dispute and the refund LANDS.
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a refund is an ordinary outcome, not a refusal"),
            landing=Expect(mos.LANDING_REFUND_DUE, only=MODE_WIRED,
                           why="B19 §15.9.3 — *after the final bill of $94.45 is met, "
                               "$59.05 remains … it is refunded*"),
            settlement_money=Expect(
                {"outstanding": "94.45", "applied": "153.50", "net": "-59.05",
                 "shortfall": "0.00", "excess": "59.05", "step_4_live": False},
                only=MODE_WIRED,
                why="BR-CUS-081 — the bill is SETTLED from the deposit and does not stand",
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED),
            shortfall_path=Silent("step 4 is skipped on a refund"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(why="does the refund have a payment path? `refund_disposition` "
                                "records a decision and moves no money"),
        ),
    ),
    Scenario(
        id="L3",
        group="LANDING",
        title="short — p113's $186.40 survives the close",
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT,
                      prior_balance=DRAWN_PRIOR),
        steps=Steps(final_reads=ONE_READ, final_bill=DRAWN_FINAL_BILL,
                    shortfall_path=mos.SHORTFALL_COLLECT,
                    forwarding_address="88 Quarry Lane, Silver Creek, TX 78611", standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("BR-CUS-082 — a surviving debt is a lawful close, not a refusal"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect(
                # 247.30 + 89.10 = 336.40 outstanding, less 153.50 = 182.90.
                # ⚠ **NOT p113's drawn $186.40, and the difference is the
                # interest.** The drawing's own red callout says so: *"the
                # signed arithmetic includes deposit interest and this product
                # does not track it … applied counts the deposit alone"*. It
                # does track it now, so the signed figure is $182.90 and the
                # drawn one is the pre-engine number. B14 rule 37 — a figure
                # drawn in a wireframe is an illustration; the SIGNED rule wins.
                {"outstanding": "336.40", "applied": "153.50", "net": "182.90",
                 "shortfall": "182.90", "excess": "0.00", "step_4_live": True},
                only=MODE_WIRED,
                why="BR-CUS-025 as amended — EVERYTHING outstanding, both terms",
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED),
            shortfall_path=Expect(
                {"path": mos.SHORTFALL_COLLECT, "amount": "182.90", "target": None,
                 "dunning_tier": 1, "escalates": False},
                only=MODE_WIRED,
                why="BR-CUS-082 (PO 2026-08-24, *(b) continue, ladder restarts*)",
            ),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="L4",
        group="LANDING",
        title="refused — another account of the same customer owes us money",
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT,
                      sibling_debt=D("948.20")),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        # ✅ NO LONGER WAITS ON `KEY_DISPUTE_STORE` — BR-CUS-096 SUSPENDED, PO
        # 2026-10-11: no store reads as no dispute, so the sibling debt decides.
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("the MOVE-OUT commits; it is the REFUND that is refused"),
            landing=Expect(mos.LANDING_REFUSED_OTHER_DEBT, only=MODE_WIRED,
                           why="B19 §15.9.5 — *the credit here goes there first, no refund*"),
            settlement_money=Expect(
                # The excess is capped at the sibling's debt: $59.05 against
                # $948.20 transfers $59.05 and leaves $889.15 there, which is
                # §15.9.5's own after-figure.
                {"outstanding": "94.45", "applied": "153.50", "net": "-59.05",
                 "shortfall": "0.00", "excess": "59.05",
                 "transfer_to_sibling": "59.05", "sibling_after_transfer": "889.15"},
                only=MODE_WIRED,
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED),
            shortfall_path=Silent("there is no shortfall — the question is where an EXCESS goes"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="L5",
        group="LANDING",
        title="no dispute recorded — the excess is REFUNDED (BR-CUS-096 suspended)",
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        # ⚠⚠ **THIS ROW READ *"held — an open dispute stops the excess going
        # back"* AND DECLARED `refused_excess` UNTIL 2026-10-11.** It was blocked
        # by design on `KEY_DISPUTE_STORE`: nothing in this product stores a
        # disputed AMOUNT, so `refused_excess` was UNREACHABLE and every excess
        # landing gapped on `open_disputes_not_readable`.
        #
        # **PO RULING 2026-10-11 suspends BR-CUS-096**, verbatim: *"today we are
        # not handling any disppute case not recodingt he dispute anywhere. hence
        # dispute check doe snot work, I think we should remove it fo time being
        # and process the refund"*. So the same account — nothing disputed
        # because nothing CAN be recorded as disputed — now lands `refund_due`
        # and its $59.05 goes back. The hold itself is not deleted: a PUBLISHED
        # `billing.open_dispute_total` is still read first and still holds
        # (`test_w5_move_out_settlement`, the suspended-rule pair).
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("the move-out commits; nothing is refused or held"),
            landing=Expect(mos.LANDING_REFUND_DUE, only=MODE_WIRED,
                           why="PO 2026-10-11 — no dispute store means no dispute, so the "
                               "excess is refunded (BR-CUS-081); BR-CUS-096 is SUSPENDED"),
            settlement_money=Expect(
                {"outstanding": "94.45", "applied": "153.50", "net": "-59.05",
                 "excess": "59.05", "refund_amount": "59.05"},
                only=MODE_WIRED,
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED),
            shortfall_path=Silent("no shortfall on a refund"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(why="a dispute is handled by hand while nothing records one "
                                "(PO 2026-10-11) — the product cannot see it"),
        ),
    ),
]

# ───────────────── SHORTFALL · p113's four paths ───────────────────────────
# ⚠ **p113's own table is the contract: PATH · ITS FIELDS · WHO CAN.** Three
# rows say `Any clerk` and the fourth says `A supervisor`. The fields half is
# asserted through what each POST needs. ⚠ The fourth — *Write it off* — is
# NOT a move-out path since PO 2026-10-12 (*"we will not write off at the time
# of move out"*), so three rows are walked and SH4 asserts the write-off's
# absence rather than its WHO.
def _short_estate(**over: Any) -> Estate:
    base = dict(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT,
                prior_balance=DRAWN_PRIOR)
    base.update(over)
    return Estate(**base)


def _short_steps(path: str, **over: Any) -> Steps:
    base = dict(final_reads=ONE_READ, final_bill=DRAWN_FINAL_BILL, shortfall_path=path,
                standby=False)
    base.update(over)
    return Steps(**base)


def _short_common(**over: Declaration) -> dict[str, Declaration]:
    base = dict(
        outcome=Expect("committed"),
        refusal_name=Silent("the close itself is lawful; step 4 decides the residue"),
        landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
        settlement_money=Expect({"shortfall": "182.90", "step_4_live": True}, only=MODE_WIRED),
        deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED),
        books_and_payments=Expect(NO_BOOKS),
        account_status=Expect(CLOSED),
        unit_after=Expect(unit_after(standby=False)),
        final_reads=Expect(reads(taken=1, state="taken")),
        move_record=Expect(record(reads_committed=1)),
        close_impact=Report(),
        friction=Report(),
    )
    base.update(over)
    return declares(**base)


SCENARIOS += [
    Scenario(
        id="SH1",
        group="SHORTFALL",
        title="collect it — the residue stays owed and follows a forwarding address",
        estate=_short_estate(),
        steps=_short_steps(mos.SHORTFALL_COLLECT,
                           forwarding_address="88 Quarry Lane, Silver Creek, TX 78611"),
        blocked_on=(KEY_FINAL_BILL,),
        expect=_short_common(
            shortfall_path=Expect(
                {"path": mos.SHORTFALL_COLLECT, "amount": "182.90", "target": None,
                 "dunning_tier": 1, "escalates": False, "chased": True},
                only=MODE_WIRED,
                why="p113 — *$186.40 stays on A-10432 as a closing balance · the account "
                    "closes SHORT, which keeps its reminder ladder running*",
            ),
            friction=Report(
                why="p113 asks for a FORWARDING ADDRESS and `shortfall_decision` has no "
                    "field for one — the reminders p113 says go there have nowhere to go"
            ),
        ),
    ),
    Scenario(
        id="SH2",
        group="SHORTFALL",
        title="a payment plan — agreed before the close, and it survives it",
        estate=_short_estate(),
        steps=_short_steps(mos.SHORTFALL_PAYMENT_PLAN),
        blocked_on=(KEY_FINAL_BILL,),
        expect=_short_common(
            shortfall_path=Expect(
                {"path": mos.SHORTFALL_PAYMENT_PLAN, "amount": "182.90", "target": None,
                 "dunning_tier": 1, "escalates": False, "chased": True},
                only=MODE_WIRED,
                why="p113 — *Agreed before the account closes, and the plan survives "
                    "the closure*",
            ),
            friction=Report(
                why="p113 asks for INSTALMENTS · FIRST PAYMENT DATE · AMOUNT EACH · THE "
                    "CUSTOMER'S AGREEMENT, and the decision records the word `payment_plan` "
                    "and none of the four — no plan row is created and nothing links one"
            ),
        ),
    ),
    Scenario(
        id="SH3",
        group="SHORTFALL",
        title="TRANSFER IT TO THE MASTER ACCOUNT — the PO's own sentence",
        # ⚠ **THE PO NAMED THIS PATH IN THE ASK: *"move the pending money to
        # master account"*.** BR-CUS-097 signs it and BR-CUS-097-as-qualified
        # (PO 2026-08-27) makes the CLERK'S ACT the consent: *"if clark tied
        # back to A during move out process"*. So the decision must carry WHO
        # tied it back, and the target must be RESOLVED by the server rather
        # than typed — p113: *"The receiving account, resolved by the server"*.
        estate=_short_estate(with_master=True),
        steps=_short_steps(mos.SHORTFALL_TRANSFER),
        blocked_on=(KEY_FINAL_BILL,),
        expect=_short_common(
            # `CR-185-BRC10` — the tie-back POSTS (OQ-1250 CLOSED → a).
            books_and_payments=Expect(BOOKS_MOVED, only=MODE_WIRED),
            shortfall_path=Expect(
                {"path": mos.SHORTFALL_TRANSFER, "amount": "182.90",
                 "target_resolved": True, "target_is_master_or_owner": True,
                 "tied_back_by_actor": True, "dunning_tier": 1, "escalates": False},
                only=MODE_WIRED,
                why="BR-CUS-097 + BR-MET-105a — the target is resolved, never a free-text "
                    "account id, and the clerk who tied it back is on the decision",
            ),
            friction=Report(
                why="p113's red callout: *transferring points the reminder ladder at "
                    "somebody who never agreed to this debt* — the master is told nothing"
            ),
        ),
    ),
    Scenario(
        id="SH4",
        group="SHORTFALL",
        title="a billing clerk's shortfall STAYS OUTSTANDING — move-out writes nothing "
              "off (PO 2026-10-12)",
        # ⚠⚠ **THIS ROW WAS *"WRITE IT OFF as a billing clerk"* UNTIL 2026-10-12.**
        # It waited on `KEY_SUPERVISOR` (p113 says `A supervisor`), and on
        # 2026-10-11 became a payments write-off REQUEST a System Admin approves
        # (`db7b2808d`), with a declared deviation telling payments' guard the
        # prior balance was on issued bills.
        #
        # **PO RULING 2026-10-12** (decision log, *"MOVE-OUT DOES NOT WRITE
        # OFF"*), verbatim: *"we will not write off at the time of move out;
        # these charges remain outstanding on the account and followup is done
        # as per outstanding rules"* — and *"fianance or system admin will do it
        # seperately later"*. So the clerk's scenario is now the one the ruling
        # names — **pursue** the $182.90 (`collect`, BR-CUS-082: chased, ladder
        # restarts at tier 1) — and this row asserts from PostgreSQL that NO
        # `write_offs` row exists for the account and that step 4 does not offer
        # `write_off` at all. The refusal of a posted `write_off` is pinned in
        # `test_w5_move_out_settlement`. The deviation is gone with the path.
        estate=_short_estate(),
        steps=_short_steps(mos.SHORTFALL_COLLECT, actor="clerk"),
        blocked_on=(KEY_FINAL_BILL,),
        expect=_short_common(
            shortfall_path=Expect(
                {"path": mos.SHORTFALL_COLLECT, "refused_for_role": False,
                 "amount": "182.90", "target": None,
                 "dunning_tier": 1, "escalates": False, "chased": True,
                 "write_off_offered": False, "write_off_rows": 0},
                only=MODE_WIRED,
                why="PO 2026-10-12 — the shortfall remains outstanding and is followed up "
                    "as per outstanding rules (BR-CUS-082); a write-off is a later, separate "
                    "act in Payments (BR-PAY-020)",
            ),
            friction=Report(),
        ),
    ),
]

# ───────────────── DEPOSIT · the five positions the PO named ───────────────
SCENARIOS += [
    Scenario(
        id="D1",
        group="DEPOSIT",
        title="no deposit held at all — nothing to accrue on, and no gap for it",
        # ⚠ **THE ONE DEPOSIT CASE THAT WAS NEVER BLOCKED**, and it is worth a
        # row of its own: `_deposit_interest` answers ZERO without consulting
        # the engine when the register is empty, so an account holding no
        # deposit could always be settled. `billing.final_bill.deposit_credit_for`
        # takes the identical posture deliberately — two modules disagreeing
        # about when a deposit may be settled is how one customer gets two
        # answers to one question.
        estate=Estate(),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"),
                    shortfall_path=mos.SHORTFALL_COLLECT, standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing refuses an account that holds no deposit"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED,
                           why="$94.45 against nothing applied is short by all of it"),
            settlement_money=Expect(
                {"outstanding": "94.45", "applied": "0.00", "net": "94.45",
                 "shortfall": "94.45", "excess": "0.00", "step_4_live": True},
                only=MODE_WIRED,
            ),
            deposit_interest=Expect(ZERO, only=MODE_WIRED,
                                    why="a real answer of zero, never an absence"),
            shortfall_path=Expect({"path": mos.SHORTFALL_COLLECT, "amount": "94.45"},
                                  only=MODE_WIRED),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="D2",
        group="DEPOSIT",
        title="the deposit covers the bill EXACTLY, with a 0% utility",
        # The same shape as L1 with the interest term removed, which is the
        # ordinary case: BR-CUS-057's default is 0% and most utilities take it.
        estate=Estate(deposit=DEPOSIT_HELD),
        steps=Steps(final_reads=ONE_READ, final_bill=DEPOSIT_HELD, standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("an exact cover is the cleanest close there is"),
            landing=Expect(mos.LANDING_SETTLED, only=MODE_WIRED),
            settlement_money=Expect(
                {"outstanding": "150.00", "applied": "150.00", "net": "0.00",
                 "settled_from_deposit": "150.00", "step_4_live": False},
                only=MODE_WIRED,
                why="BR-CUS-081 — `min(outstanding, applied)`, and nothing cleverer",
            ),
            deposit_interest=Expect(ZERO, only=MODE_WIRED,
                                    why="BR-CUS-057's *default 0%* is a real answer"),
            shortfall_path=Silent("step 4 is skipped on a settled close"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="D3",
        group="DEPOSIT",
        # Title read *"— and the excess cannot land today"* until PO 2026-10-11.
        title="the deposit covers WITH EXCESS — and the excess is refunded",
        estate=Estate(deposit=DEPOSIT_HELD),
        steps=Steps(final_reads=ONE_READ, final_bill=D("40.00"), standby=False),
        # ✅ NO LONGER WAITS ON `KEY_DISPUTE_STORE` — BR-CUS-096 SUSPENDED, PO
        # 2026-10-11: the $110.00 excess LANDS as a refund.
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("an excess is money owed BACK — nothing refuses the close"),
            landing=Expect(mos.LANDING_REFUND_DUE, only=MODE_WIRED),
            settlement_money=Expect(
                {"outstanding": "40.00", "applied": "150.00", "net": "-110.00",
                 "excess": "110.00", "refund_amount": "110.00",
                 "settled_from_deposit": "40.00"},
                only=MODE_WIRED,
                why="BR-CUS-081 — settle the bill FROM the deposit and refund the rest; "
                    "the rejected reading was to refund it all and leave the bill standing",
            ),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("no shortfall where the deposit covers"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="D4",
        group="DEPOSIT",
        title="the deposit FALLS SHORT — BR-CUS-082's lawful surviving debt",
        estate=Estate(deposit=D("50.00")),
        steps=Steps(final_reads=ONE_READ, final_bill=D("232.90"),
                    shortfall_path=mos.SHORTFALL_COLLECT, standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("BR-CUS-082 is explicit that a shortfall is a lawful STATE"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect(
                {"outstanding": "232.90", "applied": "50.00", "net": "182.90",
                 "shortfall": "182.90", "settled_from_deposit": "50.00", "step_4_live": True},
                only=MODE_WIRED,
            ),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Expect({"path": mos.SHORTFALL_COLLECT, "amount": "182.90",
                                   "dunning_tier": 1, "chased": True}, only=MODE_WIRED),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="D5",
        group="DEPOSIT",
        title="❄️ WE-7 — $150.00 held fourteen months at 2% earns $3.50",
        # ⚠ **THE ROW THE PO RULED ON TODAY, AND ITS CONSEQUENCE RUNS AGAINST
        # THE CUSTOMER.** p112's red callout, verbatim: *"Here `applied` counts
        # the deposit alone, and the consequence runs against the customer: a
        # smaller amount applied makes the shortfall bigger, so this account is
        # asked for more than the signed rule says it owes."* The engine landed
        # on 2026-09-03 (CR-059 CS-20); this row asserts the SIGNED figure so a
        # regression that drops the term is $3.50 of somebody's money, named.
        estate=Estate(deposit=DEPOSIT_HELD, interest_rate_percent=DEPOSIT_RATE_PERCENT,
                      prior_balance=DRAWN_PRIOR),
        steps=Steps(final_reads=ONE_READ, final_bill=DRAWN_FINAL_BILL,
                    shortfall_path=mos.SHORTFALL_COLLECT, standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("the interest is a TERM of the arithmetic, not a gate"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect(
                # The whole point: $186.40 without the interest, $182.90 with
                # it. The difference IS ❄️ WE-7's $3.50.
                {"applied": "153.50", "deposit_held": "150.00", "deposit_interest": "3.50",
                 "shortfall": "182.90"},
                only=MODE_WIRED,
                why="❄️ WE-7 / GT-23 (B5, FROZEN) — and the $3.50 gap between the drawn "
                    "$186.40 and the signed $182.90 is the customer's own money",
            ),
            deposit_interest=Expect(DEPOSIT_INTEREST, only=MODE_WIRED,
                                    why="❄️ WE-7 — asserted, never recomputed from the engine"),
            shortfall_path=Expect({"path": mos.SHORTFALL_COLLECT, "amount": "182.90"},
                                  only=MODE_WIRED),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
]

# ───────────────── READS · p111's three answers, and a unit with no meter ──
# p111's own table: *Taken — somebody read the register at or after the
# move-out date · Estimated — worked out from that register's own history, with
# the method disclosed · Due — no reading at all, and the date has passed.*
# *"Two would not have been enough. A settlement reached on an estimate and one
# reached on a real reading are not the same claim, and the state is stored on
# the account so the difference survives the wizard closing."*
SCENARIOS += [
    Scenario(
        id="R1",
        group="READS",
        title="TAKEN — the clerk keyed the register and the close stores `taken`",
        estate=Estate(),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a keyed reading is the ordinary path"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect({"outstanding": "94.45"}, only=MODE_WIRED),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("step 4 is not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(
                reads(taken=1, state="taken"),
                why="BR-CUS-021 — ONE row in `meter_reads` stamped `move_out`, written by "
                    "metering's own door and never by customers; and `accounts"
                    ".final_read_state` derived once at close",
            ),
            move_record=Expect(record(reads_committed=1),
                               why="a COUNT on the record, never a copy of the readings"),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="R2",
        group="READS",
        title="ESTIMATED — and the record files the committed read under nought "
              "(DEF-CUS-5933)",
        # ⚠ **THREE PRIOR READS, EACH WITH ITS CONSUMPTION AND ITS DAYS.** The
        # estimator works from `trailing_actuals` — (consumption, days) pairs of
        # ACTUAL reads on this channel — and `trailing_3_daily_avg` refuses with
        # `no_history` rather than inventing a shorter window. A single prior
        # register VALUE is not history; it is one number with no period behind
        # it, and the refusal that follows is correct.
        estate=Estate(read_history=(
            ("M-4021", "2025-09-28", "50408", "620", 30),
            ("M-4021", "2025-10-28", "51028", "620", 30),
            ("M-4021", "2025-11-28", "51648", "620", 31),
            ("M-4021", "2025-12-28", "51776", "128", 30),
        )),
        steps=Steps(final_reads=ONE_ESTIMATE, final_bill=D("94.45"), standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("p111 — *an estimated final read is lawful*"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect({"outstanding": "94.45"}, only=MODE_WIRED),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("step 4 is not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(
                reads(taken=1, state="estimated"),
                why="`accounts.final_read_state` is the ONE store that survives the wizard "
                    "closing — B18 §5.6.2's amber cell, and TC-MVO-7 proved it had none",
            ),
            move_record=Expect(
                record(reads_committed=1),
                why="`DEF-CUS-5933`, fixed by `services._reads_committed`, which counts a "
                    "persisted estimate beside the keyed reads. It read: "
                    "⚠ **THE READING IS COMMITTED AND THE RECORD SAYS ZERO.** "
                    "`commit_event_reads` returns `posted_reads = len(posted)` and puts an "
                    "estimate in a SEPARATE `estimates` list, so `services.move_out`'s "
                    "`reads_committed=int((event_reads or {}).get('posted_reads') or 0)` "
                    "counts none of them — while `accounts.final_read_state` reads "
                    "`estimated`, which can only be true if a committed head EXISTS. One "
                    "move-out, two answers about the same row: `meter_reads` holds the "
                    "reading and `move_records` files it under nought",
            ),
            close_impact=Report(),
            friction=Report(
                why="p111: *it prices the last month of a bill they are about to be asked to "
                    "settle, so the account closes on a figure nobody stood in front of*"
            ),
        ),
    ),
    Scenario(
        id="R3",
        group="READS",
        title="DUE — nothing was keyed and the close says so rather than guessing",
        estate=Estate(),
        steps=Steps(final_reads=None, final_bill=D("94.45"), standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a missing final read does not refuse the close"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect({"outstanding": "94.45"}, only=MODE_WIRED),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("step 4 is not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(
                reads(taken=0, state="due"),
                why="`due` ≡ a meter with no committed head at or after the move-out date. "
                    "NOT null, and not zero — p111's third answer, stored",
            ),
            move_record=Expect(record(reads_committed=0),
                               why="`0` is a real answer here and not an absence"),
            close_impact=Report(),
            friction=Report(
                why="the account closes and somebody still has to go and read the meter; "
                    "nothing in the close raises that as work"
            ),
        ),
    ),
    Scenario(
        id="R4",
        group="READS",
        title="a unit with NO METER AT ALL — `final_read_state` is NULL for the right reason",
        # ⚠ **NULL IS THREE DIFFERENT HONEST ABSENCES AND THIS IS ONE OF THEM**
        # (`_final_read_state`): the seam did not resolve, the unit holds no
        # meters, or the close predates the column. Only the middle one is a
        # PRODUCT state, and a suite that never built a meterless unit could not
        # tell them apart.
        estate=Estate(meters=()),
        steps=Steps(final_reads=None, final_bill=None, standby=False),
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed",
                           why="a unit with nothing fitted is not a reason to refuse a move-out"),
            refusal_name=Silent("nothing refuses a meterless close"),
            landing=Silent(
                "no meter means no consumption means no final bill — this row asserts the "
                "CLOSE, and a landing would need a bill nobody can raise"
            ),
            settlement_money=Silent("same reason: there is no bill to subtract from"),
            deposit_interest=Expect(ZERO, only=MODE_WIRED,
                                    why="no deposit held, so a real zero"),
            shortfall_path=Silent("no bill, no shortfall"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect({"vacant": True, "plan_stays": True, "meters_stay": True,
                               "standby": False, "meter_count": 0}),
            final_reads=Expect(
                reads(taken=0, state=None),
                why="NULL, and `move_reads.unit_reads_cell` renders `unit_has_no_meters` "
                    "beside it — never a dash a clerk has to interpret",
            ),
            move_record=Expect(record(reads_committed=0)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
]

# ───────────────── CONSEQUENCE · p114's unit block ─────────────────────────
SCENARIOS += [
    Scenario(
        id="C1",
        group="CONSEQUENCE",
        title="the clerk chooses standby ON — the owner pays the base charge while empty",
        # ⚠ **PO ruling 2026-09-19, verbatim: *"give option to clark to chose
        # from - using drop down - let him make the decision"*.** What is being
        # decided is money: `Unit.vacant_standby_auto` serves BR-MET-094, so the
        # choice is whether the OWNER pays the base charge while the unit stands
        # empty or nobody does. Nobody can infer that from an empty unit, which
        # is why a dropdown is right and a derivation was wrong.
        estate=Estate(standby_before=False, with_master=True),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=True),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("the standby choice is a step-5 election, never a gate"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect(
                {"outstanding": "94.45", "vacant_base_charges_served": True},
                only=MODE_WIRED,
                why="BR-MET-094 + BR-CUS-1040 — with standby ON the owner IS billed, so the "
                    "plan's own per-service base charges must be STATED IN WORDS before the "
                    "commit. `OQ-1166` CLOSED 2026-08-30: base rates only on a vacant unit, "
                    "never a minimum — a `minimum_amount` here would put $42.00 back on the "
                    "screen after it was taken off the bill",
            ),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(
                unit_after(standby=True),
                why="the clerk chose ON, so `metering.Unit.vacant_standby_auto` reads True "
                    "after the close — the PO's dropdown, written",
            ),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="C2",
        group="CONSEQUENCE",
        title="the clerk chooses standby OFF — p114's *nobody is billed for it*",
        estate=Estate(standby_before=True, with_master=True),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("the standby choice is a step-5 election, never a gate"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect({"outstanding": "94.45"}, only=MODE_WIRED),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(
                unit_after(standby=False),
                why="⚠ **THE UNIT STARTED WITH STANDBY ON AND THE CLERK TURNED IT OFF**, "
                    "which is the direction that proves the dropdown WRITES rather than "
                    "merely agreeing with whatever was already there",
            ),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(
                why="p114: *A vacant unit bills the owner only where its own standby flag "
                    "is set. This one is off, so the unit costs nobody anything*"
            ),
            friction=Report(),
        ),
    ),
    Scenario(
        id="C3",
        group="CONSEQUENCE",
        title="a move-out REMOVES NOTHING — the plan stays and the meters stay",
        # ⚠ **p114 draws both, and the PO's own journey expected the opposite
        # for one of them.** *"Plan · stays on the unit"* and *"They stay fitted
        # · yes — a move-out removes nothing"*. `BR-MET-044` puts the plan on
        # the UNIT rather than on the account, so releasing it at move-out would
        # mean the next tenant arrives unpriced. B14 rule 41 — the product
        # matches the blueprint — so this asserts the DRAWING and the report
        # flags that the journey disagreed.
        estate=Estate(meters=(("M-4021", "electric", "kWh"), ("M-4022", "water", "kgal"))),
        steps=Steps(final_reads=ONE_READ, final_bill=D("94.45"), standby=False),
        blocked_on=(KEY_FINAL_BILL,),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing refuses a two-meter close"),
            landing=Expect(mos.LANDING_SHORT, only=MODE_WIRED),
            settlement_money=Expect({"outstanding": "94.45"}, only=MODE_WIRED),
            deposit_interest=Expect(ZERO, only=MODE_WIRED),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(
                {"vacant": True, "plan_stays": True, "meters_stay": True, "standby": False,
                 "meter_count": 2},
                why="p114 — *Plan stays on the unit* (BR-MET-044) and *They stay fitted · "
                    "a move-out removes nothing*. Both read back from `units` and `assets`",
            ),
            final_reads=Expect(
                reads(taken=1, state="due"),
                why="ONE of two meters was keyed, so the state is `due` — a covering head "
                    "is needed on EVERY meter, which is `_final_read_state`'s own rule",
            ),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(
                why="p111 keys both meters on one screen; a clerk who keys one gets a `due` "
                    "close with nothing on screen saying which meter is still outstanding"
            ),
        ),
    ),
]

# ───────────────── ORDER · the bill-then-close trap ────────────────────────
# ⚠ **`final_bill.prepare_final_bill` REFUSES AN ACCOUNT THAT IS NO LONGER
# BILLABLE**, and its own refusal says why in as many words: *"The final bill
# therefore has to be produced BEFORE the move-out writes the close — which is
# the order S20's wizard uses (step 3 'Final bill & deposit', then publish)."*
#
# **NOTHING ENFORCES THAT ORDER.** `services.move_out` neither asks for a final
# bill nor checks that one was raised, so a clerk who closes first has made an
# account that can never be billed for its last month, and the product told
# them nothing. These two rows are the same account walked in the two orders.
SCENARIOS += [
    Scenario(
        id="O1",
        group="ORDER",
        title="BILL first — step 3 prices the reads step 6 will write "
              "(DEF-CUS-5931)",
        # ⚠ **THE METER HAS A PRIOR REGISTER, BECAUSE A MOVE-OUT ACCOUNT DOES.**
        # A closing read is a DIFFERENCE and there is nothing to subtract from a
        # meter this product has never read: with no history the keyed 52,410 is
        # one number, `validation.compute_consumption` answers `None` — honestly
        # — and BR-BIL-015's *"no usable read and no decision"* stops the bill.
        # Dated the day BEFORE the window opens, so it is the previous cycle's
        # closing read and not a head inside this period: a read dated ON
        # `PERIOD_START` would be found by `billing_reads_for_unit` itself, and
        # the preview would then re-bill December's 128 kWh instead of pricing
        # what the clerk keyed.
        #
        # **52,410 − 51,776 = 634 kWh**, which is the quantity the Billing
        # blueprint draws on this very table (p112, *Electric · 634 kWh*) — an
        # ILLUSTRATION under B14 rule 37 and therefore not built to, but the
        # register pair behind it is the PO's own worked case for this ruling.
        estate=Estate(read_history=(
            ("M-4021", "2025-12-27", "51776", "620", 30),
        )),
        steps=Steps(final_reads=ONE_READ, final_bill=None, standby=False),
        road="bill_first",
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("both acts succeed in this order — that is the point"),
            landing=Silent("this row is about the ORDER, and it asserts the priced bill"),
            settlement_money=Expect(
                {"final_bill_prepared": True, "period_end_is_the_move_day": True,
                 "issues_nothing": True, "priced_from_uncommitted_reads": True,
                 # ❄️-ADJACENT, SO IT IS PINNED. 52,410 keyed − 51,776
                 # committed = **634 kWh** at ×1, priced at $0.120000 =
                 # **$76.08**, plus the plan's **$20.00** base charge =
                 # **$96.08**. Proved RED before it was trusted green: armed
                 # with a sentinel, this row reported *wanted 'RED-PROOF',
                 # PostgreSQL holds '634.000000000000'* and *holds '96.08'*.
                 "usage_quantity": "634.000000000000", "charges_total": "96.08"},
                why="BR-CUS-056 — the OUTGOING account pays the move day, so `period_end` "
                    "IS `moved_out_on` and never the day before. And p112's dashed panel: "
                    "***NO BILL IS ISSUED BY THIS SCREEN*** — the priced figure is a "
                    "settlement position, not an invoice, which `books_and_payments` "
                    "proves by counting. ⚠ **AND THE ORDER PROBLEM ONE LAYER DOWN IS "
                    "RULED — PO 2026-09-20, verbatim *option b is correct*.** p111 states "
                    "that *the reads are committed with the close, not before it*, so on "
                    "step 3 the closing register does not exist yet and "
                    "`resolution.MeterMultiplierUnstated` refused every move-out in the "
                    "product — `BR-MET-056` stores the factor USED and *an absent factor "
                    "is NOT 1*. Step 3 now prices the reads the clerk KEYED on step 2 and "
                    "nobody has committed, through `metering.provisional_reads_for_unit`, "
                    "which writes nothing; the commit order at step 6 is untouched. "
                    "`priced_from_uncommitted_reads` is the payload saying which kind of "
                    "claim the figure is, because a figure priced from a keyed read is "
                    "not the same claim as one priced from a committed read",
            ),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="O2",
        group="ORDER",
        title="CLOSE first, then bill — and the refusal that explains the order "
              "is what a clerk is told (DEF-CUS-5932)",
        # ⚠ **THE METER HAS A PRIOR REGISTER, BECAUSE A MOVE-OUT ACCOUNT DOES.**
        # A closing read is a DIFFERENCE and there is nothing to subtract from a
        # meter this product has never read: with no history the keyed 52,410 is
        # one number, `validation.compute_consumption` answers `None` — honestly
        # — and BR-BIL-015's *"no usable read and no decision"* stops the bill.
        # Dated the day BEFORE the window opens, so it is the previous cycle's
        # closing read and not a head inside this period: a read dated ON
        # `PERIOD_START` would be found by `billing_reads_for_unit` itself, and
        # the preview would then re-bill December's 128 kWh instead of pricing
        # what the clerk keyed.
        #
        # **52,410 − 51,776 = 634 kWh**, which is the quantity the Billing
        # blueprint draws on this very table (p112, *Electric · 634 kWh*) — an
        # ILLUSTRATION under B14 rule 37 and therefore not built to, but the
        # register pair behind it is the PO's own worked case for this ruling.
        estate=Estate(read_history=(
            ("M-4021", "2025-12-27", "51776", "620", 30),
        )),
        steps=Steps(final_reads=ONE_READ, final_bill=None, standby=False),
        road="close_first",
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed", why="the CLOSE succeeds — nothing stops it"),
            refusal_name=Expect(
                billing_final_bill.FINAL_ACCOUNT_ALREADY_CLOSED,
                why="`account_already_closed_for_billing` — stage 1 refuses to price an "
                    "account that is not billable (BR-CUS-055), so the last month's bill "
                    "can never be raised for this customer. ⚠ **AND UNTIL 2026-09-20 THE "
                    "SENTENCE THAT EXPLAINS THE ORDER WAS UNREACHABLE.** "
                    "`prepare_final_bill` called `gather_single` and only THEN read "
                    "`data.behavior_class`, so a closed account failed plan resolution "
                    "first: what came back was *no plan version in force on <the service "
                    "date>* (`BR-RAT-007`) — true, about tariff versions, and not the "
                    "carefully written *the final bill therefore has to be produced BEFORE "
                    "the move-out writes the close*. The class is now read off the account "
                    "row BEFORE the gather, so the product tells a clerk the thing it "
                    "knows. This row is the only place that is proved from the state a "
                    "clerk is actually in",
            ),
            landing=Silent("no bill was ever priced, so there is nothing to land"),
            settlement_money=Expect(
                {"final_bill_prepared": False},
                why="the trap, measured: the same account, the same period, the other order",
            ),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(
                why="**NOTHING WARNS THE CLERK.** `services.move_out` neither raises the "
                    "final bill nor checks that one exists, so the only thing standing "
                    "between a customer and an unbillable last month is the clerk "
                    "remembering an order no screen states"
            ),
        ),
    ),
]

# ───────────────── PROCESS · save & exit → the list → Resume → finish ──────
SCENARIOS += [
    Scenario(
        id="P1",
        group="PROCESS",
        title="save & exit, find it again, RESUME from the record, finish "
              "(DEF-CUS-5922)",
        # ⚠ **THE PATH THREE RULINGS OF 2026-09-19 MADE.** The PO ruled the
        # Move-outs list shows the unfinished ones, that the word for a finished
        # one is `Completed`, and — verbatim — *"We will need this action on
        # details page - 4 · Close or complete it"*, which became `Resume`. That
        # is a four-step path and this row walks all four.
        estate=Estate(),
        steps=Steps(final_reads=ONE_READ, final_bill=None, standby=False),
        road="park_resume",
        # ⚠ **FILED BY A SIBLING AS `DEF-CUS-5922` THE SAME EVENING, AND CITED
        # RATHER THAN RE-FILED.** They found it from the other end — an
        # unexecuted backend case that can never pass because it parks a
        # `move_out` draft and only a `move_in` draft is given a reference.
        # Two lanes minting two ids for one fault is how a register stops being
        # countable, which is `DEF-GOV-5229`'s whole lesson. What this row adds
        # to theirs is the two facts downstream of the same cause: `_in_flight`
        # reads `moved_in_on`/`effective_on` and never `moved_out_on`, so the
        # date a clerk typed does not show; and `move_outs_list`'s window is
        # CLOSED ACCOUNTS, so an unfinished move-out is in no list at all.
        #
        # \u2705 **ALL OF IT CLOSED 2026-09-20** (PO ruling, option A, item 9 \u2014
        # `OQ-CUS-12489` closed). A move-out draft takes `MVO-{YY}-{0000}` from
        # the `move_out` series, `services.move_out` adopts it, and `_in_flight`
        # reads `moved_out_on`. ⚠ **AND ONE OF THE THREE WAS NEVER A PRODUCT
        # GAP**: `move_outs_list` HAS carried unfinished rows since 2026-09-19,
        # keyed on `subject_ref.account_id` \u2014 this fixture sent only `values`,
        # so the row was there under a null account and the lookup by account id
        # could not see it (`DEF-CUS-5938`, fixed in the park call above). The
        # sentence above is left as written because it is what the row
        # BELIEVED, and correcting the belief silently is how a suite stops
        # recording what it learned.
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed", why="the resumed wizard finishes the move-out"),
            refusal_name=Silent("nothing in this path refuses"),
            landing=Silent("this row is about the DOOR, not the money"),
            settlement_money=Expect(
                {"draft_parked": True, "draft_listed_in_parked_panel": True,
                 "draft_has_a_reference": True, "record_page_opens_the_draft": True,
                 "record_offers_resume": True, "draft_shows_its_move_out_date": True,
                 "draft_in_move_outs_list": True},
                why="⚠ **SEVEN CHECKS AND FOUR OF THEM ARE THE RULINGS OF TODAY.** A "
                    "move-out draft takes NO reference (`wizard_parks."
                    "_allocate_draft_reference` allocates for `move_in` and for nothing "
                    "else), so `/moves/{ref}` — which is keyed on the reference — cannot "
                    "open it, the `Resume` action the PO asked for cannot be reached from "
                    "the record, and `_in_flight` reads `moved_in_on`/`effective_on` and "
                    "never `moved_out_on`, so the date the clerk typed does not show. And "
                    "`move_outs_list`'s window is CLOSED ACCOUNTS, so an unfinished "
                    "move-out is in no list at all",
            ),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(record(reads_committed=1)),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
]

# ───────────────── EDGE · the three the ask names one row each ─────────────
SCENARIOS += [
    Scenario(
        id="E1",
        group="EDGE",
        title="a master account with OPEN SUB-ACCOUNTS is WARNED, and closes "
              "(PO 2026-09-20, OQ-CUS-12515 option (b))",
        # ⚠ **THIS ROW ASSERTED THE REFUSAL UNTIL 2026-09-20 AND IS REWRITTEN
        # RATHER THAN DELETED.** `DEF-CUS-5930` was a master closing over two
        # live tenants IN SILENCE; the fix refused it, and the PO ruled that
        # refusal out — verbatim, *"option B - give a warning and allow it; if
        # owner has sold the property to new owner then we are transfering all
        # libalities and ownership to new owner"*. Where a property is SOLD the
        # act is a TRANSFER, which carries the account and its liabilities to
        # the new owner with the tenants untouched, so the case the refusal
        # protected against already has its own flow.
        #
        # **The contract this row guards is therefore still real and it has
        # simply moved: a clerk is TOLD.** A row that vanished would take the
        # coverage with it, and the silence is what the defect actually was.
        #
        # The count is still DERIVED from the premises and never stored, so it
        # is right on the day a tenant moves in and on the day one moves out
        # with nobody maintaining it (BR-CUS-171, PO 2026-08-27, closing
        # OQ-531).
        estate=Estate(with_master=True, sub_accounts=2),
        steps=Steps(final_reads=None, final_bill=None, standby=False),
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent(
                "nothing refuses this any more — PO 2026-09-20 closed OQ-CUS-12515 on "
                "option (b). What the clerk reads is asserted as a WARNING under "
                "`settlement_money` below, by its code and its count"
            ),
            landing=Report(),
            settlement_money=Expect(
                {
                    "open_sub_accounts": 2,
                    # ⚠ **THE WARNING BY NAME AND BY COUNT, NEVER "a warning".**
                    # Every move-out comes back carrying several — the five in
                    # `MOVE_OUT_UNAVAILABLE` among them — so asserting that the
                    # list is non-empty would pass on a response that never
                    # mentions sub-accounts, and would go on passing after this
                    # rule was deleted. And asserting the CODE alone would pass
                    # on a warning that fired over a count of nobody, which is
                    # the other false pass this pair exists for.
                    "open_sub_accounts_warning": "master_closed_over_open_sub_accounts",
                    "open_sub_accounts_warned_count": 2,
                },
                why="the count comes from the premises and never from a stored column, and "
                    "the warning carries the SAME number — one definition of an open child "
                    "(DEF-CUS-5901's defect class refused)",
            ),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(
                CLOSED,
                why="⚠ THE OTHER HALF OF THE RULING. Asserting only the warning would pass "
                    "over an account that never closed, and asserting only the commit would "
                    "pass with the rule deleted entirely — every move-out commits now. The "
                    "landlord's own account really goes terminal, and its tenants do not "
                    "(they are not this account, and nothing cascades)",
            ),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=0, state=None)),
            move_record=Expect(
                record(),
                why="the numbered record is now LAWFUL and its absence would be the defect. "
                    "It was `None` here until 2026-09-20, when the move it records stopped "
                    "being forbidden",
            ),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="E2",
        group="EDGE",
        title="dated BEHIND an already-issued bill — BR-BIL-004 refuses at the commit",
        # p110: *"Whether an issued bill blocks this move-out cannot be checked
        # here. Billing has no invoices table, so the screen genuinely does not
        # know — the server answers it at the commit, and every move-out warns
        # that the check could not run."*
        #
        # ⚠ **THE SEAM IS WIRED (DEF-035) AND THE DRAWING'S REASON IS STALE.**
        # `seams.last_issued_invoice_period_end` resolved `apps.billing.SERVICES`
        # — the resolver's default kind — while billing publishes reads in
        # `selectors`, so it answered None on every call for weeks and the
        # caller dutifully recorded *not checked*. Two words were wrong. This
        # row drives the seam with a real period end and asserts the refusal.
        estate=Estate(),
        steps=Steps(moved_out_on="2025-12-15", final_reads=None, final_bill=None,
                    standby=False),
        blocked_on=(),
        expect=declares(
            outcome=Expect("refused"),
            refusal_name=Expect(
                "customers.account.move_out_behind_issued_bill",
                why="BR-BIL-004 — issued bills are untouched; corrections route via J6, "
                    "never via move-out backdating",
            ),
            landing=Silent("a refused move-out has no settlement"),
            settlement_money=Silent("nothing was settled"),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect({"behavior_class": "billable", "closed_at": None}),
            unit_after=Silent("nothing moved"),
            final_reads=Expect(reads(taken=0, state=None)),
            move_record=Expect(None),
            close_impact=Report(),
            friction=Report(
                why="p110 draws this as *cannot be checked here* — the clerk fills six "
                    "steps and learns at the commit that the date was never allowed"
            ),
        ),
    ),
    Scenario(
        id="E3",
        group="EDGE",
        title="a caller that names a SERVICE REQUEST — the door links it; the wizard "
              "has no request to send (PO 2026-09-22)",
        # ⚠ **THIS ROW ASSERTED THE WIZARD SENDING THE LINK UNTIL 2026-10-11,
        # AND A PO RULING THREE DAYS AFTER IT WAS WRITTEN TOOK AWAY THE THING
        # IT WAS WAITING FOR.** `MOVE_OUT_FIELDS` accepts `service_request_id`,
        # `services.move_out` reads it and `moves.record_move` stores it
        # (`CR-094-BRC01`, `BR-CUS-080`) — that half is built and asserted on
        # `move_record` below. The other half was *"the wizard never sends
        # one"*, red since the row was written on 2026-09-19.
        #
        # **PO 2026-09-22, verbatim: *"Option (b) — remove all three
        # permanently"*** — move-out, transfer and disconnect are gone from the
        # service request's Approve modal (`BR-CUS-091` SUPERSEDED IN PART;
        # decision log *"TWO PO ANSWERS: THE APPROVE MODAL LOSES THREE
        # OUTCOMES"* and *"WHERE A MOVE-OUT, A TRANSFER AND A DISCONNECT
        # START"*). A move-out now starts at the ACCOUNT's own door, and a
        # request describing one is *"closed against it by hand"* — the PO was
        # shown that cost and chose it. So no screen hands the move-out wizard
        # a request, and a wizard that sent one would be sending a link from
        # nowhere. The FRONT-END half is now asserted the way the product was
        # ruled to be: the wizard sends NO `service_request_id`.
        estate=Estate(from_request=True),
        steps=Steps(final_reads=ONE_READ, final_bill=None, standby=False),
        blocked_on=(),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing refuses; a caller that names a request is linked"),
            landing=Silent("not this row's subject"),
            settlement_money=Expect(
                {"wizard_sends_service_request_id": False},
                why="the FRONT-END half, read out of `MoveOutWizard.tsx` itself. PO "
                    "2026-09-22 (*\"Option (b) — remove all three permanently\"*) removed the "
                    "request-to-move-out door, so the wizard has no request to send; a "
                    "wizard that sent one again needs a ruling that reverses that one. The "
                    "backend half is asserted on `move_record` below",
            ),
            deposit_interest=Silent("no deposit on this row"),
            shortfall_path=Silent("not this row's subject"),
            books_and_payments=Expect(NO_BOOKS),
            account_status=Expect(CLOSED),
            unit_after=Expect(unit_after(standby=False)),
            final_reads=Expect(reads(taken=1, state="taken")),
            move_record=Expect(
                record(reads_committed=1, request_linked=True),
                why="`BR-CUS-080`'s child half — the record names the application it "
                    "fulfils, at the only moment this table has",
            ),
            close_impact=Report(),
            friction=Report(),
        ),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# ⬛ WHAT THIS SUITE DECLARES UNTESTABLE — NAMED, NEVER SILENTLY SKIPPED
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **A SCENARIO THAT CANNOT FAIL IS WORSE THAN ONE THAT IS NOT THERE**
#: (hard-won law 7). Each of these is printed on every run, with its reason, so
#: a reader counting green rows also reads what nobody checked.
UNTESTABLE: tuple[dict[str, str], ...] = (
    {
        "id": "U1",
        "what": "Whether a clerk can do any of this ON A SCREEN",
        "why": (
            "This suite drives the SERVICES the six steps post to and reads PostgreSQL "
            "back. It never opens a browser, so it cannot see a radio that renders "
            "disabled, a figure that renders as a dash, a step that cannot be reached or "
            "a `Save & exit` that loses what was typed. The PO's own words were *"
            "\"ensure clark is able to perform all these task from screen\"*, and the "
            "half this answers is *can the product do it at all*. **Hard-won law 6 — "
            "diff the running app against the drawing — is the other half and no gate in "
            "this repository performs it.** Two rows reach into the front end for a "
            "single fact each (E3's payload field, P1's resume handle) and both say so."
        ),
    },
    {
        "id": "U2",
        "what": "The refund actually reaching the customer",
        "why": (
            "`refund_disposition` RECORDS a decision — a method, an amount, an address — "
            "and writes an `audit_log` row. It moves no money: there is no "
            "`final_settlements` table, customers writes no payment row and no journal "
            "line, and payments has no refund execution path this module can reach. So "
            "L2 and D3 prove the ARITHMETIC of a refund and nothing proves a dollar can "
            "leave the building."
        ),
    },
    {
        "id": "U3",
        "what": "What the customer is told",
        "why": (
            "`notifications_seam.queue_move_out_final` writes an outcome row keyed on the "
            "move record, and `email_move_out_final` has been seeded on every tenant "
            "since 2026-08-16. p114 draws four messages and states the cost itself: "
            "***Queued is not sent. Rows are written and no sender picks them up.*** "
            "This suite counts what the commit queues and prints the codes; it cannot "
            "assert delivery, because nothing delivers."
        ),
    },
    {
        "id": "U4",
        "what": "\u2705 CLOSED 2026-09-20 \u2014 the move-out REASON p110 draws five options for",
        "why": (
            "**This entry is kept rather than deleted, so the change is greppable.** It "
            "read: *\"`MOVE_OUT_FIELDS` has no reason field and `accounts.close_reason` "
            "is PROPOSED-SCHEMA in B2 with no migration. There is nothing to read back, "
            "so there is nothing to assert.\"* The PO ruled on 2026-09-20 (option A) and "
            "migration `customers/0058` built the column; `reason` is an accepted field "
            "on the move-out door, and the five codes are asserted end to end in "
            "`tests/test_br_cus_030_close_reason.py`. ⚠ **This suite still asserts "
            "nothing about it**, deliberately: the twenty-seven rows declare thirteen "
            "dimensions and the reason is none of them, so adding it here would make "
            "every row incomplete for a fact its own file already covers."
        ),
    },
    {
        "id": "U5",
        "what": "BR-CUS-096's held excess, on a real dispute — SUSPENDED 2026-10-11",
        "why": (
            "BR-CUS-096 is SUSPENDED by PO ruling 2026-10-11 (*\"remove it fo time being "
            "and process the refund\"*). Nothing in this product stores a disputed AMOUNT "
            "— no model, no `db_table`, no seam, no publisher — so `_open_dispute_total` "
            "now answers 0.00 and L5 lands `refund_due`. `refused_excess` returns only "
            "when a dispute store is PUBLISHED, which this suite cannot build; the "
            "published-store hold is pinned in `test_w5_move_out_settlement`. ⚠ "
            "**`metering`'s `disputed_at` on a meter read is NOT this**: that is a "
            "quantity in dispute and BR-CUS-096 conditions on an amount, so wiring it "
            "would hold a refund because somebody queried a dial."
        ),
    },
)


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD ONE SCENARIO NEEDS — built through the owning services
# ═══════════════════════════════════════════════════════════════════════════
#: The per-service base charge every plan in this suite carries. A real figure
#: on a real plan, so C1's `vacant_base_charges` has something to state and
#: O1's `prepare_final_bill` has something to price.
BASE_CHARGE = D("20.00")


def _published_plan(tenant: Any, services: list[str], name: str) -> Any:
    """A published plan with a tariff and a BASE CHARGE per service.

    The base charge matters twice: `close_impact_for` reads the plan's own
    configured figures VERBATIM through `seams.plan_detail` for p114's vacant
    line, and `prepare_final_bill` needs something to price for O1.
    """
    # ⚠ **THE PLAN'S OWN START DATE IS SEEDED, AND WITHOUT IT THE ORDER GROUP
    # CANNOT REACH ITS SUBJECT.** `resolution_catalogue.plan_version_facts`
    # records the divergence in as many words: a published plan with no
    # `effective_from` *"bills forever on the live path and refuses at R1 on
    # this one"* — `R1: account … has no plan version in force on <date>`. That
    # divergence is REPORTED elsewhere and is not this suite's subject; what
    # made it reachable here is that the fixture built a plan the PRODUCT no
    # longer builds, because `rating/0024` (DEF-494) back-fills a start date
    # onto every published plan a real tenant holds. So this line makes the
    # seeded world match the shipped one rather than hiding a defect: a plan
    # with no start date is not a state a tenant of this product is in.
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={
            "code": name.lower().replace(" ", "-")[:40],
            "status": "published",
            "effective_from": date(2024, 1, 1),
        },
    )
    for code in services:
        service = tenancy_models.Service.objects.get(code=code)
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant=tenant, name=f"{name} — {code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
        # ⚠ **THE BASE CHARGE IS ON `PlanService`, NOT ON THE RATE SCHEDULE**,
        # and `rating.selectors.plan_detail` — which is what `close_impact_for`
        # reads VERBATIM for p114's vacant line — projects it from there. A
        # figure written on the schedule instead is a plan whose own page shows
        # no base charge at all.
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant, rate_plan=plan, service=service,
            defaults={"base_charge": BASE_CHARGE, "currency": "USD"},
        )
        # ⚠ `DEF-CUS-9061` — AND WHERE A BILL READS IT. Since `DEF-BIL-7170`
        # (2026-09-28) a base comes only from the service's `is_base` charge
        # code (BR-RAT-088), and since `18e1069f2` (2026-09-30) a base nobody
        # declared bills `$0.00` with a warning — so O1 priced `$76.08` and read
        # as a real gap. The SAME `$20.00`, unscoped and one price for all
        # sizes; `get_or_create` because every plan here shares the tenant.
        rating_models.Charge.objects.get_or_create(
            tenant=tenant,
            code=f"BASE-{code.upper()}-MOVEOUT",
            defaults={
                "name": f"{code.title()} base",
                "charge_type": "recurring",
                "amount_rule": "flat",
                "amount": BASE_CHARGE,
                "service": service,
                "is_base": True,
            },
        )
        # ⚠ **A PUBLISHED PLAN WITH NO TARIFF *VERSION* IS ENOUGH TO OPEN AN
        # ACCOUNT AND NOT ENOUGH TO BILL ONE** — the move-in suite learned the
        # same thing and wrote it down, which is why this is here rather than
        # discovered twice. `BR-RAT-007`: a bill prices on the version in force
        # at the SERVICE date, with no fallback to today's prices, so without
        # this the ORDER group's `preview_final_bill` refuses
        # `tariff_has_no_version_in_force_at_service_date` and the order trap
        # is never reached.
        #
        # ⚠ **THE PRICE IS NOT A COLUMN ON THE VERSION.** A flat rate is stored
        # as ONE 0→∞ tier (`BR-RAT-032`), and a fixture that invented a
        # `unit_price` column on the version is how a whole seam defect
        # surfaced once already.
        version, made = rating_models.TariffVersion.objects.get_or_create(
            tenant=tenant,
            tariff=tariff,
            effective_from=date(2024, 1, 1),
            defaults={
                "model": "flat",
                "base_charge": BASE_CHARGE,
                # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the code
                # above — an unnamed schedule bills a `$0.00` base.
                "base_charge_code": rating_models.Charge.objects.get(
                    tenant=tenant, code=f"BASE-{code.upper()}-MOVEOUT"
                ),
                "uom": "kWh" if code == "electric" else "kgal",
                "currency": "USD",
            },
        )
        if made:
            rating_models.RateTier.objects.create(
                tenant=tenant, tariff_version=version, seq=1,
                from_qty=D("0"), to_qty=None, unit_price=D("0.120000"),
            )
            # ⚠ **THE SCHEDULE'S SIZE AXIS, AND WITHOUT IT THE RULED CHAIN
            # REFUSES EVERY ACCOUNT AT R3** — *"connection size 'E-1P-100' has
            # no row on the rate schedule version …"*. `a_meter` gives every
            # meter the service's SMALLEST RATIFIED BAND (`BR-TEN-171`), which
            # is what a real meter has, and `rate_size_rows` is where a
            # schedule states which sizes it serves. `DEF-2799` is this exact
            # fixture gap one layer up — it refused **47 of 47** accounts of a
            # whole seeded utility — and `apps/rating/sample_data.py`
            # `sample_size_rows` is the shape copied here: **the PLATFORM's
            # ratified ladder for the service, every row with a NULL
            # `minimum_bill`**, which is r10's em-dash and means *this size IS
            # served and has no floor*. Never `$0.00`, and never the one size
            # this unit's meter happens to be — a fixture serving only today's
            # meter starts refusing the first time another is fitted.
            for size_code in asset_seams.service_size_class_codes(code):
                rating_models.RateSizeRow.objects.get_or_create(
                    tenant=tenant, tariff_version=version, size_class=size_code,
                    defaults={"minimum_bill": None, "currency": "USD"},
                )
    return plan


def _account_type_for(unit_type: str) -> str:
    return "commercial" if unit_type.startswith("commercial") else "residential"


def _occupant(actor: Any, unit_id: Any, *, name: str, opened_at: str = OPENED,
              unit_type: str = "residential") -> dict[str, Any]:
    """One occupying account, through the real S18 door."""
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": _account_type_for(unit_type),
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(
                name, account_type=_account_type_for(unit_type)
            ),
        },
    )


def _post_receivable(actor: Any, account_id: Any, amount: Decimal, *, tag: str) -> bool:
    """A REAL debit on the AR account for one customer account.

    ⚠ **THROUGH `ledger.posting.post`, WHICH IS THE ONLY THING ALLOWED TO WRITE
    A JOURNAL LINE** (CLAUDE.md rule 5). A prior balance and a sibling's debt
    both come from `seams.ar_positions`, which sums posted lines against the AR
    designation — so a suite that wanted either had to either run a whole bill
    run or write the books by hand. This does neither: it hands the posting
    service a balanced pair under its own contract and lets it refuse anything
    it does not like.

    Returns False where the tenant has no AR designation at all, which is a
    deployment fact the caller REPORTS rather than a zero it assumes
    (`ar_positions`' own `available=False`, DEF-127's lesson).
    """
    from apps.ledger import chart, posting
    from apps.ledger import selectors as ledger_selectors

    ar = ledger_selectors.gl_account_id_for_designation(chart.AR)
    contra = ledger_selectors.gl_account_id_for_designation(chart.OPENING_CLEARING)
    if ar is None or contra is None:
        return False
    source_id = str(account_id)
    request = posting.PostingRequest(
        posting_key=posting.posting_key(
            source_type="opening_balance", source_id=f"{source_id}-{tag}", event="opened"
        ),
        entry_date=date.fromisoformat(PERIOD_START),
        posted_at=datetime.fromisoformat(f"{PERIOD_START}T00:00:00+00:00"),
        currency="USD",
        source_type="opening_balance",
        source_id=source_id,
        memo=f"{tag}: the position this scenario starts from",
        lines=(
            posting.PostingLine(
                ledger_account_id=ar, side=ledger_models.SIDE_DEBIT, amount=amount,
                source_type="opening_balance", source_id=source_id, account_id=source_id,
            ),
            posting.PostingLine(
                ledger_account_id=contra, side=ledger_models.SIDE_CREDIT, amount=amount,
                source_type="opening_balance", source_id=source_id,
            ),
        ),
    )
    posting.post(request, actor=actor)
    return True


@dataclass
class World:
    premises: dict[str, Any]
    unit: dict[str, Any]
    plan: Any
    account: dict[str, Any]
    master: dict[str, Any] | None
    subs: list[dict[str, Any]]
    request: Any | None
    asset_ids: list[str]
    notes: list[str] = field(default_factory=list)


def build_world(admin: Any, tenant: Any, scenario: Scenario) -> World:
    """Everything the scenario needs standing, through the owning services."""
    estate = scenario.estate
    seed_config()
    services = sorted({svc for _no, svc, _uom in estate.meters}) or ["electric"]
    plan = _published_plan(tenant, services, f"Move-out {scenario.id}")

    # ⚠ **THE PREMISES TYPE DECIDES WHETHER A MASTER ACCOUNT MAY EXIST — PO
    # 2026-10-02 (`CR-162-BRC10` Q1, decision log *"NEW CONNECTION — THE PO'S
    # SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*), verbatim: *"apartment
    # complex, commercial building, mixed-use and any type able to hold several
    # units get a master account … a single-family home gets none."* Every row
    # here was built on `single_family`, so from `728fe0248` the rows that need
    # an owner's master (E1, SH3, C1, C2) were refused
    # `customers.account.master_not_for_single_family` before they started, and
    # walked an ordinary tenant instead. A row with a master stands on a type
    # whose seeded account kind is MASTER; every other row keeps the house.
    premises = make_premises(
        admin,
        services_available=sorted(set(services) | {"electric", "water"}),
        premises_type="apartment_complex" if estate.with_master else "single_family",
        address_line="1408 Elm Street",
        city="Silver Creek",
        postal_code="78611",
    )
    unit = make_unit(
        admin, premises["id"], label=estate.unit_label, unit_type=estate.unit_type,
        services=services,
    )
    # ⚠ **`effective_from` IS STATED, AND WITHOUT IT NOTHING IN THIS SUITE CAN
    # BE BILLED.** `_apply_unit_plan` dates an assignment from the tenant's
    # TODAY when the caller states no date, so a plan attached now is not in
    # force across a period that ended in January — `BR-RAT-007` prices on the
    # terms in force AT THE SERVICE DATE with no fallback to today's plan,
    # *"because that would silently re-price history"*. The move-in suite met
    # the same wall and recorded it; this is that lesson used rather than
    # learned twice.
    metering_services.assign_unit_plan(
        admin, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2024-01-01"}
    )
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    # ── `DEF-BIL-8702` · THE UNIT BILLS ON A CYCLE ─────────────────────────
    # PO ruling 2026-10-01: a final bill for an account on NO cycle is refused
    # (*"Refuse until the account has a cycle (same as first bill)"*), and the
    # move-out wizard's preview now refuses it too. Every scenario here moves
    # out of an ordinary billed home, so its unit is put on a cycle — a
    # route-less stamp, which is the product's own explicit statement that a
    # unit bills on a cycle. **No figure moves:** the preview below states
    # `cycle_days=31`, which wins over any read of the cycle's calendar.
    from apps.metering import models as metering_models

    cycle = metering_models.Cycle.objects.create(
        tenant=tenant, code=f"MO-{scenario.id}", start_day=1, days_to_complete=31,
        bill_day=1, due_days=21,
    )
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    if estate.standby_before:
        # The BEFORE state of the PO's own dropdown. Through the ASSIGN-PLAN
        # door because it is the only one that accepts the field at all — see
        # `STANDBY_DOOR`, which is this suite's finding rather than its choice.
        metering_services.assign_unit_plan(
            admin, unit["id"],
            {"tariff_id": str(plan.id), "vacant_standby_auto": True,
             "effective_from": "2024-01-01"},
        )

    asset_ids: list[str] = []
    for asset_no, service, uom in estate.meters:
        asset = a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
        asset_ids.append(str(asset["id"] if isinstance(asset, dict) else asset))

    for asset_no, day, value, consumption, days in estate.read_history:
        target = next(
            (aid for aid, (no, _s, _u) in zip(asset_ids, estate.meters) if no == asset_no), None
        )
        if target is not None:
            commit_read(
                admin, target, day=day, value=value,
                consumption=consumption, days_since_prior=days,
            )

    notes: list[str] = []
    master: dict[str, Any] | None = None
    if estate.with_master:
        try:
            # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
            top_up_homes(admin, premises["id"])
            master = customers_services.create_master_account(
                admin,
                {
                    "premises_id": str(premises["id"]),
                    "account_type": "commercial",
                    "opened_at": OPENED,
                    "contact": {"full_name": "Elm Street Holdings LLC"},
                    "customer": identity_fixtures.customer_block(
                        "Elm Street Holdings LLC", kind="company"
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001 — REPORTED, never swallowed
            notes.append(f"the master account could not be created: {type(exc).__name__}: {exc}")

    subs: list[dict[str, Any]] = []
    for index in range(estate.sub_accounts):
        sub_unit = make_unit(
            admin, premises["id"], label=f"Sub {index + 1}", unit_type="residential",
            services=services,
        )
        metering_services.assign_unit_plan(
            admin, sub_unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2024-01-01"},
        )
        subs.append(_occupant(admin, sub_unit["id"], name=f"Tenant {index + 1}"))

    # ── the account this scenario closes ────────────────────────────────────
    leaving_unit = unit
    if estate.with_master and estate.sub_accounts:
        # BR-CUS-171's subject is the MASTER, so on E1 the account walked is the
        # master itself and the sub-accounts are its open children.
        account = master if master is not None else _occupant(
            admin, leaving_unit["id"], name="Okafor, D."
        )
    else:
        account = _occupant(admin, leaving_unit["id"], name="Okafor, D.",
                            unit_type=estate.unit_type)

    row = customers_models.Account.objects.get(pk=account["id"])
    if estate.deposit is not None:
        # The register and its BR-CUS-050 receipt date, exactly as a move-in
        # leaves them. `deposit.take` is the move-in door's and there is no
        # door that puts a deposit on an account that already exists.
        customers_models.Account.objects.filter(pk=row.pk).update(
            deposit_on_file=estate.deposit,
            deposit_received_on=date.fromisoformat(estate.deposit_received_on),
        )
    if estate.interest_rate_percent is not None:
        from apps.tenancy import services as tenancy_services

        tenancy_services.save_settings_family(
            admin, "billing-defaults",
            {"deposit_interest_rate_annual": estate.interest_rate_percent},
        )
    if estate.prior_balance is not None:
        if not _post_receivable(admin, row.pk, estate.prior_balance, tag="prior"):
            notes.append("this tenant has no `accounts_receivable` designation, so the prior "
                         "balance could not be posted and reads 0.00")
    if estate.sibling_debt is not None:
        sibling_unit = make_unit(admin, premises["id"], label="Sibling", services=services)
        metering_services.assign_unit_plan(
            admin, sibling_unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2024-01-01"},
        )
        sibling = _occupant(admin, sibling_unit["id"], name="Okafor, D. (second address)")
        # BR-CUS-054's N:M link is HOW a sibling is found — one customer, two
        # accounts, exactly as the import writes them.
        customer = customers_models.Customer.objects.create(
            tenant=tenant, display_name="Okafor, D. — both addresses"
        )
        for account_id in (row.pk, sibling["id"]):
            customers_models.CustomerAccount.objects.create(
                tenant=tenant, customer=customer, account_id=account_id
            )
        if not _post_receivable(admin, sibling["id"], estate.sibling_debt, tag="sibling"):
            notes.append("the sibling's debt could not be posted (no AR designation)")

    request = None
    if estate.from_request:
        request = service_request_service.create_request(
            admin,
            {
                "applicant_name": "Okafor, D.",
                "applicant_kind": "person",
                # ⚠ **TWO VOCABULARIES, ONE WORD APART.** A PREMISES is
                # `single_family`; a service REQUEST's property type is one of
                # `models.ServiceRequest.PROPERTY_TYPES`, and `single_family`
                # is not among them. The door refuses by name rather than
                # storing a value nothing can read back, which is right — and
                # it is a real thing a clerk moving between the two screens
                # meets.
                "property_type": "rental_tenant_applying",
                "address_as_given": "1408 Elm Street, Silver Creek, TX 78611",
            },
        )

    return World(premises=premises, unit=unit, plan=plan, account=account, master=master,
                 subs=subs, request=request, asset_ids=asset_ids, notes=notes)


def compose(scenario: Scenario, world: World) -> dict[str, Any]:
    """**The six steps, as ONE payload** — what `POST /accounts/{id}/move-out`
    receives when the clerk presses the button on step 6."""
    steps = scenario.steps
    payload: dict[str, Any] = {"moved_out_on": steps.moved_out_on}
    if steps.final_reads is not None:
        payload["final_reads"] = [dict(row) for row in steps.final_reads]
    if world.request is not None:
        payload["service_request_id"] = str(world.request.id)
    # CR-185-BRC10 — POSTED AT COMMIT (coordinator ruling 2026-10-14): step 3's
    # tie-back rides the commit, exactly as the wizard sends it.
    if steps.shortfall_path == mos.SHORTFALL_TRANSFER:
        payload["shortfall_path"] = steps.shortfall_path
    return payload


# ═══════════════════════════════════════════════════════════════════════════
# THE READBACK — PostgreSQL, never a service's own return value
# ═══════════════════════════════════════════════════════════════════════════
def _display(payload: Any, *path: str) -> str | None:
    """A `{stored, display}` money pair's DISPLAY half, dug out by path.

    CLAUDE.md rule 2 — money is stored to four decimals and DISPLAYED to two —
    so every money assertion in this suite compares the two-place string a
    clerk reads. Comparing the stored half would let `182.9000` and `182.90`
    disagree about nothing.
    """
    node: Any = payload
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, dict):
        return node.get("display")
    return node


def observe(scenario: Scenario, world: World, outcome: dict[str, Any]) -> dict[str, Any]:
    """Everything the checkers judge, read out of the tables."""
    account_id = world.account["id"]
    seen: dict[str, Any] = dict(outcome)

    row = customers_models.Account.objects.filter(pk=account_id).select_related("status").first()
    seen["account_status"] = (
        None
        if row is None
        else {
            "behavior_class": row.status.behavior_class,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "agreements_open": customers_models.ServiceAgreement.objects.filter(
                account_id=account_id, ended_on__isnull=True
            ).count(),
            "final_read_state": row.final_read_state,
        }
    )

    # ── the unit, after ─────────────────────────────────────────────────────
    unit_row = metering_models.Unit.objects.filter(pk=world.unit["id"]).first()
    occupying = [
        acc
        for acc in customers_models.Account.objects.filter(
            unit_id=world.unit["id"]
        ).select_related("status")
        if customers_services.is_occupying(acc.status)
    ]
    from apps.metering import seams as metering_seams

    fitted = list(metering_seams.assets_on_unit(world.unit["id"]))
    seen["unit_after"] = (
        None
        if unit_row is None
        else {
            "vacant": not occupying,
            # BR-MET-044 — the plan lives on the UNIT, so *stays* means the
            # column still names one after the close.
            "plan_stays": bool(getattr(unit_row, "rate_plan_id", None)),
            "meters_stay": len(fitted) == len(scenario.estate.meters),
            "meter_count": len(fitted),
            "standby": bool(unit_row.vacant_standby_auto),
        }
    )

    # ── the readings ────────────────────────────────────────────────────────
    read_rows = list(
        metering_models.MeterRead.objects.filter(
            asset_id__in=world.asset_ids, superseded_by_id__isnull=True
        )
    )
    by_context: dict[str, int] = {}
    for read in read_rows:
        key = read.event_context or "none"
        by_context[key] = by_context.get(key, 0) + 1
    seen["final_reads"] = {
        "move_out": by_context.get("move_out", 0),
        "final_read_state": (seen["account_status"] or {}).get("final_read_state"),
    }
    seen["read_contexts"] = by_context

    # ── the record ──────────────────────────────────────────────────────────
    record_row = (
        moves.MoveRecord.objects.filter(account_id=account_id, kind=moves.KIND_MOVE_OUT)
        .order_by("-performed_at")
        .first()
    )
    seen["move_record"] = (
        None
        if record_row is None
        else {
            "kind": record_row.kind,
            "move_no": record_row.move_no,
            "prefix": (record_row.move_no or "")[:4],
            "reads_committed": record_row.reads_committed,
            "request_linked": record_row.request_id is not None,
            "effective_on": (
                record_row.effective_on.isoformat() if record_row.effective_on else None
            ),
        }
    )

    # ── the books and the drawer ────────────────────────────────────────────
    # ⚠ Counted over THE WHOLE TENANT rather than over this account, because
    # what is being asserted is that the move-out and its shortfall decision
    # wrote NOTHING — and a line posted against the master, the sibling or a
    # suspense account would be invisible to an account-scoped count.
    lines_now = ledger_models.JournalLine.objects.count()
    payments_now = payment_models.Payment.objects.count()
    decision = seen.get("decision") or {}
    seen["books_and_payments"] = {
        "journal_lines": lines_now - int(seen.get("journal_lines_before") or 0),
        "payments": payments_now - int(seen.get("payments_before") or 0),
        "persisted": decision.get("persisted", False) if decision else False,
        # CR-185-BRC10 — posted at COMMIT: step 3's decision previews, and the
        # move-out's own answer says whether the books moved.
        "posted": bool(
            ((decision.get("posting") or {}).get("posted", False) if decision else False)
            or ((seen.get("result") or {}).get("balance_to_owner") or {}).get("posted")
        ),
    }

    # ── the settlement, as this pass got it ────────────────────────────────
    settlement = seen.get("settlement") or {}
    seen["landing"] = settlement.get("landing")
    seen["gaps"] = list(settlement.get("gaps") or ())
    seen["settlement_money"] = {
        "outstanding": _display(settlement, "everything_outstanding", "total"),
        "final_bill": _display(settlement, "everything_outstanding", "final_bill"),
        "applied": _display(settlement, "what_is_applied", "total"),
        "deposit_held": _display(settlement, "what_is_applied", "deposit_held"),
        "deposit_interest": _display(settlement, "what_is_applied", "deposit_interest"),
        "net": _display(settlement, "verdict", "net"),
        "shortfall": _display(settlement, "verdict", "shortfall"),
        "excess": _display(settlement, "verdict", "excess"),
        "refund_amount": _display(settlement, "verdict", "refund_amount"),
        "settled_from_deposit": _display(settlement, "verdict", "settled_from_deposit"),
        "transfer_to_sibling": _display(settlement, "verdict", "transfer_to_sibling"),
        "sibling_after_transfer": _display(settlement, "verdict", "sibling_after_transfer"),
        "step_4_live": settlement.get("step_4_live"),
        "open_sub_accounts": settlement.get("open_sub_accounts"),
    }
    seen["settlement_money"].update(seen.get("extra_money") or {})
    seen["deposit_interest"] = seen.get("deposit_interest_figure")

    # ── the close impact, p115's six ────────────────────────────────────────
    seen["close_impact"] = seen.get("close_impact_payload") or {}
    return seen


# ═══════════════════════════════════════════════════════════════════════════
# THE CHECKERS — one per dimension, and every row goes through all thirteen
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Check:
    dimension: str
    verdict: str  # PASS · FAIL · SILENT · REPORT · BLOCKED
    detail: str


def _pass(dim: str, detail: str = "") -> Check:
    return Check(dim, "PASS", detail)


def _fail(dim: str, detail: str) -> Check:
    return Check(dim, "FAIL", detail)


def _subset(dim: str, want: dict[str, Any], seen: dict[str, Any] | None) -> Check:
    """**EVERY KEY THE ROW DECLARED, COMPARED — and no key it did not.**

    A row declares the facts it is about; a dimension's observation carries
    more than any one row cares about. Comparing the whole dict would make
    every row re-declare everything; comparing nothing would be a check that
    cannot fail. So: the declared keys, all of them, by name, and the ones
    that differ are named in the failure rather than summarised.
    """
    if seen is None:
        return _fail(dim, f"nothing was observed at all; wanted {want}")
    wrong = {key: (value, seen.get(key)) for key, value in want.items() if seen.get(key) != value}
    if wrong:
        return _fail(
            dim,
            "; ".join(f"{key}: wanted {value!r}, PostgreSQL holds {got!r}"
                      for key, (value, got) in sorted(wrong.items())),
        )
    return _pass(dim, ", ".join(f"{k}={v}" for k, v in sorted(want.items())))


def _refusal_text(refusal: Any) -> str:
    if refusal is None:
        return ""
    params = getattr(refusal, "params", None) or {}
    return " ".join(
        str(part)
        for part in (
            getattr(refusal, "message_key", None),
            getattr(refusal, "br_ref", None),
            getattr(refusal, "code", None),
            params,
            str(refusal),
        )
        if part
    )


def check_outcome(want: Expect, seen: dict[str, Any]) -> Check:
    got = "refused" if seen.get("refusal") is not None else "committed"
    if got != want.value:
        return _fail(
            "outcome",
            f"wanted the move-out to be {want.value}; it was {got}"
            + (f" — {_refusal_text(seen['refusal'])[:220]}" if got == "refused" else ""),
        )
    return _pass("outcome", got)


def check_refusal_name(want: Expect, seen: dict[str, Any]) -> Check:
    """**WHICH refusal, by message key or code — never *an error*.**

    A test that asserts *something was refused* passes on a typo, a timeout and
    a tenant-isolation failure alike. The row names the key, and the key has to
    appear in the refusal's own text.
    """
    text = _refusal_text(seen.get("refusal")) or str(seen.get("billing_problem") or "")
    if not text:
        return _fail("refusal_name", f"wanted a refusal naming {want.value!r}; nothing refused")
    if str(want.value) not in text:
        return _fail(
            "refusal_name",
            f"wanted a refusal naming {want.value!r}; got {text[:260]!r}",
        )
    return _pass("refusal_name", str(want.value))


def check_landing(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen.get("landing")
    if got == want.value:
        return _pass("landing", str(got))
    gaps = seen.get("gaps") or []
    return _fail(
        "landing",
        f"wanted {want.value!r}; the settlement states {got!r}"
        + (f" and gaps on {gaps}" if gaps else ""),
    )


def check_settlement_money(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("settlement_money", want.value, seen.get("settlement_money"))


def check_deposit_interest(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen.get("deposit_interest")
    if got is None:
        return _fail(
            "deposit_interest",
            f"wanted {want.value}; the engine answered None — BR-CUS-057 has no start date, "
            "no rate, or no day was stated (gaps: " + str(seen.get("gaps") or []) + ")",
        )
    if D(str(got)) != D(str(want.value)):
        return _fail("deposit_interest", f"wanted {want.value}; the engine gives {got}")
    return _pass("deposit_interest", str(got))


def check_shortfall_path(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("shortfall_path", want.value, seen.get("shortfall_path"))


def check_books_and_payments(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("books_and_payments", want.value, seen.get("books_and_payments"))


def check_account_status(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("account_status", want.value, seen.get("account_status"))


def check_unit_after(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("unit_after", want.value, seen.get("unit_after"))


def check_final_reads(want: Expect, seen: dict[str, Any]) -> Check:
    return _subset("final_reads", want.value, seen.get("final_reads"))


def check_move_record(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen.get("move_record")
    if want.value is None:
        if got is None:
            return _pass("move_record", "no record — nothing happened")
        return _fail(
            "move_record",
            f"a refused move-out left a record anyway: {got} (BR-SHL-019 — there must never "
            "be a record of a move that did not happen)",
        )
    if got is None:
        return _fail("move_record", "the move committed and wrote NO record (BR-CUS-150/151)")
    wanted = dict(want.value)
    prefix = wanted.pop("prefix", None)
    check = _subset("move_record", wanted, got)
    if check.verdict == "FAIL":
        return check
    if prefix is not None and not str(got.get("move_no") or "").startswith(prefix):
        # ⚠ **NOT A FAILURE OF THE MOVE.** `moves._allocate_move_no` is explicit:
        # *"A household must not be refused a move-in because nobody configured
        # numbering. The move is the regulated act; its reference is not."* So a
        # missing number is REPORTED here with the absence the row carries.
        return _fail(
            "move_record",
            f"wanted a reference starting {prefix!r}; the record carries "
            f"{got.get('move_no')!r} — the `move_out` number series is not configured on "
            "this tenant, so the move happened and only its reference is missing",
        )
    return _pass("move_record", f"{got.get('move_no')} · {got.get('reads_committed')} read(s)")


def check_close_impact(seen: dict[str, Any]) -> tuple[Check, list[str], list[str]]:
    """**p115's six consequences: stated or served, and NEVER defaulted.**

    The rule under the drawing's sentence, not the sentence: *"a blank
    consequence and a harmless one look identical once a screen guesses"*. So
    each of the six must be either a real measurement or an explicit `None`
    beside a reason — and a `0`, a `false` or an empty string standing in for a
    fact nobody took is the failure.

    Returns the verdict, WHICH of the six are now served, and which are not.
    Both lists are printed, because the drawing saying *all six arrive empty*
    while several now answer is news a reader wants (hard-won law 1 in the
    direction nobody expects: a STALE claim about an ABSENCE).
    """
    payload = seen.get("close_impact") or {}
    if not payload:
        return (
            _fail("close_impact", "the close-impact read answered nothing at all"),
            [],
            list(SIX_CONSEQUENCES),
        )
    #: Each of p115's six, mapped to the field `close_impact_for` serves for it.
    mapping = {
        "premises_occupancy_afterwards": "units_occupied_after",
        "owner_on_record": "owner_on_record",
        "vacant_charge_position": "vacant_base_charges",
        "payment_plan_progress": None,
        "what_happens_to_the_assets": None,
        "master_account_effect": "unit_falls_to",
    }
    served: list[str] = []
    absent: list[str] = []
    guessed: list[str] = []
    for name, field_name in mapping.items():
        if field_name is None:
            absent.append(f"{name} (no field is served at all)")
            continue
        if field_name not in payload:
            absent.append(f"{name} (no field is served at all)")
            continue
        value = payload[field_name]
        if value is None:
            absent.append(f"{name} (served as an explicit absence)")
        elif value in (0, False, "", [], {}):
            # ⚠ **THE ONE THING THAT FAILS THIS CHECK.** DEF-669's own half:
            # `null` is NOT `true`, and a falsy stand-in for an unread fact is
            # the screen making a claim nobody took.
            guessed.append(f"{name} = {value!r}")
        else:
            served.append(name)
    if guessed:
        return (
            _fail(
                "close_impact",
                "a consequence was DEFAULTED rather than measured or stated: "
                + ", ".join(guessed),
            ),
            served,
            absent,
        )
    return (_pass("close_impact", f"{len(served)} of 6 served, {len(absent)} stated absent"),
            served, absent)


# ═══════════════════════════════════════════════════════════════════════════
# THE FRICTION LIST — what a clerk has to do that they should not have to
# ═══════════════════════════════════════════════════════════════════════════
def collect_friction(scenario: Scenario, world: World, seen: dict[str, Any]) -> list[str]:
    """Derived from the payload and the database, never from a screen.

    ⚠ **THIS SUITE NEVER OPENS A BROWSER**, so it cannot see one box feeding
    two keys, a prefill, or a radio that renders disabled. What it CAN see is a
    field the blueprint asks for that no door accepts, and a fact the clerk has
    to go and find somewhere else.
    """
    items: list[str] = []
    steps = scenario.steps
    settlement = seen.get("settlement") or {}

    if steps.forwarding_address and "forwarding" not in json.dumps(
        seen.get("decision") or {}, default=str
    ):
        items.append(
            "p113 asks for a FORWARDING ADDRESS on the collect path and no door accepts "
            "one — the reminders it says go there have nowhere to go"
        )
    if steps.shortfall_path == mos.SHORTFALL_PAYMENT_PLAN and not seen.get("plan_row_created"):
        items.append(
            "p113 asks for INSTALMENTS · FIRST PAYMENT DATE · AMOUNT EACH · THE CUSTOMER'S "
            "AGREEMENT on the payment-plan path; the decision records the word and none of "
            "the four, and no plan row is created"
        )
    if settlement.get("final_bill_stated_by_caller") is False:
        items.append(
            "the settlement was asked with no final bill, so it states no landing and step "
            "4's four radios refuse by name — `customers.move_out.no_shortfall` with "
            "`gaps: [final_bill_not_stated]`"
        )
    if scenario.steps.shortfall_path is not None and seen.get("decision"):
        items.append(
            # ✅ **CLOSED 2026-09-19 in `v2.313.2` — `DEF-CUS-5927`.** This
            # sentence read *"the SCREEN does not send one … a clerk on the
            # wizard gets a 409 on every path"* for the few hours between this
            # suite landing and the front-end half. It is kept, amended,
            # because a friction list that goes on naming a fixed defect is
            # how `DEF-CUS-5929` happened — a stale record nothing reads for
            # truth, which the next lane then builds from.
            "✓ `DEF-CUS-5927`, CLOSED 2026-09-19 (`v2.313.2`) — the SERVICE takes a final "
            "bill on the shortfall decision and the SCREEN now sends one, so these rows "
            "record what a clerk on the wizard can actually record. Measured in a browser "
            "on `AC-2026-00031`: the step-4 POST carries `final_bill` and `as_of` and is "
            "accepted; before the fix it carried `{path}` alone and answered 409 "
            "`customers.move_out.no_shortfall` on every path"
        )
    for gap in settlement.get("gaps") or ():
        items.append(f"the settlement could not be completed: {gap}")
    if scenario.estate.meters and seen["final_reads"]["final_read_state"] == "due":
        items.append(
            "the account closed with a reading still outstanding and nothing in the close "
            "raises the work of going to take it"
        )
    if seen.get("move_record") and not (seen["move_record"].get("move_no") or ""):
        items.append(
            "the move happened and carries NO reference — a clerk has nothing to quote "
            "(`move_out` number series not configured; the move is the regulated act, its "
            "reference is not)"
        )
    items.extend(world.notes)
    items.extend(
        note for note in (seen.get("notes") or ()) if note.startswith("the step-5 standby")
        or note == STANDBY_DOOR
    )
    return items


# ═══════════════════════════════════════════════════════════════════════════
# THE RUNNER — ONE function, twenty-seven rows, TWO passes each
# ═══════════════════════════════════════════════════════════════════════════
#: Proving the suite can fail: `MOVE_OUT_BREAK=L1:account_status` damages what
#: the runner OBSERVED for that one dimension before the checkers see it.
#: Corrupting the OBSERVATION rather than the DECLARATION is deliberate — it
#: proves the checker really reads PostgreSQL's answer and compares it, which
#: inverting a verdict would not.
BREAK = os.environ.get("MOVE_OUT_BREAK", "")

_BREAKERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "account_status": lambda s: (s["account_status"] or {}).__setitem__(
        "behavior_class", "occupying"
    ),
    "unit_after": lambda s: (s["unit_after"] or {}).__setitem__("plan_stays", False),
    "final_reads": lambda s: s["final_reads"].__setitem__("move_out", 99),
    "move_record": lambda s: s.__setitem__("move_record", None),
    "books_and_payments": lambda s: s["books_and_payments"].__setitem__("journal_lines", 2),
    "landing": lambda s: s.__setitem__("landing", "a_landing_that_does_not_exist"),
    "settlement_money": lambda s: s["settlement_money"].__setitem__("shortfall", "0.01"),
    "deposit_interest": lambda s: s.__setitem__("deposit_interest", D("999.99")),
    "outcome": lambda s: s.__setitem__("refusal", RuntimeError("broken on purpose")),
    "refusal_name": lambda s: s.__setitem__("refusal", None),
    "shortfall_path": lambda s: s.__setitem__("shortfall_path", {}),
    "close_impact": lambda s: s.__setitem__("close_impact", {}),
}


def _apply_break(scenario: Scenario, mode: str, seen: dict[str, Any]) -> str | None:
    if not BREAK or ":" not in BREAK:
        return None
    target, dimension = BREAK.split(":", 1)
    if target != scenario.id or dimension not in _BREAKERS:
        return None
    _BREAKERS[dimension](seen)
    return dimension


@dataclass
class Result:
    scenario: Scenario
    mode: str
    checks: list[Check]
    friction: list[str]
    notes: list[str]
    served: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.verdict == "FAIL"]


RESULTS: list[Result] = []


def _the_actor(scenario: Scenario, admin: Any, clerk: Any) -> Any:
    return clerk if scenario.steps.actor == "clerk" else admin


def _settlement_and_decision(
    scenario: Scenario, world: World, actor: Any, mode: str, seen: dict[str, Any]
) -> None:
    """Step 3 and step 4, run the way this PASS says the product is asked.

    **TODAY** — no `final_bill`, which is what the wizard sends.
    **WIRED** — the row's own figure, which is what billing's preview returns.
    """
    # ⚠ **`as_of` IS A `date`, NOT THE ISO STRING THE WIZARD POSTS.** The API
    # layer parses it (`api._settlement_as_of`) before the service ever sees
    # it; this suite calls the service, so it parses it here for the same
    # reason. Handing the string straight through raises `AttributeError:
    # 'str' object has no attribute 'year'` inside BR-CUS-057's engine — a
    # money path that crashes rather than refusing, which is worth knowing and
    # is NOT what this suite is about.
    kwargs: dict[str, Any] = {}
    if mode == MODE_WIRED and scenario.steps.final_bill is not None:
        kwargs = {
            "final_bill": scenario.steps.final_bill,
            "as_of": date.fromisoformat(scenario.steps.as_of),
        }
    try:
        seen["settlement"] = mos.settlement_for(actor, world.account["id"], **kwargs)
    except (errors.BizError, errors.ValidationError, errors.NotFoundError) as exc:
        seen["settlement"] = {}
        seen["settlement_refusal"] = exc
        return

    # BR-CUS-057's own figure, asked of the ENGINE directly as well as read off
    # the settlement — so a settlement that lost the term and a term that was
    # never computed are two different failures rather than one.
    seen["deposit_interest_figure"] = customers_selectors.deposit_interest_accrued(
        world.account["id"], date.fromisoformat(scenario.steps.as_of)
    ) if mode == MODE_WIRED else None
    seen["close_impact_payload"] = {
        key: seen["settlement"].get(key)
        for key in ("units_occupied_after", "owner_on_record", "owner_is_free_text",
                    "common_area_account_no", "vacant_base_charge", "vacant_base_charges",
                    "unit_falls_to")
        if key in seen["settlement"]
    }

    if scenario.steps.shortfall_path is None:
        return
    payload: dict[str, Any] = {"path": scenario.steps.shortfall_path}
    if mode == MODE_WIRED and scenario.steps.final_bill is not None:
        payload["final_bill"] = scenario.steps.final_bill
        payload["as_of"] = date.fromisoformat(scenario.steps.as_of)
    try:
        decision = mos.shortfall_decision(actor, world.account["id"], payload)
    except (errors.BizError, errors.ValidationError, errors.AuthError) as exc:
        seen["decision"] = {}
        seen["decision_refusal"] = exc
        seen["shortfall_path"] = {
            "path": scenario.steps.shortfall_path,
            "refused_for_role": isinstance(exc, errors.AuthError)
            or "role" in _refusal_text(exc).lower()
            or "permission" in _refusal_text(exc).lower(),
            "refusal": _refusal_text(exc)[:200],
        }
        return
    seen["decision"] = decision
    target = decision.get("target") or None
    seen["shortfall_path"] = {
        "path": decision.get("path"),
        "amount": (decision.get("amount") or {}).get("display"),
        "target": target,
        "target_resolved": bool(target and target.get("account_id")),
        "target_is_master_or_owner": bool(
            target and target.get("target") in mos.TRANSFER_TARGETS
        ),
        "tied_back_by_actor": bool((decision.get("tied_back_by") or {}).get("actor_user_id")),
        "dunning_tier": (decision.get("dunning") or {}).get("restarts_at_tier"),
        "escalates": (decision.get("dunning") or {}).get("escalates_to_disconnection"),
        "chased": (decision.get("dunning") or {}).get("chased"),
        # ⚠ p113's WHO CAN column, asked of the OPTION rather than of the POST:
        # a screen has to grey the radio BEFORE the clerk presses it, so the
        # option must carry who may take it.
        "option_declares_who_can": any(
            "who_can" in opt or "role" in opt or "roles" in opt
            for opt in (seen["settlement"].get("shortfall_paths") or ())
        ),
        "refused_for_role": False,
    }
    # PO 2026-10-12 — *"MOVE-OUT DOES NOT WRITE OFF"*. Read on EVERY decided
    # row, from the offered paths and from PostgreSQL: step 4 must not offer
    # `write_off`, and no decision may leave a `write_offs` row behind.
    from apps.payments import collections_models as payment_collections

    seen["shortfall_path"].update(
        {
            "write_off_offered": any(
                opt.get("path") == "write_off"
                for opt in (seen["settlement"].get("shortfall_paths") or ())
            ),
            "write_off_rows": payment_collections.WriteOff.objects.filter(
                account_id=world.account["id"]
            ).count(),
        }
    )


def _walk_the_wizard(
    scenario: Scenario, world: World, admin: Any, clerk: Any, mode: str
) -> dict[str, Any]:
    """The six steps, in order, through the doors each one posts to.

    ⚠ **THE ORDER IS THE PRODUCT'S AND NOT THIS FUNCTION'S.** Step 3's
    settlement and step 4's decision are asked BEFORE the commit, because that
    is when the clerk sees them — an account already closed cannot be settled
    against a bill it can no longer be given (`prepare_final_bill`'s own
    refusal, which O2 exists to prove).
    """
    actor = _the_actor(scenario, admin, clerk)
    seen: dict[str, Any] = {
        "refusal": None,
        "journal_lines_before": ledger_models.JournalLine.objects.count(),
        "payments_before": payment_models.Payment.objects.count(),
        "extra_money": {},
    }

    # ── P1 · save & exit, find it, RESUME ───────────────────────────────────
    park = None
    if scenario.road == "park_resume":
        park = wizard_parks.park(
            admin,
            {
                "flow": "move_out",
                "step": 3,
                "subject_label": f"{scenario.estate.unit_label}, 1408 Elm Street",
                # ⚠ **`subject_ref` ADDED 2026-09-20 — THE FIXTURE, NOT THE
                # PRODUCT (`DEF-CUS-5938`).** `draft_in_move_outs_list` was red
                # because `move_reads` resolves an unfinished row's account from
                # `subject_ref`, exactly as `MoveOutWizard` writes it
                # (`subjectRef: { account_id: accountId }`), and this park call
                # sent only `values`. So the row was in the list all along under
                # a null account, and the scenario looked for it by account id
                # and could not find it. A fixture that does not build what the
                # screen builds is a check that does not check — it was
                # reporting a product gap that did not exist.
                "subject_ref": {"account_id": str(world.account["id"])},
                "values": {"moved_out_on": scenario.steps.moved_out_on,
                           "account_id": str(world.account["id"])},
            },
        )
        listed = [row.id for row in wizard_parks.list_parks(flow="move_out")]
        reference = (park.reference or "").strip()
        detail: dict[str, Any] = {}
        if reference:
            try:
                detail = move_record_reads.record_detail(reference)
            except errors.NotFoundError:
                detail = {}
        in_list = False
        try:
            rows = move_reads.move_outs_list(per=50)["rows"]
            in_list = any(str(r.get("account_id")) == str(world.account["id"]) for r in rows)
        except Exception:  # noqa: BLE001 — REPORTED below, never swallowed
            in_list = False
        seen["extra_money"].update(
            {
                "draft_parked": park.id is not None,
                "draft_listed_in_parked_panel": park.id in listed,
                "draft_has_a_reference": bool(reference),
                "record_page_opens_the_draft": bool(detail),
                "record_offers_resume": bool(detail.get("park_id")),
                "draft_shows_its_move_out_date": bool(detail.get("effective_on")),
                "draft_in_move_outs_list": in_list,
            }
        )
        wizard_parks.resume(admin, park.id)

    # ── O1 · the final bill, BEFORE the close ──────────────────────────────
    if scenario.road == "bill_first":
        seen.update(_prepare_bill(world, scenario, when="before"))

    # ── E2 · BR-BIL-004's issued-bill guard, driven through its own seam ───
    #
    # ⚠ **THE ONE SEAM THIS SUITE STANDS UP, AND IT IS A DECLARED DEVIATION.**
    # `seams.last_issued_invoice_period_end` is WIRED (`DEF-035` fixed the two
    # wrong words that made it answer None on every call for weeks), so the
    # guard is real — but reaching it needs an ISSUED invoice, and issuing one
    # needs a template pin, a number series, a cycle with due terms and a GL
    # map. Building all of that would put the bill-issue pipeline under test in
    # a suite about move-outs. So the seam is driven directly, which is how
    # `test_w5_move_out_endpoints` proves the same refusal, and the deviation is
    # printed on the row rather than hidden.
    #
    # ⚠ **RESTORED IN A `finally`.** A module-level patch that leaks because an
    # unrelated exception escaped would make every LATER scenario refuse a
    # move-out dated before 2025-12-31 — one test silently changing the world
    # for the ones after it, which is the worst shape a fixture can take.
    issued_patch = None
    from apps.customers import seams as customers_seams

    if scenario.id == "E2":
        issued_patch = customers_seams.last_issued_invoice_period_end
        customers_seams.last_issued_invoice_period_end = (  # type: ignore[assignment]
            lambda _account_id: date.fromisoformat("2025-12-31")
        )
        seen.setdefault("notes", []).append(
            "DECLARED DEVIATION: `last_issued_invoice_period_end` was driven directly "
            "rather than through an issued invoice — see the comment at the call site"
        )

    try:
        # ── steps 3 and 4, before the commit ───────────────────────────────
        _settlement_and_decision(scenario, world, actor, mode, seen)

        # ── step 5's dropdown · the PO's own ruling of 2026-09-19 ──────────
        # ⚠ **THE CHOICE IS THE CLERK'S AND IT IS A MONEY DECISION** — whether
        # the OWNER pays the base charge while the unit stands empty
        # (BR-MET-094). Written through metering's own door, because the unit
        # is metering's row and customers never writes another module's table
        # (B1/B8) — and through the ONLY one that accepts the field, which is
        # this suite's finding rather than its choice (`STANDBY_DOOR`).
        if scenario.steps.standby is not None:
            seen.setdefault("notes", []).append(_write_the_standby_choice(
                admin, world, scenario.steps.standby
            ))

        # ── step 6 · the commit ────────────────────────────────────────────
        try:
            seen["result"] = customers_services.move_out(
                actor, world.account["id"], compose(scenario, world)
            )
        except (errors.BizError, errors.ValidationError, errors.NotFoundError,
                errors.AuthError, NotImplementedError) as exc:
            seen["refusal"] = exc

        # ── E1 · the count the SETTLEMENT states, and the WARNING the commit
        # ── carries, read as two separate observations ─────────────────────
        # ⚠ **THEY ARE READ FROM TWO DIFFERENT PLACES ON PURPOSE**, because the
        # whole of `BR-CUS-1082` is that they agree. The count comes from
        # `settlement_for`'s `open_sub_accounts` — what the SCREEN draws on
        # step 1 — and the warning comes off the commit's own response. A row
        # asserting both catches the day they drift, which is `DEF-CUS-5901`'s
        # defect class and the reason the rule reads ONE selector.
        #
        # ⚠ **PO 2026-09-20 turned the refusal into this warning** (option (b),
        # `OQ-CUS-12515`). Until then `services.move_out` raised here and the
        # response did not exist to read.
        if scenario.id == "E1":
            seen["extra_money"]["open_sub_accounts"] = (
                (seen.get("settlement") or {}).get("open_sub_accounts")
            )
            warned = [
                row
                for row in ((seen.get("result") or {}).get("warnings") or ())
                if row.get("code") == "master_closed_over_open_sub_accounts"
            ]
            # `None` rather than absent when nothing warned, so the declared
            # value and the observed one are always comparable and a missing
            # warning FAILS instead of quietly matching nothing.
            seen["extra_money"]["open_sub_accounts_warning"] = (
                warned[0]["code"] if warned else None
            )
            seen["extra_money"]["open_sub_accounts_warned_count"] = (
                warned[0].get("count") if warned else None
            )
    finally:
        if issued_patch is not None:
            customers_seams.last_issued_invoice_period_end = (  # type: ignore[assignment]
                issued_patch
            )

    # ── O2 · the final bill, AFTER the close ───────────────────────────────
    if scenario.road == "close_first":
        seen.update(_prepare_bill(world, scenario, when="after"))

    # ── E3 · the FRONT-END half, read out of the wizard itself ─────────────
    if scenario.id == "E3":
        seen["extra_money"]["wizard_sends_service_request_id"] = _wizard_sends_request_id()

    if scenario.id in ("C1",):
        impact = seen.get("close_impact_payload") or {}
        seen["extra_money"]["vacant_base_charges_served"] = bool(impact.get("vacant_base_charges"))
    return seen



#: ⚠ **THE PO RULED A DROPDOWN ON STEP 5 AND THERE IS NO DOOR THAT WRITES IT.**
#: `metering.Unit.vacant_standby_auto` serves BR-MET-094 — whether the OWNER
#: pays the base charge while the unit stands empty — and it is settable in
#: exactly ONE place: `_apply_unit_plan`, which is reached by
#: `assign_unit_plan` and by `update_unit`'s `plan` block. `PATCH /units/{id}`
#: with the field on its own is refused BY NAME (`metering.unknown_field`).
#:
#: So a clerk making the PO's choice on a move-out has to RE-ASSIGN THE UNIT'S
#: PLAN to carry it — which fires `BR-MET-042`'s occupied-unit override
#: warning, writes a `unit.plan_assigned` audit row and appends a dated plan
#: history row, for a decision that is not about the plan at all. This suite
#: takes that door because it is the only one, and says so on every row that
#: uses it.
STANDBY_DOOR = (
    "the step-5 standby choice has NO door of its own: `PATCH /units/{id}` refuses "
    "`vacant_standby_auto` by name and the only writer is the ASSIGN-PLAN door, so making "
    "the PO's choice re-assigns the unit's plan, warns `unit_plan_override_on_occupied_unit` "
    "and writes a plan-history row for a decision that is not about the plan"
)


def _write_the_standby_choice(admin: Any, world: World, choice: bool) -> str:
    """The clerk's step-5 election, through the only door that accepts it."""
    try:
        metering_services.update_unit(
            admin, world.unit["id"], {"vacant_standby_auto": choice}
        )
        return (
            "the step-5 standby choice was written through `PATCH /units/{id}` directly — "
            "this door has grown a field it refused on 2026-09-19"
        )
    except Exception:  # noqa: BLE001 — the expected answer; the fallback is the real door
        pass
    try:
        metering_services.assign_unit_plan(
            admin,
            world.unit["id"],
            {"tariff_id": str(world.plan.id), "vacant_standby_auto": choice,
             "effective_from": "2024-01-01"},
        )
        return STANDBY_DOOR
    except Exception as exc:  # noqa: BLE001 — REPORTED, never swallowed
        return (
            f"the step-5 standby choice could not be written AT ALL: "
            f"{type(exc).__name__}: {exc}"
        )


def _prepare_bill(world: World, scenario: Scenario, *, when: str) -> dict[str, Any]:
    """**BILL CREATION** — the closing period, gathered and priced, posting nothing.

    ⚠ **THROUGH THE PRODUCT'S OWN DOOR, AND THAT DOOR LANDED WHILE THIS SUITE
    WAS BEING WRITTEN** (2026-09-19, *"The move-out wizard can price the final
    bill without issuing it"*). `preview_final_bill` is step 3's keystone: it
    calls the SAME `prepare_final_bill` and the SAME `runs.price_account` the
    one-time preview uses, DERIVES the other end of the window through
    `cut_bill.first_unbilled_day`, and — p112, in a dashed panel — **issues no
    bill**: no invoice, no invoice line, no journal line, no bill number.

    So this suite asks the product what the bill contains rather than stating a
    figure of its own, and the ORDER group's whole finding is what that door
    answers on either side of the close.

    **It never raises for a pricing refusal** — a clerk who cannot be given a
    figure gets a sentence — so the refusal arrives as data and is asserted as
    data, which is `check_refusal_name`'s subject on O2.

    ⚠ **IT IS HANDED STEP 2's CAPTURE, BECAUSE THAT IS WHAT THE WIZARD DOES
    (PO 2026-09-20, verbatim *"option b is correct"* — `DEF-CUS-5931`).** The
    SAME `final_reads` rows `compose` posts at step 6 are passed to step 3's
    preview, unchanged and in the same order, which is the whole of the
    ruling: the figure is priced from what the clerk keyed and the reads are
    written by the close and by nothing else. Before this the preview was
    given nothing, so it priced a closing period whose read did not exist and
    `resolution.MeterMultiplierUnstated` refused every row in this group.
    """
    out: dict[str, Any] = {}
    try:
        preview = billing_final_bill.preview_final_bill(
            account_id=world.account["id"],
            moved_out_on=date.fromisoformat(scenario.steps.moved_out_on),
            period_start=date.fromisoformat(PERIOD_START),
            cycle_days=31,
            keyed_reads=[dict(row) for row in (scenario.steps.final_reads or ())],
        )
    except Exception as exc:  # noqa: BLE001 — a raise here is itself a finding
        out["billing_problem"] = f"{type(exc).__name__}: {exc}"
        out["extra_money"] = {"final_bill_prepared": False}
        return out
    refusal = preview.get("priced_unavailable") or {}
    out["billing_problem"] = " ".join(
        str(part) for part in (refusal.get("reason"), refusal.get("detail")) if part
    )
    out["preview"] = preview
    out["extra_money"] = {
        "final_bill_prepared": bool(preview.get("priced")),
        # BR-CUS-056 — the OUTGOING account pays the move day, so the window's
        # far end IS the move-out date and never the day before.
        "period_end_is_the_move_day": (
            str(preview.get("period_end") or "") == scenario.steps.moved_out_on
        ),
        # p112's dashed panel: **NO BILL IS ISSUED BY THIS SCREEN.** Asserted
        # rather than trusted — the door says `issues_nothing` and the counts
        # in `books_and_payments` are what prove it.
        "issues_nothing": bool(preview.get("issues_nothing")),
        # `DEF-CUS-5931` — the figure SAYS which kind of claim it is. A bill
        # priced from a committed read is priced from a fact; this one is
        # priced from what a clerk typed and may still change before step 6.
        "priced_from_uncommitted_reads": bool(preview.get("priced_from_uncommitted_reads")),
        # ⚠ **THE FIGURE ITSELF, PINNED — a ruling with no number under it goes
        # green on an engine that has stopped doing the arithmetic.** The
        # closing register the clerk keyed (52,410) less the meter's last
        # committed one (51,776) is **634 kWh**, and it reaches this key off the
        # ENGINE's own priced line rather than being recomputed here.
        "usage_quantity": next(
            (
                str(line.get("quantity"))
                for line in (preview.get("lines") or ())
                if line.get("kind") == "usage"
            ),
            None,
        ),
        "charges_total": preview.get("total"),
    }
    out["preview_net"] = preview.get("net") or preview.get("total")
    return out


#: ⚠ **THE ONE PLACE THIS SUITE READS THE FRONT END, AND IT READS ONE FACT.**
#: `MOVE_OUT_FIELDS` accepts `service_request_id`, `services.move_out` reads it
#: and `moves.record_move` stores it — the backend half is built and E3 proves
#: it. Whether the WIZARD sends one is a fact only the wizard holds, and a
#: backend test that ignored it would report a working link over a screen that
#: cannot make one (hard-won law 2: built is not wired).
WIZARD_SOURCE = Path(__file__).resolve().parents[1].parent / (
    "07-frontend/src/features/customers/MoveOutWizard.tsx"
)


def _wizard_sends_request_id() -> bool | None:
    """True / False, or **None where the file could not be read at all** —
    which is a third answer and not a failure: a suite run from a worktree
    without the front end must say *I could not look* rather than *it is
    missing*."""
    try:
        return "service_request_id" in WIZARD_SOURCE.read_text(encoding="utf-8")
    except OSError:
        return None


def run_scenario(
    scenario: Scenario, mode: str, admin: Any, clerk: Any, tenant: Any
) -> Result:
    world = build_world(admin, tenant, scenario)
    raw = _walk_the_wizard(scenario, world, admin, clerk, mode)
    seen = observe(scenario, world, raw)
    notes: list[str] = list(raw.get("notes") or [])

    broke = _apply_break(scenario, mode, seen)
    if broke:
        notes.append(f"⚠ DELIBERATELY BROKEN for this run: dimension `{broke}`")

    if raw.get("preview") is not None:
        preview = raw["preview"]
        notes.append(
            "the product's OWN final-bill preview "
            f"({'priced' if preview.get('priced') else 'REFUSED'}): "
            f"{len(preview.get('lines') or [])} line(s), net={raw.get('preview_net')!r}, "
            f"window {preview.get('period_start')!r} → {preview.get('period_end')!r}, "
            f"issues_nothing={preview.get('issues_nothing')!r}"
            + (f" — {raw.get('billing_problem')}" if not preview.get("priced") else "")
        )
    settlement = seen.get("settlement") or {}
    notes.append(
        f"settlement as this pass asked it: landing={settlement.get('landing')!r} "
        f"gaps={list(settlement.get('gaps') or [])} "
        f"final_bill_stated={settlement.get('final_bill_stated_by_caller')}"
    )
    queued = [dict(row) for row in ((seen.get("result") or {}).get("move_message") or ())]
    if queued:
        codes = sorted({str(r.get("code") or r.get("outcome") or "?") for r in queued})
        notes.append(
            f"the commit queued {len(queued)} outcome row(s) for the closing letter "
            f"({', '.join(codes)}); p114 draws four messages and says *Queued is not sent*"
        )
    warnings = [w.get("code") for w in ((seen.get("result") or {}).get("warnings") or ())]
    if warnings:
        notes.append("server warnings: " + ", ".join(sorted(set(str(w) for w in warnings))))

    checks: list[Check] = []
    friction: list[str] = []
    served: list[str] = []
    absent: list[str] = []
    for dimension in DIMENSIONS:
        want = scenario.expect[dimension]
        if isinstance(want, Silent):
            checks.append(Check(dimension, "SILENT", want.why))
            continue
        if dimension == "friction":
            friction = collect_friction(scenario, world, seen)
            checks.append(Check(dimension, "REPORT", f"{len(friction)} item(s)"))
            continue
        if dimension == "close_impact":
            # ⚠ **ALWAYS THE CHECKER, NEVER THE ROW'S OWN VALUE.** p115's six
            # are the same six on every scenario, so declaring them per row
            # would be twenty-seven copies of one rule — and the twenty-eighth
            # would be the one that drifted. The row says `Report()`; the
            # checker decides, and it FAILS on a defaulted consequence.
            verdict, served, absent = check_close_impact(seen)
            checks.append(Check(dimension, "REPORT" if verdict.verdict == "PASS" else "FAIL",
                                verdict.detail))
            continue
        if isinstance(want, Report):
            checks.append(Check(dimension, "REPORT", want.why))
            continue
        # ⚠ **A ROW DECLARED FOR ONE PASS IS BLOCKED IN THE OTHER, NOT FAILED.**
        # A landing cannot be asserted in the TODAY column because the wizard
        # states no bill there. Scoring it as a failure would put a real defect
        # and a known keystone in the same bucket, which is the thing this
        # suite's two columns exist to keep apart.
        if want.only is not None and want.only != mode:
            checks.append(Check(dimension, "BLOCKED",
                                f"asserted in the {want.only} pass only"))
            continue
        checks.append(
            {
                "outcome": lambda: check_outcome(want, seen),
                "refusal_name": lambda: check_refusal_name(want, seen),
                "landing": lambda: check_landing(want, seen),
                "settlement_money": lambda: check_settlement_money(want, seen),
                "deposit_interest": lambda: check_deposit_interest(want, seen),
                "shortfall_path": lambda: check_shortfall_path(want, seen),
                "books_and_payments": lambda: check_books_and_payments(want, seen),
                "account_status": lambda: check_account_status(want, seen),
                "unit_after": lambda: check_unit_after(want, seen),
                "final_reads": lambda: check_final_reads(want, seen),
                "move_record": lambda: check_move_record(want, seen),
            }[dimension]()
        )
    return Result(scenario=scenario, mode=mode, checks=checks, friction=friction, notes=notes,
                  served=served, absent=absent)


# ═══════════════════════════════════════════════════════════════════════════
# THE SUITE'S OWN GUARD — run FIRST, and it can refuse the whole table
# ═══════════════════════════════════════════════════════════════════════════
def test_every_scenario_declares_every_dimension() -> None:
    """**The PO's reason, mechanised.**

    `declares()` already refuses an incomplete row at import, so this asserts
    what it cannot: that there are TWENTY-SEVEN of them, that every id is
    unique, that every group is one of the eight, and that every keystone a row
    claims to wait on is a keystone this suite knows about. A row blocked on a
    misspelt keystone would otherwise be counted in no column at all.
    """
    assert len(SCENARIOS) == 27, f"the table holds {len(SCENARIOS)}"
    ids = [row.id for row in SCENARIOS]
    assert len(set(ids)) == 27, f"duplicate scenario id: {sorted(ids)}"
    groups = {row.group for row in SCENARIOS}
    assert groups == {"LANDING", "SHORTFALL", "DEPOSIT", "READS", "CONSEQUENCE", "ORDER",
                      "PROCESS", "EDGE"}, sorted(groups)
    assert len([r for r in SCENARIOS if r.group == "LANDING"]) == 5
    assert len([r for r in SCENARIOS if r.group == "SHORTFALL"]) == 4
    assert len([r for r in SCENARIOS if r.group == "DEPOSIT"]) == 5
    assert len([r for r in SCENARIOS if r.group == "READS"]) == 4
    for row in SCENARIOS:
        assert set(row.expect) == set(DIMENSIONS), row.id
        for key in row.blocked_on:
            assert key in KEYSTONES, f"{row.id} waits on an unknown keystone {key!r}"
    # p112 draws all five landings as ONE arithmetic, so every REACHABLE one
    # must be here. ⚠ `refused_excess` is excepted since PO 2026-10-11: with
    # BR-CUS-096 SUSPENDED it is reachable only through a PUBLISHED dispute
    # store, which this suite cannot build — L5 moved to `refund_due`, and the
    # published-store hold is pinned in `test_w5_move_out_settlement`.
    declared = {
        row.expect["landing"].value
        for row in SCENARIOS
        if isinstance(row.expect["landing"], Expect)
    }
    reachable = set(mos.MONEY_LANDINGS) - {mos.LANDING_REFUSED_EXCESS}
    assert reachable <= declared, (
        "a landing the settlement can reach is not covered: "
        f"{sorted(reachable - declared)}"
    )
    # p113 draws four shortfall paths and the PO named one of them out loud;
    # PO 2026-10-12 took `write_off` out of move-out, so three are offered.
    walked = {row.steps.shortfall_path for row in SCENARIOS} - {None}
    assert set(mos.SHORTFALL_PATHS) <= walked, sorted(set(mos.SHORTFALL_PATHS) - walked)


@pytest.mark.parametrize(
    ("scenario", "mode"),
    [(row, mode) for row in SCENARIOS for mode in MODES],
    ids=[f"{row.id}-{mode}" for row in SCENARIOS for mode in MODES],
)
def test_move_out_scenario(scenario: Scenario, mode: str, brazos: Any, dana: Any,
                           marcus: Any) -> None:
    """One row of the table, in one pass, end to end, read back from PostgreSQL.

    ⚠ **A RED ROW HERE IS THE DELIVERABLE, NOT A BROKEN TEST.** The assertion
    message names what the product does and what the drawing or the signed rule
    says it should do, and the row's own `blocked_on` says which keystone it is
    waiting for. Weakening one to reach green would delete the finding.
    """
    with tenant_ctx(brazos):
        outcome = run_scenario(scenario, mode, dana, marcus, brazos)
    RESULTS.append(outcome)
    if outcome.failed:
        lines = [f"{scenario.id} · {mode.upper()} · {scenario.title}", ""]
        for check in outcome.failed:
            want = scenario.expect[check.dimension]
            why = getattr(want, "why", "") or ""
            lines.append(f"  ✗ {check.dimension}: {check.detail}")
            if why:
                lines.append(f"      because: {why}")
        if scenario.blocked_on:
            lines.append(f"      waiting on: {', '.join(scenario.blocked_on)}")
        pytest.fail("\n".join(lines), pytrace=False)


# ═══════════════════════════════════════════════════════════════════════════
# THE REPORT — printed at the end of the module, and written to a file
# ═══════════════════════════════════════════════════════════════════════════
def _counted(result: Result) -> tuple[int, int, int]:
    """(passed, failed, blocked) over the dimensions this pass actually judged."""
    counted = [c for c in result.checks if c.verdict in ("PASS", "FAIL")]
    blocked = len([c for c in result.checks if c.verdict == "BLOCKED"])
    failed = len([c for c in counted if c.verdict == "FAIL"])
    return len(counted) - failed, failed, blocked


def _row_line(by_mode: dict[str, Result], scenario: Scenario) -> str:
    cells = []
    for mode in MODES:
        result = by_mode.get(mode)
        if result is None:
            cells.append("  —  ")
            continue
        passed, failed, blocked = _counted(result)
        mark = "RED " if failed else "GREEN"
        cells.append(f"{mark} {passed}/{passed + failed}" + (f"+{blocked}b" if blocked else ""))
    return f"  {scenario.id:<4} {scenario.title[:56]:<56} " + "  ".join(
        f"{cell:<14}" for cell in cells
    )


@pytest.fixture(scope="module", autouse=True)
def report() -> Any:
    """Prints the whole table once, after the last row. Run with `-s`."""
    yield
    if not RESULTS:
        return
    order = {row.id: index for index, row in enumerate(SCENARIOS)}
    by_id: dict[str, dict[str, Result]] = {}
    for result in RESULTS:
        by_id.setdefault(result.scenario.id, {})[result.mode] = result

    def green(mode: str) -> list[Scenario]:
        """**COMPLETE means no failure AND nothing left unasserted.**

        ⚠ A row whose landing could not be asserted in this pass is NOT
        complete in it, even though every check that ran passed. Counting it
        green would report a scenario as working on the strength of the
        dimensions that do not depend on the thing it is about — which is
        hard-won law 7's *reporting zero over a scope it silently excludes*,
        in a scoreboard.
        """
        out: list[Scenario] = []
        for row in SCENARIOS:
            result = by_id.get(row.id, {}).get(mode)
            if result is None:
                continue
            _passed, failed, blocked = _counted(result)
            if not failed and not blocked:
                out.append(row)
        return out

    out: list[str] = []
    out.append("")
    out.append("═" * 104)
    out.append("  THE MOVE-OUT SCENARIO SUITE — twenty-seven rows, one table, two columns")
    out.append("═" * 104)
    ran = sorted({r.scenario.id for r in RESULTS}, key=lambda i: order.get(i, 99))
    out.append(f"  {len(ran)} scenario(s) run · {len(RESULTS)} passes")
    out.append("")
    out.append(
        f"  {'':<4} {'':<56} "
        + "  ".join(f"{('NO BILL' if m == MODE_TODAY else 'WITH BILL'):<14}" for m in MODES)
    )
    for group in ("LANDING", "SHORTFALL", "DEPOSIT", "READS", "CONSEQUENCE", "ORDER",
                  "PROCESS", "EDGE"):
        rows = [row for row in SCENARIOS if row.group == group and row.id in by_id]
        if not rows:
            continue
        out.append(f"  ── {group} " + "─" * (98 - len(group)))
        for row in rows:
            out.append(_row_line(by_id[row.id], row))
    out.append("")
    out.append("  ── THE TWO NUMBERS " + "─" * 84)
    out.append(
        f"      complete with NO final bill stated ................. "
        f"{len(green(MODE_TODAY))} of {len(ran)}"
    )
    out.append(
        f"      complete WITH the final bill stated ................ "
        f"{len(green(MODE_WIRED))} of {len(ran)}"
    )
    out.append(
        "      `preview_final_bill` landed 2026-09-19 18:47 (1c69a87ab), so the WITH BILL"
    )
    out.append(
        "      column is the wizard's own path today. A row red in BOTH is a real gap; one"
    )
    out.append(
        "      red only in NO BILL is waiting on a bill the product can now usually price."
    )
    out.append("      COMPLETE = no failure AND nothing left unasserted in that column.")
    out.append("")

    # ── what each red row means, and what it waits on ──────────────────────
    for mode in MODES:
        reds = [
            by_id[row.id][mode]
            for row in SCENARIOS
            if row.id in by_id and mode in by_id[row.id] and by_id[row.id][mode].failed
        ]
        if not reds:
            continue
        label = "NO BILL" if mode == MODE_TODAY else "WITH BILL"
        out.append(f"  ── WHAT EACH RED ROW MEANS · {label} " + "─" * (73 - len(label)))
        for result in reds:
            waiting = ", ".join(result.scenario.blocked_on) or "NOTHING — this is a real gap"
            out.append(f"  {result.scenario.id} · {result.scenario.title}")
            out.append(f"      waiting on: {waiting}")
            for check in result.failed:
                out.append(f"      ✗ {check.dimension}: {check.detail}")
        out.append("")

    # ── p115's six, counted rather than described ──────────────────────────
    served: dict[str, set[str]] = {}
    absent: dict[str, set[str]] = {}
    for result in RESULTS:
        for name in result.served:
            served.setdefault(name, set()).add(result.scenario.id)
        for name in result.absent:
            absent.setdefault(name, set()).add(result.scenario.id)
    out.append("  ── p115's SIX CONSEQUENCES, COUNTED " + "─" * 68)
    out.append("     (the drawing says all six arrive empty. Which of them still do is a")
    out.append("      measurement, and none of them may be DEFAULTED — that is the check.)")
    for name in sorted(served):
        out.append(f"      SERVED   · {name}   [{', '.join(sorted(served[name]))}]")
    for name in sorted(absent):
        out.append(f"      ABSENT   · {name}   [{', '.join(sorted(absent[name]))}]")
    out.append("")

    friction: dict[str, set[str]] = {}
    for result in RESULTS:
        for item in result.friction:
            friction.setdefault(item, set()).add(f"{result.scenario.id}/{result.mode[:1]}")
    if friction:
        out.append("  ── THE FRICTION LIST " + "─" * 82)
        out.append("     (derived from the payload and the database. THIS SUITE NEVER OPENS A")
        out.append("      SCREEN, so it cannot see a disabled radio or a lost `Save & exit`.)")
        for item in sorted(friction):
            out.append(f"      · {item}")
            out.append(f"            [{', '.join(sorted(friction[item]))}]")
        out.append("")

    out.append("  ── DECLARED NOT ASSERTED, per row " + "─" * 70)
    for row in SCENARIOS:
        result = by_id.get(row.id, {}).get(MODE_WIRED) or by_id.get(row.id, {}).get(MODE_TODAY)
        if result is None:
            continue
        for check in result.checks:
            if check.verdict == "SILENT":
                out.append(f"      {row.id} · {check.dimension}: {check.detail}")
    out.append("")

    notes: dict[str, set[str]] = {}
    for result in RESULTS:
        for note in result.notes:
            notes.setdefault(note, set()).add(f"{result.scenario.id}/{result.mode[:1]}")
    if notes:
        out.append("  ── WHAT THE RUN OBSERVED BESIDE THE ASSERTIONS " + "─" * 57)
        for note in sorted(notes):
            out.append(f"      · {note}")
            out.append(f"            [{', '.join(sorted(notes[note]))}]")
        out.append("")

    out.append("  ── DECLARED UNTESTABLE " + "─" * 80)
    for entry in UNTESTABLE:
        out.append(f"      {entry['id']} · {entry['what']}")
        out.append(f"          {entry['why']}")
    out.append("")
    out.append("  ── SAFETY " + "─" * 93)
    out.append("      The beta database was not opened. Every scenario ran on its own tenant")
    out.append("      inside the pgtest database, and `django_db` rolled each one back.")
    out.append("═" * 104)

    text = "\n".join(out)
    print(text)
    artefact = os.environ.get("MOVE_OUT_REPORT", "")
    if artefact:
        try:
            Path(artefact).write_text(
                text
                + "\n\n"
                + json.dumps(
                    {
                        "today_green": [row.id for row in green(MODE_TODAY)],
                        "wired_green": [row.id for row in green(MODE_WIRED)],
                        "red": {
                            f"{r.scenario.id}/{r.mode}": {
                                "waiting_on": list(r.scenario.blocked_on),
                                "failures": [f"{c.dimension}: {c.detail}" for c in r.failed],
                            }
                            for r in RESULTS
                            if r.failed
                        },
                        "friction": {k: sorted(v) for k, v in friction.items()},
                        "six_consequences_served": {k: sorted(v) for k, v in served.items()},
                        "six_consequences_absent": {k: sorted(v) for k, v in absent.items()},
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        except OSError:  # pragma: no cover — a report that cannot be written is not a failure
            pass


# ── Trace ──────────────────────────────────────────────
# status: the suite is the deliverable; a RED row is a finding, never a defect
#         in this file. Amend a row only with a ruling behind it.
# ──────────────────────────────────────────────────────
