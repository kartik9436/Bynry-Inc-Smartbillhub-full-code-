# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10694 (lockbox audit LBX-05) · migration payments/0053
# Rules:    CLAUDE.md rule 4 (append-only explanations) · rule 6 (one line ↔
#           one reversal, in the DATABASE) · hard-won law 14 (proved on
#           PostgreSQL, under a NON-superuser role)
# ───────────────────────────────────────────────────────
"""The database half of LBX-05 — what the service promises, the schema keeps.

Every refusal here is a raw cursor INSERT/UPDATE that bypasses the service.
And one atomicity proof: a match that reverses the cheque and then cannot post
leaves NO reversal behind, and the connection is still usable afterwards
(hard-won law 14 — on SQLite a broken version of this passes).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from apps.payments import bankrec_models as bankrec
from apps.payments import ledger_seam, models, reconciliation
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_lbx05_09_statement_lines_post import (
    WORKED_AT,
    import_the_statement,
    line,
    the_lockbox_day,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def _raw(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def test_pg_the_role_is_not_a_superuser():
    """RLS FORCE and the triggers mean nothing to a superuser — say which we are."""
    with connection.cursor() as cursor:
        cursor.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        assert cursor.fetchone() == (False, False)


def test_pg_one_line_one_reversal_one_entry(brazos, dana):
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = import_the_statement(dana, brazos).statement_import_id
        ret1 = line(statement_id, "RET1029-01")
        ret2 = line(statement_id, "RET1029-02")
        matched = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret1.pk, payment_id=payments["4102"].pk, occurred_at=WORKED_AT
        )
        row = bankrec.BankRecResolution.objects.get(pk=matched.resolution_id)
        insert = (
            "INSERT INTO bank_rec_resolutions (id, tenant_id, bank_line_id, reason_code, "
            "gl_account_id, amount, journal_entry_id, reversal_payment_id, created_at) "
            "VALUES (%s, %s, %s, 'returned_item', %s, -76.40, %s, %s, now())"
        )
        # a second explanation of the SAME line
        with pytest.raises(IntegrityError, match="uq_bank_rec_resolutions_line"), transaction.atomic():
            _raw(insert, [uuid.uuid4(), brazos.pk, ret1.pk, row.gl_account_id, None, None])
        # the SAME reversal on another line
        with pytest.raises(IntegrityError, match="uq_bank_rec_resolutions_reversal"), transaction.atomic():
            _raw(
                insert,
                [uuid.uuid4(), brazos.pk, ret2.pk, row.gl_account_id, None, row.reversal_payment_id],
            )
        # the SAME journal entry claimed by another line
        with pytest.raises(IntegrityError, match="uq_bank_rec_resolutions_line_entry"), transaction.atomic():
            _raw(insert, [uuid.uuid4(), brazos.pk, ret2.pk, row.gl_account_id, row.journal_entry_id, None])
        # and the row itself is still append-only (payments/0005's trigger)
        with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
            _raw("UPDATE bank_rec_resolutions SET note = 'x' WHERE id = %s", [row.pk])


def test_pg_a_match_that_cannot_post_leaves_no_reversal(brazos, dana, monkeypatch):
    """Reverse-then-post is ONE transaction: a refused posting takes the reversal with it."""
    with tenant_ctx(brazos):
        payments, _batch = the_lockbox_day(dana, brazos)
        statement_id = import_the_statement(dana, brazos).statement_import_id
        ret2 = line(statement_id, "RET1029-02")

        def refuse(**_kwargs):
            raise PaymentRuleError("refused for the proof", br_ref="BR-PAY-019")

        monkeypatch.setattr(ledger_seam, "post_bank_line_settlement", refuse)
        with pytest.raises(PaymentRuleError, match="refused for the proof"):
            reconciliation.match_returned_line(
                actor=dana, bank_line_id=ret2.pk, payment_id=payments["4103"].pk,
                occurred_at=WORKED_AT,
            )
        # The connection is NOT poisoned, and nothing of the attempt survived.
        assert not models.Payment.objects.filter(reverses_payment=payments["4103"]).exists()
        assert not bankrec.BankRecResolution.objects.filter(bank_line=ret2).exists()
        monkeypatch.undo()
        done = reconciliation.match_returned_line(
            actor=dana, bank_line_id=ret2.pk, payment_id=payments["4103"].pk, occurred_at=WORKED_AT
        )
        assert done.reversed_now and done.posted
