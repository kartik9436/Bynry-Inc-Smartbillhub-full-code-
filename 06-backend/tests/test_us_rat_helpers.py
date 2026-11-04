# ── Trace ──────────────────────────────────────────────
# Component: shared fixtures/builders for the US-RAT W1 rating story tests
#            (imported by tests/test_us_rat_*.py via `from ... import *`).
#            Rides the tenancy W0 helper plumbing: sqlite-safe tenant context,
#            the captured BE-03 audit sink, and the DRF view caller. Live-RLS
#            behavior stays the G5 isolation suite's job (sqlite cannot enforce
#            RLS) — every isolation TC here is the APP-FILTER half plus an
#            @pytest.mark.isolation placeholder for the Postgres half.
# ───────────────────────────────────────────────────────
"""Shared plumbing for the Plans & Rates story tests.

Seed vocabulary follows the epics' §4 signed test data (Brazos Bend Utilities ·
Lone Star Ridge Water Co-op · Dana Whitfield · Marcus Vega · J. Okafor).
Actors carry a REAL identity user id: rate_change_log/rate_change_batches hold
FKs to users, so a made-up uuid would be a foreign-key violation, not a test.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from core import jobs as core_jobs
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared W0 fixtures
from tests.test_us_ten_helpers import (  # noqa: F401 — re-exported to the story modules
    api_call,
    audit_actions,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    seeding_ctx,
    tenant_ctx,
)

TODAY = date(2026, 8, 9)  # the packet's "today" (CLAUDE.md currentDate)

#: BR-RAT-088's base amount per service, for the fixture's declared base codes
#: (`DEF-2965`). **Every figure is cited and none is invented.**
#:
#: `core.sample_fixture` is the home of the signed numbers — `[W] §1 "Base/mo …
#: Water $8 · Electric $12"` — and `apps/rating/sample_data.BASE_CHARGE_CODES`
#: and `seed_demo` read the same two constants, so a fixture base and a seeded
#: base can never drift apart.
#:
#: ⚠ **A SERVICE WITH NO SIGNED BASE FIGURE GETS `"0"`, AND THAT IS A PRICE
#: RATHER THAN A BLANK.** It is `BASE-S`'s own recorded reasoning, quoted:
#: *"`0` IS A PRICE, NOT AN ABSENCE (PO ruling 2026-08-19, 'print $0.00')"*,
#: and `core.sample_fixture.TRASH_BASE` states the same thing for trash after
#: `OQ-317`. The distinction is load-bearing: CR-013 part 1 makes a BLANK base
#: mean *this size is not served* and `gather._base_charge_for` stops the bill
#: on it (`DEF-277`), while a stored zero prints `$0.00`. So a service the
#: workbook names no base column for is declared at zero rather than left
#: undeclared — which is what the utility itself would have to do to activate a
#: schedule for it.
BASE_CHARGE_AMOUNTS = {
    "water": fixture.WATER_BASE,      # [W] §1 "Base/mo … Water $8"
    "electric": fixture.ELECTRIC_BASE,  # [W] §1 "Base/mo … Electric $12"
    "trash": fixture.TRASH_BASE,      # OQ-317 option A, PO 2026-08-27 — "0"
    "sewer": "0",                     # apps/rating/sample_data.py BASE-S
}
UNSIGNED_SERVICE_BASE = "0"


def _base_charge_payload(service_code):
    """`(code, name, amount)` for one service's base charge code.

    The CODE follows the seed's own spelling — `BASE-W`, `BASE-E`, `BASE-S`,
    `BASE-T` for the four services that have one there, and `BASE-<SERVICE>`
    otherwise, which is the readable form
    `apps/rating/management/commands/migrate_base_to_charge_codes.py` already
    generates (*"a service reads as `BASE-WATER`, which is what a utility would
    type"*). Codes are not matched by NAME anywhere in the engine — `BR-RAT-088`
    warns that name-matching two base codes fails silently — so the spelling is
    for a human reading the fixture, never for a lookup.
    """
    seeded = {"water": "BASE-W", "electric": "BASE-E", "sewer": "BASE-S", "trash": "BASE-T"}
    code = seeded.get(service_code) or f"BASE-{service_code.upper().replace('_', '-')}"
    amount = BASE_CHARGE_AMOUNTS.get(service_code, UNSIGNED_SERVICE_BASE)
    return code, f"{service_code.replace('_', ' ').title()} base service", amount



class FakeJobStore:
    """BE-07 duck-typed store. The real one lands with the /jobs table lane;
    until then a 202 would have no record behind it, so tests supply one
    rather than letting the kernel lie (core/jobs.py contract)."""

    def __init__(self):
        self.records: dict[str, dict] = {}

    def save(self, record):
        self.records[record["id"]] = record

    def get(self, job_id):
        return self.records.get(job_id)

    def find_active(self, tenant_id, kind, scope_key):
        for record in self.records.values():
            if (
                record["tenant_id"] == tenant_id
                and record["kind"] == kind
                and record["scope_key"] == scope_key
                and record["status"] in core_jobs.ACTIVE_STATUSES
            ):
                return record
        return None


@pytest.fixture()
def job_store():
    """Save-and-restore: apps.tenancy registers the REAL store at startup
    (BE-07), so handing back None would leave later tests without one."""
    previous = core_jobs._store
    store = FakeJobStore()
    core_jobs.set_job_store(store)
    yield store
    core_jobs.set_job_store(previous)


class RatingEnv:
    """Builders for the epic §4 fixtures — every write goes through the real
    service layer unless the column has no service-layer setter yet."""

    def __init__(self, tenant, owner):
        self.tenant = tenant
        self.owner = owner
        self.admin = SimpleNamespace(id=owner.id, role="system_admin")
        self.clerk = SimpleNamespace(id=owner.id, role="billing_clerk")

    # ── tenant setup ────────────────────────────────────────────────────
    def enable(self, *service_codes):
        from apps.tenancy import services as tenancy_services

        with tenant_ctx(self.tenant):
            for code in service_codes:
                tenancy_services.update_tenant_service(self.admin, code, {"enabled": True})

    def set_billed_uom(self, service_code, uom_code, factor=None):
        """r6.4 UoM-gate columns have no Settings-tab setter yet (US-TEN-008's
        W1 half) — the fixture writes them directly, tenancy owns the table."""
        from apps.tenancy import models as tenancy_models

        with seeding_ctx(self.tenant):  # DEF-2761
            uom, _ = tenancy_models.Uom.objects.get_or_create(
                tenant=self.tenant, code=uom_code, defaults={"name": uom_code}
            )
            row = tenancy_models.TenantService.objects.get(
                tenant=self.tenant, service__code=service_code
            )
            row.billed_uom = uom
            row.conversion_factor = factor
            row.save(update_fields=["billed_uom", "conversion_factor"])

    # ── rating builders (through the service layer) ─────────────────────
    def charge(self, code, name, **overrides):
        from apps.rating import services

        payload = {
            "code": code,
            "name": name,
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": "45.00",
        }
        payload.update(overrides)
        with tenant_ctx(self.tenant):
            return services.create_charge(self.admin, {**(payload), "effective_from": "2000-01-01"})

    def tax(self, name, **overrides):
        from apps.rating import services

        payload = {
            "name": name,
            "jurisdiction": {"name": name, "authority": name, "level": "state"},
            "kind": "percent",
            "rate": "0.0625",
        }
        payload.update(overrides)
        with tenant_ctx(self.tenant):
            return services.create_tax(self.admin, payload)

    # ── BR-RAT-088's base charge code (DEF-2965) ────────────────────────
    def declare_base_charge_code(self, service_code):
        """Declare this service's `is_base` charge code, idempotently.

        ⚠ **WHY A FIXTURE HAS TO DO THIS AT ALL, AND WHY IT IS NOT A NUMBER
        INVENTED TO MAKE A GATE PASS (`DEF-2965`).** `BR-RAT-088` (PO ruling
        2026-08-20) makes the CHARGE CODE the only source of a service's base
        amount, and since the PO ruled R3 + R4 on (`CR-057`, 2026-09-01)
        `_guard_base_charge_code` fires for EVERY tenant where the chain serves
        R4 — so activating a rate schedule for a service with no declared base
        code is REFUSED, by name, at the moment of activation. That refusal is
        the product working: without it the same tenant bills every usage line
        correctly and the total short by the whole base, which §A3 priced at
        `$23,069.50` a month across 1,247 connections.

        **So a fixture that activates a schedule is a fixture standing in for a
        utility that has finished configuring itself, and it must declare the
        code the same way that utility would** — on the Charge codes screen,
        through `create_charge`, with `is_base` set. Nothing here weakens the
        gate; `test_def2923_base_code_gate_follows_the_switch.py` still proves
        it fires, and `test_br_rat_088_base_charge_gate.py` still proves both
        halves of its condition.

        **THE FIGURES ARE THE REPO'S OWN SIGNED ONES** — `core.sample_fixture`,
        the same module `apps/rating/sample_data.BASE_CHARGE_CODES` and
        `seed_demo` both read: `[W] §1 "Base/mo … Water $8 · Electric $12"`.
        See `BASE_CHARGE_AMOUNTS` below for the service with no signed figure.
        """
        from apps.rating import models, services

        code, name, amount = _base_charge_payload(service_code)
        with tenant_ctx(self.tenant):
            existing = models.Charge.objects.filter(
                tenant=self.tenant, service__code=service_code, is_base=True,
                deleted_at__isnull=True,
            ).first()
            if existing is not None:
                return existing
            row = services.create_charge(
                self.admin,
                {
                    "code": code,
                    "name": name,
                    "service": service_code,
                    # A base is charged because a CONNECTION EXISTS
                    # (BR-RAT-080), every cycle — `recurring`, exactly as
                    # `apps/rating/sample_data.py` states it.
                    "charge_type": "recurring",
                    "amount_rule": "flat",
                    "amount": amount,
                    "is_base": True,
                 "effective_from": "2000-01-01"},
            )
            return models.Charge.objects.get(pk=row["id"])

    def _base_codes_for_activation(self, service):
        """Every service this tenant BILLS gets one, or none of them do.

        ⚠ **DECLARING ONE SERVICE'S BASE CODE ARMS THE GATE FOR THE OTHERS, AND
        THAT IS `DEF-528` — A CRITICAL DEFECT THIS REPO HAS ALREADY PAID FOR
        ONCE.** `_guard_base_charge_code` self-activates on the tenant's first
        `is_base` row, so seeding `BASE-W` alone *"did not add half a feature —
        it armed a refusal that killed `seed_demo` at the first electric
        schedule"* and a fresh deployment could not be seeded at all. The rule
        written from it is quoted here rather than re-derived: **"a base charge
        code is seeded for EVERY service this seed prices, or for none."**

        So this declares one for every ENABLED service on the tenant, not only
        for the service being activated. The enabled set is the tenant's own
        `tenant_services` rows — what the utility says it bills — never a list
        this file keeps.
        """
        from apps.tenancy import models as tenancy_models

        with tenant_ctx(self.tenant):
            enabled = sorted(
                row.service.code
                for row in tenancy_models.TenantService.objects.select_related(
                    "service"
                ).filter(tenant=self.tenant, enabled=True)
            )
        # The service being activated is included even if `tenant_services`
        # does not have it enabled: a schedule is being built for it, so it is
        # a service this fixture prices, and the gate will ask about it.
        for code in dict.fromkeys([*enabled, service]):
            self.declare_base_charge_code(code)

    def flat_schedule(self, name, service, unit_price="2.90", declare_base=True, **overrides):
        from apps.rating import services

        payload = {
            "name": name,
            "service": service,
            "model": "flat",
            "uom": "kgal",
            "effective_from": "2026-08-01",
            "structure": {"unit_price": unit_price},
        }
        payload.update(overrides)
        # BR-RAT-088 — an ACTIVE version needs the base code; a DRAFT does not,
        # and `create_rate_schedule` only calls the guard when `effective_from`
        # is stated. Mirroring that condition here keeps the fixture from
        # declaring codes a draft-only test never needed.
        if declare_base and payload.get("effective_from"):
            self._base_codes_for_activation(service)
        with tenant_ctx(self.tenant):
            return services.create_rate_schedule(self.admin, payload)

    def tiered_schedule(self, name, service, tiers, declare_base=True, **overrides):
        from apps.rating import services

        payload = {
            "name": name,
            "service": service,
            "model": "tiered",
            "uom": "kgal",
            "effective_from": "2026-08-01",
            "structure": {"tiers": tiers},
        }
        payload.update(overrides)
        if declare_base and payload.get("effective_from"):
            self._base_codes_for_activation(service)
        with tenant_ctx(self.tenant):
            return services.create_rate_schedule(self.admin, payload)

    def plan(self, name, code, services_payload, publish=False, **overrides):
        """A plan, optionally published.

        ⚠ **A PUBLISHED PLAN CARRIES A START DATE SINCE 2026-08-28** —
        BR-RAT-890, the PO ruling that closes DEF-494: `publish_plan` refuses a
        plan that does not say when it starts. So `publish=True` states one, the
        same `2026-08-01` the two schedule helpers above already use, and a
        caller that means something else passes `effective_from` itself. A
        DRAFT is left undated, because a draft with no date is what a draft is
        (BR-RAT-031) — this default is about publishing, not about creating.
        """
        from apps.rating import services

        payload = {"name": name, "code": code, "services": services_payload}
        if publish:
            payload.setdefault("effective_from", "2026-08-01")
        payload.update(overrides)
        with tenant_ctx(self.tenant):
            plan = services.create_plan(self.admin, payload)
            if publish:
                plan = services.publish_plan(self.admin, plan["id"])
        return plan

    # ── metering fixtures for the account counts (cross-module rows) ────
    def unit(self, label="Unit A"):
        from apps.metering import models as metering_models

        with seeding_ctx(self.tenant):  # DEF-2761
            premises, _ = metering_models.Premises.objects.get_or_create(
                tenant=self.tenant,
                address_line="1200 Bluebonnet Ln, Katy TX",
                defaults={"name": "Bluebonnet Court"},
            )
            return metering_models.Unit.objects.create(
                tenant=self.tenant, premises=premises, label=label
            )

    def assign(self, plan_id, unit, plan_version=1, assigned_from=None):
        """The customers-seam write (r16 #7) stood in for by the fixture: the
        assignment table is rating-owned but customers-written."""
        from apps.rating import models

        with seeding_ctx(self.tenant):  # DEF-2761
            return models.UnitPlanAssignment.objects.create(
                tenant=self.tenant,
                unit=unit,
                rate_plan_id=plan_id,
                plan_version=plan_version,
                assigned_from=assigned_from or TODAY,
                source="new_connection",
                actor=self.owner,
            )


def _owner_of(tenant):
    from apps.identity.models import User

    with seeding_ctx(tenant):  # DEF-2761 — an unscoped read returns None, not an error
        return User.objects.filter(tenant=tenant).order_by("created_at").first()


def _start_from_an_empty_rating_catalog(tenant):
    """Undo the PLATFORM reference seed for rating's two lists on this tenant.

    Added 2026-08-10 with DEF-016. Until then rating had no
    `seed_reference_list` seam, so provisioning left `charges` and
    `tax_jurisdictions` EMPTY — which is exactly the defect — and every
    US-RAT-008/009 test below was written against that empty start: their §4
    signed catalog re-uses four of the platform fixture's own codes (CONN,
    DISC, LATE, NSF) with the tenant's OWN amounts (§4 CONN is $85.00; the
    platform fixture seeds $45), which is what a real operator's S12 edit looks
    like.

    So this is NOT hiding the new behaviour, it is separating two subjects: the
    platform SEED is asserted in tests/test_reference_data_completeness.py
    against the fixture itself, and these files keep asserting S12/S13 CRUD from
    the empty catalog their §4 data describes. UoMs are deliberately left
    seeded — BR-RAT-038's UoM gate needs them.
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    # DEF-2761: inside the tenant's context. A DELETE is a read first — RLS
    # simply matches no rows without the marker, so this helper "succeeded"
    # while deleting nothing, and the cases that assert an EMPTY catalog then
    # failed on rows it was supposed to have removed. A refusal that looks like
    # a no-op is the quietest shape this defect takes.
    with seeding_ctx(tenant):
        # CR-156-BRC10 — a flat amount is an *All sizes* row now (PROTECT FK).
        rating_models.ChargeCodeAmount.objects.filter(tenant=tenant).delete()
        rating_models.Charge.objects.filter(tenant=tenant).delete()
        # DEF-273 (2026-08-18): provisioning now seeds the PO's five ruled Texas
        # `taxes` rows as well as their jurisdictions, and `Tax.jurisdiction` is
        # PROTECT — so the rates must go first or this helper raises
        # `ProtectedError` and 23 US-RAT-008/009 cases error before they start.
        # Same subject as the paragraph above: the platform seed is asserted in
        # tests/test_def_273_tax_conditions.py and test_reference_data_completeness,
        # and these files keep asserting S12/S13 CRUD from the empty catalog their
        # §4 data describes.
        rating_models.Tax.objects.filter(tenant=tenant).delete()
        rating_models.TaxJurisdiction.objects.filter(tenant=tenant).delete()
        tenancy_models.ReferenceSeedRun.objects.filter(
            tenant=tenant, list_code__in=("charge_codes", "tax_jurisdictions")
        ).delete()


