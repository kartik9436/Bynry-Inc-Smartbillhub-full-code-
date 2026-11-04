# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-013 (S34 outstandings) · US-PAY-005 (S32 summary) ·
#           US-PAY-012 (write-offs) · US-PAY-014 (the collection ladder over an
#           S34 selection) · US-PAY-024 (autopay intents, read-only) ·
#           US-PAY-002 (the purpose + plan link on the record body) ·
#           US-PAY-001 (POST /accounts/{id}/payments — the S22/S35 Record
#           modal's exit: both BR-PAY-021 dates, the BR-PAY-001 allocation
#           choice, the BR-PAY-028 idempotent submit) · US-PAY-004
#           (GET /payments — the S33 Record-payments ledger and its IS-5
#           capability row; with `f.account_id`, the S21 Payments tab) ·
#           **2026-08-16, the payments SURFACE lane** — US-PAY-020 (S37 deposit
#           batches: the list, the KPI strip, the day-cut) · US-PAY-021 (S38
#           bank-statement import → auto-match → review) · US-PAY-022 (S40:
#           every difference explained with reason + GL) · US-PAY-023 (S39 batch
#           detail, the trail and BR-PAY-004's lock/Unreconcile) · US-PAY-015
#           (the tier already sent, so a manual send never doubles one) ·
#           US-PAY-018 (the plan-notice and missed-instalment position) ·
#           US-PAY-019 (the dunning + disconnect pause, and why it is running)
#           · **2026-09-01, CR-059 task 11 (CS-4)** — US-PAY-001 /
#           US-PAY-006 (GET /accounts/{id}/open-bills: what each open bill
#           STILL OWES, the list the S22/S35 bill picker aims money at and
#           the figures S21's Bills tab shows beside the issued total;
#           closes OQ-154, PO 2026-08-12 *"Build the open-balance read"*)
#           Screens: S22 · S33 · S35 · S21 (Payments tab) · S37 · S38 · S39 ·
#           S40 · S34 (the collections board)
# Rules:    BR-PAY-001 (default rules / specific / carry credit / split) ·
#           BR-PAY-002 (payments are append-only — this surface serves no
#           write verb on an existing payment at all) · BR-PAY-010 (the
#           allocation order) · BR-PAY-012 (purpose) · BR-PAY-021 (posting date
#           ≠ clearing date — BOTH are collected) · BR-PAY-022 (the
#           single-entry field set) · BR-PAY-026 (method is a tenant lookup) ·
#           BR-PAY-027 (the S33 capability row) · BR-PAY-028 (idempotent
#           submit; key mechanics Eng-Lead 🔒) · BR-PAY-033 (the posting date
#           is USER-ENTERED — never the system timestamp) · BR-PAY-036 (a
#           payment is always accepted) · BR-SHL-011 (list grammar) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1
#           (cross-tenant reads as absent) · BR-TEN-043 (event time is an
#           input, never a clock) · CLAUDE.md rule 1 · rule 2 · rule 6 · rule 7
#           · **2026-08-16** BR-PAY-004 (a reconciled batch LOCKS; Unreconcile
#           is the only reversal) · BR-PAY-019 (bank rec in FINANCE, Owner/
#           Finance roles; every difference carries reason + GL) · BR-PAY-025
#           (SUPERSEDED-IN-PART 2026-09-22: batches group a TILL × a TENDER;
#           the day is still the POSTING day) · BR-PAY-035
#           ("Force match anyway" permanently SUPERSEDED — no route here
#           carries a flag that would reconcile a residual) · BR-PAY-016 /
#           BR-PAY-017 (the ladder's rungs and its stop conditions) ·
#           BR-CUS-043 (the plan pause, and what it does NOT cover)
# Tests:    06-backend/tests/test_us_pay_004_payments_api.py ·
#           06-backend/tests/test_us_pay_020_023_bankrec_surface.py ·
#           06-backend/tests/test_us_pay_015_019_collections_surface.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (the committed contract snapshot
#           moves with any endpoint added here — BE-11 TC05) ·
#           07-frontend/src/features/payments/ (S33 + the Record modal ·
#           DepositsPage S37 · BankImportWizard S38 · DepositBatchPage S39+S40 ·
#           CollectionsPage · WriteOffQueuePage — which call exactly these
#           paths) · apps/payments/bankrec_read.py + collections_read.py (the
#           read halves these routes serve)
# ───────────────────────────────────────────────────────
"""payments API endpoints per A11 §S22/§S33 as amended by 11b §1 + §2.9.

THIN by law (B8 / LAW 0): parse → call a service or a selector → serialize.
There is no ORM here, no money arithmetic, no allocation logic and no clock;
every refusal leaves this file as a `core.errors` catalog exception (gate G9),
including the ones the service layer raises as `PaymentRuleError`, which is
translated at this boundary and nowhere else.

WHY THIS FILE EXISTS TODAY AND NOT YESTERDAY. It was ONE LINE — a docstring with
no `urlpatterns` — while `apps/payments/services.record_payment` could already
take a customer's money, allocate it across their open bills and post it to the
books, under nineteen passing tests. **No human being could reach any of it.**
That is hard-won law 2 at feature scale, and the two cases at the top of this
lane's test file are about nothing else: the routes are resolved through the
REAL root URLconf and then called over real HTTP, because an `api.py` that
exports `urlpatterns` is not an endpoint until `config/urls.py` includes it.

The two contract rows this slice serves:

    POST /accounts/{id}/payments   US-PAY-001   S22 · S35 Record payment
    GET  /payments                 US-PAY-004   S33 ledger · S21 Payments tab

AND, ADDED 2026-09-01 BY CR-059 CS-4, the read those two screens were missing:

    GET  /accounts/{id}/open-bills  CR-059 CS-4  S22 · S35 picker · S21 Bills

It is a READ over `billing_seam.open_invoices_for_account`, which already
computed every figure it serves. Two of BR-PAY-001's four staff allocation
choices — *"A specific bill"* and *"Split across bills"* — were CONFIRMED law,
executed by the allocator and accepted by the POST above, and rendered DISABLED
on both screens for one reason: nothing served the list a clerk aims at, and
`GET /invoices` serves the ISSUED total, which is a different number the moment
anything has been paid (**247.87 issued, 47.87 open — PE-2**). OQ-154 was closed
by the PO on 2026-08-12 in the words *"Build the open-balance read"*, choosing
this path on this surface.

`POST /accounts/{id}/payments` IS 11b §1'S "STALE" ROW, REGENERATED. A11's
original params were `amount, method, apply_to`; 11b marks the row STALE because
that payload contradicts BR-PAY-021 (both dates, always), BR-PAY-033 (the
posting date is the user's), BR-PAY-012 (every payment carries a purpose) and
BR-PAY-022 (reference + allocation choice). The body below is that regeneration
— the entry-point PLACEMENT was never stale (BR-CUS-037 puts it on the account),
so the path is A11's own.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT SERVED HERE — each with the reason, none of them stubbed
════════════════════════════════════════════════════════════════════════════
A route that answers 501 is a promise. None of these is mounted:

  · `POST /payments/{id}/nsf` · `/reverse` · `/reallocate` (11b §2.9) —
    EP-PAY-03. Their behaviour is not merely unbuilt, it is UNDECIDED: the
    bounce cases sit in `12-governance/12-payments-decision-batch.md` as
    OQ-132/133/134 awaiting the PO, and BR-PAY-011's window messaging is
    server-computed. A reverse route without the reversal behind it would state
    a consequence it cannot honour.
  · `POST /refunds`, `/write-offs`, `/collections/notices`,
    `/payments/{id}/receipt` — EP-PAY-03/04 and US-PAY-025; three of the four
    also wait on PO decisions in the same batch (OQ-135, OQ-136, OQ-137).
  · `POST /payments/imports…` (US-PAY-003) — the staged lockbox/CSV import.
    Its posting-date semantics are OQ-131, blocking, in the same batch.
  · `GET /payments/summary` and `GET /autopay/intents` (S32) — US-PAY-005 and
    US-PAY-024, their own stories.
  · `GET /payments/{id}` — deliberately NOT minted. Neither A11 nor 11b §2.9
    contracts a payment DETAIL resource, and the one thing a detail would add
    over the list row — what the payment paid — rides on the row itself as
    `applied_to`. Inventing a path here would be this layer writing contract.

`GET /payments` is the read; there is NO PUT, PATCH or DELETE on any payment
path in this API (BR-PAY-002 / HR-4 / 11b G8), so a forged one is refused by the
router with 405 before any view runs. A correction is a new reversing row.
"""

import base64
from binascii import Error as BinasciiError
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors  # noqa: F401 — the catalog this file's refusals come from (G9)
from core.pagination import StandardPagination, parse_list_params
from core.permissions import AdminOrClerk, AdminOrExecutive, AnyTenantRole
from core.tenancy import require_tenant

from apps.payments import (
    allocation,
    autopay,
    bankrec_read,
    billing_seam,
    collections_read,
    counter_receipt_models,
    counter_receipts,
    counters,
    custom_values,
    ladder,
    ledger_seam,
    models,
    open_bills,
    outstandings as outstandings_read,
    reconciliation,
    selectors,
    services,
    settings_seam,
    summary as summary_read,
    writeoffs,
)
from apps.payments.exceptions import PaymentRuleError
from apps.payments.duplicates import PossibleDuplicatePayment


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="payments.payload_not_object")
    return data


def _actor(request: Any) -> Any:
    """WHO is recording this payment, from the SESSION — never from the body.

    `audit_log.actor_user_id` is hard rule 7's evidence half, so the one thing
    it must not be is client input.
    """
    return getattr(request, "user", None)


def _required(payload: dict[str, Any], name: str, *, message_key: str) -> Any:
    """A field the body must carry, refused with the copy the CALLER names.

    `message_key` is passed in as a LITERAL by every call site rather than
    composed here as `f"payments.record.{name}_required"`, and that is not a
    style choice: a key built at runtime is a key no catalogue check can see.
    G18 asserts that every key has a call site and every call site resolves, and
    it reads literals — a composed key would pass the gate by being invisible to
    it and then render as its own raw text to a clerk, which is the exact defect
    G18 exists to catch.
    """
    value = payload.get(name)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key=message_key,
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return value


def _money(payload: dict[str, Any], name: str, *, message_key: str) -> Decimal:
    """A money amount as `Decimal`, parsed from the STRING the form submits.

    `message_key` is the copy for an ABSENT amount, named by the caller as a
    literal so gate G18 can see the call site (see `_required`).

    CLAUDE.md rule 2 — never a float, at any point. `Decimal(str(...))` reads
    the digits the clerk typed; a JSON number that arrived as a float would
    already have lost them, which is why the form sends a string and the service
    refuses a float outright rather than converting one.
    """
    raw = _required(payload, name, message_key=message_key)
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.amount_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem


