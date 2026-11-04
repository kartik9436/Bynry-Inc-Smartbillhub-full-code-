# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-015 (single-bill correction: credit note + rebill with
#           impact preview)   Screens: S30
# Rules:    BR-BIL-004 (the original never changes) · BR-BIL-014 (reason →
#           preview → approval → idempotent execution → audit; NO money-bearing
#           write before approval) · BR-BIL-041 (the class derives the
#           mechanism) · BR-BIL-042 (strongest class present) · BR-BIL-043 (a
#           D-class case that moves money is REFUSED) · BR-BIL-044 (nine
#           sections; approval binds the artifact) · BR-BIL-045 (the posting
#           period named before confirm) · BR-BIL-048 (only the latest in the
#           chain) · BR-BIL-064 (the phase-4 panel follows the chain) ·
#           BR-BIL-018 (the back-bill window caps an UPWARD correction —
#           OQ-104 CLOSED) · CLAUDE.md rule 1 · rule 4 · rule 6 · rule 7
# ───────────────────────────────────────────────────────
"""One wrong bill, corrected — and every way the workflow refuses to be misused.

❄️ EVERY FIGURE IN THIS FILE IS FROZEN (B5, finance-signed 2026-08-08) AND
NOTHING HERE MINTS ONE. WE-9: an issued **247.87** whose water read is
superseded 8 → 6 kgal recomputes to **227.95**, a delta of **−19.92**. GT-6: a
**25.00** goodwill credit against a **247.30** invoice leaves **222.30**. The
PO's OQ-111 case: **117.01** corrected to **104.20**.

WHAT RUNS HERE AND WHAT DOES NOT — stated because it changes what these tests
are worth (the same disclosure the bulk file makes, hard-won law 1):

* The **case layer** — the one-bill scope, the nine-section preview, the
  approval binding, the drift refusal, per-bill idempotency — runs in full
  against real rows.
* The **chain** (`invoices.corrects_invoice_id`, migration 0017) is exercised
  end to end and against the real `release.summary_for`, which is the point of
  the column: the panel it unblocks is asserted at its ruled figure.
* The **class-R execution** is exercised with its three neighbours stubbed (the
  rebill's pricing, its issue, and the credit note's posting handoff), exactly
  as `test_us_bil_016_bulk_corrections.py` does and for the same reason. The
  integration with the real rating engine and the real ledger is NOT asserted
  here; the golden suite owns the arithmetic and this file owns the workflow.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.billing import corrections, models, release, selectors, single_correction
from apps.billing.correction_models import (
    CASE_DONE,
    CASE_OPEN,
    CASE_PENDING_APPROVAL,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    CorrectionCase,
    CorrectionCaseBill,
)
from apps.billing.exceptions import BillingRuleError

from tests.test_us_bil_016_bulk_corrections import (
    CORRECTED_TOTAL,
    DELTA,
    ISSUED_AT,
    ORIGINAL_TOTAL,
    TODAY,
    _PreparedStub,
    a_corrected_bill,
    an_issued_bill,
    money_row_counts,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — the probe fixture
    rls_probe_role,  # noqa: F401 — session fixture `rls` depends on
)
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

#: The customer's position before the case (WE-9 §6): the bill's total due was
#: 292.87 = 247.87 current + 45.00 prior, PAID IN FULL, so the balance is 0.00.
BALANCE_BEFORE = Decimal("0.00")


@pytest.fixture(autouse=True)
def _supplied_recompute(monkeypatch):
    """The recomputation is handed in — see the module docstring.

    B5 owns WE-9's corrected figures and the golden suite asserts the engine
    that produces them. What this file tests is what the CORRECTION does with
    them, so re-pricing through the real rating path here would make every
    assertion depend on rating's fixtures rather than on this workflow.
    """
    monkeypatch.setattr(corrections, "recompute", a_corrected_bill)


def a_water_account(actor, tenant, *, account_no="LSR-10001"):
    """An account on a WATER unit — Lone Star Ridge is a water-only tenant.

    `an_account` builds its unit with `services=["electric"]`, which the
    isolation tenant does not have enabled, so provisioning refuses it
    (`VAL-005 metering.service_not_enabled`). That refusal is metering doing its
    job; this helper is the fixture matching the tenant rather than a way round
    it.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(actor, address_line="2200 Pecan Grove", services_available=["water"])
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _stub_rebill_neighbours(monkeypatch, rebill):
    """Stub the three neighbours of a class-R execution. Named, not hidden."""
    monkeypatch.setattr(corrections, "post_credit_note_reversal", lambda *a, **k: None)
    monkeypatch.setattr(corrections.single, "prepare_single_bill", lambda **k: _PreparedStub())
    monkeypatch.setattr(corrections.single, "calculate_single_bill", lambda *a, **k: rebill)
    import apps.billing.issue as issue_module

    monkeypatch.setattr(issue_module, "issue_invoice", lambda invoice, **k: invoice)


# ───────────────────────────────────────────────────────────────────────────
# TC-1 · TC-8 — the preview, and the nine sections
# ───────────────────────────────────────────────────────────────────────────


