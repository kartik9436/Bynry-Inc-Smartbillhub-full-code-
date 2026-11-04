-- Bootstrap extensions (runs via docker-entrypoint-initdb.d). HUMAN-OWNED.
-- Also created idempotently by apps/tenancy/migrations/0001_initial.py so a
-- migrated database never depends on this file having run first.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;   -- B2/DB-15: citext emails
-- ⚠ `btree_gist` IS WHAT MAKES B2 §2's NO-OVERLAP CONSTRAINT POSSIBLE, AND ITS
-- ABSENCE IS WHY THAT CONSTRAINT HAS NEVER EXISTED (`DEF-RAT-8000`).
-- B2 §2 signs `tariff_versions` with
--   EXCLUDE USING gist (tenant_id WITH =, tariff_id WITH =, daterange(...) WITH &&)
-- An EXCLUDE that mixes an equality column with a range operator needs the
-- equality operator classes gist does not ship with — that is the whole of what
-- this extension adds. Migration `rating/0001` could not materialise the
-- constraint without it, materialised nothing, and said nothing; `rating/0004`
-- reported the gap in its own header and left it "for the human review of this
-- row", which never happened. Meanwhile `services._apply_batch_to_schedule`
-- carried a comment claiming the constraint was there (hard-won law 1).
-- Ottumwa Water Works then ran four versions of one sewer schedule in force on
-- one date and its one-time bills refused with `AmbiguousSchedule`.
CREATE EXTENSION IF NOT EXISTS btree_gist;
-- B2 O-1 (residue, r16 #5): uuidv7() — PKs default app-side (core/dbfields.py
-- RFC 9562 shim). If pg_uuidv7 is installed on the target (PO R6 nod), a
-- DB-side `ALTER COLUMN id SET DEFAULT uuidv7()` pass is a deploy-time
-- addition; nothing in the schema requires it.
