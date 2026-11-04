# ── Trace ──────────────────────────────────────────────
# Story:    CR-008 third set, slice B-10 — tender → GL posting (OQ-264 CLOSED
#           2026-08-17: option (ii)'s SECOND half, *"teach the posting service
#           to prefer it"*, ruled IN scope by the PO: "10 - A inside CR-008
#           now")   Screens: S22 · S38 · S39 · S40 · S56 · SET-11 §3
# Rules:    CLAUDE.md rule 5 (balanced pairs; ONLY the ledger posting service
#           writes journal lines) · rule 4 (immutability) · rule 6
#           (idempotency) · BR-PAY-039 / OQ-143 (money is not realised until
#           the bank confirms it — UNCHANGED: only WHICH holding account is
#           debited moves) · BR-PAY-019/025 (bank rec; batches day × method) ·
#           BR-LED-003 (a correction is a mirror of what was POSTED)
# Tests:    this file IS the proof for the B-10 slice
# ───────────────────────────────────────────────────────
"""Tender → GL posting: the receipt debits the tender's own clearing account,
and reconciliation credits EXACTLY WHAT WAS DEBITED — both legs in one change.

**THE SENTENCE THIS FILE EXISTS TO KEEP TRUE** is the decision log's
(2026-08-17, CR-008 second set, judgment 2): *"If the receipt leg debited a
per-tender clearing account while reconciliation kept crediting undeposited
funds, reconciliation would credit an account that was never debited — the
trial balance goes out by the amount of every card payment. So the two legs
must move in one change."* This is that one change, and the trial-balance
test at the bottom is the tie-out that would have caught the half-change.

**The worked case, from the CR record:** a utility takes **$412.30** by card
through Stripe and **$85.00** in cash at the counter on the same day. With
`card → 1015 Merchant clearing — Stripe` mapped and cash unmapped:

    on RECEIPT (card)    DR 1015 Merchant clearing   412.30 / CR AR
    on RECEIPT (cash)    DR 1010 Undeposited funds    85.00 / CR AR
    on RECONCILIATION    DR 1000 Cash / CR the account each receipt DEBITED

**What is deliberately UNCHANGED:** an unmapped tender still lands in
undeposited funds (NULL = today's behaviour, the migration's own words);
OQ-143's law — cash is not cash until the bank confirms it — still governs,
only WHICH holding account holds the unconfirmed money is now the tender's
choice; reversal still mirrors whatever was posted (BR-LED-003), so an NSF on
a mapped tender unwinds the mapped leg for free.

**The load-bearing design fact:** reconciliation reads the receipt entries'
OWN debit lines (`apps/ledger/selectors.entry_debit_totals`, a published
tenant-scoped read) — never today's mapping — so a tender re-pointed between
receipt and reconciliation still credits the account the money actually sits
in. tc5 is that case, on figures.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from tests.test_us_pay_020_023_bank_rec import the_days_batches

from apps.ledger import models as ledger_models
from apps.payments import bankrec_models as bankrec
from apps.payments import ledger_seam, models, reconciliation, reversal, services
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (  # noqa: F401
    a_bank_account,
    a_cleared_payment,
    a_statement,
    journal_legs,
    leg,
)

pytestmark = pytest.mark.django_db

# The CR record's own worked figures (11-change-requests.md, CR-008 second set
# §1): $412.30 by card through Stripe, $85.00 in cash at the counter.
CARD_STRIPE = Decimal("412.30")
CASH_COUNTER = Decimal("85.00")

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)
DAY = date(2026, 8, 8)


def admin(brazos):
    return staff_actor(brazos, "system_admin", "cr008b10@brazosbend.test")


def clearing_account(tenant, *, code="1015", name="Merchant clearing — Stripe"):
    """A tenant's own clearing account — the thing SET-11 §3 points a tender at."""
    return ledger_models.LedgerAccount.objects.create(
        tenant=tenant, code=code, name=name, type="asset"
    )


