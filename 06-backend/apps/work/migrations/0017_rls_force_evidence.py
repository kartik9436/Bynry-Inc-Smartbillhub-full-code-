"""work 0017 — RLS ENABLE + FORCE on `work_order_attachments` and `work_order_signatures`.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `K4`); not RATIFIED without a
recorded sign-off.

WHY THESE TWO TABLES NEED IT, AND IT IS NOT THE USUAL ANSWER
────────────────────────────────────────────────────────────────────────────
The usual answer is *a tenant table needs a tenant policy*, and it applies. What
is different here is what a leaked row IS.

A `work_order_attachments` row is a pointer to a PHOTOGRAPH TAKEN INSIDE
SOMEBODY'S PROPERTY. A meter cupboard, a basement, a back garden, a door with a
number on it — taken by a stranger who was let in, of a place a customer lives.
Read across a tenant boundary it is another utility's customer's home, and the
row carries enough to fetch the image itself: `document_id` is what
`document_store.download_url()` mints a four-hour bearer link from.

A `work_order_signatures` row is worse in one specific way: it holds a named
person's SIGNATURE as an image, and the printed name beside it. That is a
specimen signature with an identity attached.

There is no version of either leak that is minor, and it is why the policy is
the boundary rather than the query being careful.

⚠ **AND THE LINK IS WHY THE POLICY MUST HOLD ON THE *READ* AND NOT ONLY ON THE
WRITE.** `evidence.attachment_link()` resolves the row under the caller's tenant
FIRST and mints the URL only for the key that row carries — so a policy failure
here does not merely show a stranger a filename, it hands them a URL that reads
another utility's customer's photograph with no session and no further check
until it expires. The application's ordering and this policy are two layers over
the same door, deliberately (`US-WRK-048` TC-6: Lone Star Ridge asking for a
Brazos Bend photograph gets the same answer as for one that does not exist).

THE POLICY IS THE `NULLIF` FORM (DEF-639)
────────────────────────────────────────────────────────────────────────────
    NULLIF(current_setting('app.tenant_id', true), '')::uuid

Deny-by-default WITHOUT erroring on an unset GUC — what makes a fresh database
buildable (`OQ-354`/`DEF-622`).

WHY `FORCE` AND NOT ONLY `ENABLE`
────────────────────────────────────────────────────────────────────────────
`ENABLE` alone exempts the table's OWNER, and the application's migration role
owns every table in this schema. B2 §3 requires both, and the proof reads
`relrowsecurity` AND `relforcerowsecurity` out of `pg_class` rather than
trusting that this file ran (hard-won law 1).

AND WHY THE PROOF CANNOT BE THE SUITE'S OWN DATABASE
────────────────────────────────────────────────────────────────────────────
`config/settings/test.py` hardcodes SQLite, which has no row-level security at
all, so every assertion about it passes there by vacuum — hard-won law 14's
shape. ⚠ **AND A RUN AS THE ORDINARY `smartbillhub` ROLE PROVES NOTHING EITHER:
it holds SUPERUSER, and PostgreSQL exempts a superuser from row security
unconditionally, `FORCE` included (`DEF-2717`).**
`tests/test_us_wrk_048_evidence_pg.py` runs under `config.settings.local`
against real PostgreSQL 16 as `sbh_gate_iso`, which is NOSUPERUSER NOBYPASSRLS
(`DEF-GOV-4036`) — the only configuration in which any of this is evidence.

NO `%` IN THIS FILE, AND THAT IS DELIBERATE (`DEF-WRK-4027`)
────────────────────────────────────────────────────────────────────────────
This SQL runs through `RunSQL`, which passes `params=None` — so psycopg
substitutes nothing and a `%%` written here would reach PostgreSQL verbatim as a
literal percent. That is what stopped every PostgreSQL migration on this branch
at `work/0009` on 2026-09-05. **Double a `%` only where psycopg will
substitute** — i.e. `schema_editor.execute(sql)`, whose default `params=()`
makes it substitute. This file contains none, so the question does not arise.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLES = ("work_order_attachments", "work_order_signatures")

POLICY = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_tenant_isolation ON {t}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for t in TABLES
)

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in TABLES
)


class Migration(migrations.Migration):
    dependencies = [("work", "0016_cr070_k_evidence")]

    operations = [PostgresOnlySQL(POLICY, reverse_sql=REVERSE)]
