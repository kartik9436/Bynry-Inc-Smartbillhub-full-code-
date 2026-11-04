# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6323 — every seeded payment took `record_payment`'s default
#          idempotency source (`entry`), so the Payments list's SOURCE column
#          read "Counter" on card and ACH money that never reached a counter.
# Rules:   CR-132-BRC07 / CR-135-BRC07 P0.1 (`payments.origin`, written FROM
#          the idempotency source; `entry` is labelled Counter, `webhook`
#          Digital) · BR-PAY-028 (idempotency) · PO ruling 2026-09-23 §3.4
#          (only cash, cheques and money orders reach a drawer) · CLAUDE.md
#          hard rule 4 (a payment is append-only, so a duplicate is permanent)
#          · hard rule 6 · hard-won law 7 (prove it RED first)
# Tests:   this file
# Impacts: apps/payments/sample_data.py (`_source_for`,
#          `_recorded_before_the_source_was_stated`, `_record_sample_payment`)
# ───────────────────────────────────────────────────────
"""DEF-PAY-6323 — the seeded card and ACH money says where it came from.

TWO QUESTIONS, AND THE SECOND IS THE ONE THAT COSTS MONEY
---------------------------------------------------------
1. **A tenant seeded from now on** labels its card and ACH payments with the
   `webhook` origin (*Digital*) and its cash and cheques with `entry`
   (*Counter*). Asked of the WHOLE seeded estate, with the population counted
   first so an empty estate cannot pass.
2. **A tenant seeded BEFORE this change is not paid twice.** The origin is the
   first segment of the idempotency key, so the new seed keys a card payment
   `webhook|sample:…` where the old one keyed it `entry|sample:…`.
   `record_payment`'s own replay read asks only for the new key; without the
   seed's second read every card and ACH bill on an existing demo tenant would
   collect a SECOND permanent payment the next time the sample set is loaded.

RED-FIRST RECORD (hard-won law 7) — quoted in the lane report and in the
defect's close, not predicted here:
  * case 1 on the unchanged tip: the seeded card and ACH payments carry
    `entry`.
  * case 2 with `_recorded_before_the_source_was_stated` made to return None
    (the naive fix): the replay records a second payment.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import counters, idempotency, sample_data
from apps.payments import models as payment_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
AMOUNT = Decimal("84.0000")


def _bill(actor, tenant):
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2608-{uuid.uuid4().hex[:6]}",
        total=AMOUNT,
        issued_on=date(2026, 8, 1),
    )
    return account


def _old_seed(actor, account, reference, method_code):
    """What `sample_data` did before this change: no source stated, so `entry`."""
    from apps.payments import services

    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=AMOUNT,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code=method_code,
        memo="sample data",
        idempotency_reference=reference,
    )


def _new_seed(actor, account, reference, method_code):
    return sample_data._record_sample_payment(
        actor,
        account_id=account.pk,
        amount=AMOUNT,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code=method_code,
        memo="sample data",
        idempotency_reference=reference,
    )


# ══ 1 · THE SOURCE IS STATED ════════════════════════════════════════════════


@pytest.mark.parametrize(
    "method_code, origin",
    [("card", "webhook"), ("ach", "webhook"), ("cash", "entry"), ("check", "entry")],
)
def test_def_pay_6323__each_tender_is_seeded_with_its_own_origin(brazos, dana, method_code, origin):
    """Card and ACH arrive over a wire (*Digital*); cash and cheques are keyed at
    a counter (*Counter*). Decided by `counters.HAND_TENDERS`, the same question
    the till block asks, so SOURCE and BATCH cannot disagree about a row."""
    with tenant_ctx(brazos):
        account = _bill(dana, brazos)
        result = _new_seed(dana, account, f"sample:{uuid.uuid4().hex[:8]}", method_code)
        payment = payment_models.Payment.objects.get(pk=result.payment_id)

    assert result.created is True
    assert payment.origin == origin
    assert payment.origin_is_derived is False, "observed at INSERT, never inferred"
    assert (method_code in counters.HAND_TENDERS) == (origin == idempotency.SOURCE_ENTRY)


# ══ 2 · A TENANT SEEDED BEFORE THE FIX IS NOT PAID TWICE ════════════════════


@pytest.mark.parametrize("method_code", ["card", "ach"])
def test_def_pay_6323__a_payment_seeded_under_the_old_key_is_a_replay(brazos, dana, method_code):
    """THE HAZARD THE DEFECT ROW NAMES: *"on a tenant already seeded the replay
    check would miss and record a SECOND permanent payment"*.

    The old seed's row is written exactly as the old seed wrote it — through
    `record_payment` with no source — and then the new seed is run over the
    same bill. It must write nothing and answer with the ORIGINAL payment, as
    `record_payment` answers any replay.
    """
    reference = f"sample:BL-2608-{uuid.uuid4().hex[:6]}"
    with tenant_ctx(brazos):
        account = _bill(dana, brazos)
        first = _old_seed(dana, account, reference, method_code)
        before = payment_models.Payment.objects.count()
        replay = _new_seed(dana, account, reference, method_code)
        after = payment_models.Payment.objects.count()
        kept = payment_models.Payment.objects.get(pk=first.payment_id)

    assert first.created is True and kept.origin == "entry", "the old seed's shape"
    assert after == before, (
        f"the replay on an old tenant wrote {after - before} payment(s) — a second, "
        "permanent payment against a bill that was already paid (hard rule 4)"
    )
    assert replay.created is False
    assert str(replay.payment_id) == str(first.payment_id)
    assert replay.amount == AMOUNT


def test_def_pay_6323__a_new_electronic_payment_replays_on_its_new_key(brazos, dana):
    """The second read is an ADDITION, not a replacement: a payment seeded by
    the fixed code is found again by `record_payment`'s own key."""
    reference = f"sample:BL-2608-{uuid.uuid4().hex[:6]}"
    with tenant_ctx(brazos):
        account = _bill(dana, brazos)
        first = _new_seed(dana, account, reference, "card")
        again = _new_seed(dana, account, reference, "card")
        rows = payment_models.Payment.objects.filter(webhook_key__endswith=reference).count()

    assert first.created is True and again.created is False
    assert rows == 1