def test_us_bil_015_tc1__the_preview_reproduces_we9_and_writes_no_money(brazos, dana):
    """TC-1 — ❄️ WE-9 verbatim, and the half that is asserted by COUNTING.

    Original **247.87** → corrected **227.95** → delta **−19.92**. Every one of
    those is B5-frozen and none is computed here.

    The second assertion is the one that matters most and cannot be made by
    reading the return value: BR-BIL-014 says *"NO money-bearing write before
    approval; the preview IS the approval artifact"*, so the four money tables
    are counted before and after. A preview that quietly drafted a rebill would
    look identical from the outside and would have put an invoice in the books
    before anybody approved it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        before = money_row_counts(brazos)

        single = single_correction.open_for_bill(
            bill,
            reason_codes=("wrong_read",),
            actor=dana,
            as_of=TODAY,
            posting_period=date(2026, 7, 31),
            balance_before=BALANCE_BEFORE,
        )

        assert single.correction_class == CLASS_RESTATEMENT
        impact = single.impact
        assert Decimal(impact["original_total"]) == ORIGINAL_TOTAL
        assert Decimal(impact["corrected_total"]) == CORRECTED_TOTAL
        assert Decimal(impact["delta"]) == DELTA
        assert single.case.status == CASE_PENDING_APPROVAL

        # BR-BIL-014's "nothing money-bearing exists yet", proved by census.
        assert money_row_counts(brazos) == before


def test_us_bil_015_tc8__all_nine_preview_sections_are_present_and_none_is_empty(brazos, dana):
    """TC-8 / BR-BIL-044 — *"nine sections, all required, none collapsible away"*.

    The sections are asserted BY NAME against `PREVIEW_SECTIONS` rather than by
    counting, because a preview that renamed one and dropped another would still
    count nine. Four load-bearing contents are then checked individually:

    * **§2** shows EVERY line including the ones that did not move — the epic's
      reason is that *"a preview that shows only movement cannot be checked"*;
    * **§3** carries the per-authority tax split, because four authorities are
      four debts (BR-LED-002) and a summed −1.72 hides which basis moved;
    * **§5** names the POSTING PERIOD before confirm (BR-BIL-045);
    * **§9** carries the standing statement that nothing money-bearing exists.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        single = single_correction.open_for_bill(
            bill,
            reason_codes=("wrong_read",),
            actor=dana,
            as_of=TODAY,
            posting_period=date(2026, 7, 31),
            balance_before=BALANCE_BEFORE,
        )
        sections = single_correction.nine_sections(single)

        assert [name for _, name in single_correction.PREVIEW_SECTIONS] == list(sections)
        assert len(sections) == 9

        # §2 — the unchanged lines are SHOWN, not filtered out.
        assert sections["the_lines"]["unchanged_count"] >= 1
        assert sections["the_lines"]["moved_count"] >= 1
        assert len(sections["the_lines"]["lines"]) == (
            sections["the_lines"]["unchanged_count"] + sections["the_lines"]["moved_count"]
        )

        # §3 — the money, at its frozen figures, with tax per authority.
        assert Decimal(sections["the_money"]["delta"]) == DELTA
        assert sections["the_money"]["tax_by_authority"]

        # §4 — both documents named before anything exists.
        documents = " ".join(sections["the_documents_that_will_exist"]["documents"])
        assert "credit note" in documents and "rebill" in documents

        # §5 — TWO entries, never one net entry, and the posting period named.
        assert len(sections["the_ledger_handoff"]["entries"]) == 2
        assert sections["the_ledger_handoff"]["posting_period"] == "2026-07-31"

        # §6 — the plain-language sentence BR-BIL-009 requires.
        assert "reduces what the customer owes" in (
            sections["the_customers_balance"]["in_plain_language"]
        )
        assert Decimal(sections["the_customers_balance"]["before"]) == BALANCE_BEFORE

        # §7 — BR-BIL-036's print floor is never an empty list.
        assert sections["what_the_customer_will_receive"]["channels"] == ["print"]

        # §9 — the gate, and the standing statement, on the approval screen.
        assert sections["the_gate"]["approver_role"] == "System Admin"
        assert "Nothing money-bearing exists yet" in (sections["the_gate"]["standing_statement"])


# ───────────────────────────────────────────────────────────────────────────
# TC-2 · TC-3 — execution, and the chain the 2026-08-12 ruling made possible
# ───────────────────────────────────────────────────────────────────────────


