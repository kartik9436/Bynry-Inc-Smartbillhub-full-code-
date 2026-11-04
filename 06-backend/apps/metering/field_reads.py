# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — `07-endpoints.md` N1 (*"`POST work/mobile/reads/sync`
#           — a batch of up to 50 ROUTE readings, per-item receipts, a
#           savepoint per item, idempotent on the key minted at capture"*),
#           N6 (turn-in, never a gate), N12 (the can't-read reasons).
# Story:    US-FLD-040 · US-FLD-041 · US-FLD-042 · US-FLD-059 · US-FLD-060 ·
#           US-FLD-061 · US-FLD-063 … US-FLD-066 · US-FLD-068
#           Screens: RW-09, RW-13, RW-15, RW-17, RW-18, RW-19, RW-20, RW-25,
#           RW-26, RW-27
# Rules:    BR-FLD-00080 (R80 — warned, never blocked) · BR-FLD-00081 (R81) ·
#           BR-FLD-00082 (R82) · BR-FLD-00083 (R83 — the scan decides; never a
#           guessed meter) · BR-FLD-00084 (R84) · BR-FLD-00085 (R85) ·
#           BR-FLD-00088 … 00096 · BR-WRK-063 (SUPERSEDED for field items
#           2026-10-21, PO *"back to the technician"*: what this door cannot
#           post is REFUSED with its reason and kept on the phone) · BR-MET-129 (a warned reading POSTS with its flags) ·
#           BR-MET-1189 (the same reading again is not stored twice) ·
#           CLAUDE.md hard rules 1, 3, 6, 7 · **hard-won law 14**
# Tests:    06-backend/tests/test_cr187_reads_sync.py ·
#           06-backend/tests/test_cr187_reads_pg.py (the savepoint, on real
#           PostgreSQL — the SQLite suite cannot see it)
# ───────────────────────────────────────────────────────
"""Route readings from the field app — applied once, answered per item.

A DIFFERENT DOOR, NOT A DIFFERENT PIPELINE
────────────────────────────────────────────────────────────────────────────
Every reading that becomes a `meter_reads` row gets there through the SAME
three functions every staff, file, event and customer reading uses —
`stage_read_batch` → `validate_read_batch` → `commit_read_batch` — exactly the
path `customer_reads.record_customer_read` and `commit_event_reads` take. The
sixteen VEE rules, the true-up, the collection stamps (route, account), the
same-day rule and the high-consumption notice all apply unchanged. **Nothing in
this file judges a figure.** One sync request of ≤ 50 items is ONE staged batch
— twenty batches for a 1,000-reading day, not a thousand.

⚠ **WHY `__wrapped__`, AND WHY IT IS NOT A WAY AROUND A GUARD** (the
`customer_reads` reasoning, one door over). Those three functions carry
`@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and a meter reader holds
`field_technician`. The guard for THIS door is the field app's own and it is
the stricter one: `FieldAppRole` at the edge, the reader's own routes only for
a technician (`field_routes.route_for_reader`), the tenant from the session's
path and never from the body (R127).

WHAT EACH ITEM GETS BACK — `accepted` · `duplicate` · `refused`
────────────────────────────────────────────────────────────────────────────
⚠ **SOMETHING THIS DOOR CANNOT POST GOES BACK TO THE READER — RULED
2026-10-21.** PO, verbatim: *"back to the technician"* (decision log *"Field
app: the PO corrects four of the ten answers"* item 4). **`BR-WRK-063` is
SUPERSEDED for field items, and the design's R42 / R48 / E2E-07 / RW-27 (*"1
refused — needs you"*) stand.** That settles the collision `US-FLD-042` §8
recorded, the way the design drew it. So an item the pipeline will not post —
a unit missing or not the register's, a figure below the last one (the
engine's ERROR, `pipeline_error` with its rules), a meter the reader could not
name, a different meter with no answer, an unreadable figure or time — is
answered **`refused`** with a machine `reason`, a `message_key`, and the
specifics in `detail.params`, and **NOTHING IS STORED that could later post**:
no `field_reads` row (so the key is not spent — the fixed item resent posts
once, under the same key or a new one), no proposal, no meter read. A
candidate the pipeline itself turned away had its row inserted before the
pipeline ran; that row is DELETED in the same transaction, so from outside it
never existed. The phone keeps the item and shows it to the reader to fix and
resend — the no-drop half of `BR-WRK-063` stands; the phone holds it now.

`held_for_review` stays a COUNT on the answer (always 0 from this server), and
a duplicate of an item HELD before the ruling still answers its `first` as
it was. The sync's audit row lists each refused key and reason — the
diagnostic record. ⚠ **AMENDED 2026-10-26 (PO *"store on both"*,
`CR-194-BRC10`): Work ALSO keeps the office's copy of each refused item**
(`work_refused_items`, handed over by `_keep_for_office` through
`seams.work_refused_items()`), in its own savepoint and never as a
`field_reads` row, so the key is still unspent and the refusal gains
`detail.kept_for_office: true`.

HARD-WON LAW 14 — THE SAVEPOINT IS LOAD-BEARING
────────────────────────────────────────────────────────────────────────────
Each item's receipt row is INSERTED inside its own nested
`transaction.atomic()`, and the unique `(tenant, key)` IS the duplicate check
— there is deliberately no `exists()` before it, because a cheap read that
answers *duplicate* never touches the constraint and a test of the savepoint
would then pass with the savepoint deleted (`DEF-WRK-4079`'s lesson). On
PostgreSQL a failed INSERT aborts the whole transaction unless it ran inside a
savepoint; SQLite has no such state, so only `tests/test_cr187_reads_pg.py`
can prove this. **Do not "simplify" the nested atomic away.**

The pipeline step runs inside ONE savepoint for the whole batch: if it raises,
every candidate is REFUSED back with the refusal's key and nothing the other
items stored is lost.
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.metering import field_routes, models, register_units, seams, services, validation
from apps.metering.field_read_models import (
    FIX_QUALITIES,
    IDENTIFIED_BY,
    MISMATCH_ANSWERS,
    OUTCOME_AWAITING,
    OUTCOME_HELD,
    OUTCOME_POSTED,
    OUTCOME_RECORDED,
    READER_COULD_NOT_READ,
    READER_STATUSES,
    REMARK_SOURCES,
    CantReadReason,
    FieldMeterProposal,
    FieldRead,
    FieldRouteTurnIn,
)
from core import audit as core_audit
from core import device_clock, errors
from core import tenancy as core_tenancy

#: `03-field-map.md` §4 — *"50 items per request. Not 1,000 in one (a timeout
#: loses everything and a web worker is given sixty seconds) and not 1,000
#: separate requests"*. A request over it is refused WHOLE, before anything is
#: stored, so the handset's outbox still holds every item (nothing dropped).
MAX_ITEMS = 50

#: R82 — the eight seeded reasons, in the RW-17 board's order. A SEED, not a
#: list the code consults: the screen and the sync read the tenant's rows, and
#: a test counts them.
SEED_CANT_READ_REASONS: tuple[tuple[str, str], ...] = (
    ("dog", "Dog"),
    ("locked", "Locked"),
    ("no_access", "No access"),
    ("buried_or_covered", "Buried or covered"),
    ("obstructed", "Obstructed"),
    ("meter_not_found", "Meter not found"),
    ("unsafe", "Unsafe"),
    ("illegible", "Illegible"),
)

#: The item kinds this door applies. Anything else is refused back to the
#: reader with `unknown_kind` (2026-10-21) and stays on the phone.
KIND_READING = "reading"
KIND_ADD_METER = "add_meter"
#: A route photograph's DECLARATION (`DEF-FLD-10357`): its `photo_id` and
#: `sha256`; the link is made in this item's savepoint and the bytes follow to
#: `PUT work/mobile/reads/photos/{photo_id}` (`field_read_photos.py`). Until
#: 2026-10-21 there was no such kind and a photo item was refused or held as a
#: reading with no reader status.
KIND_PHOTO = "photo"
#: A FINDING at a meter (RW-21 *Raise it*, RW-18's mismatch) — `BR-WRK-067`,
#: PO 2026-10-22. Not a reading and never stored in `field_reads`: the door
#: parses what it already knows how to parse (the position, the clock, the
#: meter, the CAPTOR) and hands the item to Work, which keeps it and lets a
#: matching rule raise its job (`apps.work.route_findings.receive`). Until
#: then the handset kept these on the phone as `route_finding` with no door.
KIND_FINDING = "finding"
#: A LATE POSITION (`DEF-MET-10633`, FB-003 — PO 2026-10-27, *"the first fix
#: within 5 minutes of saving is sent automatically as a SEPARATE fact …
#: never written as if present at save"*). Names the reading or route photo it
#: belongs to by that item's key (`for_key`), and is kept as its OWN
#: `field_reads` row of this kind, `position_for` pointing at the target — the
#: target's own `lat`/`lng` are never touched (hard rule 4's spirit). See
#: `_judge_position`; the office reads it through `field_positions.py`.
KIND_POSITION = "position"

RESULT_ACCEPTED = "accepted"
RESULT_DUPLICATE = "duplicate"
RESULT_HELD = "held_for_review"
RESULT_REFUSED = "refused"

#: Why an item was refused — machine words, the phone writes the sentence (B14
#: rule 35). One place, so a grep finds every reason a reader can meet. The
#: `HELD_` prefix is historical (these were stored and held until 2026-10-21)
#: and kept because legacy `field_reads.held_reason` rows carry these words.
#: Each is answered with `message_key = REFUSED_KEY_PREFIX + reason`.
HELD_UNKNOWN_KIND = "unknown_kind"
HELD_READER_STATUS = "reader_status_unknown"
HELD_REASON_UNKNOWN = "cant_read_reason_unknown"
HELD_VALUE_AND_REASON = "value_and_reason"
HELD_VALUE_UNREADABLE = "value_unreadable"
HELD_UNIT_MISSING = "unit_missing"
HELD_UNIT_NOT_REGISTERS = "unit_not_the_registers"
HELD_REGISTER_UNIT_UNDECLARED = "register_unit_undeclared"
HELD_CAPTURED_AT = "captured_at_unreadable"
HELD_METER_NOT_FOUND = "meter_not_found"
HELD_SCAN_AMBIGUOUS = "scan_matches_several_meters"
HELD_DIFFERENT_METER = "different_meter_unanswered"
HELD_METER_UNCERTAIN = "meter_identity_uncertain"
HELD_PLATE_PHOTO = "plate_photo_missing"
HELD_PROPOSAL_UNKNOWN = "proposal_unknown"
HELD_PROPOSAL_INCOMPLETE = "proposal_incomplete"
HELD_PIPELINE_ERROR = "pipeline_error"
HELD_PIPELINE_REFUSED = "pipeline_refused"
HELD_NOT_POSTED = "not_posted"
HELD_SERVER_ERROR = "server_error"
#: `DEF-FLD-10358` — the item's capture token does not verify, or has expired
#: (or the office signed the handset out). Expired is refused BACK, exactly as
#: the job door does: the reader signs in, the phone re-stamps and resends.
HELD_TOKEN_INVALID = "capture_token_invalid"
HELD_TOKEN_EXPIRED = "capture_token_expired"
#: `DEF-MET-10633` — a late position whose target this server never received
#: (resent once the target has arrived), one with no coordinates, one for a
#: target that already has a position, and one outside the 5 minutes after
#: the target was saved.
HELD_POSITION_TARGET_UNKNOWN = "position_target_unknown"
HELD_POSITION_MISSING = "position_missing"
HELD_POSITION_ALREADY_KNOWN = "position_already_known"
HELD_POSITION_TOO_LATE = "position_too_late"
#: `DEF-FLD-10637` (FB-019) — a photo added after its reading was saved names
#: that reading by its key (`reading_key`). Unknown: the reading has not
#: arrived (or was sent back) — resent once it has. Foreign: the key is a
#: reading of another reader or another route — never linked across.
HELD_PHOTO_READING_UNKNOWN = "photo_reading_unknown"
HELD_PHOTO_READING_FOREIGN = "photo_reading_foreign"
#: FB-022 (PO report 2026-10-31; DevOps's 500 of 29 Oct, City of Houston) — a
#: photo added to a reading (`photo_for`) or a late position for one
#: (`position_for`) whose reading the PIPELINE turned away in the same
#: request: refused with it, naming the reading and its reason, and nothing
#: of it stored. Both foreign keys are PROTECT, so the reading's row could
#: not be deleted while they pointed at it — the delete raised ProtectedError
#: outside any savepoint and the whole request answered 500, every resend.
HELD_PHOTO_READING_REFUSED = "photo_reading_refused"
HELD_POSITION_READING_REFUSED = "position_reading_refused"

#: The catalogue key a refused item names: `work.mobile.reads.<reason>`.
REFUSED_KEY_PREFIX = "work.mobile.reads."


class _SendBack(Exception):
    """Raised inside an item's savepoint when the item cannot be posted, so
    the savepoint rolls back EVERYTHING the item wrote (its row, a proposal)
    — a refused item stores nothing (2026-10-21)."""

    def __init__(self, reason: str, detail: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _refused(key: Any, position: int, reason: str, detail: Any = None) -> dict[str, Any]:
    """A refusal BACK TO THE READER (PO 2026-10-21, *"back to the technician"*):
    the machine `reason`, the catalogue `message_key`, the specifics as
    `params`. Not stored, so not acknowledged — the phone keeps the item."""
    message_key = f"{REFUSED_KEY_PREFIX}{reason}"
    return {
        "key": key,
        "position": position,
        "result": RESULT_REFUSED,
        "reason": reason,
        "message_key": message_key,
        "detail": {
            "reason": reason,
            "message_key": message_key,
            "params": _jsonable(detail) if detail else {},
            "br_ref": "BR-WRK-063",
        },
    }

#: R83 — the scan decides: *"matched serial, then badge, then device ID"*.
#: Serial is `assets.serial_no`. **Which asset field is the BADGE, and which the
#: device id, is not decided** (`03-field-map.md` §2.2: the design shows serial
#: `MTR-0471` and badge `88241` as two values; the server has `serial_no`,
#: `asset_no` and `external_ref`). Its `OQ-FLD-` id is still to be minted. So a
#: scan is matched on the serial and on the meter NUMBER the downloaded list
#: carries, and on nothing guessed to be the badge; an unmatched scan is HELD
#: (`meter_not_found`), never resolved to a plausible meter.
BADGE_FIELD_QUESTION = "OQ-FLD (to be minted): which asset field is the badge / device id"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


# ══════════════════════════════════════════════════════════════════════════
# R82 — the can't-read reasons, the utility's own list
# ══════════════════════════════════════════════════════════════════════════


def ensure_cant_read_reasons() -> int:
    """Idempotent seed of the eight for the CURRENT tenant (`is_system` rows:
    deactivatable, never deletable). Lazy, on first use — the `unit_types`
    posture — so a tenant provisioned before this change has its eight the
    first time a reader or a screen asks. A row the tenant DEACTIVATED is left
    deactivated: get-or-create never resurrects it."""
    tenant_id = _tenant_id()
    created = 0
    for order, (code, name) in enumerate(SEED_CANT_READ_REASONS, start=1):
        exists = CantReadReason.objects.filter(tenant_id=tenant_id, code__iexact=code).exists()
        if not exists:
            CantReadReason.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=name,
                sort_order=order * 10,
                is_system=True,
                active=True,
            )
            created += 1
    return created


def reason_dict(row: CantReadReason) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "sort_order": row.sort_order,
        "is_system": row.is_system,
        "active": row.active,
    }


def cant_read_reasons(*, include_inactive: bool = False) -> dict[str, Any]:
    """`GET work/mobile/cant-read-reasons` — RW-17's list, from the server.
    Active rows only unless asked; seeded first, then the utility's own."""
    ensure_cant_read_reasons()
    qs = CantReadReason.objects.filter(tenant_id=_tenant_id())
    if not include_inactive:
        qs = qs.filter(active=True)
    rows = [reason_dict(row) for row in qs.order_by("sort_order", "name", "id")]
    return {"count": len(rows), "results": rows}


