# SMARTBillHub

Multi-tenant, self-serve **meter-to-cash + finance** SaaS for **North American utilities of up to 40,000 accounts, run by at most 10–20 staff** — the PO's tiers **T7 (≤3,000) · T6 (3–10K) · T5 (10–40K)**, all three in scope now, with **T4 (40–80K) and T3 (80–160K) explicitly later**. Bills **eleven** services per account, in seed order — Electric · Water · Gas · Sewer · Trash · **Storm water** · **Solar** · Broadband · **Thermal/Heat** · **Battery** · **Fire** (BR-RAT-024).

⚠ **This sentence read *"small utilities and sub-metering companies (< ~3,000 connections, typically 1–2 operators)"* and *"ten services"* until 2026-09-06.** The connection ceiling was not wrong, it was the bottom tier — **T7 is still in scope** — so the ceiling moved **3,000 → 40,000**; the operator count was simply false and is now **10–20 staff**, ruled. **Fire** became the eleventh service on 2026-09-02 (`CR-063`). The ICP ruling, the PO's words and every consequence are in `12-governance/02-decision-log.md`, 2026-09-06 — *"THE ICP, CORRECTED THE SAME HOUR"*. **T4/T3 need no work now beyond one thing: keeping the architecture free of per-tenant caps and unpaginated lists** (`NFR-5`, `NFR-3`). ⚠ **The public Pricing page still tops out at 3,000 on purpose** — a dated deferral until the pricing-model work (`DEF-TEN-4222`); those three bands are not a bug and must not be "fixed".

> ⚠ **This line said SIX until 2026-08-25** — Electric, Water, Gas, Sewer, Trash/Waste, Broadband — while the platform seed had carried ten since BR-RAT-024 was confirmed, and CLAUDE.md was corrected to ten on 2026-08-16. **The README is the first file a new session reads**, so it was the last place the staleness could still mislead one. Four services were missing from it: storm water, solar, thermal/heat and battery — and each of those is a whole billing surface, not a label. It is recorded rather than quietly edited because the PO named this drift explicitly: *"Ten services, not six … CLAUDE.md itself said 'six' until 2026-08-16 while the seed carried ten."*

**Stack:** React · Django/Python · PostgreSQL 16 · modular monolith (nine domain modules + audit).

> **Status: documentation COMPLETE — build gate OPEN (2026-08-08).** All 14 module packs authored (227 stories), every open question closed, and finance has SIGNED the money-math rules (B4) and golden tests (B5, GT-1..61; verification harness 33/33). Build proceeds on the wave plan.
>
> ⚠ **Two numbers, and they are not interchangeable (DEF-2846).** The harness's
> **33** is DOCUMENT self-consistency — it recomputes B4/B5's own figures and
> imports no application code, so it cannot go red when the engine drifts. What
> runs the engine is `06-backend/tests/golden/`, and that is **engine-verified:
> 14 of the 61 signed GTs**. Quote both; `python3
> 10-scripts/gates/g64_golden_engine_coverage.py --report` prints them.

## Repository map

| # | Folder | What it is |
|---|--------|------------|
| 1 | root files | Governance: security policy, contribution rules, dev setup |
| 2 | [`CLAUDE.md`](CLAUDE.md) | Operating rules for AI-assisted sessions — read every session |
| — | [`HUMAN-GUIDE.md`](HUMAN-GUIDE.md) | The human counterpart: how people read and safely update docs, code, and tests |
| 3 | [`.github/`](.github/) | CI pipelines, PR/issue templates, CODEOWNERS |
| 4 | [`04-docs/`](04-docs/) | **The contract**: spec A1–A19, decisions B1–B10, ADRs, 14 module docs (epics → stories), compliance, runbooks, UAT |
| 5 | [`05-prototype/`](05-prototype/) | Runnable clickable design reference — layout/copy/flows only, never ported |
| 6 | [`06-backend/`](06-backend/) | Django modular monolith — one app per domain module |
| 7 | [`07-frontend/`](07-frontend/) | React + Vite + Modernist design tokens |
| 8 | [`08-qa/`](08-qa/) | Cross-stack QA automation: E2E, contract, regression |
| 9 | [`09-infra/`](09-infra/) | Deployment architecture + the AWS runbook handed to DevOps |
| 10 | [`10-scripts/`](10-scripts/) | Bootstrap + demo-tenant seeding |
| 11 | [`11-change-management/`](11-change-management/) | Release approvals, cutover/rollback plans, tenant comms, training |
| 12 | [`12-governance/`](12-governance/) | Weekly status reports, risk register, decision log, metrics |

## Plan of record
**14 modules · 77 epics · ~183 stories** (04-docs/05-modules/, Modules→Epics→Stories, 8-section story format). Build/doc waves W0–W8 (ADR-005); documentation runs one wave ahead of build. Open decisions: `12-governance/01-open-questions.md` — all routed to the Product Owner.

## Where the truth lives

