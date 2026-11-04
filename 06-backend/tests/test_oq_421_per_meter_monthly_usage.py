# ── Trace ──────────────────────────────────────────────
# Change:   OQ-421 CLOSED 2026-08-27 — store the twelve-month usage PER METER
#           as well. PO verbatim: *"(b) Store it per meter too - otherwise we
#           will ahve to calculate it again and again"*.
#           Screens: S50 (the meter strip) · S21 (the account tab it must
#           never disagree with)
# Rules:    BR-MET-141 (the per-meter stored grain) · BR-MET-106 (computed from
#           reads, STORED, RESTATED never edited, ABSENT when unread, estimates
#           counted and MARKED) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           rule 3 (an explicit unit) · rule 4 (corrections are new rows) ·
#           rule 6 (idempotency)
# Defects:  DEF-798 (684 + 14 = 698 kWh where the truth is 684 kWh) — TC-2
#           asserts the wrong number is not merely absent but UNREACHABLE at
#           this grain
# ───────────────────────────────────────────────────────
"""BR-MET-141 — the per-meter stored month, and the four things it must be.

**THE WORKED NUMBER A REVIEWER WAS SHOWN.** Sarah's meter M-4412 reports a
684 kWh energy total and a 14 kW demand peak on the same July day. This build
stores **two rows** — `total 684.000000 kWh` and `demand 14.000000 kWh` — and
the account's own BR-MET-106 row stores **684.000000 kWh**. **698 appears
nowhere and cannot**, because the register is part of the key.

Four properties, one test case each, and none of them is optional:

  1. **The stored figure and the computed figure are the same figure** (TC-1,
     and the amended TC-10 next door). The decision log's one constraint on
     this build: *"the stored per-meter row must be produced by the SAME
     functions the computed figure uses, not a second implementation."*
  2. **DEF-798's wrong number is unrepresentable** (TC-2), rather than merely
     currently absent. Storing a figure freezes whatever the derivation gets
     wrong, so this is checked at the grain and not only at the value.
  3. **It is a CACHE, not a FACT** (TC-3). Delete every row and the identical
     payload comes back from the reads. That is the answer to the asymmetry
     OQ-421 put to the PO: less reversible in SCHEMA, fully reversible in
     MEANING.
  4. **Rule 6 and rule 4 hold at the new grain too** (TC-4, TC-5, TC-6): a
     second recompute writes nothing, a changed read RESTATES rather than
     edits, and a withdrawn month goes back to ABSENT rather than to zero.

TC-7 is the model↔table introspection pin the `managed = False` disposition
owes, TC-8 is the tenant-scoping case, and TC-9 is the NARROW entry point —
`recompute_month`, the one a read correction uses — which must move both grains
or the ruling's constraint holds only on the path nobody takes.

────────────────────────────────────────────────────────────────────────────
PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
The sabotage was the exact fault the decision log forbids — **a second
implementation of the figure**, injected between `summarise` and the writer so
the stored row said 843 where the account row said 842. Every one of the three
claims went red, with its own sentence, and none of them was a generic
"something differs":

    TC-1  E  AssertionError: assert Decimal('843.000000') == Decimal('842.000000')
             +  where Decimal('843.000000') = <AssetMonthlyUsage …>.quantity
             +  and   Decimal('842.000000') = <MonthlyUsage …>.quantity

    TC-3  E  AssertionError: the stored figure and the computed one are not
             the same figure

    …and the anti-drift pin next door, which is the test that has to survive
    this build for the account and the meter to keep agreeing:

    test_def_798…tc10  E  AssertionError: assert '842.000000' == '843.000000'

The sabotage was then reverted and the file re-read from HEAD.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import connection

from apps.assets import services as asset_services
from apps.customers import services as customers_services
from apps.metering import asset_usage
from apps.metering import models as metering_models
from apps.metering import monthly_usage_service as usage_service
from apps.metering.monthly_usage_asset import TABLE, AssetMonthlyUsage
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing (the same shape as test_def_798_register_blind_usage) ──
def _plan(tenant, service_code="electric", name="Small Commercial"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account_on(actor, tenant, *, service="electric"):
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label="Unit A")
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service).id)}
    )
    metering_services.ensure_service_point(unit["id"], service)
    account = customers_services.create_account(
        actor,
        {
            "unit_id": unit["id"],
            "account_type": "residential",
            "opened_at": "2024-01-05",
            "contact": {"full_name": "Sarah Chen", "email": "sarah@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block("Sarah Chen", account_type="residential"),
        },
    )
    return account, unit


def _meter(actor, unit_id, *, asset_no, service="electric", uom="kWh"):
    return asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service,
            "unit": uom,
            "read_method": "walk_by",
            "multiplier": "1",
            "unit_id": unit_id,
            "install_date": "2024-01-05",
            "status": "active",
        },
    )


def _read(tenant, account_id, asset_id, *, day, consumption, channel="total", unit="kWh"):
    """One committed read on ONE REGISTER — HISTORY SETUP only."""
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        channel=channel,
        current_value=Decimal("1000"),
        consumption=Decimal(str(consumption)),
        unit=unit,
        source="import",
        status="ok",
        lifecycle="committed",
    )


def _heads(asset_id, *, channel=None):
    qs = AssetMonthlyUsage.objects.filter(
        asset_id=asset_id, superseded_by_id__isnull=True, superseded_at__isnull=True
    )
    if channel is not None:
        qs = qs.filter(channel=channel)
    return list(qs.order_by("channel", "period_month"))


def _july_point(payload, channel="total"):
    series = [s for s in payload["series"] if s["channel"] == channel][0]
    return [p for p in series["points"] if p["month"] == "2026-07"][0]


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE STORED ROW IS THE FIGURE THE ACCOUNT TAB PRINTS
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc1__the_stored_meter_row_carries_the_account_figure(brazos, marcus):
    """One account, one meter, one register, two July reads: **684 + 158 = 842
    kWh**. The account's BR-MET-106 row says 842; the meter's BR-MET-141 row
    says 842; the S50 payload prints 842 from the row rather than from the
    reads. One derivation, two grains, one number."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5101")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 31), consumption="158.000000")

        usage_service.recompute_account(account["id"], actor=marcus)

        account_row = metering_models.MonthlyUsage.objects.get(
            account_id=account["id"],
            period_month=date(2026, 7, 1),
            superseded_by_id__isnull=True,
        )
        meter_rows = _heads(meter["id"])
        assert len(meter_rows) == 1, "one register reported, so one stored row"
        meter_row = meter_rows[0]

        assert meter_row.quantity == account_row.quantity == Decimal("842.000000")
        assert meter_row.unit == account_row.unit == "kWh"  # hard rule 3
        assert meter_row.read_count == account_row.read_count == 2
        assert meter_row.channel == "total"
        assert meter_row.period_month == date(2026, 7, 1)
        # The provenance BR-MET-106 asks a restatement to carry, at the finer
        # grain: the SAME lineage heads the account row summed.
        assert sorted(meter_row.source_read_ids) == sorted(account_row.source_read_ids)

        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert payload["source"] == "stored"
        assert _july_point(payload)["quantity"] == "842.000000"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · DEF-798's 698 IS NOT MERELY ABSENT — IT IS UNREACHABLE
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc2__the_stored_grain_cannot_hold_a_cross_register_sum(brazos, marcus):
    """DEF-798, verbatim: *"a demand peak-delta lands in the ENERGY total …
    **Measured: 684 + 14 = 698 kWh where the truth is 684 kWh**"*.

    ⚠ **A WRONG NUMBER THAT IS RECOMPUTED IS A BUG; A WRONG NUMBER THAT IS
    STORED IS A RECORD.** So this asserts the property and not only the value:
    the register is part of the key, so the two figures are two ROWS, and no
    row in this table is a sum across registers. 698 cannot be written by any
    path in the writer, and the account's own row still reads 684."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5102")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 15),
            consumption="14.000000",
            channel="demand",
        )

        usage_service.recompute_account(account["id"], actor=marcus)

        by_channel = {row.channel: row for row in _heads(meter["id"])}
        assert set(by_channel) == {"total", "demand"}, "one row per REGISTER, never one per meter"
        assert by_channel["total"].quantity == Decimal("684.000000")
        assert by_channel["demand"].quantity == Decimal("14.000000")
        # Each row counts only its own register's evidence — a read_count of 2
        # beside 684 would be a figure credited to more evidence than it had.
        assert by_channel["total"].read_count == 1
        assert by_channel["demand"].read_count == 1

        account_row = metering_models.MonthlyUsage.objects.get(
            account_id=account["id"],
            period_month=date(2026, 7, 1),
            superseded_by_id__isnull=True,
        )
        assert account_row.quantity == Decimal("684.000000")

        stored = [str(row.quantity) for row in AssetMonthlyUsage.objects.all()]
        assert not any("698" in q for q in stored), "DEF-798's wrong number reached the table"
        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert "698" not in str(payload)


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · A CACHE, NOT A FACT — delete every row and nothing is lost
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc3__dropping_every_stored_row_loses_a_cache_and_not_a_fact(brazos, marcus):
    """OQ-421 put the asymmetry to the PO before they ruled: adding the
    dimension is a migration, removing it is dropping a column with data in it.
    They ruled for it knowingly. **This is the property that makes the ruling
    safe to reverse:** every column is derivable from `meter_reads`, and the
    payload computes the identical figure when no row exists. Point for point,
    not merely "about the same"."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5103")
        _read(brazos, account["id"], meter["id"], day=date(2026, 5, 9), consumption="412.000000")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 15), consumption="684.000000")
        _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 7, 15),
            consumption="14.000000",
            channel="demand",
        )
        usage_service.recompute_account(account["id"], actor=marcus)

        stored = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert stored["source"] == "stored"

        AssetMonthlyUsage.objects.all().delete()

        computed = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert computed["source"] == "computed_from_reads"
        assert computed["stored_source_absent"] == {
            "reason": "not_recomputed_yet",
            "tracks": "BR-MET-141",
        }

        # Everything except the two fields that describe WHERE it came from.
        for payload in (stored, computed):
            payload.pop("source")
            payload.pop("stored_source_absent")
        assert stored == computed, "the stored figure and the computed one are not the same figure"


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · RULE 6 AT THE NEW GRAIN — a second recompute writes nothing
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc4__recomputing_unchanged_reads_writes_nothing(brazos, marcus):
    """CLAUDE.md rule 6, over CONTENT because nobody submits a "monthly usage
    request": the key is the sorted lineage-head ids plus the quantity, the
    unit and the estimate count, SHA-256. Three recomputes leave one row and do
    not restamp `computed_at` — a new timestamp on an unchanged figure is a
    restatement that did not happen."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5104")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")

        first = usage_service.recompute_account_assets(account["id"], actor=marcus)
        assert first == {"stated": 1, "restated": 0, "unchanged": 0, "withdrawn": 0}
        head = _heads(meter["id"])[0]

        for _ in range(3):
            again = usage_service.recompute_account_assets(account["id"], actor=marcus)
            assert again == {"stated": 0, "restated": 0, "unchanged": 1, "withdrawn": 0}

        assert AssetMonthlyUsage.objects.filter(asset_id=meter["id"]).count() == 1
        after = AssetMonthlyUsage.objects.get(pk=head.pk)
        assert after.computed_at == head.computed_at


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · RULE 4 AT THE NEW GRAIN — a correction RESTATES, it never edits
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc5__a_corrected_read_restates_the_meter_month(brazos, marcus):
    """A late read supersedes the first and the month is RESTATED: the old row
    keeps its 684 and the quantity it was true for, a NEW row carries 700, and
    the strip reads the head. Hard rule 4 — corrections are new rows."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5105")
        first_read = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000"
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        original = _heads(meter["id"])[0]

        # The correction is a NEW row on the 4th (`meter_reads` holds one row
        # per asset/instant/register) and the old one is marked superseded —
        # the ONE update B2 r8 permits on a committed read.
        correction = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 4), consumption="700.000000"
        )
        metering_models.MeterRead.objects.filter(pk=first_read.pk).update(
            superseded_by_id=correction.id, superseded_at=datetime.now(timezone.utc)
        )
        counts = usage_service.recompute_account_assets(account["id"], actor=marcus)
        assert counts["restated"] == 1

        head = _heads(meter["id"])[0]
        assert head.quantity == Decimal("700.000000")
        superseded = AssetMonthlyUsage.objects.get(pk=original.pk)
        assert superseded.quantity == Decimal("684.000000"), "the old statement was EDITED"
        assert superseded.superseded_by_id == head.id
        assert superseded.supersede_reason == "reads_changed"

        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert _july_point(payload)["quantity"] == "700.000000"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · A WITHDRAWN MONTH GOES BACK TO ABSENT, NEVER TO ZERO
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc6__a_meter_month_whose_reads_are_withdrawn_goes_absent_once(brazos, marcus):
    """BR-MET-106: *"zero usage and no read are different claims about a
    customer"*. The head is superseded with NO successor and nothing replaces
    it; a second recompute does not withdraw it again, or every run would write
    another audit row forever."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5106")
        read = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000"
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        assert len(_heads(meter["id"])) == 1

        metering_models.MeterRead.objects.filter(pk=read.pk).update(
            superseded_by_id=read.id, superseded_at=datetime.now(timezone.utc)
        )
        counts = usage_service.recompute_account_assets(account["id"], actor=marcus)
        assert counts["withdrawn"] == 1
        assert _heads(meter["id"]) == [], "ABSENT again — and no zero row was invented"

        again = usage_service.recompute_account_assets(account["id"], actor=marcus)
        assert again["withdrawn"] == 0, "rule 6: a second withdrawal is not a second write"

        payload = asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))
        assert payload["source"] == "computed_from_reads", "no row stands, so nothing is stored"
        assert payload["series"] == [], "and the reads are gone too, so there is no series"


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · THE LIVE TABLE MATCHES THE MODEL, COLUMN FOR COLUMN
# ══════════════════════════════════════════════════════════════════════════
def test_the_table_matches_the_model(brazos):
    """The pin the `managed = False` disposition owes.

    `apps/metering/models.py` belonged to another lane on 2026-08-27, so the
    model lives in `monthly_usage_asset.py` and migration 0039 builds the table
    with raw DDL. Nothing in Django holds those two together — this does. A
    column added to the DDL and not to the model, or a field added to the model
    and not to the DDL, goes RED here."""
    with tenant_ctx(brazos):
        with connection.cursor() as cursor:
            columns = {
                col.name for col in connection.introspection.get_table_description(cursor, TABLE)
            }
    fields = {f.column for f in AssetMonthlyUsage._meta.fields} | {"superseded_by_id"}
    assert columns == fields, (
        f"the live table and the model disagree — only in the table: "
        f"{sorted(columns - fields)}; only in the model: {sorted(fields - columns)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · HARD RULE 1 — one tenant's meter months are not another's
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc8__the_meter_strip_never_reads_another_tenants_stored_rows(
    brazos, lonestar, marcus
):
    """Every row carries `tenant_id`, the reader filters on it explicitly, and
    the RLS policy migration 0039 installs is the second, independent defence.
    A meter of Brazos is a plain 404 to Lone Star — indistinguishable from an
    id that does not exist (HR-1/G4)."""
    from core import errors

    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5107")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")
        usage_service.recompute_account(account["id"], actor=marcus)
        assert len(_heads(meter["id"])) == 1

    with tenant_ctx(lonestar):
        assert (
            AssetMonthlyUsage.objects.filter(tenant_id=lonestar.id, asset_id=meter["id"]).count()
            == 0
        )
        with pytest.raises(errors.NotFoundError):
            asset_usage.asset_usage_payload(meter["id"], months=12, today=date(2026, 7, 20))


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · THE NARROW PATH MOVES BOTH GRAINS, AND ONLY THE MONTH IT NAMES
# ══════════════════════════════════════════════════════════════════════════
def test_oq_421_tc9__recompute_month_restates_the_meter_grain_for_that_month_only(brazos, marcus):
    """`recompute_month` exists so a read correction can restate ONE month
    without walking an account's whole history. Two things must both hold, and
    the second is the one that would have bitten:

      1. **It moves the meter grain too.** Otherwise a corrected July leaves the
         account saying 700 and the meter saying 684 — exactly the disagreement
         the decision log's constraint exists to prevent, on the only path a
         correction actually takes.
      2. **It moves NOTHING ELSE.** The fan-out's withdrawal sweep asks "which
         heads did I not see?", so an unscoped fan-out inside a scoped call
         would withdraw every OTHER month of that meter — May's 412 kWh would
         silently become ABSENT while the caller was told "restated".
    """
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-5108")
        may = _read(
            brazos, account["id"], meter["id"], day=date(2026, 5, 9), consumption="412.000000"
        )
        july = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000"
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        assert [row.quantity for row in _heads(meter["id"])] == [
            Decimal("412.000000"),
            Decimal("684.000000"),
        ]

        # A late correction to JULY only.
        correction = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 4), consumption="700.000000"
        )
        metering_models.MeterRead.objects.filter(pk=july.pk).update(
            superseded_by_id=correction.id, superseded_at=datetime.now(timezone.utc)
        )
        service_id = (
            metering_models.MonthlyUsage.objects.filter(
                account_id=account["id"], superseded_by_id__isnull=True
            )
            .first()
            .service_id
        )

        usage_service.recompute_month(account["id"], service_id, date(2026, 7, 1), actor=marcus)

        by_month = {row.period_month: row.quantity for row in _heads(meter["id"])}
        # 1 — July moved with the account.
        assert by_month[date(2026, 7, 1)] == Decimal("700.000000")
        account_july = metering_models.MonthlyUsage.objects.get(
            account_id=account["id"],
            period_month=date(2026, 7, 1),
            superseded_by_id__isnull=True,
            superseded_at__isnull=True,
        )
        assert account_july.quantity == Decimal("700.000000")
        # 2 — and May did NOT get withdrawn by the scoped call.
        assert by_month.get(date(2026, 5, 1)) == Decimal(
            "412.000000"
        ), "the scoped fan-out withdrew a month it was never asked about"
        assert may.id is not None  # the May read is untouched history
