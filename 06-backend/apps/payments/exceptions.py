# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (single payment entry — the refusals a clerk sees)
#           Screens: S22 · S35
# Rules:    BR-PAY-002 (append-only; a correction is a new row) · BR-PAY-012
#           (purpose) · BR-PAY-021 (both dates) · BR-PAY-036 (a payment is
#           ALWAYS accepted — so a refusal here is never about the account's
#           standing) · CLAUDE.md rule 2 (money is a Decimal, never a float)
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py
# Impacts:  apps/payments/services.record_payment · apps/payments/ledger_seam
#           (translates the ledger's PostingError into this vocabulary —
#           DEF-047's lesson) · apps/payments/billing_seam
# ───────────────────────────────────────────────────────
"""The one error type the payments write path raises, and why it is its own.

`PaymentRuleError` is what `record_payment` raises when a payment cannot be
recorded under the rules — a zero amount, a float, an account that is not this
tenant's, a purpose whose linkage does not exist, a ledger that refuses the
entry.

**It is deliberately NOT one of the `core.errors` catalog exceptions.** Those
carry an HTTP status because they answer a request; this one is raised inside
batch paths that answer none, and its callers are other services.

CORRECTED 2026-08-11: this said *"this module has no HTTP surface yet (the
S22/S33/S35 endpoints are their own stories)"*, and that stopped being true the
hour `apps/payments/api.py` mounted `POST /accounts/{id}/payments` and
`GET /payments`. The split it describes is UNCHANGED and is now load-bearing
rather than hypothetical: `api._as_catalog_refusal` translates this exception
into ONE catalog code (422 BIZ-COMPLETENESS) carrying `br_ref` and this
exception's own sentence, and that translation happens at the API boundary and
nowhere else — the same split `apps/billing/exceptions.BillingRuleError` makes
and for the same reason.

**WHY THE SEAMS TRANSLATE INTO IT — DEF-047's lesson, applied before it bites.**
A rating refusal once escaped billing's run loop and killed a run of five
hundred bills, because the loop caught billing's own error types and rating
raised its own. The fix was not to widen the catch; it was to make the seam
adapt BOTH directions — the callee's REFUSAL is as much a part of the contract
as its result. So `apps/payments/ledger_seam.py` catches
`apps.ledger.posting.PostingError` and re-raises it as this, and a future bulk
import (US-PAY-003, forty rows with two bad ones) can catch one type and record
one break per row instead of losing the batch.

`br_ref` names the rule that refused, for the same reason billing's does: B8
requires every BIZ refusal to carry its BR-ID, and the module enforcing the
rule is the one that knows which rule it is.
"""


class PaymentRuleError(Exception):
    """This payment cannot be recorded under the rules, and here is why.

    Written for a billing clerk rather than for a log: the message is what the
    S22/S35 modal shows when the Record button refuses, so it says which rule
    and what to do instead.

    A refusal from this class is NEVER about the account's standing.
    BR-PAY-036 is explicit and was ruled by the PO in these words — *"payment is
    always accepted - even it is disconnected and tagged to account"* — so a
    closed, vacation-held or marked-for-disconnect account takes money exactly
    like an active one. Nothing in this module inspects account status to decide
    whether to accept a payment, and a test asserts that absence.
    """

    def __init__(
        self,
        *args: object,
        br_ref: str | None = None,
        message_key: str | None = None,
        params: dict[str, str] | None = None,
    ) -> None:
        self.br_ref = br_ref
        # DEF-PAY-10764 — OPTIONAL. A refusal whose screen must NAME something
        # (a statement line, its date) carries its own catalogue key and the
        # values the sentence reads; every other refusal keeps
        # `payments.record.refused` at the API boundary, unchanged.
        self.message_key = message_key
        self.params = dict(params or {})
        super().__init__(*args)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (the four payments sources — B2 §2 + Addenda r12/r14 · EP-PAY-01-record-payments.md · 08-payments/02-business-rules.md · 08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments closed-loop lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [D and E CLOSED 2026-08-11 by the payments API lane: apps/payments/api.py serves POST /accounts/{id}/payments + GET /payments and 07-frontend/src/features/payments/ ships S33 and the Record modal]
# gates: ruff✔ black✔ · exercised by tests/test_us_pay_001_record_payment.py
# exceptions: NOT a core.errors catalog exception, deliberately — a catalog code
#         carries an HTTP status and this exception is raised inside batch paths
#         that answer no request; `apps/payments/api._as_catalog_refusal` is the
#         ONE place it becomes one (422 BIZ-COMPLETENESS + br_ref + its own
#         sentence). The same disposition apps/billing/exceptions.py records
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
