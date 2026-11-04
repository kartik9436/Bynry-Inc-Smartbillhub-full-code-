"""rating 0023 — DEF-652: the PO's tax ruling reaches the data.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this one MOVES
MONEY on every discounted bill of every tenant).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-28 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.

WHAT THIS CHANGES, IN MONEY
---------------------------
A **$62.14** bill with a 25% senior discount of **$15.54** used to be taxed at
6.85% on the REDUCED **$46.60** and charged **$3.19**. It is now taxed on the
FULL **$62.14** and charged **$4.26** — **$1.07 more per discounted bill per
cycle**, on every discounted account of every tenant.

THE RULING, VERBATIM (PO, 2026-08-27)
-------------------------------------
*"Does a discount come off before or after tax? Tax the full amount before
discount — The utility remits tax on the full service value; the discount is the
utility's cost, not the tax authority's. - what does the tax law in the US say -
lets go with it"*, confirming an earlier *"this is correct - A $62.14 bill with a
25% senior discount of $15.54 — is the 6.85% tax charged on $62.14 ($4.26)"*.

In this schema that is `discount_treatment = "after"`. ⚠ **The names describe
when the DISCOUNT is applied, not when the tax is** — `before` puts the discount
first and so taxes the reduced base; `after` puts it last and so taxes the full
base. `rating.selectors.taxable_subtotal_for` is the one reader and its docstring
says the same thing.

⚠ NO ❄️ FROZEN FIGURE MOVES
---------------------------
B4 and B5 are silent on discounts — grepped, and recorded in the decision log on
2026-08-22 when the discount stage landed. `10-scripts/03-golden-verify.py` reads
**33 PASS / 0 FAIL, exit 0** before and after this migration; every B5 fixture
bill carries no discount, so this change is the identity on all 33. `$4.26` is
the PO's own figure, not a finance-signed golden, and it is asserted in
`tests/test_def_652_tax_on_the_full_service_value.py` and in the new part 3 of
the golden harness so that it, too, cannot drift silently.

TWO OPERATIONS, AND THE SECOND IS THE ONE THAT MATTERS
------------------------------------------------------
1. `AlterField` — the column default. This is what every NEW tax gets, from the
   wizard, from the API, from `_seed_fixture_taxes`, from `seed_sample_taxes`,
   from `seed_demo` and from every test, because all of them build the row and
   none of them states a treatment.

2. `RunPython` — **existing rows holding `before` become `after`.** Without it
   the ruling reaches nobody: every tenant alive today was provisioned with its
   tax rates already seeded, so an `AlterField` alone would fix only utilities
   that have not been created yet.

⚠ WHY IT IS LAWFUL TO MOVE EXISTING ROWS, STATED SO IT CAN BE ARGUED WITH
-------------------------------------------------------------------------
No stored `before` is a utility's answer to this question. Three reasons, and
all three are checkable:

* **Every row predates the ruling.** The ruling is 2026-08-27; the column landed
  2026-08-21 with `before` pre-selected. A value written before a question was
  answered cannot be a rejection of the answer.
* **The control shipped pre-set to `before`.** TAX-02's *Discounts* select
  defaulted to the first option, so even a tax SAVED through the wizard carries
  `before` because the form arrived that way, not because anyone chose it.
* **It is one select to put back**, per authority, visibly, and the change is
  audited like any other tax edit. Nothing here is irreversible for a utility
  that disagrees about one of its authorities.

⚠ **AND NOTHING ALREADY ISSUED CHANGES.** Hard rule 4: an issued invoice, its
lines and its journal entries are immutable. This migration touches the `taxes`
table only. A bill that has already gone out keeps the tax it was issued with;
if a utility wants it re-priced, that is a CORRECTION — new rows, a new run —
and never an edit. The new figure applies from the next bill run onwards.

⚠ **HARD RULE 1 IS OBEYED ROW BY ROW.** `taxes` is a tenant table with ENABLE +
FORCE row-level security and a deny-by-default policy, so under a NON-superuser
application role a bare `UPDATE` here matches ZERO rows and reports success —
the quietest possible failure there is. This walks the RLS-exempt `tenants`
table and sets `app.tenant_id` per tenant before touching anything, the shape
`assets/0003_meter_types_and_read_methods.py` established, and leaves the nil
sentinel behind rather than `''` for the reason that file records.

⚠ **AND IT WAS NOT PROVED BY THE DEV HOST, WHICH IS WHY IT IS WRITTEN DOWN.**
The development role `smartbillhub` is a SUPERUSER (`pg_roles.rolsuper = t`), and
a superuser bypasses row-level security entirely — so on the box this was built
on the unscoped update would have "worked" and told us nothing. The loop is
correct for the deployment that matters, not for the one it was tested on. What
WAS proved on Postgres: applied to a seeded tenant whose two authorities had been
put back to `before`, it printed *"2 tax row(s) across 1 tenant(s)"* and both rows
read `after` afterwards.

⚠ **NO `audit_log` ROW IS WRITTEN, AND THAT IS A DECISION.** `audit_log` is
RANGE-partitioned by month; an INSERT from inside a schema migration fails on a
host whose current-month partition has not been created yet, which would turn a
money fix into a failed deploy. The record of this act is the migration itself —
in git, in `django_migrations`, in the decision log and in the review ledger —
and the RunPython PRINTS the tenant and row counts it changed so the operator
sees it happen. Hard rule 7 governs money ACTIONS a person takes in the product;
this is a deployment, and the deployment's own record is the migration.
"""

