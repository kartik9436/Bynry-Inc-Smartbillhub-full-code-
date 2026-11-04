# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · CLAUDE.md hard rule 1 ·
#           RBR-03 (policy is read, never duplicated)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → payments — payments, deposits, plans in flight, bank lines. READ ONLY.

The collections ladder, cash application and bank reconciliation read here —
and **the ladder itself lives in payments' own settings**, which this module
reads and never duplicates (`RBR-03`). A runbook that copied the ladder into its
own parameters would give a utility two answers to one question and no way to
tell which was in force.

⚠ **FIVE OF THE THIRTEEN PORTS ARE PAYMENTS'** — `apply_payment`, `post_credit`,
`raise_refund`, `record_match` and `schedule_retry` — so payments is the module
this one can do the most to, and the one where the dry half of phase 4 earns its
keep. Every one of them is a declaration with **no writer bound** until then.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; each later wave brings the reads its own
runbooks actually need. A selector written here now would be a function nothing
calls (hard-won law 2), and naming one in prose that `payments` does not expose
would fail `G20` — the guard that caught `DEF-075`. What this module will need
and `payments` does not offer today is inventoried in
`17-runbooks/13-selector-inventory.md`, and **`payments` adds each of them** —
never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="payments",
    pair="operations → payments",
    crosses="payments, deposits, plans in flight, bank lines",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────


def active_tenders() -> list[dict[str, object]]:
    """The tender types a clerk may record a payment against, live only.

    `apps.payments.selectors.active_payment_methods`. Deactivated rows are
    excluded by that selector, which is what runbook 1 step 10 needs: a tenant
    whose only tender has been retired cannot take money, and a check that
    counted retired rows would report a working till.
    """
    from apps.payments import selectors as payments_selectors

    return list(payments_selectors.active_payment_methods())


# ── CR-075 wave P · the reads runbooks 10 and 14 make (US-RBS-022 · US-RBS-026) ──
#
# ⚠ **THREE OF THESE FIVE RESOLVE OUTSIDE `selectors.py`, AND THAT IS LAWFUL
# HERE WHILE IT WOULD NOT BE FOR A LATE-BOUND SEAM.** `13-selector-inventory.md`
# §2 records `collections_read.py` as a **WRONG DOOR**: a seam that resolves
# `apps.<module>.<kind>.<name>` through a resolver helper only ever looks in
# `selectors` and `services`, so a third file answers `None` and `None` reads as
# *"nothing to report"* — `DEF-035`'s shape. **These call the owning module by a
# plain import instead**, exactly as `active_tenders` above does, so there is no
# resolver to mislead. The three are
# `apps.payments.bankrec_read.statement_review`,
# `apps.payments.bankrec_read.statement_imports` and
# `apps.payments.open_bills.open_bill_position`; the other two are
# `apps.payments.selectors.payment_import_batch_dict` and
# `apps.payments.selectors.payment_queryset`.
#
# ⚠ **ONE READ THIS MODULE WANTED AND `payments` DOES NOT PUBLISH:** a LIST of
# the import batches a person has uploaded. `payment_import_batch_dict` answers
# for ONE batch by id and nothing lists them. So runbook 10 takes the batch as a
# declared input rather than going looking — which is also the shape the Product
# Owner described on 2026-09-06 (*"it is human who will collect it and uplaod in
# system"*). Inventoried as `S-15`, owned by `payments`; nothing here reaches
# past the seam to compensate for it.


def import_batch(batch_id) -> dict[str, object] | None:
    """One uploaded remittance file, with every staged row — or `None`.

    `apps.payments.selectors.payment_import_batch_dict`, with `with_rows=True`.
    That selector recomputes its counts FROM the rows rather than reading the
    denormalised `counts` column, which is exactly what runbook 10 needs: the
    figure a clerk decides on, never a cache that may have drifted.

    ⚠ **`None` MEANS *no such file for this tenant*, AND THE RUNBOOK SAYS SO.**
    The selector raises for a batch that is missing OR belongs to another tenant,
    deliberately indistinguishable (hard rule 1, `G4`). A runbook that let that
    escape would end a run with a stack trace where the honest answer is one
    sentence — so it is caught HERE, once, and every caller gets an absence it
    can render.
    """
    from apps.payments import selectors as payments_selectors
    from core import errors

    if batch_id in (None, ""):
        return None
    try:
        return dict(payments_selectors.payment_import_batch_dict(batch_id, with_rows=True))
    except (errors.NotFoundError, ValueError, TypeError):
        # A malformed id is the same fact to a clerk: there is no such file.
        return None


