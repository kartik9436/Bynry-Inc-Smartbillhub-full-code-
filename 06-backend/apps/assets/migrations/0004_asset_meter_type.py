"""assets 0004 — BR-AST-044: `assets.meter_type_id`, a PROTECTed, NULLABLE FK into
the `meter_types` catalog migration 0003 created. HUMAN-OWNED (migration ordering
is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED rule
BR-AST-044 (CONFIRMED, PO 2026-08-09). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

WHY IT EXISTS: BR-AST-043 created `meter_types` but pointedly did NOT say whether
an asset should carry one — migration 0003 and lookups.MeterTypeLookupHandler both
recorded that as REPORTED, and the handler's used_by() was honestly 0 because no
column referenced the catalog. BR-AST-044 answers it: an asset carries BOTH
classifications — `type` (what kind of DEVICE, asset_types) AND `meter_type` (what
class of METER, meter_types) — alongside `read_method`. This migration adds the
second, shaped exactly like the read_method FK 0003 landed.

⚠ FOR THE REVIEWER — two things worth your eyes:
1. ADDITIVE ONLY, NO DATA STEP. Every existing row keeps meter_type NULL. There is
   no backfill and deliberately no asset_type→meter_type mapping: BR-AST-044 names
   `meter_type` as an independent classification, and the two lists overlap only by
   coincidence of vocabulary (asset_types has `meter`/`sub_meter`, meter_types has
   `sub_meter`/`master`/AMI/AMR/walk-by). Deriving one from the other would be
   inventing a rule the PO did not write — the same refusal 0003 made for the
   unmapped legacy read_method value 'na'. Tenants classify their fleet; the
   registry's meter_type filter makes the gap visible rather than guessed at.
2. No RLS work here. `assets` already carries ENABLE+FORCE from migration 0002 and
   `meter_types` from 0003; adding a column to an RLS-protected table changes no
   policy, and this migration touches no data, so it needs no tenant context.

Nullable + PROTECT is the whole contract: nullable because non-measuring assets
(PV, battery, container/cart) have no meter class, PROTECT so a meter type in use
can never be deleted — which is exactly what turns the BR-TEN-034 delete-lock and
the BR-TEN-030 code-immutable-once-used rule live for the meter_types card.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0003_meter_types_and_read_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="meter_type",
            field=models.ForeignKey(
                blank=True,
                db_column="meter_type_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assets",
                to="assets.metertype",
            ),
        ),
    ]
