# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-088 (PO 2026-08-20 — the CHARGE CODE owns the base amount) ·
#           BR-RAT-103 (PO 2026-08-21 — a charge code prices ONE customer
#           class) · BR-RAT-092 (the decimal rule) · CLAUDE.md hard rule 7
# Defects:  DEF-452 (no seeded plan carries a customer class) · DEF-455 (the
#           seeder writes no base charge codes) · DEF-468 (two surviving base
#           codes REFUSE) · DEF-477 (the cleared column does not stay cleared) ·
#           DEF-438 (the R1–R7 chain has no production caller)
# Tests:    this file, for
#           apps/rating/management/commands/migrate_base_to_charge_codes.py
# ───────────────────────────────────────────────────────
"""BR-RAT-088's migration: the base moves owner and NOT ONE BILL MOVES.

THE ACCEPTANCE TEST IS TC-1 AND IT PRICES BOTH WAYS
---------------------------------------------------
The brief for this lane is *"for every account, the base charged before equals
the base charged after — prove it with a test that prices both ways, not by
reasoning."* So TC-1 does not compare a stored column to a stored column. It
takes the base the LIVE path charges today — `apps.billing.gather
._base_charge_for`, billing's own function, the one every invoice this product
has issued went through — and the base the RULED path resolves afterwards —
`resolution.resolve_charge_codes` narrowed by `resolve_base_charge`, R4 as
BR-RAT-088 and BR-RAT-103 define it — and requires the two Decimals to be equal
for every account.

Both halves are real code owned by the modules that own the rule. Nothing here
re-implements either, because a test that re-implements the thing it is checking
proves only that the author was consistent with themselves.

WHY THE `--apply` PATH IS EXERCISED HERE AND NOWHERE ELSE
---------------------------------------------------------
`--apply` refuses on a live product while `gather._base_charge_for` still reads
the retired column (DEF-438), so the only place it is safe to run at all is a
test database that is thrown away. TC-9 asserts that refusal; every other case
reaches `apply_plan` directly, which is the same code the command calls.

⚠ **AMENDED 2026-10-02 (`DEF-RAT-9134`).** The PO retired the plan's base on
2026-09-28 (*"we will never take default value from plan $8.0 - that is
retired"*), `DEF-BIL-7170` took it out of `_base_charge_for`, and the refusal
above lifted itself as designed. TC-1 now hands billing's reader the CODE the
ruled path resolves (its only input) and TC-9 asserts the lifted gate. TC-9c is
NOT amended here: it asserts the dry run's MOVES/REFUSES report, and that report
still calls billing with the retired arguments — a product question, not a
stale test (`DEF-RAT-9139`).

⚠ **AMENDED AGAIN 2026-10-02 (`DEF-RAT-9139`, `DEF-RAT-9140`, `DEF-RAT-9141`) —
THE COMMAND CREATES NO CHARGE CODE ANY MORE, AND THE ACCEPTANCE TEST CHANGED
SIDES WITH IT.** Under the ruling the plan figure is retired, so a code minted
from it would RAISE bills (Silver Creek water: `$0.00` today with no code →
`$8.00`). Decision log 2026-10-02 *"THE BASE MIGRATION CREATES NO CHARGE CODE
FROM A RETIRED PLAN FIGURE"*: a row whose figure equals what the bill charges is
cleared; any other is HELD for a person and no code is written. So TC-1 now
prices every account's base through billing's own functions BEFORE and AFTER
`--apply` and requires them equal — which is what "no bill moves" means once the
plan figure is not an input — and the cases that asserted minted codes now
assert that none exists and that the figure is held and listed.

PROVE-IT (hard-won law 7)
-------------------------
Run this file against the previous commit and every test errors on
`ModuleNotFoundError: apps.rating.management` — the command does not exist. The
RED that matters is narrower and is recorded per case: TC-4/5/6 fail with the
migration performed instead of refused if any refusal is removed; TC-1 fails on
`assert Decimal('8.000000') == None` the moment a minted code loses its class
scope; and TC-10 is the one that goes RED on the PRODUCT rather than on this
code — it fails the day somebody gives the seeded plans a customer class, which
is DEF-452 being fixed and is exactly when this test should be re-read.
"""

from decimal import Decimal

import pytest

from apps.rating import models, resolution
from apps.rating.constants import ALL_SIZES
from apps.rating.management.commands import migrate_base_to_charge_codes as cmd

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import api_call, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import seeding_ctx

pytestmark = pytest.mark.django_db

RESIDENTIAL = "residential"
COMMERCIAL = "commercial"


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def pg_vendor(monkeypatch):
    """Make the command's Postgres guard pass on the sqlite tier.

    The guard itself is asserted for real in TC-9b. Patching it here is the
    same move `tests/test_us_ten_020_sweep.py` makes for `sweep_reference_data`
    and for the same reason: every case below is about the MIGRATION, and a
    vendor refusal would hide all of them behind one message.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(cmd, "connection", SimpleNamespace(vendor="postgresql"))


def _account_type(tenant, code, name):
    """THIS tenant's account type for `code`.

    ⚠ **`DEF-RAT-9145` (2026-10-02).** `account_types` is tenant-owned and
    RLS-scoped, and this helper read and wrote it with no tenant context and
    no tenant. On SQLite (no RLS) it quietly returned ANY tenant's row; on
    PostgreSQL RLS hid the tenant's own seeded row and refused the insert, so
    17 of this file's 22 cases errored there. Both are fixed by asking inside
    the tenant's context, for the tenant."""
    from apps.customers import models as customers_models

    with seeding_ctx(tenant):
        row, _ = customers_models.AccountType.objects.get_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": name, "is_system": True, "active": True},
        )
    return row


