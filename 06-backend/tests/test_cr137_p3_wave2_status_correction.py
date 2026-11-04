# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.13 (cancel by status) · P3.14 (the amendable
#           three, at the SERVICE layer) · P3.15 (a correction leaves the
#           original byte-identical, and `corrects_payment_id`)
# Story:    US-PAY-004 §1 *"Cancel only while processing"*   Screens: 2·2 · 2·3c
# Rules:    CLAUDE.md hard rule 1 · hard rule 4 (and its three-column narrowing,
#           `OQ-1322`) · BR-PAY-002 · BR-PAY-021 · hard-won law 2 (built is not
#           wired) · hard-won law 7 (a check that does not check) · law 14
# ───────────────────────────────────────────────────────
"""Wave 2's three suite tasks — and what each one can HONESTLY claim here.

⚠ **WHICH DATABASE PROVES WHAT, SAID BEFORE ANYTHING ELSE (hard-won law 14).**
`config/settings/test.py` hardcodes in-memory **SQLite**, which has neither
`ck_payments_status` nor `trg_payment_immutable`. So nothing in this file is a
statement about the TRIGGER, whatever its name says. The trigger is proved on
real PostgreSQL 16 by `10-scripts/p3_cancel_state_and_trigger_readback.py`
(§3 permit · §4 freeze · §6 the three amendable columns and a refused fourth ·
**§8, added by this lane**, the SERVICE's own correction against the live
trigger on a cancelled row). Every case here proves a **PYTHON** guarantee —
the status vocabulary, the refusal words, the service's field list, what the
record path writes — and each says so in its own docstring.

WHAT WAS ALREADY COVERED, AND IS THEREFORE NOT RESTATED
═══════════════════════════════════════════════════════
`tests/test_cr137_p3_detail_cancel_receipt.py` (lane P3-BACK) already proves
`P3.13`'s two headline sentences: `test_a_processing_payment_cancels_and_the_
money_comes_off_by_a_new_row` (succeeds on `processing`) and
`test_a_cleared_payment_is_refused_and_told_to_reverse` (refused on `cleared`,
and the refusal names Reverse). **Duplicating them would add a second answer to
one question**, so this file adds only what they do not ask:

  * **the vocabulary is COMPLETE.** Two of six statuses were exercised. A cancel
    must have exactly one answer for each of the six, and the assertion is
    anchored on a **COUNT** — `paymentStatusParity.test.ts`'s precedent, minted
    in this same CR for the same reason: *a loop is green on a list that has
    silently shrunk.*
  * **the OTHER direction of the Reverse sentence.** *Refused on `cleared` names
    Reverse* is half a rule. A `failed` or `reversed` payment must **NOT** be
    sent to Reverse — that door refuses a non-cleared row too (`US-PAY-009`
    TC-5), so a clerk following the words would be bounced twice. Nothing
    asserted that until now.

⚠ WHAT WOULD MAKE EACH CASE HERE PASS WRONGLY (hard-won law 7, habit 2)
═══════════════════════════════════════════════════════════════════════
  * **A status quietly leaving `PAYMENT_STATUSES`.** A `for status in
    PAYMENT_STATUSES` loop is green over five, four, or none. Both status cases
    below therefore assert the COUNT first and compare the expectation table to
    the tuple as SETS, so a status added *or* removed is a red line naming it.
  * **`refusal_for` answering `None` everywhere.** A map-driven case that only
    checked "a refusal exists" would pass on a build that cancelled anything.
    The expectation table names the EXACT code per status, and `processing`'s
    expected answer is `None` — so a guard that refused everything fails too.
  * **The Reverse control passing on a build with no sentences at all.** *"No
    other refusal contains the word Reverse"* is vacuously true of empty
    strings, so the same case asserts the cleared one DOES contain it. Both
    directions in one case, deliberately.
  * **A correction case that proves immutability by not trying.** `P3.15` posts
    a real adjustment through the real record path and compares **every concrete
    column** of the original before and after, rather than the handful a reader
    would think of.
  * **A green that means a field does not exist.** `P3.15`'s second half is the
    dangerous one: `corrects_payment_id` is a column **nothing writes** (see
    `test_corrects_payment_id_is_not_wired_to_anything_yet`). A case asserting
    *"the correction points at the original"* by reading that column would have
    failed honestly; a case asserting *"nothing else moved"* passes **because**
    the feature is missing. The absence is asserted explicitly and loudly
    instead, with a defect behind it.

RED PROOF (hard-won law 7), OBSERVED — quoted in the commit message
═══════════════════════════════════════════════════════════════════
Each case below was first run against a deliberately broken build and the
failure is recorded in this lane's report; a guard first seen green is a guard
nobody has proved.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import amendments, cancel, detail_api, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, pe1_bills
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


#: `P3.5`'s state. Everything that needs the sixth value is skipped without it,
#: with the reason printed — a declared blind spot with a number attached.
SIXTH_STATE_LANDED = cancel.CANCELLED in models.PAYMENT_STATUSES
needs_sixth_state = pytest.mark.skipif(
    not SIXTH_STATE_LANDED,
    reason="P3.5 (the `cancelled` state + the ck_payments_status migration) has not landed",
)

#: An INPUT, never a clock (BR-TEN-043, gate G6).
CANCELLED_ON = datetime(2026, 9, 21, 11, 45, tzinfo=UTC)


def _processing_payment(tenant, actor):
    """A payment whose money has NOT arrived — the only kind Cancel touches."""
    account = an_account(actor, tenant)
    pe1_bills(tenant, account)
    recorded = a_payment(actor, account, cleared_at=None)
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _post(view, actor, tenant, payment_id, data):
    return api_call(
        view,
        "post",
        user=actor.user,
        role="billing_clerk",
        tenant=tenant,
        data=data,
        payment_id=str(payment_id),
    )


# ══════════════════════════════════════════════════════════════════════════
# P3.13 · CANCEL BY STATUS — and the vocabulary is SIX, not two
# ══════════════════════════════════════════════════════════════════════════

#: One answer per status, named rather than derived. `None` means *this status
#: may be cancelled*; every other value is the code `refusal_for` must return.
#:
#: ⚠ **WRITTEN OUT BY HAND ON PURPOSE.** Deriving it from
#: `PAYMENT_FROZEN_STATUSES` would make this case agree with the product by
#: construction — it would restate the implementation rather than check it, and
#: `PAYMENT_FROZEN_STATUSES` is itself DERIVED (a seventh status would join the
#: frozen side on a line nobody edits; `DEF-PAY-6454` is what that already cost
#: once). A hand-written table is the only kind that can disagree.
CANCEL_ANSWER_BY_STATUS = {
    models.PAYMENT_PROCESSING: None,
    models.PAYMENT_CLEARED: cancel.REFUSED_CLEARED,
    models.PAYMENT_FAILED: cancel.REFUSED_FROZEN,
    models.PAYMENT_REVERSED: cancel.REFUSED_FROZEN,
    # CR-186-BRC10 (PO 2026-10-21): "cancelled (only from posted)" — every
    # new payment is posted, and Cancel is its door. `processing` is a row
    # written before the change and keeps its own (legacy) answer.
    models.PAYMENT_POSTED: None,
    models.PAYMENT_CANCELLED: cancel.REFUSED_ALREADY,
}


def test_every_one_of_the_six_statuses_has_exactly_one_cancel_answer(brazos, marcus):
    """`P3.13`, completed: the module's two headline cases exercised TWO of six.

    ⚠ **THE COUNT COMES FIRST, AND IT IS THE WHOLE POINT.** A loop over
    `PAYMENT_STATUSES` is green on a tuple that has silently lost a value, which
    is precisely the fault `paymentStatusParity.test.ts` was minted for on the
    front end in this same CR — `PAYMENT_STATUSES` listed FIVE while the
    database accepted SIX and every check in the repository was happy.

    ⚠ **AND THE TABLE IS COMPARED AS SETS IN BOTH DIRECTIONS**, so a SEVENTH
    status added without a cancel answer fails here by name rather than being
    silently swept into `REFUSED_FROZEN` by a derivation nobody reads.

    ⚠ **WHAT THIS PROVES IS THE PYTHON PREDICATE**, on SQLite like every other
    case in the default suite. `refusal_for` is what both the screen and the
    service consult (BR-SHL-025), so it is the right subject — but the database
    guarantee underneath it is `trg_payment_immutable` and lives on PostgreSQL.
    """
    assert len(models.PAYMENT_STATUSES) == 6, (
        "the payment vocabulary is SIX since `payments/0036` (`P3.5`). If this moved, the "
        "table below needs a row and `ck_payments_status` needs a migration — do not "
        "widen this number without both"
    )
    assert set(CANCEL_ANSWER_BY_STATUS) == set(models.PAYMENT_STATUSES), (
        "a status exists with no stated cancel answer (or the reverse). Add it to "
        "CANCEL_ANSWER_BY_STATUS deliberately — a new status joins the FROZEN side by "
        "default, on a line nobody edits (DEF-PAY-6454)"
    )

    with tenant_ctx(brazos):
        _account, live = _processing_payment(brazos, marcus)
        # The one status whose answer depends on the ROW and not only on the
        # vocabulary: `refusal_for` walks past the status for `processing` and
        # asks whether money was posted, so it needs a real, saved payment.
        assert cancel.refusal_for(live) is CANCEL_ANSWER_BY_STATUS[models.PAYMENT_PROCESSING]

        for status, expected in sorted(CANCEL_ANSWER_BY_STATUS.items()):
            if status == models.PAYMENT_PROCESSING:
                continue
            # UNSAVED, and deliberately: writing a `posted` or `reversed` row
            # would be a fixture asserting the trigger permits an INSERT, which
            # is a different claim on a different database. `refusal_for`
            # returns on the status for all five of these before it touches the
            # row's allocations, so an instance is the exact subject.
            candidate = models.Payment(status=status)
            assert cancel.refusal_for(candidate) == expected, (
                f"a `{status}` payment answers {cancel.refusal_for(candidate)!r} and the "
                f"agreed answer is {expected!r}"
            )


def test_only_the_cleared_refusal_sends_the_clerk_to_reverse(brazos, marcus):
    """The other half of `P3.13`'s sentence, and nothing asserted it.

    *"Refused on `cleared`, and the clerk is pointed at Reverse"* is a rule with
    two sides. `test_a_cleared_payment_is_refused_and_told_to_reverse` proves the
    first. **The second is that no OTHER refusal may say it** — Reverse requires
    a CLEARED payment (`US-PAY-009` TC-5: *a PROCESSING payment cannot bounce*),
    so telling the holder of a `failed` or already-`reversed` row to go and
    reverse it sends them to a door that refuses them as well. Two refusals and
    no next step is how *"the two words a clerk confuses"* stay confused.

    ⚠ **BOTH DIRECTIONS IN ONE CASE.** *"No other refusal contains the word"* is
    vacuously true of a build with no sentences at all, so the positive is
    asserted in the same breath.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

        cleared_words = str(cancel._refusal_error(payment, cancel.REFUSED_CLEARED))
        # CR-186-BRC10 — PO 2026-10-21: "cleared payment cannot be cancled ; in
        # those cases refunds or credits will be issued". The cleared refusal
        # names THAT act now; no other refusal sends the clerk to Reverse.
        assert "refund or a credit" in cleared_words, (
            "the cleared refusal must NAME the act that will work — that clerk is not "
            "stuck, they are on the wrong door"
        )

        for code in (
            cancel.REFUSED_FROZEN,
            cancel.REFUSED_ALREADY,
            cancel.REFUSED_IS_A_REVERSAL,
            cancel.REFUSED_MONEY_IS_POSTED,
        ):
            words = str(cancel._refusal_error(payment, code))
            assert len(words.split()) > 8, f"{code} has no sentence of its own"
            assert "Reverse" not in words, (
                f"{code} points the clerk at Reverse, and Reverse refuses anything that is "
                "not CLEARED (US-PAY-009 TC-5) — so this sends them to a second refusal"
            )