- **What to build:** `04-docs/01-spec/` (A1–A19, extracted from the design; screen IDs S1–S114 per A1 + addenda — S49–S68 PM-assigned/ratified, S69–S90 reserved).
- **How to build it:** `04-docs/02-decisions/` (B1–B8 — architecture, database DDL, money math, golden tests).
- **Stable interfaces:** `04-docs/03-contracts/` (API A11, schema B2, enums A5, glossary A16).
- **Per-module product docs:** `04-docs/05-modules/<module>/` — overview, user stories, business rules, flows.
- **Traceability:** `04-docs/10-traceability-matrix.md` — story ↔ screen ↔ rule ↔ test.

## Quickstart (dev)

**Postgres 16 is external and yours** — there is no database container. Point `DATABASE_URL` at one (local, RDS, anything) and the two application containers do the rest.

```bash
./10-scripts/01-bootstrap.sh              # creates 06-backend/.env + 07-frontend/.env from their templates
# edit 06-backend/.env → DATABASE_URL, DJANGO_SECRET_KEY

# provision the database BEFORE the first boot — a brand-new database cannot migrate
# without this and the error does not say so (DEF-622). Needs a DBA/superuser connection.
export DATABASE_URL=…  DJANGO_SETTINGS_MODULE=config.settings.local  SBH_DB_PASSWORD=…
./10-scripts/13-provision-database.sh --all   # role, database, app.tenant_id default,
                                             # extensions, then migrate STEP BY STEP

make up                                   # build + start both images  →  http://localhost:8080
make seed                                 # Brazos Bend demo fixture — demo/staging only, NEVER prod
```

**Why a database needs provisioning at all.** Every tenant table carries `FORCE ROW LEVEL
SECURITY`, and `FORCE` applies the tenant policy to the *table owner* — which is whoever
runs migrations. PostgreSQL validates a new foreign key with an ordinary scan, so the policy
is evaluated during `migrate` itself and a database with no `app.tenant_id` session default
fails with `unrecognized configuration parameter "app.tenant_id"`. The provisioning script
sets that default to the nil UUID: it casts, so the policy evaluates instead of erroring,
and it matches no row, so deny-by-default is unchanged and nothing is granted to anybody.
The migrations are then applied **one per process, in dependency order** (PO ruling
2026-08-24, OQ-354), so a data step that clears tenant context cannot poison the
foreign-key validation of the steps after it. **No role is ever granted `BYPASSRLS`** —
the script refuses that flag by name and `--verify` fails the run if the app role holds
superuser or bypass from anywhere else.
**On a database that already exists**, this is one command run by hand, once — a redeploy
will not do it for you: `psql "$DATABASE_URL" -c "ALTER DATABASE \"<db>\" SET app.tenant_id
= '00000000-0000-0000-0000-000000000000'"`. Details in `09-infra/01-deployment-architecture.md`
§5 step 0 and `06-backend/db/001_tenant_context_default.sql`.

Two containers, **one published port**: the frontend serves the SPA and passes `/api/*` through to the backend over the compose network, so the app is same-origin by construction and the httpOnly session cookie just works. The backend publishes no host port at all. TLS to your database is a knob, not an edit, and it defaults to **encrypted** — a local Postgres without TLS needs `DB_SSLMODE=disable make up`. No nginx, no DNS, no load balancer — the edge is managed outside this repo (PO ruling 2026-08-10). `make help` lists every target.

Prefer host-run dev servers? `cd 06-backend && pip install -e '.[dev]' && python manage.py migrate && python manage.py runserver` and `cd 07-frontend && npm ci && npm run dev`.

**Tenant in the path, not the host** (PO ruling 2026-08-10): the tenant is the first URL segment — SPA `/{tenant}/…`, API `/api/{tenant}/…` — resolved from the path and cross-checked against the session, never from client input (BE-01). So a seeded demo opens at `http://localhost:8080/brazosbend`. `/`, `/pricing` and `/signup` carry no tenant, and a session pointed at a *different* tenant's URL gets **404, never 403** — a wrong tenant must be indistinguishable from a nonexistent one. Playwright E2E points `E2E_BASE_URL` at a running frontend (default `http://localhost:5173`, the Vite dev server).

`seed_demo` writes only through the real provisioning services and refuses honestly while a required lane is missing (identity owner seam, audit sink) — run `python manage.py seed_demo --check` for a write-free readiness report. Production images are the two multi-stage Dockerfiles used above (`06-backend/Dockerfile`, `07-frontend/Dockerfile`); the AWS deployment is 09-infra/02-aws-runbook.md.

## Hard rules (see CLAUDE.md for the full list)

1. Never touch a tenant table without `app.tenant_id` set — RLS `FORCE` is the isolation boundary.
2. Money is `NUMERIC(18,6)` + `CHAR(3)` currency. Never float, never integer cents.
3. No `UPDATE`/`DELETE` on issued invoices, invoice lines, payments, journal entries — corrections are new rows.
4. Only the ledger posting service writes journal lines, in balanced pairs.
5. Every money action writes an `audit_log` row.
