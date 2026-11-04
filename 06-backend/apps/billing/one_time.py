# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the ad-hoc single bill — the kind select's default and
#           this module's own shape) · US-BIL-010 (first bill) · US-BIL-011
#           (final bill) · US-BIL-013 (back-bill) · US-BIL-014 (penalty/theft)
#           Screens: S30 (One-time bill tab) · S31 (single-account mode)
# Rules:    BR-BIL-020 (ad-hoc single bill = the bulk wizard in single-account
#           mode: preview → exceptions → draft → issue; lines come ONLY from
#           rules and charge codes — free-typed amounts never exist on any
#           bill) · BR-BIL-023 (computed amounts are NEVER hand-editable) ·
#           BR-BIL-012 (first bill: prorated from move-in + the one-time lines) ·
#           BR-BIL-013 (final bill: deposit applies FIRST, then exactly ONE
#           settlement path) · BR-BIL-018 (back-bill: per-sub-period tariff
#           versions, the tenant window cap, theft EXEMPT) · BR-BIL-019 (penalty
#           bills: charge-code lines only) · BR-BIL-005 (a run is idempotent) ·
#           BR-BIL-004 (a draft is not money) · BR-BIL-050 (the run row is what
#           every later phase hangs off) · BR-TEN-043 (event-time law — no clock
#           in this file) · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) ·
#           rule 7 (every money action writes audit_log)
# Tests:    06-backend/tests/test_us_bil_012_one_time.py
# Impacts:  apps/billing/api.py (the two routes S30's One-time tab calls) ·
#           07-frontend OneTimeBillTab.tsx, which renders exactly this
# ───────────────────────────────────────────────────────
"""S30's One-time bill tab: ONE door, five engines, and no second pricing path.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file WRITES a `bill_runs` row and
mints its idempotency key (CLAUDE.md 🔒 idempotency keys), and every bill in
this product that is not part of a cycle run passes through it. AI-authored
2026-08-16 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). Row in 12-governance/09-human-review-ledger.md.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE IS, AND THE ONE THING IT IS NOT
────────────────────────────────────────────────────────────────────────────
It is a ROUTER and a run-row writer. It resolves which of the five engines a
clerk's chosen KIND belongs to, gives that engine the lawful `bill_runs` row it
has always required, and hands its answer back. **It prices nothing.** There is
no arithmetic in this file at all, and that is load-bearing rather than tidy:
every figure in B4/B5 is frozen once, and a "simple" second path for one-off
bills is exactly how a tenant discovers that their interim bills round
differently from their cycle bills. `single.py` states the same rule about
itself; this module is one level up and keeps it.

The five engines shipped complete and TESTED on 2026-08-11 and 2026-08-15 and
were reachable from nothing but their own test files until this file existed —
hard-won law 2, five times over, in the module that decides what a customer
owes.

────────────────────────────────────────────────────────────────────────────
THE FIVE KINDS, AND WHY THE SELECT OFFERS THESE AND NOT THE PROTOTYPE'S FOUR
────────────────────────────────────────────────────────────────────────────
`05-prototype/UtilityBilling.html:3376` offers four: *Interim (mid-cycle
catch-up)* · *Final (move-out)* · *Catch-up (missed cycles)* · *Deposit
invoice*. The diff, in both directions (law 6):

  * **Interim → `interim`** (US-BIL-012). The prototype's own default and this
    module's. Produces a `cycle`-typed document, because an interim bill is an
    ordinary bill over an unusual window — nothing about its LINES differs.
  * **Final → `final`** (US-BIL-011). Kept verbatim.
  * **Catch-up → `backbill`** (US-BIL-013). Kept, and it is the kind whose
    inputs the prototype gets wrong — see SUB-PERIODS below.
  * **Deposit invoice → NOT BUILT.** No story in EP-BIL-03 owns it (hard-won
    law 8: every screen needs a story). `single.py` reported the same absence
    before this file existed. It is not silently dropped: the tab names it as
    unbuilt, so a clerk looking for it learns why rather than concluding the
    product forgot.
  * **First bill → `first`** (US-BIL-010), which the prototype does NOT offer
    and which belongs here. A cycle run marks a first bill automatically for
    accounts whose move-in falls inside its period; an account that moved in
    and was MISSED by that run has no other door.
  * **Penalty / theft → `penalty`** (US-BIL-014), which the prototype also does
    not offer. `penalty.py`'s own Trace header places it: *"S30 One-time bill
    tab with a theft reason"*.

**`first` IS STILL DERIVED, NOT DECIDED BY THE CLERK** (US-BIL-010 TC-6). The
kind select is the clerk saying *"this customer moved in during this window"*;
`first_bill.calculate_first_bill` then CHECKS that against the account's own
`opened_at` and refuses by name when it is not true. The clerk expresses an
intent, the account's data decides. A kind that no data had to agree with would
be a deposit and a connection charge placed on a bill by a dropdown.

────────────────────────────────────────────────────────────────────────────
SUB-PERIODS: WHY A BACK-BILL TAKES A LIST AND NOT "A PERIOD"
────────────────────────────────────────────────────────────────────────────
Four of the five kinds bill ONE window. A back-bill (and therefore a penalty
bill, which is priced by the same pass) takes the LIST of unbilled periods it
is recovering, and `backbill.py` refuses to invent one:

    "`cycles` is a single window with no recurrence rule (B2), so 'the six
     months Jan–Jun' cannot be derived from anything in this database … A
     default of 'the whole window as one group' would be the worst possible
     guess: 18 kgal of water priced as ONE period puts 13 kgal in the top tier
     (104.50) where six monthly groups put 6 (79.50)."

That is **$25.00 of a customer's money** on one service on one bill, and it is
invisible — the bill foots either way. So the screen collects the periods and
this module passes them through untouched. It does not helpfully split a span
into months, because "monthly" is a cadence nothing in this database states.

────────────────────────────────────────────────────────────────────────────
NO CHARGE-LINE EDITOR. THE ENFORCEMENT IS STRUCTURAL
────────────────────────────────────────────────────────────────────────────
The prototype's step 2 (`:3394-3400`) renders every line as an EDITABLE
description input and an EDITABLE amount input, with a **+ Add line** button
beneath. **BR-BIL-020 supersedes that, in writing:** *"lines come ONLY from
rules and charge codes — free-typed amounts never exist on any bill"*, and
BR-BIL-023 adds *"computed amounts NEVER hand-editable"*.

`single.py` makes that structural in its own layer — no function there takes an
amount, a description or a line — and this module keeps the property: **no
function in this file accepts an amount, a description or a line either.** There
is no parameter to pass one to. A rejection can be deleted by a later refactor;
a missing parameter cannot be passed by accident.

⚠ **`charge_code` (2026-09-15, `CR-108` wave 1) DOES NOT WEAKEN THAT AND IS THE
CASE THE RULE ALWAYS ALLOWED.** BR-BIL-020's own words are *"lines come only
from RULES and CHARGE CODES"*, so naming a code is how a clerk charges a fee
lawfully: the tenant's row carries the figure (BR-BIL-007), and a utility
entitled to charge $95.00 for a reconnection gets $95.00 because their row says
so. There is still nowhere in this module to put an amount. The blueprint states
the same thing on the screen: *"The amount is the code's. Pick a different code
to charge a different amount."*

────────────────────────────────────────────────────────────────────────────
⚠ A READING TYPED ON STEP 2 IS **METERING'S** WRITE, AND THIS MODULE HAS NONE
────────────────────────────────────────────────────────────────────────────
The blueprint is explicit (p101, p103–p104): *"Step 2 may collect a reading;
billing may never store one… a reading typed on step 2 **posts to Meter Reads'
own endpoint**, and the bill prices only once the reading exists there. **One
fact, one owner** — a second home for a reading is the defect class this
document keeps finding."*

**THAT ENDPOINT ALREADY EXISTS AND NOTHING HERE MAY GROW A SECOND ONE.** One
reading goes through the three routes a 1,247-row file goes through, with a
`rows` list of length ONE:

    POST /read-batches                 → `metering.services.stage_read_batch`
    POST /read-batches/{id}/validate   → all sixteen VEE rules, unchanged
    POST /read-batches/{id}/post       → BR-MET-017's stamp, BR-MET-018's key

`apps/metering/quick_read.py` — the S28 counter modal, sanctioned by the PO on
2026-08-26 — is built on exactly that and says why in its own words: *"What the
modal must NOT become is a second way for a reading to reach `meter_reads`… a
second write path for reads would be a second place for the rules to be wrong,
and the rules are the sixteen the whole product bills off."* So the counter read
is as validated, as audited, as idempotent and as correctable as a file row.
`GET /reads/quick-context` is the one read a capture surface needs first: is
this meter simple enough to take a single number.

**MEASURED 2026-09-15, not assumed:** thirteen `/reads` routes exist and none of
them creates a reading, which reads as an absence until the batch path is
found — `tests/test_cr038_w5_bulk_and_quick.py` walks a single row through all
three and asserts it lands `committed`, with its batch stamp and its unit.
Billing gains no write here, now or later.

────────────────────────────────────────────────────────────────────────────
⚠ WHERE A CYCLE-LESS BILL'S DUE DATE COMES FROM — RULED 2026-08-23 (D8③)
────────────────────────────────────────────────────────────────────────────
This module drafts; issuing is `POST /billing/runs/{id}/issue` (US-BIL-005).
Until 2026-08-23 a one-time bill could not pass it at all, and the reason was
written here rather than discovered later:

BR-BIL-024: *"Due date = bill date + **the cycle's** due-days"*. `due_days`
existed in exactly one place in the schema — `cycles.due_days` — and a one-time
run has no cycle (that is the whole point of migration 0021), so
`issue.derive_due_date` refused by name and the tab could draft a bill nobody
could send. **OQ-241 asked the Product Owner where the terms come from.**

**THE ANSWER, verbatim:** *"③ what due date a cycle-less one-time bill gets - it
will be capture at the time of bulk billing - not here"*. So the RUN carries
`bill_date` and `due_days` (the D9 column RC-W1 added), `issue._due_terms_for`
resolves run-then-cycle and finds them, and the bill issues on the terms the
clerk captured.

**NOTHING HERE GUESSES ONE, AND THAT HAS NOT CHANGED.** With no typed terms the
derivation still refuses by name: the three available guesses are each a real
number on a real customer's bill — the tenant's most common cycle (wrong for
anyone not on it), thirty days (a figure no signed document contains), or the
period end (which would make a back-bill overdue before it was printed). What
the ruling supplied is somewhere for the clerk's own answer to live.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from apps.billing import (
    backbill,
    customers_seam,
    final_bill,
    first_bill,
    gather,
    models,
    penalty,
    posting_seam,
    runs,
    single,
)
from apps.billing.exceptions import BillingRuleError
from core import audit, idempotency
from core import tenancy as core_tenancy

# ── the kind vocabulary the tab offers ──────────────────────────────────────
#: US-BIL-012 — the prototype's *"Interim (mid-cycle catch-up)"*. An ordinary
#: bill over an unusual window, so the DOCUMENT is typed `cycle`: nothing about
#: its lines differs, and typing it otherwise would mislabel a document kept for
#: seven years.
KIND_INTERIM = "interim"
#: US-BIL-010. The account's move-in must fall inside the period; the engine
#: checks it (TC-6) and this module does not.
KIND_FIRST = "first"
#: US-BIL-011 — the prototype's *"Final (move-out)"*.
KIND_FINAL = "final"
#: US-BIL-013 — the prototype's *"Catch-up (missed cycles)"*. Takes SUB-PERIODS.
KIND_BACKBILL = "backbill"
#: US-BIL-014. Takes sub-periods too, and a reason code; cap-exempt (BR-BIL-018).
KIND_PENALTY = "penalty"
#: DEF-708's `fee` bill, given the door it never had (`CR-108` wave 1, the
#: Billing blueprint's screen 22.6). `apps/billing/fee_bill.py` shipped complete
#: and TESTED on 2026-08-27 with exactly ONE caller —
#: `customers.disconnects.commit_cut` — so a reconnection fee could be charged
#: at a cut and nothing else could be charged at all. The blueprint states the
#: cost of that in one sentence (p102): *"This is the only door to charging any
#: live code to one account — a returned cheque, a tamper charge, a meter test.
#: Without it every new fee needs a new journey."* That is hard-won law 2 in the
#: module that decides what a customer owes: a complete engine reachable from
#: one place.
#:
#: ⚠ **A FEE HAS NO USAGE, NO READING AND NO PLAN**, which is why it is the one
#: kind whose step 2 collects a CODE rather than a window — the blueprint greys
#: three of its five groups with *"Not asked, and that is not an omission"*.
KIND_FEE = "fee"

ONE_TIME_KINDS = (
    KIND_INTERIM,
    KIND_FIRST,
    KIND_FINAL,
    KIND_BACKBILL,
    KIND_PENALTY,
    KIND_FEE,
)

#: kind → the `invoices.bill_type` (r10 #12) the document carries. `interim`
#: maps to `cycle` and the other five to themselves — see KIND_INTERIM.
BILL_TYPE_BY_KIND: dict[str, str] = {
    KIND_INTERIM: "cycle",
    KIND_FIRST: "first",
    KIND_FINAL: "final",
    KIND_BACKBILL: "backbill",
    KIND_PENALTY: "penalty",
    KIND_FEE: "fee",
}

#: The kinds whose whole bill IS a charge code, so the CODE is the one thing
#: step 2 collects. A set, for `SUB_PERIOD_KINDS`' reason: the API layer and the
#: screen agree about which form to draw without either re-deriving it.
#:
#: ⚠ **A CODE IS NOT AN AMOUNT AND BR-BIL-020 IS UNTOUCHED.** The clerk picks
#: which of the tenant's own charge codes to raise; the tenant's row carries the
#: figure (BR-BIL-007) and there is still no member of `OneTimeRequest` that a
#: caller could put money in. The blueprint says the same on screen: *"The
#: amount is the code's. Pick a different code to charge a different amount."*
CHARGE_CODE_KINDS = (KIND_FEE,)

#: The two kinds priced per sub-period against the tariff version in force THEN
#: (BR-BIL-018/019). Named as a set so the API layer and the screen agree about
#: which form to collect without either of them re-deriving it.
SUB_PERIOD_KINDS = (KIND_BACKBILL, KIND_PENALTY)

#: Kinds that REQUIRE a reason code — BR-BIL-018 *"reason-coded"*, and
#: BR-BIL-019 inherits it. Charging a customer for a period they were never
#: billed for is a decision somebody made for a reason, and the bill is the only
#: place that reason survives.
REASON_CODE_KINDS = (KIND_BACKBILL, KIND_PENALTY)

#: What the One-time tab CANNOT do, stated on the screen rather than left as an
#: absence a clerk has to infer. Each row is a real capability with a real
#: reason; none is a placeholder.
ONE_TIME_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ **REMOVED 2026-08-23 — `one_time_bill_cannot_be_issued_yet` (CR-029
    # D8③).** It said a one-time bill drafts and cannot be issued, because
    # BR-BIL-024's due-days had nowhere to come from without a cycle (OQ-241).
    # The PO ruled where they come from — *"it will be capture at the time of
    # bulk billing"* — and `create_one_time_run(due_days=…)` is that capture, so
    # the limit no longer exists and the sentence would now be false. A stated
    # absence outlives its subject faster than anything else in this repo, which
    # is why it is deleted with its reason rather than reworded (hard-won law 1).
    {
        "code": "partial_window_charges_a_full_base_charge",
        "br_ref": "B4.3 ❄️ · CR-029 D8④ (OQ-242 WITHDRAWN for catch-up, penalty and fee; "
        "CLOSED option (a) for interim, PO 2026-10-01, BR-BIL-1066)",
        "detail": "a catch-up, penalty or fee bill over a window SHORTER than "
        "the customer's cycle charges a FULL period's base charge. B4.3 prorates by "
        "`service_days / cycle_days` and a cycle-less run has no cycle length to divide "
        "by, so the factor is 1. On WE-6's own figures a 20-day window's three base "
        "charges come to $38.00 where a 31-day denominator gives $24.51 — $13.49 too "
        "much, on a bill that foots either way. Nothing is guessed: B4.3 is frozen and "
        "the missing part is its INPUT. The Product Owner WITHDREW the question on "
        "2026-08-23 (CR-029 D8④, 'this is not required'), so no proration rule is built "
        "for those kinds and the factor stays 1 — the behaviour above is the product's "
        "answer, not a pending one. FIRST, FINAL and INTERIM bills are the exceptions and "
        "are NOT covered by this sentence: each prorates its base charge over the "
        "account's own cycle length (final since 2026-09-20, first since 2026-09-30, "
        "interim since the PO's ruling of 2026-10-01 — 10/30 × $30.50 = $10.17). Usage "
        "lines are unaffected.",
    },
    {
        "code": "deposit_invoice_kind_has_no_story",
        "br_ref": "hard-won law 8",
        "detail": "the prototype's step-1 kind select offers a fourth option, 'Deposit "
        "invoice', and no story in EP-BIL-03 owns it. Not built and not invented — a "
        "screen without a story is how S1 shipped half-missing for a week.",
    },
    # ⚠ **REMOVED 2026-09-15 — `penalty_charge_code_line_cannot_be_priced`
    # (`DEF-BIL-5317`).** It told every clerk on the One-time tab that a penalty
    # bill's charge-code line *"cannot be added"*. That was true when it was
    # written and stopped being true on 2026-08-27, when `DEF-708` gave
    # `fee_bill.charge_code_line` the tenant's `charge_by_code` read; `penalty`
    # alone went on refusing because it named the seam as a module constant.
    # The line is built and billed now — `TAMPER` is **$250.0000** on every
    # provisioned tenant (PO ruling 2026-08-10, a platform default) and reaches
    # the bill as a non-taxable fee — so the sentence would be false on screen.
    #
    # It is DELETED WITH ITS REASON rather than reworded, which is what this
    # list did for `one_time_bill_cannot_be_issued_yet` above and for the same
    # argument: **a stated absence outlives its subject faster than anything
    # else in this repo** (hard-won law 1), and the mirror of dead UI is a live
    # capability behind a sentence that says it does not exist (law 2's other
    # direction, `DEF-CWP-3925`). Leaving a reworded row would keep a clerk from
    # trying the thing that now works.
    # ⚠ **REMOVED 2026-09-30 — `a_fee_bill_charges_no_tax_on_a_taxable_charge_code`
    # (`DEF-BIL-8153`).** It told every clerk that a fee bill raised from a
    # charge code marked TAXABLE *"still charges $0.00 of tax"* and that the
    # question was OPEN. Both halves stopped being true the same day: `OQ-812`
    # was ruled (PO *"yes"*), the ❄️ B4.2 addendum was re-signed (PO *"Yes,
    # re-sign."*, RECON $75.00 at 8.25% → **$81.19**), and the fee-tax lane
    # built it (`fee_bill.price_charge_fee` → the engine's `price_fee_bill`).
    # The decision log row that recorded the ruling said this key *"retires
    # when built"*; it was built and the key stayed. DELETED WITH ITS REASON,
    # the way `penalty_charge_code_line_cannot_be_priced` above was, for the
    # same argument — a live capability behind a sentence saying it does not
    # exist keeps a clerk from trusting the tax the bill now charges.
)


@dataclass(frozen=True)
class OneTimeRequest:
    """One clerk's answers from step 1 — WHO, WHEN, and WHICH KIND. Nothing else.

    ⚠ **THERE IS NO `amount`, NO `description` AND NO `lines` MEMBER, AND THAT
    IS THE ENFORCEMENT OF BR-BIL-020** — not a validation that could be removed
    but a field that does not exist. A caller cannot hand-type money onto a bill
    through this module because there is nowhere to put it.

    `sub_periods` is empty for the three single-window kinds and REQUIRED for
    the two that price per sub-period. `period_start`/`period_end` are then
    DERIVED from the list (min start, max end) rather than asked for twice —
    two sources for one window is a drift waiting to happen.

    ⚠ **ONE NARROW EXCEPTION, `entered_amount` (`DEF-RAT-8753`, 2026-10-01).**
    A charge code priced *entered when used* (`amount_rule = per_case` —
    CR-010 A2, PO 2026-08-17: *"actual cost, entered per case"*) states no
    price, so the clerk's figure IS its price. `fee_bill.charge_code_line`
    refuses the member beside any other code, so BR-BIL-020 still holds for
    every code that states its own price.
    """

    account_id: str
    kind: str
    period_start: date | None = None
    period_end: date | None = None
    bill_date: date | None = None
    #: CR-029 D8③ — the due-days the BULK BILLING captures for a bill that has
    #: no cycle to take them from. `None` means nobody typed any, and the bill
    #: then drafts and cannot be issued, which is BR-BIL-024 refusing by name
    #: rather than a guessed due date starting a late-fee clock.
    due_days: int | None = None
    sub_periods: tuple[tuple[date, date], ...] = ()
    reason_code: str = ""
    #: KIND_FEE only — WHICH of the tenant's own charge codes is being raised
    #: (BR-BIL-007: a CODE, never an amount). The tenant's row carries the
    #: figure, so this member adds a choice and adds no way to type money: an
    #: unknown code, a retired one, a percent rule with no basis and a code with
    #: no GL account are each refused BY NAME rather than charged as zero —
    #: *"a fee that quietly prices at nothing is a fee nobody notices was never
    #: charged"* (the blueprint, p114).
    charge_code: str = ""
    #: DEF-RAT-8753 — KIND_FEE with a `per_case` code only: the amount the
    #: clerk entered for this case. Refused beside any other code.
    entered_amount: Decimal | None = None
    scope_services: tuple[str, ...] | None = None
    #: US-BIL-010 only — the tenant's connection-charge CODE (BR-BIL-007: a code,
    #: never an amount). None means "do not add a connection charge"; the value
    #: is looked up in the tenant's catalogue and refused if it is not live.
    connection_charge_code: str | None = first_bill.DEFAULT_CONNECTION_CHARGE_CODE
    #: ── THREE WORDS A CLERK CHOSE OR TYPED, RECORDED ON THE DRAFT (build plan
    #: DB2, DB3 · contract §6). None of them is money and none reaches any
    #: arithmetic — each lands in the draft's `bill_payload` as a record of what
    #: the clerk decided, frozen with the bill at issue (BR-BIL-030).
    #:
    #: KIND_FINAL only — the settlement path the clerk picked on step 2
    #: (`collect` · `payment_plan` · `transfer`, BR-BIL-013's staff choice).
    #: `final_bill.settle` still decides whether it is AVAILABLE for this
    #: remainder, and refuses by name when it is not. Empty = not chosen yet.
    settlement_path: str = ""
    #: KIND_PENALTY only — *what was found*, the evidence text (design §4).
    #: Photos are not stored: see `one_time_answer.ANSWER_UNAVAILABLE`.
    evidence: str = ""
    #: KIND_FEE only — the note printed on the bill beside the charge (design §4,
    #: *"code · name · amount · note"*).
    note: str = ""
    #: Contract §2 `readings` — values typed on step 2. The PREVIEW prices them
    #: as PROVISIONAL (`DEF-BIL-8300`, contract §2: *"values typed but not yet
    #: saved, priced as provisional"*) through metering's own overlay, and
    #: writes nothing. ⚠ **THE DRAFT READS THEM TOO SINCE `DEF-BIL-10067`
    #: (2026-10-12)** — this comment said it never did — but only to find the
    #: reading step 2's Continue SAVED in Meter Reads at that value, which it
    #: is then priced on (`saved_typed_reads`). A reading still reaches a bill
    #: only once it is saved through Meter Reads (`/read-batches`).
    #:
    #: 🔒 `DEF-BIL-8562` (2026-09-30) — ONE row shape the draft DOES read:
    #: `{"asset_id", "service", "role": "estimate"}`, the clerk asking for a
    #: meter with no reading in the window to be billed on the METER'S OWN
    #: ESTIMATE (`clerk_estimates`). It carries no value — the quantity is
    #: metering's (BR-MET-026), never typed — and issue saves it into Meter
    #: Reads as an estimated reading (`metering_seam.record_billed_estimates`,
    #: DEF-BIL-8280's path), so the next real read is trued up against it.
    readings: tuple[dict[str, Any], ...] = ()
    #: 🔒 `DEF-BIL-9076` — the services whose meter ROLLED OVER inside the
    #: period and whose rollover the clerk has ACCEPTED (PO 2026-09-30, changes
    #: rows 45–46: a rollover waits for a clerk). A service named here bills
    #: the whole period across the rollover; one not named is HELD by name
    #: (`possible_rollover`). Empty — accept nothing — on every other request.
    accepted_rollovers: tuple[str, ...] = ()


@contextmanager
def _rollover_answers(request: OneTimeRequest) -> Any:
    """`DEF-BIL-9076` — the clerk's accepted rollovers, as the answers the
    reads walk (`runs._answered`) already reads for the run's own Check."""
    accepted = {
        (str(request.account_id), str(code), runs.POSSIBLE_ROLLOVER): runs.ANSWER_ACCEPT
        for code in request.accepted_rollovers or ()
        if code
    }
    token = runs.open_answers(accepted) if accepted else None
    try:
        yield
    finally:
        if token is not None:
            runs.close_answers(token)


