# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W6 task 6.1 — the New Connect tables + RLS (B18 §5.4.6,
#           §6.3) **as corrected by the PO's five New Connect screens of
#           2026-08-25**: `work_orders.mode` NOT NULL (MODE is drawn per order),
#           `work_orders.is_gate` + `template_id` (the 🚩 is drawn on the
#           order), `connections.waiting_on` (a column of its own beside STATE,
#           not the hold's reason)   Screens: NCT-01 · NCT-02 · S86 · S87 · S88
#           (no screen built by this lane)
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS ENABLE + FORCE, no exceptions — B18 §6.3 says it
#           again for these five) · B2 §3 policy template with DEF-639's NULLIF
#           repair · hard rule 3 (`service_characteristics.unit_of_measure` is a
#           COLUMN, NOT NULL — never a suffix on a key name) ·
#           BR-MET-108 (a ROW per characteristic, keyed by unit and service —
#           CONFIRMED 2026-08-25, W6 task 6.9a) · BR-MET-104 (PO 2026-08-24,
#           closing OQ-348 — the characteristic lives on the UNIT) ·
#           BR-TEN-057 (`is_sample` on the OWNING row)
# Tests:    06-backend/tests/test_w6_connections.py (the policy shape is
#           asserted against this module's own POLICIES string — NOT a grep of
#           the source, which would pass on a file that generates nothing; the
#           live probe rides the G5 isolation sweep)
# Impacts:  apps/metering/connections.py (the five model classes) ·
#           apps/metering/models.py ⚠ must import that module for the model
#           registry — one line, REPORTED (apps/rating/models.py:1628 precedent)
# ───────────────────────────────────────────────────────
"""metering 0026 — CR-030 W6's five tables, and their policies, in ONE file.
HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-25 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*), applying the SIGNED B2 §3
policy template. A row is owed in `12-governance/09-human-review-ledger.md`;
that file is not this lane's, so the row is REPORTED for the orchestrator to
land. Not RATIFIED without a recorded human sign-off.

ADDITIVE ONLY: five new tables, no existing table altered, nothing backfilled,
and no row anywhere changing meaning on this commit. All five are EMPTY after it
and stay empty until W6's own services write into them — `work_order_templates`
included, because seeding the ten per-service sets is task 6.3 and **gas gates
on the light-up, not the meter set** (B18 §8.1); a lane that seeds it wrong bills
a customer with no gas.

════════════════════════════════════════════════════════════════════════════
WHY THE SCHEMA AND THE POLICIES ARE ONE MIGRATION AND NOT THE USUAL PAIR
════════════════════════════════════════════════════════════════════════════
metering 0024/0025 and 0014/0015 each split CreateModel from the policy and both
carry the same warning: *"A tenant table with no policy is a CLAUDE.md rule-1
violation between the two migrations and the pair must be applied together."*
That window is a real thing — a half-applied `migrate` leaves five unguarded
tenant tables — and the ONLY reason the split ever existed is DEF-639: enabling
FORCE RLS in the same migration that creates the tables meant Django's deferred
FK validation, scheduled implicitly at the migration's EXIT, ran under a policy
whose predicate cast `''::uuid` and DIED.

DEF-639 is fixed. The predicate below is the NULLIF form, so an unset or empty
`app.tenant_id` reads as NULL, `tenant_id = NULL` is NULL, the row is denied, and
**nothing raises**. The FK validation scan at this migration's exit therefore
finds an empty table it is not allowed to see, which is exactly correct. With the
cast no longer able to poison it, keeping the pair in one file closes the window
instead of documenting it.

⚠ THIS MIGRATION DOES NOT SET OR CLEAR TENANT CONTEXT AT ALL — there is no
`RunPython` and no seed step, so OQ-354/DEF-639's *"leave the nil sentinel
00000000-0000-0000-0000-000000000000, never `''`"* rule has nothing to apply to
here. Stated rather than omitted: the next lane adding a seed step to a metering
migration must read `apps/tenancy/migrations/0004_*.py::_leave_tenant` first.

    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;   -- the owner too
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

⚠ NONE OF THE FIVE IS PARTITIONED, deliberately. NFR-24 names five tables and
none of these is one of them; `meter_reads` is partitioned because it grows with
every register on every read day, and a connection table grows with BUILDS — for
the <3,000-connection utility this product is for (CLAUDE.md), a few hundred rows
a year. Inheriting metering 0003/0004's partition machinery would buy nothing and
would drag the partition-RLS hazard (a partition queried DIRECTLY consults only
its own policies, and `CREATE TABLE … PARTITION OF` creates it with RLS DISABLED)
into a table that does not need it.

⚠ FOR THE REVIEWER — TWO NEW CROSS-MODULE FKs, both drawn by B18 §5.4.6 and
neither yet in B2 §2's reviewed interface set:

  * `connections.request_id → customers.service_requests` (§5.4.6 `request_id`)
  * `work_orders.asset_id → assets.assets` (§5.4.6 `asset_id`)

metering already holds reviewed FKs INTO customers (`meter_reads.account_id`,
`meter_read_monthly_usage.account_id`) and assets holds one INTO metering
(`service_points`), so neither direction is new in principle — but these two
edges are, and B2 §2's rule exists to make somebody look. REPORTED, not assumed.

⚠ AND ONE HOSTING CALL, identical to the one metering 0004, 0015, 0025,
customers 0002, identity 0004 and tenancy 0004 each flagged: the policy SQL is
INLINE here rather than in `06-backend/db/`, because that directory is outside
this lane's stated territory. That is now SEVEN files wanting the same
relocation, as one edit, by whoever owns it.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proof is the G5 isolation suite (NFR-10, zero
tolerance, release blocker).
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields
from core.migrationtools import PostgresOnlySQL

TABLES = (
    "connections",
    "connection_services",
    "work_orders",
    "work_order_templates",
    "service_characteristics",
)

#: B2 §3 template with DEF-639's cast repair — see the docstring. G41 ratchets
#: the old bare-cast form and this is the form it ratchets TOWARDS.
PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICIES = "\n".join(f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      ({PREDICATE})
  WITH CHECK ({PREDICATE});
""" for table in TABLES)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0001_initial"),
        ("customers", "0018_rls_cr031_service_requests"),
        ("metering", "0025_rls_br_met_106_monthly_usage"),
        ("tenancy", "0017_br_ast_048_mapping_templates"),
    ]

    operations = [
        migrations.CreateModel(
            name="Connection",
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
                ("connection_no", models.TextField(blank=True, null=True)),
                ("state", models.TextField(default="draft")),
                ("mode", models.TextField(default="our_crew")),
                ("target_energisation", models.DateField(blank=True, null=True)),
                ("energised_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("held_at", models.DateTimeField(blank=True, null=True)),
                # NCT-01's `WAITING ON` column — an INDEPENDENT AXIS from state,
                # not the hold's reason: two of the five drawn rows wait on
                # something while NOT being on hold.
                ("waiting_on", models.TextField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_reason", models.TextField(blank=True, null=True)),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "premises",
                    models.ForeignKey(
                        db_column="premises_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.premises",
                    ),
                ),
                (
                    "service_request",
                    models.ForeignKey(
                        blank=True,
                        db_column="request_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.servicerequest",
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
                "db_table": "connections",
                "indexes": [
                    models.Index(fields=["tenant", "state"], name="ix_connections_tenant_state"),
                    models.Index(
                        fields=["tenant", "target_energisation"],
                        name="ix_connections_tenant_target",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("connection_no__isnull", False)),
                        fields=("tenant", "connection_no"),
                        name="uq_connections_tenant_no",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplate",
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
                ("sequence", models.IntegerField(default=0)),
                ("name", models.TextField()),
                ("scope", models.TextField(default="per_premise")),
                ("skill", models.TextField(blank=True, null=True)),
                ("est_duration", models.DurationField(blank=True, null=True)),
                ("is_gate", models.BooleanField(default=False)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                "db_table": "work_order_templates",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "service", "sequence"),
                        name="uq_work_order_templates_seq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrder",
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
                ("order_no", models.TextField(blank=True, null=True)),
                ("type", models.TextField()),
                ("scope", models.TextField(default="per_premise")),
                ("state", models.TextField(default="planned")),
                ("outcome", models.TextField(blank=True, null=True)),
                # NOT NULL and STAMPED at creation — NCT-01's Work orders tab
                # draws MODE per order, so how a job is run is a fact about the
                # job (§8.3). `connections.mode` is only the wizard default it
                # is copied from.
                ("mode", models.TextField(default="our_crew")),
                # NOT IN B18 §5.4.6 — added from the SCREEN, which is the
                # reference: NCT-01 draws the gate as a 🚩 on the ORDER's name.
                # STAMPED rather than read through `template_id`, so a tenant
                # editing a template cannot change what gated work already in
                # the field.
                ("is_gate", models.BooleanField(default=False)),
                ("external_ref", models.TextField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("attachment_ref", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
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
                    "blocked_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="blocked_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.workorder",
                    ),
                ),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="work_orders",
                        to="metering.connection",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        db_column="service_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                    "template",
                    models.ForeignKey(
                        blank=True,
                        db_column="template_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.workordertemplate",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        db_column="unit_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.unit",
                    ),
                ),
            ],
            options={
                "db_table": "work_orders",
                "indexes": [
                    models.Index(fields=["tenant", "connection"], name="ix_work_orders_conn"),
                    models.Index(fields=["tenant", "state"], name="ix_work_orders_tenant_state"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("order_no__isnull", False)),
                        fields=("tenant", "order_no"),
                        name="uq_work_orders_tenant_no",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ConnectionService",
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
                ("state", models.TextField(default="pending")),
                ("gate_order_id", models.UUIDField(blank=True, null=True)),
                ("energised_at", models.DateTimeField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="services",
                        to="metering.connection",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        db_column="unit_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.unit",
                    ),
                ),
            ],
            options={
                "db_table": "connection_services",
                "indexes": [
                    models.Index(
                        fields=["tenant", "connection"], name="ix_connection_services_conn"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("unit__isnull", False)),
                        fields=("tenant", "connection", "unit", "service"),
                        name="uq_connection_services_unit",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("unit__isnull", True)),
                        fields=("tenant", "connection", "service"),
                        name="uq_connection_services_premise",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ServiceCharacteristic",
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
                ("key", models.TextField()),
                ("value", models.TextField()),
                # HARD RULE 3, AS A COLUMN. NOT NULL, and never a suffix on the
                # key name: container count, impervious square feet and a speed
                # tier are three different units, and `storm_impervious_sqft`
                # encodes one in an identifier nothing can validate or migrate
                # (BR-MET-108).
                ("unit_of_measure", models.TextField()),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "service",
                    models.ForeignKey(
                        db_column="service_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                    "unit",
                    models.ForeignKey(
                        db_column="unit_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.unit",
                    ),
                ),
            ],
            options={
                "db_table": "service_characteristics",
                "indexes": [
                    models.Index(
                        fields=["tenant", "unit", "service"],
                        name="ix_service_char_unit_service",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "unit", "service", "key"),
                        name="uq_service_characteristics_key",
                    )
                ],
            },
        ),
        PostgresOnlySQL(sql=POLICIES, reverse_sql=migrations.RunSQL.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W6 task 6.1 (B18 §5.4.6 + §6.3 + BR-MET-104/108 snapshot
#         2026-08-25)
# generated: 2026-08-25 by the CR-030 W6 lane S1 (schema + policy half)
# checklist: A✔ B=deferred(schema half — the behaviour TCs assert through
#         apps/metering/connections.py) C✔ D=deferred(no-API-half — migration)
#         E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING; the ledger row is REPORTED because
#         12-governance/09-human-review-ledger.md is not this lane's file)
# gates: see the lane report
# exceptions: three columns beyond B18 §5.4.6's set, each taken from the PO's
#         2026-08-25 screens and each named in the model docstring —
#         `connections.waiting_on`, `work_orders.is_gate`,
#         `work_orders.template_id` · `WorkOrderTemplate` is created BEFORE
#         `WorkOrder` in the operations list because the new `template_id` FK
#         points at it · schema and policy in ONE migration rather than the usual pair —
#         DEF-639's cast is fixed, so the split no longer buys anything and the
#         one-file form closes the rule-1 window the pair documented · policy SQL
#         inline rather than in 06-backend/db/ (seventh file to flag the same
#         relocation — REPORTED, not resolved here) · two NEW cross-module FKs
#         (→ customers.service_requests, → assets.assets) REPORTED for B2 §2
#         interface review
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
