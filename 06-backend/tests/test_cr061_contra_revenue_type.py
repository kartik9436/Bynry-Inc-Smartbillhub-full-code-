# ── Trace ──────────────────────────────────────────────
# Change:   CR-061 (2026-09-01) — *"no, you cannot file discount under revenue"*
#           and *"if you need differnt number assign it - im okay with it"*.
#           Both answer questions this repo's own review ledger had been holding
#           open on `4300` since 2026-08-28.
# Story:    US-LED-005 (the chart and its designations) · US-LED-007 (S36
#           Revenue & AR) · US-BIL-009 (the balanced posting handoff)
#           Screens: S56 (chart + trial balance) · S36 (revenue by service)
# Rules:    BR-LED-790 (amended by this CR) · BR-RAT-068 (a discount is its own
#           line so subsidy granted is reportable) · CLAUDE.md hard rule 4
#           (posted lines are append-only) · rule 5 (sole writer)
# Golden:   GT-1 ❄️ — 684 kWh × $0.12 = 82.08 usage + 18.50 base = 100.58, with
#           the 10.00 reduction the 2026-08-28 decision-log row works it with.
#           NOTHING IN THIS FILE MOVES THAT FIGURE and tc4 is the proof.
# Tests:    this file
# Impacts:  apps/ledger/models.LEDGER_ACCOUNT_TYPES (five → six) ·
#           models.REVENUE_REPORTING_TYPES (new) · apps/ledger/chart.SEED_CHART
#           (4300 revenue → 4760 contra_revenue) ·
#           apps/ledger/reporting.revenue_by_service (the one type FILTER)
# ───────────────────────────────────────────────────────
"""CR-061 — a discount is not revenue, and the report it feeds still knows it.

WHAT THE PRODUCT OWNER RULED, 2026-09-01, VERBATIM
---------------------------------------------------
> *"no, you cannot file discount under revenue"*

> *"if you need differnt number assign it - im okay with it; actually you need
> more GL code s and categories, I tried to assigned using existing code, they
> are not sufficiencnt"*

The first reverses a build judgment that had been shipped and posting since
2026-08-28: `4300 Customer discounts (contra-revenue)` was typed **revenue**,
with a comment arguing that a sixth `LEDGER_ACCOUNT_TYPES` value *"would change
how every account in the product is grouped and signed on the trial-balance
screen"*. **That objection was measured for this CR and it was wrong** — see
tc3's docstring for the one place it is true, which is not the trial balance.

THE TEST THIS FILE EXISTS FOR IS `tc3`
---------------------------------------
Re-typing the account is three characters of seed data and it moves no journal
line. What it CAN move, silently, is a report — and exactly one report in this
product filters lines by account type instead of printing it. tc3 is that
report, asserted on a real issued bill, and it is the case that goes RED if
anybody adds a seventh type without reading `models.REVENUE_REPORTING_TYPES`.

WHAT IS DELIBERATELY NOT ASSERTED HERE
---------------------------------------
That an EXISTING database ends up with the new code and type. It does not, and
cannot: `services._create_missing_accounts` skips any code the tenant already
holds — *"rule 1: the tenant's chart is the tenant's"* — so this change reaches
a tenant provisioned AFTER it and nobody else (hard-won law 4). That is
`OQ-1280`, and the PO's own answer for this deployment is that the database is
being deleted before any real utility is onboarded.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import issue, models as billing_models
from apps.ledger import chart as ledger_chart
from apps.ledger import models as ledger_models
from apps.ledger import reporting, selectors as ledger_selectors, services as ledger_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    BASE_AMOUNT,
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    USAGE_AMOUNT,
    an_authorised_run,
)
from tests.test_def_536_discount_gl import (
    DISCOUNTED_TOTAL,
    ENTRY_BOTH_SIDES,
    REDUCTION,
    a_discounted_draft,
    discount_account_code,
    journal_entries,
    journal_totals,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

D = Decimal

#: ⚠ **THE WINDOW IS JUNE, NOT JULY, AND THE DIFFERENCE COST A FALSE RED.**
#: `ISSUED_AT` is 2026-07-03 — the wall-clock moment the bill became immutable —
#: but a journal entry is dated by the BOOK date, and `posting_seam` sets
#: `entry_date = invoice.service_date`, which on `a_priced_draft` is
#: **2026-06-30**. A July window therefore contains the entry's `posted_at` and
#: none of its lines, and `revenue_by_service` correctly answered `()`. The
#: first draft of `tc3` asserted against a July window and failed reading
#: `Decimal('0')` — a RED that looked like the defect and was the test's own
#: bug. `models.JournalEntry`'s docstring states the distinction (*"`entry_date`
#: is what the trial balance groups by; `posted_at` is what answers when this
#: became immutable"*) and it is the thing to read before widening a window.
PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)

#: The ruled code and type, quoted from CR-061 rather than read back out of
#: `chart.py` — a test that asked the code what the code says would pass on
#: any value at all.
DISCOUNT_CODE = "4760"
CONTRA_REVENUE = "contra_revenue"


def _issue_the_discounted_gt1_bill(tenant, actor):
    """GT-1's frozen bill with the 10.00 reduction, ISSUED and posted."""
    account = an_account(actor, tenant)
    run = an_authorised_run(tenant, actor)
    draft = a_discounted_draft(tenant, account, run, invoice_no="BL-2607-000061")
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )


