# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (EP-CUS-02 S20 Move-Out — step 3's money, step 4's
#           shortfall decision, the refund path)
#           Screens: S20 (steps 3 and 4)
# Rules:    BR-CUS-025 (the deposit + BR-CUS-057 interest settle EVERYTHING
#           OUTSTANDING — amended 2026-08-12, PO, OQ-158) · BR-CUS-030
#           (move-out; its `dunning stops` clause superseded for the
#           closed-with-balance case) · BR-CUS-031 (the final-bill handoff
#           contract) · BR-CUS-057 (deposit interest — customers' accrual,
#           NOT BUILT) · BR-CUS-068 (a master account is an ordinary
#           `accounts` row, `kind='master'`) · BR-CUS-081 (a closing balance
#           the deposit more than covers is SETTLED and the difference
#           REFUNDED — PO 2026-08-24, OQ-347) · BR-CUS-082 (a debt surviving
#           closure is still chased; the ladder restarts at TIER 1 — PO
#           2026-08-24, OQ-346) · BR-CUS-096 (an OPEN DISPUTE HOLDS the excess
#           — PO 2026-08-24, closing DEF-653; SUSPENDED 2026-10-11 while
#           nothing records a dispute — no store answers 0.00) · BR-CUS-097 (a sub-account's
#           unpayable residue transfers to its MASTER — PO 2026-08-24) ·
#           BR-MET-105a (the owner is a real party — PO 2026-08-24, closing
#           DEF-650) · BR-MET-107 (an unbanked export credit is APPLIED to the
#           final bill, never forfeited — PO 2026-08-24, closing DEF-654) ·
#           BR-BIL-013 (the settlement matrix and its CLOSED path set) ·
#           BR-PAY-012 (a deposit is a liability, never revenue; unapplied
#           money is an account credit and MAY BE NEGATIVE) · BR-PAY-020
#           (a write-off is NOT a move-out path — PO 2026-10-12, *"MOVE-OUT
#           DOES NOT WRITE OFF"*; it is done later, separately, in Payments) ·
#           CLAUDE.md rule 2
#           (money 4dp stored, 6dp percentages, both DISPLAY 2 — never float) ·
#           rule 4 (corrections are new rows, never edits) · rule 7 (every
#           money action writes `audit_log`)
# Journeys: J08 (the move-out close and its shortfall paths) · T4-06 step 1
# Design:   04-docs/02-decisions/19-cr031-service-request-capture.md §15.9 —
#           "THE FIVE MONEY LANDINGS", captured 2026-08-24 from the PO's own
#           move-out screenshots, with every figure. §15.12 is the handover
#           list this module implements items 1, 3 and 4 of.
# Tests:    06-backend/tests/test_w5_move_out_settlement.py
# ───────────────────────────────────────────────────────
"""W5 · the move-out settlement — ONE computation, five money landings.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides how much of a closing
customer's own money comes back to them, under CLAUDE.md's 🔒 *money rounding*
and *rating math*. AI-authored 2026-08-24 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*).
⚠ **NOT ON THE G7 GLOB LIST** (`10-scripts/gates/human_owned.txt`) and NO ROW IN
`12-governance/09-human-review-ledger.md` — both are process events this lane may
not take alone (B12 r2, *"who watches the watchers"*), so both are REPORTED for
the daily PO batch exactly as the five globs of 2026-08-11 record. A marker no
gate reads is hard-won law 1; this paragraph says so rather than implying the
guard exists.

════════════════════════════════════════════════════════════════════════════
THE FIVE LANDINGS ARE ONE SUBTRACTION — B19 §15.9
════════════════════════════════════════════════════════════════════════════
The PO walked all five positions of the prototype's `HOW THE MONEY LANDS`
switch on 2026-08-24 (*"At step 3 - llok at all variations based on
scenarios"*). The switch itself is **NOT BUILT** — B19 §15.1, PO verbatim:
*"this is only for reference not for design"*. A clerk does not choose how the
money lands; the account's own position decides it.

    final bill net = final bill − unbanked export credit  ← BR-MET-107
    outstanding    = prior balance + final bill net       ← "Everything outstanding"
    applied        = deposit held + deposit interest
                     + unapplied credit on THIS account   ← "What is applied against it"
    net            = outstanding − applied                ← the verdict figure

and the landing is read off `net` plus the customer's other accounts and any
open dispute:

    net  >  0                          → `short`
    net == 0                           → `settled`
    net  <  0 and an open DISPUTE      → `refused_excess`      (BR-CUS-096, held)
    net  <  0 and a sibling DEBT       → `refused_other_debt`
    net  <  0 otherwise                → `refund_due`          (BR-CUS-081)

**Five screens, one arithmetic.** `derive()` below is that subtraction and
nothing else; there is no branch in it that computes a different number for a
different landing, because a second arithmetic is how two of the five
eventually disagree about the same customer.

B19 §15.9.1's figures, every one reproduced in the test file:

| landing              | outstanding | applied  | verdict           |
|----------------------|-------------|----------|-------------------|
| `settled`            |    153.50   |  153.50  | 0.00              |
| `refund_due`         |     94.45   |  153.50  | −59.05 refunded   |
| `short`              |    324.24   |  153.50  | short by 170.74   |
| `refused_other_debt` |     94.45   |  153.50  | −59.05 to sibling |
| `refused_excess`     |    140.38   |  153.50  | −13.12 HELD       |

The `applied` of **153.50** is ❄️ **WE-7 / GT-23's frozen pair** — a $150.00
deposit held 14 months at the tenant's 2% simple rate earns **$3.50**
(BR-CUS-057) — so these five screens and the frozen golden test are settling
the same money.

⚠ **THOSE FIVE FIGURES PREDATE `BR-MET-107` AND ONE OF THEM IS NOW WRONG ON
THE PROTOTYPE.** The screens were drawn while an unbanked export credit was
*"forfeited on close"*, which the PO rejected on 2026-08-24. The same
`refused_excess` account holds **$4.10** on `M-4023` (B19 §15.10), so under
BR-MET-107 its final bill nets to **90.35**, everything outstanding to
**136.28**, and the excess to **17.22** — not the **13.12** printed in step 3's
verdict AND in step 6's read-back (*"Excess $13.12 pending decision"*). The
five rows above are reproduced with **no export credit**, which is what those
screens actually showed; BR-MET-107's own $4.10 is driven separately in the
test file. REPORTED, not reconciled here.

════════════════════════════════════════════════════════════════════════════
BR-CUS-025, QUOTED, BECAUSE THE WHOLE SHAPE HANGS ON ONE WORD
════════════════════════════════════════════════════════════════════════════
Amended 2026-08-12 (PO, OQ-158 → BR-BIL-013), verbatim:

  *"⚠ AMENDED 2026-08-12 (PO, OQ-158 CLOSED → BR-BIL-013): THE DEPOSIT SETTLES
  EVERYTHING OUTSTANDING, NOT JUST THE FINAL BILL. … A customer who leaves
  owing a final bill AND an older arrear has the deposit applied against the
  whole closing position; applying it to the final bill alone would refund a
  customer who still owes the utility money."*

Worked with the ruling: a **$120.84** arrear inside a *Final amount due* of
**$184.20** against a **$153.50** deposit. Bill-only settles 63.36 and refunds
**$90.14** to a customer still $120.84 in debt; whole-position settles 184.20
and collects **$30.70**. That is why `outstanding` is a SUM of two terms here
and why a caller cannot pass the bill alone.

════════════════════════════════════════════════════════════════════════════
BR-MET-107, QUOTED — THE EXPORT CREDIT COMES OFF FIRST
════════════════════════════════════════════════════════════════════════════
PO 2026-08-24, closing DEF-654, verbatim: *"apply it to the final bill"*.

  *"Where a customer closes an account holding export credit their own
  generation earned and the utility has not yet paid out, that credit reduces
  what they owe at closure; only what remains after it follows the ordinary
  settlement path (deposit, then BR-CUS-081/096)."*

Worked: **$4.10** on `M-4023 · Net meter · electric`. So the export credit is
applied to the FINAL BILL — the PO's own noun — and the deposit then settles
everything outstanding, in that order.

⚠ **WHAT THE RULING DOES NOT SETTLE, AND IS NOT INFERRED HERE:** what happens
when the credit **EXCEEDS** the final bill. BR-MET-107 says where it goes
FIRST, not whether the remainder is refundable, carried, or held. So a credit
larger than the bill is a **GAP** — no landing is stated, the reason names
BR-MET-107, and nothing is floored at zero. Flooring would silently confiscate
the difference, which is the confiscation this ruling was made to stop.

════════════════════════════════════════════════════════════════════════════
BR-CUS-081 AND BR-CUS-096 — THE REFUND, AND THE ONE CONDITION ON IT
════════════════════════════════════════════════════════════════════════════
BR-CUS-081 (PO 2026-08-24, closing OQ-347), verbatim:

  *"A CLOSING BALANCE THE DEPOSIT MORE THAN COVERS IS SETTLED FROM THE DEPOSIT
  AND THE DIFFERENCE IS REFUNDED — THE BILL DOES NOT STAND. … deposit
  $153.50, owed $142.30 → settle the $142.30 and refund $11.20. … Settlement
  and refund are BOTH money actions and both write `audit_log`; the settlement
  is a new row, never an edit of the issued bill (hard rule 4)."*

BR-CUS-096 (PO 2026-08-24, closing DEF-653), verbatim: *"hold until dispute
close"* —

  *"an open dispute on any part of the outstanding amount HOLDS the excess …
  $153.50 against $140.38 leaves $13.12, and $48.00 of that $140.38 is
  disputed — so the $13.12 is held, not refunded. ⚠ BR-CUS-081 IS NOT
  REVERSED."*

So `settled_amount` is `min(outstanding, applied)` and `refund_amount` is the
difference — **not** "refund the whole deposit and leave the bill standing",
which the PO explicitly rejected — and the refund is reachable only when
nothing is disputed. Both are recorded as NEW rows: nothing in this module
updates an issued invoice, a payment or a journal line, and it could not —
customers writes none of those tables (B1 module map).

⚠ **NOT SETTLED, AND NOTHING HERE PRETENDS OTHERWISE:** *who releases a held
excess when the dispute closes, and on what clock*. BR-CUS-096 says so in its
own text. `hold_excess()` records the hold and reports that **nothing chases
it** — there is no release path, no timer and no queue in this repository, so
the money would sit until a human looked. Stated on the payload rather than
left to be discovered.

⚠⚠ **BR-CUS-096 IS SUSPENDED — PO RULING 2026-10-11, AND NO STORE NOW MEANS
NO DISPUTE.** Verbatim: *"today we are not handling any disppute case not
recodingt he dispute anywhere. hence dispute check doe snot work, I think we
should remove it fo time being and process the refund"* (decision log, option
A). Worked as shown: Maria Lopez's **$150.00** deposit pays her **$90.00** final
bill and the **$60.00** is refunded or carried, not held.

**UNTIL THAT RULING THIS PARAGRAPH SAID THE OPPOSITE** — *"a dispute that
cannot be read is a gap, not an absence"* — and so, because nothing in this
repository stores a disputed AMOUNT (measured 2026-08-24: no model, no
`db_table`, no seam, no publisher), every excess landing stated **no landing at
all** and no refund could ever land. `_open_dispute_total` now answers **0.00**
when no `billing.open_dispute_total` seam is published. ⚠ **"FOR THE TIME
BEING" IS PART OF THE RULING:** the seam is still read FIRST, so the day a
dispute store lands the hold (`refused_excess`) returns with no change here, and
a published store that cannot answer is still a gap.

⚠ **AND THE ONE THING THAT LOOKS LIKE A DISPUTE STORE IS NOT IT** —
`apps.metering.models` carries `disputed_at` / `dispute_reason` /
`dispute_cleared_at` on a METER READ. A read dispute is a quantity in dispute,
not a sum of money, and BR-CUS-096 conditions on *"an open dispute on any part
of the outstanding AMOUNT"*. Wiring the read flag into this rule would hold a
customer's refund because somebody queried a dial. Named here because it is the
obvious wrong wire.

════════════════════════════════════════════════════════════════════════════
BR-CUS-082 AND BR-CUS-097 — WHERE A SHORTFALL GOES
════════════════════════════════════════════════════════════════════════════
BR-CUS-082 (PO 2026-08-24, closing OQ-346), verbatim: *"(b) continue, ladder
restarts"* —

  *"A DEBT SURVIVING ACCOUNT CLOSURE IS STILL CHASED, AND THE DUNNING LADDER
  RESTARTS FROM TIER 1. … a closed account cannot be escalated to
  disconnection — there is nothing left to disconnect — and the ladder for a
  closed account is a collections sequence, not a service one."*

Worked: `A-11024 · Ridge Coffee Co.` closes owing **$328.70** against
**$153.50** — a **$175.20** shortfall.

BR-CUS-097 (PO 2026-08-24, from DEF-651), verbatim: *"master account gets debt
- if sub accoun tis unable to pay it ; even aftr deposite settlement"*. The
residue moves to the master account the sub-account hangs off.

⚠ **THE TWO RULINGS DO NOT RESOLVE EACH OTHER AND THIS MODULE DOES NOT EITHER.**
BR-CUS-097's own text: *"If the residue moves to the master, who is chased —
the departed sub-account holder or the master account? The two rulings do not
resolve that between them, and W7 must not build both readings."* So
`shortfall_decision()` records the transfer and **states no dunning subject**;
the `dunning` block of its result carries the restart-at-TIER-1 fact and the
unresolved subject side by side, for W7 to inherit as a fact rather than a
guess. It also means BR-CUS-030's `dunning stops` is NOT true of a `short`
close, and is not a constant anywhere in the product (B19 §15.10).

**THE TRANSFER TARGET IS RESOLVED, NEVER SUPPLIED.** BR-CUS-097 says *"a
transfer cannot be built against an ambiguous target"*, so the master is read
from the data through published selectors and a caller-supplied account id is
not a parameter of any function here — which is what makes US-BIL-011 TC-6's
forged transfer unrepresentable rather than merely rejected. Where no master
resolves, or where more than one does, the path REFUSES and names BR-CUS-097's
open no-master case.

════════════════════════════════════════════════════════════════════════════
BR-MET-105a — THE OWNER IS A PARTY, AND THE COLUMN IS STILL MISSING
════════════════════════════════════════════════════════════════════════════
PO 2026-08-24, closing DEF-650, verbatim: *"Make the owner a real party"*. The
rule names `premises.owner_customer_id` — *"the nullable FK W0 added beside the
free-text `owner_manager`"* — as the posting target.

⚠ **MEASURED ON THIS TREE, 2026-08-24: THAT COLUMN DOES NOT EXIST.**
`apps/metering/models.Premises` carries `owner_manager` (TextField, nullable)
and nothing else about an owner; no migration in `apps/metering/migrations/`
mentions `owner_customer`; nothing in `06-backend/apps/**` references the name.
So BR-MET-105a is CONFIRMED and, on the code, still unbuildable for the exact
reason DEF-650 was filed. This module therefore offers the owner as a transfer
target that REFUSES with that measurement, rather than posting a shortfall to a
string. REPORTED — the column is a metering migration and belongs to that lane.

════════════════════════════════════════════════════════════════════════════
CREDITS DO NOT TRAVEL; DEBTS DO — AND NOTHING SIGNS IT (REPORTED)
════════════════════════════════════════════════════════════════════════════
B19 §15.9.4 records the prototype's deliberate restraint: a credit sitting on
ANOTHER of the same customer's accounts is **shown and never applied** —
`Credit on A-09984 · Available · $61.40` beside a shortfall of `$170.74` that
it would cut by more than a third — while §15.9.5's **debt** on a sibling
account IS acted on and seizes the refund.

Nothing signed says either half. BR-CUS-097 signs the SHORT direction (residue
→ master); the excess direction is drawing only. It is implemented as drawn,
and the question is REPORTED rather than answered: `SiblingPosition.disposition`
names the behaviour (`shown_not_applied` / `applied`) so a ruling changes one
constant rather than five call sites, and every settlement holding one carries
`sibling_credit_rule_unsigned` — which now cites **`OQ-362`**, the row that will
close it. A flag naming no row outlives its reason and nobody notices (DEF-445).

⚠ **WHERE A DISPUTE AND A SIBLING DEBT ARE BOTH PRESENT, THE DISPUTE WINS, AND
THAT IS A DERIVATION RATHER THAN A CHOICE.** BR-CUS-096 is SIGNED and holds the
excess *because the amount owed can still move*; the sibling-debt seizure is
unsigned prototype behaviour, and transferring money that may still be owed
elsewhere is exactly the irreversible act the signed rule prevents. Signed law
over a drawing — stated here so the ordering is auditable.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE REFUSES TO ANSWER, AND WHY EACH IS A REFUSAL NOT A DEFAULT
════════════════════════════════════════════════════════════════════════════
Hard-won law 3 — the unsafe option must be the one you type. A settlement is an
amount of a customer's money going back or not going back on an account nobody
will look at again, so every gap here fails CLOSED: `landing` is None and
`complete` is False, rather than a landing derived from a term quietly read as
zero.

  * **BR-CUS-057's deposit interest is NOT BUILT.** `apps.customers.selectors.
    deposit_interest_accrued` is published by nothing (US-CUS-023 §7), which is
    the same wall `apps/billing/final_bill.deposit_credit_for` hits. An account
    that HOLDS a deposit cannot be settled today, and this module refuses
    rather than applying principal alone: WE-7's **$3.50** on 14 months and
    GT-61's **$22.25** on 89 months is the customer's money, and a
    principal-only settlement foots perfectly while keeping it. An account with
    NO deposit settles normally — there is nothing to accrue on.
  * **The final bill is STATED by the caller, never read.** Billing publishes
    no per-account final-bill total (`apps/billing/selectors.py` has none), and
    `apps/billing/final_bill.settle_final_bill` reads the figure off the
    drafted `invoices.total` for exactly the reason repeated here: the figure
    the deposit is applied to must be the figure the customer was billed. Until
    a seam exists the wizard passes it and the payload says it was stated.
  * **There is no `final_settlements` table** (US-BIL-011 §5 names one; B2 and
    its addenda carry none), so the landing, the chosen path, the refund method
    and the hold are COMPUTED and ride the `audit_log` row. "Exactly one
    settlement per close" holds within a call and not across calls.

════════════════════════════════════════════════════════════════════════════
MONEY SHAPE (CLAUDE.md rule 2, PO re-sign 2026-08-22)
════════════════════════════════════════════════════════════════════════════
*"MOney 4 decimal, percentage 6 decimal, display both 2 decimal"*. Every figure
here is a `Decimal`; nothing is coerced through float; no arithmetic rounds.
`serialize()` emits BOTH shapes and labels them — a 4dp `stored` string for
anything that would be written and a 2dp `display` string for the screen — so a
caller never has to decide which one it is holding. Rounding happens once, in
`core.money.finalize` (B4 ❄️, half-up, 2dp), and only on the display leg.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.customers import models, seams
from core import audit as core_audit
from core import errors, money
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")
FOUR_DP = Decimal("0.0001")

# ── the five money landings (B19 §15.9.1) — a CLOSED set ────────────────────
#: A sixth landing would be a sixth way for a closed account to end up with an
#: unexplained balance, which is why BR-BIL-013's own path set is closed too.
LANDING_SETTLED = "settled"
LANDING_REFUND_DUE = "refund_due"
LANDING_SHORT = "short"
LANDING_REFUSED_OTHER_DEBT = "refused_other_debt"
LANDING_REFUSED_EXCESS = "refused_excess"
MONEY_LANDINGS: tuple[str, ...] = (
    LANDING_SETTLED,
    LANDING_REFUND_DUE,
    LANDING_SHORT,
    LANDING_REFUSED_OTHER_DEBT,
    LANDING_REFUSED_EXCESS,
)

#: B19 §15.9.1's last column: step 4 is LIVE in one landing and greyed-and-named
#: in the others. It is never skipped silently — the step bar draws
#: `4 · Shortfall · skipped` — so this is a property of the landing.
STEP_4_LIVE_IN: frozenset[str] = frozenset({LANDING_SHORT})

# ── the refund methods (B19 §15.9.3) — a CLOSED vocabulary ──────────────────
#: *"`ACH` | `Mailed cheque` | `Carry to new account`"*. `carry_to_new_account`
#: is a METHOD and not an exception: a refund becomes an opening credit on the
#: customer's NEXT account with no money moving.
REFUND_ACH = "ach"
REFUND_CHEQUE = "mailed_cheque"
REFUND_CARRY = "carry_to_new_account"
REFUND_METHODS: tuple[str, ...] = (REFUND_ACH, REFUND_CHEQUE, REFUND_CARRY)

#: *"ACH reuses the bank details on file. A cheque needs a forwarding address."*
#: The `*` in the prototype is on `Street` and on nothing else, so the address
#: is required for the cheque ALONE — requiring it of an ACH refund blocks a
#: payout that needs no address, and requiring nothing posts a cheque to an
#: empty envelope.
REFUND_METHODS_NEEDING_ADDRESS: frozenset[str] = frozenset({REFUND_CHEQUE})

# ── the three shortfall paths (task 5.8) ────────────────────────────────────
#: BR-BIL-013's CLOSED set minus `refund`, which is the other direction, and
#: minus `write_off` (below). Named with billing's own constants rather than a
#: second vocabulary — two spellings of one settlement path is how two modules
#: eventually disagree about what happened to a closing balance.
SHORTFALL_COLLECT = "collect"
SHORTFALL_PAYMENT_PLAN = "payment_plan"
SHORTFALL_TRANSFER = "transfer"
SHORTFALL_PATHS: tuple[str, ...] = (
    SHORTFALL_COLLECT,
    SHORTFALL_PAYMENT_PLAN,
    SHORTFALL_TRANSFER,
)

#: ⚠ **NOT A MOVE-OUT PATH — PO RULING 2026-10-12** (decision log, *"MOVE-OUT
#: DOES NOT WRITE OFF"*), verbatim: *"we will not write off at the time of move
#: out; these charges remain outstanding on the account and followup is done as
#: per outstanding rules"*, and on who writes it off: *"fianance or system admin
#: will do it seperately later"*. So the shortfall stays outstanding on the
#: closed account and BR-CUS-082 chases it (the ladder restarts at tier 1); a
#: write-off is a later, separate act in Payments → Debtors under BR-PAY-020.
#: Named here ONLY so `shortfall_decision` can refuse it BY NAME — a caller
#: still sending the value the 2026-10-11 build accepted gets a sentence, not
#: the generic unknown-path refusal. It superseded the 2026-10-11 row that
#: raised a payments write-off REQUEST from step 4 (`db7b2808d`), which is gone.
SHORTFALL_WRITE_OFF_REFUSED = "write_off"

#: Who a transfer may lawfully post to. TWO targets and two different rulings,
#: both of 2026-08-24, so they are named rather than collapsed: a shortfall
#: landing on a master account (BR-CUS-097) and one landing on the premises'
#: owner (BR-MET-105a) are different money on different books.
TRANSFER_TARGET_MASTER = "master_account"
TRANSFER_TARGET_OWNER = "premises_owner"
TRANSFER_TARGETS: tuple[str, ...] = (TRANSFER_TARGET_MASTER, TRANSFER_TARGET_OWNER)

#: ⚠ **THIS CONSTANT SAID THE OWNER COULD NEVER BE A POSTING TARGET, AND THAT
#: STOPPED BEING TRUE (`CR-056` W6 task 27, `DEF-2951`).** Its measurement was
#: accurate when it was taken: BR-MET-105a asks for `premises.owner_customer_id`
#: and no such column was ever added. **What landed instead is a better answer to
#: the same rule** — a TYPED OWNER ROW (`premises_owners`, CR-039 wave C) with an
#: account of its own (`premises_owners.master_account_id`, `BR-MET-1010`), which
#: is what *"make the owner a real party"* was asking for. The column the rule
#: NAMED is still absent; the FACT the rule wanted is on file. So the reason a
#: shortfall could not reach an owner is gone, and this constant now records only
#: the case that genuinely remains: **no owner is declared for this address, or
#: the declared owner has no account yet.**
#:
#: ⚠ **AND THAT REMAINING CASE IS A FAULT, NOT A SILENCE** (PO 2026-09-01, and
#: `CR-056` task 22 says the same of the empty unit): *"for as long as an address
#: carries only a name, it has no owner account — so an empty unit there still
#: has nowhere to post its standing charge. That is the old defect, surviving on
#: the old data."* It ends address by address as owners are identified. It is
#: never closed by inventing a party (PO 2026-08-31, ruling 2).
OWNER_TARGET_UNAVAILABLE = (
    "this address has no owner account to post to. BR-MET-105a makes the owner a real "
    "party and CR-056 gives every address its owner a Master Account — but this premises "
    "either names no typed owner at all (only free text, which is a name and not a party) "
    "or names one whose account has not been opened yet. The PO ruled on 2026-09-01 that "
    "an owner's account appears when the owner is IDENTIFIED, never at a migration that "
    "would invent one, so the residue is not moved anywhere and this is reported as a "
    "fault rather than passed over in silence."
)


def _money(value: Any, what: str) -> Decimal:
    """A money figure or a refusal — NEVER a float and never a silent zero."""
    if isinstance(value, Decimal):
        return value
    if value is None or isinstance(value, float):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-025",
            message_key="customers.move_out.money_not_a_decimal",
            params={"what": what, "value": repr(value)},
        )
    return Decimal(str(value))


def _stored(amount: Decimal) -> str:
    """CLAUDE.md rule 2 as re-signed 2026-08-22 — money is STORED to 4dp."""
    return str(amount.quantize(FOUR_DP))


def _display(amount: Decimal) -> str:
    """…and DISPLAYED to 2, rounded once, by B4's ❄️ frozen half-up rule."""
    return str(money.finalize(amount))