def map_tender(actor, tenant, method_code, account_id):
    """Point one tender at its cash/clearing account THROUGH THE REAL DOOR —
    Settings → Accounting → GL mapping §3's own write path."""
    method = tenancy_models.PaymentMethod.objects.get(tenant=tenant, code=method_code)
    return tenancy_services.update_lookup_entry(
        actor,
        "payment_methods",
        method.pk,
        {"clearing_gl_account_id": str(account_id) if account_id else None},
    )


# ═══════════════════════════════════════════════════════════════════════════
# The RECEIPT leg
# ═══════════════════════════════════════════════════════════════════════════
def test_b10_tc1__a_mapped_tender_debits_its_own_clearing_account(brazos, marcus):
    """The CR's $412.30 card payment lands in 1015, not 1010 — and AR still
    credits, so the entry balances exactly as before with one account moved."""
    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)

        recorded = a_cleared_payment(
            marcus, brazos, amount=CARD_STRIPE, method_code="card", posted_at=POSTED_AT
        )
        assert recorded.posted_to_ledger is True

        legs = journal_legs(brazos)
        assert leg(legs, "1015", "debit") == CARD_STRIPE
        assert leg(legs, "1200", "credit") == CARD_STRIPE
        # Undeposited funds NEVER touched for the mapped tender.
        assert leg(legs, "1010", "debit") == Decimal("0")


def test_b10_tc2__an_unmapped_tender_still_lands_in_undeposited_funds(brazos, marcus):
    """NULL = today's behaviour, byte for byte — the migration's own promise.
    The $85.00 counter cash debits 1010 exactly as it has since OQ-143."""
    with tenant_ctx(brazos):
        a_cleared_payment(
            marcus, brazos, amount=CASH_COUNTER, method_code="cash", posted_at=POSTED_AT
        )
        legs = journal_legs(brazos)
        assert leg(legs, "1010", "debit") == CASH_COUNTER
        assert leg(legs, "1200", "credit") == CASH_COUNTER


def test_b10_tc3__a_dead_clearing_account_refuses_by_name_and_nothing_lands(brazos, marcus):
    """The pick-time validation (CR-008 ruling 3) cannot see tomorrow: an
    account live when it was mapped can be deactivated afterwards. Posting to
    a retired account would put money in a row the trial balance treats as
    closed, and FALLING BACK to undeposited would silently move money to an
    account the tenant told us not to use — so the payment REFUSES, whole
    (record_payment is one transaction: no payment row, no entry, no orphan).
    """
    from django.utils import timezone

    from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        stripe.deleted_at = timezone.now()
        stripe.save(update_fields=["deleted_at", "updated_at"])

        account = an_account_of(marcus, brazos)
        an_issued_bill(
            brazos,
            account,
            number=f"BL-2608-{uuid.uuid4().hex[:6]}",
            total=CARD_STRIPE,
            issued_on=date(2026, 8, 1),
        )
        payments_before = models.Payment.objects.filter(tenant=brazos).count()
        entries_before = ledger_models.JournalEntry.objects.filter(tenant=brazos).count()

        with pytest.raises(PaymentRuleError) as refusal:
            services.record_payment(
                marcus,
                account_id=account.pk,
                amount=CARD_STRIPE,
                method_code="card",
                posted_at=POSTED_AT,
                cleared_at=POSTED_AT,
                idempotency_reference=uuid.uuid4(),
            )
        message = str(refusal.value)
        assert "card" in message
        assert "GL mapping" in message

        assert models.Payment.objects.filter(tenant=brazos).count() == payments_before
        assert ledger_models.JournalEntry.objects.filter(tenant=brazos).count() == entries_before


