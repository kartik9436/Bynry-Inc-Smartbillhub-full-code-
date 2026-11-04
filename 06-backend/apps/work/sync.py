# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-044 (offline capture and one sync) · US-WRK-045 (the close
#           from the phone is `submit_field_result` and nothing more)
#           Screens: Work-012, Work-010
# Rules:    BR-WRK-042 (a per-item idempotency key; a re-sync adds nothing) ·
#           BR-WRK-041 (the close activates nothing) · BR-WRK-037 (the safety
#           lock, re-derived on the server) · BR-MET-110 (only acceptance makes
#           anything real) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule
#           7 (every act audited) · **hard-won law 14 (the savepoint)**
# Tests:    06-backend/tests/test_us_wrk_044_sync.py (shape, order, kinds) ·
#           06-backend/tests/test_us_wrk_044_sync_pg.py (**the savepoint, on
#           real PostgreSQL — the SQLite suite cannot see it**) ·
#           tests/test_cr187_sync_volume.py · tests/test_cr187_sync_volume_pg.py
#           (CR-187-BRC10 T-30/T-46: 1,000 readings in 20 batches of 50, the
#           batch across jobs, and the savepoint's red proof)
# Impacts:  apps/work/api.py (#90) · apps/work/sync_models.py (the receipts) ·
#           apps/metering/connections.submit_field_result (the close)
# ───────────────────────────────────────────────────────
"""`POST /work/mobile/jobs/{id}/sync` — a day's captured work, applied once.

WHAT THIS IS
────────────────────────────────────────────────────────────────────────────
A technician works with no signal from 08:13 to 17:40. Every act — a safety
tick, a task tick, a reading, a part used, a photograph, a signature, the close
— is queued on the handset with a key minted AT CAPTURE. At 17:40 the phone
sends one batch per job, **in capture order**, and this applies them.

It answers **per-item results, never a boolean** (`07-endpoints.md` #90). A
boolean would collapse the three answers that matter into one: *accepted* is new
work, *duplicate* is the offline queue behaving correctly, and *refused* is
something a technician has to see and re-do.

⚠ **SOMETHING THE SERVER CANNOT ACCEPT GOES BACK TO THE TECHNICIAN — FROM
2026-10-21.** PO, verbatim: *"back to the technician"* (decision log *"Field
app: the PO corrects four of the ten answers"* item 4). **`BR-WRK-063` is
SUPERSEDED for field items**: until then an item this server could not apply —
the job closed, cancelled or accepted while the phone was offline, a captor who
is not the assignee, an expired capture credential, a malformed time, an
unknown kind, a refusal from the service underneath — was STORED in
`work_sync_receipts` with `needs_review`, acknowledged, and answered
`held_for_review`. Now it is answered **`refused`**, NOT acknowledged, with a
machine `detail.reason` and a `detail.message_key`, and **nothing is stored**:
no receipt, so no key is spent and the fixed item can be resent under the same
key or a new one and post exactly once. The phone keeps it and shows it to the
technician to fix and resend (R48, E2E-07, RW-27) — the no-drop half of
`BR-WRK-063` stands, it is simply the phone that holds the item now. The batch
audit row lists each refused item's key, kind and reason, which is the
diagnostic record. `held_for_review` stays a COUNT on the answer (always 0 from
this server) so a build reading it does not break.

⚠ **AND FROM 2026-10-26 THE SERVER *ALSO* KEEPS A COPY — "NOTHING IS STORED"
ABOVE IS AMENDED.** PO, verbatim: *"store on both"* (decision log 2026-10-26,
*"Refused field work is kept on BOTH the phone and the server"*; `CR-194-BRC10`,
`BR-WRK-071`). Every refused item with a key is copied into
`work_refused_items` for the office's review (`apps/work/refused_items.py`) —
who captured it, which job, the kind, the payload as sent (never the capture
token), the reason and when — and its answer gains `detail.kept_for_office:
true`. **Everything else above stands:** it is still `refused` and NOT
acknowledged, and **the copy is NEVER a receipt**, so the key is still unspent
and the fixed resend posts exactly once; when it does, the copy closes as
`applied_later` in the same savepoint as its receipt. The copy is written in
ITS OWN savepoint after the item's rolled back (law 14, below), so a copy that
cannot be written costs nothing but the `kept_for_office` flag.

⚠ **HARD-WON LAW 14 IS THIS FILE'S CENTRAL DESIGN CONSTRAINT, AND THE SAVEPOINT
IS NOT THE TIDY OPTION — IT IS THE ONLY ONE.**
────────────────────────────────────────────────────────────────────────────
The obvious way to skip a bad item and carry on is::

    for item in items:                      # ⛔ BROKEN ON POSTGRESQL
        try:
            apply(item)
        except IntegrityError:
            results.append("duplicate")
            continue

**On PostgreSQL that loses the whole batch.** Once any statement errors inside a
transaction, the transaction is ABORTED: every later query raises
`InFailedSqlTransaction`, and whatever did succeed is discarded at COMMIT. A
duplicate key on item 5 of 20 therefore destroys items 1–4 as well as 6–20,
and the response says *19 accepted*.

**And the test suite cannot see it.** `config/settings/test.py` hardcodes
in-memory SQLite and ignores `DATABASE_URL`; SQLite has **no aborted-transaction
state**, so the broken version above passes the entire suite, green, on every
machine, and fails the first time a real key repeats in production. That is why
`tests/test_us_wrk_044_sync_pg.py` exists and why it runs under
`config.settings.local` against real PostgreSQL 16.

**So: the nested `transaction.atomic()` below is a SAVEPOINT and it is
load-bearing. Do not "simplify" it into a bare try/except.** If you are reading
this because a linter or a reviewer called it redundant, the answer is
`CLAUDE.md` hard-won law 14, and two independent lanes found it on 2026-08-29
within hours of each other.

WHY THE RECEIPT IS WRITTEN *BEFORE* THE ACT, INSIDE THE SAME SAVEPOINT
────────────────────────────────────────────────────────────────────────────
The receipt INSERT is the duplicate check — the unique constraint is the
guarantee and a preceding SELECT is only an optimisation (wave K's own reasoning
for `work_order_attachments`). Writing it FIRST means a repeated key fails before
any work is done; writing it in the SAME savepoint as the act means a refused
item takes its receipt down with it, so the phone can legitimately re-send it.
A receipt written outside the savepoint would record *accepted* over an act that
rolled back — the one bookkeeping error this table exists to prevent.

WHAT THIS FILE DOES **NOT** DO
────────────────────────────────────────────────────────────────────────────
* **It does not re-sort the batch.** `US-WRK-044` TC-5 and `BR-WRK-037` between
  them require the server to REFUSE a close that arrives before the safety row
  it is gated on. A server that helpfully sorted safety ticks to the front would
  silently repair a tampered client and prove nothing. The list is applied in
  the order it arrived and the lock is re-derived from `ticked_at`, never from
  the client's word.
* **It activates nothing** (`BR-WRK-041`, `BR-MET-110`). The close inside the
  batch is `submit_field_result` and nothing more: `accepted_by` stays NULL,
  no `connection_services` row moves and no `meter_reads` row is written. The
  reading a technician typed becomes a meter read at ACCEPTANCE, through
  `seams/metering_seam.post_set_reads()`, and not here.
* **It does not carry photograph BYTES.** A photograph is delivered by
  `POST /work-orders/{id}/attachments` (#77, multipart, keyed at capture) — a
  JSON batch cannot carry an image and the pre-signed PUT was dropped at 100 KB
  (`BR-WRK-047a`). An `attachment` item in this batch therefore CONFIRMS a row
  #77 already wrote, by its key, and is REFUSED when no such row exists so the
  phone knows to send the bytes again. That is the seam between #77 and #90 and
  it is stated here because nothing else states it.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import audit as core_audit
from core import device_clock, errors
from core import tenancy as core_tenancy

from apps.work import checklist, evidence, mobile, models, money, refused_items
from apps.work import connection_models as work_tables
from apps.work.sync_models import (
    ITEM_KINDS,
    RESULT_ACCEPTED,
    RESULT_DUPLICATE,
    RESULT_REFUSED,
    WorkSyncReceipt,
)

#: The most items one job's queue may carry in one call. A day's work on the
#: biggest drawn job is twenty (`J65`: 3 safety · 7 tasks · 3 readings · 3
#: materials · 2 photographs · 1 signature · 1 close); this is generous by an
#: order of magnitude and exists so a malformed client cannot ask the server to
#: hold ten thousand savepoints open.
MAX_ITEMS = 200


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _order_or_404(order_id: Any) -> Any:
    """The order, under THIS tenant, or the not-found every other door gives.

    `J65` step 13: a queued item for another tenant's order — a swapped phone —
    is a `404`, and the item is marked failed and SHOWN rather than silently
    dropped. The 404 comes from here; the showing is the per-item result.
    """
    from apps.work.seams import metering_seam

    row = metering_seam.work_order(order_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _moment(value: Any) -> Any:
    """The handset's capture time, made aware, or `None`.

    Reuses metering's own parser so `15:12` means the same thing here as it does
    on a dispatcher's appointment window — two parsers for one wire format is
    two answers to the same question.
    """
    if value in (None, ""):
        return None
    from apps.work.seams import metering_seam

    # FB-014 (DEF-FLD-10639) — onto the SERVER's clock by the offset this
    # request measured (`core/device_clock.py`), never refused for being ahead.
    # Everything downstream (the receipt, `completed_at`, which dates the meter
    # read, a photo's `taken_at`, a money proceed) takes this value, already
    # shifted — none of them may shift it again.
    return device_clock.correct(metering_seam.parse_moment(value, field="captured_at"))


def _refused(item_key: str, kind: str, seq: Any, exc: Exception) -> dict[str, Any]:
    """One refusal, as DATA the phone can show and re-queue against.

    The message key and params travel, so the handset renders the same sentence
    the staff app would — a technician standing in a basement gets *"finish
    safety first"*, not a status code.
    """
    detail: dict[str, Any] = {"message": str(exc)}
    for attribute in ("code", "message_key", "params", "br_ref"):
        value = getattr(exc, attribute, None)
        if value not in (None, ""):
            detail[attribute] = value
    return {"key": item_key, "kind": kind, "seq": seq, "result": RESULT_REFUSED, "detail": detail}


# ══════════════════════════════════════════════════════════════════════════
# The seven appliers. Each is the SAME call the online route makes — the phone
# adds a surface, never a second vocabulary (`US-WRK-045`, `WS-12`).
# ══════════════════════════════════════════════════════════════════════════


def _apply_safety_tick(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    return checklist.tick_safety(actor, order_id, body.get("safety_id"))


def _apply_task_tick(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    # CR-187-BRC10 T-35 (R17) — a tick on a step that declares a money check
    # records WHAT the technician proceeded on (`money_as_at`, null = no figure
    # seen) before the tick, inside this item's savepoint. Never refuses: stale
    # is warned on the phone and recorded here as unverified. A step with no
    # money check is untouched (`record_proceed` answers `recorded: False`).
    from apps.work import money

    if body.get("task_id"):
        money.record_proceed(actor, order_id, body.get("task_id"), body)
    return checklist.tick_task(actor, order_id, body.get("task_id"))


def _apply_reading(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    # Wave K's `set_reading` owns hard rule 3 here: it refuses a bare unit and
    # refuses a unit that disagrees with the one the job was raised with. The
    # phone sends the unit it displayed; this route does not default it.
    return evidence.set_reading(actor, order_id, body.get("reading_id"), body)


def _apply_material(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """A part used — delegated to `checklist.set_material_used`, #75's service.

    ⚠ **THIS FUNCTION USED TO BE A SECOND WRITER OF `used_qty` AND ITS OWN
    DOCSTRING ASKED FOR THIS CHANGE**: *"When `PUT /work-orders/{id}/materials/
    {mid}/used` lands, this should call it rather than keep a second writer —
    two writers for one column is how a rule gets forgotten in one of them."*
    The route landed; this calls it.

    **A rule HAD already been forgotten in this one**, which is the argument
    made concrete rather than in the abstract: `work_order_materials` carries
    `issued_by` and `issued_at` — the *who* and *when* `N1` asks #75 for — and
    the inline writer set neither. Every part reported from a handset landed
    with a quantity and no attribution. Delegating fixes that here too, without
    a second edit anyone had to remember to make.
    """
    return checklist.set_material_used(actor, order_id, body.get("material_id"), body)


def _apply_attachment(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """CONFIRM a photograph #77 already delivered — see the module docstring.

    A JSON batch cannot carry an image, so the bytes travel their own multipart
    route and this item is the phone saying *"…and that one belongs to this
    day's queue"*. Refused when the row is absent, because answering *accepted*
    over a photograph the server does not have is exactly the shape hard-won law
    1 is about: a claim of a guarantee that is not the guarantee.
    """
    tenant_id = _tenant_id()
    key = str(body.get("idempotency_key") or "").strip()
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.attachment.key_required",
            br_ref="BR-WRK-047",
        )
    row = models.WorkOrderAttachment.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, idempotency_key=key
    ).first()
    if row is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-047",
            message_key="work.sync.attachment_not_delivered",
            params={"idempotency_key": key},
        )
    return {"id": str(row.id), "idempotency_key": key}


def _apply_signature(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """The phone names its photograph — the door hanger, or the signed mark —
    by its own photo id and hash (`door_hanger_photo_id` / `image_photo_id`,
    DEF-WRK-10625); `capture_signature` links it whichever of the signature and
    the photo's declaration arrives first. `upload` stays for an older caller."""
    return evidence.capture_signature(actor, order_id, body, body.get("upload"))


def _apply_close(
    actor: Any,
    order_id: Any,
    body: dict[str, Any],
    captured_at: Any,
    *,
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`submit_field_result` and nothing more (`BR-WRK-041`).

    ⚠ **`completed_at` IS THE HANDSET'S TIME, NOT 17:40, AND THAT IS THE WHOLE
    POINT OF THE COLUMN.** `J65` step 7 asserts 10:20 · 12:05 · 16:07 for three
    jobs that reached the server together, and `accept_field_result` DATES THE
    METER READ FROM IT (`BR-WRK-003`, `BR-TEN-043` — an event date, never a wall
    clock). A close that stamped the arrival time would put every offline day's
    readings on the wrong day, on a billing path, silently.

    ⚠ **`field_data` IS MERGED, NEVER REPLACED.** `submit_field_result` assigns
    `order.field_data = field_data` wholesale, so passing the phone's payload
    bare would erase a `set_reads` the new-connection wizard had already left
    there (`CR-038` W9). The merge is this caller's job because the metering
    door's contract is *"this is the field data"* and it is right to take that
    literally.
    """
    from apps.work.seams import metering_seam

    existing = _existing_field_data(order_id)
    sent = body.get("field_data")
    merged = {**existing, **(sent if isinstance(sent, dict) else {})}
    # `BR-WRK-061` — where the close was made and how precisely, for the office
    # to see on the order it accepts. Written by the server from the item's
    # location block, never taken from the phone's `field_data`.
    merged["close_location"] = mobile.close_location_record(location)
    # `DEF-WRK-4127` — the technician's own *Arrived* and *Finished* (PO
    # 2026-10-05: *"allow technicain to fill in time"*), validated and written
    # by the server beside the location — never taken from the phone's
    # `field_data` — and the labour is priced from them. Refused (a finish not
    # after the arrival) the close is HELD for the office rather than closed
    # with a duration nobody can stand behind.
    labour_time = mobile.labour_time_record(body.get("arrived_at"), body.get("finished_at"))
    if labour_time is not None:
        merged["labour_time"] = labour_time
    else:
        # A re-close without times must not keep the first close's pair.
        merged.pop("labour_time", None)
    # FB-014 (PO 2026-10-28) — the phone's own clock at send, the shift applied
    # and the times exactly as the phone sent them, kept with the close for
    # audit; the office says *"Phone clock was N min fast"* from `offset_s`.
    # Server-written like the two blocks above, never taken from the phone.
    clock = device_clock.audit_fields()
    if clock:
        merged["device_clock"] = {
            "offset_s": clock["clock_offset_s"],
            "device_time": clock["device_time"],
            "sent": {
                name: body.get(name)
                for name in ("arrived_at", "finished_at")
                if body.get(name) not in (None, "")
            },
        }
    else:
        merged.pop("device_clock", None)
    # FB-013 (`DEF-WRK-10641`, PO rulings 2026-10-28) — a close *Not done —
    # payment received* must carry the phone's snapshot of a FRESH, CLEARED
    # read on a money step, or it is REFUSED back to the technician (strict,
    # decision log judgment 3). The record is SERVER-written — the phone's
    # snapshot as seen beside the server's own read at the close — and a
    # `payment_received` the phone sent itself is never kept, like the blocks
    # above. A re-close with another outcome drops an earlier paid record.
    seen = merged.pop("money_seen", None)
    merged.pop("payment_received", None)
    if body.get("outcome") == work_tables.OUTCOME_NOT_DONE_PAID:
        merged["payment_received"] = money.paid_close_record(order_id, seen, captured_at)
    # ⚠ **THROUGH THE SEAM, NEVER `apps.metering` DIRECTLY** (`BR-WRK-002`).
    # `G78` fails a foreign import from `apps/work/**` by file and line, and it
    # failed this one — which is the gate doing exactly its job.
    return metering_seam.submit_field_result(
        actor,
        order_id,
        field_data=merged or None,
        outcome=body.get("outcome"),
        external_ref=body.get("external_ref"),
        completed_at=captured_at,
    )


def _existing_field_data(order_id: Any) -> dict[str, Any]:
    from apps.work.seams import metering_seam

    row = metering_seam.work_order_row(order_id)
    data = getattr(row, "field_data", None)
    return dict(data) if isinstance(data, dict) else {}


#: Kind → applier. A dict rather than a chain of `if`s so the vocabulary and the
#: behaviour cannot drift: `ITEM_KINDS` and these keys are asserted equal by
#: `tests/test_us_wrk_044_sync.py`, which is what stops an eighth kind being
#: added to the constant and silently doing nothing (`SignupWizard`'s eleventh
#: service, one module over).
_APPLIERS = {
    "safety_tick": _apply_safety_tick,
    "task_tick": _apply_task_tick,
    "reading": _apply_reading,
    "material": _apply_material,
    "attachment": _apply_attachment,
    "signature": _apply_signature,
    "photo": lambda actor, order_id, body: _apply_photo(actor, order_id, body, None),
}


#: ⚠ **NO LONGER PRODUCED (2026-10-21).** TECHNICIAN SYNC DESIGN (2) stored an
#: item the server could not apply and answered this; the PO's correction sends
#: it back to the technician instead (`_send_back`, module docstring). The name
#: and the `held_for_review` COUNT on every answer stay — always 0 — because
#: the web and native field apps read them, and receipts stored before the
#: ruling still carry `needs_review` for the office.
RESULT_HELD = "held_for_review"


def _send_back(key: str, kind: str, seq: Any, message_key: str, params: Any = None) -> dict[str, Any]:
    """**BACK TO THE TECHNICIAN** — the PO's correction of 2026-10-21
    (*"back to the technician"*; `BR-WRK-063` superseded for field items).

    `refused`, NOT acknowledged, and NO RECEIPT: the key is not spent and the
    phone keeps the item, shows it, and resends it once fixed — the same key
    or a new one, and it posts once either way. (From 2026-10-26 `_one_item`
    ALSO keeps the office's copy — never a receipt — `CR-194-BRC10`.)
    `detail.reason` is the machine word the phone switches on (the last segment
    of the key: `job_already_closed`, `capture_token_expired`, …) and
    `detail.message_key` is the sentence, from the catalogue; `params` carry
    the specifics. Nothing here composes words (B14 rule 35).
    """
    return {
        "key": key,
        "kind": kind,
        "seq": seq,
        "result": RESULT_REFUSED,
        "ack": False,
        "detail": {
            "reason": str(message_key).rsplit(".", 1)[-1],
            "message_key": message_key,
            "params": params or {},
            "br_ref": "BR-WRK-063",
        },
    }


def apply_kind(
    actor: Any, order_id: Any, kind: str, body: dict[str, Any], captured_at: Any, *, location: Any = None
) -> Any:
    """Apply ONE item of `kind` — the dispatch the sync and the office's
    *Apply to the job* (`refused_items.apply_to_job`, CR-194-BRC10) share, so
    the office re-runs exactly the path the phone's item would have taken.
    Raises whatever the service raises; the caller holds the savepoint."""
    if kind == "close":
        return _apply_close(actor, order_id, body, captured_at, location=location)
    if kind == "photo":
        return _apply_photo(actor, order_id, body, captured_at)
    if kind == "task_tick" and captured_at is not None and "proceeded_at" not in body:
        # CR-187-BRC10 T-35 — a money proceed is timed by the HANDSET's
        # capture, not by when the queue reached the server.
        return _APPLIERS[kind](actor, order_id, {**body, "proceeded_at": captured_at.isoformat()})
    if kind == "task_tick" and body.get("proceeded_at") and device_clock.current() is not None:
        # FB-014 — a proceed the phone timed itself is on the phone's clock.
        from apps.work.seams import metering_seam

        moved = device_clock.correct(metering_seam.parse_moment(body["proceeded_at"], field="proceeded_at"))
        return _APPLIERS[kind](actor, order_id, {**body, "proceeded_at": moved.isoformat()})
    return _APPLIERS[kind](actor, order_id, body)


def _one_item(actor: Any, order: Any, tenant_id: Any, position: int, raw: Any) -> dict[str, Any]:
    """One item's answer — and, when it is REFUSED, the office's copy of it
    (CR-194-BRC10, PO 2026-10-26 *"store on both"*).

    ⚠ LAW 14: `refused_items.keep` runs in ITS OWN savepoint, AFTER the item's
    savepoint rolled back, and never raises — a copy that cannot be written is
    logged and the item is answered exactly as before, without
    `kept_for_office`. The copy is never a receipt, so the key stays unspent."""
    answer = _one_item_answer(actor, order, tenant_id, position, raw)
    if answer.get("result") == RESULT_REFUSED and answer.get("key"):
        if refused_items.keep(
            door=refused_items.DOOR_JOB, item=raw, refusal=answer, work_order_id=order["id"], courier=actor
        ):
            refused_items.mark_kept(answer)
    return answer


def _one_item_answer(actor: Any, order: Any, tenant_id: Any, position: int, raw: Any) -> dict[str, Any]:
    """One item: applied, a duplicate, or refused BACK TO THE TECHNICIAN with
    its reason (the PO's correction of 2026-10-21 — see the module docstring).
    Only an APPLIED item writes a receipt."""
    item = raw if isinstance(raw, dict) else {}
    key = str(item.get("key") or "").strip()
    kind = str(item.get("kind") or "").strip()
    seq = item.get("seq", position)
    body = item.get("payload") if isinstance(item.get("payload"), dict) else {}

    # ── WHO captured it (BR-WRK-059). A token that does not verify names no
    # technician of this tenant and is refused outright. An EXPIRED token
    # (or a handset the office signed out) still names its technician, and is
    # refused BACK with `capture_token_expired`: the technician signs in, the
    # phone re-stamps the item with a fresh token and sends it again.
    item_actor, captor, state_reason = actor, None, None
    token = item.get("capture_token")
    if token:
        try:
            item_actor, captor = mobile.captor_from_token(token)
        except errors.AuthError as exc:
            if getattr(exc, "message_key", "") == "work.mobile.capture_token_expired":
                try:
                    item_actor, captor = mobile.captor_from_token(token, allow_expired=True)
                    state_reason = "work.mobile.capture_token_expired"
                except errors.AuthError as again:
                    return _refused(key, kind, seq, again)
            else:
                return _refused(key, kind, seq, exc)

    if not key:
        # Hard rule 6: an item with no key cannot be applied once and only once.
        return _send_back("", kind, seq, "work.sync.item_key_required")

    # The cheap duplicate read first: a replay of anything already stored —
    # applied, or held before 2026-10-21 — answers *duplicate* and is
    # acknowledged. A refused item wrote no receipt (its office copy lives in
    # `work_refused_items`, never read here), so it never reads as one.
    if WorkSyncReceipt.objects.filter(tenant_id=tenant_id, work_order_id=order["id"], key=key).exists():
        return {"key": key, "kind": kind, "seq": seq, "result": RESULT_DUPLICATE, "ack": True,
                "detail": _duplicate_detail(order, kind, body)}

    captured_at = None
    location = None
    try:
        captured_at = _moment(item.get("captured_at"))
        location = mobile.parse_location(item.get("location"))
    except Exception as exc:  # noqa: BLE001 — malformed: back to the technician
        return _send_back(key, kind, seq,
                          getattr(exc, "message_key", None) or "work.sync.item_malformed",
                          getattr(exc, "params", None))
    if kind not in ITEM_KINDS:
        return _send_back(key, kind, seq, "work.sync.unknown_item_kind",
                          {"kind": kind, "kinds": list(ITEM_KINDS)})

    # ── STATE reasons: the job moved on while the phone was offline (closed,
    # cancelled, accepted, given to someone else). Back to the technician —
    # the PO's correction of 2026-10-21; `BR-WRK-063`'s *stored and flagged*
    # is superseded for field items.
    if state_reason is None:
        state_reason = mobile.state_reason_for(captor, order["id"]) if captor else None
    if state_reason is None:
        state_reason = mobile.order_state_reason(order["id"], kind)
    if state_reason is not None:
        return _send_back(key, kind, seq, state_reason)

    try:
        # ── THE SAVEPOINT. LAW 14. DO NOT REMOVE. ─────────────────────────
        # A nested `atomic()` inside the outer one issues SAVEPOINT / RELEASE /
        # ROLLBACK TO. Without it, an IntegrityError aborts the WHOLE
        # transaction on PostgreSQL and every later item raises
        # `InFailedSqlTransaction`. SQLite has no aborted-transaction state, so
        # the version without this passes the entire suite green.
        with transaction.atomic():
            WorkSyncReceipt.objects.create(
                tenant_id=tenant_id,
                work_order_id=order["id"],
                key=key,
                kind=kind,
                seq=seq if isinstance(seq, int) else position,
                captured_at=captured_at,
                # The CAPTOR, never the courier (BR-WRK-059).
                accepted_by_id=_actor_id(item_actor),
                captured_by_technician=captor,
                lat=(location or {}).get("lat"),
                lng=(location or {}).get("lng"),
                accuracy_m=(location or {}).get("accuracy_m"),
                fix_at=(location or {}).get("fix_at"),
            )
            applied = apply_kind(item_actor, order["id"], kind, body, captured_at, location=location)
            # CR-194-BRC10 — the same key APPLIED: the office's copy of an
            # earlier refusal closes as `applied_later`, in THIS savepoint,
            # beside the receipt, so the two can never disagree.
            refused_items.close_applied(key=key, door=refused_items.DOOR_JOB, work_order_id=order["id"])
    except IntegrityError:
        # A duplicate ONLY if the key really is stored — a lost race. Any other
        # integrity failure is the APPLY failing, and acknowledging it as a
        # duplicate would drop the item; it goes back to the technician. The
        # savepoint took the receipt with it, so the key is not spent.
        if WorkSyncReceipt.objects.filter(tenant_id=tenant_id, work_order_id=order["id"], key=key).exists():
            return {"key": key, "kind": kind, "seq": seq, "result": RESULT_DUPLICATE, "ack": True}
        return _send_back(key, kind, seq, "work.sync.item_not_applied")
    except Exception as exc:  # noqa: BLE001
        # ⚠ **THIS READ IS LOAD-BEARING — LAW 14, AND IT IS NOT A DUPLICATE
        # CHECK FIRST.** A refusal stores nothing, so unlike the `_hold` it
        # replaced this branch would otherwise touch the database NOT AT ALL —
        # and on PostgreSQL WITHOUT the savepoint above, every later item's
        # `InFailedSqlTransaction` would be caught right here and answered
        # *refused*, the batch would report success and COMMIT would silently
        # roll everything back. Reading the receipts table makes a poisoned
        # transaction RAISE instead, which is what
        # `test_without_the_savepoint_the_same_batch_is_LOST_on_postgres`
        # proves (it went GREEN — wrongly — without this line, 2026-10-21).
        if WorkSyncReceipt.objects.filter(tenant_id=tenant_id, work_order_id=order["id"], key=key).exists():
            return {"key": key, "kind": kind, "seq": seq, "result": RESULT_DUPLICATE, "ack": True}
        if getattr(exc, "code", None) == errors.BIZ_LOCKED:
            # The safety lock — fixed on the spot by ticking the row. Its
            # refusal shape predates the ruling and the phones read it as is.
            return _refused(key, kind, seq, exc)
        # A unit missing or not the job's, a future close, a refused act: the
        # service's own key and params, back to the technician. The savepoint
        # took the receipt, so nothing is stored and the key is not spent.
        return _send_back(key, kind, seq,
                          getattr(exc, "message_key", None) or "work.sync.item_not_applied",
                          getattr(exc, "params", None))
    return {
        "key": key,
        "kind": kind,
        "seq": seq,
        "result": RESULT_ACCEPTED,
        "ack": True,
        "detail": applied if isinstance(applied, dict) else None,
    }


def _duplicate_detail(order: Any, kind: str, body: dict[str, Any]) -> dict[str, Any] | None:
    """A replayed PHOTO declaration answers its SAME link (the PO's correction:
    *re-sending the same page returns the same links, never new ones*)."""
    if kind != "photo":
        return None
    from apps.work import photo_links

    return photo_links.link_answer_for(body.get("photo_id"))


def _apply_photo(actor: Any, order_id: Any, body: dict[str, Any], captured_at: Any) -> dict[str, Any]:
    """A photo DECLARATION in a data page — the link is created here, in the
    same save as the record, and answered to the phone (PO 2026-10-04)."""
    from apps.work import photo_links

    return photo_links.declare(actor, order_id, body, taken_at=captured_at)


def every_item_has_a_capture_token(payload: Any) -> bool:
    """True when a batch is non-empty and every item names its captor."""
    items = (payload or {}).get("items") if isinstance(payload, dict) else None
    return (
        isinstance(items, list)
        and bool(items)
        and all(isinstance(i, dict) and str(i.get("capture_token") or "").strip() for i in items)
    )


def sync_batch(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one job's queued items, in capture order, once each.

    Returns::

        {"work_order_id", "accepted", "duplicate", "refused",
         "items": [{key, kind, seq, result, detail?}, ...],
         "synced_at", "br_ref": "BR-WRK-042"}

    The counts are DERIVED from `items` rather than tallied alongside it, so the
    summary can never disagree with the list it summarises.
    """
    order = _order_or_404(order_id)
    tenant_id = _tenant_id()

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.sync.no_items",
            br_ref="BR-WRK-042",
        )
    if len(raw_items) > MAX_ITEMS:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.sync.too_many_items",
            br_ref="BR-WRK-042",
            params={"sent": len(raw_items), "max": MAX_ITEMS},
        )

    results: list[dict[str, Any]] = []

    # ⚠ **ONE OUTER TRANSACTION, AND A SAVEPOINT PER ITEM INSIDE IT.** The outer
    # block is what makes each inner `atomic()` a SAVEPOINT rather than its own
    # transaction — which is the entire mechanism hard-won law 14 prescribes.
    # Remove the outer block and the inner ones silently become full
    # transactions: the code still passes every test and the batch stops being
    # one act.
    with transaction.atomic():
        for position, raw in enumerate(raw_items, start=1):
            results.append(_one_item(actor, order, tenant_id, position, raw))

        core_audit.write_row(
            action="work.mobile.synced",
            entity_type="work_order",
            entity_id=order["id"],
            actor_user_id=_actor_id(actor),
            after={
                "items": len(results),
                "accepted": sum(1 for r in results if r["result"] == RESULT_ACCEPTED),
                "duplicate": sum(1 for r in results if r["result"] == RESULT_DUPLICATE),
                "refused": sum(1 for r in results if r["result"] == RESULT_REFUSED),
                "held_for_review": sum(1 for r in results if r["result"] == RESULT_HELD),
                # The diagnostic record of what went back to the technician
                # (2026-10-21); the office's copy is `work_refused_items`
                # (2026-10-26, CR-194-BRC10).
                "refused_items": [
                    {"key": r.get("key"), "kind": r.get("kind"),
                     "reason": (r.get("detail") or {}).get("reason")
                     or (r.get("detail") or {}).get("message_key")}
                    for r in results if r["result"] == RESULT_REFUSED
                ],
                # FB-014 — the phone's clock at send and the shift every time
                # in this batch took; original = stored − clock_offset_s.
                **device_clock.audit_fields(),
                "br_ref": "BR-WRK-042",
            },
        )

    # TECHNICIAN SYNC DESIGN (5) — the office is told about a close and about
    # anything held for review. AFTER the items' transaction, and it never
    # raises: telling the office can never cost a field record (CR-168 §F).
    from apps.work import office_notices

    office_notices.after_sync(order["id"], results)

    return {
        "work_order_id": str(order["id"]),
        "accepted": sum(1 for r in results if r["result"] == RESULT_ACCEPTED),
        "duplicate": sum(1 for r in results if r["result"] == RESULT_DUPLICATE),
        "refused": sum(1 for r in results if r["result"] == RESULT_REFUSED),
        "held_for_review": sum(1 for r in results if r["result"] == RESULT_HELD),
        # The ACK list (TECHNICIAN SYNC DESIGN (1)): the phone removes an item
        # from its outbox ONLY when its key is here. A refused item is not
        # acknowledged and stays on the phone for the technician to fix.
        "acknowledged": [r["key"] for r in results if r.get("ack")],
        "items": results,
        "synced_at": timezone.now().isoformat(),
        "br_ref": "BR-WRK-042",
    }


def sync_across_jobs(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/sync` — ONE batch of a day's queue, across jobs
    (`CR-187-BRC10` T-30, R45: *"Fifty items to a request, in capture order
    within an order"*).

    WHY A SECOND DOOR AND NOT A WIDER FIRST ONE
    ────────────────────────────────────────────────────────────────────────
    The per-job route (#90) is addressed by ONE job's id, so a handset whose
    fifty oldest items span eleven jobs had to send eleven requests — the
    *"thousand round trips on a weak connection"* the design's batch size
    exists to avoid. Data.txt §4: *"Across orders the sequence does not
    matter, so batches can be grouped by order."* So each item here names its
    own `work_order_id`, and the server groups them — in the order each job
    first appears, every job's items in the order they arrived — and runs
    EACH GROUP THROUGH `sync_batch`, unchanged. Same appliers, same savepoint
    per item, same receipts, same per-item answers. The per-job route is
    untouched, so the web field app's calls work exactly as before.

    ⚠ **EACH JOB IS ITS OWN TRANSACTION, AND THAT IS DELIBERATE.** One job
    that cannot be reached — another tenant's (a swapped phone, `J65` step
    13), another technician's, or a server fault mid-apply — answers each of
    its items *refused*, NOT acknowledged, so they stay in the phone's outbox;
    the other jobs in the same request still commit. One outer transaction
    over all of them would let one job's failure cost the other ten.

    The tenant is the credential's, never the payload's (R127): every order
    id is looked up under the tenant already in context, so a foreign id is a
    404 like any other.
    """
    import logging
    from uuid import UUID

    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list) or not raw_items:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.sync.no_items", br_ref="BR-WRK-042"
        )
    if len(raw_items) > MAX_ITEMS:
        # A REQUEST size, not an account cap (NFR-5): the day is sent in as
        # many requests as it takes.
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.sync.too_many_items",
            br_ref="BR-WRK-042",
            params={"sent": len(raw_items), "max": MAX_ITEMS},
        )

    groups: dict[str, list[tuple[int, Any]]] = {}
    for index, raw in enumerate(raw_items):
        item = raw if isinstance(raw, dict) else {}
        groups.setdefault(str(item.get("work_order_id") or "").strip(), []).append((index, raw))

    answers: list[dict[str, Any] | None] = [None] * len(raw_items)
    jobs: list[dict[str, Any]] = []
    for order_id, members in groups.items():
        items = [raw for _, raw in members]
        try:
            try:
                UUID(order_id)
            except ValueError:
                # No id, or not an id: nothing to look up — the same answer as
                # an id that names no job of this tenant.
                raise errors.deny_as_not_found("BR-TEN-003") from None
            # The per-job route's own gate, item group by item group: a group
            # whose every item names its captor is checked item by item
            # against that captor (BR-WRK-059); anything else must be the
            # signed-in technician's own job (DEF-WRK-9593).
            if not every_item_has_a_capture_token({"items": items}):
                mobile.require_own_job(actor, order_id)
            out = sync_batch(actor, order_id, {"items": items})
        except Exception as exc:  # noqa: BLE001 — one job never costs the others
            if not isinstance(exc, (errors.ApiError, errors.NotFoundError)):
                logging.getLogger("smartbillhub.work.sync").exception(
                    "work.sync: job %s not applied", order_id
                )
            for index, raw in members:
                item = raw if isinstance(raw, dict) else {}
                answer = _refused(str(item.get("key") or ""), str(item.get("kind") or ""),
                                  item.get("seq", index + 1), exc)
                if isinstance(exc, errors.NotFoundError):
                    answer["detail"] = {"message": "not found", "status": 404}
                elif not isinstance(exc, errors.ApiError):
                    answer["detail"] = {"message_key": "work.sync.item_not_applied"}
                answers[index] = {**answer, "work_order_id": order_id or None}
            # CR-194-BRC10 — a job of THIS utility that is no longer the
            # sender's (reassigned, with items carrying no captor): the office
            # keeps a copy of each item, each in its own savepoint. A job that
            # names nothing here (another utility's, a bad id) keeps nothing.
            if isinstance(exc, errors.NotFoundError) and _order_of_this_tenant(order_id):
                for index, raw in members:
                    if answers[index].get("key") and refused_items.keep(
                        door=refused_items.DOOR_JOB, item=raw, refusal=answers[index],
                        work_order_id=order_id, courier=actor,
                    ):
                        refused_items.mark_kept(answers[index])
            jobs.append({"work_order_id": order_id or None, "accepted": 0, "duplicate": 0,
                         "refused": len(members), "held_for_review": 0})
            continue
        for (index, _), answer in zip(members, out["items"]):
            answers[index] = {**answer, "work_order_id": order_id}
        jobs.append({key: out[key] for key in
                     ("work_order_id", "accepted", "duplicate", "refused", "held_for_review")})

    results = [answer for answer in answers if answer is not None]
    return {
        "accepted": sum(1 for r in results if r["result"] == RESULT_ACCEPTED),
        "duplicate": sum(1 for r in results if r["result"] == RESULT_DUPLICATE),
        "refused": sum(1 for r in results if r["result"] == RESULT_REFUSED),
        "held_for_review": sum(1 for r in results if r["result"] == RESULT_HELD),
        # The ACK list, as #90's: an item leaves the phone's outbox ONLY when
        # its key is here (TECHNICIAN SYNC DESIGN (1)). Keys are unique per
        # JOB, so the phone matches on (work_order_id, key).
        "acknowledged": [
            {"work_order_id": r["work_order_id"], "key": r["key"]} for r in results if r.get("ack")
        ],
        # In the order SENT, so the phone can zip its batch against it.
        "items": results,
        "jobs": jobs,
        "synced_at": timezone.now().isoformat(),
        "br_ref": "BR-WRK-042",
    }


def _order_of_this_tenant(order_id: Any) -> bool:
    from uuid import UUID

    from apps.work.seams import metering_seam

    try:
        UUID(str(order_id))
    except ValueError:
        return False
    return metering_seam.work_order_row(order_id) is not None


def pending_marker(actor: Any, order_ids: list[Any] | None = None) -> dict[str, Any]:
    """`BR-WRK-036` — what is waiting to send, counted in JOBS not items.

    *◍ offline · 3 jobs to send.* The marker counts jobs with a queued CLOSE,
    which is `US-WRK-044` TC-7 in as many words, and it is the phone's own
    number: the server can only report what it has RECEIVED. This is the
    server's half — the receipts it holds — so the handset can reconcile its
    queue against them after a half-delivered sync (`J65` step 10) instead of
    re-sending everything.
    """
    tenant_id = _tenant_id()
    query = WorkSyncReceipt.objects.filter(tenant_id=tenant_id)
    if order_ids:
        query = query.filter(work_order_id__in=order_ids)
    return {
        "keys": sorted(query.values_list("key", flat=True)),
        "closed_orders": sorted(
            str(v) for v in query.filter(kind="close").values_list("work_order_id", flat=True)
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-044@386432ab (EP-WRK-08) · 07-endpoints.md §6 #90 · 10-execution-plan.md wave L · CR-187-BRC10 T-30/T-46 (`sync_across_jobs`, the volume and savepoint proofs)
# generated: 2026-09-05 by the CR-070 wave L build lane; trailer added 2026-10-21 by CR-187-BRC10 lane S-SYNC (the file carried a Trace header and no trailer, which G1 fails)
# checklist: A✔ B✔ C✔ D✔ E✔(the web field app's per-job calls and the native field app's batch) F✔ G✔ H✔(law 14: the savepoint is proved on PostgreSQL, red without it)
# gates: pytest tests/test_us_wrk_044_046_sync.py tests/test_cr187_sync_volume.py · on PostgreSQL tests/test_us_wrk_044_sync_pg.py tests/test_cr187_sync_volume_pg.py · G78 (Work writes nothing foreign)
# exceptions: photograph BYTES are not carried here (see the module docstring) — a `photo` item declares, `PUT /work/mobile/photos/{id}` delivers · AMENDED 2026-10-21 (CR-187-BRC10, PO "back to the technician"): an item the server cannot apply is REFUSED with its reason and nothing is stored (BR-WRK-063 superseded for field items) · AMENDED 2026-10-26 (CR-194-BRC10, PO "store on both"): the server ALSO keeps the office's copy of each refused item in `work_refused_items`, in its own savepoint, never as a receipt
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
