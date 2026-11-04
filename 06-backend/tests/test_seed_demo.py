# ── Trace ──────────────────────────────────────────────
# Component: `manage.py seed_demo` — the demo/staging post-migrate seeder
#            (apps/tenancy/management/commands/seed_demo.py; 09-infra §5 step 4
#            + §13 item 6). Two tiers, because the command has two halves:
#            · sqlite tier — the write-free `--check` report, the non-Postgres
#              refusal, and the FIXTURE-FIGURE PROVENANCE of every money value
#              the seed carries (asserted against the ratified sources
#              themselves, not against a restated copy).
#            · Postgres tier — the real thing: seed a live tenant, count what
#              landed, seed AGAIN and prove nothing moved (BR-TEN-010 posture).
#              Gated by tests.isolation_helpers.requires_postgres, because
#              tenant context is a Postgres GUC.
# Rules:     BR-TEN-001/010/012 · BR-RAT-020/023/024/025/030/031/035/036 ·
#            BR-MET-002/003/009/010/033/034 · BR-AST-009/011/043/044 ·
#            CLAUDE.md rule 2 (money is NUMERIC(18,6), never float) and the
#            prime directive (never resolve an open figure by choosing one).
#            The DEF-026 per-path production guard (BR-TEN-064) is asserted in
#            tests/test_reference_data_completeness.py, where the provisioning
#            fixtures those cases need already live.
# ───────────────────────────────────────────────────────
"""seed_demo tests — what it creates, that a replay changes nothing, and that
every seeded money value can be traced back to the fixture it came from.

The provenance cases are the point of this file: a demo seeder is the easiest
place in the codebase for an invented price to hide, so each figure is checked
against its SOURCE TEXT — `apps/tenancy/fixtures/lookup_defaults.json` for the
charge codes and tax jurisdictions, and the billing workbook
(`04-docs/05-modules/07-billing/08-worked-examples.md`) for the plan and rate
figures. If someone changes a rate here without changing the ratified source,
these tests go red.

AMENDED 2026-08-10 (PO ruling). TAMPER changed SOURCE, not just value: it is
$250.00 from the PLATFORM fixture, because the PO chose EP-RAT-03 §4's figure
over the billing workbook's $500.00 AND made it a platform default rather than
one fixture utility's number. The workbook still says $500.00 in WE-11 and is
still correct there, so this file asserts BOTH — a ruling that leaves no trace
is indistinguishable from drift.
"""

import io
import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.tenancy.management.commands import seed_demo as seed_demo_module

from tests.isolation_helpers import requires_postgres

CMD = seed_demo_module

FIXTURE = json.loads(
    (
        Path(seed_demo_module.__file__).resolve().parents[2] / "fixtures" / "lookup_defaults.json"
    ).read_text(encoding="utf-8")
)

WORKBOOK = (
    Path(seed_demo_module.__file__).resolve().parents[5]
    / "04-docs"
    / "05-modules"
    / "07-billing"
    / "08-worked-examples.md"
)


def _expected_charge_codes() -> set[str]:
    """`DEF-TEN-8816` — the demo tenant's charge codes are NOT only
    seed_demo's: provisioning seeds the platform catalogue
    (`lookup_defaults.json` `charge_codes`) first, every code except the ones
    rating omits by name (`reference_seed_omissions` — the two deposit codes,
    BR-RAT-020/023), and seed_demo then creates-or-completes its own list on
    top. The union, so a code added to either list moves this figure (27 on
    2026-10-01: 23 platform codes + seed_demo's four base codes)."""
    from apps.rating import services as rating_services

    omitted = {
        row["entry"]
        for row in rating_services.reference_seed_omissions("charge_codes", FIXTURE["charge_codes"])
    }
    platform = {entry["code"] for entry in FIXTURE["charge_codes"]} - omitted
    return platform | {entry["code"] for entry in CMD.CHARGE_CODES}


def _expected_tax_jurisdictions() -> set[str]:
    """`DEF-TEN-8818` — the same shape for jurisdictions: provisioning seeds
    the tenant's own state's rows plus the `ALL` scaffold
    (`tenancy.services.tax_jurisdiction_entries`, CR-010 / CR-077), matched by
    NAME, and seed_demo's `TAX_RULES` name jurisdictions inside that set. Seven
    for Texas on 2026-10-01 (`City` is in both halves and seeds once)."""
    from apps.tenancy import services as tenancy_services

    platform = {
        entry["name"] for entry in tenancy_services.tax_jurisdiction_entries(FIXTURE, "TX")
    }
    return platform | {entry["jurisdiction"]["name"] for entry in CMD.TAX_RULES}


EXPECTED = {
    "charge codes": len(_expected_charge_codes()),
    "taxes": len(CMD.TAX_RULES),
    "tax jurisdictions": len(_expected_tax_jurisdictions()),
    "rate schedules": len(CMD.RATE_SCHEDULES),
    "rate plans": len(CMD.RATE_PLANS),
    "premises": len(CMD.PREMISES),
    "units": sum(len(entry["units"]) for entry in CMD.PREMISES),
    "routes": len(CMD.ROUTES),
    "billing cycles": len(CMD.CYCLES),
    "assets": len(CMD.ASSETS),
}


