# ── Trace ──────────────────────────────────────────────
# Story:    US-IDN-004 (tenant user list — §5 columns, IS-2 pagination/sort) ·
#           US-IDN-007 (roles & permissions matrix · BR-IDN-012 reference count) ·
#           US-IDN-008 (GET /me/permissions — the caller's OWN A4 row, read off
#           the SAME matrix source; endpoint added by PO directive 2026-08-09) ·
#           US-IDN-010 (effective security-policy values = row or seed defaults)
#           Screens: S8 · S48
# Rules:    BR-IDN-008 (3 predefined roles) · BR-IDN-009 (list is SysAdmin-only —
#           enforced at the API layer) · BR-IDN-010/029 (current-tenant rows only) ·
#           BR-IDN-012 (audit-lock reference count) · BR-IDN-014 (matrix verbatim
#           from catalog + signed A4 grid) · BR-IDN-025/026 (policy seed defaults) ·
#           BR-SHL-025 (the permission set is UI convenience — the server enforces)
# Tests:    06-backend/tests/test_us_idn_004*.py · test_us_idn_007*.py ·
#           test_us_idn_010*.py (RLS halves = G5 isolation suite)
# Impacts:  apps/identity/api.py (all reads) · apps/identity/auth.py (session +
#           membership resolution) · core.pagination (sort vocabulary)
# ───────────────────────────────────────────────────────
"""identity read path (B8 layering: api.py thin → services write, selectors
read). Every query here is tenant-filtered at the app layer AND backed by RLS
on Postgres — the filter is convenience, RLS is the law (sqlite tests exercise
the filter; the G5 isolation suite proves RLS).

Cross-module reads (Eng disposition, recorded): BR-IDN-012 names referencing
tables owned by other modules (audit_log.actor_user_id, user_preferences).
Their owning modules expose no selector yet (W0), so the count reads their
models via django.apps.get_model — read-only, no write ever crosses the
boundary (B1). Later waves append their referencing tables here.
"""

import uuid
from typing import Any

from django.apps import apps as django_apps
from django.db.models import F, QuerySet

from apps.identity.models import (
    A4_MATRIX,
    Role,
    RolePermission,
    SecurityPolicy,
    Session,
    TenantMembership,
    User,
)

# US-IDN-004 capability row: sortable columns → ORM fields (IS-2).
USER_LIST_SORTS = {
    "name": "user__full_name",
    "email": "user__email",
    "role": "role__name",
    "last_active": "last_active_at",
    "status": "status",
}
USER_LIST_DEFAULT_SORT = "last_active"
USER_LIST_DEFAULT_DIR = "desc"


def user_by_email(tenant_id: Any, email: str) -> User | None:
    """(tenant, email) lookup, case-insensitive (citext law, BR-IDN-029)."""
    return User.objects.filter(tenant_id=tenant_id, email__iexact=email).first()


def user_by_phone(tenant_id: Any, raw: Any) -> User | None:
    """(tenant, phone) lookup on the E.164 form only (`CR-187-BRC10`,
    `identity/0013`). A value that is not a number, or a number no single login
    holds at this utility, answers None. Never reads `users.phone` as typed."""
    from apps.identity.phones import normalise_phone

    number = normalise_phone(raw)
    if number is None:
        return None
    return User.objects.filter(tenant_id=tenant_id, phone_e164=number).first()


def phone_holder(tenant_id: Any, raw: Any, *, exclude_user_id: Any = None) -> User | None:
    """Another login at this utility already holding this number, or None —
    what `services` asks before a save (`errors.identity.phone_in_use`)."""
    from apps.identity.phones import normalise_phone

    number = normalise_phone(raw)
    if number is None:
        return None
    qs = User.objects.filter(tenant_id=tenant_id, phone_e164=number)
    if exclude_user_id is not None:
        qs = qs.exclude(pk=exclude_user_id)
    return qs.first()


def user_in_tenant(tenant_id: Any, user_id: Any) -> User | None:
    """Current-tenant row or None — an id from another tenant is absent here,
    so the API answers 404 indistinguishable from not-found (HR-1/G4)."""
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        return None
    return User.objects.filter(tenant_id=tenant_id, pk=user_id).first()


