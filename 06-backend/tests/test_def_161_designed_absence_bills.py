# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-161 (CRITICAL)** — a plan carrying any service that is not
#           metered BY DESIGN could not be billed at all. Filed 2026-08-16,
#           ruled 2026-08-27, fixed here.
# Rule:     **PO ruling 2026-08-27**, verbatim: *"DEF-161 — the bill refuses
#           because trash has no meter - this is correct - (a) Teach it that a
#           service with no meter by design is normal — bill it from its base
#           charge or percentage and never ask for a read."*
# Rules:    BR-RAT-081 (a SERVICE declares whether it is metered — the signal
#           this fix reads) · BR-MET-134 (OQ-246's closure: unmetered-by-design
#           expects no read; a consumption-priced service with no meter is a
#           human's exception) · BR-BIL-015 (a missing read is a per-case human
#           CHOICE, never a silent skip) · BR-RAT-015 (sewer prices a % of
#           water and reads no register of its own) · CLAUDE.md rule 3
# Related:  DEF-1060 (the same ruling ONE STAGE LATER — the UNIT decides WHICH
#           services bill; this decides whether a READ IS OWED at all) ·
#           DEF-495 (`tenant_services.metered` had no reader; this is it)
# ───────────────────────────────────────────────────────
"""DEF-161 — a service with no meter BY DESIGN bills, and a missed read does not.

**THE DEFECT.** `metering.billing_reads_for_unit` answered `no_meter` for a
service point with no asset, and `billing.stages.measure_consumption` treated
EVERY absent consumption identically — only `ABSENT_BASE_ONLY` (BR-CUS-055's
vacation hold, an ACCOUNT fact) was exempt. `runs.calculate_account` then
refused **the whole account**, and the only decision that released it —
`bill_without_service` — **DELETES the service from the bill**. So Silver
Creek's `$18.00` trash charge reached no customer on any bill, ever: **$18.00 ×
48 accounts × 2 periods = $1,728.00** that the utility did the work for and
never charged.

**⚠ THE DELIVERABLE IS THE DISTINCTION, NOT THE RELEASE.** The ruling says so in
as many words: *"A meter that exists and was not read keeps refusing exactly as
it does now — that distinction is the deliverable and a fix that blurs it has
traded one silent wrong bill for another."* The cheap fix — treat every
`no_meter` as benign — would bill a water meter nobody could reach as base-only,
on a document that foots, with no work on any exception screen and no test in
this repo going red.

**SO THIS FILE ASSERTS BOTH DIRECTIONS AND WOULD FAIL ON EITHER HALF ALONE:**

  * `tc1` — trash, DECLARED unmetered, no cart meter: the bill ISSUES and
    carries the trash **base charge**.
  * `tc2` — the SAME unit, the SAME missing meter, trash left DECLARED METERED:
    the bill still REFUSES by name. This is the test the careless fix fails.
  * `tc3` — water with a real meter and NO READ for the period: still refuses,
    unchanged. BR-BIL-015 is untouched.
  * `tc4` — metering names the two absences with two different strings, and
    billing's copy of the value is the same string.

**RED PROOF (r11 step 2d) — AND IT FOUND DEAD CODE IN THE FIX, WHICH IS WHY THE
LINE TO BREAK IS NAMED HERE RATHER THAN LEFT TO A READER.**

This lane first wrote an explicit `absent_reason == ABSENT_SERVICE_NOT_METERED`
branch in `measure_consumption`. It reads exactly like the fix. Disabling it and
re-running `tc1` gave **`1 passed`** — green with the "fix" removed — because the
BR-BIL-015 fallback three lines below already forwards metering's reason
verbatim. The branch was deleted (see the decision log of 2026-08-27).

**THE LINE THAT ACTUALLY CARRIES THIS BEHAVIOUR is the exempt tuple in
`runs.calculate_account`** (and its twin in `midperiod`). Remove
`ABSENT_SERVICE_NOT_METERED` from it and `tc1` fails with the engine's own
refusal — DEF-161 exactly as filed:

    apps.billing.gather.GatherProblem: account AC-...: trash still has no
    usable read and no decision. BR-BIL-015 makes that a choice — estimate it,
    hold the account, or bill without the service — and billing the rest would
    be taking the third one silently.

And in the other direction, with metering's declaration read stubbed to
"everything is unmetered", `tc2` fails on `DID NOT RAISE`. **Neither half passes
without the other**, which is the whole point of the ruling.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.billing import gather, runs
from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read
from tests.test_br_cus_068_master_bill import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    _by_service,
    _cycle,
    _run,
)

pytestmark = pytest.mark.django_db

#: OQ-303/BR-RAT-090's own worked figure for the demo tenant — the trash charge
#: that DEF-161 kept off every bill. Typed as a plan BASE charge, which is what
#: the workbook's *"Trash flat $18"* is (decision log 2026-08-21).
TRASH_BASE = Decimal("18.00")
#: The water tariff this fixture types, so every figure below is arithmetic over
#: stated prices rather than a constant.
WATER_BASE = Decimal("8.00")
WATER_PER_KGAL = Decimal("4.000000")
#: 6 kgal at $4.0000 + the $8.00 base.
WATER_BILL = Decimal("32.00")
#: What a trash-and-water account owes once DEF-161 is fixed: the water bill
#: plus the trash base charge that used to vanish.
WATER_PLUS_TRASH = WATER_BILL + TRASH_BASE  # 50.00


def _plan_with_trash(tenant):
    """ONE plan bundling water (metered, consumption-priced) and trash (flat).

    The two services are deliberately on ONE plan: DEF-161's refusal was at the
    ACCOUNT level, so a plan carrying trash made water unbillable too, and a
    fixture with trash alone could not show that.
    """
    # ── DEF-3344 · BR-RAT-088 — THE CHARGE CODE OWNS THE BASE AMOUNT ────────
    # The `$18.00` below still travels in the tariff version's `base_charge`,
    # which is where this fixture put it in 2026-08 and which is now a RETIRED
    # column. With no `is_base` charge code covering trash, `R4` refused the
    # whole account by name and the run prepared **0 ready, 1 blocked** — so
    # six cases about a DESIGNED ABSENCE never reached a bill at all. The
    # figure does not move; only the place it is DECLARED does.
    for service_code, code, amount in (
        ("water", "BASE-WAT", WATER_BASE),
        ("trash", "BASE-TRA", TRASH_BASE),
    ):
        rating_models.Charge.objects.create(
            tenant=tenant,
            code=code,
            name=f"{service_code.title()} base service",
            charge_type="recurring",
            amount_rule="flat",
            amount=amount,
            service=tenancy_models.Service.objects.get(code=service_code),
            is_base=True,
        )
    plan = make_plan(tenant, name="Residential + Trash", services=("water", "trash"))
    from apps.rating import selectors as rating_selectors

    prices = {
        "water": (WATER_BASE, WATER_PER_KGAL, "kgal"),
        # ⚠ THE TRASH TARIFF PRICES CONSUMPTION AT $0.0000 AND CARRIES THE $18
        # AS ITS BASE — this is the seeded shape (decision log 2026-08-21) and
        # it is what makes the defect real: `flat` is a consumption-priced
        # model, so the engine asked for a read this service can never have.
        "trash": (TRASH_BASE, Decimal("0.000000"), "cart"),
    }
    for row in rating_selectors.plan_rate_schedules(plan.id):
        base, unit_price, uom = prices[row["service_code"]]
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=base,
            uom=uom,
            currency="USD",
            effective_from=date(2025, 1, 1),
            effective_to=None,
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,
            unit_price=unit_price,
        )
        if row["service_code"] == "water":
            # AMENDED 2026-10-01 (billing red triage): water is a BANDED
            # service and the meter is its smallest ratified band (`W-58`,
            # DEF-2965); a version stating no size axis prices no size
            # (`DEF-2816`, the PO's chosen reading), so R3 refused the whole
            # account — "connection size 'W-58' has no row" — before any case
            # here reached its subject. Membership only, no price.
            from tests.test_us_met_helpers import state_size_axis

            state_size_axis(version, "water")
    # `DEF-RAT-9832` (PO 2026-10-06): each schedule NAMES its base code — an
    # unnamed schedule bills `$0.00` — so no figure here moves.
    from tests.base_code_naming import name_base_code

    for code in ("BASE-WAT", "BASE-TRA"):
        name_base_code(tenant, rating_models.Charge.objects.get(tenant=tenant, code=code))
    return plan


def _sell(actor, code):
    """The tenant SELLS this service — S8's own toggle, through the real service.

    Trash is not enabled on the shared W1 tenant, and `create_unit` refuses a
    service the tenant does not sell (`metering.service_not_enabled`). Enabling
    it through `update_tenant_service` also mints the service's revenue
    accounts (BR-BIL-010 / OQ-115), which the bill needs at issue.
    """
    from apps.tenancy import services as tenancy_services

    tenancy_services.update_tenant_service(actor, code, {"enabled": True})


def _declare_unmetered(tenant, code):
    """BR-TEN-1180 — the tenant says this service is priced by CAPACITY.

    Written on `tenant_services` directly because this file is about what READS
    the declaration, not about the screen that writes it.

    ⚠ **IT WRITES `billing_basis="capacity"`, NOT `metered=False` — BR-TEN-1180
    (PO 2026-09-02) SUPERSEDED BR-RAT-081's boolean and tenancy migration `0032`
    DROPPED the column.** `capacity` is precisely what the false side of that
    boolean MEANT here: a COUNT of the unit's assets (BR-RAT-090), which is what
    every case below then measures. The third value, `share`, is the one this
    helper must never write — sewer is a percentage of the water usage charge
    and has no assets to count.

    ⚠ **DEF-3086 — THIS HELPER WROTE THE DROPPED COLUMN FOR A DAY AND TOOK SIX
    CASES DOWN WITH IT.** The failure was not about billing at all: `.update(
    metered=False)` on a column that no longer exists raises before a bill run
    is ever reached, so six cases about a DESIGNED ABSENCE reported a database
    error. Nothing in the repository connected the two, because the column was
    dropped in tenancy and the red was in billing.
    """
    service = tenancy_models.Service.objects.get(code=code)
    updated = tenancy_models.TenantService.objects.filter(
        tenant=tenant, service=service
    ).update(billing_basis=tenancy_models.BILLING_BASIS_CAPACITY)
    assert updated == 1, f"{code} has no tenant_services row to declare"


def _account_on(actor, unit, *, name="Ana Alvarez"):
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": PERIOD_START.isoformat(),
            "contact": {"full_name": name},
            # DEF-3343 / BR-CUS-1024 (PO 2026-09-01, verbatim: *"Without
            # identifier we cannot create Customer ID or master account ot
            # regular account"*). A name alone opened an account until that
            # ruling and is REFUSED now, before the transaction opens — so this
            # fixture stopped reaching a bill run at all, and its six cases
            # reported a customers-module refusal for a billing question. A
            # phone is one of the three the PO's own list accepts for a person.
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": "+1 (713) 555-0177"},
            },
            "addresses": [
                {"kind": "mailing", "line1": "1408 Bluestem Ln", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


def _world(actor, tenant, *, cycle_code, with_water_read=True, trash_unmetered=True):
    """A unit taking WATER (metered, read) and TRASH (no meter, ever).

    Returns the cycle and the account. The trash service point exists — the
    customer really does have trash collection — and carries no asset, which is
    the exact shape `metering.billing_reads_for_unit` answers `no_meter` for.
    """
    _sell(actor, "water")
    _sell(actor, "trash")
    # BR-RAT-081's declaration, made BEFORE the unit exists — it is a fact about
    # the tenant's catalogue, not about any one service point.
    if trash_unmetered:
        _declare_unmetered(tenant, "trash")
    cycle = _cycle(tenant, cycle_code)
    plan = _plan_with_trash(tenant)
    # BR-MET-151 clause 3 (CR-039 C12) — a premises points at a TYPED owner and
    # `create_premises` refuses one without it.
    from apps.metering import premises_owners

    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Bluestem Holdings {cycle_code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"1408 Bluestem Ln {cycle_code}",
        services_available=["water", "trash"],
        owner_id=owner["id"],
    )
    unit = make_unit(actor, premises["id"], label="Unit 3B", services=["water", "trash"])
    meter = a_meter(
        actor, asset_no=f"M-{cycle_code}", unit_id=unit["id"], service="water", uom="kgal"
    )
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    if with_water_read:
        # The period's opening and closing dials: 106 - 100 = 6 kgal.
        commit_read(actor, meter["id"], day=str(PERIOD_START), value="100", unit="kgal")
        commit_read(
            actor,
            meter["id"],
            day=str(PERIOD_END),
            value="106",
            unit="kgal",
            prior_value="100",
            consumption="6",
        )
    account = _account_on(actor, unit)
    return cycle, unit, account


def _bill(tenant, cycle, tag):
    prepared = runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )
    assert prepared.ready, "the fixture produced no billable account — the test would be vacuous"
    return runs.calculate_account(
        prepared.ready[0], bill_run=_run(tenant, cycle, tag), service_date=SERVICE_DATE
    )


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DEFECT — a service with no meter BY DESIGN now bills its base charge
# ══════════════════════════════════════════════════════════════════════════
def test_def_161_tc1__trash_declared_unmetered_bills_its_base_charge(brazos, dana):
    """**The `$18.00` reaches a customer for the first time.**

    Before the fix this account produced NO BILL AT ALL: `calculate_account`
    raised `GatherProblem(CALC_UNRESOLVED_READ)` naming trash, so the water
    charge was lost with it. Three assertions, deliberately separate:

      * the bill EXISTS — the account is no longer refused;
      * it carries a TRASH line, by service, at the `$18.00` base charge;
      * water is untouched at `$32.00`, so the fix did not buy the trash line
        by disturbing a metered service.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(dana, brazos, cycle_code="TR-1")

        # ⚠ `DEF-BIL-9022` — AMENDED BY THE PO's 2026-09-30 RULINGS
        # (`BR-BIL-300`/`301` as amended, built 31358c239): *"No asset means not
        # in service, even if the account took the service"* and *"sane no line
        # - and use 0"*. A trash point with no cart on it is NOT IN SERVICE, so
        # the `$18.00` base this case asserted until then is no longer charged
        # (no connection, no standing charge — `BR-RAT-080`). What DEF-161 was
        # about is unchanged and still asserted: the designed absence never
        # REFUSES the account, and water is untouched. And it is not silent —
        # the account is on the clerk's review list for trash.
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert [(d.reason, d.service_code) for d in prepared.decisions] == [
            ("service_not_connected", "trash")
        ]
        invoice = _bill(brazos, cycle, "def-161-tc1")

        by_service = _by_service(invoice)
        assert "trash" not in by_service
        assert by_service["water"] == WATER_BILL
        assert invoice.total == WATER_BILL
        assert invoice.total != WATER_PLUS_TRASH


