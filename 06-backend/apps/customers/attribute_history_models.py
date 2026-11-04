# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.18`, and
#          §7.2.4 *"As-was or as-is"*, RULED — OPTION (b). PO's words in the
#          brief: *"keep history for class, type and status. Every report that
#          slices by a customer attribute answers as-is today, silently, and
#          nobody decided that — now somebody has."*
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE; no cross-tenant queryset) ·
#          hard rule 4 (financial immutability — this table is NOT a money
#          row and nothing here widens that rule) · B2 §3 (the policy
#          template) · NFR-5 (no hard caps) · BR-CUS-012 (the confirmed
#          account attribute set)
# Tests:   06-backend/tests/test_cr142_p0_18_attribute_history.py ·
#          06-backend/tests/test_cr142_p0_10_reports_rls_pg.py (the RLS half)
# Impacts: services.update_account (the one write) · apps/reports (the reader,
#          through its own seam, in a later phase)
# ───────────────────────────────────────────────────────
"""AS-WAS FOR AN ACCOUNT'S CLASS, TYPE AND STATUS.

**THE FACT THIS TABLE EXISTS TO PRODUCE.** An account moves from Residential to
Small Commercial in September. *Revenue by class for July* should put July's
revenue under **Residential**, because that is what the account was in July and
that is what a regulator is asking about. Today every such report answers
**as-is** — Commercial, for July — silently, because the column overwrote and
nothing else remembers.

⚠ **IT RECOVERS NOTHING. IT ONLY STARTS RECORDING, AND THAT IS WHY IT IS IN
PHASE 0 RATHER THAN AT THE END.** Every class change before the day this ships
is already gone: the column was overwritten in place and the only trace is
`audit_log`, which is pruned on a retention schedule with **no exemptions**
(PO ruling 2026-09-23, verbatim: *"keep the same rule s; when audit log is
delete - it is deleted thats okay"*). So the cost of waiting is measured in
months of history nobody will ever be able to produce, and it goes up every
month.

⚠ **AND THIS DOCSTRING, THIS TABLE AND EVERY SCREEN OVER IT MAY NOT DESCRIBE
`audit_log` AS KEEPING AN OLD VALUE FOR GOOD.** It does not, ever —
CLAUDE.md hard rule 4's closing clause (`DEF-CUS-9084`: worded without the phrase
the retention scan refuses, which this sentence used to quote). What this table gives is a record with
its OWN lifetime, which `audit_log` never was.

⚠ **NOTHING ABOUT IT REACHES A SCREEN AS AN EXPLANATION.** B14 rule 33 puts
RATIONALE at ZERO WORDS ON SCREEN. A report states its BASIS — *as-was* or
*as-is* — which is a FACT about the number in front of the reader; it never
explains retention, and a screen that did would break rule 33 while trying to
obey hard rule 4.

════════════════════════════════════════════════════════════════════════════
WHICH THREE COLUMNS, AND WHY THE NAMES DO NOT LINE UP
════════════════════════════════════════════════════════════════════════════
The brief says *class, type and status*. This product's `accounts` table spells
those three:

  · **class**  → `account_type_id`     — `account_types`, the Residential /
    Commercial / Industrial / Government catalogue. It is what every report in
    this module already calls `account_class`:
    `apps/payments/reporting.ar_aging` reads `account_type.name` into
    `account_class`, and `GET /lookups/account_types` serves the filter.
  · **type**   → `account_subtype_id`  — `account_subtypes`, where
    `small_commercial` lives. The brief's own worked case — *"Moving account
    100244 to Small Commercial"* — is a change of THIS column.
  · **status** → `status_id`           — `account_statuses` (r5 #20 / r9 #7).

RECORDED HERE RATHER THAN INFERRED BY THE NEXT LANE, because *class* and *type*
are near-synonyms in English and exactly backwards from the column names: the
thing called *class* on a report is the column called `account_type_id`.

════════════════════════════════════════════════════════════════════════════
THE SHAPE: SCD TYPE 2 OVER THE TRIPLE, NOT ONE ROW PER ATTRIBUTE
════════════════════════════════════════════════════════════════════════════
One row per account per PERIOD, carrying all three values, with a half-open
window `[effective_from, effective_to)`. `effective_to IS NULL` is the row in
force now.

A status change therefore writes a row that repeats the unchanged class and
type. That is deliberate and it is the whole reason to prefer this shape: a
report asking *"what was this account on 14 July"* is ONE row lookup that
answers all three at once and cannot half-answer. The alternative — one row per
(account, attribute) change — makes every slice three lookups and makes a
report that joins two of them at different dates a silent possibility.

⚠ **`effective_from` IS A DATE AND NOT A TIMESTAMP.** Reporting slices by
accounting period and by day; sub-day precision would invite a report to
straddle a boundary in a way no window a reader chose can express. Two changes
on one day therefore collapse: the LAST one wins for that day, which is what a
day-grained report can answer truthfully.

⚠ **NO `deleted_at` AND NO UPDATE PATH.** A correction is a new row. Nothing in
this module rewrites one, so the reasoning hard rule 4 applies to invoices
applies here by choice rather than by law — and if a future lane wants to edit
one, that is a ruling, not a refactor.
"""

