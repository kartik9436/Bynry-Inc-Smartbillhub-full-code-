# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (bulk run · Send) · US-BIL-005 (issue)
# Defects:  DEF-BIL-8710 (a Send whose worker died never resumed; a hand-back
#           restarted its progress at 0) · DEF-BIL-8726 (the Send in batches)
# Rules:    CLAUDE.md hard rules 4 (an issued bill is never issued again) and 6
#           (idempotency) · hard-won law 14 (proved on PostgreSQL, never SQLite)
# ───────────────────────────────────────────────────────
"""A Send whose worker is KILLED part-way is handed back and issues no bill twice.

🔒 The idempotency proof the review ledger row cites (*"2026-10-01 · SEND AT
SCALE"*). A REAL kill, on a REAL PostgreSQL: a batch of the Send runs in a
SEPARATE Python process — its own connection, as a Celery worker has — and is
SIGKILLed with one bill issued and the next one half-issued inside its own
transaction. A SIGKILL writes nothing: no `fail()`, no rollback the process chooses,
only PostgreSQL abandoning whatever transaction the process held. The record is
left `running` with nobody on it, exactly as S3 measured on `sbh_s14_40k`.

Then the Send screen's own poll (`GET …/issue/progress`) hands the Send back,
and the case reads, from the database:

* every bill of the run issued ONCE — one `issued` status, one journal entry,
  one `invoice.issued` audit row each;
* every invoice number the one its draft carried, and none used twice;
* the release completed ONCE (`released_at`, one `bill_run.released` row);
* the resumed Send's progress starting from the bills already issued, not 0.

The child process is slowed by a test-only wrapper (half a second after each
bill it issues) so the kill lands mid-batch rather than racing it; the wrapper
changes no bill. The child's dispatcher records nothing, so the next batch it
would have pumped is lost with it, as a dead worker's would be.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.db import connection

from apps.billing import models as billing_models
from apps.billing import run_jobs, send_batches
from core import jobs as core_jobs

from tests.isolation_helpers import requires_postgres
from tests.test_def_bil_5352_run_status_machine import a_releasable_run, authorise
from tests.test_def_bil_8726_send_batches import Workers
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

BACKEND = Path(__file__).resolve().parent.parent
SENT_AT = datetime(2026, 10, 1, 9, 45, tzinfo=UTC)

#: `serialized_rollback=True` for the reason `test_bbr_f4_two_sends_pg` gives:
#: a transactional case tears down by FLUSHING the platform seed.
_TRANSACTIONAL = pytest.mark.django_db(transaction=True, serialized_rollback=True)

#: The worker, as a separate process: one batch, through `core.jobs.run_pending`.
CHILD = textwrap.dedent("""
    import sys, time
    import django
    django.setup()
    from apps.billing import issue
    from core import jobs as core_jobs

    core_jobs.set_job_dispatcher(lambda record: None)  # the next batch dies with us
    real = issue.issue_invoice

    def slowly(*args, **kwargs):
        billed = real(*args, **kwargs)
        print("ISSUED", flush=True)
        time.sleep(0.5)
        return billed

    issue.issue_invoice = slowly
    print("READY", flush=True)
    core_jobs.run_pending(sys.argv[1])
    print("FINISHED", flush=True)
    """)


def _child_env() -> dict[str, str]:
    db = connection.settings_dict
    url = f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    env = dict(os.environ)
    env.update(
        {
            "DATABASE_URL": url,
            "DJANGO_SETTINGS_MODULE": "config.settings.local",
            "JOBS_EAGER": "false",
            "PYTHONPATH": str(BACKEND),
        }
    )
    return env


def _issued(brazos, drafts) -> int:
    with tenant_ctx(brazos):
        return billing_models.Invoice.objects.filter(
            pk__in=drafts, status=billing_models.INVOICE_ISSUED
        ).count()


@requires_postgres
@pytest.mark.django_db
def test_8710_pg_this_file_is_actually_running_on_postgres():
    assert connection.vendor == "postgresql", connection.vendor


# BULK-CHG-40
@requires_postgres
@_TRANSACTIONAL
def test_8710_pg_a_send_killed_mid_batch_is_handed_back_and_issues_no_bill_twice(
    brazos, dana, monkeypatch, settings, django_capture_on_commit_callbacks
):
    from apps.audit import models as audit_models
    from apps.audit import services as audit_services
    from apps.billing import api as billing_api
    from apps.ledger import models as ledger_models
    from core import audit as core_audit

    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    # The platform's own audit trail, not the capture sink: the child process
    # writes to the table, and so must this one.
    core_audit.set_audit_sink(audit_services.store_row)
    monkeypatch.setattr(send_batches, "BATCH_SIZE", 3)
    settings.BILLING_SEND_BATCHES_PER_UTILITY = 2
    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=6, key="2026-06|8710-kill")
        authorise(run, dana)
        drafts = sorted(
            str(pk)
            for pk in billing_models.Invoice.objects.filter(bill_run=run).values_list(
                "pk", flat=True
            )
        )
        numbers_before = dict(
            billing_models.Invoice.objects.filter(pk__in=drafts).values_list("pk", "invoice_no")
        )
        clerk = an_actor_user(brazos)

    workers = Workers()
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(workers)
    try:
        with tenant_ctx(brazos):
            coordinator = run_jobs.enqueue_issue(
                run,
                issued_at=SENT_AT,
                released_at=SENT_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
            )
        workers.run(workers.take(run_jobs.ISSUE_JOB))
        batch = workers.take(send_batches.SEND_BATCH_JOB)
        # The second batch's message stays in the broker, as it would: a
        # fresh worker takes it after the kill.
        assert [r["kind"] for r in workers.queue] == [send_batches.SEND_BATCH_JOB]

        # ── the worker: its own process, its own connection — and a SIGKILL ──
        child = subprocess.Popen(
            [sys.executable, "-c", CHILD, batch["id"]],
            cwd=str(BACKEND),
            env=_child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        lines: list[str] = []
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            line = child.stdout.readline()
            if not line:
                break
            lines.append(line.rstrip())
            # The SECOND bill's print: the first bill's savepoint has closed and
            # committed, the second's is still open inside `issue_run` — so the
            # kill lands with one bill out and one half-issued.
            if sum(1 for one in lines if one.startswith("ISSUED")) == 2:
                os.killpg(child.pid, signal.SIGKILL)
                break
        child.wait(timeout=30)
        assert child.returncode == -signal.SIGKILL, (child.returncode, lines[-20:])
        issued_at_kill = _issued(brazos, drafts)
        with tenant_ctx(brazos):
            stuck = core_jobs.current(batch["id"])
        print(
            f"\nPROOF 8710 kill: child={child.returncode} issued_at_kill={issued_at_kill} "
            f"batch={stuck['status']} {stuck['progress']}"
        )
        assert 1 <= issued_at_kill < 3, issued_at_kill  # part-way through ONE batch
        assert stuck["status"] == core_jobs.RUNNING  # a SIGKILL writes nothing

        # ── a fresh worker takes what was waiting in the broker ───────────────
        workers.run(workers.queue.pop(0))
        issued_before_hand_back = _issued(brazos, drafts)
        assert issued_before_hand_back == issued_at_kill + 3

        # ── the Send screen's poll hands it back (the workers say nobody has it) ──
        settings.BILLING_JOB_STOPPED_FLOOR_SECONDS = 0
        probe = core_jobs._liveness_probe  # noqa: SLF001
        ready = core_jobs._dispatch_probe  # noqa: SLF001
        core_jobs.set_liveness_probe(lambda job_id: False)
        # The played workers ARE the billing queue's consumer here; without
        # this the probe asks a real broker, finds none, and the hand-back is
        # (rightly) refused with "no worker".
        core_jobs.set_dispatch_probe(lambda queue=None: (True, "the test's workers"))
        try:
            with django_capture_on_commit_callbacks(execute=True):
                polled = api_call(
                    billing_api.run_issue_progress,
                    "get",
                    user=clerk,
                    role="billing_clerk",
                    tenant=brazos,
                    query={"job": coordinator["id"]},
                    run_id=str(run.pk),
                )
            assert polled.status_code == 200, polled.data
            assert polled.data["job"]["resumed"] is True, polled.data
            # The resumed coordinator, in a worker that can ALSO see nobody is
            # on the killed batch (in production its own probe asks Celery),
            # takes that batch back and re-dispatches it.
            workers.run(workers.take(run_jobs.ISSUE_JOB))
            with tenant_ctx(brazos):
                resumed = core_jobs.current(coordinator["id"])
            print(
                f"PROOF 8710 progress at hand-back: {resumed['progress']} "
                f"(issued at kill {issued_at_kill}, before the hand-back {issued_before_hand_back})"
            )
            # Counted from the bills, so it reads where the Send is — never 0.
            assert resumed["progress"] == {"done": issued_before_hand_back, "total": 6}
            workers.drain()
        finally:
            core_jobs.set_liveness_probe(probe)
            core_jobs.set_dispatch_probe(ready)
    finally:
        core_jobs.set_job_dispatcher(previous)

    with tenant_ctx(brazos):
        done = core_jobs.current(coordinator["id"])
        bills = list(billing_models.Invoice.objects.filter(pk__in=drafts))
        entries = [
            ledger_models.JournalEntry.objects.filter(source_type="invoice", source_id=pk).count()
            for pk in drafts
        ]
        audits = [
            audit_models.AuditLog.objects.filter(action="invoice.issued", entity_id=pk).count()
            for pk in drafts
        ]
        release_audits = audit_models.AuditLog.objects.filter(
            action="bill_run.released", entity_id=run.pk
        ).count()
        released = billing_models.BillRunRelease.objects.get(bill_run=run)
        numbers_used = list(
            billing_models.Invoice.objects.filter(tenant=brazos)
            .exclude(invoice_no__isnull=True)
            .values_list("invoice_no", flat=True)
        )
    print(
        f"PROOF 8710 after: job={done['status']} {done['progress']} statuses="
        f"{sorted({b.status for b in bills})} entries={entries} issue_audits={audits} "
        f"release_audits={release_audits} released_at={released.released_at}"
    )
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert {b.status for b in bills} == {billing_models.INVOICE_ISSUED}
    assert {str(b.pk): b.invoice_no for b in bills} == {
        str(k): v for k, v in numbers_before.items()
    }
    assert len(numbers_used) == len(set(numbers_used))  # no number used twice
    assert entries == [1] * 6
    assert audits == [1] * 6
    assert release_audits == 1
    assert released.released_at == SENT_AT
