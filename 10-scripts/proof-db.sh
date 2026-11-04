#!/usr/bin/env bash
# ── proof-db.sh ──────────────────────────────────────────────────────────────
# ── Trace ──────────────────────────────────────────────
# Rules:   CLAUDE.md hard-won law 6 — "diff the running app against
#          05-prototype/; no gate looks at rendered output". Every rendered-output
#          check in 10-scripts/render-checks/ therefore needs a REAL, SEEDED
#          database, and every one of them builds its own from nothing.
#          CLAUDE.md hard-won law 1 — a comment claiming a guarantee is not the
#          guarantee. Hence the stamp table: the template SAYS which commit it
#          was built from, and `clone` reads it rather than trusting a name.
# Decision: 12-governance/02-decision-log.md, 2026-09-04 — "a seeded template
#          database, and what `clone` does when the template is behind the tip".
# ───────────────────────────────────────────────────────
#
# A SEEDED TEMPLATE DATABASE, CLONED IN A FRACTION OF A SECOND.
#
# ── THE COST THIS REMOVES ───────────────────────────────────────────────────
#
# Every browser walkthrough in this repository opens with the same four lines:
#
#     createdb sbh_cr070a
#     manage.py migrate && manage.py seed_demo && manage.py load_sample_data …
#
# Measured on this machine, 2026-09-04, on an empty PostgreSQL 16.13 database:
#
#     migrate                                189.3 s
#     seed_demo                               24.4 s
#     load_sample_data --tenant brazosbend    45.6 s
#     ─────────────────────────────────────────────
#     a walkthrough's database, from nothing  260.3 s   (4 min 20 s)
#
# PostgreSQL can COPY a database instead:
#
#     create database sbh_clone_x template sbh_tpl_9d40e708   0.30 s
#
# **That is 260.3 s → 0.30 s, a saving of 260 seconds per walkthrough**, paid
# again by every lane and every wave. Both figures were measured, not estimated;
# the run is quoted in the decision-log row.
#
# ── AND IT REMOVES THE OTHER HALF OF THE WARNING TOO ────────────────────────
#
# Every walkthrough header also carries: *"RUN IT AGAINST A DATABASE NOBODY ELSE
# IS SEEDING — a mid-run reseed looks exactly like a broken screen."* A clone is
# private by construction: it is a fresh database with one user, named after the
# lane that asked for it, and `drop` throws it away.
#
# ── USAGE ───────────────────────────────────────────────────────────────────
#
#   10-scripts/proof-db.sh build [--force] [--from <db>] [--no-sample] [--name N]
#       Build (or refresh) the template for the CURRENT commit and stamp it with
#       that commit. Minutes. Run it once per tip, not once per walkthrough.
#       --from <db>  copy an already-seeded database (e.g. sbh_tip) and migrate
#                    it forward instead of seeding from nothing. Seconds instead
#                    of minutes — and the stamp records that the SEED DATA came
#                    from somewhere else, so `clone` says so out loud.
#
#   10-scripts/proof-db.sh clone <label> [--stale-ok] [--kick] [--template T]
#       Clone the template into `sbh_clone_<label>` and print the DATABASE_URL.
#       Sub-second. This is the line a walkthrough header should carry.
#
#   10-scripts/proof-db.sh drop <label>          throw the clone away
#   10-scripts/proof-db.sh list                  templates, clones, stamps, users
#   10-scripts/proof-db.sh stamp <db>            which commit is this data from?
#
#   eval "$(10-scripts/proof-db.sh clone cr070a --export)"   # sets DATABASE_URL
#
# ── THE THREE TRAPS, AND WHAT THIS SCRIPT DOES ABOUT EACH ───────────────────
#
# 1 · **A TEMPLATE CANNOT BE CLONED WHILE ANYTHING IS CONNECTED TO IT.**
#     PostgreSQL answers `ERROR: source database "…" is being accessed by other
#     users`, which reads like a broken tool. `clone` asks pg_stat_activity
#     FIRST and says, in a sentence, who is holding it open and how to let go.
#     `--kick` closes those connections — and ONLY those, on the template.
#
# 2 · **A TEMPLATE BUILT FROM AN OLDER COMMIT IS WORSE THAN NO TEMPLATE**,
#     because it silently proves the wrong thing. So `clone` compares the
#     migration files in YOUR working tree with the rows in the template's
#     `django_migrations` and **REFUSES, naming every missing migration**, when
#     the template is behind.
#     ⚠ **IT REFUSES; IT DOES NOT QUIETLY RE-MIGRATE THE CLONE.** That choice is
#     argued in the decision log and the short form is: re-migrating fixes the
#     SCHEMA and cannot fix the SEED DATA. A wave that adds a migration nearly
#     always adds rows to `seed_demo` or `load_sample_data` in the same commit;
#     an auto-migrated clone would then have the new columns and none of the new
#     rows, and the walkthrough fails four checks that read exactly like a broken
#     screen — the trap the cr070-a header already warns about in capital
#     letters. A refusal costs one `build`. A silent half-fix costs a wrong
#     conclusion, and law 12 is in this file because wrong conclusions are the
#     expensive failure here, not lost time.
#     `--stale-ok` exists, must be typed, and prints exactly what it let through.
#
# 3 · **IT MUST NOT TOUCH ANOTHER LANE'S DATABASE.** `sbh_dev`, `sbh_tip`,
#     `postgres`, `template0/1` and every `sbh_cr*` walkthrough database are on a
#     hard protected list. `build` will only ever write a name it generated
#     (`sbh_tpl_*`), `clone` only `sbh_clone_*`, and `drop` refuses anything that
#     is not a `sbh_clone_*`. There is no flag that turns that off.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO/06-backend"

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-smartbillhub}"
export PGPASSWORD="${PGPASSWORD:-smartbillhub}"

