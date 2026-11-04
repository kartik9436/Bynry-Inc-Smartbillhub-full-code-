"""rating 0068 — a charge code may be marked as the returned-payment (NSF) fee.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering on a money path (the
NSF penalty a bounce charges). Row in `12-governance/09-human-review-ledger.md`
(*"2026-10-30 · THE NSF PENALTY IS CHARGED ON A BOUNCE"*).

WHY. PO 2026-10-30, verbatim: *"Do not hardcode check NSF Account> Unit> Plan>
Charge code"* (decision log, *"The NSF penalty is charged on a bounce"*). A
bounce walks the account to its unit, the unit to its plan, and charges the
plan's NSF code. Which of a plan's codes IS the NSF fee is DECLARED on the code
(`is_base`'s reasoning: never inferred from a code string at run time).

WHAT IT CHANGES
1. `charges.is_nsf_fee` boolean, NOT NULL DEFAULT FALSE.
2. A ONE-TIME BACKFILL: every live `penalty` code whose code is exactly `NSF`
   — the code `lookup_defaults.json` has provisioned on every tenant since W0 —
   is marked. That is the platform's own seeded row, read once here, exactly
   as `rating/0027` backfilled the seeded `LATE` as each plan's late fee; no
   code path reads the string afterwards. A tenant that renamed its code is
   not guessed at: it marks its own on Settings › Charge codes.

DOWN PATH: drop the column; bounces go back to charging no NSF fee and every
fee bill already raised stays exactly as issued (hard rule 4).
"""

from django.db import migrations, models

#: The all-zero uuid the database defaults `app.tenant_id` to (`rating/0027`).
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _set_tenant(connection, tenant_id):
    """CLAUDE.md hard rule 1 — `charges` is RLS FORCE, so the backfill walks
    the tenants (an RLS-exempt platform table) and SEES each one's rows under
    its own `app.tenant_id`, exactly as `rating/0027` does. sqlite has no RLS."""
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def mark_seeded_nsf(apps, schema_editor):
    Charge = apps.get_model("rating", "Charge")
    Tenant = apps.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    try:
        for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
            _set_tenant(connection, tenant_id)
            Charge.objects.filter(
                tenant_id=tenant_id,
                code="NSF",
                charge_type="penalty",
                deleted_at__isnull=True,
                is_base=False,
            ).update(is_nsf_fee=True)
    finally:
        _set_tenant(connection, NO_TENANT)


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0067_def_cus_9819_application_fee_code"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="charge",
            name="is_nsf_fee",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_seeded_nsf, migrations.RunPython.noop),
    ]
