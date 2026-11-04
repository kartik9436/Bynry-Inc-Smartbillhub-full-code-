# ── Trace ──────────────────────────────────────────────
# Epics:    EP-PAY-02 (allocation — how money meets bills)
#           Screens: — (the result renders as S33's "Applied to" column)
#           NOTE: no US-ID is cited in this header ON PURPOSE. These tests cover
#           the PURE calculation, not the US-PAY-006 write path (allocations
#           rows, balance read-model, audit) that has no tables yet — so the
#           header does not claim the story ships. The TC numbers in the test
#           NAMES are the story's, and each docstring says exactly which half of
#           its TC is covered. Same precedent as apps/billing/late_fee.py.
# Rules:    BR-PAY-010 (order: DEFAULT oldest-invoice-first; within an invoice
#           usage+base → taxes → fees LAST; overpayment → account credit;
#           tenant-configurable) · BR-PAY-001 (default = oldest open bill;
#           staff options specific / carry credit / split) · BR-PAY-002
#           (append-only; a correction is a new row) · BR-PAY-021 (allocation
#           is evaluated off the POSTING date)
# Golden:   GT-7 — B5 ❄️ FROZEN 2026-08-08. The frozen FIGURE is asserted in
#           06-backend/tests/golden/test_gt07_partial_allocation.py; this file
#           asserts the order options, the refusals, the PE-2/3/4 scenarios
#           EP-PAY-02 §7 states as CONFIRMED finance calculations, and the two
#           figures the PO ratified in chat on 2026-08-11 (the 21.90 / 20.97 /
#           5.00 composition of PE-2's 47.87, and the named-bill instruction).
# Tests:    this file
# Impacts:  apps/payments/allocation.py · apps/payments/services.py
# ───────────────────────────────────────────────────────
"""The allocation engine's rules — the parts B5 GT-7 does not state in figures.

Serves US-PAY-006 (the allocation engine) without shipping it.

B5 GT-7 freezes ONE case: two bills, an oldest-first partial payment, three
figures. Everything else BR-PAY-010 and BR-PAY-001 confirm — the configurable
order, the carry-credit option, the overpayment credit, the refusals — is stated
in words and in EP-PAY-02 §7's worked scenarios (PE-2/3/4, marked CONFIRMED),
and is pinned here.

AMENDED 2026-08-11 by two PO rulings, each put in plain English with a figure
and each answered "option A — build it now":

  #5 the WITHIN-invoice class order (usage+base → taxes → fees LAST). Shown:
     *"$110 against a $157.87 bill leaves $47.87 outstanding. Correct. But we
     can't say it's $21.90 usage + $20.97 tax + $5.00 fee."* Driver: tax
     remittance. That breakdown was CONFIRMED law that the contract could not
     express; it now can, and the figure the PO was shown is asserted below so
     drift goes RED.
  #6 `specific` and `split`. Shown: *"a customer sends $200 and says 'put it on
     the September bill'; today the system applies oldest-first instead."* Both
     used to refuse with NotImplementedError for want of a target on the seam.

    ⚠️ STILL NOT ASSERTED HERE, and deliberately: the composites B5 routes to
    GT-35..50 (the PE workbook). Those are frozen fixtures in a range this lane
    does not bind, and nothing below claims to reproduce one. What is asserted
    is US-PAY-006 TC-1 / EP-PAY-02 §7's own PE-2 figures and the figures shown
    to the PO — CONFIRMED finance calculations, not B5 numbers.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.payments import allocation as payments_allocation
from apps.payments import services

USAGE_BASE = rating_seam.CLASS_USAGE_BASE
TAXES = rating_seam.CLASS_TAXES
TENANT_DEFINED = rating_seam.CLASS_TENANT_DEFINED
FEES = rating_seam.CLASS_FEES


@pytest.fixture
def a_tenant_defined_class(monkeypatch):
    """The tenant HAS defined the fourth class — the ledger publishes its members.

    PO ruling 2026-08-11 (OQ-109, option C as amended): the class between taxes
    and fees "can be service fees or it can be special fees anything" and the
    tenant defines it IN THE LEDGER. Nothing in this repo publishes
    `apps.ledger.selectors.allocation_class_members` yet, so the tenant side of
    the ruling is stood up here rather than assumed — which is also what makes
    the unconfigured refusal (the real state today) a separate, provable case.
    """
    from apps.ledger import selectors as ledger_selectors

    monkeypatch.setattr(
        ledger_selectors,
        payments_allocation.TENANT_CLASS_READ,
        lambda: ("service_fee", "special_fee"),
        raising=False,
    )
    return ("service_fee", "special_fee")


def bill(
    number: str,
    balance: str,
    issued_on: date | None = None,
    *,
    usage_base: str | None = None,
    taxes: str | None = None,
    tenant_defined: str | None = None,
    fees: str | None = None,
    composition: tuple[rating_seam.ClassBalance, ...] | None = None,
) -> rating_seam.OpenInvoice:
    """One open bill, stated the way the published seam states it.

    The four keyword amounts are the WITHIN-INVOICE composition BR-PAY-010
    walks (usage+base → taxes → the tenant-defined class → fees LAST). Omitting
    them states NO composition, which is B5 GT-7's case exactly and stays a
    legal input.
    """
    if composition is None:
        composition = tuple(
            rating_seam.ClassBalance(line_class=line_class, balance=Decimal(amount))
            for line_class, amount in (
                (USAGE_BASE, usage_base),
                (TAXES, taxes),
                (TENANT_DEFINED, tenant_defined),
                (FEES, fees),
            )
            if amount is not None
        )
    return rating_seam.OpenInvoice(
        number=number,
        balance=Decimal(balance),
        issued_on=issued_on,
        composition=composition,
    )


def pe2_bill(number: str = "BL-2608-018410") -> rating_seam.OpenInvoice:
    """EP-PAY-02 §7 PE-2 verbatim: 247.87 = usage+base 221.90 · taxes 20.97 · late 5.00."""
    return bill(number, "247.87", usage_base="221.90", taxes="20.97", fees="5.00")


def target(invoice_number: str, amount: str | None = None) -> rating_seam.AllocationTarget:
    """One invoice the staff member NAMED, with the amount against it (BR-PAY-001)."""
    return rating_seam.AllocationTarget(
        invoice_number=invoice_number,
        amount=None if amount is None else Decimal(amount),
    )


def allocate(payment: str, invoices, order: str = "oldest_first", **kwargs):
    return services.allocate_payment(
        payment_amount=Decimal(payment),
        open_invoices=tuple(invoices),
        order=order,
        **kwargs,
    )


# ── The seam is WIRED, not merely built (hard-won law 2) ────────────────────


def test_us_pay_006_seam_resolves_to_this_module():
    """`rating_seam.allocate_payment` reaches THIS implementation.

    A pure function nothing resolves is dead code that passes its own tests.
    The seam looks its owner up as `apps.payments.services.allocate_payment` at
    call time, so this asserts the published name exists and is what runs.
    """
    assert services.allocate_payment is payments_allocation.allocate_payment

    through_the_seam = rating_seam.allocate_payment(
        payment_amount=Decimal("120"),
        open_invoices=(bill("BL-A", "100"), bill("BL-B", "147.30")),
    )
    assert through_the_seam.applied_to("BL-A") == Decimal("100")


def test_us_pay_006_default_order_is_the_shipped_default_not_a_hardcoded_law():
    """BR-PAY-010: oldest-first is the DEFAULT, and it is reachable as one.

    Called with no `order`, the engine must behave as `oldest_first` — and the
    fact that another order changes the answer is what proves the default is a
    setting rather than the only thing implemented (T4-20 / T7-13 exist for it).
    """
    invoices = (bill("BL-OLD", "100"), bill("BL-NEW", "147.30"))

    defaulted = allocate("120", invoices)
    explicit = allocate("120", invoices, order="oldest_first")
    reconfigured = allocate("120", invoices, order="newest_first")

    assert defaulted == explicit
    assert defaulted != reconfigured


# ── The CONFIRMED finance calculations (EP-PAY-02 §7) ───────────────────────


def test_us_pay_006_tc1_pe2_partial_payment_leaves_the_remainder_outstanding():
    """TC-1 (PE-2) — the INVOICE-LEVEL half, at a bill that states no lines.

    EP-PAY-02 §7: bill 247.87 (usage+base 221.90 · taxes 20.97 · late 5.00),
    pay 200 → outstanding 47.87. Deliberately kept as it was written before the
    composition landed, because it is the proof that the class walk did NOT
    change any per-invoice amount: a bill handed over with no breakdown is
    allocated to exactly the same figure it was on 2026-08-11 morning, which is
    the same property that keeps B5 GT-7 frozen. The three-way split of the
    47.87 is asserted separately, on a bill that states one.
    """
    outcome = allocate("200.00", (bill("BL-2608-018410", "247.87"),))

    assert outcome.applied_to("BL-2608-018410") == Decimal("200.00")
    assert outcome.remaining_balance == Decimal("47.87")
    assert outcome.credit_carried == Decimal("0")


def test_us_pay_006_tc2_pe3_oldest_bill_is_settled_in_full_before_the_next():
    """TC-2 (PE-3) — open Jun 142.30 + Jul 247.87, pay 300.

    EP-PAY-02 §7 verbatim: "Jun paid in full, Jul gets 157.70, Jul balance
    90.17". This is GT-7's rule at a second set of figures, and it is the whole
    content of oldest-first: the older bill is not partially paid while a newer
    one waits.
    """
    outcome = allocate(
        "300.00",
        (bill("BL-2606-018091", "142.30"), bill("BL-2607-018205", "247.87")),
    )

    assert outcome.applied_to("BL-2606-018091") == Decimal("142.30")
    assert outcome.applied_to("BL-2607-018205") == Decimal("157.70")
    assert outcome.remaining_balance == Decimal("90.17")
    assert outcome.credit_carried == Decimal("0")


def test_us_pay_006_tc3_pe4_overpayment_carries_as_account_credit():
    """TC-3 (PE-4) — open 292.87, pay 350 → bills settled + credit 57.13 carries.

    BR-PAY-010's overpayment clause. The remainder is REPORTED, never dropped;
    US-PAY-007 owns what happens to it after that (auto-apply, refundable) and
    none of that lifecycle is claimed here.
    """
    outcome = allocate("350.00", (bill("BL-2608-018410", "292.87"),))

    assert outcome.applied_to("BL-2608-018410") == Decimal("292.87")
    assert outcome.remaining_balance == Decimal("0")
    assert outcome.credit_carried == Decimal("57.13")


def test_us_pay_006_exact_payment_settles_without_inventing_a_credit():
    """The boundary between TC-2 and TC-3: paying exactly what is owed.

    Neither an outstanding remainder nor a credit — the case where an
    off-by-one in the comparison would show up as a phantom 0.00 credit row.
    """
    outcome = allocate("247.30", (bill("BL-A", "100"), bill("BL-B", "147.30")))

    assert outcome.remaining_balance == Decimal("0")
    assert outcome.credit_carried == Decimal("0")
    assert [a.invoice_number for a in outcome.allocations] == ["BL-A", "BL-B"]


# ── The WITHIN-invoice class order (BR-PAY-010) ─────────────────────────────
#
# PO ruling 2026-08-11 (#5, option A — "build it now", stated driver: tax
# remittance). Until that ruling the class walk was a recorded contract
# boundary: the seam carried no composition and none could be returned. It now
# does, and these are the figures the PO was shown.


def test_us_pay_006_tc1_pe2_outstanding_47_87_is_21_90_usage_plus_20_97_tax_plus_5_00_fee():
    """TC-1 (PE-2) — the COMPOSITION half, which used to be unexpressible.

    EP-PAY-02 §7 verbatim: bill 247.87 (usage+base 221.90 · taxes 20.97 · late
    5.00), pay 200 → "covers usage+base only; outstanding 47.87 (21.90 + 20.97 +
    5.00)". The 200 meets usage+base and stops there — that IS "fees LAST" at
    this figure — so tax and fee are untouched and stand outstanding in full.
    """
    outcome = allocate("200.00", (pe2_bill(),))

    applied = outcome.allocations[0]
    assert applied.applied_to_class(USAGE_BASE) == Decimal("200.00")
    assert [entry.line_class for entry in applied.by_class] == [USAGE_BASE]  # nothing else met

    assert outcome.remaining_of(USAGE_BASE) == Decimal("21.90")
    assert outcome.remaining_of(TAXES) == Decimal("20.97")
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    assert outcome.remaining_balance == Decimal("47.87")
    assert sum(entry.balance for entry in outcome.remaining_by_class) == Decimal("47.87")


def test_us_pay_006_the_composition_figure_the_po_ratified_on_2026_08_11():
    """The figure put to the PO in plain English, and the answer that came back.

    Shown 2026-08-11: *"$110 against a $157.87 bill leaves $47.87 outstanding.
    Correct. But we can't say it's $21.90 usage + $20.97 tax + $5.00 fee."*
    Options A (build the breakdown now — needed for tax remittance) / B (later);
    **the PO answered A**. This asserts that exact figure so drift goes RED
    (CLAUDE.md: "a test asserts the ratified figure").

    The bill's own composition is DERIVED from what the PO was shown, not
    invented: fees are paid LAST (BR-PAY-010), so an untouched tax of 20.97 and
    an untouched fee of 5.00 are their full balances, and usage+base is
    157.87 − 20.97 − 5.00 = 131.90, of which 110 is met, leaving 21.90. Same
    rule as PE-2 above at a second bill total — the remainder is identical
    because only the usage+base balance differs.
    """
    september = bill("BL-2609-018602", "157.87", usage_base="131.90", taxes="20.97", fees="5.00")

    outcome = allocate("110.00", (september,))

    assert outcome.remaining_balance == Decimal("47.87")
    assert outcome.remaining_of(USAGE_BASE) == Decimal("21.90")
    assert outcome.remaining_of(TAXES) == Decimal("20.97")
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    assert outcome.allocations[0].applied_to_class(USAGE_BASE) == Decimal("110.00")


def test_us_pay_006_fees_are_paid_last_not_merely_paid_late():
    """BR-PAY-010's ordering claim, at the figure where it is observable.

    221.90 + 20.97 = 242.87, so a 242.87 payment is exactly enough for usage+base
    AND taxes and not one cent of the 5.00 fee. A walk that took fees first, or
    that spread the money pro-rata, would leave a different class outstanding at
    the same total — which is why the total alone never proved the order.
    """
    outcome = allocate("242.87", (pe2_bill(),))

    applied = outcome.allocations[0]
    assert applied.applied_to_class(USAGE_BASE) == Decimal("221.90")
    assert applied.applied_to_class(TAXES) == Decimal("20.97")
    with pytest.raises(AssertionError):
        applied.applied_to_class(FEES)  # no row for money that did not move

    assert outcome.remaining_balance == Decimal("5.00")
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    assert outcome.remaining_of(TAXES) == Decimal("0")


def test_us_pay_006_a_payment_that_stops_inside_the_tax_class_splits_it_exactly():
    """The mid-class boundary: 230.00 clears usage+base and part of the tax.

    230.00 − 221.90 = 8.10 into taxes, leaving 12.87 of tax and the whole 5.00
    fee — 17.87 outstanding, which is 247.87 − 230.00. The class walk never
    invents or loses a cent inside the bill either.
    """
    outcome = allocate("230.00", (pe2_bill(),))

    applied = outcome.allocations[0]
    assert applied.applied_to_class(USAGE_BASE) == Decimal("221.90")
    assert applied.applied_to_class(TAXES) == Decimal("8.10")
    assert sum(entry.applied for entry in applied.by_class) == Decimal("230.00")

    assert outcome.remaining_of(TAXES) == Decimal("12.87")
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    assert outcome.remaining_balance == Decimal("17.87")


def test_us_pay_006_tc5_the_tenant_reorders_the_within_invoice_classes():
    """TC-5 — "Engine follows the tenant setting (config, not constant)".

    BR-PAY-010 makes the within-invoice order tenant-configurable exactly as it
    makes the between-invoice order configurable, so `class_order` is an
    argument with the CONFIRMED order as its default. TC-5's own scenario is
    "fees before taxes"; asserted here at the figure where the two orders put
    the same 5.00 in different places, plus TC-5's second half — "default order
    restored → default behavior returns".
    """
    fees_first = allocate(
        "5.00",
        (pe2_bill(),),
        class_order=(FEES, TAXES, USAGE_BASE),
    )
    assert fees_first.allocations[0].applied_to_class(FEES) == Decimal("5.00")
    assert fees_first.remaining_of(FEES) == Decimal("0")
    assert fees_first.remaining_of(USAGE_BASE) == Decimal("221.90")

    default = allocate("5.00", (pe2_bill(),))
    assert default.allocations[0].applied_to_class(USAGE_BASE) == Decimal("5.00")
    assert default.remaining_of(FEES) == Decimal("5.00")


def test_us_pay_006_the_class_vocabulary_is_stated_once_and_matches_the_seam():
    """BR-PAY-010 names FOUR classes since 2026-08-11; two modules must agree.

    `apps.payments` may not import `apps.billing` (billing calls payments), so
    the constants are mirrored rather than shared — and a mirror that can drift
    silently is how two copies of a signed order end up in one repo. Asserted
    instead of trusted.
    """
    assert payments_allocation.DEFAULT_CLASS_ORDER == rating_seam.DEFAULT_CLASS_ORDER
    assert payments_allocation.DEFAULT_CLASS_ORDER == (USAGE_BASE, TAXES, TENANT_DEFINED, FEES)
    assert payments_allocation.ALLOCATION_CLASSES == rating_seam.ALLOCATION_CLASSES


def test_us_pay_006_a_bill_that_states_no_composition_reports_none():
    """B5 GT-7's shape stays legal, and reports no breakdown rather than a guess.

    GT-7 gives two bills and no line detail at all. The per-invoice AMOUNTS are
    unaffected by the class walk, so the frozen figures still reproduce; what
    must NOT happen is a composition being reported for a bill that never stated
    one — a 47.87 invented from nothing reads exactly like a real one.
    """
    outcome = allocate("120", (bill("BL-A", "100"), bill("BL-B", "147.30")))

    assert outcome.applied_to("BL-A") == Decimal("100")
    assert outcome.remaining_by_class == ()
    assert outcome.allocations[0].by_class == ()
    with pytest.raises(AssertionError):
        outcome.remaining_of(TAXES)


def test_us_pay_006_a_composition_that_does_not_foot_to_the_balance_is_refused():
    """The classes must add up to the bill, or the breakdown is a different bill.

    221.90 + 20.97 + 5.00 = 247.87. A caller that states 247.87 with classes
    summing to 240.00 has lost 7.87 somewhere upstream, and allocating against
    the smaller figure would leave money owed that no class knows about.
    """
    with pytest.raises(ValueError) as raised:
        allocate(
            "200.00",
            (bill("BL-BAD", "247.87", usage_base="214.03", taxes="20.97", fees="5.00"),),
        )

    message = str(raised.value)
    assert "BL-BAD" in message
    assert "247.87" in message


def test_us_pay_006_a_mixed_composition_and_no_composition_list_is_refused():
    """Same refusal shape as mixed dates: a partial breakdown is a wrong one.

    Summing a tax outstanding across a bill that states its classes and one that
    does not produces an account figure that is silently short — and tax
    remittance is the PO's stated reason for having the breakdown at all.
    """
    with pytest.raises(ValueError) as raised:
        allocate("200.00", (pe2_bill(), bill("BL-NOLINES", "142.30")))

    assert "BL-NOLINES" in str(raised.value)


def test_us_pay_006_a_raw_line_kind_is_sent_to_the_tenant_defined_class_not_placed():
    """OQ-109 CLOSED 2026-08-11 — and the answer is a SLOT, not a classifier here.

    A deposit line is neither usage+base, nor a tax, nor a fee. The PO ruled it
    belongs to a fourth class between taxes and fees whose MEMBERSHIP the tenant
    defines in the ledger. What did NOT change is who maps a line kind onto a
    class: the composition is an input, and payments never reads `invoice_lines`.
    So a raw kind is still refused — but now the refusal names where it goes,
    and it no longer cites a closed question.
    """
    with pytest.raises(ValueError) as raised:
        allocate(
            "50.00",
            (
                bill(
                    "BL-DEP",
                    "100.00",
                    composition=(
                        rating_seam.ClassBalance(line_class=USAGE_BASE, balance=Decimal("60.00")),
                        rating_seam.ClassBalance(line_class="deposit", balance=Decimal("40.00")),
                    ),
                ),
            ),
        )

    message = str(raised.value)
    assert "deposit" in message
    assert TENANT_DEFINED in message
    assert "OQ-109" not in message  # closed 2026-08-11; a stub here would be stale


# ── The FOURTH class (PO ruling 2026-08-11, OQ-109 closed, option C amended) ─


def test_us_pay_006_the_four_class_order_the_po_ratified_on_2026_08_11(a_tenant_defined_class):
    """The PO's own worked figure, asserted so drift goes RED.

    Put to the PO in plain English: a payment meets usage+base first, then tax,
    then fees LAST — and a service fee or a special fee is none of those. Their
    ruling, verbatim: *"C Its own class between tax and fees - it can be service
    fees or it can be special fees anything; allow tenant user to define it in
    ledge[r]"*.

    The figure: a bill of usage+base **$100.58** + tax **$8.30** + a
    tenant-defined service fee **$15.00** + a late fee **$5.00** = **$128.88**.
    A payment of **$120.00** meets $100.58, then $8.30, then **$11.12 of the
    $15.00** — and the late fee stays LAST at **$0.00**, which is the whole
    point of BR-PAY-010's ordering and the half the amendment must not disturb.
    """
    invoice = bill(
        "BL-2608-018412",
        "128.88",
        usage_base="100.58",
        taxes="8.30",
        tenant_defined="15.00",
        fees="5.00",
    )

    outcome = allocate("120.00", (invoice,))
    applied = outcome.allocations[0]

    assert applied.applied == Decimal("120.00")
    assert applied.applied_to_class(USAGE_BASE) == Decimal("100.58")
    assert applied.applied_to_class(TAXES) == Decimal("8.30")
    assert applied.applied_to_class(TENANT_DEFINED) == Decimal("11.12")
    # The late fee is LAST: it received nothing, so it has no allocation row at
    # all — "the fee stays at $0.00" stated as the absence of a movement.
    with pytest.raises(AssertionError):
        applied.applied_to_class(FEES)
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    assert outcome.remaining_of(TENANT_DEFINED) == Decimal("3.88")
    assert outcome.remaining_balance == Decimal("8.88")


def test_us_pay_006_the_tenant_defined_class_refuses_when_the_ledger_defines_none():
    """The amendment's other half: the MEMBERSHIP is the tenant's, or it is nothing.

    The PO located the definition in the ledger. Nothing publishes
    `apps.ledger.selectors.allocation_class_members` today, so a bill stating
    the class has no definition behind it — and allocating anyway would put
    money into a class nobody defined, at the position that decides how much tax
    the tenant has collected. Fails closed (hard-won law 3), names the source,
    and names the two questions the ruling left open rather than answering one.
    """
    invoice = bill(
        "BL-2608-018413",
        "128.88",
        usage_base="100.58",
        taxes="8.30",
        tenant_defined="15.00",
        fees="5.00",
    )

    with pytest.raises(payments_allocation.AllocationClassNotConfigured) as raised:
        allocate("120.00", (invoice,))

    message = str(raised.value)
    assert payments_allocation.TENANT_CLASS_READ in message
    assert "OQ-123" in message and "OQ-119" in message


def test_us_pay_006_the_tenant_may_still_reorder_the_four(a_tenant_defined_class):
    """BR-PAY-010 ends "tenant-configurable", and adding a class did not end that.

    US-PAY-006 TC-5 is a tenant putting fees before taxes; the same tenant may
    put its own class anywhere. Asserted so the fourth class cannot quietly
    become a constant while the other three stay settings.
    """
    invoice = bill(
        "BL-2608-018414",
        "128.88",
        usage_base="100.58",
        taxes="8.30",
        tenant_defined="15.00",
        fees="5.00",
    )

    outcome = allocate("120.00", (invoice,), class_order=(USAGE_BASE, FEES, TAXES, TENANT_DEFINED))
    applied = outcome.allocations[0]

    assert applied.applied_to_class(FEES) == Decimal("5.00")
    assert applied.applied_to_class(TAXES) == Decimal("8.30")
    assert applied.applied_to_class(TENANT_DEFINED) == Decimal("6.12")
    assert outcome.remaining_of(TENANT_DEFINED) == Decimal("8.88")


def test_us_pay_006_an_unknown_class_order_entry_is_refused():
    """A misspelled tenant class order must not quietly drop a class.

    A walk that skipped `taxes` because the setting said `tax` would apply money
    to fees before taxes — the exact inversion BR-PAY-010 rules out — and every
    per-invoice total would still be right.
    """
    with pytest.raises(ValueError) as raised:
        allocate("200.00", (pe2_bill(),), class_order=(USAGE_BASE, "tax", FEES))

    assert "tax" in str(raised.value)

    with pytest.raises(ValueError):  # a class named twice is not an order either
        allocate("200.00", (pe2_bill(),), class_order=(USAGE_BASE, TAXES, TAXES, FEES))

    with pytest.raises(ValueError):  # a class the invoices state, left out entirely
        allocate("200.00", (pe2_bill(),), class_order=(USAGE_BASE, TAXES))


# ── The staff instruction: specific / split (BR-PAY-001) ────────────────────
#
# PO ruling 2026-08-11 (#6, option A — "build both now"). Both were CONFIRMED
# staff options that refused with NotImplementedError for want of a target on
# the seam; the seam now carries the named invoice and, for a split, the amount
# against each.


def test_us_pay_006_specific_pays_the_bill_the_customer_named_and_not_the_oldest():
    """The figure the PO was shown 2026-08-11: $200 "put it on the September bill".

    Verbatim: *"A customer sends $200 and says 'put it on the September bill.'
    Today the system applies oldest-first instead."* The instruction now wins:
    September's 157.87 is settled, the older August bill is untouched, and the
    42.13 the September bill could not absorb carries as an account credit
    (BR-PAY-010 overpayment → account credit · BR-PAY-012 unapplied → account
    credit). The default order at the same fixture does the opposite, which is
    what makes the instruction observable rather than decorative.
    """
    august = bill("BL-2608-018410", "247.87", issued_on=date(2026, 8, 1))
    september = bill("BL-2609-018602", "157.87", issued_on=date(2026, 9, 1))

    outcome = allocate(
        "200.00",
        (august, september),
        order="specific",
        targets=(target("BL-2609-018602"),),
    )

    assert outcome.applied_to("BL-2609-018602") == Decimal("157.87")
    with pytest.raises(AssertionError):
        outcome.applied_to("BL-2608-018410")  # the August bill was not named
    assert outcome.credit_carried == Decimal("42.13")
    assert outcome.remaining_balance == Decimal("247.87")

    oldest_first = allocate("200.00", (august, september))
    assert oldest_first.applied_to("BL-2608-018410") == Decimal("200.00")


def test_us_pay_006_specific_walks_the_classes_inside_the_bill_it_names():
    """The two rulings meet: a named bill is still paid usage+base → taxes → fees.

    BR-PAY-010's within-invoice order is not a property of the DEFAULT order —
    it governs every allocation, however the bill was chosen.
    """
    outcome = allocate(
        "200.00",
        (bill("BL-OTHER", "142.30", usage_base="142.30"), pe2_bill()),
        order="specific",
        targets=(target("BL-2608-018410"),),
    )

    assert outcome.allocations[0].applied_to_class(USAGE_BASE) == Decimal("200.00")
    assert outcome.remaining_of(TAXES) == Decimal("20.97")
    assert outcome.remaining_of(FEES) == Decimal("5.00")


def test_us_pay_006_tc4_split_applies_the_named_amount_to_each_named_bill():
    """TC-4 — "split writes one allocation row per target; Σ rows = payment amount".

    PE-3's two bills with the payment divided by the staff member rather than by
    the walk: 100.00 to the June bill and 200.00 to July. Σ = 300.00 exactly,
    and the account is left owing 390.17 − 300.00 = 90.17 — the same closing
    figure PE-3 reaches by oldest-first, reached deliberately instead.
    """
    outcome = allocate(
        "300.00",
        (bill("BL-2606-018091", "142.30"), bill("BL-2607-018205", "247.87")),
        order="split",
        targets=(target("BL-2606-018091", "100.00"), target("BL-2607-018205", "200.00")),
    )

    assert outcome.applied_to("BL-2606-018091") == Decimal("100.00")
    assert outcome.applied_to("BL-2607-018205") == Decimal("200.00")
    assert [row.invoice_number for row in outcome.allocations] == [
        "BL-2606-018091",
        "BL-2607-018205",
    ]
    assert outcome.remaining_balance == Decimal("90.17")
    assert outcome.credit_carried == Decimal("0")


def test_us_pay_006_tc4_split_of_one_directive_is_the_whole_payment():
    """TC-4's own wording — "$100 to BL-2607-018311" — at TC-4's own payment.

    With a 100.00 payment there is no "rest": one directive accounts for the
    whole of it, and the second bill is untouched.
    """
    outcome = allocate(
        "100.00",
        (bill("BL-2607-018311", "247.87"), bill("BL-2606-018091", "142.30")),
        order="split",
        targets=(target("BL-2607-018311", "100.00"),),
    )

    assert outcome.applied_to("BL-2607-018311") == Decimal("100.00")
    with pytest.raises(AssertionError):
        outcome.applied_to("BL-2606-018091")
    assert outcome.credit_carried == Decimal("0")


def test_us_pay_006_split_walks_the_classes_inside_each_named_bill():
    """A split's directive meets the same usage+base → taxes → fees order."""
    outcome = allocate(
        "242.87",
        (pe2_bill(), bill("BL-2606-018091", "142.30", usage_base="120.00", taxes="22.30")),
        order="split",
        targets=(target("BL-2608-018410", "242.87"),),
    )

    applied = outcome.allocations[0]
    assert applied.applied_to_class(USAGE_BASE) == Decimal("221.90")
    assert applied.applied_to_class(TAXES) == Decimal("20.97")
    assert outcome.remaining_of(FEES) == Decimal("5.00")
    # the untouched bill's own classes still stand in the account-level figure
    assert outcome.remaining_of(TAXES) == Decimal("22.30")
    assert outcome.remaining_of(USAGE_BASE) == Decimal("120.00")


