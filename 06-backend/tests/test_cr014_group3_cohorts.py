# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 group 3 — the ~21 activated journeys that are the shared flat
#           cohort PLUS ONE MORE ACT each. The cohort builders live in
#           tests/journey_cohort_fixtures.py; these are the declared cases that
#           hold each one to the Fixture paragraph it claims to satisfy.
# Rules:    DEF-108 (a cohort that cannot be produced REFUSES by name; a ✔ over
#           a half-seeded world is the false green this CR exists to remove) ·
#           DEF-556 / OQ-218 (no extension may post a journal entry into the
#           finance-signed June 30 → July 31 window) · CLAUDE.md rule 6 (a
#           re-boot re-runs every seeder and writes nothing twice) · rule 3
#           (every consumption carries its unit).
# Golden:   The only SIGNED figures asserted here are the ones the journeys
#           themselves quote: money-triples `flat,cycle,full` **97.41** (T5-19's
#           draft), WE-8's level **242** (T4-21), money-triples `flat,budget`
#           level **97** / variance **-0.41** (T7-15), and T4-02's deposit pair
#           **150.00 / 400.00**. Everything else in group 3 is engine-computed
#           per 00-e2e-design.md §5 and is asserted STRUCTURALLY, never by a
#           typed total — a figure typed here would be a figure no workbook
#           states.
# Red-proof: each case was shown RED before it was made green; the failures are
#           quoted in the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""CR-014 group 3 — each extension is the shared cohort plus exactly one act.

The builders under test were written to be run by
`08-qa/01-e2e/stack/seed_journey_fixture.py` on a booted stack, where the only
reader is a person looking at boot output. That is precisely the place DEF-108's
false green hides, so every one of them is exercised here instead: if a builder
silently produces half its journey's world, this file is what says so.

**The invariant that spans all of them** is the last test: building every group-3
cohort leaves the finance-signed July window exactly as LE-1 posted it. No
journey in group 3 asserts that, and no journey ever will — it is a property of
the FIXTURES, and only a fixture test can hold it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests import journey_cohort_fixtures as cohort
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _platform_tamper_amount() -> str:
    """The PO-ruled TAMPER figure, read from the platform fixture (DEF-563).

    Typed here it would be a fifth copy of a number two ratified sources
    already disagreed about; read from `seed_demo.CHARGE_CODES` it goes red if
    the ruling is ever revisited, which is the only useful behaviour.
    """
    from apps.tenancy.management.commands import seed_demo

    row = next(r for r in seed_demo.CHARGE_CODES if r["code"] == "TAMPER")
    return row["amount"]


# ── T4-01 · the change target ───────────────────────────────────────────────


def test_group3_t4_01__a_second_published_service_compatible_plan(brazos, dana):
    """*"target plan … (published, service-compatible per BR-RAT-030)"*.

    Two properties, and BOTH are the journey's: PUBLISHED (BR-RAT-030 makes
    only published plans assignable, so a draft target would fail the change
    for an unrelated reason) and SERVICE-COMPATIBLE with the plan being left.
    """
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        current = cohort.ensure_flat_plan(brazos, dana)
        target = cohort.ensure_second_plan(brazos, dana)

        current_services = {
            row["service_code"] for row in rating_selectors.plan_rate_schedules(current.id)
        }
        target_services = {
            row["service_code"] for row in rating_selectors.plan_rate_schedules(target.id)
        }

    assert target.id != current.id
    assert target.status == "published"
    assert target_services == current_services


# ── T4-02 · the deposit that must NOT move ──────────────────────────────────


