"""customers 0087 — the staff service request keeps every customer-form value.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-18 by lane CF-1 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

Decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS THE CREATE
SCREENS, MOVE-IN AS THE REFERENCE"*: every create screen uses Move-in's
customer form and *"saves everything it asks"*. On `service_requests`:

  * **mailing address** — `mailing_same` + five parts, the name every other
    screen uses (`customers.addresses` `kind='mailing'`);
  * **`tax_id`** — `DEF-CUS-10223`, encrypted (`EncryptedTextField`, context
    `service_requests.tax_id`);
  * **`gov_id_last4`**, **`contact_by`** — Move-in's Identity and Who fields;
  * **`co_applicants`** — the full co-applicant cards (JSON; SSN and licence
    held as `core.crypto` ciphertext inside each row, never in the clear);
  * **`paperless`**, **`sms_reminders`** — the request's Preferences.

**THE DATA STEP COPIES, IT DELETES NOTHING.** Every request's
`billing_address_same` becomes `mailing_same`, and its `billing_*_as_given`
parts become the mailing parts. A request holding only the old one-box
`billing_address_as_given` (written before `DEF-CUS-6408`) has that box copied
into `mailing_line1`, so the words are not lost. The `billing_*` columns are
left exactly as written; readers fall back to them where a mailing part is
empty (`service_request_reads._mailing_parts`). Each tenant is visited under
its own `app.tenant_id` (hard rule 1 — `service_requests` is FORCE RLS), and a
second run writes nothing it has not already written (a row whose mailing
parts are filled is skipped).

REVERSE: the schema half drops the new columns (the copied values are copies);
the data half is a stated no-op.
"""

from django.db import migrations, models

import core.crypto

PARTS = (
    ("mailing_line1", "billing_line1_as_given"),
    ("mailing_line2", "billing_line2_as_given"),
    ("mailing_city", "billing_city_as_given"),
    ("mailing_state", "billing_state_as_given"),
    ("mailing_postal_code", "billing_postal_code_as_given"),
)


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def copy_billing_to_mailing(apps_registry, schema_editor):
    """Per tenant, under its own GUC: copy the billing answer to mailing."""
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    ServiceRequest = apps_registry.get_model("customers", "ServiceRequest")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"
    arrival = ""
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0] or ""
    copied = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
            rows = ServiceRequest.objects.filter(tenant_id=tenant_id).only(
                "id",
                "billing_address_same",
                "billing_address_as_given",
                *[old for _, old in PARTS],
                *[new for new, _ in PARTS],
                "mailing_same",
            )
            for row in rows.iterator():
                if any(not _blank(getattr(row, new)) for new, _ in PARTS):
                    continue  # already written — by a capture or an earlier run
                changes = {"mailing_same": bool(row.billing_address_same)}
                for new, old in PARTS:
                    value = getattr(row, old)
                    if not _blank(value):
                        changes[new] = value
                if "mailing_line1" not in changes and not _blank(row.billing_address_as_given):
                    changes["mailing_line1"] = row.billing_address_as_given
                if changes == {"mailing_same": True} and row.mailing_same is True:
                    continue
                ServiceRequest.objects.filter(pk=row.pk).update(**changes)
                copied += 1
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])
    if copied:
        print(f"\n    customers.0087: {copied} request(s) given their mailing address")


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0086_def_cus_10161_temporary_stop_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_same",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_line1",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_line2",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_city",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_state",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="mailing_postal_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="tax_id",
            field=core.crypto.EncryptedTextField(
                blank=True, null=True, crypto_context="service_requests.tax_id"
            ),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="gov_id_last4",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="contact_by",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="co_applicants",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="paperless",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="servicerequest",
            name="sms_reminders",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_billing_to_mailing, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-10223 · DEF-CUS-10225 · decision log 2026-10-18 (customer
#         data and UI consistent across the create screens) · hard rules 1, 8
# generated: 2026-10-18 by lane CF-1
# gates: pytest tests/test_cf1_customer_forms_2026_10_18.py (PostgreSQL 16) ·
#        makemigrations --check --dry-run
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