def test_b10_tc4__a_replayed_mapped_payment_posts_once(brazos, marcus):
    """Hard rule 6 is untouched by the new leg: the posting key is still
    `payment|<id>|cleared`, so the replay returns the FIRST entry and writes
    nothing — asserted on a MAPPED tender because that is the changed path."""
    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        token = uuid.uuid4()

        from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

        account = an_account_of(marcus, brazos)
        an_issued_bill(
            brazos,
            account,
            number=f"BL-2608-{uuid.uuid4().hex[:6]}",
            total=CARD_STRIPE,
            issued_on=date(2026, 8, 1),
        )
        kwargs = dict(
            account_id=account.pk,
            amount=CARD_STRIPE,
            method_code="card",
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT,
            idempotency_reference=token,
        )
        first = services.record_payment(marcus, **kwargs)
        replay = services.record_payment(marcus, **kwargs)
        assert first.created is True and replay.created is False
        legs = journal_legs(brazos)
        assert leg(legs, "1015", "debit") == CARD_STRIPE  # once, not twice


# ═══════════════════════════════════════════════════════════════════════════
# The RECONCILIATION leg — credits what was DEBITED, read from the entries
# ═══════════════════════════════════════════════════════════════════════════
def _matched_card_batch(actor, tenant, *, amounts, bank_credit):
    """Cut the card day's batch and hand-match it to the bank's line."""
    reconciliation.cut_deposit_batches(actor=actor, day=DAY, occurred_at=POSTED_AT)
    # CR-186-BRC10: the payments joined the day's batch at posting.
    (batch,) = the_days_batches(tenant, DAY)
    account = a_bank_account(tenant)
    imported = reconciliation.import_bank_statement(
        actor=actor,
        bank_account_id=account.pk,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 11),
        payload=a_statement([("2026-08-11", "CARD SETTLEMENT", str(bank_credit))]),
        imported_at=STATEMENT_AT,
    )
    if imported.matched:
        return batch
    reconciliation.match_bank_line(
        actor=actor,
        batch_id=batch.batch_id,
        bank_line_id=imported.exceptions[0].bank_line_id,
        occurred_at=STATEMENT_AT,
    )
    return batch


def test_b10_tc5__reconciliation_credits_the_clearing_account_the_receipts_debited(brazos, marcus):
    """The other half of the one change. Two card payments (412.30 + 85.00 =
    497.30) debited 1015 on receipt; the bank confirms 497.30; the entry is

        DR 1000 Cash                497.30
        CR 1015 Merchant clearing   497.30

    and 1010 Undeposited funds is never touched in either direction. After
    both steps the clearing account NETS TO ZERO — the tie-out that goes out
    by the amount of every card payment if either leg moves alone."""
    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        for amount in (CARD_STRIPE, CASH_COUNTER):
            a_cleared_payment(
                marcus, brazos, amount=amount, method_code="card", posted_at=POSTED_AT
            )
        total = CARD_STRIPE + CASH_COUNTER
        batch = _matched_card_batch(marcus, brazos, amounts=None, bank_credit=total)

        reconciliation.reconcile_batch(
            actor=marcus, batch_id=batch.batch_id, posted_at=STATEMENT_AT
        )

        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == total
        assert leg(legs, "1015", "debit") == total  # the two receipts
        assert leg(legs, "1015", "credit") == total  # the reconciliation
        assert leg(legs, "1010", "debit") == Decimal("0")
        assert leg(legs, "1010", "credit") == Decimal("0")
        assert (
            bankrec.DepositBatch.objects.get(pk=batch.batch_id).status == bankrec.BATCH_RECONCILED
        )


