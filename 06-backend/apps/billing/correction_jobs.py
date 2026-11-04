# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10091 — a bulk Fix a bill is too slow for a web request
#           (preview, Send and Approve-and-issue each ~3 minutes on 38 bills;
#           a production web worker is killed at 60 seconds)
# Change:   CR-180-BRC10 (Fix a bill, revamped) · decision log 2026-10-13
#           *FIX A BILL (CR-180-BRC10) RELEASED IN 2.573.0* — bulk runs as a
#           background job with progress on screen; Q5 (bulk approval refused
#           when a figure moved after Send)
# Contract: TD-17 (async = Celery; every job idempotent + resumable) · B12 r1 §3
#           (202 + job_id; the client polls /jobs/{id}) · NFR-3 (paged) · NFR-4
#           (heavy work async, with progress) · NFR-5 (no caps) · NFR-16
# Rules:    BR-BIL-014 · BR-BIL-044 · BR-BIL-047 · BR-BIL-048 · BR-TEN-043
#           (event time is an ARGUMENT — a worker reads no clock) · hard rule 6
# Tests:    06-backend/tests/test_def_bil_10091_bulk_fix_jobs.py
# Impacts:  apps/billing/corrections_api.py (the routes that enqueue these and
#           the result read) · apps/billing/apps.py (registers the bodies) ·
#           apps/billing/correction_items.py (the work itself)
# ───────────────────────────────────────────────────────
"""Bulk Fix a bill in the BACKGROUND — preview, Send, Approve-and-issue.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file carries the IDEMPOTENCY KEYS of
three acts, one of which issues credit notes and bills (a CLAUDE.md 🔒 path).
AI-authored 2026-10-13 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

WHY. On the demo's September run (48 bills, PostgreSQL 16) a bulk preview took
182.7 s, Send 190.8 s and Approve-and-issue about as long, because each re-priced
every bill in the request — and Send and approval re-priced the scope again.
`docker-entrypoint.sh` gives a web worker sixty seconds. At T5 a run is
thousands of bills, so Bulk could not finish at all.

WHAT EACH ACT DOES NOW (one customer is unchanged and stays in the request):

* **preview** — `correction_items.build` under the read memo, bill by bill, with
  progress; the answer is STORED (`CorrectionJob` + `CorrectionJobBill`) and
  served a page at a time by `GET /corrections/jobs/{job_id}` (NFR-3). Paging
  the table no longer prices anything.
* **send** — opens the case FROM the stored preview
  (`correction_items.open_from_preview`). It prices nothing.
* **approve_issue** — prices each re-priced bill ONCE (`figures_moved`, writes
  nothing); a moved figure refuses the approval before it is recorded (Q5);
  otherwise approves and issues every bill on its own (BR-BIL-047), reusing
  the data that check gathered.

IDEMPOTENCY — three layers, as `run_jobs` has them:

1. **The write.** Send's pinned bills carry BR-BIL-048's unique index, so a
   second case over the same bills is refused, not written; the issue loop
   skips a bill already `done` (rule 6) and never approves twice.
2. **The scope key.** A double press while the job is still active is THE SAME
   JOB (`core.jobs.enqueue`'s NFR-16 fold-in): preview by its scope, rows, date
   and clerk; Send by the preview it opens; issue by the case.
3. **The replay check.** A re-delivered task finds its row already answered
   (an answer, a case, a result or a refusal) and does nothing.

NO CLOCK IN A WORKER (BR-TEN-043 · G6). `as_of`, `on_date` and `issued_at` are
the caller's, carried in the row and the payload.

WHAT THE WORKER CARRIES INSTEAD OF A ROLE: an id (`run_jobs._JobActor`). The role
gate ran on the request that enqueued — `SystemAdminOnly` on approve-and-issue.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from apps.billing.correction_models import (
    CASE_DONE,
    JOB_ACT_ISSUE,
    JOB_ACT_PREVIEW,
    JOB_ACT_SEND,
    SCOPE_ACCOUNT,
    SCOPE_SINGLE,
    CorrectionCase,
    CorrectionCaseBill,
    CorrectionJob,
    CorrectionJobBill,
)
from apps.billing.exceptions import BillingConfigError, BillingRuleError
from core import audit
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

PREVIEW_JOB = "billing.correction.preview"
SEND_JOB = "billing.correction.send"
ISSUE_JOB = "billing.correction.approve_issue"
CORRECTION_JOBS = (PREVIEW_JOB, SEND_JOB, ISSUE_JOB)

#: The progress stages a screen names (`"Checking 38 bills · 12 done"`).
STAGE_PRICING = "pricing"
STAGE_CHECKING = "checking"
STAGE_SENDING = "sending"
STAGE_ISSUING = "issuing"

#: The refusal a clerk reads when nothing would run the job (DEF-2487, law 3).
KEY_NO_WORKER = "billing.correction.noWorker"
#: …and when a Send names a preview that is not there or not finished.
KEY_PREVIEW_GONE = "billing.correction.previewGone"

#: The page a stored preview is served in when the caller names none.
DEFAULT_PER = 50


def is_bulk(scope_kind: str) -> bool:
    """Bulk runs in the background; One customer stays in the request."""
    return str(scope_kind or "") not in (SCOPE_ACCOUNT, SCOPE_SINGLE)


def scope_kind_of(scope: Any) -> str:
    if not isinstance(scope, dict):
        return ""
    return str(scope.get("kind") or scope.get("scope_kind") or "")


# ── small helpers ──────────────────────────────────────────────────────────
def _json(value: Any) -> Any:
    """JSON-safe, the way the wire would render it (Decimal → string)."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _digest(*parts: Any) -> str:
    text = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


