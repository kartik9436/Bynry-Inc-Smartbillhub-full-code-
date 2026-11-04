# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 2 task 3 — the taxes & fees redesign's back end
#          (`12-governance/change-requests/CR-165-BRC10-taxes-fees-redesign.md`
#          §9 the API contract, §10 what shipped).
# Defects: DEF-RAT-9278 (per-meter bills $0.00) · DEF-RAT-9279 (a deactivated
#          tax still charges) · DEF-RAT-9280 (two taxes of one authority refuse
#          the bill) · DEF-RAT-9282 (an attachment stops at a new rate) ·
#          DEF-RAT-9283 (no new-rate-from-a-date path) · DEF-RAT-9276 (a
#          correction of a coded tax is refused) · DEF-RAT-9275 (as_draft)
# Rules:   BR-RAT-036 (four forms) · BR-RAT-037 (a rate change is a new row) ·
#          BR-RAT-104 (corrections) · BR-BIL-069 (identity and rate name one
#          row) · CLAUDE.md hard rules 2 and 4
# Golden:  ❄️ B4/B5 UNMOVED — tests/golden run before and after (CR §10).
# ───────────────────────────────────────────────────────
"""The redesign's back end, one case per contract line and per money defect.

The figures are the web walk's own (`05-prototype/taxes-fees-2026-10-03/
web-walk.md`): a **$60.00** bill (usage $40.00 + base $20.00, one meter);
State sales tax 6.25% -> **$3.75**, 6.5% -> **$3.90**; County 2% -> **$1.20**;
a per-meter storm fee **$1.25**. They are test data, not signed rules
(B14 rule 37).

PROVED RED FIRST (hard-won law 7) — each money case below was run against the
branch tip BEFORE the fix (`2a842fafc`), in a separate worktree, through this
same pytest harness; the failures are quoted in CR-165-BRC10 §10.

The PostgreSQL half — the two exclusion constraints, the chain trigger, RLS on
the new table and the boundary-date proof on a real server — is
`tests/test_cr165_tax_versions_pg.py`.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.db import transaction

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors, services
from apps.rating.pricing.stages import compute_tax
from core import errors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
#: The walk's $60.00 bill: $20.00 base + 16 kgal x $2.50 = $40.00 usage.
BILL = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="kgal",
    base_charge=Decimal("20.00"),
    unit_price=Decimal("2.50"),
)
USED = rating_seam.Quantity(amount=Decimal("16"), unit="kgal")

OCT_31 = date(2026, 10, 31)
NOV_01 = date(2026, 11, 1)
OCT_15 = date(2026, 10, 15)
NOV_15 = date(2026, 11, 15)


# ── plumbing ────────────────────────────────────────────────────────────────
def authority(tenant, name):
    row, _ = rating_models.TaxJurisdiction.objects.get_or_create(tenant=tenant, name=name)
    return row


def bind(tenant, plan, jurisdiction):
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def attach(tenant, plan, tax):
    rating_models.PlanTaxRule.objects.get_or_create(tenant=tenant, rate_plan=plan, tax=tax)


def rules_on(plan, on):
    return selectors.plan_tax_rules(str(plan.id), on, services=("water",))


def charged(rules):
    """What the walk's $60.00 bill carries in tax under these resolved rules —
    through the real seam and the real engine, never a re-derivation."""
    bill = rating_seam.price_period(
        tariff=BILL,
        consumption=USED,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=Decimal(str(rule["rate"])) if rule.get("rate") is not None else None,
                tax_id=rule.get("tax_id"),
                flat_amount=rule.get("flat_amount"),
                applies_to_services=tuple(rule.get("applies_to_services") or ()),
                # Passed only when present, so this file also runs on the
                # pre-fix tree for the red proof (CR §10).
                **(
                    {"per_meter_amount": rule["per_meter_amount"]}
                    if rule.get("per_meter_amount") is not None
                    else {}
                ),
            )
            for rule in rules
        ),
    )
    return sum((line.amount for line in bill.lines if line.kind == "tax"), Decimal("0.00"))


def a_state_sales_tax(tenant, plan, **extra):
    """Web walk 1.1 — State sales tax 6.25% from 01/01/2026, bound to the plan."""
    state = authority(tenant, "CR165 State")
    tax = rating_models.Tax.objects.create(
        tenant=tenant,
        jurisdiction=state,
        name="State sales tax",
        code="ST-SALES",
        kind="percent",
        rate=Decimal("0.062500"),
        effective_from=date(2026, 1, 1),
        **extra,
    )
    bind(tenant, plan, state)
    return tax, state


# ── DEF-RAT-9278 · per-meter prices ─────────────────────────────────────────
def test_9278_a_per_meter_tax_bills_once_per_meter(brazos):
    """Web walk 1.5's $1.25 per-meter fee on a one-meter bill is **$1.25**.
    RED before the fix: `plan_tax_rules` returned no row at all (0 == 1)."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 per-meter", services=("water",))
        district = authority(brazos, "CR165 Riverside district")
        fee = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=district,
            name="Riverside storm fee",
            kind="per_meter",
            per_meter_amount=Decimal("1.25"),
        )
        bind(brazos, plan, district)
        rules = rules_on(plan, OCT_15)
        assert [rule["tax_id"] for rule in rules] == [str(fee.id)]
        assert Decimal(str(rules[0]["per_meter_amount"])) == Decimal("1.25")
        assert charged(rules) == Decimal("1.25")


