# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T8 (12-governance/11-change-requests.md) — "index the
#           unindexed dimensions". ⚠ CR-060 §0c finding 2 CORRECTS the source
#           document: THREE dimensions are unindexed, not one.
# Story:    US-LED-001 (source-event posting contracts) · US-LED-002 (the
#           dimension stamping these indexes read)   Screens: S56 · S41 · S60
# Rules:    B2 r13 #1 (the five-dimension set on `journal_lines`) ·
#           NFR-24 (this table is in the mandatory partition set — an index laid
#           on a partitioned parent is cloned onto every partition) ·
#           CLAUDE.md rule 1 (tenant scoping — every index leads with tenant_id,
#           so it is usable under the RLS predicate) · rule 4 (financial
#           immutability — CREATE INDEX reads rows and writes none) ·
#           BR-LED-001 · BR-LED-011
# Tests:    06-backend/tests/test_cr060_t8_dimension_indexes.py
# ───────────────────────────────────────────────────────
"""ledger 0010 — the three `journal_lines` dimensions that had no index.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
table is the row every money figure in the product is eventually summed from).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-01 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
`journal_lines` carries five optional dimensions (B2 r13 #1) and only two of
them had the `(tenant_id, dimension)` index every read on this table needs;
this lays the missing three, in the same shape as the four that already exist.

⚠ AND THE CR'S WORDING IS WRONG IN A WAY WORTH CORRECTING RATHER THAN COPYING.
CR-060 §0c finding 2 says the unit, service and tax-authority statements are
*"all sequential scans"*. **They are not, and they never were.** Django puts a
single-column index on every ForeignKey, so `journal_lines_unit_id_*`,
`journal_lines_service_id_*` and `journal_lines_tax_authority_id_*` have
existed since `ledger/0001`. What was missing is the COMPOSITE index — so a
dimension statement index-scanned ONE of its two columns and applied the other
as a filter. The gain is real and smaller than the CR implies, and it is
measured below rather than described.

⚠ THREE, NOT ONE — AND THAT CORRECTION IS THE REASON THIS FILE EXISTS
----------------------------------------------------------------------
CR-060's source document said `unit_id` *"is stamped but has no index — the
other four dimensions do"*. Read from the catalog rather than from the
document, `journal_lines` carried exactly five indexes:

    ix_journal_lines_entry      (tenant_id, journal_entry_id)
    ix_journal_lines_gl         (tenant_id, ledger_account_id)
    ix_journal_lines_account    (tenant_id, account_id)
    ix_journal_lines_premises   (tenant_id, premises_id)
    ix_journal_lines_source     (tenant_id, source_type, source_id)

Two of those are dimensions (`account`, `premises`); the other three are the
entry, the GL account and the source. So `unit_id`, `service_id` AND
`tax_authority_id` all had none. CR-060 §0c finding 2 records the correction.

WHAT EACH INDEX ACTUALLY HOLDS TODAY — MEASURED, NOT ASSUMED (law 1)
---------------------------------------------------------------------
Counted on the live development database (PostgreSQL 16.13), 2026-09-01,
6,098 posted journal lines across 14 tenants:

    unit_id           6,098 of 6,098 rows   (100%)  — every line carries a unit
    service_id        2,033 of 6,098 rows   ( 33%)
    tax_authority_id      0 of 6,098 rows   (  0%)

**The tax-authority index indexes nothing today, and that is not an oversight.**
`apps/ledger/reporting.py` already carries the stated absence in its own words:
rating publishes no `tax_authority_id_for_tax`, so `posting_seam` writes NULL on
every line and the collected-tax read refuses with that reason rather than
showing a billed figure. The index is laid NOW because the table is small NOW —
6,098 rows, where the whole operation is milliseconds — and it serves the read
the day CR-060 C19 / T7d fills the column. Laying it later means laying it on a
table with millions of rows under an ACCESS EXCLUSIVE lock. That is the whole
argument of T8, and it applies most to the emptiest column.

WHY PLAIN INDEXES AND NOT PARTIAL ONES
---------------------------------------
A partial index (`… WHERE tax_authority_id IS NOT NULL`) would be empty rather
than 6,098 NULL entries, and PostgreSQL would still use it for the equality
predicate every dimension statement carries. It was considered and NOT taken,
for two reasons a reviewer can weigh:

  1. The four indexes that already exist are unconditional `(tenant, dimension)`
     b-trees. Seven of one kind is one thing to review; four of one kind and
     three of another is a convention to explain on every future dimension.
  2. `unit_id` is 100% populated, so a partial index on it is the full index
     with an extra predicate — and the three arrive together as one decision.

The cost of the choice is bounded and stated: an all-NULL b-tree entry is the
tenant uuid plus a NULL bitmap, so the tax-authority index is roughly the size
of the tenant column, and it stops being dead the moment C19 lands.

WHAT IT ACTUALLY BUYS — MEASURED, BEFORE AND AFTER
---------------------------------------------------
6,098 real journal lines across 14 tenants, copied out of the development
database into a scratch database at `ledger/0009`, `ANALYZE`d, then the same
two statements run again after this migration. PostgreSQL 16.13.

    A UNIT STATEMENT — one tenant, one unit
      before  Index Scan using journal_lines_2026_unit_id_idx
                Index Cond: (unit_id = …)
                Filter:     (tenant_id = …)          Buffers: 7
      after   Index Only Scan using journal_lines_2026_tenant_id_unit_id_idx
                Index Cond: ((tenant_id = …) AND (unit_id = …))
                Heap Fetches: 0                      Buffers: 3

    A SERVICE STATEMENT — one tenant, one service (the revenue-by-service read)
      before  Index Scan using journal_lines_2026_tenant_id_idx
                Index Cond: (tenant_id = …)
                Filter:     (service_id = …)
                **Rows Removed by Filter: 496**      Buffers: 21
      after   Index Only Scan using journal_lines_2026_tenant_id_service_id_idx
                Index Cond: ((tenant_id = …) AND (service_id = …))
                Rows Removed by Filter: 0
                Heap Fetches: 0                      Buffers: 3

The service statement read 690 rows to return 194 and now reads 194 — **21
buffers to 3 on a table of 6,098 rows.** That ratio is what grows: the rows
discarded by the filter are the tenant's other services, and they scale with
the tenant, not with the answer.

⚠ **AN INDEX IS NOT PARTITION PRUNING, AND THIS BUYS NONE.** Both plans above
still touch `journal_lines_2027` — an empty partition — because the query
carries no predicate on `created_at`. That is `OQ-193`, which is OPEN and is
NOT answered here.

**HARD RULE 4, PROVED RATHER THAN ASSERTED.** `journal_lines` is append-only.
Before the migration those 6,098 rows summed to **767,852.820000** with row
digest `76ffb0dd644e24a62f9ecdbd30754be0`; after it, 6,098 rows, the same
total and the same digest. `CREATE INDEX` performs no row-level DML, so
`trg_journal_line_append_only` (ledger/0002) is never invoked — it is read back
still enabled on the parent and on every partition by the companion test.

**WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS.** `journal_lines` is a
PARTITIONED parent (ledger/0005). `CREATE INDEX` on a partitioned parent
creates the index on the parent and recursively on every partition, and it
takes a SHARE lock on each — writes to the table are blocked for the duration,
reads are not. It is instantaneous on a fresh install and on the demo tenant.
`CREATE INDEX CONCURRENTLY` is NOT available here: PostgreSQL 16 refuses it on
a partitioned table, and Django's `AddIndex` does not emit it either. On a host
that already holds millions of lines, run this in a maintenance window.

**NO ROW IS READ INTO THE APPLICATION, WRITTEN, UPDATED OR DELETED.** Hard rule
4 is not engaged: `CREATE INDEX` is a read of the heap and a write of a new
index relation. The append-only trigger `trg_journal_line_append_only`
(ledger/0002) is never invoked, because there is no row-level DML for it to
refuse.

WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
---------------------------------------------
CR-060 T8 has three halves and this is one of them. The other two are NOT here:

  * **THE PARTITION GRANULARITY** (yearly → monthly) reverses a recorded PO
    ruling — 2026-08-12, verbatim *"Nod to split both by year"*, decision log,
    closing OQ-107, where BY MONTH was the option put to them. CLAUDE.md law 13
    names that as one of the few things that legitimately reaches the PO: *a
    ruling that collides with a signed rule — the supersession must be stated,
    never assumed.* It is stated and put to them; it is not landed here.
  * **THE PARTITION KEY** is `OQ-193`, OPEN. Both tables range over
    `created_at`, which is not the book date, so a trial balance for one period
    still reads every partition. Moving to a book date needs a denormalised
    column on a B2-signed table and a MUTABLE partition key underneath an
    append-only trigger. The prime directive forbids resolving that by
    choosing, so the key is untouched and the question is not answered here.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("ledger", "0009_discount_contra_revenue_designation"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(fields=["tenant", "unit"], name="ix_journal_lines_unit"),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(fields=["tenant", "service"], name="ix_journal_lines_service"),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(
                fields=["tenant", "tax_authority"], name="ix_journal_lines_tax_authority"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T8@journal-dimension-indexes (the authorities this slice was
#         authored from: 12-governance/11-change-requests.md — CR-060 §0c
#         finding 2 and the T8 row in §12 · 04-docs/03-contracts/02-schema.md
#         r13 #1, the five-dimension set · apps/ledger/models.py JournalLine,
#         read from the catalog rather than from the document)
# generated: 2026-09-01 by the CR-060 T8 partitioning-and-indexes lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: G16 partition coverage PASS before and after (4 of 5 partitioned, outbound_messages PO-RULED) · applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 holding 6,098 posted journal lines in a yearly partition, and the three indexes were read back off the PARENT and off the partition · row count, amount total and md5 row digest identical before and after (nothing moved) · proved RED first: the companion test names all three indexes and fails on the migration's parent, ledger/0009
# exceptions: THE THREE INDEXES ARE UNCONDITIONAL, not partial, and the sparsity
#         that argues for partial is MEASURED in the docstring rather than left
#         to be inferred — tax_authority_id is NULL on 6,098 of 6,098 rows
#         today, which is a stated absence reporting.py already carries, not a
#         defect this migration introduces · NO CONCURRENTLY: PostgreSQL 16
#         refuses it on a partitioned table · T8's OTHER TWO HALVES ARE NOT
#         HERE — the granularity reverses the PO ruling of 2026-08-12 and is put
#         to them rather than assumed (law 13), and the key is OQ-193, OPEN, so
#         the prime directive forbids choosing it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