def _by_code(entries, code):
    return next(entry for entry in entries if entry["code"] == code)


def _schedule(name):
    return next(entry for entry in CMD.RATE_SCHEDULES if entry["name"] == name)


def _plan(code):
    return next(entry for entry in CMD.RATE_PLANS if entry["code"] == code)


def _plan_service(plan_code, service_code):
    return next(row for row in _plan(plan_code)["services"] if row["service"] == service_code)


# ══════════════════════════════════════════════════════════════════════════
# Provenance — every money value traces to a ratified source (vendor-agnostic)
# ══════════════════════════════════════════════════════════════════════════
def test_seed_charge_amounts_are_the_w0_fixture_amounts_verbatim():
    """[F] apps/tenancy/fixtures/lookup_defaults.json `charge_codes`.

    `charges.percent`/`min_amount`/`amount` are NUMERIC(18,6) and the percent
    form stores a FRACTION (US-RAT-008 TC-3), so the fixture's "1.5" percent
    points appear as 0.015 — a representation change, never a new number.
    """
    fixture = {entry["code"]: entry for entry in FIXTURE["charge_codes"]}

    late = _by_code(CMD.CHARGE_CODES, "LATE")
    assert Decimal(late["percent"]) == Decimal(fixture["LATE"]["percent"]) / 100
    assert Decimal(late["min_amount"]) == Decimal(fixture["LATE"]["min_amount"])

    for code in ("CONN", "DISC", "NSF", "TAMPER"):
        assert Decimal(_by_code(CMD.CHARGE_CODES, code)["amount"]) == Decimal(
            fixture[code]["amount"]
        ), code

    # AMENDED 2026-08-10 (PO ruling): TAMPER is a PLATFORM figure now, so it is
    # quoted from [F] with the other three above rather than from the workbook.
    assert Decimal(fixture["TAMPER"]["amount"]) == Decimal("250")

    # The confirmed S12 classification per code — the fixture states it now, so
    # a signup tenant is classified exactly as the demo tenant is.
    # CR-010 A2 grew the fixture 6 → 25; this case is about the DEMO tenant's
    # amounts matching the fixture verbatim, so it pins the SUBSET it asserts
    # against rather than the whole catalog (the full 25-code pin lives in
    # test_reference_data_completeness, one place, no second copy to drift).
    fixture_types = {entry["code"]: entry.get("charge_type") for entry in FIXTURE["charge_codes"]}
    assert len(fixture_types) == 25  # the CR-010 A2 ruled size
    for code, charge_type in {
        "LATE": "penalty",
        "CONN": "one_time",
        "DISC": "one_time",
        "NSF": "penalty",
        "DEPO-R": "refundable",
        "TAMPER": "penalty",
    }.items():
        assert fixture_types[code] == charge_type

    # DEPO-R carries its code and its class and NO amount — deliberately, per
    # BR-RAT-020/023 (deposits are `plan_deposit_rules`, which supersede the
    # prototype's single DEPO-R checkbox), not for want of a ratified figure.
    assert "amount" not in fixture["DEPO-R"] and "percent" not in fixture["DEPO-R"]
    assert all(entry["code"] != "DEPO-R" for entry in CMD.CHARGE_CODES)
    assert any("DEPO-R" in note for note in CMD.OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE)
    assert any(
        "BR-RAT-020/023" in note
        for note in CMD.OMITTED_FOR_LACK_OF_A_RATIFIED_FIGURE
        if "DEPO-R" in note
    )


def test_seed_tax_rates_are_the_w0_fixture_rates_as_fractions():
    """[F] lookup_defaults.json `tax_jurisdictions.TX`; `taxes.rate` is a
    fraction (models.Tax comment / US-RAT-009 TC-1).

    ⚠ AMENDED 2026-08-18 (DEF-254 → DEF-273). This used to assert that
    seed_demo's `TAX_RULES` and the fixture's TX list were the SAME SET, and
    they no longer are: the fixture now carries the PO's five ruled Texas
    authorities and their rates, while `seed_demo` still carries the two it has
    always had. That is not drift — it is DEF-247's set-skip working. Whichever
    seeder runs first wins the whole set and the other adds nothing, because a
    NAME check cannot express the rule (*"two seeders naming the same rate
    differently is not an edge case; it is the normal case"*), and provisioning
    runs before `seed_demo`.

    What still has to hold, and is what this test now asserts: seed_demo's two
    rows must not CONTRADICT the fixture's figures for the same authority. A
    tenant that somehow received seed_demo's pair must be taxed at the same
    6.25 % and 2.00 % the fixture states.
    """
    fixture_taxes = {
        tax["name"]: tax
        for entry in FIXTURE["tax_jurisdictions"]["TX"]
        for tax in (entry.get("taxes") or [])
    }
    # The fixture prices all five ruled rows; three of them are new since
    # 2026-08-18 and none of them is a percent (or is on a jurisdiction)
    # seed_demo names.
    assert set(fixture_taxes) == {
        "TX State Utility Tax",
        "Local · Bexar County",
        "PUC Regulatory Fee",
        "City Franchise Fee",
        "Water Conservation Surcharge",
    }
    by_jurisdiction = {
        entry["name"]: (entry.get("taxes") or [])[0] for entry in FIXTURE["tax_jurisdictions"]["TX"]
    }
    for entry in CMD.TAX_RULES:
        counterpart = by_jurisdiction[entry["jurisdiction"]["name"]]
        assert entry["kind"] == counterpart["kind"] == "percent", entry["name"]
        assert Decimal(entry["rate"]) == Decimal(counterpart["rate"]) / 100, entry["name"]


