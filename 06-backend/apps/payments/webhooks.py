# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 · C21 — "Gateway payment webhooks". `CR-060 §0d.1` labels it
#           *"new — was an undecided absence"*. What done looks like: *"a card
#           payment from the portal appears on Record payments with no clerk
#           keying it, marked cleared and allocated; the provider re-sending the
#           same callback produces ONE payment, not two."*
# Story:    US-PAY-001 (the recording path this feeds)   Screens: S33
# Rules:    BR-PAY-003 (inbound payment webhooks dedupe on `webhook_key`
#           UNIQUE) · BR-PAY-028 (idempotency; key mechanics Eng-Lead 🔒) ·
#           BR-PAY-021 (both dates, and the gateway names them) · BR-PAY-036 (a
#           payment is ALWAYS accepted) · BR-TEN-043 / gate G6 (nothing here
#           reads a clock) · CLAUDE.md hard rule 1 · rule 2 · rule 6 · rule 7 ·
#           hard-won law 14 (a SAVEPOINT, proved on PostgreSQL)
# Tests:    06-backend/tests/test_cr060_c21_webhooks.py
# Impacts:  apps/payments/models.PaymentWebhookEvent (payments/0020) ·
#           apps/payments/services.record_payment (the ONE inbound write path,
#           unchanged) · apps/payments/idempotency.inbound_payment_key
# ───────────────────────────────────────────────────────
"""Inbound gateway webhooks — money a customer paid without a clerk touching it.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — **CLAUDE.md's 🔒 list names webhook keys by
name**, and an unauthenticated endpoint that creates payments is the most
dangerous thing in this module. AI-authored 2026-09-03 under the PO ruling of
2026-08-09; a row in `12-governance/09-human-review-ledger.md` is OWED and this
lane's write scope does not include that file, so its content is written into
`12-governance/02-decision-log.md` verbatim to be transcribed. REPORTED.

⚠ **THIS FILE WAS ONE DOCSTRING LINE UNTIL TODAY** — *"Inbound gateway webhooks.
Idempotent via payments.webhook_key (B2). Key scheme HUMAN-OWNED."* — and
`CR-060`'s own analysis says so by name. That line was TRUE and it was a plan,
not a guarantee (hard-won law 1). This is the build.

════════════════════════════════════════════════════════════════════════════
⚠ DESIGN FOR THE RETRY FIRST. THE HAPPY PATH IS THE EASY HALF
════════════════════════════════════════════════════════════════════════════
**Payment gateways retry.** They re-send on a timeout, on a 500, on their own
schedule, and sometimes days later. C21's acceptance line puts the retry in the
same sentence as the feature for that reason: *"the provider re-sending the same
callback produces ONE payment, not two."*

**A duplicate webhook that creates a second payment is money the customer did
not pay, sitting on their account** — and it is worse than it sounds, because
the allocation engine will spend it on their next bill and nobody will look at
it again.

TWO INDEPENDENT GUARDS, CATCHING TWO DIFFERENT FACTS (DEF-058's lesson):

  1. **`uq_payment_webhook_events_event`** — *has this DELIVERY been seen?*
     `(tenant, provider, event_id)`. A redelivery is recognised BEFORE any money
     path runs, answers with the payment the first delivery produced, and writes
     nothing.
  2. **`uq_payments_webhook_key`** — *has this PAYMENT been recorded?*
     `record_payment` composes `webhook|<provider>:<event_id>` through
     `idempotency.inbound_payment_key` and its own unique index catches a race
     that slipped past guard 1.

**They are not defence in depth and each is asserted on its own**, because
DEF-058 is what happens when one guard silently stands in for another: guard 1
is switched off in a test and guard 2 must still hold the line, and the reverse.

════════════════════════════════════════════════════════════════════════════
⚠ SIGNATURE VERIFICATION IS NOT OPTIONAL AND FAILS CLOSED (hard-won law 3)
════════════════════════════════════════════════════════════════════════════
**A deployment with no configured secret REFUSES every delivery.** It does not
accept them unsigned, it does not warn and proceed. `PAYMENT_WEBHOOK_SECRETS` is
empty by default and an empty secret means *"this utility takes no gateway
callbacks"*, which is the true statement about a product whose card rails are v2.

The comparison is `hmac.compare_digest` over the RAW BODY BYTES — never over a
re-serialised dict, because two JSON encoders disagree about spacing and key
order and a signature computed over the wrong bytes fails for a reason nobody
can debug.

**A refused delivery is still RECORDED**, with `signature_verified=False` and
its reason. A provider misconfiguration and an attack look identical in an empty
log, and the first is far more common at three in the morning.

════════════════════════════════════════════════════════════════════════════
⚠ IT NEVER INITIATES A CHARGE — CS-1 AND CS-9 ARE v2 AND THIS IS NOT
════════════════════════════════════════════════════════════════════════════
C21 is the **INBOUND** half: recording what a gateway says already happened.
Taking money from a card (`CR-059` CS-1) and drafting it on autopay (CS-9) were
ruled out of this release. **Nothing in this file calls a gateway, holds a card
token, or writes an `autopay_capture_intents` status that could express a
charge** — CS-9's own warning is that *"a status that can express a charge is one
some path eventually gets written against"*, and the same applies to a function.

⚠ **AMENDED 2026-09-05 (`US-CWP-006` / `US-CWP-045`, CR-068 phase 5), AND THE
SENTENCE ABOVE IS STILL TRUE OF THIS FILE.** A charge path now exists in the
product and it is `apps/payments/gateway.py` — the ONE place that asks a
provider for a debit, and which provider that is belongs to the tenant's
integration connection (PO ruling 2026-09-05: providers are integrations).
**Nothing in THIS file calls it, and the direction of the dependency is the
guarantee:** `gateway` calls `settle_charge` below after an approval, and
`webhooks` has never heard of `gateway`. So an approved charge and an inbound
settlement are recorded by the same three steps, allocated by the same rule and
deduped on the same key — while a decline and a timeout reach nothing here at
all, which is `US-CWP-045` TC-6's *"assert zero rows"*.

════════════════════════════════════════════════════════════════════════════
⚠ CLAUDE.md HARD-WON LAW 14 — THE SAVEPOINT, AND WHY IT IS NOT OPTIONAL
════════════════════════════════════════════════════════════════════════════
`ingest` records the delivery row and THEN tries to record a payment, and a
refused payment must not lose the delivery row: *"the money is real at the
gateway; somebody has to see it."*

**On PostgreSQL a `try: … except: continue` DOES NOT WORK.** Once any statement
errors inside a transaction the transaction is aborted, every later query raises
`InFailedSqlTransaction`, and the work is lost at COMMIT anyway — so the
delivery row would be lost precisely on the deliveries that most needed
recording. **A SAVEPOINT — a nested `transaction.atomic()` — is not the tidy
option, it is the ONLY option.** It is marked in the code below so nobody
"simplifies" it away.

**AND THE SUITE CANNOT SHOW YOU THIS.** `config/settings/test.py` hardcodes
in-memory SQLite, which has no aborted-transaction state, so the broken version
passes every test on every machine.
`tests/test_cr060_c21_webhooks.py` marks the transaction-sensitive cases
`requires_postgres` and they were run on PostgreSQL 16.13.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

from apps.payments import idempotency, models
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: EP-PAY-01 §5's `<entity>.<verb>` shape. Its own code, so a screen filtering
#: the trail for *"money that arrived without a clerk"* finds it without reading
#: a payload.
AUDIT_RECEIVED = "payment.webhook_received"

#: The `type` an in-process settlement carries, so a person reading
#: `payment_webhook_event` can tell a charge WE started from a callback THEY
#: sent. `US-CWP-045`.
CHARGE_SETTLED = "charge.settled"

#: The refusal reasons, as CODES a screen groups on rather than prose it parses
#: — the discipline every `problems[]` row in this module keeps.
REFUSED_NO_SECRET = "no_signing_secret_configured"
REFUSED_BAD_SIGNATURE = "signature_did_not_verify"
REFUSED_UNKNOWN_ACCOUNT = "account_not_found"
REFUSED_BAD_AMOUNT = "amount_not_readable"
REFUSED_BAD_DATE = "dates_not_readable"
REFUSED_RULE = "refused_by_a_payment_rule"

#: What this path does NOT do, on every result.
WEBHOOK_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_charge_is_ever_initiated_here",
        "br_ref": "BR-PAY-015",
        "detail": "this is the INBOUND half — recording what a gateway says already happened. "
        "Taking money from a card is CR-059 CS-1 and drafting it on autopay is CS-9; both were "
        "ruled out of this release, and nothing on this path calls a gateway or holds a card.",
    },
)


@dataclass(frozen=True)
class IngestedWebhook:
    """What one delivery did — and, on `problems`, what it could not do."""

    event_row_id: str
    provider: str
    event_id: str
    status: str
    signature_verified: bool
    created: bool = True
    payment_id: str | None = None
    payment_no: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    outcome: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=WEBHOOK_UNAVAILABLE)


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def signing_secret(provider: str) -> str | None:
    """This deployment's shared secret for one provider, or None.

    ⚠ **NONE IS THE DEFAULT AND NONE MEANS REFUSE (hard-won law 3 — the unsafe
    option must be the one you type).** `settings.PAYMENT_WEBHOOK_SECRETS` is an
    empty mapping unless a deployment sets it, and an empty secret is the true
    statement about a product whose card rails are v2: this utility takes no
    gateway callbacks. A default that accepted unsigned deliveries would be an
    unauthenticated endpoint that creates payments.

    ⚠ **AND EDITING `.env.example` FIXES NOTHING ALREADY DEPLOYED** (hard-won
    law 4). A host that already has an `.env` keeps whatever it has; the secret
    has to be set on that host.
    """
    secrets = getattr(settings, "PAYMENT_WEBHOOK_SECRETS", None) or {}
    value = secrets.get(provider)
    return value or None


def verify_signature(*, provider: str, raw_body: bytes, signature: str | None) -> tuple[bool, str]:
    """HMAC-SHA256 over the RAW BODY BYTES. Returns `(ok, reason_if_not)`.

    ⚠ **OVER THE BYTES THAT ARRIVED, NEVER OVER A RE-SERIALISED DICT.** Two JSON
    encoders disagree about spacing, key order and unicode escaping, so a
    signature computed over `json.dumps(parsed)` fails for a reason nobody can
    debug — and the debugging usually ends with somebody switching verification
    off. The caller hands in `request.body` and this compares against that.

    `hmac.compare_digest`, not `==`: a comparison that returns early on the first
    wrong byte tells an attacker how much of a forged signature was right.
    """
    secret = signing_secret(provider)
    if secret is None:
        return False, REFUSED_NO_SECRET
    if not signature:
        return False, REFUSED_BAD_SIGNATURE
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # A provider may send `sha256=<hex>`; both spellings compare equal.
    offered = signature.split("=", 1)[-1].strip()
    if not hmac.compare_digest(expected, offered):
        return False, REFUSED_BAD_SIGNATURE
    return True, ""


def _existing_delivery(tenant_id: Any, provider: str, event_id: str) -> Any:
    """GUARD 1 — *has this DELIVERY been seen?* The cheap pre-insert half.

    `uq_payment_webhook_events_event` is the database half. This is the lookup
    that makes a redelivery cost one SELECT and open no transaction, and it runs
    **before signature verification and before any money path** — a retry must
    be recognised whatever else is true of it.
    """
    return models.PaymentWebhookEvent.objects.filter(
        tenant_id=tenant_id, provider=provider, event_id=event_id
    ).first()


def _replayed(row: Any) -> IngestedWebhook:
    """The no-op answer for a delivery this tenant has already seen.

    It reports the FIRST delivery's outcome, including its payment. A provider
    retrying after a timeout gets the same answer it would have got the first
    time, which is what stops it retrying again.
    """
    payment_no = None
    if row.payment_id is not None:
        payment = models.Payment.objects.filter(tenant_id=row.tenant_id, pk=row.payment_id).first()
        payment_no = getattr(payment, "payment_no", None)
    return IngestedWebhook(
        event_row_id=str(row.pk),
        provider=row.provider,
        event_id=row.event_id,
        status=models.WEBHOOK_DUPLICATE,
        signature_verified=row.signature_verified,
        created=False,
        payment_id=None if row.payment_id is None else str(row.payment_id),
        payment_no=payment_no,
        outcome=row.outcome,
        problems=WEBHOOK_UNAVAILABLE
        + (
            {
                "code": "duplicate_delivery_ignored",
                "br_ref": "BR-PAY-003",
                "detail": f"this tenant has already seen {row.provider} event {row.event_id}. "
                "Nothing was written: one delivery row, one payment, one audit row, one "
                "journal entry — the customer is not charged twice on this account.",
            },
        ),
    )


def _amount(raw: Any) -> Decimal:
    """The gateway's figure as a Decimal. A float is REFUSED, never converted.

    CLAUDE.md rule 2 at the boundary. A gateway that sends `29287` minor units
    is a gateway whose adapter must convert BEFORE this point and say so — this
    function will not guess a scale, because guessing one is how a $292.87
    payment becomes $29,287.00.
    """
    if isinstance(raw, float):
        raise PaymentRuleError(
            f"the gateway sent amount {raw!r} as a float. Money is NUMERIC(18,6) and never "
            "binary (CLAUDE.md rule 2) — refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise PaymentRuleError("the gateway sent no amount.", br_ref="BR-PAY-002")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise PaymentRuleError(
            f"the gateway sent amount {raw!r}, which is not a decimal figure.",
            br_ref="BR-PAY-002",
        ) from bad
    if value <= ZERO:
        raise PaymentRuleError(
            f"the gateway sent {value}. A callback reporting money RECEIVED carries a positive "
            "amount; a refund or a chargeback is a different event and a different path "
            "(BR-PAY-013 / BR-PAY-014).",
            br_ref="BR-PAY-002",
        )
    return value


def _moment(raw: Any, what: str) -> datetime:
    """A date the GATEWAY named. Nothing here reads a clock (BR-TEN-043, G6).

    BR-PAY-021 is the module's cardinal rule — posting date and clearing date,
    always both — and for a gateway payment both are facts the provider knows
    and this product does not. A server clock would decide a business day in the
    SERVER's timezone and would make a redelivered callback stamp a different
    instant from the first, which is a replay that is not identical.
    """
    if not raw:
        raise PaymentRuleError(
            f"the gateway sent no {what}. BR-PAY-021 requires both the posting and the "
            "clearing moment and this product reads no clock: a payment stamped with the "
            "server's time would be on time or late depending on where the server is.",
            br_ref="BR-PAY-021",
        )
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as bad:
        raise PaymentRuleError(
            f"the gateway sent {what} {raw!r}, which is not an ISO-8601 moment.",
            br_ref="BR-PAY-021",
        ) from bad


def ingest(
    *,
    provider: str,
    event_id: str,
    raw_body: bytes,
    signature: str | None,
    received_at: datetime,
    payload: dict[str, Any] | None = None,
    actor: Any = None,
) -> IngestedWebhook:
    """C21 — record what the gateway said, and the payment it produced.

    **The delivery row is written whatever happens**, and the payment is written
    inside a SAVEPOINT so that a refused payment loses the delivery row with it
    on no database (see the module docstring on hard-won law 14).

    THE ORDER, and every step of it is a rule rather than a preference:

      1. **Guard 1 — has this delivery been seen?** BEFORE verification and
         before any money path, because a retry must be recognised whatever else
         is true of it. Costs one SELECT and opens no transaction.
      2. **Verify the signature.** A refused delivery is RECORDED with its reason
         and creates no payment. Fails CLOSED on a deployment with no secret.
      3. **Record the delivery.**
      4. **Record the payment, in a SAVEPOINT**, through `services.record_payment`
         — the ONE inbound write path, unchanged, which allocates against open
         bills and posts to the books exactly as a counter payment does. The
         idempotency key is `webhook|<provider>:<event_id>`, so guard 2 catches
         a race that slipped past guard 1.
      5. **Stamp the outcome on the delivery row** — the one thing
         `payments/0020`'s freeze lets move.

    `actor` is `None` for a gateway, which is correct and is why every audit row
    on this path names the job instead (BR-AUD-003). **There is no user behind a
    webhook and none is invented**: a service account nobody has ruled on is
    exactly the shape `reversal.py` refuses to pre-empt for CS-1.

    Raises nothing a caller must catch for a business refusal — a refused
    delivery is a RESULT with its reason, because a gateway retrying a 500
    forever over a bad account number helps nobody.
    """
    tenant_id = _tenant_id()
    provider, event_id = _named(provider, event_id)

    # ── 1 · guard 1, before everything ──────────────────────────────────────
    already = _existing_delivery(tenant_id, provider, event_id)
    if already is not None:
        return _replayed(already)

    # ── 2 · the signature ───────────────────────────────────────────────────
    verified, refusal = verify_signature(provider=provider, raw_body=raw_body, signature=signature)
    body = payload if payload is not None else _parsed(raw_body)

    # ── 3, 4, 5 · the delivery row, the audit row and the payment ───────────
    return _deliver(
        tenant_id=tenant_id,
        provider=provider,
        event_id=event_id,
        body=body,
        received_at=received_at,
        verified=verified,
        refusal=refusal,
        actor=actor,
        audit_after={"job": "payments.webhook"},
    )


def settle_charge(
    *,
    provider: str,
    key: str,
    body: dict[str, Any],
    received_at: datetime,
    actor: Any = None,
    portal_actor: dict[str, Any] | None = None,
) -> IngestedWebhook:
    """`US-CWP-045` — a charge WE asked for and the provider APPROVED, **through
    this same door**.

    ⚠ **IT IS THE SAME DOOR ON PURPOSE, AND THAT IS THE WHOLE REASON IT LIVES
    IN THIS FILE RATHER THAN IN `gateway.py`.** The PO's 2026-09-05 ruling says
    a test provider *"posts its settlement through the SAME door a real
    processor uses"*, and the promise underneath it is that **none of the
    downstream work is rebuilt when a real vendor arrives**. A second recording
    path for portal-initiated money would be a second answer to *what did this
    customer pay* — allocated by one rule here and another rule there — and the
    day they disagreed would be the day a customer rang about it.

    ⚠ **THE PROVIDER'S LATER SETTLEMENT CALLBACK FOR THIS SAME CHARGE IS A
    DUPLICATE AND WRITES NOTHING**, because `event_id` here is the idempotency
    key we presented to the provider (`Idempotency(source="request_key")` on the
    manifest) and its settlement carries that same key. Guard 1 recognises it
    before any money path runs; guard 2 (`uq_payments_webhook_key`, composed
    through `idempotency.inbound_payment_key`) catches the race guard 1's SELECT
    cannot close. Neither is trusted because the other exists (DEF-058).

    ⚠ **NO SIGNATURE IS VERIFIED AND NONE IS PRETENDED.** There was no delivery:
    this is our own process reporting what our own outbound call was told, over
    a connection whose credentials we hold. The delivery row records
    `signature_verified=False` and its `event_type` says where it came from, so
    a person reading the table can tell an in-process settlement from an inbound
    one — which is exactly the distinction a blanket `True` would destroy.
    **`ingest` is unchanged and still fails closed on an unsigned delivery**
    (hard-won law 3); nothing here widens that.

    ⚠ **IT IS ONLY EVER CALLED AFTER AN APPROVAL.** A decline and a timeout
    return before this function is reached — see `gateway.ChargeOutcome`.
    """
    tenant_id = _tenant_id()
    provider, key = _named(provider, key)
    already = _existing_delivery(tenant_id, provider, key)
    if already is not None:
        return _replayed(already)
    payload = dict(body)
    payload.setdefault("type", CHARGE_SETTLED)
    return _deliver(
        tenant_id=tenant_id,
        provider=provider,
        event_id=key,
        body=payload,
        received_at=received_at,
        verified=False,
        refusal="",
        actor=actor,
        # hard rule 7 — a portal customer is NOT a `User`, so `actor_user_id`
        # stays NULL and the payload NAMES who acted and on which session
        # (`BR-CWP-004`, and `customers.portal_self_service._portal_actor`'s own
        # reasoning). `US-CWP-045` TC-10 is a DELEGATE paying, and this is the
        # field that carries which login it was.
        audit_after={"job": "payments.portal_charge", **(portal_actor or {})},
        skip_verification=True,
    )


@dataclass(frozen=True)
class LandedDelivery:
    """What the INTEGRATIONS door did with one arriving notification.

    Deliberately smaller than `IngestedWebhook`: there is no payment on it,
    no amount and no currency, because `land_delivery` records **none of
    those things**. A result object with a `payment_id` field would be a
    field somebody eventually fills (the `autopay_capture_intents` argument
    this module already makes about a status that can express a charge).
    """

    event_row_id: str
    provider: str
    event_id: str
    status: str
    landed: bool


def land_delivery(
    *,
    provider: str,
    event_id: str,
    body: dict[str, Any],
    received_at: datetime,
    actor: Any = None,
    audit_after: dict[str, Any] | None = None,
) -> LandedDelivery:
    """Record that a partner told us something — and **stop there**.

    ⚠ **THIS IS `ingest` WITHOUT STEP 4, AND THE MISSING STEP IS THE WHOLE
    POINT (`BR-INT-058`, PO ruling 2026-09-06, `OQ-INT-1729` option (a)).**
    `ingest` records the delivery and then records the payment. The
    INTEGRATIONS inbound door — `apps/integrations/inbound.py`, the kiosk —
    may do the first and **may not do the second**: *"we check the key,
    refuse duplicates, save exactly what arrived, and reply fast. That is
    integrations and it STOPS THERE. Everything after — reading it, deciding
    what it means, writing a record — is the runbook, and may happen a second
    later."* So this function writes ONE row to `payment_webhook_events` and
    ONE audit row, and calls nothing in `services`.

    **The reason is operational rather than tidy, and it is worth keeping in
    front of whoever next reads this:** the vendor is holding a socket open
    and will re-send if we are slow, so answering the door must never wait on
    processing. Fold the apply back in and a slow runbook becomes a duplicate
    delivery from every vendor at once — a correctness failure on a money
    path arriving as a retry storm exactly when the system can least absorb
    it.

    ⚠ **IT IS NOT A STUB AND NOTHING HERE IS AWAITING A RULING** (the
    `OQ-1396` distinction). The ruling has been made; the apply half is
    Runbooks' and is not built. `apps/integrations/inbound.runbooks_apply()`
    is the named seam it plugs into, and a test asserts that seam does
    nothing so the boundary cannot close by accident.

    ⚠ **THE DEDUPE AND THE PERSIST ARE ONE ACT, DELIBERATELY.** The composite
    key arrives already built (`kiosk · K-88231 · payment` vs `… · return`,
    `BR-INT-020` D) and `uq_payment_webhook_events_event` is what decides
    whether this delivery is new. An INSERT that the index refuses IS the
    duplicate verdict — which closes the race a SELECT-then-INSERT leaves
    open, and means the raw envelope is on disk before the reply goes out
    (`BR-INT-021`). `_existing_delivery` still runs first because a
    redelivery must cost one SELECT and open no transaction; the INSERT is
    the guard, not the lookup.

    ⚠ **CLAUDE.md HARD-WON LAW 14 — THE `transaction.atomic()` BELOW IS A
    SAVEPOINT AND IT IS THE ONLY THING THAT WORKS ON POSTGRESQL. DO NOT
    "SIMPLIFY" IT AWAY.** The door lands a BATCH one item at a time, and the
    second item being a duplicate must not lose the first. On PostgreSQL a
    failed INSERT aborts the whole transaction: every later statement raises
    `InFailedSqlTransaction` and the committed-looking earlier item is gone
    at COMMIT. **SQLite has no aborted-transaction state**, and
    `config/settings/test.py` hardcodes in-memory SQLite, so the version
    without this savepoint passes the entire suite on every machine and loses
    a real payment the first time two arrive together.
    `tests/test_us_int_044_inbound_door.py` marks that case
    `requires_postgres` for exactly this reason.

    `actor` is `None` for a machine, which is correct: there is no user
    behind a kiosk and none is invented (`BR-AUD-003`). Hard rule 7 is
    honoured on every landing — a notification that money arrived, with no
    record of it having arrived, is what rule 7 exists to prevent.
    """
    tenant_id = _tenant_id()
    provider, event_id = _named(provider, event_id)

    already = _existing_delivery(tenant_id, provider, event_id)
    if already is not None:
        return LandedDelivery(
            event_row_id=str(already.pk),
            provider=already.provider,
            event_id=already.event_id,
            status=models.WEBHOOK_DUPLICATE,
            landed=False,
        )
    try:
        with transaction.atomic():  # ← SAVEPOINT. Law 14. Do not remove.
            row = models.PaymentWebhookEvent.objects.create(
                tenant_id=tenant_id,
                provider=provider,
                event_id=event_id,
                event_type=str(body.get("type") or "") or None,
                status=models.WEBHOOK_RECEIVED,
                # There is no signature on this path and none is pretended.
                # The kiosk network publishes source addresses instead, and
                # the allowlist is checked in `integrations/runners/serve.py`
                # BEFORE this function is reached and before the body is read
                # (`BR-INT-044`). A blanket `True` here would destroy the one
                # distinction this column exists to make.
                signature_verified=False,
                body=body,
                received_at=received_at,
            )
            core_audit.money_action(
                actor,
                AUDIT_RECEIVED,
                "payment_webhook_event",
                str(row.pk),
                after={
                    "provider": provider,
                    "event_id": event_id,
                    "signature_verified": False,
                    "received_at": received_at.isoformat(),
                    **(audit_after or {"job": "integrations.inbound_door"}),
                },
            )
    except IntegrityError:
        # `uq_payment_webhook_events_event` refused ours: another delivery of
        # this same event committed between the SELECT above and this INSERT.
        # That is the correct outcome — one delivery row — and on PostgreSQL
        # the savepoint is what lets the CALLER carry on to the next item.
        winner = _existing_delivery(tenant_id, provider, event_id)
        if winner is None:  # pragma: no cover - the index is the only cause
            raise
        return LandedDelivery(
            event_row_id=str(winner.pk),
            provider=winner.provider,
            event_id=winner.event_id,
            status=models.WEBHOOK_DUPLICATE,
            landed=False,
        )
    return LandedDelivery(
        event_row_id=str(row.pk),
        provider=row.provider,
        event_id=row.event_id,
        status=models.WEBHOOK_RECEIVED,
        landed=True,
    )


def _named(provider: Any, event_id: Any) -> tuple[str, str]:
    """Both halves of the dedupe key, or a refusal by name."""
    provider = (provider or "").strip()
    event_id = (event_id or "").strip()
    if not provider or not event_id:
        raise PaymentRuleError(
            "a webhook delivery names its provider and that provider's own event id. Without "
            "both there is nothing to dedupe on, and a gateway that retries would create a "
            "second payment on a customer's account (CLAUDE.md hard rule 6).",
            br_ref="BR-PAY-003",
        )
    return provider, event_id


def _deliver(
    *,
    tenant_id: Any,
    provider: str,
    event_id: str,
    body: dict[str, Any],
    received_at: datetime,
    verified: bool,
    refusal: str,
    actor: Any,
    audit_after: dict[str, Any],
    skip_verification: bool = False,
) -> IngestedWebhook:
    """Steps 3–5, shared by the signed inbound door and the in-process one.

    ⚠ **EXTRACTED, NOT REWRITTEN (2026-09-05, `US-CWP-006`).** `ingest`'s body
    from *record the delivery row* to *stamp the outcome* moved here verbatim so
    that `settle_charge` runs the SAME three steps rather than a second copy of
    them. A copy would have been the cheaper diff and it would have been two
    places to keep the SAVEPOINT, two places to keep the audit row, and two
    places somebody would later fix one of. The fifteen existing `C21` cases
    exercise this path unchanged and are the proof that nothing moved.
    """
    try:
        with transaction.atomic():
            # ── 3 · the delivery row, whatever the outcome ──────────────────
            row = models.PaymentWebhookEvent.objects.create(
                tenant_id=tenant_id,
                provider=provider,
                event_id=event_id,
                event_type=str(body.get("type") or "") or None,
                status=models.WEBHOOK_RECEIVED,
                signature_verified=verified,
                body=body,
                received_at=received_at,
            )
            # hard rule 7, INSIDE the transaction. A gateway has no user, so the
            # JOB is named instead (BR-AUD-003) — and money that arrived with no
            # record of how is the outcome rule 7 exists to prevent.
            core_audit.money_action(
                actor,
                AUDIT_RECEIVED,
                "payment_webhook_event",
                str(row.pk),
                after={
                    "provider": provider,
                    "event_id": event_id,
                    "signature_verified": verified,
                    "received_at": received_at.isoformat(),
                    **audit_after,
                },
            )
            if not verified and not skip_verification:
                return _refuse(row, refusal, _refusal_detail(refusal))

            # ── 4 · the payment, in a SAVEPOINT ─────────────────────────────
            return _record(row, body=body, actor=actor)
    except IntegrityError:
        # The race guard 1's SELECT cannot close: another delivery of this same
        # event committed between our lookup and our INSERT.
        # `uq_payment_webhook_events_event` refused ours, which is the correct
        # outcome — one delivery row, one payment.
        winner = _existing_delivery(tenant_id, provider, event_id)
        if winner is None:  # pragma: no cover - the index is the only cause
            raise
        return _replayed(winner)


def _parsed(raw_body: bytes) -> dict[str, Any]:
    """The body as a dict, or `{}` with the failure recorded by the caller.

    A body that will not parse is still a delivery and still gets a row — it is
    the one a person most needs to see — so this answers `{}` rather than
    raising, and the payment step then refuses on the missing fields by name.
    """
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _refusal_detail(code: str) -> str:
    if code == REFUSED_NO_SECRET:
        return (
            "this deployment has no signing secret configured for that provider, so no "
            "callback from it can be verified and none is accepted. That is the safe "
            "direction: an endpoint that created payments from unverified callbacks would be "
            "an unauthenticated way to put money on any account. Set the secret on the HOST "
            "— editing `.env.example` changes nothing already deployed."
        )
    return (
        "the signature did not verify against this deployment's secret for that provider. "
        "The delivery is recorded and no payment was created. A provider misconfiguration "
        "and a forged callback look identical here, which is why the row exists at all."
    )


def _refuse(row: Any, code: str, detail: str) -> IngestedWebhook:
    """Record the refusal on the delivery row and answer with it."""
    row.status = models.WEBHOOK_REFUSED
    row.outcome = code
    # Only the columns `payments/0020`'s freeze lets move.
    row.save(update_fields=["status", "outcome", "updated_at"])
    return IngestedWebhook(
        event_row_id=str(row.pk),
        provider=row.provider,
        event_id=row.event_id,
        status=models.WEBHOOK_REFUSED,
        signature_verified=row.signature_verified,
        outcome=code,
        problems=WEBHOOK_UNAVAILABLE + ({"code": code, "br_ref": "BR-PAY-003", "detail": detail},),
    )


def _record(row: Any, *, body: dict[str, Any], actor: Any) -> IngestedWebhook:
    """Step 4 — the payment, inside a SAVEPOINT. See the module docstring.

    ⚠ **THE NESTED `transaction.atomic()` IS A SAVEPOINT AND IT IS THE ONLY
    THING THAT MAKES THIS WORK ON POSTGRESQL (CLAUDE.md hard-won law 14). DO NOT
    "SIMPLIFY" IT AWAY.** Without it, a payment refused by any rule aborts the
    WHOLE transaction — the delivery row goes with it, every later statement
    raises `InFailedSqlTransaction`, and the deliveries that most needed
    recording are exactly the ones that vanish. **SQLite has no aborted-
    transaction state, so the broken version passes the entire suite**, which is
    why the proof for this is a `requires_postgres` test and not a green run.
    """
    from apps.payments import services

    try:
        with transaction.atomic():  # ← SAVEPOINT. Law 14. Do not remove.
            recorded = services.record_payment(
                actor,
                account_id=body.get("account_id"),
                amount=_amount(body.get("amount")),
                # BR-PAY-021 — both dates, and the GATEWAY names them. A
                # `cleared_at` is what makes this money that ARRIVED, which is
                # what a settled gateway payment is and is why it allocates and
                # posts without a clerk.
                posted_at=_moment(body.get("posted_at") or body.get("created_at"), "posting date"),
                cleared_at=_moment(
                    body.get("cleared_at") or body.get("posted_at") or body.get("created_at"),
                    "clearing date",
                ),
                currency=body.get("currency"),
                method_code=body.get("method"),
                confirmation=body.get("reference") or row.event_id,
                memo=body.get("memo"),
                idempotency_source=idempotency.SOURCE_WEBHOOK,
                # GUARD 2 — `webhook|<provider>:<event_id>`, dedupe on
                # `uq_payments_webhook_key`. Independent of guard 1 and asserted
                # separately (DEF-058).
                idempotency_reference=f"{row.provider}:{row.event_id}",
            )
    except PaymentRuleError as refusal:
        # The delivery STANDS and says why. The money is real at the gateway and
        # somebody has to see it — a lost row here is a payment nobody knows
        # about, and the provider will stop retrying long before anyone notices.
        return _refuse(row, REFUSED_RULE, str(refusal))

    row.status = models.WEBHOOK_ACCEPTED
    row.payment_id = recorded.payment_id
    row.outcome = f"recorded as {recorded.payment_no or recorded.payment_id}"
    row.processed_at = row.received_at
    row.save(update_fields=["status", "payment_id", "outcome", "processed_at", "updated_at"])
    return IngestedWebhook(
        event_row_id=str(row.pk),
        provider=row.provider,
        event_id=row.event_id,
        status=models.WEBHOOK_ACCEPTED,
        signature_verified=True,
        created=recorded.created,
        payment_id=recorded.payment_id,
        payment_no=recorded.payment_no,
        amount=recorded.amount,
        currency=recorded.currency,
        outcome=row.outcome,
        problems=WEBHOOK_UNAVAILABLE + recorded.problems,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 §0d.1 C21 · CR-059 §4 (the four new tables) · BR-PAY-003 ·
#         BR-PAY-021 · BR-PAY-028 · BR-PAY-036 · apps/payments/idempotency.py ·
#         apps/payments/services.record_payment · apps/payments/migrations/0020
# generated: 2026-09-03 by the CR-059/CR-060 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — C21's acceptance line is
#            that the payment *"appears on Record payments"*, which is the
#            EXISTING S33 list and needs nothing built) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 a row in 12-governance/09-human-review-ledger.md is OWED — webhook keys
#      are a 🔒 path by name — and that file is outside this lane's write scope.
#      Its content is in the decision log to be transcribed. REPORTED.
#   E2 the endpoint that calls this is NOT mounted by this lane. A webhook URL
#      is unauthenticated by construction and its exemption from the tenant
#      middleware and from CSRF is a platform decision, not a payments one.
#      `ingest` is written, tested and callable; mounting it is REPORTED as the
#      remaining half. Hard-won law 2 in the open: the service exists and no
#      gateway can reach it yet.
#   E3 no `PAYMENT_WEBHOOK_SECRETS` value is added to `.env.example` by this
#      lane (that file is outside its scope), and law 4 applies either way — a
#      template change reaches no host that already has an `.env`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
