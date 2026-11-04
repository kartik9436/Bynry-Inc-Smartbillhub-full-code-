# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-RAT-9842 (the sample-utility seeders created rate schedules
#           naming no base code, so under PO ruling 2026-10-06 every newly set-up
#           sample utility billed a $0.00 base)
# Rules:    BR-RAT-1025 / BR-RAT-088 — base = plan -> rate schedule -> the base
#           code the schedule NAMES; names none -> $0.00 with the warning
#           (decision log 2026-10-06 "PO RULING — A RATE SCHEDULE THAT NAMES NO
#           BASE CODE BILLS A $0.00 BASE …")
# Tests:    this file, for apps/rating/sample_data.py (schedule_base_codes,
#           backbone_commercial_schedule_name, seed_sample_records)
# ───────────────────────────────────────────────────────
"""A newly set-up sample utility names a base code on every rate schedule.

Before this fix, a freshly seeded demo utility (Brazos Bend, measured on
PostgreSQL 16) had **8 of 8** live schedules naming no base code, and **50 of
71** accounts lost a priced base — about **$3,307.75 a month** — the day the PO
ruled that an unnamed schedule bills `$0.00`.

RED PROVED FIRST (with `seed_sample_records` restored to create every schedule
under `seeding_schedules_without_a_named_base()` and no `base_charge_code`):

    AssertionError: live sample schedules that name no base code — every account
    on them bills a $0.00 base: ['Sample — Commercial water (flat)', …]
"""

from __future__ import annotations

import pytest

from apps.rating import sample_data

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


#: Which base code each sample plan's schedule must name, per service — the
#: code the retired class-narrowed pool used to pick for that plan's class, so
#: every sample bill keeps its figure (water $8.00 / $15.00, electric $12.00 /
#: $48.00 / $180.00, sewer and trash their own one code).
EXPECTED = {
    (sample_data.PLAN_RESIDENTIAL, "water"): "BASE-W",
    (sample_data.PLAN_COMMERCIAL, "water"): "BASE-W-COM",
    (sample_data.PLAN_INDUSTRIAL, "water"): "BASE-W-COM",
    (sample_data.PLAN_RESIDENTIAL, "electric"): "BASE-E",
    (sample_data.PLAN_COMMERCIAL, "electric"): "BASE-E-COM",
    (sample_data.PLAN_INDUSTRIAL, "electric"): "BASE-E-IND",
    (sample_data.PLAN_RESIDENTIAL, "sewer"): "BASE-S",
    (sample_data.PLAN_COMMERCIAL, "sewer"): "BASE-S",
    (sample_data.PLAN_RESIDENTIAL, "trash"): "BASE-T",
    (sample_data.PLAN_COMMERCIAL, "trash"): "BASE-T",
}


def test_every_schedule_a_new_sample_utility_gets_names_its_base_code(
    growth_plan, audit_rows, settings
):
    from apps.customers import models as customer_models
    from apps.metering import selectors as metering_selectors
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors

    settings.JOBS_EAGER = True  # the plant runs inline, as on a real signup
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            subdomain="def9842",
            name="DEF-RAT-9842 sample",
            services=["electric", "water", "sewer", "trash"],
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@def9842.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    with tenant_ctx(tenant):
        today = rating_selectors.seams.tenant_today()
        # 1 · every live schedule names a code.
        unnamed = []
        for tariff in rating_models.Tariff.objects.filter(deleted_at__isnull=True):
            version = rating_selectors.in_force_version(tariff, today)
            if version is not None and version.base_charge_code_id is None:
                unnamed.append(tariff.name)
        assert not unnamed, (
            "live sample schedules that name no base code — every account on them "
            f"bills a $0.00 base: {sorted(unnamed)}"
        )

        # 2 · each sample plan's schedule names ITS class's code.
        found = {}
        for link in rating_models.PlanRateSchedule.objects.filter(
            rate_plan__code__in=[plan for plan, _ in EXPECTED]
        ).select_related("rate_plan", "service", "tariff"):
            version = rating_selectors.in_force_version(link.tariff, today)
            if version is None or version.base_charge_code_id is None:
                continue
            found[(link.rate_plan.code, link.service.code)] = version.base_charge_code.code
        for key, code in EXPECTED.items():
            if key in found:
                assert found[key] == code, (key, found[key])
        assert (sample_data.PLAN_RESIDENTIAL, "electric") in found
        assert (sample_data.PLAN_COMMERCIAL, "electric") in found
        # The residential and commercial electric schedules are two now.
        assert sample_data.backbone_commercial_schedule_name("electric") in {
            t.name for t in rating_models.Tariff.objects.all()
        }

        # 3 · and no sample account's base is the $0.00 of a schedule naming none.
        bills_zero_because_unnamed = []
        for account in customer_models.Account.objects.filter(
            tenant_id=tenant.id
        ).select_related("account_type"):
            if not account.unit_id:
                continue
            assignment = rating_models.UnitPlanAssignment.objects.filter(
                unit_id=account.unit_id, assigned_to__isnull=True
            ).first()
            if assignment is None:
                continue
            for link in rating_models.PlanRateSchedule.objects.filter(
                rate_plan=assignment.rate_plan
            ).select_related("service", "tariff"):
                version = rating_selectors.in_force_version(link.tariff, today)
                if version is None:
                    continue
                if version.base_charge_code_id is None:
                    bills_zero_because_unnamed.append((account.account_no, link.service.code))
                    continue
                answer = rating_selectors.base_charge_from_charge_code(
                    link.service.code,
                    customer_class=account.account_type.code if account.account_type_id else None,
                    size_class=metering_selectors.connection_size_for(
                        account.unit_id, link.service.code
                    ),
                    named_code=version.base_charge_code.code,
                )
                assert answer.get("code") in (None, version.base_charge_code.code)
        assert not bills_zero_because_unnamed, bills_zero_because_unnamed


