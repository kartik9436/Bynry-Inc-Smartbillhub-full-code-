# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10744 — the returned-payment email said "Nothing has changed
#           on your account" and printed every figure blank; the letter was empty
# Ruling:   PO 2026-10-30 (payments audit L2-04, "Rest we will fix"); NSF fee and
#           Bank memo rulings of the same day
# Rules:    BR-PAY-013 · BR-NOT-015 · BR-NOT-024 (print floor) · B14 rule 35
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Ben Zabala's $63.00 cheque comes back: what the email and the letter say.

THE WORKED CASE (decision log 2026-10-30, audit L2-04): $63.00 reversed as
*Returned by the bank*, Bank memo **"NSF"**, the plan's NSF fee **$30.00** →
both documents name the $63.00, the memo, the $30.00 fee and the new balance
**$93.00**, and neither says *"Nothing has changed on your account"*.

RED FIRST (law 7): against the tip before this change, `tc1` failed on the
queued row's `render_context` being `None` (every figure printed `——`), and
`tc2`'s letter would not render at all — `payment_failed_letter` had no
published version, so `render_for_dispatch` refused it.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a test that only read
`render_context` would pass with the old body still saying "Nothing has
changed" — so every case RENDERS the queued row through the real pinned
template, and asserts the false sentence is absent from the result.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from apps.customers import models as customer_models
from apps.notifications import models as nmodels
from apps.notifications import payment_returned_wording, rendering, seed_templates
from apps.notifications import template_models
from apps.payments import models, receipts, reversal

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_def_pay_10698_nsf_fee import _list_on_plan, _nsf_code, _plan_of
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill

pytestmark = pytest.mark.django_db

CHEQUE = D("63.00")
FEE = D("30.00")
RETURNED_ON = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)
FALSE_SENTENCE = "Nothing has changed on your account"


def _ben(brazos, dana, *, account_no, asset_no, fee_on_plan=True):
    account = a_one_time_account(brazos, dana, account_no=account_no, asset_no=asset_no)
    charge = _nsf_code(brazos)
    if fee_on_plan:
        _list_on_plan(brazos, _plan_of(account), charge)
    customer_models.Contact.objects.create(
        tenant=brazos,
        account=account,
        full_name="Ben Zabala",
        email="ben.zabala@example.com",
        is_primary=True,
    )
    an_issued_bill(
        brazos,
        account,
        number=f"BL-{account_no}",
        total=CHEQUE,
        issued_on=date(2026, 10, 1),
        due_date=date(2026, 10, 21),
    )
    recorded = a_payment(dana, account, amount=CHEQUE, confirmation="5517")
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _bounce(actor, payment, **overrides):
    values = dict(
        payment_id=payment.pk,
        returned_on=RETURNED_ON,
        reason=models.REVERSAL_REASON_NSF,
        idempotency_reference=uuid.uuid4(),
        bank_memo="NSF",
    )
    values.update(overrides)
    return reversal.reverse_payment(actor, **values)


def _rows(result):
    return {
        row.channel: row
        for row in nmodels.OutboundMessage.objects.filter(source_id=result.reversal_id)
    }


def _open(account):
    from apps.payments import billing_seam

    position = billing_seam.open_invoices_for_account(account.pk)
    return sum((invoice.balance for invoice in position.invoices), D("0"))


def _flat(text):
    return re.sub(r"\s+", " ", text or "")


