#!/usr/bin/env bash
# ── 11-smoke-stack.sh ────────────────────────────────────────────────────────
#
# Boot the WHOLE product on one machine and drive it through a browser —
# migrate → seed_demo → backend → SPA → 10-scripts/12-smoke-walkthrough.mjs —
# then tear it down. This is the check that found DEF-528/529/530/531/532 in
# one afternoon when every unit test, gate and typecheck was green.
#
# WHEN TO RUN IT: before any push that touches a screen, and after fixing any
# defect whose escape_reason names DEF-523 (no DOM test environment). See the
# header of 12-smoke-walkthrough.mjs for what the walkthrough itself checks.
#
# ASSUMPTIONS — each is CHECKED below and fails with a named reason:
#   1. Postgres is reachable via DATABASE_URL. Default is config/settings/base.py's
#      own default (postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub).
#      The database must exist; migrate creates the schema, seed_demo the tenant.
#   2. The backend's Python deps are importable (django et al) — run from the
#      environment 06-backend runs in.
#   3. 07-frontend/node_modules is installed (npm install has run).
#   4. A playwright chromium exists (PLAYWRIGHT_BROWSERS_PATH or /opt/pw-browsers);
#      12-smoke-walkthrough.mjs resolves it and names what is missing if not.
#   5. Ports 8000 (API) and 8080 (SPA join) are free, or override via env.
#
# SHAPE OF THE STACK — deliberately the DEPLOYED shape, not the dev shape:
#   * Django runserver on 127.0.0.1:8000 (config.settings.local).
#   * `npx vite build --mode compose` → dist, served by 07-frontend/server.mjs
#     on :8080 with API_PROXY_TARGET pointing at the backend. server.mjs IS the
#     production join (same-origin SPA + /api pass-through); the vite dev server
#     has no /api proxy configured at all, so it CANNOT serve this app
#     same-origin — and DEF-532 was found on the deployed join, which is the one
#     worth smoking. `vite build` is run WITHOUT the `npm run build` tsc gate:
#     the typecheck belongs to the push path and is run there; the smoke stack
#     must still boot while a sibling lane's in-flight edit has red types.
#
# ⚠ **`--mode compose` IS LOAD-BEARING AND A BARE `npx vite build` BREAKS
# SIGN-IN (`DEF-INF-7802`, 2026-09-28, after biting THREE lanes).**
#
# ⚠ **IT IS THE SECOND OCCURRENCE OF `DEF-DEP-7460`, AND THAT IS THE LESSON.**
# That defect found this exact fault in `07-frontend/Dockerfile` and fixed it
# THERE, in one caller, with three paragraphs of correct reasoning attached to
# `RUN npm run build`. **Nothing walked the other callers.** There were two —
# this file and `08-qa/01-e2e/stack/boot_stack.sh` — and both went on building
# a production bundle for a localhost stack. A fix applied to the caller it was
# found in is not a fix of the cause; it is a fix of one symptom, and the repo
# has a name for the shape (CLAUDE.md, the `CorrectionRetentionNote` case:
# *"the propagation list missed the one surface a clerk could see"*).
#
# Vite
# defaults an unflagged `build` to mode `production`, so it reads
# `07-frontend/.env.production` and **bakes `https://api-smart360.bynry.com`
# into the bundle** — both as `client.ts`'s base URL (`vite.config.ts`'s
# `define`) and inside the `<meta http-equiv="Content-Security-Policy">` tag
# that `pagePolicyPlugin` writes into `index.html`. Served from 127.0.0.1 that
# bundle does not call this stack at all: it calls the real deployed API over
# the internet, and the clerk sees **"That email or password is incorrect."**
# on correct credentials — a refusal sentence about the one thing that is not
# wrong.
#
# ⚠ **AND THE POLICY THAT BLOCKS IT IS NOT THE ONE IN THE PAGE, WHICH IS WHY
# READING THE META TAG ALONE CLEARS THE WRONG SUSPECT.** The meta tag actually
# ALLOWS the remote host — `pagePolicyPlugin` adds the API origin to
# `connect-src`, so it reads `connect-src 'self' https://api-smart360.bynry.com`
# and looks innocent. But `server.mjs` ALSO sends a `content-security-policy`
# RESPONSE HEADER, and its `BASE_POLICY` is the same-origin one:
# `connect-src 'self'`, with no remote host in it. **A browser enforces every
# policy it is given independently, so the effective permission is the
# INTERSECTION** — `'self'` — and the fetch is refused with
# *"Refused to connect to https://api-smart360.bynry.com/… because it violates
# connect-src self"*, naming the HEADER's directive. `vite.config.ts` states the
# intersection rule in its own comment; this is that rule biting from the other
# side. So the two halves are each correct alone and only the PAIR is wrong,
# which is why no single file reads as broken.
#
# `compose` is deliberately NOT in `scripts/deployConfig.mjs`'s `DEPLOYED_MODES`,
# so `resolveApiBaseUrl` returns `""`, `policyWithApiOrigin` returns the base
# policy unchanged, and every call goes same-origin through server.mjs — which
# is the only shape this stack can serve. It is the same mode
# `npm run build:bundle` uses, so the smoke stack and the container image build
# one bundle rather than two.
#
# ⚠ **AND THE WRONG BUNDLE HID BEHIND THE REUSE BELOW FOR AS LONG AS IT DID
# BECAUSE `dist` IS ONLY REBUILT WHEN IT IS MISSING.** A tree that had built
# once before the deployment change went on serving pre-change bytes, so the
# defect was invisible to every run that did not start from an empty `dist`.
# Fixing the mode alone would have left that trap loaded for the next
# deployment change, so the reuse is now GUARDED: an existing `dist` that
# carries a deployed API origin is rebuilt rather than served (hard-won law 7 —
# a check whose scope silently excludes the failing case is worse than none).
#
# ENV:
#   DATABASE_URL       see above ·  SMOKE_API_PORT (8000) · SMOKE_WEB_PORT (8080)
#   SMOKE_SKIP_SEED=1  reuse an already-seeded database (seed_demo is not
#                      re-entrant on every path, and DEF-528 — seed dies on a
#                      multi-service tenant — is OPEN as this is written)
#   SMOKE_REBUILD=1    rebuild dist even if it exists
#   SMOKE_TENANT / SMOKE_EMAIL / SMOKE_PASSWORD / SMOKE_OUT — passed through to
#                      the walkthrough (defaults are seed_demo's brazosbend owner)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO/06-backend"
FRONTEND="$REPO/07-frontend"
API_PORT="${SMOKE_API_PORT:-8000}"
WEB_PORT="${SMOKE_WEB_PORT:-8080}"
OUT="${SMOKE_OUT:-${TMPDIR:-/tmp}/smartbillhub-smoke-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"

