# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-006 (GET /billing/pending — the S30 queue and its KPI chip ·
#           POST /billing/runs/{id}/catch-up — the queue's bulk action)
#           Screens: S30 · S31 (sub-run mode)
# Rules:    BR-BIL-015 (the queue, its aging and escalation; catch-up SUB-RUNS
#           with scope-keyed idempotency) · BR-BIL-005 (a duplicate is refused
#           with who/when/link) · BR-BIL-034 (excluded work needs a door back) ·
#           BR-BIL-055 (the queue records WHICH DOOR) · BR-TEN-043 (event-time
#           law — `as_of` is REQUIRED, never a server clock) · BR-SHL-025 /
#           BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The two `/billing` routes US-BIL-006 needs, asserted as a mounted contract.

**A ROUTE THAT IS NOT MOUNTED IS NOT AN ENDPOINT**, and every other test in this
file would pass while that was true — the S30 lane learned it once and the S31
lane learned it again the next day. `tc_mounted` resolves both paths through the
REAL root URLconf, so exporting a `urlpatterns` nothing includes goes red here.

**`as_of` IS REQUIRED AND THAT IS THE POINT.** Aging is measured against the
TENANT's today (BR-TEN-043, gate G6). A default of `date.today()` would age
every row by a day the moment a clerk opened the queue from another timezone,
and an escalation is a figure somebody acts on. `tc_as_of` asserts the refusal
names the parameter instead of guessing.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from django.urls import resolve

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import pending, runs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_bil_005_issue import a_run, an_account

pytestmark = pytest.mark.django_db

HELD_ON = date(2026, 8, 1)
REVIEW_DAY = date(2026, 8, 4)


def _held(run, account, *, reason="staff_hold_missing_read", detail="gas read missing"):
    row = runs.mark_for_later(
        bill_run=run, account_id=str(account.id), reason_code=reason, detail=detail
    )
    billing_models.BillRunExclusion.objects.filter(pk=row.pk).update(
        created_at=datetime(HELD_ON.year, HELD_ON.month, HELD_ON.day, 9, 0, tzinfo=timezone.utc)
    )
    return row


def _queue(tenant, *, role="billing_clerk", **query):
    return api_call(
        billing_api.billing_pending,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        query=query,
    )


def _catch_up(tenant, actor_user, run_id, account_ids, *, role="billing_clerk"):
    return api_call(
        billing_api.run_catch_up,
        "post",
        user=actor_user,
        role=role,
        tenant=tenant,
        run_id=str(run_id),
        data={"account_ids": [str(value) for value in account_ids]},
    )


def test_us_bil_006_tc_mounted__both_queue_routes_resolve_in_the_real_urlconf():
    """An `api.py` that exports `urlpatterns` no URLconf includes is not an API."""
    assert resolve("/api/brazosbend/billing/pending").func is billing_api.billing_pending
    assert (
        resolve("/api/brazosbend/billing/runs/018f6f6a-0000-7000-8000-000000000001/catch-up").func
        is billing_api.run_catch_up
    )


def test_us_bil_006_tc_queue__the_list_and_its_chip_come_back_together(brazos, dana):
    """S30's chip and list are ONE response, so they cannot disagree on screen."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        run = a_run(brazos, key="2026-08|api-parent")
        _held(run, account)

    response = _queue(brazos, as_of=REVIEW_DAY.isoformat())
    assert response.status_code == 200
    body = response.data
    assert body["as_of"] == REVIEW_DAY.isoformat()
    assert body["counts"] == {"pending": 1, "escalated": 0, "prepare": 1, "breaks": 0}
    assert len(body["items"]) == body["counts"]["pending"]

    row = body["items"][0]
    assert set(row) == {
        "id",
        "account_id",
        "account_no",
        "bill_run_id",
        "parent_run_id",
        "period_start",
        "period_end",
        "reason_code",
        "detail",
        "origin",
        "stage",
        "held_on",
        "age_days",
        "escalated",
        "resolved_by_run_id",
        "resolved_on",
    }, "a JSON key is a contract the moment a screen reads it"
    assert row["account_no"] == "ACC-1201"
    assert row["age_days"] == 3
    assert row["origin"] == pending.ORIGIN_PREPARE
    assert row["stage"] is None
    # Hard-won law 1 — the absence travels on the envelope rather than in a
    # docstring nobody reads: the escalation threshold is not a tenant setting.
    codes = {entry["code"] for entry in body["unavailable"]}
    assert "escalation_days_is_not_a_tenant_setting_yet" in codes


def test_us_bil_006_tc_as_of__the_queue_refuses_rather_than_reading_a_clock(brazos, dana):
    """BR-TEN-043 / G6 — no `as_of`, no answer, and the refusal names the field."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        _held(a_run(brazos, key="2026-08|api-clock"), account)

    response = _queue(brazos)
    assert response.status_code == 422
    assert [field["field"] for field in response.data["field_errors"]] == ["as_of"]

    # And the threshold is a parameter, not a constant: the same rows escalate
    # or do not depending on the number the caller passes.
    strict = _queue(brazos, as_of=REVIEW_DAY.isoformat(), escalation_days=2)
    assert strict.data["counts"]["escalated"] == 1
    lax = _queue(brazos, as_of=REVIEW_DAY.isoformat(), escalation_days=30)
    assert lax.data["counts"]["escalated"] == 0


