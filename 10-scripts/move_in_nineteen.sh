#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Component: the ONE command that runs the move-in scenario suite.
# Change:   PO 2026-09-19 — nineteen move-in scenarios, runnable as one command.
# Rules:    CLAUDE.md hard rule 4 (financial immutability — a move-in COMMITS
#           and there is no delete) · hard-won law 7 (prove a guard goes RED
#           before trusting it green) · law 14 (transaction behaviour is proved
#           on PostgreSQL, never on the default SQLite suite) ·
#           `DEF-GOV-5877` (a hard timeout on every background job)
# Tests:    06-backend/tests/test_move_in_nineteen_scenarios.py
# ───────────────────────────────────────────────────────
#
#   ./10-scripts/move_in_nineteen.sh              run the nineteen, print the report
#   ./10-scripts/move_in_nineteen.sh --prove-red  break two assertions, show them
#                                                 red, restore, show them green
#   ./10-scripts/move_in_nineteen.sh M4 S5        run named scenarios only
#
# ⚠ **THE BETA IS NEVER WRITTEN TO, AND THIS SCRIPT PROVES IT RATHER THAN
# CLAIMING IT.** A move-in opens an account, takes money, writes readings and
# posts to the ledger; readings are append-only and payments and journal lines
# are under hard rule 4, so there is no undo — the database itself refuses a
# DELETE through `trg_payment_immutable`, `meter_reads_value_immutable` and
# eleven more triggers. So the suite runs on `config.settings.pgtest`, a
# SEPARATE PostgreSQL database, and each scenario provisions its own throwaway
# tenant inside it which `django_db` rolls back.
#
# This script counts the beta's service requests, accounts, payments, journal
# lines and readings BEFORE and AFTER and prints both. Hard-won law 1: a comment
# claiming a guarantee is not the guarantee.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/06-backend"
REPORT="${MOVE_IN_NINETEEN_REPORT:-$ROOT/06-backend/.move-in-nineteen-report.txt}"
#: A whole run takes about a hundred seconds warm and several minutes the first
#: time, when the pgtest database applies every migration against a real server.
TIMEOUT="${MOVE_IN_NINETEEN_TIMEOUT:-2700}"

cd "$BACKEND"
# shellcheck disable=SC1091
set -a; . ./.env; set +a
: "${DATABASE_URL:?DATABASE_URL must be set — 06-backend/.env}"

beta_counts() {
  # READ ONLY, and it is the only time this script opens the beta at all.
  # Tenant-scoped because RLS FORCE is on: with `app.tenant_id` unset the
  # counts come back zero and the check would be one that cannot fail.
  "$BACKEND/.venv/bin/python" - "$1" <<'PYEOF'
import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath("06-backend")), "06-backend"))
sys.path.insert(0, "06-backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()
from django.db import connection
label = sys.argv[1]
with connection.cursor() as cur:
    cur.execute("select id from tenants where subdomain = 'brazosbend'")
    row = cur.fetchone()
    if row is None:
        print(f"  {label}: no `brazosbend` tenant on this database — nothing to count")
        raise SystemExit(0)
    cur.execute("select set_config('app.tenant_id', %s, false)", [str(row[0])])
    out = []
    for name, table in (
        ("service requests", "service_requests"),
        ("accounts", "accounts"),
        ("payments", "payments"),
        ("journal lines", "journal_lines"),
        ("readings", "meter_reads"),
    ):
        cur.execute(f"select count(*) from {table}")  # noqa: S608 — a fixed list
        out.append(f"{name} {cur.fetchone()[0]}")
print(f"  {label}: " + " · ".join(out))
PYEOF
}

echo "── THE BETA, BEFORE ────────────────────────────────────────────────────"
beta_counts "before"

PYTEST=("$BACKEND/.venv/bin/pytest" "tests/test_move_in_nineteen_scenarios.py"
        --ds=config.settings.pgtest --reuse-db -q -s --tb=short -p no:logging)

STDERR_LOG="${MOVE_IN_NINETEEN_STDERR:-$BACKEND/.move-in-nineteen-stderr.log}"

run_suite() {  # $1 = a label, rest = extra pytest args
  local label="$1"; shift
  echo
  echo "── $label ──────────────────────────────────────────────────────────────"
  # ⚠ **STDERR GOES TO A FILE RATHER THAN THROUGH A GREP, AND THE FILE IS
  # NAMED.** Provisioning a tenant enqueues the sample-plant job and a
  # developer container has no broker, so `apps/tenancy/tasks.send` logs a
  # forty-line Celery traceback per scenario — it never raises, which is its
  # documented posture, but nineteen of them bury the report. A pattern-matched
  # filter would be a check that quietly swallows a real error one day, so the
  # noise is SET ASIDE where it can still be read rather than thrown away.
  #
  # ⚠ `JOBS_EAGER=false` is the repo's standard (`DEF-567`): eager jobs seed a
  # whole sample utility per fixture.
  set +e
  JOBS_EAGER=false MOVE_IN_NINETEEN_REPORT="$REPORT" \
    timeout "$TIMEOUT" "${PYTEST[@]}" "$@" 2>"$STDERR_LOG"
  local code=$?
  set -e
  if [ -s "$STDERR_LOG" ]; then
    local noise other
    noise=$(grep -c 'could not dispatch job' "$STDERR_LOG" || true)
    other=$(grep -cvE 'kombu|redis|celery|socket|Traceback|During handling|The above exception|^[[:space:]]|^$' "$STDERR_LOG" || true)
    echo "  (stderr: $noise broker-unreachable job dispatch(es), $other other line(s) — $STDERR_LOG)"
  fi
  return 0
}

case "${1:-}" in
  --prove-red)
    # ⚠ **A SUITE FIRST SEEN GREEN IS A SUITE NOBODY HAS PROVED** (law 7). The
    # break damages what the runner OBSERVED, not what the row DECLARED, so
    # what it proves is that the checker really reads PostgreSQL's answer and
    # compares it — which inverting a verdict would not.
    MOVE_IN_NINETEEN_BREAK=M1:payment_rows run_suite "BROKEN: M1 · payment_rows" -k "M1 or M2"
    MOVE_IN_NINETEEN_BREAK=R1:refusal_name run_suite "BROKEN: R1 · refusal_name" -k "R1"
    run_suite "RESTORED" -k "M1 or M2 or R1"
    ;;
  "")
    run_suite "THE NINETEEN"
    ;;
  *)
    run_suite "THE NINETEEN (filtered: $*)" -k "$(printf '%s or ' "$@" | sed 's/ or $//')"
    ;;
esac

echo
echo "── THE BETA, AFTER ─────────────────────────────────────────────────────"
beta_counts "after"
echo
echo "the full report is at $REPORT"