from django.db import migrations, models

#: The nil sentinel, NOT `''` — see assets/0003, which records why the empty
#: string outlives the migration and poisons later foreign-key validation.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (db/rls_tenancy_w0.sql), so it
    can be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md rule 1: never touch a tenant table without app.tenant_id set.
    On sqlite (the test DB) there is no RLS and no set_config — skipped
    honestly, and the update is then unfiltered, which is correct there."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def state_the_ruled_treatment_on_every_existing_tax(apps, schema_editor):
    """Every `taxes` row still holding the pre-ruling `before` becomes `after`.

    Per tenant, under that tenant's own RLS context. Idempotent: a second run
    finds nothing to change. A row a utility has since set to `before` ON
    PURPOSE, after this migration, is never revisited — this runs once.
    """
    Tax = apps.get_model("rating", "Tax")
    connection = schema_editor.connection
    tenants, changed = 0, 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        moved = Tax.objects.filter(tenant_id=tenant_id, discount_treatment="before").update(
            discount_treatment="after"
        )
        if moved:
            tenants += 1
            changed += moved
    _leave_tenant(connection)
    print(
        f"  rating 0023 (DEF-652): {changed} tax row(s) across {tenants} tenant(s) now levy on "
        f"the full service value. A $62.14 bill with a $15.54 discount moves from $3.19 of tax "
        f"to $4.26. Nothing already issued changes (hard rule 4)."
    )


def _irreversible_by_construction(apps, schema_editor):
    """Deliberately a NO-OP, not a flip back.

    Reversing this would have to turn `after` into `before` — and after it has
    run there is no way to tell a row THIS moved from a row a utility set to
    `after` itself. Putting them all back would silently overwrite a real
    choice, which is the exact failure this migration exists to correct. The
    schema half below reverses cleanly; the data half is a statement that was
    made, and un-making it is a decision a human takes per authority.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0022_br_rat_113_plan_tax_attachments"),
        # `tenants` is walked to set RLS context per tenant.
        ("tenancy", "0016_br_rat_081_service_metered"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tax",
            name="discount_treatment",
            field=models.TextField(default="after"),
        ),
        migrations.RunPython(
            state_the_ruled_treatment_on_every_existing_tax,
            _irreversible_by_construction,
        ),
    ]
