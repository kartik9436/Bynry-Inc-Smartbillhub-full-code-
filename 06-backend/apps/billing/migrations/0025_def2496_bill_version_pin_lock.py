# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2496 — BR-NOT-025 is written and NOTHING enforces it.
# Rules:    BR-NOT-025 (a version any SENT DOCUMENT points at is ARCHIVED and
#           NEVER DELETED) · BR-BIL-027 (the audit-lock) · BR-BIL-026 (the pin
#           is frozen at issue) · BR-NOT-026 (one screen, TWO stores) ·
#           CLAUDE.md hard rule 4 (financial immutability) · rule 1 (tenant
#           scoping — see "RLS AND WHICH WAY THIS FAILS" below)
# Tests:    06-backend/tests/test_def2496_pinned_version_delete_guard.py
# ───────────────────────────────────────────────────────
"""billing 0025 — a pinned bill-template version cannot be DELETEd, in the engine.

HUMAN-OWNED (migration ordering and RLS are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-30 under the PO ruling of 2026-08-09;
row owed in `12-governance/09-human-review-ledger.md`.

WHAT WAS TRUE BEFORE THIS, IN ONE SENTENCE A PERSON CAN ACT ON
────────────────────────────────────────────────────────────────────────────
A `manage.py shell`, a data migration or any future endpoint could delete the
bill-layout version that 94 issued bills were pinned to, and nothing anywhere —
no constraint, no trigger, no test — would have objected; the loss would surface
the first time somebody asked for a reprint.

`templates_service.delete_version` refuses it and names the count, and that
refusal is worth having: it is the half a person reads. It is also the only half
there was, and it is bypassed by not calling it.

WHY A TRIGGER AND NOT A FOREIGN KEY — THE MEASUREMENT, NOT THE PREFERENCE
────────────────────────────────────────────────────────────────────────────
Both candidate fixes were recorded on DEF-2496 and they are not equivalent. The
foreign key is the stronger shape in the abstract and it is **not available**,
for a reason measured on the development database rather than reasoned about:

  * `outbound_messages.template_id` IS POLYMORPHIC. Of its 181 rows, **94 carry
    a BILL template's id** — every one a `pdf_print` row whose `source_type` is
    `invoice` — and the other 87 carry a NOTIFICATION template's id. A single
    foreign key cannot point at two tables, so `ADD CONSTRAINT` would be
    REFUSED, today, on live rows. This is not a migration that is expensive; it
    is one that does not exist.
  * The version tables' unique key is THREE columns (`tenant_id, template_id,
    version_no`), so even on the `invoices` side the FK would be a three-column
    composite written in raw SQL — and `MATCH SIMPLE` leaves a row with a
    template but no version number unchecked, which is a hole in the guarantee
    rather than the guarantee.
  * Both `invoices` and `outbound_messages` are money-path tables; `ADD
    CONSTRAINT` takes an ACCESS EXCLUSIVE lock and a full validation scan.

⚠ **THIS OVERTURNS THE REASONING IN MIGRATION `0019`, DELIBERATELY AND IN ITS
OWN WORDS.** `0019` wrote: *"A trigger could count the pins, but it would then be
a second implementation of the rule — and the service's version can name the
count in its refusal."* The first clause is true and is not a cost; the second is
the argument the NOTIFICATION side had already answered when `0019` was written.
`notifications/0006` runs a service check AND a trigger and says why: *"The check
here is the readable half — it names the reason a person can act on — and it is
deliberately NOT the only one: a shell, a data migration and a future endpoint
all bypass this function and none of them bypasses the trigger."* Two
implementations is the ratified pattern, not a smell. The readable refusal keeps
naming the count; this is the floor under it.

WHY THE TRIGGER COUNTS **TWO** TABLES AND CROSSES A MODULE LINE TO DO IT
────────────────────────────────────────────────────────────────────────────
`templates_service.pin_count` counted `invoices` and nothing else, so a bill
version pinned by a printed-bill row and by no issued invoice read as UNPINNED.
BR-NOT-025 says *any sent document*, and a printed bill is one. The 94 rows above
are exactly that shape. So this counts both, and it is the DATABASE that carries
the cross-table read: a trigger on billing's own table reading `outbound_messages`
is not billing's ORM reaching into notifications (B1 — the readable half asks
through `delivery_seam`, by name, as it always has). The guarantee has to sit
below both modules because the row it protects is pinned from both.

RLS AND WHICH WAY THIS FAILS — the question a 🔒 path has to answer
────────────────────────────────────────────────────────────────────────────
The function is NOT `SECURITY DEFINER`. It runs as the invoking role with
`FORCE ROW LEVEL SECURITY` applied, so its two counts see only the current
tenant's rows. That is correct rather than merely acceptable, and every reachable
case fails CLOSED:

  * In a tenant context, `OLD.tenant_id` IS `app.tenant_id` (the version row
    would not be visible to the DELETE otherwise), so every pin on that version
    is visible and counted.
  * With `app.tenant_id` unset, `current_setting('app.tenant_id')` RAISES rather
    than returning NULL — the DELETE never matches a row and the trigger never
    has to be right.
  * A superuser bypasses RLS entirely, so the counts see MORE rows, never fewer.

`SECURITY DEFINER` would buy nothing here and would add a search-path attack
surface to a 🔒 path, so it is deliberately not used.

PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
`tests/test_def2496_pinned_version_delete_guard.py` was written and run against
live PostgreSQL FIRST, with no trigger present. Verbatim:

    Failed: DID NOT RAISE Exception     (a version an issued bill pinned)
    Failed: DID NOT RAISE Exception     (a draft a queued message pinned)
    assert 0 == 1  where 0 = pin_count(<BillTemplateVersion …>)

REVERSIBILITY
────────────────────────────────────────────────────────────────────────────
Dropping the trigger and the function restores the previous behaviour exactly —
no row, column or index is touched by this migration. Reversing it re-opens the
hole, which is the honest description of what a rollback here costs.

Postgres only. sqlite has no triggers, so on the developer database the readable
half in `templates_service.delete_version` is the whole of the guard — which is
why the tests for this carry `requires_postgres` and are run on the Postgres
tier rather than skipped and forgotten.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

#: ⚠ `%` IS **SINGLE** HERE. `PostgresOnlySQL` is a `RunSQL` and passes the
#: statement with NO params, so it performs no %-substitution and a doubled `%%`
#: would reach PL/pgSQL verbatim — `0019` records measuring exactly that
#: (`psycopg.errors.SyntaxError: too many parameters specified for RAISE`).
PIN_LOCK_SQL = """
CREATE OR REPLACE FUNCTION billing_template_version_pin_locked() RETURNS trigger AS $$
DECLARE
  bill_pins  integer;
  print_pins integer;
