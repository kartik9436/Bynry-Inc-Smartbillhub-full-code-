# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-536 (a discounted bill drafts and previews and CANNOT ISSUE —
#           kind `discount` had no GL rule) · DEF-537 (corrections and
#           back-bills re-price WITHOUT discounts — both ends built, the CALL
#           missing) · DEF-502 (the discount stage this builds on)
# Story:    US-BIL-005 (issue) · US-BIL-009 (the balanced posting handoff) ·
#           US-BIL-015 (corrections) · US-LED-005 (the chart and its
#           designations)   Screens: S31 step 6 · S56 · Settings → Configure
# Rules:    BR-BIL-010 (every line's GL account is stamped AT ISSUE) ·
#           BR-BIL-011 (one bill = one balanced JE) · BR-BIL-055 (a break never
#           blocks the run) · BR-RAT-068 (a discount is an OVERLAY — its own
#           line, so subsidy granted is reportable) · BR-RAT-007 (the service
#           date is the pivot a re-price resolves on) · CLAUDE.md rule 2
#           (money) · rule 4 (immutability) · rule 5 (sole writer)
# Golden:   GT-1 ❄️ — 684 kWh × $0.12 = 82.08 usage + 18.50 base = 100.58. The
#           figures below are that bill with a 10.00 reduction, exactly as the
#           2026-08-28 decision-log row works them.
# Tests:    this file
# Impacts:  apps/billing/issue._gl_account_for (the `discount` branch) ·
#           apps/billing/posting_seam (the debit bucket) ·
#           apps/ledger/chart (the thirteenth designation, 4760 — 4300 until
#           CR-061 re-filed it on 2026-09-01) ·
#           apps/billing/corrections.recompute · apps/billing/backbill
# ───────────────────────────────────────────────────────
"""DEF-536 / DEF-537 — a discounted bill ISSUES, and it posts to its own code.

WHAT THE PRODUCT OWNER RULED, 2026-08-28, VERBATIM
---------------------------------------------------
*"you will need differnt GL code for these - dont keep them in same, create
differnt category as required and keep them in it"*.

A discount does NOT reduce the service's own revenue account. It posts to a
separate GL code in a separate category — standard contra-revenue, and option
**(a)** as OQ-152 itself enumerated it on 2026-08-11.

THE WORKED FIGURES THIS FILE PINS — the frozen GT-1 bill, with a 10.00 reduction
-------------------------------------------------------------------------------
                              old (netted)      ruled (its own GL)
    electric usage  4100      CR   72.08        CR   82.08
    electric base   4105      CR   18.50        CR   18.50
    customer discounts 4760      —              DR   10.00
    accounts receivable 1200   DR   90.58        DR   90.58
                              ------------      ------------
                              both balance at 100.58

The ruled form stops reporting **72.08** of electric revenue the utility never
earned at that price, and states the 10.00 it gave away as its own figure — the
one thing BR-RAT-068's *"subsidy granted is reportable"* exists to produce.

⚠ IT ALSO REMOVES A FAILURE MODE, AND BOTH RULINGS STAND
--------------------------------------------------------
OQ-152 closed 2026-08-12 with *"a bill whose GL bucket sums below zero REFUSES
to issue"*, enforced by `posting_seam.posting_buckets`
(`posting_bucket_is_negative_oq_152`). A discount netted against the service's
own account is what drives a bucket below zero. Posted as a DEBIT to its own
account no bucket goes negative, so that refusal cannot fire on a discount at
all. **Neither ruling supersedes the other** — `tc4` is the case that holds the
refusal in place for everything else, and it is the case that must never be
softened to make a discount pass.

WHAT IS DELIBERATELY NOT BUILT HERE, so it is not mistaken for done
-------------------------------------------------------------------
No `discount_grants` row is written at issue and no programme is flipped to
`suspended_funding_exhausted`. Both need the discount LINE to name the
programme it came from, and it does not: `apply_discounts` stamps the
customer-facing NAME as the description and no code, so an issued bill cannot
say which enrolment to deplete. Matching on the description was option D of
OQ-116 and the PO declined it. Filed rather than approximated — see the
defect register — because a budget that depletes for single-discount accounts
and not for others is worse books than one that does not deplete at all.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import corrections, issue, models, posting_seam
from apps.billing.exceptions import BillingRuleError
from apps.ledger import chart as ledger_chart
from apps.ledger import models as ledger_models
from apps.ledger import selectors as ledger_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    BASE_AMOUNT,
    ISSUED_AT,
    SUBTOTAL,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    USAGE_AMOUNT,
    a_priced_draft,
    an_authorised_run,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

D = Decimal

#: The reduction the 2026-08-28 decision-log row works GT-1 with. Copied from
#: the ruling, never computed here — a test that re-derived its own expectation
#: from the code's arithmetic would agree with a broken implementation.
REDUCTION = D("10.00")
#: 100.58 − 10.00. What the customer is asked for, and `invoices.total`.
DISCOUNTED_TOTAL = D("90.58")
#: Both sides of the journal entry. Unchanged by the discount, which is the
#: whole point: the entry got BIGGER on both sides, not smaller on one.
ENTRY_BOTH_SIDES = D("100.58")


def journal_entries(tenant):
    return ledger_models.JournalEntry.objects.filter(tenant=tenant)


def journal_totals(tenant, entry):
    """Σ per GL CODE straight out of `journal_lines`.

    Read from the TABLE, never off the result object and never through a ledger
    selector — the same discipline `test_us_bil_009_posting_handoff.py` states:
    what must be checked is what LANDED, not what the code that wrote it says.
    """
    totals: dict[str, dict[str, Decimal]] = {}
    rows = ledger_models.JournalLine.objects.filter(tenant=tenant, journal_entry=entry).values_list(
        "ledger_account__code", "side", "amount"
    )
    for code, side, amount in rows:
        bucket = totals.setdefault(code, {"debit": D("0"), "credit": D("0")})
        bucket[side] += amount
    return totals


def a_discounted_draft(tenant, account, run, *, invoice_no="BL-2607-000536"):
    """GT-1's frozen bill with a 10.00 reduction on it, in stage-6 shape.

    Hand-built on `a_priced_draft`, so the usage and base figures are the
    ❄️ frozen ones and the ONLY new thing is the reduction line. The reduction
    carries kind `discount`, a NEGATIVE amount and no service — exactly what
    `apps/rating/pricing/stages/apply_discounts.py` emits (BR-RAT-068: the bill
    shows the full tariff amount AND the reduction, as its own line).
    """
    draft = a_priced_draft(tenant, account, run, invoice_no=invoice_no)
    models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=draft,
        account=account,
        service=None,  # an ACCOUNT overlay — no service's revenue line
        kind="discount",
        description="Senior citizen discount",
        amount=-REDUCTION,
        taxable=False,
    )
    draft.total = DISCOUNTED_TOTAL
    draft.save(update_fields=["total"])
    return draft


def discount_account_code():
    account_id = ledger_selectors.gl_account_id_for_designation(
        ledger_chart.DISCOUNT_CONTRA_REVENUE
    )
    assert account_id, "the seeded chart carries an account for the discount designation"
    return ledger_models.LedgerAccount.objects.get(pk=account_id).code


# ═══════════════════════════════════════════════════════════════════════════
# tc1 — THE DEFECT ITSELF: a discounted bill issues
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc1__a_discounted_bill_issues(brazos, dana):
    """DEF-536 — *"every bill for every customer with a discount"*.

    Before the PO's ruling, `_gl_account_for` had no branch for kind
    `discount`, so the line fell off the bottom of the function and BR-BIL-010
    refused the WHOLE bill with the generic *"line kind has no GL rule"*
    sentence. The bill drafted, the preview showed the reduction, and issue was
    impossible.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_discounted_draft(brazos, account, run)

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        assert bill.status == models.INVOICE_ISSUED
        assert D(bill.total) == DISCOUNTED_TOTAL


