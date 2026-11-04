# ── Trace ──────────────────────────────────────────────
# Component: BE-04 RBAC enforcement (B13 §3, W0 kernel lane — component packet)
# Contract:  A4 addendum (3 predefined roles + matrix) · B12 r1 §3-expanded (403 vs 404) ·
#            11b §3 G13 (server-enforced RBAC; UI gating is convenience)
# Rules:     BR-IDN-009 (server-enforced, System-Admin-only user mgmt as the pattern) ·
#            BR-SHL-025 (server independently enforces every mutating call) ·
#            BR-TEN-003 / HR-1 (cross-tenant = 404 never 403, via core.errors)
# Tests:     06-backend/tests/test_be04_permissions.py
# Impacts:   every api.py permission_classes · every service mutating on behalf of an actor
# ───────────────────────────────────────────────────────
"""BE-04 — server-side enforcement of the three predefined tenant roles.

Roles per A4 addendum (CONFIRMED 2026-08-07): SYSTEM_ADMIN, BILLING_CLERK,
EXECUTIVE — platform-defined, not tenant-editable. Matrix:
04-docs/01-spec/04-roles-permissions.md. UI gating is convenience only; the
checks HERE are the enforcement (BR-SHL-025, 11b G13).

Where the role comes from: the identity module's auth layer attaches the
member's role for the resolved tenant to the request as `request.tenant_role`
(one user = one tenant = one role, B2 r11). That attribute is server-derived
from the session — never client input. Until the identity story lands, no
request carries a role, so every role-gated endpoint denies — deny-by-default,
same posture as RLS.

Denial routing (the law this module encodes):
- not signed in            → DRF NotAuthenticated → 401 AUTH-001 (BE-02)
- signed in, wrong role    → DRF PermissionDenied → 403 AUTH-002 (BE-02)
- resource in ANOTHER tenant → NEVER a 403 — raise core.errors.deny_as_not_found()
  at the object lookup so the response is an indistinguishable 404 (HR-1);
  the denial is still recorded as a BR-AUD-018 attempt row by the handler.

Every denial that reaches the API surface writes its attempt row centrally in
core.errors.drf_exception_handler — endpoints and services never hand-write
attempt rows (BR-AUD-018, G15).
"""

import inspect
from collections.abc import Callable
from typing import Any

from rest_framework.permissions import BasePermission

# The three predefined tenant roles (A4 addendum; values are the wire/DB codes).
SYSTEM_ADMIN = "system_admin"
BILLING_CLERK = "billing_clerk"
EXECUTIVE = "executive"
ROLES = frozenset({SYSTEM_ADMIN, BILLING_CLERK, EXECUTIVE})
#: The field app's login (`BR-WRK-043`). ⚠ **DELIBERATELY NOT IN `ROLES`** —
#: adding it there would grant every read surface in the product in one line
#: (`US-WRK-023` TC-4). It is admitted by `FieldAppRole` below, by name, on
#: exactly the routes the field app calls.
FIELD_TECHNICIAN = "field_technician"


