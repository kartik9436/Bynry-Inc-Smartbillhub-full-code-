# 09-infra/01 — Deployment Architecture (DevOps Handover)

> ### ▶ The executable path is now `09-infra/02-aws-runbook.md`
> **PO rulings 2026-08-10 closed four of this document's open items:** posture =
> *sandbox that must behave like production* (internal demo tenant first, then real
> pipeline customers on the **same** environment — so backups, tenant isolation and
> monitoring are **day-one**, the P0→P1 band); cloud = **AWS**; domain =
> **`smartbillhub.bynry.com`**; operated by a **DevOps engineer**.
>
> ### ⚠ FIFTH RULING, SAME DAY — TENANCY IS PATH-BASED, NOT SUBDOMAIN-BASED
> **r2 of this document said "tenants at `<subdomain>.smartbillhub.bynry.com`". That is
> superseded.** URLs are now `smartbillhub.bynry.com/{tenant}/…` for screens and
> `smartbillhub.bynry.com/api/{tenant}/…` for the API; the public surface (`/`,
> `/pricing`, `/signup`, `/api/public/…`, `/api/tenants`, `/api/jobs/{id}`,
> `/api/exports…`) carries no tenant. Built and green on both sides of the stack
> (decision-log rows of 2026-08-10; `06-backend/core/tenancy.py`,
> `07-frontend/src/routing/tenantPath.ts`). The Eng-Lead's objection — that
> path-now/subdomain-later pays for two migrations — was recorded and **overruled**;
> this is a permanent choice, not a stopgap.
>
> **What it deletes from this document's r2 text:** the wildcard TLS certificate, the
> wildcard DNS record, the leading-dot `ALLOWED_HOSTS` form, the `VITE_TENANT_HOST_SUFFIX`
> build variable, and the "Host is the tenant resolver" rule (§10 is rewritten
> accordingly). **What it adds:** one origin now serves every tenant, so the browser no
> longer isolates them — the session-to-tenant binding and its 404 refusal are the
> control that replaces host isolation (§10.9).
>
> **This document remains the architecture** — what the platform is, which laws bind it,
> and why. **`02-aws-runbook.md` is the step-ordered, AWS-specific runbook a DevOps
> engineer executes**: prerequisites, concrete service picks with cost bands, ordered
> deploy steps with verifications, the exact environment variables, the single-name
> certificate, the `/api/*` edge routing rule, the psql RLS proofs, day-one ops, an
> honest not-ready list, and the decisions handed back. Read this document once for the
> *why*; work from 02 for the *how*. Where the two differ, 02 is newer — the deltas are
> marked ⚠ there and amended here.
>
> **The GCP column in §2 is retained as REFERENCE ONLY — AWS is the chosen path
> (PO 2026-08-10).** It is kept because it documents the portability the architecture
> was designed for; it is not a live option and must not be built.

> **LIVING DOCUMENT — version r3 (2026-08-10; r2 2026-08-10 same day; r1 2026-08-09,
> pre-R1 draft).** Updated at every release
> boundary (R1–R4, see §11); the R1 PO walkthrough includes handing this document to the
> incoming DevOps engineer (B12 Addendum r6, expanded by PO mandate 2026-08-09: scaling
> phases, AWS/GCP mapping, DR, telemetry, compliance controls). Owner: Eng-Lead until
> handover, then DevOps.
>
> **No gate machine-checks `09-infra/`** — no gate script, workflow or lint reads this
> directory. Everything asserted here about the code was verified by reading the code,
> file by file, on the date in the revision line.
>
> **How decisions are marked in this doc:**
> - **DECIDED** — already ruled by the project's decision registers (cited as TD-n from
>   `04-docs/02-decisions/01-architecture-decisions.md`, NFR-n from
>   `04-docs/02-decisions/06-non-functional-requirements.md`, SC-n from
>   `04-docs/07-compliance/soc2-nist-mapping.md`, or BR-/B-doc IDs). You implement these;
>   you do not re-litigate them.
> - **OPEN-FOR-DEVOPS** — deliberately left for you to decide at handover (provider,
>   tooling, sizing). Record your choices in `12-governance/02-decision-log.md`
>   (there is already a PENDING row: "Hosting/cloud + region").
> - **ESTIMATE** — cost bands and tuning thresholds in §7 are order-of-magnitude planning
>   figures, not commitments.
>
> You should not need to dig through the repo to act on this document. Where a repo file
> matters operationally, it is named here with its path.

---

## 0. What you are deploying (60-second orientation)

SMARTBillHub is a **multi-tenant meter-to-cash + finance SaaS for North American
utilities** (electric/water/gas/sewer/trash/broadband and five more; tenants are
utilities with **10–20 staff** and roughly a few hundred to **40,000** customer
accounts each — the PO's tiers **T7 ≤3,000 · T6 3–10K · T5 10–40K**, all three in
scope, with T4 and T3 explicitly later). ⚠ **The staff figure read *"1–2 staff"*
until 2026-09-06**; the account range was already right. See
`12-governance/02-decision-log.md`, 2026-09-06, *"THE ICP, CORRECTED THE SAME
HOUR"*. **No sizing in this document changes as a result** — it was already written
against a 40,000-account tenant — **but the operator-facing consequence is that
concurrent back-office sessions per tenant are now planned in tens, not in twos.**
It is:

- **One deployable Django application** (modular monolith, TD-2) — not microservices.
  There is exactly one backend artifact to build, and it runs in **four shapes as of
  2026-08-31**: web (WSGI), the default Celery worker, **a Celery worker consuming
  billing's own named queue**, and Celery beat. The fourth exists because a CPU share
  cannot be aimed at a queue with no name — PO ruling 2026-08-31, CR-051 task 29; the
  reasoning and the two operator-changeable numbers are in `docker-compose.yml` beside
  the service.
- **PostgreSQL 16 + Redis** (TD-3). Postgres is not just storage — it is the **tenant
  isolation boundary**: every tenant table has Row-Level Security with `FORCE`, keyed on a
  per-connection setting `app.tenant_id` (TD-4, NFR-10). This has direct ops consequences
  (connection pooling, bootstrap order, restore testing) called out below.
- **A React/Vite frontend that compiles to static files** (TD-1). In production nothing
  runs Node; the reverse proxy/CDN serves the built bundle.
- **Financially regulated data.** 7-year retention on financial and audit records
  (NFR-7), append-only financial tables (NFR-15), US data residency (B6). Backups are a
  compliance requirement here, not a nicety.
- **Deliberately small at the start.** The PO's own framing: "initially there will not be
  many utilities — 1, 5 or 10; then volume will increase." The infrastructure grows
  through the four phases in §7; do not build Phase P3 on day one.

Two ops-relevant laws from `CLAUDE.md` you must never design around:
1. Nothing may query a tenant table without `app.tenant_id` set — RLS FORCE denies by
   default (an unset value fails the UUID cast, returning zero rows, never wrong rows).
2. Financial rows (issued invoices, invoice lines, payments, journal entries) are never
   UPDATEd or DELETEd — so there is no "cleanup job" that trims financial tables, ever
   (NFR-25). Growth is managed by partitioning + cold storage, not deletion.

---

## 1. Topology (diagram as text)

```
                        Internet
                           │
                 ┌─────────▼──────────┐
                 │   Reverse proxy /  │  TLS termination (ONE name, smartbillhub.bynry.com, §10)
                 │   load balancer    │  Serves the static frontend build (SPA)
                 │  (AWS: ALB, §2)    │  Splits on PATH:  /api/* → Django,  * → SPA
                 └───┬────────────┬───┘  (never rewrites the path — it carries the tenant)
        static files │            │ API (HTTP; /api/{tenant}/… — the PATH is the tenant key)
        (+ index.html│            │
         fallback)   │            │
      ┌──────────────▼──┐   ┌─────▼──────────────────────┐
      │ Frontend build  │   │  Django web (WSGI)         │  DRF API (TD-19)
      │ (vite dist/,    │   │  ≥2 replicas for HA        │  TenantContextMiddleware:
      │  no runtime)    │   │                            │  path segment → SET app.tenant_id
      └─────────────────┘   └──┬──────────────┬──────────┘
                               │              │
                     enqueue   │              │ SQL (RLS FORCE on every tenant table)
                     async jobs│              │
                        ┌──────▼─────┐  ┌─────▼──────────────┐
                        │  Redis 7   │  │  PostgreSQL 16     │  partitioned big-five (§8)
                        │  (Celery   │  │  daily full + PITR │  7-yr financial retention
                        │   broker)  │  │  (§6)              │
                        └──────┬─────┘  └─────▲──────────────┘
                               │              │ SQL (jobs set app.tenant_id explicitly
                        consume│              │      per tenant — core/tenancy.py
                  ┌────────────▼───────────┐  │      tenant_context())
                  │ Celery workers (same   ├──┘
                  │ image as web; queues:  │
                  │ bill runs · imports ·  │──────► Object storage (S3-compatible, TD-15):
                  │ outbound dispatcher ·  │        uploads, e-signed docs, import files,
                  │ archival · estimation) │        report files. Per-tenant prefixes.
                  ├────────────────────────┤
                  │ Celery beat (EXACTLY 1 │──────► External providers (behind seams):
                  │ instance — scheduler)  │        BYO mailbox/ESP email (W6) · Stripe/
                  └────────────────────────┘        Plaid (W7) · Twilio SMS (W8)
```

Component inventory:

| Component | Runs what | Source in repo | Status |
|---|---|---|---|
| PostgreSQL 16 | data + RLS isolation + partitions | schema authored from `04-docs/02-decisions/02-database-design-brief.md` (B2 r16) | **DECIDED** (TD-3, TD-4) |
| Redis 7 | Celery broker (and only that in v1) | — | **DECIDED** (TD-3, TD-17) |
| Django web | DRF API, tenant middleware `core.tenancy.TenantContextMiddleware` | `06-backend/` | **DECIDED** (TD-2, TD-19) |
| Celery worker — default (`-Q celery`) | imports, list exports, dispatcher, archival, estimation — all idempotent + resumable. ⚠ **NOT bill runs, since 2026-08-31** | `06-backend/config/celery.py` | **DECIDED** (TD-17, NFR-4) |
| Celery worker — **billing** (`-Q billing`) | the bill run's calculate, findings and issue (`apps/billing/run_jobs.py`), and nothing else. Carries the deployment's ONLY `deploy.resources.limits.cpus`, and a `deploy.replicas` an operator may raise — both affecting billing and no other job kind | `docker-compose.yml` → `celery-billing`; routed by `config/celery_routes.py` | **DECIDED** (PO ruling 2026-08-31, CR-051 task 29). ⚠ A named queue is TWO halves — routing AND a consumer; `G59` fails when either is missing, because routing with no consumer accepts a bill run, says `queued`, and runs nothing, for ever |
| Celery worker — **account access** (`-Q account_access`) | the instant send of an account-access email (staff invitation, staff reset, the portal reset link) — one `notifications.send_now` job per message, fired on commit (`apps/notifications/send_now.py`) | `docker-compose.yml` → `celery-account-access` | **DECIDED** (PO 2026-10-22, *"this should be instant email"*, `CR-188-BRC10`). ⚠ Law 4: a running host does not get this service from the compose file — add it to the host / task definitions. Without it the rows are still written at the highest priority and the ordinary dispatch cycle sends them, late |
| Celery beat | schedules recurring jobs (partition archival NFR-6/28, report retention NFR-9, dispatcher pacing NFR-1) | same image | **DECIDED** (TD-17). Run exactly one. |
| Frontend | static build (`npm run build` → tsc + vite) served by the proxy/CDN | `07-frontend/` | **DECIDED** (TD-1) |
| Reverse proxy / LB | TLS, static serving with an index.html fallback, `/api/*` split, path preserved verbatim | — | Function **DECIDED**; product per cloud (§2), final pick **OPEN-FOR-DEVOPS** |
| Object storage | S3-compatible, per-tenant prefixes, US region, server-side encryption, signed expiring URLs; binaries never in the DB | — | Pattern **DECIDED** (TD-15); vendor per cloud (§2) |

✅ **r2's `/api`-prefix correction is CLOSED (2026-08-10, verified against the repo).**
r2 recorded that the API was mounted at the **root** and therefore collided head-on with
the SPA's router paths, so one origin could not serve both. `06-backend/config/urls.py`
now mounts the entire API under `api/` — `/api/{tenant}/…` for tenant-scoped routes and
`/api/public/…`, `/api/tenants`, `/api/jobs/{id}`, `/api/exports…` for the surface that
carries no tenant — and `07-frontend/src/api/client.ts` prefixes `/api` on every call.
The diagram above is therefore true again, and the edge split is a single rule:
**`/api/*` → Django, everything else → the SPA.**

Two consequences the ops side owns, both in `02-aws-runbook.md` §2.4 / §7.2:
- **The SPA must fall back to `index.html`** for any path that is not a real file —
  `/{tenant}/settings/company` is a *client* route and Django serves no HTML at all. On
  CloudFront that must be a **Function on the default behaviour**, never distribution-wide
  custom error responses, which would also rewrite the API's isolation `404` into a `200`.
- **The path must survive the edge byte for byte.** The first segment after `/api/` is
  the tenant; a rewrite rule is a tenant rewrite.

**Caution — connection pooling (read before adding PgBouncer/RDS Proxy):** tenant context
is a *session-scoped* Postgres setting (`set_config('app.tenant_id', …, false)` in
`06-backend/core/tenancy.py`), set at request start and cleared in a `finally` at request
end. A **transaction-mode pooler would break tenant isolation semantics** (the setting
would not reliably travel with the transaction). If you need a pooler, use **session
mode**, or raise it with Eng — changing the tenancy kernel is a 🔒 human-review path, not
an infra tweak. The same caution applies to any replica-routing proxy (§8.4).

---

## 2. Cloud mapping — **AWS (chosen)**; GCP column retained as reference only

**DECIDED (PO, 2026-08-10): the platform runs on AWS**, in a **US region** (B6 data
residency). This supersedes the 2026-08-09 "AWS or GCP" ruling. **The GCP column below
is REFERENCE ONLY** — kept because it documents the portability the architecture was
designed for, and because it names the equivalence class each component belongs to. It
is not a live option; do not build it.

