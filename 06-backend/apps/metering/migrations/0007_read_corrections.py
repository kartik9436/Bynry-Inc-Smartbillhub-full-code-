# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-016 (supersede & correction flow — the `read_corrections`
#           linkage J6 step 1 consumes, and the DATABASE half of "no committed
#           value is ever edited")   Screens: S25 · S29
# Rules:    BR-MET-053 (corrections = SUPERSEDE, never edit; billed-read error =
#           supersede + the J6 correction path; committed rows never UPDATE
#           except the two closure columns) · BR-MET-054 (update = supersede
#           only; delete = staged/rejected rows only) · CLAUDE.md rule 4
#           (financial immutability) · CLAUDE.md rule 1 + B2 §3 (RLS template)
# Tests:    06-backend/tests/test_us_met_016_tc_supersede.py (per-TC; the live
#           trigger halves are @pytest.mark.isolation on Postgres)
# Impacts:  apps/billing (reads the linkage in J6 step 1) · apps/metering
#           services.correct_billed_read · the G5 isolation sweep
# ───────────────────────────────────────────────────────
"""metering 0007 — `read_corrections` + the meter_reads value-immutability trigger.

HUMAN-OWNED (migration ordering 🔒; the trigger is a financial-immutability
guarantee). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of
2026-08-09 ("AI will do it; we will review it later as human"), implementing
SIGNED law only (BR-MET-053/054 + B2 r8 + CLAUDE.md rule 4). A row is requested
in 12-governance/09-human-review-ledger.md.

TWO THINGS, AND THE SECOND IS THE ONE THAT MATTERS
---------------------------------------------------
1. `read_corrections` — the PROPOSED-SCHEMA table US-MET-016 §5 names, with the
   B2 §3 tenant policy applied verbatim like every other tenant table.

2. `meter_reads_value_immutable` — US-MET-016 TC-5 in the database. The rule it
   enforces (BR-MET-053) was, until now, a SERVICE-LAYER convention: nothing
   stopped `MeterRead.objects.filter(...).update(current_value=…)` from any
   module, any shell, any future lane. A comment claiming a guarantee is not the
   guarantee (hard-won law 1), and this one guards the numbers a bill was priced
   from.

   WHAT THE TRIGGER FREEZES, and why exactly this set:

     asset_id · read_at · channel · prior_value · current_value · multiplier ·
     consumption · unit

   That is the MEASUREMENT — what was read, of what, when, in what unit, and the
   arithmetic derived from it. It is the whole of what "no committed value is
   ever edited" protects, and it is what an invoice was priced from.

   WHAT IT DELIBERATELY DOES NOT FREEZE, stated rather than left to be found:
   the two closure columns B2 r8 names (`superseded_by_id`, `superseded_at`),
   the `lifecycle` transition committed → billed (BR-MET-053's own lifecycle),
   the orthogonal dispute markers BR-MET-053 calls out by name
   (disputed→cleared), the US-MET-012 fix-disposition columns, and `status`
   (BR-MET-021's primary flag, which a disposition legitimately moves).

   This is a NARROWING of a literal reading of B2 r8 ("committed rows never
   UPDATE except these two closure columns") and it is flagged as such rather
   than quietly chosen: taken literally, that clause forbids the dispute markers
   and the BILLED lock the SAME rule (BR-MET-053) requires, so the two cannot
   both be true. The reading implemented here keeps the clause's PURPOSE — a
   committed value is immutable — and lets the lifecycle and marker columns the
   rule itself defines continue to move. REPORTED for the PO batch.

   DELETE is refused outright for every row of `meter_reads`, with no
   exception: BR-MET-054 puts the delete scope on `read_import_rows` (staged and
   rejected rows inside a batch), never here.

   Note what this trigger canNOT be asked to do: it does not fire on DROP TABLE,
   so the 7-year retention purge of a detached partition (US-MET-020) is
   unaffected and never needs the guarantee switched off, not even briefly.

`%` ESCAPING: there is no `%` in any statement below, so nothing here needs the
`%%` escape that the sqlite test tier cannot catch. The comparison uses
`to_jsonb(NEW) - 'col' - …`, which contains none.
"""

