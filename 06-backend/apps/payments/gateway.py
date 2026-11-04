# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-045 (EP-CWP-09) — *Pay now, and where the payment will land,
#           before it commits*. Screen: CWP-038 at `/{tenant}/portal/pay-now`
# Rules:    BR-CWP-058 (the screen shows where the payment will land BEFORE it
#           commits) · BR-CWP-056 (a control that may not be used is DISABLED
#           WITH ITS REASON) · BR-INT-037 (a provider is DATA — adding one adds
#           a manifest, not a branch) · BR-INT-018 (an unconfirmed run is not a
#           green word) · BR-INT-026 (sandbox and production are two rows) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 2 (4 dp, never float)
#           · rule 4 (no UPDATE on a payment) · rule 6 (idempotency) · rule 7
#           (every money action writes `audit_log`)
# Tests:    06-backend/tests/test_us_cwp_045_pay_now.py (TC-6 zero rows on a
#           timeout · TC-7 the retry carries the same key) ·
#           06-backend/tests/test_us_cwp_006_webhook_door.py (the mount, and the
#           two `requires_postgres` cases — law 14's SAVEPOINT and the RLS
#           refusal — 10 passed on PostgreSQL 16)
# Impacts:  apps/payments/webhooks.settle_charge (the ONE write door) ·
#           apps/portal/seams/pay_now_seam.py · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""ASKING A PROVIDER TO CHARGE — and this is the only file in the product that does.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is a 🔒 path by CLAUDE.md's own list
(idempotency keys, money rounding) and it is the first code in this product that
can move a real customer's money. AI-authored under the PO ruling of 2026-08-09;
a row in `12-governance/09-human-review-ledger.md` is OWED and this lane's write
scope does not include that file, so what a reviewer is owed is REPORTED with
its worked figures instead.

════════════════════════════════════════════════════════════════════════════
⚠ NO PROVIDER IS NAMED HERE, AND THAT IS THE WHOLE ARCHITECTURE
════════════════════════════════════════════════════════════════════════════
**PO ruling 2026-09-05, verbatim:** *"we will have multiple payment providers
integrated using integration module. For given utility we will activate 1 or
2."*

So *which* processor charges a card is a fact about the TENANT'S INTEGRATION
CONNECTION, never about `apps/payments`. This module asks the registry for every
manifest whose **category** is `payments` and looks for one of those the tenant
has connected. `G77` fails the merge on a `provider_key ==` anywhere outside
`adapters/` and `manifests/`, and the reason is `BR-INT-037` — *"every time such
integration comes we dont want to change our integration framework"*. When
Worldpay lands it is one manifest and one adapter and **not one line of this
file**.

════════════════════════════════════════════════════════════════════════════
⚠ THE KEY IS MINTED BEFORE THE REQUEST LEAVES. THAT IS THE POINT OF `mint`
════════════════════════════════════════════════════════════════════════════
`US-CWP-045` TC-7: *"Carries the SAME idempotency key generated BEFORE the first
request left, so a debit that already happened is never taken twice."*

A key minted **after** an answer comes back cannot exist for the one case it is
for — the case where no answer comes back. So `mint()` is called on the PREVIEW,
the key travels to the screen with the *where it will go* panel, and the screen
sends the same key on the commit **and on every retry of it**. That is why the
preview is a POST that writes nothing but still returns something the caller
must keep.

⚠ **IT IS NOT STORED ON A `payment` ROW BEFORE THE CHARGE, AND IT CANNOT BE.**
`US-CWP-045` §5 says the key is *"generated and stored before the request
leaves"* and TC-6 says a timeout writes **no payment row at all**. Both are true
at once only if the thing that holds the key across a retry is the CALLER, not a
row: a row written before the answer is a payment claim nobody can make. What
holds it on our side is `uq_payments_webhook_key` at the moment the money is
real — see `webhooks.settle_charge`.

════════════════════════════════════════════════════════════════════════════
⚠ A TIMEOUT WRITES NOTHING IN `payments`. AN UNKNOWN OUTCOME IS NOT A ZERO
════════════════════════════════════════════════════════════════════════════
`US-CWP-045` TC-6, in the story's own words: *"The screen says so and no payment
row is written. Assert zero rows — an unknown outcome is not a zero."*

`RunResult.confirmed is False` is the provider saying nothing, and `BR-INT-018`
already refuses to turn that into a green word. Here it becomes `NO_ANSWER`, and
`NO_ANSWER` returns **before** anything in `apps/payments` is written: no
payment, no allocation, no journal line, no audit row. **The attempt is not
invisible** — `integrations` records it as an unconfirmed run of its own, which
is that module's job and its table — but nothing in the money modules claims a
payment happened, because nobody knows whether one did.

⚠ **AND THE MONEY MAY WELL HAVE MOVED AT THE FAR END.** That is precisely why
the answer carries the key back: the retry re-presents it and the provider's own
idempotency (`Idempotency(mode="refuse", source="request_key")` on the manifest)
refuses the second debit.

════════════════════════════════════════════════════════════════════════════
⚠ THE GUEST CHARGE IS NOW HERE, AND THIS SECTION USED TO SAY IT WAS MISSING
════════════════════════════════════════════════════════════════════════════
**`charge_guest_bill` is written, below.** Until 2026-09-05 this section read
*"one charge this file does not publish, and something already calls it"* — and
it was right: `apps/portal/guest_api.bill_pay` called it, this module did not
define it, and a stranger who looked up their bill, saw the amount and pressed
**Pay** got **503 · the provider was silent**. Not a regression and not a
silence anybody chose: the `AttributeError` was swallowed by that edge's
`except Exception`, so the guest path had refused identically since the day it
was written.