def test_us_pay_006_a_split_whose_amounts_do_not_sum_to_the_payment_is_refused():
    """Σ rows = payment amount (TC-4). Anything else leaves money unnamed.

    Under-naming would make the engine choose a destination nobody stated;
    over-naming would apply money that was never received. Both refuse, and the
    message states both figures so the caller can see the gap.
    """
    invoices = (bill("BL-2606-018091", "142.30"), bill("BL-2607-018205", "247.87"))

    with pytest.raises(ValueError) as short:
        allocate(
            "300.00",
            invoices,
            order="split",
            targets=(target("BL-2606-018091", "100.00"),),
        )
    assert "100.00" in str(short.value) and "300.00" in str(short.value)

    with pytest.raises(ValueError) as over:
        allocate(
            "300.00",
            invoices,
            order="split",
            targets=(target("BL-2606-018091", "142.30"), target("BL-2607-018205", "200.00")),
        )
    assert "342.30" in str(over.value)


def test_us_pay_006_a_target_naming_a_bill_that_is_not_open_is_refused():
    """A named bill the account does not owe is a staff error, not an allocation.

    TC-7 puts void and draft invoices out of scope as targets; anything not in
    the open set handed to this function is exactly that case, and paying it
    would write an allocation row against a bill with no balance.
    """
    with pytest.raises(ValueError) as raised:
        allocate(
            "100.00",
            (bill("BL-2606-018091", "142.30"),),
            order="specific",
            targets=(target("BL-NOT-OPEN"),),
        )

    assert "BL-NOT-OPEN" in str(raised.value)


