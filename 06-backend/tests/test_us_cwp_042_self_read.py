# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-042 (EP-CWP-08) — *Send your own reading: one validation,
#           two sources*. Screen: CWP-035 (blueprint `P21`)
# Defect:   DEF-CWP-10175 — gap E of the PO's 2026-10-17 meter-reading ruling
# Rules:    BR-CWP-067 (the same validation as a staff read) · BR-CWP-074
#           (accepted first, then validated; a VALIDATION flag only when the
#           check objects; a PROVENANCE flag `customer` on EVERY customer
#           reading) · BR-CWP-069 (never charged twice) · BR-CWP-010 (only the
#           session's own accounts, in the query) · CR-068 R8 / US-CWP-042 TC-7
#           (switched off → unreachable AND refused) · CLAUDE.md hard rules 1, 3,
#           4, 7
# Tests:    this file
# Impacts:  apps/metering/customer_reads.py · apps/metering/services.py
#           `_post_row` · apps/portal/services.py `submit_meter_reading` ·
#           apps/portal/api.py `send_reading` · apps/portal/selectors.py
# ───────────────────────────────────────────────────────
"""`US-CWP-042` through the REAL door — a signed-in portal session, the edge,
Meter Reads' own stage → validate → commit.

⚠ **EVERY CASE GOES THROUGH A REAL SIGN-IN AND NOT A STAND-IN PRINCIPAL.**
`BR-CWP-010`'s intersection lives in the QUERY behind a real session, and
`apps/portal/session.py` is HUMAN-OWNED — a test that built its own principal
would be proving something about a class it wrote.

⚠ **THE DATES ARE RELATIVE TO THE REAL `date.today()`**, because the edge asks
the clock exactly once (`BR-TEN-043`) and passes it down. History ends 31 Aug
2026 and every submitted date is on or after it.

RED FIRST (hard-won law 7, in pytest — the harness that runs it): on the base
commit `b30401c66` every case here fails — the route is not mounted, so the
POST answers 404 and the GET answers 404.

Run on PostgreSQL (`--ds=config.settings.pgtest`) as well as SQLite: the door
catches nothing and continues, but it posts inside one transaction and the
refusals must leave nothing behind (hard-won law 14).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client

from apps.metering import models as metering_models
from core.tenancy import tenant_context

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import (
    WATER_SERIAL,
    a_read,
    a_water_meter,
    elm_unit_with_services,
    twelve_months_of_water,
)
from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria, switch_on

pytestmark = pytest.mark.django_db

LAST_DIAL = Decimal("153040")  # `US-CWP-042` §4 — 31 Aug
METER_NO = "M-88402"


def _maria_with_history(tenant, actor, *, self_read=True):
    account = elm_unit_with_services(tenant, actor, codes=("water",))
    meter = a_water_meter(tenant, actor, account.unit_id)
    twelve_months_of_water(tenant, actor, account, meter["id"])
    switch_on(tenant, actor, self_read_enabled=self_read)
    return account, meter


def _signed_in(tenant, actor):
    with tenant_context(tenant.id):
        from apps.portal import models as portal_models

        already = portal_models.PortalCredential.objects.filter(
            tenant_id=tenant.id, email=MARIA_EMAIL
        ).exists()
    if not already:
        enrol_maria(tenant, actor)
    client = Client()
    signed = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert signed.status_code == 200, signed.content
    return client


def _url(tenant, account_id):
    return f"/api/{tenant.subdomain}/portal/accounts/{account_id}/readings/send"


def _send(client, tenant, account_id, **body):
    return client.post(_url(tenant, account_id), data=body, content_type="application/json")


def _customer_reads(tenant, asset_id):
    with tenant_context(tenant.id):
        return list(
            metering_models.MeterRead.objects.filter(
                tenant_id=tenant.id, asset_id=asset_id, source="customer"
            )
        )


# ══════════════════════════════════════════════════════════════════════════
# THE FRAME — what CWP-035 draws
# ══════════════════════════════════════════════════════════════════════════
def test_the_form_names_the_meter_by_serial_with_its_last_reading(pine_hill, sarah):
    account, _meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    answer = client.get(_url(pine_hill, account.pk))
    assert answer.status_code == 200, answer.content
    body = answer.json()
    assert [m["serial"] for m in body["meters"]] == [WATER_SERIAL]
    register = body["meters"][0]["registers"][0]
    assert Decimal(register["last_reading"]) == LAST_DIAL
    assert register["last_read_on"] == "2026-08-31"
    assert register["unit"] == "gal"  # hard rule 3 — the number never travels bare
    #: B14 rule 31 — no database id anywhere in the frame.
    assert str(_meter["id"]) not in answer.content.decode()


def test_the_readings_frame_says_whether_send_a_reading_appears(pine_hill, sarah):
    account, _meter = _maria_with_history(pine_hill, sarah, self_read=False)
    client = _signed_in(pine_hill, sarah)
    frame = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/readings")
    assert frame.json()["self_read_enabled"] is False
    switch_on(pine_hill, sarah, self_read_enabled=True)
    frame = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/readings")
    assert frame.json()["self_read_enabled"] is True


# ══════════════════════════════════════════════════════════════════════════
# TC-1 / TC-10 — ACCEPTED, WITH THE PROVENANCE FLAG ON A CLEAN READING
# ══════════════════════════════════════════════════════════════════════════
def test_a_reading_is_accepted_and_carries_source_customer(pine_hill, sarah, audit_rows):
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    day = date(2026, 9, 2)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on=day.isoformat()
    )
    assert answer.status_code == 201, answer.content
    body = answer.json()
    assert body["received"] is True
    assert body["reading"] == "153300"
    assert Decimal(body["used"]) == Decimal("260")  # 153,300 − 153,040
    assert body["unit"] == "gal"

    rows = _customer_reads(pine_hill, meter["id"])
    assert len(rows) == 1
    read = rows[0]
    #: BR-CWP-074 (2) — the PROVENANCE flag: `customer`, never `manual`.
    assert read.source == "customer"
    assert read.current_value == Decimal("153300")
    assert read.read_at.date() == day
    assert read.lifecycle == "committed"
    #: Who read it — BR-MET-142's method, so CWP-034 says *You sent it in*.
    assert read.read_method == "self_read"
    #: Hard rule 7 spirit — the act is on the trail, naming the portal actor.
    trail = [row for row in audit_rows if row.get("action") == "portal.meter_reading.submitted"]
    assert len(trail) == 1
    assert str(trail[0]["entity_id"]) == str(read.id)
    assert trail[0]["actor_user_id"] is None  # a portal customer is not a User
    assert trail[0]["after"]["source"] == "customer"
    assert trail[0]["after"]["actor"]["channel"] == "customer_portal"


def test_the_portal_readings_list_says_you_sent_it_in(pine_hill, sarah):
    account, _meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    _send(client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on="2026-09-02")
    page = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/readings").json()
    row = next(r for r in page["readings"] if r["taken_on"] == "2026-09-02")
    assert row["how"] == "self_read"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 / BR-CWP-070 / 074 (1) — A HIGH READING IS ACCEPTED, AND FLAGGED
# ══════════════════════════════════════════════════════════════════════════
def test_a_very_high_reading_is_accepted_with_a_validation_flag(pine_hill, sarah):
    """⚠ **THE METER READS IN `kgal` HERE, AND THAT IS THE TENANT'S OWN
    CONFIGURATION, NOT A TEST TRICK.** The high rule needs BOTH halves (OQ-002):
    a ratio over `high_pct` AND a delta over the absolute floor, and the seeded
    floor is `high_abs_kgal`. A `gal` register with no conversion factor
    reports `absolute_floor_unavailable_for_unit` — measured on the first run
    of this case — which is the staff behaviour too (`BR-CWP-067`: one
    validation, two sources). So this case reads a register the floor is
    stated in, exactly as a utility billing in thousands of gallons would."""
    account = elm_unit_with_services(pine_hill, sarah, codes=("water",))
    meter = a_water_meter(pine_hill, sarah, account.unit_id)
    with tenant_context(pine_hill.id):
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(pk=meter["id"]).update(unit="kgal")
    dial = Decimal("104920")
    for index, used in enumerate(
        (3050, 3410, 3760, 4090, 4820, 4300, 4170, 3900, 4300, 4090, 3410, 4820)
    ):
        prior = dial
        dial += used
        a_read(
            pine_hill,
            account,
            meter["id"],
            day=date(2025, 9 + index, 28) if index < 4 else date(2026, index - 3, 28),
            current=dial,
            consumption=used,
            prior=prior,
            unit="kgal",
        )
    switch_on(pine_hill, sarah, self_read_enabled=True)
    client = _signed_in(pine_hill, sarah)
    #: 80,000 against a ~4,010 average: about twenty times usual, and far over
    #: the 1 kgal floor.
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value=str(dial + 80000), read_on="2026-09-30"
    )
    assert answer.status_code == 201, answer.content
    body = answer.json()
    assert body["received"] is True
    assert body["flagged"] is True
    assert "high" in body["checks"]
    assert body["times_usual"] is not None and body["times_usual"] >= 15

    rows = _customer_reads(pine_hill, meter["id"])
    assert len(rows) == 1
    read = rows[0]
    #: Both flags at once — they mean different things (BR-CWP-074).
    assert read.source == "customer"
    #: The read's ONE primary status is whichever warning ranks first; here the
    #: register (kgal) and the plan's price unit (gal) also differ, which the
    #: staff path flags the same way. What matters is that it is NOT `ok`.
    assert read.status != "ok"
    assert read.disposition == "accept_with_flag"
    assert any(
        o.get("rule") == "high" and o.get("severity") == "warning" for o in read.rule_outcomes
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-7 — SWITCHED OFF: UNREACHABLE AND REFUSED
# ══════════════════════════════════════════════════════════════════════════
def test_switched_off_the_form_and_the_write_both_refuse(pine_hill, sarah):
    account, meter = _maria_with_history(pine_hill, sarah, self_read=False)
    client = _signed_in(pine_hill, sarah)
    assert client.get(_url(pine_hill, account.pk)).status_code in (409, 422)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on="2026-09-02"
    )
    assert answer.status_code in (409, 422), answer.content
    assert "portal.selfRead.notOffered" in answer.content.decode()
    assert _customer_reads(pine_hill, meter["id"]) == []


# ══════════════════════════════════════════════════════════════════════════
# BR-CWP-010 — ANOTHER CUSTOMER'S METER, ANOTHER CUSTOMER'S ACCOUNT
# ══════════════════════════════════════════════════════════════════════════
def test_a_meter_not_on_this_account_is_refused_as_not_found(pine_hill, sarah):
    account, meter = _maria_with_history(pine_hill, sarah)
    #: A meter that exists in this utility, on ANOTHER unit.
    with tenant_context(pine_hill.id):
        other_unit = (
            metering_models.Unit.objects.filter(tenant_id=pine_hill.id)
            .exclude(pk=account.unit_id)
            .first()
        )
    assert other_unit is not None, "the fixture street holds a second unit"
    a_water_meter(pine_hill, sarah, other_unit.id, serial="77-11111", asset_no="M-77111")
    client = _signed_in(pine_hill, sarah)
    answer = _send(client, pine_hill, account.pk, meter="M-77111", value="10", read_on="2026-09-02")
    assert answer.status_code == 404
    #: …and an account outside the session's set is the SAME 404 as one that
    #: does not exist (`BR-CWP-010`, `_account_in_set`).
    from core.dbfields import uuid7

    answer = _send(client, pine_hill, uuid7(), meter="M-77111", value="10", read_on="2026-09-02")
    assert answer.status_code == 404
    with tenant_context(pine_hill.id):
        assert not metering_models.MeterRead.objects.filter(
            tenant_id=pine_hill.id, source="customer"
        ).exists()


def test_another_tenants_session_cannot_reach_this_account(pine_hill, oak_ridge, sarah):
    """Hard rule 1 — the tenant is resolved from the PATH, and an account of
    Pine Hill asked for under Oak Ridge's address is not found."""
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    answer = client.post(
        f"/api/{oak_ridge.subdomain}/portal/accounts/{account.pk}/readings/send",
        data={"meter": METER_NO, "value": "153300", "read_on": "2026-09-02"},
        content_type="application/json",
    )
    assert answer.status_code in (401, 403, 404)
    assert _customer_reads(pine_hill, meter["id"]) == []


