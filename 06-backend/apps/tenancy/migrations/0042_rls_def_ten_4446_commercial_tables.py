# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-TEN-4446 — two tables holding what each utility negotiated to
#           pay Bynry carry a tenant_id and no row-level security policy.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#           template, verbatim, one per table; `subscriptions` is FIRST on its
#           apply-list and neither of these two is on its exempt-list) ·
#           🔒 RLS policies (CLAUDE.md sensitive paths — `human_owned.txt`
#           globs `06-backend/**/migrations/*rls*` and `apps/*/migrations/0*.py`)
# Tests:    06-backend/tests/test_def_ten_4446_commercial_rls.py — zero rows
#           without context under the non-superuser probe role, nothing of Pine
#           Hill under Oak Ridge's context, and `relrowsecurity` AND
#           `relforcerowsecurity` both true in `pg_class` for both tables
# Impacts:  every read of `implementation_orders` and `tenant_addons` — under a
#           tenant context or nothing. `platform_numbering.allocate_sequence`
#           exists because of this migration.
# ───────────────────────────────────────────────────────
"""tenancy 0042 — RLS ENABLE + FORCE on the two priced commercial tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies the SIGNED
B2 §3 template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHAT WAS WRONG
--------------
`implementation_orders` holds what one utility agreed to pay for its setup — a
price, a currency, a duration, an instalment count. `tenant_addons` holds a
negotiated monthly figure. Both carry a `tenant_id`. Neither carried a policy,
so the only thing between one utility and another's price was a single
`.filter(tenant_id=…)` in `subscription_overview()`: an app-layer filter, which
is precisely what hard rule 1 declines to rely on.

WHAT `0021` SAID, AND WHY IT DOES NOT HOLD
-------------------------------------------
`0021` left the policy off deliberately and explained itself at length. Quoted
rather than paraphrased, because a supersession must show what it supersedes:

    ⚠ **NO `app.tenant_id` POLICY IS ADDED HERE, DELIBERATELY.** CLAUDE.md hard
    rule 1 governs TENANT tables; these are platform tables, and applying tenant
    isolation to them would make Bynry's own commercial records invisible to
    Bynry. `subscriptions` establishes that precedent and this follows it rather
    than inventing a second posture.

**The precedent points the other way.** `subscriptions` has row security ENABLED
and FORCED in this database, and B2 §3 — the signed schema contract — lists it
FIRST among the tables a policy must be applied to. B2's "No RLS (platform)"
list is `plans, tenants, roles, permissions, role_permissions, users, sso_links,
tax_jurisdictions`, and neither of these two tables is on it. So no signed rule
was ever reversed here and none is reversed now: the contract already said what
to do, and `0021` read a sibling migration's summary of it instead of reading
it. That is CLAUDE.md hard-won law 1 in its plainest form — a comment claiming a
guarantee is not the guarantee, and this one was a comment claiming a precedent.

`0021`'s docstring is left exactly as it was. A migration is a record of what
was done, and rewriting it would erase the reasoning that this file exists to
answer.

⚠ **AND THE ONE TRUE THING IN `0021`'s ARGUMENT IS ANSWERED, NOT DISMISSED.**
"Bynry's own commercial records invisible to Bynry" would be a real cost if
anything in this product read these tables as Bynry. Nothing does: `grep` finds
two readers, `subscription_overview()` (S107, the utility's own Settings →
Billing plan tab, which already runs inside that utility's context) and the
allocator. There is no Bynry-side admin surface in this product — `0021` says so
itself — so the policy takes away a view nobody has. If one is ever built, it is
a platform path that adopts a context per tenant, exactly as every job in this
product already does.

WHAT IT GUARANTEES, MEASURED ON POSTGRESQL AND NOWHERE ELSE
------------------------------------------------------------
Deny-by-default: with `app.tenant_id` unset or empty, `NULLIF(…, '')::uuid` is
NULL, the predicate is NULL, and **zero rows** of either table are visible or
writable. Under Oak Ridge's context, Pine Hill's implementation price and
add-on figure are not reachable by any query, id-guessing included. `FORCE`
makes that true for the table owner too.

SQLite has no RLS. The tests that prove this migration carry `requires_postgres`
and SKIP there rather than pass vacuously (hard-won law 14).

⚠ **THIS MIGRATION MUST NOT RUN BEFORE `0041`.** `0041` reads every existing
`order_no` to seed Bynry's counter, and after this file has run a context-free
read of `implementation_orders` returns nothing — silently, because a deny is an
empty result rather than an error. The dependency below is that ordering.
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: Kept as a literal here rather than imported from the models module, so this
#: migration reads the same in a year when that module has moved on — a
#: migration is a record of what was done (`0038` states the same rule).
#:
#: `addons` is NOT here and that is correct: it is the platform CATALOGUE, it
#: carries no `tenant_id`, and a policy on it would fail loudly at CREATE POLICY.
#: `platform_number_series`, added by `0041`, is absent for the same reason.
TENANT_TABLES = (
    "implementation_orders",
    "tenant_addons",
)


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(tenant_isolation_policy_sql(table))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0041_def_ten_4446_platform_order_counter"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-TEN-4446 (isolation receipt 2026-09-07 + B2 §3 lines 1001-1002 + tenancy/0021's own docstring)
# generated: 2026-09-07 by the DEF-TEN-4446 lane
# checklist: A✔ (r11 step 0 against 01-open-questions, 02-decision-log, 10-defect-log, 11-change-requests) B✔ C✔ D=n/a(no API half — the policy changes what an existing read can see, it adds no route) E=n/a(S107 already runs inside the tenant's own context; the screen is unchanged and was checked, not assumed) F✔ G✔ H=PENDING(🔒 RLS policies — ledger row in 09-human-review-ledger.md, plain English with the figure: two tables holding what each utility pays, zero rows visible without a tenant context, one order-number series still unique across all utilities)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_def_ten_4446_commercial_rls.py on PostgreSQL 16 under the sbh_rls_probe NOSUPERUSER NOBYPASSRLS role · 10-scripts/prove_isolation.py, whose receipt names this migration digest
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