TPL_PREFIX="sbh_tpl_"
CLONE_PREFIX="sbh_clone_"

# Databases this script will never create over, never drop and never kick.
# `sbh_cr*` covers every walkthrough database a sibling lane is using right now.
PROTECTED_RE='^(postgres|template0|template1|smartbillhub|sbh_dev|sbh_tip|sbh_cr.*|test_.*)$'

die() { echo "proof-db REFUSED: $*" >&2; exit 2; }
say() { echo "proof-db: $*"; }

psql_q() { psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -v ON_ERROR_STOP=1 "$@"; }
maint()  { psql_q -d postgres -tAc "$1"; }

now() { date +%s.%N; }
since() { awk -v a="$1" -v b="$(now)" 'BEGIN{printf "%.2f", b-a}'; }

guard_name() {
  # $1 = database name, $2 = required prefix, $3 = what we were asked to do
  local name="$1" prefix="$2" verb="$3"
  [[ "$name" =~ $PROTECTED_RE ]] && die "$name is on the protected list; $verb would touch a database this script does not own."
  case "$name" in
    "$prefix"*) : ;;
    *) die "$verb only ever names a database starting with '$prefix' (asked for '$name')." ;;
  esac
}

db_exists() { [ "$(maint "select 1 from pg_database where datname = '$1'")" = "1" ]; }

connections_to() {
  maint "select count(*) from pg_stat_activity where datname = '$1' and pid <> pg_backend_pid()"
}

describe_connections() {
  psql_q -d postgres -F' · ' -tA -c \
    "select 'pid ' || pid, coalesce(usename,'?'), coalesce(application_name,'(no application name)'), state
       from pg_stat_activity
      where datname = '$1' and pid <> pg_backend_pid()
      order by pid"
}

short_sha() { git -C "$REPO" rev-parse --short=8 "${1:-HEAD}"; }

tree_is_dirty() {
  [ -n "$(git -C "$REPO" status --porcelain -- 06-backend)" ]
}

