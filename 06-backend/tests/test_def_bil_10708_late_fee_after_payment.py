"""DEF-BIL-10708 — a bill run may not issue a late fee a payment has since cancelled.

The tester's case (payments audit L2-06, 2026-10-30): *"Xander Xanthos paid at
Hy-Vee on 21 Oct, a day before his due date. The file arrived after the bill
run had started; the run still listed him for a $5.00 late fee … If the run had
been issued, he would be charged."*

Moved onto this suite's June run (bill date 1 Jul): Xander's **$226.00** bill
was due **10 Jun** (grace to 15 Jun) and nothing was on file when the run
worked out his bill, so it carried **$5.00** (max($5.00, 1.5% × $226.00 =
$3.39)). His payment, made **9 Jun** — before the due date — is then loaded.
BR-BIL-071 judges lateness by when the money arrived, so the fee is not owed.

PROVED RED (hard-won law 7), on SQLite, with the tip's `runs.py` and
`check_store.py` swapped back in:
  * `test_the_release_gate_itself_refuses` →
    `Failed: DID NOT RAISE BillingRuleError` — the defect itself: release
    authorised a $5.00 late fee the payment had cancelled;
  * the three cases naming `late_fee_drafts_paid_since` → `AttributeError`;
  * `test_find_account_matches_the_customer_name_…` →
    `assert [] == ['A-10712']` (number-only search).
Green on SQLite and on PostgreSQL 16 (throwaway cluster, non-superuser role).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import release, runs
from apps.billing.exceptions import BillingRuleError

from tests.test_def_719_late_fee_charge_code import a_mapped_late_fee_code
from tests.test_def_bil_10200_late_fee_in_the_bill_run import (
    a_payment,
    a_run,
    an_earlier_bill,
    an_overdue_account,
    calculate,
    fee_lines,
    late_findings,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _xander(brazos, dana, *, no="10708"):
    a_mapped_late_fee_code(brazos)
    cycle, account = an_overdue_account(brazos, dana, no=no)
    bill = an_earlier_bill(brazos, account, total="226.00", due=date(2026, 6, 10))
    run = a_run(cycle)
    found = late_findings(run)[f"A-{no}"]
    assert found["params"]["amount"] == "5.00"
    calculate(run)
    _draft, fees = fee_lines(run, account)
    assert [fee.amount for fee in fees] == [Decimal("5.00")]
    return run, account, bill


def test_a_payment_after_drafting_refuses_release_naming_one_account(brazos, dana):
    with tenant_ctx(brazos):
        run, account, bill = _xander(brazos, dana)
        runs.refuse_stale_drafts(run)  # nothing has moved yet

        a_payment(brazos, account, bill, amount="226.00", cleared=date(2026, 6, 9))

        assert runs.late_fee_drafts_paid_since(run) == (str(account.id),)
        with pytest.raises(BillingRuleError) as refused:
            runs.refuse_stale_drafts(run)
        assert "re-check 1 account(s)" in str(refused.value)

        # Re-working his bill clears it, and the $5.00 is gone.
        runs.reprice_accounts(bill_run=run, account_ids=[str(account.id)])
        _draft, fees = fee_lines(run, account)
        assert fees == []
        assert runs.late_fee_drafts_paid_since(run) == ()
        runs.refuse_stale_drafts(run)


def test_the_release_gate_itself_refuses(brazos, dana):
    """Law 2 — the check is WIRED into `authorise_release`, not merely written."""
    with tenant_ctx(brazos):
        run, account, bill = _xander(brazos, dana, no="10709")
        a_payment(brazos, account, bill, amount="226.00", cleared=date(2026, 6, 9))
        with pytest.raises(BillingRuleError) as refused:
            release.authorise_release(
                bill_run=run,
                summary=release.summary_for(run),
                confirmations=release.Confirmations(
                    compliance=True,
                    email_mandate=True,
                    sms_mandate=True,
                    autopay_mandate=True,
                    final=True,
                ),
                confirmed_by=dana.user.id,
                confirmed_at=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            )
        assert "re-check 1 account(s)" in str(refused.value)


def test_a_late_payment_still_owes_the_fee_after_the_re_check(brazos, dana):
    """BR-BIL-071 cuts both ways: money that arrived AFTER grace still leaves
    the fee due, so the re-worked bill keeps its $5.00 and the gate opens."""
    with tenant_ctx(brazos):
        run, account, bill = _xander(brazos, dana, no="10710")
        a_payment(brazos, account, bill, amount="226.00", cleared=date(2026, 6, 20))
        assert runs.late_fee_drafts_paid_since(run) == (str(account.id),)

        runs.reprice_accounts(bill_run=run, account_ids=[str(account.id)])
        _draft, fees = fee_lines(run, account)
        assert [fee.amount for fee in fees] == [Decimal("5.00")]
        runs.refuse_stale_drafts(run)


def test_a_payment_on_an_account_with_no_late_fee_does_not_stop_the_run(brazos, dana):
    """Only a late-fee draft is affected: usage and base are not payment facts."""
    with tenant_ctx(brazos):
        _cycle, account = an_overdue_account(brazos, dana, no="10711")
        bill = an_earlier_bill(brazos, account, total="40.00", due=date(2026, 6, 28))
        run = a_run(_cycle)
        assert late_findings(run) == {}
        calculate(run)
        a_payment(brazos, account, bill, amount="40.00", cleared=date(2026, 6, 25))
        assert runs.late_fee_drafts_paid_since(run) == ()
        runs.refuse_stale_drafts(run)


# ── DEF-BIL-10709 (tester L3-07) — the late-fee list searches by name too ──────


def test_find_account_matches_the_customer_name_as_well_as_the_number(brazos, dana):
    """*Find account* typed "Xan" found nothing: the search read the account
    number only. It now matches the number OR the name, through customers'
    published search."""
    from apps.billing import check_store
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        run, account, _bill = _xander(brazos, dana, no="10712")
        customer_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Xander Xanthos", is_primary=True
        )
        by_name = check_store.tag_accounts(run, "late_fee", {"q": "Xan", "per": 50})
        assert [row["account_no"] for row in by_name["results"]] == ["A-10712"]
        by_number = check_store.tag_accounts(run, "late_fee", {"q": "10712", "per": 50})
        assert by_number["count"] == 1
        nobody = check_store.tag_accounts(run, "late_fee", {"q": "Halvorsen", "per": 50})
        assert nobody["count"] == 0


# ── DEF-BIL-10773 — the refusal reaches the screen with its count ─────────────


def test_def_bil_10773_the_refusal_names_its_own_key_and_the_count(brazos, dana):
    """Walked 2026-10-30: Sign off read *"Check the cycle and dates"* — the
    generic `billing.run.refused` — because this refusal named no key, and the
    count lived only in `detail`, which never reaches a screen (BR-SHL-020 r2).
    It now names `billing.run.recheckLateFees` and hands over the count."""
    from apps.billing import api as billing_api

    with tenant_ctx(brazos):
        run, account, bill = _xander(brazos, dana, no="10773")
        a_payment(brazos, account, bill, amount="226.00", cleared=date(2026, 6, 9))
        with pytest.raises(BillingRuleError) as refused:
            runs.refuse_stale_drafts(run)
        envelope = billing_api._as_catalog_refusal(refused.value, "BR-BIL-058")
        assert envelope.message_key == "billing.run.recheckLateFees"
        assert envelope.params["count"] == 1
        assert envelope.br_ref == "BR-BIL-071"
