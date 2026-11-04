# ── Trace ──────────────────────────────────────────────
# Defects: DEF-498 (R4 cannot express a percent or a per-case amount, so five
#          provisioned codes refuse the whole bill by name) · DEF-493 (R4
#          narrows by service, class and size and by nothing else, so a flipped
#          R4 bills the whole price list) · DEF-2340 (a per-case code and an
#          unpriced code are the same stored row) · DEF-2341 (the shadow's
#          hand-written copy of the refusal->step map cannot see a new class)
# Rules:   BR-RAT-730 (the two ways a charge code reaches an ordinary periodic
#          bill) · BR-RAT-117 (recurring AND auto_apply, PO 2026-08-22) ·
#          BR-RAT-088 (the charge code owns the base) · BR-RAT-041 (`formula` is
#          visible-but-disabled) · BR-BIL-001 (max($5, 1.5% x overdue))
# Rulings: PO 2026-08-22 *"ruccuring and Autom apply land on bill"* · PO
#          2026-08-17 CR-010 A2 (`per_case` is RATIFIED AS UNPRICED)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""THE TWO REASONS R4 COULD NOT BE SWITCHED ON, AND THE PROOF THEY ARE CLOSED.

They are ONE job. The decision log, 2026-08-27: *"fixing either alone turns a
refusal into an overcharge. They ship together or not at all."*

  * `DEF-498` — the CONTRACT gap. `resolution.ChargeCode` could express a flat
    amount and a per-size table while `charges.amount_rule` has stored four
    rules since r6.6, so a percent code, a per-case code and a formula code all
    arrived as `flat_amount=None, amounts={}` and were refused with one sentence
    blaming the CONNECTION SIZE. Five provisioned codes, every bill, every real
    tenant.
  * `DEF-493` — the NARROWING gap. R4 read neither `charges.charge_type` nor
    `charges.auto_apply`, so a `$45.00` one-off connection fee and a `$2.00`
    recurring paper-bill fee were the same object to it.

⚠ **NO BILL CHANGES AND NOTHING IS SWITCHED ON.** R4 still has no production
caller; `test_br_rat_120_size_refusal.py::TC6` is the assertion that says so and
this file does not weaken it. What changed is what R4 WOULD do when step 5 of
the cutover reaches it.

⚠ **NOTHING HERE MOVES A FROZEN FIGURE.** `charge_type` and `auto_apply` are not
money columns, `golden-verify` reads 33 PASS / 0 FAIL either side of this
change, and no B5 fixture configures an auto-applied charge code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import resolution as R
from apps.rating import resolution_catalogue

from tests.seeded_charge_codes import seeded_priced_total
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

RES = R.AccountFacts(account_no="A-1", unit_id="u-1", customer_class="residential")