@pytest.fixture()
def env(growth_plan):  # noqa: F811 — growth_plan comes from the W0 helper module
    """Brazos Bend Utilities with Electric + Water enabled (the §4 seed)."""
    tenant, _ = provisioned_tenant(brazosbend_payload())
    _start_from_an_empty_rating_catalog(tenant)
    return RatingEnv(tenant, _owner_of(tenant))


@pytest.fixture()
def other_env(growth_plan):  # noqa: F811
    """Lone Star Ridge Water Co-op — the isolation tenant of every §4 seed."""
    tenant, _ = provisioned_tenant(lonestarridge_payload())
    _start_from_an_empty_rating_catalog(tenant)
    return RatingEnv(tenant, _owner_of(tenant))


RES_WATER_TIERS = [  # US-RAT-005 TC-1 (Res Water · Inclining)
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.20"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "4.80"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.20"},
]
RES_ELECTRIC_TIERS = [  # US-RAT-004 §4 (Res Electric · Tiered)
    {"from_qty": "0", "to_qty": "500", "unit_price": "0.11"},
    {"from_qty": "500", "to_qty": "1000", "unit_price": "0.14"},
    {"from_qty": "1000", "to_qty": None, "unit_price": "0.19"},
]
SUMMER = {
    "label": "Summer",
    "start_month": 6,
    "start_day": 1,
    "end_month": 9,
    "end_day": 30,
}
WINTER = {
    "label": "Winter",
    "start_month": 10,
    "start_day": 1,
    "end_month": 5,
    "end_day": 31,
}


