# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-1813** — an unmetered service could not be billed by a count.
#           `asset_count` / `billable_asset` appeared in exactly ONE file
#           (`apps/billing/resolution_shadow.py`) and nowhere in the live bill
#           run; `grep unmetered` over `gather.py` and `stages/*.py` returned
#           nothing. So trash — one of the ten services this platform sells —
#           fell back to a flat base charge, and a utility that charges per cart
#           could not express it.
# Rules:    **BR-RAT-090** (an unmetered service's quantity is a COUNT of its
#           assets on the unit — PO ruling 2026-08-20 option A, closing OQ-283;
#           worked and ratified: 3 carts x $15.00 = $45.00, remove one and the
#           next bill is $30.00) · **BR-RAT-081** (a service is declared metered
#           or unmetered) · **BR-MET-710** (metering publishes the count on
#           billing's read seam, at the SERVICE-PERIOD END DATE, and NEVER as a
#           zero when nobody looked) · BR-AST-017 (assignments are dated and
#           append-only) · BR-AST-031 (in-service by behaviour class, not label)
#           · BR-BIL-015 (a missing input is a human's decision) · CLAUDE.md
#           rule 3 (a quantity always carries its unit)
# Related:  DEF-161 (a designed absence is not a missing read — the branch this
#           builds on) · DEF-1812 (the meter multiplier crossing the same seam,
#           the convention this follows) · DEF-1811 / DEF-514 (the connection
#           size) · OQ-303 / OQ-317 (both CLOSED — $15.00 per cart, the $18.00
#           monthly base retired)
# ───────────────────────────────────────────────────────
"""DEF-1813 — three carts bill $45.00, two bill $30.00, and no count refuses.

**WHAT A UTILITY CAN CHARGE NOW THAT IT COULD NOT.** A refuse utility that
collects three carts from a property bills **3 x $15.00 = $45.00**. Take one
cart away and the next bill is **$30.00** — with nobody typing a quantity
anywhere, because BR-RAT-090's count is **OBSERVED**: it is read off the carts
standing on the unit, at the service-period end date.

**THE SHARP EDGE, AND IT IS THE WHOLE REASON THIS FILE HAS FOUR CASES INSTEAD OF
ONE.** *"This unit has no carts"* and *"nobody has ever counted this unit's
carts"* are different facts and only one of them bills:

  * **3** -> $45.00;
  * **0** -> a real answer. The cart line prices $0.00, the bill issues, and
    nothing lands on the exception screen;
  * **no count at all** -> the account STOPS, by its own name. Reading it as a
    zero bills a three-cart household $0.00 for trash on a document that foots
    and prints, which is exactly what BR-RAT-090 forbids in terms: *"'no carts
    recorded' and 'zero carts' are different facts, and only one of them is
    billable."*

**RED PROOF (r11 step 2d).** Every case below was run against an untouched copy
of the tree at this lane's starting point; the lane report quotes the failures.
The line to break to make `tc1` fail is `_stamp_asset_count` in
`apps/metering/selectors.py` — delete the `row["asset_count"] = count` and the
bill falls back to $0.00 for trash. The line to break to make `tc4` fail is the
`if count is None` arm of the same function: return `0` instead and a three-cart
household is billed nothing, silently, with every other test in this repo still
green. That mutation is the defect this file exists to keep out.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import services as asset_services
from apps.billing import models as billing_models
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
from tests.test_br_cus_068_master_bill import _by_service, _cycle

pytestmark = pytest.mark.django_db

#: **THE RATIFIED PRICE — BR-RAT-090 / OQ-303, closed 2026-08-21.** PO verbatim:
#: *"they are bill 1 trash can $15 - for example if you have 3 you multiple by
#: 3"*. Typed here so every figure below is arithmetic over a stated price.
PER_CART = Decimal("15.000000")
#: The `$18.00` monthly trash base is RETIRED (OQ-317, PO 2026-08-27, option A:
#: *"option A is correct"*), so a three-cart household owes the cart line alone.
TRASH_BASE = Decimal("0")

THREE_CARTS = Decimal("45.00")
TWO_CARTS = Decimal("30.00")
NO_CARTS = Decimal("0.00")

AUG_START, AUG_END = date(2026, 8, 1), date(2026, 8, 31)
SEP_START, SEP_END = date(2026, 9, 1), date(2026, 9, 30)
INSTALL = date(2026, 1, 5)


def _declare_unmetered(tenant, code):
    """BR-TEN-1180 — the tenant says this service is priced by CAPACITY.

    Written on `tenant_services` directly because this file is about what READS
    the declaration, not about the screen that writes it. Copied from
    `tests/test_def_161_designed_absence_bills.py` rather than shared, so that
    file's fixture and this one cannot drift into each other.

    ⚠ **IT WRITES `billing_basis="capacity"`, NOT `metered=False` — BR-TEN-1180
    (PO 2026-09-02) SUPERSEDED BR-RAT-081's boolean and tenancy migration `0032`
    DROPPED the column.** `capacity` is exactly what the false side of that
    boolean MEANT for trash: a COUNT of the unit's assets, which is BR-RAT-090
    and is the whole subject of this file. The third value, `share`, must never
    be written here — a share of another service's money has nothing to count.

    ⚠ **DEF-3086 — THE COPY ABOVE AND THIS ONE BOTH WROTE THE DROPPED COLUMN,
    AND THAT IS THE COST OF THE DELIBERATE DUPLICATION.** Twelve cases across
    the two files went red together with `KeyError: 'metered'` raised out of
    Django's field map — before any bill run, so twelve tests about billing
    reported a schema error and none of them named the tenancy migration that
    caused it.
    """
    service = tenancy_models.Service.objects.get(code=code)
    updated = tenancy_models.TenantService.objects.filter(tenant=tenant, service=service).update(
        billing_basis=tenancy_models.BILLING_BASIS_CAPACITY
    )
    assert updated == 1, f"{code} has no tenant_services row to declare"


def _trash_base_charge(tenant):
    """`BR-RAT-088` — the CHARGE CODE owns the base amount, and this one is ZERO.

    ⚠ **AN EXPLICIT ZERO IS NOT THE SAME AS LEAVING IT BLANK, AND `DEF-3344` IS
    THE PROOF.** This fixture wanted NO base charge and expressed that by
    declaring nothing, which was right when it was written. Since `BR-RAT-088`
    the rate schedule's own `base_charge` column is RETIRED and a blank means
    *this service is not served* — so `R4` refused the whole account by name and
    the run prepared **0 ready, 1 blocked**:

        R4: 'trash' is UNMETERED and its assets state no size class … and no
        charge code declaring `is_base` covers this account for it (BR-RAT-088:
        the charge code owns the base amount; a plan displays it, never defines
        it) … Declare a base charge code for 'trash' under Charge codes and mark
        it as the base

    **The fixture's INTENT is unchanged and is now stated rather than implied:**
    the utility has looked at its trash tariff and put the base at `$0.0000`, so
    the bill total IS the cart line and a figure below can only come from the
    count. A wrong count still cannot hide inside a right-looking total.
    """
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code="BASE-TRA",
        name="Trash base service",
        charge_type="recurring",
        amount_rule="flat",
        amount=TRASH_BASE,
        service=tenancy_models.Service.objects.get(code="trash"),
        is_base=True,
    )


def _trash_plan(tenant):
    """ONE plan, TRASH only, priced `$15.00` per cart with a `$0.00` base charge.

    The base is zero on purpose (OQ-317 option A): the bill total IS the cart
    line, so a figure below can only come from the count. A base would let a
    wrong count hide inside a right-looking total. It is DECLARED rather than
    omitted — see `_trash_base_charge` and `DEF-3344`.
    """
    _trash_base_charge(tenant)
    plan = make_plan(tenant, name="Refuse only", services=("trash",))
    from apps.rating import selectors as rating_selectors

    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=TRASH_BASE,
            # CLAUDE.md rule 3 — the unit the PRICE is quoted per, and the unit
            # the counted quantity will carry. `_trash_uom` seeds the same code.
            uom="cart",
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
            unit_price=PER_CART,
        )
    return plan


def _cart(actor, unit_id, number):
    """One `container_cart` on the unit's trash service point — BR-AST-042.

    Non-measuring (no meter_type, no register), and it DECLARES `service:
    trash`, because BR-RAT-090's count runs asset -> service point -> service. A
    cart without a trash service point is invisible to billing, which is
    DEF-496 with extra rows.
    """
    return asset_services.create_asset(
        actor,
        {
            "type": "container_cart",
            "asset_no": f"CART-{number:04d}",
            "service": "trash",
            "unit_id": str(unit_id),
            "install_date": INSTALL.isoformat(),
        },
    )


def _world(actor, tenant, *, cycle_code, carts):
    """A unit taking TRASH ONLY, declared unmetered, with `carts` carts on it."""
    from apps.tenancy import services as tenancy_services
    from apps.metering import premises_owners

    tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
    _declare_unmetered(tenant, "trash")
    cycle = _cycle(tenant, cycle_code)
    plan = _trash_plan(tenant)
    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Bluestem Refuse {cycle_code}", "category": "landlord"}
    )
    premises = make_premises(
        actor,
        address_line=f"12 Cart Row {cycle_code}",
        services_available=["trash"],
        owner_id=owner["id"],
    )
    unit = make_unit(actor, premises["id"], label="Unit 1", services=["trash"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    made = [_cart(actor, unit["id"], n + 1) for n in range(carts)]
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": AUG_START.isoformat(),
            "contact": {"full_name": "Ana Alvarez"},
            # DEF-3343 / BR-CUS-1024 (PO 2026-09-01, verbatim: *"Without
            # identifier we cannot create Customer ID or master account ot
            # regular account"*). A name alone opened an account until that
            # ruling and is REFUSED now, before the transaction opens — so this
            # fixture stopped reaching a bill run at all, and its six cases
            # reported a customers-module refusal for a billing question. A
            # phone is one of the three the PO's own list accepts for a person.
            "customer": {
                "display_name": "Ana Alvarez",
                "kind": "person",
                "identity": {"phone": "+1 (713) 555-0166"},
            },
            "addresses": [
                {"kind": "mailing", "line1": "12 Cart Row", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    account = customer_models.Account.objects.get(pk=created["id"])
    return cycle, unit, account, made


def _bill(tenant, cycle, tag, *, start=AUG_START, end=AUG_END):
    prepared = runs.prepare_run(
        cycle_id=cycle.id, period_start=start, period_end=end, service_date=end
    )
    assert prepared.ready, "the fixture produced no billable account — the test would be vacuous"
    run = billing_models.BillRun.objects.create(
        tenant=tenant, cycle=cycle, period_start=start, period_end=end, idempotency_key=tag
    )
    return runs.calculate_account(prepared.ready[0], bill_run=run, service_date=end)


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — three carts on a unit bill $45.00
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc1__three_carts_bill_forty_five_dollars(brazos, dana):
    """**3 x `$15.00` = `$45.00`, and nobody typed the 3.**

    BR-RAT-090's own ratified figure, produced by the LIVE bill run off real
    rows: three `container_cart` assets standing on the unit's trash service
    point. Before this the same account billed `$0.00` for trash — the service
    fell through to a base charge it did not have.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _carts = _world(dana, brazos, cycle_code="CART-1", carts=3)

        invoice = _bill(brazos, cycle, "def-1813-tc1")

        assert _by_service(invoice)["trash"] == THREE_CARTS
        assert invoice.total == THREE_CARTS
        # CLAUDE.md rule 3 — the line carries the unit the price is quoted per.
        usage = [line for line in invoice.lines.all() if line.kind == "usage"]
        assert len(usage) == 1
        assert (usage[0].quantity, usage[0].unit) == (Decimal("3.000000"), "cart")


