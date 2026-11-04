# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-047 (an out-of-range reading FLAGS and is never refused) ·
#           US-WRK-049 (the rule column and the file column are different) ·
#           US-WRK-048 (three kinds, the ticket, the four-hour link) ·
#           US-WRK-036 (the signature, or the refusal with its door hanger).
#           Screens: Work-033, Work-012, Work-008
# Rules:    BR-WRK-039 (out of range flags, never refuses) · BR-WRK-040
#           (SUPERSEDED 2026-10-21, PO: *"warn"* — a missing REQUIRED
#           photograph WARNS and is recorded on the close; it no longer
#           stops it) · BR-WRK-046 (signature or refusal) ·
#           BR-WRK-047 (per-image idempotency key; 100 KB at capture) ·
#           BR-WRK-047a (through the application) · BR-WRK-048 (twelve months)
#           · CLAUDE.md hard rule 1 (tenant scope, 404 never 403) · hard rule 3
#           (a reading carries its unit) · hard rule 7 (audit) · law 14 (a
#           SAVEPOINT, and prove it on PostgreSQL)
# Tests:    06-backend/tests/test_us_wrk_047_049_evidence.py ·
#           tests/test_us_wrk_048_evidence_pg.py (PostgreSQL 16)
# Impacts:  apps/work/api.py (#74, #76, #77, #78, #79) · apps/work/checklist.py
#           (the Close readiness the phone reads) · apps/work/evidence_models.py
# ───────────────────────────────────────────────────────
"""What the phone sends back, and the two rules that are always confused.

THE TWO RULES, AND WHY THIS MODULE KEEPS SAYING THEY ARE DIFFERENT
────────────────────────────────────────────────────────────────────────────
`BR-WRK-039` — **an out-of-range reading FLAGS and is NEVER refused.** A
technician reads 1,204 on a dial whose template says 0–999. That number is what
the meter says. Refusing it would leave the true reading unrecorded and the job
uncloseable over a template somebody typed a bound into last year; the value is
stored, `in_range` goes False, and the job can still close.

`BR-WRK-040` — **a missing REQUIRED photograph WARNS and is RECORDED; it no
longer stops the close.** ⚠ **SUPERSEDED 2026-10-21** (PO, verbatim: *"warn"*;
decision log *"Field app: the PO corrects four of the ten answers"* item 3, and
the design's R110). Until then this paragraph read *"STOPS the close. Not a
flag: a stop"*. The close now lands with the gap written on it
(`field_data["photos_missing"]`, `metering.connections._with_photo_gap`) and
the office reads that count on the acceptance queue, where it decides whether
to accept or send the job back.

⚠ **NEITHER BLOCKS NOW, AND THEY ARE STILL TWO DIFFERENT FACTS.** One is a
value that is unusual (the dial said it), the other is EVIDENCE THAT IS ABSENT
(nobody photographed the dial). `close_readiness()` below still returns them in
SEPARATE lists — `missing_photos` and `flagged` — because the office reviewing
a disputed final read asks the second question and not the first, and a screen
that merged them would answer neither.

THE THIRD CONFUSION, AND IT IS A COLUMN RATHER THAN A RULE (`US-WRK-049`)
────────────────────────────────────────────────────────────────────────────
`photo_required` is THE RULE — did the template ask. `photo_attachment_id` is
THE FILE — did anybody take one. Two columns, and collapsing them makes *a
photograph was asked for and not taken* indistinguishable from *no photograph
was ever asked for*, which is precisely the question a supervisor reviewing a
disputed final read is asking. Wave H's model carries both; this module is what
reads them apart.

⚠ **THE UPLOAD GOES THROUGH THE APPLICATION** (`BR-WRK-047a`, decision log
2026-09-05). `POST …/attachments/upload-url` answers with a ticket addressed at
our own `PUT`, not with a pre-signed S3 URL. The blueprint asked for the latter
when a photograph was 250 KB–3 MB; the PO's 100 KB ruling made it a bad trade,
because a direct-to-store PUT means the server never sees the bytes and
therefore cannot hash them, count them, check the tenant, write the audit row or
enforce the ceiling at all. Revisit if the cap ever rises.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.tenancy import document_store
from apps.tenancy.document_models import (
    KIND_WORK_ORDER_PHOTO,
    KIND_WORK_ORDER_SIGNATURE,
    SOURCE_WORK_ORDER,
    SOURCE_WORK_ORDER_ATTACHMENT,
)
from apps.work import models, work_documents
from apps.work.seams import metering_seam

logger = logging.getLogger("smartbillhub.work.evidence")
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.dbfields import uuid7


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _order_or_404(order_id: Any) -> Any:
    """The order, scoped to this tenant, or a 404 — never a 403.

    HR-1: existence must not leak. `US-WRK-048` TC-6 is the case that matters
    here — Lone Star Ridge asking for a Brazos Bend photograph must get the same
    answer as for one that does not exist. A 403 would confirm the job is real.
    Read through the seam because `work_orders` is metering's table
    (`BR-WRK-002`, G78).
    """
    from apps.work.seams import metering_seam

    row = metering_seam.work_order(order_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


# ═══════════════════════════════════════════════════════════════════════════
# THE READING — value AND unit, flagged and never refused
# ═══════════════════════════════════════════════════════════════════════════


def _decimal_or_422(raw: Any, field: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.reading.value_not_a_number",
            br_ref="BR-WRK-039",
            params={field: str(raw)},
        ) from None


def _derive_in_range(value: Decimal, row: Any) -> bool | None:
    """True, False, or None when the template set no bounds.

    ⚠ **NONE IS NOT FALSE.** A reading whose template declared neither a
    minimum nor a maximum has not been checked, and saying `in_range = False`
    about it would put a red *out of range* beside a number nothing ever
    questioned. `Work-033` renders None as no flag at all.
    ⚠ **AND THIS IS SERVER-DERIVED, NEVER TAKEN FROM THE REQUEST.** A phone
    that computed it against a stale copy of the template would be the only
    thing anybody looked at afterwards.
    """
    if row.min_value is None and row.max_value is None:
        return None
    if row.min_value is not None and value < row.min_value:
        return False
    if row.max_value is not None and value > row.max_value:
        return False
    return True


def set_reading(actor: Any, order_id: Any, reading_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PUT /work-orders/{id}/readings/{rid}` — the value, WITH its unit (#74).

    ⚠ **HARD RULE 3 IS THE SHAPE OF THIS FUNCTION: A NUMBER WITHOUT A UNIT IS
    REFUSED.** *Consumption always with an explicit unit; never assume.* The
    prompt on the order already says *Final read (kWh)*, and it would be easy to
    read the unit off the copied row and let the phone send a bare number — that
    is exactly the *"unit hidden in a sentence"* wave H's model docstring warns
    about. The caller states the unit and the server checks it MATCHES the unit
    the job was raised with; a mismatch is refused, because it means the phone
    and the order disagree about what was measured, and wave L is about to post
    this number into a meter's history where a wrong unit is a wrong bill.

    ⚠ **AN OUT-OF-RANGE VALUE IS STORED AND FLAGGED AND NEVER REFUSED**
    (`BR-WRK-039`). This function has exactly one refusal path for the value
    itself — it is not a number — and range is not on it. If you are adding a
    `raise` here for a bound, read the rule first.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)

    row = models.WorkOrderReading.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, id=reading_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")

    # `DEF-WRK-10601` — *Unable to read* first, and for EITHER kind: the phone
    # marks a text reading unable too, with `unit: ""`, and the answer carries
    # no figure, so neither the text path nor hard rule 3's unit check applies.
    if payload.get("unable_to_read") is True:
        return _set_unable_reading(actor, row, payload)
    if row.kind == models.READING_KIND_TEXT:
        return _set_text_reading(actor, row, payload)
    if "value" not in payload:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.reading.value_required",
            br_ref="BR-WRK-039",
        )
    unit = str(payload.get("unit") or "").strip()
    if not unit:
        # Hard rule 3. Refused rather than defaulted from the row: a default
        # would make this endpoint's contract "send a unit or we will guess",
        # and the guess reaches a meter read in wave L.
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.reading.unit_required",
            br_ref="BR-WRK-015",
            params={"expected": row.unit_of_measure},
        )
    if unit != row.unit_of_measure:
        raise errors.ValidationError(
            errors.VAL_UOM_MISMATCH,
            message_key="work.reading.unit_mismatch",
            br_ref="BR-WRK-015",
            params={"sent": unit, "expected": row.unit_of_measure},
        )

    value = _decimal_or_422(payload["value"], "value")
    in_range = _derive_in_range(value, row)

    before = {
        "value": str(row.value) if row.value is not None else None,
        "in_range": row.in_range,
        "unable_to_read": row.unable_to_read,
    }
    with transaction.atomic():
        row.value = value
        row.in_range = in_range
        # A figure is the answer: an earlier *Unable to read* no longer stands.
        row.unable_to_read = False
        row.unable_reason = None
        row.unable_note = None
        row.captured_at = payload.get("captured_at") or timezone.now()
        row.captured_by_id = _actor_id(actor)
        row.save(update_fields=[
            "value", "in_range", "unable_to_read", "unable_reason", "unable_note",
            "captured_at", "captured_by", "updated_at",
        ])

    core_audit.write_row(
        action="work.reading.captured",
        entity_type="work_order_reading",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after={"value": str(value), "unit": unit, "in_range": in_range},
    )
    return _reading_dict(row)


def _set_text_reading(actor: Any, row: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """A reading that is WORDS — `{value_text}` (`CR-168-BRC10` P1.33, J8).

    *W-5000-N* was refused `work.reading.value_not_a_number` because the only
    shape a reading had was a number with a unit. A text reading has neither a
    unit nor a range, so neither is asked for and `in_range` stays None (*not
    checked*, never *out of range*). It is stored in `value_text`; `value` stays
    NULL; and it never posts as a meter read — the copy's `posts_as_meter_read`
    is False for every text reading, so `post_set_reads` never sees it.
    """
    text = str(payload.get("value_text") or "").strip()
    if not text:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.reading.value_required",
            br_ref="BR-WRK-039",
        )
    before = {"value_text": row.value_text, "unable_to_read": row.unable_to_read}
    with transaction.atomic():
        row.value_text = text
        row.unable_to_read = False
        row.unable_reason = None
        row.unable_note = None
        row.captured_at = payload.get("captured_at") or timezone.now()
        row.captured_by_id = _actor_id(actor)
        row.save(update_fields=[
            "value_text", "unable_to_read", "unable_reason", "unable_note",
            "captured_at", "captured_by", "updated_at",
        ])
    core_audit.write_row(
        action="work.reading.captured",
        entity_type="work_order_reading",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after={"value_text": text, "kind": row.kind},
    )
    return _reading_dict(row)


def _set_unable_reading(actor: Any, row: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """*Unable to read* — the technician's answer that there is NO figure
    (`DEF-WRK-10601`; field app R13).

    The phone sends `{reading_id, value: null, unit, unable_to_read: true}` and,
    until this function, the door refused it `work.reading.value_not_a_number`:
    the item stayed on the phone and the office never learned the meter could
    not be read. **It is never refused** — not for its missing figure, not for
    its unit (a text reading sends `""`; there is no consumption to carry one,
    so hard rule 3 has nothing to check), and not for state: the decision log's
    TECHNICIAN SYNC DESIGN of 2026-10-04 drops no field record.

    `value`, `value_text` and `in_range` are cleared (an earlier figure is no
    longer the answer), so the posting path skips the row as *no value
    captured* and no meter read is invented. The office sees *Unable to read*
    either way, and `close_readiness` lists the row under `flagged`.

    ⚠ **THE REASON IS A CODE FROM THE ONE LIST — `DEF-MET-10609`** (decision log
    2026-10-26, PO *"yes do it"*: one can't-read list for route readings AND job
    readings, managed in Settings). The phone sends `unable_reason` (a code of
    metering's `cant_read_reasons`, read through the seam — Work never touches
    that table) and an optional `note`. A code the tenant's ACTIVE list does not
    hold — switched off since, or never on it, or the words an older phone sent
    as `reason` — is **STORED AND FLAGGED, NEVER REFUSED** (TECHNICIAN SYNC
    DESIGN: no field record is dropped): the answer's `unable_reason_known` is
    False and the audit row says so.
    """
    raw = payload.get("unable_reason")
    if raw is None:
        raw = payload.get("reason")
    reason = str(raw).strip() if raw is not None else ""
    reason = reason or None
    note = str(payload.get("note") or "").strip() or None
    index = metering_seam.cant_read_reason_index() if reason else {}
    known = _reason_known(reason, index)
    before = {
        "value": str(row.value) if row.value is not None else None,
        "value_text": row.value_text,
        "unable_to_read": row.unable_to_read,
    }
    with transaction.atomic():
        row.value = None
        row.value_text = None
        row.in_range = None
        row.unable_to_read = True
        row.unable_reason = reason
        row.unable_note = note
        row.captured_at = payload.get("captured_at") or timezone.now()
        row.captured_by_id = _actor_id(actor)
        row.save(update_fields=[
            "value", "value_text", "in_range", "unable_to_read", "unable_reason",
            "unable_note", "captured_at", "captured_by", "updated_at",
        ])
    core_audit.write_row(
        action="work.reading.captured",
        entity_type="work_order_reading",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after={
            "unable_to_read": True,
            "unable_reason": reason,
            "unable_reason_known": known,
            "unable_note": note,
            "kind": row.kind,
        },
    )
    return _reading_dict(row, index)


def _reason_known(reason: str | None, index: dict[str, dict[str, Any]]) -> bool | None:
    """True when the code is on the tenant's ACTIVE list, False when it is not
    (flagged, never refused), None when no reason was given at all."""
    if not reason:
        return None
    entry = index.get(reason.casefold())
    return bool(entry and entry["active"])


def unable_reason_label(reason: str | None, index: dict[str, dict[str, Any]]) -> str | None:
    """What the office reads after *Unable to read ·* — the reason's NAME from
    the one list (switched-off reasons included: an old reading keeps its
    words), or, for a code the list does not hold, what the phone sent."""
    if not reason:
        return None
    entry = index.get(reason.casefold())
    return entry["name"] if entry else reason


def unable_reason_counts(folded_codes: list[str]) -> dict[str, int]:
    """`DEF-MET-10609` — casefolded code → this tenant's job readings answered
    *Unable to read* with it. Metering asks (through `metering/seams.py
    work_unable_reason_counts`) before it deletes a reason: a reason a job
    reading names is USED and is switched off instead."""
    from django.db.models import Count
    from django.db.models.functions import Lower

    if not folded_codes:
        return {}
    rows = (
        models.WorkOrderReading.objects.filter(
            tenant_id=_tenant_id(), unable_to_read=True, unable_reason__isnull=False
        )
        .annotate(folded=Lower("unable_reason"))
        .filter(folded__in=list(folded_codes))
        .values("folded")
        .annotate(n=Count("id"))
    )
    return {row["folded"]: row["n"] for row in rows}


def _reading_dict(row: Any, index: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if index is None:
        index = metering_seam.cant_read_reason_index() if row.unable_reason else {}
    return {
        "id": str(row.id),
        "seq": row.seq,
        "prompt": row.prompt,
        "unit": row.unit_of_measure,
        "kind": row.kind,
        "value_text": row.value_text,
        "value": str(row.value) if row.value is not None else None,
        "in_range": row.in_range,
        # `DEF-WRK-10601` — the answer that there is no figure.
        "unable_to_read": row.unable_to_read,
        "unable_reason": row.unable_reason,
        # `DEF-MET-10609` — the reason's name for the office, whether the code
        # is on the active list (False = flagged), and the technician's note.
        "unable_reason_name": unable_reason_label(row.unable_reason, index),
        "unable_reason_known": _reason_known(row.unable_reason, index),
        "unable_note": row.unable_note,
        "required": row.required,
        # THE RULE and THE FILE, kept apart on the wire too (`US-WRK-049`).
        "photo_required": row.photo_required,
        "photo_attachment_id": str(row.photo_attachment_id) if row.photo_attachment_id else None,
        "captured_at": row.captured_at,
        "posts_as_meter_read": row.posts_as_meter_read,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE PHOTOGRAPH — a ticket, the bytes, the row, and a link that dies
# ═══════════════════════════════════════════════════════════════════════════


def upload_ticket(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/{id}/attachments/upload-url` — where to send it (#76).

    ⚠ **THIS IS NOT A PRE-SIGNED S3 URL AND THAT IS `BR-WRK-047a`.** It answers
    with our own `POST …/attachments` address, the ceiling in bytes, and the
    kind. See the module docstring for the trade: at 100 KB a direct-to-store
    PUT costs the content hash, the byte count, the tenant check, the audit row
    and the ceiling itself, and buys one fewer hop.

    It still EXISTS rather than being deleted from the contract, because the
    phone needs to be told the ceiling by the server rather than carrying it as
    a constant an old build can get wrong — which is the whole failure the PO
    described (*"suggesdenly stroage is not enough"*).
    """
    _order_or_404(order_id)
    kind = str(payload.get("kind") or KIND_WORK_ORDER_PHOTO)
    if kind not in work_documents.UPLOADABLE_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.attachment.kind_not_uploadable",
            br_ref="BR-WRK-047",
            params={"kind": kind, "allowed": ", ".join(work_documents.UPLOADABLE_KINDS)},
        )
    return {
        "upload_url": f"/work-orders/{order_id}/attachments",
        "method": "POST",
        "kind": kind,
        "max_bytes": work_documents.MAX_PHOTO_BYTES,
        "long_edge_px": work_documents.PHOTO_LONG_EDGE_PX,
        # Said in words as well as in numbers because the client author reads
        # this response before they read `BR-WRK-047`.
        "compression": (
            "Compress at capture. Resize the long edge and step quality down until the "
            "bytes fit; the pixel size alone is not enough."
        ),
    }


