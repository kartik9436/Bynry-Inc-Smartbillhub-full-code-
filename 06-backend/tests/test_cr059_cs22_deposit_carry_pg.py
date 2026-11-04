# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-22 (task 33) — the deposit carry-forward, proved on a
#           real PostgreSQL 16 rather than on the in-memory SQLite the default
#           suite runs (CLAUDE.md hard-won law 14).
# Story:    US-CUS-004 / US-CUS-007   Screens: task 34's, not this lane's
# Rules:    CLAUDE.md rule 1 (RLS FORCE) · rule 4 (financial immutability, and
#           `journal_entry_id` as its ONE write-once door) · rule 5 (a movement
#           that cannot reach the books does not happen) · rule 6 · rule 7 ·
#           BR-CUS-670 (the deposit register) · BR-LED-007 (the tie-out)
# Tests:    this file · test_cr059_cs22_deposit_carry_forward.py
# ───────────────────────────────────────────────────────
"""CS-22 on PostgreSQL — the three things SQLite cannot show.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS AND WHY IT FAILS RATHER THAN SKIPS
═══════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`.
SQLite has **no aborted-transaction state**, **no row-level security**, and
**none of the immutability triggers** `payments/0006` installs — so a carry that
would be refused outright by a real database passes the whole default suite
green and fails the first time a clerk presses the button in production. That is
hard-won law 14, and these are the three shapes of it this change can take:

  1. **The immutability trigger.** The carry stamps `journal_entry_id` on a
     CLEARED payment row, and hard rule 4 forbids UPDATE on such a row. It is
     lawful only because `journal_entry_id` is the ONE write-once door
     `payments/0006` names by name — and *"a comment claiming a guarantee is not
     the guarantee"* (law 1), so it is asserted against the real trigger here.
  2. **The rollback.** `_transfer_between_accounts` claims *"all of it or none
     of it"*. On SQLite a half-made carry is hard to produce; on PostgreSQL a
     failure after the register moved and before the books are written would
     leave the customer's deposit released from one account and arriving at
     none, and both rows are immutable the instant they commit.
  3. **The lock.** `record_deposit_movement` takes `select_for_update()` on the
     account. SQLite serialises writers and cannot show it; PostgreSQL can.

**A SKIP WOULD READ AS COVERAGE IN A RUN SUMMARY. A FAILURE NAMES THE GAP.**

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    python -m pytest tests/test_cr059_cs22_deposit_carry_pg.py --reuse-db
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.db import connection as db_connection

from apps.ledger import models as ledger_models, tie_out
from apps.payments import models, transfer
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr059_cs22_deposit_carry_forward import (
    CARRIED_AT,
    REASON,
    THE_DEPOSIT,
    ZERO,
    _deposit_tie_out,
    _received_on,
    _register,
    a_customer_who_moved,
)

# Plain `django_db`, matching `test_cr059_cs36_restatement_pg.py`. The service's
# own `transaction.atomic()` becomes a SAVEPOINT of the test's transaction, and
# rolling back to a savepoint is exactly the production behaviour pg2 asserts —
# `transaction=True` would truncate between cases and prove nothing extra.
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _refuse_on_sqlite():
    """Hard-won law 14 — a skip would read as coverage. This reads as a gap."""
    assert db_connection.vendor == "postgresql", (
        "this file proves CS-22 against a real PostgreSQL 16: the immutability "
        "trigger, the rollback and the row lock do not exist on SQLite, so a "
        "green run here on SQLite would prove nothing at all. Run it with "
        "DJANGO_SETTINGS_MODULE=config.settings.local against PostgreSQL."
    )


def test_cs22_pg1__the_carry_completes_under_the_real_immutability_trigger(brazos, dana):
    """**The whole carry lands on a real database, triggers and RLS included.**

    Hard rule 4's trigger refuses every column change on a payment row that is
    not `processing`, and this carry stamps `journal_entry_id` on a CLEARED row
    moments after creating it. It is lawful because that column is the ONE
    write-once door the trigger allows — and asserting it here is what turns
    that sentence from a comment into a guarantee (law 1).

    On SQLite this case proves nothing: there is no trigger to be refused by.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )

        assert carried.journal_entry_id is not None, (
            "the destination row carries no journal entry — the write-once stamp was refused "
            "by the immutability trigger, which SQLite has none of"
        )
        stamped = models.Payment.objects.get(pk=carried.destination_payment_id)
        assert str(stamped.journal_entry_id) == str(carried.journal_entry_id)
        assert stamped.purpose == models.PURPOSE_DEPOSIT
        assert _register(old.pk) == ZERO and _register(new.pk) == THE_DEPOSIT
        row = _deposit_tie_out()
        assert row.gl == row.register == THE_DEPOSIT and row.state == tie_out.STATE_AGREED