def tou_structure(windows=None, seasons=None):
    """US-RAT-006 TC-1 Option B config (summer on/off-peak + winter all-day).

    Every window STATES its meter register (BR-RAT-067, PO 2026-08-16 closing
    OQ-236). `channel` is a required field on the write path, so a fixture that
    omitted it would exercise the refusal instead of the happy path.
    """
    return {
        "seasons": seasons if seasons is not None else [dict(SUMMER), dict(WINTER)],
        "windows": (
            windows
            if windows is not None
            else [
                {
                    "label": "On-peak",
                    "season": "Summer",
                    "day_type": "weekday",
                    "start_time": "14:00",
                    "end_time": "20:00",
                    "unit_price": "0.22",
                    "channel": "tou_on",
                },
                {
                    "label": "Off-peak",
                    "season": "Summer",
                    "day_type": "weekday",
                    "start_time": "20:00",
                    "end_time": "14:00",
                    "unit_price": "0.09",
                    "channel": "tou_off",
                },
                {
                    "label": "All day",
                    "season": "Winter",
                    "day_type": "weekday",
                    "start_time": "00:00",
                    "end_time": "00:00",
                    "unit_price": "0.13",
                    "channel": "tou_off",
                },
            ]
        ),
    }


def money(value):
    return Decimal(str(value))
