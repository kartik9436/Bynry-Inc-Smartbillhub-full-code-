# ── Trace ──────────────────────────────────────────────
# Change:   CR-185-BRC10 — a departing tenant's residue tied back to the owner,
#           remembered until it can be POSTED (coordinator ruling 2026-10-14:
#           *"the transfer must move only money that is IN THE BOOKS"*).
# Rules:    BR-CUS-097 · OQ-1250 CLOSED → (a) · CLAUDE.md hard rule 1 (RLS in
#           the migration that creates the table) · hard rule 2 (money 4 dp)
# Code:     apps/customers/move_out_settlement.py (writes and posts) ·
#           apps/billing/issue.py (asks for the post when the final bill issues)
# ───────────────────────────────────────────────────────
"""`balance_tie_backs` — one row per departing account whose residue a clerk
tied back to the owner.

**WHY A ROW.** The money may only move once it is in the books. A move-out
DRAFTS the final bill and the clerk sends it later from Billing, so between the
commit and that issue the tie-back is a promise with nothing to post yet. The
row is that promise (`pending`), then its outcome (`posted`, with the entry and
the amount, or `nothing_owed`). The move-out record reads it, so a pending
tie-back is visible rather than remembered by nobody.

It is NOT a money record: the money is the journal entry it names. Its status
moves pending → posted / nothing_owed exactly once; the entry itself is
immutable (hard rule 4) and idempotent per departing account (hard rule 6).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.dbfields import uuid7

STATUS_PENDING = "pending"
STATUS_POSTED = "posted"
STATUS_NOTHING_OWED = "nothing_owed"
STATUSES = (STATUS_PENDING, STATUS_POSTED, STATUS_NOTHING_OWED)


class BalanceTieBack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="balance_tie_backs",
    )
    owner_account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="owner_account_id",
        related_name="+",
    )
    status = models.TextField(default=STATUS_PENDING)
    #: What step 3 / the commit showed — a PREVIEW, never what is posted.
    preview_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    currency = models.CharField(max_length=3)
    #: The drafted final bill whose ISSUE posts this (billing's id; no FK — a
    #: cross-module reference outside the reviewed set, read only by value).
    final_invoice_id = models.UUIDField(null=True, blank=True)
    posted_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    decided_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "customers"
        db_table = "balance_tie_backs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "account"], name="uq_balance_tie_backs_account"),
            models.CheckConstraint(condition=Q(status__in=STATUSES), name="ck_balance_tie_backs_status"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-185-BRC10 · coordinator rulings 2026-10-14 ("POST AT COMMIT", then "only money IN THE BOOKS")
# generated: 2026-10-14 by lane OWNER-D4D5
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
