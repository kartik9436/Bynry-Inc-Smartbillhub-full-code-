# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8244 — "Meter swapped → bill both parts" was a tag with no
#          computation behind it: an exchange always fell to the anchor's
#          exchange refusal, so the ratified suggestion could never be made.
# Rulings: changes rows 44–46 (PO 2026-09-30, *"these are correct"*; *"we
#          point it out and suggest but dont make it auto"*; *"for all suto
#          cases put them in tag buckets and allow user to fic it"*) — meter
#          swapped with BOTH readings recorded → suggest *bill both parts*; a
#          reading missing → Estimate the missing part / Hold.
# Rows:    BULK-CHG-44 · BULK-CHG-45 · BULK-CHG-46 · BULK-CHG-60
# Amended: PO 2026-10-01 (*"B · Price each meter separately"*) — one reading per
#          meter part; on this flat $0.12 rate the $24.60 is unchanged.
# Code:    apps/billing/runs.py `_meter_swap` · contracts.ServiceReading
#          .meter_parts · stages/assemble_document.py · metering_seam.read_ids_on
# ───────────────────────────────────────────────────────
"""Meter swapped inside the period: both parts priced on one bill.

THE WORKED FIGURES (plan: $0.120000 per kWh; the fixture binds no base charge)
------------------------------------------------------------------------------
The May bill closed OLD meter M-5280 at **13,500**. On 10 June the old meter
came out at **13,620**; the NEW meter went in at **0** and reads **85** on
29 June.

    old part   13,620 − 13,500 = 120 kWh
    new part   85 − 0          =  85 kWh
    the bill   205 kWh × $0.12 = **$24.60**, on ONE electric line

Before the fix the account was refused as an exchange. Billing only the new
meter's reading would have been 85 kWh = $10.20 — **120 kWh ($14.40) billed to
nobody**, which is the loss the PO's 2026-09-14 anchor ruling exists to stop.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import check_store, decisions, metering_seam, runs
from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors

from tests.test_bbr_check_store import a_run as a_check_run
from tests.test_us_bil_001_prepare import a_billed_unit, a_cycle, a_priced_plan, an_account
from tests.test_us_bil_004_run_loop import a_run, prepared_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ACCEPT_FOR_ALL = {("*", "", "meter_swapped"): "accept_suggestion"}


def a_swapped_meter(tenant, actor, *, old_final=True, new_start="0", new_value="85", no="5280"):
    """An account whose meter was exchanged in June, after a May bill.

    `old_final=False` leaves the old meter with no reading after the one the
    May bill closed on; `new_start=None` records the new meter's reading with
    no start register. Either is ONE PART MISSING.
    """
    from apps.assets import models as asset_models
    from apps.assets import services as asset_services
    from apps.metering import models as metering_models
    from tests.test_us_met_reads_helpers import a_meter, commit_read

    cycle = a_cycle(tenant)
    # base_code=False: the worked figures above bind no base charge (DEF-BIL-8671
    # made binding the default for every other caller of this fixture).
    plan = a_priced_plan(tenant, base_code=False)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no=f"M-{no}", label="Unit A", consumption=None
    )
    account = an_account(tenant, unit["id"], f"A-{no}1")
    old_id = asset_models.Asset.objects.get(tenant=tenant, asset_no=f"M-{no}").id
    anchor = commit_read(
        actor,
        old_id,
        day="2026-05-28",
        value="13500",
        prior_value="13100",
        consumption="400.000000",
        unit="kWh",
    )
    # The May bill, ISSUED with the read it closed on in its own snapshot. Built
    # with the payload at creation: on PostgreSQL an issued invoice refuses
    # any later UPDATE but its status (BR-BIL-004 trigger).
    billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        status=billing_models.INVOICE_ISSUED,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        service_date=date(2026, 5, 31),
        currency="USD",
        total=Decimal("0.000000"),
        subtotal=Decimal("0.000000"),
        tax_total=Decimal("0.000000"),
        bill_payload={"services": [{"code": "electric", "read_id": str(anchor.id)}]},
    )
    old_final_read = None
    if old_final:
        old_final_read = commit_read(
            actor,
            old_id,
            day="2026-06-10",
            value="13620",
            prior_value="13500",
            consumption="120.000000",
            unit="kWh",
        )
    new_meter = a_meter(actor, asset_no=f"M-{no}-NEW", unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    # An exchange takes the old device OUT of service (see DEF-BIL-5270 tc5c).
    asset_models.Asset.objects.filter(tenant=tenant, id=old_id).update(
        status=asset_services.stage_by_code("retired")
    )
    new_read = commit_read(
        actor,
        new_meter["id"],
        day="2026-06-29",
        value=new_value,
        prior_value=new_start,
        # With no start register the reading still carries a quantity here, so
        # the ONLY thing missing is the part's opening figure.
        consumption=f"{Decimal(new_value) - Decimal(new_start or 0)}.000000",
        unit="kWh",
    )
    return SimpleNamespace(
        cycle=cycle, account=account, old_final=old_final_read, new_read=new_read
    )


def _electric(data):
    return next(r for r in data.readings if r.service_code == "electric")


# BULK-CHG-45 · BULK-CHG-46
def test_def_bil_8244__both_parts_recorded_is_a_meter_swapped_suggestion_not_a_bill(brazos, dana):
    """Nothing is billed on a suggestion nobody accepted (row 45)."""
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana)
        prepared = prepared_for(case.cycle)

        assert prepared.ready == ()
        [problem] = [p for p in prepared.blocked if p.account_no == case.account.account_no]
        assert problem.reason == "meter_swapped"
        assert "bill both parts, 205" in problem.detail


# BULK-CHG-44 · BULK-CHG-45 · BULK-CHG-46
def test_def_bil_8244__the_check_lists_it_under_meter_swapped_with_both_parts(brazos, dana):
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana)
        run = a_check_run(case.cycle)
        check_store.check_run(run)

        page = check_store.tag_accounts(run, "meter_swapped", {})
        assert [r["account_no"] for r in page["results"]] == [case.account.account_no]
        params = page["results"][0]["params"]
        assert (Decimal(params["old_from"]), Decimal(params["old_to"])) == (
            Decimal("13500"),
            Decimal("13620"),
        )
        assert Decimal(params["old_quantity"]) == Decimal("120")
        assert (Decimal(params["new_from"]), Decimal(params["new_to"])) == (
            Decimal("0"),
            Decimal("85"),
        )
        assert Decimal(params["new_quantity"]) == Decimal("85")
        assert Decimal(params["suggested_quantity"]) == Decimal("205")
        assert params["unit"] == "kWh"
        assert page["tag"]["choices"][0] == "accept_suggestion"
        assert billing_selectors.prepared_for(run).ready == ()


# BULK-CHG-44 · BULK-CHG-46
def test_def_bil_8244__accepted_the_bill_carries_both_parts_205_kwh_24_60(brazos, dana):
    """The answer fed to the pass exactly as `selectors.prepared_for` feeds a
    recorded one (`runs.open_answers`)."""
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana)
        token = runs.open_answers(ACCEPT_FOR_ALL)
        try:
            prepared = prepared_for(case.cycle)
            [data] = prepared.ready
            # PO 2026-10-01, *"B · Price each meter separately"* (BR-BIL-1062):
            # the swap arrives as ONE READING PER METER, each with its own pair.
            old_reading, new_reading = [r for r in data.readings if r.service_code == "electric"]
            assert [r.consumption.amount for r in (old_reading, new_reading)] == [
                Decimal("120"),
                Decimal("85"),
            ]
            assert {r.consumption.unit for r in (old_reading, new_reading)} == {"kWh"}
            [old] = old_reading.meter_parts
            [new] = new_reading.meter_parts
            reading = new_reading
            assert old["meter"] == "M-5280"
            assert (Decimal(old["from"]), Decimal(old["to"])) == (
                Decimal("13500"),
                Decimal("13620"),
            )
            assert Decimal(old["quantity"]) == Decimal("120")
            assert old["read_id"] == str(case.old_final.id)
            assert new["meter"] == "M-5280-NEW"
            assert Decimal(new["quantity"]) == Decimal("85")
            assert new["read_id"] == str(case.new_read.id) == reading.read_id

            result = runs.calculate_run(prepared, bill_run=a_run(brazos, case.cycle))
        finally:
            runs.close_answers(token)
        assert result.drafted_count == 1 and result.breaks == ()
        invoice = billing_models.Invoice.objects.get(
            account=case.account, status=billing_models.INVOICE_DRAFT
        )
        # 120 kWh × $0.12 + 85 kWh × $0.12 = $14.40 + $10.20 = $24.60 — both
        # parts, each priced as its own meter (PO 2026-10-01; on this FLAT rate
        # the sum is unchanged). Billing the new meter alone would be $10.20.
        assert invoice.total == Decimal("24.60")
        services = invoice.bill_payload["services"]
        assert [Decimal(p["quantity"]) for s in services for p in s["meter_parts"]] == [
            Decimal("120"),
            Decimal("85"),
        ]
        # BR-MET-053 — BOTH readings this bill priced are locked at issue.
        assert set(metering_seam.read_ids_on(invoice)) == {
            str(case.old_final.id),
            str(case.new_read.id),
        }


# BULK-CHG-44
def test_def_bil_8244__no_old_final_reading_stays_the_exchange_decision(brazos, dana):
    """One part missing → the ruled *Estimate the missing part / Hold*, never
    a suggestion built on a part nobody read."""
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana, old_final=False, no="5281")
        token = runs.open_answers(ACCEPT_FOR_ALL)
        try:
            prepared = prepared_for(case.cycle)
        finally:
            runs.close_answers(token)
        assert prepared.ready == ()
        assert [p.reason for p in prepared.blocked] == [runs.ANCHOR_METER_EXCHANGED]


# BULK-CHG-44
def test_def_bil_8244__new_meter_start_not_recorded_stays_the_exchange_decision(brazos, dana):
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana, new_start=None, no="5282")
        token = runs.open_answers(ACCEPT_FOR_ALL)
        try:
            prepared = prepared_for(case.cycle)
        finally:
            runs.close_answers(token)
        assert prepared.ready == ()
        assert [p.reason for p in prepared.blocked] == [runs.ANCHOR_METER_EXCHANGED]


# BULK-CHG-45
def test_def_bil_8244__a_recorded_accept_bills_both_parts_end_to_end(brazos, dana):
    with tenant_ctx(brazos):
        case = a_swapped_meter(brazos, dana, no="5283")
        run = a_check_run(case.cycle)
        check_store.check_run(run)
        decisions.set_standing_answer(
            bill_run=run, case="meter_swapped", choice="accept_suggestion"
        )
        [data] = billing_selectors.prepared_for(run).ready
        parts = [r.consumption.amount for r in data.readings if r.service_code == "electric"]
        assert parts == [Decimal("120"), Decimal("85")] and sum(parts) == Decimal("205")


def test_def_bil_8244__read_ids_on_names_both_parts():
    invoice = SimpleNamespace(
        bill_payload={
            "services": [
                {
                    "code": "electric",
                    "read_id": "new",
                    "meter_parts": [{"read_id": "old"}, {"read_id": "new"}],
                },
                {"code": "water", "read_id": "w"},
            ]
        }
    )
    assert metering_seam.read_ids_on(invoice) == ("new", "old", "w")


def test_def_bil_8244__the_worked_figures_foot():
    # The module docstring's arithmetic, so a reader can check the figures.
    assert (Decimal("13620") - Decimal("13500")) + (Decimal("85") - Decimal("0")) == 205
    assert Decimal("205") * Decimal("0.12") == Decimal("24.60")
    assert Decimal("120") * Decimal("0.12") == Decimal("14.40")
    assert date(2026, 6, 10) < date(2026, 6, 29)