def test_9278_two_meters_are_two_charges_and_a_cart_is_no_meter():
    """DEF-386's own figure: $1.25 on a duplex with two water meters is
    **$2.50**. A base-only trash line contributes no meter."""
    rule = SimpleNamespace(per_meter_amount=Decimal("1.25"), applies_to_services=())
    two_meters = SimpleNamespace(
        lines=(
            SimpleNamespace(kind="usage", service="water", asset_id="m-1"),
            SimpleNamespace(kind="usage", service="water", asset_id="m-1"),  # a 2nd tier
            SimpleNamespace(kind="usage", service="water", asset_id="m-2"),
            SimpleNamespace(kind="base", service="trash", asset_id=None),
        )
    )
    assert compute_tax._meters_in_scope(rule, two_meters) == Decimal("2")
    assert compute_tax._tax_amount(rule, Decimal("0"), two_meters) == Decimal("2.50")
    one_meter = SimpleNamespace(
        lines=(SimpleNamespace(kind="usage", service="water", asset_id=None),)
    )
    assert compute_tax._tax_amount(rule, Decimal("0"), one_meter) == Decimal("1.25")


# ── DEF-RAT-9279 · a deactivated tax stops pricing ──────────────────────────
def test_9279_a_deactivated_tax_charges_nothing(brazos, dana):
    """A 2% county tax deactivated adds **$0.00**, not $1.20, to a $60.00 bill.
    RED before the fix: the row was still returned (1 == 0)."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 deactivated", services=("water",))
        county = authority(brazos, "CR165 County")
        tax = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=county, name="County tax", kind="percent",
            rate=Decimal("0.020000"),
        )
        bind(brazos, plan, county)
        assert charged(rules_on(plan, OCT_15)) == Decimal("1.20")
        services.set_tax_active(dana, tax.id, False)
        tax.refresh_from_db()
        assert selectors.tax_in_force(tax, OCT_15) is False
        assert rules_on(plan, OCT_15) == []
        assert selectors.tax_status(tax) == "ended"


# ── DEF-RAT-9280 · two taxes of one authority both price ────────────────────
def test_9280_two_percent_taxes_of_one_authority_both_bill(brazos):
    """6.25% State sales tax + 2% State utility tax on $60.00 is **$3.75 +
    $1.20 = $4.95**. RED before the fix: `AmbiguousAuthorityTax`."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 two taxes", services=("water",))
        sales, state = a_state_sales_tax(brazos, plan)
        utility = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=state, name="State utility tax", kind="percent",
            rate=Decimal("0.020000"),
        )
        rules = rules_on(plan, OCT_15)
        assert sorted(rule["tax_id"] for rule in rules) == sorted([str(sales.id), str(utility.id)])
        # Two lines of one authority each name their own tax, never the authority twice.
        assert sorted(rule["code"] for rule in rules) == ["State sales tax", "State utility tax"]
        assert charged(rules) == Decimal("4.95")


