# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2856 (BR-BIL-023/053's actions have no route — `mark_for_later`
#           and `retry_account` are complete, tested and reachable from
#           nothing, so step 4 offers no action on a broken account at all) ·
#           DEF-2557 (`runs.retry_account` is reachable from no route, so no
#           retry control may be drawn as live)
# Story:    US-BIL-004 (phase 3 — the breaks and their two ways out)
#           Screens: S31 step 4 (the break list, ahead of the totals)
# Rules:    BR-BIL-053 (*"allow user to retry immediately by fixing the issue
#           or mark for later"* — two actions per row) · BR-BIL-055 (a break
#           never blocks the run; the clean bills issue and the rest are held) ·
#           BR-BIL-040 (a stage failure NAMES its stage, and the queue row
#           carries it) · BR-BIL-023 (a re-run REPLACES a draft; a computed
#           amount is never typed over) · BR-TEN-003 / HR-1 (another tenant's
#           run reads as absent) · CLAUDE.md rule 6 (a double-click is a replay)
# ───────────────────────────────────────────────────────
"""Phase 3's two doors, and until today neither had a handle.

**THE PO's OWN SENTENCE, 2026-08-11:** *"once billing is complete show
immediately bills that are break and why; allow user to retry immediately by
fixing the issue or mark for later"*. The list has been shown since CR-051 and
the two ways out have existed since 2026-08-11 — `runs.retry_account` and
`pending.mark_break_for_later`, both complete, both tested, both reachable from
no HTTP route. So `RunBreaksPanel` drew a Retry control DISABLED carrying
*"Trying one customer again is not something this screen can do yet"*, which was
true and left a clerk with one option: fix the data and re-run the whole cycle.

**WHY BOTH HALVES PASSED WHILE THE FEATURE DID NOT EXIST.** The backend tests
call the two functions directly, so both are proved correct. The frontend test
asserts the disabled control and its reason, so the absence is asserted green.
Hard-won law 2, and G13 cannot see it: it checks a component prop nothing
passes, not a service function nothing calls.

**WHAT A RETRY IS AND IS NOT.** It re-runs stages 1–6 for ONE account and
touches no other draft. It is not a re-price of a bill somebody disliked: the
clerk fixes what the reason names — a missing read, a plan that was not in
force — and asks for that account again. Nothing here types over a computed
amount, and nothing here can (BR-BIL-023).
"""

import uuid

import pytest

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import pending
from core import errors

