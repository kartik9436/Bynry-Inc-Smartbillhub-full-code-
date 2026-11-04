# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (task 49 — the multi-property tender) · CR-059 CS-27
#           (task 51 — a master pays its units' bills)
#           Screens: S21 · S22 · S33 · S35 · P5 · P6 (CR-059 tasks 50 and 52 —
#           ANOTHER LANE. Nothing here draws anything.)
# Rules:    BR-PAY-1126 (one tender may settle several accounts of one
#           customer, recorded as ONE tender row and N payments) ·
#           BR-PAY-1127 (the parts must sum to the tender EXACTLY, or the whole
#           submission is refused and nothing partial commits) · BR-PAY-1128
#           (each account's payment carries its OWN duplicate-guard key) ·
#           BR-PAY-1129 (a master may pay a bill on a unit of its own premises,
#           and the authority is recorded) · BR-PAY-1130 (money a master pays
#           that no unit bill absorbs returns to the MASTER's credit, never to a
#           unit account's) · BR-PAY-022 (the single-payment field set this
#           wraps) · BR-PAY-028 (idempotency — key mechanics Eng-Lead 🔒) ·
#           BR-CUS-054 (the customer entity, and the link that proves a holder)
#           · BR-CUS-171 (a master's children, derived from the premises) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4 dp, CHAR(3),
#           never float) · rule 4 (financial immutability) · rule 5 (only the
#           ledger posting service writes journal lines) · rule 6 (idempotency)
#           · rule 7 (every money action writes audit_log) · law 14 (a failed
#           statement poisons the PostgreSQL transaction — SAVEPOINT or lose it)
# Ruling:   PO 2026-09-01 — a master **may always** pay a unit's bill (*"anyone
#           may pay any bill; the tenant's agreement is not required"*), so the
#           authority check is a RELATIONSHIP check and not a consent check.
#           PO 2026-09-01 — a bounced master tender is chased on the TENANT's
#           own account: *"If acocunt is will Utility , utility will chase it
#           and apply penalty"*.
# Tests:    06-backend/tests/test_cr059_cs12_multi_account_tender.py ·
#           06-backend/tests/test_cr059_cs27_master_pays_units.py
# Impacts:  apps/payments/services.record_payment (wrapped N times, unchanged
#           except for the `tender_id` it now accepts) · apps/payments/
#           tender_models.PaymentTender (the row this writes) ·
#           apps/payments/tenders_api.py (its only HTTP surface) ·
#           apps/payments/customer_position.py · premises_position.py (the two
#           reads a clerk aims at) · apps/payments/idempotency.py (the key
#           shape this derives FROM, and must not collide with)
# ───────────────────────────────────────────────────────
"""ONE CHEQUE, SEVERAL ACCOUNTS — CR-059 CS-12 and CS-27.

HUMAN-OWNED (CLAUDE.md 🔒 "idempotency keys" — `tender_part_reference` below IS
an idempotency key mechanic, and BR-PAY-028 delegates those by name).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. It may never reach lifecycle RATIFIED
without a recorded human sign-off.

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠⚠ READ THIS BEFORE CHANGING ANY LINE OF `tender_part_reference`.       ║
║                                                                          ║
║  THE DUPLICATE GUARD IS KEYED ON **TENANT + TOKEN, NOT ON THE ACCOUNT**. ║
║  A form that minted ONE token and reused it across three accounts would  ║
║  have payments two and three treated as REPLAYS: the server returns      ║
║  payment one, **reports success, and writes nothing.**                   ║
║                                                                          ║
║      in the drawer   $520.00                                             ║
║      recorded        $184.20                                             ║
║      errors raised   none                                                ║
║                                                                          ║
║  That is CS-12's own worked figure and it is the whole reason this file  ║
║  exists as a service rather than as three calls from a screen.           ║
╚══════════════════════════════════════════════════════════════════════════╝

TWO INDEPENDENT GUARDS STAND AGAINST IT, AND BOTH ARE ASSERTED SEPARATELY
------------------------------------------------------------------------
DEF-058 is what happens when one guard silently stands in for another, so
neither of these is allowed to be the only one:

  1. **A DISTINCT TOKEN PER ACCOUNT** (`tender_part_reference`) — the design
     fix. Three accounts, three keys, three payments, and a re-submitted form
     derives the same three keys and replays all three.
  2. **A NEW TENDER MAY NOT HAVE PARTS THAT ALREADY EXIST** (`_refuse_a_replay_
     under_a_new_tender`) — the belt. If guard 1 were ever broken, this turns
     the SILENT failure into a loud refusal, because a tender row that was
     created a microsecond ago cannot legitimately own a payment that was
     recorded yesterday. It is what the RED proof in the test file breaks.

WHY THE PART KEY IS DERIVED HERE AND NOT IN `idempotency.py`
------------------------------------------------------------
`idempotency.inbound_payment_key(source, reference)` composes `"<source>|<ref>"`
and refuses a missing part. This function shapes the REFERENCE half — the client
token plus the account it is being spent on — and hands it to that function
unchanged, so there is still exactly one place that builds the stored string and
exactly one unique index catching a duplicate. Splitting it the other way (a
fourth `SOURCE_`) would namespace a multi-account submit apart from an ordinary
one, and then a clerk who recorded 184.20 on the S22 form and then submitted the
same cheque through the customer form would take the money twice.

WHAT "ALL OR NOTHING" MEANS HERE, PRECISELY (BR-PAY-1127)
---------------------------------------------------------
The sum is checked BEFORE the transaction opens, so a submission that does not
add up burns no `PMT-` number out of the tenant series. Everything after that —
the tender row, all N payments, all their allocations, all their journal
entries, every audit row and every queued receipt — is inside ONE
`transaction.atomic()`. A refusal on the third part unwinds the first two.

⚠ **AND THAT IS THE ONE GUARANTEE SQLITE CANNOT TEST** (hard-won law 14). The
suite runs on in-memory SQLite by default and `config/settings/test.py` ignores
`DATABASE_URL`; the transaction-sensitive cases in the two test files carry
`requires_postgres` and were run against a live PostgreSQL 16 cluster, because
that is the only place a rolled-back savepoint behaves like production.

THE ONE PLACE THIS FILE CATCHES A DATABASE ERROR, AND WHY IT IS A SAVEPOINT
---------------------------------------------------------------------------
`_tender_row` races another request for the same `submission_key`. The loser
catches `IntegrityError` and reads the winner. **On PostgreSQL a failed
statement aborts the WHOLE transaction**, so the read afterwards would raise
`InFailedSqlTransaction` and the entire submission would be lost at COMMIT — and
the naive version passes every test in this repository, green, because SQLite
has no aborted-transaction state. The nested `transaction.atomic()` around the
INSERT is a SAVEPOINT and it is **not the tidy option, it is the only option**.
Do not "simplify" it away.

WHAT THIS FILE DELIBERATELY DOES NOT DECIDE
--------------------------------------------
**WHOSE PROPERTY GOES SHORT.** CS-12: *"Needs a ruling — for the AUTOMATIC
version only. Whose property goes short when the cheque does not cover
everything: oldest bill across all properties, the largest debt, the one closest
to disconnection, or the clerk's choice each time. Manual entry against three
visible bills sidesteps the question entirely, which is why it is the right
version one."* **Manual entry is what is built.** The clerk types each part
against a bill list they can see, the parts must sum, and no line of this file
ever chooses which account is left behind. Choosing one would be resolving an
open question by picking a value, which the prime directive forbids.

WHAT IS ALREADY RIGHT AND IS NOT REBUILT (CS-12, verbatim)
-----------------------------------------------------------
*"three balanced journal entries are not an error (each settled a different
account's receivable), and matching compares batch totals to bank lines, so the
three-way split is invisible to reconciliation and ties cleanly."*

So this file composes **no journal entry of its own** and touches the posting
path not at all (hard rule 5). Each part posts through `record_payment` →
`ledger_seam.post_payment_cleared` exactly as a single payment always has, and
each part joins the day's deposit batch by tender exactly as it always has.

⚠ **CS-27's narrative sentence says *"ONE balanced entry per tender: DR
undeposited 742.60 / CR AR ACC-1042 184.20 + …"* AND WHAT IS BUILT IS N ENTRIES
WHOSE DEBITS AND CREDITS SUM TO EXACTLY THAT.** Said plainly rather than left to
be discovered (hard-won law 1): the receivable that falls is the UNIT's in both
readings and the trial balance is identical, but the ledger holds four entries
and not one. Three reasons, and none of them is convenience — CS-12 rules in
terms that the per-payment entries *"must not be rebuilt"*; CS-27 is built
SECOND and *"extends CS-12 rather than repeating it"*, so it may not reverse
CS-12's own ruling; and composing a new multi-account entry shape is a change to
the 🔒 ledger-posting path, which is its own review surface. Recorded as a lane
judgment in 12-governance/02-decision-log.md, 2026-09-03, with this figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from core import audit as core_audit

from apps.payments import allocation, idempotency, tender_models
from apps.payments.exceptions import PaymentRuleError
from apps.payments.services import (
    RecordedPayment,
    _account,
    _currency,
    _dates,
    _method,
    _tenant_id,
    record_payment,
)

#: Hard rule 2 as re-signed 2026-08-22 — money is WRITTEN at 4 decimal places.
#: The sum check quantizes both sides to this before comparing, so 184.2000 and
#: 184.20 are the same figure and 184.2001 is not.
#: Hard rule 7's action name for the tender itself, beside `payment.recorded`
#: which each part writes. Two names, because a clerk looking for one cheque and
#: an auditor looking for one payment are asking different questions.
AUDIT_TENDER_RECORDED = "payment.tender_recorded"

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")

#: The seams this module resolves BY NAME rather than importing. `customers` is
#: another module's ORM and payments carries no import edge into it (B1/B8).
CUSTOMER_EXISTS_READ = "customer_exists"
CUSTOMER_ACCOUNT_IDS_READ = "customer_account_ids"
PREMISES_SCOPE_READ = "premises_scope_for_account"


@dataclass(frozen=True)
class TenderPart:
    """ONE account's share of one tender — what the clerk typed on one row.

    `amount` is that row's figure and nothing derives it: BR-PAY-1127 makes the
    parts the input and the tender total the thing they are checked against, not
    the other way round. An automatic split is the version CS-12 says needs a
    ruling first.

    `order` and `targets` are BR-PAY-001's allocation choice, per part, because
    a landlord may pay one tenant's oldest bill and another tenant's specific
    one in the same cheque. They are passed straight through to
    `record_payment`, which passes them straight through to the allocator.
    """

    account_id: Any
    amount: Decimal
    order: str = allocation.ORDER_OLDEST_FIRST
    targets: tuple[Any, ...] = ()
    memo: str | None = None


@dataclass(frozen=True)
class RecordedTender:
    """What one submission did — the tender, and every payment it made.

    `created=False` is the idempotent replay of the WHOLE submission (hard rule
    6): the same `submission_key` arrived twice, the first tender is returned
    with its parts, and nothing was written the second time. A RESULT rather
    than an exception, for the reason `RecordedPayment` gives — a double-clicked
    Record button is doing the right thing.
    """

    tender_id: str
    created: bool
    scope: str
    amount: Decimal
    currency: str
    reference: str | None
    payer_account_id: str | None
    customer_id: str | None
    authority: str | None
    parts: tuple[RecordedPayment, ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default=())


def tender_part_reference(submission_key: str, account_id: Any) -> str:
    """ONE ACCOUNT'S SHARE OF ONE SUBMISSION, AS A DUPLICATE-GUARD REFERENCE.

    🔒 This is an idempotency-key mechanic (BR-PAY-028 delegates those by name)
    and it is the single line of design CS-12 calls *"the fix"*.

        submission_key  the client token the form minted ONCE, for the cheque
        account_id      the account THIS part settles

        >>> tender_part_reference("3f2b91c4-…-1f5d2c7e8a10", "…-1042")
        '3f2b91c4-…-1f5d2c7e8a10#…-1042'

    which `idempotency.inbound_payment_key` then folds into
    `entry|3f2b91c4-…#…-1042` and stores in `payments.webhook_key`, unique per
    tenant.

    **WHY THE ACCOUNT AND NOT AN ORDINAL.** A position in a list is not stable:
    a clerk who reorders the rows on the form and submits again would derive
    three different keys for the same three payments and take the money twice.
    The account is the fact that identifies the part, and it is also what makes
    two parts on ONE account impossible to record — which is why
    `_refuse_a_repeated_account` refuses that by name rather than letting it
    arrive here as a silent replay.

    **`#` IS THE SEPARATOR, and it is not `|`.** `|` already separates the
    SOURCE from the reference one layer up (`idempotency.KEY_SEPARATOR`), and
    reusing it would make `entry|tok|acct` ambiguous to the eye in the psql
    session where somebody is debugging a refused duplicate — which is the exact
    property that module chose `|` for. `#` cannot occur in a uuid either.

    Pure and total: same two inputs ⇒ same string, always, with no clock and no
    database read. That is what lets the caller check for the duplicate before
    doing any work and still be backstopped by `uq_payments_webhook_key`.
    """
    token = "" if submission_key is None else str(submission_key).strip()
    account = "" if account_id is None else str(account_id).strip()
    if not token or not account:
        # Refuses rather than padding, for `PaymentKeyError`'s own reason: a key
        # composed with a part missing would be the same string for every
        # numberless submission a tenant ever makes, so the SECOND cheque of the
        # day would be refused as a duplicate of the first — money not taken,
        # reported as money already taken.
        raise idempotency.PaymentKeyError(
            "a tender part's duplicate-guard reference needs BOTH the submission token and "
            f"the account it settles (got {submission_key!r}, {account_id!r}). The payment "
            "guard is keyed on tenant + token and NOT on the account, so a reference missing "
            "either half would make every part of the cheque look like a replay of the "
            "first: one payment recorded, success reported, and the rest of the money "
            "silently not taken (CR-059 CS-12)."
        )
    return f"{token}#{account}"


def _money(value: Any, *, what: str) -> Decimal:
    """A Decimal at 4 dp, or a refusal naming the field (hard rule 2)."""
    if isinstance(value, float):
        raise PaymentRuleError(
            f"{what} arrived as a float ({value!r}). CLAUDE.md rule 2 forbids float money "
            "anywhere on this path: 0.1 + 0.2 is not 0.3 in binary, and a cheque that fails "
            "to sum by one ten-thousandth would be refused for a reason nobody could see.",
            br_ref="BR-PAY-1127",
        )
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise PaymentRuleError(
            f"{what} is not a decimal amount ({value!r}).", br_ref="BR-PAY-1127"
        ) from exc
    return amount.quantize(FOUR_DP)


def _refuse_a_repeated_account(parts: tuple[TenderPart, ...]) -> None:
    """Two rows against ONE account are refused BY NAME, and that is not fussiness.

    Both rows would derive the SAME `tender_part_reference`, so the second would
    be stored as a replay of the first: the clerk sees two rows, the system
    records one payment, and the totals still sum because the sum was checked on
    what was typed. **That is CS-12's trap wearing a different hat**, and it is
    the reason this refusal exists rather than a quiet merge — merging would
    silently change what the clerk asked for, on a money path, with no record.

    A clerk who genuinely wants two amounts on one account adds them up, which
    is what one payment on one account has always meant.
    """
    seen: set[str] = set()
    for part in parts:
        key = str(part.account_id)
        if key in seen:
            raise PaymentRuleError(
                f"account {key} appears twice in this cheque. Each account takes ONE part: "
                "both rows would carry the same duplicate-guard key, so the second would be "
                "stored as a replay of the first and its money would silently not be taken "
                "(CR-059 CS-12). Add the two figures together and enter them once.",
                br_ref="BR-PAY-1128",
            )
        seen.add(key)


def _refuse_unless_the_parts_sum(amount: Decimal, parts: tuple[TenderPart, ...]) -> Decimal:
    """BR-PAY-1127 — *"the parts must sum to the tender exactly, or the whole
    submission is refused; nothing partial commits."*

    Checked BEFORE the transaction opens, deliberately: a submission that does
    not add up must leave no `PMT-` number burnt out of the tenant's series and
    no half-written tender behind it — the same discipline `record_payment`
    keeps for a cheque whose facts do not hold together.

    **The refusal states BOTH figures and their difference**, because *"the
    amounts do not add up"* is a sentence a clerk cannot act on and *"520.00
    typed, 519.00 allocated, 1.00 short"* is one they can. Worked, from CS-12's
    own scenario: 184.20 + 156.90 + **179.90** against a cheque of 520.00 is
    **1.00 over**, and today the product *"accepts all three happily."*
    """
    total = sum((part.amount for part in parts), ZERO).quantize(FOUR_DP)
    if total != amount:
        difference = (total - amount).quantize(FOUR_DP)
        direction = "over" if difference > 0 else "short"
        raise PaymentRuleError(
            f"the parts of this cheque add up to {total}, and the cheque is {amount} — "
            f"{abs(difference)} {direction}. One tender settles several accounts only when the "
            "parts sum to it EXACTLY; nothing partial is recorded, so no account has been "
            "credited and no receipt has been produced (CR-059 CS-12). Adjust a figure and "
            "submit again.",
            br_ref="BR-PAY-1127",
        )
    return total


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """Another module's published read, by name. Never an import (B1/B8)."""
    from apps.payments.billing_seam import _resolve as seam_resolve

    return seam_resolve(module, attribute, kind)


