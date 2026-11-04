# ── Trace ──────────────────────────────────────────────
# Change:   CR-078 (PO ruling 2026-09-07, finance re-signed the same day —
#           12-governance/09-human-review-ledger.md). THE SCHEMA HALF.
# Rules:    BR-RAT-1011 (a plan names the charge code its late fee is taken
#           from; naming none charges ZERO) · BR-BIL-001 (the arithmetic,
#           ❄️ B4/B5 FROZEN and NOT moved by this) · CLAUDE.md law 14 and
#           apps/tenancy/migrations/0031's docstring (schema OR data, never
#           both, on a table whose rows the migration touches)
# Tests:    06-backend/tests/test_cr078_late_fee_from_the_plans_charge_code.py
# ───────────────────────────────────────────────────────
"""rating 0026 — CR-078: the plan names its late-fee charge code. SCHEMA ONLY.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

THE RULING, VERBATIM (PO, 2026-09-07)
--------------------------------------
    "this is wrong - you ahve to take late fees form charge code mentione din
     the plan - if plan doent provide you that charge code then you have to put
     zero on late payment. - Logic aplplied ot Minimum late fee $5- - you can
     link these defaults in Charge code - we have a charge code for late
     payment"

⚠ **THIS MIGRATION ON ITS OWN IS A LOADED GUN, AND THE ORDER IS THE CHANGE.**
The column arrives NULL on every existing plan. NULL means *zero late fee*
(BR-RAT-1011), so between this migration and `0027` every plan in the product
charges nothing — which is precisely the silent failure the CR row names:

    "no plan names a late-fee charge code today because no such field exists,
     so switching the engine first turns every late fee on every live tenant to
     zero, silently, on real bills."

That is safe HERE and only because **nothing reads the column until `0027` has
filled it**: `selectors.plan_late_fee_terms` — the one reader — did not exist
before this pair landed, and it and `0027` ship in the same commit. A deploy
that applied `0026` and stopped would have a column nobody consults.

SCHEMA ONLY, AND THE FILL IS `0027`
------------------------------------
CLAUDE.md law 14 in another costume, measured by `tenancy/0031`: a migration
that ALTERs a table and UPDATEs its rows passes the whole SQLite suite and
fails on a real PostgreSQL with *"cannot ALTER TABLE ... because it has pending
trigger events"* — `rate_plans` carries `DEFERRABLE INITIALLY DEFERRED` foreign
keys (tenant, and now this one), whose deferred trigger events are not flushed
until COMMIT. So this migration adds the column and writes not one row.

REVERSIBLE. `AddField` on a nullable column drops cleanly and takes the
utility's answers with it — which is the honest cost of a reverse, not a bug.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0025_cr066_discount_gl_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="rateplan",
            name="late_fee_charge",
            field=models.ForeignKey(
                blank=True,
                db_column="late_fee_charge_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="late_fee_for_plans",
                to="rating.charge",
            ),
        ),
    ]
