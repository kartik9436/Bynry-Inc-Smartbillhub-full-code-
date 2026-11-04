-- ── 001_tenant_context_default.sql ─────────────────────────────────────────
-- The `app.tenant_id` DATABASE-LEVEL DEFAULT. HUMAN-OWNED (CLAUDE.md rule 1 🔒).
--
-- Added 2026-08-24 for DEF-622 — A FRESH DATABASE COULD NOT RUN `migrate`.
-- Apply it to the target database BEFORE the first `manage.py migrate`, as the
-- database owner or a superuser. `10-scripts/13-provision-database.sh` applies it
-- for you; this file is what it applies, and what you run by hand on a database
-- that already exists (see LAW 4 at the bottom — that case is NOT hypothetical).
--
-- WHAT BREAKS WITHOUT IT (measured, 2026-08-24, PostgreSQL 16.13)
-- ---------------------------------------------------------------
-- Every tenant table carries `FORCE ROW LEVEL SECURITY` and the B2 §3 policy
--
--     USING (tenant_id = current_setting('app.tenant_id')::uuid)
--
-- FORCE means the policy applies to the TABLE OWNER too — and the table owner is
-- the role that runs migrations. PostgreSQL validates a newly added FOREIGN KEY
-- by running an internal RI scan over the referencing table, and that scan is an
-- ordinary query: the policy is evaluated, `current_setting` runs, and on a
-- database where nobody ever set the GUC it raises
--
--     django.db.utils.ProgrammingError: unrecognized configuration parameter "app.tenant_id"
--     CONTEXT: SQL statement "SELECT fk."user_id" FROM ONLY "public"."sessions" fk
--              LEFT OUTER JOIN ONLY "public"."users" pk ON (…) WHERE pk."id" IS NULL …"
--
-- at `identity.0003_sessions_security_policy_lockout`. The migration cannot be
-- reached in any other way: `migrate` is what CREATES the tables, so no runtime
-- middleware has run and no request has set the GUC.
--
-- WHY THE NIL UUID AND NOT THE EMPTY STRING
-- -----------------------------------------
-- `core/tenancy.py` clears tenant context by SETTING the GUC to `''`, precisely
-- so the `::uuid` cast FAILS and the policy denies everything — "cleared context
-- == no access, never wrong access". That is deliberate, it is signed law, and
-- **this file does not change it**: a session that has been cleared still holds
-- `''` at SESSION level, which overrides the database default below, and still
-- errors. Verified: `tests/isolation_helpers.assert_denied_without_context`
-- clears through the shipping kernel and still gets its refusal.
--
-- But `''` cannot be the DATABASE default, because the very first thing that
-- reads it is the DDL scan above, which is not a request and has no context to
-- deny — it needs to see ZERO ROWS, not an error. So the default is the nil UUID:
--
--     00000000-0000-0000-0000-000000000000
--
-- It CASTS (so no error) and it MATCHES NOTHING (so deny-by-default is intact).
-- No tenant can carry it: ids come from `core/dbfields.py`'s RFC 9562 v7
-- generator, whose output always has version nibble 7 and a nonzero timestamp.
-- `10-scripts/13-provision-database.sh` asserts that after every run.
--
-- SECURITY STATEMENT — read this before deciding it is a weakening
-- ---------------------------------------------------------------
-- Before: a connection that never set `app.tenant_id` got an ERROR on any tenant
-- table. After: it gets ZERO ROWS. **Both deny.** What changes is loudness, and
-- only for a connection that never set context at all — which at runtime means a
-- background job or an ad-hoc `psql` that forgot, never a served request (BE-01
-- always sets or clears). 09-infra/01 §5 already DESCRIBES the after-behaviour
-- ("Ad-hoc psql sessions see zero tenant rows unless they set `app.tenant_id`");
-- this file makes that sentence true instead of merely written.
--
-- RLS `ENABLE` + `FORCE` is untouched on every table, every policy is untouched,
-- and no role is granted `BYPASSRLS` by this file.
--
-- HOW TO APPLY. Connected to the database itself (psql fills :DBNAME):
--     psql "$DATABASE_URL" -f 06-backend/db/001_tenant_context_default.sql
-- Or from any other database in the cluster, naming the target explicitly —
-- `ALTER DATABASE … SET` does not require being connected to it:
--     psql "$SBH_ADMIN_URL" -v target_db=smartbillhub \
--          -f 06-backend/db/001_tenant_context_default.sql
--
-- ⚠ LAW 4 — THIS DOES NOT REACH A HOST THAT ALREADY EXISTS.
-- This is a file in the repo. Pulling the repo changes nothing about a database
-- that is already running. On EVERY already-provisioned deployment somebody must
-- run this by hand, once, as the database owner or a superuser:
--
--     psql "$DATABASE_URL" -c "ALTER DATABASE \"<your-db>\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
--     psql "$DATABASE_URL" -c "ALTER ROLE \"<your-role>\" SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"
--
-- The second one matters as much as the first: it follows the role into databases
-- that DO NOT EXIST YET, which is what covers Django's ephemeral `test_*` database
-- (the G5 isolation suite could not run at all on a clean cluster without it) and
-- any dry-run database created later.
--
-- ⚠ AND THE ROLE SETTING WINS OVER THE DATABASE SETTING. PostgreSQL applies
-- per-database defaults first and per-role defaults after them, so if the two
-- disagree the ROLE value is what a session gets. Verified 2026-08-24 on a host
-- carrying `ALTER DATABASE … SET app.tenant_id = ''` (the broken legacy state) plus
-- the role statement above: the session started with the sentinel, not `''`. So on
-- an existing host the ROLE statement alone is enough to unblock it — run both
-- anyway, because a DIFFERENT role connecting to that database still needs the
-- database default. (Session-level `SET` beats both, which is why a request that
-- clears its context to `''` still refuses. That is the point, not a leak.)
--
-- ⚠ AND A RE-SEQUENCED MIGRATION SET REACHES SUCH A HOST NO BETTER THAN THIS FILE
-- DOES. `migrate` is a no-op on a database that already applied the old sequence,
-- so nothing re-runs and nothing self-heals. The two statements above are the
-- whole manual remediation, and they are needed BEFORE the next migration that
-- adds a foreign key to a tenant table — not after it fails.
--
-- It is safe on a live database: `ALTER DATABASE … SET` affects only sessions
-- STARTED AFTER it, changes no data, takes no lock on any table, and cannot
-- widen what any existing connection can see. Check what a host has today with
--
--     psql "$DATABASE_URL" -c "SELECT current_setting('app.tenant_id', true)"
--
-- NULL  → unprovisioned; a fresh `migrate` here fails with DEF-622 case 1.
-- ''    → the state most existing hosts are in by accident of history; a fresh
--         `migrate` here fails with DEF-622 case 2 (invalid input syntax for
--         type uuid: ""). Run the ALTER above.
-- 000…0 → provisioned.
-- ───────────────────────────────────────────────────────────────────────────

-- Default the target to whatever database this session is connected to, unless
-- the caller named one with `-v target_db=…`.
\if :{?target_db}
\else
\set target_db :DBNAME
\endif

ALTER DATABASE :"target_db" SET app.tenant_id = '00000000-0000-0000-0000-000000000000';

-- Report what the database now carries, so an operator running this by hand sees
-- the result rather than a bare ALTER DATABASE. (The value below takes effect on
-- the NEXT session — this one still holds whatever it started with.)
SELECT d.datname AS database,
       s.setconfig AS session_defaults
FROM pg_database d
LEFT JOIN pg_db_role_setting s
       ON s.setdatabase = d.oid AND s.setrole = 0
WHERE d.datname = :'target_db';