def test_9280_two_versions_of_one_tax_on_one_date_still_refuse(brazos):
    """The refusal is kept for what it was always right about: two VERSIONS of
    ONE tax in force on one date (a broken chain; PostgreSQL refuses to store
    it, `ex_taxes_chain_no_overlap`)."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 broken chain", services=("water",))
        sales, state = a_state_sales_tax(brazos, plan)
        # A SAVEPOINT rolled back at the end: on PostgreSQL the broken chain is
        # refused at commit (`ex_taxes_chain_no_overlap`, deferred), and Django
        # checks deferred constraints when a test ends — the row must not
        # outlive the assertion it exists for.
        mark = transaction.savepoint()
        try:
            rating_models.Tax.objects.create(
                tenant=brazos, jurisdiction=state, name="State sales tax", kind="percent",
                rate=Decimal("0.065000"), effective_from=NOV_01, chain_id=sales.chain_id,
                version_no=2,
            )
            with pytest.raises(selectors.AmbiguousAuthorityTax):
                rules_on(plan, NOV_15)
        finally:
            transaction.savepoint_rollback(mark)


# ── DEF-RAT-9283 · new rate from a date ─────────────────────────────────────
def test_9283_new_rate_ends_v1_the_day_before_and_bills_one_row_per_date(brazos, dana):
    """Web walk 4.2 + 5.1/5.4/5.5 — 6.25% -> 6.5% from **11/01/2026**: v1 ends
    10/31/2026, v2 starts 11/01; the lookup returns ONE row on each side —
    $3.75 on 10/31, **$3.90** on 11/01 — and nothing is deleted."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 new rate", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan)
        created = services.new_tax_rate(
            dana, v1.id, {"rate": "0.065000", "effective_from": "2026-11-01"}
        )
        v1.refresh_from_db()
        v2 = rating_models.Tax.objects.get(pk=created["id"])
        assert v1.effective_to == OCT_31
        assert (v2.effective_from, v2.effective_to) == (NOV_01, None)
        assert (v1.version_no, v2.version_no) == (1, 2)
        assert v2.chain_id == v1.chain_id and v2.follows_id == v1.id
        assert v2.code == v1.code == "ST-SALES"  # every version shares its code
        assert created["ended_version"] == {
            "id": str(v1.id), "version": 1, "effective_to": "2026-10-31",
        }
        assert rating_models.Tax.objects.filter(chain_id=v1.chain_id).count() == 2

        for on, expected_id, tax in ((OCT_31, v1.id, "3.75"), (NOV_01, v2.id, "3.90"),
                                     (OCT_15, v1.id, "3.75"), (NOV_15, v2.id, "3.90")):
            rules = rules_on(plan, on)
            assert [rule["tax_id"] for rule in rules] == [str(expected_id)], on
            assert charged(rules) == Decimal(tax), on


def test_walk_new_rate_carries_what_is_taxed_discounts_and_rounding(brazos, dana):
    """Web walk 4.2 as drawn in image 28 — *New rate from a date* may also change
    WHAT IS TAXED, DISCOUNTS and ROUNDING for the new version. RED before the
    fix: `rating.unknown_field` on `base_includes_usage`. v1 keeps its own."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 new rate scope", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan, rounding_rule="half_up")
        created = services.new_tax_rate(
            dana,
            v1.id,
            {
                "rate": "0.065000",
                "effective_from": "2026-11-01",
                "base_includes_usage": False,
                "base_includes_base": True,
                "discount_treatment": "before",
                "rounding_rule": "half_even",
            },
        )
        v1.refresh_from_db()
        v2 = rating_models.Tax.objects.get(pk=created["id"])
        assert (v2.base_includes_usage, v2.base_includes_base) == (False, True)
        assert (v2.discount_treatment, v2.rounding_rule) == ("before", "half_even")
        # The version it follows is never rewritten beyond its end date.
        assert (v1.base_includes_usage, v1.discount_treatment, v1.rounding_rule) == (
            True, "after", "half_up",
        )
        with pytest.raises(errors.ValidationError):
            services.new_tax_rate(
                dana, v2.id, {"rate": "0.07", "effective_from": "2027-01-01",
                              "rounding_rule": "sideways"}
            )


def test_9283_a_new_rate_starting_before_the_live_version_is_refused_by_name(brazos, dana):
    """Web walk 4.4 — refused, by name, and nothing written."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 too early", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan)
        for too_early in ("2026-01-01", "2025-12-01"):
            with pytest.raises(errors.ValidationError) as refused:
                services.new_tax_rate(
                    dana, v1.id, {"rate": "0.065000", "effective_from": too_early}
                )
            assert refused.value.message_key == "rating.taxes.new_rate_too_early"
        v1.refresh_from_db()
        assert v1.effective_to is None
        assert rating_models.Tax.objects.filter(chain_id=v1.chain_id).count() == 1


