#!/usr/bin/env bash
# ── 13-provision-database.sh ─────────────────────────────────────────────────
#
# THE STEP BEFORE `migrate`, AND THEN `migrate` ITSELF, ONE STEP AT A TIME.
# Turn an empty PostgreSQL 16 cluster into a database this product can migrate
# into — role, database, extensions, the `app.tenant_id` session default that
# nothing in this repo used to provision, and then the migration sequence applied
# **step by step, in dependency order, one migration per process**.
#
# WHY IT EXISTS: DEF-622, 2026-08-24. A genuinely fresh database could not run
# `manage.py migrate` AT ALL. The first deploy was blocked outright. `09-infra/`,
# `06-backend/db/`, `06-backend/docker-entrypoint.sh` and `10-scripts/` contained
# no `ALTER DATABASE`, no `ALTER ROLE` and no `set_config('app.tenant_id', …)` —
# the whole tree's only `ALTER ROLE` was in `tests/isolation_helpers.py`, and it
# REVOKES bypass. Every environment we had carried the setting by accident of
# history, so only a first deploy hit it, and nothing in CI creates a first
# deploy.
#
# The reproduction, on PostgreSQL 16.13, quoted so nobody has to take it on
# trust — an empty database, app role NOSUPERUSER NOBYPASSRLS:
#
#   Applying identity.0003_sessions_security_policy_lockout...
#   django.db.utils.ProgrammingError: unrecognized configuration parameter "app.tenant_id"
#   CONTEXT: SQL statement "SELECT fk."user_id" FROM ONLY "public"."sessions" fk
#            LEFT OUTER JOIN ONLY "public"."users" pk ON (…) WHERE pk."id" IS NULL …"
#
# then, after `ALTER DATABASE … SET app.tenant_id = ''`:
#
#   django.db.utils.DataError: invalid input syntax for type uuid: ""
#
# Both come from one mechanism: `FORCE ROW LEVEL SECURITY` applies the B2 §3
# policy to the TABLE OWNER, the owner is whoever runs migrations, and PostgreSQL
# validates a newly added FOREIGN KEY with an ordinary scan that the policy is
# evaluated against. See `06-backend/db/001_tenant_context_default.sql`.
#
# ── THE RULING THAT SHAPES THIS SCRIPT (PO, 2026-08-24, OQ-354) ─────────────
#
# An earlier draft of this file solved the second failure by granting the app role
# `BYPASSRLS` for the duration of one `migrate`. **The Product Owner ruled that
# out.** Verbatim:
#
#   "You will ahve to do the migration step by step - you will ahve to consier
#    a depands on b , b depends on c - so build the sequence of migration"
#
# So there is **no `BYPASSRLS` anywhere in this script**, no flag that grants it,
# and no environment variable that turns it on. The migration is applied as a
# SEQUENCE instead, and `--verify` fails the run if the app role turns out to hold
# bypass or superuser from anywhere else.
#
# ── WHAT "STEP BY STEP" BUYS, CONCRETELY ────────────────────────────────────
#
# `app.tenant_id` is a SESSION variable. `manage.py migrate` applies every pending
# migration on ONE connection, so a data step that clears tenant context to `''`
# poisons **every later migration in the same run** — their FK-validation scans
# inherit a value that cannot be cast. Applying one migration per PROCESS gives
# each step a fresh connection, which starts from the database/role default (the
# castable NO-TENANT sentinel) rather than from the previous step's leftovers.
# That is the dependency chain made real: each step starts from the state the
# previous step is required to have left, instead of from whatever it happened to
# leave.
#
# Measured on an empty database, 2026-08-24: eleven steps apply cleanly this way.
#
# ── THE ONE STEP THAT CANNOT BE ORDERED OUT FROM HERE ───────────────────────
#
# Step 12, `assets.0003_meter_types_and_read_methods`, poisons **itself**, and no
# runner outside the migration can reach between its parts:
#
#   CreateModel MeterType/ReadMethod  → Django DEFERS the FK constraints
#   PostgresOnlySQL(CATALOG_POLICIES) → ENABLE + FORCE RLS on the new tables
#   RunPython(seed…)                  → ends with set_config('app.tenant_id','')
#   << schema_editor exit >>          → the deferred FK constraints are created
#                                        and VALIDATED — under `''` → DataError
#
# The dependency that is violated is inside one migration: **the FK validation
# depends on a castable tenant context, and the data step destroys it before the
# validation runs.** Two sibling migrations have the identical shape:
# `metering.0016_br_met_101_common_area` and
# `tenancy.0004_settings_families_logo_and_hosted_lists`.
#
# THE FIX, AND IT IS THREE LINES: each of those three files ends its data step
# with
#
#     cursor.execute("SELECT set_config('app.tenant_id', '', false)")
#
# and must instead leave the NO-TENANT sentinel that the rest of the sequence
# runs on:
#
#     cursor.execute("SELECT set_config('app.tenant_id', %s, false)",
#                    ["00000000-0000-0000-0000-000000000000"])
#
# MEASURED, 2026-08-24, PostgreSQL 16.13: with only that substitution, and with
# **no BYPASSRLS and no superuser anywhere**, every migration in every app applies
# to an empty database, exit 0. It changes nothing at runtime (`core/tenancy.py`
# still clears a request's context to `''` on purpose, so a cleared session still
# fails the cast and still sees nothing) and nothing on a database that has
# already migrated (those `RunPython`s never run again there).
#
# It is not applied yet because those files are committed migrations and
# `.github/workflows/migration-guard.yml` blocks modifying one — that exception is
# the remaining half of OQ-354. Until it lands, this script stops at step 12 and
# prints exactly the above rather than reaching for a grant the PO ruled out.
#
# ── USAGE ───────────────────────────────────────────────────────────────────
#
#   10-scripts/13-provision-database.sh [steps…]
#
#     --create-role        CREATE ROLE (LOGIN, NOSUPERUSER, NOBYPASSRLS)   [admin]
#     --create-db          CREATE DATABASE … OWNER <role>                  [admin]
#     --tenant-guc         apply db/001_tenant_context_default.sql         [admin]
#     --role-guc           the same default on the ROLE, so it also covers every
#                          database that role creates later — above all Django's
#                          ephemeral `test_*` databases                    [admin]
#     --extensions         apply db/000_extensions.sql                     [app]
#     --migrate            apply the migration sequence STEP BY STEP, one
#                          migration per process, in dependency order
#     --verify             re-check the invariants and print them          [app]
#     --all                every step above, in that order
#
#   Environment:
#     DATABASE_URL          the APP's connection string. Required.
#     DJANGO_SETTINGS_MODULE required for --migrate (no default — see
#                           docker-entrypoint.sh for why guessing it is worse).
#     SBH_ADMIN_URL         a superuser/DBA libpq URL for the admin steps. If
#                           unset the script falls back to `sudo -u postgres psql`,
#                           which is what a local cluster wants.
#     SBH_DB_NAME/SBH_DB_ROLE  override the name/role parsed from DATABASE_URL.
#     SBH_DB_PASSWORD       required by --create-role.
#     PYTHON                python interpreter for manage.py (default python3).
#
# ── LAW 3: THE UNSAFE OPTION IS THE ONE YOU TYPE ────────────────────────────
#
# Nothing in this script grants anything to anybody. The role it creates is typed
# `NOSUPERUSER NOBYPASSRLS` explicitly rather than inheriting a default, and it is
# re-typed on every run so a role that picked up either attribute somewhere else
# loses it here. `--verify` reads `pg_roles` back and fails the run if the app role
# is a superuser or holds `BYPASSRLS`, because either one silently voids hard rule
# 1 for the whole product.
#
# The tenant-context default is not a relaxation: the nil UUID casts (so the RLS
# policy evaluates instead of erroring) and matches no row (so deny-by-default is
# unchanged). RLS stays `ENABLE`+`FORCE` on every table and enforced on every
# connection, including this script's own.
#
# ⚠ LAW 4 — WHAT THIS SCRIPT DOES NOT DO FOR YOU.
# Nothing here reaches a deployment that already exists. Adding this file to the
# repo changes no running database, and neither does a redeploy — **and a
# re-sequenced migration set does not reach a host that already ran the old
# sequence either.** On an already-provisioned host somebody must run, once, by
# hand, as the database owner or a superuser:
#
#     psql "$DATABASE_URL" \
#       -c "ALTER DATABASE \"<your-db>\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
#     psql "$DATABASE_URL" \
#       -c "ALTER ROLE \"<your-role>\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
#
# or equivalently `10-scripts/13-provision-database.sh --tenant-guc --role-guc --verify`.
# It changes no data, locks no table, and applies to sessions started after it.
# Most existing hosts currently hold `''` (the state that fails DEF-622 case 2);
# check yours with
#     psql "$DATABASE_URL" -c "SELECT current_setting('app.tenant_id', true)"
# An already-migrated host keeps booting either way — `migrate` is a no-op there —
# so the symptom does not appear until the NEXT migration that adds a foreign key
# to a tenant table. That is why this is a thing to do now, not when it breaks.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO/06-backend"
NIL_TENANT='00000000-0000-0000-0000-000000000000'
PYTHON="${PYTHON:-python3}"

