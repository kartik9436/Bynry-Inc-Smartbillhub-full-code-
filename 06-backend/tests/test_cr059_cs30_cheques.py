# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-30 (task 56) — "Give a cheque a state of its own",
#           RULED 2026-09-01.
# Story:    US-PAY-001   Screens: S22 · S33 · S35 · S37 · S21
# Rules:    BR-PAY-880 (structured fields) · BR-PAY-881 (void before banking) ·
#           BR-PAY-883 (the post-dated hold) · BR-PAY-002 / CLAUDE.md hard rule
#           4 (append-only once out of `processing`) · BR-PAY-025 (the drawer
#           day × method batch) · rule 7 (audit)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CS-30 — a cheque, as a thing rather than as free text.

WHAT WAS TRUE BEFORE THIS LANE, IN CS-30's OWN WORDS
====================================================
*"There is no cheque in this system. A cheque is an ordinary payment whose
tender is `check` and whose number is typed into a free-text reference field."*
So two cheques could carry the same number, a typo was invisible, a cheque dated
three weeks out could be banked tomorrow, and a cheque taken in error and torn
up before the deposit had no state to move to — the only correction was a
reversal, *"which is a bank event, not a counter event."*

WHAT IS BUILT, AND THE ONE THING THAT IS NOT
============================================
    ✔ cheque_date · drawer_bank as structured fields, the number staying in
      `confirmation` where CS-34 can still correct it
    ✔ a duplicate check keyed on (drawer bank, number), exempting a reversed row
    ✔ a post-dated cheque held OUT of the batch cut and NAMED when its day comes
    ✔ a counter void — `processing → failed` plus its audit row, no bank event
    ✘ RE-PRESENTMENT. CS-30's second rule (PO 2026-09-01) is NOT built; it is on
      `problems[]` on every result and in the lane report.

⚠ THE VOID IS A STATUS MOVE AND HARD RULE 4 IS WHY
==================================================
The obvious build is a `voided_at` column. `payments/0002`'s trigger lets a
`processing` payment change `status`, `cleared_at` and `updated_at` and NOTHING
else — whole-row compared, so a column added later is frozen the day it is
created — and `payments/0014` opened three more for corrections, none of which
is a void. **Widening that allow list again is a new ruling and not this one.**
A cheque *"not yet banked"* is `processing`, so the status already carries the
fact and the reason lives on the audit row.

`test_cs30__an_unbanked_cheque_is_voided_at_the_counter` and
`test_cs30__the_void_reason_is_on_the_audit_row` are where that lands: the
status moves, nothing posts, no reversing row exists, and the reason is on the
audit row because there is nowhere else it may lawfully go.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
========================================================================
  * With the `bankable_from > day` branch removed from `cut_deposit_batches`,
    `test_cs30__a_post_dated_cheque_is_held_out_of_the_cut` fails — the
    post-dated cheque joins the batch and the recorded total is 100.00 too high.
  * With `refuse_a_duplicate_cheque`'s reversed-row exemption removed,
    `test_cs30__a_reversed_cheques_number_is_free_again` fails and CS-32's own
    move of cheque #8842 becomes impossible.
  * With `void_cheque`'s `status != processing` guard removed,
    `test_cs30__a_cleared_cheque_cannot_be_voided` fails with `DID NOT RAISE`
    and a cheque whose money is in the books vanishes with no reversing entry.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import cheques, models, reconciliation, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

DRAWER_DAY = date(2026, 8, 8)
POSTED_AT = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
CUT_AT = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)

#: PE-10's own cheque number, and CS-30's worked case.
CHEQUE_NO = "8842"
FIRST_NATIONAL = "First National"


def a_cheque(
    actor,
    account,
    *,
    number=CHEQUE_NO,
    bank=FIRST_NATIONAL,
    amount=Decimal("100.00"),
    cleared=True,
    cheque_date=DRAWER_DAY,
    bankable_from=None,
):
    """One cheque through the real write path, with its structured facts."""
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT if cleared else None,
        method_code="check",
        confirmation=number,
        cheque_date=cheque_date,
        drawer_bank=bank,
        bankable_from=bankable_from,
        idempotency_reference=uuid.uuid4(),
    )