from django.db import migrations, models

import core.dbfields
from core.rls import tenant_isolation_policy_sql

#: BR-MET-053 / CLAUDE.md rule 4, in the database. See the module docstring for
#: the column set and for what is deliberately left mutable.
VALUE_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION meter_reads_value_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION
      'meter_reads is append-only: a committed read is corrected by a superseding row, never deleted (BR-MET-053/054)';
  END IF;
  IF OLD.asset_id       IS DISTINCT FROM NEW.asset_id
  OR OLD.read_at        IS DISTINCT FROM NEW.read_at
  OR OLD.channel        IS DISTINCT FROM NEW.channel
  OR OLD.prior_value    IS DISTINCT FROM NEW.prior_value
  OR OLD.current_value  IS DISTINCT FROM NEW.current_value
  OR OLD.multiplier     IS DISTINCT FROM NEW.multiplier
  OR OLD.consumption    IS DISTINCT FROM NEW.consumption
  OR OLD.unit           IS DISTINCT FROM NEW.unit THEN
    RAISE EXCEPTION
      'a committed read value is immutable: correct it with a superseding row (BR-MET-053, B2 r8)';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS meter_reads_value_immutable ON meter_reads;
CREATE TRIGGER meter_reads_value_immutable
  BEFORE UPDATE OR DELETE ON meter_reads
  FOR EACH ROW EXECUTE FUNCTION meter_reads_value_immutable();
"""

REVERSE_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS meter_reads_value_immutable ON meter_reads;
DROP FUNCTION IF EXISTS meter_reads_value_immutable();
"""


def apply_postgres_only(apps_registry, schema_editor):
    """Postgres: the tenant policy on the new table + the immutability trigger.

    sqlite keeps a plain table and no trigger, exactly as `0003_w2_reads` and
    `0004_rls_w2_reads_policies` already record for themselves: the DDL would be
    a lie there. The live assertions are the @pytest.mark.isolation halves.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(tenant_isolation_policy_sql("read_corrections"))
    schema_editor.execute(VALUE_IMMUTABILITY_SQL)


def unapply_postgres_only(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(REVERSE_IMMUTABILITY_SQL)
    schema_editor.execute(
        "DROP POLICY IF EXISTS read_corrections_tenant_isolation ON read_corrections;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0006_r17_custom_data"),
        ("assets", "0005_r17_custom_data"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadCorrection",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("superseded_read_id", models.UUIDField()),
                ("superseding_read_id", models.UUIDField()),
                ("invoice_id", models.UUIDField()),
                ("invoice_no", models.TextField(blank=True, null=True)),
                ("channel", models.TextField(default="total")),
                ("reason", models.TextField()),
                ("status", models.TextField(default="open")),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        db_column="asset_id",
                        on_delete=models.PROTECT,
                        to="assets.asset",
                    ),
                ),
                (
                    "opened_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="opened_by",
                        null=True,
                        on_delete=models.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "read_corrections",
                "indexes": [
                    models.Index(
                        fields=["tenant", "invoice_id"], name="ix_read_corrections_invoice"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["tenant", "superseded_read_id", "invoice_id"],
                        name="uq_read_corrections_pair",
                    )
                ],
            },
        ),
        migrations.RunPython(apply_postgres_only, unapply_postgres_only),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-016@c81d5a7 (EP-MET-04 supersede & correction story)
# generated: 2026-08-15 by story-coder v1 (metering + assets + audit lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row requested)
# gates: ruff✔ black✔ · makemigrations --check clean for apps.metering · migrate from empty on sqlite and on a live Postgres cluster · trigger PROVED RED before trusting it green (see the lane report for the exact failure text)
# exceptions: the immutability trigger NARROWS B2 r8's literal "except these two closure columns" so the lifecycle + dispute + fix-disposition columns the SAME rule defines can still move — the reasoning is in the docstring and is REPORTED for the PO batch, not chosen silently · `invoice_id` is a bare uuid, not an FK (a metering→billing FK would add a migration-ordering edge for a reference billing must resolve anyway; validated at write time through the seam instead) · sqlite gets the table but neither the policy nor the trigger, recorded here and asserted only under @pytest.mark.isolation
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
