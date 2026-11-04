# ── Trace ──────────────────────────────────────────────
# Rules:   BR-CUS-1046 (PO 2026-09-10, EXTENDED 2026-09-12) — "It should always
#          sort it by the creation order. The new newly created entries should
#          always show on the top." NFR-3 (universal server pagination) ·
#          NFR-5 (no hard caps anywhere) · CLAUDE.md hard rule 1 (tenant
#          scoping — the index leads on `tenant_id`, as every index on this
#          table does)
# Defects: DEF-CUS-4996 · DEF-CUS-5060
# Screens: S17 Accounts list (and every screen that lists accounts)
# Tests:   06-backend/tests/test_br_cus_1046_lists_open_newest_first.py
# Impacts: apps/customers/selectors.account_page — the read this index serves
# ───────────────────────────────────────────────────────
"""customers 0041 — ONE index, nothing dropped and no data touched.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive list, so every numbered migration is guarded (`g07`'s
`human_owned.txt`) and carries a row in
`12-governance/09-human-review-ledger.md`. AI-authored under the PO's ruling of
2026-08-09, *"AI will do it; we will review it later as human."*

`S17` stopped opening on the alphabet and started opening on the creation
order, which moved the product's busiest read from `ORDER BY name` to
`ORDER BY created_at DESC, id DESC`. This is the index for that read.

⚠ **IT IS ADDITIVE AND REVERSIBLE, AND IT IS THE WHOLE MIGRATION.** No column
is added, altered or dropped; no row is written; `accounts` keeps every
constraint and every other index it had. Rolling it back costs a `DROP INDEX`
and returns the product to sorting each page — slower, and correct.

⚠ **WHY AN INDEX AND NOT A CAP.** The alternative way to make a 40,000-row
tenant's list fast is to stop serving all of it, and `NFR-5` forbids that
everywhere — it is the T4/T5 flexibility the PO ruled load-bearing. So the
ordering is indexed instead, and the list stays unbounded.

⚠ **CONCURRENCY, STATED HONESTLY.** This builds the index with a plain
`CREATE INDEX`, which takes an `ACCESS EXCLUSIVE`-adjacent share lock that
blocks WRITES to `accounts` while it builds — seconds on a 40,000-row table,
and this project has no deployment that runs migrations against a live
write-taking database (`10-scripts/13-provision-database.sh` provisions and
migrates before traffic). `CREATE INDEX CONCURRENTLY` cannot be used from
inside an atomic migration and would need `atomic = False` plus a non-
transactional runner; that trade belongs to whoever introduces zero-downtime
migrations, and pre-empting it here would leave a half-built index on failure
with nothing watching for it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0040_cr072_report_is_the_request"),
        ("metering", "0055_cr089_a_unit_point_and_gis_check"),
        ("tenancy", "0043_cr080_thermal_capacity_basis"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="account",
            index=models.Index(
                fields=["tenant", "-created_at", "-id"], name="ix_accounts_tenant_recent"
            ),
        ),
    ]
