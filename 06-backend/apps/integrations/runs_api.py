# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) — 07-endpoints.md rows 10 and 11:
#           `GET /integrations/{key}/runs` (paginated) and
#           `GET /integrations/{key}/runs/{run_id}` (per-item results,
#           `provider_error` to the owning tenant only). Screens: S142
# Rules:    BR-INT-039 (the durable record) · CLAUDE.md hard rule 1 (the read
#           runs under the request's tenant context; another tenant's run is a
#           404 identical to an absent one) · A4 `settings_lookups` (System
#           Admin Full · Executive View) · B8 / LAW 0 (thin: resolve the
#           tenant, call the module, answer — no ORM here)
# Tests:    06-backend/tests/test_us_int_020_runs.py (the API cases, TC-5's
#           cross-tenant 404 among them)
# Impacts:  config/urls.py (one include line) · 06-backend/openapi/schema.json
#           (re-exported: two new paths) ·
#           07-frontend/src/api/integrationsEndpoints.ts
# ───────────────────────────────────────────────────────
"""The two run routes S142 reads — and why they are their own URLconf.

`api.py` carries wave A's and wave B's routes and `mappings_api.py` carries
wave D's, each for the same reason: many lanes share one working tree, and a
lane whose commit touches only its own files cannot revert another lane's
(CLAUDE.md law 11). This costs `config/urls.py` one include line.

    GET /integrations/{key}/runs            the connection's runs, newest first,
                                            twenty by default; filters
                                            operation · outcome · trigger;
                                            `q` searches the trace id ACROSS
                                            THE TENANT and every row names its
                                            own connection
    GET /integrations/{key}/runs/{run_id}   one run, with the items it could
                                            not do and the provider's own
                                            words

⚠ THE LIST NEVER CARRIES `provider_error`. That is not a saving; it is the
mitigation `US-INT-020` §1 proposes, and the split lives in
`runs.row()` / `runs.detail()` so a grep can check it. A list payload is the
thing that gets logged, cached and forwarded; the one column where another
tenant's data can arrive does not travel in it.

⚠ AN UNKNOWN PROVIDER KEY, A RUN OF ANOTHER TENANT AND A RUN THAT NEVER
EXISTED ALL ANSWER THE SAME 404 — the registry's refusal is server-side text,
never a hint that a key exists, and the read is filtered by tenant before the
id is looked at.
"""

from dataclasses import replace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.integrations import runs
from apps.integrations.registry import REGISTRY
from core import errors
from core.pagination import parse_list_params
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups
def runs_list(request: Any, key: str) -> Response:
    """The connection's recent activity, and the trace-id search behind it."""
    tenant_id = require_tenant(request)
    if REGISTRY.get(key) is None:
        raise errors.NotFoundError()
    params = parse_list_params(
        request.query_params,
        allowed_sorts=runs.SORTS,
        default_sort=runs.DEFAULT_SORT,
        allowed_filters=runs.FILTERS,
    )
    # BR-SHL-011's grammar, with this screen's own default window: `dir` falls
    # back to `asc` in the kernel and a run table reads newest first.
    if request.query_params.get("dir") not in ("asc", "desc"):
        params = replace(params, dir="desc")
    return Response(runs.list_view(tenant_id, key, params=params, per=params.per))


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def run_detail(request: Any, key: str, run_id: str) -> Response:
    """One run: its items, its artifact, and the provider's own sentence."""
    tenant_id = require_tenant(request)
    if REGISTRY.get(key) is None:
        raise errors.NotFoundError()
    found = runs.detail_view(tenant_id, key, run_id)
    if found is None:
        raise errors.NotFoundError()
    return Response(found)


urlpatterns = [
    path("integrations/<str:key>/runs", runs_list),
    path("integrations/<str:key>/runs/<str:run_id>", run_detail),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-020@d6d31c46 (EP-INT-06 story + BR-INT-018 · 039 · 040 verbatim; 07-endpoints.md rows 10–11)
# generated: 2026-09-04 by the CR-069 wave C build lane
# checklist: A✔ B✔ C✔ D✔(both routes) E✔(ConnectionDetailPage.tsx consumes both) F✔ G✔ H=n/a(a thin route)
# gates: pytest tests/test_us_int_020_runs.py · openapi export re-run (two new paths) · G6 (no ORM here) · G9 (refusals come from the shared handler)
# exceptions: a separate URLconf from api.py and mappings_api.py, on purpose — recorded in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
