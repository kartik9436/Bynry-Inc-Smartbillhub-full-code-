# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10764 (LBX-09 on screen) — the refusal named the line on the
#           server and the screen said "This payment can't be recorded as asked".
# Rulings:  decision log 2026-10-30, lockbox audit — LBX-09 (future and
#           out-of-period statement lines refused BY NAME)
# Rules:    B14 rule 33 (a FACT ≤ 6 words per sentence) · BR-PAY-019
# ───────────────────────────────────────────────────────
"""What reaches the screen when a statement line is refused, not only the sentence.

`reconciliation.import_bank_statement` named the line in English since
fb49fb1d0, but `api._as_catalog_refusal` sends every payments refusal as
`payments.record.refused`, whose catalogue sentence is about recording a
PAYMENT. So the import screen told the clerk to check "the date, amount and
account" of a payment, and never which statement line was wrong. These cases
assert the WIRE — the key and its params — which is what the screen renders.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from apps.payments import api as payments_api
from apps.payments import reconciliation
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import a_bank_account, a_statement

pytestmark = pytest.mark.django_db

CATALOGUE = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"


def _refusal(dana, brazos, rows, *, imported_at):
    with pytest.raises(PaymentRuleError) as caught:
        reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=a_bank_account(brazos, name="Lockbox").pk,
            period_start=date(2026, 10, 26),
            period_end=date(2026, 10, 31),
            payload=a_statement(rows),
            imported_at=imported_at,
        )
    return payments_api._as_catalog_refusal(caught.value)


def test_def_pay_10764__a_line_after_today_is_named_on_the_wire(brazos, dana):
    with tenant_ctx(brazos):
        wire = _refusal(
            dana,
            brazos,
            [("2026-10-27", "LBX4521-1026", "870.50"), ("2026-10-31", "FEE1031", "-24.00")],
            imported_at=datetime(2026, 10, 30, 16, 0, tzinfo=UTC),
        )
    assert wire.message_key == "payments.bankrec.line_after_import"
    assert wire.params["reference"] == "FEE1031"
    assert wire.params["date"] == "2026-10-31"
    assert "detail" in wire.params  # the English sentence still travels for the audit row


def test_def_pay_10764__a_line_outside_the_period_is_named_on_the_wire(brazos, dana):
    with tenant_ctx(brazos):
        wire = _refusal(
            dana,
            brazos,
            [("2026-10-25", "OLD-1", "10.00")],
            imported_at=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
        )
    assert wire.message_key == "payments.bankrec.line_outside_period"
    assert wire.params["reference"] == "OLD-1"
    assert wire.params["date"] == "2026-10-25"


def test_def_pay_10764__both_keys_are_in_the_catalogue_and_name_the_line():
    words = json.loads(CATALOGUE.read_text())
    for key in ("payments.bankrec.line_after_import", "payments.bankrec.line_outside_period"):
        assert "{{reference}}" in words[key], key
        for sentence in words[key].split(". "):
            assert len(sentence.split()) <= 6, (key, sentence)  # B14 rule 33, a FACT


def test_def_pay_10764__every_other_refusal_keeps_the_payment_key():
    wire = payments_api._as_catalog_refusal(PaymentRuleError("anything", br_ref="BR-PAY-019"))
    assert wire.message_key == "payments.record.refused"
