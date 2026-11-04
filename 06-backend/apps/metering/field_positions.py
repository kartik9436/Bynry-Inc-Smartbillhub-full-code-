# ── Trace ──────────────────────────────────────────────
# Change:   DEF-MET-10633 — FB-003, the position half (PO report 2026-10-26,
#           reader Sam Curran, RT-001; ruling 2026-10-27, decision log
#           "FB-003: the position is captured automatically, never by a button")
# Rules:    BR-MET-1202 (the phone's position at capture — evidence of where
#           the reader stood, never an address) · B14 rules 31 and 33
# Tests:    06-backend/tests/test_def_met_10633_late_position.py
# ───────────────────────────────────────────────────────
"""Where a field reading was taken — what the office sees on the reading.

The ruling, verbatim: *"The office sees the position and its time; a late one
reads added at 18:35 beside the saved time."*

`capture_for_meter_read` answers, for a read that came from a route reading:

* `captured_at` — the phone's clock when the reading was SAVED (R92);
* `position` — EITHER the one taken at save (`added: false`, its time the
  save's) OR, when it was saved without one, the late position that arrived
  within 5 minutes after (`added: true`, its time the FIX's) — never both,
  because a reading saved with a position takes no late one
  (`field_reads._judge_position`); None when it has neither;
* `photos` — each photograph the reading named, with its own position the same
  way (its shutter's, or a late one). `photo_id` rides for the image request
  only — never a visible value (B14 rule 31). Then each photo ADDED after the
  reading was saved (`DEF-FLD-10637`, FB-019 — its declaration's `photo_for`),
  with `added_after_save: true`; the reading's own carry `false`.

The late position is read from its own `field_reads` row (`kind = position`,
`position_for` → the target): nothing here, or anywhere, writes it into the
reading's row. Reads only; writes nothing.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from apps.metering.field_read_models import FieldRead, FieldReadPhoto
from core import errors
from core import tenancy as core_tenancy

#: PO 2026-10-27 — a late position attaches only within this long after the
#: save: *"After 5 minutes nothing is attached: the reader has likely moved,
#: and a far position is false evidence."* The phone applies it first
#: (`field-app/src/screens/reads/position.ts`); the reads door holds it too.
LATE_WINDOW = timedelta(minutes=5)

#: A reading's photographs are at most `field_reads.photo_ids`' own cap.
_PHOTO_CAP = 20


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:  # hard rule 1 — never a cross-tenant read
        raise errors.deny_as_not_found("BR-TEN-003")
    return tenant_id


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _point(row: FieldRead, *, added: bool) -> dict[str, Any]:
    return {
        "lat": str(row.lat),
        "lng": str(row.lng),
        "accuracy_m": str(row.accuracy_m) if row.accuracy_m is not None else None,
        "at": _iso(row.device_captured_at),
        "added": added,
    }


def _position_of(row: FieldRead, late: dict[Any, FieldRead]) -> dict[str, Any] | None:
    if row.lat is not None and row.lng is not None:
        return _point(row, added=False)
    found = late.get(row.id)
    if found is not None and found.lat is not None and found.lng is not None:
        return _point(found, added=True)
    return None


def capture_for_meter_read(meter_read_id: Any) -> dict[str, Any] | None:
    """The field capture behind one read, or None for a read that did not come
    from a route reading. Three queries whatever the photo count."""
    tenant_id = _tenant_id()
    reading = (
        FieldRead.objects.filter(tenant_id=tenant_id, meter_read_id=meter_read_id, kind="reading")
        .order_by("received_at")
        .first()
    )
    if reading is None:
        return None
    photo_ids = [str(p) for p in (reading.photo_ids or [])][:_PHOTO_CAP]
    declared_by = dict(
        FieldReadPhoto.objects.filter(tenant_id=tenant_id, photo_id__in=photo_ids).values_list(
            "photo_id", "key"
        )
    )
    photo_rows = {
        r.key: r
        for r in FieldRead.objects.filter(
            tenant_id=tenant_id, key__in=list(declared_by.values()), kind="photo"
        )
    }
    # FB-019 (`DEF-FLD-10637`): photos added AFTER the reading was saved name
    # it themselves (`photo_for`) — they are in no reading's `photo_ids`.
    added = list(
        FieldRead.objects.filter(tenant_id=tenant_id, photo_for=reading, kind="photo").order_by(
            "device_captured_at", "received_at"
        )[:_PHOTO_CAP]
    )
    targets = [reading.id, *(r.id for r in photo_rows.values()), *(r.id for r in added)]
    late = {
        r.position_for_id: r
        for r in FieldRead.objects.filter(tenant_id=tenant_id, position_for_id__in=targets)
    }
    photos = []
    for photo_id in photo_ids:
        key = next((k for pid, k in declared_by.items() if str(pid) == photo_id), None)
        row = photo_rows.get(key) if key else None
        photos.append(
            {
                "photo_id": photo_id,
                "position": _position_of(row, late) if row is not None else None,
                "added_after_save": False,
            }
        )
    shown = set(photo_ids)
    for row in added:
        photo_id = str((row.photo_ids or [None])[0] or "")
        if not photo_id or photo_id in shown:
            continue
        shown.add(photo_id)
        photos.append(
            {"photo_id": photo_id, "position": _position_of(row, late), "added_after_save": True}
        )
    return {
        "captured_at": _iso(reading.device_captured_at),
        "position": _position_of(reading, late),
        "photos": photos,
    }