def test_us_bil_015_tc2_tc3__execution_writes_the_chain_on_the_new_bill(brazos, dana, monkeypatch):
    """TC-2 + TC-3 — **PO 2026-08-12, OQ-120: *"Nod to add the link on the new bill"***.

    After approval: a credit note referencing the original, a rebill, the
    original moved to `corrected` — and the link stamped on the REBILL, pointing
    back at what it replaces. The direction is the ruling: the original is
    immutable and must not gain a column after issue (BR-BIL-004).

    TC-3's *"navigable both ways"* is then asserted off that ONE column, read
    forwards and backwards, which is why the chain cannot fork or disagree with
    itself.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            # A DRAFT, because that is what `calculate_single_bill` returns and
            # the chain link is stamped before issue — the immutability trigger
            # refuses it afterwards, which is the guarantee not a nuisance.
            status=models.INVOICE_DRAFT,
        )
        _stub_rebill_neighbours(monkeypatch, rebill)

        single = single_correction.open_for_bill(
            bill,
            reason_codes=("wrong_read",),
            actor=dana,
            as_of=TODAY,
            posting_period=date(2026, 7, 31),
            balance_before=BALANCE_BEFORE,
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        result = single_correction.execute_single(
            single,
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )
        assert result.status == CASE_DONE and len(result.succeeded) == 1

        original = models.Invoice.objects.get(pk=bill.pk)
        replacement = models.Invoice.objects.get(pk=rebill.pk)

        # THE RULING: the link is on the NEW bill.
        assert str(replacement.corrects_invoice_id) == str(original.pk)
        # And NOT on the original — which has no such column to gain.
        assert original.corrects_invoice_id is None
        assert original.status == models.INVOICE_CORRECTED

        # The credit note leg, which existed all along.
        credit = models.CreditNote.objects.get(original_invoice=original)
        assert credit.amount == Decimal("-247.870000")

        # TC-3 — navigable BOTH ways, off one column.
        forward = single_correction.chain_of(replacement)
        assert forward["replaces"]["invoice_no"] == "BL-2608-018410"
        assert forward["is_latest"] is True

        backward = single_correction.chain_of(original)
        assert backward["replaced_by"]["invoice_no"] == "BL-2608-018997"
        assert backward["is_latest"] is False
        assert backward["head"]["invoice_no"] == "BL-2608-018997"
        assert len(backward["credit_notes"]) == 1


def test_cr101_chain_carries_every_fact_the_what_happened_table_draws(brazos, dana, monkeypatch):
    """`CR-101-BRC03` — the Billing blueprint's §02.3 *What happened* table.

    The drawing gives five events a DATE, a REASON, an ACTOR and an EFFECT
    apiece, and `chain_of` served a number and an id. The step-1 record chipped
    that state *Exists behind* and said the chip was a claim to CHECK rather
    than inherit; this is the check, written as the assertion that fails if any
    of the four facts stops being served.

    ⚠ **THE NET EFFECT IS THE ONE DERIVED FIGURE AND IT IS ASSERTED ON THE
    ENGINE'S OWN NUMBERS, NEVER ON THE DRAWING'S.** B14 rule 37: a figure in a
    wireframe is an illustration. So the expected value here is
    `CORRECTED_TOTAL − ORIGINAL_TOTAL` computed from this file's own constants
    — `227.95 − 247.87 = −19.92` — and not the `−$53.15` the blueprint draws.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            status=models.INVOICE_DRAFT,
        )
        _stub_rebill_neighbours(monkeypatch, rebill)
        single = single_correction.open_for_bill(
            bill,
            reason_codes=("wrong_read",),
            actor=dana,
            as_of=TODAY,
            posting_period=date(2026, 7, 31),
            balance_before=BALANCE_BEFORE,
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        single_correction.execute_single(
            single,
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )

        chain = single_correction.chain_of(models.Invoice.objects.get(pk=bill.pk))

        # WHEN and EFFECT on this bill's own row.
        assert chain["issued_at"] is not None
        assert Decimal(chain["total"]) == ORIGINAL_TOTAL
        assert chain["currency"] == "USD"

        # WHEN and EFFECT on the replacement's row.
        #
        # ⚠ **THE DATE IS ASSERTED AS PRESENT, NOT AS NON-NULL, AND THE
        # DIFFERENCE IS A FINDING RATHER THAN A WEAKER TEST.** This fixture
        # builds the rebill BY HAND as a draft (the chain column is frozen at
        # issue, so it has to), and nothing in this stubbed path stamps
        # `issued_at` on it — so the fixture's replacement genuinely has no
        # issue date, while the seeded tenant's `BL-2607-000047` has one. What
        # this test owns is that the MEMBER is served; a null renders a dash on
        # the screen, exactly as every other absent date does.
        assert "issued_at" in chain["replaced_by"]
        assert Decimal(chain["replaced_by"]["total"]) == CORRECTED_TOTAL

        # REASON and WHEN on the credit note's row — the words are the screen's,
        # the CODE is what the server serves and what `DEF-BIL-5233` is about.
        note = chain["credit_notes"][0]
        assert note["reason"] == "wrong_read"
        assert "issued_at" in note
        assert Decimal(note["amount"]) == -ORIGINAL_TOTAL

        # WHO, on the two rows that have one — a NAME and a ROLE, never an id.
        case = chain["case"]
        assert case is not None
        assert case["reason_codes"] == ["wrong_read"]
        assert case["opened_at"] is not None
        assert case["opened_by"]["name"] == dana.user.full_name
        assert case["approved_on"] == TODAY.isoformat()
        assert case["approved_by"]["name"] == dana.user.full_name
        assert "id" not in case["approved_by"]  # B14 rule 31

        # The net effect, from the engine's figures.
        assert Decimal(chain["net_effect"]) == CORRECTED_TOTAL - ORIGINAL_TOTAL

        # An UNCORRECTED bill has no case and no net effect — `null`, never
        # `0.00`, because "nothing happened" is not "it netted to zero".
        clean = an_issued_bill(brazos, account, run, invoice_no="BL-2608-019001")
        clean_chain = single_correction.chain_of(clean)
        assert clean_chain["case"] is None
        assert clean_chain["net_effect"] is None
        assert clean_chain["credit_notes"] == []


def test_us_bil_015_tc3b__the_api_serves_the_chain_that_used_to_be_null(brazos, dana, monkeypatch):
    """`rebill_of_invoice_id` / `corrected_by_invoice_id` were null on EVERY row.

    They were served under their contracted names with a docstring saying no
    column carried either citation. The column exists now, and both are read off
    it — forwards on the replacement, backwards on the original. This asserts
    the API half of the same ruling, because a chain the screen cannot see is a
    chain that does not exist for the person using it (hard-won law 2).
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            corrects=bill,
        )

        on_replacement = selectors.invoice_detail(str(rebill.pk))
        assert on_replacement["rebill_of_invoice_id"] == str(bill.pk)
        assert on_replacement["corrected_by_invoice_id"] is None

        on_original = selectors.invoice_detail(str(bill.pk))
        assert on_original["rebill_of_invoice_id"] is None
        assert on_original["corrected_by_invoice_id"] == str(rebill.pk)


# ───────────────────────────────────────────────────────────────────────────
# BR-BIL-064 — the phase-4 panel that refused for want of this column
# ───────────────────────────────────────────────────────────────────────────


def test_us_bil_015_br064__the_phase4_panel_now_reads_the_replacements_figure(brazos, dana):
    """**BR-BIL-064 / OQ-111, unblocked by OQ-120.** The PO's own worked case.

    A run issues **$117.01** to ACC-1042; a rebill in a LATER run corrects it to
    **$104.20**. The ruling — *"A Replacement counts (panel = what these
    customers owe now)"* — makes the FIRST run's panel read **$104.20 · 1 bill ·
    1 account**.

    `release.summary_for` raised `BillingRuleError` on exactly this shape until
    2026-08-12, because both reachable figures were wrong. Both are asserted
    here as DATA so the contrast is pinned by more than a docstring: a panel
    that stayed a filter on `invoices.bill_run_id` totals **$117.01**, and one
    that dropped the superseded bill the way a VOID is dropped totals **nothing
    at all**. Neither is the ruled answer.
    """
    with tenant_ctx(brazos):
        first_run = a_run(brazos)
        acc_1042 = an_account(dana, brazos, account_no="ACC-1042")
        original = an_issued_bill(
            brazos, acc_1042, first_run, invoice_no="BL-2607-018410", total=Decimal("117.01")
        )
        later_run = a_run(brazos, key="2026-07|cycle-1")
        an_issued_bill(
            brazos,
            acc_1042,
            later_run,
            invoice_no="BL-2607-018411",
            total=Decimal("104.20"),
            corrects=original,
            bill_type="rebill",
        )
        original.status = models.INVOICE_CORRECTED
        original.save(update_fields=["status"])

        summary = release.summary_for(first_run)

        assert summary.amount == Decimal("104.200000")
        assert summary.bills == 1
        assert summary.accounts == 1

        # The two figures that are reachable and wrong, pinned as data.
        naive = release.counted_bills(first_run).aggregate(total=Sum("total"))["total"]
        assert naive == Decimal("117.010000"), "a filter on bill_run_id shows what nobody owes"
        dropped = (
            release.counted_bills(first_run)
            .exclude(status__in=release.SUPERSEDED_STATUSES)
            .aggregate(total=Sum("total"))["total"]
        )
        assert dropped is None, "dropping it like a VOID shows 0.00 for a customer who owes"


def test_us_bil_015_br064b__a_rebill_in_the_same_run_is_not_counted_twice(brazos, dana):
    """The de-duplication the chain walk has to get right.

    When the rebill carries THIS run's `bill_run`, the resolved head is already
    in the set on its own account. Counting it twice would read **$208.40** for
    one customer who owes **$104.20** — a plausible-looking number on a screen
    and the reason the resolved set is keyed by primary key.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="ACC-1042")
        original = an_issued_bill(
            brazos, account, run, invoice_no="BL-2607-018410", total=Decimal("117.01")
        )
        an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2607-018411",
            total=Decimal("104.20"),
            corrects=original,
            bill_type="rebill",
        )
        original.status = models.INVOICE_CORRECTED
        original.save(update_fields=["status"])

        summary = release.summary_for(run)
        assert summary.amount == Decimal("104.200000")
        assert summary.bills == 1


