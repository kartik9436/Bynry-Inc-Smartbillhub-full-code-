# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8414 — the served Ready list lost image 21's three columns
#          (services, plan, whether every reading was read)
# Code:    apps/billing/check_store.py (_ready_facts, ready_accounts)
# ───────────────────────────────────────────────────────
"""Ready to bill carries the services, the plan and *All read / Some estimated*.

RED FIRST: on the tip `ready_accounts` rows carried account, unit, customer and
left-out only, and every case here failed on `KeyError: 'services'`.
"""

from __future__ import annotations

import pytest

from apps.billing import check_models, check_store
from tests.test_bbr_check_engine import three_accounts
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# BULK-CHG-41
def test_def_bil_8414__ready_rows_carry_services_plan_and_all_read(brazos, dana):
    with tenant_ctx(brazos):
        cycle, plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        page = check_store.ready_accounts(run, {})
        missing = set(
            str(a)
            for a in check_models.BillRunFinding.objects.filter(
                bill_run=run, code="missing_read"
            ).values_list("account_id", flat=True)
        )
    assert page["results"], "the fixture must leave at least one account ready"
    for row in page["results"]:
        assert row["plan_name"] == plan.name
        assert row["services"], row
        assert all(isinstance(code, str) for code in row["services"])
        assert row["all_read"] is (row["account_id"] not in missing)


def test_def_bil_8414__a_missing_reading_reads_some_estimated(brazos, dana):
    """The flag follows the Check's own finding, so an account the clerk let
    the run estimate is never shown as *All read*."""
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        row = check_models.BillRunAccountCheck.objects.filter(bill_run=run).order_by("account_no").first()
        check_models.BillRunFinding.objects.create(
            tenant_id=row.tenant_id,
            bill_run=run,
            account_check=row,
            account_id=row.account_id,
            code="missing_read",
            category="readings",
            detail="no reading in the period",
        )
        facts = check_store._ready_facts(run, [row])
    assert facts[str(row.account_id)]["all_read"] is False