def cant_read_reason_index() -> dict[str, dict[str, Any]]:
    """DEF-MET-10609 — casefolded code → `{code, name, active}` for EVERY
    reason of the tenant, switched-off ones included. Work reads it through
    `work/seams/metering_seam.py` to validate a JOB reading's reason (against
    the active ones) and to name it for the office (from any of them — a reason
    switched off since still has its words)."""
    ensure_cant_read_reasons()
    return {
        row.code.casefold(): {"code": row.code, "name": row.name, "active": row.active}
        for row in CantReadReason.objects.filter(tenant_id=_tenant_id()).order_by(
            "sort_order", "name", "id"
        )
    }


def _active_reason_codes() -> dict[str, str]:
    ensure_cant_read_reasons()
    return {
        code.casefold(): code
        for code in CantReadReason.objects.filter(tenant_id=_tenant_id(), active=True).values_list(
            "code", flat=True
        )
    }


def add_cant_read_reason(actor: Any, payload: Any) -> dict[str, Any]:
    """A utility's own reason (R82: tenant-extensible). System Admin only — the
    API applies the role; `code` unique per tenant, case-insensitive."""
    data = payload if isinstance(payload, dict) else {}
    code = _text(data.get("code"), 60)
    name = _text(data.get("name"), 120)
    fe = []
    if not code:
        fe.append(_fe("code", errors.VAL_REQUIRED, "errors.val-001"))
    if not name:
        fe.append(_fe("name", errors.VAL_REQUIRED, "errors.val-001"))
    if fe:
        raise errors.ValidationError(errors.VAL_REQUIRED, field_errors=fe)
    ensure_cant_read_reasons()
    tenant_id = _tenant_id()
    if CantReadReason.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="metering.lookups.duplicate_code",
            params={"value": code},
            field_errors=[
                _fe("code", errors.VAL_FORMAT, "metering.lookups.duplicate_code", value=code)
            ],
        )
    last = (
        CantReadReason.objects.filter(tenant_id=tenant_id).order_by("-sort_order").first()
    )
    row = CantReadReason.objects.create(
        tenant_id=tenant_id,
        code=code,
        name=name,
        sort_order=(last.sort_order if last else 0) + 10,
        is_system=False,
        active=True,
    )
    core_audit.write_row(
        action="cant_read_reason.created",
        entity_type="cant_read_reason",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        after=reason_dict(row),
    )
    return reason_dict(row)