die() { echo "PROVISION REFUSED: $*" >&2; exit 2; }
step() { echo; echo "── $*"; }

DO_ROLE=0 DO_DB=0 DO_GUC=0 DO_ROLE_GUC=0 DO_EXT=0 DO_MIGRATE=0 DO_VERIFY=0
[ $# -gt 0 ] || die "no steps given — try --all, or read the header of this file"
for arg in "$@"; do
  case "$arg" in
    --create-role) DO_ROLE=1 ;;
    --create-db) DO_DB=1 ;;
    --tenant-guc) DO_GUC=1 ;;
    --role-guc) DO_ROLE_GUC=1 ;;
    --extensions) DO_EXT=1 ;;
    --migrate) DO_MIGRATE=1 ;;
    --verify) DO_VERIFY=1 ;;
    --all) DO_ROLE=1; DO_DB=1; DO_GUC=1; DO_ROLE_GUC=1; DO_EXT=1; DO_MIGRATE=1; DO_VERIFY=1 ;;
    -h|--help) sed -n '2,160p' "${BASH_SOURCE[0]}"; exit 0 ;;
    --migrate-with-bypassrls-window|--bypassrls*)
      die "there is no BYPASSRLS option. The PO ruled it out on 2026-08-24 (OQ-354):
  \"You will ahve to do the migration step by step - you will ahve to consier a
   depands on b , b depends on c - so build the sequence of migration\"
  Use --migrate, which applies the sequence one migration per process." ;;
    *) die "unknown argument: $arg" ;;
  esac