def _role_of(request: Any) -> str | None:
    """The server-attached tenant role, or None (unauthenticated / no member)."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    role = getattr(request, "tenant_role", None)
    return role if role in ROLES else None


class RoleRequired(BasePermission):
    """Base class: allow only requests whose tenant role is in allowed_roles.

    Returning False lets DRF raise NotAuthenticated (no credentials) or
    PermissionDenied (wrong role) — BE-02 renders those as 401 AUTH-001 /
    403 AUTH-002, and the handler writes the BR-AUD-018 attempt row.
    """

    allowed_roles: frozenset[str] = frozenset()

    def has_permission(self, request: Any, view: Any) -> bool:
        return _role_of(request) in self.allowed_roles


# Concrete classes covering the A4 matrix columns (endpoints pick one; a
# finer per-action split stays per-endpoint — the matrix rows are per area).
class AnyTenantRole(RoleRequired):
    """Signed-in member of THIS tenant, any role — read surfaces open to all 3."""

    allowed_roles = ROLES


class FieldAppRole(BasePermission):
    """The field app's routes: any office role, AND a field technician.

    `DEF-WRK-9593` (critical, 2026-10-04). Every route the field app calls was
    `AnyTenantRole`, whose comments said it admitted the technician — it never
    did, because `_role_of` answers None for any role outside `ROLES`. So a
    technician who could finally sign in (`DEF-WRK-9583`) met 403 on `/me`, on
    `/me/password` — an invited technician could never set a password — and on
    their own day. **Use this ONLY on a route the field app calls**; a route
    that serves another person's job must ALSO scope to the technician's own
    (the work module's `mobile.require_own_job`), because this class decides
    WHO may knock and not WHICH job they may open.
    """

    allowed_roles: frozenset[str] = ROLES | {FIELD_TECHNICIAN}

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return getattr(request, "tenant_role", None) in self.allowed_roles


class SystemAdminOnly(RoleRequired):
    """Settings, lookup tables, user management (A4: System Admin Full, others —/View)."""

    allowed_roles = frozenset({SYSTEM_ADMIN})


class SettingsReadAnyWriteSystemAdmin(RoleRequired):
    """Any tenant role may READ; only a System Admin may WRITE. DEF-196.

    ⚠ THIS CLASS EXISTS BECAUSE A RULING AND THE PRODUCT DISAGREED FOR A DAY,
    and every test stayed green through it.

    The PO ruled 2026-08-16, across CR-005/006/007: *"all settingsa re Admin
    only I believ; follow same rule that we folowed for settings related
    permission"* — and separately, that a Billing Clerk and an Executive **may
    LOOK at** numbering formats, routes, cycles and templates and **may not
    change them**. A4 backs it: those roles carry `Settings & lookup tables:
    View`. BR-SHL-025 then requires the controls stay **VISIBLE AND DISABLED
    WITH THEIR REASON**, never hidden.

    What shipped instead: eight Settings views in `apps/tenancy/api.py` served
    GET and a write from ONE function under `SystemAdminOnly`, so **the READ
    answered 403** and a non-admin saw *"You don't have access to this."* Every
    `readOnly` branch in those screens was unreachable code — the frontend
    computed `readOnly` correctly and nothing could ever produce it.

    **235 green frontend tests could not see it**, because they pass `readOnly`
    as a PROP: they ask what the component does *with* the state, never whether
    the running product can *produce* it. Hard-won law 2, exactly. It was found
    by signing in as an Executive and clicking.

    Why a permission class rather than eight per-view `if request.method`
    branches: the split is one RULE, so it belongs in one place where it can be
    read, tested and cited. A branch repeated eight times is eight chances to
    write it seven times.

    ⚠ THIS IS A READ GATE ONLY, NEVER THE WHOLE GUARD. The services underneath
    keep their own `@require_role(SYSTEM_ADMIN)`, so a write refuses twice —
    the narrower gate refusing first. Removing either one must still leave the
    write refused, and the tests assert both.

    ⚠ **THE READ IS NOT OPEN TO ALL THREE ROLES, AND THE FIRST CUT OF THIS FIX
    GOT THAT WRONG.** A4's `settings_lookups` row reads
    `{"system_admin": "Full", "executive": "View"}` — **a Billing Clerk has no
    cell at all**, which means no access, not read-only access. The PO's own
    words were *"all settingsa re Admin only I believ; follow same rule that we
    folowed for settings related permission"*, and "the same rule" IS A4.

    Opening the read to `ROLES` sailed past every new test written for this
    defect and was caught by `US-TEN-009 TC-5`, a story case that has asserted
    *"clerk denied at the reference-data surface"* since the surface was built.
    **The old test was right and the new fix was wrong** — which is the whole
    argument for not deleting a red test until you know which of the two is.
    """

    #: A4 `settings_lookups`: Full and View both READ. Kept as an explicit set
    #: rather than `ROLES` because the difference between them is a real cell in
    #: a signed matrix, and `test_def_196__the_read_roles_match_the_a4_matrix`
    #: asserts this set against `A4_MATRIX` itself so the two cannot drift.
    allowed_roles = frozenset({SYSTEM_ADMIN, EXECUTIVE})

    #: Verbs that mutate nothing. Everything else needs System Admin.
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = _role_of(request)
        if role is None:
            return False  # 401 AUTH-001, unchanged
        if request.method in self.SAFE_METHODS:
            return role in self.allowed_roles
        return role == SYSTEM_ADMIN


class ShellDisplayRead(RoleRequired):
    """`GET /shell/display` — what a screen needs to DRAW. Read-only, all roles.

    ⚠ **THIS CLASS EXISTS BECAUSE A BILLING CLERK COULD NOT USE THE PRODUCT AT
    ALL FOR SIXTEEN DAYS (`DEF-SHL-4272`, 2026-08-21 → 2026-09-06).**

    The app shell boots by reading the tenant's branding and its date/number
    formats, and both reads were served by the Settings endpoints under
    `SettingsReadAnyWriteSystemAdmin`, whose `allowed_roles` is
    `{system_admin, executive}` because A4's `settings_lookups` row gives a
    Billing Clerk no cell. So a clerk signed in successfully, reached
    `/dashboard`, and **every screen in the product rendered the shell's failure
    state** — *"We couldn't load your regional settings."* with a Retry that
    could never succeed.

    **THE OBVIOUS FIX IS THE WRONG ONE AND IS DELIBERATELY NOT TAKEN.** Widening
    `SettingsReadAnyWriteSystemAdmin` re-opens `DEF-196`: that class's own
    docstring records the first cut of that fix opening the read to every role,
    sailing past every test written for it, and being caught by `US-TEN-009
    TC-5`. A4 is a signed matrix and a Billing Clerk having **no cell** means no
    access, not read-only access. The settings SURFACE is unchanged by this
    class and stays admin/executive on all twelve of its views.

    **THE DISTINCTION THIS CLASS ENCODES: FORMATTING AND BRANDING ARE NOT
    SETTINGS ADMINISTRATION.** A date format is not a policy a clerk may look
    at — it is a fact the renderer needs before it can print a date at all, in
    the same way the tenant's logo is a fact the sidebar needs before it can
    draw the sidebar. `GET /shell/display` therefore serves the DISPLAY fields
    and nothing else: it carries no `accounting_method`, no `close_cadence`, no
    `close_day` and no `lock_closed_periods` — the four finance-policy fields
    that ride along on `GET /settings/regional` and that a clerk should not
    receive merely to draw a date.

    **WHY READ-ONLY RATHER THAN WRITE-GATED.** `SettingsReadAnyWriteSystemAdmin`
    splits by verb because its endpoints answer both. This one answers GET and
    nothing else, and the class refuses every mutating verb for **every** role
    including the System Admin — so if a later lane adds a `PUT` to the view,
    the permission refuses it rather than silently opening a second write path
    around `PUT /settings/regional`'s validation and audit trail. There is one
    door to these values and it is the Settings screen.

    ⚠ **THE PRECEDENT ALREADY EXISTED AND WAS NOT GENERALISED, WHICH IS HOW THIS
    SURVIVED.** `GET /settings/company/logo/file` has been `AnyTenantRole` since
    `CR-048` wave D on exactly this reasoning — its docstring says *"the app
    header draws the mark for whoever is signed in"*. The bytes of the logo were
    readable by a clerk while the NAME beside them was not.
    """

    #: All three tenant roles. Not A4's `settings_lookups` row, and never
    #: derived from it — the whole point of this class is that these values are
    #: not that row's subject. `test_def_shl_4272__the_shell_gate_is_not_the_
    #: settings_gate` asserts the two sets are different on purpose.
    allowed_roles = ROLES

    #: Verbs that mutate nothing. Everything else is refused for every role.
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = _role_of(request)
        if role is None:
            return False  # 401 AUTH-001, unchanged
        if request.method not in self.SAFE_METHODS:
            return False  # no write door here, not even for a System Admin
        return role in self.allowed_roles


#: ⚠ **THE ONE AMENDMENT TO A4's `settings_lookups` ROW, AND IT IS A READ.**
#: PO ruling 2026-10-02, verbatim: *"5. Should a billing clerk see the size
#: lists New Connection needs? A · Let the billing clerk read the size and
#: equipment lists (read only)."* (`DEF-CUS-9048`, decision log top row.)
#: New Connect step 3 reads exactly these two reference lists and the work
#: templates list; a Billing Clerk was refused all three, so a build the clerk
#: ran sized nothing and gave trash and fire no equipment.
#: **Exactly two list codes, by name.** Every other `/lookups/<list>` stays
#: `SettingsReadAnyWriteSystemAdmin` — no cell for the clerk — and no WRITE on
#: any list moves. `apps/identity/models.py` `A4_CLERK_READ_GRANTS` restates
#: this set for the role table and a test holds the two equal.
NEW_CONNECTION_CLERK_LOOKUPS = frozenset({"asset_types", "service_size_classes"})


class NewConnectionLookupRead(SettingsReadAnyWriteSystemAdmin):
    """`GET /lookups/<list>` — A4's Settings gate, plus a Billing Clerk READ of
    the two lists New Connect step 3 sizes from (PO 2026-10-02, `DEF-CUS-9048`).

    A subclass and not a widened parent, because widening the parent re-opens
    `DEF-196` on every Settings tab (that class's own docstring). The clerk is
    admitted ONLY on a safe verb and ONLY when the routed `list_code` is one of
    `NEW_CONNECTION_CLERK_LOOKUPS`; a POST, or any other list, falls through to
    the parent's answer unchanged.
    """

    clerk_lists = NEW_CONNECTION_CLERK_LOOKUPS

    def has_permission(self, request: Any, view: Any) -> bool:
        if (
            _role_of(request) == BILLING_CLERK
            and request.method in self.SAFE_METHODS
            and (getattr(view, "kwargs", None) or {}).get("list_code") in self.clerk_lists
        ):
            return True
        return super().has_permission(request, view)


class WorkTemplateListRead(SettingsReadAnyWriteSystemAdmin):
    """`GET /work/templates` — the list New Connect step 3 adds work from, READ
    by a Billing Clerk too (PO 2026-10-02, `DEF-CUS-9048`).

    Only the LIST route carries this class. A template's own record, its
    versions and every publish/duplicate/deactivate door keep
    `SettingsReadAnyWriteSystemAdmin`, and `POST /work/templates` (a new draft)
    still needs a System Admin — the parent answers every unsafe verb.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        if _role_of(request) == BILLING_CLERK and request.method in self.SAFE_METHODS:
            return True
        return super().has_permission(request, view)


class AdminOrClerk(RoleRequired):
    """Operational writes: premises/accounts/reads/billing runs/payments record."""

    allowed_roles = frozenset({SYSTEM_ADMIN, BILLING_CLERK})


class ConnectionsReadAnyWriteAdminOrClerk(RoleRequired):
    """`/connections`: any tenant role may READ the list; a WRITE is A4's.

    CR-070 wave B (`US-WRK-002`). One path, two verbs, two different answers —
    and Django can reach only the FIRST view registered on a path, so `GET
    /connections` and `POST /connections` cannot be two views. The split is one
    RULE, so it lives in one place that can be read, tested and cited, exactly
    as `SettingsReadAnyWriteSystemAdmin` above records for Settings: *"a branch
    repeated eight times is eight chances to write it seven times."*

    The read is `ROLES` and not a narrower set, because that is what
    `GET /connections` already served before this class existed and A4 gives the
    Executive VIEW across the operational modules. The write is
    `AdminOrClerk`'s own set — A4 gives the Billing Clerk *"full on
    Premises/Accounts"* — which is why `US-WRK-002` TC-3's server-side refusal
    is demonstrated with an EXECUTIVE and not with the Clerk the story names.

    ⚠ **A READ GATE IS NEVER THE WHOLE GUARD.** `create_connection` carries no
    `@require_role` of its own (no function in `connections.py` does), so this
    class is currently the only thing between an Executive and a draft build.
    That is a real asymmetry with the Settings family above, where the service
    refuses a second time, and it is stated rather than papered over: the Work
    permission set is `US-WRK-022`, and phase 0 is explicitly not blocked on it.
    `OQ-WRK-1492` — who may ACCEPT a finished job — was RULED on 2026-09-04: a
    clerk may, *"sicne it s a day to day work"*.
    """

    #: A4: the Executive has VIEW across operational modules, so all three read.
    allowed_roles = ROLES

    #: Verbs that mutate nothing.
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    #: A4 `premises/accounts`: Full for System Admin and Billing Clerk.
    WRITE_ROLES = frozenset({SYSTEM_ADMIN, BILLING_CLERK})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = _role_of(request)
        if role is None:
            return False  # 401 AUTH-001, unchanged
        if request.method in self.SAFE_METHODS:
            return role in self.allowed_roles
        return role in self.WRITE_ROLES


class JournalEntryReadAnyDeleteAdminOrClerk(RoleRequired):
    """`/ledger/journal-entries/{id}`: any tenant role READS; only A4's may DELETE.

    `DEF-LED-6723`. The same shape and the same cause as
    `ConnectionsReadAnyWriteAdminOrClerk` above — **one path, two verbs, and
    Django reaches only the first view registered on a path** — and this is the
    case that made the cost visible: the path was registered DELETE-only, so
    `GET /ledger/journal-entries/{id}` (named by `11b` §2.10 and drawn as the
    `👁` on Finance blueprint p020) could not be added anywhere, and the
    Journal's view control shipped disabled for five weeks.

    **THE READ IS `ROLES` AND THE DELETE IS NOT.** A4 gives Finance *R* to
    Staff and Clerk and *CRUD* to the Executive, and every other ledger read
    (`apps/ledger/api.py`, four routes) is `AnyTenantRole` — a detail an
    Executive may not open, of a list they may read, would be an odd book.
    The DELETE keeps `AdminOrClerk` UNCHANGED: it is the PO's closure of
    OQ-175 on 2026-08-12 (*"System Admin and Billing Clerk … Executive may
    not"*) applied to the manual-JE lifecycle, and widening it here would move
    a ruling by accident.

    ⚠ **THE DELETE'S REAL GUARD IS NOT THIS CLASS.** `posting.delete_draft`
    checks the status and `ledger/0007`'s trigger sits under it, so a posted
    entry is refused whatever role asks. This class decides WHO MAY ASK, and it
    is deliberately no weaker than the one it replaces on that verb.
    """

    #: A4: Finance is R for Staff and Clerk, CRUD for the Executive.
    allowed_roles = ROLES

    #: Verbs that mutate nothing.
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    #: Unchanged from the `AdminOrClerk` this path carried before the GET.
    WRITE_ROLES = frozenset({SYSTEM_ADMIN, BILLING_CLERK})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = _role_of(request)
        if role is None:
            return False  # 401 AUTH-001, unchanged
        if request.method in self.SAFE_METHODS:
            return role in self.allowed_roles
        return role in self.WRITE_ROLES


class WorkOrdersReadAnyWriteAdminOrClerk(RoleRequired):
    """`/work-orders`: any tenant role may READ the list; raising one is A4's.

    CR-070 wave B (`US-WRK-002`), the same shape and the same reason as
    `ConnectionsReadAnyWriteAdminOrClerk` above: one path, two verbs, and Django
    reaches only the first view registered on a path.

    Kept as its own class rather than sharing the connections one, because the
    two families are separate cells in A4 and the day one moves the other must
    not move with it by accident. `US-WRK-022` is where the Work permission set
    is built; the raise sits with the roles that already hold operational
    writes, which is where every other job-shaped write in this product sits.

    ⚠ `OQ-WRK-1492` — who may ACCEPT a finished job, which is the press that
    puts a service live — was RULED on 2026-09-04: **a clerk may**, *"sicne it
    s a day to day work"*. A field technician cannot, and needs no rule of its
    own for it: `OQ-WRK-1494` keeps their login off the web app entirely, and
    the Accept control is there.
    """

    allowed_roles = ROLES
    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
    WRITE_ROLES = frozenset({SYSTEM_ADMIN, BILLING_CLERK})

    def has_permission(self, request: Any, view: Any) -> bool:
        role = _role_of(request)
        if role is None:
            return False  # 401 AUTH-001, unchanged
        if request.method in self.SAFE_METHODS:
            return role in self.allowed_roles
        return role in self.WRITE_ROLES


class AdminOrExecutive(RoleRequired):
    """Finance/reconcile/export + approvals (A4: Approve = System Admin, Executive)."""

    allowed_roles = frozenset({SYSTEM_ADMIN, EXECUTIVE})


def require_role(*allowed: str, br_ref: str = "BR-IDN-009") -> Callable:
    """Service-layer guard: @require_role(SYSTEM_ADMIN) above a service function.

    The decorated function must take the acting user as its `actor` parameter
    (the B12 §6a service shape); the actor's `.role` attribute is checked.
    Wrong/missing role raises AuthError AUTH-002 — the API layer's BE-02
    handler renders the 403 and writes the attempt row; job callers get the
    same exception and their runner records it.

    Server-side enforcement is THE enforcement (BR-SHL-025): a service guarded
    here refuses no matter which endpoint, job, or shell forgot to gate.
    """
    unknown = set(allowed) - ROLES
    if unknown:
        raise ValueError(f"unknown role(s) {sorted(unknown)} — roles are platform-defined (A4)")
    allowed_set = frozenset(allowed)

    def decorator(fn: Callable) -> Callable:
        signature = inspect.signature(fn)
        if "actor" not in signature.parameters:
            raise TypeError(
                f"@require_role needs {fn.__name__}() to declare an 'actor' parameter (B12 §6a)"
            )

        def guarded(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(*args, **kwargs)
            actor = bound.arguments.get("actor")
            role = getattr(actor, "role", None)
            if role not in allowed_set:
                from core import errors  # local import keeps module import order trivial

                raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref=br_ref)
            return fn(*args, **kwargs)

        guarded.__name__ = fn.__name__
        guarded.__doc__ = fn.__doc__
        guarded.__wrapped__ = fn  # type: ignore[attr-defined]
        return guarded

    return decorator


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-04@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be04_permissions.py 12/12✔ · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