# ══════════════════════════════════════════════════════════════════════════
# THE DATE AND THE FIGURE — refused on the input they are about
# ══════════════════════════════════════════════════════════════════════════
def test_a_future_date_is_refused(pine_hill, sarah):
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    tomorrow = date.today() + timedelta(days=1)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on=tomorrow.isoformat()
    )
    assert answer.status_code == 422, answer.content
    errors_ = answer.json()["field_errors"]
    assert errors_[0]["field"] == "read_on"
    assert errors_[0]["message_key"] == "portal.selfRead.refuse.future"
    assert _customer_reads(pine_hill, meter["id"]) == []


def test_a_date_before_the_last_reading_is_refused(pine_hill, sarah):
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on="2026-08-15"
    )
    assert answer.status_code == 422, answer.content
    assert answer.json()["field_errors"][0]["message_key"] == ("portal.selfRead.refuse.beforeLast")


def test_an_unreadable_figure_is_refused(pine_hill, sarah):
    account, _meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="15x3", read_on="2026-09-02"
    )
    assert answer.status_code == 422
    field = answer.json()["field_errors"][0]
    assert (field["field"], field["message_key"]) == ("value", "portal.selfRead.refuse.unreadable")


def test_a_reading_lower_than_the_last_is_refused_with_a_sentence(pine_hill, sarah):
    """TC-4 — not silently accepted as a rollover, and nothing persists."""
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    answer = _send(
        client, pine_hill, account.pk, meter=METER_NO, value="152000", read_on="2026-09-02"
    )
    assert answer.status_code == 422, answer.content
    assert answer.json()["field_errors"][0]["message_key"] == ("portal.selfRead.refuse.lower")
    assert _customer_reads(pine_hill, meter["id"]) == []
    with tenant_context(pine_hill.id):
        assert not metering_models.ReadImportBatch.objects.filter(
            tenant_id=pine_hill.id, source_kind="customer"
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# BR-CWP-069 — A LATER REAL READING DOES NOT CHARGE THE SAME WATER TWICE
# ══════════════════════════════════════════════════════════════════════════
def test_a_later_real_read_bills_only_the_dial_movement(pine_hill, sarah):
    account, meter = _maria_with_history(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    _send(client, pine_hill, account.pk, meter=METER_NO, value="153300", read_on="2026-09-02")
    #: The reader comes on 30 September and reads 153,400 through the staff door.
    from apps.metering import services as metering_services

    with tenant_context(pine_hill.id):
        metering_services.commit_event_reads(
            sarah,
            {
                "event": "move_in",
                "reads": [{"meter_no": METER_NO, "read_at": "2026-09-30", "value": "153400"}],
            },
        )
        after = list(
            metering_models.MeterRead.objects.filter(
                tenant_id=pine_hill.id,
                asset_id=meter["id"],
                read_at__date__gt=date(2026, 8, 31),
                superseded_by_id__isnull=True,
            ).order_by("read_at")
        )
    assert [r.source for r in after] == ["customer", "manual"]
    #: 260 + 100 = 360 = 153,400 − 153,040: the customer is charged for the
    #: water once, whoever read the dial.
    assert sum(r.consumption for r in after) == Decimal("153400") - LAST_DIAL
