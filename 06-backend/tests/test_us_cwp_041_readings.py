# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-041 (EP-CWP-08) — *Every reading, how it was taken, and why
#           one was corrected*. Screen: CWP-034 (blueprint `P20`)
# Rules:    BR-CWP-071 (the method is shown as prominently as the number,
#           estimation included) · BR-CWP-072 (why a read was corrected, and by
#           how much) · BR-CWP-069 (a superseded read must not leave the
#           customer charged twice) · BR-CWP-041 (a draft is not a bill) ·
#           CLAUDE.md hard rule 3 (every quantity with its unit) ·
#           BR-MET-016/053 (lineage heads only)
# Tests:    this file — `US-CWP-041` §3 TC-1 … TC-9
# Impacts:  apps/metering/portal_reads.py · apps/portal/seams/billing_seam.py
#           `bill_number_covering` · apps/portal/selectors.py
# ───────────────────────────────────────────────────────
"""`US-CWP-041`'s cases. **The negative ones carry the story.**

TC-4 (a reading nobody has billed shows an EMPTY bill cell, not a guess), TC-5
(a superseded read is represented by its correction and never counted twice),
TC-6 (no reads at all) and TC-9 (a used-since cell without its unit is not
served) are what stop *"you estimated and overcharged me"* being a phone call.

⚠ **TC-4's SECOND HALF IS NOT ASSERTED HERE AND THE REASON IS SCHEMA, NOT
SCOPE.** The story's row reads *"You sent it in · awaiting review"*, and
`meter_read.review_state` is a **GAP** column declared in `US-CWP-042` §5 —
wave 3. Nothing in this product can hold that value today, so the suffix is not
built and a test for it would be a test of a fixture. The half that IS live —
the empty *on which bill* cell — is asserted below, and the boundary is in the
decision log for 2026-09-04 and in `EP-CWP-08` §3.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.metering import models as metering_models
from apps.portal import selectors
from core.dbfields import uuid7
from core.tenancy import tenant_context

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import (
    CORRECTED_DIAL,
    CORRECTED_ON,
    ESTIMATED_DIAL,
    a_read,
    a_water_meter,
    elm_unit_with_services,
)
from tests.test_us_cwp_helpers import an_issued_bill

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 2)


class _Principal:
    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def four_readings(tenant, actor):
    """`US-CWP-041` §4's own four rows, and the bills three of them fed."""
    account = elm_unit_with_services(tenant, actor)
    meter = a_water_meter(tenant, actor, account.unit_id)

    a_read(tenant, account, meter["id"], day=date(2026, 5, 31),
           current="140370", consumption="3410",
           read_method="self_read", source_detail="self_read")
    estimate = a_read(tenant, account, meter["id"], day=date(2026, 6, 30),
                      current=str(ESTIMATED_DIAL), consumption="4230",
                      read_method=None, source="manual", source_detail=None,
                      status="estimated")

    # ⚠ **THE SUPERSEDE COMES BEFORE THE REPLACEMENT, AND THE DATABASE INSISTS.**
    # `uq_meter_reads_head` is unique over LINEAGE HEADS, so the estimate must
    # stop being one before a second row exists for `30 June` — which means the
    # replacement's id has to be allocated first. This is the ONE update
    # hard rule 4 permits on a committed read (B2 r8); the estimate's own
    # figures are not rewritten, it is only pointed at.
    correction_id = uuid7()
    with tenant_context(tenant.id):
        metering_models.MeterRead.objects.filter(pk=estimate.pk).update(
            superseded_by_id=correction_id,
            superseded_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
            supersede_reason="Meter read on 3 July",
        )
    a_read(tenant, account, meter["id"], day=date(2026, 6, 30),
           current=str(CORRECTED_DIAL), consumption="3760", read_id=correction_id)
    a_read(tenant, account, meter["id"], day=date(2026, 7, 31),
           current="148220", consumption="4090")
    a_read(tenant, account, meter["id"], day=date(2026, 8, 31),
           current="153040", consumption="4820")

    with tenant_context(tenant.id):
        an_issued_bill(tenant, account, number="BL-2606-0147", total="129.0200",
                       issued_on=date(2026, 6, 30))
        an_issued_bill(tenant, account, number="BL-2607-0139", total="138.4400",
                       issued_on=date(2026, 7, 31))
        an_issued_bill(tenant, account, number="BL-2608-0141", total="142.1800",
                       issued_on=date(2026, 8, 31))
    return account, meter


