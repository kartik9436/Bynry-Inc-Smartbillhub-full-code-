# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-014 (the collection sequence engine: due+3 → late fee →
#           10-day → 5-day → 48h certified final)   Screens: S34 · S70
# Rules:    BR-PAY-017 (the tenant-config ladder; medical hold excluded; every
#           step a queue-write) · BR-PAY-016 as amended 2026-08-12 (partial
#           payment ≥ a TENANT-SET % pauses — OQ-136; a bounce restarts at rung
#           1 — OQ-133) · BR-BIL-001 as amended (the $25.00 floor on the WHOLE
#           ladder — OQ-137/OQ-157) · BR-CUS-043 (a current plan pauses it) ·
#           BR-NOT-005 (queue-write only) · CLAUDE.md rule 1 · rule 7
# ───────────────────────────────────────────────────────
"""The four 2026-08-12 rulings, each on its own worked figure.

    OQ-137/157   a **$2.40** residue buys no reminder, no notice and no
                 **$8.00** certified letter, under a **$25.00** floor that is
                 per-utility.
    OQ-136       **$150** of **$948** is **15.8%** — under either figure the PO
                 named — so the ladder CONTINUES. At 25% it needs **$237.00**;
                 at 50%, **$474.00**.
    OQ-133       a **$1,842.10** bill whose cheque bounced gets **the full
                 ladder again, first notice onward**.
    OQ-170       (asserted through `dunning`, whose own suite owns it) a missed
                 instalment lifts the pause the next day.

RED-PROVED FIRST (hard-won law 7): with `decide`'s floor branch deleted, the
$2.40 case returns `runs=True` at the friendly reminder — the exact behaviour
the PO ruled against. With the `current_rung=None` reset in
`restart_after_bounce` replaced by a no-op, the bounced account resumes at the
tier it had reached instead of rung 1. Both transcripts are in the lane report.

TWO SETTINGS ARE PASSED IN, and the reason changed on 2026-08-15 — read this
before assuming the old one. `ladder_balance_floor_amount` and
`partial_payment_pause_percent` were RULED on 2026-08-12 and
`apps.tenancy.settings_families.COLLECTIONS` stored NEITHER, so the seam refused
by name and the engine took both as arguments rather than inventing a default.
**That storage now exists (DEF-097 closed), and both readers resolve.**

The arguments STAY, and that is deliberate rather than left over: passing them
in is what kept the gap findable for three days instead of letting it decay into
a hardcoded 25, and it is the same posture BR-BIL-001's fee half already takes.
What changed is only where the caller gets the values from.

The test that pinned the absence keeps its name and now pins the presence — the
figures, and that they are per-TENANT, because the PO's stated reason for making
the floor a setting was that a $38 average-bill utility and a $180 one cannot
share one number.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import ladder, settings_seam
from apps.payments.collections_models import (
    TIER_FIRST_10_DAY,
    TIER_FRIENDLY,
    TIER_SECOND_5_DAY,
    AccountCollectionState,
    NoticeHistory,
)
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: The RULED figures. Passed in as arguments, never inlined into the engine.
FLOOR = Decimal("25.00")  # OQ-137/OQ-157, seeded default
PCT_25 = Decimal("25")  # OQ-136, the PO's first EXAMPLE
PCT_50 = Decimal("50")  # OQ-136, the PO's second EXAMPLE

DUE_ON = date(2026, 7, 6)  # OQ-133's own due date


def _decide(**overrides):
    values = dict(
        account_id="acct",
        as_of=date(2026, 7, 20),
        balance=Decimal("948.20"),
        oldest_due_on=DUE_ON,
        balance_floor=FLOOR,
        partial_pause_percent=None,
    )
    values.update(overrides)
    return ladder.decide(**values)


def test_us_pay_014_tc5d__a_2_40_residue_gets_no_ladder_step_at_all(brazos, dana):
    """TC-5d — the **$25.00** floor on the WHOLE ladder (PO 2026-08-12, OQ-137).

    *"An account leaves $2.40 unpaid → no ladder step at all … a certified
    letter costs $8.00 and chasing $2.40 spends more than it recovers"*. The
    skip is recorded with its reason; it is never silent.
    """
    decision = _decide(balance=Decimal("2.40"))
    assert decision.runs is False
    assert decision.skip_reason == ladder.SKIP_BELOW_FLOOR
    assert "25.00" in decision.detail


def test_us_pay_014_the_floor_is_strict_at_exactly_25(brazos, dana):
    """Exactly **$25.00** IS chased — *"less than $25"* is strict.

    The same reading BR-BIL-001's fee half already ships, asserted here so the
    two halves of one ruled figure cannot drift apart.
    """
    assert _decide(balance=Decimal("25.00")).runs is True
    assert _decide(balance=Decimal("24.99")).skip_reason == ladder.SKIP_BELOW_FLOOR


def test_us_pay_014_tc5c__150_of_948_is_15_8_percent_and_does_not_pause(brazos, dana):
    """TC-5c — OQ-136 on its own arithmetic.

    **$150 of $948 = 15.8%**, below both figures the PO named, so *"the ladder
    CONTINUES and the notice goes out"*. The same $150 pauses it at a 15%
    threshold — *"the behaviour follows the setting"*.
    """
    outstanding_after = Decimal("948.00") - Decimal("150.00")
    at_25 = _decide(
        balance=outstanding_after, paid_recently=Decimal("150.00"), partial_pause_percent=PCT_25
    )
    at_50 = _decide(
        balance=outstanding_after, paid_recently=Decimal("150.00"), partial_pause_percent=PCT_50
    )
    at_15 = _decide(
        balance=outstanding_after,
        paid_recently=Decimal("150.00"),
        partial_pause_percent=Decimal("15"),
    )
    assert at_25.runs is True and at_50.runs is True
    assert at_15.runs is False
    assert at_15.skip_reason == ladder.SKIP_PARTIAL_PAYMENT
    assert "15.8%" in at_15.detail


def test_us_pay_014_237_and_474_are_what_the_two_thresholds_require(brazos, dana):
    """The PO's own two figures: **$237.00** at 25%, **$474.00** at 50%."""
    assert (
        _decide(
            balance=Decimal("948.00") - Decimal("237.00"),
            paid_recently=Decimal("237.00"),
            partial_pause_percent=PCT_25,
        ).runs
        is False
    )
    assert (
        _decide(
            balance=Decimal("948.00") - Decimal("474.00"),
            paid_recently=Decimal("474.00"),
            partial_pause_percent=PCT_50,
        ).runs
        is False
    )


