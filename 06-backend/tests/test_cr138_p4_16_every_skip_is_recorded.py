# ── Trace ──────────────────────────────────────────────
# Change:   `CR-138-BRC07` `P4.16` — *"Every skip is recorded and shown — five
#           reasons. **No silent exclusion: the one thing a collections trail
#           may not contain.**"*
# Rules:    BR-PAY-017 (four rungs, five stop conditions) · BR-CUS-039 / A15 (a
#           medical hold is excluded from EVERY ladder step) · BR-PAY-016 (the
#           payment-plan pause) · CLAUDE.md hard rule 6 (the same-day guard) ·
#           hard rule 7 (every money action writes `audit_log`) · hard-won law
#           7 (a check that cannot cover its whole subject prints what it
#           SKIPPED beside what it checked)
# Defects:  DEF-3151 (`partial_payment_pause` has never fired — no caller
#           supplies `recent_payments`; `OQ-1320` owns the window) ·
#           DEF-3150 (per PASS is not per DAY — the same-day guard)
# Screens:  7·3a Ladder (S34 · PAY-B) · 7·3d Notice (S35)
# Database: the default suite — in-memory SQLite — AND re-run whole on real
#           PostgreSQL 16 (`sbh_pgtest_p4`), because this file WRITES on every
#           path and hard-won law 14's trap is a write that fails inside a
#           transaction. Both results are in the lane report.
# ───────────────────────────────────────────────────────
"""NO SILENT EXCLUSION — AND THE EXISTING TEST PROVED ONE REASON OUT OF EIGHT.

⚠ **WHAT WAS ALREADY COVERED.** `test_cr138_p4_3_p4_12_p4_13_debtor_credit_
notices.py::test_EVERY_SKIP_IS_RECORDED_no_silent_exclusion` takes ONE account
with no bill, presses send, and proves the `nothing_overdue` skip reaches
`notice_history`. That case is real and is not repeated here.

⚠ **WHAT IT CANNOT SEE, AND IT IS THE WHOLE OF `P4.16`.** `ladder` declares
**eight** skip reasons. One of them was proved. The failure a collections trail
cannot survive is **an account excluded for a reason nobody recorded**, and
every reason is its own code path: the plan pause is decided in
`collections_read` BEFORE `decide` is ever called, the medical hold and the
floor are decided inside `decide`, the same-day guard was added two weeks later
by `DEF-3150`, and the absent-from-the-board case is decided in
`notices_by_hand` itself. **A test of one reason tells you nothing about the
other seven**, because they do not share a line of code — only a promise.

So this file walks the VOCABULARY rather than a scenario: it takes
`ladder`'s own `SKIP_*` constants, reaches as many as the hand-send path can
reach, and **prints the ones it could not reach and why**. A check that
silently covered five of eight would be the same shape of defect as the thing
it is checking (law 7 — *a declared blind spot with no number beside it is
indistinguishable from an empty one*).

    reached here, each with a recorded `notice_history` row
      below_ladder_floor · medical_hold · payment_plan_pause ·
      already_noticed_today · next_step_not_due · ladder_complete
      (+ nothing_overdue, covered by the sibling file above)

    NOT reachable, stated rather than hidden
      partial_payment_pause — `DEF-3151`. `collections_read` calls
      `ladder.decide` with NO `paid_recently`, so this stop condition has
      never fired anywhere in the product and cannot fire through this
      endpoint. `OQ-1320` (*"recently" over what window*) is what unblocks
      it. The case below asserts it is STILL unreachable, so the day somebody
      supplies the argument this file goes red and names the gap.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:**

  * *The row could be written with the WRONG reason and still be a row.* Every
    case asserts the recorded `skip_reason` equals the specific constant, and
    the response's `skipped[]` entry agrees with the stored row — two surfaces,
    one fact, because a trail that disagrees with the screen is worse than one
    that is silent.
  * *The account could be skipped for a DIFFERENT reason than the one set up*
    — an account below the floor is also, trivially, an account not yet due.
    Each fixture is built so exactly one condition applies, and the order
    `decide` evaluates them in is asserted where two could collide.
  * *`notice_history` could hold a row from an earlier step in the fixture.*
    Every case counts the rows for THAT account after the send and asserts the
    count, not merely that one exists.

PROVED RED, through `pytest`:
  with `_skip`'s `notices.record_notice(...)` call removed —
    FAILED …::test_a_medical_hold_is_RECORDED_and_not_merely_refused
    AssertionError: the skip left no trace — P4.16's 'no silent exclusion'
  with `_skip` made to record `ladder.SKIP_NOTHING_OVERDUE` for every reason —
    FAILED …::test_the_floor_skip_carries_ITS_OWN_reason
    assert 'nothing_overdue' == 'below_ladder_floor'
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.payments import ladder, notices, notices_api
from apps.payments.collections_models import AccountCollectionState, NoticeHistory

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

from tests.test_us_ten_helpers import api_call  # noqa: E402 — after the star import

#: The prototype's own S34 debtor — 91 days late, **$948.20** — and the
#: business day every case is taken on (`BR-TEN-043`: named, never a clock).
OWED = Decimal("948.20")
DUE_ON = date(2026, 4, 22)
AS_OF = date(2026, 8, 16)
FLOOR = "25.00"

#: `ladder`'s WHOLE vocabulary, read off the module so a ninth reason minted
#: tomorrow appears here rather than being added to a list by hand.
ALL_SKIP_REASONS = {
    name: getattr(ladder, name) for name in dir(ladder) if name.startswith("SKIP_")
}

#: The one this endpoint cannot reach, and why — law 7's "print what you
#: skipped beside what you checked".
UNREACHABLE = {
    ladder.SKIP_PARTIAL_PAYMENT: (
        "DEF-3151 — `collections_read.ladder_board` calls `ladder.decide` with no "
        "`paid_recently`, so BR-PAY-016's partial-payment pause has never fired in this "
        "product. OQ-1320 (*'recently' over what window*) is what unblocks it."
    ),
}


def _post(view, tenant, *, actor, role="billing_clerk", data=None, **kw):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data or {}, **kw)


def _send(tenant, actor, account, *, medical=(), floor=FLOOR, as_of=AS_OF, tone="friendly"):
    """One press of **Send notice ✓** over one account, exactly as 7·3d does."""
    return _post(
        notices_api.collections_notices,
        tenant,
        actor=actor,
        data={
            "account_ids": [str(account.pk)],
            "tone": tone,
            "as_of": as_of.isoformat(),
            "balance_floor": floor,
            "medical_hold_account_ids": [str(a.pk) for a in medical],
            "idempotency_key": str(uuid.uuid4()),
        },
    )


def _a_debtor(actor, tenant, *, owed=OWED, due_on=DUE_ON):
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2604-{uuid.uuid4().hex[:6]}",
        total=owed,
        issued_on=due_on,
    )
    return account


def _rows_for(tenant, account) -> list[NoticeHistory]:
    with tenant_ctx(tenant):
        return list(
            NoticeHistory.objects.filter(tenant_id=tenant.id, account_id=account.pk).order_by("id")
        )


def _assert_skipped_and_recorded(tenant, account, response, reason: str) -> None:
    """The two halves of `P4.16`, asserted together and never one alone.

    **RECORDED** — a `notice_history` row with `OUTCOME_SKIPPED` and THIS
    reason. **SHOWN** — the same reason in the `skipped[]` the screen renders.
    Either half alone passes while a clerk is misled: a row nobody displays is
    a trail with no reader, and a sentence with no row behind it is a screen
    that will disagree with the account's history tomorrow.
    """
    assert response.status_code == 200, response.data
    assert response.data["sent"] == [], "this account should not have been written to"
    assert len(response.data["skipped"]) == 1, response.data["skipped"]
    assert response.data["skipped"][0]["reason"] == reason

    rows = _rows_for(tenant, account)
    assert rows, "the skip left no trace — P4.16's 'no silent exclusion'"
    assert len(rows) == 1, f"expected exactly one trail row, found {len(rows)}"
    assert rows[0].outcome == notices.OUTCOME_SKIPPED
    assert rows[0].skip_reason == reason
    assert rows[0].occurred_on == AS_OF


# ══════════════════════════════════════════════════════════════════════════
# THE FIVE STOP CONDITIONS, ONE CASE EACH
# ══════════════════════════════════════════════════════════════════════════
def test_the_floor_skip_carries_ITS_OWN_reason(brazos, marcus):
    """**$2.40 owed against a $25.00 floor.**

    PO 2026-08-12 (OQ-137/OQ-157): the floor covers the WHOLE ladder, not just
    the late fee, because the certified final letter costs about **$8.00** to
    send. An account under it is excluded — and a clerk looking at why must be
    able to read *"too small to chase"* rather than finding nothing at all.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos, owed=Decimal("2.40"))
    answered = _send(brazos, marcus, account)
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_BELOW_FLOOR)


