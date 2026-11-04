# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S8, S62
# Rules:    BR-TEN-056 as AMENDED 2026-08-16 · BR-TEN-057 · BR-TEN-061 ·
#           BR-TEN-063 · BR-TEN-065 as AMENDED 2026-08-16 · BR-RAT-015 ·
#           CLAUDE.md rule 2 (money) · rule 3 (consumption carries its unit)
# Tests:    this file
# Impacts:  —
# ───────────────────────────────────────────────────────
"""DEF-153 — the sample-data seams exist, and the fixture says what it claims.

WHAT THIS FILE IS FOR, AND WHY IT ASSERTS A FUNCTION'S EXISTENCE
------------------------------------------------------------------
DEF-153 was not a wrong figure. It was eight documented seams that NOTHING
IMPLEMENTED: `apps/tenancy/seams.py` named `<module>.services.
seed_sample_records()`, the orchestrator resolved it, the Settings panel called
the orchestrator, and grepping every one of those modules for that function
returned ZERO. Every gate passed, because the panel reported the absence
honestly — and a brand-new tenant was empty in production.

So the first test here asserts a thing tests do not normally assert: **that the
named callable is there.** It is the exact assertion that would have gone RED
for the day the seams were unimplemented, and it is red-proved by deleting any
one of them.

The rest pin the FIGURES and the SHAPE the fixture spec rules, so a later edit
that quietly changes what a seeded tenant looks like fails here rather than
being noticed by a Product Owner six screens in.
"""

from datetime import date
from decimal import Decimal

import pytest

from core import sample_fixture as fixture

pytestmark = pytest.mark.django_db(transaction=False)


# ══════════════════════════════════════════════════════════════════════════
# DEF-153 itself: the seams are IMPLEMENTED, not merely documented
# ══════════════════════════════════════════════════════════════════════════

SEAMS = (
    # identity joined the set 2026-08-17 — CR-010 new mandate 1's two sample
    # staff users ("along with member login i will create 2 new sample users").
    ("apps.identity.services", "seed_sample_records"),
    ("apps.rating.services", "seed_sample_records"),
    ("apps.metering.services", "seed_sample_records"),
    ("apps.metering.services", "seed_sample_reads"),
    ("apps.assets.services", "seed_sample_records"),
    ("apps.customers.services", "seed_sample_records"),
    # CR-010 Part-10.4 amendment 3 — the live payment plan and its money.
    ("apps.customers.services", "seed_sample_payment_plans"),
    ("apps.billing.services", "seed_sample_records"),
    ("apps.payments.services", "seed_sample_records"),
    ("apps.payments.services", "seed_sample_plan_payments"),
)

REMOVAL_SEAMS = tuple(
    dict.fromkeys((module, "remove_sample_records") for module, _ in SEAMS)
)


@pytest.mark.parametrize(("module_path", "name"), SEAMS + REMOVAL_SEAMS)
def test_def_153_every_documented_sample_seam_resolves(module_path, name):
    """THE DEF-153 ASSERTION. Deleting any one of these turns this test RED.

    `apps/tenancy/seams.py` documents each of these paths and
    `apps/tenancy/sample_data.py` resolves them by name at call time. For one
    day every one of them was documented and absent, the Sample data panel
    reported that honestly, and no gate could tell the difference between
    "reported honestly" and "works".
    """
    from importlib import import_module

    module = import_module(module_path)
    resolved = getattr(module, name, None)
    assert callable(resolved), (
        f"{module_path}.{name} is documented in apps/tenancy/seams.py and is not "
        "published. That is DEF-153: the orchestrator and the Settings panel both "
        "exist, so the load reports an honest zero and a brand-new tenant stays empty."
    )