def test_us_pay_006_a_negative_or_zero_target_amount_is_refused():
    """A reversal is a new reversing row (BR-PAY-002), never a negative directive;
    and a directive that moves nothing is a row for money that did not move."""
    invoices = (bill("BL-A", "100"), bill("BL-B", "147.30"))

    with pytest.raises(ValueError):
        allocate(
            "50.00",
            invoices,
            order="split",
            targets=(target("BL-A", "-50.00"), target("BL-B", "100.00")),
        )

    with pytest.raises(ValueError):
        allocate(
            "50.00",
            invoices,
            order="split",
            targets=(target("BL-A", "50.00"), target("BL-B", "0")),
        )


def test_us_pay_006_a_directive_larger_than_the_bill_it_names_is_refused():
    """ "A bill never takes more than its balance" — the invariant, stated early.

    The staff member is telling the engine to put 150.00 on a 100.00 bill. The
    50.00 excess is an overpayment, which BR-PAY-010 carries as account credit;
    expressing it as an allocation would overstate what that invoice collected
    and, with the class walk, would have nowhere inside the bill to land.
    """
    with pytest.raises(ValueError) as raised:
        allocate(
            "150.00",
            (bill("BL-A", "100"),),
            order="split",
            targets=(target("BL-A", "150.00"),),
        )

    message = str(raised.value)
    assert "BL-A" in message and "100" in message