def _plan(env, name, code, services_payload, customer_class=None):
    """A plan with a base per service, and optionally a customer class.

    `account_type_ids` is the ONLY thing that tells this migration which class a
    plan's base prices (BR-RAT-103). Every plan the product seeds today leaves
    it NULL — DEF-452 — which is why TC-5 and TC-10 exist.

    ⚠ **THIS POSTED THE SINGULAR `account_type_id` UNTIL 2026-09-27 AND THE
    PLAN WRITER HAD REFUSED IT BY NAME SINCE 2026-09-23 (`DEF-RAT-6980`).**
    `DEF-RAT-5768` replaced `rate_plans.account_type_id` — one class — with
    `rate_plans.account_type_ids`, a LIST where `[]` means EVERY class, and
    `services.create_plan` rejects an unknown field: every call through this
    helper died on `VAL-002 rating.unknown_field`, seventeen cases in this file
    alone. The command under test was moved on the same day the column was
    (`migrate_base_to_charge_codes` line 495 reads `account_type_ids`), so the
    CODE was never wrong here — only this fixture.

    ⚠ **AND THE SINGULAR IS STILL CORRECT ONE LEVEL DOWN.**
    `plan_deposit_rules.account_type_id` is a different column on a different
    table and `DEF-RAT-5768` did not touch it. A blanket rename of the string
    in this repo is the mirror-image defect.
    """
    overrides = {}
    if customer_class is not None:
        overrides["account_type_ids"] = [
            str(_account_type(env.tenant, customer_class, customer_class.title()).id)
        ]
    return env.plan(name, code, services_payload, **overrides)


def _silver_creek(env):
    """The billing workbook's own figures, on plans that DO carry a class.

    Water `$8.00` residential and `$15.00` commercial, trash `$18.00` on both,
    sewer `$0.00` on both — `core/sample_fixture.py`'s numbers, not new ones.
    The classes are the part the shipped fixture is missing (DEF-452); stating
    them here is what lets the migration be tested at all.
    """
    env.enable("water", "sewer", "trash")
    _plan(
        env,
        "Sample — Residential",
        "SCW-RES",
        [
            {"service": "water", "base_charge": "8.00"},
            {"service": "sewer", "base_charge": "0"},
            {"service": "trash", "base_charge": "18.00"},
        ],
        customer_class=RESIDENTIAL,
    )
    _plan(
        env,
        "Sample — Commercial",
        "SCW-COM",
        [
            {"service": "water", "base_charge": "15.00"},
            {"service": "sewer", "base_charge": "0"},
            {"service": "trash", "base_charge": "18.00"},
        ],
        customer_class=COMMERCIAL,
    )


def _stored_bases(tenant):
    """`{(plan_code, service_code): base_charge}` straight off the column."""
    with seeding_ctx(tenant):
        return {
            (row.rate_plan.code, row.service.code): row.base_charge
            for row in models.PlanService.objects.select_related("rate_plan", "service")
        }


def _base_codes(tenant):
    with seeding_ctx(tenant):
        return {
            charge.code: charge
            for charge in models.Charge.objects.filter(
                is_base=True, deleted_at__isnull=True
            ).select_related("service")
        }


def _catalogue_of_base_codes(tenant):
    """R4's catalogue, built from the tenant's own `is_base` rows.

    Only the base codes: R4 iterates every code it is given and REFUSES one it
    cannot price at the account's connection size, so handing it a percent-rule
    late fee would fail the test for a reason that has nothing to do with the
    base. Nothing in production builds this at all — DEF-438 — which is itself
    part of what this file records.
    """
    codes = []
    charges = _base_codes(tenant).values()
    # DEF-RAT-9145 — the amount rows are read INSIDE the tenant's context; on
    # PostgreSQL RLS otherwise hides them and every code reads "no amount".
    with seeding_ctx(tenant):
        flats = {
            charge.code: next(
                (
                    row.amount
                    for row in charge.amounts.filter(
                        size_class=ALL_SIZES,
                        customer_class__isnull=True,
                        killed_at__isnull=True,
                    )
                ),
                None,
            )
            for charge in charges
        }
    for charge in charges:
        codes.append(
            resolution.ChargeCode(
                code=charge.code,
                service=charge.service.code if charge.service_id else None,
                customer_classes=tuple(charge.applies_to_customer_classes or ()),
                is_base=charge.is_base,
                # CR-156-BRC10 — the flat amount is an *All sizes* row now
                flat_amount=flats[charge.code],
            )
        )
    return resolution.Catalogue(charge_codes=tuple(codes))


def _base_after(tenant, customer_class, service_code, named_code=None):
    """THE RULED PATH — what R4 + BR-RAT-088 resolve for one account.

    `named_code` is the code the account's rate schedule NAMES; since PO ruling
    2026-10-06 nothing else prices a base (`DEF-RAT-9841`)."""
    catalogue = _catalogue_of_base_codes(tenant)
    account = resolution.AccountFacts(
        account_no="A-1", unit_id="u-1", customer_class=customer_class
    )
    resolved = resolution.resolve_charge_codes(catalogue, account, (service_code,), {})
    return resolution.resolve_base_charge(resolved, service_code, named_code)


