# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-10-01 (decision log "SIX PO RULINGS IN ONE MESSAGE", (4)),
#          verbatim: *"show warning and A · Refuse until the account has a
#          cycle (same as first bill)"*.
# Reuses:  DEF-BIL-8330 (2.416.1) — the first bill's refusal, its key and its
#          step-1 problem on the account field.
# Rules:   BR-BIL-013 (final bill prorated through the move day, B4.3) ·
#          BR-CUS-056
# ───────────────────────────────────────────────────────
"""A FINAL bill for an account with no billing cycle is refused, like a first bill.

THE PO'S CASE. Maria moves out on the 10th. Her account is on no cycle, so a
final bill had no cycle length to prorate over and fell back to the window's
own length — a factor of 1 — and charged the whole month's **$30.50** base for
ten days. With a 30-day cycle it would be 10/30 × $30.50 = $10.17. The PO chose
to refuse it, with a warning, until the account has a cycle.

Written RED FIRST (law 7): the preview and the draft both refused nothing.
"""

from __future__ import annotations

import pytest

from apps.billing import api as billing_api
from apps.billing import one_time, one_time_answer
from apps.billing import models as billing_models
from apps.billing.exceptions import BillingRuleError
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

KEY = one_time.NO_BILLING_CYCLE_KEY


def _final_body(account, **overrides):
    """Maria's case: a final bill Jul 1 → moved out Jul 10."""
    body = {
        "account_id": str(account.id),
        "kind": "final",
        "period_start": "2026-07-01",
        "period_end": "2026-07-10",
        "bill_date": "2026-07-10",
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _keys(response):
    return [(row["field"], row["message_key"]) for row in response.data.get("field_errors") or ()]


@pytest.fixture
def cycle_less(brazos, dana):
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        assert one_time_answer.account_facts(str(account.id))["cycle_name"] is None
    return account


@pytest.fixture
def on_a_cycle(monkeypatch):
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )
    monkeypatch.setattr(
        metering_selectors,
        "billing_period_for_unit",
        lambda unit_id, as_of=None: {"start": "2026-07-01", "end": "2026-07-30"},
    )


@pytest.mark.parametrize("view", ["one_time_preview", "one_time_create"])
def test_final_bill_with_no_cycle_is_refused_on_the_account(brazos, dana, cycle_less, view):
    response = _post(getattr(billing_api, view), brazos, _clerk(brazos), _final_body(cycle_less))
    assert response.status_code == 422, response.data
    assert ("account_id", KEY) in _keys(response), response.data
    assert response.data.get("message_key") == KEY, response.data


def test_final_bill_with_no_cycle_drafts_nothing(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        before = billing_models.Invoice.objects.count()
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), _final_body(cycle_less))
    assert response.data.get("message_key") == KEY, response.data
    with tenant_ctx(brazos):
        assert billing_models.Invoice.objects.count() == before


def test_the_step_1_warning_is_raised_for_a_final_bill(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        problems = one_time_answer.account_problems(_final_body(cycle_less))
    assert problems == [{"field": "account_id", "code": problems[0]["code"], "message_key": KEY}]


def test_the_engine_refuses_the_final_preview_and_draft_by_its_key(brazos, dana, cycle_less):
    with tenant_ctx(brazos):
        before = billing_models.Invoice.objects.count()
        request = one_time_answer.request_from(_final_body(cycle_less))
        with pytest.raises(BillingRuleError) as previewed:
            one_time.preview(request)
        with pytest.raises(BillingRuleError) as drafted:
            one_time.create(request, run_by=None, actor=None)
        assert billing_models.Invoice.objects.count() == before
    assert previewed.value.message_key == KEY
    assert drafted.value.message_key == KEY


def test_the_same_accounts_fee_bill_is_not_refused_for_its_cycle(brazos, dana, cycle_less):
    """An INTERIM bill until 2026-10-01 — now refused too (`BR-BIL-1066`, its own
    test file). A fee bill has no base and is not refused for a missing cycle."""
    response = _post(
        billing_api.one_time_preview,
        brazos,
        _clerk(brazos),
        _final_body(cycle_less, kind="fee", period_start="2026-07-31", period_end="2026-07-31",
                    bill_date="2026-07-31", charge_code="RECON"),
    )
    assert ("account_id", KEY) not in _keys(response), response.data
    assert response.data.get("message_key") != KEY, response.data


def test_a_final_bill_on_a_cycle_is_not_refused_for_it(brazos, dana, cycle_less, on_a_cycle):
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), _final_body(cycle_less))
    assert ("account_id", KEY) not in _keys(response), response.data
    assert response.data.get("message_key") != KEY, response.data
