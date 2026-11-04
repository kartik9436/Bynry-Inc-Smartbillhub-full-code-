"""metering 0061 — a route stores the PREMISES a human picked, not their units
(`CR-131-BRC07` step 3, 2026-09-22).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE TABLE, TWO CONSTRAINTS, ONE RLS POLICY AND A BACKFILL THAT NAMES WHAT IT
DERIVED.

──────────────────────────────────────────────────────────────────────────────
WHAT THE PO RULED
──────────────────────────────────────────────────────────────────────────────
**PO ruling 2026-09-22, verbatim:** *"thi sis correct - The routes design —
storing 726 unit rows instead of 6 premises, and the route going stale the
moment anything changes. and route should not be status - it is
dynamicallyderive the details of units, assets meter acocount swithin it"*.

`route_memberships` stores one row per UNIT. Six premises carrying 726 units
became 726 rows, written by 726 `update_or_create` statements inside one
transaction holding the route row locked — which is the *"Working…"* for ever
the PO reported. `route_premises_memberships` stores **six**.

──────────────────────────────────────────────────────────────────────────────
THE BACKFILL IS A DERIVATION AND IS MARKED AS ONE
──────────────────────────────────────────────────────────────────────────────
Every existing route's premises set is computed as **the distinct premises of
the units it already holds**, which is exactly the set the wizard sent before
`_set_route_membership` fanned it out. That is a derived value and not an
observed fact, so it is stated here rather than left to be inferred.

⚠ **IT IS NOT LOSSLESS IN ONE DIRECTION, AND THAT IS THE POINT RATHER THAN A
DEFECT.** A route holding SOME of a building's units — which the old grain
could express and the new one cannot — comes back holding ALL of them. That is
`BR-MET-082` clause 2, *"grouping a premises groups every unit in it"*, which
the derivation has enforced since `CR-029` RC-W4: a sibling's live pick already
reached every unit in the building, so the RESOLVED membership does not move.
It is the STORED rows that stop pretending otherwise.

⚠ **AND IT IS MEASURED RATHER THAN ASSUMED.** The backfill prints the two
counts it wrote — unit rows read, premises rows written — so a deployment that
collapses 726 into 6 says so in its own output instead of being trusted to.

──────────────────────────────────────────────────────────────────────────────
WHY `route_memberships` IS STILL HERE
──────────────────────────────────────────────────────────────────────────────
A table is retired after its readers move, never in the migration that
supersedes it. `CR-131-BRC07` step 8 owns that, and until it lands the old rows
are written alongside the new ones by the one writer that owns both.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "route_premises_memberships"
#: The same expression every other policy in this module uses — NULLIF so an
#: unset `app.tenant_id` is NULL and matches nothing, rather than raising.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE_POLICY = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


def carry_the_picks_across(apps, schema_editor):  # type: ignore[no-untyped-def]
    """Every route's premises set, derived from the units it already holds.

    ⚠ **IT SETS `app.tenant_id` PER TENANT, AND THE FIRST DRAFT DID NOT — WHICH
    WROTE ZERO ROWS AND SAID SO.** The comment here read *"a migration runs with
    RLS off"*. It does not. `route_memberships` carries `FORCE ROW LEVEL
    SECURITY` and the migration role is neither superuser nor `BYPASSRLS`, so
    with `app.tenant_id` unset the policy resolves to `tenant_id = NULL`, every
    read matches nothing, and the backfill completes successfully having seen
    no data at all. **Nothing would have gone red** — the table would simply
    have been empty and every route would have lost its membership the moment
    the readers moved onto it.

    That is CLAUDE.md hard-won law 7's *reporting zero over a scope it silently
    excludes*, and the only reason it was caught is the print at the bottom,
    which law 7 habit 3 asks for: **a check's output must distinguish a pass
    from a fail to a READER.** `0 unit rows -> 0 premises rows` on a fixture
    known to hold nine memberships is a sentence somebody can be wrong about
    out loud. "Applying … OK" is not.

    So each tenant is scoped EXPLICITLY, one at a time, which is also CLAUDE.md
    rule 1 read the way `metering/0012` reads it: *"a backfill is one of the few
    places that runs outside a request's `app.tenant_id`, so the scoping is
    written into the SQL rather than relied upon."*
    """
    from django.db import connection

    if schema_editor.connection.vendor != "postgresql":
        # sqlite has no RLS and no `current_setting`; the suite's database is
        # built by migrating from empty, so there is nothing to carry across.
        # Said out loud rather than skipped silently (hard-won law 7).
        print("  route_premises_memberships: sqlite — no rows to carry across")
        return

    tenant_model = apps.get_model("tenancy", "Tenant")
    membership = apps.get_model("metering", "RouteMembership")
    premises_membership = apps.get_model("metering", "RoutePremisesMembership")

    tenant_ids = list(tenant_model.objects.values_list("id", flat=True).order_by("id"))
    read = written = 0
    for tenant_id in tenant_ids:
        with connection.cursor() as cursor:
            # LOCAL: it lasts for this migration's transaction and no longer,
            # so the setting cannot leak into whatever runs next.
            cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        seen: set[tuple[str, str]] = set()
        rows = []
        for route_id, premises_id, service_id in membership.objects.filter(
            tenant_id=tenant_id
        ).values_list("route_id", "unit__premises_id", "service_id").order_by(
            "route_id", "unit__premises_id"
        ):
            read += 1
            key = (str(route_id), str(premises_id))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                premises_membership(
                    tenant_id=tenant_id,
                    route_id=route_id,
                    premises_id=premises_id,
                    service_id=service_id,
                )
            )
        premises_membership.objects.bulk_create(rows, batch_size=500)
        written += len(rows)
    # Hard-won law 7 habit 3: output a reader can tell a pass from a fail by.
    # ⚠ **THE TENANT COUNT IS PART OF THE RESULT AND NOT DECORATION** — it is
    # what distinguishes "there was nothing to carry" from "I could not see
    # anything", which is the exact pair the first draft got wrong.
    print(
        f"  route_premises_memberships: {len(tenant_ids)} tenant(s) scoped, "
        f"{read} unit rows -> {written} premises rows "
        f"({read - written} were the same building read twice)"
    )


def drop_the_picks(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The reverse deletes only what the forward wrote — every row, because the
    table did not exist before it. `route_memberships` is untouched by both
    directions, which is what makes this migration reversible at all.

    ⚠ **TENANT-SCOPED FOR THE SAME REASON THE FORWARD IS**, and it matters more
    here: an unscoped `.delete()` under FORCE RLS deletes NOTHING and reports
    success, so a rollback would leave every row standing behind a table the
    code no longer writes."""
    from django.db import connection

    premises_membership = apps.get_model("metering", "RoutePremisesMembership")
    if schema_editor.connection.vendor != "postgresql":
        premises_membership.objects.all().delete()
        return
    for tenant_id in apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.tenant_id = %s", [str(tenant_id)])
        premises_membership.objects.filter(tenant_id=tenant_id).delete()


class Migration(migrations.Migration):

    # ⚠ **NUMBERED 0061 AND DEPENDING ON 0060, WHICH IS A SIBLING'S
    # (`DEF-2872`'s shape, caught at push time on 2026-09-22).** This was
    # written as `0060_cr131_premises_membership` against a tip that had no
    # 0060. A sibling pushed `0060_br_met_1181_premises_master_account` while
    # this lane worked, and two 0060s is not a warning — Django refuses EVERY
    # command in the process with *"Conflicting migrations detected; multiple
    # leaf nodes in the migration graph"*, which names neither lane and looks
    # for all the world like a broken tree.
    #
    # A migration number is a shared register like any other, and
    # `10-scripts/allocate.py` does not allocate this family — so the only
    # thing that catches it is re-deriving from the tip at push time and
    # RUNNING `migrate`. Reading the directory is not enough: the sibling's
    # file was absent from this worktree until the push helper restored it.
    dependencies = [
        ("metering", "0060_br_met_1181_premises_master_account"),
        ("tenancy", "0046_cr122_brc06_move_in_draft"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoutePremisesMembership",
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
            ],
            options={
                "db_table": "route_premises_memberships",
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("service__isnull", False)),
                        fields=("tenant", "premises", "service"),
                        name="uq_route_premises_members_service",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("service__isnull", True)),
                        fields=("tenant", "premises"),
                        name="uq_route_premises_members_no_service",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE_POLICY),
        migrations.RunPython(carry_the_picks_across, drop_the_picks),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-131-BRC07 step 3 + the PO ruling of 2026-09-22 ("A ROUTE IS NOT A
#         SNAPSHOT") + BR-MET-074 + BR-MET-082 clause 2 + CLAUDE.md hard rule 1
# generated: 2026-09-22 by lane R2 of CR-131-BRC07
# checklist: A✔ B✔ C✔ D=deferred(no new route in this migration) E=deferred(no
#            frontend half in this migration) F✔ G✔ H=deferred(PO 2026-08-09 —
#            🔒 HUMAN-REVIEW-PENDING, ledger row owed by the lane report)
