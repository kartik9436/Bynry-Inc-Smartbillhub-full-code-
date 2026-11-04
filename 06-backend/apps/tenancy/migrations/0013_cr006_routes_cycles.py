# ── Trace ──────────────────────────────────────────────
# Story:    CR-006 (SET-05/06/07 Routes & Cycles)  Screens: S8 → Reference data (areas) · S8 → Routes & Cycles
# Rules:    BR-MET-066b (areas gain a nullable self-reference; a row with no
#           parent is an area, a row with a parent is a sub-area) — SUPERSEDES
#           BR-MET-066's "a parent_id added here would be an invented model"
# ───────────────────────────────────────────────────────
"""tenancy 0013 — `areas.parent_id`, the sub-area hierarchy CR-004 declined to invent.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-17 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md.

WHY A COLUMN A SIGNED RULE FORBIDS IS BEING ADDED
--------------------------------------------------
BR-MET-066 reads *"NO parent/child column, and the shape is UNSPECIFIED rather
than missing… A `parent_id` added here would be an invented model."* That was
correct on 2026-08-16: r10's card said *"3 sub-areas"* and nothing anywhere
defined depth, whether a sub-area may hold premises, or what a route's
relationship to one is. CR-004 declined to guess.

The PO then specified it, the same day: *"user can define their own areas and we
wil tag them to premises ; in CR06 you can use area and sub area for filtering -
all option 1 to many options will be required"*. So the rule is SUPERSEDED by
BR-MET-066b with its date, not edited, and this migration implements the
specification rather than filling a gap on its own authority.

NULLABLE AND NO BACKFILL. The four seeded areas stay top-level, and NO sub-area
is seeded — r10's own list data contains none, and minting "SE"/"SW" to match
one screenshot's fixture would be seeding a tenant's vocabulary for it.

Depth is capped at TWO in `apps/tenancy/services.py`, not here: SQL cannot say
"a parent must itself have no parent" without a trigger, and a trigger would be
a second place the rule lives (hard-won law 1's shape — two statements of one
guarantee, one of which will drift).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0012_number_series_restart"),
    ]

    operations = [
        migrations.AddField(
            model_name="area",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                db_column="parent_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sub_areas",
                to="tenancy.area",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-009@a76398d (the reference-data story this extends; the CHANGE is CR-006 — 12-governance/11-change-requests.md, PO 2026-08-16, ruling 5)
# generated: 2026-08-17 by the CR-006 lane
# checklist: A✔ B✔ C✔(tests/test_cr006_routes_cycles.py::test_sub_area_may_not_itself_be_a_parent) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · tenancy + metering suites
# exceptions: this adds a column BR-MET-066 says must not exist — superseded by BR-MET-066b with its date and the PO's verbatim words; see the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