def test_def_pay_6323__a_counter_tender_is_keyed_exactly_as_before(brazos, dana):
    """Cash and cheques kept the `entry` key, so an old tenant's cheque replays
    through `record_payment` itself — and the second read is never asked."""
    reference = f"sample:BL-2608-{uuid.uuid4().hex[:6]}"
    with tenant_ctx(brazos):
        account = _bill(dana, brazos)
        first = _old_seed(dana, account, reference, "check")
        again = _new_seed(dana, account, reference, "check")
        rows = payment_models.Payment.objects.filter(webhook_key__endswith=reference).count()

    assert again.created is False and str(again.payment_id) == str(first.payment_id)
    assert rows == 1


# ══ 3 · THE WHOLE SEEDED ESTATE ═════════════════════════════════════════════


def test_def_pay_6323__the_seeded_estate_says_where_its_money_came_from():
    """Every seeded payment's origin matches its tender — asked of the whole
    estate the demo ships, not of a hand-built row.

    Non-vacuous (DEF-466's shape): both populations are counted before the
    rule is asserted over them, so a fixture that seeded no card payment at all
    cannot pass by having nothing to be wrong about.
    """
    from tests.test_def_pay_6321_seeded_deposit_batches import _plant

    seeded = _plant()
    with tenant_ctx(seeded):
        seeded_rows = payment_models.Payment.objects.filter(
            memo__startswith="sample data", type=payment_models.PAYMENT_TYPE_PAYMENT
        )
        electronic = seeded_rows.exclude(method__code__in=counters.HAND_TENDERS)
        # Includes the landlord's one cheque over three properties, which
        # `tenders.record_multi_account_payment` records with `entry` itself.
        by_hand = seeded_rows.filter(method__code__in=counters.HAND_TENDERS)
        electronic_count = electronic.count()
        by_hand_count = by_hand.count()
        wrong_electronic = list(
            electronic.exclude(origin=idempotency.SOURCE_WEBHOOK).values_list(
                "payment_no", "method__code", "origin"
            )
        )
        wrong_by_hand = list(
            by_hand.exclude(origin=idempotency.SOURCE_ENTRY).values_list(
                "payment_no", "method__code", "origin"
            )
        )

    assert electronic_count > 0, "the demo seeded no card or ACH payment — nothing to check"
    assert by_hand_count > 0, "the demo seeded no cash or cheque — nothing to check"
    assert wrong_electronic == [], (
        f"{len(wrong_electronic)} card/ACH payment(s) read Counter over money that never "
        f"reached a counter: {wrong_electronic[:5]}"
    )
    assert wrong_by_hand == [], (
        f"{len(wrong_by_hand)} cash/cheque payment(s) are not labelled Counter: "
        f"{wrong_by_hand[:5]}"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6323 (filed 2026-09-23 by lane SEED-BATCH, from the PO's
#         report on the deployed Payments list)
# generated: 2026-09-24 by lane SMALL-PAY
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