done

command -v psql >/dev/null || die "psql is not on PATH"
[ -n "${DATABASE_URL:-}" ] || die "DATABASE_URL is not set — it names the database to provision"

# ── who and what, parsed from the app's own URL so the two cannot disagree ───
read -r URL_DB URL_ROLE <<<"$("$PYTHON" - <<'PY'
import os, urllib.parse as u
p = u.urlparse(os.environ["DATABASE_URL"])
print((p.path or "/").lstrip("/") or "-", u.unquote(p.username or "-"))
PY
)"
DB_NAME="${SBH_DB_NAME:-$URL_DB}"
DB_ROLE="${SBH_DB_ROLE:-$URL_ROLE}"
[ "$DB_NAME" != "-" ] || die "DATABASE_URL names no database"
[ "$DB_ROLE" != "-" ] || die "DATABASE_URL names no role (set SBH_DB_ROLE)"

# ── the two connections, kept apart on purpose ──────────────────────────────
# admin: superuser/DBA. Used ONLY for CREATE ROLE / CREATE DATABASE and the two
#        `SET app.tenant_id` defaults. It grants nothing and never runs migrate.
# app:   $DATABASE_URL. Everything the product itself would do.
if [ -n "${SBH_ADMIN_URL:-}" ]; then
  admin() { psql -X -q -v ON_ERROR_STOP=1 "$SBH_ADMIN_URL" "$@"; }
  ADMIN_DESC="SBH_ADMIN_URL"