from tests.test_cr051_run_jobs_and_breaks import (  # noqa: F401 — the phase-2/3 world
    a_run,
    a_world,
    breaks_of,
    calculate,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def an_actor_user(tenant, role="billing_clerk"):
    """A FakeUser carrying a REAL `users` row id.

    ⚠ **`bill_run_exclusions.excluded_by` IS AN FK INTO IDENTITY (B2 §2), so a
    synthetic uuid is not merely untidy — it fails the deferred constraint check
    at teardown** (`invalid foreign key … does not have a corresponding value in
    users.id`) while every assertion in the case passes. Measured while writing
    this file: two cases green, two teardown errors, and nothing in the test
    body pointing at the cause.
    """
    return FakeUser(
        user_id=staff_actor(tenant, role, f"{role}-{uuid.uuid4().hex[:8]}@break-actions.test").id
    )


def a_broken_run(tenant, actor):
    """One account that bills and one whose electric read never arrived.

    The second breaks at `measure-consumption`, which is the commonest real
    break and the one BR-BIL-040 exists to name.
    """
    cycle = a_world(tenant, actor)
    run = a_run(tenant, cycle, key=f"2026-06|break-actions-{uuid.uuid4()}")
    calculate(tenant, run)
    return run


def outstanding_breaks(tenant, run):
    return breaks_of(tenant, run).data["breaks"]


def retry(tenant, run, account_id, *, user=None):
    return api_call(
        billing_api.run_break_retry,
        "post",
        user=user or FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        account_id=str(account_id),
        data={},
    )


def hold(tenant, run, account_id, *, detail="waiting on a field visit", user=None):
    return api_call(
        billing_api.run_break_hold,
        "post",
        user=user or an_actor_user(tenant),
        role="billing_clerk",
        tenant=tenant,
        run_id=str(run.pk),
        account_id=str(account_id),
        data={"detail": detail},
    )


# ══════════════════════════════════════════════════════════════════════════
# The routes exist. Asserted twice — through the URLconf and over real HTTP.
# ══════════════════════════════════════════════════════════════════════════
def test_def_2856__both_break_action_routes_are_mounted(brazos):
    from django.urls import resolve

    run_id = uuid.uuid4()
    account_id = uuid.uuid4()
    base = f"/api/brazosbend/billing/runs/{run_id}/breaks/{account_id}"
    assert resolve(f"{base}/retry").func is billing_api.run_break_retry
    assert resolve(f"{base}/hold").func is billing_api.run_break_hold


def test_def_2856__both_break_action_routes_are_reachable_over_real_http(brazos):
    """401 means the route exists and asked for a session; 404 is the defect."""
    from django.test import Client

    base = f"/api/{brazos.subdomain}/billing/runs/{uuid.uuid4()}/breaks/{uuid.uuid4()}"
    for path in (f"{base}/retry", f"{base}/hold"):
        response = Client().post(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means phase 3's two ways "
            "out are still reachable from nothing, which is DEF-2856 exactly"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-053, way out 2 — mark for later
# ══════════════════════════════════════════════════════════════════════════
def test_def_2856__mark_for_later_queues_the_account_and_closes_its_break(brazos, dana):
    """*"or mark for later"* — the account leaves the work list and joins the
    pending queue for a catch-up sub-run (BR-BIL-055).

    The reason code carries the STAGE that broke (BR-BIL-040), so the queue
    groups the way the break list does and a clerk can tell "we never
    calculated this" from "we calculated it and it broke".
    """
    with tenant_ctx(brazos):
        run = a_broken_run(brazos, dana)
    with tenant_ctx(brazos):
        rows = outstanding_breaks(brazos, run)
    assert len(rows) == 1, "the fixture is meant to break exactly one account"
    account_id = rows[0]["account_id"]
    stage = rows[0]["stage"]

    with tenant_ctx(brazos):
        response = hold(brazos, run, account_id)
    with tenant_ctx(brazos):
        exclusion = billing_models.BillRunExclusion.objects.get(
            bill_run=run, account_id=account_id
        )
        after = outstanding_breaks(brazos, run)

    assert response.status_code == 201
    assert response.data["account_id"] == str(account_id)
    assert exclusion.reason_code == f"{pending.BREAK_PREFIX}{stage}"
    assert exclusion.detail
    # The row leaves the OUTSTANDING list: BR-BIL-053's last clause refuses
    # phase 4 while a break is unresolved, and this one is resolved.
    assert after == []


def test_def_2856__a_double_clicked_hold_marks_once(brazos, dana):
    """CLAUDE.md rule 6 — a replay is a success, never a second queue row."""
    with tenant_ctx(brazos):
        run = a_broken_run(brazos, dana)
    with tenant_ctx(brazos):
        account_id = outstanding_breaks(brazos, run)[0]["account_id"]
    with tenant_ctx(brazos):
        first = hold(brazos, run, account_id)
    with tenant_ctx(brazos):
        second = hold(brazos, run, account_id)
    with tenant_ctx(brazos):
        rows = billing_models.BillRunExclusion.objects.filter(
            bill_run=run, account_id=account_id
        ).count()

    assert first.status_code == 201
    assert second.status_code == 201
    assert rows == 1


# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-053, way out 1 — fix and retry now
# ══════════════════════════════════════════════════════════════════════════
def test_def_2856__retrying_an_account_that_still_cannot_bill_refuses_by_name(brazos, dana):
    """Nothing was fixed, so the retry fails the same way and SAYS SO.

    It must not swallow the failure into a 201: a clerk who is told "done"
    over an account that still has no read will find out at the gate. The break
    row stays exactly as it was — `retry_account` closes it only AFTER a draft
    commits.
    """
    with tenant_ctx(brazos):
        run = a_broken_run(brazos, dana)
    with tenant_ctx(brazos):
        account_id = outstanding_breaks(brazos, run)[0]["account_id"]
    with tenant_ctx(brazos):
        response = retry(brazos, run, account_id)
    with tenant_ctx(brazos):
        still = outstanding_breaks(brazos, run)

    assert response.status_code == 422
    assert response.data["br_ref"] == "BR-BIL-053"
    assert len(still) == 1


def test_def_2856__retrying_an_account_the_run_never_prepared_refuses(brazos, dana):
    """An account outside the run's ready set belongs in a catch-up sub-run,
    not in a retry — and the refusal says which (BR-BIL-055)."""
    with tenant_ctx(brazos):
        run = a_broken_run(brazos, dana)
        response = retry(brazos, run, uuid.uuid4())

    assert response.status_code == 422
    assert response.data["br_ref"] == "BR-BIL-053"


# ══════════════════════════════════════════════════════════════════════════
# Isolation — HR-1
# ══════════════════════════════════════════════════════════════════════════
def test_def_2856__another_tenants_run_reads_as_absent(brazos, lonestar, dana):
    """A Brazos Bend run id in a Lone Star request is ABSENT, not forbidden —
    a 403 would confirm the run exists."""
    with tenant_ctx(brazos):
        run = a_broken_run(brazos, dana)
    with tenant_ctx(brazos):
        account_id = outstanding_breaks(brazos, run)[0]["account_id"]
    with tenant_ctx(lonestar):
        held = hold(lonestar, run, account_id)
        retried = retry(lonestar, run, account_id)
    with tenant_ctx(brazos):
        rows = billing_models.BillRunExclusion.objects.filter(bill_run=run).count()

    assert held.status_code == 404
    assert retried.status_code == 404
    assert rows == 0
