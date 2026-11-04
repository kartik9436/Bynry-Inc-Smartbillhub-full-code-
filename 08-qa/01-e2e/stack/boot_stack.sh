#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Component: E2E stack bring-up — Postgres + Django + the BUILT frontend, on
#            ONE origin, seeded, ready for a browser to click.
# Defect:   DEF-057 (2026-08-11) — *"nothing in CI starts an app server, so no
#           journey can run anywhere"*. PO ruling the same day: **"we ahve to
#           prove against human clicking"**.
# Rules:    CLAUDE.md hard-won law 3 (defaults fail closed) · law 4 (a template
#           change never reaches a host that already has a `.env`) · DEF-054
#           (every lane gets a database of its own — a shared test database is
#           how one lane's run silently kills another's)
# Impacts:  .github/workflows/qa.yml · 07-frontend/e2e/*.spec.ts (this is what
#           E2E_BASE_URL points at) · nothing in 06-backend/apps/**
# ───────────────────────────────────────────────────────
#
# WHAT THIS IS AND IS NOT
#
# It is NOT a second deployment design. `docker-compose.yml` at the repo root is
# the application's real shape — two containers, one published port, an EXTERNAL
# Postgres — and it stays the reference. This script is the same shape without
# Docker: it is what a CI runner and a sandbox can actually execute, because
# both already have Python, Node and a Postgres they can reach, and neither
# reliably has a Docker daemon or the network to build two images.
#
# The ONE PROPERTY that must not be lost either way is SAME ORIGIN. The session
# cookie is httpOnly and host-scoped, so the SPA and `/api/*` must answer on one
# address or nothing can sign in. Compose gets that from the frontend container
# proxying `/api/*` to `backend:8000` (07-frontend/server.mjs); this script runs
# that same `server.mjs` against a local Django. Same file, same pass-through,
# same origin.
#
#   ./08-qa/01-e2e/stack/boot_stack.sh          bring it up (idempotent)
#   ./08-qa/01-e2e/stack/boot_stack.sh --stop   take it down
#
# It prints the base URL to give Playwright and exits non-zero the moment any
# step fails — a half-booted stack that reports success is the thing this whole
# lane exists to stop.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"
BACKEND="${REPO_ROOT}/06-backend"
FRONTEND="${REPO_ROOT}/07-frontend"
RUN_DIR="${E2E_RUN_DIR:-/tmp/sbh-e2e-stack}"

# ── Configuration, every value overridable, every default explicit ──────────
#
# DEF-054: the database name carries the LANE, so two concurrent runs cannot
# drop each other's data. Override DATABASE_URL wholesale to point somewhere
# else (an RDS, a compose Postgres, a CI service container).
E2E_DB_NAME="${E2E_DB_NAME:-sbh_e2e}"
DATABASE_URL="${DATABASE_URL:-postgres://smartbillhub:smartbillhub@localhost:5432/${E2E_DB_NAME}}"
# `local`, not `production`: this stack is DEBUG with ALLOWED_HOSTS=["*"] and
# serves a fixture tenant with a published password. Naming it here rather than
# inheriting it means a stray production `.env` on the host cannot change what
# this boots (hard-won law 4).
DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.local}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
WEB_PORT="${E2E_WEB_PORT:-8080}"
BASE_URL="http://127.0.0.1:${WEB_PORT}"

export DATABASE_URL DJANGO_SETTINGS_MODULE

say() { printf '\n── %s\n' "$1"; }
die() { printf '\nboot_stack: FAILED — %s\n' "$1" >&2; exit 1; }

# ⚠ `exec` in the launch blocks below is LOAD-BEARING, and this function is why.
# The first version backgrounded `cd … && nohup python3 …`, so `$!` was the
# SUBSHELL's pid and the server ran one pid higher. `--stop` then killed the
# wrapper, printed "stopped backend (pid 13903)", and left the server serving on
# 13904 — a stop that reports success and does not stop. Exactly the defect
# class this whole lane exists to remove, produced by this lane, caught by
# checking rather than by trusting the message. So: `exec` makes the recorded
# pid the server's own pid, and this function VERIFIES the port is free
# afterwards instead of taking `kill`'s word for it.
port_free() {
  ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

stop_stack() {
  local ok=0
  for entry in "backend:${BACKEND_PORT}" "frontend:${WEB_PORT}"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    pidfile="${RUN_DIR}/${name}.pid"
    if [ -f "${pidfile}" ]; then
      pid="$(cat "${pidfile}")"
      if kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}" 2>/dev/null || true
        printf 'stopped %s (pid %s)\n' "${name}" "${pid}"
      fi
      rm -f "${pidfile}"
    fi
    for _ in $(seq 1 10); do
      port_free "${port}" && break
      sleep 0.3
    done
    if ! port_free "${port}"; then
      printf '⚠  %s port %s is STILL ANSWERING after stop — something else owns it, or a pid was lost.\n' \
        "${name}" "${port}" >&2
      printf '   find it with: lsof -ti tcp:%s\n' "${port}" >&2
      ok=1
    fi
  done
  return "${ok}"
}

