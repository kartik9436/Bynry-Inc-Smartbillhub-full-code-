"""rating 0066 — the late-fee GRACE moves onto the penalty charge code.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering on a ❄️ FROZEN B4/B5
money path (the late fee). Finance RE-SIGN owed (HUMAN-GUIDE §6); row in
`12-governance/09-human-review-ledger.md` (*"2026-10-06 · LATE-FEE GRACE ON THE
CHARGE CODE"*).

WHY. PO ruling 2026-10-06 11 (a), verbatim: *"Put grace on the late-fee code.
When Type is Penalty, the form asks Grace days (default 5) and Calendar /
Business days, and billing uses the code's grace. The Settings default stays as
the starting value for new codes."*

WHAT IT CHANGES
1. `charges.grace_days` (0–30, BR-BIL-008) and `charges.grace_mode`
   (`calendar` | `business`, BR-BIL-002), both nullable, each with a CHECK.
2. **Every existing PENALTY code is seeded with its utility's CURRENT grace**
   (`tenant_settings.late_grace_days/late_grace_mode`, 5 / calendar where the
   utility never set one — the Billing-defaults screen's own defaults). So the
   grace billing reads on the first run after deploy is the grace it read the
   run before: no customer's late-fee date moves. Non-penalty codes stay NULL.

Each utility is walked with `app.tenant_id` set to it (hard rule 1; RLS is FORCE
on `charges`). The arithmetic is untouched — GT-8's $8.13 reads no database.

DOWN PATH. Drop the two constraints and the two columns. Billing then reads the
tenant default again, which is exactly what the seeded values were.
"""

from django.db import migrations, models
from django.db.models import Q

NO_TENANT = ""
DEFAULT_DAYS = 5  # settings_families.BILLING_DEFAULTS `late_grace_days`
DEFAULT_MODE = "calendar"  # settings_families.BILLING_DEFAULTS `late_grace_mode`


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _seed(apps, schema_editor):
    connection = schema_editor.connection
    Tenant = apps.get_model("tenancy", "Tenant")
    TenantSettings = apps.get_model("tenancy", "TenantSettings")
    Charge = apps.get_model("rating", "Charge")
    report = []
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _set_tenant(connection, tenant_id)
        row = TenantSettings.objects.filter(tenant_id=tenant_id).first()
        days = row.late_grace_days if row is not None and row.late_grace_days is not None else DEFAULT_DAYS
        mode = row.late_grace_mode if row is not None and row.late_grace_mode else DEFAULT_MODE
        count = Charge.objects.filter(
            tenant_id=tenant_id, charge_type="penalty", grace_days__isnull=True
        ).update(grace_days=days, grace_mode=mode)
        if count:
            report.append(f"  {tenant_id}: {count} penalty code(s) seeded with {days} {mode} day(s)")
    _set_tenant(connection, NO_TENANT)
    if report:
        print("\n[rating 0066 · late-fee grace on the charge code]\n" + "\n".join(report))


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0065_def_2430_discount_grant_reversal"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="charge",
            name="grace_days",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="charge",
            name="grace_mode",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="charge",
            constraint=models.CheckConstraint(
                condition=Q(grace_days__isnull=True) | Q(grace_days__gte=0, grace_days__lte=30),
                name="ck_charges_grace_days_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="charge",
            constraint=models.CheckConstraint(
                condition=Q(grace_mode__isnull=True) | Q(grace_mode__in=("calendar", "business")),
                name="ck_charges_grace_mode",
            ),
        ),
        migrations.RunPython(_seed, migrations.RunPython.noop),
    ]
