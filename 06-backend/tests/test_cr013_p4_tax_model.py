# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-009 (Taxes & fees + TAX-02) — CR-013 part 4's data model.
#           DEF-385 (nine specified fields, no column) · DEF-382 (discount
#           treatment is statutory and per tax) · DEF-387 (two statuses where
#           four are named) · DEF-383 (an exemption is a category with a
#           certificate and an expiry) · DEF-380 (nothing counts the premises a
#           scope matches) · DEF-384 (an in-force tax cannot be corrected) ·
#           DEF-483 (the effective window is stored and never read)
#           Screens: S13 · TAX-01 landing · TAX-02 steps 1–4
# Rules:    BR-RAT-006 (exemption is account-level) · BR-RAT-036 (four
#           computation forms) · BR-RAT-037 (rate history is append-only) ·
#           BR-RAT-092 / OQ-286 (percent is six places, amount is four) ·
#           BR-TEN-043 (today is the tenant's) · CLAUDE.md hard rule 2 (money is
#           NUMERIC, never float) · hard rule 4 (financial immutability) ·
#           hard rule 7 (every money action audits) · hard-won law 3 (defaults
#           fail closed)
# Golden:   NONE MOVES — 33/33 before and after. Every added column is nullable
#           or defaults to the behaviour the engine already had, and the two
#           gates added to `plan_tax_rules` are the identity on every row that
#           exists (all undated, none draft, none superseded). Asserted below.
# Tests:    this file
# Impacts:  apps/rating/models.{Tax,TaxExemptionCategory,TaxExemptionCertificate}
#           · apps/rating/selectors.{tax_status,tax_in_force,matched_premises,
#           account_holds_exemption,taxable_subtotal_for,plan_tax_rules}
#           · apps/rating/services.{create_tax,update_tax,activate_tax,
#           correct_tax,create_exemption_category,record_exemption_certificate}
#           · apps/rating/seams.{premises_geography_rows,account_exists}
#           · apps/billing/gather._taxes_for
# ───────────────────────────────────────────────────────
"""CR-013 part 4's tax model — the six defects Wave D closes, in money.

**EVERY FIGURE HERE IS A WORKED DOLLAR AMOUNT ON A $100.00 BILL**, following
`test_def_273_tax_conditions.py`, and for its reason: a test that asserts "a
rule was returned" passes just as happily when the rule is the wrong one, and
what these changes exist to prevent is a customer being charged money they do
not owe — or not being charged money they do.

── PROVED RED FIRST (hard-won law 7), and here is what each one printed ──────

* **DEF-483** (`test_def467_*`) — the window gate. At HEAD, a tax dated
  `effective_from = today + 1 year` still produced a rule and the bill carried
  it:

      AssertionError: assert {'Tax Texas State': Decimal('6.25')} == {}

  and the expired case the same way. `plan_tax_rules` had NO date predicate at
  all, while its docstring claimed *"taxes carries no effective-dating columns,
  so there is nothing to filter on"*.

* **DEF-387** (`test_def387_*`) — `AssertionError: assert 'active' == 'draft'`
  and `assert 'active' == 'scheduled'`; `tax_row` derived status from
  `deleted_at` alone, so all four words were one word.

* **DEF-385** (`test_def385_*`) —
  `ValidationError: [{'field': 'code', 'code': 'VAL-006' …}]`: every one of the
  fields part 4 asks TAX-02 to collect was rejected by `_reject_unknown` as an
  unknown key.

* **DEF-382** (`test_def382_*`) —
  `AttributeError: module 'apps.rating.selectors' has no attribute
  'taxable_subtotal_for'`, and the column itself
  `TypeError: Tax() got unexpected keyword arguments: 'discount_treatment'`.

* **DEF-383** (`test_def383_*`) —
  `AttributeError: module 'apps.rating.models' has no attribute
  'TaxExemptionCategory'`.

* **DEF-380** (`test_def380_*`) —
  `AttributeError: module 'apps.rating.selectors' has no attribute
  'matched_premises'`.

* **DEF-384** (`test_def384_*`) — the refusal did not exist server-side:
  `PATCH` of a live tax's rate returned 200 and the rate changed in place.
  `AttributeError: module 'apps.rating.services' has no attribute 'correct_tax'`.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: A bill whose taxable base is EXACTLY $100.00 — see the DEF-273 file, same
#: shape and the same reason: every tax figure reads as its own percentage.
HUNDRED = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("100.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")
INSIDE_CITY = {"city": "San Antonio", "state": "TX", "postal_code": "78205"}


#: ⚠ EVERY JURISDICTION IN THIS FILE IS PREFIXED, AND THAT IS NOT COSMETIC.
#: The `brazos` fixture ALREADY provisions two of the PO's five ruled Texas rows
#: — `TX State Utility Tax` at 6.25 % under *Texas State* and `Local · Bexar
#: County` at 2.00 % under *Local* — because `_seed_fixture_taxes` runs at
#: provisioning (DEF-254). A helper that reached for an existing jurisdiction by
#: name would hang this file's rows off the SEEDED authority, and
#: `_authority_tax` picks the oldest row per authority, so every assertion here
#: would silently measure the seeded rate instead of the one the test set up.
#:
#: That is exactly how it failed the first time it ran: a tax dated a year into
#: the future still billed `$6.25`, which looked like the window gate not
#: working and was the seeded row answering. A test that measures the wrong row
#: is worse than no test — it reports on something nobody is changing.
WD = "WD · "


def a_tax(tenant, jurisdiction_name, **fields):
    """One `taxes` row on a jurisdiction OF ITS OWN — never a shared one."""
    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant=tenant, name=f"{WD}{jurisdiction_name}"
    )
    return (
        rating_models.Tax.objects.create(tenant=tenant, jurisdiction=jurisdiction, **fields),
        jurisdiction,
    )


def attach(tenant, plan, jurisdiction):
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def bill(rules):
    return rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=None if rule.get("rate") is None else Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
                flat_amount=(
                    None if rule.get("flat_amount") is None else Decimal(str(rule["flat_amount"]))
                ),
            )
            for rule in rules
        ),
    )


def tax_amounts(priced):
    return {line.description: line.amount for line in priced.lines_of("tax")}


def today_of(tenant):
    from apps.rating import seams as rating_seams

    with tenant_ctx(tenant):
        return rating_seams.tenant_today()


# ══════════════════════════════════════════════════════════════════════════
# DEF-483 · the effective window is stored and was never read
# ══════════════════════════════════════════════════════════════════════════
def test_def467_a_scheduled_tax_charges_nothing_until_its_statutory_date(brazos, dana):
    """A rate that starts NEXT YEAR must not be on THIS MONTH'S bill.

    RED AT HEAD: the same setup produced
    `{'Tax Texas State': Decimal('6.25')}` — six dollars twenty-five of a tax no
    authority has levied yet — because `plan_tax_rules` resolved by jurisdiction
    and kind with no date predicate. This is CR-013 part 4 step 4's *"Save &
    schedule (future statutory date, shows as Scheduled)"* being a real thing
    rather than a word on a screen.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _tax, jurisdiction = a_tax(
            brazos,
            "Texas State",
            name="TX State Utility Tax",
            kind="percent",
            rate=Decimal("0.062500"),
            effective_from=today + timedelta(days=365),
        )
        attach(brazos, plan, jurisdiction)
        # Asked ON TODAY: not yet in force.
        now_rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        # Asked on a service date INSIDE the window: in force, and $6.25.
        later_rules = selectors.plan_tax_rules(
            plan.id,
            today + timedelta(days=400),
            customer_class="commercial",
            premises=INSIDE_CITY,
            services=("electric",),
        )

    assert now_rules == []  # THE RED FIGURE WAS 6.25
    assert tax_amounts(bill(now_rules)) == {}
    assert bill(now_rules).total == Decimal("100.00")
    assert tax_amounts(bill(later_rules)) == {f"Tax {WD}Texas State": Decimal("6.25")}


