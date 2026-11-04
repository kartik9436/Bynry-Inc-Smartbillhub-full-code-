# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-003 (accounts — the row this column rides on)
#           Change: OQ-314 second half (PO ruling 2026-08-22, master accounts)
# Rules:    BR-CUS-068 (a master account is an ordinary `accounts` row,
#           `kind='master'` — no new table) · BR-MET-101 (the common-area half,
#           already shipped) · CLAUDE.md rule 1 (tenant scoping / RLS)
# ───────────────────────────────────────────────────────
"""customers 0012 — BR-CUS-068's `accounts.kind` column.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-22 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHY A COLUMN AND NOT A FIFTH `account_types` ROW. The platform catalog is the
SIGNED four-code consumer-category vocabulary — B2 r5 #12 [D5] verbatim, and
customers 0003's own docstring names B2 as the tiebreaker if the copies ever
diverge. Seeding `master` there would amend a signed vocabulary without a
re-sign AND conflate two orthogonal facts: a master account still HAS a
consumer category (a residential building's shared hallway is residential).
The PO's confirmed design says the word itself: *"kind='master'"* (decision log
2026-08-22, OQ-314 second half).

ONE TextField, default `regular`, nothing else. Every existing account IS a
regular account — the master path did not exist before this migration, so the
backfill is the default itself and no per-tenant data step is needed (contrast
metering 0016, whose backfill promoted rows a tenant had already typed).

RLS: NOTHING TO RE-POLICE. `accounts` has had ENABLE+FORCE row-level security
and the B2 §3 tenant-isolation policy since customers 0002, and that policy is
row-scoped, not column-scoped — a new column on an already-policed table is
covered the moment it exists.

DB DEFAULT 'regular', EXPLICITLY. Django applies `default=` in Python only; the
column itself would carry no DEFAULT, so an INSERT from a repair script or a
COPY would hit NOT NULL. Same correction metering 0016 made for
`is_common_area` and metering 0008 for `is_sample` — set below on Postgres.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

COLUMN_DEFAULT_SQL = """
ALTER TABLE accounts ALTER COLUMN kind SET DEFAULT 'regular';
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0011_cr010_account_subtype_parent"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="kind",
            field=models.TextField(default="regular"),
        ),
        PostgresOnlySQL(COLUMN_DEFAULT_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-003@b52ca30 (story+rules snapshot; change source: OQ-314 second half, PO ruling 2026-08-22, BR-CUS-068)
# generated: 2026-08-22 by story-coder (master-accounts lane)
# checklist: A✔ B✔ C✔ (tests/test_br_cus_068_master_accounts.py) D✔ (POST /accounts/master serves it) E=deferred(frontend half is another lane's files this round — PRM-02 Common-areas tab / accounts-list kind chip still owed) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 migration ordering, ledger row appended)
# gates: makemigrations --check clean · migrate-from-empty ✔ (see lane report)
# exceptions: none — one AddField + a DB-level DEFAULT, no data step (see docstring for why no backfill exists)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