def test_us_bil_015_tc18__a_credit_note_with_no_rebill_counts_like_a_replacement(brazos, dana):
    """TC-18 / OQ-121 — *"no rebill , Count it like a replacement"* (PO 2026-08-12).

    ❄️ GT-6's frozen shape: a **$25.00** goodwill credit against a **$247.30**
    invoice. The panel reads **$222.30 · 1 bill · 1 account** — the bill is
    COUNTED, never dropped, and the figure moves by the credit. A corrected
    account is therefore not invisible to the person signing the run off, which
    is the question the PO was asked.

    GROSS and CREDIT both travel beside the net (BR-BIL-064): a signed sum of the
    credit-note column would read **$272.30** and is the defect DEF-085 records.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos, account_no="ACC-1042")
        bill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-018410", total=Decimal("247.30")
        )
        models.CreditNote.objects.create(
            tenant=brazos,
            account=account,
            original_invoice=bill,
            amount=Decimal("-25.00"),
            currency="USD",
            reason="goodwill",
            issued_at=ISSUED_AT,
        )

        summary = release.summary_for(run)
        assert summary.amount == Decimal("222.300000")
        assert summary.bills == 1
        assert summary.accounts == 1
        # Not the signed-sum reading, which DEF-085 records.
        assert summary.amount != Decimal("272.300000")


# ───────────────────────────────────────────────────────────────────────────
# The refusals — TC-4 · TC-9 · TC-10 · TC-13 · TC-15 · TC-16
# ───────────────────────────────────────────────────────────────────────────


def test_us_bil_015_tc4__execution_without_approval_is_refused_server_side(brazos, dana):
    """TC-4 — *"the gate is server-side; preview artifacts only"* (BR-BIL-014).

    The preview is an ARTIFACT, not a permission. Refused before anything is
    written and with the approving role named, so the S30 button knows not to
    offer itself.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        single = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        before = money_row_counts(brazos)

        with pytest.raises(BillingRuleError) as refusal:
            single_correction.execute_single(single, issued_at=ISSUED_AT, on_date=TODAY)

        assert "System Admin" in str(refusal.value)
        assert "not a permission" in str(refusal.value)
        assert money_row_counts(brazos) == before