def _base_billed(service_code, code_base):
    """THE LIVE PATH — billing's own function, unmodified and un-mirrored.

    ⚠ **ITS ONLY INPUT IS THE CHARGE CODE'S FIGURE FROM 2026-09-28
    (`DEF-BIL-7170`, `DEF-RAT-9134`).** PO ruling, verbatim (decision log
    *"A STALE PLAN FIGURE MAY NOT STOP A BILL"*): *"we ahve to take ot from
    Charge code - whya re you confuse about it - charge code binded in plan -
    unitl it is part of plan we cannot take amount from charge code - we will
    never take default value from plan $8.0 - that is retired"*. So
    `_base_charge_for(service_code, *, code_base)` takes no plan figure and no
    schedule figure; this helper read `(service, plan_base, schedule_base)` until
    2026-10-02 and raised `TypeError` from the day of the ruling.
    """
    return cmd.live_base_charge_reader()(service_code, code_base=code_base)


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE ACCEPTANCE TEST — no bill amount may change
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__the_base_charged_before_equals_the_base_charged_after(env, pg_vendor):
    """RED shape: `assert Decimal('15.00') == Decimal('8.00')` if the commercial
    plan's base folds into the residential code — which is precisely what would
    happen without BR-RAT-103's class column (DEF-467).

    ⚠ **WHAT "BEFORE" MEANS CHANGED ON 2026-09-28, AND THIS CASE WAS AMENDED
    ON 2026-10-02 TO SAY SO (`DEF-RAT-9134`).** Until the PO retired the plan's
    base (*"we will never take default value from plan $8.0 - that is
    retired"*, decision log 2026-09-28), billing priced the base FROM the plan
    column, so "before" was billing's reader handed the plan figure. From that
    ruling billing reads ONLY the charge code (`_base_charge_for(service, *,
    code_base)`), so the plan figure can no longer be fed to it at all. The
    property this test owns is unchanged — **the figure that moves is the
    figure that arrives, for every class** — and it is now asserted the only
    way the live path allows: the plan's stored figure is the "before", and
    billing's own reader, handed the code the ruled path resolves, must charge
    exactly that figure.
    ⚠ **AND ON 2026-10-02 THE FIGURE THAT MUST NOT MOVE BECAME THE BILL'S OWN
    (`DEF-RAT-9139`).** The plan figure is retired and the command no longer
    turns it into a code, so "before" is now what billing charges BEFORE
    `--apply` and "after" what it charges after — each priced by the ruled
    chain (`_base_after`) handed to billing's own reader, a computation the
    command does not share. Silver Creek has no base code, so all six bills
    charge `$0.00` (base not set) on both sides; the RED shape, if a code were
    minted from the plan, is `assert Decimal('8.00') == Decimal('0.0000')`.
    """
    _silver_creek(env)
    classes = {"SCW-RES": RESIDENTIAL, "SCW-COM": COMMERCIAL}

    def billed():
        return {
            (plan_code, service_code): _base_billed(
                service_code, _base_after(env.tenant, classes[plan_code], service_code)
            )
            for (plan_code, service_code) in _stored_bases(env.tenant)
        }

    before = billed()
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        assert not plan.refusals, [r.detail for r in plan.refusals]
        cmd.apply_plan(env.admin, plan)
    after = billed()

    assert len(before) == 6, "six plan-service bases were seeded; all six must be checked"
    assert after == before
    assert set(before.values()) == {Decimal("0")}
    assert _base_codes(env.tenant) == {}, "a charge code was created from a retired figure"


def test_tc1b__only_the_figures_the_bill_already_charges_are_cleared(env, pg_vendor):
    """Sewer's `$0.00` IS what the bill charges, so it is cleared; water's
    `$8.00`/`$15.00` and trash's `$18.00` are not, so they stay on the plan and
    are listed for a person. RED if the held rows are cleared too: the stored
    set reads `{None}`."""
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        result = cmd.apply_plan(env.admin, cmd.plan_tenant(env.tenant))
    assert result == {"cleared": 2, "held": 4}
    stored = _stored_bases(env.tenant)
    assert stored[("SCW-RES", "sewer")] is None and stored[("SCW-COM", "sewer")] is None
    assert stored[("SCW-RES", "water")] == Decimal("8.00")
    assert stored[("SCW-COM", "water")] == Decimal("15.00")
    assert stored[("SCW-RES", "trash")] == Decimal("18.00")


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · the mapping, on Silver Creek's own figures
# ══════════════════════════════════════════════════════════════════════════


def test_tc2__two_amounts_for_one_service_become_two_class_scoped_codes(env, pg_vendor):
    """Water is `$8.00` residential and `$15.00` commercial — ONE service, two
    amounts, which is the case that could not be expressed at all until
    BR-RAT-103 (DEF-467)."""
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    water = sorted(
        (code for code in plan.codes if code.service_code == "water"),
        key=lambda code: code.amount,
    )
    assert [c.amount for c in water] == [Decimal("8.00"), Decimal("15.00")]
    assert water[0].customer_classes == (RESIDENTIAL,)
    assert water[1].customer_classes == (COMMERCIAL,)
    assert all(code.action == cmd.ACTION_NEW for code in water)


def test_tc2b__one_amount_on_two_plans_becomes_ONE_code_covering_both(env, pg_vendor):
    """Trash is `$18.00` on both plans. Two codes would be one figure kept in
    two rows — the duplication BR-RAT-088 exists to end — so it is one code
    whose class list names both classes."""
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    trash = [code for code in plan.codes if code.service_code == "trash"]
    assert len(trash) == 1, [c.code for c in trash]
    assert trash[0].amount == Decimal("18.00")
    assert trash[0].customer_classes == (COMMERCIAL, RESIDENTIAL)


def test_tc2c__the_class_list_is_ENUMERATED_and_never_left_null(env, pg_vendor):
    """BR-RAT-103: NULL means EVERY class. The trash base was stated by a
    residential and a commercial plan and by nothing else, so writing NULL would
    silently price `industrial` and `government` accounts nobody quoted."""
    # ⚠ 2026-10-02 — the codes are PRINTED for a person now, never written, so
    # the property is asserted on what the report tells them to create.
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        cmd.apply_plan(env.admin, plan)
    assert plan.codes
    for code in plan.codes:
        assert code.customer_classes, f"{code.code} was suggested unscoped"

    # And nothing was written, so an industrial account still resolves no trash
    # base at all rather than inheriting a figure priced for somebody else.
    assert _base_codes(env.tenant) == {}
    assert _base_after(env.tenant, "industrial", "trash") is None


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · $0 is a PRICE, not an absence (PO ruling 2026-08-19)
# ══════════════════════════════════════════════════════════════════════════