# ═══════════════════════════════════════════════════════════════════════════
# tc2 — THE ENTRY A FINANCE PERSON READS, both accounts and both figures
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc2__the_reduction_debits_its_own_account_and_revenue_is_untouched(brazos, dana):
    """The PO's ruling, as four numbers in `journal_lines`.

        DR  1200 accounts receivable                90.58
        DR  4760 customer discounts (contra-revenue) 10.00
        CR  4100 electric usage                     82.08
        CR  4105 electric base                      18.50

    **The assertion that carries the ruling is `82.08`.** Netted into the
    service's own account the same bill credits 4100 with **72.08** and the
    10.00 vanishes from every report — which is the form the PO rejected in
    those words: *"dont keep them in same"*.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_discounted_draft(brazos, account, run)

        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        entries = list(journal_entries(brazos))
        assert len(entries) == 1, "one bill, one entry"
        totals = journal_totals(brazos, entries[0])

        ar_code = ledger_models.LedgerAccount.objects.get(
            pk=ledger_selectors.gl_account_id_for_designation("accounts_receivable")
        ).code
        assert totals[ar_code]["debit"] == DISCOUNTED_TOTAL  # 90.58

        # THE RULING, in one line: the discount's own account, on the DEBIT side.
        assert totals[discount_account_code()]["debit"] == REDUCTION  # 10.00
        assert totals[discount_account_code()]["credit"] == D("0")

        # THE OTHER HALF OF THE RULING: the service's revenue is NOT reduced.
        assert totals["4100"]["credit"] == USAGE_AMOUNT == D("82.08")  # not 72.08
        assert totals["4105"]["credit"] == BASE_AMOUNT == D("18.50")

        debited = sum(bucket["debit"] for bucket in totals.values())
        credited = sum(bucket["credit"] for bucket in totals.values())
        assert debited == credited == ENTRY_BOTH_SIDES  # 100.58, both sides
        # …and the entry is BIGGER than the bill, on both sides. Stated because
        # it is the one thing about this entry that surprises a reader who knows
        # the pre-ruling shape, where every entry footed to `invoices.total`.
        assert ENTRY_BOTH_SIDES == D(bill.total) + REDUCTION
        assert bill.posting.debits == bill.posting.credits == ENTRY_BOTH_SIDES


# ═══════════════════════════════════════════════════════════════════════════
# tc3 — the bucket the handoff builds, and its SIDE
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc3__the_discount_bucket_is_a_debit_of_the_absolute_value(brazos, dana):
    """`PostingBucket.side` — the sign travels as a SIDE, never as an amount.

    B2 §2 is `CHECK (amount >= 0)`, so the ledger cannot take a negative figure
    at all; a debit bucket therefore carries the ABSOLUTE value. The BILL's own
    tie-out still reads the SIGNED sum, which is why `invoices.total` (90.58) is
    reproduced by 82.08 + 18.50 − 10.00.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_discounted_draft(brazos, account, run)
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        buckets = {bucket.gl_account_id: bucket for bucket in bill.posting.buckets}
        discount_id = ledger_selectors.gl_account_id_for_designation(
            ledger_chart.DISCOUNT_CONTRA_REVENUE
        )
        discount_bucket = buckets[str(discount_id)]
        assert discount_bucket.side == posting_seam.SIDE_DEBIT
        assert discount_bucket.amount == REDUCTION  # the ABSOLUTE value
        assert discount_bucket.signed_amount == -REDUCTION  # what the BILL sees

        # Every other bucket is a credit, exactly as §7 has always said.
        for bucket in bill.posting.buckets:
            if bucket is discount_bucket:
                continue
            assert bucket.side == posting_seam.SIDE_CREDIT

        # `Σ signed_amount == invoices.total` — the tie-out, unchanged.
        assert sum(bucket.signed_amount for bucket in bill.posting.buckets) == D(bill.total)


