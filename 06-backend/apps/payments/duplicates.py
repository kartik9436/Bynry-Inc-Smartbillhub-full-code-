# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-9263 — two $30.00 card payments on AC-2026-00060, same day,
#           same reference AUTH-S8-0030 (PY-261002-0093/0094), both saved with
#           no word to the clerk.
# Ruling:   PO 2026-10-03, verbatim: *"Same card or ACH payment entered twice -
#           B Warn "Looks like a duplicate", and let the clerk confirm"*.
# Rule:     BR-PAY-1199 (minted with this file).
# Story:    US-PAY-001 (record one payment)   Screens: S22 · S35 · the request
#           page's Take payment · New Connection step 4
# Tests:    06-backend/tests/test_def_pay_9263_card_ach_duplicate_warning.py
# ───────────────────────────────────────────────────────
"""A counter payment that looks like one already recorded — WARN, never refuse.

⚠ **WIDENED 2026-10-30 FROM CARD/ACH TO EVERY TENDER (`DEF-PAY` Q1, PO ruling
Q1 = A, decision log *"Payments audit by level: answers to Q1, Q3, Q5, Q6,
Q7"*).** Verbatim: *"Q1-A"*, put as: at the counter, ANY tender warns "Looks
like a duplicate" when the same account + amount + day is entered against a
bill already paid; *Record anyway* stays allowed and is audit-logged. **Worked:
Kevin Hall's bill is already paid; a second $259.23 in CASH is warned; Record
anyway records it and the audit row names the clerk.** That SUPERSEDES the
2026-10-03 scope below in two places and nowhere else:
  * **the tender** — `card`/`ach` only → every tender;
  * **the reference** — it is no longer part of the match. Cash carries none,
    and the ruled sentence names account, amount and day. A repeated reference
    on card/ACH is still a duplicate, because the three facts still match.
⚠ **NARROWED 2026-10-30 TO THE RULING'S OWN CONDITION (`DEF-PAY-10749`, lane
PAY-K).** The first build of Q1 matched account + amount + day and nothing
else, so two genuine $50.00 cash payments on one day for TWO DIFFERENT OPEN
bills warned. The ruled sentence says *"entered against a bill already
paid"*, so the warning now asks TWO things, in this order:
  1. **would this payment pay a bill that is already paid?** — named bills
     (`specific` / `split`): none of the named bills is still open; any other
     allocation order: the account has NO open bill left. If a bill it would
     pay is still open, there is no warning, whatever was taken earlier;
  2. **is there an earlier payment the same utility-local day with the same
     account + amount** that still stands (the exemptions below)?
Both → warned. **Worked:** Kevin Hall's $259.23 bill is paid; a second $259.23
cash → warned. Bills A and B of $50.00 open; $50.00 cash pays A; a second
$50.00 cash pays B → NOT warned. $12.00 the same day → not warned (no match).
*Warn, never refuse*, the staff-doors-only scope, the replay exemption, the
reversed-payment exemption and BR-PAY-880's cheque-number REFUSAL are all
unchanged.
⚠ **WIDENED AGAIN 2026-10-31 — A REPEATED CARD/ACH REFERENCE WARNS EVEN ON AN
OPEN BILL (`DEF-PAY-10782`, PO ruling P8 = A, decision log *"Twelve open
payment questions answered (PO)"*).** Verbatim *"P8-A"*, put as: in addition
to Q1's rule, the counter also warns when the **same card/ACH reference
repeats on the same account and day** (e.g. AUTH 88412 entered twice on an
open bill). So there are now TWO ways to match, asked in this order:
  A. **the reference** — this payment is `card` or `ach` with a reference
     typed, and an earlier `card`/`ach` payment on the same account the same
     utility-local day carries the same reference (trimmed, case-blind). The
     amount and whether a bill is still open are NOT asked: one authorisation
     is one payment, whatever it was for;
  B. **the paid bill** — Q1's two questions above, unchanged.
**Worked:** a $100.00 bill open; $40.00 card AUTH 88412 recorded; a second
$40.00 card AUTH 88412 the same day → warned (the bill still owes $60.00, so
B alone said nothing). Two $50.00 CASH for two open bills → still not warned
(cash carries no authorisation, so A is never asked of it). The sections below that say "card or ACH" describe the 2026-10-03
ruling as it was and are stamped where they no longer hold.

HUMAN-OWNED (on `10-scripts/gates/human_owned.txt` by PO ruling 2026-10-03,
verbatim: "Yes - warning only - but allow if they enter").
HUMAN-REVIEW-PENDING — 🔒 money path (it decides whether a payment is saved on
the first press). AI-authored 2026-10-03 under the PO ruling of 2026-08-09; the
review-ledger row states the $30.00 / `AUTH-S8-0030` case and the PO's words.

════════════════════════════════════════════════════════════════════════════
WHAT WAS RULED, AND WHAT THIS FILE IS
════════════════════════════════════════════════════════════════════════════
PO 2026-10-03, option **B** of three (refuse · warn · allow): *"Warn 'Looks like
a duplicate', and let the clerk confirm"*. So this is a WARNING the clerk can
override, not a rule that refuses money. The worked case it was ruled on:
**two $30.00 card payments, one account, one day, both `AUTH-S8-0030`** — the
second was a request page walked twice, and nothing said a word.

⛔ **SUPERSEDED IN SCOPE 2026-10-30 — a match is now THREE facts: account,
amount and local day (the reference is dropped).** As ruled 2026-10-03:
**A MATCH IS ALL FOUR OF:** the same ACCOUNT · the same AMOUNT · the same
REFERENCE (the card authorisation or ACH trace number, `payments.confirmation`,
compared trimmed and case-blind — `auth-s8-0030` is the same authorisation) ·
the same PAYMENT DATE (the posting day, read in the UTILITY's own timezone,
BR-TEN-081 — a Chicago clerk's 2 October is one day, not two UTC halves).

**AGAINST AN EARLIER ROW THAT STILL STANDS:** a `payment`-type row (never a
credit or an adjustment, which are not money received), of ANY tender since
2026-10-30 (card or ACH before), that is not itself a reversal, is not `failed`, and has no row
reversing it. A reversed payment's money came back, so a re-entry is the
correction rather than a repeat — `cheques.refuse_a_duplicate_cheque`'s own
exemption, for the same reason.

════════════════════════════════════════════════════════════════════════════
WHAT IS DELIBERATELY NOT HERE
════════════════════════════════════════════════════════════════════════════
  * **CHEQUES.** `BR-PAY-880` already REFUSES a cheque number repeated from one
    drawer bank (`cheques.refuse_a_duplicate_cheque`). Unchanged.
  * ⛔ SUPERSEDED 2026-10-30 — no reference now matches too. **NO REFERENCE
    TYPED.** With no reference there is nothing that makes two
    $30.00 card payments the same payment rather than two customers' coffee
    money; the ruling's case is a repeated reference. No warning.
  * ⛔ SUPERSEDED 2026-10-30 — every tender, a tenant's own codes included.
    **A TENANT'S OWN EXTRA TENDER CODES.** The PO said *card or ACH*; those are
    the seeded codes `card` and `ach` (`BR-PAY-026`). A utility-added code such
    as a bill-pay portal is not warned on.
  * **THE PORTAL, WEBHOOKS, IMPORTS, THE PARTNER FEED.** Nobody is at a screen to
    confirm, and inbound money already carries hard rule 6's idempotency key.
    Only the staff doors ask (`record_payment(warn_on_possible_duplicate=True)`).
  * **A REPLAY.** The same form pressed twice carries the same idempotency key
    and is answered with the first payment before this check runs — a
    double-click is not a duplicate, it is one payment.

Nothing here moves an amount, an allocation or a status.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError

#: The two tenders the 2026-10-03 ruling named — *"Same card or ACH payment"*.
#: ⛔ **NO LONGER A FILTER ON THE PAID-BILL MATCH SINCE 2026-10-30 (Q1 = A):
#: every tender warns there.** ⚠ **READ AGAIN SINCE 2026-10-31 (P8 = A):** these
#: are the tenders whose reference is an authorisation, so only they are
#: matched by a repeated reference (`_same_reference_today`).
WARNED_TENDERS: tuple[str, ...] = ("card", "ach")

#: The rule this warning is, on every refusal and every audit row.
BR_REF = "BR-PAY-1199"

#: WHICH of the two matches fired (P8 = A, 2026-10-31), on the warning's
#: `params` and the audit row, so the screen says the right sentence: *"Same
#: reference, same day."* for a repeated authorisation on an open bill, and
#: *"Same amount, same day. The bill is paid."* for Q1's paid-bill match.
MATCHED_ON_REFERENCE = "reference"
MATCHED_ON_PAID_BILL = "paid_bill"


class PossibleDuplicatePayment(PaymentRuleError):
    """A card/ACH payment that matches one already recorded — not saved yet.

    A `PaymentRuleError` so every caller that already translates a payments
    refusal still says SOMETHING; the two staff doors catch it first and answer
    the warning with the earlier payment named (`earlier`).
    """

    def __init__(self, earlier: dict[str, Any]) -> None:
        self.earlier = earlier
        super().__init__(
            f"looks like a duplicate of {earlier.get('payment_no')}, recorded "
            f"{earlier.get('posted_on')} for {earlier.get('amount')} "
            f"{earlier.get('currency')} with reference {earlier.get('confirmation')}.",
            br_ref=BR_REF,
        )


def _local_day_bounds(posted_at: datetime) -> tuple[datetime, datetime, Any]:
    """The utility-local day `posted_at` falls on, as [start, end) instants."""
    from apps.payments import settings_seam

    zone = settings_seam.tenant_timezone()
    local_day = posted_at.astimezone(zone).date()
    start = datetime.combine(local_day, time.min, tzinfo=zone)
    return start, start + timedelta(days=1), local_day


def is_warned_tender(method_code: str | None) -> bool:
    """Every tender is warned on since 2026-10-30 (Q1 = A) — cash, cheque,
    card, ACH, a utility's own code, and a payment with no tender at all."""
    return True


