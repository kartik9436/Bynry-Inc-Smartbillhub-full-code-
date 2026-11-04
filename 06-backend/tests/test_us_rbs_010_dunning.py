# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-012 (EP-RBS-04) — CR-075 wave L task L6:
#           runbook 8, registered as an Action with its ports declared and the
#           runbook DISABLED for live; guards evaluated BEFORE step 1.
# Rules:    BR-RBS-012 (guards are ABSOLUTE, before any step) · BR-RBS-014 (a
#           SAMPLE record is never acted on) · BR-RBS-004 (a plan first) ·
#           BR-RBS-003 (dry and live are one path) · BR-PAY-017 (the ladder is
#           payments' law, read and never copied) · OQ-RBS-1732 CLOSED (no
#           threshold) · BR-TEN-043 (event time is an argument)
# Tests:    this file
# Impacts:  apps/runbooks/definitions/dunning.py
# ───────────────────────────────────────────────────────
"""Runbook 8 — the guards, the rungs, and the thirty-day figure.

⚠ **THE LADDER'S OWN ARITHMETIC IS NOT RE-TESTED HERE, ON PURPOSE.** `BR-PAY-017`
is decided by `apps/payments/ladder.py::decide`, which is pure and has its own
suite (`tests/test_us_pay_014_ladder.py`). A copy of those cases in this file
would be a second statement of a signed rule that could drift from it. What is
tested here is what this runbook adds: the guards, the discriminator, the fee
hold, and that nothing can send.

The board is supplied by a stub in the cases below rather than by a full
billing fixture — deliberately, and it is a limitation worth naming: it proves
this runbook's own logic over a KNOWN board and proves nothing about the read
underneath it. That read is `payments_seam.collections_ladder_board`, one line
delegating to a tested function, and the end-to-end version is `L9`'s fixture
and `L12`'s browser walkthrough.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks import interfaces, models
from apps.runbooks.definitions import dunning
from apps.runbooks.engine import acts, executor
from apps.runbooks.seams import customers_seam, metering_seam, payments_seam

AS_OF = dt.date(2026, 9, 7)

#: Four accounts, one per rung, plus one the ladder refuses.
BOARD_ROWS = [
    {
        "account_id": "aaaaaaaa-0000-4000-8000-000000000001",
        "account_no": "ACC-1001",
        "balance": "184.200000",
        "currency": "USD",
        "runs": True,
        "next_rung": "first_10_day",
        "skip_reason": None,
        "days_late": 14,
        "detail_code": "decided",
        "current_tier": "friendly",
    },
    {
        "account_id": "aaaaaaaa-0000-4000-8000-000000000002",
        "account_no": "ACC-1002",
        "balance": "42.100000",
        "currency": "USD",
        "runs": True,
        "next_rung": "friendly",
        "skip_reason": None,
        "days_late": 4,
        "detail_code": "decided",
        "current_tier": None,
    },
    {
        "account_id": "aaaaaaaa-0000-4000-8000-000000000003",
        "account_no": "ACC-1003",
        "balance": "2.400000",
        "currency": "USD",
        "runs": False,
        "next_rung": None,
        "skip_reason": "below_ladder_floor",
        "days_late": 40,
        "detail_code": "decided",
        "current_tier": None,
    },
    {
        "account_id": "aaaaaaaa-0000-4000-8000-000000000004",
        "account_no": "ACC-1004",
        "balance": "900.000000",
        "currency": "USD",
        "runs": True,
        "next_rung": "final_48_hour",
        "skip_reason": None,
        "days_late": 46,
        "detail_code": "decided",
        "current_tier": "second_5_day",
    },
]

BOARD_ROWS.append(
    {
        # ⚠ `DEF-RBS-4348` — the post keeps coming back from this address. It is
        # otherwise a perfectly ordinary account at a rung that falls due today,
        # so ONLY the flag can stop the letter. Wave `M` had 23 of these and
        # planned a letter for every one.
        "account_id": "aaaaaaaa-0000-4000-8000-000000000005",
        "account_no": "ACC-1005",
        "balance": "310.000000",
        "currency": "USD",
        "runs": True,
        "next_rung": "second_5_day",
        "skip_reason": None,
        "days_late": 24,
        "detail_code": "decided",
        "current_tier": "first_10_day",
    }
)

SAMPLE_ID = "aaaaaaaa-0000-4000-8000-000000000004"
BAD_ADDRESS_ID = "aaaaaaaa-0000-4000-8000-000000000005"


@pytest.fixture()
def board(monkeypatch):
    """A KNOWN ladder board, so this file tests the runbook and not payments."""

    def _board(*, as_of, account_ids=None, medical_hold_account_ids=()):
        assert as_of == AS_OF, "as_of must reach payments unchanged (BR-TEN-043)"
        return {
            "as_of": as_of.isoformat(),
            "rows": [dict(row) for row in BOARD_ROWS],
            "rungs": ["friendly", "first_10_day", "second_5_day", "final_48_hour"],
            "next_step_available": True,
            "problems": [],
        }

    monkeypatch.setattr(payments_seam, "collections_ladder_board", _board)
    monkeypatch.setattr(customers_seam, "sample_account_ids", lambda: frozenset({SAMPLE_ID}))
    monkeypatch.setattr(customers_seam, "medical_hold", lambda account_id, *, as_of: False)
    monkeypatch.setattr(
        customers_seam,
        "account_anchors",
        lambda: [
            {
                "id": row["account_id"],
                "account_no": row["account_no"],
                "kind": "regular",
                "unit_id": "uuuuuuuu-0000-4000-8000-00000000000" + row["account_id"][-1],
                "premises_id": None,
                "bad_address": row["account_id"] == BAD_ADDRESS_ID,
            }
            for row in BOARD_ROWS
        ],
    )
    monkeypatch.setattr(metering_seam, "unit_has_dispute_hold", lambda unit_id: False)
    # `DEF-PAY-6380` — what else is ON FILE for a flagged account. Nothing, by
    # default, so the bad-address account stays undeliverable; the case that
    # gives it an email overrides this.
    monkeypatch.setattr(
        customers_seam,
        "contact_channels_for",
        lambda ids: {
            str(one): {"email": None, "text": None, "post": None, "channels": []} for one in ids
        },
    )
    return BOARD_ROWS


def _ctx(**params):
    base = {"as_of": AS_OF, "past_due_more_than": Decimal("5.0000")}
    base.update(params)
    return executor.build_context(dunning.RUNBOOK, mode="dry", params=base)


# ── the declaration ───────────────────────────────────────────────────────


def test_runbook_8_is_registered_as_an_action_with_exactly_two_ports():
    """`RB-108` — Kind: Action · Category: Collections · `step_ladder` · `apply_fee`.

    ⚠ **`step_ladder`, NOT `queue_notice`, FROM 2026-09-07** (`DEF-RBS-4347`).
    `RB-108`'s port column and `12-the-contract.md` §8 row 8 both said
    `queue_notice`, and both are amended: queueing the letter is ONE of the
    three writes a collections step is, and the other two — `notice_history`
    and the account's tier — are payments' own. With only `queue_notice` the
    ladder never climbed: 512 state rows before a month of runs and 512 after.
    """
    from apps.runbooks.registry import registry

    registry.load()
    assert dunning.RUNBOOK.kind == models.KIND_ACTION
    assert dunning.RUNBOOK.category == "collections"
    assert dunning.RUNBOOK.subject_type == "account"
    assert dunning.RUNBOOK.unit_of_work == "past due"
    assert set(dunning.RUNBOOK.ports) == {"step_ladder", "apply_fee"}
    assert dunning.RUNBOOK.writes_nothing() is False
    assert registry.get(dunning.RUNBOOK_KEY) is dunning.RUNBOOK


def test_the_registration_is_one_explicit_line_and_not_a_discovery_loop():
    """`G115` rule 3 refuses a computed import; the module is named in the tuple."""
    from apps.runbooks import definitions

    assert dunning in definitions.DEFINITION_MODULES


def test_the_runbook_is_DISABLED_FOR_LIVE_and_holds_writer_less_ports(board):
    """`L6` — *the runbook DISABLED for live*, asserted rather than described.

    Both of its ports ARE bound in the registry, so this cannot pass by accident.
    """
    assert interfaces.PORTS["queue_notice"].is_bound
    assert interfaces.PORTS["apply_fee"].is_bound
    assert acts.live_enabled(dunning.RUNBOOK_KEY) is False
    live = executor.build_context(dunning.RUNBOOK, mode="live", params={"as_of": AS_OF})
    assert [p.is_bound for p in live.ports.values()] == [False, False]


def test_there_is_no_threshold_parameter(board):
    """`OQ-RBS-1732` CLOSED — every money-bearing action carries the second
    approval and there is NO amount above which it is skipped. A threshold can
    only ever widen what an automation may do unattended."""
    names = {p.name for p in dunning.RUNBOOK.parameters}
    assert not any("threshold" in name for name in names)


def test_as_of_is_a_parameter_and_a_missing_one_is_refused(board):
    """`BR-TEN-043`, gate `G6` — a ladder re-run for last Tuesday takes last
    Tuesday's decision, which a wall clock makes impossible to express."""
    ctx = executor.build_context(dunning.RUNBOOK, mode="dry", params={})
    with pytest.raises(ValueError):
        dunning.resolve(ctx)