def _pair(amount: Decimal | None) -> dict[str, str | None]:
    if amount is None:
        return {"stored": None, "display": None}
    return {"stored": _stored(amount), "display": _display(amount)}


# ── the customer's OTHER accounts (B19 §15.9.4 / §15.9.5) ───────────────────
DISPOSITION_APPLIED = "applied"
DISPOSITION_SHOWN_NOT_APPLIED = "shown_not_applied"


@dataclass(frozen=True)
class SiblingPosition:
    """Another account of the same customer, and what happens to its money.

    `amount` is SIGNED and follows BR-PAY-012 as the PO ruled it on 2026-08-11
    (*"Yes, it's a real debt"*): positive is owed TO the utility, negative is
    money the utility holds. Nothing floors it.

    **The disposition is the unsigned rule of B19 §15.9.4** — a debt is applied
    and a credit is only shown — so it is a property here rather than an `if`
    at each call site. When the PO rules on it, one constant moves.
    """

    account_id: str
    account_no: str | None
    amount: Decimal
    currency: str

    @property
    def is_debt(self) -> bool:
        return self.amount > ZERO

    @property
    def is_credit(self) -> bool:
        return self.amount < ZERO

    @property
    def disposition(self) -> str:
        """`applied` for a debt, `shown_not_applied` for a credit — §15.9.4."""
        return DISPOSITION_APPLIED if self.is_debt else DISPOSITION_SHOWN_NOT_APPLIED

    def serialize(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_no": self.account_no,
            "amount": _pair(self.amount),
            "currency": self.currency,
            "kind": "debt" if self.is_debt else ("credit" if self.is_credit else "level"),
            "disposition": self.disposition,
        }


# ── the gaps, each naming the rule that leaves it open ──────────────────────
GAP_FINAL_BILL = "final_bill_not_stated"
GAP_DEPOSIT_INTEREST = "deposit_interest_not_accrued"
GAP_EXPORT_CREDIT_EXCEEDS_BILL = "export_credit_exceeds_final_bill"
GAP_DISPUTES_UNREADABLE = "open_disputes_not_readable"
GAP_SIBLINGS_UNREADABLE = "other_accounts_not_readable"

GAP_REASONS: dict[str, dict[str, str]] = {
    GAP_FINAL_BILL: {
        "br_ref": "BR-CUS-031 · US-BIL-011",
        "detail": "billing publishes no per-account final-bill total, so the left-hand column "
        "of B19 §15.9.0 cannot be read from here and the caller must state it.",
    },
    GAP_DEPOSIT_INTEREST: {
        "br_ref": "BR-CUS-057 · US-CUS-023 §7 · GT-61",
        # ⚠ THIS REASON READ *"the accrual engine is customers' own and is NOT
        # BUILT — `apps.customers.selectors.deposit_interest_accrued` is
        # published by nothing"* UNTIL 2026-09-03. It IS published now (CR-059
        # CS-20), so the sentence is corrected rather than left to rot
        # (hard-won law 1): a stale absence-claim misleads exactly as much as a
        # stale guarantee, and this one would send a reader to build a second
        # engine. What is left are the three things the engine itself REFUSES
        # to answer, each of which leaves this gap for a different reason.
        "detail": "the accrued interest could not be worked out. Either the day to accrue TO "
        "was not stated (BR-TEN-043 — it is the caller's, never a clock), or the deposit on "
        "this account carries no receipt date so BR-CUS-057's clock has no start, or the "
        "utility's rate could not be read at all. WE-7 freezes $3.50 on a $150 deposit held 14 "
        "months at 2% and GT-61 freezes $22.25 on 89 months; a principal-only settlement keeps "
        "that money on a bill that foots.",
    },
    GAP_EXPORT_CREDIT_EXCEEDS_BILL: {
        "br_ref": "BR-MET-107 (open half)",
        "detail": "the unbanked export credit is larger than the final bill. BR-MET-107 says "
        "where the credit goes FIRST and not whether the remainder is refundable, carried to "
        "a next account, or held. Not floored at zero — flooring would confiscate the "
        "difference, which is the confiscation the ruling was made to stop.",
    },
    # ⚠ KEPT, AND UNREACHABLE WHILE NO DISPUTE STORE IS PUBLISHED. BR-CUS-096
    # is SUSPENDED (PO 2026-10-11): `_open_dispute_total` answers 0.00 when no
    # store exists, so this gap fires only if a PUBLISHED store answers None.
    # The key stays because a store may return and the screen maps it; the
    # sentence no longer claims silence holds the refund.
    GAP_DISPUTES_UNREADABLE: {
        "br_ref": "BR-CUS-096",
        "detail": "a published dispute store gave no answer for this account. BR-CUS-096 "
        "is suspended while nothing records a dispute (PO 2026-10-11: no store means no "
        "dispute, and the excess is refunded); this gap fires only when a store exists and "
        "cannot answer. metering's `disputed_at` on a METER READ is a quantity in dispute, "
        "not an amount, and is deliberately not wired here.",
    },
    GAP_SIBLINGS_UNREADABLE: {
        "br_ref": "B19 §15.9.3 · BR-CUS-054",
        "detail": "the customer's other accounts could not be read from the books. §15.9.3's "
        "*'The customer has no other debt with us, so it is refunded'* is a PRECONDITION, not "
        "a courtesy — it is exactly what §15.9.5 falsifies — so no refund lands unchecked.",
    },
}


