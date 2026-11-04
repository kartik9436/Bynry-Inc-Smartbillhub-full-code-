# 09-infra/02 — AWS Deployment Runbook (executable handover)

> **r2 · 2026-08-10 · Owner: Eng-Lead until handover, then DevOps.**
>
> This is the **executable** companion to `09-infra/01-deployment-architecture.md`.
> Doc 01 is the architecture — *what the platform is and which laws bind it*, written
> to be true on AWS **or** GCP. This document is *what a DevOps engineer types, in what
> order, on AWS*, for the environment the PO ruled on **2026-08-10**.
>
> **Read doc 01 first, once.** Do not re-derive its decisions here; where this runbook
> is silent on a rule, doc 01 governs. Where this runbook contradicts doc 01, it is
> because the 2026-08-10 rulings or the **verified state of the repo** moved — every
> such case is marked ⚠ and doc 01 has been amended to match.
>
> **Honesty contract.** Every command below was written against the repo as it stands
> on 2026-08-10. Where the repo cannot yet do what a step needs, the step says so in
> the step, not in a footnote, and §10 lists every one of them. **Nothing in §10 may
> be promised to a customer.**
>
> **No gate machine-checks `09-infra/`.** `run_gates.py` (G1–G12), `migration-guard`,
> `trace_lint` and the CI workflows do not read this directory — grep them and see.
> A green CI run means this document broke nothing else; it is **not** evidence that
> anything here is correct. The only verification behind r2 is the set of repo reads
> cited inline, each naming the file and, where it matters, the line.

---

## 0.0 ⚠ CHANGELOG — read this before you read a printed copy

| Rev | Date | What changed |
|---|---|---|
| **r1** | 2026-08-10 | First cut. **Assumed SUBDOMAIN tenancy** — every tenant at `<tenant>.smartbillhub.bynry.com`, the tenant resolved from the **Host header's first DNS label**. That model required a three-level wildcard TLS certificate (`*.smartbillhub.bynry.com` + the apex on one ACM cert), a wildcard Route53 record, `ALLOWED_HOSTS=.smartbillhub.bynry.com` (Django's leading-dot subdomain form), a `Host`-passthrough guarantee at every edge hop, and a cross-host handoff at signup. |
| **r2** | **2026-08-10** | **PO ruling of the same date: TENANCY IS PATH-BASED.** Screens are `smartbillhub.bynry.com/{tenant}/…`, the API is `smartbillhub.bynry.com/api/{tenant}/…`, and the public surface (`/`, `/pricing`, `/signup`, `/api/public/…`, `/api/tenants`, `/api/jobs/{id}`, `/api/exports…`) carries no tenant at all. Already implemented and green in the repo — see the decision-log rows of 2026-08-10 and `06-backend/core/tenancy.py`. |

**What r2 DELETES, and why — say this out loud to whoever chased the certificate:**

1. **The wildcard certificate is gone.** ACM now needs **one name: `smartbillhub.bynry.com`.**
   The wildcard existed for exactly one reason — every tenant was its own hostname, and a
   certificate has to cover the name in the URL bar. Under path tenancy **there is only
   ever one hostname**, so there is nothing left for a wildcard to match. The whole
   "`*.bynry.com` does not cover a four-label host" warning that dominated r1 §2.6 is
   therefore **moot**: no four-label host exists any more. Do not request
   `*.smartbillhub.bynry.com`; if it was already requested, delete it rather than leave a
   renewing certificate nobody uses (ACM auto-renewal keeps validation records alive and
   the expiry alarm of §9.2 then watches a certificate that serves nothing).
2. **Wildcard DNS is gone.** One `A`/ALIAS record for `smartbillhub.bynry.com` → the edge.
3. **`ALLOWED_HOSTS` is one host, no leading dot** (`smartbillhub.bynry.com`). The code
   already reads it from `DJANGO_ALLOWED_HOSTS` — `06-backend/config/settings/production.py:22`.
4. **The SPA/API origin collision r1 flagged as unresolvable is RESOLVED.** The API moved
   under `/api/…` (`06-backend/config/urls.py`), so one ALB rule splits the origin. §7.2
   is now the routing rule, not a blocker.
5. **There is no cross-host handoff at signup.** `POST /api/tenants` opens the owner's
   session inside the provisioning transaction and returns the `httpOnly` cookie
   (`apps/tenancy/api.py`), so the new owner lands signed in on the same origin.
6. **`Host` is no longer load-bearing for tenancy.** Nothing in the backend reads
   `request.get_host()` any more (`subdomain_of()` was deleted). `Host` still matters —
   `ALLOWED_HOSTS` validates it — but a hop that rewrites it now causes a **400**, loudly,
   instead of r1's feared silent collapse into "no tenant". That inverts r1's single
   strongest argument for keeping CloudFront out of the first cut (§2.4).

---

## 0. The rulings and what they change

| # | PO ruling (2026-08-10) | Consequence for this runbook |
|---|---|---|
| 1 | **Posture: a sandbox that must behave like production.** Internal demo tenant first, then **real pipeline customers onboarded onto the same environment**. | There is no "we'll add backups later." Multi-AZ RDS, automated backups + PITR, cross-region US backup copy, the four platform alarms, log retention and the RLS proof (§8) are **day-one steps**, not phase-two. This is doc 01's **P0 → P1 band** compressed: P0 *capacity*, P1 *durability and isolation*. |
| 2 | **Cloud: AWS.** | Doc 01 §2's GCP column is **reference only** from today. Every service below is named concretely. Region pair is still yours (§11). |
| 3 | **Domain: `smartbillhub.bynry.com`.** ⚠ **Amended the same day: tenancy is PATH-based** — `…/{tenant}/…` for screens, `…/api/{tenant}/…` for the API. | **One hostname, one ACM certificate name, one DNS record.** No wildcard cert, no wildcard DNS, no per-tenant anything at the edge. See §0.0 and §2.6. |
| 4 | **Operated by a DevOps engineer.** | This is a handover another human executes. Every step has a *verify* line, every open choice is collected in §11 as a decision you make and **report back**, and no step assumes access to the authoring session. |
| 5 | **Tenancy is PATH-based** (reaffirmed after Eng-Lead pushback; built as a permanent choice). | Tenant = the first path segment after `/api/`, read from `request.path_info`. The edge does not resolve tenants and must not try to. Because one origin now serves every tenant, the **browser no longer isolates them** — the session-to-tenant binding and its 404 refusal are the control that replaces host isolation (§7.5). Nothing you configure at the edge may rewrite the path. |

**Scope of the first cut.** The backend API **and the React SPA**, on one origin, with the
database, cache, edge and guarantees — deployed and *proven*. ⚠ r1 said the SPA was not
deployable; that was true of the root-mounted API and is no longer true (§7.2). What is
still true, and matters more than it sounds: **most tenant-scoped endpoints do not yet
accept the session cookie**, so the deployed SPA can sign in and reach a handful of
screens, not all of them (§10.14). Deploy it; do not demo it end to end.

---

## 1. Prerequisites — obtain these BEFORE step 1

Nothing below is something you can create yourself mid-deploy. Chase them in parallel;
the certificate and the DNS delegation have the longest lead time.

| # | Prerequisite | Detail / what "done" looks like | Owner to chase |
|---|---|---|---|
| P1 | **AWS account** (ideally an Organizations member account dedicated to SMARTBillHub) | Account ID recorded; billing alarm set; **console MFA enforced on every human principal** (doc 01 §12 row 17 — expected day one, no exceptions) | Bynry IT / whoever owns the AWS Organization |
| P2 | **Region pair chosen, both US** | Primary region (app + RDS) and a second US region for cross-region backup copies. B6 data residency is absolute: primary, replicas, backups, WAL archives, object storage and log sinks are **all US**. Recommendation: `us-east-1` primary / `us-west-2` DR copies — `us-east-1` also spares you a second certificate if CloudFront lands later (§2.6) | **You** — record in `12-governance/02-decision-log.md` |
| P3 | **DNS control for the single name `smartbillhub.bynry.com`** | ⚠ **r2: one record, not a wildcard.** Two acceptable shapes: **(a) preferred** — a *delegated* Route53 public hosted zone for `smartbillhub.bynry.com`, with an `NS` record set added in the parent `bynry.com` zone pointing at its four Route53 nameservers. AWS then owns the ALIAS and the ACM validation record with no further corporate tickets. **(b)** — the parent `bynry.com` zone stays wherever it lives and you get write access to add **two** records into it: the ACM validation `CNAME` and the `CNAME` to the edge. Note: `ALIAS` records exist **only** in Route53; under (b) a `CNAME` is legal here (this is a subdomain of `bynry.com`, not an apex) | Bynry IT / whoever runs `bynry.com` DNS |
| P4 | **ACM public certificate request for ONE name**, in the ALB's region (and see §2.4 if you front it with CloudFront): `smartbillhub.bynry.com` | ⚠ **r2: the wildcard is gone** — path tenancy means there is only ever one hostname, so there is nothing for a wildcard to cover (§0.0, §2.6). One name means **one** validation `CNAME`; it must read `Success` before the certificate leaves `PENDING_VALIDATION`. Do not proceed to the listener step on a pending cert. If a `*.smartbillhub.bynry.com` request already exists from r1, **delete it** — an unused auto-renewing certificate is a thing your expiry alarm will one day page you about for no reason | **You**, unblocked by P3 |
| P5 | **IAM roles, defined before any task runs** | Four at minimum: (i) an **ECS task execution role** (pull from ECR, write CloudWatch Logs, read the Secrets Manager secrets referenced in the task definition); (ii) an **ECS task role** per process shape — the app's own AWS identity, granting KMS decrypt on the app CMK, S3 read/write on the bucket's `t/*` keys and **`s3:DeleteObject` on `t/*/export/*` ONLY** (the export clean-up — policy text in §10.6), no EFS (exports are in S3 since 2026-10-02); (iii) a **deploy/CI role** (push to ECR, update ECS services) — federated via OIDC from GitHub Actions, **no long-lived access keys**; (iv) **human roles** scoped per environment, MFA-enforced, least privilege. Doc 01 §12 row 5 | **You** |
| P6 | **Secrets store: AWS Secrets Manager** | One secret per value, not one JSON blob per environment — rotation and IAM scoping both work per-secret. Minimum set at §6. **No secret ever lands in a task definition as a literal**, in an image, in a CI log, or in the repo (doc 01 §4, `B12 §7`) | **You** |
| P7 | **KMS customer-managed keys** | At least three CMKs: `sbh-rds` (DB + snapshots), `sbh-s3` (buckets + backup copies), `sbh-secrets` (Secrets Manager). A fourth, `sbh-pii`, is the app-layer HIGH-PII envelope key of doc 01 §12 row 3 — **provision it but expect no consumer yet** (§10.9) | **You** |
| P8 | **A container registry: ECR, scan-on-push enabled** | One repository for the backend image. Image scanning feeds the vuln-management control (doc 01 §12 row 9) | **You** |
| P9 | ~~Three blocking Eng changes~~ — **re-verified 2026-08-10, mostly CLOSED** (§10.1) | ✅ `config/wsgi.py` and `config/asgi.py` now exist and default to **production** settings (fail closed). ✅ `production.py:22` reads `ALLOWED_HOSTS` from `DJANGO_ALLOWED_HOSTS`. **Residue, still real:** `06-backend/pyproject.toml` declares **no gunicorn/uvicorn** — `pip install -e .` gives you an app with no server, so the image must install one explicitly (§4 step 6), and `JOBS_EAGER` is still a posture you must set deliberately (§6.1) | **You** (image) · **Eng-Lead** (whether the server belongs in `pyproject.toml`) |
| P10 | **Alert destination + on-call identity** | An SNS topic and at least one human who receives a page. "Tie-out drift ≠ 0" must reach a person within minutes (§9.2). Even a single-person rota is acceptable at this size; *no rota* is not | **You + Eng-Lead** |
| P11 | **Subprocessor register entry + DPA for AWS** | Adding AWS is a compliance action, not just procurement: record it in the subprocessor register and get the DPA signed (doc 01 §12 row 15) | Whoever owns Bynry vendor compliance |
| P12 | **Signed values for the `subscription_plans` catalog** | A production database has an **empty plan catalog** and every signup fails validation with `signup.plan_unknown` (§10.3). You cannot invent SKU prices — this is a PO/Eng deliverable before the first real customer | **PO + Eng-Lead** |

---

## 2. Concrete AWS service choices for P0 → P1, and why

The PO's posture ruling collapses doc 01's P0 and P1 into one build. Read the *why*
column — it is the part that tells you which knobs are safe to change.

### 2.1 Compute: **ECS on Fargate** (recommended over EC2)

| Process shape | Service | Sizing (start here, tune per §11) | Notes |
|---|---|---|---|
| Django web (WSGI) | ECS service, **desired 2**, spread across 2 AZs | 0.5 vCPU / 1 GB each | Behind the ALB target group. 2 replicas is what makes the "behaves like production" claim honest — a single task means a deploy is an outage |
| Celery worker | ECS service, **desired 1** | 0.5 vCPU / 1 GB | ⚠ Deploys with **no work to consume today** (§10.4). Run it anyway only if you want the plumbing proven; it is not load-bearing at R1 |
| Celery beat | ECS service, **desired 1, and only ever 1** | 0.25 vCPU / 0.5 GB | ⚠ **DEPLOY IT — THIS ROW SAID *"Do not deploy yet — no beat schedule exists"* UNTIL 2026-09-28 AND THAT HAD BEEN FALSE FOR A MONTH (`DEF-INF-7540`).** **Eight schedules are installed today** (`G132` PASS, 2026-09-28 — this cell said *"six, and `CR-145-BRC08` adds a seventh"* the same morning, and `reports.schedule_sweep` had landed the day before uncounted, `DEF-INF-7541`); `G132` counts them **from the code**, which is the only version of that number that cannot rot — run it rather than trusting this cell. **Not deploying beat means none of them ever fires**: the notification dispatcher, the collections ladder, the unclosed-till notice, the Work rules sweep, the Runbooks sweep, the disconnect cut-date watch, scheduled report deliveries and the nightly session cleanup all go silent, with nothing erroring anywhere. ⚠ **STILL DESIRED 1, AND THAT HALF WAS NEVER WRONG** — two beats do not conflict, they both fire, and nothing reports it. §9.4's scheduled task remains correct for partition maintenance, which is a `manage.py` command and not a beat entry. |
| Partition maintenance | **EventBridge Scheduler → ECS RunTask**, monthly | 0.25 vCPU / 0.5 GB | §9.4. This one is **not optional** — see §10.5 |

**Why Fargate and not EC2.** Four reasons, in the order they matter here:
1. **Ops headcount.** The whole platform exists for 1–2-person utilities and is run by
   one DevOps engineer. Fargate removes AMI patching, cluster capacity providers, and
   instance draining from your job — that is a direct reduction in the surface of
   doc 01 §12 row 9 (vulnerability management), not just convenience.
2. **Per-task IAM.** Each process shape gets its own task role. The web tasks need
   Secrets Manager, the DB and S3 (downloads are signed S3 links); the export workers need S3, including delete on `t/*/export/*` for the daily clean-up. No task needs EFS. On shared EC2 hosts
   that separation is instance-profile-shaped and leaks.
3. **The beat singleton is trivially expressible** as `desiredCount: 1` with no
   instance lifecycle to reason about. "Beat must never run twice" (doc 01 §1) is a
   correctness property; keeping it in the orchestrator's declarative surface is safer
   than keeping it in your head.
4. **The workload is small and bursty.** Bill runs are minutes-long spikes inside a
   mostly-idle month. Per-second billing on a right-sized task beats a permanently-on
   instance you sized for the spike.

**No persistent local disk — and the app no longer needs one.** ⚠ This paragraph
read *"you must attach EFS"* until 2026-10-02: export files were written to a local
`JOB_ARTIFACTS_DIR` and served back from it. Since then (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*) every export
goes to the environment's S3 bucket under `t/<web name>/export/` and a job builds its
file in its own `/tmp` folder, removed when it ends. **Attach no EFS.** Give each
`celery-billing` task ephemeral storage for a bill print set: about the size of the
archive, ~2.7 KB a bill (≈ 67 MB at the 25,000-bill ceiling); Fargate's default 20 GiB
is ample (`09-infra/04-exports-to-s3.md` §3).

### 2.2 Database: **RDS for PostgreSQL 16, Multi-AZ from the start**

| Setting | Value | Why |
|---|---|---|
| Engine | PostgreSQL **16** | TD-3. Not 15, not 17 — the schema and the partitioning behaviour were verified on 16 |
| Deployment | **Multi-AZ instance** (two-AZ, not the three-AZ cluster) | PO ruling 1: real customers land here. Failover in minutes buys the B6 RTO of 4h back many times over. The three-AZ *cluster* variant is a different engine topology — do not substitute it without re-reading doc 01 §1's session-GUC caution |
| Class (start) | `db.t4g.medium` (2 vCPU / 4 GB) | Doc 01 §7 P0/P1 sizing. `t4g` burst credits are fine for 1–10 tenants; move to `m7g.large` when DB CPU exceeds 50% sustained (doc 01 §7 trigger) |
| Storage | 100 GB **gp3**, autoscaling to 500 GB | Provision IOPS ahead of raw CPU for bill-run windows (doc 01 §8.3). 100 GB is generous for P0 — **financial tables are never pruned** (NFR-25), so the curve only goes up |
| Encryption | **KMS CMK `sbh-rds`** | Doc 01 §12 row 2 |
| Backups | **Automated, 35-day retention**, PITR on, **cross-region copy to the second US region** | B6 RPO 1h / RTO 4h are law floors. §9.1 |
| Deletion protection | **ON** | |
| Public accessibility | **OFF**, private subnets only | Doc 01 §12 row 6 |
| Parameter group | Custom, `rds.force_ssl = 1` | NFR-31: no plaintext listener anywhere |
| Extensions | `pgcrypto`, `citext` — both on the RDS allowlist, both created idempotently by `tenancy` migration `0001` | ⚠ `pg_uuidv7` is **not** on the RDS allowlist and **is not needed**: `core/dbfields.py` generates uuidv7 PKs app-side (B2 O-1 residue). Doc 01 §5 step 1 left this open; on AWS it is now closed — nothing to do |
| Master role | Not a superuser | On RDS the master user has `rolsuper = false` and `rolbypassrls = false`, which is exactly what §8 requires. **Never grant `BYPASSRLS`** to the app role, and re-verify with §8's canary after every restore |

