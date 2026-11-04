"""DEF-BIL-8563 — a first bill from the account's OWN move-in date finds the
reading taken on that day, and opens on it.

J74 case 3 (PostgreSQL, 1440): Maria Alvarez, Unit C, moved in 09/12/2026 with
move-in readings dated 09/12/2026 (W-10442C 479.8, E-55120C 18,500). The page
pre-fills From = 09/12, then showed every meter's move-in reading as *none on
file*, priced nothing, and left Move-in charges at $0.00 — no deposit and no
connection charge — even with the new readings typed. Moving the date to 09/13
priced $397.82 ($150.00 deposit, $45.00 connection, plus usage), which is how
J70 E2 passed.

The rule the fix builds: **on a first bill, a reading dated exactly the move-in
day is the START reading** — the register the customer took the service on — and
never the reading the window closes on. Days are unchanged: the move-in day is
still a billed day (BR-BIL-012, the window runs from the move-in day inclusive).

Written RED FIRST (hard-won law 7).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db

MOVE_IN = date(2026, 9, 12)
TO = date(2026, 9, 30)


@pytest.fixture
def on_a_cycle(monkeypatch):
    """DEF-BIL-8330 — a first bill needs a cycle; the fixture unit is on none."""
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )


@pytest.fixture
def moved_in(brazos, dana):
    """Last read Jul 28 at 1,200; the MOVE-IN reading 1,300 taken on Sep 12,
    stored as the seed stores it (no prior value, no consumption); the account
    opened that same day."""
    from core import sample_fixture as fixture

    with tenant_ctx(brazos):
        account, _unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        commit_read(
            dana,
            asset["id"],
            day=MOVE_IN.isoformat(),
            value="1300",
            prior_value=None,
            consumption=None,
            unit=fixture.WATER_UOM,
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


def _usage(body) -> Decimal:
    lines = [line for group in body["bill"]["groups"] for line in group["lines"]]
    return sum((Decimal(line["quantity"]) for line in lines if line["charge"] == "usage"), Decimal("0"))


def test_def_bil_8563__the_move_in_days_reading_is_the_previous_reading_on_step_2(
    brazos, dana, on_a_cycle, moved_in
):
    account, _asset = moved_in
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), _first(account))
    assert response.status_code == 200, response.data
    row = response.data["readings"]["rows"][0]
    assert row["previous"] is not None, row
    assert Decimal(row["previous"]["value"]) == Decimal("1300"), row
    assert row["previous"]["read_at"] == MOVE_IN.isoformat(), row
    assert row["status"] == "waiting", row


def test_def_bil_8563__a_typed_closing_reading_prices_from_the_move_in_reading(
    brazos, dana, on_a_cycle, moved_in
):
    account, asset = moved_in
    typed = [{"asset_id": str(asset["id"]), "read_at": TO.isoformat(), "value": "1340", "role": "current"}]
    response = _post(
        billing_api.one_time_preview, brazos, _clerk(brazos), _first(account, readings=typed)
    )
    assert response.status_code == 200, response.data
    assert response.data["bill"]["total"] is not None, response.data.get("waiting_for")
    assert _usage(response.data) == Decimal("40"), response.data["bill"]
    charges = response.data["move_in_charges"]
    assert charges is not None and charges["moved_in_on"] == MOVE_IN.isoformat()


def test_def_bil_8563__the_draft_prices_from_the_move_in_reading_once_the_closing_one_is_saved(
    brazos, dana, on_a_cycle, moved_in
):
    from core import sample_fixture as fixture

    account, asset = moved_in
    with tenant_ctx(brazos):
        commit_read(
            dana,
            asset["id"],
            day=TO.isoformat(),
            value="1340",
            prior_value="1300",
            consumption=Decimal("40"),
            unit=fixture.WATER_UOM,
            days_since_prior=18,
        )
        before = billing_models.Invoice.objects.count()
    response = _post(billing_api.one_time_create, brazos, _clerk(brazos), _first(account))
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        assert billing_models.Invoice.objects.count() == before + 1
        invoice = billing_models.Invoice.objects.order_by("-created_at").first()
        kinds = list(
            billing_models.InvoiceLine.objects.filter(invoice=invoice).values_list("kind", "quantity")
        )
    usage = sum((q for kind, q in kinds if kind == "usage" and q is not None), Decimal("0"))
    assert usage == Decimal("40"), kinds
