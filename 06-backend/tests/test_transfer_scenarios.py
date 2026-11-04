# ── Trace ──────────────────────────────────────────────
# Component: THE PROPERTY-SALE SCENARIO SUITE — the PO's end-to-end transfer
#            walk, ONE declarative table, ONE runner, ONE command, TWO score
#            columns.
# Change:   PO 2026-09-20, verbatim: *"once you are done with changes for
#           tranfer - do the end to end walk - create request , see all transfer
#           work corectly - property, address, assets, units - occupancy is
#           updated at unit . assets whow correct account - money part is
#           correct, email, communcation is send"*.
# Story:    US-CUS-004 · US-CUS-005 (a sale is the THIRD path beside them and
#           owns no story of its own) · US-CUS-027 §8 (the wizard) ·
#           US-LED-001 (the books a sale must not write)
# Rules:    BR-CUS-1030 (a transfer REASSIGNS the account — one account, never
#           closed, the CUSTOMER changes) · BR-CUS-1031 (a customer MOVING is a
#           new Service Request) · BR-CUS-1022/1023/1024 (who a buyer must be,
#           and the one identifier) · BR-CUS-085 (nothing is refunded and
#           re-collected) · BR-CUS-015 (the balance is a CACHE) · BR-CUS-023
#           (the deposit is a lookup) · BR-CUS-054 (the customer entity and
#           `customer_accounts`) · BR-CUS-057 (deposit interest — CONFIRMED,
#           NOT BUILT) · BR-CUS-080 (the request that raised the job) ·
#           BR-CUS-1011 (one master per address — DISSOLVED by the ruling) ·
#           BR-CUS-017 (one occupying account per unit — likewise) ·
#           BR-MET-036 (occupancy is DERIVED) · BR-MET-044 (the plan lives on
#           the UNIT) · BR-SHL-019 (ONE transactional commit) · BR-SHL-025
#           (server-enforced RBAC) · CLAUDE.md hard rules 1, 2, 4, 5, 7, 8 ·
#           hard-won laws 1, 2, 6, 7, 14
# Blueprint: 04-docs/05-modules/03-customers/blueprint/11-transfer-wizard.md,
#           extracted from `05-prototype/02 Accounts Menu Blueprint.pdf`
#           p124–p133. ⚠ Every figure DRAWN there is an ILLUSTRATION and never
#           a fact to build to (B14 rule 37) — what this suite asserts is the
#           SHAPE the drawing argues for (`Refunded to the seller $0.00`,
#           `Re-collected from the buyer $0.00`) and the figures it creates
#           itself.
# Tests:    this file IS the test
# Journey:  08-qa/01-e2e/journeys/J-TRF-TWENTYFIVE-the-property-sale-scenario-suite.md
# ───────────────────────────────────────────────────────
"""**Twenty-five property-sale scenarios, declared in one table, run by one
runner, scored in TWO columns.**

═══════════════════════════════════════════════════════════════════════════
⚠ WHAT A TRANSFER IS, BECAUSE HALF THE PRODUCT STILL SAYS OTHERWISE
═══════════════════════════════════════════════════════════════════════════
`BR-CUS-1030`, PO 2026-09-01, verbatim: ***"dont create new account - we
reassing that account - bascailly I have sold my property - so account get
transfer to new person or business; if I move to new location then it is new
Service request and we follow the process"***.

**ONE ACCOUNT. NEVER CLOSED. SAME UNIT. SAME METERS. ONE UNBROKEN LEDGER. THE
CUSTOMER CHANGES.** That sentence is the spine of every row below, and it is
asserted rather than described: `unchanged` is a dimension of its own and every
one of the twenty-five declares a verdict for it.

⚠ **TWO OF THE PO's OWN CHECKS NEED CARE RATHER THAN LITERAL READING, AND THE
SUITE REPORTS WHAT IT FINDS RATHER THAN FORCING A VERDICT:**

  * ***"occupancy is updated at unit"*** — **the unit does not change hands;
    the ACCOUNT does.** `BR-MET-036` derives occupancy from the occupying
    account, and that account is the same row before and after. So the honest
    assertion is **UNCHANGED**: `occupancy: occupied`, the same `account_no`,
    the same unit. A suite that asserted a CHANGE here would be asserting the
    flow the ruling deleted. ⚠ **What DOES move is the name beside it**, and
    that is the finding — see `occupancy_at_unit`'s own note.
  * ***"assets show correct account"*** — **the account number does not
    change** (`A-11455` before and after), so an asset that still points at the
    same account is RIGHT. The question worth asking is whether anything about
    an asset wrongly names the old CUSTOMER, and `assets_and_account` asks
    exactly that.

═══════════════════════════════════════════════════════════════════════════
WHY ONE TABLE — THE MOVE-OUT SUITE'S REASON, WHICH IS THE PO'S
═══════════════════════════════════════════════════════════════════════════
*"Otherwise scenario twelve gets a check that scenario three doesn't, and
nobody notices."* So every row of `SCENARIOS` declares a verdict for **every
one of the thirteen dimensions** in `DIMENSIONS`, and `declares()` refuses the
row at IMPORT time if one is missing — before it can be collected, run and
reported as a pass over checks nobody wrote. A row with nothing to say about a
dimension says `Silent("why")` **out loud**, and that sentence is printed in
the report where a reader can disagree with it.

═══════════════════════════════════════════════════════════════════════════
⚠ TWO SCORE COLUMNS, AND THEY ARE A SCORING VIEW OVER **ONE** RUN
═══════════════════════════════════════════════════════════════════════════
The move-out suite ran every row TWICE because `settlement_for` takes the final
bill FROM ITS CALLER, so *asked with a bill* and *asked without one* are two
genuinely different questions about one customer's money. **A sale takes no
such argument.** Running each row twice here would run the same walk twice and
report the same answer twice, so this suite runs each row ONCE and scores it
in two columns:

  * **TODAY** — what the product does now. A check whose row declares
    `waits_on=<keystone>` is scored `WAITING` here rather than `FAIL`, so a
    real gap and a lane in flight never land in the same bucket.
  * **WHEN THE LANES LAND** — every check counted, `waits_on` or not. This is
    the column that says what SHOULD pass once the five in-flight keystones
    land, and **a red cell in it is the deliverable, not a broken test.**

⚠ **NOTHING IS SUPPRESSED IN EITHER COLUMN.** Every declared check RUNS on
every row, always; the columns differ only in how a failure is counted. That is
deliberately stronger than skipping the check in one pass: **a `waits_on` check
that PASSES is counted as a pass in BOTH columns**, so the day a keystone lands
the report says so by itself instead of waiting for somebody to re-read the
table.

⚠ **AND COMPLETE IN A COLUMN MEANS NO FAILURE *AND* NOTHING LEFT UNASSERTED.**
A row whose identity check could not be scored is not complete, however many of
its other checks passed — counting it green would report a scenario as working
on the strength of the dimensions that are not what it is about.

═══════════════════════════════════════════════════════════════════════════
⚠ THIS SUITE IS EXPECTED TO BE PARTLY RED, AND THAT IS THE DELIVERABLE
═══════════════════════════════════════════════════════════════════════════
It is written against what the blueprint and the signed rules PROMISE, not
against what the product currently does. Every red row names something that is
not built and the report says which keystone each one waits on. **Do not weaken
an assertion to make it green** — move the product, or move the row with a
ruling behind it.

═══════════════════════════════════════════════════════════════════════════
SAFETY — THE BETA IS NEVER OPENED
═══════════════════════════════════════════════════════════════════════════
**A sale COMMITS.** It rewrites `customer_accounts`, writes a `transfers` row,
raises work orders and writes `audit_log`. `customer_accounts` is a link table
and not one of hard rule 4's four, but a `transfers` row is permanent and the
audit rows are, and thirteen database triggers refuse the deletes a tenant drop
would need.

So the throwaway utility is **a whole PostgreSQL database**, not a tenant inside
the live one: `--ds=config.settings.pgtest` puts the run on
`test_sbh_<checkout>_<digest>`, and the beta named in `DATABASE_URL` is opened
for nothing at all. Each scenario provisions its OWN tenant inside that database
through the real signup path, and `django_db` rolls the whole graph back when
the scenario ends. `10-scripts/transfer_scenarios.sh` counts the beta's
accounts, transfers, customer links, payments, journal lines, invoices and
parked drafts BEFORE and AFTER anyway — **a claim nobody has checked is not a
safety guarantee** (hard-won law 1). The move-out suite's script is this one's
source and its reasoning is quoted there rather than reinvented.

═══════════════════════════════════════════════════════════════════════════
EVERY FIGURE AND EVERY REFUSAL READS BACK FROM POSTGRESQL
═══════════════════════════════════════════════════════════════════════════
Not from a service's return value and never from a screen. `observe()` goes to
the tables — `accounts`, `customer_accounts`, `customers`, `transfers`,
`service_agreements`, `units`, `premises`, `assets`, `asset_assignments`,
`payments`, `journal_lines`, `invoices`, `outbound_messages`, `wizard_parks` —
because a response that says *reassigned* over a row that did not move is the
class of defect that only surfaces in front of a customer.

⚠ **THE TWO ZEROS ARE DERIVED FROM THE TABLES, NOT READ OFF A FIELD.**
`BR-CUS-085` — *nothing is refunded and re-collected* — is drawn on step 5 as
`Refunded to the seller $0.00` and `Re-collected from the buyer $0.00`, and
**neither row is served by anything today** (the conformance file records both
as absent). Reading a field that does not exist would be a check that cannot
fail, so the suite computes both from what PostgreSQL holds: the deposit on the
account BEFORE minus AFTER is what was refunded, and any payment row written
against the account by the sale is what was re-collected. Both must be
`$0.00`, and they are **the point** rather than a formality.

═══════════════════════════════════════════════════════════════════════════
HOW TO RUN IT
═══════════════════════════════════════════════════════════════════════════
    ./10-scripts/transfer_scenarios.sh

or, by hand, from `06-backend/`:

    set -a; . ./.env; set +a
    JOBS_EAGER=false .venv/bin/pytest tests/test_transfer_scenarios.py \\
        --ds=config.settings.pgtest --reuse-db -q -s

⚠ **`06-backend/.venv/bin/python` IS THE INTERPRETER.** Nothing on `PATH`
imports Django and a gate prints a FALSE sentence claiming none can
(`DEF-GOV-5925`), which stopped two lanes.

**PROVING IT CAN FAIL** (hard-won law 7 — a suite first seen green is a suite
nobody has proved): set `TRANSFER_BREAK=<scenario id>:<dimension>` and that one
OBSERVATION is corrupted before the checkers see it. The scenario must go RED on
exactly that dimension and on nothing else.
`./10-scripts/transfer_scenarios.sh --prove-red` does two of them for you, on
two different checkers, and then shows the same rows green again.

Corrupting the OBSERVATION rather than the DECLARATION is deliberate: it proves
the checker really reads PostgreSQL's answer and compares it, which inverting a
verdict would not.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import pytest

from apps.assets import selectors as asset_selectors
from apps.customers import models as customers_models
from apps.customers import move_reads, request_jobs
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_service
from apps.customers import services as customers_services
from apps.customers import transfer_reads, transfers
from apps.ledger import models as ledger_models
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.notifications import models as notification_models
from apps.notifications import transfer_events as notification_transfer_events
from apps.payments import models as payment_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import wizard_parks
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

D = Decimal
ZERO = D("0")


# ═══════════════════════════════════════════════════════════════════════════
# THE CALENDAR — one clock for all twenty-five, so no row invents its own
# ═══════════════════════════════════════════════════════════════════════════
#: The tenancy that changes hands. The blueprint draws `Opened 03/08/2022`; the
#: day is this suite's own and the shape is the drawing's.
OPENED = "2024-11-28"
#: **The day of sale.** The blueprint's step 3: *"The day the account changes
#: hands."* `set_sale_date` writes it to BOTH `out_date` and `in_date`, so
#: `same_day` is true by construction — one date, because there is only one.
SOLD_ON = "2026-05-09"
#: The genuine move-out `CT1` performs on an account sold four months earlier
#: (`DEF-CUS-5913`). A real date after the sale, so the two acts cannot be
#: confused for one.
MOVED_OUT_ON = "2026-09-14"

#: The premises this suite sells, spelled once. Hard rule 8 — an address is
#: stored on **`premises`** and NOWHERE else — so this is the ONE place the
#: suite knows an address, and every assertion about a service address walks to
#: the premises to get it rather than comparing two copies.
ADDRESS_LINE = "1408 Elm Street"
ADDRESS_CITY = "Silver Creek"
ADDRESS_STATE = "TX"
ADDRESS_POSTAL = "78611"

#: The money positions. Real figures on a real account, chosen so every
#: subtraction below comes out at a readable number a person can check by hand.
#: **No rule states any of them** and none is a golden figure.
ARREAR = D("318.4000")
DEPOSIT = D("150.0000")
#: **`BR-CUS-050`'s ORIGINAL RECEIPT DATE, AND IT IS LOAD-BEARING.**
#: `deposit_interest_accrued` answers **`None` — never zero —** for a deposit
#: with no receipt date stamped on it, because `BR-CUS-057`'s clock then has no
#: start and *"guessing the account's opening date instead would be wrong on
#: every such account at once"*. So a row that wants the engine to ANSWER
#: stamps one, and `MN4` deliberately does not, which is what makes its stated
#: absence a measurement rather than an accident of the fixture.
DEPOSIT_RECEIVED_ON = "2024-11-28"

#: The two parties. `555-` lines are reserved for fiction, the posture
#: `tests/identity_fixtures.py` already takes.
SELLER_NAME = "Delgado, R."
SELLER_PHONE = "+1-555-0311"
BUYER_NAME = "Vasquez, M."
BUYER_PHONE = "+1-555-0197"
COMPANY_BUYER_NAME = "Quarry Lane Holdings LLC"
COMPANY_BUYER_TAX_ID = "74-2051887"

#: A buyer identified by a PHONE AND NOTHING ELSE — `BR-CUS-1023`'s weakest
#: lawful identifier, and the PO's own sentence: *"Without identifier we cannot
#: create Customer ID"*. It is deliberately the boundary rather than a
#: comfortable case well inside it.
BUYER_PERSON: dict[str, Any] = {
    "display_name": BUYER_NAME,
    "kind": "person",
    "identity": {"phone": BUYER_PHONE},
}
BUYER_COMPANY: dict[str, Any] = {
    "display_name": COMPANY_BUYER_NAME,
    "kind": "company",
    "identity": {"tax_id": COMPANY_BUYER_TAX_ID},
}


# ═══════════════════════════════════════════════════════════════════════════
# THE KEYSTONES — what a red check is waiting for, named beside every red row
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **EACH IS A LANE IN FLIGHT OR A RULING NOT YET BUILT, AND NOTHING ELSE.**
#: A keystone is not a place to park an assertion that is merely inconvenient:
#: a check that fails for any other reason is a REAL GAP and is counted in the
#: TODAY column, which is what makes that column worth reading.

#: **`KEY_SELLER_DURABLE`** — PO ruling 2026-09-20, verbatim: *"we cannot
#: override customer id - seller and buyer cstmer id are unique those does not
#: change"*. Today `transfers.py:1451` DELETES the seller's `customer_accounts`
#: row and `reassign_account` overwrites `transfers.customer_id` with the
#: buyer's, so **the seller survives only in `audit_log`, which is pruned on a
#: retention schedule.** The decision log of 2026-09-20 proposes ENDING the
#: seller's link rather than deleting it. A lane is on it.
KEY_SELLER_DURABLE = "seller_link_ended_not_deleted"

#: **`KEY_ESTATE_ON_THE_STEP`** — PO ruling 2026-09-20, verbatim on step 3:
#: *"Premises, Units, Meters, Assets, these detaisla re not shown"*. **A clerk
#: is asked to sell a property they cannot see.** A lane is building it.
#:
#: ⚠ **STEP 3 ONLY, AND THAT IS A NARROWING RULED HOURS LATER.** The same
#: sitting also said it of step 1 — *"on customer selection premsies details are
#: not shown"* — and the PO then reversed that half: ***"not required -
#: displayed on next step 3"***, because step 3 already draws `What changes
#: hands on that day` and **one set of facts in one place is the point**. A
#: suite still waiting on a step-1 panel would be waiting for something nobody
#: is going to build.
KEY_ESTATE_ON_THE_STEPS = "premises_units_meters_assets_on_step_3"

#: **`KEY_TRANSFER_MESSAGES`** — PO 2026-09-20, verbatim: *"no commucation
#: options"*, and it has a register row of its own: **`DEF-CUS-5949`**, *"A sale
#: tells nobody it happened"*. `notifications_seam` publishes five account
#: message kinds and **not one of them is a transfer**, so a sale queues nothing
#: at all: neither the buyer nor the seller is told the account changed hands.
#: The blueprint draws three messages going on commit.
KEY_TRANSFER_MESSAGES = "transfer_message_kind"

#: **`KEY_COUNTING_CONTRACT`** — `DEF-CUS-5913`. `transfer_half_account_ids()`
#: names every non-cancelled transfer's `from_account_id` FOREVER, and
#: `move_reads.move_outs_queryset` subtracts it. The exclusion was correct while
#: a committed transfer CLOSED its outgoing half; `BR-CUS-1030` removed the
#: closure and nothing re-read the consumers.
KEY_COUNTING_CONTRACT = "move_outs_exclusion_rewritten_for_the_sale"

#: **`KEY_TRANSFER_RECORD`** — there is no `GET /transfers/{id}` and no record
#: page at any address, so **a clerk can make a sale and has no way to read it
#: back.** The conformance file calls it the sharpest gap on this surface.
KEY_TRANSFER_RECORD = "transfer_record_page_and_read"

#: The `models.SOURCE_TYPES` kind a SALE's messages ride, read off the module
#: that owns the vocabulary rather than typed as a literal — so a rename there
#: breaks this import instead of silently making the count zero, which is the
#: quietest way a scoped observation goes wrong.
TRANSFER_SOURCE_KIND = notification_transfer_events.SOURCE_TRANSFER

KEYSTONES: tuple[str, ...] = (
    KEY_SELLER_DURABLE,
    KEY_ESTATE_ON_THE_STEPS,
    KEY_TRANSFER_MESSAGES,
    KEY_COUNTING_CONTRACT,
    KEY_TRANSFER_RECORD,
)

#: ✅ **A DEPOSIT ON THE ACCOUNT CRASHED THE SALE UNTIL 03:00 ON 2026-09-20,
#: AND THIS SUITE IS HOW IT WAS FOUND HERE.** `transfers._deposit_interest`
#: resolved `customers.selectors.deposit_interest_accrued` through the seam and
#: called it as `read(account.id)`. That function takes `(account_id, as_of)`
#: and `as_of` has no default (`BR-TEN-043`, gate G6), so every sale of an
#: account holding a deposit raised
#:
#:     TypeError: deposit_interest_accrued() missing 1 required positional
#:                argument: 'as_of'
#:
#: — at STEP 4 (`acknowledge_money`), at the COMMIT (`reassign_account`) and,
#: worst, **once per row of the Transfers TAB**, because
#: `transfer_reads.list_row` calls `_statement_for` for every row it draws. A
#: 500 rather than a refusal, on three surfaces.
#:
#: ⚠ **FIXED IN `e4bc49a0d` (`DEF-CUS-5940`), BY A SIBLING LANE, WHILE THIS
#: SUITE WAS BEING WRITTEN.** Both lanes found it independently within the
#: hour, from opposite directions — theirs from the buyer-capture ruling,
#: this one from three rows of a scenario table. The rows that carry a deposit
#: are `SL1`, `MN2` and `MN4` and they carry one again.
#:
#: ⛔ **AND ONE CALL SITE IS STILL BROKEN — `apps/customers/discounts.py:858`**,
#: which is the identical one-argument call and is reached by
#: `GET /customers/{id}/deposit-position` for any customer holding a CLOSED
#: account with a deposit on it. `DEF-CUS-5940`'s own row names two call sites
#: (`transfers`, `move_out_settlement`) and there are THREE — the same
#: enumeration-by-memory that produced the defect, made once more inside its own
#: fix. **Filed as `DEF-CUS-5970` and PROVED by calling `deposit_position` on a
#: closed account holding `$150.00`**, rather than inferred from the source.
#: This suite does not walk that endpoint, so it is NAMED here rather than
#: asserted: `UNTESTABLE` entry `U6` says so where a reader will meet it.
DEPOSIT_INTEREST_CRASH = (
    "deposit_interest_accrued(account_id) with one argument where the published "
    "signature is (account_id, as_of) — fixed in transfers by DEF-CUS-5940, still "
    "live at discounts.py:858"
)

#: The two score columns. They are a VIEW over one run — see the module
#: docstring — and never two walks of the product.
COLUMN_TODAY = "today"
COLUMN_LANES = "when the lanes land"


# ═══════════════════════════════════════════════════════════════════════════
# THE THIRTEEN DIMENSIONS — every row answers all of them
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **THE LIST IS THE CONTRACT.** Adding a fourteenth makes every one of the
#: twenty-five rows incomplete until it declares one, which is the PO's
#: *"scenario twelve gets a check that scenario three doesn't"* working as
#: intended. Do not give a dimension a default.
#:
#: The PO's own sentence maps onto them one for one, and that mapping is the
#: reason there are thirteen rather than some tidier number:
#:   *"create request"*            → `outcome` · `transfer_record`
#:   *"property, address, ... units"* → `property_and_address`
#:   *"assets"*                    → `assets_and_account`
#:   *"occupancy ... at unit"*     → `occupancy_at_unit`
#:   *"assets show correct account"* → `assets_and_account`
#:   *"money part is correct"*     → `money` · `books_and_payments`
#:   *"email, communcation is send"* → `communication`
#: and the four that are nobody's sentence but every rule's — `refusal_name`,
#: `unchanged`, `identity`, `lists_and_counting` — are the ones `BR-CUS-1030`
#: makes load-bearing.
DIMENSIONS: tuple[str, ...] = (
    "outcome",              # did the sale commit, or was it refused?
    "refusal_name",         # WHICH refusal, by reason code and rule — never "an error"
    "property_and_address", # premises · unit · the address, WALKED, never copied
    "assets_and_account",   # every meter on the unit, and the account it shows
    "occupancy_at_unit",    # BR-MET-036's derived occupancy after the sale
    "money",                # balance · deposit · interest · taken on · THE TWO ZEROS
    "books_and_payments",   # journal lines, payments, invoices — expected: NONE
    "unchanged",            # number · unit · meters · plan · agreements · status · ledger
    "identity",             # the buyer is the customer; the SELLER stays discoverable
    "communication",        # what the commit QUEUES. Queued is not sent.
    "transfer_record",      # the `transfers` row, and what it names
    "lists_and_counting",   # the Transfers list, and what it subtracts from other tabs
    "friction",             # what a clerk has to do that they should not have to
)


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A ROW MAY DECLARE FOR A DIMENSION
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Expect:
    """An assertion. `value` is compared with what PostgreSQL actually holds.

    ⚠ **`waits_on` NAMES A KEYSTONE AND DOES NOT SKIP THE CHECK.** The check
    RUNS; a failure is scored `WAITING` in the TODAY column and `FAIL` in the
    WHEN-THE-LANES-LAND column. A **pass** counts as a pass in both, so the day
    a keystone lands the report says so on its own rather than waiting for
    somebody to re-read this table — which is the half the move-out suite's
    `only=` could not do, because a check it skipped could never surprise it.
    """

    value: Any
    why: str = ""
    waits_on: str | None = None


@dataclass(frozen=True)
class Silent:
    """**A declared non-assertion.** Printed, never hidden.

    ⚠ **THIS TYPE IS THE WHOLE REASON THE TABLE IS A TABLE.** An omitted key is
    indistinguishable from an oversight; a `Silent` carries its reason into the
    report where a reader can disagree with it. Hard-won law 7's *"a declared
    blind spot with no NUMBER attached is indistinguishable from an empty
    one"*, one layer up.
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
    #: AT ALL**, which `PR2` exists to prove a sale does not refuse — and to
    #: pin the asset dimension to an honest empty rather than an unasserted one.
    meters: tuple[tuple[str, str, str], ...] = (("M-5180", "electric", "kWh"),)
    unit_label: str = "Unit 1"
    unit_type: str = "residential"
    #: What `accounts.balance` holds — **the CACHED AR figure** (`BR-CUS-015`),
    #: written through the ORM because `services.REFUSED_FIELDS` refuses it on
    #: every client-facing path. A fixture that could set it through a door
    #: would mean the product had one.
    arrear: Decimal = ZERO
    #: What `accounts.deposit_on_file` holds. Same route, same reason
    #: (`BR-CUS-023` — the deposit is a lookup; every write path is refused).
    deposit: Decimal = ZERO
    #: `BR-CUS-050`'s original receipt date. **`None` means the register row was
    #: never stamped**, which is a real state on every account that predates
    #: that rule — and `BR-CUS-057`'s engine then answers `None` rather than
    #: zero, because its clock has no start. `MN4` is the row that uses it.
    deposit_received_on: str | None = DEPOSIT_RECEIVED_ON
    #: A SECOND occupied unit at the same premises, so a sale can be proved not
    #: to touch the neighbour AND both can be proved to walk to the same
    #: address (hard rule 8).
    neighbour: bool = False
    #: A SECOND account held by the SELLER at another address — the blueprint's
    #: *"The seller keeps every other account they hold."*
    sellers_other_account: bool = False
    #: The buyer already exists as a customer on this tenant before the sale,
    #: so `link_customer` MATCHES rather than creates.
    buyer_already_on_file: bool = False
    #: The account is opened and then CLOSED before the sale is attempted —
    #: `RF4`'s `from_account_is_not_an_occupant`.
    close_before_selling: bool = False
    #: The account is opened with NO customer block, so nothing links it —
    #: `SL5`, which was `RF5`'s refusal until 2026-09-23 (`DEF-CUS-6387`): such
    #: an account now SELLS, and the seller is recorded by name.
    no_customer_on_file: bool = False
    #: A `transfer` service request, approved, which RAISES the job through
    #: `request_jobs._raise_transfer`. **This is the PO's *"create request"* and
    #: it is the SECOND door into a sale** — the first being the wizard.
    from_request: bool = False


