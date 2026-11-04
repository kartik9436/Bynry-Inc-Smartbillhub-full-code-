"""Base settings. Module registry mirrors B1 — one Django app per domain module."""

import hashlib
import json
import re
from pathlib import Path

# DEF-INF-7616 — the six request headers django-cors-headers grants by default,
# splatted into `CORS_ALLOW_HEADERS` beside the other CORS settings far below.
# ⚠ IMPORTED HERE AND NOT AT THE SETTING: `[tool.ruff.lint] select` includes
# `E4`, so an import next to its use is an E402. `corsheaders.defaults` is two
# tuples and imports nothing from Django, so it is safe this early — and
# `django-cors-headers` is a hard dependency in pyproject.toml, which is what
# stops this line raising at settings import inside the shipped image (the
# Dockerfile builds its requirements from that list only).
from corsheaders.defaults import default_headers

import environ

env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

# ═══════════════════════════════════════════════════════════════════════════
# CR-049 — THE DOCUMENT STORE. Where a frozen legal document's BYTES go.
# ═══════════════════════════════════════════════════════════════════════════
# The whole design and every reason is in apps/tenancy/document_storage.py.
# What matters HERE is hard-won law 3: THE UNSAFE OPTION IS THE ONE SOMEBODY
# HAS TO TYPE.
#
# The default backend is AWS S3 and the default bucket is EMPTY, so a
# deployment that has not been configured REFUSES to store a document at the
# first attempt. It does not fall back to local disk. That refusal is the
# correct outcome and is not a bug report: a legal document written to a
# container's disk is destroyed by the next restart, and NFR-35 requires it
# kept for seven years.
#
# Reaching the local-disk backend takes TWO settings — the backend name AND
# DOCUMENT_STORAGE_ALLOW_FILESYSTEM, which is False here and True only in
# config/settings/test.py and local.py. That is the same two-key shape
# FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS uses a few lines' worth of subsystem
# away, and for the identical reason: a development convenience that must be
# impossible to reach by accident.
#
# ⚠ AND EDITING .env.example FIXES NOTHING ALREADY DEPLOYED (hard-won law 4).
# ── NO UPLOAD IS VIRUS-SCANNED — PO, 2026-09-22 AND 2026-09-23 ─────────────
#
# PO, verbatim, 2026-09-23: *"please remove virus scan chek user don't wan't it.
# we have ask remove it before why you did not remove it?"*. `BR-SHL-253` (the
# in-line scanner daemon ruled on 2026-09-13) and the scan clauses of
# `BR-SHL-031` and `NFR-34` are SUPERSEDED, and the scanner, its seven settings
# and its middleware entry were deleted rather than switched off
# (`DEF-SHL-6347`). ⚠ **DO NOT ADD A SCANNER SETTING BACK "FOR LATER"** — a
# setting nothing reads is the kind a later lane wires back up, and
# `tests/test_br_shl_253_malware_scan.py` fails the day one appears. A host
# whose `.env` still names the old settings keeps those lines, read by nothing
# (hard-won law 4).

DOCUMENT_STORAGE_BACKEND = env("DOCUMENT_STORAGE_BACKEND", default="aws_s3")
DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
DOCUMENT_STORAGE_DIR = env("DOCUMENT_STORAGE_DIR", default="")
DOCUMENT_STORAGE_BUCKET = env("DOCUMENT_STORAGE_BUCKET", default="")
DOCUMENT_STORAGE_REGION = env("DOCUMENT_STORAGE_REGION", default="")
# Empty for AWS S3 itself; set for a VPC endpoint or an S3-compatible service.
DOCUMENT_STORAGE_ENDPOINT_URL = env("DOCUMENT_STORAGE_ENDPOINT_URL", default="")
# Server-side encryption. Emptying it is REFUSED, not obeyed.
DOCUMENT_STORAGE_SSE = env("DOCUMENT_STORAGE_SSE", default="AES256")
# NFR-35's seven years.
DOCUMENT_STORAGE_RETENTION_YEARS = env.int("DOCUMENT_STORAGE_RETENTION_YEARS", default=7)
# HOW THE DOCUMENT IS LOCKED — NONE (default), COMPLIANCE or GOVERNANCE.
#
# ⚠ THE DEFAULT IS NONE FROM 2026-10-02 — CR-160-BRC10, PO: "we dont want this
# to be enabled right now - dont lock it". NO FILE IS OBJECT-LOCKED, LEGAL FILES
# INCLUDED, AND NO FILE CARRIES AN EXPIRY TAG. It was COMPLIANCE. Typing
# COMPLIANCE or GOVERNANCE switches the lock back on for files written AFTER
# that moment only (and needs a bucket created with Object Lock). A host whose
# .env already types COMPLIANCE keeps locking until that .env is edited —
# editing this default reaches no host that sets the variable (hard-won law 4).
# The bucket must NOT carry a default retention rule: core/storage_guard.py
# refuses one at boot, because it would lock every file for its whole period.
#
# The paragraph below is the 2026-09-03 history of the setting, kept:
#
# PO 2026-09-03, mid S3 setup: "Until we are in beta mode We should able to
# delete these pdfs". NFR-35 is NOT amended — it still says seven years,
# write-once, for a utility's real documents. This is an environment-scoped
# exception for a deployment holding none of them, and law 3 decides the
# default: a host that sets nothing gets the strict lock, and giving it up
# takes somebody typing.
#
# ⚠ NONE is the only value that works on a bucket created WITHOUT Object Lock.
# AWS cannot switch Object Lock on afterwards, so such a bucket is either
# replaced or run with NONE. The other two are refused by S3 with
# "Bucket is missing ObjectLockConfiguration".
DOCUMENT_STORAGE_OBJECT_LOCK_MODE = env("DOCUMENT_STORAGE_OBJECT_LOCK_MODE", default="NONE")
# FOUR HOURS — PO ruling 2026-08-30, "dont expire it in minutes - exprise it in
# 3 or 4 hours". It is capped at four hours in code, so this setting can
# SHORTEN a link's life without a deploy and cannot lengthen it.
DOCUMENT_STORAGE_URL_TTL_SECONDS = env.int("DOCUMENT_STORAGE_URL_TTL_SECONDS", default=14400)
# DEF-TEN-9190 — HOW LONG ONE S3 CALL MAY WAIT, AND HOW OFTEN IT IS TRIED.
# Until 2026-10-02 the client carried boto3's defaults (60 s to connect, 60 s
# to read, five "legacy" attempts), so a worker with no network path to S3 sat
# in `running` for minutes with nothing in any log. Measured against a listener
# that accepts and never answers: boto3's defaults took 311 s to fail one
# upload. At the defaults below (botocore counts RETRIES, so 3 is 4 calls) a
# path where nothing answers the connect fails in about 20 s, and one that
# connects and then goes silent in about 4 minutes — both inside the screen's
# 5-minute wait, and both SAY so. A slow-but-live link is unaffected: the read
# timeout is per socket read, not per file.
DOCUMENT_STORAGE_CONNECT_TIMEOUT = env.int("DOCUMENT_STORAGE_CONNECT_TIMEOUT", default=5)
DOCUMENT_STORAGE_READ_TIMEOUT = env.int("DOCUMENT_STORAGE_READ_TIMEOUT", default=60)
DOCUMENT_STORAGE_MAX_ATTEMPTS = env.int("DOCUMENT_STORAGE_MAX_ATTEMPTS", default=3)
# DEF-TEN-9190 — an EXPORT job whose record is unwritten this long is failed by
# the ten-minute beat sweep (`apps/tenancy/export_sweep.py`), with a reason.
EXPORT_STALL_SECONDS = env.int("EXPORT_STALL_SECONDS", default=1800)

# ═══════════════════════════════════════════════════════════════════════════
# CR-067 — HOW LONG THE TECHNICAL DETAIL OF A FAILURE IS KEPT
# ═══════════════════════════════════════════════════════════════════════════
# `audit_log` is permanent by rule (BR-AUD-002 — it has no write verbs, so a row
# put there is there for the retention life of the trail). The DIAGNOSTIC beside
# it is the opposite: it exists to make one runtime failure reproducible, it is
# read within days by whoever is fixing it, and it expires.
#
# 90 days is CR-067 §3's proposal and this is the whole of its implementation —
# one number, changed without a deploy of new code.
#
# ⚠ `OQ-1390` IS OPEN: is 90 right, and does a diagnostic fall under `audit_log`'s
# retention regime or its own? It is PROPOSED as its own, because a diagnostic
# holds no customer data and therefore has no legal floor. Nothing in the code
# guesses the answer — when it is ruled, the ruling moves this line.
DIAGNOSTIC_RETENTION_DAYS = env.int("DIAGNOSTIC_RETENTION_DAYS", default=90)

DOMAIN_APPS = [
    "apps.tenancy",
    "apps.identity",
    "apps.customers",
    "apps.metering",
    "apps.assets",  # W1 lane: hosts the B2 r4 assets set (metering-owned tables — see
    #   apps/assets/models.py ownership note; hosting disposition reported)
    "apps.rating",
    "apps.billing",
    "apps.payments",
    "apps.ledger",
    "apps.notifications",
    "apps.audit",
    "apps.reports",
    "apps.integrations",
    # CR-068 wave A (2026-09-03): the customer web portal — a TENTH code
    # module (CLAUDE.md module map + CR-068 §11b), owning `portal_settings`
    # and reaching everything else through apps/portal/seams/.
    "apps.portal",
    # CR-070 wave A (2026-09-03): field work — the ELEVENTH code module (PO:
    # "it will become the module itself"). No model of its own yet; the six
    # Work tables stay in apps/metering/connections.py until 16-work/
    # 03-field-map.md §4 is decided. See apps/work/apps.py.
    "apps.work",
    # CR-075 wave A (2026-09-06): Runbooks — the TWELFTH code module. It owns
    # seven tables of its own, READS every other module through one seam file
    # per module in apps/runbooks/seams/, and WRITES nothing of theirs: the
    # thirteen ports in apps/runbooks/ports/ are declarations with no writer
    # bound until phase 4. G115 fails a foreign import from its first commit.
    # ⚠ The directory is `runbooks` and the nav route is `/{tenant}/operations`
    # — two names on purpose, see apps/runbooks/apps.py.
    "apps.runbooks",
]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "drf_spectacular",  # BE-11 (TD-19): OpenAPI schema generation
    # CR-144-BRC07 (X1) — CORS. The app is served from a DIFFERENT HOST to the
    # API (decision log 2026-09-28 ruling 1: two hosts, no CDN path-routing of
    # `/api/*`, because the PO refused CDN lock-in), so every call the browser
    # makes is cross-origin and needs a grant.
    "corsheaders",
    *DOMAIN_APPS,
]