def test_def_161_tc1b__no_read_is_ever_asked_for_on_a_designed_absence(brazos, dana):
    """*"…and never ask for a read."* — the second half of the PO's sentence.

    A designed absence must not reach the S31.3 exception screen: it is not
    work, and a clerk who cannot clear a line will stop trusting the list.

    ⚠ **AMENDED 2026-08-28 (DEF-1813) — THE PROPERTY IS UNCHANGED AND THE
    MECHANISM IS NOT.** This case asserted `unmeasured == {"trash":
    ABSENT_SERVICE_NOT_METERED}`: trash stayed OFF the exception screen by being
    an EXEMPT absence. BR-RAT-090 (PO 2026-08-20, option A) makes an unmetered
    service's quantity a COUNT of its assets on the unit, and the count now
    reaches billing — so trash is off that screen because it is **MEASURED**,
    with a quantity of `0`. **This unit has no carts, and `0` is a real answer
    that bills: the cart line prices `$0.00` and the `$18.00` base still
    applies, so `tc1`'s total is untouched.** *"Nobody looked"* is a different
    fact with a different reason (`ABSENT_ASSET_COUNT_UNAVAILABLE`) and it stops
    the account — asserted in `tests/test_def_1813_unmetered_count.py`.

    The half of the ruling this case exists for still holds and is still
    asserted: **no read is ever asked for.** `unmeasured` is empty rather than
    carrying trash under some other name, and water — the metered service — is
    still the only thing priced off a register.
    """
    from apps.billing.stages import measure_consumption as stage
    from apps.billing.stages.measure_consumption import measure_consumption
    from apps.billing.stages.resolve_subscription import resolve_subscription

    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(dana, brazos, cycle_code="TR-1B")
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        data = prepared.ready[0]
        usage = measure_consumption(resolve_subscription(data), data)

        unmeasured = {s.service_code: s.absent_reason for s in usage.unmeasured}
        assert unmeasured == {}, "a designed absence must never be work on S31.3"
        # ⚠ `DEF-BIL-9022` — since the 2026-09-30 rulings a trash point with no
        # cart is NOT IN SERVICE (`BR-BIL-300` as amended), so it is not measured
        # as a counted zero any more: it is not measured at all, and it is not
        # work either. Water is still the only thing priced off a register.
        counted = {s.service_code: s.asset_count for s in usage.measured}
        assert counted == {"water": None}
        assert "trash" in data.unconnected_services
        assert stage.ABSENT_SERVICE_NOT_METERED == "service_not_metered"


