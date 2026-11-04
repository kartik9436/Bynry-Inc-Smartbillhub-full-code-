# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-10-01 (decision log "SIX PO RULINGS IN ONE MESSAGE", (2)),
#          verbatim: *"B · Price each meter separately"* — against the
#          recommendation (A: add the two and price the total once).
# Rows:    BULK-CHG-46 · BULK-CHG-60
# Rules:   BR-BIL-1062 (supersedes the 2026-09-30 judgment "one line, one
#          ladder" in runs._meter_swap) · BR-RAT-002 (tiers reset each bill)
# Code:    apps/billing/runs.py (_meter_swap → one reading per meter part) ·
#          apps/billing/gather.py (_tariffs_for_plan: a swapped service's
#          later meter carries no base)
# ───────────────────────────────────────────────────────
"""A meter swapped mid-month: each meter is priced as its own meter.

THE WORKED FIGURES (written before the fix, red first — law 7)
--------------------------------------------------------------
Tiers: 0–100 kWh at $0.10, above 100 at $0.15. The May bill closed the OLD
meter at 13,500; on 10 June it came out at 13,620; the NEW meter went in at 0
and reads 80 on 29 June.

    old meter  120 kWh   100 × $0.10 + 20 × $0.15 = $13.00
    new meter   80 kWh    80 × $0.10              =  $8.00
    the bill                                        **$21.00**

Priced once, as the 2026-09-30 judgment did, 200 kWh would be
100 × $0.10 + 100 × $0.15 = **$25.00** — $4.00 more, because the new meter's
80 kWh would start in the second tier. Each meter climbs the tiers from the
bottom. The fixture binds no base charge; the one-base judgment is pinned below
with a base of its own.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import runs
from apps.rating import models as rating_models

from tests.test_def_bil_8244_meter_swapped_both_parts import ACCEPT_FOR_ALL, a_swapped_meter
from tests.test_us_bil_004_run_loop import a_run, prepared_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _tiered(tenant):
    """Make every electric version a two-tier ladder: 0–100 @ $0.10, 100+ @ $0.15."""
    for version in rating_models.TariffVersion.objects.filter(tenant=tenant):
        version.model = "tiered"
        version.save(update_fields=["model"])
        rating_models.RateTier.objects.filter(tenant=tenant, tariff_version=version).update(
            to_qty=Decimal("100"), unit_price=Decimal("0.10")
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=2,
            from_qty=Decimal("100"),
            to_qty=None,
            unit_price=Decimal("0.15"),
        )


def _draft(tenant, actor, *, no, name_base=None):
    case = a_swapped_meter(tenant, actor, new_value="80", no=no)
    _tiered(tenant)
    if name_base is not None:
        # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES the base code — an
        # unnamed schedule bills a `$0.00` base.
        from tests.base_code_naming import name_base_code

        name_base_code(tenant, name_base)
    token = runs.open_answers(ACCEPT_FOR_ALL)
    try:
        prepared = prepared_for(case.cycle)
        result = runs.calculate_run(prepared, bill_run=a_run(tenant, case.cycle))
    finally:
        runs.close_answers(token)
    assert result.drafted_count == 1 and result.breaks == (), result.breaks
    invoice = billing_models.Invoice.objects.get(
        account=case.account, status=billing_models.INVOICE_DRAFT
    )
    return case, invoice


def test_each_meter_climbs_the_tiers_from_the_bottom_21_00_not_25_00(brazos, dana):
    with tenant_ctx(brazos):
        _case, invoice = _draft(brazos, dana, no="6280")
        usage = billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="usage")
        by_meter: dict[str, Decimal] = {}
        for line in usage:
            by_meter[str(line.asset_id)] = by_meter.get(str(line.asset_id), Decimal("0")) + line.amount
    assert invoice.total == Decimal("21.00")
    assert sorted(v.quantize(Decimal("0.01")) for v in by_meter.values()) == [
        Decimal("8.00"),
        Decimal("13.00"),
    ]


def test_each_meter_is_its_own_line_with_its_own_reading(brazos, dana):
    with tenant_ctx(brazos):
        case, invoice = _draft(brazos, dana, no="6281")
    services = [s for s in invoice.bill_payload["services"] if s["code"] == "electric"]
    assert len(services) == 2
    assert all(len(s["meter_parts"]) == 1 for s in services)
    parts = sorted(
        (Decimal(s["meter_parts"][0]["from"]), Decimal(s["meter_parts"][0]["to"]), s["read_id"])
        for s in services
    )
    assert parts == [
        (Decimal("0"), Decimal("80"), str(case.new_read.id)),
        (Decimal("13500"), Decimal("13620"), str(case.old_final.id)),
    ]


def test_a_swap_charges_one_base_not_two(brazos, dana):
    """One connection over one period: the base is charged once, on the old
    meter's line (decision log 2026-10-01, judgment (2))."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        swap_base = rating_models.Charge.objects.create(
            tenant=brazos,
            code="BASE-ELECTRIC-SWAP",
            name="Electric base",
            charge_type="recurring",
            amount_rule="flat",
            amount=Decimal("10.00"),
            service=tenancy_models.Service.objects.get(code="electric"),
            is_base=True,
        )
        _case, invoice = _draft(brazos, dana, no="6282", name_base=swap_base)
        bases = list(
            billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="base").values_list(
                "amount", flat=True
            )
        )
    assert [b.quantize(Decimal("0.01")) for b in bases] == [Decimal("10.00")]
    assert invoice.total == Decimal("31.00")


def test_the_worked_figures_foot():
    assert Decimal("100") * Decimal("0.10") + Decimal("20") * Decimal("0.15") == Decimal("13.00")
    assert Decimal("80") * Decimal("0.10") == Decimal("8.00")
    assert Decimal("100") * Decimal("0.10") + Decimal("100") * Decimal("0.15") == Decimal("25.00")