def test_tc3__a_zero_base_is_migrated_like_any_other_figure(env, pg_vendor):
    """Sewer's base is `$0.00` on both plans. Skipping it would turn "this
    service is free" into "no base is stated anywhere", which `_base_charge_for`
    REFUSES — a stopped bill, not a cheaper one."""
    # ⚠ 2026-10-02 — under the ruling the bill charges `$0.00` for a base
    # nobody defined and bound, so a stated `$0.00` on the plan IS what the bill
    # charges: it is cleared, not held, and it needs no code to stay `$0.00`.
    # It is still a figure and not an absence — it is matched as `0`, not
    # skipped as blank, which is what this case has always guarded.
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        sewer = [e for e in plan.live_effects if e.base.service_code == "sewer"]
        assert len(sewer) == 2 and not any(e.held for e in sewer)
        cmd.apply_plan(env.admin, plan)

    for customer_class in (RESIDENTIAL, COMMERCIAL):
        assert _base_billed("sewer", _base_after(env.tenant, customer_class, "sewer")) == Decimal(
            "0"
        )
    stored = _stored_bases(env.tenant)
    assert stored[("SCW-RES", "sewer")] is None and stored[("SCW-COM", "sewer")] is None


# ══════════════════════════════════════════════════════════════════════════
# TC-4/5/6 · WHERE IT REFUSES RATHER THAN GUESSING
# ══════════════════════════════════════════════════════════════════════════


def test_tc4__two_plans_same_class_same_service_different_amounts_refuse(env, pg_vendor):
    """No single code can hold both, and choosing either changes a bill. RED if
    the grouping silently keeps one: the refusal list empties and two codes are
    minted for one class."""
    env.enable("water")
    _plan(env, "Standard", "STD", [{"service": "water", "base_charge": "8.00"}], RESIDENTIAL)
    _plan(env, "Senior", "SEN", [{"service": "water", "base_charge": "6.00"}], RESIDENTIAL)

    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    kinds = [r.kind for r in plan.refusals]
    assert cmd.REFUSAL_CONFLICTING_AMOUNTS in kinds, kinds
    detail = next(r.detail for r in plan.refusals if r.kind == cmd.REFUSAL_CONFLICTING_AMOUNTS)
    assert "STD=8.000000" in detail and "SEN=6.000000" in detail, detail
    assert plan.codes == [], "nothing may be minted for a service under refusal"


def test_tc5__a_plan_with_no_customer_class_refuses_and_names_def_452(env, pg_vendor):
    """An unscoped base code means EVERY class, so it silently overrides a
    scoped one for accounts of other classes."""
    env.enable("water")
    _plan(env, "Classless", "CLS", [{"service": "water", "base_charge": "8.00"}])

    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    refusal = next(r for r in plan.refusals if r.kind == cmd.REFUSAL_NO_CUSTOMER_CLASS)
    assert "'CLS'" in refusal.detail and "DEF-452" in refusal.detail
    assert plan.codes == []


def test_tc6__an_existing_unscoped_base_code_refuses_the_whole_move(env, pg_vendor):
    """The demo tenant's own state: `BASE-W` is seeded `is_base`, water, `$8.00`
    and UNSCOPED. Minting a `$15.00` commercial code beside it leaves TWO base
    codes reaching one commercial account, and `resolve_base_charge` refuses on
    that (DEF-468) — so the migration would produce REFUSED bills, not wrong
    ones. RED if the overlap check is dropped: `plan.refusals` empties and a
    commercial account then raises `ChargeCodeAmountMissing` at bill time."""
    env.enable("water")
    env.charge(
        "BASE-W",
        "Water base service",
        charge_type="recurring",
        service="water",
        amount_rule="flat",
        amount="8.00",
        is_base=True,
    )
    _plan(env, "Commercial", "COM", [{"service": "water", "base_charge": "15.00"}], COMMERCIAL)

    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    refusal = next(r for r in plan.refusals if r.kind == cmd.REFUSAL_OVERLAPPING_BASE_CODES)
    assert "'BASE-W'" in refusal.detail and "EVERY class" in refusal.detail

    # And the refusal is not decorative. ⚠ 2026-10-02 — it no longer stops
    # `--apply`, because nothing it guards is written any more: the commercial
    # bill charges BASE-W's $8.00 today, the plan's $15.00 differs, so the row
    # is HELD — left on the plan, no code created, BASE-W untouched. RED if a
    # refused row were cleared: the stored figure reads None.
    [effect] = plan.live_effects
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): the plan's schedule
    # names no base code, so the bill charges `$0.00` — not BASE-W's `$8.00`
    # from the pool. The row is still HELD and nothing below moves.
    assert (effect.bill_base, effect.bill_code, effect.held) == (Decimal("0"), None, True)
    with tenant_ctx(env.tenant):
        assert cmd.apply_plan(env.admin, plan) == {"cleared": 0, "held": 1}
    assert _stored_bases(env.tenant) == {("COM", "water"): Decimal("15.00")}
    assert list(_base_codes(env.tenant)) == ["BASE-W"]


def test_tc6b__an_existing_code_that_MATCHES_is_reused_not_duplicated(env, pg_vendor, capsys):
    """The other side of the same check. A tenant who already declared exactly
    the right code gets it REUSED — no second row, no ambiguity, and the
    migration is the no-op it should be for them."""
    env.enable("water")
    env.charge(
        "BASE-W",
        "Water base service",
        charge_type="recurring",
        service="water",
        amount_rule="flat",
        amount="8.00",
        is_base=True,
        applies_to_customer_classes=[RESIDENTIAL],
    )
    _plan(env, "Residential", "RES", [{"service": "water", "base_charge": "8.00"}], RESIDENTIAL)

    # ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9841`) — THE POOL THIS CASE STOOD ON IS
    # GONE.** It asserted the bill already charges BASE-W's `$8.00` because the
    # class-narrowed pool found BASE-W for a schedule naming nothing. PO ruling
    # 2026-10-06: *"if it is not provided then you will take it zeo"* — so the
    # bill charges `$0.00` here, the plan's `$8.00` is a figure it does NOT
    # charge, and the row is HELD. The property this case owns survives intact:
    # the matching code is REUSED — found and named, never duplicated — and the
    # report now says the cure is NAMING it on the rate schedule, a person's
    # choice the command never makes.
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        assert not plan.refusals, [r.detail for r in plan.refusals]
        [effect] = plan.live_effects
        assert (effect.bill_base, effect.bill_code, effect.held) == (Decimal("0"), None, True)
        assert [(c.code, c.action) for c in plan.codes] == [("BASE-W", cmd.ACTION_REUSE)]
        assert plan.new_codes == []
        assert cmd.apply_plan(env.admin, plan) == {"cleared": 0, "held": 1}

    from django.core.management import call_command

    call_command("migrate_base_to_charge_codes", tenant=[env.tenant.subdomain])
    printed = capsys.readouterr().out
    assert "would RAISE the bill from 0.00 to 8.00 if BASE-W were named on its rate schedule" in printed
    assert list(_base_codes(env.tenant)) == ["BASE-W"], "a second code was created"
    assert _stored_bases(env.tenant) == {("RES", "water"): Decimal("8.00")}


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · idempotence
# ══════════════════════════════════════════════════════════════════════════


