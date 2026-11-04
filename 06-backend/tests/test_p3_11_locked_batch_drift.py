# ── Trace ──────────────────────────────────────────────
# Task:    P3.11 — "Say when a locked batch no longer sums" (Finance blueprint
#          p016 · p049 · the 3·2 Batch KPI strip on p050)
# Defect:  DEF-PAY-6651 — the handed-back measurement prescribed Σ(members) −
#          recorded_total, which is identically zero and can never show the
#          drift it was written to show.
# Rules:   CLAUDE.md hard rule 2 (money exact, never float) · hard rule 4 (a
#          reversal is a NEW row; the original is never updated) · BR-PAY-004 /
#          OQ-134 (a reversal inside a LOCKED batch is lawful and the frozen
#          total stays) · BR-PAY-884 (Σ of reversals may never exceed the
#          payment)
# ───────────────────────────────────────────────────────
"""The drift a locked batch acquires, and why it is served rather than derived.

⚠ **THIS FILE'S FIRST ASSERTION IS THE ONE THAT MATTERS, AND IT ASSERTS A
NON-EVENT.** After a lawful reversal inside a locked batch:

  * `recorded_total` does not move — correct, and `_refuse_if_batch_locked` says
    why: *"the bank statement the batch was agreed against did not change."*
  * **no member row moves either** — the reversing row is created with no
    `deposit_batch_id`, and hard rule 4 forbids touching the original's amount
    or status.

So Σ`members[].amount` equals `recorded_total` **for ever**, and the arithmetic
the task was handed back with answers `0.00` on a batch that is short. The test
below states that explicitly, because a reader who does not know it will
"simplify" `live_total` away and every other test in the repo will stay green.

⚠ **AND IT IS PROVED ON REAL POSTGRESQL, NOT ONLY ON THE DEFAULT SUITE.** A reversal writes across payments,
allocations and the ledger inside one transaction; the default suite runs on
in-memory SQLite (`config/settings/test.py` hardcodes it), where a failed
statement does not poison the transaction and this path behaves differently from
production — CLAUDE.md hard-won law 14.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, models as payment_models, reconciliation, reversal

from tests.test_us_pay_020_023_bank_rec import (  # noqa: F401 — shared fixtures
    PE10_DAY,
    a_bank_account,
    a_cleared_payment,
    a_statement,
)
from tests.test_us_pay_020_023_bankrec_surface import CUT_AT
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

RETURNED_AT = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)

#: One cheque day: three payments, one of which the bank sends back.
CHEQUES = (Decimal("117.30"), Decimal("501.33"), Decimal("387.09"))
RECORDED = sum(CHEQUES, Decimal("0"))  # 1,005.72
RETURNED = Decimal("501.33")
LIVE_AFTER = RECORDED - RETURNED  # 504.39


def _locked_batch_with_a_returned_cheque(actor, tenant, admin):
    """A reconciled, LOCKED batch, then one of its cheques comes back.

    `admin` reverses, and it is a SEPARATE parameter rather than `actor` because
    `reverse_payment` is `@require_role(SYSTEM_ADMIN)` (`BR-PAY-1070`) while the
    clerk cuts and reconciles the day. Passing one actor for both would have
    hidden the role gate this screen has to mirror.
    """
    for amount in CHEQUES:
        a_cleared_payment(actor, tenant, amount=amount, method_code="check")
    cut = reconciliation.cut_deposit_batches(actor=actor, day=PE10_DAY, occurred_at=CUT_AT)
    batch = bankrec.DepositBatch.objects.get(tenant=tenant, pk=cut.batches[0].batch_id)

    # The bank shows the day to the penny, through the REAL import — a batch
    # reconciles against what the BANK said (BR-PAY-019), and setting
    # `bank_total` by hand would reconcile against nothing.
    account = a_bank_account(tenant)
    reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=account.pk,
        period_start=PE10_DAY,
        period_end=PE10_DAY,
        payload=a_statement(
            [(PE10_DAY.isoformat(), "DEPOSIT CHEQUES", str(batch.recorded_total))]
        ),
        imported_at=CUT_AT,
    )
    # Reconcile with no resolutions — the bank agreed to the penny — which is
    # what LOCKS it (BR-PAY-004).
    reconciliation.reconcile_batch(
        actor=actor, batch_id=batch.pk, posted_at=RETURNED_AT, resolutions=()
    )
    batch.refresh_from_db()
    assert batch.status == bankrec.BATCH_RECONCILED

    returned = payment_models.Payment.objects.get(
        tenant=tenant, deposit_batch_id=batch.pk, amount=RETURNED
    )
    reversal.reverse_payment(
        admin,
        payment_id=returned.pk,
        returned_on=RETURNED_AT,
        memo="returned by the bank",
        idempotency_reference=uuid.uuid4(),
    )
    return batch, returned


@pytest.mark.django_db
def test_p3_11__a_reversal_inside_a_locked_batch_moves_no_member_row(brazos, marcus, dana):
    """DEF-PAY-6651 — the non-event that makes `live_total` necessary."""
    with tenant_ctx(brazos):
        batch, returned = _locked_batch_with_a_returned_cheque(marcus, brazos, dana)

        # The reversing row exists and is NOT in the batch.
        reversing = payment_models.Payment.objects.get(
            tenant=brazos, reverses_payment_id=returned.pk
        )
        assert reversing.amount == -RETURNED
        assert reversing.deposit_batch_id is None

        # The original is untouched — hard rule 4.
        returned.refresh_from_db()
        assert returned.amount == RETURNED
        assert returned.status != payment_models.PAYMENT_REVERSED

        # Therefore Σ members is still exactly what was frozen at the cut, and
        # the handed-back arithmetic — Σ(members) − recorded_total — is ZERO on
        # a batch that is 501.33 short.
        members = payment_models.Payment.objects.filter(
            tenant=brazos, deposit_batch_id=batch.pk
        )
        assert sum((row.amount for row in members), Decimal("0")) == RECORDED
        batch.refresh_from_db()
        assert batch.recorded_total == RECORDED


@pytest.mark.django_db
def test_p3_11__the_detail_serves_live_total_and_the_line_that_moved(brazos, marcus, dana):
    """The figure the tile draws, and the row a clerk needs to find."""
    with tenant_ctx(brazos):
        batch, returned = _locked_batch_with_a_returned_cheque(marcus, brazos, dana)
        detail = bankrec_read.batch_detail(batch.pk)

        # Frozen and live, both served, and they legitimately disagree.
        assert Decimal(detail["batch"]["recorded_total"]) == RECORDED
        assert Decimal(detail["live_total"]) == LIVE_AFTER
        assert Decimal(detail["live_total"]) - Decimal(
            detail["batch"]["recorded_total"]
        ) == -RETURNED

        # The drift is ATTRIBUTABLE: exactly one member says how much came back.
        moved = [row for row in detail["members"] if Decimal(row["reversed_amount"]) != 0]
        assert len(moved) == 1
        assert moved[0]["payment_no"] == returned.payment_no
        assert Decimal(moved[0]["reversed_amount"]) == RETURNED

        # And every other member states zero rather than omitting the field —
        # the server looked at all of them, so zero is a measurement.
        untouched = [row for row in detail["members"] if row["payment_id"] != str(returned.pk)]
        assert untouched and all(Decimal(row["reversed_amount"]) == 0 for row in untouched)

        # The LOCK is untouched. P3.11 shows a difference; it changes no rule.
        assert detail["batch"]["locked"] is True
        assert detail["batch"]["status"] == bankrec.BATCH_RECONCILED


@pytest.mark.django_db
def test_p3_11__a_batch_with_nothing_returned_reads_live_equals_recorded(brazos, marcus):
    """The ordinary case, so the tile is not a permanent alarm."""
    with tenant_ctx(brazos):
        for amount in CHEQUES:
            a_cleared_payment(marcus, brazos, amount=amount, method_code="check")
        cut = reconciliation.cut_deposit_batches(
            actor=marcus, day=PE10_DAY, occurred_at=CUT_AT
        )
        detail = bankrec_read.batch_detail(cut.batches[0].batch_id)
        assert Decimal(detail["live_total"]) == Decimal(detail["batch"]["recorded_total"])
        assert all(Decimal(row["reversed_amount"]) == 0 for row in detail["members"])


@pytest.mark.django_db
def test_p3_11__the_bulk_read_is_one_query_and_agrees_with_the_single_one(brazos, marcus, dana):
    """`reversed_so_far_by_payment` is `reversed_so_far`, batched — not a second rule.

    Asserted against its own single-row sibling rather than against a literal,
    so the day `BR-PAY-884`'s Σ changes shape the two cannot drift apart.
    """
    with tenant_ctx(brazos):
        batch, returned = _locked_batch_with_a_returned_cheque(marcus, brazos, dana)
        members = list(
            payment_models.Payment.objects.filter(tenant=brazos, deposit_batch_id=batch.pk)
        )
        bulk = reversal.reversed_so_far_by_payment(brazos.id, [row.pk for row in members])
        for row in members:
            single = reversal.reversed_so_far(brazos.id, row.pk)
            assert bulk.get(str(row.pk), Decimal("0")) == single
        # A payment with no reversal is ABSENT rather than zero — the caller
        # defaults it, and a dict claiming 0 for rows it never saw would be a
        # claim about payments it never looked at.
        untouched = [row for row in members if row.pk != returned.pk]
        assert untouched and all(str(row.pk) not in bulk for row in untouched)
        assert bulk == {str(returned.pk): RETURNED}

    # An empty ask costs no query and answers nothing, rather than answering
    # "everything".
    assert reversal.reversed_so_far_by_payment(brazos.id, []) == {}