# ── the guards: ABSOLUTE, and before step 1 ───────────────────────────────


def test_br_rbs_014_a_sample_account_is_guarded_and_no_step_ever_sees_it(board):
    """**A demo account must never receive a real disconnection notice.**

    Asserted through `apply_guards`, which is what the executor calls BEFORE any
    step — so this is *the capability is absent*, not *the step decided not to*.
    """
    ctx = _ctx()
    subjects = dunning.resolve(ctx)
    walked, guarded = executor.apply_guards(dunning.RUNBOOK, ctx, subjects)
    assert [s.subject_id for s in guarded] == [SAMPLE_ID]
    assert SAMPLE_ID not in {s.subject_id for s in walked}


def test_a_medical_hold_guards_the_account_before_any_step(board, monkeypatch):
    """A15 via `BR-CUS-039`. The guard is the OUTER of two layers — payments
    also refuses it, but only when it is told."""
    held = BOARD_ROWS[0]["account_id"]
    monkeypatch.setattr(
        customers_seam, "medical_hold", lambda account_id, *, as_of: str(account_id) == held
    )
    ctx = _ctx()
    _, guarded = executor.apply_guards(dunning.RUNBOOK, ctx, dunning.resolve(ctx))
    assert held in {s.subject_id for s in guarded}


