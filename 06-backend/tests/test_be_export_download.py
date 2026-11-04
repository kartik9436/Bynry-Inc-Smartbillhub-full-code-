# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-008 (EP-SHL-02 — the generic list export whose file this
#           route finally hands over) · US-AUD-006 (EP-AUD-02 — the S61 export,
#           the OTHER producer of the same artifact)
#           Screens: S14 · S15 · S26 · S27 · S49 · S9 · S61
# Rules:    BR-REP-018 (IS-11 download contract + 3-day retention) ·
#           BR-SHL-016 (the export is server-side and STREAMED, under the
#           caller's own tenant context) · BR-AUD-007 (an audit artifact is the
#           caller's tenant's, exclusively) · BR-TEN-003 (tenant from context,
#           never client input) · HR-1 / 11b G4 (existence must not leak: every
#           no is the SAME 404)
# Tests:    this file (GET /exports/{job_id}/file, per contract clause)
# Impacts:  apps/tenancy/api.py::export_file · apps/tenancy/exports.py
#           (resolve_artifact) · apps/tenancy/export_store.py · config/urls.py
"""GET /exports/{job_id}/file — what it hands over, and the noes it refuses with.

Real HTTP with real sessions, because every law here is a request law: who may
fetch, what a foreign tenant's job looks like (indistinguishable from a job
that never existed), and what leaves the process.

⚠ **SINCE 2026-10-02 THE ROUTE ANSWERS A 302 TO A SIGNED S3 LINK** (PO ruling,
decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS
APPROVED"*: *"the system checks the record and hands over a link to the file
that lasts 4 hours"*). The file lives at `t/<web name>/export/<yyyy>/<mm>/<id>.<ext>`
in the environment's bucket — here an S3 emulator through the real client
(tests/conftest.py) — and is found through its `job_artifacts` row. The
traversal-guard cases this file used to hold are gone with the disk path they
guarded; their successor is the database check and the adapter's key check
(tests/test_s3a_job_artifacts.py, tests/test_s3a_export_storage.py).

Both producers are exercised — the generic `list_export` and S61's
`audit_export` — because the route belongs to neither module and must not
quietly work for only one of them.
"""

import datetime as dt
import json
import urllib.parse
import uuid

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.metering import models as metering_models
from apps.tenancy import export_store
from apps.tenancy import exports as export_kernel
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from apps.tenancy.export_models import JobArtifact
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    BM,
    api_delete,
    api_get,
    api_post,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

ALEX = ("alex@silvercreek.example", "Canyon2026rapids")
PRIYA = ("priya@silvercreek.example", "Meadow2026sage")
JORDAN = ("jordan@bluemesa.example", "Mesa2026bluff")
BUCKET = "sbh-test-bucket"


