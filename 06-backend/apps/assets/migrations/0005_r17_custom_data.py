# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (the r17.2 column set this completes; assets are NOT
#           reached by the R2 stamp — see the note below)
#           Screens: S49 · S50 · S51 (capture is EP-SHL-07, not this lane)
# Rules:    BR-TEN-046 (tenant-defined DATA, never schema) · BR-TEN-048 (a
#           custom field can never influence money) · BR-AUD-003 · CLAUDE.md
#           rule 1
# ───────────────────────────────────────────────────────
"""assets 0005 — r17.2 `custom_data jsonb NOT NULL DEFAULT '{}'` on `assets`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHY A COLUMN ON THE OWNING ROW AND NOT ONE SHARED `custom_field_value` TABLE
----------------------------------------------------------------------------
B2 r17.2 gives two reasons and both are structural, not stylistic. A shared
value table would be written by the customers, metering AND assets modules —
a cross-module write, forbidden by DB-16/§2. A column on your own row is
written only by its owning module's service. It also makes the audit free:
`audit_log` already snapshots the whole row's before/after (BR-AUD-003), so a
custom-value edit lands in the trail with no new audit code, where a separate
table would have needed its own path. A third benefit shows up only at RLS
time — these tables already carry ENABLE + FORCE, so the values inherit tenant
isolation with no new policy.

THIS IS THE HALF THAT IS *NOT* URGENT, and saying so is the point
-----------------------------------------------------------------
B12 r7.2 names one one-way door in this feature and it is `invoices.
custom_snapshot` (billing 0009): *"You cannot retroactively reconstruct what an
account looked like six months ago."* Of these columns the same paragraph says
the opposite in as many words — *"The master-data columns have no such door:
adding `custom_data DEFAULT '{}'` later is a clean, non-breaking migration."*
They ship in the same lane because the stamp needs something to read, not
because they could not have waited.

NO GIN INDEX (r17.2). Filtering and sorting over `custom_data` are explicitly
out of scope (BR-SHL-038) precisely so that no index decision is made before a
story needs one; `DEFAULT '{}'` costs effectively nothing on rows that never
use it.

`NOT NULL DEFAULT '{}'`, and Django only gives half of that: `JSONField(
default=dict)` applies its default in PYTHON and leaves no database default, so
an INSERT from a fixture, a repair script or a COPY would hit NOT NULL instead
of getting `{}`. The DEFAULT is set explicitly below on Postgres, where the
product runs; sqlite is the developer database and the Python-side default
covers it.

ASSETS ARE NOT REACHED BY THE R2 INVOICE STAMP, and the column ships anyway.
`feeder_number` and `pole_tag` are EP-TEN-09's own worked examples, so this is
the entity a tenant is most likely to extend first — but an account can have
several meters and the snapshot's key space is FLAT (`<entity>.<key>`, r17.3)
with nothing ruled about how two assets share one key. OQ-118. The storage is
correct either way; only the document side is undecided, and inventing
`assets.0.feeder_number` here would invent the contract R3's template variables
are written against.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: r17.2's literal `DEFAULT '{}'`, which Django's Python-side default does
#: not create. One line per table, the same boring pattern (LAW 0).
COLUMN_DEFAULT_SQL = """
ALTER TABLE assets ALTER COLUMN custom_data SET DEFAULT '{}'::jsonb;
"""

DROP_DEFAULT_SQL = """
ALTER TABLE assets ALTER COLUMN custom_data DROP DEFAULT;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0004_asset_meter_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        # The DB-level half of `NOT NULL DEFAULT '{}'` (r17.2).
        PostgresOnlySQL(sql=COLUMN_DEFAULT_SQL, reverse_sql=DROP_DEFAULT_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17.2 ·
#         EP-TEN-09-custom-fields.md · 01-tenancy/02-business-rules.md
#         BR-TEN-046/048)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean · migrate from empty on
#         sqlite and on a live Postgres cluster
# exceptions: (1) no GIN index (r17.2 — filtering/sorting over custom_data are
#         out per BR-SHL-038, so no index decision is made before a story needs
#         one) · (2) NO WRITE PATH SHIPS IN THIS LANE: the capture UI is
#         EP-SHL-07 and the definitions are EP-TEN-09. These are storage, read
#         today only by the invoice stamp through each module's own selector ·
#         (3) r17.6's "no DDL until the OQs are answered" is SATISFIED —
#         OQ-075/076/077 all closed 2026-08-10; B2's text still carries the old
#         block and that propagation is REPORTED, not done here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