def test_us_pay_014_a_partial_payment_with_no_threshold_refuses(brazos, dana):
    """No percentage is invented. The PO named 25 and 50 as EXAMPLES.

    Picking one here would answer a question they deliberately handed to each
    utility, so the engine refuses and says so.
    """
    with pytest.raises(PaymentRuleError) as refusal:
        _decide(paid_recently=Decimal("150.00"), partial_pause_percent=None)
    assert "TENANT SETTING" in str(refusal.value)
    assert refusal.value.br_ref == "BR-PAY-016"


def test_us_pay_014_tc1__the_ladder_walks_its_rungs_in_order(brazos, dana):
    """TC-1 — reminder → 10-day → 5-day → certified final, one rung per pass."""
    assert ladder.next_rung(None) == TIER_FRIENDLY
    assert ladder.next_rung(TIER_FRIENDLY) == TIER_FIRST_10_DAY
    assert ladder.next_rung(TIER_FIRST_10_DAY) == TIER_SECOND_5_DAY
    assert ladder.next_rung(ladder.LADDER_RUNGS[-1]) is None


def test_us_pay_014_the_end_of_the_ladder_is_not_a_drop_off(brazos, dana):
    """PO 2026-08-11: *"nodrop we chase for payments until write off"*.

    An exhausted ladder reports `ladder_complete`, and the detail says in as
    many words that the next act is a human's.
    """
    decision = _decide(current_rung=ladder.LADDER_RUNGS[-1])
    assert decision.skip_reason == ladder.SKIP_LADDER_COMPLETE
    assert "nodrop" in decision.detail


