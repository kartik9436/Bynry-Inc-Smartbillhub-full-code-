# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-008 (Charge codes tab + New Charge Code S12 + plan
#           attachment rules) · US-RAT-009 (Taxes & fees tab + New Tax/Fee S13
#           with tenant-entered jurisdictions + plan tax rules)
# Rules:    BR-RAT-005 (fees/late never in the tax base) · BR-RAT-025 (D7/D8
#           catalog + plan attachment) · BR-RAT-035 (charge-code identity +
#           IS-1 audit-lock) · BR-RAT-036 (tax forms; only usage/base are
#           selectable) · BR-RAT-041 (Formula visible but disabled) ·
#           BR-RAT-042 (marginal per-unit threshold) · BR-TEN-037 (tenant-
#           entered jurisdictions)
# Note:     US-RAT-009 TC-7 is implemented per the STATUS AUTHORITY register:
#           BR-RAT-042 (OQ-054 CLOSED) rules the threshold MARGINAL and
#           buildable, while the EP-RAT-03 story table still says "save blocked
#           pending OQ-054". The contradiction is REPORTED, not resolved here.
# ───────────────────────────────────────────────────────
"""US-RAT-008 / US-RAT-009 — the charge-code and tax/fee catalogs."""

from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from core import errors
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import audit_actions, tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db


def _params(sort, **kwargs):
    return ListParams(**{"sort": sort, "dir": "asc", **kwargs})


def _seed_charges(env):
    """The §4 Brazos Bend catalog rows the list TCs assert (amounts are SEEDS,
    never constants — BR-RAT-035/B4 §NSF)."""
    env.charge("BASE-E", "Electric base charge", charge_type="recurring", amount="18.50")
    env.charge("CONN", "Connection fee", amount="85.00", gl_account_id=None)
    env.charge("DISC", "Disconnect fee", amount="45.00")
    env.charge("DEPO-R", "Residential deposit", charge_type="refundable", amount="150.00")
    env.charge(
        "LATE",
        "Late payment fee",
        charge_type="penalty",
        amount_rule="percent_with_minimum",
        amount=None,
        percent="0.015",
        min_amount="5.00",
    )
    env.charge("NSF", "Returned payment (NSF) fee", charge_type="penalty", amount="30.00")


# ── US-RAT-008 — charge codes ───────────────────────────────────────────────
def test_us_rat_008_tc1__catalog_lists_code_asc_with_percent_min_rendering(env):
    _seed_charges(env)
    with tenant_ctx(env.tenant):
        rows = selectors.charge_list(_params("code"))
    assert [row["code"] for row in rows] == [
        "BASE-E",
        "CONN",
        "DEPO-R",
        "DISC",
        "LATE",
        "NSF",
    ]
    late = next(row for row in rows if row["code"] == "LATE")
    assert (late["amount_rule"], late["percent"], late["min_amount"]) == (
        "percent_with_minimum",
        "0.015000",
        "5.000000",
    )


def test_us_rat_008_tc2__creating_a_penalty_code_writes_the_row_and_audit(env, audit_rows):
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {
                "code": "TAMPER",
                "name": "Meter tampering",
                "charge_type": "penalty",
                "amount_rule": "flat",
                "amount": "250.00",
                "taxable_default": False,
                "waivable": True,
             "effective_from": "2000-01-01"},
        )
    assert (charge["code"], charge["amount"], charge["status"]) == (
        "TAMPER",
        "250.000000",
        "active",
    )
    assert charge["waivable"] is True and charge["service"] is None  # scope Any (r6.6 NULL)
    assert "charge.created" in audit_actions(audit_rows)


def test_us_rat_008_tc3__percent_with_minimum_stores_a_fraction_and_a_floor(env):
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {
                "code": "LATE",
                "name": "Late payment fee",
                "charge_type": "penalty",
                "amount_rule": "percent_with_minimum",
                "percent": "0.015",
                "min_amount": "5.00",
             "effective_from": "2000-01-01"},
        )
    assert Decimal(charge["percent"]) == Decimal("0.015")  # 1.5 % as a fraction
    assert Decimal(charge["min_amount"]) == Decimal("5.00")