def test_us_pay_006_specific_takes_exactly_one_named_bill_and_no_amount():
    """`specific` is "pay THIS bill"; naming two, or naming an amount, is a split."""
    invoices = (bill("BL-A", "100"), bill("BL-B", "147.30"))

    with pytest.raises(ValueError) as two:
        allocate("50", invoices, order="specific", targets=(target("BL-A"), target("BL-B")))
    assert "split" in str(two.value)

    with pytest.raises(ValueError) as amount:
        allocate("50", invoices, order="specific", targets=(target("BL-A", "50"),))
    assert "split" in str(amount.value)

    with pytest.raises(ValueError):  # ...and naming none at all
        allocate("50", invoices, order="specific")

    with pytest.raises(ValueError):  # a split with no directive names nothing
        allocate("50", invoices, order="split")


def test_us_pay_006_a_split_naming_the_same_bill_twice_is_refused():
    """Two directives for one bill: `applied_to` could only report one of them."""
    with pytest.raises(ValueError):
        allocate(
            "150.00",
            (bill("BL-A", "200"),),
            order="split",
            targets=(target("BL-A", "100.00"), target("BL-A", "50.00")),
        )


def test_us_pay_006_targets_handed_to_an_ordered_walk_are_refused():
    """A named bill AND "oldest first" are two instructions; the engine obeys one.

    Silently ignoring the target would apply the money somewhere the staff
    member did not choose while the screen said otherwise.
    """
    with pytest.raises(ValueError) as raised:
        allocate("50", (bill("BL-A", "100"),), order="oldest_first", targets=(target("BL-A"),))

    assert "oldest_first" in str(raised.value)