@pytest.mark.skipif(not WORKBOOK.exists(), reason=f"billing workbook not present at {WORKBOOK}")
def test_seed_rate_figures_are_quoted_from_the_billing_workbook():
    """[W] 04-docs/05-modules/07-billing/08-worked-examples.md §1 + WE-3/WE-11.

    Asserted against the workbook's OWN TEXT: each quoted phrase must still be
    in the document, and the seeded Decimal must equal the figure in it.
    """
    text = WORKBOOK.read_text(encoding="utf-8")

    # §1 Residential Standard — water tiers, TOU summer prices, bases.
    assert "0–5 kgal $4.00 / 5–15 $6.50 / 15+ $8.00" in text
    tiers = _schedule("Residential Water — Inclining tiers")["structure"]["tiers"]
    assert [(t["from_qty"], t["to_qty"], Decimal(t["unit_price"])) for t in tiers] == [
        ("0", "5", Decimal("4.00")),
        ("5", "15", Decimal("6.50")),
        ("15", None, Decimal("8.00")),
    ]

    assert "summer on $0.22" in text and "off $0.09" in text
    windows = {
        w["label"]: Decimal(w["unit_price"])
        for w in _schedule("Residential Electric — TOU")["structure"]["windows"]
    }
    assert windows["On-peak"] == Decimal("0.22")
    assert windows["Off-peak"] == Decimal("0.09")

    assert "Elec $12 · Water $8" in text
    assert Decimal(_plan_service("RES-STD", "electric")["base_charge"]) == Decimal("12")
    assert Decimal(_plan_service("RES-STD", "water")["base_charge"]) == Decimal("8")

    # §1 Small Commercial — flat water, water base.
    assert "Water flat $5.20/kgal" in text
    assert Decimal(
        _schedule("Small Commercial Water — Flat")["structure"]["unit_price"]
    ) == Decimal("5.20")
    assert "Elec $48 · Water $15" in text
    assert Decimal(_plan_service("COM-SM", "water")["base_charge"]) == Decimal("15")

    # §1 Industrial — energy + demand, electric base.
    assert "Electric energy $0.085/kWh + demand $11.00/kW" in text
    demand = _schedule("Industrial Electric — Energy + demand")["structure"]["demand"]
    assert Decimal(demand["energy_rate_per_kwh"]) == Decimal("0.085")
    assert Decimal(demand["demand_rate_per_kw"]) == Decimal("11.00")
    assert "Elec $180" in text
    assert Decimal(_plan_service("IND", "electric")["base_charge"]) == Decimal("180")

    # WE-3 minimum bill.
    # ⚠ **IT IS THE RATE SCHEDULE'S FIGURE SINCE 2026-09-10** — PO ruling, *"set
    # it in rates and use it in plans - thats it - this is rule"*. It was
    # `RATE_PLANS["RES-STD"]` water's `minimum_amount`; that column is gone
    # (`rating/0030` moves every stated figure onto the attached schedule's
    # versions, `0031` removes it). The workbook figure did not move — only
    # where the fixture states it — which is what this test exists to pin.
    assert "min $15.00" in text
    assert "minimum_amount" not in _plan_service("RES-STD", "water"), (
        "the plan states a per-service minimum again — BR-RAT-028 mode (A) is "
        "the rate schedule's since the PO ruling of 2026-09-10"
    )
    assert Decimal(
        _schedule("Residential Water — Inclining tiers")["minimum_bill"]
    ) == Decimal("15.00")

    # TAMPER is NO LONGER quoted from this document (PO ruling 2026-08-10).
    # Two ratified sources disagreed — this workbook says $500.00 (§1 + WE-11),
    # EP-RAT-03 §4 says "New: TAMPER $250.00" — and the PO ruled $250.00 AND
    # ruled it a PLATFORM default, so it lives in the platform fixture and the
    # test above pins it there. The workbook's figure is not wrong and is not
    # deleted: it is the WE-11 worked example, still in the document, and this
    # assertion keeps the two facts side by side so the divergence stays
    # visible instead of looking like drift.
    assert "TAMPER charge code $500.00" in text  # WE-11, unchanged
    assert Decimal(_by_code(CMD.CHARGE_CODES, "TAMPER")["amount"]) == Decimal("250")


