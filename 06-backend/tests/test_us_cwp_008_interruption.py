# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-008 (EP-CWP-03) — the interruption record and its
#           affected-area rule. Screens: the request detail's new section
# Rules:    BR-CWP-027 · BR-CWP-012 · CLAUDE.md hard rule 1 (the app-layer
#           scoping half; the RLS half is tests/test_us_cwp_008_pg.py —
#           the path was WRONG in four citations until DEF-CWP-3743)
# Tests:    this file — TC-1 (a clerk moves it to crew on site), TC-2 (the
#           affected area resolves to that stretch and nobody else), TC-3 (a
#           street with no premises is an EMPTY SET and still valid), TC-4
#           (resolving a resolved interruption is refused), TC-5 (an
#           overlapping street name resolves within one tenant), TC-6 (an ETA
#           in the past does not close anything)
# Impacts:  apps/metering/interruptions.py · interruption_service.py ·
#           apps/customers/service_request_api.py
# ───────────────────────────────────────────────────────
"""US-CWP-008 — *"the new thinking in the whole blueprint"* is the AREA RULE.

⚠ **AMENDED 2026-09-04 BY `CR-072`: EVERY CASE HERE USED TO GET ITS
INTERRUPTION FROM A GUEST FORM, AND NOW GETS IT FROM A CLERK.** A passer-by's
report raised the operational record itself; it does not any more, because a
stranger cannot settle whether something is an outage. **Not one assertion about
the AREA RULE moved** — what moved is the two lines above it, and `_open` below
is where they live now, so the change is in one place and visible.
"""

import pytest
from django.utils import timezone

from apps.customers import models as customers_models
from apps.customers import service_request_api
from apps.metering import interruption_service
from apps.metering import interruptions as interruption_models
from apps.portal import guest_api, sample_data
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call

REPORT = {
    "kind": "leak_or_burst",
    "location_text": "1408 Elm St, Austin TX 78702",
    "notes": "Water coming up through the pavement outside number 1412.",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}
ELM_AREA = {"street": "Elm St", "from": 1400, "to": 1500}


def _street(tenant, actor):
    """`US-CWP-008` §4's four addresses, through metering's own service."""
    with tenant_context(tenant.id):
        sample_data.seed_street(actor)


def _report(tenant):
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT),
        headers={"X-Forwarded-For": "198.51.100.10"},
    )


def _open(tenant, actor):
    """A report, and then **a clerk judging it real** — `CR-072` / `BR-CWP-101`.

    ⚠ **THE SECOND HALF IS NEW AND IT IS THE RULING.** These cases used to call
    `_report` alone, because one press of *Send* wrote the interruption too. It
    writes one row now — the request — and the operational record is opened by
    somebody who has read the reports, through `POST .../interruption`.
    """
    _report(tenant)
    request = customers_models.ServiceRequest.objects.get(tenant_id=tenant.id)
    response = api_call(
        service_request_api.service_request_interruption,
        "post",
        f"/api/{tenant.subdomain}/service-requests/{request.id}/interruption",
        tenant=tenant,
        user=actor.user,
        role="system_admin",
        data={},
        request_id=str(request.id),
    )
    assert response.status_code == 201, response.data
    # The row in hand was read BEFORE the POST, so its pointer is stale in
    # memory — refreshed here rather than in every caller.
    request.refresh_from_db()
    return request


def _one(tenant):
    return interruption_models.Interruption.objects.get(tenant_id=tenant.id)


@pytest.mark.django_db
def test_us_cwp_008_tc1_a_clerk_moves_it_to_crew_on_site(pine_hill, sarah):
    """TC-1 — and nobody edits a customer's page to do it."""
    switch_on(pine_hill, sarah)
    request = _open(pine_hill, sarah)
    row = _one(pine_hill)
    assert row.status == "looking_into_it"
    # ⚠ The path is the REQUEST's id, as it always was — but the link that
    # resolves it reversed (`CR-072`): the request points at the interruption.
    assert request.interruption_id == row.id
    response = api_call(
        service_request_api.service_request_interruption,
        "patch",
        f"/api/{pine_hill.subdomain}/service-requests/{request.id}/interruption",
        tenant=pine_hill,
        user=sarah.user,
        role="system_admin",
        data={"status": "crew_on_site"},
        request_id=str(request.id),
    )
    assert response.status_code == 200
    # ⚠ The answer is the SECTION now, not the record alone — the screen needs
    # the report and the vocabulary whether or not a record exists yet.
    assert response.data["interruption"]["status"] == "crew_on_site"
    row.refresh_from_db()
    assert row.status == "crew_on_site"
    assert row.resolved_at is None


@pytest.mark.django_db
def test_us_cwp_008_tc2_the_area_resolves_to_that_stretch_and_nobody_else(pine_hill, sarah):
    """*"Elm St, 1400–1500"* → `1408 Elm St` and `1412 Elm St`. **`22 Palm Ct`
    is not in it**, and that exclusion is the wave's exit test."""
    switch_on(pine_hill, sarah)
    _street(pine_hill, sarah)
    _open(pine_hill, sarah)
    row = _one(pine_hill)
    with tenant_context(pine_hill.id):
        interruption_service.set_affected_area(sarah, row.id, area=ELM_AREA)
        affected = interruption_service.affected_set(row.id)
    addresses = sorted(one["address_line"] for one in affected["premises"])
    assert addresses == ["1408 Elm St", "1412 Elm St"]
    assert "22 Palm Ct" not in str(affected)
    assert affected["premises_count"] == 2
    # `1408 Elm St` carries units A, B and Common; `1412` carries none.
    assert affected["unit_count"] == 3