def test_the_orchestrator_resolves_every_block_it_declares():
    """`SAMPLE_MODULES` and the published seams cannot drift apart.

    ⚠ **THIS IS THE GUARD THAT WOULD HAVE CAUGHT DEF-930, AND IT WAS NOT RUN.**
    On 2026-08-27 both CR-040 wave-D blocks shipped published only in their
    module's `sample_data.py`. `seams.resolve` imports `apps.<module>.SERVICES`
    and getattrs the name there — it never looks in `sample_data.py` — so both
    returned None, the orchestrator recorded them as `seam_not_wired`, and the
    load reported a healthy tenant with the two fixture cases missing from it.
    **This test was already in the tree and already correct.** The lane found
    the fault through a slower route (a wave-D test counting the rows the block
    should have written) because it ran its own new file first. Recorded here
    rather than in a defect row about a missing gate: the gate was not missing.

    ⚠ **THE NON-VACUITY FLOOR IS NEW, AND IT IS THE ONE THING THIS DID LACK.**
    A bare `for` over an empty tuple asserts nothing, so a `SAMPLE_MODULES`
    that had lost most of itself would pass here in silence — the shape DEF-466
    and DEF-828 both record. The floor is a FLOOR, not the exact count: adding
    a block is ordinary work and must not have to edit a number here, while
    losing most of them must not be silent.
    """
    from apps.tenancy import sample_data, seams

    assert len(sample_data.SAMPLE_MODULES) >= 13, (
        f"only {len(sample_data.SAMPLE_MODULES)} sample blocks are declared — the loop below "
        "would be passing over a fixture that had lost most of itself"
    )
    for spec in sample_data.SAMPLE_MODULES:
        assert seams.resolve(spec.module, spec.seam) is not None, (
            f"{spec.label}: apps.{spec.module}.services.{spec.seam} is declared in "
            "SAMPLE_MODULES and does not resolve, so `seed_sample_data` will SKIP it and "
            "report a healthy tenant without whatever it was for (DEF-930)"
        )


# ══════════════════════════════════════════════════════════════════════════
# The frozen money figure the fixture reproduces (B5 GT-17 ❄️ = WE-1)
# ══════════════════════════════════════════════════════════════════════════


def test_the_reference_account_consumes_the_frozen_eight_kgal():
    """GT-17's own consumption, so one seeded bill stands on a frozen figure.

    Unit 0 uses exactly 8 kgal in every period. Against the seeded tiers that
    is 5 × $4.00 = $20.00 and 3 × $6.50 = $19.50 — and **sewer is 90% of the 8
    kgal itself, 7.2 kgal at $5.0000 = $36.00** (`CR-081`, PO re-sign
    2026-09-08). It was *"40% of the $39.50 usage basis = $15.80, deliberately
    NOT counting the $8.00 base, which would give $19.00"* until that date.
    """
    for period in ("june", "july", "august"):
        assert fixture.water_consumption_kgal(fixture.CASE_REFERENCE_BILL, period) == Decimal("8")

    tier1, tier2, tier3 = fixture.WATER_TIERS
    assert (tier1[0], tier1[1], tier1[2]) == ("0", "5", "4.00")
    assert (tier2[0], tier2[1], tier2[2]) == ("5", "15", "6.50")
    assert (tier3[0], tier3[1], tier3[2]) == ("15", None, "8.00")

    usage = Decimal("5") * Decimal("4.00") + Decimal("3") * Decimal("6.50")
    assert usage == Decimal("39.50")

    # ⚠ **`CR-081`, 2026-09-08 — THIS BLOCK ASSERTED `$15.80` AND ITS `$39.50`
    # DOLLAR BASIS UNTIL THAT DATE**, with the message *"the ratified sewer
    # figure is $15.80 on $39.50"* and a counter-assertion that including the
    # $8.00 water base would give $19.00. Both were true and are SUPERSEDED by a
    # later signature from the same authority (HUMAN-GUIDE §6 re-sign, PO
    # verbatim: *"C — factor 90%, rate $5.00 → $36.00, which is what a real
    # sewer customer actually pays"*). The water dollars above are still
    # asserted, because the water lines did not move; what moved is that they
    # are no longer sewer's basis.
    sewer_quantity = Decimal("8") * Decimal(fixture.SEWER_PERCENT_OF_WATER) / Decimal("100")
    assert sewer_quantity == Decimal("7.2")
    sewer = (sewer_quantity * Decimal(fixture.SEWER_RATE_PER_UNIT)).quantize(Decimal("0.01"))
    assert sewer == Decimal("36.00"), (
        "the re-signed sewer figure is $36.00 — 90% of 8 kgal at $5.0000. If this fails "
        "the fixture has drifted off a signed number, and BR-RAT-1015 / GT-17 are FROZEN "
        "— the fixture changes, never the law."
    )
    # THE BASIS IS THE VOLUME AND NOT ANY MONEY ON THE BILL: neither the water
    # usage dollars nor the water base can reach this line. Stated as the two
    # figures they WOULD produce, which is what the old exclusion test did.
    assert sewer != (usage * Decimal("0.90")).quantize(Decimal("0.01"))  # 35.55
    assert sewer != ((usage + Decimal(fixture.WATER_BASE)) * Decimal("0.90")).quantize(
        Decimal("0.01")
    )  # 42.75


