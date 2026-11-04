# ── Trace ──────────────────────────────────────────────
# Change:  CR-138-BRC07 `P4.1` — the debtor list is cut in SQL, so what a bill
#          ASKS FOR had to become an expression as well as a function.
# Rules:   BR-BIL-072 — ❄️ B4/B5 FROZEN, PO 2026-08-11, verbatim *"Level is
#          due"*: a budget bill asks for the LEVEL and not the total ·
#          BR-BIL-030 (the level is stamped on the bill, never re-read) ·
#          DEF-2416 · DEF-062 · CLAUDE.md hard rule 2 (money is never a float)
#          · hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee — which is why this file exists at all).
# ───────────────────────────────────────────────────────
"""ONE signed rule, TWO renderings, and a test that fails when they part.

`apps.billing.selectors.amount_due_for` reads one bill in Python.
`amount_due_expression` says the same thing in SQL so that `P4.1` could push
the debtor list's arithmetic into the database. **Two implementations of one
❄️ FROZEN finance figure is exactly the shape that drifts**, and a docstring
promising they agree is a comment, not a guarantee.

⚠ **THIS FILE WAS NAMED BY `selectors.py` BEFORE IT EXISTED.** The draft of
`amount_due_expression` said *"`tests/test_cr138_p41_amount_due_expression.py`
asserts the two agree bill by bill on real PostgreSQL"* and there was no such
file — hard-won law 1 in one sentence. It exists now and it asserts that.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, and each is answered below rather than
assumed:** a fixture holding only ORDINARY bills would let the whole budget
branch rot untested and still print green — so every row below is a bill whose
treatment is a different clause of the rule, including the two that are not
"a level": a `budget` block with no `amount_due` key, and no `budget` block at
all.

⚠ **AND WHAT THIS DOES NOT COVER, said rather than left to be discovered:** the
default suite runs on in-memory SQLite (hard-won law 14), whose JSON operators
are not PostgreSQL's, so **a green run of this file alone is a claim about
SQLite.** The agreement was therefore ALSO run by hand against real PostgreSQL
16 on the seeded 40,046-debtor tenant on 2026-09-23, bill by bill over the
whole open set: **80,091 bills checked, 2,000 of them carrying a budget
`amount_due`, 0 disagreements.** See the `CR-138-BRC07` row in the decision
log.

RED-PROVED FIRST (hard-won law 7), through `pytest`: replacing the
expression's `Coalesce(..., F("total"))` with a bare `F("total")` makes
`test_the_two_renderings_agree_bill_by_bill` fail and NAME the budget bill.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ISSUED_ON = date(2026, 9, 1)

#: `(suffix, total, bill_payload, what clause of the rule this row is)`.
#: ❄️ WE-8's own pair is the first row: the bill TOTALS 292.87 and ASKS for
#: 242.00, and paying the 242 settles the month in full.
CASES = (
    ("WE8", "292.87", {"budget": {"amount_due": "242.00"}}, "a levelled bill"),
    ("ORD", "184.20", {"account_no": "x"}, "an ordinary bill — no budget block"),
    ("PRE", "77.40", {"budget": {"level": "60.00"}}, "a budget block with no amount_due"),
    ("EMP", "31.05", {}, "an empty payload"),
    ("NUL", "12.00", None, "no payload at all"),
)


def _bills(brazos, dana):
    made = []
    for suffix, total, payload, _ in CASES:
        account = an_account(dana, brazos, account_no=f"ADE-{suffix}")
        made.append(
            an_issued_bill(
                brazos,
                account,
                number=f"BL-ADE-{suffix}",
                total=Decimal(total),
                issued_on=ISSUED_ON,
                bill_payload=payload,
            )
        )
    return made


def test_the_two_renderings_agree_bill_by_bill(brazos, dana):
    """`amount_due_for(bill)` == the annotated `amount_due`, for every bill."""
    with tenant_ctx(brazos):
        _bills(brazos, dana)
        annotated = {
            row["id"]: row["amount_due"]
            for row in billing_models.Invoice.objects.filter(invoice_no__startswith="BL-ADE-")
            .annotate(amount_due=selectors.amount_due_expression())
            .values("id", "amount_due")
        }
        assert annotated, "the fixture wrote no bills — this test measured nothing"

        disagreed = []
        for bill in billing_models.Invoice.objects.filter(invoice_no__startswith="BL-ADE-"):
            in_python = selectors.amount_due_for(bill)
            in_sql = annotated[bill.id]
            if Decimal(in_python) != Decimal(in_sql):
                disagreed.append(f"{bill.invoice_no}: python {in_python} vs sql {in_sql}")
        assert (
            disagreed == []
        ), "BR-BIL-072 is rendered twice and the two renderings disagree: " + "; ".join(disagreed)


def test_the_levelled_bill_asks_for_the_level_and_not_the_total(brazos, dana):
    """❄️ *"Level is due"* — the figure, not merely the agreement.

    ⚠ An equivalence test alone would pass if BOTH renderings returned the
    total, which is `DEF-062` restored on both sides at once. This asserts the
    frozen number.
    """
    with tenant_ctx(brazos):
        _bills(brazos, dana)
        row = (
            billing_models.Invoice.objects.filter(invoice_no="BL-ADE-WE8")
            .annotate(amount_due=selectors.amount_due_expression())
            .values("amount_due", "total")
            .get()
        )
        assert Decimal(row["amount_due"]) == Decimal("242.00")
        assert Decimal(row["total"]) == Decimal("292.87")


def test_the_expression_is_a_decimal_and_never_a_float(brazos, dana):
    """Hard rule 2 — `->>` hands PostgreSQL text and it is cast to NUMERIC."""
    with tenant_ctx(brazos):
        _bills(brazos, dana)
        for row in (
            billing_models.Invoice.objects.filter(invoice_no__startswith="BL-ADE-")
            .annotate(amount_due=selectors.amount_due_expression())
            .values("invoice_no", "amount_due")
        ):
            assert isinstance(row["amount_due"], Decimal), (
                f"{row['invoice_no']} came back as {type(row['amount_due']).__name__}; "
                "money on this path must never become a binary fraction"
            )


def test_the_queryset_carries_only_the_four_columns_the_seam_reads(brazos, dana):
    """`open_invoice_amounts_queryset` is a grouped read, not a bill renderer.

    Naming the columns is the guard against a later lane adding a
    `select_related` or a fifth value and turning one grouped scan into three
    joined tables read per open bill of the tenant.
    """
    with tenant_ctx(brazos):
        _bills(brazos, dana)
        queryset = selectors.open_invoice_amounts_queryset(("issued", "paid"))
        first = queryset.first()
        assert set(first) == {"id", "account_id", "due_date", "amount_due"}
        assert queryset.query.select_related is False
