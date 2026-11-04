# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T4 (C3 + C9) — "Premises on a supplier invoice + per-building
#           recovery". T3's sub-metering fixture is what makes it testable.
# Story:    US-LED-018 (capture) · US-LED-020 (bought vs billed)  Screens: S73 · S74
# Rules:    BR-LED-029 (what a captured supplier invoice holds — AMENDED: the
#           optional premises) · BR-LED-030 (the volume is optional) ·
#           BR-LED-031 (all-or-nothing, AMENDED to per-service-per-PREMISES-
#           per-period) · BR-LED-032 (the formula, a VOLUME ratio) ·
#           BR-REP-008 (a report states what it could not attribute) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 3 (a quantity carries its
#           unit)
# Golden:   Cypress 5.00% · Magnolia 20.00% · Sabine ABSENT · the blended
#           9.80% that hides the leak and the −58.33% that never prints
# ───────────────────────────────────────────────────────
"""CR-060 C9 — the figure a sub-metering company opens the product for.

**THE TEST THIS FILE EXISTS FOR** is
`test_cr060_t4__the_leaking_building_is_the_first_row_and_the_blend_never_prints`.
Producing a percentage per building is arithmetic; the thing C9 actually buys
is that **20.00% at Magnolia Row is the first row instead of 9.80% across three
buildings** — CR-060's own words, *"an average that describes neither and points
at nothing anyone can go and fix"*.

The second is
`test_cr060_t4__one_building_missing_a_volume_does_not_poison_the_others`,
which is C9's stated proof and the whole reason BR-LED-031's scope had to move:
under the tenant-wide rule, ONE cost-only invoice at ONE address suppressed
water for every building at once.

WHAT RUNS WHERE. Everything here runs on SQLite and Postgres alike — it is a
column, a grouping and an ordering, with no aborted-transaction behaviour in
play (CLAUDE.md law 14 does not bite on a read). The MIGRATION's forward and
reverse proof against real PostgreSQL 16.13 is recorded in `ledger/0011`'s
trailer. The cross-tenant case here is the APP-layer half and carries no
`requires_postgres`, matching `test_us_led_020_reconciliation.py`'s own posture:
a vendor guard on a test that does not touch RLS is a skip pretending to be
coverage.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import cost_capture, cost_reconciliation, models as ledger_models

from tests.cost_of_service_fixtures import JULY_END, JULY_START, with_monthly_fiscal_year
from tests.sub_metering_fixtures import (
    BLENDED_PCT_THAT_HIDES_THE_LEAK,
    CYPRESS_PCT,
    MAGNOLIA_PCT,
    SABINE_SUPPRESSED_PCT,
    TOTAL_BOUGHT_COST,
    bayou_bend_july,
    make_buildings,
    submetering_payload,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── helpers ─────────────────────────────────────────────────────────────────
def _bayou(growth_plan, identity_seam, subdomain="bayoubend"):
    from tests.test_us_ten_helpers import provisioned_tenant

    tenant, _ = provisioned_tenant(submetering_payload(subdomain))
    from tests.test_us_met_helpers import seed_physical_series

    seed_physical_series(tenant)
    return tenant


def _rows_by_building(result):
    return {
        (row["premises_label"], row["service"]): row for row in result["rows"]
    }


# ══════════════════════════════════════════════════════════════════════════
# C3 — the column, and what it refuses
# ══════════════════════════════════════════════════════════════════════════
def test_cr060_t4_c3__a_capture_carries_its_building(growth_plan, identity_seam):
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    with tenant_ctx(tenant):
        with_monthly_fiscal_year(admin)
        buildings = make_buildings(admin)
        captured = cost_capture.capture_supplier_invoice(
            admin,
            invoice_date=date(2026, 7, 8),
            service="water",
            supplier_name="City of Bayou Bend — Bulk Water",
            amount=Decimal("1085.00"),
            currency="USD",
            volume=Decimal("350000"),
            volume_unit="gal",
            premises_id=buildings["cypress"]["id"],
            reference="CY-2607-0011",
        )
        assert captured["premises_id"] == str(buildings["cypress"]["id"])
        stored = ledger_models.SupplierInvoice.objects.get(pk=captured["id"])
        assert str(stored.premises_id) == str(buildings["cypress"]["id"])
        # B14 rule 31 — the register serves the NAME beside the id, so no screen
        # has to print a uuid to say which building this was.
        register = cost_capture.register()
        assert register["rows"][0]["premises_label"] == "1400 Cypress Court"


def test_cr060_t4_c3__no_building_is_lawful_and_is_not_an_error(growth_plan, identity_seam):
    """BR-LED-029 as amended — a tenant-wide cost has no building BY NATURE.

    After T5 that is most of the vocabulary: payroll, insurance, rent, the
    utility's own property taxes. A required building would make those
    uncapturable, which is the opposite of *"everything in one place"*.
    """
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    with tenant_ctx(tenant):
        with_monthly_fiscal_year(admin)
        captured = cost_capture.capture_supplier_invoice(
            admin,
            invoice_date=date(2026, 7, 8),
            service="admin_insurance",
            supplier_name="Gulf Coast Mutual",
            amount=Decimal("2400.00"),
            currency="USD",
            reference="GCM-2026-07",
        )
    assert captured["premises_id"] is None


def test_cr060_t4_c3__another_tenants_building_is_refused(growth_plan, identity_seam):
    """CLAUDE.md rule 1. A purchase filed against another tenant's building
    would be a cross-tenant read the moment the per-building report grouped it,
    and the refusal is the SERVICE's, resolved through metering's own scoped
    read rather than re-implemented here."""
    theirs = _bayou(growth_plan, identity_seam, "bayoubend")
    ours = _bayou(growth_plan, identity_seam, "cypressbend")
    their_admin = staff_actor(theirs, "system_admin", "renata@bayoubend.test")
    our_admin = staff_actor(ours, "system_admin", "renata@cypressbend.test")
    with tenant_ctx(theirs):
        with_monthly_fiscal_year(their_admin)
        their_buildings = make_buildings(their_admin)
    with tenant_ctx(ours):
        with_monthly_fiscal_year(our_admin)
        with pytest.raises(cost_capture.CostCaptureError) as raised:
            cost_capture.capture_supplier_invoice(
                our_admin,
                invoice_date=date(2026, 7, 8),
                service="water",
                supplier_name="City of Bayou Bend — Bulk Water",
                amount=Decimal("1085.00"),
                currency="USD",
                premises_id=their_buildings["cypress"]["id"],
            )
        assert "premises register" in str(raised.value)
        assert ledger_models.SupplierInvoice.objects.count() == 0


def test_cr060_t4_c3__the_building_is_editable_while_the_period_is_open(
    growth_plan, identity_seam
):
    """BR-LED-034. Re-keying a building moves a figure between two rows of a
    report and never a cent in the books, which is why it is an ordinary edit."""
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    with tenant_ctx(tenant):
        with_monthly_fiscal_year(admin)
        buildings = make_buildings(admin)
        captured = cost_capture.capture_supplier_invoice(
            admin,
            invoice_date=date(2026, 7, 8),
            service="water",
            supplier_name="City of Bayou Bend — Bulk Water",
            amount=Decimal("1085.00"),
            currency="USD",
            premises_id=buildings["cypress"]["id"],
        )
        moved = cost_capture.edit_supplier_invoice(
            admin, captured["id"], premises_id=buildings["magnolia"]["id"]
        )
        assert moved["premises_id"] == str(buildings["magnolia"]["id"])
        cleared = cost_capture.edit_supplier_invoice(admin, captured["id"], premises_id=None)
        assert cleared["premises_id"] is None


# ══════════════════════════════════════════════════════════════════════════
# C9 — the per-building recovery
# ══════════════════════════════════════════════════════════════════════════
def test_cr060_t4__the_leaking_building_is_the_first_row_and_the_blend_never_prints(
    growth_plan, identity_seam
):
    """C9 in one assertion: **20.00% at Magnolia Row, first.**

    The blended figure across the same three buildings is 9.80%
    (`(1,250,000 − 1,127,500) / 1,250,000`) — a number that describes no
    building. It must appear nowhere in this payload.
    """
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    clerk = staff_actor(tenant, "billing_clerk", "clerk@bayoubend.test")
    with tenant_ctx(tenant):
        bayou_bend_july(tenant, clerk, admin)
        result = cost_reconciliation.by_premises(
            period_start=JULY_START, period_end=JULY_END
        )

    assert result["group_by"] == "premises"
    first = result["rows"][0]
    assert first["premises_label"] == "88 Magnolia Row"
    assert first["unaccounted_for_pct"] == MAGNOLIA_PCT  # 20.00
    assert result["rows"][1]["premises_label"] == "1400 Cypress Court"
    assert result["rows"][1]["unaccounted_for_pct"] == CYPRESS_PCT  # 5.00

    printed = {row["unaccounted_for_pct"] for row in result["rows"]}
    assert BLENDED_PCT_THAT_HIDES_THE_LEAK not in printed
    assert SABINE_SUPPRESSED_PCT not in printed
    assert result["total_bought_cost"] == TOTAL_BOUGHT_COST  # 3,875.00
    assert result["currency"] == "USD"


def test_cr060_t4__one_building_missing_a_volume_does_not_poison_the_others(
    growth_plan, identity_seam
):
    """C9's stated proof, and the reason BR-LED-031's scope had to move.

    Sabine Lofts has two water purchases and one carries no volume, so its own
    row is ABSENT with the count. **Cypress and Magnolia still read**, which
    they would not under the tenant-wide rule: there, one cost-only invoice at
    one address suppressed water for the whole tenant.
    """
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    clerk = staff_actor(tenant, "billing_clerk", "clerk@bayoubend.test")
    with tenant_ctx(tenant):
        bayou_bend_july(tenant, clerk, admin)
        by_building = _rows_by_building(
            cost_reconciliation.by_premises(period_start=JULY_START, period_end=JULY_END)
        )
        tenant_wide = cost_reconciliation.reconciliation(
            period_start=JULY_START, period_end=JULY_END
        )

    sabine = by_building[("3 Sabine Lofts", "water")]
    assert sabine["unaccounted_for_pct"] is None
    assert cost_reconciliation.NO_VOLUME_FOR_SOME_PURCHASES in sabine["problems"]
    assert "1 of 2 water purchases" in sabine["reason"]

    assert by_building[("1400 Cypress Court", "water")]["unaccounted_for_pct"] == CYPRESS_PCT
    assert by_building[("88 Magnolia Row", "water")]["unaccounted_for_pct"] == MAGNOLIA_PCT

    # The contrast, asserted rather than described: the SAME month grouped the
    # OLD way produces no water figure at all for anybody.
    water = next(row for row in tenant_wide["rows"] if row["service"] == "water")
    assert water["unaccounted_for_pct"] is None
    assert cost_reconciliation.NO_VOLUME_FOR_SOME_PURCHASES in water["problems"]


def test_cr060_t4__every_row_names_its_building(growth_plan, identity_seam):
    """B14 rule 31 — no database id is the visible value of a field. Every row
    carries the building's NAME beside its id, so a screen never has to print
    a uuid to say which building leaked."""
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    clerk = staff_actor(tenant, "billing_clerk", "clerk@bayoubend.test")
    with tenant_ctx(tenant):
        bayou_bend_july(tenant, clerk, admin)
        result = cost_reconciliation.by_premises(
            period_start=JULY_START, period_end=JULY_END
        )
    assert {row["premises_label"] for row in result["rows"]} == {
        "1400 Cypress Court",
        "88 Magnolia Row",
        "3 Sabine Lofts",
    }
    assert all(row["reason"] is not None or row["unaccounted_for_pct"] is not None
               for row in result["rows"])


def test_cr060_t4__a_purchase_with_no_building_is_a_row_of_its_own(
    growth_plan, identity_seam
):
    """BR-REP-008 — a report STATES what it could not attribute.

    Folding an unattributed purchase into a building would put money on a
    building that did not buy it; dropping it would make the footer disagree
    with the register. So it is its own row, last, with its reason — and it
    carries NO percentage, because there is no per-building denominator to
    compare a tenant-wide cost against.
    """
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    clerk = staff_actor(tenant, "billing_clerk", "clerk@bayoubend.test")
    with tenant_ctx(tenant):
        bayou_bend_july(tenant, clerk, admin)
        cost_capture.capture_supplier_invoice(
            clerk,
            invoice_date=date(2026, 7, 20),
            service="water",
            supplier_name="City of Bayou Bend — Bulk Water",
            amount=Decimal("125.00"),
            currency="USD",
            volume=Decimal("40000"),
            volume_unit="gal",
            reference="BB-UNKEYED-01",
        )
        result = cost_reconciliation.by_premises(
            period_start=JULY_START, period_end=JULY_END
        )

    last = result["rows"][-1]
    assert last["premises_id"] is None
    assert last["premises_label"] is None
    assert last["unaccounted_for_pct"] is None
    assert cost_reconciliation.NO_PREMISES_KEYED in last["problems"]
    assert "no building was keyed on 1 water purchase" in last["reason"]
    # The footer still ties to the register: 3,875.00 + 125.00.
    assert result["total_bought_cost"] == TOTAL_BOUGHT_COST + Decimal("125.00")


def test_cr060_t4__a_non_commodity_category_never_enters_a_buildings_ratio(
    growth_plan, identity_seam
):
    """T7c's flag, one dimension over. A payroll figure inside a BUILDING's
    water denominator is not a smaller error than one inside a tenant's."""
    tenant = _bayou(growth_plan, identity_seam)
    admin = staff_actor(tenant, "system_admin", "renata@bayoubend.test")
    clerk = staff_actor(tenant, "billing_clerk", "clerk@bayoubend.test")
    with tenant_ctx(tenant):
        fixture = bayou_bend_july(tenant, clerk, admin)
        cost_capture.capture_supplier_invoice(
            clerk,
            invoice_date=date(2026, 7, 31),
            service="admin_payroll_benefits",
            supplier_name="Bayou Bend Payroll",
            amount=Decimal("12000.00"),
            currency="USD",
            premises_id=fixture["buildings"]["magnolia"]["id"],
            reference="BB-PAY-0726",
        )
        by_building = _rows_by_building(
            cost_reconciliation.by_premises(period_start=JULY_START, period_end=JULY_END)
        )

    payroll = by_building[("88 Magnolia Row", "admin_payroll_benefits")]
    assert payroll["enters_recovery_denominator"] is False
    assert payroll["unaccounted_for_pct"] is None
    assert cost_reconciliation.NO_VOLUME_DENOMINATOR in payroll["problems"]
    # And it did not touch the building's real figure.
    assert by_building[("88 Magnolia Row", "water")]["unaccounted_for_pct"] == MAGNOLIA_PCT