# ═══════════════════════════════════════════════════════════════════════════
# tc4 — OQ-152 IS NOT WEAKENED. The refusal still fires everywhere else.
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc4__a_negative_bucket_on_any_other_account_still_refuses(brazos, dana):
    """**The case that must never be softened to make a discount pass.**

    OQ-152 closed 2026-08-12: *"a bill whose GL bucket sums below zero REFUSES
    to issue"*. The 2026-08-28 ruling signs ONE case — a negative bucket on the
    tenant's own discount account — and removes the case that made the state
    reachable at all. It signs nothing else. A negative USAGE line still drives
    the electric revenue bucket below zero, and that still refuses by name, with
    the bill left a DRAFT and nothing in the books.
    """
    with tenant_ctx(brazos):
        from apps.tenancy import models as tenancy_models

        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run, invoice_no="BL-2607-000537")
        models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=draft,
            account=account,
            service=tenancy_models.Service.objects.get(code="electric"),
            kind="usage",
            description="Goodwill discount",
            amount=D("-100.00"),
            taxable=True,
        )
        draft.total = SUBTOTAL - D("100.00")
        draft.save(update_fields=["total"])

        with pytest.raises(BillingRuleError, match="OQ-152") as refusal:
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        assert issue._reason_for(refusal.value) == issue.ISSUE_POSTING_NEGATIVE_BUCKET
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        assert not journal_entries(brazos).exists()