# ── the seed sources, hashed ─────────────────────────────────────────────────
# Not a currency GATE (that is the migration comparison); a currency NOTE. If
# `seed_demo` or `load_sample_data` changed since the template was built, the
# schema can be perfectly current and the rows still wrong.
seed_source_hash() {
  {
    cat "$BACKEND/apps/tenancy/management/commands/seed_demo.py" 2>/dev/null || true
    cat "$BACKEND/apps/tenancy/management/commands/load_sample_data.py" 2>/dev/null || true
  } | sha256sum | cut -c1-16
}

# ── the migration files this working tree holds ──────────────────────────────
# `app name`, one per line, sorted. Files beginning with `_` are helper modules
# that live in a migrations directory and are NOT migrations — they are why a
# naive listing reports `metering _0031_helpers` as permanently pending.
ondisk_migrations() {
  find "$BACKEND/apps" -path '*/migrations/*.py' ! -name '__init__.py' ! -name '_*' \
    | sed -E 's#.*/apps/([^/]+)/migrations/([^/]+)\.py#\1 \2#' | sort
}

applied_migrations() {
  psql_q -d "$1" -tAF' ' -c "select app, name from django_migrations order by app, name" 2>/dev/null | sort || true
}

missing_migrations() {
  # on disk and NOT applied in $1 — restricted to this repo's own apps, so a
  # third-party migration we never ship cannot report as drift.
  comm -23 <(ondisk_migrations) <(applied_migrations "$1")
}

# ── the stamp ────────────────────────────────────────────────────────────────
# It lives INSIDE the database, so a clone inherits it: any lane can ask a
# walkthrough database which commit its data came from, months later.
write_stamp() {
  local db="$1" commit="$2" builtby="$3" seedhash="$4" note="$5"
  psql_q -d "$db" -q <<SQL
create table if not exists public.proof_db_stamp (
  only_row           boolean primary key default true check (only_row),
  commit_sha         text        not null,
  built_at           timestamptz not null default now(),
  built_by           text        not null,
  seed_source_sha256 text        not null,
  note               text
);
delete from public.proof_db_stamp;
insert into public.proof_db_stamp (commit_sha, built_by, seed_source_sha256, note)
values ('$commit', '$builtby', '$seedhash', '$note');
SQL
}

read_stamp() {
  psql_q -d "$1" -tAF'|' -c \
    "select commit_sha, built_at, built_by, seed_source_sha256, coalesce(note,'') from public.proof_db_stamp" 2>/dev/null || true
}

# ⚠ **THE INTERPRETER IS CHECKED ONCE, BY NAME, BEFORE ANYTHING IS BUILT.**
# `PROOF_DB_PYTHON` has always been the override and it was never documented, so
# the default `python3` is what everybody got — and on a machine where the
# project lives in a virtualenv, that interpreter cannot import the settings at
# all. The failure did not say so. `migrate` died on `ModuleNotFoundError: No
# module named 'environ'`, the build carried on, and the FIRST honest complaint
# arrived one command later as *"the template is 261 migrations behind"* — a
# true sentence about the wrong subject, which reads like a stale template
# rather than an interpreter that never ran. One lane lost its browser
# walkthrough to this and recorded the cause as machine load.
#
# So it is checked here, once, and the refusal names the fix.
require_interpreter() {
  local py="${PROOF_DB_PYTHON:-python3}"
  if ! ( cd "$BACKEND" && DJANGO_SETTINGS_MODULE=config.settings.local \
         "$py" -c 'import config.settings.local' ) >/dev/null 2>&1; then
    cat >&2 <<EOF

proof-db REFUSED: '$py' cannot import this project's settings, so every
  manage.py command below would fail — and it would fail in a way that reads
  like something else entirely (a stale template, a slow machine).

  Point PROOF_DB_PYTHON at the interpreter that runs the tests:

      PROOF_DB_PYTHON=/path/to/venv/bin/python $0 $*

  If you have no environment for this project yet:
      python3 -m venv .venv && .venv/bin/pip install -e 06-backend
EOF
    exit 2
  fi
}