def test_a_medical_hold_is_RECORDED_and_not_merely_refused(brazos, marcus):
    """`BR-CUS-039` / A15 — excluded from EVERY ladder step.

    ⚠ **THIS IS THE CASE THE WHOLE TASK IS FOR.** An account left out for a
    medical certificate and an account nobody ever chased look IDENTICAL on
    S34's *Notice history* column unless the exclusion is written down. One of
    them is a compliance decision with a reason; the other is a customer who
    fell through. J4 step 2's contract is that they never read the same.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos)
    answered = _send(brazos, marcus, account, medical=[account])
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_MEDICAL_HOLD)


def test_an_account_on_a_PLAN_is_recorded_as_paused_not_as_nothing(brazos, marcus):
    """`BR-PAY-016` — the pause is decided BEFORE the rung.

    `collections_read` returns `runs: False` with `SKIP_PLAN_PAUSED` without
    calling `decide` at all, which makes this the one stop condition that does
    not share a line of code with any of the others. A test of the floor says
    nothing about it.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos)
        plan = _a_paused_plan(brazos, account)
    assert plan is not None, "the fixture could not build a plan — see the helper"
    answered = _send(brazos, marcus, account)
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_PLAN_PAUSED)


def test_a_letter_already_sent_TODAY_stops_the_next_one_and_says_so(brazos, marcus):
    """CLAUDE.md hard rule 6 / `DEF-3150` — *per PASS is not per DAY*.

    On an account 116 days overdue **all four rungs are past due at once**, so
    without this guard four presses in one afternoon post four letters, the
    last a certified one at real postage. The guard stops the second press —
    and the second press must still leave a trail, or a clerk who pressed twice
    has no way to tell a refusal from a send that vanished.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos)
        AccountCollectionState.objects.update_or_create(
            tenant_id=brazos.id,
            account_id=account.pk,
            defaults={
                "tier": ladder.TIER_FRIENDLY,
                "tier_sent_on": AS_OF,
                "last_notice_on": AS_OF,
            },
        )
    answered = _send(brazos, marcus, account)
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_ALREADY_NOTICED_TODAY)


def test_a_step_that_is_not_due_YET_is_recorded_rather_than_sent_early(brazos, marcus):
    """*"Nothing is sent early."*

    A bill that fell due yesterday is a real outstanding position and a real
    debtor — and the reminder does not fall due for days yet. The account is
    excluded, on purpose, and the exclusion is the answer to *"why did my
    selection of twelve send nine?"*
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos, due_on=AS_OF - timedelta(days=1))
    answered = _send(brazos, marcus, account)
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_NOT_DUE_YET)