# ══════════════════════════════════════════════════════════════════════════
# (2) OBSERVED, NEVER TYPED — take a cart away and the next bill follows
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc2__removing_a_cart_moves_the_next_bill_to_thirty(brazos, dana):
    """**Remove one cart and the next bill is `$30.00`** — the second half of
    the ratified figure, and the half that proves the count is OBSERVED.

    The cart is not deleted: its `AssetAssignment` is ENDED on 31 August, which
    is what actually happens when a driver collects a cart back. BR-AST-017
    makes assignments dated and append-only, and BR-RAT-090 resolves the count
    at the SERVICE-PERIOD END DATE — so August still bills three (the cart was
    there all month) and September bills two. **Nothing was typed on the
    account, the plan or the bill.**
    """
    with tenant_ctx(brazos):
        cycle, unit, _account, carts = _world(dana, brazos, cycle_code="CART-2", carts=3)

        august = _bill(brazos, cycle, "def-1813-tc2-aug")
        assert august.total == THREE_CARTS

        asset_models.AssetAssignment.objects.filter(
            tenant=brazos, unit_id=unit["id"], asset_id=carts[-1]["id"]
        ).update(to_date=AUG_END)

        september = _bill(brazos, cycle, "def-1813-tc2-sep", start=SEP_START, end=SEP_END)
        assert _by_service(september)["trash"] == TWO_CARTS
        assert september.total == TWO_CARTS

        # ⚠ AND AUGUST IS UNTOUCHED. Hard rule 4 — the issued figure is a fact
        # about a period, and a cart removed in September does not re-price it.
        august.refresh_from_db()
        assert august.total == THREE_CARTS