manage() {
  ( cd "$BACKEND" && \
    DJANGO_SETTINGS_MODULE=config.settings.local \
    JOBS_EAGER="${JOBS_EAGER:-false}" \
    DATABASE_URL="$DB_URL" \
    "${PROOF_DB_PYTHON:-python3}" manage.py "$@" )
}

url_for() { echo "postgres://$PGUSER:$PGPASSWORD@$PGHOST:$PGPORT/$1?sslmode=disable"; }

# ── build ────────────────────────────────────────────────────────────────────
cmd_build() {
  # Before anything is dropped or created — a build that cannot migrate leaves a
  # stamped, empty template behind, and `clone` then refuses it for the wrong
  # reason.
  require_interpreter build
  local force=0 from="" sample=1 name=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --force) force=1 ;;
      --from) from="$2"; shift ;;
      --no-sample) sample=0 ;;
      --name) name="$2"; shift ;;
      *) die "build: unknown option $1" ;;
    esac
    shift
  done

  local sha commit note=""
  sha="$(short_sha)"
  commit="$(git -C "$REPO" rev-parse HEAD)"
  if tree_is_dirty; then
    commit="$commit-dirty"
    note="06-backend was modified in the working tree when this was built"
    say "⚠ 06-backend has uncommitted changes; the stamp will say '-dirty'."
  fi
  [ -n "$name" ] || name="$TPL_PREFIX$sha"
  guard_name "$name" "$TPL_PREFIX" "build"

  if db_exists "$name"; then
    [ "$force" = "1" ] || die "$name already exists. Pass --force to rebuild it, or just clone it."
    local busy; busy="$(connections_to "$name")"
    [ "$busy" = "0" ] || { describe_connections "$name" >&2; die "$name has $busy open connection(s) (above); cannot drop it."; }
    say "dropping the existing $name (--force)"
    maint "drop database $name" >/dev/null
  fi

  DB_URL="$(url_for "$name")"
  local t0 tmig tseed tsample builtby
  t0="$(now)"

  if [ -n "$from" ]; then
    db_exists "$from" || die "--from $from: no such database."
    local busy; busy="$(connections_to "$from")"
    if [ "$busy" != "0" ]; then
      describe_connections "$from" >&2
      die "--from $from has $busy open connection(s) (above). A database cannot be copied while anything is connected to it."
    fi
    say "copying $from → $name"
    maint "create database $name template $from owner $PGUSER" >/dev/null
    builtby="copied from $from, then migrated forward"
    note="${note:+$note; }SEED DATA CAME FROM $from AND WAS NOT REGENERATED"
  else
    say "creating $name"
    maint "create database $name owner $PGUSER" >/dev/null
    builtby="migrate + seed_demo$([ "$sample" = 1 ] && echo ' + load_sample_data')"
  fi

  say "migrate…"; tmig="$(now)"; manage migrate --no-input >/dev/null; tmig="$(since "$tmig")"
  say "  migrate took ${tmig}s"

  if [ -z "$from" ]; then
    say "seed_demo…"; tseed="$(now)"; manage seed_demo >/dev/null; tseed="$(since "$tseed")"
    say "  seed_demo took ${tseed}s"
    if [ "$sample" = 1 ]; then
      say "load_sample_data --tenant brazosbend…"
      tsample="$(now)"; manage load_sample_data --tenant brazosbend >/dev/null; tsample="$(since "$tsample")"
      say "  load_sample_data took ${tsample}s"
    fi
  fi

  write_stamp "$name" "$commit" "$builtby" "$(seed_source_hash)" "$note"
  say "built $name from $commit in $(since "$t0")s"
  say "clone it with:  10-scripts/proof-db.sh clone <label>"
}