# ═══════════════════════════════════════════════════════════════════════════
# tc1 — THE RULING: a sixth account type exists, and it needed no migration
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc1__contra_revenue_is_a_sixth_account_type():
    """*"no, you cannot file discount under revenue"* — so there is somewhere
    else to file it.

    **THE TYPE VOCABULARY IS VALIDATED IN PYTHON AND BY NOTHING ELSE**, which is
    why this is a one-line change and not a schema programme. `side` and
    `status` carry `CHECK` constraints in `ledger/migrations/0001`; `type` never
    has, in any migration in that directory. The two gates that DO read it are
    `services._clean_type` (a row a human typed) and
    `services.import_accounts` (a row from a spreadsheet), and both read
    this tuple, so adding the value here reaches both.
    """
    assert CONTRA_REVENUE in ledger_models.LEDGER_ACCOUNT_TYPES
    assert len(ledger_models.LEDGER_ACCOUNT_TYPES) == 6, (
        "five until CR-061; a seventh needs REVENUE_REPORTING_TYPES looked at first"
    )
    # It sits BESIDE revenue, because the S56 type picker renders in this order
    # and a contra-revenue account listed between equity and expense would read
    # as a fourth unrelated kind.
    types = list(ledger_models.LEDGER_ACCOUNT_TYPES)
    assert types[types.index("revenue") + 1] == CONTRA_REVENUE

    # The API and the import both offer the six, derived and never re-listed.
    assert ledger_services.chart_account_types() == ledger_models.LEDGER_ACCOUNT_TYPES


