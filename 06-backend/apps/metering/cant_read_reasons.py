# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10609 — no screen managed the can't-read reasons, and a
#           JOB reading's *Unable to read* carried none.
# Ruling:   decision log 2026-10-26 *"ONE 'Unable to read' reason list for
#           routes AND jobs, managed in Settings"* — PO, verbatim: *"yes do
#           it"*. One list (`metering.CantReadReason`) for route readings AND
#           job readings; Settings → Configure → Reference data → Readings;
#           the utility adds, renames and reorders; a seeded reason is switched
#           off, never deleted; a utility's own reason is deleted only if never
#           used, otherwise switched off.
# Rules:    BR-FLD-00082 (R82 — the reasons are DATA, eight seeded,
#           tenant-extensible) · BR-TEN-036 (seeded rows deactivate, never
#           delete) · NFR-3 (the list is paged by the server) · BR-SHL-025
#           (Settings Full = System Admin; the service refuses anyone else's
#           write) · CLAUDE.md hard rules 1 (tenant in context) and 7 (every
#           write audited)
# Tests:    06-backend/tests/test_def_met_10609_cant_read_reasons.py
# Impacts:  apps/metering/cant_read_reasons_api.py (the routes) ·
#           apps/metering/seams.py (`work_unable_reason_counts`) ·
#           apps/work/evidence.py (`unable_reason_counts`, the other half of USED)
# ───────────────────────────────────────────────────────
"""The office's door onto the can't-read reasons — Settings → Reference data →
Readings.

`field_reads.py` owns the list's seed and the handset's two doors
(`GET work/mobile/cant-read-reasons`, the R82 add/deactivate). This file is the
SETTINGS half the 2026-10-26 ruling asked for: a paged list that includes
switched-off reasons, add by NAME (the code is minted here and never changes),
rename, move up or down, switch on or off, and delete.

WHAT *USED* MEANS, AND WHY IT IS TWO MODULES' ROWS
────────────────────────────────────────────────────────────────────────────
A reason is used when ANY route reading names its code (`field_reads`, this
module's own table) OR any job reading was answered *Unable to read* with it
(`work_order_readings`, Work's table). Metering never reads Work's ORM (B1/B8),
so the second count arrives through `seams.work_unable_reason_counts`, which
calls Work's own function by name. A used reason cannot be deleted — the
readings that name it would then name nothing — so the refusal says to switch
it off instead, which keeps every old reading's words and stops new ones.

A SEEDED reason is never deletable, used or not (BR-TEN-036): the eight are the
product's starting vocabulary, and a utility that does not want one switches it
off.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower

from apps.metering import field_reads, seams
from apps.metering.field_read_models import CantReadReason, FieldRead
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

NAME_LIMIT = 120
CODE_LIMIT = 60

#: The refusals this door owns. Each key is in all eleven catalogues.
MSG_IN_USE = "metering.cantReadReasons.in_use"
MSG_SEEDED = "metering.cantReadReasons.seeded"
MSG_DUPLICATE = "metering.lookups.duplicate_code"


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _payload(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _fe(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _unknown_fields(data: dict[str, Any], allowed: set[str]) -> None:
    """A field this door does not take is refused BY NAME — `code` above all,
    because the code is fixed for life (readings already name it)."""
    extra = sorted(set(data) - allowed)
    if extra:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            field_errors=[_fe(name, errors.VAL_FORMAT, "errors.val-002") for name in extra],
        )


def _clean_name(raw: Any) -> str:
    name = str(raw).strip()[:NAME_LIMIT] if raw is not None else ""
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, field_errors=[_fe("name", errors.VAL_REQUIRED, "errors.val-001")]
        )
    return name


def _ordered() -> Any:
    return CantReadReason.objects.filter(tenant_id=_tenant_id()).order_by("sort_order", "name", "id")


def _reason_or_404(code: Any) -> CantReadReason:
    field_reads.ensure_cant_read_reasons()
    row = CantReadReason.objects.filter(tenant_id=_tenant_id(), code__iexact=str(code)).first()
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-TEN-003")
    return row


def _refuse_duplicate_name(name: str, *, except_id: Any = None) -> None:
    qs = CantReadReason.objects.filter(tenant_id=_tenant_id(), name__iexact=name)
    if except_id is not None:
        qs = qs.exclude(pk=except_id)
    if qs.exists():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=MSG_DUPLICATE,
            params={"value": name},
            field_errors=[_fe("name", errors.VAL_FORMAT, MSG_DUPLICATE, value=name)],
        )


# ── USED ────────────────────────────────────────────────────────────────────
def usage_counts(codes: list[str]) -> dict[str, int]:
    """casefolded code → readings naming it, routes AND jobs. Codes are matched
    without regard to case, as the list's own uniqueness is (BR-TEN-030)."""
    folded = sorted({c.casefold() for c in codes if c})
    if not folded:
        return {}
    counts: dict[str, int] = dict.fromkeys(folded, 0)
    routes = (
        FieldRead.objects.filter(tenant_id=_tenant_id(), cant_read_reason__isnull=False)
        .annotate(folded=Lower("cant_read_reason"))
        .filter(folded__in=folded)
        .values("folded")
        .annotate(n=Count("id"))
    )
    for row in routes:
        counts[row["folded"]] = counts.get(row["folded"], 0) + row["n"]
    for code, n in seams.work_unable_reason_counts(folded).items():
        counts[code] = counts.get(code, 0) + n
    return counts


