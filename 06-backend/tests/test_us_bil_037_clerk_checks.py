# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (bulk run · Check) TC-5, TC-8, TC-15 · US-BIL-038 (Calculate) TC-4
# Checks:   04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md U5 · F1 · F2 · U3
# Defects:  DEF-BIL-8418 (Answer for all not pre-selected from the Billing
#           defaults) · DEF-BIL-8511 (Resume ran the rest of the Check inside
#           the clerk's web request) · DEF-BIL-8510 (no test-only way to take
#           Meter Reads down)
# Rules:    BR-BIL-1040 (amended 2026-09-30 — answers at Check, pre-selected
#           from S66, stored on the run) · BR-BIL-051/052 (background,
#           restartable) · B21 (a utility-wide stop names what and who)
# ───────────────────────────────────────────────────────
"""The final bulk-run lane's clerk checks, each written red first."""

from __future__ import annotations

import pytest

from apps.billing import check_api, check_store, decisions, run_jobs
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.test_bbr_check_engine import three_accounts
from tests.test_bbr_check_store import a_run
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _tag(summary, code):
    for category in summary["categories"]:
        for tag in category["tags"]:
            if tag["code"] == code:
                return tag
    raise AssertionError(f"no tag {code}")


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · DEF-BIL-8418 · U5 — Answer for all opens on the S66 default and the
# run STORES it; a tag with no S66 setting opens on its first choice and
# stores nothing (no automatic fix — changes row 45).
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-20
def test_us_bil_037_tc8__answer_for_all_opens_on_the_billing_default_and_is_stored(brazos, dana):
    with tenant_ctx(brazos):
        # Not the seeded `estimate`: proves the setting is read, not a literal.
        tenancy_services.save_settings_family(
            dana, "billing-defaults", {"run_default_missing_read": "hold"}
        )
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)

        standing = decisions.standing_answers(run)
        summary = check_store.findings_summary(run)
        missing = _tag(summary, "missing_read")
        no_plan = _tag(summary, "unit_has_no_plan")
    assert standing.get("missing_read") == "hold", standing
    assert missing["default_choice"] == "hold"
    assert missing["answer_for_all"] == "hold"
    # PO 2026-10-01 (BR-BIL-1063): *No plan* BLOCKS — there is nothing to
    # choose (no default plan), so no default and nothing stored.
    assert no_plan["default_choice"] is None
    assert no_plan["answer_for_all"] is None
    assert "unit_has_no_plan" not in standing