def test_every_seeded_money_figure_is_a_string_not_a_float():
    """CLAUDE.md rule 2 — `NUMERIC(18,6)`, never float. A float literal in the
    fixture would reach a money column through the services and round wrong
    somewhere nobody is looking."""
    money = [
        fixture.WATER_BASE,
        fixture.TRASH_FLAT,
        fixture.SEWER_PERCENT_OF_WATER,
        fixture.SEWER_RATE_PER_UNIT,  # CR-081 — sewer's own rate is money too
        fixture.COMMERCIAL_WATER_FLAT,
        fixture.COMMERCIAL_WATER_BASE,
        *[price for _lo, _hi, price in fixture.WATER_TIERS],
        # DEF-463 — the draft schedule's tiers are money too, and they are
        # DERIVED, so a float creeping into the uplift would land here.
        *[price for _lo, _hi, price in fixture.WATER_2027_FILING_TIERS],
        *[entry["rate"] for entry in fixture.TAX_AUTHORITIES],
    ]
    for value in money:
        assert isinstance(value, str), f"{value!r} is not a string — rule 2"
        Decimal(value)  # parses exactly


def test_consumption_carries_its_unit():
    """CLAUDE.md rule 3 — water is kgal, and the fixture says so once."""
    assert fixture.WATER_UOM == "kgal"


# ══════════════════════════════════════════════════════════════════════════
# The shape the fixture spec rules
# ══════════════════════════════════════════════════════════════════════════


def test_the_headline_counts_are_what_the_spec_asks_for():
    """48 accounts · 44 premises — spec §2 and acceptance item 2."""
    premises = fixture.premises_plan()
    units = fixture.units_flat()
    assert len(premises) == fixture.PREMISES_COUNT == 46
    assert len(units) == fixture.UNIT_COUNT == 50
    assert len(fixture.account_plan()) == 50
    # The three premises with no unit yet — the only way both counts hold.
    assert sum(1 for row in premises if not row["units"]) == 3


def test_five_named_streets():
    """Spec §2 — named, so the premises list is navigable."""
    assert len(fixture.STREETS) == 5
    used = {row["street"] for row in fixture.premises_plan()}
    assert used == set(fixture.STREETS)


def test_one_water_meter_per_unit_plus_the_replacement():
    """The 2026-08-16 amendment: 48 water meters, not the spec's original 96.

    A sewer line priced as 40% of the water usage charge reads no register, so
    a sewer meter would only ever produce a phantom missing read.
    """
    meters = fixture.meter_plan()
    assert len(meters) == fixture.UNIT_COUNT + 1 == 51
    assert all(meter["service"] == "water" for meter in meters)
    assert all(meter["uom"] == fixture.WATER_UOM for meter in meters)
    replacements = [meter for meter in meters if meter.get("replaces")]
    assert len(replacements) == 1
    assert replacements[0]["unit_index"] == fixture.CASE_METER_REPLACED


