# ── Trace ──────────────────────────────────────────────
# Task:    one-time bill build plan B11 (hardening issue) + B13's due-terms
#          wording (04-docs/05-modules/07-billing/12-one-time-bill-build-plan.md)
# Code:    apps/billing/issue.py (🔒) :: issue_run, _issue_one, derive_due_date
# Rules:   BR-BIL-058 (the release gate) · BR-BIL-055 (one bill breaks, the rest
#          go) · BR-BIL-024 (the due date is derived, never guessed) ·
#          hard-won law 14 (a failed statement poisons a PostgreSQL transaction)
# ───────────────────────────────────────────────────────
"""Three things issue must do and did not.

1. **A RELEASE ROW THAT HAS ALREADY BEEN RELEASED AUTHORISES NOTHING MORE.**
   `release.release_run` refuses a row whose `released_at` is stamped; the
   issue gate did not ask the same question, so a direct call to issue after
   the release had completed walked straight through.
2. **A FAILURE THAT IS NOT A RULE BREAKS ONE BILL, NOT THE PASS.** A
   `RuntimeError` (`frozen_bill.NotFrozen` is one) escaped the loop and
   abandoned every bill after it. On PostgreSQL a DATABASE error is worse: the
   whole transaction is poisoned unless each bill has its own savepoint.
   `test_a_database_error_on_one_bill…` is the law-14 proof and is only
   meaningful on PostgreSQL — the suite's SQLite has no aborted state.
3. **A CYCLE-LESS RUN IS NOT TOLD ABOUT A CYCLE.** Its due-terms refusal
   carries its own key, `billing.issue.noDueTerms`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from django.db import connection

from apps.billing import issue, models
from apps.billing.exceptions import BillingRuleError

from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def _issue(run):
    return issue.issue_run(
        run, issued_at=ISSUED_AT, template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION
    )


def _three_drafts(brazos, dana, run):
    return [
        a_priced_draft(
            brazos,
            an_account(dana, brazos, account_no=f"A-11{n}"),
            run,
            invoice_no=f"BL-2607-00011{n}",
        )
        for n in (1, 2, 3)
    ]


# ── 1 · the gate ───────────────────────────────────────────────────────────


# BULK-CHG-8
def test_B11_an_already_RELEASED_row_does_not_authorise_another_issue(brazos, dana):
    """RED on the tip: the draft issued, because the gate asked only for the
    four confirmations and never for `released_at IS NULL`."""
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        models.BillRunRelease.objects.filter(bill_run=run).update(
            released_at=datetime(2026, 7, 2, 9, 0, tzinfo=UTC)
        )
        draft = a_priced_draft(brazos, an_account(dana, brazos), run)

        with pytest.raises(BillingRuleError, match="no authorised release"):
            _issue(run)
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT


# BULK-CHG-8
def test_B11_an_unreleased_row_still_authorises(brazos, dana):
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, an_account(dana, brazos), run)
        result = _issue(run)
    assert result.issued == (str(draft.pk),) or list(result.issued) == [str(draft.pk)]


# ── 2 · one bill's unexpected failure ──────────────────────────────────────


def _failing_on(monkeypatch, invoice_no, fault):
    real = issue.issue_invoice

    def flaky(invoice, **kwargs):
        if invoice.invoice_no == invoice_no:
            fault()
        return real(invoice, **kwargs)

    monkeypatch.setattr(issue, "issue_invoice", flaky)


# BULK-CHG-8
def test_B11_a_RuntimeError_on_one_bill_breaks_that_bill_only(brazos, dana, monkeypatch):
    """RED on the tip: `RuntimeError: kept copy missing` escaped `issue_run`,
    so the third bill was never tried and no break named the second."""

    def boom():
        raise RuntimeError("kept copy missing")

    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        first, second, third = _three_drafts(brazos, dana, run)
        _failing_on(monkeypatch, second.invoice_no, boom)

        result = _issue(run)

        assert set(result.issued) == {str(first.pk), str(third.pk)}
        assert [b.reason for b in result.broken] == [issue.ISSUE_FAILED_UNEXPECTEDLY]
        assert result.broken[0].invoice_no == second.invoice_no
        assert "RuntimeError" in result.broken[0].detail
        assert models.Invoice.objects.get(pk=second.pk).status == models.INVOICE_DRAFT


# BULK-CHG-8
def test_B11_a_database_error_on_one_bill_does_not_poison_the_rest(brazos, dana, monkeypatch):
    """Hard-won law 14. The fault is a REAL failed statement, executed inside
    the test's own transaction. Without a savepoint per bill, PostgreSQL
    aborts that transaction and the third bill fails with
    `InFailedSqlTransaction` — or the pass is abandoned outright. SQLite has no
    aborted state, so this case proves the savepoint only on PostgreSQL."""

    def bad_sql():
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM a_table_that_does_not_exist_b11")

    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        first, second, third = _three_drafts(brazos, dana, run)
        _failing_on(monkeypatch, second.invoice_no, bad_sql)

        result = _issue(run)

        assert set(result.issued) == {str(first.pk), str(third.pk)}
        assert [b.reason for b in result.broken] == [issue.ISSUE_FAILED_UNEXPECTEDLY]
        # The transaction is still usable afterwards.
        assert models.Invoice.objects.get(pk=third.pk).status != models.INVOICE_DRAFT


# ── 3 · B13 — a cycle-less run's due-terms refusal ─────────────────────────


def test_B13_derive_due_date_names_no_cycle_for_a_cycle_less_bill():
    with pytest.raises(BillingRuleError) as refusal:
        issue.derive_due_date(date(2026, 8, 1), None, cycle_less=True)
    assert refusal.value.message_key == "billing.issue.noDueTerms"
    assert "cycle carries" not in str(refusal.value)
    # The cycle wording is unchanged for a cycle run.
    with pytest.raises(BillingRuleError, match="the cycle carries no"):
        issue.derive_due_date(date(2026, 8, 1), None)


def test_B13_a_cycle_less_run_with_no_terms_breaks_with_its_own_key(brazos, dana):
    """RED on the tip: the break read *"the cycle carries no bill date and
    due-days pair"* for a run that has no cycle at all."""
    with tenant_ctx(brazos):
        run = an_authorised_run(brazos, dana)
        account = an_account(dana, brazos)
        # A one-time run: scoped to ONE account and no cycle (`ck_bill_runs_has_a_scope`).
        models.BillRun.objects.filter(pk=run.pk).update(
            cycle=None, scope_account=account, bill_date=None, due_days=None
        )
        run.refresh_from_db()
        draft = a_priced_draft(brazos, account, run)

        result = _issue(run)

        assert result.issued == () or list(result.issued) == []
        assert result.broken[0].reason == issue.ISSUE_NO_DUE_TERMS
        assert "cycle" not in result.broken[0].detail
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
