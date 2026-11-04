# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9255 — a draft bill run could not be thrown away (DELETE 405,
#          no discard), so a run created for the wrong period blocked every
#          overlapping run on its cycle.
# Rules:   BR-BIL-1045 (`abandoned`) · BR-BIL-004 / BR-BIL-023 (drafts are
#          discardable, issued bills are not) · BR-BIL-005 (the key) · hard
#          rules 4 and 7
# Tests:   this file — run on PostgreSQL (`--ds=config.settings.pgtest`): the
#          draft deletes go through `billing/0017`'s trigger, which sqlite lacks
# Impacts: apps/billing/runs.py `discard_run` · apps/billing/api.py
# ───────────────────────────────────────────────────────
"""Discard a DRAFT run: its drafts go, its row stays `abandoned`, the period is free.

Worked: a June run drafted three bills; Discard → 0 drafts, the run reads
Abandoned, an audit row says 3 drafts were removed, and a new June run — the
SAME cycle and period — is accepted, where before it was refused as a duplicate
and every overlapping run was refused as an overlap.
"""

from datetime import date
import pytest
from django.urls import resolve

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import run_scope, runs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_004_run_loop import prepared_for

pytestmark = pytest.mark.django_db


def _drafted_run(tenant, actor):
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    for n in (1, 2, 3):
        unit = a_billed_unit(actor, tenant, cycle, plan, asset_no=f"M-9255{n}", label=f"Unit {n}")
        an_account(tenant, unit["id"], f"A-9255{n}")
    run = runs.create_run(cycle_id=cycle.id, period_start=PERIOD_START, period_end=PERIOD_END)
    result = runs.calculate_run(prepared_for(cycle), bill_run=run)
    assert result.drafted_count == 3, "three drafts to throw away — else the case is vacuous"
    return cycle, run


def _discard(tenant, run_id, *, role="billing_clerk"):
    return api_call(
        billing_api.run_discard,
        "post",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        run_id=str(run_id),
        data={},
    )


def _codes(check):
    return {p.code for p in (*check.refusals, *check.warnings)}


def test_def_bil_9255_tc_mounted():
    assert (
        resolve("/api/brazosbend/billing/runs/018f6f6a-0000-7000-8000-000000000001/discard").func
        is billing_api.run_discard
    )


def test_def_bil_9255_tc1__a_draft_run_is_discarded_and_frees_its_period(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        cycle, run = _drafted_run(brazos, dana)
        before = run_scope.ScopeCheck()
        run_scope._check_continuity(before, str(cycle.id), PERIOD_START, PERIOD_END)
        assert "duplicate_run" in _codes(before) or "duplicate_run_unnamed" in _codes(before)
        overlap = run_scope.ScopeCheck()
        run_scope._check_continuity(overlap, str(cycle.id), date(2026, 6, 15), date(2026, 7, 14))
        assert "period_overlap" in _codes(overlap)

    response = _discard(brazos, run.pk)
    assert response.status_code == 200, response.data
    assert response.data["drafts_removed"] == 3

    with tenant_ctx(brazos):
        run.refresh_from_db()
        assert run.status == "abandoned"
        assert not billing_models.Invoice.objects.filter(bill_run=run).exists()
        rows = [row for row in audit_rows if row["action"] == "bill_run.discarded"]
        assert len(rows) == 1, "hard rule 7 — the discard is audited"
        assert rows[0]["after"]["drafts_removed"] == 3
        assert rows[0]["after"]["status"] == "abandoned"

        after = run_scope.ScopeCheck()
        run_scope._check_continuity(after, str(cycle.id), date(2026, 6, 15), date(2026, 7, 14))
        assert "period_overlap" not in _codes(after)
        # The SAME period again: no duplicate refusal, and the run is created.
        again = runs.create_run(cycle_id=cycle.id, period_start=PERIOD_START, period_end=PERIOD_END)
        assert again.status == "draft"


def test_def_bil_9255_tc2__a_run_with_a_bill_that_went_out_is_refused(brazos, dana):
    """A fee/cut run reads `draft` after its bill has gone out (DEF-BIL-5373) — the
    New Connection quote's run is one — so the status alone must not decide."""
    with tenant_ctx(brazos):
        _cycle, run = _drafted_run(brazos, dana)
        first = billing_models.Invoice.objects.filter(bill_run=run).first()
        billing_models.Invoice.objects.filter(pk=first.pk).update(
            status=billing_models.INVOICE_ISSUED, bill_payload={"services": []}
        )
        assert run.status == "draft"

    response = _discard(brazos, run.pk)
    assert response.status_code == 409, response.data  # BIZ-STATE
    with tenant_ctx(brazos):
        run.refresh_from_db()
        assert run.status == "draft"
        assert billing_models.Invoice.objects.filter(bill_run=run).count() == 3, "nothing removed"


def test_def_bil_9255_tc3__an_issued_run_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, run = _drafted_run(brazos, dana)
        billing_models.BillRun.objects.filter(pk=run.pk).update(status="issued")
        run.refresh_from_db()
        with pytest.raises(runs.DiscardRefused) as refused:
            runs.discard_run(run)
        assert refused.value.code == runs.DISCARD_REFUSED_NOT_DRAFT


def test_def_bil_9255_tc4__a_reader_cannot_discard(brazos, dana):
    with tenant_ctx(brazos):
        _cycle, run = _drafted_run(brazos, dana)
    response = _discard(brazos, run.pk, role="executive")
    assert response.status_code == 403
    with tenant_ctx(brazos):
        run.refresh_from_db()
        assert run.status == "draft"


def test_def_bil_9255_tc5__the_discarded_key_cannot_be_a_real_key():
    key = "cycle|2026-06-01|2026-06-30"
    assert runs.discarded_key(key, "abc") == f"{key}|discarded|abc"
