"""identity 0009 — `DEF-IDN-9748`: every existing field technician signs in on the field app.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-05 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHAT IT REPAIRS
───────────────
`OQ-WRK-1494` (PO 2026-09-04, verbatim: *"Field technicians will not logn to
web app; they will login to mobile app only"*) is enforced by `sign_in` reading
`users.surface_scope`. Until 2.548.2 the Settings › Users service (`add_user`)
and the role change (`update_user`) never set that column, so every technician
a utility added for itself kept the default `both` and could open the staff web
app, which then dead-ended on *"We couldn't load your regional settings."*
(customer report, sandbox, 2026-10-05). The services now derive the scope from
the role; THIS moves the logins already written.

WHO IS TOUCHED, AND NOBODY ELSE: a login whose membership role is
`field_technician` and whose scope is exactly `both`. A technician already on
`mobile` is left alone (the four demo technicians are); an office login is
never read; a technician somebody deliberately scoped `web` is left alone too,
because that is a choice somebody typed and not the default this repairs.

⚠ **ONE TENANT AT A TIME, WITH `app.tenant_id` SET — `0008`'s SHAPE, FOLLOWED.**
`users` and `tenant_memberships` are `ENABLE` + `FORCE ROW LEVEL SECURITY`. On a
real deployment the migrating role is not a superuser, holds no `BYPASSRLS` and
arrives with `app.tenant_id` at the nil UUID, so ONE query across all tenants
finds nothing, moves nobody and prints a zero (`DEF-IDN-7504`, `DEF-RAT-5799`).
So this iterates the `tenants` table (a platform table, no tenant policy) and
enters each utility's context before it reads that utility's rows.

⚠ **THE GUC IS RESTORED TO WHAT IT WAS ON ARRIVAL, NEVER CLEARED TO `''`** —
`0008`'s reason: a leftover `''` poisons later migrations on the connection.

⚠ **NO `try/except` AROUND A WRITE (hard-won law 14).** If a statement fails,
the migration fails.

Each moved login writes one `user.surface_scope_changed` audit row
(`before: both`, `after: mobile`, unnamed system job — BR-AUD-003), and the
count is PRINTED, because a person watches `migrate` and the count is the
figure to report.

REVERSING IT: `noop`, deliberately. Moving these logins back to `both` would
re-open the staff web app to field technicians — the exact defect, against a
standing PO ruling — and the forward step is idempotent, so migrating back past
this and forward again moves nobody twice. The audit rows record who was moved.
"""

from django.db import migrations

#: Re-declared rather than imported: a migration must keep meaning what it
#: meant when the live constants move on.
FIELD_TECHNICIAN = "field_technician"
FROM_SCOPE = "both"
TO_SCOPE = "mobile"
ACTION = "user.surface_scope_changed"


def technicians_to_the_field_app(apps, schema_editor):
    from core import audit as core_audit
    from core import tenancy as core_tenancy

    Tenant = apps.get_model("tenancy", "Tenant")
    User = apps.get_model("identity", "User")
    TenantMembership = apps.get_model("identity", "TenantMembership")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    moved = []
    try:
        for tenant_id in Tenant.objects.order_by("id").values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            # `write_row` stamps the tenant from the Python mirror, and RLS
            # reads the GUC; both must name this utility.
            token = core_tenancy._current_tenant.set(core_tenancy._as_uuid(tenant_id))
            try:
                technician_ids = TenantMembership.objects.filter(
                    tenant_id=tenant_id, role__code=FIELD_TECHNICIAN
                ).values_list("user_id", flat=True)
                for user in User.objects.filter(
                    tenant_id=tenant_id, pk__in=list(technician_ids), surface_scope=FROM_SCOPE
                ).order_by("id"):
                    User.objects.filter(pk=user.pk).update(surface_scope=TO_SCOPE)
                    core_audit.write_row(
                        action=ACTION,
                        entity_type="user",
                        entity_id=user.id,
                        actor_user_id=None,  # BR-AUD-003's unnamed system job
                        before={"surface_scope": FROM_SCOPE},
                        after={"surface_scope": TO_SCOPE},
                    )
                    moved.append((str(tenant_id), str(user.id)))
            finally:
                core_tenancy._current_tenant.reset(token)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    # PRINTED, not logged — `0008`'s reason: a person watches `migrate`.
    print(
        f"DEF-IDN-9748 (per tenant): {len(moved)} field technician login(s) moved "
        f"from '{FROM_SCOPE}' to '{TO_SCOPE}' (field app only)."
    )
    for tenant_id, user_id in moved:
        print(f"  {tenant_id}: user {user_id}")
    return moved


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0008_cr145_withdraw_long_timeouts_per_tenant"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(technicians_to_the_field_app, migrations.RunPython.noop),
    ]