def _checklist_target(tenant_id: Any, order_id: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
    """Which checklist row this photograph belongs to, verified three ways.

    ⚠ **THE THIRD CHECK IS THE ONE A FOREIGN KEY COULD NOT MAKE.** `reading_id`
    and `task_id` are plain uuids (the B11 F-3 convention wave H's columns
    already use), and the obvious criticism is that an FK would guarantee the
    row exists. It would — and it would NOT guarantee the row belongs to THIS
    ORDER, which is the mistake a phone actually makes: syncing nine jobs and
    attaching job 4's photograph to job 5's reading. That is what is checked
    here, and it is why converting these to foreign keys later would be an
    addition rather than a replacement for this function.
    """
    reading_id = payload.get("reading_id")
    task_id = payload.get("task_id")
    if reading_id and task_id:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.attachment.one_owner_only",
            br_ref="BR-WRK-049",
        )
    if reading_id:
        row = models.WorkOrderReading.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, id=reading_id
        ).first()
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return row, None
    if task_id:
        row = models.WorkOrderTask.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, id=task_id
        ).first()
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        return None, row
    return None, None


def record_attachment(actor: Any, order_id: Any, payload: dict[str, Any], upload: Any) -> dict[str, Any]:
    """`POST /work-orders/{id}/attachments` — the bytes and the row (#77).

    ⚠ **IDEMPOTENT ON `idempotency_key`, AND THE EARLY RETURN IS THE WHOLE
    POINT.** A phone that syncs nine photographs and loses signal halfway
    retries the batch; every photograph it already delivered comes back with the
    key it was minted with, and this returns the existing row rather than
    writing a second. `US-WRK-048` TC-2: re-syncing three jobs adds **zero**
    rows.

    ⚠ **THE DUPLICATE CHECK IS A READ FIRST AND A CONSTRAINT SECOND, AND BOTH
    ARE NEEDED.** The read makes the common case cheap and returns the same
    answer twice; the unique constraint is what holds when two syncs race. The
    `IntegrityError` path re-reads rather than raising, because to the phone a
    lost race and a duplicate are the same event.
    ⚠ **AND IT IS WRAPPED IN A NESTED `transaction.atomic()` — A SAVEPOINT —
    FOR HARD-WON LAW 14's REASON.** On PostgreSQL a failed statement poisons the
    whole transaction: without the savepoint, catching the IntegrityError and
    carrying on would raise `InFailedSqlTransaction` on the very next query and
    lose the batch. **SQLite has no aborted-transaction state, so the version
    without the savepoint passes the entire suite green** — do not "simplify"
    this away; it is proved in `tests/test_us_wrk_048_evidence_pg.py`.

    ⚠ **BYTES BEFORE THE ROW, mirroring `document_store.store()`.** The
    document row cannot be deleted (the write-once trigger), so storing the row
    first and failing the upload would leave a permanent record of a photograph
    that does not exist.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)

    key = str(payload.get("idempotency_key") or "").strip()
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.attachment.key_required",
            br_ref="BR-WRK-047",
        )

    existing = models.WorkOrderAttachment.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, idempotency_key=key
    ).first()
    if existing is not None:
        return _attachment_dict(existing, duplicate=True)

    kind = str(payload.get("kind") or KIND_WORK_ORDER_PHOTO)
    if kind not in work_documents.UPLOADABLE_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.attachment.kind_not_uploadable",
            br_ref="BR-WRK-047",
            params={"kind": kind, "allowed": ", ".join(work_documents.UPLOADABLE_KINDS)},
        )

    reading_row, task_row = _checklist_target(tenant_id, order_id, payload)

    payload_bytes = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
    # DEF-WRK-9641 — SHRINK, NEVER REFUSE, a real image of any size (PO
    # 2026-10-04: "you cannot reject the photo - that will drop the data").
    # Only the shrunk copy is stored; the audit row records both sizes.
    bytes_received = len(payload_bytes)
    try:
        payload_bytes, shrunk_type = work_documents.shrink_photo(payload_bytes)
    except work_documents.NotAnImage as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.attachment.not_an_image",
            br_ref="BR-WRK-047",
        ) from exc
    if len(payload_bytes) != bytes_received:
        payload["content_type"] = shrunk_type

    taken_at = payload.get("taken_at") or timezone.now()

    # ⚠ **THE ATTACHMENT'S ID IS MINTED HERE, BEFORE THE DOCUMENT, AND IT IS
    # THE DOCUMENT'S `source_id`.** A photograph's source is its own attachment
    # row and NOT the work order, because `uq_stored_documents_stored` allows
    # one artefact per (tenant, source_type, source_id, content_type) — so
    # under `SOURCE_WORK_ORDER` the SECOND `image/jpeg` on one job is refused
    # by the database. That constraint is right and is not widened here: its
    # reason is about RENDERINGS of one document (a bill's PDF and its HTML),
    # and nine photographs of a meter cupboard are not nine renderings of a
    # work order. See `tenancy/0040`. The job is still reachable — this table
    # is what says which order a photograph belongs to.
    attachment_id = uuid7()
    ref = document_store.store(
        kind=kind,
        source_type=SOURCE_WORK_ORDER_ATTACHMENT,
        source_id=attachment_id,
        content_type=str(payload.get("content_type") or "image/jpeg"),
        display_name=str(payload.get("display_name") or f"{key}.jpg"),
        payload=payload_bytes,
        actor_user_id=_actor_id(actor),
    )

    try:
        # ⚠ A SAVEPOINT, NOT A CONVENIENCE — hard-won law 14. See the docstring.
        with transaction.atomic():
            row = models.WorkOrderAttachment.objects.create(
                id=attachment_id,
                tenant_id=tenant_id,
                work_order_id=order_id,
                document_id=ref.id,
                kind=kind,
                taken_at=taken_at,
                device=str(payload.get("device") or ""),
                added_by_id=_actor_id(actor),
                reading_id=reading_row.id if reading_row else None,
                task_id=task_row.id if task_row else None,
                idempotency_key=key,
            )
    except Exception as exc:  # noqa: BLE001 — narrowed by the re-read below
        raced = models.WorkOrderAttachment.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, idempotency_key=key
        ).first()
        if raced is None:
            raise
        # Two syncs raced on the same key. To the phone that is the same event
        # as a duplicate, so it gets the same answer.
        del exc
        return _attachment_dict(raced, duplicate=True)

    # THE FILE is written onto the checklist row; THE RULE (`photo_required`)
    # is untouched and stays whatever the template said (`US-WRK-049`).
    if reading_row is not None:
        reading_row.photo_attachment_id = row.id
        reading_row.save(update_fields=["photo_attachment_id", "updated_at"])
    if task_row is not None:
        task_row.photo_attachment_id = row.id
        task_row.save(update_fields=["photo_attachment_id", "updated_at"])

    core_audit.write_row(
        action="work.attachment.recorded",
        entity_type="work_order_attachment",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "work_order_id": str(order_id),
            "kind": kind,
            "document_id": str(ref.id),
            "byte_length": len(payload_bytes),
            # DEF-WRK-9641 — what arrived and what was kept.
            "bytes_received": bytes_received,
            "bytes_stored": len(payload_bytes),
            "idempotency_key": key,
            "reading_id": str(reading_row.id) if reading_row else None,
            "task_id": str(task_row.id) if task_row else None,
        },
    )
    return _attachment_dict(row, duplicate=False)


def _attachment_dict(row: Any, *, duplicate: bool) -> dict[str, Any]:
    """One photograph, as `Work-033`'s `Thumbnail` opens it.

    ⚠ **WHO IS SERVED AS WELL AS WHEN, AND IT WAS NOT (`DEF-WRK-4114`).** The
    row has carried `added_by` since `K1`; only `device` was published, and
    until 2026-10-05 `device` was sent by NOBODY, so a thumbnail opened to a
    timestamp and an empty space. A supervisor questioning a reading needs the
    person before the handset, and the person was already recorded.
    ✅ `device` is filled since `DEF-WRK-4126`: the photograph route takes what
    the request names, else the capture token's handset label, else the
    request's own User-Agent (`mobile.capture_device_label`).
    """
    added_by = getattr(row, "added_by", None)
    return {
        "id": str(row.id),
        "kind": row.kind,
        "taken_at": row.taken_at,
        "device": row.device,
        "added_by_name": (
            (getattr(added_by, "full_name", "") or getattr(added_by, "email", "") or "").strip()
            or None
        )
        if added_by is not None
        else None,
        "reading_id": str(row.reading_id) if row.reading_id else None,
        "task_id": str(row.task_id) if row.task_id else None,
        # So a phone can tell "already had it" from "wrote it", without which a
        # sync cannot report honestly what it did.
        "duplicate": duplicate,
    }


def attachment_link(order_id: Any, attachment_id: Any) -> dict[str, Any]:
    """`GET /work-orders/{id}/attachments/{aid}` — a link that dies (#78).

    ⚠ **FOUR HOURS, AND IT IS A BEARER TOKEN.** `document_store.download_url`
    mints it at `document_storage.url_ttl_seconds()`, which is capped at four
    hours by the PO's ruling of 2026-08-30 and REFUSES a longer setting rather
    than clamping it. Whoever holds the URL reads this one photograph with no
    session and no further check until it expires. Do not put one in an email
    that outlives it; if a link needs to live longer, issue a new link.

    ⚠ **THE ROW IS RESOLVED UNDER THIS TENANT FIRST, AND THEN THE URL IS
    MINTED.** Order matters: a link is never issued for a photograph the caller
    could not have found. Lone Star Ridge asking for a Brazos Bend photograph
    gets a 404 — the same answer as for one that does not exist (`US-WRK-048`
    TC-6, HR-1).

    ⚠ **AND THE LINK IS NOT A STATEMENT THAT THE FILE IS KEPT FOREVER.** Twelve
    months, then an export before deletion (`BR-WRK-048`). Nothing is pruned
    today because the export does not exist.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)
    row = models.WorkOrderAttachment.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, id=attachment_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")

    from apps.tenancy import document_storage

    ttl = document_storage.url_ttl_seconds()
    return {
        "id": str(row.id),
        "kind": row.kind,
        "taken_at": row.taken_at,
        "device": row.device,
        "url": document_store.download_url(row.document_id),
        "expires_in_seconds": ttl,
    }


