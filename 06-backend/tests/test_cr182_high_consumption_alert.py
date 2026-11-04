# ── Trace ──────────────────────────────────────────────
# Change:   CR-182-BRC10 — PO rulings A1–A5, 2026-10-14 (decision log *"HIGH
#           CONSUMPTION: THE CUSTOMER IS ALERTED AS SOON AS A READING IS
#           FLAGGED — PORTAL MESSAGE, EMAIL, BILL NOTE, READING TAG (A1–A5)"*)
# Rules:    BR-MET-020 / BR-MET-120 (the one definition of high) · BR-NOT-018 ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (units) · rule 6
#           (idempotency) · rule 7 (the queue write audits)
# Tests:    this file — runs on SQLite AND on PostgreSQL
#           (`--ds=config.settings.pgtest --create-db`)
# Impacts:  apps/metering/high_consumption.py · apps/metering/services.py ·
#           apps/notifications/rule_catalog.py · apps/portal/selectors.py ·
#           apps/portal/seams/billing_seam.py · apps/metering/portal_reads.py
# ───────────────────────────────────────────────────────
"""A reading flagged HIGH tells the customer: one email, the portal, the bill.

Maria's water meter at `1408 Elm St · A` reads ~4,000 gal a month for a year
(`EP-CWP-08` §4's twelve months, 48,120 gal). A September reading of 40,000 gal
is ten times that — BR-MET-020/120 flags it high, and from that moment:

  * ONE email is queued (`usage_alert`, keyed on the reading) — A4/A5;
  * the portal Home carries `high_consumption` — A1;
  * Usage → Readings tags the row — A3;
  * once a bill priced it, the bill says *High usage* and Home says *your last
    bill is higher than usual* — A1/A2.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.metering import high_consumption, models as metering_models, services as metering_services
from apps.notifications import models as notification_models
from apps.notifications import rule_service
from apps.portal import selectors as portal_selectors
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import (
    a_water_meter,
    elm_unit_with_services,
    twelve_months_of_water,
)
from tests.test_us_met_reads_helpers import accept_warnings, csv_body, seed_service_config, stage

pytestmark = pytest.mark.django_db

#: The dial after `twelve_months_of_water` (104,920 + 48,120).
LAST_DIAL = Decimal("153040")
#: Ten times a normal month — the case the PO was shown (Susan Cook's 10×).
HIGH_GALLONS = Decimal("40000")
NORMAL_GALLONS = Decimal("4100")
SEPTEMBER = date(2026, 9, 30)


class _Principal:
    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def _maria(tenant, actor):
    account = elm_unit_with_services(tenant, actor, codes=("water",))
    meter = a_water_meter(tenant, actor, account.unit_id)
    twelve_months_of_water(tenant, actor, account, meter["id"])
    with tenant_context(tenant.id):
        # The floor in the register's own unit, so the high rule's AND-half is
        # evaluated without a conversion factor (OQ-004) — the floor is not
        # what this file is about.
        seed_service_config("water", high_pct=Decimal("200"), high_abs_value=Decimal("1000"),
                            high_abs_unit="gal")
    return account, meter


def _post(tenant, actor, gallons, *, day="2026-09-30"):
    """A reading posted through the REAL batch door — stage, validate, accept
    the warnings a clerk would accept, commit. `_post_row` is the hook."""
    dial = LAST_DIAL + gallons
    with tenant_context(tenant.id):
        batch = stage(
            actor,
            csv_body(f"M-88402,{day},{dial},total,water"),
            period_month="2026-09-01",
            source_detail="walk_by",
        )
        metering_services.validate_read_batch(actor, batch["id"])
        accept_warnings(actor, batch["id"])
        metering_services.commit_read_batch(actor, batch["id"], {"certified": True})
        return (
            metering_models.MeterRead.objects.filter(
                tenant_id=tenant.id, asset__asset_no="M-88402", superseded_by_id__isnull=True
            )
            .order_by("-read_at")
            .first()
        )


def _issued_bill_pricing(tenant, account, read, number, total):
    """An ISSUED bill whose frozen payload names the reading it priced — the
    `bill_payload.services[].read_id` stage 6 stamps (`DEF-098`).

    ⚠ **THE PAYLOAD IS WRITTEN AT CREATION, NOT AFTER.** On PostgreSQL the
    `billing_invoice_immutable` trigger refuses any change to an issued bill but
    its status (hard rule 4) — a fixture that saved the payload afterwards
    passed on SQLite and was refused on PostgreSQL, which is how this was found.
    """
    from datetime import UTC, datetime

    from apps.billing import models as billing_models

    amount = Decimal(total)
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=number,
        status=billing_models.INVOICE_ISSUED,
        service_date=SEPTEMBER,
        period_start=SEPTEMBER.replace(day=1),
        period_end=SEPTEMBER,
        due_date=SEPTEMBER,
        subtotal=amount,
        tax_total=Decimal("0"),
        total=amount,
        issued_at=datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
        bill_payload={"services": [{"code": "water", "read_id": str(read.id)}]},
    )


def _alerts(tenant):
    with tenant_context(tenant.id):
        return list(
            notification_models.OutboundMessage.objects.filter(
                tenant_id=tenant.id, source_type=high_consumption.SOURCE_USAGE_ALERT
            )
        )


def _home(tenant, account):
    with tenant_context(tenant.id):
        return portal_selectors.home(_Principal(tenant.id, [account.pk]), today=date(2026, 10, 1))


# ══════════════════════════════════════════════════════════════════════════
# A5 + A4 — flagged → ONE email, queued at once
# ══════════════════════════════════════════════════════════════════════════
def test_a_reading_flagged_high_queues_one_email(pine_hill, sarah):
    """WOULD CATCH: the trigger not wired into the batch door (`_post_row`),
    the email riding the wrong event or class, or "high" meaning anything but
    the staff rule's own stored flag."""
    account, _meter = _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, HIGH_GALLONS)
    assert read.consumption == HIGH_GALLONS
    assert high_consumption.is_flagged_high(read.rule_outcomes), read.rule_outcomes

    rows = _alerts(pine_hill)
    assert len(rows) == 1
    row = rows[0]
    assert str(row.source_id) == str(read.id)
    assert row.channel == notification_models.CHANNEL_EMAIL
    assert row.template_code == "email_high_usage_alert"
    assert row.event_key == "high_usage_alert"
    assert str(row.account_id) == str(account.pk)
    assert row.status == notification_models.STATUS_QUEUED


