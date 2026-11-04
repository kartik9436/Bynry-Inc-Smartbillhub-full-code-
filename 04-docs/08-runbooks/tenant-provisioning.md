# Runbook — Tenant Provisioning
Trigger: signup wizard completes (S6) or manual creation.
1. POST /tenants is idempotent (A11) — retries must not double-provision.
2. Creates: tenant row, Owner (System Admin) membership, subdomain, tenant_services, trial (14-day).
3. If "load defaults" checked: seed lookup tables from apps/tenancy/fixtures/lookup_defaults.json.
4. Verify: RLS context works (a test query under the new tenant_id), welcome email queued via connected mailbox (or held until email connect).
Rollback: tenant flagged failed + support alert. Never leave a half-seeded tenant active.
