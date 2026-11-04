# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (bulk account upload) · US-CUS-021 (opening balances as
#           AGED BUCKETS) · US-CUS-022 (the balanced AR↔clearing handoff) ·
#           US-CUS-023 (deposits with ORIGINAL receipt dates)
#           Screens: S68 (the import wizard) · S81 (the Imports tab)
# Change:   CR-030 W1 — accounts become the SIXTH target on the ONE ETL runner
#           (BR-MET-096), and the runner writes nothing here itself.
# Rules:    BR-CUS-047 (migration ORDER — a row naming a missing unit errors,
#           never auto-creates) · BR-CUS-048 (four aged buckets; lump-sum and
#           invoice-level REJECTED) · BR-CUS-049 (opening balances post as
#           balanced opening JEs, AR ↔ clearing, dated at cutover, immutable) ·
#           BR-CUS-061 (opening CREDIT balances import as a carried ACCOUNT
#           CREDIT — BR-PAY-010's overpayment pattern; aging buckets stay
#           DEBIT-ONLY; PO OQ-065 option (b), 2026-08-08) · BR-CUS-077 (a row
#           carrying BOTH a credit and aged arrears carries both, SEPARATELY —
#           never netted; PO 2026-08-24) · BR-PAY-010 (overpayment → account
#           credit, auto-applies to the next issued bill, refundable) ·
#           BR-CUS-050/057 (deposit interest accrues from the ORIGINAL receipt
#           date) · BR-CUS-054 (one customer_ref = one customer row) ·
#           BR-CUS-017 (at most one live account per unit) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money 4dp) · rule 4 (immutability) ·
#           rule 5 (only the posting service writes journal lines) ·
#           rule 6 (idempotency) · rule 7 (audit)
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08
# Impacts:  apps/metering/import_runs.py (the runner, through seams ONLY) ·
#           apps/ledger/opening_balances.py 🔒 (the writer this finally calls)
# ───────────────────────────────────────────────────────
"""The accounts import's write half — the caller `opening_balances` was waiting for.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this composes money-bearing rows and hands a
batch to the ledger posting service, under CLAUDE.md's 🔒 *ledger posting* and
*money rounding*. AI-authored 2026-08-24 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS
════════════════════════════════════════════════════════════════════════════
`apps/ledger/opening_balances.py` has been complete since 2026-08-16 and its own
docstring records what was missing:

    ⚠ WHAT THIS DOES NOT CLAIM, AND IT IS THE WHOLE OF WHAT IS STILL MISSING
    (hard-won law 2). There is still **no importer** … nothing in the running
    product calls this file today, and a utility migrating in from another
    system still cannot bring its receivables across.

This is that importer. **The PO asked for it on 2026-08-24** — *"also when you
upload accounts you will need trial balance field - opening balance for that
account"* — and the answer was that it had been finance-signed since 2026-08-08
with a writer built and no caller.

════════════════════════════════════════════════════════════════════════════
FOUR BUCKETS, NOT ONE FIGURE — AND THE ROUNDING RULE THAT GOES WITH IT
════════════════════════════════════════════════════════════════════════════
BR-CUS-048 (CONFIRMED, PO AC-3 option B): `Current / 31–60 / 61–90 / 90+` as of
the cutover date. **Lump-sum and invoice-level were EXPLICITLY REJECTED.** One
figure has no age, so a lump sum lands every migrated account at `Current` on day
one: collections cannot act and late fees are wrong until real invoices age.

`accounts.balance` is **Σ buckets EXACTLY** — GT-16's *"Σ buckets, exact — no
recompute"*. Nothing here rounds: the inputs are 2 dp off a spreadsheet, the
column stores 4, and `Decimal` addition of 2 dp values is exact. A `float`
anywhere in this path would turn 84.20 + 62.10 + 121.00 into 267.29999999999995
and the batch would fail its own tie-out — which is the good outcome; the bad one
is a rounding step that "fixes" it and hides a real imbalance.

════════════════════════════════════════════════════════════════════════════
A NEGATIVE BUCKET IS AN OPENING CREDIT, AND IT LOADS — BR-CUS-061 + BR-CUS-077
════════════════════════════════════════════════════════════════════════════
A negative bucket cell is a legacy CREDIT balance: an overpayment the old system
was holding for this customer.

⚠ **THIS FILE SHIPPED REFUSING IT, CITING OQ-065 AS OPEN. OQ-065 CLOSED ON
2026-08-08 — SIXTEEN DAYS BEFORE THIS FILE WAS WRITTEN (DEF-620).** The banner
that stood here said *"It is OPEN."* while
`12-governance/01-open-questions.md` line 60 read **CLOSED(→BR-CUS-061)**. The
cost was not academic: a utility migrating a base in which some accounts are in
credit had those rows REJECTED and had to settle them by hand in the system it
was leaving — which is option **(c)**, the option the PO did not choose.

**BR-CUS-061, CONFIRMED, PO OQ-065 option (b), 2026-08-08, verbatim:**

    Opening CREDIT balances at cutover import as a carried **account credit**
    (BR-PAY-010 overpayment pattern) — aging buckets stay debit-only; the credit
    auto-applies to the account's first bills; refundable on request

Two halves, and the shipped code implemented one:

  1. ✅ **AGING BUCKETS STAY DEBIT-ONLY.** No negative row is ever written to
        `account_opening_buckets`, and that is enforced here rather than by a
        CHECK constraint because the credit has to go somewhere else, not away.
  2. ✅ **THE ROW LOADS**, and the credit is carried. `opening_position` returns
        it as `credit`, a POSITIVE Decimal, beside the debit buckets.

**BR-CUS-077, CONFIRMED, PO 2026-08-24 — the row that carries BOTH.** On the
figure put to the PO: **$45.00** of credit in the current period and **$121.00**
owed from over ninety days ago. The account shows **$121.00 in the over-90
band** and separately holds a **$45.00 credit**. **Netting to $76.00 was
REJECTED**, and the reason is the reason the bands exist: netting loses the AGE
of the debt — $76 sitting in one band when $121 is genuinely over ninety days
old — so collections, disconnection notices, the `PAST DUE 60+` tile and
BR-CUS-016's derived display would all understate a real delinquent account.
**Refusing the row was also rejected**: a large migration may carry thousands.

So a credit cell contributes **0.00** to its bucket and its absolute value to
`credit`; the positive buckets in the same row load and age normally; and
`accounts.balance` stays GT-16's *"Σ buckets, exact"* — which is the DEBIT
position, exactly as `apps.payments.selectors.account_credit_position` is a
separate figure from what an account owes (`credit.py`: *"mixing the two is how
a credit balance comes to be reported as a reduced bill"*).

════════════════════════════════════════════════════════════════════════════
⛔ WHAT AN OPENING CREDIT BOOKS TO IS **NOT SIGNED** — OQ-353
════════════════════════════════════════════════════════════════════════════
BR-CUS-049 names ONE opening shape — *"AR ↔ opening-balance clearing"* — and
US-LED-001's seventeen-row contract table has exactly one opening row: **DR 1200
AR / CR opening-balance clearing**. BR-CUS-061 takes a credit OUT of AR (it is
an account credit, not a receivable), and the overpayment pattern it names books
its credit leg to `customer_credit_balance` (2400), a LIABILITY — but that leg
arises when CASH is received, and at cutover no cash is received: the money
reached the utility inside the system being left.

So **no signed document states the GL pair a carried opening credit posts**, nor
whether it joins GT-16's ❄️ frozen batch tie-out (whose worked batch is
all-debit: 1,213 accounts → **$184,320.55**). `apps/ledger/opening_balances.py`
already refuses a negative balance for exactly this reason — *"Writing the
mirror would be inventing a contract row"* — and B18 §5.9.3b says the same in
so many words: the correction *"does not specify the mechanism … whether it
posts in the same opening batch as the debit buckets, and how it tie-outs
against GT-16's frozen batch total"*.

**That is `OQ-353`, and `post_opening_credit_entry` refuses by name rather than
choosing.** The row still LOADS — that half IS ruled — and the unlanded credit
is audited per account (rule 7) so an operator can find every cent of it.

⚠ **AND THE CARRIER ITSELF IS UNBUILT, REPORTED NOT IMPLIED (hard-won law 2).**
EP-PAY-02 §1 states the shape — *"Credits are payment-type rows (B2
`payment_type` credit), append-only; application writes `allocations` rows at
bill issue"* — and `apps.payments.selectors.account_credit_position` already
sums exactly those rows. **Nothing in this product writes one.** `record_payment`
hardcodes `type='payment'` and books a cash leg; no payments service publishes a
credit writer, so there is no lawful call for customers to make (cross-module
writes are forbidden — B1/B8). Until payments publishes one, this module
measures the credit, audits it and reports it; it does not invent a table to put
it in.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.customers import models, seams, services
from core import audit as core_audit
from core import errors

#: BR-CUS-048's four bands, in the order they age.
BUCKET_FIELDS: tuple[tuple[str, str], ...] = (
    ("ob_current", models.AccountOpeningBucket.BUCKET_CURRENT),
    ("ob_31_60", models.AccountOpeningBucket.BUCKET_31_60),
    ("ob_61_90", models.AccountOpeningBucket.BUCKET_61_90),
    ("ob_90_plus", models.AccountOpeningBucket.BUCKET_90_PLUS),
)

#: ⛔ The open question this module refuses to guess at, named as a constant so
#: no call site decides it by accident and so a grep for the id finds the code
#: waiting on it (the `services.OQ_ROLLBACK_OPENING` posture).
#:
#: ⚠ **It replaced `OQ_OPENING_CREDIT = "OQ-065"`, which was DEF-620** — a
#: CLOSED question cited as open, refusing rows a signed rule said must load.
#: OQ-353 is a genuinely open one, and it is a NARROWER question: not *"what
#: happens to a credit row"* (BR-CUS-061 and BR-CUS-077 answer that) but *"what
#: journal entry does a carried opening credit post"*.
OQ_OPENING_CREDIT_LANDING = "OQ-353"

#: hard rule 7 — every money action writes `audit_log`, and an opening credit
#: the product cannot yet place is exactly the money an operator must be able to
#: find. One row per account, carrying the figure, the cells it came from and
#: the OQ that is holding it.
#: ⚠ `…_imported`, deliberately NOT `…_carried`: the row is READ and RECORDED
#: here, and the payload says `"carried": False`, because no payments row holds
#: it yet. An action code that claimed the carrying would be hard-won law 1 in
#: the audit trail — the one place a comment claiming a guarantee does real harm.
AUDIT_OPENING_CREDIT = "account.opening_credit_imported"

ZERO = Decimal("0")

#: What a carried opening credit CANNOT yet do, carried on the position rather
#: than stated in a docstring — the `opening_balances.OPENING_UNAVAILABLE` /
#: `credit.CREDIT_UNAVAILABLE` discipline, so a caller never has to infer an
#: absence and a reviewer never has to take a comment's word for it (law 1).
OPENING_CREDIT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "opening_credit_has_no_ledger_entry",
        "br_ref": f"BR-CUS-049 · BR-CUS-061 · {OQ_OPENING_CREDIT_LANDING}",
        "detail": "BR-CUS-049 states ONE opening shape (AR <-> opening-balance clearing) and "
        "BR-CUS-061 takes a credit OUT of AR. No signed document states the GL pair a carried "
        "opening credit books to, nor whether it joins GT-16's frozen batch tie-out, so "
        "`post_opening_credit_entry` refuses by name. The DEBIT buckets post exactly as before; "
        "only the credit's own entry is withheld.",
    },
    {
        "code": "no_payments_writer_carries_an_opening_credit",
        "br_ref": "BR-CUS-061 · BR-PAY-010 · EP-PAY-02 US-PAY-007",
        "detail": "EP-PAY-02 states the shape — *Credits are payment-type rows (B2 payment_type "
        "credit), append-only* — and `apps.payments.selectors.account_credit_position` already "
        "sums those rows. NOTHING in the product writes one: `payments.services.record_payment` "
        "hardcodes type='payment' and books a cash leg that a cutover has no cash for. Customers "
        "may not write another module's table (B1/B8), so the credit is measured, audited and "
        "reported here until payments publishes a writer.",
    },
)


def _amount(raw: Any, *, field: str, account_ref: str | None) -> Decimal:
    """One bucket cell → a SIGNED Decimal. Blank is 0.00 (US-CUS-021 TC-5).

    **Non-numeric is the only refusal left here**, and that is the whole of
    DEF-620: a clerk fixes `abc` by retyping it, and nobody fixes −45.00,
    because it is not wrong. It is a customer in credit, and BR-CUS-061 has said
    what happens to one since 2026-08-08. The sign is preserved and
    `opening_position` — which can see the whole row — is what splits it.
    """
    if raw is None or str(raw).strip() == "":
        return ZERO
    text = str(raw).strip().replace(",", "")
    try:
        return Decimal(text)
    except Exception as exc:  # noqa: BLE001 — any parse failure is one refusal
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.import.opening_bucket_not_numeric",
            params={"field": field, "value": str(raw), "account": account_ref or ""},
        ) from exc


def opening_position(mapped: dict[str, Any], *, account_ref: str | None = None) -> dict[str, Any]:
    """One mapped import row → its DEBIT buckets and its CREDIT, side by side.

    Returned rather than written so the VALIDATE stage can call it for its
    refusals without touching the database — the same figures the LOAD stage
    will write, derived once.

    **BR-CUS-077 is the whole shape of this function.** A cell is either aged
    debt or credit and it is never both:

      * a POSITIVE cell is its band's debit and ages from that band's floor;
      * a NEGATIVE cell contributes **0.00** to its band (BR-CUS-061: *"aging
        buckets stay debit-only"*) and its ABSOLUTE VALUE to `credit`.

    On the PO's own worked row — `ob_current = -45.00`, `ob_90_plus = 121.00` —
    that yields `total = 121.00` in the over-90 band and `credit = 45.00`, and
    **never the 76.00 the PO rejected**, because netting would leave $76 sitting
    in one band when $121 is genuinely over ninety days old.

    The keys, and why each is a fact rather than something a caller re-derives:

      ``buckets``      all four bands, DEBIT amounts only, in ageing order.
      ``total``        Σ debits — GT-16's *"Σ buckets, exact — no recompute"*,
                       and therefore what `accounts.balance` caches.
      ``overdue``      Σ debits outside `Current` — GT-16's 183.10, the day-one
                       late-fee base (GT-8 computes the fee; billing owns that).
      ``credit``       a POSITIVE Decimal: what the utility holds FOR this
                       customer. Never subtracted from `total`.
      ``credit_cells`` which columns it came from, so a screen can answer *"where
                       did this come from?"* the way `credit.CreditSource` does
                       rather than showing one number nobody can explain.
      ``has_credit``   carried rather than inferred from `credit != 0`, for the
                       same reason `empty` is: an explicit fact cannot be read
                       two ways at three call sites.
      ``empty``        NO BUCKET POSITION — all four bands blank or credit. It
                       means exactly what it has always meant (balance 0.00, no
                       bucket rows, no opening JE — US-CUS-021 TC-5), so a
                       credit-only row is correctly absent from the ledger batch
                       and GT-16's all-debit tie-out is untouched by construction.
    """
    buckets: list[tuple[str, Decimal]] = []
    credit_cells: list[tuple[str, Decimal]] = []
    total = ZERO
    credit = ZERO
    for field, bucket in BUCKET_FIELDS:
        value = _amount(mapped.get(field), field=field, account_ref=account_ref)
        if value < ZERO:
            # BR-CUS-061 — debit-only. `-value` rather than `abs()` so the sign
            # flip is visibly the only arithmetic performed on it; no rounding,
            # no scaling, and the Decimal that arrived is the Decimal carried.
            credit_cells.append((field, -value))
            credit += -value
            value = ZERO
        buckets.append((bucket, value))
        total += value
    overdue = sum(
        (
            value
            for bucket, value in buckets
            if bucket in models.AccountOpeningBucket.OVERDUE_BUCKETS
        ),
        ZERO,
    )
    return {
        "buckets": buckets,
        "total": total,
        "overdue": overdue,
        "credit": credit,
        "credit_cells": tuple(credit_cells),
        "has_credit": credit > ZERO,
        "empty": all(value == ZERO for _bucket, value in buckets),
        "credit_problems": OPENING_CREDIT_UNAVAILABLE if credit > ZERO else (),
    }


def write_opening_buckets(
    *,
    account_id: Any,
    account_ref: str | None,
    mapped: dict[str, Any],
    as_of: date,
    currency: str,
    import_run_id: Any = None,
    is_sample: bool = False,
) -> dict[str, Any]:
    """Write one account's four bucket rows, and CARRY its opening credit.

    Append-only (hard rule 4). Returns the position so the caller can cache
    `accounts.balance` and build the ledger batch from the SAME figures — never
    a second derivation.

    **Two writes, and they are deliberately not one:**

      * the four DEBIT bucket rows, when there is a bucket position at all;
      * an `audit_log` row for the CREDIT, when there is one (rule 7).

    A credit-only row therefore writes NO bucket row — BR-CUS-061's debit-only
    half — and still returns a position carrying `credit`, so the account loads
    (BR-CUS-061's second half, which is DEF-620) and the money is on the record.
    """
    position = opening_position(mapped, account_ref=account_ref)
    if not position["empty"]:
        tenant_id = services._tenant_id()
        models.AccountOpeningBucket.objects.bulk_create(
            [
                models.AccountOpeningBucket(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    import_run_id=import_run_id,
                    as_of=as_of,
                    bucket=bucket,
                    amount=amount,
                    currency=currency,
                    is_sample=is_sample,
                )
                for bucket, amount in position["buckets"]
            ]
        )
    if position["has_credit"]:
        carry_opening_credit(
            account_id=account_id,
            account_ref=account_ref,
            position=position,
            as_of=as_of,
            currency=currency,
            import_run_id=import_run_id,
        )
    return position


def carry_opening_credit(
    *,
    account_id: Any,
    account_ref: str | None,
    position: dict[str, Any],
    as_of: date | None,
    currency: str,
    import_run_id: Any = None,
    actor: Any = None,
) -> dict[str, Any]:
    """BR-CUS-061's carried account credit — as far as the signed rules reach.

    ⚠ **THIS DOES NOT CREATE THE CREDIT ROW, AND SAYING SO IS THE POINT (law
    2).** The carrier is a `payments` row of `type='credit'` (EP-PAY-02 §1, B2
    §1 `payment_type`) and **payments publishes no writer for one** — a cutover
    credit is money this system never received, so `record_payment`'s cash leg
    is not it. Customers may not write payments' table (B1/B8, hard rule: cross-
    module writes are forbidden), so there is nothing lawful to call.

    What it DOES do is make the money impossible to lose: **one `audit_log` row
    per account** naming the figure, the columns it came from, the cutover date
    and the OQ holding it (hard rule 7 — *every money action writes audit_log*,
    and money the product cannot yet place is exactly the money an operator has
    to be able to find). Returns the same statement of absence the position
    carries, so a caller reports it rather than inferring it.

    Worked, on BR-CUS-077's own row: account `A-12103` loads with **121.00** of
    over-90 debt in its buckets and an audit row reading **45.00** of opening
    credit, `ob_current`, cutover 2026-08-31, `OQ-353`.
    """
    core_audit.money_action(
        actor,
        AUDIT_OPENING_CREDIT,
        "account",
        str(account_id),
        after={
            "account_ref": account_ref,
            "credit": str(position["credit"]),
            "currency": currency,
            "cells": [[field, str(amount)] for field, amount in position["credit_cells"]],
            "as_of": str(as_of) if as_of else None,
            "import_run_id": str(import_run_id) if import_run_id else None,
            # Named IN the row, not only in this docstring: an auditor reading
            # the trail three months from now must be told why the credit is
            # sitting here rather than on the account.
            "oq": OQ_OPENING_CREDIT_LANDING,
            "br_ref": "BR-CUS-061 · BR-CUS-077",
            "carried": False,
        },
    )
    return {"carried": False, "credit": position["credit"], "problems": OPENING_CREDIT_UNAVAILABLE}


def post_opening_credit_entry(*_args: Any, **_kwargs: Any):
    """⛔ **OQ-353 — what a carried opening credit BOOKS TO is not signed.**

    The DEBIT side is: BR-CUS-049 and US-LED-001's contract table both state
    **DR 1200 AR / CR opening-balance clearing**, and `post_opening_batch_from_
    import` below posts it unchanged. A CREDIT position is not that entry with
    the signs swapped, because BR-CUS-061 rules the credit is **not a
    receivable** at all — it is an account credit, which the overpayment pattern
    books to `customer_credit_balance` (2400) **at the moment cash is received**.
    At cutover no cash is received here; the money reached the utility inside the
    system being left, so the other leg is not cash either.

    Three shapes are arguable and NONE is written down:

      (a) DR opening-balance clearing / CR customer_credit_balance — the credit
          is a liability from day one, symmetric with the debit batch;
      (b) DR opening-balance clearing / CR AR — BR-CUS-049's literal pair with
          the direction flipped, which puts a credit customer into receivables;
      (c) no opening entry at all — the credit reaches the books only when it is
          applied to a bill, which leaves the clearing account not tying out.

    They also disagree about GT-16's ❄️ FROZEN batch line (*"Σ clearing credits =
    Σ imported buckets"*, 1,213 accounts → **$184,320.55**): under (a) a credit
    would DEBIT clearing inside the same batch and the assertion `ar_debits ==
    clearing_credits` would have to be restated, which is a change to a
    finance-signed figure's meaning and needs a HUMAN-GUIDE §6 re-sign.

    So this refuses BY NAME. `apps/ledger/opening_balances.py` refuses the same
    case from the other side — *"Writing the mirror would be inventing a contract
    row"* — and this is the boundary guard, so no future caller can reach a
    guessed DR/CR by another door (CLAUDE.md prime directive).
    """
    raise NotImplementedError(
        f"{OQ_OPENING_CREDIT_LANDING}: no signed rule states the journal entry a carried "
        "opening credit posts (BR-CUS-049 names AR <-> clearing; BR-CUS-061 takes a credit "
        "out of AR), nor whether it joins GT-16's frozen batch tie-out."
    )


def deposit_rows_for_accounts(account_ids: Any) -> list[dict[str, Any]]:
    """The migrated-deposit half of a batch, read off the accounts themselves.

    ⚠ **THERE IS NO `import_run_id` ON `accounts`, AND THIS IS WHY THE CALLER
    PASSES IDS.** The AR half of a held batch is rebuilt from
    `account_opening_buckets`, which carries the run (`confirm_opening_changeover`
    below). A deposit has no such row — it is two columns on the account
    (`IMPORT_ACCOUNT_FIELDS`, US-CUS-023) — so the set of accounts this run
    created is metering's fact, held on its own `import_rows.created_record_id`,
    and it is handed here rather than inferred. Inferring it from the bucket rows
    would silently drop every account that holds a deposit and owes nothing,
    which on the seeded estate is THREE of the five that hold one.

    Tenant-scoped like every other read here (CLAUDE.md rule 1). Accounts
    holding nothing are ABSENT rather than zero-valued: a 0.00 entry is a
    journal entry for money that did not move and can never be corrected away.
    """
    ids = [str(value) for value in (account_ids or []) if value]
    if not ids:
        return []
    rows = models.Account.objects.filter(
        tenant_id=services._tenant_id(), pk__in=ids
    ).values_list("pk", "account_no", "deposit_on_file", "deposit_received_on")
    return [
        {
            "account_id": str(pk),
            "account_ref": account_no,
            "held": Decimal(held),
            "received_on": received_on,
        }
        for pk, account_no, held, received_on in rows
        if held and Decimal(held) != ZERO
    ]


def confirm_opening_changeover(
    *,
    actor: Any = None,
    import_run_id: Any,
    changeover_on: date,
    deposit_account_ids: Any = None,
) -> dict[str, Any] | None:
    """⛔ **THE HELD BATCH, RE-DATED AND THEN POSTED — ONCE** (PO ruling
    2026-08-27; `import_runs.confirm_changeover_date` is the only caller).

    An accounts import that ran without a changeover date wrote its
    `account_opening_buckets` rows under a PROVISIONAL date and called the
    ledger **not at all**. This puts the real date on those rows and hands the
    batch over.

    ⚠ **RE-DATING IS LAWFUL HERE AND NOWHERE ELSE, AND THE MODEL'S OWN
    DOCSTRING SAYS WHY.** `AccountOpeningBucket` is append-only *"because the
    moment US-CUS-022 posts, an immutable journal entry exists against these
    numbers"* (hard rule 4). **No such entry exists while the batch is held** —
    that is the entire reason the hold exists, and it is what makes the PO's
    *"we can always change this date later"* a true statement rather than a
    kindness. The moment this function returns, the date is permanent and a
    correction is a J6 adjustment like any other.
    ⚠ **ONLY `as_of` MOVES. NO AMOUNT IS TOUCHED**, so the ❄️ GT-16 tie-out (Σ AR
    debits = Σ clearing credits) is the same sum before and after — which is
    what lets this run inside one transaction with the posting.

    ⚠ **THE BATCH IS REBUILT FROM THE BUCKET ROWS, NOT FROM THE IMPORT ROWS.**
    They are the same figures by construction (`write_opening_buckets` wrote
    both from one position object), and reading the persisted rows means a
    confirmation days later cannot disagree with what was actually stored —
    two derivations of one number is how they come to differ.

    `None` when the ledger cannot answer, and the caller REFUSES rather than
    marking a batch posted whose journal entries do not exist (DEF-075).
    """
    tenant_id = services._tenant_id()
    # ⚠ **THE DEPOSIT HALF IS READ FIRST AND IS NOT CONDITIONAL ON A BUCKET
    # ROW** (DEF-1713). A run may have created accounts that hold a deposit and
    # owe nothing; returning early on "no buckets" would leave their liability
    # unposted for ever, with the changeover marked confirmed.
    held = deposit_rows_for_accounts(deposit_account_ids)
    rows = models.AccountOpeningBucket.objects.filter(
        tenant_id=tenant_id, import_run_id=import_run_id
    )
    if not rows.exists() and not held:
        return {
            "posted": 0,
            "ar_debits": str(ZERO),
            "clearing_credits": str(ZERO),
            "deposits_posted": 0,
            "deposit_credits": str(ZERO),
        }
    rows.update(as_of=changeover_on)

    totals: dict[str, Decimal] = {}
    refs: dict[str, str | None] = {}
    currency: str | None = None
    for account_id, account_no, amount, ccy in rows.values_list(
        "account_id", "account__account_no", "amount", "currency"
    ):
        key = str(account_id)
        totals[key] = totals.get(key, ZERO) + Decimal(amount)
        refs.setdefault(key, account_no)
        currency = currency or ccy
    accounts = [
        {"account_id": key, "account_ref": refs.get(key), "balance": total}
        for key, total in totals.items()
        if total != ZERO
    ]
    return post_opening_batch_from_import(
        actor=actor,
        batch_id=import_run_id,
        cutover_on=changeover_on,
        imported_at=timezone.now(),
        currency=currency or services._tenant_currency(),
        accounts=accounts,
        deposits=held,
    )


def post_opening_batch_from_import(
    *,
    actor: Any = None,
    batch_id: Any,
    cutover_on: date,
    imported_at: datetime,
    currency: str,
    accounts: list[dict[str, Any]],
    deposits: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """US-CUS-022 — hand the whole run to the ledger, once, and report the tie-out.

    ⚠ **CUSTOMERS WRITES NO JOURNAL LINES.** It builds the contract and calls
    `apps.ledger.opening_balances.post_opening_batch`; the posting service writes
    (hard rule 5, B1). This function is the boundary and nothing past it belongs
    to this module.

    `accounts` is the list this run's LOAD stage accumulated —
    `{"account_id", "account_ref", "balance"}` per account with a non-empty
    opening position. Accounts with no position are absent, not zero-valued: a
    zero JE is a journal entry that says nothing and can never be corrected away
    (hard rule 4).

    Returns None when the ledger cannot answer, and the caller REFUSES rather
    than reporting a migration whose books do not exist (the DEF-075 lesson).

    ⛔ **THIS BATCH IS ALL-DEBIT, AND THAT IS NOT AN OVERSIGHT.** An account
    whose opening position is a CREDIT has no bucket rows (BR-CUS-061), so it is
    `empty`, so it never enters `accounts` here — the frozen GT-16 tie-out (Σ AR
    debits = Σ clearing credits, batch **$184,320.55**) is therefore untouched by
    construction rather than by a filter someone has to remember. What a credit
    position posts is `post_opening_credit_entry`'s refusal and **OQ-353**.

    ⚠ **`deposits` IS THE SECOND MONEY COLUMN ON THE SAME ROW — DEF-1713.**
    `{"account_id", "account_ref", "held", "received_on"}` per account holding a
    migrated deposit. It reaches a SECOND contract in the same module
    (`post_opening_deposit_batch`: DR opening clearing / CR deposit liability,
    BR-CUS-670) and it does NOT join GT-16's AR tie-out — the two sums are kept
    apart deliberately, because ❄️ GT-16 is finance-signed as *Σ opening JEs =
    Σ imported BUCKETS* and folding a deposit into it would move a frozen figure.
    Each batch ties out against its own sides, and both are reported.

    ⚠ **IT IS ONE HANDOFF, NOT TWO.** Same `batch_id`, same `cutover_on`, same
    transaction, same caller — the AR half and the deposit half of one migration
    are posted together or not at all. Splitting them across two calls is how a
    utility ends up with its receivables migrated and its deposits not, which is
    the defect this parameter exists to close.

    ⛔ **AN AR-ONLY RUN AND A DEPOSIT-ONLY RUN ARE BOTH LAWFUL.** A migrated
    account may hold a deposit and owe nothing (three of the seeded estate's
    five do), so `accounts` empty with `deposits` non-empty must post. The
    early return fires only when BOTH are empty.
    """
    held = [row for row in (deposits or []) if row.get("held")]
    if not accounts and not held:
        return {
            "posted": 0,
            "ar_debits": str(ZERO),
            "clearing_credits": str(ZERO),
            "deposits_posted": 0,
            "deposit_credits": str(ZERO),
        }
    fn = seams.resolve("ledger", "post_opening_batch", kind="opening_balances")
    deposit_fn = seams.resolve("ledger", "post_opening_deposit_batch", kind="opening_balances")
    if fn is None or deposit_fn is None:
        return None
    from apps.ledger import opening_balances as _ob

    result = (
        fn(
            batch_id=batch_id,
            cutover_on=cutover_on,
            imported_at=imported_at,
            currency=currency,
            accounts=tuple(
                _ob.OpeningAccount(
                    account_id=row["account_id"],
                    account_ref=row.get("account_ref"),
                    balance=row["balance"],
                )
                for row in accounts
            ),
            actor=actor,
        )
        if accounts
        else None
    )
    # ⚠ **THE SECOND BATCH IS THE SAME HANDOFF, NOT A SECOND ONE** — see the
    # docstring. One `batch_id`, one `cutover_on`, one caller, two contracts.
    deposit_result = (
        deposit_fn(
            batch_id=batch_id,
            cutover_on=cutover_on,
            imported_at=imported_at,
            currency=currency,
            deposits=tuple(
                _ob.OpeningDeposit(
                    account_id=row["account_id"],
                    account_ref=row.get("account_ref"),
                    held=row["held"],
                    received_on=row.get("received_on"),
                )
                for row in held
            ),
            actor=actor,
        )
        if held
        else None
    )
    return {
        "posted": len(accounts),
        "ar_debits": str(ZERO if result is None else result.ar_debits),
        "clearing_credits": str(ZERO if result is None else result.clearing_credits),
        "deposits_posted": len(held),
        "deposit_credits": str(ZERO if deposit_result is None else deposit_result.deposit_credits),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-058 W3 · BR-MET-1030 — THE PREMISES IMPORT'S OWNER ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **PO RULING 2026-09-01, VERBATIM:** *"If owner name is given and one
# identify given - DL, SSN, Phone or Tax ID - then you create master account and
# Customer ID - otherwise dont create anything"*. It also closes `CR-056` task
# 24 — *"Premises import creates the Master Account — ruled once, never built"* —
# which is hard-won law 2 in the open: `ensure_owner_master_account` has worked
# since 2026-09-01 and **nothing walked through it**, so `DEF-2902` / `DEF-2903`
# report that no master account in the product has its owner link written.
#
# ⚠ **WHY THIS IS A SEAM IMPLEMENTER AND NOT A SECOND CREATION PATH.** It calls
# `services.create_master_account` — the ONE door — and adds nothing to it. What
# it exists for is the ROLE, and the reason is the same one that made
# `create_from_import` undecorated: the metering runner's stages are role-gated
# at their OWN doors (`@require_role` on `load`), and a DEFERRED load then runs
# in a worker carrying `_JobActor`, which holds *"an id, and no role, BY
# DESIGN"*. Handing that actor to a `@require_role`-decorated function refuses
# every row of every large migration — and it refuses them where the runner
# catches refusals and counts them, so the receipt would read *"9,881 owner
# accounts refused"* with no clue why. That is `DEF-1108`'s exact shape.
#
# ⚠ **SO THE ROLE CHECK IS NOT SKIPPED — IT IS MOVED TO WHERE THE ROLE STILL
# EXISTS**, which is `DEF-1108`'s own remedy: the question becomes *"was this
# work authorised by a role-checked caller?"* rather than *"does this actor hold
# a role right now?"*, and `import_runs.load()` answered it at the door before
# anything was enqueued. A caller reaching this function has already passed
# `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` one stage earlier.
#
# ⚠ **AND IT IS CUSTOMERS CALLING PAST ITS OWN DECORATOR, NEVER METERING DOING
# IT.** `__wrapped__` on another module's service would be one module reaching
# around another module's guard, which B1 forbids as plainly as it forbids a
# cross-module write. Here the module that WROTE the guard is the module that
# states when it does not apply, in its own file, with its reason.


def create_master_account_from_import(
    *, actor: Any = None, payload: dict[str, Any]
) -> dict[str, Any]:
    """One premises import row → the owner's master account and Customer #.

    The whole guard set travels with it because the door is unchanged:
    `BR-CUS-017`'s family, `BR-CUS-1011`'s one-owner-account-per-address,
    `BR-CUS-1010`'s hang-off-the-address, and the customer resolution the door
    performs — match first, create only on no match, and only where an
    identifier is present (`BR-CUS-1023`, and `CR-058`'s governing ruling).

    ⚠ **IT RESOLVES NO CUSTOMER ITSELF.** The `customer` block is evidence
    assembled from the operator's spreadsheet and handed over; a matcher on this
    side would be the second copy `CR-058` exists to prevent.

    ⚠ **THE DOOR'S BODY, NOT `create_master_account.__wrapped__` (`DEF-CUS-9132`,
    2026-10-02).** `__wrapped__` was the guarded door's whole body, and
    `DEF-CUS-9078` then put a call to the role-guarded
    `service_request_service.link_customer` in it — so this job path reached a
    `@require_role` function and G140 went red. Recording a request's customer
    is a request-path act and now happens only in the guarded
    `create_master_account`, after `_create_master_account` returns; this calls
    `_create_master_account` itself, which is everything the door does and
    nothing that needs a role. Same reasoning as above: customers stating, in its
    own file, when its own guard does not apply.
    """
    from apps.customers import services

    return services._create_master_account(actor, dict(payload or {}))