def test_us_pay_006_specific_and_split_reach_through_the_published_seam():
    """Hard-won law 2: built is not wired — the new fields must arrive through billing.

    `rating_seam.allocate_payment` is the published entry point; a target type
    and a composition that only the payments module can express would be an
    interface nobody can call.
    """
    outcome = rating_seam.allocate_payment(
        payment_amount=Decimal("200.00"),
        open_invoices=(pe2_bill(), bill("BL-2606-018091", "142.30", usage_base="142.30")),
        order="specific",
        targets=(rating_seam.AllocationTarget(invoice_number="BL-2608-018410"),),
        class_order=rating_seam.DEFAULT_CLASS_ORDER,
    )

    assert outcome.applied_to("BL-2608-018410") == Decimal("200.00")
    assert outcome.remaining_of(TAXES) == Decimal("20.97")


# ── The order is a TENANT SETTING (BR-PAY-010) ──────────────────────────────


def test_us_pay_006_tc5_newest_first_settles_the_newest_bill_and_leaves_the_older():
    """TC-5 (order half) — the T7-13 knob: oldest-invoice-first → newest-invoice-first.

    ⚠️ NO FROZEN FIGURE COVERS THIS ORDER. B5 states none, so what is asserted
    is journey T7-13 step 4's stated outcome at its own fixture (two 97.41
    bills, payment 97.41): "Allocates to the NEWEST open invoice: August closes;
    July remains outstanding at 97.41".
    """
    july = bill("BL-2607-0101", "97.41", issued_on=date(2026, 7, 1))
    august = bill("BL-2608-0101", "97.41", issued_on=date(2026, 8, 1))

    outcome = allocate("97.41", (july, august), order="newest_first")

    assert outcome.applied_to("BL-2608-0101") == Decimal("97.41")  # August closes
    assert outcome.remaining_balance == Decimal("97.41")  # July still outstanding
    with pytest.raises(AssertionError):
        outcome.applied_to("BL-2607-0101")  # untouched — no row for money that did not move

    # ...and the same fixture under the default order does the opposite. The
    # observable difference is what T7-13 step 4 calls "a provable data fact".
    default = allocate("97.41", (july, august))
    assert default.applied_to("BL-2607-0101") == Decimal("97.41")


