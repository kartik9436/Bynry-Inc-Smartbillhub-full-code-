# ── Trace ──────────────────────────────────────────────
# Story:    PO ruling 2026-08-27 — "A METER NUMBER IS ALLOCATED FROM THE
#           TENANT'S SERIES, NEVER TAKEN FROM AN UPLOADED FILE" + its same-day
#           ADDENDUM (12-governance/02-decision-log.md).  Screens: WFL-01
#           meters/sub-meters/devices import, AST-01/02 asset detail
# Rules:    BR-AST-049 (new — the utility's OWN legacy meter reference, UNIQUE
#           per tenant, case-insensitive, partial) · BR-AST-026 (three
#           identifiers; this is the FOURTH fact and is none of them) ·
#           BR-AST-033 (a duplicate serial is warn-but-allow, which is exactly
#           why `serial_no` could not take this job) · BR-CUS-054 (the
#           precedent `customers.external_ref` sets, followed verbatim)
# Tests:    06-backend/tests/test_br_ast_049_external_ref.py
# Impacts:  apps/assets/services (_validate_asset · create · update) ·
#           apps/assets/selectors (asset_dict · asset_import_index) ·
#           the three assets import targets (apps/metering/import_runs.py)
# ───────────────────────────────────────────────────────
"""assets 0009 — `assets.external_ref` (BR-AST-049).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-27 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human").

**WHY THE COLUMN EXISTS.** The PO ruled that a meter's number is issued by the
tenant's own numbering settings and is never taken from an uploaded file. A
utility migrating from an old system holds its OWN meter reference — not the
manufacturer's serial, the number its previous software printed on work orders
— and under that ruling the reference had nowhere to go and would be lost at
import. This is where it goes.

**WHY IT IS NOT `serial_no`.** BR-AST-033 makes a duplicate serial
warn-but-allow, so a serial cannot identify a row; and a utility's own number
and a manufacturer's serial are different facts, so a column holding either
means neither.

**THE UNIQUE IS PARTIAL AND CASE-INSENSITIVE**, `customers.external_ref`'s own
posture: an asset created by the AST-05 wizard has no legacy reference and N
NULLs must coexist, while `MTR-118` and `mtr-118` are one device in every
legacy export anyone will hand us.

One nullable TEXT column plus one partial unique index. No backfill — every
existing row keeps NULL, which the partial predicate permits. Rollback is a
clean drop of the index and the column; nothing reads it until the import
lane writes it.
"""

from django.db import migrations, models
from django.db.models import F, Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0008_cr028_allocation_share"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="external_ref",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="asset",
            constraint=models.UniqueConstraint(
                F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_assets_tenant_external_ref_ci",
            ),
        ),
    ]
