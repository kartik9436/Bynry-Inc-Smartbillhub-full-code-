# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — late-fee assessment, the Balances tab of
#           S31.2 and the per-case rows of S31.3)
#           Screens: — (the fee line renders on the invoice / S31.2)
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's TCs". The story
#           that owns the late-fee CANDIDATE list is the whole six-tab S31.2
#           preview — which this file does not ship; it ships one pure
#           calculation that story depends on. The story is named in the
#           docstring, where G10 does not read it as a completion claim: the
#           same reasoning and the same precedent as apps/billing/rating_seam.py.
#           (G10 proved this rule bites: an earlier revision of this header
#           named the ID inside the very sentence saying it did not, and the
#           gate failed on it — hard-won law 7, from the other direction.)
# Rules:    BR-BIL-001 (late fee = max($5, 1.5% × OVERDUE PORTION); grace
#           counted from the DUE date — B4.1 CONFIRMED; **AMENDED 2026-08-11
#           by the PO: no fee at all while the overdue balance is under
#           $25.00**) · BR-BIL-008 (grace: tenant-defined, DEFAULT 5 calendar
#           days after the due date, range 0–30) · BR-BIL-002 (grace mode =
#           calendar OR business days, tenant setting; both modes evaluated) ·
#           BR-BIL-003 (first-time waiver is a MANUAL staff decision — there is
#           no automatic waiver here) · BR-BIL-071 (lateness is decided by the
#           ACTUAL date the money arrived, never the posting or import date, on
#           the records that exist when the bill is generated — PO 2026-08-11,
#           OQ-131 CLOSED) · BR-MET-133 clause 4 (the DISPUTED amount is
#           excluded from ageing and from late-fee assessment while the dispute
#           is open, and the undisputed remainder ages normally — PO
#           2026-08-26, OQ-245 CLOSED; the amount itself is unrecorded, which
#           is OQ-420 and is REFUSED here, never defaulted) · BR-RAT-045 (the amount comes from the
#           percent-with-minimum plugin) · BR-RAT-003 (finalized half-up 2dp,
#           once) · BR-TEN-043 (event-time law: `as_of` is passed in, never
#           read from a clock)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08: max(5, 0.015 × 542.10) = 8.13.
#           UNAFFECTED by the 2026-08-11 $25.00 balance floor and that was
#           VERIFIED, not assumed: 542.10 is twenty-one times the threshold.
# Tests:    06-backend/tests/golden/test_gt08_late_fee.py (the frozen figure) ·
#           06-backend/tests/test_gt08_late_fee_grace.py (the grace clock) ·
#           06-backend/tests/test_po_20260811_late_fee_rulings.py (the $25.00
#           balance floor and the actual-arrival-date lateness test) ·
#           06-backend/tests/test_br_met_133_dispute_ageing.py (clause 4's
#           partial exclusion, its interaction with the $25.00 floor, and the
#           OQ-420 refusal)
# Impacts:  apps/billing/services.py (publishes assess_late_fee) ·
#           apps/billing/rating_seam.py (charge_amount → rating's amount rule)
# ───────────────────────────────────────────────────────
"""The late-fee assessment: billing owns WHEN, rating owns WHAT IT COMES TO.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

The story this serves is US-BIL-002 (step 2 "Check what we found" — the Balances
tab lists late-fee candidates). This module is one calculation inside it, not
the story.

B4.1 (CONFIRMED, finance 2026-08-07) fixes three things and this module is those
three things:

1. **The base is the OVERDUE PORTION**, not the full balance. That is an input
   here, computed by the caller from the aged balance — the engine cannot see a
   balance and must not guess which part of one is past due.
2. **The grace clock starts at the DUE DATE** (not the issue date), runs for a
   tenant-defined number of days (BR-BIL-008: default 5, range 0–30) and is
   counted in calendar OR business days (BR-BIL-002, both modes required).
3. **The amount is `max(minimum, percent × overdue)`** — which is exactly the
   `percent_min` charge amount rule (BR-RAT-041/045). This module does not
   re-implement it; it calls rating through the seam, so GT-8's arithmetic
   exists once in the codebase rather than in two places that can drift.

Nothing here reads a clock. `as_of` is an argument (BR-TEN-043, the event-time
law; G6 greps money paths for the violation). Nothing here waives: BR-BIL-003
makes the first-time waiver a manual staff decision, never an automatic rule.

    ✅ RULED 2026-08-11 (PO) — the BUSINESS-DAY grace boundary. CLOSED.
    ----------------------------------------------------------------
    "Beyond grace" needed an exact boundary, and the two worked examples in
    EP-BIL-01 §7 (WE-15) did not agree on where it sat:
      * (d) CALENDAR: "due Jul 20 + 5 cal → applies from Jul 26". Due + 5
        calendar days is Jul 25, so the fee applies STRICTLY AFTER the grace
        days have elapsed.
      * (e) BUSINESS: "due Fri Jul 17 → from Jul 24". Jul 24 is the 5th business
        day after Jul 17 — i.e. the fee applies ON the day grace expires, one
        business day earlier than (d)'s convention would put it.
    B4 and B5 froze neither boundary: GT-8 states the condition in words ("past
    Due date beyond grace"), gives no dates, and its fixture is calendar mode.
    This module applied ONE convention to BOTH modes — strictly after — and
    reported the one-business-day difference as a finding rather than settling
    it.

    **The PO ruled that convention correct, for both modes.** Worked case put to
    them: due Thu 10 Sep 2026 with 5 days grace → calendar charges Wed 16 Sep;
    business-day counts Fri 11 · Mon 14 · Tue 15 · Wed 16 · Thu 17 and charges
    **Fri 18 Sep**, not Thu 17. A customer paying on the 17th owes nothing where
    the other reading owed $8.13. Stated reason: five days of grace must mean
    the customer gets five days, and the customer-favourable reading is the
    defensible one for a regulated utility. Under this ruling WE-15(e) reads
    "from Jul 27"; that example's text is the one that was wrong.

    ✅ RULED AND BUILT 2026-08-11 (PO) — public holidays. The business-day
    ----------------------------------------------------------------
    clock now skips the tenant's public holidays as well as weekends. Before
    this, business days were Monday–Friday and Christmas Day counted as one: a
    bill due Thu 24 Dec 2026 with 5 business days' grace had its fee assessed
    on **Fri 1 Jan**, New Year's Day. Holiday-aware it is assessed **Tue 5
    Jan** — four days later, and not on a public holiday. Both halves are
    asserted in `test_business_day_grace_skips_public_holidays`, so the test
    states the rejected behaviour as well as the ruled one.

    `holidays` is an ARGUMENT and business mode REFUSES `None`. Defaulting it
    to "no holidays" would silently reinstate exactly the behaviour that was
    ruled against, for every caller that simply had not been updated — so a
    tenant that genuinely keeps no calendar passes an empty set and says so
    (hard-won law 3: the unsafe option must be the one you type). Calendar mode
    accepts `None`, because calendar days are calendar days and a caller should
    not have to branch on the mode.

    The tenant holiday calendar already existed (`holiday_calendars`, tenancy —
    the S63 Reference-data card, BR-TEN-039) so NO new storage and no migration
    was needed; it was simply unreachable from billing. Billing's third consumer
    of it reads the rows through `apps/billing/tenancy_seam.py`, which resolves
    tenancy's published read at call time (B1/BR-TEN-013 — billing never touches
    tenancy's ORM) and converts the S63 payload's ISO date STRINGS into
    `datetime.date`. That conversion is not cosmetic: `date(2026, 12, 25) in
    {"2026-12-25"}` is False, so a caller handing the raw payload to this module
    would skip no holidays at all, silently, with every test here still green.

    NOTHING WAS SEEDED into that calendar. No signed document names a default
    holiday set, so none was invented — a tenant starts with an empty calendar
    and correct behaviour rather than with guessed dates.

    ✅ RULED AND BUILT 2026-08-11 (PO) — NO LATE FEE UNDER $25.00 (OQ-137,
    ----------------------------------------------------------------
    the FEE half). PO verbatim: *"have a threshold to charge late payments - if
    less than $25 then dont charge late payments"*.

    **BR-BIL-001 is AMENDED, not replaced.** `max($5, 1.5% × overdue portion)`
    still computes the fee and not one digit of it moves; what this adds is a
    PRECONDITION — no fee is assessed at all while the overdue balance is under
    $25.00. **The threshold is a floor on the BALANCE, not on the fee**, and
    those are different rules: a floor on the fee would still charge something,
    and the whole point is that nothing is charged.

    Worked, and it is the case the PO was shown: a customer pays a $328.60 bill
    but keys it short and leaves **$2.40**. Under BR-BIL-001's `max($5, …)`
    floor that $2.40 earns a **$5.00** late fee — more than twice the debt —
    and then an $8 certified letter. Under this ruling the $2.40 earns
    **nothing**.

    **GT-8 IS UNAFFECTED, AND THAT WAS CHECKED RATHER THAN ASSERTED**: its
    overdue portion is $542.10, twenty-one times the threshold, so the frozen
    8.13 is reached by exactly the arithmetic B5 signed. The golden suite is run
    on every change here for precisely this reason (BR-BIL-038).

    **THE COLLECTION LADDER IS NOT TOUCHED.** The same question asked whether
    the certified letter and the disconnection notice share the floor; the PO
    ruled on the FEE only, so the ladder half of OQ-137 stays OPEN and nothing
    in this module reads the threshold for anything but the fee. The spirit
    plainly extends — and applying it unasked would still be choosing.

    ✅ RULED AND BUILT 2026-08-11 (PO) — LATENESS IS DECIDED BY THE ACTUAL
    ----------------------------------------------------------------
    DATE THE MONEY ARRIVED (OQ-131 CLOSED). PO verbatim: *"at the time of
    billing if record is available that bill is generated on 5th of Sep then
    you llook at actual date for late fees not posting date; in your example
    acutla date will be 20 AUg and well within due date"*.

    Worked, and it REVERSES what the code would have produced: money reaches
    the bank **20 Aug**, the bill is due **22 Aug**, the payment file is
    imported **25 Aug**, and the bill run happens **5 Sep**. The actual date is
    20 Aug, inside the due date, so the customer is **NOT late and no fee is
    charged**. An import-date reading makes them three days late and bills the
    fee — for money that was in the bank two days early.

    TWO RULES CAME OUT OF ONE SENTENCE and `overdue_portion` implements both:

      1. **WHICH DATE.** A payment counts against the overdue portion when the
         money ACTUALLY ARRIVED on or before the due date. `PaymentReceipt`
         therefore carries two dates and the lateness test reads exactly one of
         them. `recorded_on` — the posting/import moment — is carried BECAUSE
         it is the rejected reading: a field that is present and never consulted
         is a rule a test can prove, where a field that was left out is a rule
         nobody can see.
      2. **WHICH RECORDS.** *"at the time of billing if record is available"* —
         the assessment uses the payment records that exist AT THE MOMENT the
         bill is generated. A payment recorded after that moment is not
         retro-applied by this rule, so a run replayed years later reaches the
         same figure it reached on the day (BR-TEN-043 again, from the data
         side rather than the clock side).

    THIS RESOLVED A CONTRADICTION BETWEEN TWO CONFIRMED RULES — BR-PAY-033
    (an import takes the date from the FILE) versus US-PAY-003 TC-3 (the date
    is the COMMIT moment). The ACTUAL date wins, so BR-PAY-033's reading is the
    one that survives and US-PAY-003 TC-3 is stamped SUPERSEDED in
    `04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md`.

    BILLING NEVER QUERIES PAYMENTS FOR THIS. `payments` is another module's
    table (B1) and this function is pure by rule, so the receipts are an
    ARGUMENT — the same posture `holidays` takes and for the same reason: a
    function that fetched them could not be tested against a payment it did not
    also have to seed, and would behave differently in a preview and in the run
    it previews. The caller maps `payments.cleared_at` — the module's own
    definition, *"when the MONEY was actually received"* — onto `arrived_on`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from apps.billing import rating_seam
from core import money

#: BR-BIL-002 / B4.1 — the two grace modes, both required.
GRACE_CALENDAR = "calendar"
GRACE_BUSINESS = "business"
GRACE_MODES = (GRACE_CALENDAR, GRACE_BUSINESS)

#: BR-BIL-008 — the tenant-configurable window. 5 is the shipped DEFAULT and is
#: never assumed here: `assess_late_fee` takes the value, it does not supply one.
GRACE_DAYS_MIN = 0
GRACE_DAYS_MAX = 30

#: BR-RAT-041/045 — the late fee is the percent-with-minimum amount rule.
LATE_FEE_RULE = "percent_min"

#: BR-BIL-001 AS AMENDED 2026-08-11 (PO ruling, OQ-137 fee half) — **no late fee
#: is assessed while the overdue balance is under this figure**. The PO's own
#: words: *"have a threshold to charge late payments - if less than $25 then
#: dont charge late payments"*. A floor on the BALANCE, never on the fee.
#:
#: It is the DEFAULT of `assess_late_fee(balance_floor=...)` rather than an
#: inlined literal, for the reason every other term here is an argument: a
#: tenant knob is a knob. Whether this one BECOMES a tenant setting the way
#: BR-BIL-021 makes the late % and the grace days tenant settings was NOT put
#: to the PO — raised as **OQ-157**, not answered here. The ruled figure is what
#: ships, and hard-won law 3 decides which way the default points: charging a
#: fee on a $2.40 residue is the unsafe option, so THAT is the one a caller has
#: to type (`balance_floor=Decimal("0")`).
LATE_FEE_BALANCE_FLOOR = Decimal("25.00")

_SATURDAY = 5


@dataclass(frozen=True)
class PaymentReceipt:
    """One payment, as the LATE-FEE test needs to see it — BR-BIL-071.

    PO ruling 2026-08-11 (OQ-131): *"you llook at actual date for late fees not
    posting date"*. So this carries BOTH dates and the test reads exactly one.

    `arrived_on`  the date the money ACTUALLY arrived — the bank/clearing date.
                  `payments.cleared_at` is the module's own definition of it
                  (*"when the MONEY was actually received"*). THE ONLY date the
                  lateness test consults.
    `recorded_on` the date the RECORD entered our system — the counter entry,
                  the import commit, the posting moment. Consulted ONLY to
                  decide which records existed when the bill was generated, and
                  NEVER to decide whether a payment was late.

    Carrying `recorded_on` at all is deliberate. It is the reading the PO
    REJECTED, and a rejected reading that is present-and-unused can be asserted
    by a test; one that was simply left out of the dataclass is a rule nobody
    can see and the next agent re-derives from scratch.

    `arrived_on` is `date | None` because a payment can legitimately be in
    flight (`cleared_at` NULL while a cheque is processing). What the lateness
    test should do with such a record was NOT put to the PO — see
    `overdue_portion`, which refuses with **OQ-156** rather than picking one of
    the three defensible answers.
    """

    amount: Decimal
    arrived_on: date | None
    recorded_on: date


@dataclass(frozen=True)
class DisputeExclusion:
    """What is under dispute on a bill, as BR-MET-133 clause 4 needs to see it.

    THE RULE, QUOTED RATHER THAN SUMMARISED (BR-MET-133, CONFIRMED, PO
    2026-08-26, closing OQ-245). PO verbatim: *"Bill stands, resolution through
    the billed-correction door, and the disputed amount doesn't age into late
    fees while open"*, and clause 4 in full: *"while the dispute is open, the
    **disputed amount is excluded from ageing and from late-fee assessment** —
    a customer is not penalised for the days we investigate. The undisputed
    remainder of the bill ages normally."*

    **A PARTIAL EXCLUSION, NOT A HELD BILL — that distinction is the whole
    rule.** Clause 1 is emphatic that the issued invoice is not voided and not
    held (hard rule 4: issued money stays), so nothing here stops a bill; what
    it stops is the LATE-FEE CLOCK, on one part of it. Sarah's July bill is
    **$184.20** and she disputes **$47.00**: **$137.20** ages on the normal
    ladder and **$47.00** does not.

    `open`    a dispute is open against this bill. This IS readable —
              `apps.billing.dispute_ageing.open_dispute_for_invoice` asks
              metering's `dispute_holds_for_unit`, which is the marker set by
              `dispute_read` and not yet cleared.
    `amount`  how much of the bill is disputed, or **None when nothing records
              it**. None is not zero and must never be read as zero: see
              `ageable_portion`, which raises **OQ-420** rather than picking
              between "nothing ages" and "everything ages", two answers that
              sit $137.20 apart on this one bill.

    `NOTHING`, below, is the constructor for the ordinary case, and it is a
    constant rather than a default argument so that a caller who has not asked
    the question cannot get the answer by omission (hard-won law 3).
    """

    open: bool = False
    amount: Decimal | None = None

    @classmethod
    def none_open(cls) -> DisputeExclusion:
        """No dispute on this bill. The whole overdue portion ages."""
        return cls(open=False, amount=None)

    @classmethod
    def unreadable(cls) -> DisputeExclusion:
        """A dispute IS open and its amount is not recorded anywhere — the only
        shape the repository can actually produce today (OQ-420)."""
        return cls(open=True, amount=None)


#: The ordinary case, named once. A bill with no dispute on it.
NO_DISPUTE = DisputeExclusion(open=False, amount=None)


def ageable_portion(*, overdue_amount: Decimal, dispute: DisputeExclusion = NO_DISPUTE) -> Decimal:
    """BR-MET-133 clause 4 — the part of the overdue portion that AGES.

    `overdue_amount − dispute.amount`, floored at zero and finalized once
    (BR-RAT-003 / B4.4). No rate is read and no figure is invented: the rule
    states the subtraction and this performs it.

    **Worked, three ways, because the third is the one a careless build gets
    wrong:**

      * Sarah's bill, the rule's own case — overdue **$184.20**, disputed
        **$47.00** → **$137.20** ages. The fee on it is
        `max($5.00, 1.5% × 137.20) = max($5.00, $2.058) = $5.00`, which is the
        same $5.00 the undisputed bill would have earned, so this case alone
        does NOT prove the exclusion is wired — which is why the next two exist.
      * A bigger bill where the percentage bites — overdue **$1,000.00**,
        disputed **$400.00** → **$600.00** ages and the fee is
        `max($5.00, 1.5% × 600.00) = $9.00`, against **$15.00** with no
        exclusion.
      * **The floor case, and it is the one that changes a customer's answer
        from "a fee" to "no fee"** — overdue **$60.00**, disputed **$40.00** →
        **$20.00** ages, which is under BR-BIL-001's $25.00 balance floor (PO
        2026-08-11), so **no fee is assessed at all** where the un-excluded
        $60.00 earns $5.00.

    ⚠ **THAT LAST INTERACTION IS A LANE READING AND IS STATED RATHER THAN
    HIDDEN.** BR-BIL-001's base is *the overdue portion*; clause 4 removes the
    disputed amount from ageing, so the overdue portion this rule is assessed
    on IS the remainder, and the $25.00 precondition tests that. Nobody put the
    combination to the PO. It is recorded in
    `12-governance/02-decision-log.md` and asserted by a test so a different
    reading cannot arrive silently.

    **A dispute with no amount RAISES — OQ-420, the prime directive's stub.**
    Not zero, not "everything", not "nothing": nothing in this repository
    stores a disputed AMOUNT (measured 2026-08-26; the same measurement
    `customers/move_out_settlement.py` recorded for BR-CUS-096), and the two
    defensible readings differ by $137.20 on Sarah's bill alone. Choosing one
    here would be this file writing money law. ⚠ **AMENDED 2026-10-17
    (`DEF-BIL-10200`): the bill run IS a production caller now**
    (`late_fee_run`), and it passes no dispute — an account with an open
    dispute is held out of the run by BR-MET-133 clause 2
    (`runs._dispute_hold_for`) and never reaches it. So the refusal still
    blocks nothing, and OQ-420 still decides the amount the day it is recorded.
    """
    if not dispute.open:
        return money.finalize(max(overdue_amount, Decimal("0")))
    if dispute.amount is None:
        raise NotImplementedError(
            "OQ-420: a dispute is open on this bill and nothing records HOW MUCH is "
            "disputed. BR-MET-133 clause 4 excludes the disputed amount from ageing and "
            "lets the undisputed remainder age normally, which cannot be computed without "
            "a figure. The two defensible fallbacks - age nothing, or age everything - are "
            "$137.20 apart on the rule's own worked bill, so neither is chosen here."
        )
    return money.finalize(max(overdue_amount - dispute.amount, Decimal("0")))


def _business_days_between(start: date, end: date, holidays: frozenset[date]) -> int:
    """Working days in the half-open interval (start, end] — weekends and the
    tenant's public holidays excluded.

    Counted forward from the DUE date (B4.1), so the due date itself is never
    one of the grace days.

    `holidays` is an ARGUMENT, never a query. This module is pure by rule
    (BR-TEN-043: `as_of` is passed in, never read from a clock), and the same
    reasoning applies to the calendar: a function that fetched the holiday rows
    itself could not be tested against a date it did not also have to seed, and
    would silently behave differently between a bill run and a preview of that
    same bill run. The caller gets the dates from
    `apps.billing.tenancy_seam.holiday_dates()` — which returns `date` objects,
    not the ISO strings tenancy's S63 payload carries. Do not reach past that
    seam into `apps.tenancy` directly: it is a B1 boundary violation AND the
    strings would match nothing here.

    An EMPTY set is a legitimate answer (a tenant that keeps no calendar), which
    is why it is not conflated with "unknown" — see `grace_has_elapsed`.
    """
    if end <= start:
        return 0
    days = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < _SATURDAY and cursor not in holidays:
            days += 1
        cursor += timedelta(days=1)
    return days


def grace_has_elapsed(
    *,
    due_date: date,
    as_of: date,
    grace_days: int,
    grace_mode: str,
    holidays: frozenset[date] | set[date] | tuple[date, ...] | None = None,
) -> bool:
    """Whether the grace period that began at `due_date` has run out by `as_of`.

    The fee applies STRICTLY AFTER the grace days elapse, in BOTH modes — PO
    ruling 2026-08-11, which settled the one-day disagreement between EP-BIL-01
    §7's two worked examples. Hence `> grace_days`, not `>=`.

    In business-day mode the walk skips weekends AND the tenant's public
    holidays (PO ruling 2026-08-11). `holidays=None` means the caller did not
    say, and in business mode that REFUSES rather than defaulting to Mon–Fri:
    the whole content of the ruling is that assuming no holidays charges a fee
    up to four days early and can land it on New Year's Day. A tenant that
    genuinely keeps no calendar passes an empty set and says so (hard-won law 3
    — the unsafe option must be the one you type).

    Refuses an unknown mode and a grace length outside BR-BIL-008's 0–30 range:
    a misconfigured tenant setting stops the assessment rather than quietly
    choosing a window.
    """
    if grace_mode not in GRACE_MODES:
        raise ValueError(
            f"unknown late-fee grace mode {grace_mode!r}; BR-BIL-002 defines "
            f"{GRACE_MODES}. A mode the code does not implement stops the "
            "assessment — it never falls through to the other one."
        )
    if not GRACE_DAYS_MIN <= grace_days <= GRACE_DAYS_MAX:
        raise ValueError(
            f"late-fee grace of {grace_days} days is outside the BR-BIL-008 range "
            f"{GRACE_DAYS_MIN}-{GRACE_DAYS_MAX}."
        )
    if grace_mode == GRACE_CALENDAR:
        # Calendar days are calendar days: holidays are irrelevant, and passing
        # them is not an error — a caller need not branch on the mode.
        elapsed = (as_of - due_date).days
    else:
        if holidays is None:
            raise ValueError(
                "business-day grace needs the tenant's holiday calendar: pass "
                "holidays=apps.billing.tenancy_seam.holiday_dates(), "
                "or holidays=frozenset() to state explicitly that this tenant "
                "keeps none. Defaulting to Monday-Friday would charge the fee up "
                "to four days early and can assess it ON a public holiday — a "
                "bill due Thu 24 Dec 2026 with 5 business days' grace would be "
                "charged on Fri 1 Jan (PO ruling 2026-08-11)."
            )
        elapsed = _business_days_between(due_date, as_of, frozenset(holidays))
    return elapsed > grace_days


def overdue_portion(
    *,
    amount_billed: Decimal,
    payments: tuple[PaymentReceipt, ...] | list[PaymentReceipt] = (),
    due_date: date,
    assessed_on: date,
) -> Decimal:
    """What is still past due — judged by WHEN THE MONEY ARRIVED. BR-BIL-071.

    PO ruling 2026-08-11 closing OQ-131, verbatim: *"at the time of billing if
    record is available that bill is generated on 5th of Sep then you llook at
    actual date for late fees not posting date; in your example acutla date will
    be 20 AUg and well within due date"*.

    **Worked, and it reverses the outcome an import-date reading produces:** a
    bill of $117.01 is due **22 Aug**; the lockbox banks the cheque **20 Aug**;
    the clerk imports the file **25 Aug**; the run happens **5 Sep**. This
    returns **0.00** — the money arrived two days early, so nothing is overdue
    and `assess_late_fee` charges nothing. Reading the import date instead makes
    the customer three days late and bills the fee.

    TWO TESTS, IN THIS ORDER, AND EACH IS HALF THE RULING:

      * `recorded_on <= assessed_on` — *"at the time of billing if record is
        available"*. Only the records that EXISTED when the bill was generated
        are counted. A payment imported after the run is not retro-applied by
        this rule, and a run replayed in 2031 therefore reaches the figure it
        reached on the day.
      * `arrived_on <= due_date` — the ACTUAL arrival date, never the posting or
        import date. This is the whole of what the PO ruled.

    A payment that arrives AFTER the due date is not deducted here, and that is
    the rule rather than an omission: BR-BIL-001's base is the OVERDUE PORTION —
    what was past due when it fell due — so money that turns up late reduces the
    balance without retroactively unmaking the lateness.

    THE ARGUMENT IS THE RECORD SET, NOT A QUERY. `payments` is another module's
    table (B1) and this module is pure by rule; the caller reads the receipts
    and hands them over, exactly as it does the holiday calendar.

    Never negative. An overpayment leaves 0.00, not a credit — a negative
    "overdue portion" fed to `assess_late_fee` would be a nonsense the $5 floor
    could turn into a real charge.

    **A RECEIPT WITH NO ARRIVAL DATE FALLS BACK TO ITS RECORDED DATE — PO
    2026-08-12, OQ-156 CLOSED.** Verbatim: *"Fall back to the recorded date"*.

    **THIS DOES NOT WEAKEN BR-BIL-071, AND THE ORDER IS WHY.** The PO's ruling of
    2026-08-11 stands untouched: where an ACTUAL arrival date exists it decides
    lateness, and the posting or import date never does. This is the case that
    rule does not cover — `payments.cleared_at` is NULL while a cheque is still
    processing, so there is no actual date to prefer. The fallback applies ONLY
    then, which is why it is written as `arrived_on or recorded_on` rather than
    as a choice between two equals.

    Worked, on this repo's own bill: **$117.01** due **22 Aug**; a $117.01 cheque
    is entered on **20 Aug** and is still clearing, so it carries no banked date.
    The fallback reads 20 Aug, the payment is inside the due date, and **no fee
    is assessed** — where the rejected reading would have charged a customer who
    paid two days early for our bank's processing time.
    """
    credited = Decimal("0")
    for receipt in payments:
        if receipt.recorded_on > assessed_on:
            # Not in the system when the bill was generated. The PO's first
            # clause, applied literally: this rule reads what was there.
            continue
        # BR-BIL-071 first, the 2026-08-12 fallback only where it is silent.
        arrived = receipt.arrived_on or receipt.recorded_on
        if arrived <= due_date:
            credited += receipt.amount
    outstanding = amount_billed - credited
    if outstanding <= Decimal("0"):
        return money.finalize(Decimal("0"))
    return money.finalize(outstanding)


def assess_late_fee(
    *,
    overdue_amount: Decimal,
    percent: Decimal,
    minimum: Decimal,
    due_date: date,
    as_of: date,
    grace_days: int,
    grace_mode: str,
    holidays: frozenset[date] | set[date] | tuple[date, ...] | None = None,
    balance_floor: Decimal = LATE_FEE_BALANCE_FLOOR,
    dispute: DisputeExclusion = NO_DISPUTE,
) -> Decimal:
    """`max(minimum, percent × overdue_amount)` once grace has run out, else 0 —
    and nothing at all while the overdue balance is under `balance_floor`.

    B5 GT-8: overdue portion 542.10, 1.5%, floor $5 → max(5, 8.1315) → **8.13**.
    The comparison runs on the unrounded product inside rating's amount rule and
    the result is finalized here, once (BR-RAT-003 / B4.4). GT-8 is UNAFFECTED
    by the balance floor — 542.10 is twenty-one times $25.00 — and the golden
    suite is run on every change here rather than that being assumed.

    **THE $25.00 PRECONDITION (PO ruling 2026-08-11, OQ-137 fee half).** *"have
    a threshold to charge late payments - if less than $25 then dont charge
    late payments"*. BR-BIL-001 is AMENDED, not replaced: the formula is
    untouched and this is a gate in front of it. A **$2.40** residue used to
    earn the **$5.00** minimum; it now earns **0.00**.

    UNDER means strictly under. A balance of exactly $25.00 is assessed, and
    gets `max($5, 1.5% × 25.00) = max($5, $0.375) = $5.00` — the boundary is
    asserted in the tests because "less than $25" has two readings and only one
    of them matches the PO's words.

    Every term is an argument and none is a constant: BR-RAT-035 makes the
    prototype's fee figures seeds rather than constants, BR-BIL-008 makes the
    grace length and mode tenant settings, and the holiday calendar is the
    tenant's own (PO ruling 2026-08-11). In business-day mode `holidays` is
    REQUIRED — see `grace_has_elapsed`. `balance_floor` DEFAULTS to the ruled
    $25.00 because hard-won law 3 puts the unsafe option on the typing hand:
    a caller that wants the pre-ruling behaviour must write
    `balance_floor=Decimal("0")` and be seen doing it.

    **THE DISPUTED AMOUNT NEVER REACHES ANY OF THIS — BR-MET-133 clause 4, PO
    2026-08-26.** `dispute` is applied FIRST: before the zero test, before the
    $25.00 floor and before the grace clock, because the rule takes the
    disputed money out of AGEING rather than cancelling a fee that applied.
    (Nothing in clause 4 forgives a fee — it changes the BALANCE the fee is
    computed from. BR-BIL-003's own word for forgiving one is deliberately
    absent from this function's source, because the guard in
    `tests/test_gt08_late_fee_grace.py` asserts that absence and it caught an
    earlier draft of this very sentence.) Every
    term below is therefore computed on the **ageable** portion. The default is
    `NO_DISPUTE`, so a caller that has not asked the question gets exactly the
    behaviour this function had before the rule and **GT-8 is untouched** —
    verified by re-running the golden suite, not assumed.

    Worked, and deliberately the case that CHANGES the answer rather than one
    that confirms it: overdue **$60.00** with **$40.00** disputed leaves
    **$20.00** ageable, which is under the $25.00 floor, so **no fee at all** —
    where the un-excluded $60.00 earns the $5.00 minimum.
    """
    overdue_amount = ageable_portion(overdue_amount=overdue_amount, dispute=dispute)
    if overdue_amount <= Decimal("0"):
        # Nothing is past due, so there is nothing to charge a percentage of.
        # The $5 floor is a floor on a fee that applies, not a fee on its own.
        return money.finalize(Decimal("0"))
    if overdue_amount < balance_floor:
        # PO ruling 2026-08-11 (OQ-137, fee half): the balance is too small to
        # chase. Checked BEFORE the grace clock and before rating is called, so
        # a small balance is never a fee no matter how long it sits.
        return money.finalize(Decimal("0"))
    if not grace_has_elapsed(
        due_date=due_date,
        as_of=as_of,
        grace_days=grace_days,
        grace_mode=grace_mode,
        holidays=holidays,
    ):
        return money.finalize(Decimal("0"))
    return money.finalize(
        rating_seam.charge_amount(
            rule=LATE_FEE_RULE,
            percent=percent,
            basis=overdue_amount,
            minimum=minimum,
        )
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-078 — WHERE THE TWO TERMS COME FROM (BR-RAT-1011, PO ruling 2026-09-07)
# ══════════════════════════════════════════════════════════════════════════
# THE RULING, VERBATIM: *"this is wrong - you ahve to take late fees form
# charge code mentione din the plan - if plan doent provide you that charge
# code then you have to put zero on late payment. - Logic aplplied ot Minimum
# late fee $5- - you can link these defaults in Charge code - we have a charge
# code for late payment"*. Finance re-signed the same day
# (12-governance/09-human-review-ledger.md), because a late fee is a ❄️ FROZEN
# B4/B5 figure and this decides which copy of it the engine reads.
#
# ⚠ **`assess_late_fee` ABOVE IS UNTOUCHED, AND THAT IS DELIBERATE RATHER THAN
# LAZY.** It takes `percent` and `minimum` as arguments and always has; GT-8
# hands it `0.015` and `5` from Python literals and reads no database, so the
# frozen 8.13 cannot move whatever this section does. The change is a layer
# ABOVE it: which two numbers get handed in, and the new answer *none at all*.
#
# ⚠ **THE ZERO IS A RULE, NOT A FALLBACK, AND IT IS THE ONE THING A READER
# MUST NOT "TIDY".** Every other nullable term in this product falls back —
# `PlanPenaltyRule.late_fee_pct` NULL means the tenant default, `minimum_bill_
# amount` NULL means the tenant default. This one does not. A plan naming no
# late-fee charge code charges **$0.00**, and re-adding a fallback to
# `tenant_settings.billing_defaults.late_pct` would silently reinstate the
# behaviour the PO ruled against.

#: A plan charges no late fee. The REASON, carried beside the zero so a screen,
#: a log line or a test can say WHICH zero this is — a plan that charges
#: nothing, or an assessment that never ran. CLAUDE.md's own lesson: an absence
#: is invisible to every check this repo has, so it is given a name.
NO_LATE_FEE_TERMS = "plan_names_no_late_fee_charge_code"


@dataclass(frozen=True)
class LateFeeTerms:
    """The two terms BR-BIL-001's arithmetic needs, and where they came from.

    `charge_id` is the tenant's own `rating.charges.id` — the GL account the fee
    books to (BR-BIL-075 / BR-BIL-010), carried so the CALCULATION and the
    BOOKING can never name two different codes. Before `CR-078` they were two
    independent lookups: `decisions._late_fee_charge_id` resolved `"LATE"` by
    name for the account, while the amount came from the tenant's settings
    screen. One plan, two sources, and nothing checking they agreed.
    """

    percent: Decimal
    minimum: Decimal
    charge_id: str
    code: str
    name: str | None = None
    #: 🔒 PO ruling 2026-10-06 11 (a) — the grace the fee is assessed on, read
    #: with the terms so the CODE that prices the fee also times it. `None`
    #: only from a caller building terms by hand; the plan read always states
    #: one (`rating.selectors._late_fee_grace`). `grace_from` says whose it is.
    grace_days: int | None = None
    grace_mode: str | None = None
    grace_from: str | None = None
    #: 🔒 DEF-BIL-10201 (PO 2026-10-17, *"we ahve to allow flat as we wll
    #: %age"*) — `flat` charges `flat_amount` whatever the overdue amount;
    #: anything else is the percent-with-minimum arithmetic above, unchanged.
    amount_rule: str = "percent_with_minimum"
    flat_amount: Decimal | None = None

    @property
    def is_flat(self) -> bool:
        return self.amount_rule == AMOUNT_RULE_FLAT


#: The one amount rule that is not `max(minimum, percent × overdue)`.
AMOUNT_RULE_FLAT = "flat"


class LateFeePlanUnreadable(Exception):
    """The plan whose late-fee terms were asked for could not be read at all.

    ⚠ **NOT THE PO's ZERO, AND THE DISTINCTION IS THE SAFETY OF THIS WHOLE
    CHANGE.** BR-RAT-1011 says *"if plan doent provide you that charge code then
    you have to put zero"* — a plan that EXISTS and names none. An account
    whose plan id is absent, malformed or names no row of this tenant is a DATA
    FAULT: nothing could have priced it, and answering "no late fee" would turn
    a broken account into a permanently free one with nothing going red.

    So it raises, and the caller decides. `decisions.apply_decisions` lets it
    stop the CALCULATE step, exactly as `_late_fee_charge_id` already stops it
    for a tenant with no code — same refusal, same reason, one rule earlier.
    """


class LateFeeClassNotPriced(Exception):
    """🔒 `DEF-RAT-8753` — the plan's late-fee code is priced BY CUSTOMER
    CLASS, states no terms for this account's class, and states no single
    percent beside them. Not the ruled zero (BR-RAT-1011 is a plan naming NO
    code): the utility priced the fee for other classes, and charging this one
    nothing would be a free late fee nobody chose. Raised, and the caller
    decides — as `LateFeePlanUnreadable` is."""


def late_fee_terms_for_plan(
    rate_plan_id: object, customer_class: str | None = None, on_date: date | None = None
) -> LateFeeTerms | None:
    """The plan's late-fee terms, or **None meaning ZERO** — BR-RAT-1011.

    `None` is the RULED answer for exactly two states, and each is *this plan
    charges no late fee*: the plan names no charge code, or the code it names
    was retired (IS-1). Both are things a human at the utility did.

    It RAISES `LateFeePlanUnreadable` when there is no plan to ask — see that
    class. And it raises out of the seam when rating has not published the read
    at all, because a deployment fault answering "no fee" would stop every late
    fee in the product with nothing going red.
    """
    row = rating_seam.plan_late_fee_terms(
        rate_plan_id, customer_class=customer_class, on_date=on_date
    )
    if row is None:
        raise LateFeePlanUnreadable(
            f"rate plan {rate_plan_id!r} could not be read, so the late-fee terms it "
            "names cannot be resolved (BR-RAT-1011). This is NOT the ruled zero: the "
            "ruling is about a plan that exists and names no charge code. An account "
            "whose plan cannot be read could not have been priced either."
        )
    if row.get("charge_id") is None:
        # THE RULING. A real plan that charges nothing.
        return None
    if row.get("refusal"):
        raise LateFeeClassNotPriced(
            f"the late-fee charge code {row.get('code')!r} is priced by customer class and "
            f"states no terms for class {customer_class!r} (DEF-RAT-8753). Nothing here "
            "charges zero for it: a human adds the class's percent and minimum on the "
            "charge code."
        )
    flat = (row.get("amount_rule") or "") == AMOUNT_RULE_FLAT
    return LateFeeTerms(
        # A flat code carries no percent pair; zeros keep the dataclass total
        # and are never read on the flat path (`assess_late_fee_on_terms`).
        percent=Decimal("0") if flat else Decimal(str(row["percent"])),
        minimum=Decimal("0") if flat else Decimal(str(row["minimum"])),
        amount_rule=AMOUNT_RULE_FLAT if flat else str(row.get("amount_rule") or "percent_with_minimum"),
        flat_amount=Decimal(str(row["flat_amount"])) if flat else None,
        charge_id=str(row["charge_id"]),
        code=str(row["code"]),
        name=row.get("name"),
        grace_days=None if row.get("grace_days") is None else int(row["grace_days"]),
        grace_mode=row.get("grace_mode"),
        grace_from=row.get("grace_from"),
    )


def late_fee_grace_of(
    terms: LateFeeTerms, *, grace_days: int | None = None, grace_mode: str | None = None
) -> tuple[int, str]:
    """🔒 The grace a fee on `terms` is assessed on — the late-fee CODE's (PO
    ruling 2026-10-06 11 (a)). A caller-stated grace must agree with it.

    Refuses rather than choosing: a caller passing the tenant's Billing-defaults
    grace beside a code stating 10 days is two answers to one question, and
    picking either silently moves a customer's late-fee date.
    """
    days = terms.grace_days if terms.grace_days is not None else grace_days
    mode = terms.grace_mode or grace_mode
    if days is None or mode is None:
        raise ValueError(
            f"no late-fee grace for code {terms.code!r}: the plan read states none and "
            "the caller passed none (PO ruling 2026-10-06 11 (a) — billing uses the "
            "late-fee code's grace)."
        )
    if (grace_days is not None and grace_days != days) or (grace_mode is not None and grace_mode != mode):
        raise ValueError(
            f"the caller's late-fee grace ({grace_days}, {grace_mode!r}) disagrees with the "
            f"grace on code {terms.code!r} ({days}, {mode!r}). Billing uses the code's grace "
            "(PO ruling 2026-10-06 11 (a)); pass none."
        )
    return int(days), str(mode)


def assess_late_fee_for_plan(
    *,
    rate_plan_id: object,
    overdue_amount: Decimal,
    due_date: date,
    as_of: date,
    grace_days: int | None = None,
    grace_mode: str | None = None,
    holidays: frozenset[date] | set[date] | tuple[date, ...] | None = None,
    balance_floor: Decimal = LATE_FEE_BALANCE_FLOOR,
    dispute: DisputeExclusion = NO_DISPUTE,
    customer_class: str | None = None,
) -> tuple[Decimal, LateFeeTerms | None]:
    """THE PRODUCTION ENTRY POINT — the fee, and the terms it was computed on.

    **This is the function `CR-078` switched.** It resolves the two terms from
    the charge code the PLAN names and hands them to `assess_late_fee`
    unchanged; when the plan names none it returns `Decimal("0.00")` and `None`
    **without calling the arithmetic at all**, because there is no fee to
    compute rather than a fee that came to zero.

    Returns a PAIR on purpose. A bare `Decimal("0.00")` cannot tell a caller
    whether the customer paid on time, whether grace is still running, or
    whether this plan charges no late fees at all — and a screen that says
    *"Late fee $0.00"* over the third case is telling a clerk the fee was
    calculated. The terms come back so the caller can say which zero it has.

    WORKED, ON THE SIGNED REFERENCE FIGURE (GT-8 / GT-10, ❄️ B5 FROZEN):
    a plan pointing at the seeded `LATE` code (`percent 1.5`, `min_amount 5`)
    over an overdue portion of **$542.10**, six calendar days past a due date
    with five days' grace, gives `max($5.00, 1.5% × $542.10) = $8.13` — the
    same $8.13 the Billing-defaults screen produced, because the seed carries
    the same two figures. The SAME account on a plan naming no code gives
    **$0.00**, which is the behaviour change and the whole of the ruling.

    ⚠⚠ **AMENDED 2026-10-06 — THE GRACE COMES FROM THE LATE-FEE CODE TOO.**
    This paragraph read *"Grace stays where it was — `PlanPenaltyRule
    .grace_days` / `grace_mode` over the tenant's default"* until the PO ruled
    11 (a), verbatim: *"Put grace on the late-fee code. When Type is Penalty,
    the form asks Grace days (default 5) and Calendar / Business days, and
    billing uses the code's grace."* 🔒 HUMAN-REVIEW-PENDING — ❄️ B4/B5 late
    fee, finance RE-SIGN owed (HUMAN-GUIDE §6) on: *"Due 1 Nov, grace 5 days on
    LATE, $100.00 unpaid after 6 Nov → $5.00 on the next bill; grace 10 days on
    LATE → no fee until after 11 Nov."* `terms.grace_days/grace_mode` carry it
    (`rating.selectors._late_fee_grace`: a plan override stated before the
    ruling, else the code's, else Billing defaults). **A caller states NO
    grace**; one that does (the tests written before the ruling) must state
    the SAME grace the terms carry, or this refuses — two graces for one fee
    is the two-sources shape `CR-078` closed for the percent. The arithmetic
    (`grace_has_elapsed`, BR-BIL-008/002, GT-8) is unchanged.
    """
    # 🔒 DEF-RAT-8753 — the account's CLASS picks the code's per-class terms
    # where it states any, on the ASSESSMENT day (`as_of`): a price change
    # dated after the assessment does not reach it. Worked (the mock-up's
    # `LATE`): Residential $200.00 overdue → max($5.00, 1.50% × 200 = $3.00) =
    # **$5.00**; Commercial $2,000.00 → max($10.00, 2.00% × 2,000 = $40.00) =
    # **$40.00**. A code with no class rows reads its own two columns as
    # before, so GT-8 / GT-10's ❄️ $8.13 does not move.
    terms = late_fee_terms_for_plan(rate_plan_id, customer_class=customer_class, on_date=as_of)
    if terms is None:
        # BR-RAT-1011. Not `assess_late_fee(percent=0, minimum=0)`: that would
        # run the grace clock and the balance floor over a fee that does not
        # exist, and would put a 0.00 through rating's amount rule as though a
        # rule had produced it.
        return money.finalize(Decimal("0")), None
    days, mode = late_fee_grace_of(terms, grace_days=grace_days, grace_mode=grace_mode)
    return (
        assess_late_fee_on_terms(
            terms,
            overdue_amount=overdue_amount,
            due_date=due_date,
            as_of=as_of,
            grace_days=days,
            grace_mode=mode,
            holidays=holidays,
            balance_floor=balance_floor,
            dispute=dispute,
        ),
        terms,
    )


def assess_late_fee_on_terms(
    terms: LateFeeTerms,
    *,
    overdue_amount: Decimal,
    due_date: date,
    as_of: date,
    grace_days: int,
    grace_mode: str,
    holidays: frozenset[date] | set[date] | tuple[date, ...] | None = None,
    balance_floor: Decimal = LATE_FEE_BALANCE_FLOOR,
    dispute: DisputeExclusion = NO_DISPUTE,
) -> Decimal:
    """🔒 HUMAN-REVIEW-PENDING — the fee on ONE set of terms: percent or FLAT.

    **The percent path IS `assess_late_fee`, called unchanged**, so ❄️ GT-8's
    `max($5.00, 1.5% × $542.10)` = **$8.13** is reached by exactly the
    arithmetic B5 signed.

    **The flat path (DEF-BIL-10201, PO 2026-10-17 — *"we ahve to allow flat as
    we wll %age"*) runs the SAME three gates** — the disputed amount out of
    ageing first (BR-MET-133 clause 4), nothing under the $25.00 balance floor
    (BR-BIL-001 as amended), nothing until grace has run out (BR-BIL-008/002)
    — and then charges the code's flat amount whatever the overdue amount is.
    The decision log records the ruling as *"both only after due date + grace
    and only at ≥ $25.00 overdue"*. Worked: Flat $10.00 on $900.00 overdue
    past grace → **$10.00**; on $24.99 → **$0.00**; within grace → **$0.00**.
    Finalized once (BR-RAT-003), never re-rounded.
    """
    if not terms.is_flat:
        return assess_late_fee(
            overdue_amount=overdue_amount,
            percent=terms.percent,
            minimum=terms.minimum,
            due_date=due_date,
            as_of=as_of,
            grace_days=grace_days,
            grace_mode=grace_mode,
            holidays=holidays,
            balance_floor=balance_floor,
            dispute=dispute,
        )
    ageable = ageable_portion(overdue_amount=overdue_amount, dispute=dispute)
    if ageable <= Decimal("0") or ageable < balance_floor:
        return money.finalize(Decimal("0"))
    if not grace_has_elapsed(
        due_date=due_date,
        as_of=as_of,
        grace_days=grace_days,
        grace_mode=grace_mode,
        holidays=holidays,
    ):
        return money.finalize(Decimal("0"))
    if terms.flat_amount is None:  # pragma: no cover — the terms read refuses first
        raise LateFeeClassNotPriced(f"the flat late-fee code {terms.code!r} states no amount")
    return money.finalize(terms.flat_amount)


def overdue_after_grace(
    *,
    amount_billed: Decimal,
    payments: tuple[PaymentReceipt, ...] | list[PaymentReceipt] = (),
    due_date: date,
    assessed_on: date,
    grace_days: int,
    grace_mode: str,
    holidays: frozenset[date] | set[date] | tuple[date, ...] | None = None,
) -> Decimal:
    """🔒 HUMAN-REVIEW-PENDING — what was still unpaid WHEN GRACE RAN OUT, judged
    by the date the money ARRIVED (BR-BIL-071) — the base a bill-run late fee
    is computed on (DEF-BIL-10200, decision log 2026-10-17: *"if an overdue
    amount ≥ $25.00 is past due date + grace (by the date money arrived)"*).

    `overdue_portion` above credits only money that arrived ON OR BEFORE the
    due date. That is its own signed reading and it is left alone; this is the
    same walk with the grace window as the customer's: a payment counts as on
    time when grace had NOT yet elapsed on the day it arrived
    (`grace_has_elapsed`, the same strictly-after boundary the PO ruled for
    both modes on 2026-08-11). Without that, a customer paying in full on day
    three of a five-day grace would still be charged at the next run — the
    grace the rule grants would grant nothing.

    Worked, both of the PO's own figures: $100.00 due 09/21, grace 5 calendar
    days (to 09/26), paid in full **10/05** → **$100.00** overdue, so the
    October run charges **$5.00**; the same $100.00 paid **09/24** → **$0.00**.

    The records rule is unchanged: only receipts RECORDED on or before
    `assessed_on` are read (*"at the time of billing if record is
    available"*), and a receipt with no arrival date falls back to its
    recorded date (OQ-156). Never negative; finalized once.
    """
    credited = Decimal("0")
    for receipt in payments:
        if receipt.recorded_on > assessed_on:
            continue
        arrived = receipt.arrived_on or receipt.recorded_on
        late = grace_has_elapsed(
            due_date=due_date,
            as_of=arrived,
            grace_days=grace_days,
            grace_mode=grace_mode,
            holidays=holidays,
        )
        if not late:
            credited += receipt.amount
    outstanding = amount_billed - credited
    if outstanding <= Decimal("0"):
        return money.finalize(Decimal("0"))
    return money.finalize(outstanding)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — GT-8 companion seam)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-8 PASS✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# revised: 2026-08-11 — PO ruled BOTH reported items. (1) the BUSINESS-DAY grace boundary is SETTLED: "strictly after the grace days elapse" is correct for both modes (due Thu 10 Sep + 5 → calendar Wed 16 Sep, business Fri 18 Sep, not Thu 17); WE-15(e) is the erroneous example. Code unchanged — the ruling ratifies what was built. (2) the business-day clock now SKIPS the tenant public holidays (PO ruling 2026-08-11, option A "build the holiday calendar now"): `holidays` is a required argument in business mode and refusing None is deliberate, since defaulting to Mon–Fri would silently reinstate the rejected behaviour for every un-updated caller. WHAT RUNS AND WHAT WAS RULED NOW AGREE — before this change the module skipped weekends only.
# revised: 2026-08-11 (holiday lane, second pass) — RED PROOF EXECUTED, not asserted. The earlier trailer said "Proved RED by removing the skip" with no measured output; it was re-run rather than trusted (hard-won law 1). Measured: `and cursor not in holidays` deleted from `_business_days_between`, then `pytest tests/test_gt08_late_fee_grace.py -q` → `1 failed, 9 passed in 0.12s`, FAILED test_business_day_grace_skips_public_holidays with `AssertionError: assert Decimal('8.13') == Decimal('0.00')` on as_of=2027-01-01 — the fee back ON New Year's Day. Patch reverted; `10 passed in 0.07s`. Also this pass: the docstring no longer tells callers to read `apps.tenancy.selectors.holidays()` directly — that was a B1 boundary violation AND returns ISO date strings, which match nothing against a `date` cursor; the B1-legal path is apps/billing/tenancy_seam.py (new, tested, red-proved). No new storage or migration: `holiday_calendars` already existed (tenancy, S63/BR-TEN-039). exceptions: (3) The zero-overdue branch returns 0 rather than the $5 floor — the floor is a minimum on a fee that applies (BR-BIL-001 reads "max($5, 1.5% × overdue portion)" of a bill that IS past due), and B5 exercises only the applying case. (4) First-time waiver is deliberately absent: BR-BIL-003 makes it a manual staff decision. (5) NOTHING SEEDED into holiday_calendars — no signed document names a default holiday set, so tenants start empty and correct rather than with an invented US federal list. (6) No production caller feeds `holidays` yet because `assess_late_fee` has no production caller at all (S31.2/US-BIL-002 unbuilt) — PRE-EXISTING, not introduced here, and REPORTED rather than papered over.
# revised: 2026-08-11 (late-fee rulings lane) — TWO PO RULINGS OF 2026-08-11 BUILT, each with its red proof MEASURED rather than claimed. (A) **BR-BIL-001 AMENDED — no late fee while the overdue balance is under $25.00** (OQ-137, fee half; PO verbatim *"have a threshold to charge late payments - if less than $25 then dont charge late payments"*). `LATE_FEE_BALANCE_FLOOR = Decimal("25.00")` gates `assess_late_fee` BEFORE the grace clock and before rating is called. The formula is untouched — this is a precondition on the BALANCE, never a floor on the fee. Worked: a $2.40 residue used to earn $5.00 and now earns 0.00; $25.00 exactly IS charged ($5.00), because "less than $25" is strict. GT-8 is UNAFFECTED and that was VERIFIED not assumed — 542.10 is 21× the threshold and `pytest tests -m golden` was re-run. RED PROOF EXECUTED AND MEASURED: with the `if overdue_amount < balance_floor: return money.finalize(Decimal("0"))` branch DELETED from `assess_late_fee`, `pytest tests/test_po_20260811_late_fee_rulings.py -q` measured `3 failed, 9 passed in 0.13s` — FAILED test_a_residue_under_the_threshold_earns_no_late_fee, test_the_threshold_is_the_ratified_figure_and_is_strict and test_a_part_payment_leaves_the_residue_and_an_overpayment_leaves_nothing; first failure verbatim `AssertionError: the $2.40 residue must earn NOTHING under the PO's $25.00 floor (it used to earn the $5.00 minimum)` / `assert Decimal('5.00') == Decimal('0.00')` / `+ where Decimal('5.00') = fee(Decimal('2.40'))` — i.e. the $2.40 residue back on the $5.00 minimum, the exact case the PO ruled against. Patch reverted → `12 passed in 0.07s`. (B) **BR-BIL-071 — lateness is decided by the ACTUAL date the money arrived** (OQ-131 CLOSED; PO verbatim *"at the time of billing if record is available that bill is generated on 5th of Sep then you llook at actual date for late fees not posting date; in your example acutla date will be 20 AUg and well within due date"*). New: `PaymentReceipt(amount, arrived_on, recorded_on)` and `overdue_portion(...)`. `arrived_on <= due_date` decides lateness; `recorded_on <= assessed_on` decides which records existed when the bill was generated (the PO's first clause, a second rule). `recorded_on` is NEVER consulted for lateness and is carried precisely because it is the REJECTED reading — present and unused is a rule a test can assert. Worked: banked 20 Aug, due 22 Aug, imported 25 Aug, run 5 Sep → overdue 0.00 and NO fee, where the import-date reading bills $8.13. RED PROOF EXECUTED AND MEASURED: with the one lateness line changed from `if receipt.arrived_on <= due_date:` to `if receipt.recorded_on <= due_date:` — the import-date reading, and the ONLY line that differs between the two readings — `pytest tests/test_po_20260811_late_fee_rulings.py -q` measured `4 failed, 8 passed in 0.13s` — FAILED test_lateness_is_the_actual_arrival_date_not_the_import_date, test_only_the_records_that_existed_when_the_bill_was_generated_are_read, test_a_part_payment_leaves_the_residue_and_an_overpayment_leaves_nothing and test_the_import_date_is_carried_and_never_consulted_for_lateness; first failure verbatim `AssertionError: money in the bank on 20 Aug against a bill due 22 Aug is NOT overdue — the import date (25 Aug) must not decide this` / `assert Decimal('117.01') == Decimal('0.00')` — i.e. the whole bill back in the overdue portion on money that was in the bank two days early. Patch reverted → `12 passed in 0.08s`.
# revised: 2026-08-12 (PO ruling, OQ-156 CLOSED) — a receipt with NO ACTUAL arrival date (cleared_at NULL while an instrument is still processing) now FALLS BACK to its recorded date. PO verbatim: "Fall back to the recorded date". This line previously described the opposite — a refusal — and is rewritten rather than appended to, because a trailer describing a refusal the code no longer makes is hard-won law 1. BR-BIL-071 is untouched and the ordering proves it: where an arrival date EXISTS it still decides lateness and the posting date still never does; the fallback reaches only the case the 2026-08-11 ruling was silent about. Worked: $117.01 due 22 Aug, a cheque entered 20 Aug still clearing reads as 20 Aug and attracts no fee, while one entered 25 Aug reads as 25 Aug and is overdue.
# exceptions: (7) THE $25.00 FIGURE IS A DEFAULT ARGUMENT, NOT A TENANT SETTING. BR-BIL-021 makes the late %, the minimum and the grace window tenant config; whether this floor joins them was never put to the PO, so it is raised as **OQ-157** and the ruled figure ships as the default of `balance_floor`. Law 3 decides which way the default points — charging a fee on a $2.40 residue is the unsafe option, so a caller wanting the pre-ruling behaviour must type `balance_floor=Decimal("0")`. (8) THE COLLECTION LADDER IS NOT TOUCHED. OQ-137 asked about the ladder too (the certified letter, the disconnection notice); the PO ruled on the FEE and the ladder half stays OPEN, so nothing here reads the threshold for anything else. (9) `overdue_portion` HAS NO PRODUCTION CALLER, for the same pre-existing reason `assess_late_fee` has none — S31.2/US-BIL-002 is unbuilt. The ruling is implemented and tested; it is not yet consuming real `payments` rows, and the mapping `payments.cleared_at → arrived_on` / `posted_at → recorded_on` is stated in the docstring rather than wired, because `apps/payments/**` belongs to another lane in this session. REPORTED, not papered over (hard-won law 2). (10) A payment arriving AFTER the due date does not reduce the overdue portion. BR-BIL-001's base is what was past due; money that turns up late lowers the balance without unmaking the lateness. Stated because it is a rule and not an oversight.
# revised: 2026-08-26 (BR-MET-132/133 lane, CR-038) — **BR-MET-133 clause 4 BUILT: the disputed amount does not age.** PO verbatim 2026-08-26, closing OQ-245: *"Bill stands, resolution through the billed-correction door, and the disputed amount doesn't age into late fees while open"*, and the rule adds *"the undisputed remainder of the bill ages normally"*. New: `DisputeExclusion`, `NO_DISPUTE` and `ageable_portion(overdue_amount, dispute)`, plus a `dispute=` argument on `assess_late_fee` applied BEFORE the zero test, the $25.00 balance floor and the grace clock — clause 4 removes money from AGEING, it does not waive a fee that applied. It is a PARTIAL exclusion and never a held bill: hard rule 4 keeps the issued invoice exactly where it is, and clauses 1–3 are existing behaviour CONFIRMED by test rather than rebuilt. Worked, three ways, and the third is the one that changes a customer's answer: $184.20 with $47.00 disputed ages $137.20 (fee $5.00, same as undisputed — which is why it alone proves nothing); $1,000.00 with $400.00 disputed ages $600.00 and the fee is **$9.00** against **$15.00** un-excluded; $60.00 with $40.00 disputed ages $20.00, under the $25.00 floor, so **NO FEE AT ALL** where the un-excluded $60.00 earns $5.00. RED PROOF EXECUTED AND MEASURED: with the `overdue_amount = ageable_portion(...)` line DELETED from `assess_late_fee` — the one line that applies the rule — `pytest tests/test_br_met_133_dispute_ageing.py -q` measured `4 failed, 14 passed in 0.15s`; first failure verbatim `AssertionError: BR-MET-133 clause 4: $47.00 of Sarah's $184.20 bill is disputed, so 1.5% is charged on $137.20 and not on the full bill` / `assert Decimal('15.00') == Decimal('9.00')` on the $1,000/$400 case, and the floor case failed with `assert Decimal('5.00') == Decimal('0.00')` — a $5.00 late fee on a customer whose whole undisputed balance is $20.00. Patch reverted → `18 passed in 0.10s`. **GT-8 IS UNAFFECTED AND THAT WAS VERIFIED, NOT ASSUMED**: `dispute` defaults to `NO_DISPUTE`, `pytest tests -m golden` and `10-scripts/03-golden-verify.py` were both re-run. ⚠ **THE $25.00 FLOOR APPLYING TO THE REMAINDER IS A LANE READING** — BR-BIL-001's base is *the overdue portion*, clause 4 makes that the remainder, and the combination was never put to the PO; recorded in 12-governance/02-decision-log.md and asserted by a test.
# exceptions: (11) **THE DISPUTED AMOUNT IS NOT RECORDED ANYWHERE AND IS REFUSED RATHER THAN DEFAULTED — OQ-420 (MINTED, 🔒).** Measured 2026-08-26 across the repo: no model, no column, no service writes one; the same measurement `customers/move_out_settlement.py` recorded for BR-CUS-096 on 2026-08-24. `meter_reads.disputed_at` is a QUANTITY in dispute, not a sum of money, and is deliberately not read as one (CLAUDE.md rule 3). So an open dispute with `amount=None` raises `NotImplementedError("OQ-420")` — the two fallbacks (age nothing / age everything) are $137.20 apart on the rule's own bill. This blocks nothing today: `assess_late_fee` still has no production caller (exception 9, unchanged). (12) **THE AGEING HALF OF CLAUSE 4 HAS NO IMPLEMENTATION TO EXCLUDE FROM.** The rule says *"excluded from ageing AND from late-fee assessment"*. Billing publishes no `account_aging_state` (customers' seam has been resolving a function that does not exist since W2), and `customers.selectors`' ageing reads OPENING BUCKETS only, which predate any bill. The late-fee half is the half that exists, and it is the half built here — REPORTED, not papered over (hard-won law 2).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