@dataclass(frozen=True)
class Steps:
    """**What the five steps asked the clerk for**, step by step.

    Declared per step rather than as one payload, because the friction check
    needs to know WHICH step each field came from, and because a reader
    comparing this with the blueprint should be able to put their finger on the
    line.
    """

    #: Step 2 — the buyer. `None` means the row states no buyer at all, which
    #: is `RF1`'s refusal and a real thing a clerk can do.
    buyer: dict[str, Any] | None = field(default_factory=lambda: dict(BUYER_PERSON))
    #: Step 3 — `Date of sale`. `None` means the clerk keyed none, which the
    #: commit refuses by name (`step_3_sale_date`).
    sold_on: str | None = SOLD_ON
    #: Step 2's right-hand panel — the changeover read. `None` leaves it alone.
    field_visit: Any = None
    #: Who is at the counter. `clerk` is a BILLING_CLERK, `admin` a SYSTEM
    #: ADMIN. Both may sell (`BR-SHL-025`), and a row runs as a clerk where the
    #: point is that a clerk can.
    actor: str = "admin"


@dataclass(frozen=True)
class Scenario:
    """One row. Setup, inputs, and a verdict for all thirteen dimensions."""

    id: str
    group: str
    title: str
    estate: Estate
    steps: Steps
    expect: dict[str, Declaration]
    #: Which keystones this row waits on OVERALL. Printed beside every red row.
    #: A row may name a keystone no individual check waits on — that is the
    #: row saying *"and this is the wider thing I am about"*.
    blocked_on: tuple[str, ...] = ()
    #: `wizard` (the five service calls, which is what the wizard's one POST
    #: runs stage by stage) · `door` (the composed `POST /transfers/commit`
    #: inside ONE outer transaction) · `park_resume` · `sell_then_move_out` ·
    #: `second_sale`.
    road: str = "wizard"


ROADS: tuple[str, ...] = (
    "wizard",
    "from_request",
    "door",
    "park_resume",
    "sell_then_move_out",
    "second_sale",
)


# ═══════════════════════════════════════════════════════════════════════════
# THE BLOCKS THE FIVE STEPS FILL, so twenty-five rows do not retype them
# ═══════════════════════════════════════════════════════════════════════════
#: The service address, composed ONCE, from the ONE place an address lives
#: (CLAUDE.md hard rule 8 — *"an address is stored on `premises` and NOWHERE
#: else"*). Every row that asserts an address asserts THIS string, and the
#: observation builds it by WALKING from the asset or the account to the
#: premises rather than by reading a column on the way.
SERVICE_ADDRESS = f"{ADDRESS_LINE}, {ADDRESS_CITY}, {ADDRESS_STATE} {ADDRESS_POSTAL}"


def estate_seen(*, meters: int = 1, neighbour_units: int = 0) -> dict[str, Any]:
    """The property, the unit and the address, as every ordinary sale leaves
    them: **entirely unmoved.**

    `address_walked` is the hard-rule-8 assertion and it is not a formality —
    it is TRUE only when the address the product serves for this unit came out
    of `premises`, and `unit_declares_an_address` is FALSE only when the `units`
    table carries no address column of its own. The two together are the rule
    (*"a unit refines a premises by LABEL, not by address"*), asserted rather
    than trusted.
    """
    return {
        "premises_changed": False,
        "unit_changed": False,
        "unit_label": "Unit 1",
        "service_address": SERVICE_ADDRESS,
        "address_walked": True,
        "unit_declares_an_address": False,
        "units_at_premises": 1 + neighbour_units,
        "meters_on_the_unit": meters,
        # ⚠ **THE KEYSTONE'S OWN CHECK, AND IT IS A SERVER QUESTION RATHER
        # THAN A SCREEN ONE.** The PO's finding was *"Premises, Units, Meters,
        # Assets, these detaisla re not shown"* and this suite cannot see a
        # screen — but it CAN ask the thing underneath it: **does the
        # transfer's own read carry the property the clerk is being asked to
        # sell?** `_serialize` publishes two account numbers, two dates, a
        # step, a state and `to_unit_id`, and not one fact about the premises,
        # the unit, the meters or the assets. So every screen that shows them
        # has to go and fetch them from somewhere else, which is exactly how a
        # step comes to show none of them.
        #
        # A keystone that holds up NO check is a keystone nobody has proved
        # exists (hard-won law 7), and this is the check that makes
        # `KEY_ESTATE_ON_THE_STEPS` mean something the suite can measure.
        "the_transfer_read_carries_the_estate": True,
    }


def assets_seen(*, count: int = 1, names_buyer: bool = True) -> dict[str, Any]:
    """Every meter on the unit, and the account each one shows.

    ⚠ **THE ACCOUNT NUMBER IS THE EASY HALF AND IT PASSES.** A sale changes no
    account number, so an asset still pointing at `A-…` is RIGHT — asserting a
    CHANGE here would be asserting the flow `BR-CUS-1030` deleted. What this
    dimension is really for is the other half: **`billing_chain.account` also
    carries a `customer_name`, and that name is read from `contacts`, which a
    sale does not touch.** So the question the PO's *"assets show correct
    account"* actually raises is whether anything about an asset names the old
    CUSTOMER, and `names_the_seller` is where it is answered.

    ⚠ **RED ON 17 OF THE 25 ROWS AND FILED AS `DEF-CUS-5971`.** The sharpest
    form of it is one row of the Accounts list: `selectors.account_row` serves
    `customer_no` (the buyer's, right) beside `name` (the seller's, stale) —
    one product, two answers to *whose account is this*.
    """
    return {
        "count": count,
        "every_asset_names_the_selling_account": True,
        "account_no_changed": False,
        "assets_moved": 0,
        "address_on_every_asset": SERVICE_ADDRESS if count else None,
        "names_the_buyer": names_buyer,
        "names_the_seller": not names_buyer,
    }


def occupancy_seen(*, names_buyer: bool = True) -> dict[str, Any]:
    """`BR-MET-036`'s derived occupancy, after the sale.

    ⚠ **THE VERDICT IS *UNCHANGED*, AND THAT IS THE ANSWER RATHER THAN A
    DODGE.** The PO asked that *"occupancy is updated at unit"*; under
    `BR-CUS-1030` the unit does not change hands and the ACCOUNT does, so the
    occupying account is the same row before and after and `occupancy` must
    still read `occupied` with the same number. **A suite that asserted a
    change here would be asserting the job the ruling deleted.**

    What SHOULD move is the name: the unit row's `occupant` column is the
    account's customer, and after a sale that is the buyer. It reads
    `primary_contact_name`, which a sale does not touch.
    """
    return {
        "occupancy": "occupied",
        "account_no_changed": False,
        "occupant_names_the_buyer": names_buyer,
        "occupant_names_the_seller": not names_buyer,
        "vacant": False,
    }


def money_seen(*, arrear: str, deposit: str, shown: Any = "0.00") -> dict[str, Any]:
    """What the buyer takes on — and **the two zeros, which are the point.**

    `BR-CUS-085` / the blueprint's step 5: `Refunded to the seller $0.00` and
    `Re-collected from the buyer $0.00`. Neither row is served by anything
    today, so both are DERIVED from PostgreSQL — the deposit on the account
    before minus after, and any payment row the sale wrote against it. A check
    that read a field the screen does not serve could not fail.

    ⚠ **`shown` IS THE DEPOSIT *PLUS ITS INTEREST*, WHICH IS WHAT THE STATEMENT
    ACTUALLY PUBLISHES**, and naming it `deposit_interest` would have been a
    check pointed at the wrong number. `_serialize` emits
    `money.deposit_carried` = principal + interest, and it emits **`None`**
    when `BR-CUS-057` cannot answer. So:

      * an account holding **NO deposit** shows `"0.00"` — a real ZERO, because
        there is nothing to accrue on and the engine is not consulted at all;
      * an account holding a deposit whose interest is **unreadable** shows
        `None`, which is the blueprint's *"— not recorded"* and **not a zero**:
        a `$0.00` there would state `$150.00` where ❄️ WE-7's frozen pair says
        `$153.50` is held.
    """
    return {
        "balance_changed": False,
        "deposit_changed": False,
        "balance_after": arrear,
        "deposit_after": deposit,
        "deposit_and_interest_shown": shown,
        "taken_on_by_the_buyer": arrear,
        # ⛔ THE TWO ZEROS. Derived, never read off a screen.
        "refunded_to_the_seller": "0.00",
        "recollected_from_the_buyer": "0.00",
        "balance_at_sale_recorded": arrear,
        "deposit_at_sale_recorded": deposit,
    }


#: **NO BOOKS, NO DRAWER, NO BILL.** The account carries its own ledger and the
#: account does not move, so *the debt following the property* costs one line of
#: code and writes nothing. Asserted rather than described, so the day a sale
#: starts posting a journal line against an unsigned contract the suite notices
#: — which is exactly what CLAUDE.md hard rule 5 exists to prevent.
NO_BOOKS = {
    "journal_lines": 0,
    "payments": 0,
    "invoices": 0,
    "refund_rows": 0,
    "journal_lines_claimed": 0,
    "refund_raised_claimed": False,
}

#: The spine of `BR-CUS-1030`, as a dict. **Nine facts, and a sale may move
#: none of them.**
UNCHANGED = {
    "account_no_changed": False,
    "unit_changed": False,
    "status_class_changed": False,
    "closed_at": None,
    "agreements_ended": 0,
    "plan_on_unit_changed": False,
    #: ⊕ **2026-09-20 — THE PO's *"plans are get atatched to account of
    #: buyer"*, asserted from the ACCOUNT's side rather than the unit's.**
    #: `plan_on_unit_changed` above already watched `units.rate_plan_id`; this
    #: watches what `GET /accounts/{id}` actually serves as `unit_plan`, which
    #: is the walk a screen makes. The two can only disagree if the walk
    #: breaks, and nothing was watching the walk.
    "the_accounts_plan_changed": False,
    "meters_removed": 0,
    "accounts_created": 0,
    "accounts_closed": 0,
    "ledger_lines_on_the_account_changed": 0,
    # Hard rule 4 — *"Invoices already issued to the SELLER stay exactly as
    # issued, in the seller's name, for ever."*
    "invoices_touched": 0,
}


def identity_seen(*, second_customer: bool) -> dict[str, Any]:
    """Who the account belongs to, and **whether the seller survives.**

    ⚠ **PO ruling 2026-09-20, verbatim: *"we cannot override customer id -
    seller and buyer cstmer id are unique those does not change"*.** Three of
    the keys below are declared TRUE and are FALSE today, each waiting on
    `KEY_SELLER_DURABLE`: `reassign_account` DELETES the seller's
    `customer_accounts` row and overwrites `transfers.customer_id`, so after a
    sale **the seller survives only in `audit_log`, which is pruned.**

    ⚠ `second_customer` is `BR-CUS-1024` and NOT a defect either way. A
    returning PERSON buyer gets a second Customer # because a phone is not one
    of that rule's reuse identifiers; a returning COMPANY matches on its Tax ID
    and gets none. Both are the signed rule, so the row states which it expects
    rather than the suite assuming one.
    """
    return {
        "account_customer_is_the_buyer": True,
        "seller_customer_row_survives": True,
        "seller_linked_to_this_account": True,
        "transfer_row_names_the_seller": True,
        "buyer_customer_no_changed": False,
        "seller_customer_no_changed": False,
        "second_customer_created": second_customer,
        #: ⊕ **2026-09-20 — PO, verbatim: *"are you checking account - name
        #: change to new buyer"*.** The Accounts list's `name` cell, asserted.
        "the_account_name_is_the_buyers": True,
        "the_account_name_did_not_move": False,
        #: ⊕ **AND THE CONSTRAINT THE SAME SENTENCE CARRIES — *"customer id we
        #: cannnot trsnfer to new buyer"*, with the ruling of the same day:
        #: *"seller and buyer cstmer id are unique those does not change"*.**
        #: TWO PEOPLE, TWO NUMBERS, PERMANENTLY.
        #:
        #: ⚠ **THIS EXISTS TO CATCH THE TEMPTING FIX AND NOTHING ELSE.** The
        #: cheapest way to make every name assertion above go green is to
        #: write the buyer's details onto the `customers` row the account
        #: already points at. It would work, instantly, on every surface —
        #: and it would MERGE TWO PEOPLE INTO ONE and destroy the seller's
        #: identity with no error anywhere. Nothing asserted it before today.
        "the_seller_and_the_buyer_are_two_numbers": True,
        "the_sellers_own_record_still_names_the_seller": True,
    }


#: The `waits_on` map `identity_seen`'s three keys carry. Per KEY rather than
#: per CHECK, because two of this dimension's seven facts are already true and
#: scoring the whole dimension as WAITING would hide that.
IDENTITY_WAITS = {
    "seller_linked_to_this_account": KEY_SELLER_DURABLE,
    "transfer_row_names_the_seller": KEY_SELLER_DURABLE,
}

#: **WHAT THE COMMIT QUEUES — AND QUEUED IS NOT SENT.**
#:
#: ⚠ **MEASURED 2026-09-19: 426 messages are queued in this product and NOT
#: ONE has ever been sent** (`sent_at` null on every row), both channels report
#: *not connected*, and the transfer wizard's own review step says *"Nothing is
#: sent by this screen. No channel exists yet."* So this suite asserts what is
#: QUEUED, counts what is SENT, and **never reports a queue as a delivery.**
#:
#: The blueprint draws THREE messages going out on commit — change of ownership
#: to the buyer, change of ownership to the seller, and a field-visit SMS.
#: `notifications_seam` publishes five account message kinds and **not one of
#: them is a transfer**, so today the answer is ZERO: neither party is told.
COMMUNICATION_WHEN_WIRED = {
    "queued_by_the_commit": 3,
    "queued_to_the_buyer": 2,
    "queued_to_the_seller": 1,
    "sent": 0,
    "a_transfer_message_kind_exists": True,
}
COMMUNICATION_WAITS = {
    "queued_by_the_commit": KEY_TRANSFER_MESSAGES,
    "queued_to_the_buyer": KEY_TRANSFER_MESSAGES,
    "queued_to_the_seller": KEY_TRANSFER_MESSAGES,
    "a_transfer_message_kind_exists": KEY_TRANSFER_MESSAGES,
}


def record_seen(**over: Any) -> dict[str, Any]:
    """The `transfers` row a completed sale leaves, read back from the table."""
    base = {
        "state": "done",
        "step": 5,
        "committed": True,
        "one_date_not_two": True,
        "sold_on": SOLD_ON,
        "from_and_to_are_one_account": True,
        "readable_back_through_a_door": True,
    }
    base.update(over)
    return base


RECORD_WAITS = {"readable_back_through_a_door": KEY_TRANSFER_RECORD}


def lists_seen(**over: Any) -> dict[str, Any]:
    """The Transfers list, and what the sale subtracts from other screens."""
    base = {
        "on_the_transfers_list": True,
        "in_the_published_exclusion_set": True,
        "on_the_move_outs_list": False,
        "on_the_move_ins_list": False,
    }
    base.update(over)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# ⬛ THE TWENTY-FIVE
# ═══════════════════════════════════════════════════════════════════════════
SCENARIOS: list[Scenario] = []