def test_def467_an_expired_tax_stops_charging_and_an_undated_one_never_does(brazos, dana):
    """The other end of the window — and the proof that NO EXISTING ROW MOVES.

    The second half is the one that keeps golden at 33/33: every tax this
    product has ever stored is UNDATED, and a NULL bound means *no bound
    stated*, not a bound of zero. If that were wrong, every seeded rate would
    have stopped billing on this commit.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _expired, expired_jurisdiction = a_tax(
            brazos,
            "Old City",
            name="Repealed City Fee",
            kind="percent",
            rate=Decimal("0.015000"),
            effective_from=today - timedelta(days=800),
            effective_to=today - timedelta(days=30),
        )
        attach(brazos, plan, expired_jurisdiction)
        expired_rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )

        undated_plan = make_plan(brazos, name="Undated Standard")
        _undated, undated_jurisdiction = a_tax(
            brazos,
            "Bexar County",
            name="Local · Bexar County",
            kind="percent",
            rate=Decimal("0.020000"),
        )
        attach(brazos, undated_plan, undated_jurisdiction)
        undated_rules = selectors.plan_tax_rules(
            undated_plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )

    assert expired_rules == []  # THE RED FIGURE WAS 1.50, for ever
    assert tax_amounts(bill(expired_rules)) == {}
    # ⚠ THE NO-REGRESSION HALF. An undated row is in force exactly as it was.
    assert tax_amounts(bill(undated_rules)) == {f"Tax {WD}Bexar County": Decimal("2.00")}


def test_def467_the_flat_form_is_gated_by_the_same_window(brazos, dana):
    """Two lookups, one rule. A gate on only the percent half looks green for a
    year — the PUC fee is `$0.85 FLAT PER BILL` and it must obey the same date.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _fee, jurisdiction = a_tax(
            brazos,
            "Texas PUC",
            name="PUC Regulatory Fee",
            kind="flat_per_bill",
            flat_amount=Decimal("0.85"),
            effective_from=today + timedelta(days=90),
        )
        attach(brazos, plan, jurisdiction)
        rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        in_window = selectors.plan_tax_rules(
            plan.id,
            today + timedelta(days=120),
            customer_class="commercial",
            premises=INSIDE_CITY,
            services=("electric",),
        )
    assert tax_amounts(bill(rules)) == {}  # THE RED FIGURE WAS 0.85
    assert tax_amounts(bill(in_window)) == {"Tax PUC Regulatory Fee": Decimal("0.85")}


