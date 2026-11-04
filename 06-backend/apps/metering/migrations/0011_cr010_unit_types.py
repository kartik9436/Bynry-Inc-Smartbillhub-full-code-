# ── Trace ──────────────────────────────────────────────
# Story:    CR-010 A-section item 4 (PO 2026-08-17: "this is correct" on
#           "Premise & unit types (one card, two levels)")   Screens: S8 · S16
# Rules:    BR-MET-084 (unit types are a seeded, tenant-extensible reference
#           list) · BR-TEN-030/034/036 (lookup-list laws) · CLAUDE.md rule 1
#           (RLS ENABLE+FORCE in the SAME migration that creates the table)
# ───────────────────────────────────────────────────────
"""metering 0011 — the CR-010 `unit_types` table, with its RLS policy.

HUMAN-OWNED (migration ordering + an RLS policy — 🔒 twice). HUMAN-REVIEW-
PENDING — AI-authored 2026-08-18 under the PO ruling of 2026-08-09 ("AI will
do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md.

ONE new table, the exact shape `premises_types` has had since 0001 (tenant FK,
code unique per tenant case-insensitively, is_system/active, timestamps), plus
the B2 §3 policy applied in the SAME migration — a table that exists for even
one deploy without a policy is a G5 isolation failure (NFR-10).

NO column change on `units`: `unit_type` stays the TEXT code it has been since
0001, so nothing here can refuse, backfill or reinterpret an existing row.
What changes is where the ALLOWED set lives — the table this creates instead
of the UNIT_TYPES tuple — and services._validate_unit resolves against it with
the legacy tuple as fallback, so every value ever stored stays valid.

Seeding is deliberately NOT here (BR-TEN-012: seeding rides the tenant fixture
seeding lane, exactly as premises_types' docstring says of its own table).
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        # ⚠ REPOINTED 2026-08-18 (DEF-241). This read
        #     ("metering", "0010_def233_read_route_stamp")
        # and that migration DOES NOT EXIST — not on disk, not in any commit, on
        # any branch. The DEF-233 lane authored it in a shared working tree and
        # its session ended before it committed; the container was reclaimed and
        # the file went with it. This lane had already yielded the number 0010 to
        # it and committed the reference, so trunk shipped a dependency on a node
        # that was never published: Django raises NodeNotFoundError at GRAPH LOAD,
        # which fails migrate, makemigrations and every DB-touching test before a
        # single case runs.
        #
        # Repointing to 0009 is safe because this migration's operations are a
        # CreateModel for a NEW table plus its RLS policy — nothing here reads,
        # alters or orders against anything 0010 would have added. The graph stays
        # single-leaf; 0010 simply never existed.
        #
        # DEF-233 (the reads-history delete guard bypass) is STILL OPEN — its fix
        # was lost with the file and lands as 0012, not by restoring this edge.
        ("metering", "0009_cr006_routes_cycles"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UnitType",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "unit_types",
            },
        ),
        migrations.AddConstraint(
            model_name="unittype",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_unit_types_tenant_code_ci",
            ),
        ),
        # CLAUDE.md rule 1 / NFR-10: the new tenant table gets ENABLE + FORCE
        # RLS in the SAME migration that creates it.
        PostgresOnlySQL(
            sql=load_db_sql("rls_metering_unit_types.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-010 A-section item 4 (12-governance/02-decision-log.md 2026-08-17)
# generated: 2026-08-18 by the CR-010 account-subtypes/unit-types lane
# checklist: A✔ B✔ C✔(tests/test_cr010_subtypes_unit_types.py) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · migrate from empty proven
# exceptions: units.unit_type deliberately stays TEXT (see docstring) — the handler enforces BR-TEN-030/034 by live count because there is no FK PROTECT to lean on
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