def test_seed_declares_every_measuring_asset_with_an_explicit_uom_and_classifications():
    """BR-AST-009 + CLAUDE.md rule 3 (consumption always with a unit) and
    BR-AST-043/044: measuring assets carry service + UoM + both
    classifications; non-measuring ones carry neither meter_type nor
    read_method (the service refuses a meter type there)."""
    measuring = {"meter", "net_meter", "sub_meter"}
    saw_measuring = saw_non_measuring = False
    for entry in CMD.ASSETS:
        if entry["type"] in measuring:
            saw_measuring = True
            assert entry["service"] and entry["uom"], entry["asset_no"]
            assert entry["meter_type"] and entry["read_method"], entry["asset_no"]
        else:
            saw_non_measuring = True
            assert "meter_type" not in entry, entry["asset_no"]
            assert "read_method" not in entry, entry["asset_no"]
            assert "service" not in entry and "uom" not in entry, entry["asset_no"]
    assert saw_measuring and saw_non_measuring


def test_seed_only_touches_services_the_fixture_tenant_enables():
    """BR-RAT-024 / BR-MET-003: schedules, plan services, premises availability
    and asset services all stay inside the tenant's enabled set."""
    enabled = set(CMD.BRAZOS_BEND["services"])
    assert {entry["service"] for entry in CMD.RATE_SCHEDULES} <= enabled
    for plan in CMD.RATE_PLANS:
        assert {row["service"] for row in plan["services"]} <= enabled
    for premises in CMD.PREMISES:
        assert set(premises["services_available"]) <= enabled
    assert {entry["service"] for entry in CMD.ASSETS if entry.get("service")} <= enabled


# ══════════════════════════════════════════════════════════════════════════
# `--check` and the non-Postgres refusal (sqlite-safe)
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_check_reports_readiness_and_writes_nothing():
    out = io.StringIO()
    call_command("seed_demo", "--check", stdout=out)
    report = out.getvalue()
    assert "database vendor" in report
    assert ("ready to seed" in report) or ("not ready" in report)
    from apps.tenancy import models

    assert not models.Tenant.objects.filter(subdomain="brazosbend").exists()


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor == "postgresql", reason="the refusal only fires off Postgres")
def test_seed_refuses_on_a_non_postgres_vendor_before_touching_tenant_tables():
    with pytest.raises(CommandError):
        call_command("seed_demo", stdout=io.StringIO())
    from apps.tenancy import models

    assert not models.Tenant.objects.filter(subdomain="brazosbend").exists()


# ══════════════════════════════════════════════════════════════════════════
# The real seed — live Postgres only (tenant context is a Postgres GUC)
# ══════════════════════════════════════════════════════════════════════════
def _live_counts(tenant_id):
    from apps.assets import models as asset_models
    from apps.metering import models as metering_models
    from apps.rating import models as rating_models
    from core import tenancy as core_tenancy

    def count(model, **extra):
        # Explicit tenant scoping: the dev/CI role is a SUPERUSER, so RLS is
        # bypassed on this connection (see tests/isolation_helpers.py) and a
        # bare .count() would be a cross-tenant read, not a scoped one.
        return model.objects.filter(tenant_id=tenant_id, **extra).count()

    with core_tenancy.tenant_context(tenant_id):
        return {
            "charge codes": count(rating_models.Charge),
            "taxes": count(rating_models.Tax),
            "tax jurisdictions": count(rating_models.TaxJurisdiction),
            "rate schedules": count(rating_models.Tariff),
            "tariff versions": count(rating_models.TariffVersion),
            "rate plans": count(rating_models.RatePlan),
            "published plans": count(rating_models.RatePlan, status="published"),
            "plan services": count(rating_models.PlanService),
            "plan schedules": count(rating_models.PlanRateSchedule),
            "premises": count(metering_models.Premises),
            "units": count(metering_models.Unit),
            "service points": count(metering_models.ServicePoint),
            "routes": count(metering_models.Route),
            "route memberships": count(metering_models.RouteMembership),
            "billing cycles": count(metering_models.Cycle),
            "assets": count(asset_models.Asset),
            "asset assignments": count(asset_models.AssetAssignment),
        }


@requires_postgres
@pytest.mark.django_db
def test_seed_demo_fills_every_w1_screen_and_a_replay_changes_nothing():
    from apps.tenancy import models

    first = io.StringIO()
    call_command("seed_demo", stdout=first)
    tenant = models.Tenant.objects.get(subdomain="brazosbend")
    after_first = _live_counts(tenant.id)

    for label, expected in EXPECTED.items():
        assert after_first[label] == expected, label
    # W1 screens are only "worth walking through" when the bundles are complete.
    assert after_first["published plans"] == len(CMD.RATE_PLANS)
    assert after_first["tariff versions"] == len(CMD.RATE_SCHEDULES)
    assert after_first["plan schedules"] == after_first["plan services"]
    assert after_first["service points"] > 0
    # `DEF-TEN-8819` — one membership per unit PER ROUTE: RT-004 and RT-006
    # repeat RT-003's and RT-005's addresses for the other service (BR-MET-074,
    # one address, two crews), so an address's units sit on two routes.
    units_at = {entry["address_line"]: len(entry["units"]) for entry in CMD.PREMISES}
    assert after_first["route memberships"] == sum(
        units_at[address] for route in CMD.ROUTES for address in route["premises"]
    )
    assert after_first["route memberships"] > EXPECTED["units"]
    # every asset that names a unit opened its first assignment (BR-AST-011)
    assert after_first["asset assignments"] == sum(
        1 for entry in CMD.ASSETS if entry.get("on") is not None
    )

    second = io.StringIO()
    call_command("seed_demo", stdout=second)
    assert _live_counts(tenant.id) == after_first
    assert "this run created nothing" in second.getvalue()
    assert "brazosbend" in second.getvalue()
    assert CMD.BRAZOS_BEND["owner"]["email"] in second.getvalue()