def test_us_pay_006_carry_credit_touches_no_bill_at_all():
    """BR-PAY-001 "carry credit" — the staff option, and US-PAY-008 TC-2's shape.

    "Reversing rows only + credit carried; no new invoice allocation." Every
    open balance stands; the whole payment becomes the account credit.
    """
    outcome = allocate("120", (bill("BL-A", "100"), bill("BL-B", "147.30")), order="carry_credit")

    assert outcome.allocations == ()
    assert outcome.remaining_balance == Decimal("247.30")
    assert outcome.credit_carried == Decimal("120")


def test_us_pay_006_an_unknown_order_is_refused_not_silently_defaulted():
    """A misspelled tenant setting must not quietly become oldest-first.

    Falling back to the default would allocate real money under an order nobody
    chose, and would look correct in every test written against the default.
    """
    with pytest.raises(ValueError) as raised:
        allocate("120", (bill("BL-A", "100"),), order="largest_first")

    message = str(raised.value)
    assert "largest_first" in message
    assert "oldest_first" in message  # the supported set is named for the caller


# ── Ordering: by date, or by the caller's sequence (never by a guess) ───────


def test_us_pay_006_dated_bills_order_by_issue_date_not_by_arrival_order():
    """Given dates, the oldest bill is the oldest by DATE.

    The list is deliberately handed over newest-first, so a function that
    trusted arrival order would pay the wrong bill first.
    """
    outcome = allocate(
        "120",
        (
            bill("BL-JUL", "147.30", issued_on=date(2026, 7, 1)),
            bill("BL-JUN", "100", issued_on=date(2026, 6, 1)),
        ),
    )

    assert [a.invoice_number for a in outcome.allocations] == ["BL-JUN", "BL-JUL"]
    assert outcome.applied_to("BL-JUN") == Decimal("100")
    assert outcome.applied_to("BL-JUL") == Decimal("20")