def _would_pay_an_open_bill(account_id: Any, targets: tuple[Any, ...]) -> bool:
    """True when the bill(s) this payment would meet still owe money.

    Named bills (`specific` / `split` — each target carries `invoice_number`):
    any one of them still open. Every other order meets the account's open
    bills, so: the account has any open bill at all. The open set is
    `billing_seam.open_invoices_for_account` — the same read the allocation
    makes a moment later — so the two cannot disagree about what is paid.
    """
    from apps.payments import billing_seam

    open_numbers = {
        invoice.number for invoice in billing_seam.open_invoices_for_account(account_id).invoices
    }
    named = {getattr(target, "invoice_number", None) for target in targets} - {None}
    if named:
        return bool(named & open_numbers)
    return bool(open_numbers)


def find_possible_duplicate(
    tenant_id: Any,
    *,
    account_id: Any,
    amount: Decimal,
    confirmation: str | None,
    posted_at: datetime,
    method_code: str | None,
    payment_type: str,
    targets: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    """The earlier payment this one resembles, as plain facts — or None.

    A READ, run before any transaction opens, so a warned payment burns no
    `PMT-` number and writes nothing.
    """
    # Q1 = A (2026-10-30): account + amount + day, any tender, no reference —
    # and ONLY against a bill already paid (DEF-PAY-10749). `confirmation` and
    # `method_code` stay in the signature so the one caller is unchanged.
    if payment_type != models.PAYMENT_TYPE_PAYMENT or not is_warned_tender(method_code):
        return None
    # P8 = A (2026-10-31): a card/ACH reference repeated on this account and
    # day is warned FIRST, open bill or not, whatever the amount.
    by_reference = _same_reference_today(
        tenant_id,
        account_id=account_id,
        confirmation=confirmation,
        posted_at=posted_at,
        method_code=method_code,
    )
    if by_reference is not None:
        return by_reference
    if _would_pay_an_open_bill(account_id, targets):
        return None
    rows = _standing_on_the_day(tenant_id, account_id, posted_at).filter(amount=amount)
    found = _first_standing(tenant_id, rows)
    return None if found is None else {**found, "matched_on": MATCHED_ON_PAID_BILL}


def _standing_on_the_day(tenant_id: Any, account_id: Any, posted_at: datetime) -> Any:
    """Earlier `payment` rows on this account the same utility-local day that
    could still be the money taken twice: not a credit or adjustment, not
    itself a reversal, not failed, and not cancelled (a cancelled row never
    took the money either, `payments/0051`). A REVERSED row is skipped by
    `_first_standing`."""
    start, end, _local_day = _local_day_bounds(posted_at)
    return (
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            account_id=account_id,
            type=models.PAYMENT_TYPE_PAYMENT,
            reverses_payment__isnull=True,
            posted_at__gte=start,
            posted_at__lt=end,
        )
        .exclude(status__in=(models.PAYMENT_FAILED, models.PAYMENT_CANCELLED))
        .order_by("posted_at", "payment_no")
    )