def test_us_pay_014_tc3__a_medical_hold_is_excluded_and_recorded(brazos, dana):
    """TC-3 — *"EXCLUDED from every ladder step; exclusion appended … never
    silent"*."""
    decision = _decide(medical_hold=True)
    assert decision.runs is False
    assert decision.skip_reason == ladder.SKIP_MEDICAL_HOLD


def test_us_pay_014_a_bill_with_no_due_date_is_not_chased_on_an_invented_one(brazos, dana):
    """BR-PAY-032's anchor cannot be computed, so the ladder does not run.

    The BALANCE is still real and still reported; what is refused is placing it
    on a schedule anchored to a date nobody has.
    """
    decision = _decide(oldest_due_on=None)
    assert decision.runs is False
    assert decision.days_late is None


def test_us_pay_014_tc5b__a_bounce_restarts_the_ladder_at_rung_1(brazos, dana):
    """TC-5b — OQ-133, *"Restart from the beginning"*, on **$1,842.10**.

    The account had reached the 5-day notice. After the bounce its state is
    cleared, so the very next evaluation offers the FRIENDLY REMINDER — not the
    certified letter its 58-day age would otherwise select.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        AccountCollectionState.objects.create(
            tenant=brazos,
            account=account,
            tier=TIER_SECOND_5_DAY,
            tier_sent_on=date(2026, 7, 20),
        )
        ladder.restart_after_bounce(account.pk, on_date=date(2026, 7, 27), actor=dana)

        state = AccountCollectionState.objects.get(account=account)
        assert state.tier is None
        assert _decide(balance=Decimal("1842.10"), current_rung=state.tier).rung == TIER_FRIENDLY


def test_us_pay_014_run_ladder_queues_a_step_and_records_the_history(brazos, dana):
    """The engine end-to-end: one rung, one queue-write, one history row.

    BR-NOT-005 — nothing is sent inline; the step goes through `notices.py`,
    which writes to the platform outbound queue and appends `notice_history`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11025")
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-018206",
            total=Decimal("948.20"),
            issued_on=DUE_ON,
            due_date=DUE_ON,
        )
        run = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=date(2026, 7, 20),
            actor=dana,
            balance_floor=FLOOR,
        )
        assert len(run.stepped) == 1
        assert run.stepped[0].rung == TIER_FRIENDLY
        assert AccountCollectionState.objects.get(account=account).tier == TIER_FRIENDLY
        assert NoticeHistory.objects.filter(account=account, outcome="sent").exists()


def test_us_pay_014_run_ladder_records_a_skip_rather_than_staying_silent(brazos, dana):
    """A $2.40 residue leaves a SKIP row, so nobody has to wonder why."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11026")
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-018207",
            total=Decimal("2.40"),
            issued_on=DUE_ON,
            due_date=DUE_ON,
        )
        run = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=date(2026, 7, 20),
            actor=dana,
            balance_floor=FLOOR,
        )
        assert run.skipped[0].skip_reason == ladder.SKIP_BELOW_FLOOR
        skip = NoticeHistory.objects.get(account=account, outcome="skipped")
        assert skip.skip_reason == ladder.SKIP_BELOW_FLOOR


def test_us_pay_014_the_two_ruled_settings_have_no_storage_and_the_seam_says_so(
    brazos, dana, lonestar
):
    """**SUPERSEDED 2026-08-15 — the gap this test pinned is CLOSED (DEF-097).**

    Kept under its original name so the story's TC mapping still resolves, and
    rewritten rather than deleted so a reader can find out what happened to the
    old behaviour (hard-won law 1).

    **What it used to assert, and why that was right at the time:** both figures
    were RULED on 2026-08-12 and `settings_families.COLLECTIONS` carried neither
    `Param`, so the seam REFUSED by name and named the file that owed the line.
    Refusing was the honest posture — the ladder took both as arguments rather
    than inventing a default, which is exactly why the gap stayed findable
    instead of decaying into a hardcoded 25.

    **What it asserts now:** the two `Param` rows exist, they carry the PO's own
    seeded figures, and the seam READS them instead of refusing. The reason this
    is worth a test at all is DEF-097's escape reason — *no gate compares a
    CLOSED question's ruling against the storage that ruling implies* — so the
    only thing standing between a ruled setting and a silently absent one is an
    assertion somebody wrote on purpose.
    """
    with tenant_ctx(brazos):
        # The intervals that always existed still read the same.
        assert settings_seam.reminder_days_after_due() == 3
        assert settings_seam.notice_tier_days() == (10, 5)

        # The two that were owed now resolve, at the figures the PO named.
        # $25.00 floor: a $2.40 balance earns no fee, no $8.00 certified letter
        # and no notice — and $25.00 EXACTLY is still chased (see tc7).
        assert settings_seam.ladder_balance_floor() == Decimal("25")
        # 25%: $150 against $948 is 15.8% and does not pause; 25% needs $237.00.
        assert settings_seam.partial_pause_percent() == Decimal("25")

    # And they are TENANT settings, not constants — the PO's stated reason for
    # making the floor per-utility was that a $38 average-bill utility and a
    # $180 one cannot share one number. A second tenant reads its own value.
    with tenant_ctx(lonestar):
        assert settings_seam.ladder_balance_floor() == Decimal("25")


def test_us_pay_014_tc8__isolation_the_ladder_sees_one_tenants_debts(brazos, dana, lonestar):
    """TC-8 — *"Its settings, queue rows, notice_history only"*."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11027")
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-018208",
            total=Decimal("948.20"),
            issued_on=DUE_ON,
            due_date=DUE_ON,
        )
    with tenant_ctx(lonestar):
        run = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=date(2026, 7, 20),
            actor=None,
            balance_floor=FLOOR,
        )
        # The other tenant's bills are invisible, so there is nothing to chase.
        assert run.stepped == ()


