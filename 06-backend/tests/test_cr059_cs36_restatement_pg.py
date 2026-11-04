# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 §8 CS-36, task 21 — "CS-36's proof: all three shapes on
#           PostgreSQL, plus the subledger-equals-ledger tie-out, a replay, and
#           a goodwill credit releasing nothing"
#           Screens: S30 · S21 · S33 (their halves are task 20, not this)
# Rules:    BR-PAY-1072/1073/1074 (the release, no journal line, before the
#           rebill in one transaction) · BR-PAY-010 (the released money is
#           carried credit the next issue draws down) · BR-LED-007 (AR GL = Σ
#           what each account owes; ANY drift is a red flag) · BR-BIL-047 (one
#           bill, one transaction) · CLAUDE.md rule 4 · rule 5 · rule 7 ·
#           hard-won law 14 (a transaction proved on SQLite is not proved)
# Golden:   ❄️ GT-1, finance-signed 2026-08-08 — 684 kWh × $0.12 = 82.08 usage
#           + 18.50 base = 100.58, tax 8.25 % = 8.30, **total 108.88**.
#           Imported from tests/test_us_bil_029_assemble.py, never retyped, and
#           nothing in this file mints a figure: every corrected total is what
#           the real engine prices from a changed meter read.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""⚠ RUN THIS ON POSTGRESQL. ON SQLITE IT PROVES NOTHING AND SAYS SO.

    cd 06-backend
    JOBS_EAGER=false DJANGO_SETTINGS_MODULE=config.settings.local \\
      python -m pytest tests/test_cr059_cs36_restatement_pg.py --reuse-db -q

════════════════════════════════════════════════════════════════════════════
WHY THE DATABASE IS PART OF THE PROOF (CLAUDE.md hard-won law 14)
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory SQLite and ignores `DATABASE_URL`.
**SQLite has no aborted-transaction state at all**, so a failed statement inside
a transaction behaves completely differently there: the naive version of a
multi-statement money write passes the whole suite, green, on every machine, and
fails the first time a real row is refused in production. CS-36 is exactly that
shape — a release, a credit note, a rebill and a ledger posting inside ONE
transaction — and its own specification says so in terms: *"it must be proved on
PostgreSQL, not the default suite."*

**So this file REFUSES to pass on SQLite.** A skip would read as coverage in a
run summary; a failure names the gap. `_refuse_on_sqlite` is the first line of
every case.

════════════════════════════════════════════════════════════════════════════
WHAT RUNS FOR REAL, AND THE ONE THING THAT DOES NOT
════════════════════════════════════════════════════════════════════════════
REAL: the rating engine (GT-1 priced from a meter read), `issue.issue_invoice`
for both the original and the replacement, the ledger postings for both, the
credit note's posting handoff, `credit.apply_credit_at_issue`'s draw-down, the
release, the audit trail, and `ledger.reporting.ar_positions` — the same
derivation the finance screen and the tie-out panel read.

**STUBBED: the RECOMPUTATION ONLY** — what the corrected meter read prices to.
`corrections.recompute` walks gather → stages → `price_bill` against a live
meter, and this file has no meter to re-read; the replacement's figure is
therefore priced by the SAME engine from a different consumption and handed in.
The arithmetic of that pricing is B4/B5's and the golden suite's, not this
file's. Everything downstream of the figure is real.

════════════════════════════════════════════════════════════════════════════
THE TIE-OUT IS THE ASSERTION THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT
════════════════════════════════════════════════════════════════════════════
Three numbers, and two of them come from different modules:

    what the account still owes   (payments: Σ open bills at what each ASKS,
                                   less what has been allocated)
  − what the utility holds for it (payments: Σ receipts − allocations − refunds)
  = the account's slice of 1200 AR (the ledger's own posted lines)

Before the release existed, CS-36's case read **+80.00** on the left and
**−20.00** on the right: a silent **100.00** of drift, *"by exactly the amount
that was paid"*, and nothing anywhere reported it. `_assert_ties_out` is that
comparison, and it is run after every shape below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from django.db import connection as db_connection

from apps.billing import corrections, issue, models, single
from apps.billing.correction_models import CLASS_CREDIT_ONLY, CLASS_RESTATEMENT
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.ledger import reporting as ledger_reporting
from apps.payments import allocation_release, billing_seam as payments_billing_seam
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors
from apps.payments import services as payment_services
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import ISSUED_AT, TEMPLATE_ID, TEMPLATE_VERSION, an_authorised_run
from tests.test_us_bil_016_bulk_corrections import _PreparedStub, _RatedBill, _RatedLine
from tests.test_us_bil_029_assemble import GT1_TOTAL, assemble, billing_data
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: ❄️ GT-1's frozen total — 108.88 — imported and never retyped. It is the bill
#: every case below issues and pays; the CORRECTED figures are the engine's.
ORIGINAL = GT1_TOTAL