MIDDLEWARE = [
    # ⚠ **FIRST, AND THAT IS NOT A STYLE CHOICE — CR-144-BRC07 / decision log
    # 2026-09-28 ruling 2.** The Application Load Balancer addresses the ECS
    # task by its PRIVATE IP, so the health request arrives with
    # `Host: 10.0.1.23`. `ALLOWED_HOSTS` carries the public API name and cannot
    # carry an address that changes with every task placement, so Django's host
    # validation answers **400 before any URL is resolved** — a health VIEW can
    # never be reached, whatever it is mounted on. Measured as a red test before
    # `core/health.py` existed: `AssertionError: 400 for Host: 10.0.1.23`.
    #
    # ⚠ **AND AHEAD OF `SecurityMiddleware` FOR A SECOND, SEPARATE REASON.**
    # `SECURE_SSL_REDIRECT` is that middleware's, and the balancer speaks plain
    # HTTP to port 8000: behind it the probe gets a **301**, every task fails
    # its check and is replaced. Same red proof, one line down:
    # `AssertionError: 301 — the probe was redirected instead of answered`.
    #
    # ⚠ **NOTHING MAY BE PLACED ABOVE IT.** Anything above it can 400, 301 or
    # 500 the probe, and the symptom is "every task is unhealthy and the app is
    # fine" — which reads as an infrastructure fault and is not one.
    "core.health.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # CR-144-BRC07 (X1) — CORS. ⚠ **BEFORE `CommonMiddleware`, WHICH IS THE
    # LIBRARY'S OWN REQUIREMENT**: a redirect issued before the CORS headers
    # are attached reaches the browser without them, and the browser then
    # reports a CORS failure for a response that was merely a redirect.
    # Exactly ONE origin per environment and never `*` — see CORS_ALLOWED_ORIGINS
    # below, and the reasoning for why `*` is not even available to us.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CR-144-BRC07 (X2) — the guard CORS does NOT give you. `app-*.bynry.com`
    # and `api-*.bynry.com` are THE SAME SITE, so a `SameSite=Lax` session
    # cookie rides along from ANY `*.bynry.com` page, and CORS does not stop a
    # cross-origin form POST — the browser sends it and only hides the
    # response. Read core/origin_guard.py before moving or removing this.
    "core.origin_guard.OriginGuardMiddleware",
    # CR-187-BRC10 (DEF-FLD-10355, 07-endpoints N7) — the native field app's
    # minimum version. BEFORE the tenant is resolved, so a too-old build is
    # refused with no database read and every field response (its 404 too)
    # carries `X-Field-Schema-Version`. Scoped by path to the field routes;
    # read core/field_app_version.py before moving it.
    "core.field_app_version.FieldAppVersionMiddleware",
    # BE-01 (HUMAN-OWNED, review pending — see core/tenancy.py + human-review ledger):
    # resolves the tenant from the request path's /api/{tenant}/ segment (PO ruling
    # 2026-08-10; was the Host's first label), SETs app.tenant_id on the DB session.
    "core.tenancy.TenantContextMiddleware",
    # DEF-CWP-3961 — the LAST thing that touches a customer-facing portal body.
    # `problems[].detail` is a sentence written for a developer, and one of
    # them echoes the caller's own account id back at them. The rule was
    # applied on ONE route of that edge (api._webhook_view, DEF-CWP-3926) and
    # not on the other eight, because a fix at a call site cannot travel. This
    # is on the WIRE so a route cannot be written that forgets — seventeen
    # portal responses already skip `_no_store`, and `guest_api` skips it
    # entirely. Scoped to customer paths: the staff app serves `detail` to
    # clerks deliberately.
    "apps.portal.wire.PortalDiagnosticScrub",
    # CR-069 wave M (US-INT-042, `C14`) — the GENERATED Content-Security-Policy.
    # ⚠ **THIS REPOSITORY CONFIGURED NO CSP AT ALL UNTIL 2026-09-06**, which is
    # `US-INT-042` §1's own sentence, and it matters because the asset map
    # fetches hundreds of third-party tiles per pan. The policy is generated
    # from the manifests' registered BROWSER operations and this tenant's
    # connections (`apps/integrations/page_policy.py`), so a host is permitted
    # because a utility connected it and never because somebody typed it here.
    #
    # ⚠ **AFTER `TenantContextMiddleware`, DELIBERATELY.** The policy is per
    # tenant, so it needs the resolved context; Django runs `__call__` on the
    # way in and unwinds on the way out, so a later entry sees the context the
    # earlier one set. Placed before it, every response would carry the
    # base policy and the map would be blocked with nothing to read.
    #
    # ⚠ **AND IT IS THE SECOND OF TWO PLACES.** The header a browser ENFORCES
    # is the one on the document, set by `07-frontend/server.mjs`; this one
    # covers the API's own responses and is what a test can read.
    "apps.integrations.middleware.PagePolicyMiddleware",
]

# TRUSTED_PROXY_COUNT — how many reverse proxies of OURS sit in front of this
# process (09-infra/02 §10.15, deploy defect closed 2026-08-10).
#
# `REMOTE_ADDR` is the peer that opened the TCP connection. Direct-to-gunicorn
# that IS the client; behind a load balancer it is the load balancer, for every
# request alike — which silently voids BR-IDN-020's per-tenant IP allowlist and
# collapses DRF's throttle identity onto one address.
#
# The obvious repair — "read X-Forwarded-For" — is worse than the disease: XFF
# is a client-writable header, so a caller that prepends one address per request
# gets an unlimited number of throttle identities and can claim any allowlisted
# address it likes. Only the RIGHTMOST entries of that chain are trustworthy,
# and only as many of them as there are proxies we actually run: each of ours
# appends the address IT saw, so with N trusted proxies the client is the Nth
# entry from the right (the chain being XFF + REMOTE_ADDR). Everything to the
# left of that arrived from outside and is treated as forgeable noise.
#
#   0 (default) = trust nothing — REMOTE_ADDR only, today's behavior. A
#                 deployment that forgets this setting is WRONG-BUT-SAFE
#                 (allowlists over-restrict, throttles over-group); it can
#                 never be tricked into believing a forged address.
#   1           = THE VALUE A DEPLOYED ENVIRONMENT NEEDS with exactly one
#                 proxy of ours in front: one ALB and nothing else
#                 (09-infra/02 §2.4), or — in the container stack this repo
#                 ships — the frontend container's `/api/*` pass-through,
#                 which appends the address it saw before forwarding
#                 (06-backend/.env.example documents that chain and sets 1).
#                 Either way the proxy appends its peer, so XFF's last entry
#                 is the real client.
#   2           = two of ours in the chain — CloudFront in front of an ALB, or
#                 an ALB in front of that frontend container. Add 1 per proxy
#                 OF OURS, never one for "the client's proxy": those are
#                 exactly what must not be trusted.
#
# Count the chain that will actually be deployed and set the number; the wrong
# number in the SAFE direction (too low) only over-restricts, while too high
# reads an address the client controls. The default here is 0 for that reason.
#
# Both readers of the client address take the same value: apps.identity.auth
# .client_ip() (BR-IDN-020) and DRF's own BaseThrottle.get_ident() via
# NUM_PROXIES below. They must never disagree — one identity, one rule.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)

# ── CR-144-BRC07 (X1/X2/X3) — cross-origin access, and the cookie ──────────
#
# THE SHAPE THIS IS FOR (decision log 2026-09-28, ruling 1): the SPA is served
# from `app[-env].bynry.com` and the API from `api-smart360[-env].bynry.com`.
# Two hosts, on purpose — the PO refused CDN path-routing of `/api/*` so that
# leaving this cloud is never blocked by it. So EVERY call the browser makes is
# cross-origin, and the API must grant it explicitly.
#
# ⚠ **EXACTLY ONE ORIGIN PER ENVIRONMENT, AND NEVER `*`.** This is not caution:
# `Access-Control-Allow-Origin: *` and `Access-Control-Allow-Credentials: true`
# are mutually exclusive by specification — a browser refuses the pair — and the
# session cookie IS the credential. A wildcard here would not be lax, it would
# simply not work, and the symptom would be "signed in and every call is 401".
#
# Empty by default (hard-won law 3, the unsafe option is the one you type): a
# deployment that forgets this grants nothing and fails loudly in the browser
# console, rather than granting everything quietly.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# The cookie is the point. Without this the browser sends no cookie on a
# cross-origin call and every request is anonymous.
CORS_ALLOW_CREDENTIALS = True

# Only the API. Nothing else is served from this process, and a blanket regex
# would grant the grant to paths that should never be reachable cross-origin.
CORS_URLS_REGEX = r"^/api/.*$"

# ── WHAT MAY BE SENT, AND WHAT MAY BE READ BACK — DEF-INF-7616 ─────────────
#
# ⚠ **A CROSS-ORIGIN GRANT IS THREE ANSWERS AND CR-144-BRC07 WROTE ONE OF
# THEM.** The origin above answers WHO may call. These two answer WHAT MAY BE
# SENT and WHAT MAY BE READ BACK, and without them the first answer buys
# nothing at all. On 2026-09-28 every call from `app-dev.bynry.com` died in
# preflight:
#
#     Access to fetch at 'https://api-smart360-dev.bynry.com/api/public/
#     subdomain-check?subdomain=jay-utu' from origin 'https://app-dev.bynry.com'
#     has been blocked by CORS policy: Request header field x-support-ref is not
#     allowed by Access-Control-Allow-Headers in preflight response.
#
# The preflight answered **200, with the right origin, and without the header**,
# so the real request was never sent. Every call. Every screen. It could not
# show up before CR-144-BRC07 because a same-origin build makes no preflight at
# all — `VITE_API_BASE_URL` is empty locally and `server.mjs` passes `/api/*`
# through, so this whole file's CORS block was dead code until the SPA moved to
# its own host.
#
# ⚠ **THE LIST IS DERIVED FROM THE CLIENT, AND THE DERIVATION IS WRITTEN OUT
# HERE** so that the next person to add a header is told where its grant lives.
# `07-frontend/src/api/client.ts:570` is the ONLY `fetch` in the front end and
# it sets exactly four request headers: `Accept` and `Content-Type` (`:558`,
# `:561`), `X-Support-Ref` (`:558`, via `SUPPORT_REF_HEADER` at `:155`) and
# `If-None-Match` (`:564`). `Accept` is CORS-safelisted and `content-type` is
# already a default, so two names are added and no more.
#
# ⚠ **THIS SETTING REPLACES THE DEFAULTS, IT DOES NOT EXTEND THEM.** Dropping
# `*default_headers` would refuse `content-type` and break every JSON POST in
# the product — while the `x-support-ref` case above still passed. That is why
# `tests/test_def_inf_7616_cors_headers.py` asserts the six defaults BY NAME.
# ⚠ **A FIFTH, `X-Background-Refresh`, FROM 2026-10-08 (`DEF-IDN-10024`)** — the
# client sends it on a request made while nobody has touched the page, and
# `identity/auth.py` then does not slide the idle clock. Refused at preflight,
# every polling call cross-origin would fail outright rather than merely slide.
CORS_ALLOW_HEADERS = (*default_headers, "x-support-ref", "if-none-match", "x-background-refresh")

