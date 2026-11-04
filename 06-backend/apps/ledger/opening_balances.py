# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the *"Opening balance
#           (cutover batch)"* row of the DR/CR table, and TC-3)
#           Screens: S56 (the entries appear on the trial balance) · S36
# Rules:    BR-CUS-049 (opening balances post as balanced opening JEs, AR ↔
#           clearing, dated at cutover, immutable) · BR-LED-001 (every line
#           carries source_type + source_id) · BR-TEN-043 (event time is named
#           by the caller, never read from a clock) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money NUMERIC(18,6) + CHAR(3), never float) ·
#           rule 4 (financial immutability) · rule 5 (balanced pairs; the
#           posting service is the sole writer) · rule 6 (idempotency) ·
#           rule 7 (audit)
# Golden:   GT-16 — B5 ❄️ FROZEN, finance-signed 2026-08-08: cutover
#           2026-08-31, account A-12103's four buckets 84.20 / 62.10 / 0.00 /
#           121.00 = **267.30** → ONE opening JE, **DR AR 267.30 / CR
#           opening-balance clearing 267.30**, idempotent per (batch, account);
#           batch: Σ clearing credit = Σ imported buckets (1,213 accounts →
#           **184,320.55**)
# Tests:    06-backend/tests/golden/test_gt16_opening_journal_entry.py ·
#           06-backend/tests/test_us_led_001_opening_balances.py
# Impacts:  apps/ledger/posting.py 🔒 (the sole writer this composes for) ·
#           apps/customers (it owns `account_opening_buckets` and the importer —
#           the caller this file is waiting for, named by story id in the module
#           docstring rather than in this header, because a Trace-header story id
#           is a claim that this file ships that story's test cases and it does
#           not) · apps/ledger/reporting.ar_positions
#           (a brought-forward balance becomes a per-account AR position the day
#           an importer calls this)
# ───────────────────────────────────────────────────────
"""The CUTOVER posting contract: what a migrated utility's opening balances
book to, composed once, in the module that owns the books.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this composes money-bearing journal
entries under CLAUDE.md's 🔒 *ledger posting*. AI-authored 2026-08-16 under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
Row in `12-governance/09-human-review-ledger.md`; it may never reach lifecycle
RATIFIED without a recorded human sign-off.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS, AND THE MEASUREMENT THAT PRODUCED IT
════════════════════════════════════════════════════════════════════════════
US-LED-001's contract table has **seventeen** source events. On 2026-08-16 the
US-LED-002/004 lane re-measured them against the code: **thirteen post, four do
not**, and the first of the four is this one — *"Opening balance (cutover
batch) | 1200 AR | opening-balance clearing | BR-CUS-049 (GT-16, LE-10)"*.

The frozen contract was NOT unexercised. `tests/golden/test_gt16_opening_journal
_entry.py` drives it end to end against a real Postgres and has since
2026-08-11. **But the composition lived inside that test file**, so what the
golden test proved was the golden test's own arithmetic. There was no function
in the product that anybody could call, which is why `posting.py`'s own docstring
files this row as *"a MISSING WRITER, not a missing contract"*.

This file is that writer's contract half: the request composition, the account
resolution, the key, the batch tie-out. `test_gt16_opening_journal_entry.py`
now drives THIS, so the ❄️ frozen figures assert the product rather than a
fixture — which is the only version of that test worth having.

⚠ **WHAT THIS DOES NOT CLAIM, AND IT IS THE WHOLE OF WHAT IS STILL MISSING
(hard-won law 2).** There is still **no importer**. `account_opening_buckets`
(B2 r9 #2) is not built — `apps/customers/models.py`'s own trailer says so and
names **US-CUS-021** as its owner, with **US-CUS-022** owning the import that
would read it. So nothing in the running product calls this file today, and a
utility migrating in from another system still cannot bring its receivables
across. What changed is that the day that importer is written it calls ONE
named function instead of re-deriving a signed DR/CR contract in a third place
— which is exactly how `apps/billing/posting_seam.py` and
`apps/payments/ledger_seam.py` already work for the thirteen rows that post.

**THE CONTRACT THE IMPORTER WILL CALL, stated here so US-CUS-021's lane needs
no archaeology:**

    from apps.ledger import opening_balances

    opening_balances.post_opening_batch(
        batch_id=<the import batch's id>,
        cutover_on=<date — BR-CUS-049's cutover date>,
        imported_at=<datetime — when the import ran; NOT a clock read here>,
        currency="USD",
        accounts=(
            opening_balances.OpeningAccount(
                account_id=<uuid>, account_ref="A-12103",
                balance=Decimal("267.30"),
            ),
            ...
        ),
        actor=<the user who ran the import>,
    )

════════════════════════════════════════════════════════════════════════════
THE ENTRY, AND EVERY FIGURE IN IT IS THE CALLER'S
════════════════════════════════════════════════════════════════════════════
B5 GT-16 line 56, verbatim: *"one opening JE dated **2026-08-31**, source_type
`opening_balance`: **DR AR 267.30 / CR opening-balance clearing 267.30** —
balanced pair written ONLY by the ledger posting service, immutable (corrections
via J6, never edits)"*.

So per account, one entry, two lines:

    DR  1200 accounts_receivable    267.30   ← what the customer owed on day one
    CR  3000 opening_clearing       267.30   ← the other side of a migration

**Nothing here computes the 267.30.** GT-16 states it as *"Σ buckets, exact — no
recompute"*, and the four buckets (84.20 · 62.10 · 0.00 · 121.00) belong to
`account_opening_buckets`, which is customers' table. This module takes the
balance the importer read and asserts it; it does not add up buckets, does not
round, and holds no float. That is US-LED-001 §1's *"posting asserts, never
recomputes"* applied to the one row of the table that had nowhere to apply it.

**BOTH ACCOUNTS ARE RESOLVED BY DESIGNATION, NEVER BY THE NUMBERS 1200 AND
3000.** US-LED-005 lets a tenant renumber their chart and OQ-106 was raised
precisely because a posting path had no way to find "the AR account" without
writing a code into Python. `chart.AR` and `chart.OPENING_CLEARING` are two of
the twelve designations; a tenant that has designated neither cannot cut over,
and that refusal is one chart edit on S56 rather than a wrong bucket for ever.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCY: GT-16's *"per (batch, account)"* IN THE THREE-PART KEY
════════════════════════════════════════════════════════════════════════════
GT-16 ❄️: *"re-posting the same batch is idempotent (no second JE set)"*, and
its identity is TWO ids — the batch and the account. The posting key is three
parts (`source_type | source_id | event`), so the composition is:

    opening_balance | <account id> | cutover:<batch id>

Worked: account `018f6f6a-…-aa` in batch `0192f0aa-…-7c` keys as
`opening_balance|018f6f6a-…-aa|cutover:0192f0aa-…-7c`. **A SECOND run of the
same batch writes nothing** and returns the first entry with `created=False`;
**a genuinely different batch touching the same account is a different key and
lawfully posts**, which is what makes a re-run of a corrected import possible
without a database repair. `apps/ledger/posting.py`'s docstring already names
this composition as *"REPORTED, not settled"* because no importer existed to
own it; it is settled here now, under the same B2 r13 #8 delegation
(*"Exact DDL + posting-service mechanics = Eng-Lead 🔒"*) the rest of the key
mechanics live under.

════════════════════════════════════════════════════════════════════════════
THE BATCH TIE-OUT IS THE POINT OF `post_opening_batch`, NOT A CONVENIENCE LOOP
════════════════════════════════════════════════════════════════════════════
GT-16's batch line — *"Σ of all opening JEs = Σ of all imported buckets (fixture
batch: 1,213 accounts → clearing credit = total migrated AR **$184,320.55**)"* —
is a statement about the BATCH, and no per-account call can make it. So the
batch is the unit of the API: it posts every account, sums both sides as it goes,
and REFUSES to report success if Σ AR debits ≠ Σ clearing credits.

That check can only fail if this file is wrong, and that is the point of writing
it: the alternative is a migration that lands 1,212 correct entries and one
wrong one, discovered by a bookkeeper in the following quarter with no lawful
way to edit any of them (hard rule 4).

**REPLAYS COUNT TOWARD THE TIE-OUT AND ARE REPORTED SEPARATELY.** A resumed
import re-posts accounts that already landed; those return `created=False` and
their money is already in the books. `created` and `replayed` are both on the
result so a caller can tell *"1,213 accounts, 400 written, 813 already there"*
from *"1,213 accounts, 1,213 written"* — a distinction a progress bar needs and
a silent count destroys.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE REFUSES, AND WHY EACH ONE IS A REFUSAL RATHER THAN A DEFAULT
════════════════════════════════════════════════════════════════════════════
  * **A zero balance posts NOTHING.** An account that owed nothing at cutover
    has no opening position; an entry of 0.00 / 0.00 would be a journal entry
    for money that did not move, and 1,213 of them would be 1,213 rows a
    bookkeeper has to explain. Reported on the result as `skipped`, never
    silently dropped — the count still has to add up.
  * **A NEGATIVE opening balance is REFUSED BY NAME.** A customer in CREDIT at
    cutover would need DR clearing / CR AR — the mirror — and **no signed
    document states that shape.** BR-CUS-049 says *"AR ↔ clearing"* and GT-16's
    four buckets are an AGEING (all ≥ 0). Writing the mirror would be inventing
    a contract row; writing it the signed way round would put a credit customer
    into receivables as a debit. It is refused, naming the account and the
    figure, so a migration stops on the case rather than mis-stating it.
    **Deliberately not minted as an open question:** `account_opening_buckets`
    is unbuilt, so no importer can reach this state, and a register entry for a
    path nothing can walk is noise the next lane has to read. The day US-CUS-021
    lands, this refusal is the thing that raises it — with a real customer's
    figure attached, which is a better question than this one would have been.
  * **A float.** Refused by `posting.post` itself (hard rule 2), and refused
    here first so the caller is told which ACCOUNT carried it.
  * **A missing designation, a missing cutover date, a missing batch id.** Each
    names itself. A cutover with no date would book every migrated balance on
    whatever day the import happened to run, which BR-TEN-043 forbids and which
    would scatter one utility's history across two fiscal periods.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT DO, NAMED SO SILENCE IS NOT READ AS "DONE"
════════════════════════════════════════════════════════════════════════════
  * **It does not write `accounts.balance`**, and it must not. That column is a
    cache nothing in this product maintains (DEF-127), and the per-account
    position is derived from these very lines by
    `apps.ledger.reporting.ar_positions`. GT-16's *"`accounts.balance` = 267.30"*
    is US-CUS-021's half of the golden test and belongs in customers.
  * **It does not age the opening buckets.** BR-CUS-048's day-one ageing reads
    the four buckets, and this entry carries ONE figure — their sum, as GT-16
    states it. `apps/payments/reporting.py` already reports that gap by name on
    every ageing run.
  * **It has no HTTP surface and no screen of its own, by design.** The RESULT
    is on S56 (the entries) and on S36 (the AR control total and the tie-out).
    A cutover import screen is US-CUS-022's, and drawing one here over a table
    that does not exist would be a confident empty wizard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.ledger import chart, models, posting, selectors

#: B5 GT-16 line 56, verbatim: *"source_type `opening_balance`"*. B2 r9 #3 uses
#: the same string. Named once so the entry, the lines and the key cannot drift
#: apart from each other.
SOURCE_OPENING_BALANCE = "opening_balance"

#: The event half of the posting key. GT-16's identity is *"per (batch,
#: account)"* — two ids — and the key has three parts, so the BATCH rides in the
#: event and the ACCOUNT is the source id. See the module docstring.
EVENT_CUTOVER_PREFIX = "cutover:"

ZERO = Decimal("0")

#: What a cutover posting CANNOT say, carried on every result — the discipline
#: `apps/billing/posting_seam.POSTING_UNAVAILABLE` and
#: `apps/billing/issue.ISSUE_UNAVAILABLE` already use, so a caller never has to
#: infer an absence and a reviewer never has to take this docstring's word for
#: it (hard-won law 1).
OPENING_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        # ⚠ CORRECTED 2026-08-28 (hard-won law 1 — a comment claiming a state is
        # not the state). This row read *"nothing calls this module"* until
        # today, and it had been false since 2026-08-24: `account_opening_buckets`
        # is built and `apps/customers/import_writer.post_opening_batch_from_import`
        # is the caller. The code is kept rather than deleted because callers may
        # match on it; what it reports is now the gap that is genuinely still open.
        "code": "no_importer_calls_this_yet",
        "br_ref": "BR-CUS-049 · B2 r9 #2 · US-CUS-021 / US-CUS-022 · OQ-352",
        "detail": "the importer EXISTS (`apps/customers/import_writer.py`, 2026-08-24) and "
        "this module's AR contract is reached by it. What is still missing is the way OUT: "
        "an account whose opening balances were posted cannot be rolled back (OQ-352), "
        "because hard rule 4 keeps the journal entry alive while the buckets would go.",
    },
    {
        "code": "the_four_ageing_buckets_are_not_carried",
        "br_ref": "BR-CUS-048 · GT-16",
        "detail": "GT-16 imports FOUR buckets (Current 84.20 / 31-60 62.10 / 61-90 0.00 / "
        "90+ 121.00) and posts ONE figure — their sum, 267.30, exactly as the frozen line "
        "states it. The ageing of a brought-forward balance therefore has no journal-side "
        "dimension to read; `apps/payments/reporting.py` reports that on every ageing run.",
    },
    {
        "code": "accounts_balance_is_not_written",
        "br_ref": "BR-CUS-015 · DEF-127 · BR-REP-002",
        "detail": "GT-16's *`accounts.balance` = 267.30* is customers' half of the golden "
        "test. `accounts.balance` is a cache nothing in this product maintains, and the "
        "per-account position is DERIVED from the lines this module posts by "
        "`apps.ledger.reporting.ar_positions`. Writing it here would rebuild the second "
        "source of truth BR-REP-002 forbids.",
    },
)


class OpeningBalanceError(posting.PostingError):
    """A cutover the books refuse, in the ledger's own vocabulary.

    A subclass of `PostingError` so an importer that already catches the
    posting service's refusals catches these too, and declared as its own class
    so a caller that wants to tell *"this batch is malformed"* from *"the books
    said no"* can, without matching on prose.
    """


@dataclass(frozen=True)
class OpeningAccount:
    """One migrated account's opening position, as the importer read it.

    `balance` is GT-16's *"Σ buckets, exact — no recompute"* — the importer adds
    the four `account_opening_buckets` columns, once, and hands the total over.
    `account_ref` is the utility's own account number and is used for the memo
    and for every refusal message: a migration that stops on account
    `018f6f6a-…` tells a clerk nothing, and one that stops on **A-12103** tells
    them which row of their spreadsheet to look at.
    """

    account_id: Any
    balance: Decimal
    account_ref: str | None = None

    @property
    def label(self) -> str:
        return str(self.account_ref or self.account_id)


@dataclass(frozen=True)
class OpeningPosting:
    """What ONE account's cutover left in the books.

    `created=False` is the replay (hard rule 6, GT-16's *"no second JE set"*) —
    the correct outcome of a resumed import, not an error. `skipped` is the
    account that owed nothing at cutover: no entry exists, `entry_id` is None,
    and the account is still counted so a batch total cannot quietly shrink.
    """

    account_id: str
    account_ref: str | None
    balance: Decimal
    entry_id: str | None
    posting_key: str | None
    created: bool
    skipped: bool = False


@dataclass(frozen=True)
class OpeningBatchPosting:
    """What a whole cutover batch left in the books, and whether it ties out.

    `ar_debits` and `clearing_credits` are summed over the accounts this call
    actually WROTE plus the ones it found already written, because GT-16's batch
    line is a statement about the batch and not about one run of it. They are
    equal by construction and are carried anyway: the assertion is the product
    of this module being right, so publishing it is what lets a caller — and
    US-LED-004's tie-out panel — check rather than trust.
    """

    batch_id: str
    cutover_on: date
    currency: str
    accounts: tuple[OpeningPosting, ...]
    ar_debits: Decimal
    clearing_credits: Decimal
    created_count: int
    replayed_count: int
    skipped_count: int
    unavailable: tuple[dict[str, Any], ...] = field(default=OPENING_UNAVAILABLE)

    @property
    def ties_out(self) -> bool:
        return self.ar_debits == self.clearing_credits


def _designated(designation: str, *, what: str) -> str:
    """A tenant's account for one designation — or REFUSE, naming the gap.

    BY DESIGNATION, never by the numbers 1200 and 3000 (`chart.py`: *"Code
    reads the DESIGNATION. Code never reads the NUMBER"*). A tenant that has
    designated neither cannot cut over, and that is the correct answer rather
    than a harsh one: it is one edit on the GL mapping page, it blocks exactly
    one thing until somebody makes it, and the alternative is a whole utility's
    migrated receivables in a bucket nobody chose.
    """
    account_id = selectors.gl_account_id_for_designation(designation)
    if not account_id:
        raise OpeningBalanceError(
            f"no live ledger account carries the {designation!r} designation, so a cutover "
            f"batch has no {what} (BR-CUS-049 — DR AR / CR opening-balance clearing). The "
            "account is resolved by DESIGNATION and never by number, because a tenant may "
            "renumber their chart (PO ruling 2026-08-11, OQ-106); a human designates one on "
            "the GL mapping page. Nothing here picks an account for a utility's opening "
            "receivables."
        )
    return str(account_id)


def cutover_event(batch_id: Any) -> str:
    """GT-16's *"idempotent per (batch, account)"*, as the key's event half.

    Composed here and nowhere else: two call sites composing "the same" event
    string by hand is how a replay guard stops guarding, which is the reason
    `apps/billing/posting_seam.py` refuses to build the ledger's key as an
    f-string on its own side of the boundary.
    """
    text = str(batch_id or "").strip()
    if not text:
        raise OpeningBalanceError(
            "a cutover batch id is required to key an opening balance (CLAUDE.md rule 6). "
            "GT-16's identity is *per (batch, account)*: without the batch, re-importing a "
            "corrected file for the same accounts would either collide with the first import "
            "or double the utility's opening receivables, depending on which way the key was "
            "shortened. Neither is recoverable — a posted entry cannot be edited (hard rule 4)."
        )
    return f"{EVENT_CUTOVER_PREFIX}{text}"


def opening_entry_request(
    account: OpeningAccount,
    *,
    batch_id: Any,
    cutover_on: date,
    imported_at: datetime,
    currency: str,
) -> posting.PostingRequest:
    """GT-16's entry for ONE account, fully specified. Composes; writes nothing.

    Separated from `post_opening_balance` so a caller — and the golden test —
    can read exactly what will be written before anything is written, which is
    what turns *"the books took it"* into *"the books took THIS"*.

    **THE TWO DATES ARE BOTH INPUTS** (PO ruling 2026-08-11 closing OQ-107,
    BR-TEN-043). `cutover_on` is the BOOK date the trial balance groups by —
    GT-16's **2026-08-31** — and `imported_at` is the wall-clock moment the
    import ran, which is very often the following morning. Nothing in this
    module reads a clock (gate G6 greps every money path for one), so a resumed
    import stamps the same moment as the run it resumed rather than a new one.
    """
    if not isinstance(account.balance, Decimal):
        raise OpeningBalanceError(
            f"account {account.label}'s opening balance arrived as "
            f"{account.balance!r} ({type(account.balance).__name__}), not a Decimal. Money is "
            "NUMERIC(18,6) and never a float (CLAUDE.md rule 2). Refused rather than "
            "converted: a conversion hides the place where a utility's migrated receivables "
            "became binary, and the entry it produces is immutable."
        )
    if account.balance < ZERO:
        raise OpeningBalanceError(
            f"account {account.label} carries an opening balance of {account.balance}, which "
            "is a CREDIT — the utility owes this customer money at cutover. BR-CUS-049 signs "
            "one shape only, *opening balances post as balanced opening JEs (AR <-> "
            "clearing)*, and GT-16's four imported buckets are an AGEING, so every figure in "
            "the frozen example is >= 0. Posting it as written would put a customer in credit "
            "into receivables as a DEBIT; posting the mirror (DR clearing / CR AR) would be a "
            "contract row nobody has signed. It is REFUSED, naming the account and the "
            "figure, so the migration stops on this row rather than mis-stating it."
        )
    if not currency or len(str(currency)) != 3:
        raise OpeningBalanceError(
            f"a cutover posts in a stated CHAR(3) currency and got {currency!r} (CLAUDE.md "
            "rule 2). A defaulted currency is how a CAD utility's opening books quietly "
            f"become USD, on {account.label} and on every other row of the same import."
        )
    if cutover_on is None:
        raise OpeningBalanceError(
            f"account {account.label}'s opening entry has no cutover date. BR-CUS-049 dates "
            "these entries AT CUTOVER and BR-TEN-043 forbids reading a clock for an event "
            "time: without it every migrated balance would book on whichever day the import "
            "happened to run, scattering one utility's opening position across two fiscal "
            "periods depending on when somebody pressed the button."
        )

    ar = _designated(chart.AR, what="debit side")
    clearing = _designated(chart.OPENING_CLEARING, what="credit side")
    dimensions = {
        "source_type": SOURCE_OPENING_BALANCE,
        "source_id": account.account_id,
        # BR-LED-001 — the per-account dimension. Without it a migrated
        # utility's brought-forward receivables sit in the AR control total and
        # in nobody's account row (`reporting.ar_positions` groups on exactly
        # this), so every customer would read as owing only what this product
        # has billed them since.
        "account_id": account.account_id,
    }
    return posting.PostingRequest(
        posting_key=posting.posting_key(
            source_type=SOURCE_OPENING_BALANCE,
            source_id=account.account_id,
            event=cutover_event(batch_id),
        ),
        entry_date=cutover_on,
        posted_at=imported_at,
        currency=str(currency),
        source_type=SOURCE_OPENING_BALANCE,
        source_id=account.account_id,
        memo=f"Opening balance at cutover — {account.label}",
        lines=(
            posting.PostingLine(
                ledger_account_id=ar,
                side=models.SIDE_DEBIT,
                amount=account.balance,
                **dimensions,
            ),
            posting.PostingLine(
                ledger_account_id=clearing,
                side=models.SIDE_CREDIT,
                amount=account.balance,
                **dimensions,
            ),
        ),
        audit_context={
            "account_ref": account.account_ref,
            "batch_id": str(batch_id),
            "opening_balance": str(account.balance),
        },
    )


def post_opening_balance(
    account: OpeningAccount,
    *,
    batch_id: Any,
    cutover_on: date,
    imported_at: datetime,
    currency: str,
    actor: Any = None,
) -> OpeningPosting:
    """ONE account's opening JE — DR AR / CR opening clearing, or a refusal.

    A balance of exactly zero posts NOTHING and says so (`skipped=True`). An
    account that owed the utility nothing on cutover day has no opening
    position, and an entry of 0.00 against 0.00 is a journal entry for money
    that did not move — 1,213 of which is 1,213 rows somebody has to explain.
    """
    if account.balance == ZERO:
        return OpeningPosting(
            account_id=str(account.account_id),
            account_ref=account.account_ref,
            balance=ZERO,
            entry_id=None,
            posting_key=None,
            created=False,
            skipped=True,
        )
    request = opening_entry_request(
        account,
        batch_id=batch_id,
        cutover_on=cutover_on,
        imported_at=imported_at,
        currency=currency,
    )
    result = posting.post(request, actor=actor)
    return OpeningPosting(
        account_id=str(account.account_id),
        account_ref=account.account_ref,
        balance=account.balance,
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
    )


def post_opening_batch(
    *,
    batch_id: Any,
    accounts: tuple[OpeningAccount, ...] | list[OpeningAccount],
    cutover_on: date,
    imported_at: datetime,
    currency: str,
    actor: Any = None,
) -> OpeningBatchPosting:
    """GT-16's batch: every account's opening JE, and the Σ that must tie out.

    *"Σ of all opening JEs = Σ of all imported buckets (fixture batch: 1,213
    accounts → clearing credit = total migrated AR **$184,320.55**)"* — B5
    GT-16 line 56, ❄️ frozen. That is a property of the BATCH, so the batch is
    the unit of this API rather than a loop a caller writes.

    **The refusal at the end can only fire if this module is wrong**, and it is
    written because of what the alternative costs: a migration that lands 1,212
    correct entries and one wrong one is discovered by a bookkeeper a quarter
    later, with no lawful way to edit any of them (hard rule 4).

    Every account is posted through `apps.ledger.posting.post`, one entry each,
    each independently keyed — so a batch that dies halfway can be re-run and
    the accounts that already landed no-op instead of doubling.
    """
    postings: list[OpeningPosting] = []
    ar_debits = ZERO
    clearing_credits = ZERO
    created = replayed = skipped = 0

    for account in accounts:
        result = post_opening_balance(
            account,
            batch_id=batch_id,
            cutover_on=cutover_on,
            imported_at=imported_at,
            currency=currency,
            actor=actor,
        )
        postings.append(result)
        if result.skipped:
            skipped += 1
            continue
        # Both sides are accumulated from the SAME figure deliberately: the
        # check below is only worth running because `opening_entry_request`
        # builds two lines from it, and a Σ taken off the request rather than
        # off the input would be this module checking its own opinion twice.
        ar_debits += result.balance
        clearing_credits += result.balance
        if result.created:
            created += 1
        else:
            replayed += 1

    if ar_debits != clearing_credits:  # pragma: no cover — see the docstring
        raise OpeningBalanceError(
            f"cutover batch {batch_id} does not tie out: AR debits {ar_debits} against "
            f"opening-clearing credits {clearing_credits}, a difference of "
            f"{ar_debits - clearing_credits} {currency}. GT-16 (❄️ finance-signed) requires "
            "Sum of all opening JEs = Sum of all imported buckets, and nothing here plugs "
            "the delta: a balancing line would make the batch tie and the utility's opening "
            "books wrong, permanently, because a posted entry cannot be edited (hard rule 4)."
        )

    return OpeningBatchPosting(
        batch_id=str(batch_id),
        cutover_on=cutover_on,
        currency=str(currency),
        accounts=tuple(postings),
        ar_debits=ar_debits,
        clearing_credits=clearing_credits,
        created_count=created,
        replayed_count=replayed,
        skipped_count=skipped,
    )


# ══════════════════════════════════════════════════════════════════════════
# THE SECOND MONEY COLUMN ON THE SAME MIGRATED ROW — THE HELD DEPOSIT
# (DEF-1713, and DEF-177 is its mirror)
# ══════════════════════════════════════════════════════════════════════════
#
# THE DEFECT, measured on a full plant on 2026-08-27 and again on 2026-08-28:
#
#     deposit_liability  DRIFTING  GL 0.00  register 750.00  drift -750.00
#
# **And the books still footed.** Every seeded journal entry balanced, so hard
# rule 5 held perfectly: the entry was not unbalanced, it was never made. An
# import row carries TWO money facts — what the customer OWED at cutover and
# what the utility HOLDS of theirs — and only the first one reached the books.
#
# The account columns land through `IMPORT_ACCOUNT_FIELDS` (US-CUS-023, so the
# ORIGINAL receipt date rides with the amount and BR-CUS-057's interest accrues
# from the true date); nothing then told the balance sheet that the utility owes
# that money back. A deposit is the customer's money (BR-CUS-025 — *a liability,
# never revenue*), and a liability the balance sheet has never heard of is the
# one shape of money error that every check looking for imbalance passes over.
#
# ────────────────────────────────────────────────────────────────────────────
# THE DATE IS THE CUTOVER DATE, AND THAT IS A SIGNED RULE RATHER THAN A CHOICE
# ────────────────────────────────────────────────────────────────────────────
# A migration is not a transaction: the money was taken by the utility's OLD
# system, sometimes years ago (`A-12048 · Kwan, Michael` holds a deposit
# received **2024-02-05**). Posting it as a fresh entry dated the day the import
# ran would put a 2024 liability into the current period, and hard rule 4 makes
# that permanent the instant it commits.
#
# **BR-CUS-049 (CONFIRMED, PO AC-4, 2026-08-08) already answers it**, verbatim:
# *"opening balances post as balanced opening journal entries, AR <-> clearing,
# **dated at cutover**, immutable"*. A held deposit brought across at cutover IS
# an opening balance — the same row of the same spreadsheet as the four ageing
# buckets — so it takes the same date, from the same batch, in the same call.
# Nothing new is signed here and nothing was put back to the Product Owner.
#
# **AND THE "date the operator supplies" READING IS THE SAME DATE IN THIS
# PRODUCT.** The 2026-08-27 changeover ruling makes the cutover the operator's
# own answer to *"the last day your old system was in charge of the money"*
# (`import_runs.confirm_changeover_date`), and while it is unanswered the batch
# is HELD and NOTHING posts. So "at cutover" and "at a date the operator
# supplies" are one option wearing two names, and the third — the migration date
# — is the only one that would have been a new rule, and a wrong one.
#
# ⚠ **THE RECEIPT DATE IS NOT THE BOOK DATE, AND BOTH ARE KEPT.** `2024-02-05`
# is what BR-CUS-050/057 accrue interest from and it stays on the account; the
# ENTRY is dated at cutover. They answer different questions and collapsing them
# either way loses one: book at the receipt date and a utility's opening equity
# is stated in a period that predates its own books; accrue from the cutover and
# the longest-standing customers are quietly under-paid.
#
# ────────────────────────────────────────────────────────────────────────────
# THE CONTRA LEG IS THE OPENING CLEARING ACCOUNT — THE JUDGMENT THIS LANE MADE
# ────────────────────────────────────────────────────────────────────────────
# BR-CUS-049 names ONE pair, *AR <-> clearing*, and US-LED-001's contract table
# has exactly one opening row. Neither states the other side of a migrated
# DEPOSIT, so this is a judgment and it is recorded as one — in
# `12-governance/02-decision-log.md` with its worked figure, and in the
# human-review ledger as a decision the Product Owner has NOT been shown.
#
#     DR  3000 opening_clearing     150.00   <- the other side of a migration
#     CR  2300 deposit_liability    150.00   <- the customer's money, now ours to hold
#
# The reasoning, in one line each:
#
#   * **The clearing account is what "the other side of a migration" MEANS
#     here.** It is where the AR half of the very same row goes, and B5 names
#     it *3000 Opening balance equity*. A cutover states an opening trial
#     balance; every migrated figure meets its counterpart there, and the
#     account nets to the utility's opening equity exactly as it is meant to.
#   * **Cash was NOT received today, so no cash account may move.** The money
#     reached the old system years ago; debiting 1000 or 1010 would assert a
#     receipt this product never saw and would double-count the bank balance the
#     same cutover brings across.
#   * **The direction is forced.** A deposit is a liability, so it is a CREDIT;
#     with the credit fixed, the only question is which account carries the
#     debit, and the two candidates are cash (wrong, above) and clearing.
#
# What is NOT decided here, and is not needed to close the defect: BR-CUS-057's
# accrued interest is not posted (the accrual engine is unbuilt — the register
# is signed as *deposit_on_file + interest* and the interest half is 0.00 by
# absence, not by choice), and a migrated deposit's REFUND path is untouched.

#: The event half of the key for the deposit entry. A separate EVENT rather
#: than a separate `source_type`: B2 Addendum r9 #3 admits `'opening_balance'`
#: for the cutover entry and nothing signs a second value, and
#: `apps.ledger.reporting.SOURCE_TYPE_TO_VOCABULARY` maps that one to the
#: OPENING vocabulary — which is what a migrated deposit is. A new source_type
#: would be an unmapped value that module refuses to bucket silently, invented
#: to say something the existing one already says correctly.
EVENT_CUTOVER_DEPOSIT_PREFIX = "cutover-deposit:"


def cutover_deposit_event(batch_id: Any) -> str:
    """The deposit entry's key event — `cutover-deposit:<batch>`.

    Composed here and nowhere else, for the reason `cutover_event` gives: two
    call sites building "the same" event string by hand is how a replay guard
    stops guarding. It is DELIBERATELY not the same string as the AR entry's:
    one account, one batch, two entries, and a shared key would make the second
    one a replay of the first — the migration would post the receivable and
    silently swallow the deposit, which is DEF-1713 again with a guard on top.
    """
    text = str(batch_id or "").strip()
    if not text:
        raise OpeningBalanceError(
            "a cutover batch id is required to key a migrated deposit (CLAUDE.md rule 6). "
            "Without it, re-running a corrected file for the same accounts would either "
            "collide with the first import or DOUBLE the utility's deposit liability — and a "
            "posted entry cannot be edited (hard rule 4), so neither is recoverable."
        )
    return f"{EVENT_CUTOVER_DEPOSIT_PREFIX}{text}"


@dataclass(frozen=True)
class OpeningDeposit:
    """One migrated account's HELD deposit, as the importer read it.

    `held` is `accounts.deposit_on_file` — what the utility holds of this
    customer's money on cutover day — and nothing here recomputes it. The
    interest half of US-LED-004's register (`deposit_on_file + interest`) is
    absent because BR-CUS-057's accrual engine is unbuilt, and that absence is
    reported on the batch result rather than silently treated as zero.

    `received_on` is BR-CUS-050's ORIGINAL receipt date. It is carried into the
    memo and the audit context and is NEVER used as the entry date — see the
    block above.
    """

    account_id: Any
    held: Decimal
    account_ref: str | None = None
    received_on: date | None = None

    @property
    def label(self) -> str:
        return str(self.account_ref or self.account_id)


@dataclass(frozen=True)
class OpeningDepositPosting:
    """What ONE account's migrated deposit left in the books.

    Same three-state shape as `OpeningPosting`: `created=False` is the lawful
    replay of a resumed import, and `skipped` is an account holding nothing —
    counted, never dropped, so a batch total cannot quietly shrink.
    """

    account_id: str
    account_ref: str | None
    held: Decimal
    entry_id: str | None
    posting_key: str | None
    created: bool
    skipped: bool = False


#: What a migrated-deposit posting CANNOT say, carried on every batch result —
#: the `OPENING_UNAVAILABLE` discipline, so a caller never infers an absence and
#: a reviewer never takes a docstring's word for it (hard-won law 1).
OPENING_DEPOSIT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "migrated_deposit_interest_is_not_posted",
        "br_ref": "BR-CUS-057 · US-LED-004 §5",
        "detail": "US-LED-004 signs the deposit register as `accounts.deposit_on_file + "
        "interest`, and BR-CUS-057's accrual engine is unbuilt — `apps.customers.selectors` "
        "publishes no accrued figure. So this entry books the PRINCIPAL and the interest half "
        "is 0.00 by absence rather than by a decision. The two sides of the tie-out therefore "
        "agree today and will BOTH move the day the accrual lands, which is the correct "
        "coupling: the register and the liability are written from one figure.",
    },
    {
        "code": "the_contra_leg_is_this_lane_s_judgment",
        "br_ref": "BR-CUS-049 · US-LED-001 · DEF-1713",
        "detail": "BR-CUS-049 signs `AR <-> clearing` and US-LED-001's contract table holds "
        "one opening row; NEITHER states the other side of a migrated DEPOSIT. The opening "
        "clearing account is this lane's reasoned choice, recorded in the decision log with "
        "its worked figure and flagged in the human-review ledger as NOT shown to the Product "
        "Owner. A signature covers only what was shown.",
    },
)


@dataclass(frozen=True)
class OpeningDepositBatchPosting:
    """What a whole batch of migrated deposits left in the books, and whether it ties.

    `clearing_debits` and `deposit_credits` are summed over the accounts this
    call wrote PLUS the ones it found already written, for the reason
    `OpeningBatchPosting` gives: the tie-out is a statement about the batch and
    not about one run of it.
    """

    batch_id: str
    cutover_on: date
    currency: str
    deposits: tuple[OpeningDepositPosting, ...]
    clearing_debits: Decimal
    deposit_credits: Decimal
    created_count: int
    replayed_count: int
    skipped_count: int
    unavailable: tuple[dict[str, Any], ...] = field(default=OPENING_DEPOSIT_UNAVAILABLE)

    @property
    def ties_out(self) -> bool:
        return self.clearing_debits == self.deposit_credits


def opening_deposit_entry_request(
    deposit: OpeningDeposit,
    *,
    batch_id: Any,
    cutover_on: date,
    imported_at: datetime,
    currency: str,
) -> posting.PostingRequest:
    """The migrated deposit's entry for ONE account, fully specified. Writes nothing.

    Separated from `post_opening_deposit` for the reason
    `opening_entry_request` is separated from `post_opening_balance`: a caller,
    a reviewer and a test can read exactly what will be written before anything
    is, which is what turns *"the books took it"* into *"the books took THIS"*.
    """
    if not isinstance(deposit.held, Decimal):
        raise OpeningBalanceError(
            f"account {deposit.label}'s migrated deposit arrived as {deposit.held!r} "
            f"({type(deposit.held).__name__}), not a Decimal. Money is stored to 4 decimals "
            "and is never a float (CLAUDE.md rule 2). Refused rather than converted: a "
            "conversion hides the place where a customer's money became binary, and the "
            "entry it produces is immutable."
        )
    if deposit.held < ZERO:
        # BR-CUS-025 makes a deposit a LIABILITY, so the only lawful direction is
        # a CREDIT; posting a negative as written would DEBIT the deposit-liability
        # account and state that the customer owes the utility their own deposit back.
        raise OpeningBalanceError(
            f"account {deposit.label} carries a migrated deposit of {deposit.held}, which is "
            "NEGATIVE — a utility cannot hold less than none of a customer's money. It is "
            "refused, naming the account and the figure, so the migration stops on this row "
            "rather than mis-stating it."
        )
    if not currency or len(str(currency)) != 3:
        raise OpeningBalanceError(
            f"a cutover posts in a stated CHAR(3) currency and got {currency!r} (CLAUDE.md "
            f"rule 2). A defaulted currency is how a CAD utility's held deposits quietly "
            f"become USD, on {deposit.label} and on every other row of the same import."
        )
    if cutover_on is None:
        # BR-CUS-049 dates an opening entry AT CUTOVER and BR-TEN-043 forbids
        # reading a clock for an event time; BR-CUS-050's receipt date is NOT a
        # substitute — see the block above this function.
        raise OpeningBalanceError(
            f"account {deposit.label}'s migrated deposit has no changeover date. The "
            "deposit's own receipt date cannot stand in for it: it is often years earlier, "
            "and it would state a liability in a period that predates this utility's books "
            "entirely."
        )

    clearing = _designated(chart.OPENING_CLEARING, what="debit side")
    liability = _designated(chart.DEPOSIT_LIABILITY, what="credit side")
    dimensions = {
        "source_type": SOURCE_OPENING_BALANCE,
        "source_id": deposit.account_id,
        # BR-LED-001's per-account dimension — the same reason the AR entry
        # carries it: without it the migrated deposits sit in the 2300 control
        # total and in nobody's account row, and the S36 tie-out could see the
        # lump but never which customer it belongs to.
        "account_id": deposit.account_id,
    }
    return posting.PostingRequest(
        posting_key=posting.posting_key(
            source_type=SOURCE_OPENING_BALANCE,
            source_id=deposit.account_id,
            event=cutover_deposit_event(batch_id),
        ),
        entry_date=cutover_on,
        posted_at=imported_at,
        currency=str(currency),
        source_type=SOURCE_OPENING_BALANCE,
        source_id=deposit.account_id,
        memo=(
            f"Deposit held at cutover — {deposit.label}"
            + (f" (received {deposit.received_on.isoformat()})" if deposit.received_on else "")
        ),
        lines=(
            posting.PostingLine(
                ledger_account_id=clearing,
                side=models.SIDE_DEBIT,
                amount=deposit.held,
                **dimensions,
            ),
            posting.PostingLine(
                ledger_account_id=liability,
                side=models.SIDE_CREDIT,
                amount=deposit.held,
                **dimensions,
            ),
        ),
        audit_context={
            "account_ref": deposit.account_ref,
            "batch_id": str(batch_id),
            "deposit_held": str(deposit.held),
            # BR-CUS-050's true date, on the audit row rather than on the entry
            # date, so the reason the two differ is legible years later.
            "deposit_received_on": (
                deposit.received_on.isoformat() if deposit.received_on else None
            ),
        },
    )


def post_opening_deposit(
    deposit: OpeningDeposit,
    *,
    batch_id: Any,
    cutover_on: date,
    imported_at: datetime,
    currency: str,
    actor: Any = None,
) -> OpeningDepositPosting:
    """ONE account's migrated deposit — DR opening clearing / CR deposit liability.

    A held amount of exactly zero posts NOTHING and says so (`skipped=True`),
    for the same reason a zero opening balance does: an account whose old
    utility held none of their money has no deposit position, and an entry of
    0.00 against 0.00 is a journal entry for money that did not move.
    """
    if deposit.held == ZERO:
        return OpeningDepositPosting(
            account_id=str(deposit.account_id),
            account_ref=deposit.account_ref,
            held=ZERO,
            entry_id=None,
            posting_key=None,
            created=False,
            skipped=True,
        )
    request = opening_deposit_entry_request(
        deposit,
        batch_id=batch_id,
        cutover_on=cutover_on,
        imported_at=imported_at,
        currency=currency,
    )
    result = posting.post(request, actor=actor)
    return OpeningDepositPosting(
        account_id=str(deposit.account_id),
        account_ref=deposit.account_ref,
        held=deposit.held,
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
    )


def post_opening_deposit_batch(
    *,
    batch_id: Any,
    deposits: tuple[OpeningDeposit, ...] | list[OpeningDeposit],
    cutover_on: date,
    imported_at: datetime,
    currency: str,
    actor: Any = None,
) -> OpeningDepositBatchPosting:
    """Every migrated deposit in one batch, and the Σ that must tie out.

    The batch is the unit for the reason `post_opening_batch`'s docstring gives
    — and here there is a second reason, which is the defect this exists for:
    what a finance officer checks is `Σ deposits held == the 2300 balance`, and
    that is a statement about the whole register. A per-account API would let a
    migration land 400 deposits and miss one, and the one that was missed is
    invisible on every report that foots.
    """
    postings: list[OpeningDepositPosting] = []
    clearing_debits = deposit_credits = ZERO
    created = replayed = skipped = 0

    for deposit in deposits:
        result = post_opening_deposit(
            deposit,
            batch_id=batch_id,
            cutover_on=cutover_on,
            imported_at=imported_at,
            currency=currency,
            actor=actor,
        )
        postings.append(result)
        if result.skipped:
            skipped += 1
            continue
        clearing_debits += result.held
        deposit_credits += result.held
        if result.created:
            created += 1
        else:
            replayed += 1

    if clearing_debits != deposit_credits:  # pragma: no cover — see the docstring
        raise OpeningBalanceError(
            f"cutover deposit batch {batch_id} does not tie out: opening-clearing debits "
            f"{clearing_debits} against deposit-liability credits {deposit_credits}, a "
            f"difference of {clearing_debits - deposit_credits} {currency}. Nothing here "
            "plugs the delta: a balancing line would make the batch tie and the utility's "
            "deposit liability wrong, permanently, because a posted entry cannot be edited "
            "(hard rule 4)."
        )

    return OpeningDepositBatchPosting(
        batch_id=str(batch_id),
        cutover_on=cutover_on,
        currency=str(currency),
        deposits=tuple(postings),
        clearing_debits=clearing_debits,
        deposit_credits=deposit_credits,
        created_count=created,
        replayed_count=replayed,
        skipped_count=skipped,
    )



# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@1a820c8 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md — US-LED-001 §1's contract-table row "Opening balance (cutover batch)" + TC-3 — · 04-docs/02-decisions/05-golden-tests.md — GT-16 ❄️ — · 04-docs/05-modules/03-customers/02-business-rules.md — BR-CUS-049 —; co-cited B2 Addendum r9 #2/#3, r13 #8)
# generated: 2026-08-16 by story-coder (US-LED-001 four-unposted-events lane —
#         the 13-of-17 measurement the US-LED-002/004 lane left behind)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a service-layer posting contract; its RESULT is served by GET /finance/tie-outs and the S56 journal reads) E=deferred(no-frontend-half — S56 renders the entries this writes and S36 the AR control they move; the cutover IMPORT screen belongs to the unbuilt import story and drawing one over an unbuilt table would be a confident empty wizard) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_led_001_opening_balances.py ·
#         tests/golden/test_gt16_opening_journal_entry.py (now drives THIS module
#         rather than its own copy of the composition)
# exceptions: (1) NOTHING IN THE PRODUCT CALLS THIS (hard-won law 2).
#         `account_opening_buckets` (B2 r9 #2) is unbuilt — US-CUS-021 owns the
#         table, US-CUS-022 the import. The contract, the key and the batch
#         tie-out are complete; the WRITER that feeds them is not. Carried on
#         every result as `no_importer_calls_this_yet`, not only in prose.
#         (2) THE KEY COMPOSITION `opening_balance|<account>|cutover:<batch>` is
#         this lane's, under B2 r13 #8's delegation of posting-service mechanics.
#         `apps/ledger/posting.py` carried it as "REPORTED, not settled" while no
#         importer existed to own it; it is settled here and that file's docstring
#         is amended to point at this one rather than repeat it.
#         (3) A NEGATIVE OPENING BALANCE REFUSES BY NAME and is deliberately NOT
#         minted as an open question: no importer can reach the state, and a
#         register row for a path nothing can walk is noise. The refusal is what
#         raises it, with a real figure, the day US-CUS-021 lands.
#         (4) `accounts.balance` IS NOT WRITTEN — it is a cache nothing maintains
#         (DEF-127) and the per-account position is derived from these lines by
#         `reporting.ar_positions`. GT-16's balance clause is customers' half.
#         (5) THE FOUR AGEING BUCKETS ARE NOT CARRIED — GT-16 posts their SUM,
#         exactly as the frozen line states it, so BR-CUS-048's day-one ageing has
#         no journal-side dimension. Already reported by apps/payments/reporting.py.
#         (6) AMENDED 2026-08-28 (DEF-1713) — THE MIGRATED DEPOSIT'S CONTRACT.
#         `post_opening_deposit_batch` / `post_opening_deposit` /
#         `opening_deposit_entry_request` / `cutover_deposit_event`: DR opening
#         clearing / CR deposit liability, dated at cutover (BR-CUS-049, PO-signed),
#         keyed `opening_balance|<account>|cutover-deposit:<batch>`. THE CONTRA LEG IS
#         THIS LANE'S JUDGMENT and no signed document states it — decision log
#         2026-08-28, review-ledger row, and carried on every batch result as
#         `the_contra_leg_is_this_lane_s_judgment`. It does NOT join ❄️ GT-16's
#         tie-out (Σ opening JEs = Σ imported BUCKETS); each batch ties to its own
#         two sides, golden unmoved at 33 PASS / 0 FAIL. Tests:
#         tests/test_def177_def1713_deposit_register_and_books.py.
#         (7) THE `no_importer_calls_this_yet` DETAIL WAS FALSE AND IS CORRECTED —
#         the importer has existed since 2026-08-24; what is still missing is the way
#         OUT (OQ-352). Hard-won law 1, in a stated absence.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
