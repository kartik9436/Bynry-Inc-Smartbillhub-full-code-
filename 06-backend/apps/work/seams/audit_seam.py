# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P4.11 (hold, cancel, completion
#           and acceptance in the order's own history, `DEF-WRK-9532`)
# Rules:    BR-WRK-002 (a seam READS; Work writes no other module's table) ·
#           BR-AUD-007 (audit_log is read under `app.tenant_id`, RLS FORCE) ·
#           CLAUDE.md hard rule 1 · NFR-3 (paged in SQL by the caller)
# Tests:    06-backend/tests/test_cr168_srv1_server.py ·
#           tests/test_cr168_round1_held_defects.py (DEF-WRK-9532)
# ───────────────────────────────────────────────────────
"""work → audit: the `audit_log` rows written about ONE work order. READ ONLY.

The order's Audit tab read `work_order_assignments` only, so a hold, a cancel,
the field's close and the office's acceptance — every one of them written to
`audit_log` by the service that did it (hard rule 7) — never appeared on the one
screen a supervisor opens to ask *what happened to this job*. This seam hands
`dispatch.order_audit` a QUERYSET of those rows, so the union with the
assignment history is paged in SQL rather than assembled in Python.

The audit table is `apps.audit`'s; it is read here and nowhere else in
`apps/work` (`G78`). A cross-tenant row cannot appear: the filter is the tenant
in context and RLS `FORCE` sits under it.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def order_trail_queryset(order_id: Any, actions: tuple[str, ...]) -> Any:
    """`audit_log` rows about this order whose action is one of `actions`."""
    from apps.audit import models as audit_models

    return audit_models.AuditLog.objects.filter(
        tenant_id=_tenant_id(),
        entity_type="work_order",
        entity_id=order_id,
        action__in=actions,
    )


def entity_trail_queryset(entity_type: str, entity_id: Any) -> Any:
    """`audit_log` rows about one entity, every action — a template's history
    (`CR-168-BRC10` P3.28). A READ; the caller orders and pages it."""
    from apps.audit import models as audit_models

    return audit_models.AuditLog.objects.filter(
        tenant_id=_tenant_id(), entity_type=entity_type, entity_id=entity_id
    )


def trail_rows(row_ids: list[Any]) -> list[Any]:
    """The full rows for one page of ids (the union pages ids, then reads these)."""
    from apps.audit import models as audit_models

    return list(audit_models.AuditLog.objects.filter(tenant_id=_tenant_id(), id__in=row_ids))


def latest_actor_per_order(order_ids: list[Any], action: str) -> dict[str, Any]:
    """`{order_id: actor_user_id}` — who wrote the LATEST `action` row about
    each of a page's orders, in ONE query (`DEF-WRK-9679`: the Approvals row's
    *closed by*). Ordered newest first and folded keeping the first seen, so a
    job closed, sent back and closed again names its last closer. An order with
    no such row is absent from the answer, never mapped to a guess."""
    from apps.audit import models as audit_models

    if not order_ids:
        return {}
    rows = (
        audit_models.AuditLog.objects.filter(
            tenant_id=_tenant_id(),
            entity_type="work_order",
            entity_id__in=list(order_ids),
            action=action,
        )
        .order_by("-created_at")
        .values_list("entity_id", "actor_user_id")
    )
    found: dict[str, Any] = {}
    for entity_id, actor_user_id in rows:
        found.setdefault(str(entity_id), actor_user_id)
    return found
