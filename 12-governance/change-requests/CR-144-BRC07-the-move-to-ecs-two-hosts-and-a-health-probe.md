# `CR-144-BRC07` — the move to ECS Fargate: two hosts, a health probe, and a deploy that stops migrating

**Raised:** 2026-09-28 · **Version:** `2.388.0` · **Branch:** `claude/kind-goldberg-k0acqg`
**Two lanes, one change request:** DEP-BACKEND (`H1`–`H9`, `X1`–`X6`) and
DEP-FRONTEND (`FB1`–`FB12`). One change — a single deployment move — split by
where the code lives, not two changes.

⚠ **THIS FILE WAS WRITTEN BY THE BACKEND LANE AND ITS FRONT-END HALF IS
SUMMARISED FROM THE DECISION LOG RATHER THAN AUTHORED.** DEP-FRONTEND should
**extend** §3 rather than replace this file.

---

## 0 · Capture — the requester's words

Three rulings, already recorded verbatim in `12-governance/02-decision-log.md`
on 2026-09-28, before any code was written:

* *"I dont want to get locked in with the cdn from an cloud provider later if I
  move out from this cloud I dont want this to be a blocker."*
* The health path is `/api/health`. `/api/smart360/...` was **rejected** because
  every `/api/<segment>/` is read as a customer slug.
* Three build commands, each baking its own API host, and the build **fails**
  when `VITE_API_BASE_URL` is missing.

## 1 · Classify — **CHANGE**, not a defect

The product does not fail to do something it promised. It is being moved onto a
different machine shape: one container serving both halves becomes a static
frontend on S3 plus an API behind an Application Load Balancer, across three
environments.

⚠ **ONE ITEM INSIDE IT IS A DEFECT AND IS NAMED SO.** The session cookie was set
without `Secure` (runbook §10.9, open since r1). It is fixed here because the
move is what makes it urgent, not because the move created it.

## 2 · What signed statement is reversed

**None.** No `❄️ FROZEN` B4/B5 figure, no money rule, no rating rule is touched.
Two infrastructure statements in `09-infra/` are superseded and both are amended
in place with the date:

| Superseded | By |
|---|---|
| *"The app still has no health endpoint"* (runbook §10.8, Step 8) | `/api/health`, answered by middleware placed first |
| *"append the task IP to `ALLOWED_HOSTS` at start-up"* (arch §10.4, runbook §7.4) | **withdrawn** — the probe answers before host validation |

## 3 · Impact

| Surface | What moves |
|---|---|
| Backend code | `core/health.py` (new) · `core/origin_guard.py` (new) · `MIDDLEWARE` order · `production.py` security settings · three cookie sites |
| Backend boot | `docker-entrypoint.sh` stops migrating · `docker-release.sh` (new) |
| Dependencies | `django-cors-headers` becomes a runtime dependency |
| Frontend | three build commands, the per-environment API base URL, 12 hand-built API links in 9 files, the security policy into a `<meta>` tag |
| Documents | `09-infra/01` §5 and §10.4, `09-infra/02` Step 8, §10.8, §10.9 and asks 21/22/24, plus a new r4 section in each |
| Environment | `06-backend/.env.example` gains six variables |
| Open questions | none opened, none closed |
| Demo fixture | untouched |

## 4 · What is already built and is now wrong

Nothing shipped is made wrong by this. **What is made wrong is the runbook**,
which told DevOps to health-check `/api/public/pricing-plans` and to append the
task IP to `ALLOWED_HOSTS`. Both instructions are withdrawn in this change, in
the same commit as the code that makes them unnecessary — a stale instruction
left behind is this repo's most-filed rot.

## 5 · Size, in plain English with a figure

Two lanes, one afternoon. On the backend: two new middleware files, one new boot
script, six new environment variables, 33 new test cases. **The figure that
matters is `400`** — the status Django answered to the load balancer's own
health check before any of this, measured as a red test:
`AssertionError: 400 for Host: 10.0.1.23`. With the HTTPS redirect on it was
`301`. Either one means every copy of the app is declared dead and replaced, for
ever, and nothing ever serves a customer.

## 6 · Execute — through r11, unchanged

Done. The two lanes' commits are on `claude/kind-goldberg-k0acqg`.

## 7 · **VERSION — `2.388.0`**

ONE bump between the two lanes (`DEF-GOV-3756`'s collision is two lanes each
bumping). `07-frontend/package.json` — the source of truth — was moved by
DEP-FRONTEND; `06-backend/pyproject.toml`, the derived copy, was made to agree
by DEP-BACKEND rather than separately allocated.

## 8 · Close, and the rollback

**Rollback, stated before shipping:**

| If | Then |
|---|---|
| The health probe misbehaves | Point the target group back at `GET /api/public/pricing-plans` **and** add the task IP to `DJANGO_ALLOWED_HOSTS`. Both together, or it 400s. |
| The Origin guard refuses a legitimate caller | Set `ORIGIN_GUARD_ALLOWED_ORIGINS` to include it — a task-definition revision, no code change. It is a separate variable from `CORS_ALLOWED_ORIGINS` for exactly this. |
| `Secure` cookies break an environment | `SBH_AUTH_COOKIE_SECURE=false` on that task definition. ⚠ It means the sign-in cookie travels unmarked; it is a bridge, not a setting. |
| HTTPS/HSTS misbehaves | `SECURE_SSL_REDIRECT` and `SECURE_HSTS_SECONDS` both default to off/0. ⚠ **HSTS cannot be rolled back once a browser has seen it** — that is why it ships at 0. |
| The release task is the problem | Put `python manage.py migrate --noinput` back in `docker-entrypoint.sh` **and scale the service to one task**, or the race returns. |
| A bundle points at the wrong API | Rebuild with the right mode and re-upload. **There is no runtime switch** — the address is inlined, which is the point. `node 07-frontend/scripts/checkBundleHost.mjs <mode> dist` says which host a `dist/` actually names before it is uploaded. |
| The page-security policy blocks something we serve | The meta tag is generated in `07-frontend/vite.config.ts` from `server.mjs`'s `BASE_POLICY`; widen it **there and in `page_policy.py` together**, which `server.test.mjs` already enforces, then rebuild. ⚠ A meta policy INTERSECTS with any header the static host adds — it can only ever narrow, never widen, so a header alone will not undo it. |
| The asset map draws no background | Known and filed (`DEF-INT-7430`). Give the static host the tile origin, or have it serve the whole policy as a header and drop the meta tag. |
| The screens need a same-origin deploy again | `server.mjs` and the `Dockerfile` are **kept** and still work: set `VITE_API_BASE_URL=` empty, rebuild, and run the container as before. Nothing was deleted. |

**Closes when:** a DevOps engineer reports a target group going healthy on
`/api/health` in a real environment, and a clerk signs in through
`app.bynry.com` against `api-smart360.bynry.com`. Neither has happened yet —
there is no AWS account reachable from this repo.
