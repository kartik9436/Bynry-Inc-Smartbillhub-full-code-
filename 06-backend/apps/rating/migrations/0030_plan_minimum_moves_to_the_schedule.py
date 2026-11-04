# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-10, decision log "A RATE SCHEDULE IS THE ONE PLACE
#           A SERVICE'S FIGURES ARE SET; A PLAN SHOWS THEM" (13) and "THE
#           PER-SERVICE FIGURES MOVE TO THE SCHEDULE — AND NO BILL MOVES WITH
#           THEM" (14).
# Rules:    BR-RAT-028 (AMENDED — the source moves, the arithmetic does not) ·
#           GT-13 / GT-19 (re-read: both state the arithmetic and neither names
#           a source) · CLAUDE.md hard rule 1 · CLAUDE.md law 14
# Tests:    06-backend/tests/test_cr090_minimum_reads_from_the_schedule.py
# ───────────────────────────────────────────────────────
"""rating 0030 — the per-service minimum MOVES from the plan onto the schedule.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-10 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

**THE RULING, verbatim (PO, 2026-09-10):** *"set it in rates and use it in plans
- thats it - this is rule - when you do the final review on plan you show all
values - coming from rate schedule; and when we view plan details you show the
details again coming from rate schedule"*.

⚠ **THIS MIGRATION IS THE SAFETY STEP, AND WITHOUT IT A REAL PLAN UNDER-BILLS.**
`0031` removes `plan_services.minimum_amount`. On the shipped fixture that column
is the ONLY place the figure exists: plan `RES-STD` states a **$15.00** water
minimum and the schedule it points at (`Residential Water — Inclining tiers`)
states **none** — `seed_demo.RATE_PLANS` writes the plan's figure and
`_seed_schedules` deliberately writes no version-level money at all. Drop the
column without moving the value first and `WE-3`'s minimum adjustment stops being
computed: a `0.4 kgal` residential water bill prices **$9.60 + $8.00 base** and
stops there instead of being topped up to the **$15.00** floor, so that account
is short **$5.40** every month and every check in this repository stays green,
because the arithmetic over whatever figure arrives is still correct.

**WHY THE SCHEDULE'S COLUMN IS THE RIGHT DESTINATION AND IS NOT NEW.**
`tariff_versions.minimum_bill` already exists, is already written by the rate
schedule wizard (`services.create_rate_schedule` → `minimum_bill=cleaned[...]`,
plus the per-size rows), and is already PUBLISHED to billing by
`rating.selectors.pricing_inputs`. It has simply never been READ: `apps/billing/
gather._tariff_config_for` says so in its own words — *"`pricing_inputs` ALSO
PUBLISHES A `minimum_bill`, AND IT IS NOT READ HERE — DEF-2446 … nothing signed
says what a schedule that ALSO carries one means"*. **The ruling above is that
missing signature.** So this is not a new home for the figure; it is the home the
product already offered a clerk, finally becoming the one the engine reads.

⚠ **EVERY VERSION OF THE ATTACHED TARIFF, NOT ONLY THE ONE IN FORCE — AND THAT
IS THE WHOLE REASON THIS IS NOT A ONE-LINE UPDATE.** The plan's column was
VERSION-INDEPENDENT: whichever version `BR-RAT-007` resolved at the service date,
the plan's `$15.00` applied. The schedule's column is version-DEPENDENT. So a
back-dated re-bill priced from last year's version would lose the floor unless
every version of that tariff carries it. Each version that already states its own
figure is LEFT ALONE — a human typed that one, and overwriting it with the plan's
would be this repository's oldest defect (`DEF-154`) in the other direction.

⚠ **A DISAGREEMENT IS REPORTED, NEVER RECONCILED.** Where a plan states one
figure and a version of its schedule already states a DIFFERENT one, this
migration writes nothing to that version and LOGS the pair. That case cannot
arise on the shipped fixture (no version carries a minimum at all) and it is not
a decision a migration may take: preferring either of two figures a human typed
is exactly the shape of `OQ-238`, and the plan's figure is about to be deleted,
so a silent preference would be undetectable afterwards.

⚠ **NO `try/except` AROUND A SINGLE ROW (CLAUDE.md law 14).** Nothing here can
fail per row and be usefully skipped — the column is nullable, no unique
constraint is touched, and both models are read from the same database in the
same transaction. What IS wrapped is the per-tenant unit of work, in a nested
`transaction.atomic()`, because on PostgreSQL one failed statement aborts the
WHOLE transaction and would take every other tenant's move with it; the suite
runs on in-memory sqlite, which has no aborted-transaction state, so the version
without the savepoint is green everywhere and fails the first time a real row
refuses.

⚠ **IT WALKS THE TENANTS AND SETS `app.tenant_id` (CLAUDE.md hard rule 1, and
`DEF-RAT-4620` is what skipping it looks like).** `plan_services` carries
`FORCE ROW LEVEL SECURITY`; a migration runs with `app.tenant_id` at the
database default — all zeros — so **every tenant row is invisible to it** and a
plain `.update()` matches nothing, raises nothing, and prints `OK`. Over a
backfill that is the difference between moving a `$15.00` floor and moving none.

**HOW TO KNOW IT WORKED, AND IT IS NOT THE `OK`:** it logs the number of
versions it wrote, the number of plan rows whose figure had nowhere to go (no
rate schedule attached for that service), and every disagreement by name. A
migration whose only output is `OK` cannot tell 12 rows from 0.

**REVERSIBLE, and the reverse is honest about what it cannot do:** it clears
`minimum_bill` on the versions this migration wrote — recorded per version in
the same run is not possible across a `migrate` boundary, so the reverse clears
a version's figure only where the ATTACHED PLAN still states the same figure,
which is exactly the set this forward pass wrote while `0031` has not yet
removed the plan's column. Reversing after `0031` restores nothing, and
`0031`'s own reverse says so.
"""

