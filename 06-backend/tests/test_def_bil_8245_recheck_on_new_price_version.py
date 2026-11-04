# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8245 — the Check re-checked an account when its PLAN ROW
#          changed, and not when a new rate-schedule VERSION was published
#          under that plan (the plan ↔ schedule link is its own table).
# Ruling:  OQ-843 re-ruled 2026-09-30, option C — *"Save results, and
#          automatically re-check an account when its plan, reading, meter or
#          payment changes"*; a new price version is a plan change for this.
# Rows:    BULK-CHG-53 (changes list row 53)
# Code:    apps/rating/selectors.py plans_changed_since ·
#          apps/billing/check_staleness.py
# ───────────────────────────────────────────────────────
"""Publish a new price version under one plan → exactly that plan's accounts
re-check; a DRAFT version (nothing priced from it) re-checks nobody."""

from __future__ import annotations

import time
from datetime import date

import pytest

from apps.billing import check_models, check_staleness, check_store
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_bbr_check_engine import a_cycle
from tests.test_bbr_check_store import a_run
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _checked_at(run):
    return {
        str(row.account_id): row.checked_at
        for row in check_models.BillRunAccountCheck.objects.filter(bill_run=run)
    }


# BULK-CHG-53
def test_def_bil_8245__a_new_price_version_rechecks_exactly_the_accounts_on_that_plan(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        repriced = a_priced_plan(brazos, name="Repriced")
        untouched = a_priced_plan(brazos, name="Untouched")
        on_repriced, on_untouched = [], []
        for n in range(3):
            unit = a_billed_unit(dana, brazos, cycle, repriced, asset_no=f"M-845{n}", label=f"R{n}")
            on_repriced.append(an_account(brazos, unit["id"], f"A-8245{n}"))
        for n in range(2):
            unit = a_billed_unit(
                dana, brazos, cycle, untouched, asset_no=f"M-846{n}", label=f"U{n}"
            )
            on_untouched.append(an_account(brazos, unit["id"], f"A-8246{n}"))
        run = a_run(cycle)
        check_store.check_run(run)
        before = _checked_at(run)
        assert len(before) == 5

        [schedule] = rating_selectors.plan_rate_schedules(repriced.id)
        current = rating_models.TariffVersion.objects.get(
            tariff=schedule["tariff"], effective_from__isnull=False
        )
        time.sleep(0.01)

        # 1 · A DRAFT is saved under the plan. Nothing prices from a draft
        #     (BR-RAT-031: NULL effective_from IS the draft), so nobody re-checks.
        draft = rating_models.TariffVersion.objects.create(
            tenant=brazos,
            tariff=schedule["tariff"],
            model="flat",
            base_charge=current.base_charge,
            uom="kWh",
            currency="USD",
            effective_from=None,
        )
        assert check_staleness.sweep(run)["stale"] == 0

        # 2 · The draft is ACTIVATED from 15 June, the way
        #     `services.activate_rate_schedule` does it: the date is stamped on
        #     the same row and the row is saved. The old version is closed the
        #     day before (a queryset update, which moves no `updated_at` — so
        #     it is the NEW version that has to be seen).
        rating_models.TariffVersion.objects.filter(pk=current.pk).update(
            effective_to=date(2026, 6, 14)
        )
        draft.effective_from = date(2026, 6, 15)
        draft.save(update_fields=["effective_from", "effective_to", "updated_at"])

        changed = rating_selectors.plans_changed_since(
            [str(repriced.id), str(untouched.id)], min(before.values())
        )
        assert set(changed) == {str(repriced.id)}

        swept = check_staleness.sweep(run)
        assert swept["stale"] == 3 and swept["rechecked"] == 3
        after = _checked_at(run)
        for account in on_repriced:
            assert after[str(account.id)] > before[str(account.id)], account.account_no
        for account in on_untouched:
            assert after[str(account.id)] == before[str(account.id)], account.account_no

        # 3 · Nothing moved since: a second sweep finds nothing.
        assert check_staleness.sweep(run)["stale"] == 0
