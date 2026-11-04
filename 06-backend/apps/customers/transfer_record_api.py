# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-CUS-5949`'s sibling gap — *"a clerk can make a sale and then
#           has no way to read it back"*, ranked FIRST of everything the
#           transfer surface still needs by
#           `04-docs/05-modules/03-customers/conformance/
#           transfer-against-its-blueprint.md` §10.
# Story:    US-CUS-016 (the property sale) · screen `S89.transferRecord`,
#           blueprint `05-prototype/02 Accounts Menu Blueprint.pdf` p133–p134.
# Rules:    B14 rule 31 (no database id is ever the visible value of a field —
#           the address is the transfer NUMBER) · BR-CUS-1030 (a transfer
#           REASSIGNS the account) · BR-CUS-085 (nothing is refunded and
#           re-collected) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule
#           2 (money is a string at 4 decimals, displayed at 2, never computed
#           on a read) · HR-1 (a reference this tenant does not hold is a 404
#           and never a 403)
# Tests:    06-backend/tests/test_transfer_scenarios.py — the `transfer_record`
#           dimension of all twenty-five scenarios
# Impacts:  config/urls.py (this module's `urlpatterns` is included there,
#           AFTER `transfer_disconnect_api` — see the ORDER section below) ·
#           07-frontend/src/features/customers/TransferRecordPage.tsx (the
#           screen that has been waiting for this and rendering its NOT-FOUND
#           branch at every address)
# ───────────────────────────────────────────────────────
"""`GET /transfers/{ref}` — the TRANSFER RECORD, and nothing that writes.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a property was sold last Tuesday and somebody wants to look it up.      ║
╚══════════════════════════════════════════════════════════════════════════╝

**The screen has existed since `TransferRecordPage.tsx` landed and has drawn
its NOT-FOUND branch at every address**, because nothing answered. Its own §2
says so: *"`GET /transfers/{ref}` DOES NOT EXIST AT THE COMMIT THAT LANDS THIS
FILE. A sibling lane is building it."* This is that lane.

────────────────────────────────────────────────────────────────────────────
⛔ WHY THIS IS ITS OWN MODULE AND NOT ONE LINE IN `api.py` — AND IT IS AN
   ORDERING FACT, NOT A PREFERENCE
────────────────────────────────────────────────────────────────────────────
`config/urls.py` includes `apps.customers.api` **before**
`apps.customers.transfer_disconnect_api`, and Django matches by PATH and not
by method — *"a duplicate path SHADOWS rather than merges"*, which that file
says in its own words. `transfers/commit` and `transfers/buyer-preview` are
two-segment paths, and so is `transfers/<str:ref>`.

**So declaring this route in `api.py` would have swallowed `POST
/transfers/commit`** — every property sale in the product answering 405 from a
GET-only view. `transfer_disconnect_api.py` anticipated exactly this in a
comment above its own list: *"the next lane to add `transfers/<id>` would
create that collision silently."*

The route therefore lives in a module of its own, included **after** the one
that owns the literal segments, so `commit`, `buyer-preview`, `{id}/money` and
`{id}/cancel` all match first and this catch-all matches last. It is
`communication_api.py`'s precedent — *"a module may export its own
`urlpatterns` and `config/urls.py` includes them"* — used here for a second
reason on top of that one: `api.py` is the file several lanes hold at once, and
a pathspec commit naming it publishes whatever else is sitting in it (law 11,
mechanism five).

────────────────────────────────────────────────────────────────────────────
THE ADDRESS IS THE REFERENCE, NEVER THE UUID (B14 rule 31)
────────────────────────────────────────────────────────────────────────────
The blueprint's own URL is `/brazosbend/transfers/trf-26-0021`, and
`TRF-26-0001` is what a clerk quotes down a phone — ruled by the PO on
2026-08-27 when `OQ-426` closed, in the words *"Transfer TRF-26-0001 … follow
same logic that we are following for other numbers we have did in settings"*.

⚠ **THE PARAMETER IS NAMED `ref` AND NOT `transfer_id`, AND THAT IS NOT
COSMETIC.** `transfer_disconnect_api` spells its two wildcards
`<str:transfer_id>` because they take an id; this one takes a NUMBER, and a
route spelled `transfer_id` is the next reader's invitation to pass one.
`moves/<str:ref>` one file over is the same decision for the same reason.

The layer below accepts a uuid as a FALLBACK — a tenant provisioned before the
`transfer` series was seeded has no catalogue row and its sales carry
`transfer_no = NULL`, which would otherwise be unreadable for ever. That is a
way IN and never a way to DISPLAY one: the payload serves the server's own
stated absence for `reference`, so no database id is ever a field's visible
value.

────────────────────────────────────────────────────────────────────────────
NOTHING HERE WRITES, AND THAT IS THE DRAWING'S RULING RATHER THAN AN OMISSION
────────────────────────────────────────────────────────────────────────────
The blueprint says it under the drawing, in its own words: *"This record has no
actions, and that is the answer rather than a gap. A move-in and a transfer are
records of acts that have already happened — there is nothing left to decide on
them, so the only controls are doors to the accounts they produced. Drawing a
button here would invent a decision the product does not offer."*

**So this module exports ONE view, it is GET-only, and it has no sibling that
writes.** `move_record_detail` in `api.py` reached the same conclusion
independently, which is the only evidence either is right.
"""

from __future__ import annotations

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.permissions import AdminOrClerk
from core.tenancy import require_tenant

from apps.customers import transfer_reads


@api_view(["GET"])
@permission_classes([AdminOrClerk])  # the MONEY box — see below
def transfer_record_detail(request: Any, ref: str) -> Response:
    """`GET /transfers/{ref}` — the TRANSFER RECORD screen (blueprint p133).

    The assembly is `transfer_reads.record_detail` and this view adds nothing
    to it: no figure is computed here, no absence is defaulted, and nothing is
    written.

    ⚠ **`AdminOrClerk`, NOT `AnyTenantRole`, and it is the same reasoning
    `move_record_detail` and `transfers_list` both carry.** This page draws a
    MONEY section, and the deposit statement the layer below builds is gated
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`. Handing an Executive a figure
    the service beneath refuses them is the defect that rule exists to prevent,
    and matching the narrower gate is the precedent the transfers LIST already
    set on this same resource.
    """
    require_tenant(request)
    return Response(transfer_reads.record_detail(ref))


urlpatterns = [
    # ⚠ **A CATCH-ALL ON `transfers/`, WHICH IS WHY IT IS ALONE IN THIS FILE
    # AND WHY `config/urls.py` INCLUDES IT LAST.** `<str:ref>` matches
    # `commit` and `buyer-preview` as happily as it matches `TRF-26-0001`;
    # ordering is the only thing that keeps the sale's own door open, and the
    # module docstring holds the whole argument.
    path("transfers/<str:ref>", transfer_record_detail),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: transfer-against-its-blueprint.md §10 · transfer-record-what-is-durable.md ·
#         07-frontend/src/features/customers/TransferRecordPage.tsx (the wire shape) ·
#         apps/customers/api.py `move_record_detail` (the precedent) ·
#         apps/customers/transfer_disconnect_api.py (the literal segments this must not
#         shadow) · B14 rule 31 · BR-CUS-1030 · BR-CUS-085
# generated: 2026-09-20 by lane TRANSFER BACKEND
# checklist: A✔ B=n/a(the screen was built by an earlier lane and is waiting on this)
#            C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# ──────────────────────────────────────────────────────────
