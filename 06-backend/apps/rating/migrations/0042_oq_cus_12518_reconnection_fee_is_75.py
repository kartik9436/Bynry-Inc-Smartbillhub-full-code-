# ── Trace ──────────────────────────────────────────────
# Rules:   PO ruling 2026-09-21, verbatim: *"reconnection fee is $75 - fix the
#          code and seed"* (`OQ-CUS-12518`, CLOSED) · `BR-CUS-104`, SIGNED on
#          $75.00 by the PO on 2026-08-25 · `BR-BIL-007` (a reconnect fee is a
#          TENANT-CONFIGURED charge code, never hardcoded) · CLAUDE.md hard
#          rule 1 (never touch a tenant table without `app.tenant_id` set) ·
#          hard rule 2 (money stored to 4 decimals) · 🔒 migration ordering
# Defect:  DEF-BIL-5382 — a data migration under RLS FORCE sees ZERO rows with
#          the GUC unset and reports success to nobody. `rating/0039` is the
#          repair of exactly that, and its loop is the one copied here.
# ───────────────────────────────────────────────────────
"""rating 0042 — **the reconnection fee a tenant already holds becomes $75.00.**

HUMAN-OWNED (migration ordering and a money figure are both CLAUDE.md 🔒
sensitive paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-21 under the PO
ruling of 2026-08-09. Row in `12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHY A MIGRATION AT ALL — THE FIXTURE REACHES NOBODY WHO ALREADY EXISTS
════════════════════════════════════════════════════════════════════════════
`apps/tenancy/fixtures/lookup_defaults.json` is what a **new** tenant is
provisioned from. A charge code is a **per-tenant row** the utility may edit —
`rating.selectors.charge_by_code` says so in its own words, *"the amount is a
SEED the tenant edits, never a constant"*. So editing the fixture alone leaves
**every utility already provisioned charging `$45.00` for ever.**

⚠ **THIS IS CLAUDE.md HARD-WON LAW 4's SHAPE** — *"a template change never
reaches a host that already has a `.env` … say so, every time"* — with a seed
fixture in place of a `.env`. **Measured 2026-09-21 before writing this: every
existing tenant holds `RECON` at `45.000000`.**

════════════════════════════════════════════════════════════════════════════
WHAT IT DOES, AND THE ONE CONDITION THAT MATTERS
════════════════════════════════════════════════════════════════════════════
For every tenant, the `RECON` charge code's `amount` moves **from exactly
`45.000000` to `75.0000`** — and from nothing else.

⛔ **A ROW AT ANY OTHER FIGURE IS LEFT ALONE, DELIBERATELY.** The PO's ruling
corrects **our** seed error; it does not repossess a utility's own price. A
utility that has deliberately set its reconnection fee to `$60.00` keeps it,
and `BR-BIL-007` is the reason — the amount is theirs to configure. A migration
that wrote `75` over every row would be this product overruling its customers
on a money figure, which no ruling here authorises.

⚠ **SO A TENANT WHO HAD ALREADY EDITED 45 TO SOMETHING ELSE, AND MEANT 45, IS
NOT CORRECTED BY THIS.** That case cannot be told apart from a deliberate
choice by anything in the database, and guessing on a money figure is worse
than leaving it. It is stated rather than silently handled.

════════════════════════════════════════════════════════════════════════════
⚠ IT SETS `app.tenant_id` PER TENANT OR IT SILENTLY DOES NOTHING
════════════════════════════════════════════════════════════════════════════
`charges` has `relrowsecurity` AND `relforcerowsecurity` true and the migration
role does not bypass RLS, so `Charge.objects.filter(...)` with the GUC unset
returns **zero rows** — the loop runs over nothing, reports success, and the
fee stays `$45.00` on every tenant in production.

**That is not hypothetical: it is `DEF-BIL-5382`, and `rating/0039` exists
because `rating/0038` did exactly this.** The `_tenant_ids` / `_enter_tenant` /
`_leave_tenant` trio below is 0039's, unchanged, for that reason.

⚠ **AND NO TEST ON THE DEFAULT SUITE COULD CATCH IT** — `config/settings/test.py`
hardcodes SQLite, which has no row-level security, so the same loop sees every
row there and passes green (hard-won law 14). **The case over this migration
must run under `config.settings.pgtest`.**

════════════════════════════════════════════════════════════════════════════
FOUR DECIMALS, AND THE COLUMN IS SIX
════════════════════════════════════════════════════════════════════════════
`charges.amount` is `NUMERIC(18,6)`. CLAUDE.md hard rule 2 as re-signed by the
PO on 2026-08-22 — *"MOney 4 decimal, percentage 6 decimal, display both 2
decimal"* — governs **what is WRITTEN** and what a NEW column declares, and
says an existing `18,6` column stays a lawful container. So `Decimal("75.0000")`
is written into it and the column is not rewritten.

════════════════════════════════════════════════════════════════════════════
REVERSIBLE, AND WHAT REVERSING COSTS
════════════════════════════════════════════════════════════════════════════
The reverse moves `75.000000` back to `45.0000`, under the same condition and
the same per-tenant loop. ⚠ **It therefore also reverts a tenant who has since
chosen `$75.00` for themselves**, because nothing distinguishes their figure
from this migration's. Stated rather than discovered: a reverse on a database
that has been live for a while is not a clean undo.
"""

from decimal import Decimal

from django.db import migrations

#: The nil sentinel the provisioner gives a session by default, restored on the
#: way out so the connection is left as it was found.
NO_TENANT = "00000000-0000-0000-0000-000000000000"

#: `OQ-CUS-12518`'s ruled figure. `BR-CUS-104`'s signed worked case is
#: `$8,240.00` arrears `+ $75.00` `= $8,315.00` (PO 2026-08-25).
RULED_AMOUNT = Decimal("75.0000")

#: What our own seed shipped, and the ONLY value this migration will overwrite.
SEEDED_AMOUNT = Decimal("45.000000")

RECONNECT_CODE = "RECON"


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


def _move(apps, schema_editor, *, frm, to):
    Charge = apps.get_model("rating", "Charge")
    connection = schema_editor.connection
    moved = 0
    for tenant_id in _tenant_ids(apps):
        _enter_tenant(connection, tenant_id)
        # ⚠ `code` is compared EXACTLY. `iexact` would sweep a tenant's own
        # `recon` row written by hand, which is not ours to move.
        moved += Charge.objects.filter(code=RECONNECT_CODE, amount=frm).update(amount=to)
    _leave_tenant(connection)
    return moved


def set_reconnection_to_the_ruled_figure(apps, schema_editor):
    _move(apps, schema_editor, frm=SEEDED_AMOUNT, to=RULED_AMOUNT)


def put_the_seeded_figure_back(apps, schema_editor):
    _move(apps, schema_editor, frm=RULED_AMOUNT, to=Decimal("45.0000"))


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0041_def_rat_5823_drop_unresolvable_classes"),
        # `tenants` is read to enumerate the loop, so tenancy must be in place.
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            set_reconnection_to_the_ruled_figure,
            put_the_seeded_figure_back,
        ),
    ]