def _refuse_unless_one_customer(customer_id: Any, parts: tuple[TenderPart, ...]) -> None:
    """CS-12's boundary — *"several accounts of ONE customer"* (BR-PAY-1126).

    ⚠ **AN UNWIRED SEAM REFUSES; IT NEVER ANSWERS "yes"** — the same posture
    `transfer._refuse_unless_one_customer` takes, and for the same reason: a
    module that cannot see who holds an account cannot prove a cheque belongs on
    it, and recording money on that basis is how a stranger's payment lands on
    somebody else's bill.

    The membership set is `customer_account_ids(customer_id)`, BR-CUS-054's own
    N:M link read, published by customers. **It is asked ONE way only and that
    is correct here**, unlike the transfer's two-sided check: there the question
    is *do these two accounts share SOME holder*, and `customer_for_account`
    answers only the earliest link; here the customer is NAMED by the caller, so
    the link set of that named customer is the complete answer.
    """
    exists = _resolve("customers", CUSTOMER_EXISTS_READ)
    accounts_of = _resolve("customers", CUSTOMER_ACCOUNT_IDS_READ, "service_request_service")
    if exists is None or accounts_of is None:  # pragma: no cover - customers publishes both
        raise PaymentRuleError(
            "a customer tender settles several accounts of ONE customer (CS-12), and "
            f"`apps.customers.selectors.{CUSTOMER_EXISTS_READ}` or "
            f"`apps.customers.service_request_service.{CUSTOMER_ACCOUNT_IDS_READ}` is not "
            "published on this deployment — so this process cannot tell whose accounts these "
            "are. Refused rather than assumed.",
            br_ref="BR-CUS-054",
        )
    if not exists(customer_id):
        raise PaymentRuleError(
            f"customer {customer_id!r} is not a customer of this tenant, so there is nobody to "
            "record this cheque against (CLAUDE.md rule 1).",
            br_ref="BR-CUS-054",
        )
    held = set(accounts_of(customer_id))
    stray = sorted(str(part.account_id) for part in parts if str(part.account_id) not in held)
    if stray:
        raise PaymentRuleError(
            f"account(s) {stray} are not held by this customer, so one cheque from them may "
            "not settle those bills (BR-CUS-054). A shared surname or address counts for "
            "nothing here. Where a landlord is paying their TENANTS' bills the accounts are "
            "genuinely somebody else's — that is the premises path (CS-27), which records who "
            "paid and on what authority.",
            br_ref="BR-PAY-1126",
        )