@requires_postgres
@pytest.mark.django_db
def test_seeded_money_lands_in_the_db_exactly_as_the_fixture_states_it():
    """The provenance cases above check the CONSTANTS; this one checks what the
    real services actually stored — NUMERIC(18,6), no float anywhere."""
    from apps.rating import models as rating_models
    from apps.tenancy import models
    from core import tenancy as core_tenancy

    call_command("seed_demo", stdout=io.StringIO())
    tenant = models.Tenant.objects.get(subdomain="brazosbend")

    fixture_charges = {entry["code"]: entry for entry in FIXTURE["charge_codes"]}
    scope = {"tenant_id": tenant.id}  # explicit: the CI role bypasses RLS
    with core_tenancy.tenant_context(tenant.id):
        charges = {row.code: row for row in rating_models.Charge.objects.filter(**scope)}
        assert charges["LATE"].percent == Decimal(fixture_charges["LATE"]["percent"]) / 100
        assert charges["LATE"].min_amount == Decimal(fixture_charges["LATE"]["min_amount"])
        # `DEF-RAT-8813` — `charges.amount` is retired (`CR-156-BRC10`,
        # 2026-10-01): a flat amount is an *All sizes* row, read through the one
        # door the retirement names.
        from apps.rating import charge_prices

        for code in ("CONN", "DISC", "NSF", "TAMPER"):
            assert charge_prices.flat_amount(charges[code]) == Decimal(
                fixture_charges[code]["amount"]
            ), code
        # [F] — PO ruling 2026-08-10
        assert charge_prices.flat_amount(charges["TAMPER"]) == Decimal("250")
        # …and every seeded row carries its confirmed S12 class.
        for code, entry in fixture_charges.items():
            if code in charges:
                assert charges[code].charge_type == entry["charge_type"], code
        assert "DEPO-R" not in charges  # BR-RAT-020/023, not a missing figure

        # `DEF-TEN-8818` — each Texas jurisdiction carries its own `taxes`
        # list (DEF-254/DEF-273); a tax is found by ITS name, not the
        # jurisdiction's.
        fixture_taxes = {
            tax["name"]: tax
            for jurisdiction in FIXTURE["tax_jurisdictions"]["TX"]
            for tax in jurisdiction.get("taxes") or []
        }
        for tax in rating_models.Tax.objects.filter(**scope):
            assert tax.rate == Decimal(fixture_taxes[tax.name]["rate"]) / 100, tax.name

        water = rating_models.Tariff.objects.get(
            **scope, name="Residential Water — Inclining tiers"
        )
        tiers = rating_models.RateTier.objects.filter(tariff_version__tariff=water).order_by("seq")
        assert [(t.from_qty, t.to_qty, t.unit_price) for t in tiers] == [
            (Decimal("0"), Decimal("5"), Decimal("4")),
            (Decimal("5"), Decimal("15"), Decimal("6.5")),
            (Decimal("15"), None, Decimal("8")),
        ]

        flat = rating_models.Tariff.objects.get(**scope, name="Small Commercial Water — Flat")
        assert rating_models.RateTier.objects.get(
            tariff_version__tariff=flat
        ).unit_price == Decimal("5.20")

        demand = rating_models.DemandRateConfig.objects.get(**scope)
        assert demand.energy_rate_per_kwh == Decimal("0.085")
        assert demand.demand_rate_per_kw == Decimal("11")

        tou = {
            window.label: window.unit_price
            for window in rating_models.TimeOfUseWindow.objects.filter(**scope)
        }
        assert tou["On-peak"] == Decimal("0.22")
        assert tou["Off-peak"] == Decimal("0.09")

        # ⚠ `DEF-RAT-8828` — the service minimum left `plan_services` on
        # 2026-09-10 (`rating/0031`, *"set it in rates and use it in plans"*)
        # and, since 2026-10-01, is set PER METER SIZE on the schedule
        # (`DEF-RAT-8737`, PO option A; `seed_demo` writes WE-3's `$15.00` onto
        # every size row). So the floor is read where billing reads it: every
        # size row of the plan's schedule for that service, with the version's
        # own figure empty. One set per (plan, service): `{15}` is "every size
        # floors at $15.00", `{None}` is "no size has a minimum".
        schedule_of = {
            (link.rate_plan.code, link.service.code): link.tariff_id
            for link in rating_models.PlanRateSchedule.objects.filter(**scope).select_related(
                "rate_plan", "service"
            )
        }

        def _floors(plan_code, service_code):
            versions = rating_models.TariffVersion.objects.filter(
                **scope, tariff_id=schedule_of[(plan_code, service_code)]
            )
            assert all(v.minimum_bill is None for v in versions), (plan_code, service_code)
            rows = rating_models.RateSizeRow.objects.filter(**scope, tariff_version__in=versions)
            assert rows.exists(), (plan_code, service_code)
            return {row.minimum_bill for row in rows}

        bases = {
            (row.rate_plan.code, row.service.code): row.base_charge
            for row in rating_models.PlanService.objects.filter(**scope).select_related(
                "rate_plan", "service"
            )
        }
        assert (bases[("RES-STD", "electric")], _floors("RES-STD", "electric")) == (
            Decimal("12"),
            {None},
        )
        assert (bases[("RES-STD", "water")], _floors("RES-STD", "water")) == (
            Decimal("8"),
            {Decimal("15")},
        )
        assert (bases[("COM-SM", "water")], _floors("COM-SM", "water")) == (
            Decimal("15"),
            {None},
        )
        assert (bases[("IND", "electric")], _floors("IND", "electric")) == (
            Decimal("180"),
            {None},
        )


