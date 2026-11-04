"""rating 0063 — every plan's CURRENT content becomes its head version, and every
binding row points at it (`BR-RAT-1066`; `CR-167-BRC10` §9). Also removes base
charge codes stored as plan charge codes (`DEF-RAT-9337`).

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering, a money path). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-03, CR-167-BRC10 r2 t3.

For every utility, with `app.tenant_id` set to it (hard rule 1), for every plan:

1. **The head.** The plan's current filing row — `version_no = rate_plans.version`,
   not superseded by a correction — or, where none exists (a draft plan, or one
   published before `BR-RAT-111`), a new row carrying that number and an empty
   snapshot. The head takes the plan's window (`effective_from/to`), its four
   terms (`minimum_bill_amount`, `outside_city_factor`, `budget_billing`,
   `late_fee_charge_id`) and its status (`draft` for a draft plan, else
   `published`). `rate_plans.head_version_id` points at it.
2. **Every other filing row becomes `history`.** They are the in-place version
   bumps written before the plan had dates (v1, v2 … of a plan whose content
   then moved on) and corrected rows; none of them ever owned a set of bindings,
   so none of them can price. Their snapshots, reasons and authors are kept.
3. **Every binding row** (`plan_services`, `plan_rate_schedules`,
   `plan_charge_rules`, `plan_tax_rules`, `plan_discount_rules`) gets the head.

**NO FIGURE MOVES, AND WHY THAT FOLLOWS:** before this migration a plan had ONE
set of bindings; after it the same rows belong to ONE version, which is the
version every read falls back to (`plan_versioning`), and the four terms on
`rate_plans` are unchanged. Proved by a before/after bill comparison on
PostgreSQL (`10-scripts/cr167_task3_bill_compare_pg.py`).

4. **`DEF-RAT-9337`** — a `plan_charge_rules` row whose code `is_base` is
   deleted. Measured harmless on the bill (`billable_charge_codes` already
   drops every base code — `$154.50` with and without, `CR-167-BRC10` §7.1 (a));
   the base reaches the bill through the rate schedule. Each deletion is
   printed with the plan and the code.

DOWN PATH: no-op (the columns are dropped by reversing 0062). A deleted
`DEF-RAT-9337` row is not restored; it billed nothing and is printed here.
"""

from django.db import migrations

NO_TENANT = ""
BINDINGS = ("PlanService", "PlanRateSchedule", "PlanChargeRule", "PlanTaxRule")


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _forwards(apps, schema_editor):
    connection = schema_editor.connection
    Tenant = apps.get_model("tenancy", "Tenant")
    RatePlan = apps.get_model("rating", "RatePlan")
    PlanVersion = apps.get_model("rating", "PlanVersion")
    PlanChargeRule = apps.get_model("rating", "PlanChargeRule")
    PlanDiscountRule = apps.get_model("rating", "PlanDiscountRule")
    models = [apps.get_model("rating", name) for name in BINDINGS] + [PlanDiscountRule]
    report = []
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _set_tenant(connection, tenant_id)
        for plan in RatePlan.objects.filter(tenant_id=tenant_id).order_by("code"):
            head = (
                PlanVersion.objects.filter(
                    tenant_id=tenant_id,
                    rate_plan_id=plan.id,
                    version_no=plan.version,
                    superseded_by__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )
            terms = {
                "minimum_bill_amount": plan.minimum_bill_amount,
                "outside_city_factor": plan.outside_city_factor,
                "budget_billing": plan.budget_billing,
                "late_fee_charge_id": plan.late_fee_charge_id,
                "effective_from": plan.effective_from,
                "effective_to": plan.effective_to,
                "status": "draft" if plan.status == "draft" else "published",
            }
            if head is None:
                head = PlanVersion.objects.create(
                    tenant_id=tenant_id,
                    rate_plan_id=plan.id,
                    version_no=plan.version or 1,
                    snapshot={"recorded_by": "rating/0063"},
                    **terms,
                )
                report.append(f"  {plan.code}: v{head.version_no} filed by 0063 (no row)")
            else:
                PlanVersion.objects.filter(pk=head.pk).update(**terms)
            PlanVersion.objects.filter(tenant_id=tenant_id, rate_plan_id=plan.id).exclude(
                pk=head.pk
            ).update(status="history")
            RatePlan.objects.filter(pk=plan.id).update(head_version_id=head.pk)
            for model in models:
                model.objects.filter(tenant_id=tenant_id, rate_plan_id=plan.id).update(
                    plan_version_id=head.pk
                )
        base_rows = PlanChargeRule.objects.filter(tenant_id=tenant_id, charge__is_base=True)
        for row in base_rows.select_related("rate_plan", "charge"):
            report.append(
                f"  DEF-RAT-9337: {row.rate_plan.code} no longer lists base code "
                f"{row.charge.code} as a charge code"
            )
        base_rows.delete()
    _set_tenant(connection, NO_TENANT)
    if report:
        print("\n[rating 0063 · CR-167-BRC10]\n" + "\n".join(report))


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0062_cr167_plan_version_windows"),
    ]

    operations = [migrations.RunPython(_forwards, migrations.RunPython.noop)]