else
  admin() { sudo -n -u postgres psql -X -q -v ON_ERROR_STOP=1 "$@"; }
  ADMIN_DESC="sudo -u postgres psql (SBH_ADMIN_URL unset)"
fi
app() { psql -X -q -v ON_ERROR_STOP=1 "$DATABASE_URL" "$@"; }

need_admin() {
  admin -tAc "SELECT 1" >/dev/null 2>&1 \
    || die "no admin connection ($ADMIN_DESC). Set SBH_ADMIN_URL to a superuser/DBA URL."
}

echo "SMARTBillHub database provisioning (DEF-622)"
echo "  database : $DB_NAME"
echo "  app role : $DB_ROLE"
echo "  admin    : $ADMIN_DESC"

# ── 1 · the role ────────────────────────────────────────────────────────────
# NOSUPERUSER NOBYPASSRLS is TYPED, not inherited from a default: a superuser
# bypasses RLS unconditionally and BYPASSRLS exempts the role from every policy,
# so either one silently voids hard rule 1 for the whole product. Law 3 — the
# unsafe option must be the one somebody types, and it is not typed here.
if [ "$DO_ROLE" = 1 ]; then
  step "role $DB_ROLE"
  need_admin
  [ -n "${SBH_DB_PASSWORD:-}" ] || die "--create-role needs SBH_DB_PASSWORD"
  # The password goes over STDIN, never in argv — `ps` is world-readable and
  # 09-infra/02 §"Secret handling" bans secrets in shell history and CI logs.
  # Single quotes are doubled so a password containing one cannot end the literal.
  esc_pw="${SBH_DB_PASSWORD//\'/\'\'}"
  esc_role="${DB_ROLE//\'/\'\'}"
  admin <<SQL
DO \$provision\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$esc_role') THEN
    EXECUTE format(
      'CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOREPLICATION PASSWORD %L',
      '$esc_role', '$esc_pw');
  END IF;
  -- Typed every run, not only at creation: a role that picked up SUPERUSER or
  -- BYPASSRLS somewhere else loses it here rather than quietly keeping it.
  EXECUTE format('ALTER ROLE %I NOSUPERUSER NOBYPASSRLS', '$esc_role');
END
\$provision\$;
SQL
  unset esc_pw
  echo "   ok — exists, NOSUPERUSER NOBYPASSRLS"
fi

# ── 2 · the database ────────────────────────────────────────────────────────
if [ "$DO_DB" = 1 ]; then
  step "database $DB_NAME"
  need_admin
  admin -v db="$DB_NAME" -v owner="$DB_ROLE" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner')
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SELECT format('GRANT ALL ON DATABASE %I TO %I', :'db', :'owner') \gexec
SQL
  echo "   ok — exists, owned by $DB_ROLE"
fi

# ── 3 · the tenant-context default — THE FIX FOR DEF-622 CASE 1 ─────────────
if [ "$DO_GUC" = 1 ]; then
  step "app.tenant_id database default"
  need_admin
  admin -v target_db="$DB_NAME" -f "$BACKEND/db/001_tenant_context_default.sql"
  echo "   ok — sessions now start with app.tenant_id = $NIL_TENANT"
  echo "   (a cleared session still SETs '' and still errors — deny-by-default intact)"
fi

# ── 3b · the same default on the ROLE — and this one is not optional in CI ──
#
# `--tenant-guc` fixes ONE database. Django's test runner CREATES A NEW DATABASE
# (`test_<name>`) from template1 on every run and migrates it, so the test
# database is a first deploy every single time — and it hits DEF-622 case 1
# exactly. Measured on a clean cluster, 2026-08-24, before this step existed:
#
#   pytest tests/test_tenant_isolation.py -m isolation
#   E django.db.utils.ProgrammingError: unrecognized configuration parameter "app.tenant_id"
#   6 errors in 1.74s
#
# That is the G5 tenant-isolation suite — the release gate for hard rule 1 — and
# it could not run at all. `ALTER ROLE … SET` follows the role into every
# database it connects to, including databases that do not exist yet, so it is
# what makes the isolation suite, `09-infra/03`'s dry-run and any future test
# database work without anyone remembering this step again.
#
# It grants nothing. The value is the same non-matching sentinel, and a session
# that clears context still SETs '' at session level and still errors.
if [ "$DO_ROLE_GUC" = 1 ]; then
  step "app.tenant_id role default for $DB_ROLE"
  need_admin
  esc_role_guc="${DB_ROLE//\'/\'\'}"
  admin <<SQL