def tenant_currency() -> str:
    """The tenant's ONE currency code (`BR-TEN-042`), as `CHAR(3)`.

    `apps.payments.settings_seam.tenant_currency`. ⚠ **THIS EXISTS BECAUSE
    `payment_import_batch_dict` CARRIES NO CURRENCY AND A FIRST BUILD ASSUMED IT
    DID.** Runbook 10 composed *"182.40 more than this account owes"* with an
    empty code where the code should be — hard rule 2's *currency beside every
    amount*, missing, and caught only by a PostgreSQL case that asserted the
    whole sentence. `bankrec_read._currency` reads it exactly this way and
    records the reason: *"a wrong symbol on a Canadian utility's banking is a
    money defect wearing a formatting costume."* It is never defaulted to `USD`
    here.
    """
    from apps.payments import settings_seam

    return str(settings_seam.tenant_currency() or "")


def payments_recorded_between(account_ids, start, end) -> list[dict[str, object]]:
    """Every payment already recorded for these accounts inside a date window.

    Runbook 10 step 4's evidence, and the only thing that can tell a file lodged
    twice from a customer who genuinely paid twice.
    `apps.payments.selectors.payment_queryset` is the tenant-scoped queryset the
    payments list itself is built on; rows are flattened to plain dicts here so
    no `Payment` instance ever crosses the seam.

    ⚠ **THE WINDOW IS ON `posted_at`, NOT ON `created_at`.** A file lodged twice
    a week apart carries the SAME payment date both times, and the second lodging
    is the one a clerk must be shown. `created_at` would answer *when did we type
    it in*, which is a different question and the wrong one.
    """
    from apps.payments import selectors as payments_selectors

    ids = [str(one) for one in account_ids if one]
    if not ids:
        return []
    rows = payments_selectors.payment_queryset().filter(
        account_id__in=ids, posted_at__date__gte=start, posted_at__date__lte=end
    )
    return [
        {
            "payment_id": str(one.pk),
            "account_id": str(one.account_id),
            "amount": str(one.amount),
            "currency": one.currency,
            "status": one.status,
            "confirmation": one.confirmation,
            "posted_on": one.posted_at.date().isoformat() if one.posted_at else None,
        }
        for one in rows
    ]


def open_bill_position(account_id) -> dict[str, object] | None:
    """What one account still owes, oldest bill first — or `None` if unreadable.

    `apps.payments.open_bills.open_bill_position`. Runbook 10 step 5 compares the
    money in the file against `total_open` to flag an over- or a short-payment,
    and **it flags rather than guesses**: an account with nothing open answers
    `total_open` `0.0000`, which is a measured fact, and the whole payment then
    carries as account credit — something a clerk has to be TOLD, not have
    decided for them.
    """
    from apps.payments import open_bills

    if account_id in (None, ""):
        return None
    try:
        return dict(open_bills.open_bill_position(account_id=account_id))
    except Exception:  # noqa: BLE001 — see below
        # ⚠ **BROAD ON PURPOSE, AND NARROW IN EFFECT.** This read walks
        # `payments → billing` through another module's seam and can refuse for
        # reasons this module has no vocabulary for: a missing account, a bill
        # carrying no currency, a book that will not open. Runbook 10 must not
        # lose 137 good rows because ONE account's balance could not be read, so
        # the caller records *"could not read the balance"* against that one
        # payment and carries on. **Nothing is skipped silently** — the absence
        # is a row on the screen with a reason beside it.
        return None


