# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the DATA half.
# Rules:   PO 2026-10-03 rulings 1 (approved = live on its start date) and the
#          three dropdowns · CR-166 §7 open items 1 (`assistance`, ruled 2026-10-03),
#          2 and 3 (our judgment on today's free text) · CLAUDE.md hard rule 1
#          (`app.tenant_id` set per tenant — RLS FORCE)
# ───────────────────────────────────────────────────────
"""rating 0060 — seed the drawn lists, map today's free text, and put every
approved version in force.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering, and a money path:
step 4 decides which version prices a date). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-03, CR-166-BRC10 r2 t3.

For every utility, with `app.tenant_id` set to it (hard rule 1):

1. **Seed** the drawing's values — 8 program owners, 6 exclusivity groups
   (with *None*), 11 who-qualifies in two groups. Insert-missing.
2. **Program owner** — `discounts.programme_owner` free text becomes the CODE
   of the list value that means it (`discount_lists.map_or_add`). A value that
   matches no drawn label is ADDED to that utility's own list, verbatim
   (`CR-166` §7 item 2): *City assistance programme* stays *City assistance
   programme*, it is not rewritten to *City or county agency*.
3. **Exclusivity group** — the same, and ⚖️ **RULED (PO 2026-10-03, *"A Keep
   them excluding each other, so the customer gets one of the two"*)**:
   `assistance` becomes ONE shared group of the utility's own list, code
   `assistance`, label *Assistance programs* — never a drawn group — so CAP
   and SENIOR keep excluding each other and stacking moves by no cent.
4. **Who qualifies** — `eligibility_summary` is LEFT as written and
   `eligibility_code` is filled beside it: the six shipped phrases map to the
   drawn values (§7 item 3); anything else is added as a *customer shows proof*
   value.
5. **Approved is live (ruling 1).** A version left `scheduled` — approved and
   never activated, which ruling 1 says should have been pricing from its start
   date — is put `active`, after closing the open window of every older active
   version the day before it starts (the same act approval now performs). One
   that would still overlap an active window is LEFT `scheduled` and printed,
   never forced: an overlap is two versions on one date, and choosing which
   one a past bill should have used is not a migration's call.
6. **Currency** — any version whose currency is not the utility's own is
   PRINTED, never rewritten (`CR-166` §6 b).

DOWN PATH: `noop`. The codes stay in the free-text columns (they are readable
words like `customer_service`); a version put in force stays in force. Reverse
0059 to drop the list table.
"""

from datetime import timedelta

from django.db import migrations

from apps.rating import discount_lists

NO_TENANT = ""
LIST_PROGRAM_OWNER = "program_owner"
LIST_EXCLUSIVITY_GROUP = "exclusivity_group"
LIST_ELIGIBILITY = "eligibility"


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _overlaps(a_from, a_to, b_from, b_to):
    far = a_from.replace(year=9999)
    return a_from <= (b_to or far) and b_from <= (a_to or far)


def _put_approved_in_force(DiscountVersion, Discount, tenant_id, report):
    pending = DiscountVersion.objects.filter(
        tenant_id=tenant_id, status="scheduled", effective_from__isnull=False
    ).order_by("discount_id", "effective_from", "version_no")
    for version in pending:
        start = version.effective_from
        DiscountVersion.objects.filter(
            tenant_id=tenant_id,
            discount_id=version.discount_id,
            status="active",
            effective_from__lt=start,
            effective_to__isnull=True,
        ).update(effective_to=start - timedelta(days=1))
        clash = [
            other.version_no
            for other in DiscountVersion.objects.filter(
                tenant_id=tenant_id, discount_id=version.discount_id, status="active"
            ).exclude(pk=version.pk)
            if other.effective_from
            and _overlaps(start, version.effective_to, other.effective_from, other.effective_to)
        ]
        if clash:
            report.append(
                f"  discount {version.discount_id} v{version.version_no}: LEFT scheduled — "
                f"its window overlaps active v{clash}"
            )
            continue
        DiscountVersion.objects.filter(pk=version.pk).update(status="active")
        Discount.objects.filter(pk=version.discount_id, status="draft").update(status="active")
        report.append(
            f"  discount {version.discount_id} v{version.version_no}: approved → in force "
            f"from {start}"
        )


def _forwards(apps, schema_editor):
    Tenant = apps.get_model("tenancy", "Tenant")
    Discount = apps.get_model("rating", "Discount")
    DiscountVersion = apps.get_model("rating", "DiscountVersion")
    ListValue = apps.get_model("rating", "DiscountListValue")
    connection = schema_editor.connection
    report: list[str] = []
    for tenant_id, currency in list(Tenant.objects.values_list("id", "currency")):
        _set_tenant(connection, tenant_id)
        discount_lists.seed_lists(tenant_id=tenant_id, model=ListValue)
        for discount in Discount.objects.filter(tenant_id=tenant_id):
            code = discount_lists.map_or_add(
                LIST_PROGRAM_OWNER, discount.programme_owner, tenant_id=tenant_id, model=ListValue
            )
            if code != discount.programme_owner:
                Discount.objects.filter(pk=discount.pk).update(programme_owner=code)
        for version in DiscountVersion.objects.filter(tenant_id=tenant_id):
            updates = {}
            group = discount_lists.map_or_add(
                LIST_EXCLUSIVITY_GROUP,
                version.exclusivity_group,
                tenant_id=tenant_id,
                model=ListValue,
            )
            if group != version.exclusivity_group:
                updates["exclusivity_group"] = group
            if not version.eligibility_code and version.eligibility_summary:
                updates["eligibility_code"] = discount_lists.map_or_add(
                    LIST_ELIGIBILITY,
                    version.eligibility_summary,
                    tenant_id=tenant_id,
                    model=ListValue,
                )
            if updates:
                DiscountVersion.objects.filter(pk=version.pk).update(**updates)
            if currency and version.currency and version.currency != currency:
                report.append(
                    f"  tenant {tenant_id} discount {version.discount_id} v{version.version_no}: "
                    f"currency {version.currency} is not the utility's {currency} — NOT rewritten"
                )
        _put_approved_in_force(DiscountVersion, Discount, tenant_id, report)
    _set_tenant(connection, NO_TENANT)
    if report:
        print("\n[rating 0060 · CR-166-BRC10]\n" + "\n".join(report))


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0059_cr166_discount_lists_and_retire"),
    ]

    operations = [migrations.RunPython(_forwards, migrations.RunPython.noop)]
