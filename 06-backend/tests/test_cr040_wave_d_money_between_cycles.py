# ── Trace ──────────────────────────────────────────────
# Story:    CR-040 wave D tasks D12 · D13 · D14 · D15 (the money cases that did
#           not exist)   Screens: S58 (refund) · S30 (correction case) · S8
# Rules:    BR-PAY-014 (a refund is requested → approved → issued, and only a
#           REAL credit funds it) · BR-BIL-041/042 (the operator picks the
#           REASON; the class DERIVES the mechanism) · BR-BIL-048 (one open
#           case per chain) · BR-MET-053 (a BILLED read is corrected only
#           through `correct_billed_read`) · BR-TEN-063 (idempotent) ·
#           CLAUDE.md hard rule 4 (append-only)
# Tests:    this file
# Impacts:  apps/payments/sample_data.seed_sample_refund ·
#           apps/billing/sample_data.seed_sample_correction ·
#           apps/tenancy/sample_data.SAMPLE_MODULES (the position IS the task)
# ───────────────────────────────────────────────────────
"""CR-040 wave D — spec §4 cases 14 and 15, and the GAP they live in.

WHY THIS IS NOT A COUNT
-----------------------
Task D14 is the requirement and it is a POSITION, not a content: *"a refund
written after both runs is a row; a refund written between them is a HISTORY"*.
Both orderings write **exactly the same rows**, so a test that counted refunds
would pass over a tree where the blocks had been moved beside the payments
block or after the second cycle — which is the one failure this wave exists to
prevent.

⚠ **THE CLOCK IS `created_at`, AND `test_cr040_two_cycles.py` RECORDS WHY** —
its own first version compared `Payment.received_at` against `Invoice.issued_at`
and failed against a tree where the ordering was CORRECT, because those are
back-dated business dates the fixture chooses. This file inherits that lesson
and has a sharper version of the same trap: the refund and the correction are
dated in **July**, while the payments block above them is dated on the busy day
in **August**. On business dates these rows look EARLIER than the payments that
fund them. `created_at` (`auto_now_add`) is the only field that records the
block order, because it is the only one the fixture does not get to choose.

NON-VACUOUS, IN DEF-466's AND DEF-828's SHAPE
----------------------------------------------
Every presence assertion below comes with the thing that stops it passing over
an empty estate — a refund that exists but never issued, a correction case that
exists with no bill pinned to it, an ordering that holds because nothing was
written on either side of it. DEF-828's guard is the model: it asks *is
anything EXPOSED* rather than *did my rows land*.

RED-FIRST RECORD (hard-won law 7): see the lane report for the verbatim
failures. Each test was run against the tree before its block was wired into
`SAMPLE_MODULES`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.billing import correction_models
from apps.billing import models as billing_models
from apps.payments import models as payment_models
from apps.tenancy import sample_data
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _real_admin(tenant):
    """An actor whose id resolves to a real user row.

    Same helper and same reason as `test_cr040_two_cycles.py`: BR-BIL-058's
    fifth fact is WHO authorised the run, and `approve_refund` is
    `@require_role(SYSTEM_ADMIN)` on the SERVICE — a namespace with a random
    uuid gets past neither.
    """
    from apps.identity import models as identity_models

    user = identity_models.User.objects.filter(
        tenant=tenant, email="demo.owner@example.invalid"
    ).first() or identity_models.User.objects.create(
        tenant=tenant, email="demo.owner@example.invalid", full_name="Demo Owner"
    )
    return SimpleNamespace(id=user.id, role="system_admin")


def _seeded():
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(_real_admin(tenant))
    return tenant


def _second_cycle_first_write():
    """When the SECOND cycle's first bill row was written — not issued."""
    july = next(p for p in fixture.PERIODS if p["key"] == "july")
    return (
        billing_models.Invoice.objects.filter(
            bill_run__period_start=july["start"],
            bill_run__period_end=july["end"],
            status="issued",
        )
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )


def _first_cycle_first_write():
    june = next(p for p in fixture.PERIODS if p["key"] == "june")
    return (
        billing_models.Invoice.objects.filter(
            bill_run__period_start=june["start"],
            bill_run__period_end=june["end"],
        )
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )


# ══════════════════════════════════════════════════════════════════════════
# D12 — spec §4 case 14: money going OUT
# ══════════════════════════════════════════════════════════════════════════


