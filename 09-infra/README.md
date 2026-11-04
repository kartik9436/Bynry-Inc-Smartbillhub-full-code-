# Infra

> ⚠ **BEFORE ANY FIRST DEPLOY: `10-scripts/13-provision-database.sh`.** A brand-new
> PostgreSQL database **cannot run `migrate`** — it fails inside PostgreSQL's own
> foreign-key validation scan with `unrecognized configuration parameter "app.tenant_id"`,
> because `FORCE ROW LEVEL SECURITY` applies the tenant policy to the table owner and the
> table owner is whoever runs the migration (DEF-622, 2026-08-24). The script provisions
> the role, the database, the `app.tenant_id` session default and the extensions, then
> migrates and verifies. `01-deployment-architecture.md` §5 **step 0** is the reasoning.
> **On an already-provisioned deployment nothing you pull or redeploy applies it** — one
> `ALTER DATABASE … SET app.tenant_id` per existing database, by hand, once.

- **`01-deployment-architecture.md`** — the architecture (living doc, **r3**): what the
  platform is, which laws bind it, scaling phases P0–P3, DR, telemetry, SOC 2 / NIST
  control mapping, decision ledger. Read once for the *why*.
- **`02-aws-runbook.md`** — the **executable AWS handover** a DevOps engineer works
  from (**r2**): prerequisites, concrete service choices with cost bands, ordered deploy
  steps with verifications, exact environment variables, the single-name certificate,
  the `/api/*` edge routing rule and the SPA's index.html fallback, the psql RLS proofs,
  day-one operations, an honest not-ready list, and the decisions handed back. **§0.0 is
  a changelog** — read it first if you are holding a printed copy, because r1 assumed a
  different tenancy model.
- **`03-deploy-dry-run.md`** — the **five checks to run against a clean PostgreSQL
  database before a deploy**, each a measurement rather than a reading: migrations
  from zero · every tenant table actually isolated (149 tables, 148 guarded, 1
  interrogated exemption) · partitioning real and not merely declared · defaults
  failing closed · migrations reversing losslessly. Written because the gates read
  code and this reads a database, which is the only way to catch a table declared
  partitioned and never migrated, or a `.env` default that fails open. It ends with
  an explicit list of what it does **not** cover — it never boots the image.
- **`docker/`** — Dockerfiles for local/full-profile compose only. **Not production
  artifacts**, and they still reference the pre-rename `backend/` and `frontend/` paths
  (see 01 §13 items 1–2).

**Decided (PO 2026-08-10):** cloud = **AWS**; domain = **`smartbillhub.bynry.com`**;
posture = a sandbox that must behave like production (internal demo tenant, then real
customers on the same environment); operated by a **DevOps engineer**. Region pair, IaC
tooling, the edge shape and sizing remain OPEN-FOR-DEVOPS — record them in
`12-governance/02-decision-log.md`.

⚠ **Changed the same day (PO 2026-08-10): tenancy is PATH-based, not subdomain-based.**
Screens live at `smartbillhub.bynry.com/{tenant}/…` and the API at
`smartbillhub.bynry.com/api/{tenant}/…`. Consequences for whoever is provisioning
infrastructure: **no wildcard certificate** (ACM needs one name), **no wildcard DNS**
(one A/ALIAS record), `ALLOWED_HOSTS` is one host with no leading dot, and the edge
splits on `/api/*` while preserving the path verbatim. One origin also means the browser
no longer isolates tenants — the session-to-tenant binding and its 404 refusal are the
control that replaces it (01 §10.4).

**Standing requirements:** US data residency (B6) · PostgreSQL 16 with RLS FORCE on
every tenant table · daily full backup + PITR (RPO 1h / RTO 4h) · 99.9% uptime target ·
7-year retention on financial and audit records.

**No gate machine-checks this directory.** Nothing in `10-scripts/gates/`,
`10-scripts/02-trace_lint.py` or `.github/workflows/` reads `09-infra/`. A green CI run
says these documents broke nothing else; it says nothing about whether they are right.
Both documents cite the repo files behind each claim so a reader can re-check them.