@pytest.fixture()
def wired(settings, export_bucket):
    """The deployment's own wiring — real store, real transport, eager — with
    exports in the emulated bucket."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield export_bucket
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


# ── the two producers, each seeded with ONE recognisable row ────────────────
def seed_premises(tenant, marker):
    premises_type = metering_models.PremisesType.objects.create(
        tenant=tenant, code=f"{marker}-res", name=f"{marker} Residential"
    )
    return metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"P-{marker}",
        address_line=f"{marker} Elm Street",
        city="Katy",
        premises_type=premises_type,
        services_available=["electric"],
        owner_manager=f"{marker} Property Co",
        status="active",
    )


def seed_audit_row(tenant, actor):
    return AuditLog.objects.create(
        tenant_id=tenant.id,
        actor_user_id=actor.id,
        action="invoice.issued",
        entity_type="invoice",
        entity_id=uuid.uuid4(),
        after={"total": "142.50"},
    )


def list_export(client, resource="premises", *, tenant=None):
    kwargs = {"tenant": tenant} if tenant else {}
    response = api_post(client, "/exports", {"resource": resource}, **kwargs)
    assert response.status_code == 202, response.content
    return response.json()


def audit_export(client, *, tenant=None):
    kwargs = {"tenant": tenant} if tenant else {}
    response = api_post(client, "/audit-log/export?f.action=invoice.issued", **kwargs)
    assert response.status_code == 202, response.content
    return response.json()


# ── jobs built by hand, for the states a real export never rests in ─────────
def queued_job(tenant, *, kind=export_kernel.LIST_EXPORT_JOB):
    """An enqueued job with the transport switched OFF, so nothing runs it."""
    previous = core_jobs._dispatcher
    core_jobs.set_job_dispatcher(None)
    try:
        with core_tenancy.tenant_context(tenant.id):
            return core_jobs.enqueue(kind, payload={"resource": "premises"})
    finally:
        core_jobs.set_job_dispatcher(previous)


def finished_job(tenant, tmp_path, *, kind, body=b"secret,payload\r\n1,2\r\n"):
    """A SUCCEEDED job of any kind, with a REAL stored file behind it."""
    record = queued_job(tenant, kind=kind)
    source = tmp_path / f"{tenant.subdomain}_{uuid.uuid4().hex[:6]}.csv"
    source.write_bytes(body)
    with core_tenancy.tenant_context(tenant.id):
        core_jobs.start(record["id"])
        link = export_kernel.finish_artifact(record["id"], source, tenant_id=tenant.id)
        core_jobs.succeed(record["id"], result_link=link)
    return record


def handed_over(response, bucket):
    """Follow the route the way a browser does: a 302 to a signed link for the
    job's own object, whose bytes are read from the bucket."""
    assert response.status_code == 302, response.content
    assert response["Cache-Control"] == "no-store, private"
    location = urllib.parse.urlparse(response["Location"])
    query = urllib.parse.parse_qs(location.query)
    key = urllib.parse.unquote(location.path).lstrip("/")
    if key.startswith(f"{BUCKET}/"):  # path-style URL
        key = key[len(BUCKET) + 1 :]
    body = bucket.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    return key, query, body


def refusal_of(response):
    """The comparable shape of a refusal: everything except the per-request
    trace id, which is unique by design."""
    payload = response.json()
    return (
        response.status_code,
        payload["code"],
        payload["message_key"],
        json.dumps(payload["params"], sort_keys=True),
        json.dumps(payload["field_errors"], sort_keys=True),
    )


# ── what it hands over ──────────────────────────────────────────────────────
def test_download_hands_over_the_finished_list_export(idn, wired):
    """BR-REP-018/IS-11: a SUCCEEDED export is a real file, named with the IS-9
    filename the writer composed, holding the CSV the job actually wrote."""
    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    alex = signed_in_client(*ALEX)

    accepted = list_export(alex)
    job = tenancy_models.Job.objects.get(id=accepted["job_id"])
    row = JobArtifact.objects.get(job_id=job.id)

    key, query, body = handed_over(api_get(alex, job.result_link), wired)

    assert key == row.storage_key
    assert key.startswith("t/silvercreek/export/") and key.endswith(".csv")
    assert query["response-content-type"] == ["text/csv; charset=utf-8"]
    assert query["response-content-disposition"] == [f'attachment; filename="{row.display_name}"']
    # The IS-11 five-segment name, unchanged by the route that serves it.
    assert row.display_name.startswith("silvercreek_premises_full-list_current-state_")
    assert row.display_name.endswith(".csv")
    assert b"P-sc" in body
    assert row.byte_length == len(body)


def test_the_poll_result_link_is_the_download_route(idn, wired):
    """The whole chain the 202 promises: POST → poll → follow result_link →
    the file. Neither a key nor a path ever reaches the client."""
    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    alex = signed_in_client(*ALEX)

    accepted = list_export(alex)
    polled = api_get(alex, accepted["status_url"]).json()

    assert polled["status"] == core_jobs.SUCCEEDED
    assert polled["result_link"] == f"/api/exports/{accepted['job_id']}/file"
    assert api_get(alex, polled["result_link"]).status_code == 302
    assert "t/silvercreek/export" not in json.dumps(polled)
    assert "artifact_path" not in json.dumps(polled)


def test_the_export_leaves_nothing_on_disk_and_no_path_on_the_job(idn, wired):
    """DEF-MET-4954: the job record carried the WRITING container's disk path.
    Now nothing is written to a shared directory and the payload has no path."""
    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    accepted = list_export(signed_in_client(*ALEX))
    job = tenancy_models.Job.objects.get(id=accepted["job_id"])
    assert "artifact_path" not in (job.payload or {})
    assert JobArtifact.objects.get(job_id=job.id).status == "stored"