# ═══════════════════════════════════════════════════════════════════════════
# tc5 — an unmapped designation REFUSES, and nothing is netted
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc5__no_discount_account_refuses_and_never_falls_back_to_revenue(brazos, dana):
    """A tenant who has deactivated the discount account (IS-1).

    The refusal names the designation and points at Settings → Configure. What
    it must NOT do is fall back to the service's revenue account: a discount
    netted into electric revenue is indistinguishable from electricity sold
    cheaper, on a record that freezes the moment it issues (hard rule 4).
    """
    with tenant_ctx(brazos):
        from django.utils import timezone

        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_discounted_draft(brazos, account, run)

        row = ledger_models.LedgerAccount.objects.get(
            pk=ledger_selectors.gl_account_id_for_designation(ledger_chart.DISCOUNT_CONTRA_REVENUE)
        )
        row.deleted_at = timezone.now()  # IS-1 deactivate-first
        row.save(update_fields=["deleted_at"])

        # Matched on the SENTENCE A CLERK READS, not on the designation string:
        # CR-016 moved the rule ids out of this message and into the comment
        # beside the raise, so an assertion on the id would have been testing
        # the provenance rather than the copy the break list shows.
        with pytest.raises(BillingRuleError, match="set up to hold discounts"):
            issue.issue_invoice(
                draft,
                issued_at=ISSUED_AT,
                template_id=TEMPLATE_ID,
                template_version=TEMPLATE_VERSION,
                actor=dana,
            )
        assert models.Invoice.objects.get(pk=draft.pk).status == models.INVOICE_DRAFT
        assert not journal_entries(brazos).exists()
        # And nothing landed in the service's revenue account by another door.
        assert (
            models.InvoiceLine.objects.filter(invoice=draft, kind="discount")
            .values_list("gl_account_id", flat=True)
            .first()
            is None
        )


