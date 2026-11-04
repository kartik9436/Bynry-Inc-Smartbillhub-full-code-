"""reports 0003 — the 6 groups, the 19 sub-groups and the 46 definitions.
HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-26 under the PO ruling of
2026-08-09. Row in `12-governance/09-human-review-ledger.md`, shared with
`0001` and `0002`.

`CR-142-BRC07` Phase 0 · `P0.2` (the categories) · `P0.6` (the 46).

WHERE EVERY ROW BELOW CAME FROM
───────────────────────────────
`05-prototype/09 Reports Build Brief.pdf` §06, pages 49–73, **read as rendered
images** — B14 rule 42, and not optional here: the document's text layer is
measurably lossy and drops whole task rows elsewhere in the same file. Each
report is drawn with a header line of the form

    R7   Bill Print File        Billing › Delivery · bills & lines · Posting date

and that line is the four facts this migration writes: the register number, the
name, the group and sub-group, and the source tables with the date basis. The
`# Rnn` comment on every row below is the trace back to its drawing.

THE COUNTS TIE OUT, AND THAT IS THE CHECK
─────────────────────────────────────────
The document states its own group counts in headings — BILLING 5 ·
RECEIVABLES 9 · FINANCE 9 · CUSTOMERS 9 · OPERATIONS 7 · COMPLIANCE 7 — and
they sum to **46**, which is the figure `P0.6`'s outcome names. The distinct
sub-groups are 3 + 3 + 4 + 3 + 3 + 3 = **19**, which is the figure `P0.2`'s
outcome names. Both are asserted in `tests/test_rep_p0_schema_spine.py` rather
than trusted: a seed whose count is wrong is a seed nobody notices is wrong.

⚠ THE DOCUMENT SAYS 45 IN THREE PLACES AND 46 IN THREE OTHERS, AND BOTH ARE
TRUE OF DIFFERENT THINGS
────────────────────────────────────────────────────────────────────────────
§7.1 says *"the 45 reports are 45 rows"*; §7.6 says *"32 of the 45"*; p78 says
*"32 of the 46"*; the Phase 0 table and its DONE WHEN both say 46. The
reconciliation is on p20, in the catalogue screen's own note: **"45, not 46 —
the forty-sixth answer is the Dashboard tab"**. `R42 Operational Dashboard` is
a definition like any other and renders as **Tab 2** rather than as a card in
the grid, so the TABLE holds 46 and the GRID shows 45. Both numbers are right
and neither is a typo. Filed as `DEF-REP-6798` so the next reader does not have
to re-derive it, and `R42` carries `renders_as: "tab"` in its filters so the
catalogue screen can tell without counting.

⚠⚠ LIFTING `FORCE` ROUND THE SEED — AND THIS IS THE HALF THE TEST SUITE CANNOT
CHECK
──────────────────────────────────────────────────────────────────────────────
`0002` put `ENABLE` **and** `FORCE ROW LEVEL SECURITY` on these two tables, and
`FORCE` applies to the table's OWNER — which is the role running this migration.
The policy's `WITH CHECK` is `tenant_id = <the session's tenant>`, deliberately
**without** the `OR tenant_id IS NULL` its `USING` clause carries, because a
platform row must be readable by every tenant and writable by none.

**A platform row has no tenant, so there is no `app.tenant_id` this migration
could set to get past its own wall.** A bare `objects.update_or_create(
tenant_id=None, ...)` here is REFUSED. Measured on PostgreSQL 16.13,
2026-09-26, verbatim:

    ERROR:  new row violates row-level security policy for table "..."

⚠ **AND IT PASSES ON SQLITE, WHICH IS THE ENTIRE UNIT SUITE.** `config/settings/
test.py` hardcodes in-memory SQLite, which has no row-level security of any
kind, so the broken version of this file is green on every machine and fails the
first time anybody migrates a real database. That is CLAUDE.md hard-won law 14
exactly, one rule along, and it is why this paragraph exists rather than a
comment saying *"seeding works"*.

**So `FORCE` is lifted for the length of this migration and put back in the same
operation list.** The capability that lets it happen is *owning the table*, which
only a migration has: nothing at runtime can take this door, because there is no
GUC and no role a request could reach it through. The alternative — a carve-out
in the policy keyed on a session setting — would be a hole any code path could
open, and the whole point of `FORCE` is that the owner is not exempt at runtime.

Rolling back runs the list in reverse, so `FORCE` comes off, `unseed` removes
the platform rows, and `FORCE` goes back on.

**PROVED ON REAL POSTGRESQL 16.13, NOT ON THE SUITE** (2026-09-26), and it took
TWO runs — the first failed on the re-`FORCE` with *"cannot ALTER TABLE …
because it has pending trigger events"*, which is why `FORCE` above begins with
`SET CONSTRAINTS ALL IMMEDIATE`. With `FORCE`
lifted the platform insert succeeds; with it back on, a tenant session **reads**
the platform row, is **refused** when it tries to write one — *"new row violates
row-level security policy"* — **can** write its own, and a second tenant sees the
platform row and not the first tenant's copy. `P0.10` is the task that makes
that a standing check rather than one lane's transcript.

WHAT IS DELIBERATELY NOT SEEDED
───────────────────────────────
**No `columns` list on any row.** A definition's columns must every one be a
name the dataset declares (`apps/reports/datasets.py`), and the column sets the
drawings show are a screen's four-of-seven choice rather than a ratified list —
`BR-REP-021` already puts five reports on the generic viewer *because their
column sets are unratified*, and inventing forty-six of them here would be the
seeder choosing, which spec rule 7 forbids. An empty `columns` means *"every
column the dataset declares"*, which is honest and is what the runner does.

**No `name_i18n` on any row.** B14 rule 35: a catalogue is written in its own
language, never translated from English. Eleven catalogues × 46 names is 506
strings and not one of them is mine to author. The column is empty and every
reader falls back to `name`.

**Nothing is switched over to read this.** `GET /reports` still serves
`apps/reports/catalog.py`'s 23-card tuple. Making it serve these 46 is `P1.1`,
which owns the catalogue SCREEN as well — and it must, because the screen labels
groups through `t("reports.group.<code>")` and names cards through
`t("reports.card.<key>.name")`. Serving 46 today would render six unlabelled
group headings and twenty-three cards showing a raw snake_case key, which is
B14 rule 31's shape and a visibly broken screen in a phase whose own brief says
**"WHAT A CLERK CAN NEWLY DO: Nothing"**. The reasoning and the 506-string
figure are in the decision log, 2026-09-26.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: The two tables that hold PLATFORM rows. See `LIFTING FORCE` in the docstring.
PLATFORM_TABLES = ("report_definitions", "report_categories")

NO_FORCE = "\n".join(
    f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)
#: ⚠ `SET CONSTRAINTS ALL IMMEDIATE` IS LOAD-BEARING AND IT COST A SECOND
#: POSTGRESQL RUN TO FIND. The three operations below run in ONE transaction,
#: so the `ALTER TABLE` that puts `FORCE` back happens while the seed's inserts
#: still have DEFERRED foreign-key trigger events queued behind them — and
#: PostgreSQL refuses:
#:
#:     django.db.utils.OperationalError: cannot ALTER TABLE
#:     "report_definitions" because it has pending trigger events
#:
#: Flushing the deferred checks first is what makes the re-`FORCE` legal.
#: ⚠ **AND SQLITE SHOWS NONE OF THIS** — no row-level security, no deferred
#: constraint triggers, no `ALTER TABLE` here at all, because `PostgresOnlySQL`
#: skips. The unit suite is green on the broken version twice over.
FORCE = "SET CONSTRAINTS ALL IMMEDIATE;\n" + "\n".join(
    f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" for table in PLATFORM_TABLES
)

#: `(code, name, sort_order)` — the six top-level groups, in the document's
#: own order (§06 pages 49–66, each introduced by a heading with its count).
GROUPS: tuple[tuple[str, str, int], ...] = (
    ("billing", "Billing", 10),
    ("receivables", "Receivables", 20),
    ("finance", "Finance", 30),
    ("customers", "Customers", 40),
    ("operations", "Operations", 50),
    ("compliance", "Compliance", 60),
)

#: `(code, name, parent_code, sort_order)` — the nineteen sub-groups, read off
#: the `Group › Sub-group` half of every report's header line.
SUB_GROUPS: tuple[tuple[str, str, str, int], ...] = (
    ("billing_readiness", "Readiness", "billing", 10),
    ("billing_bills", "Bills", "billing", 20),
    ("billing_delivery", "Delivery", "billing", 30),
    ("receivables_payments", "Payments", "receivables", 10),
    ("receivables_arrears", "Arrears", "receivables", 20),
    ("receivables_recovery", "Recovery", "receivables", 30),
    ("finance_ledger", "Ledger", "finance", 10),
    ("finance_income", "Income", "finance", 20),
    ("finance_cash", "Cash", "finance", 30),
    ("finance_performance", "Performance", "finance", 40),
    ("customers_accounts", "Accounts", "customers", 10),
    ("customers_statements", "Statements", "customers", 20),
    ("customers_enrolment", "Enrolment", "customers", 30),
    ("operations_reads", "Reads", "operations", 10),
    ("operations_assets", "Assets", "operations", 20),
    ("operations_field", "Field", "operations", 30),
    ("compliance_audit", "Audit", "compliance", 10),
    ("compliance_changes", "Changes", "compliance", 20),
    ("compliance_filings", "Filings", "compliance", 30),
)

#: BR-REP-001's two labels plus the third case: a report carrying no money
#: names no basis, and the drawing writes that as `—`.
POSTING = "posting"
CLEARING = "clearing"
EVENT = "event"

#: `(register, key, name, group, sub_group, dataset, basis, basis_label)`
#:
#: `register` is the R-number on the drawing and is the trace back to the page.
#: `basis_label` is the drawing's own words, kept verbatim because *"As at"*,
#: *"Read date"* and *"Effective date"* are three different facts that all map
#: to `event` and a clerk reads the label, not the code.
#:
#: ⚠ SIX KEYS ARE THE STRINGS THIS PRODUCT ALREADY SERVES and are NOT
#: re-spelled to match the drawing's name: `ar_aging`, `billing_register`,
#: `revenue_by_service_rate`, `payments_by_method`, `account_ledger` and
#: `trial_balance`. `OQ-247` is open on whether those strings are ratified, and
#: renaming one breaks a bookmarked URL, a stored schedule and an IS-11 filename
#: a bookkeeper has already filed. A rename is a ruling, not a seed.
DEFINITIONS: tuple[tuple[str, str, str, str, str, str, str | None, str | None], ...] = (
    # ── Billing — 5 ─────────────────────────────────────────────────────────
    ("R4", "bill_run_readiness", "Bill Run Readiness", "billing", "billing_readiness", "invoices", POSTING, "Posting date"),
    ("R5", "billing_register", "Billing Register", "billing", "billing_bills", "invoices", POSTING, "Posting date"),
    ("R6", "bill_adjustments", "Bill Adjustments", "billing", "billing_bills", "invoices", POSTING, "Posting date"),
    ("R7", "bill_print_file", "Bill Print File", "billing", "billing_delivery", "invoices", POSTING, "Posting date"),
    # ⚠ No basis: the drawing writes `—`. A delivery report carries no money.
    ("R8", "bill_delivery", "Bill Delivery", "billing", "billing_delivery", "audit_log", None, None),
    # ── Receivables — 9 ─────────────────────────────────────────────────────
    ("R1", "payments_by_method", "Payments", "receivables", "receivables_payments", "payments", CLEARING, "Clearing date"),
    ("R2", "deposit_batches", "Deposit Batches", "receivables", "receivables_payments", "payments", CLEARING, "Clearing date"),
    ("R3", "payment_exceptions", "Payment Exceptions", "receivables", "receivables_payments", "payments", CLEARING, "Clearing date"),
    ("R9", "ar_aging", "AR Ageing", "receivables", "receivables_arrears", "payments", POSTING, "Posting date"),
    ("R10", "debtor_list", "Debtor List", "receivables", "receivables_arrears", "payments", POSTING, "Posting date"),
    ("R11", "cut_off_list", "Cut-Off List", "receivables", "receivables_arrears", "payments", POSTING, "Posting date"),
    ("R12", "collections_activity", "Collections Activity", "receivables", "receivables_recovery", "payments", None, None),
    ("R13", "write_offs_and_late_fees", "Write-Offs & Late Fees", "receivables", "receivables_recovery", "invoices", POSTING, "Posting date"),
    ("R14", "closed_account_balances", "Closed Account Balances", "receivables", "receivables_recovery", "payments", POSTING, "Posting date"),
    # ── Finance — 9 ─────────────────────────────────────────────────────────
    ("R15", "trial_balance", "Trial Balance", "finance", "finance_ledger", "journal_lines", POSTING, "Posting date"),
    ("R16", "journal_export", "Journal Export", "finance", "finance_ledger", "journal_lines", POSTING, "Posting date"),
    ("R17", "revenue_by_service_rate", "Revenue Analysis", "finance", "finance_income", "journal_lines", POSTING, "Posting date"),
    # ⚠ Two bases in ONE report, labelled per row — franchise fees read the
    # clearing date and the others read posting (R18's drawing, p57). The row
    # basis is the report's DEFAULT; the per-row label is the renderer's.
    ("R18", "tax_remittance", "Tax Remittance", "finance", "finance_income", "journal_lines", POSTING, "Posting date"),
    ("R19", "cash_reconciliation", "Cash Reconciliation", "finance", "finance_cash", "payments", CLEARING, "Clearing date"),
    ("R20", "deposits", "Deposits", "finance", "finance_cash", "payments", CLEARING, "Clearing date"),
    ("R21", "close_pack", "Close Pack", "finance", "finance_ledger", "journal_lines", POSTING, "Posting date"),
    # ⚠ R42 is the forty-sixth definition and it is NOT a card — it renders as
    # Tab 2, the Reports dashboard, by PO ruling, because a dashboard has no
    # parameters, no rows and no file. See this file's docstring on 45 vs 46.
    ("R42", "operational_dashboard", "Operational Dashboard", "finance", "finance_performance", "journal_lines", POSTING, "Posting date"),
    ("R43", "trend_pack", "Trend Pack", "finance", "finance_performance", "journal_lines", POSTING, "Posting date"),
    # ── Customers — 9 ───────────────────────────────────────────────────────
    ("R22", "account_census", "Account Census", "customers", "customers_accounts", "accounts", EVENT, "As at"),
    ("R23", "account_activity", "Account Activity", "customers", "customers_accounts", "accounts", EVENT, "Event date"),
    # ⚠ R24 and R25 are ONE definition each, drawn four times. A single
    # `subject` parameter changes whether the report is about an account, a
    # customer, a building or a unit — which is why `/reports/account-ledger`
    # and `/reports/by-premises` become one row and two subjects rather than
    # two rows (`P2.8`, and their addresses must keep opening).
    ("R24", "statement", "Statement", "customers", "customers_statements", "invoices", EVENT, "Statement date"),
    ("R25", "account_ledger", "Ledger", "customers", "customers_statements", "journal_lines", POSTING, "Posting date"),
    ("R26", "data_quality", "Data Quality", "customers", "customers_accounts", "accounts", EVENT, "As at"),
    ("R27", "plans_and_discounts", "Plans & Discounts", "customers", "customers_enrolment", "accounts", EVENT, "As at"),
    ("R44", "my_bills_and_payments", "My Bills & Payments", "customers", "customers_statements", "invoices", EVENT, "Statement date"),
    ("R45", "my_usage", "My Usage", "customers", "customers_enrolment", "meter_reads", EVENT, "Read date"),
    ("R46", "bill_projection", "Bill Projection", "customers", "customers_enrolment", "meter_reads", EVENT, "Projection date"),
    # ── Operations — 7 ──────────────────────────────────────────────────────
    ("R28", "read_completeness", "Read Completeness", "operations", "operations_reads", "meter_reads", EVENT, "Read date"),
    ("R29", "consumption_exceptions", "Consumption Exceptions", "operations", "operations_reads", "meter_reads", EVENT, "Read date"),
    ("R30", "usage_and_ranking", "Usage & Ranking", "operations", "operations_reads", "meter_reads", EVENT, "Read date"),
    ("R31", "meter_fleet", "Meter Fleet", "operations", "operations_assets", "assets", EVENT, "As at"),
    ("R32", "read_import_log", "Read Import Log", "operations", "operations_reads", "meter_reads", EVENT, "Import date"),
    ("R33", "service_order_activity", "Service Order Activity", "operations", "operations_field", "work_orders", EVENT, "Event date"),
    ("R34", "disconnect_reconnect", "Disconnect & Reconnect", "operations", "operations_field", "work_orders", EVENT, "Event date"),
    # ── Compliance — 7 ──────────────────────────────────────────────────────
    ("R35", "audit_trail", "Audit Trail", "compliance", "compliance_audit", "audit_log", EVENT, "Event date"),
    ("R36", "access_review", "Access Review", "compliance", "compliance_audit", "audit_log", EVENT, "As at"),
    ("R37", "rate_change_history", "Rate Change History", "compliance", "compliance_changes", "rate_schedules", EVENT, "Effective date"),
    ("R38", "adjustment_register", "Adjustment Register", "compliance", "compliance_changes", "invoices", POSTING, "Posting date"),
    ("R39", "regulatory_filing", "Regulatory Filing", "compliance", "compliance_filings", "journal_lines", EVENT, "Period"),
    ("R40", "external_reconciliation", "External Reconciliation", "compliance", "compliance_filings", "journal_lines", POSTING, "Posting date"),
    ("R41", "migration_assurance", "Migration Assurance", "compliance", "compliance_filings", "accounts", EVENT, "As at"),
)

#: The keys that render somewhere other than the catalogue grid. See the
#: docstring on 45 vs 46.
RENDERS_AS_TAB = ("operational_dashboard",)

#: The two definitions a single `subject` parameter draws at four grains each.
FOUR_SUBJECT_KEYS = ("statement", "account_ledger")
SUBJECTS = ("account", "customer", "premises", "unit")


def seed(apps, schema_editor):
    Category = apps.get_model("reports", "ReportCategory")
    Definition = apps.get_model("reports", "ReportDefinition")

    order = 0
    for code, name, sort_order in GROUPS:
        Category.objects.update_or_create(
            tenant_id=None,
            code=code,
            defaults={"name": name, "parent_code": None, "sort_order": sort_order},
        )
    for code, name, parent, sort_order in SUB_GROUPS:
        Category.objects.update_or_create(
            tenant_id=None,
            code=code,
            defaults={"name": name, "parent_code": parent, "sort_order": sort_order},
        )

    for register, key, name, group, sub_group, dataset, basis, basis_label in DEFINITIONS:
        order += 10
        filters: dict[str, object] = {"register": register}
        if basis is not None:
            filters["basis"] = basis
            filters["basis_label"] = basis_label
        if key in RENDERS_AS_TAB:
            filters["renders_as"] = "tab"
        if key in FOUR_SUBJECT_KEYS:
            filters["subject"] = SUBJECTS[0]
            filters["subjects"] = list(SUBJECTS)
        Definition.objects.update_or_create(
            tenant_id=None,
            key=key,
            defaults={
                "name": name,
                "dataset": dataset,
                "group_code": group,
                "sub_group_code": sub_group,
                # Empty = every column the dataset declares. See the docstring:
                # inventing forty-six unratified column sets is the seeder
                # choosing, which spec rule 7 forbids.
                "columns": [],
                "filters": filters,
                "group_by": [],
                "sort": [],
                # Empty = offered for every service. `P0.3`'s overlay is how a
                # water utility stops being shown gas reports; a service list
                # typed here would be the platform deciding it instead.
                "service_codes": [],
                "visibility": "shared",
                "owner_user_id": None,
                "version": 1,
            },
        )


def unseed(apps, schema_editor):
    """Remove exactly what `seed` wrote, and nothing a tenant has authored.

    `tenant_id=None` on both deletes is the whole of it: a tenant's own
    definitions and its own categories are untouched by a rollback of a
    platform seed. A `.all().delete()` here would take a utility's own work
    with it.
    """
    Category = apps.get_model("reports", "ReportCategory")
    Definition = apps.get_model("reports", "ReportDefinition")
    Definition.objects.filter(tenant_id=None, key__in=[row[1] for row in DEFINITIONS]).delete()
    Category.objects.filter(
        tenant_id=None,
        code__in=[row[0] for row in GROUPS] + [row[0] for row in SUB_GROUPS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("reports", "0002_rls_force")]

    operations = [
        # ⚠ See LIFTING FORCE in this file's docstring. Without these two the
        # seed raises on PostgreSQL and passes on SQLite.
        PostgresOnlySQL(NO_FORCE, reverse_sql=FORCE),
        migrations.RunPython(seed, unseed),
        PostgresOnlySQL(FORCE, reverse_sql=NO_FORCE),
    ]
