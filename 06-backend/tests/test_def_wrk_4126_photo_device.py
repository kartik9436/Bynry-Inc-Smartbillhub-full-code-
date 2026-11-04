# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-4126 — a work-order photograph's `device` was sent by no
#           client and was therefore always empty.
# Change:   CR-168-BRC10 (lane FIN-S, final round)
# Rules:    BR-WRK-047 (a photograph and its row) · BR-WRK-059 (the capture
#           token carries the handset's label, minted while the captor was
#           signed in)
# Tests:    this file — through the VIEW, because the gap was a route that
#           never put a value in the column (hard-won law 2)
# ───────────────────────────────────────────────────────
"""The phone already says which handset it is: `MobileApp.tsx` mints the
capture token with `device_label = navigator.userAgent.slice(0, 60)`, and the
token carried it as `d` — read by nothing. The photograph route now fills
`device` from, in order: what the request names, the capture token's label,
and the request's own User-Agent cut to the same 60 characters the phone uses.
"""

from __future__ import annotations

import pytest

from apps.work import mobile
from apps.work import models as work_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise
from tests.test_us_wrk_047_049_evidence import TINY_PNG

pytestmark = pytest.mark.django_db

PHONE = "Mozilla/5.0 (Linux; Android 14; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129"


def _post(tenant, tech, oid, *, key, ua="", token=None, device=None):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.identity import models as identity_models
    from apps.work import api

    data = {"idempotency_key": key, "file": SimpleUploadedFile("p.png", TINY_PNG, "image/png")}
    if token:
        data["capture_token"] = token
    if device:
        data["device"] = device
    request = APIRequestFactory().post(
        f"/api/brazosbend/work-orders/{oid}/attachments",
        data,
        format="multipart",
        HTTP_USER_AGENT=ua,
    )
    force_authenticate(request, user=identity_models.User.objects.get(pk=tech.id))
    request.tenant_role = "field_technician"
    request.tenant_id = tenant.id
    response = api.work_order_attachments(request, order_id=oid)
    assert response.status_code in (200, 201), response.data
    return work_models.WorkOrderAttachment.objects.get(
        work_order_id=oid, idempotency_key=key
    ).device


def _job(dana, brazos):
    oid = _raise(dana, brazos, _published_template(dana, brazos))["id"]
    tech = field_actor(oid, dana)
    mobile.accept_job(tech, oid)
    return oid, tech


def test_the_request_user_agent_names_the_handset(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        device = _post(brazos, tech, oid, key="ua-1", ua=PHONE)
    assert device == PHONE[:60]


def test_the_capture_tokens_label_wins_over_the_courier(brazos, dana):
    """A shared tablet: the item is the captor's, and so is the handset label
    minted with their token — not whatever sends it later."""
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        token = mobile.issue_capture_token(tech, {"device_label": "Pixel 7a"})["capture_token"]
        device = _post(brazos, tech, oid, key="tok-1", ua="Courier browser", token=token)
    assert device == "Pixel 7a"


def test_a_named_device_is_kept(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        device = _post(brazos, tech, oid, key="named-1", ua=PHONE, device="Van 3 tablet")
    assert device == "Van 3 tablet"