@dataclass(frozen=True)
class MoveOutSettlement:
    """B19 §15.9's step 3, as one object: the two columns and the verdict.

    Nothing in here is stored. There is no `final_settlements` table, so this
    rides the API response and the `audit_log` rows the decision services write.
    """

    currency: str
    prior_balance: Decimal
    final_bill: Decimal | None
    deposit_held: Decimal
    deposit_interest: Decimal | None
    unapplied_credit: Decimal = ZERO
    export_credit: Decimal = ZERO
    siblings: tuple[SiblingPosition, ...] | None = ()
    open_dispute_total: Decimal | None = None
    unavailable: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    # ── BR-MET-107: the export credit comes off the FINAL BILL, first ───────
    @property
    def final_bill_net(self) -> Decimal | None:
        """*"apply it to the final bill"* — PO 2026-08-24, BR-MET-107.

        None when the bill is unknown OR when the credit exceeds it, which is
        the open half of that ruling and is a gap rather than a zero.
        """
        if self.final_bill is None or self.export_credit > self.final_bill:
            return None
        return self.final_bill - self.export_credit

    # ── completeness, and it fails CLOSED ───────────────────────────────────
    @property
    def gaps(self) -> tuple[str, ...]:
        """Which term could not be read. A settlement with ANY gap states no
        landing — hard-won law 3, on an account nobody will read again.

        The last two are CONDITIONAL on there being an excess, and that is
        deliberate: a dispute and a sibling only decide where money that is
        going BACK ends up. A `short` or a `settled` close is unaffected by
        either, and gapping those would refuse settlements the rules settle.
        """
        missing: list[str] = []
        if self.final_bill is None:
            missing.append(GAP_FINAL_BILL)
        elif self.export_credit > self.final_bill:
            missing.append(GAP_EXPORT_CREDIT_EXCEEDS_BILL)
        if self.deposit_interest is None:
            missing.append(GAP_DEPOSIT_INTEREST)
        if not missing and self._raw_net is not None and self._raw_net < ZERO:
            if self.open_dispute_total is None:
                missing.append(GAP_DISPUTES_UNREADABLE)
            if self.siblings is None:
                missing.append(GAP_SIBLINGS_UNREADABLE)
        return tuple(missing)

    @property
    def complete(self) -> bool:
        return not self.gaps

    # ── the one subtraction ─────────────────────────────────────────────────
    @property
    def outstanding(self) -> Decimal | None:
        """BR-CUS-025 as amended: **everything outstanding**, both terms, with
        BR-MET-107's export credit already off the bill."""
        net_bill = self.final_bill_net
        if net_bill is None:
            return None
        return self.prior_balance + net_bill

    @property
    def applied(self) -> Decimal | None:
        """The deposit, its BR-CUS-057 interest, and THIS account's credit.

        A sibling's money is never in this sum — a sibling DEBT changes where
        an excess goes and a sibling CREDIT changes nothing at all (§15.9.4),
        and neither changes the arithmetic.
        """
        if self.deposit_interest is None:
            return None
        return self.deposit_held + self.deposit_interest + self.unapplied_credit

    @property
    def _raw_net(self) -> Decimal | None:
        outstanding, applied = self.outstanding, self.applied
        if outstanding is None or applied is None:
            return None
        return outstanding - applied

    @property
    def net(self) -> Decimal | None:
        return self._raw_net

    @property
    def shortfall(self) -> Decimal:
        """What survives the close and is still chased (BR-CUS-082)."""
        net = self._raw_net
        return net if net is not None and net > ZERO else ZERO

    @property
    def excess(self) -> Decimal:
        """What the deposit is worth OVER everything owed (BR-CUS-081)."""
        net = self._raw_net
        return -net if net is not None and net < ZERO else ZERO

    @property
    def settled_amount(self) -> Decimal:
        """BR-CUS-081: *"settle the $142.30 from the $153.50 deposit"*.

        `min(outstanding, applied)` and nothing cleverer — the rejected reading
        was to refund the whole deposit and leave the bill standing.
        """
        outstanding, applied = self.outstanding, self.applied
        if outstanding is None or applied is None:
            return ZERO
        return outstanding if outstanding < applied else applied

    @property
    def refund_amount(self) -> Decimal:
        """BR-CUS-081: *"and refund $11.20"*. The same figure as `excess`, named
        for what it IS on the refund path so a reader of `refund_disposition`
        is not asked to remember that the two are equal."""
        return self.excess

    # ── the customer's other accounts ───────────────────────────────────────
    @property
    def sibling_debts(self) -> tuple[SiblingPosition, ...]:
        return tuple(s for s in (self.siblings or ()) if s.is_debt)

    @property
    def sibling_credits(self) -> tuple[SiblingPosition, ...]:
        return tuple(s for s in (self.siblings or ()) if s.is_credit)

    @property
    def sibling_debt_total(self) -> Decimal:
        return sum((s.amount for s in self.sibling_debts), ZERO)

    @property
    def transfer_to_sibling(self) -> Decimal:
        """§15.9.5: *"The $59.05 credit here goes there first — no refund."*

        Capped at the debt, because a sibling owing $20 does not absorb a $59
        excess — `948.20 − 59.05 = 889.15` is the screen's own after-figure and
        it only works if the transfer is the SMALLER of the two.
        """
        excess, debt = self.excess, self.sibling_debt_total
        return excess if excess < debt else debt

    @property
    def sibling_after_transfer(self) -> Decimal:
        """*"What remains on 11902 after the transfer is $889.15, still in
        collections."* Stated so the clerk can see that transferring does not
        clear the sibling account."""
        return self.sibling_debt_total - self.transfer_to_sibling

    # ── the landing ─────────────────────────────────────────────────────────
    @property
    def landing(self) -> str | None:
        """One of `MONEY_LANDINGS`, or None when a term could not be read.

        The ORDER is the rule and each step names its evidence:

          0. any gap → **no landing**. Not a sixth outcome: a missing deposit
             interest understates `applied`, biasing the answer toward `short`;
             a missing final bill understates `outstanding`, biasing it toward
             `refund_due`. One of those two directions posts a cheque.
          1. `net > 0` → **`short`** (§15.9.4's 170.74; BR-CUS-082).
          2. `net == 0` → **`settled`** (§15.9.1 row 1, step 4 skipped).
          3. an excess with an OPEN DISPUTE → **`refused_excess`**, HELD
             (BR-CUS-096, §15.9.6's 13.12). Tested BEFORE the sibling debt
             because BR-CUS-096 is signed and the sibling seizure is not:
             transferring money that may still be owed elsewhere is the
             irreversible act the signed rule exists to prevent.
          4. an excess with a SIBLING DEBT → **`refused_other_debt`**
             (§15.9.5, unsigned — reported).
          5. otherwise → **`refund_due`** (§15.9.3, BR-CUS-081).
        """
        if not self.complete:
            return None
        net = self._raw_net
        assert net is not None  # `complete` excludes exactly the None terms
        if net > ZERO:
            return LANDING_SHORT
        if net == ZERO:
            return LANDING_SETTLED
        if self.open_dispute_total is not None and self.open_dispute_total > ZERO:
            return LANDING_REFUSED_EXCESS
        if self.sibling_debt_total > ZERO:
            return LANDING_REFUSED_OTHER_DEBT
        return LANDING_REFUND_DUE

    @property
    def step_4_live(self) -> bool:
        """§15.9.1: `4 · The shortfall` renders live in ONE landing and
        `4 · Shortfall · skipped`, greyed and named, in the others."""
        return self.landing in STEP_4_LIVE_IN

    # ── serialization: BOTH money shapes, each labelled ─────────────────────
    def serialize(self) -> dict[str, Any]:
        unavailable = [dict(entry) for entry in self.unavailable]
        for code in self.gaps:
            unavailable.append({"code": code, **GAP_REASONS[code]})
        if self.sibling_credits:
            unavailable.append(
                {
                    "code": "sibling_credit_rule_unsigned",
                    "br_ref": "B19 §15.9.4 · OQ-362",
                    "detail": "a credit on another of this customer's accounts is SHOWN and "
                    "never applied, while a sibling DEBT is applied. The prototype draws both; "
                    "no signed rule states either, and this settlement follows the drawing "
                    "rather than inventing a rule.",
                }
            )
        if self.landing == LANDING_REFUSED_EXCESS:
            unavailable.append(
                {
                    "code": "held_excess_has_no_release_path",
                    "br_ref": "BR-CUS-096 (open half)",
                    "detail": "BR-CUS-096 holds the excess until the dispute closes and does "
                    "not say who releases it or on what clock. Nothing in this repository "
                    "chases a held excess: there is no release path, no timer and no queue, "
                    "so it sits until a human looks.",
                }
            )
        return {
            "currency": self.currency,
            "landing": self.landing,
            "landings": list(MONEY_LANDINGS),
            "complete": self.complete,
            "gaps": list(self.gaps),
            "step_4_live": self.step_4_live,
            # left column — B19 §15.9.0's `Final bill · prorated to …`
            "everything_outstanding": {
                "prior_balance": _pair(self.prior_balance),
                "final_bill": _pair(self.final_bill),
                "export_credit": _pair(self.export_credit),
                "final_bill_net": _pair(self.final_bill_net),
                "total": _pair(self.outstanding),
            },
            # right column — `What is applied against it`
            "what_is_applied": {
                "deposit_held": _pair(self.deposit_held),
                "deposit_interest": _pair(self.deposit_interest),
                "unapplied_credit": _pair(self.unapplied_credit),
                "total": _pair(self.applied),
            },
            # the verdict panel
            "verdict": {
                "net": _pair(self.net),
                "shortfall": _pair(self.shortfall),
                "excess": _pair(self.excess),
                "settled_from_deposit": _pair(self.settled_amount),
                "refund_amount": _pair(self.refund_amount),
                "transfer_to_sibling": _pair(self.transfer_to_sibling),
                "sibling_after_transfer": _pair(self.sibling_after_transfer),
            },
            "siblings": (None if self.siblings is None else [s.serialize() for s in self.siblings]),
            "open_dispute_total": _pair(self.open_dispute_total),
            "refund_methods": list(REFUND_METHODS),
            "unavailable": unavailable,
        }


# ── THE COMPUTATION (pure — no reads, no writes, no rounding) ───────────────
def derive(
    *,
    currency: str,
    prior_balance: Any,
    final_bill: Any,
    deposit_held: Any,
    deposit_interest: Any,
    unapplied_credit: Any = ZERO,
    export_credit: Any = ZERO,
    siblings: tuple[SiblingPosition, ...] | None = (),
    open_dispute_total: Any = None,
    unavailable: tuple[dict[str, Any], ...] = (),
) -> MoveOutSettlement:
    """B19 §15.9's whole arithmetic, in one place, with no branch inside it.

    Pure by construction, so the five landings can be driven with the PO's own
    figures and nothing about the DERIVATION depends on a table existing. Every
    landing in `MONEY_LANDINGS` is reachable from here and the test file drives
    all five, plus BR-CUS-081's, BR-CUS-082's, BR-CUS-025's and BR-MET-107's
    worked cases.

    `siblings=None` means *the other accounts could not be read*; `siblings=()`
    means *there are none*. The two are opposite facts on the refund path
    (§15.9.3's precondition), so they are opposite values here — DEF-075's own
    lesson, applied to a money decision rather than to a currency lock.
    """
    return MoveOutSettlement(
        currency=currency,
        prior_balance=_money(prior_balance, "the prior balance"),
        final_bill=None if final_bill is None else _money(final_bill, "the final bill"),
        deposit_held=_money(deposit_held, "the deposit held"),
        deposit_interest=(
            None if deposit_interest is None else _money(deposit_interest, "the deposit interest")
        ),
        unapplied_credit=_money(unapplied_credit, "the unapplied credit"),
        export_credit=_money(export_credit, "the unbanked export credit"),
        siblings=None if siblings is None else tuple(siblings),
        open_dispute_total=(
            None if open_dispute_total is None else _money(open_dispute_total, "the open disputes")
        ),
        unavailable=tuple(unavailable),
    )


# ════════════════════════════════════════════════════════════════════════════
# THE WIRED READ — every term from the module that owns it, or a named gap
# ════════════════════════════════════════════════════════════════════════════
def _sibling_positions(account: models.Account) -> tuple[SiblingPosition, ...] | None:
    """The customer's OTHER accounts and what each owes — or None if unknown.

    Reached through BR-CUS-054's `customer_accounts` N:M link, so a jointly
    held account and a landlord's twelve are both found by the same query, and
    then through the ONE published customers→ledger read
    (`seams.ar_positions`) for the whole set at once rather than per row.

    ⚠ **None IS NOT AN EMPTY TUPLE HERE.** `()` means the books answered and
    this customer holds nothing else; `None` means the books could not be
    asked. §15.9.3's refund precondition needs the first and would be a lie
    told with the second — DEF-075's exact confusion, in a money path.
    """
    tenant_id = account.tenant_id
    customer_ids = list(
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, account=account).values_list(
            "customer_id", flat=True
        )
    )
    if not customer_ids:
        # Not a gap: an account with no customer link has no siblings BY
        # CONSTRUCTION, and there is nothing the books could add.
        return ()
    sibling_ids = list(
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, customer_id__in=customer_ids)
        .exclude(account_id=account.id)
        .values_list("account_id", flat=True)
    )
    if not sibling_ids:
        return ()
    rows = {
        str(row.id): row
        for row in models.Account.objects.filter(tenant_id=tenant_id, id__in=sibling_ids)
    }
    positions = seams.ar_positions(account_ids=list(rows))
    if not positions.available:
        return None
    out: list[SiblingPosition] = []
    for account_id, row in sorted(rows.items(), key=lambda item: item[1].account_no or ""):
        amount = positions.amount_for(account_id)
        if amount is None:  # pragma: no cover — `available` already proved otherwise
            return None
        out.append(
            SiblingPosition(
                account_id=account_id,
                account_no=row.account_no,
                amount=_money(amount, f"the position of {row.account_no}"),
                currency=row.currency,
            )
        )
    return tuple(out)


