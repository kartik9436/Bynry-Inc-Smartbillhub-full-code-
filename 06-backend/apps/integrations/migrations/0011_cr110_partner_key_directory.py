# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 — `DEF-INT-5546`. The partner surface loses the
#           utility from its URL; the key resolves it instead. PO 2026-09-16,
#           verbatim: *"we agreed not to use utility names in partner apis that
#           was our rule - so these urls are not corect - we will resolve
#           utility name using keys"*. Blueprint p159, *WHY NOT PUT IT IN THE
#           PATH*: `key ──► connection ──► tenant ──► app.tenant_id set ──►
#           RLS does the isolating`.
# Rules:    BR-TEN-003 (the tenant is resolved from the request and never from
#           a value the caller ASSERTS — narrowed, not broken; see the module
#           business rules) · CLAUDE.md hard rule 1 (RLS FORCE on every TENANT
#           table; this one is not one) · B2 §3 (the RLS-exempt list) ·
#           BR-INT-044 (a refusal teaches nothing) · 🔒 migration ordering
# ───────────────────────────────────────────────────────
"""integrations 0011 — `integration_key_directory`: which utility an issued key belongs to.

HUMAN-OWNED (🔒 migration ordering, and the table decides WHICH UTILITY a
request is executed as). HUMAN-REVIEW-PENDING — AI-authored 2026-09-16 under the
PO ruling of 2026-08-09; the review-ledger row is in
`12-governance/09-human-review-ledger.md`.

THE SEVENTH TABLE, AND THE FIRST IN THIS MODULE WITH NO RLS POLICY
-------------------------------------------------------------------
Every other table integrations owns is a tenant table with `FORCE ROW LEVEL
SECURITY` on it (`0002_rls_force`, `0009` for the rate-limit table). **This one
deliberately has none**, and the reason is the whole of why it exists.

A partner's request arrives carrying a key and nothing else. There is no utility
in the path any more, so `TenantContextMiddleware` sets no `app.tenant_id`, so
every tenant table answers ZERO ROWS — for a perfectly valid key exactly as for
an invented one. A lookup that cannot succeed is CLAUDE.md law 7's third shape,
*incapable of passing*, and it is precisely the argument the lane that built the
old `/api/{utility}/partner/v1/…` routes used to justify putting the utility in
the URL. The argument is sound about tenant tables and the conclusion does not
follow: the answer is a table that is not one.

IT IS THE SAME CLASS AS `sessions`, AND THAT IS WHY THIS IS NOT A NEW IDEA
---------------------------------------------------------------------------
`sessions` has been on B2 §3's RLS-exempt list since W0 for this exact reason.
`GET /api/jobs/{id}` and `POST /api/exports` carry no utility either; they read
the session row — exempt, so readable before a utility is chosen — and open the
utility that row names. `core.tenancy.adopt_session_tenant` states the principle
in its own docstring: *"the cookie selects a row, the row states the tenant.
Adopting it is not client input."*

A bearer key is the same shape. The blueprint says it in four words: **a path
segment is a claim; a key is proof.**

WHAT IT HOLDS IS WHY IT MAY BE EXEMPT
--------------------------------------
Three opaque ids and one keyed one-way digest. No secret — `blind_index` is the
same fingerprint `integration_credential` already stores, computed under
`serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`, and it cannot be reversed into a key. No
name, no address, no balance, nothing a customer would recognise. Read in full by
an attacker who had somehow reached the database it yields a COUNT of issued keys
and a set of uuids, and a reader with that access already has the tenant tables.

AND IT AUTHORISES NOTHING
--------------------------
It answers one question — *which utility should I open* — and every other
question is asked afterwards, by `runners/serve.resolve_caller`, against
`integration_credential` UNDER that utility's own walls. Whether the key is live,
unexpired, in scope, from a permitted address, on an enabled connector at a live
utility is decided there and is unchanged by this migration. **A row here that
named the wrong utility would buy an attacker nothing**: the credential lookup
under that utility would not find the key and the caller would be refused in the
ordinary way, with the ordinary five words.

⚠ **NO BACKFILL, AND NONE IS POSSIBLE.** A directory row is written from the
blind index at the moment a key is minted. For a key already issued we hold the
fingerprint on `integration_credential` and could copy it across — and there are
**0 `integration_credential` rows in this product** (verified in `0010`'s own
docstring and re-verified for this one: nothing issues a key outside an
authenticated API call and no seed or fixture issues one). The data migration is
written anyway, because it costs four lines and the day this ships to a database
that does have rows is the day nobody remembers to run it by hand.

REVERSING IT
-------------
`DeleteModel`. After a reverse, every partner call at `/api/partner/v1/…`
resolves no utility and is refused — the surface goes dark rather than open,
which is the safe direction (hard-won law 3). The old
`/api/{utility}/partner/v1/…` addresses are NOT restored by reversing this; they
are a route change and live in `partner_urls.py`.
"""

from django.db import migrations, models


def seed_directory_from_existing_keys(apps_registry, schema_editor):
    """One row per credential that already carries a blind index.

    ⚠ **IT RUNS WITH NO TENANT CONTEXT, WHICH ON POSTGRESQL MEANS RLS RETURNS
    NOTHING — AND THAT IS CORRECT HERE.** A migration runs as the migrating
    role, which is not the application role the `FORCE` policies bite on; if a
    deployment's migration role IS subject to them this loop sees zero rows and
    writes zero rows, which is the same answer it gives on the empty database
    this product actually has. It can never write a WRONG row: `tenant_id` is
    copied off the credential, never guessed.
    """
    Credential = apps_registry.get_model("integrations", "IntegrationCredential")
    Directory = apps_registry.get_model("integrations", "IntegrationKeyDirectory")
    rows = [
        Directory(
            blind_index=one.blind_index,
            tenant_id=one.tenant_id,
            connection_id=one.connection_id,
            credential_id=one.id,
        )
        for one in Credential.objects.exclude(blind_index=None).exclude(blind_index="")
    ]
    Directory.objects.bulk_create(rows, ignore_conflicts=True)


def drop_directory_rows(apps_registry, schema_editor):
    apps_registry.get_model("integrations", "IntegrationKeyDirectory").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0010_cr110_key_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationKeyDirectory",
            fields=[
                ("blind_index", models.TextField(primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField()),
                ("connection_id", models.UUIDField()),
                ("credential_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "integration_key_directory"},
        ),
        migrations.AddIndex(
            model_name="integrationkeydirectory",
            index=models.Index(
                fields=["connection_id"], name="integration_key_dir_conn_idx"
            ),
        ),
        # ⚠ **DELIBERATELY NO `ENABLE`/`FORCE ROW LEVEL SECURITY`.** Every other
        # table this module owns gets one; this table cannot have one and serve
        # its purpose. The exemption is DECLARED — `tests/isolation_helpers.
        # RLS_EXEMPT_TABLES` and B2 §3 — and `test_g5_the_rls_exempt_list_is_
        # exactly_what_b2_declares` fails if the two ever disagree, so this is
        # an allowlisted absence rather than an omission nobody noticed.
        migrations.RunPython(seed_directory_from_existing_keys, drop_directory_rows),
    ]