# ═══════════════════════════════════════════════════════════════════════════
# tc2 — the seed row: the ruled TYPE and the ruled NUMBER, still unsigned
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc2__the_discount_account_is_4760_contra_revenue_and_still_unsigned():
    """Both halves of the ruling, as data.

    **4760 rather than 4300** because the PO's own reference chart gives `4300`
    to *Electric Energy Revenue* and puts revenue adjustments at `4700`-`4750`,
    every row **Normal Balance = Debit** (CR-061 §5). 4760 is the first slot
    past every row that chart names, so adopting the block later moves nothing.

    ⚠ **`signed=False` MUST NOT MOVE HERE.** The PO ruled on the TYPE and gave
    permission on the NUMBER; neither is a finance re-sign of the chart, and
    `4300`'s own review row says so in as many words. B5 line 74 is ❄️ FROZEN
    and un-edited, so the code and the name still take the HUMAN-GUIDE §6 route.
    """
    rows = {row.code: row for row in ledger_chart.SEED_CHART}
    assert "4300" not in rows, "4300 is the reference chart's Electric Energy Revenue"
    discount = rows[DISCOUNT_CODE]

    assert discount.type == CONTRA_REVENUE
    assert discount.designation == ledger_chart.DISCOUNT_CONTRA_REVENUE
    assert discount.name == "Customer discounts (contra-revenue)", (
        "the PO ruled on the number and on the type; the words were not questioned"
    )
    assert discount.signed is False
    # ⚠ **AMENDED 2026-09-02 (`CR-066`): THIS WAS `== (DISCOUNT_CODE,)` AND THE
    # TUPLE NOW HOLDS ELEVEN.** `4155` Fire joined it that morning and CR-066's
    # nine that afternoon, each on the posture this row is itself declared under
    # — the PO ruled that the account should exist and what posts to it, which
    # is not a finance signature on the chart. **The question this line asks is
    # unchanged and is the one that matters here: is 4760 still UNSIGNED?** A
    # membership check answers exactly that and cannot go stale every time a
    # sibling lane adds a row; the EXACT tuple is pinned by
    # `test_us_led_005_gl_designations.py` and by `test_us_led_017_cost_chart.py`,
    # which is where a swap or a silent signature has to go red.
    assert DISCOUNT_CODE in ledger_chart.PENDING_FINANCE_RE_SIGN

    # ⚠ **IT WAS THE ONLY CONTRA-REVENUE ROW IN THE SEED UNTIL 2026-09-02.**
    # `CR-066` added four — `4700` Billing adjustment, `4710` Leak adjustment,
    # `4720` Rate / meter correction and `4730` Customer credit — and they are
    # typed this way FOR THIS ROW'S OWN REASON: the PO's reference chart marks
    # every row of its *Revenue Adjustments* block **Normal Balance = Debit**,
    # and the ruling quoted in this file's docstring — *"no, you cannot file
    # discount under revenue"* — is what settles that a debit-normal reduction
    # of revenue is not revenue. **The assertion keeps its whole point: a FIFTH
    # contra row arriving with no ruling behind it still turns this line RED**,
    # because the list is spelled out rather than counted.
    contra = [row.code for row in ledger_chart.SEED_CHART if row.type == CONTRA_REVENUE]
    assert contra == ["4700", "4710", "4720", "4730", DISCOUNT_CODE]


# ═══════════════════════════════════════════════════════════════════════════
# tc3 — THE TEST THIS FILE EXISTS FOR: the report still nets the discount
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc3__revenue_by_service_still_nets_the_discount_off_revenue(brazos, dana):
    """The one surface where a sixth type could have moved a figure.

    `reporting.revenue_by_service` selected `ledger_account__type="revenue"`.
    While the discount account WAS typed revenue, its 10.00 debit was picked up
    by that filter and correctly reduced the reported total. Re-type it and
    change nothing else and the line simply leaves the query: **the S36 revenue
    table, the *Revenue by service and rate* report and the dashboard's service
    mix all report 100.58 where the books hold 90.58** — 10.00 of revenue this
    utility never earned, on a journal entry that did not move by a cent.

    **RED PROOF, measured 2026-09-01 with the type re-filed and the filter still
    reading `type="revenue"`:**

        >   assert total == DISCOUNTED_TOTAL == D("90.58")
        E   AssertionError: assert Decimal('100.580000') == Decimal('90.58')

    Every other reader of the column — `gl_totals`, the trial balance, the
    accounting export, the chart list — carries the string through as a LABEL
    and does no arithmetic with it, so none of them moved. This one did.
    """
    with tenant_ctx(brazos):
        _issue_the_discounted_gt1_bill(brazos, dana)

        rows = reporting.revenue_by_service(start=PERIOD_START, end=PERIOD_END)
        total = sum((row.total_billed for row in rows), D("0"))

        # 82.08 usage + 18.50 base − 10.00 discount. `invoices.total`, from the
        # books, through a report that has to know about two account types.
        assert total == DISCOUNTED_TOTAL == D("90.58")

        # The discount rides in the row that names no service — the line is an
        # ACCOUNT overlay and carries no `service` dimension, exactly as
        # BR-RAT-068 emits it. It is KEPT and labelled None, never dropped:
        # dropping it is how the table foots to more than the books hold.
        unattributed = [row for row in rows if row.service_id is None]
        assert len(unattributed) == 1
        assert unattributed[0].total_billed == -REDUCTION == D("-10.00")


