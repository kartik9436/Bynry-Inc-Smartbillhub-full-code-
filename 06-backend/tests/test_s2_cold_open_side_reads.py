# ── Trace ──────────────────────────────────────────────
# Journey:  08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md S2
# Defects:  DEF-TEN-8731 (GET /settings/services counted accounts once per
#           service: 13.6 s at 10,015 accounts, killed at 60 s at 40,000) ·
#           DEF-MET-8732 (GET /cycles loaded every account and contact name to
#           count them) · DEF-BIL-8727 (Sign off on a SENT run: every money
#           figure '—', all 40,008 bills unanswered)
# Doc:      04-docs/05-modules/07-billing/19-check-cost-measured.md §13
# ───────────────────────────────────────────────────────
"""The two side reads the bulk run page makes on open, and Sign off after Send.

The speed is measured on PostgreSQL at 40,000 accounts (§13 of the cost doc);
what is asserted here is that the faster reads give the SAME answers:

  * the S8 table's active-account column, counted once for every service, is
    the per-service count the disable guard reads, service by service;
  * the batched readers that stop binding ids above a bound answer exactly what
    they answer below it (the bound forced to 0);
  * a sent run's Sign off shows what its bills were stamped with — the same
    $688.42 it showed at Sign off — instead of '—'.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import issue, signoff
from apps.billing import models as billing_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.tenancy import selectors as tenancy_selectors

from tests.test_d8696_signoff_batched import DUE, _world
from tests.test_def1549_service_reads_are_not_screen_reads import (  # noqa: F401
    ESTATE_SERVICES,
    ottumwa,
    plant_estate,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# DEF-TEN-8731
def test_8731_the_table_counts_once_and_each_row_is_the_guards_own_count(ottumwa, monkeypatch):
    with tenant_ctx(ottumwa):
        plant_estate(ottumwa, units=3, tag="a")
        singular = {code: customers_services.active_account_count(code) for code in ESTATE_SERVICES}
        calls = {"plural": 0, "singular": 0}
        plural, single = customers_services.active_account_counts, customers_services.active_account_count

        def counted_plural():
            calls["plural"] += 1
            return plural()

        def counted_single(code):
            calls["singular"] += 1
            return single(code)

        monkeypatch.setattr(customers_services, "active_account_counts", counted_plural)
        monkeypatch.setattr(customers_services, "active_account_count", counted_single)
        rows = {row["service"]: row["active_accounts"] for row in tenancy_selectors.services_overview()}
    print(f"\nPROOF 8731 table {rows} · guard {singular} · calls {calls}")
    assert singular == {"water": 3, "sewer": 3, "trash": 3}
    for code in ESTATE_SERVICES:
        assert rows[code] == singular[code]
    # a service nobody holds is an honest 0, never None
    assert all(value == 0 for code, value in rows.items() if code not in ESTATE_SERVICES)
    assert calls == {"plural": 1, "singular": 0}


# DEF-TEN-8731 — the whole-estate branch answers what the bound branch answers
def test_8731_reading_every_point_unbound_gives_the_bound_answer(ottumwa, monkeypatch):
    with tenant_ctx(ottumwa):
        plant_estate(ottumwa, units=2, tag="b")
        ids = list(metering_models.ServicePoint.objects.values_list("id", flat=True))[:-1]
        bound = metering_selectors.service_codes_for_points(ids)
        monkeypatch.setattr(metering_selectors, "_BIND_IDS_UP_TO", 0)
        unbound = metering_selectors.service_codes_for_points(ids)
    assert len(bound) == len(ids) > 0
    assert unbound == bound


# DEF-MET-8732
def test_8732_the_cycle_count_reads_the_same_account_per_unit(ottumwa, monkeypatch):
    with tenant_ctx(ottumwa):
        plant_estate(ottumwa, units=3, tag="c")
        units = [str(u) for u in metering_models.Unit.objects.values_list("id", flat=True)]
        full = {u: row["id"] for u, row in customers_selectors.accounts_for_units(units).items()}
        bound = customers_selectors.account_ids_for_units(units)
        monkeypatch.setattr(customers_selectors, "_BIND_UNITS_UP_TO", 0)
        unbound = customers_selectors.account_ids_for_units(units[:-1])
    assert len(full) == 3
    assert bound == full
    assert unbound == {u: a for u, a in full.items() if u in units[:-1]}


# DEF-BIL-8727
def test_8727_a_sent_run_shows_what_its_bills_were_stamped_with(brazos, dana):
    with tenant_ctx(brazos):
        run, drafts = _world(brazos, dana)
        at_sign_off = signoff._payments_and_balances(run, signoff._bills(run))
        blocks = {}
        for no, bill in drafts.items():
            blocks[no] = issue._stamp_balance_forward(bill, currency="USD", due_date=DUE)
        # Send: every draft issued (the stamp is already on each).
        billing_models.Invoice.objects.filter(pk__in=[b.pk for b in drafts.values()]).update(
            status=billing_models.INVOICE_ISSUED,
            issued_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        )
        sent = signoff._payments_and_balances(run, signoff._bills(run))
    print(f"\nPROOF 8727 Sign off {at_sign_off['amount_due']} · after Send {sent['amount_due']}")
    assert sent["unanswered_accounts"] == []
    assert Decimal(sent["amount_due"]) == sum(
        Decimal(block["total_due"]) for block in blocks.values()
    ) == Decimal(at_sign_off["amount_due"]) == Decimal("688.42")
    for key in ("previous_balance", "payments_and_credits_applied", "plan_not_yet_due",
                "this_run_charges", "accounts_with_payments_applied"):
        assert Decimal(str(sent[key])) == Decimal(str(at_sign_off[key])), key
    assert sent["reconciles"] is True
    assert sent["how_paid"] == at_sign_off["how_paid"]
    def covers(money):
        return [
            {k: (Decimal(v) if k in ("bill_total", "credit", "left_after") else v)
             for k, v in row.items()}
            for row in money["credit_covers_bills"]["results"]
        ], money["credit_covers_bills"]["count"]

    # The same bill covered by the same credit (the stamp's text carries the
    # stored six places; the live figure on SQLite may not).
    assert covers(sent) == covers(at_sign_off)
    # Nobody stamped the payments/credits split: null, never a guess.
    assert sent["payments_applied"] is None and sent["credits_applied"] is None


# DEF-BIL-8727 — a stamp that says '—' is still reported, never a zero
def test_8727_a_sent_bill_whose_stamp_has_no_total_is_unanswered(brazos, dana):
    with tenant_ctx(brazos):
        run, drafts = _world(brazos, dana)
        for bill in drafts.values():
            issue._stamp_balance_forward(bill, currency="USD", due_date=DUE)
        one = drafts["A-08603"]
        one.refresh_from_db()
        payload = dict(one.bill_payload)
        payload["balance_forward"] = {**payload["balance_forward"], "total_due": None}
        billing_models.Invoice.objects.filter(pk=one.pk).update(bill_payload=payload)
        billing_models.Invoice.objects.filter(pk__in=[b.pk for b in drafts.values()]).update(
            status=billing_models.INVOICE_ISSUED,
            issued_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        )
        sent = signoff._payments_and_balances(run, signoff._bills(run))
    assert sent["unanswered_accounts"] == [str(one.account_id)]
    assert sent["amount_due"] is None


# DEF-BIL-8727 — a summary saved by the old build is rebuilt once
def test_8727_the_build_version_is_part_of_the_key():
    assert signoff.SUMMARY_BUILD.endswith("DEF-BIL-8727")