def test_9283_header_reads_next_scheduled_rate_until_then(brazos, dana, monkeypatch):
    """*Next: 6.5% from 11/01/2026* on v1 while today is 10/03/2026; the list
    shows ONE row for the tax (v1), and `f.versions=all` shows both."""
    monkeypatch.setattr(selectors.seams, "tenant_today", lambda: date(2026, 10, 3))
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 scheduled", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan)
        services.new_tax_rate(dana, v1.id, {"rate": "0.065000", "effective_from": "2026-11-01"})
        row = selectors.tax_row(rating_models.Tax.objects.get(pk=v1.id))
        assert row["scheduled_next"] == {"rate_display": "6.50%", "effective_from": "2026-11-01"}
        assert row["version"] == 1 and row["status"] == "active"
        listed = [r for r in selectors.tax_list(ListParams(sort="name")) if r["code"] == "ST-SALES"]
        assert [r["version"] for r in listed] == [1]
        every = selectors.tax_list(ListParams(sort="name", filters={"versions": "all"}))
        assert sorted(r["version"] for r in every if r["code"] == "ST-SALES") == [1, 2]


# ── DEF-RAT-9282 · an attachment follows its tax across a new rate ──────────
def test_9282_an_attached_tax_keeps_billing_after_a_new_rate(brazos, dana):
    """Attached (not bound) 6.25% tax; new rate 6.5% from 11/01/2026. November's
    $60.00 bill carries **$3.90** — before the fix, **$0.00**."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 attached", services=("water",))
        state = authority(brazos, "CR165 Attached State")
        v1 = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=state, name="Attached sales tax", kind="percent",
            rate=Decimal("0.062500"), effective_from=date(2026, 1, 1),
        )
        attach(brazos, plan, v1)
        services.new_tax_rate(dana, v1.id, {"rate": "0.065000", "effective_from": "2026-11-01"})
        assert charged(rules_on(plan, OCT_15)) == Decimal("3.75")
        rules = rules_on(plan, NOV_15)
        assert len(rules) == 1
        assert charged(rules) == Decimal("3.90")


# ── DEF-RAT-9276 · a coded tax can be corrected; the superseded row never bills ─
def test_9276_correcting_a_coded_tax_keeps_its_code_and_bills_only_the_fix(brazos, dana):
    """Web walk 4.3 + 5.2 — 150% typed by mistake, fixed to 3% with a reason.
    The correction keeps the code (it was refused as a duplicate before) and the
    150% row is never returned again: $60.00 -> **$1.80**, not $90.00."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 fix", services=("water",))
        city = authority(brazos, "CR165 City")
        wrong = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=city, name="City franchise fee", code="CITY-FF",
            kind="percent", rate=Decimal("1.500000"),
        )
        bind(brazos, plan, city)
        assert charged(rules_on(plan, OCT_15)) == Decimal("90.00")
        fixed = services.correct_tax(dana, wrong.id, {"rate": "0.030000", "reason": "Typed as 150%"})
        wrong.refresh_from_db()
        assert fixed["code"] == "CITY-FF" and fixed["version"] == 2
        assert wrong.superseded_by_id is not None
        assert selectors.tax_status(wrong) == "superseded"
        for on in (OCT_15, NOV_15, date(2030, 1, 1)):
            rules = rules_on(plan, on)
            assert [rule["tax_id"] for rule in rules] == [fixed["id"]]
            assert charged(rules) == Decimal("1.80")


