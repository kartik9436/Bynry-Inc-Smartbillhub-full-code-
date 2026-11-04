# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — the routes behind a connection's named field group
#           (New World's *Send to City folder*): read · save · test · resend.
# Rules:    PO 2026-10-07 (the approved section) · BR-INT-003 (no route
#           returns a password — `GET` serves the masked hint and nothing
#           else) · A4 settings_lookups (any role reads, System Admin writes)
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py
# Impacts:  config/urls.py (one include line) · 07-frontend/src/api/
#           integrationsEndpoints.ts (the four calls)
# ───────────────────────────────────────────────────────
"""`/integrations/{key}/groups/{group}` — in its own URLconf, so this change stays out
of `api.py`, which two GIS lanes are editing the same day (`mappings_api.py` and
`runs_api.py` set the precedent for the same reason)."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.integrations import file_drop
from apps.integrations.api import _actor, _actor_name, _payload
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


@api_view(["GET", "PUT"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def group(request: Any, key: str, group: str) -> Response:
    """`GET` the section (settings, password HINT, recent files) · `PUT` save it."""
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        body = _payload(request)
        return Response(
            file_drop.save(
                actor=_actor(request),
                tenant_id=tenant_id,
                provider_key=key,
                group=group,
                values=dict(body.get("fields") or {}),
            )
        )
    return Response(file_drop.view(tenant_id, key, group))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def group_test(request: Any, key: str, group: str) -> Response:
    """**Test connection** — 200 with `{ok, sentence, server_key, …}`, ok or not.

    A refusal from the far end is an ANSWER, not an error: it comes back 200
    with `ok: false` and its one sentence, the way the card's own test does.
    """
    tenant_id = require_tenant(request)
    return Response(
        file_drop.test(
            actor=_actor(request),
            tenant_id=tenant_id,
            provider_key=key,
            group=group,
            started_by_name=_actor_name(request),
        )
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def group_resend(request: Any, key: str, group: str) -> Response:
    """A person sends one day again: `{day: "2026-10-05", reason: "…"}`."""
    tenant_id = require_tenant(request)
    body = _payload(request)
    try:
        day = date.fromisoformat(str(body.get("day") or ""))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="integrations.refusal.resend_day",
            field_errors=[
                {
                    "field": "day",
                    "code": errors.VAL_FORMAT,
                    "message_key": "integrations.field.required",
                    "params": {},
                }
            ],
        ) from None
    return Response(
        file_drop.resend(
            actor=_actor(request),
            tenant_id=tenant_id,
            provider_key=key,
            group=group,
            day=day,
            reason=str(body.get("reason") or ""),
            started_by_name=_actor_name(request),
        )
    )


urlpatterns = [
    path("integrations/<str:key>/groups/<str:group>/test", group_test),
    path("integrations/<str:key>/groups/<str:group>/resend", group_resend),
    path("integrations/<str:key>/groups/<str:group>", group),
]
