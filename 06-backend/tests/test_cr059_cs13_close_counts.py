# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 spec CS-13 — the two month-close checklist items that belong
#           to payments and could not be computed. US-LED-015 TC-1 is the
#           surface; US-PAY-020 / US-PAY-021 own the registers being counted.
#           Screens: S42 (close) · S37–S39 (the deposit register)
# Rules:    BR-LED-006 (the five-item close checklist, CONFIRMED — *"runs
#           issued, batches reconciled, bank rec current, accruals posted,
#           remittance recorded"*) · BR-LED-018 (close = WARN + CONFIRM, never a
#           hard lockout) · BR-LED-041 (an unanswerable read reports that it is
#           unanswerable, NEVER "0" — the ledger's own ratified precedent, and
#           it cites DEF-127 *"a zero that means 'I don't know'"*) ·
#           BR-PAY-004 / BR-PAY-019 (a batch is reconciled, or it is not) ·
#           BR-PAY-025 (batches group day × method; the day is the POSTING day)
#           · BR-TEN-003 (a read with no tenant in scope REFUSES) ·
#           CLAUDE.md rule 1 (tenant scoping) · hard-won law 1 (a comment
#           claiming a guarantee is not the guarantee) · law 7 (prove a guard
#           RED before trusting it green)
# Tests:    this file. Companion: tests/test_us_led_015_month_close.py TC-1,
#           which asserted these two items as `unknown` while nothing published
#           the reads.
# ───────────────────────────────────────────────────────
"""The two close-checklist items that belonged to payments and answered nothing.

Two of BR-LED-006's five items — *batches reconciled* and *bank rec current* —
read registers `apps/ledger` may not touch (B1 / BR-TEN-013: no cross-module
ORM). `apps/ledger/close.py` has always NAMED the two callables it wanted, by
exact signature, and reported `unknown` until they existed. They now exist.

**WHAT THIS FILE IS ACTUALLY GUARDING, and it is not the counting.** Counting
rows is easy and no test would be written for it alone. The property under test
is the one the close module already had and that publishing a read could
silently destroy:

    a figure nobody counted must never render as a figure somebody counted.

There are now THREE distinguishable answers where there were two, and each has
a case here:

  * a real **ZERO** — the register was read and nothing is outstanding →
    `complete`. This is the whole point of the change: a utility stops closing
    every month over a typed explanation.
  * a real **COUNT** — n outstanding → `incomplete`, naming n.
  * **UNKNOWN** — the register cannot answer for this window. Two ways in, and
    both are tested: the callable is not published at all, and the callable is
    published but *cannot run*. Publishing a read must not convert the second
    into a crash or, far worse, into a green tick.

**THE BANK-REC ITEM HAS A REAL UNKNOWN AND IT IS NOT AN EDGE CASE** (TC-5). If
no bank statement covering the window has been imported, there are zero bank
lines — and "0 unmatched lines" would tick *bank rec current* green on a month
the bank has not shown us at all. That is DEF-127 exactly, and it is the same
sentence `bankrec_read._decimal_str` already refuses: *"`bank_total` is NULL for
a batch the bank has not shown, and turning that into `"0.00"` is the DEF-127
defect."* So the read answers `None` and the item stays `unknown`.

Every assertion here was driven RED against the unpublished code first
(hard-won law 7); the verbatim failures are in the lane report.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import selectors as billing_selectors
from apps.ledger import close
from apps.payments import bankrec_models as bankrec
from apps.payments import selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

# The window every case in this file asks about — LE-9's July, the same month
# `test_us_led_015_month_close.py` closes.
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
IMPORTED_AT = datetime(2026, 8, 3, 9, 15, tzinfo=dt_timezone.utc)


# ── fixture helpers ─────────────────────────────────────────────────────────
def a_method(tenant):
    """One seeded payment method of this tenant (BR-TEN-036's lookup table)."""
    return tenancy_models.PaymentMethod.objects.filter(tenant=tenant).first()


def a_batch(tenant, *, day, status, code=None, method=None):
    """One deposit batch, written straight to its own register.

    Direct ORM rather than `reconciliation.cut_deposit_batches` deliberately:
    the subject of this file is the COUNT and its honesty, and driving the whole
    payment pipeline would re-assert US-PAY-020 while making the window
    arithmetic hard to read. The batch statuses are the four B2 `batch_status`
    values, used verbatim.
    """
    return bankrec.DepositBatch.objects.create(
        tenant=tenant,
        code=code or f"DEP-{day:%y%m%d}-{status[:3].upper()}",
        method=method or a_method(tenant),
        recorded_total=Decimal("100.00"),
        status=status,
        deposited_on=day,
    )


def a_statement_import(tenant, *, start=JULY_START, end=JULY_END, tag="jul"):
    """A statement file covering `start … end` — what makes the bank side
    readable at all (BR-PAY-028's file+tags idempotency shape)."""
    account = bankrec.BankAccount.objects.create(
        tenant=tenant, name=f"Chase Operating {tag}", mask="4021"
    )
    return bankrec.BankStatementImport.objects.create(
        tenant=tenant,
        bank_account=account,
        period_start=start,
        period_end=end,
        file_name=f"{tag}.csv",
        file_hash=f"hash-{tag}-{tenant.pk}",
        tag_fingerprint=f"tag-{tag}-{tenant.pk}",
        line_count=0,
        imported_at=IMPORTED_AT,
    )


def a_bank_line(tenant, statement, *, day, batch=None, amount=Decimal("100.00")):
    """One statement line. `batch=None` is BR-PAY-019's unmatched line."""
    return bankrec.BankLine.objects.create(
        tenant=tenant,
        statement_import=statement,
        deposit_batch=batch,
        posted_on=day,
        reference="CHECK DEPOSIT 4410",
        amount=amount,
    )


def state_of(code, *, start=JULY_START, end=JULY_END):
    """One checklist item's state, straight off `close_checklist`."""
    checklist = close.close_checklist(period_start=start, period_end=end)
    return next(item for item in checklist["items"] if item.code == code)


# ══ TC-1 · a real zero is a real zero, and it is NOT unknown ════════════════
def test_cr059_tc1__no_outstanding_batches_counts_zero_and_ticks_the_item(brazos):
    """The defect this change exists for: a month with nothing outstanding.

    Every batch of the window is `reconciled`, so the honest answer is the
    INTEGER 0 — not `None`, and not `unknown`. The item goes `complete` and the
    utility stops closing July over a typed explanation.

    `is not None` is asserted separately from `== 0` on purpose: `None == 0` is
    False in Python, but a future refactor returning `None` here would make the
    item `unknown` again and the failure message would say "0 != None" rather
    than naming what broke.
    """
    with tenant_ctx(brazos):
        a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_RECONCILED)
        a_batch(brazos, day=date(2026, 7, 9), status=bankrec.BATCH_RECONCILED)

        answer = selectors.unreconciled_batch_count(JULY_START, JULY_END)
        assert answer is not None, "a readable register must answer a number, never None"
        assert answer == 0

        item = state_of(close.ITEM_BATCHES_RECONCILED)
        assert item.state == close.STATE_COMPLETE
        assert item.state != close.STATE_UNKNOWN