def test_d12__the_seeded_tenant_has_paid_one_customer_back():
    """*"Every case above moves money in or holds it; nothing in this fixture
    has ever paid a customer back"* (spec §4 case 14).

    All four steps, not just the row: a refund that stopped at REQUESTED would
    satisfy "a refund exists" and would have moved no money, posted nothing and
    demonstrated neither the approval gate nor the cheque clearing.
    """
    tenant = _seeded()
    with tenant_ctx(tenant):
        refunds = list(payment_models.Refund.objects.filter(tenant_id=tenant.id))

    assert len(refunds) == 1, f"expected exactly one seeded refund, found {len(refunds)}"
    refund = refunds[0]
    assert refund.status == payment_models.REFUND_CLEARED, (
        f"the seeded refund is {refund.status!r}: it was not driven through all four steps, so "
        "the demo shows a refund that never left the building"
    )
    assert refund.amount > 0
    assert refund.currency == "USD"
    # THE MONEY ACTUALLY MOVED. A refund marked issued with nothing in the books
    # is the unrepairable state `issue_refund`'s own docstring names.
    assert refund.journal_entry_id is not None, (
        "the refund carries no journal entry — it was marked issued without posting, which "
        "is money out of the customer's credit and nothing in the ledger"
    )
    # Every step is dated, because BR-PAY-037 records both acts distinctly and
    # a refund with no approval date cannot say which signature it ran under.
    assert refund.requested_at is not None
    assert refund.approved_at is not None
    assert refund.issued_at is not None
    assert refund.cleared_at is not None


def test_d12__the_refund_is_on_its_own_account_and_not_on_case_11s():
    """⚠ **CASE 11 MUST SURVIVE CASE 14.**

    A refund CONSUMES a credit. Seeding it onto `CASE_CREDIT_BALANCE` would pay
    case 11 out — one case replacing another rather than a case being added,
    which no count of "how many awkward cases do we have" could see.

    This asserts the thing this lane controls: WHICH ACCOUNT the refund is on.
    Whether case 11 still shows a credit at the end of the load is a separate
    question with a separate answer — see `test_def931__…` below, which is
    where it is pinned, because the answer today is NO and the reason is not
    this refund.
    """
    from apps.customers import sample_data as customers_sample

    tenant = _seeded()
    with tenant_ctx(tenant):
        ids = customers_sample.sample_account_ids()
        refund = payment_models.Refund.objects.filter(tenant_id=tenant.id).first()
        refund_account = refund.payment.account_id if refund else None
        expected = ids[fixture.CASE_REFUND]
        credit_case_account = ids[fixture.CASE_CREDIT_BALANCE]

    assert refund is not None, "no refund was seeded — this test would pass vacuously"
    assert str(refund_account) == str(expected), "the refund is not on CASE_REFUND's account"
    assert str(refund_account) != str(credit_case_account), (
        "the refund was seeded onto the credit-balance account, which pays case 11 out "
        "instead of adding case 14"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEF-931 — the seeded credit-balance account holds NO credit once the load "
        "finishes. `apply_credit_at_issue` (BR-PAY-010) spends a carried credit on the "
        "next bill that issues, and CR-040 wave C made July a bill that issues. Correct "
        "product behaviour; the FIXTURE no longer demonstrates spec §4 case 11"
    ),
)
def test_def931__the_carried_credit_case_still_carries_a_credit():
    """⚠ **THIS TEST IS EXPECTED TO FAIL, AND THAT IS THE POINT.**

    Spec §4 case 11: *"1 credit balance from an overpayment — a negative-owing
    account renders sanely"*. It stopped being true the day the fixture started
    billing a second cycle: `apps/billing/issue.py` calls
    `payments_seam.apply_credit_at_issue` on every bill it issues, and
    BR-PAY-010 is exactly that a credit is what the next bill is for. So the
    overpayment made in June is spent on the July bill, and the demo's accounts
    list shows no account in credit at all.

    **Measured block by block on a real seeded tenant, which is what makes the
    cause certain rather than plausible: immediately BEFORE the second billing
    block that account's credit position is $17.08, and immediately after the
    whole load it is $0.00.** Nothing else in the load touches it.

    **Nothing here is broken.** The product does the right thing, the spec
    describes something the fixture no longer produces, and the fix is a
    FIXTURE FIGURE — case 11's overpayment has to be big enough to survive the
    July bill as well as the June one. That is a demo-shape judgment on a case
    the spec names, so this lane filed it (DEF-931) rather than picking a new
    multiplier: changing it moves the fixture's stated collection rate.

    ⚠ **`strict=True` IS THE RATCHET.** The day someone raises that figure this
    test XPASSes, `strict` turns an unexpected pass into a FAILURE, and whoever
    fixed it is told to delete this marker. An xfail that quietly starts
    passing is a defect nobody closes.
    """
    from apps.customers import sample_data as customers_sample
    from apps.payments import selectors as payment_selectors

    tenant = _seeded()
    with tenant_ctx(tenant):
        ids = customers_sample.sample_account_ids()
        carried = payment_selectors.account_credit_position(ids[fixture.CASE_CREDIT_BALANCE])

    assert carried > 0, (
        f"spec §4 case 11's account carries {carried}, not a credit — the second billing "
        "cycle spent it at issue (DEF-931)"
    )