def test_us_bil_015_tc9__a_document_reason_that_moves_money_is_refused(brazos, dana):
    """TC-9 / BR-BIL-043 — a spelling must never put $19.92 on an account.

    A clerk opens a case with reason "name spelling" (class D) and the
    recomputation moves money because the READ was also wrong. Refused, naming
    the delta, before anything is written; re-opened with "wrong read" it
    proceeds as TC-1.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        before = money_row_counts(brazos)

        with pytest.raises(BillingRuleError) as refusal:
            single_correction.open_for_bill(
                bill, reason_codes=("customer_name",), actor=dana, as_of=TODAY
            )

        message = str(refusal.value)
        assert "does not change money" in message
        assert "Nothing was" in message
        assert money_row_counts(brazos) == before
        assert not CorrectionCase.objects.filter(tenant=brazos).exists()

        # Re-opened with the reason that describes what is actually wrong.
        ok = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        assert ok.correction_class == CLASS_RESTATEMENT


def test_us_bil_015_tc10__the_mechanism_cannot_be_supplied_by_the_caller(brazos, dana):
    """TC-10 — the SILENT-UNDERBILLING guard (BR-BIL-041), proved RED first.

    An operator answers "wrong rate/plan" with a document reissue through the
    API. Refused: the mechanism is DERIVED from the reason, never supplied. The
    failure mode this guards is invisible — the customer keeps the wrong amount
    and no gate ever fires — which is why the epic singles it out.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")

        with pytest.raises(BillingRuleError) as refusal:
            corrections.build_impact(
                bill,
                reason_codes=("wrong_rate_plan",),
                correction_class=CLASS_RESTATEMENT,
                mechanism=CLASS_DOCUMENT,
            )
        assert "BR-BIL-041" in str(refusal.value.br_ref or "") or "derived" in str(refusal.value)


def test_us_bil_015_tc13__input_drift_between_preview_and_execute_refuses(brazos, dana):
    """TC-13 / BR-BIL-044 — approval binds the ARTIFACT, not the query.

    The read is corrected AGAIN between preview and execute. Execution is
    refused, and the stale artifact is RETAINED as evidence rather than
    overwritten — what was approved stays readable.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        single = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        approved_hash = single.case.preview_hash

        # The inputs move: the pinned impact no longer describes what would
        # happen. (Mutating the stored row is the cheapest way to stage the
        # drift the real world produces by re-superseding a read.)
        row = CorrectionCaseBill.objects.get(case=single.case)
        drifted = dict(row.impact)
        drifted["corrected_total"] = "999.99"
        row.impact = drifted
        row.save(update_fields=["impact"])

        with pytest.raises(BillingRuleError) as refusal:
            single_correction.execute_single(
                single,
                issued_at=ISSUED_AT,
                on_date=TODAY,
                template_id=bill.template_id,
                template_version=1,
            )
        assert "inputs moved between preview and execute" in str(refusal.value)

        single.case.refresh_from_db()
        assert single.case.preview_hash == approved_hash, "the stale artifact is RETAINED"


def test_us_bil_015_tc15__only_the_latest_in_the_chain_is_correctable(brazos, dana, monkeypatch):
    """TC-15 / BR-BIL-048 — and the refusal now NAMES the replacement.

    A correction opened against the ORIGINAL after a rebill already exists is
    refused. Before the chain column the message could only say "open the case
    on its replacement"; it can now say WHICH, because
    `corrections.replacement_of` reads the column the PO ruled on 2026-08-12.
    Telling an operator to go and find a bill is how the wrong bill gets picked.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            corrects=bill,
        )
        bill.status = models.INVOICE_CORRECTED
        bill.save(update_fields=["status"])

        with pytest.raises(BillingRuleError) as refusal:
            single_correction.open_for_bill(
                bill.__class__.objects.get(pk=bill.pk),
                reason_codes=("wrong_read",),
                actor=dana,
                as_of=TODAY,
            )
        message = str(refusal.value)
        assert "not the latest document in its chain" in message
        assert "BL-2608-018997" in message, "the refusal NAMES the replacement"


