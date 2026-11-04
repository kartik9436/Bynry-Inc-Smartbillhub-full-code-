# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W1 task W1-T4 (B17 §6/§7) — the route side of the ruled
#           model: D10's service SET, the exclusion's two-word reason, D11's
#           per-premises walk order, D1's first-class closable read windows.
# Rules:    D10 — *"yes it will be multi service"* · D11 — *"Per premises"* ·
#           D1 — *"yes"* · BR-MET-073/074/075 (the CR-006 shapes this extends) ·
#           BR-MET-078 (NO money on these surfaces) · CLAUDE.md rule 1
#           (tenant scoping / RLS on every new tenant table) · CLAUDE.md 🔒
#           sensitive paths (migration ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
"""metering 0020 — CR-029: the route-side schema the four rulings require.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). ⚠ Its row in `12-governance/09-human-review-ledger.md` is
OWED: the RC-W1 lane does not write governance files and has REPORTED the row
for the CR-029 close-out to add.

⚠ **THE CHOICE THIS MIGRATION WAS ASKED TO MAKE AND STATE (D10).** The build
instruction offered two ways to give a route a service SET: keep the existing
single-service column readable through the transition, **or** migrate its data
into the set and stop reading it.

**BOTH — the column is KEPT and its data is ALSO copied into `route_services`.**
The reason is a constraint, not a preference: `route_memberships.service_id` is
DENORMALIZED from `routes.service_id` and BR-MET-074's two partial unique
constraints (`uq_route_memberships_unit_service` and
`uq_route_memberships_unit_no_service`) are the only thing stopping one unit
joining two routes for one service. Retiring the head column in this migration
would either drop those guarantees or require membership to be re-modelled here
— and re-modelling membership is **RC-W4**, whose whole subject is D4's
run-time resolution. So:

  * `route_services` is the new truth for **what a route reads** (SET-05's
    "Service(s)" column, SET-06D's Facts rail, SET-06.1's service picker);
  * `routes.service_id` remains the transitional **head** — written to the
    set's first member, read by membership, and removed once RC-W4 has moved
    membership off it and RC-W5 sweeps.

⚠ **AND THE HOLE THAT LEAVES, STATED RATHER THAN HIDDEN (hard-won law 1).**
While the head is one service, a "Water + Electric" route enforces per-service
membership uniqueness for WATER only. No constraint available in this migration
closes that; D4's derived membership does. REPORTED by the lane, not papered
over and not fixed by inventing a rule nobody ruled.

BACKFILL, IN ONE PASS. Every route with a `service_id` gets the matching
`route_services` row, so a route that reads water today reads water tomorrow and
the set is never emptier than the column it replaces. Routes with NULL service —
the legacy ALL-SERVICES routes — get NO row, because an empty set is the true
statement and a set containing every enabled service would be this migration
deciding what an untagged route reads.

NOTHING IS DROPPED. `route_memberships.walk_order` (superseded by D11 and, per
B17 §5 gap G5, never once written) and `routes.service_id` both stay. RC-W5
drops what is then unread — the same discipline metering 0019 applies to the
cycle's legacy calendar columns.

NOTHING HERE IS MONEY (BR-MET-078, which this CR HARDENS). No amount, no rate,
no currency, no late day, on any of the three new tables — so no ❄️ FROZEN
B4/B5 figure is touched and no finance re-sign is triggered.

RLS: ALL THREE NEW TENANT TABLES ARE POLICED IN THIS MIGRATION
(`db/rls_metering_cr029_routes.sql`). A tenant table that exists for even one
deploy without a policy is a G5 isolation failure and a release blocker
(NFR-10, zero tolerance). `route_meter_exclusions.reason` needs no new policy —
that table has been policed since CR-006 and the policy is ROW-scoped.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


def copy_service_into_the_set(apps, schema_editor):
    """D10's backfill — every route's single service becomes its first set member.

    ⚠ NO TENANT FILTER, DELIBERATELY, for migration 0019's reason: a migration
    runs as the schema owner across every tenant's rows, and scoping it to one
    would leave every other tenant's routes with an empty set while their
    `service_id` still said water. No per-tenant decision is taken — the copy is
    the same operation for every row.
    """
    Route = apps.get_model("metering", "Route")
    RouteService = apps.get_model("metering", "RouteService")
    for route in Route.objects.exclude(service_id=None).iterator():
        RouteService.objects.get_or_create(
            tenant_id=route.tenant_id, route_id=route.id, service_id=route.service_id
        )


def empty_the_set(apps, schema_editor):
    apps.get_model("metering", "RouteService").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_rls_security_policies"),
        ("metering", "0019_cr029_cycle_schedule"),
        ("tenancy", "0017_br_ast_048_mapping_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="routemeterexclusion",
            name="reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ReadWindow",
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
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("read_on", models.DateField(blank=True, null=True)),
                ("collected_count", models.IntegerField(blank=True, null=True)),
                ("expected_count", models.IntegerField(blank=True, null=True)),
                ("skip_count", models.IntegerField(blank=True, null=True)),
                ("result", models.TextField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                    "reader",
                    models.ForeignKey(
                        blank=True,
                        db_column="reader_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "route",
                    models.ForeignKey(
                        db_column="route_id",
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
            ],
            options={
                "db_table": "read_windows",
                "indexes": [
                    models.Index(
                        fields=["tenant", "route", "period_start"], name="ix_read_windows_route"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "route", "period_start"),
                        name="uq_read_windows_route_period",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("result__isnull", True),
                            ("result__in", ("Complete", "Incomplete")),
                            _connector="OR",
                        ),
                        name="ck_read_windows_result",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RoutePremisesOrder",
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
                ("walk_order", models.IntegerField()),
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
                    "route",
                    models.ForeignKey(
                        db_column="route_id",
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
            ],
            options={
                "db_table": "route_premises_orders",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "route", "premises"), name="uq_route_premises_orders_stop"
                    ),
                    models.UniqueConstraint(
                        fields=("route", "walk_order"), name="uq_route_premises_orders_walk_order"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RouteService",
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
                (
                    "route",
                    models.ForeignKey(
                        db_column="route_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.route",
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
            ],
            options={
                "db_table": "route_services",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "route", "service"), name="uq_route_services"
                    )
                ],
            },
        ),
        # D10's backfill — see `copy_service_into_the_set` and the docstring's
        # statement of the choice this migration was asked to make.
        migrations.RunPython(copy_service_into_the_set, empty_the_set),
        # CLAUDE.md rule 1 / NFR-10: the THREE new tenant tables get ENABLE +
        # FORCE RLS in the SAME migration that creates them.
        PostgresOnlySQL(
            sql=load_db_sql("rls_metering_cr029_routes.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §6/§7 RC-W1 T4 + the CR-029 record in 12-governance/11-change-requests.md (D10 · D11 · D1)
# generated: 2026-08-23 by the CR-029 RC-W1 lane
# checklist: A✔ B=deferred(RC-W3-T3/T4 own SET-06D/SET-07D) C✔(tests/test_cr029_rcw1_route_model.py) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · metering suite green
# exceptions: (1) `routes.service_id` is KEPT as the transitional head as well as copied into the set — the choice is argued in the docstring, and the membership-uniqueness hole it leaves is REPORTED for RC-W4's D4 rather than closed by an invented rule · (2) the RunPython walks every tenant's rows with no `app.tenant_id`, the same posture as metering 0019 · (3) NO WRITER lands for `read_windows` or `route_premises_orders` in this wave — RC-W2-T1 closes windows, RC-W3-T3 writes the walk order; the ruled split, stated so it is not read as an omission
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
