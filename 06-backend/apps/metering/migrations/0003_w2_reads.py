# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007..010 (S28 read-import wizard — staged batch, validation,
#           dispositions, atomic commit) · US-MET-011 (config-driven flag
#           engine — read_validation_settings) · US-MET-014/015 (estimation +
#           true-up columns)   Screens: S25, S28, S29, S64
# Rules:    BR-MET-012 (staged import — no meter_reads row before commit) ·
#           BR-MET-016/024/053 (supersede chain, never an UPDATE of a value) ·
#           BR-MET-017 (compliance stamp per batch; every read links to it) ·
#           BR-MET-018 🔒 (file+tags idempotency — DB-12) · BR-MET-019
#           (consumption NUMERIC(18,6) with an explicit unit) · BR-MET-020
#           (thresholds are tenant CONFIG, never hardcoded — B2 r5 #15) ·
#           BR-MET-021/052 (status vocabulary + VEE catalog) · BR-MET-055
#           (monthly partitions, 2-yr hot window) · BR-MET-058/059 (channel
#           model, per-channel estimation) · DB-6/DB-7/DB-12
# Tests:    06-backend/tests/test_w2_reads_models.py (shape + constraint half on
#           the migrated sqlite DB) · tests/test_us_met_011_validation.py ·
#           tests/test_us_met_007_010_read_import.py · live RLS/partition proofs
#           = the G5 isolation suite (tests/test_us_met_reads_isolation.py)
# Impacts:  apps/metering/{services,selectors,validation,estimation,read_import}.py ·
#           billing read pickup (W3) · core/partitioning.py ACTIVE_TABLES (gap —
#           see the module docstring)
# ───────────────────────────────────────────────────────
"""metering 0003 — the W2 READS tables: `read_validation_settings` (B2 r5 #15),
`read_import_batches` / `read_import_rows` (US-MET-007..010 §5 PROPOSED-SCHEMA)
and `meter_reads` built to the B2 r8 CHANNEL end-state. HUMAN-OWNED (migration
ordering is a CLAUDE.md 🔒 sensitive path; so is the file+tags idempotency
unique this migration materialises).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing SIGNED schema
law only: B2 §2 `meter_reads` DDL as REDLINED by r8 (channel model + supersede
closure columns, DB-6), B2 r5 #15 (`read_validation_settings`, an APPROVED
table with PO-ratified seeded defaults), DB-7/NFR-24 monthly partitioning and
DB-12 ("file+tags imports" idempotency unique). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Ordering: after metering 0002 (its own RLS) and after assets/customers/identity,
whose tables `meter_reads` references through the B2 §2 REVIEWED cross-module
FK set (asset_id, account_id, imported_by) — B2 §7 module order is respected,
this migration only adds the edges those modules' tables already invited.

Two-vendor reality, recorded honestly (same posture as apps/audit/0001):
- Postgres: the Django-created plain `meter_reads` is dropped and re-created as
  the PARTITIONED parent — `PARTITION BY RANGE (read_at)`, PK
  (tenant_id, read_at, id) exactly as B2 §2 writes it — and bootstrap monthly
  partitions are created across the whole 2-year HOT WINDOW plus 3 months ahead.
  The back-window is deliberate and differs from audit_log's current+3: an
  import batch carries HISTORICAL read dates (a utility onboarding loads years
  of history, and BR-MET-026 estimation reads a meter's trailing cycles), so a
  parent with only future partitions would reject lawful rows.
  The FK constraints and the Meta indexes/constraints are NOT restated in the
  DDL below: Django emits FK constraints as deferred SQL flushed at the END of
  the migration, and the AddIndex/AddConstraint operations are sequenced AFTER
  the swap — so both land on the partitioned parent, once.
- sqlite (test DB): the plain table stands so model/constraint tests run;
  partitioning and RLS do not exist there. Those assertions live in the G5
  isolation suite against live Postgres, never faked.

⚠ FOR THE REVIEWER — one gap this migration cannot close from inside its lane:
`core/partitioning.py` (BE-10) lists `meter_reads` in its REGISTRY but not in
`ACTIVE_TABLES`, and `tests/test_be10_partitioning.py` pins that frozenset to
{"audit_log"}. So the scheduled `maintain_partitions` create-ahead job still
skips `meter_reads`: the bootstrap partitions below cover the hot window and
3 months ahead, and NOTHING renews them afterwards. Flipping the entry on (and
the matching test) belongs to core/'s owner. REPORTED, not silently patched.

RLS (ENABLE+FORCE per the B2 §3 template) rides 0004_rls_w2_reads_policies.
"""