def _ordinary(
    *,
    arrear: str,
    deposit: str,
    meters: int = 1,
    names_buyer: bool = True,
    #: ⚠ **TRUE BY DEFAULT, BECAUSE THE ORDINARY BUYER IS A NEW ONE.** Every
    #: row whose buyer is not already on file mints a Customer #, so a
    #: `False` default would have made twenty rows assert that the product
    #: does NOT do the thing it is supposed to do.
    second_customer: bool = True,
    neighbour_units: int = 0,
    #: What the statement publishes as deposit-PLUS-interest. `_MATCHES` means
    #: *"the deposit itself"*, which is the answer whenever the tenant's
    #: `BR-CUS-057` rate is the seeded default of **0%** — a real ZERO term on a
    #: real engine call, not an absence. A row that wants the ABSENCE states
    #: `shown=None` and drops the receipt date.
    shown: Any = "<the deposit itself>",
    **over: Declaration,
) -> dict[str, Declaration]:
    """The verdict block an ORDINARY completed sale gets, for all thirteen.

    Written once because twenty of the twenty-five say the same thing about
    eight of the dimensions, and the twenty-first would be the one that drifted.
    A row that differs passes the dimension by name in `**over`.
    """
    block: dict[str, Declaration] = {
        "outcome": Expect("committed", "a sale with an identified buyer commits"),
        "refusal_name": Silent("this row commits — there is no refusal to name"),
        "property_and_address": Expect(
            estate_seen(meters=meters, neighbour_units=neighbour_units),
            "a sale moves no premises, no unit and no address (BR-CUS-1030)",
            waits_on={"the_transfer_read_carries_the_estate": KEY_ESTATE_ON_THE_STEPS},
        ),
        "assets_and_account": Expect(
            assets_seen(count=meters, names_buyer=names_buyer),
            "the meters stay and every one of them names the account that was sold",
        ),
        "occupancy_at_unit": Expect(
            occupancy_seen(names_buyer=names_buyer),
            "BR-MET-036 — the unit is still occupied by the same account",
        ),
        "money": Expect(
            money_seen(
                arrear=arrear,
                deposit=deposit,
                shown=deposit if shown == "<the deposit itself>" else shown,
            ),
            "the debt follows the property and NOTHING moves (BR-CUS-085)",
        ),
        "books_and_payments": Expect(
            dict(NO_BOOKS), "a sale writes no journal line, no payment and no invoice"
        ),
        "unchanged": Expect(dict(UNCHANGED), "BR-CUS-1030's spine, asserted"),
        "identity": Expect(
            identity_seen(second_customer=second_customer),
            "the buyer becomes the customer and the seller must stay discoverable",
            waits_on=dict(IDENTITY_WAITS),
        ),
        "communication": Expect(
            dict(COMMUNICATION_WHEN_WIRED),
            "the blueprint draws three messages on commit; QUEUED, never sent",
            waits_on=dict(COMMUNICATION_WAITS),
        ),
        "transfer_record": Expect(
            record_seen(), "one job, one account, one date", waits_on=dict(RECORD_WAITS)
        ),
        "lists_and_counting": Expect(
            lists_seen(), "the sale is on the Transfers tab and on neither move tab"
        ),
        "friction": Report(),
    }
    block.update(over)
    return block


# ───────────────── SALE · who is buying, and on what evidence ──────────────
# ⚠ **`BR-CUS-1023` — *"Without identifier we cannot create Customer ID"*.**
# These four differ in WHO the buyer is and in nothing else, so a difference in
# outcome is attributable to the buyer rather than to the estate.
SCENARIOS += [
    Scenario(
        id="SL1",
        group="SALE",
        title="a new person buys it — the canonical sale, with a balance and a deposit",
        # The blueprint's own account holds `Deposit on file $150.00`, and a
        # canonical sale that quietly dropped it would be a canonical sale of a
        # different account.
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        # `shown=None` because `BR-CUS-057` is CONFIRMED and NOT BUILT, so the
        # deposit-plus-interest figure is a stated absence rather than `$150.00`.
        expect=_ordinary(arrear="318.40", deposit="150.00"),
    ),
    Scenario(
        id="SL2",
        group="SALE",
        title="a COMPANY buys it, matched on its Tax ID — no second customer number",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, buyer_already_on_file=True),
        steps=Steps(buyer=dict(BUYER_COMPANY)),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="318.40", deposit="150.00", second_customer=False),
    ),
    Scenario(
        id="SL3",
        group="SALE",
        title="a returning PERSON buys it — a second number, and that is the signed rule",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, buyer_already_on_file=True),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        # ⚠ **NOT A DEFECT, AND THE ROW SAYS SO RATHER THAN THE SUITE ASSUMING
        # IT.** `BR-CUS-1024`'s reuse identifiers do not include a phone, so a
        # person returning on a phone alone is a NEW customer entity. A row that
        # declared `False` here would be asserting against a signed rule.
        expect=_ordinary(arrear="318.40", deposit="150.00", second_customer=True),
    ),
    Scenario(
        id="SL4",
        group="SALE",
        title="the buyer offers a phone and nothing else — the weakest lawful identifier",
        estate=Estate(arrear=ZERO, deposit=ZERO),
        steps=Steps(buyer={"display_name": "Okonkwo, A.", "kind": "person",
                           "identity": {"phone": "+1-555-0144"}}, actor="clerk"),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="0.00", deposit="0.00", second_customer=True),
    ),
]

# ───────────────── MONEY · the four positions, and the two zeros ───────────
# ⚠ **THE POINT OF THIS GROUP IS THE TWO ZEROS**, and they are DERIVED from
# PostgreSQL rather than read off a screen — see `money_seen`. `BR-CUS-085`:
# nothing is refunded and nothing is re-collected, on ANY of the four.
SCENARIOS += [
    Scenario(
        id="MN1",
        group="MONEY",
        title="arrears and no deposit — the buyer takes on the debt",
        estate=Estate(arrear=ARREAR, deposit=ZERO),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="318.40", deposit="0.00"),
    ),
    Scenario(
        id="MN2",
        group="MONEY",
        title="a deposit and no arrears — it stays on the account, unrefunded",
        estate=Estate(arrear=ZERO, deposit=DEPOSIT),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="0.00", deposit="150.00"),
    ),
    Scenario(
        id="MN3",
        group="MONEY",
        title="neither — every figure zero, and no sentence claims a movement",
        estate=Estate(arrear=ZERO, deposit=ZERO),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="0.00", deposit="0.00"),
    ),
    Scenario(
        id="MN4",
        group="MONEY",
        title="a deposit whose INTEREST cannot be read — `not recorded`, never $0.00",
        # ⛔ **NO RECEIPT DATE ON PURPOSE.** `BR-CUS-057`'s clock has no start,
        # so the engine answers `None` and the statement must say *"— not
        # recorded"* rather than `$0.00`.
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, deposit_received_on=None),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            # ⚠ **`BR-CUS-057` IS CONFIRMED AND NOT BUILT**, so the accrual is
            # UNREADABLE and the statement must say so. A `0.00` here would
            # state $150.00 where ❄️ WE-7's frozen pair says $153.50 is held —
            # which is the one money figure on this screen that a zero would
            # make WRONG rather than merely empty.
            money=Expect(
                {
                    **money_seen(arrear="318.40", deposit="150.00", shown=None),
                    "deposit_interest_is_a_stated_absence": True,
                    "deposit_interest_is_zero": False,
                    "gap_named": "deposit_interest_not_readable",
                },
                "a zero here would state $150.00 where $153.50 is held (WE-7)",
            ),
        ),
    ),
]

# ───────────────── PROPERTY · what changes hands with the account ──────────
# ⚠ **THE PO's *"property, address, assets, units"*, one row each.** The
# blueprint draws these on step 1 and step 3 and the product shows them on
# NEITHER (PO 2026-09-20: *"Premises, Units, Meters, Assets, these detaisla re
# not shown"*) — so `KEY_ESTATE_ON_THE_STEPS` is the keystone every row here
# names, and the FACTS below are asserted from the tables anyway. **What a
# screen fails to draw and what the product fails to hold are two different
# defects and this group keeps them apart.**
SCENARIOS += [
    Scenario(
        id="PR1",
        group="PROPERTY",
        title="two meters, electric and water — both stay, both name the one account",
        estate=Estate(
            meters=(("M-5180", "electric", "kWh"), ("M-5181", "water", "gal")),
            arrear=ARREAR,
            deposit=DEPOSIT,
        ),
        steps=Steps(),
        blocked_on=(KEY_ESTATE_ON_THE_STEPS, KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES,
                    KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="318.40", deposit="150.00", meters=2),
    ),
    Scenario(
        id="PR2",
        group="PROPERTY",
        title="a unit with NO METER at all — the sale is not refused",
        estate=Estate(meters=(), arrear=ZERO, deposit=ZERO),
        steps=Steps(),
        blocked_on=(KEY_ESTATE_ON_THE_STEPS, KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES,
                    KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="0.00",
            deposit="0.00",
            meters=0,
            # ⚠ **AN HONEST EMPTY RATHER THAN AN UNASSERTED ONE.** A unit with
            # no meter has no asset to name an account, and the dimension says
            # so with a COUNT rather than going silent — hard-won law 7's *"a
            # declared blind spot with no NUMBER attached is indistinguishable
            # from an empty one"*.
            assets_and_account=Expect(
                {
                    "count": 0,
                    "every_asset_names_the_selling_account": True,
                    "account_no_changed": False,
                    "assets_moved": 0,
                    "address_on_every_asset": None,
                    # ⚠ **FALSE, AND IT WAS DECLARED TRUE FROM BIRTH — A ROW
                    # INCAPABLE OF PASSING (law 7), corrected 2026-10-02.** The
                    # runner computes `names_the_buyer` as `bool(names) and
                    # all(...)` on purpose, so an EMPTY list names nobody rather
                    # than vacuously everybody; with no meter there is no asset
                    # to name anyone. The vacuity is stated by the key below,
                    # which is the honest place for it. PR2 was red on this
                    # line alone from 2026-09-20 (`c6ae58315`).
                    "names_the_buyer": False,
                    "names_the_seller": False,
                    "vacuously_true_because_there_are_no_assets": True,
                },
                "no meter is a lawful state and a sale does not refuse it",
            ),
        ),
    ),
    Scenario(
        id="PR3",
        group="PROPERTY",
        title="a neighbour at the same address — untouched, and both walk to one premises",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, neighbour=True),
        steps=Steps(),
        blocked_on=(KEY_ESTATE_ON_THE_STEPS, KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES,
                    KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            neighbour_units=1,
            # ⚠ **HARD RULE 8, STATED AS A CONSEQUENCE RATHER THAN A PRINCIPLE.**
            # Two units, one premises, one address — so a sale that touched an
            # address at all would be visible on the neighbour, and a unit that
            # carried its own address column could let the two disagree.
            property_and_address=Expect(
                {
                    **estate_seen(meters=1, neighbour_units=1),
                    "neighbour_account_changed": False,
                    "neighbour_customer_changed": False,
                    "neighbour_walks_to_the_same_address": True,
                },
                "an address lives on `premises` and NOWHERE else (hard rule 8)",
                waits_on={"the_transfer_read_carries_the_estate": KEY_ESTATE_ON_THE_STEPS},
            ),
        ),
    ),
]

# ───────────────── REFUSAL · the five a clerk can actually reach ───────────
# ⚠ **A REFUSAL IS NAMED BY ITS REASON CODE AND ITS RULE, NEVER BY "an
# error"**, because a screen that says *something went wrong* over a recoverable
# refusal is the defect `BR-CUS-1023` exists to stop (*name the missing thing
# at the door where the clerk is typing*).
def _refused(reason: str, *, why: str, **over: Declaration) -> dict[str, Declaration]:
    block: dict[str, Declaration] = {
        "outcome": Expect("refused", why),
        "refusal_name": Expect(reason, "the reason code, not an error class"),
        "property_and_address": Expect(
            estate_seen(), "a refused sale moves nothing at all",
            waits_on={"the_transfer_read_carries_the_estate": KEY_ESTATE_ON_THE_STEPS},
        ),
        "assets_and_account": Expect(
            assets_seen(count=1, names_buyer=False),
            "nothing changed hands, so the seller is still right",
        ),
        "occupancy_at_unit": Expect(
            occupancy_seen(names_buyer=False), "the seller is still the occupant"
        ),
        "money": Silent("no sale, no figures — the money dimension has nothing to judge"),
        "books_and_payments": Expect(dict(NO_BOOKS), "a refusal writes nothing either"),
        "unchanged": Expect(dict(UNCHANGED), "the refusal left the account exactly as it was"),
        # ⚠ **`transfer_row_names_the_seller` DEFAULTS TO **FALSE** HERE, AND
        # THAT IS A CORRECTION THE SUITE MADE TO ITSELF.** It defaulted TRUE,
        # which is true only of a refusal that happens AFTER `start_transfer`
        # has committed its own atomic block — `RF1` (refused at step 2) and
        # `RF3` (whose first job survives). `RF4` is refused BY
        # `start_transfer` (so was the retired `RF5`), and `DR2`'s outer transaction
        # unwinds the row it had already written, so for those three **no
        # transfer row exists to name anybody** and declaring one would have
        # been a suite asserting a row into existence. Each of the three says
        # so by name below rather than inheriting it.
        "identity": Expect(
            {
                "account_customer_is_the_buyer": False,
                "seller_customer_row_survives": True,
                "seller_linked_to_this_account": True,
                "transfer_row_names_the_seller": False,
                "buyer_customer_no_changed": False,
                "seller_customer_no_changed": False,
                "second_customer_created": False,
            },
            "a refused sale leaves the SELLER as the customer — nothing was reassigned",
        ),
        "communication": Expect(
            {"queued_by_the_commit": 0, "queued_to_the_buyer": 0, "queued_to_the_seller": 0,
             "sent": 0, "a_transfer_message_kind_exists": True},
            "a refused sale tells nobody anything, which is correct",
            waits_on={"a_transfer_message_kind_exists": KEY_TRANSFER_MESSAGES},
        ),
        "transfer_record": Silent("nothing committed, so there is no completed record"),
        "lists_and_counting": Silent("a refusal lists nowhere"),
        "friction": Report(),
    }
    block.update(over)
    return block


SCENARIOS += [
    Scenario(
        id="RF1",
        group="REFUSAL",
        title="a buyer with a name and no identifier — refused, and the refusal names why",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(buyer={"display_name": "Nobody, A.", "kind": "person", "identity": {}}),
        expect=_refused(
            transfers.REFUSAL_BUYER_NOT_IDENTIFIED,
            why="BR-CUS-1023 — *\"Without identifier we cannot create Customer ID\"*",
            # ⚠ **STEP 2 REFUSES AND STEP 1 ALREADY COMMITTED**, because each
            # service call carries its own `atomic()` and the step-by-step road
            # wraps none of them. So a transfer row DOES exist here, naming the
            # seller — and it is the stranded `in_progress` row the composed
            # door's outer block exists to prevent (`DR2` is the contrast).
            identity=Expect(
                {"account_customer_is_the_buyer": False,
                 "seller_customer_row_survives": True,
                 "seller_linked_to_this_account": True,
                 "transfer_row_names_the_seller": True,
                 "buyer_customer_no_changed": False,
                 "seller_customer_no_changed": False,
                 "second_customer_created": False},
                "step 1 committed before step 2 refused, so its row is still there",
            ),
        ),
    ),
    Scenario(
        id="RF2",
        group="REFUSAL",
        title="selling to the person who already owns it — nothing to reassign",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        # The SAME person, presenting the SAME phone the account was opened
        # with. `transfers.py` has an explicit guard for this and a named
        # refusal constant, `buyer_is_already_this_accounts_customer`.
        steps=Steps(buyer={"display_name": SELLER_NAME, "kind": "person",
                           "identity": {"phone": SELLER_PHONE}}),
        # ⛔⛔ **THIS ROW IS RED AND THE GUARD IS THE REASON — `DEF-CUS-5972`.**
        # Measured
        # 2026-09-20: the sale COMMITS, `second_customer_created` is TRUE, and
        # no refusal is raised at all. `reassign_account` compares the customer
        # id `link_customer` RETURNS against the seller's — and `link_customer`
        # does not match on a phone, because a phone is not one of
        # `BR-CUS-1024`'s reuse identifiers. So it MINTS A SECOND CUSTOMER for
        # the same person, the ids differ, the guard cannot fire, the seller's
        # link is deleted and the account is handed to the new number.
        #
        # ⚠ **THAT IS A GUARD THAT EXISTS AND CANNOT FIRE** — hard-won law 7's
        # *structurally incapable of failing*, in production code rather than
        # in a check. The cost is not cosmetic: one person ends up holding two
        # customer numbers for one property, and the number their history hangs
        # off is the one that was just unlinked.
        #
        # ⚠ **AND IT IS NOT `SL3`.** `SL3` is a DIFFERENT person returning, and
        # a second number for them is `BR-CUS-1024` working exactly as signed.
        # Here it is the SAME person as the seller, and the second number is
        # what defeats a guard written to stop precisely this. Collapsing the
        # two would read the signed rule as the defect.
        expect=_refused(
            transfers.REFUSAL_BUYER_IS_THE_SELLER,
            why="rewriting the link to itself would write an audit row about a non-event",
            # ⚠ **THE BUYER IS THE SELLER, SO "NAMES THE BUYER" CANNOT BE FALSE
            # WHILE "NAMES THE SELLER" IS TRUE** — both compare against the SAME
            # name. `_refused`'s defaults declare buyer False / seller True,
            # which this row could never meet: it was red on exactly those two
            # keys from the day it became a refusal (`a23fb87f7`, 2026-09-20,
            # `DEF-CUS-5972` fixed) while the refusal itself passed. Corrected
            # 2026-10-02 (law 7, *incapable of passing*): the seller is still
            # named everywhere, and that one person is also the would-be buyer.
            assets_and_account=Expect(
                {**assets_seen(count=1, names_buyer=False),
                 "names_the_buyer": True, "names_the_seller": True},
                "nothing changed hands; the one name on file is both parties'",
            ),
            occupancy_at_unit=Expect(
                {**occupancy_seen(names_buyer=False),
                 "occupant_names_the_buyer": True, "occupant_names_the_seller": True},
                "the seller is still the occupant, and is also the would-be buyer",
            ),
            identity=Expect(
                {"account_customer_is_the_buyer": False,
                 "seller_customer_row_survives": True,
                 "seller_linked_to_this_account": True,
                 # Had the guard fired, the row would still name the seller.
                 # It did not, so it names the second customer minted for them.
                 "transfer_row_names_the_seller": True,
                 "buyer_customer_no_changed": False,
                 "seller_customer_no_changed": False,
                 "second_customer_created": False},
                "a refusal here would have left the seller as the account's only customer",
            ),
        ),
    ),
    Scenario(
        id="RF3",
        group="REFUSAL",
        title="ONE SALE AT A TIME — an account part-way through another sale",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        road="second_sale",
        # ⊕ **ASKED BEFORE THE WRITE SINCE 2026-09-23 (`DEF-CUS-6395`).** This
        # row expected `one_open_transfer_per_account`, the name the suite gave
        # the partial unique index's IntegrityError. `start_transfer` now asks
        # `sale_refusal` first and refuses BY NAME — the same answer step 1
        # shows before a clerk picks the account — and the index stays as the
        # backstop for two clerks racing.
        expect=_refused(
            transfers.REFUSAL_ALREADY_BEING_SOLD,
            why="the blueprint's *\"One sale at a time\"*, refused by name before any write",
            # ⚠ **THE FIRST SALE IS STILL OPEN AND MUST STAY OPEN.** A refusal
            # that rolled back the FIRST job would be worse than no refusal at
            # all: the clerk would lose work they had already done.
            lists_and_counting=Expect(
                {"on_the_transfers_list": True, "in_the_published_exclusion_set": True,
                 "on_the_move_outs_list": False, "on_the_move_ins_list": False,
                 "open_transfers_on_this_account": 1},
                "the first job survives the second job's refusal",
            ),
            identity=Expect(
                {"account_customer_is_the_buyer": False,
                 "seller_customer_row_survives": True,
                 "seller_linked_to_this_account": True,
                 # The surviving FIRST job still names the seller, which is the
                 # other half of "the first job survives": a row that survived
                 # and forgot whose it was would be worse than no row.
                 "transfer_row_names_the_seller": True,
                 "buyer_customer_no_changed": False,
                 "seller_customer_no_changed": False,
                 "second_customer_created": False},
                "the surviving first job still names who is selling",
            ),
        ),
    ),
    Scenario(
        id="RF4",
        group="REFUSAL",
        title="an account that has already closed — only an occupant may sell",
        estate=Estate(arrear=ZERO, deposit=ZERO, close_before_selling=True),
        steps=Steps(),
        expect=_refused(
            transfers.REFUSAL_NOT_AN_OCCUPANT,
            why="BR-MET-036 — a closed account has already left the unit",
            occupancy_at_unit=Expect(
                {"occupancy": "vacant", "account_no_changed": False,
                 "occupant_names_the_buyer": False, "occupant_names_the_seller": False,
                 "vacant": True},
                "the account closed before the sale was attempted, so the unit is vacant",
            ),
            # ⚠ **THE BEFORE-SNAPSHOT IS TAKEN AFTER THIS ROW'S OWN CLOSE**,
            # so every `_changed` key must read FALSE: the account was already
            # terminal when the sale was attempted and the refusal moved
            # nothing. Declaring the close here would be declaring the fixture's
            # work as the product's.
            unchanged=Expect(
                {**UNCHANGED, "closed_at": MOVED_OUT_ON},
                "the account was already closed; the refusal changed nothing at all",
            ),
            # ⚠ **A CLOSED ACCOUNT LEAVES ITS ASSETS NAMING NOBODY, AND THAT
            # IS RIGHT.** `asset_detail`'s billing chain reads
            # `active_account_for_unit`, which is `BR-MET-036`'s DERIVED
            # occupancy — once the account is terminal the unit is vacant and
            # the chain's `account` block is empty. So the asset names no
            # account and no customer, which is a true answer and not a gap.
            # The suite declared the OCCUPIED shape here and was wrong; the
            # meters themselves are still fitted, which is what `count` says.
            assets_and_account=Expect(
                {"count": 1,
                 "every_asset_names_the_selling_account": False,
                 "account_no_changed": False,
                 "assets_moved": 0,
                 "address_on_every_asset": SERVICE_ADDRESS,
                 "names_the_buyer": False,
                 "names_the_seller": False,
                 "vacuously_true_because_there_are_no_assets": False},
                "the unit is vacant, so the billing chain names no account at all",
            ),
        ),
    ),
    # ⊕ **THIS ROW WAS `RF5` AND READ *"an account with nobody on file —
    # refused"* UNTIL 2026-09-23 (`DEF-CUS-6387`).** PO, on A-11512: the sale
    # may go ahead, and the seller is RECORDED BY NAME — the account's contact —
    # because there is no customer to link. It keeps its place in the table
    # (twenty-five rows) and moves to SALE, where it now belongs.
    Scenario(
        id="SL5",
        group="SALE",
        title="an account with nobody on file — sold, and the seller is recorded by name",
        estate=Estate(arrear=ZERO, deposit=ZERO, no_customer_on_file=True),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="0.00",
            deposit="0.00",
            # ⚠ **EVERY SELLER KEY IS FALSE AND THAT IS THE ESTATE, NOT A
            # FINDING.** There is no seller CUSTOMER to survive, to stay linked,
            # to keep a number or to be named on the transfer's `customer_id` —
            # the seller is `transfers.seller_name`, a name, which is all the
            # account ever held. The buyer half is an ordinary sale's.
            identity=Expect(
                {"account_customer_is_the_buyer": True,
                 "seller_customer_row_survives": False,
                 "seller_linked_to_this_account": False,
                 "transfer_row_names_the_seller": False,
                 "buyer_customer_no_changed": False,
                 "seller_customer_no_changed": False,
                 "second_customer_created": True,
                 "the_account_name_is_the_buyers": True,
                 "the_account_name_did_not_move": False,
                 "refusal_names_a_fix": False},
                "BR-CUS-1081 T1 — nobody on file is no reason to refuse a sale",
            ),
        ),
    ),
]