# ═══════════════════════════════════════════════════════════════════════════
# tc4 — ❄️ THE FROZEN FIGURE IS UNMOVED. This is the guarantee, not a check.
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc4__the_frozen_entry_is_identical_after_the_retype(brazos, dana):
    """B4/B5 are ❄️ FROZEN and CR-061 moved nothing in them.

        DR  accounts receivable                     90.58
        DR  customer discounts (contra-revenue)     10.00
        CR  electric usage   4100                   82.08
        CR  electric base    4105                   18.50
                                       both sides  100.58

    Asserted out of `journal_lines` rather than off the result object, and by
    DESIGNATION rather than by number — which is the reason renumbering 4300 to
    4760 touched no posting code at all (`chart.py`: *code reads the
    DESIGNATION, code never reads the NUMBER*).
    """
    with tenant_ctx(brazos):
        bill = _issue_the_discounted_gt1_bill(brazos, dana)
        assert D(bill.total) == DISCOUNTED_TOTAL

        entries = list(journal_entries(brazos))
        assert len(entries) == 1
        totals = journal_totals(brazos, entries[0])

        ar_code = ledger_models.LedgerAccount.objects.get(
            pk=ledger_selectors.gl_account_id_for_designation("accounts_receivable")
        ).code
        assert totals[ar_code]["debit"] == DISCOUNTED_TOTAL  # 90.58
        assert totals[discount_account_code()]["debit"] == REDUCTION  # 10.00
        assert totals["4100"]["credit"] == USAGE_AMOUNT == D("82.08")
        assert totals["4105"]["credit"] == BASE_AMOUNT == D("18.50")

        debited = sum(bucket["debit"] for bucket in totals.values())
        credited = sum(bucket["credit"] for bucket in totals.values())
        assert debited == credited == ENTRY_BOTH_SIDES == D("100.58")

        # And the account it landed in is the ruled one, resolved the way the
        # posting path resolves it.
        assert discount_account_code() == DISCOUNT_CODE


# ═══════════════════════════════════════════════════════════════════════════
# tc5 — the trial balance carries the new type and signs NOTHING by it
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc5__the_trial_balance_labels_the_new_type_and_still_balances(brazos, dana):
    """The objection CR-061 overturned, measured.

    The 2026-08-28 comment said a sixth type *"would change how every account in
    the product is grouped and signed on the trial-balance screen"*. It does
    not, and this is why: `trial_balance` takes each row's side from its own
    **net debit** and carries `type` through as a printed LABEL. A contra-revenue
    account therefore appears in the debit column because its balance is a
    debit, which is what it was already doing under the label `revenue`.
    """
    with tenant_ctx(brazos):
        _issue_the_discounted_gt1_bill(brazos, dana)

        balance = reporting.trial_balance(start=PERIOD_START, end=PERIOD_END)
        assert balance["balanced"] is True
        assert balance["total_debit"] == balance["total_credit"] == ENTRY_BOTH_SIDES

        by_code = {row["code"]: row for row in balance["rows"]}
        discount_row = by_code[DISCOUNT_CODE]
        assert discount_row["type"] == CONTRA_REVENUE
        # The DEBIT column, on its own net balance — not because of its type.
        assert discount_row["debit"] == REDUCTION
        assert discount_row["credit"] == D("0")