def test_us_rat_008_tc4__plan_attachment_carries_an_amount_override(env):
    """AMENDED 2026-08-21 by BR-RAT-094 (PO ruling, DEF-411 option B).

    This TC used to raise CONN from the catalogue's $85.00 to $95.00 on the
    plan, which is a PLAN SETTING A PRICE — forbidden by CR-013 part 5 and now
    refused by the server. What BR-RAT-043 defends, and all this TC ever needed
    to prove, is that the override is a per-plan figure distinct from the
    catalogue amount. So the figure moves to the discount side of zero: the
    plan takes $10.00 OFF the $85.00 connection fee, the catalogue is still
    $85.00, and the raise is asserted refused in the same test.
    """
    env.charge("CONN", "Connection fee", amount="85.00")
    plan = env.plan(
        "Small Commercial",
        "COM-SM",
        [{"service": "electric", "base_charge": "36.00"}],
        charge_rules=[{"charge": "CONN", "amount_override": "-10.00", "recurrence": "once"}],
    )
    rule = plan["charge_rules"][0]
    assert (rule["code"], rule["amount_override"], rule["recurrence"]) == (
        "CONN",
        "-10.000000",
        "once",
    )
    with tenant_ctx(env.tenant):
        catalog = selectors.charge_list(_params("code"))
    assert next(row for row in catalog if row["code"] == "CONN")["amount"] == "85.000000"
    # BR-RAT-094: the same field, above zero, is the refusal this TC lost.
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError):
        env.plan(
            "Small Commercial Raised",
            "COM-SM-UP",
            [{"service": "electric", "base_charge": "36.00"}],
            charge_rules=[{"charge": "CONN", "amount_override": "95.00", "recurrence": "once"}],
        )


def test_us_rat_008_tc5__duplicate_code_is_rejected(env):
    env.charge("CONN", "Connection fee", amount="85.00")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_charge(
                env.admin,
                {"code": "CONN", "name": "Second", "amount_rule": "flat", "amount": "10.00", "effective_from": "2000-01-01"},
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.duplicate_code"


def test_us_rat_008_tc6__negative_amount_is_refused(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_charge(
                env.admin,
                {"code": "NEG", "name": "Negative", "amount_rule": "flat", "amount": "-85", "effective_from": "2000-01-01"},
            )
    assert excinfo.value.code == errors.VAL_RANGE  # discounts are plan-side (BR-RAT-043)


def test_us_rat_008_tc7__deactivate_allowed_but_delete_is_audit_locked(env, audit_rows):
    charge = env.charge("DEPO-R", "Residential deposit", charge_type="refundable", amount="150.00")
    env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "electric", "base_charge": "18.50"}],
        charge_rules=[{"charge": "DEPO-R", "recurrence": "once"}],
    )
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        deactivated = services.set_charge_active(env.admin, charge["id"], False)
        with pytest.raises(errors.BizError) as excinfo:
            services.delete_charge(env.admin, charge["id"])
        assert models.Charge.objects.filter(pk=charge["id"]).exists()
    assert deactivated["status"] == "inactive"
    assert "charge.deactivated" in audit_actions(audit_rows)
    assert excinfo.value.code == errors.BIZ_LOCKED and excinfo.value.params["plans"] == 1


