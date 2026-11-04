# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-020 (re-level at drift, per-account override ±30%)
#           Screens: S30 · S66/S69
# Rules:    BR-BIL-017 (auto re-level at ±20% drift each 6 mo; per-account
#           override bounded ±30% with reason + audit — every parameter a
#           tenant setting. ⚠ ITS OFF-BUDGET-AFTER-2-MISSED-PAYMENTS CLAUSE IS
#           **SUPERSEDED** — PO 2026-08-11, "nodrop we chase for payments until
#           write off") · BR-TEN-043 (config forward; event time is an
#           argument) · CLAUDE.md rule 7 (audit)
# ───────────────────────────────────────────────────────
"""US-BIL-020 §3 — re-level, override, and the drop-off that no longer exists.

TC-5 in the epic reads *"Second missed level payment → status → off_budget"*.
**That test case is superseded** by the PO's ruling of 2026-08-11 and this file
asserts the OPPOSITE, deliberately and with the ruling quoted: an account that
misses ten level payments is still enrolled, still on its level, and is chased
through collections to write-off. Leaving the old behaviour merely
unimplemented would let the next lane put it back.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import budget, budget_service, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account

pytestmark = pytest.mark.django_db

LEVEL = Decimal("242")  # ❄️ WE-8
ENROLLED_ON = date(2026, 6, 28)
SIX_MONTHS_ON = date(2027, 1, 4)  # J09 step 5's checkpoint
THREE_MONTHS_ON = date(2026, 9, 28)

# US-BIL-020 §4's drift fixtures: 250 is inside the ±20% band, 300 breaches it.
WITHIN_BAND = (Decimal("3000"),)  # 3,000 ÷ 12 = 250
BREACHES_BAND = (Decimal("3600"),)  # 3,600 ÷ 12 = 300


def enrolled(actor, account):
    return budget_service.enroll(
        actor=actor,
        account_id=account.id,
        trailing_actuals=(Decimal("2904"),),
        months_of_history=12,
        plan_offers_budget=True,
        currency="USD",
        on_date=ENROLLED_ON,
    )


def test_us_bil_020_tc1__at_cadence_and_inside_the_band_nothing_moves(brazos, marcus):
    """Recomputed 250 against a current 242 is 3.3% drift — inside ±20%.

    `last_leveled_at` still advances, because "we looked and it was fine" is the
    fact J09 step 5 asks for; the LEVEL does not.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enrolled(marcus, account)

        moved = budget_service.relevel(
            actor=marcus,
            account_id=account.id,
            trailing_actuals=WITHIN_BAND,
            on_date=SIX_MONTHS_ON,
        )
        assert moved is None
        status.refresh_from_db()
        assert status.level == LEVEL
        assert status.last_leveled_at == SIX_MONTHS_ON


def test_us_bil_020_tc2__a_drift_breach_at_cadence_re_levels_and_is_audited(
    brazos, marcus, audit_rows
):
    """Recomputed 300 against 242 is 24.0% — a breach. Old → new is audited."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enrolled(marcus, account)

        moved = budget_service.relevel(
            actor=marcus,
            account_id=account.id,
            trailing_actuals=BREACHES_BAND,
            on_date=SIX_MONTHS_ON,
        )
        assert moved is not None
        status.refresh_from_db()
        assert status.level == Decimal("300")

        row = [r for r in audit_rows if r["action"] == "budget.releveled"][-1]
        # The stored level carries the column's six decimals; the audit trail
        # records what was STORED rather than a display rounding of it.
        assert row["before"]["level"] == "242.000000"
        assert row["after"]["level"] == "300"

        # BR-TEN-043 / J09 step 5: the new level governs FORWARD only. The bill
        # events already written keep the level they were billed at.
        billed_levels = [
            e.level
            for e in budget_service.event_queryset().filter(event=models.BUDGET_EVENT_RELEVELED)
        ]
        assert billed_levels == [Decimal("300.000000")]


def test_us_bil_020_tc3__an_override_within_the_bound_is_accepted_with_its_reason(
    brazos, marcus, audit_rows
):
    """Computed 242, staff set **200** with "customer hardship request".

    The bound is 242 × 0.70 = **169.40** to 242 × 1.30 = **314.60** (OQ-068),
    and 200 is inside it. The COMPUTED level is kept alongside the override,
    because the bound is measured against the computed one.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-1042")
        status = enrolled(marcus, account)

        assert budget.override_bounds(computed_level=LEVEL, bound_pct=Decimal("30")) == (
            Decimal("169.40"),
            Decimal("314.60"),
        )

        budget_service.override_level(
            actor=marcus,
            account_id=account.id,
            override=Decimal("200"),
            reason="customer hardship request",
            on_date=THREE_MONTHS_ON,
        )
        status.refresh_from_db()
        assert status.level == LEVEL  # the computed level is NOT overwritten
        assert status.level_override == Decimal("200.000000")
        assert status.level_override_reason == "customer hardship request"
        assert budget_service.effective_level(status) == Decimal("200.000000")

        row = [r for r in audit_rows if r["action"] == "budget.overridden"][-1]
        assert row["after"]["reason"] == "customer hardship request"
        assert row["after"]["computed_level"] == "242.000000"

        # …and the customer now owes the OVERRIDE, not the computed level.
        facts = budget_service.record_bill(
            account_id=account.id, actual=Decimal("292.87"), on_date=date(2026, 10, 1)
        )
        assert facts.amount_due == Decimal("200.00")
        assert facts.variance_movement == Decimal("-92.87")  # 200 − 292.87