def statement_imports(limit: int = 50) -> list[dict[str, object]]:
    """The bank statements a person has imported, most recent first.

    `apps.payments.bankrec_read.statement_imports`. Runbook 14 takes the
    statement as a declared input and falls back to the most recent one when a
    person starts the run with nothing chosen.
    """
    from apps.payments import bankrec_read

    return [dict(one) for one in bankrec_read.statement_imports(limit=limit)]


def statement_review(statement_import_id) -> dict[str, object] | None:
    """Every line of one statement, with the batch it is tied to or why not.

    `apps.payments.bankrec_read.statement_review`. It is recomputed from the
    PERSISTED link rather than replayed through the matcher, so a statement
    re-read an hour after a clerk tied a line by hand shows what is true NOW —
    which is the only thing a tie-out may be built on.

    `None` where the statement is not this tenant's or does not exist, for
    `import_batch`'s reason: a runbook renders an absence, never a traceback.
    """
    from apps.payments import bankrec_read
    from core import errors

    if statement_import_id in (None, ""):
        return None
    try:
        return dict(bankrec_read.statement_review(statement_import_id))
    except (errors.NotFoundError, errors.BizError, ValueError, TypeError):
        return None


# ── CR-075 wave L · the reads runbook 8 makes (US-RBS-010) ────────────────
#
# Added with `definitions/dunning.py` in the same commit. Both calls resolve
# `apps.payments.collections_read.ladder_board` and
# `apps.payments.ladder.LADDER_RUNGS`, which `payments` already publishes —
# nothing is reimplemented here and nothing new is asked of that module.


def collections_ladder_board(
    *,
    as_of,
    account_ids=None,
    medical_hold_account_ids=(),
) -> dict[str, object]:
    """WHO IS AT WHICH RUNG AND WHAT GOES NEXT — **without stepping the ladder**.

    `apps.payments.collections_read.ladder_board`. ONE call for the whole pinned
    set rather than one per account, which is why runbook 8's tier step is a
    `set` step: 1,004 accounts are one read here and 1,004 reads if it were
    written per record.

    ⚠ **THE LADDER'S LAW IS PAYMENTS' AND NONE OF IT IS COPIED INTO THIS
    MODULE.** `BR-PAY-017`'s five rungs, the $25.00 balance floor
    (`OQ-137`/`OQ-157`), the medical hold (`A15` via `BR-CUS-039`), the plan
    pause (`BR-CUS-043`), the partial-payment pause and hard rule 6's same-day
    guard are all decided inside `ladder.decide`, which is PURE — every figure
    arrives as an argument, so the board a clerk previews and the pass a runbook
    takes cannot disagree. A runbook that re-derived any of that would be a
    second copy of a signed rule, living where payments' reviewers never read
    it.

    ⚠ **`as_of` IS AN ARGUMENT AND NEVER A CLOCK READ** (`BR-TEN-043`, gate
    `G6`): a run re-taken for last Tuesday must take last Tuesday's answer, and
    a backdated pass against an account that has since climbed a rung must not
    post a letter to a customer who has moved on.

    ⚠ **`medical_hold_account_ids` IS PASSED IN, NEVER INFERRED.** `payments`
    publishes no medical-hold selector and a clinical fact does not belong in
    that module — the posture `apps/payments/notices.py` already takes. Runbook
    8 gets it from its own guard, which is where an absolute exclusion belongs
    (`BR-RBS-012`).
    """
    from apps.payments import collections_read

    return collections_read.ladder_board(
        as_of=as_of,
        account_ids=account_ids,
        medical_hold_account_ids=tuple(medical_hold_account_ids),
    )


def ladder_rungs() -> tuple[str, ...]:
    """`BR-PAY-017`'s rungs, in the order it names them — payments' vocabulary.

    `apps.payments.ladder.LADDER_RUNGS`. Read rather than restated, because ONE
    vocabulary across the automatic engine and the manual modals is what makes
    *"no double-send"* possible at all: a runbook writing its own rung words
    would produce notices `account_collection_state` cannot recognise, and the
    same customer would climb two ladders at once.
    """
    from apps.payments import ladder

    return tuple(ladder.LADDER_RUNGS)


