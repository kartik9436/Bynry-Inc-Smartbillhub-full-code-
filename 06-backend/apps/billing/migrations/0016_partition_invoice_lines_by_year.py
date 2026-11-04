# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the lines this table holds) · US-BIL-009
#           (posting handoff reads them back)   Screens: S31 · S32
# Rules:    NFR-24 (invoice_lines is in the mandatory partition set, "No
#           exceptions"; its "monthly" wording SUPERSEDED for this table by the
#           PO ruling of 2026-08-12) · NFR-25 (financial partitions are NEVER
#           pruned) · B2 §5 ("Candidate key: period_start / created_at") ·
#           B2 r16 #1 (F-1: §5 "do not partition now" SUPERSEDED) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE) · rule 4 (financial
#           immutability — no UPDATE/DELETE on issued invoice lines) ·
#           DEF-031 (this table shipped flat and no gate read NFR-24)
# Tests:    06-backend/tests/test_oq_107_yearly_partitions.py (the shape, the
#           tie-out and the guards, live PG) · tests/test_us_aud_001_partition_rls.py
#           (catalog-wide: every partition carries its own policy)
# ───────────────────────────────────────────────────────
"""billing 0016 — `invoice_lines` becomes a YEARLY partitioned table.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
table holds money). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO
ruling of 2026-08-09. Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without a recorded human sign-off.

WHAT RULING THIS IMPLEMENTS, IN THE PO'S OWN WORDS
---------------------------------------------------
2026-08-12, verbatim: *"Nod to split both by year"* — OQ-107, recorded in
12-governance/02-decision-log.md. The option put to them was BY MONTH, because
NFR-24's own sentence says monthly; they answered by year. NFR-24's "monthly"
is therefore SUPERSEDED for this table, which is a change to a signed
non-functional requirement and is flagged here rather than absorbed. At this
product's declared ceiling — utilities under 3,000 connections — a year of
invoice lines is a small partition and there are fewer of them to maintain.

⚠ THE KEY IS `created_at`, AND THE PO WAS NOT ASKED THE KEY. They ruled how big
a partition is, not which column it ranges over. `created_at` is one of the two
candidates B2 §5 names for this table in signed text; the other, `period_start`,
is **NULLABLE** — a fee or late-charge line has no service period — and a NULL
RANGE key routes to no partition at all, so it could not have been used as the
column stands. The decision-log reading of 2026-08-11 (that an invoice line
should range over its invoice's SERVICE DATE) is NOT implemented: `service_date`
lives on `invoices`, not here, so it would have to be denormalised onto this
table — a schema change to a B2-signed table, and a decision above a partition
migration. Reported for a ruling; see the report accompanying this change.

⚠ THIS IS A DATA MIGRATION. SAY IT PLAINLY.
PostgreSQL cannot convert an existing table to a partitioned one in place —
there is no `ALTER TABLE … PARTITION BY`, in any version. The only route is to
build a new partitioned parent and carry the rows into it, so on a host that
already has invoice lines this migration COPIES them. What it does not do is
UPDATE or DELETE one: the rows are read once, INSERTed verbatim, and the old
heap is released by `DROP TABLE` — not by row-level deletes, so hard rule 4's
immutability trigger has nothing to refuse and is never asked to.

That is a claim, so it is measured rather than asserted (hard-won law 1):
`core.partitioning` takes the row count, the sum of `amount` and an **md5 over
the full text of every row** before the copy and again after it, and a single
differing byte aborts the transaction with both figures printed. The old heap
is dropped only after the tie-out has matched. The whole migration is one
transaction and PostgreSQL DDL is transactional, so the failure mode is "nothing
happened", never "half happened".

**WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS** — it holds an ACCESS
EXCLUSIVE lock on `invoice_lines` for as long as the copy takes, which is
proportional to the number of invoice lines on that host. Take a backup and run
it in a maintenance window. On a fresh install the table is empty and it is
instantaneous.

WHAT COMES BACK, AND WHY IT IS NOT RETYPED HERE
-----------------------------------------------
The column list and the primary key are declared below, in full, so a reviewer
can diff them against `apps/billing/models.py` and so G16 can see the
`PARTITION BY` (its evidence is the migration DDL, never a claim in code). The
migration REFUSES to run if the live table's columns are not exactly this list —
a column added by a later billing migration must be added here too, and finding
that out as a refusal is the point.

Everything else — the seven foreign keys, the two composite indexes, the
`trg_invoice_line_immutable` trigger from `billing/0002` — is read out of the
catalog before the swap and replayed onto the new parent verbatim. Restating
another migration's immutability trigger in this file would be a second copy
free to drift from the first. PostgreSQL clones a parent's row triggers onto
every partition, including partitions the create-ahead job mints later
(measured on PG 16.13).

The primary key changes from `(id)` to `(tenant_id, created_at, id)` because
PostgreSQL requires the partition key inside it — the same shape B2 §2 already
writes for `meter_reads`. Django's model still names `id` as its pk and keeps
working: it supplies all three columns on every INSERT.

sqlite (the test tier) keeps the plain table, exactly as `apps/metering/0003`
does. Partition DDL there would be a lie; the live assertions are the G5
isolation suite's.
"""