# ⚠ **THE SAME GAP RUNS THE OTHER WAY, AND THAT HALF FAILS IN SILENCE — WHICH
# IS WHY IT IS THE HALF WORTH READING.** A browser hides every non-safelisted
# RESPONSE header from the script unless this setting names it. No error, no
# console line, no failing test: cross-origin and unset,
# `response.headers.get("ETag")` simply returns `null`. Conditional caching
# stops working (`client.ts:596`), `Retry-After` stops steering the retry delay
# (`:604`), a download loses the filename the server chose
# (`endpoints.ts:14750`), and the audit banner states the wrong window
# (`endpoints.ts:3418` / `:3421`). That is hard-won law 2's mirror — a live
# screen behind a control that has quietly stopped answering.
#
# ⚠ **THE CRITERION IS WHAT THE FRONT END READS, NOT WHAT A VIEW SETS**, and
# the difference is deliberate rather than an oversight: a list built the other
# way would be longer and still wrong. Four things this API does send are NOT
# here, because nothing reads them, and they are named so that their absence is
# a decision rather than an oversight:
#
#   * `Location` on every `201` — `apps/tenancy/api.py:210`,
#     `apps/metering/api.py:369` and at least six more modules. This is the one
#     most likely to acquire a reader, since a create answers 201 and the new
#     id is in the body today.
#   * `X-Documents-Kept` / `X-Documents-Listed` — `apps/portal/api.py:3536`–`:3537`.
#   * `X-Cost-Rows-Omitted` — `apps/ledger/finance_api.py:1319`.
#   * the `X-Receipts-*` family — `apps/integrations/partner_api.py:1783`–`:1791`,
#     which is the SERVER-TO-SERVER partner surface and reaches no browser at all.
#
# Add a name when a reader appears, not before:
# `tests/test_def_inf_7616_cors_headers.py` walks every non-test `.ts`/`.tsx`
# under `07-frontend/src` and fails the day the front end starts reading one
# that is missing from this list.
#
# ⚠ **`X-Support-Ref` IS THE ONE NAME HERE WITH NO READER AND NO SENDER, SAID
# PLAINLY SO NOBODY BUILDS ON IT (hard-won law 1).** No view in this codebase
# sets it on a RESPONSE: the client mints it OUTBOUND (`client.ts:558`) and
# takes the trace back out of the JSON envelope's `trace_id` (`client.ts:120`).
# It is granted because echoing it is the obvious next step for support and a
# grant with no sender is inert rather than risky. It is NOT evidence that the
# echo exists.
#
# ⚠ **NEITHER SETTING IS READ FROM THE ENVIRONMENT, ON PURPOSE (hard-won law
# 4).** `CORS_ALLOWED_ORIGINS` has to differ per environment and therefore must
# be typed on every host; these two are a property of OUR OWN CLIENT and are
# identical everywhere. Keeping them as literals is what makes this a code-only
# fix: no `.env`, no task definition and no runbook table has to be touched on
# any host for it to take effect.
CORS_EXPOSE_HEADERS = [
    "ETag",
    "Retry-After",
    "Content-Disposition",
    "X-Support-Ref",
    "X-Audit-Window",
    "X-Audit-Window-From",
]

# ⚠ **THE SAME LIST DOES TWO DIFFERENT JOBS, AND THE SECOND IS THE ONE THAT
# ACTUALLY DEFENDS ANYTHING.** CORS decides what a browser is willing to SHOW a
# script; `core.origin_guard` decides what this server is willing to DO. A
# cross-origin form POST is sent by the browser either way — CORS only hides
# the response from the attacker's script — and `app-*.bynry.com` and
# `api-*.bynry.com` are the same SITE, so a `SameSite=Lax` cookie rides along
# from any `*.bynry.com` page. Read core/origin_guard.py.
ORIGIN_GUARD_ALLOWED_ORIGINS = env.list(
    "ORIGIN_GUARD_ALLOWED_ORIGINS", default=CORS_ALLOWED_ORIGINS
)

# ── THE APP'S PUBLIC ADDRESS — DEF-CWP-9717, PO ruling 2026-10-05 ───────────
#
# Where a customer or a clerk opens the app: `https://app-sand.bynry.com`, never
# the API's own host. The server builds every address it hands a PERSON from
# this — the customer portal's address, its Copy/Open buttons and its QR code
# (`core/public_origin.py`). PO, verbatim: *"(a) A setting per environment:
# each host names its public address, for example https://app-sand.bynry.com.
# The address is always the same, whoever opens the page."*
#
# ⚠ **WHY NOT `CORS_ALLOWED_ORIGINS[0]`, WHICH HOLDS THE SAME STRING TODAY.**
# That list answers WHO MAY CALL the API and may legitimately grow a second
# entry; a public address picked out of it by position would change silently
# the day it does. One fact, one name.
#
# Empty by default (law 3): a host that forgets it shows no portal address and
# draws no QR code, rather than one on the wrong host. Bare origin only —
# scheme and host, no trailing slash, no path. ⚠ LAW 4: type it in each host's
# existing `.env` / task definition; `.env.example` reaches no deployed host.
# ⚠ `CR-188-BRC10` (2026-10-22): this is ALSO the PO's answer 3, *"add one
# server setting for the product's public address"* — the staff invitation and
# reset emails build their one-time link from it (`core.public_origin.
# public_app_link`). Unset, those emails are not sent and the admin is told so.
PUBLIC_APP_ORIGIN = env("PUBLIC_APP_ORIGIN", default="")

# ── THE API'S PUBLIC ADDRESS — `CR-198-BRC10`, PO 2026-10-29 (answer 3) ───────
#
# Where a THIRD PARTY reaches this server — Twilio telephoning us back with a
# text's delivery status. Distinct from `PUBLIC_APP_ORIGIN` above, which is
# where a PERSON opens the app; the two hosts differ on every deployment that
# serves the API on its own name. Bare origin, no trailing slash, no path,
# e.g. `https://api-sand.bynry.com`.
#
# Empty by default (law 3): with it unset NO status callback is asked for, the
# Twilio card says so, and every callback that arrives anyway is refused,
# because the signature is checked against the address WE published and there
# is none. ⚠ LAW 4: type it in each host's existing `.env` / task definition;
# `.env.example` reaches no deployed host. The PO supplies the per-server values.
PUBLIC_API_BASE_URL = env("PUBLIC_API_BASE_URL", default="").strip().rstrip("/")

# ── TEXT MESSAGES — ONE SHARED PLATFORM TWILIO ACCOUNT (`CR-198-BRC10`) ───────
#
# PO 2026-10-29, ruling 4B: *one shared platform Twilio account*, the same
# shape as email's *"our account"* (2026-09-17). These are SERVER SECRETS: they
# are read by `apps/integrations/platform_sms.py` and nowhere else, never written
# to a tenant row, never served on any screen and never logged. All empty by
# default, and empty means SMS FAILS CLOSED: every text rests `queued` with a
# named reason and the card reads *Not set up on this server*.
#
#   TWILIO_ACCOUNT_SID          AC…  — always required (it is in every URL)
#   TWILIO_AUTH_TOKEN           the account's Auth Token. Sends with it AND checks
#                               Twilio's callback signature — without it every
#                               callback is refused (Twilio signs with this token
#                               even when you send with an API key).
#   TWILIO_API_KEY_SID / _SECRET  SK… + secret — optional; when BOTH are set they
#                               are used to SEND instead of the Auth Token.
#   TWILIO_MESSAGING_SERVICE_SID  MG… — the platform's default sender (preferred;
#                               A2P 10DLC needs a Messaging Service)
#   TWILIO_FROM_NUMBER          +E.164 — the default sender when no MG… is set
#   TWILIO_SENDER_BY_UTILITY    `subdomain:MG…;subdomain2:+1…` — a utility's own
#                               sender, held by the SERVER so no utility can type
#                               another's (decision log 2026-10-29, judgment 1)
#   TWILIO_API_BASE_URL         defaults to https://api.twilio.com; a test or the
#                               walkthrough points it at a fake.
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_API_KEY_SID = env("TWILIO_API_KEY_SID", default="")
TWILIO_API_KEY_SECRET = env("TWILIO_API_KEY_SECRET", default="")
TWILIO_MESSAGING_SERVICE_SID = env("TWILIO_MESSAGING_SERVICE_SID", default="")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", default="")
TWILIO_SENDER_BY_UTILITY = env("TWILIO_SENDER_BY_UTILITY", default="")
TWILIO_API_BASE_URL = env("TWILIO_API_BASE_URL", default="https://api.twilio.com")

# ── X3 — `Secure` on the sign-in cookies ───────────────────────────────────
# Read at the three places a session cookie is set: apps/identity/api.py,
# apps/tenancy/api.py and apps/portal/api.py. ONE setting, because three
# literals is three places to get it wrong (the pyproject/package.json version
# pair in this repo is the worked example of what that costs).
#
# ⚠ **DEFAULT `True` — HARD-WON LAW 3, THE UNSAFE OPTION IS THE ONE YOU TYPE.**
# A deployment that forgets this gets a cookie that only travels over HTTPS,
# which is right everywhere it is deployed.
#
# ⚠ **AND LAW 4: THIS DOES NOT REACH A HOST THAT ALREADY HAS A `.env`.** Local
# HTTP development under `config.settings.production` (which is what `make up`
# runs) needs `SBH_AUTH_COOKIE_SECURE=false` added to its OWN `06-backend/.env`
# by hand, or sign-in over `http://localhost` will appear to succeed and the
# next request will be anonymous — the browser accepts the response and then
# refuses to send a `Secure` cookie back over plain HTTP. `config.settings.local`
# and `config.settings.test` set it False for themselves.
AUTH_COOKIE_SECURE = env.bool("SBH_AUTH_COOKIE_SECURE", default=True)

