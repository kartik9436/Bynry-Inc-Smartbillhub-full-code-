#!/bin/sh
# ── SMARTBillHub — the RELEASE task ─────────────────────────────────────────
# Run ONCE per deploy, by the pipeline, BEFORE the service rolls. Never in a
# web task.
#
#   aws ecs run-task --task-definition smartbillhub-release-<env> ...
#
# ⚠ **WHY THIS FILE EXISTS (CR-144-BRC07, H4, 2026-09-28).** `migrate` used to
# run inside `docker-entrypoint.sh`, in EVERY web task, at start-up. With one
# task that is fine and with two it is three separate faults at once:
#
#   * TWO TASKS MIGRATE CONCURRENTLY. Django takes no advisory lock. The loser
#     fails on an object that already exists, exits non-zero, and ECS restarts
#     it straight back into the same race.
#   * A SLOW MIGRATION FAILS THE HEALTH CHECK. Nothing answered on port 8000
#     until gunicorn started, so a long migration was a long stretch of an
#     unhealthy target — and the balancer kills the task PARTWAY THROUGH the
#     migration it is waiting for, which is the worst of the three.
#   * SCALING OUT RAN DDL. Adding a task at 9am should not change the schema.
#
# ⚠ **DJANGO_SETTINGS_MODULE MUST BE THE SAME VALUE AS THE WEB TASK'S, AND THAT
# IS THE §5 BOOT-ORDER REASONING, UNCHANGED — IT JUST BINDS TWO SCRIPTS NOW.**
# `manage.py` defaults it to `config.settings.local` while `config/wsgi.py`
# defaults it to `config.settings.production`. Unset, this task would migrate
# against sqlite-shaped local defaults while the web task serves production.
# So this script refuses to start without it, exactly as the entrypoint does,
# and X4 requires `DJANGO_SETTINGS_MODULE=config.settings.production` in ALL
# THREE task definitions of every environment.
#
# ⚠ **IT MUST EXIT ZERO BEFORE THE SERVICE ROLLS.** The web tasks now assume a
# migrated database. A pipeline that starts the rollout in parallel with this
# is the old race with more steps.
set -eu

: "${DJANGO_SETTINGS_MODULE:?set DJANGO_SETTINGS_MODULE (see 06-backend/.env.example)}"

echo "release: settings=${DJANGO_SETTINGS_MODULE}"

# ── Boot-time tenant-context check (added 2026-08-24 from DEF-622) ──────────
# A FRESH DATABASE CANNOT MIGRATE unless `app.tenant_id` has a castable session
# default. Every tenant table carries FORCE ROW LEVEL SECURITY, FORCE applies the
# policy to the table OWNER — which is whoever runs migrations — and PostgreSQL
# validates a new FOREIGN KEY with an ordinary scan the policy is evaluated
# against. With the GUC absent that scan raises
#   ProgrammingError: unrecognized configuration parameter "app.tenant_id"
# and with the GUC set to '' (the cleared/deny sentinel, which cannot cast) it
# raises
#   DataError: invalid input syntax for type uuid: ""
# Neither message names the database, the setting, or the fix, and the migrate
# below simply runs into them. So look FIRST and say what to do.
#
# ⚠ THIS DOES NOT REFUSE TO BOOT, and that is the same reasoning as the
# ALLOWED_HOSTS block above. An ALREADY-MIGRATED database is unaffected — migrate
# is a no-op there, whatever the GUC says — so refusing would take a working
# production down for a setting it does not need at that moment. What it must not
# do is stay silent, because every environment we have carries this setting by
# accident of history and only a first deploy discovers it.
#
# ⚠ AND IT CANNOT FIX ITSELF (hard-won law 4). This container runs as the app
# role and the fix is a database-level ALTER; nothing you pull, rebuild or
# redeploy applies it. A human runs it once per database, by hand.
echo "release: checking app.tenant_id session default (DEF-622)"
tenant_guc_state="$(python - <<'PY' 2>/dev/null || echo UNREACHABLE
import django
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT current_setting('app.tenant_id', true)")
    value = cursor.fetchone()[0]