# ── CR-075 waves J and K · the reads runbooks 2 and 9 make ─────────────────


def open_invoice_positions() -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """Every OPEN bill this tenant holds, ONE ROW EACH, with what it still owes.

    `apps.payments.billing_seam.open_invoice_positions`, returning
    `(positions, problems)`.

    ⚠ **THE GRAIN IS THE BILL BECAUSE THE PRODUCT OWNER RULED IT ON 5 SEPTEMBER
    2026**, choosing *one line per open invoice* over *one balance per account*
    and *one bucket per age band* (`US-RBS-008` §8). It is not a presentation
    choice: a legacy trial balance is written at invoice grain, and an
    account-grain comparison nets two errors of opposite sign inside one
    customer and reports a tie — the one wrong answer a cutover check could give
    that an implementer would believe.

    ⚠ **NOTHING HERE IS RE-SUMMED.** `balance` is `amount_due − allocated`,
    which is the same subtraction `open_bill_position` does for one account and
    `outstanding_positions` does rolled up to one. Measured on the seeded
    utility on 2026-09-07: **32 open bills across 31 accounts, $7,661.92**, and
    the account-grain read's gross total is $7,661.92 to the cent. Three grains,
    one derivation.

    ⚠ **IT IS THE GROSS, NOT NET OF ACCOUNT CREDIT.** `outstanding_positions`
    nets credit off because CR-059 CS-38 ruled that the collection ladder must
    not chase money the utility is already holding. A cutover compares OUR bill
    against THEIR bill; credit on account is a separate line of the legacy
    trial balance, and netting it in here would move a difference from the
    credit line onto the receivables line where nobody could find it.
    """
    from apps.payments import billing_seam as payments_billing_seam

    positions, problems = payments_billing_seam.open_invoice_positions()
    return (
        tuple(
            {
                "account_id": str(one.account_id),
                "invoice_id": str(one.invoice_id),
                "number": one.number,
                "balance": one.balance,
                "issued_on": one.issued_on,
                "due_on": one.due_on,
                "currency": one.currency,
            }
            for one in positions
        ),
        tuple(dict(problem) for problem in problems),
    )


def unapplied_cash(period_start, period_end) -> dict:
    """Money the utility is HOLDING in this window that no bill has claimed.

    `apps.payments.selectors.unapplied_cash`. Runbook 9 step 3 reads the total,
    the payment count and the rows; `RB-109`'s parameter *Unapplied cash allowed*
    defaults to `$0.00`, so on most tenants any figure here is a finding.

    ⚠ **A DEPOSIT IS NOT UNAPPLIED CASH.** Payments excludes `purpose='deposit'`
    for a reason worth carrying across the seam: a deposit is money held on
    purpose, it sits in the deposit-liability account, and it has its own
    tie-out row (`BR-LED-007`). Counting it here would report every healthy
    utility as holding money nobody allocated and the runbook would refuse to
    close for ever — a check that can never pass, which is the shape hard-won
    law 7 names.

    Measured on the seeded utility, August 2026: **$1,195.05 across 3 payments**,
    the largest a $6,296.77 receipt with $1,049.46 still unapplied.
    """
    from apps.payments import selectors as payments_selectors

    answer = payments_selectors.unapplied_cash(period_start, period_end)
    return {
        "total": answer["total"],
        "payment_count": int(answer["payment_count"]),
        "currency": answer["currency"],
        "payments": tuple(dict(row) for row in answer["payments"]),
    }


# ── CR-075 wave R′ · the reads runbooks 15, 17, 25 and 26 make ────────────
#
# `US-RBS-027` · `US-RBS-029` · `US-RBS-035` · `US-RBS-036`. Every one resolves
# `apps.payments.runbook_reads.<name>` — a module `payments` added in the same
# commit, the way `collections_read` and `bankrec_read` already are, so **this
# module reaches past no seam and re-derives none of payments' law**
# (`BR-RBS-039`). `13-selector-inventory.md` **S-11** and **S-12** are two of
# them and are ticked off there in the same commit.
#
# ⚠ **THREE OF THESE ANSWER WITH AN ABSENCE AND ITS REASON RATHER THAN WITH AN
# EMPTY LIST**, because on a screen the two read identically and mean opposite
# things (hard-won law 7). Each says so in its own docstring below and the
# runbook renders the sentence rather than a zero.