def attachment_bytes(order_id: Any, attachment_id: Any) -> tuple[bytes, str]:
    """`GET /work-orders/{id}/attachments/{aid}/content` — the photograph's own
    bytes, SAME-ORIGIN (`DEF-WRK-9594`, CR-168-BRC10 P1.22).

    ⚠ **WHY NOT THE LINK ABOVE.** `attachment_link` answers a presigned link on
    the storage host, and the staff app's page policy draws images only from
    itself (`img-src 'self' data: blob:`), so a browser refuses the picture —
    and on the local store the link is `file://`, refused too. Served through
    the API, the picture rides the session like every other read: no bearer
    token leaves the server and nothing widens the page policy.

    The row is resolved under this tenant FIRST (`US-WRK-048` TC-6, HR-1): a
    neighbouring utility's photograph is the same 404 as one that does not
    exist. `document_store.fetch` re-checks the stored hash on every read.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)
    row = models.WorkOrderAttachment.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, id=attachment_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    ref = document_store.reference(row.document_id)
    return document_store.fetch(row.document_id), ref.content_type


def attachments_for_order(order_id: Any) -> list[dict[str, Any]]:
    """Every photograph on this job, oldest shutter first — `Work-033`'s list."""
    tenant_id = _tenant_id()
    _order_or_404(order_id)
    rows = (
        models.WorkOrderAttachment.objects.filter(tenant_id=tenant_id, work_order_id=order_id)
        .select_related("added_by")
        .order_by("taken_at")
    )
    return [_attachment_dict(row, duplicate=False) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════
# THE SIGNATURE — or the refusal, and never both
# ═══════════════════════════════════════════════════════════════════════════


def capture_signature(actor: Any, order_id: Any, payload: dict[str, Any], upload: Any = None) -> dict[str, Any]:
    """`POST /work-orders/{id}/signature` — signed, or refused (#79).

    `BR-WRK-046`, and r10 in its own words: *"if refused, record decline reason
    and photo of door hanger"*.

      * **signed**  — `printed_name` and the signature image: the bytes
        (`upload`, the web form) or `image_photo_id` (the phone).
      * **refused** — `decline_reason` and the door-hanger photograph:
        `door_hanger_attachment_id`, which must already be one of this job's
        photographs (the web form), or `door_hanger_photo_id` (the phone).

    ⚠ **THE PHONE NAMES A PHOTOGRAPH BY ITS OWN PHOTO ID (`DEF-WRK-10625`).**
    Its bytes upload later on signal, so the id must name a `WorkPhotoLink` ON
    THIS ORDER — and when the signature item arrives ahead of the photo's own
    declaration (the phone's outbox writes the act first), `*_sha256` beside
    the id lets this function make the link itself, exactly as `declare` would;
    the declaration that follows answers the same link. Order of arrival
    therefore never matters. Until 2026-10-27 every refusal from a phone was
    refused here.

    ⚠ **NEVER BOTH, AND THE DATABASE SAYS SO TOO** — the CHECK constraint
    `ck_work_order_signatures_shape` is the rule, and this function refuses
    earlier only so the caller gets a sentence instead of an integrity error.
    Do not remove either: the validator is the message and the constraint is the
    guarantee (hard-won law 1).

    ⚠ **THE DOOR HANGER IS AN ATTACHMENT, NOT A LOOSE DOCUMENT.** It is one of
    the job's photographs, taken on the same phone on the same visit, and it
    appears in the job's evidence list like any other. See
    `WorkOrderSignature`'s docstring for why this diverges from
    `US-WRK-048` §5's `door_hanger_document_id`.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)

    if models.WorkOrderSignature.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id
    ).exists():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.signature.already_captured",
            br_ref="BR-WRK-046",
        )

    refused = bool(payload.get("refused"))
    signed_at = payload.get("signed_at") or timezone.now()

    if refused:
        reason = str(payload.get("decline_reason") or "").strip()
        if not reason:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.signature.reason_required",
                br_ref="BR-WRK-046",
            )
        if payload.get("printed_name"):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="work.signature.never_both",
                br_ref="BR-WRK-046",
            )
        hanger_id = payload.get("door_hanger_attachment_id")
        hanger = models.WorkOrderAttachment.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id, id=hanger_id
        ).first() if hanger_id else None
        hanger_link = None if hanger is not None else _phone_photo(actor, order_id, payload, "door_hanger")
        if hanger is None and hanger_link is None:
            # `BR-WRK-046` asks for the photograph, so a refusal without one is
            # not a lesser record — it is an unevidenced claim that somebody
            # declined, which is the thing a dispute turns on.
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.signature.door_hanger_required",
                br_ref="BR-WRK-046",
            )
        row = models.WorkOrderSignature.objects.create(
            tenant_id=tenant_id,
            work_order_id=order_id,
            refused=True,
            decline_reason=reason,
            door_hanger=hanger,
            door_hanger_photo_id=hanger_link.photo_id if hanger_link is not None else None,
            signed_at=signed_at,
            captured_by_id=_actor_id(actor),
        )
    else:
        printed = str(payload.get("printed_name") or "").strip()
        if not printed:
            # A squiggle with no name beside it cannot be attributed to anybody
            # six months later, which is the only thing it is FOR.
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.signature.printed_name_required",
                br_ref="BR-WRK-046",
            )
        if payload.get("decline_reason"):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="work.signature.never_both",
                br_ref="BR-WRK-046",
            )
        image_bytes = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
        mark_link = None if image_bytes else _phone_photo(actor, order_id, payload, "image")
        if not image_bytes and mark_link is None:
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="work.signature.image_required",
                br_ref="BR-WRK-046",
            )
        if mark_link is not None:
            # The phone's mark: the file lands later on its link and is read
            # through it (`signature_image_bytes`), never copied onto this row.
            row = models.WorkOrderSignature.objects.create(
                tenant_id=tenant_id,
                work_order_id=order_id,
                refused=False,
                printed_name=printed,
                image_photo_id=mark_link.photo_id,
                signed_at=signed_at,
                captured_by_id=_actor_id(actor),
            )
        else:
            row = _store_signed(actor, tenant_id, order_id, payload, printed, image_bytes, signed_at)

    core_audit.write_row(
        action="work.signature.captured",
        entity_type="work_order_signature",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after={
            "work_order_id": str(order_id),
            "refused": row.refused,
            "printed_name": row.printed_name,
            "decline_reason": row.decline_reason,
            "door_hanger_photo_id": str(row.door_hanger_photo_id) if row.door_hanger_photo_id else None,
            "image_photo_id": str(row.image_photo_id) if row.image_photo_id else None,
        },
    )
    return signature_for_order(order_id)


def _store_signed(
    actor: Any, tenant_id: Any, order_id: Any, payload: dict[str, Any], printed: str, image_bytes: bytes, signed_at: Any
) -> Any:
    """The web form's signed mark: the bytes, shrunk and stored, on the row."""
    # DEF-WRK-9641 — a signature image is shrunk, never refused for size.
    try:
        shrunk, shrunk_type = work_documents.shrink_photo(image_bytes)
    except work_documents.NotAnImage as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.attachment.not_an_image",
            br_ref="BR-WRK-047",
        ) from exc
    if len(shrunk) != len(image_bytes):
        image_bytes = shrunk
        payload = {**payload, "content_type": shrunk_type}
    ref = document_store.store(
        kind=KIND_WORK_ORDER_SIGNATURE,
        source_type=SOURCE_WORK_ORDER,
        source_id=order_id,
        content_type=str(payload.get("content_type") or "image/png"),
        display_name=f"signature-{order_id}.png",
        payload=image_bytes,
        actor_user_id=_actor_id(actor),
    )
    return models.WorkOrderSignature.objects.create(
        tenant_id=tenant_id,
        work_order_id=order_id,
        refused=False,
        printed_name=printed,
        image_id=ref.id,
        signed_at=signed_at,
        captured_by_id=_actor_id(actor),
    )