# ══════════════════════════════════════════════════════════════════════════
# (2) THE HALF A CARELESS FIX DESTROYS — a METERED service with no meter
# ══════════════════════════════════════════════════════════════════════════
def test_def_161_tc2__an_undeclared_service_with_no_meter_still_refuses(brazos, dana):
    """**The same fixture, one column different, and the bill must still stop.**

    Trash is left at `tenant_services.metered = True` — its default, and the
    state of every tenant that has never touched the setting. Nothing else
    changes: the same unit, the same service point, the same absent meter.

    ⚠ **THIS IS THE TEST THAT FAILS ON THE OBVIOUS FIX.** Making every
    `no_meter` benign passes tc1 and this one goes green-by-accident too — so
    it asserts the REFUSAL, which that fix cannot produce. A water meter nobody
    installed is a setup fault, and billing base-only over it would be silent,
    plausible and wrong on an immutable document.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(
            dana, brazos, cycle_code="TR-2", trash_unmetered=False
        )

        # ⚠ `DEF-BIL-9022` — TRASH IS NO LONGER METERED BY DEFAULT. BR-TEN-1180
        # (5205cdb7d, 2026-09-02) seeds it as capacity, so "the default" this
        # case leaned on is gone and the metered declaration is written
        # explicitly. It is still the one column that differs from tc1.
        service = tenancy_models.Service.objects.get(code="trash")
        tenancy_models.TenantService.objects.filter(tenant=brazos, service=service).update(
            billing_basis=tenancy_models.BILLING_BASIS_METERED
        )
        assert tenancy_models.TenantService.objects.get(tenant=brazos, service=service).metered
        # …and metering really does report the OTHER reason for it, so the
        # refusal below is DEF-161's second branch and not a coincidence.
        reasons = {
            row["service_code"]: row["absent_reason"]
            for row in metering_selectors.billing_reads_for_unit(
                _unit["id"], period_start=PERIOD_START, period_end=PERIOD_END
            )
        }
        assert reasons["trash"] == metering_selectors.READ_ABSENT_NO_METER

        # ⚠ `DEF-BIL-9022` — THE PO RULED THE REFUSAL AWAY ON 2026-09-30
        # (`BR-BIL-300` as amended: a gas point with no meter is NOT IN SERVICE
        # and the bill goes out instead of being refused). What this case guards
        # against is unchanged: a metered service with no meter must never be
        # billed base-only SILENTLY. So: no trash line and no base at all, and
        # the account is on the clerk's review list naming trash.
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert [(d.reason, d.service_code) for d in prepared.decisions] == [
            ("service_not_connected", "trash")
        ]
        invoice = _bill(brazos, cycle, "def-161-tc2")
        assert "trash" not in _by_service(invoice)
        assert invoice.total == WATER_BILL


def test_def_161_tc3__a_real_meter_with_no_read_still_refuses(brazos, dana):
    """**BR-BIL-015 is untouched: a meter that exists and was not read stops.**

    Water has a real meter, declared metered, and NO read in the period. This
    is the ordinary missing-read case the exception screen was built for, and
    DEF-161's fix must not have widened its way into it. Trash is declared
    unmetered here, so the ONLY thing that can raise is the water meter — which
    makes the assertion specific rather than merely "something refused".
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account = _world(dana, brazos, cycle_code="TR-3", with_water_read=False)
        # ⚠ `DEF-BIL-9022` — THE METER HAS A HISTORY AND NO READ THIS PERIOD.
        # Until this amendment it had never been read at all, and a never-read
        # meter has no multiplier for the Check to answer from (BR-MET-056), so
        # the Check stopped it for its FACTOR before anything asked for its
        # READ — the case read as vacuous ("no billable account"). A meter that
        # was read last period and not this one is the ordinary missing read
        # this case is about, and it is what the clerk meets.
        from apps.assets import models as asset_models

        meter = asset_models.Asset.objects.get(tenant=brazos, asset_no="M-TR-3")
        before = PERIOD_START - timedelta(days=31)
        commit_read(dana, meter.id, day=str(before), value="90", unit="kgal")

        with pytest.raises(gather.GatherProblem) as refusal:
            _bill(brazos, cycle, "def-161-tc3")

        assert refusal.value.reason == runs.CALC_UNRESOLVED_READ
        assert "water" in str(refusal.value)
        assert "trash" not in str(refusal.value)


