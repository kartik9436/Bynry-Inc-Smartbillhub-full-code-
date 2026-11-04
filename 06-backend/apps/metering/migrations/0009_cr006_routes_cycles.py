# ── Trace ──────────────────────────────────────────────
# Story:    CR-006 (SET-05/06/07 Routes & Cycles)  Screens: S8 → Routes & Cycles
# Rules:    BR-MET-071 (premises.area_id — the link the CR-004 areas list shipped
#           without) · BR-MET-073 (a route carries service, area, notes) ·
#           BR-MET-074 (membership is unique PER SERVICE — two partial
#           constraints, because SQL NULLs are distinct) · BR-MET-075
#           (route_meter_exclusions: an exclusion is a row, never a change to the
#           asset) · BR-MET-076 (draft status) · BR-MET-077 (day-of-month
#           DEFAULTS, not dates) · BR-MET-078 (NO money column) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""metering 0009 — the CR-006 shapes: areas on premises, service/area/notes on a
route, day-of-month defaults on a cycle, per-service membership, meter exclusions.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-17 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

THE ONE OPERATION IN HERE THAT COULD LOSE DATA, AND WHY IT CANNOT
------------------------------------------------------------------
`uq_route_memberships_unit` (tenant, unit) is REMOVED and replaced by two
partial constraints (BR-MET-074). A dropped unique is normally the dangerous
direction — but both replacements are strictly WEAKER over the existing rows,
never stronger: every membership row today has `service_id = NULL`, so every
one of them falls under `uq_route_memberships_unit_no_service`, which is the
old constraint over exactly the same column pair. **No existing row can fail
the new constraints, so the migration cannot refuse and cannot silently drop
a duplicate.** What changes is only what becomes newly LEGAL: the same unit on
a water route and an electric route.

EVERY COLUMN IS NULLABLE AND THAT IS DELIBERATE, NOT LAZY. Existing premises
have no area, existing routes no service, existing cycles no day-of-month
defaults. A NOT NULL with a backfilled default would be this migration
INVENTING a value — an area for a premises nobody has surveyed, a service for
a route that reads three of them. Nullable says "not yet answered", which is
the true statement.

NOTHING HERE IS MONEY (BR-MET-078). r10 SET-07.3 draws a *Late / penalty date*;
the PO removed it — *"dont have anything related to money when you create route
and cycles"* — so there is no `late_day`, no rate, no amount and no currency
column anywhere below, and this migration needs no finance re-sign.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0006_br_ten_057_is_sample"),
        ("metering", "0008_br_ten_057_is_sample"),
        ("tenancy", "0013_cr006_routes_cycles"),
    ]

    operations = [
        migrations.CreateModel(
            name="RouteMeterExclusion",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "route_meter_exclusions",
            },
        ),
        migrations.RemoveConstraint(
            model_name="routemembership",
            name="uq_route_memberships_unit",
        ),
        migrations.AddField(
            model_name="cycle",
            name="bill_day",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="due_day",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="first_run_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="frequency",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="name",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="read_day_from",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="read_day_to",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="status",
            field=models.TextField(default="active"),
        ),
        migrations.AddField(
            model_name="premises",
            name="area",
            field=models.ForeignKey(
                blank=True,
                db_column="area_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.area",
            ),
        ),
        migrations.AddField(
            model_name="route",
            name="area",
            field=models.ForeignKey(
                blank=True,
                db_column="area_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.area",
            ),
        ),
        migrations.AddField(
            model_name="route",
            name="notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="route",
            name="service",
            field=models.ForeignKey(
                blank=True,
                db_column="service_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.service",
            ),
        ),
        migrations.AddField(
            model_name="routemembership",
            name="service",
            field=models.ForeignKey(
                blank=True,
                db_column="service_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.service",
            ),
        ),
        migrations.AddConstraint(
            model_name="routemembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("service__isnull", False)),
                fields=("tenant", "unit", "service"),
                name="uq_route_memberships_unit_service",
            ),
        ),
        migrations.AddConstraint(
            model_name="routemembership",
            constraint=models.UniqueConstraint(
                condition=models.Q(("service__isnull", True)),
                fields=("tenant", "unit"),
                name="uq_route_memberships_unit_no_service",
            ),
        ),
        migrations.AddField(
            model_name="routemeterexclusion",
            name="asset",
            field=models.ForeignKey(
                db_column="asset_id", on_delete=django.db.models.deletion.PROTECT, to="assets.asset"
            ),
        ),
        migrations.AddField(
            model_name="routemeterexclusion",
            name="route",
            field=models.ForeignKey(
                db_column="route_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="metering.route",
            ),
        ),
        migrations.AddField(
            model_name="routemeterexclusion",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddConstraint(
            model_name="routemeterexclusion",
            constraint=models.UniqueConstraint(
                fields=("tenant", "route", "asset"), name="uq_route_meter_exclusions"
            ),
        ),
        # CLAUDE.md rule 1 / NFR-10: the new tenant table gets ENABLE + FORCE
        # RLS in the SAME migration that creates it. A table that exists for
        # even one deploy without a policy is a G5 isolation failure.
        PostgresOnlySQL(
            sql=load_db_sql("rls_metering_cr006_route_meter_exclusions.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-006@a76398d (the story this extends; the CHANGE is CR-006 — 12-governance/11-change-requests.md, PO 2026-08-16, SET-05/06/07)
# generated: 2026-08-17 by the CR-006 lane
# checklist: A✔ B✔ C✔(tests/test_cr006_routes_cycles.py) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · metering + tenancy suites green
# exceptions: `uq_route_memberships_unit` is dropped — see the docstring for why the replacement cannot refuse or drop a row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