# ══ TC-2 · a real count, and the close says how many ════════════════════════
def test_cr059_tc2__outstanding_batches_are_counted_and_named(brazos):
    """Three of the four batch states are NOT reconciled and all three count.

    `in_transit` (cut, the bank has not shown it), `unmatched` (a statement is
    in and this batch is not tied) and `matched` (tied, not yet reconciled) are
    each outstanding work on the close checklist; only `reconciled` is done.
    """
    with tenant_ctx(brazos):
        a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_IN_TRANSIT)
        a_batch(brazos, day=date(2026, 7, 9), status=bankrec.BATCH_UNMATCHED)
        a_batch(brazos, day=date(2026, 7, 10), status=bankrec.BATCH_MATCHED)
        a_batch(brazos, day=date(2026, 7, 11), status=bankrec.BATCH_RECONCILED)

        assert selectors.unreconciled_batch_count(JULY_START, JULY_END) == 3

        item = state_of(close.ITEM_BATCHES_RECONCILED)
        assert item.state == close.STATE_INCOMPLETE
        assert "3 outstanding" in item.detail


# ══ TC-3 · the window is a window ═══════════════════════════════════════════
def test_cr059_tc3__a_batch_outside_the_window_is_not_this_months_problem(brazos):
    """June's and August's unreconciled batches are not July's close.

    Both boundary days are INSIDE the window — a close that dropped the 1st or
    the 31st would under-report the month by two drawer days.
    """
    with tenant_ctx(brazos):
        a_batch(brazos, day=date(2026, 6, 30), status=bankrec.BATCH_IN_TRANSIT)
        a_batch(brazos, day=JULY_START, status=bankrec.BATCH_IN_TRANSIT)
        a_batch(brazos, day=JULY_END, status=bankrec.BATCH_IN_TRANSIT)
        a_batch(brazos, day=date(2026, 8, 1), status=bankrec.BATCH_IN_TRANSIT)

        assert selectors.unreconciled_batch_count(JULY_START, JULY_END) == 2