def deposits_held(*, as_of, months: int = 12) -> dict[str, object]:
    """Every deposit held longer than the policy period — inventory **S-11**.

    `apps.payments.runbook_reads.deposits_held`. ONE read that answers both the
    setup screen's *"Matches N deposits · $X held"* and the set runbook 15 walks,
    for the ladder board's reason: a count computed a second way is a count that
    can disagree with the run.

    ⚠ **A DEPOSIT IS TWO COLUMNS ON `accounts` AND THERE IS NO `deposits`
    TABLE** (B2 r9 #5, `BR-CUS-050`). The subject a runbook walks is still the
    DEPOSIT — `subject_type` is the declared unit and never the raw row
    (`BR-RBS-019`) — and the row it is read off is the account's.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.deposits_held(as_of=as_of, months=months))


def payment_history_verdict(account_ids, *, as_of, months: int = 12) -> dict[str, object]:
    """Twelve months of on-time payment, and whether anything is past due TODAY.

    `apps.payments.runbook_reads.payment_history_verdict`. `BR-PAY-021` decides
    what *on time* means — `posted_at ≤ due date`, so a cheque posted on the due
    date and cleared three days later is on time — and this module reads that
    answer rather than restating it.

    ⚠ **`on_time` IS THREE-VALUED AND `None` MEANS UNPROVEN.** An account with no
    bills has no on-time history, and treating that as a clean record would
    release a deposit on evidence nobody has.
    """
    from apps.payments import runbook_reads

    return dict(
        runbook_reads.payment_history_verdict(account_ids, as_of=as_of, months=months)
    )


def returned_payment_counts(account_ids) -> dict[str, int]:
    """Prior returned payments per account — inventory **S-12**.

    `apps.payments.runbook_reads.returned_payment_counts`. Counted from the
    reversing ROWS and not from `accounts.nsf_count`, which nothing increments on
    this deployment (`DEF-069`): a privilege limit read off a counter nobody
    writes would never be reached on any account.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.returned_payment_counts(account_ids))


def returned_items_landed(*, as_of, window_days: int = 1) -> dict[str, object]:
    """Items the bank returned — the reversing rows that carry a bank return code.

    `apps.payments.runbook_reads.returned_items_landed`. ⚠ **UNTIL 2026-10-07 it
    answered `feed_available: False` with three named absences** (`DEF-PAY-10010`);
    since `CR-175-BRC10` it answers with every return US Payments sent and every
    ACH payment a clerk marked returned, already reversed, with the number of
    code-less hand reversals beside them.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.returned_items_landed(as_of=as_of, window_days=window_days))


def autopay_debits_due(*, as_of, within_days: int = 10) -> dict[str, object]:
    """Every debit this product has PROMISED inside the notice window.

    `apps.payments.runbook_reads.autopay_debits_due`. The promise is the
    `AutopayCaptureIntent` row and nothing else (`BR-PAY-015`): an open bill on
    an autopay account with no intent is not a debit due, because nothing will
    draft it and telling a customer otherwise is a promise this product cannot
    keep. Both counts travel — how many accounts are on autopay at all, and how
    many have a debit scheduled — so *6 on autopay · 0 scheduled* cannot be
    mistaken for *nobody is on autopay*.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.autopay_debits_due(as_of=as_of, within_days=within_days))