def membership_for_user(tenant_id: Any, user_id: Any) -> TenantMembership | None:
    return (
        TenantMembership.objects.filter(tenant_id=tenant_id, user_id=user_id)
        .select_related("role", "user")
        .first()
    )


def session_by_id(session_id: str) -> Session | None:
    """Platform read (sessions is RLS-exempt — it establishes tenant context).

    Deliberately NOT select_related("user"): `users` IS an RLS table, so a JOIN
    here is evaluated under whatever `app.tenant_id` the request arrived with —
    which, since the 2026-08-10 path ruling, is another tenant's (the foreign-
    session case) or none at all (the platform paths /api/jobs, /api/exports).
    The policy would hide the joined row, the INNER JOIN would drop the session
    with it, and the caller would read "unknown session" — a 401 where the law
    says 404, and a broken poll endpoint. The row is read first, the tenant is
    settled, and only THEN does auth.py touch `session.user`, by which point
    the context is the session's own tenant. One extra query, correct answer.
    """
    try:
        uuid.UUID(str(session_id))
    except ValueError:
        return None
    return Session.objects.filter(pk=session_id).first()


def user_list(tenant_id: Any, *, sort: str | None, direction: str) -> QuerySet:
    """US-IDN-004: the current tenant's memberships with user + role, ordered
    per the capability row (default last-active desc, nulls last = "Never" at
    the bottom, stable secondary by id)."""
    field = USER_LIST_SORTS.get(sort or USER_LIST_DEFAULT_SORT, "last_active_at")
    descending = direction == "desc"
    ordering = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_first=True)
    return (
        TenantMembership.objects.filter(tenant_id=tenant_id)
        .select_related("user", "role")
        .order_by(ordering, "id")
    )


def role_by_code(code: str) -> Role | None:
    return Role.objects.filter(code=code).first()


def roles_matrix() -> dict[str, Any]:
    """US-IDN-007 TC-3 (BR-IDN-014): the read-only matrix — roles + permission
    rows from the platform catalog, cell values from the signed A4 grid
    (models.A4_MATRIX; the cell has no B2 column — reported gap)."""
    roles = list(Role.objects.order_by("created_at").values("code", "name"))
    permissions = []
    for code, label, cells in A4_MATRIX:
        permissions.append(
            {
                "code": code,
                "label": label,
                "cells": {role["code"]: cells.get(role["code"], "—") for role in roles},
            }
        )
    return {"roles": roles, "permissions": permissions}


def role_holds(role_code: str | None, permission_code: str) -> bool:
    """Does this platform role hold this permission? — the catalogue read.

    ⚠ **THIS READS `role_permissions`, NOT `A4_MATRIX`, AND THAT IS THE WHOLE
    POINT OF IT.** `roles_matrix()` above renders the SIGNED A4 grid, which is
    nine rows and must stay nine rows (`BR-IDN-014`). A permission declared
    outside that grid — today exactly one, `work_accept`, seeded by
    `identity/0005` under the ruling of 2026-09-04 — is a real row in the real
    table and is enforced from there.

    A role code that is not in the catalogue answers **False**, which is
    deny-by-default and the same posture as RLS: an unknown role is not a role
    with everything, it is a role with nothing.
    """
    if not role_code:
        return False
    return RolePermission.objects.filter(
        role__code=role_code, permission__code=permission_code
    ).exists()


def permission_set_for_role(role_code: str) -> dict[str, Any] | None:
    """GET /me/permissions: the caller's OWN row of the A4 matrix, in the same
    vocabulary the /roles grid serves.

    Derived FROM roles_matrix() on purpose (BR-IDN-014): the signed A4 grid is
    transcribed exactly once (models.A4_MATRIX) and read here, so the two
    endpoints can never drift. Only the caller's own cell is read out of each
    row — no other role's column is reachable from this payload, and the
    platform role catalog itself is not enumerated.

    Convenience for UI gating ONLY: the server remains the sole enforcement
    (BR-SHL-025 / 11b G13) — nothing here grants anything.

    None = no such role in the platform catalog (a broken deployment, which the
    API layer answers loudly rather than as an empty permission set).
    """
    matrix = roles_matrix()
    role = next((row for row in matrix["roles"] if row["code"] == role_code), None)
    if role is None:
        return None
    return {
        "role": role["code"],
        "role_name": role["name"],
        "permissions": [
            {"code": row["code"], "label": row["label"], "access": row["cells"][role_code]}
            for row in matrix["permissions"]
        ],
    }


