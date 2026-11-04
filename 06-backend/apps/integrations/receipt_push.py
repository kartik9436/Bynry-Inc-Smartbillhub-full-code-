# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — the New World / Logos receipt file for ONE day,
#           built once and placed in the City's SFTP folder.
# Rules:    PO 2026-10-07 — S1 (per utility) · S3 (*one file, one <Receipts>
#           block, built from the same code the API uses … for the whole day —
#           never API pages glued together*) · Q2 (*"(b) Ann Arbor's local day
#           - we need to use date and time setting from Tenant"*) · Q3 (*"(a)
#           send an empty file and alert"*) · Q4 (*"(a) refuse if already
#           sent"*) · Q5 (*"System admin of Utility/tenant"*) · Q7 (*"(a)"* —
#           an unmapped GL line is sent flagged and counted, never guessed) ·
#           PO 2026-09-22 (*"please send receipt even if it is not balance"*)
#           · CLAUDE.md hard rule 6 (idempotency by a unique key) · hard-won
#           law 14 (a SAVEPOINT around the INSERT that may be refused)
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py ·
#           06-backend/tests/test_cr173_newworld_sftp_pg.py (PostgreSQL 16)
# Impacts:  apps/integrations/runbook_ports.py (the runbook's port) ·
#           apps/integrations/file_drop.py (a person's Resend) ·
#           apps/integrations/seams/payments.py (the local-day window)
# ───────────────────────────────────────────────────────
"""ONE day's receipts, as ONE New World file, placed ONCE.

HUMAN-OWNED (🔒 idempotency key — the one-file-per-utility-per-day claim).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-07 under the PO ruling of
2026-08-09; the review-ledger row is in `12-governance/09-human-review-ledger.md`.

WHAT IS IN THE FILE — EXACTLY WHAT THE API WOULD SERVE FOR THAT DAY
-------------------------------------------------------------------
`/partner/v1/receipts` selects `payments_seam.page_queryset(origin=
ORIGIN_ONLINE)` over a window and hands each page to `newworld.emit`. This
module selects with the SAME function, the SAME origin and the SAME order, over
the utility's own day, and hands the rows to the SAME `emit` in batches of
`BATCH` — then renders the receipts it got back ONCE with `newworld.render`.
So each `<ReceiptHeaderLevel>` in the file is byte-identical to its API form, and the file
holds one `<ROOT>` root (it was `<Receipts>` until 2026-10-21, DEF-INT-10304)
however many API pages the day would have been.

⚠ **NEVER API PAGES GLUED TOGETHER.** That is the PO's S3 and the worked figure
they were shown: 1,500 online payments at 1,000 a page is two complete XML
documents; pasted end to end the file carries two declarations and two root
elements and New World rejects the WHOLE file. `render` is called once, over
every receipt, and nowhere in this file are two byte strings concatenated.

THE DAY
-------
The utility's own calendar day, on the zone in its tenancy settings (Q2). The
window is two INSTANTS — local midnight to the next local midnight — so a 9 pm
payment on 5 Oct in Michigan (01:00 UTC on the 6th) is in
`Receipt_20261005.xml`, and a day with a clock change is 23 or 25 hours long
rather than a day that loses or doubles an hour. The file is named for the day
its receipts belong to, never the day it was sent.

AN EMPTY DAY
------------
Sent anyway, as `<ROOT />` — the City's importer then sees that the day
was looked at and held nothing — and the System Admins are alerted (Q3), so a
silent stop in online payments is a message on somebody's screen in the
morning rather than a gap found at month end.

ONCE, AND A RESEND IS A PERSON
------------------------------
`integration_file_delivery`'s partial unique index admits one `sending` or
`sent` row per utility, connection and day (Q4). The claim is INSERTed inside
its own SAVEPOINT and an `IntegrityError` out of it is read as *already sent*:
on PostgreSQL a refused INSERT aborts the whole transaction otherwise, and the
suite runs on SQLite, which cannot show that (hard-won law 14). A RESEND is a
row with `is_resend = True`, outside the index, and only `file_drop.resend`
writes one — a person, a reason, an audit row. Nothing scheduled can.

⚠ **THE UPLOAD IS A SIDE EFFECT INSIDE A DATABASE TRANSACTION, AND THAT HAS
ONE HONEST CONSEQUENCE.** If the file reaches the City and the transaction that
records it then rolls back, the record is lost and the next run sends the day
again. The window is the few statements between the upload returning and the
commit; the opposite order (commit *sent*, then upload) would be worse — a day
marked sent that never arrived, which the guard would then refuse to fix.

WHAT A FAILURE LEAVES BEHIND
----------------------------
`send()` NEVER RAISES for the far end's refusal or for a file it could not
build. Every attempt writes an `integration_run` row (the run history on
Settings → Integrations) and, on failure, alerts the System Admins — and both
must SURVIVE the caller: the runbook engine calls its port inside a SAVEPOINT
and rolls that savepoint back when the port raises, so a port that raised
would erase the very run row and alert that say what went wrong. The port
therefore returns `done: False` and the engine records the act as not done
(`runbooks.engine.acts.act`, the `done` answer).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.integrations import models, newworld, services, sftp
from apps.integrations.adapters.base import ConnectionView
from apps.integrations.adapters.erp_newworld import ErpNewWorldAdapter, is_set_up
from apps.integrations.manifests.erp_newworld import (
    SEND_FILE_GROUP,
    SEND_RECEIPT_FILE,
    SFTP_HOST,
    SFTP_PASSWORD,
    SFTP_PATH,
)
from apps.integrations.seams import notifications as notifications_seam
from apps.integrations.seams import payments as payments_seam
from apps.integrations.seams import tenancy as tenancy_seam

logger = logging.getLogger(__name__)

PROVIDER_KEY = "erp_newworld"
OPERATION = SEND_RECEIPT_FILE

#: Receipts handed to `newworld.emit` at a time — the API's own page size, so
#: the per-batch reads `emit` makes (accounts, journal entries) are exactly the
#: reads one API page makes. It decides MEMORY and QUERY COUNT, never the file:
#: the file is one `render` over every batch (S3).
BATCH = 1000

#: The words a person reads — ≤ 6 per sentence (B14 rule 33).
NOT_CONNECTED_SENTENCE = "New World is not connected."
NOT_SET_UP_SENTENCE = "No City folder set up."
NO_PASSWORD_SENTENCE = "No password saved for the folder."
ALREADY_SENT_SENTENCE = "Already sent for that day."
BUILD_FAILED_SENTENCE = "The file could not be built."
INVALID_SENTENCE = "The file failed its format check."
NO_ZONE_SENTENCE = "The utility time zone is unknown."
SENT_SENTENCE = "Sent to the City folder."

#: Outcome codes a caller branches on. Words travel separately.
CODE_SENT = "sent"
CODE_ALREADY = "already_sent"
CODE_NOT_SET_UP = "not_set_up"
CODE_FAILED = "failed"

#: The phrase the bell reads — never a code (B14 rule 32).
ALERT_OPERATION = "New World receipt file"


def filename_for(day: date) -> str:
    """`Receipt_20261005.xml` — the DATA day, never the run date (PO Q2)."""
    return f"Receipt_{day:%Y%m%d}.xml"


def day_window(day: date, zone: Any) -> tuple[datetime, datetime]:
    """Local midnight → next local midnight, as two UTC instants (from inclusive, before exclusive)."""
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


def default_day(*, now: datetime | None = None, zone: Any = None) -> date | None:
    """Yesterday on the utility's clock — what a nightly run sends."""
    zone = zone if zone is not None else tenancy_seam.timezone()
    if zone is None:
        return None
    moment = (now or timezone.now()).astimezone(zone)
    return moment.date() - timedelta(days=1)


