"""rating 0065 — a discount grant can be REVERSED, once, and no grant is ever edited.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and an idempotency
key, both on CLAUDE.md's sensitive-paths list. AI-authored 2026-10-03 under the
PO ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"2026-10-03 · DISCOUNT GRANTS RECORDED AT ISSUE"*).

WHY (`DEF-2430` / `DEF-BIL-5341`, PO ruling 2026-10-03 *"A · Yearly caps don't
count down - a"*). Issue now records one `discount_grants` row per enrolment a
bill spent, so a yearly cap and a budget count down. A CORRECTED bill must give
its subsidy back before the replacement bill is priced, or the replacement sees
a cap already spent by the bill it replaces: Carl's $25.00 CAP credit on a
corrected December bill would be counted twice and his rebill would get $0.00.
Hard rule 4 makes that a NEW row of the opposite sign, never an edit.

WHAT IT CHANGES
1. `reverses_grant_id` — nullable self-reference, set on a reversal row only.
2. `uq_discount_grants_enrolment_invoice` (one grant per enrolment per bill —
   rule 6 at issue) now EXCLUDES reversal rows, which carry the corrected
   bill's own `invoice_id` so they land in the same cap year as the money they
   cancel.
3. `uq_discount_grants_reverses_grant` — a grant is reversed at most once, so a
   replayed correction cannot hand the cap headroom back twice (rule 6 at
   correction).
4. PostgreSQL only: `trg_discount_grant_append_only` refuses every UPDATE and
   DELETE on `discount_grants`. The model has said *"APPEND-ONLY (hard rule 4)"*
   since 2026-08-19 and nothing enforced it (hard-won law 1); now that real
   bills write it, the sentence becomes a fact. SQLite has no such trigger and
   the service layer is the only writer.

DOWN PATH. Drop the trigger, restore the original unique constraint, drop the
column. ⚠ Reversing after a correction has written a reversal row FAILS on the
restored constraint (the reversal and the original share an enrolment and an
invoice) — deliberately: dropping the column would silently turn a reversal
into a second grant against the same bill. Delete nothing by hand; roll the
code back instead and leave this migration applied.
"""

from django.db import migrations, models
from django.db.models import Q

import django.db.models.deletion

from core.migrationtools import PostgresOnlySQL

#: A single `%` — `RunSQL` with a plain string executes it with no params, so
#: psycopg does not read it as a format template (unlike payments/0002, which
#: calls `schema_editor.execute(sql)` and so doubles every `%`).
APPEND_ONLY = """
CREATE OR REPLACE FUNCTION rating_discount_grant_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'hard rule 4: discount grant % is append-only (attempted %). A corrected bill gives its subsidy back with a NEW row of the opposite sign that names the grant it reverses; nothing edits or removes a grant.',
    COALESCE(OLD.id::text, NEW.id::text), lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_discount_grant_append_only ON discount_grants;
CREATE TRIGGER trg_discount_grant_append_only
  BEFORE UPDATE OR DELETE ON discount_grants
  FOR EACH ROW EXECUTE FUNCTION rating_discount_grant_append_only();
"""

DROP_APPEND_ONLY = """
DROP TRIGGER IF EXISTS trg_discount_grant_append_only ON discount_grants;
DROP FUNCTION IF EXISTS rating_discount_grant_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0064_cr167_plan_version_lock"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountgrant",
            name="reverses_grant",
            field=models.ForeignKey(
                blank=True,
                db_column="reverses_grant_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="rating.discountgrant",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="discountgrant",
            name="uq_discount_grants_enrolment_invoice",
        ),
        migrations.AddConstraint(
            model_name="discountgrant",
            constraint=models.UniqueConstraint(
                condition=Q(invoice_id__isnull=False, reverses_grant__isnull=True),
                fields=("enrolment", "invoice_id"),
                name="uq_discount_grants_enrolment_invoice",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountgrant",
            constraint=models.UniqueConstraint(
                condition=Q(reverses_grant__isnull=False),
                fields=("reverses_grant",),
                name="uq_discount_grants_reverses_grant",
            ),
        ),
        PostgresOnlySQL(sql=APPEND_ONLY, reverse_sql=DROP_APPEND_ONLY),
    ]