from datetime import date

from django.db import migrations

from core import partitioning

#: The NEW parent. Column order and nullability mirror the live table exactly —
#: `core.partitioning.convert_to_partitioned` refuses to run if they do not.
#: There are no column DEFAULTs on purpose: there are none on the live table
#: either (Django supplies them in Python), and inventing one here would change
#: what an INSERT that omits a column does.
PARTITIONED_PARENT_DDL = """
CREATE TABLE invoice_lines (
  id                uuid           NOT NULL,
  gl_account_id     uuid,
  kind              text           NOT NULL,
  description       text           NOT NULL,
  quantity          numeric(18,6),
  unit              text,
  unit_price        numeric(18,6),
  amount            numeric(18,6)  NOT NULL,
  taxable           boolean        NOT NULL,
  period_start      date,
  period_end        date,
  created_at        timestamptz    NOT NULL,        -- partition key (yearly)
  updated_at        timestamptz    NOT NULL,
  account_id        uuid           NOT NULL,
  charge_id         uuid,
  invoice_id        uuid           NOT NULL,
  service_id        uuid,
  tariff_version_id uuid,
  tenant_id         uuid           NOT NULL,
  tax_id            uuid,
  PRIMARY KEY (tenant_id, created_at, id)           -- must contain the key
) PARTITION BY RANGE (created_at);
"""

#: The reverse. One heap again, same rows — a migration on the books that cannot
#: be backed out of is one a deploy cannot back out of.
FLAT_TABLE_DDL = """
CREATE TABLE invoice_lines (
  id                uuid           NOT NULL,
  gl_account_id     uuid,
  kind              text           NOT NULL,
  description       text           NOT NULL,
  quantity          numeric(18,6),
  unit              text,
  unit_price        numeric(18,6),
  amount            numeric(18,6)  NOT NULL,
  taxable           boolean        NOT NULL,
  period_start      date,
  period_end        date,
  created_at        timestamptz    NOT NULL,
  updated_at        timestamptz    NOT NULL,
  account_id        uuid           NOT NULL,
  charge_id         uuid,
  invoice_id        uuid           NOT NULL,
  service_id        uuid,
  tariff_version_id uuid,
  tenant_id         uuid           NOT NULL,
  tax_id            uuid,
  PRIMARY KEY (id)
);
"""

COLUMNS = [
    "id",
    "gl_account_id",
    "kind",
    "description",
    "quantity",
    "unit",
    "unit_price",
    "amount",
    "taxable",
    "period_start",
    "period_end",
    "created_at",
    "updated_at",
    "account_id",
    "charge_id",
    "invoice_id",
    "service_id",
    "tariff_version_id",
    "tenant_id",
    "tax_id",
]


def partition_invoice_lines(apps_registry, schema_editor):
    partitioning.convert_to_partitioned(
        schema_editor,
        table="invoice_lines",
        parent_ddl=PARTITIONED_PARENT_DDL,
        columns=COLUMNS,
        today=date.today(),
        money_column="amount",
    )


def unpartition_invoice_lines(apps_registry, schema_editor):
    partitioning.convert_to_flat(
        schema_editor,
        table="invoice_lines",
        flat_ddl=FLAT_TABLE_DDL,
        columns=COLUMNS,
        money_column="amount",
    )


class Migration(migrations.Migration):

    # One transaction, deliberately: the failure mode has to be "nothing
    # happened". Postgres DDL is transactional, so a tie-out failure leaves the
    # original table with every original row in it.
    atomic = True

    dependencies = [
        ("billing", "0015_rls_correction_cases"),
    ]

    operations = [
        migrations.RunPython(partition_invoice_lines, unpartition_invoice_lines),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@8d956fb (sha1[:7] of the three authorities this slice was
#         authored from, newline-joined in order: the 2026-08-12 decision-log row
#         carrying the PO ruling "Nod to split both by year" · the OQ-107 row in
#         12-governance/01-open-questions.md · NFR-24's own sentence in
#         04-docs/02-decisions/06-non-functional-requirements.md, whose "monthly"
#         wording that ruling SUPERSEDES for this table)
# generated: 2026-08-15 by story-coder (OQ-107 partitioning lane)
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied to a REAL PostgreSQL 16.13 (postgres:16 as ci-backend.yml uses), forward and reverse, on an empty database and on one seeded with invoice lines; G16 proved RED first (the two OQ-107 exception lines naming this table) and green after
# exceptions: THIS IS A DATA MIGRATION and says so — PostgreSQL cannot convert a table to partitioned in place, so the rows are copied into a new heap under a count/sum/row-digest tie-out and the old heap is dropped only after it matches. No row is UPDATEd or DELETEd · the partition KEY (`created_at`) was NOT ruled by the PO, only the granularity was; `period_start` is NULLABLE and unusable as a RANGE key, and the 2026-08-11 decision-log reading (range over the invoice's service_date) would need that column denormalised onto this table — reported, not assumed · sqlite keeps the plain table (apps/metering/0003's posture); live assertions are the G5 isolation suite's
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
