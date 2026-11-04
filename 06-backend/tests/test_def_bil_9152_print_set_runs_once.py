# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9152 — a print set asked for WITHOUT the background flag ran
#           TWICE when a worker existed: `POST /billing/print-sets` handed the
#           record to the transport (JOBS_EAGER=false → celery-billing) and then
#           ALSO ran it inline in the web request because the record still read
#           `queued`, so the web request answered 500 while the worker built the set.
# Code:     06-backend/apps/billing/print_api.py `print_sets`
# Rules:    CR-053 task 13 · DEF-2487 (never queued into a void) · B12 r1
# ───────────────────────────────────────────────────────
"""ONE REQUEST, ONE RUN OF THE JOB BODY — whichever process runs it.

The decision is the one every billing job door makes (`run_check`,
`run_calculate`): ask `would_run()` — is something consuming billing's queue?
Yes → hand the record to it and answer 202. No → run it here and answer 201,
with the record handed to NOBODY, because a message sent to a queue with no
consumer is a second run waiting to happen the day a worker starts.

The worker in these cases is a TRANSPORT THAT RECORDS what it was handed, and
the delivery is `apps.tenancy.tasks.run_pending_job` — the real Celery task
body — so "ran on the worker" means the same door production uses.

⚠ RED FIRST, on the code before the fix (2026-10-02):
    test_with_a_worker_the_request_hands_over_and_does_not_also_run_it
        assert 201 == 202   (the request ran the body inline AND handed it over)
    test_with_no_worker_the_request_runs_it_and_hands_it_to_nobody
        assert ['…'] == []  (handed to a queue nobody consumes, then run inline)
"""

from __future__ import annotations

import pytest

from apps.billing import print_set
from apps.tenancy import services as tenancy_services
from apps.tenancy import tasks as tenancy_tasks
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant  # noqa: F401
from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_cr101_print_bills import a_mailing_address, a_printable_bill

pytestmark = pytest.mark.django_db

GENERATED_AT = "2026-10-02T09:41:00+00:00"


@pytest.fixture()
def transport(settings, monkeypatch):
    """The real store, a recording transport, and a counted job body.

    `ready` is what the dispatch probe answers — a worker consuming billing's
    queue, or none. `handed` is every record the request gave the transport;
    `runs` is every time the print-set BODY executed, in any process.
    """
    settings.JOBS_EAGER = False
    state = {"ready": True, "handed": [], "runs": 0}

    previous = (core_jobs._store, core_jobs._dispatcher, core_jobs._dispatch_probe)
    real_body = core_jobs.job_handler(print_set.PRINT_SET_JOB)

    def counted(record):
        state["runs"] += 1
        return real_body(record)

    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(lambda record: state["handed"].append(record))
    core_jobs.set_dispatch_probe(
        lambda queue=None: (state["ready"], "test worker" if state["ready"] else "no worker")
    )
    core_jobs.set_job_handler(print_set.PRINT_SET_JOB, counted)
    yield state
    core_jobs.set_job_handler(print_set.PRINT_SET_JOB, real_body)
    core_jobs.set_job_store(previous[0])
    core_jobs.set_job_dispatcher(previous[1])
    core_jobs.set_dispatch_probe(previous[2])


def _one_printable_bill(tenant, actor):
    with tenant_ctx(tenant):
        account = an_account(tenant, actor, account_no="A-91", label="Unit Q")
        a_mailing_address(tenant, account)
        a_printable_bill(tenant, account, invoice_no="BL-2610-000091")


def _post(tenant, actor, body):
    """A real DRF POST through the view — the door the defect was in."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.billing import print_api

    request = APIRequestFactory().post("/api/v1/billing/print-sets", body, format="json")
    force_authenticate(request, user=actor.user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return print_api.print_sets(request)


def _status(job_id, tenant):
    with tenant_ctx(tenant):
        return core_jobs.current(str(job_id))["status"]


def test_with_a_worker_the_request_hands_over_and_does_not_also_run_it(brazos, marcus, transport):
    _one_printable_bill(brazos, marcus)

    response = _post(brazos, marcus, {"filters": {}, "generated_at": GENERATED_AT})

    assert response.status_code == 202, response.data
    # The web request ran NOTHING; it handed the record over exactly once.
    assert transport["runs"] == 0
    assert [str(r["id"]) for r in transport["handed"]] == [str(response.data["job_id"])]

    # The worker's delivery — the real Celery task body — is the one run.
    record = transport["handed"][0]
    tenancy_tasks.run_pending_job(str(record["id"]), str(brazos.id), kind=str(record["kind"]))
    assert transport["runs"] == 1
    assert _status(record["id"], brazos) == core_jobs.SUCCEEDED


def test_with_no_worker_the_request_runs_it_and_hands_it_to_nobody(brazos, marcus, transport):
    transport["ready"] = False
    _one_printable_bill(brazos, marcus)

    response = _post(brazos, marcus, {"filters": {}, "generated_at": GENERATED_AT})

    assert response.status_code == 201, response.data
    assert transport["runs"] == 1
    # Nothing was sent to a queue nobody consumes: a worker started tomorrow
    # must not find a second copy of this set waiting for it.
    assert [str(r["id"]) for r in transport["handed"]] == []
    assert _status(response.data["job_id"], brazos) == core_jobs.SUCCEEDED


def test_asking_for_the_background_with_no_worker_also_runs_it_once(brazos, marcus, transport):
    """The flag's own fall-back (DEF-2487) takes the same inline path."""
    transport["ready"] = False
    _one_printable_bill(brazos, marcus)

    response = _post(
        brazos, marcus, {"filters": {}, "generated_at": GENERATED_AT, "background": True}
    )

    assert response.status_code == 201, response.data
    assert transport["runs"] == 1
    assert transport["handed"] == []


def test_under_eager_dispatch_the_body_runs_once_in_this_process(brazos, marcus, transport, settings):
    """JOBS_EAGER: the real transport runs the body inside `enqueue`."""
    settings.JOBS_EAGER = True
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    core_jobs.set_dispatch_probe(tenancy_services.job_dispatch_ready)
    _one_printable_bill(brazos, marcus)

    response = _post(brazos, marcus, {"filters": {}, "generated_at": GENERATED_AT})

    assert response.status_code in (201, 202), response.data
    assert transport["runs"] == 1
    assert _status(response.data["job_id"], brazos) == core_jobs.SUCCEEDED