def test_cr060_t4__another_tenants_buildings_are_not_in_the_report(
    growth_plan, identity_seam
):
    """CLAUDE.md rule 1, at the read as well as at the write."""
    theirs = _bayou(growth_plan, identity_seam, "bayoubend")
    ours = _bayou(growth_plan, identity_seam, "cypressbend")
    their_admin = staff_actor(theirs, "system_admin", "renata@bayoubend.test")
    their_clerk = staff_actor(theirs, "billing_clerk", "clerk@bayoubend.test")
    our_admin = staff_actor(ours, "system_admin", "renata@cypressbend.test")
    with tenant_ctx(theirs):
        bayou_bend_july(theirs, their_clerk, their_admin)
    with tenant_ctx(ours):
        with_monthly_fiscal_year(our_admin)
        result = cost_reconciliation.by_premises(
            period_start=JULY_START, period_end=JULY_END
        )
    assert result["rows"] == ()
    assert result["total_bought_cost"] == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T4@premises-recovery (12-governance/11-change-requests.md CR-060 §7 C3 + C9, §9's `supplier_invoices` row, §11's test table and the T4 row in §12 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-029/030/031/032 · apps/ledger/cost_reconciliation.py, read from the code)
# generated: 2026-09-01 by the CR-060 T2/T3/T4 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN, and the failures are quoted as OBSERVED rather
#         than as predicted (DEF-182: a check whose output cannot distinguish
#         pass from fail is worse than no check).
#         ① **THE BUILDING KEY DROPPED FROM THE GROUPING** (`by_key` keyed on a
#         constant instead of `row.premises_id`), which is what this report
#         looked like before T4: the three buildings collapse into one row and
#         both live cases fail —
#             `AssertionError: assert None == '88 Magnolia Row'`
#             `KeyError: ('3 Sabine Lofts', 'water')`
#         The label is `None` because the collapsed row belongs to no building
#         and the KeyError is Sabine having no row of its own at all, which is
#         precisely the state C9 exists to end.
#         ② **THE ALL-OR-NOTHING BRANCH BYPASSED** in `_row_for` (the
#         `purchases_missing_volume` early return removed), so Sabine's partial
#         denominator is computed —
#             `AssertionError: assert Decimal('-58.33') is None`
#         a building that appears to have delivered more water than it bought.
# exceptions: the billed denominator's per-building read runs on billing's
#         PUBLISHED `invoice_queryset` plus `dimension_seam.location_for_account`
#         because billing publishes no per-premises read — PARKED beside its
#         tenant-wide twin in 10-scripts/gates/seam_known_gaps.txt · OQ-201 and
#         OQ-202 ride every row here exactly as they ride the service-grained
#         report, asserted as LABELS and never as chosen answers
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