def _unapplied_credit(account: models.Account) -> Decimal:
    """What payments holds FOR this account — SIGNED (BR-PAY-012, OQ-132).

    *"any code, screen or report that assumes a customer credit is non-negative
    is wrong"* (PO 2026-08-11), so nothing here floors it: a negative credit is
    a real debt and reduces what the deposit can settle.

    Unwired ⇒ **zero**, and that direction is argued rather than assumed: this
    term only ever ADDS to what is applied, so a missing credit understates the
    money going back and can never refund somebody who is owed nothing. It is
    the opposite of the deposit-interest gap, where the same absence would keep
    the customer's money — which is why one is a gap and this is not.
    """
    read = seams.resolve("payments", "account_credit_position", kind="selectors")
    if read is None:  # pragma: no cover — payments publishes it today
        return ZERO
    return _money(read(account.id), "the unapplied credit on this account")


def _deposit_interest(account: models.Account, as_of: Any) -> Decimal | None:
    """BR-CUS-057's accrual, or None. NEVER computed here.

    An account holding NO deposit answers ZERO without consulting the engine —
    there is nothing to accrue on, and blocking those closures on an unbuilt
    engine would be a refusal with no rule behind it. This is
    `apps/billing/final_bill.deposit_credit_for`'s posture, deliberately
    identical: two modules disagreeing about when a deposit may be settled is
    how a customer gets two different answers to one question.

    ⚠ **THE ENGINE EXISTS FROM 2026-09-03 (CR-059 CS-20) AND THE POSTURE HERE IS
    UNCHANGED.** This function still fails CLOSED on a `None`; what changed is
    that `apps.customers.selectors.deposit_interest_accrued` now answers.

    ⚠ **`as_of` IS STATED BY THE CALLER AND IS NOT DEFAULTED HERE.** It is the
    business day the settlement is being worked, exactly as `final_bill` is the
    figure the caller states, and for the same class of reason: BR-TEN-043 and
    gate G6 keep the clock out of a money path, and a settlement re-opened
    tomorrow must show the same figure unless somebody moved the date. When the
    caller states none, this reports rather than guessing a day — an interest
    figure computed against an unstated date is a number nobody can check.
    """
    if account.deposit_on_file == ZERO:
        return ZERO
    read = seams.resolve("customers", "deposit_interest_accrued", kind="selectors")
    if read is None:
        return None
    # `as_of` is passed THROUGH, `None` included, rather than short-circuited
    # here. The rule *"an unstated day accrues nothing that can be checked"*
    # belongs to the engine and is stated there once; a copy of it in this
    # module would be a second place for it to drift, and it is the shape
    # `_open_dispute_total` and `_export_credit` already take with their own
    # seams — this module resolves and forwards, and never decides.
    answered = read(account.id, as_of)
    return None if answered is None else _money(answered, "the accrued deposit interest")


def _open_dispute_total(account: models.Account) -> Decimal | None:
    """BR-CUS-096's precondition — SUSPENDED: no dispute store answers ZERO.

    ⚠ **PO RULING 2026-10-11 (decision log, *"MOVE-OUT REFUND: THE OPEN-DISPUTE
    HOLD (`BR-CUS-096`) IS SET ASIDE WHILE NOTHING RECORDS A DISPUTE"*),
    verbatim:** *"today we are not handling any disppute case not recodingt he
    dispute anywhere. hence dispute check doe snot work, I think we should
    remove it fo time being and process the refund"*. Option A of three: treat
    *no dispute recorded* as *no dispute*; disputes are handled by hand.

    Worked, as put to the PO: Maria Lopez's **$150.00** deposit pays her
    **$90.00** final bill, so **$60.00** is refunded (or carried) — it is no
    longer held behind a check that could only ever answer *unknown*.

    **Until that ruling this returned None**, because nothing stores a disputed
    AMOUNT (measured 2026-08-24: no model, no `db_table`, no seam, no
    publisher), and `None` made every excess landing gap on
    `open_disputes_not_readable` — so no refund could ever land.

    ⚠ **"FOR THE TIME BEING" IS PART OF THE RULING, WHICH IS WHY THE SEAM IS
    STILL READ FIRST.** The day billing publishes `open_dispute_total`, this
    answers what it says and BR-CUS-096's hold (`refused_excess`) returns with
    no change here. Only the ABSENCE of a store moved from *unknown* to *zero*.

    ⚠ **`metering`'s `disputed_at` ON A METER READ IS NOT THIS.** That is a
    quantity in dispute; BR-CUS-096 conditions on an amount. Do not wire it
    here — it would hold a refund because somebody queried a dial.
    """
    read = seams.resolve("billing", "open_dispute_total", kind="selectors")
    if read is None:
        # BR-CUS-096 SUSPENDED (PO 2026-10-11): no store recorded, no dispute.
        return Decimal("0.00")
    answered = read(account.id)
    # A PUBLISHED store that cannot answer is still a gap — fail closed.
    return None if answered is None else _money(answered, "the open disputes")


def _export_credit(account: models.Account) -> Decimal:
    """BR-MET-107's unbanked export credit — the $4.10 on `M-4023`.

    Metering publishes no per-account export-credit balance (measured
    2026-08-24), so this answers ZERO, and unlike the two gaps above that is
    safe in the ONE direction that matters: a missing credit leaves the
    customer owing MORE, never less, so it cannot cause an over-refund. It is
    still recorded on the payload, because a customer silently billed $4.10
    they had earned is exactly what DEF-654 was filed about.
    """
    read = seams.resolve("metering", "unbanked_export_credit", kind="selectors")
    return ZERO if read is None else _money(read(account.id), "the unbanked export credit")


EXPORT_CREDIT_UNWIRED: dict[str, Any] = {
    "code": "unbanked_export_credit_not_readable",
    "br_ref": "BR-MET-107 · DEF-654",
    "detail": "metering publishes no per-account unbanked export-credit balance, so the "
    "credit BR-MET-107 applies to the final bill is read as 0.00. That direction can only "
    "leave the customer owing MORE, never less — but a closing solar or battery account "
    "carries one, and it is named rather than left silent.",
}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def settlement_for(
    actor: Any, account_id: Any, *, final_bill: Any = None, as_of: Any = None
) -> dict[str, Any]:
    """`GET`-shaped read model for S20 step 3 — the five landings, wired.

    Every term comes from the module that owns it: the prior balance and the
    siblings from the LEDGER through `seams.ar_positions` (never
    `accounts.balance`, which is a cache nothing writes — DEF-127), the deposit
    principal from this module's own column, the interest from BR-CUS-057's
    unbuilt engine, the credit from payments, the export credit from metering,
    the disputes from a store that does not exist — read as 0.00 while
    BR-CUS-096 is suspended (PO 2026-10-11).

    `final_bill` is STATED by the caller — the drafted `invoices.total` the
    wizard is already showing on the left — because billing publishes no
    per-account final-bill total. Absent, the read model reports the gap and
    states no landing rather than settling against a bill nobody read.

    `as_of` is STATED by the caller too, and for the same class of reason
    (CR-059 CS-20, 2026-09-03): BR-CUS-057's interest accrues from the original
    receipt date to a DAY, and gate G6 keeps a clock out of a money path. A
    caller that states none gets `deposit_interest_not_accrued` on an account
    that holds a deposit — the same fail-closed answer it got while the engine
    did not exist, with a different reason.

    A READ: no audit row, because nothing moved. The two decision services
    below are the money actions and each writes its own (hard rule 7).
    """
    from apps.customers import selectors

    account = selectors.account_or_404(account_id)
    positions = seams.ar_positions(account_ids=[str(account.id)])
    prior = positions.amount_for(account.id)
    if prior is None:
        # DEF-127's shape, moved into a money path: a balance that could not be
        # read is not 0.00. A zero here settles a deposit against an
        # understated position and refunds a customer who still owes.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-025 · DEF-127",
            message_key="customers.move_out.balance_not_readable",
            params={
                "account_no": account.account_no,
                "reasons": [str(gap.get("code")) for gap in positions.unavailable],
            },
        )

    unavailable: list[dict[str, Any]] = []
    export_credit = _export_credit(account)
    if export_credit == ZERO:
        unavailable.append(dict(EXPORT_CREDIT_UNWIRED))

    settlement = derive(
        currency=account.currency,
        prior_balance=prior,
        final_bill=final_bill,
        deposit_held=account.deposit_on_file,
        deposit_interest=_deposit_interest(account, as_of),
        unapplied_credit=_unapplied_credit(account),
        export_credit=export_credit,
        siblings=_sibling_positions(account),
        open_dispute_total=_open_dispute_total(account),
        unavailable=tuple(unavailable),
    )
    payload = settlement.serialize()
    payload["account_id"] = str(account.id)
    payload["account_no"] = account.account_no
    payload["final_bill_stated_by_caller"] = final_bill is not None
    payload["shortfall_paths"] = shortfall_path_options(account)
    # `BR-CUS-1082` — a parent with open children is **WARNED** when it is
    # moved out (PO ruling 2026-09-20, closing `OQ-CUS-12515` on option (b));
    # this comment said *"cannot be moved out"* for one day. The count is
    # DERIVED from the premises, never stored, so it is right on the day a
    # tenant moves in and on the day one moves out with nobody maintaining it.
    # `BR-CUS-171` (PO 2026-08-27, closing OQ-531) is cited for the one thing
    # it signs: WHO counts as an open child.
    #
    # ⚠ **THIS COMMENT ATTRIBUTED THE REFUSAL TO `BR-CUS-171` UNTIL 2026-09-20
    # AND THAT IS `DEF-CUS-5950`.** `BR-CUS-171`'s row is about the parent/child
    # LINK and carries no move-out clause at all; the sentence quoted here is
    # `B19 §15.8`'s, which says of itself *"THIS IS NOT IN ANY SIGNED RULE …
    # It needs ratifying before W5 builds step 1."* The mis-citation reached
    # `DEF-CUS-5930`, the decision log and the `J-MVO` journey, one of which
    # called it *"the signed rule"* — `DEF-GOV-5229`'s shape, and every
    # id-existence check passes over it because `BR-CUS-171` is real.
    #
    # ⚠ **THE WARNING READS THIS NUMBER'S SOURCE, NOT THIS PAYLOAD.**
    # `services.move_out` calls the SAME `selectors.sub_accounts_for_master`,
    # so there is one definition of an open child and this field cannot
    # disagree with the commit. **That survived the reversal untouched**: it
    # was true of the refusal and it is true of the warning, because what it
    # guarantees is that one selector answers both readers (`DEF-CUS-5901`'s
    # defect class). `OQ-CUS-12515` is CLOSED — the rule is no longer a lane
    # judgment, and what the PO signed is the WARNING.
    #
    # ⚠ `07-frontend/.../moveShared.tsx` has declared and rendered
    # `open_sub_accounts` since 2026-08-24 and NO BACKEND HAD EVER SERVED IT —
    # hard-won law 2, and OQ-531 recorded it as rendering `0` on every tenant.
    # Zero is now a measurement rather than a default.
    payload["open_sub_accounts"] = len(selectors.sub_accounts_for_master(account))
    payload.update(close_impact_for(account))
    return payload


# ════════════════════════════════════════════════════════════════════════════
# THE MOVE-OUT'S IMPACT — WHERE THE UNIT GOES (CR-056 W6 task 26)
# ════════════════════════════════════════════════════════════════════════════
#: `BR-CUS-1040` — a move-out states, in words and BEFORE it is committed, which
#: account the unit falls to and that its standing charge continues there.
#:
#: **PO ruling 2026-08-31, verbatim:** *"it is taken care during move out step -
#: we have in impact section, we need to cover it there - expliciately"*, and the
#: decision log of that day makes the adverb a requirement rather than an
#: emphasis: *"The unit falling to the owner's account is a new consequence of
#: that act and must be drawn there in words — which account it moves to, and
#: that the standing charge continues on it — rather than happening correctly and
#: invisibly. A clerk who has to discover a money movement afterwards has been
#: given a surprise, and a surprise on a money path is a defect whatever the
#: arithmetic did."*
#:
#: ⚠ **THE MECHANISM IS NOT NEW AND MUST NOT BE REBUILT.** A move-out sets the
#: terminal status, `BR-MET-036` derives the unit back to vacant, and
#: `selectors.base_charge_only_coverage` puts every unit with no occupying
#: account onto the owner's bill — *"the exclusion test is the ACCOUNT, never a
#: flag"*. **A cut arrives at the identical state by the identical path**
#: (`CR-052` W0 task 2: `$69.60` of common areas becomes `$81.60` when one unit
#: empties), which is why nothing here writes a second one. What was missing was
#: never the money — it was the SENTENCE.
def close_impact_for(account: models.Account) -> dict[str, Any]:
    """The five impact facts S20 step 5 has rendered as blanks since 2026-08-24.

    ⚠ **HARD-WON LAW 2, AND THE PANELS HAVE BEEN THERE ALL ALONG.**
    `07-frontend/src/features/customers/moveShared.tsx` has declared and drawn
    `units_occupied_after`, `owner_on_record`, `owner_is_free_text`,
    `common_area_account_no` and `vacant_base_charge` since the impact screen
    shipped, and its port maps every one of them to an explicit `null` under a
    comment naming the module that owes it. This is that debt paid for the four
    of them customers can answer.

    **`vacant_base_charge` IS DELIBERATELY STILL `None`, AND THE FIFTH FIELD IS
    WHY.** A single "this is what the empty unit will cost" figure is a PRICE,
    and pricing is the rating engine's alone (CLAUDE.md 🔒). Nothing publishes a
    per-unit standing-charge preview outside a bill run, and a sum computed here
    would be a second implementation of signed money law in a module that does
    not own it — the exact defect class `seams.prorate_base_charge` exists to
    prevent. What IS served is `vacant_base_charges`: the plan's OWN configured
    per-service base charges, read VERBATIM through `seams.plan_detail`, which
    that seam's docstring licenses in as many words (*"the tenant's own
    configured figures, read verbatim … not a proration"*). Real numbers, no
    arithmetic, and no total that could disagree with the bill.

    **NOTHING HERE IS A DEFAULT.** Every field is `None` where it could not be
    measured, because the panels already render a stated absence and a `0` or a
    `false` would be the screen making a claim nobody took (DEF-669's own half:
    *"`null` is NOT `true`"*).
    """
    from apps.customers import selectors

    premises_id = selectors.premises_id_for_account(account)
    owner = owner_target_for(account)
    if not owner["available"]:
        by_address = transfer_target_for(account)
        # ⚠ **THE ADDRESS READ REPLACES THE OWNER READ ONLY WHEN IT ANSWERS.**
        # Where NEITHER resolves, the sentence the screen shows is the OWNER's
        # refusal — *this address has no owner account* — because that is the
        # fact the PO's ruling is about and the one a clerk can act on. The
        # master read's own wording (*no master account NAMES this address*) is
        # true and is a sentence about our data model; it would tell a clerk to
        # go looking for something they have never heard of.
        if by_address["available"]:
            owner = by_address
    falls_to = {
        # ⚠ **AN UNOCCUPIED UNIT THAT FINDS NO OWNER ACCOUNT IS A FAULT, NOT A
        # SILENCE** — PO 2026-08-31, ruling 1 consequence 3: *"'no lines because
        # nothing falls to it' and 'no lines although the premises HAS an
        # unoccupied unit' are different facts and only one of them is good
        # news."* `CR-056` task 22 puts the same case on the exceptions screen.
        "available": bool(owner["available"]),
        "account_id": owner["account_id"],
        "account_no": owner["account_no"],
        "br_ref": owner["br_ref"],
        "reason": owner["reason"],
    }
    return {
        "units_occupied_after": _units_occupied_after(premises_id, leaving=account),
        "owner_on_record": _owner_on_record(premises_id, owner),
        "owner_is_free_text": _owner_is_free_text(premises_id, owner),
        # The panel's label says *common-area account* because that is what a
        # master account WAS. Under `CR-056` it is the owner's account at the
        # address whether or not the address has a common area, and the field
        # keeps its name so no reader has to be migrated — the meaning widened,
        # the contract did not.
        "common_area_account_no": owner["account_no"],
        "vacant_base_charge": None,
        "vacant_base_charges": _vacant_base_charges(account),
        "unit_falls_to": falls_to,
    }


