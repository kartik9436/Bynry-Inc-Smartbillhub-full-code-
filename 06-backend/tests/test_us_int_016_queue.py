# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-016 (EP-INT-05) — job kinds, the `integrations` queue and
#           its consuming worker, or neither. Screens: S141 (the 202)
# Rules:    BR-INT-041 (both halves in one commit; the default worker does
#           not drain it) · BR-INT-022 (a different process from the request)
#           · B12 r1 §3 (202 + job id) · DEF-320 · DEF-2487 (never queued
#           into a void) · CLAUDE.md hard-won law 7 (the gate is shown RED)
# Tests:    this file — TC-1 (the row before the message) · TC-2 (G80 red
#           and green) · TC-5 (a dropped message leaves ONE row) · TC-6 (two
#           tenants, two scope keys) · the routing table · the quadrants
# Impacts:  apps/integrations/jobs.py · runners/ · docker-compose.yml ·
#           10-scripts/gates/g80_integrations_queue_split.py
# ───────────────────────────────────────────────────────
"""US-INT-016 — the job row is written before the broker message, and the queue has both halves."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from apps.integrations import jobs as integration_jobs
from apps.integrations import models, runners, services
from apps.integrations.registry import REGISTRY
from apps.tenancy import models as tenancy_models
from config.celery_routes import route_job
from core import jobs as core_jobs
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import SMTP_FIELDS, post_connect, post_test, run_job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "10-scripts" / "gates" / "g80_integrations_queue_split.py"


def _gate():
    spec = importlib.util.spec_from_file_location("g80_integrations_queue_split", GATE)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(GATE.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.mark.django_db
def test_us_int_016_tc1_the_jobs_row_exists_before_the_broker_message_and_before_the_202(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    response = post_test(brazos, dana, "email_smtp")
    assert response.status_code == 202
    assert response.data["status_url"] == f"/api/jobs/{response.data['job_id']}"
    assert len(recording_dispatcher) == 1
    handed = recording_dispatcher[0]
    assert handed["id"] == response.data["job_id"]
    assert handed["row_existed"] is True, "the message left before the row was written"
    assert handed["row_status"] == core_jobs.QUEUED
    assert handed["queue"] == integration_jobs.INTEGRATIONS_QUEUE
    row = tenancy_models.Job.objects.get(id=response.data["job_id"])
    assert row.status == core_jobs.QUEUED and row.kind == integration_jobs.TEST_JOB
    assert row.scope_key.endswith(":test")


def test_us_int_016_tc2_the_gate_is_green_at_head_and_red_without_a_consumer():
    gate = _gate()
    status, detail = gate.run()
    assert status == "PASS", detail
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    # Not a RENAME — a consumer under another name still consumes; the sabotage
    # takes the queue off the worker's command line.
    without = compose.replace('"-Q", "integrations",', '"-Q", "elsewhere",', 1)
    problems, _seen = gate.findings(compose_text=without)
    assert any("NO service consumes the 'integrations' queue" in one for one in problems), problems
    # And the third half: the default worker must not drain it either.
    greedy = compose.replace('"-Q", "celery",', '"-Q", "celery,integrations",', 1)
    problems, _seen = gate.findings(compose_text=greedy)
    assert any("drains 'integrations' ALONGSIDE" in one for one in problems), problems
    assert gate.selftest() is True


def test_us_int_016_every_kind_routes_to_the_integrations_queue_through_celerys_own_router():
    for kind in integration_jobs.JOB_KINDS:
        assert core_jobs.job_queue(kind) == "integrations"
        assert route_job("smartbillhub.jobs.run_pending", kwargs={"kind": kind}) == {"queue": "integrations"}
    assert route_job("smartbillhub.jobs.run_pending", kwargs={"kind": "billing.run.calculate"}) == {"queue": "billing"}
    assert core_jobs.job_handler(integration_jobs.TEST_JOB) is integration_jobs.run_test_job
    assert core_jobs.job_handler(integration_jobs.RUN_JOB) is integration_jobs.run_run_job
    # ⚠ WAVE H GAVE `sweep_expiry` A BODY (2026-09-06), AND THIS LINE MOVED WITH
    # IT RATHER THAN BEING LOOSENED. Until then all three later kinds were
    # asserted handler-less, which was right: a stub that swallowed a message
    # would be `DEF-320` wearing a different coat. `US-INT-027` built the sweep,
    # so `integration.sweep_expiry` now resolves to `run_sweep_expiry_job` and
    # is asserted BY NAME — the same strength as the two above it, not a
    # weakened check. The remaining two stay handler-less until their waves.
    assert (
        core_jobs.job_handler(integration_jobs.SWEEP_EXPIRY_JOB)
        is integration_jobs.run_sweep_expiry_job
    )
    # Routed with no body: a message fails by name at run_pending, never silently.
    for later in (integration_jobs.SWEEP_DUE_JOB, integration_jobs.INBOUND_PROCESS_JOB):
        assert core_jobs.job_handler(later) is None


def test_us_int_016_the_compose_file_names_the_worker_and_the_default_worker_does_not_drain_it():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["celery-integrations"]
    assert worker["command"][worker["command"].index("-Q") + 1] == "integrations"
    assert worker["entrypoint"] == []
    assert worker["healthcheck"]["test"][0] == "CMD-SHELL" and "$(hostname)" in worker["healthcheck"]["test"][1].replace("$$", "$")
    assert worker["deploy"]["resources"]["limits"]["cpus"] and worker["deploy"]["replicas"] == 1
    default = compose["services"]["celery"]["command"]
    assert default[default.index("-Q") + 1] == "celery"
    billing = compose["services"]["celery-billing"]["command"]
    assert billing[billing.index("-Q") + 1] == "billing"


@pytest.mark.django_db
def test_us_int_016_tc5_a_dropped_message_leaves_one_queued_row_and_a_repeat_folds_into_it(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    first = post_test(brazos, dana, "email_smtp").data
    again = post_test(brazos, dana, "email_smtp").data
    assert first["job_id"] == again["job_id"], "the same scope while queued must fold into ONE row (NFR-16)"
    assert tenancy_models.Job.objects.filter(kind=integration_jobs.TEST_JOB).count() == 1
    assert tenancy_models.Job.objects.get(id=first["job_id"]).status == core_jobs.QUEUED


@pytest.mark.django_db
def test_us_int_016_tc6_two_tenants_get_two_jobs_and_neither_dedupes_the_other(
    brazos, dana, lonestar, erin, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    post_connect(lonestar, erin, "email_smtp", SMTP_FIELDS)
    one = post_test(brazos, dana, "email_smtp").data["job_id"]
    two = post_test(lonestar, erin, "email_smtp").data["job_id"]
    assert one != two
    rows = {str(r.id): r for r in tenancy_models.Job.objects.filter(kind=integration_jobs.TEST_JOB)}
    assert set(rows) == {one, two}
    assert rows[one].tenant_id == brazos.id and rows[two].tenant_id == lonestar.id
    assert rows[one].scope_key != rows[two].scope_key


@pytest.mark.django_db
def test_us_int_016_no_worker_on_the_queue_is_a_refusal_not_a_promise(brazos, dana, smtp_adapter, not_ready_probe):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    response = post_test(brazos, dana, "email_smtp")
    assert response.status_code == 409
    assert response.data["message_key"] == services.REFUSAL_NO_WORKER
    assert tenancy_models.Job.objects.filter(kind=integration_jobs.TEST_JOB).count() == 0


@pytest.mark.django_db
def test_us_int_016_a_queued_test_whose_adapter_went_away_closes_its_run_honestly(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    accepted = post_test(brazos, dana, "email_smtp").data
    REGISTRY.unregister_adapter("email_smtp")
    try:
        run_job(accepted)
    finally:
        REGISTRY.register_adapter("email_smtp", smtp_adapter)
    run = models.IntegrationRun.objects.get(operation="send_message")
    assert run.outcome == "failed" and run.summary == integration_jobs.NO_ADAPTER_SENTENCE
    assert len(integration_jobs.NO_ADAPTER_SENTENCE.split()) <= 6
    assert tenancy_models.Job.objects.get(id=accepted["job_id"]).status == core_jobs.SUCCEEDED


def test_us_int_016_the_four_quadrants_resolve_and_the_two_without_a_connector_raise_by_name():
    kiosk = REGISTRY.require("payments_kiosk")
    # ⚠ `gl_partner` until `CR-110-BRC04`. The SERVE quadrant is what this asserts
    # and it did not move: a finance system still reads FROM us.
    partner = REGISTRY.require("erp_workday")
    smtp = REGISTRY.require("email_smtp")
    meters = REGISTRY.require("meters_neptune360")
    assert runners.runner_for(smtp.operations[0]) is runners.deliver
    assert runners.runner_for(meters.operations[0]) is runners.fetch
    assert runners.runner_for(partner.operations[0]) is runners.serve
    assert runners.runner_for(kiosk.operations[0]) is runners.inbound
    # ⚠ **SERVE IS BUILT NOW (CR-069 wave S, `2.199.0`) AND THIS CASE MOVED
    # WITH IT.** `OQ-INT-1481` was ruled on 2026-09-04 (System Admin, audited
    # grant), and wave S then built the door — so `record_read()` RECORDS a
    # read instead of raising, and asserting it still names *wave R* would be
    # asserting the opposite of what shipped.
    #
    # `execute_run` is the half that still raises and always will: a partner's
    # read is not work WE start, so there is no batch to run. That is the claim
    # the quadrant table is actually making, and it is the one kept here.
    with pytest.raises(NotImplementedError, match="not work we start"):
        runners.serve.execute_run(connection=None, operation=partner.operations[0], adapter=None, work=[], trigger="manual")
    assert callable(runners.serve.record_read), (
        "wave S built the SERVE quadrant; `record_read` writes an `inbound_read` "
        "run and its cases live in tests/test_us_int_041_partner_surface.py"
    )
    # ⚠ **AND THE INBOUND HALF MOVED THE SAME WAY, ONE WAVE LATER (CR-069 wave
    # N, `2.202.0`).** This line asserted `match="US-INT-044"` — the wave B
    # stub's *not built yet* — and `US-INT-044` is now BUILT, so keeping it
    # would have been a hold nobody released: hard-won law 2's mirror, a
    # refusal still true in a test over a door that is live. It went RED on
    # the wave that landed the door, which is exactly what a hold-expiry
    # assertion is for.
    #
    # `execute_run` is the half that still raises and always will, for the
    # same reason `serve`'s does: a partner's message is not work WE start,
    # so there is no batch to run. `receive()` is the door, and its cases are
    # in tests/test_us_int_044_inbound_door.py.
    with pytest.raises(NotImplementedError, match="not work we start"):
        runners.inbound.execute_run(connection=None, operation=kiosk.operations[0], adapter=None, work=[], trigger="manual")
    assert callable(runners.inbound.receive), (
        "wave N built the INBOUND quadrant; `receive` authenticates, dedupes, "
        "persists raw and replies — and stops there (BR-INT-058)"
    )
    assert runners.inbound.runbooks_apply(None) is None, (
        "the apply half is Runbooks' and is NOT built (BR-INT-058, OQ-INT-1729 (a))"
    )