def test_us_bil_015_tc16__an_upward_correction_beyond_the_window_refuses_not_stubs(
    brazos, dana, monkeypatch
):
    """TC-16 — **OQ-104 is CLOSED and this is a refusal, not a stub.**

    EP-BIL-04's TC-16 still asks for a not-implemented stub against that id and
    its frontmatter still carries `blocked_by: [OQ-104]`. The live registry
    records the PO closing it on 2026-08-11 with option A — *the BR-BIL-018
    back-bill window APPLIES to an upward correction; the correction workflow is
    NOT a route around the cap; downward corrections are unaffected at any age*.

    A not-implemented stub against a CLOSED id is what gate G8 exists to catch,
    so this asserts the REFUSAL — and asserts the asymmetry, because the
    asymmetry is the ruling: the same aged bill corrected DOWNWARD proceeds.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")

        # An UPWARD correction of a bill 30 months old, the PO's own example.
        monkeypatch.setattr(
            corrections,
            "recompute",
            lambda invoice: _upward(invoice),
        )
        with pytest.raises(BillingRuleError) as refusal:
            single_correction.open_for_bill(
                bill,
                reason_codes=("missed_charge",),
                actor=dana,
                as_of=date(2029, 1, 31),
            )
        message = str(refusal.value)
        assert "back-bill window" in message
        # A REFUSAL, never a stub. The message DOES cite OQ-104 — as the
        # RULING that produced the refusal ("PO 2026-08-11, OQ-104 ... the
        # window applies"), which is the honest citation of a closed question
        # and the opposite of a stub.
        assert not isinstance(refusal.value, NotImplementedError)
        assert "closing OQ-104" in message and "PO 2026-08-11" in message

        # The asymmetry: DOWNWARD, same age, proceeds.
        monkeypatch.setattr(corrections, "recompute", a_corrected_bill)
        ok = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=date(2029, 1, 31)
        )
        assert Decimal(ok.impact["delta"]) == DELTA


def _upward(invoice):
    """WE-9's fixture re-priced UPWARD — a missed charge, not a lower read."""
    rated = a_corrected_bill(invoice)
    rated.total = ORIGINAL_TOTAL + Decimal("40.00")
    return rated


# ───────────────────────────────────────────────────────────────────────────
# Rule 6 · rule 4 · rule 1 — idempotency, immutability, isolation
# ───────────────────────────────────────────────────────────────────────────


def test_us_bil_015_tc6__execution_replayed_produces_exactly_one_of_each(brazos, dana, monkeypatch):
    """TC-6 / rule 6 — a retry storm leaves ONE credit note and ONE rebill.

    TWO guarantees, at two depths, and they are not the same one:

    * **The case gate.** A finished case is `done`, and re-executing it is
      refused outright. That is what stops a double-clicked button.
    * **The per-bill skip**, which is the guarantee that survives a *crashed*
      worker — the case status never settled, so a resumed job finds it `open`
      and runs the loop again. `correction_case_bills` only ever moves
      queued → done, so the row is reported as already-done and nothing is
      written. This is the shape asserted below, because it is the one that
      actually happens in production and the one a re-implementation would
      break.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            # A DRAFT, because that is what `calculate_single_bill` returns and
            # the chain link is stamped before issue — the immutability trigger
            # refuses it afterwards, which is the guarantee not a nuisance.
            status=models.INVOICE_DRAFT,
        )
        _stub_rebill_neighbours(monkeypatch, rebill)

        single = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        common = dict(
            issued_at=ISSUED_AT, on_date=TODAY, template_id=bill.template_id, template_version=1
        )
        single_correction.execute_single(single, **common)

        # 1 · the case gate — a finished case does not re-execute.
        single.case.refresh_from_db()
        assert single.case.status == CASE_DONE
        with pytest.raises(BillingRuleError) as gated:
            single_correction.execute_single(single, **common)
        assert "nothing executes without a recorded" in str(gated.value)

        # 2 · the per-bill skip — a crashed worker's resume, which is the real
        #     replay shape: the artifacts exist but the case never settled.
        CorrectionCase.objects.filter(pk=single.case.pk).update(status=CASE_OPEN)
        single.case.refresh_from_db()
        replay = single_correction.execute_single(single, **common)

        assert replay.skipped_already_done and not replay.succeeded
        assert models.CreditNote.objects.filter(original_invoice=bill).count() == 1
        assert models.Invoice.objects.filter(corrects_invoice_id=bill.pk).count() == 1


@requires_postgres
def test_us_bil_015_rule4__the_chain_link_is_frozen_at_issue_like_the_money(brazos, dana):
    """**Hard rule 4 applied to the new column** — migration 0017's whole point.

    `0009` wrote down the mechanism this obeys: PostgreSQL stores a function
    body as TEXT, so adding a column does not teach the immutability trigger
    about it, and a column added without re-emitting the function is a column
    the freeze does not cover. A chain edge that could be re-pointed after issue
    would let history be rewritten without an UPDATE to any money column.

    PROVED RED: the column was added WITHOUT the re-emitted function and this
    UPDATE succeeded. The transcript is in the lane report.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        other = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018411")

        with pytest.raises(Exception) as refusal:  # noqa: B017 — the DB's own error type
            with transaction.atomic():
                models.Invoice.objects.filter(pk=bill.pk).update(corrects_invoice_id=other.pk)
        assert "BR-BIL-004" in str(refusal.value) or "hard rule 4" in str(refusal.value)