# ══════════════════════════════════════════════════════════════════════════
# DEF-387 · four statuses, derived, and the one fact that cannot be
# ══════════════════════════════════════════════════════════════════════════
def test_def387_the_four_statuses_are_derived_from_stored_facts(brazos, dana):
    """Active / Draft / Scheduled / Expired — CR-013 part 4's landing column.

    RED AT HEAD: every one of these read `"active"`, because `tax_row` answered
    `"inactive" if deleted_at else "active"` and ignored both dates.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        live, _ = a_tax(brazos, "A", name="Live", kind="percent", rate=Decimal("0.01"))
        draft, _ = a_tax(
            brazos, "B", name="Draft", kind="percent", rate=Decimal("0.01"), is_draft=True
        )
        scheduled, _ = a_tax(
            brazos,
            "C",
            name="Scheduled",
            kind="percent",
            rate=Decimal("0.01"),
            effective_from=today + timedelta(days=10),
        )
        expired, _ = a_tax(
            brazos,
            "D",
            name="Expired",
            kind="percent",
            rate=Decimal("0.01"),
            effective_to=today - timedelta(days=1),
        )
        assert selectors.tax_status(live) == "active"
        assert selectors.tax_status(draft) == "draft"
        assert selectors.tax_status(scheduled) == "scheduled"
        # CR-165-BRC10 round 2 (§9 contract): `expired` reads `ended`.
        assert selectors.tax_status(expired) == "ended"

        # The FIFTH value, which part 4 does not name and the product already
        # had: IS-1's deactivate-first. `schedule_state` adds `archived` beyond
        # its own ratified set for exactly the same reason.
        live.deleted_at = expired.created_at
        live.save(update_fields=["deleted_at"])
        # CR-165 §9 — a deactivated row prices nothing (`DEF-RAT-9279`), so it
        # reads `ended`; the separate `active` flag still says it was deactivated.
        assert selectors.tax_status(live) == "ended"


def test_def387_a_draft_defaults_to_false_so_no_existing_row_becomes_one(brazos, dana):
    """⚠ THE GUARD ON THE MISTAKE THIS COLUMN ALMOST SHIPPED WITH.

    The first design made draft-ness a NULLABLE `activated_at` backfilled on
    migration. Every path that creates a tax without going through `create_tax`
    — the fixture seeder, the sample-data seeder, every test — would have minted
    a silent DRAFT that never prices, and the ruled Texas rates would have
    stopped charging on the next tenant provisioned.

    So this asserts the DEFAULT, in money: a row created the way the seeder
    creates one is in force and bills `$6.25`. Hard-won law 3 — the unsafe
    option must be the one you type.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        seeded, jurisdiction = a_tax(
            brazos,
            "Texas State",
            name="TX State Utility Tax",
            kind="percent",
            rate=Decimal("0.062500"),
        )
        attach(brazos, plan, jurisdiction)
        rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        assert seeded.is_draft is False
        # INSIDE the tenant context: `tax_in_force` with no date reads the
        # TENANT's today (BR-TEN-043), and tenancy refuses to answer that
        # outside a resolved tenant rather than falling back to a server clock.
        assert selectors.tax_in_force(seeded) is True
    assert tax_amounts(bill(rules)) == {f"Tax {WD}Texas State": Decimal("6.25")}


def test_def387_a_draft_prices_nothing_and_activating_it_puts_it_in_force(brazos, dana):
    """Part 4 step 4's *Draft* then *Activate* — one save plus a date."""
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name=f"{WD}Texas State"
        )
        created = services.create_tax(
            dana,
            {
                "name": "TX State Utility Tax",
                "kind": "percent",
                "rate": "0.062500",
                "jurisdiction": str(jurisdiction.id),
            },
            as_draft=True,
        )
        attach(brazos, plan, jurisdiction)
        assert created["status"] == "draft"
        assert created["in_force"] is False
        drafted = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        activated = services.activate_tax(dana, created["id"])
        live = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        # Activating twice is refused, not silently ignored: it is the only
        # signal that the row is not the draft the caller thought it was.
        with pytest.raises(errors.BizError) as excinfo:
            services.activate_tax(dana, created["id"])

    assert tax_amounts(bill(drafted)) == {}
    assert activated["status"] == "active"
    assert tax_amounts(bill(live)) == {f"Tax {WD}Texas State": Decimal("6.25")}
    assert excinfo.value.code == errors.BIZ_STATE


def test_def387_save_and_schedule_is_one_save_plus_a_date(brazos, dana):
    """*"Save & schedule (future statutory date, shows as Scheduled)"* — and it
    is not a third code path, because it is not a third act."""
    today = today_of(brazos)
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(tenant=brazos, name=f"{WD}City")
        created = services.create_tax(
            dana,
            {
                "name": "City Franchise Fee",
                "kind": "percent",
                "rate": "0.015000",
                "jurisdiction": str(jurisdiction.id),
            },
            as_draft=True,
        )
        scheduled = services.activate_tax(
            dana, created["id"], (today + timedelta(days=45)).isoformat()
        )
    assert scheduled["status"] == "scheduled"
    assert scheduled["in_force"] is False
    assert scheduled["effective_from"] == (today + timedelta(days=45)).isoformat()