# ══════════════════════════════════════════════════════════════════════════
# CR-054 W0 task 1 — THE MULTI-REGISTER READINGS
#
# ⚠ THE FINDING THESE CASES EXIST FOR, MEASURED ON A LIVE SEEDED TENANT
# (2026-08-30, PostgreSQL 16): `select channel, count(*) from meter_reads
# group by 1` returned exactly one row — `total | 199`. Every reading the
# product had ever seeded carried NO channel, so `plan_register_completeness`
# had nothing short to fire on, `tou_sum_sanity` could only ever answer
# `not_evaluated: incomplete_group`, and no `demand` or `export` register
# existed anywhere on the demo utility.
#
# Two tiers, matching the two this file already has: the CONSTANTS are checked
# here (they go red the moment somebody edits a register value so the windows
# stop summing), and what actually LANDED is checked on live Postgres below.
# ══════════════════════════════════════════════════════════════════════════
def _read_rows():
    for batch in CMD.DEMO_CYCLE_READS:
        for row in batch["rows"]:
            yield batch, row


def _registers_by_meter_date():
    """(meter, read date) → {register: Decimal(register value)}, from the
    constant. The shape the validation engine's GROUP rules are computed over."""
    out: dict[tuple[str, str], dict[str, Decimal]] = {}
    for _batch, row in _read_rows():
        out.setdefault((row["meter_id"], row["read_date"]), {})[row["channel"]] = Decimal(
            row["reading"]
        )
    return out


def _unit_plan_codes():
    return {
        unit["unit_no"]: unit.get("plan") for premises in CMD.PREMISES for unit in premises["units"]
    }


def _meter_unit_no():
    """asset_no → unit_no, resolved through the (address, label) pair the ASSETS
    table places a meter on — the same pair `_seed_assets` indexes by."""
    labels = {
        (premises["address_line"], unit["label"]): unit["unit_no"]
        for premises in CMD.PREMISES
        for unit in premises["units"]
    }
    return {
        entry["asset_no"]: labels[entry["on"]]
        for entry in CMD.ASSETS
        if entry.get("on") is not None
    }


def test_every_seeded_reading_names_a_seeded_meter_and_a_unit_that_carries_a_plan():
    """A reading whose meter does not exist stages as `unknown_meter`, and a
    reading on a planless unit makes `plan_register_completeness` report
    `not_evaluated: no_plan` — the exact state CR-054 W0 task 1 found, and one
    that is invisible unless something asserts against it."""
    meters = {entry["asset_no"] for entry in CMD.ASSETS}
    on_unit = _meter_unit_no()
    plans = _unit_plan_codes()
    plan_codes = {plan["code"] for plan in CMD.RATE_PLANS}
    for _batch, row in _read_rows():
        meter = row["meter_id"]
        assert meter in meters, meter
        assert meter in on_unit, f"{meter} is in inventory — a read cannot be filed against it"
        assert plans[on_unit[meter]] in plan_codes, meter


