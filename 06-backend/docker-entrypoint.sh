#!/bin/sh
# ── SMARTBillHub API container entrypoint ────────────────────────────────────
# CHECK, then SERVE. It no longer migrates.
#
# ⚠ **MIGRATIONS MOVED OUT ON 2026-09-28 (CR-144-BRC07, task H4) AND MUST NOT
# COME BACK.** This script ran `manage.py migrate` in EVERY web task at
# start-up. That is correct with exactly one task and wrong with two:
#
#   * TWO OR MORE TASKS MIGRATE AT ONCE. Django takes no advisory lock, so two
#     tasks can run the same migration concurrently; the loser fails on a
#     duplicate object, exits non-zero, and ECS restarts it into the same race.
#   * A SLOW MIGRATION FAILS THE HEALTH CHECK. Nothing answers on port 8000
#     until `exec gunicorn` at the bottom, so a five-minute migration is five
#     minutes of an unhealthy target — and the balancer kills the task partway
#     through the migration it is waiting for. A rollout that cannot finish.
#   * IT COUPLES A SCALE-OUT TO A SCHEMA CHANGE. Adding a task at 9am should
#     not run DDL.
#
# Migrations now run ONCE, as a one-off ECS task, BEFORE the rollout — see
# `docker-release.sh` beside this file and 09-infra/02-aws-runbook.md §H6.
#
# ⚠ **WHAT STAYS HERE, AND WHY IT IS NOT ARBITRARY:** every check below is about
# THIS PROCESS's ability to serve safely — the settings module it booted under,
# the hosts it will accept, the database session default it needs, and whether
# row-level security is actually enforced on its connection. A release task
# cannot answer any of those on a web task's behalf, because it is a different
# process with a different role and a different connection. The RLS check in
# particular is the one that REFUSES TO BOOT, and moving it to the release task
# would mean a task that bypasses tenant isolation is allowed to serve as long
# as some other container was fine an hour ago.
#
# ⚠ **THE §5 BOOT-ORDER REASONING STILL BINDS, IT JUST BINDS TWO SCRIPTS NOW.**
# `manage.py` defaults DJANGO_SETTINGS_MODULE to config.settings.local while
# config/wsgi.py defaults it to config.settings.production, so an unset variable
# would have the release task migrating against sqlite-shaped local defaults and
# this one serving production. **BOTH scripts refuse to start without it, and
# both ECS task definitions must carry the SAME value** — that is X4's rule that
# `DJANGO_SETTINGS_MODULE=config.settings.production` appears in all of them.
#
# 06-backend/.env.example documents every variable.
set -eu

: "${DJANGO_SETTINGS_MODULE:?set DJANGO_SETTINGS_MODULE (see 06-backend/.env.example)}"

echo "entrypoint: settings=${DJANGO_SETTINGS_MODULE}"

# Boot order per 09-infra/01 §5, as amended by CR-144-BRC07:
#   RELEASE TASK (docker-release.sh, run once by the pipeline, before rollout):
#       extensions → migrate (this includes the RLS policy migrations) →
#       sweep reference data (added 2026-08-15, OQ-087)
#   WEB TASK (this script, every task, every start): check → serve.
#       ⚠ AND ONE OF THOSE CHECKS IS NOW "did the release task actually run?"
#       (DEF-INF-7683) — not by asking the pipeline, which cannot be asked, but
#       by asking the DATABASE whether any migration is unapplied. A web task
#       must never migrate; it may certainly refuse to serve a schema it cannot
#       serve.
# DEMO seeding (`manage.py seed_demo`) stays a DELIBERATE manual step — never
# automatic on boot, never production (§5 step 4):
#   docker compose exec backend python manage.py seed_demo
# The reference-data SWEEP below is a different thing and is deliberately not
# that: it provisions nothing and is the PO's ruled delivery mechanism for
# platform vocabulary reaching tenants that already exist (OQ-087).
# ── Boot-time host check (added 2026-08-10 from the first live deploy) ───────
# ALLOWED_HOSTS empty or localhost-only under production settings means Django
# answers 400 to EVERY request — including the load balancer's health check.
# That is exactly what happened at smartbillhub.bynry.com: the .env was copied
# from the template and never edited, so gunicorn logged a clean, healthy boot
# and then rejected every request with a bare 400 that named no cause.
#
# The failure was findable but silent in the wrong place: visible only as
# per-request 400s in the access log, while the misconfiguration itself is known
# at startup. So say it at startup. This does NOT refuse to boot — running
# production settings against localhost is legitimate (that is `make up`), and a
# hard stop would break it.
echo "entrypoint: allowed_hosts=${DJANGO_ALLOWED_HOSTS:-<unset>}"
case "${DJANGO_SETTINGS_MODULE}" in
  *production*)
    case ",${DJANGO_ALLOWED_HOSTS:-}," in
      ,,|,localhost,|,127.0.0.1,|,localhost,127.0.0.1,|,127.0.0.1,localhost,)
        echo "entrypoint: ⚠ DJANGO_ALLOWED_HOSTS is empty or localhost-only while"
        echo "entrypoint: ⚠ settings are PRODUCTION. Django will answer 400 to every"
        echo "entrypoint: ⚠ request whose Host is anything else — including your"
        echo "entrypoint: ⚠ public domain and your load balancer's health check."
        echo "entrypoint: ⚠ Set it in 06-backend/.env, e.g."
        echo "entrypoint: ⚠   DJANGO_ALLOWED_HOSTS=smartbillhub.bynry.com"
        ;;
    esac
    ;;