def test_an_open_dispute_guards_the_account(board, monkeypatch):
    """`BR-MET-133` clause 4 — a disputed account is not chased."""
    disputed_unit = "uuuuuuuu-0000-4000-8000-000000000002"
    monkeypatch.setattr(
        metering_seam, "unit_has_dispute_hold", lambda unit_id: unit_id == disputed_unit
    )
    ctx = _ctx()
    _, guarded = executor.apply_guards(dunning.RUNBOOK, ctx, dunning.resolve(ctx))
    assert BOARD_ROWS[1]["account_id"] in {s.subject_id for s in guarded}


def test_a_guard_wins_over_a_rung_that_would_otherwise_have_fired(board):
    """`BR-RBS-012` — a guarded record is skipped **whatever the checks
    conclude**. ACC-1004 is due the final certified letter and is a sample."""
    assert BOARD_ROWS[3]["runs"] is True
    assert BOARD_ROWS[3]["next_rung"] == "final_48_hour"
    ctx = _ctx()
    walked, guarded = executor.apply_guards(dunning.RUNBOOK, ctx, dunning.resolve(ctx))
    assert SAMPLE_ID in {s.subject_id for s in guarded}
    assert SAMPLE_ID not in {s.subject_id for s in walked}


# ── the scope ─────────────────────────────────────────────────────────────


def test_the_threshold_filters_the_scope_and_the_ladder_floor_does_not(board):
    """Two different numbers, and conflating them loses the trail.

    `past_due_more_than` is this runbook's SCOPE filter. The $25.00 ladder floor
    is payments' per-utility setting and stops the LADDER — so ACC-1003 at
    **$2.40** is in the plan **with its reason**, rather than vanishing from it.
    `J4` step 2: every send AND skip is recorded, because a silent exclusion is
    the one thing a collections trail may not contain.
    """
    ctx = _ctx(past_due_more_than=Decimal("5.0000"))
    ids = {s.subject_id for s in dunning.resolve(ctx)}
    # $2.40 is under the SCOPE threshold of $5.00, so it is not in this run.
    assert BOARD_ROWS[2]["account_id"] not in ids
    # ...but at a $1.00 threshold it IS, and it is reported as a skip rather
    # than dropped — which is what the next case asserts.
    wide = _ctx(past_due_more_than=Decimal("1.0000"))
    assert BOARD_ROWS[2]["account_id"] in {s.subject_id for s in dunning.resolve(wide)}