def failed_debits(*, as_of) -> dict[str, object]:
    """Yesterday's failed debits — **NOT REPORTED, and never zero.**

    `apps.payments.runbook_reads.failed_debits`. `AutopayCaptureIntent.status`
    has one value and nothing consumes an intent (`BR-PAY-015`), so no debit is
    ever attempted and none can fail. A tile reading **0** over that would be
    indistinguishable from a morning when every debit went through.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.failed_debits(as_of=as_of))


def plans_in_flight(*, as_of, grace_days: int = 0) -> dict[str, object]:
    """Every payment plan still running, with the instalments it has missed.

    `apps.payments.runbook_reads.plans_in_flight`. *In flight* is
    `LIVE_PLAN_STATUSES` — the same tuple `uq_one_live_plan_per_account` is built
    on — read rather than restated, so one debt can never carry two schedules
    because two files disagreed about what *in flight* means. The read returns
    the miss COUNT and no verdict: deciding *voided* is the runbook's step,
    against the limit Settings holds.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.plans_in_flight(as_of=as_of, grace_days=grace_days))


def plan_notice_settings() -> dict[str, object]:
    """`BR-PAY-016`'s plan figures and `BR-PAY-013`'s return limit, from Settings.

    `apps.payments.runbook_reads.plan_notice_settings`. Grace days, misses before
    a void, and how many returns cost an account its payment privilege — read,
    never duplicated onto a card (`RBR-03`). An unreadable setting travels as
    `readable: False`: `settings_seam.collections` refuses rather than falling
    back to the signed defaults, and its reason holds here word for word —
    *"every step it takes reaches a real customer"*.
    """
    from apps.payments import runbook_reads

    return dict(runbook_reads.plan_notice_settings())


# ── CR-075 wave S · the reads runbook 13 makes (US-RBS-025) ───────────────

def payments_matching(
    *,
    amount=None,
    around=None,
    within_days: int = 3,
    tolerance="0.01",
    account_ids=None,
    last_four: str | None = None,
    limit: int = 200,
) -> list[dict[str, object]]:
    """EVERY payment that could be the one a customer is asking about.

    `RB-113`'s steps 1 to 3 in one read: this account's payments in the window,
    the same amount and date ANYWHERE — *"this is where mis-keyed payments
    hide"* — and the reversed or returned ones, which are payments like any
    other and are told apart by their own columns rather than by a second query.

    ⚠ **THE WINDOW IS ON `posted_at`, WHICH IS THE DATE THE CUSTOMER MEANS.**
    `created_at` answers *when did we type it in*; a lockbox file keyed three
    days late carries the customer's own payment date, and that is the date they
    are reading off their bank statement.

    ⚠ **THE TOLERANCE IS A `Decimal` AND NEVER A FLOAT** (hard rule 2). The
    card's value is `$0.01`, which exists because a customer who paid `$182.40`
    may remember `$182.39` — and because a fee taken at the far end can move a
    figure by a cent.

    ⚠ **`last_four` IS MATCHED ON THE CONFIRMATION AND ON THE ACCOUNT NUMBER,
    AND THE SECOND IS THE POINT OF THE WHOLE RUNBOOK.** The card's worked case
    is a payment applied to the wrong account **because both end 4471**; a
    search that looked only at the cheque number would find the payment and
    never explain it.

    ⚠ **NO ROW IS DECIDED HERE.** *Applied to the wrong account* is a judgment
    and it belongs in the runbook with the reasoning on the screen; this returns
    facts.
    """
    from decimal import Decimal

    from apps.payments import selectors as payments_selectors

    rows = payments_selectors.payment_queryset()
    if account_ids:
        rows = rows.filter(account_id__in=[str(one) for one in account_ids if one])
    if around is not None:
        from datetime import timedelta

        span = timedelta(days=max(int(within_days), 0))
        rows = rows.filter(
            posted_at__date__gte=around - span, posted_at__date__lte=around + span
        )
    if amount is not None:
        edge = Decimal(str(tolerance or "0"))
        target = Decimal(str(amount))
        rows = rows.filter(amount__gte=target - edge, amount__lte=target + edge)
    rows = rows.select_related("account").order_by("-posted_at", "-id")[: max(int(limit), 1)]

    out: list[dict[str, object]] = []
    for one in rows:
        account_no = str(getattr(one.account, "account_no", "") or "")
        confirmation = str(one.confirmation or "")
        if last_four and not (
            confirmation.endswith(str(last_four)) or account_no.endswith(str(last_four))
        ):
            continue
        out.append(
            {
                # B14 rule 31 — the payment's NUMBER is what a clerk reads.
                "payment_no": one.payment_no,
                "payment_id": str(one.pk),
                "account_id": str(one.account_id),
                "account_no": account_no,
                # Money crosses as its stored four-decimal string with its
                # CHAR(3) code; nothing here rounds (hard rule 2).
                "amount": str(one.amount),
                "currency": one.currency,
                "status": one.status,
                "type": one.type,
                "purpose": one.purpose,
                "confirmation": one.confirmation,
                "memo": one.memo,
                "posted_on": one.posted_at.date().isoformat() if one.posted_at else None,
                "cleared_on": one.cleared_at.date().isoformat() if one.cleared_at else None,
                "reverses_payment_id": (
                    str(one.reverses_payment_id) if one.reverses_payment_id else None
                ),
                "reversal_reason": one.reversal_reason,
                "moved_from_payment_id": (
                    str(one.moved_from_payment_id) if one.moved_from_payment_id else None
                ),
                "deposit_batch_id": (
                    str(one.deposit_batch_id) if one.deposit_batch_id else None
                ),
            }
        )
    return out


