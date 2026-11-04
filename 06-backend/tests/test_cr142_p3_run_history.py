# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 (`P3.1`, `P3.5`).
#          Drawing p13–p14 (the task table) and p39 (screen `5·1`), read as
#          images per B14 rule 42.  Screens: `5·1` · `5·2`
# Rules:   BR-REP-018 (generated files retained 3 days) · NFR-3 (universal
#          server pagination) · CLAUDE.md rule 1 (tenant scoping, RLS FORCE) ·
#          B14 rule 31 (no database id is ever the visible value of a field)
# ───────────────────────────────────────────────────────
"""The run history, and the one thing it must never do.

**`P3.5` IS A BEHAVIOUR, NOT A CONSTANT.** A case that asserts
`ARTIFACT_RETENTION_DAYS == 3` proves the number and nothing about the screen.
These cases produce a run, age it past the window, and read what the ROW says
and whether the CONTROL is there — because a download button over a purged file
is the same defect as the toast this phase exists to fix.

⚠ **THE TWO REASONS A ROW EXPIRES ARE TESTED SEPARATELY, ON PURPOSE.** The
ruling is that retention is evaluated against the RUN'S TIMESTAMP, so
`test_a_run_older_than_the_window_expires_even_with_its_file_present` ages the
row and leaves the file exactly where it is. If that case passed only because
the file had also gone, it would be proving the wrong half and would go on
passing if the timestamp rule were deleted.
"""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports import run_history
from apps.tenancy import exports as export_kernel, models as tenancy_models, services
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def wired(tmp_path, settings):
    """The deployment's own wiring — real store, real transport, EAGER.

    ⚠ **`config/settings/test.py` SETS `JOBS_EAGER = False`, AND `JOBS_EAGER=1`
    IN THE ENVIRONMENT DOES NOT OVERRIDE IT.** The base settings read the
    variable; the test settings then assign the constant unconditionally. So a
    case that calls `request_list_export` without this fixture reaches for
    Celery and dies on `kombu.exceptions.OperationalError: Error 111 connecting
    to localhost:6379` — a traceback that names Redis and says nothing about
    the setting that sent it there. Measured: that is exactly how this file
    failed on its first run.

    The export file goes to the S3 EMULATOR (tests/conftest.py) — PO
    2026-10-02, exports in S3 everywhere — and each test's bucket is its own.
    """
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def _an_export(actor, tenant, *, resource="ar_aging"):
    """One real export, through the real accept path — never a hand-made row.

    ⚠ It goes through `request_list_export` rather than `Job.objects.create`
    because the three fields `5·1` draws that are NOT columns —
    `payload.actor_user_id`, `payload.filters`, `progress.done` — are written
    by that function and by nothing else. A hand-made job row would give this
    file a shape to assert against that the product never produces.
    """
    with tenant_ctx(tenant):
        return services.request_list_export(actor=actor, resource_name=resource, filters={})


def _runs(tenant):
    with tenant_ctx(tenant):
        return run_history.runs()


def test_a_run_appears_on_the_history_with_who_when_and_the_file(brazos, dana):
    _an_export(dana, brazos)
    page = _runs(brazos)
    assert page["total"] == 1
    row = page["rows"][0]
    assert row["report"] == "ar_aging"
    # ⚠ **A NAME, NEVER AN ID** (B14 rule 31) — and asserted against the row
    # identity actually holds rather than against a literal. `staff_actor`
    # wraps the user in a `SimpleNamespace(id, pk, role, user)`, so the name is
    # `dana.user.full_name`; reaching for `dana.full_name` is an
    # `AttributeError` and is how two of these cases first went red.
    assert row["started_by"] == dana.user.full_name
    assert row["started_by"] not in ("", None)
    assert row["ran_at"] is not None
    assert row["status"] == "ready"
    assert row["file"] == f"/api/exports/{row['id']}/file"


def test_the_row_carries_no_disk_path_and_no_user_id(brazos, dana):
    """B14 rule 31 + G28: neither an internal id nor a server path is served.

    ⚠ **ASSERTED ON THE WHOLE SERIALISED ROW, NOT ON NAMED KEYS.** A check that
    listed the keys it disapproves of would pass the day a new one was added.
    """
    _an_export(dana, brazos)
    row = _runs(brazos)["rows"][0]
    blob = json.dumps(row)
    assert "artifact_path" not in row
    assert "started_by_id" not in row
    assert "/var/artifacts" not in blob and ".csv" not in blob
    assert "/export/" not in blob and "t/brazosbend" not in blob  # no storage key either
    assert str(dana.id) not in blob