def test_us_pay_006_undated_bills_keep_the_callers_sequence():
    """B5 GT-7's case: "oldest" stated as a sequence, with no calendar.

    The seam's `OpenInvoice` docstring rules this explicitly — `issued_on` stays
    None and "the caller's sequence carries the ordering B5 states". No date is
    invented to stand in for it.
    """
    outcome = allocate("120", (bill("FIRST", "100"), bill("SECOND", "147.30")))

    assert [a.invoice_number for a in outcome.allocations] == ["FIRST", "SECOND"]


def test_us_pay_006_a_mixed_dated_and_undated_list_refuses_to_guess_a_placement():
    """No rule places an undated bill against a dated one — so neither does this.

    Treating None as oldest, as newest, or as "leave it where it sits" are three
    different allocations of real money and nothing signed picks one.
    """
    with pytest.raises(ValueError) as raised:
        allocate(
            "120",
            (bill("BL-DATED", "100", issued_on=date(2026, 6, 1)), bill("BL-UNDATED", "147.30")),
        )

    assert "BL-UNDATED" in str(raised.value)


# ── Money: hard rule 2, and the absence of a rounding event ────────────────


def test_us_pay_006_a_binary_fraction_amount_is_refused_not_coerced():
    """Hard rule 2: money is Decimal — never a binary fraction, never cents.

    Coercing would hide an upstream defect behind arithmetic that mostly looks
    right; 0.1 + 0.2 is the classic way a cent goes missing from a ledger.
    """
    with pytest.raises(TypeError):
        services.allocate_payment(
            payment_amount=120.0, open_invoices=(bill("BL-A", "100"),), order="oldest_first"
        )

    with pytest.raises(TypeError):
        services.allocate_payment(
            payment_amount=Decimal("120"),
            open_invoices=(rating_seam.OpenInvoice(number="BL-A", balance=100.0),),
            order="oldest_first",
        )


def test_us_pay_006_nothing_here_rounds():
    """B4: round at finalization/display ONLY — and this is neither.

    A balance carrying its full NUMERIC(18,6) precision comes back with that
    precision intact. A function that quantized "to be safe" would silently
    finalize a figure a second time, which is exactly what BR-RAT-003 forbids.
    """
    outcome = allocate("50", (bill("BL-A", "20.123456"), bill("BL-B", "100")))

    assert outcome.applied_to("BL-A") == Decimal("20.123456")
    assert outcome.applied_to("BL-B") == Decimal("29.876544")
    assert outcome.remaining_balance == Decimal("70.123456")


# ── Invariants and refusals (TC-7) ─────────────────────────────────────────


def test_us_pay_006_tc7_sum_of_allocations_never_exceeds_the_payment():
    """TC-7 — the engine invariant, over every order and several shapes.

    Σ allocations ≤ payment, and Σ allocations + credit == payment exactly:
    money is neither invented nor lost. Asserted here across the matrix rather
    than trusted from the three worked cases above.
    """
    invoices = (bill("BL-A", "100"), bill("BL-B", "147.30"), bill("BL-C", "0.01"))

    for order in ("oldest_first", "newest_first", "carry_credit"):
        for payment in ("0", "0.01", "120", "247.30", "247.31", "1000"):
            amount = Decimal(payment)
            outcome = allocate(payment, invoices, order=order)
            applied = sum((a.applied for a in outcome.allocations), Decimal("0"))

            assert applied <= amount
            assert applied + outcome.credit_carried == amount
            assert outcome.remaining_balance == Decimal("247.31") - applied
            for one in outcome.allocations:
                assert one.applied > Decimal("0")  # a row means money moved


def test_us_pay_006_tc7_the_class_figures_conserve_across_every_order():
    """The same invariant one level down: nothing is invented INSIDE a bill either.

    Per allocation, Σ(by_class) == applied. Per account, Σ(remaining_by_class)
    == remaining_balance. Checked across the orders and several payment sizes,
    because a class walk that dropped a cent would still foot at invoice level.
    """
    invoices = (pe2_bill(), bill("BL-2606-018091", "142.30", usage_base="120.00", taxes="22.30"))
    total_open = Decimal("390.17")

    for order in ("oldest_first", "newest_first", "carry_credit"):
        for payment in ("0", "0.01", "200.00", "242.87", "390.17", "500.00"):
            outcome = allocate(payment, invoices, order=order)

            for row in outcome.allocations:
                assert sum(entry.applied for entry in row.by_class) == row.applied
            assert sum(entry.balance for entry in outcome.remaining_by_class) == (
                outcome.remaining_balance
            )
            assert outcome.remaining_balance == total_open - (
                Decimal(payment) - (outcome.credit_carried)
            )
            for entry in outcome.remaining_by_class:
                assert entry.balance >= Decimal("0")