def test_us_rat_008_tc8__the_formula_amount_rule_is_disabled(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_charge(
                env.admin,
                {"code": "FORM", "name": "Formula fee", "amount_rule": "formula", "effective_from": "2000-01-01"},
            )
        assert models.Charge.objects.filter(code="FORM").exists() is False
    assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.formula_disabled"


def test_us_rat_008_tc9__the_same_code_coexists_in_two_tenants(env, other_env):
    env.charge("CONN", "Connection fee", amount="85.00")
    other_env.charge("CONN", "Connection fee", amount="60.00")
    with tenant_ctx(other_env.tenant):
        rows = selectors.charge_list(_params("code"))
    assert [(row["code"], row["amount"]) for row in rows] == [("CONN", "60.000000")]


@pytest.mark.isolation
@requires_postgres
def test_us_rat_008_tc9_rls__charge_catalog_is_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-008 TC-9 at the DATABASE, app-layer filter out of the path.

    The app half proves the same CODE can mean $85.00 to one utility and $60.00
    to another. That shared code is exactly what makes a lost tenant filter
    invisible in a list — the rows look plausible. Only the policy stops the
    AMOUNT crossing, so the amount is what is asserted.
    """
    mine = env.charge("CONN", "Connection fee", amount="85.00")
    theirs = other_env.charge("CONN", "Connection fee", amount="60.00")

    assert_rls_scoped(
        rls, "charges", owner=env.tenant, intruder=other_env.tenant, owner_ids={str(mine["id"])}
    )
    # ⚠ `DEF-RAT-9028` — THE PRICE LIVES IN `charge_code_amounts` SINCE
    # CR-156-BRC10 wave A (2026-10-01): a flat amount is an *All sizes* row and
    # `charges.amount` is retired (NULL). So that table's policy is what keeps
    # $85.00 from crossing, and it is the one asserted.
    assert_rls_scoped(
        rls,
        "charge_code_amounts",
        owner=env.tenant,
        intruder=other_env.tenant,
    )
    with live_tenant_context(other_env.tenant.id):
        assert rls.ids("charges") == {str(theirs["id"])}
        # Compared as money, not as text: the new column is NUMERIC(18,4)
        # (hard rule 2), the retired one was (18,6).
        amounts = {
            Decimal(str(row[0]))
            for row in rls.rows(
                "SELECT a.amount FROM charge_code_amounts a "
                "JOIN charges c ON c.id = a.charge_id WHERE c.code = 'CONN'"
            )
        }
    assert amounts == {Decimal("60.00")}, f"LEAK — the intruder read another tenant's price: {amounts}"
    assert_write_into_other_tenant_refused(
        rls, "charges", owner=env.tenant, intruder=other_env.tenant
    )
    assert_denied_without_context(rls, "charges")


# ── US-RAT-009 — taxes & fees ───────────────────────────────────────────────
def _seed_taxes(env):
    env.tax(
        "TX State Utility Tax",
        jurisdiction={
            "name": "Texas Comptroller",
            "authority": "Texas Comptroller",
            "level": "state",
        },
        kind="percent",
        rate="0.0625",
        filing_frequency="monthly",
    )
    env.tax(
        "Local · Fort Bend County",
        jurisdiction={
            "name": "Fort Bend County",
            "authority": "Fort Bend County",
            "level": "county",
        },
        kind="percent",
        rate="0.0200",
        filing_frequency="monthly",
    )
    env.tax(
        "PUC Regulatory Fee",
        jurisdiction={"name": "TX PUC", "authority": "TX PUC", "level": "state"},
        kind="flat_per_bill",
        rate=None,
        flat_amount="0.85",
        flat_frequency="per_bill",
        applies_to_services=["electric"],
        filing_frequency="quarterly",
    )
    env.tax(
        "Water Conservation Surcharge",
        jurisdiction={"name": "TWDB", "authority": "TWDB", "level": "special_district"},
        kind="per_unit",
        rate=None,
        per_unit_amount="0.25",
        per_unit_uom="kgal",
        applies_to_services=["water"],
        filing_frequency="annual",
    )


def test_us_rat_009_tc1__tab_lists_every_tax_with_rate_and_remittance(env):
    _seed_taxes(env)
    with tenant_ctx(env.tenant):
        rows = selectors.tax_list(_params("name"))
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {
        "TX State Utility Tax",
        "Local · Fort Bend County",
        "PUC Regulatory Fee",
        "Water Conservation Surcharge",
    }
    assert by_name["TX State Utility Tax"]["rate"] == "0.062500"
    assert by_name["PUC Regulatory Fee"]["flat_amount"] == "0.850000"
    assert by_name["Water Conservation Surcharge"]["per_unit_uom"] == "kgal"
    assert by_name["Water Conservation Surcharge"]["filing_frequency"] == "annual"


def test_us_rat_009_tc2__creating_a_city_fee_writes_tax_and_jurisdiction(env, audit_rows):
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        tax = services.create_tax(
            env.admin,
            {
                "name": "City Franchise Fee",
                "jurisdiction": {
                    "name": "City of Katy",
                    "authority": "City of Katy",
                    "level": "city",
                },
                "kind": "percent",
                "rate": "0.0150",
                "applies_to_services": ["electric"],
                "base_includes_usage": True,
                "base_includes_base": True,
                "remit_to": "City of Katy",
                "filing_frequency": "quarterly",
                "effective_from": "2026-09-01",
            },
        )
    assert tax["jurisdiction"]["level"] == "city"
    assert tax["effective_from"] == "2026-09-01"
    actions = audit_actions(audit_rows)
    assert "tax_jurisdiction.created" in actions and "tax.created" in actions


def test_us_rat_009_tc3__the_taxable_base_can_only_express_usage_and_base(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_tax(
                env.admin,
                {
                    "name": "Illegal base",
                    "jurisdiction": {"name": "Somewhere", "level": "city"},
                    "kind": "percent",
                    "rate": "0.02",
                    "base_includes_fees": True,  # B4.2 wins over the prototype checkbox
                },
            )
    assert excinfo.value.field_errors[0]["field"] == "base_includes_fees"
    assert excinfo.value.field_errors[0]["message_key"] == "rating.unknown_field"


def test_us_rat_009_tc4__plan_tax_rules_carry_the_override(env):
    state = env.tax("TX State Utility Tax", rate="0.0625")
    county = env.tax(
        "Local · Fort Bend County",
        jurisdiction={"name": "Fort Bend County", "level": "county"},
        rate="0.0200",
    )
    standard = env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "electric", "base_charge": "18.50"}],
        tax_rules=[
            {"jurisdiction": state["jurisdiction"]["id"]},
            {"jurisdiction": county["jurisdiction"]["id"]},
        ],
    )
    assert len(standard["tax_rules"]) == 2
    assert [rule["rate_override"] for rule in standard["tax_rules"]] == [None, None]
    # AMENDED 2026-08-21 by BR-RAT-094 (PO ruling, DEF-411 option B). This TC
    # used to build a `Senior` plan carrying `rate_override: "0.00"` on the TX
    # state tax — a plan zeroing a state tax, which is the exact case the PO
    # named: "Nobody has ever defended letting a plan skip a state tax." The
    # field is gone from the accepted set, so the attempt is now the assertion.
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError):
        env.plan(
            "Senior",
            "SENIOR",
            [{"service": "electric", "base_charge": "18.50"}],
            tax_rules=[{"jurisdiction": state["jurisdiction"]["id"], "rate_override": "0.00"}],
        )


def test_us_rat_009_tc5__a_negative_or_missing_percent_rate_is_refused(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as negative:
            services.create_tax(
                env.admin,
                {
                    "name": "Negative",
                    "jurisdiction": {"name": "Somewhere", "level": "city"},
                    "kind": "percent",
                    "rate": "-2",
                },
            )
        with pytest.raises(errors.ValidationError) as blank:
            services.create_tax(
                env.admin,
                {
                    "name": "Blank",
                    "jurisdiction": {"name": "Somewhere", "level": "city"},
                    "kind": "percent",
                },
            )
    assert negative.value.code == errors.VAL_RANGE
    assert blank.value.field_errors[0]["field"] == "rate"


def test_us_rat_009_tc6__the_same_jurisdiction_twice_on_one_plan_is_rejected(env):
    state = env.tax("TX State Utility Tax", rate="0.0625")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(
                env.admin,
                {
                    "name": "Double taxed",
                    "code": "DBL",
                    "services": [{"service": "electric", "base_charge": "18.50"}],
                    "tax_rules": [
                        {"jurisdiction": state["jurisdiction"]["id"]},
                        {"jurisdiction": state["jurisdiction"]["id"]},
                    ],
                },
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.plans.duplicate_jurisdiction"


def test_us_rat_009_tc7__per_unit_threshold_saves_as_marginal_per_br_rat_042(env):
    # STATUS AUTHORITY: BR-RAT-042 (OQ-054 CLOSED) rules the threshold MARGINAL
    # and buildable; the EP-RAT-03 TC still says "blocked pending OQ-054" —
    # contradiction REPORTED, implemented per the BR register.
    with tenant_ctx(env.tenant):
        tax = services.create_tax(
            env.admin,
            {
                "name": "Water Conservation Surcharge",
                "jurisdiction": {"name": "TWDB", "level": "special_district"},
                "kind": "per_unit",
                "per_unit_amount": "0.25",
                "per_unit_uom": "kgal",
                "applies_above_units": "10",
                "applies_to_services": ["water"],
            },
        )
    assert tax["applies_above_units"] == "10.000000"
    assert tax["per_unit_amount"] == "0.250000"


def test_us_rat_009_tc8__jurisdiction_lists_never_leak_across_tenants(env, other_env):
    env.tax("TX State Utility Tax", rate="0.0625")
    other_env.tax(
        "Hays County", jurisdiction={"name": "Hays County", "level": "county"}, rate="0.0050"
    )
    with tenant_ctx(other_env.tenant):
        jurisdictions = selectors.jurisdiction_list()
    assert [row["name"] for row in jurisdictions] == ["Hays County"]  # BR-TEN-037


@pytest.mark.isolation
@requires_postgres
def test_us_rat_009_tc8_rls__jurisdictions_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-009 TC-8 at the DATABASE (r16 #2 made `tax_jurisdictions` tenant-scoped).

    Both tables are asserted, not just the jurisdiction: `taxes` carries the
    RATE, and a rate is what a tax authority is eventually owed against.
    """
    env.tax("TX State Utility Tax", rate="0.0625")
    other_env.tax(
        "Hays County", jurisdiction={"name": "Hays County", "level": "county"}, rate="0.0050"
    )

    for table in ("tax_jurisdictions", "taxes"):
        assert_rls_scoped(rls, table, owner=env.tenant, intruder=other_env.tenant)
    with live_tenant_context(other_env.tenant.id):
        names = {row[0] for row in rls.rows("SELECT name FROM tax_jurisdictions")}
    assert names == {"Hays County"}, f"LEAK — the intruder read jurisdictions {names}"
    assert_no_foreign_rows_anywhere(rls, other_env.tenant, ("tax_jurisdictions", "taxes"))
    assert_denied_without_context(rls, "tax_jurisdictions", "taxes")


# ── Reference-data cards (S8) — the /lookups handlers rating owns ───────────
# BR-TEN-031: tenancy renders + routes, rating validates + writes. Both list
# codes were declared in tenancy's registry with NO handler, so the two cards
# could not render at all; these TCs exercise them THROUGH the framework's own
# service layer, which is where the BR-TEN-030/034 locks live.
def test_us_ten_009_tc1__the_two_rating_cards_now_render_with_live_counts(env):
    from apps.tenancy import selectors as tenancy_selectors

    _seed_charges(env)
    env.tax("TX State Utility Tax", jurisdiction={"name": "Texas Comptroller"})
    with tenant_ctx(env.tenant):
        cards = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
    # BR-TEN-029: counts computed live at render, never cached.
    # DEF-336 added `state` — the report's own word for this list, so the screen
    # can say WHY a card has no number instead of drawing a bare chevron.
    assert cards["charge_codes"] == {
        "list": "charge_codes",
        "owner": "rating",
        "count": 6,
        "state": "seeded",
    }
    assert cards["tax_jurisdictions"]["count"] == 1


def test_us_rat_008_tc10__the_charge_code_card_lists_adds_and_refuses_duplicates(env):
    from apps.tenancy import selectors as tenancy_selectors
    from apps.tenancy import services as tenancy_services

    _seed_charges(env)
    with tenant_ctx(env.tenant):
        rows = tenancy_selectors.lookup_page("charge_codes", None)
        assert [row["code"] for row in rows] == [
            "BASE-E",
            "CONN",
            "DEPO-R",
            "DISC",
            "LATE",
            "NSF",
        ]
        assert rows[0]["active"] is True and rows[0]["used_by"] == 0
        assert rows[0]["is_system"] is False  # no such column — REPORTED, not faked
        # IS-3 server-side search, min 2 chars.
        assert len(tenancy_selectors.lookup_page("charge_codes", "fee")) == 4
        # BR-TEN-036: the tenant may EXTEND the list.
        added = tenancy_services.create_lookup_entry(
            env.admin, "charge_codes", {"code": "GATE", "name": "Gate remote fee"}
        )
        assert added["code"] == "GATE" and added["used_by"] == 0
        # The money fields stay with S12 — the card is not a back door into them.
        stored = models.Charge.objects.get(pk=added["id"])
        assert _flat(stored) is None and stored.amount_rule is None
        with pytest.raises(errors.ValidationError) as unknown_field:
            tenancy_services.create_lookup_entry(
                env.admin, "charge_codes", {"code": "X", "name": "X", "amount": "45.00"}
            )
        assert unknown_field.value.field_errors[0]["field"] == "amount"
        # BR-TEN-030: codes are unique per tenant, case-insensitively.
        with pytest.raises(errors.ValidationError) as duplicate:
            tenancy_services.create_lookup_entry(
                env.admin, "charge_codes", {"code": "conn", "name": "Second connection fee"}
            )
        assert duplicate.value.field_errors[0]["field"] == "code"
        assert duplicate.value.field_errors[0]["params"]["existing"] == "CONN"


def test_us_ten_011_tc4__a_used_charge_code_is_locked_and_its_code_frozen(env, audit_rows):
    """BR-TEN-034 audit-lock + BR-TEN-030 code immutability, both enforced by
    tenancy from the used-by count this handler supplies (BR-RAT-035's own
    inputs: plan attachments + invoice lines)."""
    from apps.tenancy import services as tenancy_services

    env.charge("DEPO-R", "Residential deposit", charge_type="refundable", amount="150.00")
    unused = env.charge("TAMPER", "Tamper fee", amount="75.00")
    env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "electric", "base_charge": "18.50"}],
        charge_rules=[{"charge": "DEPO-R", "recurrence": "once"}],
    )
    with tenant_ctx(env.tenant):
        used = next(
            row for row in tenancy_selectors_lookup_page("charge_codes") if row["code"] == "DEPO-R"
        )
        assert used["used_by"] == 1
        with pytest.raises(errors.BizError) as locked:
            tenancy_services.delete_lookup_entry(env.admin, "charge_codes", used["id"])
        assert locked.value.code == errors.BIZ_LOCKED
        assert locked.value.br_ref == "BR-TEN-034"
        with pytest.raises(errors.BizError) as frozen:
            tenancy_services.update_lookup_entry(
                env.admin, "charge_codes", used["id"], {"code": "DEPOSIT-R"}
            )
        assert frozen.value.br_ref == "BR-TEN-030"
        # The NAME stays editable while the code is frozen, and deactivation is
        # always allowed (BR-TEN-029/IS-1).
        renamed = tenancy_services.update_lookup_entry(
            env.admin, "charge_codes", used["id"], {"name": "Residential deposit (refundable)"}
        )
        assert renamed["name"] == "Residential deposit (refundable)"
        deactivated = tenancy_services.set_lookup_entry_active(
            env.admin, "charge_codes", used["id"], False
        )
        assert deactivated["active"] is False
        # An UNREFERENCED tenant row deletes freely (Used-by = 0).
        tenancy_services.delete_lookup_entry(env.admin, "charge_codes", unused["id"])
        assert models.Charge.objects.filter(pk=unused["id"]).exists() is False
    assert "settings.lookup.deleted" in audit_actions(audit_rows)


