# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-040 · US-CWP-041 · US-CWP-043 (EP-CWP-08). Screens CWP-033 ·
#           CWP-034 · CWP-037
# Change:   CR-068 wave H (2026-09-04)
# Rules:    EP-CWP-08 §4 (the fixture's own figures, verbatim) · J36 handoff ·
#           J39 handoff · BR-MET-106 (an unread month is ABSENT, never 0) ·
#           BR-MET-028 (an estimate carries consumption, not a dial figure) ·
#           CLAUDE.md hard rule 3 (every quantity with its unit)
# Tests:    06-backend/tests/test_us_cwp_040_usage.py ·
#           06-backend/tests/test_us_cwp_041_readings.py ·
#           06-backend/tests/test_us_cwp_043_equipment.py
#           (this file is imported by all three; G95 reads the paths, and a
#           bare filename is a citation it cannot resolve — which reads exactly
#           like a citation to a test nobody wrote)
# Impacts:  nothing in the product — this file is fixture only
# ───────────────────────────────────────────────────────
"""Maria's meter, her twelve months, her cart and her backflow device.

⚠ **A SEPARATE FILE FROM `test_us_cwp_helpers.py`, DELIBERATELY.** That one is
shared by every portal story and eight lanes append to it; this is three
stories' fixture and nobody else's, so law 11's shared-file hazard does not
apply to it at all.

⚠ **THE READS ARE WRITTEN THROUGH THE ORM AND THE MONTHS THROUGH THE REAL
WRITER.** Same posture `test_br_met_106_monthly_usage.py` records: building each
reading through the five-step import wizard would make the FIXTURE the thing
under test. But `monthly_usage_service.recompute_account` IS called, because
the stored month is what these screens read and a test that wrote
`MonthlyUsage` rows by hand would prove nothing about the read the product uses.

**Every figure here is `EP-CWP-08` §4's own**, so a number a test asserts and a
number the story states can never come from two places.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from apps.assets import services as asset_services
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.metering import monthly_usage_service, services as metering_services
from core.tenancy import tenant_context

from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account

#: `EP-CWP-08` §4 and `J36`'s handoff. The meter on the wall at `1408 Elm St · A`.
WATER_SERIAL = "88-40219"
CART_SERIAL = "C-11840"
BACKFLOW_SERIAL = "BF-2210"

#: `US-CWP-040` §4 — lowest month `3,050 gal`, highest `4,820 gal`, this year
#: `48,120 gal`. Twelve months, oldest first, ending 31 Aug 2026.
#: ⚠ **THEY SUM TO `48,120` AND THE TEST ASSERTS IT** — a fixture whose figures
#: do not reproduce the story's own totals is a fixture that proves the wrong
#: screen.
MONTHLY_GALLONS: tuple[int, ...] = (
    3050, 3410, 3760, 4090, 4820, 4300, 4170, 3900, 4300, 4090, 3410, 4820,
)
YEAR_TOTAL = 48120
LOWEST = 3050
HIGHEST = 4820

#: `US-CWP-041` §4 — the four rows the story names, and the correction.
ESTIMATED_DIAL = Decimal("144600")
CORRECTED_DIAL = Decimal("144130")
CORRECTED_ON = date(2026, 7, 3)


def _month_start(index: int) -> date:
    """The first of the month `index` months back from September 2026."""
    total = (2026 * 12 + 8) - index  # September 2026 is month 9 → index 0 = Sep
    return date(total // 12, total % 12 + 1, 1)


def elm_unit_with_services(tenant, actor, *, codes=("water", "sewer", "trash")):
    """Maria's account, with a service point for each code she is billed for.

    The wave-C fixture gives Elm Unit A **water only**; sewer and trash are what
    make `BR-CWP-073` testable at all — one `share` basis and one `capacity`
    one — so they are added through metering's own door.
    """
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        # ⚠ **THE PREMISES DECLARES THE SERVICE FIRST OR THE PRODUCT REFUSES**
        # (`BR-MET-119`, the premises → units → meters chain). `seed_street`
        # gives `1408 Elm St` water only, so a fixture that went straight to
        # `ensure_service_point("sewer")` is refused with
        # `metering.service_not_at_premises` — correctly, by the rule. The
        # premises is updated through metering's own door first, exactly as
        # `portal.sample_data._put_on_plan` does it.
        unit = (
            metering_models.Unit.objects.filter(pk=account.unit_id)
            .select_related("premises")
            .first()
        )
        declared = list(unit.premises.services_available or [])
        missing = [code for code in codes if code not in declared]
        if missing:
            metering_services.update_premises(
                actor, unit.premises_id, {"services_available": declared + missing}
            )
        for code in codes:
            metering_services.ensure_service_point(account.unit_id, code)
        # ⚠ **THE AGREEMENT IS WHAT PUTS A SERVICE ON THE SCREEN, NOT THE
        # SERVICE POINT.** `customers_seam.services_held` reads
        # `service_agreements` — the account's own inheritance of its unit,
        # written by `_open_service_agreements` when the account is OPENED. The
        # wave-C fixture opens Maria's account when the unit carries water
        # only, so the points added above have no agreement and `CWP-033` would
        # list one service where the customer is billed for three. History
        # setup, written through the ORM for the same reason the reads are.
        # ⚠ **SCOPED TO THE CODES THE CALLER ASKED FOR.** The wave-C fixture
        # already leaves a WATER service point on this unit, so an unscoped
        # loop would give a *trash-only* account a water agreement too — and
        # `US-CWP-040` TC-5 is precisely the account that has no measured
        # service at all.
        points = metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id,
            unit_id=account.unit_id,
            deleted_at__isnull=True,
            service__code__in=list(codes),
        )
        held = set(
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=tenant.id, account=account, ended_on__isnull=True
            ).values_list("service_point_id", flat=True)
        )
        for point in points:
            if point.id in held:
                continue
            customers_models.ServiceAgreement.objects.create(
                tenant_id=tenant.id,
                account=account,
                service_point_id=point.id,
                started_on=account.opened_at or date(2021, 3, 4),
            )
        # ⚠ **AND THE ONES THE CALLER DID NOT ASK FOR ARE ENDED, NOT LEFT.**
        # The wave-C fixture opens Maria's account on WATER, so a caller asking
        # for `codes=("trash",)` would still get a water agreement it never
        # requested — and `US-CWP-040` TC-5 is exactly the account that has NO
        # measured service. `ended_on` is what a real move off water writes, and
        # `services_held` filters on it (*your services*, present tense).
        wanted = set(
            metering_models.ServicePoint.objects.filter(
                tenant_id=tenant.id,
                unit_id=account.unit_id,
                deleted_at__isnull=True,
                service__code__in=list(codes),
            ).values_list("id", flat=True)
        )
        customers_models.ServiceAgreement.objects.filter(
            tenant_id=tenant.id, account=account, ended_on__isnull=True
        ).exclude(service_point_id__in=wanted).update(ended_on=date(2026, 1, 1))
    return account


def a_water_meter(tenant, actor, unit_id, *, serial=WATER_SERIAL, asset_no="M-88402"):
    """The meter a customer can walk outside and read (`US-CWP-043` §4)."""
    with tenant_context(tenant.id):
        return asset_services.create_asset(
            actor,
            {
                "type": "meter",
                "asset_no": asset_no,
                "serial_no": serial,
                "service": "water",
                "unit": "gal",
                "read_method": "walk_by",
                "multiplier": "1",
                "unit_id": str(unit_id),
                "install_date": "2021-03-04",
                "location_note": "Front boundary box",
                "status": "active",
            },
        )


def a_refuse_cart(tenant, actor, unit_id, *, serial=CART_SERIAL, asset_no="C-11840"):
    """⚠ **A CART IS EQUIPMENT** (`BR-CWP-073`) — it is what an unmeasured
    service is billed on, and it has **no last read**, which is `US-CWP-043`
    TC-2's whole point."""
    with tenant_context(tenant.id):
        return asset_services.create_asset(
            actor,
            {
                "type": "container_cart",
                "asset_no": asset_no,
                "serial_no": serial,
                "service": "trash",
                "unit_id": str(unit_id),
                "install_date": "2024-01-15",
                "location_note": "Rear alley",
                "status": "active",
                "size_class": "CART-96",
            },
        )


