"""rating 0007 — `taxes` gains the qualifiers the PO's ruled Texas rates need.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md sensitive
path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a
recorded human sign-off.

PO ruling 2026-08-18 (decision log top row; DEF-254 split into (a) figures,
(b) the silence, (c) THIS model gap), verbatim twice: *"Tax jurisdiction rates
(5 TX rows) - already answered"* and *"I ahve already answered it; close it"*.
The answer is r10's own tax table, and three of its five rows carry a condition
`taxes` could not express:

  * **State Utility Tax 6.25 %** — *"Comm, Industrial only"*, residential exempt
  * **City Franchise Fee 1.50 %** — *"Inside city limits"*, 61 outside-city
    accounts exempt
  * **PUC Regulatory Fee $0.85 flat/bill** — electric only (expressible already,
    through `applies_to_services`)

Seeding the first as written would have charged 6.25 % to every residential
customer r10 exempts. So the columns land BEFORE the seed, which is the whole
point of DEF-273 having been filed rather than worked around.

Two columns, both NULLABLE, both meaning "no restriction" when NULL — so every
`taxes` row that already exists keeps behaving exactly as it did this morning.
NOTHING IS BACKFILLED: a tax whose condition nobody has stated is a tax that
applies to everybody, which is what it did yesterday, and inventing a class
list or a city name for an existing tenant's row would be exactly the invented
figure the 2026-08-17 tax ruling forbids.

RLS: `taxes` is already ENABLE + FORCE row level security with its
`taxes_tenant_isolation` policy, created by `rating 0003_rls_w1_policies` from
`db/rls_rating_w1.sql`. Adding a column to a table under RLS FORCE inherits the
table's policy — there is no per-column policy in Postgres — so this migration
creates no policy and needs none. CLAUDE.md rule 1 asks that a migration which
CREATES a tenant table create its policy in the SAME migration; this one alters
an already-protected table, and the check that proves it is
`tests/test_rls_isolation.py`'s taxes case, which passes unchanged.

A CHECK CONSTRAINT bounds `premises_scope_kind` to the FIVE mechanisms the PO
named in CR-013 part 4 (2026-08-18, `TAXES-FEES-BUSINESS-SPEC.md`, TAX-02 step 1,
verbatim): *"how the system decides a premise is in scope (city limits, county,
state, taxing district, explicit premise list)"*. All five are in the column's
vocabulary FROM THIS MIGRATION even though only three can be resolved against
what `premises` records today — a second migration to widen an enum is exactly
the avoidable cost, and a mechanism that cannot be evaluated fails CLOSED and is
named rather than silently applying. Same shape `rating 0006` gave
`time_of_use_windows.channel`.

There is deliberately NO check on `applies_to_customer_classes`: it is a JSON
array validated in `services._validate_tax` against the platform `account_types`
catalog, exactly as `applies_to_services` is validated against the enabled
service catalog, and a DB-level check cannot read another table's rows.

⚠ WHAT THIS MIGRATION DELIBERATELY DOES NOT ADD, so it reads as a decision and
not as an oversight — each is named in the lane's write-back:
  * CR-013 part 4's **exemption object** (*"categories, accounts holding each,
    certificate expiry"*). That is an ACCOUNT-side table with a certificate and
    a date; `applies_to_customer_classes` is a SCOPE and is not a substitute.
  * The **explicit premise list** mechanism's join table. The vocabulary carries
    the value; the set it needs does not exist and the scope fails closed.
  * **`liability_gl_account_id` already exists** on this table (B11 F-3,
    BR-BIL-069) and is what part 4's *"mandatory liability GL"* asks for, so no
    column is added for it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0006_tou_window_register"),
    ]

    operations = [
        migrations.AddField(
            model_name="tax",
            name="applies_to_customer_classes",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="premises_scope_kind",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tax",
            name="premises_scope_value",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="tax",
            constraint=models.CheckConstraint(
                condition=models.Q(("premises_scope_kind__isnull", True))
                | models.Q(
                    (
                        "premises_scope_kind__in",
                        ("city_limits", "county", "state", "taxing_district", "premise_list"),
                    )
                ),
                name="ck_taxes_premises_scope_kind",
            ),
        ),
    ]
