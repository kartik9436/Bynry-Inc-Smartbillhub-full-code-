# ── Trace ──────────────────────────────────────────────
# Story:    EP-RAT-12 (CR-013 part 3 — DISCOUNTS)   Screens: DIS-01, the
#           discount detail shell, DIS-02 — none of which this slice builds.
# Rules:    BR-RAT-068 (overlay) · BR-RAT-069 (available ≠ granted) ·
#           BR-RAT-070 (a plan may not override a discount's value) ·
#           BR-RAT-071 (R6 before R7; per-tax treatment) · BR-RAT-072
#           (statuses) · BR-RAT-073 (precedence + exclusivity) · BR-RAT-074
#           (the floor) · BR-RAT-075 (caps, budget, exhaustion) · BR-RAT-076
#           (verification + the contradiction gate) · BR-RAT-077 (second
#           approval) · BR-RAT-078 (enrolments survive versioning) ·
#           BR-RAT-079 (restricted proof)
# Tests:    this file
# Impacts:  —
# ───────────────────────────────────────────────────────
"""CR-013 part 3 — the discount object, proved.

⚠ **THE FIRST TEST ASSERTS THAT THE TABLES EXIST**, which tests do not normally
do. That is deliberate and it is the shape of the gap this slice closed: on
2026-08-19 `\\dt *discount*` on the live database returned **0 rows**, a grep
for a Discount model across every `models.py` in `apps/` returned no match, and
r10 drew five discounts with nothing behind them. A test that goes RED when the
tables are absent is the check that would have caught it, and every one of the
six is named here rather than inferred from a queryset that happens to run.

⚠ **AND THE S1/S2 FIGURES ARE PINNED.** Design §A4's scenario S1 totals
**$195.60** including a **−$1.00 PAPERLESS** discount, and S2 totals **$286.55**
the same way. Both were UNREACHABLE while no discount existed — a design figure
nothing could produce. They are reachable now, so the discount half of each is
asserted to the cent here: 189.90 − 1.00 = **188.90** and 280.85 − 1.00 =
**279.85**, which are the taxable bases those two totals are built on.
"""

import uuid
from dataclasses import replace
from importlib import import_module
from datetime import date
from decimal import Decimal

import pytest

from apps.rating import discount_pricing, discount_sample_data, discount_services
from apps.rating import discounts as discount_models
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE GAP ITSELF — six tables that did not exist this morning
# ══════════════════════════════════════════════════════════════════════════

EXPECTED_TABLES = (
    "discounts",
    "discount_versions",
    "plan_discount_rules",
    "discount_enrolments",
    "discount_enrolment_documents",
    "discount_grants",
)