def a_legacy_processing_cheque(actor, account, *, number=CHEQUE_NO, amount=Decimal("100.00")):
    """A cheque as it was recorded BEFORE `CR-186-BRC10` — `processing`, unposted.

    ⚠ PO 2026-10-21: *"first they will pot the payment"* — every new cheque is
    `posted`, applied and journalled at entry, so `record_payment` can no longer
    produce a processing cheque. The counter void (BR-PAY-881) still serves the
    rows written before the change (PO: existing rows are left as they are), so
    those tests build one by an INSERT, which is what such a row was.
    """
    tenant_id = account.tenant_id
    return models.Payment.objects.create(
        tenant_id=tenant_id,
        account=account,
        payment_no=f"PMT-LEGACY-{uuid.uuid4().hex[:6]}",
        type=models.PAYMENT_TYPE_PAYMENT,
        method=__import__("apps.tenancy.models", fromlist=["PaymentMethod"]).PaymentMethod.objects.get(
            tenant_id=tenant_id, code="check"
        ),
        amount=amount,
        currency="USD",
        status=models.PAYMENT_PROCESSING,
        purpose=models.PURPOSE_BILL,
        confirmation=number,
        cheque_date=DRAWER_DAY,
        drawer_bank=FIRST_NATIONAL,
        posted_at=POSTED_AT,
        origin="entry",
        origin_is_derived=False,
    )


# ══ BR-PAY-880 · THE STRUCTURED FACTS ══════════════════════════════════════


def test_cs30__the_three_facts_are_stored(brazos, dana):
    """A cheque carries its number, its date and its drawer bank.

    The NUMBER is `confirmation` and that is the considered half: it is one of
    the exactly three columns the PO opened to correction on 2026-09-02, so a
    typo stays fixable through `POST /payments/{id}/correct-reference`. A fourth
    column would have held a number nobody could ever correct.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        paid = a_cheque(dana, account)
        row = models.Payment.objects.get(pk=paid.payment_id)
        assert row.confirmation == CHEQUE_NO
        assert row.cheque_date == DRAWER_DAY
        assert row.drawer_bank == FIRST_NATIONAL
        assert cheques.is_a_structured_cheque(row) is True


def test_cs30__the_three_facts_travel_together(brazos, dana):
    """Half of them describes an instrument nobody can identify.

    The drawer bank is not optional: two banks legitimately issue the same
    cheque number, so without it a duplicate cannot be told from an ordinary
    second cheque.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            a_cheque(dana, account, bank="")
        assert "DRAWER BANK" in str(refusal.value)


def test_cs30__a_duplicate_cheque_is_refused_by_name(brazos, dana):
    """*"Two cheques can carry the same number; a typo is invisible."* Not now.

    The refusal names the payment that already holds it, so a clerk can go and
    look rather than guess.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = a_cheque(dana, account)
        with pytest.raises(PaymentRuleError) as refusal:
            a_cheque(dana, account, amount=Decimal("250.00"))
        assert CHEQUE_NO in str(refusal.value)
        assert FIRST_NATIONAL in str(refusal.value)
        assert first.payment_no in str(refusal.value)


def test_cs30__two_banks_may_issue_the_same_number(brazos, dana):
    """Identity is (drawer bank, number) and not the number alone.

    Two banks issue cheque #8842 every week and a utility that banks both is not
    making a mistake — which is why a `(tenant, confirmation)` index would have
    been wrong even before the reversed-row problem below.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_cheque(dana, account)
        second = a_cheque(dana, account, bank="Community Savings", amount=Decimal("250.00"))
        assert second.created is True