def _premises_scope(payer_account_id: Any) -> dict[str, Any]:
    """CS-27's authority resolver — *unit → premises → owner → master*.

    **IT IS A RELATIONSHIP CHECK AND NOT A CONSENT CHECK, AND THAT IS A PO
    RULING (2026-09-01), not a simplification made here.** The PO ruled that a
    master **may always** pay a unit's bill — *"anyone may pay any bill; the
    tenant's agreement is not required"* — and that paying it **does** give the
    master sight of that bill including its usage. So the only question is *is
    this unit on this master's premises?*

    ⚠ **FOLLOWS FROM THAT RULING AND IS OWED TO A PERSON:** a tenant's
    consumption becomes visible to their landlord. CS-27 says to *"tell the
    tenant it happens — at sign-up or on the bill — so it is a policy rather
    than a discovery."* No screen in this lane; REPORTED on the tender's
    `problems` so the surface that renders it cannot silently drop the fact.

    The walk itself is customers' own published read (`premises_scope_for_
    account`), because the join is three modules wide and payments may touch
    none of those tables. **An unowned premises has nobody to authorise** —
    CS-27's own *"the join to build carefully"* — and arrives here as an empty
    `account_ids`, so every part is refused by name.
    """
    read = _resolve("customers", PREMISES_SCOPE_READ)
    if read is None:  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            f"`apps.customers.selectors.{PREMISES_SCOPE_READ}` is not published on this "
            "deployment, so this process cannot tell which units belong to this master's "
            "premises. A payer who may not be checked is a payer who is refused (CS-27).",
            br_ref="BR-PAY-1129",
        )
    scope = read(payer_account_id)
    if scope is None:
        raise PaymentRuleError(
            f"account {payer_account_id!r} is not a master account of this tenant, so it has "
            "no premises to pay for. An ordinary account pays its own bills; a landlord "
            "paying a block is a MASTER account holding the building's common areas "
            "(BR-CUS-068).",
            br_ref="BR-PAY-1129",
        )
    return scope