def test_b10_tc6__a_tender_repointed_mid_day_credits_what_each_receipt_debited(brazos, marcus):
    """The reason the credit split is read from the ENTRIES and never derived
    from today's mapping: card pointed at 1015 when the 412.30 arrived, then a
    clerk re-pointed it at 1016 before the 85.00. Reconciliation credits 1015
    412.30 and 1016 85.00 — each account nets to zero. Crediting today's
    mapping instead would leave 412.30 stranded in 1015 forever."""
    with tenant_ctx(brazos):
        boss = admin(brazos)
        stripe = clearing_account(brazos)  # 1015
        adyen = clearing_account(brazos, code="1016", name="Merchant clearing — Adyen")
        map_tender(boss, brazos, "card", stripe.pk)
        a_cleared_payment(
            marcus, brazos, amount=CARD_STRIPE, method_code="card", posted_at=POSTED_AT
        )
        map_tender(boss, brazos, "card", adyen.pk)
        a_cleared_payment(
            marcus, brazos, amount=CASH_COUNTER, method_code="card", posted_at=POSTED_AT
        )
        total = CARD_STRIPE + CASH_COUNTER
        batch = _matched_card_batch(marcus, brazos, amounts=None, bank_credit=total)

        reconciliation.reconcile_batch(
            actor=marcus, batch_id=batch.batch_id, posted_at=STATEMENT_AT
        )

        legs = journal_legs(brazos)
        assert leg(legs, "1015", "credit") == CARD_STRIPE
        assert leg(legs, "1016", "credit") == CASH_COUNTER
        assert leg(legs, "1015", "debit") - leg(legs, "1015", "credit") == Decimal("0")
        assert leg(legs, "1016", "debit") - leg(legs, "1016", "credit") == Decimal("0")


def test_b10_tc7__the_seam_refuses_a_credit_split_that_does_not_foot(brazos, marcus):
    """The balanced-pair tie-out, proved at the seam: a split whose Σ is not
    the batch's recorded total is refused BY NAME before anything reaches the
    posting service — the second of the two independent checks (the ledger's
    debits=credits refusal is the other), because a posting that is wrong here
    is wrong in the trial balance forever."""
    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        a_cleared_payment(
            marcus, brazos, amount=CARD_STRIPE, method_code="card", posted_at=POSTED_AT
        )
        reconciliation.cut_deposit_batches(actor=marcus, day=DAY, occurred_at=POSTED_AT)
        # CR-186-BRC10: the payments joined the day's batch at posting.
        (batch,) = the_days_batches(brazos, DAY)
        row = bankrec.DepositBatch.objects.get(pk=batch.batch_id)

        with pytest.raises(PaymentRuleError) as refusal:
            ledger_seam.post_batch_reconciled(
                batch=row,
                bank_total=CARD_STRIPE,
                recorded_total=CARD_STRIPE,
                resolutions=(),
                entry_date=DAY,
                posted_at=STATEMENT_AT,
                undeposited_credits=((str(stripe.pk), CARD_STRIPE - Decimal("0.03")),),
            )
        assert "does not foot" in str(refusal.value)
        assert not ledger_models.JournalEntry.objects.filter(
            tenant=brazos, source_type="deposit_batch"
        ).exists()


def test_b10_tc8__a_legacy_member_with_no_entry_falls_back_to_undeposited(brazos, marcus):
    """A payment recorded before the payments→ledger seam existed has no
    journal entry to read a debit from. Its share of the batch credits
    UNDEPOSITED FUNDS — today's behaviour, which for exactly those payments is
    the only lawful answer, because 1010 is where every pre-seam receipt was
    (or was assumed) to be. Reconstructed here by blanking the stamp on an
    UNMAPPED payment whose entry did debit 1010, so the books stay consistent.
    """
    with tenant_ctx(brazos):
        a_cleared_payment(
            marcus, brazos, amount=CASH_COUNTER, method_code="cash", posted_at=POSTED_AT
        )
        # The write-once trigger is Postgres-only (migration 0006); on the
        # sqlite tier this .update() reconstructs the pre-seam shape.
        models.Payment.objects.filter(tenant=brazos).update(journal_entry_id=None)
        reconciliation.cut_deposit_batches(actor=marcus, day=DAY, occurred_at=POSTED_AT)
        # CR-186-BRC10: the payments joined the day's batch at posting.
        (batch,) = the_days_batches(brazos, DAY)
        account = a_bank_account(brazos)
        reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CASH DEPOSIT", str(CASH_COUNTER))]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.reconcile_batch(
            actor=marcus, batch_id=batch.batch_id, posted_at=STATEMENT_AT
        )
        legs = journal_legs(brazos)
        assert leg(legs, "1010", "credit") == CASH_COUNTER


