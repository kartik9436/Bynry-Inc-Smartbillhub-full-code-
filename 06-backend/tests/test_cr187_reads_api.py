# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the route-reading routes through the REAL door: a
#           field technician's session, `FieldAppRole`, the tenant from the path.
# Story:    US-FLD-040 · US-FLD-054 · US-FLD-060
# Rules:    07-endpoints.md §0 (tenant from the credential, never the payload) ·
#           BR-FLD-00082 · CLAUDE.md hard rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The five routes, mounted, behind a technician's sign-in."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.identity.models import User

from tests.isolation_helpers import writing_as_tenant
from tests.test_cr038_w5_reads_surface import metering_actor
from tests.test_cr187_reads_helpers import a_reading, build_route, tenant_ctx
from tests.test_us_idn_helpers import JSON, SC, api_path, idn  # noqa: F401 — fixture by name

pytestmark = pytest.mark.django_db

TECH = ("ray@silvercreek.example", "Prairie2026grass")


@pytest.fixture()
def wired(idn):
    idn.seed_silvercreek()
    tech, _membership = idn.make_user(
        idn.silvercreek, TECH[0], "Ray Reader", password=TECH[1], role="field_technician"
    )
    with writing_as_tenant(idn.silvercreek):
        User.objects.filter(pk=tech.pk).update(surface_scope="mobile")
    with tenant_ctx(idn.silvercreek):
        admin = metering_actor(idn.silvercreek)
        route = build_route(idn.silvercreek, admin, tech, history=False)
    client = Client()
    signed = client.post(
        api_path("/auth/session", SC),
        data={"email": TECH[0], "password": TECH[1], "surface": "mobile"},
        content_type=JSON,
    )
    assert signed.status_code == 201, signed.content
    return client, route, idn.silvercreek


def test_the_technician_downloads_sends_and_turns_in_through_the_api(wired):
    client, route, tenant = wired
    mine = client.get(api_path("/work/mobile/routes"))
    assert mine.status_code == 200, mine.content
    assert [r["code"] for r in mine.json()["results"]] == ["WLK-07"]

    page = client.get(api_path(f"/work/mobile/routes/{route.route_id}?per=50"))
    assert page.status_code == 200, page.content
    assert page.json()["count"] == 3

    reasons = client.get(api_path("/work/mobile/cant-read-reasons"))
    assert reasons.status_code == 200 and reasons.json()["count"] == 8

    with tenant_ctx(tenant):  # the helper reads the tenant's own clock
        item = a_reading("api-0001", "MTR-0471", "120", route_id=route.route_id)
    sent = client.post(api_path("/work/mobile/reads/sync"), data={"items": [item]},
                       content_type=JSON)
    assert sent.status_code == 200, sent.content
    assert sent.json()["items"][0]["result"] == "accepted"

    turned = client.post(
        api_path(f"/work/mobile/routes/{route.route_id}/turn-in"),
        data={"key": "turn-api-1", "keys": ["api-0001"]},
        content_type=JSON,
    )
    assert turned.status_code == 200, turned.content
    assert turned.json()["landed"]["readings"] == 1


def test_a_technician_cannot_add_a_reason_and_an_unknown_route_is_a_404(wired):
    client, _route, _tenant = wired
    refused = client.post(
        api_path("/work/mobile/cant-read-reasons"),
        data={"code": "flooded", "name": "Flooded"},
        content_type=JSON,
    )
    assert refused.status_code == 403
    missing = client.get(api_path("/work/mobile/routes/00000000-0000-0000-0000-000000000000"))
    assert missing.status_code == 404


def test_unauthenticated_calls_are_refused():
    assert Client().get(api_path("/work/mobile/routes")).status_code in (401, 403, 404)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-040@fa5746815 (CR-187-BRC10 route-reading server lane)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no frontend in this lane) F✔ G✔ H=deferred(no 🔒 path in a test)
# gates: see the lane report
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