def test_the_seeded_time_of_use_windows_sum_to_their_total_within_the_tenants_tolerance():
    """BR-MET-052 / `validation.tou_sum_sanity`: Σ(tou_on + tou_mid + tou_off)
    ≈ total, judged against the tenant's seeded `tou_sum_tolerance_pct`.

    The rule reads CONSUMPTIONS (BR-MET-019 deltas), not register values, so
    this case derives the deltas from consecutive reads exactly as the engine
    does. The tolerance is NOT restated here — it is read from
    `metering.services.RATIFIED_SERVICE_SEED`, so a re-ratification moves the
    product and this assertion together and neither can drift alone.
    """
    from apps.metering.services import RATIFIED_SERVICE_SEED

    tolerance = RATIFIED_SERVICE_SEED["electric"]["tou_sum_tolerance_pct"]
    registers = _registers_by_meter_date()
    windows = ("tou_on", "tou_mid", "tou_off")
    checked = 0
    for (meter, read_date), current in sorted(registers.items()):
        if not all(channel in current for channel in windows):
            continue
        prior = next(
            (
                values
                for (other_meter, other_date), values in sorted(registers.items())
                if other_meter == meter and other_date < read_date
            ),
            None,
        )
        if prior is None:
            continue  # the opening read has no delta — nothing for the rule to judge
        window_sum = sum(current[c] - prior[c] for c in windows)
        total = current["total"] - prior["total"]
        deviation = abs(total - window_sum) / total * Decimal(100)
        assert deviation <= tolerance, f"{meter} {read_date}: {deviation}% > {tolerance}%"
        checked += 1
    assert checked >= 2, "no TOU meter in the seed has a delta for the rule to judge"


def test_one_seeded_meter_is_deliberately_short_of_its_plans_register_set():
    """BR-MET-049: the whole point of the register-completeness WARNING is that
    a clerk reads *"expects total/tou_on/tou_mid/tou_off, file has total only"*.
    A fixture in which every meter is complete gives that warning nothing to
    fire on, which is the state this task found.

    ⚠ **JUDGED ON THE LATEST READ DATE PER METER, AND THAT IS THE WHOLE GUARD.**
    The first draft asked whether ANY (meter, date) group was total-only, and it
    stayed GREEN through its own red-proof: giving M-7301 all four registers in
    August left its JULY opening read total-only, which satisfied the question
    as asked. A check that cannot tell pass from fail is worse than no check
    (CLAUDE.md law 11's own words), so it now asks about the read the product
    actually judges — the most recent one, the one whose plan version resolves.
    """
    on_unit = _meter_unit_no()
    plans = _unit_plan_codes()
    tou_plans = {
        plan["code"]
        for plan in CMD.RATE_PLANS
        for service in plan["services"]
        if _schedule(service["schedule"])["model"] == "time_of_use"
    }
    registers = _registers_by_meter_date()
    latest: dict[str, tuple[str, set[str]]] = {}
    for (meter, read_date), channels in registers.items():
        if plans[on_unit[meter]] not in tou_plans:
            continue
        if meter not in latest or read_date > latest[meter][0]:
            latest[meter] = (read_date, set(channels))
    short = {meter for meter, (_date, channels) in latest.items() if channels == {"total"}}
    complete = {
        meter
        for meter, (_date, channels) in latest.items()
        if {"total", "tou_on", "tou_mid", "tou_off"} <= channels
    }
    assert short, "no seeded meter is short of its plan's register set on its latest read"
    assert complete, "no seeded TOU meter carries its full register set on its latest read"


def test_the_demand_rows_are_a_maximum_in_kw_and_only_they_carry_a_reset():
    """BR-MET-051 + BR-MET-143 / DEF-797. Two facts, and the defect was worth
    **$4,378.00 on one bill**: a demand register is a MAXIMUM (so its peak is
    the billed quantity and nothing subtracts one peak from another), and
    `demand_reset` is lawful ONLY on a demand row
    (`demand_reset_not_demand_channel`)."""
    demand_plans = {
        plan["code"]
        for plan in CMD.RATE_PLANS
        for service in plan["services"]
        if _schedule(service["schedule"])["model"] == "demand"
    }
    on_unit = _meter_unit_no()
    plans = _unit_plan_codes()
    demand_rows = [row for _b, row in _read_rows() if row["channel"] == "demand"]
    assert demand_rows, "the demo has no demand register at all"
    for row in demand_rows:
        assert plans[on_unit[row["meter_id"]]] in demand_plans, row["meter_id"]
    for _batch, row in _read_rows():
        if row.get("demand_reset"):
            assert row["channel"] == "demand", row


def test_an_export_row_is_seeded_only_on_a_net_metering_asset():
    """BR-AST-029 / `validation.export_not_net`: an export record is lawful on a
    net-metering asset and on no other, and it is a HARD error elsewhere — so a
    fixture that put one on a plain meter would refuse its own batch."""
    net = {
        entry["asset_no"]
        for entry in CMD.ASSETS
        if entry.get("net_metering") or entry["type"] == "net_meter"
    }
    exports = {row["meter_id"] for _b, row in _read_rows() if row["channel"] == "export"}
    assert exports, "the demo has no export register at all"
    assert exports <= net, exports - net