# ══════════════════════════════════════════════════════════════════════════
# (3) THE SEAM — two facts, two strings, one spelling
# ══════════════════════════════════════════════════════════════════════════
def test_def_161_tc4__metering_names_the_two_absences_apart(brazos, dana):
    """The reads seam itself answers two different reasons for two facts.

    Asserted at the seam because that is where the distinction is DECIDED —
    billing only carries it. Both rows come from the SAME call on the SAME
    unit, so nothing about the fixture can make one path taken and the other
    not.
    """
    with tenant_ctx(brazos):
        cycle, unit, _account = _world(dana, brazos, cycle_code="TR-4")
        assert cycle is not None

        rows = {
            row["service_code"]: row["absent_reason"]
            for row in metering_selectors.billing_reads_for_unit(
                unit["id"], period_start=PERIOD_START, period_end=PERIOD_END
            )
        }
        # Trash: declared unmetered, no asset -> the designed absence.
        assert rows["trash"] == metering_selectors.READ_ABSENT_SERVICE_NOT_METERED
        # Water: metered, has an asset and a read -> no absence at all.
        assert rows["water"] is None
        assert (
            metering_selectors.READ_ABSENT_SERVICE_NOT_METERED
            != metering_selectors.READ_ABSENT_NO_METER
        )