def test_the_subject_label_is_the_account_NUMBER_and_never_the_id(board):
    """B14 rule 31 — no database id is ever the visible value of a field."""
    ctx = _ctx()
    labels = {s.label for s in dunning.resolve(ctx)}
    assert labels == {"ACC-1001", "ACC-1002", "ACC-1004", "ACC-1005"}


# ── the rung is the discriminator: the thirty-day answer ──────────────────


def test_the_rung_is_the_discriminator_so_one_debt_gets_FOUR_letters_not_thirty(board):
    """**THE WORKED FIGURE, and the boundary `engine/duplicates.py` named.**

    A customer past due for thirty days under a daily ladder: the run-level check
    stops the 09:00 retry and the 24-hour bound stops a second run the same day,
    and **neither stops thirty letters on thirty days.** The rung does — one key
    per rung, so the ladder writes at most one letter per rung over one debt:

        day  4 reminder · day 14 10-day · day 24 5-day · day 26 certified
        = **4 letters over 45 days, not 30 over 30.**

    Asserted on the keys themselves, because that is the mechanism.
    """
    keys = {
        acts.idempotency_key(
            runbook_key=dunning.RUNBOOK_KEY,
            action_kind="queue_notice",
            subject=type("S", (), {"subject_type": "account", "subject_id": "acct-4021"})(),
            discriminator=rung,
        )
        for rung in ("friendly", "first_10_day", "second_5_day", "final_48_hour")
    }
    assert len(keys) == 4, "one key per rung — four letters over the life of one debt"
    # ...and the SAME rung on the SAME account is ONE key however many days the
    # ladder runs, which is what turns thirty days into one letter.
    repeated = {
        acts.idempotency_key(
            runbook_key=dunning.RUNBOOK_KEY,
            action_kind="queue_notice",
            subject=type("S", (), {"subject_type": "account", "subject_id": "acct-4021"})(),
            discriminator="first_10_day",
        )
        for _ in range(30)
    }
    assert len(repeated) == 1


# ── the fee hold ──────────────────────────────────────────────────────────


def test_apply_fee_charges_NOTHING_unless_a_utility_named_the_charge_code(board):
    """`RB-108`'s own tile: **Fees charged: $0.00**, and this is why.

    Whether a late fee is owed is billing's (`BR-BIL-001`/`008`), and
    `apps/payments/ladder.py` says of the same step *"This engine CITES the step
    and applies nothing"*. A runbook may carry out a charge code a utility has
    already named; it may not decide a customer owes a fee.
    """
    ctx = _ctx()
    result = dunning.step_late_fee(ctx, dunning.resolve(ctx))
    assert result["applied"] == 0
    assert result["charge_code"] is None
    assert "has not named a late-fee charge code" in result["reason"]


def test_the_late_fee_charge_code_parameter_has_no_default():
    """The unsafe option is the one you type (hard-won law 3)."""
    fee = next(p for p in dunning.RUNBOOK.parameters if p.name == "late_fee_charge_code")
    assert fee.default is None
    assert fee.required is False


# ── the steps ─────────────────────────────────────────────────────────────


def test_the_two_read_steps_are_SET_and_the_queue_step_is_PER_RECORD():
    """`TC-RBS-17`'s mistake, in the other direction: the ladder board is ONE
    read for the pinned set, and registering it per-record would make it 1,004."""
    modes = {step.key: step.mode for step in dunning.RUNBOOK.steps}
    assert modes[dunning.STEP_TIER] == "set"
    assert modes[dunning.STEP_DELIVERABLE] == "set"
    assert modes[dunning.STEP_QUEUE] == "per_record"
    writes = {step.key for step in dunning.RUNBOOK.steps if step.writes}
    assert writes == {dunning.STEP_QUEUE, dunning.STEP_FEE}