def is_active_system_admin(membership: TenantMembership) -> bool:
    return (
        membership.status == TenantMembership.STATUS_ACTIVE
        and membership.role.code == "system_admin"
    )


def active_system_admin_count(tenant_id: Any) -> int:
    """BR-IDN-013 guard input: ACTIVE System Admin memberships of the tenant."""
    return TenantMembership.objects.filter(
        tenant_id=tenant_id,
        status=TenantMembership.STATUS_ACTIVE,
        role__code="system_admin",
    ).count()


def user_reference_count(user: User, *, exclude_membership: TenantMembership | None = None) -> int:
    """BR-IDN-012 audit-lock ("Used-by", IS-1): references to this member in
    tenant records. W0 tables only — audit_log.actor_user_id (named by the
    rule), tenant_memberships.invited_by, user_preferences.user_id; each
    later wave appends its referencing tables (meter_reads.imported_by,
    bill_runs.run_by, ...)."""
    audit_log = django_apps.get_model("audit", "AuditLog")
    user_preference = django_apps.get_model("tenancy", "UserPreference")
    count = audit_log.objects.filter(tenant_id=user.tenant_id, actor_user_id=user.id).count()
    invited = TenantMembership.objects.filter(invited_by=user)
    if exclude_membership is not None:
        invited = invited.exclude(pk=exclude_membership.pk)
    count += invited.count()
    count += user_preference.objects.filter(user_id=user.id).count()
    return count


def security_policy_values(tenant_id: Any) -> dict[str, Any]:
    """US-IDN-010: the tenant's effective policy — its row, or the BR-IDN-025/
    026 seed defaults when no row exists yet (reads never write a row).

    ⚠ **IT SERVES THE LIMITS WITH THE VALUES (`CR-145-BRC08`).** The six
    settings the PO made per-utility on 2026-09-28 each have a range or a
    choice list, and those live once in `services.SETTING_LIMITS`. Sending
    them down under `limits` is what lets the Security tab render *"3 to 10"*
    and the four timeout choices **without keeping a copy of either** — a
    second copy in TypeScript is a copy that goes stale silently the next time
    the PO moves a ceiling, and nothing in this repo reads rendered output.

    ⚠ **THE KEY IS `limits` AND IT SITS BESIDE THE VALUES, NOT AMONG THEM.**
    `save_security_policy` iterates the field names it is given, so a limits
    entry mixed in with the values would read as a seventh settable field.

    ⚠ **THIS FUNCTION IS ALSO THE ENGINE'S READ**, not only the screen's:
    `services.sign_in`, `auth.IdentitySessionAuthentication.authenticate` and
    `services.refresh_persistent_session` all resolve their numbers here. That
    is deliberate — one read means the number an admin sees on the tab and the
    number the sign-in obeys cannot be two different numbers.

    ⚠ **AND SINCE 2026-09-29 THE LIMITS IT SERVES ARE PER-TENANT IN EXACTLY
    ONE RESPECT: `retained`.** Four ranges became choice lists that day, two
    of them narrower than the range they replaced, so a utility can be sitting
    on a value the redesigned screen no longer offers. **The value is served
    unchanged and the field's entry gains `"retained": <that value>`.** The
    screen draws it as the selected option and marks it as not offered; the
    validator lets it be saved back untouched and refuses any OTHER unoffered
    value by name (`services._validate_policy_values`'s `current` exemption).
    Refusing to render it instead would take the Security tab down for that
    utility, and silently adding it to `choices` would make the product offer
    a value it has withdrawn. Worked case and reasoning:
    `12-governance/02-decision-log.md`, 2026-09-29.
    """
    policy = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    if policy is None:
        # The model field defaults ARE the confirmed seed (BR-IDN-025/026).
        policy = SecurityPolicy(tenant_id=tenant_id)
    return {
        "pw_min_length": policy.pw_min_length,
        "pw_require_mixed": policy.pw_require_mixed,
        "pw_require_symbol": policy.pw_require_symbol,
        "pw_expiry_days": policy.pw_expiry_days,
        "session_timeout_minutes": policy.session_timeout_minutes,
        "absolute_session_hours": policy.absolute_session_hours,
        "keep_signed_in_offered": policy.keep_signed_in_offered,
        "keep_signed_in_days": policy.keep_signed_in_days,
        "lockout_max_failed": policy.lockout_max_failed,
        "lockout_minutes": policy.lockout_minutes,
        "ip_allowlist": list(policy.ip_allowlist or []),
        "field_capture_hours": policy.field_capture_hours,
        # CR-188-BRC10 — an emailed sign-in link's life, days.
        "password_link_valid_days": policy.password_link_valid_days,
        "limits": security_policy_limits(policy),
    }