**THE LANE THAT STOPPED WAS RIGHT TO, AND THAT IS THE PART WORTH KEEPING.** It
recorded the contract instead of stubbing a function that would always refuse,
because a function that existed and always refused would make the call site
LOOK wired — hard-won law 2 pointed the wrong way. What it correctly refused to
invent was one read: **bill number → the account the payment lands on**, which
`apps.payments.billing_seam` did not publish, and inventing one from here would
have been this file choosing where a stranger's money goes.

**WHAT CLOSED IT.** `billing_seam.account_for_bill_number` publishes that read,
narrow and tenant-scoped, **with the reasoning for its shape written into that
file** — including the option that was refused: letting the guest EDGE pass the
account down, which would have made *where the money lands* a request-shaped
value on a public form. The contract this section recorded did not move:

    charge_guest_bill(tenant_id, *, bill_number, amount, currency, instrument,
                      receipt_email, channel, paid_by, idempotency_key)
        -> {reference, amount, currency, paid_at, method_brand,
            method_last_four, receipt_sent}

**AND IT STILL WRITES NOTHING ITSELF.** The approval goes to
`webhooks.settle_charge`, the same door a real processor's settlement comes
through, so the allocation, the balanced pair, the receipt queue and the audit
row are the existing tested ones. The refusals — a decline, a timeout, a held
control, a number that names no payable bill — return before that door and
raise `GuestChargeRefused`, which is a raise rather than a result **only on
this path**, for the reason written on the class: the guest edge turns whatever
comes back into a receipt.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT THIS FILE DELIBERATELY DOES NOT DO
════════════════════════════════════════════════════════════════════════════
It does not write a payment, allocate one, post to the ledger, write an audit
row, or decide what a bill owes. `BR-INT-038` — *an adapter TRANSLATES; it
decides nothing* — applies one level up as well: everything downstream of an
approved charge is `services.record_payment` reached through
`webhooks.settle_charge`, which is the same door a real processor's settlement
comes through. That is the ruling's own promise (*"none of it is rebuilt when a
real provider is chosen"*) kept in code rather than in a docstring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from apps.integrations import models as integration_models
from apps.integrations import services as integration_services
from apps.integrations.registry import REGISTRY, Manifest, Operation, Registry
from apps.integrations.runners import deliver as integration_deliver
from apps.payments.exceptions import PaymentRuleError
from core import errors
from core import tenancy as core_tenancy

#: The manifest CATEGORY every payment processor declares. ⚠ A category and not
#: a provider key: `payments_sandbox`, `payments_card` and the five the PO named
#: on 2026-09-05 all carry it, and the next one will too without this constant
#: moving (`BR-INT-037`).
PAYMENTS_CATEGORY = "payments"

#: The manifest OPERATION this file asks for. Named here so a manifest that
#: declares it under another word fails at lookup rather than silently never
#: being charged.
CHARGE = "charge"

#: The three outcomes, and there are exactly three because there are exactly
#: three things that can be true about somebody else's money.
APPROVED = "approved"
DECLINED = "declined"
#: ⚠ **NOT A FAILURE AND NOT A ZERO.** The provider did not answer, so what
#: happened at the far end is unknown. `US-CWP-045` TC-6.
NO_ANSWER = "no_answer"
OUTCOMES = (APPROVED, DECLINED, NO_ANSWER)

#: Why a Pay control is held, as CODES a screen renders in its own language
#: (B14 rules 33 and 35 — five or six words, written by eleven catalogues and
#: never by this module).
HELD_NO_PROVIDER = "no_payment_provider_connected"
HELD_NO_ADAPTER = "provider_cannot_charge_yet"
HELD_CASH_ONLY = "account_is_cash_only"
HELD_NO_METHOD = "no_saved_payment_method"
HELD_NOT_PERMITTED = "this_login_may_not_pay"

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refuses rather than defaulting, for `open_bills._tenant_id`'s reason: on
    PostgreSQL RLS would block the read and on the SQLite developer tier it
    would answer for whichever tenant came first.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


@dataclass(frozen=True)
class PaymentsProvider:
    """The tenant's active payments connection, as much of it as this file needs.

    ⚠ **`environment` TRAVELS ALL THE WAY TO THE SCREEN.** A tenant connected to
    a SANDBOX provider is testing, and the customer looking at the confirmation
    is entitled to know no real money moved (PO ruling 2026-09-05 §3). It is a
    fact on the connection row rather than a property of any provider's name.
    """

    connection: Any
    manifest: Manifest
    operation: Operation
    adapter_cls: type

    @property
    def provider_key(self) -> str:
        return str(self.manifest.key)

    @property
    def environment(self) -> str:
        return str(self.connection.environment)

    @property
    def is_sandbox(self) -> bool:
        return self.environment == integration_models.ENVIRONMENT_SANDBOX


@dataclass(frozen=True)
class ChargeOutcome:
    """What the provider said — and, on `NO_ANSWER`, that it said nothing.

    `key` is on EVERY outcome including the one that wrote nothing, because the
    retry needs it and the retry is the whole reason it was minted early
    (TC-7).
    """

    outcome: str
    key: str
    provider_key: str
    environment: str
    amount: Decimal | None = None
    currency: str | None = None
    #: THEIRS, verbatim and scrubbed by the adapter. Shown to staff, never
    #: rendered as a customer's refusal sentence (`G89`, `BR-INT-034`).
    provider_text: str | None = None
    run_id: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=())

    @property
    def approved(self) -> bool:
        return self.outcome == APPROVED

    @property
    def wrote_nothing(self) -> bool:
        """⚠ TRUE ON A TIMEOUT **AND** ON A DECLINE. Only an approval may be
        followed by a payment row, and the caller reads this rather than
        re-deriving it from `outcome`."""
        return self.outcome != APPROVED