# W0 kernels wired platform-wide: BE-02 envelope handler (B12 §3 + r1 HTTP table)
# and BE-05 pagination (IS-2 as amended — 50/100/200/500/1000, default 50).
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "core.errors.drf_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    # ── Authentication is PLATFORM-WIDE, not opt-in ──────────────────────────
    # 09-infra/02 §10.14 (deploy defect closed 2026-08-10): DRF's own default is
    # SessionAuthentication + BasicAuthentication, neither of which knows about
    # the identity `sessions` table, so every view that forgot to declare
    # `authentication_classes` answered 401 to a perfectly good cookie — most of
    # Settings, Lookups, Plans & Rates, Premises, Units, Routes, Cycles, Assets
    # and the S62 checklist. The gap was per-view because the DEFAULT was wrong;
    # declaring the class on ~70 views would have left the same trap open for
    # view #71. The default is the fix.
    #
    # Reading the session is not permission to do anything with it: this class
    # only attaches `request.user` + `request.tenant_role` (both server-derived)
    # and enforces the session's own law — one tenant per session (BR-IDN-006,
    # foreign path ⇒ 404), idle/absolute expiry, deactivation, the BR-IDN-020 IP
    # allowlist and the BR-IDN-022 forced-change gate. WHAT a caller may then
    # reach is still decided, endpoint by endpoint, by the BE-04 permission
    # classes below and by the service-layer @require_role guards behind them.
    # The three public routes (sign-in, pricing, slug availability) and
    # provisioning opt OUT with `authentication_classes = []`, which is now a
    # deliberate, greppable declaration instead of an accident of omission.
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.identity.auth.IdentitySessionAuthentication"],
    # …and the matching deny-by-default for authorisation. DRF ships `AllowAny`,
    # so a view that forgets `permission_classes` is world-readable; with the
    # authenticator now global that omission would be the only thing between an
    # endpoint and every caller. AnyTenantRole demands a signed-in member of the
    # resolved tenant — the weakest gate any real endpoint uses, and the same
    # posture as RLS (core/permissions.py). Every route in the product today
    # declares its own class, so this changes no existing answer; it decides
    # what happens the day someone forgets.
    "DEFAULT_PERMISSION_CLASSES": ["core.permissions.AnyTenantRole"],
    # §10.15: DRF's throttle identity reads the SAME trusted-proxy depth as
    # client_ip(). Left unset (DRF's default), BaseThrottle.get_ident() joins
    # the WHOLE X-Forwarded-For chain into the identity — so a client that
    # prepends a header gets a fresh bucket per request and the 60/min public
    # onboarding throttle is bypassable.
    "NUM_PROXIES": TRUSTED_PROXY_COUNT,
    # DEF-SHL-10621 (VAPT round, PO 2026-10-27) — the four APPLICATION rate
    # limits A1–A4: per user, per utility, heavy actions, field-app sync per
    # phone. A view that declares its own `throttle_classes` (every public door)
    # keeps exactly those. Rates and the on/off switch are below, from the
    # environment; `core/throttling.py` says what each one counts.
    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttling.HeavyActionThrottle",
        "core.throttling.DeviceSyncThrottle",
        "core.throttling.UserRateThrottle",
        "core.throttling.TenantRateThrottle",
    ],
    # BE-11 (TD-19): drf-spectacular generates the schema the typed frontend
    # client (FI-01) is built from.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# BE-11 — OpenAPI publisher (TD-19; B13 row BE-11). CI-DIFF CLAUSE (A11
# Addendum r2): the ratified contract baseline is A11 + 11b COMBINED; CI runs
# `manage.py export_openapi` and diffs the generated schema against the
# committed snapshot (06-backend/openapi/schema.json) — ANY drift fails the
# build loudly, so an endpoint can never change shape without the A11 contract
# (and the generated client) changing in the same review. The step is
# `OpenAPI contract diff` in .github/workflows/ci-backend.yml; it and the
# snapshot both landed 2026-08-10, having been described here for a day
# before either existed.
SPECTACULAR_SETTINGS = {
    "TITLE": "SMART360 Next API",
    "DESCRIPTION": (
        "Multi-tenant meter-to-cash + finance API. Contract of record: "
        "04-docs/01-spec/11-api-contracts.md (A11) + the 11b conformance audit, "
        "as ratified by A11 Addendum r2."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Deterministic output — a stable sort makes the CI diff signal, not noise.
    "SORT_OPERATIONS": True,
    "SORT_OPERATION_PARAMETERS": True,
    # PO ruling 2026-08-10: the tenant-scoped API is mounted behind a
    # non-capturing regex (config/urls.py explains why), which spectacular
    # would otherwise publish literally. See core/openapi.py.
    "PREPROCESSING_HOOKS": ["core.openapi.name_the_tenant_segment"],
    # `DEF-INT-6529`, 2026-09-24: the partner surface authenticates by a KEY
    # rather than by the session cookie, so it carries no DRF authenticator for
    # drf-spectacular to resolve a scheme from — and 23 operations, the payment
    # write among them, published `security: [{}]`, which a client generator
    # reads as *needs no credentials*. The door was never open; the sign on it
    # was wrong. `core.openapi.declare_the_key_schemes` defines the scheme those
    # operations name, importing it from the file that owns the door.
    #
    # ⚠ **THE FIRST ENTRY IS DRF-SPECTACULAR'S OWN DEFAULT AND IS REPEATED HERE
    # BECAUSE NAMING THIS SETTING REPLACES THE DEFAULT LIST RATHER THAN ADDING
    # TO IT.** Leaving it out would drop `postprocess_schema_enums` silently, in
    # a setting nobody would think to look at.
    #
    # ⚠ **MEASURED RATHER THAN ASSUMED, AND THE MEASUREMENT IS THE UNCOMFORTABLE
    # HALF:** that hook extracts repeated enums into named components, and this
    # contract has **zero** component schemas today — every view here is an
    # `@api_view` function with no serializer, which is what the generator's
    # *"unable to guess serializer"* warnings are. **So keeping it changes
    # nothing about the document we publish right now**, and the honest reason
    # to keep it is that it will matter the day a serializer-backed view lands,
    # not that it is doing work today. The proof that adding this setting caused
    # no other drift is the snapshot diff for `DEF-INT-6529`: 74 lines added and
    # 23 removed, every one of them a `security` block or the new scheme.
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "core.openapi.declare_the_key_schemes",
    ],
}

# BE-07 jobs framework (TD-17: async = Celery on Redis). The broker moves task
# messages ONLY — job status/progress/results live in job records polled at
# /jobs/{id} (B12 r1 202-contract, core/jobs.py), so a broker flush can delay
# work but never lose truth. The celery app module + beat schedule land with
# the first real job story; these settings are read then.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_TASK_ACKS_LATE = (
    True  # NFR-16: a worker crash re-delivers; every job is idempotent+resumable
)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # long money jobs: no task hoarding behind a slow run

# ── A JOB IS BOUNDED IN TIME (CR-051 task 30, the half that was missing) ────
#
# Task 30 asks for two bounds and until now this deployment had ONE. The SIZE
# bound is `BILLING_MAX_ACCOUNTS_PER_RUN` below — a run of more than 25,000
# accounts is refused at the door. Nothing bounded a run in TIME: `TIME_LIMIT`
# appeared nowhere in this package, so **a bill run that hung held one of the
# two worker slots for ever** and the only way to get it back was to restart a
# container. `DEF-2829` is the record of the CR counting that task done anyway.
#
# ⚠ **TWO LIMITS, AND ONE OF THEM ALONE IS WORSE THAN USELESS.**
#   * The SOFT limit raises `SoftTimeLimitExceeded` INSIDE the task, so
#     `core.jobs.run_job` catches it on the ordinary failure path it already
#     has, writes `failed` and a sentence onto the job record, and leaves the
#     checkpoint alone so the clerk's next attempt RESUMES (CR-051 task 11)
#     instead of re-walking. The run stops claiming it is working, and it says
#     what happened, in the same place every other job failure is said.
#   * The HARD limit is for a task that ignores the soft one — a C-level call
#     that never returns to the interpreter. Celery kills the worker child. It
#     records NOTHING: the job row is left `running` for ever, and because
#     `core.jobs.start` only admits `queued → running` and `failed → running`,
#     the re-delivered message cannot resume it either (`DEF-2805`). So the
#     hard limit is the backstop that gets the worker slot back, and the soft
#     limit is the one that keeps the record honest.
#
# ── WHERE THE NUMBERS COME FROM, so the next person can move them ──────────
# They are derived from the LARGEST RUN THIS DEPLOYMENT ACCEPTS and the
# SLOWEST per-account figure this repo has ever published, not from a round
# number that felt safe:
#
#     ceiling                    25,000 accounts  (BILLING_MAX_ACCOUNTS_PER_RUN)
#     slowest measured           0.219 s/account  (CR-051 task 26's re-measured
#                                table, 10,000 accounts, real PostgreSQL 16
#                                with row-level security ENFORCED, taken while
#                                the machine was at load 5-7)
#     longest legitimate run     25,000 x 0.219 = 5,475 s = 1 h 31 m
#     x 1.5 headroom             8,212.5 s  ->  8,220 s = 2 h 17 m   SOFT
#     + 300 s to fail honestly   8,520 s = 2 h 22 m                   HARD
#
# **Why 1.5 and not 1.0.** The 219 ms was itself measured under contention —
# the statement count is flat at 111 an account across a hundredfold range
# while the wall clock drifts from 172 ms to 219 ms, so the spread is the
# machine and not the work. Half again covers a slower disk or a busier host
# without letting a genuinely hung run sit through a whole shift.
#
# **The 300-second gap is an ASSUMPTION and is labelled as one.** Nothing here
# measured the longest single statement a run issues, and the soft signal is
# only seen when control returns to Python — a statement in flight finishes
# first. 300 s is longer than any statement this product is known to issue and
# short enough that a worker ignoring the soft signal is reclaimed in minutes.
#
# **Every other job fits inside the soft limit with room to spare**, which is
# what makes ONE pair of limits honest for all of them: the print set is 0.012 s
# a bill (25,000 bills = 5 min), the findings pass is the prepare pass measured
# at 121.9 s per 1,000 accounts (25,000 = 51 min), and the biggest import this
# product has been benchmarked on — 50,000 rows — is 230 s end to end.
#
# ⚠ **IT IS ONE PAIR FOR EVERY KIND, AND THAT IS A LIMITATION, NOT A DESIGN.**
# This deployment runs exactly ONE Celery task for every job kind
# (`apps.tenancy.tasks.run_pending_job` — the RECORD says what kind it is), so
# a per-kind limit cannot be expressed as a setting; it would have to travel on
# each `apply_async`. Until it does, a CSV export inherits a ceiling sized for
# a bill run, which bounds it and does not protect it.
#
# ⚠ **AND EDITING `.env.example` FIXES NOTHING ALREADY DEPLOYED** (hard-won
# law 4). A host that already has a `.env` keeps whatever it has.
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=8220)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=8520)

# ── WHAT MAKES `core.jobs.reclaim` SAFE (CR-105-BRC03) ─────────────────────
#
# A worker killed mid-job writes NOTHING — `core.jobs.run_job` catches
# `Exception`, and a process that dies raises none — so its record is left
# saying `running`. `CELERY_TASK_ACKS_LATE` above exists so the broker DELIVERS
# THAT MESSAGE AGAIN, and `core.jobs.resume` now reclaims such a record
# (`running` → `failed`, checkpoint untouched) so the redelivery can start it
# and skip what the dead attempt already finished.
#
# ⚠ **THAT IS ONLY SAFE IF A REDELIVERY PROVES THE PREVIOUS ATTEMPT IS DEAD,
# AND THIS LINE IS WHERE THAT IS ARRANGED.** Redis has no real acknowledgement:
# kombu re-delivers an unacked message once `visibility_timeout` elapses, and
# its DEFAULT IS 3600 SECONDS — **less than the 8520-second hard limit above**.
# So today a legitimate 70-minute bill run is re-delivered while it is still
# running. Nothing has gone wrong yet only because `start()` refused the second
# delivery outright; the moment a reclaim exists, that same sequence would put
# two passes on one job and let the first `succeed()` a record it no longer
# owns.
#
# Set ABOVE the hard limit, a redelivery cannot arrive until after the limit has
# already killed whatever was running the task. The two numbers are therefore
# set in one expression, each naming the other, because changing one without the
# other is what makes the reclaim unsafe — and nothing downstream could see it.
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": CELERY_TASK_TIME_LIMIT + 300,
}