#: The two authorities, at the rates `seed_demo` seeds Brazos Bend with. The
#: same pair `test_def_127_one_account_one_figure.py` uses, and for the same
#: reason: BR-BIL-069 makes every tax line resolve its own 2200-series account
#: and a rule naming no tax refuses at issue.
AUTHORITIES = (
    ("State of Texas", Decimal("0.0625"), "2200-01"),
    ("Local", Decimal("0.0200"), "2200-02"),
)

GT1_KWH = Decimal("684")
POSTED_ON = ISSUED_AT
CORRECTED_ON = date(2026, 8, 28)


def _refuse_on_sqlite() -> None:
    """Hard-won law 14 — a skip would read as coverage. This reads as a gap."""
    assert db_connection.vendor == "postgresql", (
        "CS-36's proof asserts what a MULTI-STATEMENT WRITE INSIDE ONE TRANSACTION "
        "does, and SQLite has no aborted-transaction state at all (CLAUDE.md hard-won "
        "law 14). Run it against PostgreSQL: "
        "JOBS_EAGER=false DJANGO_SETTINGS_MODULE=config.settings.local "
        "python -m pytest tests/test_cr059_cs36_restatement_pg.py --reuse-db"
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD — one account, one engine-priced bill, issued and posted for real
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class World:
    tenant: Any
    actor: Any
    account: Any
    invoice: Any
    taxes: tuple


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _an_authority(name: str, rate: Decimal, code: str, actor: Any) -> Any:
    """One tenant-entered authority, its tax and its own 2200-series account."""
    from apps.ledger import services as ledger_services

    jurisdiction = rating_models.TaxJurisdiction.objects.create(
        tenant_id=_tenant_id(), name=name, authority=name
    )
    account = ledger_models.LedgerAccount.objects.filter(tenant_id=_tenant_id(), code=code).first()
    if account is None:
        account = ledger_services.create_tax_authority_account(
            code=code, name=f"Tax payable — {name}", actor=actor
        )
    return rating_models.Tax.objects.create(
        tenant_id=_tenant_id(),
        jurisdiction=jurisdiction,
        name=f"{name} sales tax",
        kind="percent",
        rate=rate,
        liability_gl_account_id=account.id,
    )


def _draft(world_or_none, tenant, actor, account, taxes, *, kwh: Decimal, run_key: str):
    """One draft priced by the REAL engine at a chosen consumption."""
    from apps.billing import rating_seam
    from apps.billing.contracts import ServiceReading

    run = an_authorised_run(tenant, actor, key=run_key)
    data = billing_data(
        account,
        taxes=taxes,
        # Hard rule 3 — consumption ALWAYS with an explicit unit, never a bare
        # number. `Quantity` is the only shape stage 2 accepts, and that is the
        # rule enforced rather than documented.
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=kwh, unit="kWh"),
            ),
        ),
    )
    return assemble(tenant, account, run, data)


def _a_billed_account(tenant, actor, *, account_no: str) -> World:
    """GT-1 priced by the real engine, ISSUED, and posted to the books."""
    from apps.billing import rating_seam

    taxes = tuple(
        rating_seam.TaxRule(
            code=name, rate=rate, tax_id=str(_an_authority(name, rate, code, actor).id)
        )
        for name, rate, code in AUTHORITIES
    )
    account = an_account(actor, tenant, account_no=account_no)
    draft = _draft(None, tenant, actor, account, taxes, kwh=GT1_KWH, run_key=f"{account_no}|orig")
    invoice = issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )
    assert invoice.total == ORIGINAL, "the engine must still price ❄️ GT-1 at 108.88"
    return World(tenant=tenant, actor=actor, account=account, invoice=invoice, taxes=taxes)


def _pay(world: World, amount: Decimal):
    """A REAL receipt, through `record_payment` — so the books move too."""
    return payment_services.record_payment(
        world.actor,
        account_id=world.account.pk,
        amount=amount,
        posted_at=POSTED_ON,
        cleared_at=POSTED_ON,
        confirmation="8842",
        idempotency_reference=uuid4(),
    )