from django.db import models

from core.dbfields import uuid7_pk


class AccountAttributeHistory(models.Model):
    """One period during which an account's class, type and status held still.

    ⚠ **NULLABLE `account_subtype` IS A REAL ANSWER.** `accounts.account_subtype_id`
    is NULL per r5 #19's addendum, so *"this account had no sub-type in July"*
    is a fact this table must be able to state. It is never a fabricated value
    and never the string "none".
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="attribute_history",
    )
    #: *class* on a report. See the module docstring for why the names cross.
    account_type = models.ForeignKey(
        "customers.AccountType", on_delete=models.PROTECT, db_column="account_type_id"
    )
    #: *type* on a report. NULL is a real answer.
    account_subtype = models.ForeignKey(
        "customers.AccountSubtype",
        on_delete=models.PROTECT,
        db_column="account_subtype_id",
        null=True,
        blank=True,
    )
    status = models.ForeignKey(
        "customers.AccountStatus", on_delete=models.PROTECT, db_column="status_id"
    )
    #: Inclusive. The day these three values began to be true of this account.
    effective_from = models.DateField()
    #: EXCLUSIVE, and NULL means *still in force*. Half-open so two adjacent
    #: rows cannot both claim the boundary day — the off-by-one that makes a
    #: month-end report count one account twice.
    effective_to = models.DateField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    #: Who made the change. NULL for a row written by a backfill or a job
    #: rather than by a person — never a substituted user.
    recorded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        db_column="recorded_by",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "account_attribute_history"
        constraints = [
            #: An open row is the CURRENT one, and there can be exactly one.
            #: Partial, so closed rows are unconstrained — an account with
            #: twelve historical periods is ordinary (`NFR-5`: no caps).
            models.UniqueConstraint(
                fields=["account"],
                condition=models.Q(effective_to__isnull=True),
                name="uq_account_attribute_history_open",
            ),
            #: A window that ends before it starts is not a window. Same-day
            #: (`effective_to == effective_from`) is refused too: a half-open
            #: window of zero days contains no date and can only ever be a
            #: row a reader trips over.
            models.CheckConstraint(
                condition=(
                    models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gt=models.F("effective_from"))
                ),
                name="ck_account_attribute_history_window",
            ),
        ]
        indexes = [
            #: THE as-was query: this account, as at a date. Ordered so the
            #: index answers `effective_from <= d` with a backward scan and
            #: the planner never sorts in memory (`NFR-3`).
            models.Index(
                fields=["tenant", "account", "-effective_from"],
                name="ix_account_attr_hist_as_was",
            ),
            #: THE report query: every account's class as at a date, for a
            #: whole tenant. Without this, *Revenue by class for July* is a
            #: sequential scan of every period of every account.
            models.Index(
                fields=["tenant", "effective_from", "effective_to"],
                name="ix_account_attr_hist_window",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        end = self.effective_to.isoformat() if self.effective_to else "open"
        return f"account {self.account_id} {self.effective_from}…{end}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.18 (05-prototype/09 Reports Build Brief.pdf p9 + §7.2.4 p85-86, read as images per B14 rule 42)
# screens: none — this phase adds no screen (the brief: "Nothing. this is the only phase with no user value")
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a(no screen in Phase 0) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p0_18_attribute_history.py could not import this module before it existed.
# exceptions: (1) the table records ONLY from the day it ships and says so in its own docstring rather than in any user-facing string (B14 rule 33) · (2) `account_type` is create-only on `update_account` today, so the class column will not move through that path until a class-change door exists — the COLUMN is recorded regardless, so the day that door lands nothing here changes
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (migration ordering + RLS are 🔒 paths)
# ──────────────────────────────────────────────────────────