def test_def_pay_10744_tc1__the_email_names_the_bounce_the_memo_the_fee_and_the_balance(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _account, cheque = _ben(brazos, dana, account_no="A-10739", asset_no="M-10739")
        result = _bounce(dana, cheque)
        assert result.nsf_fee_status == "charged" and result.nsf_fee_amount == FEE

        email = _rows(result)[nmodels.CHANNEL_EMAIL]
        assert email.template_code == receipts.FAILED_PAYMENT_TEMPLATE_CODE
        context = email.render_context or {}
        assert context, "the bounce notice must carry its figures (it carried none)"

        rendered = rendering.render_for_dispatch(email)
        body = _flat(rendered.body)
        assert FALSE_SENTENCE not in body
        assert "$63.00" in body, body
        assert "Bank memo NSF" in body, body
        assert "Returned payment fee $30.00" in body, body
        assert "Check or reference 5517" in body, body
        assert "Hi Ben," in body, body
        # The balance is the BOOKS' (`receipts._ar_balance`, the receipt
        # email's own figure) read after the bounce and the fee. This fixture
        # issues its bill without posting it to AR, so the books hold only
        # what the bounce and the fee posted; billing's own open position is
        # the worked $93.00 ($63.00 owed again + the $30.00 fee bill).
        assert context.get("balance") is not None, "the books answered a balance"
        assert "Your balance is now $" in body, body
        assert _open(_account) == D("93.00")
        assert "returned by your bank" in (rendered.subject or ""), rendered.subject


def test_def_pay_10744_tc2__the_printed_letter_has_words_and_the_same_figures(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _account, cheque = _ben(brazos, dana, account_no="A-10740", asset_no="M-10740")
        result = _bounce(dana, cheque)
        letter = _rows(result)[nmodels.CHANNEL_PRINT]
        assert letter.template_code == receipts.FAILED_PAYMENT_LETTER_TEMPLATE_CODE
        assert letter.template_version is not None, "the letter is pinned to a published body"
        body = _flat(rendering.render_for_dispatch(letter).body)
        assert "Dear Ben Zabala," in body, body
        assert "Account A-10740" in body, body
        assert "Bank memo NSF" in body and "Returned payment fee $30.00" in body, body
        assert FALSE_SENTENCE not in body


def test_def_pay_10744_tc3__no_fee_on_the_plan_prints_no_fee_line_never_zero(
    brazos, dana, marcus
):
    """The fee paragraph is OPTIONAL: no NSF code on the plan → no fee line at
    all. A customer is never told about a `$0.00` fee."""
    with tenant_ctx(brazos):
        _account, cheque = _ben(
            brazos, dana, account_no="A-10741", asset_no="M-10741", fee_on_plan=False
        )
        result = _bounce(dana, cheque, bank_memo=None)
        assert result.nsf_fee_status == "nsf_fee_not_set_on_plan"
        body = _flat(rendering.render_for_dispatch(_rows(result)[nmodels.CHANNEL_EMAIL]).body)
        assert "Returned payment fee" not in body, body
        assert "fee $0.00" not in body, body
        assert "Bank memo" not in body, "no memo given, no memo line"
        assert "$63.00" in body and FALSE_SENTENCE not in body


def test_def_pay_10744_tc4__both_classes_are_seeded_in_every_registry_language(brazos):
    with tenant_ctx(brazos):
        for code in (receipts.FAILED_PAYMENT_TEMPLATE_CODE, "payment_failed_letter"):
            languages = set(
                template_models.NotificationTemplate.objects.filter(
                    tenant_id=brazos.id, code=code
                ).values_list("language", flat=True)
            )
            assert set(payment_returned_wording.WORDING[code]) <= languages, (code, languages)


def test_def_pay_10744_tc5__no_language_says_nothing_changed_and_the_optional_lines_stand_alone():
    """Every variant: the optional tokens each sit alone in their own paragraph
    (else the renderer would drop a neighbour), and every token is in the
    class's palette."""
    from apps.notifications import catalogs

    for code, table in payment_returned_wording.WORDING.items():
        palette = catalogs.catalog_for(code)
        assert palette is not None, code
        for language, (subject, body) in table.items():
            used = set(re.findall(r"{(\w+)}", body + (subject or "")))
            assert used <= set(palette.tokens), (code, language, used - set(palette.tokens))
            for token in palette.optional:
                paragraphs = [p for p in body.split("\n\n") if "{" + token + "}" in p]
                assert len(paragraphs) == 1, (code, language, token)
                assert re.findall(r"{(\w+)}", paragraphs[0]) == [token], (code, language, token)
    assert seed_templates.EMAIL_PAYMENT_FAILED_BODY == (
        payment_returned_wording.WORDING["email_payment_failed"]["en"][1]
    )


def test_def_pay_10744_tc6__the_migration_moves_only_an_untouched_seed():
    """`0038` freezes the old and new wording; the new must be today's `en`."""
    import importlib

    migration = importlib.import_module(
        "apps.notifications.migrations.0038_def_pay_10744_returned_payment_wording"
    )
    subject, body = payment_returned_wording.WORDING["email_payment_failed"]["en"]
    assert (migration.NEW_SUBJECT, migration.NEW_BODY) == (subject, body)
    assert FALSE_SENTENCE in migration.OLD_BODY