def test_two_cycles_billed_and_the_third_left_for_the_product_owner():
    """⚠ THE ACCEPTANCE TEST ITSELF — REVERSED AGAIN 2026-08-27 (CR-040 C9).

    This test has now moved with the ruling **three times**, and the history is
    kept in the name and here rather than rewritten each time, because the shape
    of the fixture is the thing the PO keeps deciding:

      · 2026-08-16 — June AND July billed.
      · 2026-08-17 — CR-010 Part-10.4, PO verbatim *"do 1 month billed na dkeep
        other month ready"*. June alone; the test was renamed
        `test_one_month_billed_and_the_next_ready_to_run` and pinned
        `july.billed is False` with the message *"July is READY-TO-RUN"*.
      · 2026-08-27 — CR-040, PO verbatim *"I want you to complete 2 billing
        cycle and create data for 3rd billing cycle"*. Two billed, the third
        staged.

    ⚠ **THE INVARIANT THAT SURVIVED ALL THREE IS THE ONE WORTH ASSERTING, and
    it is the last two lines of this test:** the LAST declared period is never
    billed. *"everything done leaves nothing to evaluate"* was the reason in
    2026-08-17's ruling and it is still the reason — what changed is which month
    is last in the queue, not that one is. Anyone who "finishes the job" by
    billing August is still deleting the PO's acceptance test.
    """
    by_key = {period["key"]: period for period in fixture.PERIODS}
    assert by_key["june"]["billed"] is True
    assert by_key["july"]["billed"] is True, "July is billed again (PO 2026-08-27)"
    assert by_key["july"]["bill_on"] == date(2026, 8, 2), "July's bill date mirrors June's"
    # ⚠ Billed and NOT collected, deliberately — CR-040 task C9. The PO's
    # ordering puts the money before the second run, so July's bills are days
    # old and unpaid, which is what gives the ageing report a live CURRENT
    # bucket beside June's aged one.
    assert by_key["july"]["collected_share"] == Decimal("0")

    # THE SURVIVING INVARIANT: the last period is unbilled, whatever it is.
    last = fixture.PERIODS[-1]
    assert last["billed"] is False, "the last period is the PO's own run — all three rulings"
    assert last["bill_on"] is None, "its bill date is the clerk's (BR-BIL-070)"

    from apps.billing import sample_data as billing_sample

    # AND THE TWO CYCLES ARE TWO SEAMS, not one seam billing twice — the block
    # ORDER is what CR-040 asked for and a single block cannot express it.
    first = {period["key"] for period in billing_sample._periods_to_bill()}
    second = {period["key"] for period in billing_sample._second_cycle_periods()}
    assert first == {"june"}
    assert second == {"july"}
    assert not (first & second), "a period billed by both seams would be billed twice"
    assert first | second == {
        period["key"] for period in fixture.PERIODS if period["billed"]
    }, "every billed period belongs to exactly one cycle seam"
    assert "august" not in first | second

    # Both months must be fully read, or a billed cycle is a lie.
    from apps.metering import sample_data as metering_sample

    assert len(metering_sample._rows_for(by_key["july"])) == fixture.UNIT_COUNT == 50
    assert len(metering_sample._rows_for(by_key["june"])) == fixture.UNIT_COUNT == 50


def test_the_money_blocks_run_between_the_two_billing_blocks():
    """CR-040 task C8/C10 — the ORDER is the requirement, not the contents.

    PO verbatim: *"first you will run first billing, then you will create
    payment record, refunds, credit over charges records, add meter reading for
    second month and then again run the billing"*.

    A refund written after both runs is a row; a refund written between them is
    a HISTORY, and only the second one changes what the next bill is issued
    against. Nothing else in the suite can see this: every block writes the same
    rows in any order, so the ordering is invisible to a test that asks what was
    written. This asks WHEN.
    """
    from apps.tenancy import sample_data as orchestrator

    order = [(spec.module, spec.seam) for spec in orchestrator.SAMPLE_MODULES]
    first_bill = order.index(("billing", "seed_sample_records"))
    money = order.index(("payments", "seed_sample_records"))
    second_bill = order.index(("billing", "seed_sample_second_cycle"))

    assert first_bill < money < second_bill, (
        "the payments block must sit BETWEEN the two billing blocks — "
        f"got billing@{first_bill}, payments@{money}, second cycle@{second_bill}"
    )