# ── AND THE SIZE BOUND, WHICH SAID IT WAS OVERRIDABLE AND WAS NOT (DEF-2806) ─
#
# `run_jobs.max_accounts_per_run()` and `print_set.max_bills_per_print_set()`
# both read `getattr(settings, "<NAME>", <module default>)`, and both files
# tell their reader the name is a deployment override — *"an operator raises
# `BILLING_MAX_BILLS_PER_PRINT_SET` deliberately, and `0` switches the ceiling
# off"*. **No settings module declared either name**, so Django never exposed
# one, the `getattr` always fell through to the module default, and an operator
# who put `BILLING_MAX_ACCOUNTS_PER_RUN=5000` in `.env` changed nothing at all
# and was told nothing. That is hard-won law 1 exactly — a comment claiming a
# guarantee that was not there — on the setting CR-051 task 30 is about.
#
# ⚠ **THE DEFAULTS ARE STATED TWICE ON PURPOSE AND A TEST HOLDS THEM EQUAL.**
# A settings module may not import `apps.billing`, so the number cannot be read
# from `run_jobs.MAX_ACCOUNTS_PER_RUN_DEFAULT` here. The two literals are
# asserted equal by `tests/test_cr051_task30_time_limit.py`, so the pair cannot
# drift the way `package.json` and `pyproject.toml` did three times.
#
# `0` switches a ceiling OFF and has to be typed (hard-won law 3): the unsafe
# option is never the default.
BILLING_MAX_ACCOUNTS_PER_RUN = env.int("BILLING_MAX_ACCOUNTS_PER_RUN", default=25000)
BILLING_MAX_BILLS_PER_PRINT_SET = env.int("BILLING_MAX_BILLS_PER_PRINT_SET", default=25000)

# ── AND THE BAR ABOVE WHICH A RUN IS REFUSED RATHER THAN RUN INLINE ─────────
#
# CR-105-BRC03, blueprint p050: *"Refuse rather than run inline above the bar —
# a deployment with no worker runs the check inline today and the request dies
# long before its own `ran inline` answer can be read."*
#
# The number is arithmetic over two PUBLISHED figures and is derived in full in
# `apps/billing/run_jobs.INLINE_ACCOUNT_BAR_DEFAULT`: 60 seconds of request wall
# ÷ 0.17 seconds per account (CR-051 task 21, real PostgreSQL with RLS enforced)
# = 352, set at 300 to leave room for everything a request does that is not
# billing. Declared HERE as well as there for DEF-2806's reason — a module that
# reads `getattr(settings, NAME, DEFAULT)` for a name no settings module exposes
# ignores the operator's override and tells them nothing — and a test holds the
# two literals equal so they cannot drift.
#
# `0` switches the bar off, and the unsafe option is the one you type (law 3).
BILLING_INLINE_ACCOUNT_BAR = env.int("BILLING_INLINE_ACCOUNT_BAR", default=300)

# ── A STOPPED BILLING JOB (DEF-BIL-8511, 2026-09-30) ─────────────────────────
# How long a RUNNING billing job may write no progress before Resume takes it
# back from a worker that is gone. Two figures, read by
# `apps/billing/run_jobs.job_is_abandoned`:
#   * STOPPED_FLOOR — when the workers ANSWER and none is executing the job.
#     A short floor so a job just picked up is never taken back between two
#     heartbeats (the Check writes progress every 25 accounts: ~12-17 s at the
#     measured 0.5-0.7 s an account).
#   * STALL — when nobody can say (no answer from the broker): the heartbeat
#     alone, well above the Check's longest silence.
# Before this, a killed worker's job came back only when the broker re-delivered
# its message: CELERY_TASK_TIME_LIMIT + 300 = 8,820 s.
BILLING_JOB_STOPPED_FLOOR_SECONDS = env.int("BILLING_JOB_STOPPED_FLOOR_SECONDS", default=20)
BILLING_JOB_STALL_SECONDS = env.int("BILLING_JOB_STALL_SECONDS", default=300)

# ── HOW MANY CHECK BATCHES ONE UTILITY MAY RUN AT ONCE (B28, 2026-09-30) ─────
# Decision log 2026-09-30, decided by the coordinator at the PO's request
# (*"i dont know you can decide"*): HALF THE BILLING WORKERS, NEVER FEWER THAN 1,
# AS A PLATFORM SETTING — so one 40,000-account utility cannot hold every worker
# while another utility's run waits, and the figure moves with infrastructure
# without a code change. Read by `apps/billing/check_batches.batch_cap`.
#   * BILLING_WORKERS — how many billing worker SLOTS this deployment runs (the
#     `celery-billing` service's `--concurrency` times its replicas). The repo's
#     compose file runs 2; production scales it through infrastructure (PO,
#     2026-09-30), so set this to what infra actually runs.
#   * BILLING_CHECK_BATCHES_PER_UTILITY — an explicit cap; 0 (the default) means
#     derive it, max(1, BILLING_WORKERS // 2). 8 workers → 4; 2 → 1.
# ⚠ A template change never reaches a host that already has a `.env` (law 4):
# an operator who scales workers must set BILLING_WORKERS there too.
BILLING_WORKERS = env.int("BILLING_WORKERS", default=2)
BILLING_CHECK_BATCHES_PER_UTILITY = env.int("BILLING_CHECK_BATCHES_PER_UTILITY", default=0)
# ── AND HOW MANY SEND BATCHES (DEF-BIL-8726, 2026-10-01) ─────────────────────
# The Send runs in batches of 500 under a coordinator, as the Check does
# (`apps/billing/send_batches.batch_cap`). Its own cap, counted apart from the
# Check's, by the Check's ruled formula: 0 (the default) = max(1,
# BILLING_WORKERS // 2). Set it on a host's `.env` to change it (law 4).
BILLING_SEND_BATCHES_PER_UTILITY = env.int("BILLING_SEND_BATCHES_PER_UTILITY", default=0)

# ── TEST-ONLY OUTAGE SWITCHES (DEF-BIL-8510, `core/walk_switches.py`) ───────
# Empty = off, and off is the default everywhere. A walk names a directory and
# drops `<module>.down` into it to make that module stop answering.
# production.py forbids it outright (law 3: the unsafe option is the one you type).
WALK_SWITCHES_DIR = env("SBH_WALK_SWITCHES_DIR", default="")
WALK_SWITCHES_FORBIDDEN = False

# ── NAMED QUEUES (CR-051 task 29, PO ruling 2026-08-31) ─────────────────────
#
# PO, verbatim: *"we will ahve to create named worker for billing - eventually
# we should able to scale these works on the fly itf required; but billing will
# need its own named workers - otherwise it will slow down the system"*.
#
# ⚠ **WHAT THIS IS FOR, BECAUSE IT IS NOT WHAT IT LOOKS LIKE.** A second queue
# does not create a CPU core, and CR-051 task 27 measured that concurrent bill
# runs never block one another in PostgreSQL — zero ungranted locks across six
# waves. The reason the queue exists is that **a limit can only be aimed at a
# queue that has a name.** Before this, one unrouted queue carried bill runs,
# CSV exports, staged imports and customers' outbound notices through the same
# two worker slots: capping the worker's CPU capped the notices too, and adding
# a worker for billing added one for everything. Task 28 measured the harm a
# clerk feels — the accounts list goes from **605.8 ms to 2,868.9 ms at p95**
# under the two runs `--concurrency 2` can actually execute — and its own
# remedy list put "cap the worker's CPU share" first. This is the routing that
# makes that cap targetable.
#
# ⚠ **A NAMED QUEUE IS TWO HALVES AND SHIPPING ONE IS WORSE THAN SHIPPING
# NEITHER.** The routing below is half; `docker-compose.yml`'s `celery-billing`
# service consuming `-Q billing` is the other. Route without a consumer and a
# bill run is accepted, answers 202 and never runs — `core/jobs.py` names that
# shape in its own words: *"it accepts the file, says 'queued', and writes
# nothing, for ever."* `G59` fails when either half is missing.
#
# The default queue is named EXPLICITLY rather than left to Celery's implicit
# "celery", because `docker-compose.yml` now types `-Q celery` on the default
# worker and a literal in a compose file that matches an implicit default by
# luck is a literal nobody can grep for.
CELERY_TASK_DEFAULT_QUEUE = "celery"

# `task_routes` was configured NOWHERE in this repo until 2026-08-31 — every
# message went to the default queue because nothing said otherwise.
#
# It is a ROUTER FUNCTION and not a name→queue dict on purpose: this deployment
# runs exactly ONE Celery task for every job kind
# (`apps.tenancy.tasks.run_pending_job`, because the RECORD already says what
# kind it is), so a dict keyed on task name cannot tell a bill run from a CSV
# export. The router reads the kind out of the message and asks
# `core.jobs.job_queue()`, which is the registry each owning module fills in its
# own `AppConfig.ready()`. One source of truth, consulted by Celery's own
# routing path — so a test can exercise the real `app.amqp.router` rather than a
# helper of ours that only resembles it.
CELERY_TASK_ROUTES = ("config.celery_routes.route_job",)

# JOBS_EAGER — where a job BODY runs (read at dispatch time by
# apps.tenancy.services.dispatch_job; see core/jobs.py for the whole contract).
#   True  (here, so local/dev/demo inherit it): the job runs in-process the
#         moment it is enqueued. R1 has no broker, and a 202 that never
#         completes is worse than no 202 at all.
#   False (config/settings/production.py, and the test settings): the record
#         rests `queued` until a TD-17 Celery worker runs it. Production MUST
#         keep it False with a broker up — otherwise long money jobs execute
#         inside the web request. (Note for the next revision of
#         09-infra/01-deployment-architecture.md, out of this lane's territory.)
# ── A REFUSAL MUST HAVE A SENTENCE (core/refusal_catalogue.py) ─────────────
# When True, constructing a catalog exception whose `message_key` no catalogue
# defines RAISES instead of returning a refusal a clerk would experience as
# silence. True under `config.settings.test`, which is where a lane meets it —
# their own `pytest`, on their own file, before the branch has the fault.
#
# ⚠ FALSE HERE, AND THAT IS LAW 3 RIGHT WAY ROUND RATHER THAN AN EXCEPTION TO
# IT. Law 3 says the unsafe option must be the one you type; the unsafe
# direction HERE is raising. In production a missing catalogue entry would turn
# a clean 422 refusal into a 500 — the customer loses the refusal they were
# entitled to and gains a fault report they cannot read — and the catalogue is a
# frontend build artefact a backend image need not carry at all. The gate that
# covers production is G32, which reads the source and needs nothing at runtime.
REFUSAL_KEYS_MUST_RESOLVE = env.bool("REFUSAL_KEYS_MUST_RESOLVE", default=False)
# Where the source catalogue lives. Unset means the repo's own
# 07-frontend/src/i18n/locales/en.json, resolved relative to this file.
REFUSAL_CATALOGUE_PATH = env("REFUSAL_CATALOGUE_PATH", default="")

