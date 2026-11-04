# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 lane RULINGS (2026-10-05) — `OQ-CUS-12790` CLOSED (a):
#           a cancelled move-in releases its held deposit to the account's
#           credit and refunds everything as ONE refund.
# Rules:    PO ruling, decision log *"FOUR PO RULINGS IN ONE REPLY"* (4),
#           verbatim: *"Release the deposit and refund the full $175.00 as one
#           refund, approved by Finance as usual."* · BR-PAY-012 (a deposit is a
#           LIABILITY, never revenue) · US-PAY-002 TC-1 (a HELD deposit is not
#           credit) · BR-PAY-014 (a refund only out of a real credit) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7
# Tests:    06-backend/tests/test_cr171_oq_cus_12790_cancel_refund.py ·
#           06-backend/tests/test_cr171_deposit_releases_rls_pg.py
# Impacts:  apps/payments/deposit_release.py (the ONLY writer) ·
#           apps/payments/selectors.account_credit_position (counts a release) ·
#           apps/payments/credit.deposit_payments_for_account (nets it out)
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — `deposit_releases`: a held deposit
handed back to the customer's CREDIT, one row per release.

AI-authored 2026-10-05 (lane RULINGS, `CR-171-BRC10`) under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"OQ-CUS-12790 (a) — A CANCELLED MOVE-IN REFUNDS ITS DEPOSIT WITH THE REST"*).

WHY A TABLE, AND WHY THIS ONE
-----------------------------
A deposit-purpose payment is HELD (US-PAY-002 TC-1): `account_credit_position`
excludes it, so the refund path — which pays only out of a real credit
(BR-PAY-014) — can never reach it. That exclusion is right and stays. What was
missing is the ACT that ends the holding before any bill: the PO's worked case
is Nilesh, who paid **$175.00 by check 1043** (a **$150.00** deposit and a
**$25.00** fee) and cancelled his move-in before any bill — *"Release the deposit
and refund the full $175.00 as one refund"*.

A payment row cannot record it: hard rule 4 freezes every column of `payments`
but three, and a deposit's `purpose` is not one of them. A refund row cannot
either: a refund SPENDS credit, it does not make it. So the release is its own
row — append-only, written by ONE function (`deposit_release.release_to_credit`)
together with its books entry (DR 2300 customer deposit liability / CR 2400
customer credit balances, through the ledger's own `post_deposit_applied`, the
entry a move-out's leftover deposit already uses) — and the credit position adds
it. Nothing here is ever updated or deleted; there is no code path that does.

`account_id` is a plain UUID, not a foreign key: the reviewed cross-module FK set
(B2 §2) is not widened by this file, and the writer checks the account is this
tenant's before writing.

Money is `NUMERIC(18,4)` (hard rule 2 — a NEW column declares four).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk


class DepositRelease(models.Model):
    """One held deposit moved to the account's credit. Append-only."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account_id = models.UUIDField()
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")  # CHAR(3), hard rule 2
    #: Why the deposit stopped being held — `move_in_cancelled` today.
    reason = models.TextField()
    #: The document that caused it (e.g. `move_record` + its id). Free text on
    #: purpose, the same shape `journal_entries.source_type` has.
    source_type = models.TextField()
    source_id = models.TextField()
    released_on = models.DateField()
    released_by_id = models.UUIDField(null=True, blank=True)
    #: The books entry written with it (DR 2300 / CR 2400).
    journal_entry_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "deposit_releases"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="ck_deposit_releases_amount_positive"
            ),
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"], name="uq_deposit_releases_idempotency"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account_id"], name="ix_deposit_releases_account"),
        ]
