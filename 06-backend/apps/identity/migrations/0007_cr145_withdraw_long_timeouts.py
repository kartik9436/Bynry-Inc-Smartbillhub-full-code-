"""identity 0007 — `CR-145-BRC08`: 240 and 480 minutes are withdrawn.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-28 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

⚠ **THIS IS THE ONLY VISIBLE BEHAVIOUR CHANGE IN THE WHOLE OF `CR-145`.**
Every other part of it is a constant becoming a column whose default is the
number that constant held, so no utility's behaviour moves. This one moves
real ones: the PO narrowed the inactivity choices to **15 / 30 / 45 / 60** on
2026-09-28, so a utility sitting on 240 or 480 minutes is moved to **60**, and
**its staff are signed out up to seven hours earlier than they were the day
before**. 30 and 60 are untouched, because they are still choices.

⚠ **ONE AUDIT ROW PER UTILITY MOVED, AND A PRINTED COUNT.** The count is a
figure the PO will be given, so it is COUNTED rather than estimated: it is the
length of the list of rows this migration actually wrote, not the number of
rows the `UPDATE` was aimed at. `before` and `after` are on the row, so a year
from now the answer to *"why did our timeout change?"* is in the same trail as
every other change to that setting — written the same way
`services.save_security_policy` writes it, with the same action code, because
a clerk reading the Security tab's history should not be able to tell that one
of those rows came from a migration.

⚠ **THE ROWS ARE WRITTEN THROUGH `core.audit.write_row`, NOT BY AN INSERT
HERE.** `audit_log` is monthly RANGE-partitioned and its RLS policy has a
`WITH CHECK`, so a hand-rolled INSERT in a migration is a second writer that
has to get the partition, the tenant GUC and the BR-AUD-003 row shape right on
its own. Rule 5's shape for the trail: one writer.

⚠ **`tenant_context` IS VENDOR-GUARDED, AND THAT IS HARD-WON LAW 14 IN THE
OPPOSITE DIRECTION.** `app.tenant_id` is a PostgreSQL GUC set through
`set_config()`, which SQLite does not have — and `config/settings/test.py`
hardcodes in-memory SQLite, so this migration runs on SQLite in every test
run. Calling the kernel unguarded would make the whole suite fail at migrate
time, on every machine, for a reason that has nothing to do with the change.
On SQLite the Python mirror alone is set, which is what `write_row` reads for
`tenant_id`; on PostgreSQL the real GUC is set, which is what RLS reads. **The
real proof is on PostgreSQL** (`tests/test_cr145_migration_pg.py`), because a
data migration proved only on SQLite is a data migration nobody has run.

REVERSING IT
────────────
`migrations.RunPython.noop`, deliberately, and it is not laziness. Reversing
would mean putting a utility back on a value the product no longer offers —
its Security tab would show a number missing from its own dropdown, and the
next save would refuse it by name. The audit rows say what each utility held,
so a utility that wants the old behaviour has the evidence to argue for it;
what it cannot have is the withdrawn number back by an automatic rollback.
"""

from contextlib import contextmanager

from django.db import migrations

#: PO ruling 2026-09-28. Both are gone from `services.SETTING_LIMITS`.
WITHDRAWN_TIMEOUTS = (240, 480)

#: Where they go. It is the column default and the middle of the new range —
#: and it is the choice CLOSEST to the withdrawn ones, so the disruption is the
#: smallest the narrowed list allows.
REPLACEMENT_TIMEOUT = 60

#: The same action code `services.save_security_policy` writes, on purpose —
#: see the module docstring.
ACTION = "settings.security_updated"


@contextmanager
def _tenant_context(connection, tenant_id):
    """The tenant GUC on PostgreSQL; the Python mirror alone elsewhere.

    See the module docstring for why this is guarded rather than simply
    calling the kernel.
    """
    from core import tenancy as core_tenancy

    if connection.vendor == "postgresql":
        with core_tenancy.tenant_context(tenant_id):
            yield
        return
    token = core_tenancy._current_tenant.set(core_tenancy._as_uuid(tenant_id))
    try:
        yield
    finally:
        core_tenancy._current_tenant.reset(token)


def withdraw_long_timeouts(apps, schema_editor):
    from core import audit as core_audit

    SecurityPolicy = apps.get_model("identity", "SecurityPolicy")

    # Read the rows FIRST and write them one at a time. A single bulk
    # `UPDATE … WHERE session_timeout_minutes IN (240, 480)` would be one
    # statement and no trail, and `rowcount` would be a number with no rows
    # behind it to check — exactly the assumption the ruling asked to avoid.
    moved = []
    for policy in SecurityPolicy.objects.filter(
        session_timeout_minutes__in=WITHDRAWN_TIMEOUTS
    ).order_by("tenant_id"):
        was = policy.session_timeout_minutes
        policy.session_timeout_minutes = REPLACEMENT_TIMEOUT
        policy.save(update_fields=["session_timeout_minutes"])
        with _tenant_context(schema_editor.connection, policy.tenant_id):
            core_audit.write_row(
                action=ACTION,
                entity_type="security_policy",
                entity_id=policy.id,
                # No person did this. `actor_user_id=None` with no automation
                # actor is BR-AUD-003's UNNAMED SYSTEM JOB, which is what a
                # migration is, and it is how every reader already tells a
                # person's change from the product's.
                actor_user_id=None,
                before={"session_timeout_minutes": was},
                after={"session_timeout_minutes": REPLACEMENT_TIMEOUT},
            )
        moved.append((str(policy.tenant_id), was))

    # ⚠ **PRINTED, NOT LOGGED.** A `migrate` run is watched by a person, and a
    # log line at INFO on a deployment that configures its own logging is a
    # number nobody sees. This is the figure the PO is given.
    print(
        f"CR-145: {len(moved)} utility(ies) moved from a withdrawn "
        f"inactivity timeout to {REPLACEMENT_TIMEOUT} minutes."
    )
    for tenant_id, was in moved:
        print(f"  {tenant_id}: {was} -> {REPLACEMENT_TIMEOUT} minutes")
    return moved


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0006_cr145_session_settings"),
        # The trail is written here, so the table and its policies must exist.
        # Named rather than assumed: a migration that writes another module's
        # table without depending on it runs in whatever order the graph
        # happens to pick.
        ("audit", "0007_us_aud_010_audit_actor"),
    ]

    operations = [
        migrations.RunPython(withdraw_long_timeouts, migrations.RunPython.noop),
    ]