class _JobActor:
    """An id and no role (`run_jobs._JobActor`'s reasoning, verbatim in intent)."""

    __slots__ = ("id", "pk")

    def __init__(self, user_id: Any) -> None:
        self.id = user_id
        self.pk = user_id


def _actor_of(record: dict[str, Any]) -> _JobActor | None:
    user_id = (record.get("payload") or {}).get("actor_user_id")
    return None if user_id is None else _JobActor(user_id)


def _row_of(record: dict[str, Any]) -> CorrectionJob:
    payload = record.get("payload") or {}
    return CorrectionJob.objects.get(
        tenant_id=core_tenancy.current_tenant_id(), pk=payload["correction_job_id"]
    )


def _reporter(job_id: Any, stage: str) -> Any:
    """`on_bill(done, total)` → `core.jobs.record_progress`, about 200 writes
    a pass at most, and always the last bill (a finished pass never reads
    "37 of 38")."""

    def report(done: int, total: int) -> None:
        step = max(1, total // 200)
        if done % step and done != total:
            return
        core_jobs.record_progress(job_id, done=done, total=total, stage=stage)

    return report


def _refused(row: CorrectionJob, refusal: Exception) -> None:
    """A refusal is the act's ANSWER: kept on the row by `message_key`, the job
    itself succeeds. `detail` is for the log and the support cycle."""
    key = getattr(refusal, "message_key", None) or "billing.correction.refused"
    row.refusal = _json(
        {
            "message_key": key,
            "params": getattr(refusal, "params", None) or {},
            "br_ref": getattr(refusal, "br_ref", None),
            "detail": str(refusal),
        }
    )
    row.save(update_fields=["refusal", "updated_at"])


def _no_worker_refusal() -> None:
    """Never queue into a void (DEF-2487). A deployment running jobs EAGERLY
    always answers ready; production with no billing worker refuses."""
    from apps.billing import run_jobs

    ready, reason = run_jobs.would_run()
    if not ready:
        logger.warning("bulk Fix a bill refused: nothing would run it (%s)", reason)
        raise BillingRuleError(
            "background work is not running on this deployment, so a bulk correction "
            "cannot start. Nothing has been written.",
            br_ref="BR-BIL-051",
            message_key=KEY_NO_WORKER,
        )


def _enqueue(kind: str, row: CorrectionJob, *, scope_key: str, extra: dict[str, Any]):
    record = core_jobs.enqueue(
        kind,
        payload={"correction_job_id": str(row.pk), **extra},
        scope_key=scope_key,
        dispatch=False,
    )
    row.job_id = record["id"]
    row.save(update_fields=["job_id", "updated_at"])
    core_jobs.dispatch(record)
    return core_jobs.current(record["id"])


def _folded(kind: str, scope_key: str) -> tuple[dict[str, Any], CorrectionJob] | None:
    """A double press while the job is still active: the SAME job (NFR-16)."""
    existing = core_jobs.find_active(kind, scope_key)
    if existing is None:
        return None
    row = CorrectionJob.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), job_id=existing["id"]
    ).first()
    return None if row is None else (existing, row)


