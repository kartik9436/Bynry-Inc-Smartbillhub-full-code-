#!/usr/bin/env bash
# First run. Creates the two env files and tells you the one thing you must edit.
#
# It deliberately does NOT start anything. Until DATABASE_URL points at a real
# Postgres 16 there is nothing for the backend to talk to, and a container that
# boots, fails to migrate and restart-loops teaches you less than this message.
# When the file is right:  make up
#
# Rewritten 2026-08-10. The previous version copied a ROOT .env.example that no
# settings module ever read (nothing calls environ's read_env), then announced
# "Postgres + Redis up" — compose has had neither service since the external-DB
# ruling. It printed success while doing nothing useful.
set -euo pipefail

echo "SMARTBillHub bootstrap"
command -v docker >/dev/null || { echo "docker required"; exit 1; }

for svc in 06-backend 07-frontend; do
  if [ -f "$svc/.env" ]; then
    echo "  $svc/.env exists — left alone"
  else
    cp "$svc/.env.example" "$svc/.env"
    echo "  $svc/.env created from .env.example"
  fi
done

cat <<'EOF'

Postgres is EXTERNAL and yours — there is no database container. Before starting:

  1. 06-backend/.env  → DATABASE_URL   point it at your Postgres 16
                      → DJANGO_SECRET_KEY  anything but the dev default
  2. ./10-scripts/13-provision-database.sh --all
                      PROVISION THE DATABASE. A brand-new database CANNOT run
                      migrate without this and the error does not say so — it
                      says `unrecognized configuration parameter "app.tenant_id"`
                      from inside PostgreSQL's foreign-key validation scan
                      (DEF-622). Needs a DBA/superuser connection; set
                      SBH_ADMIN_URL, or it uses `sudo -u postgres psql`.
                      ⚠ On a database that ALREADY EXISTS nothing you pull or
                      redeploy applies this. Run `--tenant-guc --role-guc
                      --verify` against it once, by hand.
  3. make up          builds both images and starts them
  4. open http://localhost:8080

TLS to that database defaults to ENCRYPTED (sslmode=require), which is what RDS
demands. A local Postgres with no TLS:  DB_SSLMODE=disable make up
EOF
