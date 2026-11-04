# ── Trace ──────────────────────────────────────────────
# Story:    DEF-233 (the reads-history delete guard is bypassed by moving the
#           premises away first) · CR-006 SET-05   Screens: SET-05
# Rules:    BR-MET-079 (a route with reads history cannot be DELETED, only
#           deactivated — CR-006 verbatim: "deleting is not allowed once a
#           route has reads history") · BR-MET-008 (the membership lock this
#           sits one layer under) · BR-MET-033 (membership drives route_id on
#           the service point — the mutable link that caused this) ·
#           CLAUDE.md rule 1 (tenant scoping) · hard-won law 1
# ───────────────────────────────────────────────────────
"""metering 0012 — `meter_reads.route_id`, the collection-time route stamp.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-18 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

⚠ THIS IS THE SECOND AUTHORING OF THIS MIGRATION, AND THE FIRST ONE IS WHY THE
NUMBER IS 0012 AND NOT 0010
----------------------------------------------------------------------------
A lane authored `0010_def233_read_route_stamp` on 2026-08-17 in the shared
working tree and its session ended before it committed. The container was
reclaimed and the file went with it — it exists in no commit on any branch. The
unit-types lane had already YIELDED the number 0010 to it and committed a
dependency on it, so trunk shipped an edge to a node nobody ever published and
Django raised NodeNotFoundError at graph load: migrate, makemigrations and every
DB-touching test failed before running. That edge was repointed to 0009
(DEF-241) and this migration takes the next free number. 0010 never existed.

WHAT WAS ACTUALLY BROKEN
------------------------
`route_read_history_count` counted a route's reads two ways and a membership
edit defeated both:

  · the SERVICE POINTS currently stamped with the route — and moving a
    membership UNSTAMPS them, so a route emptied of members reported ZERO;
  · `read_import_batches.route_id`, which the services docstring called "the
    durable link ... which no membership edit clears". On the shipped fixture
    every one of the 135 `meter_reads` rows has `import_batch_id` NULL and
    `read_import_batches` holds ZERO rows, so that half could never fire.

Measured consequence, from the CR-006 walkthrough's SECOND run: the seeded
Route 1 refused deletion an hour earlier naming 135 reads, and was then DELETED
after its premises were moved to another route. Run 1 could not see it — before
DEF-217 was fixed, putting a read premises on a route answered HTTP 500, so the
bypass path did not exist to be walked.

THE FIX, AND WHY IT IS A COLUMN RATHER THAN A CLEVERER QUERY
------------------------------------------------------------
Every link that could be queried instead is one a later edit can clear; that is
the defect, not an implementation detail. So the read carries the route it was
collected on, written once and never rewritten. Nothing in a membership edit
reaches it.

THE BACKFILL IS EVIDENCE-AT-MIGRATION-TIME, AND SAYS SO
--------------------------------------------------------
Existing rows are stamped from the best source available NOW, in three passes,
most-authoritative first: the read's own import batch where one exists, then the
asset's service point, then the asset's unit. The unit hop picks
deterministically (`ORDER BY sp.id LIMIT 1`) because a unit may carry one
service point per service and an arbitrary pick would make the backfill
unrepeatable.

⚠ **PASS 3 WENT THROUGH `assets.unit_id` IN THE FIRST CUT OF THIS FILE AND
THERE IS NO SUCH COLUMN — corrected 2026-08-18, and the correction is kept
because it is the best argument in this repo for the PO's closure bar.** The
same lane had just filed DEF-243 for precisely this — `assets.unit` is the
explicit-UoM TEXT column and an asset reaches a unit through
`asset_assignments` — fixed the Python half correctly, and then wrote the SQL
half with the bug still in it. Every static check passed: the file parsed, the
migration graph loaded, the Django test suite went 1025/0 on **sqlite**, where
`PostgresOnlySQL` does not execute. It failed the instant it met a real
Postgres, with `ProgrammingError: column a.unit_id does not exist`. Knowing the
fact was not enough; only running it was.

**Every pass is tenant-scoped in its own join predicate.** A backfill is one of
the few places that runs outside a request's `app.tenant_id`, so the scoping is
written into the SQL rather than relied upon (CLAUDE.md rule 1).

A row the backfill cannot resolve stays NULL, and NULL never means "no route
history" — `route_read_history_count` UNIONS this stamp with the two older
sources rather than replacing them, so this migration can only ever make the
guard fire MORE often. That direction is deliberate: an under-counted history
deletes a route that has one, and an over-counted history refuses a delete that
a deactivate can still serve.

REVERSIBLE. Dropping the column loses the stamp and returns the guard to its
two older sources — i.e. to the defect. Nothing else depends on it.
"""

from django.db import migrations, models
import django.db.models.deletion

from core.migrationtools import PostgresOnlySQL

#: Three passes, most authoritative first, each one tenant-scoped in its own
#: predicate and each one refusing to overwrite a stamp an earlier pass set.
BACKFILL_SQL = """
UPDATE meter_reads mr
   SET route_id = b.route_id
  FROM read_import_batches b
 WHERE mr.import_batch_id = b.id
   AND b.tenant_id = mr.tenant_id
   AND mr.route_id IS NULL
   AND b.route_id IS NOT NULL;

UPDATE meter_reads mr
   SET route_id = sp.route_id
  FROM assets a
  JOIN service_points sp
    ON sp.id = a.service_point_id
   AND sp.tenant_id = a.tenant_id
 WHERE mr.asset_id = a.id
   AND a.tenant_id = mr.tenant_id
   AND mr.route_id IS NULL
   AND sp.route_id IS NOT NULL;

UPDATE meter_reads mr
   SET route_id = pick.route_id
  FROM assets a
  JOIN LATERAL (
        SELECT sp.route_id
          FROM asset_assignments aa
          JOIN service_points sp
            ON sp.unit_id = aa.unit_id
           AND sp.tenant_id = aa.tenant_id
         WHERE aa.asset_id = a.id
           AND aa.tenant_id = a.tenant_id
           AND sp.route_id IS NOT NULL
         ORDER BY sp.id
         LIMIT 1
       ) pick ON TRUE
 WHERE mr.asset_id = a.id
   AND a.tenant_id = mr.tenant_id
   AND mr.route_id IS NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0011_cr010_unit_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="meterread",
            name="route",
            field=models.ForeignKey(
                blank=True,
                db_column="route_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reads_collected",
                to="metering.route",
            ),
        ),
        PostgresOnlySQL(BACKFILL_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-233@CR-006 (BR-MET-079 — the reads-history delete guard)
# generated: 2026-08-18 by the Phase-0 recovery lane (re-authoring the lost 0010)
# checklist: A✔ B✔ C=deferred(schema only — the behaviour tests are on the guard, tests/test_def233_route_read_stamp.py) D=deferred(no-API-half — a column has no endpoint) E=deferred(no-frontend-half — SET-05's delete refusal is the surface) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: migration graph AST-parsed clean (DEF-241's check); makemigrations --check owed on a booted stack — Django is not installed in the recovery container and this is REPORTED, not claimed
# exceptions: the backfill writes across tenants by design (it is a migration), so every pass carries its own tenant_id predicate rather than relying on app.tenant_id
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