def test_def_161_tc5__billing_and_metering_spell_the_reason_identically():
    """The seam is dynamic (`gather._resolve`), so the contract is a STRING.

    Billing never imports metering, so nothing but this assertion stops a
    rename on one side from silently reopening DEF-161 — the branch would stop
    matching, every existing test would still pass, and trash would go back to
    refusing every account that carries it.
    """
    from apps.billing.stages import measure_consumption as stage

    assert stage.ABSENT_SERVICE_NOT_METERED == metering_selectors.READ_ABSENT_SERVICE_NOT_METERED


def test_def_161_tc6__an_undeclared_tenant_is_byte_identical_to_before(brazos, dana):
    """DEF-495's column defaults to True, so a tenant that never touched it has
    NO unmetered services — and every bill in the product prices exactly as it
    did before this read existed. That is what makes the fix safe under ❄️
    frozen B4/B5.
    """
    from apps.metering import seams as metering_seams

    with tenant_ctx(brazos):
        _sell(dana, "trash")
        # ⚠ `DEF-BIL-9022` — BR-TEN-1180 (5205cdb7d, 2026-09-02) seeds trash
        # as CAPACITY, so a tenant that never touched the setting already has
        # trash unmetered — the ruled seed, not a drift. The property this case
        # protects is the frozen one: a METERED service (water, every ❄️ B5
        # figure) is never in this set unless somebody declares it.
        assert metering_seams.unmetered_service_codes() == frozenset({"trash"})
        assert "water" not in metering_seams.unmetered_service_codes()
        _declare_unmetered(brazos, "trash")
        assert metering_seams.unmetered_service_codes() == frozenset({"trash"})