@dataclass
class BuiltFile:
    """The day's file and what is wrong with it, stated."""

    day: date
    filename: str
    payload: bytes
    receipt_count: int
    unbalanced_count: int
    unbalanced_total: Decimal
    unresolved_gl_count: int
    unmapped_tenders: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.receipt_count == 0

    def flags(self) -> list[str]:
        """The counts the PO's *send it flagged* rulings require, in words."""
        out: list[str] = []
        if self.unbalanced_count:
            out.append(f"{self.unbalanced_count} not balanced, by {self.unbalanced_total}")
        if self.unresolved_gl_count:
            out.append(f"{self.unresolved_gl_count} lines with no City GL number")
        for tender in self.unmapped_tenders:
            out.append(f"tender {tender} unmapped")
        return out


def build_file(day: date, *, zone: Any = None) -> BuiltFile:
    """The day's ONE document. Reads only; writes nothing; dials nothing."""
    zone = zone if zone is not None else tenancy_seam.timezone()
    if zone is None:
        raise LookupError(NO_ZONE_SENTENCE)
    start, end = day_window(day, zone)
    queryset = payments_seam.page_queryset(
        origin=payments_seam.ORIGIN_ONLINE,
        posted_from=start,
        posted_before=end,
    ).prefetch_related("allocations__invoice")
    receipts: list[Any] = []
    batch: list[Any] = []
    for row in queryset.iterator(chunk_size=BATCH):
        batch.append(row)
        if len(batch) >= BATCH:
            receipts.extend(newworld.emit(batch).receipts)
            batch = []
    if batch:
        receipts.extend(newworld.emit(batch).receipts)
    # ⚠ ONE RENDER, OVER EVERY RECEIPT (S3). The per-batch `body` bytes that
    # `emit` also produced are DISCARDED, deliberately — they are the API's
    # pages, and gluing them is the failure the PO was shown.
    whole = newworld.Emission(body=newworld.render(receipts), receipts=tuple(receipts))
    # ⚠ CHECKED AGAINST NEW WORLD'S CONFIRMED TEMPLATE BEFORE ANYTHING CAN
    # TOUCH IT (PO 2026-10-21, DEF-INT-10304). `ReceiptFileInvalid` out of here
    # means no `BuiltFile` exists, so nothing downstream — the delivery claim,
    # the upload — can be handed a file that failed.
    newworld.checked(whole.body)
    return BuiltFile(
        day=day,
        filename=filename_for(day),
        payload=whole.body,
        receipt_count=len(whole.receipts),
        unbalanced_count=whole.short_count,
        unbalanced_total=whole.short_total,
        unresolved_gl_count=whole.unresolved_gl_count,
        unmapped_tenders=whole.unmapped_tenders(),
    )


