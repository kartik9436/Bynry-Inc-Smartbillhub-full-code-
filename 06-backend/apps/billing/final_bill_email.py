# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10536 — the move-out final bill email carried no PDF and
#           printed dashes for the total due and the due date
# Ruling:   PO 2026-10-22, decision log *"Move-out final bill email: sent at
#           completion with the draft figures, at normal priority (no instant
#           email); details and PDF filled in"*; our judgments in the entry
#           after it (*"…built: our judgments…"*, points 1 and 2)
# Rules:    BR-BIL-026 (the pin issue writes is the pin rendered) · BR-BIL-024
#           (due date = bill date + the cycle's due days) · BR-BIL-030 (the
#           draft's frozen inputs are not changed here) · CLAUDE.md rule 1
#           (tenant scoping) · rule 4 (nothing issued is touched — the row is a
#           DRAFT and every write below is rolled back) · hard-won law 14
# Tests:    06-backend/tests/test_def_not_10536_move_out_final_email.py
# Impacts:  apps/billing/services.py (publishes `final_bill_email_document`) ·
#           apps/customers/seams.py (the caller, by name)
# ───────────────────────────────────────────────────────
"""The drafted final bill as a PDF, for the move-out email — without issuing it.

WHY THIS IS NOT THE PRINT PATH'S OWN CALL
────────────────────────────────────────────────────────────────────────────
`GET /invoices/{id}/document.pdf` refuses a DRAFT: a draft carries no template
pin and no due date until issue writes them (`documents._pinned`), and the
masthead, the balance forward and the usage chart are stamped into the payload
AT ISSUE (`issue._stamp_*`). A draft rendered as it stands would therefore print
a dash for the utility's name, the due date and the total due.

So this does what issue does before it renders — the same pin resolution
(`issue._pin_for_account`), the same due date (`issue._due_terms_for` +
`derive_due_date`), the same five stamps in the same order — renders through the
same `documents.render_invoice`, and then ROLLS ALL OF IT BACK. The draft row is
byte-for-byte what it was; what leaves is the page issue would keep on this day.
`tests/test_def_not_10536_move_out_final_email.py` issues the same draft
afterwards and compares the kept page with the one returned here, so a sixth
stamp added to issue and not here goes red rather than drifting.

⚠ **THE ROLLBACK IS A SAVEPOINT AND AN EXCEPTION, NOT A TIDY-UP.** Every stamp
SAVES the row. The only way to keep none of them is to leave the `atomic` block
by raising, which on PostgreSQL rolls back to the savepoint and leaves the
caller's transaction usable (hard-won law 14).

Answers `{"outcome": "rendered", pdf, filename, due_date, total_due,
currency, invoice_no}` or `{"outcome": "refused", reason, detail}` — never raises a
billing exception at the caller (B1: customers must not import one).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import models
from apps.billing.exceptions import BillingRuleError

RENDERED = "rendered"
REFUSED = "refused"


class _Rendered(Exception):
    """Carries the page OUT of the savepoint, so everything inside is undone."""

    def __init__(self, answer: dict[str, Any]) -> None:
        super().__init__("rendered; rolling the issue-time stamps back")
        self.answer = answer


def _render_as_issue_would(invoice_id: Any) -> dict[str, Any]:
    from apps.billing import documents, issue, templates_service

    locked = models.Invoice.objects.select_for_update().get(
        tenant_id=issue._tenant_id(), pk=invoice_id
    )
    if locked.status != "draft":
        raise BillingRuleError(
            f"bill {locked.invoice_no or locked.pk} is no longer a draft, so this is not the "
            "draft final bill the move-out email describes."
        )
    bill_date, due_days = issue._due_terms_for(locked.bill_run)
    due_date = issue.derive_due_date(
        bill_date,
        due_days,
        cycle_less=locked.bill_run is None or locked.bill_run.cycle_id is None,
    )
    fallback, version = templates_service.resolve_for(consumer_category=None)
    (template_id, template_version), _problem, _own = issue._pin_for_account(
        locked, run_pin=(fallback.pk, version.version_no)
    )
    lines = list(locked.lines.all().order_by("created_at", "id"))
    # The order is `issue.issue_invoice`'s, stamp for stamp.
    issue._stamp_balance_forward(locked, currency=locked.currency, due_date=due_date)
    issue._stamp_usage_history(locked)
    issue._stamp_bill_copy(locked, template_id=template_id, template_version=template_version)
    issue._stamp_bill_header(locked, bill_date=bill_date, bill_run=locked.bill_run)
    issue._stamp_plan_instalment(locked)
    locked.due_date = due_date
    rendered = documents.render_invoice(
        locked, template_id=template_id, template_version=template_version, lines=lines
    )
    name = locked.invoice_no or str(locked.pk)
    # The TOTAL DUE the page prints — previous balance, less payments, plus this
    # bill (BR-BIL-035, stamped above) — never `invoices.total`, which is the
    # current charges alone: the walk of 2026-10-22 caught the email saying
    # $388.98 beside a PDF saying 576.90. A customer in credit owes nothing, so
    # a negative figure is 0.00, which is the page's own headline
    # (`documents._total_due_field`). Unreadable arrears → None, as on the page.
    stamped = (locked.bill_payload or {}).get("total_due")
    total_due = None if stamped in (None, "") else max(Decimal(str(stamped)), Decimal("0"))
    return {
        "outcome": RENDERED,
        "pdf": bytes(rendered.pdf),
        "filename": f"{name}.pdf",
        "content_type": rendered.pdf_content_type,
        "invoice_no": locked.invoice_no,
        "due_date": due_date,
        "total_due": total_due,
        "currency": locked.currency,
    }


def final_bill_email_document(invoice_id: Any) -> dict[str, Any]:
    """The drafted final bill's page, due date and total, as issue would make them."""
    try:
        with transaction.atomic():
            raise _Rendered(_render_as_issue_would(invoice_id))
    except _Rendered as done:
        return done.answer
    except (BillingRuleError, models.Invoice.DoesNotExist) as refused:
        return {
            "outcome": REFUSED,
            "reason": "final_bill_document_not_rendered",
            "detail": str(refused),
        }


__all__ = ["REFUSED", "RENDERED", "final_bill_email_document"]