# ═══════════════════════════════════════════════════════════════════════════
# PREVIEW
# ═══════════════════════════════════════════════════════════════════════════
def start_preview(
    scope: dict[str, Any], raw_items: Any, *, as_of: date, actor: Any
) -> tuple[dict[str, Any], CorrectionJob]:
    """Enqueue a bulk preview. **Prices nothing in the request.**"""
    actor_id = audit.actor_user_id(actor)
    key = f"billing:correction:preview:{_digest(scope, raw_items, as_of.isoformat(), actor_id)}"
    folded = _folded(PREVIEW_JOB, key)
    if folded is not None:
        return folded
    _no_worker_refusal()
    tenant_id = core_tenancy.current_tenant_id()
    row = CorrectionJob.objects.create(
        tenant_id=tenant_id,
        act=JOB_ACT_PREVIEW,
        scope=_json(scope or {}),
        items=_json(raw_items if isinstance(raw_items, list) else []),
        as_of=as_of,
        created_by_id=actor_id,
    )
    _forget_old_previews(tenant_id, actor_id, keep=row.pk)
    record = _enqueue(
        PREVIEW_JOB,
        row,
        scope_key=key,
        extra={"actor_user_id": None if actor_id is None else str(actor_id)},
    )
    return record, row


def _forget_old_previews(tenant_id: Any, actor_id: Any, *, keep: Any) -> None:
    """A clerk's earlier previews that were never sent lose their per-bill
    rows when they start a new one. Each edit of a row is a new preview, so
    without this a 40,000-bill run would leave 40,000 rows per keystroke. A
    preview a Send opened from is kept whole: it is the case's evidence."""
    stale = CorrectionJob.objects.filter(
        tenant_id=tenant_id, act=JOB_ACT_PREVIEW, created_by_id=actor_id
    ).exclude(pk=keep)
    sent_from = CorrectionJob.objects.filter(
        tenant_id=tenant_id, act=JOB_ACT_SEND, source__isnull=False
    ).values("source_id")
    CorrectionJobBill.objects.filter(
        tenant_id=tenant_id, job__in=stale.exclude(pk__in=sent_from)
    ).delete()


def run_preview_job(record: dict[str, Any]) -> str | None:
    from apps.billing import correction_items

    row = _row_of(record)
    if row.answer is not None or row.refusal is not None:
        return None  # a replay: this preview is already answered
    actor = _actor_of(record)
    try:
        built = correction_items.build(
            row.scope,
            row.items,
            as_of=row.as_of,
            on_bill=_reporter(record["id"], STAGE_PRICING),
        )
        answer = correction_items.answer_for(built, actor=actor)
    except (BillingRuleError, BillingConfigError) as refusal:
        _refused(row, refusal)
        return None
    bills = answer.pop("bills")
    seq = {str(impact["invoice_id"]): n for n, impact in enumerate(built.impacts)}
    impacts = {str(impact["invoice_id"]): impact for impact in built.impacts}
    with transaction.atomic():
        CorrectionJobBill.objects.bulk_create(
            [
                CorrectionJobBill(
                    tenant_id=row.tenant_id,
                    job=row,
                    position=position,
                    seq=seq[str(bill["invoice_id"])],
                    invoice_id=bill["invoice_id"],
                    row=_json(bill),
                    impact=_json(impacts[str(bill["invoice_id"])]),
                )
                for position, bill in enumerate(bills)
            ],
            batch_size=500,
        )
        row.answer = _json(answer)
        row.built = _json(correction_items.built_record(built))
        row.preview_hash = built.preview_hash
        row.save(update_fields=["answer", "built", "preview_hash", "updated_at"])
    return None


# ═══════════════════════════════════════════════════════════════════════════
# SEND
# ═══════════════════════════════════════════════════════════════════════════
def preview_row(job_id: Any) -> CorrectionJob | None:
    """This tenant's background PREVIEW for `job_id`, or None."""
    if not job_id:
        return None
    try:
        return CorrectionJob.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), job_id=job_id, act=JOB_ACT_PREVIEW
        ).first()
    except (ValueError, TypeError):
        return None
    except Exception:  # noqa: BLE001 — a malformed uuid on PostgreSQL
        return None


