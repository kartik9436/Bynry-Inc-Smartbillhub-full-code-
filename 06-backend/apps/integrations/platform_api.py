"""Text messages provided by the platform — the card's read, its Test, and Twilio's two doors.

`CR-198-BRC10` (PO 2026-10-29, ruling 4B: one shared platform Twilio account).

    GET  /api/{utility}/integrations/{key}/platform          the card's state
    POST /api/{utility}/integrations/{key}/platform-test     one real text (System Admin)
    POST /api/{utility}/integrations/platform/sms_twilio/status   Twilio → us (signed)
    POST /api/hooks/twilio/reply                              Twilio → us (signed)

⚠ **THE CARD READ SERVES NO SECRET.** `platform_sms.card_state` answers booleans,
codes and a masked sender tail; this view adds when a text last left and the
last failure's words — Twilio's error code and message, which name no
credential. A test asserts no `TWILIO_*` value reaches the response.

⚠ **THE TWO DOORS OPT OUT OF THE DEFAULT AUTHENTICATOR**, like the inbound
door: Twilio has no session. They are named in
`tests/test_be_default_authentication.py`'s `PUBLIC_ROUTES` deliberately. Each
proves itself by `X-Twilio-Signature` (`platform_door.verify`); a refusal is
`401` with the five words every refused machine gets, and nothing is saved.

⚠ **THE REPLY DOOR HAS NO UTILITY IN ITS PATH, ON PURPOSE.** A shared sender's
incoming-message webhook is ONE address for every utility, set once on the
Messaging Service. `hooks` is a no-tenant first segment
(`core.tenancy.NON_TENANT_SEGMENTS`) and a reserved slug, so no utility can be
named `hooks` and be shadowed here. The door then applies a STOP inside each
concerned utility's own tenant context (`platform_door.reply`).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.integrations import platform_door, platform_sms
from apps.integrations.registry import MODE_PLATFORM_HOLDS_OURS, REGISTRY
from apps.integrations.runners import serve
from apps.integrations.seams import notifications as notifications_seam
from apps.integrations.seams import tenancy as tenancy_seam
from core import audit as core_audit
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin

REFUSED_STATUS = 401
AUDIT_TEST = "integration.test_run"
#: Twilio reads the reply to an incoming text as instructions; an empty
#: `<Response/>` says *send nothing back* — the carrier's own opt-out
#: confirmation is Twilio's to send.
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _platform_manifest_or_404(key: str):
    manifest = REGISTRY.get(key)
    if manifest is None or manifest.auth.mode != MODE_PLATFORM_HOLDS_OURS:
        raise errors.NotFoundError()
    return manifest


def _mask(number: str) -> str:
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    return f"***{digits[-2:]}" if len(digits) >= 2 else "***"


@api_view(["GET"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def platform_card(request: Any, key: str) -> Response:
    """The card: provided by the platform, configured or not, sender kind and a
    masked tail, callbacks on or off, when a text last left, the last failure."""
    _platform_manifest_or_404(key)
    utility = tenancy_seam.subdomain()
    state = platform_sms.card_state(utility)
    activity = notifications_seam.text_activity() or {}
    return Response(
        {
            **state,
            "last_sent_at": activity.get("last_sent_at"),
            "last_error": activity.get("last_error"),
            "last_error_at": activity.get("last_error_at"),
        }
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def platform_test(request: Any, key: str) -> Response:
    """One real text to a number the admin types. Refused by name when the
    platform is not set up; audited either way (hard rule 7)."""
    manifest = _platform_manifest_or_404(key)
    body = request.data if isinstance(request.data, dict) else {}
    raw = str(body.get("to") or "").strip()
    from apps.identity.phones import normalise_phone

    number = normalise_phone(raw)
    if number is None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="integrations.platformSms.badNumber",
            field_errors=[{"field": "to", "message_key": "integrations.platformSms.badNumber"}],
        )
    utility = tenancy_seam.subdomain()
    actor = SimpleNamespace(
        id=getattr(request.user, "id", None) or getattr(request.user, "pk", None),
        role=getattr(request, "tenant_role", None),
    )
    if not platform_sms.configured(utility):
        core_audit.money_action(
            actor,
            AUDIT_TEST,
            "integration_platform",
            None,
            after={"provider_key": manifest.key, "ok": False, "to": _mask(number), "reason": "not_configured"},
        )
        return Response({"ok": False, "sentence_key": "integrations.platformSms.notSetUp", "provider_text": None})
    adapter_cls = REGISTRY.adapter_for(manifest.key)
    secrets = platform_sms.secrets()
    try:
        result = adapter_cls().test(platform_sms.view(utility), secrets, recipient=number)
    finally:
        del secrets
    core_audit.money_action(
        actor,
        AUDIT_TEST,
        "integration_platform",
        None,
        after={"provider_key": manifest.key, "ok": result.ok, "to": _mask(number)},
    )
    return Response({"ok": result.ok, "sentence": result.sentence, "provider_text": result.provider_text})


def _refused() -> JsonResponse:
    return JsonResponse({"error": serve.REFUSAL_SENTENCE}, status=REFUSED_STATUS)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def twilio_status(request: Any) -> HttpResponse:
    """`POST /api/{utility}/integrations/platform/sms_twilio/status` — signed."""
    try:
        answer = platform_door.status(
            headers=request.META,
            full_path=request.get_full_path(),
            raw_body=request.body,
            received_at=timezone.now(),
        )
    except platform_door.Refused:
        return _refused()
    return JsonResponse({"outcome": answer.outcome}, status=200)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def twilio_reply(request: Any) -> HttpResponse:
    """`POST /api/hooks/twilio/reply` — signed; STOP only."""
    try:
        platform_door.reply(
            headers=request.META,
            full_path=request.get_full_path(),
            raw_body=request.body,
            received_at=timezone.now(),
        )
    except platform_door.Refused:
        return _refused()
    return HttpResponse(EMPTY_TWIML, content_type="text/xml", status=200)


#: Inside `/api/{utility}/` (config/urls.py's tenant include).
urlpatterns = [
    path("integrations/platform/sms_twilio/status", twilio_status),
    path("integrations/<str:key>/platform", platform_card),
    path("integrations/<str:key>/platform-test", platform_test),
]

#: Under `/api/` with NO utility — `hooks` is a no-tenant segment.
hook_urlpatterns = [
    path("hooks/twilio/reply", twilio_reply),
]