def test_us_bil_020_tc4__out_of_bound_and_reason_less_overrides_are_refused(brazos, marcus):
    """150 (below 169.40), 320 (above 314.60), and any override with no reason.

    The reason is checked FIRST and separately: "you must say why" and "that
    number is too low" are different corrections for the clerk to make.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enrolled(marcus, account)

        for bad in (Decimal("150"), Decimal("320")):
            with pytest.raises(ValueError, match=r"169\.40–314\.60"):
                budget_service.override_level(
                    actor=marcus,
                    account_id=account.id,
                    override=bad,
                    reason="customer hardship request",
                    on_date=THREE_MONTHS_ON,
                )

        for missing in (None, "", "   "):
            with pytest.raises(ValueError, match="requires a REASON"):
                budget_service.override_level(
                    actor=marcus,
                    account_id=account.id,
                    override=Decimal("200"),
                    reason=missing,
                    on_date=THREE_MONTHS_ON,
                )

        # Nothing was written by any of the five refusals.
        status = budget_service.status_for(account.id)
        assert status.level_override is None


def test_us_bil_020_tc5__nobody_is_dropped_off_budget_billing(brazos, marcus):
    """**PO ruling 2026-08-11, verbatim: "nodrop we chase for payments until
    write off".**

    The epic's own TC-5 says an account goes `off_budget` on the second missed
    level payment. That clause of BR-BIL-017 is SUPERSEDED, and this test
    asserts the replacement rather than leaving the old behaviour merely
    unbuilt: TEN misses later the account is still enrolled, still on its
    level, and still billed — collections chases it, and write-off is the end
    of the road, with a human on it.

    The undefined "missed payment" the old clause depended on became MOOT
    rather than answered, so there is no counter here to assert either. The
    absence is the rule.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        status = enrolled(marcus, account)

        for month in range(1, 11):
            budget_service.record_bill(
                account_id=account.id,
                actual=Decimal("292.87"),
                on_date=date(2027, ((month - 1) % 12) + 1, 1),
            )
        status.refresh_from_db()
        assert status.status == budget.STATUS_ENROLLED

        # There is no drop-off API to call, and no miss counter to read.
        assert not hasattr(budget_service, "record_missed_level_payment")
        assert not hasattr(budget, "missed_payment")
        assert not any(
            field.name in ("missed_count", "missed_payments")
            for field in models.AccountBudgetStatus._meta.get_fields()
        )