def mint(*, prefix: str = "pay") -> str:
    """The idempotency key, minted **before the request leaves** (TC-7).

    ⚠ **RANDOM, NOT DERIVED FROM THE PAYMENT'S FACTS.** A key derived from
    account + amount + day would collide across two genuine payments of the same
    amount on the same day — a customer paying `$40.00` twice in an afternoon
    would have the second one silently swallowed as a duplicate of the first,
    which is the mirror of the bug idempotency exists to prevent and is far
    harder to see.

    ⚠ **AND IT IS MINTED ONCE PER ATTEMPT-SEQUENCE, NOT ONCE PER REQUEST.** The
    caller mints it on the preview and re-presents the SAME string on the commit
    and on every retry of that commit. A caller that minted a fresh key per HTTP
    request would have idempotency that reads correctly and protects nothing.
    """
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def payments_manifests(*, registry: Registry = REGISTRY) -> tuple[Manifest, ...]:
    """Every registered provider whose CATEGORY is payments — by category, never
    by key (`G77`, `BR-INT-037`)."""
    return tuple(one for one in registry.all() if one.category == PAYMENTS_CATEGORY)


def active_provider(tenant_id: Any = None, *, registry: Registry = REGISTRY) -> PaymentsProvider | None:
    """The payments provider this tenant has switched on, or **None as a value**.

    ⚠ **NONE IS A VALUE AND NOT AN ERROR**, exactly as `registry.adapter_for`
    answers None for a provider with no adapter. A utility that has connected no
    processor is the ordinary state of this product today, and the screen's job
    is to render the Pay control **disabled with its reason** (`BR-CWP-056`),
    which it cannot do if this raised.

    Production is preferred over sandbox when a tenant holds both rows — they
    are two rows by `BR-INT-026`, and the one that takes real money wins.
    """
    tenant_id = tenant_id if tenant_id is not None else _tenant_id()
    keys = [one.key for one in payments_manifests(registry=registry)]
    if not keys:  # pragma: no cover — a build with no payments manifest at all
        return None
    rows = list(
        integration_models.IntegrationConnection.objects.filter(
            tenant_id=tenant_id,
            provider_key__in=keys,
            enabled=True,
        ).exclude(status=integration_models.STATUS_OFF)
    )
    if not rows:
        return None
    rows.sort(key=lambda row: 0 if row.environment == integration_models.ENVIRONMENT_PRODUCTION else 1)
    for row in rows:
        manifest = registry.get(row.provider_key)
        if manifest is None:  # pragma: no cover — the registry refuses unknown keys at connect
            continue
        operation = next((one for one in manifest.operations if one.name == CHARGE), None)
        adapter_cls = registry.adapter_for(manifest.key)
        if operation is None or adapter_cls is None:
            # A declared-but-not-yet-connectable processor. The screen says so
            # rather than offering a control that would answer nothing.
            continue
        return PaymentsProvider(
            connection=row, manifest=manifest, operation=operation, adapter_cls=adapter_cls
        )
    return None


def held_reason(
    *,
    provider: PaymentsProvider | None,
    cash_only: bool,
    has_method: bool,
    may_pay: bool,
) -> str | None:
    """Why the Pay control may not be pressed — **a code, or None.**

    ⚠ **THE ORDER IS THE ORDER A PERSON CAN ACT ON.** A cash-only account is
    told it is cash-only even where no provider is connected, because that is
    the fact that will still be true tomorrow and it is the one a customer can
    ring about. `BR-CWP-056` is what forbids the alternative — a control that is
    simply absent, or present and inert.
    """
    if not may_pay:
        return HELD_NOT_PERMITTED
    if cash_only:
        return HELD_CASH_ONLY
    if provider is None:
        return HELD_NO_PROVIDER
    if not has_method:
        return HELD_NO_METHOD
    return None


