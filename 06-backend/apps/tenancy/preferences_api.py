# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-013 (EP-SHL-05 — preference storage)
#           Screens: every list screen's column chooser (S14, S15, S17, S25,
#           S26, S27, S30, S33, S34, S37, S45, S49, S108, …)
# Defect:   DEF-647 — "⚠ THERE IS NO CONSUMER, AND NO ENDPOINT. […]
#           `config/urls.py` registers no preferences route." This file is the
#           endpoint; `07-frontend/src/components/DataTable.tsx` is the consumer.
# Rules:    BR-SHL-024 (the storage contract — enforced in preferences.py) ·
#           BR-SHL-027 (server-side ALWAYS, never localStorage-only) ·
#           BR-SHL-013 (`table.‹screen›.columns`; identity column unhideable —
#           the CLIENT's law, asserted in DataTable's suite) ·
#           BR-TEN-003 (tenant from the request path, never client input) ·
#           A4 (a UI preference belongs to its owner: ANY tenant role)
# Tests:    06-backend/tests/test_us_shl_013_user_preferences.py (per-TC,
#           including the isolation case that used to be an it.todo)
# Impacts:  06-backend/config/urls.py (mounts this list) ·
#           06-backend/openapi/schema.json (regenerated from source) ·
#           07-frontend/src/api/endpoints.ts (the typed wrapper)
# ───────────────────────────────────────────────────────
"""`GET|PUT /user-preferences/{key}` — the per-user UI preference store.

THIN by law (B8/LAW 0): both verbs delegate to `apps.tenancy.preferences`;
there is no ORM here and no rule here. Refusals are catalog exceptions rendered
by the BE-02 handler.

WHY THIS PATH, AND WHAT IT DIVERGES FROM (read before "fixing" it)
------------------------------------------------------------------
US-SHL-013 §1 and the 11b row both write `PUT /me/preferences/{key}`. This lane
serves `/user-preferences/{key}` instead, which is the path DEF-647's stated fix
names, for one structural reason: `/me/*` is **identity's** registered route
family (`apps/identity/urls.py` owns `/me`, `/me/password`, `/me/permissions`)
and `user_preferences` is hosted by **tenancy** (migration 0002 — platform-shell
has no Django app). Mounting a tenancy view inside identity's path family would
put one module's route in another module's namespace with no owner.

**The divergence is REPORTED, not resolved**: A11/11b need an addendum row, and
this docstring is where the next lane finds out that the contract and the code
disagree — hard-won law 1 works both ways, and a route that quietly does not
match its contract is the same defect as a comment that quietly does not match
its code.

WHAT IS *NOT* BUILT HERE, AND WHY THAT IS SAID OUT LOUD
--------------------------------------------------------
`GET /me/preferences` (the whole-set read 11b contracts, for shell boot) has NO
route. Nothing reads it today, and DEF-647 is precisely what happens when a
surface is built ahead of its consumer and everyone assumes the round trip
exists. It lands with its first caller.

STATUS CODES
------------
  GET  200 always for a signed-in member — `{"key": …, "value": null}` when
       nothing is stored. **Never 404 on an unwritten key**: BR-SHL-024 says
       "unknown keys read as absent (callers fall back to defaults)" and
       US-SHL-013 TC-6 says "Returns absent (no error)". A 404 is an error in
       every client error path in this app, and a client that has to catch an
       error to learn "you have no preference yet" will eventually stop
       catching it.
  PUT  200 with the stored value. 422 VAL-002/VAL-003 on a bad key, 422 BIZ-CAP
       over the 32 KB cap (TC-4), both BEFORE any write.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.tenancy import preferences
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _caller_user_id(request: Any) -> Any:
    """The acting user's id, server-attached by the identity layer.

    NEVER client input — a `user_id` in the body or the query would let one
    member read another's preferences, which is exactly the leak US-SHL-013
    TC-7 asserts cannot happen. There is no code path here that reads one.
    """
    user = getattr(request, "user", None)
    user_id = getattr(user, "id", None) or getattr(user, "pk", None)
    if user_id is None:
        # Auth already refuses an anonymous caller (AnyTenantRole); defence in
        # depth, never a silently tenant-wide preference row.
        raise errors.AuthError(errors.AUTH_UNAUTHENTICATED, br_ref="BR-SHL-024")
    return user_id


@api_view(["GET", "PUT"])
@permission_classes([AnyTenantRole])
def user_preference(request: Any, key: str) -> Response:
    """The caller's OWN preference for `key`, read and written.

    A4/BR-SHL-025: every signed-in role may manage their own UI preferences —
    a Billing Clerk choosing which columns they see grants them nothing, and
    gating this on System Admin would make the product's column chooser work
    for one person per tenant.
    """
    tenant_id = require_tenant(request)
    user_id = _caller_user_id(request)
    preferences.validate_key(key)

    if request.method == "GET":
        stored = preferences.read_preference(tenant_id, user_id, key)
        # `ABSENT` renders as null with 200 — see the module docstring.
        return Response({"key": key, "value": None if stored is preferences.ABSENT else stored})

    payload = request.data
    if not isinstance(payload, dict) or "value" not in payload:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="settings.preferences.value_required",
            br_ref="BR-SHL-024",
        )
    value = preferences.set_preference(tenant_id, user_id, key, payload["value"])
    return Response({"key": key, "value": value})


# Mounted by config/urls.py under `/api/{tenant}/` — a preference is per user
# AND per tenant (BR-SHL-024), so it cannot live on the no-tenant surface.
urlpatterns = [
    path("user-preferences/<str:key>", user_preference),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-013@EP-SHL-05 + DEF-647
# generated: 2026-08-24 by story-coder (DEF-647 column-preference lane)
# checklist: A✔ B✔ C✔ D✔ E✔(consumer wired in the same lane: DataTable.tsx reads on mount and writes on change) F✔ G✔ H=deferred(PO)
# gates: ruff✔ black✔ · makemigrations --check --dry-run clean✔ (no migration — the table has existed since tenancy 0002) · pytest tests/test_us_shl_013_user_preferences.py✔ · export_openapi regenerated from source (hard-won law 5: one generated file)
# exceptions: the path diverges from US-SHL-013 §1 / 11b's `/me/preferences/{key}` — REPORTED for the A11/11b addendum, reason in the module docstring · `GET /me/preferences` (the whole-set read) is NOT built: no caller exists and building a surface ahead of its consumer is the defect this lane is fixing · no audit row per write (CLAUDE.md rule 7 audits MONEY actions; BR-SHL-024 scopes this table to UI preferences only)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