def _correct(world: World, monkeypatch, *, kwh: Decimal, run_key: str):
    """The real restatement, with ONLY the recomputation supplied."""
    rebill_draft = _draft(
        world, world.tenant, world.actor, world.account, world.taxes, kwh=kwh, run_key=run_key
    )
    corrected = _RatedBill(
        [
            _RatedLine(line.kind, line.description, line.amount)
            for line in rebill_draft.lines.all().order_by("created_at", "id")
        ],
        rebill_draft.total,
    )
    monkeypatch.setattr(single, "prepare_single_bill", lambda **k: _PreparedStub())
    monkeypatch.setattr(single, "calculate_single_bill", lambda *a, **k: rebill_draft)

    impact = corrections.build_impact(
        world.invoice,
        reason_codes=("meter_read_error",),
        correction_class=CLASS_RESTATEMENT,
        corrected=corrected,
    )
    executed = corrections.execute_restatement(
        world.invoice,
        impact=impact,
        reason="meter_read_error",
        issued_at=ISSUED_AT,
        on_date=CORRECTED_ON,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=world.actor,
    )
    return executed, models.Invoice.objects.get(pk=executed.rebill_invoice_id)


# ═══════════════════════════════════════════════════════════════════════════
# THE THREE FIGURES, AND THE ONE ASSERTION THAT COMPARES TWO MODULES
# ═══════════════════════════════════════════════════════════════════════════
def _outstanding(world: World) -> Decimal:
    position = payments_billing_seam.open_invoices_for_account(world.account.pk)
    return sum((row.balance for row in position.invoices), ZERO)


def _credit(world: World) -> Decimal:
    return payment_selectors.account_credit_position(world.account.pk)


def _receivable(world: World) -> Decimal:
    positions = ledger_reporting.ar_positions(account_ids=[world.account.pk])
    assert positions["available"], "no AR designation — the tie-out cannot be made"
    return positions["positions"].get(str(world.account.pk), ZERO)


def _assert_ties_out(world: World) -> tuple[Decimal, Decimal, Decimal]:
    """BR-LED-007 — the subledger and the books agree, or this goes red.

    Debit-positive on both sides: what the customer owes, less what the utility
    is holding for them, IS the account's slice of the AR control. Any other
    result is money in one half of the product that the other half has never
    heard of, which is the whole of CS-36's damage in one line.
    """
    outstanding, credit, receivable = _outstanding(world), _credit(world), _receivable(world)
    assert outstanding - credit == receivable, (
        f"SUBLEDGER {outstanding} owed − {credit} held = {outstanding - credit}, "
        f"LEDGER 1200 AR {receivable}. Drift {outstanding - credit - receivable}."
    )
    return outstanding, credit, receivable


# ═══════════════════════════════════════════════════════════════════════════
# SHAPE 1 · DOWN — CS-36's own case
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg1__corrected_down_on_a_paid_bill(brazos, dana, monkeypatch):
    """A bill paid in full, corrected DOWNWARD: the customer owes nothing and
    keeps the difference as visible, refundable credit.

    CS-36's Ajinkya, on ❄️ GT-1's own figures: **108.88** paid on time, the read
    turns out to be wrong, the bill is corrected. Before this fix his account
    said he still owed the whole replacement and he was overdue on arrival,
    because the replacement inherits the ORIGINAL due date.
    """
    _refuse_on_sqlite()
    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-DOWN")
        _pay(world, ORIGINAL)
        assert _assert_ties_out(world) == (ZERO, ZERO, ZERO)

        executed, rebill = _correct(world, monkeypatch, kwh=Decimal("500"), run_key="down|rebill")
        expected_credit = ORIGINAL - rebill.total

        # THE TIE-OUT FIRST, because it is the assertion that would have caught
        # the original defect and the one a reader should see fail (BR-LED-007).
        outstanding, credit, receivable = _assert_ties_out(world)
        assert executed.released_amount == ORIGINAL, "the whole payment came off the original"
        assert rebill.total < ORIGINAL, "the fixture must actually correct the bill DOWNWARD"
        assert outstanding == ZERO, "the replacement is settled by the released money"
        assert credit == expected_credit, "the difference stays on the account"
        assert receivable == -expected_credit, "the books say the utility owes it"
        # ⚠ AMENDED 2026-10-13. This asserted `rebill.due_date ==
        # world.invoice.due_date` ("the replacement inherits the ORIGINAL due
        # date"). The PO ruled that day that a corrected bill is due on the
        # CORRECTION date plus the days to pay. This harness cannot speak to
        # either rule: `_correct` hands `execute_restatement` a draft already
        # priced on its OWN run, so its due date is that run's, not the
        # rebill run's. The ruling is proved end to end in
        # `test_def_bil_10091_bulk_fix_jobs.py` (10 Sep + 21 → 1 Oct).