def test_9276_a_different_tax_may_not_take_the_code(brazos, dana):
    with tenant_ctx(brazos):
        state = authority(brazos, "CR165 Code State")
        services.create_tax(
            dana, {"name": "Coded", "kind": "percent", "rate": "0.01", "code": "ONE",
                   "jurisdiction": str(state.id)},
        )
        with pytest.raises(errors.ValidationError):
            services.create_tax(
                dana, {"name": "Other", "kind": "percent", "rate": "0.02", "code": "one",
                       "jurisdiction": str(state.id)},
            )


# ── Retire (CR §7 item 4) ───────────────────────────────────────────────────
def test_retire_ends_the_window_and_never_deactivates(brazos, dana):
    """Retire the 2% county tax on 12/31/2026: December still $1.20, January
    nothing. `deleted_at` stays empty."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 retire", services=("water",))
        county = authority(brazos, "CR165 Retire County")
        tax = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=county, name="County tax", kind="percent",
            rate=Decimal("0.020000"),
        )
        bind(brazos, plan, county)
        row = services.retire_tax(dana, tax.id, {"effective_to": "2026-12-31"})
        tax.refresh_from_db()
        assert row["effective_to"] == "2026-12-31" and tax.deleted_at is None
        assert charged(rules_on(plan, date(2026, 12, 15))) == Decimal("1.20")
        assert rules_on(plan, date(2027, 1, 15)) == []


def test_retire_refuses_while_a_later_version_is_scheduled(brazos, dana):
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 retire scheduled", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan)
        services.new_tax_rate(dana, v1.id, {"rate": "0.065000", "effective_from": "2026-11-01"})
        with pytest.raises(errors.BizError) as refused:
            services.retire_tax(dana, v1.id, {"effective_to": "2026-10-15"})
        assert refused.value.message_key == "rating.taxes.retire_scheduled_version"


# ── Filing due (CR §7 item 3) and the form's lists ──────────────────────────
@pytest.mark.parametrize(
    "frequency, rule, expected",
    [
        ("monthly", "20th_next_month", date(2026, 10, 20)),  # the contract's own example
        ("monthly", "15th_next_month", date(2026, 10, 15)),
        ("monthly", "last_day_next_month", date(2026, 10, 31)),
        ("quarterly", "30_days_after_quarter", date(2026, 10, 30)),
        ("annual", "jan_31_next_year", date(2026, 1, 31)),
        ("monthly", "20th of following month", None),  # legacy free text computes nothing
        (None, "20th_next_month", None),
    ],
)
def test_next_filing_due(frequency, rule, expected):
    assert selectors.next_filing_due(frequency, rule, today=date(2026, 10, 3)) == expected


def test_form_options_lists_only_boundaries_that_bill_today():
    options = selectors.tax_form_options()
    # PO 2026-10-03: "Only what works today" — and no place box anywhere.
    assert [(o["value"], o["needs_place"]) for o in options["boundaries"]] == [
        ("everywhere", False), ("city_limits", False),
    ]
    assert [o["value"] for o in options["due_rules"]] == [
        "15th_next_month", "20th_next_month", "25th_next_month",
        "last_day_next_month", "30_days_after_quarter", "jan_31_next_year",
    ]
    assert [o["value"] for o in options["bases"]] == [
        "percent", "flat_per_bill", "per_unit", "per_meter",
    ]
    assert [o["value"] for o in options["filing_frequencies"]] == [
        "monthly", "quarterly", "annual",
    ]


def test_due_date_rule_takes_a_code_and_everywhere_is_no_scope(brazos, dana):
    with tenant_ctx(brazos):
        made = services.create_tax(
            dana,
            {"name": "Coded rule", "kind": "percent", "rate": "0.01",
             "jurisdiction": {"name": "CR165 Rule State"}, "filing_frequency": "monthly",
             "due_date_rule": "20th_next_month", "premises_scope_kind": "everywhere"},
        )
        assert made["due_date_rule"] == "20th_next_month"
        assert made["premises_scope_kind"] is None
        with pytest.raises(errors.ValidationError):
            services.update_tax(dana, made["id"], {"due_date_rule": "whenever"})


# ── Authority accounts (CR §7 item 1) ───────────────────────────────────────
def test_authority_accounts_are_typed_once_and_picked_on_a_tax(brazos, dana):
    with tenant_ctx(brazos):
        made = services.create_authority_account(
            dana, {"authority_name": "TX Comptroller", "account_number": "32-1180455"}
        )
        assert made["active"] is True and made["jurisdiction_id"] is None
        with pytest.raises(errors.ValidationError):
            services.create_authority_account(
                dana, {"authority_name": "tx comptroller", "account_number": "32-1180455"}
            )
        tax = services.create_tax(
            dana,
            {"name": "With account", "kind": "percent", "rate": "0.01",
             "jurisdiction": {"name": "CR165 Account State"},
             "authority_account_id": made["id"]},
        )
        assert tax["authority_account"] == {
            "id": made["id"], "label": "TX Comptroller · 32-1180455",
        }
        retired = services.update_authority_account(dana, made["id"], {"active": False})
        assert retired["active"] is False
        # A retired account stays on the tax that filed under it…
        services.update_tax(dana, tax["id"], {"authority_account_id": made["id"]})
        # …and cannot be picked by a new one.
        with pytest.raises(errors.ValidationError):
            services.create_tax(
                dana,
                {"name": "Too late", "kind": "percent", "rate": "0.01",
                 "jurisdiction": {"name": "CR165 Account State 2"},
                 "authority_account_id": made["id"]},
            )
        rows, count = selectors.authority_account_page(ListParams(sort="authority_name"))
        assert count == 1 and rows[0]["account_number"] == "32-1180455"


# ── Plans tab: accounts beside units ────────────────────────────────────────
def test_plans_tab_serves_accounts_beside_units(brazos, dana):
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 plans tab", services=("water",))
        sales, _state = a_state_sales_tax(brazos, plan)
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="CR165-1")
        rating_models.UnitPlanAssignment.objects.create(
            tenant=brazos, unit_id=unit["id"], rate_plan=plan, plan_version=1,
            assigned_from=date(2026, 1, 1), assigned_to=None, source="import",
        )
        rows = selectors.tax_plans(sales.id)
        assert len(rows) == 1
        assert rows[0]["units"] == 1
        assert rows[0]["accounts"] == 0  # a vacant unit is a unit and not an account


def test_walk_plans_tab_count_is_the_plans_it_lists(brazos, dana):
    """Web walk 6.1/6.2 (`DEF-RAT-9304`): a plan that binds the tax's authority
    AND has the tax attached is ONE plan. The tab read *Plans 9* over a table
    of 7 plans. RED before the fix: `2 == 1`."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 bound and attached", services=("water",))
        sales, _state = a_state_sales_tax(brazos, plan)  # binds the authority
        attach(brazos, plan, sales)  # and attaches the tax too
        assert len(selectors.tax_plans(sales.id)) == 1
        assert selectors.tax_row(rating_models.Tax.objects.get(pk=sales.id))["used_by_plans"] == 1


