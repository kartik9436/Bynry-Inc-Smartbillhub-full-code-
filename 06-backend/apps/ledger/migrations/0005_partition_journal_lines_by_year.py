# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the rows the books are
#           summed from) · US-LED-003 (reversal pairs)   Screens: S56 · S36
# Rules:    NFR-24 (journal_lines is in the mandatory partition set, "No
#           exceptions"; its "monthly" wording SUPERSEDED for this table by the
#           PO ruling of 2026-08-12) · NFR-25 (financial partitions are NEVER
#           pruned) · B2 §5 ("Candidate key: period_start / created_at") ·
#           B2 r16 #1 (F-1: §5 "do not partition now" SUPERSEDED) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE) · rule 4 (financial
#           immutability) · rule 5 (balanced pairs; only the posting service
#           writes journal lines) · BR-LED-003 · BR-LED-007 ·
#           DEF-031 (this table shipped flat and no gate read NFR-24)
# Tests:    06-backend/tests/test_oq_107_yearly_partitions.py (the shape, the
#           tie-out and the guards, live PG) · tests/test_us_aud_001_partition_rls.py
#           (catalog-wide: every partition carries its own policy)
# ───────────────────────────────────────────────────────
"""ledger 0005 — `journal_lines` becomes a YEARLY partitioned table.

HUMAN-OWNED (migration ordering AND ledger posting are CLAUDE.md 🔒 sensitive
paths, and this table is the row every money number in this product is
eventually summed from). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under
the PO ruling of 2026-08-09. Row in 12-governance/09-human-review-ledger.md;
not RATIFIED without a recorded human sign-off.

WHAT RULING THIS IMPLEMENTS, IN THE PO'S OWN WORDS
---------------------------------------------------
2026-08-12, verbatim: *"Nod to split both by year"* — OQ-107, recorded in
12-governance/02-decision-log.md. The option put to them was BY MONTH, because
NFR-24's own sentence says monthly; they answered by year, so NFR-24's
"monthly" is SUPERSEDED for this table and that supersession is flagged rather
than absorbed.

⚠ THE KEY IS `created_at`, AND IT IS NOT THE BOOK DATE. This is the single most
important sentence in this file, so it is not buried.

OQ-107 asked the key and argued its own answer: *"`entry_date` is the BOOK DATE
every trial-balance query groups by, so a `created_at` partition prunes nothing
for the query it exists to serve"*. The decision log of 2026-08-11 records that
as an **Eng-Lead reading, explicitly stated so it could be disagreed with**. The
PO's ruling of 2026-08-12 settled the GRANULARITY and said nothing about the
column. What shipped is `created_at`, for three reasons that a reviewer should
weigh rather than take on trust:

  1. It is one of the two candidates **B2 §5 names in signed text** for this
     table ("Candidate key: period_start / created_at"), so it is chosen from
     signed law rather than invented.
  2. **`journal_lines` HAS NO BOOK DATE.** `entry_date` is a column of
     `journal_entries`. Ranging over it means denormalising it onto every
     journal line — a change to a B2-signed table (DB-11 fixes this table's
     dimension set) and a decision well above a partitioning migration.
  3. It would be a **MUTABLE partition key.** BR-LED-003 makes a DRAFT entry
     freely editable, `entry_date` included, so moving a draft's date would
     have to move its lines between partitions — a partition-key UPDATE that
     PostgreSQL performs as a delete-and-reinsert, underneath the append-only
     trigger `ledger/0002` installed to make exactly that impossible.

So `created_at` serves what NFR-24 exists for — volume, and NFR-25's
detach-by-age — and does NOT give a trial balance partition pruning. That gap is
real. It is reported for a PO ruling and must not be read as settled by this
migration.

⚠ THIS IS A DATA MIGRATION. SAY IT PLAINLY.
PostgreSQL cannot convert an existing table to a partitioned one in place —
there is no `ALTER TABLE … PARTITION BY`, in any version. The only route is to
build a new partitioned parent and carry the rows into it, so on a host that
already has books this migration COPIES them. What it does not do is UPDATE or
DELETE a journal line: the rows are read once, INSERTed verbatim, and the old
heap is released by `DROP TABLE` — not by row-level deletes, so
`trg_journal_line_append_only` has nothing to refuse and is never asked to.

That is a claim, so it is measured rather than asserted (hard-won law 1):
`core.partitioning` takes the row count, the sum of `amount` and an **md5 over
the full text of every row** before the copy and again after it, and a single
differing byte aborts the transaction with both figures printed. The old heap is
dropped only after the tie-out has matched. The whole migration is one
transaction, so the failure mode is "nothing happened", never "half happened".

**WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS** — it holds an ACCESS
EXCLUSIVE lock on `journal_lines` for as long as the copy takes. Take a backup
and run it in a maintenance window. On a fresh install the table is empty and it
is instantaneous.

THE THREE GUARANTEES THIS TABLE CARRIES ALL COME BACK, AND NONE IS RETYPED
--------------------------------------------------------------------------
`journal_lines` carries more machinery than any other table in the product:
`journal_balanced` (the DEFERRABLE constraint trigger that enforces hard rule 5
at COMMIT, `ledger/0002`), `trg_journal_line_append_only` (hard rule 4, which
also refuses a LATE INSERT into a posted entry, `ledger/0002`), and
`trg_journal_lines_sole_writer` (the `app.ledger_posting` fence, `ledger/0004`).

None of them is restated here. All three are read out of the catalog with
`pg_get_triggerdef` BEFORE the swap — while they still name the table by the
name the new parent will carry — and replayed verbatim afterwards, along with
the two CHECK constraints, the eight foreign keys and the five composite
indexes. A second copy of another migration's trigger text in this file would be
free to drift from the original, and the entire point of this table is that its
guarantees do not drift.

**Both trigger kinds work on a partitioned parent in PostgreSQL 16 and both are
cloned to every partition, including partitions the create-ahead job mints in
later years.** That was measured on PG 16.13 before this migration was written,
not assumed: a `CREATE CONSTRAINT TRIGGER` and a `BEFORE … FOR EACH ROW` trigger
were created on a partitioned parent and a partition added afterwards carried
both. The copy itself runs while the new parent has no triggers yet, which is
why it does not have to forge `app.ledger_posting` to write the rows.

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
#: The two CHECK constraints (`ck_journal_lines_side`, `ck_journal_lines_amount_ge0`)
#: are NOT restated: they come back from the catalog with everything else, so
#: there is one definition of them and it stays `ledger/0001`'s.
PARTITIONED_PARENT_DDL = """
CREATE TABLE journal_lines (
  id                uuid           NOT NULL,
  side              text           NOT NULL,
  amount            numeric(18,6)  NOT NULL,
  source_type       text,
  source_id         uuid,
  created_at        timestamptz    NOT NULL,        -- partition key (yearly)
  updated_at        timestamptz    NOT NULL,
  account_id        uuid,
  journal_entry_id  uuid           NOT NULL,
  premises_id       uuid,
  service_id        uuid,
  tax_authority_id  uuid,
  tenant_id         uuid           NOT NULL,
  unit_id           uuid,
  ledger_account_id uuid           NOT NULL,
  PRIMARY KEY (tenant_id, created_at, id)           -- must contain the key
) PARTITION BY RANGE (created_at);
"""

#: The reverse. One heap again, same rows — a migration on the books that cannot
#: be backed out of is one a deploy cannot back out of.
FLAT_TABLE_DDL = """
CREATE TABLE journal_lines (
  id                uuid           NOT NULL,
  side              text           NOT NULL,
  amount            numeric(18,6)  NOT NULL,
  source_type       text,
  source_id         uuid,
  created_at        timestamptz    NOT NULL,
  updated_at        timestamptz    NOT NULL,
  account_id        uuid,
  journal_entry_id  uuid           NOT NULL,
  premises_id       uuid,
  service_id        uuid,
  tax_authority_id  uuid,
  tenant_id         uuid           NOT NULL,
  unit_id           uuid,
  ledger_account_id uuid           NOT NULL,
  PRIMARY KEY (id)
);
"""

COLUMNS = [
    "id",
    "side",
    "amount",
    "source_type",
    "source_id",
    "created_at",
    "updated_at",
    "account_id",
    "journal_entry_id",
    "premises_id",
    "service_id",
    "tax_authority_id",
    "tenant_id",
    "unit_id",
    "ledger_account_id",
]


def partition_journal_lines(apps_registry, schema_editor):
    partitioning.convert_to_partitioned(
        schema_editor,
        table="journal_lines",
        parent_ddl=PARTITIONED_PARENT_DDL,
        columns=COLUMNS,
        today=date.today(),
        money_column="amount",
    )


def unpartition_journal_lines(apps_registry, schema_editor):
    partitioning.convert_to_flat(
        schema_editor,
        table="journal_lines",
        flat_ddl=FLAT_TABLE_DDL,
        columns=COLUMNS,
        money_column="amount",
    )


class Migration(migrations.Migration):

    # One transaction, deliberately: the failure mode has to be "nothing
    # happened". Postgres DDL is transactional, so a tie-out failure leaves the
    # original table with every original journal line in it.
    atomic = True

    dependencies = [
        ("ledger", "0004_posting_guard"),
    ]

    operations = [
        migrations.RunPython(partition_journal_lines, unpartition_journal_lines),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@8d956fb (sha1[:7] of the three authorities this slice was
#         authored from, newline-joined in order: the 2026-08-12 decision-log row
#         carrying the PO ruling "Nod to split both by year" · the OQ-107 row in
#         12-governance/01-open-questions.md · NFR-24's own sentence in
#         04-docs/02-decisions/06-non-functional-requirements.md, whose "monthly"
#         wording that ruling SUPERSEDES for this table)
# generated: 2026-08-15 by story-coder (OQ-107 partitioning lane)
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied to a REAL PostgreSQL 16.13 (postgres:16 as ci-backend.yml uses), forward and reverse, on an empty database and on one seeded with a posted balanced entry; the three triggers were read back off the new parent AND off a partition; G16 proved RED first (the two OQ-107 exception lines naming this table) and green after
# exceptions: THIS IS A DATA MIGRATION and says so — PostgreSQL cannot convert a table to partitioned in place, so the rows are copied into a new heap under a count/sum/row-digest tie-out and the old heap is dropped only after it matches. No journal line is UPDATEd or DELETEd · THE PARTITION KEY IS `created_at`, NOT THE BOOK DATE, and the PO ruled only the granularity — `entry_date` is not a column of this table, and BR-LED-003 makes it mutable while an entry is a draft, so ranging over it would need a denormalised column AND a movable partition key under an append-only trigger. OQ-107's own argument that created_at prunes nothing for a trial balance therefore STANDS UNANSWERED and is reported for a ruling · the three triggers and both CHECK constraints are replayed from the catalog rather than restated here, so there is exactly one definition of each and it stays ledger/0001, 0002 and 0004's · sqlite keeps the plain table (apps/metering/0003's posture); live assertions are the G5 isolation suite's
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
