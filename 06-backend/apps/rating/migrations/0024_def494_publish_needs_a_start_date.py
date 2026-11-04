"""rating 0024 — DEF-494: every published plan states when it starts.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this one writes the
date the RULED pricing path uses to decide whether a plan prices a bill at all).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-28 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.

⚠ **THE MIGRATION NUMBER IS ALLOCATED, NOT TAKEN FROM THE WATERMARK** (DEF-892).
`0023` was the real leaf and `0024` is reserved in
`12-governance/14-id-reservations.md` under this lane's block.

THE RULING, VERBATIM (PO, 2026-08-28)
-------------------------------------
The question put was *"a rate plan has been published, but nobody ever typed a
start date for it — should it be charging customers?"* The PO chose neither of
the two obvious answers and took a third: **require a date to publish** — *"you
cannot publish a plan without saying when it starts, so the situation stops
existing; any published plan today that has no date gets one."*

`apps/rating/services.publish_plan` is the *"cannot publish"* half (BR-RAT-890).
This file is the *"gets one"* half.

WHAT WAS WRONG, IN THE PRODUCT'S OWN NUMBERS
--------------------------------------------
`rating.selectors.plan_ref` — what the bill run reads — filters on
`status="published"` and consults **no date at all**, so an undated published
plan bills **forever**. `resolution.PlanVersion.in_force_on` requires a stated
`effective_from`, so the SAME plan is in force **never** and R1 refuses the
account outright. Both readings are defensible and BR-RAT-007 chooses neither.

Measured on the seeded Brazos Bend tenant at the tip, through the real bill run
and the real pricing-shadow report: **47 of 47 accounts refused at R1** on each
of three runs — *"R1: account AC-2026-00001 has no plan version in force on
2026-07-02"* — while the live path priced every one of them. **R1 gates every
later step**, so R2–R7 could not be compared on a single account.

⚠ WHICH DATE, AND WHY IT IS NOT "TODAY" — THE JUDGMENT THIS LANE MADE
----------------------------------------------------------------------
The ruling deliberately does **not** say what date an existing undated plan
gets; the decision log says so in as many words. So this is a lane decision,
recorded with its worked figure in `12-governance/02-decision-log.md` of
2026-08-28.

**The date used is the earliest `effective_from` among the ACTIVATED versions of
the rate schedules the plan itself binds** — a date a human at the utility typed,
about this plan's own prices, that the product already stores.

Worked, on the seeded tenant:

    plan     earliest bound schedule version   earliest period actually billed
    SCW-RES  2026-06-01                        2026-06-01   (90 invoices)
    SCW-COM  2026-06-01                        2026-06-01   (4 invoices)
    RES-STD  2026-08-01                        — never billed
    COM-SM   2026-08-01                        — never billed
    IND      2026-08-01                        — never billed

The two plans that have actually billed customers get **exactly the day their
first billed period starts**. That is the check that makes this the right rule
rather than a plausible one: the date is derived from the utility's own prices
and lands on the day the plan demonstrably began pricing.

**The alternatives, and why each was rejected:**

* **Today (2026-08-28).** SCW-RES has 90 issued invoices whose earliest service
  period starts 2026-06-01. Stamping today would put every one of those bills
  OUTSIDE its own plan's effective window — the ruled path would then refuse to
  explain a bill the utility has already sent and been paid for. That is the
  decision log's own objection: *"picking today restates history."*
* **The epoch, or `rate_plans.created_at`.** Both claim the plan priced periods
  it never priced. On the seeded tenant `created_at` is today for all five rows,
  so it is *also* wrong in the other direction here — but on a migrated tenant it
  would be a draft's first keystroke, months before anything was publishable.
* **The publish date** (`plan_versions` v1, BR-RAT-111). Honest about
  assignability and WRONG about pricing: the seeded plans were published today
  and have June invoices, so it reproduces the "today" failure exactly.

**Fallbacks, in order, and each one is narrower than the last:** the earliest
dated version of a bound schedule → the v1 filing record's date (the day the
plan was published, BR-RAT-111) → `rate_plans.created_at`. A published plan
always has a bound schedule (`publish_plan` refuses otherwise), so the second
and third only reach a plan whose schedules carry no activated version at all.

⚠ **NOTHING ALREADY ISSUED CHANGES — HARD RULE 4, AND IT IS PROVABLE HERE**
---------------------------------------------------------------------------
This migration touches the `rate_plans` table and nothing else. It writes no
`invoices` row, no `invoice_lines` row, no `payments` row and no journal line.

And the change cannot re-price a bill even indirectly: the LIVE path
(`selectors.plan_ref`, `billing/gather.py`) does not read `effective_from` at
all, so on every code path that prices a bill today this column is inert. The
RULED path does read it — and `resolution_switch.apply()` is switched on
nowhere (`SBH_BILLING_RESOLUTION_STEPS` is empty on every deployment), and R1
has no fork in any case. An issued bill keeps the money it was issued with; a
utility that wants one re-priced does that as a CORRECTION — new rows, never an
edit.

⚠ **HARD RULE 1 IS OBEYED ROW BY ROW.** `rate_plans` is a tenant table with
ENABLE + FORCE row-level security, so under a non-superuser application role a
bare `UPDATE` here matches ZERO rows and reports success — the quietest failure
there is. This walks the RLS-exempt `tenants` table and sets `app.tenant_id`
before touching anything, the shape `assets/0003` established and `rating/0023`
followed, and leaves the nil sentinel behind rather than `''`.

⚠ **NO `audit_log` ROW IS WRITTEN, and that is `rating/0023`'s decision kept.**
`audit_log` is RANGE-partitioned by month and an INSERT from inside a schema
migration fails on a host whose current-month partition does not exist yet,
which turns a data fix into a failed deploy. The record of this act is the
migration — in git, in `django_migrations`, in the decision log and in the
review ledger — and the RunPython PRINTS every plan it dated, with the date and
where the date came from, so an operator sees it happen.

⚠ **NO ❄️ FROZEN FIGURE MOVES.** B4 and B5 say nothing about plan effective
dates (grepped). `10-scripts/03-golden-verify.py` reads 33 PASS / 0 FAIL before
and after.
"""

