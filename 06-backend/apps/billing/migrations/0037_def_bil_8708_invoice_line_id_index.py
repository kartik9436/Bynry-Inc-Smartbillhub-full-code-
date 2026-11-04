# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8708 (Send issued 1.9 bills a second at 40,000 accounts)
# Story:    US-BIL-005 (issue) · US-BIL-040 (bulk run · Send)
# Rules:    NFR-24 (this table is partitioned; an index on the parent is
#           cloned onto every partition) · CLAUDE.md hard rule 4 (CREATE INDEX
#           reads rows and writes none)
# Tests:    06-backend/tests/test_def_bil_8708_line_update_index_pg.py
# Measured: 04-docs/05-modules/07-billing/19-check-cost-measured.md §11
# ───────────────────────────────────────────────────────
"""billing 0037 — an index on `invoice_lines (id)`.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored 2026-10-01 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"2026-10-01 · SEND AT SCALE"*).

WHAT IT FIXES. Issue stamps every line's GL account with
`line.save(update_fields=["gl_account_id", "updated_at"])`, which reaches
PostgreSQL as `UPDATE invoice_lines … WHERE invoice_lines.id = %s`. Since
billing 0016 the table is partitioned with primary key
`(tenant_id, created_at, id)` — the partition key has to be in it — and no
index led with `id`. So each update walked the partition: at 40,008 bills,
**300,695 rows removed by filter, 68 ms a line, about 7.5 lines a bill**, and
Send ran at 1.9 bills a second (`DEF-BIL-8708`). It grew with every month of
lines a utility keeps.

WHY `(id)` AND NOT `(tenant_id, id)`. The defect row suggested the second, in
the repo's tenant-first convention. The statement Django sends names `id` and
NOTHING ELSE; the tenant predicate is added by row-level security, and only
under a role that does not bypass it. A `(tenant_id, id)` index serves the
statement under that role and NOT under a superuser, a maintenance script or
the test database, where the same `WHERE id = %s` would walk the index again.
`(id)` serves every one of them, and under RLS the tenant predicate is simply
checked on the one row found. It cannot be UNIQUE: PostgreSQL requires a
unique index on a partitioned table to contain the partition key.

WHAT AN OPERATOR MUST KNOW. `CREATE INDEX` on a partitioned parent builds the
index on every partition and takes a SHARE lock on each: writes wait, reads do
not. On the 300,696-line test world it took about a second. `CONCURRENTLY` is
not available on a partitioned parent in PostgreSQL 16 (ledger 0010 says the
same). No row is read into the application, written, updated or deleted, so
the line-immutability trigger (billing 0002) is never invoked.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("billing", "0036_bbr_exclusion_next_cycle"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="invoiceline",
            index=models.Index(fields=["id"], name="ix_invoice_lines_id"),
        ),
    ]