esac

# ⚠ **THE DEF-622 `app.tenant_id` CHECK MOVED TO `docker-release.sh` ON
# 2026-09-28 (CR-144-BRC07, H4).** It was always a PRE-MIGRATE check — its own
# text ends "the migrate below will report the real connection error" — and
# there is no migrate below any more. Left here it would print a warning about
# a step this process does not perform, which is the stale-record rot this repo
# files most; a paragraph describing a thing that no longer happens outlives the
# thing. It runs in the release task, immediately before the migrate it is about.

# ── Boot-time RLS-enforcement check (added 2026-08-31 from DEF-2717) ────────
# ⚠ THIS ONE REFUSES TO BOOT, AND THE TWO CHECKS ABOVE DELIBERATELY DO NOT.
# That difference is the decision, so here is the reasoning rather than the rule:
#   * ALLOWED_HOSTS warns because production settings against localhost is a
#     legitimate configuration (`make up`) — refusing would break it.
#   * app.tenant_id warns because an already-migrated database is unaffected —
#     refusing would take a healthy production down for a setting it does not
#     need at that moment.
#   * A BYPASSING ROLE HAS NO LEGITIMATE PRODUCTION USE. PostgreSQL exempts
#     superusers and BYPASSRLS roles from row-level security unconditionally,
#     FORCE ROW LEVEL SECURITY included. For as long as this process runs, every
#     query for every tenant is unfiltered — and it is invisible: the tables
#     still report ENABLE and FORCE, the policies still exist, and every query
#     returns plausible rows. Serving is strictly WORSE than not serving,
#     because the product keeps answering and quietly mixes tenants' data.
# Measured on PostgreSQL 16.13 (2026-08-31): same table, same policy, same
# app.tenant_id — NOSUPERUSER NOBYPASSRLS saw 2 rows, SUPERUSER saw 3, the third
# being the other tenant's.
#
# Development on a superuser role is legitimate and common, so it is NOT fatal
# there: config/settings/local.py types RLS_ALLOW_BYPASSING_ROLE = True and this
# prints one loud line instead. Hard-won law 3 — the unsafe option is the one you
# type. The same function runs in config/wsgi.py, so a `command:` override that
# skips this script is still covered.
echo "entrypoint: checking that row-level security is enforced (DEF-2717)"
python - <<'PY'
import sys
import django

django.setup()
from core import rls_guard

try:
    rls_guard.enforce_at_startup(stream=sys.stdout)
except Exception as exc:  # ImproperlyConfigured — print it, do not traceback
    print(str(exc))
    sys.exit(1)
PY

# ⚠ **`python manage.py migrate --noinput` AND THE OQ-087 REFERENCE-DATA SWEEP
# USED TO BE HERE. THEY ARE IN `docker-release.sh` (CR-144-BRC07, H4).**
#
# The sweep moved WITH the migrate rather than staying behind, and that is the
# OQ-087 ruling being kept rather than bent: it says the sweep is *"automatic
# post-migrate, across all tenants"*. Left here it would run in every web task,
# so N tasks would sweep every tenant at once — and it would run BEFORE the
# migrate in a fresh environment, which is the one order the ruling forbids.
# Keeping the two steps adjacent in one place is what keeps "post-migrate" true.
#
# ⚠ **THIS PARAGRAPH USED TO END "SO A WEB TASK NOW ASSUMES THE DATABASE IS
# ALREADY MIGRATED … the runbook says so at the step where it matters". IT NO
# LONGER ASSUMES. IT ASKS — see the block below (DEF-INF-7683, 2026-09-28.)**
# The old sentence went on: *"a rollout that skips it starts tasks against an
# older schema, and the symptom is a column-not-found error from a view rather
# than anything that names the deploy."* **That was right, and it came true the
# same day it was written**, at smartbillhub.bynry.com: nobody could sign in,
# every `POST /api/<slug>/auth/session` answered 500 over
# `psycopg.errors.UndefinedColumn: column security_policies.absolute_session_hours
# does not exist`, and `/api/health` answered 200 throughout.
#
# **A correct prediction with no check beside it is hard-won law 1 exactly** — a
# comment claiming a guarantee is not the guarantee — and the assumption was
# being honoured by a pipeline that does not exist: every workflow in
# `.github/workflows/` is `.disabled`, and `docker-release.sh` has two callers,
# `make release` and a human runbook step. An assumption held by a human step is
# an assumption, and this one took the product down.