from django.db import migrations

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


def _date_for(apps, plan):
    """The date this plan has been in force since, and where it came from.

    Returns `(date, provenance)`. Never returns None: the last fallback is the
    plan's own creation date, which every row has.
    """
    PlanRateSchedule = apps.get_model("rating", "PlanRateSchedule")
    TariffVersion = apps.get_model("rating", "TariffVersion")
    PlanVersion = apps.get_model("rating", "PlanVersion")

    tariff_ids = list(
        PlanRateSchedule.objects.filter(tenant_id=plan.tenant_id, rate_plan_id=plan.id).values_list(
            "tariff_id", flat=True
        )
    )
    if tariff_ids:
        # ACTIVATED versions only. BR-RAT-031: a NULL `effective_from` on
        # `tariff_versions` IS the resumable draft — it has never priced
        # anything, so it cannot date a plan.
        earliest = (
            TariffVersion.objects.filter(
                tenant_id=plan.tenant_id,
                tariff_id__in=tariff_ids,
                effective_from__isnull=False,
            )
            .order_by("effective_from")
            .values_list("effective_from", flat=True)
            .first()
        )
        if earliest is not None:
            return earliest, "its earliest bound rate-schedule version"

    # BR-RAT-111 — v1 is written at PUBLISH, so its row is the day this plan
    # became assignable. UTC calendar date: a plan effective date is a CALENDAR
    # date (BR-SHL-023 — the same date in every tenant), and the only drift this
    # can produce is one day LATE for an evening publish, which the ruled path
    # answers with a loud refusal rather than a quiet price.
    published = (
        PlanVersion.objects.filter(tenant_id=plan.tenant_id, rate_plan_id=plan.id, version_no=1)
        .values_list("created_at", flat=True)
        .first()
    )
    if published is not None:
        return published.date(), "the day it was published (its v1 filing record)"
    return plan.created_at.date(), "the day it was created"


def state_when_every_published_plan_started(apps, schema_editor):
    """Every `rate_plans` row that is PUBLISHED and undated gets its date.

    Per tenant, under that tenant's own RLS context. Idempotent: a second run
    finds nothing, because every row it touched now states a date. DRAFT and
    ARCHIVED plans are left alone — a draft with no date is exactly what a draft
    is (BR-RAT-031's save-and-come-back), and an archived plan is withdrawn and
    assigns to nobody, so dating it would invent a fact about a plan nobody can
    put an account on.
    """
    RatePlan = apps.get_model("rating", "RatePlan")
    connection = schema_editor.connection
    tenants, changed = 0, 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        undated = list(
            RatePlan.objects.filter(
                tenant_id=tenant_id, status="published", effective_from__isnull=True
            )
        )
        if not undated:
            continue
        tenants += 1
        for plan in undated:
            stated, provenance = _date_for(apps, plan)
            RatePlan.objects.filter(pk=plan.pk).update(effective_from=stated)
            changed += 1
            print(f"    {plan.code}: effective from {stated.isoformat()} — {provenance}")
    _leave_tenant(connection)
    print(
        f"  rating 0024 (DEF-494): {changed} published plan(s) across {tenants} tenant(s) now "
        f"state a start date. Nothing already issued changes (hard rule 4): the live pricing "
        f"path does not read this column and the ruled path is switched on nowhere."
    )


def _irreversible_by_construction(apps, schema_editor):
    """Deliberately a NO-OP, not a blanking.

    Reversing this would have to set `effective_from` back to NULL — and after
    it has run there is no way to tell a row THIS dated from a row a utility
    dated itself. Blanking them all would recreate, silently, the exact state
    the PO ruled out of existence. There is nothing to undo in the schema: this
    migration alters no column.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0023_def652_discount_treatment_after"),
        # `tenants` is walked to set RLS context per tenant.
        ("tenancy", "0016_br_rat_081_service_metered"),
    ]

    operations = [
        migrations.RunPython(
            state_when_every_published_plan_started,
            _irreversible_by_construction,
        ),
    ]
