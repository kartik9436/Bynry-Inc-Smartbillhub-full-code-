# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-045 (EP-CWP-09) — pay now, and where the payment will land,
#           BEFORE it commits. Screen: CWP-038 (blueprint `P24`)
# Rules:    BR-CWP-058 (the screen shows where the payment will land before it
#           commits) · BR-CWP-056 (a refused control is visible, disabled and
#           carries its reason) · BR-CWP-057 (a token, a brand and four digits —
#           never a card number) · BR-CWP-010 (both halves IN THE QUERY) ·
#           BR-CWP-012 (read through a seam, no second copy) · BR-CWP-047
#           (nothing here is cached) · BR-PAY-001 / BR-PAY-010 (the tenant's
#           allocation rule, oldest bill first) · CLAUDE.md hard rule 2 (4 dp
#           stored, 2 dp displayed) · hard rule 6 · B14 rule 31
# Tests:    06-backend/tests/test_us_cwp_045_pay_now.py
# Impacts:  apps/portal/api.py (the four `pay-now` routes) ·
#           apps/payments/gateway.py · apps/payments/allocation.py
# ───────────────────────────────────────────────────────
"""WHERE THE MONEY WILL LAND — previewed by the rule that will actually apply it.

⚠ **THE PREVIEW AND THE APPLIED ALLOCATION COME FROM THE SAME FUNCTION, AND A
TEST ASSERTS THEY AGREE.** `US-CWP-045` §7 in its own words: *"the preview and
the applied allocation must come from the SAME rule, and a test that asserts the
preview matches the outcome is the one that stops them drifting."* So this file
calls `apps.payments.allocation.allocate_payment` — the function
`services.record_payment` passes its own instruction straight through to — and
computes nothing of its own. A second implementation of *which bill does my $40
land on* is a second answer, and the customer would be looking at the one the
receipt does not say.

⚠ **WHY THE PANEL IS NOT DECORATION** (`BR-CWP-058`). A payment is allocated by
a rule the utility configures, and afterwards the payment row **cannot be
edited, only reversed** (hard rule 4). A customer paying part of what they owe
therefore has exactly one moment to find out where it goes, and it is before
they press the button.

════════════════════════════════════════════════════════════════════════════
⚠ WHY THIS IS ITS OWN FILE AND NOT A SECTION OF `payments_seam.py`
════════════════════════════════════════════════════════════════════════════
It is a slice of the same seam — portal → payments — kept apart for **hard-won
law 11** and nothing else. Four lanes are building six payment screens in six
worktrees at once, and a pathspec commit takes the WHOLE working-tree content of
every path it names: the second lane to commit `payments_seam.py` would silently
revert the first, with a correct file count, its own hunks present, and nothing
anywhere looking wrong. When the lanes converge this belongs in
`payments_seam.py` beside `money_list` and `plan_preview`.

⚠ **IT COMPUTES NO MONEY** (`CR-068` §2d). Every figure is carried out of
`payments`' own reads as a four-decimal STRING; rounding happens at display and
this is not display.

⚠ **EVERY READ NAMES THE TENANT IN THE QUERY** (`BR-CWP-010`, `G96`). RLS
`FORCE` is on and would refuse a cross-tenant read a second time — but the suite
runs on in-memory SQLite, which has no row-level security at all (hard-won law
14), so a read that leaned on it would pass every test in this repository
forever.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.customers import models as customers_models
from apps.payments import allocation as payments_allocation
from apps.payments import gateway as payments_gateway
from apps.payments import models as payments_models
from apps.payments import open_bills as payments_open_bills
from core import tenancy as core_tenancy

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")

#: A saved instrument's KIND → the tenant's seeded tender code
#: (`SEED_PAYMENT_METHODS`, tenancy migration 0004). Two different vocabularies
#: for two different things: `stored_payment_instruments.kind` says what the
#: customer saved, `payment_methods.code` says how the money came in.
#: ⚠ A MAPPING AND NOT A BRANCH — a third instrument kind adds a row here and
#: changes no `if`.
METHOD_FOR_KIND: dict[str, str] = {
    payments_models.INSTRUMENT_CARD: "card",
    payments_models.INSTRUMENT_BANK: "ach",
}


def _money(value: Any) -> str:
    """A figure as its four-decimal STRING — hard rule 2's stored precision,
    carried rather than rounded, because rounding happens at DISPLAY."""
    return str(Decimal(value or 0).quantize(FOUR_DP, rounding=ROUND_HALF_UP))


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:  # pragma: no cover — the edge resolves it from the path
        raise RuntimeError("no tenant context; CLAUDE.md hard rule 1")
    return tenant_id


class _OpenBill:
    """One open bill in the shape `allocation.OpenInvoiceLike` expects.

    Structural, exactly as `rating_seam.OpenInvoice` is: the allocation contract
    is a Protocol, so this satisfies it without `allocation.py` importing
    anything of the portal's.
    """

    __slots__ = ("number", "balance", "issued_on", "composition")

    def __init__(self, *, number: str, balance: Decimal, issued_on: Any):
        self.number = number
        self.balance = balance
        self.issued_on = issued_on
        #: ⚠ **NO COMPOSITION IS CLAIMED.** The within-bill class walk needs
        #: usage/tax/fee balances the portal has not read, and a preview that
        #: invented them would show a customer a breakdown the engine would not
        #: reproduce. Empty means *"this bill stated none"*, which
        #: `allocate_payment` handles by amount alone and reports as no
        #: breakdown — the honest answer rather than a guessed one.
        self.composition = ()


def instruments(tenant_id: Any, customer_id: Any) -> list[dict[str, Any]]:
    """The customer's saved cards and mandates — **brand and last four only**.

    ⚠ **`BR-CWP-057` IS ENFORCED BY THE COLUMN, NOT BY THIS FUNCTION.**
    `stored_payment_instruments.last_four` is `CharField(max_length=4)` and there
    is no column a card number would fit in. What this adds is that the TOKEN
    never leaves the server: it is read by `gateway.charge` and is not in the
    dict below.

    ⚠ **`id` IS SERVED AND NEVER DISPLAYED** (B14 rule 31). The screen posts it
    back to say which method was chosen, exactly as `open_bill_position` serves
    `invoice_id` beside the `number` a clerk reads. `label` is what a person
    recognises.
    """
    rows = payments_models.StoredPaymentInstrument.objects.filter(
        tenant_id=tenant_id, customer_id=customer_id, deleted_at__isnull=True
    ).order_by("-created_at")
    out: list[dict[str, Any]] = []
    for row in rows:
        expired = row.status == payments_models.INSTRUMENT_EXPIRED
        out.append(
            {
                "id": str(row.pk),
                "label": f"{row.brand} ••••{row.last_four}",
                "brand": row.brand,
                "last_four": row.last_four,
                "kind": row.kind,
                "status": row.status,
                "used_for": list(row.used_for or []),
                "expires_month": row.expires_month,
                "expires_year": row.expires_year,
                # `US-CWP-046` TC-6 — an expired card reads expired and cannot be
                # chosen for a payment. The reason is a CODE the catalogues write.
                "selectable": not expired,
                "held_reason": "card_has_expired" if expired else None,
            }
        )
    return out


def pay_now(account_id: Any, *, customer_id: Any, may_pay: bool) -> dict[str, Any]:
    """Everything `CWP-038` draws before anything is typed.

    ⚠ **THE HELD REASON IS COMPUTED HERE AND RENDERED THERE** (`BR-CWP-056`).
    The control is never hidden and never live-but-inert; it renders in its
    normal place, disabled, with words on it. `held_reason` is a CODE — eleven
    catalogues write the sentence in their own language (B14 rule 35) and each is
    five or six words (rule 33).
    """
    tenant_id = _tenant_id()
    account = customers_models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    position = payments_open_bills.open_bill_position(account_id=account_id)
    saved = instruments(tenant_id, customer_id)
    provider = payments_gateway.active_provider(tenant_id)
    cash_only = bool(getattr(account, "cash_only_no_autopay", False))
    reason = payments_gateway.held_reason(
        provider=provider,
        cash_only=cash_only,
        has_method=any(one["selectable"] for one in saved),
        may_pay=may_pay,
    )
    return {
        # B14 rule 31 — the number printed on the bill, never the row id.
        "account_no": getattr(account, "account_no", None),
        "balance": position["total_open"],
        "currency": position.get("currency"),
        "bills": position["bills"],
        "bill_count": position["bill_count"],
        "instruments": saved,
        "can_pay": reason is None,
        "held_reason": reason,
        # ⚠ **THE ORDER IS THE TENANT'S AND IT IS ON THE WIRE**, so the footer
        # under the panel states the rule that produced the rows above it rather
        # than a sentence somebody typed once (`US-CWP-045` TC-5).
        "order": _tenant_order(),
        # PO ruling 2026-09-05 §3 — a customer looking at a sandbox confirmation
        # is entitled to know that no real money moved.
        "environment": None if provider is None else provider.environment,
        "problems": position.get("problems", []),
    }


def preview(account_id: Any, *, amount: Any, key: str | None = None) -> dict[str, Any]:
    """`BR-CWP-058` — where this amount will land, **before it commits**.

    ⚠ **WRITES NOTHING AND MINTS THE KEY** — which is not a contradiction and is
    the point. `US-CWP-045` TC-7 needs the idempotency key to exist *before the
    first request leaves*, and the first request leaves on the COMMIT. Minting
    it here and carrying it to the screen is what lets a retry after a timeout
    present the same string; a key minted on the commit could never cover the one
    case it exists for. Nothing is stored: the caller holds it, and the row that
    finally carries it is written only when the money is real.

    ⚠ **`owing_after` IS WHY THE PANEL IS WORTH DRAWING.** `US-CWP-045` TC-4:
    `$40.00` against a `$142.18` bill must read `$102.18` afterwards, and the
    customer must be able to see that figure before they press anything.
    """
    _tenant_id()
    position = payments_open_bills.open_bill_position(account_id=account_id)
    figure = Decimal(str(amount)).quantize(FOUR_DP)
    order = _tenant_order()
    invoices = tuple(
        _OpenBill(
            number=row["number"],
            balance=Decimal(row["open_balance"]),
            issued_on=row["issued_on"],
        )
        for row in position["bills"]
    )
    outcome = payments_allocation.allocate_payment(
        payment_amount=figure,
        open_invoices=invoices,
        order=order,
    )
    owing_before = {row["number"]: Decimal(row["open_balance"]) for row in position["bills"]}
    lands_on = [
        {
            "number": one.invoice_number,
            "owing": _money(owing_before.get(one.invoice_number, ZERO)),
            "paying": _money(one.applied),
            # The figure TC-4 asks the screen to show BEFORE the commit.
            "owing_after": _money(owing_before.get(one.invoice_number, ZERO) - one.applied),
        }
        for one in outcome.allocations
    ]
    return {
        "amount": _money(figure),
        "currency": position.get("currency"),
        "order": order,
        "lands_on": lands_on,
        # BR-PAY-010 — whatever no bill can absorb carries as account credit. It
        # is on the wire so an overpayment says where it went rather than
        # vanishing off the panel.
        "credit_carried": _money(outcome.credit_carried),
        "remaining_balance": _money(outcome.remaining_balance),
        "idempotency_key": key or payments_gateway.mint(),
        #: Always `[]` — the staff preview's own contract, so a caller can tell a
        #: preview from a commit without knowing which route it called.
        "writes": [],
    }


def pay(
    account_id: Any,
    *,
    customer_id: Any,
    may_pay: bool,
    amount: Decimal,
    instrument_id: str | None,
    key: str | None,
    portal_actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The commit. **The only path in this product that takes a customer's money.**

    ⚠ **THE HELD REASON IS RE-CHECKED HERE AND NOT TRUSTED FROM THE SCREEN**
    (`US-CWP-045` TC-2, TC-9). Forcing the disabled control produces no payment
    row, no audit row and no gateway call, because a screen order is not the
    security — the posture `set-password` already takes on this edge.

    ⚠ **NOTHING IS WRITTEN UNLESS THE PROVIDER APPROVED** (TC-6). A decline and
    a timeout both return before `settle_charge` is reached, and the timeout
    carries the key back so the retry presents the same string (TC-7).

    ⚠ **AND THE PAYMENT ROW IS WRITTEN THROUGH THE INBOUND DOOR**, not beside
    it: `webhooks.settle_charge` runs the same three steps a real processor's
    settlement runs, so the allocation, the balanced ledger pair, the receipt and
    the audit row are the existing tested ones. The provider's own settlement
    callback for this charge then carries the same key and is recognised as a
    duplicate — one payment, whatever the provider does.
    """
    from apps.payments import webhooks as payments_webhooks

    tenant_id = _tenant_id()
    account = customers_models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    saved = instruments(tenant_id, customer_id)
    chosen = next(
        (one for one in saved if instrument_id is not None and one["id"] == instrument_id), None
    )
    if chosen is None:
        chosen = next((one for one in saved if one["selectable"]), None)
    provider = payments_gateway.active_provider(tenant_id)
    reason = payments_gateway.held_reason(
        provider=provider,
        cash_only=bool(getattr(account, "cash_only_no_autopay", False)),
        has_method=chosen is not None and chosen["selectable"],
        may_pay=may_pay,
    )
    if reason is not None or provider is None:
        # ⚠ **REFUSED BEFORE ANY MONEY MOVES, AND THE REASON IS THE SAME CODE
        # THE SCREEN WAS ALREADY SHOWING.** A refusal a customer has never seen
        # is a refusal they cannot act on.
        return {
            "outcome": "refused",
            "held_reason": reason or payments_gateway.HELD_NO_PROVIDER,
            "payment_no": None,
            "amount": _money(amount),
            "currency": None,
            "lands_on": [],
            "idempotency_key": key,
            "environment": None if provider is None else provider.environment,
            "problems": [],
        }
    token = _token_of(tenant_id, customer_id, chosen["id"])
    attempt_key = key or payments_gateway.mint()
    position = payments_open_bills.open_bill_position(account_id=account_id)
    currency = position.get("currency") or "USD"
    # ⚠ **PRICED BEFORE THE CHARGE, AND THAT IS WHAT THE CONFIRMATION SHOWS.**
    # `US-CWP-045` §7 asks that the preview and the applied allocation come from
    # the same rule. Re-previewing AFTERWARDS answers a different question —
    # *where would the NEXT `$40.00` land* — and on this story's own figures that
    # is `$62.18` rather than `$102.18`: the same function, the same rule, and
    # the wrong answer, because the open bills have moved underneath it. So the
    # rows a customer read before pressing are the rows the receipt states, and
    # the test that compares them is comparing two calls made at the same moment
    # rather than two calls made either side of a payment.
    landing = preview(account_id, amount=amount, key=attempt_key)
    answer = payments_gateway.charge(
        provider=provider,
        key=attempt_key,
        amount=amount,
        currency=currency,
        token=token,
    )
    if answer.wrote_nothing:
        return {
            # `no_answer` and `declined` are DIFFERENT WORDS on the wire because
            # they are different facts: one means no money moved, the other
            # means nobody knows (`BR-INT-018`).
            "outcome": answer.outcome,
            "held_reason": None,
            "payment_no": None,
            "amount": _money(amount),
            "currency": currency,
            "lands_on": [],
            # ⚠ TC-7 — the SAME key, carried back for the retry.
            "idempotency_key": attempt_key,
            "environment": answer.environment,
            "problems": [dict(one) for one in answer.problems],
        }
    recorded = payments_webhooks.settle_charge(
        provider=answer.provider_key,
        key=attempt_key,
        body={
            "account_id": str(account_id),
            "amount": str(_money(amount)),
            "currency": currency,
            # BR-PAY-021 — both moments, and the PROVIDER names them. An
            # approved charge is money that has arrived, so the two are the same
            # instant here; nothing in `payments` reads a clock (G6).
            "posted_at": _now().isoformat(),
            "cleared_at": _now().isoformat(),
            # ⚠ **A SEEDED LOOKUP CODE, RESOLVED BY `payments` AND REFUSED BY
            # NAME IF A TENANT RETIRED IT** (`BR-PAY-026`, `services._method`).
            # `card` and `ach` are two of the seven `SEED_PAYMENT_METHODS`; the
            # list is tenant-extensible, and a tenant who deactivated one has
            # said stop using it rather than "use it silently".
            "method": METHOD_FOR_KIND[chosen["kind"]],
            "reference": attempt_key,
        },
        received_at=_now(),
        portal_actor=portal_actor,
    )
    return {
        "outcome": "paid",
        "held_reason": None,
        "payment_no": recorded.payment_no,
        "amount": _money(amount),
        "currency": currency,
        # ⚠ **WHAT IT MET — THE ROWS THE CUSTOMER READ BEFORE PRESSING.** See
        # `landing` above for why this is the pre-charge pricing and not a
        # re-read.
        "lands_on": landing["lands_on"],
        "idempotency_key": attempt_key,
        "environment": answer.environment,
        "problems": [dict(one) for one in recorded.problems],
    }


