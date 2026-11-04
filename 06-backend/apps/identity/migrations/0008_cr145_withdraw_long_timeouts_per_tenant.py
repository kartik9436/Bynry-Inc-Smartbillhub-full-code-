"""identity 0008 — `CR-145-BRC08`: the 240/480 withdrawal, done so that RLS lets it happen.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-28 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

⚠ **WHY THERE IS A SECOND MIGRATION FOR ONE RULING (`DEF-IDN-7504`).**
`0007` reads every utility's `security_policies` row in ONE query before it
sets any tenant context — it sets context only around the audit write. That
table is `ENABLE` + `FORCE ROW LEVEL SECURITY`, and on a real deployment the
role that runs `migrate` owns the tables, is not a superuser, holds no
`BYPASSRLS` (the PO ruled the grant out) and starts with `app.tenant_id` set to
the nil UUID, which matches no row (`09-infra/01-deployment-architecture.md`
§Step 0). So there `0007` finds nothing, moves nobody, and prints
*"CR-145: 0 utility(ies) moved"* — the very figure the PO asked to be given.
Its tests passed because the test role is a superuser, which is the one role
for which the bug cannot exist.

**This migration does the same job one tenant at a time**, iterating the
`tenants` table (a platform table with no tenant policy — B2's *"No RLS
(platform)"* list) and entering each utility's context before it reads that
utility's row: `tenancy/0043`'s shape, followed rather than re-derived.

⚠ **`0007` IS LEFT EXACTLY AS IT WAS.** The repository's migrations are
append-only (`.github/workflows/migration-guard.yml`), and `0007` is already on
the main line. Where it ran as a superuser — a developer's database, a test
database — it moved the rows and this one finds none. Where it ran as the real
migrating role it moved none and this one moves them. **Either way each row is
moved exactly once**, because this one only ever looks for rows still holding
240 or 480.

⚠ **SO THE PO'S NUMBER IS THE SUM OF THE TWO PRINTED LINES**, `CR-145:` from
`0007` and `CR-145 (per tenant):` from this one. On a production deployment
the first will read 0 and the second carries the count.

⚠ **THE GUC IS RESTORED TO WHAT IT WAS ON ARRIVAL, NEVER CLEARED TO `''`.** A
data step that leaves `''` behind poisons the foreign-key validation of every
later migration on the same connection (§Step 0 and `OQ-354`); leaving the
arrival value — normally the nil UUID — is what `tenancy/0043` does.

⚠ **NO `try/except` AROUND A WRITE (hard-won law 14).** Nothing here can fail
per row and be skipped; if a statement fails, the migration must fail.

REVERSING IT: `noop`, for `0007`'s reason — the withdrawn values are not
choices any more, and the audit rows record what each utility held.
"""

from django.db import migrations

#: Re-declared rather than imported from `0007` or `services`: a migration must
#: keep meaning what it meant when the live constants move on.
WITHDRAWN_TIMEOUTS = (240, 480)
REPLACEMENT_TIMEOUT = 60
ACTION = "settings.security_updated"


def withdraw_long_timeouts(apps, schema_editor):
    from core import audit as core_audit
    from core import tenancy as core_tenancy

    Tenant = apps.get_model("tenancy", "Tenant")
    SecurityPolicy = apps.get_model("identity", "SecurityPolicy")
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
                for policy in SecurityPolicy.objects.filter(
                    tenant_id=tenant_id, session_timeout_minutes__in=WITHDRAWN_TIMEOUTS
                ):
                    was = policy.session_timeout_minutes
                    policy.session_timeout_minutes = REPLACEMENT_TIMEOUT
                    policy.save(update_fields=["session_timeout_minutes"])
                    core_audit.write_row(
                        action=ACTION,
                        entity_type="security_policy",
                        entity_id=policy.id,
                        actor_user_id=None,  # BR-AUD-003's unnamed system job
                        before={"session_timeout_minutes": was},
                        after={"session_timeout_minutes": REPLACEMENT_TIMEOUT},
                    )
                    moved.append((str(tenant_id), was))
            finally:
                core_tenancy._current_tenant.reset(token)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    # PRINTED, not logged — `0007`'s reason: a person watches `migrate`.
    print(
        f"CR-145 (per tenant): {len(moved)} utility(ies) moved from a withdrawn "
        f"inactivity timeout to {REPLACEMENT_TIMEOUT} minutes."
    )
    for tenant_id, was in moved:
        print(f"  {tenant_id}: {was} -> {REPLACEMENT_TIMEOUT} minutes")
    return moved


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0007_cr145_withdraw_long_timeouts"),
        # The tenants table is read here; named rather than assumed.
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(withdraw_long_timeouts, migrations.RunPython.noop),
    ]