def test_cs22_pg2__a_carry_that_cannot_reach_the_books_does_not_happen(brazos, dana, monkeypatch):
    """**All of it or none of it — and "none" means the REGISTER too.**

    The register move happens BEFORE the ledger call, so a refusal from the
    books must unwind it. If it did not, the customer's deposit would be
    released from the closed account and arrive at no account at all: $150.00
    the utility no longer records holding for anybody, on two payment rows hard
    rule 4 makes immutable the moment they commit.

    Every figure is asserted on BOTH sides, because the failure mode is
    asymmetric — the source is the one that was emptied first.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        payments_before = models.Payment.objects.count()
        entries_before = ledger_models.JournalEntry.objects.count()

        def _the_books_refuse(**_kwargs):
            raise PaymentRuleError("the books refused this movement", br_ref="BR-LED-001")

        monkeypatch.setattr(transfer.ledger_seam, "post_account_transfer", _the_books_refuse)
        with pytest.raises(PaymentRuleError, match="the books refused"):
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=new.pk,
                moved_on=CARRIED_AT,
                reason=REASON,
                idempotency_reference=uuid.uuid4(),
            )

        assert _register(old.pk) == THE_DEPOSIT, (
            "the deposit was released from the closed account and the books then refused — "
            "the customer's $150.00 is now held against no account at all"
        )
        assert _register(new.pk) == ZERO
        assert _received_on(new.pk) is None
        assert models.Payment.objects.count() == payments_before
        assert ledger_models.JournalEntry.objects.count() == entries_before
        row = _deposit_tie_out()
        assert row.gl == row.register == THE_DEPOSIT and row.state == tie_out.STATE_AGREED


def test_cs22_pg3__the_same_deposit_cannot_be_carried_twice(brazos, dana):
    """A carried deposit is GONE from the source, and the second try is refused.

    Two different submit tokens, so the idempotency replay does not answer this
    — the guard that does is the register itself, re-read inside the atomic
    block and locked by `record_deposit_movement`'s `select_for_update()`.
    SQLite serialises writers and cannot show that lock doing anything.

    The refusal is the CORRECT one — *"holds no deposit"* — rather than a
    release the register would have had to refuse one layer down, so the clerk
    is told the deposit has already moved instead of meeting a database error.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )
        with pytest.raises(PaymentRuleError, match="holds no deposit"):
            transfer.carry_deposit_forward(
                dana,
                source_account_id=old.pk,
                destination_account_id=new.pk,
                moved_on=CARRIED_AT,
                reason=REASON,
                idempotency_reference=uuid.uuid4(),
            )
        assert _register(new.pk) == THE_DEPOSIT
        assert (
            models.Payment.objects.filter(
                account_id=new.pk, purpose=models.PURPOSE_DEPOSIT, amount=THE_DEPOSIT
            ).count()
            == 1
        )


def test_cs22_pg4__the_books_move_the_liability_and_realise_nothing(brazos, dana):
    """The 2300 legs on a real ledger: two of them, equal, and netting to zero.

    Asserted against the posted journal lines rather than against a report, so
    a reporting layer that was wrong in the same direction could not agree with
    a broken posting. The net across the pair is **0.00** — the utility owes the
    same $150.00 back to the same person, held against a different account.
    """
    with tenant_ctx(brazos):
        old, new = a_customer_who_moved(dana, brazos)
        carried = transfer.carry_deposit_forward(
            dana,
            source_account_id=old.pk,
            destination_account_id=new.pk,
            moved_on=CARRIED_AT,
            reason=REASON,
            idempotency_reference=uuid.uuid4(),
        )
        lines = list(
            ledger_models.JournalLine.objects.filter(journal_entry_id=carried.journal_entry_id)
        )
        assert len(lines) == 2
        assert {line.side for line in lines} == {"debit", "credit"}
        assert {line.amount for line in lines} == {THE_DEPOSIT}
        net = sum(
            (line.amount if line.side == "debit" else -line.amount for line in lines), Decimal("0")
        )
        assert net == ZERO
        assert {str(line.account_id) for line in lines} == {str(old.pk), str(new.pk)}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-22 · task 33 · CLAUDE.md hard-won law 14 · rule 4's
#         write-once door (payments/0006) · BR-CUS-670 · BR-LED-007
# generated: 2026-09-03 by the CR-059 CS-22 deposit carry-forward lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — task 34) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 THE FILE FAILS rather than SKIPS on SQLite. A skipped case reads as
#      coverage in a summary line; a failure names the gap (law 1).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
