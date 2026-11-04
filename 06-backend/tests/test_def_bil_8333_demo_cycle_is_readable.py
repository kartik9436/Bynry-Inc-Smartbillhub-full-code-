"""DEF-BIL-8333 — the J70/J74 demo cycle can be read, so demo bills prorate.

Coordinator ruling 2026-09-30 (decision log): proration is signed law (B4.3,
BR-BIL-012, BR-BIL-1047), so a bill's figure depends only on the days billed —
and the demo cycle `J70-MONTHLY` was seeded with NO first run date, which makes
metering's `billing_period_for_unit` answer None and every first and final bill
fall back to charging whole bases. A real utility's cycle always has one.

These cases use the seed's OWN `ensure_cycle` (10-scripts/seed_j70_one_time_bill.py),
not a monkeypatched seam, so they fail the day the seed stops shipping a
readable cycle. Written RED FIRST (law 7).
"""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.rating import models as rating_models
from tests.test_def_438_parity import _account_on, _water_plan
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEED = pathlib.Path(__file__).resolve().parents[2] / "10-scripts" / "seed_j70_one_time_bill.py"


def _seed_module():
    spec = importlib.util.spec_from_file_location("seed_j70_for_test", SEED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def on_the_seeded_cycle(brazos, dana):
    """`_account_on`'s unit stamped onto the cycle the seed builds — exactly as
    the seed stamps its own units (`ServicePoint.cycle`)."""
    seed = _seed_module()
    with tenant_ctx(brazos):
        cycle = seed.ensure_cycle(brazos)
        account, unit, asset, _delta = _account_on(brazos, dana, _water_plan(brazos))
        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(cycle=cycle)
    return cycle, account, unit, asset


def test_def_bil_8333__the_seeded_cycle_has_a_first_run_date(brazos, on_the_seeded_cycle):
    cycle, _account, _unit, _asset = on_the_seeded_cycle
    assert cycle.first_run_date == date(2026, 1, 1)


def test_def_bil_8333__metering_can_read_the_seeded_cycle(brazos, on_the_seeded_cycle):
    _cycle, _account, unit, _asset = on_the_seeded_cycle
    with tenant_ctx(brazos):
        period = metering_selectors.billing_period_for_unit(unit["id"], as_of=date(2026, 9, 12))
    assert period == {"start": "2026-09-01", "end": "2026-09-30"}, period


def test_def_bil_8333__an_old_demo_database_is_repaired_by_running_the_seed_again(brazos):
    """`get_or_create` alone would leave a cycle created before this fix unreadable."""
    seed = _seed_module()
    with tenant_ctx(brazos):
        metering_models.Cycle.objects.create(
            tenant=brazos, code=seed.CYCLE_CODE, frequency="Monthly", start_day=1, days_to_complete=30, due_days=21
        )
        cycle = seed.ensure_cycle(brazos)
    assert cycle.first_run_date == date(2026, 1, 1)


def test_def_bil_8333__a_first_bill_prorates_on_the_seeded_cycle(brazos, dana, on_the_seeded_cycle):
    """GT-3's figures on the seed's own cycle, no seam patched: move-in Sep 16,
    15 of September's 30 days, base $30.50 → $15.25."""
    _cycle, account, _unit, asset = on_the_seeded_cycle
    with tenant_ctx(brazos):
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=Decimal("30.50"))
        rating_models.Charge.objects.filter(tenant=brazos, is_base=True, service__code="water").update(
            amount=Decimal("30.50")
        )
        customer_models.Account.objects.filter(pk=account.pk).update(opened_at=date(2026, 9, 16))
    body = {
        "account_id": str(account.id),
        "kind": "first",
        "period_start": "2026-09-16",
        "period_end": "2026-09-30",
        "bill_date": "2026-09-30",
        "due_days": 21,
        "readings": [{"asset_id": str(asset["id"]), "read_at": "2026-09-30", "value": "1240", "role": "current"}],
    }
    response = _post(billing_api.one_time_preview, brazos, _clerk(brazos), body)
    assert response.status_code == 200, response.data
    bases = [
        Decimal(line["amount"])
        for group in response.data["bill"]["groups"]
        for line in group["lines"]
        if line["charge"] == "base"
    ]
    assert bases == [Decimal("15.25")], response.data["bill"]
