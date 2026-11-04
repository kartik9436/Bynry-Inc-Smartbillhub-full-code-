# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — `GET/PUT settings/portal` · US-CWP-070 —
#           `GET/PUT settings/portal/branding` (07-endpoints.md §3). Screens:
#           CWP-069 · CWP-070
# Rules:    CR-068 §0 row 18 (`portal_settings` is portal-owned, so its
#           endpoints live HERE and not in apps/tenancy — B2 §2 forbids a
#           cross-module write) · A4 `settings_lookups` (System Admin Full ·
#           Executive View · Billing Clerk no cell — US-CWP-069 TC-9 refuses
#           the clerk server-side) · DEF-196 (any-role read / admin write is
#           ONE class) · US-CWP-069 TC-1 (the QR code)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py ·
#           test_us_cwp_070_branding.py
# Impacts:  config/urls.py (one include) · 07-frontend/src/api/
#           portalSettingsEndpoints.ts (the contract)
# ───────────────────────────────────────────────────────
"""THE BACK OFFICE for the portal — staff-authenticated, in the STAFF app's
Settings → Configure → Customer portal. Three routes under the tenant prefix:

    GET/PUT settings/portal              the address, the on/off, the five, the counts
    GET/PUT settings/portal/branding     the shared four read-only + the portal-only four
    GET     settings/portal/qr.svg       the address as a QR code (`?download=1` to save it)

THIN by law: resolve the tenant, hand a write to `settings_service`, answer
with the selector. The role gate is A4's `settings_lookups` cell through the
one class that encodes it (`SettingsReadAnyWriteSystemAdmin`): an Executive
may read, a System Admin may write, a Billing Clerk is refused 403 on both.
"""

from types import SimpleNamespace
from typing import Any

from django.http import HttpResponse
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.portal import qr, selectors, settings_service
from apps.portal.seams import tenancy_seam
from core import errors, public_origin
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user for the B12 §6a service shape: id from the session user,
    role server-attached by the identity layer — never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    return data


def _origin(request: Any) -> str | None:
    """Scheme and host a customer types before `/{tenant}/portal` — the
    environment's `PUBLIC_APP_ORIGIN` (`core.public_origin`), and NEVER the
    host this request arrived on (`DEF-CWP-9717`).

    ⚠ THIS DOCSTRING READ *"The SPA server forwards `Host` unchanged, so on the
    deployed build this is the utility's public address"* UNTIL 2026-10-05, and
    the body was `request.build_absolute_uri("/")`. That stopped being true in
    `f0739cfc8` (`CR-144-BRC07`, 2.388.0), when the front end became static
    files on its own host and the browser began calling a separate API host:
    the screen then showed `https://api-smart360-sandbox.bynry.com/<slug>/portal`.
    PO ruling 2026-10-05: one setting per environment, the same whoever opens
    the page. `request` is kept in the signature only so the call sites read as
    they did; it is deliberately not consulted. `None` when the setting is
    unset or malformed (law 3) — the address is then absent, never guessed."""
    del request
    return public_origin.public_app_origin()


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups · DEF-196
def portal_settings(request: Any) -> Response:
    """CWP-069's read and write. The address is `tenants.subdomain` as a path;
    the counts are the ones the product can count today (`selectors.usage`)."""
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        settings_service.save_settings(_actor(request), tenant_id, _payload(request))
    return Response(selectors.overview(tenant_id, origin=_origin(request)))


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups · DEF-196
def portal_branding(request: Any) -> Response:
    """CWP-070's read and write. A PUT carrying a shared field (logo, names,
    colours) is refused by name — those are edited in Company → Profile."""
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        settings_service.save_branding(_actor(request), tenant_id, _payload(request))
    return Response(selectors.branding(tenant_id))


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups · DEF-196
def portal_qr(request: Any) -> HttpResponse:
    """`GET /settings/portal/qr.svg` — the address as a QR code, inline for
    the screen and as a download with `?download=1` (B14 rule 4: `↓`)."""
    tenant_id = require_tenant(request)
    address = selectors.address_for(tenancy_seam.branding(tenant_id), _origin(request))
    if address["url"] is None:
        # Law 3: with no public host configured there is no address a customer
        # could reach, and a QR code of the bare path scans to nothing useful.
        # Refuse rather than print a code onto a bill that sends nobody anywhere.
        raise errors.SysError(errors.SYS_INTERNAL)
    body = qr.portal_qr_svg(address["url"])
    response = HttpResponse(body, content_type="image/svg+xml")
    if request.query_params.get("download") == "1":
        response["Content-Disposition"] = f'attachment; filename="{address["slug"]}-portal-qr.svg"'
    return response


urlpatterns = [
    path("settings/portal", portal_settings),
    path("settings/portal/branding", portal_branding),
    path("settings/portal/qr.svg", portal_qr),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-069@87b94265 · US-CWP-070@87b94265 (EP-CWP-12 stories + BR-CWP snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D✔ E✔(SettingsCustomerPortalTab.tsx consumes all three) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_cwp_069_settings.py tests/test_us_cwp_070_branding.py · openapi export re-run (three new paths) · G9 error envelope
# exceptions: `settings/portal/help` and `settings/portal/tips` of 07-endpoints.md §3 are wave D's — stated so their absence is a plan
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