if [ "${1:-}" = "--stop" ]; then
  stop_stack
  exit 0
fi

mkdir -p "${RUN_DIR}"

# ── 1. Postgres ─────────────────────────────────────────────────────────────
# NOT started here, deliberately: the database is external in every environment
# this product runs in (docker-compose.yml says so at length, and says why). If
# it is not reachable the honest outcome is a named failure, not a silent
# fallback to sqlite — a money journey against sqlite proves nothing about RLS,
# NUMERIC(18,6) or the immutability triggers.
say "1/5 · Postgres"
python3 - <<'PY' || die "cannot reach DATABASE_URL — start Postgres (or point DATABASE_URL at one) and re-run"
import os, sys
from urllib.parse import urlparse
url = urlparse(os.environ["DATABASE_URL"])
import socket
try:
    socket.create_connection((url.hostname or "localhost", url.port or 5432), 5).close()
except OSError as exc:
    sys.stderr.write(f"  no Postgres at {url.hostname}:{url.port} — {exc}\n")
    raise SystemExit(1)
print(f"  reachable at {url.hostname}:{url.port}, database {url.path.lstrip('/')}")
PY

# ── 2. Migrate ──────────────────────────────────────────────────────────────
say "2/5 · migrate"
( cd "${BACKEND}" && python3 manage.py migrate --noinput ) >"${RUN_DIR}/migrate.log" 2>&1 \
  || { tail -30 "${RUN_DIR}/migrate.log"; die "migrate failed (full log: ${RUN_DIR}/migrate.log)"; }
printf '  %s migrations applied this run (0 = already up to date)\n' \
  "$(grep -c 'OK$' "${RUN_DIR}/migrate.log" || true)"

# ── 3. Seed ─────────────────────────────────────────────────────────────────
# Three steps, in order, and each is idempotent: `seed_demo` provisions the
# Brazos Bend fixture tenant and its W1 world; `seed_e2e_fixture.py` adds the ONE
# account and the ONE issued bill the money journey reads — priced by the real
# engine, never typed; `seed_journey_fixture.py` adds the cohort a NAMED journey
# asserts over, read from that journey's own Fixture paragraph.
#
# THE THIRD STEP EXISTS BECAUSE OF DEF-108, and its counts are the argument: on a
# stack seeded by the first two, units 10 · units with a plan **0** ·
# unit_plan_assignments **0** · accounts **1** · meter_reads **0**. A journey
# driving real screens over that is a green tick proving the buttons exist and
# nothing about the money. `--check` names every ACTIVATED journey with no
# fixture, which is the loud boot-time failure that row asks for.
say "3/5 · seed"
( cd "${BACKEND}" && python3 manage.py seed_demo ) >"${RUN_DIR}/seed_demo.log" 2>&1 \
  || { tail -30 "${RUN_DIR}/seed_demo.log"; die "seed_demo failed (full log: ${RUN_DIR}/seed_demo.log)"; }
( cd "${BACKEND}" && python3 "${HERE}/seed_e2e_fixture.py" ) | sed 's/^/  /' \
  || die "the E2E fixture did not seed — see the message above"
# Every journey with a registered seeder is seeded. `--tolerate-missing` is typed
# here ON PURPOSE and is the ONE place it is acceptable: most activated journeys
# have no fixture yet, and refusing to boot for that would take the whole stack
# down rather than telling the truth about it. The truth is still printed, and a
# WAVE CLOSE must run `--check` (which exits 1) rather than this.
( cd "${BACKEND}" && python3 "${HERE}/seed_journey_fixture.py" --activated --tolerate-missing ) \
  | sed 's/^/  /' || die "a journey fixture failed to seed — see the message above"

# ── 4. Backend ──────────────────────────────────────────────────────────────
say "4/5 · Django on 127.0.0.1:${BACKEND_PORT}"
stop_stack
( cd "${BACKEND}"; exec python3 manage.py runserver "127.0.0.1:${BACKEND_PORT}" --noreload \
    >"${RUN_DIR}/backend.log" 2>&1 ) &