@pytest.mark.django_db
def test_us_cwp_008_tc3_a_street_with_no_premises_is_an_empty_set_and_still_valid(pine_hill, sarah):
    """⚠ AN INTERRUPTION CAN EXIST BEFORE WE KNOW WHO IT TOUCHES."""
    switch_on(pine_hill, sarah)
    _street(pine_hill, sarah)
    _open(pine_hill, sarah)
    row = _one(pine_hill)
    with tenant_context(pine_hill.id):
        interruption_service.set_affected_area(sarah, row.id, area={"street": "Cedar Row"})
        affected = interruption_service.affected_set(row.id)
    assert affected["premises"] == []
    assert affected["premises_count"] == 0
    row.refresh_from_db()
    assert row.affected_area == {"street": "Cedar Row", "from": None, "to": None}
    assert row.status == "looking_into_it", "an empty set does not invalidate the record"


@pytest.mark.django_db
def test_us_cwp_008_tc4_resolving_a_resolved_interruption_is_refused(pine_hill, sarah):
    """The second resolution is not recorded as a new event."""
    switch_on(pine_hill, sarah)
    _open(pine_hill, sarah)
    row = _one(pine_hill)
    with tenant_context(pine_hill.id):
        interruption_service.set_status(sarah, row.id, status="resolved")
        first_resolved_at = _one(pine_hill).resolved_at
        with pytest.raises(errors.BizError) as caught:
            interruption_service.set_status(sarah, row.id, status="crew_on_site")
    assert caught.value.message_key == "metering.interruption.statusNotAllowed"
    row.refresh_from_db()
    assert row.status == "resolved"
    assert row.resolved_at == first_resolved_at


@pytest.mark.django_db
def test_us_cwp_008_tc5_an_overlapping_street_name_resolves_within_one_tenant(
    pine_hill, sarah, oak_ridge, elena
):
    """Pine Hill's *Elm St* and Oak Ridge's *Elm St* are two streets."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _street(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        sample_data.seed_street(
            elena,
            (
                {
                    "address_line": "1408 Elm St",
                    "city": "Oak Ridge",
                    "state": "TX",
                    "postal_code": "78610",
                    "units": (),
                },
            ),
        )
    _open(pine_hill, sarah)
    row = _one(pine_hill)
    with tenant_context(pine_hill.id):
        interruption_service.set_affected_area(sarah, row.id, area=ELM_AREA)
        affected = interruption_service.affected_set(row.id)
    assert affected["premises_count"] == 2, "Oak Ridge's Elm St is not Pine Hill's"


@pytest.mark.django_db
def test_us_cwp_008_tc6_an_eta_in_the_past_does_not_close_anything(pine_hill, sarah):
    """⚠ THE CLOCK DOES NOT CLOSE A RECORD — A CREW DOES."""
    switch_on(pine_hill, sarah)
    _open(pine_hill, sarah)
    row = _one(pine_hill)
    yesterday = timezone.now() - timezone.timedelta(days=1)
    with tenant_context(pine_hill.id):
        interruption_service.set_status(sarah, row.id, status="crew_on_site")
        interruption_service.set_affected_area(
            sarah, row.id, area=ELM_AREA, expected_back_on=yesterday
        )
    row.refresh_from_db()
    assert row.expected_back_on == yesterday
    assert row.status == "crew_on_site"
    assert row.resolved_at is None


@pytest.mark.django_db
def test_us_cwp_008_the_house_number_rule_reads_a_free_text_address(pine_hill):
    """The arithmetic the SQL cannot do (law 14), asserted on its own."""
    assert interruption_models.house_number("1408 Elm St") == 1408
    assert interruption_models.house_number("1408A Elm St") == 1408
    assert interruption_models.house_number("Elm St") is None
    assert interruption_models.house_number(None) is None
    # A street with no numbers means the whole street; one with numbers cannot
    # include a premises we are unable to place.
    assert interruption_models.normalise_area({"street": "Elm St", "from": 1500, "to": 1400}) == {
        "street": "Elm St",
        "from": 1400,
        "to": 1500,
    }
    assert interruption_models.normalise_area({"from": 1, "to": 2}) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@d6d31c46 (EP-CWP-03 §3 cases, written before the code)
# generated: 2026-09-04 by the CR-068 wave B build lane · AMENDED 2026-09-04 by the CR-072 lane (the interruption is opened by a CLERK, not by a guest form — `_open` is the one place that changed; no area-rule assertion moved)
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_008_interruption.py
# exceptions: the RLS half of TC-5 is tests/test_us_cwp_008_pg.py — SQLite has no row-level security (CLAUDE.md law 14). ⚠ That path read `test_us_cwp_pg.py` — a file that has never existed — in four places until DEF-CWP-3743 (2026-09-04)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