# BULK-CHG-20
def test_us_bil_037_tc8__a_clerks_answer_is_never_overwritten_by_the_default(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        decisions.set_standing_answer(
            bill_run=run, case="missing_read", choice=decisions.CHOICE_BILL_WITHOUT_SERVICE
        )
        check_store.check_run(run)  # Check again — a whole pass
        standing = decisions.standing_answers(run)
    assert standing["missing_read"] == decisions.CHOICE_BILL_WITHOUT_SERVICE


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · DEF-BIL-8511 · F1 / U3 — Resume hands the Check BACK TO THE WORKER.
# It never runs the rest of the Check inside the clerk's request (60 s).
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def captured_dispatch():
    """The transport, captured: what Resume HANDS to a worker, never run."""
    sent: list[dict] = []
    before = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(lambda record: sent.append(dict(record)))
    try:
        yield sent
    finally:
        core_jobs.set_job_dispatcher(before)


def _check_job(run, *, status, sent=None):
    """A Check job left as a worker leaves it: `running` (killed) or `failed`.
    `sent` (the captured transport) is emptied after the ENQUEUE's own dispatch,
    so a test reads only what Resume handed over."""
    from apps.billing import check_models

    record = run_jobs.enqueue_check(run)
    core_jobs.start(record["id"])
    core_jobs.record_progress(
        record["id"], done=1, total=3, checkpoint={"done": 1, "account_no": "A-00101"}
    )
    if status == core_jobs.FAILED:
        core_jobs.fail(record["id"], "the machine working on this stopped before it finished")
    run.findings_summary = {**(run.findings_summary or {}), "job_id": record["id"]}
    run.save(update_fields=["findings_summary", "updated_at"])
    check_models.BillRunAccountCheck.objects.filter(bill_run=run).delete()
    if sent is not None:
        sent.clear()
    return record


def _clerk(brazos):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    return an_actor_user(brazos)


# BULK-CHG-25
def test_us_bil_037_tc5__resume_hands_a_stopped_check_to_the_worker_and_runs_nothing_here(
    brazos, dana, captured_dispatch, django_capture_on_commit_callbacks
):
    from apps.billing import check_models
    from tests.test_us_met_helpers import api_call

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        record = _check_job(run, status=core_jobs.FAILED, sent=captured_dispatch)
        clerk = _clerk(brazos)
    with django_capture_on_commit_callbacks(execute=True):
        answer = api_call(
            check_api.run_check_resume,
            "post",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            data={},
            run_id=str(run.pk),
        )
    with tenant_ctx(brazos):
        saved = check_models.BillRunAccountCheck.objects.filter(bill_run=run).count()
        after = core_jobs.current(record["id"])
    assert answer.status_code == 202, answer.data
    assert answer.data["resumed"] is True
    # Handed to the transport ONCE, as a queued record with its checkpoint…
    assert [one["id"] for one in captured_dispatch] == [record["id"]]
    assert captured_dispatch[0]["status"] == core_jobs.QUEUED
    assert after["checkpoint"]["account_no"] == "A-00101"
    # …and not one account checked inside the request (RED before: 3 saved).
    assert saved == 0


# BULK-CHG-25
def test_us_bil_037_tc5__a_check_a_worker_is_still_on_is_left_alone(
    brazos, dana, captured_dispatch, settings
):
    settings.BILLING_JOB_STOPPED_FLOOR_SECONDS = 0
    before = core_jobs._liveness_probe  # noqa: SLF001
    core_jobs.set_liveness_probe(lambda job_id: True)
    try:
        with tenant_ctx(brazos):
            cycle, _plan, _accounts = three_accounts(brazos, dana)
            run = a_run(cycle)
            record = _check_job(run, status=core_jobs.RUNNING, sent=captured_dispatch)
            _record, outcome = run_jobs.resume_job(run, record["id"])
    finally:
        core_jobs.set_liveness_probe(before)
    assert outcome == core_jobs.STILL_RUNNING
    assert captured_dispatch == []


# BULK-CHG-25
def test_us_bil_037_tc5__a_killed_workers_check_comes_back_on_the_screens_next_poll(
    brazos, dana, captured_dispatch, settings, django_capture_on_commit_callbacks
):
    """F1: a SIGKILL writes nothing, so the job says `running` with nobody on
    it. When the workers answer and none has it, the Check screen's own poll
    hands it back — not the broker's 8,820 s redelivery."""
    from tests.test_us_met_helpers import api_call

    settings.BILLING_JOB_STOPPED_FLOOR_SECONDS = 0
    before = core_jobs._liveness_probe  # noqa: SLF001
    core_jobs.set_liveness_probe(lambda job_id: False)
    try:
        with tenant_ctx(brazos):
            cycle, _plan, _accounts = three_accounts(brazos, dana)
            run = a_run(cycle)
            record = _check_job(run, status=core_jobs.RUNNING, sent=captured_dispatch)
            clerk = _clerk(brazos)
        with django_capture_on_commit_callbacks(execute=True):
            polled = api_call(
                check_api.run_check,
                "get",
                user=clerk,
                role="billing_clerk",
                tenant=brazos,
                run_id=str(run.pk),
            )
    finally:
        core_jobs.set_liveness_probe(before)
    assert polled.status_code == 200, polled.data
    assert polled.data["job"]["resumed"] is True
    assert [one["id"] for one in captured_dispatch] == [record["id"]]


# ══════════════════════════════════════════════════════════════════════════
# TC-15 · DEF-BIL-8510 · F2 — a TEST-ONLY switch takes Meter Reads down; the
# stop names what and who in the error envelope; production cannot flip it.
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-24
def test_us_bil_037_tc15__the_walk_switch_takes_meter_reads_down_and_the_stop_names_what_and_who(
    brazos, dana, settings, tmp_path
):
    from tests.test_us_met_helpers import api_call

    settings.WALK_SWITCHES_DIR = str(tmp_path)
    settings.WALK_SWITCHES_FORBIDDEN = False
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        clerk = _clerk(brazos)
    (tmp_path / "meter_reads.down").write_text("walk")
    down = api_call(
        check_api.run_check,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        data={"background": False},
        run_id=str(run.pk),
    )
    (tmp_path / "meter_reads.down").unlink()
    up = api_call(
        check_api.run_check,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        data={"background": False},
        run_id=str(run.pk),
    )
    assert down.status_code == 503
    assert down.data["message_key"] == "billing.bulkRun.check.down.meter_reads"
    assert down.data["params"]["module"] == "meter_reads"
    assert down.data["params"]["who"] == "support"
    assert down.data["params"]["ref"].startswith("SBH-")
    assert up.status_code == 200, up.data  # the run was kept, and carries on
    assert up.data["counts"]["accounts"] == 3


# BULK-CHG-24
def test_us_bil_037_tc15__production_can_never_flip_the_switch(settings, tmp_path):
    from pathlib import Path

    from core import walk_switches

    (tmp_path / "meter_reads.down").write_text("walk")
    settings.WALK_SWITCHES_DIR = str(tmp_path)
    settings.WALK_SWITCHES_FORBIDDEN = True  # what production.py sets
    assert walk_switches.is_down("meter_reads") is False
    settings.WALK_SWITCHES_FORBIDDEN = False
    settings.WALK_SWITCHES_DIR = ""  # the default everywhere
    assert walk_switches.is_down("meter_reads") is False
    production = (
        Path(__file__).resolve().parents[1] / "config/settings/production.py"
    ).read_text()
    assert 'WALK_SWITCHES_DIR = ""' in production
    assert "WALK_SWITCHES_FORBIDDEN = True" in production


# ══════════════════════════════════════════════════════════════════════════
# F4 · DEF-BIL-8512 — the second clerk sees who else has the run open.
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40
def test_us_bil_037_f4__the_second_clerk_is_told_who_else_has_the_run_open(brazos, dana):
    from types import SimpleNamespace

    from django.core.cache import cache

    from apps.billing import run_presence

    cache.clear()
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        first = SimpleNamespace(id="u-1", full_name="Dana Whitfield")
        second = SimpleNamespace(id="u-2", full_name="Marcus Webb")
        alone = run_presence.touch(run, first)
        told = run_presence.touch(run, second)
        back = run_presence.touch(run, first)
    assert alone == []
    assert told == [{"name": "Dana Whitfield"}]
    assert back == [{"name": "Marcus Webb"}]


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-040 TC-3 · DEF-BIL-8421 · F3 — a bill that breaks at Send is FILED
# with its reason; *Retry failed* sends only it; nothing is sent twice.
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-40
def test_us_bil_040_tc3__a_send_break_is_filed_and_a_retry_sends_only_it(
    brazos, dana, monkeypatch
):
    from apps.billing import issue, release
    from apps.billing import models as billing_models
    from apps.billing.exceptions import BillingRuleError
    from tests.test_def_bil_5352_run_status_machine import (
        a_releasable_run,
        authorise,
        release_the_run,
    )

    real = issue.issue_invoice
    broken_no = {"value": None}

    def one_bill_breaks(draft, **kwargs):
        if draft.invoice_no == broken_no["value"]:
            raise BillingRuleError(
                "service 'electric' has no revenue account configured, so its usage line "
                "cannot be stamped (BR-BIL-010)."
            )
        return real(draft, **kwargs)

    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=2, key="2026-06|f3")
        drafts = list(billing_models.Invoice.objects.filter(bill_run=run).order_by("invoice_no"))
        broken_no["value"] = drafts[1].invoice_no
        monkeypatch.setattr(issue, "issue_invoice", one_bill_breaks)
        first = release_the_run(run, authorise(run, dana), dana)
        filed = list(
            billing_models.BillRunBreak.objects.filter(
                bill_run=run, stage=billing_models.BREAK_STAGE_SEND, resolution__isnull=True
            )
        )
        # Fixed (the revenue account mapped): Retry failed — a second sign-off
        # row, then Send with nothing named.
        monkeypatch.setattr(issue, "issue_invoice", real)
        second = release_the_run(run, authorise(run, dana), dana)
        statuses = sorted(
            billing_models.Invoice.objects.filter(bill_run=run).values_list("status", flat=True)
        )
        closed = billing_models.BillRunBreak.objects.get(pk=filed[0].pk)
    assert first.issued.issued_count == 1
    assert [row.reason for row in filed] == ["line_has_no_gl_account"]
    assert str(filed[0].account_id) == str(drafts[1].account_id)
    # The retry issued ONLY the failed bill — the first was not sent twice.
    assert second.issued.issued_count == 1
    assert list(second.issued.issued) == [str(drafts[1].pk)]
    assert statuses.count(billing_models.INVOICE_DRAFT) == 0
    assert closed.resolution == billing_models.BREAK_RESOLUTION_ISSUED
