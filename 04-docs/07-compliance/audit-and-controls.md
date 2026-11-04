# Audit & Controls Map (SOC 2-oriented)

What buyers' security questionnaires ask vs where this repo answers.

| Control area | Mechanism | Where |
|---|---|---|
| Logical tenant isolation | Postgres RLS ENABLE+FORCE, session GUC, isolation test suite | B2 §3, 06-backend/core/rls.py, 06-backend/tests/test_tenant_isolation.py |
| Change management | PR review + CODEOWNERS + CR records | .github/, 11-change-management/ |
| Financial integrity | Append-only triggers, balanced-journal constraint, golden tests | B2, 06-backend/tests/ |
| Audit trail | audit_log on every money action, append-only, 7-yr retention | apps/audit, B8 rule 7 |
| Access control | 3 predefined roles, server-side enforcement, 2FA | A4, 06-backend/core/permissions.py |
| Secrets management | no secrets in repo, gitleaks in CI + pre-commit, per-tenant creds encrypted | security-scan.yml |
| Availability | 99.9% target, backup/restore runbook | B6, 04-docs/08-runbooks/ |
| Vendor management | provider-agnostic seams, per-tenant enablement | B7, apps/integrations |

Formal SOC 2 engagement: not started (pre-revenue). This map keeps the evidence collectible from day one.