def test_def387_the_status_filter_reads_the_derived_word(brazos, dana):
    """The landing's Status filter. It moved out of the queryset when the value
    stopped being a synonym for `deleted_at IS NULL` — a derived value cannot be
    filtered in SQL without a second implementation of the derivation."""
    today = today_of(brazos)
    with tenant_ctx(brazos):
        a_tax(brazos, "A", name="WD Live", kind="percent", rate=Decimal("0.01"))
        a_tax(brazos, "B", name="WD Draft", kind="percent", rate=Decimal("0.01"), is_draft=True)
        a_tax(
            brazos,
            "C",
            name="WD Scheduled",
            kind="percent",
            rate=Decimal("0.01"),
            effective_from=today + timedelta(days=10),
        )
        from core.pagination import ListParams

        def names(status):
            rows = selectors.tax_list(
                ListParams(
                    page=1,
                    per=50,
                    sort="name",
                    dir="asc",
                    q="",
                    filters={"status": status},
                )
            )
            # Narrowed to this file's own rows: the `brazos` fixture seeds two
            # of the PO's ruled Texas rates at provisioning and both are ACTIVE,
            # which is correct and is not what this test is measuring.
            return sorted(row["name"] for row in rows if row["name"].startswith("WD "))

        assert names("active") == ["WD Live"]
        assert names("draft") == ["WD Draft"]
        assert names("scheduled") == ["WD Scheduled"]


# ══════════════════════════════════════════════════════════════════════════
# DEF-385 · the fields TAX-02 is specified to collect
# ══════════════════════════════════════════════════════════════════════════
def test_def385_every_specified_field_round_trips(brazos, dana):
    """RED AT HEAD: each of these keys was refused by `_reject_unknown` as an
    unknown field, which is why TAX-02 rendered them as named absences rather
    than controls — *"a control that posts a key the server refuses as unknown
    is worse than no control."*

    ⚠ THE COLLECTION ALLOWANCE IS THE ONE THAT COSTS MONEY, so it is asserted as
    a figure: `0.005000` is Texas' 0.5 % timely-filing discount, and on
    `$2,400.00` of tax remitted in a quarter that is **$12.00** the utility is
    entitled to keep and was previously remitting away with no way to record it.
    """
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name=f"{WD}Texas State", authority="Texas Comptroller"
        )
        row = services.create_tax(
            dana,
            {
                "name": "TX State Utility Tax",
                "kind": "percent",
                "rate": "0.062500",
                "jurisdiction": str(jurisdiction.id),
                "code": "sales-tx",
                "bill_label": "State utility tax",
                "tax_type": "sales_tax",
                "rounding_rule": "half_up",
                # CR-165 §7 item 3 — a CODE now (`selectors.DUE_DATE_RULES`).
                "due_date_rule": "20th_next_month",
                "remit_method": "portal",
                "remit_reference": "1-74-1234567-8",
                "collection_allowance_percent": "0.005000",
                "interest_penalty_percent": "0.015000",
                "interest_penalty_basis": "monthly",
                "filing_reminder_recipient": "bookkeeper@example.test",
            },
        )
    # Uppercased on the way in, like every other tenant code in this product.
    assert row["code"] == "SALES-TX"
    assert row["bill_label"] == "State utility tax"
    assert row["tax_type"] == "sales_tax"
    assert row["rounding_rule"] == "half_up"
    assert row["due_date_rule"] == "20th_next_month"
    assert row["remit_method"] == "portal"
    assert row["remit_reference"] == "1-74-1234567-8"
    assert row["collection_allowance_percent"] == "0.005000"
    assert row["interest_penalty_percent"] == "0.015000"
    assert row["interest_penalty_basis"] == "monthly"
    assert row["filing_reminder_recipient"] == "bookkeeper@example.test"
    # BR-RAT-092 / OQ-286: a percent stored as a FRACTION keeps SIX places, so
    # 0.5 % does not truncate to 0.0050 and lose its meaning at the fourth digit.
    assert Decimal(row["collection_allowance_percent"]).as_tuple().exponent == -6


def test_def385_an_interest_rate_without_its_period_is_refused(brazos, dana):
    """`1.5%` monthly read as annual is TWELVE TIMES too small. A rate without
    its period is not a rate — the same reasoning hard rule 3 applies to
    consumption — so it is refused rather than defaulted to a guess."""
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(tenant=brazos, name=f"{WD}A")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_tax(
                dana,
                {
                    "name": "Fee",
                    "kind": "percent",
                    "rate": "0.01",
                    "jurisdiction": str(jurisdiction.id),
                    "interest_penalty_percent": "0.015000",
                },
            )
    assert any(fe["field"] == "interest_penalty_basis" for fe in excinfo.value.field_errors)