# ═══════════════════════════════════════════════════════════════════════════
# THE STATEMENT THE PO SIGNED ON 2026-10-06 ("S9–S13 approve", S13)
# ═══════════════════════════════════════════════════════════════════════════
#: The base each sample plan's class paid BEFORE the ruling (the class-narrowed
#: pool, CR-171 §49's table) — which the named code must now give, unchanged.
BASES_AS_BEFORE = {
    (sample_data.PLAN_RESIDENTIAL, "water", "residential"): "BASE-W",
    (sample_data.PLAN_COMMERCIAL, "water", "commercial"): "BASE-W-COM",
    (sample_data.PLAN_RESIDENTIAL, "electric", "residential"): "BASE-E",
    (sample_data.PLAN_COMMERCIAL, "electric", "commercial"): "BASE-E-COM",
    (sample_data.PLAN_INDUSTRIAL, "electric", "industrial"): "BASE-E-IND",
}


def _the_pool_before_the_ruling(service, klass):
    """The code the RETIRED class-narrowed pool picked for this class (the
    "before" of the statement): the base codes of the service that reach the
    class, narrowed to the ones scoped to it BY NAME when there are any. The
    test asserts it is ONE code and the code the schedule now names."""
    from apps.rating import models as rating_models

    reach = [
        charge
        for charge in rating_models.Charge.objects.filter(
            service__code=service, is_base=True, deleted_at__isnull=True
        )
        if not charge.applies_to_customer_classes or klass in charge.applies_to_customer_classes
    ]
    scoped = [c for c in reach if klass in (c.applies_to_customer_classes or [])]
    return sorted({charge.code for charge in (scoped or reach)})