def test_us_rat_009_tc9__the_jurisdiction_card_lists_adds_and_refuses_duplicates(env):
    from apps.tenancy import services as tenancy_services

    env.tax(
        "TX State Utility Tax",
        jurisdiction={
            "name": "Texas Comptroller",
            "authority": "Texas Comptroller",
            "level": "state",
        },
    )
    with tenant_ctx(env.tenant):
        (row,) = tenancy_selectors_lookup_page("tax_jurisdictions")
        # No `code` column exists on tax_jurisdictions — the NAME is this list's
        # identity and fills the framework's code slot (REPORTED, not invented).
        assert row["code"] == row["name"] == "Texas Comptroller"
        assert row["level"] == "state" and row["used_by"] == 1
        assert row["is_system"] is False
        # BR-TEN-037: tenant-entered — the tenant adds its own authorities.
        added = tenancy_services.create_lookup_entry(
            env.admin, "tax_jurisdictions", {"code": "Katy City", "name": "Katy City"}
        )
        assert added["used_by"] == 0
        with pytest.raises(errors.ValidationError) as duplicate:
            tenancy_services.create_lookup_entry(
                env.admin, "tax_jurisdictions", {"code": "katy city", "name": "katy city"}
            )
        assert duplicate.value.field_errors[0]["params"]["existing"] == "Katy City"
        # S13's own fields are refused here — the card must not half-fill a
        # tax authority (US-RAT-009 owns authority/level/reference_no).
        with pytest.raises(errors.ValidationError) as unknown_field:
            tenancy_services.create_lookup_entry(
                env.admin,
                "tax_jurisdictions",
                {"code": "Harris County", "name": "Harris County", "level": "county"},
            )
        assert unknown_field.value.field_errors[0]["field"] == "level"