def test_group3_t4_02__both_deposit_rules_exist_and_differ(brazos, dana):
    """*"deposit held $150.00 … Small Commercial category amount $400.00 exists
    in the same fixture"*.

    T4-02's whole assertion is an ABSENCE — the held deposit does not move to
    400.00 when the account changes category (BR-CUS-062). An absence is only
    worth asserting where the other figure EXISTS to be tempted by, so a
    fixture missing the 400.00 row makes the journey vacuous while it passes.
    """
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        result = cohort.ensure_deposit_rules(brazos, dana)
        amounts = sorted(
            Decimal(row.amount).quantize(Decimal("0.01"))
            for row in rating_models.PlanDepositRule.objects.filter(tenant=brazos)
        )

    assert result["residential"] == Decimal("150.000000")
    assert result["commercial"] == Decimal("400.000000")
    assert Decimal("150.00") in amounts and Decimal("400.00") in amounts
    # The HELD position, not just the rules: this is the figure step 2 watches
    # for movement, and 0.00 → 0.00 is "unchanged" too.
    assert Decimal(result["deposit_on_file"]) == Decimal("150.00")


# ── T4-03 · the wrongly-planned occupied unit ───────────────────────────────


def test_group3_t4_03__an_issued_wrong_plan_bill_exists(brazos, dana):
    """*"June's bill is issued and wrong-plan-priced (the J6 correction
    fixture)"* — amended to August per DEF-556.

    The load-bearing facts are that the unit is OCCUPIED, that it carries the
    WRONG plan, and that a real ISSUED bill was priced from it. The bill's
    total is engine-computed (00-e2e-design.md §5), so it is asserted to be
    the commercial price rather than a number typed here — and specifically
    NOT the flat cohort's 97.41, which is what a wrongly-shared plan would give.
    """
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        result = cohort.ensure_wrong_plan_cohort(brazos, dana)
        account = customer_models.Account.objects.get(
            tenant=brazos, account_no=cohort.WRONG_PLAN_ACCOUNT
        )
        unit_plan = account.unit.rate_plan

    assert account.status.code == "active"  # OCCUPIED — BR-MET-036
    assert unit_plan.name == cohort.COMMERCIAL_PLAN_NAME  # the error being corrected
    assert result["invoice_no"]
    assert Decimal(result["invoice_total"]) != cohort.FLAT_TOTAL


# ── T4-12 · the exemption certificate that expires ──────────────────────────


def test_group3_t4_12__the_exempt_account_is_billable_and_its_cert_is_expired(brazos, dana):
    """*"ACC-1049 tax-exempt, cert ref TX-EX-88121, expiry 2026-07-31"*.

    The expiry is DERIVED state (BR-CUS-063, CL-6: expired → warning, never
    auto-untag), so the STORED expiry is the fixture. The builder also proves
    the account is READY for a run — a journey whose step 2 is *"the Aug bill
    run executes"* over an unbillable account would report zero tax lines
    because it billed nothing, which reads exactly like a correct exemption.
    """
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        result = cohort.ensure_expiring_exemption(brazos, dana)
        account = customer_models.Account.objects.get(
            tenant=brazos, account_no=cohort.EXEMPT_ACCOUNT
        )

    assert account.tax_exempt is True
    assert account.tax_exempt_ref == cohort.EXEMPT_CERT_REF
    assert account.tax_exempt_expires == cohort.EXEMPT_CERT_EXPIRY
    assert result["cycle"] == cohort.EXEMPT_CYCLE


# ── T4-15 · the swap pre-state ──────────────────────────────────────────────


def test_group3_t4_15__the_old_meter_is_installed_and_read(brazos, dana):
    """*"unit 104, ACC-1044 active · electric meter M-2201 (multiplier 1)"*.

    The SWAP is the journey's own act, so the fixture is only the x-state: a
    meter on an occupied unit with a committed read to take a FINAL read
    against. A meter with no prior read gives step 1 nothing to compute a span
    from and the journey's two-span assertion becomes one span of nothing.
    """
    from apps.assets import models as asset_models
    from apps.metering.models import MeterRead

    with tenant_ctx(brazos):
        result = cohort.ensure_swap_pre_state(brazos, dana)
        meter = asset_models.Asset.objects.get(tenant=brazos, asset_no=cohort.SWAP_METER_OLD)
        reads = MeterRead.objects.filter(tenant=brazos, asset_id=meter.id).count()
        # An asset reaches its unit through the SERVICE POINT (B2's reviewed
        # cross-module FK), never a `unit_id` column — a fixture that asserted
        # the column would be asserting a shape the product does not have.
        point_unit = str(meter.service_point.unit_id) if meter.service_point_id else None

    assert result["account_no"] == cohort.SWAP_ACCOUNT
    assert point_unit == result["unit_id"]
    assert reads >= 1


