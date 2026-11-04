# ── Trace ──────────────────────────────────────────────
# Change:  REQ-03 redrawn, six steps into four (PO 2026-09-29). Task 4:
#          *"use american english check = not cheque"* — verbatim, and it is
#          not only a label.
# Rules:   CLAUDE.md hard rule 4 — `service_requests` is NOT one of the four
#          financially immutable tables (issued invoices, invoice lines,
#          payments, journal entries), so a correcting UPDATE here is lawful.
#          Nothing in `payments` is touched by this migration and nothing in
#          it may be: `counter_receipts.method_code` already spells the tender
#          `check` and is payments' to own (B2 §2).
#          CLAUDE.md hard rule 1 — the UPDATE is unconditional across every
#          tenant BY DESIGN: a migration runs as the owner outside any request,
#          `app.tenant_id` is unset, and a per-tenant loop here would silently
#          match nothing (the `DEF-PAY-6166` shape).
#          CLAUDE.md hard rule 7 — no `audit_log` row: this is a spelling
#          correction applied by a migration, not a money action by an actor,
#          and there is no actor to name.
# Tests:   06-backend/tests/test_req03_four_steps_server.py
# ───────────────────────────────────────────────────────
"""`service_requests.fee_method`: `cheque` → `check`.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-29 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Migration ordering is a
CLAUDE.md 🔒 path; the row is `12-governance/09-human-review-ledger.md`,
2026-09-29, lane REQ03-SERVER.

The column stored the only British spelling of a tender left in the product.
`payments` has spelled it `check` since `BR-PAY-026`, `tenancy.PaymentMethod`
seeds `check`, and `payments.counter_receipts.FEE_METHOD_TO_TENDER` existed
only to translate one into the other at the boundary.

⚠ **THE REVERSE IS DELIBERATELY A NO-OP AND SAYS SO.** Writing `check` back to
`cheque` would re-introduce the spelling the PO ruled out, and it would do it
to rows created after this migration as well as to the ones it changed —
un-correcting work nobody asked to un-correct. The column is free text, so a
rollback of the CODE alone leaves every value readable: `collect_fee` accepts
both spellings and `FEE_METHOD_TO_TENDER` maps both.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from __future__ import annotations

from django.db import migrations


def spell_it_check(apps, schema_editor):
    ServiceRequest = apps.get_model("customers", "ServiceRequest")
    ServiceRequest.objects.filter(fee_method="cheque").update(fee_method="check")


def leave_it_alone(apps, schema_editor):
    """See the module docstring: un-correcting is not a rollback."""


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0074_rls_def_gov_7821_attribute_history_deny_on_unset"),
    ]

    operations = [
        migrations.RunPython(spell_it_check, leave_it_alone),
    ]
