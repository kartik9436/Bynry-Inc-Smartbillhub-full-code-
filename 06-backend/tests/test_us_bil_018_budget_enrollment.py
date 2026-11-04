# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 (enrolment, eligibility & the level computation)
#           Screens: S30 (Budget Bills tab) · S66/S69 (the parameter rows)
# Rules:    BR-BIL-017 (level = trailing-12-month average, whole $; eligibility
#           = 12-mo history; every parameter a tenant setting with these as
#           seeded defaults) · BR-RAT-043 (budget billing rides the plan flag)
#           · BR-BIL-021 (nothing hardcoded) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 7 (every money action writes audit_log)
# ───────────────────────────────────────────────────────
"""US-BIL-018 §3 — the six test cases, on the frozen WE-8 fixture.

The one that matters most is TC-2: it lowers the tenant's eligibility window to
9 and watches the same account flip from ineligible to eligible. A level
computed from a hardcoded 12 would pass every other case in this file.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import budget, budget_service, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account

pytestmark = pytest.mark.django_db

# ❄️ WE-8 / GT-24 verbatim.
TRAILING_12 = (Decimal("2904"),)
LEVEL = Decimal("242")
ENROLLED_ON = date(2026, 6, 28)  # J09 step 1's date


def set_budget_settings(actor, tenant, **changes):
    """Write the tenant's S69 rule page through tenancy's own service.

    Never the ORM: the point of TC-2 is that the ENGINE reads the tenant's
    stored settings, and a test that patched a constant would prove nothing
    about that.
    """
    from apps.tenancy import services as tenancy_services

    return tenancy_services.save_settings_family(actor, "budget-billing", changes)


def enroll(actor, account, **overrides):
    kwargs = dict(
        actor=actor,
        account_id=account.id,
        trailing_actuals=TRAILING_12,
        months_of_history=12,
        plan_offers_budget=True,
        currency="USD",
        on_date=ENROLLED_ON,
    )
    kwargs.update(overrides)
    return budget_service.enroll(**kwargs)


def test_us_bil_018_tc1__twelve_months_of_history_computes_the_frozen_level(
    brazos, marcus, dana, audit_rows
):
    """ACC-1042: trailing-12 actuals $2,904 → level **$242**, variance 0.00.

    The status row, the settle-up month from the tenant setting, and the audit
    row — US-BIL-018 TC-1 in full.
    """
    with tenant_ctx(brazos):
        # The S69 page is a System Admin's to write and the enrolment is the
        # Billing Clerk's to take — two roles, exactly as the product has them.
        set_budget_settings(dana, brazos, settle_up_month=4)  # April, tenant-set
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enroll(marcus, account)

        assert status.level == LEVEL
        assert status.variance_balance == Decimal("0")
        assert status.settle_up_month == 4
        assert status.status == budget.STATUS_ENROLLED
        assert status.enrolled_on == ENROLLED_ON

        # Rule 7: the enrolment is a money action and leaves a trail with the
        # level ON it — "why does this customer pay 242?" has an answer.
        enrolled = [row for row in audit_rows if row["action"] == "budget.enrolled"]
        assert len(enrolled) == 1
        assert enrolled[0]["after"]["level"] == "242"
        assert enrolled[0]["after"]["eligibility_months"] == 12

        # The opening event exists and the cache agrees with its derivation.
        assert budget_service.recompute_balance(status) == Decimal("0.00")


def test_us_bil_018_tc2__the_eligibility_window_is_a_tenant_setting_not_a_constant(
    brazos, marcus, dana
):
    """Nine months of history is ineligible at 12 and eligible at 9.

    THE POINT OF THIS TEST is that nothing in the engine knows the number 12.
    The reason names the shortfall the way S30 shows it ("9/12 months").
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1350")

        verdict = budget.eligibility(
            months_of_history=9, required_months=12, plan_offers_budget=True
        )
        assert verdict.eligible is False
        assert verdict.reason == budget.INELIGIBLE_SHORT_HISTORY
        assert verdict.detail == "9/12 months"

        with pytest.raises(budget_service.BudgetRuleError, match="9/12 months"):
            enroll(marcus, account, months_of_history=9)

        # The tenant lowers the window. Same account, same history, same call.
        set_budget_settings(dana, brazos, eligibility_months=9)
        status = enroll(marcus, account, months_of_history=9)
        assert status.status == budget.STATUS_ENROLLED
        # …and the DIVISOR followed the setting: 2,904 ÷ 9 = 322.67 → 323 whole
        # dollars, not 242. A level that stayed 242 would mean the window moved
        # for eligibility and not for the average.
        assert status.level == Decimal("323")