def _refuse_unless_the_payer_may_pay(
    scope: dict[str, Any], parts: tuple[TenderPart, ...]
) -> tuple[str, ...]:
    """BR-PAY-1129 — every part names a unit account on the payer's premises, or
    the payer's OWN account.

    Today *"nobody checks the payer may pay — there is no bill-to and no
    responsible party anywhere"* (CS-27). This is that check, and it is the
    whole of it.

    **The payer's own account is always allowed as a part**, and it has to be:
    BR-PAY-1130 says money no unit bill absorbs is carried as the MASTER's own
    credit, and *"a leftover has to live somewhere and the only lawful home is
    the payer's account."* That leftover is a payment on the master, which is
    the ONE exception to *"the master carries the tender record and no payment
    entry."*

    Returns the ids of the parts that are UNIT parts, in the order given — the
    set BR-PAY-1130 then guards against absorbing a landlord's money.
    """
    payer_id = str(scope["payer_account_id"])
    payable = set(scope.get("account_ids") or ())
    stray = sorted(
        str(part.account_id)
        for part in parts
        if str(part.account_id) != payer_id and str(part.account_id) not in payable
    )
    if stray:
        raise PaymentRuleError(
            f"account(s) {stray} are not on this master's premises, so "
            f"{scope.get('payer_account_no') or payer_id} may not pay their bills "
            "(BR-PAY-1129). A master may always pay a unit of its OWN building — the tenant's "
            "agreement is not needed (PO ruling 2026-09-01) — but the building is what makes "
            "it lawful, and this account is not in it. Where the premises names no owner "
            "there is nobody to authorise at all, and declaring the owner is the fix.",
            br_ref="BR-PAY-1129",
        )
    return tuple(str(part.account_id) for part in parts if str(part.account_id) != payer_id)