die() { echo "SMOKE STACK REFUSED: $*" >&2; exit 2; }

# ── assumption checks, each with its name ────────────────────────────────────
#
# ⚠ **THE INTERPRETER IS RESOLVED, NOT ASSUMED (`DEF-GOV-4299`, 2026-09-06).**
# This block used to run `python3 -c "import django"` and refuse when it failed.
# On a box carrying TWO interpreters — a `python3` that is 3.11 without Django
# and a `python3.12` that has it — that refusal is TRUE of the name and FALSE of
# the machine, and its message ("django is not importable — install the deps")
# points at the wrong repair.
#
# **It cost three build lanes their walkthrough on one day.** Each correctly
# reported "I could not boot the stack", none of them was right about why, and
# the Product Owner's own definition of done — *"ensure you do web walkthorugh
# before you sign off"* — silently became an honest deferral, wave after wave.
# No gate runs this script, so nothing in CI has ever executed its preconditions.
#
# So: try the override, then `python3`, then every `python3.N` on PATH, and take
# the first that can actually import Django. **The chosen one is PRINTED**, because
# a script that silently picks a different interpreter than the operator expects is
# the next version of this defect.
resolve_python() {
  local candidate
  for candidate in ${PYTHON:-} python3 $(compgen -c 'python3.' 2>/dev/null | sort -Vu); do
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c "import django" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(resolve_python)" || die \
  "no interpreter on PATH can import django — tried ${PYTHON:+$PYTHON, }python3 and every python3.N.
   Install 06-backend's deps, or set PYTHON=/path/to/python (assumption 2)"
echo "── python : $PYTHON ($("$PYTHON" --version 2>&1), django $("$PYTHON" -c 'import django;print(django.get_version())'))"
[ -d "$FRONTEND/node_modules" ] \
  || die "07-frontend/node_modules is missing — run: npm install --prefix 07-frontend (assumption 3)"

export DATABASE_URL="${DATABASE_URL:-postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub}"
if command -v pg_isready >/dev/null; then
  pg_isready -d "$DATABASE_URL" -q \
    || die "Postgres is not reachable via DATABASE_URL=$DATABASE_URL (assumption 1)"
fi

for port in "$API_PORT" "$WEB_PORT"; do
  if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$port/"; then
    die "port $port is already serving something — stop it or set SMOKE_API_PORT/SMOKE_WEB_PORT (assumption 5)"
  fi
done

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"

# ── teardown: always, even on failure ────────────────────────────────────────
PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

# ── migrate + seed ───────────────────────────────────────────────────────────
echo "── migrate"
(cd "$BACKEND" && "$PYTHON" manage.py migrate --noinput) >"$OUT/migrate.log" 2>&1 \
  || die "migrate failed — see $OUT/migrate.log"

if [ "${SMOKE_SKIP_SEED:-0}" != "1" ]; then
  echo "── seed_demo"
  (cd "$BACKEND" && "$PYTHON" manage.py seed_demo) >"$OUT/seed.log" 2>&1 || die \
    "seed_demo failed — see $OUT/seed.log. If it died at 'rate schedules', that is
    DEF-528 (the BR-RAT-088 base-charge guard vs a one-base-code seed), which is
    OPEN. If the tenant already exists from an earlier run, re-run with
    SMOKE_SKIP_SEED=1."
else
  echo "── seed_demo skipped (SMOKE_SKIP_SEED=1)"
fi

# ── backend ──────────────────────────────────────────────────────────────────
echo "── backend on :$API_PORT"
(cd "$BACKEND" && exec "$PYTHON" manage.py runserver "127.0.0.1:$API_PORT" --noreload) \
  >"$OUT/backend.log" 2>&1 &
PIDS+=($!)

# ── SPA: build once, serve through the production join ───────────────────────
#
# ⚠ THE REUSE IS GUARDED (DEF-INF-7802). An existing `dist` is only trusted when
# it is a SAME-ORIGIN bundle. `dist_calls_a_deployed_api` greps the built files
# for the three deployed API origins; a hit means this tree's `dist` predates
# the mode fix (or was left by `npm run build:prod`), and serving it would
# reproduce the defect silently. It is the cheap half of
# `07-frontend/scripts/checkBundleHost.mjs`, asked in the one direction that
# script cannot answer — it throws for any mode outside DEPLOYED_MODES, and
# `compose` is outside it on purpose.
dist_calls_a_deployed_api() {
  [ -d "$FRONTEND/dist" ] || return 1
  grep -rqlE 'https://api-smart360(-dev|-sandbox)?\.bynry\.com' \
    --include='*.js' --include='*.html' --include='*.css' "$FRONTEND/dist" 2>/dev/null
}

REBUILD_WHY=""
if [ ! -d "$FRONTEND/dist" ]; then
  REBUILD_WHY="no dist"
elif [ "${SMOKE_REBUILD:-0}" = "1" ]; then
  REBUILD_WHY="SMOKE_REBUILD=1"
elif dist_calls_a_deployed_api; then
  REBUILD_WHY="the existing dist names a DEPLOYED API origin, so it was not built --mode compose (DEF-INF-7802)"
fi

if [ -n "$REBUILD_WHY" ]; then
  echo "── vite build --mode compose ($REBUILD_WHY)"
  (cd "$FRONTEND" && npx vite build --mode compose) >"$OUT/vite-build.log" 2>&1 \
    || die "vite build failed — see $OUT/vite-build.log"
  if dist_calls_a_deployed_api; then
    die "the bundle STILL names a deployed API origin after --mode compose —
    a same-origin build must bake none. Check 07-frontend/.env and
    07-frontend/.env.compose (neither should set VITE_API_BASE_URL) and
    07-frontend/scripts/deployConfig.mjs's DEPLOYED_MODES."
  fi
else
  echo "── vite build skipped (dist exists and is same-origin)"
fi
echo "── server.mjs on :$WEB_PORT (proxying /api → 127.0.0.1:$API_PORT)"
(cd "$FRONTEND" && PORT="$WEB_PORT" API_PROXY_TARGET="http://127.0.0.1:$API_PORT" \
  exec node server.mjs) >"$OUT/web.log" 2>&1 &
PIDS+=($!)

# ── readiness: poll, never sleep-and-hope ────────────────────────────────────
wait_for() { # url · name · logfile
  for _ in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$1" || true)
    [ "$code" != "000" ] && return 0
    sleep 1
  done
  die "$2 never answered at $1 — see $3"
}
wait_for "http://127.0.0.1:$API_PORT/api/public/pricing-plans" "backend" "$OUT/backend.log"
wait_for "http://127.0.0.1:$WEB_PORT/" "SPA server" "$OUT/web.log"

# ── the walkthrough itself ───────────────────────────────────────────────────
echo "── walkthrough"
status=0
SMOKE_BASE="http://127.0.0.1:$WEB_PORT" SMOKE_OUT="$OUT" \
  node "$REPO/10-scripts/12-smoke-walkthrough.mjs" || status=$?
echo "logs and screenshots: $OUT"
exit $status