def field_capture_seconds(tenant_id: Any) -> int:
    """The utility's field-app capture life in SECONDS (PO 2026-10-21, *"this
    should come from settings"*). ONE read for the two credentials it governs —
    the capture token (`apps/work/mobile`) and the native refresh token
    (`identity/native`) — so the life the Security tab shows and the life a
    handset is given cannot be two numbers. A utility with no row reads the
    seeded 168 hours (7 days), like every other setting here."""
    return int(security_policy_values(tenant_id)["field_capture_hours"]) * 3600


def security_policy_limits(policy: SecurityPolicy | None = None) -> dict[str, Any]:
    """What an admin may choose, as plain JSON — `services.SETTING_LIMITS`.

    A choice list serves `choices`; a range serves `min` and `max`; the tick
    box serves `boolean`. `default` rides along so a *Reset to default*
    control needs no second source. Tuples become lists because a tuple is
    not JSON.

    ⚠ **`policy` IS OPTIONAL AND IT DOES EXACTLY ONE THING: IT ADDS BACK THE
    VALUE THIS UTILITY ALREADY HOLDS.** Four ranges became choice lists on
    2026-09-29 and two of those lists are narrower than the range they
    replace, so a utility can be sitting on a value the product no longer
    offers anybody — 23 minutes, say. **That value is inserted into THAT
    UTILITY'S OWN `choices`, in order, and flagged under `retained`.**

    ⚠ **WHY IT IS INSERTED RATHER THAN MERELY FLAGGED, WHICH IS A REVERSAL OF
    THIS FUNCTION'S FIRST VERSION THE SAME DAY.** The first version served the
    platform list untouched and put the held value beside it under `retained`,
    on the reasoning that the product must not go on offering a value it has
    withdrawn. **That is true of the PLATFORM and false of the SELECT.** The
    Security tab builds its dropdown from `choices` alone
    (`optionsFromLimit`), so a `<select>` whose value matches no option falls
    back to the FIRST one: the utility on 23 minutes would have been shown
    *5 minutes*, and the next save — of any other field on the tab — would
    have written 5. A screen that silently misreports a stored setting and
    then changes it is worse than a list with one extra entry on it, and this
    is the mirror of hard-won law 2 that `DEF-CWP-3925` records: a live screen
    telling a confident lie.

    **The list stays honest in every other respect.** The extra entry is
    served only to the utility that holds it, never to anybody else and never
    in the platform-wide answer; `services.SETTING_LIMITS` is untouched; and
    `_validate_policy_values`'s `current` exemption accepts exactly that one
    value and nothing else, so the dropdown and the validator agree row for
    row. Once the utility picks an offered value the entry is gone for good —
    retained, not restored.

    `retained` stays beside it so a screen can badge the option later without
    a second read; nothing renders it today.

    ⚠ **NO `options`, NO RENDERED TEXT.** An earlier version of this function
    published each choice already in words. The Security tab labels its own
    options through `securityValueLabel` and the eleven catalogues, so that
    key was read by nothing — dead data on the wire, which is hard-won law 2
    with the arrow reversed. Deleted rather than left as a fallback.
    """
    # Local import: `services` imports this module at the top, so a
    # module-level import here would be a cycle.
    from apps.identity import services

    published: dict[str, Any] = {}
    for field, limits in services.SETTING_LIMITS.items():
        entry = {
            key: (list(value) if isinstance(value, tuple) else value)
            for key, value in limits.items()
        }
        choices = entry.get("choices")
        if choices is not None and policy is not None:
            held = getattr(policy, field, None)
            if held not in choices:
                entry["retained"] = held
                # In ORDER, so the dropdown reads as a scale rather than
                # putting the odd one out at the end. `None` ("never") sorts
                # first because that is where it already sits in every list
                # that has one.
                entry["choices"] = sorted(
                    [*choices, held], key=lambda value: (value is not None, value)
                )
        published[field] = entry
    return published