**Connection pooling — read doc 01 §1 before you reach for RDS Proxy.** Tenant context
is a **session-scoped** Postgres GUC (`set_config('app.tenant_id', …, false)`). RDS
Proxy multiplexes in transaction mode by default; that would break tenant isolation
semantics. At P0–P1 you do not need a pooler at all. If you later do, it is
**session-pinning only**, and it is an Eng conversation, not an infra tweak.

### 2.3 Cache / broker: **ElastiCache for Redis**

`cache.t4g.micro`, single node at P0, **encryption in transit ON**, private subnets,
auth token in Secrets Manager. ⚠ Honest note: **the backend reads `CELERY_BROKER_URL`
but nothing enqueues to it today** (§10.4). Deploy Redis because the broker URL must
point somewhere real and because standing it up later is a change to every task
definition — not because work is flowing through it yet.

### 2.4 Edge: one origin, one split ⚠ *(r2 — this section is rewritten)*

**One hostname serves everything: the marketing pages, every tenant's screens, and the
API.** The split is by **path prefix**, and it is one rule:

```
/api/*   →  the Django target group          (the whole API, tenanted or not)
*        →  the SPA (index.html fallback)    (every screen, every tenant)
```

That is the entire edge routing contract. §7.2 gives the exact ALB rule and the two
supported ways to serve "the SPA" side of it.

**Why r1's "no CloudFront at P0" argument no longer applies.** r1 kept CloudFront out
because CloudFront can rewrite `Host`, and under subdomain tenancy `Host` *was* the
tenant. Under path tenancy nothing in the backend reads `Host` at all
(`core/tenancy.py` reads `request.path_info`; `subdomain_of()` was deleted), so a
rewritten `Host` no longer silently collapses tenants — it fails `ALLOWED_HOSTS` and
returns a loud `400`. The choice of edge is therefore now an ordinary engineering
choice, and it turns on **what serves the SPA**:

| Shape | What it is | When to pick it |
|---|---|---|
| **A — CloudFront + S3 + ALB** *(recommended)* | CloudFront distribution with two origins: S3 (private, OAC) holding `07-frontend/dist/`, and the ALB. Default behaviour → S3; `/api/*` behaviour → ALB. | The normal answer. The SPA is genuinely static, gets cached at the edge, and the Django tasks never serve a byte of JavaScript. |
| **B — ALB only, two target groups** | A second, tiny target group running nginx/Caddy over the built bundle with `try_files $uri /index.html;`. Listener rule `/api/*` → API TG; **default action** → static TG. | You want exactly one edge product at P0 and will accept one more Fargate task instead of a CDN. Fully expressible today. |

**If you pick A, three things are easy to get wrong and one of them is dangerous:**

1. **`Host` on the API behaviour.** Attach the managed **AllViewer** origin request
   policy to the `/api/*` behaviour so the viewer's `Host` (`smartbillhub.bynry.com`),
   cookies and `Authorization` reach Django. Without it CloudFront sends
   `Host: <alb-dns-name>` and every API call is a `400 DisallowedHost`.
   **Do not** attach AllViewer to the S3 behaviour — S3 rejects a foreign `Host`.
2. **Caching on the API behaviour must be OFF** (managed `CachingDisabled`) and the
   session cookie must be forwarded. A cached `/api/{tenant}/…` response is a
   cross-tenant leak with a CDN in front of it.
3. ⚠ **NEVER implement the SPA's index.html fallback with CloudFront *custom error
   responses*.** Custom error responses are **distribution-wide** — they apply to
   responses from *every* origin, including the ALB. Mapping `404 → /index.html (200)`
   would rewrite the API's `404` into a `200` page of HTML, and in this platform the
   `404` **is the tenant-isolation answer** (a foreign session on another tenant's path;
   HR-1, `apps/identity/auth.py`). You would convert the isolation refusal into an
   apparent success and break the acceptance criterion of the whole tenancy model.
   Do the fallback with a **CloudFront Function on viewer-request, attached to the
   default behaviour only**:
   ```js
   function handler(event) {
     var req = event.request;
     // no dot in the last segment ⇒ a client route, not a file
     if (req.uri.indexOf('.') === -1) { req.uri = '/index.html'; }
     return req;
   }
   ```
   `/api/*` has its own behaviour and never sees this function.

CloudFront requires its certificate in **`us-east-1`** regardless of where the app runs;
if your primary region is `us-east-1` the same single-name ACM certificate serves both,
otherwise request the same one name twice (once per region).

Also at the edge from day one:
- **AWS WAF** web ACL on the ALB: AWS managed common rule set + known-bad-inputs +
  a rate-based rule. The app owns the per-tenant `429 + Retry-After` contract
  (B12 r1); WAF is the crude outer layer, not a substitute.
- **Access logs to S3**, and the ALB in **public subnets** with only `:443` open to the
  internet. `:80` redirects to `:443`, never serves.
- TLS policy: **TLS 1.2 minimum** (NFR-31).

### 2.5 Storage

| Store | Use | Config |
|---|---|---|
| **S3 `sbh-prod-documents`** | TD-15 document store: uploads, e-signed agreements, import source files, report files. ⚠ **ONE BUCKET PER ENVIRONMENT, KEYS `t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext]` — e.g. `t/austin-water/billing/2026/09/<file id>.pdf` — and the key never names the bucket (`CR-160-BRC10`, PO 2026-10-02).** Files written before 2026-10-02 keep `t/<tenant id>/<yyyy>/<mm>/<file id>` and still open; nothing is moved | Versioning **ON**; ~~**Object Lock, compliance mode, 7-year** on the write-once classes (NFR-35)~~ ⚠ **NO OBJECT LOCK AND NO EXPIRY TAG ON ANY FILE FOR NOW, LEGAL FILES INCLUDED (`CR-160-BRC10`, PO: *"dont lock it"*) — and NO DEFAULT RETENTION RULE on the bucket, which the app refuses at boot (`smartbillhub.E002`)**; SSE-KMS with `sbh-s3`; Block Public Access **all four ON**; lifecycle: ~~report files expire 3 days (NFR-9)~~ ⚠ **NO EXPIRY RULE FOR EXPORTS — the app deletes them itself, once a day per utility, by their database rows (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*); a lifecycle rule could not tell an export from a bill in the same module folder anyway**; archived artifacts may transition to colder classes after 2 years. ⚠ ~~**No application code writes here yet** (§10.7)~~ — **the app writes here today: every bill, notice and upload since `CR-049`, and every EXPORT FILE since 2026-10-02 at `t/<web name>/export/<yyyy>/<mm>/<file id>.<csv\|zip>`** (`DEF-GOV-9149`) |
| **S3 `sbh-prod-backups`** | RDS snapshot copies, ALB access logs, future WAL/export archives | SSE-KMS, versioning ON, **replication to the second US region only** (B6) |
| **S3 `sbh-prod-web`** ⚠ *new in r2* | The built SPA (`07-frontend/dist/` — `index.html` + `assets/index-*.{js,css}`). Only under edge shape **A** (§2.4) | Block Public Access **all four ON**; served **only** through CloudFront with an Origin Access Control policy — never a public bucket, never a website endpoint. SSE-S3 is sufficient (public assets, no tenant data). Long `Cache-Control` on `assets/*` (content-hashed filenames), **`no-cache` on `index.html`** or a deploy will keep serving the old bundle |
| ~~**EFS `sbh-prod-artifacts`**~~ | ⚠ **REMOVED 2026-10-02 — DO NOT CREATE IT.** It held `JOB_ARTIFACTS_DIR`, the export files the app wrote and served back (`DEF-MET-4954`). Exports are in `sbh-prod-documents` under `t/<web name>/export/` now (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*: *"Removed -> Yes we will just be using S3"*). An EFS already created for this can be deleted once no download older than its utilities' retention is wanted from it | — |

### 2.6 TLS: one name ⚠ *(r2 — the wildcard requirement is DELETED)*

**Request exactly one name: `smartbillhub.bynry.com`.** Nothing else is needed and
nothing else should be requested.

r1 devoted this section to a three-level wildcard (`*.smartbillhub.bynry.com` plus the
apex on one certificate) and to a warning that a corporate `*.bynry.com` certificate
would not cover `brazosbend.smartbillhub.bynry.com`. **Both are obsolete**, for one
reason: under path tenancy **no tenant hostname exists**. `brazosbend` is a path
segment (`smartbillhub.bynry.com/brazosbend/…`), and a certificate covers hostnames,
not paths. A single-name certificate on the one host serves every tenant that will ever
exist, forever, with no reissue and no SAN list that grows.

Practical consequences, in the order you will meet them:
- **One validation record.** ACM validates per domain name; one name means one `CNAME`
  in the zone. Watch it to `Success`; a certificate in `PENDING_VALIDATION` cannot be
  attached to a listener.
- **A corporate `*.bynry.com` certificate now WOULD work** for this deployment, since
  `smartbillhub.bynry.com` is exactly one label under `bynry.com`. Prefer your own
  single-name ACM certificate anyway — ACM auto-renews it, it is scoped to this
  workload, and it does not couple your uptime to another team's renewal calendar.
- **If a wildcard was already issued for r1, delete it.** It serves nothing, it
  auto-renews forever, and it will eventually trip the §9.2 certificate-expiry alarm
  for a certificate no listener references.

### 2.7 Observability, keys, network — one line each

- **CloudWatch** metrics, Logs, alarms, dashboards (§9.2–9.3). Managed Prometheus is a
  P2 concern; do not build it now.
- **KMS** CMKs per P7, key rotation enabled.
- **VPC**: 2 AZs; public subnets carry only the ALB and NAT; private subnets carry ECS
  tasks, RDS and ElastiCache (no EFS since 2026-10-02). Security groups reference **other security groups**,
  never CIDRs, for the app→DB and app→Redis hops. **RDS and Redis must never be
  publicly reachable** (doc 01 §12 row 6).
- **VPC endpoints** for ECR, S3, Secrets Manager, CloudWatch Logs — this is a cost
  decision as much as a security one (§3).

### 2.8 Rough monthly cost — **ESTIMATE**

Order-of-magnitude planning figures for the primary US region, on-demand pricing, one
environment. Not a quote; not a commitment. Verify against the AWS pricing calculator
for your region before you tell anyone a number.

| Line | P0 (demo tenant + first pilots) | P1 (real customers, 5–10 tenants) |
|---|---|---|
| RDS PostgreSQL 16 Multi-AZ + 100 GB gp3 | ~$130–160 | ~$230–330 (`m7g.large`, more storage/IOPS) |
| ElastiCache Redis (`t4g.micro`) | ~$12 | ~$25 (with a replica) |
| ECS Fargate (2 web + 1 worker + scheduled tasks) | ~$60–90 | ~$120–200 |
| ALB (+ LCUs) | ~$20–25 | ~$25–35 |
| NAT Gateway | ~$35 (one) | ~$70 (one per AZ) |
| S3 + cross-region backup copies (no EFS since 2026-10-02) | ~$15–30 | ~$30–70 |
| CloudWatch (logs, metrics, alarms, dashboards) | ~$15–35 | ~$40–90 |
| WAF | ~$10–20 | ~$15–30 |
| Secrets Manager + KMS + ECR + Route53 | ~$12–18 | ~$15–25 |
| **SPA hosting** ⚠ *r2 — now at P0, because the SPA is deployable* | ~$5–15 (shape **A**: CloudFront + a near-empty S3 bucket) or ~$10–15 (shape **B**: one extra small Fargate task) | ~$10–25 |
| **Total (ESTIMATE)** | **≈ $315–445 / month** | **≈ $585–925 / month** |

⚠ **r2 delta:** the only cost change from r1 is the SPA line — r1 had no deployable
frontend, so CloudFront sat at `—` for P0. Dropping the wildcard certificate saves
nothing (ACM public certificates are free either way); it saves a *prerequisite*, not a
dollar. Everything else is unchanged.

This sits in the **upper half** of doc 01 §7's P0 band (~$200–500) — deliberately.
The PO's posture ruling turns Multi-AZ, WAF, cross-region backup copies and real
alarming on at P0, and those are most of the delta. The two biggest levers if you need
to cut: **one NAT gateway instead of two** (already assumed at P0; costs you AZ
redundancy for egress only) and **VPC endpoints** for ECR/S3/Logs, which pay for
themselves quickly once image pulls and log shipping stop traversing NAT.

---

## 3. Naming and tagging (adopt before step 1 — retrofitting tags is misery)

Resource names: `sbh-<env>-<component>` → `sbh-prod-db`, `sbh-prod-alb`, `sbh-prod-web`.
Tags on **everything**: `Project=SMARTBillHub`, `Environment=prod|staging|demo`,
`Owner=<your team>`, `DataClass=financial|operational`, `Compliance=SOC2`.
The `DataClass` tag is what makes the eventual SOC 2 evidence request answerable
without re-inventorying the account.

---

## 4. Deployment steps, in order

Each step: **what**, **how**, **verify**. Do not skip a verify — several later steps
fail in ways that look like earlier steps' bugs.

### Step 1 — Network

**What.** VPC `10.20.0.0/16`, 2 AZs, public + private subnets per AZ, IGW, one NAT
gateway (P0), route tables, and five security groups: `sg-alb`, `sg-web`, `sg-worker`,
`sg-db`, `sg-redis`.

**How.** Console or IaC (§11 — pick Terraform or CDK and commit it; a console-built
production environment is a single-person dependency). Security group rules:

| SG | Inbound | From |
|---|---|---|
| `sg-alb` | 443, 80 | `0.0.0.0/0` |
| `sg-web` | 8000 | `sg-alb` only |
| `sg-db` | 5432 | `sg-web`, `sg-worker` only |
| `sg-redis` | 6379 | `sg-web`, `sg-worker` only |

**Verify.** `aws ec2 describe-security-groups` shows **no** `0.0.0.0/0` ingress on
`sg-db` or `sg-redis`. The private route tables have **no** IGW route.

### Step 2 — KMS keys and Secrets Manager entries

**What.** The CMKs from P7 and the secret entries from §6.

**How.** Create the CMKs first (secrets and RDS reference them at creation). Then:

```bash
aws secretsmanager create-secret --name sbh/prod/DJANGO_SECRET_KEY \
  --kms-key-id alias/sbh-secrets \
  --secret-string "$(python3 -c 'import secrets;print(secrets.token_urlsafe(64))')"
```

Generate the secret key **on your machine and never echo it into a shared terminal**;
`DJANGO_SECRET_KEY` is on the project's 🔒 sensitive-path list, so its rotation is an
audited change (doc 01 §4).

**Verify.** `aws secretsmanager list-secrets` shows every `sbh/prod/*` name from §6, and
`aws kms describe-key` shows rotation enabled on each CMK.

### Step 3 — RDS PostgreSQL 16

**What.** The instance from §2.2, in the private subnet group, `sg-db`.

**How.** Create with Multi-AZ, `sbh-rds` CMK, 35-day backup retention, PITR, deletion
protection, the custom parameter group with `rds.force_ssl = 1`, and a maintenance
window outside US business hours. Store the connection string as
`sbh/prod/DATABASE_URL` in the **exact** shape `base.py`'s `env.db()` parses:

```
postgres://<user>:<password>@<endpoint>:5432/smartbillhub?sslmode=require
```

`sslmode=require` is the minimum; `verify-full` with the RDS CA bundle baked into the
image is better and is a §11 decision.

**Verify.**
```bash
psql "$DATABASE_URL" -c "SELECT version();"                     # → PostgreSQL 16.x
psql "$DATABASE_URL" -c "SHOW ssl;"                              # → on
psql "$DATABASE_URL" -c "SELECT rolname, rolsuper, rolbypassrls
                         FROM pg_roles WHERE rolname = current_user;"
# → rolsuper = f AND rolbypassrls = f.  If either is TRUE, STOP:
#   every isolation probe in §8 would pass vacuously.
```

### Step 4 — ElastiCache Redis

**What.** `cache.t4g.micro`, private subnet group, `sg-redis`, in-transit encryption,
auth token.

**How.** Store the URL as `sbh/prod/CELERY_BROKER_URL` in **`rediss://`** form (two
esses — TLS) including the auth token.

**Verify.** From a task in `sg-web`: `redis-cli -u "$CELERY_BROKER_URL" ping` → `PONG`.

### Step 5 — S3 buckets (no EFS)

**What.** The three stores from §2.5.