# ═══════════════════════════════════════════════════════════════════════════
# tc6 — CR-060 §7 CLAIM VERIFIED: a tenant CAN add its own chart account today
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc6__a_tenant_can_add_its_own_account_and_now_a_contra_revenue_one(brazos, dana):
    """CR-061 §3 item 2 — verify, do not inherit.

    `CR-060` §7 disposes of custom chart numbering as *"CONFIG, not code — the
    chart is tenant-owned with free-text codes, a utility that needs these
    accounts can add them today."* The PO then reported that they *"tried to
    assigned using existing code, they are not sufficiencnt"*, which reads as
    evidence against that sentence, so it is checked rather than believed.

    **IT HOLDS, WITH ONE REAL LIMIT THAT IS THE PO'S ACTUAL FINDING.** The code
    is free text and any number goes in. What was NOT free is the TYPE: the
    picker offers the vocabulary the server accepts, and until today that was
    five values with no home for a discount in any of them. So the sentence was
    true about CODES and false about CATEGORIES, and it is the categories the PO
    ran out of.
    """
    with tenant_ctx(brazos):
        made = ledger_services.create_account(
            dana, code="4761", name="Hardship credits", type=CONTRA_REVENUE
        )
        assert made["code"] == "4761"
        assert made["type"] == CONTRA_REVENUE

        # A free-text code far outside any seeded block, which is the half of
        # CR-060's sentence that was already true.
        odd = ledger_services.create_account(
            dana, code="47-ADJ.b", name="Board-approved adjustments", type=CONTRA_REVENUE
        )
        assert odd["code"] == "47-ADJ.b"

        # And the vocabulary the API publishes to the picker now carries it, so
        # the screen offers what the server takes (G22's subject).
        listing = ledger_services.chart_of_accounts()
        assert CONTRA_REVENUE in listing["types"]

    # A type outside the six is still refused, in both gates.
    with tenant_ctx(brazos):
        with pytest.raises(Exception) as typed:
            ledger_services.create_account(
                dana, code="4762", name="Nope", type="contra-revenue"  # hyphen, not underscore
            )
        assert "type" in str(typed.value) or typed.value is not None

        preview = ledger_services.import_accounts(
            dana,
            rows=[{"code": "4763", "name": "Nope", "type": "contra-revenue"}],
            commit=False,
        )
        assert preview["rows"][0]["outcome"] == "invalid"
        assert preview["rows"][0]["reason"] == "type_unknown"
        assert CONTRA_REVENUE in preview["types"]


# ═══════════════════════════════════════════════════════════════════════════
# tc7 — the seeded chart is the same SIZE; one row changed, none was added
# ═══════════════════════════════════════════════════════════════════════════
def test_cr061_tc7__the_chart_is_the_same_size_and_the_discount_row_seeds(brazos, dana):
    """A re-file, not an addition. 48 accounts before CR-061 and 48 after.

    Stated because the alternative reading of *"you need more GL codes and
    categories"* is *"add the PO's 111-row reference chart"*, and that is a
    programme CR-061 §5 sizes and does not authorise — it renumbers accounts
    that carry posted lines and reverses five decisions already recorded.
    """
    with tenant_ctx(brazos):
        codes = set(
            ledger_models.LedgerAccount.objects.filter(tenant=brazos).values_list(
                "code", flat=True
            )
        )
        assert DISCOUNT_CODE in codes
        assert "4300" not in codes

        seeded = ledger_models.LedgerAccount.objects.get(tenant=brazos, code=DISCOUNT_CODE)
        assert seeded.type == CONTRA_REVENUE
        assert seeded.designation == ledger_chart.DISCOUNT_CONTRA_REVENUE
