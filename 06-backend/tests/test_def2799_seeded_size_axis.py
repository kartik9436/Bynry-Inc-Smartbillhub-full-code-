# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2799 — the seeded utility configures NO per-size rate row and NO
#          version base charge, so the ruled R1–R7 chain refuses 47 of 47
#          accounts at R3 (`SizeNotServed` on `W-58`, the ordinary domestic
#          connection) and the cutover cannot be measured past R3 on the repo's
#          own fixture. Fixing EITHER fact alone changes nothing.
# Rules:   BR-RAT-120 (a banded service whose schedule version configures no
#          size serves NONE, and every meter on it refuses — PO 2026-08-28) ·
#          BR-RAT-088 (the charge code owns the base) · DEF-277 / CR-013 part 1
#          (a BLANK base means *this size is not served*) · OQ-238 /
#          `gather._base_charge_for` (two stated bases that DISAGREE refuse the
#          bill; two EQUAL ones are a duplicate and pass through)
# Tests:   this file. The other half is on real rows:
#          `10-scripts/def2799_live_base_charges.py` before and after, and
#          `10-scripts/cr052_r1r7_shadow_measure.py`.
# Impacts: apps/rating/sample_data.py · apps/tenancy/management/commands/seed_demo.py
# ───────────────────────────────────────────────────────
"""The seeded utility can be priced by the ruled chain, and no bill moved.

⚠ **THE SECOND FACT IS INVISIBLE UNTIL THE FIRST IS FIXED, WHICH IS WHY BOTH
ARE ASSERTED HERE AND NOT IN TWO FILES.** With `rate_size_rows` empty, R3 refuses
with *"connection size 'W-58' has no row on the rate schedule version"*. Write a
row for every size and it refuses again with the OTHER sentence — *"…with a
BLANK base charge … a blank base means THIS SIZE IS NOT SERVED (DEF-277)"* —
because `tariff_versions.base_charge` is NULL. A lane that fixed only the size
rows would find 47 of 47 still refusing and would have learned nothing.

⚠ **THE BASE HALF WAS A WORKAROUND FOR `DEF-2823` AND IT IS NOW GONE
(2026-08-31).** For one afternoon both seeders wrote `tariff_versions
.base_charge` so R3 would stop refusing. That column is RETIRED: BR-RAT-088
moved the base onto the CHARGE CODE, the S11 wizard has had no control for it
since, and `decimalOut("")` omits the key — so **every schedule a real utility
creates through this product stores NULL there**, and a fixture that wrote it
was configured in a way no customer could copy. `DEF-2823` fixed the CHAIN
instead: R3 asks only *does this schedule serve this size* and R4 states the
amount from the `is_base` charge code.

**So what these tests now pin is the OTHER half — the size axis — plus the new
invariant that replaced the workaround: every base a PLAN states is also stated
by an `is_base` CHARGE CODE, at the same figure.** `seed_demo.Command
._assert_base_codes_state_the_plans_bases` is that guard, and it stops the SEED
rather than letting `gather._base_charge_for` refuse a bill later.

**THE ONE THING THAT MUST NOT HAPPEN** is a customer's base charge moving.
Measured on real rows across this change: water $8.00 on `AC-2026-00001` and
$390.00 across the 47 accounts of the July run, account by account, diff empty.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import sample_data
from apps.tenancy import service_size_classes
from apps.tenancy.management.commands import seed_demo
from core import sample_fixture as fixture

# ══════════════════════════════════════════════════════════════════════════
# The helper both seeders share
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("service", ["water", "electric", "gas", "trash"])
def test_sample_size_rows_states_every_ratified_class_of_a_banded_service(service):
    """BR-RAT-120's axis, and it must cover every size a meter can BE.

    The seeded `meter_size_classes` rows come from this same ratified list, so
    covering it covers every size any asset on the tenant can carry — by
    construction, rather than by the seeders happening to agree.
    """
    ruled = [code for code, _name in service_size_classes.size_classes_for_service(service)]
    assert ruled, f"{service} is expected to be banded"
    assert [row["size_class"] for row in sample_data.sample_size_rows(service)] == ruled


def test_sample_size_rows_states_NO_minimum_bill():
    """A row with no `minimum_bill` says *this size IS served and has no floor*
    (r10's em-dash) — never `$0.00`, which would be a stated money figure nobody
    typed. `_validate_size_rows` stores the NULL; DEF-277's distinction, one
    column across."""
    for row in sample_data.sample_size_rows("water"):
        assert set(row) == {"size_class"}


def test_sewer_is_ruled_to_have_no_size_axis_and_gets_no_rows():
    """NOT a gap. Sewer is priced as a share of the WATER usage charge and reads
    no register of its own, so `configured_sizes_for` answers with the single
    blank-size ladder rather than refusing. An empty tuple here means *ruled to
    have none*; a RAISE would mean *nobody has said*, and the two must never
    collapse into each other."""
    assert service_size_classes.size_classes_for_service("sewer") == ()
    assert sample_data.sample_size_rows("sewer") == []


def test_an_unruled_service_raises_rather_than_seeding_a_guess(monkeypatch):
    """The prime directive: a lane may not answer an open boundary by choosing a
    value. A seeder that priced an unruled dimension would be inventing a tariff,
    and the raise carries the OQ-ID, which is what makes the failure actionable.

    ⚠ **THIS CASE ASSERTED IT THROUGH `battery` AND HAD BEEN RED SINCE
    2026-09-01 (`DEF-3097`).** `DEF-2408` moved battery out of the *never ruled*
    register that morning — the PO had DISSOLVED `OQ-561`, so battery became
    `()`, *ruled to have none* — and `sample_size_rows("battery")` therefore
    returned `[]` instead of raising. Three suites were updated with that fix
    and this one was missed, so it failed **DID NOT RAISE** for a day with
    nobody reading it. `CR-062` then gave battery six capacities, which changed
    the number in the failure from 0 rows to 6 and changed nothing else.

    **NO SERVICE OF THE TEN IS UNRULED ANY MORE**, so the mechanism is now
    tested the only way that is honest: a dimension is registered as unruled for
    the length of one assertion. That is the shape `test_br_rat_120_size_refusal
    .py` TC-5 already uses, and for the same reason — the MECHANISM is what is
    under test, not any particular service.
    """
    # Both halves are needed and the order they are read in is the reason:
    # `size_classes_for_service` consults the RATIFIED map FIRST, so adding an
    # unbanded entry without removing the ratified one changes nothing.
    monkeypatch.delitem(service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES, "battery")
    monkeypatch.setitem(
        service_size_classes.UNBANDED_SERVICE_DIMENSIONS,
        "battery",
        ("OQ-99999", "a dimension nobody has ruled, for this assertion only"),
    )
    with pytest.raises(NotImplementedError) as raised:
        sample_data.sample_size_rows("battery")
    assert "OQ-99999" in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
# The demo fixture (seed_demo) — the base is DERIVED from the plan, never retyped
# ══════════════════════════════════════════════════════════════════════════


def test_seed_demo_states_a_BASE_CHARGE_CODE_for_every_base_a_plan_states():
    """`DEF-2823`'s replacement for the version-base assertion.

    With `BR-RAT-088` making the charge code the source, a plan that states a
    base for a service with NO `is_base` code for it bills **no base at all** —
    every line individually correct and the total short by the base. The guard
    is pure over two module constants, so it cannot be defeated by seeding
    order.
    """
    seed_demo.Command._assert_base_codes_state_the_plans_bases()


def test_seed_demo_base_codes_state_THE_SAME_FIGURE_the_plans_do():
    """**THE ASSERTION THAT KEEPS A BILL FROM MOVING.**

    `gather._base_charge_for` refuses the bill when the charge code and the plan
    both state a base and the two DISAGREE — the plan's figure is then a
    migration artefact, not a second opinion. Equality is therefore not a
    tidiness property: it is the whole reason pointing the live path at the
    charge code moved no bill.
    """
    stated: dict[str, set[Decimal]] = {}
    for code in seed_demo.CHARGE_CODES:
        if not code.get("is_base"):
            continue
        stated.setdefault(str(code["service"]), set()).add(Decimal(str(code["amount"])))
    for plan in seed_demo.RATE_PLANS:
        for service in plan["services"]:
            base = service.get("base_charge")
            if base is None:
                continue
            assert Decimal(str(base)) in stated.get(str(service["service"]), set()), (
                f"plan {plan['code']} states {base} for {service['service']} and no "
                "is_base charge code states that figure — every bill on it would refuse"
            )


def test_seed_demo_refuses_a_plan_base_no_charge_code_states():
    """PROVED RED, not described. No such plan exists in the fixture today; the
    seed stops if one ever does, rather than shipping a tenant whose every bill
    on that service refuses at run time.

    ⚠ **THE FIGURE IS THE ONE THIS FIXTURE ACTUALLY CARRIED.** Until 2026-08-31
    plan `IND` stated `$180.00` for electric while the only `is_base` electric
    code stated `$12.00` — a `$168.00` gap nothing could see, because the live
    path read the plan and the ruled chain has no production caller. 0 accounts
    are on `IND`, so no bill ever carried either figure.
    """
    from django.core.management.base import CommandError

    original = seed_demo.RATE_PLANS
    seed_demo.RATE_PLANS = (
        {
            "name": "A",
            "code": "A",
            "description": "",
            "services": [{"service": "electric", "base_charge": "999", "schedule": "S"}],
            "charges": (),
        },
    )
    try:
        with pytest.raises(CommandError, match="no .is_base. charge code states that figure"):
            seed_demo.Command._assert_base_codes_state_the_plans_bases()
    finally:
        seed_demo.RATE_PLANS = original


def test_seed_demo_writes_NO_base_on_the_rate_schedule_version():
    """⚠ **THE WORKAROUND'S REMOVAL, ASSERTED.** `DEF-2823` — a real utility
    cannot write `tariff_versions.base_charge`, so neither may the fixture that
    is supposed to show what a real utility looks like."""
    from pathlib import Path

    source = Path(seed_demo.__file__).read_text(encoding="utf-8")
    assert 'payload["base_charge"]' not in source, (
        "seed_demo writes the RETIRED tariff_versions.base_charge again — "
        "BR-RAT-088 moved the base onto the charge code and S11 has no control "
        "for this column (DEF-2823)"
    )


# ══════════════════════════════════════════════════════════════════════════
# The sample utility (rating.sample_data) — the tenant the 47 accounts are on
# ══════════════════════════════════════════════════════════════════════════


def _sample_payloads(monkeypatch):
    """`_schedule_payloads()` with the tenant reads stubbed.

    Every one of them is a declaration about which services this tenant sells
    and in what unit — not money — and stubbing them lets the FIGURES be
    asserted without provisioning a tenant.

    ⚠ AMENDED FOR `DEF-2397`: `_schedule_payloads` used to gate the water
    payloads on `seams.service_is_enabled` and now asks `sample_data.estate()`,
    which resolves the tenant's enabled set AND its declared units into the one
    backbone `core.sample_fixture.estate_plan` gives metering and assets. So the
    stub states an ESTATE — the municipal water/sewer/trash shape these figures
    belong to — rather than "every service is on". No assertion below moves.
    """
    monkeypatch.setattr(sample_data.seams, "service_is_enabled", lambda code: True)
    monkeypatch.setattr(sample_data.seams, "billed_uom", lambda code: None)
    monkeypatch.setattr(
        sample_data,
        "estate",
        lambda: fixture.estate_plan(["water", "sewer", "trash"], {"water": fixture.WATER_UOM}),
    )
    return {row["name"]: row for row in sample_data._schedule_payloads()}


def test_every_sample_schedule_states_a_SIZE_AXIS_and_NO_base(monkeypatch):
    """The size axis on every banded schedule the sample utility seeds — and
    **no base on any of them** (`DEF-2823`).

    Before the size axis existed, all five carried none and the chain refused
    every account on the tenant. The BASE is a different fact and it does not
    belong here: `tariff_versions.base_charge` is retired, S11 has no control
    for it, and the figure lives on `BASE_CHARGE_CODES`.
    """
    payloads = _sample_payloads(monkeypatch)
    for name, payload in payloads.items():
        assert "base_charge" not in payload, (
            f"{name} writes the RETIRED tariff_versions.base_charge — BR-RAT-088 "
            "moved the base onto the charge code (DEF-2823)"
        )
        if payload["service"] == "sewer":
            assert "size_rows" not in payload
            continue
        assert payload.get("size_rows"), f"{name} states no size axis — R3 refuses"


def test_the_sample_base_CODES_state_the_figures_the_sample_plans_do(monkeypatch):
    """Where the base actually lives, asserted against the fixture's own
    constants — one constant, two homes, so they cannot drift apart."""
    codes = {row["code"]: row for row in sample_data.BASE_CHARGE_CODES}
    assert Decimal(str(codes["BASE-W"]["amount"])) == Decimal(str(fixture.WATER_BASE))
    assert Decimal(str(codes["BASE-W-COM"]["amount"])) == Decimal(
        str(fixture.COMMERCIAL_WATER_BASE)
    )
    assert Decimal(str(codes["BASE-T"]["amount"])) == Decimal(str(fixture.TRASH_BASE))
    # BR-RAT-108 — one service, two amounts, separated by CLASS and never by name.
    # ⚠ `DEF-RAT-8811` — since `CR-062` J3/J4 (2026-09-02, `DEF-3282`) each
    # water code also claims the class that has no code of its own: `municipal`
    # rides residential and `industrial` rides commercial (water has no
    # industrial base), or those accounts match no base and bill nothing.
    assert codes["BASE-W"]["applies_to_customer_classes"] == ["residential", "municipal"]
    assert codes["BASE-W-COM"]["applies_to_customer_classes"] == ["commercial", "industrial"]


def test_the_sample_water_ladder_serves_the_size_its_own_meters_are(monkeypatch):
    """`W-58` — `Water 5/8"`, the ordinary domestic connection, and the size
    every one of the 47 accounts in the July run carries. This is the assertion
    that would have gone RED for the whole life of `DEF-2799`."""
    payloads = _sample_payloads(monkeypatch)
    served = {row["size_class"] for row in payloads[sample_data.SCHEDULE_WATER_RES]["size_rows"]}
    assert "W-58" in served


def test_both_seeders_name_the_defects_their_decisions_answer():
    """⚠ **THE ROW THAT USED TO SAY "THIS EXISTS TO BE DELETED" — AND IT WAS.**

    It pinned the version-base workaround and named `DEF-2823` as its removal
    condition. That defect is fixed and the workaround is gone, so what is
    asserted now is the durable half: the reason for each decision stays AT the
    line, because a figure whose justification lives only in a commit message is
    one the next lane will either delete blindly or defend forever.

    Hard-won law 1 in the other direction: a comment claiming a guarantee is not
    the guarantee, so what is asserted here is only that the defects are NAMED
    where the decisions were taken.
    """
    from pathlib import Path

    for path in (Path(sample_data.__file__), Path(seed_demo.__file__)):
        source = path.read_text(encoding="utf-8")
        assert "DEF-2799" in source, f"{path.name} does not name the size-axis defect"
        assert "DEF-2823" in source, f"{path.name} does not name the base-source defect"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2799 · DEF-2823 · CR-052 task 20 · BR-RAT-120 · BR-RAT-088
# generated: 2026-08-31 by the DEF-2799/DEF-2798 lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL before and after. No ❄️ FROZEN B4/B5
#        figure is read, asserted or moved: every money figure here is a seeded
#        base charge from the billing workbook §1, and the only arithmetic is an
#        equality between two copies of one constant.
# ──────────────────────────────────────────────────────────