def test_the_six_discount_tables_exist(django_assert_num_queries=None):
    """RED before this slice: there was no Discount model anywhere in `apps/`.

    Asserted against the real connection's introspection rather than against
    the model registry, because a model that is defined but never migrated is
    exactly as useful to a bill run as no model at all.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        present = set(connection.introspection.table_names(cursor))
    missing = [name for name in EXPECTED_TABLES if name not in present]
    assert not missing, f"CR-013 part 3 tables missing from the database: {missing}"


def test_every_discount_table_is_tenant_scoped():
    """Hard rule 1 — a tenant table carries `tenant_id`, and the RLS policy in
    `db/rls_rating_discounts.sql` is written against that column on all six.
    A table that reached its tenant through a parent FK would have a policy a
    subquery can defeat."""
    for model in (
        discount_models.Discount,
        discount_models.DiscountVersion,
        discount_models.PlanDiscountRule,
        discount_models.DiscountEnrolment,
        discount_models.DiscountEnrolmentDocument,
        discount_models.DiscountGrant,
    ):
        assert any(f.name == "tenant" for f in model._meta.get_fields()), model.__name__


def test_every_rls_policy_is_written_for_every_table():
    """The SQL the migration applies names all six, ENABLE **and** FORCE.

    `rating 0003_rls_w1_policies` exists because a lane documented policies it
    never wrote; this asserts the file, so the same omission cannot recur
    silently on a table holding a customer's income proof.
    """
    from pathlib import Path

    sql = Path(__file__).resolve().parents[1].joinpath("db/rls_rating_discounts.sql").read_text()
    for table in EXPECTED_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql, table
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in sql, table
        assert f"CREATE POLICY {table}_tenant_isolation ON {table}" in sql, table


def test_a_plan_discount_rule_cannot_carry_a_value():
    """PO ruling 2026-08-19, verbatim: **"no plan cannot override prices."**

    r10 draws a per-plan discount-value override and step 8 generates the
    sentence *"discount value replaced with {value}"*. The ruling deletes it, so
    the table has no column that could hold one — the forbidden thing is
    unstorable, not merely refused. RED the moment somebody adds
    `amount_override` back for convenience.
    """
    columns = {f.name for f in discount_models.PlanDiscountRule._meta.get_fields()}
    forbidden = {"value", "amount", "amount_override", "value_override", "percent", "rate"}
    assert not (columns & forbidden), f"a plan may not price: {columns & forbidden}"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE SEED — r10's five, and what a query returns
# ══════════════════════════════════════════════════════════════════════════


def _seed(env):
    with tenant_ctx(env.tenant):
        created = discount_sample_data.seed_sample_discounts(env.admin)
    return created


def test_all_five_r10_discounts_seed(env):
    """The PO's standing position: *"without default sample functionalities ill
    not work"*. r10's five rows, r10's own codes, r10's own values.

    ⚠ **FIVE → SIX ON 2026-09-02 (`CR-062` addendum J2).** The Product Owner
    ruled a sixth — *"What is the government discount called? Municipal account -
    yes; What rate? 20% off the bill before taxes - yes"* — and it is NOT one of
    r10's: the drawing shows five and this one is a ruling made today, which is
    why it is asserted separately below rather than folded into r10's list. The
    count is RESTATED rather than loosened into a band, because a band would
    absorb one of r10's five being silently dropped.
    """
    assert _seed(env) == 6
    with tenant_ctx(env.tenant):
        rows = {
            row["code"]: row
            for row in (
                discount_services.discount_row(d)
                for d in discount_models.Discount.objects.filter(tenant=env.tenant).order_by("code")
            )
        }
    assert set(rows) == {"SENIOR", "CAP", "PAPERLESS", "AUTOPAY", "MILITARY", "MUNICIPAL"}

    # r10 `SMARTBillHub.dc.html:814-818`, value column, to the digit.
    assert rows["SENIOR"]["type"] == "percentage" and Decimal(rows["SENIOR"]["value"]) == Decimal(
        "15"
    )
    assert rows["CAP"]["type"] == "fixed_amount" and Decimal(rows["CAP"]["value"]) == Decimal("25")
    assert rows["PAPERLESS"]["type"] == "fixed_amount" and Decimal(
        rows["PAPERLESS"]["value"]
    ) == Decimal("1")
    assert rows["AUTOPAY"]["type"] == "percentage" and Decimal(rows["AUTOPAY"]["value"]) == Decimal(
        "0.5"
    )
    assert rows["MILITARY"]["type"] == "percentage" and Decimal(
        rows["MILITARY"]["value"]
    ) == Decimal("10")

    # r10 draws MILITARY as a `pill warn` — Draft — with `—` plans and `—` enrolled.
    assert rows["MILITARY"]["status"] == "draft"
    for code in ("SENIOR", "CAP", "PAPERLESS", "AUTOPAY"):
        assert rows[code]["status"] == "active", code

    # Eligibility and verification are r10's own two columns.
    # `CR-166-BRC10` (PO 2026-10-03, *"Who qualifies * - drop down"*): the
    # fixture's *Age 65+* maps to the drawn value, and the row now serves it.
    assert rows["SENIOR"]["eligibility"] == "Age 65 or over"
    assert rows["SENIOR"]["verification"] == "annual_recertification"
    assert rows["CAP"]["verification"] == "agency_file_monthly"
    assert rows["PAPERLESS"]["verification"] == "automatic"

    # ── CR-062 addendum J2 · THE SIXTH, AND IT IS NOT r10's ────────────────
    # PO ruling 2026-09-02, verbatim: *"What is the government discount called?
    # Municipal account - yes; What rate? 20% off the bill before taxes - yes"*.
    # ⚠ **AUTOMATIC ON BOTH COUNTS, AND THAT IS AN ARGUMENT RATHER THAN A
    # CONVENIENCE**: the eligibility is the ACCOUNT TYPE, a fact the utility
    # already records and can see, so there is nothing for a customer to prove
    # and no document to expire. Asking a public works department for a
    # government ID to prove it is a government would be the contradiction
    # `_validate_version` refuses outright.
    assert rows["MUNICIPAL"]["type"] == "percentage"
    assert Decimal(rows["MUNICIPAL"]["value"]) == Decimal("20")
    assert rows["MUNICIPAL"]["status"] == "active"
    assert rows["MUNICIPAL"]["eligibility"] == "Government or municipal account"  # CR-166 drawn value
    assert rows["MUNICIPAL"]["verification"] == "automatic"


def test_the_seed_is_idempotent(env):
    """BR-TEN-063 — a second load writes nothing and returns 0."""
    assert _seed(env) == 6  # r10's five + CR-062 addendum J2's MUNICIPAL
    assert _seed(env) == 0
    with tenant_ctx(env.tenant):
        assert discount_models.Discount.objects.filter(tenant=env.tenant).count() == 6


def test_the_seed_enrols_nobody(env):
    """⚠ **AVAILABLE, NOT GRANTED** (BR-RAT-069), at the fixture's own level.

    r10 shows 72 · 38 · 611 · 418 enrolled accounts. Those are a screenshot's
    numbers. A loader that created them would discount 1,139 real bills on a
    demo tenant, which is the exact failure the rule exists to prevent.

    ⚠ **STILL TRUE OF `seed_sample_discounts`, AND DELIBERATELY SO, AFTER
    `CR-062` ADDENDUM J2 (2026-09-02).** The addendum adds the first seeded
    enrolment this fixture has ever carried — the Municipal discount on ONE
    demonstration account — and it lives in a SEPARATE seam,
    `seed_sample_enrolments`, run as its own sample block after the Accounts
    block. **That separation is what keeps this case meaningful:** the loader
    that creates the catalogue still grants nobody anything, and the one that
    grants is a deliberate act with a named account behind it.
    """
    _seed(env)
    with tenant_ctx(env.tenant):
        assert discount_models.DiscountEnrolment.objects.filter(tenant=env.tenant).count() == 0


def test_the_seeded_rows_carry_the_sample_tag(env):
    """BR-TEN-057 — `is_sample` on the OWNING row, so BR-TEN-061 can remove
    them again on this predicate and on nothing else."""
    _seed(env)
    with tenant_ctx(env.tenant):
        assert (
            discount_models.Discount.objects.filter(tenant=env.tenant, is_sample=True).count() == 6
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · AVAILABLE ≠ GRANTED — the rule that is easiest to build backwards
# ══════════════════════════════════════════════════════════════════════════


def test_attaching_a_discount_to_a_plan_discounts_nobody(env):
    """Part 3: *"plan attachment makes a discount available, not granted."*

    Built as a plan-level flag, a plan carrying SENIOR would discount every
    account on it — 842 of them on Residential Standard. This asserts the
    other half: attaching creates AVAILABILITY and zero enrolments, and R6
    reads enrolments.
    """
    _seed(env)
    # `env.plan` opens its OWN tenant context, so it is called outside this
    # test's — nesting them clears the inner one on exit and the next service
    # call fails AUTH-003, which is the guard doing its job.
    plan = env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "water", "base_charge": "12.00"}],
    )
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        discount_services.attach_discount_to_plan(env.admin, plan["id"], senior.id)

        assert (
            discount_models.PlanDiscountRule.objects.filter(
                tenant=env.tenant, discount=senior
            ).count()
            == 1
        )
        assert (
            discount_models.DiscountEnrolment.objects.filter(
                tenant=env.tenant, discount=senior
            ).count()
            == 0
        )


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ARITHMETIC — §A4's S1 and S2, and the rules around them
# ══════════════════════════════════════════════════════════════════════════

#: Design §A4 S1, inside city: BASE-E 18.50 · USAGE-E 55.00 + 47.60 · BASE-W
#: 12.00 · USAGE-W 12.80 + 28.80 + 7.20 · BASE-S 8.00 → subtotal **189.90**.
S1_LINES = (
    discount_pricing.BillLine("electric", "base", Decimal("18.50"), "BASE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("55.00"), "USAGE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("47.60"), "USAGE-E"),
    discount_pricing.BillLine("water", "base", Decimal("12.00"), "BASE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("12.80"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("28.80"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("7.20"), "USAGE-W"),
    discount_pricing.BillLine("sewer", "base", Decimal("8.00"), "BASE-S"),
)

#: §A4 S2, the SAME account outside city limits — base and usage ×1.5 except
#: sewer, which the multiplier does not touch → subtotal **280.85**.
S2_LINES = (
    discount_pricing.BillLine("electric", "base", Decimal("27.75"), "BASE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("82.50"), "USAGE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("71.40"), "USAGE-E"),
    discount_pricing.BillLine("water", "base", Decimal("18.00"), "BASE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("19.20"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("43.20"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("10.80"), "USAGE-W"),
    discount_pricing.BillLine("sewer", "base", Decimal("8.00"), "BASE-S"),
)

PAPERLESS = discount_pricing.DiscountRule(
    code="PAPERLESS",
    discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
    value=Decimal("1"),
    currency="USD",
    applies_to=discount_models.SCOPE_WHOLE_BILL,
    proof_before_first_reduction=False,
    stacking_precedence=30,
)


def test_scenario_s1_paperless_reaches_the_designs_own_figure():
    """§A4 S1 — subtotal **$189.90**, less **$1.00** PAPERLESS, taxable base
    **$188.90**, and the design's total is **$195.60**.

    ⚠ This figure was UNREACHABLE until this slice: the design stated a total
    that included a discount the product could not express. It is reachable now
    and it agrees, to the cent.
    """
    outcome = discount_pricing.price_discounts(S1_LINES, (PAPERLESS,))
    assert outcome.subtotal_before == Decimal("189.90")
    assert outcome.total_reduction() == Decimal("1.00")
    assert outcome.subtotal_after == Decimal("188.90")
    assert outcome.as_resolution_pairs() == (("PAPERLESS", Decimal("-1.00")),)


def test_scenario_s2_paperless_reaches_the_designs_own_figure():
    """§A4 S2 — subtotal **$280.85**, less **$1.00**, taxable base **$279.85**,
    and the design's total is **$286.55**. Same discount, different bill."""
    outcome = discount_pricing.price_discounts(S2_LINES, (PAPERLESS,))
    assert outcome.subtotal_before == Decimal("280.85")
    assert outcome.subtotal_after == Decimal("279.85")


