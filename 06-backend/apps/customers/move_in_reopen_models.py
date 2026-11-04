# ── Trace ──────────────────────────────────────────────
# Change:   CR-181-BRC10 B2 / B3 (lane REOPEN, 2026-10-13) — a returning
#           customer's closed account on THIS unit is reopened at move-in, and
#           the clerk's choice about what it still owes is recorded.
# Rules:    PO rulings 2026-10-13 (decision log *"RETURNING CUSTOMER AT
#           MOVE-IN — FOUR PO RULINGS"*): Q2 *"Reopen, for the same unit only"*
#           · Q3 *"Must pay first · Carry it onto the reopened account · Clerk
#           chooses"* · BR-CUS-152 (the move record is never updated — so this
#           fact lives in a row of its own, written once) · CLAUDE.md hard
#           rules 1 (RLS FORCE, `customers/0083`), 2 (money 4 places), 4 (no
#           issued money row is touched), 7 (audited by `move_in_reopen`)
# Tests:    06-backend/tests/test_cr181_returning_customer_reopen.py
# ───────────────────────────────────────────────────────
"""**`move_in_reopenings` — one row per move-in that REOPENED an account.**

Written once, at Complete, inside the move-in's own transaction, and never
updated (the move record's own posture, `BR-CUS-152`). It answers the three
questions the Move-ins list and details ask of a reopened move-in and that no
other row can answer once the account is live again:

  * **which account was reopened**, and what its `opened_at` / `closed_at`
    were before (the account row now holds the new tenancy's dates);
  * **what the clerk chose** about the old balance — `pay_first` or `carry`
    (PO Q3), or nothing when the account owed nothing;
  * **the figure at Complete** — what the books said the account owed at the
    moment the clerk pressed Complete (0.00 under `pay_first`, which is refused
    until it is; the carried amount under `carry`). NULL when the ledger could
    not be read, never a 0.00 nobody derived (`DEF-127`).

⚠ **NOT A COLUMN ON `move_records`.** That row is written by `moves.record_move`,
which four flows share; a reopen is the move-in's alone, and widening the
record for one flow's fact is how a shared table collects slots three of its
writers never fill (hard-won law 2 on data).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.dbfields import uuid7_pk
from core.money_fields import money_field

CHOICE_PAY_FIRST = "pay_first"
CHOICE_CARRY = "carry"
BALANCE_CHOICES: tuple[str, ...] = (CHOICE_PAY_FIRST, CHOICE_CARRY)


class MoveInReopening(models.Model):
    """The reopen a move-in performed, and the clerk's balance choice."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    move_record = models.OneToOneField(
        "customers.MoveRecord",
        on_delete=models.PROTECT,
        db_column="move_record_id",
        related_name="reopening",
    )
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="reopenings",
    )
    #: The account's dates BEFORE the reopen — the finished tenancy's.
    previous_opened_at = models.DateField(null=True, blank=True)
    previous_closed_at = models.DateField()
    #: `pay_first` | `carry` | NULL (nothing was owed, so nothing was asked).
    balance_choice = models.TextField(null=True, blank=True)
    #: What the ledger said the account owed when Complete was pressed.
    balance_at_complete = money_field(null=True, blank=True)
    currency = models.CharField(max_length=3, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "customers"
        db_table = "move_in_reopenings"
        indexes = [models.Index(fields=["tenant", "account"], name="ix_move_in_reopenings_account")]
        constraints = [
            models.CheckConstraint(
                condition=Q(balance_choice__isnull=True) | Q(balance_choice__in=BALANCE_CHOICES),
                name="ck_move_in_reopenings_choice",
            ),
        ]