DO \$provision\$
BEGIN
  EXECUTE format('ALTER ROLE %I SET app.tenant_id = %L', '$esc_role_guc', '$NIL_TENANT');
END
\$provision\$;
SQL
  echo "   ok — every database this role connects to, including test_* databases"
fi

# ── 4 · extensions ──────────────────────────────────────────────────────────
# pgcrypto and citext are TRUSTED in PostgreSQL 16, so the database owner can
# create them without a superuser; tenancy migration 0001 also creates them
# idempotently, so this step is belt-and-braces rather than load-bearing.
if [ "$DO_EXT" = 1 ]; then
  step "extensions"
  app -f "$BACKEND/db/000_extensions.sql"
  echo "   ok — $(app -tAc "SELECT string_agg(extname, ', ' ORDER BY extname) FROM pg_extension")"
fi

# ── 5 · migrate, STEP BY STEP (PO ruling 2026-08-24) ────────────────────────
#
# Django's own `migrate --plan` is the dependency order — it is the graph
# resolved, `a depends on b, b depends on c` already answered by the migration
# graph itself. This reads that plan and applies each entry in its OWN PROCESS,
# so no step can inherit a session variable from the step before it.
if [ "$DO_MIGRATE" = 1 ]; then
  step "migrate — step by step, one migration per process"
  [ -n "${DJANGO_SETTINGS_MODULE:-}" ] \
    || die "DJANGO_SETTINGS_MODULE is not set (see 06-backend/.env.example)"

  plan_file="$(mktemp)"
  trap 'rm -f "$plan_file"' EXIT
  ( cd "$BACKEND" && "$PYTHON" manage.py migrate --plan ) \
    | grep -E '^[a-z_]+\.[0-9]{4}' > "$plan_file" || true

  total="$(wc -l < "$plan_file" | tr -d ' ')"
  if [ "$total" = "0" ]; then
    echo "   nothing to apply — the database is already at the latest migration"
  else
    echo "   $total migration(s) to apply, in dependency order"
    n=0
    while read -r target; do
      [ -n "$target" ] || continue
      n=$((n + 1))
      migration_app="${target%%.*}"
      migration_name="${target#*.}"
      printf '   [%3d/%3d] %s ... ' "$n" "$total" "$target"
      if ( cd "$BACKEND" && "$PYTHON" manage.py migrate "$migration_app" "$migration_name" \
             --noinput > "$plan_file.out" 2>&1 ); then
        echo "ok"
      else
        echo "FAILED"
        echo
        sed -n '$p' "$plan_file.out" >&2
        cat >&2 <<EOF

PROVISION REFUSED at step $n of $total: $target

  If the last line above reads

      DataError: invalid input syntax for type uuid: ""

  this is the residual half of DEF-622 and the migration poisons ITSELF — no
  runner outside it can reach between its parts. Its internal order is

      CreateModel …            Django DEFERS the FK constraints
      RunSQL  (RLS policies)   ENABLE + FORCE on the new tables
      RunPython (data step)    ends with set_config('app.tenant_id','')
      << migration exit >>     the deferred FKs are created AND VALIDATED,
                               and the validation scan is evaluated against
                               that '' — which cannot be cast to uuid.

  The dependency violated is inside the migration: the FK validation depends on
  a castable tenant context, and the data step destroys it before the validation
  runs. Three migrations have this shape:

      apps/assets/migrations/0003_meter_types_and_read_methods.py
      apps/metering/migrations/0016_br_met_101_common_area.py
      apps/tenancy/migrations/0004_settings_families_logo_and_hosted_lists.py

  Each must leave the NO-TENANT sentinel instead of the empty string:

      cursor.execute("SELECT set_config('app.tenant_id', %s, false)",
                     ["$NIL_TENANT"])

  Measured: with only that substitution the whole sequence applies to an empty
  database, exit 0, with no BYPASSRLS and no superuser. See OQ-354 — the change
  needs the append-only migration-guard exception the PO's ruling implies.

  If instead the last line reads

      ProgrammingError: unrecognized configuration parameter "app.tenant_id"

  the tenant-context default was never applied. Run --tenant-guc --role-guc.

  A partially applied sequence is safe to resume: Django rolls each migration
  back on failure, so re-running this script continues from where it stopped.