# ── The Security tab's own Audit log card (redesign, 2026-09-29) ───────────
#: Five rows, as drawn in `approved-auditcard-1440.png`. A count, not a page:
#: `View all →` opens S61, which is where paging lives.
SECURITY_AUDIT_CARD_ROWS = 5


def security_policy_audit_card(tenant_id: Any, *, limit: int = SECURITY_AUDIT_CARD_ROWS):
    """WHEN · WHO · SETTING · CHANGE — the last five changes on this tab.

    ⚠ **IT SERVES FACTS AND NOT WORDS, AND THAT IS A REVERSAL MADE THE SAME
    DAY (2026-09-29).** For one afternoon this function rendered the pair
    server-side — `480 minutes`, `Never`, `Off` — through an
    `apps/identity/security_render.py` that has since been deleted. The
    Security tab landed that day with `securityValueLabel`, ONE browser
    formatter that already labels the dropdowns AND this card through the
    eleven catalogues, and a second formatter for the same pair is the
    `DEF-IDN-7501` shape rather than a fix for it. Of the two, only the
    browser's can speak eleven languages, so the server sends the field name
    and the two stored values and the browser prints them.

    ⚠ **THE WIRE SHAPE IS THE ONE `endpoints.ts` DECLARES** —
    `{id, changed_at, actor, field, before, after}`, `SecurityPolicyChange`.
    A row the screen has no label for is DROPPED by the card rather than
    printed as a column name (B14 rule 31), which is why a new setting needs
    no server change to stay off this card.

    The rows come from `seams/audit_seam.py`, because audit owns what an audit
    query means — its window floor, its tenant scope, its stable sort.

    ⚠ **AN EMPTY LIST IS AN HONEST ANSWER AND THE PAYLOAD SAYS SO IN A FIELD
    RATHER THAN BY BEING SHORT.** `audit_log` is monthly RANGE-partitioned and
    pruned on a retention schedule, and hard rule 4 forbids any surface from
    calling it a permanent record — so a utility that has changed nothing, and
    one whose history has aged out, both legitimately get `[]`. `complete` is
    False whenever fewer than `limit` changes came back, so a reader can tell
    *there is no more* from *there is more and you asked for five*.
    """
    from apps.identity.seams import audit_seam

    read = audit_seam.security_policy_changes(tenant_id, limit=limit)
    rows = read["changes"]
    return {"rows": rows, "complete": len(rows) >= limit, "scan_capped": read["capped"]}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-IDN-004@9d61512 (EP-IDN-02 list story; also US-IDN-007@9d61512 · US-IDN-008@c4e29d2 · US-IDN-010@493ea2f · session/membership reads for US-IDN-001/003@402b6db — hash = sha256/7 of each source epic)
# generated: 2026-08-09 by story-coder v1 (identity W0 feature-story lane, backend only) · AMENDED 2026-08-09 by story-coder (API-gap lane: permission_set_for_role for GET /me/permissions) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: py_compile✔ · pytest tests -m "not golden and not isolation" 323-green-0-fail at handoff (shared tree, concurrent tenancy lane active) · run_gates 11-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — flagged, deferred with the CI lane · [API-gap lane 2026-08-09] ruff✔(E4/E7/E9/F on the app files — the test tier carries the repo's pre-existing F811 fixture-import pattern) black✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: cross-module READS for the BR-IDN-012 reference count via django_apps.get_model (owning modules expose no selector yet) — Eng disposition recorded above · A4 cell values from the signed grid constant (no B2 column — reported) · API-gap lane 2026-08-09: `permission_set_for_role` is DERIVED from roles_matrix() (one transcription of the signed grid, BR-IDN-014) and exposes only the caller's own cells — GET /me/permissions is NOT an A11/11b row, it exists on the PO's 2026-08-09 "create endpoints for all and integrate" directive; REPORTED for the A11 addendum · [path-tenancy lane 2026-08-10] session_by_id dropped select_related("user"): `users` is RLS'd, so the join was evaluated under the FOREIGN tenant's GUC (or none, on the platform paths) and would have hidden the session row itself — 401 where the law says 404, and a dead /api/jobs/{id}. Proven by test_path_tenancy_isolation_the_session_lookup_survives_a_foreign_guc
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
