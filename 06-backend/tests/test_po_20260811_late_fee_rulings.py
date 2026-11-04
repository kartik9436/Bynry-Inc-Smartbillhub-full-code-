# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — the late-fee assessment of S31.2's Balances
#           tab and S31.3's per-case rows)
#           Screens: — (the fee line renders on the invoice / S31.2)
#           NOTE: no US-ID is cited in this header ON PURPOSE, the same reason
#           apps/billing/late_fee.py states in its own: G10 reads a
#           Trace-header US-ID as "this file ships that story's TCs", and this
#           file asserts two PO rulings about one pure calculation, not the
#           six-tab S31.2 preview story that consumes it.
# Rules:    BR-BIL-001 (late fee = max($5, 1.5% × OVERDUE PORTION) — **AMENDED
#           2026-08-11 by the PO: no fee at all while the overdue balance is
#           under $25.00**) · BR-BIL-071 (lateness is decided by the ACTUAL
#           date the money arrived, never the posting or import date, on the
#           records that exist when the bill is generated — PO 2026-08-11,
#           OQ-131 CLOSED) · BR-BIL-008 (grace: tenant-defined, default 5
#           calendar days) · BR-BIL-003 (a waiver is manual, never automatic) ·
#           BR-TEN-043 (event time is an argument, never a clock)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08 (max(5, 0.015 × 542.10) = 8.13).
#           Asserted here too, deliberately: the $25.00 floor lands in front of
#           the same function, and "GT-8 is far above the threshold" is a claim
#           this file makes bite rather than a sentence in a docstring.
# Tests:    this file
# Impacts:  apps/billing/late_fee.py · apps/billing/services.py
# ───────────────────────────────────────────────────────
"""The two late-fee rulings the Product Owner made on 2026-08-11, as tests.

Each ruled figure is asserted so drift goes RED, and each REJECTED reading is
asserted alongside it — a test that only states the answer cannot tell a later
reader what was rejected, and both of these rulings reverse an outcome the code
would otherwise produce.

RULING A — NO LATE FEE ON A BALANCE UNDER $25.00 (OQ-137, the fee half)
----------------------------------------------------------------------
PO verbatim: *"have a threshold to charge late payments - if less than $25 then
dont charge late payments"*.

BR-BIL-001 is AMENDED, not replaced: `max($5, 1.5% × overdue portion)` still
computes the fee and this adds a precondition in front of it. The threshold is
a floor on the BALANCE, not on the fee — which is why a $25.00 balance is
charged $5.00, a fee far below the threshold, and that case is asserted below.

Worked, and it is the case the PO was shown: a **$2.40** residue used to earn
the **$5.00** minimum — more than twice the debt — and now earns nothing.

RULING B — LATENESS IS THE ACTUAL DATE THE MONEY ARRIVED (OQ-131 CLOSED)
-----------------------------------------------------------------------
PO verbatim: *"at the time of billing if record is available that bill is
generated on 5th of Sep then you llook at actual date for late fees not posting
date; in your example acutla date will be 20 AUg and well within due date"*.

Worked: money reaches the bank **20 Aug**, the bill is due **22 Aug**, the file
is imported **25 Aug**, the run happens **5 Sep** → NOT late, no fee. The
import-date reading makes the customer three days late and bills the fee for
money that was in the bank two days early.

The sentence carries two rules and both are asserted: WHICH DATE decides
lateness (the arrival), and WHICH RECORDS are read (the ones that exist when
the bill is generated).

WHAT THIS FILE DELIBERATELY DOES NOT ASSERT
-------------------------------------------
The COLLECTION LADDER. OQ-137 also asked whether the certified letter and the
disconnection notice share the $25.00 floor; the PO ruled on the FEE and the
ladder half stays OPEN. Asserting a ladder threshold here would pin behaviour
nobody has ruled on.
"""

from datetime import date
from decimal import Decimal

from apps.billing import late_fee, services

# GT-8's inputs. The FIGURE 8.13 is frozen in tests/golden/test_gt08_late_fee.py;
# it appears here because the $25.00 floor sits in front of the same function.
PERCENT = Decimal("0.015")
MINIMUM = Decimal("5")
GT8_OVERDUE = Decimal("542.10")

#: A tenant that keeps no holiday calendar, stated explicitly — business mode
#: refuses `None` and every case below is calendar mode anyway.
NO_HOLIDAYS: frozenset[date] = frozenset()

# ── Ruling A's dates ────────────────────────────────────────────────────────
# Scaffolding, not frozen figures: any pair "past the due date beyond grace"
# does. Due Wed 15 Jul 2026, assessed Tue 21 Jul — 6 calendar days, past a
# 5-day grace.
DUE = date(2026, 7, 15)
PAST_GRACE = date(2026, 7, 21)