# ── Audit: every change to the tax and its versions ─────────────────────────
def test_audit_reads_every_change_across_versions(brazos, dana):
    # The shared helpers capture audit rows in a list (`audit_rows`, autouse);
    # this case is about READING `audit_log`, so the platform's own sink writes
    # the rows to the table for the duration of the test.
    from apps.audit.services import store_row
    from core import audit as core_audit

    captured = core_audit._sink
    core_audit.set_audit_sink(store_row)
    try:
        _audit_case(brazos, dana)
    finally:
        core_audit.set_audit_sink(captured)


def _audit_case(brazos, dana):
    with tenant_ctx(brazos):
        made = services.create_tax(
            dana, {"name": "Audited", "kind": "percent", "rate": "0.0625",
                   "jurisdiction": {"name": "CR165 Audit State"}, "effective_from": "2026-01-01"},
        )
        services.update_tax(dana, made["id"], {"name": "Audited (renamed)"})
        services.new_tax_rate(
            dana, made["id"],
            {"rate": "0.065", "effective_from": "2026-11-01", "reason": "Statute 2026-44"},
        )
        tax = rating_models.Tax.objects.get(pk=made["id"])
        rows = list(selectors.seams.tax_audit_queryset(selectors.tax_chain_ids(tax)))
        actors = selectors.seams.audit_actor_payloads(rows)
        entries = [selectors.tax_audit_entry(row, actor) for row, actor in zip(rows, actors)]
        actions = [entry["action"] for entry in entries]
        assert {"tax.created", "tax.updated", "tax.ended_for_new_rate", "tax.new_rate_created"} <= set(actions)
        renamed = next(e for e in entries if e["action"] == "tax.updated")
        assert renamed["before"] == {"name": "Audited"}
        assert renamed["after"] == {"name": "Audited (renamed)"}
        new_rate = next(e for e in entries if e["action"] == "tax.new_rate_created")
        assert new_rate["reason"] == "Statute 2026-44"
        for entry in entries:
            assert entry["actor"] is not None