def test_tc7__running_it_twice_does_nothing_the_second_time(env, pg_vendor):
    """By CONSTRUCTION, not by a marker: the second run finds no plan-service
    carrying a base, so it plans nothing. A stored "already migrated" flag would
    be one more thing that can disagree with the data."""
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        first = cmd.apply_plan(env.admin, cmd.plan_tenant(env.tenant))
        second_plan = cmd.plan_tenant(env.tenant)
        second = cmd.apply_plan(env.admin, second_plan)

    # 2026-10-02 — the two sewer zeros are cleared; the four held rows (water
    # residential and commercial, trash on both plans) are held again, and the
    # second run clears nothing and creates nothing.
    assert first == {"cleared": 2, "held": 4}
    assert second == {"cleared": 0, "held": 4}
    assert len(second_plan.bases) == 4
    assert second_plan.to_clear == []
    assert _base_codes(env.tenant) == {}


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · the audit row is the reversal story
# ══════════════════════════════════════════════════════════════════════════


def test_tc8__every_cleared_column_writes_its_prior_figure_to_the_audit_row(
    env, pg_vendor, audit_rows
):
    """CLAUDE.md hard rule 7, and the only route back. `plan_services.base_charge`
    is not versioned, so once cleared the `before` payload here is the sole
    record of what the utility had typed."""
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        cmd.apply_plan(env.admin, cmd.plan_tenant(env.tenant))

    # 2026-10-02 — only the two cleared sewer rows write one; a held row is not
    # written, so it needs no audit row. `after` says what the bill charges and
    # which code charges it (none: the `$0.00` is "base not set").
    cleared = [row for row in audit_rows if row["action"] == cmd.ACTION_BASE_CLEARED]
    assert len(cleared) == 2
    figures = sorted(row["before"]["base_charge"] for row in cleared)
    assert figures == ["0.000000", "0.000000"]
    assert all(row["actor_user_id"] == env.admin.id for row in cleared)
    assert all(row["after"]["charged_by_charge_code"] is None for row in cleared)
    assert all(Decimal(row["after"]["bill_base"]) == Decimal("0") for row in cleared)


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · the live path, and the gate it forces
# ══════════════════════════════════════════════════════════════════════════


def test_tc9__the_DEF_438_gate_has_lifted_because_billing_reads_only_the_charge_code(
    env, pg_vendor
):
    """DEF-438's gate: `--apply` refused while the bill run took its base from
    `plan_services`, because clearing that column would have stopped bills. The
    gate is a BEHAVIOUR PROBE so that it lifts itself the day billing stops
    reading the plan — and billing stopped on 2026-09-28.

    ⚠ **TURNED AROUND ON 2026-10-02 (`DEF-RAT-9134`), NOT DELETED.** This case
    was `test_tc9__apply_refuses_while_the_live_path_still_reads_the_plan_column`
    and asserted the probe answered `True`. The PO's ruling of 2026-09-28
    (decision log *"A STALE PLAN FIGURE MAY NOT STOP A BILL"*, verbatim: *"we
    will never take default value from plan $8.0 - that is retired"*) took the
    plan figure out of `_base_charge_for` altogether (`DEF-BIL-7170`), and the
    probe's own docstring names that case: *"the function having been removed
    — means the read has moved on, and the gate below lifts itself"*. So the
    probe answers `False` BY DESIGN and `--apply` is no longer refused for
    DEF-438. Asserted end to end through the command, with a real actor, so the
    lifted gate is proved by a run that WRITES rather than by the probe alone.
    """
    from django.core.management import call_command

    from tests.test_us_rat_helpers import _owner_of

    _silver_creek(env)
    assert cmd.live_path_still_reads_the_plan_column() is False

    # `DEF-RAT-9140` FIXED 2026-10-02 — the role-swap shim that stood here is
    # gone. `Command._actor` now attaches the user's role from their membership
    # in THIS tenant, as `identity/auth.py` does after sign-in, so the run below
    # goes through `apply_plan`'s `@require_role(SYSTEM_ADMIN)` as the real
    # owner. RED before the fix: `AuthError AUTH-002` out of `call_command`.
    owner = _owner_of(env.tenant)
    call_command(
        "migrate_base_to_charge_codes",
        "--apply",
        tenant=[env.tenant.subdomain],
        actor_email=owner.email,
    )
    stored = _stored_bases(env.tenant)
    assert stored[("SCW-RES", "sewer")] is None, "the lifted gate applied nothing"
    assert stored[("SCW-RES", "water")] == Decimal("8.00"), "a held figure was cleared"
    assert _base_codes(env.tenant) == {}


def test_tc9a__the_permission_check_is_not_weakened(env, pg_vendor):
    """The role check used to live in `services.create_charge`, one call below
    `apply_plan`. With the mint gone it moved UP, onto `apply_plan` itself — so
    an actor without the System Admin role still clears nothing."""
    from types import SimpleNamespace

    from core import errors

    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        with pytest.raises(errors.AuthError):
            cmd.apply_plan(SimpleNamespace(id=env.admin.id, role=None), plan)
    assert _stored_bases(env.tenant)[("SCW-RES", "sewer")] == Decimal("0")