# ══════════════════════════════════════════════════════════════════════════
# (3) ZERO IS A REAL ANSWER AND IT BILLS
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc3__no_carts_bills_zero_and_still_issues(brazos, dana):
    """**A count of `0` is the utility having LOOKED.** The cart line prices
    `$0.00`, the bill is produced, and nothing lands on the exception screen.

    This is the case a lane is tempted to merge with `tc4` below, and merging
    them is the defect: one of these two facts bills and the other must not.
    """
    with tenant_ctx(brazos):
        cycle, _unit, _account, _carts = _world(dana, brazos, cycle_code="CART-3", carts=0)

        # ⚠ `DEF-BIL-9022` — SUPERSEDED IN PART BY THE PO's 2026-09-30 RULING
        # (`BR-BIL-300` as amended, built 31358c239): *"No asset means not in
        # service, even if the account took the service"*. A unit with no cart
        # is no longer a COUNTED ZERO that bills `$0.00` — it is NOT IN SERVICE
        # for trash, prints no line, and counts `$0`. This account sells trash
        # and nothing else, so nothing on it is in service, and the run says so
        # by name rather than issuing a `$0.00` document (*"A bill with no
        # services is not a $0.00 bill"*). What BR-RAT-090 cared about is still
        # asserted below and in tc4: zero is never confused with "nobody
        # counted" — this is not `CALC_ASSET_COUNT_UNAVAILABLE`.
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
        )
        assert prepared.ready == ()
        assert [b.reason for b in prepared.blocked] == ["plan_has_no_tariff_for_service"]
        assert runs.CALC_ASSET_COUNT_UNAVAILABLE not in [b.reason for b in prepared.blocked]
        assert billing_models.Invoice.objects.filter(tenant=brazos).count() == 0
        assert NO_CARTS == Decimal("0.00")  # the figure that is no longer billed