def test_the_statement_the_po_signed_on_2026_10_06(growth_plan, audit_rows, settings):
    """**SIGNED 2026-10-06 (S13)** — review-ledger AMENDMENT row *"SIGN-OFF
    RECORDED (S13 of S9–S13)"* for `DEF-RAT-9842`; decision log *"S9–S13
    SIGNED"*.

    Shown to the PO, verbatim: *"A newly set-up sample utility names a base
    code on every rate schedule, so its bills match what they were before (100
    sample bills: $45,343.83 either way); nothing changes for utilities already
    set up."* PO, verbatim: *"S9–S13 approve"*.

    * *"names a base code on every rate schedule"* — every live schedule of a
      freshly provisioned sample utility names one;
    * *"its bills match what they were before"* — for EVERY sample account on
      a sample plan, the code its schedule names is the one code the retired
      class-narrowed pool picked for its class (`BASE-W` / `BASE-W-COM`,
      `BASE-E` / `BASE-E-COM` / `BASE-E-IND`), so at the account's own size
      the base is the same figure to the cent (a sample home's water `$8.00`
      among them);
    * *"nothing changes for utilities already set up"* — a schedule that
      already exists naming NO code is left naming none when the sample is
      replayed over it (no migration, no replay names a code on it).

    ⚠ **THE `$45,343.83` TOTAL IS NOT ASSERTED HERE**, and that is recorded in
    the ledger row rather than hidden: it was measured ONCE by lane RAT-9842 on
    a fresh demo utility, by no recorded procedure, and three loads tried by
    the sign-off lane on this checkout (signup sample; demo seed + sample load,
    with and without eager jobs) gave 100 bills of `$60,315.82`, `$47,237.11`
    and `$51,420.56` — the total depends on HOW the demo is loaded. The
    per-account equality above is what makes it "either way", and it is
    deterministic. (The per-class figures on the PENDING row — `$15.00`,
    `$48.00`, `$180.00` — are size-priced in the sample: commercial water reads
    `$45.00`/`$63.75` and industrial electric `$1,710.00` at the sizes the
    sample records, the same before and after.)
    """
    from decimal import Decimal

    from apps.customers import models as customer_models
    from apps.metering import selectors as metering_selectors
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors

    from tests.test_cr040_two_cycles import _real_admin

    settings.JOBS_EAGER = True
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            subdomain="signed9842",
            name="S13 sample",
            services=["electric", "water", "sewer", "trash"],
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@signed9842.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    with tenant_ctx(tenant):
        today = rating_selectors.seams.tenant_today()
        # ── "names a base code on every rate schedule" ──
        live = [
            rating_selectors.in_force_version(tariff, today)
            for tariff in rating_models.Tariff.objects.filter(deleted_at__isnull=True)
        ]
        live = [version for version in live if version is not None]
        assert live and all(version.base_charge_code_id for version in live)

        # ── "so its bills match what they were before" ──
        # Every sample account on a sample plan, at its own recorded size, the
        # way the bill asks (`gather` → the schedule's named code → its price).
        found: dict[tuple[str, str, str], set[str]] = {}
        priced: set = set()
        for account in customer_models.Account.objects.filter(
            tenant_id=tenant.id, unit_id__isnull=False, account_type__isnull=False
        ).select_related("account_type"):
            assignment = rating_models.UnitPlanAssignment.objects.filter(
                unit_id=account.unit_id, assigned_to__isnull=True
            ).select_related("rate_plan").first()
            if assignment is None:
                continue
            for link in rating_models.PlanRateSchedule.objects.filter(
                rate_plan=assignment.rate_plan, service__code__in=("water", "electric")
            ).select_related("service", "tariff"):
                key = (assignment.rate_plan.code, link.service.code, account.account_type.code)
                if key not in BASES_AS_BEFORE:
                    continue
                named = rating_selectors.in_force_version(link.tariff, today).base_charge_code.code
                answer = rating_selectors.base_charge_from_charge_code(
                    link.service.code,
                    customer_class=account.account_type.code,
                    size_class=metering_selectors.connection_size_for(
                        account.unit_id, link.service.code
                    ),
                    named_code=named,
                )
                # The pool's pick at the same size is the same code, so the same
                # price: the bill is what it was before, to the cent.
                pool = _the_pool_before_the_ruling(link.service.code, account.account_type.code)
                assert pool == [named], (key, pool, named)
                before = rating_selectors.base_charge_from_charge_code(
                    link.service.code,
                    customer_class=account.account_type.code,
                    size_class=metering_selectors.connection_size_for(
                        account.unit_id, link.service.code
                    ),
                    named_code=pool[0],
                )
                assert before["amount"] == answer["amount"], key
                found.setdefault(key, set()).add(named)
                if key == (sample_data.PLAN_RESIDENTIAL, "water", "residential"):
                    priced.add(answer["amount"])
        assert found == {key: {code} for key, code in BASES_AS_BEFORE.items()}
        # The figure a sample home has always paid for water is still there.
        assert Decimal("8.00") in {Decimal(a) for a in priced if a is not None}

        # ── "nothing changes for utilities already set up" ──
        older = rating_selectors.in_force_version(
            rating_models.PlanRateSchedule.objects.select_related("tariff")
            .get(rate_plan__code=sample_data.PLAN_RESIDENTIAL, service__code="water")
            .tariff,
            today,
        )
        rating_models.TariffVersion.objects.filter(pk=older.pk).update(base_charge_code_id=None)
        sample_data.seed_sample_records(_real_admin(tenant))
        older.refresh_from_db()
        assert older.base_charge_code_id is None, "a schedule already set up is never touched"
