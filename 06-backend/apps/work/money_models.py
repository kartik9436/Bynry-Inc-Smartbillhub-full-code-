# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 T-34 — the server pushes when money changes
#           on an account a technician is about to visit.
# Rules:    R19 (PO ruled: *"The server pushes the moment money changes. A
#           customer paying on Wednesday reaches the phone on Wednesday, so the
#           technician never drives out on Thursday"*) · CLAUDE.md hard rule 1
#           (tenant scoping; RLS FORCE in work/0040)
# Tests:    06-backend/tests/test_cr187_money_push.py ·
#           06-backend/tests/test_cr187_money_pg.py (RLS)
# Impacts:  apps/work/money.py (the only writer) · apps/work/models.py (imports
#           this so Django registers it) · apps/work/migrations/0039, 0040
# ───────────────────────────────────────────────────────
"""`work_money_pushes` — one row per money change a phone was told about.

A NEW FILE RATHER THAN A NEW BLOCK IN `models.py`, for wave K's reason
(hard-won law 11, mechanism two — `models.py` is shared by many lanes).

WHY A TABLE AT ALL
------------------
`core.jobs.enqueue` folds a repeated scope key only while the first job is
still ACTIVE (NFR-16). A push job finishes in milliseconds, so the next sweep —
a minute later, reading the same payment — would enqueue it again, and the
technician's phone would ring once a minute for the same $241.38 for as long as
the job stayed open. **"Once per money change" needs a memory that outlives the
job**, and this row is it: the unique key `(tenant, account, change_at)` means a
second sweep over the same change inserts nothing and pushes nothing.
"""

from django.db import models

from core.dbfields import uuid7_pk


class WorkMoneyPush(models.Model):
    """One money change on one account, pushed to the phone of each open job.

    `change_at` is payments' own `updated_at` of the latest payment row that
    moved (posted, cleared, cancelled, reversed) — read through
    `seams/payments_seam.money_changed_since`, never a clock of this module's,
    so two sweeps reading the same change agree on its key.

    `orders` and `devices` record what the sweep DID, for the audit tab and for
    a reader asking why a phone did or did not ring: the open orders on the
    account that declare a money check, and how many devices were addressed.
    No amount is stored here — the figure is payments', read live by the phone
    (R16), and a copy here would be a stale balance with a timestamp on it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: A plain uuid, not an FK: the account is CUSTOMERS' row and Work declares
    #: no new cross-module FK for a log (B2 §2's reviewed set is closed).
    account_id = models.UUIDField()
    change_at = models.DateTimeField()
    orders = models.JSONField(default=list)
    devices = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_money_pushes"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "account_id", "change_at"],
                name="uq_work_money_pushes_change",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "-change_at"], name="ix_work_money_pushes_recent"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030@3e02d12e (CR-187-BRC10 Phase 13 T-34 — the push to the phone; R19; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D=deferred(n/a — no route) E=deferred(n/a — no screen) F✔ G✔ H✔ [work/0040 is the 🔒 RLS path]
# gates: pytest tests/test_cr187_money_push.py · tests/test_cr187_money_pg.py on PostgreSQL 16
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