@needs_sixth_state
def test_a_frozen_payment_is_refused_at_the_door_and_is_not_sent_to_reverse(brazos, marcus):
    """The map above is a predicate; this is the ENDPOINT, for one frozen status.

    ⚠ **WITHOUT THIS, `P3.13` WOULD BE PROVED ENTIRELY BY UNIT-TESTING A PURE
    FUNCTION** — and a service that never called `refusal_for` would pass every
    case above. The cleared path already has its endpoint case; this is the
    same walk one status along, and it is the status that shows the Reverse
    sentence is not simply pasted onto every refusal.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
    # An INSERT-free way to reach a frozen status on SQLite *and* on
    # PostgreSQL: the cancel path itself puts the row there, through the one
    # statement `trg_payment_immutable` permits.
    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"reason": cancel.CANCEL_REASON_DUPLICATE, "cancelled_on": CANCELLED_ON.isoformat()},
    )
    assert answered.status_code == 201, answered.data

    # Now cancel the REVERSING row, which is `cancelled` from birth and was
    # never processing. Hard rule 6's replay covers a second cancel of the
    # ORIGINAL; this is a different row and a genuine refusal.
    with tenant_ctx(brazos):
        mirror = models.Payment.objects.get(reverses_payment_id=payment.pk)
        assert mirror.status == cancel.CANCELLED
        assert cancel.refusal_for(mirror) == cancel.REFUSED_IS_A_REVERSAL

    refused = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        mirror.pk,
        {"reason": cancel.CANCEL_REASON_DUPLICATE, "cancelled_on": CANCELLED_ON.isoformat()},
    )
    assert refused.status_code == 422, refused.data
    assert "Reverse" not in str(refused.data), (
        "a reversing row cannot be reversed either (BR-PAY-036) — naming Reverse here "
        "sends the clerk to a second refusal"
    )


# ══════════════════════════════════════════════════════════════════════════
# P3.14 · THE THREE AMENDABLE COLUMNS — the SERVICE half, said plainly
# ══════════════════════════════════════════════════════════════════════════


def test_the_amendable_list_is_exactly_three_and_a_fourth_is_refused_by_name(brazos, marcus):
    """`P3.14`, the half a SQLite suite can honestly claim.

    ⚠ **THE TRIGGER IS NOT ON TRIAL HERE AND THIS CASE DOES NOT PRETEND IT IS.**
    `trg_payment_immutable` does not exist on SQLite (law 14), so *"the trigger
    refuses a cancelled UPDATE and still permits the three"* is proved by
    `10-scripts/p3_cancel_state_and_trigger_readback.py` §4, §6 and §8 on real
    PostgreSQL 16 — read that script before trusting anything here. What this
    case owns is the SERVICE's own list, which is the layer a clerk actually
    meets and which can drift away from the database with the suite green.

    ⚠ **A COUNT, NOT A LOOP.** `for field in AMENDABLE_FIELDS: assert …` is
    green on a tuple that has lost `memo`. Three is the number `payments/0014`
    moved the database's allow list to, and hard rule 4 narrows for three
    columns *"and for nothing else"* — so the number is the assertion.
    """
    assert len(amendments.AMENDABLE_FIELDS) == 3, (
        "hard rule 4 is narrowed for THREE columns and for nothing else (`OQ-1322`, PO "
        "2026-09-02). Widening this list is a new ruling, not a refactor — and "
        "`payments/0014` is the only place the database's allow list moves"
    )
    assert set(amendments.AMENDABLE_FIELDS) == {"reference", "memo", "tender_id"}, (
        "these are the API's names for `confirmation`, `memo` and `method_id`"
    )
    # The fourth direction: a field NOT on the list is refused BY NAME rather
    # than silently dropped, which is what makes the route the spec.
    with pytest.raises(Exception) as refused:
        amendments.refuse_money_fields({"amount": "1.00"})
    assert "amount" in str(refused.value)


@needs_sixth_state
def test_a_cancelled_payments_reference_is_still_correctable(brazos, marcus):
    """The PO ruling of 2026-09-02 does not stop at the `processing` boundary.

    A clerk types cheque `4471` as `4417`, cancels the payment five minutes
    later because it was the wrong customer, and *then* notices the typo. The
    three-column narrowing is written against the TABLE and not against a
    status, so the correction must still work — and the database agrees
    (`p3_cancel_state_and_trigger_readback.py` §6 permits all three on a
    cancelled row and refuses a fourth).

    ⚠ **THE CLERK'S NOTE IS WRITTEN AT CANCEL TIME AND IS STILL CORRECTABLE
    AFTERWARDS, WHICH IS NOT THE SAME AS BEING REQUIRED.** `cancel_payment`
    takes an OPTIONAL `note` and writes it to the REVERSING row's `memo` (p044
    makes *Why* required and *Note* optional). This case asserts the
    correctability, never the requirement — asserting a requirement no ruling
    made would put a false rule into the suite, which is worse than no case.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {
            "reason": cancel.CANCEL_REASON_WRONG_ACCOUNT,
            "note": "wrong customer at the counter",
            "cancelled_on": CANCELLED_ON.isoformat(),
        },
    )

    with tenant_ctx(brazos):
        payment.refresh_from_db()
        assert payment.status == cancel.CANCELLED
        mirror = models.Payment.objects.get(reverses_payment_id=payment.pk)
        assert mirror.memo == "wrong customer at the counter", (
            "the clerk's own words live on the ROW, not only on a pruned audit entry"
        )

        amendments.amend_reference(
            marcus,
            payment_id=payment.pk,
            note="the cheque number was mistyped",
            reference="4471",
        )
        payment.refresh_from_db()
        assert payment.confirmation == "4471"
        assert payment.status == cancel.CANCELLED, "correcting a reference moves no status"


