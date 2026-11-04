# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 (Check — saved results, re-checked on change)
# Ruling:   OQ-843 RE-RULED 2026-09-30, option C — PO verbatim: *"this is
#           correct - C · Save results, and automatically re-check an account
#           when its plan, reading, meter or payment changes"*. SUPERSEDES the
#           2026-08-30 "recompute, never cache" ruling.
# Plan:     15-bulk-bill-run-build-plan.md B9 · DB1 · B13 (standing answers)
# Migration: billing/0032 (tables) · billing/0033 (RLS FORCE) — 🔒
#           HUMAN-REVIEW-PENDING
# Tests:    06-backend/tests/test_bbr_check_store.py
# ───────────────────────────────────────────────────────
"""The Check's saved results, and the run's standing answers.

THREE TABLES, AND NONE OF THEM IS A FINANCIAL RECORD
----------------------------------------------------
  * `bill_run_account_checks` — ONE row per account per run: its status
    (ready / decision / blocked / quiet), WHEN it was checked (`checked_at`,
    what the page shows as *"Checked at 10:42"*), whether it is STALE, and the
    facts the staleness sweep needs to know which changes concern it (its
    covered units, its plan).
  * `bill_run_findings` — ONE row per account per problem: code, category,
    tag severity, service, the sentence and the catalogue key + params the
    screen translates (DB1's list, exactly).
  * `bill_run_standing_answers` — the Check's *Answer for all N* for one tag
    (BR-BIL-1040 amended 2026-09-30: standing answers moved from Scope to
    Check, per tag). A per-account decision still overrides it.

⚠ **WHAT OPTION C KEEPS FROM THE AUGUST RULING, AND HOW.** The August ruling
protected one thing — *a fix is seen* (*"it will collect data at that
instansce"*). Every account is still checked from LIVE data; what is saved is
the answer, with the instant it was true. A change to that account's plan,
reading, meter/asset or payment marks its row STALE and re-checks JUST that
account (`check_staleness`), and *Check again* is the backstop. A stale row is
served AS stale, never as current.

All three are derived and rewritable (a re-check replaces an account's rows);
none carries money, so hard rule 4 does not reach them. Tenant-scoped with RLS
FORCE (`billing/0033`). `account_id` is a plain uuid rather than a foreign key
into customers: a findings row must never hold up an account's lifecycle, and
the reviewed cross-module FK set (B2 §2) is not widened for a cache of a check.
"""

from django.db import models

from core.dbfields import uuid7_pk

CHECK_READY = "ready"
CHECK_DECISION = "decision"
CHECK_BLOCKED = "blocked"
CHECK_QUIET = "quiet"
CHECK_STATUSES = (CHECK_READY, CHECK_DECISION, CHECK_BLOCKED, CHECK_QUIET)


class BillRunAccountCheck(models.Model):
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        "billing.BillRun",
        on_delete=models.CASCADE,
        related_name="account_checks",
        db_column="bill_run_id",
    )
    account_id = models.UUIDField()
    account_no = models.TextField()
    unit_id = models.UUIDField(null=True, blank=True)
    #: `accounts.kind` (regular / master), for the Ready list's filter.
    account_kind = models.TextField(null=True, blank=True)
    status = models.TextField()
    #: The units this account's bill covers and the plan it priced on — what
    #: the staleness sweep matches a metering / rating change against.
    covered_unit_ids = models.JSONField(default=list, blank=True)
    plan_id = models.UUIDField(null=True, blank=True)
    stale = models.BooleanField(default=False)
    #: The job that last checked it, or NULL when checked inline.
    job_id = models.UUIDField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_run_account_checks"
        indexes = [
            models.Index(fields=["tenant", "bill_run", "status"], name="ix_brac_run_status"),
            models.Index(fields=["tenant", "bill_run", "account_no"], name="ix_brac_run_no"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["bill_run", "account_id"], name="uq_brac_once"),
        ]


class BillRunFinding(models.Model):
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        "billing.BillRun",
        on_delete=models.CASCADE,
        related_name="findings",
        db_column="bill_run_id",
    )
    account_check = models.ForeignKey(
        BillRunAccountCheck,
        on_delete=models.CASCADE,
        related_name="findings",
        db_column="account_check_id",
    )
    account_id = models.UUIDField()
    code = models.TextField()
    category = models.TextField()
    severity = models.TextField(null=True, blank=True)
    service_code = models.TextField(null=True, blank=True)
    detail = models.TextField()
    message_key = models.TextField(null=True, blank=True)
    params = models.JSONField(default=dict, blank=True)
    support_ref = models.TextField(null=True, blank=True)
    #: The Check CATEGORY that recorded this row (`check_engine.CATEGORY_*`) —
    #: a partial re-check replaces only its own categories' rows (DEF-BIL-8286,
    #: `billing/0035`). NULL on rows saved before it: such an account is
    #: re-checked in full.
    check_step = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_run_findings"
        indexes = [
            models.Index(fields=["tenant", "bill_run", "code"], name="ix_brf_run_code"),
            models.Index(fields=["tenant", "bill_run", "account_id"], name="ix_brf_run_account"),
        ]


class BillRunStandingAnswer(models.Model):
    """*Answer for all N* on one tag (BR-BIL-1040 as amended 2026-09-30).

    One live row per (run, case); a change of mind writes a new row and
    supersedes the old one, like `bill_run_decisions` — the trail says who
    answered a whole tag and when.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    bill_run = models.ForeignKey(
        "billing.BillRun",
        on_delete=models.PROTECT,
        related_name="standing_answers",
        db_column="bill_run_id",
    )
    case = models.TextField()
    choice = models.TextField()
    decided_by_id = models.UUIDField(null=True, blank=True)
    superseded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_run_standing_answers"
        constraints = [
            models.UniqueConstraint(
                fields=["bill_run", "case"],
                condition=models.Q(superseded=False),
                name="uq_brsa_live",
            ),
        ]