def test_a_normal_reading_queues_nothing(pine_hill, sarah):
    """WOULD CATCH: alerting on every reading rather than on the flag."""
    _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, NORMAL_GALLONS)
    assert not high_consumption.is_flagged_high(read.rule_outcomes)
    assert _alerts(pine_hill) == []


def test_saving_the_same_reading_again_does_not_alert_twice(pine_hill, sarah):
    """WOULD CATCH: a second email for the same reading (hard rule 6). The
    queue's unique key on (usage_alert, reading, email) is what holds it."""
    _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, HIGH_GALLONS)
    with tenant_context(pine_hill.id):
        again = high_consumption.notify_if_flagged(read, actor=sarah)
    assert again["messages"] and all(not m["created"] for m in again["messages"])
    assert len(_alerts(pine_hill)) == 1


def test_a_correction_that_is_no_longer_high_resolves_the_alert(pine_hill, sarah):
    """WOULD CATCH: the portal going on showing an alert after a clerk corrected
    the reading to a normal figure — and a second email for the correction."""
    account, _meter = _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, HIGH_GALLONS)
    assert [a["kind"] for a in _home(pine_hill, account)["attention"]] == ["high_consumption"]

    with tenant_context(pine_hill.id):
        metering_services.supersede_read(
            sarah, read.id, {"value": str(LAST_DIAL + NORMAL_GALLONS), "reason": "Misread dial"}
        )
    assert "high_consumption" not in [a["kind"] for a in _home(pine_hill, account)["attention"]]
    assert len(_alerts(pine_hill)) == 1  # the first email stands; nothing new


def test_a_correction_that_is_still_high_is_not_emailed_again(pine_hill, sarah):
    """WOULD CATCH: telling the customer twice about one collection."""
    account, _meter = _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, HIGH_GALLONS)
    with tenant_context(pine_hill.id):
        metering_services.supersede_read(
            sarah, read.id, {"value": str(LAST_DIAL + HIGH_GALLONS + 10), "reason": "Retyped"}
        )
    assert len(_alerts(pine_hill)) == 1
    assert [a["kind"] for a in _home(pine_hill, account)["attention"]] == ["high_consumption"]


def test_the_utility_switching_the_rule_off_stops_the_email_not_the_portal(pine_hill, sarah):
    """WOULD CATCH: the email ignoring SET-12, or the switch also silencing
    the portal message (A1 is the reading's own flag, not a queued message)."""
    account, _meter = _maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        rule_service.update_rule(event_key="high_usage_alert", actor=sarah, enabled=False)
    _post(pine_hill, sarah, HIGH_GALLONS)
    assert _alerts(pine_hill) == []
    assert [a["kind"] for a in _home(pine_hill, account)["attention"]] == ["high_consumption"]


# ══════════════════════════════════════════════════════════════════════════
# A1 / A2 / A3 — what the portal shows
# ══════════════════════════════════════════════════════════════════════════
def test_home_names_the_service_and_the_date_and_no_id(pine_hill, sarah):
    """WOULD CATCH: a Home item that leaks a database id (B14 rule 31), or one
    that cannot say which meter."""
    account, _meter = _maria(pine_hill, sarah)
    _post(pine_hill, sarah, HIGH_GALLONS)
    item = next(a for a in _home(pine_hill, account)["attention"] if a["kind"] == "high_consumption")
    assert item == {
        "kind": "high_consumption",
        "service": "water",
        "service_name": item["service_name"],
        "taken_on": "2026-09-30",
    }
    assert item["service_name"]