print("ABSENT" if value is None else ("EMPTY" if value == "" else "SET"))
PY
)"
case "${tenant_guc_state}" in
  SET)
    echo "release: app.tenant_id default present — a fresh migrate can run"
    ;;
  UNREACHABLE)
    echo "release: ⚠ could not read app.tenant_id (database unreachable?)."
    echo "release: ⚠ migrate below will report the real connection error."
    ;;
  *)
    echo "release: ⚠ ────────────────────────────────────────────────────────"
    echo "release: ⚠ app.tenant_id has NO USABLE SESSION DEFAULT on this database"
    echo "release: ⚠   state: ${tenant_guc_state}  (ABSENT = never set, EMPTY = '')"
    echo "release: ⚠"
    echo "release: ⚠ An already-migrated database boots fine and you can ignore"
    echo "release: ⚠ this. Applying a NEW migration that adds a foreign key to a"
    echo "release: ⚠ tenant table will fail here, and a FIRST deploy fails now."
    echo "release: ⚠"
    echo "release: ⚠ Fix it once, by hand, as the database owner or a superuser"
    echo "release: ⚠ (it changes no data, locks no table, and applies to sessions"
    echo "release: ⚠ started after it):"
    echo "release: ⚠"
    echo "release: ⚠   psql \"\$DATABASE_URL\" -c \"ALTER DATABASE \\\"<db>\\\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'\""
    echo "release: ⚠"
    echo "release: ⚠ or, from a checkout of this repo:"
    echo "release: ⚠   10-scripts/13-provision-database.sh --tenant-guc --verify"
    echo "release: ⚠"
    echo "release: ⚠ The nil UUID is the 'no tenant' sentinel: it CASTS, so the RLS"
    echo "release: ⚠ policy evaluates instead of erroring, and it MATCHES NO ROW, so"
    echo "release: ⚠ deny-by-default is unchanged. See 06-backend/db/001_tenant_context_default.sql."
    echo "release: ⚠ ────────────────────────────────────────────────────────"
    ;;
esac

python manage.py migrate --noinput

# ── OQ-087 (CLOSED, PO 2026-08-10): the reference-data sweep is AUTOMATIC and
# POST-MIGRATE, across all tenants. Ruling verbatim: "automatic post-migrate,
# across all tenants. Per-tenant context, per-tenant transaction, failures
# isolated and recorded, sweep continues (BR-TEN-074)."
#
# ⚠ **IT MOVED HERE WITH THE MIGRATE ON 2026-09-28 (CR-144-BRC07), WHICH KEEPS
# THE RULING RATHER THAN BENDING IT.** Left in the web entrypoint it would run
# in every task — N tasks sweeping every tenant at once — and, in a fresh
# environment, BEFORE the migrate, which is the one order "post-migrate"
# forbids. Adjacent to the migrate in one place is what keeps it true.
#
# Without it a tenant provisioned in August still never receives the vocabulary
# shipped in September, and the command would be a feature that exists and does
# not happen — hard-won law 2, built is not wired.
#
# It is NOT allowed to fail the release, and that is BR-TEN-074 rather than
# convenience: the sweep isolates per-tenant failures by design and exits 2
# naming them, 3 on an unexplained-empty list. Refusing to deploy because one
# tenant's reference list needs attention would hold a schema change hostage to
# a configuration gap. So the exit code is PRINTED LOUDLY and this script still
# exits 0 — `set -e` is suspended for this one command on purpose.
#
# Unlike `seed_demo` — which stays a DELIBERATE manual step, never automatic,
# never production — this runs in production: it mints no tenant, no user, no
# credential and no subscription, and production is the only host where the
# tenants that need it exist (BR-TEN-064's per-path precedent, DEF-026).
# `--dry-run` stays the mandatory step BEFORE releasing a fixture bump
# (BR-TEN-076); it is a release-PROCESS step, not a step in this script.
echo "release: reference-data sweep (OQ-087 — automatic post-migrate)"
set +e
python manage.py sweep_reference_data
sweep_status=$?
set -e
if [ "${sweep_status}" -ne 0 ]; then
  echo "release: ⚠ sweep_reference_data exited ${sweep_status} — see the lines above."
  echo "release: ⚠   1 = refused before touching any tenant (vendor / audit sink /"
  echo "release: ⚠       fixture edited without a BR-TEN-077 version bump)"
  echo "release: ⚠   2 = one or more tenants FAILED and were rolled back whole;"
  echo "release: ⚠       every other tenant kept its writes (BR-TEN-074)"
  echo "release: ⚠   3 = a declared reference list is EMPTY with no recorded reason (DEF-016)"
  echo "release: ⚠ The RELEASE still succeeds — a reference-data gap must not hold a"
  echo "release: ⚠ schema change hostage. Fix it and re-run this task alone."
fi

echo "release: done — the service may now roll"