def test_the_audit_export_downloads_through_the_same_route(idn, wired):
    """US-AUD-006: S61's artifact is served by the SAME endpoint — the route
    belongs to whoever hosts the jobs table, not to the producing module, and
    `audit_export` reaches it by registering its kind (AuditConfig.ready)."""
    users = idn.seed_silvercreek()
    seed_audit_row(idn.silvercreek, users.alex)
    alex = signed_in_client(*ALEX)

    accepted = audit_export(alex)
    job = tenancy_models.Job.objects.get(id=accepted["job_id"])
    assert job.status == core_jobs.SUCCEEDED, job.error
    assert job.kind == "audit_export"

    row = JobArtifact.objects.get(job_id=job.id)
    key, query, body = handed_over(api_get(alex, job.result_link), wired)
    assert key.startswith("t/silvercreek/export/")
    assert row.display_name.startswith("silvercreek_audit-log_hot-window_event-time_")
    downloaded = body.decode("utf-8")
    assert downloaded.splitlines()[0] == "when,actor,action,entity_type,entity_id,summary,source"
    assert "invoice.issued" in downloaded


def test_both_export_kinds_are_registered_for_download(wired):
    """The registry, stated: `list_export` is the kernel's own, `audit_export`
    arrives from AuditConfig.ready(), and `billing.bills.print_set` from
    BillingConfig.ready(). A NAMED SET, so a kind cannot join or leave quietly.
    """
    assert export_kernel.downloadable_kinds() == (
        "audit_export",
        "billing.bills.print_set",
        "list_export",
    )


def test_any_signed_in_role_may_download_what_their_tenant_exported(idn, wired):
    """The same gate the export's own accept applies."""
    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    accepted = list_export(signed_in_client(*ALEX))

    clerk = signed_in_client(*PRIYA)
    assert api_get(clerk, f"/exports/{accepted['job_id']}/file").status_code == 302


def test_downloading_without_a_session_is_401(idn, wired):
    from django.test import Client

    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    accepted = list_export(signed_in_client(*ALEX))
    assert api_get(Client(), f"/exports/{accepted['job_id']}/file").status_code == 401


def test_the_download_is_read_only(idn, wired):
    """An artifact is the RUNNER's output; a client only fetches it."""
    idn.seed_silvercreek()
    seed_premises(idn.silvercreek, "sc")
    accepted = list_export(signed_in_client(*ALEX))
    alex = signed_in_client(*ALEX)
    path = f"/exports/{accepted['job_id']}/file"
    assert api_post(alex, path).status_code == 405
    assert api_delete(alex, path).status_code == 405


# ── the noes, and the fact that they are ONE no ─────────────────────────────
def test_every_refusal_is_the_same_404(idn, wired, tmp_path):
    """HR-1 / 11b G4, asserted as an EQUALITY: unknown · another tenant's · not
    an export · not finished · swept · past retention must be indistinguishable,
    or the route becomes an oracle for which job ids exist."""
    idn.seed_silvercreek()
    idn.seed_bluemesa_admin()
    seed_premises(idn.silvercreek, "sc")
    alex = signed_in_client(*ALEX)

    # 1 — an id that never existed
    unknown = api_get(alex, f"/exports/{uuid.uuid4()}/file")

    # 2 — a real, finished export belonging to ANOTHER tenant
    seed_premises(idn.bluemesa, "bm")
    jordan = signed_in_client(*JORDAN, tenant=BM)
    theirs = list_export(jordan, tenant=BM)
    foreign = api_get(alex, f"/exports/{theirs['job_id']}/file")

    # 3 — a SUCCEEDED job of this tenant that is not an export at all, with a
    #     real stored file behind it: only the KIND stands between it and the wire
    other_kind = finished_job(idn.silvercreek, tmp_path, kind="bill_run")
    wrong_kind = api_get(alex, f"/exports/{other_kind['id']}/file")

    # 4 — this tenant's own export, still queued
    unfinished = queued_job(idn.silvercreek)
    pending = api_get(alex, f"/exports/{unfinished['id']}/file")

    # 5 — a succeeded export the daily sweep has deleted (BR-REP-018)
    gone = finished_job(idn.silvercreek, tmp_path, kind=export_kernel.LIST_EXPORT_JOB)
    JobArtifact.objects.filter(job_id=gone["id"]).update(status="deleted", deleted_at=timezone.now())
    swept = api_get(alex, f"/exports/{gone['id']}/file")

    # 6 — a succeeded export past the utility's retention, NOT YET swept
    #     (BR-TEN-043: retention is read now, not when the sweep gets there)
    old = finished_job(idn.silvercreek, tmp_path, kind=export_kernel.LIST_EXPORT_JOB)
    JobArtifact.objects.filter(job_id=old["id"]).update(
        created_at=timezone.now() - dt.timedelta(days=4)
    )
    expired = api_get(alex, f"/exports/{old['id']}/file")

    every = (unknown, foreign, wrong_kind, pending, swept, expired)
    assert all(response.status_code == 404 for response in every)
    assert len({refusal_of(response) for response in every}) == 1
    assert refusal_of(unknown)[1] is None  # a 404 carries no catalog code
    assert "Location" not in wrong_kind  # …and no link to the decoy's bytes left