def row_dict(row: CantReadReason, used: int) -> dict[str, Any]:
    return {**field_reads.reason_dict(row), "used": used}


# ── READ ────────────────────────────────────────────────────────────────────
def reasons_queryset(*, q: str | None = None, status: str | None = None) -> Any:
    """`GET settings/cant-read-reasons` — every reason of the tenant, switched
    off ones included, in the order the phone shows them. The DATABASE pages it
    (NFR-3); `page_rows` adds *used* for the page only."""
    field_reads.ensure_cant_read_reasons()
    qs = _ordered()
    if q and str(q).strip():
        qs = qs.filter(Q(name__icontains=str(q).strip()))
    if status == "active":
        qs = qs.filter(active=True)
    elif status == "inactive":
        qs = qs.filter(active=False)
    return qs


def page_rows(page: list[CantReadReason]) -> list[dict[str, Any]]:
    counts = usage_counts([row.code for row in page])
    return [row_dict(row, counts.get(row.code.casefold(), 0)) for row in page]


def _answer(row: CantReadReason) -> dict[str, Any]:
    return row_dict(row, usage_counts([row.code]).get(row.code.casefold(), 0))


def _audit(actor: Any, action: str, row_id: Any, *, before: Any = None, after: Any = None) -> None:
    core_audit.write_row(
        action=action,
        entity_type="cant_read_reason",
        entity_id=row_id,
        actor_user_id=_actor_id(actor),
        before=before,
        after=after,
    )


# ── WRITE ───────────────────────────────────────────────────────────────────
def _mint_code(name: str) -> str:
    """The code a reading will carry for life — from the name, unique per
    tenant without regard to case. A name with no Latin letters (`犬`) gets
    `reason`, then `reason_2`…; the code is never shown to anyone."""
    base = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")[: CODE_LIMIT - 6] or "reason"
    taken = {
        c.casefold()
        for c in CantReadReason.objects.filter(
            tenant_id=_tenant_id(), code__istartswith=base
        ).values_list("code", flat=True)
    }
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