# ═══════════════════════════════════════════════════════════════════════════
# SHAPE 2 · UP
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg2__corrected_up_on_a_paid_bill(brazos, dana, monkeypatch):
    """Corrected UPWARD: the released money meets the replacement and the
    difference is owed — on the replacement, due on the correction date plus
    the days to pay (PO 2026-10-13; it read "at the ORIGINAL due date" before).

    *"Which is exactly right"* (CS-36). No special case and no second rule: the
    same one step, and the existing draw-down does the rest.
    """
    _refuse_on_sqlite()
    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-UP")
        _pay(world, ORIGINAL)

        executed, rebill = _correct(world, monkeypatch, kwh=Decimal("900"), run_key="up|rebill")
        expected_owed = rebill.total - ORIGINAL

        outstanding, credit, receivable = _assert_ties_out(world)
        assert executed.released_amount == ORIGINAL
        assert rebill.total > ORIGINAL, "the fixture must actually correct the bill UPWARD"
        assert outstanding == expected_owed
        assert credit == ZERO, "everything he paid met the replacement"
        assert receivable == expected_owed
        # Due date: see pg1 — this harness's draft carries its own run's date.


# ═══════════════════════════════════════════════════════════════════════════
# SHAPE 3 · PARTLY PAID
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg3__corrected_down_on_a_part_paid_bill(brazos, dana, monkeypatch):
    """60.00 against ❄️ 108.88, corrected downward: 60.00 is released, the
    replacement draws all 60.00, and the rest is owed.

    The third of CS-36's three shapes, and the one that shows the step is not a
    special case for fully-paid bills.
    """
    _refuse_on_sqlite()
    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-PART")
        paid = Decimal("60.00")
        _pay(world, paid)
        assert _assert_ties_out(world) == (ORIGINAL - paid, ZERO, ORIGINAL - paid)

        executed, rebill = _correct(world, monkeypatch, kwh=Decimal("500"), run_key="part|rebill")

        outstanding, credit, receivable = _assert_ties_out(world)
        assert executed.released_amount == paid, "only what was applied comes off"
        assert outstanding == rebill.total - paid
        assert credit == ZERO
        assert receivable == rebill.total - paid


# ═══════════════════════════════════════════════════════════════════════════
# THE REPLAY
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg4__a_replayed_release_releases_once(brazos, dana):
    """Hard rule 6, on PostgreSQL. The second call finds nothing to release.

    CS-36 says the case row's queued → done guard *"exists and must be relied on
    rather than reinvented"*, and it is — no new key was minted. What is proved
    here is that the ARITHMETIC agrees with it, so a replay that got past the
    case row would still write nothing rather than re-applying the money.
    """
    _refuse_on_sqlite()
    from django.db import transaction

    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-REPLAY")
        _pay(world, ORIGINAL)

        with transaction.atomic():
            first = allocation_release.release_allocations_for_invoice(
                invoice_id=world.invoice.pk, reason="meter_read_error", actor=dana
            )
            second = allocation_release.release_allocations_for_invoice(
                invoice_id=world.invoice.pk, reason="meter_read_error", actor=dana
            )

        assert first.released == ORIGINAL
        assert second.released == ZERO
        assert second.rows == ()
        assert payments_billing_seam.allocated_so_far(world.invoice.pk) == ZERO
        assert _credit(world) == ORIGINAL, "released once, not twice"


# ═══════════════════════════════════════════════════════════════════════════
# A GOODWILL CREDIT RELEASES NOTHING
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg5__a_goodwill_credit_releases_nothing(brazos, dana):
    """No bill changed and no payment moved, so nothing is re-allocated.

    PO ruling 2026-08-11, verbatim: *"you dont touch the bill; you issue new a
    good will credit"*. The release is a RESTATEMENT's step and a concession
    never calls it — which is asserted here by counting allocation rows before
    and after, rather than by reading the code.
    """
    _refuse_on_sqlite()
    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-GOODWILL")
        _pay(world, ORIGINAL)
        rows_before = payment_models.Allocation.objects.filter(invoice=world.invoice).count()
        credit_before = _credit(world)

        concession = Decimal("25.00")
        impact = corrections.build_impact(
            world.invoice,
            reason_codes=("goodwill",),
            correction_class=CLASS_CREDIT_ONLY,
            goodwill_amount=concession,
        )
        corrections.execute_credit_only(
            world.invoice,
            impact=impact,
            amount=concession,
            reason="goodwill",
            issued_at=ISSUED_AT,
            actor=dana,
        )

        assert (
            payment_models.Allocation.objects.filter(invoice=world.invoice).count() == rows_before
        ), "a concession writes no allocation row of any kind"
        assert _credit(world) == credit_before
        assert models.Invoice.objects.get(pk=world.invoice.pk).total == ORIGINAL
        assert models.Invoice.objects.get(pk=world.invoice.pk).status == models.INVOICE_ISSUED
        # ⚠ CS-38 (CR-059 task 24) is the gap this line records rather than
        # closes: the concession is real in the ledger and the customer's
        # balance does not move. That is a different change and is NOT this one.
        assert _outstanding(world) == ZERO