def _phone_photo(actor: Any, order_id: Any, payload: dict[str, Any], prefix: str) -> Any:
    """The `WorkPhotoLink` the phone named as `<prefix>_photo_id`, ON THIS ORDER
    — made here from `<prefix>_sha256` when the signature item arrived ahead of
    the photo's own declaration (`DEF-WRK-10625`). None when nothing usable was
    named: no id, an id that is not a uuid, an id declared on ANOTHER order (a
    phone syncing nine jobs attaching job 4's photo to job 5 — the mistake
    `_checklist_target` exists for), or an undeclared id with no hash to
    declare it by. The caller turns None into its own refusal."""
    import uuid

    from apps.work import photo_links
    from apps.work.evidence_models import WorkPhotoLink

    raw = payload.get(f"{prefix}_photo_id")
    if not raw:
        return None
    try:
        photo_id = uuid.UUID(str(raw))
    except ValueError:
        return None
    tenant_id = _tenant_id()
    link = WorkPhotoLink.objects.filter(tenant_id=tenant_id, photo_id=photo_id).first()
    if link is None and payload.get(f"{prefix}_sha256"):
        photo_links.declare(
            actor,
            order_id,
            {"photo_id": str(photo_id), "sha256": payload.get(f"{prefix}_sha256")},
            taken_at=payload.get("signed_at") or None,
        )
        link = WorkPhotoLink.objects.filter(tenant_id=tenant_id, photo_id=photo_id).first()
    if link is None or str(link.work_order_id) != str(order_id):
        return None
    return link