# ── T4-16 · the sub-meter group ─────────────────────────────────────────────


def test_group3_t4_16__the_master_has_exactly_its_two_children(brazos, dana):
    """*"master M-MASTER-12 with children SM-8801, SM-8802"*.

    The journey moves ONE child and recomputes Σ-subs against the master. A
    group of one, or of three, changes the arithmetic it asserts — so the
    builder refuses on anything but the named pair, and this holds it to that.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_master_group(brazos, dana)

    assert result["children"] == sorted([cohort.SUB_METER_MOVED, cohort.SUB_METER_STAYS])
    assert result["target_unit_id"]


# ── T5-14 · billing without a snapshot ──────────────────────────────────────


def test_group3_t5_14__the_no_plan_account_blocks_the_run(brazos, dana):
    """*"seeded as a cutover DEFECT: no account_plan_assignments row"*.

    Seeding the state is half the job; the other half is that the run actually
    REFUSES it. A journey asserting *"the run surfaces it as an exception"*
    passes over an empty exception list, so the builder asserts the refusal and
    this asserts that it asserted it.
    """
    from apps.billing import gather as billing_gather

    with tenant_ctx(brazos):
        result = cohort.ensure_no_plan_account(brazos, dana)

    assert result["blocked_reason"] == billing_gather.GATHER_NO_PLAN
    assert result["account_no"] == cohort.NO_PLAN_ACCOUNT


# ── T5-19 · the draft, and the charge code ──────────────────────────────────


def test_group3_t5_19__a_draft_totalling_the_dataset_row_and_the_tamper_code(brazos, dana):
    """*"draft … showing computed lines totaling $97.41 pre-issue … charge code
    TAMPER $500.00 configured"*.

    Both halves are the journey's own figures. The draft must be a DRAFT
    (BR-BIL-004 — a draft is not money, and the journey hunts for a door that
    lets a human type a dollar into one), and the TAMPER code exists because
    BR-BIL-019 says even theft money enters as a configured charge code.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_draft_cohort(brazos, dana)

    assert Decimal(result["draft_total"]) == cohort.FLAT_TOTAL  # 97.41
    assert result["charge_code"] == cohort.TAMPER_CODE
    # ⚠ 250.00, NOT the paragraph's 500.00 — DEF-563. The PO ruled the platform
    # TAMPER default is $250.00 on 2026-08-10, over the billing workbook's
    # WE-11 $500.00 that T5-19's paragraph quotes. The fixture reads the ruled
    # figure from `seed_demo.CHARGE_CODES` and never overwrites a tenant's row,
    # so this asserts the RULING rather than the stale paragraph.
    assert Decimal(result["charge_amount"]) == Decimal(_platform_tamper_amount())


# ── T4-21 / T7-15 · budget billing ──────────────────────────────────────────


def test_group3_t4_21__the_engine_computes_we8s_level(brazos, dana):
    """*"computed level $242 (WE-8)"* — COMPUTED, never typed.

    The band the journey enforces is ±30% OF THAT NUMBER, so a different level
    is a different test. The builder feeds the engine twelve actuals summing to
    WE-8's $2,904 and refuses anything but 242 back.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_budget_band_account(brazos, dana)

    assert Decimal(result["level"]) == cohort.WE8_LEVEL  # 242
    assert Decimal(result["trailing_total"]) == cohort.WE8_TRAILING_TOTAL  # 2904.00


def test_group3_t7_15__the_running_variance_is_produced_not_typed(brazos, dana):
    """*"level 97 … variance balance running at -0.41 after the latest bill
    (money-triples `flat,budget`: actual 97.41 vs level 97)"*.

    T7-15's assertion is that a SETTINGS save may never touch that running
    variance, so the variance has to be real before the journey starts. It is
    produced by `record_bill` putting the dataset row's 97.41 against the level.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_budget_params_account(brazos, dana)

    assert Decimal(result["level"]) == cohort.T715_LEVEL  # 97
    assert Decimal(result["variance"]) == cohort.T715_VARIANCE  # -0.41
    assert result["settle_up_month"] == cohort.T715_SETTLE_UP_MONTH  # 4