def test_a_ladder_already_EXHAUSTED_is_not_a_drop_off_and_says_which(brazos, marcus):
    """PO 2026-08-11: *"nodrop we chase for payments until write off"*.

    An account that has had the 48-hour certified final has no automatic step
    left. That is not the same as owing nothing, and a trail that recorded it
    as `nothing_overdue` would tell a clerk the debt had gone away.
    """
    with tenant_ctx(brazos):
        account = _a_debtor(marcus, brazos)
        AccountCollectionState.objects.update_or_create(
            tenant_id=brazos.id,
            account_id=account.pk,
            defaults={
                "tier": ladder.TIER_FINAL_48_HOUR,
                "tier_sent_on": AS_OF - timedelta(days=4),
                "last_notice_on": AS_OF - timedelta(days=4),
            },
        )
    answered = _send(brazos, marcus, account)
    _assert_skipped_and_recorded(brazos, account, answered, ladder.SKIP_LADDER_COMPLETE)


# ══════════════════════════════════════════════════════════════════════════
# THE VOCABULARY ITSELF — what this file could NOT reach, and why
# ══════════════════════════════════════════════════════════════════════════
def test_every_skip_reason_is_either_EXERCISED_here_or_NAMED_unreachable():
    """Law 7 — *print what you skipped beside what you checked*.

    `ladder` declares its skip reasons as module constants. If somebody mints a
    ninth tomorrow it arrives here automatically, and this case goes red until
    a lane either writes its scenario or states why the hand-send path cannot
    produce it. A vocabulary that grows faster than its coverage is exactly how
    `DEF-PAY-6281` put a live skip reason on a clerk's screen as silence.
    """
    exercised = {
        ladder.SKIP_BELOW_FLOOR,
        ladder.SKIP_MEDICAL_HOLD,
        ladder.SKIP_PLAN_PAUSED,
        ladder.SKIP_ALREADY_NOTICED_TODAY,
        ladder.SKIP_NOT_DUE_YET,
        ladder.SKIP_LADDER_COMPLETE,
        # covered by test_cr138_p4_3_p4_12_p4_13_debtor_credit_notices.py
        ladder.SKIP_NOTHING_OVERDUE,
    }
    declared = set(ALL_SKIP_REASONS.values())
    unaccounted = declared - exercised - set(UNREACHABLE)
    assert not unaccounted, (
        f"{len(unaccounted)} skip reason(s) are declared and neither exercised nor "
        f"declared unreachable: {sorted(unaccounted)}. A reason with no case is a way "
        "an account can leave a collections run with nobody able to say why."
    )
    # …and the count is printed as a figure rather than implied by a pass.
    assert len(declared) == len(exercised) + len(UNREACHABLE) == 8


