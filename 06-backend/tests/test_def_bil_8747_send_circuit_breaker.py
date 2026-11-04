# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-040 (bulk run · Send) · US-BIL-005 (issue)
# Defects:  DEF-BIL-8747 (a fault of the DEPLOYMENT — code one migration ahead
#           of its database — broke 22,640 bills one by one, filed each as
#           *not sent*, and the release still completed)
# Pattern:  tests/test_def_bil_8726_send_batches.py (the played worker)
# Rules:    CLAUDE.md hard rules 4, 6 and 7 · BR-BIL-055 (a break never blocks
#           the run) · hard-won law 14 (proved on PostgreSQL too: run this file
#           under config.settings.local)
# ───────────────────────────────────────────────────────
"""The Send's circuit breaker: the same unexpected fault on bill after bill
STOPS the Send; one bad bill does not.

Written BEFORE the breaker, red first (r11 step 2c). One case per promise:

1. **A fault of the system stops the Send.** Every bill fails with the same
   database error (a real failing statement — a column that is not there —
   so on PostgreSQL the per-bill savepoint is exercised for real). The Send
   stops after `send_batches.SAME_FAULT_LIMIT` bills in a row: the coordinator
   is FAILED with a named stop the Send screen reads, the release is NOT
   completed, no bill is filed *not sent*, and no bill past the stop is even
   attempted.
2. **Once the fault clears, Send carries on and sends each bill exactly once**
   — one `invoice.issued` audit row and one journal entry each, every number
   its draft's, the release completed once.
3. **One bad bill is still a break and the Send goes on** (BR-BIL-055): it is
   filed *not sent* and the release completes.
4. **A run of failures shorter than the limit, broken by a bill that issues,
   does not stop the Send** — the streak resets.
5. **A genuine break before the stop is still filed**; only the bills of the
   streak itself are left unfiled.
6. **The screen's read carries the stop** (`GET …/issue/progress` → `stopped`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import connection, transaction
from django.test import override_settings

from apps.billing import issue, run_jobs, send_batches
from apps.billing import models as billing_models
from core import jobs as core_jobs

from tests.test_def_bil_8726_send_batches import (  # noqa: F401 — fixtures
    a_signed_off_run,
    batch_of,
    job,
    press_send,
    what_went_out,
    workers,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SENT_AT = datetime(2026, 10, 1, 9, 45, tzinfo=UTC)


def _the_missing_column() -> None:
    """What `sbh_send40k` did on every bill: a statement naming a column the
    database does not have. A REAL failing statement, not a raised stand-in,
    so on PostgreSQL it aborts the transaction it runs in (law 14)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pricing_trace_8747 FROM invoice_lines LIMIT 1")


def _break_bills(monkeypatch, *, which=lambda n, draft: True, fault=_the_missing_column):
    """Patch `issue_invoice` so the bills `which(n, draft)` picks fail with
    `fault()`; the rest issue for real. Answers the call counter."""
    real = issue.issue_invoice
    calls = {"n": 0, "attempted": []}

    def patched(draft, *args, **kwargs):
        calls["n"] += 1
        calls["attempted"].append(str(draft.pk))
        if which(calls["n"], draft):
            fault()
        return real(draft, *args, **kwargs)

    monkeypatch.setattr(issue, "issue_invoice", patched)
    return calls, real


@pytest.fixture()
def a_worker_is_ready():
    """The billing queue answers (the played `workers` consume it). Without
    this `config.settings.local` asks a real broker, finds none, and Send runs
    inline and Resume is refused — right for a box with no worker, and not the
    case under test. As `test_def_bil_8710_send_resume_pg.py` does."""
    ready = core_jobs._dispatch_probe  # noqa: SLF001
    core_jobs.set_dispatch_probe(lambda queue=None: (True, "the test's workers"))
    try:
        yield
    finally:
        core_jobs.set_dispatch_probe(ready)


def drain_through_the_stop(workers) -> int:
    """Run every queued record as a worker would. A batch that STOPS the Send
    raises (`core.jobs.run_job` fails the record and re-raises, as it does for
    any body), and a worker moves on to its next message."""
    stops = 0
    while workers.queue:
        try:
            workers.run(workers.queue.pop(0))
        except issue.IssuePassStopped:
            stops += 1
    return stops


def _send_breaks(brazos, run):
    with tenant_ctx(brazos):
        return list(
            billing_models.BillRunBreak.objects.filter(
                bill_run=run, stage=billing_models.BREAK_STAGE_SEND, resolution__isnull=True
            ).values_list("account_id", "reason")
        )


def _drafts_left(brazos, drafts):
    with tenant_ctx(brazos):
        return billing_models.Invoice.objects.filter(
            pk__in=drafts, status=billing_models.INVOICE_DRAFT
        ).count()