@requires_postgres
def test_us_bil_015_br048__one_original_has_at_most_one_replacement(brazos, dana):
    """`uq_invoices_one_replacement` — the chain is a chain, never a tree.

    BR-BIL-048 presumes a chain: *"only the LATEST document in a chain is
    correctable"*. Two bills claiming to replace one original is a tree, a tree
    has no latest member, and the panel would have no answer. The service layer
    refuses this twice already; this is the guarantee that survives the race
    both of those lose.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        original = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        an_issued_bill(brazos, account, run, invoice_no="BL-2608-018997", corrects=original)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                an_issued_bill(brazos, account, run, invoice_no="BL-2608-018998", corrects=original)


@pytest.mark.isolation
@requires_postgres
def test_us_bil_015_tc7__isolation_a_correction_never_crosses_a_tenant(
    brazos, lonestar, dana, erin, rls
):
    """TC-7 / hard rule 1 — Lone Star Ridge's case sees its own bills only.

    Asserted THROUGH THE DATABASE under `sbh_rls_probe`, a role RLS actually
    applies to, so the app-layer `tenant_id=` filter is deliberately not in the
    path. `tenant_ctx` alone would prove nothing here: the unit-tier fixtures
    monkeypatch the connection with a recorder because sqlite has no
    `set_config`, and on Postgres that recorder would swallow the very statement
    this case exists to verify.

    THE CHAIN COLUMN IS THE REASON THIS MATTERS MORE THAN THE USUAL ROW PROBE. A
    Postgres foreign key is NOT RLS-aware, so `invoices.corrects_invoice_id`
    (migration 0017) is exactly the shape that could put one utility's bill
    number on another utility's screen if only the app layer were checking.
    """
    with tenant_ctx(brazos):
        brazos_bill = an_issued_bill(
            brazos,
            an_account(dana, brazos),
            a_run(brazos, key="2026-07|cycle-A"),
            invoice_no="BL-2608-018410",
        )
    with tenant_ctx(lonestar):
        lsr_bill = an_issued_bill(
            lonestar,
            a_water_account(erin, lonestar),
            a_run(lonestar, key="2026-07|cycle-A"),
            invoice_no="LSR-2608-000102",
        )

    # Each tenant sees its own invoice rows and none of the other's.
    assert_rls_scoped(
        rls, "invoices", owner=brazos, intruder=lonestar, owner_ids={str(brazos_bill.pk)}
    )
    assert_rls_scoped(
        rls, "invoices", owner=lonestar, intruder=brazos, owner_ids={str(lsr_bill.pk)}
    )

    # And the correction workflow's own tables carry the same policy — a case
    # is a record of which of a utility's bills are being changed and by how
    # much, which is not metadata.
    assert_denied_without_context(rls, "invoices", "correction_cases", "correction_case_bills")


def test_us_bil_015_rule7__every_money_action_writes_an_audit_row(
    brazos, dana, monkeypatch, audit_rows
):
    """CLAUDE.md rule 7 — the case, the approval and the execution are all audited.

    And the audit row still carries the rebill link. The 2026-08-11 reading of
    OQ-120 made that trail the ONLY carrier; the 2026-08-12 ruling added the
    column and the trail stays, because rule 7 owes the row whatever the schema
    does.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            # A DRAFT, because that is what `calculate_single_bill` returns and
            # the chain link is stamped before issue — the immutability trigger
            # refuses it afterwards, which is the guarantee not a nuisance.
            status=models.INVOICE_DRAFT,
        )
        _stub_rebill_neighbours(monkeypatch, rebill)

        single = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        single_correction.execute_single(
            single,
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )

        actions = {row["action"] for row in audit_rows}
        assert {"correction.case_opened", "correction.approved", "correction.executed"} <= actions

        executed = next(row for row in audit_rows if row["action"] == "correction.executed")
        assert executed["after"]["rebill_invoice_id"] == str(rebill.pk)
        # DEF-2377 — THIS ASSERTION USED TO READ
        #     assert "corrects_invoice_id" in executed["after"]["chain_link_column"]
        # and that is the trap G28's own docstring names: *"a test written beside
        # the string protects the string"*. It PINNED a database column name into
        # a value S61 renders to a clerk, so the internal reference was not merely
        # unchecked, it was a requirement. The link is unchanged; what changed is
        # that the sentence is now readable, and this asserts BOTH halves.
        link = executed["after"]["replacement_link"]
        assert "replace" in link, link
        assert "corrects_invoice_id" not in link and "invoices." not in link, link


