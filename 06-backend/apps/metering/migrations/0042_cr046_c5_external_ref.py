# ── Trace ──────────────────────────────────────────────
# Change:  CR-046 C5 — `external_ref` present and unique per tenant on every
#          upload target that lacks it, following the `customers` precedent.
#          Screens: WFL-01 premises/units import (stages 1–5), PRM-01/02, MET-02
# Rules:   BR-MET-403 (new — the utility's own PREMISE reference, unique per
#          tenant, case-insensitive, partial) · BR-MET-404 (new — the same fact
#          on `units`, and the column did not exist at all) · BR-AST-049 (the
#          assets precedent this follows verbatim) · BR-CUS-054 (the original
#          `customers.external_ref` posture both descend from) ·
#          BR-TEN-035 (don't renumber what a customer already has — this is the
#          column that keeps that promise once the number stops coming off the
#          file)
# Tests:   06-backend/tests/test_cr046_identifiers.py
# Impacts: apps/metering/import_runs.py (both targets' match key, dedupe key,
#          template column) · import_rules.py (the two new rule pairs) ·
#          apps/metering/models.py
# ───────────────────────────────────────────────────────
"""metering 0042 — `premises.external_ref` gets a unique, `units.external_ref` is born.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-27 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

**WHY.** CR-046 applies the meter ruling to the other three uploads: a record's
own identifier is ISSUED from the tenant's numbering series and never taken from
the file. That leaves the utility's OWN id — the number their previous software
printed on every work order — with nowhere to go, and with no way for a
corrected re-run of the same file to find the rows it created. `assets` solved
exactly this on 2026-08-27 (BR-AST-049); this is that solution on `premises` and
`units`.

**TWO DIFFERENT OPERATIONS, AND THE DIFFERENCE MATTERS FOR ROLLBACK.**

  * `premises.external_ref` **already exists** and has held data since CR-023
    (the `LEGACY_KEY` header maps to it). This migration adds only the INDEX.
    ⚠ **A tenant who has already loaded two premises carrying the same legacy
    key will find this migration REFUSES** — `CREATE UNIQUE INDEX` fails on the
    existing duplicate. That is the correct outcome and not a bug: the pair is a
    real data error, and the alternative is an index that silently is not
    unique. It is stated here because the operator's fix is to clear one of the
    two values, and nothing else in the repo would tell them so.
  * `units.external_ref` is a NEW nullable column. Every existing row keeps
    NULL, which the partial predicate permits. No backfill; nothing reads it
    until the import writes it.

**PARTIAL AND CASE-INSENSITIVE**, `customers.external_ref`'s stated posture: a
premises typed into PRM-02 has no legacy reference and N NULLs must coexist,
while `GIS-118` and `gis-118` are one property in every legacy export.

**ROLLBACK** is a clean drop of both indexes and of the `units` column. The
`premises` column stays — dropping a column that has taken customer data is the
one irreversible act available here, and CR-046 step 8 says so explicitly.
"""

from django.db import migrations, models
from django.db.models import F, Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0041_def650_owner_master_account"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="premises",
            constraint=models.UniqueConstraint(
                F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_premises_tenant_external_ref_ci",
            ),
        ),
        migrations.AddField(
            model_name="unit",
            name="external_ref",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="unit",
            constraint=models.UniqueConstraint(
                F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_units_tenant_external_ref_ci",
            ),
        ),
    ]