def test_us_bil_020_tc5b__a_staff_removal_is_the_only_way_off_and_carries_the_variance(
    brazos, marcus, audit_rows
):
    """S30's "Remove from budget" — a decision with a name on it.

    US-BIL-020 §5: the variance balance is CARRIED, *"never silently dropped"*.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        status = enrolled(marcus, account)
        budget_service.record_bill(
            account_id=account.id, actual=Decimal("292.87"), on_date=date(2026, 7, 1)
        )

        budget_service.remove_from_budget(
            actor=marcus,
            account_id=account.id,
            reason="customer asked to leave the programme",
            on_date=date(2026, 10, 1),
        )
        status.refresh_from_db()
        assert status.status == budget.STATUS_OFF_BUDGET
        assert status.variance_balance == Decimal("-50.87")  # carried, not cleared

        row = [r for r in audit_rows if r["action"] == "budget.removed"][-1]
        assert row["after"]["variance_balance_carried"] == "-50.87"
        assert row["after"]["reason"] == "customer asked to leave the programme"

        # …and the next bill is plain actuals: the account is no longer enrolled,
        # so the pipeline's call returns None.
        assert (
            budget_service.record_bill(
                account_id=account.id, actual=Decimal("184.20"), on_date=date(2026, 11, 1)
            )
            is None
        )


def test_us_bil_020_tc6__a_mid_cadence_job_call_is_a_no_op(brazos, marcus):
    """A re-level changes what a customer pays and must not be triggerable by
    calling a function more often. The manual S30 row action still works."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        status = enrolled(marcus, account)

        # Three months in, with a 24% breach: the DRIFT is there, the cadence
        # is not.
        assert (
            budget_service.relevel(
                actor=marcus,
                account_id=account.id,
                trailing_actuals=BREACHES_BAND,
                on_date=THREE_MONTHS_ON,
            )
            is None
        )
        status.refresh_from_db()
        assert status.level == LEVEL

        # BR-BIL-017 allows the manual row action, audited — it skips the
        # CADENCE gate and nothing else.
        assert (
            budget_service.relevel(
                actor=marcus,
                account_id=account.id,
                trailing_actuals=BREACHES_BAND,
                on_date=THREE_MONTHS_ON,
                manual=True,
            )
            is not None
        )
        status.refresh_from_db()
        assert status.level == Decimal("300")


@pytest.mark.isolation
def test_us_bil_020_tc7__overrides_and_parameters_evaluate_per_tenant(
    brazos, marcus, lonestar, erin
):
    """Lone Star Ridge's own settings and status rows only (RLS).

    Its override bound is widened to 50%, and an override Brazos would refuse
    is accepted there — the parameter is read per tenant, never once.
    """
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(lonestar):
        tenancy_services.save_settings_family(erin, "budget-billing", {"override_bound_pct": 50})
        lone = an_account(lonestar, erin, account_no="LSR-1", service="water")
        budget_service.enroll(
            actor=erin,
            account_id=lone.id,
            trailing_actuals=(Decimal("2904"),),
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=ENROLLED_ON,
        )
        # 242 × 0.50 = 121.00 → the floor is 121.00 here.
        budget_service.override_level(
            actor=erin,
            account_id=lone.id,
            override=Decimal("150"),
            reason="hardship",
            on_date=THREE_MONTHS_ON,
        )
        assert budget_service.status_for(lone.id).level_override == Decimal("150.000000")

    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        enrolled(marcus, account)
        # The same 150 is refused here, under Brazos's own seeded 30%.
        with pytest.raises(ValueError, match=r"169\.40–314\.60"):
            budget_service.override_level(
                actor=marcus,
                account_id=account.id,
                override=Decimal("150"),
                reason="hardship",
                on_date=THREE_MONTHS_ON,
            )
        assert budget_service.status_queryset().count() == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-020@e9d5a48 (05-golden-tests.md + EP-BIL-05-budget-billing.md + 07-billing/02-business-rules.md + 07-billing/08-worked-examples.md)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S30's Budget Bills tab has no endpoint; REPORTED) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: THE EPIC'S OWN TC-5 IS SUPERSEDED and this file asserts the
#         opposite. US-BIL-020 §3 TC-5 reads "Second missed level payment →
#         status → off_budget"; the PO ruled on 2026-08-11 "nodrop we chase for
#         payments until write off", so `tc5` here asserts that ten misses
#         change nothing and that no miss counter exists. The epic text is
#         stamped SUPERSEDED in the same commit — a test that quietly stopped
#         covering a written test case would be the gap this states instead.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