def set_cant_read_reason_active(actor: Any, code: str, payload: Any) -> dict[str, Any]:
    """Deactivate or re-activate one reason. A seeded row is deactivatable and
    never deletable (BR-TEN-036); there is no delete door at all."""
    data = payload if isinstance(payload, dict) else {}
    if not isinstance(data.get("active"), bool):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[_fe("active", errors.VAL_REQUIRED, "errors.val-001")],
        )
    ensure_cant_read_reasons()
    row = CantReadReason.objects.filter(tenant_id=_tenant_id(), code__iexact=str(code)).first()
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    before = reason_dict(row)
    row.active = data["active"]
    row.save(update_fields=["active", "updated_at"])
    core_audit.write_row(
        action="cant_read_reason.updated",
        entity_type="cant_read_reason",
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after=reason_dict(row),
    )
    return reason_dict(row)


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


# ══════════════════════════════════════════════════════════════════════════
# The sync
# ══════════════════════════════════════════════════════════════════════════


def _decimal(raw: Any) -> Decimal | None:
    """A dial figure: non-negative, finite. Typing separators are dropped and
    never interpreted (the `customer_reads._parse_value` posture)."""
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


def _coordinate(raw: Any, bound: int) -> Decimal | None:
    """R91 — a poor or absent fix never refuses anything; an unusable number is
    simply not stored as a position (the payload keeps what was sent)."""
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not value.is_finite() or abs(value) > bound:
        return None
    return value.quantize(Decimal("0.000001"))