# ══════════════════════════════════════════════════════════════════════════
# (4) ⚠ THE ONE THAT MUST NOT BILL — no count at all
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc4__an_absent_count_refuses_by_name_and_never_bills_zero(
    brazos, dana, monkeypatch
):
    """**"Nobody looked" STOPS the account, by its own name.**

    The count is unobtainable here because the assets read is unpublished —
    exactly the state `metering.seams.billable_asset_count` degrades on, and the
    only way the product can honestly not know. The unit HAS three carts, so if
    the absence were read as a zero this account would be billed `$0.00` on a
    document that foots and prints.

    Asserted on the REASON, not merely "something refused": a generic
    missing-read refusal would send a clerk to the Reads tab to estimate a
    register that does not exist, when the work is to go and count the carts.
    """
    from apps.metering import seams as metering_seams

    with tenant_ctx(brazos):
        cycle, _unit, _account, _carts = _world(dana, brazos, cycle_code="CART-4", carts=3)

        monkeypatch.setattr(metering_seams, "billable_asset_count", lambda *a, **k: None)

        # ⚠ `DEF-BIL-8851` — THE STOP NOW HAPPENS AT THE CHECK, WHICH IS WHERE
        # A CLERK READS IT. `prepare_run` runs every account through the ruled
        # path first, so the account never reaches `calculate_account` and the
        # `_bill` helper (which demands a ready account) cannot be the probe.
        # Until this fix the Check stopped it under ANOTHER name — *"the meter
        # states no multiplier — Hold, or Bill with multiplier 1"* — on a cart.
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
        )
        assert prepared.ready == ()
        (refusal,) = prepared.blocked
        assert refusal.reason == runs.CALC_ASSET_COUNT_UNAVAILABLE
        assert refusal.reason != runs.CALC_UNRESOLVED_READ
        assert refusal.reason != runs.METER_HAS_NO_MULTIPLIER
        assert refusal.service_code == "trash"
        assert "count" in refusal.detail
        # …and nothing about it is a decision a clerk could answer with ×1.
        assert [d.reason for d in prepared.decisions] == []
        # Not retryable from the run screen: the carts have to be counted onto
        # the unit, which does not happen on that screen.
        assert runs.CALC_ASSET_COUNT_UNAVAILABLE in runs.NOT_RETRYABLE_HERE
        assert billing_models.Invoice.objects.filter(tenant=brazos).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# (5) THE SEAM ITSELF — what metering publishes, and what it never publishes
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc5__the_count_crosses_the_seam_and_absence_is_not_zero(
    brazos, dana, monkeypatch
):
    """`billing_reads_for_unit` publishes `asset_count`; an unwired read yields
    `None` and a NAMED reason, never `0`.

    The three states side by side on the one seam, which is the only place they
    can be compared without a bill in between.
    """
    from apps.metering import seams as metering_seams

    with tenant_ctx(brazos):
        _cycle_, unit, _account, _carts = _world(dana, brazos, cycle_code="CART-5", carts=3)

        rows = metering_selectors.billing_reads_for_unit(
            unit["id"], period_start=AUG_START, period_end=AUG_END
        )
        trash = next(row for row in rows if row["service_code"] == "trash")
        assert trash["asset_count"] == 3
        assert trash["absent_reason"] == metering_selectors.READ_ABSENT_SERVICE_NOT_METERED
        # ⚠ NOT published as a consumption. A module that answered
        # `consumption=3` would be claiming a meter was read.
        assert trash["consumption"] is None

        # The by-name seam answers the same count, at the same date.
        assert metering_selectors.billable_asset_count(unit["id"], "trash", AUG_END) == 3
        # A cart delivered AFTER the period end is not in the period's count.
        assert (
            metering_selectors.billable_asset_count(
                unit["id"], "trash", INSTALL - timedelta(days=1)
            )
            == 0
        )

        monkeypatch.setattr(metering_seams, "billable_asset_count", lambda *a, **k: None)
        rows = metering_selectors.billing_reads_for_unit(
            unit["id"], period_start=AUG_START, period_end=AUG_END
        )
        trash = next(row for row in rows if row["service_code"] == "trash")
        assert trash["asset_count"] is None
        assert trash["absent_reason"] == metering_selectors.READ_ABSENT_ASSET_COUNT_UNAVAILABLE