def test_tc9b__the_dry_run_says_NO_bill_changes_and_lists_the_retired_figures(
    env, pg_vendor, capsys
):
    """THE TRUE REPORT (`DEF-RAT-9139`, 2026-10-02).

    This case was `..._says_the_bill_would_REFUSE_and_that_is_the_truth` and
    asserted `bills_that_refuse == 6`. It was green over a FALSE report: the
    command called `_base_charge_for` with arguments retired on 2026-09-28,
    swallowed the `TypeError`, and printed REFUSES for all six rows — and the
    old world had also refused all six, for a real reason, so the number never
    moved. Under the ruling (*"we will never take default value from plan
    $8.0 - that is retired"*) billing takes no plan figure at all, so:

      * clearing the plan column changes NO bill — six rows, `UNCHANGED`;
      * every Silver Creek bill charges `$0.00` base today (no code defined
        and bound, PO 2026-09-30);
      * the four rows stating more than that — water `$8.00` and `$15.00`,
        trash `$18.00` twice — are HELD for a person and listed as figures a
        code would newly charge; the two sewer `$0.00` rows are cleared.

    And the stale `DEF-477` precondition is gone from the report
    (`DEF-RAT-9141`): that defect was fixed on 2026-08-21.
    """
    _silver_creek(env)
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    assert [e.outcome for e in plan.live_effects] == [cmd.LIVE_UNCHANGED] * 6
    assert plan.bills_that_change == 0
    assert {e.bill_base for e in plan.live_effects} == {Decimal("0")}
    assert all(e.bill_code is None and e.bill_refusal is None for e in plan.live_effects)
    held = sorted((e.base.plan_code, e.base.service_code) for e in plan.held)
    assert held == [
        ("SCW-COM", "trash"),
        ("SCW-COM", "water"),
        ("SCW-RES", "trash"),
        ("SCW-RES", "water"),
    ]
    assert len(plan.bases_newly_charged) == 4
    assert sorted((e.base.plan_code, e.base.service_code) for e in plan.to_clear) == [
        ("SCW-COM", "sewer"),
        ("SCW-RES", "sewer"),
    ]

    from django.core.management import call_command

    call_command("migrate_base_to_charge_codes", tenant=[env.tenant.subdomain])
    printed = capsys.readouterr().out
    assert "DRY RUN — nothing is written" in printed
    assert "REFUSES" not in printed and "MOVES" not in printed
    assert "UNCHANGED" in printed
    assert "bills that change 0" in printed
    assert "held for a person 4 (would newly charge 4)" in printed
    assert "charge codes created 0" in printed
    assert "would RAISE the bill from 0.00 to 8.00" in printed
    assert "DEF-477" not in printed, "a stale precondition is back on the report"
    assert set(_stored_bases(env.tenant).values()) != {None}, "a dry run wrote something"


