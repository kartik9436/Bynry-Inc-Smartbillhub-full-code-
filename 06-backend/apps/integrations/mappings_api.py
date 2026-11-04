# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-037 (EP-INT-10) — `GET` / `PUT /integrations/{key}/mappings`
#           (07-endpoints.md rows 14 and 15, ADDED by the design). Screens: S143
# Rules:    BR-INT-032 (a foreign name is a row; UNIQUE on the external side) ·
#           BR-INT-031 (an unmapped value shows red; `R02` is OQ-INT-1487's) ·
#           A4 `settings_lookups` (System Admin Full · Executive View · Billing
#           Clerk no cell — the read is refused server-side) · CLAUDE.md hard
#           rule 1 (the read runs under the request's tenant context) · B8 /
#           LAW 0 (thin: resolve the tenant, call the module, answer — no ORM)
# Tests:    06-backend/tests/test_us_int_037_mappings.py (the API cases)
# Impacts:  config/urls.py (one include line) · 06-backend/openapi/schema.json
#           (re-exported: one new path) · 07-frontend/src/api/integrationsEndpoints.ts
# ───────────────────────────────────────────────────────
"""integrations mappings API — the two routes S143 reads and writes.

A SEPARATE URLCONF FROM `api.py`, AND WHY
-----------------------------------------
`api.py` is wave B's file this week — the connect / test / credential / run
routes are landing there — and this wave's two routes are a different story
on a different screen. Mounting them from their own module keeps each lane's
commit to its own file (CLAUDE.md law 11) and costs `config/urls.py` one
include line. It is thin by law: the tenant is resolved, the module is asked,
the answer is returned; every rule lives in `mappings.py`.

    GET  /integrations/{key}/mappings     every row for the target, unmapped first,
                                          with the choices of ours beside them
    PUT  /integrations/{key}/mappings     {"rows": [{entity_type, external_value,
                                          local_value}]} — set one or more; an
                                          empty local_value unmaps

An unknown provider key answers 404 exactly as any absent resource does —
the registry's refusal is server-side text and never a hint that a key exists.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.integrations import mappings
from apps.integrations.registry import REGISTRY, ManifestError
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user with the server-attached tenant role — the shape
    `@require_role` reads (`.role`)."""
    user = request.user
    role = getattr(request, "tenant_role", None)
    if role is not None and getattr(user, "role", None) != role:
        # A thin view object so the service sees ONE actor with ONE role.
        return type("Actor", (), {"id": user.id, "pk": user.pk, "role": role, "user": user})()
    return user


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups
def mappings_view(request: Any, key: str) -> Response:
    """Their words for our things, for one provider — read or set."""
    tenant_id = require_tenant(request)
    if REGISTRY.get(key) is None:
        raise errors.NotFoundError()
    target = request.query_params.get("target") or None
    if request.method == "PUT":
        payload = request.data if isinstance(request.data, dict) else {}
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise errors.ValidationError(
                errors.VAL_REQUIRED, message_key="integrations.refusal.mapping_rows"
            )
        target = payload.get("target") or target
        try:
            mappings.set_rows(
                actor=_actor(request),
                tenant_id=tenant_id,
                provider_key=key,
                rows=rows,
                target_key=target,
            )
        except ManifestError:
            raise errors.NotFoundError() from None
    return Response(mappings.view(tenant_id, key, target_key=target))


urlpatterns = [
    path("integrations/<str:key>/mappings", mappings_view),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-037@87b94265 (EP-INT-10 story + BR-INT-031 · BR-INT-032 verbatim; 07-endpoints.md rows 14–15)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔(ValueMappingPage.tsx consumes both verbs) F✔ G✔ H=n/a(a thin route)
# gates: pytest tests/test_us_int_037_mappings.py · openapi export re-run (one new path) · G6 (no ORM here) · G9 (refusals come from the shared handler)
# exceptions: a separate URLconf from api.py, on purpose — recorded in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