def test_us_ten_011_tc5__a_referenced_jurisdiction_is_locked_and_deactivation_has_no_storage(env):
    """BR-TEN-034 bites (a referenced authority cannot be deleted), and the
    deactivate half REFUSES loudly: `tax_jurisdictions` has no active column, so
    accepting the click would record nothing — the gap is reported, not faked."""
    from apps.tenancy import services as tenancy_services

    env.tax("TX State Utility Tax", jurisdiction={"name": "Texas Comptroller"})
    with tenant_ctx(env.tenant):
        (used,) = tenancy_selectors_lookup_page("tax_jurisdictions")
        with pytest.raises(errors.BizError) as locked:
            tenancy_services.delete_lookup_entry(env.admin, "tax_jurisdictions", used["id"])
        assert locked.value.code == errors.BIZ_LOCKED
        assert locked.value.params["used_by"] == 1
        with pytest.raises(errors.BizError) as no_storage:
            tenancy_services.set_lookup_entry_active(
                env.admin, "tax_jurisdictions", used["id"], False
            )
        assert no_storage.value.code == errors.BIZ_STATE
        assert no_storage.value.br_ref == "BR-TEN-029"
        assert no_storage.value.message_key == "rating.lookups.deactivate_unsupported"
        # An unreferenced authority deletes freely.
        spare = tenancy_services.create_lookup_entry(
            env.admin, "tax_jurisdictions", {"code": "Spare Authority", "name": "Spare Authority"}
        )
        tenancy_services.delete_lookup_entry(env.admin, "tax_jurisdictions", spare["id"])
        assert models.TaxJurisdiction.objects.filter(pk=spare["id"]).exists() is False


