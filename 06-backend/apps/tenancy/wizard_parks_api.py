# ── Trace ──────────────────────────────────────────────
# Change:   CR-035 step 6 part 3 — the ENDPOINTS behind Park.
#           Screens: S19 move-in · S20 move-out · TRF-02 · DSC-02 · the
#           new-connect wizard, plus the "Waiting on" list CR-035 step 6 part 5
#           builds on this list route.
# Rules:    BR-SHL-048 (a parked wizard changes NOTHING until it is executed —
#           PO 2026-08-26) · BR-SHL-047 (every wizard parks) · B19 §12.2 ·
#           BR-SHL-025 (server-enforced RBAC) · BR-SHL-011 (list params) ·
#           BR-TEN-003 (tenant from the path, never client input) ·
#           CLAUDE.md rules 1 · 7
# Defect:   DEF-746 — the control is inert on five of six wizards.
# Tests:    06-backend/tests/test_cr035_wizard_parks.py (every case crosses the
#           wire through config/urls.py — see the note on hard-won law 2 below)
# Impacts:  06-backend/config/urls.py (mounts this list) ·
#           06-backend/openapi/schema.json (the ONE generated snapshot) ·
#           07-frontend `wizardParkPort()` — the port lane's whole switch
# ───────────────────────────────────────────────────────
"""`/wizard-parks` — the HTTP surface a parked wizard needs and did not have.

THIN by law (B8/LAW 0): every verb delegates to `apps.tenancy.wizard_parks`,
there is **no ORM here and no rule here**, and every refusal is a catalog
exception the BE-02 handler renders (G9).

    POST   /wizard-parks        park a draft            -> 201 + the row
    GET    /wizard-parks        ?flow=&mine=            -> the "Waiting on" list
    GET    /wizard-parks/{id}   the row, for resume     -> 200
    PATCH  /wizard-parks/{id}   save more of the form   -> 200
    DELETE /wizard-parks/{id}   discard                 -> 204

WHY THIS PATH FAMILY, AND WHAT IT DELIBERATELY IS NOT UNDER
------------------------------------------------------------
`preferences_api.py` next door documents the reasoning this file follows: a
route lives in the path family of the module that OWNS the table, not the one
whose screens call it. `wizard_parks` is hosted by **tenancy** — platform-shell
has no Django app, and these drafts belong to five flows across TWO modules
(customers and metering), so `/accounts/…` or `/move-ins/…` would put half of
them under a module that does not own them and the other half nowhere.

**A top-level `/wizard-parks` is also the honest shape of BR-SHL-048.** A draft
is not a sub-resource of the unit or the account it names, because the ruling is
that it has no relationship to either until it is executed — there is no FK to
nest it under. The URL says the same thing the schema says.

⚠ **HARD-WON LAW 2 — BUILT IS NOT WIRED — IS WHY THIS FILE EXISTS AT ALL.**
The park PANEL, its nine reasons, the note and the reminder date have been built
and wired in `WizardFrame.tsx` since 2026-08-24; `wizardParkPort()` returns
`null` and its own docstring says *"Returning a port here is the whole switch"*.
Part 1 then landed the table and its RLS policy. Neither half is worth anything
without a route between them, and this product has recorded that same defect
seven times in `config/urls.py`. The test suite resolves every path here THROUGH
`config/urls.py` and calls it over the wired stack, so a future lane cannot lose
the include silently.

ROLE POSTURE, AND IT IS NARROWER THAN THE LISTS NEXT DOOR
----------------------------------------------------------
**AdminOrClerk on every verb, reads included.** Service requests open their
reads to `AnyTenantRole` because A4 gives Executive VIEW on the Premises and
Accounts family. A parked draft is in neither family: BR-SHL-048 says it appears
*"in the clerk's own 'Waiting on' list and in no other surface of the product"*,
and it holds an incoming occupant's name, email and phone BEFORE any customer
row exists. A half-typed form carrying a stranger's phone number is a working
document, not a report, so the read sits where the work sits. The service
re-checks with its own `@require_role` (defence in depth, BR-SHL-025).

**`?mine=` IS A FILTER, NOT A BOUNDARY.** A tenant here has one or two staff and
either of them may pick up the other's draft; the boundary is `tenant_id` and it
is enforced by the queryset AND by RLS FORCE. A `mine` that hid rows from a
colleague would be a rule nobody made, and would strand a draft when its author
is on leave — which is the exact working pattern CR-035 exists to serve.

WHAT THIS SURFACE WILL NOT DO
-----------------------------
It does not execute a parked wizard, and there is no `/execute`. Resuming is the
wizard's job: it rehydrates what was typed, lands on the step it was parked at,
and **re-runs every check before it commits** (BR-SHL-048 (b)) through the same
move-in / move-out / transfer / disconnect / new-connect endpoints it would have
used had the clerk never stopped. Nothing here validates the domain contents of
a draft, resolves the ids in `subject_ref`, or writes anything outside this one
table — that is the ruling, and a convenience added here would quietly undo it.

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.pagination import StandardPagination
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant, tenant_path

from apps.tenancy import wizard_parks as service

#: Query values that mean "yes" on `?mine=`. BR-SHL-011's "never error" posture:
#: anything else is simply not the filter, rather than a 422 on a list.
_TRUE = frozenset({"1", "true", "yes", "on"})


def _actor(request: Any) -> Any:
    """The acting user, server-attached by the identity layer — NEVER client
    input. A `parked_by` in the body would let one member file a draft under
    another's name, and `?mine=` reads that column."""
    return getattr(request, "user", None)


