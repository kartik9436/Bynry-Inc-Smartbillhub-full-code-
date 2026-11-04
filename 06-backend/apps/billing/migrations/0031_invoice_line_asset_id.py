# ── Trace ──────────────────────────────────────────────
# Task:     One-time bill build plan `DB1` (04-docs/05-modules/07-billing/
#           12-one-time-bill-build-plan.md) — `invoice_lines.asset_id`
#           (nullable) so a line names its meter.
# Ruling:   PO 2026-09-30, decision log: *"both meter should be build in
#           metered case also - as a speearte line"* — two water meters bill
#           2 × ($21.20 + $8.00) = $58.40 on two sets of lines, and a document
#           must say which line is which meter.
# Rules:    B2 §2 (cross-module FKs are the REVIEWED interface set) · B11 F-3
#           (the deferred-FK shape: a plain uuid until the reference is
#           reviewed) · CLAUDE.md hard rule 4 (issued lines are immutable — a
#           nullable ADD COLUMN rewrites no row)
# Tests:    06-backend/tests/test_br_bil_300_services_rulings_2026_09_30.py ·
#           10-scripts/br_bil_300_services_rulings_pg_measure.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""billing 0031 — `invoice_lines.asset_id`: which meter a line was priced for.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. Row in `12-governance/09-human-review-ledger.md`
(*"NEW ROW 2026-09-30 · ONE-TIME BILL BUILD PLAN `B1` … `DB1`"*).

WHAT IT IS
----------
One nullable `uuid` column. NULL on every existing row and on every line whose
service carries one meter, so no bill already written changes and no ❄️ B5
figure can move.

WHY A PLAIN UUID AND NOT A FOREIGN KEY
--------------------------------------
B2 §2 makes a cross-module foreign key a REVIEWED interface, and the build plan
names this one as needing that review (`DB1`: *"a new cross-module FK,
reviewed under B2 §2"*). The review has not happened, so this migration does
not decide it: the column carries the id and the database does not yet police
it — exactly the `B11 F-3` shape `invoice_lines.gl_account_id` had until
`billing/0030` added its constraint. When the review lands, the constraint is
one `ALTER TABLE invoice_lines ADD CONSTRAINT … REFERENCES assets(id)
DEFERRABLE INITIALLY DEFERRED` in 0030's form.

⚠ **`invoice_lines` IS A PARTITIONED PARENT** (`billing/0016`). On PostgreSQL an
`ADD COLUMN` on the parent is propagated to every partition and inherited by
every future one, and a nullable column with no default is a catalogue-only
change — no row is rewritten, so hard rule 4's immutability trigger never
fires. Proved forward on real PostgreSQL 16 by the measure script above.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0030_p0_4_gl_pointers_become_foreign_keys"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceline",
            name="asset_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