def _token_of(tenant_id: Any, customer_id: Any, instrument_id: str) -> str:
    """The gateway token, read for the length of one call and never served.

    ⚠ **IT IS NOT ON `instruments()`' DICT AND MUST NOT BE.** `BR-CWP-057` says
    a stored instrument is a token, a brand and four digits; the four digits are
    for a person to recognise and the token is for the provider. A response body
    carrying it would put it in a browser, a proxy log and a screenshot.
    """
    row = payments_models.StoredPaymentInstrument.objects.filter(
        tenant_id=tenant_id, customer_id=customer_id, pk=instrument_id, deleted_at__isnull=True
    ).only("gateway_token").first()
    return "" if row is None else str(row.gateway_token)


def _now() -> Any:
    """The one clock read on this path, and it is the EDGE's rather than a
    rule's. `payments` reads no clock (`BR-TEN-043`, `G6`) — an approved charge
    is money that arrived now, and the provider's own settlement callback will
    carry its own moments when it comes."""
    from django.utils import timezone

    return timezone.now()


def _tenant_order() -> str:
    """The between-bill walk this payment will ACTUALLY be allocated by.

    ⚠ **NOT A DEFAULT TYPED HERE, AND NOT A SECOND READ OF THE TENANT SETTING
    EITHER — IT IS THE WRITE PATH'S OWN INSTRUCTION, IMPORTED.**
    `US-CWP-045` TC-5 asks that the panel show *"oldest first, BY THE TENANT'S
    RULE, and the screen never guesses a different order"*, and §7 asks that the
    preview and the applied allocation come from the SAME rule. The only way to
    guarantee the second is to take the value from where the write path takes
    it: `services.record_payment`'s `order` parameter, whose default is this
    constant, passed straight through to `allocation.allocate_payment`.

    ⚠ **MEASURED WHILE BUILDING THIS, AND WORTH WRITING DOWN BECAUSE IT LOOKS
    LIKE A BUG AND IS NOT ONE YET.** A tenant setting for this exists —
    `billing-defaults · allocation_order`, `BR-PAY-010` — and **nothing in this
    product reads it**: `record_payment` defaults to the constant below and the
    portal's commit passes no `order`. Its vocabulary is also a different one
    from the engine's (`oldest_invoice_first` against `oldest_first`) and it
    accepts exactly ONE value today, so no tenant can currently choose anything
    else and no figure moves either way. **Reading it HERE would be the drift
    §7 warns about** — a preview allocating by the setting while the write path
    allocated by the constant, agreeing on every tenant until the day somebody
    widened the choice list. Wiring the setting through `record_payment` is one
    change in `payments`, and it is REPORTED rather than made from a portal seam.
    """
    return payments_allocation.ORDER_OLDEST_FIRST


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-045 (EP-CWP-09) · BR-CWP-056/057/058 · BR-PAY-001 · BR-PAY-010
#         · CLAUDE.md hard rules 1, 2, 4, 6 · B14 rules 31, 33, 35
# generated: 2026-09-05 by the CR-068 phase 5 lane B (the money path)
# checklist: A✔ B✔ C✔ D✔ E✔(CWP-038) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 the preview states no per-class breakdown. `_OpenBill.composition` is
#      empty because the portal has not read usage/tax/fee balances, and an
#      invented breakdown would be one the engine does not reproduce. Stated
#      rather than implied.
#   E2 this file belongs inside `payments_seam.py`; it is separate for hard-won
#      law 11 while four lanes share one branch. See the module docstring.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
