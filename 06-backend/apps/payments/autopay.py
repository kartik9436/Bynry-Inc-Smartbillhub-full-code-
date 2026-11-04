# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-024 (autopay capture-intents: bill issue records the intent;
#           staff record the money)   Screens: S32 · S33
# Rules:    BR-PAY-015 (autopay v1 = capture-INTENT: bill issue records an
#           intent dated the DUE DATE, visible on S32/S33; staff record the
#           actual money; real charging = rails W7) · BR-CUS-059 (enrolment is
#           CAPTURE-ONLY; no drafting originates anywhere in v1) · BR-PAY-021
#           (on-time-ness stays a POSTING-date fact — an intent never
#           substitutes for money) · BR-PAY-034 (a "fulfilled" intent is a
#           COMPUTED display state in v1, never a stored transition) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 7
# Tests:    06-backend/tests/test_us_pay_024_autopay_intents.py
# Impacts:  apps/payments/models.AutopayCaptureIntent (the row) ·
#           apps/payments/summary.py (the S32 "autopay scheduled" chip) ·
#           apps/billing (US-BIL-005 issue — the CALLER this module waits for) ·
#           apps/payments/api.py
# ───────────────────────────────────────────────────────
"""Autopay in v1 is a PROMISE RECORDED — and there is no way to charge anybody.

BR-PAY-015, CONFIRMED: *"Autopay v1 = capture-INTENT: enrollment + method
stored; bill issue records intent dated the due date, visible on S32/S33; staff
record the actual money; real charging = rails (W7)"*.

════════════════════════════════════════════════════════════════════════════
US-PAY-024 TC-5 IS A TEST ABOUT AN ABSENCE, AND THIS FILE IS THE ABSENCE
════════════════════════════════════════════════════════════════════════════
TC-5: *"Any v1 code path attempts to charge the stored method (or a 'Retry
autopay' action) → Impossible — no charging path exists before rails"*. That is
not enforced by a guard here; it is enforced by there being nothing to call. The
model carries ONE status (`awaiting_rails`), the stored payment instrument is
never read by this module, and no function in it takes a method or an amount to
capture. A `charge()` that raised would be a charging path with a flag on it.

════════════════════════════════════════════════════════════════════════════
WHY THE INTENT IS STORED AND NOT DERIVED
════════════════════════════════════════════════════════════════════════════
US-PAY-024 §1: *"when rails land (W7), the dispatcher-side execution consumes
these same intents — the v1 record IS the W7 contract"*. So `amount` and
`scheduled_on` are stamped at issue and never recomputed: what the customer was
told would be drafted, and when, must survive a later correction to the bill.

**FULFILLED IS COMPUTED, NEVER STORED** (BR-PAY-034, field-map P-7). An intent
is fulfilled when its invoice settles — which this module reads from
`allocations`, the same rows every other settlement question is answered from.
A stored `fulfilled` flag would be a second copy of that fact, free to disagree
with it the first time a payment was reapplied.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT WIRED, NAMED RATHER THAN IMPLIED
════════════════════════════════════════════════════════════════════════════
**NOTHING CALLS `record_intent_at_issue`.** BR-PAY-015 puts the trigger at BILL
ISSUE, that is `apps/billing/issue.py` (US-BIL-005), and `apps/billing` belongs
to another lane this session. The function is published, idempotent and tested;
the caller is one line in billing's issue path and it is REPORTED (hard-won law
2 — a component nothing calls is not a feature).

**ENROLMENT IS CUSTOMERS' FACT AND IS READ, NEVER INFERRED.** `accounts.autopay`
and the stored instrument are customers-owned (BR-CUS-059) and this module reads
enrolment through their published queryset. An account that is not enrolled gets
NO intent (TC-4), and a module that guessed enrolment would draft money for
somebody who never asked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Sum

from core import audit as core_audit
from core import tenancy as core_tenancy

from apps.payments import models
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

AUDIT_INTENT_RECORDED = "autopay_intent.recorded"

#: Carried on every result — the caller must not have to infer the absence.
AUTOPAY_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_charging_path_before_rails",
        "br_ref": "BR-PAY-015",
        "detail": "autopay v1 records an INTENT and nothing else. No code path in this product "
        "can charge a stored instrument, the intent carries one status (awaiting_rails), and "
        "the prototype's *Retry autopay* action is superseded. Staff record the actual money "
        "through US-PAY-001 when it arrives.",
    },
    {
        "code": "intent_recording_has_no_caller",
        "br_ref": "BR-PAY-015",
        "detail": "BR-PAY-015 records the intent AT BILL ISSUE and that path is "
        "`apps/billing/issue.py` (US-BIL-005), which belongs to another module. Until billing "
        "calls `record_intent_at_issue`, intents exist only for bills something else recorded "
        "them for.",
    },
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


@dataclass(frozen=True)
class IntentResult:
    """One intent, or the reason there is none."""

    intent_id: str | None
    created: bool
    account_id: str
    invoice_id: str
    amount: Decimal = ZERO
    scheduled_on: Any = None
    status: str = models.INTENT_AWAITING_RAILS
    problems: tuple[dict[str, Any], ...] = AUTOPAY_UNAVAILABLE


def is_enrolled(account_id: Any) -> bool:
    """May this account be autopaid? Customers' fact, read through their queryset.

    TWO COLUMNS, AND THEY ANSWER DIFFERENT QUESTIONS (DEF-070):

      * `autopay` is the customer's own ELECTION (BR-CUS-059) — they asked for
        it and nothing here ever un-asks it.
      * `cash_only_no_autopay` is BR-PAY-013's PRIVILEGE SANCTION — at the
        tenant's Nth bounce (default 2, `nsf_privilege_n`) the account goes
        cash-only and off autopay, and **J12 step 6 says no rule ever
        auto-clears it**; lifting it is an explicit, audited staff action.

    An enrolled account under the sanction is therefore **not autopayable**, and
    this is where that becomes true rather than a sentence in a rule: the flag
    had no column at all until 2026-08-15, so the second bounce did nothing and
    the customer's card kept being scheduled. Reading only `autopay` here would
    leave the new column a fact nobody consults — built and not wired (law 2).

    REFUSES rather than answering False when customers publishes nothing: *"we
    could not tell"* and *"they are not enrolled"* are different statements, and
    only the second one silently stops an intent from ever being recorded.
    """
    queryset = _resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            "apps.customers.selectors.account_queryset is not published, so whether this "
            "account is enrolled in autopay cannot be read. An intent is not recorded on a "
            "guess, and 'not enrolled' is not the same answer as 'unknown' (BR-CUS-059).",
            br_ref="BR-PAY-015",
        )
    row = queryset().filter(pk=account_id).values("autopay", "cash_only_no_autopay").first()
    if not row or not row["autopay"]:
        return False
    return not row["cash_only_no_autopay"]


@transaction.atomic
def record_intent_at_issue(
    *,
    actor: Any = None,
    account_id: Any,
    invoice_id: Any,
    amount: Decimal,
    due_date: date,
    currency: str = "USD",
) -> IntentResult:
    """BR-PAY-015's one write: an intent, dated the bill's DUE DATE.

    Worked, PE-12: BL-2608-018410 issues for autopay-enrolled ACC-1042 →
    amount **292.87** (the bill's total due), `scheduled_on` **22 Aug 2026** (its
    due date), status `awaiting_rails`, S32 chip +1.

    IDEMPOTENT ON THE INVOICE (TC-6). `UNIQUE (tenant, invoice_id)` is the
    guarantee, not a SELECT-then-INSERT that two workers would both win: a bill
    run retried after a crash re-issues the same invoice and must not promise
    the customer two drafts.

    A NON-ENROLLED ACCOUNT GETS NO INTENT (TC-4) and that is reported rather
    than raised — a bill run issuing four hundred bills must not fail because
    three hundred of those accounts are not on autopay.
    """
    if not isinstance(amount, Decimal):
        raise PaymentRuleError(
            f"amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a float "
            "(CLAUDE.md rule 2). Refused rather than converted.",
            br_ref="BR-PAY-015",
        )
    if not is_enrolled(account_id):
        return IntentResult(
            intent_id=None,
            created=False,
            account_id=str(account_id),
            invoice_id=str(invoice_id),
            problems=AUTOPAY_UNAVAILABLE
            + (
                {
                    "code": "account_not_enrolled",
                    "br_ref": "BR-CUS-059",
                    "detail": "this account is not enrolled in autopay, so no capture intent "
                    "was recorded (US-PAY-024 TC-4). Intents exist only for enrolled accounts.",
                },
            ),
        )

    existing = models.AutopayCaptureIntent.objects.filter(
        tenant_id=_tenant_id(), invoice_id=invoice_id
    ).first()
    if existing is not None:
        return IntentResult(
            intent_id=str(existing.pk),
            created=False,
            account_id=str(existing.account_id),
            invoice_id=str(existing.invoice_id),
            amount=existing.amount,
            scheduled_on=existing.scheduled_on,
            status=existing.status,
        )

    try:
        intent = models.AutopayCaptureIntent.objects.create(
            tenant_id=_tenant_id(),
            account_id=account_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            # BR-PAY-015 — *"dated the due date"*. Never user-set, never today.
            scheduled_on=due_date,
            status=models.INTENT_AWAITING_RAILS,
        )
    except IntegrityError:
        # The race the unique index exists for: another worker recorded this
        # invoice's intent between our SELECT and our INSERT. A lost race and a
        # replay are the same fact — one intent exists, ours is not it.
        winner = models.AutopayCaptureIntent.objects.get(
            tenant_id=_tenant_id(), invoice_id=invoice_id
        )
        return IntentResult(
            intent_id=str(winner.pk),
            created=False,
            account_id=str(winner.account_id),
            invoice_id=str(winner.invoice_id),
            amount=winner.amount,
            scheduled_on=winner.scheduled_on,
            status=winner.status,
        )

    core_audit.money_action(
        actor,
        AUDIT_INTENT_RECORDED,
        "autopay_capture_intent",
        str(intent.pk),
        after={
            "account_id": str(account_id),
            "invoice_id": str(invoice_id),
            "amount": str(amount),
            "currency": currency,
            "scheduled_on": due_date.isoformat(),
            "status": models.INTENT_AWAITING_RAILS,
            "job": None if actor is not None else "payments.autopay.record_intent",
        },
    )
    return IntentResult(
        intent_id=str(intent.pk),
        created=True,
        account_id=str(account_id),
        invoice_id=str(invoice_id),
        amount=amount,
        scheduled_on=due_date,
    )


def intent_rows(*, account_id: Any = None) -> list[dict[str, Any]]:
    """The S32 chip's and S33 column's rows, with the COMPUTED fulfilled state.

    BR-PAY-034 / field-map P-7: *"fulfilled"* is a display state derived from
    invoice settlement, not a stored transition. An intent is fulfilled when the
    allocations against its invoice cover the amount it promised — read from the
    same `allocations` rows every other settlement question is answered from.

    US-PAY-024 TC-3: a manual payment posted on the due date and cleared three
    days later leaves the account ON TIME (BR-PAY-021 reads `posted_at`), and
    `scheduled_on` is display metadata that never substitutes for money.
    """
    rows = models.AutopayCaptureIntent.objects.filter(tenant_id=_tenant_id())
    if account_id is not None:
        rows = rows.filter(account_id=account_id)
    rows = list(rows.order_by("scheduled_on", "created_at"))
    if not rows:
        return []
    settled = {
        row["invoice_id"]: row["total"] or ZERO
        for row in models.Allocation.objects.filter(
            tenant_id=_tenant_id(), invoice_id__in=[row.invoice_id for row in rows]
        )
        .values("invoice_id")
        .annotate(total=Sum("amount"))
    }
    return [
        {
            "id": str(row.pk),
            "account_id": str(row.account_id),
            "invoice_id": str(row.invoice_id),
            "amount": f"{row.amount:.4f}",
            "currency": row.currency,
            "scheduled_on": row.scheduled_on.isoformat(),
            "status": row.status,
            # Computed, never stored — see the docstring.
            "fulfilled": settled.get(row.invoice_id, ZERO) >= row.amount,
        }
        for row in rows
    ]


# ══ CR-068 · `CWP-040` — AUTOPAY AS A CUSTOMER READS IT (US-CWP-047) ═════
#
# ⚠ **THIS ADDS NO CHARGING PATH AND COULD NOT.** Everything below is a READ
# over the intents `record_intent_at_issue` already wrote, plus the account's own
# two flags. TC-5's guarantee — *"any v1 code path attempts to charge the stored
# method → Impossible"* — is enforced by there being nothing to call, and this
# block does not become the exception: no function here takes a method, an amount
# or a date to capture.
#
# ⚠ **AND EVERY REFUSAL BELOW IS A CODE, NEVER A SENTENCE** (B14 rule 35 — a
# catalogue is written in its own language, not translated from English; rule 33
# — a refusal caps at five or six words). Eleven catalogues write the words; the
# server says WHICH refusal.

#: Why the *Turn autopay on* control is disabled. `BR-CWP-056` / `CR-068` R3:
#: visible, disabled, carrying its reason — never hidden, never live-but-inert.
#:
#: ⚠ **IT READ `no_rails` UNTIL `apps/payments/gateway.py` LANDED (2026-09-05,
#: lane B, `US-CWP-045`) AND THAT WORDING IS NOW FALSE.** A charging path
#: exists: a customer can press a button and a provider is asked to charge.
#: What does not exist is anything that DRAFTS a payment on its own — nothing
#: consumes `AutopayCaptureIntent`, which is `BR-PAY-015`'s whole shape. The
#: refusal survived the change and its SENTENCE did not, which is the failure
#: hard-won law 2's mirror exists to catch, so the code says what is true:
#: *we cannot draft payments yet*.
HELD_NO_AUTOMATIC_CHARGE = "no_automatic_charge"
#: `BR-PAY-013`'s privilege sanction outranks it: an account that cannot be
#: drafted at all is refused for THAT reason, because it is the one that stays
#: true the day rails land.
HELD_CASH_ONLY = "cash_only"

#: The *next few* table's two states. `US-CWP-047` TC-2 and TC-3.
SLOT_SCHEDULED = "scheduled"
SLOT_NOT_BILLED_YET = "not_billed_yet"

#: *"Always the due date. It cannot be changed."* (`US-CWP-047` §5, blueprint
#: `P26`). Stated as DATA so no lane has to remember not to draw the control —
#: the posture `availability.py` takes for the deferred document upload.
WHEN_DUE_DATE = "due_date"

#: The three gaps this read NAMES rather than filling in.
CASH_ONLY = "cash_only_no_autopay"
CEILING_NOT_STORED = "ceiling_has_no_column"
NEXT_DUE_DATE_NOT_HELD = "next_due_date_not_held"

#: How much is taken. `US-CWP-047` §1 offers *the whole balance* or *a ceiling*;
#: only the first is expressible, because nothing stores the second.
HOW_MUCH_WHOLE_BALANCE = "whole_balance"

_ACCOUNT_FLAGS = ("autopay", "cash_only_no_autopay", "nsf_count")


def _account_flags(account_id: Any) -> dict[str, Any]:
    """The account's own three facts, read through customers' published queryset.

    REFUSES when customers publishes nothing, for `is_enrolled`'s reason: *"we
    could not tell"* and *"they are not enrolled"* are different statements and
    only the second one silently empties a screen.
    """
    queryset = _resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            "apps.customers.selectors.account_queryset is not published, so this "
            "account's autopay election cannot be read. CWP-040 refuses rather than "
            "drawing a screen that says autopay is off (BR-CUS-059).",
            br_ref="BR-PAY-015",
        )
    row = queryset().filter(pk=account_id).values(*_ACCOUNT_FLAGS).first()
    return dict(row or {"autopay": False, "cash_only_no_autopay": False, "nsf_count": 0})


def _display(value: Decimal) -> str:
    """Two decimals with a symbol — hard rule 2's display half, made once.

    Kept here rather than reaching for `apps.portal.money`: `payments` may not
    import the portal, and a second rounding rule is what `DEF-014` cost.
    """
    return f"${value.quantize(Decimal('0.01')):,}"


def portal_position(*, account_id: Any, today: date | None = None) -> dict[str, Any]:
    """`CWP-040` whole — what autopay IS on this account, and what it is not.

    ⚠ **THE *NEXT FEW* ROWS ARE THE STORED INTENTS AND ARE NEVER RECOMPUTED**
    (`US-CWP-047` TC-4, `BR-PAY-015`). `intent_rows` reads `amount` and
    `scheduled_on` off the row, so a bill corrected from `$142.18` to `$138.00`
    after the intent was written still shows **`$142.18`** — what the customer
    was told would be drafted. A read that recomputed from the invoice would
    pass every other case in `US-CWP-047` and fail only that one, silently, on a
    customer's money.

    ⚠ **THE UNBILLED SLOT CARRIES NO DATE, AND THAT IS A MEASURED ABSENCE
    RATHER THAN AN OVERSIGHT.** `US-CWP-047` TC-3 draws `14 Oct 2026 · — · NOT
    BILLED YET`. The AMOUNT is an em dash because the story says so — *"⚠ not an
    estimate"* — and the DATE is one because **nothing in this product answers
    an account's next due date before the bill is made**: an intent is written AT
    ISSUE, and the due date is `invoice.due_date`, which does not exist yet. The
    figure could only come from re-deriving billing's schedule (the cycle's
    `bill_day`, its frequency and its `due_days`) inside `payments` — a second
    implementation of *when does a bill fall due*, which is `CR-068` §2d's rule
    applied to a date instead of to money, and `DEF-154` is what two
    implementations of one figure cost. So the row is drawn, the state is real,
    and `NEXT_DUE_DATE_NOT_HELD` says why the date is missing.

    ⚠ **THE HELD REASON IS THE ONE THAT SURVIVES.** A cash-only account is
    refused for `HELD_CASH_ONLY` rather than `HELD_NO_RAILS`, because the
    sanction is still true the day rails land and `J12` step 6 says no rule ever
    auto-clears it.
    """
    del today  # the read is of stored rows; no clock decides anything here
    flags = _account_flags(account_id)
    cash_only = bool(flags.get("cash_only_no_autopay"))
    elected = bool(flags.get("autopay"))

    problems: list[dict[str, Any]] = list(AUTOPAY_UNAVAILABLE)
    if cash_only:
        problems.append(
            {
                "code": CASH_ONLY,
                "br_ref": "BR-PAY-013",
                "detail": "this account is cash-only after its bounces, so no card or bank "
                "payment may be taken on it. Nothing auto-clears the sanction (J12 step 6) — "
                "lifting it is an explicit, audited staff action.",
            }
        )
    problems.append(
        {
            "code": CEILING_NOT_STORED,
            "br_ref": "BR-CWP-056",
            "detail": "US-CWP-047 §1 offers a ceiling above which the utility rings rather "
            "than drafting, and `accounts` has no column to hold one. The choice is shown "
            "and refused rather than taking a figure with nowhere to put it.",
        }
    )
    problems.append(
        {
            "code": NEXT_DUE_DATE_NOT_HELD,
            "br_ref": "BR-PAY-015",
            "detail": "an intent is written AT BILL ISSUE and carries the invoice's own due "
            "date, so the NEXT month's date does not exist until that bill is made. It is "
            "left absent rather than derived from the cycle, which would be a second "
            "implementation of when a bill falls due.",
        }
    )

    scheduled = [
        {
            "scheduled_on": row["scheduled_on"],
            "amount": row["amount"],
            "display": _display(Decimal(row["amount"])),
            "currency": row["currency"],
            "state": SLOT_SCHEDULED,
            "fulfilled": row["fulfilled"],
        }
        for row in intent_rows(account_id=account_id)
    ]
    #: ⚠ **ONE UNBILLED SLOT, ALWAYS DRAWN.** The table's job is to say *this is
    #: what happens next*, and an account whose bills are all issued still has a
    #: next month. Drawing it with no figures is the honest version of that.
    next_few = scheduled + [
        {
            "scheduled_on": None,
            "amount": None,
            "display": None,
            "currency": None,
            "state": SLOT_NOT_BILLED_YET,
            "fulfilled": False,
        }
    ]

    return {
        #: The customer's own election, AND the sanction, resolved into the one
        #: question a screen asks: may this account be autopaid? `is_enrolled`
        #: is the single implementation of that and this mirrors it.
        "enrolled": elected and not cash_only,
        #: What they elected, untouched by the sanction — nothing here un-asks it.
        "elected": elected,
        "cash_only": cash_only,
        "bounces": int(flags.get("nsf_count") or 0),
        #: ⚠ FALSE TODAY AND FALSE UNTIL RAILS (BR-PAY-015). Never hidden.
        "available": False,
        "held_reason": HELD_CASH_ONLY if cash_only else HELD_NO_AUTOMATIC_CHARGE,
        "how_much": HOW_MUCH_WHOLE_BALANCE,
        "ceiling": None,
        "when": WHEN_DUE_DATE,
        "when_settable": False,
        "any_scheduled": bool(scheduled),
        "next_few": next_few,
        "problems": tuple(problems),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-024@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-07-autopay-receipts.md US-PAY-024 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-015/034/021 · 04-docs/05-modules/08-payments/03-field-map.md §7 + P-7 · 04-docs/05-modules/08-payments/07-pre-session-model.md PE-12 · 08-qa/01-e2e/journeys/J2-read-to-cash.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_024_autopay_intents.py (the one-intent-per-invoice guard and the not-enrolled path were driven RED first) · pytest tests -m isolation✔
# exceptions: (1) NOTHING CALLS `record_intent_at_issue` — BR-PAY-015 puts the trigger at BILL ISSUE (`apps/billing/issue.py`, US-BIL-005) and that module belongs to another lane. Every result carries `intent_recording_has_no_caller`, so the gap is on the wire (hard-won law 2)
#         (2) TC-5 IS ENFORCED BY ABSENCE, NOT BY A GUARD. There is no `charge()`, no method read and one status; a raising charge function would be a charging path with a flag on it
#         (3) FULFILLED IS COMPUTED (BR-PAY-034 / P-7) from `allocations`, never stored — a stored flag would disagree with the rows the first time a payment was reapplied
#         (4) A NON-ENROLLED ACCOUNT IS REPORTED, NOT RAISED: a bill run issuing 400 bills must not fail because 300 accounts are not on autopay
#         (5) ENROLMENT IS READ from customers' published queryset and REFUSES when unreadable — "unknown" is not "not enrolled" (G20)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