# ══════════════════════════════════════════════════════════════════════════
# P3.15 · A CORRECTION LEAVES THE ORIGINAL BYTE-IDENTICAL
# ══════════════════════════════════════════════════════════════════════════


def test_a_correction_leaves_the_original_byte_identical(brazos, marcus, dana):
    """Hard rule 4 SATISFIED, not circumvented — 2·3c's own banner in one case.

    The Correction modal's first line is *"This does not change PMT-…. It writes
    a new row instead."* That is a claim about the database, and this is it:
    a second payment of `type=adjustment` is recorded against the same account
    and **every concrete column** of the original is compared before and after.

    ⚠ **EVERY COLUMN, NOT THE FOUR A READER WOULD THINK OF.** `_meta
    .concrete_fields` is walked, so a column added later is covered on the day
    it lands rather than on the day somebody remembers.

    ⚠ **AND THIS IS A STATEMENT ABOUT THE SERVICE, ON SQLITE.** The database
    guarantee is `trg_payment_immutable`, which is not here (law 14). Said out
    loud rather than implied by the word *byte-identical*.

    ⚠ **THE FIGURE IS `+8.10` AND THE DRAWING'S IS `-8.10`, AND THAT IS A
    DEFECT RATHER THAN A CHOICE — `DEF-PAY-6260`.** `record_payment` refuses
    any amount at or below zero BY NAME, so the signed correction the shipped
    modal offers cannot be submitted in the direction the blueprint works
    through. See `test_a_negative_correction_is_refused_by_the_service_today`
    below; this case uses the direction that WORKS so that it proves
    immutability and not the bug.
    """
    with tenant_ctx(brazos):
        account, payment = _processing_payment(brazos, marcus)
        before = {
            field.name: getattr(payment, field.attname)
            for field in models.Payment._meta.concrete_fields
        }

    with tenant_ctx(brazos):
        from apps.payments import services as payment_services

        correction = payment_services.record_payment(
            # ⚠ **A SYSTEM ADMIN, AND THAT IS A RULE RATHER THAN A FIXTURE
            # CONVENIENCE.** This utility's approval threshold for a credit or
            # an adjustment is `0`, so EVERY adjustment needs one (CR-008); a
            # Billing Clerk is refused by name. Recorded here because it is
            # what a correction actually costs at the counter — the clerk who
            # took the payment cannot correct its amount alone.
            dana,
            account_id=account.pk,
            amount=Decimal("8.10"),
            posted_at=CANCELLED_ON,
            payment_type=models.PAYMENT_TYPE_ADJUSTMENT,
            # CS-35 — a credit or an adjustment carries a reason from the
            # tenant's own list, and `_reason_code` refuses one without it. The
            # code also chooses the GL account this lands in (CR-008 ruling 9),
            # so it is not decoration.
            reason_code="goodwill",
            idempotency_reference=uuid.uuid4(),
        )

        payment.refresh_from_db()
        after = {
            field.name: getattr(payment, field.attname)
            for field in models.Payment._meta.concrete_fields
        }

    moved = {key for key in before if before[key] != after[key]}
    assert moved == set(), f"a correction moved {sorted(moved)} on the payment it corrects"

    with tenant_ctx(brazos):
        written = models.Payment.objects.get(pk=correction.payment_id)
        assert written.pk != payment.pk, "a correction is a NEW ROW — that is the whole rule"
        assert written.type == models.PAYMENT_TYPE_ADJUSTMENT
        assert written.amount == Decimal("8.10")
        # ⚠ **WHAT WOULD MAKE THE CASE ABOVE PASS WRONGLY:** a build where
        # `record_payment` silently wrote nothing at all. Then *"the original
        # did not move"* is true and means nothing. The new row is asserted in
        # the same case for exactly that reason.