def _first_standing(tenant_id: Any, rows: Any) -> dict[str, Any] | None:
    """The first row nothing has reversed, as plain facts — or None."""
    for row in rows:
        if models.Payment.objects.filter(tenant_id=tenant_id, reverses_payment_id=row.pk).exists():
            continue  # reversed: the money came back, a re-entry is the correction
        local_day = _local_day_bounds(row.posted_at)[2]
        return {
            "payment_id": str(row.pk),
            "payment_no": row.payment_no,
            "posted_on": local_day.isoformat(),
            "amount": str(row.amount),
            "currency": row.currency,
            "confirmation": row.confirmation,
            "method": getattr(row.method, "code", None),
        }
    return None


def _reference_key(confirmation: str | None) -> str:
    """Trimmed, inner spaces collapsed and case-blind: `auth 88412 ` is the
    same authorisation as `AUTH 88412`."""
    return " ".join(str(confirmation or "").split()).casefold()


def _same_reference_today(
    tenant_id: Any,
    *,
    account_id: Any,
    confirmation: str | None,
    posted_at: datetime,
    method_code: str | None,
) -> dict[str, Any] | None:
    """P8 = A — an earlier card/ACH payment on this account today carrying the
    same reference, or None.

    Only `card` and `ach` carry an authorisation or trace number
    (`WARNED_TENDERS`). A cash note is not one, and a cheque number already has
    `BR-PAY-880`'s own refusal, so neither is matched here. Compared in Python
    rather than SQL because the key collapses inner spaces, and one account's
    card payments on one day are a handful of rows.
    """
    if method_code not in WARNED_TENDERS:
        return None
    key = _reference_key(confirmation)
    if not key:
        return None
    rows = [
        row
        for row in _standing_on_the_day(tenant_id, account_id, posted_at)
        .filter(method__code__in=WARNED_TENDERS)
        .exclude(confirmation__isnull=True)
        .select_related("method")
        if _reference_key(row.confirmation) == key
    ]
    found = _first_standing(tenant_id, rows)
    return None if found is None else {**found, "matched_on": MATCHED_ON_REFERENCE}