def test_the_readings_row_carries_the_tag(pine_hill, sarah):
    account, _meter = _maria(pine_hill, sarah)
    _post(pine_hill, sarah, HIGH_GALLONS)
    with tenant_context(pine_hill.id):
        rows = portal_selectors.account_readings(
            _Principal(pine_hill.id, [account.pk]), account, today=date(2026, 10, 1)
        )
    readings = rows["readings"] if isinstance(rows, dict) else rows
    flagged = [r for r in readings if r["high_consumption"]]
    assert [r["taken_on"] for r in flagged] == ["2026-09-30"]
    assert all(r["high_consumption"] is False for r in readings if r["taken_on"] != "2026-09-30")


def test_once_billed_the_bill_says_high_usage_and_home_says_last_bill(pine_hill, sarah):
    """WOULD CATCH: the bill note or the Home bill notice reading anything but
    the bill's OWN frozen read ids, or the reading alert outliving the bill."""
    account, _meter = _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, HIGH_GALLONS)
    with tenant_context(pine_hill.id):
        bill = _issued_bill_pricing(pine_hill, account, read, "BL-2609-0151", "612.4000")
        # What billing's issue does for every read a bill priced (DEF-098).
        assert metering_services.mark_read_billed(read.id, bill.pk)
        detail = billing_seam.bill_detail_for(
            [account.pk], number="BL-2609-0151", today=date(2026, 10, 1)
        )
    assert detail["high_usage"] is True
    attention = _home(pine_hill, account)["attention"]
    assert {"kind": "high_bill", "number": "BL-2609-0151"} in attention
    # The reading alert has done its job: the bill notice replaces it.
    assert "high_consumption" not in [a["kind"] for a in attention]


def test_def_cwp_10153_a_high_reading_partway_through_the_period_still_marks_the_bill(
    pine_hill, sarah
):
    """DEF-CWP-10153 — WOULD CATCH: the bill note or the Home notice asking
    about the bill's CLOSING read only. A period with a reading partway through
    charges every reading in its chain (DEF-BIL-9016), and stage 6 stamps them
    all in `chain_read_ids`, the closing one first (DEF-BIL-9075). Combined walk
    2026-10-14: 8 kgal, then 80 kgal flagged high on 10/13, then 6 kgal on 10/31
    — the October bill charged all 94 kgal and said nothing."""
    from datetime import UTC, datetime

    from apps.billing import models as billing_models

    account, _meter = _maria(pine_hill, sarah)
    high = _post(pine_hill, sarah, HIGH_GALLONS, day="2026-09-15")
    closing = _post(pine_hill, sarah, HIGH_GALLONS + NORMAL_GALLONS, day="2026-09-30")
    assert high.status == "high" and closing.status != "high"
    with tenant_context(pine_hill.id):
        amount = Decimal("700.0000")
        bill = billing_models.Invoice.objects.create(
            tenant=pine_hill,
            account=account,
            invoice_no="BL-2609-0153",
            status=billing_models.INVOICE_ISSUED,
            service_date=SEPTEMBER,
            period_start=SEPTEMBER.replace(day=1),
            period_end=SEPTEMBER,
            due_date=SEPTEMBER,
            subtotal=amount,
            tax_total=Decimal("0"),
            total=amount,
            issued_at=datetime(2026, 9, 30, 9, 0, tzinfo=UTC),
            bill_payload={
                "services": [
                    {
                        "code": "water",
                        "read_id": str(closing.id),
                        "chain_read_ids": [str(closing.id), str(high.id)],
                    }
                ]
            },
        )
        for one in (closing, high):
            metering_services.mark_read_billed(one.id, bill.pk)
        detail = billing_seam.bill_detail_for(
            [account.pk], number="BL-2609-0153", today=date(2026, 10, 1)
        )
    assert detail["high_usage"] is True
    assert {"kind": "high_bill", "number": "BL-2609-0153"} in _home(pine_hill, account)["attention"]


def test_a_bill_with_a_normal_reading_says_nothing(pine_hill, sarah):
    account, _meter = _maria(pine_hill, sarah)
    read = _post(pine_hill, sarah, NORMAL_GALLONS)
    with tenant_context(pine_hill.id):
        bill = _issued_bill_pricing(pine_hill, account, read, "BL-2609-0152", "61.0000")
        detail = billing_seam.bill_detail_for(
            [account.pk], number="BL-2609-0152", today=date(2026, 10, 1)
        )
    assert detail["high_usage"] is False
    assert [a for a in _home(pine_hill, account)["attention"] if a["kind"].startswith("high")] == []


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 1 — another utility sees none of it
# ══════════════════════════════════════════════════════════════════════════
def test_another_utility_sees_no_alert(pine_hill, sarah, oak_ridge, elena):
    """WOULD CATCH: an alert read that is not tenant-scoped — Oak Ridge asking
    with Maria's account id must get nothing."""
    account, _meter = _maria(pine_hill, sarah)
    _post(pine_hill, sarah, HIGH_GALLONS)
    with tenant_context(oak_ridge.id):
        assert high_consumption.open_alerts_for_accounts([account.pk]) == []
        assert not notification_models.OutboundMessage.objects.filter(
            tenant_id=oak_ridge.id, source_type=high_consumption.SOURCE_USAGE_ALERT
        ).exists()
    assert len(_alerts(pine_hill)) == 1