def test_us_bil_015_artifacts__the_cases_claim_of_success_is_checkable(brazos, dana, monkeypatch):
    """BR-BIL-047 — *"checkable against what it produced"*, not taken.

    Every id comes back off the row after execution and the chain is re-walked
    from the database, which is the difference between a result table and a
    progress bar.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(brazos, account, run, invoice_no="BL-2608-018410")
        rebill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018997",
            total=CORRECTED_TOTAL,
            # A DRAFT, because that is what `calculate_single_bill` returns and
            # the chain link is stamped before issue — the immutability trigger
            # refuses it afterwards, which is the guarantee not a nuisance.
            status=models.INVOICE_DRAFT,
        )
        _stub_rebill_neighbours(monkeypatch, rebill)

        single = single_correction.open_for_bill(
            bill, reason_codes=("wrong_read",), actor=dana, as_of=TODAY
        )
        single_correction.approve(single.case, approver=dana, on_date=TODAY)
        single_correction.execute_single(
            single,
            issued_at=ISSUED_AT,
            on_date=TODAY,
            template_id=bill.template_id,
            template_version=1,
            actor=dana,
        )
        artifacts = single_correction.executed_artifacts(single)

        assert artifacts["case_status"] == CASE_DONE
        assert artifacts["original_status"] == models.INVOICE_CORRECTED
        assert artifacts["credit_note_id"] is not None
        assert artifacts["rebill_invoice_id"] == str(rebill.pk)
        assert artifacts["chain"]["replaced_by"]["invoice_no"] == "BL-2608-018997"


def test_us_bil_015_oq215__the_class_c_artifact_question_is_stated_not_decided(brazos, dana):
    """**OQ-215** — two PO rulings disagree and this lane refuses to pick.

    ❄️ GT-6's **222.30** is reached either way — as a credit note against THIS
    bill, or as an account credit carried to the next one — which is exactly why
    nothing has forced the question. What differs is whether the customer's
    current bill says 247.30 or 222.30.

    So the preview STATES the open question in §3 rather than presenting the
    engine's reading as settled. This asserts the statement is there, which is
    the whole of what an implementer is allowed to do here.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(
            brazos, account, run, invoice_no="BL-2608-018410", total=Decimal("247.30")
        )
        single = single_correction.open_for_bill(
            bill,
            reason_codes=("goodwill",),
            actor=dana,
            as_of=TODAY,
            goodwill_amount=Decimal("25.00"),
            balance_before=Decimal("247.30"),
        )
        sections = single_correction.nine_sections(single)

        question = sections["the_money"]["open_question"]
        assert question["oq"] == "OQ-215"
        assert "222.30" in question["detail"] and "247.30" in question["detail"]
        # The engine's own reading is left exactly as it was — not flipped here.
        assert Decimal(single.impact["delta"]) == Decimal("0")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-015@f24bbae (ships with apps/billing/single_correction.py — the same four sources)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest · run_gates · 10-scripts/03-golden-verify.py
# exceptions: (1) THE CLASS-R EXECUTION STUBS THREE NEIGHBOURS (the rebill's
#         pricing, its issue, and the credit note's posting handoff), exactly as
#         `test_us_bil_016_bulk_corrections.py` does. The integration with the
#         real rating engine and the real ledger is NOT asserted here and is
#         REPORTED — a test that stubs its neighbours must say so rather than
#         let a green tick imply more (hard-won law 1).
#         (2) TC-16 IS A REFUSAL TEST, NOT A STUB TEST. OQ-104 is CLOSED in the
#         live registry; a not-implemented stub against a closed id is what G8
#         catches. The stale epic frontmatter is REPORTED.
#         (3) TC-17's CLASS-C EXECUTION IS NOT ASSERTED HERE beyond the preview
#         and OQ-215's statement: the artifact question is open and asserting an
#         execution shape would be picking a reading.
#         (4) THE THREE DATABASE-LEVEL GUARANTEES USE `requires_postgres`, never
#         a bare skip — sqlite has neither the trigger nor the partial unique
#         index, and a check that skips silently is not a check.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