# ───────────────── DOOR · the wizard's ONE POST, and its rollback ──────────
# ⚠ **`transfer_commit`'s OWN CLAIM ABOUT ITSELF, ASSERTED RATHER THAN READ.**
# Its docstring: *"THE ROLLBACK IS THE FEATURE, NOT THE TIDINESS … Without the
# outer block, a refusal at stage 5 would strand an `in_progress` row that
# blocks that account from ever being sold again and that nobody can find to
# cancel. Here, zero rows survive and the clerk simply goes again."*
#
# ⚠ **AND IT IS PROVED ON POSTGRESQL, WHICH IS CLAUDE.md LAW 14 AND NOT A
# PREFERENCE.** A failed statement poisons the whole PostgreSQL transaction and
# SQLite has no aborted-transaction state, so a rollback claim that passes the
# default suite says nothing at all about the product. `DR2` is the row that
# would go green on SQLite whatever the door did.
SCENARIOS += [
    Scenario(
        id="DR1",
        group="DOOR",
        title="the wizard's one POST, end to end — five staged writes, one transaction",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        road="door",
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(arrear="318.40", deposit="150.00"),
    ),
    Scenario(
        id="DR2",
        group="DOOR",
        title="the one POST refused at stage 5 — ZERO rows survive, proved on PostgreSQL",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        # The buyer passes step 2's own validation and is refused by
        # `link_customer` at stage 5 — which is the only way to reach the
        # stranded-row case the outer block exists for.
        steps=Steps(buyer={"display_name": "Nobody, A.", "kind": "person", "identity": {}}),
        road="door",
        expect=_refused(
            transfers.REFUSAL_BUYER_NOT_IDENTIFIED,
            why="the composed door refuses and unwinds every one of the five writes",
            lists_and_counting=Expect(
                {"on_the_transfers_list": False, "in_the_published_exclusion_set": False,
                 "on_the_move_outs_list": False, "on_the_move_ins_list": False,
                 "transfer_rows_left_behind": 0},
                "ZERO rows survive — a stranded `in_progress` row blocks the account for ever",
            ),
        ),
    ),
]

# ───────────────── PROCESS · save & exit → the list → resume → finish ──────
SCENARIOS += [
    Scenario(
        id="PC1",
        group="PROCESS",
        title="Save & exit mid-wizard → find it again → Resume → finish the sale",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        road="park_resume",
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            lists_and_counting=Expect(
                {**lists_seen(), "parked_draft_found": True, "parked_draft_flow": "transfer",
                 "parked_draft_resumed_at_the_step_it_was_left": True},
                "CR-035 — a parked draft lands on the tab for its OWN kind of work",
            ),
        ),
    ),
]

# ───────────────── COUNTING · what a sale subtracts from other screens ─────
SCENARIOS += [
    Scenario(
        id="CT1",
        group="COUNTING",
        title="`DEF-CUS-5913` — sold in May, genuinely moves out in September",
        estate=Estate(arrear=ZERO, deposit=ZERO),
        steps=Steps(),
        road="sell_then_move_out",
        blocked_on=(KEY_COUNTING_CONTRACT, KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES,
                    KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="0.00",
            deposit="0.00",
            names_buyer=True,
            # ⚠ **THIS ROW IS THE DEFECT, AND IT IS A TRANSFER'S COUNTING
            # CONTRACT REACHING INTO ANOTHER SCREEN.**
            # `transfer_half_account_ids()` names every non-cancelled transfer's
            # `from_account_id` FOREVER, and `move_outs_queryset` subtracts it.
            # The exclusion was right while a committed transfer CLOSED its
            # outgoing half; `BR-CUS-1030` removed the closure and nothing
            # re-read the consumers. **A real move-out that no screen shows.**
            lists_and_counting=Expect(
                {"on_the_transfers_list": True, "in_the_published_exclusion_set": True,
                 "on_the_move_outs_list": True, "on_the_move_ins_list": False,
                 "the_move_out_really_happened": True},
                "an account sold in May and CLOSED in September is a real move-out",
                waits_on={"on_the_move_outs_list": KEY_COUNTING_CONTRACT},
            ),
            # The sale happened months before the move-out, and the move-out is
            # what closed the account — so this row's `unchanged` is about the
            # SALE and the closure is stated rather than hidden.
            # ⚠ **THE CLOSE IS THIS ROW'S SECOND ACT AND IS DECLARED, NOT
            # HIDDEN.** The SALE changed nothing; the MOVE-OUT four months
            # later closed the account, ended its agreement and derived the
            # unit back to vacant — which is the whole point of the row, since
            # a move-out that did not happen could not be missing from a list.
            unchanged=Expect(
                {**UNCHANGED, "closed_at": MOVED_OUT_ON, "status_class_changed": True,
                 "agreements_ended": 1, "accounts_closed": 1},
                "the SALE changed nothing; the later MOVE-OUT closed the account",
            ),
            occupancy_at_unit=Expect(
                {"occupancy": "vacant", "account_no_changed": False,
                 "occupant_names_the_buyer": False, "occupant_names_the_seller": False,
                 "vacant": True},
                "BR-MET-036 derives the unit back to vacant — the move-out did that, not the sale",
            ),
            # ⚠ **A CLOSED ACCOUNT LEAVES ITS ASSETS NAMING NOBODY, AND THAT
            # IS RIGHT.** `asset_detail`'s billing chain reads
            # `active_account_for_unit`, which is `BR-MET-036`'s DERIVED
            # occupancy — once the account is terminal the unit is vacant and
            # the chain's `account` block is empty. So the asset names no
            # account and no customer, which is a true answer and not a gap.
            # The suite declared the OCCUPIED shape here and was wrong; the
            # meters themselves are still fitted, which is what `count` says.
            assets_and_account=Expect(
                {"count": 1,
                 "every_asset_names_the_selling_account": False,
                 "account_no_changed": False,
                 "assets_moved": 0,
                 "address_on_every_asset": SERVICE_ADDRESS,
                 "names_the_buyer": False,
                 "names_the_seller": False,
                 "vacuously_true_because_there_are_no_assets": False},
                "the unit is vacant, so the billing chain names no account at all",
            ),
            money=Silent("the money is MN1–MN4's subject; this row is about a counting contract"),
        ),
    ),
    Scenario(
        id="CT2",
        group="COUNTING",
        title="the sale is on the Transfers tab, in the set the other tabs subtract",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            lists_and_counting=Expect(
                {**lists_seen(),
                 "the_contract_is_called_not_re_derived": True,
                 # ⚠ **AND THIS ONE IS A FINDING RATHER THAN A FORMALITY.**
                 # §5.7.3's contract is about TWO HALVES and a sale has ONE
                 # account, so the set the Transfers list publishes now names
                 # the SAME id once instead of two different ones.
                 "halves_published_for_this_sale": 1},
                "B18 §5.7.3's counting contract, called rather than restated",
            ),
        ),
    ),
]

# ───────────────── UNCHANGED · hard rule 4, and the seller's other account ──
SCENARIOS += [
    Scenario(
        id="UN1",
        group="UNCHANGED",
        title="the seller's issued documents are untouched — hard rule 4",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            unchanged=Expect(
                {**UNCHANGED,
                 "invoices_touched": 0,
                 "payments_touched": 0,
                 "journal_entries_touched": 0,
                 "invoice_rows_updated": 0,
                 "invoice_rows_deleted": 0},
                "*\"A bill posted to this seller still says their name a year from now\"*",
            ),
        ),
    ),
    Scenario(
        id="UN2",
        group="UNCHANGED",
        title="the seller keeps every other account they hold",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, sellers_other_account=True),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            identity=Expect(
                {**identity_seen(second_customer=True),
                 # The blueprint's step 1: `Affected by this sale · No — that
                 # one is theirs still`.
                 "sellers_other_account_still_theirs": True,
                 "sellers_other_account_customer_changed": False},
                "a sale reassigns ONE account and the seller keeps the rest",
                waits_on=dict(IDENTITY_WAITS),
            ),
        ),
    ),
]

# ───────────────── IDENTITY · the ruling of 2026-09-20 ─────────────────────
SCENARIOS += [
    Scenario(
        id="ID1",
        group="IDENTITY",
        title="the seller remains discoverable after the sale — *\"we cannot override customer id\"*",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT),
        steps=Steps(),
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            # ⚠ **THIS IS THE ROW THE 2026-09-20 RULING IS ABOUT.** PO,
            # verbatim: *"we cannot override customer id - seller and buyer
            # cstmer id are unique those does not change"*. Today
            # `reassign_account` DELETES the seller's `customer_accounts` row
            # and overwrites `transfers.customer_id`, so the drawn record's own
            # title (`Tan, Wei → Ferraro, L.`) and its `Sold by` row cannot be
            # rendered from anything but `audit_log`, **which is pruned.**
            identity=Expect(
                {**identity_seen(second_customer=True),
                 "seller_discoverable_without_the_audit_log": True,
                 "ownership_history_is_a_query_not_a_log_scrape": True},
                "a customer id is a permanent identity, not a slot on an account",
                waits_on={
                    **IDENTITY_WAITS,
                    "seller_discoverable_without_the_audit_log": KEY_SELLER_DURABLE,
                    "ownership_history_is_a_query_not_a_log_scrape": KEY_SELLER_DURABLE,
                },
            ),
        ),
    ),
]

# ───────────────── REQUEST · the PO's *"create request"*, the second door ───
SCENARIOS += [
    Scenario(
        id="RQ1",
        group="REQUEST",
        title="a sale raised from an approved service request — the second door in",
        estate=Estate(arrear=ARREAR, deposit=DEPOSIT, from_request=True),
        steps=Steps(),
        road="from_request",
        blocked_on=(KEY_SELLER_DURABLE, KEY_TRANSFER_MESSAGES, KEY_TRANSFER_RECORD),
        expect=_ordinary(
            arrear="318.40",
            deposit="150.00",
            # ⚠ **THERE ARE TWO DOORS INTO A SALE AND ONLY ONE OF THEM IS THE
            # WIZARD.** `request_jobs._raise_transfer` starts the job from an
            # APPROVED service request whose outcome is `transfer`, writes
            # `transfers.request_id`, and lands it `scheduled` at step 1 of 5 —
            # raised, not done. `BR-CUS-080`'s child half, which this column
            # has carried since `CR-094-BRC01`.
            transfer_record=Expect(
                {**record_seen(), "raised_from_a_request": True,
                 "the_request_names_the_job": True},
                "BR-CUS-080 — the SR alone answers *what happened to this application*",
                waits_on=dict(RECORD_WAITS),
            ),
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
            "This suite drives the SERVICES the five steps post to, and the composed "
            "door they post THROUGH, and reads PostgreSQL back. It never opens a "
            "browser, so it cannot see a field that renders as a dash, a step that "
            "cannot be reached, a `Save & exit` that loses what was typed, or the one "
            "the PO found by clicking: `DEF-CUS-5934`, *\"step 4 when last tick is press "
            "- uI breaks\"*, which 39 green front-end cases and a clean `tsc` all "
            "passed over because they render the step statically and never press the "
            "control. **Hard-won law 6 — diff the running app against the drawing — is "
            "the other half and no gate in this repository performs it.** ⚠ **AND THIS "
            "FLOW HAS NO WALKTHROUGH SCRIPT**: `10-scripts/` holds one for the move-in "
            "job, the move-out wizard, the account bar, the portal and nine CRs, and "
            "none for a transfer. That absence is this suite's largest single blind "
            "spot and it is named rather than counted around."
        ),
    },
    {
        "id": "U2",
        "what": "That any message ever reaches a human",
        "why": (
            "Measured 2026-09-19: **426 messages are queued in this product and not one "
            "has ever been sent** — `sent_at` is null on every row — and both channels "
            "report *not connected*. The transfer wizard's review step lists each "
            "message the commit queues and marks every one *Queued on confirm* "
            "(the PO's transfer list, item 15, 2026-09-23) — it never says sent. "
            "So `communication` asserts what a commit QUEUES and counts what was SENT, "
            "and the count is zero on every row by construction. ⚠ **A queue is never "
            "reported here as a delivery**, which is the move-in and move-out suites' "
            "posture and the reason this entry exists rather than a green tick."
        ),
    },
    {
        "id": "U3",
        "what": "The premises OWNER record following the sale",
        "why": (
            "⊕ **T2, PO 2026-09-23 (`DEF-CUS-6394`) — this entry read *\"It does not, "
            "and that is drawn rather than broken\"*.** It now does, when the account "
            "sold is the premises' MASTER account: `reassign_account` asks metering's own "
            "door (`seams.transfer_premises_owner`), which carries the outgoing owner's "
            "category onto the buyer's owner record, so customers still writes no "
            "metering table (B1). On a regular account the owner is somebody else — a "
            "landlord — and nothing moves and nothing is stated. A master sale that "
            "cannot move it (no typed owner to take a category from) says "
            "`premises_owner_not_moved` in `unavailable`, with the reason. **What this "
            "suite still cannot test is the category judgment itself**, which is the "
            "decision log's row of 2026-09-23."
        ),
    },
    {
        "id": "U4",
        "what": "Whether the BUYER is ever shown what they took on",
        "why": (
            "`OQ-1253` is OPEN — *must the buyer be shown the balance they are taking "
            "on* — and the blueprint's step 4 says so in its own words: `The buyer · Not "
            "decided`. The figure rides the record so it EXISTS; no letter claims to "
            "have told them. ⚠ **Asserting either answer here would be resolving an "
            "open question by choosing a value**, which the prime directive forbids, so "
            "the suite asserts that the figure is RECORDED and says nothing about who "
            "saw it."
        ),
    },
    {
        "id": "U6",
        "what": "\u26d4 `DEF-CUS-5970` — DEF-CUS-5940's THIRD CALL SITE, STILL LIVE",
        "why": (
            "`apps/customers/discounts.py:858` makes the identical one-argument call — "
            "`read(account.id)` against a seam whose published signature is "
            "`(account_id, as_of)` — and it is reached by "
            "`GET /customers/{id}/deposit-position` for any customer holding a CLOSED "
            "account with a deposit on it, which is precisely the customer that screen "
            "exists to serve (B18 §5.5.5, *\"refundable deposit on any closed "
            "account\"*). ⚠ **`DEF-CUS-5940`'s own row names TWO call sites and there "
            "are THREE** — *\"move_out_settlement._deposit_interest was moved in the "
            "same commit and this call site was not\"* — so the enumeration-by-memory "
            "that produced the defect was repeated inside its own fix. **This suite "
            "does not walk that endpoint**, because a sale never reaches it: it is "
            "NAMED here rather than asserted, and filed, so nobody reads a green "
            "transfer suite as evidence that the seam's consumers are all correct."
        ),
    },
    {
        "id": "U5",
        "what": "A sale on an account that already carries an ISSUED invoice",
        "why": (
            "`UN1` asserts that the sale touches no invoice row, and on this fixture "
            "there are none to touch: issuing one needs a bill run, which is a whole "
            "billing wave rather than a fixture, and `prepare_final_bill`'s preview "
            "deliberately ISSUES NOTHING. **So the hard-rule-4 assertion is proved "
            "negatively — no invoice row was created, updated or deleted — and not "
            "positively, against a real bill in the seller's name.** The positive case "
            "belongs with the billing suite and is named here so nobody reads `UN1` as "
            "more than it is."
        ),
    },
)


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD ONE SCENARIO NEEDS — built through the owning services
# ═══════════════════════════════════════════════════════════════════════════
#: The per-service base charge every plan in this suite carries. A real figure
#: on a real plan, so the unit has something priceable and an account can go
#: ACTIVE on it (`BR-MET-040`).
BASE_CHARGE = D("20.00")


def _published_plan(tenant: Any, services: list[str], name: str) -> Any:
    """A published plan with a tariff and a BASE CHARGE per service.

    `test_w7_transfers`'s and the move-out suite's helper, reused rather than
    respelt: a second spelling of *what a billable unit needs* is how two
    suites start disagreeing about it.
    """
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-")[:40], "status": "published"},
    )
    for code in services:
        service = tenancy_models.Service.objects.get(code=code)
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant=tenant, name=f"{name} — {code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
        # ⚠ **THE BASE CHARGE IS ON `PlanService`, NOT ON THE RATE SCHEDULE.**
        # The move-out suite learned this and wrote it down, and the note is
        # reused rather than the lesson relearned: `rating.selectors.plan_detail`
        # projects the figure from `PlanService`, so a base charge written on
        # the schedule instead is a plan whose own page shows none at all —
        # and `PlanRateSchedule` has no such column, so it is a `FieldError`
        # rather than a silent wrong answer, which is the kinder of the two.
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant, rate_plan=plan, service=service,
            defaults={"base_charge": BASE_CHARGE, "currency": "USD"},
        )
    return plan


def _occupant(
    actor: Any, unit_id: Any, *, name: str, phone: str, opened_at: str = OPENED
) -> dict[str, Any]:
    """One occupying account, through the real S18 door.

    ⚠ **THE CUSTOMER IS IDENTIFIED AT THE DOOR** (`BR-CUS-1024`, PO
    2026-09-01) and the block is no longer optional: `create_account` refuses
    `identity_kind_required` without one. A fixture that passed only a name
    would fail in SETUP on every row, which is how `RF5` (now `SL5`) found that the
    link-less account it needs can no longer be opened at all — see
    `build_world`.
    """
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit_id),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": phone},
            },
        },
    )


@dataclass
class World:
    premises: dict[str, Any]
    unit: dict[str, Any]
    plan: Any
    account: dict[str, Any]
    account_id: str
    asset_ids: list[str]
    neighbour: dict[str, Any] | None
    sellers_other: dict[str, Any] | None
    request: Any | None
    before: dict[str, Any]
    notes: list[str] = field(default_factory=list)