@require_role(SYSTEM_ADMIN)
def add_reason(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST settings/cant-read-reasons` `{name}` — a utility's own reason, at
    the bottom of the list, switched on."""
    data = _payload(payload)
    _unknown_fields(data, {"name"})
    name = _clean_name(data.get("name"))
    field_reads.ensure_cant_read_reasons()
    _refuse_duplicate_name(name)
    with transaction.atomic():
        last = _ordered().order_by("-sort_order").first()
        row = CantReadReason.objects.create(
            tenant_id=_tenant_id(),
            code=_mint_code(name),
            name=name,
            sort_order=(last.sort_order if last else 0) + 10,
            is_system=False,
            active=True,
        )
        _audit(actor, "cant_read_reason.created", row.id, after=field_reads.reason_dict(row))
    return row_dict(row, 0)


@require_role(SYSTEM_ADMIN)
def update_reason(actor: Any, code: str, payload: Any) -> dict[str, Any]:
    """`PATCH settings/cant-read-reasons/{code}` `{name?, active?}` — rename
    and/or switch on or off. A seeded reason may be renamed too: the wording is
    the utility's, the code underneath is not."""
    data = _payload(payload)
    _unknown_fields(data, {"name", "active"})
    if "active" in data and not isinstance(data["active"], bool):
        raise errors.ValidationError(
            errors.VAL_FORMAT, field_errors=[_fe("active", errors.VAL_FORMAT, "errors.val-002")]
        )
    row = _reason_or_404(code)
    before = field_reads.reason_dict(row)
    fields: list[str] = []
    if "name" in data:
        name = _clean_name(data["name"])
        _refuse_duplicate_name(name, except_id=row.id)
        row.name = name
        fields.append("name")
    if "active" in data:
        row.active = data["active"]
        fields.append("active")
    if fields:
        with transaction.atomic():
            row.save(update_fields=[*fields, "updated_at"])
            _audit(actor, "cant_read_reason.updated", row.id, before=before,
                   after=field_reads.reason_dict(row))
    return _answer(row)


@require_role(SYSTEM_ADMIN)
def move_reason(actor: Any, code: str, payload: Any) -> dict[str, Any]:
    """`POST settings/cant-read-reasons/{code}/move` `{direction: up|down}` —
    one place in the order the phone shows. One row at a time so it works on
    any page of a paged list; at either end it is a no-op, not a refusal."""
    data = _payload(payload)
    _unknown_fields(data, {"direction"})
    direction = data.get("direction")
    if direction not in ("up", "down"):
        raise errors.ValidationError(
            errors.VAL_FORMAT, field_errors=[_fe("direction", errors.VAL_FORMAT, "errors.val-002")]
        )
    row = _reason_or_404(code)
    with transaction.atomic():
        rows = list(_ordered().select_for_update())
        index = next(i for i, r in enumerate(rows) if r.pk == row.pk)
        other = index - 1 if direction == "up" else index + 1
        if 0 <= other < len(rows):
            before = [r.code for r in rows]
            rows[index], rows[other] = rows[other], rows[index]
            for position, item in enumerate(rows, start=1):
                if item.sort_order != position * 10:
                    item.sort_order = position * 10
                    item.save(update_fields=["sort_order", "updated_at"])
            _audit(actor, "cant_read_reason.moved", row.id, before={"order": before},
                   after={"order": [r.code for r in rows], "direction": direction})
    row.refresh_from_db()
    return _answer(row)


@require_role(SYSTEM_ADMIN)
def delete_reason(actor: Any, code: str) -> dict[str, Any]:
    """`DELETE settings/cant-read-reasons/{code}` — a utility's own reason that
    no reading has ever named. Anything else is refused with the way out."""
    row = _reason_or_404(code)
    if row.is_system:
        raise errors.BizError(errors.BIZ_STATE, br_ref="BR-TEN-036", message_key=MSG_SEEDED)
    used = usage_counts([row.code]).get(row.code.casefold(), 0)
    if used:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-FLD-00082", message_key=MSG_IN_USE, params={"used": used}
        )
    with transaction.atomic():
        before = field_reads.reason_dict(row)
        row_id = row.id
        row.delete()
        _audit(actor, "cant_read_reason.deleted", row_id, before=before)
    return {"code": before["code"], "deleted": True}


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-10609 (decision log 2026-10-26 "ONE 'Unable to read' reason list")
# generated: 2026-10-26 by the DEF-MET-10609 lane
