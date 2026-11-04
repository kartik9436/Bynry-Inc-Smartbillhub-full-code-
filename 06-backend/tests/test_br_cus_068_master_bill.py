# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-068 (a master account is an ordinary `accounts` row,
#           `kind='master'`, payer = the owner/manager, covering the premises'
#           common-area units through the SAME account–unit linkage every
#           account uses) · BR-MET-101 (a common area is a unit with a flag;
#           THE worked case: 1408 Elm, 3 units + 2 common areas — hallway
#           lighting $41.20 + shared irrigation $28.40 = **$69.60 on ONE owner
#           bill**)
# Pin:      **$69.60.** One master account, one document, every covered common
#           area priced. Written FIRST and proved RED against the anchor-only
#           behaviour it replaces (the bill carried the anchor unit's services
#           alone, and the second common area was additionally reported as a
#           unit with no billable account).
# Rules:    BR-CUS-017 (an account holds exactly ONE `unit_id` — which is why
#           coverage rides `service_agreements`) · BR-BIL-039 (stages 1–5 pure,
#           so every covered unit's readings are GATHERED before the run) ·
#           BR-BIL-015 (a missing read is a human decision, never a zero) ·
#           BR-RAT-007 (priced on the version in force at the SERVICE date)
# Defects:  DEF-571 (the under-bill: $41.20 of a $69.60 obligation) · DEF-572
#           (the phantom exception row on a covered common area)
# OQs:      OQ-334 (two covered areas taking the SAME service — base per
#           connection or per bill?) · OQ-335 (covered areas on DIFFERENT
#           plans — whose taxes, fees, discounts and plan snapshot?) ·
#           OQ-336 (BR-RAT-114's mid-period split over a multi-unit account)
# Impacts:  apps/billing/gather.py · apps/billing/runs.py ·
#           apps/billing/midperiod.py · apps/customers/selectors.py
# ───────────────────────────────────────────────────────
"""BR-MET-101's $69.60, on one document.

THE ONE ASSERTION THIS FILE EXISTS FOR is tc1's **$69.60**. A master account
anchors on the premises' FIRST common area (BR-CUS-068: `accounts.unit_id`
holds exactly one unit) and covers the rest through its open service
agreements. Until this file was written, `gather` priced `account.unit_id` and
nothing else — so the owner's bill carried the hallway's electric and the
irrigation's water was billed to nobody, on a document that footed correctly
and looked entirely ordinary.

The fixture is BR-MET-101's own building, with prices chosen so the two ruled
figures come out of the product rather than out of a constant:

    hallway lighting   electric   base 12.00 + 146 kWh × 0.20  = **41.20**
    shared irrigation  water      base  8.00 + 5.1 kgal × 4.00 = **28.40**
                                                       ONE BILL  **69.60**
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models, runs
from apps.customers import models as customer_models, services as customer_services
from apps.metering import models as metering_models, services as metering_services
from apps.rating import models as rating_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    state_size_axis,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)
SERVICE_DATE = date(2026, 8, 31)

#: The two ruled figures (BR-MET-101 / BR-CUS-068), and their sum.
HALLWAY = Decimal("41.20")
IRRIGATION = Decimal("28.40")
COMMON_BILL = Decimal("69.60")


def _priced_plan(tenant, *, name="Small Commercial"):
    """ONE plan bundling electric + water — r10's own Common-areas table puts
    both common areas on `Small Commercial` — with a stated base charge and a
    single open tier per service, so the two ruled figures are arithmetic over
    typed prices and not constants.
    """
    plan = make_plan(tenant, name=name, services=("electric", "water"))
    from apps.rating import selectors as rating_selectors

    prices = {
        "electric": (Decimal("12.00"), Decimal("0.200000"), "kWh"),
        "water": (Decimal("8.00"), Decimal("4.000000"), "kgal"),
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
        # ⚠ **`DEF-BIL-8470`'s SECOND LAYER, AND IT IS THE FIXTURE'S (2026-09-30).**
        # Once the ruled path asked the COVERED unit its size (the product half
        # of the defect), it found `E-1P-100` and refused it: this version stated
        # no size axis, and a banded service with none refuses every size by
        # name — the PO's own choice (`DEF-2816`, `state_size_axis`'s docstring).
        # The shared helper states the platform's ratified axis; it moves no
        # money (no pricing read touches `rate_size_rows`).
        state_size_axis(version, row["service_code"])
    # ⚠ **ADDED 2026-09-30 — RED SINCE 2026-09-28.** `DEF-BIL-7170` (PO: *"we
    # will never take default value from plan $8.0 - that is retired"*) made the
    # base come ONLY from the charge code, so the `base_charge` on the versions
    # above stopped being read: every case refused until 2026-09-30, then billed
    # a $0.00 base with a warning once a base nobody defined became $0.00
    # (`18e1069f2`). 1408 Elm read $49.60 against the signed $69.60. The SAME
    # figures are now declared where they live, so no asserted amount moves.
    from apps.tenancy import models as tenancy_models

    from tests.base_code_naming import name_base_code

    for service_code, (base, _unit_price, _uom) in prices.items():
        # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the code — an
        # unnamed schedule bills `$0.00` — so the signed figures still bill.
        name_base_code(
            tenant,
            rating_models.Charge.objects.create(
                tenant=tenant,
                code=f"BASE-{service_code.upper()}",
                name=f"{service_code.title()} base service",
                charge_type="recurring",
                amount_rule="flat",
                amount=base,
                service=tenancy_models.Service.objects.get(code=service_code),
                is_base=True,
            ),
        )
    return plan


def _cycle(tenant, code):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields; `window_start`/`window_end` were dropped
        # columns (metering 0021) and the window is derived from these two.
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        # ⚠ OQ-344 (RC-W6): `cycles.bill_date` is dropped (metering 0023). The
        # surviving default is the bill DAY, and a run with no typed date
        # resolves *"the bill day, in the month after the period ends"*.
        bill_day=1,
        due_days=21,
    )


def _common_area(actor, tenant, cycle, plan, premises, *, label, service, uom, asset_no, used):
    """One COMMON-AREA unit (BR-MET-101's flag), metered, in the cycle, on the
    plan, with one committed read."""
    unit = make_unit(
        actor,
        premises["id"],
        label=label,
        unit_type="common_area",
        is_common_area=True,
        services=[service],
    )
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service=service, uom=uom)
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    commit_read(
        actor,
        asset["id"],
        day=PERIOD_END.isoformat(),
        value=str(Decimal("1000") + Decimal(used)),
        prior_value="1000",
        consumption=str(Decimal(used)),
        unit=uom,
    )
    return unit


def elm_1408(actor, tenant, cycle, plan):
    """BR-MET-101's worked premises: 1408 Elm — 3 units + 2 common areas.

    ⚠ **THE METERS DO RECORD A CONNECTION SIZE** (`a_meter`'s default, the
    smallest ratified band: M-4109 `E-1P-100`, M-4110 `W-58`). `DEF-BIL-8285`
    said they did not; a probe of tc1 showed the refusal comes from the pricing
    path asking the size of the MASTER's own unit, which is NULL by design —
    `DEF-BIL-8470`, a product defect no fixture change can reach. It landed
    2026-09-30 (the ruled path now asks the covered unit that serves each
    service, as the live path does), and tc1/tc2 are green on it.
    """
    premises = make_premises(
        actor,
        address_line="1408 Elm St",
        premises_type="apartment_complex",
        owner_manager="Miller Property LLC",
        services_available=["electric", "water"],
    )
    for label in ("Unit A", "Unit B", "Unit C"):
        make_unit(actor, premises["id"], label=label)
    hallway = _common_area(
        actor,
        tenant,
        cycle,
        plan,
        premises,
        label="Hallway & exterior lighting",
        service="electric",
        uom="kWh",
        asset_no="M-4109",
        used="146.000000",
    )
    irrigation = _common_area(
        actor,
        tenant,
        cycle,
        plan,
        premises,
        label="Shared irrigation",
        service="water",
        uom="kgal",
        asset_no="M-4110",
        used="5.100000",
    )
    return premises, hallway, irrigation


def a_master(actor, premises):
    return customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": PERIOD_START.isoformat(),
            # ⛔ **`BR-CUS-1024` — THE MASTER DOOR IS GATED TOO, AND IT NEEDS A
            # `customer` BLOCK EVEN WITH NO `contact` IN THE PAYLOAD.** When one
            # is absent this door builds the contact from the premises' own
            # free-text `owner_manager` (PO 2026-08-22, *"payer = the premises'
            # owner/manager"*), so a party IS presented and the refusal fires —
            # which is why "no contact" is safe at `POST /accounts` and is NOT
            # safe here. The party named is therefore the owner the door would
            # otherwise have minted from, as a COMPANY: the seeded owner is
            # `Whitfield Rentals LLC` and a landlord is an organisation whatever
            # the account TYPE says. Same shape as every other fixture in the
            # repo: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )


def _run(tenant, cycle, key):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=key,
    )


def _by_service(invoice):
    """{service: Σ line amounts} — what the owner is actually charged, per
    service, across base and usage lines alike."""
    totals: dict[str, Decimal] = {}
    for line in invoice.lines.all():
        if line.kind not in ("base", "usage"):
            continue
        code = line.service.code if line.service_id else None
        totals[code] = totals.get(code, Decimal("0")) + line.amount
    return totals


# ══════════════════════════════════════════════════════════════════════════
# THE PIN
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_068_bill_tc1__one_master_bill_prices_every_covered_common_area(brazos, dana):
    """**$69.60 on ONE owner bill** (BR-MET-101 / BR-CUS-068, PO 2026-08-22).

    RED BEFORE THE FIX: the same fixture billed the ANCHOR's services only —
    the hallway's $41.20 plus the water BASE the plan bundle carried, and no
    irrigation usage at all — while the run additionally reported the covered
    irrigation unit as *"in this cycle but has no billable account"*.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-1")
        plan = _priced_plan(brazos)
        premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
        master = a_master(dana, premises)

        # ── THE LINKAGE THE FIGURES RIDE ON, REWRITTEN FOR `CR-056` W1.
        # It used to be *ONE row, ANCHORED on the first common area, covering
        # BOTH through its open agreements* — `assert master["unit_id"] ==
        # hallway["id"]`. Under `BR-CUS-1000` the account hangs off the ADDRESS
        # and covers BOTH common areas through its agreements, the hallway
        # included: the two shared spaces are things it is CHARGED FOR rather
        # than the thing it hangs off. **The $69.60 below did not move.**
        assert master["kind"] == customer_services.ACCOUNT_KIND_MASTER
        assert master["premises_id"] == premises["id"]
        assert master["unit_id"] is None

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        # DEF-572 — a covered common area is NOT a unit with nobody to bill.
        assert prepared.blocked == (), prepared.blocked
        assert len(prepared.ready) == 1
        assert prepared.ready[0].account_no == master["account_no"]

        invoice = runs.calculate_account(
            prepared.ready[0], bill_run=_run(brazos, cycle, "ma-pin"), service_date=SERVICE_DATE
        )

        # DEF-571 — the whole obligation, on one document.
        assert _by_service(invoice) == {"electric": HALLWAY, "water": IRRIGATION}
        assert invoice.subtotal == COMMON_BILL
        assert invoice.total == COMMON_BILL
        # ONE bill for the owner, never one per common area.
        assert billing_models.Invoice.objects.filter(account_id=master["id"]).count() == 1
        # And NO account hangs off either shared space — `CR-056` W1 makes that
        # true of the hallway too, where it used to be the anchor.
        assert customer_models.Account.objects.filter(unit_id=irrigation["id"]).count() == 0
        assert customer_models.Account.objects.filter(unit_id=hallway["id"]).count() == 0
        # The document can SAY what it covers, and the ORDER is unchanged by the
        # move off the anchor: `covered_unit_ids` sorts by (label, id), which puts
        # `Hallway & exterior lighting` before `Shared irrigation` exactly as
        # anchor-first did on this building.
        covered = prepared.ready[0].snapshot["covered_units"]
        assert [entry["unit_id"] for entry in covered] == [hallway["id"], irrigation["id"]]


# ══════════════════════════════════════════════════════════════════════════
# THE INVERSION — the pin proved RED by breaking exactly the hop it rests on
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_068_bill_tc2__anchor_only_coverage_bills_the_short_number(
    brazos, dana, monkeypatch
):
    """WHAT THE OWNER WAS BILLED BEFORE THIS LANE, measured rather than
    remembered (CLAUDE.md law 7 — prove the guard RED).

    The ONE hop is disabled — customers' coverage read is made to answer the
    anchor alone, which is exactly what `gather.py` did until 2026-08-22 — and
    the same fixture is billed again. The bill that comes out is **$49.20**:
    the hallway's whole $41.20 plus the water BASE the plan bundle carries,
    with the shared irrigation's 5.1 kgal measured by nobody. It foots, it
    prints, and it is short by **$20.40** of usage the utility supplied.

    ⚠ The run ALSO reports the covered irrigation unit as *"in this cycle but
    has no billable account"* (DEF-572) — a false alarm about a unit that IS
    billed, sitting on the exception tab beside the true ones.

    ⚠ **HOW THE HOP IS DISABLED CHANGED WITH `CR-056` W1, AND THE MEASUREMENT
    DID NOT.** The old inversion made the coverage read answer
    `[account.unit_id]` — the ANCHOR alone. There is no anchor any more
    (`BR-CUS-1000`: the account hangs off the address and `unit_id` is NULL), so
    the same read is made to answer **the FIRST covered unit and nothing else**,
    which on this building is the identical unit — the hallway — and therefore
    the identical bill. Making it answer `[]` instead would test something else
    entirely: an account the run cannot even find.
    """
    from apps.customers import selectors as customer_selectors

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "MA-2")
        plan = _priced_plan(brazos)
        premises, hallway, irrigation = elm_1408(dana, brazos, cycle, plan)
        a_master(dana, premises)

        whole_coverage = customer_selectors.covered_unit_ids
        monkeypatch.setattr(
            customer_selectors,
            "covered_unit_ids",
            lambda account: list(whole_coverage(account))[:1],
        )
        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        # DEF-572 — the covered common area reported as having nobody to bill.
        assert [problem.unit_id for problem in prepared.blocked] == [irrigation["id"]]
        assert prepared.blocked[0].reason == runs.RUN_UNIT_HAS_NO_ACCOUNT

        # …and the bill cannot even be PRODUCED: the plan bundles water, the
        # anchor has no water meter, and the irrigation's read is invisible —
        # so water is a missing read nobody decided (BR-BIL-015).
        # …and the bill that comes out is SHORT by the whole irrigation. ⚠
        # **THIS READ `pytest.raises(GatherProblem)` — "water is a missing read
        # nobody decided" — UNTIL 2026-09-30**, when the PO ruled that a service
        # with no asset is NOT IN SERVICE: no tariff, no line (bulk-run changes
        # row 2). The anchor has no water meter, so water is simply not billed,
        # and the anchor-only bill is the hallway alone: **$41.20, short by the
        # irrigation's $28.40** of the signed $69.60. Seen by `DEF-BIL-8470`'s
        # lane, which was the first to reach this line in a month (tc2 had been
        # red one assertion earlier since R3 was switched on).
        invoice = runs.calculate_account(
            prepared.ready[0],
            bill_run=_run(brazos, cycle, "ma-red"),
            service_date=SERVICE_DATE,
        )
        kinds = set(
            billing_models.InvoiceLine.objects.filter(invoice=invoice).values_list(
                "description", flat=True
            )
        )
        assert invoice.total == HALLWAY
        assert COMMON_BILL - invoice.total == IRRIGATION
        assert not any("water" in kind for kind in kinds)

        # The most the clerk could get out of the product for this building —
        # decide water away, or scope the run to the anchor's own service — is
        # the hallway's **$41.20**, and the shared irrigation's **$28.40** is
        # billed to nobody at all. That gap IS DEF-571.
        electric_only = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
            scope_services=("electric",),
        )
        invoice = runs.calculate_account(
            electric_only.ready[0],
            bill_run=_run(brazos, cycle, "ma-red-electric"),
            service_date=SERVICE_DATE,
        )
        assert _by_service(invoice) == {"electric": HALLWAY}
        assert invoice.total == HALLWAY
        assert invoice.total != COMMON_BILL
        assert (
            billing_models.InvoiceLine.objects.filter(
                invoice=invoice, service__code="water"
            ).exists()
            is False
        )
