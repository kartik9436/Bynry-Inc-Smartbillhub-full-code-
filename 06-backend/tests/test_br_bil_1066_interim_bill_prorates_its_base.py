# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-10-01 (decision log "TWO PO RULINGS ON THE BASE CHARGE", (1)),
#          verbatim: *"Should interim bills cut the base down like first and
#          final bills? A · Cut down (10/30)"* — OQ-242 option (a), CLOSED for
#          interim bills.
# Rules:   BR-BIL-1066 · B4.3 ❄️ (calendar-day proration, base always prorated)
# Golden:  WE-6 ❄️ — 20 days of a 31-day cycle prorates the bases 12.00 / 8.00 /
#          18.00 to 7.74 / 5.16 / 11.61 = 24.51
# Reuses:  final_bill._closing_cycle_days (via one_time._the_accounts_cycle_days),
#          the first bill's no-cycle refusal and its key (DEF-BIL-8330)
# ───────────────────────────────────────────────────────
"""An INTERIM bill cuts its base charge down by days, like a first and final bill.

THE PO'S CASE. An interim bill for 10 days of a 30-day cycle on a $30.50 base
charged the whole $30.50, because the one-time door passed the WINDOW's length
as the cycle length (a factor of 1). Ruled: 10/30 × $30.50 = **$10.17**.

WE-6's frozen figures, through the same path: 20 days of a 31-day cycle →
**7.74 / 5.16 / 11.61 = $24.51** (it charged 12.00 / 8.00 / 18.00 = $38.00).

An account on NO cycle has no length to divide by; its interim bill is refused
the first bill's way rather than falling back to the window (factor 1) in
silence.

Written RED FIRST (law 7): before the fix the preview and the draft charged
$30.50 and the no-cycle interim bill was priced.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import one_time, one_time_answer
from apps.billing.exceptions import BillingRuleError
from apps.customers import models as customer_models
from apps.rating import engine as rating_engine
from apps.rating import models as rating_models
from core import sample_fixture as fixture
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

KEY = one_time.NO_BILLING_CYCLE_KEY
CENT = Decimal("0.01")

PO_BASE = Decimal("30.50")
PO_PRORATED = Decimal("10.17")  # 10/30 × 30.50 — PO 2026-10-01
PO_FROM, PO_TO = date(2026, 9, 21), date(2026, 9, 30)  # 10 days of a 30-day September

#: ❄️ WE-6 — base → its 20/31 share. Changing any of these is a finance re-sign.
WE6 = {
    Decimal("12.00"): Decimal("7.74"),
    Decimal("8.00"): Decimal("5.16"),
    Decimal("18.00"): Decimal("11.61"),
}
WE6_TOTAL = Decimal("24.51")
WE6_FROM, WE6_TO = date(2026, 8, 12), date(2026, 8, 31)  # 20 days of a 31-day August


@pytest.fixture
def a_monthly_cycle(monkeypatch):
    """The unit bills on ONE calendar-month cycle, read through metering's own
    seams — the card's cycle and the period the denominator comes from."""
    from apps.metering import selectors as metering_selectors

    def period(unit_id, as_of=None):
        last = calendar.monthrange(as_of.year, as_of.month)[1]
        return {
            "start": as_of.replace(day=1).isoformat(),
            "end": as_of.replace(day=last).isoformat(),
        }

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-MONTH", "name": "Monthly", "due_days": 21},
    )
    monkeypatch.setattr(metering_selectors, "billing_period_for_unit", period)


def _account_with_base(brazos, dana, base: Decimal):
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=base)
        rating_models.Charge.objects.filter(
            tenant=brazos, is_base=True, service__code="water"
        ).update(amount=base)
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 7, 1))
    return account, asset


def _interim(account, start: date, end: date, **overrides):
    body = {
        "account_id": str(account.id),
        "kind": "interim",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "bill_date": end.isoformat(),
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _typed(asset, on: date):
    return [
        {
            "asset_id": str(asset["id"]),
            "read_at": on.isoformat(),
            "value": "1240",
            "role": "current",
        }
    ]


def _base_amounts(body) -> list[Decimal]:
    return [
        Decimal(line["amount"]).quantize(CENT)
        for group in body["bill"]["groups"]
        for line in group["lines"]
        if line["charge"] == "base"
    ]


def _keys(response):
    return [(row["field"], row["message_key"]) for row in response.data.get("field_errors") or ()]


# ── the engine: B4.3's own arithmetic on the ruled figures ──────────────────
@pytest.mark.parametrize("base,expected", list(WE6.items()))
def test_the_engine_prorates_we6s_bases_over_20_of_31_days(base, expected):
    period = type("P", (), {"cycle_days": 31, "service_days": 20})()
    assert rating_engine.prorate_base_charge(base_charge=base, period=period) == expected
    assert sum(WE6.values()) == WE6_TOTAL


def test_the_engine_prorates_the_pos_case_10_of_30():
    period = type("P", (), {"cycle_days": 30, "service_days": 10})()
    assert rating_engine.prorate_base_charge(base_charge=PO_BASE, period=period) == PO_PRORATED


# ── the one-time interim path ───────────────────────────────────────────────
def test_the_interim_preview_charges_10_of_30(brazos, dana, a_monthly_cycle):
    account, asset = _account_with_base(brazos, dana, PO_BASE)
    response = _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        _interim(account, PO_FROM, PO_TO, readings=_typed(asset, PO_TO)),
    )
    assert response.status_code == 200, response.data
    assert _base_amounts(response.data) == [PO_PRORATED], response.data["bill"]