# ══ TC-4 · TENANT ISOLATION (CLAUDE.md rule 1) ══════════════════════════════
def test_cr059_tc4__another_utilitys_deposits_are_never_counted(brazos, lonestar):
    """Lone Star Ridge's unreconciled batches are invisible to Brazos Bend.

    The failure this blocks is not a leak of data to a screen — it is a NUMBER:
    a Brazos clerk reading "5 outstanding" over a register that holds two of
    their own, and closing July against another utility's banking.

    Both directions are asserted. A filter that silently matched everything
    would still pass a one-sided check whenever the other tenant happened to be
    empty, which is the shape of a test that cannot fail.
    """
    with tenant_ctx(lonestar):
        a_batch(lonestar, day=date(2026, 7, 8), status=bankrec.BATCH_IN_TRANSIT)
        a_batch(lonestar, day=date(2026, 7, 9), status=bankrec.BATCH_UNMATCHED)
        a_batch(lonestar, day=date(2026, 7, 10), status=bankrec.BATCH_UNMATCHED)

    with tenant_ctx(brazos):
        a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_IN_TRANSIT)
        assert selectors.unreconciled_batch_count(JULY_START, JULY_END) == 1
        assert state_of(close.ITEM_BATCHES_RECONCILED).detail.startswith("1 outstanding")

    with tenant_ctx(lonestar):
        assert selectors.unreconciled_batch_count(JULY_START, JULY_END) == 3


def test_cr059_tc4b__another_utilitys_bank_lines_are_never_counted(brazos, lonestar):
    """The same isolation over the statement side, which has its own table."""
    with tenant_ctx(lonestar):
        statement = a_statement_import(lonestar, tag="ls")
        a_bank_line(lonestar, statement, day=date(2026, 7, 6))
        a_bank_line(lonestar, statement, day=date(2026, 7, 7))

    with tenant_ctx(brazos):
        statement = a_statement_import(brazos, tag="bb")
        a_bank_line(brazos, statement, day=date(2026, 7, 6))
        assert selectors.unmatched_bank_line_count(JULY_START, JULY_END) == 1

    with tenant_ctx(lonestar):
        assert selectors.unmatched_bank_line_count(JULY_START, JULY_END) == 2


def test_cr059_tc4c__both_reads_refuse_with_no_tenant_in_scope(brazos):
    """BR-TEN-003 — no `app.tenant_id`, no answer. Not a zero, not a None.

    A count computed with no tenant in scope is blocked by RLS on PostgreSQL and
    would count every utility's banking on the SQLite developer tier, so the
    refusal is what makes the SQLite run worth anything at all.
    """
    from core import errors

    with tenant_ctx(brazos):
        a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_IN_TRANSIT)

    with pytest.raises(errors.AuthError):
        selectors.unreconciled_batch_count(JULY_START, JULY_END)
    with pytest.raises(errors.AuthError):
        selectors.unmatched_bank_line_count(JULY_START, JULY_END)


# ══ TC-5 · the bank has not shown us this month → UNKNOWN, never zero ═══════
def test_cr059_tc5__no_statement_for_the_window_is_unknown_not_a_green_tick(brazos):
    """DEF-127, defended: zero rows because nobody imported a statement.

    There are no bank lines in July, so a plain `.count()` would answer 0 and
    tick *bank rec current* green on a month the bank has never been asked
    about. The register cannot answer, so it says so, and the close still
    demands a reason (BR-LED-018 — a warn, never a lockout).

    A statement covering JUNE is present, so this is not testing an empty
    database: it is testing that coverage is checked against the WINDOW.
    """
    with tenant_ctx(brazos):
        a_statement_import(brazos, start=date(2026, 6, 1), end=date(2026, 6, 30), tag="jun")

        assert selectors.unmatched_bank_line_count(JULY_START, JULY_END) is None

        item = state_of(close.ITEM_BANK_REC_CURRENT)
        assert item.state == close.STATE_UNKNOWN
        assert not item.complete