def test_us_ten_010_tc7__rating_card_rows_live_independently_per_tenant(env, other_env):
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(env.tenant):
        tenancy_services.create_lookup_entry(
            env.admin, "charge_codes", {"code": "GATE", "name": "Gate remote fee"}
        )
        tenancy_services.create_lookup_entry(
            env.admin, "tax_jurisdictions", {"code": "Katy City", "name": "Katy City"}
        )
    with tenant_ctx(other_env.tenant):
        assert tenancy_selectors_lookup_page("charge_codes") == []
        assert tenancy_selectors_lookup_page("tax_jurisdictions") == []
        # The same code, independently owned — no cross-tenant collision.
        mine = tenancy_services.create_lookup_entry(
            other_env.admin, "charge_codes", {"code": "GATE", "name": "Our gate fee"}
        )
        assert mine["code"] == "GATE"


@pytest.mark.isolation
@requires_postgres
def test_us_rat_008_tc10_rls__rating_lookup_cards_are_rls_scoped(  # noqa: F811
    env, other_env, rls
):
    """US-TEN-010 TC-7's RLS half: the S8 reference-data cards write into RATING's
    own tables (`charges`, `tax_jurisdictions`) through the tenancy lookup seam.

    The seam is why this case exists separately from TC-9 above: the SAME rows
    are reachable by a second write path, and a lookup selector that lost its
    tenant filter would leak them just as a rating selector would.
    """
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(env.tenant):
        mine_code = tenancy_services.create_lookup_entry(
            env.admin, "charge_codes", {"code": "GATE", "name": "Gate remote fee"}
        )
        mine_juris = tenancy_services.create_lookup_entry(
            env.admin, "tax_jurisdictions", {"code": "Katy City", "name": "Katy City"}
        )
    with tenant_ctx(other_env.tenant):
        tenancy_services.create_lookup_entry(
            other_env.admin, "charge_codes", {"code": "GATE", "name": "Our gate fee"}
        )
        tenancy_services.create_lookup_entry(
            other_env.admin, "tax_jurisdictions", {"code": "Buda City", "name": "Buda City"}
        )

    assert_rls_scoped(
        rls,
        "charges",
        owner=env.tenant,
        intruder=other_env.tenant,
        owner_ids={str(mine_code["id"])},
    )
    assert_rls_scoped(
        rls,
        "tax_jurisdictions",
        owner=env.tenant,
        intruder=other_env.tenant,
        owner_ids={str(mine_juris["id"])},
    )
    with live_tenant_context(other_env.tenant.id):
        names = {row[0] for row in rls.rows("SELECT name FROM charges")}
    assert "Gate remote fee" not in names, f"LEAK — the intruder read {names}"