def a_backflow_device(tenant, actor, unit_id, *, serial=BACKFLOW_SERIAL, asset_no="BF-2210"):
    """`US-CWP-043` TC-3 — its status comes from the EXISTING maintenance
    cadence (`BR-AST-007`), never from a word typed on the row."""
    with tenant_context(tenant.id):
        return asset_services.create_asset(
            actor,
            {
                "type": "backflow",
                "asset_no": asset_no,
                "serial_no": serial,
                "service": "water",
                "unit_id": str(unit_id),
                "install_date": "2021-03-04",
                "location_note": "Front boundary box",
                "status": "active",
                "last_test_date": "2025-11-14",
                "test_interval_months": 12,
            },
        )


def a_read(
    tenant,
    account,
    asset_id,
    *,
    day: date,
    current: Any,
    consumption: Any,
    unit: str = "gal",
    read_method: str | None = "walk_by",
    source: str = "manual",
    source_detail: str | None = "walk_by",
    status: str = "ok",
    prior: Any = None,
    read_id: Any = None,
):
    """One committed lineage head — history setup, written through the ORM.

    ⚠ **`current` IS `None` ON AN ESTIMATE** (`BR-MET-028`: consumption only,
    because nobody read a dial). Callers that want the story's `144,600` pass it
    explicitly, which is the case where a clerk recorded an estimated dial.

    ⚠ **`read_id` EXISTS BECAUSE OF `uq_meter_reads_head`, AND THE CONSTRAINT
    IS RIGHT.** `(tenant, asset, read_at, channel)` is unique **over lineage
    HEADS** — `condition=Q(superseded_by_id__isnull=True)` — so two live rows
    for one register on one date is refused by the database, which is exactly
    what B2 r8 intends. A correction is a NEW row at the SAME `read_at`, so the
    old row must stop being a head BEFORE the new one is inserted, and that
    means its replacement's id has to exist first. Pre-allocating it here is not
    a trick around the rule: it is the only order in which the rule and the
    correction can both be true, and a fixture that used two different dates
    would have proved the screen against a shape the product cannot produce.
    """
    with tenant_context(tenant.id):
        return metering_models.MeterRead.objects.create(
            **({"id": read_id} if read_id is not None else {}),
            tenant_id=tenant.id,
            account_id=account.pk,
            asset_id=asset_id,
            read_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
            channel="total",
            period_start=date(day.year, day.month, 1),
            period_end=day,
            prior_value=None if prior is None else Decimal(str(prior)),
            current_value=None if current is None else Decimal(str(current)),
            consumption=None if consumption is None else Decimal(str(consumption)),
            unit=unit,
            source=source,
            source_detail=source_detail,
            read_method=read_method,
            status=status,
            lifecycle="committed",
        )