def test_cr059_tc5b__a_statement_covering_the_window_makes_zero_a_real_zero(brazos):
    """The mirror of TC-5: the bank HAS shown us July, and every line is tied.

    Same zero, opposite meaning — and the pair is the whole point. One is
    `unknown`, one is `complete`, and no `.count()` alone can tell them apart.
    """
    with tenant_ctx(brazos):
        statement = a_statement_import(brazos)
        batch = a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_RECONCILED)
        a_bank_line(brazos, statement, day=date(2026, 7, 8), batch=batch)

        answer = selectors.unmatched_bank_line_count(JULY_START, JULY_END)
        assert answer is not None
        assert answer == 0
        assert state_of(close.ITEM_BANK_REC_CURRENT).state == close.STATE_COMPLETE


def test_cr059_tc5c__unmatched_lines_are_counted_and_named(brazos):
    """Two lines the statement carries that tie to no batch — S38's fourth tile."""
    with tenant_ctx(brazos):
        statement = a_statement_import(brazos)
        batch = a_batch(brazos, day=date(2026, 7, 8), status=bankrec.BATCH_RECONCILED)
        a_bank_line(brazos, statement, day=date(2026, 7, 8), batch=batch)
        a_bank_line(brazos, statement, day=date(2026, 7, 9))
        a_bank_line(brazos, statement, day=date(2026, 7, 10))
        # August's line rides the same file and is NOT July's problem.
        a_bank_line(brazos, statement, day=date(2026, 8, 2))

        assert selectors.unmatched_bank_line_count(JULY_START, JULY_END) == 2

        item = state_of(close.ITEM_BANK_REC_CURRENT)
        assert item.state == close.STATE_INCOMPLETE
        assert "2 outstanding" in item.detail


def test_cr059_tc5d__a_statement_overlapping_the_window_is_coverage(brazos):
    """A file cut Jun 25 – Jul 24 covers part of July, so July is answerable.

    Statement periods are the BANK's, not the tenant's fiscal calendar, and they
    routinely straddle a month end. Requiring total coverage would make almost
    every real month `unknown` and the change would have bought nothing.
    """
    with tenant_ctx(brazos):
        statement = a_statement_import(
            brazos, start=date(2026, 6, 25), end=date(2026, 7, 24), tag="straddle"
        )
        a_bank_line(brazos, statement, day=date(2026, 7, 6))

        assert selectors.unmatched_bank_line_count(JULY_START, JULY_END) == 1


# ══ TC-6 · a published read that CANNOT RUN is still unknown ════════════════
def test_cr059_tc6__a_read_that_blows_up_reports_unknown_and_never_crashes_the_close(
    brazos, monkeypatch
):
    """The honesty the close module had, kept after the reads were published.

    Before this change `unknown` was reachable only while the callable did not
    exist, and `_seam_item` called it with no guard. Publishing the reads would
    have turned any failure inside them into a 500 on the close screen — a
    finance user locked out of closing the month, which BR-LED-018 forbids in
    the same breath as it forbids a silent close.

    So a read that raises is reported as `unknown` — incomplete, closeable with
    a reason — and the reason it could not run travels in the detail so the
    person reading S42 can act on it.
    """

    def exploding(start, end):
        raise RuntimeError("the deposit register is unreachable")

    monkeypatch.setattr(selectors, "unreconciled_batch_count", exploding)

    with tenant_ctx(brazos):
        item = state_of(close.ITEM_BATCHES_RECONCILED)
        assert item.state == close.STATE_UNKNOWN
        assert not item.complete
        assert "the deposit register is unreachable" in item.detail