@requires_postgres
@pytest.mark.django_db
def test_the_seed_lands_every_register_and_the_two_group_rules_actually_fire():
    """The live half — what CR-054 W0 task 1 is FOR. Asserts the four registers
    the demo utility could not previously demonstrate, and that the two group
    rules reach a VERDICT rather than `not_evaluated`."""
    from apps.metering import models as metering_models
    from apps.tenancy import models
    from core import tenancy as core_tenancy

    call_command("seed_demo", stdout=io.StringIO())
    tenant = models.Tenant.objects.get(subdomain="brazosbend")
    scope = {"tenant_id": tenant.id}  # explicit: the CI role bypasses RLS

    with core_tenancy.tenant_context(tenant.id):
        heads = metering_models.MeterRead.objects.filter(**scope, superseded_by_id__isnull=True)
        for channel in ("tou_on", "tou_mid", "tou_off", "demand", "export"):
            assert heads.filter(channel=channel).exists(), channel

        # BR-MET-143: a demand register carries kW and its consumption is the
        # PEAK, scaled by the meter's own multiplier — never a delta of peaks.
        peak = heads.filter(channel="demand").order_by("-read_at").first()
        assert peak.unit == "kW"
        assert peak.consumption == Decimal("412")  # 41.2 read on a x10 CT meter
        assert peak.demand_reset_noted is True

        # The export register is a QUANTITY and is never netted here
        # (BR-AST-025 — subtracting export from import is rating's credit math).
        assert heads.filter(channel="export").order_by("-read_at").first().unit == "kWh"

        verdicts: dict[tuple[str, str], set[str]] = {}
        for row in metering_models.ReadImportRow.objects.filter(
            **scope, batch__file_name__startswith="demo-2026-08"
        ):
            for outcome in row.rule_outcomes or []:
                if outcome["rule"] in ("plan_registers", "tou_sum_sanity"):
                    verdicts.setdefault((row.meter_no_raw, outcome["rule"]), set()).add(
                        outcome["severity"]
                    )

    # `not_evaluated` is the state this task existed to end — assert the VERDICT.
    assert verdicts[("M-7450", "tou_sum_sanity")] == {"ok"}
    assert verdicts[("M-7450", "plan_registers")] == {"ok"}
    assert verdicts[("M-7210", "plan_registers")] == {"ok"}
    assert verdicts[("M-7302", "plan_registers")] == {"ok"}
    assert verdicts[("M-7301", "plan_registers")] == {"warning"}


def test_seed_charges_never_sends_a_scalar_amount_to_a_code_priced_per_size(monkeypatch):
    """DEF-TEN-5343 — a NULL amount beside a per-size table is NOT a blank.

    Since `DEF-6440` (2.219.7, 2026-09-07) provisioning prices every base code
    PER CONNECTION SIZE and omits the scalar on purpose: CR-013 part 2 gives a
    code ONE basis, and `rating.services._validate_charge` refuses a scalar
    beside a table (`rating.charges.amount_and_size_table`). `_seed_charges`'
    create-or-COMPLETE read that NULL as a field still to fill, sent the
    fixture's scalar, and every fresh `seed_demo` died at the charge step for
    eight days — before taxes, schedules, plans, premises, cycles, assets or
    reads existed. Nothing in the default suite ran the seed, because the
    end-to-end case is Postgres-gated; this one is not.

    Runs on sqlite: rating's reader and writers are stubbed at the module
    attributes `_seed_charges` resolves at call time, so what is asserted is
    the PAYLOAD the seed decides to send, which is the whole defect.
    """
    from apps.rating import selectors as rating_selectors
    from apps.rating import services as rating_services

    entry = _by_code(CMD.CHARGE_CODES, "BASE-W")
    # The row provisioning leaves behind: every fixture field answered EXCEPT
    # the scalar, which the table owns — its smallest size IS the fixture figure.
    priced_per_size = {
        **{k: v for k, v in entry.items()},
        "id": "chg-base-w",
        "amount": None,
        "size_amounts": [
            {"size_class": "5/8", "customer_class": None, "amount": entry["amount"]},
            {"size_class": "2", "customer_class": None, "amount": "34"},
        ],
    }
    # And one that ALSO lacks its classification, so the fill still has a job.
    priced_per_size_unclassified = {
        **priced_per_size,
        "id": "chg-base-e",
        "code": "BASE-E",
        "name": _by_code(CMD.CHARGE_CODES, "BASE-E")["name"],
        "charge_type": None,
    }
    monkeypatch.setattr(
        rating_selectors,
        "charge_list",
        lambda params: [priced_per_size, priced_per_size_unclassified],
    )
    sent: list[tuple[str, dict]] = []
    created: list[str] = []
    monkeypatch.setattr(
        rating_services,
        "update_charge",
        lambda actor, charge_id, payload: sent.append((charge_id, dict(payload))),
    )
    monkeypatch.setattr(
        rating_services, "create_charge", lambda actor, payload: created.append(payload["code"])
    )

    CMD.Command()._seed_charges(actor=object())

    by_id = dict(sent)
    # BASE-W had nothing to complete: the seed must call nothing for it.
    assert "chg-base-w" not in by_id, by_id
    # BASE-E's classification is still filled — the fix must not stop the fill.
    assert by_id["chg-base-e"]["charge_type"] == entry["charge_type"]
    # …and the scalar never travels beside a table, on any row.
    for charge_id, payload in sent:
        assert "amount" not in payload, (charge_id, payload)
    # Every other fixture code was absent and is created, unchanged.
    assert set(created) == {e["code"] for e in CMD.CHARGE_CODES} - {"BASE-W", "BASE-E"}
