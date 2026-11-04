# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5, tasks `P5.1` (the
#           settlement ingest), `P5.2` (the fee posting) and `P5.3`
#           (idempotency on a repeat payout). Drawing: p024.
# Story:    no story — the two Settlements screens are `P5.7`, another lane.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#           Decimal, never a float; rounded at finalisation) · hard rule 4 (a
#           payment row is append-only — and `P5.6`'s pointer collides with it,
#           `OQ-PAY-12608`) · hard rule 5 (ONLY the ledger posting service
#           writes journal lines — nothing here composes one) · hard rule 6
#           (the repeat-payout key) · hard rule 7 (every money action writes
#           `audit_log`) · hard-won law 14 (a SAVEPOINT per member, proved on
#           PostgreSQL) · BR-PAY-019 (every difference carries a reason AND an
#           account) · BR-INT-037 (no provider is named here)
# Tests:    06-backend/tests/test_cr139_p5_settlements.py ·
#           06-backend/tests/test_cr139_p5_rls_pg.py (PostgreSQL only) ·
#           10-scripts/cr139_p5_6_pointer_freeze_proof.py (the trigger refusal)
# Impacts:  apps/payments/settlement_models.py (the two tables) ·
#           apps/payments/reconciliation.derive_processor_fee (the sibling this
#           deliberately does NOT duplicate) · apps/payments/ledger_seam.py
#           (the one door to the books, unchanged by this file)
# ───────────────────────────────────────────────────────
"""A payout arrives, and its members are written — **the third source, closed.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — idempotency keys and money rounding are on
CLAUDE.md's 🔒 list. AI-authored 2026-09-23 under the PO ruling of 2026-08-09; a
row in `12-governance/09-human-review-ledger.md` says in plain English, with a
figure, what a reviewer is owed.

════════════════════════════════════════════════════════════════════════════
⚠ THE MOST IMPORTANT THING IN THIS FILE IS WHAT IT DOES **NOT** DO
════════════════════════════════════════════════════════════════════════════
**`P5.2`'s balanced pair already exists, is shipped, and was ruled by the
Product Owner thirteen months' worth of decisions ago.** Measuring that before
writing a line is the difference between this phase adding a capability and this
phase adding a second answer to a question the product already answers.

  * **`OQ-144`, CLOSED 2026-08-11** — PO, verbatim: *"Match net with a fee
    line"*.
  * **`OQ-160`, CLOSED 2026-08-12** — the fee **may be DERIVED from the
    shortfall**.

`reconciliation.reconcile_batch` → `ledger_seam.post_batch_reconciled` writes
exactly the entry `P5.2` describes, on the PO's own worked card day:

    DR 1000 Cash               4,972.90   ← what the bank actually credited
    DR 6800 Bank fees            147.50   ← the processor's fee, ITS OWN LINE
    CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

**The customer paid the gross and the fee is an expense — that is already
true.** A $100.00 card payment with a $2.90 fee is a $100.00 `payments` row and
$2.90 in `6800 Bank fees`; nothing in this product has ever written $97.10.

So **a settlement that posted cash of its own would post the same money twice**
— the drawing's own *"two answers to one question"* risk landing on the money
path — and this file therefore contains **no `post_` function, no journal line
and no import of `ledger_seam` at all**. Hard rule 5 is kept by having nothing
to keep it about.

════════════════════════════════════════════════════════════════════════════
⚠ SO WHAT DOES `P5.2` ACTUALLY ADD? THE FEE STOPS BEING A GUESS
════════════════════════════════════════════════════════════════════════════
`OQ-160`'s own text records the hazard the PO accepted when they chose
derivation, in the decision log's words:

    *"whether the net match requires the fee to be known in advance from the
    processor's settlement file, or is derived from the difference (which would
    silently absorb a genuine shortfall into 'fees'). That distinction decides
    whether a $10 customer chargeback hides inside a fee line."*

They ruled for derivation **because the product did not ingest a settlement
file**. Phase 5 is that ingestion, and `OQ-160`'s option (c) — *"taken from an
ingested processor settlement file, with (b) as the fallback"* — becomes
available for the first time.

`stated_processor_fee()` below is that option, and it is deliberately **the same
door** a human's explanation and `derive_processor_fee`'s guess already go
through: it returns a `ResolutionInput`, it posts nothing, and `reconcile_batch`
checks it against the difference exactly as before. **What it adds is the one
refusal derivation cannot make** — when the provider says it kept **$137.50**
and the bank is **$147.50** short, the remaining **$10.00** is a real question
about a real customer, and this refuses rather than calling it a fee.

    derived : bank 4,972.90 − recorded 5,120.40 = −147.50 → "fee 147.50" ✓ ties
    stated  : provider kept 137.50, gap is 147.50        → REFUSED, $10.00 unexplained

**That $10.00 is the whole value of phase 5's money half.** Under derivation the
chargeback reconciles clean, the customer's bill stays paid, and nothing ever
re-opens it.

════════════════════════════════════════════════════════════════════════════
⚠ `P5.6`'s POINTER IS DROPPED — `OQ-PAY-12608` CLOSED 2026-09-24, OPTION (b)
════════════════════════════════════════════════════════════════════════════
**PO, verbatim: *"p7 (b) — nothing is lost, and the payment-row lock stays
exactly as it is"*.** `payments.settlement_id` is removed by `payments/0044`.
The rest of this section is WHY, kept because a reader who meets `P5.6` in the
blueprint needs to find out where the column went — and because the finding
that produced the question is the reason the ruling went the way it did.

⛔ **SUPERSEDED — this section opened *"THE POINTER CANNOT BE STAMPED"* and
described a live column.** It reads in the past tense now.

**The column existed and nothing here ever wrote it.** The immutability trigger
compares a payment's WHOLE ROW minus a short allow list and says so in
`payments/0005`'s own comment: *"a column added later is frozen the day it is
created."*

⚠ **AND IT IS FROZEN IN EVERY STATUS, NOT ONLY AFTER CLEARING — WHICH IS
STRONGER THAN THIS PARAGRAPH FIRST CLAIMED, AND THE RUN IS WHAT CORRECTED IT.**
The draft said *a payout arrives after clearing, so every stamp is an UPDATE on
a frozen row*; that is true and it is not the whole fact. The trigger has been
amended twice since `payments/0005` (`US-PAY-009`'s journal stamp, `CR-059`
CS-34's three correction columns), and its **processing** branch now names its
mutable set explicitly too — *only status and cleared_at … plus the cheque
number, memo and tender*. So there is no earlier moment at which a stamp would
work either; the column is settable only at INSERT, and a payout by definition
arrives after the row exists. **Reading the migration would have got this
wrong, which is why it is a script and not an argument.**

⚠ **AND THE SUITE CANNOT SHOW YOU THIS.** That trigger is installed by a
`RunPython` that returns early on any non-PostgreSQL vendor, and
`config/settings/test.py` hardcodes in-memory SQLite. **The version that stamps
passes every test on every machine and fails the first real payout.** It is
hard-won law 14's exact shape, one table over from the one law 14 is written
about, and it is proved red on PostgreSQL 16.13 by
`10-scripts/cr139_p5_6_pointer_freeze_proof.py`.

**Widening the allow list was not a lane's call.** `CLAUDE.md` hard rule 4 is
explicit about its own narrowing: *"`payments/0014` is the ONLY place the
database's allow list moves; widening it anywhere else is a new ruling, not this
one."* So `OQ-PAY-12608` was minted rather than guessed, with three options —
widen the lock write-once · drop the column · leave it frozen and unwritten —
and **the PO chose to drop it. The lock did not move.**

**NOTHING IS LOST, AND THAT IS A FACT RATHER THAN A REASSURANCE.**
`settlement_members` is the record, and `awaiting_settlement_filter()` below
answers *"is this payment awaiting settlement?"* from it — which it always did,
because the pointer was never readable either. So **no read in this product
changed behaviour on the day the column went.** The pointer was a
denormalisation for the list screen's convenience, never the fact, and the
phase's own acceptance sentence — *"a supervisor opens last night's payout and
sees the forty-six payments inside it"* — was met in full before it and is met
in full after it.

⚠ **THERE WAS NEVER A STUB FUNCTION FOR IT, AND THAT WAS DELIBERATE.**
`apps/payments/gateway.py` records the precedent from 2026-09-05: a lane
stopped, and *"what it correctly refused to do"* was write a function that would
always refuse, **because a function that exists and always refuses makes the
call site LOOK wired** — hard-won law 2 pointing the wrong way. The absence is
declared as data on every result instead (`SETTLEMENT_UNAVAILABLE`), which is
the posture `WEBHOOK_UNAVAILABLE` and `DOCUMENT_UNAVAILABLE` already keep.

════════════════════════════════════════════════════════════════════════════
⚠ HARD-WON LAW 14 — THE SAVEPOINT, AND WHY IT IS THE PHASE'S NAMED RISK
════════════════════════════════════════════════════════════════════════════
The blueprint's p025 risk table names it against this phase by name: *"A Load
writes hundreds of payments in one transaction, and on PostgreSQL a single
failed statement poisons the whole transaction."* A payout has **forty-six**
members in the worked case and can have thousands.

**`try: … except IntegrityError: continue` DOES NOT WORK on PostgreSQL.** Once
any statement errors the transaction is aborted; every later query raises
`InFailedSqlTransaction` and the work is lost at COMMIT — so ONE member naming a
payment we do not hold would lose the other forty-five AND the settlement row.
Each member is therefore written inside a nested `transaction.atomic()`, which
is a SAVEPOINT. **It is not the tidy option, it is the only one**, and this
paragraph exists so nobody simplifies it away.

════════════════════════════════════════════════════════════════════════════
⚠ TWO GUARDS, CATCHING TWO DIFFERENT FACTS (`P5.3`, hard rule 6)
════════════════════════════════════════════════════════════════════════════
  1. **`_existing_payout`** — *has this PAYOUT been seen?* `(tenant, provider,
     code)`, one SELECT, before any write and before any arithmetic.
  2. **`uq_settlements_provider_code`** — the database half, which catches the
     race the SELECT cannot close.

**Neither is trusted because the other exists** (`DEF-058`'s lesson, which
`webhooks.py` already keeps): guard 1 is switched off in a test and guard 2 must
still hold the line, and the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from core import audit as core_audit
from core import errors
from core import money
from core import tenancy as core_tenancy

from apps.payments import models, settlement_models
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: EP-PAY-01 §5's `<entity>.<verb>` shape, so a trail can be filtered for
#: *"money a provider paid us"* without reading a payload.
AUDIT_PAYOUT_INGESTED = "settlement.ingested"

#: The reason code a stated fee carries into `reconcile_batch`. **The same
#: string `derive_processor_fee` uses**, on purpose: a finance report grouping
#: differences by reason must not split one kind of money across two words
#: because of where the figure came from. Where it came from is the NOTE's job.
REASON_PROCESSOR_FEE = "processor_fee"

#: The refusal reasons a member can carry, as CODES a screen groups on rather
#: than prose it parses — the discipline every `problems[]` row in this module
#: keeps.
MEMBER_PAYMENT_NOT_FOUND = "payment_not_in_this_product"
MEMBER_GROSS_DISAGREES = "member_gross_is_not_the_payments_amount"
MEMBER_ALREADY_PAID_OUT = "payment_is_already_in_another_payout"


#: What this path does NOT do, on every result — the `WEBHOOK_UNAVAILABLE`
#: posture. A caller must not have to infer an absence and a reviewer must not
#: have to take a docstring's word for one (hard-won law 1).
SETTLEMENT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_payment_row_is_stamped_with_its_payout",
        "br_ref": "CLAUDE.md hard rule 4 · OQ-PAY-12608",
        "detail": "A payment row carries no pointer to its payout, BY RULING. The blueprint "
        "asked for `payments.settlement_id` and it was built; nothing could ever write it, "
        "because the immutability trigger freezes every column of a payment except a short "
        "allow list and its own comment says 'a column added later is frozen the day it is "
        "created' — so it was settable only at INSERT, and a payout arrives after the row "
        "exists. Hard rule 4 says widening that allow list is a new PO ruling; the PO was "
        "shown the choice on 2026-09-24 and DROPPED THE COLUMN instead (OQ-PAY-12608, "
        "option (b), `payments/0044`), leaving the payment-row lock exactly as it was. "
        "NOTHING IS LOST: `settlement_members` is the record, "
        "`uq_settlement_members_payment` carries the one-payout-per-payment rule with the "
        "referential integrity the column never had, and `awaiting_settlement_filter()` "
        "answers the third state from it — as it always did, because the pointer was never "
        "readable either.",
    },
    {
        "code": "no_ledger_entry_is_written_here",
        "br_ref": "CLAUDE.md hard rule 5 · OQ-144 · OQ-160",
        "detail": "ingesting a payout posts NOTHING to the books, and that is correct rather "
        "than missing. The balanced pair for a card day is already written by "
        "`reconciliation.reconcile_batch` — DR 1000 Cash net, DR 6800 Bank fees, CR what the "
        "receipts debited — under the PO's rulings of 2026-08-11 and 2026-08-12. A second "
        "posting path would post the same money twice. What phase 5 adds is "
        "`stated_processor_fee()`: the fee stops being derived from the gap and starts being "
        "the figure the provider stated, which is the only way a chargeback hiding inside a "
        "fee line can ever be seen.",
    },
    {
        "code": "no_bank_line_is_matched_here",
        "br_ref": "BR-PAY-019 · OQ-161",
        "detail": "a payout is ingested with `status='received'` and no `bank_line_id`. "
        "Identifying which bank credit it arrived as is the bank-rec path's job and its "
        "screen's; this writes the record the match will be made against. Many-to-one "
        "matching already exists (OQ-161, PO 2026-08-12).",
    },
)


@dataclass(frozen=True)
class PayoutMember:
    """One line of a payout message: a provider's charge reference and its money.

    `reference` is the PROVIDER'S id for that charge — the same string their
    settlement callback carried — which is what makes the payment findable here
    without this module knowing anything about the vendor.
    """

    reference: str
    gross: Decimal
    fee: Decimal


@dataclass(frozen=True)
class IngestedPayout:
    """What one payout message did — and, on `problems`, what it could not do."""

    settlement_id: str
    provider: str
    code: str
    status: str
    created: bool
    member_count: int
    gross: Decimal
    fees: Decimal
    net: Decimal
    currency: str
    unresolved: tuple[dict[str, Any], ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default=SETTLEMENT_UNAVAILABLE)


def _tenant_id() -> Any:
    """CLAUDE.md hard rule 1 — nothing touches a tenant table without it set.

    ⚠ **AN UNSET `app.tenant_id` DOES NOT RAISE IN THE DATABASE, IT MATCHES
    NOTHING AND REPORTS SUCCESS.** This branch's own finding: a lane stamped
    **0 of 74 payments** and was told it had worked. So the refusal is here, at
    the top, before any query — the policy is the backstop, never the check.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _decimal(value: Any, *, what: str) -> Decimal:
    """Money is a `Decimal` or it is refused — never coerced (hard rule 2).

    A `float` that arrived from a provider's JSON is already wrong before it
    gets here: `0.1 + 0.2` is not `0.3` in binary floating point, and a payout
    is a sum of hundreds of amounts. Converting it would launder the error into
    something that looks like money.
    """
    if not isinstance(value, Decimal):
        raise PaymentRuleError(
            f"{what} {value!r} is not a Decimal — money is NUMERIC and never a float "
            "(CLAUDE.md hard rule 2). Refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    return value


def _existing_payout(tenant_id: Any, provider: str, code: str) -> Any:
    """GUARD 1 — *has this PAYOUT been seen?* The cheap pre-write half.

    `uq_settlements_provider_code` is the database half. This is the lookup that
    makes a redelivery cost ONE SELECT, open no transaction and run no
    arithmetic — and it runs before every other check, because a retry must be
    recognised whatever else is true of it.
    """
    return settlement_models.Settlement.objects.filter(
        tenant_id=tenant_id, provider=provider, code=code
    ).first()


def _replayed(row: Any) -> IngestedPayout:
    """The no-op answer for a payout this tenant has already ingested.

    `created=False` is the whole signal. It is not an error: a provider
    redelivering is a provider behaving correctly, and answering with a red
    failure for a message that was already handled teaches an operator to retry
    until something breaks.
    """
    return IngestedPayout(
        settlement_id=str(row.pk),
        provider=row.provider,
        code=row.code,
        status=row.status,
        created=False,
        member_count=row.members.count(),
        gross=row.gross,
        fees=row.fees,
        net=row.net,
        currency=row.currency,
    )


def _check_the_providers_arithmetic(
    *, gross: Decimal, fees: Decimal, net: Decimal, members: tuple[PayoutMember, ...]
) -> None:
    """Four refusals, and each one is a different thing a provider can get wrong.

    ⚠ **NOTHING HERE IS RE-DERIVED TO MAKE IT FIT.** The temptation is to
    compute `net = gross - fees` ourselves and carry on. That would make the
    first check unfailable — which is `OQ-160`'s recorded hazard exactly: *a
    figure derived to close a gap can never disagree with anything.*
    """
    if gross - fees != net:
        raise PaymentRuleError(
            f"the payout does not tie: gross {money.finalize(gross)} − fees "
            f"{money.finalize(fees)} = {money.finalize(gross - fees)}, and it states a net of "
            f"{money.finalize(net)}. It is refused rather than recomputed — a net we worked "
            "out ourselves would agree with us by construction and would hide whatever the "
            "provider actually got wrong.",
            br_ref="BR-PAY-019",
        )
    if fees < ZERO:
        raise PaymentRuleError(
            f"the payout states fees of {money.finalize(fees)}. A fee is what the provider "
            "KEPT, so it is positive and it makes their credit smaller; a negative one would "
            "read as an addition and would put a negative expense in front of whoever posts "
            "it. Money the provider GAVE us beyond the payout is a different fact with a "
            "different reason.",
            br_ref="BR-PAY-019",
        )
    if not members:
        raise PaymentRuleError(
            "the payout names no members. A bank credit with nothing inside it cannot be "
            "tied to any payment, which is the one thing this record exists to do — so it "
            "is refused rather than stored as an empty payout somebody has to explain later.",
            br_ref="BR-PAY-019",
        )
    member_gross = sum((one.gross for one in members), ZERO)
    member_fees = sum((one.fee for one in members), ZERO)
    if member_gross != gross:
        raise PaymentRuleError(
            f"the payout states a gross of {money.finalize(gross)} and its "
            f"{len(members)} members sum to {money.finalize(member_gross)}. The difference is "
            f"{money.finalize(gross - member_gross)} and it is refused: a payout whose parts "
            "do not foot to its total is a payout one of whose halves is wrong, and storing "
            "it would put that disagreement in the books.",
            br_ref="BR-PAY-019",
        )
    if member_fees != fees:
        raise PaymentRuleError(
            f"the payout states fees of {money.finalize(fees)} and its per-payment fees sum "
            f"to {money.finalize(member_fees)}. ⚠ THIS IS THE CHECK THAT MAKES A STATED FEE "
            "WORTH HAVING: if the two halves may disagree, the stated total is just another "
            "guess and `stated_processor_fee` is no better than deriving it from the gap "
            "(OQ-160).",
            br_ref="BR-PAY-019",
        )


def _payment_for(tenant_id: Any, provider: str, reference: str) -> Any:
    """The payment a member names, found by the key the webhook path composed.

    `webhook_key` is `webhook|<provider>:<event_id>` — see
    `idempotency.inbound_payment_key` and `webhooks._record`, which is the ONE
    place that string is built for an inbound payment. Re-composing it here
    rather than matching on `confirmation` is deliberate: `confirmation` is a
    free-text column a clerk may correct (`POST /payments/{id}/correct-reference`
    moves exactly that column), and a join that a correction can break is a join
    that will silently stop matching one day.
    """
    key = f"webhook|{provider}:{reference}"
    return models.Payment.objects.filter(tenant_id=tenant_id, webhook_key=key).first()


def ingest_payout(
    *,
    provider: str,
    code: str,
    paid_out_at: datetime,
    gross: Decimal,
    fees: Decimal,
    net: Decimal,
    members: tuple[PayoutMember, ...],
    currency: str = "USD",
    actor: Any = None,
) -> IngestedPayout:
    """`P5.1` — *"A payout arrives, its members are written."*

    The outcome sentence is *"Being paid out is a second message, and it is
    handled"*, and the *second* is the load-bearing word. The **first** message
    is the one `webhooks.py` already handles: a charge settled, one payment.
    This is the one that says *and here is the bank credit that carried
    forty-six of them.*

    ⚠ **`provider` IS A `provider_key` STRING AND IS NEVER COMPARED TO A
    LITERAL HERE.** PO ruling 2026-09-05, verbatim: *"we will have multiple
    payment providers integrated using integration module. For given utility we
    will activate 1 or 2."* Which processor this is belongs to the tenant's
    integration connection; `G77` fails the merge on a `provider_key ==`
    comparison outside `adapters/` and `manifests/`, and `BR-INT-037` is the
    reason — *"every time such integration comes we dont want to change our
    integration framework"*. `P5.9`'s adapter is what turns a vendor's own
    payload shape into the arguments above.

    ⚠ **A MEMBER THIS PRODUCT DOES NOT HOLD IS RECORDED, NOT RAISED.** A payout
    can legitimately contain a charge taken before this utility went live, or
    one whose webhook never arrived. Those land in `unresolved` with a code, the
    payout is still written, and somebody can see them — because the alternative
    is a payout that refuses whole and a supervisor with no record of a bank
    credit that is really in their account.
    """
    tenant_id = _tenant_id()
    provider = (provider or "").strip()
    code = (code or "").strip()
    if not provider or not code:
        raise PaymentRuleError(
            f"a payout needs both a provider and its own reference (got {provider!r}, "
            f"{code!r}). Those two ARE the idempotency key (hard rule 6), so a blank half "
            "would make every payout from that provider the same payout and the second one "
            "of the day would be swallowed as a redelivery of the first.",
            br_ref="BR-PAY-028",
        )

    # ── GUARD 1 · before any arithmetic and any write ───────────────────────
    already = _existing_payout(tenant_id, provider, code)
    if already is not None:
        return _replayed(already)

    gross = _decimal(gross, what="the payout gross")
    fees = _decimal(fees, what="the payout fees")
    net = _decimal(net, what="the payout net")
    for one in members:
        _decimal(one.gross, what=f"member {one.reference}'s gross")
        _decimal(one.fee, what=f"member {one.reference}'s fee")
    _check_the_providers_arithmetic(gross=gross, fees=fees, net=net, members=tuple(members))

    try:
        with transaction.atomic():
            settlement = settlement_models.Settlement.objects.create(
                tenant_id=tenant_id,
                provider=provider,
                code=code,
                paid_out_at=paid_out_at,
                gross=gross,
                fees=fees,
                net=net,
                currency=currency,
                status=settlement_models.SETTLEMENT_RECEIVED,
            )
            # Hard rule 7, INSIDE the transaction. A provider has no user, so
            # the JOB is the actor (BR-AUD-003) — and a bank credit that
            # appeared with no record of how is exactly the outcome rule 7
            # exists to prevent.
            core_audit.money_action(
                actor,
                AUDIT_PAYOUT_INGESTED,
                "settlement",
                str(settlement.pk),
                after={
                    "provider": provider,
                    "code": code,
                    "paid_out_at": paid_out_at.isoformat(),
                    "gross": str(money.finalize(gross)),
                    "fees": str(money.finalize(fees)),
                    "net": str(money.finalize(net)),
                    "currency": currency,
                    "members": len(members),
                },
            )
            unresolved = _write_members(
                settlement, tenant_id=tenant_id, provider=provider, members=tuple(members)
            )
    except IntegrityError:
        # GUARD 2 — the race guard 1's SELECT cannot close: another delivery of
        # this same payout committed between our lookup and our INSERT.
        # `uq_settlements_provider_code` refused ours, which is the correct
        # outcome: one payout, one record.
        winner = _existing_payout(tenant_id, provider, code)
        if winner is None:  # pragma: no cover - the index is the only cause
            raise
        return _replayed(winner)

    return IngestedPayout(
        settlement_id=str(settlement.pk),
        provider=provider,
        code=code,
        status=settlement.status,
        created=True,
        member_count=len(members) - len(unresolved),
        gross=gross,
        fees=fees,
        net=net,
        currency=currency,
        unresolved=unresolved,
    )


def _write_members(
    settlement: Any, *, tenant_id: Any, provider: str, members: tuple[PayoutMember, ...]
) -> tuple[dict[str, Any], ...]:
    """One membership row per member — **each inside its own SAVEPOINT.**

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  ⚠ THE NESTED `transaction.atomic()` IS A SAVEPOINT AND IT IS NOT    ║
    ║  OPTIONAL. DO NOT "SIMPLIFY" IT INTO A BARE try/except.              ║
    ╚══════════════════════════════════════════════════════════════════════╝
    CLAUDE.md hard-won law 14, and the blueprint names it as **this phase's**
    risk: on PostgreSQL a single failed statement poisons the whole
    transaction, so a bare `except IntegrityError: continue` loses the
    settlement row and the other forty-five members at COMMIT. **The suite runs
    on in-memory SQLite, which has no aborted-transaction state, so the broken
    version passes every test on every machine.**

    Proved on PostgreSQL 16.13 rather than argued — see
    `tests/test_cr139_p5_settlements.py::test_cr139_p5_1_one_bad_member_keeps_the_rest`,
    which is marked `requires_postgres` for exactly that reason.
    """
    unresolved: list[dict[str, Any]] = []
    for one in members:
        payment = _payment_for(tenant_id, provider, one.reference)
        if payment is None:
            unresolved.append(
                {
                    "reference": one.reference,
                    "code": MEMBER_PAYMENT_NOT_FOUND,
                    "gross": str(money.finalize(one.gross)),
                    "detail": "this payout names a charge this product holds no payment for. "
                    "It is recorded rather than raised: a payout can legitimately carry a "
                    "charge taken before the utility went live, or one whose settlement "
                    "callback never arrived — and refusing the whole message would leave a "
                    "real bank credit with no record at all.",
                }
            )
            continue
        if payment.amount != one.gross:
            unresolved.append(
                {
                    "reference": one.reference,
                    "code": MEMBER_GROSS_DISAGREES,
                    "gross": str(money.finalize(one.gross)),
                    "payment_no": payment.payment_no,
                    "detail": f"the payout says this charge was "
                    f"{money.finalize(one.gross)} and the payment recorded "
                    f"{money.finalize(payment.amount)}. ⚠ THE MEMBER IS NOT WRITTEN, AND "
                    "WRITING THE PAYOUT'S FIGURE WOULD BE THE ONE ERROR THIS PHASE EXISTS "
                    "TO PREVENT: a member's gross is what the CUSTOMER paid, never what the "
                    "provider netted, so a disagreement is a question and not a correction.",
                }
            )
            continue
        # ── THE SAVEPOINT (law 14) ──────────────────────────────────────────
        # `uq_settlement_members_payment` is the guard: a payment belongs to at
        # most one payout. Without the nested atomic, the IntegrityError it
        # raises aborts the OUTER transaction on PostgreSQL and the whole
        # payout is lost — including every member already written.
        try:
            with transaction.atomic():
                settlement_models.SettlementMember.objects.create(
                    tenant_id=tenant_id,
                    settlement=settlement,
                    payment=payment,
                    gross=one.gross,
                    fee=one.fee,
                )
        except IntegrityError:
            unresolved.append(
                {
                    "reference": one.reference,
                    "code": MEMBER_ALREADY_PAID_OUT,
                    "gross": str(money.finalize(one.gross)),
                    "payment_no": payment.payment_no,
                    "detail": "this payment is already a member of another payout. One "
                    "dollar cannot be paid out twice, so the second membership is refused "
                    "by `uq_settlement_members_payment` and recorded here — the rest of "
                    "this payout is unaffected, which is what the SAVEPOINT buys.",
                }
            )
    return tuple(unresolved)


# ═══════════════════════════════════════════════════════════════════════════
# `P5.2` · THE FEE STOPS BEING A GUESS — AND IT GOES THROUGH THE SAME DOOR
# ═══════════════════════════════════════════════════════════════════════════
def stated_processor_fee(
    settlement: Any,
    *,
    recorded_total: Decimal,
    bank_total: Decimal,
    gl_account_id: Any,
    note: str | None = None,
) -> Any:
    """`OQ-160`'s option (c): the fee the PROVIDER stated, not the gap we found.

    Returns a `reconciliation.ResolutionInput` — **the identical type
    `derive_processor_fee` returns and a human's own explanation is built as.**
    Nothing is posted here. The figure enters `reconcile_batch` through the same
    door, is tied out against the difference by the same check, and reaches the
    books through `ledger_seam.post_batch_reconciled` as it always has.
    `ResolutionInput`'s own docstring anticipated this caller in as many words:
    *"a human or a settlement file states it"*.

    **WHY THIS IS WORTH A FUNCTION AT ALL, IN ONE WORKED CASE** — the PO's card
    day, with a chargeback inside it:

        recorded 5,120.40 · bank 4,972.90 · difference −147.50
        provider states it kept                        137.50
        unexplained                                     10.00   ← A CUSTOMER

    `derive_processor_fee` would answer *fee 147.50*, the batch would reconcile
    clean, and **the $10.00 chargeback would be invisible forever** — the
    customer's bill stays paid and nothing re-opens it. That is `OQ-160`'s
    recorded hazard, accepted by the PO because the product had no settlement
    file. This refuses instead, naming the remainder, because now it does.

    ⚠ **IT REFUSES RATHER THAN RETURNING TWO LINES.** Splitting the difference
    into *fee 137.50* + *unexplained 10.00* would make the batch tie out and
    would be a plug with a nicer name — `BR-PAY-019` (*every difference carries
    a reason AND an account*) and `BR-PAY-035` (*"Force match anyway" is
    permanently SUPERSEDED*) both say the same thing: an unexplained $10.00 is a
    question for a person, and this is where they are made to answer it.
    """
    from apps.payments import reconciliation  # local: no import cycle at module load

    recorded_total = _decimal(recorded_total, what="the recorded total")
    bank_total = _decimal(bank_total, what="the bank total")
    stated = _decimal(getattr(settlement, "fees", None), what="the payout's stated fees")
    difference = money.finalize(bank_total - recorded_total)
    if difference >= ZERO:
        raise PaymentRuleError(
            f"the bank credited {money.finalize(bank_total)} against a recorded "
            f"{money.finalize(recorded_total)}, a difference of {difference}. A processor "
            "fee makes the bank's credit SMALLER, so this difference cannot be one — an "
            "overage is a real question about where extra money came from, and naming it a "
            "fee would post a negative expense over the top of it.",
            br_ref="BR-PAY-019",
        )
    if money.finalize(-stated) != difference:
        remainder = money.finalize(difference + stated)
        raise PaymentRuleError(
            f"payout {getattr(settlement, 'code', settlement)} states the provider kept "
            f"{money.finalize(stated)}, and the bank is {money.finalize(-difference)} short "
            f"of what we recorded. {money.finalize(abs(remainder))} is unexplained. ⚠ THIS "
            "IS THE WHOLE POINT OF A STATED FEE: derived from the gap it would tie out "
            "perfectly and a customer chargeback would disappear into the fee line forever "
            "(OQ-160's recorded hazard). The remainder needs its own reason and its own GL "
            "account before this batch reconciles — it is not plugged and there is no "
            "'force match' (BR-PAY-035).",
            br_ref="BR-PAY-019",
        )
    return reconciliation.ResolutionInput(
        reason_code=REASON_PROCESSOR_FEE,
        gl_account_id=gl_account_id,
        amount=difference,
        note=note
        or (
            f"processor fee STATED by payout {getattr(settlement, 'code', settlement)}: "
            f"{money.finalize(stated)} kept of {money.finalize(getattr(settlement, 'gross', ZERO))} "
            f"gross (OQ-160 option c — known in advance, not derived from the shortfall)"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════
# `P5.6` · THE THIRD STATE, ANSWERED FROM THE RECORD RATHER THAN THE POINTER
# ═══════════════════════════════════════════════════════════════════════════
def awaiting_settlement_filter() -> Any:
    """*Which payments have not been paid out to us yet?* — as a `Q`.

    ⚠ **IT READS `settlement_members`, AND THERE IS NO LONGER ANYTHING ELSE
    IT COULD READ.** `payments.settlement_id` was dropped by `payments/0044`
    on the PO's ruling of 2026-09-24 (`OQ-PAY-12608`); before that it existed
    and could not be stamped, so a filter on it would have answered *"all of
    them"* truthfully and uselessly — hard-won law 7's *incapable of failing*
    shape wearing a list filter. **This function did not change when the
    column went**, which is the clearest statement of why nothing was lost.

    ⚠ **AND IT IS NOT THE SAME QUESTION AS *has this money been banked***. A
    counter payment, a lockbox row and a posted cheque are awaiting settlement
    **forever**, because nobody pays those out to us — which is why the screen
    that draws this state draws THREE (in a payout · awaiting one · never will
    be) and not two, and why the third one is a fact about the TENDER rather
    than about time.
    """
    from django.db.models import Q

    return ~Q(settlement_memberships__isnull=False)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 `P5.1` `P5.2` `P5.3` (05-prototype/06 Payments Page Blueprint.pdf p024 · 12-governance/02-decision-log.md 2026-09-05 "Payment providers are integrations" · 12-governance/01-open-questions.md OQ-144 CLOSED 2026-08-11 · OQ-160 CLOSED 2026-08-12 · OQ-264 CLOSED 2026-08-17 · CLAUDE.md hard rules 1/2/4/5/6/7 + hard-won law 14)
# generated: 2026-09-23 by LANE P5-BACK (the payments blueprint's phase 5, backend half)
# checklist: A✔ B✔ C✔ D=deferred(no endpoint — `P5.7`'s screens and their API are another lane) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · the pointer freeze was PROVED RED on PostgreSQL 16.13 in
#   2026-09-23 and that proof produced OQ-PAY-12608; the column is now DROPPED
#   (payments/0044, 2026-09-24) and the standing guard is
#   `test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone`
# exceptions: no payment row names its payout, BY RULING (OQ-PAY-12608 option
#         (b), 2026-09-24). `settlement_members` is the record. Declared as
#         data in `SETTLEMENT_UNAVAILABLE` rather than stubbed, per
#         `gateway.py`'s 2026-09-05 precedent
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