JOBS_EAGER = env.bool("JOBS_EAGER", default=True)

# JOBS_REQUIRE_LIVE_WORKER — DEF-2487. When a stage is about to be handed to the
# queue in front of a person who is waiting for it, ask the workers whether any
# of them is alive (apps.tenancy.services.job_dispatch_ready → Celery's own
# `control.ping`) and REFUSE the upload if none answers.
#   True  (here, so every deployment inherits it — CLAUDE.md law 3, the unsafe
#         option is the one you have to type): a broker with nothing consuming
#         it accepts the file, says "queued", and writes nothing, for ever. That
#         is worse than the visible 500 it would replace.
#   False (config/settings/test.py, and only there): the suite IS its own
#         worker — it enqueues and then calls `core.jobs.run_pending` by hand —
#         so a ping would ask a broker that is deliberately not running and
#         refuse every deferral case in the suite. The cases that prove the
#         refusal turn it back on for themselves.
# Under eager dispatch the probe answers `ready` without touching the network:
# the body runs in this process, so there is nothing to be ready.
JOBS_REQUIRE_LIVE_WORKER = env.bool("JOBS_REQUIRE_LIVE_WORKER", default=True)

# ── App-layer field encryption (OQ-016 CLOSED, B2 §6 · BR-CUS-092) ───────────
# The keys `core/crypto.py` encrypts high-sensitivity columns with. Format:
#
#     <kid>:<base64url 32 bytes>[,<kid>:<key>…]      FIRST ENTRY IS ACTIVE
#
# The active key encrypts every new value; every other entry is decrypt-only,
# which is the whole of the rotation story — put the new key first, leave the old
# one behind it, and no row has to be rewritten to stay readable. The kid is
# stored inside each ciphertext, so a value always says which key made it.
#
# ⚠ THE DEFAULT IS EMPTY, AND EMPTY MEANS REFUSE — NOT PLAINTEXT (hard-won law 3).
# With this unset, `core/crypto.py` raises on every encrypt, decrypt and blind
# index. It never invents a key and never stores the value it was handed.
# `sslmode=disable` and `ALLOWED_HOSTS=localhost` each blocked a live deploy in
# this product because the SAFE option was the default; here the unsafe option is
# not available at all. config/settings/production.py refuses to import without a
# key, so the failure lands at boot with a name rather than at the moment a
# customer types their Social Security Number into a form.
#
# ⚠ EDITING `.env.example` REACHES NO HOST THAT ALREADY HAS A `.env` (law 4). On
# every already-provisioned deployment somebody must add this variable BY HAND
# before the next deploy — the tenancy EIN backfill migration refuses without it.
#   python -c "import base64,os;print('k1:'+base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip('='))"
FIELD_ENCRYPTION_KEYS = env("SBH_FIELD_ENCRYPTION_KEYS", default="")

# Whether a key id beginning `insecure-` may be used. FALSE HERE, AND ONLY
# config/settings/local.py and config/settings/test.py turn it on — that is what
# makes the development key committed in those two files unusable anywhere else.
# "Deploy with the dev key" is therefore not a state this code can be in.
FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS = False

# ── RLS_ALLOW_BYPASSING_ROLE — DEF-2717, and the same two-key shape as the two
# ALLOW flags above, for the same reason (hard-won law 3: the unsafe option is
# the one somebody has to type).
#
# PostgreSQL exempts superusers and BYPASSRLS roles from row-level security
# UNCONDITIONALLY, FORCE ROW LEVEL SECURITY included. On such a connection every
# tenant policy in the schema is skipped and NOTHING REPORTS IT: the tables still
# say relrowsecurity=t and relforcerowsecurity=t, the policies still exist, and
# every query still returns plausible rows. Measured on PostgreSQL 16.13 with the
# B2 §3 policy in place: a NOSUPERUSER NOBYPASSRLS role saw 2 rows, a SUPERUSER
# saw 3 — the third being the OTHER tenant's. That is hard rule 1 failing
# silently.
#
# False here means every settings module REFUSES TO START on such a connection by
# inheritance. `config/settings/local.py` types True, because a developer's local
# role is often a superuser and that is legitimate; reaching it requires
# DJANGO_SETTINGS_MODULE=config.settings.local, which already means DEBUG=True
# and ALLOWED_HOSTS=["*"]. Even then core/rls_guard.py still prints one loud line
# per boot — a tolerated bypass that goes silent is how DEF-2717 happened.
RLS_ALLOW_BYPASSING_ROLE = False

# ⚠ THERE IS NO `JOB_ARTIFACTS_DIR` (removed 2026-10-02, `DEF-MET-4954`). Export
# files — list, report and finance exports, the audit-log export, the bill print
# set — are stored in THIS environment's S3 bucket (`DOCUMENT_STORAGE_BUCKET`
# above) at `t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>`, recorded in the
# `job_artifacts` table and swept daily per utility by celery-beat
# (`apps/tenancy/export_store.py`, `export_sweep.py`). PO, verbatim: *"keep the
# same mechanism everywhere we have dedicated s3 bucket for every env"*. A host
# whose `.env` still sets JOB_ARTIFACTS_DIR keeps a line nothing reads (law 4);
# `tests/test_cr092_registry_paging.py` fails if the setting comes back.

# ── BR-BIL-870 · WHICH RULES OF THE R1–R7 CHAIN PRICE A REAL BILL ──────────
#
# ⚠ **EMPTY MEANS EVERY RULE IS PRICED BY THE CODE THAT PRICES IT TODAY**, and
# empty is the default on every deployment. This is step 5 of the cutover
# recorded in `12-governance/02-decision-log.md`, 2026-08-27 — *"switch one STEP
# at a time, each only when its class is at zero"* — and no class has been ruled
# yet, so nothing is named here and nothing should be.
#
# A space- or comma-separated list of the chain's own step names: R3 R4 R5.
# `apps/billing/resolution_switch.py` REFUSES a name it does not recognise, a
# step it has no fork for, and R3 or R4 named without the other — a switch that
# is accepted and does nothing would be reported as a rule that has been live
# for a week when it never ran once.
#
# It fails CLOSED (hard-won law 3: the unsafe option is the one you type), it is
# reversible at the next restart, and the active set is stamped on every
# gathered account so a bill can say which narrowing produced it.
#
# ⚠ **THIS LINE IS THE EFFECTIVE DEFAULT, AND `resolution_switch
# .SERVED_BY_CHAIN_DEFAULT` IS NOT (`DEF-2922`, found the hour the pair was
# switched on).** That constant is only reached through
# `getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT)`, and this setting is
# ALWAYS defined — so the fallback is unreachable and the constant has never
# decided anything on any deployment. Changing it alone switches nothing on,
# which is hard-won law 2 (*built is not wired*) hiding inside the one file
# whose whole job is the switch. The two literals are pinned equal by
# `test_br_bil_870_resolution_switch.py`, because two sources of one truth is
# how they drift (law 5).
#
# ⚠ **R3 AND R4 ARE ON — THE PO RULED THE PAIR IN ON 2026-09-01 (`CR-057`),
# AND THIS LINE IS WHERE THAT RULING TAKES EFFECT.** PO verbatim: *"Can you wire
# them in now - R3 and R4"* and, after the first flip broke things, *"can you fix
# this probelm and again try to siwthicing - R3 and R4"*.
#
# **WHAT THE FIRST FLIP BROKE — `DEF-2923`.** Seven cases of
# `test_br_bil_870_resolution_switch.py` went red, every one of them real: **a
# tenant that had declared no `is_base` charge code for a service had every
# account of that service REFUSED** on its next bill run, by name, with
# *"Declare a base charge code for 'water' under Charge codes"*. That is
# `BR-RAT-088` behaving exactly as ruled — the charge code is the only source of
# a base amount — meeting a live default for the first time. The three utilities
# the pair was measured on all carry seeded base codes (`DEF-455`), so **the
# measurement could not see that case at all.**
#
# **IT IS CLOSED AT THE CAUSE RATHER THAN WORKED AROUND.** The first answer was
# to keep this empty and serve the ruling per deployment; the PO sent that back,
# and the state was the defect. `rating.services._guard_base_charge_code` now
# consults `steps_served_by_chain()` and REFUSES TO ACTIVATE A SCHEDULE for a
# tenant with no base charge code while R4 is served — so the refusal happens on
# a settings screen, with the fix in its sentence, instead of on the day the
# money is due. No fallback was added and none may be (`BR-BIL-872`).
#
# **BEFORE TRUSTING THIS ON A DEPLOYMENT, run both preflights per utility:**
# `10-scripts/cr052_r1r7_shadow_measure.py --tenant <subdomain>` (does R3 refuse
# anybody, and does every service carry a base charge code) and
# `10-scripts/cr057_r3r4_switch_dry_run.py --tenant <subdomain>` (and is the
# figure the same). Measured 2026-09-01: **3 utilities, 163 accounts, 163
# unchanged, 0 moved, 0 refused.** Both were proved able to print the failing
# verdict, because a check that has only ever printed one answer is not a check.
#
# **ROLLBACK — one line, no release:** `SBH_BILLING_RESOLUTION_STEPS=` (empty)
# and restart. It is re-read on every call, never cached at import, and
# `test_br_rat_120_size_refusal.py::test_TC6b` prices a real bill through the
# rolled-back path so the rollback is tested rather than promised.
BILLING_RESOLUTION_STEPS = env("SBH_BILLING_RESOLUTION_STEPS", default="R3,R4")

