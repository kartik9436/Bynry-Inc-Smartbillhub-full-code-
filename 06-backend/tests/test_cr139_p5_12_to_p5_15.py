# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, the four TEST rows:
#          `P5.12` *"a payout clears the third state — every payment in it
#          stops reading Awaiting settlement"* · `P5.13` *"the fee tie-out —
#          the balanced pair, with the gross intact. hard rule 5"* · `P5.14`
#          *"a barcode check digit rejects a mis-read, with the worked case in
#          the test"* · `P5.15` *"a scan with no barcode fails visibly rather
#          than silently keying nothing"*.
# Rules:   CLAUDE.md hard rule 2 (money to four decimals, a Decimal and never a
#          float) · hard rule 4 (`OQ-PAY-12608` CLOSED 2026-09-24 option (b) —
#          `payments.settlement_id` is DROPPED (`payments/0044`) and the third
#          state is read from `settlement_members`, as it always was) · hard
#          rule 5 (only the ledger posting service
#          writes journal lines) · hard-won law 7 (every case answers *what
#          would make this pass wrongly*, and the three CONTROL cases below
#          exist because their subjects could otherwise pass by vacuum) ·
#          hard-won law 14 (the tie-out is ALSO run on real PostgreSQL, by
#          `10-scripts/cr139_p5_13_fee_tie_out_proof.py`)
# Tests:   this file. The PostgreSQL half is the script named above.
# ───────────────────────────────────────────────────────
"""Phase 5's four test rows — **and what was already covered before it.**

THE MEASUREMENT, BECAUSE THE BOARD AND THE DISPATCH TABLE DISAGREED
---------------------------------------------------------------------
`CR-139-BRC07` §4 lists all four rows as **NOT STARTED**, and §6 says `P5.14`
and `P5.15` *"landed with their subject"* and that `P5.12` *"is already
asserted"*. Both statements were written the same day by the same lane, and
**§6 is the accurate one for three of the four.** Measured case by case before
a line of this file was written:

  * **`P5.12`** — `test_cr139_p5_6_the_third_state_is_answered_from_the_membership`
    already drives a payout and asserts *3 awaiting → 0 awaiting*. **Covered,
    and with ONE GAP that matters:** every payment it holds is inside the
    payout, so a filter that emptied for EVERYBODY the moment any payout
    existed would pass it unchanged. That is hard-won law 7's *incapable of
    failing* shape wearing a list filter — the exact shape
    `awaiting_settlement_filter`'s own docstring warns about one layer up.
    **This file adds the CONTROL**, and asserts the three by name rather than
    by a count.
  * **`P5.13`** — **NOT covered, and §6 says so in as many words:** *"this lane
    asserted the resolution it produces, not the posting it reaches."*
    `test_cr139_p5_2_a_stated_fee_that_explains_the_gap_becomes_a_resolution`
    stops at the `ResolutionInput`; `test_us_pay_022_tc3__the_card_day_reconciles_net_with_its_fee_as_its_own_line`
    drives the balanced pair end to end but from a **hand-written**
    `ResolutionInput`, so nothing anywhere joins `settlements.stated_processor_fee()`
    to the books. **That join is what this file's `P5.13` section is.**
  * **`P5.14`** — covered by three cases in `test_cr139_p5_remittance.py`, and
    **one half of the task row is missing: *"with the worked case in the
    test"*.** The mis-read is asserted and the arithmetic a reader can follow
    is a TOY payload (`0Z` → `Z`), not the worked line. **This file spells the
    worked line's own sum out**, so the `%` on every printed bill is a figure a
    reviewer can check by hand.
  * **`P5.15`** — the parse half is covered by two cases in the same file.
    **The SCREEN half is not**, and it is another lane's (`P5.8`). What this
    file owns of it is the backend end of the hold: see
    `test_cr139_p5_15_the_scan_card_stays_held_while_our_own_bills_carry_no_bars`.
    The routed-screen half is `07-frontend/src/features/payments/scanSourceIsReachableAndHeld.dom.test.tsx`.

**So: two of the four were already covered, one was covered with a gap, and one
was not covered at all.**

WHERE EACH HALF OF `P5.13` RUNS, AND WHY IT IS TWO PLACES
------------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL` (hard-won law 14). The tie-out's ARITHMETIC — three legs, the
right accounts, debits equal to credits, the payments' own amounts untouched —
is arithmetic and is asserted here. **Hard rule 5 itself is not**, and that is
the half worth naming: on PostgreSQL an INSERT into `journal_entries` that did
not come through `apps/ledger/posting.py::post()` is refused BY NAME, so *only
the ledger posting service writes journal lines* is a database guarantee. The
trigger is installed by a `RunPython` that returns early on any non-PostgreSQL
vendor, so on the suite a second writer is an ordinary INSERT. The same is true
of the append-only trigger on a posted line and of `payments/0005` freezing
`payments.amount` — which is what makes *the gross intact* unbreakable rather
than merely untested. **That half is
`10-scripts/cr139_p5_13_fee_tie_out_proof.py`, run on real PostgreSQL 16.13,
ALL PARTS PASSED, exit 0, in under two seconds.**
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.billing import remittance
from apps.payments import models as payment_models
from apps.payments import reconciliation, settlement_models, settlements

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import (
    a_bank_account,
    a_batch,
    a_statement,
    gl_id,
    journal_legs,
    leg,
)

#: ⚠ **NO MODULE-LEVEL `django_db` MARK.** Four of the cases below read a file
#: on disk or compute a checksum and touch no row; a mark up here would make
#: them pay the test-database build to answer a question about arithmetic. The
#: settlements file keeps the same posture for the same reason.
pytestmark: list = []

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "06-backend"

PROVIDER = "payments_sandbox"
POSTED_AT = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
PAID_OUT_AT = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)

#: The PO's own card day, and the figures every phase-5 document quotes.
CARD_RECORDED = Decimal("5120.40")
CARD_BANKED = Decimal("4972.90")
CARD_FEE = Decimal("147.50")

#: The worked remittance line, spelled here exactly as `remittance.py`'s own
#: docstring and `test_cr139_p5_remittance.py` spell it, so all three move
#: together or one of them goes red.
WORKED_PAYLOAD = "ACC-1042$BL-2608-0117$14218"
WORKED_CHECK = "%"


# ═══════════════════════════════════════════════════════════════════════════
#  P5.12 — a payout clears the third state, AND THE CONTROL THAT MAKES IT MEAN
#          SOMETHING
# ═══════════════════════════════════════════════════════════════════════════
def _account(actor, tenant):
    """One account to hang the payments on.

    Copied from `test_cr139_p5_settlements.py` rather than imported because its
    version is module-private (`_account`), and reaching across test files for
    an underscore name couples two suites through something neither publishes.
    The bank-rec helpers at the top of this file ARE imported, because they are
    public in their module and are the canonical way to cut a deposit batch —
    a second batch builder is exactly the *two answers to one question* the
    blueprint's own risk table warns about.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(
        actor, address_line="1901 Bluestem Ln", services_available=["electric"]
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=f"A-{uuid.uuid4().hex[:8]}",
    )