def test_each_cycles_reads_are_walked_before_that_cycle_is_billed():
    """**PO 2026-09-01 — reads, bill, reads, bill, reads (`DEF-2968`).**

    Verbatim: *"reading data when you seed first time add reading then bill it,
    then add reading data again, then bill it and then again add reading data -
    you can not add reading data once for 3 months"*.

    ⚠ **THIS IS THE ASSERTION WHOSE ABSENCE LET THE DEFECT THROUGH, AND IT IS
    WORTH SAYING WHY NOTHING ELSE COULD.** Every row, register value and read
    date is identical whether the three months are walked in one pass or in
    three, so nothing that counts rows or compares figures can tell the two
    orders apart. The suite already asserts the order of the MONEY blocks
    (`test_the_money_blocks_run_between_the_two_billing_blocks`) and asserted
    nothing about the reads, so a seeder that handed in three months on the same
    morning — before anything had been billed — was invisible.

    What is pinned: the three reads blocks PARTITION the fixture's periods, and
    each one runs before the bill run that prices what it planted.
    """
    from apps.metering import sample_data as metering_sample
    from apps.tenancy import sample_data as orchestrator

    order = [(spec.module, spec.seam) for spec in orchestrator.SAMPLE_MODULES]
    first_reads = order.index(("metering", "seed_sample_reads"))
    first_bill = order.index(("billing", "seed_sample_records"))
    second_reads = order.index(("metering", "seed_sample_second_cycle_reads"))
    second_bill = order.index(("billing", "seed_sample_second_cycle"))
    next_reads = order.index(("metering", "seed_sample_next_cycle_reads"))

    assert first_reads < first_bill < second_reads < second_bill < next_reads, (
        "the seeded tenant must be built as reads -> bill -> reads -> bill -> reads; "
        f"got reads@{first_reads}, bill@{first_bill}, reads@{second_reads}, "
        f"bill@{second_bill}, reads@{next_reads}"
    )

    # …and the three walks partition the fixture's periods: every one is planted
    # by exactly one block, so no period is walked twice or left to no block.
    walked = (
        [period["key"] for period in metering_sample._first_cycle_periods()]
        + [period["key"] for period in metering_sample._second_cycle_periods()]
        + [period["key"] for period in metering_sample._next_cycle_periods()]
    )
    assert sorted(walked) == sorted(period["key"] for period in fixture.PERIODS)
    assert len(walked) == len(set(walked)), f"a period is walked twice: {walked}"


def test_three_meters_are_deliberately_unreadable_in_august():
    """Spec §4 case 1 — so the S25 estimation screen has work to do."""
    assert len(fixture.CASE_UNREADABLE) == 3
    assert len(set(fixture.CASE_UNREADABLE)) == 3

    from apps.metering import sample_data as metering_sample

    august = [period for period in fixture.PERIODS if period["key"] == "august"][0]
    rows = metering_sample._rows_for(august)
    assert len(rows) == fixture.UNIT_COUNT - 3 == 47, (
        "the unreadable meters must be ABSENT from the batch"
    )
    absent = {
        f"W-{5000 + index:04d}" for index in fixture.CASE_UNREADABLE
    }
    assert not (absent & {row["meter_id"] for row in rows})


def test_the_landlord_holds_three_accounts_under_one_customer():
    """Spec §4 case 13 — the only thing that makes the customer screen more
    than a synonym for the account screen.

    ⚠ **TWO ACCOUNTS UNTIL 2026-09-03, THREE FROM IT (`CR-059` CS-12, task
    74).** The case itself is unchanged; what changed is that CS-12 asks the
    demo for *"one customer with three properties"* so ONE CHEQUE can be seen
    covering all of them, and a landlord with two properties cannot show a
    three-way split. Written as a loop over the whole tuple rather than as a
    wider unpack, so a fourth property would not need this test edited again.
    """
    plan = {row["unit_index"]: row for row in fixture.account_plan()}
    first, *rest = fixture.CASE_LANDLORD
    assert len(fixture.CASE_LANDLORD) == 3
    for other in rest:
        assert plan[first]["customer_key"] == plan[other]["customer_key"]
        assert plan[first]["bill_to"] == plan[other]["bill_to"]


