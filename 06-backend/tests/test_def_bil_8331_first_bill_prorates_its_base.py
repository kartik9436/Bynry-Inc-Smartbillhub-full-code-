"""DEF-BIL-8331 — a first bill prorates its base charge from the move-in day.

Signed law, not a question (decision log 2026-09-30, coordinator under BR-BIL-012
and the ❄️ frozen B5 figure): BR-BIL-012 reads *"First bill: prorated from
move-in day (B4.3)"*, and GT-3's worked figure is **move-in day 16 of 30; base
$30.50; 15/30 × 30.50 = $15.25**.

The fault: the one-time door passed the bill's OWN window length as the cycle
length (`_cycle_days(request) or (period_end − period_start) + 1`), so the factor
was always 1 and a first bill charged the whole month's base however few days it
covered — the PO's *"$418.00 for one day"* and J74's *"bases whole"*.

The fix reads the cycle length the way the final bill already does
(`final_bill._closing_cycle_days`, metering's `billing_period_for_unit`), on the
move-in day. These cases put GT-3's own figures through the one-time first-bill
path — the preview AND the draft — and were written RED FIRST (law 7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.rating import models as rating_models
from core import sample_fixture as fixture
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

GT3_BASE = Decimal("30.50")
GT3_PRORATED = Decimal("15.25")  # 15/30 × 30.50 — ❄️ B5 GT-3
MOVE_IN = date(2026, 9, 16)  # day 16 of a 30-day September cycle
TO = date(2026, 9, 30)


@pytest.fixture
def september_cycle(monkeypatch):
    """The unit bills on ONE 30-day cycle, Sep 1–30, read through metering's own
    seams (the card's cycle and the period the denominator comes from)."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-SEP", "name": "September", "due_days": 21},
    )
    monkeypatch.setattr(
        metering_selectors,
        "billing_period_for_unit",
        lambda unit_id, as_of=None: {"start": "2026-09-01", "end": "2026-09-30"},
    )


@pytest.fixture
def gt3_account(brazos, dana):
    """GT-3's base, $30.50, on the water plan; moved in Sep 16."""
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=GT3_BASE)
        rating_models.Charge.objects.filter(tenant=brazos, is_base=True, service__code="water").update(
            amount=GT3_BASE
        )
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=MOVE_IN)
    return account, asset


def _first(account, **overrides):
    body = {
        "account_id": str(account.id),
        "kind": "first",
        "period_start": MOVE_IN.isoformat(),
        "period_end": TO.isoformat(),
        "bill_date": TO.isoformat(),
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _base_amounts(body) -> list[Decimal]:
    return [
        Decimal(line["amount"])
        for group in body["bill"]["groups"]
        for line in group["lines"]
        if line["charge"] == "base"
    ]


def test_def_bil_8331__the_preview_charges_gt3s_prorated_base(brazos, dana, september_cycle, gt3_account):
    account, asset = gt3_account
    typed = [{"asset_id": str(asset["id"]), "read_at": TO.isoformat(), "value": "1240", "role": "current"}]
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), _first(account, readings=typed))
    assert response.status_code == 200, response.data
    assert _base_amounts(response.data) == [GT3_PRORATED], response.data["bill"]


def test_def_bil_8331__the_draft_charges_gt3s_prorated_base(brazos, dana, september_cycle, gt3_account):
    account, asset = gt3_account
    with tenant_ctx(brazos):
        commit_read(
            dana,
            asset["id"],
            day=TO.isoformat(),
            value="1240",
            prior_value="1200",
            consumption=Decimal("40"),
            unit=fixture.WATER_UOM,
            days_since_prior=64,
        )
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), _first(account))
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.order_by("-created_at").first()
        bases = [
            Decimal(amount).quantize(Decimal("0.01"))
            for amount in billing_models.InvoiceLine.objects.filter(invoice=invoice, kind="base").values_list(
                "amount", flat=True
            )
        ]
    assert bases == [GT3_PRORATED], bases


def test_def_bil_8331__an_interim_bill_now_prorates_the_same_way(brazos, dana, september_cycle, gt3_account):
    """⚠ REVERSED 2026-10-01. This pinned *"an interim one-time bill is NOT
    prorated"* (OQ-242 withdrawn, 2026-08-23). The PO has since ruled the
    interim base is cut down like the first bill's — *"A · Cut down (10/30)"*,
    `BR-BIL-1066` — so the same Sep 16–30 window on the same 30-day cycle is
    15/30 × 30.50 = 15.25 on an interim bill too."""
    account, asset = gt3_account
    typed = [{"asset_id": str(asset["id"]), "read_at": TO.isoformat(), "value": "1240", "role": "current"}]
    response = _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        _first(account, kind="interim", readings=typed),
    )
    assert response.status_code == 200, response.data
    assert [amount.quantize(Decimal("0.01")) for amount in _base_amounts(response.data)] == [
        GT3_PRORATED
    ], response.data["bill"]