BEGIN
  SELECT count(*) INTO bill_pins
    FROM invoices i
   WHERE i.tenant_id        = OLD.tenant_id
     AND i.template_id      = OLD.template_id
     AND i.template_version = OLD.version_no;

  SELECT count(*) INTO print_pins
    FROM outbound_messages m
   WHERE m.tenant_id        = OLD.tenant_id
     AND m.template_id      = OLD.template_id
     AND m.template_version = OLD.version_no;

  IF bill_pins + print_pins > 0 THEN
    RAISE EXCEPTION 'BR-NOT-025 / BR-BIL-027: bill template version % is pinned by % issued bill(s) and % sent document row(s) and can never be deleted. Each of those renders from THIS version whenever it is reprinted, re-sent or disputed, for the full seven-year retention window. Archive it instead: an archived version stops being offered for new assignments and keeps rendering every document already pinned to it.',
      OLD.version_no, bill_pins, print_pins;
  END IF;

  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bill_tpl_version_pin_locked ON bill_template_versions;
CREATE TRIGGER trg_bill_tpl_version_pin_locked
  BEFORE DELETE ON bill_template_versions
  FOR EACH ROW EXECUTE FUNCTION billing_template_version_pin_locked();
"""

REVERSE_PIN_LOCK_SQL = """
DROP TRIGGER IF EXISTS trg_bill_tpl_version_pin_locked ON bill_template_versions;
DROP FUNCTION IF EXISTS billing_template_version_pin_locked();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0024_cr048_e9_bill_version_archived_at"),
        # The trigger body reads `outbound_messages`, so that table must exist
        # before this runs. Named as a dependency rather than assumed — the
        # ordering IS the 🔒 path here.
        ("notifications", "0001_w3_outbound_queue"),
    ]

    operations = [
        PostgresOnlySQL(sql=PIN_LOCK_SQL, reverse_sql=REVERSE_PIN_LOCK_SQL),
    ]