def _rides(**kwargs) -> R.ChargeCode:
    """A code the utility has declared rides an ordinary periodic bill."""
    return R.ChargeCode(charge_type="recurring", auto_apply=True, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# DEF-498 — R4 can now SAY what is in the way, rule by rule
# ══════════════════════════════════════════════════════════════════════════


def test_tc1_a_percent_code_refuses_naming_the_percentage_not_the_connection_size():
    """`LATE` is `percent_with_minimum` 1.5% / $5.00 — BR-BIL-001's
    *max($5, 1.5% x overdue)*. It is an account-level code, so `code.service` is
    None and `sizes.get(None or "")` is None **for every account that has ever
    existed**: the old refusal was unconditional AND it named a fact that has
    nothing to do with the problem.

    R1-R7 takes frozen RATING facts. An overdue balance is a BILLING fact, so
    the chain still cannot price this code — **and that is the correct answer**,
    not a gap. What it may not do is blame a meter for it.
    """
    late = _rides(
        code="LATE",
        amount_rule="percent_with_minimum",
        percent=Decimal("0.015000"),
        min_amount=Decimal("5.000000"),
    )
    with pytest.raises(R.ChargeCodeAmountMissing) as refusal:
        R.charge_code_amount(late, None)
    sentence = str(refusal.value)
    assert "percent_with_minimum" in sentence
    assert "0.015000" in sentence
    assert "is handed no balance" in sentence
    assert "connection size" not in sentence, (
        "DEF-498 reopening: the refusal is naming the connection size again, "
        f"which is not what is wrong with a percentage code — {sentence}"
    )


def test_tc2_a_plain_percent_code_refuses_the_same_way():
    """`percent` and `percent_with_minimum` are one class of problem, so they
    are one branch. Asserted separately because a fix that special-cased the
    minimum would pass TC1 and leave this one blaming a meter."""
    with pytest.raises(R.ChargeCodeAmountMissing) as refusal:
        R.charge_code_amount(
            _rides(code="SURCHG", amount_rule="percent", percent=Decimal("0.020000")), "5/8"
        )
    assert "is handed no balance" in str(refusal.value)


def test_tc3_a_formula_code_refuses_naming_BR_RAT_041():
    """`formula` is BR-RAT-041's reserved value — *visible-but-disabled*. No
    version of this product evaluates one, so there is no amount to state and
    the refusal says which rule reserved it."""
    with pytest.raises(R.ChargeCodeAmountMissing) as refusal:
        R.charge_code_amount(_rides(code="CUSTOM", amount_rule="formula"), "5/8")
    assert "formula" in str(refusal.value)
    assert "BR-RAT-041" in str(refusal.value)


def test_tc4_a_code_with_no_rule_and_no_amount_refuses_claiming_NEITHER_reading():
    """`DEF-2340` — **two different facts the database cannot tell apart.**

    A code the PO RULED unpriced (CR-010 A2, 2026-08-17: *"actual cost, entered
    per case"* — `TAP`, `IMPACT`, `DAMAGE`, `BULK-WATER`) and a code nobody has
    priced both store `amount_rule = NULL` with no amount. `service_size_classes
    .py`'s own docstring is the standing law on this shape: *"an empty tuple
    means 'ruled to have none' and a raise means 'nobody has said' … the two
    readings must never collapse."*

    They HAVE collapsed here, on a column that does not exist. So the refusal
    states both readings and asserts neither, which is the only honest sentence
    available until `DEF-2340` gives per-case a column of its own.
    """
    with pytest.raises(R.ChargeCodeAmountMissing) as refusal:
        R.charge_code_amount(_rides(code="TAP"), "5/8")
    sentence = str(refusal.value)
    assert "per case" in sentence
    assert "nobody has priced it" in sentence
    assert "the product does not record which" in sentence


def test_tc5_the_flat_and_per_size_refusals_are_untouched():
    """The two refusals R4 already made must still fire, and for their own
    reasons — a fix that widened the amount branch could swallow either."""
    with pytest.raises(R.ChargeCodeAmountMissing) as both:
        R.charge_code_amount(
            _rides(
                code="BASE-W",
                service="water",
                amount_rule="flat",
                flat_amount=Decimal("12.0000"),
                amounts={"5/8": Decimal("12.0000")},
            ),
            "5/8",
        )
    assert "states BOTH a flat amount and a per-size table" in str(both.value)

    with pytest.raises(R.ChargeCodeAmountMissing) as size:
        R.charge_code_amount(
            _rides(code="FIRE", service="water", amounts={"4": Decimal("14.0000")}), "5/8"
        )
    assert "no amount for connection size" in str(size.value)


def test_tc6_a_flat_code_still_prices_to_the_cent():
    """The rule dispatch must not disturb the case that already worked."""
    code = _rides(code="PAPER", amount_rule="flat", flat_amount=Decimal("2.0000"))
    assert R.charge_code_amount(code, "5/8") == Decimal("2.0000")


# ══════════════════════════════════════════════════════════════════════════
# DEF-493 — the fourth narrowing axis (BR-RAT-730)
# ══════════════════════════════════════════════════════════════════════════


def test_tc7_both_flags_ride_and_either_alone_does_not():
    """`BR-RAT-117`, PO verbatim 2026-08-22: *"ruccuring and Autom apply land on
    bill"*. **The conjunction is the rule.**"""
    both = _rides(code="PAPER", amount_rule="flat", flat_amount=Decimal("2.0000"))
    recurring_only = R.ChargeCode(
        code="HYDRANT",
        charge_type="recurring",
        auto_apply=False,
        amount_rule="flat",
        flat_amount=Decimal("50.0000"),
    )
    catalogue = R.Catalogue(charge_codes=(both, recurring_only))
    resolved = R.resolve_charge_codes(catalogue, RES, ("water",), {"water": "5/8"})
    assert [code.code for code, _amount in resolved] == ["PAPER"]


def test_tc8_a_one_time_code_is_NOT_SELECTED_and_is_not_an_error():
    """**Not riding is not a refusal.** 18 of the 23 codes a tenant is
    provisioned with are `one_time`; refusing them would stop every bill on
    every tenant, which is the failure mode `BR-RAT-120` warned about in the
    same week (*"switching first would refuse every bill"*)."""
    catalogue = R.Catalogue(
        charge_codes=(
            R.ChargeCode(
                code="CONN",
                charge_type="one_time",
                amount_rule="flat",
                flat_amount=Decimal("45.0000"),
            ),
        )
    )
    assert R.resolve_charge_codes(catalogue, RES, ("water",), {"water": "5/8"}) == ()


def test_tc8b_THE_ORDER_IS_LOAD_BEARING_an_unpriced_one_time_code_never_reaches_the_amount():
    """⚠ **THIS IS WHERE THE TWO DEFECTS MEET, AND WHY THEY ARE ONE JOB.**

    `TAP`, `IMPACT`, `DAMAGE` and `BULK-WATER` are `one_time` codes that state
    NO amount. Ask *what does it cost* first and every one of them refuses the
    whole bill — `DEF-498` — for a code that was never going to appear on it.
    Ask *does it ride* first and they are simply not selected.

    TC8 cannot see this: its `CONN` states `$45.00`, so the amount step succeeds
    either way and the ordering is invisible to it. This one has no amount, so
    reversing the two steps turns a clean bill into a refusal.
    """
    catalogue = R.Catalogue(charge_codes=(R.ChargeCode(code="TAP", charge_type="one_time"),))
    assert R.resolve_charge_codes(catalogue, RES, ("water",), {"water": "5/8"}) == ()


def test_tc9_an_UNSTATED_charge_type_does_not_ride_and_is_not_read_as_recurring():
    """`charges.charge_type` is nullable. An unstated type is a fact about the
    configuration, **not a licence to guess** — the chain's standing posture, and
    the safe direction: not billing a fee is fixed by ticking a box, billing one
    that was never declared is a credit note under hard rule 4."""
    catalogue = R.Catalogue(
        charge_codes=(
            R.ChargeCode(
                code="MYSTERY", charge_type=None, amount_rule="flat", flat_amount=Decimal("9.0000")
            ),
        )
    )
    assert R.resolve_charge_codes(catalogue, RES, ("water",), {"water": "5/8"}) == ()


def test_tc10_auto_apply_on_a_NON_recurring_code_is_a_CONFLICT_and_refuses_by_name():
    """Two columns a person filled in that contradict each other. `one_time`
    says *fire on an event*; `auto_apply` says *fire on every bill*. Reading
    either as authoritative discards the other answer — a `$250.00` tamper fee
    on one bill or on twelve — so the chain says so and stops."""
    for charge_type in ("one_time", "penalty", "refundable", None):
        code = R.ChargeCode(
            code="TAMPER",
            charge_type=charge_type,
            auto_apply=True,
            amount_rule="flat",
            flat_amount=Decimal("250.0000"),
        )
        with pytest.raises(R.ChargeCodeRecurrenceConflict) as refusal:
            R.resolve_charge_codes(R.Catalogue(charge_codes=(code,)), RES, ("water",), {})
        assert "auto-apply" in str(refusal.value)
        assert repr(charge_type) in str(refusal.value)


def test_tc11_A_BASE_CODE_RIDES_WITHOUT_THE_FLAGS_AND_THIS_IS_THE_8_DOLLAR_ROW():
    """⚠ **THE ROW THAT WOULD HAVE BILLED `$0.00` FOR BASE ON EVERY SEEDED
    TENANT.**

    `resolve_base_charge` reads R4's OUTPUT, so a base code that does not
    survive the narrowing is a base that does not exist. The seeder's `BASE-W`,
    `BASE-W-COM`, `BASE-S` and `BASE-T` are `charge_type='recurring'` with
    `auto_apply` **unset** — gating them on both flags takes `$8.00` residential
    water, `$15.00` commercial water and `$18.00` trash to `$0.00`.

    That is `DEF-154` exactly: the base sourced from the wrong column, billing
    `$0.00` for weeks, *"invisible because the arithmetic over it was right and
    the SOURCING was wrong."* `BR-RAT-117` forbids it in terms — *"⚠ THIS DOES
    NOT MOVE THE BASE."*
    """
    base = R.ChargeCode(
        code="BASE-W",
        service="water",
        is_base=True,
        charge_type="recurring",
        auto_apply=False,  # exactly as `seed_demo.CHARGE_CODES` writes it
        amount_rule="flat",
        flat_amount=Decimal("8.0000"),
    )
    resolved = R.resolve_charge_codes(
        R.Catalogue(charge_codes=(base,)), RES, ("water",), {"water": "5/8"}
    )
    assert [(code.code, amount) for code, amount in resolved] == [("BASE-W", Decimal("8.0000"))]
    assert R.resolve_base_charge(resolved, "water", "BASE-W") == Decimal("8.0000")  # DEF-RAT-9832: named


def test_tc12_the_seeder_s_own_base_rows_are_the_shape_tc11_protects():
    """TC11 asserts the RULE on a hand-built code, which is the shape whose
    escape reason `DEF-498` records (*"a hand-built code always states an amount
    because the author is thinking about the case under test"*). This asserts
    the same thing about the rows the product actually ships, so the two cannot
    drift."""
    from apps.tenancy.management.commands import seed_demo

    bases = [row for row in seed_demo.CHARGE_CODES if row.get("is_base")]
    assert bases, "the seeder declares no base charge code (DEF-455 reopening)"
    for row in bases:
        assert row.get("charge_type") == "recurring", row["code"]
        assert not row.get("auto_apply"), (
            f"{row['code']} is auto-apply; TC11's exemption is what carries a base "
            "onto a bill and this row no longer tests it"
        )


# ══════════════════════════════════════════════════════════════════════════
# The two figures, measured on a provisioned tenant — the deliverable
# ══════════════════════════════════════════════════════════════════════════


def test_tc13_ON_A_PROVISIONED_TENANT_none_of_23_refuses_and_none_of_18_rides(brazos, dana):
    """**BOTH NUMBERS, OFF THE SAME ROWS, IN ONE ASSERTION EACH.**

    Before: **5 of 23 codes refused the whole bill by name**, and the other
    **18, totalling `$829.95`, would have ridden a bill whose base is `$8.00`.**

    ⚠ **THAT TOTAL READ `$799.95` UNTIL 2026-09-27 (`DEF-RAT-6980`).** It was
    measured correctly and then the PO repriced one of the eighteen:
    `OQ-CUS-12518`, CLOSED 2026-09-21, verbatim *"reconnection fee is $75 -
    fix the code and seed"*, over `BR-CUS-104` which they had already SIGNED on
    `$75.00` on 2026-08-25. `RECON` went `$45.00` → `$75.00`; `$829.95 -
    $799.95 = $30.00` is that and nothing else, and the count is 18 on both
    sides. **The data was right and this number was stale** — it is no longer a
    constant, so the next repricing cannot make this red.
    After: **0 refuse and 0 ride.**

    The catalogue is unchanged — the same five codes still state no amount. What
    changed is that R4 asks *does this ride* before it asks *what does it cost*.
    """
    with tenant_ctx(brazos):
        catalogue = resolution_catalogue.charge_code_facts()
        assert len(catalogue) == 23, len(catalogue)

        unpriced = [code for code in catalogue if code.flat_amount is None and not code.amounts]
        assert sorted(code.code for code in unpriced) == [
            "BULK-WATER",
            "DAMAGE",
            "IMPACT",
            "LATE",
            "TAP",
        ]
        priced = [code for code in catalogue if code.flat_amount is not None]
        assert len(priced) == 18
        # DEF-RAT-6980 — summed from the fixture this tenant was provisioned
        # FROM, never re-typed. `$829.95` today.
        assert sum((code.flat_amount for code in priced), Decimal("0")) == seeded_priced_total()
        # ...and the ruled figure pinned BY NAME, because a total that derives
        # itself cannot notice a repricing (OQ-CUS-12518, PO 2026-09-21).
        recon = next(code for code in catalogue if code.code == "RECON")
        assert recon.flat_amount == Decimal("75.0000"), recon.flat_amount

        resolved = R.resolve_charge_codes(
            R.Catalogue(charge_codes=catalogue), RES, ("water",), {"water": "5/8"}
        )
        assert resolved == (), [code.code for code, _amount in resolved]


def test_tc14_the_five_unpriceable_codes_are_all_one_time_or_penalty(brazos, dana):
    """WHY the refusals went away, stated as a fact about the data rather than
    left as a coincidence. If a future fixture marks one of the five
    `recurring` + `auto_apply`, TC13 keeps passing and this goes RED — which is
    the day somebody has to answer *what is 1.5% of what*."""
    with tenant_ctx(brazos):
        catalogue = resolution_catalogue.charge_code_facts()
        for code in catalogue:
            if code.flat_amount is None and not code.amounts:
                assert code.charge_type in ("one_time", "penalty"), (code.code, code.charge_type)
                assert code.auto_apply is False, code.code


def test_tc15_every_one_of_the_23_carries_auto_apply_FALSE(brazos, dana):
    """The premise of the judgment recorded in the decision log: `auto_apply`
    defaults False and **no seeded row sets it**, so *"nobody ticked it"* and
    *"the utility declared this does not auto-apply"* are the same stored value.

    Read as a DECLARATION, deliberately and in the safe direction. Nothing is
    backfilled. This test is what makes a future backfill visible."""
    with tenant_ctx(brazos):
        assert [c.code for c in resolution_catalogue.charge_code_facts() if c.auto_apply] == []


# ══════════════════════════════════════════════════════════════════════════
# The contract's own hygiene
# ══════════════════════════════════════════════════════════════════════════


def test_tc16_the_chain_stays_pure_no_django_reaches_resolution_py():
    """The purity is load-bearing for the whole cutover method: *"running it
    beside the live path costs CPU and nothing else"* (decision log,
    2026-08-27). Six columns arrived on the contract today and not one query."""
    import pathlib

    source = pathlib.Path(R.__file__).read_text()
    for banned in ("import django", "from django", "models.", "objects."):
        assert banned not in source, f"resolution.py has grown a DB dependency: {banned}"


def test_tc17_refusal_steps_covers_every_refusal_class_including_the_new_one():
    """`DEF-2341` — `apps/billing/resolution_shadow.py` keeps a HAND-WRITTEN
    copy of this map, keyed on class name and read with `.get(name)`, so a class
    added here comes back `None` and its account silently vanishes from the
    shadow report's `by_step` count. Nothing fails; a number is just quietly
    smaller.

    `resolution.refusal_steps()` derives the map from each class's own `step`,
    which is the one source hard-won law 5 asks for. The shadow is another
    lane's file today, so this asserts the SOURCE is complete and that the copy
    does not contradict it — never that the copy is complete, which would go RED
    on a fix rather than on a defect."""
    steps = R.refusal_steps()
    assert steps["ChargeCodeRecurrenceConflict"] == "R4"
    assert steps["ChargeCodeAmountMissing"] == "R4"
    assert len(steps) >= 10, steps

    from apps.billing import resolution_shadow

    for name, step in resolution_shadow.REFUSAL_STEPS.items():
        assert steps.get(name) == step, (name, step, steps.get(name))
