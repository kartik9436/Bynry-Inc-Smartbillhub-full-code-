# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 — the exception step: decide, record, apply)
#           Screens: S31.3
# Rules:    BR-BIL-015 (a missing read is a CHOICE — estimate | hold | bill
#           without the service) · BR-BIL-060 (bulk everywhere; one bulk action
#           is N rows plus one shared id) · BR-BIL-061 (billing the base-only
#           cohort is a recorded staff opt-in, not a consequence of the status
#           class) · BR-BIL-003 (a late-fee waiver is manual, never bulk) ·
#           BR-BIL-055 (a hold writes the pending queue) · BR-BIL-075 (an
#           applied late fee names the tenant's own charge code — PO ruling
#           2026-08-26, closing DEF-719) · BR-BIL-007 (a fee's account is the
#           tenant's, never a literal) · BR-BIL-010 (the GL stamp resolves at
#           issue and freezes) · BR-BIL-001 + B4 ❄️ (the fee's AMOUNT, which
#           the charge code does NOT supply) · CLAUDE.md rule 3
#           (an estimated quantity carries its unit) · rule 4's reasoning (the
#           trail is append-only; a change of mind supersedes)
# Tests:    06-backend/tests/test_us_bil_003_decisions.py ·
#           06-backend/tests/test_def_719_late_fee_charge_code.py (BR-BIL-075 —
#           a bill CARRYING an applied late fee is issued, and 8.13 is 8.13)
# Impacts:  apps/billing/runs.py (the run consumes what this returns) ·
#           apps/billing/gather.with_readings (the seam this finally calls) ·
#           apps/billing/issue._gl_account_for (the fee branch, which can now
#           resolve a late fee's account instead of refusing the whole bill)
# ───────────────────────────────────────────────────────
"""The missing middle: a staff decision, recorded, and then actually applied.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (the `late_fee`/`apply` branch, and
since 2026-09-14 the `billing_continuity` case — `DEF-BIL-5270` — whose
`investigate` choice takes an account out of a run, and `accounts_touched`,
which names the set a decision RE-PRICES; `DEF-BIL-5271`) —
this module became a money path on 2026-08-26: under **BR-BIL-075** it decides
WHICH tenant charge code an applied late fee books to, and therefore which GL
account an immutable invoice line is stamped with. Its row is in
`12-governance/09-human-review-ledger.md`.

✅ **AND IT IS GUARDED NOW — PO RULING 2026-08-26, verbatim: "add it".** The
paragraph here used to end: *"`human_owned.txt` does NOT list this file, so G7
does not guard it; editing that register is a process event and is REPORTED by
the lane rather than taken."* That reporting was right — the register's own
header says the guarded set must not drift with whoever is coding, so a lane may
not add itself — and the report was answered.

⚠ **THE GUARD BIT THE MOMENT IT COULD SEE THE FILE, WHICH IS THE POINT.** Adding
the glob turned G7 red on this very module — *"lacks HUMAN-OWNED marker"* — even
though the review-ledger row had existed for hours. A marker and a row are not
protection while no glob matches: that is the SECOND time this exact escape has
hit a money path here, and `issue.py`'s own line in the register records the
first. Everything else in this module writes no money.

Two halves existed and nothing joined them. `BillRunDecision` has been a table
since the schema slice — append-only, with a `bulk_action_id`, carefully
designed — and `prepare_run` has listed what needs deciding since phase 1 was
built. **Nothing wrote a decision and nothing read one.** A clerk could see
that account A-10432 needs an estimate, and there was no way to say so, and no
way for saying so to reach a bill.

`gather.with_readings` was written for exactly this and had no caller: hard-won
law 2, at the seam rather than at a prop.

────────────────────────────────────────────────────────────────────────────
WHY APPLYING IS A TRANSFORMATION AND NOT A WRITE
────────────────────────────────────────────────────────────────────────────
`apply_decisions` takes the prepared run and returns a NEW prepared run. It
does not touch the database except to record a hold, and it recomputes nothing.

That shape is forced by BR-BIL-039's purity rule and it is worth keeping for a
second reason: **a clerk must be able to see what their decisions did before
anything is billed.** A function that returned a modified run can be rendered;
a function that wrote its effects into the pipeline can only be trusted. The
PO's own flow is "decide on screen, then run the batch" — deciding is not
billing, and this keeps that true structurally.

RE-GATHERING IS DELIBERATELY NOT DONE. An estimate replaces the READING on
data already gathered. Re-gathering would re-read the customer record and pick
up a name changed since the run began, so the bill would print a name the
clerk never saw against a period priced before it. `with_readings` exists to
swap one field and leave the rest exactly as gathered.

────────────────────────────────────────────────────────────────────────────
WHAT IS IMPLEMENTED, AND WHAT REFUSES
────────────────────────────────────────────────────────────────────────────
`missing_read` (all three choices), `base_only_billing`, `late_fee`, `no_usage`
and CR-038 W8's seven reading cases are implemented on contracts that exist.

**ONE case still REFUSES by name rather than being half-done:** `overcharge`
(BR-BIL-029) needs the trailing-average guardrail, computed from billing history
this module cannot yet query. It is named in `UNSUPPORTED_CASES` and raises —
the prime directive's shape: implement to the boundary, and make the gap loud
rather than silent.

⚠ **`extra_charge` WAS THE SECOND SUCH CASE AND IS NOT ANY MORE (CR-051 task 18,
2026-08-31), AND THE DISTINCTION IT DREW IS THE ONE THAT MATTERS HERE.** The old
paragraph said it *"needs the tenant's charge codes with their own GL — the
charge-code reader does not exist, and inventing an amount here would put a
number on a customer's bill that no rule produced."* Two claims; only the second
survived. The charge-code reader HAS existed since BR-BIL-075 landed on
2026-08-26 (`_late_fee_charge_id` uses it), so refusing to STORE the clerk's
reply had lost its reason — while S31.3's *Charges to add* tab went on offering
Apply on every row and the server refused every one of them.

**So the two halves are now separated, which is the whole build:** the decision
is RECORDED with the same `apply`/`waive` the late fee uses, and the money
application does not exist, so `apply` HOLDS the account at a named boundary
(`HOLDING_CHOICES`) rather than billing it without the charge a human asked for.
BR-BIL-007's amount belongs to the tenant's own charge code and no case row in
this product names one.

⚠ **AND THE HONEST HALF, MEASURED RATHER THAN IMPLIED: NOTHING IN THIS PRODUCT
EMITS AN `extra_charge` CASE ROW TODAY (`DEF-2596`, open).** `runs._decisions_for`
emits `base_only_billing` and `missing_read`; `read_analysis` emits seven reading
cases. Neither `late_fee` nor `extra_charge` is among the nine, so the tab is
empty on every database there is and this choice can be recorded and never
arises. It is built anyway and said plainly: a decision that CAN be recorded and
never arises is honest, and a screen offering Apply with nothing behind it is
not. The day a pass emits the row, the reply lands.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.billing import gather, models, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import tenancy as core_tenancy

#: Choices a clerk may make about a missing read (BR-BIL-015, verbatim).
CHOICE_ESTIMATE = "estimate"
CHOICE_HOLD = "hold"
CHOICE_BILL_WITHOUT_SERVICE = "bill_without_service"

#: The base-only cohort (BR-BIL-061) and the zero-usage account.
CHOICE_INCLUDE = "include"
CHOICE_EXCLUDE = "exclude"

#: The late fee (BR-BIL-003). A waiver is always manual and never bulk.
CHOICE_APPLY = "apply"
CHOICE_WAIVE = "waive"

#: ── CR-038 W8 — the read-analysis dispositions (2026-08-26) ─────────────────
#: Every one is a RECORDED row with an actor (the PO reaffirmed the
#: no-pre-selected-default rule the same day: *"an auditor asking 'who chose to
#: estimate M-4412?' gets a name"*). One word, one meaning, across cases:
#: `bill_as_is` on a high, a low and a days row is the same act — bill what the
#: run gathered, with the flag recorded as looked-at — so it is one constant,
#: not three spellings.
CHOICE_KEEP = "keep"  # estimated_read: the estimate stands (BR-MET-029 lawful input)
#: The clerk wants the ACTUAL read instead. This routes to the field-visit /
#: actual-read path that already exists — the read is entered on S25/S28 and the
#: account re-prepares — so the choice HOLDS the account for the catch-up run
#: (BR-BIL-055's one queue) rather than billing the estimate they just refused.
#: Nothing here invents a reading.
CHOICE_REPLACE_WITH_ACTUAL = "replace_with_actual"
CHOICE_BILL_AS_IS = "bill_as_is"  # bill what was gathered; the look is recorded
CHOICE_INVESTIGATE = "investigate"  # hold the account out while a human looks
CHOICE_CONFIRM_FACTOR = "confirm_factor"  # meter_factor: ×N is right — recorded
#: days_threshold (BR-MET-121): price the span AS the cycle's own N days. ⚠ The
#: pricing-side usage-proration hook this feeds DOES NOT EXIST — B4.3 prorates
#: BASE charges on service_days/cycle_days and no signed rule scales a measured
#: consumption to N days — so the recorded choice HOLDS the account at that
#: named boundary instead of billing the unprorated span as though nobody had
#: chosen. See `HOLDING_CHOICES` below; the gap is REPORTED, never bridged with
#: invented quantity math.
CHOICE_PRORATE_TO_CYCLE_DAYS = "prorate_to_cycle_days"
CHOICE_WAIT_NEXT_CYCLE = "wait_next_cycle"  # days_threshold: the read bills next cycle
#: replacement: price BOTH segments of a mid-cycle swap (old meter's final read
#: + new meter's start). ⚠ Same posture as the prorate above: the pricing seam
#: (`billing_reads_for_unit`) prices the single latest head, so both-segments
#: pricing is a named boundary and the recorded choice HOLDS the account there.
CHOICE_PRORATE_BOTH_SEGMENTS = "prorate_both_segments"
#: true_up (BR-BIL-006 / GT-9 / WE-13 ❄): the trued-up quantity bills on THIS
#: bill at current-period rates — which is what the pipeline already does with
#: the committed read (its stored consumption IS the register-arithmetic
#: result). The choice records that a human looked and let it; it changes no
#: data because the signed math is already in the read.
CHOICE_APPLY_NEXT_BILL = "apply_next_bill"

#: **THE TENANT CHARGE CODE AN APPLIED LATE FEE BOOKS TO — BR-BIL-075 (PO
#: ruling 2026-08-26, closing DEF-719).** PO verbatim: *"A · The late fee uses a
#: tenant charge code — like NSF and reconnect already do"*. The rejected shape
#: was a twelfth GL designation hard-wiring every late fee to the seeded `4200`,
#: which would have made this the one fee a utility cannot point at its own
#: account.
#:
#: `"LATE"` is NOT this module's choice and is not a guess. Billing's own field
#: map states it against this exact column — `03-field-map.md`, the *Late-fee
#: apply/waive* row: *"applied → draft fee line `invoice_lines.charge_id` →
#: LATE (B2 `charges`)"* — and `EP-BIL-01-bill-run.md` §5 says the same
#: (*"applied → draft fee line (LATE charge code)"*). `LATE` is seeded on every
#: tenant by `seed_demo.CHARGE_CODES` **and** by provisioning (LATE/CONN/DISC/
#: NSF from the same `[F]` fixture), so unlike `CC-RECON` (DEF-700 — a code the
#: reconnect feature needs and no seed writes) this code is reachable on every
#: tenant in this tree the day the rule ships.
#:
#: It is a DEFAULT and not a constant at the call site: `apply_decisions` takes
#: `late_fee_charge_code=` exactly as `first_bill` takes `code=` for `CONN`, so
#: a tenant that names theirs something else is one argument away rather than a
#: fork away.
DEFAULT_LATE_FEE_CHARGE_CODE = "LATE"

#: ⚠⚠ **WHAT THE CODE SUPPLIES, AND WHAT IT DOES NOT — BR-BIL-075, stated here
#: because the ruling's own words invite the wrong reading.** "Like NSF and
#: reconnect" is exact about the GL ACCOUNT and SILENT about the amount, and
#: the analogy breaks at precisely that point: NSF and reconnect are FLAT fees
#: whose charge code carries the figure, and **a late fee is not flat**. Its
#: amount is computed by ❄️ FROZEN B4 math (BR-BIL-001 — `max($5.00, 1.5% ×
#: overdue portion)`, above a tenant-set balance floor seeded at $25.00) and
#: `GT-10`'s **8.13** is a signed golden figure: `usage 82.08 + base 18.50 +
#: fee 8.13 + tax 8.30 = 117.01`, re-signed 2026-08-10 under HUMAN-GUIDE §6.
#:
#: So the code says WHERE the fee books and B4 keeps saying WHAT IT IS. A
#: charge code carrying an `amount` that overrode 8.13 would change a frozen
#: figure — a finance re-sign via HUMAN-GUIDE §6, never an implementation
#: choice. **This module therefore reads `id` off the resolved code and NOTHING
#: ELSE**, which is why `_late_fee_charge_id` returns a string rather than the
#: row: a function that cannot see `amount` cannot spend it by accident.
#:
#: The seeded `LATE` row is `percent_with_minimum`, so `charge_by_code` already
#: answers `amount=None` for it — that is a property of the seed and NOT the
#: guarantee, because a tenant may re-key their own code to `flat` at any time.
#: The guarantee is the return type of `_late_fee_charge_id` and the test that
#: configures `LATE` flat at **$99.00** and asserts the bill still charges 8.13.
#:
#: ⚠⚠ **AMENDED 2026-09-07 BY `CR-078` (BR-RAT-1011), AND THE AMENDMENT IS TO
#: WHERE THE CODE COMES FROM — NOT TO WHAT THIS MODULE READS OFF IT.** PO
#: verbatim: *"you ahve to take late fees form charge code mentione din the
#: plan - if plan doent provide you that charge code then you have to put zero
#: on late payment. - Logic aplplied ot Minimum late fee $5"*. Finance
#: re-signed the same day, because the fee is a ❄️ FROZEN B4/B5 figure.
#:
#: TWO THINGS CHANGE HERE AND ONE FAMOUSLY DOES NOT:
#:
#:   * **WHICH CODE.** It is the one the PLAN names (`rate_plans
#:     .late_fee_charge_id`), read through `rating_seam.plan_late_fee_terms`,
#:     not the constant `"LATE"` below. `DEFAULT_LATE_FEE_CHARGE_CODE` survives
#:     as the BACKFILL's seed name and as the argument default for a caller
#:     that has no plan in hand; it is no longer what a run resolves.
#:   * **NO CODE MEANS NO FEE.** A plan naming none charges **$0.00** and this
#:     module adds no line at all — where before it REFUSED THE WHOLE RUN by
#:     name. That refusal was right under BR-BIL-075 (an unbookable fee) and is
#:     wrong under this ruling (a fee that does not exist). It is not a silent
#:     drop: `selectors.plans_missing_late_fee_charge`, `manage.py
#:     cr078_late_fee_codes` and gate `G121` each count the plans in that state.
#:
#:   * **THE AMOUNT IS STILL NOT READ OFF THE CODE HERE.** `_late_fee_charge_id`
#:     still returns a string. `percent` and `min_amount` are read by
#:     `late_fee.assess_late_fee_for_plan`, which is where B4's arithmetic
#:     lives and where the single finalization happens (BR-RAT-003). Two
#:     readers of one row, each taking the half it is entitled to — the
#:     *"a function that cannot see `amount` cannot spend it by accident"*
#:     guarantee above is UNCHANGED and still worth having.
#:
#: ⚠ **THE HALF THIS MODULE CANNOT DELIVER, NAMED RATHER THAN IMPLIED:** the
#: ruling says the ignored amount is *stated on screen* rather than silently
#: dropped, and S31.3 renders no such sentence today. That is a frontend
#: deliverable and is REPORTED as owed, not faked here with a field nothing
#: reads (hard-won law 2).

#: Cases whose INPUTS do not exist yet. Named so the refusal says which, and
#: so a reader can see the gap is known rather than overlooked.
#:
#: ⚠ **`extra_charge` LEFT THIS DICT ON 2026-08-31 (CR-051 task 18), AND WHAT
#: CHANGED IS NOT THE MONEY — IT IS WHETHER A REPLY CAN BE STORED AT ALL.** The
#: entry read: *"BR-BIL-007 adds a tenant CHARGE CODE to the bill, and the
#: charge-code reader (with its own GL, S12) does not exist yet. An amount
#: invented here would reach a customer's bill without any rule having produced
#: it."* **Its first clause has expired and its second has not**, and separating
#: them is the whole of this task:
#:
#:   * the charge-code READER exists — `gather._resolve("rating",
#:     "charge_by_code")`, wired for BR-BIL-075 on 2026-08-26 and used by
#:     `_late_fee_charge_id` below. So the reason given for refusing the
#:     RECORDING is gone;
#:   * an AMOUNT is still produced by nothing. BR-BIL-007 says NSF and reconnect
#:     read theirs from the tenant's own charge code, and no case row in this
#:     product carries the code it means (see `DEF-2596` — no pass emits an
#:     `extra_charge` row at all). Inventing one is still forbidden.
#:
#: So the decision becomes RECORDABLE and its money application does not exist:
#: see `CHOICES_BY_CASE` and `HOLDING_CHOICES` below, where `apply` holds the
#: account at that named boundary exactly as `prorate_to_cycle_days` does. The
#: consequence for the screen is the point — S31.3's *Charges to add* tab drew
#: Apply on every row and the server refused every one of them with *"this case
#: cannot be applied yet"*, so a clerk's answer went nowhere.
UNSUPPORTED_CASES: dict[str, str] = {
    "overcharge": (
        "BR-BIL-029's guardrail compares a draft against the account's trailing "
        "average, which is computed from billing history this module cannot yet "
        "query. Releasing or holding on a guardrail nobody computed would be a "
        "decision about a number that does not exist."
    ),
}

#: A waiver is a per-case, manual act (BR-BIL-003). Bulk-applying one would let
#: a single click forgive a thousand fees with one reason between them, and the
#: reason is the whole evidence a waiver leaves.
BULK_FORBIDDEN: frozenset[tuple[str, str]] = frozenset({("late_fee", CHOICE_WAIVE)})

#: 🔒 HUMAN-REVIEW-PENDING · DEF-BIL-10200 — the answer a Check decision takes
#: when NOBODY answered it. Decision log 2026-10-17: *"THE LATE FEE IS APPLIED
#: BY THE BILL RUN"* (PO: *"this is good - we have to fix it"*) — the fee bills
#: unless a clerk waives it on that account. Every other decision stays
#: unanswered until a person answers (changes row 45: no check fixes anything
#: by itself); the late fee is not a fix, it is the rule the run applies.
#: Read by `apply_decisions` and by `check_store._effective_answers`, so the
#: Check's Ready count and Calculate's partition agree.
DEFAULT_ANSWERS: dict[str, str] = {"late_fee": CHOICE_APPLY}

# ── THE BULK CHECK'S DECISIONS (PO rulings 2026-09-30, changes rows 44–46) ──
#: *"these are correct"* (the alternatives table) · *"this should be decision
#: by clark - we point it out and suggest but dont make it auto"* (the seven
#: former AUTO rows) · *"rest fo thema re good"* (the four kinds). **The FIRST
#: choice of each is the default the screen pre-selects** — a suggestion where
#: the case has one, HOLD where the ruling made Hold the default (no
#: multiplier, city limits unknown).
CHOICE_ACCEPT_SUGGESTION = "accept_suggestion"
CHOICE_BILL_ON_ESTIMATE = "bill_on_estimate"
CHOICE_BILL_TOTAL_FLAT = "bill_total_flat_rate"
CHOICE_BILL_WITH_MULTIPLIER_1 = "bill_with_multiplier_1"
CHOICE_TREAT_INSIDE = "treat_as_inside"
CHOICE_TREAT_OUTSIDE = "treat_as_outside"
CHOICE_USE_EARLIER_VERSION = "use_earlier_version"
CHOICE_SPLIT_AT_CHANGE = "split_at_change"
CHOICE_APPLY_THIS_BILL = "apply_this_bill"
CHOICE_BILL_WITHOUT_PAYMENT = "bill_without_payment"
CHOICE_REVERSE_WITH_FEE = "reverse_with_fee"
CHOICE_REVERSE_NO_FEE = "reverse_no_fee"
CHOICE_ADD_TO_BILL = "add_to_bill"
CHOICE_SKIP = "skip"
CHOICE_RESET = "reset"

CHECK_CHOICES_BY_CASE: dict[str, tuple[str, ...]] = {
    # Former AUTO → suggestion, pre-selected, with Hold beside it (row 45).
    "reading_has_no_unit": (CHOICE_ACCEPT_SUGGESTION, CHOICE_HOLD),
    "possible_rollover": (CHOICE_ACCEPT_SUGGESTION, CHOICE_ESTIMATE, CHOICE_HOLD),
    "meter_swapped": (CHOICE_ACCEPT_SUGGESTION, CHOICE_HOLD),
    "plan_not_published": (CHOICE_ACCEPT_SUGGESTION, CHOICE_HOLD),
    "plan_has_no_tariff_for_service": (CHOICE_ACCEPT_SUGGESTION, CHOICE_HOLD),
    "no_charge_applies_to_this_customer_type": (CHOICE_ACCEPT_SUGGESTION, CHOICE_HOLD),
    "price_changed_mid_period": (CHOICE_ACCEPT_SUGGESTION, CHOICE_SPLIT_AT_CHANGE, CHOICE_HOLD),
    # Ratified decisions (row 44), default first.
    "account_held_by_disputed_read": (CHOICE_HOLD, CHOICE_BILL_ON_ESTIMATE),
    "anchor_register_went_backwards": (CHOICE_ESTIMATE, CHOICE_HOLD),
    "anchor_meter_exchanged": (CHOICE_ESTIMATE, CHOICE_HOLD),
    "anchor_tou_windows_unanchorable": (CHOICE_BILL_TOTAL_FLAT, CHOICE_HOLD),
    "anchor_multiplier_unstated": (CHOICE_HOLD, CHOICE_BILL_WITH_MULTIPLIER_1),
    # Changes row 44 (built 2026-10-01): a meter never read — the ruled path's
    # missing factor, its own tag. Hold first: it is the ruled default.
    "meter_has_no_multiplier": (CHOICE_HOLD, CHOICE_BILL_WITH_MULTIPLIER_1),
    # 🔒 `DEF-BIL-8246` closed by ruling: `unit_has_no_plan` is NOT a decision since 2026-10-01 (PO: *"we ahve
    # to show the warning that no plan on unit, please fi the plan first"*,
    # BR-BIL-1063). There is no customer-type default plan (`OQ-RAT-12782`
    # closed as a deliberate absence, BR-RAT-1047), so the account STAYS
    # BLOCKED with the plan fixed on the row (`check_fixes.FIX_SET_PLAN`) —
    # nothing a clerk can answer here could bill it.
    "premises_jurisdiction_unstated": (CHOICE_HOLD, CHOICE_TREAT_INSIDE, CHOICE_TREAT_OUTSIDE),
    "tariff_has_no_version_in_force_at_service_date": (CHOICE_USE_EARLIER_VERSION, CHOICE_HOLD),
    # BR-BIL-1053 — payments & balances.
    "paid_after_cutoff": (CHOICE_APPLY_THIS_BILL, CHOICE_APPLY_NEXT_BILL),
    "unmatched_payment": (CHOICE_HOLD, CHOICE_BILL_WITHOUT_PAYMENT),
    "bounced_payment_not_reversed": (CHOICE_REVERSE_WITH_FEE, CHOICE_REVERSE_NO_FEE, CHOICE_HOLD),
    "plan_instalment_due": (CHOICE_ADD_TO_BILL, CHOICE_SKIP),
    # `level_pay_off_track` is NOT here since 2026-09-30 (DEF-BIL-8241): it is
    # a WARNING, so nothing is asked, and its old *reset* choice was a
    # re-level the Check may not perform (`check_taxonomy`).
}

#: ── BR-BIL-1054 (PO 2026-09-30, changes row 41) · LEAVE A READY ACCOUNT OUT ──
#: *"in left hand panel can you also add ready to bill tab"* — each ready
#: account has **Leave out** and **Put back**. It is a DECISION ROW like any
#: other (append-only; Put back supersedes Leave out, so the trail says who
#: took the account out and who put it back), and it is NOT a Check case: no
#: check raises it, so it is never in `MUST_ANSWER_CASES` and never on a tag.
#: `leave_out` HOLDS (see `HOLDING_CHOICES`), which is what sends the account
#: to Pending billing — reason code `LEFT_OUT_REASON`, *"left out by clerk"*
#: (plan DB3: a reference code in `bill_run_exclusions.reason_code`, which is
#: tenant-extensible text, so no column moves). Only a READY account may be
#: left out; that is refused at the route (`check_api.run_leave_out`).
CASE_LEFT_OUT = "left_out"
CHOICE_LEAVE_OUT = "leave_out"
CHOICE_PUT_BACK = "put_back"
LEFT_OUT_REASON = "staff_left_out_by_clerk"

#: The Check's decision cases that must be ANSWERED before the account is
#: billed (*"An account is Ready when every problem on it is a warning or has
#: an accepted decision"*). An unanswered one keeps the account OUT of the
#: calculate pass — not written to the pending queue, simply not priced — so
#: nothing is ever billed on a suggestion nobody accepted.
#:
#: 🔒 DEF-BIL-8650 / DEF-BIL-8653 (2026-10-01) — and THREE MORE than the Check
#: cases: `base_only_billing` (PO 2026-08-11: *"opt in or opt out … on
#: screen"*), `billing_continuity` in EVERY state (a gap too — it is a DECISION
#: on the Check, so an unanswered one is an open decision, not a warning), and
#: `missing_read` (BR-BIL-015: estimate, hold or bill without it). Until then
#: the first two were billed with no answer ($63.25 and $8.00 on the J72 walk)
#: and the third went on to Calculate, broke there and was queued again at
#: Send — two places for one account.
MUST_ANSWER_CASES: frozenset[str] = frozenset(CHECK_CHOICES_BY_CASE) | {
    "base_only_billing",
    "billing_continuity",
    "missing_read",
}

#: Recorded choices whose MONEY APPLICATION is built, because the pass that
#: follows already holds the data it needs:
#:   * `reading_has_no_unit`/accept — the reading was gathered in the meter's
#:     recorded unit; accepting bills it (and not accepting holds it);
#:   * `possible_rollover`/accept and `anchor_multiplier_unstated`/×1 — the
#:     answer is fed back into the next pass (`runs._ANSWERS`), which prices
#:     the suggested quantity;
#:   * `plan_has_no_tariff_for_service`/accept — the account was gathered
#:     WITHOUT that service; accepting bills the others;
#:   * `price_changed_mid_period` — accept bills the whole period at the
#:     period-end version (the split dropped); split keeps the split;
#:   * the payment choices that leave THIS bill as gathered.
#: Every other non-hold choice is RECORDED and HOLDS the account at a named
#: boundary until its application is built — the `extra_charge`/`apply`
#: precedent (DEF-BIL-8240–8279 name each).
APPLIED_CHOICES: frozenset[tuple[str, str]] = frozenset(
    {
        ("reading_has_no_unit", CHOICE_ACCEPT_SUGGESTION),
        ("possible_rollover", CHOICE_ACCEPT_SUGGESTION),
        ("anchor_multiplier_unstated", CHOICE_BILL_WITH_MULTIPLIER_1),
        # The ruled path's adapter reads it (`resolution_switch._resolve_for`).
        ("meter_has_no_multiplier", CHOICE_BILL_WITH_MULTIPLIER_1),
        ("plan_has_no_tariff_for_service", CHOICE_ACCEPT_SUGGESTION),
        ("price_changed_mid_period", CHOICE_ACCEPT_SUGGESTION),
        ("price_changed_mid_period", CHOICE_SPLIT_AT_CHANGE),
        # `DEF-BIL-8412` (PO 2026-10-01, OQ-217 closed) — *Apply next bill* is no
        # longer billed like *Apply to this bill*: the bill leaves payments posted
        # after the period off its payments line and the NEXT bill counts them
        # (`issue._defers_late_payments`, `open_balance.whole_account`).
        ("paid_after_cutoff", CHOICE_APPLY_NEXT_BILL),
        # 🔒 DEF-BIL-8243 (2026-09-30) — *Apply to this bill* BILLS the account
        # as gathered, and that IS the whole application: the payment is
        # already posted and allocated by PAYMENTS (its own journal entry, the
        # one ledger posting there is), and this bill's balance-forward block
        # is stamped at issue from payments' allocations
        # (`payments_seam.prior_position_for_account`, BR-BIL-035). So the
        # $120.00 appears ONCE, as *payments received*, and billing adds no
        # line, no credit and no journal line for it — nothing here can count
        # it a second time. Until this line it HELD the account.
        ("paid_after_cutoff", CHOICE_APPLY_THIS_BILL),
        ("unmatched_payment", CHOICE_BILL_WITHOUT_PAYMENT),
        ("plan_instalment_due", CHOICE_SKIP),
        # 🔒 DEF-BIL-8243 (2026-09-30) — *Add to bill* BILLS the account and
        # the due instalment is printed on it as its own line, stamped at issue
        # (`issue._stamp_plan_instalment`). It is NOT a charge line: the
        # instalment is part of arrears already on earlier bills, already in AR
        # and already in the balance forward, so a charge would bill it twice.
        ("plan_instalment_due", CHOICE_ADD_TO_BILL),
        # 🔒 DEF-BIL-8244 (2026-09-30) — *Accept* on a swapped meter bills BOTH
        # parts: the answer is fed back through `ANCHOR_ANSWER_CASES` and the
        # pass prices the old meter's part and the new meter's part separately.
        ("meter_swapped", CHOICE_ACCEPT_SUGGESTION),
    }
)
CHECK_HOLDING: frozenset[tuple[str, str]] = frozenset(
    (case, choice)
    for case, choices in CHECK_CHOICES_BY_CASE.items()
    for choice in choices
    if (case, choice) not in APPLIED_CHOICES
)

#: The dispositions each case OFFERS, in the order the rule states them. This
#: is the vocabulary S31.3 renders, and it is published from here rather than
#: hardcoded in the screen because BR-BIL-015's three choices and BR-BIL-003's
#: manual-only waiver are rules THIS module enforces — a client-side option list
#: would drift off them the day one changed, and the failure mode is a control
#: that submits a choice the server refuses.
#:
#: The two `UNSUPPORTED_CASES` are deliberately absent rather than mapped to an
#: empty tuple: an empty list of choices reads as "no options", where the truth
#: is "this case cannot be recorded at all" — `record_decision` says which and
#: why, and a case with no entry here has no row to offer choices on anyway.
CHOICES_BY_CASE: dict[str, tuple[str, ...]] = {
    # BR-BIL-015, verbatim order: estimate it, hold the account, or bill
    # without the service.
    "missing_read": (CHOICE_ESTIMATE, CHOICE_HOLD, CHOICE_BILL_WITHOUT_SERVICE),
    # BR-BIL-061 (PO 2026-08-11): opt in or opt out, at prepare time, on screen.
    # 🔒 PO ruling 2026-09-30 (fixed-charge case 2, option B): the opt-out is
    # WAIVE, not "leave out" — *"clark is making decision which mean he is
    # deciding that base charges will not be billed and we need to provide a
    # warning and leave it ; next mnth we keep the consitnent behaviour"*. A
    # reason is required, the account is not billed, Sign off shows the
    # amount waived, and NOTHING is carried forward (no pending-queue row, so
    # no catch-up run ever bills it). `exclude` stays lawful for rows recorded
    # before the ruling (`HOLDING_CHOICES`); it is no longer offered.
    "base_only_billing": (CHOICE_INCLUDE, CHOICE_WAIVE),
    "no_usage": (CHOICE_INCLUDE, CHOICE_EXCLUDE),
    # BR-BIL-003: a waiver is manual — allowed here, refused in bulk.
    "late_fee": (CHOICE_APPLY, CHOICE_WAIVE),
    # BR-BIL-007 (CR-051 task 18, 2026-08-31). THE SAME TWO WORDS AS THE LATE
    # FEE, and deliberately: r10 line 4256 draws Apply and Waive on this table,
    # `CHARGE_FILTERS` in `billRunStep23.tsx` already groups the two cases
    # together as *Charges to add*, and one word meaning one act across cases is
    # the convention CR-038 W8 set (`bill_as_is` on three different rows). A
    # third spelling for "put it on the bill" would be a vocabulary, not a
    # choice.
    #
    # ⚠ **THE WAIVER IS ALLOWED IN BULK HERE AND FORBIDDEN ON THE LATE FEE, and
    # that asymmetry is the RULE's, not this module's.** BR-BIL-003 is about a
    # late fee: *"a waiver is a per-case, manual decision, and the reason is the
    # whole of the evidence it leaves"*. BR-BIL-007 says nothing of the kind
    # about a service charge, and BR-BIL-060 puts bulk on every case surface. So
    # `BULK_FORBIDDEN` is left naming exactly the pair the rule names —
    # extending a signed restriction to a case it was never given for is
    # inventing law, the same act as ignoring it.
    "extra_charge": (CHOICE_APPLY, CHOICE_WAIVE),
    # ── CR-038 W8 — the read-analysis cases (2026-08-26). Bulk applies to all
    # of them (BR-BIL-060: bulk on every case surface); only the late-fee
    # waiver above stays manual-only.
    "estimated_read": (CHOICE_KEEP, CHOICE_REPLACE_WITH_ACTUAL),
    "high_usage": (CHOICE_BILL_AS_IS, CHOICE_INVESTIGATE),
    "low_usage": (CHOICE_BILL_AS_IS, CHOICE_INVESTIGATE),
    "days_threshold": (
        CHOICE_PRORATE_TO_CYCLE_DAYS,
        CHOICE_WAIT_NEXT_CYCLE,
        CHOICE_BILL_AS_IS,
    ),
    "meter_factor": (CHOICE_CONFIRM_FACTOR, CHOICE_INVESTIGATE),
    # `DEF-BIL-5270` — the account's reads do not pick up where its last ISSUED
    # bill left off. THE SAME TWO WORDS the high/low cases use, and
    # deliberately: *bill what the run gathered, with the look recorded* and
    # *hold the account out while a human looks* are the two acts available
    # here too, and a third spelling for either would be a vocabulary rather
    # than a choice (the convention `CR-038` W8 set with `bill_as_is` on three
    # different rows).
    #
    # ⚠ **THERE IS DELIBERATELY NO "FIX IT" CHOICE.** The repair for a gap or
    # an overlap is a read entered, a re-read superseded or a meter exchange
    # recorded — all of them in METERING, on S25/S28, none of them on this
    # screen. Offering a third word here would be offering a button that
    # cannot do what it says.
    "billing_continuity": (CHOICE_BILL_AS_IS, CHOICE_INVESTIGATE),
    "replacement": (CHOICE_PRORATE_BOTH_SEGMENTS, CHOICE_BILL_AS_IS, CHOICE_INVESTIGATE),
    "true_up": (CHOICE_APPLY_NEXT_BILL, CHOICE_HOLD),
    **CHECK_CHOICES_BY_CASE,
}

#: 🔒 PO ruling 2026-09-30 (fixed-charge case 4): *"Bill as is"* is removed for
#: an OVERLAP and stays only for a GAP. An overlap no longer reaches a clerk as
#: a question at all — the account's bill starts the day after its last bill
#: (`check_engine._account_period_start`), base prorated — so the only overlap
#: a case row can still describe is one the run cannot shorten (the last bill
#: already covers the whole period), and billing it "as is" would charge the
#: overlapped days' base twice. `record_decision` refuses it by name.
CONTINUITY_CHOICES_BY_STATE: dict[str, tuple[str, ...]] = {
    "gap": (CHOICE_BILL_AS_IS, CHOICE_INVESTIGATE),
    "overlap": (CHOICE_INVESTIGATE,),
}

#: The cases whose decision must carry a REASON — the reason is the whole of
#: the evidence a waiver leaves (BR-BIL-003's words, and the PO's for case 2).
REASON_REQUIRED: frozenset[tuple[str, str]] = frozenset({("base_only_billing", CHOICE_WAIVE)})

#: (case, choice) pairs that take the account OUT of this run, into the pending
#: queue (BR-BIL-055's ONE queue, two doors). The first three rows are the
#: behaviour `_is_held` has always had, written as data; the CR-038 W8 rows are
#: new and each states WHY its choice holds:
#:
#:   * `replace_with_actual` — the clerk refused the estimate; billing it anyway
#:     would un-make their decision. The account waits for the actual read.
#:   * `investigate` — a number a human has said is suspect must not reach a
#:     document while they look (the same reasoning as BR-MET-024's hold).
#:   * `wait_next_cycle` — BR-MET-121's second disposition by name.
#:   * `prorate_to_cycle_days` / `prorate_both_segments` — ⚠ recorded choices
#:     whose PRICING application does not exist yet (no signed rule scales a
#:     consumption to N days; the pricing seam prices one head, not two
#:     segments). The account holds at that NAMED boundary, because the only
#:     alternatives are billing money the clerk explicitly asked to change, or
#:     inventing quantity math nobody signed. Both boundaries are REPORTED.
#:   * `true_up`/`hold` — the trued-up quantity is baked into the committed
#:     read (register arithmetic, BR-MET-029), so "not this bill" can only
#:     mean the whole account waits.
HOLDING_CHOICES: frozenset[tuple[str, str]] = frozenset(
    {
        ("missing_read", CHOICE_HOLD),
        ("base_only_billing", CHOICE_EXCLUDE),
        ("no_usage", CHOICE_EXCLUDE),
        # `_is_held` historically accepted hold/exclude on any of the three
        # legacy cases; both spellings stay lawful there so no recorded row
        # changes meaning.
        ("missing_read", CHOICE_EXCLUDE),
        ("base_only_billing", CHOICE_HOLD),
        ("no_usage", CHOICE_HOLD),
        ("estimated_read", CHOICE_REPLACE_WITH_ACTUAL),
        ("high_usage", CHOICE_INVESTIGATE),
        ("low_usage", CHOICE_INVESTIGATE),
        ("days_threshold", CHOICE_WAIT_NEXT_CYCLE),
        ("days_threshold", CHOICE_PRORATE_TO_CYCLE_DAYS),
        ("meter_factor", CHOICE_INVESTIGATE),
        # `DEF-BIL-5270` — `investigate` holds for the reason every other
        # `investigate` holds: a quantity a human has said is suspect must not
        # reach a document while they look. `bill_as_is` is NOT here — billing
        # what the run gathered is the whole of that act, and the recorded row
        # is what makes it a decision rather than a default.
        ("billing_continuity", CHOICE_INVESTIGATE),
        ("replacement", CHOICE_INVESTIGATE),
        ("replacement", CHOICE_PRORATE_BOTH_SEGMENTS),
        ("true_up", CHOICE_HOLD),
        # CR-051 task 18 — see the block under `CHOICES_BY_CASE`. `apply` is a
        # recorded choice whose MONEY APPLICATION does not exist: BR-BIL-007's
        # amount comes from the tenant's own charge code and no case row in this
        # product names one. The account therefore holds at that named boundary,
        # because the only alternatives are billing it WITHOUT the charge the
        # clerk explicitly asked to add — silently under-charging, and un-making
        # a decision they took on screen — or inventing a figure no rule
        # produced, which is what `UNSUPPORTED_CASES` refused this case for in
        # the first place. `waive` is not here: waiving means the charge does
        # not go on the bill, so the account bills normally and the recorded row
        # is the whole of the act (the `late_fee`/`waive` shape exactly).
        ("extra_charge", CHOICE_APPLY),
        # BR-BIL-1054 — a ready account the clerk left out of this run.
        (CASE_LEFT_OUT, CHOICE_LEAVE_OUT),
    }
    | CHECK_HOLDING
)

#: The separator inside a case-row id. See `case_row_id`.
CASE_ID_SEPARATOR = "|"


def case_row_id(case: str, account_id: Any, service_id: Any) -> str:
    """The stable id of ONE case row on S31.3 — its decision's natural key.

    A case row is not a stored entity. It is *"this account, this case, this
    service, undecided"*, computed by `prepare_run` on every viewing, so it has
    no primary key to serve. What it does have is the key a decision about it
    lands under: `current_decision(bill_run, account_id, case, service_id=…)`
    resolves on exactly (account, case, service), which is therefore what the
    row is identified BY.

    Derived rather than minted, and that is the property that matters: the id a
    screen selected yesterday still names the same case today, and a resolve
    posted twice writes one decision and one supersession rather than landing
    on two different rows. The run id is NOT part of it — it is already in the
    path, and repeating it would let a caller name one run in the URL and
    another in the body.

        base_only_billing|018f…-account|              (no service)
        missing_read|018f…-account|018f…-service      (per service)
    """
    return CASE_ID_SEPARATOR.join(
        (case, str(account_id), "" if service_id in (None, "") else str(service_id))
    )


def split_case_row_id(value: str) -> tuple[str, str, str | None]:
    """`case_row_id` in reverse: (case, account_id, service_id or None).

    REFUSES a malformed id instead of guessing at its parts. An id that does
    not split into three is a client that built one by hand, and recording a
    decision against a half-parsed account is worse than refusing to record it.
    """
    parts = (value or "").split(CASE_ID_SEPARATOR)
    if len(parts) != 3 or not parts[0] or not parts[1]:
        raise BillingRuleError(
            f"case id {value!r} is not a case row of this run. A case row is named by "
            "its decision's natural key — case, account and service — and one that "
            "cannot be split into those three names no account, so no decision is "
            "recorded for it."
        )
    return parts[0], parts[1], (parts[2] or None)


def resolve_cases(
    *,
    bill_run: Any,
    case_id: str,
    choice: str,
    reason: str | None = None,
    case_ids: list[str] | None = None,
    amount: Decimal | None = None,
    unit: str | None = None,
    decided_by: Any = None,
) -> tuple[uuid.UUID | None, list[models.BillRunDecision]]:
    """S31.3's one write: record this choice against one case row, or against N.

    BULK IS DECIDED HERE AND NOT BY THE CLIENT (BR-BIL-060). A screen looping N
    times would produce N UNRELATED decisions and lose the fact the rule exists
    to keep — *"was this considered individually, or was it one of a
    thousand?"* — because only the server can mint an id shared across rows. So
    `case_ids` carries the selection and this decides the rows.

    **Every row in one call must be the same CASE.** A selection is made inside
    one case table on S31.3, and a bulk action whose rows spanned cases would
    apply one choice ("hold") to two different questions. Refused by name.

    A bulk of ONE is still a bulk: it keeps its `bulk_action_id`, because the
    clerk used the bulk control and the trail should say so.
    """
    case, account_id, service_id = split_case_row_id(case_id)
    if not case_ids:
        return None, [
            record_decision(
                bill_run=bill_run,
                account_id=account_id,
                case=case,
                choice=choice,
                reason=reason,
                amount=amount,
                unit=unit,
                service_id=service_id,
                decided_by=decided_by,
            )
        ]

    parsed = [split_case_row_id(value) for value in case_ids]
    cases = {row[0] for row in parsed}
    if cases != {case}:
        raise BillingRuleError(
            f"a bulk action covers one case at a time; this one names {sorted(cases)} "
            f"against a path that says {case!r}. One choice applied across two "
            "different questions is not one decision taken N times."
        )
    if (case, choice) in BULK_FORBIDDEN:
        # Checked BEFORE the id is minted so a refused bulk leaves nothing at
        # all — not a bulk_action_id with no rows under it. `record_decision`
        # refuses again per row; this one names the whole action.
        raise BillingRuleError(
            f"{case}/{choice} may not be taken in bulk (BR-BIL-003). A first-time "
            "waiver is a per-case, manual decision, and the reason is the whole "
            "of the evidence it leaves — one reason shared across a thousand "
            "accounts is not a reason for any of them.",
            br_ref="BR-BIL-003",
        )

    bulk_action_id = uuid.uuid4()
    rows = [
        record_decision(
            bill_run=bill_run,
            account_id=row_account_id,
            case=case,
            choice=choice,
            reason=reason,
            amount=amount,
            unit=unit,
            service_id=row_service_id,
            decided_by=decided_by,
            bulk_action_id=bulk_action_id,
        )
        for _case, row_account_id, row_service_id in parsed
    ]
    return bulk_action_id, rows


def accounts_touched(rows: Any) -> tuple[str, ...]:
    """The accounts a decision write covers — `DEF-BIL-5271`(a)'s scope.

    **WHAT A RE-PRICE IS FOR, DERIVED FROM WHAT WAS WRITTEN AND NEVER FROM WHAT
    WAS ASKED.** The caller holds a `case_id` and maybe a `case_ids` list;
    `resolve_cases` is what turns those into rows, and a row is the only proof
    an account was decided about. Deriving the set from the REQUEST would
    re-price accounts a refusal had just excluded.

    De-duplicated and ORDERED as the rows arrived, so a bulk of 44 that names
    one account twice re-prices it once and a re-price walks accounts in the
    order the clerk's selection did.
    """
    seen: dict[str, None] = {}
    for row in rows or ():
        account_id = getattr(row, "account_id", None)
        if account_id is not None:
            seen.setdefault(str(account_id), None)
    return tuple(seen)


def accounts_paid_but_not_arrived(bill_run: Any) -> set[str]:
    """🔒 DEF-BIL-8651 — the accounts whose *Paid after cut-off* payment has not
    ARRIVED: payments still has it `processing` (no clearing date, so it meets
    no bill — `apps/payments/services.record_payment`), or payments could not
    be asked. *Apply to this bill* puts the payment on this bill through its
    allocations, and a payment with none would print **$0.00 paid** against a
    clerk's *Apply* — a choice that does nothing. So for these accounts that
    choice is REFUSED when written and NEVER COUNTS as an answer (a tag's
    standing answer included); *Apply next bill* still does. Fail closed: a
    payments module that cannot answer leaves every such account here.

    One finding read and one payments read for the whole run."""
    from apps.billing import check_models, payments_seam

    named = {
        str(account_id)
        for account_id in check_models.BillRunFinding.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), bill_run=bill_run, code="paid_after_cutoff"
        ).values_list("account_id", flat=True)
    }
    if not named:
        return set()
    # The SAME window the Check's finding used: the run's effective bill date
    # (typed, else the cycle's bill day), as `selectors.prepared_for` resolves it.
    from apps.billing import runs, selectors

    period_end = getattr(bill_run, "period_end", None)
    bill_date = getattr(bill_run, "bill_date", None)
    if period_end is not None and getattr(bill_run, "pk", None) is not None:
        cycle_bill_day, _due_days = selectors.cycle_terms_for(bill_run)
        bill_date = runs.effective_bill_date(bill_date, cycle_bill_day, period_end)
    statuses = payments_seam.payment_statuses(
        sorted(named), period_end=period_end, bill_date=bill_date
    )
    if statuses is None:
        return named
    # An account the finding names and payments no longer lists has nothing
    # that could be applied: fail closed, exactly as *processing* does.
    return {
        account_id
        for account_id in named
        if not statuses.get(account_id)
        or payments_seam.PAYMENT_NOT_ARRIVED in statuses[account_id]
    }


def record_decision(
    *,
    bill_run: Any,
    account_id: str,
    case: str,
    choice: str,
    reason: str | None = None,
    amount: Decimal | None = None,
    unit: str | None = None,
    service_id: Any = None,
    decided_by: Any = None,
    bulk_action_id: uuid.UUID | None = None,
) -> models.BillRunDecision:
    """Write one decision. APPEND-ONLY — a change of mind supersedes.

    The PO's requirement was *"all the decisions are made on screen and
    recorded"*, and **recorded is the operative word**. A month later, "why was
    this account estimated instead of held?" has an answer with a name on it,
    and a customer disputing an estimated bill can be told who made that call.

    Changing a decision writes a NEW row pointing the old one at it, rather
    than updating in place. Evidence that can be edited is not evidence — the
    same reasoning hard rule 4 applies to money, applied to a decision trail.
    """
    if case in UNSUPPORTED_CASES:
        raise BillingRuleError(
            f"decision case {case!r} cannot be applied yet: {UNSUPPORTED_CASES[case]}"
        )
    _refuse_if_sent(bill_run)
    if bulk_action_id is not None and (case, choice) in BULK_FORBIDDEN:
        raise BillingRuleError(
            f"{case}/{choice} may not be taken in bulk (BR-BIL-003). A first-time "
            "waiver is a per-case, manual decision, and the reason is the whole "
            "of the evidence it leaves — one reason shared across a thousand "
            "accounts is not a reason for any of them."
        )
    if case == "billing_continuity" and choice == CHOICE_BILL_AS_IS:
        from apps.billing import runs

        start = getattr(bill_run, "period_start", None)
        if start is not None:
            state = runs.period_anchor(account_id, period_start=start).state
            if choice not in CONTINUITY_CHOICES_BY_STATE.get(state, (choice,)):
                raise BillingRuleError(
                    "an overlap cannot be billed as is — the overlapped days' base "
                    "would be charged twice (PO ruling 2026-09-30, fixed-charge case 4).",
                    message_key="billing.check.choiceNotOffered",
                )
    if (
        case == "paid_after_cutoff"
        and choice == CHOICE_APPLY_THIS_BILL
        and str(account_id) in accounts_paid_but_not_arrived(bill_run)
    ):
        raise BillingRuleError(
            "the payment is still processing — it has not reached the books, so it "
            "meets no bill and Apply to this bill would put nothing on it "
            "(DEF-BIL-8651). Apply it to the next bill.",
            message_key="billing.check.paidAfterCutoff.notArrived",
            br_ref="BR-BIL-1053",
        )
    if (case, choice) in REASON_REQUIRED and not (reason or "").strip():
        raise BillingRuleError(
            f"{case}/{choice} needs a reason — a waiver's reason is the whole of the "
            "evidence it leaves (PO ruling 2026-09-30, fixed-charge case 2).",
            message_key="billing.check.reasonRequired",
        )
    if choice == CHOICE_ESTIMATE and (amount is None or not unit):
        # CLAUDE.md rule 3. An estimated quantity with no unit is a number
        # nobody can check against a meter.
        raise BillingRuleError(
            "an estimate must carry BOTH a quantity and its unit (CLAUDE.md "
            "rule 3) — the estimate reaches a customer's bill as a consumption."
        )

    tenant_id = core_tenancy.current_tenant_id()
    superseded = current_decision(bill_run, account_id, case, service_id=service_id)
    row = models.BillRunDecision.objects.create(
        tenant_id=tenant_id,
        bill_run=bill_run,
        account_id=account_id,
        service_id=service_id,
        case=case,
        choice=choice,
        reason=reason,
        amount=amount,
        unit=unit,
        # WHO, by id. A caller holding the `users` row passes it; an API layer
        # holds only the session user's id and must not have to fetch the row
        # to record a decision — `audit.actor_user_id` accepts either and never
        # accepts a name (BR-AUD-003: the trail stores the id, not a label).
        # ⚠ It replaces `getattr(x, "pk", x)`, which would have STORED an
        # actor object the first time one reached it — DEF-BIL-5090's shape
        # rather than its occurrence, since `billing/api` passes an id here.
        decided_by_id=audit.actor_user_id(decided_by),
        bulk_action_id=bulk_action_id,
    )
    if superseded is not None:
        # The ONLY update this trail ever takes: pointing an old row at the one
        # that replaced it. The row's own content is never touched.
        superseded.superseded_by = row
        superseded.save(update_fields=["superseded_by"])
    return row


def record_bulk(
    *,
    bill_run: Any,
    account_ids: list[str],
    case: str,
    choice: str,
    reason: str | None = None,
    amount: Decimal | None = None,
    unit: str | None = None,
    decided_by: Any = None,
) -> tuple[uuid.UUID, list[models.BillRunDecision]]:
    """One human decision applied to N accounts — BR-BIL-060.

    The PO's words: *"if there are 500 or 1000 or 5000 bills to be generated
    and 1000 bills has late fees, it is impossible for user to do this manually
    account by account."*

    **Each account still gets its OWN row.** Its bill changed, so its trail
    must say so, and a dispute six months later is about one account. What the
    shared `bulk_action_id` adds is the answer to a DIFFERENT question — "was
    this considered individually, or was it one of a thousand?" — and a single
    row cannot carry both facts.
    """
    bulk_action_id = uuid.uuid4()
    rows = [
        record_decision(
            bill_run=bill_run,
            account_id=account_id,
            case=case,
            choice=choice,
            reason=reason,
            amount=amount,
            unit=unit,
            decided_by=decided_by,
            bulk_action_id=bulk_action_id,
        )
        for account_id in account_ids
    ]
    return bulk_action_id, rows


def current_decision(
    bill_run: Any, account_id: str, case: str, *, service_id: Any = None
) -> models.BillRunDecision | None:
    """The decision that stands — the row nothing has superseded."""
    return (
        models.BillRunDecision.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            bill_run=bill_run,
            account_id=account_id,
            case=case,
            service_id=service_id,
            superseded_by__isnull=True,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def current_decisions(bill_run: Any) -> list[models.BillRunDecision]:
    """Every live decision in this run — what the screen renders and what
    `apply_decisions` consumes. Superseded rows are excluded, never deleted."""
    return list(
        models.BillRunDecision.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            bill_run=bill_run,
            superseded_by__isnull=True,
        ).order_by("account_id", "case", "created_at")
    )


def _estimated_reading(existing: ServiceReading, row: models.BillRunDecision) -> ServiceReading:
    """The clerk's estimate, in the reading's own shape.

    `estimated=True` travels with it and is NOT decoration: BR-MET-029 makes an
    estimate a lawful bill input that must be visibly an estimate, and a
    customer disputing one has to be able to see that it was one.
    """
    return replace(
        existing,
        consumption=rating_seam.Quantity(amount=row.amount, unit=row.unit),
        estimated=True,
        absent_reason=None,
    )


def _late_fee_charge_id(code: str) -> str:
    """BR-BIL-075 — WHERE an applied late fee books, or REFUSE by name.

    Returns `rating.charges.id` as a string and **nothing else**, deliberately:
    the row also carries `amount`, and a late fee's amount is BR-BIL-001's ❄️
    FROZEN B4 figure (GT-10's **8.13**), never the code's. A function that
    cannot see the amount cannot spend it, which is a stronger guarantee than a
    comment asking the next author not to (hard-won law 1).

    **NEVER A FALLBACK.** Three states answer "no code" — the tenant has none by
    that name, they retired it (IS-1 — a retired charge is not chargeable), or
    rating has not published the read — and every one is a refusal. Substituting
    a hardcoded `4200` would put one tenant's late-fee revenue in an account
    they never chose, on a stamp that freezes with the bill (BR-BIL-010), which
    is exactly the shape the PO rejected when they rejected the twelfth
    designation.

    It refuses the CALCULATE step rather than one account, and that is right
    rather than a BR-BIL-055 breach: the missing code is a fact about the
    TENANT, so every late fee in the run is unbookable and issuing the rest
    while silently dropping a thousand fees would be worse than stopping.
    `api.run_calculate` catches it and renders it as a named 422 carrying
    `br_ref` (`BR-BIL-051`), so a clerk reads the sentence rather than a stack.
    """
    read_charge = gather._resolve("rating", "charge_by_code")
    if read_charge is None:
        raise BillingRuleError(
            "apps.rating.selectors.charge_by_code is not published, so an applied late "
            "fee cannot name the charge code it books to (BR-BIL-075). The GL account "
            "is the tenant's own (BR-BIL-007 / BR-BIL-010) and is never a constant here.",
            br_ref="BR-BIL-075",
        )
    charge = read_charge(code)
    if charge is None:
        raise BillingRuleError(
            f"charge code {code!r} is not a live charge code of this tenant, so an "
            "applied late fee has no GL account to book to and the bills carrying one "
            "cannot be issued (BR-BIL-075 / BR-BIL-010). A late fee books to the "
            "tenant's OWN code, the same way NSF and reconnection fees already do "
            "(BR-BIL-007) — nothing here falls back to a platform account, because a "
            "guessed bucket freezes onto an immutable invoice. A human creates or "
            f"reactivates {code!r} on S13 (Taxes & fees → charge codes) and points it "
            "at an account; the seeded chart's `4200 Late-fee revenue` is where a "
            "utility that thinks about nothing lands, and it is no longer the only "
            "place the fee can go. THE FEE IS NOT SILENTLY SKIPPED: a late fee the "
            "clerk applied and the bill did not carry is money the utility decided to "
            "charge and never charged.",
            br_ref="BR-BIL-075",
        )
    # `id` ONLY — see the module constants above. The amount is B4's.
    return str(charge["id"])


def _late_fee_charge_id_for_plan(rate_plan_id: Any) -> str | None:
    """BR-RAT-1011 / `CR-078` — the charge code THIS PLAN names, or None = ZERO.

    None is the ruled answer, not a gap: *"if plan doent provide you that
    charge code then you have to put zero on late payment"*. `rating_seam
    .plan_late_fee_terms` returns None for all four of its states — no code, a
    retired code (IS-1), another tenant's (HR-1), an unknown plan — and every
    one of them is *this plan charges no late fee*.

    ⚠ **IT RAISES ONLY WHEN THE SEAM ITSELF IS ABSENT**, and that distinction
    is the whole safety of this function. A deployment where rating publishes
    no reader must STOP, not quietly charge nothing: the second is the exact
    silent-zero failure `CR-078`'s ordering was written to prevent, and it
    would reach every customer of every tenant with nothing going red.
    """
    terms = rating_seam.plan_late_fee_terms(rate_plan_id)
    if terms is None:
        # ⚠ NOT THE RULED ZERO — there is no plan to ask (see
        # `late_fee.LateFeePlanUnreadable`). It REFUSES the calculate step, the
        # same way `_late_fee_charge_id` refuses a tenant with no code, because
        # an account whose plan cannot be read could not have been priced and a
        # "no late fee" answer here would make a broken account free forever.
        raise BillingRuleError(
            f"rate plan {rate_plan_id!r} could not be read, so the late-fee charge code "
            "it names cannot be resolved (BR-RAT-1011 / CR-078). This is not the ruled "
            "zero: that is a plan which EXISTS and names no code. A late fee the clerk "
            "applied and the bill did not carry is money the utility decided to charge "
            "and never charged.",
            br_ref="BR-RAT-1011",
        )
    charge_id = terms.get("charge_id")
    return None if charge_id is None else str(charge_id)


#: The reason an account left out of a calculate pass carries while one of
#: its Check decisions is unanswered.
DECISION_NEEDED = "decision_needed"


def standing_answers(bill_run: Any) -> dict[str, str]:
    """The run's live *Answer for all N*, `{case: choice}`."""
    from apps.billing import check_models

    return {
        row.case: row.choice
        for row in check_models.BillRunStandingAnswer.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), bill_run=bill_run, superseded=False
        )
    }


def set_standing_answer(*, bill_run: Any, case: str, choice: str, decided_by: Any = None) -> Any:
    """B13 — *Answer for all N* on one tag. Validated against the case's own
    vocabulary; a change of mind supersedes the live row (the trail keeps both)."""
    from apps.billing import check_models

    offered = CHOICES_BY_CASE.get(case)
    if offered is None or choice not in offered:
        raise BillingRuleError(
            f"{choice!r} is not one of the answers {case!r} offers "
            f"({', '.join(offered or ())}).",
            br_ref="BR-BIL-1040",
        )
    if (case, choice) in REASON_REQUIRED:
        # A standing answer carries no reason, and a waiver's reason is the
        # whole of its evidence (PO 2026-09-30, case 2): answered per account.
        raise BillingRuleError(
            f"{case}/{choice} needs a reason, so it is answered per account, "
            "never for a whole tag.",
            message_key="billing.check.reasonRequired",
        )
    if (case, choice) in BULK_FORBIDDEN:
        # 🔒 DEF-BIL-10200 — an Answer for all IS a bulk act: one click over
        # every account on the tag. BR-BIL-003 keeps the late-fee waiver per
        # account, so it is refused here exactly as `record_bulk` refuses it.
        raise BillingRuleError(
            f"{case}/{choice} may not be taken for a whole tag (BR-BIL-003): a "
            "waiver is answered account by account.",
            message_key="billing.check.waiveOneAtATime",
            br_ref="BR-BIL-003",
        )
    _refuse_if_sent(bill_run)
    tenant_id = core_tenancy.current_tenant_id()
    check_models.BillRunStandingAnswer.objects.filter(
        tenant_id=tenant_id, bill_run=bill_run, case=case, superseded=False
    ).update(superseded=True)
    row = check_models.BillRunStandingAnswer.objects.create(
        tenant_id=tenant_id,
        bill_run=bill_run,
        case=case,
        choice=choice,
        decided_by_id=audit.actor_user_id(decided_by),
    )
    audit.money_action(
        decided_by,
        "bill_run.standing_answer",
        "bill_run",
        str(bill_run.pk),
        before=None,
        after={"case": case, "choice": choice},
    )
    return row


#: The anchor answers a pass feeds back into `runs._anchor_quantity`.
ANCHOR_ANSWER_CASES = (
    "possible_rollover",
    "anchor_multiplier_unstated",
    "meter_swapped",
    # Changes row 44 — read by the ruled path's adapter, not the anchor; it
    # rides the same feed into the pass (`selectors.prepared_for`).
    "meter_has_no_multiplier",
)


def anchor_answers_for(bill_run: Any) -> dict[tuple[str, str, str], str]:
    """`{(account_id, service_code, case): choice}` for the answers a pass may
    use (`runs.open_answers`). Per-account rows first; the tag's standing
    answer covers the rest through the `""` service key."""
    from apps.billing import gather

    codes = gather._resolve("tenancy", "service_ids_by_code")
    code_by_id = {str(v): k for k, v in ((codes() if codes else {}) or {}).items()}
    out: dict[tuple[str, str, str], str] = {}
    for row in current_decisions(bill_run):
        if row.case in ANCHOR_ANSWER_CASES:
            code = code_by_id.get(str(row.service_id), "") if row.service_id else ""
            out[(str(row.account_id), code, row.case)] = row.choice
    return out


def standing_anchor_answers(bill_run: Any) -> dict[str, str]:
    return {k: v for k, v in standing_answers(bill_run).items() if k in ANCHOR_ANSWER_CASES}


def apply_decisions(
    prepared: Any,
    *,
    bill_run: Any,
    late_fee_charge_code: str = DEFAULT_LATE_FEE_CHARGE_CODE,
) -> Any:
    """Fold the run's live decisions into its prepared data. Returns a NEW run.

    What comes back is what phase 2 will bill, so a clerk can be shown it
    before anything is calculated. Held accounts leave `ready` and gain a
    `bill_run_exclusions` row — the same pending queue a phase-3
    mark-for-later writes, because the PO confirmed one queue with two doors.

    **BR-BIL-075 (DEF-719):** an applied late fee now names the tenant's own
    late-fee charge code, so the bill carrying it can be ISSUED at all. The code
    is resolved ONCE per run and only when some account actually has an applied
    late fee — a run with no late fees must not fail for a code it never needs,
    and a run with a thousand of them must not ask rating a thousand times.
    """
    from apps.billing import runs

    by_account: dict[str, list[models.BillRunDecision]] = {}
    for row in current_decisions(bill_run):
        by_account.setdefault(str(row.account_id), []).append(row)
    # ── BR-BIL-1040 AMENDED 2026-09-30 · ANSWER FOR ALL, THEN PER ACCOUNT ──
    # A tag's standing answer stands in for every account that has no answer
    # of its own for that case; a per-account row always wins. Synthesised
    # rows are NOT saved: the trail keeps the one standing-answer row with a
    # name on it, and a per-account row is written only when a clerk wrote one.
    standing = standing_answers(bill_run)
    raised: dict[str, set[str]] = {}
    for problem in getattr(prepared, "decisions", ()) or ():
        if problem.account_id:
            raised.setdefault(str(problem.account_id), set()).add(problem.reason)
    # 🔒 DEF-BIL-8651 — *Apply to this bill* on money that has not arrived
    # applies nothing, so it is not an answer: the account waits on it.
    not_arrived = (
        accounts_paid_but_not_arrived(bill_run)
        if any("paid_after_cutoff" in cases for cases in raised.values())
        else set()
    )
    for account_id in not_arrived:
        if account_id in by_account:
            by_account[account_id] = [
                row
                for row in by_account[account_id]
                if not (row.case == "paid_after_cutoff" and row.choice == CHOICE_APPLY_THIS_BILL)
            ]
    for account_id, cases in raised.items():
        # 🔒 DEF-BIL-9009 — a per-METER missing-read answer covers that meter
        # only, so it does not stop the tag's answer covering the account's
        # OTHER unread meters. Only an account-wide row (no service) does.
        answered = {
            row.case
            for row in by_account.get(account_id, [])
            if not (row.case == "missing_read" and row.service_id is not None)
        }
        for case in cases - answered:
            choice = standing.get(case)
            if (
                case == "paid_after_cutoff"
                and choice == CHOICE_APPLY_THIS_BILL
                and account_id in not_arrived
            ):
                continue
            if choice and choice != CHOICE_ESTIMATE:  # an estimate needs a quantity
                synthesised = models.BillRunDecision(case=case, choice=choice, account_id=account_id)
                # DEF-BIL-9009 — marks a TAG-WIDE answer: it speaks for every
                # unread meter of the account that no per-meter row answers
                # (`_apply_to_account`), never for "the sole one" only.
                synthesised.from_standing_answer = True
                by_account.setdefault(account_id, []).append(synthesised)

    kept: list[AccountBillingData] = []
    held: list[runs.AccountProblem] = []
    # `CR-078` — memoised BY PLAN, not resolved once per RUN. The code is a
    # property of the plan now, and a run bills many plans; but a 40,000-account
    # tenant (T5, the top of the ICP) runs a handful of plans, so this asks
    # rating once per plan rather than once per account. `None` is a legitimate
    # memoised answer — *this plan charges no late fee* — so membership is
    # tested with `in`, never with a truthiness check that would re-ask forever.
    charge_id_by_plan: dict[Any, str | None] = {}

    # 🔒 DEF-BIL-8473 · PO 2026-09-30 fixed-charge case 4. An OVERLAP that still
    # reaches a clerk is one the run could not shorten — the last issued bill
    # covers the WHOLE period (`check_engine._account_period_start`) — so there
    # is nothing left to bill and it offers Hold only
    # (`CONTINUITY_CHOICES_BY_STATE["overlap"]`). Until 2026-09-30 an unanswered
    # one was PRICED (`billing_continuity` is not a Check case, so it was never
    # must-answer) and drafted the same days' base twice — $8.00 on the J72
    # walk. It is now must-answer for an overlap, and a *Bill as it stands* —
    # a tag's standing answer or a row written before the ruling — never
    # counts as its answer. A GAP is must-answer too since DEF-BIL-8650
    # (`MUST_ANSWER_CASES`): *Bill as it stands* or *Look into it*, never billed
    # on no answer. Asked of the anchor only for the accounts that raised the
    # case, so a run with none pays nothing.
    overlaps = {
        account_id
        for account_id, cases in raised.items()
        if "billing_continuity" in cases
        and getattr(bill_run, "period_start", None) is not None
        and runs.period_anchor(account_id, period_start=bill_run.period_start).state
        == runs.CONTINUITY_OVERLAP
    }

    undecided: list[runs.AccountProblem] = []
    waived: list[runs.AccountProblem] = []
    for data in prepared.ready:
        rows = by_account.get(data.account_id, [])
        if data.account_id in overlaps:
            lawful = CONTINUITY_CHOICES_BY_STATE[runs.CONTINUITY_OVERLAP]
            rows = [
                row
                for row in rows
                if row.case != "billing_continuity" or row.choice in lawful
            ]
        must_answer = MUST_ANSWER_CASES | (
            {"billing_continuity"} if data.account_id in overlaps else set()
        )
        waiting = sorted(
            raised.get(data.account_id, set()) & must_answer
            - {row.case for row in rows}
        )
        if waiting and not _is_held(rows):
            # *"Nothing is applied to a bill without a clerk's click"* — the
            # account is left out of this pass and says why; nothing written.
            undecided.append(
                runs.AccountProblem(
                    reason=DECISION_NEEDED,
                    detail=f"account {data.account_no}: waiting on {', '.join(waiting)}.",
                    account_id=data.account_id,
                    account_no=data.account_no,
                )
            )
            continue
        waiver = next(
            (row for row in rows if row.case == "base_only_billing" and row.choice == CHOICE_WAIVE),
            None,
        )
        if waiver is not None and not _is_held(rows):
            waived.append(_waive(data, waiver, bill_run=bill_run))
            continue
        if _is_held(rows):
            runs.mark_for_later(
                bill_run=bill_run,
                account_id=data.account_id,
                reason_code=_hold_reason(rows),
                detail=_hold_detail(rows),
            )
            held.append(
                runs.AccountProblem(
                    reason=_hold_reason(rows),
                    detail=_hold_detail(rows),
                    account_id=data.account_id,
                    account_no=data.account_no,
                )
            )
            continue
        rows = _with_run_late_fee(rows, prepared, data.account_id)
        late_fee_charge_id: str | None = None
        if any(row.case == "late_fee" and row.choice == CHOICE_APPLY for row in rows):
            if data.rate_plan_id not in charge_id_by_plan:
                charge_id_by_plan[data.rate_plan_id] = _late_fee_charge_id_for_plan(
                    data.rate_plan_id
                )
            late_fee_charge_id = charge_id_by_plan[data.rate_plan_id]
        if any(
            row.case == "price_changed_mid_period" and row.choice == CHOICE_ACCEPT_SUGGESTION
            for row in rows
        ):
            # 🔒 PO 2026-09-30 — the whole period at the PERIOD-END version:
            # `data` was gathered at the period end (BR-BIL-1055); the split's
            # segments are what a clerk declined by accepting this.
            data = replace(data, split_segments=())
        kept.append(
            _apply_to_account(
                data,
                rows,
                late_fee_charge_id=late_fee_charge_id,
                plan_names_a_late_fee_code=late_fee_charge_id is not None,
            )
        )

    return replace(
        prepared,
        ready=tuple(kept),
        decisions=tuple(held) + tuple(undecided),
        waived=tuple(waived),
    )


def _with_run_late_fee(
    rows: list[models.BillRunDecision], prepared: Any, account_id: str
) -> list[models.BillRunDecision]:
    """🔒 HUMAN-REVIEW-PENDING · DEF-BIL-10200 — the account's late-fee answer
    with the RUN'S figure on it.

    The figure is the one the Check computed and showed (`check_engine` C7 →
    `late_fee_run.assess_account`), read back off the pass's own `late_fee`
    finding — so the amount a clerk saw on the Check is the amount the bill
    carries, from one computation. A clerk's Waive on the account wins; any
    other answer, or none (`DEFAULT_ANSWERS`), applies it. The row is
    SYNTHESISED and never saved, like a standing answer's: the trail keeps
    the rows a person wrote.

    ⚠ **THE FIGURE IS NEVER A TYPED ONE.** An `apply` row carrying a clerk's
    own `amount` is replaced by the computed figure whenever the run raised
    the finding (BR-BIL-019: hand-typed amounts never reach a bill). Where the
    run raised NO late fee, rows are returned untouched — a direct caller's
    row (the S31.3 path and its tests) still bills what it carries."""
    findings = (getattr(prepared, "findings", None) or {}).get(str(account_id), ())
    found = next((f for f in findings if getattr(f, "code", None) == "late_fee"), None)
    if found is None:
        return rows
    params = getattr(found, "params", None) or {}
    try:
        amount = Decimal(str(params.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        return [row for row in rows if row.case != "late_fee"]
    answer = next((row for row in rows if row.case == "late_fee"), None)
    choice = answer.choice if answer is not None else DEFAULT_ANSWERS["late_fee"]
    kept = [row for row in rows if row.case != "late_fee"]
    if choice == CHOICE_WAIVE:
        return kept + [answer] if answer is not None else kept
    applied = models.BillRunDecision(
        case="late_fee",
        choice=CHOICE_APPLY,
        account_id=account_id,
        amount=amount,
        reason=params.get("name") or "Late fee",
    )
    return kept + [applied]


def _refuse_if_sent(bill_run: Any) -> None:
    """🔒 PO ruling 2026-09-30 (option A): a SENT run's decisions and standing
    answers are LOCKED — they explain the money on bills that went out. The
    database refuses too (`billing/0034`); this gives the clerk the sentence."""
    from apps.billing import check_store

    if getattr(bill_run, "pk", None) is not None:
        check_store.refuse_if_sent(bill_run)


def _waive(data: AccountBillingData, row: Any, *, bill_run: Any) -> Any:
    """🔒 PO ruling 2026-09-30 (fixed-charge case 2) — the standing charges are
    WAIVED for this run: not billed, NOT queued for a catch-up run.

    The amount waived is what this account's bill would have come to, priced
    by the one pricing path (`runs.price_account`) — a figure, never a guess —
    and stamped on the decision row so Sign off can say *"Waived $26"*. The
    row is append-only, so a changed figure SUPERSEDES it (`record_decision`)
    rather than editing it, carrying the reason and the clerk across, and the
    waiver is audited then — once per figure, never once per viewing.
    """
    from apps.billing import runs

    amount = runs.price_account(data).priced.total
    if row.pk is not None and row.amount != amount:
        record_decision(
            bill_run=bill_run,
            account_id=data.account_id,
            case=row.case,
            choice=row.choice,
            reason=row.reason,
            amount=amount,
            service_id=row.service_id,
            decided_by=row.decided_by_id,
        )
        audit.money_action(
            row.decided_by_id,
            "bill_run.base_waived",
            "bill_run",
            str(getattr(bill_run, "pk", bill_run)),
            before=None,
            after={
                "account_id": str(data.account_id),
                "amount": str(amount),
                "currency": data.currency,
                "reason": row.reason,
            },
        )
    return runs.AccountProblem(
        reason="base_charges_waived",
        detail=f"account {data.account_no}: standing charges waived, {amount} {data.currency}.",
        account_id=data.account_id,
        account_no=data.account_no,
    )


def _is_held(rows: list[models.BillRunDecision]) -> bool:
    """Any hold on any case takes the account out of the run.

    Deliberately ANY rather than all: a clerk who held one service's missing
    read has held the account, and billing it for the rest would be the
    "bill without this service" choice they did not make.

    WHICH (case, choice) pairs hold is `HOLDING_CHOICES` — one table, stated
    with its reasons where it is declared, so a new case cannot half-join this
    logic (the CR-038 W8 cases each name why their holding choice holds,
    including the two that hold at a NAMED pricing boundary).
    """
    return any((row.case, row.choice) in HOLDING_CHOICES for row in rows)


def _hold_reason(rows: list[models.BillRunDecision]) -> str:
    for row in rows:
        if (row.case, row.choice) == (CASE_LEFT_OUT, CHOICE_LEAVE_OUT):
            # BR-BIL-1054 — Pending billing reads *"left out by clerk"*.
            return LEFT_OUT_REASON
        if (row.case, row.choice) in HOLDING_CHOICES:
            return f"staff_{row.choice}_{row.case}"
    return "staff_hold"


def _hold_detail(rows: list[models.BillRunDecision]) -> str:
    for row in rows:
        if (row.case, row.choice) in HOLDING_CHOICES:
            return row.reason or f"{row.case}: {row.choice}"
    return ""


def _apply_to_account(
    data: AccountBillingData,
    rows: list[models.BillRunDecision],
    *,
    late_fee_charge_id: str | None = None,
    plan_names_a_late_fee_code: bool | None = None,
) -> AccountBillingData:
    """One account's decisions, folded into its gathered data.

    `late_fee_charge_id` is resolved per PLAN by `apply_decisions` and handed
    down (BR-BIL-075 as amended by BR-RAT-1011 / `CR-078`).

    ⚠ **`None` NOW HAS TWO MEANINGS AND THEY NEED DIFFERENT ANSWERS**, which is
    why `plan_names_a_late_fee_code` exists beside it rather than being inferred:

      * **`plan_names_a_late_fee_code is False`** — `apply_decisions` asked, and
        the plan names no live late-fee charge code. The ruled answer is ZERO
        (*"if plan doent provide you that charge code then you have to put zero
        on late payment"*), so no fee line is added and nothing is refused.
      * **`plan_names_a_late_fee_code is None`** — nobody asked, i.e. a caller
        reached this function directly. It falls through to the refusal below,
        because that path is exactly how a fee line went out anonymous in
        DEF-719 and DEF-201.

    A boolean rather than a sentinel string on purpose: the alternative is
    inferring "asked and got nothing" from `late_fee_charge_id is None`, which
    cannot distinguish the two and would turn a direct caller's bug into free
    late fees for that account.
    """
    readings = list(data.readings)
    tariffs = list(data.tariffs)
    fees = list(data.fees)
    deferred: set[str] = set()

    # 🔒 DEF-MET-10163 (PO 2026-10-15, *"go with 1 and 3"*) — a service a LATER
    # actual reading already covers is never estimated: its usage waits for the
    # next bill, which that reading measures from the last reading billed, and
    # its base bills now (the *"bill base, usage later"* path below). An
    # `estimate` answer on such a service — recorded before the reading arrived,
    # or a standing answer — is not applied. `runs.covered_by_later_read` holds
    # the rule and the worked figure.
    from apps.billing import runs as _runs

    covered = _runs.covered_by_later_read(readings)
    deferred |= covered

    # 🔒 DEF-BIL-9009 — the tag's *Answer for all* (a synthesised row, no
    # service) covers every unread meter the clerk did not answer one by one.
    # It used to resolve through `_service_code_for`'s "sole unread service"
    # fallback, which answers None on an account with two unread meters — so
    # nothing was deferred and Calculate broke the account for "no decision"
    # (40,005 of 40,009 accounts on the 2026-10-01 close-out walk). Per-meter
    # rows are applied first and win for their own meter.
    per_meter_codes = {
        _service_code_for(row, readings)
        for row in rows
        if row.case == "missing_read" and not getattr(row, "from_standing_answer", False)
    }
    standing_rows = [
        row
        for row in rows
        if row.case == "missing_read" and getattr(row, "from_standing_answer", False)
    ]
    rows = [row for row in rows if row not in standing_rows]
    for row in standing_rows:
        if row.choice == CHOICE_BILL_WITHOUT_SERVICE:
            deferred.update(
                r.service_code
                for r in readings
                if r.consumption is None and r.service_code not in per_meter_codes
            )

    for row in rows:
        if row.case == "missing_read":
            code = _service_code_for(row, readings)
            if code in covered:
                continue  # DEF-MET-10163 — see `covered` above
            if row.choice == CHOICE_ESTIMATE:
                readings = [
                    _estimated_reading(r, row) if r.service_code == code else r for r in readings
                ]
            elif row.choice == CHOICE_BILL_WITHOUT_SERVICE:
                # 🔒 PO ruling 2026-09-30 (fixed-charge case 1, option A):
                # *"The customer sees a steady base every month and nothing is
                # lost. The bill says 'Water usage: no reading, billed next
                # bill'"*. The service's BASE bills; its USAGE waits. No usage
                # line is drawn (never a $0.00 one — that would claim the
                # meter read nothing), and no reading is named on the bill, so
                # the next bill measures from the last reading actually billed.
                # Until 2026-09-30 this dropped the service's base too, and
                # that month's base was never billed by anything.
                if code:
                    deferred.add(code)
        elif row.case == "late_fee" and row.choice == CHOICE_APPLY:
            if late_fee_charge_id is None and plan_names_a_late_fee_code is False:
                # BR-RAT-1011 (`CR-078`) — the plan names no late-fee charge
                # code, so the fee is $0.00 and there is no line to draw. A
                # $0.00 fee line would tell the customer a late fee was
                # calculated and came to nothing, which is a different claim.
                # NOT SILENT: `plans_missing_late_fee_charge`, `manage.py
                # cr078_late_fee_codes` and gate G121 each count this state,
                # and `PlanWizard` shows the empty field on the plan itself.
                continue
            if row.amount is None or row.amount <= 0:
                # 🔒 DEF-BIL-10200 — an Apply with no figure (an Answer for all
                # reaching an account the run computed no fee for) is not a
                # $0.00 fee line: that would tell the customer a late fee was
                # calculated and came to nothing.
                continue
            if late_fee_charge_id is None:
                # Nobody asked — a direct caller. See the docstring: refuse
                # rather than assume, because this is DEF-719's path.
                late_fee_charge_id = _late_fee_charge_id(DEFAULT_LATE_FEE_CHARGE_CODE)
            fees.append(
                rating_seam.RatedLine(
                    kind="fee",
                    description=row.reason or "Late fee",
                    # ⚠ **B4's FIGURE, NOT THE CODE'S (BR-BIL-075).** The
                    # decision row carries what BR-BIL-001's signed rule
                    # computed — `max($5.00, 1.5% × overdue portion)`, **8.13**
                    # on the GT-10 reference bill — and the charge code below
                    # supplies only the GL account. Reading `amount` off the
                    # code would move a ❄️ FROZEN figure, which is a finance
                    # re-sign under HUMAN-GUIDE §6 and not a code change.
                    amount=row.amount if row.amount is not None else Decimal("0"),
                    taxable=False,  # B4.2 — a fee is never in the tax base
                    # WHICH CODE IT BOOKS TO (BR-BIL-075, 2026-08-26, closing
                    # DEF-719). Until this field was set, `issue._gl_account_for`
                    # could resolve nothing for the line and **a bill carrying an
                    # applied late fee could not be issued at all** — the clerk
                    # applied the fee on S31.3, the draft assembled, and the whole
                    # bill died at release with `fee_line_names_no_charge_code`.
                    charge_id=late_fee_charge_id,
                )
            )
        # late_fee/waive and base_only_billing|no_usage/include are decisions
        # to change NOTHING. They are recorded because "someone looked and
        # decided to leave it" is a different fact from "nobody looked", and
        # only the recorded row can tell them apart. The CR-038 W8 record-only
        # choices are the same shape: `keep`, `bill_as_is`, `confirm_factor`
        # and `apply_next_bill` each bill exactly what was gathered — for the
        # true-up that IS the money application, because the committed read's
        # stored consumption already carries BR-MET-029's register arithmetic
        # and prices at current-period rates through the ordinary pipeline
        # (WE-13 ❄: 53 ccf billed Aug at Aug rates; one money path,
        # BR-SHL-023). The holding choices never reach this function —
        # `apply_decisions` routed those accounts to the pending queue above.

    # 🔒 DEF-BIL-9009 (second half) — a service priced as a SHARE of a deferred
    # service waits with it. Sewer bills 40% of water's volume (BR-RAT-1015);
    # with water's usage moved to the next bill the engine refused sewer
    # (`BasisUnavailable`) and the WHOLE account broke — 40,004 of 40,009 on
    # the 2026-10-02 re-walk. Its base bills now; its usage comes with water's.
    # Repeated until nothing new joins, so a chain of shares cannot be half-done.
    while deferred:
        joining = {
            t.service
            for t in tariffs
            if getattr(t, "basis_service", None) in deferred and t.service not in deferred
        }
        if not joining:
            break
        deferred |= joining
    if deferred:
        readings = [r for r in readings if r.service_code not in deferred]
        tariffs = [_usage_waits(t) if t.service in deferred else t for t in tariffs]
        data = replace(
            data,
            usage_next_bill=tuple(sorted(set(data.usage_next_bill or ()) | deferred)),
        )

    # The readings go through `gather.with_readings` rather than a local
    # `replace`, and that is not ceremony: it is the function written for this
    # exact move, carrying the reasoning about why a re-gather would be wrong,
    # and until now it had NO CALLER. Routing through it means one place
    # decides what "the same account with different readings" means. The
    # tariff and fee changes are this module's own and follow separately.
    data = gather.with_readings(data, tuple(readings))
    return replace(data, tariffs=tuple(tariffs), fees=tuple(fees))


def _usage_waits(tariff: Any) -> Any:
    """🔒 DEF-BIL-9009 — this tariff bills its BASE and no usage on this bill.

    For an ordinary service `base_only=True` says exactly that. A SHARE of
    another service (`percent_of_service`, sewer at 40% of water) is
    different: the engine keeps pricing a base-only share from its basis
    service (that is how a sewer with no meter of its own bills at all,
    DEF-161), and with the basis's usage waiting there is nothing to take a
    share OF, so it refused the whole bill. So the share is handed to the
    engine as what it is on THIS bill — a base with no usage rate — and its
    usage is priced next bill with water's (`usage_next_bill`). The base
    figure itself is untouched: it is the tariff's own `base_charge`.
    """
    if getattr(tariff, "model", None) != "percent_of_service":
        return replace(tariff, base_only=True)
    return replace(
        tariff,
        base_only=True,
        model="flat",
        unit_price=Decimal("0"),
        tiers=(),
        percent=None,
        basis_service=None,
    )


def _service_code_for(row: models.BillRunDecision, readings: list[ServiceReading]) -> str | None:
    """Which service a per-service decision is about.

    The decision row carries a `service_id`; the readings carry both the id and
    the code. Matching on the id and falling back to the sole unmeasured
    service keeps a screen that sends only the code working, without this
    module guessing when there is more than one candidate.
    """
    if row.service_id is not None:
        for reading in readings:
            if reading.service_id == str(row.service_id):
                return reading.service_code
    unmeasured = [r.service_code for r in readings if r.consumption is None]
    return unmeasured[0] if len(unmeasured) == 1 else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-003@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — closing the gap between
#         a recorded decision and a bill)
# checklist: A✔ B✔ C✔ D✔(the API half landed 2026-08-11 — GET /billing/runs/{id}/exceptions and POST .../exceptions/{caseId}/resolve) E✔(S31.3 ships and calls both) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_003_decisions.py
# exceptions: (1) TWO OF THE SIX CASES REFUSE BY NAME. `extra_charge` needs the
#         tenant charge-code reader (with its own GL) and `overcharge` needs the
#         trailing-average guardrail; neither exists, and both are in
#         UNSUPPORTED_CASES rather than half-implemented. Inventing either would
#         put a number on a customer's bill that no rule produced
#         (2) `apply_decisions` RETURNS a run rather than mutating one — so a
#         clerk can be shown what their decisions did BEFORE anything is
#         billed. Deciding is not billing, and this keeps that structural
#         (3) it re-gathers nothing: an estimate swaps the READING on data
#         already gathered (`gather.with_readings`'s own reasoning), so a
#         customer name changed since the run cannot reach a bill priced before
#         it
#         (4) a HOLD on any case holds the whole account — ANY, not all. A
#         clerk who held one service's missing read has held the account, and
#         billing the rest would be the "bill without this service" choice they
#         did not make
#         (5) [run-API lane 2026-08-11] `case_row_id` / `split_case_row_id` /
#         `resolve_cases` / `CHOICES_BY_CASE` published for the S31.3 endpoint.
#         A case row is NOT a stored entity — `prepare_run` computes it on every
#         viewing — so it is identified by the DECISION's natural key (case +
#         account + service), which is what `current_decision` already resolves
#         on. Derived, never minted: the id a screen selected yesterday names
#         the same case today, and a resolve posted twice supersedes rather than
#         landing on two rows. BULK is decided HERE and not by the client, since
#         only the server can mint an id shared across N rows (BR-BIL-060), and
#         a bulk whose rows span two CASES is refused by name rather than
#         applying one choice to two different questions.
#         (6) [run-API lane 2026-08-11] `decided_by` is now assigned by ID
#         (`decided_by_id=getattr(x, "pk", x)`) so an API layer holding only the
#         session user's id need not fetch the `users` row to record a decision.
#         Both forms are accepted; neither accepts a name (BR-AUD-003).
#         (7) [lane LATEFEE 2026-08-26, BR-BIL-075 closing DEF-719] AN APPLIED
#         LATE FEE NOW NAMES A CHARGE CODE, so the bill carrying it can be
#         ISSUED — before this, `issue._gl_account_for` had nothing to resolve
#         and refused the WHOLE bill by name, with nothing a clerk could click.
#         The code is `LATE`, which is STATED (03-field-map.md's Late-fee row
#         names `invoice_lines.charge_id → LATE`; EP-BIL-01 §5 agrees) and
#         seeded on every tenant — not chosen here. ⚠ The code supplies the GL
#         ACCOUNT ONLY: the amount stays BR-BIL-001's ❄️ FROZEN B4 figure
#         (GT-10's 8.13), and `_late_fee_charge_id` returns an id and never the
#         row, so a later author cannot read `amount` off it without deleting
#         that guarantee on purpose. ⚠ TWO HALVES NOT DONE AND NOT IMPLIED: the
#         ruling's *stated on screen rather than silently dropped* has no S31.3
#         sentence (frontend, REPORTED), and `charges.LATE` is seeded with NO GL
#         account on any tenant, so a fresh utility still refuses at issue by
#         name until a clerk maps it — DEF-733, held by
#         `tests/test_def_719_late_fee_charge_code.py::tc11`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