def _landed_attachment(tenant_id: Any, photo_id: Any) -> Any:
    """The attachment a phone photograph became once its bytes landed, else None."""
    from apps.work.evidence_models import WorkPhotoLink

    if not photo_id:
        return None
    link = (
        WorkPhotoLink.objects.filter(tenant_id=tenant_id, photo_id=photo_id)
        .select_related("attachment")
        .first()
    )
    return link.attachment if link is not None and link.attachment_id else None


def signature_for_order(order_id: Any) -> dict[str, Any] | None:
    """What the customer did, for `Work-008`'s Customer tab. None if nothing yet."""
    tenant_id = _tenant_id()
    row = (
        models.WorkOrderSignature.objects.filter(tenant_id=tenant_id, work_order_id=order_id)
        .select_related("captured_by")
        .first()
    )
    if row is None:
        return None
    hanger = None if row.door_hanger_id else _landed_attachment(tenant_id, row.door_hanger_photo_id)
    return {
        "id": str(row.id),
        "refused": row.refused,
        "printed_name": row.printed_name,
        "decline_reason": row.decline_reason,
        # The web's chosen attachment, or the phone's photograph once its
        # bytes have landed (DEF-WRK-10625); `door_hanger_uploading` says the
        # photo was named and has not arrived yet, so the office reads
        # *uploading* rather than *missing*.
        "door_hanger_attachment_id": (
            str(row.door_hanger_id) if row.door_hanger_id else (str(hanger.id) if hanger is not None else None)
        ),
        "door_hanger_uploading": bool(row.door_hanger_photo_id) and not row.door_hanger_id and hanger is None,
        "signed_at": row.signed_at,
        # ── CR-168-BRC10 P1.23 · serve the signature's MARK ─────────────────
        # Who captured it (the technician at the door), and a link to the
        # image that dies after four hours (`attachment_link`'s bearer-token
        # rule, PO 2026-08-30). Minted only once the row is resolved under this
        # tenant; None for a refusal, which has no mark.
        "captured_by": (
            {"name": row.captured_by.full_name or row.captured_by.email}
            if row.captured_by_id
            else None
        ),
        "image_url": _signature_link(row),
    }