def test_tc9c__a_LEGACY_ZERO_SCHEDULE_BASE_no_longer_moves_the_bill(env, pg_vendor):
    """WHAT USED TO BE THE MOVES CASE, AND WHAT IT IS NOW.

    `tariff_versions.base_charge` was NOT NULL with `default=0` until 2026-08-19
    (DEF-277), so schedule versions written before then hold a stored `0`.
    Until 2026-09-28 billing let the plan's `$8.00` win over that zero, and
    clearing the plan column would have dropped the bill to `$0.00` — DEF-154's
    shape — which is why the report grew a MOVES column.

    ⚠ **REWRITTEN 2026-10-02 (`DEF-RAT-9139`).** Billing now reads neither the
    plan figure nor the schedule's: `_base_charge_for(service, *, code_base)`
    takes the charge code's figure and nothing else. Activating the schedule
    declares the tenant's `BASE-W` (water, `$8.00`, every class — the fixture's
    signed figure), so this bill charges `$8.00` TODAY, from the code, and the
    schedule's zero is read by nothing. Clearing the plan's `$8.00` leaves it at
    `$8.00` — UNCHANGED — and because the plan figure IS what the bill charges,
    the row is CLEARED rather than held, and no code is created. RED on the old
    command: it reported `MOVES 8.00 → 0.00` here, and before the old command
    was fixed it raised `TypeError` instead. The schedule's zero is still
    reported and still not touched. (The HELD case — a plan figure a code would
    newly charge — is TC-9b.)
    """
    from tests.test_us_rat_helpers import _base_charge_payload

    _code, _name, water_base = _base_charge_payload("water")
    reader = cmd.live_base_charge_reader()
    with pytest.raises(TypeError):
        reader("water", Decimal("8.00"), Decimal("0"))
    assert reader("water", code_base=None) == Decimal("0")

    env.enable("water")
    schedule = env.flat_schedule("Legacy water", "water", unit_price="2.90")
    _plan(
        env,
        "Legacy",
        "LEG",
        [{"service": "water", "base_charge": water_base, "tariff": schedule["id"]}],
        RESIDENTIAL,
    )
    codes_before = sorted(_base_codes(env.tenant))
    with tenant_ctx(env.tenant):
        models.TariffVersion.objects.filter(tariff_id=schedule["id"]).update(
            base_charge=Decimal("0")
        )
        plan = cmd.plan_tenant(env.tenant)
        result = cmd.apply_plan(env.admin, plan)

    assert Decimal(water_base) == Decimal("8.00"), "the fixture's signed water base moved"
    assert plan.bills_that_change == 0
    [effect] = plan.live_effects
    assert (effect.outcome, effect.bill_base, effect.bill_code) == (
        cmd.LIVE_UNCHANGED,
        Decimal("8.00"),
        "BASE-W",
    )
    assert not effect.held and plan.codes == [] and plan.refusals == []
    assert plan.schedule_bases_remaining == 1
    assert result == {"cleared": 1, "held": 0}
    assert _stored_bases(env.tenant) == {("LEG", "water"): None}
    assert sorted(_base_codes(env.tenant)) == codes_before, "a charge code was created"
    # The bill after the clear, through the ruled chain and billing's reader.
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9841`): R4 reads the code the schedule
    # NAMES and nothing else (PO ruling), so the ruled path is handed the code
    # activation wrote onto the version — BASE-W, the service's only one.
    assert _base_billed(
        "water", _base_after(env.tenant, RESIDENTIAL, "water", named_code=effect.bill_code)
    ) == Decimal("8.00")


# ══════════════════════════════════════════════════════════════════════════
# TC-10 · THE SHIPPED FIXTURE — this is the finding, not a failure
# ══════════════════════════════════════════════════════════════════════════


def test_tc10__the_shipped_sample_plans_now_SAY_which_customers_they_price(env, pg_vendor):
    """**DEF-452 IS FIXED, AND THIS IS THE READING ITS OWN TEST ASKED FOR.**

    Until 2026-08-24 this case was named `..._carry_NO_customer_class` and
    asserted `"account_type_id" not in payload`, with a docstring that said:

        ⚠ THIS TEST GOING RED IS GOOD NEWS. It fails the day DEF-452 is fixed,
        which is the day this migration becomes runnable on a real tenant. Read
        it then; do not delete it.

    DEF-452 was fixed in `54a7c09` (*"the two sample plans finally say which
    customers they price"*) and the register carries it as `status=fixed`. The
    test went red exactly as designed — **and stayed red, unread, because a
    failing assertion says "something broke" in a voice indistinguishable from
    "the good news arrived".** Found on 2026-08-24 by a CR-030 W0 regression
    sweep that had nothing to do with rating, and confirmed pre-existing by
    re-running it against the commit before W0 in a detached worktree.

    So: read, not deleted. The assertion is INVERTED to the new truth rather
    than removed, because the property still matters — BR-RAT-103's worked
    example, *"Silver Creek's water base is $8.00 residential and $15.00
    commercial"*, needs the two plans to name DIFFERENT classes, and a payload
    that merely has the key would satisfy a weaker check while pricing both
    tiers at the same class.

    It reads `_plan_payloads` rather than running the whole seeder on purpose:
    the payload builder is the thing that decides this, and depending on the
    entire sample-seeding chain would make this case fail for reasons that have
    nothing to do with the customer class.
    """
    from apps.rating import sample_data

    schedule_ids = {
        sample_data.SCHEDULE_WATER_RES: "res",
        sample_data.SCHEDULE_WATER_COM: "com",
        sample_data.SCHEDULE_SEWER: "sew",
        sample_data.SCHEDULE_TRASH: "tra",
    }
    with tenant_ctx(env.tenant):
        payloads = sample_data._plan_payloads(schedule_ids)

    # ⚠ **THREE PLANS, NOT TWO, SINCE THE SEED GAINED AN INDUSTRIAL ONE —
    # `DEF-RAT-6980` (found on 2026-09-27, after the `account_type_ids` half of
    # this case was repaired and this assertion became the next one to fire).**
    # `sample_data._plan_payloads` builds `SCW-RES`, `SCW-COM` and `SCW-IND`,
    # each naming its own class. **The list is asserted whole rather than by
    # membership**, exactly as it was, so a FOURTH sample plan still goes red
    # here and names itself — which is the property this case is for. What was
    # stale was the contents, never the shape.
    assert [payload["code"] for payload in payloads] == [
        sample_data.PLAN_RESIDENTIAL,
        sample_data.PLAN_COMMERCIAL,
        sample_data.PLAN_INDUSTRIAL,
    ]
    # Every shipped plan names its class...
    # ⚠ **`account_type_ids`, A LIST, SINCE `DEF-RAT-5768` (2026-09-23) —
    # `DEF-RAT-6980`.** `[]` now means EVERY class, so `.get(...)` being truthy
    # is still exactly the right question: a plan that names no class is the
    # DEF-452 state this case was written to prove gone.
    for payload in payloads:
        assert payload.get("account_type_ids"), payload["code"]
    # ...and they name DIFFERENT ones, which is the half that makes
    # BR-RAT-103's $8.00-residential / $15.00-commercial example producible.
    classes = {payload["code"]: payload["account_type_ids"] for payload in payloads}
    assert classes[sample_data.PLAN_RESIDENTIAL] != classes[sample_data.PLAN_COMMERCIAL]
    # DEF-RAT-6980 — all THREE distinct, not merely the first two. Two plans
    # sharing a class would make `BR-RAT-103`'s per-class base unproducible for
    # whichever of them the migration reached second.
    assert len({tuple(value) for value in classes.values()}) == len(classes), classes
    assert classes[sample_data.PLAN_INDUSTRIAL] == [
        str(sample_data.seams.account_type_id_by_code("industrial"))
    ]
    assert classes[sample_data.PLAN_RESIDENTIAL] == [
        str(sample_data.seams.account_type_id_by_code("residential"))
    ]
    assert classes[sample_data.PLAN_COMMERCIAL] == [
        str(sample_data.seams.account_type_id_by_code("commercial"))
    ]

    # And the figures the fixture states are the ones this lane was handed.
    bases = {
        (payload["code"], line["service"]): line["base_charge"]
        for payload in payloads
        for line in payload["services"]
    }
    # Read from `core.sample_fixture`, never re-typed: B12 §No hard-coded
    # values, and a second literal here would be a second source of truth for
    # the exact figures this migration exists to move.
    from core import sample_fixture as fixture

    assert Decimal(bases[(sample_data.PLAN_RESIDENTIAL, "water")]) == Decimal(fixture.WATER_BASE)
    assert Decimal(bases[(sample_data.PLAN_COMMERCIAL, "water")]) == Decimal(
        fixture.COMMERCIAL_WATER_BASE
    )
    # ⚠ **TRASH IS `$0.00`, NOT `$18.00` — `OQ-317` CLOSED 2026-08-27 ON OPTION A
    # AND RETIRED THE WORKBOOK'S MONTHLY TRASH BASE (`DEF-2490`).** This read
    # `fixture.TRASH_FLAT` and went on passing for a day after the ruling,
    # because the fixture and this assertion agreed with each other while both
    # disagreed with the PO. `TRASH_FLAT` is still `"18.00"` — a signed `[W] §1`
    # figure is superseded and RECORDED, never deleted — and nothing seeds it;
    # `TRASH_BASE` is what the plan and `BASE-T` read. Worked: a three-cart
    # household is 3 x $15.00 = $45.00, not $63.00.
    assert Decimal(bases[(sample_data.PLAN_RESIDENTIAL, "trash")]) == Decimal(fixture.TRASH_BASE)
    assert Decimal(bases[(sample_data.PLAN_COMMERCIAL, "trash")]) == Decimal(fixture.TRASH_BASE)
    assert Decimal(bases[(sample_data.PLAN_RESIDENTIAL, "sewer")]) == Decimal("0")
    # The three figures, spelled out once so a reader sees them without a lookup.
    assert (
        Decimal(fixture.WATER_BASE),
        Decimal(fixture.COMMERCIAL_WATER_BASE),
        Decimal(fixture.TRASH_BASE),
    ) == (Decimal("8.00"), Decimal("15.00"), Decimal("0"))


def test_tc10b__so_the_migration_refuses_on_every_one_of_those_rows(env, pg_vendor):
    """The same six figures on classless plans — the shipped shape — and the
    command refuses six times and mints nothing. This is the dry-run finding the
    Product Owner is owed, PRODUCED rather than described."""
    env.enable("water", "sewer", "trash")
    for code, water in (("SCW-RES", "8"), ("SCW-COM", "15")):
        _plan(
            env,
            f"Sample — {code}",
            code,
            [
                {"service": "water", "base_charge": water},
                {"service": "sewer", "base_charge": "0"},
                {"service": "trash", "base_charge": "18"},
            ],
        )

    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)

    assert len(plan.bases) == 6
    assert plan.codes == []
    assert {r.kind for r in plan.refusals} == {cmd.REFUSAL_NO_CUSTOMER_CLASS}
    assert len(plan.refusals) == 6


def test_tc10c__and_no_seeded_charge_code_declares_itself_a_base(env, pg_vendor):
    """DEF-455, OPEN. The platform reference fixture is what puts charge codes on
    a tenant, and not one of its entries carries `is_base` — so BR-RAT-088's read
    path finds nothing on a seeded tenant and PLN-03 step 4 reads "No base charge
    code for this service" for every service."""
    import json
    from pathlib import Path

    from django.conf import settings

    fixture = json.loads(
        Path(settings.BASE_DIR, "apps/tenancy/fixtures/lookup_defaults.json").read_text()
    )
    entries = fixture.get("charge_codes") or fixture["lists"]["charge_codes"]
    assert entries, "the fixture seeds charge codes — if it stops, re-read this"
    assert [entry for entry in entries if entry.get("is_base")] == []


# ══════════════════════════════════════════════════════════════════════════
# TC-11/12 · the two things that would be silent if they were wrong
# ══════════════════════════════════════════════════════════════════════════


def test_tc11__no_precision_is_lost_in_what_the_report_tells_a_person(env, pg_vendor):
    """CLAUDE.md hard rule 2 and BR-RAT-092. The figure is reported, never
    quantized: B4's rounding is ❄️ FROZEN and rounding on the way past would be
    an unsigned rounding rule standing in front of a signed one.

    ⚠ 2026-10-02 — no code is created any more, so the figure is no longer
    COPIED anywhere: it is HELD on the plan, exactly as typed, and the code a
    person would need is printed carrying it whole. (A code they create stores
    four places — `charge_code_amounts.amount`, PO re-sign 2026-08-22.)"""
    env.enable("water")
    _plan(env, "Odd", "ODD", [{"service": "water", "base_charge": "8.123456"}], RESIDENTIAL)

    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        cmd.apply_plan(env.admin, plan)

    assert [code.amount for code in plan.new_codes] == [Decimal("8.123456")]
    assert _stored_bases(env.tenant) == {("ODD", "water"): Decimal("8.123456")}


def test_tc12__an_existing_code_is_REUSED_whatever_the_tenant_named_it(env, pg_vendor):
    """BR-RAT-088's own docstring warns that matching `BASE-<service>` by name
    fails SILENTLY. So a tenant whose residential water base is a code named
    nothing like `BASE-WATER` still has it found — by `is_base`, the service,
    the class list and the figure, never the string — and the plan's matching
    `$8.00` is cleared because the bill already charges it.

    ⚠ 2026-10-02 — this renamed codes the command had MINTED; it mints none
    now, so the tenant's own code stands in for one."""
    env.enable("water")
    env.charge(
        "SERVICE-CHG-7",
        "Water standing charge",
        charge_type="recurring",
        service="water",
        amount_rule="flat",
        amount="8.00",
        is_base=True,
        applies_to_customer_classes=[RESIDENTIAL],
    )
    _plan(env, "Residential", "RES", [{"service": "water", "base_charge": "8.00"}], RESIDENTIAL)

    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9841`): the plan's schedule names no base
    # code, so the bill charges `$0.00` (PO ruling) and the row is HELD; the
    # tenant's code is still FOUND — as the reuse the report points a person
    # at — by `is_base`, service, class and figure, never by its name.
    with tenant_ctx(env.tenant):
        plan = cmd.plan_tenant(env.tenant)
        assert [(c.code, c.action) for c in plan.codes] == [("SERVICE-CHG-7", cmd.ACTION_REUSE)]
        [effect] = plan.live_effects
        assert (effect.bill_base, effect.bill_code, effect.held) == (Decimal("0"), None, True)
        assert cmd.apply_plan(env.admin, plan) == {"cleared": 0, "held": 1}

    assert _stored_bases(env.tenant) == {("RES", "water"): Decimal("8.00")}
    assert sorted(_base_codes(env.tenant)) == ["SERVICE-CHG-7"]


def test_tc12b__the_generated_code_fits_the_column_validator(env, pg_vendor):
    """`services._validate_charge` caps `charges.code` at 20. The command
    generates its codes, so a service whose name is long enough must not produce
    a payload the writer refuses — a migration that fails on the tenth tenant is
    worse than one that fails on the first."""
    assert cmd.CODE_MAX_LENGTH == 20
    long_code = cmd._unique_code("BASE-" + "THERMAL-HEAT", "-RES", set())
    assert len(long_code) <= 20
    assert long_code.endswith("-RES"), "the CLASS must survive the trim, not the service"
