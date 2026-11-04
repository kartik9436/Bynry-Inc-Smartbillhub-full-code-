# ── Trace ──────────────────────────────────────────────
# Change:   CR-162-BRC10 item 2 (Q1) — the account type (master or regular) is
#           decided by the PREMISES TYPE, not by how many units were entered.
# Rules:    BR-CUS-1114 (amended 2026-10-02, Q1) · BR-MET-034 (the premises-type
#           list) · BR-MET-116 · CLAUDE.md hard rule 1 (tenant scoping), hard-won
#           law 3 (defaults fail closed) · B2 §2 (customers reads metering only
#           through a seam)
# Tests:    06-backend/tests/test_cr162_master_by_premises_type.py
# ───────────────────────────────────────────────────────
"""**Which ACCOUNT TYPE does a premises of this type take — master or
regular?** — the one answer every account-creation door reads, and it lives ON
THE UTILITY'S OWN PREMISES-TYPE ROW (`premises_types.account_kind`).

PO ruling 2026-10-02 (decision log, *"NEW CONNECTION — THE PO'S SCREEN-BY-SCREEN
REVIEW BECOMES ONE PROGRAMME"*, Q1): *"apartment complex, commercial building,
mixed-use and any type able to hold several units get a master account (and the
owner customer) even with one unit entered … a single-family home gets none."*
It corrects how `BR-CUS-1114` was first built (2.442.0), which counted the units
entered — Haustin Towers, an apartment building with one unit typed in, got no
master account.

⚠ **NOT A MAPPING OF NAMES IN CODE — A SETTING ON EACH TYPE.** Reframed by the
PO the same day, verbatim: *"when we say premises type has account type - master
or regular attached … then when you create account dont you want to use this
field when you are creating accounts"*. So each row of the tenant's own list
says `master` or `regular`:

  * the seeded rows start from `SEED_ACCOUNT_KIND` below — by the seed for a
    new utility and by `metering/0066` for every existing one;
  * a type a utility ADDS in Settings must answer it: required, no default,
    refused with a plain sentence when missing (hard-won law 3 —
    `lookups.PremisesTypeLookupHandler`);
  * changing the answer later moves only what is created AFTERWARDS: it is
    read when an owner's master account is opened, and nothing removes or
    creates one retroactively.

**`None`** — a utility's own row from before 0066 that nobody has answered yet,
an unknown premises, or a premises with no type. The caller then falls back to
the rule as first built: two or more homes at the address
(`customers.services.dwelling_units_at_premises`), so such an address behaves
exactly as it did on 2.442.0 until the row is answered.
"""

from __future__ import annotations

from typing import Any

from apps.metering import models
from core import tenancy as core_tenancy

#: The two answers — the same words as `accounts.kind`.
ACCOUNT_KIND_MASTER = "master"
ACCOUNT_KIND_REGULAR = "regular"
ACCOUNT_KINDS: tuple[str, ...] = (ACCOUNT_KIND_MASTER, ACCOUNT_KIND_REGULAR)

#: The SEEDED answer for each of `BR-MET-034`'s system codes — the seed's and
#: `metering/0066`'s single source. A utility may change any of them on
#: Settings; this is where a new utility STARTS, never what it is held to.
SEED_ACCOUNT_KIND: dict[str, str] = {
    "apartment_complex": ACCOUNT_KIND_MASTER,
    "commercial_building": ACCOUNT_KIND_MASTER,
    "mixed_use": ACCOUNT_KIND_MASTER,
    "mobile_home_park": ACCOUNT_KIND_MASTER,
    "government_building": ACCOUNT_KIND_MASTER,
    "single_family": ACCOUNT_KIND_REGULAR,
}


def seed_answer(code: Any) -> str | None:
    """The seeded account type for a system code, `None` for any other code."""
    return SEED_ACCOUNT_KIND.get(str(code or "").strip().lower())


def premises_account_kind(premises_id: Any) -> str | None:
    """`master` / `regular` off this premises' TYPE row, for the tenant in
    context — `None` for an unknown premises, a premises with no type, or a
    type row not yet answered (the caller's fallback, counting homes, then
    decides). A stranger's id answers the same as an absent one
    (`BR-TEN-003`)."""
    if not premises_id:
        return None
    answer = (
        models.Premises.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), pk=premises_id
        )
        .values_list("premises_type__account_kind", flat=True)
        .first()
    )
    return answer if answer in ACCOUNT_KINDS else None


