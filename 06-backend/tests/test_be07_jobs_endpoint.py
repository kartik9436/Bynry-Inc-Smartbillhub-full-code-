# ── Trace ──────────────────────────────────────────────
# Component: BE-07 poll resource — GET /jobs/{id} (11b §2.17, required by B12 r1's
#            "202 + job_id for EVERY async op … client polls /jobs/{id}"). The
#            route registered in config/urls.py, the view in apps/tenancy/api.py
#            (the module hosting the `jobs` table), the read in its selectors.
#            Numbering continues tests/test_be07_job_runner.py.
# ───────────────────────────────────────────────────────
"""BE-07 endpoint TCs: what the poll serves, and what it refuses to serve.

Real HTTP with real sessions (the identity plumbing), because three of the
four laws under test are request laws: who may poll, what a foreign tenant's
job id looks like (a plain 404, never a 403 — HR-1/11b G4), and the fact that
the `status_url` handed out in a 202 is a route that actually answers.
"""

import uuid

import pytest

from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_delete,
    api_get,
    api_patch,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")
PRIYA = ("priya@silvercreek.example", "Meadow2026sage")


@pytest.fixture()
def live_store():
    previous = core_jobs._store
    core_jobs.set_job_store(tenancy_services.JobStore())
    yield
    core_jobs.set_job_store(previous)


def make_job(tenant, *, kind="audit_export", **finish):
    """One job row for `tenant`, through the kernel (never a hand-built row)."""
    with core_tenancy.tenant_context(tenant.id):
        record = core_jobs.enqueue(kind, payload={"filters": {"action": "invoice.issued"}})
        if finish:
            core_jobs.start(record["id"])
            if "error" in finish:
                core_jobs.fail(record["id"], error=finish["error"])
            else:
                core_jobs.record_progress(record["id"], done=40, total=120, checkpoint="row-40")
                core_jobs.succeed(record["id"], result_link=finish.get("result_link"))
    return record


# ── what the poll serves ────────────────────────────────────────────────────
def test_be07_tc31_the_poll_serves_the_record_contract_and_nothing_more(idn, live_store):
    """⚠ AMENDED 2026-09-02 (DEF-3280 / CR-064), NOT FLIPPED — `checkpoint` IS
    SERVED NOW, and this test used to assert that it was not.

    The old assertion said `"checkpoint" not in body` and grouped it with
    `payload` and `scope_key` as *"runner business — they never ship"*. Two of
    those three are still runner business. `checkpoint` never was: the
    sample-data plant has written the label of the block it just finished into
    it since 2026-08-19 precisely so a screen could narrate the run, and no
    client could read it, so the poll could answer *"11 of 17"* and never
    *"Meter reads"*. The test was pinning the defect.

    Everything else here is untouched, deliberately: `payload` and `scope_key`
    still never ship, the 202's id comes back unchanged, and the exact key set
    is still asserted so a seventh field cannot arrive unnoticed."""
    idn.seed_silvercreek()
    record = make_job(idn.silvercreek, result_link="file:///tmp/silvercreek_audit-log.csv")
    alex = signed_in_client(*ALEX)

    response = api_get(alex, f"/api/jobs/{record['id']}")
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {
        "id",
        "kind",
        "status",
        "progress",
        "checkpoint",
        "result_link",
        "error",
    }
    assert body["id"] == record["id"]  # the id the 202 handed out, unchanged
    assert body["kind"] == "audit_export"
    assert body["status"] == core_jobs.SUCCEEDED
    assert body["progress"] == {"done": 40, "total": 120}
    assert body["checkpoint"] == "row-40"  # what `make_job` recorded, served
    assert body["result_link"] == "file:///tmp/silvercreek_audit-log.csv"
    assert body["error"] is None
    # payload / scope_key are runner business — they never ship.
    assert "payload" not in body and "scope_key" not in body
    # ⚠ AND `steps` IS THE PLANT KIND'S ALONE (CR-064). An export job has no
    # blocks, so seventeen `not_started` rows on it would be a lie about a job
    # that never had any — the DEF-127 posture, one level along.
    assert "steps" not in body


def test_be07_tc32_a_failed_job_polls_as_failed_with_its_error(idn, live_store):
    idn.seed_silvercreek()
    record = make_job(idn.silvercreek, error="OSError: disk full")
    alex = signed_in_client(*ALEX)
    body = api_get(alex, f"/api/jobs/{record['id']}").json()
    assert body["status"] == core_jobs.FAILED
    assert body["error"] == "OSError: disk full"
    assert body["result_link"] is None


