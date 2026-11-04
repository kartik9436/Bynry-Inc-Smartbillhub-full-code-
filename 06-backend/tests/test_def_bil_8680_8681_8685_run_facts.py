# ── Trace ──────────────────────────────────────────────
# Journey:  J72 § E11 — the bulk bill run beside its D1 drawings (wave 2, 2026-10-01)
# Defects:  DEF-BIL-8680 (the run's name read "—" after Scope) · DEF-BIL-8681
#           (Scope said "No runs yet" while the period was invalid) ·
#           DEF-BIL-8685 (Send said "Signed off <date>" — no who, no time)
# Drawing:  05-prototype/bulk-bill-run-2026-09-30/05 (Last run while refused),
#           25–36 (Run name on the aside), 32 ("Signed off by J. Ortiz · Oct 1, 09:42")
# ───────────────────────────────────────────────────────
"""The run's own facts, served so the screen never has to remember them.

A run opened from its address (`?run=`) knew only what `GET /billing/runs/{id}`
served, and that read carried neither the name the clerk typed nor who signed
it off — so the aside said "—" for the name on every step after Scope, and the
Send card dropped the sign-off line altogether on a re-opened run. Scope, for
its part, only looked for the cycle's previous run once the period was valid,
so a typing slip in the period made a cycle with a sent run say "No runs yet".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import selectors
from tests.test_bulk_run_scope import a_cycle, a_june_run_behind, a_published_template, check
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_def_bil_8681_an_invalid_period_still_names_the_cycles_last_run(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_start="2026-07-31", period_end="2026-07-01"
        )
    assert any(problem.code == "period_order" for problem in result.refusals)
    assert result.previous_run is not None
    assert result.previous_run["run_no"] == "RUN-0001"


def test_def_bil_8680_the_run_detail_serves_the_name_the_clerk_typed(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        june = a_june_run_behind(brazos, cycle)
        detail = selectors.run_detail_dict(june)
    assert detail["label"] == "June 2026 · Riverside"


def test_def_bil_8685_the_run_detail_serves_who_signed_off_and_when(brazos, dana):
    signed = datetime(2026, 10, 1, 14, 42, tzinfo=UTC)
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        june = a_june_run_behind(brazos, cycle)
        assert selectors.run_detail_dict(june)["signed_off"] is None
        billing_models.BillRunRelease.objects.create(
            tenant=brazos,
            bill_run=june,
            summary={},
            account_count=1,
            bill_count=1,
            total_amount=Decimal("10.0000"),
            currency="USD",
            confirmed_by=getattr(dana, "user", dana),
            confirmed_at=signed,
        )
        detail = selectors.run_detail_dict(june)
    user = getattr(dana, "user", dana)
    assert detail["signed_off"]["at"] == signed.isoformat()
    assert detail["signed_off"]["by"] == (getattr(user, "full_name", None) or None)
    assert detail["signed_off"]["by"]