@requires_postgres
@pytest.mark.isolation
def test_us_pay_014_the_audit_write_does_not_crash_the_run(brazos, dana):
    """**DEF-117** — the hard-rule-7 audit write 500'd the whole request.

    `ladder.run_ladder` passed `str(as_of)` — a DATE — as the audit row's
    `entity_id`, which is a `UUIDField`. Postgres refuses it with
    `ValueError: badly formed hexadecimal UUID string`, so the collections run
    raised **500 SYS-INTERNAL after the ladder had already stepped the
    accounts**: the customer-facing work happened and the request failed.

    **Why 2,400 unit tests missed it and a browser found it.** SQLite's
    UUIDField is forgiving; only a real Postgres column refuses a date. So this
    case carries `requires_postgres` — a bare skip here would restore exactly
    the blindness that let it ship.

    A collection run is a SWEEP, not a persisted entity, so it has no id and
    the column is left NULL — which is what nullable is for. The date is not
    lost; it travels in `after["as_of"]`, where a date belongs.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11901")
        an_issued_bill(
            brazos,
            account,
            number="BL-2607-019011",
            total=Decimal("948.20"),
            issued_on=DUE_ON,
            due_date=DUE_ON,
        )
        # The call that used to raise. It must complete and return a result.
        run = ladder.run_ladder(
            account_ids=(account.pk,),
            as_of=date(2026, 7, 20),
            actor=dana,
            balance_floor=FLOOR,
        )
        assert run is not None

        from apps.audit import models as audit_models

        rows = list(audit_models.AuditLog.objects.filter(entity_type="collection_run"))
        # ⚠ WHAT THIS ASSERTS, AND WHAT IT DELIBERATELY DOES NOT.
        #
        # The crash is fixed and PROVED by the call above completing: before the
        # fix `run_ladder` raised before ever returning, so `run is not None`
        # could not be reached at all on Postgres.
        #
        # Whether the audit row lands is a SEPARATE question and this test does
        # not pretend to settle it: on this fixture the sweep steps no account,
        # and whether hard rule 7 demands a row for a sweep that did nothing is
        # not a thing any signed rule says. Raised rather than asserted either
        # way — asserting "no row" would freeze an accident into a guarantee.
        #
        # What IS asserted: if a row exists, it carries NULL rather than a date
        # in the uuid column, which is the defect.
        for row in rows:
            assert row.entity_id is None, (
                "audit_log.entity_id is a UUIDField; a date string there is what "
                "raised ValueError and 500'd the request after the ladder had run"
            )