def test_the_partial_payment_pause_is_STILL_unreachable_and_this_is_the_alarm(brazos, marcus):
    """`DEF-3151` — a stop condition that has never stopped anything.

    `collections_read` builds every board row through `ladder.decide` **without
    `paid_recently`**, so `BR-PAY-016`'s pause cannot fire however much a
    customer has paid. This case asserts the absence by reading the call site,
    so the day a lane starts supplying the argument this goes RED and the
    coverage list above is forced to grow with it — rather than the reason
    quietly becoming reachable and untested.
    """
    import inspect

    from apps.payments import collections_read

    source = inspect.getsource(collections_read.ladder_board)
    assert "paid_recently" not in source, (
        "`ladder_board` now supplies `paid_recently`, so BR-PAY-016's partial-payment "
        "pause CAN fire. DEF-3151 is fixed — add a case for "
        f"{ladder.SKIP_PARTIAL_PAYMENT!r} above and take it off UNREACHABLE."
    )
    assert ladder.SKIP_PARTIAL_PAYMENT in UNREACHABLE


# ── fixtures that need more than one row ───────────────────────────────────
def _a_paused_plan(tenant, account):
    """A payment plan that pauses the chase, built through payments' own model.

    Deliberately NOT a stub: `collections_read` asks `dunning.collections_pause
    _for_many`, which reads the real table, so a faked pause would prove this
    lane's idea of the seam rather than the seam.
    """
    from apps.payments import collections_models

    # ACTIVE **and CURRENT** — `_pause_decision` pauses only when both hold.
    # No instalment is due yet (the first falls a week after `as_of`), so
    # `outstanding_installments` is empty and `PAUSE_ACTIVE_AND_CURRENT` is the
    # decision. A plan merely PROPOSED pauses nothing (BR-CUS-044) and a plan
    # BEHIND resumes the chase — either would silently give this case a
    # different skip reason, which is what the per-reason assertion catches.
    return collections_models.PaymentPlan.objects.create(
        tenant_id=tenant.id,
        account_id=account.pk,
        total_amount=OWED,
        down_payment=Decimal("0"),
        currency="USD",
        installment_count=10,
        cadence="monthly",
        status=collections_models.PLAN_ACTIVE,
        proposed_on=AS_OF - timedelta(days=30),
        signed_on=AS_OF - timedelta(days=29),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 `P4.16` · blueprint p022 (the task row) · BR-PAY-017 ·
#         BR-PAY-016 · BR-CUS-039 · CLAUDE.md hard rule 6 · J4 step 2
# generated: 2026-09-23 by LANE P4-TESTS
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# gates: RED PROVED FIRST through `pytest` — `_skip` with its `record_notice`
#         call removed failed every case on "the skip left no trace", and
#         `_skip` hardcoded to `SKIP_NOTHING_OVERDUE` failed each case on its
#         OWN reason. Re-run whole on real PostgreSQL 16, because every case
#         WRITES (law 14).
# exceptions: (1) `partial_payment_pause` IS NOT EXERCISED and that is
#         `DEF-3151`, not an omission — it is named in `UNREACHABLE`, and the
#         call-site case above goes red the day it becomes reachable.
#         (2) `nothing_overdue` is proved in the sibling P4.13 file and is
#         listed here only so the vocabulary arithmetic is complete. Two files
#         asserting one figure is how they come to disagree.
# status: VERIFIED-UNRATIFIED