def start_send(
    preview_job_id: Any, *, preview_hash: str, actor: Any
) -> tuple[dict[str, Any], CorrectionJob]:
    """Enqueue a bulk Send from a finished background preview."""
    from apps.billing import correction_items

    source = preview_row(preview_job_id)
    if source is None or source.answer is None:
        raise BillingRuleError(
            "the preview this Send names is not there or has not finished",
            br_ref="BR-BIL-044",
            message_key=KEY_PREVIEW_GONE,
        )
    if not preview_hash or preview_hash != source.preview_hash:
        raise correction_items._refuse(
            correction_items.KEY_FIGURES_MOVED,
            "the figures changed since they were checked",
            br_ref="BR-BIL-044",
        )
    # A Send already made from this preview answers with ITS job: a second
    # press after the first finished is the same Send, not a second case.
    done = (
        CorrectionJob.objects.filter(
            tenant_id=source.tenant_id, act=JOB_ACT_SEND, source=source, case__isnull=False
        )
        .order_by("-created_at")
        .first()
    )
    if done is not None and done.job_id is not None:
        return core_jobs.current(str(done.job_id)), done
    key = f"billing:correction:send:{source.pk}"
    folded = _folded(SEND_JOB, key)
    if folded is not None:
        return folded
    _no_worker_refusal()
    actor_id = audit.actor_user_id(actor)
    row = CorrectionJob.objects.create(
        tenant_id=source.tenant_id,
        act=JOB_ACT_SEND,
        scope=source.scope,
        items=source.items,
        as_of=source.as_of,
        preview_hash=preview_hash,
        source=source,
        created_by_id=actor_id,
    )
    record = _enqueue(
        SEND_JOB,
        row,
        scope_key=key,
        extra={"actor_user_id": None if actor_id is None else str(actor_id)},
    )
    return record, row


def run_send_job(record: dict[str, Any]) -> str | None:
    from apps.billing import correction_items

    row = _row_of(record)
    if row.case_id is not None or row.refusal is not None:
        return None  # a replay: this Send already opened its case (or was refused)
    total = row.source.bills.count() if row.source_id else 0
    core_jobs.record_progress(record["id"], done=0, total=total, stage=STAGE_SENDING)
    try:
        case = correction_items.open_from_preview(
            row.source, preview_hash=row.preview_hash or "", actor=_actor_of(record)
        )
    except BillingRuleError as refusal:
        _refused(row, refusal)
        return None
    row.case = case
    row.save(update_fields=["case", "updated_at"])
    core_jobs.record_progress(record["id"], done=total, total=total, stage=STAGE_SENDING)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# APPROVE AND ISSUE (and Try again)
# ═══════════════════════════════════════════════════════════════════════════
def start_issue(
    case: CorrectionCase,
    *,
    preview_hash: str | None,
    on_date: date,
    issued_at: datetime,
    template_id: Any,
    template_version: int | None,
    actor: Any,
    resume: bool = False,
) -> tuple[dict[str, Any], CorrectionJob]:
    """Enqueue a bulk Approve-and-issue (or, `resume`, a Try again that runs
    the bills not yet done). The hash is checked HERE, before anything is
    queued, exactly as the one-request route checked it."""
    from apps.billing import correction_items

    if not resume and preview_hash != case.preview_hash:
        raise correction_items._refuse(
            correction_items.KEY_FIGURES_MOVED,
            "the figures changed since they were checked",
            br_ref="BR-BIL-044",
        )
    key = f"billing:correction:issue:{case.pk}"
    folded = _folded(ISSUE_JOB, key)
    if folded is not None:
        return folded
    _no_worker_refusal()
    actor_id = audit.actor_user_id(actor)
    row = CorrectionJob.objects.create(
        tenant_id=case.tenant_id,
        act=JOB_ACT_ISSUE,
        scope=case.scope or {},
        preview_hash=case.preview_hash,
        case=case,
        created_by_id=actor_id,
    )
    record = _enqueue(
        ISSUE_JOB,
        row,
        scope_key=key,
        extra={
            "actor_user_id": None if actor_id is None else str(actor_id),
            "on_date": on_date.isoformat(),
            "issued_at": issued_at.isoformat(),
            "template_id": None if template_id is None else str(template_id),
            "template_version": template_version,
            "resume": bool(resume),
        },
    )
    return record, row