def test_corrects_payment_id_is_not_wired_to_anything_yet(brazos, marcus, dana):
    """⚠ **`P3.15`'s SECOND HALF CANNOT BE TRUE TODAY, AND THIS IS THE HOLD.**

    `P3.15` asks that *"`corrects_payment_id` points at it"*. **It cannot.**
    `payments/0037` added the column (`P3.7`, and proved it thoroughly against
    `pg_constraint`), `models.Payment.corrects_payment` declares it — and
    **nothing in `06-backend/apps/` or `07-frontend/src/` ever writes or reads
    it.** Measured 2026-09-23: the strings `corrects_payment` and
    `corrects_payment_id` occur in the migration and the model and nowhere else.
    `services.record_payment` takes `moved_from_payment_id` and has no parameter
    for it, and `AddCorrectionModal` posts `type: "adjustment"` carrying no
    reference to the payment it corrects.

    **That is hard-won law 2 exactly — built is not wired** — on a money path,
    and it is invisible to every check this repository has, because an absence
    is (CLAUDE.md, `DEF-CUS-3653`). Filed as **`DEF-PAY-6259`**.

    ⚠ **THIS CASE IS THE TEST THAT FIRES WHEN THE HOLD EXPIRES** (law 2's own
    cure, *write it in the same commit*). It asserts the column is NULL on a
    correction today. **The day anybody wires it, this case goes RED and names
    `P3.15`** — and the right fix then is to replace it with the assertion
    `P3.15` actually asked for, not to loosen it.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** everything, if it only asserted
    `is None` — a build where the column had been DROPPED would pass too, and
    so would one where `record_payment` wrote nothing. So the column's
    EXISTENCE is asserted first, and a row is really written.
    """
    assert any(
        field.attname == "corrects_payment_id"
        for field in models.Payment._meta.concrete_fields
    ), "`payments/0037` added this column; if it is gone, `P3.7` was reverted"

    with tenant_ctx(brazos):
        account, _payment = _processing_payment(brazos, marcus)
        from apps.payments import services as payment_services

        correction = payment_services.record_payment(
            dana,  # a System Admin: the threshold is 0 (see above)
            account_id=account.pk,
            amount=Decimal("8.10"),
            posted_at=CANCELLED_ON,
            payment_type=models.PAYMENT_TYPE_ADJUSTMENT,
            reason_code="goodwill",
            idempotency_reference=uuid.uuid4(),
        )
        written = models.Payment.objects.get(pk=correction.payment_id)

    assert written.corrects_payment_id is None, (
        "`corrects_payment_id` is now being written — so DEF-PAY-6259 is fixed and "
        "`P3.15`'s second half is finally buildable. REPLACE this case with the "
        "assertion P3.15 asked for: a correction points at the payment it corrects, "
        "and the walk back through `ix_payments_corrects` finds it. Do not relax it"
    )