def test_us_pay_006_a_negative_payment_is_refused_reversals_are_new_rows():
    """BR-PAY-002 / hard rule 4: a reversal is a new reversing row.

    A negative payment amount would be an attempt to un-allocate by arithmetic
    rather than by the audited US-PAY-008 reapply / EP-PAY-03 reversal path.
    """
    with pytest.raises(ValueError):
        allocate("-50", (bill("BL-A", "100"),))


def test_us_pay_006_a_negative_open_balance_is_not_an_allocation_target():
    """A credit position is an account credit row (US-PAY-007), not an open bill."""
    with pytest.raises(ValueError):
        allocate("50", (bill("BL-CREDIT", "-25"),))


def test_us_pay_006_the_same_bill_twice_is_refused_as_ambiguous():
    """`applied_to` could only report one of them, and the split would be a guess."""
    with pytest.raises(ValueError):
        allocate("120", (bill("BL-A", "100"), bill("BL-A", "147.30")))


# ── Purity (the property that makes GT-7 meaningful) ───────────────────────


def test_us_pay_006_allocation_is_pure_and_repeatable():
    """Identical inputs, identical output; the inputs come back unchanged.

    `allocate_payment` computes an allocation — it does not post one. Nothing is
    written, so running it twice is not a double posting and a preview is free.
    """
    invoices = (bill("BL-A", "100"), bill("BL-B", "147.30"))

    first = allocate("120", invoices)
    second = allocate("120", invoices)

    assert first == second  # frozen dataclasses compare by value
    assert invoices[0].balance == Decimal("100")  # the caller's bills are untouched
    assert invoices[1].balance == Decimal("147.30")


def test_us_pay_006_allocation_source_has_no_orm_no_clock_and_no_writes():
    """The static half: there is nothing here to be non-deterministic WITH.

    BR-PAY-021 makes the POSTING date the fact that matters for on-time-ness,
    and BR-TEN-043 makes event time an argument — so a wall clock in this path
    would be a defect even if it never changed a figure. The repeatability test
    above would not catch one that only affects a stored date.
    """
    import pathlib

    root = pathlib.Path(payments_allocation.__file__).resolve().parent

    def code_of(path):
        return "\n".join(
            line for line in path.read_text().splitlines() if not line.strip().startswith("#")
        )

    # `allocation.py` is the CALCULATION and is pure in every sense: no
    # queryset, no clock, no network. Handed the same inputs it returns the
    # same split, forever, which is what makes GT-7 reproducible.
    calculation = code_of(root / "allocation.py")
    for forbidden in (".objects.", "datetime.now()", "timezone.now()", "import requests"):
        assert forbidden not in calculation, f"allocation.py reaches for {forbidden} — this is pure"

    # `services.py` is the WRITE PATH and the two are NOT held to the same
    # rule. AMENDED 2026-08-11: this test asserted both files were free of
    # `.objects.`, which was true when written — services.py was 51 lines and
    # wrote nothing — and became false the moment the record-a-payment path
    # landed. B8's layering makes services.py "the ONLY write path", so a
    # queryset there is the design, not a defect, and a test forbidding it
    # would push the ORM somewhere worse.
    #
    # THE CLOCK HALF IS KEPT, AND IT IS THE HALF THAT MATTERS. BR-PAY-021 makes
    # the POSTING date decide whether a payment was on time, BR-TEN-043 makes
    # event time an argument, and the PO ruled it directly on 2026-08-11:
    # *"posting and actual dates can differ; ask actual date to user."* A
    # `timezone.now()` here would silently date money by the server's clock —
    # a defect that changes no figure in any test and quietly makes late
    # payments punctual for tenants west of the server.
    write_path = code_of(root / "services.py")
    for forbidden in ("datetime.now()", "timezone.now()", "import requests"):
        assert forbidden not in write_path, (
            f"services.py reaches for {forbidden} — a payment's dates are ARGUMENTS "
            "(BR-TEN-043, and the PO's 'ask actual date to user'), never the server's clock"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-006@ba9a795 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/08-payments/06-epics/EP-PAY-02-allocation.md ·
#         04-docs/05-modules/08-payments/02-business-rules.md)
# generated: 2026-08-11 by story-coder (payments allocation lane — GT-7)
# amended:   2026-08-11 by story-coder (allocation composition + staff targets lane) —
#            implementing PO rulings #5 and #6 of 2026-08-11
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_006_allocation.py → 45 passed✔ · pytest tests -m golden → 12 passed / 1 xfailed✔ (GT-7 unchanged) · run_gates 15 PASS/0 FAIL/1 SKIP✔
# exceptions: (1) US-PAY-006's TC-6 (posting vs clearing), TC-7's forged-row half and TC-8 (isolation) are NOT here — each needs the `allocations` write path, a session and RLS, none of which exist; the pure function is handed no dates and touches no queryset. (2) TC-1's composition and TC-5's class reorder ARE now asserted (PO ruling 2026-08-11 #5); TC-4's specific/split are asserted at the figures the PO was shown (#6). (2b) ADDED 2026-08-11 (four-class lane): the PO's OQ-109 figure is asserted directly — a $128.88 bill meets a $120.00 payment as usage+base 100.58 / tax 8.30 / tenant-defined 11.12, late fee LAST at 0.00 — proved RED by moving the class after fees (`assert Decimal('6.12') == Decimal('11.12')`, the late fee paid $5.00). The old OQ-109 refusal test was REWRITTEN rather than kept: OQ-109 is closed and a test asserting its ID in a refusal message would pin a stale stub. The tenant-defined class needs a ledger definition the repo does not publish, so `a_tenant_defined_class` stands one up with monkeypatch for the ORDER cases and a separate test asserts the unconfigured REFUSAL, which is the real state today. What remains unasserted is TC-4's "rest oldest" as a single call — a split states every amount and Σ = payment (TC-4's own invariant), and the caller composes the rest with a preview; see the decision log 2026-08-11. (3) `newest_first` is asserted against journey T7-13 step 4, NOT against a B5 figure — B5 freezes none for a non-default order. (4) The composition figures are EP-PAY-02 §7 / US-PAY-006 TC-1 and the PO's own 157.87 case; B5's composite fixtures GT-35..50 are NOT reproduced here and are not claimed. (5) Test names carry US-PAY-006's TC numbers for traceability; the Trace header deliberately does not cite the story, so this file claims coverage of the calculation and not of the story.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
