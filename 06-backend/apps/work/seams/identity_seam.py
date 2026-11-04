# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — the identity seam: a user by id, so an
#           order can show who raised, accepted or is assigned to it.
#           US-WRK-022 · US-WRK-023 (EP-WRK-04, CR-070 wave F) — may(),
#           enforce_surface() and the staff-user reads the crews screen needs
# Rules:    BR-WRK-002 (read-only) · CLAUDE.md hard rule 1 · OQ-WRK-1492, RULED
#           2026-09-04 — a clerk may accept, because it is day-to-day work (who
#           may accept — NOT decided here; this file reads a name and grants
#           nothing)
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-6 · TC-7)
# Impacts:  apps/work/selectors.py
# ───────────────────────────────────────────────────────
"""work → identity: a staff user by id. READ ONLY.

`work_orders.accepted_by` is already a reviewed cross-module FK to
`identity.User`; wave G's assignment columns will point the same way. Identity
owns roles and permissions (`identity/models.py`), and whether a technician
role or a `work_accept` permission exists is identity's companion work — this
file never answers "may this person accept". `OQ-WRK-1492` was RULED on
2026-09-04 — a clerk may, *"sicne it s a day to day work"* — and the mapping
lives in identity's catalogue, not in a seam that only reads.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def user(user_id: Any) -> dict[str, Any] | None:
    """One user of the tenant in context, or None. A user invited and not yet
    named has no name, and that is served as None rather than as ""."""
    from apps.identity import models as identity_models

    row = identity_models.User.objects.filter(tenant_id=_tenant_id(), pk=user_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "full_name": (getattr(row, "full_name", None) or None),
        "email": getattr(row, "email", None),
    }


def user_names(user_ids: Any) -> dict[str, str]:
    """`{id: name}` for many users in ONE read — the order's Audit tab names
    who acted on each row of a page (`CR-168-BRC10` P4.11). A user with no name
    yet is named by their email; an id this tenant does not hold is absent."""
    from apps.identity import models as identity_models

    ids = [value for value in set(user_ids) if value]
    if not ids:
        return {}
    return {
        str(row.id): (getattr(row, "full_name", None) or getattr(row, "email", None) or "")
        for row in identity_models.User.objects.filter(tenant_id=_tenant_id(), pk__in=ids)
    }


# ── The two questions wave F closed ────────────────────────────────────────


def may(actor: Any, permission_code: str) -> bool:
    """Does the acting user's role hold this permission?

    `actor` is the B12 §6a service shape — an object with `.role` (the role the
    identity layer attached to the request, server-derived, never client input)
    and `.id`. A `None` role answers **False**: deny-by-default, the same
    posture `core.permissions._role_of` takes and the same posture as RLS.

    ⚠ **THE PERMISSION IT IS ASKED FOR TODAY IS `work_accept`, AND THE OFFICE
    ROLES HOLD IT** — `OQ-WRK-1492`, ruled 2026-09-04. A field technician does
    not, and needs no rule of its own for it (`BR-WRK-044`): the Accept control
    is on the web app and `BR-WRK-043`'s surface scope keeps their login off it.
    Building a second *"technicians may not accept"* check here would go stale
    the day the phone gains an approval screen, which is exactly why the
    register records the exclusion as a consequence rather than as a rule.
    """
    from apps.identity import selectors as identity_selectors

    return identity_selectors.role_holds(getattr(actor, "role", None), permission_code)


def surface_scope(user_id: Any) -> str | None:
    """Which app this login may open — `web`, `mobile` or `both`, or None when
    there is no such user in the tenant in context."""
    from apps.identity import models as identity_models

    row = (
        identity_models.User.objects.filter(tenant_id=_tenant_id(), pk=user_id)
        .values_list("surface_scope", flat=True)
        .first()
    )
    return row or None


def enforce_surface(user_id: Any, surface: str) -> bool:
    """May this login be used from this app? — a READ, and it raises nothing.

    ⚠ **THE REFUSAL LIVES AT SIGN-IN, NOT HERE, AND THAT IS DELIBERATE.**
    `identity.services.sign_in` is the one place that knows which app a request
    came from, so that is where a wrong-surface attempt is refused with
    the key `identity.signIn.fieldAppOnly` (`OQ-WRK-1494`; its words are the
    PO's two sentences of 2026-10-06, `DEF-IDN-9777`, a ruled exception to
    B14 rule 33 — they read *"Sign in on the field app."* until then).
    A second refusal in this seam would be a second place for the sentence to
    be written differently.

    What this is for is the phone's own reads: `US-WRK-023` TC-6 says a login
    with no technician profile gets an empty day and a sentence rather than an
    error, and a screen that has to decide that needs to ask without being
    thrown at.

    An unknown user answers **False** — deny-by-default again.
    """
    scope = surface_scope(user_id)
    return scope in ("both", surface) if scope else False


def staff_user_choices() -> list[dict[str, Any]]:
    """Every ACTIVE or INVITED login of the tenant, for the *add a technician*
    picker (`Work-023`).

    ⚠ **IT IS A PICKER AND NOT A TEXT BOX, WHICH IS `BR-WRK-028` MADE
    UNAVOIDABLE.** A technician is a profile beside an existing login; offering
    a list of logins that exist is how a supervisor is stopped from typing an
    email that has none, rather than being told off afterwards. The refusal in
    `workforce.create_technician` still stands — a picker is convenience and
    the server is the enforcement (`BR-SHL-025`) — but the two together mean
    the refusal is a thing a caller has to work at.

    Deactivated logins are left out: a person who cannot sign in cannot be sent
    to a job, and offering them would put a name in the dispatcher's picker
    that can never be assigned anything.
    """
    from apps.identity import models as identity_models

    rows = (
        identity_models.TenantMembership.objects.filter(tenant_id=_tenant_id())
        .exclude(status=identity_models.TenantMembership.STATUS_DEACTIVATED)
        .select_related("user", "role")
        .order_by("user__full_name", "user__email")
    )
    return [
        {
            "user_id": str(row.user_id),
            "full_name": (row.user.full_name or None),
            "email": row.user.email,
            "role_code": row.role.code,
            "status": row.status,
        }
        for row in rows
    ]


def staff_users_queryset(q: str | None = None) -> Any:
    """`staff_user_choices`' population as a QUERYSET to page in SQL — every
    ACTIVE or INVITED membership of the tenant, by name, with `user` and
    `role` joined; `q` matches the name or the email (`CR-168-BRC10` image 26,
    lane SRV-4: the add-member picker pages like any other list, NFR-3). READ
    ONLY."""
    from django.db.models import Q

    from apps.identity import models as identity_models

    qs = (
        identity_models.TenantMembership.objects.filter(tenant_id=_tenant_id())
        .exclude(status=identity_models.TenantMembership.STATUS_DEACTIVATED)
        .select_related("user", "role")
        .order_by("user__full_name", "user__email", "id")
    )
    term = (q or "").strip()
    if term:
        qs = qs.filter(Q(user__full_name__icontains=term) | Q(user__email__icontains=term))
    return qs


def revoke_device_tokens(device_uid: str, actor_user_id: Any) -> int:
    """`CR-187-BRC10` — the office's remote sign-out, identity's half: every
    live native-app token of this handset revoked, reason `device_signed_out`.

    ⚠ **THE ONE CALL IN THIS FILE THAT CAUSES A WRITE, AND IT IS A SERVICE CALL,
    NOT AN ORM WRITE.** `BR-WRK-002` forbids Work writing identity's tables; it
    sanctions asking identity's own service to act, which is the door
    `metering_seam.raise_work_order` already uses. The tokens are identity's;
    the decision to sign a handset out is the office's on Work's screen.
    HUMAN-REVIEW-PENDING — 🔒 auth, AI-authored 2026-10-21."""
    from apps.identity import native

    return native.revoke_device(
        tenant_id=_tenant_id(), device_uid=device_uid, actor_user_id=actor_user_id
    )


def field_capture_seconds() -> int:
    """The utility's field-app capture life, in seconds — identity's Security
    setting (PO 2026-10-21, *"this should come from settings"*). A READ: the
    capture token is minted and checked against it, and the native refresh
    token is minted from the same function, so the two cannot disagree."""
    from apps.identity import selectors as identity_selectors

    return identity_selectors.field_capture_seconds(_tenant_id())



def field_app_pins() -> list[dict[str, Any]]:
    """The utility's field-app certificate pins, active and unexpired —
    identity's Security setting (`OQ-FLD-12797`, PO 2026-10-24: *"use settings
    - security values set in staff portal"*). A READ, tenant-scoped like every
    other call here, so one utility's list never reaches another's phones."""
    from apps.identity import field_pins

    return field_pins.phone_pins(_tenant_id())

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01) · US-WRK-022/023@2b08ba9f (EP-WRK-04) · 10-execution-plan.md wave F task F2
# generated: 2026-09-03 by the CR-070 wave A build lane
# AMENDED 2026-09-05 by the CR-070 wave F build lane — may() · surface_scope() ·
#   enforce_surface() · staff_user_choices(). The two NotImplementedError stubs the
#   wave plan called for were NEVER WRITTEN: both questions were ruled on 2026-09-04,
#   a day after the plan, and r11 step 0 is what caught it.
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_005_module.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