def test_us_bil_006_tc_catch_up__the_endpoint_creates_a_child_and_refuses_a_repeat(brazos, dana):
    """The queue's bulk action, and BR-BIL-005 at sub-run granularity over HTTP.

    The duplicate answers the SAME catalog code a repeated cycle run answers
    (`BIZ-…` idempotent, BR-BIL-005's three facts) — one rule at two
    granularities, and a screen should not have to tell two refusals apart to
    render one sentence.
    """
    with tenant_ctx(brazos):
        first = an_account(dana, brazos, account_no="ACC-1201")
        second = an_account(dana, brazos, account_no="ACC-1455")
        parent = a_run(brazos, key="2026-08|api-catchup")
        _held(parent, first)
        _held(parent, second)

    created = _catch_up(brazos, dana.user, parent.id, [first.id])
    assert created.status_code == 201
    assert created.data["parent_run_id"] == str(parent.id)
    assert created.data["period_start"] == parent.period_start.isoformat()

    repeated = _catch_up(brazos, dana.user, parent.id, [first.id])
    assert repeated.status_code == 409, "BIZ-IDEMPOTENT — the same status a repeated cycle run gets"
    assert repeated.data["params"]["run_id"] == created.data["id"]
    assert repeated.data["br_ref"] == "BR-BIL-015"

    other = _catch_up(brazos, dana.user, parent.id, [second.id])
    assert other.status_code == 201, "a DIFFERENT held subset is a different scope"

    stray = _catch_up(brazos, dana.user, parent.id, [str(parent.id)])
    assert stray.status_code == 422
    assert "never held" in stray.data["params"]["detail"]

    malformed = api_call(
        billing_api.run_catch_up,
        "post",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        run_id=str(parent.id),
        data={"account_ids": "ACC-1201"},
    )
    assert malformed.status_code == 422


def test_us_bil_006_tc_rbac__an_executive_may_look_and_may_not_start_a_sub_run(brazos, dana):
    """A4 gives Executive VIEW on Reads & Billing runs — and BR-SHL-025 is
    server-enforced, not a disabled button."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        parent = a_run(brazos, key="2026-08|api-rbac")
        _held(parent, account)

    assert _queue(brazos, role="executive", as_of=REVIEW_DAY.isoformat()).status_code == 200
    refused = _catch_up(brazos, dana.user, parent.id, [account.id], role="executive")
    assert refused.status_code == 403


def test_us_bil_006_tc_isolation__another_tenants_queue_and_run_are_absent(brazos, lonestar, dana):
    """HR-1 — a crafted run id from another tenant is 404, never 403."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        parent = a_run(brazos, key="2026-08|api-iso")
        _held(parent, account)

    assert _queue(brazos, as_of=REVIEW_DAY.isoformat()).data["counts"]["pending"] == 1
    other = _queue(lonestar, as_of=REVIEW_DAY.isoformat())
    assert other.data["counts"]["pending"] == 0
    assert other.data["items"] == []

    crossed = _catch_up(lonestar, dana.user, parent.id, [account.id])
    assert crossed.status_code == 404, "existence must not leak one bit at a time"


def test_us_bil_006_tc_history__a_closed_row_is_reachable_but_not_in_the_queue(brazos, dana):
    """The row is CLOSED, never deleted — enter → age → clear is what an audit
    reads (US-BIL-006 TC-3)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        parent = a_run(brazos, key="2026-08|api-history")
        row = _held(parent, account)
        billing_models.BillRunExclusion.objects.filter(pk=row.pk).update(
            resolved_at=datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc), resolved_by_run=parent
        )

    live = _queue(brazos, as_of=REVIEW_DAY + timedelta(days=10))
    assert live.data["counts"]["pending"] == 0

    history = _queue(
        brazos, as_of=(REVIEW_DAY + timedelta(days=10)).isoformat(), include_resolved="true"
    )
    assert len(history.data["items"]) == 1
    assert history.data["items"][0]["resolved_by_run_id"] == str(parent.id)
    assert history.data["items"][0]["resolved_on"] == "2026-08-10"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-006@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         04-docs/01-spec/11b-api-audit.md §2.8)
# generated: 2026-08-15 by Eng-Lead (US-BIL-006 lane — the two endpoints)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — nothing in 07-frontend calls these two paths yet; REPORTED, hard-won law 2) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_bil_006_pending_api.py
# exceptions: (1) `openapi/schema.json` is NOT regenerated by this lane —
#         BE-11 TC05 diffs the committed snapshot, so the two new routes will
#         show as a diff until it is. REPORTED rather than regenerated blind,
#         because the snapshot is one generated file committed once (hard-won
#         law 5) and other lanes are adding routes in the same session.
#         (2) The i18n keys `billing.pending.as_of_required`,
#         `billing.pending.escalation_days_invalid`,
#         `billing.catch_up.account_ids_required` and
#         `billing.catch_up.duplicate` are added to all ELEVEN catalogues by
#         this lane; G15/G18 are the check.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