def _under_rollover_answers(fn: Any) -> Any:
    """`DEF-BIL-9076` — run `fn(request, …)` under the clerk's accepted
    rollovers, so the preview prices exactly what the draft will. A decorator
    (with `wraps`) rather than a wrapper function, so `preview`'s own source is
    still what `inspect.getsource` reads (`test_def_bil_7990`)."""

    @wraps(fn)
    def wrapped(request: OneTimeRequest, *args: Any, **kwargs: Any) -> Any:
        with _rollover_answers(request):
            return fn(request, *args, **kwargs)

    return wrapped


def checked_kind(raw: Any) -> str:
    """The kind, or a refusal naming the five. Never a default.

    Defaulting an unknown kind to `interim` would be the worst available
    behaviour: a clerk who asked for a FINAL bill and got an interim one has an
    account that closes with an unsettled deposit and nobody watching it.
    """
    kind = str(raw or "").strip()
    if kind not in ONE_TIME_KINDS:
        raise BillingRuleError(
            f"unknown one-time bill kind {kind!r}. The tab offers {ONE_TIME_KINDS}; the "
            "prototype's fourth option 'Deposit invoice' is not among them because no "
            "story owns it (hard-won law 8). A kind is never defaulted — a clerk who "
            "asked for a final bill and silently got an interim one leaves a closed "
            "account with an unsettled deposit.",
            br_ref="BR-BIL-020",
        )
    return kind


def checked_window(request: OneTimeRequest) -> tuple[date, date]:
    """The bill's whole window — stated for one kind, DERIVED for the other two.

    A sub-period kind derives it from the list it was given (min start, max end)
    so the run row and the groups can never disagree about what was billed.

    ⚠ **A FEE IS CHARGED ON A DAY, NOT OVER A WINDOW**, so its window is the
    bill date at both ends — `fee_bill.raise_charge_fee` already states it:
    *"a wider window would state a service period this charge never had"*. The
    date is the clerk's typed bill date and there is no second source for it,
    because two sources for one window is a drift waiting to happen; an absent
    one refuses BY NAME rather than being read off a clock (BR-TEN-043, gate
    G6). Nothing is prorated either way — B4.3 does not reach a fee.
    """
    if request.kind in CHARGE_CODE_KINDS:
        if request.bill_date is None:
            raise BillingRuleError(
                f"a {request.kind!r} bill is charged ON a day and needs the date it is "
                "charged on. That date is the bill date the clerk typed at step 1: it "
                "dates the document, it is both ends of its period, and it is what makes "
                "a second fee for the same customer on the same day a duplicate rather "
                "than a second charge (BR-BIL-005). Nothing here reads a clock for it "
                "(BR-TEN-043).",
                br_ref="BR-BIL-070",
            )
        return request.bill_date, request.bill_date
    if request.kind in SUB_PERIOD_KINDS:
        if not request.sub_periods:
            raise BillingRuleError(
                f"a {request.kind!r} bill is priced PER SUB-PERIOD against the tariff "
                "version in force at the time (BR-BIL-018), so it needs the list of "
                "periods being recovered — not one span. Nothing here splits a span into "
                "months: no recurrence rule exists in this database to split it BY, and "
                "18 kgal of water priced as one period puts 13 kgal in the top tier where "
                "six monthly groups put 6 — a difference of $25.00 on a bill that foots "
                "either way.",
                br_ref="BR-BIL-018",
            )
        return (
            min(start for start, _ in request.sub_periods),
            max(end for _, end in request.sub_periods),
        )
    if request.period_start is None or request.period_end is None:
        raise BillingRuleError(
            f"a {request.kind!r} bill needs both ends of its period. Every proration in "
            "B4.3 divides by this window and no end of it is defaulted.",
            br_ref="BR-BIL-020",
        )
    return request.period_start, request.period_end


def checked_reason_code(request: OneTimeRequest) -> str:
    """BR-BIL-018's *"reason-coded"*, checked before anything is written.

    ⚠ **CORRECTED 2026-09-30 (one-time bill build plan B13).** This read *"the
    reason-code lookup (r10 #13, tenant-extensible) has no table in this
    repository"*, and that was false: `tenancy.models.ReasonCode` is that table
    (`reason_codes` — code · name · is_system · active, S8 reference data,
    hosted by tenancy for billing). What is TRUE is narrower: **this function
    does not yet check the code against it** — it refuses the EMPTY code early,
    so a clerk is told at step 1 rather than after the run row exists, and
    accepts any non-empty one. Checking it against the tenant's ACTIVE rows is
    build-plan task A2, and belongs with the dropdown that will offer them.
    """
    if request.kind not in REASON_CODE_KINDS:
        return ""
    code = (request.reason_code or "").strip()
    if not code:
        raise BillingRuleError(
            f"a {request.kind!r} bill must carry a reason code (BR-BIL-018). Charging a "
            "customer for a period they were never billed for is a decision someone made "
            "for a reason, and the bill is the only place that reason survives.",
            br_ref="BR-BIL-018",
        )
    return code


def checked_charge_code(request: OneTimeRequest) -> str:
    """The charge code a fee bill IS, or a refusal. Never a default.

    Only the EMPTY code is refused here, early, so a clerk is told at step 2
    rather than after a run row exists. Whether the code is one of the tenant's,
    whether it is still live, whether it carries a flat price and whether it has
    a GL account are the four states `fee_bill.charge_code_line` refuses on, and
    they are left to it on purpose: this module has never held a second opinion
    about a money rule and a duplicate check here would eventually be the wrong
    one. **None of the five defaults.** A fee raised at a guessed amount lands
    on a document that can never be corrected (hard rule 4).
    """
    if request.kind not in CHARGE_CODE_KINDS:
        return ""
    code = (request.charge_code or "").strip()
    if not code:
        raise BillingRuleError(
            f"a {request.kind!r} bill is a charge code and nothing else, so it needs the "
            "code being raised. There is no amount to type and no default code to fall "
            "back on: the amount is the tenant's own, and a code chosen for them would "
            "charge somebody for something nobody picked.",
            br_ref="BR-BIL-007",
        )
    return code


# ── phase 1: look, and write nothing ────────────────────────────────────────