def _card_payment(tenant, account, *, amount, reference):
    """A cleared card payment carrying the `webhook|<provider>:<event_id>` key
    a payout's members name — the join `settlements._payment_for` makes."""
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        webhook_key=f"webhook|{PROVIDER}:{reference}",
    )


def _payout(**overrides):
    """The three-member payout the phase-5 suite uses everywhere.

    `$100.00 + $60.00 + $40.00 = $200.00` gross, `$5.80` in fees, `$194.20`
    net."""
    kwargs = dict(
        provider=PROVIDER,
        code=f"po_{uuid.uuid4().hex[:10]}",
        paid_out_at=PAID_OUT_AT,
        gross=Decimal("200.0000"),
        fees=Decimal("5.8000"),
        net=Decimal("194.2000"),
        currency="USD",
        members=(
            settlements.PayoutMember("ch_A", Decimal("100.0000"), Decimal("2.9000")),
            settlements.PayoutMember("ch_B", Decimal("60.0000"), Decimal("1.7400")),
            settlements.PayoutMember("ch_C", Decimal("40.0000"), Decimal("1.1600")),
        ),
    )
    kwargs.update(overrides)
    return kwargs


@pytest.fixture()
def three_in_and_one_out(brazos, dana):
    """Three payments the payout names, and **one it does not.**

    ⚠ **THE FOURTH IS THE WHOLE POINT OF THIS FIXTURE.** `ch_D` is a cleared
    card payment of the same tenant, the same day and the same tender, and the
    payout says nothing about it — so it is still awaiting settlement after the
    payout lands, and any answer that says otherwise is wrong in the direction
    a clerk would never notice.
    """
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        rows = {}
        for ref, amount in (
            ("ch_A", "100.0000"),
            ("ch_B", "60.0000"),
            ("ch_C", "40.0000"),
            ("ch_D", "77.0000"),
        ):
            rows[ref] = _card_payment(brazos, account, amount=Decimal(amount), reference=ref)
        return rows


