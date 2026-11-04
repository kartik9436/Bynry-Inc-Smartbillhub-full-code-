# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-006 (Pending-billing queue + catch-up sub-runs)
#           Screens: S30 (KPI chip → queue list) · S31 (sub-run mode)
# Rules:    BR-BIL-015 (the queue, its aging and escalation; catch-up SUB-RUNS
#           with scope-keyed idempotency) · BR-BIL-005 (a run key; a sub-run's
#           is parent key + scope) · BR-BIL-034 (excluded work needs a door
#           back, or it is unbillable forever) · BR-BIL-055 (a partial run
#           issues the clean and holds the rest; the queue records WHICH DOOR) ·
#           BR-TEN-043 (aging is measured against a caller's date, never a
#           clock) · CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# Journeys: J16 (held-account catch-up, steps 1–6) · J24 · J2 step 8
# Tests:    this file
# ───────────────────────────────────────────────────────
"""US-BIL-006 — hold ≠ forget, proved from both doors and out the far side.

**THE FAILURE THIS STORY EXISTS TO PREVENT IS SILENT.** BR-BIL-034 says it in
one sentence: the run key is `(tenant, cycle, period)` with no scope term, so
re-running July is refused as a duplicate and an account held in July would be
*unbillable forever* — lost revenue nobody finds until a customer notices they
were never billed. Every test below is a step on the path back: the row exists,
it ages, it escalates, a scoped sub-run bills it, the row closes, and doing the
same catch-up twice is refused.

**TWO DOORS, ONE QUEUE, AND THE DIFFERENCE SURVIVES.** A phase-1 HOLD means
*"we never calculated this"*; a phase-3 MARK-FOR-LATER means *"we calculated it
and it broke at measure-consumption"*. `tc8` asserts a clerk can still tell them
apart in the queue, because the two are fixed differently.

**AGING IS NEVER READ FROM A CLOCK.** Every call below passes `as_of`
explicitly (BR-TEN-043, gate G6), which is also why `tc4`'s escalation boundary
is assertable at all instead of needing a test that travels in time.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from apps.billing import issue, models, pending, runs
from apps.billing.exceptions import BillingRuleError
from core import idempotency

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    a_release,
    a_run,
    an_account,
    an_authorised_run,
)

pytestmark = pytest.mark.django_db

# ── J16's own fixture (US-BIL-006 §4) ───────────────────────────────────────
HELD_ON = date(2026, 8, 1)  # the parent run's exceptions step
REVIEW_DAY = date(2026, 8, 4)  # J16 step 2 — "3 days held"
CATCH_UP_DAY = date(2026, 8, 10)  # J16 step 4 — the read arrived on the 9th
ESCALATION_DAYS = 14  # US-BIL-006 §4's tenant fixture
DAY_FIFTEEN = HELD_ON + timedelta(days=15)  # ACC-1455 "hits day 15"

HOLD_REASON = "staff_hold_missing_read"  # door 1, as `decisions._hold_reason` writes it
BREAK_STAGE = "measure-consumption"  # door 2 — BR-BIL-040 names the stage


def _held_on(row, when: date) -> None:
    """Backdate a queue row's `created_at` so age is a fixture, not a wait.

    `created_at` is `auto_now_add`, so it is written as *now* and then moved
    here with a direct UPDATE. That is the only honest way to test aging without
    a clock: the alternative is patching time, and the whole reason `as_of` is
    an argument (BR-TEN-043) is so that nobody has to.
    """
    models.BillRunExclusion.objects.filter(pk=row.pk).update(
        created_at=datetime(when.year, when.month, when.day, 9, 0, tzinfo=timezone.utc)
    )


def _hold(run, account, *, reason=HOLD_REASON, on=HELD_ON, detail="gas read missing"):
    row = runs.mark_for_later(
        bill_run=run, account_id=str(account.id), reason_code=reason, detail=detail
    )
    _held_on(row, on)
    return row


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the row, the aging, and the chip that ties to the list
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc1__a_held_account_appears_in_the_queue_with_its_age(brazos, dana):
    """J16 steps 1–2: ACC-1201 held Aug 1, reviewed Aug 4 → **3 days**.

    The chip is asserted to TIE to the list rather than merely to be non-zero.
    A chip with its own COUNT and a list with its own WHERE disagree the first
    time one of the two filters moves, and the chip is the number a clerk trusts
    without opening anything — so it is computed FROM the list, and this is the
    assertion that keeps it that way.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        run = a_run(brazos, key="2026-08|parent-07A")
        _hold(run, account)

        rows = pending.pending_rows(as_of=REVIEW_DAY, escalation_days=ESCALATION_DAYS)
        assert len(rows) == 1
        row = rows[0]
        assert row.account_no == "ACC-1201"
        assert row.age_days == 3, "held Aug 1, reviewed Aug 4"
        assert row.escalated is False
        assert row.reason_code == HOLD_REASON
        assert row.detail == "gas read missing"
        assert row.is_open is True
        assert (row.period_start, row.period_end) == (run.period_start, run.period_end)

        chip = pending.pending_count(as_of=REVIEW_DAY, escalation_days=ESCALATION_DAYS)
        assert chip["pending"] == len(rows) == 1
        assert chip["escalated"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — escalation SURFACES; it never bills
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc4__the_row_escalates_after_the_tenant_threshold(brazos, dana):
    """US-BIL-006 TC-4 — fixture 14 days, ACC-1455 *"hits day 15"*.

    The boundary is asserted on BOTH sides, which is the point: day 14 is inside
    the window and day 15 is outside it. `>=` would flag a fourteenth-day row the
    setting says is still fine, and that is a one-character error nobody would
    ever see on a screen.

    **And nothing is billed.** The invoice count is asserted to be zero after an
    escalation, because r1.3 says escalation *"still requires staff action,
    never auto-bills"* and a queue that quietly billed at day 15 would be the
    decision-by-omission the whole five-phase model exists to remove.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1455")
        run = a_run(brazos, key="2026-08|parent-esc")
        _hold(run, account, reason="staff_hold_missing_read", detail="access flagged")

        on_the_threshold = pending.pending_rows(
            as_of=HELD_ON + timedelta(days=ESCALATION_DAYS), escalation_days=ESCALATION_DAYS
        )
        assert on_the_threshold[0].age_days == 14
        assert on_the_threshold[0].escalated is False, "day 14 is inside a 14-day window"

        past_it = pending.pending_rows(as_of=DAY_FIFTEEN, escalation_days=ESCALATION_DAYS)
        assert past_it[0].age_days == 15
        assert past_it[0].escalated is True

        chip = pending.pending_count(as_of=DAY_FIFTEEN, escalation_days=ESCALATION_DAYS)
        assert chip["escalated"] == 1
        assert models.Invoice.objects.count() == 0, "escalation surfaces; it never bills"


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the catch-up sub-run: parent-linked, same period, held scope only
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc2__a_catch_up_is_a_child_run_over_the_parents_period(brazos, dana):
    """J16 step 4 — the read arrives, three holds are caught up.

    Four facts about the child row, and each is a rule rather than a
    convenience: `parent_run_id` is set (r10 #7, a queryable lineage), the
    PERIOD is the parent's (US-BIL-006 TC-2 — *"invoices carry the original
    period"*, so a July catch-up run in August bills July), the idempotency key
    is the parent's key plus the scope (BR-BIL-005/015), and the key CONTAINS
    the parent's own key so the lineage is readable in psql without a join.
    """
    with tenant_ctx(brazos):
        held = [an_account(dana, brazos, account_no=f"ACC-1{n}") for n in ("201", "455", "710")]
        parent = a_run(brazos, key="2026-08|parent-07A")
        for account in held:
            _hold(parent, account)

        child = pending.create_catch_up_run(
            parent_run=parent,
            account_ids=[str(account.id) for account in held],
            run_by=dana.user,
            actor=dana.user,
        )

        assert child.parent_run_id == parent.pk
        assert (child.period_start, child.period_end) == (parent.period_start, parent.period_end)
        assert child.cycle_id == parent.cycle_id
        assert child.status == "draft"
        assert child.idempotency_key.startswith(parent.idempotency_key), (
            "the child's key CONTAINS its parent's, so a human reading bill_runs in psql "
            "can see which run a catch-up belongs to"
        )
        assert child.idempotency_key != parent.idempotency_key
        assert idempotency.CATCH_UP_MARKER in child.idempotency_key


def test_us_bil_006_tc2b__the_scope_key_is_order_and_duplicate_insensitive():
    """{A, B}, {B, A} and {A, A, B} are ONE scope — a pure-function assertion.

    If reordering a checkbox list changed the key, a clerk could bill the same
    two accounts twice by clicking them in the other order, and the duplicate
    guard would report nothing. This is the cheapest possible place to assert
    it, and it needs no database.
    """
    parent = "cycle-uuid|2026-07-01|2026-07-31"
    a, b = "aaa-1", "bbb-2"
    forward = idempotency.catch_up_run_key(parent_key=parent, account_ids=[a, b])
    backward = idempotency.catch_up_run_key(parent_key=parent, account_ids=[b, a])
    repeated = idempotency.catch_up_run_key(parent_key=parent, account_ids=[a, a, b])
    assert forward == backward == repeated
    assert idempotency.catch_up_run_key(parent_key=parent, account_ids=[a]) != forward

    with pytest.raises(idempotency.IdempotencyKeyError, match="scope is empty"):
        idempotency.catch_up_run_key(parent_key=parent, account_ids=[])
    with pytest.raises(idempotency.IdempotencyKeyError, match="PARENT"):
        idempotency.catch_up_run_key(parent_key="", account_ids=[a])


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 (negative) — the same scope twice is refused, with who/when/link
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc5__the_same_catch_up_scope_is_refused_and_a_different_one_is_not(
    brazos, dana
):
    """BR-BIL-015's *"never a colliding re-run"*, at SUB-RUN granularity.

    Both halves matter and the second is the one a naive guard gets wrong: the
    identical scope is blocked, and a catch-up over a **different held subset**
    starts normally. A guard keyed on the parent alone would refuse the second
    one too, and the remaining held accounts would be stuck behind the first
    catch-up forever — which is BR-BIL-034's failure re-created inside the fix
    for it.
    """
    with tenant_ctx(brazos):
        first = an_account(dana, brazos, account_no="ACC-1201")
        second = an_account(dana, brazos, account_no="ACC-1455")
        parent = a_run(brazos, key="2026-08|parent-07A")
        _hold(parent, first)
        _hold(parent, second)

        child = pending.create_catch_up_run(
            parent_run=parent, account_ids=[str(first.id)], run_by=dana.user
        )

        with pytest.raises(pending.DuplicateCatchUp) as refused:
            pending.create_catch_up_run(
                parent_run=parent, account_ids=[str(first.id)], run_by=dana.user
            )
        assert refused.value.existing.pk == child.pk, "the refusal names the run that won"

        other = pending.create_catch_up_run(
            parent_run=parent, account_ids=[str(second.id)], run_by=dana.user
        )
        assert other.pk != child.pk
        assert models.BillRun.objects.filter(parent_run=parent).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 (negative) — the scope must be a SUBSET of the parent's held set
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc6__an_account_never_held_cannot_join_a_catch_up(brazos, dana):
    """US-BIL-006 TC-6, and the consequence is double billing.

    The parent already billed every account it did not hold. Catching one of
    those up would bill it a SECOND time for one period — and both bills would
    be immutable (hard rule 4), so the repair is a credit note and a customer
    conversation. Refused by name, with the stray account listed.
    """
    with tenant_ctx(brazos):
        held = an_account(dana, brazos, account_no="ACC-1201")
        never_held = an_account(dana, brazos, account_no="ACC-9999")
        parent = a_run(brazos, key="2026-08|parent-07A")
        _hold(parent, held)

        with pytest.raises(BillingRuleError, match="never held"):
            pending.create_catch_up_run(
                parent_run=parent,
                account_ids=[str(held.id), str(never_held.id)],
                run_by=dana.user,
            )
        assert models.BillRun.objects.filter(parent_run=parent).count() == 0, (
            "a refused catch-up leaves no row — a half-created sub-run would hold the "
            "scope key against the correct one"
        )

        with pytest.raises(BillingRuleError, match="names the held accounts"):
            pending.create_catch_up_run(parent_run=parent, account_ids=[], run_by=dana.user)


def test_us_bil_006_tc6b__a_resolved_hold_is_no_longer_a_lawful_scope(brazos, dana):
    """A row already caught up is OUT of the held set — it was billed once.

    `held_account_ids` reads UNRESOLVED rows, and this is why. Without the
    filter an account could be caught up, billed, and then caught up again over
    the same period under a scope key that differs only by which other accounts
    travel with it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        parent = a_run(brazos, key="2026-08|parent-07A")
        row = _hold(parent, account)
        assert pending.held_account_ids(parent) == frozenset({str(account.id)})

        models.BillRunExclusion.objects.filter(pk=row.pk).update(
            resolved_at=ISSUED_AT, resolved_by_run=parent
        )
        assert pending.held_account_ids(parent) == frozenset()
        with pytest.raises(BillingRuleError, match="never held"):
            pending.create_catch_up_run(
                parent_run=parent, account_ids=[str(account.id)], run_by=dana.user
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the row CLOSES when the catch-up issues, and the chip decrements
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc3__issuing_the_catch_up_closes_the_queue_row(brazos, dana):
    """J16 step 4's exit: *"ACC-1077 leaves the queue"*, with the link forward.

    The close happens inside `issue_run` rather than on a screen, which is what
    makes it structural: a clerk who never opens the queue still sees the chip
    decrement, and a resolution can never be recorded for a bill that did not
    issue. The forward link (`resolved_by_run`) is asserted, because "closed" is
    not an answer to *which run finally billed them*.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1077")
        parent = a_run(brazos, key="2026-08|parent-07A")
        row = _hold(parent, account, detail="water read missing")

        assert pending.pending_count(as_of=CATCH_UP_DAY)["pending"] == 1

        child = pending.create_catch_up_run(
            parent_run=parent, account_ids=[str(account.id)], run_by=dana.user
        )
        a_release(brazos, child, dana)
        a_priced_draft(brazos, account, child, invoice_no="BL-2608-001077")

        result = issue.issue_run(
            child,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )
        assert len(result.issued) == 1
        assert result.queue_rows_resolved == 1

        row.refresh_from_db()
        assert row.resolved_by_run_id == child.pk
        assert row.resolved_at is not None
        assert pending.pending_count(as_of=CATCH_UP_DAY)["pending"] == 0

        # The row is CLOSED, never deleted — the enter → age → clear history is
        # what an audit reads (US-BIL-006 TC-3, *"audit trail complete"*).
        history = pending.pending_rows(as_of=CATCH_UP_DAY, include_resolved=True)
        assert len(history) == 1 and history[0].is_open is False
        assert history[0].resolved_by_run_id == str(child.pk)


def test_us_bil_006_tc3b__a_bill_for_a_different_period_never_closes_a_hold(brazos, dana):
    """The close is SAME-PERIOD only, and this is the case that proves why.

    An account held for July and billed for August is still owed its July bill.
    Closing the July row on the August run would drop it out of the queue with
    nobody ever billing it — BR-BIL-034's silent lost revenue, re-created by the
    very function written to prevent it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        july = a_run(brazos, key="2026-07|parent")
        row = _hold(july, account)

        august = a_run(brazos, key="2026-08|next-cycle")
        models.BillRun.objects.filter(pk=august.pk).update(
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 31)
        )
        august.refresh_from_db()
        a_release(brazos, august, dana)
        # The August bill bills AUGUST. (Its period was the fixture's June until
        # 2026-09-30 — an August run's bill covering June — which reads as the
        # held month billed once DEF-BIL-8413 closes a row a later bill covers.)
        a_priced_draft(
            brazos,
            account,
            august,
            invoice_no="BL-2609-000001",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
        )

        result = issue.issue_run(
            august,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )
        assert len(result.issued) == 1
        assert result.queue_rows_resolved == 0
        row.refresh_from_db()
        assert row.resolved_at is None, "July's hold is still owed a July bill"


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 / TC-9 — the second door, and a partial run is not a failed run
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc8__the_queue_shows_which_door_a_row_came_through(brazos, dana):
    """BR-BIL-055 — *"we never calculated this"* vs *"it broke at stage 2"*.

    Both doors write the SAME table, which is the design; what must survive is
    the difference, because the first is fixed by entering a read and the second
    is usually fixed by fixing configuration. The phase-3 row also carries the
    STAGE (BR-BIL-040), so the queue groups the way the break list does.
    """
    with tenant_ctx(brazos):
        prepare_side = an_account(dana, brazos, account_no="ACC-1201")
        break_side = an_account(dana, brazos, account_no="ACC-1455")
        run = a_run(brazos, key="2026-08|two-doors")

        _hold(run, prepare_side)
        marked = pending.mark_break_for_later(
            bill_run=run,
            account_id=str(break_side.id),
            stage=BREAK_STAGE,
            reason="calc_unresolved_read",
            detail="no usable read for gas",
        )
        _held_on(marked, HELD_ON)

        rows = {row.account_no: row for row in pending.pending_rows(as_of=REVIEW_DAY)}
        assert rows["ACC-1201"].origin == pending.ORIGIN_PREPARE
        assert rows["ACC-1201"].stage is None, (
            "nothing was calculated for a phase-1 hold, so there is no stage that failed "
            "— showing one would be inventing it"
        )
        assert rows["ACC-1455"].origin == pending.ORIGIN_BREAKS
        assert rows["ACC-1455"].stage == BREAK_STAGE
        assert rows["ACC-1455"].detail == "no usable read for gas"

        chip = pending.pending_count(as_of=REVIEW_DAY)
        assert chip == {"pending": 2, "escalated": 0, "prepare": 1, "breaks": 1}

        with pytest.raises(BillingRuleError, match="records the STAGE"):
            pending.mark_break_for_later(
                bill_run=run, account_id=str(prepare_side.id), stage="", reason="x"
            )


def test_us_bil_006_tc9__a_partial_run_is_a_run_that_worked(brazos, dana):
    """BR-BIL-055 — 1,122 issued and 2 queued is **completed**, not failed.

    Scaled down to 3 and 2 so the assertion is about the SHAPE rather than about
    a loop: the clean bills issue, the queued accounts get no invoice at all,
    and nothing about the two is presented as an error inside the issued bills'
    own result. `broken` is empty — a marked-for-later account is not a break in
    the ISSUE pass, it is an account this run was never going to bill.
    """
    with tenant_ctx(brazos):
        billed = [an_account(dana, brazos, account_no=f"ACC-2{n:03d}") for n in range(3)]
        queued = [an_account(dana, brazos, account_no=f"ACC-3{n:03d}") for n in range(2)]
        run = an_authorised_run(brazos, dana, key="2026-08|partial")

        for index, account in enumerate(billed):
            a_priced_draft(brazos, account, run, invoice_no=f"BL-2608-00{index:04d}")
        for account in queued:
            pending.mark_break_for_later(
                bill_run=run,
                account_id=str(account.id),
                stage=BREAK_STAGE,
                reason="calc_unresolved_read",
                detail="no usable read for gas",
            )

        result = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana.user,
        )
        assert len(result.issued) == 3
        assert result.broken == (), "a held account is not a break in the issue pass"
        assert pending.pending_count(as_of=CATCH_UP_DAY)["pending"] == 2
        assert (
            models.Invoice.objects.filter(account_id__in=[a.id for a in queued]).count() == 0
        ), "nothing partial is created for a queued account"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 (isolation) — queues and sub-runs never cross a tenant boundary
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_006_tc7__another_tenants_queue_and_parent_run_are_invisible(brazos, lonestar, dana):
    """Hard rule 1 · HR-1 — and BOTH halves are probed.

    The QUEUE half is the obvious one. The SUB-RUN half is the dangerous one: a
    catch-up created against another tenant's parent run would write a
    `bill_runs` row under this tenant pointing at a run they cannot see, and its
    scope check would read that run's holds. It answers ABSENT — the same door
    an unknown id takes, so existence cannot be probed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-1201")
        brazos_run = a_run(brazos, key="2026-08|brazos")
        _hold(brazos_run, account)
        assert pending.pending_count(as_of=REVIEW_DAY)["pending"] == 1

    with tenant_ctx(lonestar):
        assert pending.pending_rows(as_of=REVIEW_DAY) == ()
        assert pending.pending_count(as_of=REVIEW_DAY)["pending"] == 0
        assert pending.held_account_ids(brazos_run) == frozenset()
        from core import errors

        with pytest.raises(errors.NotFoundError):
            pending.create_catch_up_run(
                parent_run=brazos_run, account_ids=[str(account.id)], run_by=dana.user
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-006@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-15 by Eng-Lead (US-BIL-006 lane)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S30's chip/list unbuilt, REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_bil_006_pending_queue.py
# exceptions: (1) aging is fixture-backdated with a direct UPDATE on
#         `created_at` (auto_now_add), which is the only way to test aging
#         without patching a clock — and `as_of` being an argument is why no
#         clock is patched anywhere here. (2) TC-2's J16 read-import step is
#         metering's and is not re-tested; what is asserted is the sub-run the
#         arriving read unblocks.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