def test_a_running_export_is_not_downloadable_mid_write(idn, wired):
    """A half-written file is not a file. `succeeded` is the only status that
    opens the route."""
    idn.seed_silvercreek()
    record = queued_job(idn.silvercreek)
    with core_tenancy.tenant_context(idn.silvercreek.id):
        core_jobs.start(record["id"])
    alex = signed_in_client(*ALEX)
    assert api_get(alex, f"/exports/{record['id']}/file").status_code == 404


def test_a_failed_export_is_not_downloadable(idn, wired):
    idn.seed_silvercreek()
    record = queued_job(idn.silvercreek)
    with core_tenancy.tenant_context(idn.silvercreek.id):
        core_jobs.start(record["id"])
        core_jobs.fail(record["id"], error="OSError: disk full")
    alex = signed_in_client(*ALEX)
    assert api_get(alex, f"/exports/{record['id']}/file").status_code == 404


def test_a_job_finished_before_the_move_has_no_file_to_hand_over(idn, wired):
    """An export made before 2026-10-02 left only `payload.artifact_path` (a
    disk path) and no row. It answers the same 404 as an expired file — the
    honest state of a transient file that was on a disk this deployment no
    longer reads (09-infra/04-exports-to-s3.md R3)."""
    idn.seed_silvercreek()
    record = queued_job(idn.silvercreek)
    with core_tenancy.tenant_context(idn.silvercreek.id):
        core_jobs.start(record["id"])
        tenancy_models.Job.objects.filter(id=record["id"]).update(
            payload={"resource": "premises", "artifact_path": "/app/var/artifacts/x.csv"}
        )
        core_jobs.succeed(record["id"], result_link=export_kernel.download_path(record["id"]))
    alex = signed_in_client(*ALEX)
    assert api_get(alex, f"/exports/{record['id']}/file").status_code == 404
    with core_tenancy.tenant_context(idn.silvercreek.id):
        assert export_store.for_job(record["id"]) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-008@17df6a0 (EP-SHL-02 §Stories — hash = sha256/7 of the source epic; co-packet US-AUD-006@009e809 for the S61 artifact this route also serves)
# generated: 2026-08-10 by story-coder v1 (download lane — GET /exports/{job_id}/file, the endpoint three previous packets recorded as missing) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ · pytest tests/test_be_export_download.py 17 passed✔ · suite `pytest tests -m "not golden and not isolation"` 786 passed / 7 skipped / 47 deselected (762 was the baseline when this lane started) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · [path-tenancy lane 2026-08-10] ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔
# exceptions: the RLS half of the cross-tenant refusal belongs to the G5 isolation suite (sqlite cannot enforce RLS); the app-filter half is asserted here, and the two halves are the same law · the actor-scoping disposition is inherited from GET /jobs/{id} (tenant scope, not "the user who started it" — the BE-07 record has no actor column) and is asserted, not silently accepted · a malformed (non-uuid) job id is refused by the URL resolver before the view, so it is Django's 404 rather than the BE-02 envelope's — the four in-view noes are the ones this file proves identical · [path-tenancy lane 2026-08-10] the download route is `/api/exports/{id}/file`; requests name their tenant instead of a Host
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