# ═══════════════════════════════════════════════════════════════════════════
# 1 + 2 · a fault of the system stops the Send; once fixed, Send sends once
# ═══════════════════════════════════════════════════════════════════════════
def test_8747_1__the_same_fault_on_bill_after_bill_stops_the_send(
    audit_rows,
    brazos,
    dana,
    workers,
    batch_of,
    monkeypatch,
    django_capture_on_commit_callbacks,
    a_worker_is_ready,
):
    """RED before: every bill was filed as a send break and the release was
    completed with every bill still a draft (22,640 of them on sbh_send40k)."""
    from apps.billing import api as billing_api
    from tests.test_us_bil_001_003_run_api import an_actor_user
    from tests.test_us_ten_helpers import api_call

    monkeypatch.setattr(send_batches, "SAME_FAULT_LIMIT", 3)
    batch_of(4)
    run, drafts = a_signed_off_run(brazos, dana, 7, "2026-06|8747-stop")
    with tenant_ctx(brazos):
        numbers_before = sorted(
            billing_models.Invoice.objects.filter(pk__in=drafts).values_list(
                "invoice_no", flat=True
            )
        )
    calls, real = _break_bills(monkeypatch)
    coordinator = press_send(brazos, run)
    with override_settings(BILLING_SEND_BATCHES_PER_UTILITY=1):
        assert drain_through_the_stop(workers) == 1
    stopped = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    print(f"\nPROOF 8747 stop: job={stopped['status']} attempted={calls['n']} {out}")
    assert stopped["status"] == core_jobs.FAILED, stopped
    assert stopped["checkpoint"]["stopped"]["code"] == send_batches.STOP_SAME_FAULT
    assert stopped["checkpoint"]["stopped"]["bills"] == 3
    # Stopped AT the limit: the fourth bill of the batch, and every bill of
    # the batch not yet dispatched, was never attempted.
    assert calls["n"] == 3
    assert _drafts_left(brazos, drafts) == 7
    assert _send_breaks(brazos, run) == []  # nobody told *not sent*
    assert out["released_at"] is None  # the release is NOT completed
    assert out["release_audits"] == 0
    assert out["issue_audits"] == [0] * 7

    # 6 · the Send screen's own read names the stop.
    with tenant_ctx(brazos):
        clerk = an_actor_user(brazos)
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
    assert polled.data["job"]["status"] == core_jobs.FAILED
    assert polled.data["job"]["stopped"]["message_key"] == "billing.bulkRun.send.stoppedSameFault"
    assert polled.data["job"]["stopped"]["code"] == send_batches.STOP_SAME_FAULT

    # 2 · the fault is fixed; Send is pressed again and every bill goes ONCE.
    monkeypatch.setattr(issue, "issue_invoice", real)
    with django_capture_on_commit_callbacks(execute=True):
        pressed = api_call(
            billing_api.run_issue,
            "post",
            user=clerk,
            role="billing_clerk",
            tenant=brazos,
            data={"issued_at": SENT_AT.isoformat(), "background": True},
            run_id=str(run.pk),
        )
    assert pressed.status_code == 202, pressed.data
    workers.drain()
    done = job(brazos, pressed.data["job_id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    print(f"PROOF 8747 after the fix: job={done['status']} {done['progress']} {out}")
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["numbers"] == numbers_before
    assert len(set(out["numbers"])) == 7
    assert out["entries"] == [1] * 7
    assert out["issue_audits"] == [1] * 7
    assert out["release_audits"] == 1
    assert _send_breaks(brazos, run) == []


def test_8747_2__a_stopped_send_resumed_through_its_own_record_carries_on(
    audit_rows,
    brazos,
    dana,
    workers,
    batch_of,
    monkeypatch,
    django_capture_on_commit_callbacks,
    a_worker_is_ready,
):
    """The other door back: `run_jobs.resume_job` on the stopped coordinator
    (failed → queued, checkpoint kept) re-dispatches the failed batch and the
    ones never dispatched, and the stop is cleared from its checkpoint."""
    monkeypatch.setattr(send_batches, "SAME_FAULT_LIMIT", 2)
    batch_of(3)
    run, drafts = a_signed_off_run(brazos, dana, 5, "2026-06|8747-resume")
    _calls, real = _break_bills(monkeypatch)
    coordinator = press_send(brazos, run)
    with override_settings(BILLING_SEND_BATCHES_PER_UTILITY=1):
        assert drain_through_the_stop(workers) == 1
    assert job(brazos, coordinator["id"])["status"] == core_jobs.FAILED
    monkeypatch.setattr(issue, "issue_invoice", real)
    with django_capture_on_commit_callbacks(execute=True):
        with tenant_ctx(brazos):
            _record, outcome = run_jobs.resume_job(run, coordinator["id"])
    assert outcome == core_jobs.REDISPATCHED
    workers.drain()
    done = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert "stopped" not in (done.get("checkpoint") or {})
    assert out["statuses"] == [billing_models.INVOICE_ISSUED]
    assert out["entries"] == [1] * 5
    assert out["issue_audits"] == [1] * 5
    assert out["release_audits"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3 · one bad bill is a break, and the Send goes on (BR-BIL-055)
# ═══════════════════════════════════════════════════════════════════════════
def test_8747_3__one_bad_bill_is_filed_not_sent_and_the_send_completes(
    audit_rows, brazos, dana, workers, batch_of, monkeypatch
):
    monkeypatch.setattr(send_batches, "SAME_FAULT_LIMIT", 2)
    batch_of(5)
    run, drafts = a_signed_off_run(brazos, dana, 4, "2026-06|8747-one")
    with tenant_ctx(brazos):
        bad = billing_models.Invoice.objects.filter(pk__in=drafts).order_by("invoice_no").first()
    _break_bills(monkeypatch, which=lambda n, draft: str(draft.pk) == str(bad.pk))
    coordinator = press_send(brazos, run)
    workers.drain()
    done = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert _drafts_left(brazos, drafts) == 1
    assert _send_breaks(brazos, run) == [(bad.account_id, issue.ISSUE_FAILED_UNEXPECTEDLY)]
    assert out["released_at"] == SENT_AT
    assert out["release_audits"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4 · a streak broken by a bill that issues does not stop the Send
# ═══════════════════════════════════════════════════════════════════════════
def test_8747_4__failures_short_of_the_limit_reset_when_a_bill_issues(
    audit_rows, brazos, dana, workers, batch_of, monkeypatch
):
    monkeypatch.setattr(send_batches, "SAME_FAULT_LIMIT", 3)
    batch_of(10)
    run, drafts = a_signed_off_run(brazos, dana, 6, "2026-06|8747-reset")
    # Bills 1, 2 fail; 3 issues; 4, 5 fail; 6 issues — never three in a row.
    _break_bills(monkeypatch, which=lambda n, draft: n in (1, 2, 4, 5))
    coordinator = press_send(brazos, run)
    workers.drain()
    done = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert done["status"] == core_jobs.SUCCEEDED, done
    assert len(_send_breaks(brazos, run)) == 4
    assert _drafts_left(brazos, drafts) == 4
    assert out["release_audits"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5 · a genuine break before the stop is still filed
# ═══════════════════════════════════════════════════════════════════════════
def test_8747_5__a_different_break_before_the_stop_is_still_filed(
    audit_rows, brazos, dana, workers, batch_of, monkeypatch
):
    monkeypatch.setattr(send_batches, "SAME_FAULT_LIMIT", 3)
    batch_of(10)
    run, drafts = a_signed_off_run(brazos, dana, 6, "2026-06|8747-mixed")
    first = {}

    def which(n, draft):
        if n == 1:
            first["account_id"] = draft.account_id
            raise KeyError("a bill-shaped fault on the first bill only")
        return True  # every later bill: the system's fault

    calls, _real = _break_bills(monkeypatch, which=which)
    coordinator = press_send(brazos, run)
    assert drain_through_the_stop(workers) == 1
    stopped = job(brazos, coordinator["id"])
    out = what_went_out(brazos, run, drafts, audit_rows)
    assert stopped["status"] == core_jobs.FAILED, stopped
    assert calls["n"] == 4  # one KeyError, then three of the same fault
    assert _send_breaks(brazos, run) == [(first["account_id"], issue.ISSUE_FAILED_UNEXPECTEDLY)]
    assert out["released_at"] is None


# ═══════════════════════════════════════════════════════════════════════════
# the pieces — the fault's name, and the default issue pass unchanged
# ═══════════════════════════════════════════════════════════════════════════
def test_8747_6__the_fault_is_named_by_its_innermost_cause():
    from django.db import ProgrammingError

    class UndefinedColumn(Exception):
        pass

    try:
        try:
            raise UndefinedColumn("column x does not exist")
        except UndefinedColumn as inner:
            raise ProgrammingError("column x does not exist") from inner
    except ProgrammingError as outer:
        assert issue.fault_signature(outer).endswith("UndefinedColumn")
    assert issue.fault_signature(KeyError("a")) == "builtins.KeyError"


def test_8747_7__the_limit_is_ten():
    """The figure the decision log records — moving it is a decision."""
    assert send_batches.SAME_FAULT_LIMIT == 10


def test_8747_8__an_issue_pass_with_no_limit_never_stops(brazos, dana, monkeypatch):
    """`issue_run`'s default is unchanged: the inline release and every other
    caller still file every failure as a break (B11)."""
    from tests.test_def_bil_5352_run_status_machine import a_releasable_run, authorise
    from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION

    with tenant_ctx(brazos):
        run = a_releasable_run(brazos, dana, accounts=4, key="2026-06|8747-inline")
        authorise(run, dana)
    _break_bills(monkeypatch)
    with tenant_ctx(brazos), transaction.atomic():
        outcome = issue.issue_run(
            run,
            issued_at=SENT_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
    assert len(outcome.broken) == 4
    assert {b.reason for b in outcome.broken} == {issue.ISSUE_FAILED_UNEXPECTEDLY}