def _tender_row(
    actor: Any,
    *,
    tenant_id: Any,
    scope: str,
    customer_id: Any,
    payer_account: Any,
    premises_id: Any,
    authority: str | None,
    amount: Decimal,
    currency: str,
    method: Any,
    reference: str | None,
    posted_at: Any,
    cleared_at: Any,
    submission_key: str,
) -> tuple[tender_models.PaymentTender, bool]:
    """The tender row, created or found. Hard rule 6, at the SUBMISSION level.

    ⚠ **THE `try/except IntegrityError` BELOW IS WRAPPED IN A NESTED
    `transaction.atomic()` AND THAT IS NOT A STYLE CHOICE — IT IS THE ONLY THING
    THAT WORKS ON POSTGRESQL** (CLAUDE.md hard-won law 14). Once any statement
    errors inside a transaction, PostgreSQL aborts the WHOLE transaction: the
    `filter().first()` in the handler would raise `InFailedSqlTransaction` and
    the entire cheque would be lost at COMMIT. **The naive version — catch,
    read, carry on — passes this repository's whole suite, green, on every
    machine**, because `config/settings/test.py` hardcodes in-memory SQLite and
    SQLite has no aborted-transaction state. The nested atomic is a SAVEPOINT.
    Do not remove it, and do not "simplify" it into a bare try.

    The cheap path is a SELECT first, so an ordinary replay costs one query and
    no savepoint at all — the same shape `record_payment` uses, and for the same
    reason: the unique index is what makes a LOST RACE indistinguishable from a
    replay, and neither writes a second tender.
    """
    found = tender_models.PaymentTender.objects.filter(
        tenant_id=tenant_id, submission_key=submission_key
    ).first()
    if found is not None:
        return found, False
    try:
        # ── SAVEPOINT (law 14) ──────────────────────────────────────────────
        with transaction.atomic():
            row = tender_models.PaymentTender.objects.create(
                tenant_id=tenant_id,
                scope=scope,
                customer_id=customer_id,
                payer_account=payer_account,
                premises_id=premises_id,
                authority=authority,
                amount=amount,
                currency=currency,
                method=method,
                reference=reference,
                posted_at=posted_at,
                cleared_at=cleared_at,
                submission_key=submission_key,
            )
            # ── hard rule 7, INSIDE the transaction ─────────────────────────
            # **The tender is a money action in its own right and is audited as
            # one.** Each part writes its own `payment.recorded` row carrying
            # this tender's id, so the parts are traceable either way — but the
            # thing a clerk and an auditor recognise is THE CHEQUE, and without
            # this row the only record that 520.00 was handed over once is three
            # rows saying 184.20, 156.90 and 178.90. `core.audit` raises rather
            # than losing the row, which takes the tender with it: money
            # recorded with no record of who took it is the one outcome rule 7
            # exists to prevent.
            core_audit.money_action(
                actor,
                AUDIT_TENDER_RECORDED,
                "payment_tender",
                str(row.pk),
                after={
                    "scope": scope,
                    "customer_id": None if customer_id is None else str(customer_id),
                    "payer_account_id": (None if payer_account is None else str(payer_account.pk)),
                    "premises_id": None if premises_id is None else str(premises_id),
                    "authority": authority,
                    "amount": str(amount),
                    "currency": currency,
                    "reference": reference,
                    "posted_at": posted_at.isoformat(),
                    "cleared_at": None if cleared_at is None else cleared_at.isoformat(),
                    "idempotency_key": submission_key,
                    "job": None if actor is not None else "payments.tender",
                },
            )
        return row, True
    except IntegrityError:
        # The race `uq_payment_tenders_submission` exists for. A lost race and a
        # replay are the same fact — one tender exists, ours is not it. The
        # savepoint above has been rolled back, so this SELECT is lawful.
        winner = tender_models.PaymentTender.objects.filter(
            tenant_id=tenant_id, submission_key=submission_key
        ).first()
        if winner is None:  # pragma: no cover - the index is the only thing that fires
            raise
        return winner, False


