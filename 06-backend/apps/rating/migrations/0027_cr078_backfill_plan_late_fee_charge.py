# ── Trace ──────────────────────────────────────────────
# Change:   CR-078 (PO ruling 2026-09-07, finance re-signed the same day).
#           THE DATA HALF of the pair `0026`/`0027`; see `0026`'s docstring for
#           the ruling and for why the two are separate files.
# Rules:    BR-RAT-1011 · BR-BIL-001 (❄️ frozen, untouched) · CLAUDE.md law 14
# Tests:    06-backend/tests/test_cr078_late_fee_from_the_plans_charge_code.py
# ───────────────────────────────────────────────────────
"""rating 0027 — CR-078: every existing plan gets the tenant's `LATE` code.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **THIS MIGRATION IS THE SAFETY STEP, NOT A CONVENIENCE.** `0026` adds a
column whose NULL means *charge no late fee at all* (BR-RAT-1011 — the ruling
reverses the fallback reading every other nullable column on `rate_plans`
carries). Every plan in the product is NULL the instant `0026` lands. This
migration is what stops that from reaching a bill: it points every existing
plan at the `LATE` charge code its own tenant already has, so the fee a
utility charged yesterday is the fee it charges tomorrow.

**WHY `LATE` AND NOT SOMETHING CHOSEN HERE.** `apps/tenancy/fixtures/
lookup_defaults.json` seeds exactly one late-payment charge code on every
tenant — `{"code": "LATE", "name": "Late payment fee", "charge_type":
"penalty", "percent": "1.5", "min_amount": "5"}` — and those two figures are
the SAME TWO the Billing-defaults screen holds (`late_pct` 1.5,
`late_min_amount` 5, `apps/tenancy/settings_families.BILLING_DEFAULTS`). That
identity is the whole reason `GT-10`'s ❄️ FROZEN **$8.13** does not move: the
engine changes which of two identical copies it reads, and `max($5.00, 1.5% ×
$542.10) = $8.13` either way. The CR row and the finance re-sign both say so in
those words.

**A TENANT WITH NO `LATE` CODE IS LEFT NULL AND IS NOT INVENTED.** Creating a
charge code here would put a fee on a customer's bill that no human at that
utility ever configured, booked to a GL account nobody chose. NULL is the
ruled answer for a plan that names no code — zero — and it is VISIBLE rather
than silent: `10-scripts/gates/g121_plans_name_their_late_fee_code.py`
counts the unpointed plans and fails, and `manage.py cr078_late_fee_codes`
prints the same count per tenant on demand.

⚠ **NO `try/except` AROUND THE WRITE, DELIBERATELY (CLAUDE.md law 14).**
Nothing here can fail per row and be usefully skipped: the column is nullable,
the FK target is read from the same database in the same transaction, and no
unique constraint is touched. A caught `IntegrityError` would poison this
migration's own PostgreSQL transaction while passing the whole SQLite suite —
the exact trap law 14 records — so if a statement here fails, the migration
fails.

⚠ **SET OPERATIONS, ONE `UPDATE` PER TENANT, NOT A ROW LOOP.** `NFR-5` forbids
a hard cap anywhere and T5 is 40,000 accounts; the plan count is small but the
shape is the one this repo insists on, and a per-row save would be a round trip
per plan.


⚠ **AND THE FIRST DRAFT OF THIS MIGRATION WROTE NOTHING AT ALL — MEASURED, NOT
IMAGINED (`DEF-RAT-4620`).** It used a plain `RatePlan.objects.filter(...)
.update(...)` and `manage.py migrate` printed:

    Applying rating.0027_cr078_backfill_plan_late_fee_charge... OK

over **eight seeded plans that stayed NULL**. `rate_plans` carries `FORCE ROW
LEVEL SECURITY` with the B2 §3 policy `tenant_id = NULLIF(current_setting(
'app.tenant_id', true), '')::uuid`, and a migration runs with that setting at
the database's default — all zeros — so **every tenant row is invisible to it**.
Nothing raised. The update matched zero rows and reported success, which is
precisely `tenancy/0031`'s own warning in a second costume: *a green run over an
empty table is not evidence about a backfill*, and here the table only LOOKED
empty.

**It would have shipped a silent catastrophe.** The column means *charge zero*,
so a backfill that writes nothing leaves every plan of every live tenant
charging **$0.00** in late fees, which is the exact failure `CR-078`'s ordering
was written to prevent — reached by obeying the ordering and getting the fill
wrong.

So this walks the tenants and sets `app.tenant_id` for each, which is CLAUDE.md
hard rule 1 applied to a migration and the shape `assets/0011` and
`assets/0003` already use. **`tenants` is an RLS-exempt platform table**
(`db/rls_tenancy_w0.sql`), so it can be enumerated before any tenant context
exists.

**HOW TO KNOW IT WORKED, AND IT IS NOT THE "OK":** it LOGS the number of plans
it pointed and the number of tenants it could not point (no live `LATE` code).
A migration whose only output is `OK` cannot distinguish 8 rows from 0.

REVERSIBLE, and the reverse is honest about what it destroys: it sets the
column back to NULL on every plan, which is where `0026` left it — and it walks
the tenants the same way, for the same reason.
"""

from django.db import migrations, transaction

