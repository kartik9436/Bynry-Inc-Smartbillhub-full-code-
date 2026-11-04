# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-018 · US-BIL-019 · US-BIL-020   Screens: S30
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS ENABLE + FORCE) · CLAUDE.md
#           rule 4's reasoning applied to a derivation trail (US-BIL-019 TC-6:
#           the variance balance derives from APPEND-ONLY bill events, so an
#           event row cannot be updated or deleted) · BR-BIL-017 · NFR-10
#           (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""billing 0013 — tenant isolation for the budget tables, and TC-6's append-only.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path, and the append-only trigger
is hard rule 4's shape). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under
the PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.
Applies the SIGNED B2 §3 template verbatim, the same shape as `0002` and
`0004`, and invents no policy of its own.

WHY BOTH TABLES NEED THE POLICY. `account_budget_status` names an account and
the amount that account pays every month; `account_budget_events` is the trail
of every change to it. Neither is metadata — one of them IS what a customer is
asked for.

THE APPEND-ONLY TRIGGER IS US-BIL-019 TC-6, NOT DECORATION. The test case reads
*"Variance recomputed by editing the stored balance directly → Rejected; the
balance derives from bill events append-only"*. `account_budget_status.
variance_balance` is a CACHE of these rows, so if a row can be edited the
balance can be invented, and the settle-up would collect or credit a figure
nobody can reconstruct. `apps/billing/models.py` says in its own docstring that
a Django model cannot refuse a `.save()`; the same is true here, so the
guarantee is a trigger and not a promise — the exact reasoning `0002` records.

Postgres only. SQLite has neither RLS nor these triggers and the developer test
database is SQLite, so the append-only half is ALSO asserted at the service
layer (`budget_service.record_event` is the only writer) and in
tests/test_us_bil_019_budget_bill.py — a check that skips silently on the
database a developer actually runs is not a check.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE account_budget_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_budget_status FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_budget_status_tenant_isolation ON account_budget_status;
CREATE POLICY account_budget_status_tenant_isolation ON account_budget_status
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

ALTER TABLE account_budget_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_budget_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_budget_events_tenant_isolation ON account_budget_events;
CREATE POLICY account_budget_events_tenant_isolation ON account_budget_events
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""

APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION billing_budget_event_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'US-BIL-019 TC-6: account_budget_events is APPEND-ONLY — the budget variance balance DERIVES from these rows, so %% is refused. A correction is a new event row.',
    lower(TG_OP);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_budget_event_append_only ON account_budget_events;
CREATE TRIGGER trg_budget_event_append_only
  BEFORE UPDATE OR DELETE ON account_budget_events
  FOR EACH ROW EXECUTE FUNCTION billing_budget_event_append_only();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS trg_budget_event_append_only ON account_budget_events;
DROP FUNCTION IF EXISTS billing_budget_event_append_only();
DROP POLICY IF EXISTS account_budget_events_tenant_isolation ON account_budget_events;
ALTER TABLE account_budget_events NO FORCE ROW LEVEL SECURITY;
ALTER TABLE account_budget_events DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_budget_status_tenant_isolation ON account_budget_status;
ALTER TABLE account_budget_status NO FORCE ROW LEVEL SECURITY;
ALTER TABLE account_budget_status DISABLE ROW LEVEL SECURITY;
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
        ("billing", "0012_w4_budget_billing"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-018@e9d5a48 (ships with 0012 — co-packets US-BIL-019@e9d5a48 · US-BIL-020@e9d5a48)
# generated: 2026-08-11 by story-coder (W4 budget-billing lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED 2026-08-11, not claimed — `ruff check apps` **All checks passed!** · `black --check --line-length 100 apps tests` **402 files would be left unchanged** · `python manage.py makemigrations --check` **No changes detected** · `pytest tests -m "not golden and not isolation" -q` **1 failed, 1771 passed, 38 skipped, 127 deselected in 439.43s** — the one failure is `test_us_cus_003_tc1` (`link_customer() missing 1 required keyword-only argument: 'account_id'`), the CUSTOMER-ENTITY lane's change to apps/customers/services.py, a file this lane never opened · `pytest tests -m golden -q` **23 passed, 1913 deselected, 1 xfailed** · `pytest tests -m isolation -q` **23 passed, 80 skipped, 1834 deselected** · `10-scripts/03-golden-verify.py` **33 PASS, 0 FAIL** (unchanged baseline) · `10-scripts/gates/run_gates.py` **14 PASS/4 FAIL/1 SKIP, then 15 PASS/3 FAIL/1 SKIP on the last run** as a neighbouring lane fixed its own — the count moved between runs because three other lanes were committing throughout, which is why it is quoted as a range rather than as one number. The lane's own baseline at start was **18 PASS/0 FAIL/1 SKIP** and **every failure across every run named another lane's file**: G6 apps/payments/lockbox.py:106 (since fixed by that lane), G7 db/rls_payments_refunds.sql + rls_payments_w5.sql + apps/payments/migrations/0005+0006, G10 US-PAY-010, G15 de.json customers.account.customer.identity. **NONE named a file this lane wrote**, and the one G7 row that DID — apps/billing/migrations/0013 — was fixed here by adding its full repo-relative path to the review ledger. REPORTED rather than smoothed: this lane cannot fix payments or the i18n catalogues and did not try.
# exceptions: (1) The append-only trigger is Postgres-only, so on SQLite the
#         guarantee is the service layer plus the test — stated rather than
#         implied, because a docstring claiming a guarantee the schema does not
#         have is hard-won law 1 and this repo has paid for it once.
#         (2) `account_budget_status` is deliberately NOT frozen: the level, the
#         override and the cached balance are supposed to change, and the trail
#         that makes those changes reconstructible is the events table.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