**How.** Create the buckets with Block Public Access on, SSE-KMS, versioning.
⚠ **`sbh-prod-documents`: ONE per environment, NO default retention rule, and
Object Lock is no longer required (`CR-160-BRC10`, PO 2026-10-02: *"we dont want
this to be enabled right now - dont lock it"*).** The app sends no lock and no
expiry tag (`DOCUMENT_STORAGE_OBJECT_LOCK_MODE` defaults to `NONE`). If the
utility may want per-file locking LATER, tick Object Lock ON at creation anyway —
AWS cannot add it afterwards — but leave **Default retention DISABLED**: a default
rule would lock every file, exports included, for its whole period, and in
COMPLIANCE mode nobody could delete one. Switching the lock on later
(`DOCUMENT_STORAGE_OBJECT_LOCK_MODE=COMPLIANCE` on the host) covers files written
after that moment only. *(Superseded instruction, kept: "apply Object Lock **at
bucket creation** on `sbh-prod-documents` (it cannot be enabled afterwards)".)* ⚠ **No EFS** (removed 2026-10-02 — exports are in this bucket under
`t/<web name>/export/`). Grant the task role `s3:DeleteObject` on
`arn:aws:s3:::sbh-prod-documents/t/*/export/*` and on nothing else (§10.6).

**Verify.** `aws s3api get-object-lock-configuration --bucket sbh-prod-documents`
returns EITHER `ObjectLockConfigurationNotFoundError` (no Object Lock) OR a
configuration with **no `Rule` / no `DefaultRetention`**. A `DefaultRetention`
in the answer is the one thing to fix before deploying — the app's boot check
refuses it (`smartbillhub.E002`) and names the console path to disable it
(`CR-160-BRC10`). *(Until 2026-10-02 this line said the command "returns a
retention configuration".)* `aws s3api get-public-access-block` shows all four
flags `true`. ⚠ The IAM policy simulator shows `s3:DeleteObject` **allowed** on `t/austin-water/export/2026/09/x.csv` and **denied** on `t/austin-water/billing/2026/09/x.pdf`.

⚠ **THE PARAGRAPH BELOW IS THE 2026-09-03 HISTORY AND APPLIES ONLY TO A HOST
THAT TYPES `DOCUMENT_STORAGE_OBJECT_LOCK_MODE=COMPLIANCE` OR `GOVERNANCE` BACK ON.**
Under `CR-160-BRC10` the default is `NONE`, which writes to a bucket without
Object Lock as it stands. A host whose `.env` already types `COMPLIANCE` keeps
locking until that `.env` is edited (hard-won law 4).

⚠ **RUN THAT FIRST COMMAND BEFORE ANYTHING IS DEPLOYED AGAINST THE BUCKET — IT IS
THE ONLY CHEAP MOMENT TO FIND THIS (`DEF-2363`, 2026-09-03).** The instruction two
paragraphs up is four days old and was still missed: a bucket was created without
Object Lock, and the product's first witness was a tenant creation stopping eight
steps in on S3's own sentence,
`InvalidRequest: … Bucket is missing ObjectLockConfiguration`, which names no
setting and does not say the bucket cannot be repaired. If the command answers

    An error occurred (ObjectLockConfigurationNotFoundError) …

that bucket will refuse every write this product makes. **Two ways out and no
third:** create a replacement bucket with Object Lock ticked ON and move anything
already in the old one across — the answer for anything that will hold real
documents — or, for a beta holding none, set
`DOCUMENT_STORAGE_OBJECT_LOCK_MODE=NONE` on that host, which sends no lock and
writes to the bucket as it stands (PO 2026-09-03: *"Until we are in beta mode We
should able to delete these pdfs"*). Nothing written under `NONE` is protected from
deletion, and `NFR-35` is unchanged for real documents. The application itself now
says all of this at the point of failure rather than relaying S3's string.

### Step 6 — Build and push images

**What.** One backend image (three process shapes, one artifact) pushed to ECR, **and**
the SPA bundle (`07-frontend/dist/`) built for whichever edge shape §2.4 you chose.

⚠ **r1 said this step was blocked. Re-verified 2026-08-10: it is not.**
`06-backend/config/wsgi.py` and `config/asgi.py` now exist and both default
`DJANGO_SETTINGS_MODULE` to `config.settings.production` (fail closed). **One residue is
still real:** `06-backend/pyproject.toml` declares **no gunicorn and no uvicorn**, so the
server is not a project dependency and the image must install it explicitly — as the
`Dockerfile` below does. Ask Eng whether it belongs in `pyproject.toml` (§11 item 18);
until it does, a pinned `gunicorn==x.y.z` in the image is the honest place for it.

Also still true: the existing Dockerfiles are **not** production artifacts.
`06-backend/Dockerfile.dev` runs `manage.py runserver` by its own header, and
`09-infra/docker/api.Dockerfile` / `web.Dockerfile` still `COPY backend/` and
`COPY frontend/` — the pre-rename paths (the directories are `06-backend/` and
`07-frontend/`). They are compose-only. Do not adapt them; write the production image.

**Backend image** — multi-stage on `python:3.12-slim`:

```
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "." "gunicorn==23.0.0"   # gunicorn is NOT in pyproject
COPY . .
# entrypoint appends the ECS task IP to DJANGO_ALLOWED_HOSTS (see §7.4)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
```

Three shapes, same image, different `command` overrides in the task definitions:
`gunicorn …` / `celery -A config.celery worker --loglevel=info` /
`celery -A config.celery beat --loglevel=info`.

**Frontend bundle** — `cd 07-frontend && npm ci && npm run build` produces
`dist/index.html` plus content-hashed `dist/assets/index-*.{js,css}`. ⚠ **There are no
`VITE_*` build variables to pass** (§6.3) — the bundle is environment-independent, so
one artifact serves every environment. Then either `aws s3 sync dist/ s3://sbh-prod-web/`
(shape A) or bake `dist/` into the static-server image (shape B).

**Never** bake a secret, a `.env`, or a settings default into either image. `.env` and
`.env.example` are local-dev conveniences and are not deployed (doc 01 §4).

**Verify.** `docker run --rm <image> python -c "import config.wsgi"` exits 0;
`aws ecr describe-image-scan-findings` returns no `CRITICAL` findings before you deploy;
`grep -r "smartbillhub.bynry" 07-frontend/dist/` finds **nothing** (the bundle must not
carry a hostname — it composes tenant URLs from `window.location`).

### Step 7 — ACM certificate and DNS validation

**What.** ⚠ **One certificate, one name** (P4 / §2.6): `smartbillhub.bynry.com`. Do the
cert now — its validation is the long pole. The record that points at the edge comes
later (step 10), once the ALB/distribution exists.

**How.**
```bash
aws acm request-certificate \
  --domain-name smartbillhub.bynry.com \
  --validation-method DNS \
  --region <primary-region>
# ⚠ NO --subject-alternative-names. r1's "*.smartbillhub.bynry.com" is DELETED:
#   path tenancy means no tenant hostname exists for a wildcard to cover.
```
Then read the single validation `CNAME` back and create it in the hosted zone (Route53
can do this for you in one click if the zone is in the same account — P3 option (a)):
```bash
aws acm describe-certificate --certificate-arn <arn> \
  --query 'Certificate.DomainValidationOptions[].ResourceRecord'
```
If you chose edge shape **A**, request the **same one name again in `us-east-1`** unless
your primary region already is `us-east-1` — CloudFront only accepts certificates there.

**Verify.** `aws acm describe-certificate` shows `"Status": "ISSUED"` and
`ValidationStatus: SUCCESS` for the single domain entry, and
`DomainValidationOptions` has **length 1**. Do not continue on `PENDING`.

### Step 8 — ALB, target groups, listener rules, WAF

**What.** Internet-facing ALB in the public subnets, `sg-alb`; the API target group
(IP-type, port 8000); HTTPS listener with the single-name cert; HTTP listener redirecting
to HTTPS; WAF web ACL associated; access logs to `sbh-prod-backups`. Under edge shape
**B**, a second target group for the static server.

**⚠ The routing rule (r2 — this is the whole thing).** On the `:443` listener:

| Priority | Condition | Action |
|---|---|---|
| 10 | **Path pattern `/api/*`** | forward → `tg-sbh-prod-api` (Django, port 8000) |
| — | *default* | shape **A**: this listener only ever sees `/api/*` (CloudFront sends the rest to S3) — set the default action to a fixed `404` response so a direct ALB hit cannot reach the SPA path space. Shape **B**: forward → `tg-sbh-prod-web` (the static server) |

Nothing else. No host conditions, no per-tenant rules, **no rule that rewrites the path**
— the first segment after `/api/` *is* the tenant (`core/tenancy.py::tenant_slug_of`), so
a path rewrite at the edge is a tenant rewrite.

**How the SPA side must behave.** `/{tenant}/settings/company`, `/brazosbend/checklist`,
`/pricing` and `/signup` are **client routes** — there is no file at those paths and
Django serves no HTML at all. Whatever serves the SPA must return `index.html` (HTTP
**200**, not a redirect) for any path that is not a real file, so a deep link and a
browser refresh both boot the app. Shape **A**: the CloudFront Function of §2.4 (**not**
custom error responses — read the warning there, it is the one that can break tenant
isolation). Shape **B**: nginx `try_files $uri /index.html;`. Assets are requested
absolutely (`/assets/index-*.js`), so depth of the client route does not matter.

**Target group health check (API).** ⚠ **AMENDED 2026-09-28 (`CR-144-BRC07`) — THE
SENTENCE THAT STOOD HERE, *"the app still has no health endpoint"*, IS NOW FALSE.**
There is one, at **`/api/health`**, and both caveats this paragraph used to carry are
gone with it. Do not health-check `/api/public/pricing-plans` any more.

| Target group setting | Value | Why this one |
|---|---|---|
| Protocol / port | **HTTP : 8000** | The ALB terminates TLS; the task speaks plain HTTP. |
| Path | **`/api/health`** | Not `/api/smart360/health/` — every `/api/<segment>/` is read as a **customer slug**, so that path would ask for a utility called `smart360`. |
| Success codes | **200** | The only code it can answer. `POST` is refused with 405; the probe never posts. |
| Healthy threshold | 2 | |
| Unhealthy threshold | 3 | |
| Interval | 15s | Nothing rate-limits it now, so the old "never below 10s" caveat is gone. |
| Timeout | 5s | The answer touches no database and no Redis; if it is slow, the process is wedged. |
| ECS **health-check grace period** | **60–90s** | Gunicorn boot plus the RLS-enforcement check. Set BELOW it and ECS kills a task that is still starting, for ever — a rollout that can never finish. |

**The two old caveats, and why neither applies:**
- **It is not rate-limited.** It is answered by middleware before DRF exists, so no
  throttle sees it. §10.15's warning about "per IP" behind a load balancer still holds
  for everything else.
- **`Host: <target-ip>:8000` no longer 400s** — and this is the whole reason the answer
  is middleware rather than a view. `core.health.HealthCheckMiddleware` is **FIRST** in
  `MIDDLEWARE`, ahead of Django's host validation and ahead of `SecurityMiddleware`, so
  it answers before `ALLOWED_HOSTS` is consulted and before any HTTPS redirect.
  **⚠ DO NOT add the task IP to `ALLOWED_HOSTS` for this** — it changes on every task
  placement, and it is no longer needed.
  ⚠ A target group stuck `unhealthy` with `400`s in the log now means **something was
  placed above the health middleware**, which is a code fault, not a configuration one.

**Verify from a shell, with no AWS console:**
```
curl -i -H 'Host: 10.0.1.23' http://<task-private-ip>:8000/api/health
curl -i https://api-smart360.bynry.com/api/health        # through the ALB
curl -i -X POST https://api-smart360.bynry.com/api/health # expect 405
```
The first is the one that matters: a `200 {"status":"ok"}` for a Host the app has never
heard of is the property this whole design rests on.

**Verify.** Target group shows both targets `healthy`. `curl -I https://<alb-dns-name>/`
completes the TLS handshake (a `400` body here is expected and correct — the ALB DNS
name is not in `ALLOWED_HOSTS`).

### Step 9 — ECS cluster, task definitions, services

**What.** Cluster `sbh-prod`; task definitions per §2.1; services in the private subnets
with `sg-web` / `sg-worker`; the web service registered to the target group.

**How.** Inject every secret via the task definition's `secrets` block (ARN references,
resolved by the **execution role** at start), and every non-secret via `environment`.
Both lists are in §6. ⚠ **Mount no EFS** (removed 2026-10-02; exports are in S3). Log driver `awslogs` to
`/ecs/sbh-prod/{web,worker,beat}`, retention per §9.3.

Set `minimumHealthyPercent: 100` / `maximumPercent: 200` on the web service so a deploy
is a rolling replacement, not a gap.

**Verify.** `aws ecs describe-services` shows `runningCount == desiredCount`; the web
log group carries gunicorn startup lines and **no** `DisallowedHost` or
`ImproperlyConfigured` tracebacks.

### Step 10 — DNS record

**What.** ⚠ **One record.** r1 created two (the apex and a wildcard); the wildcard is
**deleted** — path tenancy means there is no second hostname to resolve.

**How.** In the `smartbillhub.bynry.com` hosted zone (P3 option (a)):

| Name | Type | Value |
|---|---|---|
| `smartbillhub.bynry.com` | `A` — ALIAS | the edge (the CloudFront distribution under shape **A**, the ALB under shape **B**) |

Under P3 option (b) it is a `CNAME` to the edge's DNS name. **Do not create
`*.smartbillhub.bynry.com`;** if r1's wildcard record exists, delete it — it would
answer for hostnames the certificate no longer covers, which is a confusing TLS error
instead of a clean `NXDOMAIN`.

**Verify.**
```bash
dig +short smartbillhub.bynry.com                 # → the edge
dig +short brazosbend.smartbillhub.bynry.com      # → NXDOMAIN / empty.  CORRECT under
                                                  #   path tenancy: tenants are paths.
openssl s_client -connect smartbillhub.bynry.com:443 \
  -servername smartbillhub.bynry.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName
# → SAN lists exactly smartbillhub.bynry.com.  A wildcard here means the r1 cert is
#   still attached; swap the listener to the single-name one.
```
**New tenants need no DNS change and no certificate change** — they never did under the
wildcard either, and now there is not even a wildcard to depend on. Self-serve onboarding
is a database row and nothing else.

### Step 11 — Migrate

**What.** Doc 01 §5's bootstrap, in order. Order is not stylistic: RLS
policies reference columns the migrations create.

⚠ **STEP 0 FIRST, AND IT DID NOT EXIST UNTIL 2026-08-24 (DEF-622).** On a brand-new RDS
database `migrate` **fails outright** with
`ProgrammingError: unrecognized configuration parameter "app.tenant_id"`, raised inside
PostgreSQL's foreign-key validation scan — because `FORCE ROW LEVEL SECURITY` applies the
tenant policy to the table owner, and the table owner is the role running the migration.
Setting the parameter to `''` fails one step later with
`DataError: invalid input syntax for type uuid: ""`. Provision the tenant-context default
**before** the ECS task below:

```bash
# from a bastion / one-off task that can reach the DB, with a DBA connection:
psql "$ADMIN_DATABASE_URL" \
  -c "ALTER DATABASE \"sbh_prod\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
psql "$ADMIN_DATABASE_URL" \
  -c "ALTER ROLE \"sbh_app\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
```

or, from a checkout, `10-scripts/13-provision-database.sh --tenant-guc --role-guc --verify`.
The nil UUID casts (so the policy evaluates rather than erroring) and matches no row (so
deny-by-default is unchanged); nothing is granted to any role and RLS stays `ENABLE`+`FORCE`
on every table. Full note: `06-backend/db/001_tenant_context_default.sql`, doc 01 §5 step 0.

⚠ **APPLY THE MIGRATIONS STEP BY STEP, NOT IN ONE `migrate`** — PO ruling 2026-08-24
(OQ-354), verbatim: *"You will ahve to do the migration step by step - you will ahve to
consier a depands on b , b depends on c - so build the sequence of migration"*.
`app.tenant_id` is a SESSION variable, so one `migrate` over one connection lets a data step
that clears tenant context poison every later migration's foreign-key validation.
`10-scripts/13-provision-database.sh --migrate` reads Django's own `migrate --plan` and runs
each entry in its own process. **No `BYPASSRLS` is granted at any point** — an earlier draft
proposed a temporary grant and the PO ruled it out; the script refuses the flag by name, and
a standing `BYPASSRLS` on the app role is a hole in hard rule 1 that Step 12's
`SELECT rolname, rolsuper, rolbypassrls` check exists to catch.

⚠ **A FIRST DEPLOY CURRENTLY STOPS AT STEP 12 OF 163 (OQ-354, open half).**
`assets.0003_meter_types_and_read_methods` poisons itself — Django defers its foreign-key
constraints to the migration's exit, after its own data step has set `app.tenant_id` to `''`
— and no runner outside the migration can reach between its parts. The fix is three lines in
three committed migrations (leave the NO-TENANT sentinel, not the empty string) and needs the
append-only migration-guard exception. **Do not work around it with a grant.**

⚠ **LAW 4 — an EXISTING environment gets none of this from a deploy.** Every database
provisioned before 2026-08-24 carries `app.tenant_id` as `''` or not at all and keeps
booting fine (migrate is a no-op once applied). It breaks on the **next** migration that
adds a foreign key to a tenant table. Run the two `ALTER`s above once per existing
database. Check what a host holds:
`psql "$DATABASE_URL" -c "SELECT current_setting('app.tenant_id', true)"`.

**How.** Run as a **one-off ECS task** using the same image and task role (never from a
laptop — the DB is not publicly reachable, and it must stay that way):

```bash
aws ecs run-task --cluster sbh-prod --launch-type FARGATE \
  --task-definition sbh-prod-web \
  --network-configuration "awsvpcConfiguration={subnets=[<private>],securityGroups=[<sg-web>]}" \
  --overrides '{"containerOverrides":[{"name":"web",
      "command":["python","manage.py","migrate","--noinput"]}]}'
```

Extensions (`pgcrypto`, `citext`) are created **idempotently by `tenancy` migration
`0001`**, so `06-backend/db/000_extensions.sql` needs no separate step on RDS. The RLS
policies, the monthly partitions and the append-only triggers all ride **inside** the
migrations — there is no separate "apply RLS" command, and you must never hand-patch a
policy in production (doc 01 §5 step 3).

**Verify.**
```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM information_schema.tables
                         WHERE table_schema='public';"      # → ~72
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_class c
                         JOIN pg_namespace n ON n.oid=c.relnamespace
                         WHERE n.nspname='public'
                           AND c.relrowsecurity AND c.relforcerowsecurity;"  # → 53
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_policies WHERE schemaname='public';" # → 53
```
53 tables with `ENABLE`+`FORCE` and 53 policies is the verified W0+W1 figure. **A lower
number means a migration did not apply and tenant data is unprotected — stop and fix
before anything writes.** Then run §8 in full.

### Step 12 — RLS verification

**Do not skip this and do not defer it.** §8 is a step in this sequence, not an
appendix. It is what turns "we deployed a multi-tenant app" into "we proved tenants
cannot see each other."

### Step 13 — Catalog bootstrap and the internal demo tenant

**What.** A usable environment: the SKU catalog, then the internal demo tenant.

⚠ **`manage.py seed_demo` refuses to run under `config.settings.production`** — by
design (`seed_demo.py`: *"fixtures never reach prod"*). That guard collides with PO
ruling 1, which puts the internal demo tenant and real customers on the same
environment. Resolve it the honest way:

1. **The `subscription_plans` catalog must exist first** or every signup fails with
   `signup.plan_unknown` (§10.3 — still real; `apps/tenancy/services.py:238` validates
   the requested plan against that table). No migration seeds it and `seed_demo` is
   refused here. This needs **signed values and a supported path from Eng/PO** (P12) —
   do not invent a price and do not `INSERT` into a platform table by hand on your own
   authority.
2. **Create the internal demo tenant through the real product**, not through a seeder:
   ⚠ `POST https://smartbillhub.bynry.com/api/tenants` — note the `/api` prefix (r1 said
   `/tenants`). It is the public, `AllowAny`, idempotent provisioning endpoint the signup
   wizard itself calls (`BR-TEN-010`: replay returns the existing tenant). This exercises
   the same path a real customer will, which is precisely what "a sandbox that behaves
   like production" is supposed to mean.
   ⚠ **r2:** a *first* commit now also **signs the owner in** — the response carries the
   `sbh_session` httpOnly cookie and `signed_in` in the body (PO ruling 2026-08-10,
   superseding BR-TEN-045). A **replay deliberately gets neither**, because a replay
   verifies no password; that is correct, not a bug, and it is why you cannot "re-run
   provisioning to get a session".
3. Fixture data beyond that does not exist on this environment at all: ⚠ **r2 —
   `seed_demo` now seeds a genuinely walkthrough-ready utility** (§10.10), but it still
   refuses under production settings, so none of it reaches here. Meter reads, customers,
   accounts, bills and payments have no seeder anywhere.

**Verify.** `curl https://smartbillhub.bynry.com/api/public/pricing-plans` returns the
catalog, and `POST /api/tenants` returns `201` with a `Location` header. Then §14.

### Step 14 — Smoke test ⚠ *(r2 — every URL below changed; r1's are all wrong now)*

```bash
H=https://smartbillhub.bynry.com

# 1. The public API answers, TLS valid
curl -sSI  $H/api/public/pricing-plans | head -1                    # 200

# 2. The SPA is served at the root
curl -sSI  $H/ | head -1                                            # 200, text/html

# 3. THE SPA FALLBACK — a deep CLIENT route must boot the app, not 404.
#    This is the check that fails when the index.html fallback is missing.
curl -sSI  $H/brazosbend/settings/company | head -1                 # 200, text/html
curl -sS   $H/brazosbend/settings/company | grep -c '<div id="root"' # 1
#    …and a real asset is still a real asset, not index.html:
curl -sSI  $H/assets/<the-hashed-bundle>.js | head -1               # 200, application/javascript

# 4. An UNKNOWN tenant in the API path is a 404 — not a 403, not a 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
     $H/api/nosuchtenant/auth/session \
     -H 'Content-Type: application/json' \
     -d '{"email":"a@b.c","password":"x","keep_signed_in":false}'   # 404

# 5. Sign-in on the tenant's API path sets the session cookie
curl -sS -c /tmp/c.txt -X POST $H/api/brazosbend/auth/session \
     -H 'Content-Type: application/json' \
     -d '{"email":"...","password":"...","keep_signed_in":false}'   # 201 + Set-Cookie: sbh_session

# 6. A tenant-scoped read works WITH the cookie
curl -sS -b /tmp/c.txt $H/api/brazosbend/me                         # 200 + the user payload

# 7. THE ACCEPTANCE CRITERION OF PATH TENANCY — the same cookie on ANOTHER
#    tenant's path is refused 404, and the body is byte-identical to any other
#    404 (trace_id aside). One origin means one cookie jar; this is the control
#    that replaces the host isolation subdomains used to give for free.
curl -sS -b /tmp/c.txt -o /dev/null -w '%{http_code}\n' \
     $H/api/<another-real-tenant>/me                                # 404  (never 401, never 403)

# 8. Cross-tenant id-guessing inside your own tenant is the same 404
curl -sS -b /tmp/c.txt -o /dev/null -w '%{http_code}\n' \
     $H/api/brazosbend/audit-log/<an-id-owned-by-another-tenant>    # 404
```

Checks 7 and 8 are the ones people misread as bugs. **404 is isolation working**
(doc 01 §10, B12 r1 HR-1, `apps/identity/auth.py`). Never "fix" either into a 403 — a
403 confirms the other tenant exists, and existence is exactly what must not leak.

⚠ **Expect a 401, not a 200, on most other tenant endpoints** — `/api/{t}/settings/*`,
`/api/{t}/lookups/*`, `/api/{t}/plans*`, `/api/{t}/premises*`, `/api/{t}/assets*`,
`/api/{t}/tenants/checklist`. That is **not** a deployment fault: those modules declare
no `authentication_classes`, so the session cookie is never attached. See §10.14 — it is
the difference between "the SPA loads" and "the SPA works", and it is an Eng ask, not
something to route around at the edge.

---

## 5. Rollback

Application containers roll back freely — redeploy the previous task definition
revision. **Database rollback is restore-based, never down-migration-based**: financial
immutability (NFR-15) means reverse migrations on financial tables are not a supported
path. That is what the pre-release manual snapshot (doc 01 §11 step 0) and PITR are for.
Rehearse this on staging before the first release that carries real money math.

---

## 6. Environment variables — the exact set

⚠ **Re-read from the code on 2026-08-10 for r2**: `06-backend/config/settings/base.py`,
`production.py`, `config/wsgi.py`, `config/asgi.py`, `config/celery.py`, `manage.py`,
the root `.env.example`, `07-frontend/README.md` and `07-frontend/src/vite-env.d.ts`.
**Two rows moved and one row was deleted** — see §6.2 and §6.3.

### 6.1 Backend — variables the code reads TODAY

Everything the running app consults. There is nothing else; `base.py` calls `env()`
exactly five times and `production.py` adds two.

| Variable | Read at | Value for AWS prod | Source | Required? |
|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `manage.py` and `config/celery.py` default to `config.settings.local`; ⚠ **`config/wsgi.py` and `config/asgi.py` default to `config.settings.production`** (fail closed) | `config.settings.production` | task def `environment` | **YES** on **every** shape — web, worker, beat, and every one-off task. `manage.py` (migrate, `maintain_partitions`) still defaults to **local**, so a one-off task that omits it silently runs against dev settings |
| **`DJANGO_ALLOWED_HOSTS`** ⚠ *promoted from §6.2 in r2 — the code now reads it* | `production.py:22` — `env.list("DJANGO_ALLOWED_HOSTS", default=[])` | **`smartbillhub.bynry.com`** — ⚠ **one host, NO leading dot.** r1 said `.smartbillhub.bynry.com`; that wildcard form is deleted with subdomain tenancy (§7.3) | task def `environment` | **YES.** `DEBUG=False` with an empty list rejects **every** request, including the health check |
| `DJANGO_SECRET_KEY` | `base.py` (default `dev-only-insecure`) | 64-byte URL-safe random | Secrets Manager `sbh/prod/DJANGO_SECRET_KEY` | **YES**. Distinct per environment. 🔒 audited rotation |
| `DATABASE_URL` | `base.py` `env.db()` | `postgres://…:5432/smartbillhub?sslmode=require` | Secrets Manager `sbh/prod/DATABASE_URL` | **YES** |
| `CELERY_BROKER_URL` | `base.py` (default `redis://localhost:6379/0`) | `rediss://…:6379/0` | Secrets Manager `sbh/prod/CELERY_BROKER_URL` | **YES** — the library default points at localhost and will silently not work |
| `JOBS_EAGER` | `base.py` (default `True`); **`production.py` overrides the default to `False`** | ⚠ **`true`** — see §10.4 | task def `environment` | **YES, set it explicitly.** Left unset under production settings it is `False`, and with no Celery task registered **every export job stays `queued` forever**. Setting it `true` runs job bodies inside the web request — acceptable for R1's export-sized jobs, **not** acceptable once bill runs exist. ⚠ **AND NOT FOR UPLOADS ABOVE THE ASYNC BAR (`DEF-AST-8103`, 2026-09-30).** An import stage over its row bar (`import_runs.ASYNC_ROW_BAR_BY_TARGET` — meters load 500, other asset sheets 200, accounts 100) is handed to a job; with `JOBS_EAGER=true` that "job" runs **inside the same request**, so the 60 s gunicorn timeout still applies and a 1,000-meter file (~20 s measured) or an accounts file over ~600 rows is killed mid-load. **Uploads above a bar need `JOBS_EAGER=false` AND a running Celery worker.** ⚠ **AND THE SAME FOR POSTING METER READS (`DEF-MET-8106`/`DEF-MET-8108`, 2026-09-30).** A read batch of more than `services.READ_POST_ASYNC_ROW_BAR` staged rows (200) is posted by a job, and every post queues the monthly-usage rebuild as a second job; with `JOBS_EAGER=true` both run **inside the request that clicked Post**, which is exactly how 480 readings reached the 60 s timeout (readings saved, clerk shown *Internal Server Error*, usage rebuilt for 267 of 480 accounts). **Posting reads at cycle size needs `JOBS_EAGER=false` AND a running Celery worker** — with no worker the post above the bar is refused by name (`metering.import.no_worker`) rather than queued for ever, and a rebuild that was queued and never ran is a `queued` job record naming its accounts, recoverable with `manage.py backfill_monthly_usage`. ⚠ **Changing this value in `.env.example` or in this runbook changes NOTHING on a server that already has its `.env` (CLAUDE.md law 4)** — set it in the running task definition / host `.env` and restart the web and worker processes |
| ~~`JOB_ARTIFACTS_DIR`~~ | ⚠ **REMOVED 2026-10-02** — read by nothing; exports go to `DOCUMENT_STORAGE_BUCKET` under `t/<web name>/export/` | — | — | **Delete it from an existing `.env`/task definition**; it is ignored. `DOCUMENT_STORAGE_BUCKET`/`_REGION` are what exports need (`DEF-MET-4954`) |

### 6.2 Backend — variables production needs that the code does NOT read yet

⚠ **r2: `DJANGO_ALLOWED_HOSTS` has LEFT this table** — `production.py` reads it now.
It is in §6.1.

| Variable | Status | What must happen |
|---|---|---|
| `REDIS_URL` | Declared in the root `.env.example`; **read by no backend module** (only `docker-compose.yml` passes it) | Set it anyway for parity/legibility, but `CELERY_BROKER_URL` is the one that matters |
| `SECURE_PROXY_SSL_HEADER` / the `SECURE_*` family | Not settings the app exposes as env vars — they are **absent from `production.py` entirely** (§10.9) | Eng ask. Relevant here because `django.middleware.security.SecurityMiddleware` **is** installed, so the moment those settings appear they take effect; and behind an ALB, `SECURE_SSL_REDIRECT` without `SECURE_PROXY_SSL_HEADER` is an infinite redirect loop |
| ~~Object-storage bucket / prefix / region~~ | ⚠ **MOVED — read since `CR-049`** (`DOCUMENT_STORAGE_BUCKET`, `_REGION`, `_SSE`; see the document-store rows) and needed by EXPORTS since 2026-10-02 (`DEF-GOV-9149`) | Set them in §6.1 |
| Error-sink DSN (Sentry or equivalent) | No consumer in code | Product choice is yours (§11); wiring is Eng's |
| Payment webhook signing keys | R4/W7, not now | 🔒 vault-only, never logged, rotation documented when W7 lands |
| `SEED_DEMO_OWNER_PASSWORD` | Read via `os.environ` by `seed_demo` | Demo/staging only. Irrelevant here — `seed_demo` refuses under production settings (§4 step 13) |
| `STRIPE_API_KEY`, `PLAID_*`, `QBO_*`, `TWILIO_*` | Dev sandbox only | **Leave unset.** In production these are **per-tenant data** held by the integrations module, not platform env vars (TD-8/TD-9) |

### 6.3 Frontend — build-time only ⚠ *(r2 — the one variable r1 required is DELETED)*

**There are no frontend build variables. None. The bundle is environment-independent.**

r1 required `VITE_TENANT_HOST_SUFFIX=smartbillhub.bynry.com` and called it
"never ship a build without it". **That variable no longer exists**, along with
`07-frontend/.env.example` itself. It was deleted with the mechanism it configured: it
named the *hostname suffix* a tenant lived at, so that the signup success screen could
hand the new owner across to `brazosbend.smartbillhub.bynry.com`. Under path tenancy a
tenant's address is `/{tenant}` on the origin the browser is already on, composed from
`window.location`, and the cross-host handoff is gone entirely (§0.0 item 5).
Verified in `07-frontend/src/vite-env.d.ts` ("THERE ARE NONE RIGHT NOW"),
`07-frontend/README.md` §Deployment configuration, and the absence of
`07-frontend/.env.example`.

| Variable | Value | Notes |
|---|---|---|
| ~~`VITE_TENANT_HOST_SUFFIX`~~ | — | **DELETED 2026-08-10** with the host mechanism. Do not reintroduce it, and do not pass it as a build arg — Vite would inline a value nothing reads. |
| `VITE_API_URL` | do not set | Still declared in the **root** `.env.example` (a local-dev file, not deployed) and still read by **no code**: `07-frontend/src/api/client.ts` builds every URL from `API_PREFIX = "/api"` plus the tenant taken from `window.location.pathname`, against a same-origin empty base. ⚠ The root `.env.example` comment describing it is stale on both counts (it says "same-origin `/api` so one bundle serves every tenant **subdomain**") — flagged; that file is outside `09-infra/`. |

Consequence worth stating for the deploy pipeline: **one bundle is valid in every
environment.** `npm run build` needs no environment injection, the same `dist/` can be
promoted from staging to prod unchanged, and a build cannot be "wrong for this
environment" any more.

---

## 7. Tenant-PATH mechanics ⚠ *(r2 — this whole section is rewritten)*

### 7.1 The chain

```
https://smartbillhub.bynry.com/api/brazosbend/settings/company
   │  Route53   smartbillhub.bynry.com  A/ALIAS → edge    (ONE record, all tenants, forever)
   ▼
  edge  :443, cert = { smartbillhub.bynry.com }            (ONE name — no wildcard)
   │   splits on PATH:  /api/*  → Django target group
   │                    *       → the SPA (index.html fallback)
   │   Host is forwarded, but tenancy no longer depends on it
   ▼
 ECS Fargate → gunicorn → Django
   │   ALLOWED_HOSTS validates the Host = smartbillhub.bynry.com   (security boundary,
   │                                       no longer the tenant key)
   │   TenantContextMiddleware  (core/tenancy.py, BE-01):
   │      tenant_slug_of(request.path_info)                  ← the RAW path
   │        "/api/brazosbend/settings/company" → "brazosbend"
   │        (first segment after "/api/", lower-cased; None for the reserved set)
   │      resolver: slug → tenant_id      (apps.tenancy.selectors)
   │      SELECT set_config('app.tenant_id', <uuid>, false)
   ▼
 PostgreSQL — RLS FORCE on 53 tables does the rest.
   Cleared in a `finally` at request end: the GUC never outlives its request.
```

**`/api/brazosbend/…` → tenant `brazosbend`.** The first path segment after `/api/`,
nothing else. Not a header, not a query param, not a body field — `X-Tenant-ID` does not
exist and may never be introduced (TD-4 / BR-TEN-003). The route in
`config/urls.py` is deliberately **non-capturing**
(`re_path(r"^api/[-a-zA-Z0-9_]+/", …)`) so that no view can receive a `tenant=` kwarg:
the tenant is resolved once, by the middleware, from the raw path.

**Reserved first segments — a tenant slug can never be one of these:**

```
api  signup  signin  pricing  static  assets  public  jobs  exports  health  tenants
```

They are held in **two** places that a test keeps in step (`test_be01_tc16`):
`core.tenancy.NON_TENANT_SEGMENTS` resolves `public · tenants · jobs · exports · health`
to *no tenant* before the resolver is consulted, and
`apps.tenancy.selectors.RESERVED_SUBDOMAINS` refuses to *mint* a tenant with any of the
names above (plus the DNS-era carry-overs `www app admin mail billing support status
help bynry smartbillhub`). A tenant called `jobs` would be unreachable at its own API;
one called `signin` would shadow a client route. **Nothing at the edge needs to know
this list** — but if you ever add an edge rule on a root path, check it against this
list first, because a new root path is a new reserved name and only the code can
enforce it.

An **unknown** slug is not an error at the middleware: the request proceeds with **no
tenant context**, RLS denies every tenant table (deny-by-default, HR-1), and
`require_tenant()` renders a `404` that is byte-identical to every other `404`. New
tenants work the instant they are provisioned, with **no DNS change, no edge config, no
certificate change** — and now not even a wildcard to depend on.

### 7.2 ⚠ RESOLVED — the API is under `/api/`, and the SPA shares this origin

r1 recorded a head-on collision: the API was mounted at the **root**, so
`/audit-log` and `/settings/*` owed HTML to a browser navigation and JSON to a fetch,
and no path-based split could express that. **That is fixed.** `06-backend/config/urls.py`
now mounts everything under `/api/`, and `07-frontend/src/api/client.ts` prefixes every
call with `API_PREFIX = "/api"` plus the tenant it reads from `window.location.pathname`.

The URL space, in full:

| Path | Served by | Notes |
|---|---|---|
| `/api/{tenant}/…` | Django | every tenant-scoped endpoint; the tenant is the segment |
| `/api/public/…` | Django | pricing catalog, slug availability — no tenant |
| `/api/tenants` | Django | `POST` = provisioning (S114) — no tenant, `AllowAny` |
| `/api/jobs/{id}` · `/api/exports` · `/api/exports/{id}/file` | Django | platform resources; they serve tenant-scoped records but carry **no** tenant segment, so they take their scope from the **session row** (`core.tenancy.adopt_session_tenant`, BR-IDN-006) |
| `/` · `/pricing` · `/signup` · `/signin-help` | SPA | public screens |
| `/{tenant}/signin` | SPA | per-tenant sign-in → `POST /api/{tenant}/auth/session` |
| `/{tenant}/…` | SPA | every authenticated screen |
| `/assets/*` · `/index.html` | SPA | the built bundle's own files |

**The ALB/edge rule that expresses this is one line: `/api/*` → the Django target
group, everything else → the SPA** (§4 step 8 for the listener, §2.4 for how the SPA
side is served and the index.html fallback it needs).

**Two things the edge must never do:**
- **Never rewrite the path.** The first segment after `/api/` is the tenant. A rewrite
  rule is a tenant rewrite.
- **Never cache an `/api/*` response.** One origin, one cookie jar, many tenants — a
  cached tenant-scoped response served to the next caller is a cross-tenant leak.

**Rejected workaround, kept for the record:** r1 rejected a Lambda@Edge function routing
on `Sec-Fetch-Dest`. It is no longer needed and it stays rejected — a load-bearing
routing rule in a place no test covers and no reviewer reads.

### 7.3 The `ALLOWED_HOSTS` value ⚠ *(r2 — the wildcard form is deleted)*

```
DJANGO_ALLOWED_HOSTS=smartbillhub.bynry.com
```

**One host. No leading dot.** r1 required `.smartbillhub.bynry.com` — Django's
leading-dot subdomain-wildcard form, which matches the domain *and every subdomain of
it*. That form existed only because every tenant was a subdomain. Under path tenancy
there is exactly one hostname, so the wildcard is not merely unnecessary — dropping it
is a **real narrowing**: `.smartbillhub.bynry.com` would accept any label anyone could
point at the load balancer, and `Host` is what Django trusts for absolute URLs and (once
`CSRF_TRUSTED_ORIGINS` exists) origin checks. The code says the same thing in
`config/settings/production.py:11-22`.

Do **not** use `*`. Do not add a bare `bynry.com`. Do not add the ALB DNS name or the
CloudFront domain (see §7.4 for the health-check problem — solve it there, not by
widening this). If you front the ALB with CloudFront, forward the viewer `Host` (§2.4)
rather than adding origin hostnames here.

Note the change of consequence: under r1 a hop that rewrote `Host` would have **silently
collapsed every tenant into "no tenant"** and shown empty screens. Now it produces a
loud `400 DisallowedHost`. Better failure mode, same fix — don't rewrite `Host`.

### 7.4 Health checks and `DisallowedHost`

Unchanged by the tenancy move, and still real. ALB health checks send
`Host: <target-ip>:8000` and **cannot be configured with a custom Host header**. Django
will reject that with `400 DisallowedHost`, the target group will never go healthy, and
the ALB will report a perfectly working app as down.

Standard ECS fix — in the image's entrypoint, append the task's own IP before starting
gunicorn:

```sh
#!/bin/sh
set -e
if [ -n "$ECS_CONTAINER_METADATA_URI_V4" ]; then
  TASK_IP=$(wget -qO- "$ECS_CONTAINER_METADATA_URI_V4/task" \
    | sed -n 's/.*"IPv4Addresses":\["\([0-9.]*\)".*/\1/p')
  [ -n "$TASK_IP" ] && export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS},${TASK_IP}"
fi
exec "$@"
```

⚠ **r2 makes this strictly safer.** Under r1 the appended IP was also a *tenant* input
(`subdomain_of("10.20.3.41")` returned `"10"`). Now the tenant comes from the path, so
the health-check request to `/api/public/pricing-plans` resolves to **no tenant** by
the reserved-segment rule, deterministically. Adding the task IP widens `ALLOWED_HOSTS`
and nothing else.

The cleaner end state is a dedicated health route that skips host validation — that is
an Eng ask (§10.8), not something to bodge at the edge. The `health` segment is already
reserved for it on both lists.

### 7.5 ⚠ One origin means the browser no longer isolates tenants — read this

Under subdomain tenancy the browser gave tenant isolation away for free: one cookie jar
per host, so a Brazos Bend cookie could not physically be sent to Silver Creek. **One
origin removes that.** Two rules replace it, both in the application, both tested:

1. a session row is **bound to its tenant** (`identity.sessions.tenant_id`);
2. a session presented on **another tenant's path is refused with `404`** — never `403`
   (that would confirm the other tenant exists), never a silent switch to the session's
   own tenant. `apps/identity/auth.py::IdentitySessionAuthentication` raises it; BE-02
   renders it with a body byte-identical to any other `404`.

**What this means for you as the operator**, concretely:
- The `404`s in §4 step 14 checks 7–8 and in §9's error-rate dashboards are **the
  control working**. Do not tune them away, do not add an edge rule that "helpfully"
  redirects a foreign-tenant request to the session's own tenant, and do not let anyone
  file them as a bug.
- **Never put a caching layer in front of `/api/*`** (§2.4, §7.2). Under subdomains a
  cache key that ignored `Host` was already wrong; under one origin a cache key that
  ignores the path's tenant segment *or the session cookie* is a cross-tenant leak.
- One browser now holds **one tenant session at a time** — the cookie name is fixed, so
  signing into tenant B replaces tenant A's cookie. A staffer who works two utilities
  signs in and out. Expect that support question; it is by design.

---

## 8. Post-deploy verification — prove the guarantees, do not assume them

These are the **same four probes** the local isolation suite runs
(`06-backend/tests/isolation_helpers.py`, `tests/test_tenant_isolation.py`) and the same
four that were run against a live PostgreSQL 16 cluster on 2026-08-10. Run them against
**production, after every migration, and after every restore**. A restore that silently
loses policies is a catastrophic quiet failure; this section is what catches it.

Run from a one-off ECS task in `sg-web` (the DB is not publicly reachable — keep it
that way).

### 8.0 The canary — is this proof real at all?

Everything below is worthless if the connected role bypasses RLS. **PostgreSQL exempts
superusers and `BYPASSRLS` roles unconditionally, `FORCE` or not.**

```sql
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
-- REQUIRED: rolsuper = f  AND  rolbypassrls = f
```

On RDS the master user satisfies this by default. **If either column is `t`, stop** —
every probe below would pass vacuously, and a green result would be a lie. (This is
exactly why the test suite runs its RLS half under a dedicated `sbh_rls_probe` role.)

⚠ **DEF-2717 (2026-08-31) — THIS CHECK IS CORRECT AND IT HAD NEVER BEEN RUN AND RECORDED.**
A benchmark lane made its database role `SUPERUSER` to create a database — one command, for an
unrelated reason — and every bill-run performance figure published that day was measured with the
tenant predicate never evaluated. It surfaced only because a second tenant reported **73 accounts**
inside its own tenant context when it had none; the count was the other tenant's. Measured on
PostgreSQL 16.13, one table, one policy, one `app.tenant_id`, `relrowsecurity = t` and
`relforcerowsecurity = t` throughout: `NOSUPERUSER NOBYPASSRLS` read **2 rows**, `SUPERUSER` read
**3**, `BYPASSRLS` read **3** — the third being the other tenant's.

**TWO CONSEQUENCES FOR WHOEVER OPERATES THIS.**

**1 · The application now asks this question itself, on every boot, and REFUSES TO START in
production when the answer is wrong** (`06-backend/core/rls_guard.py`; `G56` keeps it wired). You
should never see a running task on a bypassing role again. If a deploy stops with
`REFUSING TO START: row-level security is not enforced on this connection`, that is this check —
it names the role and prints the `ALTER ROLE` that fixes it. Do not reach for
`SBH_ALLOW_RLS_BYPASSING_ROLE=1`; it exists so an incident can be unblocked deliberately, and it
leaves tenant isolation off.

**2 · RECORD THE ANSWER, PER ENVIRONMENT — that is `DEF-2760`, and it is the half no code can
close.** The repository has never held the `rolsuper`/`rolbypassrls` of any deployed role. The
only trace of a real one anywhere is the username in a quoted error message from 2026-08-10, and
nobody wrote down what it could do. **A runbook step that is never recorded is indistinguishable
from a step that was never run.** Fill this in and keep it filled in — after every restore, and
after any change of credentials:

| Environment | Database role (`current_user`) | `rolsuper` | `rolbypassrls` | Checked on | By |
|---|---|---|---|---|---|
| _(sandbox / demo)_ | | | | | |
| _(production)_ | | | | | |

A blank row means UNKNOWN, and unknown is not the same as safe.

**ONE COMMAND PRODUCES THE ROW** (added 2026-09-01, `DEF-2760`). The friction was
the gap: find the snippet, run it, read three values, turn them into a markdown
row, remember which environment you were on. This does all five, from wherever
the app runs:

```bash
DATABASE_URL=… python3 10-scripts/rls_role_record.py --env production --by "A. Operator"
# → | production | `sbh_app` | f | f | 2026-09-01 | A. Operator |
```

It exits 1 and prints the `ALTER ROLE` when the role bypasses RLS — and tells you
to record the row **anyway**, because a bad answer written down is worth far more
than a blank one, and the blank is what `DEF-2760` is about. It deliberately does
NOT edit this file: a person runs it against an environment only they can reach,
and a person signs the row with their own name. A script that filled the table in
would be recording that a check was run by nobody.

⚠ **THIS TABLE IS STILL EMPTY AS OF 2026-09-01, AND `DEF-2760` STAYS OPEN UNTIL
IT IS NOT.** The code half is closed — `core/rls_guard.py` refuses to boot in
production on a bypassing role and `G56` keeps it wired — but no repository
change can measure a role on a database it cannot reach. Two rows, from whoever
holds the credentials, close it.

### 8.1 Coverage — every tenant table is actually protected

```sql
-- (a) how many tables carry ENABLE + FORCE
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
  AND c.relrowsecurity AND c.relforcerowsecurity;
-- EXPECT: 53  (the verified W0+W1 set; it only ever grows)

-- (b) the complement: any tenant-scoped table with NO row-level security
SELECT c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
WHERE n.nspname='public' AND c.relkind='r' AND NOT a.attisdropped
  AND NOT c.relrowsecurity AND c.relispartition IS FALSE
ORDER BY c.relname;
-- EXPECT exactly this RLS-exempt platform set (B2 §3), and NOTHING else:
--   tenants, services, subscription_plans, roles, permissions,
--   role_permissions, sessions
-- ANY other name is a cross-tenant read waiting to happen. S1 defect.
```

### 8.2 Probe 1 — no tenant context ⇒ the query ERRORS (deny-by-default)

```sql
SELECT set_config('app.tenant_id', '', false);
SELECT count(*) FROM uoms;
-- EXPECT: ERROR:  invalid input syntax for type uuid: ""
-- The empty GUC fails the ::uuid cast inside the policy, so NO row is a
-- candidate. Absence of context is never "see everything" (HR-1).
-- A row count here — even 0 — means the policy is not being applied. STOP.
```

### 8.3 Probe 2 — tenant A sees only tenant A's rows

Take two real tenant UUIDs (`SELECT id, subdomain FROM tenants;` — the column is still
named `subdomain`; since 2026-08-10 its value is the **path slug**, and the decision-log
row keeps the column name deliberately rather than churn the schema).

```sql
SELECT set_config('app.tenant_id', '<TENANT_A_UUID>', false);

SELECT DISTINCT tenant_id FROM uoms;
-- EXPECT: exactly one row, = TENANT_A_UUID.  Any second value is a LEAK.

SELECT count(*) FROM uoms WHERE tenant_id = '<TENANT_B_UUID>';
-- EXPECT: 0

-- id-guessing, the attack that survives a missing application filter:
SELECT count(*) FROM uoms WHERE id = '<A_ROW_ID_OWNED_BY_TENANT_B>';
-- EXPECT: 0   (the row exists; it is simply not a candidate under A's context)

-- and the same shape on a second table, so this is not one table's luck:
SELECT DISTINCT tenant_id FROM rate_plans;   -- EXPECT: TENANT_A_UUID only
```

### 8.4 Probe 3 — `UPDATE`/`DELETE` on `audit_log` are REFUSED

```sql
SELECT set_config('app.tenant_id', '<TENANT_A_UUID>', false);

UPDATE audit_log SET action = 'tampered' WHERE tenant_id = '<TENANT_A_UUID>';
-- EXPECT: ERROR:  audit_log is append-only; corrections are new rows (BR-AUD-002)

DELETE FROM audit_log WHERE tenant_id = '<TENANT_A_UUID>';
-- EXPECT: the identical error
```

The trigger sits on the partitioned parent **and on every partition**. If it fires, the
7-year compliance record cannot be rewritten by anyone reaching the database through the
application's role — which is the claim SOC 2 CC7 / doc 01 §12 row 7 rests on.

There is exactly **one** carve-out, and it is not yours: the day-91 closed-tenant purge
(BR-TEN-044, PO ruling 2026-08-10) is an operator procedure run by the table owner, in a
single transaction, only for a tenant closed ≥90 days, recorded platform-side. It has no
API, UI, service or tenant-role path. Do not run it ad hoc.

### 8.5 Probe 4 — writing into another tenant is REFUSED

```sql
SELECT set_config('app.tenant_id', '<TENANT_A_UUID>', false);

-- direct INSERT stamped for tenant B:
INSERT INTO uoms (id, tenant_id, code, name, is_system, active, created_at, updated_at)
VALUES (gen_random_uuid(), '<TENANT_B_UUID>', 'XX', 'cross-tenant probe',
        false, true, now(), now());
-- EXPECT: ERROR:  new row violates row-level security policy for table "uoms"

-- the table-agnostic form: re-stamp one of A's own visible rows as B's.
-- USING lets the UPDATE find the row; WITH CHECK rejects the result.
UPDATE uoms SET tenant_id = '<TENANT_B_UUID>' WHERE tenant_id = '<TENANT_A_UUID>';
-- EXPECT: ERROR:  new row violates row-level security policy for table "uoms"
```

### 8.6 Probe 5 — the GUC does not outlive its request

```sql
SELECT set_config('app.tenant_id', '<TENANT_A_UUID>', false);
SELECT current_setting('app.tenant_id', true);   -- → the UUID
SELECT set_config('app.tenant_id', '', false);
SELECT current_setting('app.tenant_id', true);   -- → '' (empty)
SELECT count(*) FROM uoms;                       -- → ERROR again (8.2)
```

A pooled connection that kept the last request's `app.tenant_id` would hand the next
caller another tenant's rows. This is also **the** reason a transaction-mode pooler is
forbidden (§2.2 / doc 01 §1).

### 8.7 Record the result

Write the date, the migration revision, the row counts from 8.1, and PASS/FAIL per probe
into your ops log — and re-run the whole section after every restore test (§9.1). It is
your standing evidence for doc 01 §12 row 4.

---

## 9. Day-one operational requirements

Not phase-two. PO ruling 1 puts real customers on this environment.

### 9.1 Backups and a restore test you have actually performed

| Item | Requirement | Source |
|---|---|---|
| Automated backups | RDS automated, **35-day** retention, PITR on | B6 (RPO **1h** / RTO **4h** — law floors) |
| Cross-region copy | Automated snapshot copy to the second **US** region, KMS-encrypted | B6 residency; doc 01 §6.2 says on from day one |
| Manual snapshot | Before **every** release (doc 01 §11 step 0) | belt over the PITR braces |
| Backup window | Outside US business hours, not overlapping the maintenance window | §11 — your call |
| **Restore test** | **Quarterly, automated**, first one performed **before the first real customer**, not after | SC-5 CONFIRMED |
| Document store | S3 versioning. ~~Object Lock (7yr, compliance mode) on write-once classes~~ — **no object lock and no default retention rule for now (`CR-160-BRC10`, PO 2026-10-02)**; the database row stays write-once | NFR-35 (lock half suspended) |

**A restore test is not `pg_isready`.** Restore the latest full + WAL to a point in
time into an isolated instance, then prove the data:
1. **Re-run §8 in full** — a restore that lost the RLS policies is a silent
   catastrophe, and this is the only thing that detects it;
2. run the golden money suite (`make golden`) against the restored data — proves
   financial figures survived;
3. run a trial-balance tie-out — drift must be **0** (NFR-17);
4. **record the wall-clock restore duration** against the 4h RTO and file it.

⚠ Restored environments must come up with **outbound sending disabled** so a restore
never re-emails customers. No dispatcher exists yet, so today this is free — write it
into the restore runbook now, before it stops being free (doc 01 §6.5 item 3).

### 9.2 Alarms that matter

The four platform metrics are **decided** (B12 §7); wire them first, even where the
producing code has not landed — a metric that appears later into a dashboard nobody
built is a metric nobody sees.

| Alarm | Condition | Action | Why |
|---|---|---|---|
| **Subledger tie-out drift** | **any value ≠ 0** | **PAGE** | The double-entry ledger must tie out at all times. Drift is a release blocker by law (NFR-17). The single most important alarm in the platform. *(No producer yet — ledger is W-later. Create the alarm and the dashboard tile now.)* |
| **Queue depth + oldest-message age** | oldest > 15 min (relaxed during announced bill-run windows) | page | Generation and sending are decoupled (NFR-1); a stuck dispatcher silently stops all customer bills. Also the autoscaling signal at P2 |
| **Provider error rates** | sustained elevation → warn; hard-down → page | warn/page | Seams are expected to fail and the queue absorbs it — but only if someone notices |
| **Bill-run duration** | full cycle > 5 min | warn | The one latency SLO the PO tracks (B6) |

Plus the infrastructure baseline, with the platform-specific twists that matter here:

| Alarm | Threshold | Note |
|---|---|---|
| **DB free storage** | < 20% | Financial tables are **never pruned** (NFR-25) — this curve only rises. Do not treat a storage alarm as noise |
| **DB CPU** | > 50% sustained | Also doc 01 §7's phase-move trigger |
| Backup failure | any missed daily full | **page** |
| RDS Multi-AZ failover | any event | page |
| **Partition-job health** | next month's partitions missing by mid-month | See §9.4 — inserts **hard-fail** without them |
| ALB 5xx rate | > 1% over 5 min | |
| ALB target health | any unhealthy target | |
| **Certificate expiry** | < 30 days | ACM auto-renews **only while the validation record still resolves** — the alarm catches a deleted CNAME. ⚠ r2: there is now **one** name and **one** validation record to watch, not two. If r1's wildcard certificate still exists, delete it rather than let this alarm watch a certificate no listener uses |
| p95 API latency | > 500 ms sustained | doc 01 §7 phase trigger |
| ECS service running < desired | > 5 min | |
| Beat liveness | when beat exists | Singleton: if it dies, retention and dispatch schedules stop silently |

Route everything to the SNS topic from P10. **An alarm with no subscriber is not
monitoring.**

### 9.3 Logs

- **Structured JSON**, carrying `tenant`, `trace_id` and the `US-ID` of the code path
  (B12 §7). Every API error envelope already carries `trace_id`, so support can go from
  a screenshot to the exact log line.
- **Retention:** security-relevant events **≥ 13 months**; general app/access logs
  **30–90 days**; ALB access logs to S3 with a lifecycle rule. Exact values are yours
  (§11).
- **Ops logs are NOT the audit system.** The 7-year `audit_log` lives in PostgreSQL
  (NFR-28) and is the compliance record. Do not let anyone treat log retention as audit
  retention, or the reverse.
- **US-region sinks only** (B6).
- **Never ship PII-bearing payloads to log sinks.** The app masks by design
  (BR-CUS-045) — treat unmasked PII in a log as a bug to raise, not a filter to add.

### 9.4 ⚠ Scheduled partition maintenance — required, not optional

`audit_log` is monthly-partitioned. The migration bootstraps **the current month + 3
ahead**. Steady-state create-ahead is `manage.py maintain_partitions`, whose celery-beat
wiring **has not landed** (TD-17). So:

**≈3 months after deploy, every `audit_log` INSERT fails** with *"no partition of
relation audit_log found for row"* — and because every money action writes an audit row
(CLAUDE.md rule 7), that failure takes the write paths with it.

Until beat exists, schedule it yourself:

**EventBridge Scheduler → ECS RunTask, monthly (suggest the 1st at 02:00 UTC):**
```
command: ["python","manage.py","maintain_partitions"]
```
Alarm on non-zero exit **and** on the absence of a success in any 35-day window. Verify
after the first run:
```sql
SELECT relname FROM pg_class
WHERE relispartition AND relname LIKE 'audit_log_%' ORDER BY relname;
-- EXPECT: current month + 3 ahead, always.
```

### 9.5 Incident response

Incidents carry a **72h internal assessment target** with state-law-driven notification
(SC-6). Your DR runbook plugs into that process. Make sure the on-call human knows the
target exists before they need it.

---

## 10. What is NOT ready — do not promise any of this

⚠ **Re-verified item by item against the repo on 2026-08-10 for r2**, because several of
r1's blockers were closed in the intervening hours and a stale blocker in a handover
document is as damaging as a missing one. Each row below says what was checked.

| r1 item | r2 status |
|---|---|
| 10.1 WSGI entrypoint + `ALLOWED_HOSTS` | **CLOSED**, with one named residue (gunicorn) |
| 10.2 SPA cannot share the origin | **CLOSED** — §7.2 is now the routing rule |
| 10.3 empty `subscription_plans` | **STILL OPEN — the one true deploy blocker** |
| 10.4 Celery eager / idle broker | STILL OPEN |
| 10.5 manual partition maintenance | STILL OPEN |
| 10.6 artifacts on local disk | **CLOSED 2026-10-02** — export files are in S3 (`t/<web name>/export/`), found through a database row; the `artifacts:` volume, the EFS plan and `JOB_ARTIFACTS_DIR` are gone (`DEF-MET-4954`) |
| 10.7 no S3 file service | **CLOSED — it was stale** (`DEF-GOV-9149`): the document store has written to S3 since `CR-049`, and exports since 2026-10-02 |
| 10.8 no health endpoint | **CLOSED 2026-09-28** (`CR-144-BRC07`) — `/api/health`, answered by middleware placed first |
| 10.9 app security settings | **MOSTLY CLOSED 2026-09-28** (`CR-144-BRC07`) — `Secure` on all three sign-in cookies, `SECURE_PROXY_SSL_HEADER`, `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT` and `CSRF_TRUSTED_ORIGINS` all present. MFA and the `sbh-pii` CMK are untouched and STILL OPEN |
| 10.10 thin demo seed | **CLOSED as to content**; the production-settings refusal stands |
| 10.11 no autoscaling | STILL OPEN (correctly) |
| 10.12 no deploy pipeline | STILL OPEN |
| 10.13 closed-tenant offboarding | STILL OPEN |
| **10.14, 10.15** | **NEW in r2** |

### 10.1 ✅ CLOSED (mostly) — WSGI/ASGI exist and `ALLOWED_HOSTS` is wired
Checked `06-backend/config/`: **`wsgi.py` and `asgi.py` both exist**, both
`os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")` so a
container that loses the variable **fails closed** rather than booting dev settings on a
public port. Checked `config/settings/production.py:22`:
`ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])`. Both of r1's blockers
are gone; deploy day is no longer waiting on Eng for these.

⚠ **Residue that is still real:** `06-backend/pyproject.toml` lists
`django · djangorestframework · drf-spectacular · psycopg · celery[redis] ·
django-environ` and **no WSGI/ASGI server**. `pip install -e .` therefore produces an
application with nothing to run it. The image installs `gunicorn` explicitly (§4 step 6);
whether it should instead be a declared dependency is an Eng call (§11 item 18) — but
either way, **do not assume a bare `pip install -e .` gives you a serving container.**

### 10.2 ✅ CLOSED — the SPA and the API share this origin
The collision r1 described is gone: `06-backend/config/urls.py` mounts the whole API
under `api/`, and `07-frontend/src/api/client.ts` prefixes `/api` (+ the tenant from
`window.location.pathname`) on every call. One ALB rule now splits the origin —
`/api/*` → Django, everything else → the SPA (§7.2, §4 step 8). What replaces this item
is not a blocker but a build requirement: **the SPA side must fall back to `index.html`**
for unknown paths, or every deep link and every refresh 404s (§2.4).

### 10.3 ⚠ STILL OPEN — and now the *only* deploy blocker: `subscription_plans` is empty
Re-verified. No migration seeds the table. `apps/tenancy/services.py:238` validates the
requested plan against it and appends `signup.plan_unknown` when absent. The only code
that ever writes a row is `seed_demo._ensure_plans()`, which (a) creates **one** plan
(`growth`) and says in as many words that *"starter/scale have no signed values — not
invented"*, and (b) sits behind the guard at `seed_demo.py:1010` that raises
`CommandError` under production settings. So on a fresh production database
**`GET /api/public/pricing-plans` returns `[]` and every signup fails.** Needs signed SKU
values and a supported bootstrap path from PO + Eng (P12). **No customer — not even the
internal demo tenant — can self-serve onto this environment until it is fixed.**

### 10.4 Celery runs eagerly in-process; the broker is deployed but idle (TD-17)
Re-verified: **no `tasks.py` exists in any app**, and the only `@app.task` in the repo is
inside a docstring showing future usage (`core/jobs.py::tenant_task_class`). No
dispatcher sends to the broker — `dispatch_job` either runs the body in-process
(`JOBS_EAGER=True`) or does nothing. `config/celery.py` declares
`autodiscover_tasks()` and no beat schedule **in `config/`**.

⚠ **THIS SECTION IS SUPERSEDED IN ITS ENTIRETY — AMENDED 2026-09-28 (`DEF-INF-7540`), AND IT IS KEPT RATHER THAN DELETED BECAUSE ITS CONCLUSION IS STILL QUOTED.** Every re-verified claim above stopped being true and nothing re-read it. **`apps/tenancy/tasks.py` holds a real `@app.task`**, so *"no `tasks.py` exists in any app"* and *"the only `@app.task` is inside a docstring"* are both false. And **`no beat schedule at all` was the right answer to the wrong question**: a schedule is installed from an app's `ready()`, never declared in `config/`, so grepping `config/` returns the old answer for ever — exactly the correction `01-deployment-architecture.md` §10.3 already took on **2026-09-23** (`DEF-PAY-6268`). **That correction moved ONE document and the identical sentence lived in TWO.** ⚠ **THE COST OF THE STALE VERSION IS THE WHOLE POINT:** the service table above read *"Do not deploy yet"* on this section's authority, so following this runbook deploys a product in which no scheduled job runs at all. **The live count is `G132`'s, from the code.** The `JOBS_EAGER` half of this section — that a `False` setting with no reachable broker leaves every 202 job `queued` for ever — is UNAFFECTED and still true.
Consequences: with `JOBS_EAGER` left at production's `False`, **every 202 job stays
`queued` forever**; set to `true`, job bodies **execute inside the web request**. Today
the only job kinds are CSV exports, so `true` is the working choice — and it is a
temporary one. Also noted by Eng: `run_job()` loads the job record *before* entering
tenant context, so a real broker worker will have to resolve its tenant before that
load. **No beat, no schedule, no async bill runs. Do not promise background processing.**

### 10.5 Partition maintenance is manual until beat lands
Re-verified: `apps/audit/management/commands/maintain_partitions.py` exists; nothing
schedules it. See §9.4. ⚠ **THE PARENTHESIS HERE READ *"(no beat schedule — see 10.4)"* UNTIL 2026-09-28 AND IS STRUCK (`DEF-INF-7540`)** — beat has eight schedules (`G132`, 2026-09-28; this read *six* until `DEF-INF-7541`) and this command is simply not one of them, which is a different fact with a different fix. **The heading is left as it stands on purpose:** *"manual until beat lands"* is still the right instruction, because beat landing does not schedule this command — somebody has to add the entry. Left unscheduled, audit writes
hard-fail roughly three months in, and every money action writes an audit row.

### 10.6 Export artifacts are on local disk, not object storage — **CLOSED 2026-10-02**
⚠ **THIS SECTION DESCRIBED THE DISK UNTIL 2026-10-02 AND IS REWRITTEN, NOT APPENDED TO.**
The history: export files were written to `JOB_ARTIFACTS_DIR` on whichever container ran
the job, and with `JOBS_EAGER=false` that is a worker, so the web task answered a 404 and
Download saved `file.json` (`DEF-MET-4954`). A shared Docker volume / EFS mount papered
over it from 2026-09-12.

**Now** (PO 2026-10-02, decision log *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*): every export file — list, report and finance exports, the
audit-log export, the bill print set — is stored in `sbh-prod-documents` at
`t/<web name>/export/<yyyy>/<mm>/<file id>.<csv|zip>`, recorded in the `job_artifacts`
table, handed over as a **4-hour signed link** (the 2026-08-30 ruling) and deleted
**once a day per utility** by celery-beat after that utility's `file_retention_days`
(3 by default). Analysis, risks and measurements: `09-infra/04-exports-to-s3.md`.

**The delete permission, and why it is this narrow.** No file in the bucket is locked
(`CR-160-BRC10`), so what the app may delete is the only barrier between an application
bug and a sent bill. The PO: *"make sure that you don't delete any other data"*. Three
locks, and this is the third — the task role's delete statement:

```json
{
  "Sid": "DeleteExportFilesOnly",
  "Effect": "Allow",
  "Action": "s3:DeleteObject",
  "Resource": "arn:aws:s3:::sbh-prod-documents/t/*/export/*"
}
```

Grant `s3:PutObject` / `s3:GetObject` on `t/*` as before; grant **no other delete**. (The
other two locks are in code: the sweep acts only on `job_artifacts` rows, and
`apps/tenancy/export_storage.py` refuses any key not under `t/<that utility>/export/`.)

**The whole task-role policy, written out (`DEF-TEN-9190`, 2026-10-02).** One policy, on
the role of EVERY app task — web, celery, celery-billing (and celery-beat, which runs the
clean-up's fan-out but uploads nothing). Since 2.455.0 the WORKER uploads every export, so
a worker task role without these is an export that fails; since 2.460.1 it fails LOUDLY.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "DocumentsAndExportsReadWrite",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"],
      "Resource": "arn:aws:s3:::sbh-prod-documents/t/*" },
    { "Sid": "DeleteExportFilesOnly",
      "Effect": "Allow",
      "Action": "s3:DeleteObject",
      "Resource": "arn:aws:s3:::sbh-prod-documents/t/*/export/*" },
    { "Sid": "BootChecksAskTheBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketObjectLockConfiguration"],
      "Resource": "arn:aws:s3:::sbh-prod-documents" }
  ]
}
```

- `s3:PutObject` covers the multipart upload a print set uses (create, upload part,
  complete); `s3:AbortMultipartUpload` lets a failed one clean up after itself.
- `s3:GetObject` covers **HeadObject** too — the worker reads the object back before it
  calls an export ready, and the download route checks it is still there before it hands
  out the signed link. Without it every export fails *"File missing from storage after
  upload."*
- The third statement is optional: without `s3:ListBucket` the worker's start-up line says
  *"reachable (the bucket answered 403)"* instead of *"reachable"*, which is still the
  answer that matters (the path is open). Without `GetBucketObjectLockConfiguration` the
  document boot check warns (`smartbillhub.W001`).
- If the bucket uses SSE-KMS rather than the default `AES256`, add `kms:GenerateDataKey`
  and `kms:Decrypt` on the key.

**What a host must do** (law 4 — nothing here reaches a running host by itself): set
`DOCUMENT_STORAGE_BUCKET` / `_REGION` (exports now need them), delete
`JOB_ARTIFACTS_DIR`, unmount and delete the EFS / `artifacts:` volume once nothing
older than its utilities' retention is wanted from it, and run `celery-beat` (the daily
clean-up is a beat entry, `tenancy.export_retention_sweep`, 03:47 UTC).

### 10.7 There is no S3 file service in the code — **STALE, CLOSED (`DEF-GOV-9149`)**
⚠ **THIS SAID *"`boto3` and `django-storages` appear nowhere in `06-backend/`"* AND THAT
THE BUCKET *"will sit empty"*. IT STOPPED BEING TRUE WITH `CR-049` (2026-08-30).**
`apps/tenancy/document_storage.py` writes every bill, notice and upload to S3 through
`boto3`, and since 2026-10-02 `apps/tenancy/export_storage.py` writes every export file
there too (§10.6). Still true and unchanged: the tenant logo is stored as **bytes in a
database column** (`tenants.logo_bytes`). *(This does not affect the `sbh-prod-web`
bucket of §2.5, which CI populates with `aws s3 sync`.)*

### 10.8 No health endpoint — **CLOSED 2026-09-28 (`CR-144-BRC07`)**
⚠ **THIS SECTION SAID "nothing serves a health route" FROM r1 TO 2026-09-28. IT IS NO
LONGER TRUE AND IS KEPT ONLY SO THE CHANGE IS VISIBLE.**

`GET /api/health` and `GET /api/health/` answer `200 {"status":"ok"}`, with **no sign-in,
no database and no Redis**. `HEAD` too; `POST` is refused with `405`.

**It is NOT a route and there is no URL pattern for it.** It is answered by
`core.health.HealthCheckMiddleware`, **first** in `MIDDLEWARE` — ahead of host
validation, so `Host: <task-ip>` does not 400, and ahead of `SecurityMiddleware`, so an
HTTPS redirect does not turn it into a `301`. The §7.4 task-IP `ALLOWED_HOSTS` append is
**withdrawn**: do not do it.

**It is a LIVENESS check and must never become a readiness check.** A probe that queries
the database turns a slow database into a total outage — every task fails, every task is
replaced, and the monitoring manufactures the incident it was meant to report.
`tests/test_health.py` makes every database connection raise and still demands a `200`,
so an edit that adds a query goes red there instead of in production.

The `health` segment stays reserved in `core.tenancy.NON_TENANT_SEGMENTS` and
`apps.tenancy.selectors.RESERVED_SUBDOMAINS`, which is what stops a customer being named
`health` and shadowing the probe.

### 10.9 Security items the app does not do yet ⚠ *(r2: re-verified, and it grew)*
- ⚠ **`Secure` ON THE SESSION COOKIE — DONE 2026-09-28 (`CR-144-BRC07`).** This bullet
  said it was missing; it is set now, at **all three** places a session cookie is issued
  (`apps/identity/api.py`, `apps/tenancy/api.py`, `apps/portal/api.py`), from **one**
  setting — `AUTH_COOKIE_SECURE`, env `SBH_AUTH_COOKIE_SECURE` — which **defaults to
  `true`**. Local HTTP development turns it off for itself. **Neither cookie NAME moved:
  renaming a live session cookie signs every user out at once.**
- ⚠ **THE `SECURE_*` SETTINGS — DONE 2026-09-28 (`CR-144-BRC07`).** `production.py`
  now carries `SECURE_PROXY_SSL_HEADER` (unconditional — the ALB terminates TLS and
  overwrites `X-Forwarded-Proto`, **which is only safe because nothing but the ALB can
  reach port 8000; that security-group rule is part of this setting**),
  `SECURE_SSL_REDIRECT` (env, default **off** — the ALB's own listener already does it
  one hop earlier and cannot loop), the `SECURE_HSTS_*` trio (env, default **0 = not
  sent**) and `CSRF_TRUSTED_ORIGINS` (from the same list as CORS, so the two cannot
  drift). **`CsrfViewMiddleware` is still NOT installed**, so `CSRF_TRUSTED_ORIGINS` is
  still inert — it is set for the day it is, and the cross-site risk it would have
  covered is covered instead by `core/origin_guard.py`.
  ⚠ **HSTS IS THE ONE HEADER YOU CANNOT TAKE BACK.** Ramp it — 300, then 86400, then
  31536000 — and only after one certificate renewal has been observed.
- **App-level MFA is v2** by PO ruling (SC-1) with documented compensating controls.
  Cloud-console MFA for the ops team is expected **now** (P1).
- The `sbh-pii` CMK has **no consumer** — app-layer HIGH-PII encryption is not
  implemented (doc 01 §12 row 3).

### 10.10 ✅ CLOSED as to content — the demo seed now builds a real utility
r1 said the seeder produced W0 only and a walkthrough showed empty screens. Re-verified
against `apps/tenancy/management/commands/seed_demo.py`: it now seeds, through each
module's **own service functions** under tenant context, **5 charge codes · 2 taxes (+2
jurisdictions) · 4 rate schedules · 3 published rate plans · 6 premises · 10 units ·
5 routes · 2 cycles · 10 assets** (8 meter-typed), idempotent on natural keys, and it
prints the walkthrough credentials and the sign-in **path** (`/{tenant}/signin`) at the
end. Meter reads, customers, accounts, bills and payments are still absent and the
seeder says so rather than faking them.

⚠ **What has NOT changed, and is the part that binds you:** `seed_demo.py:1010` still
refuses to run under `config.settings.production`. None of the above reaches this
environment. Combined with 10.3 that is the whole shape of the bootstrap problem: the
one command that can populate an environment is the one command that will not run here.

### 10.11 No autoscaling policy is tuned
Doc 01 §8.2 is explicit that the scaling signal is **queue depth and oldest-message
age, not CPU** — and there is no queue traffic yet to tune against. Deploy fixed task
counts; add autoscaling when there is a real month-end to measure. A CPU-based policy
would be actively wrong.

### 10.12 No deploy pipeline exists
Re-verified: `.github/workflows/` holds `ci-backend · ci-frontend · gates ·
migration-guard · qa · security-scan · trace-lint` and **no build-and-deploy workflow** —
no ECR push, no `s3 sync` of the bundle, no ECS update. Also **still true**:
`ci-frontend.yml` uses `working-directory: frontend` while the directory is
`07-frontend` (`ci-backend.yml` was fixed to `06-backend`; the frontend one was not) —
the same pre-rename path bug as the old Dockerfiles. **Whatever you build must not
bypass the merge-blocking gate stack** (doc 01 §12 row 16).

### 10.13 Open decisions above your pay grade
**Closed-tenant offboarding** (export format + deletion SLA) is still an unresolved
retention row — re-verified: `04-docs/07-compliance/data-retention.md` line 12 reads
*"Closed-tenant data | **OPEN** — offboarding export + deletion SLA needed"*. Needs a
PO/legal ruling **before the first tenant contract** (doc 01 §6.3). Not a DevOps call.
*(Related but separate and now CLOSED: the day-91 audit purge, PO ruling 2026-08-10 —
see §8.4's carve-out.)*

### 10.14 ⚠ NEW — most tenant endpoints do not accept the session cookie
This is a pre-existing, documented, tested gap that r1 did not carry, and it changes what
a deployed environment can be *shown* doing. Only the modules that declare
`authentication_classes = [IdentitySessionAuthentication]` can be reached by a real
cookie client:

| Reachable with the session cookie | 401 for every tenant alike |
|---|---|
| `/api/{t}/auth/session` (public POST) · `/api/{t}/me` · `/api/{t}/me/permissions` · `/api/{t}/users*` · `/api/{t}/roles` · `/api/{t}/settings/security-policy` · `/api/{t}/audit-log*` · `/api/jobs/{id}` · `/api/exports*` | `/api/{t}/settings/company` · `/settings/regional` · `/lookups/*` · `/plans*` · `/rate-schedules*` · `/charges*` · `/taxes*` · `/premises*` · `/units*` · `/routes*` · `/cycles*` · `/assets*` · `/tenants/checklist` |

Counted from the source: `apps/rating/api.py`, `apps/metering/api.py` and
`apps/assets/api.py` contain **zero** `authentication_classes` declarations, and
`apps/tenancy/api.py`'s three are all on the platform paths (`job_status`,
`list_export`, `export_file`). The file's own trailer records the gap, and
`tests/test_path_tenancy_session_binding.py::test_path_tenancy_the_unauthenticated_endpoints_leak_nothing_either`
pins it — asserting the answer is `401` for the caller's own tenant, a foreign tenant and
an unknown tenant **alike**, so **nothing leaks**. It is a functional gap, not a tenancy
one.

**What this means on deploy day:** the SPA loads, a user signs in, and most screens come
back empty-with-an-error. Do not schedule a PO walkthrough of Settings, Plans & Rates,
Premises or Assets against this environment until the gap closes. Do not "fix" it at the
edge — there is nothing an edge can do about an authentication class that was never
declared. §11 item 19.

### 10.15 ⚠ NEW — behind a load balancer, the app sees the load balancer
`apps/identity/auth.py::client_ip()` reads **`REMOTE_ADDR` only**, with a comment that
says so: *"never a header a client could forge — X-Forwarded-For handling is an infra
concern."* Behind an ALB `REMOTE_ADDR` is the load balancer's private IP for **every**
request. Two consequences, both real, neither solvable at the edge alone:
- **BR-IDN-020's per-tenant IP allowlist becomes meaningless** — every request appears
  to come from one ALB address, so an allowlist either admits everyone or locks the
  tenant out entirely. Do not let a customer configure one on this environment until
  Eng handles `X-Forwarded-For`.
- **DRF throttling has no `NUM_PROXIES` setting**, so `BaseThrottle.get_ident()` falls
  back to using the whole `X-Forwarded-For` chain as the identity — which a client can
  prepend to. The public 60/min `PublicOnboardingThrottle` (signup, slug availability,
  pricing) is therefore trivially bypassable, and conversely a real client's identity is
  not what you think it is. **Interim mitigation is the WAF rate-based rule** (§2.4) —
  which is exactly why that rule is not optional. The fix is Eng's: set `NUM_PROXIES`
  (and give `client_ip()` a trusted-proxy-aware source). §11 item 24.

---

## 11. Hand-back list — decide, then report

Record each in `12-governance/02-decision-log.md` (there is a PENDING "Hosting/cloud +
region" row waiting) and tell the Eng-Lead. Doc 01 §14 rows 19–28 are the long form;
this is what is actually blocking or imminent.

### Sizing and capacity
1. **RDS instance class and storage** — start `db.t4g.medium` / 100 GB gp3? Report what
   you provisioned and the first week's CPU/IOPS.
2. **Fargate task sizes and counts** per shape — confirm or adjust §2.1.
3. **ElastiCache node class**, and whether a replica is wanted at P0.
4. **Storage autoscaling ceiling** on RDS.

### Backup and recovery
5. **Backup window** and **maintenance window** (must not overlap; both outside US
   business hours).
6. **Snapshot retention** beyond RDS's 35 days — do long-term snapshots go to
   `sbh-prod-backups` with a lifecycle rule?
7. **Restore-test date and mechanism** — the first one must precede the first real
   customer. Report the measured restore duration against the 4h RTO.

### Alerting and observability
8. **Alert routing**: which SNS topic, which humans, which channel, and what counts as a
   page versus a warn. Name the on-call human.
9. **Error-sink vendor** (Sentry or equivalent) — and note that adding it means a
   subprocessor-register entry and a DPA (doc 01 §12 row 15).
10. **Log retention values**: security events (suggest 13 months), app/access logs
    (30–90 days), ALB access logs in S3.

### Platform and network
11. **Region pair** (primary + US DR copy region). PO ruled the cloud; the region is
    yours.
    - ⚠ **NEW in r2 — the edge shape: A (CloudFront + S3 + ALB) or B (ALB + a static
      target group)?** §2.4. This is now a real decision because the SPA is deployable
      and r1's "no CloudFront, nothing may rewrite `Host`" argument no longer applies.
      Whichever you pick, **report how the index.html fallback is implemented** — and if
      it is CloudFront, confirm in writing that it is a **CloudFront Function on the
      default behaviour**, not distribution-wide custom error responses (which would
      rewrite the API's isolation 404 into a 200).
12. **IaC tool** — Terraform or CDK. Pick one and commit it. A console-built production
    environment is a single-person dependency and is not a handover.
13. **Deploy pipeline**: GitHub Actions with an OIDC-federated role is the expected
    shape (no long-lived keys). Must not bypass the gate stack.
14. **One NAT gateway or two**, and which **VPC endpoints** to add.
15. **Whether demo/staging share this account** or get their own. Given ruling 1
    (customers land on this environment), a **separate** staging account is strongly
    recommended — the restore rehearsals of §9.1 need somewhere that is not production.
16. **TLS depth to the database**: `sslmode=require` now, or `verify-full` with the RDS
    CA bundle in the image?
17. **Connection pooler**: none at P0 is correct. If it ever changes, **session mode
    only**, and raise it with Eng first.

### Asks you must put back to Eng / the PO ⚠ *(r2 — two closed, two added)*
18. **Eng — does a WSGI server belong in `pyproject.toml`?** ✅ r1's WSGI/`ALLOWED_HOSTS`
    blockers are **closed** (§10.1). What remains: gunicorn is not a declared dependency,
    so the image pins it (§4 step 6), and the **`JOBS_EAGER` posture** must still be set
    explicitly on every task definition (§6.1). Deploy day is no longer gated on this.
19. ~~Eng — the API prefix + client base URL~~ ✅ **CLOSED 2026-08-10** — the API is under
    `/api/` and the client prefixes it (§7.2). **Replaced by a bigger ask: wire
    `IdentitySessionAuthentication` on the tenancy / rating / metering / assets
    endpoints** (§10.14). Without it a signed-in browser gets `401` on most screens, and
    the environment cannot be walked through.
20. **PO + Eng — signed `subscription_plans` values and a supported bootstrap path**
    (§10.3), without which nobody can sign up. **This is now the only deploy blocker.**
21. ~~**Eng — `Secure` on the session cookie** and the `SECURE_*` production settings~~
    **DONE 2026-09-28 (`CR-144-BRC07`)**, including `SECURE_PROXY_SSL_HEADER` — which is
    set unconditionally, precisely so nobody can turn on `SECURE_SSL_REDIRECT` without
    it and redirect every request for ever.
22. ~~**Eng — a health endpoint** that does not trip host validation (§10.8).~~
    **DONE 2026-09-28 (`CR-144-BRC07`)** — `/api/health`, answered by middleware placed
    first. DevOps action is now a target-group setting, not an ask: see Step 8.
23. **PO/legal — closed-tenant offboarding export + deletion SLA** (§10.13), before the
    first tenant contract.
24. **DevOps — `TRUSTED_PROXY_COUNT=1` in every task definition** (§10.15). The code
    side is built; this is now a value somebody has to type. ⚠ **ON ECS IT IS 1 FOR A
    DIFFERENT REASON THAN THIS ITEM ORIGINALLY GAVE** — there is no frontend container
    in front of the API any more (the SPA is static on S3 and the browser calls the API
    host directly), so the one proxy is the ALB. Same number, different chain.
    **Unset it and it defaults to 0**, which is wrong-but-safe: allowlists over-restrict
    and throttles over-group. **Set it too high and a client forges its own address** in
    `X-Forwarded-For` — it can then claim any allowlisted address and mint an unlimited
    number of throttle identities.
25. ⚠ **NEW — Eng/Docs: the root `.env.example` still describes the subdomain model.**
    It carries `VITE_API_URL` (read by nothing), an `E2E_BASE_URL` comment describing
    tenant journeys at `http://brazosbend.localhost:5173`, and a line saying tenant
    context comes from "membership + subdomain". Harmless to production — it is never
    deployed — but it is the first file a new engineer opens. Outside `09-infra/`;
    flagged, not edited.

---

## 12. Quick reference

```bash
# ⚠ THE SITE IS 500ing ON EVERY SIGN-IN — run the release step (DEF-INF-7683)
#    Locally / on a compose host:
make release                                        # → docker compose run --rm --no-deps --entrypoint /app/docker-release.sh backend
#    See what is pending FIRST:
docker compose exec backend python manage.py showmigrations --plan | grep '\[ \]'

# Migrate (the RELEASE task — §H6. ⚠ THIS BLOCK USED TO OVERRIDE THE **web**
# TASK's command with `manage.py migrate`, which is the pre-CR-144-BRC07 shape:
# it skips the DEF-622 tenant-GUC check and the OQ-087 reference-data sweep that
# `docker-release.sh` runs on either side of the migrate, so a release done this
# way silently omits half of itself.)
aws ecs run-task --cluster sbh-prod --launch-type FARGATE \
  --task-definition smartbillhub-release-prod \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIV],securityGroups=[$SGWEB]}"
# WAIT for it and CHECK THE EXIT CODE before rolling the service (§H6 step 3).

# Partition maintenance (also the EventBridge monthly target)
  ... --overrides '{"containerOverrides":[{"name":"web","command":["python","manage.py","maintain_partitions"]}]}'

# Roll back the app to the previous task definition revision
aws ecs update-service --cluster sbh-prod --service sbh-prod-web \
  --task-definition sbh-prod-web:<previous-revision>

# The four RLS probes, condensed — run after EVERY migration and EVERY restore
psql "$DATABASE_URL" <<'SQL'
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user; -- f, f
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relrowsecurity AND c.relforcerowsecurity;          -- 53
SELECT set_config('app.tenant_id','',false);
SELECT count(*) FROM uoms;                                                          -- must ERROR
SQL

# Ship a new SPA bundle (edge shape A) — content-hashed assets first, index.html LAST,
# so a browser never sees an index that references files not yet uploaded.
aws s3 sync 07-frontend/dist/assets/ s3://sbh-prod-web/assets/ \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp   07-frontend/dist/index.html s3://sbh-prod-web/index.html \
  --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id <id> --paths '/index.html' '/'
```

**The URL cheat sheet** (r2 — pin this next to the terminal):

```
https://smartbillhub.bynry.com/                        marketing / pricing (SPA)
https://smartbillhub.bynry.com/signup                  signup wizard (SPA)
https://smartbillhub.bynry.com/{tenant}/signin         sign-in (SPA)
https://smartbillhub.bynry.com/{tenant}/…              every app screen (SPA)
https://smartbillhub.bynry.com/api/{tenant}/…          every tenant-scoped endpoint
https://smartbillhub.bynry.com/api/public/…            catalog + slug availability
https://smartbillhub.bynry.com/api/tenants             POST = provisioning
https://smartbillhub.bynry.com/api/jobs/{id}           job poll (scoped by session)
https://smartbillhub.bynry.com/api/exports[/{id}/file] export + download
reserved first segments: api signup signin pricing static assets public jobs exports
                         health tenants  (+ www app admin mail billing support status
                         help bynry smartbillhub)
```

**Release sequence** (doc 01 §11, unchanged and binding): pre-flight snapshot → deploy →
migrate → seed (never prod) → gates → journeys → PO walkthrough → post-release watch
through the first bill-run window.

---

*r1 · 2026-08-10 · authored against the repo state of 2026-08-10 following the PO's four
deployment rulings of the same date.*

*r2 · 2026-08-10 · amended for the PO's **path-tenancy** ruling of the same date
(`smartbillhub.bynry.com/{tenant}/…`, API `…/api/{tenant}/…`), already implemented and
green in the repo. **Deleted:** the wildcard certificate requirement (§2.6), the wildcard
DNS record (§4 step 10), the leading-dot `ALLOWED_HOSTS` form (§7.3), the
`VITE_TENANT_HOST_SUFFIX` build variable (§6.3) and the cross-host signup handoff.
**Rewritten:** the edge (§2.4) and the SPA/API split (§7.2) from "not ready" into the
actual `/api/*` routing rule with its index.html fallback; the tenant mechanics (§7) from
Host-label to path-segment, with the reserved-segment list and the one-origin cookie
consequence (§7.5); the whole smoke test (§4 step 14). **§10 re-verified item by item:**
10.1, 10.2 and 10.10 closed against the code, 10.3–10.9 and 10.11–10.13 confirmed still
real, 10.14 and 10.15 added. No gate machine-checks this directory — the verification
behind r2 is the repo reads cited inline, nothing more.*

*Living document: update at every release boundary alongside
`01-deployment-architecture.md`, and record every decision from §11 in
`12-governance/02-decision-log.md`.*

---

# r4 · 2026-09-28 — ECS Fargate, two hosts, and the deploy that stopped migrating (`CR-144-BRC07`)

**Everything in this section is new.** It does not supersede r3's topology; it fills in
the three things r3 left as asks (§10.8, §10.9, ask 24) and adds the two the move to ECS
creates: **where migrations run** and **what the browser is allowed to call**.

⚠ **NO GATE MACHINE-CHECKS `09-infra/`.** Every figure below was read out of the code on
2026-09-28 and is cited to a file. If you are reading this months later, re-read the
files; a document describing a system is a claim nothing re-checks.

## r4.1 · H5 — the API target group

Already in Step 8, restated here as one block because it is what a DevOps engineer
actually types:

| | |
|---|---|
| Target type | `ip` (Fargate) |
| Protocol / port | **HTTP** : **8000** |
| Health-check path | **`/api/health`** |
| Health-check protocol | HTTP |
| Success codes | **200** |
| Interval | 15s · Timeout 5s · Healthy 2 · Unhealthy 3 |
| ECS service `healthCheckGracePeriodSeconds` | **60–90** |

**Why the grace period is not optional.** Nothing answers on port 8000 until gunicorn
has booted and the RLS-enforcement check has passed. Set the grace below that and ECS
kills every task while it is still starting — for ever. The symptom is a service that
never stabilises with no error in any application log, because the application never got
far enough to write one.

## r4.2 · H6 — migrations are a ONE-OFF TASK, run by the pipeline BEFORE the rollout

⚠ **`docker-entrypoint.sh` NO LONGER MIGRATES, AND MUST NOT AGAIN.** It ran `migrate` in
every web task at start-up, which is correct with one task and three faults with two:

1. **Two tasks migrate at once.** Django takes no advisory lock. The loser fails on an
   object that already exists, exits non-zero, and ECS restarts it into the same race.
2. **A slow migration fails the health check.** Nothing answered on 8000 until gunicorn
   started, so a five-minute migration was five minutes of an unhealthy target — and the
   balancer kills the task **partway through the migration it is waiting for**.
3. **Scaling out ran DDL.** Adding a task at 9am should not change the schema.

**What to build:** a second task definition, `smartbillhub-release-<env>`, from the
**same image**, same subnets, same security group, same task role, same `environment`
and `secrets` blocks — overriding only the command:

```
"entryPoint": ["/app/docker-release.sh"]
```

**Pipeline order, and the order is the point:**

```
1. build + push the image
2. aws ecs run-task  --task-definition smartbillhub-release-<env>   # WAIT for it
3. check the exit code — STOP THE DEPLOY IF IT IS NOT 0
4. aws ecs update-service --force-new-deployment                    # the rollout
```

⚠ **STEP 3 IS THE STEP THAT GETS SKIPPED.** A pipeline that starts the rollout in
parallel with step 2 is the old race with more moving parts, and the symptom — a
column-not-found error from a view — names neither the deploy nor the migration.

### ⚠ IT WAS SKIPPED, ON THE DAY THIS SECTION WAS WRITTEN — `DEF-INF-7683`, 2026-09-28

**Nobody could sign in at `smartbillhub.bynry.com`.** Every
`POST /api/<slug>/auth/session` answered **500** over

```
psycopg.errors.UndefinedColumn: column security_policies.absolute_session_hours does not exist
```

while **`GET /api/health` answered `200 {"status":"ok"}` throughout**, so the
balancer kept every useless task in rotation. The build needed `identity/0006`
(`CR-145-BRC08`'s five session and lockout columns); the database was at `0005`.

**There is no pipeline to skip step 3 — that is the finding.** Every workflow in
`.github/workflows/` is `.disabled`, and `docker-release.sh` has exactly two
callers: `make release`, and step 2 above, which is a human typing a command. The
paragraph above describes a procedure, and a procedure is not a control.

> ## ⏱ IF THE SITE IS 500ing RIGHT NOW, THIS IS THE COMMAND
>
> ```bash
> make release        # → docker compose run --rm --no-deps --entrypoint /app/docker-release.sh backend
> ```
>
> On ECS: `aws ecs run-task --task-definition smartbillhub-release-<env>`, then
> wait for exit 0 and restart the service.
>
> **To see what is pending before you run it:**
>
> ```bash
> python manage.py showmigrations --plan | grep '\[ \]'
> ```
>
> Nothing else is needed and nothing else should be tried. **Do NOT make the web
> container migrate** — the three faults at the top of this section are why it
> stopped, and they have not gone away.

**What changed in the product on 2026-09-28, so this cannot be silent again:
the web task now refuses to boot on a schema it cannot serve.**
`docker-entrypoint.sh` calls `core/schema_guard.py` immediately before
`exec gunicorn`, and it has three outcomes rather than two:

| Verdict | What the task does | Why |
|---|---|---|
| **CURRENT** | boots, prints `0 unapplied migrations` | it can serve |
| **PENDING** | **REFUSES**, exit 1, listing every unapplied migration and the command above | serving is strictly worse than not serving: a booted task 500s every request while reporting healthy. A refusing task fails the rollout instead, and the **previous task definition keeps serving customers** |
| **UNREACHABLE** | warns loudly and **boots** | a process that cannot reach the database fails every request whatever its schema; one that refused would be gone when the database comes back |

⚠ **THE THIRD ROW IS NOT TIDINESS.** `manage.py migrate --check` exits **1** for
*pending* **and** for *cannot connect* — measured four ways on 2026-09-28 — so a
boot check written as `migrate --check || exit 1` would crash-loop the whole
service through a thirty-second RDS failover.

⚠ **THE ESCAPE HATCH, AND WHEN IT IS LEGITIMATE.** A *forward-compatible*
pending migration — one that adds something this build does not read — is
harmless, and nothing can tell it apart from a needed one. Setting
**`SBH_ALLOW_PENDING_MIGRATIONS=1`** in the task definition boots anyway and
prints every assumed migration on every boot. **Remove it in the same change
that runs the release task**; the right answer is almost always to run the
release task, which takes seconds.

**ROLLBACK OF THIS GUARD ITSELF, stated before it ships.** It is one
environment variable and no redeploy: set `SBH_ALLOW_PENDING_MIGRATIONS=1` on
the web task definition and every task boots exactly as it did before
2026-09-28, printing its warning. To remove the guard from the image, delete
the `schema-guard` block in `06-backend/docker-entrypoint.sh` — `G136` then
fails at merge and names it, which is the intended friction. **It adds one
`SELECT` against `django_migrations` per task start and nothing per request**,
so there is no runtime cost to weigh against it.

**What `docker-release.sh` does, in order:** refuses without `DJANGO_SETTINGS_MODULE` ·
checks the `app.tenant_id` session default (DEF-622 — a fresh database **cannot** migrate
without it, and the error names neither the database nor the fix) · `migrate --noinput` ·
the OQ-087 reference-data sweep. The sweep's exit code is printed loudly and does **not**
fail the release: a reference-data gap must not hold a schema change hostage.

**What stayed in `docker-entrypoint.sh`,** because a release task cannot answer any of it
on a web task's behalf: the `DJANGO_SETTINGS_MODULE` refusal, the `ALLOWED_HOSTS` warning,
and the **RLS-enforcement check that refuses to boot**. A task whose role bypasses
row-level security must not serve, whatever some other container was doing an hour ago.

## r4.3 · X4 — the environment variables, per task definition

**Three task definitions per environment — `web`, `worker`, `release` — and these values
go in ALL THREE unless a row says otherwise.**

| Variable | dev | sandbox | production |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` | `config.settings.production` | `config.settings.production` |
| `DJANGO_ALLOWED_HOSTS` | `api-smart360-dev.bynry.com` | `api-smart360-sandbox.bynry.com` | `api-smart360.bynry.com` |
| `CORS_ALLOWED_ORIGINS` | `https://app-dev.bynry.com` | `https://app-sand.bynry.com` | `https://app.bynry.com` |
| `PUBLIC_APP_ORIGIN` (`DEF-CWP-9717` — the customer portal's address and QR code; **and since `CR-188-BRC10` the one-time sign-in link in staff invitation and reset emails** — unset, those emails are not sent and the admin is told why; web task is the one that reads it) | `https://app-dev.bynry.com` | `https://app-sand.bynry.com` | `https://app.bynry.com` |
| `TRUSTED_PROXY_COUNT` | `1` | `1` | `1` |
| `SBH_AUTH_COOKIE_SECURE` | `true` (or omit) | `true` (or omit) | `true` (or omit) |
| `JOBS_EAGER` | `false` | `false` | `false` |
| `CELERY_BROKER_URL` | see r4.4 | see r4.4 | see r4.4 |
| `CACHE_URL` | see r4.4 | see r4.4 | see r4.4 |
| `DATABASE_URL`, `DJANGO_SECRET_KEY`, `SBH_FIELD_ENCRYPTION_KEYS` | vault | vault | vault |

⚠ **`DJANGO_SETTINGS_MODULE=config.settings.production` MUST BE IN ALL THREE, INCLUDING
DEV.** `manage.py` defaults it to `config.settings.local` and `config/wsgi.py` defaults it
to `config.settings.production`, so an environment that forgets it has the **release task
migrating under one settings module and the web task serving under another**. Both
scripts refuse to start without it, which is the check — but only if you let it be the
check rather than "fixing" it with a default.

⚠ ⚠ **`config.settings.local` MUST NEVER BE DEPLOYED, TO ANY ENVIRONMENT, INCLUDING DEV.**
It is `DEBUG=True` with **`ALLOWED_HOSTS=["*"]`**, a committed `insecure-dev` encryption
key that protects nothing, documents written to local disk, and `RLS_ALLOW_BYPASSING_ROLE
= True` — **which means tenant isolation is not enforced by the database at all.** "Dev
is only internal" is not an answer: dev holds real-shaped data and the same code path.

⚠ **`DJANGO_ALLOWED_HOSTS` IS THE API HOST ONLY. DO NOT ADD THE TASK'S PRIVATE IP.** That
was r3's §7.4 workaround for the health check and it is **withdrawn** — the probe answers
ahead of host validation now. The IP changes on every placement anyway.

⚠ **THESE REACH A RUNNING TASK ONLY THROUGH A NEW TASK DEFINITION REVISION.** Editing
`06-backend/.env.example` changes nothing anywhere (hard-won law 4), and an ECS task does
not read a `.env` file at all. Revise the task definition and update the service.

## r4.4 · X5 — ElastiCache for Redis

**No code change. Two existing variables, new values.**

⚠ **CLUSTER MODE MUST BE OFF — AND "ELASTICACHE SERVERLESS" IS CLUSTER MODE.** Serverless
offers no cluster-mode-disabled option; it is Redis Cluster behind a configuration
endpoint. Two things in this stack cannot use it:

* **Database indexes.** Redis Cluster supports database **0 only**. The whole point of
  the two URLs is that the broker is db 0 and the cache is db 1, so a `FLUSHDB` on one
  cannot touch the other. `/1` against a cluster endpoint is refused.
* **Multi-key operations across slots.** Celery's and Django's Redis clients are not
  cluster clients.

**So: a cluster-mode-DISABLED replication group.** One primary, one replica in a second
AZ, automatic failover on. **Both URLs point at the PRIMARY endpoint.**

```
CELERY_BROKER_URL=rediss://<auth>@<primary-endpoint>:6379/0?ssl_cert_reqs=required
CACHE_URL=rediss://<auth>@<primary-endpoint>:6379/1?ssl_cert_reqs=required
```

⚠ **`rediss://` AND `?ssl_cert_reqs=required` TOGETHER.** Without the query parameter the
client connects over TLS and **verifies nothing** — a lock icon over an unverified
connection, which is hard-won law 7's *check that cannot fail*. With encryption-in-transit
enabled and a plain `redis://` URL the connection is refused outright, which at least
fails loudly.

The AUTH token is a **credential**: it belongs in the task definition's `secrets` block
(a Secrets Manager ARN), never in `environment`, and never in this document.

⚠ **THE FAILURE IS LATE, NOT LOUD.** A cluster endpoint connects. `CACHE_URL` then fails
at the first operation, and the visible symptom is that **the portal's rate limits refuse
nothing** (`CR-110-BRC04`: a per-process count turned a ceiling of 100/min into 300/min
across three workers). **Verify by counting**, not by connecting.

## r4.5 · X1/X2 — CORS, and the guard CORS does not give you

The SPA is on `app[-env].bynry.com` and the API on `api-smart360[-env].bynry.com` —
two hosts, on purpose (decision log 2026-09-28 ruling 1: the PO refused CDN path-routing
of `/api/*` and the lock-in that comes with it). So every call the browser makes is
cross-origin.

* **Exactly one origin per environment; never `*`.** Not caution:
  `Access-Control-Allow-Origin: *` and `Access-Control-Allow-Credentials: true` are
  mutually exclusive by specification and the session cookie IS the credential. A
  wildcard would present as *"signed in, and every call is 401"*.
* **`CORS_ALLOWED_ORIGINS` defaults to EMPTY.** A deployment that forgets it grants
  nothing, loudly, in the browser console — rather than everything, quietly.
* ⚠ **AND CORS IS NOT THE DEFENCE.** `app-*.bynry.com` and `api-*.bynry.com` are the same
  **site**, so a `SameSite=Lax` session cookie rides along from **any** `*.bynry.com`
  page; DRF's default parsers accept form posts; and the session authenticator is a
  custom cookie class with no CSRF check. **A cross-origin form POST is SENT** — CORS
  only hides the response, after the write. `core/origin_guard.py` refuses it
  server-side, before any view runs. **A request with NO `Origin` header is let through,
  deliberately** (curl, the partner surface, inbound webhooks), and there is a test
  asserting that so it cannot drift shut.

**Nothing here is a load-balancer rule.** Do not add CORS headers at the edge — two
sources for one header is hard-won law 5, and the ALB cannot see the session anyway.


## r5 · 2.389.0 — session and lockout settings (`CR-145-BRC08`): three things to do around the deploy

**Nothing to add to any task definition or `.env`.** This release declares **no new
environment variable** — `06-backend/.env.example`'s 2.389.0 block says so in its first
line and holds only comments. What it adds is one beat schedule and one data step.

### r5.1 Before the migration — tell the utilities that are about to move

Six sign-in rules become settings each utility chooses, and **every default is today's
value**, with one exception: the 4-hour and 8-hour inactivity timeouts are withdrawn and
a utility on either is moved to **1 hour**. Its staff are then signed out after a much
shorter quiet spell — a clerk who steps away for 90 minutes is signed in when they come
back today and signed out after this release. Decided 2026-09-28 (decision log, *"THE TWO
CR-145 QUESTIONS LEFT OPEN WITH THE PO"*, item 2): **those utilities are told before the
release ships.** No in-product banner exists; this is the step that tells them.

**Who they are is a query, and it must run under each utility's tenant context** —
`security_policies` is `ENABLE`+`FORCE` row-level security, so a plain `psql` `SELECT` as
the table owner with the nil-UUID default answers **zero rows whatever the truth is** (the
exact failure `DEF-IDN-7504` found in the migration itself). Run it as a one-off task with
the web image, like Step 11:

```bash
python manage.py shell -c "
from core import tenancy
from apps.tenancy.selectors import live_tenant_subdomains
from apps.identity.models import SecurityPolicy
for s in live_tenant_subdomains():
    tid = tenancy.tenant_id_for_slug(s)
    with tenancy.tenant_context(tid):
        for p in SecurityPolicy.objects.filter(tenant_id=tid, session_timeout_minutes__in=(240, 480)):
            print(s, p.session_timeout_minutes)
"
```

Each printed line is one utility to tell. No line at all means nobody moves.

### r5.2 During the migration — the count is TWO printed lines, added together

`identity/0007` and `identity/0008` both look for 240 and 480 and move them to 60, one
`audit_log` row per utility. **Each row is moved exactly once, by whichever of the two can
see it:** `0007` reads before setting tenant context, so on a real deployment (non-superuser
owner, no `BYPASSRLS`) it prints `CR-145: 0 utility(ies) moved …`; `0008` walks the tenants
one at a time and prints `CR-145 (per tenant): N utility(ies) moved …` followed by one line
per utility. **The number of utilities moved is the sum of the two**, and it should equal
the number of lines r5.1 printed — or exceed it only by utilities that are not live
(`0008` walks every row in `tenants`; r5.1 asks only for live ones). Record it on the release; it is the figure the PO asked
for. Neither migration touches a session — `0006` adds five columns, `0007`/`0008` rewrite
one column of `security_policies`.

⚠ **NOT REVERSIBLE FROM THE ROW.** The old 240/480 survives only in those audit rows, and
`audit_log` is pruned on its retention schedule with no exemption (hard rule 4). Keep the
printed output with the release record.

### r5.3 After the deploy — the new nightly schedule, and the release note

* **`identity.session_cleanup`**, 03:20 every day, on the existing beat service — it is
  installed from `apps/identity/apps.py`'s `ready()`, so **nothing is added per schedule on
  ECS**: beat stays one service at desired count 1 and picks up the entry from the image.
  It deletes staff and portal sessions that have **already expired or been signed out**,
  and never an idle or live one. `G132` must list it; if beat is not deployed, it never
  runs and nothing errors (§9.2's beat-liveness alarm is what notices).
* **Release note — both halves, or neither:**
  > Sessions opened before the deploy keep their old cookie until they expire; nobody is
  > forced to sign out. Utilities that were on a 4- or 8-hour inactivity timeout now sign
  > their staff out after 1 hour of inactivity, so a person who steps away for longer than
  > that will be asked to sign in again where yesterday they were not.

  Checked in the code on 2026-09-28: the cookie names `sbh_session` and `sbh_portal` are
  unchanged; the value is still the session id and the only change to the three
  `set_cookie` calls is an explicit `max_age`; no migration deletes or revokes a session;
  the nightly sweep removes only expired or signed-out rows. ⚠ **The *Keep me signed in*
  fix reaches a person at their next sign-in**, not at the deploy — a browser already
  holding the old cookie keeps it until the browser closes.

## r6 · 2.443.0 — the nightly clean-up of unsent portal applications (`CR-158-BRC10` §5)

* **What it is.** `portal.draft_cleanup`, **03:40 UTC every day**, on the existing beat
  service — installed from `apps/portal/apps.py`'s `ready()`, so, as in r5.3, **nothing is
  added on ECS**. PO ruling 2026-10-02: an application a customer started on the portal and
  never sent is deleted, **with the files attached to it**, **30 days after their last
  visit** — opening the link, saving, or adding or removing a file is a visit. The days are
  the utility's own calendar days: a draft last visited on 1 October goes in the run that
  falls on 31 October in that utility's timezone.
* **The migration** `portal/0012` adds one nullable column (`last_visited_at`) and backfills
  nothing; it is instant on any table size. Drafts from before it count from their last
  save, so **the first night after the deploy may delete applications abandoned more than
  30 days ago** — that is the ruling applied to them, not a fault.
* **What to check after the deploy.** `G132` lists `portal.draft_cleanup`. After the first
  03:40 run, `audit_log` rows with `action = 'portal.application_draft.deleted_unsent'`
  show what went, per utility, each naming its file count and *"unsent 30 days"*. Zero rows
  is a normal answer for a utility with no abandoned application.
* **What it never does.** It never touches a SENT application or anything in the document
  store, never a draft visited in the last 30 days, and never another utility's drafts. A
  second run the same night deletes nothing.
* **If beat is not deployed**, it never runs and nothing errors; unsent applications are
  then kept, which is the state before this ruling (§9.2's beat-liveness alarm is what
  notices).
* **Release note:**
  > An application started on the customer portal and never sent is now deleted, with any
  > documents attached to it, 30 days after the customer last opened it. Sent applications
  > are not affected.

## r7 · 2.562.0 — Settings → Security made true (`DEF-IDN-10022/10023/10024`, PO ruling 2026-10-08)

* **The migration** `identity/0010` adds one empty table, `password_history`, with
  ENABLE + FORCE row-level security. Instant on any size; it back-fills nothing, so
  nobody's earlier passwords are known on day one — the history fills as people change.
* **What users will notice.** (1) Where a utility has *Password expires after* set to 90
  or 180 days, anyone whose password is older than that is sent to *Set your password* at
  their next sign-in. ⚠ **On the first day this ships, that can be many people at once** —
  logins with no recorded change date count from the day they were created. A utility on
  *Never* (the default) sees nothing. (2) A new password matching the current one or any of
  the five before it is refused. (3) A page left open that refreshes itself (the bill run,
  imports) now signs out after the utility's idle time, as the setting always said.
* **CORS.** The SPA sends one new request header, `X-Background-Refresh`, and
  `CORS_ALLOW_HEADERS` grants it in code. Nothing to set. ⚠ If a WAF or proxy in front of
  the API strips or rejects unknown request headers, allow this one — stripping it only
  loses the idle sign-out on polling pages; rejecting it would break those pages.
* ⚠ **BEFORE ANY UTILITY USES *ALLOWED ADDRESSES* — CONFIRM `TRUSTED_PROXY_COUNT`.** The
  allowlist compares the address `client_ip` computes, which trusts `X-Forwarded-For` only
  as many hops deep as `TRUSTED_PROXY_COUNT` (§10.15, §11 item 24). It must equal the
  number of proxies OF OURS in front of the API — **1 on ECS behind one ALB**; add one for
  each further proxy we run (a CloudFront in front of the ALB makes it 2). Too low and every
  caller looks like the load balancer (a utility's list then locks everybody out, or lets
  everybody in); too high and a caller can forge their own address. **Check it, read-only:**
  1. sign in to the live site yourself from a known address (note your public IP);
  2. on a backend task: `python manage.py client_ip_check` — it prints
     `TRUSTED_PROXY_COUNT = N` and the address recorded for the newest sign-ins. Yours must
     be your public IP. A `10.x`, `172.16–31.x` or `192.168.x` address means the server is
     seeing a proxy: the setting is too low;
  3. to test a line from the ALB access log without a deploy:
     `python manage.py client_ip_check --remote-addr <ALB peer> --xff "<X-Forwarded-For>"`.
  A changed `TRUSTED_PROXY_COUNT` reaches a running task only through its task definition —
  editing `.env.example` changes nothing already deployed (hard-won law 4).
* **Rollback:** redeploy 2.561.5. `identity/0010` may stay (an unused table); reversing it
  drops the history, which is harmless.