def test_a_run_older_than_the_window_expires_even_with_its_file_present(brazos, dana):
    """THE RULING: retention is evaluated against the RUN'S TIMESTAMP.

    ⚠ **THE FILE IS LEFT IN THE BUCKET ON PURPOSE.** A row surviving while its file
    does not is the designed state, and the timestamp is what decides it — so
    this case must fail if the timestamp rule is removed, even on a deployment
    whose sweep has not run. Asserting expiry over a file that had ALSO been
    deleted would prove the other half and hide this one.
    """
    from apps.tenancy.export_models import JobArtifact

    accepted = _an_export(dana, brazos)
    job_id = accepted["job_id"]
    with tenant_ctx(brazos):
        assert JobArtifact.objects.get(job_id=job_id).status == "stored", "the file must be there"
        assert run_history.run(job_id)["status"] == "ready"

        tenancy_models.Job.objects.filter(id=job_id).update(
            created_at=timezone.now()
            - timedelta(days=export_kernel.ARTIFACT_RETENTION_DAYS, hours=1)
        )
        aged = run_history.run(job_id)

    assert JobArtifact.objects.get(job_id=job_id).status == "stored", (
        "the file was not touched — only the clock moved"
    )
    assert aged["status"] == "expired"
    # ⚠ **THE POINT OF THE WHOLE CASE.** Never draw a download over a file the
    # product will not serve.
    assert aged["file"] is None


def test_a_run_whose_file_was_swept_is_expired_inside_the_window(brazos, dana):
    """The FILE half (PO 2026-10-02, exports in S3): the run is one day old,
    well inside the window, but its `job_artifacts` row says the file is gone
    — so no download is drawn over it. The bucket is never asked."""
    from apps.tenancy.export_models import JobArtifact

    accepted = _an_export(dana, brazos)
    job_id = accepted["job_id"]
    with tenant_ctx(brazos):
        JobArtifact.objects.filter(job_id=job_id).update(status="deleted", deleted_at=timezone.now())
        row = run_history.run(job_id)
    assert row["status"] == "expired"
    assert row["file"] is None


def test_an_expired_run_keeps_its_row_and_its_facts(brazos, dana):
    """A row outliving its file still says what ran, when, and how many rows."""
    accepted = _an_export(dana, brazos)
    with tenant_ctx(brazos):
        tenancy_models.Job.objects.filter(id=accepted["job_id"]).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        row = run_history.run(accepted["job_id"])
    assert row["status"] == "expired"
    assert row["report"] == "ar_aging" and row["started_by"] == dana.user.full_name
    assert row["rows"] is not None
    assert row["file"] is None


def test_the_status_filter_splits_ready_from_expired_in_sql(brazos, dana):
    """A filter whose pager counts what the filter shows (hard-won law 7).

    Two runs, one aged. `ready` must return one row AND a total of one — a
    total of two over one row is the shape a Python-side split produces.
    """
    fresh = _an_export(dana, brazos)
    stale = _an_export(dana, brazos, resource="billing_register")
    with tenant_ctx(brazos):
        tenancy_models.Job.objects.filter(id=stale["job_id"]).update(
            created_at=timezone.now() - timedelta(days=9)
        )
        ready = run_history.runs(status="ready")
        expired = run_history.runs(status="expired")
    assert ready["total"] == 1 and len(ready["rows"]) == 1
    assert ready["rows"][0]["id"] == str(fresh["job_id"])
    assert expired["total"] == 1 and expired["rows"][0]["id"] == str(stale["job_id"])


def test_the_page_is_cut_in_sql_and_the_pager_counts_the_whole_set(brazos, dana):
    """NFR-3. Three runs, `per=2`: two pages, no row on both, none missing."""
    for _ in range(3):
        _an_export(dana, brazos)
    with tenant_ctx(brazos):
        one = run_history.runs(per=2, page=1)
        two = run_history.runs(per=2, page=2)
        past_the_end = run_history.runs(per=2, page=99)
    assert one["total"] == 3 and one["pages"] == 2 and len(one["rows"]) == 2
    assert len(two["rows"]) == 1
    assert {row["id"] for row in one["rows"]} & {row["id"] for row in two["rows"]} == set()
    # A stale bookmark clamps rather than drawing an empty page over 3 rows.
    assert past_the_end["page"] == 2


def test_newest_first(brazos, dana):
    first = _an_export(dana, brazos)
    second = _an_export(dana, brazos, resource="billing_register")
    rows = _runs(brazos)["rows"]
    assert [row["id"] for row in rows] == [str(second["job_id"]), str(first["job_id"])]


def test_a_job_that_is_not_a_report_run_is_absent(brazos, dana):
    """The history is REPORT runs, not every job the platform has ever had."""
    with tenant_ctx(brazos):
        other = tenancy_models.Job.objects.create(
            tenant_id=brazos.id, kind="provisioning_plant", payload={"resource": "ar_aging"}
        )
        assert run_history.run(other.id) is None
        assert run_history.runs()["total"] == 0


