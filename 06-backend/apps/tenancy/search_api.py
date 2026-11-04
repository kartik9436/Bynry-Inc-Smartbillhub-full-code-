# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 (EP-SHL-01 — global search across the product)
#           Screens: shell chrome — the topbar box on EVERY authenticated screen
# Defect:   DEF-2423 — "The universal search box accepts text and does nothing,
#           on every screen, with no sign to the user." The box has stated its
#           own absence since 2026-09-01 because `GET /search` did not exist.
#           THIS FILE IS THE ENDPOINT. It is what makes the box work and what
#           lets the honest-absence branch and its copy go away.
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 (nine groups, ≤5 each,
#           prefix-then-recency, per-group View all, by their B2 identifiers) ·
#           BR-SHL-006 (runs under app.tenant_id + RLS FORCE; never another
#           tenant's rows; role-invisible groups OMITTED) · BR-TEN-003 (tenant
#           from the request path, never client input) · A4 (all three roles
#           read all nine surfaces in v1) · B14 rule 31 (no database id is ever
#           the visible value of a field)
# Tests:    06-backend/tests/test_us_shl_003_search.py (endpoint, rank, caps,
#           min-chars, role omission) ·
#           06-backend/tests/test_us_shl_003_search_isolation.py (TC-7 —
#           the mandatory live-Postgres cross-tenant probe)
# Impacts:  06-backend/config/urls.py (mounts this list) ·
#           07-frontend/src/api/endpoints.ts (the typed wrapper) ·
#           07-frontend/src/components/ShellWithSession.tsx (the caller)
# ───────────────────────────────────────────────────────
"""`GET /search?q=` — the ONE global-search endpoint behind the topbar box.

THIN by law (B8/LAW 0): this view parses one query parameter, asks
`core.search.search()` for the groups, and shapes the response. There is no ORM
here, no ranking here and no rule decided here — the rank lives in
`core/search.prefix_then_recency` so nine sources cannot drift apart, and each
group's query lives in the module that owns the table.

WHY THIS PATH LIVES IN `tenancy` (read before "fixing" it)
-----------------------------------------------------------
Platform-shell has no Django app — it is a DOCS module. `apps/tenancy` is where
the other shell-owned surface already lives (`preferences_api.py` serves
US-SHL-013's `GET|PUT /user-preferences/{key}` for exactly this reason), and
this file follows that precedent rather than inventing a second one. The
endpoint is mounted under `/api/{tenant}/` because a search that is not scoped
to a tenant is not a search this product may perform — see below.

⚠ **TENANT SCOPING IS THE WHOLE RISK OF THIS FEATURE AND IT IS DEFENDED THREE
TIMES.** A global search is the only surface in the product that reads nine
tables at once, so a scoping mistake here leaks everything rather than one
screen's worth. The three layers, none of which is decoration:

  1. **The route.** `/api/{tenant}/search` — `require_tenant(request)` resolves
     the tenant from the PATH, server-side, and BE-01's middleware has already
     SET `app.tenant_id` on the database session. A tenant id in a query param
     or a body is never read, here or anywhere (BR-TEN-003).
  2. **The kernel.** `core.search.search()` refuses outright when
     `current_tenant_id()` is None — it raises AUTH-003 rather than running an
     unscoped query. There is no code path that searches without context.
  3. **The database.** Every one of the nine tables carries RLS FORCE with the
     B2 §3 policy, so even a selector that forgot its `tenant_id=` filter would
     return nothing. `tests/test_us_shl_003_search_isolation.py` proves this on
     real PostgreSQL under a NON-SUPERUSER probe role, with a second tenant's
     rows present that the probe would see if the scoping were wrong. A green
     SQLite run proves nothing about RLS and that suite says so.

ROLE-INVISIBLE GROUPS ARE OMITTED, NOT EMPTY (BR-SHL-006)
----------------------------------------------------------
The kernel drops a group the caller's role may not see, so it never reaches this
response and the client cannot render a heading over zero rows. In v1 all three
roles read all nine surfaces (every read route involved is `AnyTenantRole`), so
the clause guards a future role rather than today's — but it is enforced where
it cannot be forgotten, and the client is given no group list to filter.

THE RESPONSE, AND WHY IT CARRIES A `total`
-------------------------------------------
    {"q": "A-104",
     "total": 3,
     "groups": [{"entity": "accounts",
                 "rows": [{"id": …, "label": "A-10432",
                           "context": "Maria Delgado",
                           "amount": null, "currency": null}]}]}

`groups` is a LIST rather than an object so the BR-SHL-005 order is carried by
the wire rather than reconstructed by the client from a hardcoded array — which
is how an eleventh service failed to appear on the sign-up screen (CLAUDE.md's
hard-won law about a front end that types a list out by hand). A group with no
rows is not in the list at all.

`total` is the number of ROWS SHOWN, not a database count. Nothing in this
feature counts matches beyond the cap: nine `COUNT(*)`s per keystroke on a
debounced box is a real cost for a figure nobody acts on, and a "5 of 214" that
was only ever an estimate is worse than no number. The popover's *View all* link
is what answers "how many are there" — it opens the module's own list, which
counts properly.

`id` is for the deep link and is NEVER rendered (B14 rule 31). `label` is the
B2 identifier a person quotes. Money rides as an exact decimal string beside its
CHAR(3) currency and is formatted for display by the client (hard rule 2).

STATUS CODES
------------
  200 always for a signed-in member, including for a query below the two-
      character minimum and for a query that matches nothing. **A no-match is
      not an error**: it renders A18 §2's "No results" pattern, and a client
      that had to catch an exception to learn "nothing matched" would
      eventually stop catching it (the same reasoning `preferences_api` gives
      for never 404-ing an unwritten key).
  401/403 through the BE-04 permission class, rendered by the BE-02 handler.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import permissions, search
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _caller_role(request: Any) -> str:
    """The acting member's tenant role, server-attached by the identity layer.

    NEVER client input. A `role` in the query string would let any member ask
    for the groups of any other, which is the half of BR-SHL-006 that is about
    permission rather than about tenancy. `AnyTenantRole` has already refused an
    anonymous caller, so the fallback here is defence in depth rather than a
    path a request can take.
    """
    role = getattr(request, "tenant_role", None)
    return role if role in permissions.ROLES else ""


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def global_search(request: Any) -> Response:
    """US-SHL-003 — one grouped, capped, tenant-scoped, role-filtered search.

    A4/BR-SHL-025: every signed-in role may search. Finding a record grants
    nothing — the record's own endpoint re-checks the caller's role when they
    open it, and a search that worked for one role and silently returned less
    for another would read as broken data rather than as a permission.
    """
    require_tenant(request)  # BR-TEN-003 — tenant from the PATH; refuses if unresolvable
    query = request.query_params.get("q", "")

    # The kernel enforces the two-character minimum (IS-3), the ≤5 cap and the
    # role omission, and it refuses to run at all without tenant context
    # (BR-SHL-006). Below the minimum it returns {} — silence, never an error.
    grouped = search.search(query, role=_caller_role(request))

    groups = [{"entity": entity, "rows": rows} for entity, rows in grouped.items()]
    return Response(
        {
            "q": query,
            "total": sum(len(group["rows"]) for group in groups),
            "groups": groups,
        }
    )


# Mounted by config/urls.py under `/api/{tenant}/`. It CANNOT live on the
# no-tenant surface: a search with no tenant is a cross-tenant query, which is
# the one thing BR-SHL-006 calls release-blocking.
urlpatterns = [
    path("search", global_search),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-003@EP-SHL-01 + DEF-2423 + the PO ruling of 2026-09-03
# generated: 2026-09-03 by story-coder (universal-search lane)
# checklist: A✔ B✔ C✔ D✔ E✔(ShellWithSession.tsx passes onSearch in this lane) F✔ G✔ H=deferred(PO)
# exceptions: `GET /search` is a PROPOSED A11 addition rather than a contracted
#         row (BR-SHL-005 says so itself) — the addendum row is REPORTED, and
#         this docstring is where the next lane finds out that the contract does
#         not yet name the path the code serves
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