from datetime import date

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

# The parent DDL mirrors the CreateModel columns EXACTLY (B2 §2 as redlined by
# r8). Column ORDER follows the model so a reviewer can diff the two side by
# side; NULLability follows B2 (`unit`, `source` NOT NULL — CLAUDE.md rule 3
# gives consumption its explicit unit at every single row).
PARTITIONED_PARENT_SQL = """
DROP TABLE IF EXISTS meter_reads;
CREATE TABLE meter_reads (
  id                      uuid NOT NULL,
  tenant_id               uuid NOT NULL,
  asset_id                uuid NOT NULL,
  account_id              uuid,
  read_at                 timestamptz NOT NULL,        -- partition key
  channel                 text NOT NULL DEFAULT 'total',
  period_start            date,
  period_end              date,
  prior_value             numeric(18,6),
  current_value           numeric(18,6),               -- NULL on an estimate (BR-MET-028)
  multiplier              numeric(18,6),
  consumption             numeric(18,6),
  unit                    text NOT NULL,               -- EXPLICIT always (CLAUDE.md rule 3)
  source                  text NOT NULL,
  source_detail           text,
  status                  text NOT NULL DEFAULT 'ok',
  lifecycle               text NOT NULL DEFAULT 'committed',
  days_since_prior        integer,
  rule_outcomes           jsonb,
  import_batch_id         uuid,
  imported_by             uuid,
  disposition             text,
  disposition_reason      text,
  fix_disposition         text,
  fix_reason              text,
  fixed_by                uuid,
  superseded_by_id        uuid,                        -- bare uuid: no unique on id alone
  superseded_at           timestamptz,
  supersede_reason        text,
  estimation_method       text,
  consecutive_estimate_no integer,
  trues_up_read_ids       jsonb,
  disputed_at             timestamptz,
  dispute_reason          text,
  disputed_by             uuid,
  dispute_cleared_at      timestamptz,
  dispute_cleared_by      uuid,
  demand_reset_noted      boolean NOT NULL DEFAULT false,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, read_at, id)                 -- includes the partition key (B2 §2)
) PARTITION BY RANGE (read_at);
COMMENT ON COLUMN meter_reads.consumption IS
  'NUMERIC(18,6); rounding at invoice-line finalization only';
COMMENT ON COLUMN meter_reads.unit IS
  'Explicit UoM, stamped from the asset — never inferred from service (CLAUDE.md rule 3)';
"""

# BR-MET-055 hot window (2 years) — writable from day one, see the docstring.
BOOTSTRAP_MONTHS_BACK = 24
BOOTSTRAP_MONTHS_AHEAD = 3


