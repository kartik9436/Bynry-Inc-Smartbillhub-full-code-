# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (interim) TC-11, TC-21 · US-BIL-010 · US-BIL-011
#           Screens: S30 (the one-time bill, step 1 → step 2)
# Defects:  DEF-BIL-8300 — step 1 refused until the period's reading was SAVED,
#           and step 2 is where it is typed (a deadlock) ·
#           DEF-BIL-8320 — two meters on one point shared one typed value
# Contract: 04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md §2
#           request `readings[]` — *"values typed but not yet saved, priced as
#           provisional"*
# ───────────────────────────────────────────────────────
"""The preview answers a meter still waiting for its reading, and prices a typed one.

The J70 walk found the one-time bill could not leave step 1 for any account
whose meters had no reading inside the period: the preview answered `422
missing_read_undecided_at_calculate`, and the reading that would cure it is
typed on step 2. These cases pin the four answers that replace it:

  1. no reading in the period, nothing typed → `200`, the meter's row
     *waiting*, and a bill with NO total (never `0.00`);
  2. a value typed on step 2 → priced PROVISIONALLY through Meter Reads' own
     overlay: the row *accepted*, the usage line 60 kgal (1,260 − 1,200);
  3. a typed value below the last reading → refused ON ITS ROW (*Below last
     reading*), still `200`;
  4. the DRAFT is not changed: with nothing saved it still refuses.

And `DEF-BIL-8320`: two in-service meters on one water point each take their
own typed value.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import one_time_answer, runs
from apps.metering import selectors as metering_selectors
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _the_unit_bills_on_a_cycle(monkeypatch):
    """`BR-BIL-1066` (PO 2026-10-01) — an interim bill for an account on no
    billing cycle is now REFUSED (*"No billing cycle. Assign one on the
    account."*). This file's interim cases are about something else, so their
    unit is put on a cycle through the same metering seam the card and the
    refusal read. Only the cycle's NAME is given, not its calendar, so the
    denominator falls back to the window's own length and no figure here moves.
    """
    from apps.metering import selectors as _metering_selectors

    monkeypatch.setattr(
        _metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )

AUG_1 = date(2026, 8, 1)
AUG_31 = date(2026, 8, 31)


def _august(account, **overrides):
    body = {
        "account_id": str(account.id),
        "kind": "interim",
        "period_start": AUG_1.isoformat(),
        "period_end": AUG_31.isoformat(),
        "bill_date": AUG_31.isoformat(),
        "due_days": 21,
    }
    body.update(overrides)
    return body


def _typed(asset, value):
    return [
        {"asset_id": str(asset["id"]), "read_at": AUG_31.isoformat(), "value": value, "role": "current"}
    ]


def test_def_bil_8300__the_waiting_reason_is_the_runs_own_constant():
    assert runs.CALC_UNRESOLVED_READ in one_time_answer.PREVIEW_WAITS_FOR_A_READING


def test_def_bil_8300__a_meter_with_no_reading_in_the_period_answers_waiting_not_refused(
    brazos, dana
):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
    response = _post(billing_api.one_time_preview, brazos, user, _august(account))
    assert response.status_code == 200, response.data
    body = response.data
    assert [row["status"] for row in body["readings"]["rows"]] == ["waiting"]
    assert body["services"] and body["rates"], "step 2's tables are what the clerk types beside"
    assert body["bill"]["total"] is None, "no total — never 0.00 on a bill preview"
    assert body["bill"]["groups"] == []
    assert body["waiting_for"]["reason"] == runs.CALC_UNRESOLVED_READ


def test_def_bil_8300__a_first_bill_waiting_for_its_reading_answers_waiting_too(
    brazos, dana, monkeypatch
):
    """The same deadlock on a FIRST bill: with no reading inside the window the
    engine's no-prior-read refusal (BR-BIL-062) fired at step 1 — before the
    clerk could type the reading on step 2. J70 re-walk, Unit C."""
    from datetime import date as _date

    from apps.customers import models as customer_models
    from apps.metering import selectors as metering_selectors

    # `DEF-BIL-8330` (PO 2026-09-30, option A) — a first bill needs a billing
    # cycle; this fixture's unit is on none, so it is put on one through the
    # same metering seam the card and the refusal read.
    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )

    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, _asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=_date(2026, 8, 1))
    body = _august(account, kind="first")
    response = _post(billing_api.one_time_preview, brazos, user, body)
    assert response.status_code == 200, response.data
    assert [row["status"] for row in response.data["readings"]["rows"]] == ["waiting"]
    assert response.data["bill"]["total"] is None


def test_def_bil_8300__a_typed_reading_prices_the_preview_provisionally(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
    response = _post(
        billing_api.one_time_preview,
        brazos,
        user,
        _august(account, readings=_typed(asset, "1260")),
    )
    assert response.status_code == 200, response.data
    body = response.data
    row = body["readings"]["rows"][0]
    assert row["status"] == "accepted"
    assert row["current"]["value"] == "1260"
    lines = [line for group in body["bill"]["groups"] for line in group["lines"]]
    usage = [line for line in lines if line["charge"] == "usage"]
    # The water plan is tiered, so the 60 kgal may arrive as one line per tier.
    assert usage and sum(Decimal(line["quantity"]) for line in usage) == Decimal("60"), usage
    assert Decimal(body["bill"]["total"]) > 0
    assert "waiting_for" not in body


def test_def_bil_8300__a_typed_reading_below_the_last_is_refused_on_its_row(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
    response = _post(
        billing_api.one_time_preview,
        brazos,
        user,
        _august(account, readings=_typed(asset, "1100")),
    )
    assert response.status_code == 200, response.data
    row = response.data["readings"]["rows"][0]
    assert row["status"] == "refused"
    assert row["refusal_key"] == "billing.oneTimeBill.readings.status.belowLast"
    assert response.data["bill"]["total"] is None


def test_def_bil_8300__the_draft_still_prices_only_saved_readings(brazos, dana):
    user = _clerk(brazos)
    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
    response = _post(
        billing_api.one_time_create,
        brazos,
        user,
        _august(account, readings=_typed(asset, "1260")),
    )
    assert response.status_code == 422, response.data


def test_def_bil_8320__two_meters_on_one_point_each_take_their_own_typed_value(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="8 Quarry Hill Rd", services_available=["water"])
        unit = make_unit(dana, premises["id"], label="Unit A", services=["water"])
        first = a_meter(dana, asset_no="W-83201", service="water", uom="kgal", unit_id=unit["id"])
        second = a_meter(dana, asset_no="W-83202", service="water", uom="kgal", unit_id=unit["id"])
        for meter, value in ((first, "482.3"), (second, "130.6")):
            commit_read(
                dana,
                meter["id"],
                day="2026-07-31",
                value=value,
                prior_value=str(Decimal(value) - 5),
                consumption=Decimal("5"),
                unit="kgal",
            )
        rows = metering_selectors.provisional_reads_for_unit(
            unit["id"],
            period_start=AUG_1,
            period_end=AUG_31,
            keyed_reads=(
                {"asset_id": str(first["id"]), "value": "488.4"},
                {"asset_id": str(second["id"]), "value": "136.7"},
            ),
        )
    by_meter = {str(row.get("asset_id")): row for row in rows if row.get("asset_id")}
    assert set(by_meter) == {str(first["id"]), str(second["id"])}, rows
    assert Decimal(by_meter[str(first["id"])]["consumption"]) == Decimal("6.1")
    assert Decimal(by_meter[str(second["id"])]["consumption"]) == Decimal("6.1")
    assert by_meter[str(first["id"])]["current_value"] == Decimal("488.4")
    assert by_meter[str(second["id"])]["current_value"] == Decimal("136.7")
