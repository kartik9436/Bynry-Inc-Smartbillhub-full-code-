"""work 0060 — a work-order template says what the CUSTOMER should prepare,
and whether its jobs send the customer visit messages at all.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-29 (`DEF-WRK-10652`) under the PO
ruling of 2026-08-09; its row is in `12-governance/09-human-review-ledger.md`.

WHAT IT DOES
------------
PO 2026-10-29, *"1A 2A 3B 4A, start"* (decision log, same date):

* **3B** — `wot_details.prep_instructions` and `work_order_details.
  prep_instructions` (text, NULL = blank): the template's preparation text,
  copied onto the job at raise (`BR-WRK-008`); and `work_settings.
  visit_prep_default` (text, NULL reads the PO's seeded sentence).
* **4A** — `wot_details.send_customer_visit_messages` and the same on
  `work_order_details` (boolean, DEFAULT TRUE — hard-won law 3 is not at stake
  here: ON is what every template did before this column existed, so nothing
  changes for a utility that never touches it).

THE DATA HALF: the SAMPLE disconnect / reconnect templates (`is_sample`, type
`DISCONNECT_RECONNECT` — the seeder's own identification of the rows it
planted, never a runtime test of a type name) get the switch OFF, per tenant
under its own `app.tenant_id` (`wot_details` and `work_order_templates` carry
ENABLE + FORCE). A template with no `wot_details` row gets one, so the switch
has somewhere to live. A template a utility made itself is not touched.

No RLS change: every column joins a table that already has its policy.

ROLLBACK
--------
`migrate work 0059` drops the five columns; the switch-off is lost with them,
which is correct — before this migration nothing could switch a message off.
"""

from django.db import migrations, models

DISCONNECT_TYPE_CODE = "DISCONNECT_RECONNECT"


def _apply_tenant(apps_registry, tenant_id) -> int:
    Template = apps_registry.get_model("work", "WorkOrderTemplate")
    Detail = apps_registry.get_model("work", "WorkOrderTemplateDetail")
    ids = list(
        Template.objects.filter(
            tenant_id=tenant_id, is_sample=True, type__code=DISCONNECT_TYPE_CODE
        ).values_list("id", flat=True)
    )
    for template_id in ids:
        Detail.objects.update_or_create(
            tenant_id=tenant_id,
            template_id=template_id,
            defaults={"send_customer_visit_messages": False},
        )
    return len(ids)


def switch_off_sample_disconnects(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    written = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            written += _apply_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if written:
        print(
            f"DEF-WRK-10652: {tenants} tenant(s) — {written} sample disconnect/reconnect "
            "template(s) set to send no customer visit messages (PO 2026-10-29, ruling 4A)"
        )


def undo(apps_registry, schema_editor):
    """Nothing to undo row by row: reversing the AddField drops the column."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0059_fb013_outcome_not_done_paid"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="prep_instructions",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertemplatedetail",
            name="send_customer_visit_messages",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="workorderdetail",
            name="prep_instructions",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorderdetail",
            name="send_customer_visit_messages",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="worksettings",
            name="visit_prep_default",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(switch_off_sample_disconnects, undo),
    ]