def test_def385_a_tax_code_is_unique_per_tenant_and_case_insensitive(brazos, dana):
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(tenant=brazos, name=f"{WD}A")
        services.create_tax(
            dana,
            {
                "name": "One",
                "kind": "percent",
                "rate": "0.01",
                "jurisdiction": str(jurisdiction.id),
                "code": "SALES-TX",
            },
        )
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_tax(
                dana,
                {
                    "name": "Two",
                    "kind": "percent",
                    "rate": "0.02",
                    "jurisdiction": str(jurisdiction.id),
                    "code": "sales-tx",
                },
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.taxes.duplicate_code"


# ══════════════════════════════════════════════════════════════════════════
# DEF-382 · discount treatment is statutory and per authority
# ══════════════════════════════════════════════════════════════════════════
def test_def382_the_two_directions_give_two_different_totals(brazos, dana):
    """⚠ THE ONLY PROOF THAT THE COLUMN IS BEING READ IS THAT THE TWO TOTALS
    DIFFER, which is what DEF-382's own suggested fix asks for.

    **The worked pair, and it is the one `resolution.py` already carries in its
    docstring:** a `$1.00` PAPERLESS credit on a Bexar County bill leaves the
    county's 2 % line at **`$3.78`** under `before` (the authority levies on the
    reduced subtotal) and at **`$3.80`** under `after` (the discount never
    reaches the tax base). Two cents, per bill, per authority.

    RED AT HEAD: `taxable_subtotal_for` did not exist and the product had ONE
    behaviour, so there was no second figure to compare against.
    """
    subtotal_before = Decimal("190.00")
    subtotal_after = Decimal("189.00")  # a $1.00 PAPERLESS credit
    rate = Decimal("0.02")

    before_base = selectors.taxable_subtotal_for("before", subtotal_before, subtotal_after)
    after_base = selectors.taxable_subtotal_for("after", subtotal_before, subtotal_after)

    assert before_base == subtotal_after
    assert after_base == subtotal_before
    assert (before_base * rate).quantize(Decimal("0.01")) == Decimal("3.78")
    assert (after_base * rate).quantize(Decimal("0.01")) == Decimal("3.80")
    # THE FIGURES ARE DIFFERENT. That difference IS the test.
    assert (after_base * rate).quantize(Decimal("0.01")) != (
        before_base * rate
    ).quantize(Decimal("0.01"))


def test_def382_the_default_is_the_ruled_answer_and_a_null_seam_still_is_not(brazos, dana):
    """⚠ AMENDED 2026-08-28 (DEF-652). This used to be
    `test_def382_the_default_is_todays_behaviour_so_no_figure_moves` and it
    asserted `before` — correct on 2026-08-21, when the column was new and the
    question it stands for was unanswered.

    The PO answered it on 2026-08-27: *"Tax the full amount before discount —
    The utility remits tax on the full service value; the discount is the
    utility's cost, not the tax authority's."* That is `after`, and a $62.14
    bill with a $15.54 senior discount moves from $3.19 of tax to $4.26.

    **The second half of this test is UNCHANGED and that is the point.** A NULL
    or an unknown value reaching `taxable_subtotal_for` is not a row's answer —
    no row can hold one, the column is NOT NULL — it is a SEAM that published
    nothing. A wiring gap keeps behaving exactly as it always has; only the
    stored answer moved.
    """
    with tenant_ctx(brazos):
        tax, _ = a_tax(brazos, "Bexar County", name="Local", kind="percent", rate=Decimal("0.02"))
    assert tax.discount_treatment == "after"
    assert selectors.taxable_subtotal_for(None, Decimal("190"), Decimal("189")) == Decimal("189")
    assert selectors.taxable_subtotal_for("", Decimal("190"), Decimal("189")) == Decimal("189")


def test_def382_only_the_two_statutory_answers_are_accepted(brazos, dana):
    with tenant_ctx(brazos):
        jurisdiction = rating_models.TaxJurisdiction.objects.create(tenant=brazos, name=f"{WD}A")
        with pytest.raises(errors.ValidationError):
            services.create_tax(
                dana,
                {
                    "name": "Fee",
                    "kind": "percent",
                    "rate": "0.01",
                    "jurisdiction": str(jurisdiction.id),
                    "discount_treatment": "sometimes",
                },
            )
        stored = services.create_tax(
            dana,
            {
                "name": "Statutory After",
                "kind": "percent",
                "rate": "0.01",
                "jurisdiction": str(jurisdiction.id),
                "discount_treatment": "after",
            },
        )
    assert stored["discount_treatment"] == "after"


# ══════════════════════════════════════════════════════════════════════════
# DEF-383 · an exemption is a category with a certificate and an expiry
# ══════════════════════════════════════════════════════════════════════════
def test_def383_a_live_certificate_removes_one_authoritys_tax_and_no_others(
    brazos, dana, account_factory=None
):
    """⚠ THE DISTINCTION THE MODEL DOCSTRING WARNS ABOUT, IN MONEY.

    A church holding a religious exemption against the 6.25 % STATE tax still
    pays the city's 1.50 % franchise fee, because a city is not a state and its
    statute is its own. Collapsing this into `applies_to_customer_classes` — or
    into `accounts.tax_exempt`, which is BLANKET — would silently widen every
    exemption a utility records to every authority it remits to.

    On a $100.00 bill: **$1.50, not $7.75.**
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        state_tax, state_jurisdiction = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        _city, city_jurisdiction = a_tax(
            brazos, "City", name="City Franchise Fee", kind="percent", rate=Decimal("0.015000")
        )
        attach(brazos, plan, state_jurisdiction)
        attach(brazos, plan, city_jurisdiction)

        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=state_tax, code="RELIGIOUS", name="Religious organisation"
        )
        account_id = "11111111-1111-1111-1111-111111111111"
        rating_models.TaxExemptionCertificate.objects.create(
            tenant=brazos,
            category=category,
            account_id=account_id,
            certificate_ref="TX-501C3-9912",
            expires_on=today + timedelta(days=365),
        )
        exempt_rules = selectors.plan_tax_rules(
            plan.id,
            today,
            customer_class="commercial",
            premises=INSIDE_CITY,
            services=("electric",),
            account_id=account_id,
        )
        ordinary_rules = selectors.plan_tax_rules(
            plan.id,
            today,
            customer_class="commercial",
            premises=INSIDE_CITY,
            services=("electric",),
            account_id="22222222-2222-2222-2222-222222222222",
        )

    assert tax_amounts(bill(exempt_rules)) == {f"Tax {WD}City": Decimal("1.50")}
    assert bill(exempt_rules).tax_total == Decimal("1.50")
    assert tax_amounts(bill(ordinary_rules)) == {
        f"Tax {WD}City": Decimal("1.50"),
        f"Tax {WD}Texas State": Decimal("6.25"),
    }
    assert bill(ordinary_rules).tax_total == Decimal("7.75")


def test_def383_an_expired_certificate_reinstates_the_tax_with_no_exception(brazos, dana):
    """⚠ THE RULE THAT IS THE OPPOSITE OF THIS PRODUCT'S USUAL POSTURE, AND IT
    IS DELIBERATE. CR-013 part 4, shared rules, verbatim: *"Expired exemption
    certificates reinstate the tax on the next run with no exception raised —
    it's expected behaviour."*

    Everywhere else a bill run STOPS and names what changed underneath it. Here
    it must not: an expiry is a date passing, not a fault, and a utility with two
    staff cannot triage an exception queue that refills every January. This test
    exists because somebody will otherwise "fix" it into an exception.

    The account pays `$0.00` while the certificate is live and **`$6.25`** on the
    first run after it expires — and `plan_tax_rules` raises NOTHING either time.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        state_tax, jurisdiction = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        attach(brazos, plan, jurisdiction)
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=state_tax, code="RELIGIOUS", name="Religious organisation"
        )
        account_id = "11111111-1111-1111-1111-111111111111"
        certificate = rating_models.TaxExemptionCertificate.objects.create(
            tenant=brazos,
            category=category,
            account_id=account_id,
            certificate_ref="TX-501C3-9912",
            expires_on=today + timedelta(days=1),
        )
        while_live = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",), account_id=account_id,
        )
        certificate.expires_on = today - timedelta(days=1)
        certificate.save(update_fields=["expires_on"])
        # NO try/except HERE ON PURPOSE — if this ever raises, the test fails,
        # which is exactly what the rule asks for.
        after_expiry = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",), account_id=account_id,
        )
        assert selectors.exemption_certificate_row(certificate)["state"] == "expired"

    assert tax_amounts(bill(while_live)) == {}
    assert tax_amounts(bill(after_expiry)) == {f"Tax {WD}Texas State": Decimal("6.25")}