@dataclass
class SendResult:
    """What one attempt did. `done` is the only thing the runbook engine branches on."""

    code: str
    sentence: str
    day: date | None = None
    filename: str = ""
    folder: str = ""
    receipt_count: int = 0
    unbalanced_count: int = 0
    unresolved_gl_count: int = 0
    flags: list[str] = field(default_factory=list)
    run_trace: str = ""
    alerted: bool = False

    @property
    def done(self) -> bool:
        return self.code == CODE_SENT

    def as_dict(self) -> dict[str, Any]:
        return {
            "done": self.done,
            "code": self.code,
            "reason": "" if self.done else self.sentence,
            "sentence": self.sentence,
            "day": self.day.isoformat() if self.day else None,
            "filename": self.filename,
            "folder": self.folder,
            "receipt_count": self.receipt_count,
            "unbalanced_count": self.unbalanced_count,
            "unresolved_gl_count": self.unresolved_gl_count,
            "flags": list(self.flags),
            "trace": self.run_trace,
            "alerted": self.alerted,
        }


def connection() -> models.IntegrationConnection | None:
    """This utility's New World connection — production first (`services.connection_for`)."""
    from core.tenancy import current_tenant_id

    tenant_id = current_tenant_id()
    if tenant_id is None:
        return None
    row = services.connection_for(tenant_id, PROVIDER_KEY)
    if row is None or not row.enabled:
        return None
    return row


