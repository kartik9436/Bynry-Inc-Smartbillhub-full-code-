# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-035 (EP-CWP-07) — why this bill is different, and the lines
#           must sum to the difference. Screen: CWP-030
# Rules:    BR-CWP-046 (the component lines sum EXACTLY to the stated
#           difference — CONFIRMED, `CP-24`) · BR-CWP-010 · B4 (round only at
#           display) · CLAUDE.md hard rule 2 · hard rule 3
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `bill_comparison_for` /
#           `components_tie_out` · apps/portal/api.py `bill_comparison`
# ───────────────────────────────────────────────────────
"""`US-CWP-035`'s cases, and the boundary this story could not cross.

⚠ **THE DECOMPOSITION RULE IS PROPOSED, NOT SIGNED — `OQ-CWP-1563`.** The
story's own §7 says it: *"This is new arithmetic on a money path and B4/B5 are
frozen … A lane must not ratify its own formula."* §8 names the hard part —
*"which components exist, and in what order they are attributed when two move
at once"* — and `J38`'s header says the same thing a third time. So the four
lines are NOT built, `_components_for` raises on that id, and everything else
in the story IS built.

⚠ **WHAT IS BUILT IS NOT A CONSOLATION PRIZE.** `BR-CWP-046` is CONFIRMED and
its invariant holds under ANY decomposition finance signs, so it is coded and
tested NOW, on the story's own worked figures:

    142.18 − 138.44                          = +3.74
    +8.83  +  0.00  +  4.29  +  (−9.38)      = +3.74   ✓ exactly

and TC-3's negative — perturb any component by one cent and it must FAIL —
is asserted rather than described, because *"a tolerance here would defeat the
whole story"*.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account, switch_on

JULY = date(2026, 7, 31)
AUGUST = date(2026, 8, 30)
JULY_NUMBER = "BL-2607-0139"
AUGUST_NUMBER = "BL-2608-0141"
JULY_TOTAL = "138.4400"
AUGUST_TOTAL = "142.1800"

#: `US-CWP-035` §4 — the four components put to finance on `OQ-CWP-1563`.
#: They are the FIXTURE, not the product: nothing computes them yet.
PROPOSED_COMPONENTS = (
    {"code": "used_more_water", "amount": "8.8300"},
    {"code": "trash_cart_unchanged", "amount": "0.0000"},
    {"code": "summer_discount_ended", "amount": "4.2900"},
    {"code": "lower_tax_smaller_sewer_share", "amount": "-9.3800"},
)
DIFFERENCE = "3.7400"


def two_months(tenant, account):
    """July at `$138.44` and August at `$142.18` — the story's own two bills."""
    july = an_issued_bill(
        tenant, account, number=JULY_NUMBER, total=JULY_TOTAL, issued_on=JULY,
        due_on=date(2026, 8, 14),
    )
    august = an_issued_bill(
        tenant, account, number=AUGUST_NUMBER, total=AUGUST_TOTAL, issued_on=AUGUST,
        due_on=date(2026, 9, 14),
    )
    return july, august


def _lines(tenant, account, invoice, rows):
    """Charge lines on a bill, as stage 6 writes them.

    ⚠ **THE FIXTURE ABOVE DELIBERATELY WRITES NONE**, which is what makes
    `test_us_cwp_035_the_breakdown_is_ABSENT_BY_NAME…` a real case: a bill
    whose stored total does not equal its own lines gets no breakdown at all.
    """
    from apps.billing import models as billing_models
    from apps.tenancy import models as tenancy_models

    for kind, service_code, amount in rows:
        # The PLATFORM catalogue's service, which is where `services` lives —
        # the same lookup `test_us_cwp_033_bill_detail._service` makes.
        service = (
            tenancy_models.Service.objects.filter(code=service_code).first()
            if service_code
            else None
        )
        billing_models.InvoiceLine.objects.create(
            tenant=tenant,
            account=account,
            invoice=invoice,
            service=service,
            kind=kind,
            description=f"{service_code or 'bill'} {kind}",
            amount=Decimal(amount),
        )


def read(tenant, account, number=AUGUST_NUMBER):
    with tenant_context(tenant.id):
        return billing_seam.bill_comparison_for([account.pk], number=number)


# ═══════════════════════════════════════════════════════════════════════════
# BR-CWP-046 — THE ARITHMETIC, WHICH IS THE POINT OF THE STORY
# ═══════════════════════════════════════════════════════════════════════════