def test_def383_a_certificate_with_no_expiry_is_permanent_not_expired(brazos, dana):
    """NULL is *does not expire*, not *unknown*: a municipality does not renew
    being a municipality, and forcing a date would have made somebody invent one.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        tax, _ = a_tax(brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.0625"))
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=tax, code="GOVT", name="Government body"
        )
        account_id = "33333333-3333-3333-3333-333333333333"
        rating_models.TaxExemptionCertificate.objects.create(
            tenant=brazos, category=category, account_id=account_id, expires_on=None
        )
        assert selectors.account_holds_exemption(tax, account_id, today) is True
        assert (
            selectors.account_holds_exemption(tax, account_id, today + timedelta(days=36500))
            is True
        )


def test_def383_a_revoked_certificate_stops_exempting_immediately(brazos, dana):
    """An authority that disallows a claim does not wait for the paper to run
    out — and the row is REVOKED, never deleted, so the utility can show WHEN it
    stopped honouring it."""
    today = today_of(brazos)
    with tenant_ctx(brazos):
        tax, _ = a_tax(brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.0625"))
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=tax, code="RELIGIOUS", name="Religious organisation"
        )
        account_id = "11111111-1111-1111-1111-111111111111"
        certificate = rating_models.TaxExemptionCertificate.objects.create(
            tenant=brazos,
            category=category,
            account_id=account_id,
            expires_on=today + timedelta(days=365),
        )
        assert selectors.account_holds_exemption(tax, account_id, today) is True
        services.revoke_exemption_certificate(dana, str(certificate.id))
        assert selectors.account_holds_exemption(tax, account_id, today) is False
        assert rating_models.TaxExemptionCertificate.objects.filter(pk=certificate.id).exists()


def test_def383_an_absent_account_id_means_the_tax_applies(brazos, dana):
    """⚠ THIS GATE OPENS WHERE THE OTHER THREE CLOSE, AND THAT IS DELIBERATE.

    The class, service and premises gates are RESTRICTIONS STATED ON THE TAX, so
    one that cannot be evaluated must close (DEF-273's fail-safe). An exemption
    is a CLAIM MADE BY A CUSTOMER, and a claim nobody has made is not an
    exemption — reading *"I could not check"* as *"exempt"* would zero the tax on
    every bill for every account the moment a caller forgot the argument.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        tax, jurisdiction = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        attach(brazos, plan, jurisdiction)
        rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=tax, code="RELIGIOUS", name="Religious organisation"
        )
        rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
    assert tax_amounts(bill(rules)) == {f"Tax {WD}Texas State": Decimal("6.25")}