def already_sent(conn: models.IntegrationConnection, day: date) -> models.IntegrationFileDelivery | None:
    """The successful non-resend delivery for that day, if there is one. The SENTENCE half only."""
    return (
        models.IntegrationFileDelivery.objects.filter(
            tenant_id=conn.tenant_id,
            connection=conn,
            operation=OPERATION,
            data_day=day,
            status=models.DELIVERY_SENT,
            is_resend=False,
        )
        .order_by("-created_at")
        .first()
    )


def preview(day: date) -> dict[str, Any]:
    """What a DRY run reports: the file it WOULD send, built, counted, uploaded nowhere."""
    conn = connection()
    config = dict(conn.config or {}) if conn is not None else {}
    earlier = already_sent(conn, day) if conn is not None else None
    try:
        built = build_file(day)
    except newworld.ReceiptFileInvalid as exc:
        # The dry run says the file would be REFUSED, and why — never a byte count
        # for a file that would not be sent.
        return {
            "day": day.isoformat(),
            "filename": filename_for(day),
            "folder": str(config.get(SFTP_PATH) or "/"),
            "server": str(config.get(SFTP_HOST) or ""),
            "set_up": conn is not None and is_set_up(config),
            "valid": False,
            "problems": list(exc.problems),
            "flags": [INVALID_SENTENCE],
            "already_sent": earlier is not None,
            "already_sent_at": earlier.finished_at.isoformat() if earlier and earlier.finished_at else None,
        }
    return {
        "valid": True,
        "problems": [],
        "day": day.isoformat(),
        "filename": built.filename,
        "folder": str(config.get(SFTP_PATH) or "/"),
        "server": str(config.get(SFTP_HOST) or ""),
        "set_up": conn is not None and is_set_up(config),
        "receipt_count": built.receipt_count,
        "unbalanced_count": built.unbalanced_count,
        "unresolved_gl_count": built.unresolved_gl_count,
        "flags": built.flags(),
        "bytes": len(built.payload),
        "already_sent": earlier is not None,
        "already_sent_at": earlier.finished_at.isoformat() if earlier and earlier.finished_at else None,
    }


def _alert(*, actor: Any, conn: models.IntegrationConnection, day: date, what: str, key: Any,
           total: int) -> bool:
    """One bell message to the System Admins (Q5). Never raises; returns whether one was queued."""
    answer = notifications_seam.queue_staff_alert(
        actor=actor,
        operation=f"{ALERT_OPERATION} for {day:%d %b %Y}: {what}",
        operation_id=key,
        total_count=max(int(total), 1),
        failed_count=1,
        finished_at=timezone.now(),
    )
    queued = bool(answer.get("message_id"))
    if not queued:
        logger.warning(
            "the New World receipt-file alert for %s was not raised: %s",
            day.isoformat(),
            answer.get("note"),
        )
    return queued


def _finish(
    run: models.IntegrationRun,
    *,
    ok: bool,
    built: BuiltFile | None,
    summary: str,
    failure_sentence: str = "",
    provider_text: str | None = None,
    filename: str = "",
    never_dialled: bool = False,
) -> models.IntegrationRun:
    """Close the run row. The COUNT is receipts; an empty file that could not be
    placed counts as one item — the file — so a failure can never read as success."""
    count = built.receipt_count if built is not None else 0
    if never_dialled:
        return services.finish_run(
            run, attempted=0, succeeded=0, failed=0, skipped=0, confirmed=True,
            never_dialled=True, summary=summary,
        )
    if ok:
        return services.finish_run(
            run, attempted=count, succeeded=count, failed=0, skipped=0, confirmed=True,
            summary=summary,
        )
    failed = max(count, 1)
    return services.finish_run(
        run,
        attempted=failed,
        succeeded=0,
        failed=failed,
        skipped=0,
        confirmed=True,
        summary=summary,
        provider_error=provider_text,
        items=[{"ref": filename, "outcome": "failed", "detail": failure_sentence,
                "provider_text": provider_text}],
    )