# ═══════════════════════════════════════════════════════════════════════════
# tc6 — the THIRTEENTH designation, and its unsigned seed account
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc6__the_designation_is_the_thirteenth_and_its_account_is_unsigned(brazos):
    """The chart's own half of the ruling.

    `signed=False` is DATA and not a comment (hard-won law 1): the RULING is
    signed, and the CODE and NAME are this lane's reading of the chart's ladder,
    awaiting a HUMAN-GUIDE §6 finance re-sign. B5 line 74 is ❄️ un-edited.
    """
    assert ledger_chart.DISCOUNT_CONTRA_REVENUE in ledger_chart.GL_DESIGNATIONS
    # ⚠ **AMENDED 2026-09-23 (`DEF-LED-6224`) — THIS PINNED `== 13` AND HAD BEEN
    # RED SINCE 2026-09-02**, when `CR-060` T7b/T7f added three designations;
    # T15 made it seventeen the next day and `CR-136-BRC07` §3.3 eighteen on
    # 2026-09-23. **It is the identical fault the comment eight lines below
    # already names about the sibling assertion** — *"pinning the whole list
    # made every correct arrival look like a broken test, which is how two lanes
    # came to land over a red one"* — and that amendment fixed one assertion and
    # walked past this one.
    # **The question THIS case asks is about the discount**, so it asks it about
    # the discount: the designation is in the closed set, and the set is still
    # CLOSED — a designation reaching the tuple without reaching `chart.py`'s own
    # enumeration is impossible by construction, and the COUNT is
    # `tests/test_us_led_005_gl_designations.py`'s to own.
    assert len(set(ledger_chart.GL_DESIGNATIONS)) == len(ledger_chart.GL_DESIGNATIONS)
    # ⚠ **AMENDED 2026-09-02 (`DEF-3360`) — THIS PINNED `== ("4760",)` AND HAD
    # BEEN RED SINCE `CR-063` LANDED THAT MORNING.** The register held eleven
    # codes by then: `4155 Fire` and `CR-066`'s nine, each seeded `signed=False`
    # exactly as this row is, and 67 more arrived with `CR-061` statement (1) the
    # same day. **The question this case asks is about THIS ROW**, so it asks it
    # about this row: 4760 is in the register, and the register is the chart's
    # own derived answer. Pinning the whole list made every correct arrival look
    # like a broken test, which is how two lanes came to land over a red one.
    assert "4760" in ledger_chart.PENDING_FINANCE_RE_SIGN
    assert ledger_chart.PENDING_FINANCE_RE_SIGN == tuple(
        row.code for row in ledger_chart.SEED_CHART if not row.signed
    )
    with tenant_ctx(brazos):
        # It is SEEDED — the difference from `budget_variance`, which was ruled
        # into existence with no account and refused for three days. An unseeded
        # designation would reproduce DEF-536 for every fresh tenant.
        # ⚠ 4300 until CR-061 (PO 2026-09-01) re-filed it; the type moved with
        # it, from `revenue` to `contra_revenue`. Resolved by DESIGNATION here
        # and everywhere, which is why the renumber touched no posting code.
        assert discount_account_code() == "4760"


# ═══════════════════════════════════════════════════════════════════════════
# DEF-537 — corrections and back-bills re-price WITH the discount
# ═══════════════════════════════════════════════════════════════════════════
def test_def537_tc7__a_correction_reprices_with_the_accounts_discounts(brazos, dana, monkeypatch):
    """DEF-537 — `corrections.recompute` passed NO `discounts=` at all.

    Both ends were built and the CALL was missing, which is DEF-502's own shape
    one door over (hard-won law 2). The asymmetry it produced: the ORIGINAL bill
    carried the reduction and the CORRECTION of the same period did not, so a
    corrected discounted customer silently lost their subsidy.

    Asserted at the SEAM rather than through a second live fixture: what the
    defect is about is one keyword argument reaching `price_bill`, so the test
    captures the call. A live end-to-end discount already has its case in
    `test_def_502_discount_stage.py`; duplicating it here would test the engine
    twice and this wire not at all.
    """
    seen: dict = {}

    def _capture(**kwargs):
        seen.update(kwargs)
        raise RuntimeError("captured")

    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = an_authorised_run(brazos, dana)
        draft = a_priced_draft(brazos, account, run, invoice_no="BL-2607-000538")

        rule = _a_seam_discount()
        # The three reads BEFORE the call under test are stubbed, deliberately:
        # `billable_account` / `gather_single` are the correction path's own
        # scoping and are covered by `test_us_bil_015_single_correction.py`.
        # What is asserted here is the ONE thing DEF-537 is about — which
        # keyword arguments reach the pricing seam.
        monkeypatch.setattr(corrections.single, "billable_account", lambda account_id: object())
        monkeypatch.setattr(
            corrections.single,
            "gather_single",
            lambda scope, **kwargs: object(),
        )
        monkeypatch.setattr(
            corrections.rating_seam, "price_bill", lambda **kwargs: _capture(**kwargs)
        )
        monkeypatch.setattr(
            corrections,
            "resolve_subscription",
            lambda data: _SubscriptionWithDiscounts(rule),
        )
        monkeypatch.setattr(corrections, "measure_consumption", lambda sub, data: _NoUsage())

        with pytest.raises(RuntimeError, match="captured"):
            corrections.recompute(draft)

    assert "discounts" in seen, (
        "corrections.recompute must pass the account's granted discounts — without it a "
        "corrected period re-prices at FULL TARIFF while the original bill carried a "
        "reduction (DEF-537)"
    )
    assert seen["discounts"] == (rule,)


