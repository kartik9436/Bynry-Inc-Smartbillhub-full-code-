# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave D — migration 1 of 2. "The call limit is a GUARD,
#           not a setting." PO 2026-09-16, verbatim: *"keep the limit in
#           database so if we want to change it later it is easy to do"*, and
#           *"so wecant allow clark to reset it"*.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE on every tenant table; the policy
#           is in THIS migration, see below) · NFR-5 (no hard cap per tenant —
#           this table caps CALLS A MINUTE and never accounts, rows or
#           connections) · B2 §3 (the signed policy template, verbatim,
#           through core.rls) · 🔒 migration ordering + RLS policies
# ───────────────────────────────────────────────────────
"""integrations 0009 — `integration_rate_limit`: one ceiling per connection, per operation.

HUMAN-OWNED (🔒 migration ordering AND 🔒 RLS policies, both CLAUDE.md
sensitive paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-16 under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*); the
review-ledger row is in `12-governance/09-human-review-ledger.md` and states,
in plain English with the figure, exactly what a reviewer is agreeing to.

ONE TABLE, ONE UNIQUE, ONE CHECK, ONE INDEX AND ITS POLICY
-----------------------------------------------------------
`integration_rate_limit` holds the number of calls a minute a partner may make
**on one operation of one connection**. Nothing else. It is the only place in
this change request where a number a utility might one day have negotiated is
written down, which is exactly what the PO asked for: a value that moves
without a release.

WHY THE POLICY IS HERE AND NOT IN `0002_rls_force`
---------------------------------------------------
`0002` put the signed B2 §3 template on the five tables that existed on
2026-09-03, and it is a RECORD OF WHAT WAS DONE rather than a list to keep
appending to. A sixth tenant table added later cannot borrow that migration's
protection: between `CreateModel` and whatever later migration added the
policy, the table would exist **unguarded**, and a data migration or a deploy
that stopped in between would leave it that way. So the `CREATE TABLE` and the
`CREATE POLICY` are in one migration and one operation list, and the policy
comes from `core.rls.tenant_isolation_policy_sql` — the one function that holds
the signed template — so this file invents no policy shape of its own.

⚠ **THE TABLE IS A TENANT TABLE AND IT WOULD BE EASY TO ARGUE IT IS NOT.** A
call ceiling looks like configuration, and configuration feels shared. It is
not: it is one utility's agreement with one partner, and under RLS `FORCE`
with no `app.tenant_id` it yields zero rows like every other tenant table.
`serve.rate_limit_for` reads it inside the tenant context the path already set,
and treats *no row* as the DEFAULT ceiling rather than as no ceiling — so a
lane that somehow reads it without context gets a limit of 100, never
unlimited.

⚠ **`NFR-5` IS NOT BREACHED AND THE DISTINCTION MATTERS, BECAUSE THIS TABLE IS
LITERALLY A CAP.** `NFR-5` forbids a cap on how much of this product a utility
may HAVE — accounts, rows, connections, tenants. This caps how fast an outside
machine may knock on the door. A tenant may have as many of these rows as it
has connections × operations, with no maximum anywhere, and nothing here
counts accounts.

⚠ **`on_delete=CASCADE` HERE IS DJANGO'S CASCADE AND NOT THE DATABASE'S, AND
THAT SENTENCE COST THIS FILE THREE ROUNDS OF A FAILING TEST. READ IT BEFORE
WRITING `on_delete=CASCADE` ANYWHERE ELSE IN THIS REPO.**

The choice itself is deliberate: every other foreign key in `apps/integrations`
is `PROTECT`, because the rows on the other end are RECORDS — a credential, a
run, a mapping — and destroying a connection must not quietly destroy an audit
trail. A ceiling is not a record; it is a setting with no meaning once the
connection it bounds is gone, and `PROTECT` would mean a connection could not be
disconnected until somebody deleted rows nobody has a screen for.

**What `on_delete=models.CASCADE` actually produces is `FOREIGN KEY (…)
REFERENCES … DEFERRABLE INITIALLY DEFERRED` — `NO ACTION`.** Django issues the
child DELETE itself, in Python, when you call `.delete()`. So:

  * an ORM delete of a connection removes its ceilings — the ordinary path;
  * a **raw** `DELETE FROM integration_connection` does NOT, and is **REFUSED at
    COMMIT** with a foreign-key violation. That is a safe direction rather than
    a hole — nothing silently loses a ceiling — and it is stated here because
    the failure arrives at commit, names neither table helpfully, and reads like
    a broken tool.

⚠ **AND THIS FILE SPENT SIXTY LINES TRYING TO PUT A REAL `ON DELETE CASCADE`
INTO THE DATABASE BEFORE LEARNING WHY IT CANNOT, WHICH IS THE PART WORTH
KEEPING.** A `RunPython` that dropped and re-added the constraint **found no
constraint to drop**: Django creates a `CreateModel`'s foreign keys through
`schema_editor.deferred_sql`, which is flushed **after every operation in the
migration has run**. So the lookup returned `None`, the function returned
silently, and its own `# pragma: no cover — the CreateModel above just wrote
it` comment was a lie about the thing it sat next to (hard-won law 1, on its
author, in a comment about hard-won law 1). It was removed rather than worked
around: a third migration would have broken the Product Owner's *"two
migrations, their own named commits"*, and the behaviour we actually have is
already the safe one.

⚠ **NO BACKFILL, AND THAT IS A MEASURED FACT RATHER THAN A CORNER CUT.** The
change request verified it and the query is repeatable: nothing in this product
issues a partner key outside an authenticated API call, the set-up screen has
no route at all, and there are **0 `integration_connection` rows and 0
`integration_credential` rows** anywhere. So there is no connection to seed a
ceiling for. `services.ensure_rate_limits` seeds them at `connect()` from the
manifest default, and it is idempotent, so a connection made between this
migration and that code landing is repaired by the next call rather than left
short.

REVERSING IT
-------------
`migrations.CreateModel` reverses by dropping the table, and the policy goes
with it. `drop_rls` below exists for the case where somebody reverses only the
`RunPython` — it is written to be safe on a table that is already gone.
"""

