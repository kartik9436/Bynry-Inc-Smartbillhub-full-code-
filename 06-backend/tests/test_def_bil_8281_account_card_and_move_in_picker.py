# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-034 TC-5 (the account card) · US-BIL-010 TC-6 (the move-in
#           date — SUPERSEDED for the screen by the PO change of 2026-09-30)
#           Screens: S30 (the one-time bill, step 1)
# Defect:   DEF-BIL-8281 — the account card read '—' until a preview answered
# Change:   decision log 2026-09-30 *"ONE-TIME FIRST BILL: THE MOVE-IN DATE IS A
#           DATE PICKER THE CLERK CAN OVERWRITE"* — PO verbatim, *"Move -date
#           should have date picker cleark will overwrite it"*
# ───────────────────────────────────────────────────────
"""Step 1 reads the account from the account, and a first bill takes the clerk's date.

1. `GET /billing/one-time/accounts/{id}` answers the card — plan, days to pay,
   last bill, move-in date — with NO preview, so a step 1 whose preview is
   refused (a field still empty) still shows who the account is.
2. A first bill's `period_start` is the move-in date THE CLERK left: a date
   other than the account's recorded one is priced, not refused, and the
   account's recorded date is not changed.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.billing import api as billing_api
from apps.customers import models as customer_models
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def test_def_bil_8281__the_account_card_is_read_from_the_account_without_a_preview(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 7, 12))
    response = api_call(
        billing_api.one_time_account,
        "get",
        user=user,
        role="billing_clerk",
        tenant=brazos,
        account_id=str(account.id),
    )
    assert response.status_code == 200, response.data
    card = response.data
    assert card["account_no"] == "SCW-0001"
    assert card["plan"], "the unit's plan names the card's Plan"
    assert card["moved_in_on"] == "2026-07-12"
    assert "cycle_due_days" in card and "last_bill_on" in card


def test_def_bil_8281__an_account_with_no_move_in_date_still_names_its_plan_and_cycle(brazos, dana):
    """PO, verbatim: *"even if you dont find the move in date you should pull
    plan and cycle"*. Only the move-in field is empty; nothing else on the card
    is missing because of it."""
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=None)
    response = api_call(
        billing_api.one_time_account,
        "get",
        user=user,
        role="billing_clerk",
        tenant=brazos,
        account_id=str(account.id),
    )
    assert response.status_code == 200, response.data
    card = response.data
    assert card["moved_in_on"] is None
    assert card["plan"], "the plan is the unit's, whatever the move-in date"
    assert card["account_no"] == "SCW-0001" and card["status_name"]
    assert card["balance"] is not None or card["currency"]


def test_po_20260930__a_first_bill_prices_from_the_clerks_move_in_date(brazos, dana, monkeypatch):
    # `DEF-BIL-8330` (PO 2026-09-30, option A) — a first bill needs a billing
    # cycle; this fixture's unit is on none, so it is put on one through the
    # same metering seam the card and the refusal read.
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        # Recorded Aug 5; the clerk bills from Jul 5 — the recorded date is not
        # even inside this window, which is what the old check refused.
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 8, 5))
    body = {
        "account_id": str(account.id),
        "kind": "first",
        "period_start": "2026-07-05",
        "period_end": "2026-07-31",
        "bill_date": "2026-07-31",
        "due_days": 21,
    }
    response = _post(billing_api.one_time_preview, brazos, user, body)
    assert response.status_code == 200, response.data
    assert response.data["account"]["moved_in_on"] == "2026-08-05", "the account's record"
    charges = response.data["move_in_charges"]
    assert charges is not None and charges["moved_in_on"] == "2026-07-05", "the bill's date"
    with tenant_ctx(brazos):
        assert customer_models.Account.objects.get(pk=account.pk).opened_at == date(2026, 8, 5)