def test_a_malformed_id_is_absent_rather_than_an_error(brazos):
    with tenant_ctx(brazos):
        assert run_history.run("not-a-uuid") is None


def test_the_ROUTE_answers_the_product_s_one_list_envelope(brazos, dana):
    """`{count, next, previous, results}` — asserted on the WIRE, not the selector.

    ⚠ **EVERY OTHER CASE IN THIS FILE CALLS `run_history.runs()`, WHICH IS THE
    LAYER BELOW THE BOUNDARY.** That is the right place for the ROW shape and
    the wrong one for the REPLY, and the difference is `DEF-WRK-4119`: three
    shipped Work screens drew their own *no results* state over rows the API
    had just returned, because a client typed from the selector's dict read
    `data.rows` as `undefined` and `undefined ?? []` is a legal empty array.
    `tsc`, eslint, 116 gates and 9,810 backend tests were green over all three
    for two waves.

    So this case goes through the ROUTE. It is the only one here that can see
    `_envelope` being dropped, and `G114` is the only other thing in the repo
    that could.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.reports import api as reports_api

    accepted = _an_export(dana, brazos)
    # ⚠ **THE VIEW, NOT THE SELECTOR.** The request factory is enough: what is
    # under test is `_envelope` reaching the reply, and a sign-in would add a
    # password the `staff_actor` fixture does not set without testing one more
    # thing about the boundary.
    request = APIRequestFactory().get("/api/brazosbend/reports/history")
    # ⚠ **THE THREE THINGS THE MIDDLEWARE ADDS AND A FACTORY DOES NOT**, copied
    # from `tests/test_cr092_asset_paging.py`, which already had this working
    # for the same reason — `DEF-AST-4120`, *"the shape on the wire was the
    # only thing nobody was checking"*.
    #
    # ⚠ **`force_authenticate` RATHER THAN `request.user = …`**: DRF's
    # `Request.user` re-runs the authenticators and overwrites whatever the
    # underlying Django request carried, so a direct assignment silently 401s.
    # This lane spent three runs rediscovering that, and the first two guesses
    # were a 403 (no `tenant_role`) and an `AttributeError` (`is_authenticated`
    # is a read-only property on `identity.User`, already returning True).
    # **Looking for the pattern that already worked was cheaper than any of
    # them** — CLAUDE.md law 11's last clause, one directory over.
    force_authenticate(request, user=dana.user)
    request.tenant_role = "system_admin"
    request.tenant_id = brazos.id
    with tenant_ctx(brazos):
        response = reports_api.report_runs(request)
    assert response.status_code == 200
    body = response.data

    # The four names, and NOT the selector's.
    assert set(body) >= {"count", "next", "previous", "results"}
    assert "rows" not in body and "per" not in body and "pages" not in body
    assert body["count"] == 1
    assert [row["id"] for row in body["results"]] == [str(accepted["job_id"])]

    # ⚠ **THE EXTRAS SURVIVE.** `_envelope` returns a FRESH dict and discards
    # every other key; `asset_work_orders` forgot to spread and
    # `maintenance_index` never left the server.
    assert body["reports"] and body["statuses"]
    assert "expired" in body["statuses"]


@pytest.mark.isolation
def test_one_tenants_runs_are_invisible_to_another(brazos, dana, lonestar, erin):
    """CLAUDE.md rule 1. Two tenants, one export each, neither sees the other.

    ⚠ **RUN THIS ON POSTGRESQL.** On SQLite there are no RLS policies at all,
    so the only thing enforcing the boundary is the explicit `tenant_id=`
    filter in the selector — which is real, and is half the guarantee. `G5`
    running this suite on sqlite and calling the skips a pass is recorded in
    CLAUDE.md as one of the shapes a check fails in.
    """
    mine = _an_export(dana, brazos)
    theirs = _an_export(erin, lonestar)

    with tenant_ctx(brazos):
        page = run_history.runs()
        assert [row["id"] for row in page["rows"]] == [str(mine["job_id"])]
        assert run_history.run(theirs["job_id"]) is None

    with tenant_ctx(lonestar):
        page = run_history.runs()
        assert [row["id"] for row in page["rows"]] == [str(theirs["job_id"])]
        assert run_history.run(mine["job_id"]) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P3.1 · P3.5 (05-prototype/09 Reports Build Brief.pdf p13-p14, p39-p43, read as images per B14 rule 42)
# screens: 5·1 · 5·2
# generated: 2026-09-27 by lane REP-P3
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `GET /api/brazosbend/reports/history` answered `422 VAL-005 reports.viewer.unknown_key {"key": "history"}` on the branch tip, through the real URLconf against real PostgreSQL 16, BEFORE these routes existed: the `/reports/<key>` catch-all swallowed the word, which is the exact hazard `P0.8` reserved the segment for.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