def test_us_bil_018_tc3__three_accounts_enrol_with_their_own_levels(brazos, marcus):
    """Bulk enrolment is N single enrolments, each on its OWN trailing twelve.

    The prototype's step-2 table shows one flat monthly per customer
    ($2,846.40 → $237.20 · $4,120.80 → $343.40 · $1,096.80 → $91.40), so a bulk
    action that applied one level to three accounts would match no row of it.
    """
    fixtures = {
        "ACC-1042": (Decimal("2846.40"), Decimal("237")),
        "ACC-1091": (Decimal("4120.80"), Decimal("343")),
        "ACC-1130": (Decimal("1096.80"), Decimal("91")),
    }
    with tenant_ctx(brazos):
        for account_no, (total, expected) in fixtures.items():
            account = an_account(brazos, marcus, account_no=account_no, label=account_no)
            status = enroll(marcus, account, trailing_actuals=(total,))
            assert status.level == expected, account_no

        assert budget_service.status_queryset().count() == 3


def test_us_bil_018_tc4__a_plan_without_the_budget_flag_is_refused(brazos, marcus):
    """BR-RAT-043: budget billing rides the plan flag, and the refusal says so.

    Checked BEFORE the history, deliberately: an account on a plan that does not
    offer budget billing is not "nearly eligible", and telling them "9/12
    months" would send them away to wait for an answer that will still be no.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        with pytest.raises(budget_service.BudgetRuleError, match="does not offer budget"):
            enroll(marcus, account, plan_offers_budget=False, months_of_history=3)


def test_us_bil_018_tc5__an_account_cannot_be_enrolled_twice(brazos, marcus):
    """One live budget status per account — two levels and no rule for which
    one is charged is not a state the product may reach."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enroll(marcus, account)
        with pytest.raises(budget_service.BudgetRuleError, match="already on budget billing"):
            enroll(marcus, account)
        assert budget_service.status_queryset().count() == 1


@pytest.mark.isolation
def test_us_bil_018_tc6__budget_status_never_crosses_a_tenant(brazos, marcus, lonestar, erin):
    """Lone Star Ridge's parameters, histories and levels are its own (RLS).

    Both halves: Brazos cannot SEE Lone Star's row, and Lone Star's own
    eligibility setting (9) does not reach Brazos's enrolment.
    """
    with tenant_ctx(lonestar):
        set_budget_settings(erin, lonestar, eligibility_months=9)
        # Lone Star Ridge has only Water enabled — the two tenants are
        # deliberately not identical (BR-TEN-026).
        lone_account = an_account(lonestar, erin, account_no="LSR-1", service="water")
        budget_service.enroll(
            actor=erin,
            account_id=lone_account.id,
            trailing_actuals=(Decimal("2160"),),
            months_of_history=9,
            plan_offers_budget=True,
            currency="USD",
            on_date=ENROLLED_ON,
        )
        assert budget_service.status_queryset().count() == 1

    with tenant_ctx(brazos):
        # Brazos sees none of it…
        assert budget_service.status_queryset().count() == 0
        # …and Lone Star's 9-month window does not apply here: 9 months of
        # history is still ineligible under Brazos's own seeded 12.
        account = an_account(brazos, marcus)
        with pytest.raises(budget_service.BudgetRuleError, match="9/12 months"):
            enroll(marcus, account, months_of_history=9)

    # The tenant column itself, checked rather than assumed — and read under
    # Lone Star's own context, because on a connection RLS applies to a
    # `filter(tenant_id=…)` taken with `app.tenant_id` unset returns zero
    # whatever the column says. Deny-by-default is doing that, not a missing row.
    with tenant_ctx(lonestar):
        assert models.AccountBudgetStatus.objects.filter(tenant_id=lonestar.id).count() == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@e9d5a48 (05-golden-tests.md + EP-BIL-05-budget-billing.md + 07-billing/02-business-rules.md + 07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's Budget Bills tab has no endpoint; REPORTED) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: TC-3 asserts the prototype's own three levels ($237 / $343 / $91)
#         computed from its own three trailing-12 totals — those are
#         PROTOTYPE-sourced figures (S30 step 2), not B5 ones, and the whole-$
#         rounding is what makes 2,846.40 ÷ 12 = 237.20 land on 237.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