def test_cr059_tc6b__an_unpublished_read_still_reports_unknown_by_name(brazos, monkeypatch):
    """The original `unknown` path, unchanged: no callable, no claim.

    ⚠ **`runs_issued` WAS ASSERTED LIVE HERE AND WENT RED ON 2026-09-23
    (`DEF-LED-6616`).** This case read *"`runs_issued` is still genuinely
    unpublished (billing owes `unissued_run_count`), so it is asserted live
    rather than simulated — the one item in this file whose `unknown` nobody had
    to arrange."* **Billing published it** in `b06eba2bb` and the item now
    computes `complete`, so the sentence became false and took the case with it.

    **THE RED WAS THE GUARD DOING ITS JOB, NOT A FAULT.** This is hard-won law
    2's own prescription — *when you write a hold, write the test that fires
    when the hold expires* — working exactly as designed: the day the read
    landed, the suite went red and NAMED it. What was missing is the other half,
    *and when you land a screen, grep for the control that was holding it*.
    So the assertion is not deleted; it is turned over.

    **BOTH HALVES ARE NOW ASSERTED, AND NEITHER IS FREE.** The `unknown` path is
    simulated for all three items the same way (there is no longer an item whose
    absence nobody had to arrange), and the item's RESOLUTION is asserted
    separately in the case below — which is the half that goes red if billing
    ever renames or unpublishes the read, a silent regression to `unknown` that
    nothing else in this file would catch.
    """
    monkeypatch.delattr(selectors, "unmatched_bank_line_count", raising=True)
    monkeypatch.delattr(billing_selectors, "unissued_run_count", raising=True)

    with tenant_ctx(brazos):
        item = state_of(close.ITEM_BANK_REC_CURRENT)
        assert item.state == close.STATE_UNKNOWN
        assert "is not published" in item.detail
        assert item.wanted_reads  # the callable it wants is still NAMED

        runs = state_of(close.ITEM_RUNS_ISSUED)
        assert runs.state == close.STATE_UNKNOWN
        assert "is not published" in runs.detail
        assert "apps.billing.selectors.unissued_run_count" in runs.wanted_reads[0]


def test_cr059_tc6c__runs_issued_is_published_now_and_resolves_through_the_seam(brazos):
    """`DEF-LED-6616`'s other half: the read billing published is REACHED.

    The item stopped being `unknown` on 2026-09-23 and nothing asserted that it
    had. Without this, unpublishing or renaming `unissued_run_count` would drop
    the item silently back to `unknown` — a close checklist quietly reporting a
    typed reason instead of a counted one — and the only case that mentioned the
    callable at all was the one asserting it did NOT resolve.
    """
    # The contract the ledger documents, which is what a rename would break.
    # ⚠ Read from `WANTED_READS` and NOT from the resolved item: `wanted_reads`
    # names what is MISSING, so it is empty once the seam resolves — asserting
    # it on a healthy item would have been a check that cannot fail.
    assert (
        "apps.billing.selectors.unissued_run_count" in close.WANTED_READS[close.ITEM_RUNS_ISSUED][0]
    )

    with tenant_ctx(brazos):
        runs = state_of(close.ITEM_RUNS_ISSUED)
        # Not `unknown`: the seam resolved and an integer came back.
        assert runs.state in (close.STATE_COMPLETE, close.STATE_INCOMPLETE)
        assert "is not published" not in runs.detail
        assert (
            runs.wanted_reads == ()
        ), f"a resolved item still names a read it is waiting for: {runs.wanted_reads}"


# ══ TC-7 · a backwards window is refused, not answered ══════════════════════
def test_cr059_tc7__a_backwards_window_is_refused_by_both_reads(brazos):
    """`end` before `start` is a caller bug, and 0 would hide it.

    Every other refusal in this file protects a clerk from a wrong number; this
    one protects the next agent from a silent empty count.
    """
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            selectors.unreconciled_batch_count(JULY_END, JULY_START)
        with pytest.raises(errors.ValidationError):
            selectors.unmatched_bank_line_count(JULY_END, JULY_START)


# ══ TC-8 · the seam contract the ledger names, asserted from the ledger ═════
def test_cr059_tc8__the_ledger_resolves_both_reads_by_the_exact_names_it_documents(brazos):
    """`WANTED_READS` is the contract, and a rename on either side is a silent
    regression to `unknown` that no other test in this file would catch.

    The strings are parsed rather than eyeballed: the callable named in the
    ledger's own documentation must be the one that actually resolves.
    """
    for code in (close.ITEM_BATCHES_RECONCILED, close.ITEM_BANK_REC_CURRENT):
        wanted = close.WANTED_READS[code][0]
        dotted = wanted.split("(")[0]
        assert dotted.startswith("apps.payments.selectors.")
        name = dotted.rsplit(".", 1)[1]
        assert callable(getattr(selectors, name)), f"{wanted} does not resolve"
