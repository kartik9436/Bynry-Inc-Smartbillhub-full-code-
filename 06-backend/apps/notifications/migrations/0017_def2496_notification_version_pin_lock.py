# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2496 — BR-NOT-025 is written and NOTHING enforces it; the two
#           sides refuse DIFFERENT things.
# Rules:    BR-NOT-025 (a version any SENT DOCUMENT points at is ARCHIVED and
#           NEVER DELETED) · BR-BIL-027 (the audit-lock) · BR-NOT-027 (a legal
#           document is frozen as the document when it is sent) · NFR-8
#           (retained forever) · CLAUDE.md hard rule 4 · rule 1
# Tests:    06-backend/tests/test_def2496_pinned_version_delete_guard.py
# ───────────────────────────────────────────────────────
"""notifications 0017 — the DRAFT-shaped hole in `0006`'s delete guard.

HUMAN-OWNED (migration ordering and RLS are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-30 under the PO ruling of 2026-08-09;
row owed in `12-governance/09-human-review-ledger.md`.

WHAT WAS TRUE BEFORE THIS, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
A bare `DELETE` could remove the DRAFT template version that a queued
disconnection letter was pinned to, and the message could then never be produced
again — which is the exact case BR-NOT-025 was written for.

WHY `0006` DID NOT ALREADY COVER IT, AND WHY THAT WAS NOT AN OVERSIGHT
────────────────────────────────────────────────────────────────────────────
`trg_ntv_append_only` refuses a DELETE on any NON-DRAFT row. That covers a
published or an archived version completely, and for the ordinary lifecycle it
is enough: resolution never pins a draft, so a pinned draft should not exist.

**"Should not exist" is not "cannot exist", and the suite already knew it.**
`test_us_not_006_a_pinned_draft_is_refused_too` exists precisely because a caller
may stamp a draft's version number onto a queue row by hand, and its own
docstring says so: *"the day a caller stamps a draft's version onto a row by
hand, the delete must still refuse."* The SERVICE refused that case. The database
waved it through — so the one check that survives a shell, a data migration and a
future endpoint was the one that did not cover it.

This trigger is that gap and nothing else. It is a PIN check, so it never refuses
a delete `0006` would have allowed for any reason other than a pin: an unpinned
draft still deletes, which is T5-02 step 4 and is asserted.

WHY A SECOND TRIGGER RATHER THAN AN EDIT TO `0006`'s FUNCTION
────────────────────────────────────────────────────────────────────────────
The two guards answer different questions — *is this row still editable* and *is
anything pointing at it* — and they are ratified separately (`0006` cites NFR-8
and BR-BIL-026; this cites BR-NOT-025). Keeping them apart means each can be read,
reversed and re-signed on its own, and it leaves `0006` byte-identical for the
lane working in this module today. PostgreSQL fires BEFORE DELETE triggers in
name order; either refusal is correct and neither depends on the other.

WHICH PINS ARE COUNTED — and why this side counts ONE table where billing counts two
────────────────────────────────────────────────────────────────────────────
`outbound_messages` alone, which is `template_service.pin_count`'s own
definition. Measured on the development database: of its 181 rows, 87 carry a
notification template's id and 94 carry a BILL template's id (that column is
POLYMORPHIC, which is why `billing/0025` has to count this table too). Nothing
else in this product pins a notification template version — `invoices` pins bill
layouts, and signed contracts have no store yet. So this trigger reads only its
own module's table and crosses no line.

RLS AND WHICH WAY THIS FAILS — the question a 🔒 path has to answer
────────────────────────────────────────────────────────────────────────────
Not `SECURITY DEFINER`. It runs as the invoking role under `FORCE ROW LEVEL
SECURITY`, so the count sees the current tenant's rows. Every reachable case
fails CLOSED: inside a tenant context `OLD.tenant_id` IS `app.tenant_id` (the
DELETE could not have matched the row otherwise) so every pin is visible; with
the GUC unset `current_setting('app.tenant_id')` RAISES rather than returning
NULL, so the DELETE matches nothing; and a superuser bypasses RLS and therefore
sees MORE rows, never fewer.

PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
Run against live PostgreSQL with no trigger present, verbatim:

    Failed: DID NOT RAISE Exception

— the draft was deleted and the queued message left unreproducible.

REVERSIBILITY
────────────────────────────────────────────────────────────────────────────
Dropping the trigger and function restores the previous behaviour exactly; no
row, column or index is touched. Reversing re-opens the hole, which is what a
rollback here costs.

Postgres only. sqlite has no triggers, so the tests carry `requires_postgres` and
run on the Postgres tier.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: ⚠ `%` IS **SINGLE** — `PostgresOnlySQL` is a `RunSQL` and performs no
#: %-substitution, so a doubled `%%` would reach PL/pgSQL verbatim. `0006` and
#: `billing/0019` both record measuring exactly that.
PIN_LOCK_SQL = """
CREATE OR REPLACE FUNCTION notifications_template_version_pin_locked() RETURNS trigger AS $$
DECLARE
  pins integer;
BEGIN
  SELECT count(*) INTO pins
    FROM outbound_messages m
   WHERE m.tenant_id        = OLD.tenant_id
     AND m.template_id      = OLD.template_id
     AND m.template_version = OLD.version;

  IF pins > 0 THEN
    RAISE EXCEPTION 'BR-NOT-025 / BR-BIL-027: notification template version % is pinned by % sent message(s) and can never be deleted; it is the evidence of what those customers were actually sent. Archive is the ratified door, and publishing a NEW version is how a template changes.',
      OLD.version, pins;
  END IF;

  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ntv_pin_locked ON notification_template_versions;
CREATE TRIGGER trg_ntv_pin_locked
  BEFORE DELETE ON notification_template_versions
  FOR EACH ROW EXECUTE FUNCTION notifications_template_version_pin_locked();
"""

REVERSE_PIN_LOCK_SQL = """
DROP TRIGGER IF EXISTS trg_ntv_pin_locked ON notification_template_versions;
DROP FUNCTION IF EXISTS notifications_template_version_pin_locked();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0016_cr048_b6_event_attribution"),
    ]

    operations = [
        PostgresOnlySQL(sql=PIN_LOCK_SQL, reverse_sql=REVERSE_PIN_LOCK_SQL),
    ]