**Still OPEN-FOR-DEVOPS:** which US region pair (primary + DR copy region — both must be
US).

▶ **For the AWS column, `02-aws-runbook.md` §2 is the executable version**: the same
rows with instance classes, why-this-not-that reasoning, cost bands and ordered steps.
Two deliberate divergences are recorded there — row 5's CloudFront is deferred to P1
(ALB direct at P0, so nothing can rewrite `Host`), and row 1's `pg_uuidv7` question is
closed (not on the RDS allowlist, and not needed: PKs are generated app-side by
`core/dbfields.py`).

| # | Component (from §1) | **AWS — CHOSEN** | GCP *(reference only)* | Notes |
|---|---|---|---|---|
| 1 | PostgreSQL 16 | RDS for PostgreSQL 16 (Multi-AZ from P1, §7) | Cloud SQL for PostgreSQL 16 (HA from P1) | Verify the `uuidv7`/extension allowlist before R1 (§5 step 1); PITR must meet RPO 1h (§6) |
| 2 | Redis (Celery broker) | ElastiCache for Redis | Memorystore for Redis | TLS in transit in prod; no persistence requirements beyond broker durability (jobs are idempotent/resumable, NFR-4/16) |
| 3 | Django web / workers | ECS on Fargate (or EKS if you prefer K8s) | Cloud Run (or GKE) | Same image, different commands per process shape |
| 4 | Celery beat (singleton) | ECS service, desired-count=1 | Cloud Run service min=max=1 (always-on), or GKE with a single replica | Beat must never run twice; alarm on liveness (§9) |
| 5 | Static frontend | S3 + CloudFront | GCS + Cloud CDN | ⚠ **r3:** the CDN serves the SPA on the **one** host, for every tenant, with an **index.html fallback** for unknown paths (client routes). The `/api/*` behaviour forwards to the app origin with `Host` intact (managed **AllViewer** on CloudFront) — needed now for `ALLOWED_HOSTS`, no longer for tenancy — and **must not cache**. ✅ No longer deferred: the bundle is deployable (§13 item 8) |
| 6 | Object storage (documents) | S3 — ~~**Object Lock** for the write-once classes (NFR-35)~~ **one bucket per environment, no object lock and no default retention rule for now (`CR-160-BRC10`, 2026-10-02)**, versioning on | GCS — ~~**Bucket Lock / retention policy** (NFR-35)~~ (no adapter yet), versioning on | Keys `t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext]` (`CR-160-BRC10`; was per-tenant-id prefixes), SSE with KMS keys, signed expiring URLs (TD-15) |
| 7 | Backup target (DB + WAL) | S3 (+ cross-region replication) or RDS automated backups w/ cross-region copy | GCS (+ dual-region US) or Cloud SQL backups | All copies stay in US regions (B6) |
| 8 | Load balancer / proxy | ALB (+ CloudFront in front) | Global External HTTPS LB | ⚠ **r3:** splits on **path** — `/api/*` → app, `*` → SPA. Must preserve the path verbatim (§10.2) and pass `Host` through (now for host validation, not tenancy) |
| 9 | TLS certificates | ACM — **one DNS-validated name**, `smartbillhub.bynry.com` | Certificate Manager — one name via DNS authorization | ⚠ **r3: the wildcard is DELETED** (§10.1). Path tenancy means one hostname, so nothing needs a wildcard. Auto-renewal, expiry alarm |
| 10 | DNS | Route 53 — **one A/ALIAS record** | Cloud DNS — one record | ⚠ **r3: no wildcard record.** Cert automation still needs API access to the zone for the single DNS-validation record |
| 11 | Secrets vault | AWS Secrets Manager | GCP Secret Manager | §4 policy; vault injects env vars at deploy |
| 12 | Key management (encryption at rest + app-layer PII keys) | AWS KMS (CMKs) | Cloud KMS | §12 rows 2–3; keys for RDS/Cloud SQL, volumes, buckets, and the app-layer HIGH-PII envelope keys |
| 13 | WAF / DDoS | AWS WAF + Shield | Cloud Armor | In front of the LB; also where per-tenant rate limiting can be assisted (app owns the 429 contract, B12 r1) |
| 14 | Metrics/alerts | CloudWatch (+ Managed Prometheus at P2, §9.4) | Cloud Monitoring (+ Managed Prometheus at P2) | The four platform metrics of §9.1 are mandatory on either |
| 15 | Logs | CloudWatch Logs | Cloud Logging | Structured JSON logs (§9.2); retention per §9.2 |
| 16 | Tracing | X-Ray (via OpenTelemetry) | Cloud Trace (via OpenTelemetry) | Instrument once with OTel, export to either (§9.3) |
| 17 | Container registry + image scanning | ECR (scan-on-push) | Artifact Registry (+ Artifact Analysis) | Feeds §12 row 9 (vuln management) |
| 18 | Network segmentation | VPC: private subnets for DB/Redis/app; only LB public; security groups least-open | VPC: private IPs + Private Service Connect for Cloud SQL; firewall rules least-open | §12 row 6; DB and Redis must never be publicly reachable |
| 19 | Platform ops email (alerts, internal only — customer email is tenant BYO/ESP, TD-8) | SES | No first-party equivalent — third-party ESP (e.g. SendGrid/Postmark) | Customer-facing email NEVER goes through platform SMTP; it rides the tenant's connected provider (NFR-21) |
| 20 | CI/CD deploy | CodePipeline/GitHub Actions → ECS | Cloud Build/GitHub Actions → Cloud Run | Gates in §11 run in CI regardless of deploy tooling |

**AWS must be added to the subprocessor register** (`soc2-nist-mapping.md` §5 — register
kept in audit-and-controls.md) and the DPA signed — that is a compliance action, not
just procurement (§12 row 15). The same applies to every additional vendor you
introduce (error sink, paging tool, ESP).

---

## 3. Environments

Four environments. The first is local-only; you own the other three.

| Env | Purpose | Data | Deploy cadence |
|---|---|---|---|
| **local** | developer laptops; `docker compose up -d` starts Postgres+Redis (root `docker-compose.yml`); `--profile full` adds api/web containers | Brazos Bend demo fixture | ad hoc |
| **demo** | the PO's clickable environment. A hosted demo URL is an explicit **R1 deliverable** (B12 r4: "the PO clicks a link, not a terminal"). Redeployed **every time an epic's stories merge** (preview-per-epic rhythm, B12 r4) | seeded Brazos Bend fixture family **plus one blank tenant** (R1 gate) | per landed epic |
| **staging** | release-gate environment, production-shaped. The release runbook (§11) runs here first in full: migrate → seed → gates → journeys. Also where you **rehearse restores** (§6.4) | Brazos Bend fixture; scrubbed copies of prod later if ever needed (policy then: PO sign-off) | per release candidate |
| **prod** | real tenants; 99.9% uptime target, US residency, RPO 1h / RTO 4h (B6) | real | per release (R1–R4), then per the post-R4 cadence you define |

⚠ **Amended by PO ruling 1 (2026-08-10) — posture: "a sandbox that must behave like
production."** The first AWS environment hosts the internal demo tenant **and then real
pilot customers, on the same environment**. It is therefore **prod** by every rule that
matters (backups, Multi-AZ, tenant isolation proofs, monitoring, retention) even while
it is called a sandbox — that is the whole point of the ruling. Two consequences:
(a) the four-environment table stands, but demo and prod **collapse into one** for the
first cut; (b) a **separate staging** is now more important, not less — the quarterly
restore rehearsals of §6.5 need somewhere that is not carrying customers.
One friction the ruling exposes: `manage.py seed_demo` **refuses to run under
`config.settings.production`** (fixtures never reach prod, §5 step 4) — still true in
r3, and it now costs more, because the seeder builds a genuinely walkthrough-ready
utility that this environment therefore cannot have (§13 item 6). The internal demo
tenant is instead created through the real provisioning endpoint,
⚠ **`POST /api/tenants`** (r3 — the `/api` prefix is new), which since 2026-08-10 also
**signs the owner in** on the same origin: no cross-host handoff, no success screen.
See `02-aws-runbook.md` §4 step 13.

Settings profiles map to environments via `DJANGO_SETTINGS_MODULE`
(`06-backend/config/settings/`): `local.py` (DEBUG, ALLOWED_HOSTS=`*`) for local only;
`production.py` for demo/staging/prod — it deliberately contains nothing but
"fill from environment at deploy time; no secrets in this file, ever."
`test.py` is CI-only (sqlite for unit tests; the golden/isolation suites force Postgres
because RLS is untestable on sqlite).

**DECIDED:** the environment *set* and the demo-redeploy-per-epic rhythm (B12 r4).
**OPEN-FOR-DEVOPS:** whether demo and staging share a cluster/host, IaC tooling
(Terraform etc.), and CI/CD mechanics for deploys.

---

## 4. Environment-variable + secrets contract

Policy (**DECIDED**, B12 §7 "Security" + `06-backend/config/settings/production.py`):
**no secrets in code or in the repo, ever** — production values live in the cloud's
secret vault (§2 row 11) and are injected as environment variables at deploy time.
`.env` files are a local-dev convenience only, and there are exactly two:
`06-backend/.env` and `07-frontend/.env`, each copied from the `.env.example`
committed beside it (`10-scripts/01-bootstrap.sh`, or `make env-init`). Compose
loads only the `.env`, never the example, so what runs is what you wrote.
Neither file is deployed. *(r4, 2026-08-10: the ROOT `.env.example` this
paragraph used to name is DELETED — no settings module ever read a root `.env`,
so it was a template for a file nothing loaded, still advertising `REDIS_URL`,
`VITE_API_URL` and subdomain-form E2E URLs after all three stopped being true.)*

### 4.1 Variables the code reads TODAY (verified against `06-backend/config/`)

