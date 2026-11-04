"""work 0064 — the work-order template's Reconnect limit (FB-028).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-31 (FB-028) under the PO ruling of
2026-08-09; its row is in `12-governance/09-human-review-ledger.md`.

WHAT IT DOES
------------
PO 2026-10-31, verbatim: *"the 25 $ limit should be part of work order
template when payment check is included in work order template and it should
not be part of settings"* (decision log, *"Field-raised disconnects go to the
technician with the live checks; the reconnect limit lives on the work-order
template"*). Two NUMERIC(18,4) columns, NULL by default (hard rule 2: money is
stored to 4 places):

* `wot_details.reconnect_limit` — the template's limit;
* `work_order_details.reconnect_limit` — the job's own copy (`BR-WRK-008`,
  `order_copies`).

DATA STEP: a template that ALREADY has a payment check (any `wot_tasks` row
with `money_fresh_minutes`) gets **25.0000**, the PO's figure, so the gate a
raised reconnect meets on day one is the one the PO named rather than none.
Templates with no payment check stay NULL. Jobs already raised are left alone
(their copy was taken before the limit existed; a NULL limit gates nothing).

ROLLBACK
--------
`migrate work 0063` drops both columns; a raised reconnect then meets no limit
on the phone (the step reads the balance and shows it, as before FB-028).
"""

from decimal import Decimal

from django.db import migrations, models

DEFAULT_LIMIT = Decimal("25.0000")


def seed_limit(apps, schema_editor):
    Detail = apps.get_model("work", "WorkOrderTemplateDetail")
    Task = apps.get_model("work", "WorkOrderTemplateTask")
    checked = Task.objects.filter(money_fresh_minutes__isnull=False).values("template_id")
    Detail.objects.filter(template_id__in=checked, reconnect_limit__isnull=True).update(
        reconnect_limit=DEFAULT_LIMIT
    )


class Migration(migrations.Migration):
    dependencies = [
        ("work", "0063_rls_force_fb033_availability"),
    ]

    operations = [
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="reconnect_limit",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="workorderdetail",
            name="reconnect_limit",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.RunPython(seed_limit, migrations.RunPython.noop),
    ]
