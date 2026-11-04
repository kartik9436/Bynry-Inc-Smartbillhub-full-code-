# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-014 (EP-CWP-04) — the recorded paperless consent.
#           Screen: CWP-009 (Check and send)
# Rules:    03-field-map.md §1 `portal_consent` — ⚠ *"May never be in the
#           future"* on `agreed_on` · CLAUDE.md hard rule 4 (a consent is a
#           record, so the repair is a NEW migration and never an edit to an
#           applied one) · law 14 (the CHECK exists on PostgreSQL only, and
#           the SQLite suite cannot prove it either way)
# Tests:    06-backend/tests/test_us_cwp_014_pg.py — TC-5 (a future date is
#           refused) and the case added with this migration: a consent written
#           LATER IN THE SAME TRANSACTION as other work is ACCEPTED.
# Impacts:  apps/portal/services.py record_paperless_consent · the guest
#           submit POST portal/public/applications/<token>/submit
# ───────────────────────────────────────────────────────
"""portal 0005 — the future-date CHECK now means the wall clock (DEF-CWP-3709).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHAT WAS WRONG, AND WHY EVERY TEST PASSED OVER IT
--------------------------------------------------
`portal 0003` wrote the rule as `CHECK (agreed_on <= now())`. In PostgreSQL
`now()` is the **transaction start** timestamp and never moves again for the
life of that transaction. The submit does three things in one transaction — it
numbers the service request, it stamps the draft, and only then does it write
the consent — so by the time the consent row exists, Python's clock is a few
milliseconds PAST the transaction's `now()` and the row is refused. The
constraint was reading *"not after this transaction started"* where the field
map says *"never in the future"*.

It reached a browser. Every legitimate submit was answered *"Something went
wrong on our side. Nothing was saved."* and the server said:

    django.db.utils.IntegrityError: new row for relation "portal_consent"
    violates check constraint "ck_portal_consent_agreed_on_not_future"

**The whole suite was green, on both engines, and could not have caught it.**
SQLite has no such constraint at all (law 14), and the one PostgreSQL test
wrote the consent as the FIRST statement of its savepoint, where transaction
start and wall clock are the same instant. It took clicking the screen.

THE REPAIR
----------
`clock_timestamp()` is the wall clock, re-read per row, which is what *"in the
future"* has always meant. PostgreSQL accepts it in a CHECK; proved before
this migration was written, on a scratch database:

    ALTER TABLE t ADD CONSTRAINT ck_clock CHECK (agreed_on <= clock_timestamp());
    BEGIN;
      INSERT INTO t VALUES (1, now());                    -- accepted
      SELECT pg_sleep(0.05);
      INSERT INTO t VALUES (2, clock_timestamp());        -- accepted  ← the bug
      INSERT INTO t VALUES (3, now() + interval '1 day'); -- REFUSED   ← the rule
    ERROR:  new row for relation "t" violates check constraint "ck_clock"

An applied constraint cannot be edited in place, so this drops the old name and
adds it back under the same name with the corrected expression. The rule the
constraint enforces is UNCHANGED — a consent dated in the future is still
refused by the database, in the database's own words.
"""

from django.db import migrations

#: The wall clock, re-read per row — *"never in the future"*, as the field map
#: has said since it was written. `now()` was the wrong clock, not a weaker one.
NOT_FUTURE_BY_WALL_CLOCK = (
    "ALTER TABLE portal_consent ADD CONSTRAINT ck_portal_consent_agreed_on_not_future "
    "CHECK (agreed_on <= clock_timestamp());"
)
#: What portal 0003 added, kept here so the reverse rebuilds exactly that.
NOT_FUTURE_BY_TRANSACTION_START = (
    "ALTER TABLE portal_consent ADD CONSTRAINT ck_portal_consent_agreed_on_not_future "
    "CHECK (agreed_on <= now());"
)
DROP = (
    "ALTER TABLE portal_consent "
    "DROP CONSTRAINT IF EXISTS ck_portal_consent_agreed_on_not_future;"
)


def use_wall_clock(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP)
    schema_editor.execute(NOT_FUTURE_BY_WALL_CLOCK)


def back_to_transaction_start(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP)
    schema_editor.execute(NOT_FUTURE_BY_TRANSACTION_START)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_rls_consent_and_draft"),
    ]

    operations = [
        migrations.RunPython(use_wall_clock, back_to_transaction_start),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-014@7c210243 (EP-CWP-04 + 03-field-map.md §1 `portal_consent`)
# generated: 2026-09-04 by the CR-068 wave C build lane, from DEF-CWP-3709
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · migrate on PostgreSQL 16 and on the SQLite suite · tests/test_us_cwp_014_pg.py (both directions)
# exceptions: PostgreSQL-only, exactly as portal 0003 — SQLite has no such state and the test SKIPS there rather than passing vacuously (law 14)
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