def test_us_cwp_035_tc2_THE_FOUR_LINES_SUM_TO_THE_DIFFERENCE_EXACTLY():
    """⚠ **`+8.83 + 0.00 + 4.29 − 9.38 = +3.74`, and no tolerance anywhere.**

    ⚠ **THE SIGNS ARE THE SERVER'S AND NOTHING TAKES AN ABSOLUTE VALUE.**
    `−9.38` is a real reduction; read as `+9.38` the four lines would add to
    `+22.50` and the invariant would be lost while every number on the page
    still looked plausible. `accountDetailTabs.tsx` records what the other
    reading cost once — a panel reading `272.30` where the customer owed
    `222.30`.

    Needs no database: the invariant is arithmetic over figures, which is why
    it can be proved before the rule that produces them is signed.
    """
    assert billing_seam.components_tie_out(list(PROPOSED_COMPONENTS), difference=DIFFERENCE)
    # …and the difference is the two bills' own totals, not a third figure.
    assert Decimal(AUGUST_TOTAL) - Decimal(JULY_TOTAL) == Decimal(DIFFERENCE)


def test_us_cwp_035_tc3_NEGATIVE_one_cent_anywhere_and_the_tie_out_FAILS():
    """⚠ **PROVED RED, COMPONENT BY COMPONENT** (hard-won law 7).

    Every one of the four is perturbed by a single cent, in both directions,
    and the check must refuse all eight. A tie-out that could not fail is worse
    than none, because it is trusted — and a tolerance here would defeat the
    whole story (`J38` step 3).
    """
    for index in range(len(PROPOSED_COMPONENTS)):
        for delta in ("0.01", "-0.01"):
            perturbed = [dict(row) for row in PROPOSED_COMPONENTS]
            perturbed[index]["amount"] = str(
                Decimal(perturbed[index]["amount"]) + Decimal(delta)
            )
            assert not billing_seam.components_tie_out(perturbed, difference=DIFFERENCE), (
                f"a one-cent error on component {index} ({delta}) was accepted"
            )


def test_us_cwp_035_the_tie_out_is_on_the_DISPLAYED_figures_not_the_stored_ones():
    """⚠ **FOUR STORED COMPONENTS CAN SUM AND STILL PRINT A COLUMN THAT IS OUT.**

    `1.2350 + 1.2350 = 2.4700` stored, and `1.24 + 1.24 = 2.48` printed. B4's
    2026-08-11 ruling chose the ROUNDED addends *for reproducibility*, and this
    check applies that reading — so a customer adding the printed column gets
    the printed headline. A tie-out on the stored figures would pass this pair
    and the page would be a cent out.
    """
    halves = [{"code": "a", "amount": "1.2350"}, {"code": "b", "amount": "1.2350"}]
    assert billing_seam.components_tie_out(halves, difference="2.4800")
    assert not billing_seam.components_tie_out(halves, difference="2.4700")


# ═══════════════════════════════════════════════════════════════════════════
# The read: what ships, and what is stated as absent
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_035_tc1_the_difference_and_its_direction_are_served(pine_hill, sarah):
    """*"Why August cost `$3.74` more"* — plain subtraction of two stored totals.

    That subtraction is NOT the proposed decomposition and is not blocked by it:
    `142.18 − 138.44` needs no finance ruling, and the screen's headline is the
    half of the story that deflects the telephone call.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        two_months(pine_hill, account)
    view = read(pine_hill, account)

    assert view["compared"] is True
    assert view["prior_number"] == JULY_NUMBER
    assert view["prior_total_display"] == "138.44"
    assert view["total_display"] == "142.18"
    assert view["difference_display"] == "3.74"
    assert view["direction"] == billing_seam.MOVED_UP


@pytest.mark.django_db
def test_us_cwp_035_tc4_NEGATIVE_a_bill_that_went_DOWN_reads_cost_less(pine_hill, sarah):
    """⚠ **THE SIGN IS REVERSED, NOT REMOVED.** `138.44 − 142.18 = −3.74`.

    An absolute value here would tell a customer whose bill FELL that it rose,
    with a correct-looking figure. The direction and the signed figure travel
    together and the screen renders what it is given.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        two_months(pine_hill, account)
    view = read(pine_hill, account, number=JULY_NUMBER)
    # July is now the LATER of the pair being explained? No — July has no prior,
    # so the down-case needs its own pair.
    assert view["compared"] is False

    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2609-0150", total="138.4400",
            issued_on=date(2026, 9, 30), due_on=date(2026, 10, 14),
        )
    fell = read(pine_hill, account, number="BL-2609-0150")
    assert fell["direction"] == billing_seam.MOVED_DOWN
    assert fell["difference_display"] == "-3.74", "the sign is the answer"
    assert fell["difference_display"].startswith("-")