def create_partitioned_parent(apps_registry, schema_editor):
    """Postgres only: swap the plain table for the partitioned parent and
    bootstrap the hot window + 3 months ahead (B2 §5 create-ahead)."""
    if schema_editor.connection.vendor != "postgresql":
        return  # sqlite test DB keeps the plain table — recorded in the docstring
    from core import partitioning

    schema_editor.execute(PARTITIONED_PARENT_SQL)
    current = partitioning.month_start(date.today())
    for offset in range(-BOOTSTRAP_MONTHS_BACK, BOOTSTRAP_MONTHS_AHEAD + 1):
        month = partitioning.add_months(current, offset)
        schema_editor.execute(partitioning.create_partition_sql("meter_reads", month))


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0004_asset_meter_type"),
        ("customers", "0003_seed_account_types"),
        ("identity", "0004_rls_security_policies"),
        ("metering", "0002_rls_w1_policies"),
        ("tenancy", "0005_seed_subscription_plans"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadImportBatch",
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
                ("batch_no", models.TextField(blank=True, null=True)),
                ("source_kind", models.TextField(default="csv")),
                ("source_detail", models.TextField(blank=True, null=True)),
                ("period_month", models.DateField(blank=True, null=True)),
                ("service", models.TextField(blank=True, null=True)),
                ("file_name", models.TextField(blank=True, null=True)),
                ("file_hash", models.TextField(blank=True, null=True)),
                ("tag_fingerprint", models.TextField(blank=True, null=True)),
                ("uploaded_at", models.DateTimeField(blank=True, null=True)),
                ("session_ref", models.TextField(blank=True, null=True)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("certified_by_uploader", models.BooleanField(default=False)),
                ("counts", models.JSONField(blank=True, null=True)),
                ("status", models.TextField(default="staged")),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cosigned_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="cosigned_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cosigned_read_batches",
                        to="identity.user",
                    ),
                ),
                (
                    "cycle",
                    models.ForeignKey(
                        blank=True,
                        db_column="cycle_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.cycle",
                    ),
                ),
                (
                    "route",
                    models.ForeignKey(
                        blank=True,
                        db_column="route_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.route",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="uploaded_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "read_import_batches",
            },
        ),
        migrations.CreateModel(
            name="MeterRead",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "tenant_id",
                        "read_at",
                        "id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("id", models.UUIDField(default=core.dbfields.uuid7, editable=False)),
                ("read_at", models.DateTimeField()),
                ("channel", models.TextField(default="total")),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                (
                    "prior_value",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "current_value",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "multiplier",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "consumption",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("unit", models.TextField()),
                ("source", models.TextField()),
                ("source_detail", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="ok")),
                ("lifecycle", models.TextField(default="committed")),
                ("days_since_prior", models.IntegerField(blank=True, null=True)),
                ("rule_outcomes", models.JSONField(blank=True, null=True)),
                ("disposition", models.TextField(blank=True, null=True)),
                ("disposition_reason", models.TextField(blank=True, null=True)),
                ("fix_disposition", models.TextField(blank=True, null=True)),
                ("fix_reason", models.TextField(blank=True, null=True)),
                ("superseded_by_id", models.UUIDField(blank=True, null=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                ("supersede_reason", models.TextField(blank=True, null=True)),
                ("estimation_method", models.TextField(blank=True, null=True)),
                ("consecutive_estimate_no", models.IntegerField(blank=True, null=True)),
                ("trues_up_read_ids", models.JSONField(blank=True, null=True)),
                ("disputed_at", models.DateTimeField(blank=True, null=True)),
                ("dispute_reason", models.TextField(blank=True, null=True)),
                ("dispute_cleared_at", models.DateTimeField(blank=True, null=True)),
                ("demand_reset_noted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        db_column="account_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "asset",
                    models.ForeignKey(
                        db_column="asset_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="assets.asset",
                    ),
                ),
                (
                    "dispute_cleared_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="dispute_cleared_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cleared_read_disputes",
                        to="identity.user",
                    ),
                ),
                (
                    "disputed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="disputed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="disputed_reads",
                        to="identity.user",
                    ),
                ),
                (
                    "fixed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="fixed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fixed_reads",
                        to="identity.user",
                    ),
                ),
                (
                    "imported_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="imported_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="imported_reads",
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "import_batch",
                    models.ForeignKey(
                        blank=True,
                        db_column="import_batch_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.readimportbatch",
                    ),
                ),
            ],
            options={
                "db_table": "meter_reads",
            },
        ),
        migrations.CreateModel(
            name="ReadImportRow",
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
                ("row_no", models.IntegerField()),
                ("meter_no_raw", models.TextField(blank=True, null=True)),
                ("read_at_raw", models.TextField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("channel", models.TextField(default="total")),
                (
                    "value",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "raw_value",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("service", models.TextField(blank=True, null=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("demand_reset_noted", models.BooleanField(default=False)),
                ("rule_outcomes", models.JSONField(blank=True, null=True)),
                ("severity", models.TextField(default="ok")),
                ("disposition", models.TextField(blank=True, null=True)),
                ("disposition_reason", models.TextField(blank=True, null=True)),
                ("meter_read_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        db_column="asset_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="assets.asset",
                    ),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.readimportbatch",
                    ),
                ),
                (
                    "disposed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="disposed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "read_import_rows",
            },
        ),
        migrations.CreateModel(
            name="ReadValidationSettings",
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
                ("high_pct", models.DecimalField(decimal_places=6, default=200, max_digits=18)),
                ("high_abs_kwh", models.DecimalField(decimal_places=6, default=50, max_digits=18)),
                ("high_abs_kgal", models.DecimalField(decimal_places=6, default=1, max_digits=18)),
                ("low_pct", models.DecimalField(decimal_places=6, default=25, max_digits=18)),
                ("zero_scope", models.TextField(default="active_non_vacant")),
                ("days_flag_min", models.IntegerField(default=25)),
                ("days_flag_max", models.IntegerField(default=35)),
                ("days_hard_min", models.IntegerField(default=20)),
                ("days_hard_max", models.IntegerField(default=45)),
                (
                    "mismatch_default_pct",
                    models.DecimalField(decimal_places=6, default=3, max_digits=18),
                ),
                (
                    "tou_sum_tolerance_pct",
                    models.DecimalField(decimal_places=6, default=1, max_digits=18),
                ),
                ("est_method", models.TextField(default="trailing_3_daily_avg")),
                ("est_max_consecutive", models.IntegerField(default=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "read_validation_settings",
            },
        ),
        migrations.AddConstraint(
            model_name="readimportbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("batch_no__isnull", False)),
                fields=("tenant", "batch_no"),
                name="uq_read_import_batches_no",
            ),
        ),
        migrations.AddConstraint(
            model_name="readimportbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("file_hash__isnull", False), ("status", "posted")),
                fields=("tenant", "file_hash", "tag_fingerprint"),
                name="uq_read_import_batches_idempotency",
            ),
        ),
        # The plain table becomes the PARTITIONED parent HERE — before the
        # meter_reads indexes and the head-uniqueness constraint below, so both
        # are built on the parent and propagate to every partition (PG11+).
        migrations.RunPython(create_partitioned_parent, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="meterread",
            index=models.Index(
                fields=["tenant", "account", "read_at"], name="ix_meter_reads_acct_period"
            ),
        ),
        migrations.AddIndex(
            model_name="meterread",
            index=models.Index(
                fields=["tenant", "asset", "channel"], name="ix_meter_reads_asset_channel"
            ),
        ),
        migrations.AddConstraint(
            model_name="meterread",
            constraint=models.UniqueConstraint(
                condition=models.Q(("superseded_by_id__isnull", True)),
                fields=("tenant", "asset", "read_at", "channel"),
                name="uq_meter_reads_head",
            ),
        ),
        migrations.AddIndex(
            model_name="readimportrow",
            index=models.Index(fields=["tenant", "batch"], name="ix_read_import_rows_batch"),
        ),
        migrations.AddConstraint(
            model_name="readimportrow",
            constraint=models.UniqueConstraint(
                fields=("batch", "row_no"), name="uq_read_import_rows"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-007@a4d93b5 (story+rules snapshot — EP-MET-03 lead story; co-packets EP-MET-04@64b3d87 · EP-MET-05@feddf11)
# generated: 2026-08-10 by the W2 reads lane (schema half — models + migration)
# checklist: A✔ B✔ C✔ D=deferred(API half lands in apps/metering/api.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — ruff✔ black✔ · tests/test_w2_reads_models.py 17 passed · migrate applied clean on live PG 16 (relkind 'p', 28 partitions, 8 FKs, uq_meter_reads_head) · -m isolation 5 passed under the NOSUPERUSER probe role
# exceptions: uq_meter_reads_head is PARTIAL (heads only) — the only reading under which both of B2 r8's clauses hold, Eng disposition REPORTED · bootstrap covers 24 months back + 3 ahead (not audit_log's current+3) because import batches carry historical read dates · core/partitioning.ACTIVE_TABLES still omits meter_reads, so the create-ahead job does not renew these partitions — outside this lane, REPORTED · `lifecycle` column added because BR-MET-053's committed→BILLED state cannot share `status` with BR-MET-021's one-primary-flag rule — Eng disposition REPORTED · trues_up_read_ids stored as JSON rather than uuid[] (sqlite test DB has no array type) — same disposition as premises.services_available
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