EOF
        exit 1
      fi
    done < "$plan_file"
    echo "   ok — $n/$total migrations applied, each in its own session"
  fi
fi

# ── 6 · verify. Read the database, do not read the code. ────────────────────
if [ "$DO_VERIFY" = 1 ]; then
  step "verify"
  fail=0

  # (1) the app role is not exempt from RLS. This is the one that matters, and
  #     it is a REFUSAL, not a warning: a superuser or a BYPASSRLS role makes
  #     every isolation proof in this repo vacuous.
  read -r is_super has_bypass <<<"$(app -tAc \
    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user" \
    | tr '|' ' ')"
  echo "   app role $DB_ROLE: rolsuper=$is_super rolbypassrls=$has_bypass"
  if [ "$is_super" != "f" ] || [ "$has_bypass" != "f" ]; then
    echo "   ✗ the app role BYPASSES row-level security — hard rule 1 is not in force" >&2
    echo "     fix: ALTER ROLE \"$DB_ROLE\" NOSUPERUSER NOBYPASSRLS;" >&2
    fail=1
  fi

  # (2) the tenant-context default is the castable sentinel.
  guc="$(app -tAc "SELECT coalesce(current_setting('app.tenant_id', true), '<absent>')")"
  echo "   app.tenant_id default: ${guc:-<empty string>}"
  if [ "$guc" != "$NIL_TENANT" ]; then
    echo "   ✗ expected $NIL_TENANT — run --tenant-guc --role-guc (and see LAW 4 above)" >&2
    fail=1
  fi

  # (3) RLS is still ENABLED *and* FORCED on every tenant-scoped table, found by
  #     the presence of a tenant_id column so a table nobody remembered counts.
  read -r tenant_tables forced policies <<<"$(app -tAc "
    WITH t AS (
      SELECT c.oid, c.relrowsecurity AND c.relforcerowsecurity AS forced
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                         AND a.attnum > 0 AND NOT a.attisdropped
      WHERE n.nspname = 'public' AND c.relkind IN ('r','p'))
    SELECT count(*), count(*) FILTER (WHERE forced),
           (SELECT count(*) FROM pg_policies WHERE schemaname='public')
    FROM t" | tr '|' ' ')"
  echo "   tenant-scoped tables: $tenant_tables · ENABLE+FORCE: $forced · policies: $policies"
  if [ "$forced" -lt 1 ]; then
    echo "   ✗ no table is FORCED — migrations did not apply and tenant data is unprotected" >&2
    fail=1
  fi

  # (4) nothing can be wearing the sentinel as its real tenant id. If a tenant
  #     ever carried the nil UUID it would be visible to every contextless
  #     session, which is the one way this fix could become a hole.
  nil_tenants="$(app -tAc "SELECT count(*) FROM tenants WHERE id = '$NIL_TENANT'" 2>/dev/null || echo skip)"
  echo "   tenants carrying the nil sentinel as their id: $nil_tenants"
  if [ "$nil_tenants" != "0" ] && [ "$nil_tenants" != "skip" ]; then
    echo "   ✗ a tenant carries the nil UUID — it would be visible without tenant context" >&2
    fail=1
  fi

  [ "$fail" = 0 ] || die "verification failed — see the ✗ lines above"
  echo "   ok — all four invariants hold"
fi

echo
echo "provisioning done."