def _units_occupied_after(premises_id: Any, *, leaving: models.Account) -> dict[str, int] | None:
    """§15.10's `Units occupied after this 1 of 3` — counted, never stored.

    Common areas are excluded: they are the owner's by construction and nobody
    "occupies" a hallway, so counting them would make every building read as
    permanently under-occupied. The leaving account is excluded from the
    occupied side because the number the screen states is the one AFTER this
    move-out — which is the whole point of an impact panel.
    """
    from apps.customers import selectors

    if premises_id is None:
        return None
    units = [
        unit
        for unit in selectors._units_on_premises(premises_id)
        if not getattr(unit, "is_common_area", False)
    ]
    if not units:
        return None
    occupied = 0
    for unit in units:
        holders = [
            row
            for row in selectors.occupying_accounts_for_unit(unit.id)
            if str(row.id) != str(leaving.id)
        ]
        if holders:
            occupied += 1
    return {"occupied": occupied, "total": len(units)}


def _owner_on_record(premises_id: Any, owner: dict[str, Any]) -> str | None:
    """WHO the empty unit's standing charge is addressed to, as a person reads it.

    The resolved owner ACCOUNT's own primary contact first — that is the party
    the bill is actually sent to — and the premises' free-text `owner_manager`
    only where no account resolved. A name with no account behind it is exactly
    `DEF-650`'s *"a charge cannot be sent to a name"*, and serving it here is how
    the screen SAYS so rather than implying somebody is covered.
    """
    from apps.customers import selectors

    if owner["available"] and owner["account_id"]:
        row = selectors.account_queryset().filter(pk=owner["account_id"]).first()
        if row is not None:
            return selectors.primary_contact_name(row) or row.account_no
    if premises_id is None:
        return None
    try:
        return seams.premises_ref(premises_id).get("owner_manager") or None
    except errors.NotFoundError:  # pragma: no cover — a PROTECTed FK cannot dangle
        return None


def _owner_is_free_text(premises_id: Any, owner: dict[str, Any]) -> bool | None:
    """`True` only when the owner is a NAME and nothing else — `None` when unknown.

    DEF-669's own correction, kept: this was typed `boolean` and defaulted an
    unread value to `true`, which asserts the owner is free text on every
    premises in the product. Three states, and the third is the honest one.
    """
    if owner["available"]:
        return False
    if premises_id is None:
        return None
    try:
        return bool(seams.premises_ref(premises_id).get("owner_manager"))
    except errors.NotFoundError:  # pragma: no cover
        return None


def _vacant_base_charges(account: models.Account) -> list[dict[str, Any]] | None:
    """The plan's OWN per-service base charges for the unit being vacated.

    Read VERBATIM through `seams.plan_detail` and NEVER summed, prorated or
    adjusted — see `close_impact_for` for why a total is not served. `None`
    where the unit names no plan or rating is unwired, which the panel renders
    as a stated absence.

    ⚠ **NO MINIMUM IS ADDED, AND THAT IS A RULING RATHER THAN AN OMISSION.**
    `OQ-1166` CLOSED 2026-08-30, PO verbatim: *"when units are vacant - at that
    time, we are only charging base rates. minimum rates are applied when
    consumer is suppose to use minimum usage, but they end up using less than
    what they are suppose ot use"*. Six empty units went from `$90.00` to
    `$48.00` on that ruling; a `minimum_amount` shown here would put the $42.00
    back on the screen after it was taken off the bill.
    """
    unit_id = getattr(account, "unit_id", None)
    if unit_id in (None, ""):
        return None
    try:
        unit = seams.unit_dict(seams.unit_row(unit_id))
    except errors.NotFoundError:  # pragma: no cover
        return None
    plan_id = unit.get("rate_plan_id")
    if plan_id in (None, ""):
        return None
    detail = seams.plan_detail(plan_id)
    if not detail:
        return None
    rows: list[dict[str, Any]] = []
    for item in detail.get("services") or ():
        amount = item.get("base_charge")
        if amount in (None, ""):
            continue
        rows.append(
            {
                "service": item.get("service"),
                "name": item.get("name"),
                **_pair(_money(Decimal(str(amount)), "the plan's base charge")),
                "currency": item.get("currency"),
            }
        )
    return rows or None


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — THE SHORTFALL DECISION (task 5.8)
# ════════════════════════════════════════════════════════════════════════════
def transfer_target_for(account: models.Account) -> dict[str, Any]:
    """Where a shortfall may lawfully go — RESOLVED, never supplied.

    BR-CUS-097: *"a transfer cannot be built against an ambiguous target"*, so
    the target is read from the data and no function in this module takes a
    target account id as an argument. That is what makes US-BIL-011 TC-6's
    forged transfer unrepresentable rather than merely rejected.

    Two rulings, two targets, and only one of them has a schema today:

      * **`master_account`** — BR-CUS-097 (PO 2026-08-24): *"master account
        gets debt - if sub accoun tis unable to pay it ; even aftr deposite
        settlement"*. Resolved through BR-CUS-068's own linkage: the unit's
        premises, its ACTIVE common-area units, and the `kind='master'` account
        covering them. Exactly one master resolves or the path refuses.
      * **`premises_owner`** — BR-MET-105a (PO 2026-08-24): *"Make the owner a
        real party"*, resolved through the DECLARED chain
        `premises → premises_owners → master_account_id` (`owner_target_for`).

    ⚠ **THE COMMON-AREA WALK IS GONE, AND REMOVING IT IS `DEF-2951` (`CR-056`
    W6 task 27).** This function used to ask each of the premises' COMMON AREAS
    who paid for it and take the account that came back — the *hallway
    inference*. **The PO retired exactly that on 2026-08-27 (decision 4, closing
    `DEF-650`)**, verbatim: *"the premises names its owner, the owner is the
    master, and nothing is inferred from hallways. The old path is retired
    rather than kept as a fallback, because a fallback that disagrees with the
    declared owner would silently bill a different party."*
    `selectors.master_account_for` was moved to the declared read that same day
    and **this one was not** — so the single place in the product that decides
    whose account a departing tenant's DEBT lands on kept the retired rule for
    five days. It is the money path, which is the worst place for it to survive.

    ⚠ **AND THE WALK COULD NOT SEE THE CASE `CR-056` EXISTS FOR.** A house with
    no shared space has no common area to ask about, so the walk answered *no
    master* for every single-family address — which is the owner-occupier who
    lets his house out (`CR-056` task 28), the one move-out this whole CR was
    written to make ordinary.

    **WHAT REPLACES IT IS THE ACCOUNT'S OWN DECLARED ADDRESS, `BR-CUS-1010`.**
    `accounts.premises_id` is written at creation and was backfilled for every
    row that predates it, so a master account now SAYS which address it is the
    owner's account for. That is a declared fact, not a shape read off the
    building — the same distinction `sub_accounts_for_master` already draws in
    its own words (*"this is not a disagreeing fallback, it is which premises
    this account covers"*). Exactly one master resolves, or the path refuses;
    ambiguity is still never resolved by picking.

    **NOTHING MOVES ON THE ESTATE WE ALREADY HAVE, AND THAT IS CHECKED RATHER
    THAN ASSUMED.** `1408 Elm Street`'s master anchors on its hallway, and
    `CR-056` W1 backfilled its `premises_id` FROM that anchor's premises — so
    the retired walk and this read name the SAME account. What is added is every
    address the walk was blind to.
    """
    from apps.customers import selectors

    premises_id = selectors.premises_id_for_account(account)
    if premises_id is None:
        return {
            "target": TRANSFER_TARGET_MASTER,
            "available": False,
            "br_ref": "BR-CUS-097 · BR-CUS-1010",
            "account_id": None,
            "account_no": None,
            "reason": "this account names no address, so there is no premises to look for a "
            "master account on. BR-CUS-097 does not say what happens when there is no "
            "master — its own text records that as unsettled — so the residue is not moved "
            "anywhere.",
        }
    masters = _master_accounts_at(premises_id, exclude_id=account.id)
    if len(masters) == 1:
        master = masters[0]
        return {
            "target": TRANSFER_TARGET_MASTER,
            "available": True,
            "br_ref": "BR-CUS-097 · BR-CUS-1010",
            "account_id": str(master.id),
            "account_no": master.account_no,
            "reason": None,
        }
    if not masters:
        return {
            "target": TRANSFER_TARGET_MASTER,
            "available": False,
            "br_ref": "BR-CUS-097 · BR-CUS-1010",
            "account_id": None,
            "account_no": None,
            "reason": "no master account names this address. Under CR-056 every address gets "
            "its owner a Master Account, and this one has not been opened yet — the PO ruled "
            "on 2026-09-01 that it appears when the owner is IDENTIFIED and never at a "
            "migration that would invent one. So the residue is not moved anywhere.",
        }
    return {
        "target": TRANSFER_TARGET_MASTER,
        "available": False,
        "br_ref": "BR-CUS-097 · BR-CUS-1010",
        "account_id": None,
        "account_no": None,
        "reason": f"{len(masters)} master accounts name this address, so the target is "
        "ambiguous. BR-CUS-097: a transfer cannot be built against an ambiguous target.",
    }


def _master_accounts_at(premises_id: Any, *, exclude_id: Any = None) -> list[models.Account]:
    """Every OCCUPYING master account whose declared address is this premises.

    `BR-CUS-1010` — the stored `accounts.premises_id` first, the anchor unit's
    premises for a row the W1 backfill could not resolve; both reads live in
    `selectors.premises_id_for_account` and neither is repeated here.

    The status class is the filter, never the label (`BR-CUS-055`, and it is the
    same test `occupying_accounts_for_unit` applies one level down): a CLOSED
    master is excluded, because posting a residue to a closed account is the
    *"workaround that dies on the day it is needed"* this CR exists to end.
    """
    from apps.customers import selectors, services

    candidates = selectors.account_queryset().filter(
        kind=services.ACCOUNT_KIND_MASTER,
        status__behavior_class__in=services.OCCUPYING_BEHAVIOR_CLASSES,
    )
    found: list[models.Account] = []
    for row in candidates.order_by("created_at", "id"):
        if exclude_id is not None and str(row.id) == str(exclude_id):
            continue
        if str(selectors.premises_id_for_account(row) or "") == str(premises_id):
            found.append(row)
    return found


def owner_target_for(account: models.Account) -> dict[str, Any]:
    """BR-MET-105a's owner — the DECLARED chain, `premises → owner → account`.

    ⚠ **THIS ANSWERED "NEVER" UNTIL `CR-056` W6 (`DEF-2951`)**, on the accurate
    measurement that BR-MET-105a names `premises.owner_customer_id` and no such
    column was ever added. **The fact the rule wanted arrived under a different
    name:** a typed owner ROW with an account of its own, reached through
    `seams.owner_master_account_for_premises` — which is the read the PO named on
    2026-08-27 (*"Bascially Premises -> owner = Master account"*) and which
    `selectors.master_account_for` has used since. See `OWNER_TARGET_UNAVAILABLE`
    for what genuinely remains unavailable and why that case is a fault.

    **THIS IS THE FIRST TARGET OFFERED, AND THE ORDER IS THE POINT.** Where an
    owner is declared, the owner's own account is who the money belongs to;
    `transfer_target_for`'s address read is consulted only where nobody has
    declared one. Two rungs, both DECLARED facts, and the stronger one wins —
    which is the shape the 2026-08-27 ruling asks for, rather than a fallback
    that could disagree with a declared owner.
    """
    from apps.customers import selectors

    premises_id = selectors.premises_id_for_account(account)
    account_id = seams.owner_master_account_for_premises(premises_id) if premises_id else None
    row = (
        selectors.account_queryset().filter(pk=account_id).first()
        if account_id not in (None, "")
        else None
    )
    if row is None or str(row.id) == str(account.id):
        return {
            "target": TRANSFER_TARGET_OWNER,
            "available": False,
            "br_ref": "BR-MET-105a · BR-MET-1010",
            "account_id": None,
            "account_no": None,
            "reason": OWNER_TARGET_UNAVAILABLE,
        }
    return {
        "target": TRANSFER_TARGET_OWNER,
        "available": True,
        "br_ref": "BR-MET-105a · BR-MET-1010",
        "account_id": str(row.id),
        "account_no": row.account_no,
        "reason": None,
    }


