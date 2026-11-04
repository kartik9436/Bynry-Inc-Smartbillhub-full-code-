# ── Trace ──────────────────────────────────────────────
# Change:  CR-130-BRC07 §3 — `tariff_versions` gains ONE column, `percent_basis`
#          ('usage' | 'charge'). PO ruling 2026-09-22.
# Rules:   BR-RAT-1030 (NEW — the two bases) · BR-RAT-015 ❄️ SUPERSEDED
#          2026-09-08 by CR-081 · BR-RAT-032 (one price is ONE 0→∞ tier — which
#          is why there is no second column for the rate and no `rate_shape`)
#          · CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set) · CLAUDE.md 🔒 migration ordering
# Golden:  ❄️ GT-17 ($36.00) · GT-20 ($54.00) · GT-25 ($27.00) · GT-26 ($27.00)
#          — NONE of them moves, and this migration is why: every row that
#          exists is written 'usage' BY NAME.
# Tests:   06-backend/tests/test_cr130_percent_basis.py
# ───────────────────────────────────────────────────────
"""rating 0043 — a percent schedule says WHAT it is a percentage OF.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

WHY THIS IS THREE OPERATIONS AND NOT ONE
-----------------------------------------
`AddField(default='usage')` alone would be one line and would produce the right
bytes. It is not used, and the reason is the whole point of the change:

    A schedule that silently changed basis moves real money on a real customer.

With a single `AddField`, every existing schedule would read `'usage'` because
nobody ever wrote anything else — a value by omission, indistinguishable from a
value somebody chose. Worse, a row the write could not reach (row-level
security, a tenant added mid-deploy) would be indistinguishable too, and there
would be no way afterwards to tell the difference.

So the column arrives NULLABLE, is filled BY NAME one tenant at a time, and is
only then made NOT NULL. **`SET NOT NULL` is the proof**: if the backfill missed
one row anywhere, the third operation fails and the deploy stops. That is the
safe direction (hard-won law 3 — the unsafe option must be the one you type).

⚠ **THE DATABASE DEFAULT IS FOR THE RACE, NOT FOR THE BACKFILL.** Step three
restores `DEFAULT 'usage'` so an INSERT from a process still running the old
code during a rolling deploy lands a lawful row rather than a NULL. It is not
what fills the rows that already exist.

⚠ **`app.tenant_id` IS SET PER TENANT AND THE PATTERN IS BORROWED, NOT
INVENTED** — `rating/0039` exists precisely because `rating/0038`'s backfill ran
with no tenant context, RLS FORCE hid every row from it, and **three plans came
out saying the opposite of what they said**. It was invisible to the suite:
`config/settings/test.py` hardcodes SQLite and SQLite has no row-level security
(hard-won law 14's shape). The `_enter_tenant` / `_leave_tenant` pair below and
the nil sentinel are `rating/0039`'s, reused verbatim rather than rewritten.

⚠ **AND THE `SET NOT NULL` IS THE ONLY CHECK THAT SURVIVES THAT TRAP.** On
SQLite the loop sees every row whether or not the context is set, so a green
suite proves nothing about the backfill's REACH. What it does prove is that the
column is not-null afterwards — and on PostgreSQL, where the reach can fail,
that same assertion is what turns a silent miss into a stopped deploy.

WHAT IT DOES *NOT* DO
---------------------
Nothing is converted to `'charge'`. There is no data anywhere that says a
schedule meant the dollar basis: `CR-081` moved every schedule to the volume
basis on 2026-09-08 with a PO re-sign of six ❄️ frozen figures, and this change
is ADDITIVE — the dollar basis comes back BESIDE the volume one as a choice a
clerk makes on S11, never as a migration's guess.

ROLLBACK
--------
The reverse drops the column. Every row is `'usage'`, which is today's
behaviour, so nothing already billed changes and no issued invoice is touched
(CLAUDE.md hard rule 4 — this migration writes no invoice, line, payment or
journal row).
"""

from django.db import migrations, models

from apps.rating.pricing.percent_basis import PERCENT_BASIS_USAGE

#: The nil sentinel rather than `''` — `assets/0003` and `rating/0039` record
#: why in full: `set_config(..., false)` is SESSION level and outlives this
#: migration, and an empty string makes a later `::uuid` cast raise. A real
#: uuid that matches no row keeps deny-by-default intact.
NO_TENANT = "00000000-0000-0000-0000-000000000000"


def _tenant_ids(apps):
    """`tenants` is an RLS-exempt platform table, so it enumerates with no
    context — the same door `rating/0039` and `assets/0003` use."""
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _enter_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _leave_tenant(connection):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NO_TENANT])


def _say_usage_out_loud(apps, schema_editor):
    """Write `'usage'` onto every existing version, BY NAME, tenant by tenant.

    `update()` rather than a per-row `save()`: this touches no other column, so
    there is no field to overwrite by accident and no `auto_now` to disturb.
    """
    TariffVersion = apps.get_model("rating", "TariffVersion")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        TariffVersion.objects.filter(percent_basis__isnull=True).update(
            percent_basis=PERCENT_BASIS_USAGE
        )
    _leave_tenant(connection)


def _unsay_it(apps, schema_editor):
    """Reversing step two is a no-op: step three's reverse makes the column
    nullable again and the reverse of step one drops it outright, so there is
    nothing for this to put back. Stated rather than omitted so the reverse
    reads as deliberate."""


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0042_oq_cus_12518_reconnection_fee_is_75"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        # 1 · NULLABLE, with no default — so an unreached row stays visibly
        #     unanswered instead of quietly acquiring the right answer.
        migrations.AddField(
            model_name="tariffversion",
            name="percent_basis",
            field=models.TextField(null=True),
        ),
        # 2 · the explicit backfill, under each tenant's own RLS context.
        migrations.RunPython(_say_usage_out_loud, _unsay_it),
        # 3 · NOT NULL + the default for the rolling-deploy race. This is the
        #     assertion: it cannot succeed if step 2 missed a row.
        migrations.AlterField(
            model_name="tariffversion",
            name="percent_basis",
            field=models.TextField(default=PERCENT_BASIS_USAGE),
        ),
    ]
