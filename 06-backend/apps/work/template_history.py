# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — P3.28 (a template's change
#           history: *"The Audit tab lists who changed what, and when"*), image 47
# Rules:    hard rule 7 (every builder write already lands an audit row) ·
#           B14 rule 31 (names and words, never ids) · NFR-3 (paged in SQL)
# Tests:    06-backend/tests/test_cr168_srv3_templates.py
# ───────────────────────────────────────────────────────
"""`GET /work/templates/{id}/audit` — the trail `audit_log` already holds.

⚠ **THE AUDIT TAB SAID *"opens with the next release"* OVER A TRAIL THAT
EXISTED** (P3.28): every builder write — header, the seven collections, publish,
duplicate, (de)activate — has written an `audit_log` row since wave D. This
reads it, newest first, paged in SQL, each row in words:

    {at, by {name}, act, collection, version, summary {field: value}}

`act` is a token the screen translates (`created`, `updated`, `published`,
`deactivated`, `reactivated`, `duplicated`, `replaced`, `help_document_stored`,
`deleted`); `collection` names which of the seven a `replaced` changed;
`summary` carries the row's own small facts (*3 rows*, *v2*) — never an id.
"""

from __future__ import annotations

import math
from typing import Any

from apps.work.seams import audit_seam, identity_seam, metering_seam
from core import errors
from core.pagination import clamp_page_size

_PREFIX = "work_order_template."

#: Keys an audit row may carry that are ids, never drawn (B14 rule 31).
_HIDDEN = {"id", "template_id", "user_id", "part_id", "asset_type_id", "skill_id", "type_id"}


def _act_of(action: str) -> tuple[str, str | None]:
    tail = action[len(_PREFIX):] if action.startswith(_PREFIX) else action
    if tail.endswith("_replaced"):
        return "replaced", tail[: -len("_replaced")].replace("_", "-")
    return tail, None


def _summary(row: Any) -> dict[str, Any]:
    after = row.after if isinstance(row.after, dict) else {}
    out: dict[str, Any] = {}
    for key, value in after.items():
        if key in _HIDDEN or key.endswith("_id") or isinstance(value, (dict, list)):
            continue
        out[key] = value
    return out


def template_audit(template_id: Any, *, page: Any = 1, per: Any = None) -> dict[str, Any]:
    header = metering_seam.template(template_id)
    if header is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    qs = audit_seam.entity_trail_queryset("work_order_template", header["id"]).order_by(
        "-created_at", "-id"
    )
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    start = (number - 1) * size
    slab = list(qs[start : start + size])
    names = identity_seam.user_names([row.actor_user_id for row in slab])
    rows = []
    for row in slab:
        act, collection = _act_of(row.action)
        after = row.after if isinstance(row.after, dict) else {}
        by = names.get(str(row.actor_user_id)) if row.actor_user_id else None
        if by is None and getattr(row, "actor_label", None):
            by = row.actor_label
        rows.append(
            {
                "at": row.created_at.isoformat() if row.created_at else None,
                "by": {"name": by} if by else None,
                "act": act,
                "collection": collection or after.get("collection"),
                "version": after.get("version"),
                "summary": _summary(row),
            }
        )
    return {
        "template_no": header.get("template_no"),
        "name": header.get("name"),
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (GET /work/templates/{id}/audit) · §16
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D✔ E=n/a F✔ G✔ H=n/a
# gates: G78 (audit_log read through audit_seam) · pytest
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