# ── THE REQUEST-BODY CEILING, AND WHY IT IS NOT DJANGO'S DEFAULT ────────────
#
# ⚠ **DJANGO'S DEFAULT IS 2.5 MB AND IT WAS THE REAL IMPORT LIMIT — NOT ANY CAP
# WE WROTE (`DEF-MET-5756`, measured 2026-09-18).** An import file arrives as a
# JSON string field, so it is a request BODY, and `DATA_UPLOAD_MAX_MEMORY_SIZE`
# refuses it before one line of our code runs. Measured against
# `rest_framework.request.Request.data` with these settings: **2 MB accepted;
# 3, 8 and 12 MB all `RequestDataTooBig`** — about **25,000 premises rows**.
#
# **Raising `CSV_BYTE_CAP` did not move it by a single row**, and the refusal is
# Django's own: no `trace_id`, no catalogue sentence, nothing the clerk can act
# on. A limit the product does not know it has is worse than a low one it does.
#
# ⚠ **IT IS DERIVED, NOT A SECOND HAND-PICKED NUMBER, BECAUSE TWO CAPS FOR ONE
# IDEA IS THE DEFECT THIS FIXES.** `CR-026` raised the row cap to 100,000 and
# the byte cap stayed at the 3,000-row-era 10 MB, so an operator met a megabyte
# refusal while the product's stated limit counted rows. `import_runs` has since
# derived its byte cap from its row cap for that reason; this derives from that
# byte cap in turn, so all three move together or not at all.
#
# **The 1.5x allowance is the JSON envelope, not slack.** The CSV travels as a
# JSON *string*: quotes, commas and any non-ASCII are escaped, and the payload
# carries the target, the mapping and the run's own fields beside the file. A
# ceiling equal to the CSV size would refuse a file the CSV cap accepts, which
# is the exact bug being fixed, one layer up.
#
# ⚠ **THIS IS A DENIAL-OF-SERVICE SURFACE AND THE NUMBER IS THE MITIGATION.**
# It applies to EVERY endpoint, not only the import: any caller may now post a
# body this large and Django will hold it in memory. That is the cost of taking
# the file through a JSON field, and it is why the number is derived from a cap
# somebody argued for rather than rounded up to something comfortable. The
# durable fix is a streaming multipart upload, which would let this return to a
# small number; it is deferred (PO ruling 2026-09-18, option A before option B)
# and `DEF-MET-5756` records what it would cost.
#
# `SBH_MAX_REQUEST_BODY_BYTES` overrides it for a deployment that knows better.
# Hard-won law 3: the unsafe option is the one you type.
_IMPORT_CSV_BYTE_CAP = 100_000 * 512  # import_runs.CSV_ROW_CAP x CSV_BYTES_PER_ROW_ALLOWANCE
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int(
    "SBH_MAX_REQUEST_BODY_BYTES", default=int(_IMPORT_CSV_BYTE_CAP * 1.5)
)

ROOT_URLCONF = "config.urls"
_db_sslmode = env("DB_SSLMODE", default="require")
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"postgres://authuser:Smart36023@qa-smart360-postgres.cch84ysgqvda.us-east-1.rds.amazonaws.com:5432/smartbillhub?sslmode={_db_sslmode}",
    )
}
# ── ONE TEST DATABASE PER CHECKOUT — A WORKTREE DOES NOT ISOLATE THE DATABASE ──
#
# ⚠ DEF-054, and again on 2026-08-30 at a cost of fifty minutes and no number.
# Two lanes ran the backend suite against the same PostgreSQL at once — one
# without `--reuse-db`, which CREATES AND DROPS the test database, and one with
# it, which depends on that database existing. Neither deadlocked and neither
# finished; the same eleven files run alone take 2m56s. The other face of it is
# louder and reads like a defect in whatever file happens to be executing:
#
#     assert not self._finalizers
#
# — the second run dropped `test_smartbillhub` under the first, so
# `django_db_setup` failed mid-session and every test in the running file
# errored in fixture setup. `tests/golden/test_gt16_opening_journal_entry.py`
# carries that diagnosis in its own header because a lane that believes the
# error is its own will revert correct code to make it go away.
#
# **A `git worktree` isolates the FILES and shares the REFS — and it shares the
# DATABASE with everything else on the machine, which is one level worse.**
# `check_head_current.sh`'s header records the refs half of exactly this lesson.
#
# ⚠ THE OLD MITIGATION WAS A SENTENCE IN A README, AND THAT IS THE BUG. Three
# documents told lanes to "point DATABASE_URL wherever you like" — which is an
# environment variable nobody sets, so the SHARED name was what you got by
# typing nothing. Hard-won law 3 says the unsafe option must be the one you
# type. Now it is: with nothing set, each checkout gets its own name, derived
# from its own path.
#
#   * `test_sbh_smartbillhub_<hash>` in the main checkout;
#   * `test_sbh_agent_a10dce0b7306_<hash>` in a lane's worktree;
#   * the SAME name every run from the same directory, so `--reuse-db` still
#     reuses and costs nothing;
#   * `SBH_TEST_DB_NAME=test_smartbillhub` to go back to a shared database
#     deliberately, which is now something a person types on purpose.
#
# ⚠ WHAT THIS DOES NOT CHANGE, checked before it landed: `pytest` defaults to
# `config.settings.test`, which HARDCODES in-memory SQLite and ignores
# `DATABASE_URL` entirely (CLAUDE.md law 14) — so `ci-backend.yml`'s `pytest -q`
# is untouched. No workflow runs pytest under these settings: the Postgres steps
# in `ci-backend.yml` and `qa.yml` are `manage.py migrate` and a booted stack
# against explicitly-named databases (`sbh_ci`, `sbh_e2e`), and Django's TEST
# name is read only when a test database is CREATED. This is inert everywhere
# except a lane running pytest against real PostgreSQL, which is the one place
# it is needed.
#
# The first run after this lands re-creates the database under its new name and
# pays a full migrate once; every run after that reuses it.
#
# To see the name your checkout will use:
#   python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.local');django.setup();from django.conf import settings;print(settings.DATABASES['default']['TEST']['NAME'])"
_checkout = str(BASE_DIR.resolve())
_slug = re.sub(r"[^a-z0-9]+", "_", BASE_DIR.parent.name.lower()).strip("_")[:20] or "sbh"
_lane = hashlib.sha256(_checkout.encode("utf-8")).hexdigest()[:8]
DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"]["NAME"] = env("SBH_TEST_DB_NAME", default=f"test_sbh_{_slug}_{_lane}")

# ── The customer portal's own budget (NFR-38–41, PO ruling 2026-09-03) ────────
# *"there can be 500 users or 100 users from various tulities using customer
# portal … it should not hamper performance of back office user"*. The portal is
# isolated from the staff app at three named places (NFR-39); the two that are
# SETTINGS live here, so a deployment moves them without a code change. The
# third — the portal's own queue and worker — arrives with the portal's first
# job kind (wave E: the one-time code by email), routed through
# `core.jobs.set_job_queue` in the portal's `AppConfig.ready()` and consumed by a
# `celery-portal` service, both halves in ONE commit (G59 refuses either alone).
# Wave A creates no job kind, so wave A declares no queue: a route with no
# consumer accepts work and never runs it (DEF-320).
#
# PORTAL_TENANT_RATE — requests a minute ONE UTILITY's visitors may make in
#   total, beside the sixty a minute each ADDRESS may make (BR-CWP-022). A
#   DEFAULT, stated as one: ten times the per-address rate, on the reasoning
#   that a utility of three thousand connections with a busy afternoon is a
#   few hundred people making one or two requests each. Read by
#   `apps.portal.guards.PortalTenantThrottle`.
# PORTAL_INFLIGHT_MAX — how many portal requests may be IN FLIGHT at once across
#   the deployment. This deployment runs gunicorn with SYNC workers and no
#   connection pool (`docker-entrypoint.sh`: GUNICORN_WORKERS, default 3), so
#   "the pool the staff app draws from" IS the worker count, and the budget
#   is one less than it: one worker is always free for a clerk. Read by
#   `apps.portal.guards.portal_admission`; over budget answers 429 +
#   Retry-After: 1 before the first query.
# ⚠ Neither figure is the response time the ruling refers to — none is
#   recorded anywhere (`OQ-CWP-1510`, OPEN); the portal builds to that
#   question's PROPOSAL and never quotes a number as agreed.
PORTAL_TENANT_RATE = env("PORTAL_TENANT_RATE", default="600/min")
PORTAL_INFLIGHT_MAX = env.int(
    "PORTAL_INFLIGHT_MAX", default=max(1, env.int("GUNICORN_WORKERS", default=3) - 1)
)

# ── PORTAL_CLOCK_OVERRIDE — a demo clock, and it FAILS CLOSED ────────────────
# CR-068 wave D (2026-09-04). A service centre's *"Closed today · Opens
# Thursday at 9:00am"* and *"Closed 26 November — Thanksgiving"* are computed
# from the clock and the tenant's holiday calendar and typed by nobody
# (BR-CWP-096) — which is the whole point of the rule and also means the two
# sentences can only be SEEN on a Wednesday in November. The walkthrough has to
# be able to stand on that day.
#
# ⚠ **IT IS HONOURED ONLY WHEN `DEBUG` IS TRUE** (see
# `apps.tenancy.published_content._tenant_now`). `DEBUG` is False in this file
# and in `production.py`; only `local.py` turns it on. So on any deployed build
# this variable can be set, exported, or left in a `.env` by accident and a
# customer's opening hours still come from the real clock — the unsafe option
# is the one you have to type, twice (hard-won law 3), and a template change
# never reaches a host that already has a `.env` (law 4), which is exactly why
# the guard is in the CODE and not in the default.
#
# Format: an ISO date or datetime, e.g. `2026-11-18` or `2026-11-18T14:00:00`.
# Unset (the default) means the real clock, which is what every environment
# uses.
PORTAL_CLOCK_OVERRIDE = env("PORTAL_CLOCK_OVERRIDE", default=None) or None

# ── The default cache — SHARED when Redis is there, per-process otherwise ─────
# Django's default is a per-process in-memory cache. Every rate limit in this
# product counts in it (`PublicOnboardingThrottle`, and now the portal's two
# guards), so with three gunicorn workers a "sixty a minute" limit has been
# one-hundred-and-eighty a minute in production, silently, since the day it was
# written. The portal's connection budget cannot be per-process at all — a sync
# worker never holds more than one request, so a per-process count never
# refuses anything. When a Redis URL is configured the cache moves there, on a
# different database index from Celery's broker so a FLUSHDB on one cannot
# touch the other; test settings and a bare local run keep the in-memory cache,
# and `apps/portal/guards.py` states the difference.
_cache_url = env("CACHE_URL", default=None)
if _cache_url:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": _cache_url}}

# ── The partner call limit's counter MUST be shared, unless you say otherwise ─
#
# `CR-110-BRC04`, PO 2026-09-16: *"this is important - we need to inlcude speed
# limit - otherwise if somone hack we will not have a control"*, and *"you can
# have shared counter"*.
#
# The limit on our inbound partner APIs was counted in a module-level dict, so
# with `GUNICORN_WORKERS` sync workers (default 3) a ceiling written as 100 a
# minute was **300 a minute**, silently, since the day it was written. The
# counter now lives in the default cache above, which is shared when
# `CACHE_URL` is set and PRIVATE TO ONE PROCESS when it is not.
#
# ⚠ **TRUE HERE, AND THE CONSEQUENCE IS THAT A DEPLOYMENT WITH NO `CACHE_URL`
# REFUSES PARTNER TRAFFIC RATHER THAN METERING IT PER PROCESS.** That is
# hard-won law 3 — `sslmode=disable` and `ALLOWED_HOSTS=localhost` each blocked
# a live deploy, and the unsafe option must be the one you type. Turning this
# off is a sentence somebody writes on purpose, in `test.py` and in a local
# run, and never something a missing environment variable does for them.
#
# ⚠ **AND hard-won law 4: EDITING THIS FILE REACHES NO HOST THAT ALREADY HAS A
# `.env`.** A box deployed before today has no `CACHE_URL` and will not get one
# from this commit; it has to be given one by hand, or this set to False by
# hand, before its partner routes answer anything but `429`.
INTEGRATION_SHARED_COUNTER_REQUIRED = env.bool(
    "INTEGRATION_SHARED_COUNTER_REQUIRED", default=True
)

