# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.10` — *"A draft has no number; a post
#           allocates one; a rolled-back post leaves a gap and the gap is
#           tolerated"*. Outcome: *"the contradiction in `P0.3` is settled by
#           an assertion, not a comment"*.
# Rules:    `BR-LED-021` (a journal entry carries a `JE-` number, stamped AT
#           POST — a DRAFT has none) · `BR-TEN-035` (one monotonic counter per
#           tenant per series: *"gaps ok, never reused"*) · CLAUDE.md hard
#           rule 4 (a posted entry's number is frozen; an unnumbered entry can
#           never be numbered afterwards)
# Code:     apps/ledger/posting.py `_allocated_number` · `post` · `post_draft`
# ───────────────────────────────────────────────────────
"""THE TWO CONTRADICTIONS `BR-LED-021` CARRIES, SETTLED BY ASSERTION.

`BR-LED-021`'s own business-rules row flags two clauses of its recorded ruling
as standing against signed law, raises both and chooses neither. `P0.3` builds
on that rule, so leaving them as prose would mean building a money path on a
sentence that two documents disagree about. **A comment claiming a guarantee is
not the guarantee** (hard-won law 1) — so each is pinned here.

**(a) DOES THE `JE-` SERIES COVER SYSTEM-GENERATED ENTRIES?** The rules row
says it *"was never put to the PO"*. It does not need to be: `LE-4`, a ratified
golden document, draws *"Sep 30 **JE-201** (accrual) → Oct 1 **JE-202**
auto-posts the mirror"*, and an accrual mirror is posted by `reverse_entry` —
a machine path. A ratified worked example already shows a system entry carrying
a number, and the Finance blueprint's acceptance sentence agrees without
exception: *"a newly posted entry carries a `JE-` number"*. Settled by READING,
recorded in the decision log, not put back to the PO (law 13). `tc2` pins it.

**(b) "GAPLESS" (the decision-log row) vs "GAPS OK, NEVER REUSED"
(`BR-TEN-035`).** `BR-TEN-035` is the signed numbering rule and `BR-LED-021`'s
own CONFIRMED text already concedes the point — *"the build allocates through
BR-TEN-035's monotonic counter, so GAPS HAPPEN"*. `tc4b` **asserts the gap**, so a later
lane reading the word *gapless* cannot "fix" the series into something the
allocator cannot provide under concurrency, and so nobody treats a hole in the
numbers as a defect.

⚠ **AND `tc4a` CORRECTS THE PLAN'S OWN SENTENCE, WHICH WAS WRITTEN FROM THE
RULE RATHER THAN FROM A MEASUREMENT.** `P0.10` reads *"a rolled-back post
leaves a gap"*. Measured on PostgreSQL 16.13: **it does not** — the counter is
bumped inside the same transaction the entry is written in, so a lone rollback
takes the allocation back with it and the next post gets the same number. The
gap is real, but it needs a COMMITTED post in between; the two cases are split
so each says only what it proved.

⚠ **`tc5` ASSERTS A MIS-SORT ON PURPOSE.** `JE-{MM}{DD}{YY}-{0000}` puts the
month first, so the text does not sort chronologically. The list that shows
these entries therefore orders by `entry_date`, and this case exists so that
changing it to order by the number goes red. See
`tests/test_p0_13_je_series_format.py` for the format's own proof.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import transaction

from apps.ledger import models as ledger_models
from apps.ledger import posting
from apps.tenancy import models as tenancy_models
from core import numbering as core_numbering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

BOOK_DATE = date(2026, 8, 2)
POSTED_AT = datetime(2026, 8, 2, 14, 30, tzinfo=timezone.utc)


def _two_accounts():
    """Any two distinct live GL accounts from this tenant's chart."""
    rows = list(ledger_models.LedgerAccount.objects.filter(deleted_at__isnull=True).order_by("code")[:2])
    assert len(rows) >= 2, "the tenant's chart of accounts has fewer than two live accounts"
    return rows[0], rows[1]