| Var | Read by | Default if unset | Prod requirement |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `manage.py` and `config/celery.py` default to `config.settings.local`; ⚠ **r3: `config/wsgi.py` and `config/asgi.py` default to `config.settings.production`** | depends on the entry point (see left) | **must** be `config.settings.production` on every container (web, worker, beat) **and every one-off `manage.py` task** — that path still defaults to local |
| ⚠ **`DJANGO_ALLOWED_HOSTS`** — *r3: moved here from §4.3; the code reads it now* | `config/settings/production.py:22` (`env.list`) | `[]` — and `DEBUG=False` then rejects every request | **`smartbillhub.bynry.com`** — **one host, NO leading dot** (§10.3). The r2 wildcard form `.smartbillhub.bynry.com` is deleted with subdomain tenancy |
| `DJANGO_SECRET_KEY` | `config/settings/base.py` | `dev-only-insecure` | **must** be set from vault; rotate on compromise; never reuse across environments |
| `DATABASE_URL` | `config/settings/base.py` (`env.db()`) | `postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub` | **must** be set from vault; TLS to the DB (`sslmode=require` minimum) |
| `CELERY_BROKER_URL` | `config/settings/base.py` | `redis://localhost:6379/0` | **must** be set from vault (`rediss://` in prod). The library default points at localhost and will silently not work. ⚠ **LIVE AS OF 2026-08-19** — this stopped being a value nothing dialled: a Celery worker now consumes the queue (PO ruling, §13 item 3), so a wrong value here is jobs that never finish rather than a value nobody reads. `06-backend/.env.example` types `redis://redis:6379/0`, the compose service name. *(Row added 2026-08-10: `base.py` now reads this directly — §4.2's older note is superseded)* |
| `JOBS_EAGER` | `config/settings/base.py` (default `True`); `production.py` overrides the default to `False` | `True` outside production | ⚠ **Set it explicitly, and the right answer FLIPPED on 2026-08-19.** It used to read *“`True` is the working choice”*, because `False` with nothing consuming the queue left every 202 `queued` forever — which is exactly what happened on the deployed build, across FOUR job kinds (DEF-320; a bulk rate change that changed no price, DEF-326). A worker now exists, so **`False` is the answer wherever one is running**, and `True` only where none is (a laptop, CI, a one-off container). `True` beside a running worker is silent the other way: bodies run inside the web request and the worker idles |
| `JOBS_EAGER` — on the deployed host | — | — | ⚠ **A template change never reaches a host that already has a `.env`** (hard-won law 4). Editing `06-backend/.env.example` and `docker-compose.yml` changed nothing already running. That host needs three things done ON IT: a reachable broker at its own `CELERY_BROKER_URL`, at least one process running `celery -A config.celery worker`, and `JOBS_EAGER=false` in the `.env` it already has. Until all three are true there, DEF-320 and DEF-326 are still live on it — the code is correct and nothing is running it |
| ~~`JOB_ARTIFACTS_DIR`~~ | ⚠ **REMOVED 2026-10-02** (`DEF-MET-4954`) | — | Read by nothing. Export files go to `DOCUMENT_STORAGE_BUCKET` at `t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>` (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*). Delete it from an existing `.env`; set `DOCUMENT_STORAGE_BUCKET`/`_REGION` instead — exports need them. No EFS, no shared volume (§13 item 9) |

### 4.2 Variables declared in `.env.example` but NOT yet consumed by settings — wiring lands with the R1 deploy lane

| Var | Intended consumer | Note |
|---|---|---|
| `REDIS_URL` | ⚠ **Superseded 2026-08-10:** `base.py` now reads `CELERY_BROKER_URL` directly (see §4.1). `REDIS_URL` is declared in `.env.example` and passed by `docker-compose.yml`, but **no backend module reads it**. Set it for parity/legibility if you like; `CELERY_BROKER_URL` is the one that matters | not required |
| `VITE_API_URL` | frontend **build-time** constant. ⚠ **Not read by any code**: `07-frontend/src/api/client.ts` deliberately reads no env var and defaults to a same-origin empty base URL, composing `/api` + the tenant it reads from `window.location.pathname`. The root `.env.example` entry is stale twice over — nothing reads it, and its comment still describes serving "every tenant **subdomain**" | leave unset |
| ~~**`VITE_TENANT_HOST_SUFFIX`**~~ | ⚠ **DELETED 2026-08-10 (r3)**, together with `07-frontend/.env.example` itself. It named the hostname suffix a tenant lived at, purely so the signup success screen could hand the new owner across to `brazosbend.smartbillhub.bynry.com`. Path tenancy removes both the suffix and the handoff: a tenant address is `/{tenant}` on the origin the browser is already on, composed from `window.location`, and provisioning signs the owner in on that same origin. Verified in `07-frontend/src/vite-env.d.ts` ("THERE ARE NONE RIGHT NOW") and `07-frontend/README.md` | **do not set** — and do not reintroduce |

⚠ **r3 consequence worth stating on its own: the frontend has NO build-time variables at
all.** One `npm run build` artifact is valid in every environment; a bundle cannot be
"wrong for this environment", and the same `dist/` promotes from staging to prod
unchanged.
| `STRIPE_API_KEY` · `PLAID_CLIENT_ID` · `PLAID_SECRET` · `QBO_CLIENT_ID` · `QBO_CLIENT_SECRET` · `TWILIO_ACCOUNT_SID` · `TWILIO_AUTH_TOKEN` | integration seams. **Dev sandbox only** — in production, provider credentials are per-tenant data stored by the integrations module, not platform env vars (TD-8, TD-9). Payment rails go live in release R4/W7; SMS in W8 | keep empty until the owning release; sandbox values only outside prod |

### 4.3 Variables production will additionally need (not in code yet — flag at R1 if missing)

✅ ~~`DJANGO_ALLOWED_HOSTS`~~ **CLOSED 2026-08-10 — the code reads it; the row moved to §4.1.**

| Var (name to be finalized with Eng) | Why |
|---|---|
| Object-storage endpoint/bucket/credentials (or IAM-role binding) | TD-15 file service (uploads, e-signed documents, import files, report files) |
| Error/trace sink DSN (Sentry or equivalent) | §9 observability; product **OPEN-FOR-DEVOPS** |
| Payment **webhook signing keys** (R4/W7) | 🔒 sensitive path (CLAUDE.md); vault-only, never logged, rotation procedure documented when W7 lands |
| ⚠ **r3 — the `SECURE_*` family and a trusted-proxy setting** | `production.py` sets no `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` or `CSRF_TRUSTED_ORIGINS`, and DRF has no `NUM_PROXIES`. Behind a load balancer that makes the per-tenant IP allowlist (BR-IDN-020) meaningless and the public throttle spoofable, and `SECURE_SSL_REDIRECT` without `SECURE_PROXY_SSL_HEADER` would be a redirect loop. Eng settings changes, not env vars — recorded here because deploy is where they bite (§13 item 14, runbook §10.15) |

**Secret handling rules (DECIDED):** vault-injected env only; no secrets in images,
compose files, CI logs, or shell history; distinct values per environment; webhook keys
and `DJANGO_SECRET_KEY` are on the project's 🔒 sensitive-path list — treat their rotation
as an audited change. Prefer cloud IAM roles/workload identity over long-lived keys
wherever the provider allows.

---

## 5. Migration & RLS bootstrap order (do these IN THIS ORDER, every environment)

The database is bootstrapped in four ordered steps. Order matters because RLS policies
reference columns the migrations create, and the seed writes through the application
layer, which requires tenant context to already work.

> ⚠ **This section said "four steps" and was missing STEP 0 for as long as RLS `FORCE`
> has existed. That gap was DEF-622 (2026-08-24): a genuinely empty database could not
> run `migrate` at all — the first deploy was blocked outright.** Every environment we
> had carried the missing setting by accident of history, so only a first deploy hit it,
> and nothing in CI creates a first deploy. Step 0 below is the step that did not exist.

> ⚠ **AMENDED 2026-09-28 (`CR-144-BRC07`) — *WHERE* THESE STEPS RUN HAS MOVED, THE ORDER
> HAS NOT.** Steps 0–4 were carried out by `06-backend/docker-entrypoint.sh` in **every
> web container at start-up**. On ECS that is a concurrent migration between tasks with
> no advisory lock, a health check that fails for as long as the migration runs (and a
> balancer that kills the task partway through it), and DDL executed by a scale-out.
>
> **They now run in `06-backend/docker-release.sh`, as a ONE-OFF ECS task the pipeline
> runs to completion BEFORE the rollout.** Same steps, same order, same reasoning — one
> process per step, the tenant-GUC default checked before `migrate`, the OQ-087
> reference-data sweep after it. `docker-entrypoint.sh` keeps only what is about THIS
> process's ability to serve: the settings refusal, the `ALLOWED_HOSTS` warning and the
> RLS-enforcement check that refuses to boot.
>
> ⚠ **AND ONE MORE, ADDED 2026-09-28 AFTER THE MOVE TOOK THE PRODUCT DOWN
> (`DEF-INF-7683`): THE WEB TASK ASKS WHETHER THE SCHEMA IS THE ONE IT WAS BUILT FOR,
> AND REFUSES TO SERVE WHEN IT IS NOT.** While every web container migrated at
> start-up, a task could not serve a schema older than its code — **an invariant held
> by an implementation detail and by no check at all.** The detail moved, nothing went
> red, and within hours nobody could sign in at `smartbillhub.bynry.com`: every
> `POST /api/<slug>/auth/session` answered 500 over
> `UndefinedColumn: column security_policies.absolute_session_hours does not exist`
> while `GET /api/health` answered `200 {"status":"ok"}` throughout. `core/schema_guard.py`
> now runs immediately before `exec gunicorn` — **CURRENT** boots, **PENDING** refuses
> and names both the unapplied migrations and `make release`, **UNREACHABLE** warns and
> boots (a failover must not crash-loop the service). It does **not** migrate, on any
> flag. See `09-infra/02-aws-runbook.md` §H6.
>
> ⚠ **AND THE `DJANGO_SETTINGS_MODULE` REASONING NOW BINDS TWO SCRIPTS RATHER THAN ONE.**
> `manage.py` defaults it to `config.settings.local` and `config/wsgi.py` to
> `config.settings.production`, so an environment that leaves it unset has the release
> task migrating under one settings module and the web task serving under another. Both
> scripts refuse to start without it, and **all three task definitions carry the same
> value** (runbook r4.3).

**Step 0 — Tenant-context session default (`app.tenant_id`). DO THIS BEFORE `migrate`.**

```bash
export DATABASE_URL=…  DJANGO_SETTINGS_MODULE=config.settings.production  SBH_DB_PASSWORD=…
10-scripts/13-provision-database.sh --all
```

**Why it is a precondition of `migrate` and not a runtime concern.** Every tenant table
carries `FORCE ROW LEVEL SECURITY`. `FORCE` applies the §5-step-3 policy to the **table
owner** — and the table owner is whoever runs migrations. PostgreSQL validates a newly
added `FOREIGN KEY` by running an ordinary scan over the referencing table, so the policy
is evaluated, `current_setting('app.tenant_id')` runs, and on a database where nobody ever
set it the migration dies:

```
Applying identity.0003_sessions_security_policy_lockout...
django.db.utils.ProgrammingError: unrecognized configuration parameter "app.tenant_id"
CONTEXT: SQL statement "SELECT fk."user_id" FROM ONLY "public"."sessions" fk
         LEFT OUTER JOIN ONLY "public"."users" pk ON (…) WHERE pk."id" IS NULL …"
```

Setting it to the empty string does **not** help — `''` is the *cleared* sentinel, chosen
precisely so the `::uuid` cast fails and the policy denies everything, so it fails one step
later with `DataError: invalid input syntax for type uuid: ""`. The value that works is the
**nil UUID `00000000-0000-0000-0000-000000000000`**: it casts (so the policy evaluates
instead of erroring) and it matches no row (so deny-by-default is unchanged). Full note:
`06-backend/db/001_tenant_context_default.sql`.

**RLS is not weakened by this.** No role is granted `BYPASSRLS`, `ENABLE`+`FORCE` is
untouched on every table, every policy is untouched, and a session that clears context
still `SET`s `''` at session level and still refuses. What changes is that a connection
which never set context at all now sees **zero rows instead of an error** — which is what
§7 of this document has always *claimed* happens ("Ad-hoc psql sessions see zero tenant
rows unless they set `app.tenant_id`").

**`--migrate` APPLIES THE SEQUENCE STEP BY STEP — one migration per process, in
dependency order.** PO ruling 2026-08-24 (OQ-354), verbatim: *"You will ahve to do the
migration step by step - you will ahve to consier a depands on b , b depends on c - so
build the sequence of migration"*. `app.tenant_id` is a SESSION variable and
`manage.py migrate` applies every pending migration on ONE connection, so a data step that
clears tenant context to `''` poisons the foreign-key validation of **every later migration
in the same run**. A process per step gives each one a fresh connection that starts from
the database/role default instead of from the previous step's leftovers. The order comes
from Django's own `migrate --plan`, which is the migration graph already resolved.

⚠ **NO ROLE IS EVER GRANTED `BYPASSRLS`.** An earlier draft of this section proposed a
temporary grant around the first `migrate`; **the PO ruled it out** in the ruling above.
The script refuses the flag by name, and `--verify` FAILS the run if the app role turns out
to hold superuser or bypass from anywhere else.

⚠ **ONE STEP IS NOT YET SEQUENCEABLE, AND A FIRST DEPLOY STOPS THERE (OQ-354, open).**
`assets.0003_meter_types_and_read_methods` — step 12 of 163 — poisons *itself*: Django
DEFERS its foreign-key constraints to the migration's exit, which is **after** its own
`RunPython` data step has set `app.tenant_id` to `''`. `metering.0016_br_met_101_common_area`
and `tenancy.0004_settings_families_logo_and_hosted_lists` share the shape. Each must leave
the NO-TENANT sentinel instead of the empty string; measured 2026-08-24, with only that
substitution the remaining 152 steps applied to an empty database, exit 0, under a role with
`rolsuper=f rolbypassrls=f`. Those are committed migrations, so the change needs the
append-only migration-guard exception — that is the open half of OQ-354.

⚠ **`--role-guc` is not optional in CI.** Django's test runner creates a NEW database on
every run, so a test database is a first deploy every time. Before this step existed the
**G5 tenant-isolation suite could not run at all** on a clean cluster: `6 errors in 1.74s`,
`unrecognized configuration parameter "app.tenant_id"`. `ALTER ROLE … SET` follows the role
into databases that do not exist yet, which is what covers them.

⚠ **LAW 4 — THIS DOES NOT REACH A HOST THAT ALREADY EXISTS.** Adding these files to the
repo changes no running database, and neither does a redeploy. On every already-provisioned
deployment somebody runs this once, by hand, as the database owner or a superuser:

```bash
psql "$DATABASE_URL" -c "SELECT current_setting('app.tenant_id', true)"   # NULL or '' → act
psql "$DATABASE_URL" -c "ALTER DATABASE \"<your-db>\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
```

It changes no data, takes no table lock, and applies to sessions started after it. An
already-migrated database keeps booting either way — `migrate` is a no-op there — so the
symptom does not appear until the next migration that adds a foreign key to a tenant table.
`06-backend/docker-release.sh` prints this exact remediation when it sees the setting
missing, and does **not** refuse, for that reason. ⚠ **THIS SENTENCE SAID
`docker-entrypoint.sh` UNTIL 2026-09-28 AND WAS STALE FROM THE HOUR `CR-144-BRC07` H4
LANDED** (found while building `DEF-INF-7683`): the check is a PRE-MIGRATE check — its
own text ends *"the migrate below will report the real connection error"* — and there is
no migrate in the web entrypoint any more, so it moved with the migrate it is about.

**Step 1 — Extensions SQL.**
`06-backend/db/000_extensions.sql` (currently: `pgcrypto`). Locally it auto-applies via
`docker-entrypoint-initdb.d`; on RDS/Cloud SQL you (or the migration pipeline) apply it
first, before any Django migration. Note: B2 O-1 leaves the `uuidv7()` source open —
`pg_uuidv7` extension if the target supports it, else a SQL shim. **Confirm with Eng which
one your chosen cloud's Postgres allows before R1** (RDS and Cloud SQL have different
extension allowlists). The file is marked HUMAN-OWNED; you apply it, you don't edit it.

**Step 2 — Django migrations** (`python manage.py migrate`).
Migrations are authored from B2 r16 plus the 18-item pre-migration checklist (B11) — never
improvised — and CI has a **migration-guard** gate (TD-12): ordering is enforced
mechanically. Table-creation order follows B2: platform → tenancy → identity → metering →
customers → rating → billing → payments → ledger → notifications → audit; **partitioned
tables are created partitioned from day one** (§8) — you cannot bolt partitioning onto a
billion-row table later.

**Step 3 — RLS policies, `ENABLE` + `FORCE`, per the B2 §3 template.**
Applied by migrations immediately after each tenant-scoped table exists. The exact
template (from `04-docs/02-decisions/02-database-design-brief.md` §3, mirrored in
`06-backend/core/rls.py`):

```sql
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to the table owner
CREATE POLICY <t>_tenant_isolation ON <t>
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

- `FORCE` matters operationally: even the application's own DB role is subject to the
  policy. Ad-hoc psql sessions see zero tenant rows unless they set `app.tenant_id` —
  this is by design (deny-by-default). Your break-glass/DBA procedures must account for it.
- Platform (non-tenant) tables carry no RLS — the list is in B2 §3, **as corrected by
  B2 r16**: `users` and `tax_jurisdictions` ARE tenant-scoped + RLS despite the older §3
  listing (r16 supersedes; newest-wins).
- 🔒 **HUMAN-REVIEW-PENDING:** RLS policy files are on the sensitive-path list. Per the
  PO ruling of 2026-08-09, they are AI-authored under machine gates (isolation suite +
  cross-tenant probes, gate G5) with every such file recorded in
  `12-governance/09-human-review-ledger.md`, awaiting deferred human sign-off. As DevOps
  you deploy them like any migration, but know their review status — and never hand-patch
  a policy in production.

**Step 4 — Seed.**
⚠ **r3: the live seeder is `manage.py seed_demo`**
(`06-backend/apps/tenancy/management/commands/seed_demo.py`), not the
`10-scripts/03-seed_demo.py` stub this section named in r1/r2. It seeds the **Brazos
Bend fixture family** through each module's own service functions under tenant context —
5 charge codes, 2 taxes, 4 rate schedules, 3 published plans, 6 premises, 10 units,
5 routes, 2 cycles, 10 assets — idempotent on natural keys, and it prints the walkthrough
credentials and the `/{tenant}/signin` path at the end. Accounts, reads, bills and
payments are **not** seeded and the command says so rather than inventing them (§13
item 6). It is the standard post-migrate step for demo and staging (plus one blank
tenant for the R1 walkthrough). **Never seed fixtures into prod** — and it enforces that
itself, refusing to run under production settings.

**Step 4b — Reference-data sweep (`manage.py sweep_reference_data`). NEW 2026-08-15, and
it RUNS IN PRODUCTION — this AMENDS step 4's "never in prod", which governs the demo
fixture only.**
PO ruling **OQ-087** (2026-08-10), verbatim: *"automatic post-migrate, across all tenants.
Per-tenant context, per-tenant transaction, failures isolated and recorded, sweep continues
(BR-TEN-074)."* The ruling's own closure note says this text had to be amended, so it is.

The two commands are not the same kind of thing and the distinction is the whole reason
one refuses in prod and the other must not:

| | `seed_demo` | `sweep_reference_data` |
|---|---|---|
| creates | a whole tenant with a **published owner password** | nothing — no tenant, user, credential or subscription |
| writes | demo CONTENT (premises, plans, assets) | platform reference VOCABULARY only, insert-if-absent (BR-TEN-071) |
| in prod | **refuses**, by design | **runs** — prod is the only host where the tenants that need it exist |

It is wired into `06-backend/docker-release.sh` immediately after `migrate` — ⚠ **this
line said `docker-entrypoint.sh` until 2026-09-28 and was stale from the hour
`CR-144-BRC07` H4 landed** (found while building `DEF-INF-7683`); the sweep moved WITH
the migrate, because left behind it would run in every web task at once and, in a fresh
environment, BEFORE the migrate, which is the one order *"automatic post-migrate"*
forbids — and is
**not allowed to stop the release**: it isolates per-tenant failures by design (exit 2 names
them; exit 3 is DEF-016's unexplained-empty list; exit 1 is a refusal before any tenant was
touched, including a fixture edited without a BR-TEN-077 version bump). A reference-data
gap must not take the API down, so the exit code is printed loudly and gunicorn still
starts. **`--dry-run` remains mandatory before RELEASING a fixture version bump**
(BR-TEN-076) — that is a release-process step (§11 step 2), not a boot step, and it writes
nothing at all. `--report` answers "which tenants are behind" and has no screen anywhere
(BR-TEN-079: A4 records that no UI exposes cross-tenant data; the Bynry admin console is v2).

Immutability triggers (append-only enforcement on invoices/payments/journal tables, B2 §3)
ship inside the migrations — no separate ops step, listed here so a `permission denied`-
style trigger error on a financial UPDATE is recognized as by-design, not a fault.

---

## 6. Backup, restore, DR & retention (compliance-grade — cite these NFRs in your runbooks)

### 6.1 Baseline targets — **DECIDED** (B6 planning table, confirmed 2026-08-07)

| Objective | Value | Source |
|---|---|---|
| RPO (max data loss) | **1 hour** — this is the LAW FLOOR at every phase | B6 |
| RTO (max time to restore) | **4 hours** — law floor at every phase | B6 |
| Backup scheme | **daily full + continuous PITR (WAL archiving)**, automated | B6 |
| Uptime target | 99.9% | B6 |
| Data residency | **US only** — primary, backups, WAL archives, cross-region copies, log sinks: all US | B6 |
| Restore verification | **QUARTERLY automated restore test** | SC-5 CONFIRMED (`soc2-nist-mapping.md` §4) |

### 6.2 Per-phase DR posture (targets tighten as volume grows — the tightened numbers are recommendations, **OPEN-FOR-DEVOPS** to adopt; B6 remains the floor)

| Phase (§7) | RPO target | RTO target | Mechanism |
|---|---|---|---|
| P0 pilot | 1h (B6) | 4h (B6) | Managed-PG automated daily backup + PITR; **cross-region US backup copy ON from day one** (cheap; residency-compliant); restore test quarterly, may be semi-manual at P0. ⚠ **PO ruling 2026-08-10: `Multi-AZ` is ON at P0 too** (real customers land here), and the **first restore test must precede the first real customer** |
| P1 early | 1h | 2h (recommended) | Multi-AZ/HA instance (failover is minutes); quarterly restore test now AUTOMATED per SC-5; document restore timing against real data volume |
| P2 growth | 15 min (recommended) | 1h (recommended) | Tuned WAL archiving cadence; rehearsed runbook; optional warm standby in second US region |
| P3 scale | ≤5 min (recommended) | ≤30 min (recommended) | Multi-AZ auto-failover + warm cross-region DR (replica or continuously-restored standby); semiannual DR game-day in addition to quarterly restore tests |

### 6.3 Retention rules the platform enforces (you provision the storage tiers for them)

Consolidated from NFRs + `04-docs/07-compliance/data-retention.md` (2026-08-08 addendum):

| Data | Retention | Rule |
|---|---|---|
| Financial records (invoices, invoice_lines, payments, allocations, journal_*) | 7 years, **NEVER pruned**; >2-year partitions may move to cold storage/cheaper tablespace but stay queryable | NFR-7, NFR-25 |
| Audit log | 7 years; monthly partitions; 2 years hot, then cold | NFR-7, NFR-28 |
| Meter reads | 2-year hot window; monthly partitions detach to cold via an automatic scheduled job; 7-year total | NFR-6, BR-MET-055 |
| Outbound messages | rendered bodies prunable after 90 days (tenant-config); queue/status rows archive after 18 months; `notice_history` 7 years | NFR-29 |
| Notices (disconnect/reminder) | 7 years (PUC dispute defense) | data-retention.md |
| Generated report files (object storage) | 3 days default, tenant-config | NFR-9 |
| Pinned bill-template versions + rate/plan versions | template versions **FOREVER** (undeletable); rate/plan versions 7yr+ | NFR-8 |
| E-signed agreements, import source files | 7 years, **WRITE-ONCE** (object lock, §2 row 6) — ⚠ object lock suspended by `CR-160-BRC10` (2026-10-02); the row stays write-once | NFR-35 |
| Closed-account PII | 7 years with the financial records, masked display | SC-7 CONFIRMED, BR-CUS-065 |
| Closed-tenant data (offboarding export + deletion SLA) | **OPEN** — not yet ruled; raise before the first tenant contract | data-retention.md |

End-of-retention deletion is a **supervised archival job, never an operational path**
(data-retention.md). The partition-detach/archival jobs are application code (Celery
beat); your part is the cold-storage destination (cheaper tablespace or in-region object
storage tier) and monitoring that the jobs run (§9.1).

### 6.4 Document-store protection — **DECIDED pattern** (TD-15, NFR-35)

- Bucket **versioning ON** for all document buckets (both clouds, §2 rows 6–7).
- ~~**Object lock / bucket retention** on the write-once classes (e-signed agreements,
  import source files) — 7-year lock, compliance mode.~~ ⚠ **THE OBJECT-LOCK HALF IS SUSPENDED 2026-10-02 BY `CR-160-BRC10` (PO, verbatim: *"we dont want this to be enabled right now - dont lock it"*): no file is object-locked, legal files included, and no file carries an expiry tag.** The lock stays a setting (`DOCUMENT_STORAGE_OBJECT_LOCK_MODE`, default `NONE`) and applies, when switched on, only to files written after that moment. The product still deletes nothing — the `stored_documents` row stays write-once — but someone with direct access to the storage account could delete or overwrite a file.
  **And the bucket must carry NO default retention rule** — the boot check refuses one
  (`smartbillhub.E002`).
- Lifecycle policies: ~~transient classes (report files 3d, rendered bodies 90d) expire by
  lifecycle rule where the app doesn't do it~~ ⚠ **EXPORT FILES ARE DELETED BY THE APP,
  NOT BY A LIFECYCLE RULE** (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*): once a day, per utility, by their
  `job_artifacts` rows, after that utility's `file_retention_days` — and only under
  `t/<web name>/export/` (the task role's delete is limited to `t/*/export/*`). No expiry
  tag and no expiry rule; archived partitions and >2yr artifacts may still transition to
  colder storage classes.
- Replication/redundancy stays inside the US (dual-region US on GCP; CRR to a second US
  region on AWS).

### 6.5 Restore procedure requirements — **DECIDED in principle, mechanics OPEN-FOR-DEVOPS**

1. **Quarterly automated restore test on staging** (SC-5): restore latest full + WAL to a
   point in time; then run the platform's own verification, not just `pg_isready`:
   - the **isolation suite** (`make isolation`) — proves RLS survived the restore intact
     (a restore that loses policies is a catastrophic silent failure; NFR-10 makes this
     suite a zero-tolerance release blocker, and it doubles as the restore acceptance test);
   - the **golden money suite** (`make golden`) — proves financial figures are intact;
   - a trial-balance tie-out check (drift must be 0 — NFR-17).
2. Record actual restore duration each quarter against the phase's RTO target (§6.2).
3. Restored environments must come up with **outbound sending disabled** (dispatcher off)
   so a restore never re-emails customers — coordinate the switch mechanism with Eng.
4. Incident response context: SC-6 CONFIRMED — incidents carry a **72h internal
   assessment target** with state-law-driven notification; your DR runbook plugs into
   that process (see `incident.md` per the mapping doc).

---

## 7. SCALING PHASES — how the infrastructure grows with tenant volume

> PO direction (2026-08-09): "initially there will not be many utilities — 1, 5 or 10;
> then volume will increase; infra should scale with data volume." This section is the
> plan for that. The **phase frame is DECIDED** (this doc r1, derived from the B6
> capacity math); the **trigger thresholds and cost bands are ESTIMATES** you tune with
> real telemetry (§9), and every infra action inside a phase is yours to execute.

**The math behind the phases** (B6 capacity table): each account generates roughly
**550–600 DB rows/year** (journal_lines 216 + invoice_lines 144 + audit_log 72 +
outbound_messages 48 + meter_reads 36 + the rest). The full B6 planning model —
1,000 tenants / 1.6M accounts — reaches **≈2.7 billion rows in 3 years**, with
journal_lines alone at **≈1.04B** (it is the biggest table, not reads or audit). Every
phase below is that same math at smaller tenant counts.

### Phase table (summary)

| | **P0 — Pilot** | **P1 — Early** | **P2 — Growth** | **P3 — Scale** |
|---|---|---|---|---|
| Tenants | 1 (~3k accounts) | 5–10 (≈5–25k accounts) | 25–100 (≈30–160k accounts) | 100–1,000 (up to 1.6M accounts — the full B6 model) |
| New rows/yr (≈) | ~1.8M | ~3–15M | ~20–90M | ~0.1–0.9B (2.7B by yr 3) |
| DB shape | smallest managed-PG tier (≈2 vCPU/8GB), single-AZ acceptable | managed PG ≈4 vCPU/16GB, **Multi-AZ/HA on** | vertical scale ≈8–16 vCPU/64GB+, provisioned IOPS | 32+ vCPU, read replicas for reports, cold-tier tablespaces, possible cell split |
| App shape | 1 web + 1 worker + beat (can share a small cluster/host) | 2 web (HA) + **separate worker pool** (2 workers) + beat | web autoscaling; workers autoscale **on queue-oldest**; queue-per-class separation load-bearing | per-cell stacks if cell split triggers; otherwise larger pools |
| Monthly cost band (ESTIMATE, infra only) | ~$200–500 | ~$500–1,500 | ~$2k–6k | ~$10k–40k+ |
| Move up when (trigger metrics) | >3 tenants signed, or DB CPU >50% sustained, or queue-oldest alarms recur | >10–25 tenants, or big-five combined >50M rows, or overlapping bill-run windows contend, or p95 API >500ms sustained | >100 tenants, or journal_lines >250M, or write saturation signs (WAL throughput ceiling, vacuum/autovacuum falling behind), or reports contend with OLTP despite rollups | cell-split trigger below |

### P0 — Pilot (1 utility, ~3,000 accounts)

The whole platform fits on the smallest sensible managed footprint. What matters at P0 is
**correctness scaffolding, not capacity**: the big-five tables are still created
**partitioned from day one** (NFR-24 — a monthly partition of 10k rows costs nothing;
retrofitting partitioning onto a big table later is a migration project), RLS FORCE is
fully on, backups + PITR + cross-region copy run from the first day of real data (§6.2 —
compliance does not have a pilot phase), and the four platform metrics (§9.1) are wired
even if the graphs are boring.

⚠ **Amended by PO ruling 1 (2026-08-10): Multi-AZ is NO LONGER deferrable at P0.** The
first environment carries real pilot customers, so the P0 build is P0 capacity with P1
durability — `Multi-AZ` on, ≥2 web replicas, WAF and cross-region backup copies from day
one. Still deferred at P0: autoscaling (the scaling signal is queue depth, and there is
no queue traffic to tune against yet — §8.2), read replicas, Prometheus (cloud-native
metrics suffice). Cost consequence: the AWS build lands in the **upper half** of the
band below (~$310–430/mo — runbook §2.8, ESTIMATE).

### P1 — Early (5–10 utilities)

First structural change: **separate the worker pool from web** so a bill run can never
starve the API (they scale on different signals). Turn on Multi-AZ/HA for Postgres —
from here real utilities depend on the platform for revenue. Partition creation cadence
is now live and monitored (alert if next month's partitions are missing, §9.1);
the 2-year cold-detach jobs exist but won't fire until year 2. Bill-run windows are still
sequential and comfortably inside the <5 min/cycle budget (B6).
Zero-downtime path from P0: managed-PG vertical resize = failover blip (do it in a
window); splitting workers out is a stateless redeploy.

### P2 — Growth (25–100 utilities)

The B6 mechanisms stop being theoretical:
- **NFR-26 rollup-on-close is load-bearing** — dashboards and reports read materialized
  period rollups; if you see reports scanning raw journal_lines, that's a bug to raise,
  not a DB to upsize.
- **Queue autoscaling on oldest-message age** (§9.1) — many tenants' cycles now overlap
  at month-end; workers scale out for the window and back in after.
- **Per-tenant API rate limits start to matter** (429 + Retry-After is already in the API
  contract, B12 r1; ops-config thresholds are yours).
- Postgres scales **vertically** (8–16 vCPU, 64GB+, provisioned IOPS for the bill-run
  windows); first cold-tier partition detaches actually run (2 years after P0 tenants).
Zero-downtime path from P1: vertical resize via failover; queue split is config;
introducing autoscaling policies is additive.

### P3 — Scale (100–1,000 utilities — the full B6 model)

Everything NFR-24..30 was designed for: monthly-partitioned big-five with >2yr partitions
in cold tablespaces/storage (NFR-25 — cold, never deleted), **read replicas for the
report/query-service workload** (replicas inherit RLS policies; any replica routing must
keep whole sessions together — the §1 pooler caution applies), aggressive rollup usage,
and worker fleets sized per queue class.

**Cell/shard split — state of the trigger (DECIDED to name it now, execute only if hit):**
the monolith + single Postgres writer carries the full B6 model on paper. If real load
disproves that, the split is by **cell**: a second full stack (LB→app→PG→Redis) with
tenants assigned per cell. ⚠ **r3 — the mechanism changed with the tenancy model.** Under
subdomains this was a *DNS-level* tenant→cell map (point `<tenant>.` at a different
stack). Under path tenancy every tenant shares one hostname, so the map lives **entirely
at the LB/CDN layer as a path-prefix rule** (`/api/{tenant}/*` and `/{tenant}/*` → cell
N). Two honest consequences: the map is now a **routing-rule list that grows with tenant
count**, not a DNS record per tenant, so at hundreds of tenants it wants generating from
the tenants table rather than hand-maintaining (ALB listener rules are capped; CloudFront
Functions or a small router service are the realistic shapes); and cell-to-cell migration
is logical replication + a **routing-rule cutover** instead of a DNS cutover — faster to
apply, but with no DNS TTL to stage it behind, so it must be atomic. Still no application
sharding layer. Trigger metrics (any sustained):
- single-writer write saturation: WAL generation at instance ceiling, autovacuum
  permanently behind on the big five, or checkpoint/replication lag alarms at p95;
- the month-end bill-run window cannot hold the <5 min/cycle budget across tenants even
  with maxed worker scale-out (i.e., the DB, not the workers, is the limit);
- vertical headroom exhausted (already at the largest sensible instance class).
Also at P3: revisit **NFR-27** vigilantly — a single AMI/interval-read tenant multiplies
read volume 30–60× and must re-run the capacity math with Eng-Lead sign-off *before*
enablement, at any phase.

---

## 8. Scaling mechanics (the machinery behind the phases)

### 8.1 Partition plan — **DECIDED** (NFR-24)
The "big five" (journal_lines, invoice_lines, audit_log, outbound_messages, meter_reads)
are partitioned **monthly** from day one; any table projected >50M rows/year must be. The
tenant-aware partition strategy (whether tenant is part of the partition key vs leading
indexes only) is an Eng-Lead 🔒 decision — implemented in migrations, not by ops. What
ops owns: disk/tablespace planning for partition growth and the >2-year cold tier
(§6.3); verifying the automatic monthly partition-create and partition-detach jobs ran
(§9.1); treating AMI enablement as change-control (NFR-27).

Query-side protections you inherit rather than build: NFR-30 tenant-leading composite
indexes on every hot path (no cross-tenant scans exist), and NFR-26 rollup-on-close.

### 8.2 Worker sizing — starting point (final numbers **OPEN-FOR-DEVOPS**, tune per §7)
Tenants are small (1–2 concurrent staff each — B6); interactive API load is light and
bursty. The real work is **batch**: bill-run windows and end-of-month payment spikes.
- **Budget to protect:** a full billing cycle (~1,100 accounts) rated + invoiced in
  **< 5 minutes** (B6 / B12 §7). This is a monitored SLO (§9.1), so size workers to it.
- Every heavy operation is async (202 + job_id contract, B12 r1) and **idempotent +
  resumable** (NFR-4, NFR-16) — a worker crash mid-bill-run is recoverable by re-running;
  scope-keyed idempotency prevents duplicate charges. You can therefore be aggressive
  with worker autoscaling/preemption without financial risk.
- Separate queues for bill-runs vs the outbound dispatcher vs imports/archival so a slow
  ESP can never starve a bill run (the dispatcher is deliberately paced in tenant-config
  batches, default 500 — NFR-1); exactly 1 beat.
- **Scale on queue metrics, not CPU:** queue depth and oldest-message age (§9.1) are the
  platform's own chosen scaling signals (B12 §7).

### 8.3 Postgres sizing
Follow the phase table (§7). Provision IOPS for bill-run windows before raw CPU.

### 8.4 Read replicas (P3)
Not assumed by the app in v1 (TD-18: reads go through query services + close-rollups).
When added for reports at P3: replicas inherit RLS policies automatically, but the
session GUC caveat (§1) applies to any replica-routing proxy — route whole sessions, not
individual statements.

---

## 9. Telemetry & observability

### 9.1 Metrics — the four platform metrics are **DECIDED** (B12 §7); wire them first

| Metric | Alert condition | Why it exists |
|---|---|---|
| **Subledger tie-out drift** | **any value ≠ 0 → page immediately** | double-entry ledger must tie out at all times; drift is a *release blocker by law* (NFR-17, SYS-DRIFT error class). The single most important alarm in the platform |
| **Queue depth + oldest-message age** (per Celery queue AND the outbound_messages table) | oldest-message age over threshold (suggest 15 min normal; relaxed during announced bill-run windows) | generation and sending are decoupled (NFR-1); a stuck dispatcher silently stops all customer bills/notices. Also the §7/§8 autoscaling signal |
| **Provider error rates** (email ESP/BYO mailbox, later Stripe/Plaid/Twilio) | sustained elevation → warn; hard-down → page. On provider-down the queues HOLD, nothing is lost (SYS-PROVIDER 502/503 contract) | seams are expected to fail; the queue absorbs it — but only if someone notices |
| **Bill-run duration** | full cycle > 5 min → warn (budget breach, B6) | the one latency SLO the PO tracks |

Plus the infra baseline, with platform-specific twists:
- **DB partition growth & partition-job health**: next month's partitions must exist by
  mid-month (create job), detach jobs ran on schedule (NFR-6/28), per-partition size
  trend feeding the §7 trigger metrics (journal_lines row count IS a phase trigger);
- WAL-archive lag (**RPO 1h means archive lag > ~30 min is an incident**), backup
  success/failure (missed daily full = page), replication lag once replicas exist;
- Celery **beat liveness** (singleton — if beat dies, archival/retention/dispatch
  schedules silently stop);
- certificate expiry (§10 — one name, one validation record), synthetic checks on the
  demo URL (a PO deliverable), on `GET /` (the SPA must serve `index.html`), on a **deep
  client route** such as `/{tenant}/dashboard` (this is what catches a broken index.html
  fallback, and nothing else will) and on prod sign-in at `/{tenant}/signin`;
  99.9% availability tracking;
- p95 API latency (a §7 phase trigger), DB CPU/IOPS saturation, autovacuum backlog on the
  big five (a P3/cell-split trigger).

### 9.2 Logs — **DECIDED shape** (B12 §7)
Structured JSON logs carrying **`tenant`, `trace_id`, and the `US-ID`** of the code path;
every API error envelope carries `trace_id`, so support can go from a user screenshot to
the exact log line. Two boundaries to respect:
- **Ops logs are NOT the audit system.** The 7-year `audit_log` lives in Postgres
  (NFR-28) and is the compliance record; log sinks are for operations. Do not let anyone
  treat log retention as audit retention, or vice versa.
- **Retention aligned to the compliance schedule:** security-relevant event logs (auth
  events are logged in-app per SC-3; the ops copies of them) should be kept ≥ 1 year
  (suggest 13 months — **OPEN-FOR-DEVOPS**); general app/access logs 30–90 days per cost;
  never ship PII-bearing payloads to log sinks (the app masks by design, BR-CUS-045 —
  treat any unmasked PII in a log as a bug to raise).
- Log sinks stay in **US regions** (B6 residency applies to logs containing tenant data).

### 9.3 Tracing — **DECIDED intent, tooling per cloud**
Instrument once with **OpenTelemetry** (Django + Celery + psycopg auto-instrumentation),
export to X-Ray or Cloud Trace (§2 row 16). The `trace_id` in the API error envelope and
in logs is the correlation key across web → queue → worker → DB. Sampling: 100% of errors
always; head-sample successes (suggest 10% at P0–P1, tune down as volume grows).

### 9.4 Telemetry stack per phase, both clouds (**OPEN-FOR-DEVOPS** products; this is the recommended ramp)

| Phase | AWS | GCP | What you add |
|---|---|---|---|
| P0 | CloudWatch metrics/logs/alarms | Cloud Monitoring + Cloud Logging | The four §9.1 metrics + backup/WAL/beat/cert alarms; error sink (Sentry or equivalent); paging channel (even if it pages one person) |
| P1 | + dashboards, SNS→on-call tool, synthetics | + dashboards, alert channels, uptime checks | Per-environment dashboards; demo-URL synthetic; restore-test automation reporting (SC-5) |
| P2 | + Managed Prometheus/Grafana, X-Ray tracing on | + Managed Prometheus/Grafana, Cloud Trace on | SLO burn-rate alerts (99.9%), queue-based autoscaling wired to metrics, per-tenant rate-limit metrics |
| P3 | + log-based per-tenant anomaly metrics, per-cell dashboards | same | Cell-level views if split; capacity forecasting from partition growth trends |

### 9.5 Release-health checks that double as monitoring
Nightly, on main: the full gate stack + golden (33 assertions + 245-row expectation CSV)
+ isolation suite + all activated E2E journeys (B12 r3 §5). Treat a red nightly as an
incident feed, not just CI noise — it is the platform's own regression radar.

---

## 10. TLS + tenant-per-PATH routing ⚠ *(r3 — rewritten; r2's subdomain text is superseded)*

**DECIDED (PO, 2026-08-10): the domain is `smartbillhub.bynry.com`. DECIDED AND THEN
CHANGED THE SAME DAY (PO, 2026-08-10): tenancy is PATH-based, not subdomain-based.**

```
https://smartbillhub.bynry.com/{tenant}/…        screens  (SPA client routes)
https://smartbillhub.bynry.com/{tenant}/signin   sign-in
https://smartbillhub.bynry.com/api/{tenant}/…    tenant-scoped API
https://smartbillhub.bynry.com/api/public/…      catalog + slug availability (no tenant)
https://smartbillhub.bynry.com/api/tenants       POST = provisioning        (no tenant)
https://smartbillhub.bynry.com/api/jobs/{id}     job poll                   (no tenant seg.)
https://smartbillhub.bynry.com/api/exports…      export + download          (no tenant seg.)
https://smartbillhub.bynry.com/  /pricing  /signup  /signin-help            (public SPA)
```

**The routing model is still security-critical, and still server-side.** On every
request the middleware (`06-backend/core/tenancy.py`, BE-01) takes
`request.path_info`, extracts the **first segment after `/api/`**, resolves it to a
tenant, and sets `app.tenant_id` on the DB session — RLS does the rest. **Only the
SOURCE changed** (Host label → path segment); the law did not: the tenant is resolved
first, server-side, and **never from client-chosen input** (TD-4, BR-TEN-003). No
`X-Tenant-ID` header, no query param, no body field exists or may be introduced. The
route is deliberately **non-capturing**, so no view can even receive a `tenant=` kwarg.

Ops consequences — **DECIDED** behaviour you must preserve:

1. **One DNS record and a ONE-NAME TLS certificate: `smartbillhub.bynry.com`.**
   ⚠ **r2 required a three-level wildcard (`*.smartbillhub.bynry.com` + the apex) and
   a wildcard DNS record. Both are DELETED.** The wildcard existed solely because every
   tenant was its own hostname; certificates and DNS wildcards cover hostnames, and
   under path tenancy **there is only one hostname, forever.** The r2 warning that a
   corporate `*.bynry.com` certificate would not cover a four-label tenant host is
   likewise moot — no four-label host exists. Prefer a **delegated Route 53 hosted zone
   for `smartbillhub.bynry.com`** anyway (NS records in the parent `bynry.com` zone) so
   AWS owns the ALIAS and the single ACM validation record (§2 rows 9–10, runbook §1
   P3–P4). Alarm on expiry (§9.1). **New tenants still need no DNS change, no edge
   config and no certificate issuance** — and now there is not even a wildcard to
   depend on.
2. **The edge splits on PATH and must never rewrite it.** One rule: `/api/*` → the
   application origin, everything else → the SPA. The first segment after `/api/` *is*
   the tenant, so a path-rewrite rule at the edge is a tenant-rewrite rule.
   Correspondingly: **never cache an `/api/*` response** — one origin serves every
   tenant, so a cache key that ignores the tenant segment or the session cookie is a
   cross-tenant leak.
3. **The SPA must fall back to `index.html`** (HTTP 200, not a redirect) for any path
   that is not a real file, because `/{tenant}/settings/company` is a *client* route and
   Django serves no HTML. ⚠ On CloudFront this must be a **Function on the default
   behaviour**, never distribution-wide custom error responses — those would also
   rewrite the API's `404` into a `200`, and that `404` is the isolation answer (item 5).
4. **`Host` still matters, but no longer for tenancy.** Pass it through unmodified
   (`proxy_set_header Host $host;`-equivalent; managed **AllViewer** on the CloudFront
   API behaviour) so it satisfies `ALLOWED_HOSTS`, absolute-URL generation and future
   origin checks. A hop that rewrites it now produces a loud `400 DisallowedHost`
   instead of r2's feared silent collapse into "no tenant" — a better failure mode, and
   the same fix.
   **Django's `ALLOWED_HOSTS` is the single host `smartbillhub.bynry.com`, with NO
   leading dot** (§4.1). The r2 leading-dot form accepted any label anyone could point
   at the load balancer; dropping it is a real narrowing. Never `*`; never a bare
   `bynry.com`. ⚠ **AMENDED 2026-09-28 (`CR-144-BRC07`): THE TASK-IP APPEND IS
   WITHDRAWN.** This clause said ALB health checks arrive as `Host: <target-ip>`, are
   rejected with `400 DisallowedHost`, and that the fix was to append the task's own IP
   to `ALLOWED_HOSTS` at start-up. **The first sentence is still true and the fix is
   not.** `core.health.HealthCheckMiddleware` answers `/api/health` **first in the
   chain**, before host validation runs at all, so the probe never meets `ALLOWED_HOSTS`.
   **Do not append the task IP** — it changes on every placement, and widening the
   pattern is what this clause exists to forbid. On ECS the value is the API host and
   nothing else (runbook r4.3).
5. **Unknown tenant segments resolve to *no tenant***: the request proceeds with no
   tenant context and RLS denies all tenant data (deny-by-default). Cross-tenant
   resource requests return **404, never 403** — existence must not leak (B12 r1 HTTP
   contract, HR-1). Don't "fix" 404s that are actually isolation working, and don't add
   an edge rule that redirects a foreign-tenant request to the session's own tenant.
6. **Reserved first segments.** A tenant slug can never be
   `api signup signin pricing static assets public jobs exports health tenants` (nor the
   DNS-era carry-overs `www app admin mail billing support status help bynry
   smartbillhub`). Enforced in two places kept in step by a test:
   `core.tenancy.NON_TENANT_SEGMENTS` (resolution) and
   `apps.tenancy.selectors.RESERVED_SUBDOMAINS` (minting). **Adding a new root path is
   therefore a code change, not just an edge change** — check this list first.
7. TLS 1.2+ terminates at the LB/proxy — and **TLS 1.2+ everywhere internally too: app,
   DB, Redis, provider adapters; no plaintext listener anywhere** (NFR-31, recorded in
   the compliance mapping §2). mTLS between internal hops: **OPEN-FOR-DEVOPS**. Enable
   HSTS once one certificate renewal has been observed.
8. One static frontend bundle serves every tenant — and now with **no build-time
   configuration at all** (§4.2): tenant identity comes from the URL the browser is on,
   composed by `07-frontend/src/routing/tenantPath.ts` and
   `src/api/client.ts::apiPath()`. At P3, the tenant→cell map (§7) lives at the LB/CDN
   layer as **path-prefix rules**, not DNS records.

### 10.9 ⚠ NEW in r3 — one origin means the browser no longer isolates tenants

This is the security consequence of the ruling and the reason it needed a control it did
not need before. Subdomains gave tenant isolation away for free: one cookie jar per
host, so a Brazos Bend cookie could not physically be sent to Silver Creek. **One origin
removes that.** Two application rules replace it, both tested, both load-bearing:

1. a session row is **bound to its tenant** (`identity.sessions.tenant_id`);
2. a session presented on **another tenant's path is refused `404`** — never `403`
   (which would confirm the other tenant exists), never a silent switch to the session's
   own tenant. Raised in `apps/identity/auth.py::IdentitySessionAuthentication`, rendered
   by BE-02 with a body byte-identical to any other `404`. The acceptance-criterion test
   compares those bytes against `404`s from two unrelated code paths.

Ops must **preserve** this the way it must preserve RLS: no caching in front of
`/api/*`, no path rewriting, no "helpful" redirect of a foreign-tenant request, and no
treating the resulting `404` rate as a defect. One further user-visible consequence to
expect at the support desk: **one browser holds one tenant session at a time** (the
cookie name is fixed), so a staffer who works two utilities signs in and out.

---

## 11. Release runbook (per B12 r4/r6 — run at every release boundary R1→R4, staging first, then prod)

The delivery plan is four releases, each ending in a deployed, seeded, clickable product
(R1 "Set up your utility" → R2 "Bill" → R3 "Collect & close the books" → R4 "Switch on
the world"). The per-release runbook — **DECIDED sequence**, tooling yours:

```
0. Pre-flight    freeze release candidate; verify vault has every §4 var for the target
                 env; take a manual pre-release DB snapshot (belt over the PITR braces)
1. DEPLOY        build images (backend once → web/worker/beat; frontend `npm run build`);
                 roll out proxy/static/web/workers/beat
2. MIGRATE       apply §5 in order: extensions (idempotent) → `manage.py migrate`
                 (includes RLS policy + partition + immutability-trigger migrations,
                 migration-guard-vetted) — run BEFORE new app code serves traffic.
                 ⚠ IF THIS RELEASE BUMPS `lookup_defaults.json`'s `version`, run
                 `manage.py sweep_reference_data --dry-run` HERE and read the plan
                 before the deploy goes out (BR-TEN-076, restated in OQ-087's own
                 closure). It writes nothing and always exits 0. The real sweep is
                 automatic post-migrate on boot (§5 step 4b) — the dry-run is what
                 stops a bad fixture edit reaching every tenant at once
3. SEED          demo/staging only: Brazos Bend fixture family + one blank tenant
                 (`manage.py seed_demo` — §5 step 4). NEVER in prod; the command
                 refuses under production settings by design
4. RUN GATES     python3 10-scripts/gates/run_gates.py --wave-close  (release-scoped
                 G-stack incl. G4 golden money figures + G5 isolation/RLS probes —
                 both are merge/release BLOCKERS by law, no override exists)
5. JOURNEYS      run this release's ACTIVATED E2E journeys (G12; Playwright UI journeys +
                 API-level engine journeys, asserting against the expectation CSV).
                 A release cannot close with an activated journey red
6. PO WALKTHROUGH the PO clicks through the release's "what you can DO" list (B12 r4
                 table) on the deployed environment and signs off. R1's walkthrough
                 includes handing over THIS DOCUMENT
7. Post-release  update this doc (living-doc rule, r6) incl. §7 phase status; log any new
                 OPEN-FOR-DEVOPS decisions taken; tag the release; watch §9 alarms
                 through the first bill-run window
```

Rollback: application containers roll back freely (previous image). Database rollback is
**restore-based, not down-migration-based** — financial immutability (NFR-15) means
reverse migrations on financial tables are not a supported path; that is what step 0's
snapshot and PITR are for. Practice this on staging before R2 (the first release with
real money math).

---

## 12. Compliance controls — SOC 2 / NIST mapping for infrastructure

Source of truth: `04-docs/07-compliance/soc2-nist-mapping.md` (the SC battery is fully
CLOSED as of 2026-08-08 — no open compliance decisions), `pii-inventory.md` (column-level
PII register), `data-retention.md`. This table is the **infrastructure slice**: which
infra controls implement which SOC 2 Trust Services Criteria / NIST items, and what state
each is in. App-level controls (RBAC, sessions, masking) are listed only where ops can
break them.

| # | Infra control | Implements | SOC 2 / NIST | Status |
|---|---|---|---|---|
| 1 | TLS 1.2+ everywhere: LB policy, `sslmode=require`+ to Postgres, TLS to Redis, HTTPS-only provider adapters; no plaintext listener | NFR-31 (mapping §2, RECORDED) | CC6.7 / PR.DS-2 | **DECIDED** — you implement at §2 rows 1–2, 8 |
| 2 | Encryption at rest with KMS-managed keys: DB instance, volumes, buckets, backups, WAL archive | NFR-13 + OQ-016 closure (mapping §2) | CC6.1 / PR.DS-1 | **DECIDED** pattern; key config per cloud (§2 row 12) |
| 3 | KMS key material + strict key IAM for **app-layer encryption of HIGH PII** (EIN, DOB, TOTP secrets; gov-ID stored as tokenized last-4 only — full register in `pii-inventory.md`) | NFR-13, OQ-016 | CC6.1 | App code does the encrypting (**DECIDED**); key provisioning/rotation **OPEN-FOR-DEVOPS** |
| 4 | Tenant isolation: RLS FORCE + server-side GUC; isolation suite = zero-tolerance release blocker | NFR-10 (mapping §1) | CC6 / PR.AC | **DECIDED** — ops must PRESERVE it (§1 pooler caution, §6.5 restore test) |
| 5 | Cloud-account IAM least privilege: human + service roles scoped per environment, no shared credentials, no long-lived keys where roles work | mapping §1 (app RBAC COVERED; infra side standard practice) | CC6.2-3 / PR.AC-1,4 | Policy **DECIDED**; implementation **OPEN-FOR-DEVOPS** |
| 6 | Network segmentation: DB/Redis/app on private networks; only the LB public; least-open security groups/firewall rules | standard control (§2 row 18) | CC6.6 / PR.AC-5 | **OPEN-FOR-DEVOPS** to implement |
| 7 | Audit-log immutability + 7-year retention: append-only table, monthly partitions, 2yr hot → cold tier | NFR-15, NFR-28 (mapping §3) | CC7 / PR.PT-1 | **DECIDED** — app enforces append-only; ops provisions tiers (§6.3) |
| 8 | Security-event logging + alerting: auth events logged v1 (S61 auth class); **alert wiring is explicitly ops config** | SC-3 CONFIRMED (mapping §3), BR-AUD-004 | DE.CM | Logging **DECIDED**; alert rules **OPEN-FOR-DEVOPS** (§9) |
| 9 | Vulnerability management: continuous dependency-scan CI (exists: security-scan.yml) + container image scanning (§2 row 17) + infra patching + **ANNUAL pen test and before major releases** | SC-4 CONFIRMED (mapping §3) | CC7.1 / DE.CM-8 | CI scan **DECIDED**; image/infra scanning + pen-test vendor & scheduling **OPEN-FOR-DEVOPS** |
| 10 | Backups + PITR (RPO 1h/RTO 4h floor) + **quarterly automated restore test** + cross-region US copies | B6, SC-5 CONFIRMED (mapping §4) | A1 / PR.IP-4, RC | Targets & cadence **DECIDED**; tooling **OPEN-FOR-DEVOPS** (§6) |
| 11 | Incident response: 72h internal assessment target, state-law-driven notification; DR runbook integrated with on-call | SC-6 CONFIRMED (mapping §4) | RS | Process **DECIDED**; on-call/paging mechanics **OPEN-FOR-DEVOPS** |
| 12 | Secrets in vault only, per-env values, audited rotation (webhook keys + SECRET_KEY are 🔒 paths) | B12 §7 (§4 of this doc) | CC6.1 | Policy **DECIDED**; vault product **OPEN-FOR-DEVOPS** (§2 row 11) |
| 13 | Data residency: US-only for primary, replicas, backups, DR copies, log sinks, object storage | B6 (mapping §5) | P-series | **DECIDED** — constrains every region pick |
| 14 | Retention schedule enforcement: storage tiers + lifecycle rules matching §6.3, incl. write-once object lock (NFR-35) and closed-account PII kept 7yr masked | NFR-6..9/25/28/29/35, SC-7 CONFIRMED, `data-retention.md` | P-series / PR.IP | Schedule **DECIDED**; tier/lifecycle implementation **OPEN-FOR-DEVOPS** |
| 15 | Subprocessor register + DPAs: chosen cloud, monitoring/error-sink vendors, ESP — every vendor you introduce goes in the register | mapping §5 (register in audit-and-controls.md) | P | **OPEN-FOR-DEVOPS** action at each vendor choice |
| 16 | Change management: CODEOWNERS on 🔒 paths, migration-guard, trace-lint, gate stack G1–G12 merge-blocking; gate scripts themselves change-controlled (B12 r2) | mapping §3 | CC8 | **DECIDED** — ops must not bypass gates in deploy tooling |
| 17 | MFA: app-level MFA is v2 by PO ruling (SC-1) with documented compensating controls (mapping §6: IP allowlist, lockout, session limits, per-tenant identity, full auth audit) — **but cloud-console/IAM MFA for the ops team is standard and expected NOW** | SC-1 CONFIRMED (mapping §1, §6) | CC6 / PR.AC-7 | App side **DECIDED** (v2); console MFA **OPEN-FOR-DEVOPS** to enforce day one |

For SOC 2 scoping conversations: the mapping doc's §6 (compensating controls while MFA is
v2) is the auditor-facing narrative; keep this table and that doc in sync when you change
infra controls.

---

## 13. Known gaps to close in the R1 deploy lane (honest list — **re-verified item by item against the repo 2026-08-10 for r3**)

These are not decisions, they are TODOs the first deployment will hit. Items marked ⚠
**block the deploy**; the runbook's §10 carries the same list with the AWS-specific
consequence of each. **r3 re-read the code for every one of the 15 items rather than
carrying them forward** — three closed, one closed-and-replaced, two added.

1. **Production Dockerfiles still don't exist** — but ✅ **the WSGI entrypoint does.**
   Re-verified: `06-backend/config/wsgi.py` and `config/asgi.py` now exist and both
   default `DJANGO_SETTINGS_MODULE` to `config.settings.production` so a container
   without the variable fails closed. **Residue:** `pyproject.toml` still declares no
   gunicorn/uvicorn, so the production image must install a server explicitly; and the
   Dockerfiles that exist are dev-only — `09-infra/docker/api.Dockerfile` runs
   `manage.py runserver`, `web.Dockerfile` runs the Vite *dev server*, and
   `06-backend/Dockerfile.dev` says so in its header. DevOps writes the production image
   (runbook §4 step 6) with Eng review.
2. **Path mismatch in the dev Dockerfiles and frontend CI:** they reference `backend/`
   and `frontend/` but the repo directories are `06-backend/` and `07-frontend/`.
   Re-verified 2026-08-10: `.github/workflows/ci-backend.yml` **was fixed** to
   `06-backend`; `ci-frontend.yml` still says `working-directory: frontend`, and both
   files in `09-infra/docker/` still `COPY backend/` / `COPY frontend/`. Known; fix
   rides with item 1.
3. ~~`CELERY_BROKER_URL` not yet wired~~ — **CLOSED 2026-08-10**. ~~Replaced by a
   larger truth: Celery runs eagerly in-process and the broker carries nothing …
   deployed as-is every 202 job stays `queued` forever~~ — ✅ **THAT LARGER TRUTH IS
   CLOSED TOO, 2026-08-19.** It was right, it was written here in those words, and
   **nothing reads prose**: the state it described stood until a lane measured it and
   filed DEF-320. What it cost while it stood — every new tenant opening with no sample
   data, and a **bulk rate change that answered “accepted” and changed no price**
   (DEF-326) — is the argument for a check rather than a paragraph.
   **PO ruling 2026-08-19:** *“We want Async job install redis and celery; Trigger after
   tenant creation; also add these two services in docker compose”*, and *“we need
   Beat ; include it”*. `docker-compose.yml` now runs **three** services — `redis`, a
   `celery` worker and `celery-beat` — `apps/tenancy/tasks.py` is the transport, and
   `dispatch_job`'s non-eager branch reaches it. **Proved with three processes**, which
   is the only way this class of defect can be proved:
   `10-scripts/verify_celery_transport.py` runs a live worker against a live Redis under
   `JOBS_EAGER=false` and all four kinds reach `succeeded`.
   ⚠ **STILL OPEN, and it is two separate things.** (a) **None of it reaches the deployed
   host** — see the two `JOBS_EAGER` rows in §4.1. That half is UNCHANGED.
   (b) ~~**BEAT HAS NO SCHEDULE.**~~ **CORRECTED 2026-09-02 — beat has TWO entries now, and
   this clause has been wrong twice.** It read: *"There is no `beat_schedule` anywhere in
   `06-backend/config/`, and the three recurring jobs this document decided beat for —
   partition archival (NFR-6/28), report retention (NFR-9), dispatcher pacing (NFR-1) — are
   none of them built. The container connects and fires nothing."* The literal sentence
   about `06-backend/config/` is still true and is no longer the test: **a schedule is
   installed from an app's `ready()`, not declared in `config/`**, which is why grepping
   `config/` kept returning the old answer.

   * **`notifications.dispatch`** — dispatcher pacing (NFR-1), landed **2026-08-29**
     (`CR-048` B5, `apps/notifications/schedule.py`). One of the three this document named.
   * **`payments.collections_ladder`** — the collection sequence, landed **2026-09-02**
     (`CR-059` CS-10, `apps/payments/collections_schedule.py`). **NOT one of the three**:
     it is a fourth recurring job this document had not anticipated, and it is the first
     one that is PER-TENANT and runs on each utility's own business day rather than on a
     single clock — so beat owns a fifteen-minute sweep and the app owns the per-utility
     decision. Read that shape before adding another.
   ⚠ **AND THIS LIST WENT STALE, WHICH IS WHY IT SAID *"a fifth"* — CORRECTED 2026-09-23
   (`DEF-PAY-6268`).** It named two entries while FIVE were installed, and
   `counter_watch.py` and `sweep_open_counters.py` both said in their own docstrings that
   *"this repo has no beat schedule to add it to"* — so the notice that tells a supervisor
   about a counter nobody closed fired never. ⚠ **THERE ARE EIGHT — `G132` PASS on
   2026-09-28 names them — AND THIS LINE SAID SIX, THEN SEVEN, THE SAME DAY
   (`DEF-INF-7541`).** The fourth time this one count has been wrong, each time in the
   same direction and for the same reason: a schedule lands and the paragraph describing
   it does not move. The seventh correction added `identity.session_cleanup` to the old
   six by hand and never ran the gate, which would have named `reports.schedule_sweep`,
   landed the day before. `G132` counts them **from the code** rather than from this
   paragraph, which is the only version of this list that cannot rot — **run it, do not
   read this:** `python3 10-scripts/gates/g132_beat_entries_are_installed.py`.

   * **`work.rules_sweep`** — the Work rules sweep (`apps/work/rules.py`).
   * **`runbooks.schedule_sweep`** — Runbooks' scheduled Checks (`apps/runbooks/scheduler.py`).
   * **`customers.cut_date_watch`** — the disconnect cut-date watch, landed **2026-09-20**
     (`apps/customers/disconnect_schedule.py`). Reads cut dates and cuts nothing.
   * **`payments.counter_watch`** — the unclosed-till notice, landed **2026-09-23**
     (`CR-136-BRC07` `P2.11`, `apps/payments/counter_watch_schedule.py`). The second
     per-utility one: beat owns a fifteen-minute sweep and the app fires each utility at
     **06:00 on its own clock**. ⚠ **It TELLS and it never CLOSES** — PO ruling 2026-09-23
     §3.1 struck the blueprint's midnight auto-close, so no scheduled job may seal a till,
     and the absence of a write is asserted from the source of both modules.

   * **`reports.schedule_sweep`** — scheduled report deliveries, landed **2026-09-27**
     (`CR-142-BRC07` `P2.15`, `a2ad9b6c8`, `apps/reports/schedules.py`). Beat ticks every
     **60 seconds**; each schedule fires at **06:00 in its utility's own timezone** and a
     missed firing is fired once, never caught up N times. It enqueues the platform's own
     `list_export` job and deletes nothing.

   * **`identity.session_cleanup`** — the nightly session sweep, landed **2026-09-28**
     (`CR-145-BRC08` `B10`, `apps/identity/session_cleanup.py`), at **03:20 daily**.
     ⚠ **IT IS THE FIRST SCHEDULE IN THIS PRODUCT THAT DELETES A ROW**, and every other
     entry on this list only reads or writes. It removes sessions that have **already
     expired or been signed out** — two POSITIVE conditions, never the negation of
     *"live"*, because a `NOT` over three nullable columns is one `OR` away from matching
     every session in the product and this is a `DELETE`. **An idle session is not an
     expired one and is not touched.** The portal's half runs through the portal's own
     code, resolved by name, because a cross-module write is forbidden (`G78`/`G91`).

   * **`portal.draft_cleanup`** — unsent portal applications, landed **2026-10-02**
     (`CR-158-BRC10` §5, `apps/portal/draft_cleanup.py`), at **03:40 UTC daily**. The
     SECOND schedule that deletes a row. PO ruling 2026-10-02: an application the customer
     never sent, and the files they attached to it, are deleted **30 days after their last
     visit** (opening the link counts), in the utility's own calendar days — 1 October goes
     on 31 October. One `audit_log` row per application (`portal.application_draft.
     deleted_unsent`, file count, *"unsent 30 days"*, no personal content). It never touches
     a SENT application or the document store. Installed from `apps/portal/apps.py`'s
     `ready()`; `G132` PASS on 2026-10-02 counts **ten** entries with it.

   **Partition archival (NFR-6/28) and report retention (NFR-9) are still unbuilt**, and
   `TD-17`'s `manage.py maintain_partitions` still has no entry — which is the warning
   elsewhere in this document that partitioned inserts start failing months after deploy.
   ⚠ **AND (a) STILL GOVERNS BOTH ENTRIES:** on the deployed host neither fires, because
   that host has no reachable broker and no beat process. Adding the PROCESS is not adding
   the SCHEDULES, and adding a SCHEDULE is not running it — which is the same lesson one
   turn further on.
   ⚠ **BEAT RUNS EXACTLY ONE.** `deploy.replicas: 1` in compose, with the reason written
   beside the number: two beats do not conflict, they both fire — archival over the same
   range twice, retention DELETEs twice, pacing at double rate, and none of the three
   errors when it happens. §4 already asks for liveness alarming on this process; that
   belongs to the monitoring stack, outside `docker-compose.yml` (PO ruling 2026-08-10:
   the edge is managed elsewhere). Async bill runs are still TD-17 and still unbuilt.
4. ~~`ALLOWED_HOSTS` production wiring~~ — ✅ **CLOSED 2026-08-10.**
   `config/settings/production.py:22` reads
   `env.list("DJANGO_ALLOWED_HOSTS", default=[])`. ⚠ The **value** changed with the
   tenancy ruling: `smartbillhub.bynry.com`, one host, **no leading dot** (§4.1, §10.9).
5. ~~uuidv7 extension decision~~ — **CLOSED for AWS 2026-08-10**: `pg_uuidv7` is not on
   the RDS allowlist and is not needed — PKs are generated app-side (`core/dbfields.py`,
   RFC 9562 shim). `pgcrypto` + `citext` are both allowed and are created idempotently
   by `tenancy` migration `0001`, so no separate extensions step is required on RDS.
6. ✅ **Seeder now builds a real utility — CLOSED as to content.** Re-verified against
   `apps/tenancy/management/commands/seed_demo.py`: 5 charge codes · 2 taxes (+2
   jurisdictions) · 4 rate schedules · 3 published rate plans · 6 premises · 10 units ·
   5 routes · 2 cycles · 10 assets, all written **through each module's own service
   functions** under tenant context, idempotent on natural keys, with the walkthrough
   credentials and the `/{tenant}/signin` path printed at the end. Reads, customers,
   accounts, bills and payments remain unseeded and the command says so. ⚠ **Unchanged
   and still binding: it refuses to run under production settings** (`seed_demo.py:1010`)
   — see §3 and item 12, which together are the whole bootstrap problem.
7. **Closed-tenant offboarding (export + deletion SLA)** is still an OPEN retention row —
   re-verified: `04-docs/07-compliance/data-retention.md` line 12. Needs a ruling before
   the first tenant contract. *(Distinct from the day-91 audit purge, which the PO ruled
   on 2026-08-10.)*
8. ✅ **CLOSED 2026-08-10 — the SPA shares the origin with the API.** The API moved under
   `/api/` and the client prefixes it (§1). **Replaced by a build requirement, not a
   blocker:** whatever serves the SPA must fall back to `index.html` for unknown paths,
   or every deep link and refresh 404s (§10 item 3).
9. ~~**Export artifacts live on local container disk.**~~ ✅ **CLOSED 2026-10-02**
   (`DEF-MET-4954`). Export files are stored in the environment's S3 bucket at
   `t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>`, recorded in `job_artifacts`, handed
   over as a 4-hour signed link and swept daily per utility (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*). No shared
   volume, no EFS, no `JOB_ARTIFACTS_DIR`. Analysis: `09-infra/04-exports-to-s3.md`.
10. ~~**There is no S3 file service in the code.**~~ ⚠ **STALE SINCE `CR-049` (2026-08-30),
    CLOSED (`DEF-GOV-9149`).** It read *"`boto3` and `django-storages` appear nowhere"*;
    `apps/tenancy/document_storage.py` has written bills, notices and uploads to S3 since
    `CR-049`, and exports since 2026-10-02. Still true: the tenant logo is stored as
    **bytes in a DB column** (`tenants.logo_bytes`). *(The SPA bucket is unaffected.)*
11. ~~**No health endpoint.**~~ **CLOSED 2026-09-28 (`CR-144-BRC07`).** ⚠ This item
    said *"nothing serves one"* and told the LB to health-check
    `/api/public/pricing-plans`. **Both are now wrong.** `GET /api/health` (and
    `/api/health/`) answers `200 {"status":"ok"}` with no sign-in, no database and no
    Redis; `POST` is `405`. It is **middleware placed first**, not a route, which is
    what makes it survive `Host: <target-ip>` and an HTTPS redirect alike. `health`
    stays reserved on both lists so no customer can shadow it. Target-group settings:
    runbook r4.1.
12. ⚠ **The `subscription_plans` catalog is empty on a fresh production database — now
    the ONLY deploy blocker.** Re-verified: no migration seeds it;
    `apps/tenancy/services.py:238` validates the requested plan and fails with
    `signup.plan_unknown`; the only writer is `seed_demo._ensure_plans()`, which creates
    one plan and is refused under production settings. Needs signed SKU values and a
    supported bootstrap path from PO + Eng **before any customer — including the internal
    demo tenant — can self-serve**.
13. **Partition maintenance is manual.** Re-verified:
    `apps/audit/management/commands/maintain_partitions.py` exists; `config/celery.py`
    declares **no beat schedule** and no `tasks.py` exists in any app. Unscheduled,
    **audit inserts hard-fail ≈3 months in** — and every money action writes an audit
    row. Schedule it externally (runbook §9.4).
14. **App-side production security settings are absent.** Re-verified: the session cookie
    is set `httponly=True, samesite="Lax"` and **not `Secure`**
    (`apps/identity/api.py:175`); `production.py` (27 lines) has no `SECURE_SSL_REDIRECT`,
    `SECURE_HSTS_*`, `SECURE_PROXY_SSL_HEADER` or `CSRF_TRUSTED_ORIGINS`. Two notes:
    `SecurityMiddleware` **is** installed so those settings will take effect immediately;
    `CsrfViewMiddleware` is **not**, so `CSRF_TRUSTED_ORIGINS` would be inert until it is.
    ⚠ The missing `Secure` flag matters more under one origin than it did under
    subdomains — that cookie is now the sole carrier of tenant scope in a browser
    (§10.9). Eng fixes, not edge workarounds.
15. **No deploy pipeline.** Re-verified: `.github/workflows/` holds CI, gates,
    migration-guard, qa, security-scan and trace-lint, and **nothing** that builds or
    pushes an image, syncs the bundle, or updates a service. Whatever is built must not
    bypass the merge-blocking gate stack (§12 row 16).
16. ⚠ **NEW (r3) — most tenant endpoints do not accept the session cookie.**
    `apps/rating/api.py`, `apps/metering/api.py` and `apps/assets/api.py` declare **zero**
    `authentication_classes`, and `apps/tenancy/api.py`'s three are all on the platform
    paths (`/api/jobs/{id}`, `/api/exports`, `/api/exports/{id}/file`). A real cookie
    client therefore gets **401** on `/settings/*`, `/lookups/*`, `/plans*`, `/premises*`,
    `/assets*` and `/tenants/checklist` — identically for its own tenant, a foreign
    tenant and an unknown one, so **nothing leaks** (pinned by
    `tests/test_path_tenancy_session_binding.py`). It is a functional gap, not a tenancy
    one, and it is recorded in the API file's own trailer. **Consequence for deployment:
    the SPA loads and signs in, but most screens are empty-with-an-error.** Do not
    schedule a PO walkthrough of Settings, Plans & Rates, Premises or Assets against a
    hosted environment until it closes. Nothing at the edge can compensate.
17. ⚠ **NEW (r3) — behind a load balancer the app sees the load balancer.**
    `apps/identity/auth.py::client_ip()` reads `REMOTE_ADDR` only and says in a comment
    that `X-Forwarded-For` handling is "an infra concern"; DRF has no `NUM_PROXIES`.
    Result: **BR-IDN-020's per-tenant IP allowlist is meaningless** behind an ALB (every
    request looks like the LB), and DRF's throttle identity falls back to the whole
    `X-Forwarded-For` chain, which a client can prepend to — so the public 60/min
    onboarding throttle is bypassable. Interim mitigation is the WAF rate-based rule
    (§2 row 13), which is therefore **not optional**. The fix is Eng's, and it needs to
    be told how many trusted proxies sit in front (one with an ALB, two with CloudFront).

---

## 14. Decision ledger summary

| # | Topic | Status |
|---|---|---|
| 1 | Single Django deployable (modular monolith), 3 process shapes + beat singleton | DECIDED — TD-2, TD-17 |
| 2 | PostgreSQL 16 + Redis 7 | DECIDED — TD-3 |
| 3 | RLS FORCE + `app.tenant_id`; **the request PATH is the tenant resolver** (`/api/{tenant}/…`) | **DECIDED — TD-4, NFR-10, BR-TEN-003; SOURCE CHANGED 2026-08-10** from the Host header's first DNS label to the first path segment after `/api/` (PO ruling). The law is unchanged — resolved first, server-side, never from client-chosen input; only where the server reads it moved (§10) |
| 4 | DRF API; React/Vite static build | DECIDED — TD-19, TD-1 |
| 5 | Celery-on-Redis async; jobs idempotent/resumable | DECIDED — TD-17, NFR-4/16 |
| 6 | **Cloud is AWS**, US region(s) only | **DECIDED — PO 2026-08-10** (supersedes the 2026-08-09 "AWS or GCP"); B6 residency. GCP column in §2 is reference only. Executable path: `02-aws-runbook.md` |
| 7 | Env-var/vault secrets policy; no secrets in code | DECIDED — B12 §7 |
| 8 | Bootstrap order: extensions → migrations → RLS (B2 §3 template) → seed | DECIDED — B2/B11; RLS files 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09) |
| 9 | RPO 1h / RTO 4h floor / daily full + PITR / 99.9% / quarterly automated restore test | DECIDED — B6, SC-5 |
| 10 | Retention matrix (7yr financial+audit; partition cold tiers; write-once artifacts; closed-account PII 7yr masked) | DECIDED — NFR-6/7/8/9/25/28/29/35, SC-7 |
| 11 | Monthly partitioning of the big five; no financial pruning; AMI change-gate | DECIDED — NFR-24/25/27 |
| 12 | Object storage pattern (S3/GCS, per-tenant prefix, signed URLs, versioning + object lock) | DECIDED — TD-15, NFR-35 |
| 13 | Metric set: tie-out drift=0, queue oldest, provider errors, run <5min (+ partition-job health) | DECIDED — B12 §7, NFR-17 |
| 14 | Structured logs (tenant, trace_id, US-ID); logs ≠ audit system; US-resident sinks | DECIDED — B12 §7, NFR-28, B6 |
| 15 | TLS 1.2+ everywhere (external + internal); **single-name cert** + path preserved verbatim + `Host` passthrough + 404-not-403 isolation semantics | **DECIDED — NFR-31, TD-4, B12 r1; AMENDED 2026-08-10:** the wildcard certificate requirement is **deleted** with subdomain tenancy (row 31). `Host` passthrough is retained for host validation, not for tenancy; the new must-preserve is the **path** (§10 items 1–4) |
| 16 | Release runbook sequence (deploy→migrate→seed→gates→journeys→walkthrough); restore-based DB rollback | DECIDED — B12 r4/r6, NFR-15 |
| 17 | Scaling-phase frame P0→P3 driven by B6 capacity math; cell-split trigger named up front | DECIDED (this doc r1, from B6/NFR-24..30) — thresholds/cost bands ESTIMATE, tune with telemetry |
| 18 | Compliance control set + SC battery closures (SC-1..8) binding on infra | DECIDED — soc2-nist-mapping.md (battery CLOSED 2026-08-08) |
| **19a** | **Which cloud** | **DECIDED — AWS, PO 2026-08-10** (see row 6) |
| **19b** | Which **US region pair** (primary + DR copy) | **OPEN-FOR-DEVOPS** (decision-log PENDING row). Runbook §1 P2 suggests `us-east-1` / `us-west-2` |
| **30** | **Deployment posture: a sandbox that must behave like production** — internal demo tenant first, then real pipeline customers onto the **same** environment; backups, tenant isolation and monitoring are **day-one**. Maps to the P0→P1 band of §7 | **DECIDED — PO 2026-08-10.** Consequences amended into §3, §6.2 and §7 (Multi-AZ no longer deferrable at P0; first restore test precedes the first customer) |
| **31** | **Domain `smartbillhub.bynry.com`; tenants addressed by PATH** — screens `…/{tenant}/…`, API `…/api/{tenant}/…`; **one** ACM certificate name; **one** Route 53 A/ALIAS record | ⚠ **DECIDED AND CHANGED — both dates matter. DECIDED PO 2026-08-10** (domain `smartbillhub.bynry.com`, tenants at `<subdomain>.smartbillhub.bynry.com`, three-level wildcard cert + wildcard DNS). **CHANGED PO 2026-08-10, same day, reaffirmed after Eng-Lead pushback** (recorded and overruled — path-now/subdomain-later would pay two migrations; built as permanent). **DELETED by the change:** the wildcard certificate, the wildcard DNS record, the leading-dot `ALLOWED_HOSTS` form, `VITE_TENANT_HOST_SUFFIX`, and the cross-host signup handoff. **Now drives:** `ALLOWED_HOSTS=smartbillhub.bynry.com` (§4.1), an edge that splits on `/api/*` and preserves the path (§10 items 1–3), and the session-to-tenant binding that replaces host isolation (§10.9). Implemented and green — `06-backend/core/tenancy.py`, `06-backend/config/urls.py`, `07-frontend/src/routing/tenantPath.ts` |
| **32** | **Operated by a DevOps engineer** — the deliverable is a handover another human executes, not a self-deploy | **DECIDED — PO 2026-08-10.** `02-aws-runbook.md` is that handover; its §11 is the decisions the DevOps engineer makes and reports back |
| **33** | **One origin ⇒ the browser no longer isolates tenants; the session-to-tenant binding and its 404 refusal are the replacement control** | **DECIDED — PO 2026-08-10** (named with the path ruling as its acceptance criterion). Sessions carry `tenant_id`; a session on another tenant's path is refused **404**, byte-identical to any other 404 — never 403, never a silent switch. Ops must preserve it: no caching in front of `/api/*`, no path rewriting, no redirect of a foreign-tenant request (§10.9) |
| 20 | Orchestrator + IaC + CI/CD deploy mechanics | Orchestrator **RECOMMENDED: ECS on Fargate** with reasoning (runbook §2.1); IaC tool + pipeline still **OPEN-FOR-DEVOPS** |
| 21 | LB/proxy + ACM/DNS tooling on AWS (§2 rows 8–10) | ⚠ **REVISED 2026-08-10.** r2 recommended *ALB direct at P0* for one reason — nothing could then rewrite `Host`, which *was* the tenant. Path tenancy removes that reason, and the SPA now needs serving, so the choice is a genuine one: **A — CloudFront + S3 + ALB (recommended)** or **B — ALB with a static target group** (runbook §2.4). Either way: **single-name** DNS-validated ACM certificate + delegated Route 53 zone, `/api/*` split, path preserved, `/api/*` uncached, index.html fallback on the default behaviour only. Final pick **OPEN-FOR-DEVOPS** — report which, and how the fallback is implemented |
| 22 | Secret-vault + KMS key provisioning/rotation for app-layer PII keys | **OPEN-FOR-DEVOPS** (§12 rows 3, 12) |
| 23 | Managed-PG backup tooling config; per-phase RPO/RTO tightening beyond the B6 floor (§6.2) | **OPEN-FOR-DEVOPS** (must meet #9) |
| 24 | Telemetry stack products per phase (§9.4); ops-log retention values; error-sink vendor | **OPEN-FOR-DEVOPS** (must expose #13/#14) |
| 25 | Connection pooler (if any) — session mode only (§1 caution) | **OPEN-FOR-DEVOPS** |
| 26 | Worker/DB instance sizing per phase (start from §7/§8.2, tune on queue metrics) | **OPEN-FOR-DEVOPS** |
| 27 | Production Dockerfiles + build pipeline (gap list §13) | **OPEN-FOR-DEVOPS** (with Eng) |
| 28 | Network segmentation, console MFA, image scanning, pen-test vendor, subprocessor DPAs (§12 rows 5/6/9/15/17) | **OPEN-FOR-DEVOPS** (standard controls — implement, then record) |
| 29 | Closed-tenant offboarding export + deletion SLA | **OPEN** (needs PO/legal ruling — not a DevOps solo call; §6.3) |

---

*r1 · 2026-08-09 · pre-R1 draft, authored per B12 Addendum r6 + PO expansion of the same
date (scaling phases, AWS/GCP mapping, DR, telemetry, SOC2/NIST controls).*

*r2 · 2026-08-10 · amended for the PO's four deployment rulings (posture = production-
behaving sandbox; cloud = AWS; domain = `smartbillhub.bynry.com` with a three-level
wildcard cert; operated by a DevOps engineer), and re-verified against the repo — §1
`/api`-prefix correction, §4 environment-variable table corrected and extended, §13 gap
list expanded from 7 to 15 items. The executable AWS path now lives in
`09-infra/02-aws-runbook.md`.*

*r3 · 2026-08-10 (same day) · amended for the PO's **fifth** ruling: **tenancy moved from
subdomain to PATH** — `smartbillhub.bynry.com/{tenant}/…`, API `…/api/{tenant}/…` —
already implemented and green on both sides of the stack. **Deleted from r2:** the
three-level wildcard certificate, the wildcard DNS record, the leading-dot
`ALLOWED_HOSTS` form, `VITE_TENANT_HOST_SUFFIX` (and with it every frontend build
variable), and the cross-host signup handoff. **Rewritten:** §1 topology and its
`/api`-prefix correction (now CLOSED); §2 rows 5, 8, 9, 10; §4.1–4.3; §7's P3 cell-split
mechanism (a DNS map becomes an LB path-prefix map); §9.1's synthetics; §10 in full,
including the new §10.9 on what one origin costs and what replaces it. **Ledger:** row 3
re-sourced, row 15 amended, **row 31 marked decided-and-changed with both dates**, row 21
revised, row 33 added. **§13 re-verified item by item against the code** — items 4, 6 and
8 closed, item 1 partly closed, items 16 and 17 added. **No gate machine-checks
`09-infra/`;** the verification behind r3 is the repo reads cited inline. Update both
documents at every release boundary; record every OPEN-FOR-DEVOPS resolution in
`12-governance/02-decision-log.md`.*

---

## r4 · 2026-09-28 — ECS Fargate, two hosts, and the health probe (`CR-144-BRC07`)

**What changed in the topology, in one paragraph:** the SPA is no longer served by a
Node container that passes `/api/*` through to the API. It is **static files on S3
behind a CDN**, at `app[-env].bynry.com`, and the browser calls the API **directly** at
`api-smart360[-env].bynry.com`. Two hosts, on purpose — PO, verbatim: *"I dont want to
get locked in with the cdn from an cloud provider later if I move out from this cloud I
dont want this to be a blocker."* So there is no CDN path-routing of `/api/*` and
nothing CDN-specific in the code.

**Three consequences, each of which is a change somewhere else in this repo:**

| Consequence | Where it lands |
|---|---|
| Every browser call is **cross-origin** | `CORS_ALLOWED_ORIGINS`, one origin per environment, credentials on, never `*` |
| The two hosts are **the same SITE**, so `SameSite=Lax` does not separate them | `core/origin_guard.py` refuses a state-changing request from any other origin |
| **`TRUSTED_PROXY_COUNT` is still 1, for a different reason** | The frontend container is gone; the ALB is now the one proxy |

⚠ **THE SECOND ROW IS THE ONE THAT IS EASY TO MISS.** "Site" for a cookie means the
registrable domain — `bynry.com` — not the host, so a `SameSite=Lax` session cookie
rides along from **any** `*.bynry.com` page. DRF's default parsers accept form posts and
the session authenticator has no CSRF check, so a cross-origin `<form method=post>` is
**sent** with the victim's cookie and CORS merely hides the response from the attacker's
script — after the write has already happened. That is why there is a server-side guard
and not only a CORS policy.

**The API health probe** is `GET /api/health` (and `/api/health/`), answered by
`core.health.HealthCheckMiddleware` **first** in the chain — see runbook r4.1 for the
target-group settings and §10.8 there for why it is middleware rather than a route.

**Migrations** run in a one-off ECS task before the rollout, not in every web container
(§5's amendment above, runbook r4.2).

**Redis** is ElastiCache with **cluster mode OFF** — Serverless is cluster mode and will
not work, because the broker and the cache deliberately use two database indexes and
Redis Cluster supports only database 0 (runbook r4.4).

⚠ **`config.settings.local` MUST NEVER BE DEPLOYED, TO ANY ENVIRONMENT, DEV INCLUDED.**
`DEBUG=True`, `ALLOWED_HOSTS=["*"]`, a committed encryption key that protects nothing,
documents on local disk, and `RLS_ALLOW_BYPASSING_ROLE = True` — which means tenant
isolation is not enforced by the database at all.

*No gate machine-checks `09-infra/`. Everything above was read out of the code on
2026-09-28 and is cited to a file; re-read the files rather than trusting this page.*