def charge(
    *,
    provider: PaymentsProvider,
    key: str,
    amount: Decimal,
    currency: str,
    token: str,
) -> ChargeOutcome:
    """Ask the tenant's provider for ONE debit. Writes nothing in `apps/payments`.

    ⚠ **THE KEY IS AN ARGUMENT AND IS NEVER MINTED HERE.** `mint()` is a separate
    function called by the caller before the first attempt, and this signature is
    what makes a retry able to be a retry: the same `key` presented twice is one
    debit at the provider (`Idempotency(mode="refuse", source="request_key")`)
    and one payment here (`uq_payments_webhook_key`). See the module docstring.

    ⚠ **AN UNCONFIRMED RUN IS `NO_ANSWER` AND NOT A FAILURE** (`BR-INT-018`).
    `RunResult.confirmed is False` means the far end did not say what it did;
    turning that into *declined* would tell a customer no money moved when it may
    have, and turning it into *paid* would be worse.

    ⚠ **THE ATTEMPT IS RECORDED BY `integrations`, IN `integrations`' OWN
    TABLE.** `execute_run` opens and closes an `integration_run`, which is that
    module's audit of what it was asked to do. Nothing here writes another
    module's rows (B2 §2), and nothing here writes a payments row on an outcome
    that is not an approval.
    """
    if not key or not str(key).strip():
        raise PaymentRuleError(
            "a charge is asked for with the idempotency key that was minted before the first "
            "attempt left (US-CWP-045 TC-7). Without it a retry after a timeout would take a "
            "second debit from a customer who has already paid (CLAUDE.md hard rule 6).",
            br_ref="BR-PAY-028",
        )
    figure = _as_money(amount)
    run = integration_deliver.execute_run(
        connection=provider.connection,
        operation=provider.operation,
        adapter=provider.adapter_cls(),
        work=[
            {
                # ⚠ `ref` IS THE IDEMPOTENCY KEY, and the manifest declares
                # `source="request_key"` for exactly this reason: what the
                # provider dedupes on is what we present, so the retry and the
                # first attempt are one debit at their end as well as at ours.
                "ref": str(key),
                "operation": CHARGE,
                "amount": str(figure),
                "currency": currency,
                "token": token,
            }
        ],
        # ⚠ `manual` IS THE CLOSED VOCABULARY'S WORD FOR *A PERSON PRESSED IT*
        # (`RUN_TRIGGERS`), and a customer pressing Pay is exactly that. There
        # is no `inline`; `start_run` refuses an undeclared trigger by name
        # rather than storing one no screen can group on.
        trigger="manual",
    )
    # ⚠ **THE OUTCOME IS READ OFF THE CLOSED RUN ROW AND NOT OFF THE ADAPTER'S
    # ANSWER.** `services.outcome_for` is *"the one place the outcome word is
    # chosen"* (`BR-INT-018`), so reading anything else here would be a second
    # opinion about whether a provider succeeded — and the two would disagree on
    # the day somebody widened one of them.
    #
    # ⚠ **AND `run.items` IS EMPTY ON AN APPROVAL BY DESIGN**: `finish_run`
    # stores only the items that did NOT succeed. So the branch below reads the
    # COUNTS, which are always populated, rather than an item list that is
    # legitimately absent on the happy path.
    items = list(run.items or ())
    first = items[0] if items else {}
    provider_text = (first or {}).get("provider_text") or run.provider_error or None
    if run.outcome == integration_models.OUTCOME_UNCONFIRMED:
        # ⚠ NOTHING IS WRITTEN IN `apps/payments` FROM HERE. TC-6.
        return ChargeOutcome(
            outcome=NO_ANSWER,
            key=str(key),
            provider_key=provider.provider_key,
            environment=provider.environment,
            amount=figure,
            currency=currency,
            provider_text=provider_text,
            run_id=str(run.pk),
            problems=(
                {
                    "code": "gateway_did_not_answer",
                    "br_ref": "BR-INT-018",
                    "detail": "the provider was asked and did not answer, so whether the money "
                    "moved is unknown. NO payment row was written — an unknown outcome is not a "
                    "zero (US-CWP-045 TC-6) — and the same key is carried back so a retry "
                    "presents it again and the debit is never taken twice (TC-7).",
                },
            ),
        )
    if run.outcome != integration_models.OUTCOME_SUCCEEDED or run.succeeded != 1:
        return ChargeOutcome(
            outcome=DECLINED,
            key=str(key),
            provider_key=provider.provider_key,
            environment=provider.environment,
            amount=figure,
            currency=currency,
            provider_text=provider_text,
            run_id=str(run.pk),
            problems=(
                {
                    "code": "gateway_declined",
                    "br_ref": "BR-INT-018",
                    "detail": "the provider answered and refused the debit. No payment row was "
                    "written and nothing was allocated; the customer's bills are exactly as they "
                    "were.",
                },
            ),
        )
    return ChargeOutcome(
        outcome=APPROVED,
        key=str(key),
        provider_key=provider.provider_key,
        environment=provider.environment,
        amount=figure,
        currency=currency,
        provider_text=provider_text,
        run_id=str(run.pk),
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE GUEST CHARGE — `US-CWP-004`, and the hole this module's own docstring
# recorded rather than stubbed
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE PREVIOUS LANE WAS RIGHT TO STOP AND ITS REASON IS WORTH KEEPING.**
# The docstring above says a stub *"would make that call site LOOK wired, which
# is hard-won law 2 pointed the wrong way"*, and names the exact missing piece:
# a bill number → account read that `billing_seam` did not publish. It now
# does, WITH the reasoning for its shape written into that file, and this is
# the function the contract was recorded for.
#
# **WHAT IS AND IS NOT NEW HERE.** Nothing below allocates, prices, rounds,
# posts to the ledger or decides what a bill owes. It resolves an account,
# checks the same guards the signed-in Pay control checks, asks `charge()` for
# one debit and — **only on an approval** — hands the result to
# `webhooks.settle_charge`, which is the SAME door a real processor's
# settlement comes through. That is the whole point of the door: the
# allocation, the balanced ledger pair, the receipt queue and the audit row are
# the existing tested ones, and none of it is rebuilt when a real vendor
# arrives.

#: Customers' published account read, resolved BY NAME like every other
#: cross-module fact this module needs (`autopay.is_enrolled`'s own idiom).
CUSTOMERS_MODULE = "customers"
ACCOUNT_QUERYSET_READ = "account_queryset"

#: `SEED_PAYMENT_METHODS`' code for a card. ⚠ **A CONSTANT AND NOT A
#: CLASSIFIER.** `BR-CWP-057` says a guest instrument is a token, a brand and a
#: last four — there is no `kind` on it — and `CWP-003` collects a card number,
#: an expiry and a security code and nothing else. Deriving a method from the
#: BRAND string would be a classifier nobody signed, on a money row that can
#: never be edited afterwards (hard rule 4). The day a bank-account guest path
#: lands it adds a field to the instrument, not an `if` here.
GUEST_METHOD_CODE = "card"


class GuestChargeRefused(PaymentRuleError):
    """The guest's card was not charged, and `outcome` says which kind of not.

    ⚠ **A RAISE RATHER THAN A RESULT, DELIBERATELY, AND ONLY ON THIS PATH.**
    `pay_now_seam.pay` answers a signed-in screen with a dict carrying an
    `outcome` word, because that screen renders a panel either way. The guest
    edge does not: it turns whatever comes back into a RECEIPT
    (`selectors.guest_payment_receipt`) and answers 201. So a non-approval that
    returned a dict would be one forgotten branch away from a receipt for money
    that never moved, and the type system would not care. Refusing loudly is the
    direction that fails closed (hard-won law 3).

    ⚠ **IT CARRIES NO SENTENCE FOR A CUSTOMER.** `apps/payments` does not write
    what a screen says — eleven catalogues do (B14 rule 35). What travels is a
    CODE the edge maps to its own key, plus the provider's own words for a
    person reading the log, which `BR-INT-034` keeps away from customer copy.
    """

    def __init__(
        self,
        message: str,
        *,
        outcome: str,
        key: str | None = None,
        held_reason: str | None = None,
        provider_text: str | None = None,
        br_ref: str | None = None,
        problems: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.outcome = outcome
        #: ⚠ TC-7 — carried back on EVERY refusal including the one that wrote
        #: nothing, because the retry needs it and the retry is the whole reason
        #: it was minted before the first request left.
        self.key = key
        self.held_reason = held_reason
        self.provider_text = provider_text
        self.problems = problems
        super().__init__(message, br_ref=br_ref)


#: The outcome word for *this bill cannot be paid here at all* — no processor
#: connected, or the account is under `BR-PAY-013`'s cash-only sanction. ONE
#: word for both, and `held_reason` carries which to the log and never to the
#: wire; see `charge_guest_bill` for why that is a disclosure decision.
HELD = "held"
#: The outcome word for *this number names no bill anybody may pay*.
NO_BILL = "no_bill"
#: ⛔ **THE WORST ONE: THE PROVIDER APPROVED AND WE COULD NOT RECORD IT.** The
#: money moved at the far end and `settle_charge` refused the payment under some
#: rule — a deactivated method code, a purpose whose linkage is missing, a
#: ledger that would not take the entry. It is NOT a decline and NOT a silence:
#: both of those mean nothing was taken.
#:
#: ⚠ **IT EXISTS BECAUSE THE FIRST DRAFT OF THIS FUNCTION RETURNED A RECEIPT
#: FOR IT.** `settle_charge` answers with `payment_id=None` on a refusal rather
#: than raising — deliberately, so the DELIVERY row stands and somebody can see
#: the money — and `recorded.payment_no or recorded.payment_id` is then `None`.
#: That reached `guest_payment_receipt` as `reference: None`: a 201, a receipt,
#: a blank reference, and a customer told they had paid. Found writing the
#: PostgreSQL cases, not by any gate.
NOT_RECORDED = "not_recorded"


def _cash_only(tenant_id: Any, account_id: Any) -> bool:
    """Is this account under `BR-PAY-013`'s privilege sanction?

    ⚠ **REFUSES RATHER THAN ANSWERING FALSE WHEN CUSTOMERS PUBLISHES NOTHING**,
    the posture `autopay.is_enrolled` already takes: *"they may use a card"* and
    *"we could not tell"* are different statements and only the first is safe to
    act on. On this path the unsafe direction would take a stranger's money
    against an account the utility has put on cash-only.
    """
    queryset = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            f"apps.{CUSTOMERS_MODULE}.selectors.{ACCOUNT_QUERYSET_READ} is not published, so "
            "whether this account is under the cash-only sanction cannot be read. A card is "
            "not charged on a guess (BR-PAY-013).",
            br_ref="BR-PAY-013",
        )
    row = (
        queryset().filter(tenant_id=tenant_id, pk=account_id).values("cash_only_no_autopay").first()
    )
    if row is None:
        raise PaymentRuleError(
            "the bill resolved to an account this tenant does not have. Nothing is charged.",
            br_ref="BR-TEN-003",
        )
    return bool(row["cash_only_no_autopay"])


def charge_guest_bill(
    tenant_id: Any = None,
    *,
    bill_number: Any,
    amount: Any,
    currency: str | None,
    instrument: dict[str, Any],
    receipt_email: str | None,
    channel: str,
    paid_by: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """One debit for somebody who is not signed in, and where it lands.

    The signature is the one this module's docstring recorded before the
    function existed, so the call site and its recorder did not move.

    ════════════════════════════════════════════════════════════════════════
    ⚠ THE ACCOUNT IS RESOLVED HERE, FROM THE DATABASE, AND NEVER PASSED IN
    ════════════════════════════════════════════════════════════════════════
    `billing_seam.account_for_bill_number` answers it, and that file records why
    the read lives there. What matters at this end is the direction: the caller
    is an **unauthenticated form**, so where a stranger's money lands is decided
    by the module that owns the money, from a tenant-scoped query, every time.

    ⚠ **AND THE BILL IT NAMES IS NOT A TARGET.** No `targets=` is passed to
    `record_payment`, so the money meets the account's OLDEST open bill first
    under `BR-PAY-001`, through the one allocator. On this story's own figures a
    guest paying `$142.18` against `BL-2608-0141` with a `$18.00` July bill
    still open settles July first and leaves `$124.18` on August — correct, and
    worth knowing, because the receipt's *against* line names the bill they were
    LOOKING at rather than the only bill the money met.

    ════════════════════════════════════════════════════════════════════════
    ⚠ ONE REFUSAL SENTENCE FOR EVERY HELD REASON — A DISCLOSURE DECISION
    ════════════════════════════════════════════════════════════════════════
    `held_reason` distinguishes *no processor connected* from *this account is
    cash-only*. **Only the first is safe to say out loud here.** The second is a
    fact about the CUSTOMER — `BR-PAY-013` is a sanction applied after bounced
    payments — and `BR-CWP-021` forbids telling a stranger holding the paper
    anything about the person, as plainly as it forbids their name. So both
    leave as the single `HELD` outcome, the specific code travels on the
    exception for the log, and the edge answers one sentence for both.

    ⚠ **THE SANCTION IS CHECKED AT ALL BECAUSE THE PUBLIC FORM WOULD OTHERWISE
    BE THE WAY ROUND IT.** `pay_now_seam` already holds the signed-in Pay
    control on `HELD_CASH_ONLY`; J12 step 6 says no rule ever auto-clears the
    flag, and the customer under it is the one person certain to know quick pay
    exists.

    ════════════════════════════════════════════════════════════════════════
    ⚠ NOTHING IS WRITTEN UNLESS THE PROVIDER APPROVED
    ════════════════════════════════════════════════════════════════════════
    A DECLINE and a TIMEOUT both return before `settle_charge` is reached, so
    there is no payment, no allocation, no journal line and no audit row — and
    the two are different words on the way out, because `BR-INT-018` says an
    unconfirmed run is not a green word and a decline is not a silence.
    `US-CWP-004` TC-7: *"a zero is a claim nobody can make."*

    ⚠ **AND THE KEY IS NEVER MINTED HERE.** It arrives from the caller, who
    minted it from the browser's per-visit token before the first request left
    (`guest_api._attempt_key`), so a retry after a timeout presents the same
    string: one debit at the provider (`Idempotency(source="request_key")`) and
    one payment here (`uq_payments_webhook_key`). A key minted inside this
    function would be different on every attempt and would dedupe nothing while
    looking like it did.

    ⚠ **`receipt_sent` IS FALSE, AND IT IS FALSE HONESTLY.** Nothing in this
    release dispatches a notification (`BR-NOT-013`); `record_payment` QUEUES a
    receipt to the ACCOUNT's own contacts under the tenant's election, which is
    a different address from the one a guest typed — `US-CWP-004` §4 is explicit
    that a guest may be a neighbour. Nothing sends to the typed address and this
    lane did not make it: writing an unverified address supplied by an anonymous
    caller into a notification row against somebody else's account is a
    disclosure decision, not a plumbing job. So the flag says what is true, the
    screen draws its held *Email receipt* control, and the gap is reported.
    """
    from apps.payments import billing_seam, webhooks as payments_webhooks

    tenant_id = tenant_id if tenant_id is not None else _tenant_id()
    figure = _as_money(amount)
    key = str(idempotency_key or "").strip()
    if not key:
        # The same refusal `charge()` makes, made EARLIER so that nothing is
        # resolved or read for a request that could not have been idempotent.
        raise PaymentRuleError(
            "a guest charge is asked for with the idempotency key the caller minted before "
            "the first attempt left (US-CWP-045 TC-7). Without it a retry after a timeout "
            "would take a second debit from somebody who has already paid (hard rule 6).",
            br_ref="BR-PAY-028",
        )

    owner = billing_seam.account_for_bill_number(bill_number)
    if owner is None:
        raise GuestChargeRefused(
            "that bill number names no bill this utility may take a payment against. An "
            "unknown number, a draft, a cancelled bill and another utility's number are one "
            "answer here on purpose (US-CWP-003 TC-2).",
            outcome=NO_BILL,
            key=key,
            br_ref="BR-CWP-019",
        )

    provider = active_provider(tenant_id)
    reason = held_reason(
        provider=provider,
        cash_only=_cash_only(tenant_id, owner.account_id),
        # A token arrived in the body or `_instrument` would already have
        # refused, so the guest always HAS a method — it is simply not a saved
        # one, which is what makes this path different from `pay_now_seam`.
        has_method=bool(str((instrument or {}).get("token") or "").strip()),
        # Nobody is signed in, so there is no permission to fail. `BR-CWP-025`'s
        # bill-number-plus-postcode pair is what stands in its place, and the
        # edge has already re-proved it against the same counter step 1 uses.
        may_pay=True,
    )
    if reason is not None or provider is None:
        raise GuestChargeRefused(
            "this bill cannot be paid by card here. The reason is on `held_reason` for the "
            "log and is deliberately NOT on the wire: one of the two reasons is a fact about "
            "the customer (BR-PAY-013's cash-only sanction) and BR-CWP-021 does not let a "
            "stranger holding the paper be told it.",
            outcome=HELD,
            key=key,
            held_reason=reason or HELD_NO_PROVIDER,
            br_ref="BR-CWP-056",
        )

    # ⚠ **THE BILL'S OWN CURRENCY WINS OVER THE CALLER'S.** Hard rule 2 — a
    # currency rides WITH the amount — and on a public form the caller's half of
    # the request is a stranger's. They agree today (the edge reads the same
    # column); when they cannot, the database is the one that decides.
    money_currency = owner.currency or currency
    if money_currency is None:
        raise PaymentRuleError(
            f"bill {owner.number} states no currency and the caller named none, so the "
            "figure has no CHAR(3) code to travel with (hard rule 2). Nothing is charged: a "
            "bare number is not money.",
            br_ref="BR-PAY-002",
        )

    answer = charge(
        provider=provider,
        key=key,
        amount=figure,
        currency=money_currency,
        token=str((instrument or {}).get("token") or ""),
    )
    if answer.wrote_nothing:
        # ⚠ NOTHING IN `apps/payments` HAS BEEN WRITTEN AT THIS POINT AND
        # NOTHING WILL BE. `integrations` has its own run row, which is that
        # module's audit of what it was asked to do — see `charge()`.
        raise GuestChargeRefused(
            "the provider did not approve the debit."
            if answer.outcome == DECLINED
            else "the provider was asked and did not answer, so whether the money moved is "
            "unknown. No payment row was written — an unknown outcome is not a zero.",
            outcome=answer.outcome,
            key=answer.key,
            provider_text=answer.provider_text,
            br_ref="BR-INT-018",
            problems=answer.problems,
        )

    recorded = payments_webhooks.settle_charge(
        provider=answer.provider_key,
        key=key,
        body={
            "account_id": str(owner.account_id),
            "amount": str(figure),
            "currency": money_currency,
            # BR-PAY-021 — both moments, and an approved charge is money that
            # has arrived, so the two are the same instant. The clock is the
            # EDGE's rather than a rule's: `payments` reads none (`G6`).
            "posted_at": _now().isoformat(),
            "cleared_at": _now().isoformat(),
            "method": GUEST_METHOD_CODE,
            "reference": key,
        },
        received_at=_now(),
        # Hard rule 7's WHO on the one money path in the product with no `User`
        # behind it. `actor_user_id` stays NULL and the payload NAMES the form:
        # `BR-CWP-004` keeps portal people and staff users apart on purpose, and
        # a guest has neither a customer id nor a session to name — so the two
        # facts that DO exist travel instead, and a row nobody can explain a
        # year later is what this prevents.
        portal_actor={
            "portal_customer_id": None,
            "portal_session_id": None,
            "channel": channel,
            "portal_paid_by": paid_by,
            "portal_bill_number": owner.number,
        },
    )
    if recorded.payment_id is None:
        # ⛔ THE PROVIDER TOOK THE MONEY AND WE DID NOT RECORD IT. See
        # `NOT_RECORDED`. The delivery row STANDS and carries the refusal, which
        # is what lets a person find the money; what must not happen is a
        # receipt with a blank reference telling the customer they have paid.
        raise GuestChargeRefused(
            f"the provider approved the debit and the payment could not be recorded: "
            f"{recorded.outcome or 'no reason was stated'}. The delivery row stands so the "
            "money can be found, and NO receipt is answered — a reference nobody can quote "
            "is worse than a refusal.",
            outcome=NOT_RECORDED,
            key=key,
            br_ref="BR-PAY-003",
            problems=tuple(dict(one) for one in recorded.problems),
        )
    return {
        # `PMT-26-…` from the tenant series — a HUMAN reference somebody can
        # read down a telephone, never a row id (B14 rule 31).
        "reference": recorded.payment_no or recorded.payment_id,
        "amount": recorded.amount,
        "currency": recorded.currency,
        "paid_at": _now(),
        # `BR-CWP-057` — a brand and a last four are what a stored instrument
        # shows a person. The token is NOT here: a guest screen has no use for
        # it and a response body carrying it would put it in a browser, a proxy
        # log and a screenshot.
        "method_brand": (instrument or {}).get("brand"),
        "method_last_four": (instrument or {}).get("last_four"),
        # See the docstring: nothing dispatches in this release, so this is
        # FALSE rather than "an address was typed".
        "receipt_sent": False,
        # Carried for a caller that wants to say something truthful about what
        # could not be answered — `guest_payment_receipt` drops it, correctly,
        # because a guest receipt is `BR-CWP-028`'s six keys and nothing else.
        "problems": [dict(one) for one in recorded.problems],
    }


def charge_guest_fee(
    tenant_id: Any = None,
    *,
    amount: Any,
    currency: str | None,
    instrument: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING — `CR-191-BRC10` (PO 2026-10-23): one debit for a
    portal APPLICATION FEE, through the SAME `charge()` quick pay uses.

    PO, verbatim: *"if there is a application or service fee then consumer will
    have to pay it online; they can't say pay later"*, and *"3A"* — the card on
    the same screen, through the portal's existing online payment.

    ⚠ **NOT A SECOND GATEWAY PATH.** The provider is `active_provider`, the
    held rule is `held_reason`, the debit is `charge()` and the key is the
    caller's, minted before the first attempt left — every line of the guest
    bill path above except its LAST step. That step is `settle_charge`, which
    writes a `payments` row against an ACCOUNT, and an applicant has none
    (*"no application fee is ever carried to an account"*, 2026-09-23). So
    **this writes nothing in `apps/payments`**; the caller records the money as
    a counter receipt in the same transaction as the request it pays for
    (`counter_receipts.record_counter_receipt`), which is where every
    application fee already lives.

    ⚠ **A REFUSAL RAISES `GuestChargeRefused`, EXACTLY AS THE BILL PATH DOES**,
    so the edge maps it through the same `_refusal_for` and a stranger reads the
    same sentence for a declined card on either form. `NO_BILL` cannot occur
    here; the cash-only sanction cannot either (there is no account to carry
    it).

    **Worked:** `$10.00`, a sandbox set to approve, key `appfee:…:<attempt>` →
    `{reference: "appfee:…", amount: 10.0000, currency: "USD", method_brand,
    method_last_four, environment: "sandbox"}`; the same key again → the same
    answer and, at a real provider, no second debit. Set to `decline` →
    `GuestChargeRefused(outcome=DECLINED)` and nothing written anywhere but
    integrations' own run row.
    """
    tenant_id = tenant_id if tenant_id is not None else _tenant_id()
    figure = _as_money(amount)
    key = str(idempotency_key or "").strip()
    if not key:
        raise PaymentRuleError(
            "an application-fee charge is asked for with the idempotency key the caller minted "
            "before the first attempt left (US-CWP-045 TC-7, hard rule 6).",
            br_ref="BR-PAY-028",
        )
    if not currency:
        raise PaymentRuleError(
            "an application fee with no CHAR(3) currency is a bare number, not money (hard "
            "rule 2). Nothing is charged.",
            br_ref="BR-PAY-002",
        )
    token = str((instrument or {}).get("token") or "").strip()
    provider = active_provider(tenant_id)
    reason = held_reason(provider=provider, cash_only=False, has_method=bool(token), may_pay=True)
    if reason is not None or provider is None:
        raise GuestChargeRefused(
            "this application fee cannot be paid by card here.",
            outcome=HELD,
            key=key,
            held_reason=reason or HELD_NO_PROVIDER,
            br_ref="BR-CWP-056",
        )
    answer = charge(provider=provider, key=key, amount=figure, currency=currency, token=token)
    if answer.wrote_nothing:
        raise GuestChargeRefused(
            "the provider did not approve the debit."
            if answer.outcome == DECLINED
            else "the provider was asked and did not answer, so whether the money moved is "
            "unknown. Nothing was written — an unknown outcome is not a zero.",
            outcome=answer.outcome,
            key=answer.key,
            provider_text=answer.provider_text,
            br_ref="BR-INT-018",
            problems=answer.problems,
        )
    return {
        "reference": answer.key,
        "amount": figure,
        "currency": currency,
        "method_brand": (instrument or {}).get("brand"),
        "method_last_four": (instrument or {}).get("last_four"),
        "environment": answer.environment,
        "run_id": answer.run_id,
    }


def card_payments_available(tenant_id: Any = None) -> bool:
    """`CR-191-BRC10` — can this utility take a card at all? A read, so the
    portal's last step can hold its button WITH its reason (`BR-CWP-056`)
    rather than offer a commit that can only be refused."""
    return active_provider(tenant_id) is not None


def _now() -> Any:
    """The one clock read on this path, and it is the EDGE's rather than a
    rule's — `payments` reads no clock (`BR-TEN-043`, `G6`). An approved charge
    is money that arrived now; the provider's own settlement callback will carry
    its own moments when it comes, and it will be recognised as a duplicate."""
    from django.utils import timezone

    return timezone.now()


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's published callable, or None while it has none.

    getattr-at-call-time, the idiom every seam in this module uses: no import
    statement binds `payments` to another module's internals (B1/BR-TEN-013,
    gate `G6`), and the moment a lane publishes its function this file starts
    using it with no re-wiring.
    """
    from importlib import import_module

    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def secrets_for(provider: PaymentsProvider) -> dict[str, str]:
    """The connection's credentials, through `integrations`' ONE reader.

    Exposed so a caller that needs them holds them for the length of one call
    and drops them (`BR-INT-003`). Nothing in `apps/payments` stores one.
    """
    return integration_services.credential_secrets(provider.connection)


def _as_money(value: Any) -> Decimal:
    """A positive figure at four decimals. ⚠ **A float is REFUSED, not converted.**

    CLAUDE.md rule 2 at the boundary, the same refusal `webhooks._amount` makes
    for an inbound figure — because a `float` that arrived from JSON has already
    lost the cent it was going to lose.
    """
    if isinstance(value, float):
        raise PaymentRuleError(
            f"an amount of {value!r} arrived as a float. Money is stored to four decimals and "
            "never as binary (CLAUDE.md hard rule 2) — refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    try:
        figure = Decimal(str(value))
    except Exception as bad:  # noqa: BLE001 — every malformed figure answers the same way
        raise PaymentRuleError(
            f"an amount of {value!r} is not a decimal figure.", br_ref="BR-PAY-002"
        ) from bad
    if figure <= ZERO:
        raise PaymentRuleError(
            f"an amount of {figure} cannot be charged. A payment carries a positive figure; "
            "money going the other way is a refund and a different path (BR-PAY-013).",
            br_ref="BR-PAY-002",
        )
    return figure.quantize(FOUR_DP)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-045 (EP-CWP-09) · US-CWP-006 (EP-CWP-02) · decision log
#         2026-09-05 "Payment providers are integrations, and beta ships behind
#         a test one" · BR-INT-037 · BR-INT-018 · BR-CWP-056 · BR-CWP-058 ·
#         CLAUDE.md hard rules 1, 2, 4, 6, 7 · hard-won law 14
# generated: 2026-09-05 by the CR-068 phase 5 lane B (the money path) · AMENDED
#         2026-09-05 by the CR-068 lane F (the guest charge): `charge_guest_bill`
#         is written, and the docstring section that recorded its absence now
#         records how it was closed. The signed-in path (`pay_now_seam`) is
#         untouched, `charge()` is untouched, and no figure moved.
# checklist: A✔ B✔ C✔ D✔ E✔(CWP-038 · CWP-003 for the guest half) F✔ G✔
#         H=deferred(PO 2026-08-09)
# exceptions:
#   E1 a row in 12-governance/09-human-review-ledger.md is OWED — this is a 🔒
#      path (idempotency keys) — and that file is outside this lane's write
#      scope. What a reviewer is owed is REPORTED with its worked figures.
#   E2 no refund path. `US-CWP-049` owns it and it is a different operation on
#      the same manifest; a stub here would be a door (US-CWP-051 TC-10's
#      lesson).
#   E3 [2026-09-05] THE GUEST'S TYPED RECEIPT ADDRESS GOES NOWHERE, and
#      `receipt_sent` says so rather than reporting a send that never happened.
#      Writing an unverified address supplied by an anonymous caller into a
#      notification row against somebody else's account is a DISCLOSURE
#      decision, not a plumbing job — `US-CWP-004` §4 is explicit that a guest
#      may be a neighbour. REPORTED rather than decided by this lane.
#   E4 [2026-09-05] A LOST RESPONSE ANSWERS "there is nothing to pay" ON THE
#      RETRY. Hard rule 6 holds — one payment every way in — but the retry is
#      stopped by the payability re-read rather than handed the receipt it
#      already earned. Turning that into a replay means moving the idempotency
#      lookup ahead of the re-read, which is a guard-order change on a money
#      edge and belongs to its own story. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