def test_def383_a_category_requiring_a_certificate_refuses_a_claim_without_one(brazos, dana):
    """A category that requires a certificate and holds claims with no reference
    is a list of customers the utility cannot defend to an authority."""
    with tenant_ctx(brazos):
        tax, _ = a_tax(brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.0625"))
        category = services.create_exemption_category(
            dana,
            str(tax.id),
            {
                "code": "religious",
                "name": "Religious organisation",
                "requires_certificate": True,
                "certificate_requirement": "Proof of 501(c)(3)",
            },
        )
        assert category["code"] == "RELIGIOUS"
        with pytest.raises(errors.ValidationError) as excinfo:
            services.record_exemption_certificate(
                dana,
                category["id"],
                {"account_id": "11111111-1111-1111-1111-111111111111"},
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.taxes.certificate_required"


# ══════════════════════════════════════════════════════════════════════════
# DEF-380 · the matched premise count
# ══════════════════════════════════════════════════════════════════════════
def test_def380_the_count_runs_the_engines_own_predicate(brazos, dana, premises_factory=None):
    """CR-013 part 4 step 1: *"Shows the matched premise count so a wrong
    boundary is visible before rates are entered."*

    ⚠ THE COUNT IS COMPUTED BY `premises_in_scope` — the SAME function
    `plan_tax_rules` calls to decide whether a real bill attracts the tax. A
    count computed from a WHERE clause would be a second implementation of one
    rule, and a safeguard that can disagree with the thing it safeguards is
    worse than no safeguard.

    RED AT HEAD: `selectors.matched_premises` did not exist and no handler in
    `apps/rating/api.py` counted premises against a scope, so TAX-02 stated the
    absence by name and rendered no digit at all.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        for index, (city, inside) in enumerate(
            [("San Antonio", True), ("San Antonio", True), ("Helotes", False), ("Helotes", None)]
        ):
            metering_models.Premises.objects.create(
                tenant=brazos,
                premise_no=f"P-{index:03d}",
                address_line=f"{index} Main St",
                city=city,
                state="TX",
                inside_city_limits=inside,
            )
        inside_city = selectors.matched_premises("city_limits", "San Antonio")
        everywhere = selectors.matched_premises(None, None)
        county = selectors.matched_premises("county", "Bexar")

    # BR-RAT-101's flag WINS over the recorded city name where it is set: two
    # premises are flagged inside, one flagged outside, and one whose flag
    # nobody recorded falls back to the city name and does not match.
    assert inside_city["count"] == 2
    assert inside_city["total"] == 4
    assert inside_city["resolvable"] is True
    assert [line["premise_no"] for line in inside_city["sample"]] == ["P-000", "P-001"]

    # No scope stated = everywhere, said explicitly rather than as a number that
    # happens to equal the total for a reason nobody can see.
    assert everywhere["count"] == 4 and everywhere["everywhere"] is True

    # ⚠ `county` HAS NO FACT TO RESOLVE AGAINST, so the honest count is 0 of 4 —
    # a TRUE statement about the product and a MISLEADING one about the
    # utility's boundary. `resolvable: False` is what lets TAX-02 say which.
    assert county["count"] == 0 and county["resolvable"] is False


# ══════════════════════════════════════════════════════════════════════════
# DEF-384 · an in-force tax cannot be corrected at all
# ══════════════════════════════════════════════════════════════════════════
def test_def384_an_in_place_rate_edit_on_a_live_tax_is_refused_by_the_server(brazos, dana):
    """⚠ A CLIENT-SIDE REFUSAL IS NOT A REFUSAL.

    TAX-02 has refused this since it was built. `PATCH /taxes/{id}` accepted a
    new rate on a live tax from anything that could reach the API — RED AT HEAD:
    the PATCH returned 200 and the stored rate changed in place, rewriting rate
    history, which part 4 calls *"an audit artefact"* and hard rule 4 forbids.

    The refusal NAMES the correction route, because a refusal that does not say
    what to do instead is the road ending — which is the shape DEF-384 was filed
    for in the first place.
    """
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        with pytest.raises(errors.BizError) as excinfo:
            services.update_tax(dana, str(tax.id), {"rate": "0.070000"})
        tax.refresh_from_db()

    assert excinfo.value.code == errors.BIZ_IMMUTABLE
    assert excinfo.value.params["fields"] == "rate"
    assert excinfo.value.params["correction_path"].endswith("/corrections")
    assert tax.rate == Decimal("0.062500")  # UNCHANGED — that is the whole point


def test_def384_filing_detail_stays_editable_in_place_on_a_live_tax(brazos, dana):
    """⚠ THE BOUNDARY, AND IT IS A JUDGMENT RECORDED IN THE DECISION LOG.

    Part 4's refusal is REASONED — *"because rate history is an audit artefact"*
    — and a bookkeeper's email address is not rate history. Refusing it too would
    mean minting a correction version to fix a typo in a contact, which is the
    kind of over-application that gets a rule quietly disabled later.
    """
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        updated = services.update_tax(
            dana, str(tax.id), {"filing_reminder_recipient": "new@example.test"}
        )
    assert updated["filing_reminder_recipient"] == "new@example.test"
    assert updated["status"] == "active"


def test_def384_a_draft_is_freely_editable_because_it_is_not_history(brazos, dana):
    """It has never priced anything, so there is nothing to preserve."""
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos,
            "Texas State",
            name="TX State",
            kind="percent",
            rate=Decimal("0.062500"),
            is_draft=True,
        )
        updated = services.update_tax(dana, str(tax.id), {"rate": "0.070000"})
    assert updated["rate"] == "0.070000"


def test_def384_a_correction_mints_a_new_row_over_the_same_window(brazos, dana):
    """*"a historic typo is fixed by a documented correction version with a
    reason"* — the door part 4 points at and nothing implemented.

    **Worked:** a rate typed as `0.625000` (62.5 %) instead of `0.062500`
    (6.25 %) charges **`$62.50`** on a $100.00 bill where it should charge
    **`$6.25`**. The correction mints a second row over the SAME window; the
    next run charges `$6.25`, and the 62.5 % row stays visible as the thing that
    happened.

    A CORRECTION restates the same window; a rate CHANGE gets a new one. The two
    must not be conflated — a change leaves history intact and a correction says
    history was mis-recorded — so the window is copied from the corrected row and
    NOT taken from the payload.
    """
    today = today_of(brazos)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        wrong, jurisdiction = a_tax(
            brazos,
            "Texas State",
            name="TX State Utility Tax",
            kind="percent",
            rate=Decimal("0.625000"),  # the typo: 62.5 %
            effective_from=today - timedelta(days=30),
        )
        attach(brazos, plan, jurisdiction)
        before_rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        correction = services.correct_tax(
            dana,
            str(wrong.id),
            {
                "rate": "0.062500",
                "reason": "Statutory rate transposed at entry; Comptroller notice 2026-14.",
            },
        )
        after_rules = selectors.plan_tax_rules(
            plan.id, today, customer_class="commercial", premises=INSIDE_CITY,
            services=("electric",),
        )
        wrong.refresh_from_db()

    assert tax_amounts(bill(before_rules)) == {f"Tax {WD}Texas State": Decimal("62.50")}
    assert tax_amounts(bill(after_rules)) == {f"Tax {WD}Texas State": Decimal("6.25")}
    # THE SAME WINDOW, copied — not taken from the payload.
    assert correction["effective_from"] == (today - timedelta(days=30)).isoformat()
    assert correction["corrects_tax_id"] == str(wrong.id)
    assert correction["correction_reason"].startswith("Statutory rate transposed")
    # ⚠ THE ORIGINAL IS NEVER REWRITTEN AND NEVER DELETED — it is the audit
    # artefact. It keeps its 62.5 % for ever and simply stops pricing.
    assert wrong.rate == Decimal("0.625000")
    assert wrong.superseded_by_id is not None
    assert selectors.tax_in_force(wrong) is False
    # ⚠ AND THE MONEY ALREADY BILLED IS NOT TOUCHED — hard rule 4, and whether
    # it MUST be is OQ-310, named in the response so an operator who has just
    # corrected a wrong rate is not left believing the money is fixed.
    assert correction["issued_bills_unchanged"] is True
    assert correction["open_question"] == "OQ-310"


def test_def384_a_correction_needs_a_documented_reason_and_a_change(brazos, dana):
    """*"with a reason"* — and a one-word reason documents nothing an auditor can
    use twelve months later. A correction that corrects NOTHING is refused too:
    it would break rate history with no content."""
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        with pytest.raises(errors.ValidationError):
            services.correct_tax(dana, str(tax.id), {"rate": "0.07", "reason": "typo"})
        with pytest.raises(errors.ValidationError):
            services.correct_tax(
                dana, str(tax.id), {"reason": "A properly documented reason here."}
            )
        with pytest.raises(errors.BizError):
            # A DRAFT is not history — edit it, do not correct it.
            draft, _ = a_tax(
                brazos, "B", name="Draft", kind="percent", rate=Decimal("0.01"), is_draft=True
            )
            services.correct_tax(
                dana, str(draft.id), {"rate": "0.02", "reason": "A properly documented reason."}
            )


def test_def384_correcting_a_correction_is_refused(brazos, dana):
    """The chain is a chain, not a graph. A superseded row is frozen entirely."""
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        services.correct_tax(
            dana, str(tax.id), {"rate": "0.070000", "reason": "First documented correction."}
        )
        with pytest.raises(errors.BizError) as excinfo:
            services.correct_tax(
                dana, str(tax.id), {"rate": "0.080000", "reason": "Second documented correction."}
            )
    assert excinfo.value.code == errors.BIZ_STATE


def test_def384_the_correction_audits_both_rows(brazos, dana, audit_rows):
    """Hard rule 7 — a correction to an in-force rate changes what customers are
    charged, so both halves are on the trail: the row that stopped and the row
    that started."""
    with tenant_ctx(brazos):
        tax, _ = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        audit_rows.clear()
        services.correct_tax(
            dana, str(tax.id), {"rate": "0.070000", "reason": "A properly documented reason."}
        )
    actions = {row.get("action") if isinstance(row, dict) else getattr(row, "action", None)
               for row in audit_rows}
    assert "tax.corrected" in actions
    assert "tax.correction_created" in actions


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 4 VERBATIM (12-governance/11-change-requests.md) + the six
#         defect rows DEF-380/382/383/384/385/387 read in full + DEF-483 (filed
#         by this lane, before the fix, per the write-back law)
# generated: 2026-08-21 by the Wave D taxes data-model lane
# checklist: A✔ B=n/a(test) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: golden-verify 33/33 UNCHANGED before and after✔ · makemigrations --check clean✔
# exceptions: E1 DEF-381 (compounding order + the cycle check) is DEFERRED BY THE
#         PO — *"stacking later — because that one needs care to avoid a tax that
#         taxes itself in a circle"* — and has NO test here, deliberately ·
#         E2 `rounding_rule` is STORED AND NOT HONOURED (OQ-309): B4 ❄️ is
#         finance-signed and a per-authority override would move a signed figure
#         without a re-sign, so there is no test asserting a non-B4 rounding ·
#         E3 whether a correction must also restate bills ALREADY ISSUED under
#         the wrong figure is OQ-310 — `test_def384_a_correction_mints_a_new_row`
#         asserts only that they are UNCHANGED and that the question is named
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