# ══════════════════════════════════════════════════════════════════════════
# D13 — spec §4 case 15: an overcharge, corrected
# ══════════════════════════════════════════════════════════════════════════


def test_d13__one_issued_bill_was_restated_downward():
    """The corrections engine, driven for the first time by a fixture.

    ⚠ **DOWNWARD, and that is the whole case.** An overcharge corrected must
    move the customer's balance in their favour; a correction whose delta is
    zero or positive is a different story wearing this one's label.
    """
    tenant = _seeded()
    with tenant_ctx(tenant):
        cases = list(correction_models.CorrectionCase.objects.filter(tenant_id=tenant.id))
        rows = list(correction_models.CorrectionCaseBill.objects.filter(tenant_id=tenant.id))

    assert len(cases) == 1, f"expected exactly one seeded correction case, found {len(cases)}"
    case = cases[0]
    assert case.correction_class == correction_models.CLASS_RESTATEMENT
    assert case.reason_codes == [fixture.OVERCHARGE["reason_code"]]
    assert case.status == correction_models.CASE_DONE, (
        f"the case is {case.status!r}: it was opened and never executed, so no credit note and "
        "no rebill exist and the demo shows a correction nobody made"
    )
    assert case.approved_on is not None, "nothing executes without a recorded approval"

    # NON-VACUITY: a case with no bill pinned to it satisfies every assertion
    # above and corrects nothing.
    assert len(rows) == 1, f"the case pins {len(rows)} bill(s)"
    row = rows[0]
    assert row.delta_amount < 0, (
        f"the correction moved the bill by {row.delta_amount}, which is not a customer being "
        "given money back. Spec §4 case 15 is an OVERCHARGE corrected"
    )
    assert row.credit_note_id is not None, "no credit note was issued"
    assert row.rebill_invoice_id is not None, "no rebill was issued"


def test_d13__the_reading_underneath_was_superseded_through_meterings_own_door():
    """BR-MET-053: *"read fix and money fix travel together"*.

    A class-R restatement RE-PRICES from today's inputs, so a correction with
    nothing changed underneath it computes a delta of exactly zero. The read
    correction is therefore not decoration — it is the mechanism, and it is
    checked as one.
    """
    from apps.metering import selectors as metering_selectors

    tenant = _seeded()
    with tenant_ctx(tenant):
        row = correction_models.CorrectionCaseBill.objects.filter(tenant_id=tenant.id).first()
        assert row is not None
        linkages = metering_selectors.read_corrections_for_invoice(row.invoice_id)

    assert linkages, (
        "no `read_corrections` row names this bill, so the delta above came from somewhere "
        "other than a corrected reading — which for a class-R case means it came from nowhere"
    )


# ══════════════════════════════════════════════════════════════════════════
# D14 — THE POSITION. Both orderings write the same rows.
# ══════════════════════════════════════════════════════════════════════════


def test_d14__the_refund_and_the_correction_are_written_between_the_two_runs():
    """⚠ **THE ASSERTION THE WHOLE WAVE IS FOR.**

    Two bounds, and both are needed:

      * AFTER cycle one — an overcharge correction cannot exist before the bill
        it corrects has issued, and a refund cannot exist before the
        overpayment that funds it;
      * BEFORE cycle two — a refund or correction written after run 2 is a row
        rather than a history, and the second cycle would then bill an estate
        that had never been credited, refunded or corrected.
    """
    tenant = _seeded()
    with tenant_ctx(tenant):
        first_cycle = _first_cycle_first_write()
        second_cycle = _second_cycle_first_write()
        refund = payment_models.Refund.objects.filter(tenant_id=tenant.id).first()
        case = correction_models.CorrectionCase.objects.filter(tenant_id=tenant.id).first()

    # NON-VACUITY, on both sides: with nothing seeded, every comparison below
    # would be vacuously true or would raise rather than fail informatively.
    assert first_cycle is not None, "cycle one wrote no bill — this test would be meaningless"
    assert second_cycle is not None, "cycle two wrote no bill — this test would pass vacuously"
    assert refund is not None, "no refund was seeded"
    assert case is not None, "no correction case was seeded"

    assert first_cycle < case.created_at, (
        "the correction case was written BEFORE the first cycle's bills — a correction "
        "corrects a bill that has issued, so this fixture is describing something that "
        "cannot have happened"
    )
    assert refund.created_at < second_cycle, (
        "the refund was written AFTER the second cycle's bills. The rows are identical either "
        "way; what is lost is that cycle two bills an estate that has been refunded — which is "
        "the one thing CR-040 wave C split the billing block to make possible"
    )
    assert case.created_at < second_cycle, (
        "the correction was written AFTER the second cycle's bills, so the second cycle bills "
        "an account that had not yet been corrected"
    )