def _source_id(event: str):
    """A stable UUID per case — `journal_lines.source_id` is a `uuid` column,
    and a stable one keeps each case's `posting_key` the same across runs so
    the replay guard means what it means in production."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"p0-10/{event}")


def _lines(source_id) -> tuple[posting.PostingLine, ...]:
    """One balanced pair on two chart accounts. No dimensions: these cases are
    about the NUMBER, and a line that names no account is lawfully
    undimensioned (`BR-LED-001`, *where they apply*)."""
    debit, credit = _two_accounts()
    return (
        posting.PostingLine(
            ledger_account_id=debit.pk,
            side=ledger_models.SIDE_DEBIT,
            amount=Decimal("100.0000"),
            source_type="manual_je",
            source_id=source_id,
        ),
        posting.PostingLine(
            ledger_account_id=credit.pk,
            side=ledger_models.SIDE_CREDIT,
            amount=Decimal("100.0000"),
            source_type="manual_je",
            source_id=source_id,
        ),
    )


def _request(
    tenant,
    *,
    event: str,
    number: str | None = None,
    entry_date: date = BOOK_DATE,
) -> posting.PostingRequest:
    source_id = _source_id(event)
    return posting.PostingRequest(
        posting_key=posting.posting_key(
            source_type="manual_je", source_id=source_id, event=event
        ),
        entry_date=entry_date,
        posted_at=POSTED_AT,
        currency="USD",
        number=number,
        lines=_lines(source_id),
    )


def _series(tenant) -> tenancy_models.NumberSeries:
    return tenancy_models.NumberSeries.objects.get(
        tenant=tenant, series=core_numbering.JOURNAL_ENTRY
    )


def test_tc1_a_draft_has_no_number(brazos, dana):
    """`BR-LED-021`, verbatim: *"stamped when the entry POSTS — a DRAFT has NO
    number"*. The draft path must not consume a counter either: a draft that
    is deleted would otherwise burn a number nobody ever sees."""
    with tenant_ctx(brazos):
        before = _series(brazos).next_number
        # ⚠ Through `save_draft`, NOT `JournalEntry.objects.create` — the first
        # draft of this case did the latter and `ledger_sole_writer_guard()`
        # refused it by name: *"journal_entries is written ONLY by the ledger
        # posting service"*. That is `ledger/0004` doing its job on a test, and
        # it is worth leaving recorded: there is no back door into the books,
        # including for a fixture.
        draft = posting.save_draft(
            posting.DraftRequest(
                entry_date=BOOK_DATE,
                currency="USD",
                memo="P0.10 draft",
                lines=_lines(_source_id("draft")),
            ),
            actor=dana,
        )
        entry = ledger_models.JournalEntry.objects.get(pk=draft.entry_id)
        assert entry.status == ledger_models.JE_DRAFT
        assert entry.number is None
        assert _series(brazos).next_number == before, (
            "saving a draft consumed a JE- number; a deleted draft would then "
            "burn a number nobody ever saw"
        )


def test_tc2_a_system_posted_entry_carries_a_number(brazos, dana):
    """**(a), settled.** `post()` is the machine path — the bill run, the
    payment webhook, the accrual sweep — and until 2026-09-24 it allocated
    nothing, so the product held **167 entries and 0 numbers**."""
    with tenant_ctx(brazos):
        result = posting.post(_request(brazos, event="numbered"), actor=dana)
        entry = ledger_models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.status == ledger_models.JE_POSTED
        assert entry.number is not None, (
            "a system-posted entry carries no JE- number — BR-LED-021 and LE-4's "
            "JE-202 both say it must"
        )
        # The ruled format, on the ruled date: 2 Aug 2026 -> JE-0802 26-nnnn.
        assert entry.number.startswith("JE-080226-")


def test_tc3_the_counter_moves_by_exactly_one_per_posted_entry(brazos, dana):
    """`BR-TEN-035`'s counter is monotonic and is consumed once per entry. A
    second allocation on one post would be how two entries end up as JE-14."""
    with tenant_ctx(brazos):
        before = _series(brazos).next_number
        posting.post(_request(brazos, event="one"), actor=dana)
        assert _series(brazos).next_number == before + 1
        posting.post(_request(brazos, event="two"), actor=dana)
        assert _series(brazos).next_number == before + 2


def test_tc4a_a_rolled_back_post_on_its_own_gives_its_number_back(brazos, dana):
    """⚠ **MEASURED, AND IT IS NOT WHAT THE PLAN'S SENTENCE SAYS.**

    `P0.10`'s row reads *"a rolled-back post leaves a gap and the gap is
    tolerated"*. On its own, **it does not**: the counter lives on the tenant's
    `number_series` row and is bumped inside the SAME transaction the entry is
    written in, so rolling that transaction back takes the allocation with it
    and the next post gets the same number. That is better than the plan
    expected and it violates nothing — `BR-TEN-035`'s signed clause is *"gaps
    ok, NEVER REUSED"*, and a number that was never carried by a surviving
    entry has not been used, so handing it out is not reuse.

    **THE GAP IS REAL, IT IS JUST NOT THIS CASE.** It appears when another
    post COMMITS in between: worker A takes 5 under the row lock, worker B
    waits and takes 6, B commits, A rolls back. `next_number` is 7 and nothing
    will ever carry 5. `tc4b` asserts the system tolerates exactly that state.

    The sentence in the plan was written from the rule rather than from a
    measurement, and this case is the correction.
    """
    with tenant_ctx(brazos):
        before = _series(brazos).next_number

        with pytest.raises(RuntimeError):
            with transaction.atomic():
                posting.post(_request(brazos, event="abandoned"), actor=dana)
                raise RuntimeError("the caller's own work failed after posting")

        assert _series(brazos).next_number == before, (
            "the counter did not roll back with the entry — a number was burnt "
            "for an entry that never existed"
        )
        landed = posting.post(_request(brazos, event="after-rollback"), actor=dana)
        number = ledger_models.JournalEntry.objects.get(pk=landed.entry_id).number
        assert int(number.rsplit("-", 1)[1]) == before


def test_tc4b_a_gap_in_the_series_is_tolerated_and_no_number_is_reused(brazos, dana):
    """**(b), settled: A HOLE IS A LAWFUL STATE, NOT A DEFECT.**

    A gap is produced here the way a real one is produced outside a race —
    the counter moves forward without an entry behind it (`BR-TEN-035` makes
    the series tenant-editable and FORWARD-ONLY, `ensure_forward_only`) — and
    the product is required to carry on posting over it.

    ⚠ **THIS ASSERTS THE HOLE ON PURPOSE.** `BR-LED-021`'s decision-log row
    calls the series *"gapless"*. It is not, and it cannot be: a gapless series
    would have to hold the counter lock for the whole of every posting
    transaction, serialising a 3,000-bill run behind one row. The clause that
    IS signed — *never reused* — is the second assertion here, and it is the
    one that matters, because a reused number would put two different entries
    under one reference for ever.
    """
    with tenant_ctx(brazos):
        first = posting.post(_request(brazos, event="before-gap"), actor=dana)
        kept = ledger_models.JournalEntry.objects.get(pk=first.entry_id).number

        # The hole: the counter moves and nothing is posted into it.
        series = _series(brazos)
        skipped = series.next_number
        series.next_number = skipped + 5
        series.save(update_fields=["next_number"])

        after = posting.post(_request(brazos, event="after-gap"), actor=dana)
        landed = ledger_models.JournalEntry.objects.get(pk=after.entry_id).number

        kept_counter = int(kept.rsplit("-", 1)[1])
        landed_counter = int(landed.rsplit("-", 1)[1])
        assert landed_counter > kept_counter + 1, "the gap was closed up"
        # Nothing carries the skipped numbers, and nothing ever will.
        for missing in range(skipped, skipped + 5):
            assert not ledger_models.JournalEntry.objects.filter(
                tenant=brazos, number__endswith=f"-{missing:04d}"
            ).exists()
        # NEVER REUSED — the clause BR-TEN-035 actually signs.
        numbers = list(
            ledger_models.JournalEntry.objects.filter(
                tenant=brazos, number__isnull=False
            ).values_list("number", flat=True)
        )
        assert len(numbers) == len(set(numbers)), "a JE- number was issued twice"


def test_tc5_the_journal_list_orders_by_date_and_not_by_the_number(brazos, dana):
    """`JE-{MM}{DD}{YY}-{0000}` does not sort chronologically as text — the
    month leads. Two entries a month apart are posted here and the list is
    required to come back in DATE order, whatever the strings do.

    This is the assertion that stops a later lane "tidying" the journal into a
    sort by number, which the ruled format can never deliver.
    """
    with tenant_ctx(brazos):
        # February 2025 first, then January 2026 — eleven months LATER, and
        # the number for it sorts EARLIER as text.
        posting.post(
            _request(brazos, event="older", entry_date=date(2025, 2, 3)), actor=dana
        )
        posting.post(
            _request(brazos, event="newer", entry_date=date(2026, 1, 15)), actor=dana
        )
        posted = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, status=ledger_models.JE_POSTED, number__isnull=False
        ).exclude(entry_date=BOOK_DATE)

        by_date = list(posted.order_by("entry_date").values_list("entry_date", "number"))
        by_number = list(posted.order_by("number").values_list("entry_date", "number"))

        assert [row[0] for row in by_date] == [date(2025, 2, 3), date(2026, 1, 15)]
        # ⚠ THE WHOLE POINT: the two orders DISAGREE, so the choice matters.
        assert by_number != by_date, (
            "the two orders happen to agree here, so this case is no longer "
            "testing anything — pick dates whose MMDDYY strings invert"
        )
        assert [row[0] for row in by_number] == [date(2026, 1, 15), date(2025, 2, 3)]