def read(tenant, account):
    with tenant_context(tenant.id):
        return selectors.account_readings(
            _Principal(tenant.id, [account.pk]), account, today=date(2026, 9, 2)
        )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · FOUR READINGS, EACH WITH ITS METHOD AND THE BILL IT FED
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__each_row_carries_its_method_and_the_bill_it_fed(pine_hill, sarah):
    account, _meter = four_readings(pine_hill, sarah)
    rows = read(pine_hill, account)["readings"]

    #: Newest first — the story's own order.
    assert [row["taken_on"] for row in rows] == [
        "2026-08-31", "2026-07-31", "2026-06-30", "2026-05-31",
    ]
    by_date = {row["taken_on"]: row for row in rows}
    assert by_date["2026-08-31"]["how"] == "reader"
    assert by_date["2026-08-31"]["on_bill"] == "BL-2608-0141"
    assert by_date["2026-07-31"]["on_bill"] == "BL-2607-0139"
    #: ⚠ **THE METHOD IS A CODE, NOT A SENTENCE** — eleven catalogues write the
    #: words (B14 rule 35), and a server that shipped the English would make
    #: ten of them impossible.
    assert by_date["2026-08-31"]["read_method"] == "walk_by"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE ESTIMATED ROW — ITS REASON *AND* ITS SIZE (`BR-CWP-072`)
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__the_corrected_row_carries_both_figures_and_the_date(pine_hill, sarah):
    """*"estimated 144,600, corrected to 144,130 when the meter was read on
    3 July — you were not charged twice"* — five keys, one sentence per
    catalogue."""
    account, _meter = four_readings(pine_hill, sarah)
    row = next(r for r in read(pine_hill, account)["readings"] if r["taken_on"] == "2026-06-30")

    assert row["how"] == "estimated_corrected"
    correction = row["correction"]
    assert correction is not None
    assert correction["estimated_reading_display"] == "144600"
    assert correction["corrected_to_display"] == "144130"
    #: ⚠ **3 JULY, NOT 30 JUNE.** Both rows carry `read_at = 30 June` — that is
    #: the PERIOD — and the day somebody went and looked is the estimate's
    #: `superseded_at`. The story's sentence is *"when the meter was read on
    #: 3 July"*, and a screen that printed 30 June would be naming the month
    #: rather than the visit.
    assert correction["corrected_on"] == "2026-07-03"
    assert correction["reason"] == "Meter read on 3 July"


def test_tc2b__the_corrected_row_is_the_only_one_for_that_date(pine_hill, sarah):
    """`BR-CWP-069` held at the DISPLAY layer: the estimate it replaced is not a
    second line a customer would count twice — it is that row's `correction`."""
    account, _meter = four_readings(pine_hill, sarah)
    rows = read(pine_hill, account)["readings"]
    assert [r["taken_on"] for r in rows].count("2026-06-30") == 1


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · A CUSTOMER-SUBMITTED ROW READS *You sent it in*
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__a_self_read_is_named_as_the_customers_own(pine_hill, sarah):
    account, _meter = four_readings(pine_hill, sarah)
    row = next(r for r in read(pine_hill, account)["readings"] if r["taken_on"] == "2026-05-31")
    assert row["how"] == "self_read"


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · negative — A READING NO ISSUED BILL COVERS SHOWS AN EMPTY CELL
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__a_reading_no_bill_covers_names_no_bill_at_all(pine_hill, sarah):
    """⚠ **NOT THE NEAREST BILL.** Naming one would tell a customer they were
    charged for a reading nobody has billed."""
    account, meter = four_readings(pine_hill, sarah)
    a_read(pine_hill, account, meter["id"], day=date(2026, 9, 2),
           current="153300", consumption="260",
           read_method="self_read", source_detail="self_read")
    row = next(r for r in read(pine_hill, account)["readings"] if r["taken_on"] == "2026-09-02")
    assert row["on_bill"] is None
    assert row["how"] == "self_read"