def test_a_negative_correction_is_refused_by_the_service_today(brazos, marcus, dana):
    """⚠ **A SECOND FINDING FROM `P3.15`, AND IT IS A LIVE ONE — `DEF-PAY-6260`.**

    2·3c draws **Correction amount** with the help line *"Negative takes money
    back."*, its note ② reads *"a correction can go either way, and the sign is
    the whole meaning"*, and the worked figure on p042–43 is **`−8.10`** with
    the consequence *"Ana Alvarez will owe $8.10 more."* `AddCorrectionModal`
    was built to that: a `SIGNED_AMOUNT` regex, a non-zero rule, a
    `takesMoneyBack` branch, and the value posted straight through
    `recordPayment` with `type: "adjustment"`.

    **`services.record_payment` refuses it**, and not with a gentle message:

        payment amount -8.10 must be greater than zero (A2 §S22 '> 0'). A
        reversal is a NEW reversing row (BR-PAY-002 / hard rule 4), never a
        negative payment …

    which is a true sentence about REVERSALS shown to a clerk filling in a
    CORRECTION form. So the modal's whole negative half is a live control over
    a refusing service — hard-won law 2's mirror, the shape that cost the
    customer portal six dead doors — and **`tsc`, every suite and every gate
    are green on it**, because no test had ever posted one.

    ⚠ **WHICH SIDE IS WRONG IS NOT THIS LANE'S TO DECIDE.** The `> 0` rule
    carries `A2 §S22` and a hard-rule-4 argument; the drawing carries B14 rule
    41. That is a drawing contradicting a signed rule, which is the ONE thing
    that reaches the PO (CLAUDE.md law 13). Filed, not answered.

    ⚠ **SO THIS CASE ASSERTS TODAY'S BEHAVIOUR, LOUDLY, AND FIRES WHEN IT
    CHANGES.** The day either side moves it goes RED and names the defect.
    Pinning the refusal is not endorsing it.
    """
    with tenant_ctx(brazos):
        account, _payment = _processing_payment(brazos, marcus)
        from apps.payments import services as payment_services

        with pytest.raises(Exception) as refused:
            payment_services.record_payment(
                dana,
                account_id=account.pk,
                amount=Decimal("-8.10"),
                posted_at=CANCELLED_ON,
                payment_type=models.PAYMENT_TYPE_ADJUSTMENT,
                reason_code="goodwill",
                idempotency_reference=uuid.uuid4(),
            )

    # ⚠ **THE WORDS, NOT THE EXCEPTION CLASS.** `PaymentRuleError` is raised by
    # a dozen guards on this path — a missing reason code raises it too — so
    # `pytest.raises` alone would pass on a build where the sign was fine and
    # something else was broken. That is law 7's *looking at the wrong thing*.
    assert "must be greater than zero" in str(refused.value), (
        "the service no longer refuses a negative adjustment — DEF-PAY-6260 has moved. "
        "If the `> 0` rule was relaxed, replace this case with the assertion 2·3c "
        "actually wants: a `-8.10` correction is WRITTEN and the bill re-opens at $8.10"
    )