def shortfall_path_options(account: models.Account) -> list[dict[str, Any]]:
    """Task 5.8's options — three since 2026-10-12 — each enabled or greyed WITH ITS REASON.

    ⚠ **THE FOURTH OPTION IS NO LONGER FLATLY DISABLED, AND THAT IS A CHANGE
    TO THE TASK AS WRITTEN.** B18 task 5.8 says *"option ④ disabled with
    BR-CUS-068's reason"*, which was right while the only transfer on offer was
    BR-BIL-013's landlord-agreement path (OQ-069's flag, still with no column).
    BR-CUS-097 signed a DIFFERENT transfer on 2026-08-24 — a sub-account's
    residue to its master — and that one has a resolvable target. So the option
    is enabled exactly when a master resolves and carries the refusal otherwise;
    the fourth option is still never a free-text account id.

    ⚠ **`write_off` IS NOT OFFERED — PO RULING 2026-10-12** (*"we will not
    write off at the time of move out"*). It is absent rather than greyed: a
    greyed row would be a control promising a door that does not exist here.
    The balance stays outstanding and BR-CUS-082 chases it; Finance or a
    System Admin writes it off later in Payments (BR-PAY-020).
    """
    options: list[dict[str, Any]] = []
    for path in SHORTFALL_PATHS:
        if path != SHORTFALL_TRANSFER:
            options.append({"path": path, "enabled": True, "br_ref": "BR-BIL-013", "reason": None})
            continue
        # ⚠ **THE OWNER COMES FIRST, AND THE ORDER IS A DECISION (`CR-056` W6).**
        # `shortfall_decision` posts to `available[0]`, so this list IS the
        # precedence. A DECLARED owner is who the money belongs to; the address
        # read below it is *which master account names this premises*, which is
        # the right answer only where nobody has declared an owner. Both rungs
        # are declared facts and the stronger one wins — the shape the PO's
        # 2026-08-27 ruling asks for.
        #
        # ⚠ **AND WHERE BOTH RESOLVE THEY NAME THE SAME ACCOUNT**, because the
        # owner's account hangs off the address (`BR-CUS-1010`). That is asserted
        # rather than assumed: a build where the two disagree is a building whose
        # declared owner is not the party its master account bills, and the
        # settlement must not choose between them by luck of list order.
        targets = [owner_target_for(account), transfer_target_for(account)]
        available = [t for t in targets if t["available"]]
        options.append(
            {
                "path": path,
                "enabled": bool(available),
                "br_ref": "BR-CUS-097 · BR-MET-105a",
                "reason": None if available else "; ".join(str(t["reason"]) for t in targets),
                "targets": targets,
            }
        )
    return options


#: BR-CUS-082 + BR-CUS-097 — and as of 2026-08-27 they DO resolve each other.
#: Carried on every shortfall decision so W7 inherits a settled fact rather than
#: a collision. ⚠ THE SUBJECT IS RESOLVED PER DECISION, NOT IN THIS CONSTANT:
#: `_dunning_for` below fills it in, because the answer depends on whether a
#: clerk actually tied the residue back.
DUNNING_AFTER_CLOSE: dict[str, Any] = {
    "chased": True,
    "restarts_at_tier": 1,
    "escalates_to_disconnection": False,
    "br_ref": "BR-CUS-082",
    "detail": "BR-CUS-082 (PO 2026-08-24, *'(b) continue, ladder restarts'*): the debt is "
    "still chased and the ladder restarts at TIER 1, not at the tier reached. A closed "
    "account cannot be escalated to disconnection — there is nothing left to disconnect — so "
    "this is a collections sequence, not a service one. BR-CUS-030's `dunning stops` is "
    "superseded for this case only; an account closing at zero still stops.",
}

#: ⚠ **THIS SAID `OQ-580` AND MEANT `OQ-532`, AND IT SAID THE QUESTION WAS
#: UNANSWERED WHEN IT HAD BEEN RULED — `DEF-2950`, two failures with one cause.**
#:
#: **The wrong id.** Two lanes minted `OQ-580` within an hour on 2026-08-27 for
#: unrelated questions, and the register renumbered THIS one to `OQ-532` at merge
#: that same day (`12-governance/14-id-reservations.md` records the race). The
#: code kept the retired number. `OQ-580` is now a real, live, different question
#: — *how does a utility retire premises it no longer serves* — so a reader
#: following the citation from this money path landed on an import question and
#: found it open, which is exactly the misread `CLAUDE.md`'s ID-grammar section
#: describes one order of magnitude down (`DEF-2804`, `DEF-2820`).
#:
#: **The stale claim.** Because the citation pointed at a question that IS open,
#: the sentence *"was not put to the Product Owner"* read as true for five days
#: after the PO answered it. **`OQ-532` CLOSED on 2026-08-27, option (B) — JOIN.**
#: PO verbatim: *"this si correct - B — join the existing position — Tier 4, on a
#: larger balance"*. A residue arriving on a master already at Tier 3 does not
#: restart the ladder and does not run its own sequence: it is more money on an
#: account already in collections, so the next letter is **Tier 4**.
#:
#: **THIS NARROWS `BR-CUS-082`**, whose literal words restart at Tier 1, and the
#: PO's reason is the one the question named: restarting RELIEVES a landlord
#: already deep in collections by resetting the clock on arrears they have not
#: paid. So `restarts_at_tier` below is the rule for a residue arriving on a
#: master with NO ladder running; where one IS running the position is joined.
#:
#: ⚠ **NOTHING HERE READS THE MASTER'S LADDER POSITION, AND THAT IS UNCHANGED.**
#: Collections has no tables — no ladder runs against anybody today — so the
#: ruled behaviour is carried as a STATEMENT for W7 to implement rather than as
#: an arithmetic this module could execute. What changed is that it is now a
#: ruling to be built and no longer a question to be asked.
LADDER_ON_A_MASTER_WITH_ARREARS = (
    "OQ-532 (CLOSED 2026-08-27, option B — JOIN) — the master's OWN ladder position is not "
    "read here, because collections has no tables and no ladder runs against anybody yet. "
    "The PO ruled what W7 must build: a residue arriving on a master ALREADY in collections "
    "JOINS that ladder's existing position rather than restarting it, so a master at TIER 3 "
    "receives TIER 4 on the larger balance. This NARROWS BR-CUS-082's restart-at-Tier-1, "
    "which governs a residue arriving where no ladder is running."
)


def _dunning_for(target: dict[str, Any] | None) -> dict[str, Any]:
    """BR-CUS-082 + BR-CUS-097 + OQ-366 — WHOSE door the restarted ladder knocks on.

    **OQ-366 CLOSED 2026-08-27 (PO), verbatim:** *"Sub account is closed when
    debt is trasnfer hence we now follow with owner for debt"*. The reasoning is
    STRUCTURAL rather than a balance of fairness — the sub-account is **closed**
    at the moment the residue transfers, so there is no open account on the
    tenant side to chase at all, which also disposes of the *both, differently*
    reading (a second ladder would have to run against a closed account).

    ⚠ **AND IT INHERITS THE SAME DAY'S QUALIFICATION, WHICH IS WHY THE SUBJECT
    IS PER-DECISION AND NOT A CONSTANT.** BR-CUS-097 as qualified 2026-08-27:
    the transfer is CLERK-INITIATED — *"if clark tied back to A during move out
    process"*. So the ladder follows the master **only for a residue a clerk
    actually tied back**. A shortfall written off, collected, or put on a
    payment plan moved nowhere, and a residue nobody tied back must not
    silently become the landlord's problem — and therefore must not generate
    the landlord's letters either. `target` is non-None on exactly the transfer
    path, which is exactly the clerk's act.

    Worked, end to end, on the case both rules were written against: `A-11024`
    closes owing **$328.70**, deposit and interest cover **$153.50**,
    **$175.20** survives, moves to the master, and TIER 1 fires on the MASTER.
    """
    dunning = dict(DUNNING_AFTER_CLOSE)
    # ⚠ **THE KEY IS RENAMED WITH THE FACT IT CARRIES (`DEF-2950`).** It read
    # `oq_580_master_ladder_position_unsigned` — the wrong question id AND a
    # claim of unsignedness that the PO had already answered. A key naming a
    # question that has been ruled is the sentence, not just the value, so both
    # move together; `07-frontend/.../moveShared.tsx` reads neither and the two
    # suites that assert it are updated in the same commit.
    dunning["oq_532_master_ladder_position"] = LADDER_ON_A_MASTER_WITH_ARREARS
    if target is None or not target.get("available"):
        dunning["subject"] = "the closed account itself"
        dunning["subject_br_ref"] = "BR-CUS-082"
        dunning["subject_detail"] = (
            "No residue was tied back to anyone, so BR-CUS-097 never fired and OQ-366's "
            "closure does not apply: the debt stays where it was and the restarted ladder "
            "runs against this account. A residue nobody tied back does not become the "
            "landlord's problem, and therefore does not become the landlord's letters."
        )
        return dunning
    dunning["subject"] = "master_account"
    dunning["subject_account_no"] = target.get("account_no")
    dunning["subject_account_id"] = target.get("account_id")
    dunning["subject_br_ref"] = "BR-CUS-082 · BR-CUS-097 · OQ-366 (CLOSED 2026-08-27)"
    dunning["subject_detail"] = (
        "PO 2026-08-27, closing OQ-366: *'Sub account is closed when debt is trasnfer hence "
        "we now follow with owner for debt'*. A CLERK tied this residue back, which is the "
        "consent BR-CUS-097 requires, and the sub-account is closed by then — so there is no "
        "open account on the tenant side to chase and TIER 1 fires on the master."
    )
    return dunning


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def shortfall_decision(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """S20 step 4 — where the balance that survives the close goes.

    *"Step 4 decides where the remaining balance goes. It cannot be skipped."*
    (B19 §15.9.4). Reachable ONLY on the `short` landing; every other landing
    renders `4 · Shortfall · skipped` and this refuses by name rather than
    quietly recording a decision about nothing.

    **A NEW ROW, NEVER AN EDIT** (hard rule 4) and **an `audit_log` row**
    (hard rule 7). ⚠ **ON THE `transfer` PATH THE MONEY NOW MOVES (`OQ-1250`
    CLOSED 2026-10-14 → a, PO D5).** This paragraph read *"What it does NOT do
    is move money … the transfer BR-CUS-097 rules on has no ledger path in this
    module"* until that ruling. Customers still writes no journal line: it
    hands the resolved target and the 2-dp shortfall to
    `apps/ledger/balance_transfer.py` through its seam, and the ledger posting
    service writes ONE entry, DR AR (owner) / CR AR (this account), in the same
    transaction as the audit row. Collect and payment plan move nothing. There
    is still no `final_settlements` table (`OQ-CUS-12516`).

    ⚠ **`write_off` IS REFUSED BY NAME — PO RULING 2026-10-12** (decision
    log, *"MOVE-OUT DOES NOT WRITE OFF"*), verbatim: *"we will not write off at
    the time of move out; these charges remain outstanding on the account and
    followup is done as per outstanding rules"*. Refused BEFORE anything is
    computed or written: no `write_offs` row, no decision, no audit row. The
    shortfall stays outstanding on the closed account and BR-CUS-082 chases
    it; a write-off is a later, separate act by Finance or a System Admin in
    Payments (BR-PAY-020). This replaced the 2026-10-11 build (`db7b2808d`)
    that raised a payments write-off REQUEST from this door.
    """
    from apps.customers import selectors

    data = payload if isinstance(payload, dict) else {}
    final_bill = data.get("final_bill")
    path = data.get("path")
    if path == SHORTFALL_WRITE_OFF_REFUSED:
        # PO 2026-10-12 — a write-off is never part of a move-out. Refused
        # first, so nothing is read, decided or audited on its behalf.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-082 · BR-PAY-020",
            message_key="customers.move_out.write_off_not_at_move_out",
            params={"path": path, "paths": list(SHORTFALL_PATHS)},
        )

    account = selectors.account_or_404(account_id)
    # CR-059 CS-20 — the day BR-CUS-057's interest accrues TO, stated by the
    # caller alongside the final bill. Never a clock (BR-TEN-043, gate G6).
    settlement = settlement_for(
        actor, account_id, final_bill=final_bill, as_of=data.get("as_of")
    )
    if settlement["landing"] != LANDING_SHORT:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-082",
            message_key="customers.move_out.no_shortfall",
            params={"landing": settlement["landing"], "gaps": settlement["gaps"]},
        )
    if path not in SHORTFALL_PATHS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-013",
            message_key="customers.move_out.shortfall_path_unknown",
            params={"path": path, "paths": list(SHORTFALL_PATHS)},
        )

    target: dict[str, Any] | None = None
    if path == SHORTFALL_TRANSFER:
        options = {opt["path"]: opt for opt in settlement["shortfall_paths"]}
        available = [t for t in options[SHORTFALL_TRANSFER]["targets"] if t["available"]]
        if not available:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-097 · BR-MET-105a",
                message_key="customers.move_out.shortfall_transfer_no_target",
                params={
                    "reasons": [str(t["reason"]) for t in options[SHORTFALL_TRANSFER]["targets"]]
                },
            )
        target = available[0]

    # ⚠ **ONE TRANSACTION FOR THE ENTRY AND THE DECISION'S AUDIT ROW.** On the
    # transfer path the books now move (`OQ-1250` CLOSED → a, PO D5
    # 2026-10-14), so a decision whose audit row landed while its entry did not
    # — or the other way round — would be two records of one act that
    # disagree. Either both are written or neither is.
    with transaction.atomic():
        posting_state = None
        if path == SHORTFALL_TRANSFER and target is not None:
            # ⚠ **ONLY MONEY IN THE BOOKS MOVES — coordinator rulings
            # 2026-10-14 (`CR-185-BRC10`; the walk's `DEF-CUS-10152`).** On an
            # account still OPEN (the wizard's step 3) the move-out does not
            # exist yet, so this only RECORDS the choice and previews the
            # figure; `services.move_out` records the tie-back inside its own
            # commit (`record_balance_to_owner_at_commit`) and it POSTS when the
            # final bill is issued. On an account already CLOSED (the move-out
            # record) it posts now — unless a drafted final bill is still
            # waiting to be sent, in which case it waits for that bill too.
            posting_state = (
                _tie_back_on_closed_account(
                    actor, account, settlement, target, as_of=data.get("as_of")
                )
                if getattr(account, "closed_at", None) is not None
                else _posts_at_completion(settlement, target)
            )
        decision = _shortfall_decision_row(
            actor, account, settlement, path=path, target=target, posting_state=posting_state
        )
        _audit(actor, "account.move_out.shortfall_decided", account.id, after=decision)
    return decision


def _posts_at_completion(settlement: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    """Step 3's answer on an OPEN account: recorded now, moved once billed.

    The figure is a PREVIEW — what the residue is with the final bill the
    clerk is looking at. The commit records the tie-back; the entry posts when
    that final bill is ISSUED, for what is owed THEN (coordinator ruling
    2026-10-14: *"the transfer must move only money that is IN THE BOOKS"*).
    """
    return {
        "posted": False,
        "posts_at": "final_bill_issue",
        "amount": settlement["verdict"]["shortfall"],
        "to_account_no": target.get("account_no"),
        "br_ref": "OQ-1250 CLOSED 2026-10-14 → (a) · CR-185-BRC10 (posted when the final bill issues)",
    }


def _transfer_target(settlement: dict[str, Any]) -> dict[str, Any]:
    """The resolved owner (BR-CUS-097, `available[0]`), or refused by name."""
    options = {opt["path"]: opt for opt in settlement["shortfall_paths"]}
    available = [t for t in options[SHORTFALL_TRANSFER]["targets"] if t["available"]]
    if not available:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-097 · BR-MET-105a",
            message_key="customers.move_out.shortfall_transfer_no_target",
            params={"reasons": [str(t["reason"]) for t in options[SHORTFALL_TRANSFER]["targets"]]},
        )
    return available[0]