# ═══════════════════════════════════════════════════════════════════════════
# THE TRANSACTION — the half law 14 exists for
# ═══════════════════════════════════════════════════════════════════════════
def test_cs36_task21_pg6__a_failed_rebill_takes_the_release_with_it(brazos, dana, monkeypatch):
    """BR-PAY-1074 on PostgreSQL: both land, or neither does.

    ⚠ **THIS IS THE CASE HARD-WON LAW 14 IS ABOUT.** The release, the credit
    note, the rebill and two ledger postings are one multi-statement write; on
    PostgreSQL a failure anywhere in it aborts the whole transaction, and a
    release that had committed on its own would leave the customer holding
    **108.88** of credit against a bill that was never issued. Afterwards the
    account is exactly as it was: the bill still issued, still paid, nothing
    released, and the books unmoved.
    """
    _refuse_on_sqlite()
    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-ROLLBACK")
        _pay(world, ORIGINAL)
        before = _assert_ties_out(world)
        entries_before = ledger_models.JournalEntry.objects.count()

        def _explode(invoice, **kwargs):
            raise BillingRuleError("the replacement could not be issued", br_ref="BR-BIL-047")

        monkeypatch.setattr(issue, "issue_invoice", _explode)
        with pytest.raises(BillingRuleError):
            _correct(world, monkeypatch, kwh=Decimal("500"), run_key="rollback|rebill")

        assert not models.CreditNote.objects.filter(original_invoice=world.invoice).exists()
        assert payments_billing_seam.allocated_so_far(world.invoice.pk) == ORIGINAL
        assert models.Invoice.objects.get(pk=world.invoice.pk).status == models.INVOICE_ISSUED
        assert ledger_models.JournalEntry.objects.count() == entries_before
        assert _assert_ties_out(world) == before


def test_cs36_task21_pg7__the_release_itself_posts_no_journal_line(brazos, dana):
    """BR-PAY-1073 — the step that re-points the subledger books nothing.

    Asserted on PostgreSQL beside the tie-out, because the two together are the
    whole claim: no entry is written, AND the books still agree with the
    subledger afterwards. Either one alone would be half an answer.
    """
    _refuse_on_sqlite()
    from django.db import transaction

    with tenant_ctx(brazos):
        world = _a_billed_account(brazos, dana, account_no="CS36-NOPOST")
        _pay(world, ORIGINAL)
        entries_before = ledger_models.JournalEntry.objects.count()
        receivable_before = _receivable(world)

        with transaction.atomic():
            allocation_release.release_allocations_for_invoice(
                invoice_id=world.invoice.pk, reason="meter_read_error", actor=dana
            )

        assert ledger_models.JournalEntry.objects.count() == entries_before
        assert _receivable(world) == receivable_before
        # And the subledger DID move — which is the point of releasing.
        assert _credit(world) == ORIGINAL
        assert _outstanding(world) == ORIGINAL


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-36 (*"Proof: the full case on PostgreSQL at each of the
#         three shapes — down, up and partly paid — asserting the outstanding,
#         the credit and the receivable balance after each. The tie-out is the
#         real test: subledger equals ledger… Plus a replayed execution proved
#         to release once, and a goodwill credit proved to release nothing."*) ·
#         §11 task 21 · CLAUDE.md hard-won law 14 · BR-LED-007
# generated: 2026-09-01 by the CR-059 W4 CS-36 lane (tasks 14/19/21)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half —
#         S30/S21/S33 are task 20) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every case was driven RED first — with the release call
#         removed from `execute_restatement` the three shapes fail on the
#         customer-facing figure AND on the tie-out, quoting both halves.
# exceptions: (1) THE RECOMPUTATION IS SUPPLIED, not walked: `corrections.
#         recompute` needs a live meter to re-read and this fixture has none.
#         The replacement's figure is priced by the SAME engine from a different
#         consumption, so no total is typed anywhere in this file. Everything
#         downstream of that figure — the postings, the draw-down, the release,
#         the tie-out — is real.
#         (2) THE FILE FAILS rather than SKIPS on SQLite. A skipped case reads as
#         coverage in a summary line; a failure names the gap (law 1).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
