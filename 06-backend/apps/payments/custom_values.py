# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W5 — payment custom fields, captured at entry
#           only. PO 2026-10-02 (`aa4d30f8b`), R3: *"Payments IN as
#           capture-at-entry only"*; Part 2 row 14: *"Record payment (at entry
#           only) · Payment detail · Can't be corrected afterwards; never used
#           to apply the payment to bills"*.
#           Screens: S35 (Record payment — Input) · S33 (Payment detail — View)
# Rules:    BR-TEN-048 (UNCHANGED: a custom value never reaches allocation,
#           deposit, refund, dunning, rating, tax or a ledger posting) ·
#           BR-TEN-052 (required only where typed in) · CLAUDE.md hard rule 4
#           (written at INSERT; `payments/0014`'s allow list does not move) ·
#           hard rule 1
# Tests:    06-backend/tests/test_cr161_w5_payment_custom_fields.py
# Impacts:  apps/payments/services.record_payment (the INSERT) ·
#           apps/payments/api.account_payments (the S35 door) ·
#           apps/payments/payment_detail.payment_detail (the S33 read) ·
#           10-scripts/gates/g06_forbidden.py (DB-17 allows this file)
# ───────────────────────────────────────────────────────
"""The ONE place in `apps/payments/` that handles a payment's custom answers.

G6 / DB-17 bans the token `custom_data` from every money path. For payments the
ban is opened for exactly the capture and the display — this file, the column
declaration, the migration that adds it, and the named statements that hand the
blob to the INSERT and to the detail payload. **Allocation, deposit batching,
refunds, dunning and the ledger handoff stay banned**, and the gate's self-test
pins a read in each of them as a failure.

WHY THE S35 DOOR IS "THE BODY CARRIES THE KEY"
----------------------------------------------
One endpoint (`POST /accounts/{id}/payments`) serves the Record payment page
AND three other doors (Take payment on the account, the build dialogs, Add
correction) that draw no custom fields. BR-TEN-052 as amended says *"Required
means required only where it's typed in"*, so a required payment field must
block S35 and must NOT block a door that never showed it. The Record payment
page always sends `custom_data` — `{}` when the utility has no fields — and the
other doors never do; so the key's presence names the screen. A door that
omits it records the payment with `{}` and nothing is required of it.

There is no edit path and none is to be added: the answers are written by the
INSERT and the database refuses a later UPDATE (`payments/0046`).
"""

from __future__ import annotations

from typing import Any

from apps.payments import settings_seam

#: The one entity name and the two slots (`apps/tenancy/custom_fields.SLOTS`).
ENTITY = "payments"
RECORD_PAYMENT_SCREEN = "S35"
PAYMENT_DETAIL_SCREEN = "S33"

BODY_KEY = "custom_data"


def entry_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    """What the S35 door hands `services.record_payment`: the submitted answers
    and the screen they were typed on — or nothing, for a door that draws none."""
    if BODY_KEY not in payload:
        return {"custom_data": None, "custom_data_screen": None}
    return {
        "custom_data": payload.get(BODY_KEY) or {},
        "custom_data_screen": RECORD_PAYMENT_SCREEN,
    }


def capture(submitted: Any, *, screen: str | None) -> dict[str, Any]:
    """The cleaned blob the INSERT writes. `{}` for a door that sent nothing —
    no registry read, so the eight non-screen callers of `record_payment` pay
    nothing for this feature."""
    if submitted is None and screen is None:
        return {}
    return settings_seam.validate_entry_answers(submitted or {}, screen=screen)


def for_display(payment: Any) -> dict[str, Any]:
    """The stored answers, as Payment detail (S33) shows them. Read-only: the
    screen draws `CustomFieldsView` and no control that could send one back."""
    stored = getattr(payment, "custom_data", None)
    return dict(stored) if isinstance(stored, dict) else {}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-161-BRC10 W5 (change request + decision log 2026-10-02 + BR-TEN-046/048/052)
# generated: 2026-10-02 by lane CF-W5
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: G6 (DB-17 allows this file by name) · G7 · pytest
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