def test_both_subtotals_are_returned_because_the_tax_picks_its_own_base():
    """BR-RAT-071 — CR-013 part 4 makes discount treatment statutory and PER
    TAX. A module that returned one figure would have decided for every
    authority in the product; both are returned and R7 chooses."""
    outcome = discount_pricing.price_discounts(S1_LINES, (PAPERLESS,))
    assert outcome.subtotal_before != outcome.subtotal_after
    assert outcome.subtotal_before == Decimal("189.90")  # a pre-discount authority
    assert outcome.subtotal_after == Decimal("188.90")  # a post-discount authority


def test_precedence_changes_the_answer_which_is_why_it_is_data():
    """Part 3's own reason for storing an order.

    AUTOPAY is 0.5% of the subtotal and PAPERLESS is a flat $1.00. Run the
    percentage FIRST and it sees $189.90 → $0.95. Run it SECOND and it sees
    $188.90 → $0.94. One cent, on every bill, decided by a number an operator
    types — which is exactly why part 3 refuses to leave it to code order.
    """
    autopay_first = discount_pricing.DiscountRule(
        code="AUTOPAY",
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("0.5"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        proof_before_first_reduction=False,
        stacking_precedence=10,
    )
    autopay_last = replace(autopay_first, stacking_precedence=90)

    first = discount_pricing.price_discounts(S1_LINES, (autopay_first, PAPERLESS))
    last = discount_pricing.price_discounts(S1_LINES, (autopay_last, PAPERLESS))

    assert dict((a.code, a.amount) for a in first.applied)["AUTOPAY"] == Decimal("0.95")
    assert dict((a.code, a.amount) for a in last.applied)["AUTOPAY"] == Decimal("0.94")
    assert first.subtotal_after != last.subtotal_after


def test_one_assistance_programme_per_account_and_the_larger_applies():
    """r10's SENIOR detail, verbatim: *"Not with CAP credit · One assistance
    program per account — the larger applies."*

    On a $189.90 bill, SENIOR at −15% is $28.49 and CAP is a flat $25.00, so
    SENIOR wins and CAP is DENIED with a reason — not silently dropped, because
    *"why did I not get the CAP credit?"* is a support call.
    """
    senior = discount_pricing.DiscountRule(
        code="SENIOR",
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("15"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        exclusivity_group="assistance",
        stacking_precedence=10,
    )
    cap = discount_pricing.DiscountRule(
        code="CAP",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("25"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        exclusivity_group="assistance",
        stacking_precedence=20,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (senior, cap))
    assert [a.code for a in outcome.applied] == ["SENIOR"]
    assert outcome.applied[0].amount == Decimal("28.49")  # 189.90 × 15%
    assert [d.code for d in outcome.denied] == ["CAP"]
    assert "excluded by SENIOR" in outcome.denied[0].reason


def test_a_scoped_discount_takes_its_own_scope_not_the_running_subtotal():
    """BR-RAT-068 — a scoped percentage is a percentage of what is PRINTED.

    A base-only 10% on S1 sees 18.50 + 12.00 + 8.00 = $38.50 → $3.85, not 10%
    of the whole $189.90.
    """
    base_only = discount_pricing.DiscountRule(
        code="BASEDISC",
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("10"),
        currency="USD",
        applies_to=discount_models.SCOPE_BASE_ONLY,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (base_only,))
    assert outcome.applied[0].base == Decimal("38.50")
    assert outcome.applied[0].amount == Decimal("3.85")


def test_the_floor_stops_a_bill_going_below_what_the_programme_allows():
    """BR-RAT-074 — *"a floor so bills don't reach zero unless allowed"*."""
    generous = discount_pricing.DiscountRule(
        code="BIG",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("500"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        bill_floor_amount=Decimal("10.00"),
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (generous,))
    assert outcome.subtotal_after == Decimal("10.00")
    assert outcome.applied[0].trimmed_by == "bill_floor"


def test_a_discount_never_makes_a_bill_negative_even_with_no_floor():
    """The default floor is 0.000000, and that is the whole of *"unless
    allowed"*: a negative bill is a CREDIT, a different object with a different
    ledger posting, and no discount may mint one."""
    generous = discount_pricing.DiscountRule(
        code="BIG",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("500"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (generous,))
    assert outcome.subtotal_after == Decimal("0.00")


def test_proof_before_the_first_reduction_means_no_reduction():
    """BR-RAT-076 — an unverified enrolment on a proof-first programme is
    charged in full, and the reason is RETURNED rather than the line vanishing."""
    senior = discount_pricing.DiscountRule(
        code="SENIOR",
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("15"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        verified=False,
        proof_before_first_reduction=True,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (senior,))
    assert outcome.applied == ()
    assert outcome.subtotal_after == Decimal("189.90")
    assert "not verified" in outcome.denied[0].reason


def test_an_exhausted_budget_gives_nothing_and_never_holds_the_bill():
    """⚖️ `BR-RAT-075` "suspend" SUPERSEDED — PO 2026-10-04, verbatim: *"We
    cannot hold the bill; we need to make discount value to 0 and move on - we
    cannot stop the billing"*. Until then part 3's *"raises an exception when
    budget is exhausted mid-run"* held every enrolled customer's bill. Now a
    spent budget is a $0.00 discount, named as denied, and the bill prices in
    full — for every exhaustion setting, "suspend" included."""
    for behaviour in discount_models.EXHAUSTION_BEHAVIOURS:
        if behaviour == discount_models.EXHAUSTION_CONTINUE:
            continue  # the utility knowingly overspends — it still gives
        spent = discount_pricing.DiscountRule(
            code="CAP",
            discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
            value=Decimal("25"),
            currency="USD",
            applies_to=discount_models.SCOPE_WHOLE_BILL,
            budget_remaining=Decimal("0"),
            exhaustion_behaviour=behaviour,
        )
        outcome = discount_pricing.price_discounts(S1_LINES, (spent,))
        assert outcome.applied == ()
        assert outcome.total_reduction() == Decimal("0")
        assert [d.code for d in outcome.denied] == ["CAP"]


def test_a_budget_that_runs_out_this_bill_is_reported_for_suspension():
    """`suspended_funding_exhausted` is the one status a BILL RUN sets, so the
    run needs to be told which code to set it on."""
    nearly = discount_pricing.DiscountRule(
        code="CAP",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("25"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        budget_remaining=Decimal("25"),
        exhaustion_behaviour=discount_models.EXHAUSTION_SUSPEND,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (nearly,))
    assert outcome.applied[0].amount == Decimal("25.00")
    assert outcome.exhausted == ("CAP",)


def test_a_budget_trim_names_what_trimmed_it():
    """Part 3's Budget-&-usage tab reports *"denials by cap or funding"*, and
    "capped" with no reason is not a report."""
    tight = discount_pricing.DiscountRule(
        code="CAP",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("25"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        budget_remaining=Decimal("4"),
        exhaustion_behaviour=discount_models.EXHAUSTION_CONTINUE,
    )
    outcome = discount_pricing.price_discounts(S1_LINES, (tight,))
    assert outcome.applied[0].amount == Decimal("4.00")
    assert outcome.applied[0].trimmed_by == "budget"


def test_an_unpriceable_type_refuses_rather_than_reducing_nothing():
    """`rate_override` and `usage_allowance` are storable and not priceable. A
    discount that silently reduces nothing is what *"subsidy granted is
    reportable"* exists to prevent."""
    override = discount_pricing.DiscountRule(
        code="SUBSIDY",
        discount_type=discount_models.DISCOUNT_RATE_OVERRIDE,
        value=Decimal("1"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
    )
    with pytest.raises(discount_pricing.DiscountTypeNotPriceable):
        discount_pricing.price_discounts(S1_LINES, (override,))


def test_a_fixed_credit_in_another_currency_refuses():
    """Hard rule 2 is about the PAIRING: a $25 credit is not 25 of a currency
    the bill is not in, and no rate for converting it is signed anywhere."""
    euro = discount_pricing.DiscountRule(
        code="CAP",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("25"),
        currency="EUR",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
    )
    with pytest.raises(discount_pricing.DiscountCurrencyMismatch):
        discount_pricing.price_discounts(S1_LINES, (euro,), currency="USD")


def test_money_never_touches_a_float():
    """CLAUDE.md rule 2 — every figure the arithmetic returns is a Decimal."""
    outcome = discount_pricing.price_discounts(S1_LINES, (PAPERLESS,))
    for value in (outcome.subtotal_before, outcome.subtotal_after, outcome.total_reduction()):
        assert isinstance(value, Decimal)
    assert all(isinstance(line.amount, Decimal) for line in outcome.applied)


# ══════════════════════════════════════════════════════════════════════════
# 5 · APPROVAL — the three PO rulings of 2026-08-19
# ══════════════════════════════════════════════════════════════════════════


def _set_threshold(env, value):
    """Type a figure into the tenant's own Settings page — the ONLY place the
    bar lives. Nothing in `discount_services` carries a default of its own."""
    tenancy_services = import_module("apps.tenancy.services")
    with tenant_ctx(env.tenant):
        tenancy_services.save_settings_family(
            env.admin,
            discount_services.SETTINGS_FAMILY_SLUG,
            {discount_services.KEY_SECOND_APPROVAL_THRESHOLD: value},
        )


def test_the_second_approval_threshold_STARTS_UNSET(env):
    """⚠ **PO RULING 2026-09-10 — THE PLUMBING STAYS AND THE DEFAULT GOES OFF.**
    Verbatim: *"Keep the plumbing, default it off. The threshold setting stays
    but starts unset, so nothing ever requires a second approval unless a
    utility deliberately turns it on."*

    ⚠ **THIS REVERSES THE FIGURE HALF OF THIS TEST, WHICH USED TO REQUIRE
    $50,000** (PO 2026-08-21, OQ-290). The bar did not move again — it was
    removed, and the setting it lived in is still there. The PO's reason:
    *"we have cap also that one person get maixim X discount - that it - we
    dont have to double check it again"*, and exposure really is already
    bounded per customer three ways (cap per bill, per year, lifetime) and once
    more in total by the budget cap."""
    with tenant_ctx(env.tenant):
        assert discount_services.second_approval_threshold() is None


def test_nothing_requires_a_second_approval_while_the_threshold_is_unset(env):
    """The whole of the ruling, on the four seeded budgets and on the two
    boundary figures the old bar was asserted at."""
    with tenant_ctx(env.tenant):
        for budget in ("12312", "11400", "7332", "2383", "50000", "50000.01", "999999999"):
            required, threshold = discount_services.second_approval_required(Decimal(budget))
            assert required is False, budget
            assert threshold is None, budget


def test_A_BLANK_BUDGET_CAP_NO_LONGER_FORCES_IT_EITHER(env):
    """⚠ **THE CLAUSE THAT HAD TO GO WITH THE REST, OR THE FEATURE IS NOT OFF.**

    BR-RAT-077 (PO 2026-08-19) says *"a discount with no budget cap ALWAYS
    requires the second approval"*, and that clause reads no threshold at all —
    so with the bar unset it would have gone on firing, and an assistance
    programme with no cap (the one a small utility is most likely to write)
    would still have demanded an approver it may not have. PO ruling
    2026-09-10 disables it with the rest.

    MILITARY is the seeded case."""
    with tenant_ctx(env.tenant):
        required, threshold = discount_services.second_approval_required(None)
    assert required is False
    assert threshold is None


def test_THE_MECHANISM_COMES_BACK_THE_MOMENT_A_UTILITY_TYPES_A_FIGURE(env):
    """⚠ **THE OTHER HALF OF THE RULING, AND THE ONE AN ABSENCE TEST CANNOT
    SEE.** *"The threshold setting stays"* — so a larger utility switches it on
    and gets the whole mechanism, BR-RAT-077's no-cap clause included. Without
    this case, deleting `second_approval_required` outright would pass every
    assertion above."""
    _set_threshold(env, "10000")
    with tenant_ctx(env.tenant):
        assert discount_services.second_approval_threshold() == Decimal("10000")
        # Above the bar it fires; exactly on it does not, because BR-RAT-077
        # reads "above". The quantity is the discount's own budget cap.
        assert discount_services.second_approval_required(Decimal("10000.01")) == (
            True,
            Decimal("10000"),
        )
        assert discount_services.second_approval_required(Decimal("10000")) == (
            False,
            Decimal("10000"),
        )
        # And the no-cap clause is back with it.
        assert discount_services.second_approval_required(None) == (True, Decimal("10000"))


def test_the_seeded_versions_store_the_requirement_they_were_submitted_under(env):
    """§A7.6 — computed at SUBMIT and STORED, never recomputed at approval. An
    approver must see the requirement the submitter saw."""
    _seed(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount__code="SENIOR"
        )
        paperless = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount__code="PAPERLESS"
        )
    # ⚠ AMENDED TWICE, AND THE SECOND TIME IS THE RULING OF 2026-09-10
    # (`BR-RAT-964`). At $50,000 (OQ-290, 2026-08-21) SENIOR's $12,312 budget no
    # longer tripped the gate but the row still stored the bar it was submitted
    # under. **The bar is now UNSET**, so the row stores `None` — the honest
    # record of *nothing required this, and no figure decided it*, rather than a
    # threshold nobody set.
    #
    # What this TC actually protects is unchanged across both amendments: the
    # version stores what it was SUBMITTED under, so a tenant who turns the
    # setting on tomorrow cannot move the bar under a filing already signed.
    assert senior.second_approval_required is False
    assert senior.second_approval_threshold is None
    assert paperless.second_approval_required is False


def test_a_submitter_may_approve_their_own_filing_and_it_is_recorded(env):
    """PO ruling 2026-08-19, verbatim *"yes allow it"* — Silver Creek has 1–2
    staff and a second person is often nobody. The gate is unchanged; the FACT
    is written down so an auditor sees it rather than inferring it."""
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": "SOLO",
                "name": "Solo test discount",
                "discount_type": "percentage",
                "value": "5",
                "applies_to": "whole_bill",
                "effective_from": date(2026, 8, 1),
                "budget_cap": "500",
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
        discount_services.submit_discount_version(env.admin, version.id)
        result = discount_services.approve_discount_version(env.admin, version.id)
    assert result["self_approved"] is True


def test_activation_refuses_a_type_no_engine_can_price(env):
    """It refuses where an operator is looking at it, not at bill time — an
    active `rate_override` would be a configured discount every run skips."""
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(
            env.admin,
            {
                "code": "OVERRIDE",
                "name": "Subsidised tier",
                "discount_type": "rate_override",
                "value": "1",
                "applies_to": "whole_bill",
                "effective_from": date(2026, 8, 1),
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
        # `CR-166-BRC10` ruling 1: approval is the act that puts it live, so
        # the refusal moved from Activate to Approve.
        discount_services.submit_discount_version(env.admin, version.id)
        with pytest.raises(errors.BizError):
            discount_services.approve_discount_version(env.admin, version.id)


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE NAMED VALIDATION GATES
# ══════════════════════════════════════════════════════════════════════════


def test_automatic_enrolment_with_mandatory_proof_is_refused(env):
    """Part 3 names this one by hand: *"automatic enrolment with mandatory
    proof (contradictory)"*. The product REFUSES the combination rather than
    resolving it, because which half it would have honoured would have been
    decided by whichever code path ran first."""
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.create_discount(
                env.admin,
                {
                    "code": "CONTRA",
                    "name": "Contradictory",
                    "discount_type": "percentage",
                    "value": "5",
                    "enrolment_mode": "automatic",
                    "proof_required": True,
                    "accepted_proof_kinds": ["government_id"],
                },
            )


def test_a_percentage_over_one_hundred_is_refused(env):
    """Not a discount — a payment TO the customer, and no floor rescues a bill
    priced backwards."""
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.create_discount(
                env.admin,
                {
                    "code": "TOOMUCH",
                    "name": "Over 100",
                    "discount_type": "percentage",
                    "value": "150",
                },
            )


def test_a_negative_value_is_refused(env):
    """A discount's value is a MAGNITUDE — stored negative and then subtracted,
    it would ADD to the bill."""
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.create_discount(
                env.admin,
                {"code": "NEG", "name": "Negative", "discount_type": "percentage", "value": "-5"},
            )


def test_an_unknown_field_is_refused_not_ignored(env):
    """Which is what stops a caller sending `plan_value_override` and believing
    it was stored — the ruling of 2026-08-19 made unstorable."""
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.create_discount(
                env.admin,
                {
                    "code": "SNEAK",
                    "name": "Sneaky",
                    "discount_type": "percentage",
                    "value": "5",
                    "plan_value_override": "3",
                },
            )


# ══════════════════════════════════════════════════════════════════════════
# 7 · ENROLMENT, PROOF AND THE SUBSIDY RECORD
# ══════════════════════════════════════════════════════════════════════════


def _account(env, service="water"):
    """One real account, through metering's own premises/unit helpers."""
    from apps.customers import models as customer_models
    from tests.test_us_met_helpers import make_premises, make_unit

    with tenant_ctx(env.tenant):
        premises = make_premises(
            env.admin, address_line="1 Discount Way", services_available=[service]
        )
        unit = make_unit(env.admin, premises["id"], label="A", services=[service])
        account = customer_models.Account.objects.create(
            tenant=env.tenant,
            unit_id=unit["id"],
            account_no="ACC-DISC-1",
            status=customer_models.AccountStatus.objects.get(tenant=env.tenant, code="active"),
            account_type=customer_models.AccountType.objects.first(),
        )
        # `CR-166-BRC10` ruling 2: only an account whose plan carries a discount
        # can be enrolled in it, so the unit is put on a plan carrying them all.
        from tests.discount_plan_fixture import carry

        carry(env.tenant, unit["id"], discount_models.Discount.objects.filter(tenant=env.tenant))
        return account


def test_enrolment_is_what_grants_a_discount(env):
    """The whole of BR-RAT-069's other half, end to end: enrol an account and
    R6 sees the discount; the plan attachment is not what did it."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        assert discount_services.discount_rules_for_account(account.id, date(2026, 9, 30)) == ()
        discount_services.enrol_account(env.admin, paperless.id, account.id, date(2026, 9, 1))
        rules = discount_services.discount_rules_for_account(account.id, date(2026, 9, 30))
    assert [rule.code for rule in rules] == ["PAPERLESS"]
    assert rules[0].value == Decimal("1.000000")


def test_the_enrolled_account_reaches_the_s1_figure_through_the_db_path(env):
    """§A4 S1's −$1.00, this time through the DATABASE rather than a literal
    rule — the path a bill run will take.

    189.90 − 1.00 = **188.90**, which is S1's taxable base and the figure its
    **$195.60** total is built on.
    """
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        discount_services.enrol_account(env.admin, paperless.id, account.id, date(2026, 9, 1))
        outcome = discount_services.price_account_discounts(
            account.id, S1_LINES, on_day=date(2026, 9, 30)
        )
    assert outcome.subtotal_before == Decimal("189.90")
    assert outcome.subtotal_after == Decimal("188.90")


def test_a_proof_first_enrolment_reduces_nothing_until_it_is_verified(env):
    """SENIOR demands proof. The enrolment stands and the bill is charged in
    full until the document is recorded — a money rule, so it is stored and
    asserted rather than assumed."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(
            env.admin, senior.id, account.id, date(2026, 9, 1)
        )
        before = discount_services.price_account_discounts(
            account.id, S1_LINES, on_day=date(2026, 9, 30)
        )
        discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="government_id", verified_on=date(2026, 9, 2)
        )
        after = discount_services.price_account_discounts(
            account.id, S1_LINES, on_day=date(2026, 9, 30)
        )
    assert before.applied == ()
    assert after.applied[0].code == "SENIOR"
    assert after.applied[0].amount == Decimal("28.49")  # 189.90 × 15%


def test_verification_sets_the_recertification_clock(env):
    """Part 3's *"expiring in 30 days"* filter reads this column, so an annual
    programme verified on 2 Sep 2026 is due again on 2 Sep 2027."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(
            env.admin, senior.id, account.id, date(2026, 9, 1)
        )
        row = discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="government_id", verified_on=date(2026, 9, 2)
        )
    assert row["recertification_due_on"] == "2027-09-02"


def test_income_and_medical_proof_are_restricted_by_their_kind(env):
    """BR-RAT-079 — *"income and medical proof restricted by role and excluded
    from general document lists"*. The flag is DERIVED from the kind, never
    supplied, so a new restricted kind cannot be filed as an ordinary one."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        cap = discount_models.Discount.objects.get(tenant=env.tenant, code="CAP")
        enrolment = discount_services.enrol_account(env.admin, cap.id, account.id, date(2026, 9, 1))
        discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="income_statement", verified_on=date(2026, 9, 2)
        )
        document = discount_models.DiscountEnrolmentDocument.objects.get(
            tenant=env.tenant, enrolment_id=enrolment["id"]
        )
    assert document.restricted is True


def test_an_ordinary_proof_is_not_restricted(env):
    """The negative half — a veteran ID is an ordinary document, and marking
    everything restricted would make the restriction meaningless."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(
            env.admin, senior.id, account.id, date(2026, 9, 1)
        )
        discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="government_id", verified_on=date(2026, 9, 2)
        )
        document = discount_models.DiscountEnrolmentDocument.objects.get(
            tenant=env.tenant, enrolment_id=enrolment["id"]
        )
    assert document.restricted is False


def test_an_enrolment_survives_a_new_discount_version(env):
    """Part 3's shared rule: *"enrolments survive versioning."*

    r10's SENIOR went v1 −10% → v2 −15% on 1 Jan 2026 and its 72 accounts did
    not re-enrol. The FK is to the DISCOUNT, so a new version cannot end one.
    """
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(
            env.admin, senior.id, account.id, date(2026, 9, 1)
        )
        discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="government_id", verified_on=date(2026, 9, 2)
        )
        new_version = discount_services.create_discount_version(
            env.admin,
            senior.id,
            {
                "discount_type": "percentage",
                "value": "20",
                "applies_to": "whole_bill",
                "effective_from": date(2026, 10, 1),
                "budget_cap": "12312",
                "change_reason": "Raised from -15% to -20%",
                "enrolment_mode": "apply_and_approve",
                "verification_method": "annual_recertification",
                "proof_required": True,
                "accepted_proof_kinds": ["government_id"],
                "recertification_months": 12,
            },
        )
        discount_services.submit_discount_version(env.admin, new_version["id"])
        discount_services.approve_discount_version(env.admin, new_version["id"])  # live (ruling 1)

        still_here = discount_models.DiscountEnrolment.objects.get(
            tenant=env.tenant, pk=enrolment["id"]
        )
        rules = discount_services.discount_rules_for_account(account.id, date(2026, 10, 31))
    assert still_here.ended_on is None
    assert [rule.value for rule in rules] == [Decimal("20.000000")]  # the NEW version prices it


def test_ending_an_enrolment_restores_full_price_with_no_rate_change(env):
    """r10's own words. The rate is untouched; only the enrolment ends."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        enrolment = discount_services.enrol_account(
            env.admin, paperless.id, account.id, date(2026, 9, 1)
        )
        discount_services.end_enrolment(env.admin, enrolment["id"], "withdrawn", date(2026, 9, 15))
        outcome = discount_services.price_account_discounts(
            account.id, S1_LINES, on_day=date(2026, 9, 30)
        )
    assert outcome.applied == ()
    assert outcome.subtotal_after == Decimal("189.90")


def test_lifetime_subsidy_equals_the_sum_of_grants(env):
    """The denormalised counter and the append-only rows are asserted EQUAL, so
    the drift a counter invites goes RED rather than quiet."""
    from django.db.models import Sum

    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        enrolment = discount_services.enrol_account(
            env.admin, paperless.id, account.id, date(2026, 9, 1)
        )
        for month in (9, 10, 11):
            discount_services.record_grant(
                env.admin,
                enrolment["id"],
                date(2026, month, 1),
                date(2026, month, 28),
                Decimal("1.00"),
            )
        row = discount_models.DiscountEnrolment.objects.get(tenant=env.tenant, pk=enrolment["id"])
        total = discount_models.DiscountGrant.objects.filter(
            tenant=env.tenant, enrolment=row
        ).aggregate(t=Sum("amount"))["t"]
    assert row.lifetime_subsidy_amount == total == Decimal("3.000000")


def test_a_correction_is_a_new_row_never_an_edit(env):
    """Hard rule 4 — an issued bill's reduction is never updated or deleted; a
    correction is a NEW row with a negative amount, so the SUM is the net."""
    from django.db.models import Sum

    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        enrolment = discount_services.enrol_account(
            env.admin, paperless.id, account.id, date(2026, 9, 1)
        )
        discount_services.record_grant(
            env.admin, enrolment["id"], date(2026, 9, 1), date(2026, 9, 28), Decimal("1.00")
        )
        # The reversal carries its own invoice id, which is what the idempotency
        # unique allows and a same-period duplicate does not: hard rule 6 stops
        # a re-run double-counting, and hard rule 4 requires the correction to
        # be a row of its own rather than an edit of the first.
        discount_services.record_grant(
            env.admin,
            enrolment["id"],
            date(2026, 9, 1),
            date(2026, 9, 28),
            Decimal("-1.00"),
            invoice_id=uuid.uuid4(),
        )
        rows = discount_models.DiscountGrant.objects.filter(
            tenant=env.tenant, enrolment_id=enrolment["id"]
        )
        assert rows.count() == 2
        assert rows.aggregate(t=Sum("amount"))["t"] == Decimal("0.000000")


def test_a_retired_discount_takes_no_new_enrolment(env):
    """Part 3: *"retiring blocks new enrolment"* — and leaves existing ones."""
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        paperless = discount_models.Discount.objects.get(tenant=env.tenant, code="PAPERLESS")
        # Ruling 4: Retire takes a date; retiring blocks new enrolment from
        # the moment it is recorded (BR-RAT-078's surviving clause).
        from apps.rating import seams

        discount_services.retire_discount(
            env.admin, paperless.id, {"effective_to": str(seams.tenant_today())}
        )
        with pytest.raises(errors.BizError):
            discount_services.enrol_account(env.admin, paperless.id, account.id, date(2026, 9, 1))


def test_every_money_action_writes_an_audit_row(env, audit_rows):
    """CLAUDE.md rule 7. Enrolling, verifying and granting each write one.

    Asserted through the BE-03 CAPTURE SINK rather than by querying
    `audit_log`, which is the contract these suites use: capture, don't fake
    storage.
    """
    _seed(env)
    account = _account(env)
    with tenant_ctx(env.tenant):
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        enrolment = discount_services.enrol_account(
            env.admin, senior.id, account.id, date(2026, 9, 1)
        )
        discount_services.verify_enrolment(
            env.admin, enrolment["id"], proof_kind="government_id", verified_on=date(2026, 9, 2)
        )
        discount_services.record_grant(
            env.admin, enrolment["id"], date(2026, 9, 1), date(2026, 9, 28), Decimal("28.49")
        )
    actions = set(audit_actions(audit_rows))
    assert {
        "discount.account_enrolled",
        "discount.enrolment_verified",
        "discount.subsidy_granted",
    } <= actions


# ══════════════════════════════════════════════════════════════════════════
# 8 · TENANT SCOPING
# ══════════════════════════════════════════════════════════════════════════


def test_one_tenants_discounts_are_invisible_to_another(env, other_env):
    """Hard rule 1's app-filter half. The RLS half runs in the G5 isolation
    suite against Postgres — sqlite cannot enforce a policy."""
    _seed(env)
    with tenant_ctx(other_env.tenant):
        assert discount_services.discount_count() == 0
    with tenant_ctx(env.tenant):
        assert discount_services.discount_count() == 6


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 VERBATIM + 08-cr013-design.md §A4 (S1/S2 figures) and §A8 (the four programme costs) + 07-r10-plans-rates-readout.md §4 + the PO rulings of 2026-08-19 + CLAUDE.md hard rules 1/2/4/7
# generated: 2026-08-19 by the CR-013 EP-RAT-12 lane (discounts — tests)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: the RLS half of the isolation case runs in the G5 suite on Postgres — sqlite cannot enforce a policy, so this file asserts the app filter and the SQL text · no enrolment is seeded, so no test asserts r10's 72/38/611/418 enrolled counts: they are a screenshot's numbers, not a fixture's
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── BR-RAT-109 · SUPERSEDED 2026-10-03 by PO ruling (1) → BR-RAT-1061 ──────
#
# Activating a never-submitted version used to be warned-and-allowed. Approval
# is now the last act and there is no Activate, so no door remains through
# which a draft goes live without approval: the old door refuses by name.


def test_br_rat_109_superseded__a_draft_cannot_be_activated_at_all(env):
    _seed(env)
    with tenant_ctx(env.tenant):
        discount_services.create_discount(
            env.admin,
            {
                "code": "STRAIGHT", "name": "Activated straight from draft",
                "discount_type": "percentage", "value": "0.05",
                "effective_from": "2026-07-01",
            },
        )
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount__code="STRAIGHT"
        )
        with pytest.raises(errors.BizError) as refused:
            discount_services.activate_discount_version(env.admin, version.id)
        version.refresh_from_db()
    assert refused.value.message_key == "rating.discounts.activate_retired"
    assert version.status == discount_models.VERSION_DRAFT