def test_cs30__a_reversed_cheques_number_is_free_again(brazos, dana):
    """⚠ **THE CLAUSE A PARTIAL UNIQUE INDEX COULD NEVER EXPRESS.**

    *"Has this row been reversed"* lives in ANOTHER row, so no index predicate
    can reach it — and this CR's own CS-32 move re-records cheque #8842 on the
    correct account while the original stays `cleared`. A database index would
    refuse a correction this product is being built to make.

    **RED PROOF:** with the exemption removed this fails and the move becomes
    impossible.
    """
    from apps.payments import reversal

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = a_cheque(dana, account)
        reversal.reverse_payment(
            dana,
            payment_id=first.payment_id,
            returned_on=datetime(2026, 8, 20, 9, 0, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
        )
        again = a_cheque(dana, account, amount=Decimal("100.00"))
        assert again.created is True, (
            "the instrument came back, so its number is free — and this is exactly the "
            "exemption CS-32's move needs"
        )


# ══ BR-PAY-883 · THE POST-DATED HOLD ═══════════════════════════════════════


def test_cs30__a_post_dated_cheque_is_held_out_of_the_cut(brazos, dana):
    """*"A cheque dated in the future is held out of the batch cut until its date."*

    And it is NAMED in the result rather than dropped — the same rule CS-35
    imposed on a credit, and for the same reason: a drawer that does not tie has
    to be explainable.

    **RED PROOF:** with the branch removed the recorded total is 250.00 instead
    of 150.00 and the utility banks an instrument the customer asked it to hold.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_cheque(dana, account, amount=Decimal("150.00"))
        held = a_cheque(
            dana,
            account,
            number="9001",
            amount=Decimal("100.00"),
            cheque_date=date(2026, 8, 29),
            bankable_from=date(2026, 8, 29),
        )

        result = reconciliation.cut_deposit_batches(actor=dana, day=DRAWER_DAY, occurred_at=CUT_AT)
        reasons = {row["reason"] for row in result.skipped}
        assert "held_until_bankable" in reasons
        skipped = [row for row in result.skipped if row["reason"] == "held_until_bankable"][0]
        assert skipped["payment_id"] == held.payment_id
        assert skipped["bankable_from"] == "2026-08-29"

        banked = models.Payment.objects.get(pk=held.payment_id)
        assert banked.deposit_batch_id is None, "it stayed in the drawer"
        # CR-186-BRC10: the bankable cheque joined the day's batch at posting.
        from tests.test_us_pay_020_023_bank_rec import the_days_batches

        totals = [batch.recorded_total for batch in the_days_batches(brazos, DRAWER_DAY)]
        assert Decimal("150.00") in totals, "and the batch carries only what could be banked"


def test_cs30__it_is_named_on_the_day_it_becomes_bankable(brazos, dana):
    """The other half of the rule — *"named on the day it becomes bankable."*

    Without this read the hold is a trap: the money sits in the drawer and
    nothing ever tells anybody it is ready.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        held = a_cheque(
            dana,
            account,
            number="9001",
            cheque_date=date(2026, 8, 29),
            bankable_from=date(2026, 8, 29),
        )
        assert list(cheques.bankable_on(DRAWER_DAY)) == [], "not on the 8th"
        assert [row.pk for row in cheques.held_after(DRAWER_DAY)] == [
            models.Payment.objects.get(pk=held.payment_id).pk
        ]

        ready = list(cheques.bankable_on(date(2026, 8, 29)))
        assert [str(row.pk) for row in ready] == [held.payment_id], "and named on the 29th"


def test_cs30__bankable_from_may_not_precede_the_cheques_own_date(brazos, dana):
    """It would say the utility may bank an instrument before the day it exists."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            a_cheque(
                dana,
                account,
                cheque_date=date(2026, 8, 29),
                bankable_from=date(2026, 8, 1),
            )
        assert "cannot be banked before the day it is written" in str(refusal.value)


def test_cs30__the_hold_is_read_from_bankable_from_and_not_derived(brazos, dana):
    """A cheque dated last week is bankable today — the hold is a STATED fact.

    A utility may also agree to hold a cheque past its own date. Deriving the
    hold from `cheque_date` would be an inference two places could make
    differently, so the cut reads `bankable_from` and nothing else.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        old = a_cheque(dana, account, cheque_date=date(2026, 7, 1), bankable_from=None)
        result = reconciliation.cut_deposit_batches(actor=dana, day=DRAWER_DAY, occurred_at=CUT_AT)
        assert not [row for row in result.skipped if row["reason"] == "held_until_bankable"]
        banked = models.Payment.objects.get(pk=old.payment_id)
        assert banked.deposit_batch_id is not None, "a July cheque banked in August is fine"


# ══ BR-PAY-881 · THE COUNTER VOID ══════════════════════════════════════════


def test_cs30__an_unbanked_cheque_is_voided_at_the_counter(brazos, dana):
    """*"A cheque not yet banked may be voided at the counter without a bank
    reversal."*

    No reversing row, no journal entry, no NSF count. The cheque never cleared,
    so nothing reached the books — which is exactly why the counter void is
    expressible at all.
    """
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        taken = a_legacy_processing_cheque(dana, account)
        before = ledger_models.JournalLine.objects.filter(tenant=brazos).count()

        voided = cheques.void_cheque(
            dana,
            payment_id=taken.pk,
            reason="the customer tore it up at the counter",
            on_date=DRAWER_DAY,
        )
        assert voided.status == models.PAYMENT_FAILED
        assert (
            ledger_models.JournalLine.objects.filter(tenant=brazos).count() == before
        ), "nothing posted — a processing payment never reached the books"
        assert (
            models.Payment.objects.filter(reverses_payment_id=taken.pk).count() == 0
        ), "and no reversing row: a void is a COUNTER event, not a bank one"


def test_cs30__a_cleared_cheque_cannot_be_voided(brazos, dana):
    """The money arrived and is in the books — that is a REVERSAL.

    **RED PROOF:** with the guard removed this fails with `DID NOT RAISE` and a
    cheque whose money is in the books vanishes with no reversing entry, leaving
    the trial balance carrying cash the product says nobody paid.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        # CR-186-BRC10: a cheque taken today is POSTED — applied and in the
        # books — so the void (which writes neither) is refused and names Cancel.
        posted = a_cheque(dana, account, cleared=True)
        with pytest.raises(PaymentRuleError) as refusal:
            cheques.void_cheque(
                dana, payment_id=posted.payment_id, reason="too late", on_date=DRAWER_DAY
            )
        assert "Cancel the payment instead" in str(refusal.value)


def test_cs30__a_banked_cheque_cannot_be_voided(brazos, dana):
    """Once it is in a cut batch, only the reversal path applies (CS-30's rule)."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        taken = a_legacy_processing_cheque(dana, account)
        models.Payment.objects.filter(pk=taken.pk).update(deposit_batch_id=uuid.uuid4())
        with pytest.raises(PaymentRuleError) as refusal:
            cheques.void_cheque(
                dana, payment_id=taken.pk, reason="already cut", on_date=DRAWER_DAY
            )
        assert "already in a deposit batch" in str(refusal.value)


def test_cs30__a_void_needs_a_reason(brazos, dana):
    """A payment that vanishes from the drawer with no explanation is the one
    thing a bookkeeper cannot reconcile."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        taken = a_legacy_processing_cheque(dana, account)
        with pytest.raises(PaymentRuleError) as refusal:
            cheques.void_cheque(dana, payment_id=taken.pk, reason="", on_date=DRAWER_DAY)
        assert "needs a reason" in str(refusal.value)


def test_cs30__only_a_cheque_can_be_counter_voided(brazos, dana):
    """The void exists for an instrument somebody can physically tear up."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cash = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("100.00"),
            posted_at=POSTED_AT,
            cleared_at=None,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
        )
        with pytest.raises(PaymentRuleError) as refusal:
            cheques.void_cheque(
                dana, payment_id=cash.payment_id, reason="not a cheque", on_date=DRAWER_DAY
            )
        assert "is not a cheque" in str(refusal.value)


def test_cs30__the_void_reason_is_on_the_audit_row(brazos, dana, audit_rows):
    """Hard rule 7, and it is the ONLY place the reason lives.

    ⚠ `audit_log` is pruned on a retention schedule and whether such a row is
    exempt is `OQ-1340`, OPEN — so nothing describes this as a permanent record.
    `problems[]` says so on every result.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        taken = a_legacy_processing_cheque(dana, account)
        result = cheques.void_cheque(
            dana,
            payment_id=taken.pk,
            reason="torn up at the counter",
            on_date=DRAWER_DAY,
        )
        # ⚠ **THROUGH THE CAPTURE SINK, NOT THROUGH `AuditLog.objects`.**
        # `audit_rows` is this suite's own BE-03 fixture and it is what every
        # other file asserts a trail with: the live table is partitioned by
        # month on `created_at` and its `entity_id` is a UUIDField this path
        # holds as a string, so a query against it can answer "no row" for a row
        # that is there — a check that cannot tell pass from fail.
        written = [row for row in audit_rows if row["action"] == cheques.AUDIT_VOIDED]
        assert len(written) == 1
        assert written[0]["after"]["reason"] == "torn up at the counter"
        assert written[0]["after"]["is_a_bank_event"] is False
        assert any(
            problem["code"] == "void_reason_lives_only_in_the_audit_trail"
            for problem in result.problems
        )


def test_cs30__re_presentment_is_reported_as_unbuilt(brazos, dana):
    """CS-30's second rule is NOT built, and the absence is on the wire.

    Hard-won law 1 — a comment claiming a guarantee is not the guarantee, and
    its mirror: an absence stated only in a docstring is an absence a screen
    lane discovers.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        taken = a_legacy_processing_cheque(dana, account)
        result = cheques.void_cheque(
            dana, payment_id=taken.pk, reason="x", on_date=DRAWER_DAY
        )
        assert any(problem["code"] == "re_presentment_not_built" for problem in result.problems)


def test_cs30__the_uncleared_list_is_what_a_bookkeeper_asks_for(brazos, dana):
    """*"neither is a list of cheques awaiting clearance."* Now one is."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        waiting = a_cheque(dana, account, cleared=False)
        also = a_cheque(dana, account, number="9002", cleared=True, amount=Decimal("50.00"))
        legacy = a_legacy_processing_cheque(dana, account, number="9003")
        rows = sorted(str(row.pk) for row in cheques.uncleared_cheques())
        # CR-186-BRC10: "awaiting clearance" is POSTED until the bank
        # reconciliation clears it (a passed clearing date is not stored), plus
        # a legacy processing cheque.
        assert rows == sorted([waiting.payment_id, also.payment_id, str(legacy.pk)])