def tenancy_selectors_lookup_page(list_code, q=None):
    """Small local shim so each TC reads as one line (tenancy's selector is the
    framework's read path — BR-TEN-031)."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.lookup_page(list_code, q)


# ── BR-RAT-108 · a charge code prices one customer class ───────────────────


def test_br_rat_103__silver_creeks_two_water_bases_can_finally_be_expressed(env):
    """The case that forced the column (DEF-467).

    Water base is `$8.00` on Sample — Residential and `$15.00` on Sample —
    Commercial: ONE service, TWO amounts. A charge code is per TENANT where the
    plan column it replaces was per PLAN, so before this there was no way to
    state both. `resolution.ChargeCode.customer_classes` had expected it since
    R4 was written and had no column behind it — the rule read as implementable
    because the ENGINE could express it and the TABLE could not.
    """
    with tenant_ctx(env.tenant):
        residential = services.create_charge(
            env.admin,
            {
                "code": "BASE-W-RES", "name": "Water base · residential",
                "amount_rule": "flat", "amount": "8.00", "is_base": True,
                "applies_to_customer_classes": ["residential"],
             "effective_from": "2000-01-01"},
        )
        commercial = services.create_charge(
            env.admin,
            {
                "code": "BASE-W-COM", "name": "Water base · commercial",
                "amount_rule": "flat", "amount": "15.00", "is_base": True,
                "applies_to_customer_classes": ["commercial"],
             "effective_from": "2000-01-01"},
        )
    assert residential["applies_to_customer_classes"] == ["residential"]
    assert commercial["applies_to_customer_classes"] == ["commercial"]


def test_br_rat_103__an_unstated_list_means_EVERY_class_and_that_is_what_exists_today(env):
    """NULL/[] = no restriction, which is what every row already means — so the
    column is additive and no existing charge code changes behaviour."""
    with tenant_ctx(env.tenant):
        row = services.create_charge(
            env.admin,
            {"code": "LATE", "name": "Late fee", "amount_rule": "flat", "amount": "15.00", "effective_from": "2000-01-01"},
        )
    assert row["applies_to_customer_classes"] == []


def test_br_rat_103__a_TYPOD_class_is_refused_and_never_dropped(env):
    """DEF-273's reason, and it is sharper on a base charge than on a tax.

    A silently-dropped `"residental"` would leave a base the utility believes is
    restricted applying to EVERYBODY — and a base charge is on every bill, not
    an edge case. The refusal names the index so a human can find it.
    """
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_charge(
            env.admin,
            {
                "code": "BASE-X", "name": "Typo", "amount_rule": "flat", "amount": "8.00",
                "applies_to_customer_classes": ["residental"],
             "effective_from": "2000-01-01"},
        )
    fields = [error["field"] for error in raised.value.field_errors]
    assert "applies_to_customer_classes[0]" in fields


def test_br_rat_103__the_charge_and_the_tax_answer_the_class_question_identically(env):
    """One rule, one validator. The 25-line block used to live only inside the
    tax validator; two copies is how the two objects end up disagreeing about
    what a valid customer class is."""
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as charge_error:
        services.create_charge(
            env.admin,
            {
                "code": "BASE-Y", "name": "Typo", "amount_rule": "flat", "amount": "8.00",
                "applies_to_customer_classes": ["nonsense"],
             "effective_from": "2000-01-01"},
        )
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as tax_error:
        services.create_tax(
            env.admin,
            {
                "name": "Typo tax", "kind": "percent", "rate": "0.01",
                "applies_to_customer_classes": ["nonsense"],
            },
        )
    assert (
        charge_error.value.field_errors[0]["message_key"]
        == tax_error.value.field_errors[0]["message_key"]
    )
