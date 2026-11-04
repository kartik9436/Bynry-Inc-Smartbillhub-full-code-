# ── Trace ──────────────────────────────────────────────
# Component: THE MOVE-IN SCENARIO SUITE — nineteen PO-specified scenarios,
#            ONE declarative table, ONE runner, ONE command.
# Change:   PO 2026-09-19 — the move-in flow is to be walked end to end the way
#           `J-REQ-CLERK-WALK` walks the request: six money cases, five
#           refusals, eight representatives, and a friction list.
# Story:    US-CUS-004 (S19 move-in) · US-CUS-007 (the deposit) ·
#           US-PAY-002 (a deposit-purpose payment) · US-LED-004 (the books)
# Rules:    BR-CUS-017 (one occupying account per unit) · BR-CUS-021 (opening
#           reads through metering's event door) · BR-CUS-022 (an occupying
#           account needs a start date) · BR-CUS-023/025 (a deposit is a
#           LIABILITY, looked up, never an input) · BR-CUS-056 (the outgoing
#           account pays the move day) · BR-CUS-089 (money moves only on a
#           STRONG identity match) · BR-CUS-090 (a shortfall is a lawful state)
#           · BR-CUS-670 (the register moves with the money) · BR-CUS-1022
#           (a company is matched on name + Tax ID) · BR-CUS-1024 (no
#           identifier, no account) · BR-MET-062 (a demand peak is NEVER
#           estimated) · BR-SHL-019 (ONE transactional commit) · B18 §5.3.4 (a
#           discount claim never blocks service) · CLAUDE.md hard rules 1, 2,
#           4, 5, 7
# Tests:    this file IS the test
# ───────────────────────────────────────────────────────
"""**Nineteen move-in scenarios, declared in one table, run by one function.**

═══════════════════════════════════════════════════════════════════════════
WHY ONE TABLE AND NOT NINETEEN WALKS — THE PO'S OWN REASON
═══════════════════════════════════════════════════════════════════════════
*"Otherwise scenario twelve gets a check that scenario three doesn't, and
nobody notices."*

So every row of `SCENARIOS` declares a verdict for **every one of the eleven
dimensions** in `DIMENSIONS`, and `test_every_scenario_declares_every_dimension`
refuses the suite if one is missing. A row that has nothing to say about a
dimension says `Silent("why")` **out loud**: it is printed in the report beside
the assertions, so a gap is a sentence somebody can read rather than an absence
nobody can see.

⚠ **THIS SUITE IS EXPECTED TO BE PARTLY RED THE DAY IT LANDS, AND THAT IS THE
POINT.** It is written against what the blueprint and the signed rules PROMISE,
not against what the product currently does. Every red row names something that
is not built. **Do not weaken an assertion to make it green** — move the
product, or move the row with a ruling behind it.

═══════════════════════════════════════════════════════════════════════════
SAFETY — WHERE THIS RUNS, AND WHY THE BETA IS NEVER OPENED
═══════════════════════════════════════════════════════════════════════════
**A move-in COMMITS.** It opens an account, takes money, writes readings and
posts to the ledger. Readings are append-only and payments and journal lines are
under CLAUDE.md hard rule 4 — **there is no delete**, and the database enforces
it: `trg_payment_immutable`, `meter_reads_value_immutable` and eleven more
triggers refuse a DELETE outright.

So the throwaway utility is **a whole PostgreSQL database**, not a tenant inside
the live one. `--ds=config.settings.pgtest` puts the run on
`test_sbh_<checkout>_<digest>`; the beta database named in `DATABASE_URL` is
opened for **nothing at all** — not a read, not a count, not a connection. Each
scenario then provisions its OWN tenant inside that database through the real
signup path, and `django_db` rolls the whole graph back when the scenario ends.

**That is strictly stronger than the permission this suite was given** (drafts
on the beta, purged by tag). Nothing is written to the beta, so nothing has to
be purged from it, and `10-scripts/move_in_nineteen.sh` counts the beta's
service requests, accounts, payments, journal lines and readings before and
after anyway — a claim nobody has checked is not a safety guarantee (hard-won
law 1).

═══════════════════════════════════════════════════════════════════════════
EVERY MONEY AND REFUSAL ASSERTION READS BACK FROM POSTGRESQL
═══════════════════════════════════════════════════════════════════════════
Not from the service's return value and never from a screen. `observe()` goes to
the tables — `payments`, `journal_lines` joined to `ledger_accounts.designation`,
`accounts.deposit_on_file`, `meter_reads`, `move_records`, `customer_accounts` —
because a response that says *Approved* over a row that did not move is the
class of defect that only surfaces in front of a customer.

═══════════════════════════════════════════════════════════════════════════
HOW TO RUN IT
═══════════════════════════════════════════════════════════════════════════
    ./10-scripts/move_in_nineteen.sh

or, by hand, from `06-backend/`:

    set -a; . ./.env; set +a
    JOBS_EAGER=false .venv/bin/pytest tests/test_move_in_nineteen_scenarios.py \\
        --ds=config.settings.pgtest --reuse-db -q -s

**PROVING IT CAN FAIL** (hard-won law 7 — a suite first seen green is a suite
nobody has proved): set `MOVE_IN_NINETEEN_BREAK=<scenario id>:<dimension>` and
that one declaration is corrupted before the run. The scenario must go RED on
exactly that dimension and on nothing else. `./10-scripts/move_in_nineteen.sh
--prove-red` does it for you.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import pytest

from apps.customers import deposit as customers_deposit
from apps.customers import discounts as customers_discounts
from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import move_record_reads, moves
from apps.customers import service_request_service
from apps.customers import services as customers_services
from apps.ledger import models as ledger_models
from apps.metering import estimation as metering_estimation
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.payments import ledger_seam
from apps.payments import models as payment_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — the shared world
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    seed_config,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# THE CALENDAR — one clock for all nineteen, so no row invents its own
# ═══════════════════════════════════════════════════════════════════════════
OUTGOING_OPENED = "2026-05-01"
OUTGOING_CLOSED = "2026-08-19"
MOVE_IN_DAY = "2026-08-20"
#: `BR-CUS-056` — the incoming account starts the day AFTER the outgoing closes,
#: so this date is the refusal R1 asserts and never a valid start.
TOO_EARLY = OUTGOING_CLOSED

#: The blueprint draws `$150.00`. **B14 rule 37 — a figure drawn in a wireframe
#: is an ILLUSTRATION.** It is a test figure here and never a rule.
A_DEPOSIT = "150.00"
#: The plan's figure for every category in these worlds. ⚠ **EQUAL TO THE
#: DEPOSIT ABOVE SINCE 2026-09-23, AND IT HAS TO BE (`DEF-CUS-6369`).** It was
#: deliberately `120.00` while the clerk TYPED the figure and the plan's was only
#: reported beside it; the PO then ruled the deposit IS the plan's figure with
#: no override, so a block sending `150.00` against a `120.00` plan is refused
#: by name — which is `test_cr094_wh_deposit`'s case, not a move-in scenario's.
PLAN_STANDARD = Decimal("150.0000")
#: M4's shortfall: the clerk assessed `A_DEPOSIT` and the customer handed over
#: this. `BR-CUS-090` — *"a shortfall is a lawful state"*.
PART_PAYMENT = "25.00"

#: **The match tier a move-in records when it CREATES a customer: none.**
#:
#: ⚠ **THIS IS AN ASSERTION AND NOT A SHRUG, AND THE CONSEQUENCE IS MONEY.**
#: `match_tier` describes agreement with a customer ALREADY ON FILE, so a
#: freshly created one has nothing to agree with and the column is NULL —
#: correct, and `link_customer`'s own docstring says so. What follows from it is
#: the part worth asserting: `discounts.carry_forward_offer` moves money only on
#: a **STORED** `strong` tier, so **every customer a move-in creates is
#: permanently ineligible for a deposit carry-forward** until somebody confirms
#: a match by hand. S7 is the one row where a tier is stored, because S7 is the
#: one row that LINKS.
TIER_ON_A_CREATE: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# THE ELEVEN DIMENSIONS — every row answers all of them
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **THE LIST IS THE CONTRACT.** Adding a twelfth dimension here makes every
#: one of the nineteen rows incomplete until it declares one, which is exactly
#: the PO's *"scenario twelve gets a check that scenario three doesn't"*
#: working as intended. Do not give a dimension a default.
DIMENSIONS: tuple[str, ...] = (
    "outcome",  # did the move-in commit, or was it refused?
    "refusal_name",  # WHICH refusal, by message key and rule — never "an error"
    "payment_rows",  # rows in `payments` for this account, and their purpose
    "journal_pair",  # the DR/CR designations in `journal_lines`
    "deposit_register",  # `accounts.deposit_on_file`
    "readings",  # rows in `meter_reads`, by event context
    "unit_occupied",  # does the unit now derive Occupied?
    "move_record",  # a `move_records` row, and what it names
    "customer_link",  # linked · created · none, and the stored match tier
    "field_homes",  # the field-by-field walk against `GET /moves/{ref}`
    "friction",  # what a clerk has to do that they should not have to
)


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A ROW MAY DECLARE FOR A DIMENSION
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Expect:
    """An assertion. `value` is compared with what PostgreSQL actually holds."""

    value: Any
    why: str = ""


@dataclass(frozen=True)
class Silent:
    """**A declared non-assertion.** Printed, never hidden.

    ⚠ **THIS TYPE IS THE WHOLE REASON THE TABLE IS A TABLE.** An omitted key
    would be indistinguishable from an oversight; a `Silent` carries the reason
    into the report, where a reader can disagree with it. Hard-won law 7's
    *"a declared blind spot with no NUMBER attached is indistinguishable from an
    empty one"*, one layer up: a blind spot with no SENTENCE attached is
    indistinguishable from a missing check.
    """

    why: str


@dataclass(frozen=True)
class Report:
    """Collect and print, pass/fail decided by the dimension's own checker."""

    why: str = ""


Declaration = Expect | Silent | Report


# ═══════════════════════════════════════════════════════════════════════════
# THE SETUP A ROW DECLARES — what world this scenario needs standing
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Estate:
    """The premises, unit, meters and previous tenancy a scenario stands on."""

    #: `(asset_no, service, uom, channel)`. **Empty means a unit with NO METER
    #: AT ALL**, which S3 exists to prove the wizard does not refuse.
    meters: tuple[tuple[str, str, str, str], ...] = (("M-9101", "electric", "kWh", "total"),)
    premises_type: str = "single_family"
    unit_type: str = "residential"
    unit_label: str = "Unit A"
    #: The outgoing tenancy. `close_outgoing=False` leaves it OCCUPYING, which
    #: is how R2 reaches `BR-CUS-017` through the front door.
    close_outgoing: bool = True
    outgoing_opened: str = OUTGOING_OPENED
    outgoing_closed: str = OUTGOING_CLOSED
    #: Days of vacancy before the move-in. S4's 94 — the opening reads are three
    #: months old and the drawing says a long vacancy is worth noticing.
    vacant_days: int | None = None
    #: `plan_deposit_rules` — the standard figure the product REPORTS beside
    #: what the clerk typed. `None` means the plan states none.
    plan_deposit: Decimal | None = PLAN_STANDARD
    #: A customer already on file, and how strongly the mover will match them.
    #: `"strong"` seeds name + date of birth + driving licence; `"weak"` seeds a
    #: phone alone, which `BR-CUS-089` will not move money on.
    returning: str | None = None
    #: An approved service request this move-in fulfils.
    from_request: str | None = None  # the request's `property_type`


