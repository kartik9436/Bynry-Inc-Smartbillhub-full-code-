# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction — the chain the case navigates)
#           Screens: S30 · S31
# Rules:    BR-BIL-064 (the phase-4 sign-off panel follows the correction chain
#           to each bill's replacement) · BR-BIL-048 (only the LATEST document
#           in a chain is correctable) · BR-BIL-004 (an issued invoice never
#           changes — which is WHY the link is on the new bill and not the old
#           one) · BR-BIL-014 (the correction workflow this edge serves) ·
#           B2 Addendum r10 #15 (exact DDL = Eng-Lead-owned) · CLAUDE.md rule 1
#           (RLS is inherited: this is a column on an already-policied table) ·
#           rule 4 (financial immutability)
# Tests:    06-backend/tests/test_us_bil_015_single_correction.py ·
#           06-backend/tests/test_us_bil_005_release.py (TC-48, now BUILT)
# ───────────────────────────────────────────────────────
"""billing 0017 — `invoices.corrects_invoice_id`, the correction chain's rebill leg.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
column decides which figure a sign-off panel shows). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-15 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row owed in
12-governance/09-human-review-ledger.md.

THE RULING THIS IMPLEMENTS, IN THE PO'S OWN WORDS
--------------------------------------------------
2026-08-12, **OQ-120 CLOSED**, verbatim: *"Nod to add the link on the new
bill"*. The pointer lives on the REPLACEMENT and points back at what it
replaces.

**The direction is the ruling, not a design preference.** The alternative —
`corrected_by_invoice_id` on the original — would require writing a column onto
an ISSUED invoice, and an issued invoice is frozen (BR-BIL-004, hard rule 4,
and the `billing_invoice_immutable()` trigger that has enforced it since
`0002`). A chain edge that can only be created by defeating the immutability
guarantee is not an edge worth having. A rebill learns what it replaces at
INSERT, when it is still a draft and nothing is frozen yet.

⚠ THIS SUPERSEDES A PREVIOUS READING OF THE SAME OQ ID.
On 2026-08-11 the PO was recorded as ruling the link belonged *"in Histrory log
only - at account level"*, and three files were written to that reading: they
say in as many words that NO column is added, and `apps/billing/corrections.py`
writes the rebill id into its hard-rule-7 audit row instead. **That reading is
overturned.** The audit row STAYS — it is owed under rule 7 regardless — but it
is no longer the only carrier, because BR-BIL-064's panel cannot join to a log:
`release.summary_for` has been raising `BillingRuleError` naming this exact
column on every run holding a superseded bill. The superseded paragraphs are
stamped in place rather than deleted (`correction_models.py`), so a reader who
arrives at the old text arrives at the correction with it.

WHAT THE PANEL COULD NOT DO WITHOUT THIS, WORKED
--------------------------------------------------
The PO's own case: **$117.01** issued to ACC-1042 in run 1, corrected to
**$104.20** by a rebill in run 2. A panel that stays a filter on
`invoices.bill_run_id` reads **$117.01** — a figure nobody owes. A panel that
drops the superseded bill the way a VOID is dropped reads **$0.00** — and this
customer owes $104.20. Both were measured under mutation before this migration
existed (`test_us_bil_005_tc48`). With this column the first run's panel reads
**$104.20**, which is the ruled answer and was previously unreachable.

THE TRIGGER HAD TO BE RE-EMITTED, AND THAT IS THE POINT OF HALF THIS FILE
-------------------------------------------------------------------------
`0002` created `billing_invoice_immutable()`; `0006` and `0009` each re-emitted
it, and `0009` wrote down why in a sentence this migration is obeying:
**PostgreSQL stores a function body as TEXT**, so adding a column does not
teach the function that guards the table about it. A new column added without
touching the function is a column NOT covered by the freeze — silently editable
on an issued invoice, hard rule 4 failing open while every test stays green.

A chain edge is exactly the wrong column to leave editable. If
`corrects_invoice_id` could be UPDATEd after issue, a rebill could be re-pointed
at a different original after the fact, which rewrites what an auditor reads as
history without ever touching a money column. So the function is re-emitted with
one line added — `NEW.corrects_invoice_id IS DISTINCT FROM OLD.corrects_invoice_id`
— and diffing this against `0009` should show exactly that one condition and
nothing else.

**PROVED RED FIRST (hard-won law 7).** The column was added WITHOUT the
re-emitted function, an issued invoice's `corrects_invoice_id` was UPDATEd, and
Postgres accepted it. The transcript is in the lane report; only then was the
condition added and the same UPDATE refused.

WHY UNIQUE, AND WHY PARTIAL
----------------------------
`UNIQUE (tenant_id, corrects_invoice_id) WHERE corrects_invoice_id IS NOT NULL`
— one bill is replaced by AT MOST ONE bill. BR-BIL-048 (*"only the LATEST
document in a chain is correctable"*) presumes a chain; two bills claiming to
replace one original is a tree, and a tree has no latest member, so the rule
would have no referent and the panel would have no answer. The service layer
already refuses that shape twice (`corrections.refuse_unless_latest_in_chain`
reads the original's `corrected` status, and `uq_correction_bill_in_flight`
stops a second case claiming the bill); this is the guarantee that survives the
race both of those lose. PARTIAL because nearly every bill replaces nothing and
many NULLs must coexist — the same shape `uq_invoices_no` takes for the same
reason.

RLS IS NOT IN THIS MIGRATION AND DOES NOT NEED TO BE
------------------------------------------------------
`invoices` has carried `ENABLE + FORCE` and its tenant policy since `0002`. A
column added to a policied table inherits the policy — the policy is on the
ROW. What a column CAN do is leak across tenants through the FK it declares, so
the self-reference is checked in the service layer and in an isolation test
(`test_us_bil_015_single_correction.py`): a rebill in Brazos Bend may not point
at a Lone Star Ridge invoice. Postgres FKs are not RLS-aware, which is why that
is a test and not an assumption.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q

#: `0009`'s function, re-emitted with `corrects_invoice_id` in the frozen set.
#: EVERY OTHER LINE IS IDENTICAL — diffing this against `0009` should show
#: exactly one added condition. `%` is doubled because the SQL travels through
#: `schema_editor.execute`, which treats a single `%` as a parameter marker.
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
  OR NEW.corrects_invoice_id IS DISTINCT FROM OLD.corrects_invoice_id
  OR NEW.tenant_id       IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: invoice %% is %% -- only status may change after issue. What the customer was charged, and the document they were sent, are frozen; a correction is a new row (adjustments / credit_notes).',
      COALESCE(OLD.invoice_no, OLD.id::text), OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def recreate_trigger(apps_registry, schema_editor):
    """A NEW column does not rewrite the function body that guards the table.

    Same mechanism `0006` and `0009` each documented, same consequence if
    skipped: the freeze would simply not cover `corrects_invoice_id`, and a
    correction chain that can be re-pointed after the fact is a history that can
    be rewritten without an UPDATE to any money column.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RECREATE_TRIGGER_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0016_partition_invoice_lines_by_year"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="corrects_invoice",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_invoice_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrected_by",
                to="billing.invoice",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["tenant", "corrects_invoice"], name="ix_invoices_corrects"),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=Q(corrects_invoice__isnull=False),
                fields=("tenant", "corrects_invoice"),
                name="uq_invoices_one_replacement",
            ),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.CheckConstraint(
                condition=~Q(corrects_invoice=F("id")),
                name="ck_invoices_corrects_not_self",
            ),
        ),
        # MUST follow the AddField: the function body is TEXT and does not learn
        # about a column that did not exist when it was created.
        migrations.RunPython(recreate_trigger, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@f24bbae (sha256[:7] over the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-04-corrections.md §5/§8 · 12-governance/01-open-questions.md OQ-120 · 04-docs/02-decisions/02-database-design-brief.md Addendum r10 #15 · apps/billing/migrations/0009_w2_custom_snapshot.py, whose trigger this re-emits)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — schema only; the S30 correction endpoints are unbuilt) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run_gates · pytest · makemigrations --check — see the lane report for
#         the verbatim RED transcript of the un-re-emitted trigger accepting an
#         UPDATE to `corrects_invoice_id` on an ISSUED invoice.
# exceptions: (1) THIS MIGRATION CONTRADICTS THREE COMMITTED DOCSTRINGS on
#         purpose. `correction_models.py`, `corrections.py` and `0014` each say
#         no such column is added, quoting the 2026-08-11 reading of OQ-120.
#         The 2026-08-12 ruling overturned it; the paragraphs are stamped
#         SUPERSEDED in place rather than deleted.
#         (2) NO RLS BLOCK. `invoices` is already ENABLE + FORCE with its policy
#         from `0002`; a column inherits a row policy. The cross-tenant risk a
#         column CAN add is through its FK, and that is covered by an isolation
#         test rather than by a policy this migration could not write anyway.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