def _signature_link(row: Any) -> str | None:
    """A SAME-ORIGIN API path to the mark, never a storage link (`DEF-WRK-9594`,
    recorded by lane ORDER-PAGE in §7.3): the staff app's page policy draws
    images only from itself, so a presigned storage URL is refused by the
    browser. The bytes come through `signature_image_bytes`, under the session.
    None for a refusal, which has no mark."""
    from apps.work.seams import tenancy_seam

    if row.refused or not (row.image_id or _landed_attachment(row.tenant_id, row.image_photo_id)):
        return None
    slug = tenancy_seam.tenant_slug()
    if not slug:
        return None
    return f"/api/{slug}/work-orders/{row.work_order_id}/signature/image"


def signature_image_bytes(order_id: Any) -> tuple[bytes, str]:
    """`GET /work-orders/{id}/signature/image` — the signature's mark, same-origin
    (`CR-168-BRC10` P1.23). Resolved under this tenant first (HR-1); a refusal,
    or no signature, is the same 404 as an order that does not exist."""
    tenant_id = _tenant_id()
    _order_or_404(order_id)
    row = models.WorkOrderSignature.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id
    ).first()
    if row is None or row.refused:
        raise errors.deny_as_not_found("BR-TEN-003")
    # The web form's stored mark, or the phone's once its bytes landed
    # (DEF-WRK-10625); a mark still uploading is the same 404 as none.
    landed = None if row.image_id else _landed_attachment(tenant_id, row.image_photo_id)
    document_id = row.image_id or (landed.document_id if landed is not None else None)
    if not document_id:
        raise errors.deny_as_not_found("BR-TEN-003")
    ref = document_store.reference(document_id)
    return document_store.fetch(document_id), ref.content_type