@pytest.mark.django_db
def test_cr139_p5_12_every_payment_in_the_payout_clears_the_third_state_by_name(
    brazos, dana, three_in_and_one_out
):
    """`P5.12`'s own sentence: **every** payment in it stops reading *Awaiting
    settlement* — asserted per payment, not as a total.

    ⚠ **WHAT WOULD MAKE A COUNT PASS WRONGLY.** The existing case
    (`test_cr139_p5_6_the_third_state_is_answered_from_the_membership`) asserts
    `3 → 0` over a tenant whose every payment is in the payout. Two different
    bugs give that same answer: the right one, and a filter that empties for
    everybody once a payout exists. A count cannot tell them apart; naming the
    three can, and the control below closes the other half.
    """
    with tenant_ctx(brazos):
        awaiting = settlements.awaiting_settlement_filter()
        before = set(payment_models.Payment.objects.filter(awaiting).values_list("id", flat=True))
        for ref in ("ch_A", "ch_B", "ch_C", "ch_D"):
            assert three_in_and_one_out[ref].id in before, (
                f"{ref} is not awaiting settlement BEFORE any payout exists, so this case "
                "could never observe the transition it is named for."
            )

        settlements.ingest_payout(actor=dana, **_payout())

        after = set(payment_models.Payment.objects.filter(awaiting).values_list("id", flat=True))
        for ref in ("ch_A", "ch_B", "ch_C"):
            assert three_in_and_one_out[ref].id not in after, (
                f"{ref} is inside the payout and still reads 'Awaiting settlement'. P5.12's "
                "outcome is that EVERY payment in it clears the third state, and it is read "
                "from settlement_members because OQ-PAY-12608 keeps payments.settlement_id "
                "unwritable (hard rule 4)."
            )


@pytest.mark.django_db
def test_cr139_p5_12_control_a_payment_outside_the_payout_is_still_awaiting(
    brazos, dana, three_in_and_one_out
):
    """⚠ **THE CONTROL, AND WITHOUT IT THE CASE ABOVE PROVES ALMOST NOTHING.**

    `awaiting_settlement_filter()` is `~Q(settlement_memberships__isnull=False)`
    — a negation over a reverse relation, which is the shape that most often
    comes back as *"none of them"* rather than *"the ones with no membership"*.
    A filter with that bug clears the third state for the three payments in the
    payout **and for every other payment in the product**, and the count-based
    case reads `0` and goes green.

    `ch_D` is the same tenant, the same tender and the same day, and the payout
    does not name it. It must still be awaiting afterwards, and the awaiting set
    must be **exactly** `{ch_D}` — which pins the answer in both directions at
    once.
    """
    with tenant_ctx(brazos):
        settlements.ingest_payout(actor=dana, **_payout())
        awaiting = set(
            payment_models.Payment.objects.filter(
                settlements.awaiting_settlement_filter()
            ).values_list("id", flat=True)
        )
        assert awaiting == {three_in_and_one_out["ch_D"].id}, (
            "the awaiting-settlement set should be exactly the ONE payment the payout did "
            f"not name. It is {len(awaiting)} row(s). A set that came back empty is the "
            "filter answering 'none of them' — hard-won law 7's incapable-of-failing shape, "
            "and it is invisible to a case whose every payment is inside the payout."
        )