def test_roughly_one_account_in_four_is_awkward():
    """Spec §4: *"Roughly one account in four is interesting; the rest are
    ordinary on purpose, so the interesting ones stand out."*

    MEASURED AT 42%, NOT 25%, AND THE SPEC'S OWN LIST IS WHY: §4 names fifteen
    cases, three of which are three meters and two of which are two accounts,
    so the list itself lands on 20 of 48. Dropping a case to hit "one in four"
    would remove something the spec asked for in order to satisfy a word it
    used loosely, so the band is widened and the arithmetic is written down.
    What the band still catches is the failure that matters — a fixture that
    quietly became TIDY, which *"proves nothing"*.

    ⚠ **18 → 20 ON 2026-08-27 (CR-040 wave D).** Spec §4 gained cases 14 and 15
    — one refund and one overcharge corrected — and each takes an ordinary unit
    (`CASE_REFUND` 23, `CASE_OVERCHARGE` 31). The count is restated rather than
    the band being loosened, because the count is what catches a case being
    silently DROPPED; the band alone would have absorbed either direction.
    """
    share = len(fixture.AWKWARD_UNITS) / fixture.UNIT_COUNT
    assert 0.15 <= share <= 0.45, f"{share:.0%} of accounts are awkward"
    # ⚠ **20 → 21 ON 2026-09-03 (`CR-059` CS-12, task 74).** The landlord case
    # gained a third property so the demo can show ONE CHEQUE covering three,
    # and unit 47 joins `CASE_LANDLORD` and therefore this set. **The count is
    # restated rather than the band being loosened**, for the reason the
    # docstring above already gives about the 18 → 20 move: the count is what
    # catches a case being silently DROPPED, and the band alone would have
    # absorbed either direction.
    assert len(fixture.AWKWARD_UNITS) == 21


# ══════════════════════════════════════════════════════════════════════════
# BR-TEN-065 as amended, and BR-TEN-061's order
# ══════════════════════════════════════════════════════════════════════════


def test_sample_accounts_are_seeded_active_not_pending():
    """BR-TEN-065 as AMENDED 2026-08-16.

    The 2026-08-10 rule seeded them `Pending activation`, whose behaviour class
    is `non_billable`, and said in as many words that *"the sample set therefore
    cannot demonstrate a bill run"*. That consequence is what the Product Owner
    removed: the fixture spec requires June and July BILLED.
    """
    from apps.customers import sample_data as customers_sample

    assert customers_sample.SAMPLE_ACCOUNT_STATUS == "active"


def test_removal_order_still_reverses_the_creation_order():
    """BR-TEN-061 — B2 declares no `ON DELETE CASCADE` on any of these FKs, so
    the order is not an optimisation; it is the only thing that makes the
    delete possible."""
    from apps.tenancy import sample_data

    order = sample_data.BR_TEN_061_REMOVAL_ORDER
    assert order[0] == "meter_reads"
    assert order[-1] == "premises"
    assert order.index("accounts") < order.index("units")
    assert order.index("asset_assignments") < order.index("assets")
    assert order.index("service_points") < order.index("units") < order.index("premises")


def test_the_senior_plan_is_not_seeded_and_says_why():
    """OQ-240 — no signed figure states the discount, and spec rule 7 forbids
    choosing one. The gap is NAMED rather than filled."""
    from apps.rating import sample_data as rating_sample

    assert rating_sample.NOT_SEEDED
    entry = rating_sample.NOT_SEEDED[0]
    assert "Senior" in entry["what"]
    assert entry["oq"] == "OQ-240"