def _moment(payload: dict[str, Any], name: str, *, message_key: str | None) -> datetime | None:
    """A BR-PAY-021 date, exactly as the user gave it — no clock, ever.

    The PO ruled on this directly on 2026-08-11: *"posting and actual dates can
    differ; ask actual date to user."* So both dates are INPUTS. An absent
    posting date is REFUSED rather than defaulted to `now()` — a defaulted
    posting date would let the moment a request happened to arrive decide
    whether a customer owes a late fee (BR-PAY-033, and gate G6 bans a clock in
    this path). An absent CLEARING date is legal and means `processing`.

    Two shapes are accepted, because two callers exist:
      · a full ISO-8601 instant — its own offset is kept;
      · a `YYYY-MM-DD` calendar date, which is what the S22 date field collects
        (BR-PAY-033 pre-fills one and the clerk may override it).

    `message_key` is the copy for an ABSENT date and doubles as the REQUIRED
    flag: `None` means the field is optional. Named by the caller as a literal
    so gate G18 can see the call site (see `_required`).

    ════════════════════════════════════════════════════════════════════════
    A BARE DATE IS MIDNIGHT IN THE UTILITY'S OWN TIMEZONE (DEF-094, 2026-08-15)
    ════════════════════════════════════════════════════════════════════════
    **OQ-153 is CLOSED and this is the ruled behaviour.** PO 2026-08-12:
    *midnight in the UTILITY's own timezone*, which BR-TEN-081 states. This
    docstring used to say *"a bare date … is anchored to UTC … WHICH INSTANT a
    user-entered calendar date should become, in whose timezone, is OQ-153 —
    raised, not answered"*, and that sentence outlived the ruling by three days.

    **THE DEFECT THAT MADE IT URGENT WAS A CLOSED DEFECT (DEF-094).** DEF-082
    built the READ half — `tenant_today()` reads the tenant's zone, proved by
    moving the answer across a date boundary: frozen at **2026-08-22T04:30:00Z**
    a utility on `America/Chicago` answers **2026-08-21** while UTC has already
    rolled over. Closing it made the rule LOOK shipped. It was not: a Houston
    clerk typing **22 August** still stored `2026-08-22T00:00:00Z`, and every
    screen — reading through the half that WAS fixed — displayed **21 August**.

    **WHAT A ONE-DAY SHIFT COSTS, in the product's own rules.** BR-PAY-021's
    on-time test is `posted_at <= due_date`, so a payment slipping backwards a
    day can clear a late fee that was owed and slipping forwards can charge one
    that was not (BR-BIL-001, on a **$25.00** floor). BR-PAY-025 allows exactly
    ONE deposit batch per day per method, so a payment on the wrong side of
    midnight lands in the wrong drawer day — and BR-REP-013 groups the deposit
    report by that day. A period boundary is the same shift at month scale: the
    money lands in the wrong month's books.

    The zone is read THROUGH THE SEAM (`settings_seam.tenant_timezone`, which
    resolves tenancy's own `tenant_timezone()` by name) and never re-derived
    here — that is the whole lesson of the two halves disagreeing, and a second
    derivation in this file would be the defect rebuilt one layer up.

    **A FULL INSTANT IS UNTOUCHED.** `2026-08-22T10:30:00-05:00` states its own
    offset and this function has nothing to add to it; an API client that sends
    a real instant means it. Only a value that carries NO offset is anchored,
    because only that value is missing one. A naive `2026-08-22T10:30` — a time
    of day with no zone — is anchored in the tenant's zone too, for exactly the
    same reason the bare date is: it came from a human in that utility.
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if message_key is not None:
            # Always raises; one refusal shape and one copy key for the pair.
            return _required(payload, name, message_key=message_key)
        return None
    text = str(raw).strip()
    try:
        # Python 3.11's `fromisoformat` already accepts the date-only form and
        # answers midnight, so one parse covers both shapes; what it never does
        # is invent an offset, which is the next lines' whole job.
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from problem
    if parsed.tzinfo is None:
        # BR-TEN-081 / OQ-153. `.replace(tzinfo=...)` and not `astimezone`: the
        # clerk typed a WALL-CLOCK value and it is that wall-clock value in
        # their own zone, not a UTC instant being converted into one.
        return parsed.replace(tzinfo=settings_seam.tenant_timezone())
    return parsed


class _Target:
    """One bill the staff member NAMED (BR-PAY-001 `specific` / `split`).

    A plain carrier matching `allocation.AllocationTargetLike` — the allocator
    reads `invoice_number` and `amount` and nothing else. `amount is None` is
    the `specific` instruction ("this bill, up to what it owes"); a `split`
    states an amount per bill and the allocator checks that they sum to the
    payment exactly (US-PAY-006 TC-4). Nothing here divides money.
    """

    __slots__ = ("invoice_number", "amount")

    def __init__(self, invoice_number: str, amount: Decimal | None) -> None:
        self.invoice_number = invoice_number
        self.amount = amount


def _targets(payload: dict[str, Any]) -> tuple[_Target, ...]:
    raw = payload.get("targets") or []
    if not isinstance(raw, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.targets_invalid",
            field_errors=[{"field": "targets", "code": errors.VAL_FORMAT}],
        )
    built: list[_Target] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("invoice_number"):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="payments.record.target_invoice_required",
                field_errors=[{"field": "targets", "code": errors.VAL_REQUIRED}],
            )
        amount = entry.get("amount")
        built.append(
            _Target(
                invoice_number=str(entry["invoice_number"]),
                amount=(
                    None
                    if amount in (None, "")
                    else _money(entry, "amount", message_key="payments.record.amount_required")
                ),
            )
        )
    return tuple(built)


def _installment_seq(payload: dict[str, Any]) -> int | None:
    """Which instalment the clerk named, or None for the ruled default.

    CR-059 CS-23 · task 6. **A WHOLE NUMBER OR NOTHING** — `"2"` and `2.5` are
    refused rather than coerced, for `_int_field`'s reason one module along:
    4.5 instalments is not a schedule, and a string that happened to parse would
    let a typo mark the wrong row of a customer's signed agreement as met.
    `True` is an `int` in Python and is refused explicitly, which is the trap
    every hand-rolled integer check in this repo has had to close.

    `None` means the caller did not choose, and the service then links the
    EARLIEST UNMET instalment (`plans.earliest_unmet_installment`). It is not a
    fallback for a bad value: a bad value is a refusal.
    """
    raw = payload.get("installment_seq")
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.record.installment_seq_whole_number",
            field_errors=[{"field": "installment_seq", "code": errors.VAL_FORMAT}],
        )
    return raw


def _optional_date(payload: dict[str, Any], name: str) -> date | None:
    """A calendar DAY the body may leave out — CR-059 CS-30's cheque facts.

    **Absent and unreadable are different answers.** Absent means the payment
    carries no cheque state, which is every payment that is not a cheque and is
    what every caller before today sent. Unreadable is a REFUSAL and never a
    silent `None`: a cheque dated `"14/07/2026"` that quietly became "no date"
    would drop the hold the deposit-batch cut obeys, and the cheque would be
    banked before the day it exists.

    A DATE and not a moment, deliberately. `bankable_from` is compared against a
    business day by `cheques.bankable_on`, and `cheque_date` is what a person
    wrote on a piece of paper; neither has a time of day, and giving one a
    timezone would make the same cheque bankable on different days in different
    places (BR-TEN-043's own argument).
    """
    raw = payload.get(name)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.date_invalid",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _as_catalog_refusal(refusal: PaymentRuleError) -> errors.BizError:
    """A service-layer rule refusal, as the ONE catalog exception G9 allows.

    `PaymentRuleError` is deliberately not a catalog exception (see
    `apps/payments/exceptions.py`): it is raised inside batch paths that answer
    no request, and a catalog code carries an HTTP status. This layer IS
    answering a request, so it is where the translation belongs and the only
    place in the module that knows what HTTP is.

    ONE code for all of them — 422 BIZ-COMPLETENESS — for the reason
    `apps/billing/api._as_catalog_refusal` gives: every refusal that reaches
    here has the same shape (*this cannot be done as asked, here is the rule and
    here is the sentence a clerk can act on*), and picking among the nine BIZ
    codes per refusal would be this layer INTERPRETING rules it does not own.
    The refusal's own sentence travels in `params.detail` and its BR-ID in
    `br_ref`, which is what the modal renders (BR-SHL-020) and what BR-AUD-018's
    attempt row records.
    """
    # DEF-PAY-10764: a refusal that names something on screen brings its own
    # key and params (LBX-09's statement line); the English sentence still
    # travels as `detail` for the audit row. Every other refusal is unchanged.
    own_key = getattr(refusal, "message_key", None)
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-022",
        message_key=own_key or "payments.record.refused",
        params={**(getattr(refusal, "params", None) or {}), "detail": str(refusal)},
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])  # A4 payments_record: Executive is VIEW
def account_payments(request: Any, account_id: str) -> Response:
    """Record ONE payment against one account (11b §1 regenerated · US-PAY-001).

    The body is BR-PAY-022's field set: *"account → amount, method,
    posting+clearing dates, reference, allocation choice"*, plus BR-PAY-012's
    purpose and r14 #4's memo.

        amount           decimal STRING, > 0
        posted_at        the USER's posting date — required (BR-PAY-033)
        cleared_at       the clearing date, or absent = still processing
        method           a tenant method CODE (BR-PAY-026) — optional
        confirmation     check / confirmation number — optional
        memo             optional
        purpose          bill | deposit | plan_down | prepay (default bill)
        apply_to         oldest_first | newest_first | carry_credit |
                         specific | split (BR-PAY-001; default oldest_first)
        targets[]        {invoice_number, amount?} for specific / split
        idempotency_key  the form's client token — REQUIRED (see below)
        currency         optional; must equal the account's (BR-TEN-042)
        type             payment | credit | adjustment (default payment)
        reason           a tenant reason code — REQUIRED for the latter two

    **`idempotency_key` IS REQUIRED, and refusing without it is the point.**
    `record_payment` stores no key when the caller names none, and a double
    submit then records two payments — its docstring says so and says the API
    layer will pass one. Generating one HERE would produce a different string on
    the second submit and dedupe nothing while looking as though it had, so the
    only honest options are "require it" and "take the money twice".

    A REPLAY ANSWERS 200 WITH THE ORIGINAL PAYMENT and `created: false`, not
    409. 11b §3 G7 makes a duplicate a 409 for the four operations it
    enumerates — bill runs, read/payment IMPORTS, webhooks, tenant provisioning
    — and a staff double-click is none of them: BR-PAY-028's field-map row reads
    *"duplicate submit → single row"*, US-PAY-001 TC-6's expected outcome is
    "One row only", and G7's own list already contains the same shape
    (`POST /tenants`, *"repeat returns existing tenant"*). A 409 toast for a
    button that worked is a wrong answer a clerk would act on.

    201 on a new payment, with the allocation inline: a clerk who has just taken
    $292.87 has to be shown what it paid, and the allocator worked that out in
    the same transaction.
    """
    require_tenant(request)
    payload = _payload(request)
    _required(payload, "idempotency_key", message_key="payments.record.idempotency_key_required")
    # ── CR-136-BRC07 `P2.23` · A HAND TENDER NEEDS AN OPEN TILL ────────────
    # PO ruling 2026-09-23 §3.4, verbatim: *"(a) Refuse it. \"Start your
    # counter first.\" One press, then take the money. It is the only option
    # where every cash dollar belongs to somebody"*.
    #
    # ⚠ **THIS DOOR AND NOT `record_payment`, AND THE BLAST RADIUS IS WHY.**
    # The service is reached by nine callers, and three of them are not a
    # person at a counter: `payment_import`/`import_writer` (a lockbox file),
    # `webhooks` (a gateway) and `sample_data` (the demo seed, which records
    # cash for a utility that has no clerks). A guard in the service would
    # refuse a utility's own lockbox import and stop every fixture in the
    # suite from seeding — which is not what was ruled, and the ruling names
    # the ENDPOINT: *"Enforced at the endpoint, not by hiding a button"*
    # (`BR-SHL-025`). **The rule itself has exactly one implementation**, in
    # `counters.assert_till_open_for_tender`; this is a call site, not a copy.
    #
    # ⚠ **THE DOORS THAT DO NOT CALL IT ARE NAMED RATHER THAN LEFT TO BE
    # DISCOVERED:** the transfer path. ⚠ **`POST /customers/{id}/payments` and
    # `POST /accounts/{id}/premises-payments` WERE NAMED HERE UNTIL 2026-10-30
    # AND NOW CALL IT** (`tenders_api._open_till`, `DEF-PAY-7642` /
    # `DEF-PAY-6322`): `OQ-PAY-12601` closed on *"back office or counter … it
    # is same process, they ahve to open the counter"*, and the PO's audit
    # ruling of 2026-10-30 names the multi-account door with the till check.
    #
    # ⚠ **THE RETURN VALUE IS THE POINT, AND IT WAS THROWN AWAY UNTIL
    # `DEF-PAY-6226`.** `assert_till_open_for_tender` answers the OPEN TILL
    # for the three hand tenders and `None` for the other four, and this line
    # discarded it — so the refusal worked, `P2.23` was DONE, and **no payment
    # ever named the till it was taken at**. A clerk opened a counter at 08:55,
    # took seventeen payments and closed an empty drawer at 17:30, because
    # every dollar banked under the day's system till, the one that is openly
    # nobody's. One name on one line is the whole wiring (hard-won law 2).
    try:
        counter_session = counters.assert_till_open_for_tender(
            _actor(request), payload.get("method")
        )
    except PaymentRuleError as refusal:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=getattr(refusal, "br_ref", None) or "BR-PAY-1186",
            # A LITERAL key, resolved at the RAISE SITE — G32 can only see a
            # helper defined in the same file, and reported 0 unresolved over
            # 21 live refusals that reached a clerk as silence.
            message_key="payments.counter.till_required",
            params={"detail": str(refusal)},
        ) from refusal
    try:
        result = services.record_payment(
            _actor(request),
            account_id=account_id,
            amount=_money(payload, "amount", message_key="payments.record.amount_required"),
            posted_at=_moment(
                payload, "posted_at", message_key="payments.record.posted_at_required"
            ),
            cleared_at=_moment(payload, "cleared_at", message_key=None),
            currency=payload.get("currency"),
            method_code=payload.get("method"),
            confirmation=payload.get("confirmation"),
            memo=payload.get("memo"),
            purpose=payload.get("purpose") or models.PURPOSE_BILL,
            # US-PAY-002 / BR-PAY-012 — the plan a DOWN PAYMENT attaches to.
            # Optional: BR-CUS-043's one-live-plan invariant means the
            # account is enough to find it, and the S22 counter form does
            # not know a plan id.
            plan_id=payload.get("plan_id"),
            # ⛔ CR-059 CS-23 · task 6 — THE CLERK'S CHOICE, WHICH THIS LAYER
            # DID NOT SEND. `services.record_payment` has taken
            # `installment_seq` since 2026-09-01 and its own trailer says so in
            # terms: *"the S22/S35 half of CS-23 is server-side only … no screen
            # draws the schedule or offers the 'change it' control yet —
            # `installment_seq` is an argument the API layer does not send."*
            # CS-23 asks for *"the option to change it"* on those screens, so
            # the argument travels now. `None` — which every batch caller and
            # every form that does not offer the control still sends — keeps the
            # ruled default: the EARLIEST UNMET instalment.
            installment_seq=_installment_seq(payload),
            order=payload.get("apply_to") or allocation.ORDER_OLDEST_FIRST,
            targets=_targets(payload),
            idempotency_reference=payload.get("idempotency_key"),
            # ── CR-136-BRC07 `P2.13` · `DEF-PAY-6226` ───────────────────────
            # `None` for `ach`, `card`, `wire` and `lockbox` — the helper above
            # answers `None` for them and the service refuses a till for them
            # BY NAME, so neither layer alone decides it. The service stamps
            # the till AND the till's batch for this tender in the payment's
            # own INSERT: *"The id attaches when taken. Not at close."*
            counter_session_id=(
                None if counter_session is None else counter_session.pk
            ),
            # ── CR-059 CS-35 · the type, and the reason that goes with it ────
            # The column and all three values have existed since the first
            # payments migration and the frontend has published them since it
            # shipped; nothing had ever sent one, so the only way to put a
            # goodwill credit on an account was to record a fake payment.
            # `type` defaults to `payment`, so every existing caller is
            # unchanged. The service refuses an unknown value, requires the
            # reason on a credit or an adjustment, refuses one on a payment, and
            # enforces the System-Admin threshold — all server-side, because a
            # screen that hides a control is not an authorisation (BR-SHL-025).
            payment_type=payload.get("type") or models.PAYMENT_TYPE_PAYMENT,
            reason_code=payload.get("reason"),
            # ── CR-059 CS-30 · task 57 — THE THREE CHEQUE FACTS ─────────────
            # ⛔ The same shape as `installment_seq` above, and the same finding.
            # `services.record_payment` has taken `cheque_date`, `drawer_bank`
            # and `bankable_from` since 2026-09-03 and its own trailer says the
            # INSERT is the only thing that may write them (hard rule 4's
            # trigger refuses a later column change on a row that is not
            # `processing`). **This layer did not send them**, so a cheque could
            # not be given a date, a drawer bank or a hold through any door a
            # person can reach — `POST /payments` was the only writer and it
            # dropped all three. Hard-won law 2: the argument existed and
            # nothing passed it.
            #
            # `None` on all three — what every existing caller still sends —
            # records a payment with no cheque state, exactly as before.
            # `cheques.validate_cheque_fields` refuses a half-stated cheque and
            # `refuse_a_duplicate_cheque` refuses a repeat of the same number
            # from the same bank; neither rule is copied here (one owner).
            cheque_date=_optional_date(payload, "cheque_date"),
            drawer_bank=payload.get("drawer_bank"),
            bankable_from=_optional_date(payload, "bankable_from"),
            # ── CR-161-BRC10 W5 · the utility's own payment fields ──────────
            # The Record payment page (S35) always sends its answers; the
            # other doors on this endpoint draw none and send none, so a
            # required field binds only on S35 (`custom_values` says why).
            **custom_values.entry_arguments(payload),
            # ── DEF-PAY-9263 · BR-PAY-1199 — "Looks like a duplicate" ───────
            # PO 2026-10-03: *"Warn "Looks like a duplicate", and let the
            # clerk confirm"*. Every door on this endpoint is a person at a
            # screen, so every one asks; `confirm_duplicate: true` is the
            # clerk's *Record anyway* and nothing else turns the warning off.
            warn_on_possible_duplicate=True,
            duplicate_confirmed=payload.get("confirm_duplicate") is True,
        )
    except PossibleDuplicatePayment as warning:
        raise as_duplicate_warning(warning) from warning
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(selectors.recorded_payment_dict(result), status=201 if result.created else 200)


def as_duplicate_warning(warning: PossibleDuplicatePayment, **extra: Any) -> errors.BizError:
    """The card/ACH duplicate WARNING as a 409 the screen answers with two buttons.

    `BIZ-IDEMPOTENT` because it is the catalogue's *"this looks like one already
    done"* (B12 §3, 409). The earlier payment travels in `params` — its receipt
    number, day, amount, currency and reference — so the screen can name it
    without a second read. Nothing was written; the clerk's *Record anyway*
    resends the same body with `confirm_duplicate: true`.
    """
    return errors.BizError(
        errors.BIZ_IDEMPOTENT,
        br_ref=getattr(warning, "br_ref", None) or "BR-PAY-1199",
        # A LITERAL key at the raise site (G32).
        message_key="payments.record.possible_duplicate",
        params={**dict(warning.earlier), "possible_duplicate": True, **extra},
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive View
def payments(request: Any) -> Response:
    """S33 Record payments (11b §1 · US-PAY-004), and the S21 Payments tab
    scoped by `f.account_id` — one endpoint, because a per-tab read model would
    be a second place for the "Applied to" join and the BR-PAY-021 date columns
    to drift.

    Pagination is mandatory on every list (11b G5) and its sizes are ratified at
    50/100/200/500/1000, default 50. The page is taken in the DATABASE.

    Two members ride alongside the DRF envelope, exactly as `GET /invoices`
    carries its roll-up:

      `totals`  US-PAY-004 TC-1's "totals row per current filter" — and it
                states no money figure when the filter matched nothing or when
                the rows could not honestly be summed (`selectors`).
      `methods` the tenant's LIVE method list (BR-PAY-026 / BR-REP-006). The
                S33 method FILTER and the S22 Record form's picker read this one
                list, so the two can never offer different vocabularies. It is
                served here rather than at `GET /lookups/payment_methods`
                because payments has registered no handler for that list, so
                that route 404s on this deployment — REPORTED.
    """
    require_tenant(request)
    params = selectors.list_params(request.query_params)
    paginator = StandardPagination()
    queryset = selectors.payment_list_queryset(params)
    page = paginator.paginate_queryset(queryset, request)
    # ⚠ **`payment_rows`, NOT a comprehension over `payment_row`** — the Batch
    # column's lookup is taken ONCE for the page (`NFR-3`: a page costs a page).
    response = paginator.get_paginated_response(selectors.payment_rows(page or []))
    response.data["totals"] = selectors.payments_totals(queryset)
    response.data["methods"] = selectors.active_payment_methods()
    return response


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive View
def payments_selection_total(request: Any) -> Response:
    """`POST /payments/selection-total` — CR-059 CS-43 (S33's selection bar).

    The acceptance line, verbatim from the change register: *"four rows selected
    on page one and two on page two show `6 selected · 3,918.44` — not a
    blank."*

    **A POST that writes nothing, and the verb is the considered half.** The body
    is a list of payment ids and a clerk may tick five hundred of them; a query
    string carrying five hundred uuids is 18,000 characters and meets a proxy's
    URL limit long before it meets the server. So the selection travels in a
    body. Nothing is created, nothing is stored, and the same request may be sent
    twice with no consequence — which is why it needs no idempotency token and
    has none.

    **200 always, including for an empty selection**, which answers
    `count: 0, amount: null, amount_unavailable: "no_rows"`. A `0.00` there would
    read as *"these rows are worth nothing"* rather than *"nothing is selected"*,
    and the two are different sentences on a screen a clerk is about to press
    Refund on.

    **`AnyTenantRole`, matching `GET /payments`.** This is a total over rows the
    caller can already list one page at a time; a narrower gate here would mean a
    role could read six payments and not their sum.

    Money comes back twice, both as STRINGS (CLAUDE.md rule 2): `amount` is the
    exact stored decimal and `amount_display` is the two-place figure the bar
    renders. The client formats neither — `rating.selectors._display_money`
    records why (DEF-364: a percent shipped as `0.015000` and a customer read
    `0.015000`).
    """
    require_tenant(request)
    payload = _payload(request)
    ids = payload.get("payment_ids")
    if ids is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.selection.ids_required",
            field_errors=[{"field": "payment_ids", "code": errors.VAL_REQUIRED}],
        )
    if not isinstance(ids, list) or any(not isinstance(one, str) for one in ids):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.selection.ids_invalid",
            field_errors=[{"field": "payment_ids", "code": errors.VAL_FORMAT}],
        )
    return Response(selectors.selection_total(ids))


def _as_of(request: Any) -> date:
    """The business day a read-model is asked about (BR-TEN-043).

    REQUIRED, and the requirement is the rule rather than strictness. This
    module reads NO CLOCK — a pre-existing assertion in
    tests/test_us_pay_004_payments_api.py checks the source for one — because a
    server clock decides a business day in the SERVER's timezone, and the
    tenant's own timezone cannot be chosen yet (OQ-153, blocked by DEF-082).
    Every service below takes `as_of` as an argument for the same reason
    (BR-TEN-043), so a clerk reconciling yesterday asks for yesterday and gets
    yesterday's ageing rather than a figure that moved under them at midnight.
    """
    raw = request.query_params.get("as_of")
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="payments.as_of_required", params={"field": "as_of"}
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="payments.as_of_invalid", params={"value": raw}
        ) from exc


def _query_date(request: Any, name: str) -> date | None:
    """An OPTIONAL date range bound off the query string (Finance `P2.19`).

    ⚠ **ABSENT IS `None` AND A MALFORMED VALUE IS A REFUSAL — the two are not
    the same and must not collapse into each other.** A `try/except: return
    None` here would make `?from=2026-13-45` mean *no lower bound*, so the
    clerk sets a date range, the server ignores it, and the same rows come
    back: hard-won law 7's check that cannot fail, wearing a filter's clothes.
    `_as_of` above refuses a bad date for the same reason; the only difference
    here is that nothing is a legal answer.
    """
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="payments.as_of_invalid", params={"value": raw}
        ) from exc


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive View
def outstandings(request: Any) -> Response:
    """S34 Outstandings (US-PAY-013) — AR high→low with its ageing strip.

    ⚠ **THIS CAN NOW PAGE AND SORT IN SQL, AND IT DOES SO ONLY WHEN ASKED —
    READ THE SECOND WARNING BELOW BEFORE QUOTING THE FIRST.** The docstring
    that stood here said "Unpaginated ON PURPOSE" and `CLAUDE.md` QUOTED IT AS
    THE `NFR-3` BREACH IT NAMES BY NAME (`DEF-PAY-4221`). The argument it made
    was that the KPI tiles must foot to the rows exactly (US-PAY-013 TC-1) and
    that a paginated body would make the tiles describe a page instead of the
    debt. **The premise was wrong rather than the conclusion:** the tiles are
    a SQL aggregate over the whole filtered set whether a page is cut or not,
    so the strip ties to the debt either way.

    Measured on real PostgreSQL 16 (`10-scripts/cr138_p4_debtor_cost.py`,
    median of 3 after a discarded warm-up, 2026-09-23):

        2,046 debtors    3.089 s ·  2,041 statements  →  0.232 s · 13
        40,046 debtors  61.539 s · 40,041 statements  →  3.746 s · 12

    ⚠ **A WEB WORKER IS GIVEN SIXTY SECONDS** (`docker-entrypoint.sh`,
    `GUNICORN_TIMEOUT:-60`), so at 40,046 debtors — the top of the ICP — the
    old read did not merely run slowly: **it was killed by the worker before
    it answered.** The 2,046-debtor figure is two thirds of the OLD 3,000
    ceiling, so the sentence justifying it was already 3 seconds of server
    time inside the tier it claimed to be correct in.

    ⚠⚠ **AND THOSE FIGURES ARE FOR A CALLER THAT ASKS FOR A PAGE. NOTHING
    ASKS YET — `DEF-PAY-4221` STAYS OPEN.** See the comment at the call
    below: the screen declares ten sorts, a search and four filters, this
    query honours three sorts and two filters, and cutting a page underneath
    the rest would be a live screen behind a broken control. The engine is
    built, measured and tested; the wiring is `DEF-PAY-6271`.

    `q`/`sort`/`dir`/`page`/`per`/`f.<name>` is BR-SHL-011's grammar and an
    invalid value CLAMPS rather than erroring. `NFR-5`: `per` is a page size
    from `PAGE_SIZES`, never a cap on the list.

    `problems` travels on the body: the DSO tile is null with its reason, the
    medical-hold column is unavailable, and any unpaid bill with no due date is
    named rather than aged on a date nobody has.
    """
    require_tenant(request)
    params = parse_list_params(
        request.query_params,
        allowed_sorts=billing_seam.OUTSTANDINGS_SORTS,
        default_sort="balance",
        default_dir="desc",
        allowed_filters=("bucket", "bad_address"),
    )
    # ⚠ **THE FILTERS COME OFF `params`, NOT OFF `query_params` AGAIN.** The
    # `allowed_filters` list above is the endpoint's declared vocabulary
    # (BR-SHL-010); reading `f.bucket` straight off the request a second time
    # would make that list DECORATION — declared, and bypassed by the only
    # code that uses it (hard-won law 2). `DEF-PAY-6246` is the same list
    # being trusted to refuse something it silently drops, one endpoint over.
    #
    # ⚠⚠ **A PAGE IS CUT ONLY WHEN THE CALLER ASKS FOR ONE, AND THAT IS THE
    # HALF OF `P4.1` THAT IS NOT DONE — SAID HERE RATHER THAN LEFT TO READ AS
    # FINISHED.** `parse_list_params` FALLS BACK rather than erroring, so it
    # answers `page=1, per=50` to a request that named neither — and paging by
    # default would hand today's screen fifty of a utility's forty thousand
    # debtors with a search box that searches the fifty. Screen 7·1 landed
    # hours before this (`P4.7`) declaring **ten sortable columns, a search
    # over account number and customer name, and four filters**; this query
    # honours **three sorts and two filters**, because the rest live on
    # customers' and on the collection-state tables that a billing-composed
    # queryset does not join. **`DEF-PAY-4221` therefore STAYS OPEN** and
    # `DEF-PAY-6271` names the join that closes it.
    #
    # **What IS done, and it is the expensive half:** the read filters, bands,
    # sorts, counts and pages IN SQL — 12 statements for a page at 40,046
    # debtors where the old one made 40,041 and took 61.539 s against a
    # 60-second worker timeout. A caller that asks for a page gets one.
    asked_for_a_page = "page" in request.query_params or "per" in request.query_params
    view = outstandings_read.outstandings(
        as_of=_as_of(request),
        bucket=params.filters.get("bucket") or None,
        bad_address_only=params.filters.get("bad_address") == "true",
        page=params.page,
        per=params.per if asked_for_a_page else None,
        sort=params.sort or "balance",
        direction=params.dir,
    )
    # DEF-099: every amount below travels with its CHAR(3) code. Rule 2 is a
    # PAIR, and a body full of bare numbers made the screen fetch a third
    # endpoint just to learn what money it was rendering.
    return Response({**view.as_dict(), "currency": settings_seam.tenant_currency()})


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive View
def payments_summary(request: Any) -> Response:
    """S32 Summary (US-PAY-005) — five panels, no stored aggregate anywhere.

    Carries `currency` for the same reason `/outstandings` does (DEF-099): a
    money figure without its code is half of CLAUDE.md rule 2.
    """
    require_tenant(request)
    body = summary_read.summary(as_of=_as_of(request)).as_dict()
    return Response({**body, "currency": settings_seam.tenant_currency()})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def autopay_intents(request: Any) -> Response:
    """The S32 chip's and S33 column's rows (US-PAY-024).

    There is no POST and no action route here, and that is BR-PAY-015 rather
    than an omission: an intent is recorded by BILL ISSUE and nothing in v1 may
    charge anybody. A retry endpoint would be a charging path with a name.
    """
    require_tenant(request)
    return Response(
        {"rows": autopay.intent_rows(account_id=request.query_params.get("f.account_id"))}
    )


@api_view(["GET", "POST"])
@permission_classes([AdminOrClerk])  # initiate is operational (BR-PAY-020)
def write_offs(request: Any) -> Response:
    """GET the approval queue · POST a request. Two people, two verbs (DEF-100).

    **GET** — `f.status=requested` is the Finance approval queue and no filter
    is the reported history (*"approved + reported in Finance"*, BR-PAY-020).
    This route did not exist, and its absence is what made the two-person split
    nominal: the only write-off id a browser could hold was the one the
    requester's own screen had just minted, so the Approve control had nowhere
    to live except beside the request. With the queue listable in Finance the
    control moves there. **BR-PAY-037 is untouched** — the same user holding the
    approver role may still initiate AND approve in v1, both acts recorded
    distinctly; what changes is the SCREEN, which is the half BR-PAY-020
    specifies and the product did not have.

    Unpaginated, deliberately, for the reason `/outstandings` is: a utility
    under 3,000 connections has a queue a person reads in one screen, and a page
    of an approval queue is a queue that lies about what is pending.

    **POST** — INITIATE a write-off (US-PAY-012), and move no money (TC-1).

        account_id   required
        amount       decimal STRING, > 0 and ≤ what the account owes
        reason       one of the four US-PAY-012 ships
        note         REQUIRED (the prototype marks it so, and so does this)
        requested_on the business date

    The response's `problems` says in as many words that nothing money-bearing
    has happened yet, so a screen cannot render this as a completed write-off.
    """
    require_tenant(request)
    if request.method == "GET":
        try:
            rows = writeoffs.write_off_queue(
                status=request.query_params.get("f.status"),
                # Finance blueprint `P2.19`. p039's criteria table marked
                # **State** SERVED and these four NOT SERVED, over a toolbar
                # the drawing puts on the screen.
                q=request.query_params.get("q"),
                reason=request.query_params.get("f.reason"),
                requested_from=_query_date(request, "from"),
                requested_to=_query_date(request, "to"),
                requested_by=request.query_params.get("f.requested_by"),
            )
        except PaymentRuleError as refusal:
            raise _as_catalog_refusal(refusal) from refusal
        return Response(
            {
                "rows": [dict(row) for row in rows],
                # ⚠ **`P2.19`'s HALF THAT IS NOT A FILTER, AND IT IS THE POINT
                # OF THE TASK.** This route's own docstring objects to paging
                # an approval queue: *"a page of an approval queue is a queue
                # that lies about what is pending."* **The objection is real
                # and the ceiling it rests on is not** — 3,000 connections
                # became 40,000 on 2026-09-06 and `NFR-3` forbids an
                # unpaginated list. The blueprint's answer (p038) is to state
                # the TRUE total beside the list: *"`Write-offs · 2` states the
                # true total on every page, so paging can no longer hide
                # anything."*
                #
                # **It ignores every filter above, deliberately.** A count that
                # moved when a clerk narrowed the list would BE the lie rather
                # than the cure, which is why it is its own indexed `COUNT(*)`
                # and never `len(rows)`. The badge in the Revenue & AR view
                # label reads this.
                "pending": writeoffs.write_off_pending_count(),
            }
        )
    payload = _payload(request)
    try:
        result = writeoffs.request_write_off(
            _actor(request),
            account_id=_required(payload, "account_id", message_key="payments.write_off.account"),
            amount=_money(payload, "amount", message_key="payments.write_off.amount"),
            reason=_required(payload, "reason", message_key="payments.write_off.reason"),
            note=_required(payload, "note", message_key="payments.write_off.note"),
            requested_on=_business_date(payload, "requested_on"),
            # OPTIONAL, and only ever used when the tenant's own threshold has
            # already waived the approver (CR-008 ruling 2). Absent is the
            # normal case and posts nothing — see `writeoffs.request_write_off`
            # for the three locks. Never defaulted to a clock (BR-TEN-043).
            posted_at=_moment(payload, "posted_at", message_key=None),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "id": result.write_off_id,
            "status": result.status,
            "account_id": result.account_id,
            "amount": f"{result.amount:.4f}",
            "posted_to_ledger": result.posted_to_ledger,
            # CR-008 ruling 2: whether THIS amount needed an approver under the
            # tenant's threshold. Served so a screen states the outcome rather
            # than re-deriving a money policy it does not own.
            "approval_required": result.approval_required,
            "journal_entry_id": (
                str(result.journal_entry_id) if result.journal_entry_id else None
            ),
            "problems": [dict(problem) for problem in result.problems],
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])  # the ROLE gate is the service's (BR-PAY-020)
def approve_write_off(request: Any, write_off_id: str) -> Response:
    """APPROVE a write-off — Finance's act, where the money moves.

    The role check is the SERVICE's `@require_role(SYSTEM_ADMIN)` and not this
    decorator's, deliberately: server-side enforcement is THE enforcement
    (BR-SHL-025), and a guard here would be a second copy of it free to drift.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = writeoffs.approve_write_off(
            actor=_actor(request),
            write_off_id=write_off_id,
            approved_on=_business_date(payload, "approved_on"),
            posted_at=_moment(payload, "posted_at", message_key="payments.write_off.posted_at"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "id": result.write_off_id,
            "status": result.status,
            "journal_entry_id": str(result.journal_entry_id) if result.journal_entry_id else None,
            "posted_to_ledger": result.posted_to_ledger,
            "plan_closed": result.plan_closed,
            "problems": [dict(problem) for problem in result.problems],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrClerk])
def collections_run(request: Any) -> Response:
    """Advance the collection ladder over an S34 selection (US-PAY-014).

    ⚠ THIS IS NOT THE NIGHTLY JOB. BR-PAY-017's ladder is evaluated on a
    schedule and BE-07 registers no collections job; every response carries
    `no_scheduled_caller` saying so. This route lets a clerk drive the same
    engine over the rows they have selected, which is the S34 bulk action.
    """
    require_tenant(request)
    payload = _payload(request)
    account_ids = tuple(payload.get("account_ids") or ())
    if not account_ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="payments.collections.no_selection"
        )
    try:
        run = ladder.run_ladder(
            account_ids=account_ids,
            as_of=_business_date(payload, "as_of"),
            actor=_actor(request),
            balance_floor=_optional_money(payload, "balance_floor"),
            partial_pause_percent=_optional_money(payload, "partial_pause_percent"),
            medical_hold_account_ids=tuple(payload.get("medical_hold_account_ids") or ()),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "as_of": run.as_of.isoformat(),
            "stepped": [
                {"account_id": d.account_id, "rung": d.rung, "detail": d.detail}
                for d in run.stepped
            ],
            "skipped": [
                {"account_id": d.account_id, "reason": d.skip_reason, "detail": d.detail}
                for d in run.skipped
            ],
            "problems": [dict(problem) for problem in run.problems],
        }
    )