@dataclass(frozen=True)
class Steps:
    """**What the FOUR steps asked the clerk for** — Unit · Customer · Billing ·
    Review (`CR-171-BRC10`, images 30, 33, 41, 45; re-pointed from the six-step
    wizard by `P3.05`, 2026-10-05).

    Declared step by step rather than as one payload, because check 1 — *every
    value the steps asked for must appear on the move record afterwards* —
    needs to know WHICH STEP each field came from to report it usefully. The
    move-in date and the opening reads are step 1 (Unit, image 30/32); the
    customer and contact are step 2 (Customer, image 33); the preferences and
    the deposit are step 3 (Billing, image 41/43). Review (step 4) asks for
    nothing the commit carries but the extra messages, which no scenario adds.
    """

    step1_unit: dict[str, Any] = field(default_factory=dict)
    step2_customer: dict[str, Any] = field(default_factory=dict)
    step2_contact: dict[str, Any] = field(default_factory=dict)
    step3_billing: dict[str, Any] = field(default_factory=dict)
    step3_deposit: dict[str, Any] | None = None

    def captured(self) -> dict[str, tuple[int, Any]]:
        """Every field the clerk typed, with the step it was typed on."""
        out: dict[str, tuple[int, Any]] = {}
        for step, block, prefix in (
            (1, self.step1_unit, ""),
            (2, self.step2_contact, "contact."),
            (2, self.step2_customer, "customer."),
            (3, self.step3_billing, ""),
            (3, self.step3_deposit or {}, "deposit."),
        ):
            for key, value in (block or {}).items():
                if key == "identity" and isinstance(value, dict):
                    for sub, sub_value in value.items():
                        out[f"{prefix}identity.{sub}"] = (step, sub_value)
                    continue
                if key == "initial_reads":
                    out["initial_reads"] = (step, value)
                    continue
                out[f"{prefix}{key}"] = (step, value)
        return out


@dataclass(frozen=True)
class Scenario:
    """One row. Setup, inputs, and a verdict for all eleven dimensions."""

    id: str
    group: str  # MONEY · REFUSAL · REPRESENTATIVE
    title: str
    estate: Estate
    steps: Steps
    expect: dict[str, Declaration]
    #: `move_in` (the chained road, from the account being left) or
    #: `create_account` (the standalone road). Both are the S19 wizard's commit;
    #: which one runs depends on how the clerk got there.
    road: str = "chained"
    #: A money question asked of a door OTHER than the move-in — R5's carry
    #: forward. Run after the commit, against the customer the move-in linked.
    money_probe: str | None = None