# ═══════════════════════════════════════════════════════════════════════════
# CLOSE READINESS — the two rules, kept apart
# ═══════════════════════════════════════════════════════════════════════════


def close_readiness(order_id: Any) -> dict[str, Any]:
    """May this job close, and what it is short of.

    ⚠ **`BR-WRK-040` SUPERSEDED 2026-10-21 (PO: *"warn"*).** Missing REQUIRED
    photographs moved from `blocking` to `missing_photos`: they WARN on the
    phone and are recorded on the close for the office, and they no longer
    stop it. `blocking` stays on the answer, EMPTY, because it is the shape the
    phone's Close button reads — a key removed would read as *undefined* on a
    build that still checks it, and an empty list reads as *may close*, which
    is now the truth. `flagged` (out of range, `BR-WRK-039`) is unchanged and
    still a separate list from `missing_photos`.

    Returns the two counts `Work-033`'s footer states — *3 of 4 readings
    captured · 2 of 3 required photographs* — because a screen that computed
    them itself would be a second opinion about whether the job can close.
    """
    tenant_id = _tenant_id()
    _order_or_404(order_id)

    readings = list(
        models.WorkOrderReading.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id
        ).order_by("seq")
    )
    tasks = list(
        models.WorkOrderTask.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id
        ).order_by("seq")
    )

    reasons = (
        metering_seam.cant_read_reason_index()
        if any(r.unable_to_read and r.unable_reason for r in readings)
        else {}
    )

    # Nothing blocks a close any more (`BR-WRK-040` superseded); the list is
    # kept for the reason in the docstring.
    blocking: list[dict[str, Any]] = []
    missing_photos: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    # CR-168-BRC10 §F (PO 2026-10-04): a required photograph whose LINK exists
    # — declared in the data page, bytes still uploading — satisfies the
    # CLOSE. It is PENDING, never missing; the office's Accept is what waits
    # for it (`photo_links.refuse_accept_while_uploading`).
    from apps.work.evidence_models import WorkPhotoLink

    linked = {
        str(v)
        for pair in WorkPhotoLink.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id
        ).values_list("task_id", "reading_id")
        for v in pair
        if v
    }
    pending = WorkPhotoLink.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, required=True
    ).exclude(state=WorkPhotoLink.STATE_LANDED).count()

    for row in readings:
        # THE RULE and THE FILE — two columns, and this is the read that needs
        # them apart (`US-WRK-049`). `photo_required and not photo_attachment_id`
        # is *asked for and not taken*; `not photo_required` is *never asked*,
        # and the two must not produce the same sentence.
        if row.photo_required and not row.photo_attachment_id and str(row.id) not in linked:
            missing_photos.append(
                {
                    "kind": "missing_required_photo",
                    "scope": "reading",
                    "id": str(row.id),
                    "prompt": row.prompt,
                }
            )
        if row.in_range is False:
            flagged.append(
                {
                    "kind": "out_of_range",
                    "scope": "reading",
                    "id": str(row.id),
                    "prompt": row.prompt,
                    "value": str(row.value) if row.value is not None else None,
                    "unit": row.unit_of_measure,
                }
            )
        if row.unable_to_read:
            # `DEF-WRK-10601` — flagged for the office, never blocking: the
            # technician answered that there is no figure to take.
            flagged.append(
                {
                    "kind": "unable_to_read",
                    "scope": "reading",
                    "id": str(row.id),
                    "prompt": row.prompt,
                    # `DEF-MET-10609` — the reason's NAME from the one list.
                    "reason": unable_reason_label(row.unable_reason, reasons),
                }
            )
    for row in tasks:
        if row.photo_required and not row.photo_attachment_id and str(row.id) not in linked:
            missing_photos.append(
                {
                    "kind": "missing_required_photo",
                    "scope": "task",
                    "id": str(row.id),
                    "prompt": row.title,
                }
            )

    required_photos = [r for r in readings if r.photo_required] + [
        t for t in tasks if t.photo_required
    ]
    return {
        # Neither a missing required photograph nor an out-of-range value
        # stops the close (`BR-WRK-040` superseded 2026-10-21, `BR-WRK-039`).
        # Both facts are on this object and neither is derived from the other.
        "can_close": not blocking,
        "blocking": blocking,
        "missing_photos": missing_photos,
        "flagged": flagged,
        # A reading is ANSWERED by a figure, by words on a text reading
        # (`DEF-WRK-10602`) or by *Unable to read* (`DEF-WRK-10601`), as the
        # phone's own count reads it.
        "readings_captured": len([
            r for r in readings if r.value is not None or r.value_text or r.unable_to_read
        ]),
        "readings_total": len(readings),
        "required_photos_taken": len([r for r in required_photos if r.photo_attachment_id]),
        "required_photos_total": len(required_photos),
        # Declared and still uploading — the count *N photos uploading* reads.
        "required_photos_pending": pending,
    }