def _refuse_a_replay_under_a_new_tender(
    *, tender_created: bool, part: RecordedPayment, account_id: Any
) -> None:
    """GUARD 2 — the belt behind `tender_part_reference` (see the module header).

    A tender row created a microsecond ago cannot legitimately own a payment
    that already existed. If it does, the part's duplicate-guard key collided
    with something — which is exactly what happens when one token is reused
    across accounts — and the caller is about to be told a cheque was recorded
    when most of its money was not.

    **This is what turns CS-12's SILENT failure into a loud one**, and it is the
    guard the RED proof in `test_cr059_cs12_multi_account_tender.py` breaks: with
    `tender_part_reference` monkeypatched to ignore the account, the service
    refuses here instead of reporting success over $335.80 that was never taken.

    Both guards are asserted separately, because DEF-058 is what happens when
    one guard silently stands in for another.
    """
    if tender_created and not part.created:
        raise PaymentRuleError(
            f"the part for account {account_id} was treated as a REPLAY of payment "
            f"{part.payment_no or part.payment_id}, under a tender that has only just been "
            "created — so its duplicate-guard key collided with a payment that already "
            "existed. Nothing is recorded. This is the failure CR-059 CS-12 names: the guard "
            "is keyed on tenant + token and NOT on the account, so one token reused across "
            "accounts records the first payment, reports success and writes nothing for the "
            "rest. Every part must carry its own key (BR-PAY-1128).",
            br_ref="BR-PAY-1128",
        )


def _refuse_a_tenant_holding_the_landlords_money(
    *, part: RecordedPayment, account_id: Any, payer_account_no: str | None
) -> None:
    """BR-PAY-1130 — *"money a master pays that no unit bill absorbs returns to
    the MASTER's credit, never to a unit account's."*

    CS-27 names this as the second-worst thing that goes wrong today: *"An
    overpayment becomes a TENANT's credit — the landlord's money, on a different
    person's account, and it will auto-apply to their next bill."*

    **The test is the allocator's OWN figure, not a balance read before the
    fact.** `credit_carried` is what this payment could not put against a bill,
    measured inside the same transaction that wrote the allocations, so nothing
    can slip in between a pre-check and the write. Anything above zero on a UNIT
    part means the landlord's money is sitting on the tenant's account, and the
    whole submission is refused rather than that being allowed to commit.

    Worked, from CS-27's own fixture: the owner's cheque **#9931 for $742.60**
    over four units owing 184.20 · 156.90 · 212.60 · 188.90. Type **200.00**
    against `ACC-1042`, which owes 184.20, and **15.80 of the landlord's money**
    would sit as J. Ilori's credit and auto-apply to their next water bill. The
    lawful home for it is a part on the master's own account.

    ⚠ **THIS IS THE PREMISES PATH ONLY.** On a CUSTOMER tender (CS-12) a
    leftover is the customer's own money on their own account and is lawful — it
    is REPORTED, with CS-8 named as the way to reach a sibling in arrears, and
    never refused. The two are different because in CS-12 the payer holds the
    account and in CS-27 they emphatically do not.
    """
    if part.credit_carried > ZERO:
        raise PaymentRuleError(
            f"{part.credit_carried} of this cheque would be left on account {account_id} as "
            "that customer's own credit, and the money is "
            f"{payer_account_no or 'the master'}'s. A tenant must never end up holding their "
            "landlord's money — it would auto-apply to that tenant's next bill "
            "(BR-PAY-1130). Nothing is recorded. Reduce this row to what the unit owes and "
            "put the remainder on the master's own account, which is where a leftover "
            "lawfully lives.",
            br_ref="BR-PAY-1130",
        )