def declares(**kwargs: Declaration) -> dict[str, Declaration]:
    """The expectation block. **Refuses a row that skips a dimension.**

    ⚠ It refuses at IMPORT time and not at assertion time, so a half-declared
    row cannot be collected, run, and reported as a pass over checks nobody
    wrote. Hard-won law 7's *"structurally incapable of failing"* is what this
    prevents.
    """
    missing = [name for name in DIMENSIONS if name not in kwargs]
    unknown = [name for name in kwargs if name not in DIMENSIONS]
    if missing or unknown:
        raise AssertionError(
            f"a scenario must declare every dimension: missing={missing} unknown={unknown}"
        )
    return dict(kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# THE BLOCKS THE FOUR STEPS FILL, so nineteen rows do not retype them
# ═══════════════════════════════════════════════════════════════════════════
def a_person(name: str, *, email: str | None = "s.miller@example.com") -> dict[str, Any]:
    """Step 2 for a PERSON, as blueprint p071 draws it.

    `BR-CUS-089`'s STRONG test is name + date of birth + one government id, so
    all three travel: a row that means to be a weak match says so by leaving
    them out, never by accident.
    """
    return {
        "display_name": name,
        "kind": "person",
        "identity": {
            "date_of_birth": "1988-04-11",
            "ssn": "123-45-4417",
            "driving_licence": "TX-9911882",
        },
    }


def a_company(name: str, *, tax_id: str = "74-2255310") -> dict[str, Any]:
    """Step 2 for a COMPANY — `BR-CUS-1022`, PO 2026-09-01: *"if it is Company
    then we ask for Tax ID"*.

    ⚠ **NO DATE OF BIRTH AND NO SSN, AND THAT IS THE ASSERTION, NOT AN
    OMISSION.** `tier_for` gives a company `strong` on name + Tax ID alone, and
    `KIND_DATED_FIELDS[company]` is empty: a business has no date of birth to
    agree about. S2 exists to prove the product applies the company test and
    not the person one.
    """
    return {"display_name": name, "kind": "company", "identity": {"tax_id": tax_id}}


def contact(name: str, *, email: str | None = "s.miller@example.com") -> dict[str, Any]:
    """The contact half of step 2 — p071's Full name · Email · Phone · Date of
    birth · Government id (*"last four only"*)."""
    return {
        "full_name": name,
        "email": email,
        "phone": "(512) 555-0142",
        "dob": "1988-04-11",
        "gov_id_last4": "4417",
    }


MAILING = [
    {
        "kind": "mailing",
        "line1": "1408 Elm Street",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78704",
    }
]

PREFERENCES = {
    "paperless": True,
    "sms_reminders": False,
    "autopay": False,
    "tax_exempt": False,
    "preferred_language": "en",
    "addresses": MAILING,
}


def start(day: str = MOVE_IN_DAY, reads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Step 1 — *Unit*: the move-in date and the opening reads (image 30/32;
    the six-step wizard's step 3, p072)."""
    out: dict[str, Any] = {"opened_at": day, "status": "active"}
    if reads is not None:
        out["initial_reads"] = reads
    return out


ONE_READ = [{"meter_no": "M-9101", "value": "41680"}]


def deposit_block(**over: Any) -> dict[str, Any]:
    """Step 3 — *Billing*'s deposit (image 41/43; the six-step wizard's step 5,
    p073/p074). Defaults to the drawing's own filled-in state."""
    block = {
        "decision": "required",
        "amount": A_DEPOSIT,
        "reason": "standard",
        "due_on": "2026-09-16",
        "take_now": True,
        "method_code": "cash",
        "confirmation": "AUTH 55192",
        "amount_taken": A_DEPOSIT,
        "posted_at": MOVE_IN_DAY,
        # No `cleared_at` — DEF-CUS-10324 / CR-186-BRC10: posted at entry.
    }
    block.update(over)
    return block


# ═══════════════════════════════════════════════════════════════════════════
# ⬛ THE NINETEEN
# ═══════════════════════════════════════════════════════════════════════════
SCENARIOS: list[Scenario] = [
    # ───────────────────────── MONEY · all six, exhaustive ─────────────────
    Scenario(
        id="M1",
        group="MONEY",
        title="deposit taken now · cash · clearing date today",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Miller, Sarah"),
            step2_customer=a_person("Miller, Sarah"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing is refused — this is the happy money path"),
            payment_rows=Expect(
                {"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")},
                why="`record_payment(purpose='deposit')` — one row, the amount taken",
            ),
            journal_pair=Expect(
                ("undeposited_funds", "deposit_liability"),
                why="DR undeposited / CR 2300 — BR-CUS-025, and only on a CLEARED payment",
            ),
            deposit_register=Expect(
                Decimal("150.0000"), why="`accounts.deposit_on_file` — BR-CUS-670's register"
            ),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="M2",
        group="MONEY",
        title="taken now · cheque · POSTED AT ENTRY (CR-186-BRC10)",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Okafor, Dele"),
            step2_customer=a_person("Okafor, Dele"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(method_code="check"),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("no clearing date is asked — the payment is posted at entry"),
            # p074's *"Leave the clearing date blank … the new account will read
            # a deposit of $0.00 while the cash is in the drawer"* is SUPERSEDED
            # by CR-186-BRC10 (PO 2026-10-21) and DEF-CUS-10324: a cheque
            # deposit is POSTED at entry, booked and held at once; only bank
            # reconciliation clears it.
            payment_rows=Expect(
                {"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")},
                why="the payment row is REAL — the money was taken",
            ),
            journal_pair=Expect(
                ("undeposited_funds", "deposit_liability"),
                why="CR-186-BRC10: journalled at posting, not at clearing",
            ),
            deposit_register=Expect(
                Decimal("150.0000"), why="DEF-CUS-10324: held at posting, never $0.00 in the drawer"
            ),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(why="does the screen WARN? p074 draws the sentence in red"),
        ),
    ),
    Scenario(
        id="M3",
        group="MONEY",
        title='"No — send it with the first bill"',
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Nadeau, Remi"),
            step2_customer=a_person("Nadeau, Remi"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(take_now=False, method_code=None, confirmation=None,
                                        amount_taken=None, posted_at=None),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("declining to take it today is an ordinary answer"),
            payment_rows=Expect({"count": 0}, why="NO PAYMENT ROW AT ALL — nothing was tendered"),
            journal_pair=Expect(None, why="no money, no books"),
            deposit_register=Expect(Decimal("0"), why="the deposit is owed, not held"),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="M4",
        group="MONEY",
        title="amount taken LESS than the deposit — a lawful shortfall",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Duarte, Rui"),
            step2_customer=a_person("Duarte, Rui"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(amount_taken=PART_PAYMENT),
        ),
        expect=declares(
            # `BR-CUS-090` — *"a shortfall is a lawful state"*: never a waiver,
            # never a refusal at the desk, always an open balance.
            outcome=Expect("committed"),
            refusal_name=Silent("BR-CUS-090 is explicit that the counter does NOT refuse"),
            payment_rows=Expect(
                {"count": 1, "purpose": "deposit", "amount": Decimal("25.0000")},
                why="the payment is what was HANDED OVER, not what was assessed",
            ),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("25.0000"), why="the register holds what arrived"),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect(
                # ⚠ **THE FIGURE IS THE ASSERTION; `.0000` IS THE WIRE FORMAT.**
                # This read `"125.00"` until 2026-09-20 and would have gone on
                # failing over the RIGHT number (`DEF-CUS-6015`). Money travels
                # this API as a STRING at FOUR decimals and the SCREEN renders
                # two — CLAUDE.md hard rule 2 (*"round only at
                # finalization/display"*), `BR-TEN-080` (*"exactly 2 dp on
                # screen"*) and `components/MoneyCell.formatMoney`, which
                # trims `8.2985` to `$8.30` for exactly this reason. Every
                # sibling fact in `money_taken` is served the same way. The
                # arithmetic this row exists for — ASSESSED minus TAKEN, not
                # the plan standard minus taken — is unchanged and is what
                # `DEF-CUS-5909` was filed for.
                {"kind": "move_in", "prefix": "MVI-", "still_to_collect": "125.0000"},
                why="p075's review computes ASSESSED minus TAKEN: 150.00 − 25.00",
            ),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="M5",
        group="MONEY",
        # ⚠ SINCE 2026-09-23 *No* IS ONLY AN ANSWER WHERE THE PLAN ASKS NONE
        # (`OQ-CUS-12620` (a)), so this world's plan asks none.
        title="no deposit — the plan asks none",
        estate=Estate(plan_deposit=None),
        steps=Steps(
            step2_contact=contact("Kaur, Simran"),
            step2_customer=a_person("Kaur, Simran"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit={"decision": "not_required"},
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("no deposit is an answer, not an error"),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None, why="no payment, no journal line"),
            deposit_register=Expect(Decimal("0")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="M6",
        group="MONEY",
        title='"Waive it" — a Billing Clerk waives Rosa\'s $150.00 (BR-CUS-1050, 2026-09-24)',
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Alvarez, Rosa"),
            step2_customer=a_person("Alvarez, Rosa"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit={
                "decision": "waived",
                "amount": A_DEPOSIT,
                "waive_reason": "Hardship",
            },
        ),
        # ⛔ **FLIPPED 2026-09-24 — `OQ-CUS-12623`, `BR-CUS-1050` amended.** p073
        # draws *`Waive it (needs a supervisor)`* and this row asserted the
        # refusal; PO, verbatim: *"p3 - clark and sysem admin can do it"*. The
        # actor is still a BILLING CLERK, deliberately — the case now proves the
        # clerk CAN waive, with the reason, and nothing is taken.
        road="chained",
        expect=declares(
            outcome=Expect("committed", why="a Billing Clerk may waive since 2026-09-24"),
            refusal_name=Silent("a clerk's waive with a reason is an answer, not an error"),
            payment_rows=Expect({"count": 0}, why="waiving never collects — that is what it IS"),
            journal_pair=Expect(None, why="no money, no books"),
            deposit_register=Expect(Decimal("0"), why="forgiven: nothing held"),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
]

# ───────────────────── REFUSALS · all five, each BY NAME ───────────────────
SCENARIOS += [
    Scenario(
        id="R1",
        group="REFUSAL",
        title="the start date is earlier than the outgoing account's close",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Peralta, Lucia"),
            step2_customer=a_person("Peralta, Lucia"),
            # p072, verbatim: *"The outgoing account must have been billed
            # through the move day — the server refuses an earlier start."*
            step1_unit=start(day=TOO_EARLY, reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("refused"),
            refusal_name=Expect(
                {
                    "message_key": "customers.account.start_on_prior_move_day",
                    "br_ref": "BR-CUS-056",
                    "params": ("earliest_start",),
                },
                why="the refusal must NAME the earliest lawful start, p072's *Earliest start*",
            ),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(None, why="no account exists to carry a register"),
            readings=Expect({"move_in": 0}, why="BR-SHL-019 — none of it happens"),
            unit_occupied=Expect(False),
            move_record=Expect(None),
            customer_link=Expect({"outcome": "none"}),
            field_homes=Silent("no move record on a refused commit"),
            friction=Report(),
        ),
    ),
    Scenario(
        id="R2",
        group="REFUSAL",
        title="the unit is already occupied",
        estate=Estate(close_outgoing=False),
        steps=Steps(
            step2_contact=contact("Ito, Hana"),
            step2_customer=a_person("Ito, Hana"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("refused"),
            refusal_name=Expect(
                {
                    "message_key": "customers.account.unit_already_occupied",
                    "br_ref": "BR-CUS-017",
                    "params": ("account_no",),
                },
                why="p070 draws it as **`Occupied · A-11455`** — the refusal names the account",
            ),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(None),
            readings=Expect({"move_in": 0}),
            unit_occupied=Expect(True, why="occupied by the INCUMBENT, which is the refusal"),
            move_record=Expect(None),
            customer_link=Expect({"outcome": "none"}),
            field_homes=Silent("no move record on a refused commit"),
            friction=Report(),
        ),
    ),
    Scenario(
        id="R3",
        group="REFUSAL",
        title="the customer carries no identifier",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Nobody, N."),
            # `BR-CUS-1024`, PO 2026-09-01: *"Without identifier we cannot
            # create Customer ID or master account ot regular account"*. A name
            # and nothing else.
            step2_customer={"display_name": "Nobody, N.", "kind": "person", "identity": {}},
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("refused"),
            refusal_name=Expect(
                {
                    "message_key": "customers.account.identity_required_person",
                    "br_ref": "BR-CUS-1024",
                    "params": ("accepts",),
                },
                why="the sentence follows the KIND — a business is never asked for a licence",
            ),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(None),
            readings=Expect({"move_in": 0}),
            unit_occupied=Expect(False),
            move_record=Expect(None),
            customer_link=Expect({"outcome": "none"}),
            field_homes=Silent("no move record on a refused commit"),
            friction=Report(),
        ),
    ),
    Scenario(
        id="R4",
        group="REFUSAL",
        title="the status would not occupy",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Vega, Marcus"),
            step2_customer=a_person("Vega, Marcus"),
            # `pending_activation` is `non_billable`, which is not in
            # OCCUPYING_BEHAVIOR_CLASSES. The wizard's exit condition is *the
            # unit derives Occupied*, so this must be refused rather than
            # quietly producing a draft that frees nothing.
            step1_unit={"opened_at": MOVE_IN_DAY, "status": "pending_activation",
                         "initial_reads": ONE_READ},
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("refused"),
            refusal_name=Expect(
                {"br_ref": "BR-CUS-055", "message_key_contains": "occupy"},
                why="it must say the status does not occupy, not merely fail",
            ),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(None),
            readings=Expect({"move_in": 0}),
            unit_occupied=Expect(False),
            move_record=Expect(None),
            customer_link=Expect({"outcome": "none"}),
            field_homes=Silent("no move record on a refused commit"),
            friction=Report(),
        ),
    ),
    Scenario(
        id="R5",
        group="REFUSAL",
        title="a WEAK match is asked to move money",
        estate=Estate(returning="weak", plan_deposit=None),
        steps=Steps(
            step2_contact=contact("Santos, Ana"),
            # A phone alone. `BR-CUS-089` is verbatim *name + date of birth +
            # one government ID*, and `identity_match`'s own exception note
            # says a phone match alone is WEAK.
            step2_customer={
                "display_name": "Santos, Ana",
                "kind": "person",
                "identity": {"phone": "+1 (281) 555-0155"},
            },
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        money_probe="carry_forward",
        expect=declares(
            # ⚠ **THE ACCOUNT STILL OPENS.** `BR-CUS-019` is ADVISORY, so
            # nothing is blocked; `BR-CUS-089` governs the MONEY alone. The
            # refusal under test is the carry-forward's, not the wizard's.
            outcome=Expect("committed", why="BR-CUS-019 is advisory — service is never refused"),
            refusal_name=Expect(
                {
                    "br_ref": "BR-CUS-089",
                    "code_in": ["no_identity_match_recorded", "identity_match_not_strong"],
                    "names_no_figure": True,
                },
                why="a refused offer that printed $150.00 invites it to be typed in by hand",
            ),
            payment_rows=Expect({"count": 0}, why="no deposit was taken on this one"),
            journal_pair=Expect(None),
            deposit_register=Expect(Decimal("0"), why="MONEY NEVER MOVES ON A WEAK MATCH"),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect(
                {"outcome": "created", "tier": None},
                why="its OWN customer number — nothing is merged on a guess",
            ),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
]

# ──────────── ONE REPRESENTATIVE EACH · the eight shapes that differ ────────
SCENARIOS += [
    Scenario(
        id="S1",
        group="REPRESENTATIVE",
        title="a person · residential · rental tenant applying · multi-unit · FROM A REQUEST",
        estate=Estate(
            premises_type="apartment_complex",
            unit_type="residential",
            unit_label="Unit 2",
            from_request="rental_tenant_applying",
        ),
        steps=Steps(
            step2_contact=contact("Nadeau, Robin"),
            step2_customer=a_person("Nadeau, Robin"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("nothing is refused — a request-fed move-in is the ordinary road"),
            payment_rows=Expect({"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")}),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("150.0000")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            # PO 2026-09-19: *"here if move is coming from service request these
            # details will be filled in"*. The COLUMN has existed since
            # 2026-09-15; what this asserts is that the finished record NAMES
            # the application it fulfils.
            move_record=Expect(
                {"kind": "move_in", "prefix": "MVI-", "names_the_request": True},
                why="`move_records.request_id` — BR-CUS-080's child half",
            ),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(why="and whether step 2 had to be RE-KEYED from the request"),
            friction=Report(),
        ),
    ),
    Scenario(
        id="S2",
        group="REPRESENTATIVE",
        title="a COMPANY · commercial · standalone owner-occupied · a different identity test",
        estate=Estate(premises_type="commercial_building", unit_type="commercial"),
        steps=Steps(
            step2_contact=contact("Silver Creek Warehousing LLC", email="ap@scw.example.com"),
            # `BR-CUS-1022` — name + Tax ID. **No date of birth, no SSN.**
            step2_customer=a_company("Silver Creek Warehousing LLC"),
            step1_unit=start(reads=ONE_READ),
            step3_billing={**PREFERENCES, "tax_exempt": False},
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a business with its Tax ID identifies itself completely"),
            payment_rows=Expect({"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")}),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("150.0000")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect(
                {"outcome": "created", "tier": TIER_ON_A_CREATE, "kind": "company"},
                why="the COMPANY test was applied — kind `company`, matched on no date of birth",
            ),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="S3",
        group="REPRESENTATIVE",
        title="a unit with NO METER AT ALL",
        estate=Estate(meters=()),
        steps=Steps(
            step2_contact=contact("Ibarra, Teo"),
            step2_customer=a_person("Ibarra, Teo"),
            step1_unit=start(),  # no reads — there is nothing to read
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            # p070, verbatim, in a red box: *"A UNIT WITH NO METER CAN STILL BE
            # MOVED INTO. The wizard does not refuse it. Service starts,
            # nothing can be measured, and no metered bill can be raised until
            # one is fitted."*
            outcome=Expect("committed", why="p070 — the wizard does not refuse it"),
            refusal_name=Silent("the drawing is explicit that there is no refusal here"),
            payment_rows=Expect({"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")}),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("150.0000")),
            readings=Expect({"move_in": 0}, why="nothing can be measured"),
            unit_occupied=Expect(True, why="SERVICE STARTS — that is the whole point"),
            move_record=Expect(
                {"kind": "move_in", "prefix": "MVI-", "says_no_meters": True},
                why="the record must SAY the unit has no meters, not show an empty table",
            ),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(why="is the clerk TOLD no metered bill can be raised?"),
        ),
    ),
    Scenario(
        id="S4",
        group="REPRESENTATIVE",
        title="a unit vacant 94 days · opening reads three months old",
        estate=Estate(vacant_days=94, outgoing_closed="2026-05-18", plan_deposit=None),
        steps=Steps(
            step2_contact=contact("Okafor, Dayo"),
            step2_customer=a_person("Okafor, Dayo"),
            # p070: *"a long vacancy is worth noticing: nothing has been read
            # here since January, so the opening reads above are three months
            # old"*. The read carries its OWN date, three months back.
            step1_unit=start(reads=[{"meter_no": "M-9101", "value": "41680",
                                      "read_at": "2026-05-18"}]),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a stale read is a fact to notice, never a refusal"),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(Decimal("0")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect(
                {"kind": "move_in", "prefix": "MVI-", "read_date_kept": "2026-05-18"},
                why="p072: *every date opens on the move-in day* — and a clerk may change it",
            ),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(why="is the 94-day vacancy stated anywhere a clerk sees it?"),
        ),
    ),
    Scenario(
        id="S5",
        group="REPRESENTATIVE",
        title="a DEMAND register that cannot be read AND cannot be estimated",
        estate=Estate(
            plan_deposit=None,
            meters=(("M-9101", "electric", "kWh", "total"), ("M-9301", "electric", "kW", "demand")),
        ),
        steps=Steps(
            step2_contact=contact("Brandt, Elke"),
            step2_customer=a_person("Brandt, Elke"),
            # The total is read; the demand register is left out entirely —
            # p072 draws it with `—` and COULD NOT BE READ ticked.
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        expect=declares(
            outcome=Expect("committed"),
            # p072, verbatim: *"The demand register could not be read, and could
            # not be estimated either. A demand peak is never estimated, because
            # the charge it drives would be disputed."*
            refusal_name=Expect(
                {"br_ref": "BR-MET-062", "code": "demand_never_estimated"},
                why="the ESTIMATOR must refuse a demand channel by name",
            ),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(Decimal("0")),
            readings=Expect(
                {"move_in": 1}, why="ONE reading — nothing is invented for the demand register"
            ),
            unit_occupied=Expect(True),
            move_record=Expect(
                {"kind": "move_in", "prefix": "MVI-", "unread_registers": 1},
                why="p075: *One register opens unread and unestimated* — the record must say so",
            ),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="S6",
        group="REPRESENTATIVE",
        title="a builder or developer on `under_construction`",
        estate=Estate(premises_type="single_family", from_request="under_construction"),
        steps=Steps(
            step2_contact=contact("Ridgeline Homes LLC", email="site@ridgeline.example.com"),
            step2_customer=a_company("Ridgeline Homes LLC", tax_id="74-3399104"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a builder taking service is an ordinary move-in"),
            payment_rows=Expect({"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")}),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("150.0000")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-", "names_the_request": True}),
            # The conformance record's own table: on `under_construction` the
            # mover is the BUILDER and the master account stays the owner's.
            customer_link=Expect(
                {"outcome": "created", "tier": TIER_ON_A_CREATE, "kind": "company"},
                why="the BUILDER's own customer number — never the property owner's",
            ),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="S7",
        group="REPRESENTATIVE",
        title="a returning customer · STRONG match",
        estate=Estate(returning="strong", plan_deposit=None),
        steps=Steps(
            step2_contact=contact("Whitfield, Dana"),
            step2_customer=a_person("Whitfield, Dana"),
            step1_unit=start(reads=ONE_READ),
            step3_billing=dict(PREFERENCES),
            step3_deposit=None,
        ),
        money_probe="carry_forward",
        expect=declares(
            outcome=Expect("committed"),
            refusal_name=Silent("a strong match is the case where nothing is refused"),
            payment_rows=Expect({"count": 0}),
            journal_pair=Expect(None),
            deposit_register=Expect(Decimal("0"), why="a carry-forward is OFFERED, never automatic"),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect(
                {
                    "outcome": "linked",
                    "tier": "strong",
                    "reuses_existing": True,
                    # ⚠ **THE WARNING MUST NOT FIRE ON A MOVE-IN THAT LINKED.**
                    # `MOVE_IN_UNAVAILABLE` rides every move-in unconditionally
                    # and `customer_not_linked` reads *"the first-class
                    # `customers` entity has no table, so a RETURNING customer
                    # cannot be recognised — this move-in writes a fresh contact
                    # row"*. The table has existed since 2026-08-11 and THIS ROW
                    # recognises a returning customer, so every clause of that
                    # sentence is false here. Hard-won law 1's second form: a
                    # stated reason that has expired. `DEF-CUS-5912`.
                    "no_stale_not_linked_warning": True,
                },
                why="ONE customer number across tenancies — never a second (DEF-2587)",
            ),
            field_homes=Report(),
            friction=Report(),
        ),
    ),
    Scenario(
        id="S8",
        group="REPRESENTATIVE",
        title="a SENIOR DISCOUNT claim alongside a deposit — it must NEVER gate service",
        estate=Estate(),
        steps=Steps(
            step2_contact=contact("Arriaga, Pilar"),
            step2_customer=a_person("Arriaga, Pilar"),
            step1_unit=start(reads=ONE_READ),
            step3_billing={
                **PREFERENCES,
                # B18 §5.3.4, verbatim: *"never blocks service — only the
                # discount"*. The claim is RECORDED; `proof_before_first_
                # reduction` defaults true so it grants nothing.
                "eligibility_claimed": True,
                "eligibility_note": "Senior — 65+, government id shown at the counter",
            },
            step3_deposit=deposit_block(),
        ),
        expect=declares(
            outcome=Expect("committed", why="B18 §5.3.4 — a claim NEVER blocks service"),
            refusal_name=Silent("a discount claim has no refusal — that is the rule"),
            payment_rows=Expect({"count": 1, "purpose": "deposit", "amount": Decimal("150.0000")}),
            journal_pair=Expect(("undeposited_funds", "deposit_liability")),
            deposit_register=Expect(Decimal("150.0000")),
            readings=Expect({"move_in": 1}),
            unit_occupied=Expect(True),
            move_record=Expect({"kind": "move_in", "prefix": "MVI-"}),
            customer_link=Expect({"outcome": "created", "tier": TIER_ON_A_CREATE}),
            field_homes=Report(why="and specifically: does the CLAIM have a home?"),
            friction=Report(),
        ),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# ⬛ FOUR THINGS THIS SUITE DECLARES UNTESTABLE — NAMED, NEVER SILENTLY SKIPPED
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **A SCENARIO THAT CANNOT FAIL IS WORSE THAN ONE THAT IS NOT THERE**
#: (hard-won law 7). Each of these is printed on every run, with the reason, so
#: a reader counting nineteen green rows also reads what nobody checked.
UNTESTABLE: tuple[dict[str, str], ...] = (
    {
        "id": "U1",
        "what": "Deposit carry-forward — whether a returning customer's own money follows them",
        "why": (
            "The six-step blueprint asked it on step 5, now Billing (*Has this customer paid us a deposit before?*) "
            "and answers its own question in the dashed box: *Could not be checked.* There "
            "is no path that ACCEPTS a carry-forward — `carry_deposit_from` is a refused "
            "field on every door, and the offer function's own result carries "
            "`no_accept_path`. S7 proves the LINK and the stored `strong` tier a "
            "carry-forward depends on, and R5 proves the offer is REFUSED BY NAME on a "
            "weak match. ⚠ Neither proves the offer is MADE — S7's prior closed account "
            "holds no deposit, so its offer comes back EMPTY rather than populated — and "
            "**nothing proves a single dollar can move**, because nothing in the product "
            "can move it."
        ),
    },
    {
        "id": "U2",
        "what": "Automatic discounts — paperless, autopay and municipal",
        "why": (
            "`DiscountVersion.eligibility_rule` carries the rule builder's output and NO "
            "CODE EVALUATES IT — the field's own docstring says *ADVISORY IN THIS SLICE*. "
            "So a customer who ticks paperless on Billing (step 3) does not get the paperless "
            "discount; somebody enrols them by hand afterwards. S8 proves a CLAIM is "
            "recorded and never gates service; **no scenario can prove a discount was "
            "applied, because no code applies one.**"
        ),
    },
    {
        "id": "U3",
        "what": "The five customer messages",
        "why": (
            "p075 draws five — the welcome carrying the account number, the deposit "
            "receipt, the service agreement, the opening reads, and the note that a meter "
            "still has to be read — and p076 states the cost in its own words: "
            "***Everything here is queued, and nothing is sent.*** This suite counts the "
            "rows the commit QUEUES and reports the number; it cannot assert delivery, "
            "because no sender picks any of them up — no email, no text, no print file."
        ),
    },
    {
        "id": "U4",
        "what": '"Billable" — the seventh item on the PO\'s Approve list',
        "why": (
            "Six of the seven — account status, unit status, assets, plan, the deposit and "
            "the books — follow from what the commit writes and are asserted above. "
            "*Billable* is not a switch; it is a CONSEQUENCE, and nobody has watched it "
            "happen. **This suite attempts it** (`test_u4_billable_*`): a bill is prepared "
            "against a fresh move-in account on the throwaway utility. Whatever it "
            "reports — ready, blocked or refused — is stated rather than assumed."
        ),
    },
)


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD ONE SCENARIO NEEDS — built through the real services, never the ORM
# ═══════════════════════════════════════════════════════════════════════════
def _published_plan(tenant: Any, services: list[str], name: str) -> Any:
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name=name, defaults={"code": name.lower().replace(" ", "-"),
                                            "status": "published"}
    )
    for code in services:
        service = tenancy_models.Service.objects.get(code=code)
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant=tenant, name=f"{name} — {code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
    return plan


def _state_the_plan_deposit(tenant: Any, plan: Any, amount: Decimal) -> None:
    """`plan_deposit_rules` — the figure the account is ASKED (`BR-RAT-020/023`).

    ⚠ ENFORCED since 2026-09-23 (`DEF-CUS-6369`, `OQ-CUS-12620` (a)): the
    deposit is this figure, *No* is refused while the plan asks one, and a
    world with `plan_deposit=None` is a plan that asks none.
    """
    for account_type in customers_models.AccountType.objects.all():
        rating_models.PlanDepositRule.objects.get_or_create(
            tenant=tenant,
            rate_plan=plan,
            account_type_id=account_type.id,
            defaults={"amount": amount, "currency": "USD"},
        )


def _account_type_for(unit_type: str) -> str:
    return "commercial" if unit_type.startswith("commercial") else "residential"


def _a_request(actor: Any, property_type: str, name: str) -> Any:
    """An application this move-in fulfils. Draft is enough: what is under test
    is that the RECORD names it, not the request lifecycle (that is
    `J-REQ-CLERK-WALK`'s subject and is proved there)."""
    return service_request_service.create_request(
        actor,
        {
            "applicant_name": name,
            "applicant_kind": "person",
            "property_type": property_type,
            "address_as_given": "1408 Elm Street, Silver Creek, TX 78611",
        },
    )


def _prior_tenancy(admin: Any, tenant: Any, plan: Any, customer_block: dict[str, Any],
                   name: str, label: str) -> None:
    """A CLOSED account for the same party, on a DIFFERENT unit.

    That is what makes a *returning* customer returning: `BR-CUS-024`'s carry
    forward is *"from a prior closed account of the same customer"*, and p073 is
    explicit that it is **the customer's own** prior account and not the one
    being moved out of.
    """
    premises = make_premises(admin, services_available=["electric"],
                             address_line="22 Old Mill Rd", premises_type="single_family")
    unit = make_unit(admin, premises["id"], label=label, services=["electric"])
    metering_services.assign_unit_plan(admin, unit["id"], {"tariff_id": str(plan.id)})
    prior = customers_services.create_account(
        admin,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2024-03-01",
            "contact": {"full_name": name},
            "customer": customer_block,
        },
        # ⚠ WORLD-BUILDING, NOT THE SCENARIO: a tenancy that predates the deposit
        # step, opened the way an imported account is — with no deposit
        # question asked (`require_deposit_answer`, `OQ-CUS-12620` (a)).
        require_deposit_answer=False,
    )
    customers_services.move_out(admin, prior["id"], {"moved_out_on": "2025-11-30"})


@dataclass
class World:
    unit: dict[str, Any]
    plan: Any
    outgoing: dict[str, Any]
    request: Any | None


def build_world(admin: Any, tenant: Any, scenario: Scenario) -> World:
    """Everything the scenario needs standing, through the owning services."""
    estate = scenario.estate
    seed_config()
    services = sorted({svc for _no, svc, _uom, _ch in estate.meters}) or ["electric"]
    plan = _published_plan(tenant, services, f"Move-in {scenario.id}")
    if estate.plan_deposit is not None:
        _state_the_plan_deposit(tenant, plan, estate.plan_deposit)

    premises = make_premises(
        admin,
        services_available=services,
        premises_type=estate.premises_type,
        address_line="1408 Elm Street",
        city="Silver Creek",
        postal_code="78611",
    )
    unit = make_unit(
        admin, premises["id"], label=estate.unit_label,
        unit_type=estate.unit_type, services=services,
    )
    metering_services.assign_unit_plan(admin, unit["id"], {"tariff_id": str(plan.id)})
    for asset_no, service, uom, _channel in estate.meters:
        a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)

    if estate.returning is not None:
        block = (
            a_person(scenario.steps.step2_customer.get("display_name", "Returning, R."))
            if estate.returning == "strong"
            else dict(scenario.steps.step2_customer)
        )
        _prior_tenancy(admin, tenant, plan,
                       block, block["display_name"], f"{scenario.id}-prior")

    outgoing = customers_services.create_account(
        admin,
        {
            "unit_id": str(unit["id"]),
            "account_type": _account_type_for(estate.unit_type),
            "status": "active",
            "opened_at": estate.outgoing_opened,
            "contact": {"full_name": "Okafor, D."},
            "customer": identity_fixtures.customer_block("Okafor, D."),
        },
        # ⚠ WORLD-BUILDING, NOT THE SCENARIO: a tenancy that predates the deposit
        # step, opened the way an imported account is — with no deposit
        # question asked (`require_deposit_answer`, `OQ-CUS-12620` (a)).
        require_deposit_answer=False,
    )
    if estate.close_outgoing:
        customers_services.move_out(admin, outgoing["id"], {"moved_out_on": estate.outgoing_closed})

    request = None
    if estate.from_request is not None:
        request = _a_request(admin, estate.from_request,
                             scenario.steps.step2_contact.get("full_name", "Applicant"))
    return World(unit=unit, plan=plan, outgoing=outgoing, request=request)


def compose(scenario: Scenario, world: World) -> dict[str, Any]:
    """**The four steps, as ONE payload.** p076: *Commits to
    `POST /accounts/{fromId}/move-in` · every field from all six steps* — the
    same one commit now fed by four (CR-171-BRC10)."""
    steps = scenario.steps
    payload: dict[str, Any] = {
        "account_type": _account_type_for(scenario.estate.unit_type),
        "contact": dict(steps.step2_contact),
        "customer": dict(steps.step2_customer),
        **dict(steps.step1_unit),
        **dict(steps.step3_billing),
    }
    if steps.step3_deposit is not None:
        payload["deposit"] = {k: v for k, v in steps.step3_deposit.items() if v is not None}
    if world.request is not None:
        payload["service_request_id"] = str(world.request.id)
    return payload


# ═══════════════════════════════════════════════════════════════════════════
# WHERE EACH CAPTURED FIELD SHOULD LAND ON `GET /moves/{ref}`
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **A FIELD ABSENT FROM THIS MAP IS REPORTED AS HAVING NO HOME, BY NAME.**
#: That is check 1 of the two the PO said matter most: *a clerk types a receipt
#: number, a why-this-amount reason, a plot reference — if it has no home, it is
#: gone and nobody can tell.* The map is written against the RECORD alone, not
#: against the account page, because the record is where the drawing puts the
#: answer to *what happened on the day*.
def _dig(record: dict[str, Any], *path: str) -> Any:
    """Walk the record, unwrapping `{"value": …, "unavailable": …}` on the way.

    ⚠ **UNWRAPPING ONLY AT THE LEAF WAS WRONG AND IT READ AS A FINDING.** The
    record wraps most facts in that pair, so `doors → customer → name` met the
    wrapper at `customer` and answered None — and the report then said the
    customer's name had NO HOME on the record, which is false. A finder that
    cannot reach a value it is pointed at manufactures the exact defect this
    suite exists to detect, so the walk unwraps at every step.
    """
    cursor: Any = record
    for key in path:
        if isinstance(cursor, dict) and "value" in cursor and "unavailable" in cursor:
            cursor = cursor["value"]
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    if isinstance(cursor, dict) and "value" in cursor:
        return cursor["value"]
    return cursor


MOVE_RECORD_HOMES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "contact.full_name": lambda r: r.get("title"),
    "customer.display_name": lambda r: _dig(r, "doors", "customer", "name"),
    "opened_at": lambda r: _dig(r, "what_happened", "moved_in_on"),
    # ⚠ **THE FINDER ASKS FOR THE FIGURE, NOT FOR A ROW.** A table with a row
    # per register and `Reading —` in every one of them is not a home for the
    # number a clerk typed; it is a table that proves the number is gone.
    "initial_reads": lambda r: next(
        (row.get("reading") for row in (_dig(r, "opening_reads", "rows") or ()) if row.get("reading")),
        None,
    ),
    # `customers 0059` / `DEF-CUS-5909` — p075's `Amount`, the figure the clerk
    # ASSESSED. It had NO HOME until 2026-09-20 and was reported homeless on
    # every money row; the shortfall is measured from it.
    "deposit.amount": lambda r: _dig(r, "money_taken", "assessed"),
    "deposit.amount_taken": lambda r: _dig(r, "money_taken", "taken"),
    "deposit.posted_at": lambda r: _dig(r, "money_taken", "taken_on"),
}


# ═══════════════════════════════════════════════════════════════════════════
# THE READBACK — PostgreSQL, never the service's own return value
# ═══════════════════════════════════════════════════════════════════════════
def observe(scenario: Scenario, world: World, result: dict[str, Any] | None,
            refusal: Any) -> dict[str, Any]:
    """Everything the checkers judge, read out of the tables."""
    unit_id = world.unit["id"]
    seen: dict[str, Any] = {"refusal": refusal, "result": result}

    occupying = [
        row
        for row in customers_models.Account.objects.filter(unit_id=unit_id).select_related("status")
        if customers_services.is_occupying(row.status)
    ]
    account = None
    if result is not None:
        account = customers_models.Account.objects.filter(pk=result["id"]).first()
    seen["unit_occupied"] = bool(occupying)
    seen["occupying_account_nos"] = sorted(row.account_no for row in occupying)

    # ── money ───────────────────────────────────────────────────────────────
    payments = list(payment_models.Payment.objects.filter(account_id=account.pk)) if account else []
    seen["payments"] = [
        {
            "purpose": row.purpose,
            "amount": Decimal(str(row.amount)),
            "status": row.status,
            "confirmation": row.confirmation,
            "cleared_at": row.cleared_at,
        }
        for row in payments
    ]
    lines = (
        list(
            ledger_models.JournalLine.objects.filter(
                source_id__in=[row.pk for row in payments]
            ).select_related("ledger_account")
        )
        if payments
        else []
    )
    seen["journal_lines"] = sorted(
        (row.side, row.ledger_account.designation, Decimal(str(row.amount))) for row in lines
    )
    seen["deposit_register"] = (
        Decimal(str(account.deposit_on_file)) if account and account.deposit_on_file is not None
        else (Decimal("0") if account else None)
    )

    # ── readings ────────────────────────────────────────────────────────────
    asset_ids = [
        row["id"] for row in __import__(
            "apps.metering.seams", fromlist=["x"]
        ).assets_on_unit(unit_id)
    ]
    reads = list(
        metering_models.MeterRead.objects.filter(
            asset_id__in=asset_ids, superseded_by_id__isnull=True
        )
    )
    seen["readings"] = {}
    for row in reads:
        key = row.event_context or "none"
        seen["readings"][key] = seen["readings"].get(key, 0) + 1
    seen["readings"].setdefault("move_in", 0)
    seen["read_dates"] = sorted(row.read_at.date().isoformat() for row in reads)

    # ── the record ──────────────────────────────────────────────────────────
    record_row = (
        moves.MoveRecord.objects.filter(account_id=account.pk).first() if account else None
    )
    seen["move_record"] = None
    seen["record_detail"] = None
    if record_row is not None:
        seen["move_record"] = {
            "kind": record_row.kind,
            "move_no": record_row.move_no,
            "request_id": str(record_row.request_id) if record_row.request_id else None,
            "reads_committed": record_row.reads_committed,
        }
        seen["record_detail"] = move_record_reads.record_detail(record_row.move_no)

    # ── who this account belongs to ─────────────────────────────────────────
    link = (
        customers_models.CustomerAccount.objects.filter(account_id=account.pk)
        .select_related("customer")
        .first()
        if account
        else None
    )
    seen["customer_link"] = (
        None
        if link is None
        else {
            "customer_id": str(link.customer_id),
            "customer_no": link.customer.customer_no,
            "kind": link.customer.kind,
            "tier": link.match_tier,
        }
    )
    seen["customer_count"] = customers_models.Customer.objects.count()

    # ── what was queued for the customer (U3) ───────────────────────────────
    seen["messages_queued"] = [
        dict(row) for row in ((result or {}).get("move_message") or ())
    ]
    seen["warnings"] = [row.get("code") for row in ((result or {}).get("warnings") or ())]
    seen["deposit_notes"] = list(((result or {}).get("deposit") or {}).get("notes") or ())
    return seen


# ═══════════════════════════════════════════════════════════════════════════
# THE CHECKERS — one per dimension, and every row goes through all eleven
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Check:
    dimension: str
    verdict: str  # PASS · FAIL · DECLARED-SILENT
    detail: str


def _pass(dim: str, detail: str = "") -> Check:
    return Check(dim, "PASS", detail)


def _fail(dim: str, detail: str) -> Check:
    return Check(dim, "FAIL", detail)


#: A currency amount, or a bare decimal that reads as one. Never a rule id.
_MONEY_IN_TEXT = __import__("re").compile(r"[$\u00a3\u20ac]\s?\d|\b\d[\d,]*\.\d{2}\b")


def _refusal_text(refusal: Any) -> str:
    if refusal is None:
        return ""
    params = getattr(refusal, "params", None) or {}
    return " ".join(
        str(part)
        for part in (
            getattr(refusal, "message_key", None),
            getattr(refusal, "br_ref", None),
            params.get("code"),
            params.get("detail"),
            params.get("reason"),
        )
        if part
    )


def check_outcome(want: Expect, seen: dict[str, Any]) -> Check:
    got = "refused" if seen["result"] is None else "committed"
    if got == want.value:
        return _pass("outcome", got)
    return _fail("outcome", f"wanted {want.value}, got {got}: {_refusal_text(seen['refusal'])}")


def check_refusal_name(want: Expect, seen: dict[str, Any], scenario: Scenario) -> Check:
    spec = want.value
    # S5 — the refusal under test belongs to the ESTIMATOR, not to the wizard.
    # `BR-MET-062`: no config, no history and no cap can make a demand estimate
    # lawful, so the engine refuses it before anything else about the row.
    if "demand_refusal" in seen and spec.get("code") == "demand_never_estimated":
        got = seen["demand_refusal"]
        if got.get("reason") != spec["code"]:
            return _fail("refusal_name", f"the estimator answered {got!r}, wanted {spec['code']!r}")
        if spec.get("br_ref") and spec["br_ref"] not in str(got.get("rule_ref") or ""):
            return _fail("refusal_name", f"cites {got.get('rule_ref')!r}, wanted {spec['br_ref']}")
        return _pass("refusal_name", f"{got['reason']} · {got['rule_ref']}")
    if scenario.money_probe:
        offer = seen.get("money_probe") or {}
        refused = offer.get("refused") or {}
        code, br_ref = refused.get("code"), refused.get("br_ref") or ""
        if not refused:
            return _fail("refusal_name", f"the money door did NOT refuse: offered={offer.get('offered')}")
        if code not in spec["code_in"]:
            return _fail("refusal_name", f"refused with {code!r}, wanted one of {spec['code_in']}")
        if spec.get("br_ref") and spec["br_ref"] not in br_ref:
            return _fail("refusal_name", f"cites {br_ref!r}, wanted {spec['br_ref']}")
        # ⚠ **A RULE ID HAS DIGITS IN IT AND IS NOT A FIGURE.** The hazard
        # `BR-CUS-089` names is a refused offer that still prints **$150.00** —
        # an invitation to type it in by hand. So this looks for MONEY.
        if spec.get("names_no_figure") and _MONEY_IN_TEXT.search(str(refused.get("detail") or "")):
            return _fail("refusal_name", "the refusal prints a money figure — BR-CUS-089's hazard")
        return _pass("refusal_name", f"{code} · {br_ref}")

    refusal = seen["refusal"]
    if refusal is None:
        return _fail("refusal_name", "nothing was refused")
    message_key = getattr(refusal, "message_key", None)
    br_ref = getattr(refusal, "br_ref", None) or ""
    params = getattr(refusal, "params", None) or {}
    if "message_key" in spec and message_key != spec["message_key"]:
        return _fail("refusal_name", f"message_key is {message_key!r}, wanted {spec['message_key']!r}")
    if "message_key_contains" in spec and spec["message_key_contains"] not in (message_key or ""):
        return _fail(
            "refusal_name",
            f"message_key {message_key!r} does not name {spec['message_key_contains']!r}",
        )
    if "br_ref" in spec and spec["br_ref"] not in br_ref:
        return _fail("refusal_name", f"cites {br_ref!r}, wanted {spec['br_ref']}")
    for name in spec.get("params", ()):
        if params.get(name) in (None, "", []):
            return _fail("refusal_name", f"the refusal does not name {name!r}: params={sorted(params)}")
    if spec.get("names_a_supervisor") and "supervis" not in _refusal_text(refusal).lower():
        return _fail("refusal_name", "the refusal never says a supervisor is needed")
    return _pass("refusal_name", f"{message_key} · {br_ref}")


def check_payment_rows(want: Expect, seen: dict[str, Any]) -> Check:
    spec, rows = want.value, seen["payments"]
    if len(rows) != spec["count"]:
        return _fail("payment_rows", f"{len(rows)} payment row(s) in PostgreSQL, wanted {spec['count']}")
    if spec["count"] == 0:
        return _pass("payment_rows", "no payment row — correct")
    row = rows[0]
    if row["purpose"] != spec["purpose"]:
        return _fail("payment_rows", f"purpose is {row['purpose']!r}, wanted {spec['purpose']!r}")
    if row["amount"] != spec["amount"]:
        return _fail("payment_rows", f"amount is {row['amount']}, wanted {spec['amount']}")
    return _pass("payment_rows", f"{len(rows)} × {row['purpose']} {row['amount']}")


def check_journal_pair(want: Expect, seen: dict[str, Any]) -> Check:
    lines = seen["journal_lines"]
    if want.value is None:
        if lines:
            return _fail("journal_pair", f"journal lines exist and should not: {lines}")
        return _pass("journal_pair", "no journal line — correct")
    debit, credit = want.value
    got_debit = {d for side, d, _a in lines if side == ledger_models.SIDE_DEBIT}
    got_credit = {d for side, d, _a in lines if side == ledger_models.SIDE_CREDIT}
    if debit not in got_debit or credit not in got_credit:
        return _fail(
            "journal_pair",
            f"wanted DR {debit} / CR {credit}; PostgreSQL holds DR {sorted(got_debit)} "
            f"/ CR {sorted(got_credit)}",
        )
    amounts = {a for _s, _d, a in lines}
    if len(amounts) != 1:
        return _fail("journal_pair", f"the pair does not balance: {sorted(amounts)}")
    return _pass("journal_pair", f"DR {debit} / CR {credit} · {amounts.pop()}")


def check_deposit_register(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen["deposit_register"]
    if want.value is None:
        return (
            _pass("deposit_register", "no account, so no register — correct")
            if got is None
            else _fail("deposit_register", f"an account exists holding {got}")
        )
    if got is None:
        return _fail("deposit_register", "no account was created, so the register cannot be read")
    if Decimal(str(got)) != Decimal(str(want.value)):
        return _fail("deposit_register", f"accounts.deposit_on_file is {got}, wanted {want.value}")
    return _pass("deposit_register", f"deposit_on_file = {got}")


def check_readings(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen["readings"]
    for event, count in want.value.items():
        if got.get(event, 0) != count:
            return _fail("readings", f"{got.get(event, 0)} {event!r} reading(s) in meter_reads, wanted {count}")
    return _pass("readings", ", ".join(f"{k}={v}" for k, v in sorted(got.items())))


def check_unit_occupied(want: Expect, seen: dict[str, Any]) -> Check:
    got = seen["unit_occupied"]
    if got != want.value:
        return _fail("unit_occupied", f"the unit derives occupied={got}, wanted {want.value}")
    return _pass("unit_occupied", f"occupied={got} ({', '.join(seen['occupying_account_nos']) or '—'})")


def check_move_record(want: Expect, seen: dict[str, Any]) -> Check:
    spec, row, detail = want.value, seen["move_record"], seen["record_detail"]
    if spec is None:
        return (
            _pass("move_record", "no record — correct, the commit was refused")
            if row is None
            else _fail("move_record", f"a move record exists and should not: {row['move_no']}")
        )
    if row is None:
        return _fail("move_record", "NO ROW in move_records")
    if row["kind"] != spec["kind"]:
        return _fail("move_record", f"kind is {row['kind']!r}")
    if not str(row["move_no"]).startswith(spec["prefix"]):
        return _fail("move_record", f"move_no {row['move_no']!r} does not start {spec['prefix']!r}")
    notes = [row["move_no"]]
    if spec.get("names_the_request") and not row["request_id"]:
        return _fail("move_record", "the record does NOT name the service request it came from")
    if "still_to_collect" in spec:
        got = _dig(detail or {}, "money_taken", "still_to_collect")
        if str(got) != spec["still_to_collect"]:
            return _fail(
                "move_record",
                f"`Still to collect` reads {got}, wanted {spec['still_to_collect']} "
                "(assessed minus taken, as p075's review computes it)",
            )
    if spec.get("says_no_meters"):
        absence = (_dig(detail or {}, "opening_reads") or {})
        unavailable = (detail or {}).get("opening_reads", {}).get("unavailable") or {}
        if not unavailable or "meter" not in str(unavailable.get("code", "")):
            return _fail("move_record", f"the record does not SAY the unit has no meters: {unavailable or absence}")
        notes.append(str(unavailable.get("code")))
    if "unread_registers" in spec:
        got = (detail or {}).get("chips", {}).get("unread_registers")
        if got != spec["unread_registers"]:
            return _fail("move_record", f"unread_registers reads {got}, wanted {spec['unread_registers']}")
        notes.append(f"unread={got}")
    if "read_date_kept" in spec:
        if spec["read_date_kept"] not in seen["read_dates"]:
            return _fail(
                "move_record",
                f"the clerk's own read date {spec['read_date_kept']} is not in meter_reads "
                f"(dates held: {seen['read_dates']})",
            )
        notes.append(f"read on {spec['read_date_kept']}")
    return _pass("move_record", " · ".join(notes))


def check_customer_link(want: Expect, seen: dict[str, Any]) -> Check:
    spec, link = want.value, seen["customer_link"]
    if spec["outcome"] == "none":
        return (
            _pass("customer_link", "nobody linked — correct")
            if link is None
            else _fail("customer_link", f"a customer was linked: {link['customer_no']}")
        )
    if link is None:
        return _fail("customer_link", "NO `customer_accounts` row — the account belongs to nobody")
    # `CR-058` tasks 7 and 8 — the ONE key a screen reads: `customer_outcome`.
    outcome = (seen["result"] or {}).get("customer_outcome")
    if outcome != spec["outcome"]:
        return _fail("customer_link", f"outcome is {outcome!r}, wanted {spec['outcome']!r}")
    if "tier" in spec and link["tier"] != spec["tier"]:
        return _fail(
            "customer_link",
            f"the stored match tier is {link['tier']!r}, wanted {spec['tier']!r} — "
            "BR-CUS-089 moves money only on a STORED strong tier",
        )
    if "kind" in spec and link["kind"] != spec["kind"]:
        return _fail("customer_link", f"customer kind is {link['kind']!r}, wanted {spec['kind']!r}")
    if spec.get("no_stale_not_linked_warning") and "customer_not_linked" in (seen["warnings"] or ()):
        return _fail(
            "customer_link",
            f"the commit linked customer {link['customer_no']} and still warns "
            "`customer_not_linked`, whose stated reason — that the `customers` entity "
            "has no table — expired on 2026-08-11",
        )
    if spec.get("reuses_existing") and seen["customer_count"] != 2:
        return _fail(
            "customer_link",
            f"{seen['customer_count']} customers exist — a returning customer must keep ONE "
            "number across tenancies (DEF-2587)",
        )
    return _pass("customer_link", f"{outcome} · {link['customer_no']} · tier={link['tier']}")


def check_field_homes(scenario: Scenario, seen: dict[str, Any]) -> tuple[Check, list[str]]:
    """**CHECK 1 — field by field, and report any field with NO HOME by name.**"""
    detail = seen["record_detail"]
    if detail is None:
        return _fail("field_homes", "no move record to walk"), []
    homeless: list[str] = []
    housed: list[str] = []
    for name, (step, value) in sorted(scenario.steps.captured().items()):
        if value in (None, "", [], {}):
            continue
        finder = MOVE_RECORD_HOMES.get(name)
        if finder is None:
            homeless.append(f"step {step} · {name}")
            continue
        try:
            found = finder(detail)
        except Exception:  # noqa: BLE001 — a finder that raises is a missing home
            found = None
        (housed if found not in (None, "", [], {}) else homeless).append(
            f"step {step} · {name}" if found in (None, "", [], {}) else name
        )
    verdict = _pass("field_homes", f"{len(housed)} housed · {len(homeless)} with NO HOME")
    return verdict, homeless


# ═══════════════════════════════════════════════════════════════════════════
# CHECK 2 — THE FRICTION LIST
# ═══════════════════════════════════════════════════════════════════════════
def collect_friction(scenario: Scenario, world: World, seen: dict[str, Any]) -> list[str]:
    """**What a clerk has to do that they should not have to.**

    ⚠ **THIS LIST HAS A BLIND SPOT AND IT IS PRINTED WITH THE LIST.** Every item
    is derived from the PAYLOAD the four steps composed and from what PostgreSQL
    holds afterwards. **This suite never opens a screen**, so it cannot see that
    one input box feeds two payload keys, or that a field arrives prefilled.

    ⚠ **THE FIRST VERSION OF THIS FUNCTION IGNORED THAT AND REPORTED TWO THINGS
    THAT WERE NOT TRUE.** It said the full name and the date of birth are *asked
    twice on step 2* — the screen has ONE box for each and builds both payload
    keys from it (`MoveInWizard.tsx:413` and `:1435`). And it said a
    request-fed move-in *re-keys* the applicant's name, phone, email and date of
    birth — the wizard prefills all four from the request, built the same day
    this ran. **A check that reasons about a screen it cannot see is hard-won
    law 7's fourth shape**, looking at the wrong thing, so each item below now
    says what it is evidence OF.
    """
    items: list[str] = []
    steps = scenario.steps

    # (a) ONE FACT, TWO PAYLOAD KEYS. Not clerk friction — the screen asks once.
    #     It is a DIVERGENCE hazard: two columns for one fact is `DEF-154`'s
    #     shape, and nothing makes the pair agree on the way in.
    identity = steps.step2_customer.get("identity") or {}
    for a, b, same in (
        ("contact.full_name", "customer.display_name",
         steps.step2_contact.get("full_name") == steps.step2_customer.get("display_name")),
        ("contact.dob", "customer.identity.date_of_birth",
         steps.step2_contact.get("dob") == identity.get("date_of_birth")),
        ("contact.phone", "customer.identity.phone",
         steps.step2_contact.get("phone") == identity.get("phone")),
    ):
        if same:
            items.append(
                f"one fact, two payload keys: `{a}` and `{b}`. The screen asks once; "
                "nothing makes the two agree on the way in"
            )

    # (b) WHAT A REQUEST-FED MOVE-IN STILL COSTS. The wizard prefills the name,
    #     the email, the phone, the date of birth and the language; the two
    #     ENCRYPTED identifiers are deliberately NOT copied, because the request
    #     serves only their last four and writing `••••4417` into the box would
    #     send that literal string as an identifier. So the residue is named as
    #     a KNOWN COST rather than as a defect.
    if world.request is not None:
        keyed = [
            name
            for name, present in (
                ("SSN", identity.get("ssn")),
                ("driving licence", identity.get("driving_licence")),
                ("Tax ID", identity.get("tax_id")),
            )
            if present
        ]
        if keyed:
            items.append(
                "re-keyed even though the move-in came from an application: "
                + ", ".join(keyed)
                + " — deliberate, because a request serves only the last four of an "
                "encrypted identifier (`BR-CUS-045`)"
            )

    # (c) TYPED AND LOST — database-observable, and the sharpest item here.
    lost = [
        name
        for name, (_step, value) in sorted(steps.captured().items())
        if value not in (None, "", [], {}) and name not in MOVE_RECORD_HOMES
    ]
    money_lost = [name for name in lost if name.startswith("deposit.")]
    if money_lost:
        items.append(
            "keyed on the money step and not readable afterwards: " + ", ".join(money_lost)
        )

    # (d) A REFUSAL WITH NO WAY OUT — payload-observable: it says no and names
    #     nothing the clerk can act on.
    refusal = seen["refusal"]
    if refusal is not None:
        params = getattr(refusal, "params", None) or {}
        actionable = {"earliest_start", "accepts", "account_no", "account_id"} & set(params)
        if not actionable:
            items.append(
                f"the refusal `{getattr(refusal, 'message_key', '?')}` names no way out — "
                f"params carried: {sorted(params) or 'none'}"
            )

    # (e) A WARNING A CLERK IS SHOWN THAT IS NOT TRUE OF THIS MOVE-IN.
    if seen["customer_link"] is not None and "customer_not_linked" in (seen["warnings"] or ()):
        items.append(
            "the confirmation carries `customer_not_linked` over a move-in that linked "
            f"customer {seen['customer_link']['customer_no']} (`DEF-CUS-5912`)"
        )
    return items


# ═══════════════════════════════════════════════════════════════════════════
# THE RUNNER — ONE function, nineteen rows
# ═══════════════════════════════════════════════════════════════════════════
#: Proving the suite can fail: `MOVE_IN_NINETEEN_BREAK=M1:payment_rows` damages
#: what the runner OBSERVED for that one dimension before the checkers see it.
#: Corrupting the observation rather than the declaration is deliberate — it
#: proves the checker really reads PostgreSQL's answer and compares it, which
#: inverting a verdict would not.
BREAK = os.environ.get("MOVE_IN_NINETEEN_BREAK", "")

_BREAKERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "payment_rows": lambda s: s["payments"].clear(),
    "journal_pair": lambda s: s["journal_lines"].clear(),
    "deposit_register": lambda s: s.__setitem__("deposit_register", Decimal("999.0000")),
    "readings": lambda s: s.__setitem__("readings", {"move_in": 99}),
    "unit_occupied": lambda s: s.__setitem__("unit_occupied", not s["unit_occupied"]),
    "move_record": lambda s: s.__setitem__("move_record", None),
    "customer_link": lambda s: s.__setitem__("customer_link", None),
    "outcome": lambda s: s.__setitem__("result", None),
    "refusal_name": lambda s: s.__setitem__("refusal", None),
}


def _apply_break(scenario: Scenario, seen: dict[str, Any]) -> str | None:
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
    checks: list[Check]
    homeless: list[str]
    friction: list[str]
    notes: list[str]

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.verdict == "FAIL"]


RESULTS: list[Result] = []


def run_scenario(scenario: Scenario, admin: Any, clerk: Any, tenant: Any) -> Result:
    world = build_world(admin, tenant, scenario)
    payload = compose(scenario, world)
    # ⚠ **M6 RUNS AS A BILLING CLERK ON PURPOSE.** p073 drew the option as
    # *Waive it (needs a supervisor)*; since 2026-09-24 (`OQ-CUS-12623`) a
    # clerk may waive, and a suite that waived as a system admin would never
    # prove it.
    actor = clerk if scenario.id == "M6" else admin

    result: dict[str, Any] | None = None
    refusal: Any = None
    try:
        result = customers_services.move_in(actor, world.outgoing["id"], payload)
    except (errors.BizError, errors.ValidationError, errors.NotFoundError, NotImplementedError) as exc:
        refusal = exc

    seen = observe(scenario, world, result, refusal)
    notes: list[str] = []

    if scenario.money_probe == "carry_forward":
        if seen["customer_link"] is not None:
            seen["money_probe"] = customers_discounts.carry_forward_offer(
                admin, seen["customer_link"]["customer_id"]
            )
            offer = seen["money_probe"]
            notes.append(
                f"carry-forward: offered={offer.get('offered')} "
                f"refused={(offer.get('refused') or {}).get('code')}"
            )
        else:
            seen["money_probe"] = {}

    # S5 — the estimator's own refusal, asked directly. `BR-MET-062`.
    if any(channel == "demand" for _n, _s, _u, channel in scenario.estate.meters):
        verdict = metering_estimation.estimate(
            metering_estimation.EstimationInput(
                channel="demand", unit="kW", days_in_period=30,
                trailing_actuals=[], consecutive_estimates=0,
            ),
            config=None,
        )
        seen["demand_refusal"] = {
            "reason": getattr(verdict, "reason", None),
            "rule_ref": (getattr(verdict, "detail", None) or {}).get("rule_ref"),
        }
        notes.append(f"estimator on a demand channel: {seen['demand_refusal']}")

    broke = _apply_break(scenario, seen)
    if broke:
        notes.append(f"⚠ DELIBERATELY BROKEN for this run: dimension `{broke}`")

    checks: list[Check] = []
    homeless: list[str] = []
    friction: list[str] = []
    for dimension in DIMENSIONS:
        want = scenario.expect[dimension]
        if isinstance(want, Silent):
            checks.append(Check(dimension, "SILENT", want.why))
            continue
        if dimension == "field_homes":
            verdict, homeless = check_field_homes(scenario, seen)
            checks.append(Check(dimension, "REPORT" if verdict.verdict == "PASS" else "FAIL",
                                verdict.detail))
            continue
        if dimension == "friction":
            friction = collect_friction(scenario, world, seen)
            checks.append(Check(dimension, "REPORT", f"{len(friction)} item(s)"))
            continue
        checks.append(
            {
                "outcome": lambda: check_outcome(want, seen),
                "refusal_name": lambda: check_refusal_name(want, seen, scenario),
                "payment_rows": lambda: check_payment_rows(want, seen),
                "journal_pair": lambda: check_journal_pair(want, seen),
                "deposit_register": lambda: check_deposit_register(want, seen),
                "readings": lambda: check_readings(want, seen),
                "unit_occupied": lambda: check_unit_occupied(want, seen),
                "move_record": lambda: check_move_record(want, seen),
                "customer_link": lambda: check_customer_link(want, seen),
            }[dimension]()
        )

    # U3 — how many of the five the commit QUEUED. Reported, never asserted.
    if result is not None:
        # ⚠ **NOT "N OF THE FIVE DRAWN" — THAT RATIO WAS WRONG AND THIS REPORT
        # PRINTED IT ONCE.** `queue_move_in_welcome` returns OUTCOME ROWS for
        # the ONE welcome letter, not one row per drawn message, so counting
        # them against p075's five compared two different things. The codes are
        # printed instead, which is what a reader can act on.
        codes = sorted(
            {str(row.get("code") or row.get("outcome") or "?") for row in seen["messages_queued"]}
        )
        notes.append(
            f"the commit queued {len(seen['messages_queued'])} outcome row(s) for the WELCOME "
            f"letter ({', '.join(codes) or 'none'}); p075 draws five messages"
        )
    if seen["warnings"]:
        notes.append("server warnings: " + ", ".join(sorted(set(seen["warnings"]))))
    if seen["deposit_notes"]:
        notes.append("deposit notes: " + ", ".join(seen["deposit_notes"]))
    return Result(scenario=scenario, checks=checks, homeless=homeless, friction=friction, notes=notes)


# ═══════════════════════════════════════════════════════════════════════════
# THE SUITE'S OWN GUARD — run FIRST, and it can refuse the whole table
# ═══════════════════════════════════════════════════════════════════════════
def test_every_scenario_declares_every_dimension() -> None:
    """**The PO's reason, mechanised.**

    *"Otherwise scenario twelve gets a check that scenario three doesn't, and
    nobody notices."* `declares()` already refuses an incomplete row at import,
    so this asserts the two things it cannot: that there are NINETEEN of them,
    and that every id is unique. A twentieth row silently replacing a
    nineteenth would otherwise pass everything.
    """
    assert len(SCENARIOS) == 19, f"the PO specified nineteen; the table holds {len(SCENARIOS)}"
    ids = [row.id for row in SCENARIOS]
    assert len(set(ids)) == 19, f"duplicate scenario id: {sorted(ids)}"
    assert {row.group for row in SCENARIOS} == {"MONEY", "REFUSAL", "REPRESENTATIVE"}
    assert len([r for r in SCENARIOS if r.group == "MONEY"]) == 6
    assert len([r for r in SCENARIOS if r.group == "REFUSAL"]) == 5
    assert len([r for r in SCENARIOS if r.group == "REPRESENTATIVE"]) == 8
    for row in SCENARIOS:
        assert set(row.expect) == set(DIMENSIONS), row.id


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[row.id for row in SCENARIOS])
def test_move_in_scenario(scenario: Scenario, brazos: Any, dana: Any, marcus: Any) -> None:
    """One row of the table, end to end, read back from PostgreSQL.

    ⚠ **A RED ROW HERE IS THE DELIVERABLE, NOT A BROKEN TEST.** The assertion
    message names what the product does and what the drawing or the signed rule
    says it should do. Weakening one to reach green would delete the finding.
    """
    with tenant_ctx(brazos):
        outcome = run_scenario(scenario, dana, marcus, brazos)
    RESULTS.append(outcome)
    if outcome.failed:
        lines = [f"{scenario.id} · {scenario.title}", ""]
        for check in outcome.failed:
            want = scenario.expect[check.dimension]
            why = getattr(want, "why", "") or ""
            lines.append(f"  ✗ {check.dimension}: {check.detail}")
            if why:
                lines.append(f"      because: {why}")
        pytest.fail("\n".join(lines), pytrace=False)


# ═══════════════════════════════════════════════════════════════════════════
# U4 — "BILLABLE", THE ONE NOBODY HAS WATCHED HAPPEN
# ═══════════════════════════════════════════════════════════════════════════
def test_u4_billable_against_a_fresh_move_in_account(brazos: Any, dana: Any, marcus: Any) -> None:
    """**Is a fresh move-in account actually billable?**

    The PO's Approve list has seven items and six of them are asserted by the
    nineteen. This is the seventh, and the conformance record is explicit that
    it is *"not proved … a bill has not been run against a fresh move-in"*.

    ⚠ **IT ASSERTS WHAT IT FINDS RATHER THAN A VERDICT IT WANTS.** Billing has
    its own preconditions — a cycle, a period, a priced schedule — and a
    move-in that opens an account correctly is not answerable for them. What
    this proves is the ONE thing the move-in owns: **the account reaches the
    biller as a billable scope rather than being rejected at the door.**
    """
    from apps.billing import single as billing_single
    from apps.metering import seams as metering_seams

    from tests.test_us_bil_001_prepare import a_priced_plan
    from tests.test_us_met_reads_helpers import commit_read

    with tenant_ctx(brazos):
        scenario = SCENARIOS[0]  # M1 — the fully-formed happy money path
        world = build_world(dana, brazos, scenario)
        # ⚠ **THE UNIT'S PLAN IS SWAPPED FOR A PRICED ONE, AND THAT IS THE
        # WHOLE DIFFERENCE FROM M1.** The nineteen stand on a published plan
        # with no tariff VERSION, which is all an account needs to be opened —
        # and `BR-RAT-007` gives a bill no fallback to today's prices, so the
        # first attempt at this came back `tariff_has_no_version_in_force`.
        # That was the FIXTURE's silence, not the move-in's, and leaving it
        # would have been a check reporting an absence it created itself.
        priced = a_priced_plan(brazos, name="Move-in billable")
        # ⚠ `effective_from` IS PASSED AND IT IS LOAD-BEARING: the default is
        # the tenant's TODAY, so an assignment made now is not in force during
        # a period that ended yesterday, and the bill refuses with *no tariff
        # version in force across …* — a refusal about the fixture's dates
        # wearing the words of a rating rule.
        metering_services.assign_unit_plan(
            dana,
            world.unit["id"],
            {"tariff_id": str(priced.id), "effective_from": "2026-01-01"},
        )
        # ⚠ AND THE PRICED PLAN ASKS M1's DEPOSIT TOO (2026-09-23, `DEF-CUS-6369`):
        # the deposit is the PLAN's figure now, so a plan that asks none refuses
        # M1's *take it* by name — correctly, and not what this case is about.
        _state_the_plan_deposit(brazos, priced, PLAN_STANDARD)
        result = customers_services.move_in(dana, world.outgoing["id"], compose(scenario, world))
        # A closing read, so there is CONSUMPTION to price. The opening read the
        # wizard committed is the period's start; this is its end.
        asset_id = metering_seams.assets_on_unit(world.unit["id"])[0]["id"]
        commit_read(dana, asset_id, day="2026-09-19", value="42364",
                    prior_value="41680", consumption="684")
        verdict: dict[str, Any] = {"account_no": result["account_no"]}
        try:
            prepared = billing_single.prepare_single_bill(
                account_id=result["id"],
                period_start=date(2026, 8, 20),
                period_end=date(2026, 9, 19),
                service_date=date(2026, 9, 19),
            )
            verdict["ready"] = len(getattr(prepared, "ready", []) or [])
            verdict["blocked"] = [
                getattr(row, "code", None) or str(row) for row in (getattr(prepared, "blocked", []) or [])
            ]
            verdict["silent"] = [
                getattr(row, "code", None) or str(row) for row in (getattr(prepared, "silent", []) or [])
            ]
        except Exception as exc:  # noqa: BLE001 — the refusal IS the finding
            verdict["refused"] = f"{type(exc).__name__}: {exc}"
    BILLABLE.append(verdict)
    # The account must at least be a scope the biller ACCEPTS. Anything else —
    # ready, blocked for want of a reading, silent — is reported, not judged.
    assert "refused" not in verdict, (
        "a bill run against a fresh move-in account was REFUSED at the door: " + str(verdict)
    )
    assert verdict["ready"] == 1, (
        "a fresh move-in account, on a priced plan and with a reading, did not reach the "
        "biller as billable: " + str(verdict)
    )


BILLABLE: list[dict[str, Any]] = []


# ═══════════════════════════════════════════════════════════════════════════
# THE REPORT — printed at the end of the module, and written to a file
# ═══════════════════════════════════════════════════════════════════════════
def _row_line(result: Result) -> str:
    counted = [c for c in result.checks if c.verdict in ("PASS", "FAIL")]
    failed = [c for c in counted if c.verdict == "FAIL"]
    mark = "RED " if failed else "GREEN"
    return (
        f"  {mark}  {result.scenario.id:<3} {result.scenario.title[:62]:<62} "
        f"{len(counted) - len(failed)}/{len(counted)}"
    )


@pytest.fixture(scope="module", autouse=True)
def report() -> Any:
    """Prints the whole table once, after the last row. Run with `-s`."""
    yield
    if not RESULTS:
        return
    order = {row.id: index for index, row in enumerate(SCENARIOS)}
    RESULTS.sort(key=lambda r: order.get(r.scenario.id, 99))
    green = [r for r in RESULTS if not r.failed]
    red = [r for r in RESULTS if r.failed]

    out: list[str] = []
    out.append("")
    out.append("═" * 92)
    out.append("  THE MOVE-IN SCENARIO SUITE — nineteen rows, one table")
    out.append("═" * 92)
    out.append(f"  {len(green)} GREEN · {len(red)} RED   of {len(RESULTS)} run")
    out.append("")
    for group in ("MONEY", "REFUSAL", "REPRESENTATIVE"):
        out.append(f"  ── {group} " + "─" * (86 - len(group)))
        for result in RESULTS:
            if result.scenario.group == group:
                out.append(_row_line(result))
    out.append("")
    if red:
        out.append("  ── WHAT EACH RED ROW MEANS " + "─" * 63)
        for result in red:
            out.append(f"  {result.scenario.id} · {result.scenario.title}")
            for check in result.failed:
                out.append(f"      ✗ {check.dimension}: {check.detail}")
        out.append("")

    homeless: dict[str, set[str]] = {}
    for result in RESULTS:
        for name in result.homeless:
            homeless.setdefault(name, set()).add(result.scenario.id)
    if homeless:
        out.append("  ── FIELDS WITH NO HOME ON THE MOVE RECORD " + "─" * 49)
        out.append("     (a clerk typed it; `GET /moves/{ref}` cannot show it back)")
        for name in sorted(homeless):
            out.append(f"      · {name}   [{', '.join(sorted(homeless[name]))}]")
        out.append("")

    friction: dict[str, set[str]] = {}
    for result in RESULTS:
        for item in result.friction:
            friction.setdefault(item, set()).add(result.scenario.id)
    if friction:
        out.append("  ── THE FRICTION LIST " + "─" * 69)
        out.append("     (derived from the payload and the database. THIS SUITE NEVER OPENS A")
        out.append("      SCREEN, so it cannot see one box feeding two keys, or a prefill.)")
        for item in sorted(friction):
            out.append(f"      · {item}   [{', '.join(sorted(friction[item]))}]")
        out.append("")

    out.append("  ── DECLARED NOT ASSERTED, per row " + "─" * 57)
    for result in RESULTS:
        for check in result.checks:
            if check.verdict == "SILENT":
                out.append(f"      {result.scenario.id} · {check.dimension}: {check.detail}")
    out.append("")

    # ⚠ **U3 SAYS THIS SUITE *"COUNTS THE ROWS THE COMMIT QUEUES AND REPORTS
    # THE NUMBER"*, AND UNTIL THIS BLOCK EXISTED IT COUNTED THEM AND REPORTED
    # NOTHING.** A declared capability the report does not deliver is a claim
    # nobody can check — hard-won law 1 in the shape this file is most exposed
    # to, since the whole point of the suite is what it prints.
    notes: dict[str, set[str]] = {}
    for result in RESULTS:
        for note in result.notes:
            notes.setdefault(note, set()).add(result.scenario.id)
    if notes:
        out.append("  ── WHAT THE RUN OBSERVED BESIDE THE ASSERTIONS " + "─" * 44)
        for note in sorted(notes):
            out.append(f"      · {note}   [{', '.join(sorted(notes[note]))}]")
        out.append("")

    out.append("  ── DECLARED UNTESTABLE " + "─" * 67)
    for entry in UNTESTABLE:
        out.append(f"      {entry['id']} · {entry['what']}")
        out.append(f"          {entry['why']}")
    if BILLABLE:
        out.append(f"      U4 measured: {BILLABLE[0]}")
    out.append("")
    out.append("  ── SAFETY " + "─" * 80)
    out.append("      The beta database was not opened. Every scenario ran on its own tenant")
    out.append("      inside the pgtest database, and `django_db` rolled each one back.")
    out.append("═" * 92)

    text = "\n".join(out)
    print(text)
    try:
        artefact = Path(os.environ.get("MOVE_IN_NINETEEN_REPORT", "")) if os.environ.get(
            "MOVE_IN_NINETEEN_REPORT"
        ) else None
        if artefact is not None:
            artefact.write_text(
                text
                + "\n\n"
                + json.dumps(
                    {
                        "green": [r.scenario.id for r in green],
                        "red": {r.scenario.id: [c.detail for c in r.failed] for r in red},
                        "homeless": {k: sorted(v) for k, v in homeless.items()},
                        "friction": {k: sorted(v) for k, v in friction.items()},
                        "billable": BILLABLE,
                        "notes": {k: sorted(v) for k, v in notes.items()},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    except OSError:  # pragma: no cover — a report that cannot be written is not a failure
        pass


# ── Trace ──────────────────────────────────────────────
# status: the suite is the deliverable; a RED row is a finding, never a defect
#         in this file. Amend a row only with a ruling behind it.
# ──────────────────────────────────────────────────────