# ── The application rate limits A1–A4 (DEF-SHL-10621, PO 2026-10-27) ─────────
# Per minute; DevOps tunes them on the task definition without a release
# (09-infra/06-vapt-remediation-2026-10.md §2). ON unless someone types OFF
# (hard-won law 3); `test.py` turns them off and the throttle tests turn them
# back on for themselves. ⚠ Counted in the default cache: shared across ECS
# tasks ONLY when `CACHE_URL` is set (see above) — otherwise per process.
APP_RATE_LIMITS_ENABLED = env.bool("APP_RATE_LIMITS_ENABLED", default=True)
RATE_USER_PER_MIN = env.int("RATE_USER_PER_MIN", default=300)
RATE_TENANT_PER_MIN = env.int("RATE_TENANT_PER_MIN", default=3000)
RATE_HEAVY_PER_MIN = env.int("RATE_HEAVY_PER_MIN", default=10)
RATE_DEVICE_PER_MIN = env.int("RATE_DEVICE_PER_MIN", default=120)
DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"  # B2 uses uuidv7 PKs per-model; explicit on each model.
)
USE_TZ = True  # storage is UTC (B2); display per tenant Regional settings
TIME_ZONE = "UTC"

# ── LOGGING — an unhandled exception must reach the container log ────────────
#
# ⚠ ADDED 2026-08-27 FROM A LIVE INCIDENT (DEF-1080). The Product Owner hit
# `HTTP 500` on the asset import and NOBODY COULD SAY WHY — not because the
# traceback was hard to find, but because **it was never written anywhere.**
#
# WHY IT VANISHED, precisely, because "add logging" is not the lesson:
# this project defined no `LOGGING` at all, so Django's own DEFAULT_LOGGING
# applied. That default attaches two handlers to the `django` logger — a
# `console` handler filtered by `require_debug_true`, and `mail_admins`
# filtered by `require_debug_false`. Under `DEBUG=False`:
#
#   * `console` is REJECTED BY ITS OWN FILTER — nothing is printed;
#   * `mail_admins` passes the filter and mails `ADMINS`, which this project
#     never sets — so it mails nobody;
#   * and `logging.lastResort` (the stderr fallback) does NOT fire, because it
#     only applies when a record finds NO handler at all. Here a handler was
#     found and then declined, which counts as handled.
#
# So every 500 in production was silently discarded, by three mechanisms at
# once, and the only trace left was gunicorn's access line: the URL, the
# timestamp and `500`, with no exception and no line number. Django catches the
# exception itself and returns a response, so it never escapes to gunicorn —
# which is why gunicorn's `--error-logfile -` did not save us either.
#
# THE FIX IS DELIBERATELY BORING: one stream handler, no filters, on the
# loggers that matter. `docker-entrypoint.sh` already runs gunicorn with
# `--access-logfile -` and `--error-logfile -`, so stderr IS the container log
# and `docker compose logs backend` is where this lands. Nothing new to deploy
# or configure.
#
# ⚠ HARD-WON LAW 4 DOES **NOT** APPLY TO THIS ONE, AND THAT IS WHY IT IS HERE
# RATHER THAN IN `.env.example`: this is a settings module, shipped in the
# image, so it reaches every host on its next deploy WITHOUT anyone editing a
# `.env` by hand. A logging level knob in the environment would have had
# exactly the law-4 problem — the hosts already running would never get it.
# `SBH_LOG_LEVEL` below only TUNES what is already on.
LOGGING = {
    "version": 1,
    # Never disable Django's own loggers — this dict adds to them, and a
    # `True` here silently mutes any logger defined before settings load.
    "disable_existing_loggers": False,
    "formatters": {
        "sbh": {
            # Timestamp first so a log line can be matched to the minute a user
            # reports — which is the whole point of DEF-1080.
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        # NO `filters` key. That is the entire bug above: the default console
        # handler carried `require_debug_true` and therefore did nothing in the
        # only environment where it mattered.
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "sbh",
        },
    },
    "loggers": {
        # THE ONE THAT MATTERS: Django logs every unhandled exception here at
        # ERROR with `exc_info`, so this is the line that carries the traceback.
        # `propagate: False` stops it reaching `django` and being handled twice.
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": env("SBH_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        # This project's own `getLogger(__name__)` calls all live under `apps.`.
        "apps": {
            "handlers": ["console"],
            "level": env("SBH_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        # ⛔ **AND UNDER `core.`, WHICH THIS DICT LEFT OUT (`DEF-2161`).**
        # `core/errors.py` is where every refusal in the product is logged with
        # the trace id a person reads off their screen — `logger.info("refused
        # %s (code=%s trace_id=%s)")` for 401/403/404/409/422/429. With no
        # `core` logger those records fell through to the ROOT logger, which
        # has no handler, and `logging.lastResort` only prints at WARNING and
        # above. So the INFO lines were dropped in production by exactly the
        # mechanism the block above was written to fix, one package along:
        # **support could be handed a reference with no log line behind it.**
        # `logger.exception` at ERROR did survive, which is why nobody noticed.
        "core": {
            "handlers": ["console"],
            "level": env("SBH_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        # ⛔ **AND UNDER `smartbillhub.`, THE SAME HOLE A THIRD TIME
        # (`DEF-TEN-9190`).** The job runner, the export store and the export
        # sweep all log to `smartbillhub.*`. A celery worker hijacks the root
        # logger so those lines DID print there; the WEB process has no root
        # handler, so an export download refused for a job that "succeeded"
        # with no stored file was logged into nothing.
        "smartbillhub": {
            "handlers": ["console"],
            "level": env("SBH_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}

# ── CR-169-BRC10 · PRODUCT ANALYTICS (PostHog), SERVER SIDE ──────────────────
# All four come from the environment, per deployed environment, and none is
# committed. EMPTY KEY = ANALYTICS OFF (hard-won law 3): local, compose and the
# test suite send nothing. `POSTHOG_ENVIRONMENT` is `dev` | `sandbox` |
# `production` and is REQUIRED when a key is set — without it the server sends
# nothing. `POSTHOG_PROD_KEY_FINGERPRINT` (the first 16 hex characters of the
# SHA-256 of the PRODUCTION key) makes a dev or sandbox server that was handed
# the production key refuse to send. `config/product_analytics.py` reads them.
POSTHOG_KEY = env("POSTHOG_KEY", default="")
POSTHOG_HOST = env("POSTHOG_HOST", default="https://us.i.posthog.com")
POSTHOG_ENVIRONMENT = env("POSTHOG_ENVIRONMENT", default="")
POSTHOG_PROD_KEY_FINGERPRINT = env("POSTHOG_PROD_KEY_FINGERPRINT", default="")

# ── CR-187-BRC10 · THE NATIVE FIELD APP'S MINIMUM VERSION (DEF-FLD-10355) ────
# A field-app build whose `X-Field-App-Version` is BELOW this is answered 426
# `app_too_old` on the field routes (`core/field_app_version.py`) and shows
# *Update the app*. PLATFORM-WIDE, never per tenant: a binary is the same at
# every utility. DEFAULT `0.0.0` REFUSES NOTHING — raising it is the act that
# stops a bad installed build (15-release-and-rollback.md §5.2). ⚠ A change to
# `.env.example` never reaches a host that already has a `.env` (law 4): set it
# in the deployed environment itself.
FIELD_APP_MIN_VERSION = env("FIELD_APP_MIN_VERSION", default="0.0.0")

# ── DEF-FLD-10580 · THE UTILITY-FREE ACTIVATION LOOKUP'S LIMIT ──────────────
# `POST /api/auth/activation/lookup` — the field app's first call, which turns
# the office's six-character code into the utility that holds it. PO
# 2026-10-24: PLATFORM-WIDE, because no utility's Settings › Security can
# apply before the code has named the utility. Counted per network address AND
# per device id (`identity.api.ActivationLookup*Throttle`). Seed 10 tries per
# 15 minutes. Once the code names the utility, wrong emails follow THAT
# utility's lockout count (`native.activation_max_failed`). ⚠ A change to
# `.env.example` never reaches a host that already has a `.env` (law 4).
ACTIVATION_LOOKUP_MAX_TRIES = env.int("ACTIVATION_LOOKUP_MAX_TRIES", default=10)
ACTIVATION_LOOKUP_WINDOW_S = env.int("ACTIVATION_LOOKUP_WINDOW_S", default=15 * 60)

# ── OQ-FLD-12797 · THE FIELD APP'S DEFAULT CERTIFICATE PINS ─────────────────
# PO 2026-10-24: *"Trust the certificate issuer's key plus one backup issuer
# … plese dont hardcode it use settings - security values set in staff
# portal"*. Each utility's own list lives on its Settings › Security
# (`security_policies.field_app_pins`); THIS is what a utility that has never
# edited that list is served, and the starting list the card offers to edit.
# PLATFORM-WIDE because every utility is reached through one server
# certificate. A JSON list of {spki_sha256, label, not_after}.
# The documented default: ISRG Root X1 (Let's Encrypt — the current issuer)
# plus GTS Root R1 (Google Trust Services — a DIFFERENT authority, the backup
# the server can move to without stranding a phone). Both hashes computed
# 2026-10-24 from the system trust store (SHA-256 of the DER
# SubjectPublicKeyInfo, base64). The field app's `app.json` `extra.pins` carries
# the same two. ⚠ Before the first store build, confirm the deployed host's
# chain ends in one of these; set `SBH_FIELD_APP_DEFAULT_PINS` if it does not.
# ⚠ A change to `.env.example` never reaches a host that already has a `.env`
# (law 4). Malformed JSON fails the process at start (law 3), never silently.
# ── CR-195-BRC10 · WHETHER THE FIELD APP PINS AT ALL — OFF ───────────────────
# PO 2026-10-28, *"start A1"*: certificate pinning is NOT a go-live
# requirement. No field-app build pins (`FIELD_APP_PINNING` off in both EAS
# profiles); the phone relies on Android's standard certificate validation.
# This one PLATFORM flag says so to the staff portal: false hides the
# Settings › Security *Field app certificates* card (a control that would do
# nothing). The lists below, the card's endpoint and the phone's settings
# answer stay, so `SBH_FIELD_APP_PINNING_ENABLED=true` brings the card back
# the day a build is switched on — set both together. ⚠ A change to
# `.env.example` never reaches a host that already has a `.env` (law 4).
FIELD_APP_PINNING_ENABLED = env.bool("SBH_FIELD_APP_PINNING_ENABLED", default=False)

FIELD_APP_DEFAULT_PINS = json.loads(
    env(
        "SBH_FIELD_APP_DEFAULT_PINS",
        default=(
            '[{"spki_sha256": "C5+lpZ7tcVwmwQIMcRtPbsQtWLABXhQzejna0wHFr8M=",'
            ' "label": "ISRG Root X1", "not_after": "2035-06-04"},'
            ' {"spki_sha256": "hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc=",'
            ' "label": "GTS Root R1", "not_after": "2036-06-22"}]'
        ),
    )
)