def run_issue_job(record: dict[str, Any]) -> str | None:
    from apps.billing import bulk_corrections, correction_items

    row = _row_of(record)
    if row.result is not None or row.refusal is not None:
        return None  # a replay: this act already has its answer
    case = CorrectionCase.objects.get(tenant_id=row.tenant_id, pk=row.case_id)
    if case.status == CASE_DONE:
        return None
    payload = record.get("payload") or {}
    actor = _actor_of(record)
    on_date = date.fromisoformat(str(payload["on_date"]))
    issued_at = datetime.fromisoformat(str(payload["issued_at"]).replace("Z", "+00:00"))
    template_id = payload.get("template_id")
    template_version = payload.get("template_version")
    try:
        if payload.get("resume"):
            result = bulk_corrections.execute(
                case,
                issued_at=issued_at,
                on_date=on_date,
                template_id=template_id,
                template_version=template_version,
                actor=actor,
                on_bill=_reporter(record["id"], STAGE_ISSUING),
            )
        else:
            result = correction_items.approve_and_issue(
                case,
                approver=actor,
                preview_hash=row.preview_hash or "",
                on_date=on_date,
                issued_at=issued_at,
                template_id=template_id,
                template_version=template_version,
                on_check=_reporter(record["id"], STAGE_CHECKING),
                on_issue=_reporter(record["id"], STAGE_ISSUING),
            )
    except BillingRuleError as refusal:
        _refused(row, refusal)
        return None
    row.result = _json(result_of(result))
    row.save(update_fields=["result", "updated_at"])
    return None


def result_of(result: Any) -> dict[str, Any]:
    """`/execute`'s per-bill answer — the same shape the one-request route
    served, so the screen reads one result whichever way it was issued."""
    return {
        "case_id": result.case_id,
        "status": result.status,
        "succeeded": list(result.succeeded),
        "failed": [
            {"invoice_id": invoice_id, "reason": reason} for invoice_id, reason in result.failed
        ],
        "skipped_already_done": list(result.skipped_already_done),
        "summary": result.summary(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE RESULT READ — GET /corrections/jobs/{job_id}
# ═══════════════════════════════════════════════════════════════════════════
def job_row(job_id: Any) -> CorrectionJob | None:
    try:
        return CorrectionJob.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), job_id=job_id
        ).first()
    except Exception:  # noqa: BLE001 — a malformed id is a 404, not a 500
        return None


def preview_page(row: CorrectionJob, *, page: int, per: int) -> dict[str, Any] | None:
    """A stored preview, one page of its bills (NFR-3). Totals cover all."""
    if row.answer is None:
        return None
    start = (page - 1) * per
    bills = list(
        CorrectionJobBill.objects.filter(tenant_id=row.tenant_id, job=row)
        .order_by("position")
        .values_list("row", flat=True)[start : start + per]
    )
    return {**row.answer, "bills": bills, "page": page, "per": per}


def job_state(row: CorrectionJob) -> dict[str, Any]:
    """The `jobs` record's status and progress, as the poll serves them."""
    if row.job_id is None:
        return {"status": core_jobs.QUEUED, "progress": None, "error": None}
    record = core_jobs.current(str(row.job_id))
    return {
        "status": record["status"],
        "progress": record.get("progress"),
        "error": record.get("error"),
    }


def case_bill_count(case: CorrectionCase) -> int:
    return CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case).count()


def register() -> None:
    """Register the three bodies on billing's own queue (`run_jobs.BILLING_QUEUE`
    — a queue with no consumer would leave them `queued` for ever, which is
    what `G59` and `would_run` guard)."""
    from apps.billing import run_jobs

    core_jobs.set_job_handler(PREVIEW_JOB, run_preview_job)
    core_jobs.set_job_handler(SEND_JOB, run_send_job)
    core_jobs.set_job_handler(ISSUE_JOB, run_issue_job)
    for kind in CORRECTION_JOBS:
        core_jobs.set_job_queue(kind, run_jobs.BILLING_QUEUE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-10091@2026-10-13 (the defect row · decision log 2026-10-13
#         *FIX A BILL (CR-180-BRC10) RELEASED IN 2.573.0* Q3/Q5 · CR-180-BRC10
#         contract §2–§4 · core/jobs.py's BE-07 contract · run_jobs.py)
# generated: 2026-10-13 by the DEF-BIL-10091 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