def test_def537_tc8__a_back_bill_applies_the_discount_once_on_the_final_pass(monkeypatch):
    """DEF-537, the other caller — and the extra rule this one needs.

    `price_day_weighted` makes ONE `price_bill` call per proration FACTOR and
    carries the earlier passes' lines into the last one, so that the tax pass
    runs exactly once over the whole bill (B4.2, OQ-155). A discount is
    bill-level for the same reason (BR-RAT-071), so it must ride the SAME way:
    empty on every carrying pass, real on the final one. Applied per bucket, a
    six-month catch-up spanning a tariff change would reduce the customer two or
    three times.
    """
    from apps.billing import backbill

    calls: list[dict] = []

    def _fake(**kwargs):
        calls.append(kwargs)
        return _PricedLines()

    monkeypatch.setattr(backbill.rating_seam, "price_bill", _fake)
    rule = _a_seam_discount()
    usages = [
        _usage_at(Fraction_days=31, cycle=31, discounts=(rule,)),
        _usage_at(Fraction_days=10, cycle=31, discounts=(rule,)),
    ]
    backbill.price_day_weighted(usages)

    assert len(calls) == 2, "two proration factors, two calls (OQ-155)"
    carrying, final = calls[0], calls[1]
    # The carrying pass takes no taxes, no fees and — the new clause — no
    # discounts, so R6 does not run twice over one bill.
    assert carrying["discounts"] == ()
    assert carrying["taxes"] == ()
    assert final["discounts"] == (rule,)


# ── fixture plumbing for the two seam captures ─────────────────────────────
def _a_seam_discount():
    from apps.billing import rating_seam

    return rating_seam.DiscountRule(
        code="SENIOR",
        name="Senior citizen discount",
        discount_type="percentage",
        value=D("10"),
        currency="USD",
        applies_to="whole_bill",
    )


class _SubscriptionWithDiscounts:
    """The shape `resolve_subscription` returns, narrowed to what the call reads."""

    def __init__(self, rule):
        from apps.billing import rating_seam

        self.discounts = (rule,)
        self.taxes = ()
        self.fees = ()
        self.currency = "USD"
        self.tax_exempt = False
        self.period = rating_seam.BillingPeriod(cycle_days=30, service_days=30)


class _NoUsage:
    measured: tuple = ()
    unmeasured: tuple = ()


class _PricedLines:
    lines: tuple = ()