# ── Boot-time SCHEMA check (added 2026-09-28 from DEF-INF-7683) ─────────────
# ⚠ THIS ONE REFUSES TO BOOT. The criterion is the one stated above the RLS
# check and it is the same answer for the same reason: **serving is strictly
# worse than not serving.** A task that boots on an older schema answers 500 to
# every request that reads a new column while its probe answers 200, so the
# balancer keeps a useless task in rotation and nothing in any log names the
# deploy. A task that REFUSES fails the rollout instead — and under a rolling
# deploy the previous task definition's tasks go on serving customers.
#
# ⚠ THE OTHER SIDE, ARGUED, BECAUSE IT IS A REAL RISK AND NOT A FORMALITY:
# pending is not the same as NEEDED. A migration that adds a column no code
# reads yet is harmless, and nothing here can tell the two apart — Django knows
# a migration is unapplied, not whether this build reads what it adds. The
# moment that bites is NOT the deploy but an unrelated task replacement (a spot
# interruption, an AZ event, a 9am scale-out), where a refusal takes capacity
# off a site that was working. So it is law 3's answer rather than a cleverer
# test: refuse by default, and let an operator who KNOWS the migration is
# forward-compatible type `SBH_ALLOW_PENDING_MIGRATIONS=1`. The unsafe option
# is the one you type, and it prints loudly on every boot so it cannot be left
# behind quietly.
#
# ⚠ IT IS NOT `manage.py migrate --check`, AND THAT IS MEASURED RATHER THAN
# PREFERRED. Measured 2026-09-28 on PostgreSQL 16: schema at tip → exit 0;
# `identity` rolled back to 0005 → exit 1; DATABASE_URL on a closed port →
# exit 1; DATABASE_URL naming a database that does not exist → exit 1. **Exit 1
# means "pending" OR "I could not ask."** `migrate --check || exit 1` would
# therefore crash-loop the whole service through a thirty-second RDS failover.
# `core/schema_guard.py` returns THREE states so "we could not tell" is never
# rendered as either answer — and on UNREACHABLE it warns and boots, because a
# process that cannot reach the database fails every request whatever its
# schema, and one that refused would be gone when the database returns.
#
# ⚠ AND IT DOES NOT MIGRATE. Not on a flag, not as a fallback. H4's three
# faults are unchanged: concurrent migration with no advisory lock, a slow
# migration failing the health check that is waiting on it, and a scale-out
# running DDL. The fix for a refusal is `make release`, never this file.
echo "entrypoint: checking the schema is the one this build was built for (DEF-INF-7683)"
python - <<'PY'
import sys

import django

django.setup()
from core import schema_guard

try:
    schema_guard.enforce_at_startup(stream=sys.stdout)
except Exception as exc:  # ImproperlyConfigured — print it, do not traceback
    print(str(exc))
    sys.exit(1)
PY

# ⚠ **`/api/health` IS NOT MADE DEEPER BY ANY OF THIS, ON PURPOSE.** It answered
# 200 all the way through the outage above, which reads like the bug and is not
# it: `core/health.py` is a LIVENESS probe — *this Python process is accepting
# and answering HTTP* — and `tests/test_health.py::
# test_health_answers_with_the_database_unreachable` pins it there, because a
# probe that queries the database turns a slow database into no service at all
# and manufactures the outage it was meant to report. The answer to "the probe
# said healthy while every sign-in 500'd" is not a deeper probe. It is that
# **the process answering the probe must not exist when the schema is wrong**,
# which is the block above: a refusing task never reaches `exec gunicorn`, so
# there is nothing listening for the balancer to be told about.

# Worker/timeout defaults are overridable by env so a small box and a big one do
# not need different images. 3 workers is the conventional 2n+1 for a 1-vCPU
# task; raise GUNICORN_WORKERS with the vCPU count. The 60s timeout is generous
# for the API but NOT generous for a job body — with JOBS_EAGER=true a job runs
# INSIDE the request (09-infra/02 §10.4), so a long export can hit it. That is a
# property of eager jobs, not of this timeout; raising it hides the symptom.
#
# ⚠ THIS 60 IS THE WALL DEF-2487 HIT, AND THE FIX WAS NOT HERE. The accounts
# import commit ran inline for any file at or below the async bar; one accounts
# row cost about 124 ms on real PostgreSQL, so 1,048 rows took 121.9 s and the
# worker was SIGKILLed at 60 s mid-transaction. Django never formed a response,
# so there was no envelope, no code and no trace_id — the browser fell back to
# "Something went wrong. Nothing was saved - try again", which was TRUE: the
# outer transaction rolled back and zero accounts landed. The repair made the
# async bar per-target and per-stage (accounts load = 100, not 5,000) in
# apps/metering/import_runs.py and halved the per-row cost in
# apps/customers/services.py. Raising GUNICORN_TIMEOUT would have hidden it.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile - \
  "$@"