@pytest.mark.django_db
def test_cr139_p5_12_the_membership_is_what_moved_and_the_pointer_did_not(
    brazos, dana, three_in_and_one_out
):
    """The third state moved **without a single payment row being written.**

    ⚠ **`OQ-PAY-12608` CLOSED 2026-09-24 AND `payments.settlement_id` IS
    DROPPED** (`payments/0044`). PO, verbatim: *"p7 (b) — nothing is lost, and
    the payment-row lock stays exactly as it is"*. The pointer could not be
    written in ANY status — hard rule 4's trigger freezes a column from the
    day it is created — so the PO removed it rather than widening the lock.

    ⛔ **SUPERSEDED — what this case used to assert.** It read back
    `row.settlement_id is None` on all four payments. There is no such
    attribute now, so that loop would RAISE rather than fail, which is why it
    is rewritten rather than left. What it was really guarding is kept and is
    wider: **an ingest writes no payment row at all**, asserted against
    `updated_at` and `status` instead of against one column that has gone. A
    future lane that "fixes" the filter by writing payment rows breaks this,
    which is the correct outcome.
    """
    with tenant_ctx(brazos):
        before = {}
        for ref in ("ch_A", "ch_B", "ch_C", "ch_D"):
            row = three_in_and_one_out[ref]
            row.refresh_from_db()
            before[ref] = (row.updated_at, row.status)
        settlements.ingest_payout(actor=dana, **_payout())
        for ref in ("ch_A", "ch_B", "ch_C", "ch_D"):
            row = three_in_and_one_out[ref]
            row.refresh_from_db()
            assert (row.updated_at, row.status) == before[ref], (
                f"{ref} was written by ingest_payout. A payout touches NO payment row — "
                "hard rule 4 freezes them, and OQ-PAY-12608 (2026-09-24) removed the one "
                "column the blueprint asked to stamp rather than widening that lock."
            )
        members = settlement_models.SettlementMember.objects.all()
        assert members.count() == 3, "the payout's record is its membership, and it has three"


