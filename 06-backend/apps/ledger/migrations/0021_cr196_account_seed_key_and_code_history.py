"""ledger 0021 — `CR-196-BRC10`: a chart account's code may change; its seed slot may not.

PO ruling 2026-10-29, verbatim: *"in many cases utilities are giving there own
GL codes; which means we have to ability to change existing GL code as per the
given utility for that specific tenant; even if they are used ; if user update
them they should be applicable after the updation."*

TWO NULLABLE/DEFAULTED COLUMNS ON `ledger_accounts`, ONE BACK-FILL, ONE INDEX.

1 · `seed_key` (TEXT, NULL) — the code an account was SEEDED or MINTED under.
    Our judgment 5a/5b (decision log 2026-10-29): the reference sweep runs
    `seed_chart_of_accounts` for every tenant after every `migrate`, and it used
    to find a seeded account BY CODE. Rename `4150` to the utility's own
    `0117-080-1000-0000-7127` and the next deploy mints an EMPTY `4150 Solar`
    beside it; rename the tax account `2200-01` and the remittance refuses it
    and the tax report drops it. The key is how both find the account instead.
    **Internal: never on the wire, never on a screen, never moved by a code
    edit.**

2 · `code_history` (JSON, default `[]`) — every code change, oldest first.
    On the account because `audit_log` is pruned (OQ-1340), and *"formerly
    4150"* must outlive the retention window.

3 · THE BACK-FILL. For every tenant, an account with no key whose CODE is a
    code some seed path plants (`chart.seed_codes()`) or is in the 2200 tax
    series gets `seed_key = code`. Before this migration no code could change
    (BR-LED-040 as signed), so today's code IS the seeded/minted code for every
    such row — there is nothing to reconstruct. A hand-typed account whose code
    happens to equal a seed code takes that slot, which is also what the seed
    already believed (`_create_missing_accounts` skipped it as "theirs").

4 · `uq_ledger_accounts_seed_key` — one account per seed slot per tenant, live
    or retired, PARTIAL on `seed_key IS NOT NULL`. Created AFTER the back-fill.
    The back-fill cannot violate it: it copies `code`, which
    `uq_ledger_accounts_code` already makes unique per tenant.

⚠ **HARD RULE 1 — EACH TENANT'S UPDATE RUNS UNDER ITS OWN `app.tenant_id`.**
`ledger_accounts` is RLS `FORCE`, which binds the table owner too, so the
UPDATE sets the tenant first (the `assets/0011` shape) and resets to the nil
sentinel — never `''`, which poisons later migrations in the same run
(OQ-354). On sqlite there is no RLS and no `set_config`.

⚠ **NO SAVEPOINT PER TENANT, DELIBERATELY.** Nothing here catches an error and
carries on, so hard-won law 14's trap does not arise: a failure aborts the
whole `migrate`, which is the right outcome for a back-fill a later guard
depends on. A tenant silently left un-keyed would be exactly the duplicate the
column exists to prevent.

⚠ **ROLLBACK** drops the index and both columns. A code a System Admin has
already changed STAYS changed — every journal line points at the account by
id, so nothing re-points — and what is lost is the "formerly" history and the
two guards, so a later re-seed could again mint a duplicate of a renamed row.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering and the chart are
CLAUDE.md 🔒 sensitive paths. AI-authored 2026-10-29 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md` (`CR-196-BRC10`).
"""

from django.db import migrations, models
from django.db.models import F, Q

#: The nil sentinel, never `''` — see `assets/0003`'s note (OQ-354).
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _set_tenant(connection, tenant_id: str) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [tenant_id])


def backfill_seed_keys(apps, schema_editor):
    from apps.ledger import chart  # the live seed list — see the docstring, 3

    Tenant = apps.get_model("tenancy", "Tenant")
    Account = apps.get_model("ledger", "LedgerAccount")
    codes = sorted(chart.seed_codes())
    connection = schema_editor.connection
    # `tenants` is an RLS-exempt platform table (db/rls_tenancy_w0.sql).
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _set_tenant(connection, str(tenant_id))
        Account.objects.filter(tenant_id=tenant_id, seed_key__isnull=True).filter(
            Q(code__in=codes) | Q(code__startswith=chart.TAX_PAYABLE_SERIES)
        ).update(seed_key=F("code"))
    _set_tenant(connection, NO_TENANT)


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0020_p4_4_tax_remittances"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ledgeraccount",
            name="seed_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ledgeraccount",
            name="code_history",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_seed_keys, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=models.UniqueConstraint(
                condition=Q(seed_key__isnull=False),
                fields=("tenant", "seed_key"),
                name="uq_ledger_accounts_seed_key",
            ),
        ),
    ]