# ── clone ────────────────────────────────────────────────────────────────────
cmd_clone() {
  local label="" stale_ok=0 kick=0 template="" export_only=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --stale-ok) stale_ok=1 ;;
      --kick) kick=1 ;;
      --template) template="$2"; shift ;;
      --export) export_only=1 ;;
      -*) die "clone: unknown option $1" ;;
      *) label="$1" ;;
    esac
    shift
  done
  [ -n "$label" ] || die "clone: give the clone a label, e.g. 'clone cr070a'."
  [[ "$label" =~ ^[a-z0-9_]+$ ]] || die "clone: a label is lower-case letters, digits and underscores (got '$label')."

  if [ -z "$template" ]; then
    template="$TPL_PREFIX$(short_sha)"
    if ! db_exists "$template"; then
      # fall back to the newest template that exists, then let the currency
      # check below decide whether it is good enough.
      template="$(maint "select datname from pg_database where datname like '${TPL_PREFIX}%' order by datname desc limit 1")"
      [ -n "$template" ] || die "no template exists yet. Build one:  10-scripts/proof-db.sh build"
    fi
  fi
  db_exists "$template" || die "template $template does not exist."

  local target="$CLONE_PREFIX$label"
  guard_name "$target" "$CLONE_PREFIX" "clone"
  ! db_exists "$target" || die "$target already exists. Drop it first:  10-scripts/proof-db.sh drop $label"

  # ── trap 2 · is the template behind this working tree? ────────────────────
  local missing count
  missing="$(missing_migrations "$template" || true)"
  count="$(printf '%s' "$missing" | grep -c . || true)"
  if [ "${count:-0}" -gt 0 ]; then
    {
      echo ""
      echo "  The template $template is BEHIND your working tree by $count migration(s):"
      printf '%s\n' "$missing" | sed 's/^/    /'
      echo ""
      echo "  A template built from an older commit is worse than no template: the"
      echo "  product raises a database error, or worse, renders a screen that proves"
      echo "  the wrong thing. Rebuild it — that is the only slow command here:"
      echo ""
      echo "      10-scripts/proof-db.sh build --force"
      echo ""
      echo "  Re-migrating the clone is NOT offered, on purpose: it would fix the"
      echo "  schema and could not fix the seed rows those migrations came with."
      echo "  If you have read the list above and it genuinely does not touch what"
      echo "  you are proving, say so out loud with --stale-ok."
      echo ""
    } >&2
    [ "$stale_ok" = "1" ] || die "$template is $count migration(s) behind."
    say "⚠ --stale-ok: cloning a template that is $count migration(s) behind, listed above."
  fi

  # seed-source note (not a gate — see the header)
  local stamp tpl_seed
  stamp="$(read_stamp "$template")"
  tpl_seed="$(printf '%s' "$stamp" | cut -d'|' -f4)"
  if [ -n "$tpl_seed" ] && [ "$tpl_seed" != "$(seed_source_hash)" ]; then
    say "⚠ seed_demo/load_sample_data have CHANGED since $template was built. The schema is current; the rows may not be."
  fi
  case "$stamp" in *"SEED DATA CAME FROM"*) say "⚠ $template's rows were copied from another database and not regenerated." ;; esac

  # ── trap 1 · a template cannot be cloned while anything is connected ──────
  local busy; busy="$(connections_to "$template")"
  if [ "$busy" != "0" ]; then
    if [ "$kick" = "1" ]; then
      say "closing $busy connection(s) to $template (--kick):"
      describe_connections "$template" | sed 's/^/    /'
      maint "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$template' and pid <> pg_backend_pid()" >/dev/null
      sleep 1
      busy="$(connections_to "$template")"
    fi
    if [ "$busy" != "0" ]; then
      {
        echo ""
        echo "  $template has $busy open connection(s), and PostgreSQL cannot copy a"
        echo "  database while anything is connected to it. These are holding it:"
        describe_connections "$template" | sed 's/^/    /'
        echo ""
        echo "  Close them — a psql session, a runserver still pointed at the template,"
        echo "  a stray manage.py shell — or let this script close them:  --kick"
        echo ""
      } >&2
      die "$template is busy."
    fi
  fi

  local t0; t0="$(now)"
  maint "create database $target template $template owner $PGUSER" >/dev/null
  local took; took="$(since "$t0")"

  local url; url="$(url_for "$target")"
  if [ "$export_only" = "1" ]; then
    echo "export DATABASE_URL='$url'"
    echo "export PROOF_DB_CLONE='$label'" 
    say "cloned $template → $target in ${took}s" >&2
  else
    say "cloned $template → $target in ${took}s"
    say "stamp: $(printf '%s' "$stamp" | cut -d'|' -f1,2 | tr '|' ' ')"
    echo ""
    echo "  DATABASE_URL=\"$url\""
    echo ""
    say "throw it away with:  10-scripts/proof-db.sh drop $label"
  fi
}

