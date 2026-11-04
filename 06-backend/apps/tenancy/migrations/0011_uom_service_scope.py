# ── Trace ──────────────────────────────────────────────
# Change:   CR-004 task A3 — the optional Utility-service column, switched ON
#           for units of measure ONLY.   Defect: DEF-184
#           Screens: S8 / r10 SET-03 (the primary/alt UoM pickers) · SET-04
# Rules:    BR-TEN-026 (a service must be ENABLED for the tenant) · BR-TEN-036
#           (seeded defaults, tenant may extend) · BR-TEN-029 (deactivated
#           entries leave the picker) · CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""tenancy 0011 — `uoms.service_id`, nullable; NULL = "All services".

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-16 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"), implementing the PO ruling of 2026-08-16:
*"it's a real field - every entry can be scoped to one service or all - I added
it in Unit of measure since unit of measure is for speific service; so when we
select service we have specific unit of measure available; currently it is not
as per utility service."*

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW IS NEEDED, AND HERE IS WHY THAT IS TRUE RATHER THAN HOPED
────────────────────────────────────────────────────────────────────────────
**NO TABLE IS CREATED — this migration adds ONE COLUMN**, so there is no new
policy to write and writing one would shadow the signed original. `uoms` is
already ENABLE + FORCE under `uoms_tenant_isolation`, applied verbatim from
`06-backend/db/rls_tenancy_w0.sql` by `0003_rls_w0_policies`; that policy gates
the ROW, so a column added to a gated row is gated. Same posture, same words,
as `0006_service_gl_attributes` — which added two columns to `tenant_services`
and needed no policy for the same reason.

The FK's TARGET carries no policy either, and that is deliberate rather than an
omission: `services` is the closed 10-service PLATFORM catalog (BR-RAT-024),
RLS-EXEMPT per B2 §3 and read by every tenant. Nothing tenant-identifying
crosses the edge — the column holds catalog vocabulary, and which tenant may
SCOPE a unit to which service is enforced in validation (BR-TEN-026: the
service must be one this tenant has ENABLED), never by the FK.

The claim is backed by a sweep, not by this paragraph:
`tests/test_tenant_isolation.py` walks every tenant-scoped table rather than a
hand-kept list, so a table reaching the schema without a policy fails it.
Postgres only — the sqlite test DB cannot exercise RLS, and says so.

────────────────────────────────────────────────────────────────────────────
ORDERING (🔒) AND BACKFILL
────────────────────────────────────────────────────────────────────────────
Depends on tenancy/0010 only. `services` is created and seeded by tenancy/0001,
so the FK target exists ten migrations before this one — no cross-app edge is
added and no ordering hazard is introduced.

**NOTHING IS BACKFILLED, ON PURPOSE.** Every existing `uoms` row lands with
`service_id = NULL`, which reads as "All services" — the behaviour those rows
have today, exactly. Scoping the units of a tenant that has already been
running would silently REMOVE options from a picker their staff have been using
and could orphan a stored `tenant_services.primary_uom`. The seed states the
scope for units created FROM NOW (`apps.tenancy.services._seed_uoms`, reading
`SERVICE_DEFAULT_UOMS`); a live tenant re-scopes its own list from SET-04, one
entry at a time, and sees what changed. This is a default, never a backfill —
the same rule `SERVICE_DEFAULT_UOMS` already states for itself.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0010_area_certificationtype_devicetype_importmapping_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="uom",
            name="service",
            field=models.ForeignKey(
                blank=True,
                db_column="service_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="uoms",
                to="tenancy.service",
            ),
        ),
    ]
