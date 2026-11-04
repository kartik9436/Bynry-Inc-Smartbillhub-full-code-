# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 · US-PAY-016 · US-PAY-017 · US-PAY-018
#           Screens: S21 · S24 · S33 · S34 · S35
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS ENABLE + FORCE) · rule 4's
#           reasoning applied to a notice trail (a record of what a customer was
#           told is not a record if it can be rewritten) · BR-PAY-017 (J4
#           step-2: every send AND skip appended) · NFR-10 (isolation — release
#           blocker)
# ───────────────────────────────────────────────────────
"""payments 0008 — isolation for the plan/collections tables, and the trail's freeze.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path, and the append-only trigger
is hard rule 4's shape). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the
PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies
the SIGNED B2 §3 template verbatim, the same shape as `0002` and `0005`.

WHY `notice_history` IS APPEND-ONLY AND THE OTHER FOUR ARE NOT. It is the record
a utility produces when a customer says *"nobody ever told me you were going to
cut me off"* — and a record that can be edited afterwards does not answer that
question. The other four tables hold STATE that is supposed to change: a plan
moves proposed → active → closed, an instalment gets paid, a ladder advances a
tier, a returned envelope gets resolved. Freezing those would freeze the
product.

Postgres only. SQLite has neither RLS nor triggers and the developer test
database is SQLite, so the append-only half is ALSO enforced at the service
layer (`notices.record_notice` is the only writer and never updates) and
asserted in tests — a check that skips silently on the database a developer
actually runs is not a check.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE payment_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_plans FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_plans_tenant_isolation ON payment_plans;
CREATE POLICY payment_plans_tenant_isolation ON payment_plans
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE payment_plan_installments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_plan_installments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_plan_installments_tenant_isolation ON payment_plan_installments;
CREATE POLICY payment_plan_installments_tenant_isolation ON payment_plan_installments
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE notice_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE notice_history FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notice_history_tenant_isolation ON notice_history;
CREATE POLICY notice_history_tenant_isolation ON notice_history
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE account_collection_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_collection_state FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_collection_state_tenant_isolation ON account_collection_state;
CREATE POLICY account_collection_state_tenant_isolation ON account_collection_state
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE delivery_return_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE delivery_return_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS delivery_return_events_tenant_isolation ON delivery_return_events;
CREATE POLICY delivery_return_events_tenant_isolation ON delivery_return_events
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION payments_notice_history_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-PAY-017 / J4 step 2: notice_history is APPEND-ONLY — it is the record of what a customer was actually told, so %% is refused. A correction is a new row.',
    lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notice_history_append_only ON notice_history;
CREATE TRIGGER trg_notice_history_append_only
  BEFORE UPDATE OR DELETE ON notice_history
  FOR EACH ROW EXECUTE FUNCTION payments_notice_history_append_only();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS trg_notice_history_append_only ON notice_history;
DROP FUNCTION IF EXISTS payments_notice_history_append_only();
DROP POLICY IF EXISTS delivery_return_events_tenant_isolation ON delivery_return_events;
ALTER TABLE delivery_return_events NO FORCE ROW LEVEL SECURITY;
ALTER TABLE delivery_return_events DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_collection_state_tenant_isolation ON account_collection_state;
ALTER TABLE account_collection_state NO FORCE ROW LEVEL SECURITY;
ALTER TABLE account_collection_state DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notice_history_tenant_isolation ON notice_history;
ALTER TABLE notice_history NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notice_history DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_plan_installments_tenant_isolation ON payment_plan_installments;
ALTER TABLE payment_plan_installments NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_plan_installments DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_plans_tenant_isolation ON payment_plans;
ALTER TABLE payment_plans NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_plans DISABLE ROW LEVEL SECURITY;
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)
    schema_editor.execute(APPEND_ONLY_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0007_w5_plans_and_collections"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-017@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — policy SQL) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: APPLIED TO POSTGRES, not only to the SQLite test tier (DEF-064) — see
#         the lane report for the verbatim `migrate` output and the isolation run
# exceptions: The append-only trigger is Postgres-only, so on SQLite the
#         guarantee is the service layer plus the test — stated rather than
#         implied, because a docstring claiming a guarantee the schema does not
#         have is hard-won law 1 and this repo has paid for it once.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
