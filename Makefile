.PHONY: help up down build logs ps sh migrate seed test test-server golden isolation gates lint bootstrap

help:             ## List targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

# ── Containers (root docker-compose.yml — two services, external Postgres) ────

env-init:  ## Create the two .env files from their committed templates (run once)
	@test -f 06-backend/.env  || cp 06-backend/.env.example  06-backend/.env
	@test -f 07-frontend/.env || cp 07-frontend/.env.example 07-frontend/.env
	@echo "06-backend/.env and 07-frontend/.env ready — edit DATABASE_URL and DJANGO_SECRET_KEY before any real use."

# ⚠ THE BACKEND CONTAINER NO LONGER MIGRATES AT START-UP (CR-144-BRC07, 2026-09-28).
# `docker-entrypoint.sh` used to run `migrate` in every web container, which on ECS
# with two tasks is a concurrent migration with no advisory lock. It is now a
# separate step — `docker-release.sh` in a deployed environment, and this target
# locally. So `up` runs it explicitly: same order (extensions → migrate → sweep),
# same script, one container.
#
# ⚠ **THESE TWO TARGETS READ THE OTHER WAY ROUND UNTIL 2026-09-28 AND WOULD NOW
# DEADLOCK ON A FRESH DATABASE (`DEF-INF-7703`).** `up` was
# `docker compose up -d --build` followed by `$(MAKE) release`, and `release` was
# `docker compose exec backend …`. Since `DEF-INF-7683` the backend REFUSES to
# boot when migrations are pending — and on an empty database *every* migration
# is pending — so `up` left the backend crash-looping under
# `restart: unless-stopped` and `exec` cannot attach to a restarting container.
# The migrate could never be reached, by the one command every new machine runs.
#
# ⚠ **THE OLD COMMENT'S REASON WAS ALSO NOT QUITE TRUE**: it said release must
# follow `up` *"because it needs the database container to be accepting
# connections"*, and there is no database container — Postgres is EXTERNAL and
# named only by `DATABASE_URL` (see the note at the top of `docker-compose.yml`).
# What release needs is a reachable database, not a started service.
#
# So release is a **one-off container that never passes through
# `docker-entrypoint.sh`**, which is exactly the shape 09-infra/02-aws-runbook.md
# §H6 already prescribes on ECS: a separate task definition from the same image
# overriding `entryPoint` to `/app/docker-release.sh`. `--no-deps` keeps it a
# true one-off — the migrate needs no Redis and no workers.
#
# ⚠ **AND IT NOW RUNS IN THE PIPELINE'S OWN ORDER — BUILD → RELEASE → ROLL.**
# That is §H6 step by step, and it means the backend starts for the first time
# against a schema that is already current, so its boot check passes rather than
# being something to work around.
#
# `migrate` retries nothing; if the database is not reachable yet, run
# `make release` again.
up: env-init               ## Build and start the app  →  http://localhost:8080
	docker compose build
	$(MAKE) release
	docker compose up -d

release:          ## Migrate + reference-data sweep — what the deploy pipeline runs before a rollout
	docker compose run --rm --no-deps --entrypoint /app/docker-release.sh backend

down:             ## Stop and remove the containers
	docker compose down

build:            ## Rebuild both images without starting them
	docker compose build

logs:             ## Follow both services' logs
	docker compose logs -f

ps:               ## Show container state and health
	docker compose ps

sh:               ## Shell in the backend container (non-root)
	docker compose exec backend sh

migrate:          ## Run migrations in the running backend container
	docker compose exec backend python manage.py migrate

seed:             ## Brazos Bend demo fixture — demo/staging only, refuses under production settings
	docker compose exec backend python manage.py seed_demo

bootstrap:        ## First run: create the .env files and print what to edit
	@./10-scripts/01-bootstrap.sh

# ── Host-side checks (no containers involved) ─────────────────────────────────

test:             ## Backend unit tests
	cd 06-backend && python -m pytest -q

test-server:      ## Frontend static-server + /api pass-through tests
	cd 07-frontend && npm run test:server

golden:           ## Golden billing tests (GT-1..11) — release gate
	cd 06-backend && python -m pytest tests/golden -q

isolation:        ## Tenant-isolation suite — release gate, zero tolerance
	cd 06-backend && python -m pytest tests/test_tenant_isolation.py -q

gates:            ## Merge-blocking gate suite (G1-G12)
	python3 10-scripts/gates/run_gates.py

lint:
	cd 06-backend && python -m ruff check .