from django.db import migrations, models

import core.dbfields
from core.rls import tenant_isolation_policy_sql

TABLE = "integration_rate_limit"


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(tenant_isolation_policy_sql(TABLE))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0008_m1_inline_trigger"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationRateLimit",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("operation", models.TextField()),
                ("calls_per_minute", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=models.CASCADE,
                        related_name="rate_limits",
                        to="integrations.integrationconnection",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": TABLE},
        ),
        migrations.AddConstraint(
            model_name="integrationratelimit",
            constraint=models.UniqueConstraint(
                fields=("connection", "operation"),
                name="uq_integration_rate_limit_operation",
            ),
        ),
        migrations.AddConstraint(
            model_name="integrationratelimit",
            constraint=models.CheckConstraint(
                condition=models.Q(calls_per_minute__gt=0),
                name="ck_integration_rate_limit_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="integrationratelimit",
            index=models.Index(
                fields=["tenant", "connection"], name="ix_intg_rate_limit_conn"
            ),
        ),
        # ⚠ IN THE SAME MIGRATION AS THE TABLE. See the docstring — a tenant
        # table that exists for even one migration without a policy is hard
        # rule 1 with a window in it.
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 (PO rulings 2026-09-16) + blueprint p017 + B2 §3
# generated: 2026-09-16 by the CR-110-BRC04 wave D build lane
# checklist: A✔ B=n/a(display only — another lane renders the cell) C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 — row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · sqlmigrate prints one CREATE TABLE, one UNIQUE, one CHECK, one INDEX and the B2 §3 policy · tests/test_cr110_rate_limits_pg.py (the policy denies without context; the CHECK refuses 0; the duplicate is a savepoint) · G7
# exceptions: `on_delete=CASCADE` is DJANGO's cascade, not the database's — the FK is `NO ACTION DEFERRABLE`, so an ORM delete removes the ceilings and a RAW delete is refused at commit. Deliberate, measured, and explained in the docstring · no backfill: 0 connections and 0 credentials exist to seed
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