def test_the_interim_draft_charges_10_of_30(brazos, dana, a_monthly_cycle):
    account, asset = _account_with_base(brazos, dana, PO_BASE)
    with tenant_ctx(brazos):
        commit_read(
            dana,
            asset["id"],
            day=PO_TO.isoformat(),
            value="1240",
            prior_value="1200",
            consumption=Decimal("40"),
            unit=fixture.WATER_UOM,
            days_since_prior=64,
        )
    response = _post(
        billing_api.one_time_create, brazos, _clerk(brazos), _interim(account, PO_FROM, PO_TO)
    )
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.order_by("-created_at").first()
        bases = [
            Decimal(amount).quantize(CENT)
            for amount in billing_models.InvoiceLine.objects.filter(
                invoice=invoice, kind="base"
            ).values_list("amount", flat=True)
        ]
    assert bases == [PO_PRORATED], bases


def test_the_interim_preview_reproduces_we6_24_51(brazos, dana, a_monthly_cycle):
    """WE-6 ❄️ — each of its three bases, 20 days of a 31-day cycle, through the
    interim path; their sum is the frozen $24.51 (it was $38.00)."""
    account, asset = _account_with_base(brazos, dana, Decimal("12.00"))
    got = []
    for base in WE6:
        with tenant_ctx(brazos):
            rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=base)
            rating_models.Charge.objects.filter(
                tenant=brazos, is_base=True, service__code="water"
            ).update(amount=base)
        response = _post(
            billing_api.one_time_preview,
            brazos,
            _clerk(brazos),
            _interim(account, WE6_FROM, WE6_TO, readings=_typed(asset, WE6_TO)),
        )
        assert response.status_code == 200, response.data
        got.extend(_base_amounts(response.data))
    assert got == list(WE6.values()), got
    assert sum(got) == WE6_TOTAL


def test_a_whole_cycle_interim_still_charges_the_whole_base(brazos, dana, a_monthly_cycle):
    """Sep 1–30 on a 30-day cycle is 30/30 = 1 — J74 cases 1 and 2 do not move."""
    account, asset = _account_with_base(brazos, dana, PO_BASE)
    response = _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        _interim(account, date(2026, 9, 1), PO_TO, readings=_typed(asset, PO_TO)),
    )
    assert response.status_code == 200, response.data
    assert _base_amounts(response.data) == [PO_BASE], response.data["bill"]


# ── no cycle: refused, the first bill's way ─────────────────────────────────
@pytest.fixture
def cycle_less(brazos, dana):
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        assert one_time_answer.account_facts(str(account.id))["cycle_name"] is None
    return account


@pytest.mark.parametrize("view", ["one_time_preview", "one_time_create"])
def test_an_interim_bill_with_no_cycle_is_refused_on_the_account(brazos, dana, cycle_less, view):
    response = _post(
        getattr(billing_api, view),
        brazos,
        _clerk(brazos),
        _interim(cycle_less, date(2026, 7, 1), date(2026, 7, 31)),
    )
    assert response.status_code == 422, response.data
    assert ("account_id", KEY) in _keys(response), response.data
    assert response.data.get("message_key") == KEY, response.data


def test_the_engine_refuses_the_interim_preview_and_draft_by_its_key(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        before = billing_models.Invoice.objects.count()
        request = one_time_answer.request_from(
            _interim(cycle_less, date(2026, 7, 1), date(2026, 7, 31))
        )
        with pytest.raises(BillingRuleError) as previewed:
            one_time.preview(request)
        with pytest.raises(BillingRuleError) as drafted:
            one_time.create(request, run_by=None, actor=None)
        assert billing_models.Invoice.objects.count() == before
    assert previewed.value.message_key == KEY
    assert drafted.value.message_key == KEY


def test_the_scope_is_interim_only():
    assert one_time.KINDS_NEEDING_A_CYCLE == (
        one_time.KIND_FIRST,
        one_time.KIND_FINAL,
        one_time.KIND_INTERIM,
    )
    for kind in (one_time.KIND_BACKBILL, one_time.KIND_PENALTY, one_time.KIND_FEE):
        assert kind not in one_time.KINDS_NEEDING_A_CYCLE