@_under_rollover_answers
def preview(request: OneTimeRequest, *, capture: dict[str, Any] | None = None) -> dict[str, Any]:
    """What this customer would owe — computed, returned, and NOT written.

    ⚠ **`capture` (2026-09-30, the one-time bill redesign's API lane).** When a
    dict is passed, the preview puts the objects it ALREADY built into it — the
    gathered account data (`"data"`) and the priced pass (`"priced"`) — so
    `one_time_answer` can shape the redrawn screen's answer from them without
    gathering or pricing a second time. It changes nothing this function
    returns and nothing it computes; `None` (every existing caller) behaves
    exactly as before.

    BR-BIL-020's *"preview → exceptions → draft → issue"*, first clause. The
    promise is the one `prepare_run` makes and for the same reason: the PO's
    flow looks before it commits, and a preview that wrote would make looking a
    committing action.

    Every kind's own prepare pass is called, so what the clerk sees is produced
    by the engine that will produce the bill — never by a lighter re-implementation
    that could disagree with it.

    ────────────────────────────────────────────────────────────────────────
    ⚠ IT NOW SERVES THE LINES AND THE MONEY — AMENDED `CR-108` WAVE 1
    ────────────────────────────────────────────────────────────────────────
    **THIS DOCSTRING AND `_account_body`'s USED TO SAY THE PREVIEW SERVED NO
    TOTAL, AND THE REASON THEY GAVE WAS SOUND WHILE IT WAS TRUE.** It was *"a
    figure here would either be a second arithmetic — the thing this whole
    module exists to avoid — or a zero standing in for 'not computed', which on
    a bill preview is a money claim"*. Both hazards are real and neither is
    present now, which is why the sentence is corrected rather than quietly
    dropped (hard-won law 1):

      * it is **not a second arithmetic**. `runs.price_account` is stages 1→5
        of the run's own `calculate_account`, extracted line for line by
        `CR-075` wave F precisely so that a figure could be shown without a
        draft; `calculate_account` IS `price_account` followed by stage 6. The
        four kinds that shape their data before pricing now do that in one
        place each — `first_bill.first_bill_data`, `backbill.price_back_bill`,
        `fee_bill.price_charge_fee` — and both the preview and the draft call
        it. The lines cannot differ, by construction rather than by assertion;
      * it is **not a zero standing in for not-computed**. Pricing that refuses
        answers `priced: false` with the engine's own reason, and no total at
        all. A screen therefore cannot render 0.00 over an account that was
        never priced.

    **NOTHING IS WRITTEN AND NO BILL NUMBER IS SPENT.** Stage 6 is where a draft
    is written and where `core.numbering` spends a number (BR-BIL-063), and it
    is not called on this path — the blueprint's own words for step 3, *"This is
    the first thing that writes"*, are about the button and not about this.

    **THE LINES ARE THE KIND'S.** There is no `amount` field and no parameter to
    pass one to; what is served is what the engine produced.

    ⚠ **BASIS IS THE SCREEN'S SENTENCE AND NOT THIS MODULE'S.** The blueprint
    draws a BASIS column — *"9 / 30 days"*, *"6.1 kgal, tiered"*, *"8.25%"* —
    and what is served here are the FACTS that sentence is made of: the
    quantity with its unit (rule 3), the unit price, the service, the tax the
    line belongs to and the window's two day counts. Composing the words here
    would put clerk-facing English in an API, which B14 rule 35 gives to the
    catalogue, and would put a second copy of it out of reach of translation.

    ⚠ **THE ONE THING THE PREVIEW DOES NOT REPRODUCE IS THE SNAPSHOT, AND IT IS
    SAID HERE SO THE NEXT READER DOES NOT READ IT AS A SECOND PATH.** A penalty
    bill's draft carries an `extra_snapshot` — the theft case's reason code, its
    cap exemption and the unverifiable-assessed flag — which `BR-BIL-030` locks
    at issue so a reprint in 2033 still says which reads could not be proved.
    The preview runs the identical pricing pass and passes no snapshot, because
    a snapshot is a record of a document and there is no document. **The LINES
    and the MONEY are byte-identical either way**; only the frozen payload of a
    bill that does not exist is absent.
    """
    kind = checked_kind(request.kind)
    period_start, period_end = checked_window(request)
    reason_code = checked_reason_code(request)
    charge_code = checked_charge_code(request)
    kept: dict[str, Any] = capture if capture is not None else {}
    keyed = provisional_reads(request)

    def _kept(pricing_pass: Any) -> Any:
        def run() -> Any:
            kept["priced"] = pricing_pass()
            return kept["priced"]

        return run

    body: dict[str, Any] = {
        "kind": kind,
        "bill_type": BILL_TYPE_BY_KIND[kind],
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        # `DEF-BIL-7990` — WHO, beside WHICH ACCOUNT. Set on the top-level body
        # rather than inside one kind's branch, because all six kinds answer
        # the same question and five different places would answer it five
        # ways. See `_customer_name`.
        "name": _customer_name(request.account_id),
        # `DEF-BIL-9787` — the PO the drafted bill will print (stage 6 stamps
        # the same column), so the preview shows it too. None: no PO named.
        "po_number": customers_seam.po_number_for(request.account_id),
        "unavailable": [dict(row) for row in ONE_TIME_UNAVAILABLE],
        # PO ruling 2026-09-30 — the named warnings of the bill this preview
        # would draft (contract §2). `[]` until a pricing pass answers; the
        # pass's own list replaces it in `_priced_body`.
        "warnings": [],
    }

    if kind in CHARGE_CODE_KINDS:
        body.update(_fee_body(request, charge_code=charge_code, on_date=period_start, kept=kept))
        return body

    if kind in SUB_PERIOD_KINDS:
        prepared = _prepare_sub_period_kind(
            request, kind=kind, reason_code=reason_code, keyed_reads=keyed, waiting_ok=True
        )
        back = prepared.back_bill if kind == KIND_PENALTY else prepared
        kept["data"] = back.groups[-1].data if back.groups else None
        body.update(_sub_period_body(prepared, kind=kind))
        # `DEF-BIL-8324` (PO 2026-09-30) — a stretch no reading measured and the
        # meter's history cannot estimate WAITS for step 2's reading, which is
        # used first; refusing here would stop step 1 before the clerk can type
        # it (`DEF-BIL-8300`'s shape). The draft still refuses without one.
        if any(_waits_for_a_reading(group.data) for group in back.groups):
            body.update(
                {
                    "priced": False,
                    "lines": [],
                    "priced_unavailable": {
                        "reason": runs.CALC_UNRESOLVED_READ,
                        "detail": "a meter has a stretch with no reading and no history yet",
                    },
                }
            )
            _add_books(body, kind=kind)
            return body
        body.update(
            _priced_body(
                _kept(
                    lambda: backbill.price_back_bill(
                        prepared.back_bill if kind == KIND_PENALTY else prepared,
                        bill_type=BILL_TYPE_BY_KIND[kind],
                        # `DEF-BIL-5317` — the preview must show the SAME lines the
                        # draft will write, charge-code line included, or a clerk
                        # approves one document and issues another. `charge_lines`
                        # was resolved by `prepare_penalty_bill` above and is empty
                        # for a back-bill, which has no such ingredient.
                        extra_fees=getattr(prepared, "charge_lines", ()),
                    )
                )
            )
        )
        _add_books(body, kind=kind)
        return body

    if kind == KIND_FINAL:
        # PO 2026-10-01 — no cycle, no final bill (*"same as first bill"*).
        refuse_a_bill_with_no_cycle(request.account_id, kind=kind)
        data = final_bill.prepare_final_bill(
            account_id=request.account_id,
            period_start=period_start,
            moved_out_on=period_end,
            cycle_days=_cycle_days(request),
            scope_services=request.scope_services,
            keyed_reads=keyed,
        )
        kept["data"] = data
        body.update(_account_body(data))
        # BR-BIL-013 — the deposit applies FIRST, so a clerk previewing a final
        # bill has to be shown it BEFORE they draft. It is read, never computed
        # here (BR-CUS-057 is customers' rule).
        #
        # ⚠ **`as_of` WAS MISSING HERE UNTIL `CR-108` WAVE 1, AND IT IS
        # `DEF-CWP-3842`'s SECOND SITE — `surface_debt.txt` names this file by
        # path for it**: *"the refusal is gone from the final-bill path,
        # `apps/billing/one_time.py` still calls it the old way"*.
        # `deposit_interest_accrued` answers None for a day nobody named,
        # deliberately (gate G6 keeps a wall clock off a money path), so
        # `deposit_credit_for` refused BY NAME for every interest-bearing
        # deposit and this row printed a sentence blaming an unreadable accrual.
        # The day is the MOVE-OUT DAY, read off the request and never off a
        # clock — `BR-CUS-056` and `prepare_final_bill` both put it there:
        # *"the OUTGOING account pays the move day, so `period_end` IS
        # `moved_out_on`"* — which is the day the deposit stops being held and
        # therefore the day the accrual ends. `settle_final_bill` passes exactly
        # this.
        body["deposit"] = _deposit_body(request.account_id, as_of=period_end)
        body.update(_priced_body(_kept(lambda: runs.price_account(data))))
        # BR-BIL-013's order, which is the rule and not a preference: the
        # deposit and its interest apply BEFORE any path is chosen, because the
        # remainder is what selects the path. So *Still due · to collect* can
        # only be computed once the charges are, and it is computed by
        # `final_bill` rather than here — a subtraction in this file would be a
        # second reading of the word *remainder*, and the two readings differ by
        # everything the customer already owed.
        settlement = _previewed_settlement(body, request, period_end=period_end)
        body["settlement"] = _settlement_preview_body(settlement)
        # ⚠ **THE SETTLEMENT OBJECT AND NOT THE SERIALISED DICT.** The books
        # panel takes the deposit and the closing position this pass already
        # resolved instead of resolving them again: a second
        # `deposit_credit_for(…)` inside one payload is how the *Deposit and its
        # interest, applied first* row and the *Deposit applied* entry come to
        # state different figures about the same customer's money on the same
        # screen. The `deposit` block above reads on the SAME day for the same
        # reason, so all three figures on this screen are one accrual.
        _add_books(body, kind=kind, settlement=settlement)
        return body

    if kind == KIND_FIRST:
        # `DEF-BIL-8330` — no cycle, no first bill (PO 2026-09-30, option A).
        refuse_a_first_bill_with_no_cycle(request.account_id)
        moved_in_on = first_bill_move_in(request, period_start)
        data = first_bill.prepare_first_bill(
            account_id=request.account_id,
            moved_in_on=moved_in_on,
            period_end=period_end,
            cycle_days=first_bill_cycle_days(request, moved_in_on, period_start, period_end),
            period_start=period_start,
            scope_services=request.scope_services,
            keyed_reads=keyed,
            # `DEF-BIL-8749` — a price change inside the window cuts it, each
            # part over the account's cycle on its own last day.
            cycle_days_for=_interim_part_cycle_days(request),
        )
        kept["data"] = data
        body.update(_account_body(data))
        body["moved_in_on"] = moved_in_on.isoformat()
        body["is_first_bill"] = first_bill.is_first_bill(
            moved_in_on=moved_in_on, period_start=data.period_start, period_end=data.period_end
        )
        # ⚠ `DEF-BIL-8300` ON A FIRST BILL. With no reading inside the window
        # yet, `first_bill_data` refuses as BR-BIL-062's *no prior read* — at
        # step 1, before the clerk can type the reading on step 2 (J70 re-walk,
        # Unit C). A metered service still waiting for its read is the
        # preview's WAITING case, answered with its reading rows; the draft is
        # untouched and still refuses without a saved reading.
        if _waits_for_a_reading(data):
            body.update(
                {
                    "priced": False,
                    "lines": [],
                    "priced_unavailable": {
                        "reason": runs.CALC_UNRESOLVED_READ,
                        "detail": "a metered service has no reading in the window yet",
                    },
                }
            )
            _add_books(body, kind=kind)
            return body
        # The deposit line and the connection charge are what make a first bill
        # different from an interim one, so the preview has to price the data
        # that CARRIES them — `first_bill_data`, the same function the draft
        # calls — rather than the bare prepared data.
        body.update(
            _priced_body(
                _kept(
                    lambda: runs.price_account(
                        first_bill.first_bill_data(
                            data,
                            moved_in_on=moved_in_on,
                            account_type_id=_account_type_id(request.account_id),
                            connection_charge_code=request.connection_charge_code,
                        )
                    )
                )
            )
        )
        _add_books(body, kind=kind)
        return body

    if kind == KIND_INTERIM:
        # PO 2026-10-01 — no cycle, no interim bill (`BR-BIL-1066`).
        refuse_a_bill_with_no_cycle(request.account_id, kind=kind)
    prepared = single.prepare_single_bill(
        account_id=request.account_id,
        period_start=period_start,
        period_end=period_end,
        # BR-RAT-007 prices on the SERVICE date. For an interim bill it is the
        # window's end — the last day of service being billed — and never a
        # clock (BR-TEN-043 / G6).
        service_date=period_end,
        # PO 2026-10-01 (`BR-BIL-1066`) — an INTERIM bill divides by the
        # account's own cycle; any other kind reaching here keeps `None`.
        cycle_days=(
            interim_bill_cycle_days(request, period_start, period_end)
            if kind == KIND_INTERIM
            else _cycle_days(request)
        ),
        scope_services=request.scope_services,
        bill_type=BILL_TYPE_BY_KIND[kind],
        keyed_reads=keyed,
        # CR-156-BRC10 — an interim window crossing a charge-code price change
        # is cut there, each part over its own cycle (`single.prepare_single_
        # bill`'s docstring carries the PO's worked $9.65).
        price_split_cycle_days=_interim_part_cycle_days(request) if kind == KIND_INTERIM else None,
    )
    if kind == KIND_INTERIM:
        prepared = _prepared_with_clerk_estimates(
            prepared, request, period_start=period_start, period_end=period_end
        )
    body.update(
        {
            "account_no": prepared.ready[0].account_no if prepared.ready else None,
            "ready": len(prepared.ready),
            # `DEF-RAT-7991` — a blocked row is the same 200-body shape as the
            # five below it and reached the same screen with the same uuids.
            "blocked": [_clerk_gap(problem, problem.reason) for problem in prepared.blocked],
            "decisions": [_clerk_gap(problem, problem.reason) for problem in prepared.decisions],
            "cycle_days": prepared.cycle_days,
        }
    )
    if prepared.ready:
        kept["data"] = prepared.ready[0]
        body.update(_account_body(prepared.ready[0]))
        body.update(_priced_body(_kept(lambda: runs.price_account(prepared.ready[0]))))
        _add_books(body, kind=kind)
    return body


#: 🔒 `DEF-BIL-8562` — the reading ROLE by which step 2 asks for a meter's own
#: estimate. The only role a DRAFT reads (see `OneTimeRequest.readings`).
ROLE_ESTIMATE = "estimate"


def clerk_estimates(request: OneTimeRequest) -> tuple[dict[str, str], ...]:
    """The meters the clerk asked to ESTIMATE on step 2 (`DEF-BIL-8562`)."""
    return tuple(
        {"asset_id": str(row.get("asset_id")), "service": str(row.get("service") or "")}
        for row in (request.readings or ())
        if isinstance(row, dict)
        and str(row.get("role") or "") == ROLE_ESTIMATE
        and row.get("asset_id")
    )