# ── DEF-RAT-9275 · as_draft reaches the server ──────────────────────────────
def test_9275_as_draft_saves_a_draft_that_does_not_price(brazos, dana):
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.rating import api as rating_api

    request = APIRequestFactory().post(
        "/api/brazosbend/taxes",
        {"name": "Half-way", "kind": "percent", "rate": "0.01", "as_draft": True,
         "jurisdiction": {"name": "CR165 Draft City"}},
        format="json",
    )
    force_authenticate(request, user=dana.user)
    request.tenant_role = "system_admin"
    request.tenant_id = brazos.id
    with tenant_ctx(brazos):
        response = rating_api.taxes(request)
        assert response.status_code == 201, response.data
        tax = rating_models.Tax.objects.get(pk=response.data["id"])
        assert tax.is_draft is True
        assert selectors.tax_in_force(tax, OCT_15) is False
        assert response.data["status"] == "draft"


# ── PO 2026-10-03 on CR-008 — the liability account after creation ──────────
def test_liability_account_is_picked_at_creation_and_changed_only_in_settings(brazos, dana):
    """*"Pick it when you create the tax; change it later only in Settings -a
    llow it"*. RED before the fix: `PATCH /taxes/{id}` accepted it on a live
    tax (no error raised)."""
    from apps.ledger import services as ledger_services

    with tenant_ctx(brazos):
        first = ledger_services.create_tax_authority_account(
            code="2200-31", name="Tax payable — CR165 A", actor=dana
        )
        second = ledger_services.create_tax_authority_account(
            code="2200-32", name="Tax payable — CR165 B", actor=dana
        )
        made = services.create_tax(
            dana,
            {"name": "Liability at birth", "kind": "percent", "rate": "0.01",
             "jurisdiction": {"name": "CR165 Liability State"},
             "liability_gl_account_id": str(first.id)},
        )
        assert made["liability_gl_account_id"] == str(first.id)
        with pytest.raises(errors.BizError) as refused:
            services.update_tax(dana, made["id"], {"liability_gl_account_id": str(second.id)})
        assert refused.value.message_key == "rating.taxes.liability_edit_in_settings"
        moved = services.set_tax_liability_account(
            dana, made["id"], {"liability_gl_account_id": str(second.id)}
        )
        assert moved["liability_gl_account_id"] == str(second.id)


# ── The list's Over 20% banner (CR-165 §9, list lane) ───────────────────────
def test_over_20_count_and_filter_cover_the_whole_filtered_set(brazos, dana, monkeypatch):
    """150% counts until it is corrected; a 2% tax never counts; an ENDED 150%
    row does not count; `f.status=ended` is the contract's word."""
    monkeypatch.setattr(selectors.seams, "tenant_today", lambda: date(2026, 10, 3))
    with tenant_ctx(brazos):
        city = authority(brazos, "CR165 Over20 City")
        typo = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=city, name="Over twenty", kind="percent",
            rate=Decimal("1.500000"),
        )
        rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=city, name="Two percent", kind="percent",
            rate=Decimal("0.020000"),
        )
        rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=city, name="Old and ended", kind="percent",
            rate=Decimal("0.500000"), effective_to=date(2026, 1, 31),
        )
        params = ListParams(sort="name", per=1)
        assert selectors.tax_over_20_count(params) == 1
        over = ListParams(sort="name", filters={"over_20": "1"})
        assert [row["name"] for row in selectors.tax_list(over)] == ["Over twenty"]
        ended = ListParams(sort="name", filters={"status": "ended"})
        assert [row["name"] for row in selectors.tax_list(ended)] == ["Old and ended"]
        assert selectors.tax_over_20_count(ended) == 0
        services.correct_tax(dana, typo.id, {"rate": "0.030000", "reason": "Typed as 150%"})
        assert selectors.tax_over_20_count(params) == 0