def _business_date(payload: dict[str, Any], name: str) -> date:
    """A business date from the body (BR-TEN-043 — never a server clock).

    REQUIRED. See `_as_of`: this layer reads no clock at all, and a write-off
    dated by the server would be dated in the server's timezone.
    """
    raw = payload.get(name)
    if not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="payments.date_required", params={"field": name}
        )
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="payments.date_invalid", params={"field": name}
        ) from exc


def _optional_money(payload: dict[str, Any], name: str) -> Decimal | None:
    """A money/percentage figure the caller MAY state.

    None means *read the tenant setting*, which today REFUSES by name for the
    two collections values the PO ruled on 2026-08-12 and tenancy does not yet
    store. Absent is not zero and is never treated as one.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="payments.amount_invalid", params={"field": name}
        ) from exc


# ════════════════════════════════════════════════════════════════════════════
# S37 · S38 · S39 · S40 — deposits and bank reconciliation (US-PAY-020..023)
# ════════════════════════════════════════════════════════════════════════════
# Added 2026-08-16 by the payments SURFACE lane, and the reason is one sentence
# from `apps/payments/reconciliation.py`'s own docstring, written by the lane
# that built the engine: *"S37 (the batch list), S38 (the import wizard), S39
# (batch detail) and S40 (the reconcile modal) do not exist, and neither does an
# endpoint. Everything below is reachable only from a test or a shell today —
# built is not wired (hard-won law 2)."* 2,700 lines of correct, tested,
# finance-signed reconciliation, and no human could cut a deposit batch, import
# a statement, or explain a difference.
#
# EVERY ROUTE BELOW IS `AdminOrExecutive`, NOT `AdminOrClerk`, AND THAT IS
# BR-PAY-019 RATHER THAN A CHOICE: *"Bank reconciliation lives in the FINANCE
# area (S37–S40, **Owner/Finance roles**)"*, and A4's own "Finance / reconcile /
# export" row is System Admin Full · Billing Clerk — · Executive Full. A clerk
# who records payments all day does not reconcile the bank; US-PAY-021 TC-6 says
# so as a NEGATIVE test (*"a Staff-role user opens S38 → blocked server-side"*).


@api_view(["GET"])
@permission_classes([AdminOrExecutive])  # A4 finance_reconcile_export (BR-PAY-019)
def deposit_batches(request: Any) -> Response:
    """S37 / screen 3·1 — one PAGE of the TILL × tender batches, the KPI strip
    over the whole filtered set, the chip vocabularies and the named gaps.

    `f.status` and `f.method` are the capability matrix's two filters and `q` is
    `P1.7`. An unrecognised status REFUSES (422) rather than returning an empty
    list: an empty reconciliation queue and an unanswerable one look identical
    on screen, and only one of them means "nothing to do".

    ⚠ **THE PAGE IS TAKEN IN SQL SINCE 2026-09-24 (`DEF-PAY-6554` · `NFR-3` ·
    `P1.2`).** This handler used to hand DRF a built dict, so the WIRE was a
    full list and the QUERY was unbounded — `StandardPagination` is registered
    as the DRF default and an endpoint returning a plain dict never reaches it.
    `core.pagination.prepaged` builds byte-for-byte the four keys every other
    list serves, with the extras after them.

    ⚠ **`count` IS THE FILTERED SET AND SO ARE THE TILES, WHICH IS WHY THEY
    COME OUT OF THE SAME CALL.** A second `batch_list` for the tiles would be a
    second query able to disagree with the first — `batch_kpis`' own recorded
    warning. `captured` holds the one body the fetch produced.

    ⚠ **`statement_imports` STAYS ON THIS BODY.** `ReconciliationStatementPage`
    reads the statements to reconcile off the S37 list rather than adding a
    route of its own, and that was checked before the envelope moved.
    """
    from core.pagination import parse_list_params, prepaged

    require_tenant(request)
    params = request.query_params
    listing = parse_list_params(
        params,
        allowed_sorts=tuple(bankrec_read.BATCH_SORTS),
        default_sort=bankrec_read.BATCH_DEFAULT_SORT,
        default_dir="desc",
    )
    captured: dict[str, Any] = {}

    def fetch(page: Any) -> tuple[list[dict[str, Any]], int]:
        body = bankrec_read.batch_list(
            status=params.get("f.status"),
            method_code=params.get("f.method"),
            q=params.get("q") or None,
            sort=page.sort,
            direction=page.dir,
            offset=max(page.page - 1, 0) * page.per,
            limit=page.per,
        )
        captured.update(body)
        return body["rows"], body["total"]

    try:
        response = prepaged(request, listing, fetch)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    response.data["kpis"] = captured["kpis"]
    # `P1.4` — the chips, so a status added here appears on screen without a
    # front-end change (`DEF-PAY-6556`).
    response.data["statuses"] = captured["statuses"]
    response.data["methods"] = captured["methods"]
    response.data["still_open"] = captured["still_open"]
    response.data["unavailable"] = captured["unavailable"]
    # The days a clerk can still cut, and the fee account S40 pre-selects. Both
    # ride the list so the screen's two controls have real data behind them
    # instead of an optional prop nothing passes (hard-won law 2 / G13).
    response.data["cuttable_days"] = bankrec_read.cuttable_days()
    response.data["fee_account"] = bankrec_read.default_fee_account()
    response.data["statement_imports"] = bankrec_read.statement_imports()
    return response


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def deposit_batches_cut(request: Any) -> Response:
    """Cut ONE drawer day's cleared money into TILL × tender batches (US-PAY-020).

    `day` is REQUIRED and is the POSTING day — the physical drawer day, PO
    ruling RQ-5 / BR-PAY-025 — and `occurred_at` is the moment the caller names
    (BR-TEN-043). Neither is defaulted: a batch cut on the server's idea of
    "today" would bank a day the clerk did not choose.

    Idempotent by construction — membership is write-once (migration 0005) and
    the batch is keyed on (tenant, day, method) — so a double-click cuts nothing
    the second time and no total moves (hard rule 6).
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.cut_deposit_batches(
            actor=_actor(request),
            day=_business_date(payload, "day"),
            occurred_at=_required_moment(payload, "occurred_at"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "day": result.day.isoformat(),
            "payments_batched": result.payments_batched,
            "batches": [
                {
                    "id": summary.batch_id,
                    "code": summary.code,
                    "method_code": summary.method_code,
                    "deposited_on": summary.deposited_on.isoformat(),
                    "recorded_total": f"{summary.recorded_total:.6f}",
                    "currency": settings_seam.tenant_currency(),
                    "payment_count": summary.payment_count,
                    "status": summary.status,
                    "created": summary.created,
                }
                for summary in result.batches
            ],
            # Cleared money that could NOT be batched, with the reason. NEVER
            # dropped: a payment nobody banked is a real thing to look at, and
            # the engine reports each one rather than guessing a method.
            "skipped": [dict(row) for row in result.skipped],
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def deposit_batch(request: Any, batch_id: str) -> Response:
    """S39 — one batch: members, the bank side, the trail and the resolutions.

    A batch id belonging to another tenant answers 404 and not 403 (BR-TEN-003 /
    HR-1): a cross-tenant read must read as ABSENT, because a 403 confirms the
    row exists somewhere.
    """
    require_tenant(request)
    return Response(bankrec_read.batch_detail(batch_id))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def deposit_batch_match(request: Any, batch_id: str) -> Response:
    """A HUMAN names a pairing the exact rule could not make (S38 step 2 → S40).

    This is how the card day gets tied at all: the amounts differ by the
    processor's fee, so `auto_match` leaves both sides alone and a person says
    *"that credit is this deposit"*. **It is not a force-match** — nothing
    reconciles here and BR-PAY-035's superseded button still does not exist. The
    difference it returns is what S40 must then explain to zero.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        difference = reconciliation.match_bank_line(
            actor=_actor(request),
            batch_id=batch_id,
            bank_line_id=_required(
                payload, "bank_line_id", message_key="payments.bankrec.bank_line_required"
            ),
            occurred_at=_required_moment(payload, "occurred_at"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "batch_id": batch_id,
            "difference": f"{difference:.6f}",
            "currency": settings_seam.tenant_currency(),
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def deposit_batch_reconcile(request: Any, batch_id: str) -> Response:
    """S40 — explain every difference with a reason AND a GL, then reconcile.

    The tie-out this cannot skip (US-PAY-022 §7, verbatim): *"Σ reason-coded
    explanations + Σ member corrections = difference, then difference = 0 at
    reconcile."* A residual has NO path through this route, because
    BR-PAY-035 made *"Force match anyway"* permanently superseded and there is
    no flag here that would carry it.

    `resolutions[]` each carry `reason_code`, `gl_account_id` and a SIGNED
    `amount` string — the card day's processor fee is `-147.50`. The service
    checks every account is live in this tenant's own chart and refuses a
    resolution that names none.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.reconcile_batch(
            actor=_actor(request),
            batch_id=batch_id,
            posted_at=_required_moment(payload, "posted_at"),
            resolutions=_resolutions(payload),
            entry_date=_optional_business_date(payload, "entry_date"),
            note=payload.get("note") or None,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "batch_id": result.batch_id,
            "code": result.code,
            "recorded_total": f"{result.recorded_total:.6f}",
            "bank_total": f"{result.bank_total:.6f}",
            "difference": f"{result.difference:.6f}",
            "explained": f"{result.explained:.6f}",
            "currency": settings_seam.tenant_currency(),
            "journal_entry_id": str(result.journal_entry_id),
            "posting_key": result.posting_key,
            "created": result.created,
            "resolutions": [dict(row) for row in result.resolutions],
            "unavailable": [dict(gap) for gap in result.unavailable],
        }
    )


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def deposit_batch_unreconcile(request: Any, batch_id: str) -> Response:
    """BR-PAY-004's ONLY way back — confirm + REASON, audited (US-PAY-023 TC-4).

    The reason is required by the service and named here so the form can say so
    before the round trip: Unreconcile re-opens a signed-off day and the trail is
    the only record of why. Every prior trail entry survives it, forever.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.unreconcile_batch(
            actor=_actor(request),
            batch_id=batch_id,
            reason=_required(payload, "reason", message_key="payments.bankrec.reason_required"),
            posted_at=_required_moment(payload, "posted_at"),
            entry_date=_optional_business_date(payload, "entry_date"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(dict(result))


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_accounts(request: Any) -> Response:
    """S38 step 1's picker — the tenant's LIVE bank accounts (B2 r14 #1)."""
    require_tenant(request)
    return Response({"rows": bankrec_read.bank_accounts()})


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def bank_statements(request: Any) -> Response:
    """S38 steps 1–2 — persist the statement, then auto-match the unambiguous.

    The file arrives as `file_base64` because this API is JSON end to end and a
    multipart branch here would be a second request shape for one operation.
    The bytes are decoded and handed to the engine unchanged — nothing in this
    layer parses a bank file, and `lockbox.py` is the only parser.

    Idempotent on **file + tags** (BR-PAY-028 🔒): re-importing the same bytes
    for the same account and period is REFUSED naming who imported them first,
    when, and the import's id. That refusal is a 422 carrying the sentence, not
    a silent second copy of every line.
    """
    require_tenant(request)
    payload = _payload(request)
    raw = _required(payload, "file_base64", message_key="payments.bankrec.file_required")
    try:
        content = base64.b64decode(str(raw), validate=True)
    except (BinasciiError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.bankrec.file_invalid",
            field_errors=[{"field": "file_base64", "code": errors.VAL_FORMAT}],
        ) from problem
    try:
        result = reconciliation.import_bank_statement(
            actor=_actor(request),
            bank_account_id=_required(
                payload, "bank_account_id", message_key="payments.bankrec.bank_account_required"
            ),
            period_start=_business_date(payload, "period_start"),
            period_end=_business_date(payload, "period_end"),
            payload=content,
            imported_at=_required_moment(payload, "imported_at"),
            file_name=payload.get("file_name") or None,
            # CS-14 — S38 step 1's two new fields. OPTIONAL and never defaulted:
            # a balance nobody typed is served back as null, and the
            # reconciliation statement refuses to compute a tie-out from it
            # rather than reporting a difference of 0.00 it did not measure.
            opening_balance=_optional_money(payload, "opening_balance"),
            closing_balance=_optional_money(payload, "closing_balance"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "statement_import_id": result.statement_import_id,
            "line_count": result.line_count,
            "review": bankrec_read.statement_review(result.statement_import_id),
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_statement(request: Any, statement_import_id: str) -> Response:
    """S38 step 2, re-openable — every line's CURRENT state, not a replay.

    Recomputed from the persisted link rather than by re-running the matcher, so
    a pairing a human named an hour ago is still there when they come back.
    """
    require_tenant(request)
    return Response(bankrec_read.statement_review(statement_import_id))


# ════════════════════════════════════════════════════════════════════════════
# CR-059 wave W8 — the four reconciliation changes (tasks 43–46)
# ════════════════════════════════════════════════════════════════════════════
# Every route below is `AdminOrExecutive` for the same reason the eight above
# are: BR-PAY-019 puts bank reconciliation in the FINANCE area (Owner/Finance
# roles) and A4's "Finance / reconcile / export" row gives the Billing Clerk a
# dash. A clerk who records payments all day does not reconcile the bank.
#
# ⚠ **NONE OF THESE HAS A SCREEN CONTROL YET.** S38's line selection, S39's set
# panel, S40's reason picker and S37's reconciliation statement are CR-059 task
# 48. The endpoints are live and unreachable from the product — hard-won law 2,
# stated here rather than left for a reviewer to discover.


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_statement_reconciliation(request: Any, statement_import_id: str) -> Response:
    """CS-14 — the reconciliation STATEMENT for one imported bank statement.

    **IT STATES TWO FACTS AND EXPLAINS THE GAP; IT ADJUSTS NEITHER SIDE.** PO
    ruling 2026-09-02 (`OQ-1310` CLOSED), verbatim: *"we need to go on factual
    basis, if bank as report we count if bank did not report we dont count, and
    if clark wants to balance the book they can always make journal entries on
    their own - that is allowed"*. So the body carries the bank's own closing
    figure, the books' cash, and the difference between them —
    `difference_bank_less_books`, named so a screen cannot render it the wrong
    way round — with the reconciling items listed beside it, AGED, as the
    explanation. **No adjusted balance and no sign on any item**, which is what
    supersedes CS-14's stated arithmetic. Every figure is assembled from rows
    that already exist, so this can never disagree with S37 beside it.

    **Absences are served as `null` and never as `0.00`**, each with its reason
    in `unavailable[]`: a statement imported before the balances existed, or a
    chart with no designated cash account, makes the difference UNKNOWN — which
    is a different answer from "the two agree" and only one of them is good news.
    """
    require_tenant(request)
    return Response(bankrec_read.reconciliation_statement(statement_import_id))


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def bank_rec_match_set(request: Any) -> Response:
    """CS-17 — tie MANY bank lines to one batch, or one line to many batches.

    The PO's own case (2026-08-12, OQ-161): a $2,840.00 cheque batch and a
    $14,280.00 ACH batch banked the same afternoon, posted by the bank as ONE
    credit of $17,120.00. Before this route neither batch could ever reconcile.

    `bank_line_ids[]` and `batch_ids[]` are both required and the set's two
    sides must foot EXACTLY — a set that does not tie is refused with both sums
    named, because nothing rules how to apportion a difference across members.
    A double submit of the same membership answers **200** with the set that
    exists and `created:false`, never a red 409 (hard rule 6).
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.match_set(
            actor=_actor(request),
            bank_line_ids=_id_list(payload, "bank_line_ids"),
            batch_ids=_id_list(payload, "batch_ids"),
            occurred_at=_required_moment(payload, "occurred_at"),
            note=payload.get("note") or None,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "match_set_id": result.match_set_id,
            "matched_total": f"{result.matched_total:.6f}",
            "currency": result.currency,
            "bank_line_ids": list(result.bank_line_ids),
            "batch_ids": list(result.batch_ids),
            "batch_codes": list(result.batch_codes),
            "created": result.created,
            "unavailable": [dict(gap) for gap in result.unavailable],
        },
        status=201 if result.created else 200,
    )


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def bank_line_resolve(request: Any, bank_line_id: str) -> Response:
    """CS-16 — explain a bank line that is not a deposit of ours. S40, from a line.

    *"Every bank line ends the period either matched or explained, with a reason
    and a GL. Silence is not a state."* `reason_code` must be one of this
    utility's own reconciliation difference reasons once it has any (CS-18), and
    `gl_account_id` must be a live account of its own chart.

    **NOTHING IS POSTED.** Creating a journal entry from an unmatched bank line
    is batch decision G3 and the PO has not ruled on it, so the explanation is
    recorded, the books are untouched, and `unavailable[]` says so on every
    response. A second submit of the SAME explanation answers 200 with the row
    that exists; a DIFFERENT one is refused, quoting what the line already says.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.resolve_bank_line(
            actor=_actor(request),
            bank_line_id=bank_line_id,
            reason_code=str(
                _required(payload, "reason_code", message_key="payments.bankrec.reason_required")
            ),
            gl_account_id=_required(
                payload, "gl_account_id", message_key="payments.bankrec.gl_account_required"
            ),
            amount=_money(payload, "amount", message_key="payments.bankrec.amount_required"),
            occurred_at=_required_moment(payload, "occurred_at"),
            note=payload.get("note") or None,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(
        {
            "resolution_id": result.resolution_id,
            "bank_line_id": result.bank_line_id,
            "reason_code": result.reason_code,
            "gl_account_id": result.gl_account_id,
            "amount": f"{result.amount:.6f}",
            "currency": result.currency,
            "created": result.created,
            # G3 — said in the body, not only in a docstring: a screen that
            # assumed the books had caught up would be wrong on every row.
            "journal_entry_id": None,
            "posted": False,
            "unavailable": [dict(gap) for gap in result.unavailable],
        },
        status=201 if result.created else 200,
    )


# ── LBX-05 (DEF-PAY-10694) · G3 RULED 2026-10-30 — a line the bank took OUT ──
def _line_posting_body(result: Any) -> dict[str, Any]:
    return {
        "resolution_id": result.resolution_id,
        "bank_line_id": result.bank_line_id,
        "reason_code": result.reason_code,
        "gl_account_id": result.gl_account_id,
        "amount": f"{result.amount:.6f}",
        "currency": result.currency,
        "created": result.created,
        "journal_entry_id": result.journal_entry_id,
        "posted": result.posted,
        "reversal_payment_id": result.reversal_payment_id,
        "original_payment_id": result.original_payment_id,
        "reversed_now": result.reversed_now,
        "nsf_fee_status": result.nsf_fee_status,
        "nsf_fee_amount": None
        if result.nsf_fee_amount is None
        else f"{result.nsf_fee_amount:.6f}",
    }


def _with_account_numbers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = bankrec_read._accounts_by_id([row["account_id"] for row in rows])
    accounts = {str(key): value for key, value in found.items()}
    for row in rows:
        row["account_no"] = getattr(accounts.get(row["account_id"]), "account_no", None)
    return rows


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_line_return_candidates(request: Any, bank_line_id: str) -> Response:
    """The payments a RETURNED line could be — by amount, cheque number and date."""
    require_tenant(request)
    try:
        rows = reconciliation.return_candidates(bank_line_id, query=request.query_params.get("q"))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response({"rows": _with_account_numbers(rows)})


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def bank_line_match_return(request: Any, bank_line_id: str) -> Response:
    """Match a returned line to its payment — reversing it once if nobody has.

    Posts the returned amount holding → cash (PO 2026-10-30, G3 = A). A second
    submit of the same pair answers 200 with the row that exists.
    """
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.match_returned_line(
            actor=_actor(request),
            bank_line_id=bank_line_id,
            payment_id=_required(
                payload, "payment_id", message_key="payments.bankrec.payment_required"
            ),
            occurred_at=_required_moment(payload, "occurred_at"),
            nsf_fee_waived=bool(payload.get("nsf_fee_waived")),
            nsf_fee_waive_reason=payload.get("nsf_fee_waive_reason") or None,
            # P1 a2-2 (PO 2026-10-31) — the clerk's edited Bank memo; a body
            # without the key keeps the line's own words.
            bank_memo=payload.get("bank_memo")
            if "bank_memo" in payload
            else reconciliation.LINE_TEXT,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_line_posting_body(result), status=201 if result.created else 200)


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_line_fee_candidates(request: Any, bank_line_id: str) -> Response:
    """Bank fees already posted on a Reverse that this fee line could be."""
    require_tenant(request)
    try:
        rows = reconciliation.bank_fee_candidates(bank_line_id)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response({"rows": rows})


@api_view(["POST"])
@permission_classes([AdminOrExecutive])
def bank_line_bank_fee(request: Any, bank_line_id: str) -> Response:
    """Explain a fee line → Bank fees (6800) against cash; or link a Reverse's fee."""
    require_tenant(request)
    payload = _payload(request)
    try:
        result = reconciliation.explain_bank_fee_line(
            actor=_actor(request),
            bank_line_id=bank_line_id,
            occurred_at=_required_moment(payload, "occurred_at"),
            payment_id=payload.get("payment_id") or None,
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(_line_posting_body(result), status=201 if result.created else 200)


@api_view(["GET"])
@permission_classes([AdminOrExecutive])
def bank_rec_differences(request: Any) -> Response:
    """CS-18 — differences grouped by reason AND GL account, over a period.

    *How much was processor fees this quarter, how much was error.* `from` and
    `to` are required business dates: a report whose period defaulted to
    "everything" would answer a question nobody asked and would keep answering
    it as the register grows.

    Each row is counted under the MONEY's own date — a batch explanation under
    its banking day, a line explanation under the bank's posted day — never
    under the day somebody typed it.
    """
    require_tenant(request)
    query = {"from": request.query_params.get("from"), "to": request.query_params.get("to")}
    body = bankrec_read.difference_report(
        start=_business_date(query, "from"), end=_business_date(query, "to")
    )
    # The picker's own vocabulary rides with the report so S40 and the S8 card
    # offer exactly what this report groups by (hard-won law 2 / G13: an
    # optional prop nothing passes is a control that does not exist).
    body["reasons"] = bankrec_read.difference_reasons()
    return Response(body)


# ════════════════════════════════════════════════════════════════════════════
# The collections POSITION — who is at which tier, and why (US-PAY-015/018/019)
# ════════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive View
def collections_ladder(request: Any) -> Response:
    """The ladder board — a PREVIEW that steps nothing (US-PAY-014/015).

    `POST /collections/run` already existed and it SENDS: it writes the notice,
    advances the tier and records a skip row on every path. There was no way to
    look first, so a clerk drove a five-stop-condition engine over a selection
    they could not inspect. This is the look.

    `as_of` is the caller's business day (BR-TEN-043 — this layer reads no
    clock). `balance_floor` and `partial_pause_percent` may be stated; when they
    are not, the board answers `next_step_available: false` with the reason
    rather than inventing either figure (OQ-136 · OQ-137 · OQ-157).
    """
    require_tenant(request)
    try:
        body = collections_read.ladder_board(
            as_of=_as_of(request),
            balance_floor=_optional_money_param(request, "balance_floor"),
            partial_pause_percent=_optional_money_param(request, "partial_pause_percent"),
        )
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(body)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record: Executive is VIEW
def account_open_bills(request: Any, account_id: str) -> Response:
    """WHAT EACH OF THIS ACCOUNT'S BILLS STILL OWES — CR-059 CS-4, closing OQ-154.

    The list the S22/S35 Record modal aims money at when a clerk picks *"A
    specific bill"* or *"Split across bills"*, and the figures S21's Bills tab
    shows beside the issued total.

    **THE POINT IS THAT IT IS THE OPEN BALANCE AND NOT THE ISSUED TOTAL.** Both
    controls have been CONFIRMED law and executed by the allocator since
    2026-08-11 and have rendered DISABLED on both screens, because
    `GET /invoices?f.account_id=` serves what a bill was ISSUED for and that is a
    different number the moment anything has been paid: `BL-2608-018410` was
    issued at **247.87**, a 200.00 payment left **47.87** open, and a picker
    built on the bill list would have offered the clerk 247.87 to aim at.

    Each row carries the bill's number, its issue date, its total, what has been
    allocated to it, what it still owes and its CHAR(3) currency; the position
    carries the account's own currency, the number of open bills and their sum —
    P1's *"owes 341.10 across 2 bills"* header, summed over exactly the rows
    below it. A settled bill is ABSENT rather than listed at 0.00.

    Read-only, by every rule in the module: no clock, no money arithmetic, no
    write. It reshapes `billing_seam.open_invoices_for_account`, which already
    did the subtraction, and **the allocator is untouched**.

    A cross-tenant or unknown account id refuses by the same sentence and the
    same rule id `POST /accounts/{id}/payments` refuses by — the picker and the
    record call must agree on what an account is.
    """
    require_tenant(request)
    try:
        body = open_bills.open_bill_position(account_id=account_id)
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(body)


@api_view(["GET"])
@permission_classes([AnyTenantRole])  # A4 payments_record — the role that RECORDS one
def payment_reason_codes(request: Any) -> Response:
    """`GET /payments/reason-codes` — this utility's own credit/adjustment reasons.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE LIST A LIVE CONTROL HAS NEEDED SINCE 2026-09-02 AND NEVER HAD.  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **DEF-PAY-5128.** CR-059 CS-35 taught `record_payment` the type AND the
    reason and built the type select; nothing ever published the reasons. So
    S33's select has offered *Credit* and *Adjustment* since 2026-09-02 and
    `services._reason_code` refuses either with no reason BY NAME — two options
    of a live control that could only fail, and every test of that form drives
    the default `payment`, for which a reason is REFUSED. It is also what
    `DEF-CUS-5126`'s `Adjust` control on the account needs.

    **WHY IT IS NOT `GET /lookups/reason_codes`.** That route is gated on
    `SettingsReadAnyWriteSystemAdmin` and A4 gives the Billing Clerk **no
    `settings_lookups` cell** — so the one role A4 lets *Request* an adjustment
    cannot read the reasons through Settings. Same rows, clerk-facing surface.

    **UNPAGINATED, AND THAT IS NOT `NFR-3` BEING BROKEN.** This is a tenant's
    own reference list — five seeded rows, tenant-extensible — and it is a
    `<select>`'s whole contents, not a record list: a picker that pages cannot
    be used. The rule NFR-3 exists for is a list that grows with ACCOUNTS, and
    this one does not; `GET /lookups/payment_methods`'s stand-in on the same
    form takes the same shape for the same reason.

    Read-only. No clock, no money, no write.
    """
    require_tenant(request)
    try:
        rows = ledger_seam.active_reason_codes()
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response({"reasons": rows, "count": len(rows)})


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def account_collections(request: Any, account_id: str) -> Response:
    """ONE account's dunning position — the pause, the plan, the tier, the trail.

    The S21 header's answer to *"why is this customer being chased, or not?"*,
    and the record a utility shows a regulator when a customer says they were
    never told. Sends AND skips: an account excluded for a medical hold and one
    nobody ever chased must never read the same.
    """
    require_tenant(request)
    try:
        body = collections_read.account_position(account_id=account_id, as_of=_as_of(request))
    except PaymentRuleError as refusal:
        raise _as_catalog_refusal(refusal) from refusal
    return Response(body)


# ── Body helpers the bank-rec routes need (BR-TEN-043 · rule 2) ─────────────


def _required_moment(payload: dict[str, Any], name: str) -> datetime:
    """A moment the CALLER names — BR-TEN-043, gate G6, and never a clock.

    Required, not optional: a resumed batch run, a replay and a re-run must
    stamp the SAME instant rather than three, which is impossible if the server
    reads its own clock. `_moment` already parses both shapes; this only refuses
    the absence, because `reconciliation` raises `PaymentRuleError` for a
    non-datetime and a 422 naming the field is the better answer to a form.
    """
    moment = _moment(payload, name, message_key="payments.bankrec.moment_required")
    if moment is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.bankrec.moment_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return moment


def _optional_business_date(payload: dict[str, Any], name: str) -> date | None:
    """A business date the caller MAY state. Absent is ABSENT, never today.

    `entry_date` defaults inside the service to the BANK's own posting day —
    which is the day the bank confirmed the money, and the PO's ruling makes
    confirmation the event that realises it. Defaulting here would take that
    decision away from the rule that owns it.
    """
    raw = payload.get(name)
    if raw in (None, ""):
        return None
    return _business_date(payload, name)


def _optional_money_param(request: Any, name: str) -> Decimal | None:
    """A query-string money/percentage figure, or None. Absent is never zero.

    None means *read the tenant setting*, which today REFUSES by name for the
    two collections values the PO ruled on 2026-08-12 and tenancy does not yet
    store — and the board reports that refusal instead of running the ladder
    against a floor of zero, which would chase a customer over forty cents.
    """
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="payments.amount_invalid", params={"field": name}
        ) from exc


def _id_list(payload: dict[str, Any], name: str) -> list[str]:
    """A required, non-empty JSON array of ids (CS-17's two sides).

    A missing or non-list value is a 422 naming the field rather than an empty
    match set: a body that meant to tie three lines and sent a string would
    otherwise be answered with "a match set needs at least one bank line", which
    is true and unhelpful.

    ⚠ **THE MESSAGE KEY IS BORROWED AND THAT IS REPORTED, NOT HIDDEN.** The
    right key is `payments.bankrec.match_set_members_required` and it does not
    exist in any catalogue; G32 is a RATCHET, so raising a key that resolves to
    nothing would make a refusal SILENT on screen — worse than the defect it
    would be fixing (DEF-322's ruling). Writing the sentence means editing the
    eleven locale catalogues, which is CR-059 task 48's territory. So this
    borrows `payments.bankrec.bank_line_required` — *"Choose the bank line to
    pair with this deposit"* — which is right for `bank_line_ids` and only
    approximate for `batch_ids`. `field_errors` still names the exact field, so
    the form highlights the right input either way. Task 48 mints the key.
    """
    raw = payload.get(name)
    if not isinstance(raw, list) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="payments.bankrec.bank_line_required",
            params={"field": name},
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    return [str(one) for one in raw]


def _resolutions(payload: dict[str, Any]) -> tuple[reconciliation.ResolutionInput, ...]:
    """S40's explanations, as the engine's own carrier — BR-PAY-019's reason + GL.

    Each entry needs a `reason_code`, a `gl_account_id` and a SIGNED decimal
    STRING `amount` (the card day's processor fee is `-147.50`). Nothing here
    derives, nets or balances: the service checks the sum against the difference
    and refuses anything that leaves a residual, which is the one control
    BR-PAY-035 made unskippable.
    """
    raw = payload.get("resolutions") or []
    if not isinstance(raw, list):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="payments.bankrec.resolutions_invalid",
            field_errors=[{"field": "resolutions", "code": errors.VAL_FORMAT}],
        )
    built: list[reconciliation.ResolutionInput] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.bankrec.resolutions_invalid",
                field_errors=[{"field": "resolutions", "code": errors.VAL_FORMAT}],
            )
        built.append(
            reconciliation.ResolutionInput(
                reason_code=str(
                    _required(
                        entry, "reason_code", message_key="payments.bankrec.reason_code_required"
                    )
                ),
                gl_account_id=_required(
                    entry, "gl_account_id", message_key="payments.bankrec.gl_account_required"
                ),
                amount=_money(entry, "amount", message_key="payments.bankrec.amount_required"),
                note=entry.get("note") or None,
            )
        )
    return tuple(built)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def counter_receipts_list(request: Any) -> Response:
    """`GET /counter-receipts` — **money taken at a counter, in payments.**

    CR-094-BRC01 lane H, the PO ruling of 2026-09-15: *"payemnt should show in
    payments, in ledge and in fiannce books"*. The ledger half is automatic —
    the collection posts a balanced pair, so the money is on the journal, the
    trial balance and the GL detail for its two accounts the minute it is
    taken. **This is the payments half**, and it exists because a row nobody can
    open does not satisfy that ruling.

    Why these rows are not on `GET /payments`: a `Payment` in this product is a
    payment BY AN ACCOUNT, and the whole reason this table exists is that there
    is no account yet. Mixing the two into one paginated queryset would give
    `totals` two kinds of money to add up and every column an *if*.

    Pagination is mandatory on every list (`NFR-3`) and the page is taken in the
    DATABASE, ordered by the moment the money was taken.

    `f.state` filters to `held`, `applied` or `earned`. `held` is the one a
    finance clerk actually opens: it is everything `2400 Customer credit
    balances` is carrying for applications nobody has decided yet.

    Two members ride alongside the DRF envelope, exactly as `GET /payments`
    carries its roll-up:

      `totals`          `taken` and `held` for the CURRENT filter, four-decimal
                        strings with the tenant's `CHAR(3)` beside them. `held`
                        is what is still a liability — the sum of every row's
                        `amount − earned_amount` — which is the figure that
                        should agree with 2400 and is the point of the screen.
                        `by_method` splits the same figures by tender.
      `states`          the three, so a filter control needs no hardcoded list.

    ⚠ **`f.taken_on` IS HOW A CLERK BALANCES A TILL, AND WITHOUT IT THEY CANNOT.**
    `YYYY-MM-DD`, optional, and ABSENT MEANS ABSENT rather than today — this
    layer reads no clock (`BR-TEN-043`), so a day is always one the caller
    named. **The counter money is never in a deposit batch**: `BR-PAY-025`
    groups a batch by day and method and writes membership onto a `payments`
    row, and a counter receipt is deliberately not one, because there is no
    account yet. A clerk reconciling against batches alone therefore finds the
    counter cash missing every single day, and this is the figure that answers
    it — `f.taken_on=2026-05-12` with `totals.by_method`'s cash line is what
    gets counted against the notes and coin in the drawer.

    ⚠ **AND NOTHING MOUNTS THIS ENDPOINT — `DEF-PAY-5875`, filed rather than
    left in this trailer.** A `grep` of `07-frontend/src/` for it returns
    nothing: the screen was deferred when lane H shipped on 2026-09-15 and is
    deferred still, so **a clerk cannot balance a till from the product today**
    even though the figure above is correct. That is hard-won law 2's mirror —
    a live endpoint behind no control — and it is a register row now because a
    deferral written only into a docstring is one nobody can count.
    """
    require_tenant(request)
    queryset = counter_receipts.list_queryset(
        state=request.query_params.get("f.state"),
        taken_on=_optional_business_date(
            {"taken_on": request.query_params.get("f.taken_on")}, "taken_on"
        ),
    )
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    response = paginator.get_paginated_response(
        [counter_receipts.receipt_dict(row) for row in (page or [])]
    )
    response.data["totals"] = counter_receipts.list_totals(queryset)
    response.data["states"] = list(counter_receipt_models.RECEIPT_STATES)
    return response


urlpatterns = [
    path("payments", payments),
    path("payments/summary", payments_summary),
    # CR-094-BRC01 lane H — the counter takings a clerk can open. An all-literal
    # path like its neighbours above, for the same reason they are.
    path("counter-receipts", counter_receipts_list),
    # CR-059 CS-43. A THIRD all-literal `payments/…` path beside `summary`;
    # neither can shadow the other and no `payments/<id>` two-segment pattern
    # may ever be added above them, or the words "summary" and
    # "selection-total" would resolve as payment ids.
    path("payments/selection-total", payments_selection_total),
    path("outstandings", outstandings),
    path("autopay-intents", autopay_intents),
    path("write-offs", write_offs),
    path("write-offs/<str:write_off_id>/approve", approve_write_off),
    path("collections/run", collections_run),
    # The ladder POSITION. Declared after `collections/run` and before nothing
    # that could shadow it — both are literal two-segment paths, so neither can
    # swallow the other, and no `collections/<id>` pattern may be added above
    # them without moving these two first.
    path("collections/ladder", collections_ladder),
    path("accounts/<str:account_id>/payments", account_payments),
    path("accounts/<str:account_id>/collections", account_collections),
    # CR-059 CS-4 / OQ-154. A third literal last segment beside `payments` and
    # `collections` — none of the three can shadow another, and no
    # `accounts/<id>/<something>` catch-all may be added above them.
    path("accounts/<str:account_id>/open-bills", account_open_bills),
    # ⚠ ABOVE `payments/<str:payment_id>` if one is ever added, or the literal
    # would be read as a payment id (the DEF-520 route-ordering shape).
    path("payments/reason-codes", payment_reason_codes),
    # S37–S40. `deposit-batches/cut` is an all-literal path and MUST stay above
    # `deposit-batches/<batch_id>`, or the word "cut" resolves as a batch id and
    # a clerk cutting the day's takings gets a 404 on a batch that never existed.
    path("deposit-batches", deposit_batches),
    path("deposit-batches/cut", deposit_batches_cut),
    path("deposit-batches/<str:batch_id>", deposit_batch),
    path("deposit-batches/<str:batch_id>/match", deposit_batch_match),
    path("deposit-batches/<str:batch_id>/reconcile", deposit_batch_reconcile),
    path("deposit-batches/<str:batch_id>/unreconcile", deposit_batch_unreconcile),
    path("bank-accounts", bank_accounts),
    path("bank-statements", bank_statements),
    # ── CR-059 W8 ─────────────────────────────────────────────────────────
    # `bank-rec/...` is a THIRD literal first segment beside `bank-accounts`
    # and `bank-statements`; none of the three can shadow another. The two
    # `bank-statements/<id>` patterns are declared LAST and the `/reconciliation`
    # one comes FIRST of the pair, because a two-segment `<id>` pattern would
    # otherwise swallow `<id>/reconciliation` — the same trap the comment above
    # `deposit-batches/cut` names.
    path("bank-rec/match-set", bank_rec_match_set),
    path("bank-rec/differences", bank_rec_differences),
    path("bank-lines/<str:bank_line_id>/resolve", bank_line_resolve),
    path("bank-lines/<str:bank_line_id>/return-candidates", bank_line_return_candidates),
    path("bank-lines/<str:bank_line_id>/match-return", bank_line_match_return),
    path("bank-lines/<str:bank_line_id>/fee-candidates", bank_line_fee_candidates),
    path("bank-lines/<str:bank_line_id>/bank-fee", bank_line_bank_fee),
    path("bank-statements/<str:statement_import_id>/reconciliation", bank_statement_reconciliation),
    path("bank-statements/<str:statement_import_id>", bank_statement),
    # ── CR-059 W6/W7/W10 (2026-09-03) ─────────────────────────────────────
    # Four modules of their own, INCLUDED here rather than from
    # `config/urls.py` where `refunds_api`, `reversal_api` and `amendments_api`
    # are. Two reasons, and the second is the load-bearing one:
    #
    #   1. `config/urls.py` already includes THIS module at `path("")`, so an
    #      include from here reaches the identical resolver at the identical
    #      prefix. Nothing about the served URLs differs.
    #   2. **`config/urls.py` is a shared file with several lanes live in it**,
    #      and hard-won law 11's fourth and fifth occurrences are both a
    #      pathspec commit taking the whole working-tree content of a file two
    #      lanes had edited. An include from a file this lane owns outright
    #      costs one line and takes nobody's work.
    #
    # Every pattern each module declares is checked for shadowing in that
    # module's own docstring: `transfers` / `transfer-preview` /
    # `credit-sources` are further literal last segments beside `payments`,
    # `collections`, `open-bills` and `refunds`; `payments/<id>/move`,
    # `move-preview`, `reapply` and `reapply-plan` are three-segment patterns
    # and THIS module declares only literal `payments/…` paths; `cheques` is a
    # new literal first segment and `payments/<id>/cheque/void` is the only
    # four-segment `payments/<id>/…` pattern anywhere in the module.
    path("", include("apps.payments.transfer_api")),  # CS-8 · CS-32
    path("", include("apps.payments.reapply_api")),  # CS-11
    path("", include("apps.payments.bulk_acts_api")),  # Q4 bulk bar (DEF-PAY-10747)
    path("", include("apps.payments.cheques_api")),  # CS-30
    # CR-136-BRC07 phase 2 — the six Counter screens' five doors (`P2.1`–`P2.3`).
    path("", include("apps.payments.counters_api")),
    # CS-2's six `payment-imports` doors are GONE (`DEF-PAY-10697`, lockbox
    # audit LBX-08(c), 2026-10-30) — `OQ-PAY-12579` cleared the retiring
    # pipeline for deletion on 2026-09-23 (*"(a) No such file exists — delete
    # the old importer as planned"*). No screen called them; the one importer's
    # payments target (`import_writer.py`) is the only way in. The staging
    # tables and their reads stay for the rows already in them.
    # CR-139-BRC07 phase 5 — the two Settlements screens' three READ doors
    # (`P5.7`). `settlements` is a new literal first segment, so it can collide
    # with nothing already declared here; it sits above the `detail_api` line
    # below for the one reason that line records about itself.
    path("", include("apps.payments.settlements_api")),
    # ── CR-137-BRC07 P3.1–P3.4 + P3.19 (2026-09-23) ───────────────────────
    # A payment's own address, its history, Cancel, Resend and the counter's
    # printable receipt.
    #
    # ⚠⚠ **THIS LINE MUST STAY LAST, AND IT IS THE ONLY INCLUDE IN THIS FILE
    # THAT HAS TO BE.** `detail_api` declares `payments/<str:payment_id>`, a
    # TWO-segment pattern, and it is the widest pattern in the module: moved
    # above the three literal two-segment routes declared earlier in this list
    # — `payments/summary`, `payments/reason-codes`, `payments/selection-total`
    # — the word "summary" resolves as a PAYMENT NUMBER and a clerk opening the
    # S33 summary gets a 404 on a payment that never existed. It is the
    # identical trap the comment above `deposit-batches/cut` records, one noun
    # along, and it is asserted by test rather than left to this comment
    # (hard-won law 1: a comment claiming an ordering is not the ordering).
    path("", include("apps.payments.detail_api")),  # P3.1 · P3.2 · P3.3 · P3.4 · P3.19
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@0f1a7c3 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md — US-PAY-001 + US-PAY-004 — · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.9 · 04-docs/01-spec/11-api-contracts.md Addendum r2; co-packet US-PAY-004, same four sources)
# generated: 2026-08-11 by story-coder (W4 payments API lane — the endpoints the payments write path landed without) · AMENDED 2026-09-01 by the CR-059 task 11 lane (CS-4 — `GET /accounts/{id}/open-bills`, the open-balance read OQ-154 ordered built; a READ over the existing seam, no money logic moved and the allocator untouched)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests/test_us_pay_004_payments_api.py (RED-PROVED FIRST: AttributeError on every view name and django.urls.exceptions.Resolver404 on /api/brazosbend/payments, plus `assert 404 == 401` from the live HTTP probe — verbatim in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔ · openapi/schema.json REGENERATED (BE-11 TC05 diffs it, so an endpoint added without it goes red)
# exceptions: (1) `idempotency_key` is REQUIRED on the record body and a missing one is a 422 VAL-001 naming the field (B12 §3 maps the whole VAL class to 422) — generating one here would dedupe nothing while looking as if it had (hard rule 6) · (2) a REPLAY answers 200 + `created:false`, not 11b G7's 409: a staff double-click is not one of G7's four enumerated operations, and BR-PAY-028's own field-map row reads "duplicate submit → single row" · (3) a calendar-date `posted_at`/`cleared_at` is stamped at midnight UTC — WHICH instant a user-entered date becomes, in whose timezone, is OQ-153, RAISED not answered; the DATE is preserved either way and that is what BR-PAY-021's on-time test reads · (4) the tenant's method vocabulary is served on the LIST response because `GET /lookups/payment_methods` 404s (payments registers no lookup handler — REPORTED, it is US-TEN-010/011's card and BR-TEN-031's content owner is this module) · (5) NO detail route is minted: neither A11 nor 11b §2.9 contracts `GET /payments/{id}`, and what a detail would add rides on the list row as `applied_to` · (6) NSF, reverse, reapply, refund, write-off, receipts, collections notices and the staged import are NOT served and NOT stubbed — every one is either another epic's or blocked on an unanswered PO decision in 12-governance/12-payments-decision-batch.md
#         · (7) [2026-09-01, CR-059 CS-4] `GET /accounts/{id}/open-bills` is SERVED and its SCREEN is NOT built here — CR-059 task 12 owns S22/S35's picker, the running remainder and the deletion of the on-screen refusal text (`payments.applyTo.pickerUnavailable`, rendered on BOTH PaymentsPage and AccountActions through `paymentsShared.allocationChoiceReason`). Until that lands the endpoint is live and the two controls still render disabled: hard-won law 2 with the halves in two lanes by design, REPORTED so the second half is not lost · (8) [2026-09-01, AMENDED THE SAME DAY] DEF-2416 is FIXED. This entry read "every balance the new route serves is measured at `invoice.total` … FILED, not fixed" — `apps/payments/billing_seam.py` now asks billing's own `selectors.amount_due_for` per bill (BR-BIL-072, the PO's *"Level is due"* of 2026-08-11), so a BUDGET BILLING bill is measured at its LEVEL: WE-8 charges 292.87 and asks 242.00, and a customer who pays the 242.00 owes nothing instead of being chased for the 50.87 variance. Each row of this route now carries `amount_due` beside `total`, `allocated` and `open_balance`; the key is ADDITIVE and this route serves a plain body, so `openapi/schema.json` describes no response properties and is unchanged. The DOCSTRING above is deliberately untouched for the same reason entry (9) exists: the schema embeds it verbatim, so editing it would re-open TC-05 · (9) [2026-09-01] `openapi/schema.json` REGENERATED, and it carries MORE than this route — say so plainly: `tests/test_be11_openapi.py` TC-05 was ALREADY RED at the pinned tip, because two `/customers` routes and two description changes (`accounts/imports/template`, `transfers/commit`) were committed without it. The snapshot was rebuilt in a clean worktree at the tip with ONLY this lane's three payments files copied in, so every entry in it derives from COMMITTED code and no lane's in-flight work is published (law 11 / DEF-168). TC-05 was red before and is green after
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