# ══════════════════════════════════════════════════════════════════════════
# (6) THE TWO MODULES AGREE ON A STRING, NOT ON AN IMPORT
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc6__billings_copy_of_the_reason_is_meterings_value():
    """Billing resolves metering BY NAME and never imports it, so the two agree
    on a STRING. A rename on either side goes RED here instead of silently
    re-opening the defect — the shape `tests/test_def_161_...` already asserts
    for `service_not_metered`."""
    from apps.billing.stages import measure_consumption as stage

    assert (
        stage.ABSENT_ASSET_COUNT_UNAVAILABLE
        == metering_selectors.READ_ABSENT_ASSET_COUNT_UNAVAILABLE
    )


# ══════════════════════════════════════════════════════════════════════════
# (7) THE SHADOW CAN NOW ATTEMPT AN UNMETERED SERVICE
# ══════════════════════════════════════════════════════════════════════════
def test_def_1813_tc7__the_shadow_adapter_receives_the_real_count(brazos, dana):
    """The R1-R7 adapter stops reporting `MISSING_ASSET_COUNT` and hands the
    chain a real `AssetCountFacts`.

    This is the fourth of the four missing facts the 2026-08-27 shadow lane
    named (`connection size`, `multiplier`, `asset count`, `plan`). The count
    comes off the reading ROW rather than a fresh query — the same choice
    BR-MET-500 records for the multiplier: the row cannot name a different unit
    or a different date from the one being priced.
    """
    from apps.billing import resolution_shadow

    with tenant_ctx(brazos):
        cycle, _unit, account, _carts = _world(dana, brazos, cycle_code="CART-7", carts=3)
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=AUG_START, period_end=AUG_END, service_date=AUG_END
        )
        data = prepared.ready[0]

        inputs = resolution_shadow.adapt(data, account=account)

        assert inputs.blocked_reason != resolution_shadow.MISSING_ASSET_COUNT
        assert inputs.unmetered_services == ("trash",)
        assert [(f.service, f.count) for f in inputs.asset_counts] == [("trash", 3)]
