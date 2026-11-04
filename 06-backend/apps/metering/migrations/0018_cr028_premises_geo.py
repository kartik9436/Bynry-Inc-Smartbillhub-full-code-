# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W5 T3 (B16 §4.6/§6 · §10-D6 RULED 2026-08-22: premises
#           gain coordinates; a geocoder is ACCEPTED and the selection is
#           engineering's, recorded in apps/metering/geocode.py)
# Rules:    §10-D6 · BR-MET-071 (premises.area — the EXISTING area link this
#           migration deliberately does NOT duplicate) · CLAUDE.md rule 1
#           (tenant scoping / RLS) · CLAUDE.md 🔒 sensitive paths (migration
#           ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — row appended to 12-governance/09-human-review-ledger.md
# by the CR-028 AST-W5 close-out.
"""metering 0018 — CR-028 AST-W5: `premises.lat` / `premises.lng`.

WHY PREMISES. A meter is where its premises is (B16 §4.6: "premises-level
geocoding is the natural owner"); coordinates on the asset would go stale on
every reassign and be wrong for every device sharing an address.

NUMERIC(9,6), NULLABLE, NO DEFAULT. Six decimal places is ~0.11 m of
latitude — display cartography, far past marker precision — and 9,6 bounds
the integer part to ±999, which every real latitude/longitude fits. NULL
means "never geocoded", which is a REAL state the map must render honestly
(the asset simply has no marker); a 0,0 default would draw the fleet in the
Gulf of Guinea, so no default exists.

⚠ NO `area` COLUMN, DELIBERATELY — the packet drew `premises_geo.area TEXT`
(B16 §6) and the check the build instruction ordered ("premises belongs to
metering — check apps/metering/models.py Premises") found the column already
exists: `premises.area` has been the BR-MET-071 FK into tenancy's areas since
2026-08-16, seeded and filterable. Adding a second, free-text `area` beside it
would be exactly the duplication §6 warns against on `test_frequency`
("reconcile, not duplicate"), so the map's Area facts read the EXISTING link.
Reported in the lane close-out for the record.

RLS: NOTHING TO RE-POLICE. `premises` has had ENABLE+FORCE and the B2 §3
tenant-isolation policy since metering 0002, and that policy is row-scoped —
a new column on an already-policed table is covered the moment it exists
(the metering 0016 statement, verbatim posture).

NO BACKFILL. No coordinate exists anywhere to backfill from. The two lawful
writers land with this wave: the sample seed (deterministic, offline —
`apps/metering/sample_data.apply_premises_geo`) and the `geocode_premises`
management command (the live path, §10-D6's accepted geocoder).

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this file
declares schema that money is priced, posted or scoped against.

HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human."*). The standing record of that deferred
review is 12-governance/09-human-review-ledger.md; no 🔒 file reaches lifecycle
RATIFIED without a human sign-off recorded there.

⚠ **BOTH MARKERS WERE MISSING UNTIL 2026-09-02 AND G7 HAD BEEN RED ON THIS FILE
EVER SINCE IT LANDED (DEF-3229).** 198 of this repository's 218 migrations carry
them and 20 did not — so the gate that enforces the 🔒 protocol could not go green
for anybody, and every lane that ran it truthfully reported the failure as
"pre-existing, not mine". Nothing about the migration itself changed here.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0017_cr026_import_progress"),
    ]

    operations = [
        migrations.AddField(
            model_name="premises",
            name="lat",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="lng",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