echo $! >"${RUN_DIR}/backend.pid"
for _ in $(seq 1 40); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${BACKEND_PORT}/api/public/pricing-plans" 2>/dev/null; then
    break
  fi
  sleep 0.5
done
curl -fsS -o /dev/null "http://127.0.0.1:${BACKEND_PORT}/api/public/pricing-plans" \
  || { tail -30 "${RUN_DIR}/backend.log"; die "Django never answered (full log: ${RUN_DIR}/backend.log)"; }
printf '  answering\n'

# ── 5. Frontend ─────────────────────────────────────────────────────────────
# The BUILT bundle behind `server.mjs`, not the Vite dev server: same file the
# frontend container runs, so `/api/*` is same-origin and the session cookie
# rides. A journey against `vite dev` would be testing a different server.
#
# ⚠ **`--mode compose`, NOT A BARE `npx vite build` (`DEF-INF-7802`,
# 2026-09-28 — the SECOND occurrence of `DEF-DEP-7460`, which fixed the
# identical fault in `07-frontend/Dockerfile` and walked none of the other
# callers).** Vite defaults an unflagged `build` to mode `production`, which
# reads `07-frontend/.env.production` and bakes `https://api-smart360.bynry.com`
# into the bundle — as `client.ts`'s base URL AND inside the
# `Content-Security-Policy` meta tag `vite.config.ts` writes into `index.html`.
# On 127.0.0.1 that bundle never talks to the Django above it; it calls the real
# deployed API, and sign-in fails with *"That email or password is incorrect."*
# on correct credentials. **That destroys the ONE PROPERTY this file's header
# says must not be lost — same origin** — so the journeys would be testing a
# different server, which is the exact failure the header warns about for
# `vite dev`, arriving through the build flag instead.
#
# `compose` is outside `scripts/deployConfig.mjs`'s `DEPLOYED_MODES`, so the API
# base URL resolves to `""` and the policy stays `'self'` throughout. Same mode
# as `npm run build:bundle` and as `10-scripts/11-smoke-stack.sh`.
say "5/5 · built SPA on ${BASE_URL} (same-origin /api pass-through)"
( cd "${FRONTEND}" && npx vite build --mode compose ) >"${RUN_DIR}/build.log" 2>&1 \
  || { tail -30 "${RUN_DIR}/build.log"; die "vite build failed (full log: ${RUN_DIR}/build.log)"; }
# The bundle must name NO deployed API origin — a same-origin build bakes none.
# Asserted rather than assumed: the mode flag is one word and a future edit that
# drops it would restore a defect that costs a whole walkthrough to diagnose.
if grep -rqlE 'https://api-smart360(-dev|-sandbox)?\.bynry\.com' \
     --include='*.js' --include='*.html' --include='*.css' "${FRONTEND}/dist" 2>/dev/null; then
  die "the built bundle names a DEPLOYED API origin — it was not built --mode compose.
  Served from ${BASE_URL} it calls that other host and sign-in fails with
  \"That email or password is incorrect.\" on correct credentials (DEF-INF-7802)."
fi
( cd "${FRONTEND}"; PORT="${WEB_PORT}" HOST=127.0.0.1 \
    API_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}" exec node server.mjs \
    >"${RUN_DIR}/frontend.log" 2>&1 ) &
echo $! >"${RUN_DIR}/frontend.pid"
for _ in $(seq 1 40); do
  if curl -fsS -o /dev/null "${BASE_URL}/" 2>/dev/null; then break; fi
  sleep 0.5
done
curl -fsS -o /dev/null "${BASE_URL}/" \
  || { tail -30 "${RUN_DIR}/frontend.log"; die "the SPA never answered (full log: ${RUN_DIR}/frontend.log)"; }

cat <<EOF

── the stack is up ───────────────────────────────────────
  app ................. ${BASE_URL}
  sign in ............. ${BASE_URL}/brazosbend/signin
  credentials ......... dana@brazosbendutilities.com / S3cure!passw0rd
  logs ................ ${RUN_DIR}/
  stop ................ ${HERE}/boot_stack.sh --stop

  run the journeys:
    cd 07-frontend && E2E_BASE_URL=${BASE_URL} npx playwright test
──────────────────────────────────────────────────────────
EOF

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
# generated: 2026-08-11 by the E2E bring-up lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: run end-to-end against a live Postgres; output quoted in the lane report
# exceptions: `manage.py runserver` rather than gunicorn — the compose image runs
#   gunicorn and this does not, which is a REAL difference and is stated rather
#   than hidden: it affects worker model and static handling, neither of which
#   any assertion here touches. Reported, not worked around.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