def _metres(lat1: Any, lng1: Any, lat2: Any, lng2: Any) -> Decimal | None:
    """R90 — great-circle distance in metres between the reader and the place
    the meter is recorded. Float arithmetic is fine here: this is a distance on
    a map, never money (hard rule 2 governs money only)."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    radius = 6371008.8
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lng2) - float(lng1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return Decimal(str(round(2 * radius * math.asin(math.sqrt(a)), 2)))


def _accuracy(raw: Any) -> Decimal | None:
    """R90 — the fix's radius in metres, as the handset reported it. A figure
    the column cannot hold (over 1,000 km is not a fix) is not stored as one."""
    value = _decimal(raw)
    if value is None or value > Decimal("1000000"):
        return None
    return value.quantize(Decimal("0.01"))


def _captured_at(raw: Any) -> datetime | None:
    """R92 — the device clock, as sent. Must carry its zone: a naive time is a
    time on an unknown clock, and guessing the zone moves a reading across a
    date boundary (BR-TEN-043's whole reason)."""
    if not raw:
        return None
    parsed = parse_datetime(str(raw).strip())
    if parsed is None or parsed.tzinfo is None:
        return None
    # FB-014 (DEF-FLD-10639, PO 2026-10-28) — moved onto the SERVER's clock by
    # the offset this request measured, so a phone running fast cannot date a
    # reading tomorrow (`core/device_clock.py`). The sync's audit row keeps
    # the phone's clock and the offset.
    return device_clock.correct(parsed)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class _Context:
    """What one sync request reads once and every item shares — the route
    meter sets (R84) and the reason codes (R82). DEF-324's one-read-per-thing."""

    def __init__(self, actor: Any) -> None:
        self.actor = actor
        self.tenant_id = _tenant_id()
        self.reasons = _active_reason_codes()
        self._route_meters: dict[str, set[str]] = {}
        self._routes: dict[str, Any] = {}
        self.tz = seams.tenant_timezone()

    def route(self, route_id: Any) -> Any:
        if not route_id or not field_routes._is_uuid(route_id):
            return None
        key = str(route_id)
        if key not in self._routes:
            self._routes[key] = models.Route.objects.filter(
                tenant_id=self.tenant_id, pk=key, deleted_at__isnull=True
            ).first()
        return self._routes[key]

    def route_meters(self, route: Any) -> set[str]:
        key = str(route.id)
        if key not in self._route_meters:
            self._route_meters[key] = field_routes.route_meter_ids(route)
        return self._route_meters[key]


def _asset_model() -> Any:
    return django_apps.get_model("assets", "Asset")


def _resolve_meter(item: dict[str, Any]) -> tuple[Any, str | None, dict[str, Any]]:
    """`(asset, held_reason, detail)` — the meter the reader READ.

    By number (`meter_no`, the downloaded list's key) first, else by the
    scanned code: serial, then meter number (R83). Never by anything guessed to
    be a badge — see `BADGE_FIELD_QUESTION`. Several meters sharing one serial
    (BR-AST-033 warns and allows that) is HELD, never resolved to one of them.
    """
    meter_no = _text(item.get("meter_no") or item.get("meter"), 80)
    if meter_no:
        asset = seams.meter_by_no(meter_no)
        if asset is None:
            return None, HELD_METER_NOT_FOUND, {"meter_no": meter_no}
        return asset, None, {}
    code = _text(item.get("scanned_code"), 120)
    if not code:
        return None, HELD_METER_NOT_FOUND, {"reason": "no_meter_named"}
    matches = list(
        _asset_model()
        .objects.filter(tenant_id=_tenant_id(), serial_no=code)
        .values_list("asset_no", flat=True)[:2]
    )
    if len(matches) > 1:
        return None, HELD_SCAN_AMBIGUOUS, {"scanned_code": code}
    if matches:
        return seams.meter_by_no(matches[0]), None, {}
    asset = seams.meter_by_no(code)
    if asset is not None:
        return asset, None, {}
    return None, HELD_METER_NOT_FOUND, {"scanned_code": code, "badge_question": BADGE_FIELD_QUESTION}


def _record_point(asset: Any) -> tuple[Any, Any]:
    """Where the meter is RECORDED — its unit's own point, else its building's
    (`BR-MET-1162`). Read by walking; nothing is stored on the meter."""
    point = getattr(asset, "service_point", None)
    unit = getattr(point, "unit", None) if point is not None else None
    if unit is not None and unit.lat is not None and unit.lng is not None:
        return unit.lat, unit.lng
    if unit is not None:
        place = models.Premises.objects.filter(tenant_id=_tenant_id(), pk=unit.premises_id).only(
            "lat", "lng"
        ).first()
        if place is not None:
            return place.lat, place.lng
    return None, None


def _base_row(ctx: _Context, item: dict[str, Any], key: str, kind: str, reader_id: Any = None) -> FieldRead:
    """The receipt row with every capture fact the item carries — stored as
    received, whatever happens next (BR-WRK-063). `reader_id` is the CAPTOR
    named by the item's capture token (`DEF-FLD-10358`); without a token, the
    signed-in caller, as before."""
    position = item.get("position") if isinstance(item.get("position"), dict) else {}
    route = ctx.route(item.get("route_id"))
    premises_id = item.get("premises_id")
    premises = (
        models.Premises.objects.filter(tenant_id=ctx.tenant_id, pk=premises_id).first()
        if premises_id and field_routes._is_uuid(premises_id)
        else None
    )
    fix = _text(position.get("fix_quality"), 20)
    identified = _text(item.get("identified_by"), 20)
    remark_source = _text(item.get("remark_source"), 20)
    photos = item.get("photos") if isinstance(item.get("photos"), list) else []
    return FieldRead(
        tenant_id=ctx.tenant_id,
        key=key,
        kind=kind,
        reader_id=reader_id if reader_id is not None else _actor_id(ctx.actor),
        route=route,
        premises=premises,
        channel=_text(item.get("register") or item.get("channel"), 40) or models.CHANNEL_TOTAL,
        value=_decimal(item.get("value")),
        unit=_text(item.get("unit"), 40),
        reader_status=_text(item.get("reader_status"), 40),
        cant_read_reason=_text(item.get("cant_read_reason"), 60),
        accepted_anyway=bool(item.get("accepted_anyway")),
        lat=_coordinate(position.get("lat"), 90),
        lng=_coordinate(position.get("lng"), 180),
        accuracy_m=_accuracy(position.get("accuracy_m")),
        fix_quality=fix if fix in FIX_QUALITIES else None,
        device_captured_at=_captured_at(item.get("captured_at")),
        identified_by=identified if identified in IDENTIFIED_BY else None,
        scanned_code=_text(item.get("scanned_code"), 120),
        mismatch_answer=_text(item.get("mismatch_answer"), 40),
        read_method=_text(item.get("read_method"), 60),
        remark=_text(item.get("remark"), 2000),
        remark_source=remark_source if remark_source in REMARK_SOURCES else None,
        photo_ids=[str(p)[:120] for p in photos][:20],
        outcome=OUTCOME_HELD,
        received_payload=_jsonable(item),
    )


def _hold(row: FieldRead, reason: str, **detail: Any) -> None:
    row.outcome = OUTCOME_HELD
    row.held_reason = reason
    row.held_detail = _jsonable(detail) if detail else None


def _judge_reading(ctx: _Context, row: FieldRead, item: dict[str, Any]) -> dict[str, Any] | None:
    """Decide what one READING item is, BEFORE anything is posted.

    Returns the staging row when the item is a candidate for `meter_reads`,
    else None with `row.outcome` set (recorded · awaiting_acceptance · held).
    Nothing here judges the FIGURE — that is the pipeline's, unchanged.
    """
    if row.reader_status not in READER_STATUSES:
        _hold(row, HELD_READER_STATUS, sent=row.reader_status)
        return None

    # ── R85 · a reading on a meter added in the field ──────────────────────
    proposal_key = _text(item.get("proposal_key"), 200)
    if proposal_key:
        proposal = FieldMeterProposal.objects.filter(
            tenant_id=ctx.tenant_id, key=proposal_key
        ).first()
        if proposal is None:
            _hold(row, HELD_PROPOSAL_UNKNOWN, proposal_key=proposal_key)
            return None
        row.proposal = proposal
        if row.reader_status == READER_COULD_NOT_READ:
            return _judge_cant_read(ctx, row, item)
        if row.value is None:
            _hold(row, HELD_VALUE_UNREADABLE, sent=_jsonable(item.get("value")))
            return None
        if not row.unit:
            _hold(row, HELD_UNIT_MISSING)
            return None
        # R85: *"It can be read immediately; it bills only once accepted."*
        # Kept here, posted by the acceptance door — never before it.
        row.outcome = OUTCOME_AWAITING
        return None

    asset, missing, detail = _resolve_meter(item)
    if asset is None:
        _hold(row, missing or HELD_METER_NOT_FOUND, **detail)
        return None
    row.asset = asset

    # ── RW-18 · the meter in front of the reader is not the one on the list ─
    expected_no = _text(item.get("expected_meter_no"), 80)
    if expected_no and expected_no != asset.asset_no:
        expected = seams.meter_by_no(expected_no)
        row.expected_asset = expected
        answer = row.mismatch_answer
        if answer not in MISMATCH_ANSWERS:
            # *"Do not guess."* A reading against an unconfirmed meter puts a
            # year of the wrong consumption on somebody's account.
            _hold(row, HELD_DIFFERENT_METER, listed=expected_no, read=asset.asset_no)
            return None
        if answer == "cannot_tell":
            # *"Photograph both plates and leave it to the office."*
            _hold(row, HELD_METER_UNCERTAIN, listed=expected_no, read=asset.asset_no)
            return None
        if not row.photo_ids:
            # RW-18: *"Photograph the plate — required"*.
            _hold(row, HELD_PLATE_PHOTO, listed=expected_no, read=asset.asset_no)
            return None

    # R90 — distance from where the meter is recorded, computed here.
    rec_lat, rec_lng = _record_point(asset)
    row.metres_from_record = _metres(row.lat, row.lng, rec_lat, rec_lng)

    # R84 — off-route is the server's own finding, against the route's CURRENT
    # meters. Accepted and marked; never refused.
    row.off_route = row.route is None or str(asset.id) not in ctx.route_meters(row.route)
    if row.premises is None:
        unit = getattr(getattr(asset, "service_point", None), "unit", None)
        if unit is not None:
            row.premises_id = unit.premises_id

    if row.reader_status == READER_COULD_NOT_READ:
        return _judge_cant_read(ctx, row, item)

    # ── a figure ───────────────────────────────────────────────────────────
    if row.value is None:
        _hold(row, HELD_VALUE_UNREADABLE, sent=_jsonable(item.get("value")))
        return None
    if not row.unit:
        # Hard rule 3: never assume. The handset always has the unit.
        _hold(row, HELD_UNIT_MISSING)
        return None
    register = register_units.register_unit(asset.unit, row.channel)
    if not register:
        _hold(row, HELD_REGISTER_UNIT_UNDECLARED, register=row.channel)
        return None
    if register_units.fold(register) != register_units.fold(row.unit):
        # DEF-WRK-4072's check, for this door: a WRONG unit is worse than a
        # bare one. Kept with the unit the reader stated; never posted.
        _hold(row, HELD_UNIT_NOT_REGISTERS, register_unit=register, stated_unit=row.unit)
        return None
    if row.device_captured_at is None:
        _hold(row, HELD_CAPTURED_AT, sent=_jsonable(item.get("captured_at")))
        return None
    if not asset.asset_no:
        _hold(row, HELD_METER_NOT_FOUND, reason="meter_has_no_number")
        return None
    read_on = row.device_captured_at.astimezone(ctx.tz).date()
    return {
        "meter_no": asset.asset_no,
        "read_at": read_on.isoformat(),
        "reading": str(row.value),
        "channel": row.channel,
        "read_method": row.read_method or "",
        "note": (row.remark or "")[:500],
    }


def _judge_cant_read(ctx: _Context, row: FieldRead, item: dict[str, Any]) -> None:
    """R82 / RW-17 — *could not read*, with the tenant's own reason. No reading
    exists and none is invented: an estimate, if any, is the office's act."""
    if row.value is not None:
        _hold(row, HELD_VALUE_AND_REASON)
        return None
    code = ctx.reasons.get((row.cant_read_reason or "").casefold())
    if code is None:
        _hold(row, HELD_REASON_UNKNOWN, sent=row.cant_read_reason)
        return None
    row.cant_read_reason = code
    row.outcome = OUTCOME_RECORDED
    return None


def _judge_add_meter(ctx: _Context, row: FieldRead, item: dict[str, Any]) -> None:
    """RW-20 — *"Send it for acceptance"*. A PENDING proposal, never an asset
    (R85). The premises is required (the address walks from it — hard rule 8)
    and so is a photograph."""
    meter = item.get("meter") if isinstance(item.get("meter"), dict) else {}
    service = _text(meter.get("service"), 40)
    missing = [
        name
        for name, ok in (
            ("premises_id", row.premises is not None),
            ("service", bool(service)),
            ("photos", bool(row.photo_ids)),
            ("badge_or_serial", bool(meter.get("badge") or meter.get("serial_no"))),
        )
        if not ok
    ]
    if service and service not in seams.enabled_service_codes():
        missing.append("service_enabled")
    if missing:
        _hold(row, HELD_PROPOSAL_INCOMPLETE, missing=missing)
        return None
    unit = None
    if meter.get("unit_id") and field_routes._is_uuid(meter.get("unit_id")):
        unit = models.Unit.objects.filter(
            tenant_id=ctx.tenant_id, pk=meter["unit_id"], premises=row.premises
        ).first()
    FieldMeterProposal.objects.create(
        tenant_id=ctx.tenant_id,
        key=row.key,
        # The CAPTOR, never the courier (`DEF-FLD-10358`).
        proposed_by_id=row.reader_id,
        route=row.route,
        premises=row.premises,
        unit=unit,
        service_code=service,
        size_class=_text(meter.get("size_class"), 40),
        badge=_text(meter.get("badge"), 120),
        serial_no=_text(meter.get("serial_no"), 120),
        unit_of_measure=_text(meter.get("unit_of_measure"), 40),
        lat=row.lat,
        lng=row.lng,
        accuracy_m=row.accuracy_m,
        photo_ids=row.photo_ids,
        remark=row.remark,
        device_captured_at=row.device_captured_at,
    )
    row.outcome = OUTCOME_AWAITING
    return None


def _judge_photo(ctx: _Context, row: FieldRead, item: dict[str, Any]) -> None:
    """`DEF-FLD-10357` — a route photograph's declaration: the link, made in
    this item's savepoint (`field_read_photos.declare`). Recorded, never a
    reading; the reading that names it carries its id in `photos`.

    `DEF-FLD-10637` (FB-019, PO report 2026-10-28): a photo added AFTER its
    reading was saved is not in that reading's `photos` — the reading had
    already gone — so its declaration names the reading by key
    (`reading_key`) and this row points at it (`photo_for`). The reading must
    be one this door holds, of the same reader and the same route; the tenant
    is the request's (hard rule 1). Anything else is sent back by name and
    nothing is linked."""
    from apps.metering import field_read_photos

    reading_key = _text(item.get("reading_key"), 200)
    if reading_key:
        target = FieldRead.objects.filter(
            tenant_id=ctx.tenant_id, key=reading_key, kind=KIND_READING
        ).first()
        if target is None:
            _hold(row, HELD_PHOTO_READING_UNKNOWN, reading_key=reading_key)
            return None
        if target.reader_id != row.reader_id or target.route_id != row.route_id:
            _hold(row, HELD_PHOTO_READING_FOREIGN, reading_key=reading_key)
            return None
        row.photo_for = target
        row.premises = target.premises
        row.asset = target.asset
    try:
        link = field_read_photos.declare(
            photo_id=item.get("photo_id"),
            sha256=item.get("sha256"),
            key=row.key,
            reader_id=row.reader_id,
            route=row.route,
            captured_at=row.device_captured_at,
        )
    except field_read_photos.DeclarationRefused as refused:
        _hold(row, refused.reason, **refused.detail)
        return None
    row.photo_ids = [str(link.photo_id)]
    row.outcome = OUTCOME_RECORDED
    return None


def _judge_position(ctx: _Context, row: FieldRead, item: dict[str, Any]) -> None:
    """`DEF-MET-10633` (FB-003) — a late position for a reading or a route
    photo saved without one. Kept as its own row; the target is not touched.

    The ruling's figures, enforced here as well as on the phone: the fix must
    be no earlier than the target's save and no more than 5 minutes after it
    (worked case: saved 18:32:48, a fix at 18:35 is kept, one at 18:38 is not).
    A second late position for the same target trips
    `uq_field_reads_one_late_position` inside this item's savepoint and is
    answered as a duplicate — the first one stands."""
    from apps.metering.field_positions import LATE_WINDOW

    position = item.get("position") if isinstance(item.get("position"), dict) else {}
    for_key = _text(item.get("for_key"), 200)
    target = (
        FieldRead.objects.filter(
            tenant_id=ctx.tenant_id, key=for_key, kind__in=(KIND_READING, KIND_PHOTO)
        ).first()
        if for_key
        else None
    )
    if target is None:
        _hold(row, HELD_POSITION_TARGET_UNKNOWN, for_key=for_key)
        return None
    fix_at = _captured_at(position.get("fix_at")) or row.device_captured_at
    if row.lat is None or row.lng is None or row.accuracy_m is None or fix_at is None:
        _hold(row, HELD_POSITION_MISSING)
        return None
    if target.lat is not None:
        _hold(row, HELD_POSITION_ALREADY_KNOWN, for_key=for_key)
        return None
    saved = target.device_captured_at
    if saved is None or fix_at < saved or fix_at - saved > LATE_WINDOW:
        _hold(
            row,
            HELD_POSITION_TOO_LATE,
            saved_at=saved.isoformat() if saved else None,
            fix_at=fix_at.isoformat(),
        )
        return None
    row.position_for = target
    # The position's own time is the FIX's, so the office can say *added at*.
    row.device_captured_at = fix_at
    row.route = row.route or target.route
    row.premises = target.premises
    row.asset = target.asset
    row.outcome = OUTCOME_RECORDED
    return None


def _receipt(row: FieldRead, result: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": row.key,
        "result": result,
        "outcome": row.outcome,
        "off_route": row.off_route,
    }
    if row.kind == KIND_PHOTO and row.photo_ids:
        from apps.metering import field_read_photos

        # Where the bytes go — answered on every receipt, a duplicate's too.
        out["photo_id"] = row.photo_ids[0]
        out["upload_url"] = field_read_photos.upload_url(row.photo_ids[0])
    if row.outcome == OUTCOME_HELD:
        out["reason"] = row.held_reason
        out["detail"] = row.held_detail
    if row.meter_read_id:
        out["meter_read_id"] = str(row.meter_read_id)
    return out


def _result_for(row: FieldRead) -> str:
    return RESULT_HELD if row.outcome == OUTCOME_HELD else RESULT_ACCEPTED


def _finding_receipt(key: str, position: int, finding: dict[str, Any], result: str) -> dict[str, Any]:
    """A finding's answer: its status as the receipt's `outcome` and the
    finding itself — so the phone can show *WO-4870* the moment a rule made
    one, or offer *Create work order* when none did (`BR-WRK-067`)."""
    return {
        "key": key,
        "position": position,
        "result": result,
        "outcome": finding.get("status"),
        "finding": finding,
    }


def _finding_asset_id(item: dict[str, Any]) -> Any:
    """The meter a finding is about, when the reader named one the system
    knows: the downloaded meter's id, else its number. A meter the phone
    added itself (RW-20, pending) is not one yet — the finding then stands on
    the stop alone, never on a guessed meter (R83)."""
    asset_id = item.get("asset_id")
    if asset_id and field_routes._is_uuid(asset_id):
        found = _asset_model().objects.filter(tenant_id=_tenant_id(), pk=asset_id).values_list(
            "id", flat=True
        ).first()
        if found is not None:
            return found
    meter_no = _text(item.get("meter_no"), 80)
    if meter_no:
        asset = seams.meter_by_no(meter_no)
        if asset is not None:
            return asset.id
    return None


def _claim_finding(
    ctx: _Context, raw: dict[str, Any], key: str, position: int, reader_id: Any, technician: Any
) -> dict[str, Any]:
    """One `finding` item, handed to Work inside its own SAVEPOINT (law 14).

    Refused back to the reader — nothing stored — for an unknown kind or
    urgency, or a finding that names neither the stop nor a meter."""
    work_findings = seams.work_route_findings()
    position_block = raw.get("position") if isinstance(raw.get("position"), dict) else {}
    premises_id = raw.get("premises_id")
    if premises_id and not (
        field_routes._is_uuid(premises_id)
        and models.Premises.objects.filter(tenant_id=ctx.tenant_id, pk=premises_id).exists()
    ):
        premises_id = None
    route = ctx.route(raw.get("route_id"))
    photos = raw.get("photos") if isinstance(raw.get("photos"), list) else []
    detail = {
        name: _text(raw.get(name), 120)
        for name in ("mismatch", "scanned_code", "listed_meter_no", "scanned_meter_no")
        if _text(raw.get(name), 120)
    }
    if reader_id is None:
        reader_id = _actor_id(ctx.actor)
    if technician is None:
        technician = seams.field_technician_of(ctx.actor)
    try:
        with transaction.atomic():
            finding, duplicate = work_findings.receive(
                ctx.actor,
                key=key,
                kind=raw.get("finding") or raw.get("finding_kind"),
                urgency=raw.get("urgency"),
                note=raw.get("remark"),
                note_source=raw.get("remark_source"),
                detail=detail,
                photo_ids=photos,
                route_id=route.id if route is not None else None,
                premises_id=premises_id,
                asset_id=_finding_asset_id(raw),
                lat=_coordinate(position_block.get("lat"), 90),
                lng=_coordinate(position_block.get("lng"), 180),
                accuracy_m=_accuracy(position_block.get("accuracy_m")),
                captured_at=_captured_at(raw.get("captured_at")),
                captor_id=reader_id,
                captor_technician_id=getattr(technician, "id", None),
                payload=_jsonable(raw),
            )
    except work_findings.FindingRefused as refused:
        return _refused(key, position, refused.reason, refused.detail)
    except Exception as exc:  # noqa: BLE001 — never dropped: the phone keeps it
        stored = work_findings.stored_finding(key)
        if stored is not None:
            return _finding_receipt(key, position, stored, RESULT_DUPLICATE)
        return _refused(key, position, HELD_SERVER_ERROR, {"error": type(exc).__name__})
    return _finding_receipt(key, position, finding, RESULT_DUPLICATE if duplicate else RESULT_ACCEPTED)


def _claim(ctx: _Context, raw: Any, position: int) -> tuple[FieldRead | None, dict[str, Any], dict | None]:
    """One item: judged, then its receipt row INSERTED, inside its own SAVEPOINT.

    Returns `(row, receipt, staging_row)`. `row` is None for a duplicate or a
    refusal. The staging row is what the pipeline step will post.
    """
    if not isinstance(raw, dict):
        return None, _refused(None, position, "item_not_an_object"), None
    key = _text(raw.get("key"), 200)
    if not key:
        # Hard rule 6 — an item with no key cannot be stored once and only
        # once. It stays in the handset's outbox; nothing is dropped.
        return None, _refused(None, position, "key_required"), None
    kind = _text(raw.get("kind"), 40) or KIND_READING
    # ── WHO captured it (`DEF-FLD-10358`, the job door's rule `BR-WRK-059`):
    # the item's capture token names the CAPTOR; the request names only the
    # courier. A token that does not verify is refused outright; an EXPIRED one
    # (or a handset signed out) still names its reader — a replay of a key
    # already stored is a duplicate, anything else is refused back to be
    # re-stamped. No token: the caller, as before (the web, older builds).
    reader_id = None
    technician = None
    token = raw.get("capture_token")
    if token:
        try:
            captor, technician = seams.field_captor_from_token(str(token))
            reader_id = _actor_id(captor)
        except errors.AuthError as exc:
            if getattr(exc, "message_key", "") != "work.mobile.capture_token_expired":
                return None, _refused(key, position, HELD_TOKEN_INVALID), None
            if kind == KIND_FINDING:
                first_finding = seams.work_route_findings().stored_finding(key)
                if first_finding is not None:
                    return None, _finding_receipt(key, position, first_finding, RESULT_DUPLICATE), None
                return None, _refused(key, position, HELD_TOKEN_EXPIRED), None
            if FieldRead.objects.filter(tenant_id=ctx.tenant_id, key=key).exists():
                first = FieldRead.objects.filter(tenant_id=ctx.tenant_id, key=key).first()
                return None, {"key": key, "position": position, "result": RESULT_DUPLICATE,
                              "first": _receipt(first, _result_for(first))}, None
            return None, _refused(key, position, HELD_TOKEN_EXPIRED), None
    if kind == KIND_FINDING:
        return None, _claim_finding(ctx, raw, key, position, reader_id, technician), None
    staging: dict[str, Any] | None = None
    try:
        # ⚠ HARD-WON LAW 14 — this nested atomic() is a SAVEPOINT and it is
        # load-bearing. See the module docstring before touching it.
        with transaction.atomic():
            row = _base_row(ctx, raw, key, kind, reader_id)
            if kind == KIND_READING:
                staging = _judge_reading(ctx, row, raw)
            elif kind == KIND_ADD_METER:
                _judge_add_meter(ctx, row, raw)
            elif kind == KIND_PHOTO:
                _judge_photo(ctx, row, raw)
            elif kind == KIND_POSITION:
                _judge_position(ctx, row, raw)
            else:
                _hold(row, HELD_UNKNOWN_KIND, kind=kind)
            if row.held_reason:
                # Back to the reader (2026-10-21): roll the savepoint back so
                # nothing this item judged into being survives.
                raise _SendBack(row.held_reason or HELD_NOT_POSTED, row.held_detail)
            row.save(force_insert=True)
    except _SendBack as back:
        # A replay of a key ALREADY stored is still a duplicate, whatever the
        # resend now looks like — the key is the identity (hard rule 6).
        first = FieldRead.objects.filter(tenant_id=ctx.tenant_id, key=key).first()
        if first is not None:
            return None, {"key": key, "position": position, "result": RESULT_DUPLICATE,
                          "first": _receipt(first, _result_for(first))}, None
        return None, _refused(key, position, back.reason, back.detail), None
    except IntegrityError:
        first = FieldRead.objects.filter(tenant_id=ctx.tenant_id, key=key).first()
        receipt = {"key": key, "position": position, "result": RESULT_DUPLICATE}
        if first is not None:
            receipt["first"] = _receipt(first, _result_for(first))
        return None, receipt, None
    except Exception as exc:  # noqa: BLE001 — never dropped: the phone keeps it
        # The server could not even judge it. Refused back (2026-10-21) with
        # the error's NAME only; the savepoint stored nothing, so a resend
        # after the fix is judged afresh.
        # ⚠ LAW 14: this read is what makes a POISONED transaction (no
        # savepoint) raise here rather than be answered *refused* item after
        # item and then silently rolled back at COMMIT. Do not remove it.
        if FieldRead.objects.filter(tenant_id=ctx.tenant_id, key=key).exists():
            return None, {"key": key, "position": position, "result": RESULT_DUPLICATE}, None
        return None, _refused(key, position, HELD_SERVER_ERROR, {"error": type(exc).__name__}), None
    receipt = _receipt(row, _result_for(row))
    receipt["position"] = position
    return row, receipt, staging


def _post_candidates(ctx: _Context, candidates: list[tuple[FieldRead, dict[str, Any]]]) -> None:
    """The ONE pipeline call for the request's postable items — stage →
    validate → (mechanical dispositions) → commit, exactly the customer-read
    door's sequence. Runs inside ONE savepoint; if anything in it raises, every
    candidate is HELD with the refusal's key and the receipts stored before it
    survive (law 14)."""
    if not candidates:
        return
    actor = ctx.actor
    rows_payload = [staging for _row, staging in candidates]
    first_day = min(staging["read_at"] for staging in rows_payload)
    try:
        with transaction.atomic():
            staged = services.stage_read_batch.__wrapped__(
                actor,
                {
                    "source_kind": "manual",
                    "period_month": first_day,
                    "rows": rows_payload,
                    "session_ref": "field_app_route_reads",
                },
            )
            batch = services._batch_row(staged["id"])
            services.validate_read_batch.__wrapped__(actor, batch.id)
            staged_rows = {
                row.row_no: row
                for row in models.ReadImportRow.objects.filter(
                    tenant_id=ctx.tenant_id, batch=batch
                )
            }
            already: dict[int, str | None] = {}
            for index, (field_row, _staging) in enumerate(candidates, start=1):
                staged_row = staged_rows.get(index)
                if staged_row is None:  # pragma: no cover — one staged row per item
                    _hold(field_row, HELD_NOT_POSTED)
                    continue
                if services._is_already_recorded(staged_row):
                    # BR-MET-1189 (4) — the very same reading is already on
                    # file: not stored twice, and not a refusal either.
                    already[index] = services._already_recorded_id(staged_row)
                    services.set_row_disposition.__wrapped__(
                        actor,
                        batch.id,
                        index,
                        {
                            "disposition": "reject",
                            "reason": "BR-MET-1189: the same reading is already in the register",
                        },
                    )
                elif staged_row.severity == validation.ERROR and _only_lower_than_last(
                    staged_row
                ):
                    # FB-022 — PO 2026-10-31 (decision log *"FB-022: a lower
                    # reading is warned, never refused"*), verbatim: *"if the
                    # current reading is less than previous reading it shows
                    # warning to technician , but do not refuse the reading
                    # accept"*. A field reading whose ONLY error is BR-MET-052's
                    # `negative_usage` POSTS with that flag and its consumption
                    # left empty (the engine never invents one, BR-MET-052).
                    # Its status is `negative_usage`, which is in billing's own
                    # `UNBILLABLE_READ_STATUSES`, so it does NOT bill until a
                    # clerk corrects it (PO R1 A, the same day): billing meets
                    # the meter as having no usable reading. Any OTHER error
                    # still refuses the row, below. Field door only — an office
                    # file keeps BR-MET-052's resolve-before-post.
                    services.set_row_disposition.__wrapped__(
                        actor,
                        batch.id,
                        index,
                        {
                            "disposition": "accept_with_flag",
                            "reason": (
                                "FB-022 (PO 2026-10-31): a field reading lower than the "
                                "last is stored with its flag and does not bill until a "
                                "clerk corrects it"
                            ),
                        },
                    )
                elif staged_row.severity == validation.ERROR:
                    rules = [
                        {"rule": o.get("rule"), "detail": o.get("detail")}
                        for o in (staged_row.rule_outcomes or [])
                        if o.get("severity") == validation.ERROR
                    ]
                    _hold(field_row, HELD_PIPELINE_ERROR, rules=rules)
                    services.set_row_disposition.__wrapped__(
                        actor,
                        batch.id,
                        index,
                        {
                            "disposition": "reject",
                            "reason": (
                                "BR-WRK-063 as superseded 2026-10-21: a field reading the "
                                "pipeline will not post is refused back to the reader"
                            ),
                        },
                    )
                elif staged_row.severity == validation.WARNING:
                    # BR-MET-129 (1) / R80 — a warned reading POSTS with its
                    # flags. Mechanical: the ruling's own clause, not a person.
                    services.set_row_disposition.__wrapped__(
                        actor,
                        batch.id,
                        index,
                        {
                            "disposition": "accept_with_flag",
                            "reason": (
                                "BR-FLD-00080: a field reading is warned, never blocked; "
                                "it posts with its flags for the office"
                            ),
                        },
                    )
            services.commit_read_batch.__wrapped__(
                actor, batch.id, {"certified": True}, defer=False
            )
            posted = {
                row.row_no: row.meter_read_id
                for row in models.ReadImportRow.objects.filter(
                    tenant_id=ctx.tenant_id, batch=batch
                )
            }
            for index, (field_row, _staging) in enumerate(candidates, start=1):
                field_row.read_import_batch_id = batch.id
                if field_row.outcome == OUTCOME_HELD and field_row.held_reason:
                    continue
                if index in already:
                    field_row.outcome = OUTCOME_POSTED
                    field_row.meter_read_id = already[index]
                    field_row.held_detail = {"already_recorded": True}
                elif posted.get(index):
                    field_row.outcome = OUTCOME_POSTED
                    field_row.meter_read_id = posted[index]
                else:
                    _hold(field_row, HELD_NOT_POSTED)
                field_row.save()
            for field_row, _staging in candidates:
                if field_row.outcome == OUTCOME_HELD:
                    field_row.save()
    except errors.ApiError as exc:
        _hold_all(candidates, HELD_PIPELINE_REFUSED, message_key=getattr(exc, "message_key", None))
    except Exception as exc:  # noqa: BLE001 — refused back, never dropped
        _hold_all(candidates, HELD_PIPELINE_REFUSED, error=type(exc).__name__)


def _only_lower_than_last(staged_row: Any) -> bool:
    """FB-022 — the row's errors are BR-MET-052's `negative_usage` and nothing
    else: the figure is below the meter's last one and the engine found no
    other fault. A row with no error rule named is not this (never guessed)."""
    rules = {
        o.get("rule")
        for o in (staged_row.rule_outcomes or [])
        if o.get("severity") == validation.ERROR
    }
    return rules == {validation.RULE_NEGATIVE_USAGE}


def _hold_all(candidates: list[tuple[FieldRead, dict[str, Any]]], reason: str, **detail: Any) -> None:
    for field_row, _staging in candidates:
        _hold(field_row, reason, **detail)
        field_row.meter_read_id = None
        field_row.read_import_batch_id = None
        field_row.save()


def _refuse_dependents(
    ctx: _Context, reading: FieldRead, reason: str, receipts: list[dict[str, Any]]
) -> None:
    """FB-022 — before a refused reading's row is deleted, every row that
    points at it through a PROTECT key goes with it: a photo added to it
    (`photo_for`, FB-019) and a late position for it (`position_for`,
    DEF-MET-10633). Each is deleted in the same transaction — a photo's
    still-pending link too, so no upload address is left for bytes that will
    never come — and its receipt becomes a refusal naming the reading and the
    reading's reason. Nothing is stored and nothing acknowledged, so the phone
    keeps both and the replay gets the same answer (hard rule 6)."""
    from apps.metering.field_read_models import FieldReadPhoto

    dependents = list(
        FieldRead.objects.filter(tenant_id=ctx.tenant_id, photo_for=reading)
    ) + list(FieldRead.objects.filter(tenant_id=ctx.tenant_id, position_for=reading))
    if not dependents:
        return
    at_of = {r.get("key"): i for i, r in enumerate(receipts) if r.get("key")}
    for dep in dependents:
        own = (
            HELD_PHOTO_READING_REFUSED
            if dep.photo_for_id == reading.pk
            else HELD_POSITION_READING_REFUSED
        )
        if dep.kind == KIND_PHOTO:
            FieldReadPhoto.objects.filter(
                tenant_id=ctx.tenant_id, key=dep.key, state="pending"
            ).delete()
        FieldRead.objects.filter(tenant_id=ctx.tenant_id, pk=dep.pk).delete()
        at = at_of.get(dep.key)
        if at is not None:
            receipts[at] = _refused(
                dep.key,
                receipts[at]["position"],
                own,
                {"reading_key": reading.key, "reading_reason": reason},
            )


def sync_reads(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST work/mobile/reads/sync` — up to `MAX_ITEMS` route items, in the
    order captured, each answered on its own.

    Payload::

        {"items": [
          {"key": "<minted on the handset>",          # hard rule 6
           "kind": "reading",                           # | "add_meter"
           "route_id": "<uuid>", "premises_id": "<uuid>",
           "meter_no": "MTR-0471" | "scanned_code": "…",
           "expected_meter_no"?: "MTR-0471",            # RW-18
           "mismatch_answer"?: "swapped" | "cannot_tell",
           "identified_by": "scan" | "typed" | "listed",
           "register"?: "total",
           "reader_status": "read" | "could_not_read" | "read_with_problem",
           "value"?: "52410", "unit"?: "gal",          # hard rule 3
           "cant_read_reason"?: "dog",                  # R82
           "accepted_anyway"?: true,                    # R80
           "position"?: {"lat", "lng", "accuracy_m", "fix_quality"},
           "captured_at": "2026-10-20T10:42:18-05:00",  # device clock (R92)
           "remark"?: "…", "remark_source"?: "voice" | "typed",
           "photos"?: ["<photo id>", …],
           "read_method"?: "<tenant read-method code>",
           "proposal_key"?: "<key of an add_meter item>",
           "read_format_version_id"?: "<uuid>",          # MQ-033
           "answers"?: [{"question_key": "seal_intact",
                         "value": true | "photo_id": "<uuid>"}, …]}, …]}

    MQ-033 (`CR-192-BRC10`): a reading's answers to the utility's read format
    travel inside its own item; its receipt then carries `answers: {version_id,
    stored, needs_review, issues: [{question_key, issue}], work: [...]}`. A
    bad answer is stored and flagged — it never changes the reading's result.

    A `position` item (`DEF-MET-10633`, FB-003) carries `for_key` (the
    reading's or route photo's own key), `for_kind`, and `position: {lat, lng,
    accuracy_m, fix_at}` — a fix that arrived within 5 minutes AFTER that item
    was saved without one. It is kept as its own row (`outcome: recorded`).

    A `photo` item (`DEF-FLD-10357`) carries `photo_id` and `sha256`, and —
    for a photo added after its reading was saved (`DEF-FLD-10637`, FB-019) —
    `reading_key`, that reading's own key; it is linked to the reading
    (`photo_for`), or sent back `photo_reading_unknown` /
    `photo_reading_foreign`.

    A `finding` item (`BR-WRK-067`) carries `finding` (the kind), `urgency`,
    `remark`, `premises_id`, `asset_id` or `meter_no`, `photos`, `position`,
    `captured_at` and, for RW-18, `mismatch` / `scanned_code`; its receipt
    carries `finding` — open, or the job a rule made.

    Returns `{received, accepted, duplicate, held_for_review, refused,
    server_time, items: [{key, position, result, outcome, …}]}` — one answer
    per item, in the order sent (never re-sorted).
    """
    data = payload if isinstance(payload, dict) else {}
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.sync.no_items",
            field_errors=[_fe("items", errors.VAL_REQUIRED, "work.sync.no_items")],
        )
    if len(items) > MAX_ITEMS:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.sync.too_many_items",
            params={"sent": len(items), "max": MAX_ITEMS},
            field_errors=[
                _fe("items", errors.VAL_RANGE, "work.sync.too_many_items",
                    sent=len(items), max=MAX_ITEMS)
            ],
        )
    ctx = _Context(actor)
    receipts: list[dict[str, Any]] = []
    candidates: list[tuple[FieldRead, dict[str, Any], int]] = []
    #: MQ-033 — every STORED reading row with the item it came from, so its
    #: read-format answers are judged once the engine has spoken.
    stored: list[tuple[FieldRead, dict[str, Any], int]] = []
    with transaction.atomic():
        for position, raw in enumerate(items, start=1):
            row, receipt, staging = _claim(ctx, raw, position)
            receipts.append(receipt)
            if row is not None and staging is not None:
                candidates.append((row, staging, len(receipts) - 1))
            if row is not None and row.kind == KIND_READING:
                stored.append((row, raw, len(receipts) - 1))
        _post_candidates(ctx, [(row, staging) for row, staging, _ in candidates])
        flagged = _engine_verdicts([row for row, _s, _i in candidates])
        for row, _staging, at in candidates:
            # ⚠ `held_reason`, NOT `outcome == held`: every row is BUILT with
            # outcome `held` (`_base_row`) until something decides otherwise,
            # so the outcome alone cannot tell a refusal from a candidate.
            if row.outcome == OUTCOME_HELD and row.held_reason:
                # The PIPELINE turned it away (an engine ERROR such as a figure
                # below the last one, or the pipeline refusing the batch). Its
                # row was inserted before the pipeline ran; it is deleted here,
                # in the same transaction, so nothing is stored that could
                # later post and the key is not spent (2026-10-21).
                reason, detail = row.held_reason or HELD_NOT_POSTED, row.held_detail
                _refuse_dependents(ctx, row, reason, receipts)
                FieldRead.objects.filter(tenant_id=ctx.tenant_id, pk=row.pk).delete()
                receipts[at] = _refused(row.key, receipts[at]["position"], reason, detail)
                continue
            receipt = _receipt(row, _result_for(row))
            receipt["position"] = receipts[at]["position"]
            if row.meter_read_id and str(row.meter_read_id) in flagged:
                receipt["engine"] = flagged[str(row.meter_read_id)]
            receipts[at] = receipt
        _record_answers(ctx, stored, receipts, flagged)
        # A duplicate INSIDE this request was answered before the pipeline ran,
        # so its `first` is re-read now — the answer the first copy finally got.
        repeated = [r for r in receipts if r["result"] == RESULT_DUPLICATE and r.get("key")]
        if repeated:
            firsts = {
                row.key: row
                for row in FieldRead.objects.filter(
                    tenant_id=ctx.tenant_id, key__in=[r["key"] for r in repeated]
                )
            }
            refused_now = {
                r["key"]: r for r in receipts if r["result"] == RESULT_REFUSED and r.get("key")
            }
            for at, receipt in enumerate(receipts):
                if receipt not in repeated:
                    continue
                if receipt["key"] in firsts:
                    first = firsts[receipt["key"]]
                    receipt["first"] = _receipt(first, _result_for(first))
                elif receipt["key"] in refused_now:
                    # The first copy in THIS request was refused and its row
                    # deleted; the second copy is refused with it, never
                    # answered *duplicate* over nothing stored.
                    copy = refused_now[receipt["key"]]
                    receipts[at] = _refused(
                        receipt["key"], receipt["position"], copy["reason"],
                        copy["detail"].get("params"),
                    )
        _keep_for_office(actor, items, receipts)
        counts = {
            result: sum(1 for r in receipts if r["result"] == result)
            for result in (RESULT_ACCEPTED, RESULT_DUPLICATE, RESULT_HELD, RESULT_REFUSED)
        }
        core_audit.write_row(
            action="field_reads.synced",
            entity_type="field_reads_sync",
            entity_id=_actor_id(actor),
            actor_user_id=_actor_id(actor),
            after={
                **counts,
                "received": len(items),
                # The diagnostic record of what went back to the reader; the
                # office's copy is Work's `work_refused_items` (2026-10-26).
                "refused_items": [
                    {"key": r.get("key"), "reason": r.get("reason")}
                    for r in receipts
                    if r["result"] == RESULT_REFUSED
                ],
                # FB-014 — the phone's clock at send and the shift every
                # reading's time took (original = stored − clock_offset_s).
                **device_clock.audit_fields(),
                "br_ref": "BR-WRK-042 · BR-WRK-063",
            },
        )
    return {
        "received": len(items),
        **counts,
        "server_time": timezone.now().isoformat(),
        "items": receipts,
    }


def _keep_for_office(actor: Any, items: list[Any], receipts: list[dict[str, Any]]) -> None:
    """CR-194-BRC10 (PO 2026-10-26, *"store on both"*) — the office's COPY of
    every item this request refused, and the copy of an earlier refusal closed
    when its key has now been stored.

    ⚠ **METERING WRITES NOTHING OF WORK'S.** The copy is Work's table
    (`work_refused_items`); the item is handed to `apps.work.refused_items`
    through `seams.work_refused_items()` — the `work_route_findings` precedent
    — and Work writes its own row. ⚠ **LAW 14:** `keep` runs in its own
    savepoint and never raises, and the close below is wrapped the same way, so
    a copy that cannot be written costs the reader nothing but the
    `kept_for_office` flag on the refusal. Called once every receipt is FINAL
    (after the pipeline), so a candidate the pipeline turned away is copied as
    refused and never closed."""
    keeper = seams.work_refused_items()
    for at, receipt in enumerate(receipts):
        key = receipt.get("key")
        if not key or at >= len(items):
            continue
        if receipt.get("result") == RESULT_REFUSED:
            if keeper.keep(door=keeper.DOOR_READS, item=items[at], refusal=receipt, courier=actor):
                keeper.mark_kept(receipt)
        elif receipt.get("result") in (RESULT_ACCEPTED, RESULT_HELD):
            try:
                with transaction.atomic():
                    keeper.close_applied(key=str(key), door=keeper.DOOR_READS)
            except Exception:  # noqa: BLE001 — closing the office's copy never costs the reading
                import logging

                logging.getLogger("smartbillhub.metering.field_reads").exception(
                    "field_reads: office copy of %s not closed", key
                )


#: MQ-033 — the engine rules whose warning makes a reading *out of range*
#: for a read-format question asked `out_of_range`.
OUT_OF_RANGE_RULES = frozenset({validation.RULE_HIGH, validation.RULE_LOW, validation.RULE_ZERO})


def _record_answers(
    ctx: _Context,
    stored: list[tuple[FieldRead, dict[str, Any], int]],
    receipts: list[dict[str, Any]],
    verdicts: dict[str, dict[str, Any]],
) -> None:
    """MQ-033 (`CR-192-BRC10`, `BR-MET-1215`/`1216`) — each stored reading's
    read-format ANSWERS, judged against the version the item names, AFTER the
    reading itself was judged and posted, so nothing here can change whether
    a reading posts. PO, verbatim: answers *"never cause a reading to be
    dropped (stored and flagged instead)"*.

    ⚠ HARD-WON LAW 14 — each reading's answers are stored in their OWN
    SAVEPOINT. A failure there rolls back that reading's answers only; the
    reading stays as posted, is marked `answers_need_review`, and its answers
    survive verbatim in `received_payload`. Without the savepoint one bad
    answer would poison the whole request on PostgreSQL —
    `tests/test_mq033_read_answers_pg.py` proves it."""
    from apps.metering import read_formats

    live = [
        (row, raw, at)
        for row, raw, at in stored
        if receipts[at].get("result") in (RESULT_ACCEPTED, RESULT_HELD)
    ]
    if not live:
        return
    answer_ctx = read_formats.AnswerContext()
    read_formats.plan_stop_answers(answer_ctx, [(row, raw) for row, raw, _at in live], ctx.tz)
    for row, raw, at in live:
        verdict = verdicts.get(str(row.meter_read_id)) if row.meter_read_id else None
        # "Out of range" is the engine's RANGE verdict — high, low or zero
        # against the expected consumption (R78) — or the reader's accepted-
        # anyway (R80). Not every flag: a vacant unit is not out of range.
        engine_flagged = bool(row.accepted_anyway) or bool(
            verdict and set(verdict.get("flags") or ()) & OUT_OF_RANGE_RULES
        )
        try:
            # ⚠ LAW 14 — load-bearing savepoint; see the docstring.
            with transaction.atomic():
                block = read_formats.record_answers(
                    ctx.actor, answer_ctx, row, raw, engine_flagged=engine_flagged, tz=ctx.tz
                )
        except Exception as exc:  # noqa: BLE001 — the reading is kept; flagged
            FieldRead.objects.filter(tenant_id=ctx.tenant_id, pk=row.pk).update(
                answers_need_review=True
            )
            block = {
                "version_id": None,
                "stored": 0,
                "needs_review": True,
                "issues": [{"question_key": None, "issue": HELD_SERVER_ERROR,
                            "error": type(exc).__name__}],
                "work": [],
            }
        if block is not None:
            receipts[at]["answers"] = block


def _engine_verdicts(rows: list[FieldRead]) -> dict[str, dict[str, Any]]:
    """R96 — the ENGINE's verdict on each posted reading, beside (never merged
    with) the reader's status: `{status, consumption, unit, flags}`."""
    ids = [row.meter_read_id for row in rows if row.meter_read_id]
    if not ids:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for read in models.MeterRead.objects.filter(tenant_id=_tenant_id(), id__in=ids).only(
        "id", "status", "consumption", "unit", "rule_outcomes"
    ):
        out[str(read.id)] = {
            "status": read.status,
            "consumption": str(read.consumption) if read.consumption is not None else None,
            "unit": read.unit,  # hard rule 3
            "flags": [
                o.get("rule")
                for o in (read.rule_outcomes or [])
                if o.get("severity") == validation.WARNING
            ],
        }
    return out


# ══════════════════════════════════════════════════════════════════════════
# Turn-in — RW-25 … RW-27, never a gate
# ══════════════════════════════════════════════════════════════════════════


def turn_in(actor: Any, route_id: Any, payload: Any) -> dict[str, Any]:
    """`POST work/mobile/routes/{id}/turn-in` — *"Turning in does not close the
    cycle. The office chases whatever is missing, and a route can be handed
    back to you tomorrow."* Always answered; never refused for what is missing.

    Payload: `{"key", "keys"?: [every item key the handset captured on this
    route], "counts"?: {…the handset's own}, "captured_at"?}`.

    The receipt is the SERVER's account, recomputed from `field_reads` every
    time: what LANDED (posted readings, recorded reasons, flagged, held,
    awaiting acceptance, off-route), which of the handset's keys never reached
    the server (`not_received` — send those first), and how many of the route's
    meters nobody has read in the window (`never_read`), which is the office's
    chase list. Idempotent on `key`: a second turn-in answers the same row.
    """
    route = field_routes.route_for_reader(actor, route_id)
    data = payload if isinstance(payload, dict) else {}
    key = _text(data.get("key"), 200)
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            field_errors=[_fe("key", errors.VAL_REQUIRED, "work.sync.item_key_required")],
        )
    today = seams.tenant_today()
    window = field_routes.window_for(route, today)
    try:
        with transaction.atomic():
            record = FieldRouteTurnIn.objects.create(
                tenant_id=_tenant_id(),
                key=key,
                route=route,
                reader_id=_actor_id(actor),
                period_start=window[0] if window else None,
                period_end=window[1] if window else None,
                handset_counts=_jsonable(data.get("counts") or {}),
                device_captured_at=_captured_at(data.get("captured_at")),
            )
            core_audit.write_row(
                action="field_route.turned_in",
                entity_type="route",
                entity_id=route.id,
                actor_user_id=_actor_id(actor),
                after={"key": key, "handset_counts": record.handset_counts},
            )
    except IntegrityError:
        record = FieldRouteTurnIn.objects.get(tenant_id=_tenant_id(), key=key)

    mine = FieldRead.objects.filter(tenant_id=_tenant_id(), route=route, reader_id=_actor_id(actor))
    everyone = FieldRead.objects.filter(tenant_id=_tenant_id(), route=route)
    if window:
        mine = mine.filter(received_at__date__gte=window[0], received_at__date__lte=window[1])
        everyone = everyone.filter(
            received_at__date__gte=window[0], received_at__date__lte=window[1]
        )
    else:
        mine = mine.filter(received_at__date=today)
        everyone = everyone.filter(received_at__date=today)
    rows = list(
        mine.only(
            "key", "outcome", "held_reason", "accepted_anyway", "off_route", "meter_read_id",
            "asset_id",
        )
    )
    verdicts = _engine_verdicts(rows)
    landed = {
        "readings": sum(1 for r in rows if r.outcome == OUTCOME_POSTED),
        "with_reason": sum(1 for r in rows if r.outcome == OUTCOME_RECORDED),
        "flagged": sum(
            1
            for r in rows
            if r.outcome == OUTCOME_POSTED
            and (
                r.accepted_anyway
                or (verdicts.get(str(r.meter_read_id), {}).get("status") not in (None, "ok"))
            )
        ),
        # R80 — the READER's flag (seen twice, taken anyway), kept apart from
        # the engine's (`flagged` above counts either) — R96, never merged.
        "accepted_anyway": sum(
            1 for r in rows if r.outcome == OUTCOME_POSTED and r.accepted_anyway
        ),
        "awaiting_acceptance": sum(1 for r in rows if r.outcome == OUTCOME_AWAITING),
        "off_route": sum(1 for r in rows if r.off_route),
    }
    held = [
        {"key": r.key, "reason": r.held_reason} for r in rows if r.outcome == OUTCOME_HELD
    ]
    sent_keys = data.get("keys") if isinstance(data.get("keys"), list) else []
    known = set(
        FieldRead.objects.filter(
            tenant_id=_tenant_id(), key__in=[str(k) for k in sent_keys]
        ).values_list("key", flat=True)
    ) if sent_keys else set()
    not_received = [str(k) for k in sent_keys if str(k) not in known]
    read_meters = {
        str(a) for a in everyone.exclude(asset_id__isnull=True).values_list("asset_id", flat=True)
    }
    route_meters = field_routes.route_meter_ids(route)
    never = route_meters - read_meters
    return {
        "route_id": str(route.id),
        "turned_in_at": record.received_at.isoformat(),
        "window": (
            {"start": window[0].isoformat(), "end": window[1].isoformat()} if window else None
        ),
        # Turning in closes nothing (RW-25): the read window and the cycle are
        # exactly as they were.
        "closes_cycle": False,
        "landed": landed,
        "held": {"count": len(held), "items": held},
        "not_received": {"count": len(not_received), "keys": not_received},
        "never_read": {"meters": len(never), "of": len(route_meters)},
    }


__all__ = [
    "MAX_ITEMS",
    "SEED_CANT_READ_REASONS",
    "add_cant_read_reason",
    "cant_read_reasons",
    "ensure_cant_read_reasons",
    "set_cant_read_reason_active",
    "sync_reads",
    "turn_in",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-040@fa5746815 (CR-187-BRC10 route-reading server lane — 07-endpoints.md N1, N6, N12)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the native app lanes build RW-09…RW-27) F✔ G✔ H=deferred(PO 2026-08-09 — idempotency keys are a 🔒 path, HUMAN-REVIEW-PENDING; ledger row owed by the coordinator)
# gates: see the lane report
# exceptions: AMENDED 2026-10-21 — an item this door cannot post is REFUSED back to the reader with its reason and nothing is stored (PO "back to the technician"; BR-WRK-063 superseded for field items, which settles the US-FLD-042 §8 collision the design's way) · AMENDED 2026-10-26 (CR-194-BRC10, PO "store on both"): Work also keeps the office's copy of a refused item (`_keep_for_office`, through `seams.work_refused_items()`), never as a field_reads row · the badge/device-id scan match is not built (field undecided) · the field-meter ACCEPTANCE door is not built — REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