@pytest.mark.django_db
def test_us_cwp_035_tc5_NEGATIVE_a_FIRST_bill_offers_no_comparison_at_all(pine_hill, sarah):
    """⚠ **NOT A COMPARISON AGAINST ZERO** — the story says so in as many words.

    *"$142.18 more than last month"* is arithmetically true and, to somebody who
    has just moved in, a lie. `compared: false` is what the screen branches on
    and there is no difference figure at all.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number=AUGUST_NUMBER, total=AUGUST_TOTAL,
            issued_on=AUGUST, due_on=date(2026, 9, 14),
        )
    view = read(pine_hill, account)
    assert view["compared"] is False
    assert "difference_display" not in view, "no figure at all, not a zero"
    assert view["against_last_year"] == []


@pytest.mark.django_db
def test_us_cwp_035_the_breakdown_is_ABSENT_BY_NAME_and_not_silently_empty(
    pine_hill, sarah
):
    """⚠ **`components: []` WITH ITS REASON — the prime directive's boundary.**

    An empty list on its own would read as *"nothing moved"*, which is a
    different and false statement. The body names the question it is waiting on,
    so the screen states the absence in words (B14 rule 32) instead of drawing
    a blank panel.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        two_months(pine_hill, account)
    view = read(pine_hill, account)

    # ⚠ **THIS CASE SURVIVES THE RULING WITH A DIFFERENT REASON, AND THAT IS
    # WHY IT IS NOT DELETED** (`DEF-CWP-3968`). It used to prove the breakdown
    # was absent because nobody had signed it (`OQ-CWP-1563`). The PO signed it
    # on 2026-09-05 — *"(a) list every reason with its share"* — so what is
    # asserted now is `BR-CWP-046`: `two_months` writes two bills with TOTALS
    # AND NO LINES, the buckets are therefore empty, and shares that sum to
    # `0.00` against a headline of `+3.74` are NOT SERVED. Four numbers that do
    # not add up to the figure a customer is reading explain nothing, and
    # `US-CWP-035` TC-3 allows no tolerance to paper over the gap.
    assert view["components"] == []
    assert view["components_available"] is False
    assert view["components_blocked_by"] == "BR-CWP-046"


@pytest.mark.django_db
def test_def_cwp_3968_EVERY_REASON_WITH_ITS_SHARE_and_they_sum_exactly(pine_hill, sarah):
    """**THE RULED BEHAVIOUR, ON BILLS THAT HAVE LINES.**

    PO, 2026-09-05, verbatim: *"(a) list every reason with its share"*, chosen
    from three options — the alternative being to pick the larger mover and
    call it the cause. The decision log records why: *"It is more arithmetic
    than naming one, and it is the only version that survives a customer
    checking it."*

    ⚠ **THE GRANULARITY IS THE RULING'S OWN WORKED EXAMPLE.** Its four lines
    were a usage bucket, a base bucket, a discount bucket and a tax bucket —
    nothing in it splits one service's usage into a VOLUME part and a PRICE
    part, and nothing here does either. That cross-term attribution is a second
    finance judgment that was never put.

    July charges `$100.00` of water usage, `$20.00` of water standing charge
    and `$18.44` of tax. August charges `$110.00`, `$20.00` and `$12.18`. The
    shares are `+$10.00`, `$0.00` and `−$6.26`, which sum to `+$3.74` — the
    difference between `$138.44` and `$142.18`, exactly.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        july, august = two_months(pine_hill, account)
        _lines(pine_hill, account, july, (
            ("usage", "water", "100.0000"),
            ("base", "water", "20.0000"),
            ("tax", None, "18.4400"),
        ))
        _lines(pine_hill, account, august, (
            ("usage", "water", "110.0000"),
            ("base", "water", "20.0000"),
            ("tax", None, "12.1800"),
        ))
    view = read(pine_hill, account)

    assert view["components_available"] is True
    assert view["components_blocked_by"] is None
    shares = {row["code"]: row["amount_display"] for row in view["components"]}
    assert shares == {"water_usage": "10.00", "water_base": "0.00", "bill_tax": "-6.26"}
    # ⚠ **THE INVARIANT THE PO STATED IN THEIR OWN TERMS** — *"no residue
    # hidden in a rounding"*. Read back off the served figures, not asserted
    # about them.
    total = sum(Decimal(row["amount_display"]) for row in view["components"])
    assert total == Decimal(view["difference_display"]) == Decimal("3.74")
    assert billing_seam.components_tie_out(view["components"], difference=view["difference"])


@pytest.mark.django_db
def test_def_cwp_3968_a_charge_that_ENDED_is_a_reason_and_not_an_omission(
    pine_hill, sarah
):
    """A summer discount on July's bill and not on August's is the whole of
    why August costs more. Dropping the bucket because this bill has no such
    line would leave the column short by exactly the amount the customer is
    asking about."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        july, august = two_months(pine_hill, account)
        _lines(pine_hill, account, july, (
            ("usage", "water", "142.1800"),
            ("discount", None, "-3.7400"),
        ))
        _lines(pine_hill, account, august, (("usage", "water", "142.1800"),))
    view = read(pine_hill, account)

    shares = {row["code"]: row["amount_display"] for row in view["components"]}
    assert shares["bill_discount"] == "3.74", "the discount that ENDED is the reason"
    assert shares["water_usage"] == "0.00", "and the water did not move — still listed"
    assert view["components_available"] is True