def with_clerk_estimates(
    data: Any, request: OneTimeRequest, *, period_start: date, period_end: date
) -> Any:
    """🔒 `DEF-BIL-8562` — an interim meter with no reading, billed on its OWN estimate.

    PO request 2026-09-30 (J74 case 2): *"an interim bill can estimate a meter
    with no reading on step 2 (the meter's own estimate, marked Estimated), as
    catch-up does"*. BR-BIL-015 names three answers to a missing read —
    estimate, hold, bill without — and the interim page offered none: a clerk
    with no September reading for Hannah Ortiz's one water meter could not bill
    September at all.

    The quantity is METERING's (`back_bill_segment_estimate`, BR-MET-026, the
    same seam the catch-up's never-read stretch uses — `backbill.
    _metering_estimate`), for exactly this window and meter; nothing is typed
    and nothing is computed here. The reading keeps `read_id=None` and is
    marked `estimated=True`, which is what makes stage 6 freeze it as an
    `estimate` on the bill and issue save it into Meter Reads (DEF-BIL-8280),
    the same as a bulk run's clerk estimate. A meter that already has a reading
    in the window is never estimated (a committed read always wins), and a
    meter metering will not estimate stays WAITING — the page still says so.
    """
    wanted = clerk_estimates(request)
    if not wanted or data is None:
        return data
    from apps.billing import rating_seam

    unit_id = single.billable_account(request.account_id).unit_id
    readings = list(getattr(data, "readings", ()) or ())
    changed = False
    for ask in wanted:
        for index, reading in enumerate(readings):
            if reading.consumption is not None:
                continue
            own = getattr(reading, "asset_id", None)
            if own and str(own) != ask["asset_id"]:
                continue
            if not own and reading.service_code != ask["service"]:
                continue
            quantity, unit, _reason = backbill._metering_estimate(
                unit_id,
                service_code=reading.service_code,
                period_start=period_start,
                period_end=period_end,
                asset_id=ask["asset_id"],
            )
            if quantity is not None:
                readings[index] = replace(
                    reading,
                    consumption=rating_seam.Quantity(amount=quantity, unit=unit),
                    estimated=True,
                    absent_reason=None,
                )
                changed = True
            break
    return replace(data, readings=tuple(readings)) if changed else data


def _prepared_with_clerk_estimates(
    prepared: Any, request: OneTimeRequest, *, period_start: date, period_end: date
) -> Any:
    """`prepare_single_bill`'s answer with step 2's estimates applied (`DEF-BIL-8562`)."""
    if not prepared.ready or not clerk_estimates(request):
        return prepared
    data = with_clerk_estimates(
        prepared.ready[0], request, period_start=period_start, period_end=period_end
    )
    # ── CR-156-BRC10 · A SPLIT INTERIM ESTIMATES EACH PART ON ITS OWN DAYS ──
    # When a price change cut the window (`price_split_cycle_days`), the bill is
    # priced from its SEGMENTS, so the clerk's estimate must reach each one —
    # metering's own estimate for that part's dates, never a share of the
    # whole typed by us. Without this the parts would price with no usage.
    segments = tuple(getattr(prepared.ready[0], "split_segments", ()) or ())
    if segments:
        data = replace(
            data,
            split_segments=tuple(
                replace(
                    segment,
                    data=with_clerk_estimates(
                        segment.data,
                        request,
                        period_start=segment.period_start,
                        period_end=segment.period_end,
                    ),
                )
                for segment in segments
            ),
        )
    if data is prepared.ready[0]:
        return prepared
    still_missing = {
        reading.service_code for reading in data.readings if reading.consumption is None
    }
    return replace(
        prepared,
        ready=(data,),
        decisions=tuple(
            problem
            for problem in prepared.decisions
            if getattr(problem, "service_code", None) in still_missing
        ),
    )


def _waits_for_a_reading(data: Any) -> bool:
    """True when a metered service in `data` has no usable read yet — the
    reason set `runs.price_account` refuses on (`CALC_UNRESOLVED_READ`), read
    off the same exemption list so the two cannot disagree (`DEF-BIL-8300`).

    ⚠ `DEF-BIL-9750` — WHETHER A READ WAS EVER OWED IS ASKED OF THE TARIFF,
    exactly as `backbill`'s `never_read` asks it (`DEF-BIL-5326`). Sewer priced
    as a share of water (BR-RAT-015) has no register, so metering's reading
    says `no_meter` — not on the exempt list — while the service is never
    measured. Read off the reading alone, every move-in starting sewer waited
    for ever. A consumption-priced service with no meter still waits."""
    from apps.billing.stages import measure_consumption as measure_consumption_stage

    not_in_service = set(getattr(data, "unconnected_services", ()) or ())
    never_read = {
        tariff.service
        for tariff in getattr(data, "tariffs", ()) or ()
        if measure_consumption_stage.prices_no_consumption(tariff)
        or measure_consumption_stage.bills_base_only(tariff)
    }
    return any(
        getattr(reading, "consumption", None) is None
        and getattr(reading, "asset_count", None) is None
        and reading.service_code not in not_in_service
        and reading.service_code not in never_read
        and getattr(reading, "absent_reason", None)
        not in measure_consumption_stage.EXEMPT_FROM_MISSING_READ
        for reading in getattr(data, "readings", ()) or ()
    )


def provisional_reads(request: OneTimeRequest) -> tuple[dict[str, Any], ...] | None:
    """Step 2's typed values in the shape metering's overlay reads — or None.

    ── `DEF-BIL-8300` (2026-09-30) · WHY THE PREVIEW PRICES WHAT WAS TYPED ──
    Step 1 asked for a preview and was refused *"missing read"* for every
    account whose meters had no reading in the period — while step 2 is where
    that reading is typed. The clerk could never reach it. Contract §2's
    request has always said the typed values are *"priced as provisional"*;
    the build echoed them and priced nothing.

    **Metering does the arithmetic, not this function** — `provisional_reads_
    for_unit` owns the factor, the prior register, the rollover branch and the
    negative-usage refusal, and writes nothing (the move-out wizard's
    `DEF-CUS-5931` path, PO *"option b is correct"*).

    ── 🔒 `DEF-BIL-10067` (2026-10-12) · THE TYPED READING WINS ON THIS BILL ──
    ⚠ **THIS DOCSTRING SAID *"A committed read in the period always wins over
    a typed one"*, AND THAT IS THE DEFECT.** It is metering's DEFAULT and the
    move-out wizard's rule, and it is the wrong rule here: the PO ruled for the
    one-time bill that *"the draft is priced on the reading entered"*, with the
    Readings table showing the full usage and the Rates table following it
    (decision log 2026-10-12). The walk: W-9011, previous 2.9 on 31 Aug, a
    committed 8.0 on 29 Sep, typed 4.6 — Readings said 1.7 kgal while the Rates
    table, step 3 and the draft priced 5.1. `DEF-BIL-10067`'s first fix carried
    the typed value into the SPLIT parts only, and water was no longer split.

    So every entry here carries `runs.KEYED_WINS_OVER_COMMITTED`: the typed
    value replaces a committed read in the period, for every service, split or
    not, counted from the dial the period opens at (2.9 → 4.6 = 1.7). Metering's
    default is untouched — the option is per entry, and only this bill sets it.
    A split service takes its parts as day shares of that 1.7
    (`midperiod._apportion_evenly_by_day`), never the typed reading beside a
    committed part.

    **THE DRAFT** prices from `saved_typed_reads` — the same entries, also
    asking for the reading step 2's Continue SAVED at that value, so the preview
    and the draft price one number and the draft names, and issue locks, the
    reading Meter Reads holds. See that function.

    One entry per meter: the `current` (or a catch-up's `last_period`) value,
    with a `move_in` value on the same meter carried as its `prior` — a first
    bill whose move-in reading is not on file. A blank value is not a zero and
    is dropped.
    """
    current: dict[str, str] = {}
    prior: dict[str, str] = {}
    for row in request.readings or ():
        if not isinstance(row, dict):
            continue
        asset_id = str(row.get("asset_id") or "").strip()
        value = str(row.get("value") or "").strip()
        if not asset_id or not value:
            continue
        if str(row.get("role") or "current") == "move_in":
            prior[asset_id] = value
        else:
            current[asset_id] = value
    if not current:
        return None
    return tuple(
        {
            "asset_id": asset_id,
            "value": value,
            **({"prior": prior[asset_id]} if asset_id in prior else {}),
            runs.KEYED_WINS_OVER_COMMITTED: True,
        }
        for asset_id, value in current.items()
    )


def saved_typed_reads(request: OneTimeRequest) -> tuple[dict[str, Any], ...] | None:
    """🔒 `DEF-BIL-10067` — what the DRAFT is priced from: step 2's typed
    readings, AS SAVED in Meter Reads.

    ── WHY THE SAVED READING, AND NOT THE TYPED STRING ─────────────────────
    Step 2's Continue posts every typed reading to Meter Reads before step 3
    (`OneTimeBillPage.saveReadings`), on the date of the row it was typed in —
    29 Sep, beside the committed 8.0. Two readings on one register and date is
    BR-MET-1189's case, and its rule (*"highest consumption"*) counts the 8.0,
    so a draft priced on Meter Reads' own choice billed 5.1 kgal for a screen
    that had shown 1.7. A draft priced on the bare typed string would price 1.7
    but name no reading, so issue would lock nothing — or the 8.0 it never used.

    So the draft asks metering for the reading Meter Reads HOLDS at exactly the
    typed value inside the period (`runs.KEYED_SAVED_ONLY`), prices on it the
    way the preview priced the typed value — 4.6 − 2.9 = 1.7, the same
    arithmetic over the same two dials, so **the preview total IS the draft
    total** — and names it, so issue locks the 4.6 and not the 8.0. A typed
    value that was never saved prices nothing: the row is absent and the draft
    refuses, exactly as `DEF-BIL-8300` ruled a draft refuses without a saved
    reading. The committed 8.0 is not billed and not locked by this bill; what
    happens to it next is the decision log's 2026-10-12 entry for this defect.
    """
    entries = provisional_reads(request)
    if entries is None:
        return None
    return tuple({**entry, runs.KEYED_SAVED_ONLY: True} for entry in entries)


# ── phase 2: the run row, then ONE draft bill ───────────────────────────────