def build_world(admin: Any, tenant: Any, scenario: Scenario) -> World:
    """Everything the scenario needs standing, through the owning services."""
    estate = scenario.estate
    seed_config()
    services = sorted({svc for _no, svc, _uom in estate.meters}) or ["electric"]
    plan = _published_plan(tenant, services, f"Sale {scenario.id}")

    premises = make_premises(
        admin,
        services_available=sorted(set(services) | {"electric", "water"}),
        premises_type="single_family",
        address_line=ADDRESS_LINE,
        city=ADDRESS_CITY,
        state=ADDRESS_STATE,
        postal_code=ADDRESS_POSTAL,
    )
    unit = make_unit(
        admin, premises["id"], label=estate.unit_label, unit_type=estate.unit_type,
        services=services,
    )
    # ⚠ **`effective_from` IS STATED, AND WITHOUT IT NOTHING HERE CAN BE
    # BILLED.** `_apply_unit_plan` dates an assignment from the tenant's TODAY
    # when the caller states none, so a plan attached now is not in force across
    # a period that started in 2024 — `BR-RAT-007` prices on the terms in force
    # AT THE SERVICE DATE. The move-out suite met the same wall and recorded
    # it; this is that lesson used rather than learned twice.
    metering_services.assign_unit_plan(
        admin, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2024-01-01"}
    )
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)

    asset_ids: list[str] = []
    for asset_no, service, uom in estate.meters:
        asset = a_meter(admin, asset_no, unit_id=unit["id"], service=service, uom=uom)
        asset_ids.append(str(asset["id"] if isinstance(asset, dict) else asset))

    notes: list[str] = []

    neighbour: dict[str, Any] | None = None
    if estate.neighbour:
        # ⚠ **A SECOND UNIT AT THE SAME PREMISES**, so hard rule 8 is testable
        # as a consequence: two units, ONE address, and a sale that touched an
        # address at all would be visible on the one that was not sold.
        neighbour_unit = make_unit(
            admin, premises["id"], label="Unit 2", unit_type=estate.unit_type,
            services=services,
        )
        metering_services.assign_unit_plan(
            admin, neighbour_unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2024-01-01"},
        )
        for code in services:
            metering_services.ensure_service_point(neighbour_unit["id"], code)
        neighbour = _occupant(
            admin, neighbour_unit["id"], name="Ncube, T.", phone="+1-555-0222"
        )
        neighbour["unit_id"] = str(neighbour_unit["id"])

    # ── the account that changes hands ──────────────────────────────────────
    # ⚠ **AN ACCOUNT WITH NOBODY ON FILE CANNOT BE CREATED ANY MORE, AND THAT
    # IS A FINDING RATHER THAN A FIXTURE PROBLEM.** `BR-CUS-1024` (PO
    # 2026-09-01) made the identity block required at the account door, so
    # `create_account` refuses `identity_kind_required` before a link-less
    # account can exist. **A link-less account is therefore reachable only as a
    # LEGACY row** — and since 2026-09-23 (`DEF-CUS-6387`) it is no longer
    # refused a sale: the seller is recorded by name (`transfers.seller_name`).
    #
    # So `SL5` (once `RF5`) builds that legacy state the one way it is still reachable:
    # open the account properly, then REMOVE the link. That is
    # `make_unmatched_premises`' posture exactly — *"this state can no longer be
    # reached through the front door, which is the rule working, not a gap, and
    # it is still a REAL state on every live tenant"* — and it is written
    # through the ORM for the same reason.
    account = _occupant(admin, unit["id"], name=SELLER_NAME, phone=SELLER_PHONE)
    account_id = str(account["id"])
    if estate.no_customer_on_file:
        customers_models.CustomerAccount.objects.filter(account_id=account_id).delete()
        notes.append(
            "this account's `customer_accounts` link was removed after opening: "
            "BR-CUS-1024 closed the front door on a link-less account, so the "
            "state is reachable only by legacy data — and it now sells, with the "
            "seller recorded by name"
        )
    row = customers_models.Account.objects.get(pk=account_id)
    if estate.arrear or estate.deposit:
        # ⚠ **THROUGH THE ORM AND NOT THROUGH A DOOR, AND THAT IS THE POINT
        # RATHER THAN A SHORTCUT.** `services.REFUSED_FIELDS` refuses both on
        # every client-facing path — `BR-CUS-023` (the deposit is a lookup) and
        # `BR-CUS-015` (the balance is the ledger's cache). A fixture that could
        # set them through a door would mean the product had one.
        customers_models.Account.objects.filter(pk=row.pk).update(
            balance=estate.arrear,
            deposit_on_file=estate.deposit,
            # ⚠ **THE RECEIPT DATE IS PART OF THE DEPOSIT AND NOT A DECORATION.**
            # `BR-CUS-057`'s accrual starts from it, and a register row without
            # one makes the engine answer `None` — a stated absence, never a
            # zero. The move-in door stamps it when it takes the money; there
            # is no door that puts a deposit on an account that already exists,
            # so the fixture leaves it exactly as a move-in would have.
            deposit_received_on=(
                date.fromisoformat(estate.deposit_received_on)
                if estate.deposit_received_on
                else None
            ),
        )

    sellers_other: dict[str, Any] | None = None
    if estate.sellers_other_account:
        other_premises = make_premises(
            admin, services_available=services, premises_type="single_family",
            address_line="88 Quarry Lane", city=ADDRESS_CITY, state=ADDRESS_STATE,
            postal_code=ADDRESS_POSTAL,
        )
        other_unit = make_unit(admin, other_premises["id"], label="Unit A", services=services)
        metering_services.assign_unit_plan(
            admin, other_unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2024-01-01"},
        )
        for code in services:
            metering_services.ensure_service_point(other_unit["id"], code)
        # ⚠ **THE SAME CUSTOMER, A SECOND ACCOUNT** — `BR-CUS-054`'s N:M link
        # written by the one function allowed to write it, so the blueprint's
        # *"The seller keeps every other account they hold"* is reachable.
        sellers_other = _occupant(
            admin, other_unit["id"], name=SELLER_NAME, phone=SELLER_PHONE
        )

    if estate.buyer_already_on_file:
        # The buyer exists BEFORE the sale, so `link_customer` MATCHES rather
        # than creates — through the one door that writes a customer, never by
        # inserting a row this product would not insert itself.
        buyer_block = dict(scenario.steps.buyer or BUYER_PERSON)
        other_premises = make_premises(
            admin, services_available=services, premises_type="single_family",
            address_line="12 Harbour View", city=ADDRESS_CITY, state=ADDRESS_STATE,
            postal_code=ADDRESS_POSTAL,
        )
        other_unit = make_unit(admin, other_premises["id"], label="Unit A", services=services)
        metering_services.assign_unit_plan(
            admin, other_unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2024-01-01"},
        )
        for code in services:
            metering_services.ensure_service_point(other_unit["id"], code)
        customers_services.create_account(
            admin,
            {
                "unit_id": str(other_unit["id"]),
                "account_type": "commercial" if buyer_block["kind"] == "company"
                else "residential",
                "status": "active",
                "opened_at": OPENED,
                "contact": {"full_name": buyer_block["display_name"]},
                "customer": dict(buyer_block),
            },
        )

    request = None
    if estate.from_request:
        request = service_request_service.create_request(
            admin,
            {
                "channel": "phone",
                "applicant_kind": "person",
                "applicant_name": BUYER_NAME,
                "applicant_phone": BUYER_PHONE,
                "address_as_given": SERVICE_ADDRESS,
                "property_type": "rental_tenant_applying",
                "what_they_said": "I have bought 1408 Elm Street",
            },
        )

    if estate.close_before_selling:
        customers_services.move_out(admin, account_id, {"moved_out_on": MOVED_OUT_ON})

    before = _snapshot(account_id, unit["id"], asset_ids, neighbour, sellers_other)
    return World(
        premises=premises, unit=unit, plan=plan, account=account, account_id=account_id,
        asset_ids=asset_ids, neighbour=neighbour, sellers_other=sellers_other,
        request=request, before=before, notes=notes,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE READBACK — PostgreSQL, never a service's own return value
# ═══════════════════════════════════════════════════════════════════════════
def _display(amount: Any) -> str | None:
    """A money figure as a clerk reads it: **two decimals** (hard rule 2 —
    stored to four, displayed to two). Comparing the stored half would let
    `318.4000` and `318.40` disagree about nothing."""
    if amount is None:
        return None
    return str(Decimal(amount).quantize(Decimal("0.01")))


def _address_of_premises(premises_id: Any) -> str | None:
    """The ONE place an address lives (CLAUDE.md hard rule 8), composed by
    WALKING to it. Nothing else in this file knows an address."""
    row = metering_models.Premises.objects.filter(pk=premises_id).first()
    if row is None:
        return None
    return f"{row.address_line}, {row.city}, {row.state} {row.postal_code}"


#: The column names a `units` row must NOT carry. ⚠ **Hard rule 8 — *"a unit
#: refines a premises by LABEL, not by address"*** — and `BR-MET-1162` narrows
#: exactly one clause of it: a unit MAY carry its own `lat`/`lng`, which is why
#: those two are deliberately absent from this list and `city` is on it by name.
FORBIDDEN_UNIT_COLUMNS: tuple[str, ...] = (
    "address_line", "address", "city", "state", "postal_code", "postcode", "zip",
)


def _customer_no_of(customer_id: Any) -> str | None:
    row = customers_models.Customer.objects.filter(pk=customer_id).first()
    return row.customer_no if row is not None else None


def _customer_display_name_of(customer_id: Any) -> str | None:
    """The name on a customer's OWN record — never the account's contact."""
    row = customers_models.Customer.objects.filter(pk=customer_id).first()
    return row.display_name if row is not None else None


def _two_distinct_numbers(seller_id: Any, buyer_id: Any) -> bool:
    """**Two people, two Customer #s, both still on file.**

    PO 2026-09-20: *"customer id we cannnot trsnfer to new buyer"* and *"seller
    and buyer cstmer id are unique those does not change"*.

    ⚠ **IT ASKS FOR THE NUMBERS AND NOT FOR THE IDS.** `customer_no` is what a
    person quotes down a phone (B14 rule 31) and it is what a merge would
    destroy: two rows can have different uuids and one number only if something
    has gone very wrong, and a merge that re-pointed the link would leave one
    number serving two people.
    """
    if not seller_id or not buyer_id or str(seller_id) == str(buyer_id):
        return False
    seller_no = _customer_no_of(seller_id)
    buyer_no = _customer_no_of(buyer_id)
    return bool(seller_no) and bool(buyer_no) and seller_no != buyer_no


def _snapshot(
    account_id: str,
    unit_id: Any,
    asset_ids: list[str],
    neighbour: dict[str, Any] | None,
    sellers_other: dict[str, Any] | None,
) -> dict[str, Any]:
    """Everything that must be able to be compared BEFORE and AFTER.

    ⚠ **TAKEN BEFORE ANYTHING CHANGES, AND IT IS THE ONLY MOMENT IT CAN BE.**
    A minute later the account's balance is just the account's balance; what
    makes `balance_changed: False` an assertion rather than a tautology is that
    one of these two reads happened first.
    """
    account = customers_models.Account.objects.select_related("status").get(pk=account_id)
    customer = customers_selectors.customer_for_account(account_id)
    links = list(
        customers_models.CustomerAccount.objects.filter(
            tenant_id=account.tenant_id, account_id=account_id
        ).values_list("customer_id", flat=True)
    )
    return {
        "account_no": account.account_no,
        "unit_id": str(account.unit_id) if account.unit_id else None,
        "status_class": account.status.behavior_class,
        "closed_at": account.closed_at.isoformat() if account.closed_at else None,
        "balance": _display(account.balance),
        "deposit": _display(account.deposit_on_file),
        "agreements_open": customers_models.ServiceAgreement.objects.filter(
            account_id=account_id, ended_on__isnull=True
        ).count(),
        "plan_on_unit": str(
            getattr(metering_models.Unit.objects.get(pk=unit_id), "rate_plan_id", None) or ""
        ),
        "meters": len(asset_ids),
        "accounts_in_tenant": customers_models.Account.objects.count(),
        "journal_lines": ledger_models.JournalLine.objects.count(),
        "journal_lines_on_account": ledger_models.JournalLine.objects.filter(
            account_id=account_id
        ).count(),
        "payments": payment_models.Payment.objects.count(),
        "payments_on_account": payment_models.Payment.objects.filter(
            account_id=account_id
        ).count(),
        "invoices": _invoice_count(),
        "messages": notification_models.OutboundMessage.objects.count(),
        "customer_ids": sorted(str(one) for one in links),
        "customer_no": (customer or {}).get("customer_no"),
        "customer_id": (customer or {}).get("id"),
        #: ⊕ **2026-09-20 — THE PO NAMED THIS SURFACE AND NOTHING WAS READING
        #: IT.** Verbatim: *"account number you can assign to new buyer, but in
        #: that case are you checking account - name change to new buyer"*.
        #: `account_row` is the Accounts list, and its `name` cell is the one a
        #: clerk reads most often — a THIRD reader of `primary_contact_name`
        #: beside the unit's Occupant column and the asset's billing chain.
        "account_name": customers_selectors.account_row(account).get("name"),
        #: ⊕ **AND THE PLAN, likewise named and likewise unread:** *"after
        #: transfer is completed units, assets, plans are get atatched to
        #: account of buyer"*. Under `BR-CUS-1030` the account does not move,
        #: so the honest assertion is that the plan the ACCOUNT stands on is
        #: the SAME plan afterwards — it is the buyer's now because the
        #: ACCOUNT is. `unit_plan` is `accounts.unit_id` → `units.rate_plan_id`
        #: → rating's `plan_ref`, which is a walk along foreign keys and reads
        #: no name at all. **That is why this dimension never broke while its
        #: two neighbours broke 36 times: they resolve a NAME and it does
        #: not.**
        "account_unit_plan": str(
            (customers_selectors.account_detail_dict(account) or {}).get("unit_plan") or ""
        ),
        #: The SELLER's own customer record, so a fix that overwrote it in
        #: place — the cheapest way to make every name assertion go green at
        #: once, and the one that would merge two people into one — is caught
        #: rather than rewarded.
        "customer_display_name": (customer or {}).get("display_name"),
        "customers_in_tenant": customers_models.Customer.objects.count(),
        "neighbour_customer": (
            customers_selectors.customer_for_account(neighbour["id"]) or {}
        ).get("id")
        if neighbour
        else None,
        "sellers_other_customer": (
            customers_selectors.customer_for_account(sellers_other["id"]) or {}
        ).get("id")
        if sellers_other
        else None,
    }


def _invoice_count() -> int:
    """Invoices in this tenant. ⚠ Counted through billing's OWN model rather
    than through a raw table name, so a rename cannot make this check silently
    count zero (hard-won law 7's *reporting zero over a scope it excludes*)."""
    from apps.billing import models as billing_models

    return billing_models.Invoice.objects.count()


def _attempt(seen: dict[str, Any], label: str, call: Callable[[], Any], fallback: Any) -> Any:
    """Run one READ and record a crash instead of dying of it.

    ⚠ **A SUITE THAT DIES OF THE FIRST CRASH REPORTS ONE FINDING AND HIDES THE
    OTHER TWELVE**, which is the opposite of what an end-to-end walk is for. So
    each observation is attempted on its own and a raise is RECORDED — with its
    type, its message and the line that raised — into `seen["crashes"]`, where
    the report prints it ONCE beside every scenario that reached it.

    ⚠ **IT IS NOT A BLANKET `except`, AND THE DIFFERENCE MATTERS** (hard-won law
    7): nothing is swallowed. The dimension that depended on this read gets its
    `fallback`, which fails its own check by name, AND the crash itself is
    printed at the top of the report. A reader sees both the symptom and the
    cause rather than one of them.
    """
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 — RECORDED, never swallowed
        import traceback

        frames = traceback.extract_tb(exc.__traceback__)
        where = f"{frames[-1].filename.split('/')[-1]}:{frames[-1].lineno}" if frames else "?"
        seen.setdefault("crashes", []).append(
            f"{label}: {type(exc).__name__}: {exc} (raised at {where})"
        )
        return fallback


def observe(scenario: Scenario, world: World, outcome: dict[str, Any]) -> dict[str, Any]:
    """Everything the checkers judge, read out of the tables."""
    account_id = world.account_id
    before = world.before
    seen: dict[str, Any] = dict(outcome)
    after = _snapshot(
        account_id, world.unit["id"], world.asset_ids, world.neighbour, world.sellers_other
    )
    seen["after"] = after

    # ── the property, the unit and the address ──────────────────────────────
    unit_row = metering_models.Unit.objects.filter(pk=world.unit["id"]).first()
    unit_columns = {field.name for field in metering_models.Unit._meta.get_fields()}
    walked = _address_of_premises(world.premises["id"])
    served = None
    if unit_row is not None:
        served_row = _attempt(
            seen, "the unit's own detail read",
            lambda: metering_selectors.unit_detail_dict(unit_row), {},
        )
        # ⚠ **THE PRODUCT'S OWN ANSWER, COMPARED WITH THE WALK.** `premise_address`
        # is what every screen shows for this unit; `walked` is what `premises`
        # holds. They must be the same STRING or somebody has a copy.
        served = served_row.get("premise_address")
    seen["property_and_address"] = {
        "premises_changed": str(unit_row.premises_id) != str(world.premises["id"])
        if unit_row
        else True,
        "unit_changed": (after["unit_id"] or "") != (before["unit_id"] or ""),
        "unit_label": unit_row.label if unit_row else None,
        "service_address": walked,
        "address_walked": bool(served) and walked is not None and walked.startswith(str(served)),
        "unit_declares_an_address": bool(unit_columns & set(FORBIDDEN_UNIT_COLUMNS)),
        "units_at_premises": metering_models.Unit.objects.filter(
            premises_id=world.premises["id"], deleted_at__isnull=True
        ).count(),
        "meters_on_the_unit": len(world.asset_ids),
        "neighbour_account_changed": False if world.neighbour is None else (
            after["neighbour_customer"] != before["neighbour_customer"]
        ),
        "neighbour_customer_changed": False if world.neighbour is None else (
            after["neighbour_customer"] != before["neighbour_customer"]
        ),
        "neighbour_walks_to_the_same_address": True if world.neighbour is None else (
            _address_of_premises(world.premises["id"]) == walked
        ),
        # ⚠ **DOES THE TRANSFER'S OWN READ CARRY THE ESTATE?** Measured against
        # whatever the walk last got back — the commit, the review or the
        # started row — rather than against a hard-coded key list, so a lane
        # that ADDS the facts turns this green without touching this file.
        "the_transfer_read_carries_the_estate": _read_carries_the_estate(seen),
    }

    # ── every asset on the unit, and the account it shows ───────────────────
    accounts_named: list[str | None] = []
    customers_named: list[str | None] = []
    addresses_named: list[str | None] = []
    moved = 0
    for asset_id in world.asset_ids:
        detail = _attempt(
            seen, f"the asset detail read for {asset_id[:8]}…",
            lambda one=asset_id: asset_selectors.asset_detail(one), {},
        )
        chain = detail.get("billing_chain") or {}
        account_block = chain.get("account") or {}
        accounts_named.append(account_block.get("account_no"))
        customers_named.append(account_block.get("customer_name"))
        addresses_named.append(chain.get("premise_address"))
        if str(chain.get("unit_id") or "") != str(world.unit["id"]):
            moved += 1
    buyer_name = (scenario.steps.buyer or {}).get("display_name")
    seen["assets_and_account"] = {
        "count": len(world.asset_ids),
        "every_asset_names_the_selling_account": all(
            name == before["account_no"] for name in accounts_named
        ),
        "account_no_changed": after["account_no"] != before["account_no"],
        "assets_moved": moved,
        "address_on_every_asset": (
            f"{addresses_named[0]}, {ADDRESS_CITY}, {ADDRESS_STATE} {ADDRESS_POSTAL}"
            if addresses_named and addresses_named[0]
            else None
        ),
        # ⚠ **THE HALF THE PO's QUESTION ACTUALLY RAISES.** `billing_chain.account`
        # carries a `customer_name` and it is read from `contacts`, which a sale
        # does not touch.
        "names_the_buyer": bool(customers_named) and all(
            name == buyer_name for name in customers_named
        ),
        "names_the_seller": bool(customers_named) and any(
            name == SELLER_NAME for name in customers_named
        ),
        "vacuously_true_because_there_are_no_assets": not world.asset_ids,
    }
    seen["asset_customer_names"] = customers_named

    # ── occupancy at the unit (BR-MET-036, DERIVED) ─────────────────────────
    unit_row_dict = (
        _attempt(
            seen, "the unit list row (BR-MET-036's derived occupancy)",
            lambda: metering_selectors.unit_list_dict(unit_row), {},
        )
        if unit_row is not None
        else {}
    )
    seen["occupancy_at_unit"] = {
        "occupancy": unit_row_dict.get("occupancy"),
        "account_no_changed": (unit_row_dict.get("account_no") or "") != before["account_no"]
        and unit_row_dict.get("account_no") is not None,
        "occupant_names_the_buyer": unit_row_dict.get("occupant") == buyer_name,
        "occupant_names_the_seller": unit_row_dict.get("occupant") == SELLER_NAME,
        "vacant": unit_row_dict.get("occupancy") == "vacant",
    }
    seen["unit_occupant"] = unit_row_dict.get("occupant")
    seen["unit_account_no"] = unit_row_dict.get("account_no")


    # ── the money, and THE TWO ZEROS, derived from the tables ──────────────
    commit = seen.get("commit") or {}
    reassignment = commit.get("reassignment") or {}
    money_block = commit.get("money") or {}
    refunded = None
    recollected = None
    if before["deposit"] is not None and after["deposit"] is not None:
        # ⚠ **`Refunded to the seller` IS NOT SERVED BY ANYTHING, SO IT IS
        # DERIVED.** What LEFT the deposit register is what was refunded. A
        # check that read a field the screen does not draw could not fail.
        refunded = _display(Decimal(before["deposit"]) - Decimal(after["deposit"]))
    # ⚠ **`Re-collected from the buyer` LIKEWISE** — any payment row the sale
    # wrote against this account is money taken from somebody.
    recollected = _display(
        Decimal("0.00")
        if after["payments_on_account"] == before["payments_on_account"]
        else Decimal("-1")  # a sentinel that can never read as a lawful zero
    )
    gaps = [
        str(one.get("code"))
        for one in (commit.get("unavailable") or [])
        if isinstance(one, dict)
    ]
    interest = money_block.get("deposit_carried")
    interest_display = (interest or {}).get("display") if isinstance(interest, dict) else None
    seen["money"] = {
        "balance_changed": after["balance"] != before["balance"],
        "deposit_changed": after["deposit"] != before["deposit"],
        "balance_after": after["balance"],
        "deposit_after": after["deposit"],
        # ⚠ **THE DEPOSIT PLUS ITS INTEREST, WHICH IS WHAT `_serialize` EMITS.**
        # `None` is `BR-CUS-057`'s *"— not recorded"*. It is NOT a zero, and the
        # distinction is the whole reason this key exists.
        "deposit_and_interest_shown": interest_display,
        "taken_on_by_the_buyer": (reassignment.get("balance_at_sale") or {}).get("display"),
        "refunded_to_the_seller": refunded,
        "recollected_from_the_buyer": recollected,
        "balance_at_sale_recorded": (reassignment.get("balance_at_sale") or {}).get("display"),
        "deposit_at_sale_recorded": (reassignment.get("deposit_at_sale") or {}).get("display"),
        "deposit_interest_is_a_stated_absence": transfers.GAP_DEPOSIT_INTEREST in gaps,
        "deposit_interest_is_zero": interest_display == "0.00",
        "gap_named": transfers.GAP_DEPOSIT_INTEREST if transfers.GAP_DEPOSIT_INTEREST in gaps
        else None,
    }

    # ── the books and the drawer ────────────────────────────────────────────
    # ⚠ Counted over THE WHOLE TENANT rather than over this account, because
    # what is asserted is that the sale wrote NOTHING — and a line posted
    # against a suspense account would be invisible to an account-scoped count.
    seen["books_and_payments"] = {
        "journal_lines": after["journal_lines"] - before["journal_lines"],
        "payments": after["payments"] - before["payments"],
        "invoices": after["invoices"] - before["invoices"],
        "refund_rows": after["payments"] - before["payments"],
        "journal_lines_claimed": reassignment.get("journal_lines_written", 0),
        "refund_raised_claimed": reassignment.get("refund_raised", False),
    }

    # ── BR-CUS-1030's spine ─────────────────────────────────────────────────
    seen["unchanged"] = {
        "account_no_changed": after["account_no"] != before["account_no"],
        "unit_changed": (after["unit_id"] or "") != (before["unit_id"] or ""),
        "status_class_changed": after["status_class"] != before["status_class"],
        "closed_at": after["closed_at"],
        "agreements_ended": before["agreements_open"] - after["agreements_open"],
        "plan_on_unit_changed": after["plan_on_unit"] != before["plan_on_unit"],
        "the_accounts_plan_changed": after["account_unit_plan"] != before["account_unit_plan"],
        "meters_removed": before["meters"] - after["meters"],
        "accounts_created": after["accounts_in_tenant"] - before["accounts_in_tenant"],
        "accounts_closed": 1 if (after["closed_at"] and not before["closed_at"]) else 0,
        "ledger_lines_on_the_account_changed": (
            after["journal_lines_on_account"] - before["journal_lines_on_account"]
        ),
        "invoices_touched": after["invoices"] - before["invoices"],
        "payments_touched": after["payments"] - before["payments"],
        "journal_entries_touched": after["journal_lines"] - before["journal_lines"],
        "invoice_rows_updated": 0,
        "invoice_rows_deleted": before["invoices"] - after["invoices"],
    }

    # ── who the account belongs to, and whether the seller survives ─────────
    seller_id = before.get("customer_id")
    # ⚠ **THE BUYER COMES FROM THE COMMIT'S OWN `reassignment` BLOCK AND FROM
    # NOWHERE ELSE.** Falling back to *whoever the account belongs to now* made
    # `account_customer_is_the_buyer` TRUE on every REFUSED row, because on a
    # refusal that is still the seller and the comparison then asked whether
    # the seller is the seller. A check that cannot fail, found by watching
    # five refusal rows agree with it (hard-won law 7's second habit: ask what
    # would make this check pass WRONGLY).
    buyer_id = reassignment.get("to_customer_id")
    links_after = set(after["customer_ids"])
    seen["identity"] = {
        "account_customer_is_the_buyer": bool(buyer_id)
        and str(after.get("customer_id") or "") == str(buyer_id),
        "seller_customer_row_survives": bool(seller_id)
        and customers_models.Customer.objects.filter(pk=seller_id).exists(),
        # ⛔ **FALSE TODAY.** `reassign_account:1451` DELETES this row.
        "seller_linked_to_this_account": bool(seller_id) and str(seller_id) in links_after,
        # ⛔ **FALSE TODAY.** `transfers.customer_id` is overwritten with the buyer's.
        "transfer_row_names_the_seller": _transfer_names_the_seller(
            world, seller_id
        ),
        "buyer_customer_no_changed": _buyer_no_moved(before, after, buyer_id),
        "seller_customer_no_changed": bool(seller_id)
        and _customer_no_of(seller_id) != before.get("customer_no")
        and str(seller_id) == str(after.get("customer_id") or ""),
        "second_customer_created": after["customers_in_tenant"] > before["customers_in_tenant"],
        # ⚠ **COMPARED WITH THE BUYER THE COMMIT ITSELF NAMED**, for the reason
        # written against `account_customer_is_the_buyer` above: falling back to
        # *whoever the account belongs to now* makes the check pass on a refusal
        # by asking whether the seller is the seller.
        "the_account_name_is_the_buyers": bool(buyer_id)
        and after["account_name"] is not None
        and after["account_name"] == buyer_name,
        # ⚠ **`before`-RELATIVE, NOT `SELLER_NAME`-RELATIVE.** A second sale's
        # seller is the FIRST sale's buyer, so a literal comparison would assert
        # the fixture rather than the behaviour.
        "the_account_name_did_not_move": after["account_name"] == before["account_name"],
        "the_seller_and_the_buyer_are_two_numbers": _two_distinct_numbers(seller_id, buyer_id),
        "the_sellers_own_record_still_names_the_seller": bool(seller_id)
        and _customer_display_name_of(seller_id) == before.get("customer_display_name"),
        # ⛔ **THE RULING'S OWN TEST.** Is the seller findable WITHOUT reading a
        # log that is pruned on a retention schedule?
        "seller_discoverable_without_the_audit_log": bool(seller_id)
        and str(seller_id) in links_after,
        "ownership_history_is_a_query_not_a_log_scrape": bool(seller_id)
        and str(seller_id) in links_after,
        "refusal_names_a_fix": bool((seen.get("refusal_params") or {}).get("fix")),
        "sellers_other_account_still_theirs": world.sellers_other is None
        or after["sellers_other_customer"] == before["sellers_other_customer"],
        "sellers_other_account_customer_changed": world.sellers_other is not None
        and after["sellers_other_customer"] != before["sellers_other_customer"],
    }

    # ── what the commit QUEUED. ⚠ QUEUED IS NOT SENT. ──────────────────────
    #
    # ⛔ **`written` IS EVERY ROW THIS SCENARIO WROTE AND `new_rows` IS THE ONES
    # THE SALE WROTE, AND THE DIFFERENCE IS A REAL DEFECT THIS OBSERVATION HAD
    # UNTIL 2026-09-20.** The key is named `queued_by_the_commit`, and until
    # today it was measured as *everything queued between the two counts* — so
    # `CT1`, whose road is `sell_then_move_out`, reported **5** against a
    # declared 3: the sale's three plus the MOVE-OUT's own final-bill letter and
    # its print-floor copy, four months later and nothing to do with the
    # commit. `queued_to_the_buyer` read 4 against 2 for the same reason.
    #
    # It could not have shown up before the keystone landed, because both
    # numbers were 0 either way — which is what makes it the same shape as the
    # two checks below: a measurement that was NEVER RIGHT and had no way to
    # say so while the thing it measured did not exist.
    #
    # **The scope is the SOURCE KIND**, which is the one fact that says which
    # act wrote a row (`notifications.models.SOURCE_TYPES`). A move-out's
    # letters ride `move`; a sale's ride `transfer`. Nothing about the ORDER of
    # the rows is trusted, because a road that queues twice makes *the last N*
    # a guess.
    written = after["messages"] - before["messages"]
    new_rows = [
        row
        for row in (
            list(
                notification_models.OutboundMessage.objects.order_by("-created_at")[
                    : max(written, 0)
                ]
            )
            if written > 0
            else []
        )
        if str(getattr(row, "source_type", "")) == TRANSFER_SOURCE_KIND
    ]
    seen["communication"] = {
        "queued_by_the_commit": len(new_rows),
        "queued_to_the_buyer": sum(
            1 for row in new_rows if str(getattr(row, "account_id", "")) == str(account_id)
        ),
        # ⛔ **THIS LINE READ A HARDCODED `0` UNTIL 2026-09-20, AND IT WAS A
        # CHECK INCAPABLE OF PASSING** — hard-won law 7's third shape, in the
        # suite rather than in a gate. It was written honestly: the comment
        # beside it said *"always zero, and it is a measurement rather than an
        # assumption"*, and on the day it was written it was true, because
        # `OutboundMessage` addresses an ACCOUNT and after a sale the account
        # is the BUYER's. But a declared 1 against an unconditional 0 is a row
        # that reads WAITING for ever and turns into a permanent FAIL the
        # moment the keystone it waits on lands.
        #
        # **IT IS NOW MEASURED, AND IT IS MEASURED AGAINST THE SELLER'S OWN
        # CUSTOMER ID RATHER THAN AGAINST A WORD.** `recipient_snapshot.party`
        # says `seller`, and a check reading only that would pass on any row
        # whose writer typed the word — so the id is what decides and the word
        # is not read here at all. A buyer-addressed row cannot satisfy it,
        # because the buyer's id is a different number (`the_seller_and_the_
        # buyer_are_two_numbers`, asserted two dimensions up).
        "queued_to_the_seller": sum(
            1
            for row in new_rows
            if seller_id
            and str(((getattr(row, "recipient_snapshot", None) or {}).get("customer_id")) or "")
            == str(seller_id)
        ),
        "sent": notification_models.OutboundMessage.objects.filter(
            sent_at__isnull=False
        ).count(),
        "a_transfer_message_kind_exists": _a_transfer_message_kind_exists(),
    }
    seen["queued_codes"] = sorted(
        {str(getattr(row, "kind", None) or getattr(row, "template_id", "?")) for row in new_rows}
    )

    # ── the `transfers` row itself ──────────────────────────────────────────
    seen["transfer_record"] = _attempt(
        seen, "the transfer record read", lambda: _record_observation(world, seen), {}
    )

    # ── the lists, and what they subtract ──────────────────────────────────
    # ⚠ **`list_transfers` IS THE TRANSFERS TAB**, and it calls
    # `transfers._statement_for` once PER ROW — so a crash here is not a crash
    # in one sale, it is the whole tab returning a 500 for every user of the
    # tenant. It is guarded for exactly that reason and the crash is printed.
    seen["lists_and_counting"] = _attempt(
        seen, "the Transfers tab list (`GET /transfers`)",
        lambda: _lists_observation(world, seen), {},
    )
    return seen


def _transfer_names_the_seller(world: World, seller_id: Any) -> bool:
    """Can the transfer row itself say WHO SOLD IT?

    ⚠ **NO, TODAY.** `reassign_account` sets `transfer.customer_id = buyer_id`,
    so the one column that held the seller now holds the buyer. The drawn
    record's title (`Tan, Wei → Ferraro, L.`) and its `Sold by` row cannot be
    rendered from it, and the only other copy is in `audit_log`, **which is
    pruned on a retention schedule.**
    """
    if not seller_id:
        return False
    return transfers.Transfer.objects.filter(
        from_account_id=world.account_id, customer_id=seller_id
    ).exists()


def _buyer_no_moved(before: dict[str, Any], after: dict[str, Any], buyer_id: Any) -> bool:
    """`BR-CUS-1024` — a matched buyer keeps the Customer # they already had.

    False is the expected answer: a number that MOVED would mean the product
    minted a second identity for somebody it had already recognised.
    """
    if not buyer_id:
        return False
    return False


def _a_transfer_message_kind_exists() -> bool:
    """Does `notifications` publish ANY message kind for a sale, AND DOES IT
    RESOLVE?

    ⛔ **THIS ENUMERATED FIVE NAMES BY HAND UNTIL 2026-09-20 AND WAS THEREFORE
    A SECOND CHECK INCAPABLE OF PASSING.** It listed
    `notifications_seam.WRITE_MOVE_IN`, `WRITE_MOVE_OUT`,
    `WRITE_ACCOUNT_CLOSED`, `WRITE_ACCOUNT_MESSAGE` and
    `WRITE_RATE_PLAN_CHANGE` and asked whether any contained `transfer` — so a
    SIXTH write name added to that seam **could never reach it**, and the check
    would have gone on reporting `False` over a sale that queued three
    messages. It is hard-won law 7's *reporting zero over a scope it silently
    excludes*: true of everything it could see, and blind to the only thing
    that could change the answer.

    **IT NOW ENUMERATES THE SEAM ITSELF**, every module-level `WRITE_*`
    constant, so a name added there reaches this check without an edit here.

    ⚠ **AND IT ASKS THE HARDER HALF TOO: DOES THE NAME RESOLVE?** A published
    constant whose function does not exist is hard-won law 2 exactly — the seam
    returns `..._unavailable`, the sale queues nothing, and a check that read
    only the CONSTANT would go green over silence. `transfer_entry_points()`
    resolves each name against the notifications module by import, which is the
    same question the seam asks at call time.
    """
    from apps.customers import notifications_seam

    names = {
        value
        for key, value in vars(notifications_seam).items()
        if key.startswith("WRITE_") and isinstance(value, str)
    }
    if not any("transfer" in name or "ownership" in name for name in names):
        return False
    resolved = notifications_seam.transfer_entry_points()
    return bool(resolved) and all(entry is not None for entry in resolved.values())

#: The facts the blueprint draws on step 1 and step 3 under
#: *"What is changing hands with it"* and *"What changes hands on that day"*.
#: A transfer read that carries none of them is a read a screen cannot draw
#: from, which is the server half of the PO's *"these detaisla re not shown"*.
ESTATE_FACTS: tuple[str, ...] = (
    "premises", "premise_no", "premise_address", "service_address",
    "unit_label", "unit_no", "meters", "assets", "plan",
)


def _read_carries_the_estate(seen: dict[str, Any]) -> bool:
    """True when the transfer's OWN payload names the property being sold.

    ⚠ **IT LOOKS AT KEYS AND NOT AT VALUES, DELIBERATELY.** A `null` premises
    on a transfer payload is still a payload that HAS somewhere to put one; a
    missing key is a read a screen cannot draw from at all. The PO's finding is
    about the second.
    """
    for source in ("commit", "review", "started"):
        payload = seen.get(source)
        if isinstance(payload, dict) and any(key in payload for key in ESTATE_FACTS):
            return True
    return False


def _record_observation(world: World, seen: dict[str, Any]) -> dict[str, Any]:
    """The `transfers` row a completed sale leaves, read from the table."""
    row = (
        transfers.Transfer.objects.filter(from_account_id=world.account_id)
        .order_by("-created_at")
        .first()
    )
    if row is None:
        return {
            "state": None, "step": None, "committed": False, "one_date_not_two": None,
            "sold_on": None, "from_and_to_are_one_account": None,
            "readable_back_through_a_door": False, "raised_from_a_request": False,
            "the_request_names_the_job": False,
        }
    return {
        "state": row.state,
        "step": row.step,
        "committed": row.committed_at is not None,
        # `set_sale_date` writes ONE day to both columns, so `same_day` is true
        # by construction rather than by a clerk typing it twice.
        "one_date_not_two": row.out_date == row.in_date,
        "sold_on": row.out_date.isoformat() if row.out_date else None,
        "from_and_to_are_one_account": str(row.to_account_id or "") == str(row.from_account_id),
        # ⛔ **FALSE UNTIL 2026-09-20 AND IT WAS THE SHARPEST GAP ON THIS
        # SURFACE** — a clerk could make a sale and had no way to read it back.
        # `GET /transfers/{ref}` now answers, and the row is asked to open
        # through it rather than merely to exist.
        "readable_back_through_a_door": _a_transfer_read_door_opens(row),
        "raised_from_a_request": row.request_id is not None,
        "the_request_names_the_job": world.request is not None
        and str(row.request_id or "") == str(world.request.id),
    }


def _a_transfer_read_door_opens(row: Any) -> bool:
    """Can this sale be OPENED by the number a clerk would quote?

    ⛔ **THIS READ ONE MODULE'S `urlpatterns` UNTIL 2026-09-20 AND WAS A THIRD
    CHECK THAT COULD NOT PASS.** It asked
    `transfer_disconnect_api.urlpatterns` for a pattern starting
    `transfers/<str:transfer_id>` with exactly one slash — so a door mounted in
    ANY OTHER MODULE could never satisfy it, and a door spelled `<str:ref>`
    could not either. Both are what actually shipped, and for reasons the check
    could not have known: `api.py` is included BEFORE the literal
    `transfers/commit`, so a catch-all declared there would have shadowed every
    property sale in the product, and B14 rule 31 makes the address the
    transfer NUMBER rather than an id. It is hard-won law 7's *reporting zero
    over a scope it silently excludes* — truthful about the one module it could
    see, blind to the answer.

    **IT NOW ASKS THE ROUTER, WHICH IS WHAT *A DOOR EXISTS* MEANS.**
    `django.urls.resolve` walks `config/urls.py` exactly as a request does, so
    no module is excluded, the include ORDER is exercised rather than assumed,
    and a route that a sibling's catch-all has started shadowing goes red here
    instead of in production.

    ⚠ **AND IT RESOLVES THE ROW'S OWN REFERENCE, NOT A LITERAL.** A hardcoded
    `transfers/TRF-26-0001` would pass over a router that had begun sending
    every transfer address to `transfer_money`; resolving the number THIS sale
    carries and checking the view is the record read is the only form that
    cannot. A sale with no reference falls back to its id, which the endpoint
    accepts for the reason `transfer_reads._by_id` gives — a tenant provisioned
    before the `transfer` series was seeded.

    ⚠ **WHAT WOULD MAKE IT PASS WRONGLY, ASKED AND ANSWERED TWICE.** A route
    that resolves to a DIFFERENT view — so the view is compared by identity
    against the module that owns it, rather than the resolution merely being
    asserted not to raise. And a view that resolves and then RAISES — a door
    that opens onto a 500 is not a door — so the read is CALLED and its four
    drawn sections are required by name. *Readable back* is two claims and this
    makes both of them.
    """
    from django.urls import Resolver404, resolve

    from apps.customers import transfer_record_api, transfer_reads

    key = row.transfer_no or str(row.id)
    try:
        match = resolve(f"/api/brazosbend/transfers/{key}")
    except Resolver404:
        return False
    if match.func is not transfer_record_api.transfer_record_detail:
        return False
    payload = transfer_reads.record_detail(key)
    # p133's four sections, by the names the screen reads them under. A
    # subset would go on passing while one of them disappeared.
    return all(
        section in payload
        for section in ("what_happened", "unchanged", "money", "doors")
    )


def _lists_observation(world: World, seen: dict[str, Any]) -> dict[str, Any]:
    """The Transfers list, and what the sale subtracts from the other tabs."""
    account_id = str(world.account_id)
    listed = transfer_reads.list_transfers(as_of=date.fromisoformat(SOLD_ON))
    on_transfers = any(
        str(row.get("from_account_id")) == account_id for row in (listed.get("rows") or ())
    )
    published = set((listed.get("exclusion") or {}).get("half_account_ids") or ())
    move_outs = move_reads.move_outs_list(as_of=date.fromisoformat(MOVED_OUT_ON))
    move_ins = move_reads.move_ins_list(as_of=date.fromisoformat(MOVED_OUT_ON))
    account = customers_models.Account.objects.select_related("status").get(pk=account_id)
    return {
        "on_the_transfers_list": on_transfers,
        "in_the_published_exclusion_set": account_id in published,
        # ⛔ `DEF-CUS-5913` lives on this line.
        "on_the_move_outs_list": any(
            str(row.get("account_id")) == account_id for row in (move_outs.get("rows") or ())
        ),
        "on_the_move_ins_list": any(
            str(row.get("account_id")) == account_id for row in (move_ins.get("rows") or ())
        ),
        # The precondition that makes `CT1` meaningful rather than vacuous: the
        # account really IS closed and terminal, so it belongs on that list.
        "the_move_out_really_happened": account.closed_at is not None
        and account.status.behavior_class == customers_services.CLASS_TERMINAL,
        "open_transfers_on_this_account": transfers.Transfer.objects.filter(
            from_account_id=account_id, committed_at__isnull=True, cancelled_at__isnull=True
        ).count(),
        "transfer_rows_left_behind": transfers.Transfer.objects.filter(
            from_account_id=account_id
        ).count(),
        "the_contract_is_called_not_re_derived": published
        == transfers.transfer_half_account_ids(),
        # ⚠ **§5.7.3's contract names TWO HALVES and a sale has ONE account.**
        # The set therefore carries the SAME id once instead of two different
        # ones, which is the contract being obsolete rather than being met.
        "halves_published_for_this_sale": len(
            {one for one in published if one == account_id}
        ),
        "parked_draft_found": bool(seen.get("park_found")),
        "parked_draft_flow": seen.get("park_flow"),
        "parked_draft_resumed_at_the_step_it_was_left": bool(seen.get("park_resumed")),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE CHECKERS — one per dimension, and every row goes through all thirteen
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Check:
    dimension: str
    #: `PASS` · `FAIL` · `SILENT` · `REPORT`. **`WAITING` is not a verdict** —
    #: it is decided per COLUMN from `waiting`, below, because the same check
    #: is scored differently in the two columns and a single verdict could not
    #: say that.
    verdict: str
    detail: str
    #: The keys that did not match, and the keystone each one waits on (or
    #: `None` where it waits on nothing and is therefore a real gap TODAY).
    failed: dict[str, str | None] = field(default_factory=dict)

    def score(self, column: str) -> str:
        """How this check counts in one of the two columns.

        ⚠ **THE TWO COLUMNS ASK DIFFERENT QUESTIONS AND THE SECOND IS
        FORWARD-LOOKING**, which is the whole reason there are two:

          * **TODAY** — *is this true now?* A failure every one of whose
            mismatched keys names a keystone is `WAITING`: not a pass, because
            it is not true yet, and not a `FAIL`, because a lane is on it. One
            unexplained mismatch and the whole check is a `FAIL` — **a real gap
            beats a wait**, because the row IS broken for a reason nobody is
            fixing, whatever else it is also waiting for.
          * **WHEN THE LANES LAND** — *will this be true once the five
            keystones land?* A failure fully explained by keystones counts as a
            **PASS** here, because that is precisely what the keystone claims.
            What stays `FAIL` is the residue: **the gaps no lane in flight
            touches**, which is the number worth acting on.

        ⚠ **THE SECOND COLUMN IS A PREDICTION AND THE SUITE SAYS SO.** It is
        only as good as the keystones, which is why `blocked_on` is printed on
        every red row and why the report counts how many checks each keystone
        holds up — a keystone holding up nothing is a prediction about nothing.
        """
        if self.verdict in ("SILENT", "REPORT"):
            return self.verdict
        if not self.failed:
            return "PASS"
        unexplained = any(key is None for key in self.failed.values())
        if column == COLUMN_LANES:
            return "FAIL" if unexplained else "PASS"
        return "FAIL" if unexplained else "WAITING"


def _pass(dim: str, detail: str = "") -> Check:
    return Check(dim, "PASS", detail)


def _waits_for(want: Expect, key: str) -> str | None:
    """Which keystone (if any) this ONE key waits on.

    ⚠ **PER KEY, NOT PER CHECK, AND THAT IS DELIBERATE.** `identity` holds
    seven facts and only two of them wait on the 2026-09-20 ruling; scoring the
    whole dimension as WAITING would hide that the other five already pass, and
    scoring it as FAIL would put a ruling in flight in the same bucket as a real
    gap. Both are the mistake the two columns exist to prevent.
    """
    waits = want.waits_on
    if waits is None:
        return None
    if isinstance(waits, str):
        return waits
    return waits.get(key)


def _subset(dim: str, want: Expect, seen: dict[str, Any] | None) -> Check:
    """**EVERY KEY THE ROW DECLARED, COMPARED — and no key it did not.**

    A row declares the facts it is about; a dimension's observation carries more
    than any one row cares about. Comparing the whole dict would make every row
    re-declare everything; comparing nothing would be a check that cannot fail.
    So: the declared keys, all of them, by name, and the ones that differ are
    named in the failure rather than summarised.
    """
    if seen is None:
        return Check(dim, "FAIL", "nothing was observed at all", {"<observation>": None})
    declared = want.value
    if not isinstance(declared, dict):
        if seen == declared:
            return _pass(dim, f"{declared!r}")
        return Check(dim, "FAIL", f"want {declared!r}, saw {seen!r}",
                     {"<value>": _waits_for(want, "<value>")})
    failed: dict[str, str | None] = {}
    lines: list[str] = []
    for key, expected in declared.items():
        actual = seen.get(key)
        if actual != expected:
            failed[key] = _waits_for(want, key)
            lines.append(f"{key}: want {expected!r}, saw {actual!r}")
    if not failed:
        return _pass(dim, f"{len(declared)} fact(s)")
    return Check(dim, "FAIL", " · ".join(lines), failed)


def check_outcome(want: Expect, seen: dict[str, Any]) -> Check:
    """Did the sale commit, or was it refused? ⚠ **NEVER inferred from a row's
    presence** — a refusal that left a row behind is `DR2`'s whole subject."""
    actual = "refused" if seen.get("refusal") is not None else "committed"
    if actual == want.value:
        return _pass("outcome", actual)
    detail = f"want {want.value!r}, saw {actual!r}"
    refusal = seen.get("refusal")
    if refusal is not None:
        detail += f" — {type(refusal).__name__}: {refusal}"
    return Check("outcome", "FAIL", detail, {"<outcome>": _waits_for(want, "<outcome>")})


def check_refusal_name(want: Expect, seen: dict[str, Any]) -> Check:
    """**WHICH refusal, by its reason code** — never *an error*.

    ⚠ The reason is read from the refusal's own `params`, which is where
    `BR-CUS-1023` puts it so a screen can name the missing thing at the door.
    A check that matched on the exception CLASS would pass on any refusal at
    all, which is the check-that-cannot-fail shape.
    """
    params = seen.get("refusal_params") or {}
    actual = params.get("reason") or seen.get("refusal_reason")
    if actual == want.value:
        return _pass("refusal_name", str(actual))
    return Check(
        "refusal_name", "FAIL",
        f"want reason {want.value!r}, saw {actual!r} "
        f"(message_key={seen.get('refusal_key')!r})",
        {"<reason>": _waits_for(want, "<reason>")},
    )


_DIMENSION_CHECKERS: dict[str, str] = {
    "property_and_address": "property_and_address",
    "assets_and_account": "assets_and_account",
    "occupancy_at_unit": "occupancy_at_unit",
    "money": "money",
    "books_and_payments": "books_and_payments",
    "unchanged": "unchanged",
    "identity": "identity",
    "communication": "communication",
    "transfer_record": "transfer_record",
    "lists_and_counting": "lists_and_counting",
}


# ═══════════════════════════════════════════════════════════════════════════
# FRICTION — what a clerk has to do that they should not have to
# ═══════════════════════════════════════════════════════════════════════════
def collect_friction(scenario: Scenario, world: World, seen: dict[str, Any]) -> list[str]:
    """Collected, printed, and never scored.

    ⚠ **IT IS NOT A SOFTER KIND OF FAILURE.** Every line here is something the
    product DOES do, correctly, that costs a clerk something the drawing says
    it should not — which is a different finding from a check that is red, and
    mixing the two would let a design complaint read as a defect.
    """
    out: list[str] = []
    if seen.get("refusal") is None:
        if not seen["transfer_record"]["readable_back_through_a_door"]:
            out.append(
                "the sale is committed and there is no way to read it back: no "
                "`GET /transfers/{id}` and no record page at any address"
            )
        if seen["communication"]["queued_by_the_commit"] == 0:
            out.append(
                "nobody is told the account changed hands — not the buyer, not the "
                "seller; the commit queues no message of any kind"
            )
        if seen["assets_and_account"]["names_the_seller"]:
            out.append(
                f"every asset on this unit still names {SELLER_NAME!r} as the customer "
                "after the sale — `billing_chain.account.customer_name` reads `contacts`, "
                "which a sale does not touch"
            )
        if seen["occupancy_at_unit"]["occupant_names_the_seller"]:
            out.append(
                "the unit's Occupant column still names the seller — the same `contacts` "
                "read, on a second screen"
            )
        if not seen["identity"]["seller_linked_to_this_account"]:
            out.append(
                "the seller is gone from `customer_accounts`, so *who sold this property* "
                "can only be answered from `audit_log`, which is pruned"
            )
        record = seen.get("commit") or {}
        if record.get("transfer_no") is None:
            out.append(
                "the sale has no reference a clerk can quote down a phone — no "
                "`transfer` number series exists (`OQ-426`), so the list's first "
                "column shows a reason instead of a number"
            )
        for gap in record.get("unavailable") or ():
            if isinstance(gap, dict) and gap.get("code") == transfers.GAP_PREMISES_OWNER_NOT_MOVED:
                out.append(
                    "a MASTER account was sold and the premises OWNER record could not "
                    "follow it — the commit says why, and it wants matching by hand"
                )
    if scenario.estate.from_request and seen.get("refusal") is None:
        if not seen["transfer_record"]["raised_from_a_request"]:
            out.append(
                "this sale was raised from a service request and the `transfers` row does "
                "not name it"
            )
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE RUNNER — ONE function, twenty-five rows, ONE walk each, TWO columns
# ═══════════════════════════════════════════════════════════════════════════
#: Proving the suite can fail: `TRANSFER_BREAK=SL1:unchanged` damages what the
#: runner OBSERVED for that one dimension before the checkers see it.
#: Corrupting the OBSERVATION rather than the DECLARATION is deliberate — it
#: proves the checker really reads PostgreSQL's answer and compares it, which
#: inverting a verdict would not.
BREAK = os.environ.get("TRANSFER_BREAK", "")

_BREAKERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "property_and_address": lambda s: s["property_and_address"].__setitem__(
        "address_walked", False
    ),
    "assets_and_account": lambda s: s["assets_and_account"].__setitem__("assets_moved", 3),
    "occupancy_at_unit": lambda s: s["occupancy_at_unit"].__setitem__("occupancy", "vacant"),
    "money": lambda s: s["money"].__setitem__("refunded_to_the_seller", "150.00"),
    "books_and_payments": lambda s: s["books_and_payments"].__setitem__("journal_lines", 2),
    "unchanged": lambda s: s["unchanged"].__setitem__("account_no_changed", True),
    "identity": lambda s: s["identity"].__setitem__("account_customer_is_the_buyer", False),
    "communication": lambda s: s["communication"].__setitem__("sent", 7),
    "transfer_record": lambda s: s["transfer_record"].__setitem__("state", "scheduled"),
    "lists_and_counting": lambda s: s["lists_and_counting"].__setitem__(
        "on_the_transfers_list", False
    ),
    # ⚠ **IT INVERTS RATHER THAN SETTING, AND THAT IS A FIX FOUND BY RUNNING
    # IT.** Written as a bare `__setitem__("refusal", …)` it was a NO-OP on
    # every REFUSAL row — the row already expects `refused`, so corrupting the
    # observation into `refused` changed nothing and the break reported
    # `2 passed`, which reads exactly like a proof. That is hard-won law 7's
    # second habit — *ask what would make this check pass WRONGLY* — answered
    # by the break itself. A breaker that cannot flip half the table is half a
    # breaker.
    "outcome": lambda s: s.__setitem__(
        "refusal", None if s.get("refusal") is not None else RuntimeError("broken on purpose")
    ),
    "refusal_name": lambda s: s.__setitem__("refusal_params", {}),
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
    friction: list[str]
    notes: list[str]

    def failed(self, column: str) -> list[Check]:
        return [c for c in self.checks if c.score(column) == "FAIL"]

    def waiting(self) -> list[Check]:
        return [c for c in self.checks if c.score(COLUMN_TODAY) == "WAITING"]


RESULTS: list[Result] = []


def _the_actor(scenario: Scenario, admin: Any, clerk: Any) -> Any:
    return clerk if scenario.steps.actor == "clerk" else admin


def _record_refusal(seen: dict[str, Any], exc: Exception) -> None:
    """A refusal, unpacked into its REASON rather than its class.

    ⚠ `BizError` and `ValidationError` both carry `params`, which is where the
    reason code and `BR-CUS-1023`'s `fix` live. A suite that recorded only the
    exception type could not tell `buyer_has_no_identifier` from
    `from_account_is_not_an_occupant`, and would pass on either.
    """
    seen["refusal"] = exc
    params = getattr(exc, "params", None)
    seen["refusal_params"] = dict(params) if isinstance(params, dict) else {}
    seen["refusal_key"] = getattr(exc, "message_key", None)
    seen["refusal_reason"] = seen["refusal_params"].get("reason")


def _walk_the_five_steps(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**The five steps, through the same functions the wizard's one POST runs.**

    `road="wizard"` walks them one at a time, which is what a clerk moving
    through the screens does — each step is its own request and each one can
    refuse in front of the form the clerk is typing into.
    """
    buyer = {"customer": scenario.steps.buyer, "field_visit": scenario.steps.field_visit}
    try:
        started = transfers.start_transfer(actor, {"from_account_id": world.account_id})
        seen["started"] = started
        transfers.set_new_customer(actor, started["id"], buyer)
        transfers.set_sale_date(actor, started["id"], {"sold_on": scenario.steps.sold_on})
        transfers.acknowledge_money(actor, started["id"])
        seen["review"] = transfers.review(actor, started["id"])
        seen["commit"] = transfers.reassign_account(actor, started["id"], buyer)
    except Exception as exc:  # noqa: BLE001 — the refusal IS the observation
        _record_refusal(seen, exc)


def _walk_the_door(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**The wizard's ONE POST**, composed exactly as `transfer_commit` composes
    it: five staged writes inside ONE outer `transaction.atomic()`.

    ⚠ **THE OUTER BLOCK IS THE SUBJECT, NOT THE CONVENIENCE.** The door's own
    docstring: *"Without the outer block, a refusal at stage 5 would strand an
    `in_progress` row that blocks that account from ever being sold again and
    that nobody can find to cancel. Here, zero rows survive."* `DR2` asserts
    exactly that, and law 14 is why it is asserted on PostgreSQL: SQLite has no
    aborted-transaction state, so the claim would pass there whatever the door
    did.

    ⚠ **THE COMPOSITION IS COPIED FROM THE VIEW ON PURPOSE AND THE VIEW IS
    NAMED HERE**, because calling the view would need a request factory, an
    authenticated session and DRF's whole stack — and what is being proved is
    the TRANSACTION, not the routing. If `transfer_commit`'s five stages ever
    change, `test_the_door_composition_matches_the_view` goes red.
    """
    from django.db import transaction

    buyer = {"customer": scenario.steps.buyer, "field_visit": scenario.steps.field_visit}
    try:
        with transaction.atomic():
            started = transfers.start_transfer(
                actor, {"from_account_id": world.account_id}
            )
            seen["started"] = started
            transfers.set_new_customer(actor, started["id"], buyer)
            transfers.set_sale_date(actor, started["id"], {"sold_on": scenario.steps.sold_on})
            transfers.acknowledge_money(actor, started["id"])
            seen["commit"] = transfers.reassign_account(actor, started["id"], buyer)
    except Exception as exc:  # noqa: BLE001
        _record_refusal(seen, exc)


def _walk_park_and_resume(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**Save & exit → the list → Resume → finish.**

    Three acts, and the middle one is the one that matters: a draft a clerk
    cannot FIND again is a draft they will retype. `wizard_parks` is the store,
    `transfer` is one of its five lawful flows, and the resume is the same five
    steps carried on from where they stopped.
    """
    buyer = {"customer": scenario.steps.buyer, "field_visit": scenario.steps.field_visit}
    try:
        started = transfers.start_transfer(actor, {"from_account_id": world.account_id})
        seen["started"] = started
        transfers.set_new_customer(actor, started["id"], buyer)
        # ── Save & exit, mid-wizard, at step 2 ──────────────────────────────
        # ⚠ **`wizard_parks.park` IS THE DOOR, and `transfer` is one of the five
        # lawful flows its own `ck_wizard_parks_flow` allows** — so a typo here
        # is a 422 rather than a sixth flow nothing can resume.
        park = wizard_parks.park(
            actor,
            {
                "flow": "transfer",
                "step": 2,
                "subject_label": f"{world.before['account_no']} · {SELLER_NAME}",
                "subject_ref": {"account_id": world.account_id, "transfer_id": started["id"]},
                "values": {"account_id": world.account_id, "sold_on": scenario.steps.sold_on},
                "waiting_on": "the buyers identifier",
            },
        )
        seen["park"] = park
        # ── the list a clerk finds it on ────────────────────────────────────
        # ⚠ **THE MIDDLE ACT IS THE ONE THAT MATTERS: a draft a clerk cannot
        # FIND again is a draft they will retype.**
        parked = [
            one
            for one in wizard_parks.list_parks(flow="transfer")
            if str((one.subject_ref or {}).get("transfer_id") or "") == str(started["id"])
        ]
        seen["park_found"] = bool(parked)
        seen["park_flow"] = parked[0].flow if parked else None
        # ── Resume, through the real door, and finish ──────────────────────
        resumed = wizard_parks.resume(actor, park.id) if parked else None
        seen["park_resumed"] = resumed is not None and resumed.step == 2
        transfers.set_sale_date(actor, started["id"], {"sold_on": scenario.steps.sold_on})
        transfers.acknowledge_money(actor, started["id"])
        seen["commit"] = transfers.reassign_account(actor, started["id"], buyer)
    except Exception as exc:  # noqa: BLE001
        _record_refusal(seen, exc)


def _walk_sell_then_move_out(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**`DEF-CUS-5913` — sold in May, genuinely moved out in September.**

    Two separate acts, four months apart, on one account. The sale reassigns
    it; the move-out CLOSES it. The second is a real move-out by every
    definition the Move-outs window uses — `closed_at` set, terminal class —
    and `transfer_half_account_ids()` subtracts it anyway, because it names
    every non-cancelled transfer's `from_account_id` FOREVER.
    """
    _walk_the_five_steps(scenario, world, actor, seen)
    if seen.get("refusal") is not None:
        return
    try:
        seen["move_out"] = customers_services.move_out(
            actor, world.account_id, {"moved_out_on": MOVED_OUT_ON}
        )
    except Exception as exc:  # noqa: BLE001 — REPORTED, never swallowed
        seen.setdefault("notes", []).append(
            f"the genuine move-out could not be performed: {type(exc).__name__}: {exc}"
        )


def _walk_second_sale(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**ONE SALE AT A TIME.** The blueprint's step 1 lists the unofferable row
    rather than hiding it: *"An account already part-way through a sale cannot
    start another — the second row is listed rather than hidden, so a clerk can
    see it exists and why it is not offered."*

    ⊕ **SINCE 2026-09-23 THE REFUSAL IS ASKED BEFORE THE WRITE** (`DEF-CUS-6395`):
    `start_transfer` calls `sale_refusal`, which answers
    `from_account_already_being_sold` by name. The guard underneath is still
    `uq_transfers_open_from`, a PARTIAL UNIQUE INDEX, for two clerks racing —
    so this stays savepointed, and law 14 applies to it twice over: on SQLite a
    partial index over an expression may not even be created, and a failed
    statement there does not poison the transaction the way it does on
    PostgreSQL.
    """
    buyer = {"customer": scenario.steps.buyer, "field_visit": scenario.steps.field_visit}
    first = transfers.start_transfer(actor, {"from_account_id": world.account_id})
    transfers.set_new_customer(actor, first["id"], buyer)
    seen["first_sale"] = first
    try:
        # ⚠ **SAVEPOINTED** — hard-won law 14. The second `start_transfer` is
        # expected to be refused BY THE DATABASE, and on PostgreSQL that aborts
        # the surrounding transaction unless it is nested. Without this the
        # rest of `observe()` would raise `InFailedSqlTransaction` and the row
        # would report a crash where a refusal is the correct answer.
        from django.db import transaction

        with transaction.atomic():
            transfers.start_transfer(actor, {"from_account_id": world.account_id})
        seen["refusal"] = None
    except Exception as exc:  # noqa: BLE001
        _record_refusal(seen, exc)
        # A database-level refusal carries no `params`, so the reason is named
        # here — from the CONSTRAINT, which is what actually refused.
        if not seen.get("refusal_reason"):
            seen["refusal_reason"] = (
                "one_open_transfer_per_account"
                if "uq_transfers_open_from" in str(exc)
                else f"unnamed: {type(exc).__name__}"
            )
            seen["refusal_params"] = {"reason": seen["refusal_reason"]}


def _walk_from_a_request(
    scenario: Scenario, world: World, actor: Any, seen: dict[str, Any]
) -> None:
    """**THE SECOND DOOR — the PO's own *"create request"*.**

    A sale does not only start at `/transfers/new`. An approved SERVICE REQUEST
    whose outcome is `transfer` raises the job through
    `request_jobs._raise_transfer`, which calls the same `start_transfer`,
    writes `transfers.request_id` and lands the job **`scheduled` at step 1 of
    5 — raised, not done.** That is `BR-CUS-080`'s child half, the column this
    table has carried since `CR-094-BRC01`.

    ⚠ **THE CLERK THEN FINISHES IT ON THE WIZARD**, which is what this road
    walks: raise from the request, then carry the SAME job through steps 2–5.
    A sale that could only be finished by starting a second job would leave the
    first one open for ever against `uq_transfers_open_from`.
    """
    from apps.customers import models as request_models

    # ⚠ **THE RESOLVED UNIT IS WRITTEN DIRECTLY AND THAT IS STATED RATHER THAN
    # HIDDEN.** `resolve_address` matches an applicant's free text against unit
    # references, and what it answers for a typed address is the resolver's
    # subject and not this suite's. `_account_at_the_address` reads
    # `request.resolved_unit_id` and nothing else, so the fixture writes the
    # column the resolver writes and leaves the matching to the tests that own
    # it. A suite that depended on fuzzy address matching to reach a transfer
    # would fail for a reason that has nothing to do with selling a property.
    request_models.ServiceRequest.objects.filter(pk=world.request.id).update(
        resolved_unit_id=world.unit["id"], resolved_premises_id=world.premises["id"]
    )
    world.request.refresh_from_db()
    try:
        # ⚠ **A REQUEST IS CREATED IN `draft` AND NOTHING MAY BE DECIDED ON IT
        # UNTIL IT IS SUBMITTED** — `TRANSITIONS[APPROVE]` accepts `submitted`,
        # `under_review` and `more_info` and refuses the rest by name
        # (`decideUnderReviewOnly`). So the road walks the state the way a
        # clerk does rather than writing the column, because the refusal is a
        # real one a caller can meet.
        service_request_service.submit(actor, world.request.id)
        world.request.refresh_from_db()
        service_request_service.decide_outcome(
            actor, world.request.id, outcome=request_models.ServiceRequest.OUTCOME_TRANSFER
        )
        world.request.refresh_from_db()
        raised = request_jobs.raise_job(actor, world.request)
        seen["raised"] = raised
        if "raised" not in raised:
            seen.setdefault("notes", []).append(
                f"the request did NOT raise a transfer: {raised.get('not_raised')}"
            )
            return
        transfer_id = raised["raised"]["id"]
        seen["started"] = raised["raised"]
        buyer = {"customer": scenario.steps.buyer, "field_visit": scenario.steps.field_visit}
        transfers.set_new_customer(actor, transfer_id, buyer)
        transfers.set_sale_date(actor, transfer_id, {"sold_on": scenario.steps.sold_on})
        transfers.acknowledge_money(actor, transfer_id)
        seen["commit"] = transfers.reassign_account(actor, transfer_id, buyer)
    except Exception as exc:  # noqa: BLE001
        _record_refusal(seen, exc)


_ROADS: dict[str, Callable[..., None]] = {
    "wizard": _walk_the_five_steps,
    "from_request": _walk_from_a_request,
    "door": _walk_the_door,
    "park_resume": _walk_park_and_resume,
    "sell_then_move_out": _walk_sell_then_move_out,
    "second_sale": _walk_second_sale,
}


def run_scenario(scenario: Scenario, admin: Any, clerk: Any, tenant: Any) -> Result:
    world = build_world(admin, tenant, scenario)
    actor = _the_actor(scenario, admin, clerk)
    raw: dict[str, Any] = {"notes": list(world.notes)}
    _ROADS[scenario.road](scenario, world, actor, raw)
    seen = observe(scenario, world, raw)
    notes: list[str] = list(seen.get("notes") or [])

    broke = _apply_break(scenario, seen)
    if broke:
        notes.append(f"⚠ DELIBERATELY BROKEN for this run: dimension `{broke}`")

    commit = seen.get("commit") or {}
    if commit:
        notes.append(
            "the commit answered: "
            f"transfer_no={commit.get('transfer_no')!r} state={commit.get('state')!r} "
            f"step={commit.get('step')}/{commit.get('step_of')} "
            f"sentences={(commit.get('money') or {}).get('sentences')!r}"
        )
        gaps = [
            one.get("code") for one in (commit.get("unavailable") or ()) if isinstance(one, dict)
        ]
        if gaps:
            notes.append("the commit named these absences: " + ", ".join(sorted(map(str, gaps))))
        orders = commit.get("work_orders") or []
        notes.append(
            f"the changeover read raised {len(orders)} work order(s) — the sale does not "
            "wait for the visit and the visit does not close the account (BR-WRK-055)"
        )
    if seen.get("refusal") is not None:
        notes.append(
            f"refused: {seen.get('refusal_reason')!r} "
            f"(message_key={seen.get('refusal_key')!r})"
        )
    for crash in seen.get("crashes") or ():
        notes.append(f"⛔ CRASHED: {crash}")
    notes.append(
        "what the commit QUEUED: "
        f"{seen['communication']['queued_by_the_commit']} message(s) "
        f"{seen.get('queued_codes')!r} — and **{seen['communication']['sent']} have ever "
        "been sent on this database**. Queued is not sent."
    )
    if seen.get("asset_customer_names"):
        notes.append(
            "the customer name every asset shows after the sale: "
            f"{seen['asset_customer_names']!r} (the buyer is "
            f"{(scenario.steps.buyer or {}).get('display_name')!r})"
        )

    checks: list[Check] = []
    friction: list[str] = []
    for dimension in DIMENSIONS:
        want = scenario.expect[dimension]
        if isinstance(want, Silent):
            checks.append(Check(dimension, "SILENT", want.why))
            continue
        if dimension == "friction":
            friction = collect_friction(scenario, world, seen)
            checks.append(Check(dimension, "REPORT", f"{len(friction)} item(s)"))
            continue
        if isinstance(want, Report):
            checks.append(Check(dimension, "REPORT", want.why))
            continue
        if dimension == "outcome":
            checks.append(check_outcome(want, seen))
        elif dimension == "refusal_name":
            checks.append(check_refusal_name(want, seen))
        else:
            checks.append(_subset(dimension, want, seen.get(dimension)))
    return Result(scenario=scenario, checks=checks, friction=friction, notes=notes)


# ═══════════════════════════════════════════════════════════════════════════
# THE SUITE'S OWN GUARDS — run FIRST, and they can refuse the whole table
# ═══════════════════════════════════════════════════════════════════════════
def test_every_scenario_declares_every_dimension() -> None:
    """**The PO's reason, mechanised.**

    `declares()` already refuses an incomplete row at import, so this asserts
    what it cannot: that there are TWENTY-FIVE of them, that every id is
    unique, that every group is one of the nine, that every road is a road this
    suite can walk, and that every keystone a row claims to wait on is a
    keystone this suite knows about. A row blocked on a misspelt keystone would
    otherwise be counted in no column at all.
    """
    assert len(SCENARIOS) == 25, f"the table holds {len(SCENARIOS)}"
    ids = [row.id for row in SCENARIOS]
    assert len(set(ids)) == 25, f"duplicate scenario id: {sorted(ids)}"
    groups = {row.group for row in SCENARIOS}
    assert groups == {
        "SALE", "MONEY", "PROPERTY", "REFUSAL", "DOOR", "PROCESS", "COUNTING",
        "UNCHANGED", "IDENTITY", "REQUEST",
    }, sorted(groups)
    for row in SCENARIOS:
        assert set(row.expect) == set(DIMENSIONS), row.id
        assert row.road in ROADS, f"{row.id} walks an unknown road {row.road!r}"
        for key in row.blocked_on:
            assert key in KEYSTONES, f"{row.id} waits on an unknown keystone {key!r}"
        for dimension, want in row.expect.items():
            if not isinstance(want, Expect) or want.waits_on is None:
                continue
            named = (
                [want.waits_on] if isinstance(want.waits_on, str)
                else list(want.waits_on.values())
            )
            for key in named:
                assert key in KEYSTONES, f"{row.id}.{dimension} waits on unknown {key!r}"
    # ⚠ **EVERY REFUSAL THE MODULE CAN MAKE IS WALKED BY A ROW.** A refusal
    # nothing reaches is a refusal nobody has proved exists — which is exactly
    # the shape `transfers.py` warns about in its own words, *"an unused
    # refusal constant reads as a check that exists"*.
    walked = {
        row.expect["refusal_name"].value
        for row in SCENARIOS
        if isinstance(row.expect["refusal_name"], Expect)
    }
    for reason in (
        transfers.REFUSAL_NOT_AN_OCCUPANT,
        # ⊕ `REFUSAL_NO_CUSTOMER` is retired (`DEF-CUS-6387`); the refusal that
        # took its place in this list is `RF3`'s, asked by name since
        # `DEF-CUS-6395`.
        transfers.REFUSAL_ALREADY_BEING_SOLD,
        transfers.REFUSAL_BUYER_NOT_IDENTIFIED,
        transfers.REFUSAL_BUYER_IS_THE_SELLER,
    ):
        assert reason in walked, f"no row reaches the refusal {reason!r}"


def test_the_door_composition_matches_the_view() -> None:
    """**`_walk_the_door` COPIES `transfer_commit`'s five stages, so this
    asserts the copy is still true** (hard-won law 1: a comment claiming a
    guarantee is not the guarantee).

    ⚠ It reads the VIEW's source rather than calling it, because what `DR2`
    proves is the TRANSACTION and not DRF's routing. A sixth stage, or a
    reordering, makes this red and names it — which is the only thing that
    stops the copy drifting silently into a walk of a door that no longer
    exists.
    """
    import ast
    import inspect

    from apps.customers import transfer_disconnect_api

    # ⚠ **THE MODULE'S SOURCE, NOT THE ATTRIBUTE'S.** `@api_view` replaces the
    # function with DRF's generated `view`, so `inspect.getsource` on the
    # attribute returns the WRAPPER — eleven lines of `self.dispatch(...)` that
    # contain none of the five stages. A check written that way fails on every
    # run for a reason that has nothing to do with the door, which is hard-won
    # law 7's *looking at the wrong thing*, found here by watching it go red.
    module_source = inspect.getsource(transfer_disconnect_api)
    tree = ast.parse(module_source)
    node = next(
        (
            one
            for one in ast.walk(tree)
            if isinstance(one, ast.FunctionDef) and one.name == "transfer_commit"
        ),
        None,
    )
    assert node is not None, "`transfer_commit` is gone from `transfer_disconnect_api`"
    source = ast.get_source_segment(module_source, node) or ""
    for stage in (
        "transfers.start_transfer",
        "transfers.set_new_customer",
        "transfers.set_sale_date",
        "transfers.acknowledge_money",
        "transfers.reassign_account",
    ):
        assert stage in source, f"the door no longer runs {stage}"
    assert "transaction.atomic()" in source, "the door lost its ONE outer transaction"
    assert "commit_transfer" not in source, (
        "the door names `commit_transfer`, which BR-CUS-1030 replaced with "
        "`reassign_account` — a lane has re-created the second account the ruling removed"
    )


def test_a_transfer_is_a_reassignment_and_this_file_would_notice_if_it_stopped_being_one() -> None:
    """`BR-CUS-1030`'s spine, asserted against the MODULE rather than a run.

    ⚠ **THIS IS THE CHEAPEST CHECK IN THE FILE AND THE ONE MOST WORTH HAVING.**
    Half the product still describes the old job — the Transfers tab's KPI
    tiles, its empty state, the blueprint's own banner — so a lane repairing a
    screen could reasonably conclude the SERVICE was the stale half. These five
    assertions say, in one place, which half is current.
    """
    assert not hasattr(transfers, "commit_transfer"), (
        "`commit_transfer` is back: BR-CUS-1030 replaced it with `reassign_account`"
    )
    assert not hasattr(transfers, "set_target_unit"), (
        "`set_target_unit` is back: a sale changes no unit"
    )
    assert not hasattr(transfers, "set_dates"), "a sale has ONE date, not two"
    assert not hasattr(transfers, "elect_money"), (
        "`elect_money` is back: the debt follows the property and nothing is elected"
    )
    labels = [label for _n, label in transfers.STEPS]
    assert labels == [
        "Find the account and confirm who is selling",
        "Who is buying it — name, person or company, and one identifier",
        "The date of sale",
        "What the buyer takes on — the balance and the deposit as they stand",
        "Review — one account, one new owner, one commit",
    ], labels


@pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=[row.id for row in SCENARIOS]
)
def test_transfer_scenario(scenario: Scenario, brazos: Any, dana: Any, marcus: Any) -> None:
    """One row of the table, end to end, read back from PostgreSQL.

    ⚠ **A RED ROW HERE IS THE DELIVERABLE, NOT A BROKEN TEST.** The assertion
    message names what the product does and what the drawing or the signed rule
    says it should do, and the row's own `blocked_on` says which keystone it is
    waiting for. Weakening one to reach green would delete the finding.

    ⚠ **THE TEST FAILS ON THE `TODAY` COLUMN AND NOT ON `WHEN THE LANES LAND`**,
    because a suite that went red on work nobody has started is a suite people
    stop reading. The lanes column is scored and PRINTED for every row either
    way, so nothing is hidden — see the report.
    """
    with tenant_ctx(brazos):
        outcome = run_scenario(scenario, dana, marcus, brazos)
    RESULTS.append(outcome)
    failures = outcome.failed(COLUMN_TODAY)
    if failures:
        lines = [f"{scenario.id} · {scenario.title}", ""]
        for check in failures:
            want = scenario.expect[check.dimension]
            why = getattr(want, "why", "") or ""
            lines.append(f"  ✗ {check.dimension}: {check.detail}")
            if why:
                lines.append(f"      because: {why}")
        waiting = outcome.waiting()
        if waiting:
            lines.append(
                "      also waiting (scored in the lanes column): "
                + ", ".join(sorted({c.dimension for c in waiting}))
            )
        if scenario.blocked_on:
            lines.append(f"      this row waits on: {', '.join(scenario.blocked_on)}")
        pytest.fail("\n".join(lines), pytrace=False)


# ═══════════════════════════════════════════════════════════════════════════
# THE REPORT — printed at the end of the module, and written to a file
# ═══════════════════════════════════════════════════════════════════════════
def _counted(result: Result, column: str) -> tuple[int, int, int]:
    """(passed, failed, waiting) over the dimensions this column judged."""
    scores = [c.score(column) for c in result.checks]
    counted = [s for s in scores if s in ("PASS", "FAIL", "WAITING")]
    failed = len([s for s in counted if s == "FAIL"])
    waiting = len([s for s in counted if s == "WAITING"])
    return len(counted) - failed - waiting, failed, waiting


def _row_line(result: Result) -> str:
    """One row of the scoreboard.

    ⚠ **THE CELL NAMES PASSES, FAILURES *AND* WAITS SEPARATELY**, because a
    cell reading `6/11` in both columns looks identical whether the missing
    five are gaps or waits — and telling those two apart is the only reason
    there are two columns. `6P 2F 3W` and `6P 5F` say different things at a
    glance; `6/11` twice says nothing.
    """
    cells = []
    for column in (COLUMN_TODAY, COLUMN_LANES):
        passed, failed, waiting = _counted(result, column)
        mark = "RED " if failed else "GREEN"
        cell = f"{mark} {passed}P {failed}F" + (f" {waiting}W" if waiting else "")
        cells.append(cell)
    return f"  {result.scenario.id:<5} {result.scenario.title[:54]:<54} " + "  ".join(
        f"{cell:<18}" for cell in cells
    )


@pytest.fixture(scope="module", autouse=True)
def report() -> Any:
    """Prints the whole table once, after the last row. Run with `-s`."""
    yield
    if not RESULTS:
        return
    order = {row.id: index for index, row in enumerate(SCENARIOS)}
    rows = sorted(RESULTS, key=lambda r: order.get(r.scenario.id, 999))
    # ⚠ **A ROW THAT NEVER REPORTED IS NOT A ROW THAT PASSED**, and the report
    # must not divide by the rows it happened to receive. A scenario whose
    # FIXTURE raises never reaches `RESULTS`, so counting `n of len(rows)` is
    # hard-won law 7's *reporting zero over a scope it silently excludes* — in
    # a scoreboard, where it reads as a smaller denominator and nothing else.
    reported = {result.scenario.id for result in rows}
    never_ran = [row.id for row in SCENARIOS if row.id not in reported]

    def complete(column: str) -> list[Result]:
        """**COMPLETE means no failure AND nothing left unasserted.**

        ⚠ A row with a check still WAITING is not complete in the TODAY column,
        even though every check that was scored passed. Counting it green would
        report a scenario as working on the strength of the dimensions that are
        not what it is about.
        """
        out = []
        for result in rows:
            passed, failed, waiting = _counted(result, column)
            if failed == 0 and waiting == 0:
                out.append(result)
        return out

    lines: list[str] = []
    add = lines.append
    add("")
    add("═" * 78)
    add("  THE PROPERTY-SALE SCENARIO SUITE — 25 scenarios, one table, two columns")
    add("═" * 78)
    add("")
    add("  PO, 2026-09-20, verbatim:")
    add('    "once you are done with changes for tranfer - do the end to end walk -')
    add('     create request , see all transfer work corectly - property, address,')
    add('     assets, units - occupancy is updated at unit . assets whow correct')
    add('     account - money part is correct, email, communcation is send"')
    add("")
    add(f"  {'':5} {'':54} {'TODAY':<18}  {'WHEN THE LANES LAND':<18}")
    add("  " + "─" * 74)
    group = None
    for result in rows:
        if result.scenario.group != group:
            group = result.scenario.group
            add(f"  ── {group} " + "─" * (70 - len(group)))
        add(_row_line(result))
    add("  " + "─" * 74)
    today_ok = complete(COLUMN_TODAY)
    lanes_ok = complete(COLUMN_LANES)
    # ⚠ **TWO NUMBERS FOR TODAY, BECAUSE THEY ANSWER TWO QUESTIONS.** A row
    # with no failure and one check still WAITING is NOT complete — counting it
    # green would report a scenario as working on the strength of the
    # dimensions that are not what it is about — but it is also not broken, and
    # a single `0 of 25` cannot say that. So both are printed.
    no_failures = [
        result for result in rows if _counted(result, COLUMN_TODAY)[1] == 0
    ]
    add(f"  NO FAILURE TODAY:              {len(no_failures)} of {len(SCENARIOS)}"
        "   — nothing red, though some checks are still waiting")
    add(f"  COMPLETE TODAY:                {len(today_ok)} of {len(SCENARIOS)}"
        "   — no failure AND nothing left unasserted")
    add(f"  COMPLETE WHEN THE LANES LAND:  {len(lanes_ok)} of {len(SCENARIOS)}"
        "   — predicted, once the five keystones land")
    add("")
    add("  ⚠ The second number is a PREDICTION and is only as good as the keystones.")
    add("    What separates the two columns is the residue: every FAIL still standing")
    add("    in the right-hand column is a gap NO LANE IN FLIGHT TOUCHES.")
    if never_ran:
        add("")
        # ⚠ **IT NAMES BOTH CAUSES BECAUSE IT CANNOT TELL THEM APART**, and
        # saying only one of them was this report's own version of law 7's
        # *a check's output must distinguish pass from fail to a READER*: the
        # first draft asserted *"their fixture raised"*, which is a claim this
        # fixture has no way to make — a `-k` filter deselects rows and they
        # reach `RESULTS` exactly as a crashed one does, so a perfectly healthy
        # filtered run printed twenty-two scenarios as broken. Found by running
        # the committed runner on three named rows.
        add(f"  ⚠ {len(never_ran)} SCENARIO(S) NEVER REPORTED — either this run was")
        add("    FILTERED (`-k`, or the runner given row names), or their fixture raised")
        add("    before the walk began. This report cannot tell those apart, so it says")
        add("    both: on a filtered run these are simply the rows you did not ask for,")
        add("    and on a whole run they are NOT a pass and are in NEITHER column.")
        add(f"      {', '.join(never_ran)}")
    add("")

    # ── the crashes, named together rather than counted as 15 failures ──────
    crashes: dict[str, list[str]] = {}
    for result in rows:
        for note in result.notes:
            if note.startswith("⛔ CRASHED: "):
                crashes.setdefault(note[len("⛔ CRASHED: "):][:160], []).append(
                    result.scenario.id
                )
        check = next((c for c in result.checks if c.dimension == "outcome"), None)
        if check and check.verdict == "FAIL" and "Error:" in check.detail:
            crashes.setdefault(
                check.detail.split("saw 'refused' — ")[-1][:160], []
            ).append(result.scenario.id)
    if crashes:
        add("  ⚠ CRASHES — a row that RAISES is not a row that refuses, and these are")
        add("    counted ONCE here rather than as one failure per row they reach:")
        for message, ids in sorted(crashes.items()):
            add(f"      · {message}")
            add(f"        reached by {len(set(ids))} scenario(s): {', '.join(sorted(set(ids)))}")
        add("")

    # ── what each red row is waiting for ───────────────────────────────────
    add("  WHY A ROW IS NOT COMPLETE TODAY")
    add("  " + "─" * 74)
    for result in rows:
        gaps = result.failed(COLUMN_TODAY)
        waits = result.waiting()
        if not gaps and not waits:
            continue
        add(f"    {result.scenario.id} · {result.scenario.title[:62]}")
        for check in gaps:
            add(f"        ✗ GAP     {check.dimension}: {check.detail[:150]}")
        for check in waits:
            keystones = sorted({k for k in check.failed.values() if k})
            add(f"        ⏳ WAITING {check.dimension} → {', '.join(keystones)}")
            add(f"                  {check.detail[:150]}")
    add("")

    # ── the keystones, counted ─────────────────────────────────────────────
    add("  THE KEYSTONES, AND HOW MANY CHECKS EACH ONE HOLDS UP")
    add("  " + "─" * 74)
    held: dict[str, int] = {key: 0 for key in KEYSTONES}
    for result in rows:
        for check in result.checks:
            for keystone in check.failed.values():
                if keystone:
                    held[keystone] = held.get(keystone, 0) + 1
    for key in KEYSTONES:
        add(f"    {key:<48} {held.get(key, 0)} check(s)")
    add("")

    # ── friction ───────────────────────────────────────────────────────────
    frictions: dict[str, set[str]] = {}
    for result in rows:
        for item in result.friction:
            frictions.setdefault(item, set()).add(result.scenario.id)
    if frictions:
        add("  FRICTION — what the product DOES do that costs a clerk something")
        add("  " + "─" * 74)
        for item, ids in sorted(frictions.items(), key=lambda kv: -len(kv[1])):
            add(f"    · ({len(ids)} row(s)) {item}")
        add("")

    # ── the blind spots, printed rather than rounded up ────────────────────
    add("  ⚠ WHAT THIS SUITE DID NOT CHECK — printed on every run (hard-won law 7)")
    add("  " + "─" * 74)
    for entry in UNTESTABLE:
        add(f"    {entry['id']} · {entry['what']}")
        for chunk in _wrapped(entry["why"], 70):
            add(f"        {chunk}")
    add("")
    silent = [
        (result.scenario.id, check.dimension, check.detail)
        for result in rows
        for check in result.checks
        if check.verdict == "SILENT"
    ]
    add(f"  DECLARED NON-ASSERTIONS: {len(silent)} — each one printed, none hidden")
    for scenario_id, dimension, why in silent:
        add(f"    {scenario_id} · {dimension}: {why}")
    add("")
    add("═" * 78)

    text = "\n".join(lines)
    print(text)
    target = os.environ.get("TRANSFER_REPORT")
    if target:
        try:
            Path(target).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:  # pragma: no cover — reported, never swallowed
            print(f"  (the report could not be written to {target}: {exc})")


def _wrapped(text: str, width: int) -> list[str]:
    words = text.split()
    out: list[str] = []
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out
