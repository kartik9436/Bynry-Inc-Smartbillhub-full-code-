# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-014 (Send statement) — `CR-094-BRC01` wave M.
#           Screens: S21 Account detail, the ✉ quick action `ACC-Q07`
# Rules:    BR-CUS-040 (statement != bill) · A19 §1 + rule 1 · BR-LED-010 ·
#           BR-NOT-005 / BR-NOT-013 (queued, never sent) · BR-TEN-043 (the
#           caller names the date) · HR-1 / G4 (404-never-403) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (the queue write's audit row)
# Tests:    06-backend/tests/test_cr094_m_send_statement.py
# Impacts:  apps/billing/statement.py (all of the work) · config/urls.py
# ───────────────────────────────────────────────────────
"""`POST /accounts/{id}/statement` — QUEUE an account's statement for a period.

**IT QUEUES. IT DOES NOT SEND.** `BR-NOT-005` and `BR-NOT-013`: a document is
written to `outbound_messages` and only the dispatcher sends, and no vendor is
connected on email, text or post this release (PO, 15 August 2026). The
response says `queued` and the screen says *Queued*. A screen that said a
statement had been sent would be false on every account in this product.

**WHY A POST AND NOT A GET.** It writes rows. It is idempotent — the same
account over the same period produces the same `source_id` and a replay queues
nothing (hard rule 6) — but idempotent is not safe, and a statement that could
be queued by a link prefetcher is a statement queued by a browser.

**WHY IT LIVES IN BILLING.** The statement is a BILLING document: `catalogs.py`
names `S91`–`S93` as *bill residential / bill commercial / statement* owned by
billing, and `seed_templates.py` says in so many words that *"Bills and
statements are BILLING's registry (B2 r10 #4)"*. The `accounts/` prefix is the
URL grammar for a thing that hangs off an account and is not a claim about
ownership — `apps/payments` already serves `accounts/{id}/notices` on exactly
that reading, and billing owns `bill-templates` under its own prefix. No
customers table is touched from here; the two facts this needs come through
that module's own published reads (B1).

**THE PERIOD IS REQUIRED AND HAS NO DEFAULT** (`BR-TEN-043`, gate `G6`). A
missing or malformed date is a 422 naming WHICH field, because *"you did not
say when"* and *"that is not a date"* are different answers. A default invented
here would be a product decision taken in the quietest possible place: a
statement covering the wrong three months is wrong in a way nobody notices.
The SCREEN offers a starting range the clerk can see and change.

**404-NEVER-403** for an account another tenant holds (HR-1 / G4) — raised by
`customers.selectors.account_detail`, let through rather than caught, because
a statement for somebody else's account is not a document with a gap in it.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import statement
from core import errors
from core.permissions import AdminOrClerk
from core.tenancy import require_tenant


def _money(value: Any) -> str | None:
    """A `Decimal` as the wire's 4-decimal string, or None.

    ⚠ **THIS IS NOT DISPLAY ROUNDING AND MUST NOT BECOME IT.** CLAUDE.md rule
    2 stores money to 4 decimals and DISPLAYS 2, and the display half happens
    in ONE place on each side — `format_money` for a rendered document,
    `MoneyCell` for a screen. An endpoint that rounded to 2 here would hand the
    browser a figure that had already lost precision, and the account screen
    could then never show the same number the books hold.
    """
    return None if value is None else f"{value:.4f}"


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def queue_account_statement(request: Any, account_id: str) -> Response:
    """`POST /accounts/{id}/statement` — queue this account's statement.

    Body: `{"from": "2026-07-01", "to": "2026-07-31", "copy_no": 0}`.

    `copy_no` is the one deliberate door through hard rule 6's key and it is
    the human's: asking again for the SAME period returns the same rows with
    `created: false`, and a clerk who genuinely wants a second copy passes
    `copy_no: 1`. That is the same posture a bill reprint takes (US-BIL-024
    TC-4), and it is why a double-clicked button cannot queue two statements.

    Hard rule 7's audit row is written by the queue's owner for the queue
    write, naming the actor handed down here. This view writes none of its own:
    a second row would be two records of one event, and a statement moves no
    money to audit separately.
    """
    require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    start, end = statement.parse_period(body.get("from"), body.get("to"))

    raw_copy = body.get("copy_no", 0)
    try:
        copy_no = int(raw_copy)
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.statement.copyNoFormat",
            field_errors=[{"field": "copy_no", "code": errors.VAL_FORMAT}],
        ) from None
    if copy_no < 0:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="billing.statement.copyNoRange",
            field_errors=[{"field": "copy_no", "code": errors.VAL_RANGE}],
        )

    answer = statement.queue_statement(
        account_id=account_id,
        start=start,
        end=end,
        actor=getattr(request, "user", None),
        copy_no=copy_no,
    )
    period = answer.get("period") or {}
    return Response(
        {
            **answer,
            # ⚠ ISO STRINGS, because a `date` is not JSON and DRF's renderer
            # says so with a 500 rather than a 422 — which is a server error
            # over a request that was perfectly valid. The dates come back out
            # of the LEDGER's answer rather than being echoed from the request,
            # so the response states the window the books actually used.
            "period": {
                "start": period.get("start").isoformat() if period.get("start") else None,
                "end": period.get("end").isoformat() if period.get("end") else None,
            },
            "opening_balance": _money(answer.get("opening_balance")),
            "closing_balance": _money(answer.get("closing_balance")),
            # Stated as a VALUE and not only in prose, the way `QueueWrite`
            # states it: nothing was sent, and a caller can assert it rather
            # than having to take a docstring's word for it (hard-won law 1).
            "dispatched": False,
        }
    )


urlpatterns = [
    path("accounts/<str:account_id>/statement", queue_account_statement),
]
