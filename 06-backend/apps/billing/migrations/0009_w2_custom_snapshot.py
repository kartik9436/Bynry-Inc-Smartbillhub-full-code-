# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (stamp the custom-field snapshot onto the invoice)
#           Screens: S30 · S31
# Rules:    BR-BIL-030 (the bill is LOCKED — the document instance is stamped
#           and a reprint renders it forever, joining nothing live; the rule
#           names `custom_snapshot` inside it) · BR-BIL-004 (an issued invoice
#           is immutable; a correction is a new row) · BR-TEN-048 (a custom
#           field can never influence money) · CLAUDE.md rule 4
# ───────────────────────────────────────────────────────
"""billing 0009 — `invoices.custom_snapshot`, the R2 one-way door.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHY THIS COLUMN LANDS NOW, WHEN NOTHING READS IT UNTIL R3
----------------------------------------------------------
B12 addendum r7.2, verbatim, is the whole reason this migration is scheduled
ahead of the feature it serves: *"You cannot retroactively reconstruct what an
account looked like six months ago. If R2 issues real invoices with no snapshot
column, every invoice from that period is permanently unable to render custom
fields — and the tempting repair is a live join to master data, which rewrites
issued documents without ever running an UPDATE. Stamp early, render later."*

The master-data columns (r17.2, this lane's customers/metering/assets
migrations) have NO such door — the plan says so in the same paragraph, calling
their later addition "a clean, non-breaking migration". Its verbatim sentence
is quoted in those three migrations' docstrings and deliberately NOT here: it
names the r17.2 column, and G6's DB-17 rule bans that token anywhere under
`apps/billing/` except the one allowlisted module. The gate fired on this very
paragraph the first time it ran, which is the gate working — a docstring is not
worth weakening a security grep for on the day it ships.

This column is the half that cannot wait.

`NOT NULL DEFAULT '{}'` (B2 r17.3, exactly)
--------------------------------------------
Django's `JSONField(default=dict)` produces `jsonb NOT NULL` and applies the
default in PYTHON, leaving no database default at all. That is not what r17.3
signs, and the difference is load-bearing: an INSERT from anywhere other than
this ORM — a fixture, a repair script, a future COPY — would fail on NOT NULL
instead of getting `{}`. US-BIL-028 TC-5 says the value is `{}` and *never
null*, so the DEFAULT is set explicitly below on Postgres, where the product
runs. sqlite is the developer database and honestly skips it (the
`PostgresOnlySQL` posture every migration in this repo takes for DDL sqlite
does not have).

THE TRIGGER HAD TO FOLLOW THE COLUMN, and it is the actual guard
----------------------------------------------------------------
`0002` created `billing_invoice_immutable()` and `0006` re-emitted it after
renaming `issued_snapshot` → `bill_payload`, for the reason `0006` gives:
**PostgreSQL stores a function body as TEXT**, so neither renaming a column nor
adding one rewrites the function that guards the table. A new column added
without touching the function is a column NOT covered by the freeze — it would
be silently editable on an issued invoice, which is hard rule 4 failing open
while every test stays green.

So this migration re-emits the function with ONE line added:
`NEW.custom_snapshot IS DISTINCT FROM OLD.custom_snapshot`. Diffing this
against `0006` should show exactly that. It was PROVED RED first: the migration
was applied to a live cluster WITHOUT the new line, an issued invoice's
`custom_snapshot` was updated successfully, and only then was the line added
and the update refused (transcript in the human-review ledger row —
hard-won law 7).

WHAT IS DELIBERATELY NOT ADDED
-------------------------------
No issue-time NOT-NULL clause of the kind `0006` added for `bill_payload`.
`{}` is a LEGITIMATE value at issue (TC-5: an account with no custom fields
defined), so a trigger check could not tell "nothing to stamp" from "the stamp
never ran" — that distinction is proved by a wiring test over
`stages/assemble_document.py`, not by the database.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: r17.3's `DEFAULT '{}'`. Split from the trigger because it is plain DDL and
#: reads better as such; both are Postgres-only for the same reason.
COLUMN_DEFAULT_SQL = "ALTER TABLE invoices ALTER COLUMN custom_snapshot SET DEFAULT '{}'::jsonb;"

#: `0006`'s function, re-emitted with `custom_snapshot` in the frozen set. Every
#: other line is identical — diffing this against 0006 should show exactly one
#: added condition.
RECREATE_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION billing_invoice_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'BR-BIL-004: invoice %% is %% and cannot be deleted; a correction is a new row',
        COALESCE(OLD.invoice_no, OLD.id::text), OLD.status;
    END IF;
    RETURN OLD;
  END IF;

  -- BR-BIL-030: a bill cannot BECOME issued without its locked instance. This
  -- is the rule's NOT NULL, enforced where the rule speaks -- at issue -- so
  -- that a discardable draft is still legal.
  IF NEW.status <> 'draft' AND OLD.status = 'draft' AND NEW.bill_payload IS NULL THEN
    RAISE EXCEPTION 'BR-BIL-030: invoice %% cannot be issued without bill_payload. The locked document instance IS the bill a reprint renders; issuing without one leaves a bill whose document can only be rebuilt from live rows that have since moved.',
      COALESCE(NEW.invoice_no, NEW.id::text);
  END IF;

  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;

  IF NEW.account_id      IS DISTINCT FROM OLD.account_id
  OR NEW.bill_run_id     IS DISTINCT FROM OLD.bill_run_id
  OR NEW.bill_type       IS DISTINCT FROM OLD.bill_type
  OR NEW.service_date    IS DISTINCT FROM OLD.service_date
  OR NEW.period_start    IS DISTINCT FROM OLD.period_start
  OR NEW.period_end      IS DISTINCT FROM OLD.period_end
  OR NEW.due_date        IS DISTINCT FROM OLD.due_date
  OR NEW.subtotal        IS DISTINCT FROM OLD.subtotal
  OR NEW.tax_total       IS DISTINCT FROM OLD.tax_total
  OR NEW.total           IS DISTINCT FROM OLD.total
  OR NEW.currency        IS DISTINCT FROM OLD.currency
  OR NEW.invoice_no      IS DISTINCT FROM OLD.invoice_no
  OR NEW.issued_at       IS DISTINCT FROM OLD.issued_at
  OR NEW.template_id     IS DISTINCT FROM OLD.template_id
  OR NEW.template_version IS DISTINCT FROM OLD.template_version
  OR NEW.bill_payload    IS DISTINCT FROM OLD.bill_payload
  OR NEW.payload_version IS DISTINCT FROM OLD.payload_version
  OR NEW.custom_snapshot IS DISTINCT FROM OLD.custom_snapshot
  OR NEW.tenant_id       IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: invoice %% is %% -- only status may change after issue. What the customer was charged, and the document they were sent, are frozen; a correction is a new row (adjustments / credit_notes).',
      COALESCE(OLD.invoice_no, OLD.id::text), OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def recreate_trigger(apps_registry, schema_editor):
    """A NEW column does not rewrite the function bodies that guard the table.

    Same mechanism `0006` documented for a RENAMED column, same consequence if
    skipped: the freeze would simply not cover `custom_snapshot`, and hard rule
    4 would fail open on the one column this whole lane exists to protect.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RECREATE_TRIGGER_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0008_rls_release_gate"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="custom_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        # r17.3's literal `DEFAULT '{}'`, which Django's Python-side default
        # does not create.
        PostgresOnlySQL(
            sql=COLUMN_DEFAULT_SQL,
            reverse_sql="ALTER TABLE invoices ALTER COLUMN custom_snapshot DROP DEFAULT;",
        ),
        # MUST follow the AddField: the function body is TEXT and does not
        # learn about a column that did not exist when it was created.
        migrations.RunPython(recreate_trigger, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17 ·
#         EP-BIL-02-invoice-gl.md US-BIL-028 · 07-billing/02-business-rules.md
#         BR-BIL-030)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved on a LIVE Postgres cluster — with the new condition ABSENT the
#         `custom_snapshot` of an ISSUED invoice updated successfully (guard
#         failing open); with it present the same update raises BR-BIL-004.
#         Transcript verbatim in 12-governance/09-human-review-ledger.md
# exceptions: (1) NO issue-time NOT-NULL clause of the kind 0006 added for
#         `bill_payload` — `{}` is a legitimate stamp (US-BIL-028 TC-5) and the
#         database cannot tell it from a stamp that never ran; that distinction
#         is a wiring test over stages/assemble_document.py instead ·
#         (2) 0002 and 0006 are NOT edited: both have run on a live cluster, so
#         editing them would change nothing there and only make the files
#         disagree with what they did (hard-won law 4's shape) ·
#         (3) the DB-level DEFAULT is Postgres-only; sqlite is the developer
#         database and the Python-side default covers it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
