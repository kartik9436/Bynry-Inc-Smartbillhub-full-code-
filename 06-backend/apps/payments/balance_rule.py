# ── Trace ──────────────────────────────────────────────
# Change:   CR-186-BRC10 · T14 — one balance formula, every reader
# Defect:   DEF-PAY-10340 (failed and cancelled payments counted as money
#           received, because every reader excluded only `processing`)
# Ruling:   decision log 2026-10-21, "The payment lifecycle, stated by the PO
#           for every method", rulings 3, 4 and 6; "No 'Reconciled' payment
#           status", ruling 1
# Rules:    BR-BIL-035 · BR-PAY-041 · US-PAY-002 TC-1 · CLAUDE.md hard rule 2
# Tests:    06-backend/tests/test_cr186_balance_counts_posted_and_cleared.py
# ───────────────────────────────────────────────────────
"""WHICH payment rows count toward what an account owes — stated ONCE.

HUMAN-OWNED · HUMAN-REVIEW-PENDING (money: every balance in the product reads
this set). AI-authored 2026-10-21 under the PO ruling of 2026-08-09; its row is
in `12-governance/09-human-review-ledger.md`.

THE FORMULA (PO, 2026-10-21)
----------------------------
    balance = Σ issued bills' own charges + migrated opening
            − Σ payments whose status is in BALANCE_COUNTED_PAYMENT_STATUSES
              (deposits excluded; reversing rows are negative)
            + Σ refunds issued or cleared

PO verbatim: *"when paymet is posted ; we need to change the opening balance
formalue so that opening balance reflect the new opening balance; if payment is
cancled then it will not be considered … you will ahve to take refunds or
credits into account while calcualting opening balance"*.

Shown to the PO: a $150.00 bill and $120.00 posted → $30.00; a $20.00 refund
issued on top → $50.00.

WHY THREE STATUSES
------------------
* `posted` — the record is created and applied at posting, for every method.
* `cleared` — the same money, once its deposit batch is reconciled with the
  bank. Clearing changes WHEN the bank agreed, never whether it counts.
* `reversed` — the NEGATIVE row a bounce or return writes
  (`reversal.reverse_payment`). The original keeps its own status, so the pair
  nets to zero, or to what stood for a partial return.

And never:
* `cancelled` — both the original and its reversing row carry it, so a
  cancelled payment is excluded whole rather than netted by luck.
* `failed` — a cheque voided at the counter (`cheques.void_cheque`); it writes
  no reversing row, so before this set it was counted in full.
* `processing` — no longer written by new payments; existing rows stay and
  never count (decision log 2026-10-21, "No 'Reconciled' payment status").

A credit note is a `type='credit'` payment row and rides the same sum; a
deposit is never credit (US-PAY-002 TC-1) and every reader still excludes it by
PURPOSE, separately from this set.

⚠ **THIS IS AN ALLOW LIST, NOT AN EXCLUDE LIST, ON PURPOSE.** The defect it
fixes is exactly what an exclude list does when a status is added: every reader
said *"every payment except processing"*, and `failed` and `cancelled` joined
the counted side with no edit anywhere near a balance. A seventh status now
joins the NOT-counted side until somebody decides otherwise here.
"""

from __future__ import annotations

from apps.payments import models

#: The payment statuses a balance counts. Read by every balance reader; a test
#: asserts the exact set (`test_the_counted_set_is_exactly_posted_cleared_and_
#: reversed`), so widening it is a red test that names the ruling.
BALANCE_COUNTED_PAYMENT_STATUSES: tuple[str, ...] = (
    models.PAYMENT_POSTED,
    models.PAYMENT_CLEARED,
    models.PAYMENT_REVERSED,
)

#: The receipts a customer actually made and that stand — the set a *Last
#: payment* panel shows. The balance set without the negative reversing row.
RECEIPT_STATUSES: tuple[str, ...] = (models.PAYMENT_POSTED, models.PAYMENT_CLEARED)


def counted(queryset, *, field: str = "status"):
    """Narrow a payments queryset to the rows a balance counts."""
    return queryset.filter(**{f"{field}__in": BALANCE_COUNTED_PAYMENT_STATUSES})