def _usage_at(*, Fraction_days, cycle, discounts):
    from apps.billing import rating_seam

    class _Sub:
        period = rating_seam.BillingPeriod(cycle_days=cycle, service_days=Fraction_days)
        currency = "USD"
        tax_exempt = False
        taxes: tuple = ()
        fees: tuple = ()

    _Sub.discounts = discounts

    class _Usage:
        subscription = _Sub()
        measured: tuple = ()
        unmeasured: tuple = ()

    return _Usage()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-009@6a57121 (sha1[:7] of the authorities this slice was
#         authored from, newline-joined in order: 12-governance/10-defect-log.csv
#         — DEF-536 and DEF-537 · 12-governance/02-decision-log.md — the
#         2026-08-28 PO ruling verbatim, and OQ-152's closure it composes with ·
#         04-docs/05-modules/07-billing/02-business-rules.md — BR-BIL-010/011/055
#         and the new BR-BIL-790/791/792 · 04-docs/02-decisions/05-golden-tests.md
#         — B5 GT-1 ❄️, 82.08 + 18.50 = 100.58, the bill every figure here is
#         built on)
# generated: 2026-08-28 by the DEF-536/DEF-537 discount-posting lane
# checklist: A✔ B✔ C✔ D=n/a(no API half — the GL mapping surface under Settings → Configure already exists) E=n/a(no screen half; the S31.2 preview renders lines generically and already showed the reduction) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 ledger posting, HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED FIRST at the lane's starting commit — tc1..tc3, tc5 and tc6
#         all fail there, tc1 with `BillingRuleError: line kind 'discount' has
#         no GL rule`. tc4 is GREEN before and after, deliberately: it is the
#         guard that must not move. golden-verify 33/33 before AND after
# exceptions: tc7 and tc8 capture the SEAM CALL rather than driving a live
#         discounted correction end to end. What DEF-537 is about is one
#         keyword argument reaching `price_bill`; the engine's own behaviour on
#         that argument is already pinned by test_def_502_discount_stage.py, and
#         a second live fixture would exercise the engine twice and this wire
#         not at all · the grant write (`discount_grants`) and the
#         `suspended_funding_exhausted` flip are NOT built and are filed with
#         their reason — the discount line names no programme, so an issued bill
#         cannot say which enrolment to deplete (see the module docstring)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# tc9 — THE WHOLE THING, ON THE LIVE PATH: enrol → bill → issue → correct
# ═══════════════════════════════════════════════════════════════════════════
def test_def536_tc9__a_real_enrolled_account_bills_issues_and_corrects_with_its_discount(
    brazos, dana
):
    """The two defects end to end, on the path a bill run actually walks.

    Nothing is hand-built here and nothing is stubbed: an account enrolled in a
    real programme, gathered by the real gather, priced by the real engine,
    drafted, ISSUED into the real books, and then re-priced by
    `corrections.recompute` — which is the exact call DEF-537 was filed against.

    **The asymmetry the two defects produced, made visible in one case:** the
    original bill carried the reduction, and before today the correction did
    not. Asserted as an EQUALITY between the two, so a correction that quietly
    drops the discount fails here whatever the tariff happens to be.
    """
    from apps.billing import runs
    from tests.test_def_502_discount_stage import _enrolled_account, _gathered

    with tenant_ctx(brazos):
        account, _plan = _enrolled_account(brazos, dana, bind_to_plan=True)
        data = _gathered(account)
        # A run whose release gate has been passed and whose CYCLE carries a
        # bill day and due terms — BR-BIL-024 derives the due date from them and
        # refuses a bill that has neither, so a draft with no run cannot issue
        # whatever else is right about it.
        run = an_authorised_run(brazos, dana, key="2026-07|def536-live")
        draft = runs.calculate_account(data, bill_run=run, service_date=date(2026, 7, 31))

        original_discounts = [row for row in draft.lines.all() if row.kind == "discount"]
        assert len(original_discounts) == 1, "the drafted bill carries the reduction (DEF-502)"
        reduction = original_discounts[0].amount
        assert reduction < 0

        # ── DEF-536: it ISSUES, and the reduction lands in its own account ──
        bill = issue.issue_invoice(
            draft,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )
        assert bill.status == models.INVOICE_ISSUED

        entry = journal_entries(brazos).get(source_id=bill.pk)
        totals = journal_totals(brazos, entry)
        assert totals[discount_account_code()]["debit"] == -reduction
        assert totals[discount_account_code()]["credit"] == D("0")

        # The books balance, and by MORE than the bill — the discount is on the
        # debit side beside AR, which is what contra-revenue means.
        debited = sum(bucket["debit"] for bucket in totals.values())
        credited = sum(bucket["credit"] for bucket in totals.values())
        assert debited == credited == D(bill.total) - reduction

        # ── DEF-537: the CORRECTION carries the same reduction ──────────────
        recomputed = corrections.recompute(bill)
        corrected = [line for line in recomputed.lines if line.kind == "discount"]
        assert corrected, (
            "the correction re-priced WITHOUT the discount — DEF-537. The original bill "
            f"carried {reduction} and the corrected period carried nothing, so the customer "
            "would be handed back less than they are owed"
        )
        assert sum(line.amount for line in corrected) == reduction