def account_credit(account_id) -> str | None:
    """MONEY THIS UTILITY HOLDS AND HAS NOT PLACED, as a stored money string.

    `apps.payments.selectors.account_credit_position`, which returns a
    `Decimal`. `RB-113` step 4: a customer who paid and whose money is sitting
    as credit has not been ignored — it has been received and not applied, which
    is a different sentence and a different fix.

    ⚠ **IT MAY BE BELOW ZERO AND NOTHING HERE FLOORS IT** — PO ruling
    2026-08-11 closing `OQ-132`: a negative credit is a real debt. A seam that
    clamped it would hide money the utility is owed.

    ⚠ **IT CROSSES AS A STRING, NOT AS A `Decimal`.** A seam hands a runbook
    facts rather than another module's types, and the four stored decimals are
    what the renderer needs to show two (hard rule 2).

    `None` where the account cannot be read, for `open_bill_position`'s reason:
    a runbook renders an absence, never a traceback.
    """
    from apps.payments import selectors as payments_selectors

    if account_id in (None, ""):
        return None
    try:
        return str(payments_selectors.account_credit_position(account_id))
    except Exception:  # noqa: BLE001 — see `open_bill_position` above
        return None


# ── CR-075 wave S · the read runbook 12 makes (US-RBS-024) ────────────────
#
# Added with `definitions/disconnect_eligibility.py` in the same commit. It
# resolves `apps.payments.settings_seam.final_notice_hours`, which `payments`
# already publishes and which `ladder.decide` already consumes.


def final_notice_hours() -> dict[str, object]:
    """How long after the certified final letter a disconnection may follow.

    `apps.payments.settings_seam.final_notice_hours` — `BR-PAY-017`'s *"48h
    certified final"*, seeded per tenant, which is exactly what `RB-112`'s
    parameter row means by **Notice period · From Settings · 48 h after
    certified**. `RBR-03`: policy lives in Settings and is never duplicated onto
    a card, so the number is READ and the card's `48` is a seeded default rather
    than a constant this module holds.

    ⚠ **AN UNREADABLE SETTING TRAVELS AS `readable: False` AND NEVER AS 48.**
    `plan_notice_settings` above takes the same posture and gives the reason in
    payments' own words — *"every step it takes reaches a real customer"* — and
    here the step is a crew arriving at a house. A runbook that fell back to the
    signed default would compute a notice period from another utility's policy
    and clear people for disconnection two days early.
    """
    from apps.payments import settings_seam as payments_settings_seam
    from apps.payments.exceptions import PaymentRuleError

    try:
        return {"readable": True, "hours": int(payments_settings_seam.final_notice_hours())}
    except (PaymentRuleError, TypeError, ValueError) as refusal:
        return {"readable": False, "hours": None, "detail": str(refusal)}