# ── Ruling B's dates — the PO's own worked case, to the day ─────────────────
BILL_TOTAL = Decimal("117.01")  # this repo's reference bill
BILL_DUE = date(2026, 8, 22)  # "bill due 22 Aug"
MONEY_IN_THE_BANK = date(2026, 8, 20)  # "actual date will be 20 AUg"
FILE_IMPORTED = date(2026, 8, 25)  # "payment file imported 25 Aug"
BILL_RUN = date(2026, 9, 5)  # "bill is generated on 5th of Sep"


def fee(overdue, *, as_of=PAST_GRACE, due=DUE, **kwargs):
    """`assess_late_fee` with GT-8's rate and floor and a 5-day calendar grace."""
    return services.assess_late_fee(
        overdue_amount=overdue,
        percent=PERCENT,
        minimum=MINIMUM,
        due_date=due,
        as_of=as_of,
        grace_days=5,
        grace_mode="calendar",
        holidays=NO_HOLIDAYS,
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════════════════
# RULING A — the $25.00 balance floor (OQ-137, fee half)
# ══════════════════════════════════════════════════════════════════════════
def test_a_residue_under_the_threshold_earns_no_late_fee():
    """The PO's worked case: a $2.40 residue earns NOTHING.

    Both halves asserted. Under the ruling the fee is 0.00; the rejected
    behaviour — BR-BIL-001's $5.00 minimum applied to $2.40, more than twice
    the debt — is asserted by naming the floor a caller would have to type to
    get it back, so the test states what changed and not merely where it landed.
    """
    assert fee(Decimal("2.40")) == Decimal("0.00"), (
        "the $2.40 residue must earn NOTHING under the PO's $25.00 floor "
        "(it used to earn the $5.00 minimum)"
    )
    # The rejected reading, kept visible: with the floor removed the same
    # residue is charged $5.00 — which is what the PO ruled against.
    assert fee(Decimal("2.40"), balance_floor=Decimal("0")) == Decimal("5.00")


def test_the_threshold_is_the_ratified_figure_and_is_strict():
    """$25.00 exactly, and "less than $25" means strictly less.

    The constant is asserted so a drifted figure goes RED (the PO's sign-off
    test: a test must assert the ratified number). The boundary is asserted
    because "less than $25" has two readings and only one matches the words.
    """
    assert late_fee.LATE_FEE_BALANCE_FLOOR == Decimal("25.00")
    assert fee(Decimal("24.99")) == Decimal("0.00")  # under → nothing
    assert fee(Decimal("25.00")) == Decimal("5.00")  # not under → charged


def test_the_floor_is_on_the_balance_never_on_the_fee():
    """The distinction the decision log makes, as an assertion.

    A $25.00 overdue balance is charged `max($5, 1.5% × 25.00)` = **$5.00** — a
    fee twenty dollars below the threshold. If the $25.00 were a floor on the
    FEE this case would be zero, so the two readings disagree here and nowhere
    else.
    """
    assert fee(Decimal("25.00")) == Decimal("5.00")
    assert Decimal("5.00") < late_fee.LATE_FEE_BALANCE_FLOOR


def test_gt08s_frozen_figure_is_untouched_by_the_threshold():
    """B5 ❄️ GT-8 — 542.10 is twenty-one times the floor, so 8.13 stands.

    The decision log asserts this in words ("its balance is far above the
    threshold"); here it bites. A floor raised above 542.10 by a later change
    would zero the frozen figure, and this goes red before the golden suite
    does.
    """
    assert GT8_OVERDUE > late_fee.LATE_FEE_BALANCE_FLOOR
    assert fee(GT8_OVERDUE) == Decimal("8.13")


def test_the_threshold_never_touches_the_collection_ladder():
    """OQ-137's ladder half is OPEN — nothing here may decide it.

    Asserted as an absence: this module exposes exactly one threshold and it is
    read by the FEE. A ladder constant appearing here would be an implementer
    answering the half of the question the PO did not rule on.
    """
    thresholds = [name for name in dir(late_fee) if "FLOOR" in name or "THRESHOLD" in name]
    assert thresholds == ["LATE_FEE_BALANCE_FLOOR"]
    assert "ladder" not in late_fee.assess_late_fee.__doc__.lower()


# ══════════════════════════════════════════════════════════════════════════
# RULING B — lateness is the ACTUAL arrival date (OQ-131)
# ══════════════════════════════════════════════════════════════════════════
def test_lateness_is_the_actual_arrival_date_not_the_import_date():
    """The PO's worked case, to the day, and the outcome it reverses.

    Banked 20 Aug · due 22 Aug · imported 25 Aug · run 5 Sep. The money was in
    the bank two days early, so nothing is overdue and no fee is charged. An
    import-date reading makes the customer three days late.
    """
    receipt = late_fee.PaymentReceipt(
        amount=BILL_TOTAL,
        arrived_on=MONEY_IN_THE_BANK,  # 20 Aug — the ACTUAL date
        recorded_on=FILE_IMPORTED,  # 25 Aug — the import, never consulted
    )
    overdue = services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(receipt,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    )
    assert overdue == Decimal("0.00"), (
        "money in the bank on 20 Aug against a bill due 22 Aug is NOT overdue — "
        "the import date (25 Aug) must not decide this"
    )
    assert fee(overdue, due=BILL_DUE, as_of=BILL_RUN) == Decimal("0.00")

    # THE REJECTED READING, stated so the ruling's effect is visible: had the
    # money genuinely not arrived until the file was imported, the same bill IS
    # overdue and DOES attract a fee. The two readings differ by a real charge.
    arrived_late = late_fee.PaymentReceipt(
        amount=BILL_TOTAL, arrived_on=FILE_IMPORTED, recorded_on=FILE_IMPORTED
    )
    still_owed = services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(arrived_late,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    )
    assert still_owed == Decimal("117.01")
    assert fee(still_owed, due=BILL_DUE, as_of=BILL_RUN) == Decimal("5.00")


def test_only_the_records_that_existed_when_the_bill_was_generated_are_read():
    """The PO's first clause is a second rule: *"if record is available"*.

    A payment recorded AFTER the run is not retro-applied — it simply was not
    there when the bill was generated. This is also what makes a run replayed
    years later reach the figure it reached on the day (BR-TEN-043 from the data
    side).
    """
    recorded_after_the_run = late_fee.PaymentReceipt(
        amount=BILL_TOTAL,
        arrived_on=MONEY_IN_THE_BANK,  # arrived in time…
        recorded_on=date(2026, 9, 20),  # …but entered our system after the run
    )
    assert services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(recorded_after_the_run,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    ) == Decimal("117.01")

    # The same receipt, assessed later, IS available and IS counted.
    assert services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(recorded_after_the_run,),
        due_date=BILL_DUE,
        assessed_on=date(2026, 9, 30),
    ) == Decimal("0.00")