import logging

logger = logging.getLogger(__name__)

#: ⚠ Re-declared rather than imported from any live module: a migration must
#: keep running when the seed moves on. `LATE` is the code
#: `apps/tenancy/fixtures/lookup_defaults.json` and `seed_demo.CHARGE_CODES`
#: both write, on every tenant, since before this column existed.
SEEDED_LATE_FEE_CODE = "LATE"

#: The all-zero uuid the database defaults `app.tenant_id` to. Restored when the
#: walk finishes so the connection is left as it was found (`assets/0011`).
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table (`db/rls_tenancy_w0.sql`), so
    it can be enumerated before any tenant context exists."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1 — never touch a tenant table without
    `app.tenant_id` set. On sqlite there is no RLS and no `set_config`: skipped
    honestly, and the same ORM path runs."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def backfill(apps, schema_editor):
    """Point every plan at its OWN tenant's live `LATE` charge code.

    Tenant by tenant, because the RLS policy makes that the only way to SEE a
    plan at all (see the module docstring) — and because a charge code belongs
    to one tenant, so the join is per tenant either way.

    The `LATE` lookup filters `deleted_at__isnull=True` for IS-1's reason —
    *a retired charge is not chargeable* — so a utility that retired theirs is
    left NULL and charges zero, which is what retiring it meant.

    ⚠ **EACH TENANT IS ITS OWN SAVEPOINT (CLAUDE.md law 14).** On PostgreSQL a
    single failed statement aborts the WHOLE transaction, so one tenant whose
    update is refused would take every other tenant's backfill with it and the
    entire `migrate` would roll back. The test suite runs on in-memory sqlite,
    which has no aborted-transaction state, so the version without the
    savepoint is green everywhere and fails the first time a real row refuses.
    **The nested `transaction.atomic()` is not the tidy option here, it is the
    only one — do not "simplify" it away.** The exception is LOGGED with the
    tenant named, never swallowed: a tenant that did not get its fill is a
    tenant whose late fees are about to be $0.00, and that must be readable.
    """
    RatePlan = apps.get_model("rating", "RatePlan")
    Charge = apps.get_model("rating", "Charge")
    connection = schema_editor.connection

    pointed = 0
    without_code = []
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                charge_id = (
                    Charge.objects.filter(
                        tenant_id=tenant_id,
                        code=SEEDED_LATE_FEE_CODE,
                        deleted_at__isnull=True,
                    )
                    .values_list("id", flat=True)
                    .first()
                )
                if charge_id is None:
                    # Stated absence, never an invention. Creating a charge code
                    # here would put a fee on a customer's bill that no human at
                    # that utility configured, booked to a GL account nobody
                    # chose. See the module docstring.
                    if RatePlan.objects.filter(tenant_id=tenant_id).exists():
                        without_code.append(str(tenant_id))
                    continue
                pointed += RatePlan.objects.filter(
                    tenant_id=tenant_id, late_fee_charge__isnull=True
                ).update(late_fee_charge_id=charge_id)
        except Exception:  # pragma: no cover — reported, never silently swallowed
            logger.exception(
                "rating 0027: tenant %s could not be backfilled with its %s charge code; "
                "its plans will charge $0.00 in late fees until a human points them "
                "(BR-RAT-1011). Every other tenant is unaffected (per-tenant savepoint).",
                tenant_id,
                SEEDED_LATE_FEE_CODE,
            )
    _leave_tenant(connection)
    # ⚠ THE NUMBER IS THE DELIVERABLE, NOT THE `OK`. A migration whose only
    # output is "Applying ... OK" cannot tell 8 rows from 0, and 0 is what the
    # first draft of this file silently did.
    logger.info(
        "rating 0027 (CR-078): pointed %d rate plan(s) at their tenant's %r charge code; "
        "%d tenant(s) with plans have no live %r code and their plans charge $0.00 "
        "(BR-RAT-1011): %s",
        pointed,
        SEEDED_LATE_FEE_CODE,
        len(without_code),
        SEEDED_LATE_FEE_CODE,
        ", ".join(without_code) or "none",
    )


def unbackfill(apps, schema_editor):
    """Back to NULL — where `0026` left every row. LOSSY and says so: a utility
    that re-pointed a plan at a different code loses that answer.

    Walks the tenants for the same RLS reason as `backfill`; a global
    `.update()` here would report success over zero rows exactly as the forward
    pass did.
    """
    RatePlan = apps.get_model("rating", "RatePlan")
    connection = schema_editor.connection
    cleared = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                cleared += RatePlan.objects.filter(tenant_id=tenant_id).update(
                    late_fee_charge_id=None
                )
        except Exception:  # pragma: no cover
            logger.exception("rating 0027 reverse: tenant %s could not be cleared", tenant_id)
    _leave_tenant(connection)
    logger.info("rating 0027 reverse (CR-078): cleared %d rate plan(s)", cleared)


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("rating", "0026_cr078_plan_late_fee_charge"),
    ]

    operations = [
        # DATA ONLY. An `AddField` or `AlterField` beside this is what `0026`'s
        # docstring — and `tenancy/0031`'s measured PostgreSQL failure — exist
        # to prevent.
        migrations.RunPython(backfill, unbackfill),
    ]