def premises_status(premises_id: Any) -> str | None:
    """The stored status of one premises (`draft | pending | active |
    inactive`), or `None` when there is no such premises in this tenant.

    `customers` reads it to open an owner's master account PENDING on a
    premises that is itself still pending (Q1: *"created PENDING at Create,
    ACTIVE on approval"*)."""
    if not premises_id:
        return None
    return (
        models.Premises.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), pk=premises_id
        )
        .values_list("status", flat=True)
        .first()
    )


def unit_build_services(unit_id: Any) -> list[dict[str, Any]]:
    """`CR-162-BRC10` — every service a LIVE New Connection (not cancelled)
    provides at this unit, with the moment it was activated or `None` while it
    waits. `[]` for a unit no build touched — every unit before New Connection
    existed, and the ordinary answer.

    Customers reads it to keep an account opened BEFORE approval from being
    billed for days the service did not exist yet (PO 2026-10-02, ruled B:
    *"allow it. The account opens, but billing waits until the unit is
    activated"*)."""
    if not unit_id:
        return []
    return units_build_services([unit_id]).get(str(unit_id), [])


def units_build_services(unit_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """`unit_build_services` for MANY units in ONE query — what billing's bulk
    Check primes a whole batch with (`customers.selectors.prime_check_batch`).
    A unit no build touched is absent from the map."""
    ids = [str(one) for one in (unit_ids or ()) if one not in (None, "")]
    if not ids:
        return {}
    from apps.work import connection_models as work_tables

    rows = (
        work_tables.ConnectionService.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            unit_id__in=ids,
            connection__cancelled_at__isnull=True,
        )
        .exclude(state=work_tables.SVC_CANCELLED)
        .select_related("service", "connection")
        .order_by("unit_id", "created_at", "id")
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row.unit_id), []).append(
            {
                "service": row.service.code,
                "activated_at": row.activated_at if row.state == work_tables.SVC_ACTIVATED else None,
                "connection_id": str(row.connection_id),
                "connection_no": row.connection.connection_no,
            }
        )
    return out


def unit_not_yet_active(unit_id: Any) -> dict[str, Any] | None:
    """`CR-162-BRC10` — is this unit still waiting on its New Connection's
    approval? `None` when it may be moved into; otherwise the build that holds
    it, so a refusal can link to it.

    PO 2026-10-02, verbatim, on a move-in before approval: *"this will not
    ahppen sicne presies and unit is still in pending status"* — enforced by
    STATUS. A unit is not active yet when its premises is still `pending`, or
    when a live build (not cancelled) still holds one of the unit's services
    un-activated (*"unit active when all its services are"*). A unit no build
    ever touched — every unit before New Connection existed — is active."""
    if not unit_id:
        return None
    from apps.work import connection_models as work_tables

    tenant_id = core_tenancy.current_tenant_id()
    unit = (
        models.Unit.objects.filter(tenant_id=tenant_id, pk=unit_id)
        .select_related("premises")
        .first()
    )
    if unit is None:
        return None
    waiting = (
        work_tables.ConnectionService.objects.filter(
            tenant_id=tenant_id, unit_id=unit.id, connection__cancelled_at__isnull=True
        )
        .exclude(state__in=(work_tables.SVC_ACTIVATED, work_tables.SVC_CANCELLED))
        .select_related("connection")
        .order_by("created_at", "id")
        .first()
    )
    connection = waiting.connection if waiting is not None else None
    if connection is None and unit.premises.status == "pending":
        connection = (
            work_tables.Connection.objects.filter(
                tenant_id=tenant_id, premises_id=unit.premises_id, cancelled_at__isnull=True
            )
            .order_by("created_at", "id")
            .first()
        )
        if connection is None:
            return {"connection_id": None, "connection_no": None}
    if connection is None:
        return None
    return {"connection_id": str(connection.id), "connection_no": connection.connection_no}
