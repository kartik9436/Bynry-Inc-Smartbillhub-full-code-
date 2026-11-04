# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C19 / task T7d — the guarantees the model class in 0015
#           cannot give.
#           Screens: S41 · S36
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · BR-PAY-031 (a reapply is
#           reversing allocation rows plus new rows, never an edit)
# ───────────────────────────────────────────────────────
"""payments 0016 — isolation and append-only for `allocation_classes`.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3 policy
template VERBATIM and invents no new policy shape — the same template
`db/rls_payments_w5.sql` carries for the six W5 tables.

────────────────────────────────────────────────────────────────────────────
WHY THE TENANT POLICY IS NOT OPTIONAL HERE
────────────────────────────────────────────────────────────────────────────
These rows say **how much tax one utility has actually collected**, which is the
figure a tax return is filed from. A cross-tenant read is somebody else's
liability to a revenue authority.

────────────────────────────────────────────────────────────────────────────
APPEND-ONLY, BECAUSE ITS PARENT IS
────────────────────────────────────────────────────────────────────────────
`payments_allocation_append_only()` (migration 0002) already refuses UPDATE and
DELETE on `allocations` at any time, on BR-PAY-031's rule: *"Reapply = reversing
allocation rows + new rows, reason + audit; never edits."* A child that could be
edited would be a back door into the same fact — somebody could leave the parent
row untouched and rewrite what the money met, which changes a tax figure and
leaves the allocation looking undisturbed. So the child takes the same law rather
than a weaker one, for the reason `payments/0013` gives about match sets: a
guarantee that lives on only one of two doors simply moves to whichever door a
caller happens to use.

**A CORRECTION IS A NEW ALLOCATION WITH ITS OWN NEGATIVE BREAKDOWN**, exactly as
BR-PAY-031 already prescribes for the parent. Nothing here needs a reversal verb
of its own.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every law here is ALSO enforced at the service layer and every
database-dependent case carries `requires_postgres` and SKIPS there rather than
passing vacuously.
"""

from django.db import migrations

TABLE = "allocation_classes"

#: B2 §3's template. Deny-by-default: with `app.tenant_id` unset,
#: `NULLIF(…, '')::uuid` is NULL and the comparison is NULL, so NO row is
#: visible and no row may be written.
RLS_SQL = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
"""

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template, so a lone `%` in a RAISE
#: aborts the migration. Every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as payments/0002, 0005 and 0013.
APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION payments_allocation_class_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-PAY-031 / hard rule 4: allocation_classes is append-only (attempted %%). What a payment met inside a bill is financial history and a tax return is filed from it. A correction is a reversing allocation with its own negative breakdown, never an edit to this row.',
    lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_allocation_class_append_only ON allocation_classes;
CREATE TRIGGER trg_allocation_class_append_only
  BEFORE UPDATE OR DELETE ON allocation_classes
  FOR EACH ROW EXECUTE FUNCTION payments_allocation_class_append_only();
"""

DROP_APPEND_ONLY_SQL = """
DROP TRIGGER IF EXISTS trg_allocation_class_append_only ON allocation_classes;
DROP FUNCTION IF EXISTS payments_allocation_class_append_only();
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL)


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


def apply_append_only(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(APPEND_ONLY_SQL)


def drop_append_only(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_APPEND_ONLY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0015_cr060_t7d_allocation_classes"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_append_only, drop_append_only),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/11-change-requests.md CR-060 §7 C19 + §12 task T7d ·
#         04-docs/02-decisions/02-database-design-brief.md §3 (the signed RLS
#         template, applied verbatim) · apps/payments/migrations/0002 (the
#         parent's append-only trigger, whose law this repeats) ·
#         04-docs/05-modules/07-payments/02-business-rules.md BR-PAY-031 ·
#         CLAUDE.md hard rules 1 and 4
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI)
#         F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING)
# gates: makemigrations --check clean · the RLS and append-only cases carry
#         requires_postgres. **THEY WERE RUN ON A REAL POSTGRESQL BY THIS LANE**
#         and the trigger's refusal is quoted in
#         06-backend/tests/test_cr060_t7d_allocation_classes.py — which is the
#         difference from payments/0013, whose own exceptions block reports that
#         nothing in it was proved on a live cluster
# exceptions: (1) no new `db/rls_*.sql` file — this is ONE table and the
#         template is applied inline, the shape payments/0013 uses · (2) there
#         is no unmatch/dissolve path and none is invented: a correction is a
#         reversing allocation with its own negative breakdown, which BR-PAY-031
#         already rules for the parent
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