def send(
    day: date,
    *,
    trigger: str,
    actor: Any = None,
    started_by_name: str | None = None,
    resend: bool = False,
    reason: str | None = None,
) -> SendResult:
    """Build the day's file and place it in the City's folder — once.

    `trigger` is `manual` or `scheduled`. `resend=True` is `file_drop.resend`'s
    and nobody else's. Never raises for an operational failure; see the module
    docstring for why that is load-bearing.
    """
    conn = connection()
    if conn is None:
        return SendResult(code=CODE_NOT_SET_UP, sentence=NOT_CONNECTED_SENTENCE, day=day)
    config = dict(conn.config or {})
    folder = str(config.get(SFTP_PATH) or "/").strip() or "/"
    filename = filename_for(day)
    if not is_set_up(config):
        # PO S1: a utility that typed no server sends nothing, and is not
        # alerted about a file it never asked for.
        return SendResult(
            code=CODE_NOT_SET_UP, sentence=NOT_SET_UP_SENTENCE, day=day, filename=filename,
            folder=folder,
        )

    run = services.start_run(
        connection=conn,
        operation=OPERATION,
        direction=models.RUN_DIRECTION_OUTBOUND,
        trigger=trigger,
    )
    if started_by_name:
        run.started_by_name = started_by_name
        run.save(update_fields=["started_by_name"])

    if not resend and already_sent(conn, day) is not None:
        closed = _finish(run, ok=False, built=None, never_dialled=True,
                         summary=f"{filename} · {ALREADY_SENT_SENTENCE}")
        return SendResult(code=CODE_ALREADY, sentence=ALREADY_SENT_SENTENCE, day=day,
                          filename=filename, folder=folder, run_trace=closed.trace_id)

    try:
        built = build_file(day)
    except newworld.ReceiptFileInvalid as exc:
        # ⚠ A FILE THAT FAILED THE TEMPLATE CHECK IS NEVER SENT (PO
        # 2026-10-21). No delivery claim is written — the day stays sendable
        # once the fault is fixed — and the run row says what was wrong.
        logger.error("the New World receipt file for %s failed its check: %s",
                     day.isoformat(), exc.problems)
        closed = _finish(run, ok=False, built=None, filename=filename,
                         summary=" · ".join([filename, INVALID_SENTENCE, *exc.problems[:5]]),
                         failure_sentence=INVALID_SENTENCE,
                         provider_text="; ".join(exc.problems[:20]))
        alerted = _alert(actor=actor, conn=conn, day=day, what=INVALID_SENTENCE,
                         key=closed.id, total=0)
        return SendResult(code=CODE_FAILED, sentence=INVALID_SENTENCE, day=day,
                          filename=filename, folder=folder, flags=list(exc.problems),
                          run_trace=closed.trace_id, alerted=alerted)
    except Exception as exc:  # noqa: BLE001 — a build failure is a result, alerted, never a raise
        logger.exception("the New World receipt file for %s could not be built", day.isoformat())
        closed = _finish(run, ok=False, built=None, filename=filename,
                         summary=f"{filename} · {BUILD_FAILED_SENTENCE}",
                         failure_sentence=BUILD_FAILED_SENTENCE,
                         provider_text=type(exc).__name__)
        alerted = _alert(actor=actor, conn=conn, day=day, what=BUILD_FAILED_SENTENCE,
                         key=closed.id, total=0)
        return SendResult(code=CODE_FAILED, sentence=BUILD_FAILED_SENTENCE, day=day,
                          filename=filename, folder=folder, run_trace=closed.trace_id,
                          alerted=alerted)

    # ── the claim — the INSERT is the refusal, inside its own SAVEPOINT ─────
    claim: models.IntegrationFileDelivery | None = None
    try:
        with transaction.atomic():  # ⚠ a SAVEPOINT — hard-won law 14
            claim = models.IntegrationFileDelivery.objects.create(
                tenant_id=conn.tenant_id,
                connection=conn,
                operation=OPERATION,
                data_day=day,
                filename=filename,
                folder=folder,
                status=models.DELIVERY_SENDING,
                is_resend=bool(resend),
                trigger=trigger,
                started_by_name=started_by_name,
                reason=reason,
                receipt_count=built.receipt_count,
                unbalanced_count=built.unbalanced_count,
                unresolved_gl_count=built.unresolved_gl_count,
                byte_count=len(built.payload),
                run_id=run.id,
            )
    except IntegrityError:
        closed = _finish(run, ok=False, built=built, never_dialled=True,
                         summary=f"{filename} · {ALREADY_SENT_SENTENCE}")
        return SendResult(code=CODE_ALREADY, sentence=ALREADY_SENT_SENTENCE, day=day,
                          filename=filename, folder=folder, run_trace=closed.trace_id)

    # ── the upload ──────────────────────────────────────────────────────────
    secrets = services.credential_secrets(conn, slot=SEND_FILE_GROUP)
    failure = ""
    provider_text: str | None = None
    if not secrets.get(SFTP_PASSWORD):
        failure = NO_PASSWORD_SENTENCE
    else:
        view = ConnectionView(provider_key=PROVIDER_KEY, environment=conn.environment,
                              config=config, label=conn.label)
        result = ErpNewWorldAdapter().execute(
            view, secrets, [{"filename": filename, "payload": built.payload}]
        )
        item = result.items[0] if result.items else None
        if item is None or item.outcome != "succeeded":
            failure = (item.detail if item is not None else None) or sftp.UNREACHABLE_SENTENCE
            provider_text = item.provider_text if item is not None else None
    del secrets  # the plaintext lives for one call (BR-INT-003)

    now = timezone.now()
    flags = built.flags()
    head = f"{filename} · {built.receipt_count} receipts · to {folder}"
    if failure:
        models.IntegrationFileDelivery.objects.filter(pk=claim.pk).update(
            status=models.DELIVERY_FAILED, failure=failure, finished_at=now
        )
        closed = _finish(run, ok=False, built=built, filename=filename,
                         summary=" · ".join([head, failure, *flags]),
                         failure_sentence=failure, provider_text=provider_text)
        alerted = _alert(actor=actor, conn=conn, day=day, what=failure, key=claim.pk,
                         total=built.receipt_count)
        return SendResult(code=CODE_FAILED, sentence=failure, day=day, filename=filename,
                          folder=folder, receipt_count=built.receipt_count,
                          unbalanced_count=built.unbalanced_count,
                          unresolved_gl_count=built.unresolved_gl_count, flags=flags,
                          run_trace=closed.trace_id, alerted=alerted)

    models.IntegrationFileDelivery.objects.filter(pk=claim.pk).update(
        status=models.DELIVERY_SENT, finished_at=now
    )
    words = [head]
    if resend:
        words.append("resent")
    if built.empty:
        words.append("no receipts that day")
    closed = _finish(run, ok=True, built=built, summary=" · ".join([*words, *flags]))
    alerted = False
    if built.empty:
        # PO Q3: *"(a) send an empty file and alert"* — both halves.
        alerted = _alert(actor=actor, conn=conn, day=day, what="no online receipts",
                         key=claim.pk, total=0)
    return SendResult(code=CODE_SENT, sentence=SENT_SENTENCE, day=day, filename=filename,
                      folder=folder, receipt_count=built.receipt_count,
                      unbalanced_count=built.unbalanced_count,
                      unresolved_gl_count=built.unresolved_gl_count, flags=flags,
                      run_trace=closed.trace_id, alerted=alerted)


def recent_deliveries(conn: models.IntegrationConnection, *, limit: int = 10) -> list[dict[str, Any]]:
    """The last few files, newest day first — what the panel shows under its form."""
    rows = models.IntegrationFileDelivery.objects.filter(
        tenant_id=conn.tenant_id, connection=conn, operation=OPERATION
    ).order_by("-data_day", "-created_at")[:limit]
    return [
        {
            "day": one.data_day.isoformat(),
            "filename": one.filename,
            "folder": one.folder,
            "status": one.status,
            "is_resend": one.is_resend,
            "receipt_count": one.receipt_count,
            "unbalanced_count": one.unbalanced_count,
            "unresolved_gl_count": one.unresolved_gl_count,
            "failure": one.failure,
            "started_by_name": one.started_by_name,
            "finished_at": one.finished_at,
        }
        for one in rows
    ]