def test_the_tier_step_reads_the_board_ONCE_for_the_whole_pinned_set(board, monkeypatch):
    """`BR-RBS-009` — resolved ONCE and pinned. Read twice, an account could
    climb a rung between the scope and the decision."""
    calls = []
    original = payments_seam.collections_ladder_board

    def counting(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(payments_seam, "collections_ladder_board", counting)
    ctx = _ctx()
    subjects = dunning.resolve(ctx)
    dunning.step_tier_due(ctx, subjects)
    assert len(calls) == 1, "the board is memoised for the run, not read per step"


def test_an_unconfigured_utility_reports_not_configured_and_not_a_clean_run(board, monkeypatch):
    """**A false pass this runbook could have had** (hard-won law 7, habit 2).

    `ladder_board` returns `next_step_available: false` when the utility has set
    no thresholds. A build that read `next_rung: None` as *"no notice due"* would
    report a CLEAN run over a ladder nobody has configured.
    """
    def unconfigured(*, as_of, account_ids=None, medical_hold_account_ids=()):
        rows = [dict(row, runs=None, next_rung=None, detail_code="thresholds_unset") for row in BOARD_ROWS]
        return {
            "as_of": as_of.isoformat(),
            "rows": rows,
            "rungs": [],
            "next_step_available": False,
            "problems": [],
        }

    monkeypatch.setattr(payments_seam, "collections_ladder_board", unconfigured)
    ctx = _ctx()
    subjects = dunning.resolve(ctx)
    ctx.set_results[dunning.STEP_TIER] = dunning.step_tier_due(ctx, subjects)
    ctx.set_results[dunning.STEP_DELIVERABLE] = dunning.step_deliverable(ctx, subjects)
    outcome = dunning.step_queue_notice(ctx, subjects[0])
    assert outcome["outcome"] == dunning.OUTCOME_NOT_CONFIGURED
    assert outcome["fix_route"] == "Settings → Collections"


def test_a_skipped_account_carries_the_rule_in_a_clerks_words_with_no_rule_id(board):
    """`BR-RBS-010` and B14 rule 32 — the reason is readable and carries no id."""
    ctx = _ctx(past_due_more_than=Decimal("1.0000"))
    subjects = dunning.resolve(ctx)
    ctx.set_results[dunning.STEP_TIER] = dunning.step_tier_due(ctx, subjects)
    ctx.set_results[dunning.STEP_DELIVERABLE] = dunning.step_deliverable(ctx, subjects)
    floor = next(s for s in subjects if s.subject_id == BOARD_ROWS[2]["account_id"])
    outcome = dunning.step_queue_notice(ctx, floor)
    assert outcome["outcome"] == dunning.OUTCOME_SKIPPED
    assert outcome["reason"] == "the balance is under this utility's collection floor"
    assert "BR-" not in outcome["reason"] and "OQ-" not in outcome["reason"]


def test_the_deliverable_step_REPORTS_that_it_cannot_see_a_bounce_history(board):
    """`DEF-RBS-4331` — `suppress_channel` has no writer and no column, so this
    run cannot know an address has ever failed. **Stated rather than inferred
    away**: a build that treated *we have never heard otherwise* as *this
    address works* would report 812 deliverable and post into the void."""
    ctx = _ctx()
    result = dunning.step_deliverable(ctx, dunning.resolve(ctx))
    assert result["bounce_history_available"] is False
    assert "cannot see whether one CHANNEL has stopped working" in result["stated_absence"]


def test_a_bad_address_is_UNDELIVERABLE_and_the_letter_is_not_planned(board):
    """`DEF-RBS-4348` — *"Check the address works"* must be able to skip somebody.

    ⚠ **IT COULD NOT.** The step asked `bool(anchors.get(id))` — whether the
    ACCOUNT exists — and every subject reaching it came from `resolve()`, which
    walks accounts, so the answer was `True` for every possible input and the
    `undeliverable` outcome was **unreachable**. Wave `M` planned a letter for
    each of **23 accounts flagged `bad_address`**, and the run reported them as
    deliverable. A check that cannot fail is worse than no check (law 7).

    Shown RED first on the build that read `bool(anchor)`: `reachable` was True
    for `ACC-1005`, `undeliverable` was empty, and the step returned `queued`.
    """
    ctx = _ctx()
    subjects = dunning.resolve(ctx)
    ctx.set_results[dunning.STEP_TIER] = dunning.step_tier_due(ctx, subjects)
    ctx.set_results[dunning.STEP_DELIVERABLE] = dunning.step_deliverable(ctx, subjects)

    channel = ctx.set_results[dunning.STEP_DELIVERABLE]
    assert channel["reachable"][BAD_ADDRESS_ID] is False
    assert channel["undeliverable"] == [BAD_ADDRESS_ID]
    # …and every other account on the board is still reachable, so the flag is
    # doing the work rather than the step having simply stopped answering.
    assert sorted(k for k, ok in channel["reachable"].items() if ok) == sorted(
        str(s.subject_id) for s in subjects if str(s.subject_id) != BAD_ADDRESS_ID
    )

    subject = next(s for s in subjects if str(s.subject_id) == BAD_ADDRESS_ID)
    outcome = dunning.step_queue_notice(ctx, subject)
    assert outcome["outcome"] == dunning.OUTCOME_UNDELIVERABLE
    assert outcome["fix_route"] == "Add a contact"


def test_a_bad_address_closes_the_POST_and_an_email_on_file_is_still_planned(
    board, monkeypatch
):
    """`DEF-PAY-6380` — a returned LETTER is not a dead customer.

    `accounts.bad_address` means the POSTAL address failed. Until 2026-09-24 the
    step read it as *no address at all* and dropped the email too, so a customer
    whose letter came back and whose inbox works was told nothing. Now the flag
    removes the post channel only: `ACC-1005` has an email on file, so the
    5-day notice is planned on EMAIL, and on email alone.

    RED on the unchanged tip: `reachable` was False for `ACC-1005` and the step
    returned `undeliverable` — quoted in the defect's close.
    """
    monkeypatch.setattr(
        customers_seam,
        "contact_channels_for",
        lambda ids: {
            str(one): {
                "email": "sarah.miller@example.com" if str(one) == BAD_ADDRESS_ID else None,
                "text": None,
                "post": "1408 Elm St, Austin, TX, 78704",
                "channels": ["email", "post"],
            }
            for one in ids
        },
    )
    planned = []

    def perform(ctx, request):
        planned.append(request)
        return type(
            "Performed",
            (),
            {"outcome": acts.OUTCOME_DONE, "record_id": None, "idempotency_key": "k"},
        )()

    monkeypatch.setattr(dunning.acts, "perform", perform)
    # The run-level duplicate check reads the run row; this is a dry context
    # with no row, so it is answered as *not a duplicate* rather than asked.
    monkeypatch.setattr(
        dunning, "_run_level", lambda ctx: type("V", (), {"is_duplicate": False})()
    )
    ctx = _ctx()
    subjects = dunning.resolve(ctx)
    ctx.set_results[dunning.STEP_TIER] = dunning.step_tier_due(ctx, subjects)
    ctx.set_results[dunning.STEP_DELIVERABLE] = dunning.step_deliverable(ctx, subjects)

    channel = ctx.set_results[dunning.STEP_DELIVERABLE]
    assert channel["reachable"][BAD_ADDRESS_ID] is True
    assert channel["undeliverable"] == []
    assert channel["channels"][BAD_ADDRESS_ID] == ["email"], "the post is closed, the email is not"
    # An unflagged account keeps the run's whole ask.
    assert channel["channels"]["aaaaaaaa-0000-4000-8000-000000000001"] == ["email", "pdf_print"]

    subject = next(s for s in subjects if str(s.subject_id) == BAD_ADDRESS_ID)
    outcome = dunning.step_queue_notice(ctx, subject)
    assert outcome["outcome"] != dunning.OUTCOME_UNDELIVERABLE
    assert [request.payload["channels"] for request in planned] == [("email",)]


def test_a_bad_address_on_a_post_only_run_is_still_undeliverable(board):
    """The run asked for the post and nothing else: with the post closed there
    is nothing left, whatever else is on file."""
    ctx = _ctx(channels="pdf_print")
    subjects = dunning.resolve(ctx)
    channel = dunning.step_deliverable(ctx, subjects)
    assert channel["reachable"][BAD_ADDRESS_ID] is False
    assert channel["channels"][BAD_ADDRESS_ID] == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-012 (EP-RBS-04; CR-075 wave L task L6)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_010_dunning.py
# exceptions: the ladder board is a stub here — payments' own arithmetic is tested in tests/test_us_pay_014_ladder.py and the end-to-end version is L9's fixture
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