def test_be07_tc33_any_signed_in_role_may_poll(idn, live_store):
    """11b §2.17 is the shared resource behind every wizard, import and run, so
    it is not gated to one role. DISPOSITION (documented in apps/tenancy/api.py):
    the contract says "a job they started", but the BE-07 record has no actor
    column — the scope enforced is the TENANT's, and the narrowing is REPORTED
    rather than invented as a schema change."""
    idn.seed_silvercreek()
    record = make_job(idn.silvercreek)
    clerk = signed_in_client(*PRIYA)
    response = api_get(clerk, f"/api/jobs/{record['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == core_jobs.QUEUED


def test_be07_tc34_polling_without_a_session_is_401(idn, live_store):
    from django.test import Client

    idn.seed_silvercreek()
    record = make_job(idn.silvercreek)
    response = api_get(Client(), f"/api/jobs/{record['id']}")
    assert response.status_code == 401


# ── what it refuses ─────────────────────────────────────────────────────────
def test_be07_tc35_another_tenants_job_id_is_404_never_403(idn, live_store):
    """HR-1 / 11b G4: a 403 would confirm the id exists. Absent and forbidden
    must be indistinguishable, byte for byte."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    theirs = make_job(idn.silvercreek)
    okafor = signed_in_client("jordan@bluemesa.example", "Mesa2026bluff", tenant=BM)

    foreign = api_get(okafor, f"/jobs/{theirs['id']}", tenant=BM)
    unknown = api_get(okafor, f"/jobs/{uuid.uuid4()}", tenant=BM)

    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json()["code"] is unknown.json()["code"] is None  # 404 has no catalog code
    assert foreign.json()["message_key"] == unknown.json()["message_key"]


def test_be07_tc36_an_unknown_job_id_is_404(idn, live_store):
    idn.seed_silvercreek()
    alex = signed_in_client(*ALEX)
    assert api_get(alex, f"/jobs/{uuid.uuid4()}").status_code == 404


def test_be07_tc37_the_poll_resource_is_read_only(idn, live_store):
    """Job status is the RUNNER's to write; the client only reads it. No other
    verb is defined, so DRF's own dispatch answers 405 (11b G8 posture)."""
    idn.seed_silvercreek()
    record = make_job(idn.silvercreek)
    alex = signed_in_client(*ALEX)
    assert api_post(alex, f"/api/jobs/{record['id']}").status_code == 405
    assert api_patch(alex, f"/api/jobs/{record['id']}", {"status": "succeeded"}).status_code == 405
    assert api_delete(alex, f"/api/jobs/{record['id']}").status_code == 405


# ── the round trip the whole contract exists for ────────────────────────────
def test_be07_tc38_a_202s_status_url_is_a_route_that_answers(idn, tmp_path, settings):
    """B12 r1 end to end: POST → 202 {job_id, status_url} → GET that URL → the
    finished job. This is the gap the runner lane closed; before it, the accept
    raised and nothing could be polled."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    try:
        users = idn.seed_silvercreek()
        from apps.audit.models import AuditLog

        AuditLog.objects.create(
            tenant_id=idn.silvercreek.id,
            actor_user_id=users.alex.id,
            action="invoice.issued",
            entity_type="invoice",
            entity_id=uuid.uuid4(),
            after={"total": "142.50"},
        )
        alex = signed_in_client(*ALEX)
        accepted = api_post(alex, "/audit-log/export?f.action=invoice.issued")
        assert accepted.status_code == 202
        status_url = accepted.json()["status_url"]

        polled = api_get(alex, status_url)
        body = polled.json()
        assert polled.status_code == 200
        assert body["id"] == accepted.json()["job_id"]
        assert body["kind"] == "audit_export"
        assert body["status"] == core_jobs.SUCCEEDED
        # The link is the IS-11 download route, so the poll ends at a file the
        # browser can actually fetch (the download lane, 2026-08-10).
        assert body["result_link"] == f"/api/exports/{body['id']}/file"
    finally:
        core_jobs.set_job_store(previous_store)
        core_jobs.set_job_dispatcher(previous_dispatcher)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-006@009e809 (the 202 this resource completes — EP-AUD-02; the resource itself is component packet BE-07@05736ee, 11b §2.17, and has no story of its own)
# generated: 2026-08-10 by story-coder v1 (job-runner lane — the poll resource every 202 promised and nothing served) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — FI-01 job polling is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_be07_jobs_endpoint.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: tc33 records the actor-scoping disposition (tenant scope, not "the user who started it" — no actor column exists on the BE-07 record) — REPORTED · the RLS half of tc35 belongs to the G5 isolation suite; the app-filter half is asserted here · [path-tenancy lane 2026-08-10] requests address `/api/jobs/{id}` and name their TENANT instead of a Host; the foreign-job 404 is unchanged in law
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