# ═══════════════════════════════════════════════════════════════════════════
#  P5.13 — the fee tie-out, from the STATED fee all the way into the books
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr139_p5_13_the_stated_fee_ties_out_into_the_balanced_pair(brazos, marcus):
    """**The join nothing in the repo made: `stated_processor_fee` → the books.**

    The PO's card day, driven end to end. We record **5,120.40**, the bank
    credits **4,972.90**, and the payout STATES the provider kept **147.50**:

        DR 1000 Cash               4,972.90   ← what the bank actually credited
        DR 6800 Bank fees            147.50   ← the fee, ITS OWN LINE
        CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

    ⚠ **THE FEE'S AMOUNT COMES FROM THE PAYOUT AND NOT FROM THE GAP.** That is
    `OQ-160`'s option (c) and the whole reason `P5.2` exists: derived from the
    shortfall, a customer chargeback hiding inside the difference reconciles
    clean forever. The figure is therefore READ off the settlement row here and
    is never written into the call by this test.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, AND IT IS WHY THE RESOLUTION IS NOT
    HAND-WRITTEN.** `test_us_pay_022_tc3` asserts these same three legs from a
    `ResolutionInput` the test composed itself — so it holds whether or not
    `stated_processor_fee` exists, whether or not it returns the right reason
    code, and whether or not its sign is the one `reconcile_batch` expects. The
    only thing this case adds is the JOIN, and the join is the thing `P5.13`
    names.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("3000.00"), Decimal("2120.40")),  # Σ = 5,120.40
            method_code="card",
            day=date(2026, 8, 4),
        )
        assert batch.recorded_total == CARD_RECORDED

        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 6),
            payload=a_statement([("2026-08-04", "CARD SETTLEMENT", "4972.90")]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )

        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_20260804_card",
            paid_out_at=PAID_OUT_AT,
            gross=CARD_RECORDED,
            fees=CARD_FEE,
            net=CARD_BANKED,
        )
        resolution = settlements.stated_processor_fee(
            settlement,
            recorded_total=CARD_RECORDED,
            bank_total=CARD_BANKED,
            gl_account_id=gl_id(brazos, "bank_fees"),
        )
        # The figure reached the resolution from the PAYOUT, not from the gap.
        assert resolution.amount == -CARD_FEE
        # ⚠ **THE LITERAL, NOT `settlements.REASON_PROCESSOR_FEE`.** The first
        # draft of this line compared the constant with itself, which is true of
        # ANY value the constant holds — proved by re-spelling it `"bank_fee"`
        # and watching all three P5.13 cases stay green. `processor_fee` is a
        # row on the TENANT'S own difference-reason list, which is what
        # `reconcile_batch._canonical_reason` resolves against, so the literal
        # is the only spelling that pins the vocabulary rather than the symbol.
        assert resolution.reason_code == "processor_fee"

        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=STATEMENT_AT,
            resolutions=(resolution,),
        )
        assert result.bank_total == CARD_BANKED
        assert result.recorded_total == CARD_RECORDED
        assert result.explained == -CARD_FEE

        legs = journal_legs(brazos)
        assert leg(legs, "1000", "debit") == CARD_BANKED, "cash is the NET the bank credited"
        assert leg(legs, "6800", "debit") == CARD_FEE, "the fee is its own line, never netted"
        assert leg(legs, "1010", "credit") == CARD_RECORDED, "the GROSS the receipts debited"
        debits = sum(amount for _code, side, amount in legs if side == "debit")
        credits = sum(amount for _code, side, amount in legs if side == "credit")
        assert debits == credits, "hard rule 5 — a posted entry balances to the cent"


@pytest.mark.django_db
def test_cr139_p5_13_the_gross_is_intact_no_payment_was_netted_down(brazos, marcus):
    """**`P5.13`'s second clause, and the money error the whole phase exists to
    prevent: *with the gross intact*.**

    A $100.00 card payment with a $2.90 fee is **a $100.00 payment and a $2.90
    expense** — never a $97.10 payment. Netting it down makes the customer's
    account short by the fee and ties the trial balance to the wrong number.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY: asserting only the ledger.** The
    three legs above are correct in a build that ALSO rewrote each payment row
    to its net — the books would still balance, because the credit to 1010
    comes from the batch's frozen `recorded_total` rather than from the
    payments. So this case reads the payment rows themselves, after the
    reconcile, and adds them up.
    """
    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("3000.00"), Decimal("2120.40")),
            method_code="card",
            day=date(2026, 8, 4),
        )
        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 6),
            payload=a_statement([("2026-08-04", "CARD SETTLEMENT", "4972.90")]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_20260804_gross",
            paid_out_at=PAID_OUT_AT,
            gross=CARD_RECORDED,
            fees=CARD_FEE,
            net=CARD_BANKED,
        )
        reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=STATEMENT_AT,
            resolutions=(
                settlements.stated_processor_fee(
                    settlement,
                    recorded_total=CARD_RECORDED,
                    bank_total=CARD_BANKED,
                    gl_account_id=gl_id(brazos, "bank_fees"),
                ),
            ),
        )

        amounts = sorted(
            payment_models.Payment.objects.filter(
                tenant=brazos, deposit_batch_id=batch.batch_id
            ).values_list("amount", flat=True)
        )
        assert amounts == [Decimal("2120.4000"), Decimal("3000.0000")], (
            f"the batch's payments read {amounts}. A fee is the utility's cost of collecting "
            "the money, not a reduction of what the customer paid — netting a payment down "
            "leaves that customer's account short by the fee for ever."
        )
        assert sum(amounts) == CARD_RECORDED, "Σ payments must still be the GROSS"


@pytest.mark.django_db
def test_cr139_p5_13_the_entry_is_the_deposit_batchs_and_settlements_wrote_none(brazos, marcus):
    """**Hard rule 5 — *only the ledger posting service writes journal lines* —
    checked behaviourally rather than only structurally.**

    `test_cr139_p5_2_nothing_in_this_module_writes_a_journal_line` asserts an
    ABSENCE over `settlements.py`'s import graph. That is the right check and it
    cannot see the thing this one can: **which posting actually produced the
    lines.** A second writer that reached the ledger through some other module
    would leave the import graph clean and would still post the money twice —
    §2.3's *two answers to one question*, on the money path.

    So: after a payout's fee ties out, every posted entry of this tenant is the
    **deposit batch's**, and its source id is this batch. There is no settlement
    entry because `settlements.py` posts nothing at all.
    """
    from apps.ledger import models as ledger_models
    from apps.payments import ledger_seam

    with tenant_ctx(brazos):
        batch = a_batch(
            marcus,
            brazos,
            amounts=(Decimal("3000.00"), Decimal("2120.40")),
            method_code="card",
            day=date(2026, 8, 4),
        )
        account = a_bank_account(brazos)
        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account.pk,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 6),
            payload=a_statement([("2026-08-04", "CARD SETTLEMENT", "4972.90")]),
            imported_at=STATEMENT_AT,
        )
        reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=STATEMENT_AT,
        )
        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_20260804_writer",
            paid_out_at=PAID_OUT_AT,
            gross=CARD_RECORDED,
            fees=CARD_FEE,
            net=CARD_BANKED,
        )
        # ⚠ **AN ID SET, NOT A COUNT.** Recording the two card payments already
        # posted their own `payment` entries, so "every entry of this tenant is
        # the batch's" is false and a count would only say how MANY arrived.
        # The question is which ones the RECONCILE wrote.
        before = set(
            ledger_models.JournalEntry.objects.filter(tenant=brazos).values_list("id", flat=True)
        )
        reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=STATEMENT_AT,
            resolutions=(
                settlements.stated_processor_fee(
                    settlement,
                    recorded_total=CARD_RECORDED,
                    bank_total=CARD_BANKED,
                    gl_account_id=gl_id(brazos, "bank_fees"),
                ),
            ),
        )
        written = list(
            ledger_models.JournalEntry.objects.filter(tenant=brazos).exclude(id__in=before)
        )
        assert written, "the reconcile posted no entry at all"
        for entry in written:
            assert entry.source_type == ledger_seam.SOURCE_DEPOSIT_BATCH, (
                f"an entry of source_type {entry.source_type!r} appeared when a payout's fee "
                "tied out. The reconcile is the ONE posting on this path; a second one posts "
                "the same money twice and the trial balance is where it shows up."
            )
            assert str(entry.source_id) == str(batch.batch_id)


# ═══════════════════════════════════════════════════════════════════════════
#  P5.14 — the check digit, WITH THE WORKED CASE'S ARITHMETIC ON THE PAGE
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_14_the_worked_lines_own_mod_43_sum_is_written_out():
    """`P5.14`'s second clause: *"with the worked case in the test"* — **the
    arithmetic, not just the answer.**

    Every document in this phase quotes `ACC-1042$BL-2608-0117$14218%` and none
    of them shows where the `%` comes from. `test_cr139_p5_10_the_worked_line_is_exactly_this`
    pins the literal and `test_cr139_p5_14_the_check_is_mod_43_and_not_luhn`
    works a TOY payload (`0Z` → `Z`). Neither lets a reviewer check the `%` on a
    real printed bill by hand, which is what this case is for.

    **The sum, symbol by symbol, in Code 39's own alphabet (index IS value):**

        A=10  C=12  C=12  -=36  1=1  0=0  4=4  2=2           Σ  77
        $=39                                                 Σ 116
        B=11  L=21  -=36  2=2  6=6  0=0  8=8  -=36           Σ 236
        0=0  1=1  1=1  7=7                                   Σ 245
        $=39                                                 Σ 284
        1=1  4=4  2=2  1=1  8=8                              Σ 300

        300 mod 43 = 300 − (6 × 43) = 300 − 258 = 42
        ALPHABET[42] = '%'

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY: calling `check_character` and
    comparing it with itself.** So the total is computed here from the literal
    43-symbol alphabet, by a loop this file owns, and only then compared with
    the module's answer. The two arithmetics are independent; if they ever
    disagree, one of them is wrong and the test says which figure it expected.
    """
    total = sum(remittance.ALPHABET.index(symbol) for symbol in WORKED_PAYLOAD)
    assert total == 300, f"the worked line's symbol values sum to {total}, not 300"
    assert total % 43 == 42
    assert remittance.ALPHABET[42] == WORKED_CHECK
    assert remittance.check_character(WORKED_PAYLOAD) == WORKED_CHECK
    assert WORKED_PAYLOAD + WORKED_CHECK == remittance.compose(
        account_no="ACC-1042", invoice_no="BL-2608-0117", amount=Decimal("142.18")
    )


def test_cr139_p5_14_control_the_mis_read_moves_the_sum_by_exactly_one():
    """⚠ **THE CONTROL: the arithmetic above must also EXPLAIN the refusal.**

    `ACC-1042` mis-read as `ACC-1043` changes one symbol from `2` (value 2) to
    `3` (value 3), so the sum goes `300 → 301`, `301 mod 43 = 43 × 7 = 301` →
    `0`, and the expected check becomes `ALPHABET[0]` = `'0'`. The line still
    carries `%`, so it is refused.

    **That is why a mis-read fails visibly**, and it is stated as a figure so a
    reader can see that the check character is doing work rather than being
    decoration. `test_cr139_p5_14_one_wrong_character_is_refused` asserts the
    refusal; this asserts the reason for it.
    """
    misread = WORKED_PAYLOAD.replace("ACC-1042", "ACC-1043")
    total = sum(remittance.ALPHABET.index(symbol) for symbol in misread)
    assert total == 301
    assert total % 43 == 0
    assert remittance.check_character(misread) == "0" != WORKED_CHECK
    assert remittance.verify(misread + WORKED_CHECK) is False


# ═══════════════════════════════════════════════════════════════════════════
#  P5.15 — a scan with no barcode fails visibly, AND THE HOLD THAT SAYS SO
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_15_the_scan_card_is_live_now_that_our_own_bills_carry_bars():
    """⏳→✅ **THIS WAS THE HOLD. IT EXPIRED ON 2026-09-23 AND IS NOW INVERTED.**

    It read `..._stays_held_while_our_own_bills_carry_no_bars` and asserted the
    opposite of both lines below: that `documents.py` did NOT call
    `remittance.bars(`, and that `SCAN_PAPER_CARD` read `available: false`. It
    was right on the day it was written, it went red on the day the bars were
    drawn, and it named the four things that had to move together.

    **They moved, in this order, and the ORDER was the whole job.** The PO said
    *"please enable it and also start putting bar code on bills"* — enable
    first, bars second. Built that way round it would have shipped a live Scan
    input over a bill with nothing on it to scan, which is precisely the silent
    failure `P5.15` is named for. So the BARS landed first (`DEF-BIL-6325`,
    decode-proved by `tests/test_def_bil_6325_barcode_round_trip.py`), and the
    card was released only afterwards.

    ⚠ **THE TWO ASSERTIONS STILL TRAVEL TOGETHER, WHICH IS WHY THIS IS ONE CASE
    AND NOT TWO.** The property worth holding is not *the card is on* — it is
    **the card is on if and only if our own paper can be scanned**. Split them
    and a lane that removes the bars leaves a live control over a door onto
    nothing, with the card's own test still green.
    """
    documents = (BACKEND / "apps" / "billing" / "documents.py").read_text()
    kinds = (REPO / "07-frontend" / "src" / "components" / "workflow" / "kinds.ts").read_text()

    bars_are_drawn = "remittance.bars(" in documents
    # ⚠ **LOCATED POSITIVELY, BECAUSE A `split()` ON A MISSING ANCHOR RAISES
    # `IndexError` AND A READER MEETS A STACK TRACE INSTEAD OF A SENTENCE.**
    # Proved by renaming the constant: this line now names what moved.
    assert "const SCAN_PAPER_CARD" in kinds, (
        "kinds.ts no longer declares `SCAN_PAPER_CARD`. This case reads that constant to "
        "decide whether the Scan paper card is live; renaming it moves the question "
        "somewhere nothing is watching. Re-point this case at the new name."
    )
    card = kinds.split("const SCAN_PAPER_CARD")[1].split("};")[0]
    # ⚠ **COMMENT LINES ARE STRIPPED, AND THIS COST A RED BEFORE IT WAS
    # NOTICED.** The `unavailable_reason_key` assertion below reads SOURCE
    # TEXT, and the card's own comment explains that it deliberately has no
    # `unavailable_reason_key` — so the check failed on the sentence saying it
    # passed. A grep over source that prose can trip is a check looking at the
    # wrong thing (hard-won law 7); it must read CODE.
    code = "\n".join(
        line for line in card.splitlines() if not line.strip().startswith("//")
    )
    card_is_live = "available: true" in code

    assert bars_are_drawn, (
        "`documents.py` no longer calls `remittance.bars(...)`, so our own printed bill "
        "carries no scannable symbol — and the Scan paper card is live over it. A clerk "
        "points a scanner at one of our bills and gets NOTHING, which is the silent "
        "failure P5.15 is named for. Put the bars back, or put the card back."
    )
    assert card_is_live, (
        "our bills carry scannable bars and the Scan paper card is refused, so a clerk "
        "is being told to type what a scanner could read. If the card was held back "
        "deliberately, say why here — a refusal whose stated reason has stopped being "
        "true is what sends the next lane to release it for the wrong reason "
        "(DEF-PAY-6274)."
    )
    assert "unavailable_reason_key" not in code, (
        "the card is available AND still names a reason it is not. BR-SHL-025 puts a "
        "reason on a control that cannot be honoured; on one that can, it is a sentence "
        "a clerk reads and disbelieves."
    )


def test_cr139_p5_15_control_this_case_can_see_both_of_its_own_subjects():
    """⚠ **A CHECK OVER TWO FILES IT LOCATES BY PATH CAN REPORT *ALL WELL* BY
    FINDING NEITHER** — hard-won law 7's *reporting zero over a scope it
    silently excludes*, and CLAUDE.md's own eighth occurrence of it.

    If either file is moved or renamed, `read_text()` raises and the case above
    errors rather than passing — but the `split()` on `SCAN_PAPER_CARD` would
    hand back an empty string for a renamed constant and `available: false`
    would simply not be found, which reads as a FAILURE rather than as a miss.
    The dangerous direction is the other one: a `documents.py` that no longer
    mentions bars because the whole renderer moved. So both subjects are
    located positively here, with a figure beside each.
    """
    documents = (BACKEND / "apps" / "billing" / "documents.py").read_text()
    kinds = (REPO / "07-frontend" / "src" / "components" / "workflow" / "kinds.ts").read_text()
    assert "remittance" in documents and len(documents) > 10_000, (
        "apps/billing/documents.py no longer mentions the remittance stub — the hold above "
        "is reading a file that has stopped being its subject."
    )
    assert kinds.count("const SCAN_PAPER_CARD") == 1, (
        "SCAN_PAPER_CARD is not declared exactly once in kinds.ts, so the hold above is "
        "slicing the wrong text and could pass over a card that went live."
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 `P5.12` `P5.13` `P5.14` `P5.15` (05-prototype/06 Payments Page Blueprint.pdf pp.23–25 · 12-governance/01-open-questions.md OQ-PAY-12608 OPEN · OQ-144 CLOSED 2026-08-11 · OQ-160 CLOSED 2026-08-12 · CLAUDE.md hard rules 2/4/5 + hard-won laws 2/7/14)
# generated: 2026-09-23 by LANE P5-TESTS
# checklist: A=n/a(tests) B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · PROVED RED: each case was broken on its own subject before being trusted green — see the CR's §5b
# exceptions: the PostgreSQL half of `P5.13` is `10-scripts/cr139_p5_13_fee_tie_out_proof.py`, because config/settings/test.py hardcodes SQLite (hard-won law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