# ── drop ─────────────────────────────────────────────────────────────────────
cmd_drop() {
  local label="${1:-}"
  [ -n "$label" ] || die "drop: which clone? e.g. 'drop cr070a'."
  local target="$CLONE_PREFIX$label"
  guard_name "$target" "$CLONE_PREFIX" "drop"
  db_exists "$target" || { say "$target does not exist; nothing to drop."; return 0; }
  local busy; busy="$(connections_to "$target")"
  if [ "$busy" != "0" ]; then
    say "closing $busy connection(s) to your own clone $target:"
    describe_connections "$target" | sed 's/^/    /'
    maint "select pg_terminate_backend(pid) from pg_stat_activity where datname = '$target' and pid <> pg_backend_pid()" >/dev/null
    sleep 1
  fi
  maint "drop database $target" >/dev/null
  say "dropped $target"
}

# ── list / stamp ─────────────────────────────────────────────────────────────
cmd_list() {
  echo "templates and clones on $PGHOST:$PGPORT — everything else is left alone"
  printf '  %-26s %-9s %-5s %s\n' DATABASE SIZE CONNS "COMMIT / BUILT"
  local db
  for db in $(maint "select datname from pg_database where datname like '${TPL_PREFIX}%' or datname like '${CLONE_PREFIX}%' order by datname"); do
    local size conns stamp
    size="$(maint "select pg_size_pretty(pg_database_size('$db'))")"
    conns="$(connections_to "$db")"
    stamp="$(read_stamp "$db" | cut -d'|' -f1,2 | tr '|' ' ')"
    printf '  %-26s %-9s %-5s %s\n' "$db" "$size" "$conns" "${stamp:-（no stamp）}"
  done
}

cmd_stamp() {
  local db="${1:-}"
  [ -n "$db" ] || die "stamp: which database?"
  db_exists "$db" || die "$db does not exist."
  local stamp; stamp="$(read_stamp "$db")"
  [ -n "$stamp" ] || die "$db carries no proof-db stamp; it was not built by this script."
  echo "  commit      $(printf '%s' "$stamp" | cut -d'|' -f1)"
  echo "  built       $(printf '%s' "$stamp" | cut -d'|' -f2)"
  echo "  by          $(printf '%s' "$stamp" | cut -d'|' -f3)"
  echo "  seed hash   $(printf '%s' "$stamp" | cut -d'|' -f4)"
  local note; note="$(printf '%s' "$stamp" | cut -d'|' -f5)"
  [ -z "$note" ] || echo "  note        $note"
  local missing count
  missing="$(missing_migrations "$db" || true)"
  count="$(printf '%s' "$missing" | grep -c . || true)"
  if [ "${count:-0}" -gt 0 ]; then
    echo "  BEHIND      this working tree by $count migration(s):"
    printf '%s\n' "$missing" | sed 's/^/                /'
  else
    echo "  current     every migration in this working tree is applied"
  fi
}

case "${1:-}" in
  build) shift; cmd_build "$@" ;;
  clone) shift; cmd_clone "$@" ;;
  drop)  shift; cmd_drop "$@" ;;
  list)  shift; cmd_list "$@" ;;
  stamp) shift; cmd_stamp "$@" ;;
  ""|-h|--help|help)
    sed -n '/^# ── USAGE/,/^# ── THE THREE TRAPS/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    ;;
  *) die "unknown command '${1}'. Try: build · clone · drop · list · stamp" ;;
esac
