# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5799 — `rating/0038`'s backfill ran with NO tenant context, so
#          RLS FORCE hid every row from it and all six seeded plans came out of
#          the migration reading `[]` (*every class*) when three of them named
#          one. Silent, and invisible to the test suite: SQLite has no RLS.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set) · DEF-RAT-5768 (the ruling 0038 implements) ·
#          CLAUDE.md hard-won law 14 (the suite's database cannot express the
#          production guarantee) · CLAUDE.md 🔒 migration ordering
# Tests:   06-backend/tests/test_def_rat_5768_plan_customer_classes.py
# ───────────────────────────────────────────────────────
"""rating 0039 — repair `rating/0038`'s backfill, which RLS silently emptied.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **WHAT WENT WRONG IN `0038`, MEASURED RATHER THAN REASONED ABOUT.** Its
`RunPython` did `RatePlan.objects.all()` with no tenant context. On PostgreSQL
`rate_plans` has `relrowsecurity` AND `relforcerowsecurity` true and the
migration role `sbh` has `rolbypassrls = false`, so that queryset returns
**zero rows** — checked with `SELECT count(*) FROM rate_plans` at an unset
`app.tenant_id`, which answered `0`. The loop therefore ran over nothing, every
row kept the column's `default=list`, and **three plans that named a customer
class came out naming none** — which under `DEF-RAT-5768`'s ruling means EVERY
class, the opposite of what they said.

⚠ **AND NO TEST COULD HAVE SEEN IT, WHICH IS THE PART WORTH WRITING DOWN.**
`config/settings/test.py` hardcodes SQLite; SQLite has no row-level security,
so the same loop sees every row there and the 12 cases over this migration pass
green. That is hard-won law 14's shape exactly — *the broken version passes the
entire suite on every machine and fails the first time it meets a real
database* — with RLS in place of an aborted transaction.

⚠ **`0038` IS NOT EDITED, AND THAT IS DELIBERATE.**
`.github/workflows/migration-guard.yml` treats committed migrations as
append-only, and `0038` is pushed. Repairing forward is also the honest record:
a host that already ran `0038` needs this repair, and rewriting history would
leave no trace that it ever happened.

── WHERE THE LOST VALUES COME FROM, AND THE ONE CASE THAT CANNOT BE RECOVERED ──

`0038` DROPPED `rate_plans.account_type_id`, so the old value is not in that
table any more. It IS in `plan_versions.snapshot`, which `BR-RAT-111` keeps
append-only and which records the plan as filed. **Measured on the seeded
estate: 3 plans name a class in their snapshots — `SCW-RES`, `SCW-COM` and
`SCW-IND` — which is exactly the 3 that held one before `0038` ran.** Full
recovery there.

⚠ **A DRAFT PLAN THAT NAMED A CLASS AND HAS NEVER FILED A VERSION CANNOT BE
RECOVERED, AND THIS MIGRATION SAYS SO RATHER THAN PRETENDING OTHERWISE.** It
has no snapshot to read. On this estate that set is EMPTY (all 6 plans carry a
filed version), but on another host it need not be; such a plan is left at `[]`,
which means *every class*, and `DEF-RAT-5799` carries the residual gap.

⚠ **IT ONLY EVER FILLS AN EMPTY LIST.** A plan whose `account_type_ids` already
holds anything is left exactly as it is — so running this after a clerk has
already set the classes by hand cannot overwrite their work, and running it
twice changes nothing the second time.
"""

from django.db import migrations

#: The nil sentinel rather than `''` — `assets/0003` records why in full:
#: `set_config(..., false)` is SESSION level and outlives this migration, and
#: an empty string makes a later `::uuid` cast raise. A real uuid that matches
#: no row keeps deny-by-default intact.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table, so it enumerates with no
    context — the same door `assets/0003` uses."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _repair(apps, schema_editor):
    RatePlan = apps.get_model("rating", "RatePlan")
    PlanVersion = apps.get_model("rating", "PlanVersion")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        # The LATEST snapshot that names a class wins — a plan corrected or
        # re-versioned since should read as it was last filed, not as it was
        # first filed.
        latest: dict = {}
        for version in PlanVersion.objects.order_by("created_at").iterator():
            snapshot = version.snapshot or {}
            if not isinstance(snapshot, dict):
                continue
            stated = snapshot.get("account_type_id")
            if stated:
                latest[version.rate_plan_id] = str(stated)
        for plan in RatePlan.objects.iterator():
            if plan.account_type_ids:
                continue  # already stated — never overwritten
            stated = latest.get(plan.id)
            if stated:
                plan.account_type_ids = [stated]
                plan.save(update_fields=["account_type_ids"])
    _leave_tenant(connection)


def _noop(apps, schema_editor):
    """Reversing this does NOT re-empty the lists. Putting a repaired plan back
    to *every class* would be re-applying the defect, and the column `0038`
    reversed into is restored by `0038`'s own reverse."""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0038_def_rat_5768_plan_customer_classes"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(_repair, _noop)]