def test_d14__sample_modules_puts_both_blocks_inside_the_gap():
    """The tuple, as well as the consequence.

    Asserted alongside the `created_at` test above rather than instead of it:
    the tuple can be right while a block silently writes nothing (DEF-167's
    shape), and the rows can be in the right order for a reason that is not the
    block order. Neither test alone says what both say together.
    """
    seams = [(block.module, block.seam) for block in sample_data.SAMPLE_MODULES]
    first_cycle = seams.index(("billing", "seed_sample_records"))
    payments = seams.index(("payments", "seed_sample_records"))
    refund = seams.index(("payments", "seed_sample_refund"))
    correction = seams.index(("billing", "seed_sample_correction"))
    second_cycle = seams.index(("billing", "seed_sample_second_cycle"))

    assert first_cycle < payments < refund < second_cycle
    assert first_cycle < correction < second_cycle


# ══════════════════════════════════════════════════════════════════════════
# D15 — the guards' own guarantee: a replay changes nothing
# ══════════════════════════════════════════════════════════════════════════


def test_d15__a_replay_refunds_nothing_twice_and_corrects_nothing_twice():
    """BR-TEN-063 on both new seams.

    ⚠ **BOTH RETURN 0 AND BOTH COUNTS ARE UNCHANGED**, because either one alone
    can lie: a seam that returned 0 while writing a second row would pass the
    first check, and a seam that wrote nothing at all would pass the second.
    """
    from apps.billing import sample_data as billing_sample
    from apps.payments import sample_data as payments_sample

    tenant = _seeded()
    with tenant_ctx(tenant):
        admin = _real_admin(tenant)
        before = (
            payment_models.Refund.objects.filter(tenant_id=tenant.id).count(),
            correction_models.CorrectionCase.objects.filter(tenant_id=tenant.id).count(),
            correction_models.CorrectionCaseBill.objects.filter(tenant_id=tenant.id).count(),
        )
        replayed_refund = payments_sample.seed_sample_refund(admin)
        replayed_correction = billing_sample.seed_sample_correction(admin)
        after = (
            payment_models.Refund.objects.filter(tenant_id=tenant.id).count(),
            correction_models.CorrectionCase.objects.filter(tenant_id=tenant.id).count(),
            correction_models.CorrectionCaseBill.objects.filter(tenant_id=tenant.id).count(),
        )

    assert before == (1, 1, 1), f"the first load did not seed one of each: {before}"
    assert replayed_refund == 0, "a replay recorded a second refund"
    assert replayed_correction == 0, "a replay opened a second correction case"
    assert before == after, f"a replay changed the counts: {before} -> {after}"


# ⚠ **THE SEAM-RESOLUTION GUARD IS NOT HERE, AND THE REASON IS A CORRECTION TO
# THIS LANE'S OWN DEFECT ROW (DEF-930).** Both wave-D blocks were silently
# SKIPPED on their first run — `seed_sample_data` resolves every block through
# `apps.<module>.SERVICES` and never through `sample_data.py`, so a seam
# published only in `sample_data.py` returns None and the orchestrator records
# `seam_not_wired`. This file's first draft grew its own guard for that, and
# **there already was one**:
# `test_us_ten_019_sample_records.py::test_the_orchestrator_resolves_every_block_it_declares`.
# A second copy of a check is the drift this repo has been bitten by; the
# existing one was given the non-vacuity floor it lacked instead, in the file
# that owns it.


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-040 wave D tasks D12/D13/D14/D15 + 08-qa/04-fixtures/02-demo-tenant-spec.md §4
# generated: 2026-08-27 by the CR-040 wave A/D lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
