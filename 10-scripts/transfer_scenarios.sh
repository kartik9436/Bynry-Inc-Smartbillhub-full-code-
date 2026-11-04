#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Component: the ONE command that runs the property-sale scenario suite.
# Change:   PO 2026-09-20, verbatim: *"once you are done with changes for
#           tranfer - do the end to end walk - create request , see all transfer
#           work corectly - property, address, assets, units - occupancy is
#           updated at unit . assets whow correct account - money part is
#           correct, email, communcation is send"*.
# Rules:    BR-CUS-1030 (a transfer REASSIGNS the account — one account, never
#           closed, the CUSTOMER changes) · BR-CUS-085 (nothing is refunded and
#           re-collected) · CLAUDE.md hard rules 4 and 8 · hard-won law 7 (prove
#           a guard goes RED before trusting it green) · law 14 (transaction
#           behaviour is proved on PostgreSQL, never on the default SQLite
#           suite) · `DEF-GOV-5925` (nothing on `PATH` can import Django — use
#           `06-backend/.venv/bin/python`, and the gate that says otherwise is
#           printing a FALSE sentence)
# Tests:    06-backend/tests/test_transfer_scenarios.py
# Journey:  08-qa/01-e2e/journeys/J-TRF-TWENTYFIVE-the-property-sale-scenario-suite.md
# ───────────────────────────────────────────────────────
#
#   ./10-scripts/transfer_scenarios.sh              run all 25, both columns
#   ./10-scripts/transfer_scenarios.sh --prove-red  break two assertions, show
#                                                   them red, restore, show green
#   ./10-scripts/transfer_scenarios.sh SL1 MN4      run named scenarios only
#
# ⚠ **THE BETA IS NEVER WRITTEN TO, AND THIS SCRIPT PROVES IT RATHER THAN
# CLAIMING IT.** A sale rewrites `customer_accounts`, writes a permanent
# `transfers` row, raises work orders and writes `audit_log`; the audit rows and
# the transfer row have no undo, and thirteen database triggers refuse the
# deletes a tenant drop would need. So the suite runs on `config.settings.pgtest`
# — a SEPARATE PostgreSQL database — and each scenario provisions its own
# throwaway tenant inside it which `django_db` rolls back.
#
# This script counts the beta's accounts, transfers, customer links, payments,
# journal lines, invoices, queued messages and parked drafts BEFORE and AFTER
# and prints both. Hard-won law 1: a comment claiming a guarantee is not the
# guarantee. The move-out suite's script is this one's source and its reasoning
# is quoted rather than reinvented.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/06-backend"
REPORT="${TRANSFER_REPORT:-$BACKEND/.transfer-scenarios-report.txt}"
#: A whole run is 28 tests — twenty-five scenarios and three guards. About four
#: minutes warm, and several more the first time the pgtest database applies
#: every migration against a real server.
TIMEOUT="${TRANSFER_TIMEOUT:-3600}"

cd "$BACKEND"
# shellcheck disable=SC1091
set -a; . ./.env; set +a
: "${DATABASE_URL:?DATABASE_URL must be set — 06-backend/.env}"

beta_counts() {
  # READ ONLY, and it is the only time this script opens the beta at all.
  # Tenant-scoped because RLS FORCE is on: with `app.tenant_id` unset the counts
  # come back zero and the check would be one that cannot fail.
  "$BACKEND/.venv/bin/python" - "$1" <<'PYEOF'
import os, sys, django
sys.path.insert(0, "06-backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
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
        ("transfers", "transfers"),
        ("customer links", "customer_accounts"),
        ("customers", "customers"),
        ("payments", "payments"),
        ("journal lines", "journal_lines"),
        ("invoices", "invoices"),
        ("queued messages", "outbound_messages"),
        ("parked drafts", "wizard_parks"),
    ):
        cur.execute(f"select count(*) from {table}")  # noqa: S608 — a fixed list
        out.append(f"{name} {cur.fetchone()[0]}")
print(f"  {label}: " + " · ".join(out))
PYEOF
}

echo "── THE BETA, BEFORE ────────────────────────────────────────────────────"
beta_counts "before"

PYTEST=("$BACKEND/.venv/bin/pytest" "tests/test_transfer_scenarios.py"
        --ds=config.settings.pgtest --reuse-db -q -s --tb=line -p no:logging)

STDERR_LOG="${TRANSFER_STDERR:-$BACKEND/.transfer-scenarios-stderr.log}"

run_suite() {  # $1 = a label, rest = extra pytest args
  local label="$1"; shift
  echo
  echo "── $label ──────────────────────────────────────────────────────────────"
  # ⚠ **STDERR GOES TO A NAMED FILE RATHER THAN THROUGH A GREP.** Provisioning a
  # tenant enqueues the sample-plant job and a developer container has no broker,
  # so `apps/tenancy/tasks.send` logs a forty-line Celery traceback per scenario
  # — it never raises, which is its documented posture, but twenty-five of them
  # bury the report. A pattern-matched filter would be a check that quietly
  # swallows a real error one day, so the noise is SET ASIDE where it can still
  # be read rather than thrown away.
  #
  # ⚠ `JOBS_EAGER=false` is the repo's standard (`DEF-567`): eager jobs seed a
  # whole sample utility per fixture.
  set +e
  JOBS_EAGER=false TRANSFER_REPORT="$REPORT" \
    timeout "$TIMEOUT" "${PYTEST[@]}" "$@" 2>"$STDERR_LOG"
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
    # break damages what the runner OBSERVED, not what the row DECLARED, so what
    # it proves is that the checker really reads PostgreSQL's answer and
    # compares it — which inverting a verdict would not.
    #
    # TWO DIFFERENT CHECKERS, on purpose: `_subset` (which compares a declared
    # dict against a table read) and `check_outcome` (which has its own logic
    # and reads no dict at all). One break proving one checker would leave the
    # other eleven dimensions unproved.
    #
    # ⚠ **THE SECOND BREAK IS ON A ROW THAT COMMITS, AND THAT MATTERS.**
    # Pointed at a REFUSAL row, corrupting the observation into *refused*
    # changes nothing the row did not already expect and the break reports
    # `2 passed` — a no-op that reads exactly like a proof. `MN1` commits, so
    # flipping it to refused is a real inversion. (The breaker inverts now
    # either way; the row is still chosen so the proof does not depend on
    # that.)
    TRANSFER_BREAK=MN3:books_and_payments run_suite "BROKEN: MN3 · books_and_payments" -k "MN3 or MN2"
    TRANSFER_BREAK=MN1:outcome run_suite "BROKEN: MN1 · outcome" -k "MN1 or SL1"
    run_suite "RESTORED" -k "MN1 or MN2 or MN3 or SL1"
    ;;
  "")
    run_suite "THE TWENTY-FIVE, BOTH COLUMNS"
    ;;
  *)
    run_suite "THE TWENTY-FIVE (filtered: $*)" -k "$(printf '%s or ' "$@" | sed 's/ or $//')"
    ;;
esac

echo
echo "── THE BETA, AFTER ─────────────────────────────────────────────────────"
beta_counts "after"
echo
echo "the full report is at $REPORT"