def create(request: OneTimeRequest, *, run_by: Any = None, actor: Any = None) -> dict[str, Any]:
    """Mint the run, draft the bill, return both. The tab's one write.

    ── ORDER, AND WHY IT IS THIS ONE ────────────────────────────────────────
    The run row is written FIRST and the draft second, inside one transaction.
    A draft with no run would have nowhere to hang (stage 6 keys replacement on
    `(tenant, account, bill_run)`), and a run whose draft failed rolls back
    with it — so a refused bill leaves no orphan row occupying the idempotency
    key that the clerk's corrected second attempt needs.

    ── BR-BIL-005 IS THE POINT OF THE RUN ROW, NOT A SIDE EFFECT ────────────
    A clerk who double-clicks *Create bill* on a move-out gets ONE final bill
    and a refusal naming the first, with who ran it and when. Without the key
    they would get two final bills for one tenancy, and a final bill is the one
    nobody checks afterwards.
    """
    kind = checked_kind(request.kind)
    period_start, period_end = checked_window(request)
    reason_code = checked_reason_code(request)
    charge_code = checked_charge_code(request)
    bill_type = BILL_TYPE_BY_KIND[kind]

    if kind in CHARGE_CODE_KINDS:
        # ⚠ **THE FEE KIND MINTS ITS RUN INSIDE `fee_bill`, AND THE BRANCH IS
        # HERE RATHER THAN IN `_draft_for` FOR THAT REASON** (`CR-108` wave 1).
        # `raise_charge_fee` has called `create_one_time_run` itself since
        # DEF-708 — the cut is its first caller and it owns its own
        # transaction — so routing a fee through the run-then-draft path above
        # would mint TWO runs for one bill, and the second would collide on
        # BR-BIL-005's key with the first. It also writes its own
        # `invoice.drafted` audit row (CLAUDE.md rule 7), so a fee audits once
        # and not twice. One door, one run, one audit.
        return _create_fee(
            request,
            charge_code=charge_code,
            on_date=period_start,
            run_by=run_by,
            actor=actor,
        )

    with transaction.atomic():
        run = create_one_time_run(
            account_id=request.account_id,
            bill_type=bill_type,
            period_start=period_start,
            period_end=period_end,
            bill_date=request.bill_date,
            due_days=request.due_days,
            scope_services=request.scope_services,
            run_by=run_by,
            actor=actor,
        )
        with _rollover_answers(request):  # DEF-BIL-9076
            invoice = _draft_for(request, kind=kind, run=run, reason_code=reason_code)
        _record_clerk_choices(invoice, request, kind=kind)
        # CLAUDE.md rule 7. The DRAFT is the money action here — it is the point
        # at which a figure exists against a named customer — so it is audited
        # separately from the run row's own creation.
        audit.money_action(
            actor if actor is not None else run_by,
            "invoice.drafted",
            "invoice",
            str(invoice.pk),
            before=None,
            after={
                "bill_run_id": str(run.pk),
                "one_time_kind": kind,
                "bill_type": invoice.bill_type,
                "account_id": str(invoice.account_id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "reason_code": reason_code or None,
                # rule 2 — the figure never travels without its currency.
                "total": str(invoice.total),
                "currency": invoice.currency,
            },
        )

    body: dict[str, Any] = {
        "run_id": str(run.pk),
        "kind": kind,
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "bill_type": invoice.bill_type,
        "status": invoice.status,
        "subtotal": str(invoice.subtotal),
        "tax_total": str(invoice.tax_total),
        "total": str(invoice.total),
        "currency": invoice.currency,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "unavailable": [dict(row) for row in ONE_TIME_UNAVAILABLE],
        # PO ruling 2026-09-30 — read back from the DRAFT's own frozen payload
        # (`runs.price_account` / `backbill.price_back_bill` put them there),
        # so what the answer says is what the document holds.
        "warnings": [dict(row) for row in (invoice.bill_payload or {}).get("warnings") or ()],
    }
    if kind == KIND_FINAL:
        # BR-BIL-013 — the settlement is computed from the DRAFTED bill's own
        # total plus everything outstanding (PO 2026-08-12, OQ-158), so it can
        # only be produced once the bill exists. Nothing is WRITTEN by it: there
        # is no `final_settlements` table (`final_bill.py` reports the gap), so
        # the path is shown to the clerk and recorded nowhere. Stated here
        # because a screen that showed a settlement would otherwise imply one
        # had been saved.
        body["settlement"] = _settlement_body(invoice)
    return body


def _create_fee(
    request: OneTimeRequest,
    *,
    charge_code: str,
    on_date: date,
    run_by: Any = None,
    actor: Any = None,
) -> dict[str, Any]:
    """Screen 22.6's write — one charge code, one DRAFT, through `fee_bill`.

    A thin forwarder, and thin on purpose: `fee_bill.raise_charge_fee` is the
    money path DEF-708 built and reviewed, it mints its own run, it audits its
    own draft and it refuses on four states by name. Re-implementing any of
    that here so the shapes matched would be a second way for a fee to reach
    `invoice_lines`, which is the one thing `fee_bill`'s own docstring refuses
    to be.

    **`due_days` IS REQUIRED AND IS NOT CHOSEN HERE.** A cycle-less bill has no
    cycle to take its terms from (CR-029 D8③), and `issue` refuses a bill whose
    due date cannot be derived rather than guessing one — so an absent value is
    refused at step 1 rather than becoming a late-fee clock nobody started.

    It returns the same body every other kind returns, so a screen reads ONE
    shape whichever kind it drafted.
    """
    from apps.billing import fee_bill  # local: `fee_bill` imports this module.

    if request.due_days is None:
        raise BillingRuleError(
            "this fee has no days to pay, so its due date could not be derived and the "
            "bill could be drafted and never sent (BR-BIL-024). A one-time bill takes its "
            "terms from the clerk rather than from a cycle it does not have, and nothing "
            "here guesses them: thirty days is a figure no signed document contains, and "
            "the tenant's commonest cycle is wrong for anyone not on it.",
            br_ref="BR-BIL-024",
        )

    with transaction.atomic():
        invoice = fee_bill.raise_charge_fee(
            actor if actor is not None else run_by,
            account_id=request.account_id,
            charge_code=charge_code,
            # BR-TEN-043 / gate G6 — the clerk's typed bill date, never a clock.
            on_date=on_date,
            due_days=request.due_days,
            entered_amount=request.entered_amount,
        )
        _record_clerk_choices(invoice, request, kind=KIND_FEE)
    return {
        "run_id": str(invoice.bill_run_id),
        "kind": KIND_FEE,
        "charge_code": charge_code,
        "invoice_id": str(invoice.pk),
        "invoice_no": invoice.invoice_no,
        "bill_type": invoice.bill_type,
        "status": invoice.status,
        "subtotal": str(invoice.subtotal),
        "tax_total": str(invoice.tax_total),
        "total": str(invoice.total),
        "currency": invoice.currency,
        "period_start": on_date.isoformat(),
        "period_end": on_date.isoformat(),
        "unavailable": [dict(row) for row in ONE_TIME_UNAVAILABLE],
        # A fee bill prices no service, so no base can be missing from it.
        "warnings": [dict(row) for row in (invoice.bill_payload or {}).get("warnings") or ()],
    }


def _record_clerk_choices(invoice: models.Invoice, request: OneTimeRequest, *, kind: str) -> None:
    """Put what the clerk DECIDED on step 2 into the draft's snapshot (DB2, DB3).

    Three facts, each for one kind, each a WORD and never a figure:

      * FINAL — `bill_payload.settlement.path`, the path the clerk chose
        (contract §2 `settlement.paths`). It is checked HERE against
        `final_bill.settle_final_bill(invoice, chosen=…)`, which refuses by name
        when the path is not available for this remainder (a transfer with no
        master account, a payment plan on a refund) — so a draft never carries
        a choice the settlement rule would not accept. There is no
        `final_settlements` table (`final_bill.py` exception 1); the snapshot
        is where the choice survives to issue, and BR-BIL-030 freezes it there.
      * PENALTY — `bill_payload.penalty.evidence`, what was found. TEXT only:
        photos are not stored (see `one_time_answer.ANSWER_UNAVAILABLE`).
      * FEE — `bill_payload.note`, the note printed beside the charge.

    A DRAFT's payload may be written (the immutability trigger bites at issue,
    `billing/0006`); nothing here touches an issued bill. An empty value writes
    nothing, so a draft made without the new fields is byte-identical to one
    made before they existed.
    """
    payload = dict(invoice.bill_payload or {})
    changed = False
    if kind == KIND_FINAL and request.settlement_path:
        settled = final_bill.settle_final_bill(invoice, chosen=request.settlement_path)
        payload["settlement"] = {
            **dict(payload.get("settlement") or {}),
            "path": settled.path or request.settlement_path,
            "chosen_by_clerk": request.settlement_path,
        }
        changed = True
    if kind == KIND_PENALTY and request.evidence:
        payload["penalty"] = {**dict(payload.get("penalty") or {}), "evidence": request.evidence}
        changed = True
    if kind == KIND_FEE and request.note:
        payload["note"] = request.note
        changed = True
    if changed:
        invoice.bill_payload = payload
        invoice.save(update_fields=["bill_payload", "updated_at"])


def create_one_time_run(
    *,
    account_id: Any,
    bill_type: str,
    period_start: date,
    period_end: date,
    bill_date: date | None = None,
    due_days: int | None = None,
    scope_services: tuple[str, ...] | list[str] | None = None,
    run_by: Any = None,
    actor: Any = None,
    pending_new_connection_owner: bool = False,
    run_key_source: str | None = None,
) -> models.BillRun:
    """The lawful `bill_runs` row a ONE-TIME bill hangs off. Writes nothing else.

    `pending_new_connection_owner` (`DEF-MET-9217`, 🔒 HUMAN-REVIEW-PENDING) —
    a `fee` run ONLY, for the New Connection fee door; forwarded to
    `single.billable_account`, whose docstring says why and how narrow.

    `run_key_source` (`DEF-PAY-10740`, 🔒 HUMAN-REVIEW-PENDING) — the one event
    this bill answers to, folded into the idempotency key as its sixth part
    (`idempotency.one_time_run_key`'s `source`). Only the NSF fee passes it
    (`nsf:<bounced payment uuid>`), so two bounces on one account on one day
    are two runs; every other caller passes nothing and keeps its key.

    ── WHY THIS FUNCTION EXISTS AT ALL ──────────────────────────────────────
    Five complete engines — `first_bill` · `final_bill` · `single` · `backbill`
    · `penalty` — each take a `bill_run`, and it is REQUIRED rather than
    optional for a reason `single.calculate_single_bill` states in its own
    docstring: stage 6 replaces an existing draft for `(tenant, account,
    bill_run)`, so a `None` run would make a July interim bill and a January
    back-bill key identically and drafting the second would DELETE the first.

    Until migration 0021 no such row could exist — `bill_runs.cycle_id` was NOT
    NULL and a one-time bill has no cycle. This is the writer that fills the two
    columns that migration added.

    ── WHAT IT IS **NOT**: A SECOND `create_run` ────────────────────────────
    Everything a cycle run and a one-time run share is shared: the same table,
    the same `draft` status, the same audit action, the same `DuplicateRun`
    refusal carrying who/when/link. What differs is exactly the SCOPE — an
    ACCOUNT instead of a CYCLE — and therefore the idempotency key
    (`one_time_run_key`; BR-BIL-005 keys a run on the scope that identifies it).

    ── THE ACCOUNT IS VERIFIED THROUGH CUSTOMERS' OWN READ, AND IT HAS TO BE ─
    `scope_account_id` is a foreign key, and a foreign key alone would NOT stop
    a run being pointed at another tenant's account: PostgreSQL evaluates
    referential integrity OUTSIDE row-level security. So the account is resolved
    through customers' own tenant-scoped read first, and an unknown id, a
    malformed id and another tenant's id come back as ONE answer — absent
    (HR-1). This is `runs.create_run`'s posture with its cycle, for the
    identical reason.

    ⚠ **`final` DELIBERATELY DOES NOT GO THROUGH THE BILLABLE SET.** A final
    bill is precisely the bill of an account LEAVING that set —
    `final_bill.moving_out_account` exists for it — so a `final` run verifies
    that the account exists and is this tenant's, and lets the engine rule on
    the behaviour class, which it does with a sentence a clerk can act on.
    """
    if period_end < period_start:
        raise BillingRuleError(
            f"period {period_start} → {period_end} ends before it begins. Every proration "
            "in B4.3 divides by this window, so the run is refused rather than created "
            "with a window that cannot be divided."
        )
    if bill_type not in models.BILL_TYPES:
        raise BillingRuleError(
            f"unknown bill type {bill_type!r}. B2 r10 #12 defines {models.BILL_TYPES}; a "
            "type the code does not implement stops the bill rather than defaulting to "
            "'cycle', which would mistype a document that is kept for seven years."
        )

    if bill_type == "final":
        scope = final_bill.moving_out_account(account_id)
    else:
        scope = single.billable_account(
            account_id,
            pending_new_connection_owner=pending_new_connection_owner and bill_type == "fee",
        )

    tenant_id = core_tenancy.current_tenant_id()
    key = idempotency.one_time_run_key(
        account_id=scope.account_id,
        bill_type=bill_type,
        period_start=period_start,
        period_end=period_end,
        source=run_key_source,
    )
    existing = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
    if existing is not None:
        raise runs.DuplicateRun(existing)

    try:
        row = models.BillRun.objects.create(
            tenant_id=tenant_id,
            # NULL, and it is a fact rather than a gap: this bill belongs to no
            # cycle. `ck_bill_runs_has_a_scope` is satisfied on the other branch.
            cycle_id=None,
            scope_account_id=scope.account_id,
            period_start=period_start,
            period_end=period_end,
            # BR-BIL-070 — the date the clerk typed. On a one-time run this is
            # the ONLY source of a bill date: `effective_bill_date` falls back to
            # the CYCLE's and there is no cycle here. Absent stays absent rather
            # than being filled from a clock (BR-TEN-043 / gate G6).
            bill_date=bill_date,
            # ── CR-029 D8③ · WHERE A CYCLE-LESS BILL'S DUE DATE COMES FROM ──
            # PO, verbatim 2026-08-23: *"③ what due date a cycle-less one-time
            # bill gets - it will be capture at the time of bulk billing - not
            # here"*. So the RUN carries the terms, exactly as it carries the
            # bill date, and `issue._due_terms_for` resolves run-then-cycle with
            # no cycle to fall back to. This closes OQ-241, which asked the
            # question and which the module head answered *"nothing here guesses
            # one"* — it still does not: absent stays absent and the derivation
            # refuses by name, and what changed is that there is now somewhere
            # for the clerk's answer to live.
            #
            # ⚠ `0` IS A TYPED VALUE (due on the bill date, BR-MET-009's
            # `due_days ≥ 0`) and `None` is *nobody typed one*. The API layer
            # keeps the two apart with `is None`, never truthiness.
            due_days=due_days,
            status="draft",
            bill_type=bill_type,
            idempotency_key=key,
            scope_services=list(scope_services) if scope_services is not None else None,
            # WHO ran it, by id — BR-BIL-005's refusal names this user.
            # ⚠ `getattr(run_by, "pk", run_by)` here is DEF-BIL-5090: the B12
            # actor has `id` and no `pk`, so the NAMESPACE went into a UUID
            # column and no cut could be committed. One resolver, five shapes.
            run_by_id=audit.actor_user_id(run_by),
        )
    except IntegrityError as clash:
        # Lost the race between the check above and this insert. The unique
        # index is the real guarantee; re-read and answer with the same refusal
        # rather than a 500.
        winner = models.BillRun.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
        if winner is None:
            raise clash
        raise runs.DuplicateRun(winner) from clash

    # CLAUDE.md rule 7 — creating the run is the act that decides WHO is billed
    # for WHAT window under WHICH rules, so it is audited exactly as a cycle
    # run's creation is.
    audit.money_action(
        actor if actor is not None else run_by,
        "bill_run.created",
        "bill_run",
        str(row.pk),
        before=None,
        after={
            "cycle_id": None,
            "scope_account_id": scope.account_id,
            "scope_account_no": scope.account_no,
            "bill_type": bill_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "bill_date": bill_date.isoformat() if bill_date is not None else None,
            # CR-029 D8③ — the terms this bill falls due on, recorded with the
            # act that decided them (CLAUDE.md rule 7).
            "due_days": due_days,
            "status": row.status,
            "scope_services": row.scope_services,
            "idempotency_key": key,
        },
    )
    return row


# ── the per-kind plumbing. No arithmetic below this line. ───────────────────


def _draft_for(
    request: OneTimeRequest, *, kind: str, run: models.BillRun, reason_code: str
) -> models.Invoice:
    """Route the kind to ITS engine's calculate pass. One draft, every time."""
    period_start, period_end = checked_window(request)

    # 🔒 `DEF-BIL-10067` — step 2's typed readings as SAVED in Meter Reads, so
    # the draft prices the number the preview priced (`saved_typed_reads`).
    keyed = saved_typed_reads(request)

    if kind == KIND_BACKBILL or kind == KIND_PENALTY:
        prepared = _prepare_sub_period_kind(
            request, kind=kind, reason_code=reason_code, keyed_reads=keyed
        )
        if kind == KIND_PENALTY:
            return penalty.calculate_penalty_bill(prepared, bill_run=run)
        return backbill.calculate_back_bill(prepared, bill_run=run)

    if kind == KIND_FINAL:
        # PO 2026-10-01 — no cycle, no final bill (*"same as first bill"*).
        refuse_a_bill_with_no_cycle(request.account_id, kind=kind)
        data = final_bill.prepare_final_bill(
            account_id=request.account_id,
            period_start=period_start,
            moved_out_on=period_end,
            cycle_days=_cycle_days(request),
            scope_services=request.scope_services,
            keyed_reads=keyed,
        )
        return final_bill.calculate_final_bill(data, bill_run=run)

    if kind == KIND_FIRST:
        # `DEF-BIL-8330` — no cycle, no first bill (PO 2026-09-30, option A).
        refuse_a_first_bill_with_no_cycle(request.account_id)
        moved_in_on = first_bill_move_in(request, period_start)
        cycle_days = first_bill_cycle_days(request, moved_in_on, period_start, period_end)
        data = first_bill.prepare_first_bill(
            account_id=request.account_id,
            moved_in_on=moved_in_on,
            period_end=period_end,
            cycle_days=cycle_days,
            period_start=period_start,
            scope_services=request.scope_services,
            cycle_days_for=_interim_part_cycle_days(request),  # `DEF-BIL-8749`
            keyed_reads=keyed,
        )
        return first_bill.calculate_first_bill(
            data,
            bill_run=run,
            moved_in_on=moved_in_on,
            account_type_id=_account_type_id(request.account_id),
            connection_charge_code=request.connection_charge_code,
        )

    if kind == KIND_INTERIM:
        # PO 2026-10-01 — no cycle, no interim bill (`BR-BIL-1066`).
        refuse_a_bill_with_no_cycle(request.account_id, kind=kind)
    prepared = single.prepare_single_bill(
        account_id=request.account_id,
        period_start=period_start,
        period_end=period_end,
        service_date=period_end,
        # PO 2026-10-01 (`BR-BIL-1066`) — the same denominator as the preview.
        cycle_days=(
            interim_bill_cycle_days(request, period_start, period_end)
            if kind == KIND_INTERIM
            else _cycle_days(request)
        ),
        scope_services=request.scope_services,
        bill_type=BILL_TYPE_BY_KIND[kind],
        # CR-156-BRC10 — the same cut the preview makes, so the clerk approves
        # the document the draft writes.
        price_split_cycle_days=_interim_part_cycle_days(request) if kind == KIND_INTERIM else None,
        keyed_reads=keyed,
    )
    if kind == KIND_INTERIM:
        prepared = _prepared_with_clerk_estimates(
            prepared, request, period_start=period_start, period_end=period_end
        )
    return single.calculate_single_bill(prepared, bill_run=run, bill_type=BILL_TYPE_BY_KIND[kind])


def _prepare_sub_period_kind(
    request: OneTimeRequest,
    *,
    kind: str,
    reason_code: str,
    keyed_reads: Any = None,
    waiting_ok: bool = False,
) -> Any:
    """`backbill.prepare_back_bill`, or `penalty`'s cap-exempt wrapper of it.

    A theft case goes through `penalty.prepare_penalty_bill`, which sets
    `theft=True` — the ONLY thing that flag exempts is the tenant's back-bill
    window cap (BR-BIL-018 / OQ-071). The case is still reason-coded and still
    approval-gated, and it is priced by the same pass, which is why a theft bill
    and a catch-up bill can never round differently.
    """
    if kind == KIND_PENALTY:
        return penalty.prepare_penalty_bill(
            account_id=request.account_id,
            sub_periods=request.sub_periods,
            reason_code=reason_code,
            # ⚠ **THIS READ `charge_codes=()` UNTIL 2026-09-15 (`DEF-BIL-5317`).**
            # Its comment said the lines *"cannot be priced (rating publishes no
            # charge-code read)"*, which had stopped being true on 2026-08-27 —
            # so a clerk who picked TAMPER on step 2 got a theft bill with the
            # usage restated and no penalty on it. BR-BIL-019's second
            # ingredient now reaches the bill. A code is OPTIONAL here, unlike
            # the fee kind where the code IS the bill: a penalty bill may be
            # restated usage and nothing else, so an empty string sends none
            # rather than refusing.
            charge_codes=(request.charge_code,) if (request.charge_code or "").strip() else (),
            scope_services=request.scope_services,
            keyed_reads=keyed_reads,
            waiting_ok=waiting_ok,
        )
    return backbill.prepare_back_bill(
        account_id=request.account_id,
        sub_periods=request.sub_periods,
        reason_code=reason_code,
        theft=False,
        scope_services=request.scope_services,
        # DEF-BIL-8324 — step 2's typed readings, used first; the draft passes
        # them as SAVED (`saved_typed_reads`, DEF-BIL-10067).
        keyed_reads=keyed_reads,
        waiting_ok=waiting_ok,
    )


def _sub_period_body(prepared: Any, *, kind: str) -> dict[str, Any]:
    """The back-bill preview: the GROUPS, and which of them carry derived usage.

    US-BIL-013 §5 asks for period-labeled groups and their tariff versions, and
    OQ-191's ruling requires that a clerk approving a catch-up be SHOWN which
    segments carry an estimate — *"a clerk who approves a six-month catch-up
    without being told which of its segments carry derived usage has approved
    something they were not shown"* (`backbill.PreparedBackBill`).
    """
    back = prepared.back_bill if kind == KIND_PENALTY else prepared
    body: dict[str, Any] = {
        "account_no": back.account_no,
        "reason_code": back.reason_code,
        "theft": back.theft,
        "cap_months": back.cap_months,
        "approval_mode": back.approval_mode,
        "estimate_source": back.estimate_source,
        "groups": [
            {
                "label": group.label(),
                "period_start": group.period_start.isoformat(),
                "period_end": group.period_end.isoformat(),
                "service_date": group.service_date.isoformat(),
                "days": group.days,
                "cycle_days": group.cycle_days,
                "tariff_version_ids": dict(group.tariff_version_ids),
                # `DEF-BIL-8328` — what THIS group is priced on, after the
                # day-share and the estimate (`DEF-BIL-8324`): whether a meter
                # still waits, and each read's own quantity and flag. Step 2
                # states these, never the raw read of the window. Facts only;
                # nothing here prices.
                "waiting": _waits_for_a_reading(group.data),
                "reads": [_group_read(reading) for reading in group.data.readings],
            }
            for group in back.groups
        ],
        # Every derived usage, with the weight it was derived on, so the
        # arithmetic is re-checkable from the record alone.
        "estimates": [estimate.as_dict() for estimate in back.estimates],
    }
    if kind == KIND_PENALTY:
        body["assessed_unverifiable"] = prepared.assessed_unverifiable
        body["charge_codes"] = list(prepared.charge_codes)
    return body


def _group_read(reading: Any) -> dict[str, Any]:
    """One read of a catch-up group as step 2 states it (`DEF-BIL-8328`) — the
    quantity the group is priced on, with its unit (rule 3), or None."""
    quantity = getattr(reading, "consumption", None)
    return {
        "service": reading.service_code,
        "asset_id": getattr(reading, "asset_id", None),
        "quantity": None if quantity is None else str(quantity.amount),
        "unit": None if quantity is None else quantity.unit,
        "estimated": bool(getattr(reading, "estimated", False)),
    }


def _line_body(line: Any) -> dict[str, Any]:
    """ONE priced line, as the facts its BASIS sentence is made of.

    Every value here is carried off the engine's own `RatedLine` and none is
    re-derived. In particular `quantity × unit_price` is deliberately NOT
    asserted against `amount`: B4 rounds per line (BR-RAT-003) and a proration
    may sit between them, so anything that multiplied would eventually
    contradict the number printed beside it (`runbooks/definitions/test_bill`
    says the same of its own sentence).

    `unit_price` ON A TAX LINE IS THE RATE — the engine puts it there in as many
    words, *"a percent rule's unit price IS its rate, that is what the bill
    prints beside the line"* — so the drawn *8.25%* needs no second read and no
    second formatter. A FLAT rule states None rather than 0.

    `charge_id`, `tax_id`, `service` and `tariff_version_id` are the line's
    IDENTITY (BR-BIL-069). They are carried for a caller that must group or link
    by them; none of them is the visible value of a field (B14 rule 31).
    """
    consumption = getattr(line, "quantity", None)
    return {
        "kind": line.kind,
        "description": line.description,
        # rule 2 — a money figure travels at 4dp as a string, rounded for
        # display and never here.
        "amount": str(line.amount),
        "taxable": bool(line.taxable),
        # rule 3 — a quantity NEVER travels without its unit.
        "quantity": None if consumption is None else str(consumption),
        "unit": getattr(line, "unit", None),
        "unit_price": (None if getattr(line, "unit_price", None) is None else str(line.unit_price)),
        "service": getattr(line, "service", None),
        "tax_id": getattr(line, "tax_id", None),
        "tariff_version_id": getattr(line, "tariff_version_id", None),
        "charge_id": getattr(line, "charge_id", None),
    }


# ══════════════════════════════════════════════════════════════════════════
# WHAT A CLERK READS WHEN THIS SCREEN CANNOT PRICE — `DEF-RAT-7991`, 2026-09-29
# ══════════════════════════════════════════════════════════════════════════
#: On 2026-09-29 the One-time bill screen showed a clerk, verbatim:
#:
#:     R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-25fa070287cc' are in
#:     force for 'sewer' on 2026-10-29 (01a0b366-…, 01a0b388-…, 01a0b424-…,
#:     01a0e712-…). Exactly one prices a service; there is no best match and
#:     this chain never picks.
#:
#: **Four database uuids on screen.** B14 rule 31 — PO verbatim, *"no Databse
#: ID on screen - that is a rule"* — and rule 32 for the internal code beside
#: them. The six sites below each put `str(refusal)` into `detail` on a **200
#: response**, and `BR-SHL-020 r2`'s protection (`client.ts`, `delete
#: rest.detail`) strips an **ApiError's params**: it is not anywhere near this
#: shape and never was. The guard existed and could not see it.
#:
#: ⚠ **THE SENTENCE STAYS — `DEF-CUS-6464` put it here on purpose**, because a
#: bare `reason` code breaks rule 32 and this file's own docstring calls
#: `detail` *"the ACTIONABLE half"*. What changes is WHOSE sentence it is.
#: `rating.resolution.clerk_refusal` is the one reader, published by the module
#: that raises; where it answers, `detail` becomes the id-free sentence and
#: `message_key` travels beside it so the words come from the clerk's own
#: catalogue (`DEF-BIL-5339`'s vehicle, reused). Where it answers None — every
#: refusal this module and `gather` raise themselves, which is most of them —
#: the body is byte-identical to what it served yesterday.
#:
#: `G139` re-runs the chain and fails on a uuid in any of the three fields.
def _clerk_gap(refusal: Exception, fallback_reason: str) -> dict[str, Any]:
    """The `{reason, detail, …}` object these six sites serve, id-free."""
    body: dict[str, Any] = {
        "reason": getattr(refusal, "reason", fallback_reason),
        # `detail` on an `AccountProblem` (the blocked/decisions rows), the
        # string form on an exception. Both are the ENGINEER's sentence and
        # both are the fallback for a refusal that states no clerk one.
        "detail": (
            getattr(refusal, "clerk_detail", None)
            or getattr(refusal, "detail", None)
            or str(refusal)
        ),
    }
    service_code = getattr(refusal, "service_code", None)
    if service_code:
        # The service a setup refusal is about — the one fact a clerk acts on
        # (contract §2: a pricing refusal *"names the service"*). A code and
        # never an id; the screen turns it into the service's own word.
        body["service_code"] = service_code
    key = getattr(refusal, "message_key", None)
    if key:
        body["message_key"] = key
        params = getattr(refusal, "message_params", None)
        if params:
            body["message_params"] = dict(params)
    return body


def _customer_name(account_id: Any) -> str | None:
    """WHOSE bill this is — the primary contact's name, or **None**.

    ⚠ **THE PREVIEW SERVED `account_no` AND NO NAME UNTIL 2026-09-29, AND THE
    COST WAS A SENTENCE ABOUT THE WRONG THING (`DEF-BIL-7990`).** Step 1 of the
    One-time bill builds its label from the account picker, which carries
    `{account_no, name}` — *"AC-2026-00058 — Rostan Chase"*. Step 2 renders
    THIS payload, which carried the number alone, and its null fallback was
    *"Account with no name on file"*. `account_no` is null here whenever the
    prepare pass resolved no READY account — a BLOCKED account, which says
    nothing whatever about the customer record — so a clerk reading a real
    refusal was told a false fact about the customer instead of the true one
    about billability.

    ⚠ **IT IS THE BATCHED READ WITH ONE ID, NOT THE SINGULAR ONE.**
    `customers.primary_contact_name` takes a row this function does not have
    and would cost a second account fetch; `primary_contact_names_for` takes
    ids and answers in ONE query. `bill_run_readiness.py` and `/outstandings`
    are on the same read for the same reason (`P2.12`).

    ⚠ **`None` IS A REAL ANSWER AND IS NOT AN ERROR.** An account with no
    `customer_accounts` link genuinely has no name (`BR-CUS-054`), and the seam
    returns `None` rather than `{}` when customers has not published the read
    at all. Both land here as `None`, and the SCREEN decides what to say —
    which is where that decision belongs, because *"we asked and there is no
    name"* and *"we could not ask"* are the same thing to a clerk and neither
    is *"this account cannot be billed"*.
    """
    names = customers_seam.primary_contact_names_for([str(account_id)])
    if names is None:
        return None
    return names.get(str(account_id))


def _priced_body(pricing_pass: Any) -> dict[str, Any]:
    """Stages 1–5's own answer — the LINES and the money — or the named refusal.

    `pricing_pass` is a callable so that every kind hands over the exact pricing
    call the DRAFT will make and this function decides nothing about which one.
    It is not spelled `price`: `test_us_bil_012_one_time.py::tc4` walks every
    signature in this module for the names an API layer could bind money to, and
    a parameter it cannot distinguish from a typed figure is refused — correctly.
    The guard was narrowed for nothing here; the parameter was renamed.

    ⚠ **A REFUSAL IS RETURNED, NOT RAISED**, which is `_deposit_body`'s posture
    for the same reason: a clerk who cannot be shown the lines can still be
    shown the account, the window and what is blocking it, and the missing half
    is named on screen instead of blanking the page.

    ⚠ **AND `priced: false` CARRIES NO TOTAL AT ALL.** Not `0.00` — a zero here
    is a money claim about a customer, and on a bill preview it is the claim
    that they owe nothing. The absence of the key is the honest shape.
    """
    try:
        priced_pass = pricing_pass()
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {
            "priced": False,
            "lines": [],
            "priced_unavailable": _clerk_gap(refusal, "not_priced"),
        }
    # `runs.PricedAccount` or `backbill.PricedBackBill` — both carry `.priced`
    # and, since the PO's ruling of 2026-09-30, `.warnings`: a base nobody
    # defined and bound bills `$0.00` and the preview SAYS so. A pass that
    # returns the bare `RatedBill` (none does today) reads as no warnings.
    priced = getattr(priced_pass, "priced", priced_pass)
    return {
        "warnings": [dict(row) for row in getattr(priced_pass, "warnings", ()) or ()],
        "priced": True,
        "lines": [_line_body(line) for line in getattr(priced, "lines", ())],
        # The SAME four keys `create` returns from the drafted bill, so a screen
        # reads one shape before and after the write. `assemble_document` writes
        # `invoices.subtotal` from `taxable_subtotal` and `invoices.total` from
        # `total`, so these are the figures the document will carry.
        "subtotal": str(getattr(priced, "taxable_subtotal", 0)),
        "tax_total": str(getattr(priced, "tax_total", 0)),
        "total": str(getattr(priced, "total", 0)),
        "currency": getattr(priced, "currency", None),
    }


def _fee_body(
    request: OneTimeRequest,
    *,
    charge_code: str,
    on_date: date,
    kept: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Screen 22.6 — the charge, and nothing that a fee does not have.

    Three of the five step-2 groups are ABSENT rather than empty, and the
    blueprint's words for that are *"Not asked, and that is not an omission. A
    fee has no usage, so there is nothing to read and no plan to price it on."*
    So this body carries no services list, no readings, no cycle days and no
    rate plan: a null in any of those keys would read as *we looked and found
    nothing*, which is a different statement.

    The refusals fire HERE, before anything is written and while the clerk is
    still on step 2 — an unknown code, a code with no live price, a code with no
    GL account, and a TAXABLE code on an account with no plan to tax it by (the
    fee-tax lane's judgment (c)). *"Each refuses by name rather than charging
    zero, because a fee that quietly prices at nothing is a fee nobody notices
    was never charged."* A code the tenant has marked TAXABLE is otherwise
    TAXED (`OQ-812`, ❄️ B4.2 addendum re-signed 2026-09-30 — RECON $75.00 at
    8.25% → $81.19), by `fee_bill.price_charge_fee` through the engine's one
    tax pass, so the answer below carries its tax lines and `tax_total`.
    ⚠ This sentence read *"(stated rather than refused) a code the tenant has
    marked taxable"* until 2026-09-30 — true when a fee bill could not be
    taxed, false from the fee-tax lane's commit (`DEF-BIL-8153`).
    """
    from apps.billing import fee_bill  # local: `fee_bill` imports this module.

    body: dict[str, Any] = {"charge_code": charge_code}
    try:
        priced_bill = fee_bill.price_charge_fee(
            account_id=request.account_id,
            charge_code=charge_code,
            on_date=on_date,
            entered_amount=request.entered_amount,
        )
    except (gather.GatherProblem, BillingRuleError) as refusal:
        body.update(
            {
                "priced": False,
                "lines": [],
                "priced_unavailable": _clerk_gap(refusal, "fee_cannot_be_raised"),
            }
        )
        return body

    if kept is not None:
        kept["priced"] = priced_bill.priced
    body.update(
        {
            "account_id": priced_bill.account.account_id,
            "account_no": priced_bill.account.account_no,
            "ready": 1,
            "blocked": [],
            "decisions": [],
            "priced": True,
            "lines": [_line_body(line) for line in priced_bill.priced.lines],
            "subtotal": str(priced_bill.priced.taxable_subtotal),
            "tax_total": str(priced_bill.priced.tax_total),
            "total": str(priced_bill.priced.total),
            "currency": priced_bill.priced.currency,
        }
    )
    body["books"] = _books_body(
        bill_type=BILL_TYPE_BY_KIND[KIND_FEE],
        charges=priced_bill.priced.total,
        currency=priced_bill.priced.currency,
    )
    return body


def _previewed_settlement(
    body: dict[str, Any], request: OneTimeRequest, *, period_end: date
) -> Any:
    """BR-BIL-013's deposit-first settlement on a bill that does not exist yet.

    The drawn rows *Deposit and its interest, applied first* and *Still due · to
    collect* are this: `final_bill.settle_closing_position` applies the deposit
    BEFORE any path is chosen, because the remainder is what selects the path.

    ⚠ **IT RETURNS THE OBJECT RATHER THAN THE PAYLOAD, WHICH IS THE WHOLE POINT
    OF THE SPLIT.** The books panel needs the same deposit and the same closing
    position this computed, and reading them again would be a second reading of
    BR-CUS-057's interest accrual inside one payload — the settlement row and
    the *Deposit applied* entry could then state different figures about the
    same customer's money on the same screen. `_settlement_preview_body`
    serialises whatever this answers.

    A refusal comes back as a `dict` in `_settlement_body`'s own
    `available: False` shape, so a screen renders one thing whether the bill is
    drafted or not, and the caller can tell the two apart by type.
    """
    if not body.get("priced"):
        return {
            "available": False,
            "reason": "not_priced",
            "detail": "the charges could not be priced, so the deposit has nothing to be "
            "applied to. BR-BIL-013 applies the deposit FIRST and the remainder is what "
            "chooses the settlement path, so there is no settlement to show until there "
            "is a figure to settle.",
        }
    try:
        return final_bill.settle_closing_position(
            account_id=request.account_id,
            total=Decimal(str(body["total"])),
            currency=str(body["currency"]),
            moved_out_on=period_end,
        )
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {"available": False, **_clerk_gap(refusal, "settlement_unavailable")}


def _settlement_preview_body(settlement: Any) -> dict[str, Any]:
    """`_previewed_settlement`'s answer on the wire — the object, or its refusal."""
    if isinstance(settlement, dict):
        return settlement
    return {
        "available": True,
        "charges": str(settlement.charges),
        "deposit_total": str(settlement.deposit.total),
        "remainder": str(settlement.remainder),
        "refund_amount": str(settlement.refund_amount),
        "amount_due": str(settlement.amount_due),
        "path": settlement.path,
        "automatic": settlement.automatic,
        "available_paths": list(settlement.available),
        "currency": settlement.currency,
        "write_off_threshold": str(settlement.write_off_threshold),
        "transfer_unavailable": settlement.transfer_unavailable,
        # Nothing is stored — there is no `final_settlements` table
        # (`final_bill.py` exception 1) — and on a PREVIEW nothing could be.
        "recorded": False,
    }


def _books_body(
    *,
    bill_type: str,
    charges: Any,
    currency: Any,
    deposit: Any = None,
    closing_position: Any = None,
) -> dict[str, Any]:
    """*Impact on your books* — the entries this bill would post, or why none.

    ⚠ **IT WRITES NOTHING AND IT IS NOT ALLOWED TO.** Only the ledger posting
    service writes journal lines (CLAUDE.md hard rule 5); `posting_seam.
    preview_bill_entries` composes no posting key, calls no ledger write and
    resolves none — it reads two designations and compares two numbers. Shown
    ABOVE the button on purpose: *"showing the three entries before the button
    means the clerk is not the last person to find out what the bill did to the
    ledger."*

    A refusal is RETURNED rather than raised, exactly as the settlement's is: a
    clerk whose deposit cannot be applied still has to see the charges and the
    reason, and it is the one panel where the reason is the whole point.
    """
    try:
        previewed = posting_seam.preview_bill_entries(
            bill_type=bill_type,
            charges=Decimal(str(charges)),
            currency=str(currency),
            deposit=deposit,
            closing_position=closing_position,
        )
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {
            "available": False,
            "posts": False,
            **_clerk_gap(refusal, "books_unavailable"),
        }
    return {
        "available": True,
        "posts": previewed.posts,
        "refused": previewed.refused,
        "reason": previewed.reason,
        "detail": previewed.detail,
        "currency": previewed.currency,
        "closing_position": (
            None if previewed.closing_position is None else str(previewed.closing_position)
        ),
        "deposit_total": (
            None if previewed.deposit_total is None else str(previewed.deposit_total)
        ),
        "entries": [
            {
                "event": entry.event,
                "amount": str(entry.amount),
                "debit": _books_account(entry.debit),
                "credit": _books_account(entry.credit),
                "credit_is_per_gl": entry.credit_is_per_gl,
            }
            for entry in previewed.entries
        ],
        "unavailable": [dict(row) for row in previewed.unavailable],
    }


def _books_account(account: Any) -> dict[str, Any] | None:
    """One side of one entry — the code and the name a clerk reads."""
    if account is None:
        return None
    return {
        "designation": account.designation,
        "code": account.code,
        "name": account.name,
        # Carried for a caller that links to the chart; never the visible value
        # of a field (B14 rule 31).
        "account_id": account.account_id,
    }


def _add_books(body: dict[str, Any], *, kind: str, settlement: Any = None) -> None:
    """Attach the books panel once the money is known, and only then.

    An unpriced bill gets NO panel rather than an empty one: *nothing to post*
    and *we could not work out what this would post* are different facts, and a
    panel that conflated them would tell a clerk the bill moves no account when
    the truth is that it was never priced.

    ⚠ **THE DEPOSIT AND THE CLOSING POSITION ARE HANDED IN, NEVER RE-READ.**
    `_previewed_settlement` has already resolved both — the deposit with its
    BR-CUS-057 interest, accrued to the move-out day the caller named and never
    to a clock (`DEF-CWP-3842`, gate G6) — and asking for them a second time
    inside one payload is how the settlement row and the *Deposit applied* entry
    come to state different figures about the same customer's money on the same
    screen. A `dict` here is a refusal from that pass, so there is nothing to
    apply and the panel prices the bill alone.
    """
    if not body.get("priced"):
        return
    deposit = None
    closing_position = None
    if kind == KIND_FINAL and settlement is not None and not isinstance(settlement, dict):
        deposit = settlement.deposit
        closing_position = settlement.charges
    body["books"] = _books_body(
        bill_type=BILL_TYPE_BY_KIND[kind],
        charges=body["total"],
        currency=body["currency"],
        deposit=deposit,
        closing_position=closing_position,
    )


def _account_body(data: Any) -> dict[str, Any]:
    """What the preview says about the account and its window. No money.

    ⚠ **THIS DOCSTRING SAID "NO TOTAL IS SERVED BY THE PREVIEW, AND THAT IS
    DELIBERATE" UNTIL `CR-108` WAVE 1, AND ITS REASONING WAS SOUND WHILE IT WAS
    TRUE** — *"a figure here would either be a second arithmetic or a zero
    standing in for 'not computed', which on a bill preview is a money claim"*.
    **THIS FUNCTION still serves no money and that has not changed**; what
    changed is that `preview` now also calls `runs.price_account`, which is the
    run's OWN stages 1–5 rather than a second arithmetic, and which serves
    `priced: false` with no total rather than a zero when it refuses. Corrected
    here rather than deleted, because a reader who finds the total on the wire
    and this sentence in the file cannot tell which one is stale (hard-won law
    1). `_priced_body` is where that money comes from.
    """
    return {
        "account_id": data.account_id,
        "account_no": data.account_no,
        "behavior_class": data.behavior_class,
        "currency": data.currency,
        "period_start": data.period_start.isoformat(),
        "period_end": data.period_end.isoformat(),
        # B4.3 — the two numbers the proration factor is made of. Shown because
        # they are the whole explanation of why a partial bill is smaller: 20 of
        # 31 days is a sentence a clerk can check, where "prorated" is not.
        "cycle_days": data.cycle_days,
        "service_days": data.service_days,
        "rate_plan_name": data.rate_plan_name,
        "services": [
            {
                "service_code": reading.service_code,
                # CLAUDE.md rule 3 — a quantity NEVER travels without its unit,
                # and `rating_seam.Quantity` is the pair. None is a MISSING READ
                # and is served as null rather than as 0: a zero would claim the
                # meter was read and showed no usage, which is a different and
                # sometimes very expensive statement (BR-BIL-015).
                "consumption": (
                    None
                    if getattr(reading, "consumption", None) is None
                    else {
                        "amount": str(reading.consumption.amount),
                        "unit": reading.consumption.unit,
                    }
                ),
                "estimated": bool(getattr(reading, "estimated", False)),
                "absent_reason": getattr(reading, "absent_reason", None),
            }
            for reading in data.readings
        ],
    }


def _deposit_body(account_id: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """BR-BIL-013's deposit credit, or the named reason it could not be read.

    A refusal is returned rather than raised so the rest of the final-bill
    preview still renders: a clerk who cannot see the deposit can still see the
    charges, and the missing half is named on screen instead of blanking the
    page.
    """
    try:
        credit = final_bill.deposit_credit_for(account_id, as_of)
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {"available": False, **_clerk_gap(refusal, "deposit_unavailable")}
    return {
        "available": True,
        "principal": str(credit.principal),
        "interest": str(credit.interest),
        "total": str(credit.total),
        "currency": credit.currency,
        "received_on": credit.received_on.isoformat() if credit.received_on else None,
    }


def _settlement_body(invoice: models.Invoice) -> dict[str, Any]:
    """BR-BIL-013's ONE settlement path for a drafted final bill, or why not.

    `path` null with `settled` true means the remainder is zero — nothing is
    owed in either direction. `path` null with `settled` false means a STAFF
    CHOICE is outstanding and `available` lists it. Two different facts, and a
    screen that conflated them would either nag about a settled account or
    quietly close an unsettled one (`final_bill.Settlement`).
    """
    try:
        settlement = final_bill.settle_final_bill(invoice)
    except (gather.GatherProblem, BillingRuleError) as refusal:
        return {"available": False, **_clerk_gap(refusal, "settlement_unavailable")}
    return {
        "available": True,
        "charges": str(settlement.charges),
        "deposit_total": str(settlement.deposit.total),
        "remainder": str(settlement.remainder),
        "refund_amount": str(settlement.refund_amount),
        "amount_due": str(settlement.amount_due),
        "path": settlement.path,
        "automatic": settlement.automatic,
        "available_paths": list(settlement.available),
        "currency": settlement.currency,
        "write_off_threshold": str(settlement.write_off_threshold),
        "transfer_unavailable": settlement.transfer_unavailable,
        # There is no `final_settlements` table (`final_bill.py` exception 1), so
        # this is COMPUTED and stored nowhere. Said on the wire so a screen
        # cannot imply it was saved.
        "recorded": False,
    }


def _cycle_days(request: OneTimeRequest) -> int | None:
    """The CYCLE's length, which a one-time bill does not have. Always None.

    ⚠ **AMENDED 2026-10-01 — THE INTERIM BILL NO LONGER USES THIS `None` EITHER.**
    PO ruling, verbatim: *"Should interim bills cut the base down like first and
    final bills? A · Cut down (10/30)"* — `OQ-242` option (a), CLOSED for interim
    bills (`BR-BIL-1066`). The interim path reads the account's own cycle through
    `interim_bill_cycle_days`, as the first bill does through
    `first_bill_cycle_days`. **What still holds below is the catch-up, penalty
    and fee bills only**, for which the withdrawal stands; read every *"interim"*
    in the paragraphs that follow as historical.

    ⚠ **AND `None` NO LONGER MEANS *CHARGE THE BASE WHOLE* ON ONE OF THE SIX
    KINDS — THE FINAL BILL READS THE ACCOUNT'S OWN CYCLE (PO 2026-09-20).**
    This function is unchanged and still answers `None` for every kind,
    including `final`; what changed is what the final bill's engine does with
    that `None`. `final_bill.prepare_final_bill` now reads the denominator
    itself through `final_bill._closing_cycle_days`, because a CLOSING account
    on a real billing cycle is not the cycle-less case `OQ-242` was withdrawn
    over: the cycle exists and metering has published the calendar since
    `DEF-2708`. On the PO's own case a 12-day closing window on a 30-day cycle
    was billed **$18.50** whole where 12/30 gives **$7.40** — **$11.10 too
    much** on a customer who is leaving. **The other five kinds are untouched**
    and everything below still describes them exactly.

    ⚠ **THIS IS A REPORTED GAP AND NOT A SHRUG.** B4.3 prorates
    `service_days / cycle_days`, so the denominator decides how much of a base
    charge a partial window carries. With no cycle on the run there is nothing
    to read it from, and every engine then defaults it to the window's OWN
    length — which yields a factor of 1 and charges a FULL month's base for a
    seventeen-day interim bill.

    Worked, on WE-6's own figures: a 20-day window against a 31-day cycle
    prorates three base charges to **7.74 / 5.16 / 11.61**; against a 20-day
    denominator they are **12.00 / 8.00 / 18.00** — the customer pays **$13.49**
    too much on one bill.

    It is NOT closed by guessing 30, or by reading the tenant's commonest cycle:
    both are figures no signed document contains, and B4.3 is ❄️ frozen — the
    RULE is not in question, the INPUT it divides by is missing.

    ⚠ **OQ-242 IS WITHDRAWN, NOT ANSWERED (CR-029 D8④, PO 2026-08-23).** Asked
    for the denominator, the Product Owner replied *"this is not required"*. So
    **no proration rule is built here and none may be invented later without a
    new ruling**: the factor stays 1, a partial one-time window carries a full
    base charge, and that is the product's answer rather than a pending one. The
    figures above are kept because the tab still states the consequence on
    screen and a reader deserves to know its size.

    It errs toward OVER-charging, which is the worse direction for a customer
    and the better one for being noticed — an under-charge is never queried.
    That is not a justification for leaving it; it is why it is on the screen.
    """
    return None


#: `DEF-BIL-8330` — the one-time bill's own sentence for a first bill whose
#: account is on no billing cycle: *"No billing cycle. Assign one on the
#: account."* Read by `one_time_answer.account_problems` too, so the step-1
#: problem and the engine's refusal are one key.
NO_BILLING_CYCLE_KEY = final_bill.NO_BILLING_CYCLE_KEY

#: The kinds refused for an account on no cycle: the FIRST bill (`DEF-BIL-8330`,
#: PO 2026-09-30), the FINAL bill (PO 2026-10-01, *"same as first bill"*) and the
#: INTERIM bill (PO 2026-10-01, *"A · Cut down (10/30)"*, `BR-BIL-1066`). All
#: three prorate over the CYCLE's length (B4.3) and an account with no cycle has
#: none. Catch-up, penalty and fee bills are not prorated by a cycle.
KINDS_NEEDING_A_CYCLE = (KIND_FIRST, KIND_FINAL, KIND_INTERIM)


def account_has_a_billing_cycle(account_id: Any) -> bool:
    """Whether the account's unit bills on exactly ONE cycle — the card's *Cycle*.

    Read through the SAME metering seam the step-1 card reads its cycle name
    from (`cycle_terms_for_unit`), so the card saying *None* and a first bill
    being refused are one fact and cannot disagree. A unit on no cycle, on TWO
    cycles, or a premises-anchored master account with no unit all answer
    False: each is an account with no single cycle length to prorate over.
    Customers' own read refuses an unknown or another tenant's id (hard rule 1).
    """
    detail = gather._resolve("customers", "account_detail")
    terms = gather._resolve("metering", "cycle_terms_for_unit")
    if detail is None or terms is None:
        return False
    unit_id = (detail(account_id) or {}).get("unit_id")
    return bool(unit_id) and terms(unit_id) is not None


def refuse_a_bill_with_no_cycle(account_id: Any, *, kind: str) -> None:
    """🔒 A FIRST or FINAL bill for an account on no billing cycle is REFUSED.

    The first bill is `DEF-BIL-8330` (below); the final bill is the PO's ruling
    of 2026-10-01, verbatim: *"show warning and A · Refuse until the account has
    a cycle (same as first bill)"*. Worked: Maria moves out on the 10th, her
    account has no cycle, and the final bill charged the whole month's
    **$30.50** base for ten days. Same key, same step-1 problem, same question
    asked through the same seam. `final_bill.prepare_final_bill` refuses the
    same way behind this, so the move-out wizard's door is closed too.
    """
    if kind == KIND_FIRST:
        refuse_a_first_bill_with_no_cycle(account_id)
        return
    if kind == KIND_INTERIM and not account_has_a_billing_cycle(account_id):
        # PO 2026-10-01 — an interim bill's base is `base × days / the account's
        # own cycle length` (`BR-BIL-1066`). With no cycle there is no length,
        # and falling back to the window's own would charge the base whole —
        # silently, which is the case the ruling exists to end. Refused the
        # first bill's way, with its key and its sentence.
        raise BillingRuleError(
            "this account is on no billing cycle, so its interim bill has no cycle "
            "length to prorate the base over (B4.3) and is refused until a cycle is "
            "assigned (PO ruling 2026-10-01, OQ-242 option (a) — same as the first bill).",
            br_ref="BR-BIL-1066",
            message_key=NO_BILLING_CYCLE_KEY,
        )
    if kind == KIND_FINAL and not account_has_a_billing_cycle(account_id):
        raise BillingRuleError(
            "this account is on no billing cycle, so its final bill has no cycle length "
            "to prorate over (B4.3) and is refused until a cycle is assigned "
            "(PO ruling 2026-10-01, option A — same as the first bill).",
            br_ref="BR-BIL-013",
            message_key=NO_BILLING_CYCLE_KEY,
        )


def refuse_a_first_bill_with_no_cycle(account_id: Any) -> None:
    """`DEF-BIL-8330` — a FIRST bill for an account on no billing cycle is REFUSED.

    HUMAN-REVIEW-PENDING · 🔒 money path (this file is on `human_owned.txt`).

    PO ruling 2026-09-30, option A, verbatim: *"you have to show the message
    /warning to user - A · Refuse until the account has a cycle"* (BR-BIL-012,
    decision log). BR-BIL-012 prorates a first bill from the move-in day over
    the CYCLE's length (B4.3 ❄️); an account with no cycle has no length, and
    the window's own length stood in for it — a factor of 1. **Worked, the
    PO's case:** a ONE-day first bill for John Mauli (AC-2026-00054) priced
    **$418.00**, the same as a whole month.

    Asked BEFORE anything is gathered or priced, in the preview and the draft
    alike, so no door into this module can price one. The API asks the same
    question at step 1 (`one_time_answer.account_problems`), so a clerk meets
    it on the account field; this is the engine's own refusal behind it.
    """
    if not account_has_a_billing_cycle(account_id):
        raise BillingRuleError(
            "this account is on no billing cycle, so its first bill has no cycle length "
            "to prorate over (B4.3) and is refused until a cycle is assigned "
            "(PO ruling 2026-09-30, option A).",
            br_ref="BR-BIL-012",
            message_key=NO_BILLING_CYCLE_KEY,
        )


def first_bill_cycle_days(
    request: OneTimeRequest, moved_in_on: date, period_start: date, period_end: date
) -> int:
    """B4.3's ❄️ DENOMINATOR for a FIRST bill — the length of the cycle moved into.

    HUMAN-REVIEW-PENDING · 🔒 money path (this file is on `human_owned.txt`).

    `DEF-BIL-8331` — signed law, not a question (decision log 2026-09-30,
    coordinator under BR-BIL-012 and B5 GT-3). BR-BIL-012: *"First bill:
    prorated from move-in day (B4.3)"*; GT-3 ❄️: *move-in day 16 of 30; base
    $30.50; 15/30 × 30.50 = 15.25*. This line used to be `_cycle_days(request)
    or (period_end − period_start) + 1` — the bill's OWN length, a factor of 1 —
    so every first bill charged the whole base: GT-3's account paid **$30.50**
    where **$15.25** is due, and the PO's one-day bill for John Mauli cost what
    a month does.

    **Reuse, not a third implementation:** the cycle length is read exactly as
    the final bill reads it (`final_bill._closing_cycle_days` → metering's
    `billing_period_for_unit`), on the MOVE-IN day, because that is the cycle the
    customer moved into (the mirror of the final bill reading on the move-out
    day). A first bill with NO cycle never gets here (`DEF-BIL-8330`). Where the
    cycle exists but its calendar cannot be read (a pre-`CR-029` cycle with no
    frequency or first run), the window's own length is used, which is exactly
    the behaviour before this function — the final bill's documented fallback,
    so an unreadable cycle never makes a bill worse than it was.
    """
    return _the_accounts_cycle_days(request, as_of=moved_in_on, period_start=period_start, period_end=period_end)


def interim_bill_cycle_days(request: OneTimeRequest, period_start: date, period_end: date) -> int:
    """B4.3's ❄️ DENOMINATOR for an INTERIM bill — the account's own cycle length.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING · 🔒 money path (this file is on
    `human_owned.txt`; row in `12-governance/09-human-review-ledger.md`,
    2026-10-01 *"AN INTERIM BILL CUTS THE BASE DOWN BY DAYS"*).

    PO ruling 2026-10-01 (decision log *"TWO PO RULINGS ON THE BASE CHARGE"*,
    (1); `OQ-242` option (a), CLOSED for interim bills; `BR-BIL-1066`), verbatim:
    *"Should interim bills cut the base down like first and final bills? A · Cut
    down (10/30)"*. **Worked, the PO's case:** an interim bill for 10 days of a
    30-day cycle on a **$30.50** base charged **$30.50** whole; 10/30 × 30.50 is
    **$10.17**. On WE-6's frozen figures a 20-day window of a 31-day cycle
    prorates three bases 12.00 / 8.00 / 18.00 to **7.74 / 5.16 / 11.61 =
    $24.51** (it charged **$38.00**).

    **Not a change to frozen B4.3** — the rule already divides by the cycle's
    length; the interim path passed the WINDOW's length instead (factor 1). This
    reads the ACCOUNT's cycle exactly as the first and final bills do
    (`_the_accounts_cycle_days` → `final_bill._closing_cycle_days` → metering's
    `billing_period_for_unit`). Nothing new computes a day count.

    ⚠ **`as_of` IS THE WINDOW'S LAST DAY**, the same day the interim bill is
    PRICED on (`service_date=period_end`, BR-RAT-007), so the tariff version and
    the cycle length are read for one and the same day. Never a clock (G6).

    An account with NO cycle never gets here — it is refused first
    (`refuse_a_bill_with_no_cycle`, the first bill's key and sentence). Where a
    cycle exists and its calendar cannot be read, the window's own length is
    used, the first and final bills' documented fallback. A window LONGER than
    the cycle is capped by `gather` (`service_days ≤ cycle_days`), so it carries
    one whole base, as before.

    ⚠ **SCOPE: INTERIM ONLY.** Catch-up and penalty bills divide each stated
    SUB-PERIOD by its own length (`backbill`), and a fee bill has no base; the
    ruling does not reach them and this function is not called for them.
    """
    return _the_accounts_cycle_days(request, as_of=period_end, period_start=period_start, period_end=period_end)


def _interim_part_cycle_days(request: OneTimeRequest) -> Any:
    """`CR-156-BRC10` — the denominator for ONE part of an interim (and, since
    `DEF-BIL-8749`, a FIRST) bill's window cut at a price change: the account's
    cycle length on that part's last day, `interim_bill_cycle_days`'s own rule
    applied per part; a stated `cycle_days` still wins. Worked: 10/16–10/31
    → 31, 11/01–11/15 → 30 (the PO's *"each part is prorated over its own
    month"*). The final bill reads the same per part inside
    `final_bill.prepare_final_bill`."""

    def per_part(part_start: date, part_end: date) -> int:
        # 🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` Q-b (PO 2026-10-12, *"each
        # part gets its share of the tier limits by days"*). Where the cycle's
        # calendar cannot be read the FALLBACK is the WHOLE WINDOW's length —
        # `final_bill.prepare_final_bill`'s own per-part fallback — never the
        # PART's. Falling back to the part's length made every part a factor
        # of 1: each part got the FULL first tier, and on the walk of
        # 2026-10-12 an 800 kWh read cut in three priced $91.60, below both the
        # old ($95.50) and the new ($103.50) price.
        return _the_accounts_cycle_days(
            request,
            as_of=part_end,
            period_start=request.period_start or part_start,
            period_end=request.period_end or part_end,
        )

    return per_part


def _the_accounts_cycle_days(
    request: OneTimeRequest, *, as_of: date, period_start: date, period_end: date
) -> int:
    """The one read the first and the interim bill share (the final bill reads
    the same helper from inside `final_bill.prepare_final_bill`).

    A stated `cycle_days` wins; otherwise the cycle's calendar length on `as_of`
    through `final_bill._closing_cycle_days`; otherwise the window's own length.
    Moved out of `first_bill_cycle_days` on 2026-10-01 unchanged, so the interim
    bill reuses it rather than carrying a second copy.
    """
    stated = _cycle_days(request)
    if stated:
        return stated
    detail = gather._resolve("customers", "account_detail")
    unit_id = (detail(request.account_id) or {}).get("unit_id") if detail else None
    days = final_bill._closing_cycle_days(unit_id, as_of=as_of) if unit_id else None
    return days or (period_end - period_start).days + 1


def first_bill_move_in(request: OneTimeRequest, period_start: date) -> date:
    """THIS first bill's move-in date — the date the clerk left on step 1.

    ── PO change 2026-09-30 (decision log *"ONE-TIME FIRST BILL: THE MOVE-IN
    DATE IS A DATE PICKER THE CLERK CAN OVERWRITE"*) ─────────────────────────
    PO verbatim: *"Move -date should have date picker cleark will overwrite
    it"*. The screen pre-fills it with the account's recorded move-in date
    (`accounts.opened_at`) and the clerk may change it for THIS bill. So the
    request's `period_start` IS the move-in date the bill is priced from — the
    deposit and the connection charge still apply — and the account's recorded
    date is never written here (*"overwriting changes the bill only"*).

    It superseded the read-only derivation (`_moved_in_on`, US-BIL-010 TC-6)
    FOR THE SCREEN; `_moved_in_on` stays the pre-fill's source and the answer's
    `account.moved_in_on`, so the screen can warn when the two differ.
    """
    return period_start


def _moved_in_on(account_id: Any) -> date:
    """The account's own move-in date — read, never typed (US-BIL-010 TC-6).

    `bill_type=first` is DERIVED from this date and a caller does not supply it.
    An account with no `opened_at` is refused by name rather than treated as
    having moved in on the period's first day: that assumption would put a
    deposit and a connection charge on the bill of somebody who has lived there
    for years.
    """
    detail = gather._resolve("customers", "account_detail")
    if detail is None:
        raise BillingRuleError(
            "customers has not published account_detail, so the move-in date a first "
            "bill is derived from cannot be read (US-BIL-010 TC-6).",
            br_ref="BR-BIL-012",
        )
    row = detail(account_id)
    raw = row.get("opened_at")
    if not raw:
        raise BillingRuleError(
            "this account records no move-in date, so no first bill can be derived for "
            "it (US-BIL-010 TC-6 — the type follows the move-in date and is never "
            "supplied). Assuming the period's first day would put a deposit and a "
            "connection charge on the bill of somebody who has lived there for years.",
            br_ref="BR-BIL-012",
        )
    return raw if isinstance(raw, date) else date.fromisoformat(str(raw))


def _account_type_id(account_id: Any) -> Any:
    """The consumer CATEGORY the deposit rule is keyed on (BR-RAT-020/023).

    `plan_deposit_rules` is keyed on rate_plan × account_type, so a first bill
    cannot resolve its deposit without one. Read from the account rather than
    accepted from the caller — a category a clerk could pick is a deposit figure
    a clerk could pick.

    ⚠ **THE KEY IS ASSERTED, NEVER `.get()`-ed (`DEF-BIL-5318`, 2026-09-15).**
    This line read `.get("account_type_id")` from 2026-08-16 until 2026-09-15 and
    the customers seam did not publish that key, so it answered `None` on EVERY
    account, `first_bill.deposit_line_for` refused by name on every account, and
    the first kind had never produced a bill through S30's tab. A missing KEY and
    a missing CATEGORY are different facts and only one of them is the
    customer's:
      * key ABSENT ⇒ OUR seam is wrong. Refused here, naming the seam and the
        field, so the next reader looks at customers and not at the account.
      * key present, value `None` ⇒ THIS ACCOUNT has no category. Travels on and
        `deposit_line_for` refuses in the customer's own language.
    `.get()` flattened the two into the second, which is how a seam defect was
    read for three weeks as a refusal about somebody's data three frames away.
    """
    detail = gather._resolve("customers", "account_detail")
    if detail is None:
        raise BillingRuleError(
            "customers has not published account_detail, so the consumer category the "
            "first bill's deposit rule is keyed on cannot be read (BR-RAT-020/023).",
            br_ref="BR-BIL-012",
        )
    blob = detail(account_id)
    if "account_type_id" not in blob:
        raise BillingRuleError(
            "customers' `account_detail` seam does not carry `account_type_id`, so the "
            "consumer category the first bill's deposit rule is keyed on cannot be read "
            "(BR-RAT-020/023). This names OUR read and not the account: the account has "
            "a category, the seam does not publish it. See DEF-BIL-5318.",
            br_ref="BR-BIL-012",
        )
    return blob["account_type_id"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-012@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md; co-packets US-BIL-010/011/013/014,
#         same four sources)
# generated: 2026-08-16 by Eng-Lead (S30 One-time bill tab lane — the door five
#         complete engines had never been given)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_012_one_time.py · run_gates
# exceptions: (1) ~~A ONE-TIME BILL CANNOT BE ISSUED~~ **CLOSED 2026-08-23 —
#         CR-029 D8③ ruled where a cycle-less bill's due-days come from:
#         *"it will be capture at the time of bulk billing - not here"*. The RUN
#         now carries `bill_date` + `due_days` and `issue._due_terms_for`
#         resolves run-then-cycle, so the bill issues on the terms the clerk
#         captured. OQ-241 closes as RULED. With no typed terms the derivation
#         still refuses by name — nothing is guessed, and that half is unchanged.
#         (2) `cycle_days` IS ALWAYS None, so a PARTIAL one-time window charges a
#         full period's base charge — WE-6's own figures put that at **$13.49**
#         on one bill. The denominator has no lawful source on a cycle-less run
#         and B4.3 is ❄️ frozen (the RULE is not in question; its INPUT is
#         missing). **OQ-242 is WITHDRAWN (CR-029 D8④, *"this is not
#         required"*)** — so this is now a RULED behaviour rather than a pending
#         question, and no proration rule may be added without a new ruling. Still
#         REPORTED in `_cycle_days`' docstring, on `ONE_TIME_UNAVAILABLE` and on
#         the screen before a clerk drafts. ⚠ **NARROWED 2026-10-01: FIRST,
#         FINAL AND INTERIM BILLS ARE OUT OF THIS EXCEPTION.** The PO ruled the
#         interim bill *"A · Cut down (10/30)"* (`OQ-242` option (a) for
#         interim, `BR-BIL-1066`): 10/30 × $30.50 = $10.17, and WE-6's 20/31
#         gives 7.74 / 5.16 / 11.61 = $24.51. It now reads the account's own
#         cycle (`interim_bill_cycle_days`) and is refused with no cycle. What
#         remains of (2) is catch-up, penalty and fee bills.
#         (3) NO FREE-TYPED AMOUNTS, and the enforcement is STRUCTURAL rather
#         than a validation: `OneTimeRequest` has no amount, description or line
#         member and no function here takes one. BR-BIL-020 supersedes the
#         prototype's editable line inputs and its "+ Add line" button in writing.
#         (4) THE PROTOTYPE'S FOURTH KIND, "Deposit invoice", IS NOT BUILT — no
#         story in EP-BIL-03 owns it (law 8). Named on screen, not dropped.
#         (5) CLOSED 2026-09-15 by `DEF-BIL-5317`. It read "A PENALTY BILL
#         CARRIES NO TAMPER FEE. Rating publishes no charge-code read, so
#         `penalty.penalty_charge_line` refuses every code; `charge_codes=()` is
#         passed deliberately". Rating HAD published it — `charge_by_code`, read
#         by `fee_bill.charge_code_line` since 2026-08-27 — and `penalty` was
#         asking for a name (`charge_ref`) that never existed. The code the
#         clerk picks on step 2 now reaches `prepare_penalty_bill`, is priced
#         from the tenant's own row (`TAMPER` = $250.0000, PO 2026-08-10) and
#         rides `extra_fees` onto the document.
#         (6) NO `final_settlements` TABLE EXISTS, so a final bill's settlement
#         is COMPUTED and stored nowhere; the body says `recorded: false` rather
#         than letting a screen imply it was saved. `final_bill.py` owns the gap.
#         (7) The preview serves NO TOTAL. A prepare pass prices nothing, and a
#         zero standing in for "not computed" is a money claim on a bill preview.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