# ── The property no journey asserts ─────────────────────────────────────────


def test_group3__building_every_extension_leaves_the_signed_july_untouched(brazos, dana):
    """DEF-556 / OQ-218, held across the WHOLE group at once.

    Each builder was written not to post into the finance-signed window; this
    is the only place that checks they all still don't, TOGETHER. An extension
    added later that quietly bills a July period would move LE-1's 553.69, and
    every journey in the suite would stay green while it happened.
    """
    from apps.ledger import reporting
    from tests import ledger_le_fixtures as le

    with tenant_ctx(brazos):
        world: dict = {}
        accounts = le.make_accounts(dana, brazos, world, service="electric")
        le.post_le1_month(brazos, accounts)
        before = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)

        cohort.ensure_flat_cohort(brazos, dana)
        cohort.ensure_deposit_rules(brazos, dana)
        cohort.ensure_second_plan(brazos, dana)
        cohort.ensure_swap_pre_state(brazos, dana)
        cohort.ensure_master_group(brazos, dana)
        cohort.ensure_wrong_plan_cohort(brazos, dana)
        cohort.ensure_expiring_exemption(brazos, dana)
        cohort.ensure_no_plan_account(brazos, dana)
        cohort.ensure_draft_cohort(brazos, dana)
        cohort.ensure_budget_band_account(brazos, dana)
        cohort.ensure_budget_params_account(brazos, dana)

        after = reporting.trial_balance(start=le.JULY_START, end=le.JULY_END)

    assert before["rows"] == after["rows"]
    assert Decimal(str(after["total_debit"])) == Decimal("553.69")


def test_group3__every_extension_is_idempotent(brazos, dana):
    """CLAUDE.md rule 6. A stack is re-booted and every seeder runs again; the
    second pass must find its world and mint nothing twice. A cohort whose
    content depends on how many times it was seeded is a cohort that is right
    on a fresh boot and wrong on every one after."""
    from apps.billing import models as billing_models
    from apps.customers import models as customer_models

    builders = (
        cohort.ensure_deposit_rules,
        cohort.ensure_swap_pre_state,
        cohort.ensure_master_group,
        cohort.ensure_wrong_plan_cohort,
        cohort.ensure_expiring_exemption,
        cohort.ensure_no_plan_account,
        cohort.ensure_draft_cohort,
        cohort.ensure_budget_band_account,
        cohort.ensure_budget_params_account,
    )
    with tenant_ctx(brazos):
        for builder in builders:
            builder(brazos, dana)
        for builder in builders:
            builder(brazos, dana)

        accounts = customer_models.Account.objects.filter(
            tenant=brazos,
            account_no__in=[
                cohort.SWAP_ACCOUNT,
                cohort.WRONG_PLAN_ACCOUNT,
                cohort.EXEMPT_ACCOUNT,
                cohort.NO_PLAN_ACCOUNT,
                cohort.DRAFT_ACCOUNT,
                cohort.BUDGET_BAND_ACCOUNT,
                cohort.T715_ACCOUNT,
            ],
        ).count()
        wrong_plan_bills = billing_models.Invoice.objects.filter(
            tenant=brazos, account__account_no=cohort.WRONG_PLAN_ACCOUNT, status="issued"
        ).count()
        drafts = billing_models.Invoice.objects.filter(
            tenant=brazos, account__account_no=cohort.DRAFT_ACCOUNT, status="draft"
        ).count()

    assert accounts == 7
    assert wrong_plan_bills == 1
    assert drafts == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-014 group 3 · W11 lane 2026-08-22
# generated: 2026-08-22
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: pytest (this file) · seed_journey_fixture.py --check · golden 33/33
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