def test_payments_names_what_it_did_not_seed():
    """A gap a reader can see beats a fixture that looks complete.

    ⚠ AMENDED 2026-08-17: the floor was 5 and is now 4, because the PAYMENT
    PLAN left the list — CR-010 Part-10.4 seeds it as REAL rows (customers'
    `seed_sample_payment_plans` + payments' `seed_sample_plan_payments`), and
    a NOT_SEEDED entry for a thing that IS seeded would be the inverse of
    DEF-016. The four that remain are still honestly named.

    ⚠ **AMENDED AGAIN 2026-09-23 (`DEF-PAY-6321`): THE DEPOSIT BATCHES LEFT
    THE LIST TOO, AND THE COUNT DID NOT MOVE** — the entry that named them
    named the BANK STATEMENT in the same breath, and only the batches are
    seeded now, so one entry became one entry. **That is exactly why a floor
    of four could not have caught this**, and it is the half of DEF-016's
    shape this test was never asked about: it guards against naming a gap that
    is filled, and says nothing about a gap that stands UNFILLED for five
    weeks with nothing counting it. The count for that lives in
    `test_def_pay_6321_seeded_deposit_batches.py`, on the rows; what belongs
    here is the inverse guard, so the third assertion below now names the
    batches beside the plan.
    """
    from apps.payments import sample_data as payments_sample

    assert len(payments_sample.NOT_SEEDED) >= 4
    for entry in payments_sample.NOT_SEEDED:
        assert entry["what"] and entry["reason"]
    named = " ".join(entry["what"] for entry in payments_sample.NOT_SEEDED)
    assert "payment plan" not in named.lower(), (
        "the plan is seeded since CR-010 Part-10.4 — naming it NOT_SEEDED would be false"
    )
    assert "deposit batch" not in named.lower(), (
        "the deposit batches are seeded since DEF-PAY-6321 — the busy day's cash and "
        "cheques are taken into a counter till that opens, takes the money and is "
        "sealed. Naming them NOT_SEEDED would send a reader looking for work that is "
        "done. The BANK STATEMENT is still unseeded and is still named, separately"
    )


def test_the_payment_plan_is_declared_mid_schedule():
    """CR-010 Part-10.4 amendment 3 — the plan the fixture promises is LIVE
    and mid-schedule: instalments still to fall due after the paid ones, and
    every date after the June bill it spreads."""
    plan = fixture.PAYMENT_PLAN
    assert plan["unit_index"] == fixture.CASE_PAYMENT_PLAN
    assert 0 < plan["paid_installments"] < plan["installments"], "MID-schedule, both ways"
    june = fixture.PERIODS[0]
    assert plan["proposed_on"] > june["bill_on"], "a plan spreads a bill that exists"
    assert plan["signed_on"] >= plan["proposed_on"]
    assert plan["first_due"] > plan["proposed_on"], "US-CUS-018 §5: first due after as-of"
    assert Decimal("0") < plan["down_payment_share"] < Decimal("1")