def test_money_that_arrives_after_the_due_date_does_not_unmake_the_lateness():
    """BR-BIL-001's base is what was PAST DUE, so a late payment is not credited.

    Stated as a rule rather than left implicit: the customer paid, the balance
    falls, and the fee they earned by being late is still earned.
    """
    late_payment = late_fee.PaymentReceipt(
        amount=BILL_TOTAL, arrived_on=date(2026, 8, 30), recorded_on=date(2026, 8, 30)
    )
    assert services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(late_payment,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    ) == Decimal("117.01")


def test_a_part_payment_leaves_the_residue_and_an_overpayment_leaves_nothing():
    """Partial arrival reduces the overdue portion; overpayment never goes negative.

    The residue case is the bridge to ruling A: $328.60 billed, $326.20 arrives
    in time, **$2.40** left — the exact figure the PO was shown, and it earns no
    fee under the $25.00 floor.
    """
    part = late_fee.PaymentReceipt(
        amount=Decimal("326.20"), arrived_on=MONEY_IN_THE_BANK, recorded_on=FILE_IMPORTED
    )
    residue = services.overdue_portion(
        amount_billed=Decimal("328.60"),
        payments=(part,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    )
    assert residue == Decimal("2.40")
    assert fee(residue, due=BILL_DUE, as_of=BILL_RUN) == Decimal("0.00")

    overpaid = late_fee.PaymentReceipt(
        amount=Decimal("400.00"), arrived_on=MONEY_IN_THE_BANK, recorded_on=FILE_IMPORTED
    )
    assert services.overdue_portion(
        amount_billed=Decimal("328.60"),
        payments=(overpaid,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    ) == Decimal("0.00")


def test_a_payment_with_no_actual_arrival_date_falls_back_to_the_recorded_date():
    """**PO ruling 2026-08-12, verbatim: _"Fall back to the recorded date"_.**

    OQ-156 CLOSED. This test asserted the REFUSAL until the ruling landed, and
    the refusal was correct: a payment still processing carries `cleared_at`
    NULL, so it has no ACTUAL date, and treating it as not-arrived, falling back
    to the posting date, or holding the assessment were all defensible and all
    moved a real fee on a real customer.

    **BR-BIL-071 IS NOT WEAKENED BY THIS, and the ordering is the proof.** Where
    an arrival date EXISTS it still decides lateness and the posting date still
    never does — every other case in this file asserts exactly that and is
    untouched. The fallback reaches only the case the ruling of 2026-08-11 was
    silent about.
    """
    # The PO's own worked case: entered 20 Aug against a bill due 22 Aug, still
    # clearing so it carries no banked date. The fallback reads 20 Aug → paid in
    # time → nothing overdue. The rejected reading would charge a customer who
    # paid two days early for our bank's processing time.
    in_flight = late_fee.PaymentReceipt(
        amount=BILL_TOTAL, arrived_on=None, recorded_on=MONEY_IN_THE_BANK
    )
    assert services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(in_flight,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    ) == Decimal("0.00")

    # The fallback does NOT forgive a genuinely late record. Entered 25 Aug with
    # no banked date reads as 25 Aug, which is after the 22nd — still overdue.
    entered_late = late_fee.PaymentReceipt(
        amount=BILL_TOTAL, arrived_on=None, recorded_on=FILE_IMPORTED
    )
    assert (
        services.overdue_portion(
            amount_billed=BILL_TOTAL,
            payments=(entered_late,),
            due_date=BILL_DUE,
            assessed_on=BILL_RUN,
        )
        == BILL_TOTAL
    )


def test_the_import_date_is_carried_and_never_consulted_for_lateness():
    """The rejected reading is a FIELD, and this asserts it stays unused.

    `recorded_on` exists so the ruling can be proved rather than described. It
    decides availability and nothing else: moving the import date anywhere at or
    before the run cannot change the answer, where moving the arrival date by
    one day does.
    """
    answers = {
        services.overdue_portion(
            amount_billed=BILL_TOTAL,
            payments=(
                late_fee.PaymentReceipt(
                    amount=BILL_TOTAL, arrived_on=MONEY_IN_THE_BANK, recorded_on=imported
                ),
            ),
            due_date=BILL_DUE,
            assessed_on=BILL_RUN,
        )
        for imported in (MONEY_IN_THE_BANK, FILE_IMPORTED, date(2026, 9, 5))
    }
    assert answers == {Decimal("0.00")}

    # One day later on the ARRIVAL date and the answer changes — the boundary is
    # the due date, and it is the arrival that is tested against it.
    one_day_late = late_fee.PaymentReceipt(
        amount=BILL_TOTAL, arrived_on=date(2026, 8, 23), recorded_on=MONEY_IN_THE_BANK
    )
    assert services.overdue_portion(
        amount_billed=BILL_TOTAL,
        payments=(one_day_late,),
        due_date=BILL_DUE,
        assessed_on=BILL_RUN,
    ) == Decimal("117.01")


def test_the_overdue_portion_reads_no_clock_and_no_table():
    """BR-TEN-043 and B1, asserted as absences.

    Every date is an argument and the payment records are an argument. A
    function that read a clock could not reproduce a 2026 run in 2031, and one
    that queried `payments` would be billing reaching into another module's
    tables (B1) — and would behave differently in a preview than in the run it
    previews.
    """
    import inspect

    source = inspect.getsource(late_fee.overdue_portion)
    assert "today" not in source.lower()
    assert "now(" not in source.lower()
    assert "objects" not in source

    parameters = set(inspect.signature(late_fee.overdue_portion).parameters)
    assert parameters == {"amount_billed", "payments", "due_date", "assessed_on"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — the same packet
#         apps/billing/late_fee.py carries, because this file asserts that
#         module's rulings and nothing else)
# generated: 2026-08-11 by Eng-Lead (late-fee rulings lane — the PO's OQ-131 and OQ-137 decisions of 2026-08-11)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · both rulings RED-PROVED before being trusted green — the
#         measured failures are quoted verbatim in the trailer of
#         apps/billing/late_fee.py and in 12-governance/09-human-review-ledger.md
# exceptions: (1) the COLLECTION LADDER is deliberately unasserted — OQ-137's
#         ladder half is OPEN and a threshold pinned here would answer it ·
#         (2) the dates in ruling A's cases are scaffolding satisfying B5 GT-8's
#         stated condition ("past Due date beyond grace"); ruling B's dates are
#         the PO's own worked figures and ARE assertions · (3) `overdue_portion`
#         has no production caller yet (S31.2/US-BIL-002 unbuilt), so this file
#         pins the RULE and not a live bill run — pre-existing, and the same
#         limitation `assess_late_fee` has carried since it was written
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