@pytest.mark.django_db
def test_def_cwp_3968_a_bucket_that_did_not_move_is_still_listed(pine_hill, sarah):
    """*Trash cart charge unchanged `$0.00`* is one of the PO's four lines.

    A customer looking for what changed is also asking what did NOT, and a
    service silently absent from the list reads as a service that stopped being
    charged."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        july, august = two_months(pine_hill, account)
        _lines(pine_hill, account, july, (
            ("usage", "water", "118.4400"),
            ("base", "trash", "20.0000"),
        ))
        _lines(pine_hill, account, august, (
            ("usage", "water", "122.1800"),
            ("base", "trash", "20.0000"),
        ))
    view = read(pine_hill, account)
    codes = [row["code"] for row in view["components"]]
    assert "trash_base" in codes
    shares = {row["code"]: row["amount_display"] for row in view["components"]}
    assert shares["trash_base"] == "0.00"


@pytest.mark.django_db
def test_def_cwp_3968_no_component_carries_a_database_id_or_a_sentence(
    pine_hill, sarah
):
    """B14 rule 31 and rule 32. The row travels as a SERVICE CODE and a KIND;
    the words are the catalogue's, in the reader's own language (rule 35), and
    the `code` is a handle for a test and a log that no screen prints."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        july, august = two_months(pine_hill, account)
        _lines(pine_hill, account, july, (("usage", "water", "138.4400"),))
        _lines(pine_hill, account, august, (("usage", "water", "142.1800"),))
    view = read(pine_hill, account)
    for row in view["components"]:
        assert set(row) == {"code", "service", "kind", "amount", "amount_display"}, row
        assert str(account.pk) not in repr(row)
        assert str(august.pk) not in repr(row)


@pytest.mark.django_db
def test_us_cwp_035_tc9_the_prior_bill_is_by_PERIOD_and_never_by_issue_date(
    pine_hill, sarah
):
    """⚠ **A BACKBILL ISSUED TODAY FOR MARCH IS NOT LAST MONTH'S BILL.**

    Ordering by `issued_at` would make it one, and August would be explained
    against a figure the customer never experienced as *last month*. The read
    orders on `period_end`, which is the month a person means.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        two_months(pine_hill, account)
        # Issued LAST, covering MARCH — a catch-up bill.
        an_issued_bill(
            pine_hill, account, number="BL-2603-0088", total="61.0000",
            issued_on=date(2026, 3, 31), due_on=date(2026, 4, 14),
        )
    view = read(pine_hill, account)
    assert view["prior_number"] == JULY_NUMBER, "August is explained against JULY"


@pytest.mark.django_db
def test_us_cwp_035_tc7_TENANT_ISOLATION_a_bill_outside_the_account_set_is_absent(
    pine_hill, sarah
):
    """`BR-CWP-010` — both halves in `bill_in_set`'s own filter."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        two_months(pine_hill, account)
        assert billing_seam.bill_comparison_for([], number=AUGUST_NUMBER) is None
        assert billing_seam.bill_comparison_for([account.pk], number="BL-9999-0000") is None