def _payload(request: Any) -> dict[str, Any]:
    body = request.data
    if not isinstance(body, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="shell.wizardPark.objectExpected",
            br_ref="BR-SHL-048",
            params={"field": "body"},
        )
    return body


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])
def wizard_parks(request: Any) -> Response:
    """The "Waiting on" list, and parking a new draft onto it.

    **The list is newest first and every row carries `age_days`.** That is not
    decoration: BR-SHL-048 accepts, in as many words, that a parked move-out is
    invisible to the rest of the product and *"the remind-on date and the
    visible age … are the only thing stopping a draft sitting forever"*. The
    server computes the age with the same arithmetic `parkAgeDays` uses in
    `WizardFrame.tsx`, so the number beside the control inside a wizard and the
    number in the list's AGE column cannot drift apart by a day.

    ⚠ **THE LIST IS PAGINATED** (11b G5 — pagination is mandatory on every
    list), so the body is the DRF envelope `{count, next, previous, results}`
    and the rows are under `results`. `?page=` and `?per=` behave as on every
    other list in the product.
    """
    require_tenant(request)
    if request.method == "POST":
        row = service.park(_actor(request), _payload(request))
        response = Response(service.row_dict(row), status=201)
        response["Location"] = tenant_path(request, f"/wizard-parks/{row.id}")
        return response

    mine = str(request.query_params.get("mine") or "").strip().lower() in _TRUE
    # ⚠ **THE QUERYSET, NOT A LIST — `NFR-3` (DEF-SHL-5748).** This read used to
    # be `paginate_queryset([service.row_dict(row) for row in rows], …)` over
    # `list_parks`, which built a dict for EVERY parked draft in the tenant and
    # then threw away all but fifty. The envelope was correct and no check could
    # see it: a test counting `results` passes on a Python page and on a SQL page
    # alike. `row_dict` is applied to the PAGE, so the work is fifty rows'
    # worth whatever the tenant holds.
    #
    # ⚠ **AND THIS IS A COMMENT RATHER THAN A LINE IN THE DOCSTRING ABOVE, ON
    # PURPOSE.** `drf-spectacular` publishes a view's docstring as the
    # operation's `description`, so a paragraph added up there also edits
    # `06-backend/openapi/schema.json` — the ONE committed generated file
    # (hard-won law 5), which `test_be11_tc05` diffs and which three lanes were
    # editing the same afternoon. How a page is taken is for whoever reads this
    # code, not for a generated client.
    rows = service.parks_queryset(
        flow=request.query_params.get("flow") or None,
        mine_user_id=getattr(_actor(request), "id", None) if mine else None,
    )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response([service.row_dict(row) for row in (page or [])])


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AdminOrClerk])
def wizard_park_item(request: Any, park_id: str) -> Response:
    """One draft: read it to resume, patch it to save more, delete to discard.

    **GET is the resume read, and it writes an audit row** (`wizard_park.
    resumed`) — reasoned in `wizard_parks.resume`: opening a parked move-in is
    an access to a person's name, email and phone before any customer row
    exists, and rule 7 wants the who and the when. One row per open is the
    stated cost.

    **DELETE really deletes, and that is lawful.** CLAUDE.md rule 4's
    immutability governs issued invoices, invoice lines, payments and journal
    lines; a half-typed form has moved no money and posted nothing. 204 with no
    body — there is nothing left to return.

    A draft belonging to another tenant is a **404, never a 403** (HR-1), on all
    three verbs, and RLS FORCE refuses it at the database as well.
    """
    require_tenant(request)
    actor = _actor(request)

    if request.method == "DELETE":
        service.discard(actor, park_id)
        return Response(status=204)

    if request.method == "PATCH":
        row = service.update_park(actor, park_id, _payload(request))
        return Response(service.row_dict(row))

    return Response(service.row_dict(service.resume(actor, park_id)))


urlpatterns = [
    # ⚠ ORDER: `wizard-parks` is all-static and declared above the id route.
    # Django matches whole SEGMENTS, so neither is a prefix of the other and
    # nothing else in `config/urls.py` claims either literal — checked with
    # `grep -rn "wizard-parks" apps/`, not assumed (the `service-requests`
    # entry next door records why that check is written down).
    path("wizard-parks", wizard_parks),
    path("wizard-parks/<str:park_id>", wizard_park_item),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-035 step 6 parts 2-3 (BR-SHL-048 + the PO ruling quoted verbatim in
#         12-governance/02-decision-log.md, 2026-08-26)
# generated: 2026-08-26 by the CR-035 park-service lane (PARKSVC)
# checklist: A✔ B=deferred(the port and resume are lane PARKUI's, built against this contract in parallel) C✔ D✔ E=deferred(no-frontend-half in this lane) F✔ G✔ H=deferred(PO)
# gates: recorded in the lane report — ruff, black, pytest counts and exit
#         codes, G32/G33/G9 and the isolation tier, each with the number that
#         was actually run
# exceptions: reads are AdminOrClerk rather than AnyTenantRole — narrower than
#         the service-request lists next door, reasoned in the module docstring
#         (a draft holds PII and is in neither the Premises nor the Accounts
#         family) · the list is PAGINATED, so the body is the DRF envelope and
#         the rows are under `results` — REPORTED to the port lane, because the
#         contract sentence says "a list" · no `/execute` route: resuming runs
#         the wizard's own endpoints and re-validates there (BR-SHL-048 (b))
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