def test_sub_meters_and_btm_devices_are_declared_for_every_s49_tab():
    """CR-010 Part-10.4 amendments 1–2 (PO: *"please add sub meter and few
    bhend the meter devices"*) — the S49 register's three tabs all have rows.

    Sub-meters sit on the apartment block's six `residential_submetered`
    units, each parented on that unit's own meter (BR-AST-003) and declaring
    service + explicit UoM (BR-AST-009, CLAUDE.md rule 3). BTM devices are
    the seeded non-measuring vocabulary — backflow, pv, ev_charger — and
    declare neither.
    """
    subs = fixture.sub_meter_plan()
    apartments = fixture.apartment_unit_indexes()
    assert len(apartments) == 6, "the apartment block has six units"
    assert [row["unit_index"] for row in subs] == list(apartments)
    for row in subs:
        assert row["parent_asset_no"] == f"W-{5000 + row['unit_index']:04d}"
        assert row["service"] == "water" and row["uom"] == fixture.WATER_UOM
        assert row["asset_no"].startswith("SM-")

    devices = fixture.BTM_DEVICE_PLAN
    assert {row["type"] for row in devices} == {"backflow", "pv", "ev_charger"}
    for row in devices:
        assert "service" not in row and "uom" not in row, (
            "a non-measuring BTM device declares no service and no UoM (BR-AST-009)"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 + 08-qa/04-fixtures/02-demo-tenant-spec.md (PO-ruled 2026-08-16)
# generated: 2026-08-16 by story-coder (DEF-153 sample-data lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: these are DECLARATION and RESOLUTION tests — they assert that every documented seam is published (the DEF-153 assertion, red-proved by deleting one) and that the fixture's figures and shape match the PO-ruled spec. The end-to-end LOAD is proved on a booted stack rather than here: it provisions a tenant, drives six modules' services and issues bills, which is a stack test and not a unit one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── DEF-463 · the seed writes a DRAFT schedule, not only actives ───────────


def test_def_463__the_2027_filing_tiers_are_the_stated_uplift_of_the_in_force_ones():
    """DERIVED, never retyped, and this is what makes the derivation checkable.

    The fixture states a `1.125` uplift; these are `WATER_TIERS` scaled by it and
    rounded to the cent. When the earlier version history was typed by hand it
    carried `7.31` where the arithmetic gives `7.30` and nothing caught it for
    weeks — a fixture that disagrees with its own stated uplift is a worked
    example nobody can check.
    """
    from decimal import ROUND_HALF_UP, Decimal

    scale = Decimal(fixture.WATER_V3_UPLIFT)
    for (lo, hi, base), (flo, fhi, filed) in zip(
        fixture.WATER_TIERS, fixture.WATER_2027_FILING_TIERS
    ):
        # The BANDS are untouched — a filing raises prices; moving the
        # boundaries would be a different change and would make any comparison
        # against the in-force version meaningless.
        assert (flo, fhi) == (lo, hi)
        expected = (Decimal(base) * scale).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert Decimal(filed) == expected
    # The ratified figures, stated so a reader does not have to run the sum.
    assert [price for _lo, _hi, price in fixture.WATER_2027_FILING_TIERS] == [
        "4.50",
        "7.31",
        "9.00",
    ]


def test_def_463__the_draft_schedule_carries_no_effective_date():
    """The whole mechanism, asserted where a lane would break it.

    `create_rate_schedule` reads an ABSENT `effective_from` as "Save draft &
    exit" and lands a version with a NULL effective date; `schedule_state` then
    derives `draft`, because nothing is in force. Giving this payload a date —
    the obvious "fix" for a row that looks incomplete — would make it a fourth
    ACTIVE schedule and seed nothing new.
    """
    from apps.rating import sample_data
    from core import sample_fixture as fixture

    # `_schedule_payloads` builds the estate THIS TENANT can be given, and this
    # test is about the payload's SHAPE rather than about which utility it is —
    # so the estate is stated rather than a tenant being built, which would make
    # a fixture-shape test depend on provisioning.
    #
    # ⚠ AMENDED FOR `DEF-2397`: this stubbed `sample_data._enabled` and returned
    # True for every service, because the three water payloads were gated on
    # `_enabled("water")`. They are gated on the ESTATE now — one backbone per
    # tenant, resolved by `core.sample_fixture.estate_plan` the same way
    # metering and assets resolve it — so the thing to state is the estate. The
    # ASSERTIONS below are untouched: this is the same question asked through
    # the seam that now answers it.
    original = sample_data.estate
    sample_data.estate = lambda: fixture.estate_plan(
        ["water", "sewer", "trash"], {"water": fixture.WATER_UOM}
    )
    try:
        payloads = {row["name"]: row for row in sample_data._schedule_payloads()}
    finally:
        sample_data.estate = original
    filing = payloads.get(sample_data.SCHEDULE_WATER_FILING)
    assert filing is not None, "the draft schedule is not in the seed"
    assert "effective_from" not in filing
    # And it is a real thing to open: a draft nobody could resume would not
    # exercise BR-RAT-031's resume view, which is what the row exists to show.
    assert filing["structure"]["tiers"], "the draft has no structure to resume"
    # Every OTHER seeded schedule still states its date — this is the one
    # deliberate absence, not a pattern.
    dated = [name for name, row in payloads.items() if "effective_from" in row]
    assert len(dated) == len(payloads) - 1