from decimal import Decimal

import logging

from django.db import migrations, transaction

logger = logging.getLogger(__name__)

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


def _plan_minimums(PlanService, PlanRateSchedule, tenant_id):
    """`{tariff_id: (plan_code_or_id, service_id, minimum)}` for every plan
    service line that states a minimum AND has a schedule attached.

    The join is (rate_plan, service) → tariff, which is `plan_rate_schedules`'
    own unique constraint, so a service resolves to at most one tariff per plan.
    """
    attached = {
        (str(row.rate_plan_id), str(row.service_id)): row.tariff_id
        for row in PlanRateSchedule.objects.filter(tenant_id=tenant_id)
    }
    out = []
    orphaned = []
    for row in PlanService.objects.filter(
        tenant_id=tenant_id, minimum_amount__isnull=False
    ).select_related("rate_plan", "service"):
        tariff_id = attached.get((str(row.rate_plan_id), str(row.service_id)))
        if tariff_id is None:
            # The plan states a floor for a service it has attached no schedule
            # to. Publishing is refused in that state (D2 completeness), so no
            # bill has ever been priced from it — but it is a figure a human
            # typed and it is about to be deleted, so it is NAMED.
            orphaned.append((row.rate_plan.code, row.service.code, row.minimum_amount))
            continue
        out.append((tariff_id, row.rate_plan.code, row.service.code, row.minimum_amount))
    return out, orphaned


def move_minimums_onto_the_schedule(apps, schema_editor):
    """Copy each plan service line's minimum onto EVERY version of the tariff
    its plan attached for that service, where the version states none."""
    PlanService = apps.get_model("rating", "PlanService")
    PlanRateSchedule = apps.get_model("rating", "PlanRateSchedule")
    TariffVersion = apps.get_model("rating", "TariffVersion")
    connection = schema_editor.connection

    written = 0
    orphaned_total = []
    disagreements = []
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                moves, orphaned = _plan_minimums(PlanService, PlanRateSchedule, tenant_id)
                orphaned_total.extend(orphaned)
                for tariff_id, plan_code, service_code, minimum in moves:
                    versions = TariffVersion.objects.filter(
                        tenant_id=tenant_id, tariff_id=tariff_id
                    )
                    # A version that already states a figure is LEFT ALONE and
                    # reported when it disagrees. See the module docstring.
                    for stated in versions.exclude(minimum_bill__isnull=True):
                        if Decimal(stated.minimum_bill) != Decimal(minimum):
                            disagreements.append(
                                (
                                    plan_code,
                                    service_code,
                                    str(minimum),
                                    str(stated.minimum_bill),
                                    str(stated.id),
                                )
                            )
                    written += versions.filter(minimum_bill__isnull=True).update(
                        minimum_bill=minimum
                    )
        except Exception:  # pragma: no cover — reported, never silently swallowed
            logger.exception(
                "rating 0030: tenant %s could not have its per-service minimums moved "
                "onto its rate schedules. `0031` is about to remove the plan's column, "
                "so this tenant's floors would stop being charged — DO NOT run `0031` "
                "until this is resolved. Every other tenant is unaffected (per-tenant "
                "savepoint).",
                tenant_id,
            )
    _leave_tenant(connection)

    # ⚠ THE NUMBERS ARE THE DELIVERABLE, NOT THE `OK`.
    logger.info(
        "rating 0030 (PO ruling 2026-09-10): wrote the per-service minimum onto %d rate "
        "schedule version(s). %d plan service line(s) state a minimum with no schedule "
        "attached and their figure has nowhere to go: %s. %d version(s) already state a "
        "DIFFERENT figure and were left untouched (reported, never reconciled — that is "
        "OQ-238's shape): %s",
        written,
        len(orphaned_total),
        orphaned_total or "none",
        len(disagreements),
        disagreements or "none",
    )


def clear_the_moved_minimums(apps, schema_editor):
    """Reverse — see the module docstring's last paragraph for what this can and
    cannot restore."""
    PlanService = apps.get_model("rating", "PlanService")
    PlanRateSchedule = apps.get_model("rating", "PlanRateSchedule")
    TariffVersion = apps.get_model("rating", "TariffVersion")
    connection = schema_editor.connection

    cleared = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        try:
            with transaction.atomic():
                moves, _orphaned = _plan_minimums(PlanService, PlanRateSchedule, tenant_id)
                for tariff_id, _plan_code, _service_code, minimum in moves:
                    cleared += TariffVersion.objects.filter(
                        tenant_id=tenant_id, tariff_id=tariff_id, minimum_bill=minimum
                    ).update(minimum_bill=None)
        except Exception:  # pragma: no cover
            logger.exception("rating 0030 reverse: tenant %s could not be cleared", tenant_id)
    _leave_tenant(connection)
    logger.info("rating 0030 reverse: cleared %d rate schedule version minimum(s)", cleared)


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0029_cr087_a1_amount_by_customer_class"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(move_minimums_onto_the_schedule, clear_the_moved_minimums),
    ]