def record_balance_to_owner_at_commit(
    actor: Any, account: models.Account, *, final_bill_draft: dict[str, Any] | None, moved_out_on: Any
) -> dict[str, Any]:
    """🔒 `services.move_out` — the tie-back, RECORDED inside the move-out commit.

    HUMAN-REVIEW-PENDING (CR-185-BRC10). Called after the final bill is drafted
    and before the account is closed, inside the commit's transaction, so a
    refused commit rolls the record back with everything else.

    ⚠ **ONLY MONEY IN THE BOOKS MOVES (coordinator ruling 2026-10-14).** The
    commit DRAFTS the final bill and the clerk sends it later from Billing, so
    at the commit part of the residue is a bill nobody has issued. So:

    * **a final bill was drafted** → the tie-back is recorded PENDING with the
      preview (prior balance + the drafted bill − deposit, interest, credit) and
      NOTHING is posted. It posts when that bill is issued
      (`post_pending_balance_to_owner`, called from billing's issue path), for
      what is owed then.
    * **nothing to bill** (every day already on an issued bill) → everything
      owed is already in the books, so it posts now, exactly as before.
    * **the draft was refused** → recorded pending with no bill named; the next
      final bill issued for the account posts it, and the move-out record can
      post it at once.

    No shortfall then → nothing recorded, and the answer says so. No owner
    account → refused by name, and the whole move-out with it, exactly as step
    3 refuses it.
    """
    draft = final_bill_draft or {}
    outcome = draft.get("outcome")
    total = draft.get("total") if outcome == "drafted" else None
    final_bill = Decimal(str(total)) if total not in (None, "") else ZERO
    settlement = settlement_for(actor, str(account.id), final_bill=final_bill, as_of=moved_out_on)
    if settlement["landing"] != LANDING_SHORT:
        return {
            "posted": False,
            "reason": "nothing_owed_at_move_out",
            "landing": settlement["landing"],
        }
    target = _transfer_target(settlement)
    if outcome == "nothing_to_bill":
        amount = Decimal(str(settlement["verdict"]["shortfall"]["display"]))
        posting_state = _post_and_record(
            actor, account, target, amount=amount, as_of=moved_out_on, invoice_id=None
        )
    else:
        posting_state = _record_pending(
            actor,
            account,
            settlement,
            target,
            invoice_id=draft.get("invoice_id") if outcome == "drafted" else None,
            invoice_no=draft.get("invoice_no") if outcome == "drafted" else None,
        )
    decision = _shortfall_decision_row(
        actor, account, settlement, path=SHORTFALL_TRANSFER, target=target,
        posting_state=posting_state,
    )
    _audit(actor, "account.move_out.shortfall_decided", account.id, after=decision)
    return posting_state


def _tie_back_on_closed_account(
    actor: Any,
    account: models.Account,
    settlement: dict[str, Any],
    target: dict[str, Any],
    *,
    as_of: Any,
) -> dict[str, Any]:
    """The move-out record's transfer: post at once, unless a bill still waits.

    The account is closed, so the move-out exists. If its drafted final bill
    has been sent (or there never was one) everything owed is in the books and
    the entry posts now, for the settlement's own figure. If a drafted final
    bill is still waiting, the money it carries is not in the books yet, so
    the tie-back is recorded pending and posts when that bill is issued.
    """
    waiting = seams.unissued_final_bill_for_account(str(account.id))
    if waiting is not None:
        return _record_pending(
            actor,
            account,
            settlement,
            target,
            invoice_id=waiting.get("invoice_id"),
            invoice_no=waiting.get("invoice_no"),
        )
    amount = Decimal(str(settlement["verdict"]["shortfall"]["display"]))
    return _post_and_record(actor, account, target, amount=amount, as_of=as_of, invoice_id=None)


def _tie_back_row(account: models.Account) -> Any:
    from apps.customers.tie_back_models import BalanceTieBack

    return (
        BalanceTieBack.objects.select_for_update()
        .select_related("owner_account")
        .filter(tenant_id=account.tenant_id, account_id=account.id)
        .first()
    )


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _record_pending(
    actor: Any,
    account: models.Account,
    settlement: dict[str, Any],
    target: dict[str, Any],
    *,
    invoice_id: Any,
    invoice_no: Any,
) -> dict[str, Any]:
    """Record (or keep) the PENDING tie-back. Writes no journal line."""
    from apps.customers.tie_back_models import STATUS_PENDING, BalanceTieBack

    preview = Decimal(str(settlement["verdict"]["shortfall"]["display"]))
    row = _tie_back_row(account)
    if row is not None and row.status != STATUS_PENDING:
        # Already settled once — idempotent per departing account (rule 6).
        return _state_of(row)
    if row is None:
        row = BalanceTieBack(
            tenant_id=account.tenant_id,
            account_id=account.id,
            owner_account_id=target["account_id"],
            currency=account.currency,
        )
    row.owner_account_id = target["account_id"]
    row.preview_amount = preview
    row.final_invoice_id = invoice_id
    row.decided_by = _actor_id(actor)
    row.save()
    state = {
        "posted": False,
        "pending": True,
        "posts_at": "final_bill_issue",
        "amount": _pair(preview),
        "to_account_no": target.get("account_no"),
        "final_bill_no": invoice_no,
        "br_ref": "OQ-1250 CLOSED 2026-10-14 → (a) · CR-185-BRC10 (posted when the final bill issues)",
    }
    _audit(actor, "account.move_out.balance_to_owner_pending", account.id, after=state)
    return state


def _post_and_record(
    actor: Any,
    account: models.Account,
    target: dict[str, Any],
    *,
    amount: Decimal,
    as_of: Any,
    invoice_id: Any,
) -> dict[str, Any]:
    """Post now and record the tie-back as posted (an existing pending row moves)."""
    import datetime as _dt

    from apps.customers.tie_back_models import STATUS_PENDING, STATUS_POSTED, BalanceTieBack

    row = _tie_back_row(account)
    if row is not None and row.status != STATUS_PENDING:
        return _state_of(row)
    entry_date = _entry_date_for(account, as_of)
    posted_at = _dt.datetime.combine(entry_date, _dt.time(0), tzinfo=seams.tenant_timezone())
    state = _post_balance_to_owner(
        actor,
        account,
        amount=amount,
        to_account_id=target["account_id"],
        to_account_no=target.get("account_no"),
        entry_date=entry_date,
        posted_at=posted_at,
    )
    if row is None:
        row = BalanceTieBack(
            tenant_id=account.tenant_id,
            account_id=account.id,
            owner_account_id=target["account_id"],
            currency=account.currency,
            preview_amount=amount,
            decided_by=_actor_id(actor),
        )
    row.status = STATUS_POSTED
    row.posted_amount = amount
    row.journal_entry_id = state["entry_id"]
    row.final_invoice_id = invoice_id or row.final_invoice_id
    row.settled_at = posted_at
    row.save()
    return state


def post_pending_balance_to_owner(
    account_id: Any,
    *,
    invoice_id: Any,
    entry_date: Any,
    posted_at: Any,
    actor: Any = None,
) -> dict[str, Any]:
    """🔒 Billing's issue path — the FINAL bill is in the books; post the tie-back.

    HUMAN-REVIEW-PENDING (CR-185-BRC10). Called by `apps/billing/issue.py`
    through `customers_seam.post_pending_balance_to_owner`, inside the issue's
    transaction, AFTER the bill's own entry, its deposit legs and the credit
    drawdown — so the account's receivable is now exactly what is owed.

    **THE AMOUNT IS WHAT THE BOOKS SAY THEN**: the account's AR position from
    the ledger (prior balance + the issued final bill − the deposit and its
    interest the issue applied; every payment, applied or not, already credited
    receivables when it was received), finalized to 2 dp (B4 half-up,
    `_display`). Never the preview — the preview was a forecast of this.

    ⚠ **THE UNAPPLIED CREDIT IS NOT SUBTRACTED AGAIN.** A payment posts CR AR
    for its whole amount when it arrives, so the part payments still calls
    *unapplied* is already inside the AR position; subtracting it would count
    it twice. Walk 2026-10-14: AC-2026-00043 step 3 previewed $311.90
    ($82.26 + $234.74 − $5.10), and the books after issue read $317.00 —
    the $5.10 was already netted in the $82.26 (`DEF-CUS-10151`).

    * no tie-back, or one already settled → nothing new (idempotent per
      departing account: a re-issue, a retry or a second final bill posts
      nothing);
    * owed ≤ $0.00 → recorded `nothing_owed`, nothing posted;
    * otherwise ONE entry DR AR (owner) / CR AR (tenant), through the ledger,
      and an audit row.

    A ledger refusal raises; the caller holds it in a savepoint and reports it
    rather than refusing the bill (BR-BIL-055), and the tie-back stays pending.
    """
    from apps.customers.tie_back_models import STATUS_NOTHING_OWED, STATUS_PENDING, STATUS_POSTED

    account = models.Account.objects.filter(id=account_id).first()
    if account is None:
        return {"posted": False, "reason": "no_tie_back"}
    row = _tie_back_row(account)
    if row is None:
        return {"posted": False, "reason": "no_tie_back"}
    if row.status != STATUS_PENDING:
        return {**_state_of(row), "created": False}
    positions = seams.ar_positions(account_ids=[str(account.id)])
    position = positions.amount_for(account.id)
    if position is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-097 · BR-LED-001",
            message_key="customers.move_out.balance_to_owner_not_posted",
            params={"account_no": account.account_no, "reason": "ar_position_unavailable"},
        )
    owed = Decimal(str(position))
    amount = Decimal(_display(owed))
    if amount <= ZERO:
        row.status = STATUS_NOTHING_OWED
        row.posted_amount = ZERO
        row.final_invoice_id = invoice_id
        row.settled_at = posted_at
        row.save()
        state = _state_of(row)
        _audit(actor, "account.move_out.balance_to_owner_nothing_owed", account.id, after=state)
        return state
    state = _post_balance_to_owner(
        actor,
        account,
        amount=amount,
        to_account_id=row.owner_account_id,
        to_account_no=row.owner_account.account_no,
        entry_date=entry_date,
        posted_at=posted_at,
    )
    row.status = STATUS_POSTED
    row.posted_amount = amount
    row.journal_entry_id = state["entry_id"]
    row.final_invoice_id = invoice_id
    row.settled_at = posted_at
    row.save()
    _audit(
        actor,
        "account.move_out.balance_to_owner_posted",
        account.id,
        after={**state, "preview": _pair(row.preview_amount), "final_invoice_id": str(invoice_id)},
    )
    return state


def _state_of(row: Any) -> dict[str, Any]:
    """A tie-back row as the answer every reader gets (record page, account)."""
    from apps.customers.tie_back_models import STATUS_PENDING, STATUS_POSTED

    return {
        "status": row.status,
        "posted": row.status == STATUS_POSTED,
        "pending": row.status == STATUS_PENDING,
        "posts_at": "final_bill_issue" if row.status == STATUS_PENDING else None,
        "amount": _pair(row.posted_amount if row.posted_amount is not None else row.preview_amount),
        "preview": _pair(row.preview_amount),
        "entry_id": str(row.journal_entry_id) if row.journal_entry_id else None,
        "to_account_no": row.owner_account.account_no if row.owner_account_id else None,
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
    }


def balance_to_owner_for(account: models.Account) -> dict[str, Any] | None:
    """The tie-back on this account, for the move-out record and the account. None if none."""
    from apps.customers.tie_back_models import BalanceTieBack

    row = (
        BalanceTieBack.objects.select_related("owner_account")
        .filter(tenant_id=account.tenant_id, account_id=account.id)
        .first()
    )
    return _state_of(row) if row is not None else None


def _entry_date_for(account: models.Account, as_of: Any) -> Any:
    """The BOOK date the balance-to-owner entry is dated — never a clock.

    The business day the caller STATED (`as_of`, the wizard's moved-out day)
    first; otherwise the day the tenancy ENDED, `accounts.closed_at`, which the
    move-out wrote and which the move-out record settles against (it states no
    terms — `DEF-CUS-5927`). Neither present: refused by name rather than dated
    today, because `post()` takes the date as an INPUT (PO 2026-08-11 closing
    OQ-107) and gate G6 keeps a clock out of this path. (On billing's issue
    path the date is the bill's own `issued_at` day, stated by billing.)
    """
    if as_of not in (None, ""):
        return as_of
    closed = getattr(account, "closed_at", None)
    if closed is not None:
        return closed
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-TEN-043 · OQ-107",
        message_key="customers.move_out.balance_to_owner_needs_date",
        params={"account_no": account.account_no},
    )


def _post_balance_to_owner(
    actor: Any,
    account: models.Account,
    *,
    amount: Decimal,
    to_account_id: Any,
    to_account_no: Any,
    entry_date: Any,
    posted_at: Any,
) -> dict[str, Any]:
    """🔒 `OQ-1250` CLOSED → (a) — ONE entry, AR to AR, through the ledger.

    HUMAN-REVIEW-PENDING (CR-185-BRC10; row in 09-human-review-ledger.md).

    PO D5, 2026-10-14, verbatim: *"option 1; property is always under landload
    agreement"*. So EVERY property with an owner (master) account counts as
    under agreement — `OQ-069`'s condition is met without an agreement record —
    and the residue a clerk ties back MOVES: DR accounts receivable on the
    owner's account / CR accounts receivable on this account, same control
    account, the account dimension is what differs. No revenue, no bad debt,
    total AR unchanged.

    **THE AMOUNT IS STATED BY THE CALLER, ALREADY 2 DP** — the books' figure at
    the final bill's issue, or the settlement's 2-dp shortfall when nothing was
    left to bill. The posting service refuses a third decimal place
    (BR-LED-025: the caller rounds), so the ledger is never a second rounding
    site.

    **THE TARGET IS THE RESOLVED ONE** (`available[0]`, owner first —
    BR-CUS-097, never a caller argument from a screen).
    """
    try:
        result = seams.post_balance_to_owner(
            from_account_id=str(account.id),
            to_account_id=str(to_account_id),
            amount=amount,
            entry_date=entry_date,
            posted_at=posted_at,
            currency=account.currency,
            actor=actor,
            memo=f"Balance to owner {account.account_no} → {to_account_no}",
            audit_context={
                "account_no": account.account_no,
                "owner_account_no": to_account_no,
            },
        )
    except seams.BalanceTransferRefused as refusal:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-097 · BR-LED-001",
            message_key="customers.move_out.balance_to_owner_not_posted",
            params={"account_no": account.account_no, "reason": str(refusal)},
        ) from refusal
    if result is None:  # pragma: no cover - the ledger publishes it
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-097 · BR-LED-001",
            message_key="customers.move_out.balance_to_owner_not_posted",
            params={"account_no": account.account_no, "reason": "ledger_publishes_no_transfer"},
        )
    return {
        "posted": True,
        "status": "posted",
        "entry_id": result.entry_id,
        "created": result.created,
        "amount": _pair(result.amount),
        "entry_date": str(entry_date),
        "to_account_no": to_account_no,
        "debit": {
            "designation": result.designation,
            "account_id": result.to_account_id,
            "account_no": to_account_no,
        },
        "credit": {
            "designation": result.designation,
            "account_id": result.from_account_id,
            "account_no": account.account_no,
        },
        "br_ref": "OQ-1250 CLOSED 2026-10-14 → (a) · PO D5 · BR-CUS-097 · US-LED-001",
    }