# ═══════════════════════════════════════════════════════════════════════════
# The mirror — BR-LED-003 gives the NSF the right leg for free
# ═══════════════════════════════════════════════════════════════════════════
def test_b10_tc9__an_nsf_on_a_mapped_tender_unwinds_the_mapped_leg(brazos, marcus, dana):
    """`reverse_entry` copies the ORIGINAL with the sides swapped, so a bounce
    on a mapped tender credits 1015 — the account the money actually sat in —
    and never touches 1010 or bank cash. Nothing in the reversal path changed;
    this asserts the property held rather than assuming it."""
    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        recorded = a_cleared_payment(
            marcus, brazos, amount=CARD_STRIPE, method_code="card", posted_at=POSTED_AT
        )

        reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
            idempotency_reference=uuid.uuid4(),
        )

        legs = journal_legs(brazos)
        assert leg(legs, "1015", "debit") == CARD_STRIPE  # the receipt
        assert leg(legs, "1015", "credit") == CARD_STRIPE  # the mirror
        assert leg(legs, "1010", "credit") == Decimal("0")
        assert leg(legs, "1000", "credit") == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# The published read the split is built from
# ═══════════════════════════════════════════════════════════════════════════
def test_b10_tc10__entry_debit_totals_is_tenant_scoped_and_reads_only_what_is_asked(
    brazos, lonestar, marcus
):
    """`apps/ledger/selectors.entry_debit_totals` — CLAUDE.md rule 1 at the new
    read: another tenant's entry ids answer NOTHING under this tenant's
    context, and an id that is not an entry answers nothing rather than
    erroring, because the caller treats absence as the legacy residual."""
    from apps.ledger import selectors as ledger_selectors

    with tenant_ctx(brazos):
        stripe = clearing_account(brazos)
        map_tender(admin(brazos), brazos, "card", stripe.pk)
        recorded = a_cleared_payment(
            marcus, brazos, amount=CARD_STRIPE, method_code="card", posted_at=POSTED_AT
        )
        entry_id = recorded.journal_entry_id
        totals = ledger_selectors.entry_debit_totals([entry_id, str(uuid.uuid4())])
        assert totals == {str(stripe.pk): CARD_STRIPE}
    with tenant_ctx(lonestar):
        assert ledger_selectors.entry_debit_totals([entry_id]) == {}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-008 third set B-10 (12-governance/02-decision-log.md 2026-08-17 rows "the B and C sections ruled" ["10 - A inside CR-008 now"] + "ONE EDITOR for a GL code…" judgment 2 [the measured reason both legs move together] · 12-governance/01-open-questions.md OQ-264 · 11-change-requests.md CR-008 second set §1)
# generated: 2026-08-18 by the CR-008 ledger lane
# checklist: A✔ B✔ C✔ D=n/a(no new endpoint — the write door shipped with CR-008's second set) E=n/a(SET-11 §3 is the screen; its stale sentence is updated with this slice) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED-PROVED FIRST — this whole file was written and run BEFORE the wiring existed: 8 of 10 cases failed (tc1 `assert 0 == Decimal('412.30')` on the 1015 debit; tc5/tc6 crediting 1010 instead of the clearing accounts; tc7 `TypeError: unexpected keyword 'undeposited_credits'`; tc10 `AttributeError: no entry_debit_totals`), quoted in the lane report. tc2/tc8 passed before the change and after it, which is the point of both.
# exceptions: tc8 reconstructs the pre-seam legacy shape with an ORM .update on
#         the sqlite tier — the Postgres write-once trigger (payments 0006)
#         forbids exactly that, which is why the reconstruction uses an
#         UNMAPPED payment so the books it fakes are the books that era had
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