def twelve_months_of_water(tenant, actor, account, asset_id):
    """`US-CWP-040` §4's twelve months, oldest first, ending 31 Aug 2026.

    Returns the created reads. The dial climbs by each month's consumption, so
    a reading and its used-since agree the way a real register does.
    """
    reads = []
    dial = Decimal("104920")  # 153,040 − 48,120: the dial a year before
    with tenant_context(tenant.id):
        for index, gallons in enumerate(MONTHLY_GALLONS):
            month = _month_start(len(MONTHLY_GALLONS) - index)
            last_day = _month_start(len(MONTHLY_GALLONS) - index - 1)
            taken = date.fromordinal(last_day.toordinal() - 1)
            prior = dial
            dial = dial + Decimal(gallons)
            reads.append(
                a_read(
                    tenant, account, asset_id,
                    day=taken, current=dial, consumption=gallons, prior=prior,
                )
            )
    return reads


def state_the_months(tenant, actor, account):
    """Run the REAL writer, so the screens read what the product stores.

    `monthly_usage_service.recompute_account` is what `BR-MET-106` names; a test
    that inserted `MonthlyUsage` rows itself would assert against its own
    arithmetic instead of the product's.
    """
    with tenant_context(tenant.id):
        return monthly_usage_service.recompute_account(account.pk, actor=actor)