def record_multi_account_payment(
    actor: Any,
    *,
    parts: tuple[TenderPart, ...],
    amount: Decimal,
    posted_at: Any,
    submission_key: str,
    cleared_at: Any = None,
    customer_id: Any = None,
    payer_account_id: Any = None,
    method_code: str | None = None,
    reference: str | None = None,
    currency: str | None = None,
    memo: str | None = None,
    counter_session_id: Any = None,
) -> RecordedTender:
    """ONE tender, N payments — all of it, or none of it (CR-059 CS-12 · CS-27).

    Name EITHER `customer_id` (CS-12 — several accounts of one customer) OR
    `payer_account_id` (CS-27 — a master paying its tenants' bills). Naming both
    or neither is refused: they are different keys and different authority
    questions, and a submission that does not say which one it is cannot be
    checked against either.

    **THE WORKED CASE (CS-12's fixture scenario):** cheque **#8842 for $520.00**
    on 8 August, customer *Oakwood Holdings*, three parts —
    `ACC-1042` **184.20**, `ACC-1043` **156.90**, `ACC-1044` **178.90**. One
    tender row, three payments, three allocations, three balanced journal
    entries, three receipts each naming cheque #8842, and 520.00 checked before
    a single row is written.

    **THE OTHER WORKED CASE (CS-27's fixture scenario):** the owner's cheque
    **#9931 for $742.60** over `ACC-1042` 184.20 · `ACC-1043` 156.90 ·
    `ACC-1044` 212.60 · `ACC-1045` 188.90, paid by master `ACC-9001`. Four
    payments land on the four TENANTS' accounts, each annotated with the payer
    through its tender; **the master carries the tender and no payment entry**,
    and its own hallway bill of 69.60 is untouched.

    Order of operations, and each step is where it is for a reason:

      1. **Shape** — one scope, at least one part, no repeated account, every
         amount positive. Cheapest refusals first.
      2. **Arithmetic** — BR-PAY-1127's sum, BEFORE the transaction, so a
         cheque that does not add up burns no `PMT-` number.
      3. **Authority** — the customer link (CS-12) or the premises relationship
         (CS-27). Before the transaction for the same reason.
      4. **The transaction** — the tender row, then every part through
         `record_payment`, then the two guards. One `atomic()`; a refusal on the
         last part unwinds the first.

    `counter_session_id` — THE TILL THIS CHEQUE WAS TAKEN AT (`DEF-PAY-6322`,
    `DEF-PAY-7642`, lane PAY-H 2026-10-30). The two doors in `tenders_api.py`
    now call `counters.assert_till_open_for_tender` exactly as the single-account
    door does, and hand the open till here; it is stamped on EVERY part, because
    each part is a payment row and the drawer is counted by payment rows. A
    tender of six cheque parts and no till would bank $520.00 under the day's
    system till, the one that is openly nobody's. `None` for the four tenders
    that never pass through hands, and for the service's own callers.

    Raises `PaymentRuleError` for everything a human can act on. Returns
    `RecordedTender(created=False)` for a replay of the whole submission — never
    an exception.
    """
    tenant_id = _tenant_id()
    parts = tuple(parts or ())

    # ── 1 · SHAPE ───────────────────────────────────────────────────────────
    named = [
        name for name, value in (("customer", customer_id), ("payer", payer_account_id)) if value
    ]
    if len(named) != 1:
        raise PaymentRuleError(
            "a tender is grouped EITHER by customer (several accounts of one customer, "
            "CS-12) OR by premises (a master paying its tenants' bills, CS-27), and this "
            f"submission named {named or 'neither'}. They are different keys and different "
            "authority questions — CS-12's customer link does not join a landlord to their "
            "tenants — so a submission that does not say which it is cannot be checked "
            "against either.",
            br_ref="BR-PAY-1126",
        )
    scope = (
        tender_models.TENDER_SCOPE_CUSTOMER if customer_id else tender_models.TENDER_SCOPE_PREMISES
    )
    if not parts:
        raise PaymentRuleError(
            "this cheque names no account to settle. One tender settles SEVERAL accounts "
            "(CS-12); with none there is nothing to record and nothing to sum against.",
            br_ref="BR-PAY-1126",
        )
    amount = _money(amount, what="the cheque total")
    if amount <= ZERO:
        raise PaymentRuleError(
            f"a tender of {amount} is not something anybody handed over. The cheque total "
            "must be greater than zero.",
            br_ref="BR-PAY-1127",
        )
    priced: list[TenderPart] = []
    for part in parts:
        part_amount = _money(part.amount, what=f"the part for account {part.account_id}")
        if part_amount <= ZERO:
            raise PaymentRuleError(
                f"the part for account {part.account_id} is {part_amount}. Every row of a "
                "cheque settles a real amount; a zero row is a row the clerk did not mean to "
                "add, and a negative one would take money off an account this path never "
                "touches.",
                br_ref="BR-PAY-1127",
            )
        priced.append(replace(part, amount=part_amount))
    parts = tuple(priced)
    _refuse_a_repeated_account(parts)

    # ── 2 · ARITHMETIC, BEFORE ANYTHING IS WRITTEN (BR-PAY-1127) ────────────
    _refuse_unless_the_parts_sum(amount, parts)

    # ── 3 · AUTHORITY, ALSO BEFORE ANYTHING IS WRITTEN ──────────────────────
    problems: list[dict[str, Any]] = []
    payer_account = None
    premises_id = None
    authority = None
    unit_account_ids: tuple[str, ...] = ()
    payer_account_no: str | None = None
    if scope == tender_models.TENDER_SCOPE_CUSTOMER:
        _refuse_unless_one_customer(customer_id, parts)
        authority = tender_models.AUTHORITY_ACCOUNT_HOLDER
    else:
        premises_scope = _premises_scope(payer_account_id)
        unit_account_ids = _refuse_unless_the_payer_may_pay(premises_scope, parts)
        authority = tender_models.AUTHORITY_PREMISES_OWNER_MASTER
        premises_ids = premises_scope.get("premises_ids") or []
        premises_id = premises_ids[0] if premises_ids else None
        payer_account_no = premises_scope.get("payer_account_no")
        accounts = _resolve("customers", "account_queryset")
        payer_account = accounts().filter(pk=premises_scope["payer_account_id"]).first()
        # CS-27's own instruction, and it is owed to a person rather than to a
        # screen: paying a tenant's bill gives the master sight of that bill,
        # including its usage. REPORTED so the surface cannot drop the fact.
        problems.append(
            {
                "code": "master_can_see_the_units_bills",
                "br_ref": "BR-PAY-1129",
                "detail": "paying a unit's bill gives this master sight of that bill, "
                "including its usage (PO ruling 2026-09-01). CS-27 asks that the tenant be "
                "TOLD this happens — at sign-up or on the bill — so it is a policy rather "
                "than something they discover.",
            }
        )
        if len(premises_ids) > 1:
            problems.append(
                {
                    "code": "master_owns_several_premises",
                    "br_ref": "BR-PAY-1129",
                    "detail": f"this master owns {len(premises_ids)} premises and the tender "
                    "records the first as its authority reference. Every part was checked "
                    "against the whole set, so nothing is refused wrongly — but a tender "
                    "carries ONE premises id and which one it names is not a signed rule.",
                }
            )

    method = _method(method_code) if method_code else None
    # BR-TEN-042 locks a utility to ONE currency, and hard rule 2 wants a CHAR(3)
    # beside every amount rather than an assumed one. The tender takes the
    # currency of the FIRST part's account through `services._currency`, which is
    # the same function — and therefore the same refusal — that stamps each
    # payment: so the cheque and its parts can never end up in two currencies,
    # and a stated code that disagrees with the account is refused once, here,
    # instead of three times with three different account numbers in the message.
    tender_currency = _currency(_account(parts[0].account_id), currency)
    # BR-PAY-021, normalised ONCE. `record_payment` normalises its own copies
    # identically, so the tender and its parts carry the same two moments — a
    # cheque with three different posting dates is the defect this table exists
    # to remove.
    tender_posted_at, tender_cleared_at = _dates(posted_at, cleared_at)

    # ── 4 · ONE TRANSACTION. ALL OF IT, OR NONE OF IT (BR-PAY-1127) ─────────
    with transaction.atomic():
        tender, tender_created = _tender_row(
            actor,
            tenant_id=tenant_id,
            scope=scope,
            customer_id=customer_id or None,
            payer_account=payer_account,
            premises_id=premises_id,
            authority=authority,
            amount=amount,
            currency=tender_currency,
            method=method,
            reference=reference,
            posted_at=tender_posted_at,
            cleared_at=tender_cleared_at,
            submission_key=submission_key,
        )
        recorded: list[RecordedPayment] = []
        for part in parts:
            result = record_payment(
                actor,
                account_id=part.account_id,
                amount=part.amount,
                posted_at=posted_at,
                cleared_at=cleared_at,
                currency=currency,
                method_code=method_code,
                # CS-12: one cheque reads as one cheque. The NUMBER goes on every
                # part's `confirmation`, which is the column bank reconciliation
                # matches on and the one the PO opened to correction on
                # 2026-09-02 — so a mistyped cheque number stays fixable part by
                # part, exactly as it is for a single payment.
                confirmation=reference,
                memo=part.memo or memo,
                order=part.order,
                targets=part.targets,
                idempotency_source=idempotency.SOURCE_ENTRY,
                # 🔒 THE ONE LINE OF DESIGN CS-12 CALLS "the fix". See
                # `tender_part_reference`, and do not replace it with
                # `submission_key`.
                idempotency_reference=tender_part_reference(submission_key, part.account_id),
                tender_id=tender.pk,
                # DEF-PAY-6322 — one till for the whole cheque, on every part.
                counter_session_id=counter_session_id,
            )
            _refuse_a_replay_under_a_new_tender(
                tender_created=tender_created, part=result, account_id=part.account_id
            )
            if str(part.account_id) in unit_account_ids:
                _refuse_a_tenant_holding_the_landlords_money(
                    part=result,
                    account_id=part.account_id,
                    payer_account_no=payer_account_no,
                )
            recorded.append(result)

    if scope == tender_models.TENDER_SCOPE_CUSTOMER:
        stranded = [
            (str(part.account_id), result.credit_carried)
            for part, result in zip(parts, recorded, strict=True)
            if result.credit_carried > ZERO
        ]
        if stranded:
            # CS-12: *"Overpay at 600.00 and the 80.00 remainder parks on ONE
            # account and auto-applies to that account's next bill, unreachable
            # by a sibling in arrears."* It is the customer's OWN money on their
            # OWN account, so it is lawful and is NOT refused — but the sibling
            # problem is real and CS-8 is the door, so it is stated with its
            # figure rather than left silent.
            problems.append(
                {
                    "code": "remainder_parks_on_one_account",
                    "br_ref": "BR-PAY-1126",
                    "detail": "the amounts left over after each row met its bills are "
                    + ", ".join(f"{account}: {left}" for account, left in stranded)
                    + ". Each stays as credit on the account it was typed against and will "
                    "auto-apply to that account's next bill; it does not reach a sibling "
                    "property in arrears on its own. Moving it is a credit transfer "
                    "(CR-059 CS-8), which is a deliberate act with its own audit row.",
                }
            )

    return RecordedTender(
        tender_id=str(tender.pk),
        created=tender_created,
        scope=tender.scope,
        amount=tender.amount,
        currency=tender.currency,
        reference=tender.reference,
        payer_account_id=str(tender.payer_account_id) if tender.payer_account_id else None,
        customer_id=str(tender.customer_id) if tender.customer_id else None,
        authority=tender.authority,
        parts=tuple(recorded),
        problems=tuple(problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-12 + CS-27 (12-governance/11-change-requests.md §8 · §11 tasks 49, 51 · 04-docs/05-modules/08-payments/02-business-rules.md · CLAUDE.md hard rules 1/2/4/5/6/7 + law 14)
# generated: 2026-09-03 by the CR-059 W9 multi-account/master-tender lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no UI — CR-059 tasks 50/52 are another lane, live in 07-frontend/src/features/payments/ while this was written) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · PROVED RED FIRST (hard-won law 7): with `tender_part_reference` monkeypatched to ignore the account — the one-token version CS-12 warns about — the $520.00 cheque records ONE payment of $184.20; guard 2 then refuses it by name, and with guard 2 also removed the service reports success over $335.80 that was never taken. Both are asserted separately (DEF-058). The all-or-nothing rollback was run against a live PostgreSQL 16 cluster, because SQLite cannot test it.
# exceptions: (1) NO SCREEN. CR-059 tasks 50 and 52 own P5, P6, S21's two sides
#         and S33's grouping; another lane holds `07-frontend/src/features/
#         payments/`. The routes are live and nothing draws them — hard-won law
#         2 with the halves in two lanes BY DESIGN, and REPORTED.
#         (2) THE AUTOMATIC SHORTFALL ORDER IS NOT DECIDED HERE and no line of
#         this file chooses which account goes short. CS-12 says a ruling is
#         needed for the automatic version and that manual entry sidesteps it;
#         manual entry is version one.
#         (3) N JOURNAL ENTRIES, NOT ONE PER TENDER. CS-27's narrative sentence
#         describes one entry of 742.60; what is built is four entries summing
#         to it, because CS-12 rules the per-payment entries must not be rebuilt
#         and a new entry shape is a change to the 🔒 posting path. Stated in
#         the module docstring with the figure and in the decision log.
#         (4) A CUSTOMER TENDER's LEFTOVER IS REPORTED, NEVER REFUSED — it is
#         the customer's own money on their own account. Only the PREMISES path
#         refuses it (BR-PAY-1130), because there the payer is not the holder.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