def _shortfall_decision_row(
    actor: Any,
    account: models.Account,
    settlement: dict[str, Any],
    *,
    path: str,
    target: dict[str, Any] | None,
    posting_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The decision payload `shortfall_decision` records and returns."""
    return {
        "account_id": str(account.id),
        "account_no": account.account_no,
        "path": path,
        "amount": settlement["verdict"]["shortfall"],
        "currency": settlement["currency"],
        "target": target,
        # BR-CUS-097 as QUALIFIED 2026-08-27 (PO, OQ-531 part 5): *"if clark
        # tied back to A during move out process"*. The transfer is NOT
        # automatic — it happens only because a person chose `transfer` on
        # this screen, and **the clerk's action is the consent**. The audit row
        # below has carried the actor since this function was written; the
        # DECISION now carries it too, so who tied the debt back is readable
        # without joining the trail. `None` on every other path, which is the
        # true answer: nothing was tied back.
        "tied_back_by": (
            {
                "actor_user_id": str(getattr(actor, "id", None) or getattr(actor, "pk", "") or "")
                or None,
                "br_ref": "BR-CUS-097 (qualified 2026-08-27)",
            }
            if path == SHORTFALL_TRANSFER
            else None
        ),
        "dunning": _dunning_for(target),
        "settlement": settlement,
        "persisted": False,
        "persistence_unavailable": "US-BIL-011 §5 — no `final_settlements` table exists in B2 "
        "or any addendum, so this decision rides the audit row and the response.",
        # ── WHAT MOVES IN THE BOOKS (`OQ-1250` CLOSED 2026-10-14 → a) ─────────
        # ⚠ **THIS READ `posting: {posted: False, oq: "OQ-1250"}` ON EVERY PATH
        # UNTIL 2026-10-14**, with the reason that no designation existed for a
        # receivable moving between two customers. The PO ruled D5 that day
        # (*"option 1; property is always under landload agreement"*) and the
        # transfer path now posts ONE entry, AR to AR, through the ledger
        # (`_post_balance_to_owner`). Every OTHER path still moves nothing, and
        # says so: collecting and a payment plan leave the debt where it is.
        "posting": (
            posting_state
            if posting_state is not None
            else {
                "posted": False,
                "br_ref": "BR-CUS-082 · BR-BIL-013",
                "detail": "this disposition leaves the balance on the account it is on, so "
                "nothing is posted: it is still owed there and chased there.",
            }
        ),
    }


# ════════════════════════════════════════════════════════════════════════════
# THE REFUND PATH (task 5.9) AND THE HELD EXCESS (BR-CUS-096)
# ════════════════════════════════════════════════════════════════════════════
def _audit(actor: Any, action: str, entity_id: Any, *, after: dict[str, Any]) -> None:
    """CLAUDE.md rule 7 — every money action writes `audit_log`.

    BEFORE is deliberately absent: none of these actions changes a row, so
    there is no prior state to record. What they record is a DECISION about
    money, which is why the row exists at all — BR-CUS-081 makes both the
    settlement and the refund money actions in so many words.
    """
    core_audit.write_row(
        action=action,
        entity_type="account",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=None,
        after=after,
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def refund_disposition(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """S20 step 3's conditional sub-panel — BR-CUS-081's settle-and-refund.

    *"settle the $142.30 from the $153.50 deposit and refund $11.20; the
    account closes at zero and the bill does NOT stand."* Both movements are
    recorded here as ONE decision with TWO amounts, because they are one
    ruling: a response carrying only the refund would read as "the whole
    deposit went back", which is the reading the PO rejected.

    Reachable ONLY on the `refund_due` landing. `refused_excess` is refused by
    name and points at `hold_excess` (BR-CUS-096); `refused_other_debt`,
    `short` and `settled` are refused for what they are.

    B19 §15.9.3's rules on the panel itself, all enforced:
      * the three methods are a CLOSED vocabulary;
      * the forwarding address is required for the **cheque only** — the `*` is
        on `Street` and the helper names the condition;
      * the amount is the settlement's own `refund_amount` and is NEVER a
        caller input, so a clerk cannot refund a figure they typed.

    **A NEW ROW, NEVER AN EDIT** (hard rule 4) and an `audit_log` row (rule 7).
    It does not PAY: payments owns `refunds`, whose `payment_id` is NOT NULL
    with no account column (OQ-195), so a deposit excess has no row to become.
    The disposition is recorded and the execution reported unavailable.
    """
    from apps.customers import selectors

    data = payload if isinstance(payload, dict) else {}
    account = selectors.account_or_404(account_id)
    settlement = settlement_for(
        actor,
        account_id,
        final_bill=data.get("final_bill"),
        # CR-059 CS-20 — stated beside the final bill, never read from a clock.
        as_of=data.get("as_of"),
    )

    if settlement["landing"] != LANDING_REFUND_DUE:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-081 · BR-CUS-096",
            message_key="customers.move_out.no_refund_due",
            params={"landing": settlement["landing"], "gaps": settlement["gaps"]},
        )

    method = data.get("method")
    if method in (None, ""):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-025",
            message_key="customers.move_out.refund_method_required",
            params={"methods": list(REFUND_METHODS)},
        )
    if method not in REFUND_METHODS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-025",
            message_key="customers.move_out.refund_method_unknown",
            params={"method": method, "methods": list(REFUND_METHODS)},
        )
    address = (
        data.get("forwarding_address") if isinstance(data.get("forwarding_address"), dict) else {}
    )
    if method in REFUND_METHODS_NEEDING_ADDRESS and not str(address.get("street") or "").strip():
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-025",
            message_key="customers.move_out.forwarding_street_required",
            params={"method": method},
        )

    decision = {
        "account_id": str(account.id),
        "account_no": account.account_no,
        "currency": settlement["currency"],
        # BR-CUS-081's TWO movements, both named. The settlement is a new row
        # against everything outstanding; the refund is what is left.
        "settled_from_deposit": settlement["verdict"]["settled_from_deposit"],
        "refund_amount": settlement["verdict"]["refund_amount"],
        "bill_stands": False,
        "method": method,
        "forwarding_address": dict(address) if method in REFUND_METHODS_NEEDING_ADDRESS else None,
        "settlement": settlement,
        "persisted": False,
        "execution_unavailable": (
            {
                "code": "refund_has_no_row_to_become",
                "br_ref": "OQ-195 · BR-PAY-014",
                "detail": "payments owns `refunds` and B2 types `refunds.payment_id uuid NOT "
                "NULL` with no account column, so a refund raised against a DEPOSIT EXCESS "
                "rather than one payment cannot be written. `apps.payments.credit."
                "refund_from_credit_balance` stubs on the same schema question.",
            },
            {
                "code": "deposit_settlement_not_posted",
                "br_ref": "OQ-248 · BR-CUS-081 · BR-BIL-013",
                "detail": "this decision posts nothing. The deposit's settlement is posted by "
                "the FINAL BILL's issue, and since OQ-248 closed (PO 2026-09-30, option A) the "
                "part left over is credited to customer credit there, as money owed back. "
                "Paying the refund out is payments' refund row, which stubs on OQ-195.",
            },
        ),
    }
    _audit(actor, "account.move_out.refund_disposed", account.id, after=decision)
    return decision


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def hold_excess(actor: Any, account_id: Any, payload: Any = None) -> dict[str, Any]:
    """BR-CUS-096 — *"hold until dispute close"*, recorded as a decision.

    The `refused_excess` landing: the deposit is worth more than everything
    owed AND part of what is owed is disputed, so *"the excess is HELD until
    the dispute closes"* because the amount owed can still move. B19 §15.11's
    read-back says the same in the clerk's words — `Disposition · Excess
    $13.12 pending decision`.

    ⚠ **BR-CUS-096 DOES NOT SAY WHO RELEASES THE HOLD, OR WHEN**, and its own
    text records that as unsettled. Nothing in this repository chases a held
    excess — no release path, no timer, no queue — so the result says so on
    every call rather than leaving a customer's money to be discovered. That
    sentence is the deliverable here; inventing a release clock would be
    answering a question the PO has not been asked.

    An `audit_log` row (hard rule 7): holding a customer's money is a money
    action even though no money moves, and it is the only record that the
    decision was taken at all.
    """
    from apps.customers import selectors

    data = payload if isinstance(payload, dict) else {}
    account = selectors.account_or_404(account_id)
    settlement = settlement_for(
        actor,
        account_id,
        final_bill=data.get("final_bill"),
        # CR-059 CS-20 — stated beside the final bill, never read from a clock.
        as_of=data.get("as_of"),
    )
    if settlement["landing"] != LANDING_REFUSED_EXCESS:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-096",
            message_key="customers.move_out.excess_not_held",
            params={"landing": settlement["landing"], "gaps": settlement["gaps"]},
        )
    decision = {
        "account_id": str(account.id),
        "account_no": account.account_no,
        "currency": settlement["currency"],
        "settled_from_deposit": settlement["verdict"]["settled_from_deposit"],
        "held_amount": settlement["verdict"]["excess"],
        "disputed_amount": settlement["open_dispute_total"],
        "released": False,
        "release_unavailable": {
            "code": "held_excess_has_no_release_path",
            "br_ref": "BR-CUS-096 (open half)",
            "detail": "BR-CUS-096 holds the excess until the dispute closes and does not say "
            "who releases it or on what clock. Nothing in this repository chases a held "
            "excess, so it sits until a human looks. Raised, not invented.",
        },
        "settlement": settlement,
        "persisted": False,
    }
    _audit(actor, "account.move_out.excess_held", account.id, after=decision)
    return decision


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@1d161e9 (04-docs/05-modules/03-customers/02-business-rules.md ·
#         04-docs/02-decisions/19-cr031-service-request-capture.md §15 ·
#         04-docs/02-decisions/18-cr030-onboarding-design.md §11 W5 ·
#         04-docs/05-modules/04-metering/02-business-rules.md BR-MET-105a/107 ·
#         12-governance/02-decision-log.md "NINE PO RULINGS" 2026-08-24)
# generated: 2026-08-24 by the CR-030 W5 move-out lane (tasks 5.7 · 5.8 · 5.9 · 5.14)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S20 steps 3/4 have no route yet; another lane owns api.py) E=deferred(no-frontend-half, same lane split) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_w5_move_out_settlement.py
# exceptions: (1) NOT ON THE G7 GLOB LIST and NO ROW IN
#         12-governance/09-human-review-ledger.md. This file holds 🔒 money
#         math and carries HUMAN-OWNED · HUMAN-REVIEW-PENDING, but enrolling
#         it is a process event (B12 r2) and the ledger is another lane's
#         file. REPORTED for the daily PO batch, exactly as the five globs of
#         2026-08-11 record.
#         (2) THE FINAL BILL IS STATED BY THE CALLER. Billing publishes no
#         per-account final-bill total; `settle_final_bill` reads it off the
#         drafted `invoices.total`. Absent, the read model reports the gap and
#         states no landing.
#         (3) TWO CROSS-MODULE READS ARE MADE THROUGH `seams.resolve` FROM A
#         FILE G20 DOES NOT HARVEST (it reads apps/*/seams.py and
#         apps/*/<neighbour>_seam.py only): `apps.payments.selectors.
#         account_credit_position` and `apps.customers.selectors.
#         deposit_interest_accrued`, plus two that do not exist at all
#         (`billing.open_dispute_total`, `metering.unbanked_export_credit`).
#         DEF-075's own shape. REPORTED for the seams lane rather than
#         declared here, since apps/customers/seams.py is not this lane's file.
#         (4) NO MONEY MOVES. There is no `final_settlements` table, customers
#         writes no invoice, payment or journal line, `apps.payments.credit.
#         refund_from_credit_balance` stubs on OQ-195, and — AMENDED 2026-09-30 —
#         `apps.ledger.deposit_legs.post_deposit_applied` no longer refuses the
#         over-credit case: OQ-248 closed (option A) and the excess is credited to
#         customer credit at the final bill's issue. Every decision here is recorded in `audit_log` and says
#         `persisted: False`.
#         ⚠ AMENDED 2026-10-14 (CR-185-BRC10, PO D5, OQ-1250 CLOSED → a): the
#         TRANSFER path now POSTS — one AR→AR entry through
#         `apps/ledger/balance_transfer.py`, owner account DR / this account
#         CR — and `posting.posted` is True with the entry. The 2026-09-01 text
#         below is the trail, not the current behaviour.
#         ⚠ AMENDED 2026-09-01 (CR-056 W6): the shortfall decision now NAMES
#         what does not move, as `posting: {posted: False, oq: "OQ-1250"}`.
#         US-LED-001's contract table has seventeen source events and a
#         receivable moving between two customer accounts is not one of them,
#         so no designation exists to resolve. Not stubbed with a raise — the
#         precedent is OQ-500's own row, and raising would restore the refusal
#         task 27 removes.
#         (5) BR-MET-105a IS CONFIRMED AND THE OWNER IS A POSTING TARGET AGAIN.
#         ⚠ THIS ENTRY READ "ITS COLUMN DOES NOT EXIST" AND THAT WAS TRUE WHEN
#         IT WAS WRITTEN AND STOPPED BEING THE WHOLE TRUTH (DEF-2951). The
#         column the rule NAMES — `premises.owner_customer_id` — is still
#         absent from apps/metering/models.py and from every migration. The
#         FACT the rule wanted arrived under another name: a typed owner ROW
#         with an account of its own (`premises_owners.master_account_id`,
#         BR-MET-1010), which is the read the PO named on 2026-08-27
#         (*"Bascially Premises -> owner = Master account"*). `owner_target_for`
#         resolves through it; what genuinely remains unavailable is an address
#         with no declared owner, and that is a FAULT the screen states rather
#         than a silence.
#         (6) TASK 5.8's "option ④ disabled with BR-CUS-068's reason" IS
#         SUPERSEDED by BR-CUS-097 (2026-08-24): the fourth option is enabled
#         when a master account resolves for the premises. The target is
#         resolved from data and is never a caller argument.
#         (7) THE SIBLING-CREDIT RULE IS UNSIGNED. Credits are shown and never
#         applied, debts are applied — B19 §15.9.4's drawing, implemented as
#         drawn and reported as a question.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