def test_tc4b__a_draft_bill_is_never_named(pine_hill, sarah):
    """`BR-CWP-041` — a draft is the utility's working copy. The filter is in
    the QUERY, so no screen can reach past it."""
    from apps.billing import models as billing_models

    account = elm_unit_with_services(pine_hill, sarah)
    meter = a_water_meter(pine_hill, sarah, account.unit_id)
    a_read(pine_hill, account, meter["id"], day=date(2026, 8, 31),
           current="153040", consumption="4820")
    with tenant_context(pine_hill.id):
        billing_models.Invoice.objects.create(
            tenant=pine_hill, account=account, invoice_no="BL-DRAFT-0001",
            status=billing_models.INVOICE_DRAFT,
            service_date=date(2026, 8, 31),
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
            due_date=date(2026, 9, 14),
            subtotal=Decimal("100"), tax_total=Decimal("0"), total=Decimal("100"),
        )
    rows = read(pine_hill, account)["readings"]
    assert rows[0]["on_bill"] is None


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · negative — AN ACCOUNT WITH NO READS
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__no_reads_is_an_empty_list_the_screen_states(pine_hill, sarah):
    account = elm_unit_with_services(pine_hill, sarah)
    a_water_meter(pine_hill, sarah, account.unit_id)
    assert read(pine_hill, account)["readings"] == []


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · tenant isolation
# ══════════════════════════════════════════════════════════════════════════
def test_tc7__an_oak_ridge_session_cannot_read_pine_hills_readings(
    pine_hill, sarah, oak_ridge, elena
):
    account, _meter = four_readings(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        with pytest.raises(RuntimeError, match="BR-CWP-005"):
            selectors.account_readings(
                _Principal(pine_hill.id, [account.pk]), account, today=date(2026, 9, 2)
            )


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · A ROLLOVER — USED-SINCE COMES THROUGH IT, NEVER NEGATIVE
# ══════════════════════════════════════════════════════════════════════════
def test_tc8__a_rollover_used_since_is_the_stored_figure_and_is_positive(pine_hill, sarah):
    """⚠ **THE SCREEN DOES NOT SUBTRACT AND NEITHER DOES THE SEAM.** `000,400`
    after `999,900` is `500 gal`, computed by metering's own rollover handling
    at commit; anything that subtracted the two dial figures would print
    `−999,500 gal` for exactly the customer whose meter rolled over."""
    account = elm_unit_with_services(pine_hill, sarah)
    meter = a_water_meter(pine_hill, sarah, account.unit_id)
    a_read(pine_hill, account, meter["id"], day=date(2026, 7, 31),
           current="999900", consumption="4100")
    a_read(pine_hill, account, meter["id"], day=date(2026, 8, 31),
           current="400", consumption="500", prior="999900", status="rollover")

    row = read(pine_hill, account)["readings"][0]
    assert row["used_since_display"] == "500 gal"
    assert not row["used_since_display"].startswith("-")


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · negative — EVERY USED-SINCE CELL CARRIES ITS UNIT, OR IS NOT SERVED
# ══════════════════════════════════════════════════════════════════════════
def test_tc9__a_quantity_with_no_unit_is_not_rendered_bare(pine_hill, sarah):
    """CLAUDE.md hard rule 3, held at the last step before a screen:
    `quantity_with_unit` returns `None` rather than a bare number, and the cell
    dashes. `4,820` means nothing; `4,820 gal` is the whole column."""
    account = elm_unit_with_services(pine_hill, sarah)
    meter = a_water_meter(pine_hill, sarah, account.unit_id)
    a_read(pine_hill, account, meter["id"], day=date(2026, 8, 31),
           current="153040", consumption="4820")
    with tenant_context(pine_hill.id):
        metering_models.MeterRead.objects.filter(asset_id=meter["id"]).update(unit="")

    row = read(pine_hill, account)["readings"][0]
    assert row["used_since_display"] is None
    assert row["used_since"] == "4820.000000"


def test_tc9b__a_normal_used_since_carries_its_unit(pine_hill, sarah):
    account, _meter = four_readings(pine_hill, sarah)
    rows = read(pine_hill, account)["readings"]
    assert rows[0]["used_since_display"] == "4820 gal"
    for row in rows:
        if row["used_since"] is not None:
            assert row["used_since_display"].endswith(" gal")
