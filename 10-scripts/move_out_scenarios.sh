#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Component: the ONE command that runs the move-out scenario suite.
# Change:   PO 2026-09-19, verbatim: *"ensure you run end to end walk withmuitle
#           scenarios - deposites, settlement, bill creation etc … create
#           variosu cases and scenarios and do end to end walk to ensure clark
#           is able to perform all these task from screen"*.
# Rules:    CLAUDE.md hard rule 4 (financial immutability — a move-out COMMITS
#           and there is no delete) · hard-won law 7 (prove a guard goes RED
#           before trusting it green) · law 14 (transaction behaviour is proved
#           on PostgreSQL, never on the default SQLite suite) ·
#           `DEF-GOV-4299` (nothing on `PATH` can import Django — use
#           `06-backend/.venv/bin/python`)
# Tests:    06-backend/tests/test_move_out_scenarios.py
# Defects:  `DEF-CUS-5930` — `E1`, a master account with open sub-accounts
#           moved out anyway. FIXED in `v2.314.2` (`BR-CUS-1082`, a LANE
#           JUDGMENT pending `OQ-CUS-12515`); `E1` is GREEN 7/7 in both
#           columns and the two numbers moved 1→2 and 16→17 of 27, with no
#           other row moving in either direction. ⚠ The rule that defect
#           was filed against does not say it — `DEF-CUS-5950`.
# Journey:  08-qa/01-e2e/journeys/J-MVO-TWENTYSEVEN-the-move-out-scenario-suite.md
# ───────────────────────────────────────────────────────
#
#   ./10-scripts/move_out_scenarios.sh              run all 27, both columns
#   ./10-scripts/move_out_scenarios.sh --prove-red  break two assertions, show
#                                                   them red, restore, show green
#   ./10-scripts/move_out_scenarios.sh L3 SH3       run named scenarios only
#
# ⚠ **THE BETA IS NEVER WRITTEN TO, AND THIS SCRIPT PROVES IT RATHER THAN
# CLAIMING IT.** A move-out closes an account, ends its service agreements,
# writes readings and writes a permanent move record; readings are append-only
# and payments and journal lines are under hard rule 4, so there is no undo —
# the database itself refuses a DELETE through thirteen triggers. So the suite
# runs on `config.settings.pgtest`, a SEPARATE PostgreSQL database, and each
# scenario provisions its own throwaway tenant inside it which `django_db`
# rolls back.
#
# This script counts the beta's accounts, move records, payments, journal
# lines, invoices and parked drafts BEFORE and AFTER and prints both. Hard-won
# law 1: a comment claiming a guarantee is not the guarantee.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/06-backend"
REPORT="${MOVE_OUT_REPORT:-$BACKEND/.move-out-scenarios-report.txt}"
#: A whole run is 54 passes — twenty-seven scenarios, twice each. About five
#: minutes warm, and several more the first time the pgtest database applies
#: every migration against a real server.
TIMEOUT="${MOVE_OUT_TIMEOUT:-3600}"

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
        ("accounts", "accounts"),
        ("move records", "move_records"),
        ("payments", "payments"),
        ("journal lines", "journal_lines"),
        ("invoices", "invoices"),
        ("parked drafts", "wizard_parks"),
    ):
        cur.execute(f"select count(*) from {table}")  # noqa: S608 — a fixed list
        out.append(f"{name} {cur.fetchone()[0]}")
print(f"  {label}: " + " · ".join(out))
PYEOF
}

echo "── THE BETA, BEFORE ────────────────────────────────────────────────────"
beta_counts "before"

PYTEST=("$BACKEND/.venv/bin/pytest" "tests/test_move_out_scenarios.py"
        --ds=config.settings.pgtest --reuse-db -q -s --tb=short -p no:logging)

STDERR_LOG="${MOVE_OUT_STDERR:-$BACKEND/.move-out-scenarios-stderr.log}"

run_suite() {  # $1 = a label, rest = extra pytest args
  local label="$1"; shift
  echo
  echo "── $label ──────────────────────────────────────────────────────────────"
  # ⚠ **STDERR GOES TO A NAMED FILE RATHER THAN THROUGH A GREP.** Provisioning
  # a tenant enqueues the sample-plant job and a developer container has no
  # broker, so `apps/tenancy/tasks.send` logs a forty-line Celery traceback per
  # scenario — it never raises, which is its documented posture, but fifty-four
  # of them bury the report. A pattern-matched filter would be a check that
  # quietly swallows a real error one day, so the noise is SET ASIDE where it
  # can still be read rather than thrown away.
  #
  # ⚠ `JOBS_EAGER=false` is the repo's standard (`DEF-567`): eager jobs seed a
  # whole sample utility per fixture.
  set +e
  JOBS_EAGER=false MOVE_OUT_REPORT="$REPORT" \
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
    #
    # TWO DIFFERENT CHECKERS, on purpose: `_subset` (which compares a declared
    # dict against a table read) and `check_move_record` (which has its own
    # logic for a record that should not exist). One break proving one checker
    # would leave eleven unproved.
    MOVE_OUT_BREAK=C1:unit_after run_suite "BROKEN: C1 · unit_after" -k "C1 or C2"
    MOVE_OUT_BREAK=R1:move_record run_suite "BROKEN: R1 · move_record" -k "R1 or R2"
    run_suite "RESTORED" -k "C1 or C2 or R1 or R2"
    ;;
  "")
    run_suite "THE TWENTY-SEVEN, BOTH COLUMNS"
    ;;
  *)
    run_suite "THE TWENTY-SEVEN (filtered: $*)" -k "$(printf '%s or ' "$@" | sed 's/ or $//')"
    ;;
esac

echo
echo "── THE BETA, AFTER ─────────────────────────────────────────────────────"
beta_counts "after"
echo
echo "the full report is at $REPORT"
