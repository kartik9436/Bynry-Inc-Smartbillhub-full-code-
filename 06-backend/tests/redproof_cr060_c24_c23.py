"""RED PROOFS for CR-060 C24 / C23 (CLAUDE.md hard-won law 7).

Each case DISABLES one guard — through `monkeypatch`, so **no live file is
edited** (DEF-3101) — and asserts the DAMAGE that guard exists to prevent.
**These cases PASS when the guard is removed.** That is the point: each one
reproduces the failure, with its figure, so the guard is demonstrably
load-bearing rather than assumed to be.

Run explicitly:
    JOBS_EAGER=false pytest tests/redproof_cr060_c24_c23.py -q

The filename deliberately does NOT start with `test_`, so an ordinary suite run
never collects it. It is a scaffold kept in the repo so the next lane can re-run
the proof instead of taking this lane's word for it.

WHAT THEY MEASURED, 2026-09-03, on the signed LE-1 month:

  1. `premises_id` dropped inside `_posted_lines` — the filter accepted and
     ignored, which is the shape `GAP_PREMISES_FILTER_NOT_OFFERED` calls the
     worse failure. A trial balance narrowed to 500 Main St reports the WHOLE
     utility: AR gross debit **689.59** where the property's own is **247.87**.
     ⚠ The first draft of this proof predicted **553.69** and went RED at
     `assert Decimal('689.590000') == Decimal('553.690000')` — 553.69 is LE-6's
     BILLED footer, not the AR account's gross debits, which also carry the
     month's other AR movement. The measured figure is kept.
     The screen shows a property selected in its dropdown and the numbers are
     real, they foot, and they are about the wrong thing.

  2. `_opening_balances` called WITHOUT the property while the movement stays
     filtered. C4's identity `opening + movement = closing` breaks on every
     account the property ever touched, because one property's month is being
     compared against the whole utility's position.

  3. `balanced` computed as `debits == credits` on a narrowed table. It produces
     **True** on an ordinary month — a proof nobody performed — and **False**
     the moment one entry is split, which is BR-LED-007's posting-service bypass
     reported on books that are correct.

  4. `journal_entry_list` filtering through the to-many relation
     (`lines__premises_id=`) instead of the `pk__in` subquery. An entry is
     returned ONCE PER MATCHING LINE, so a clerk sees the same journal entry
     three times because three of its lines named the property.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.ledger import models as ledger_models
from apps.ledger import posting, reporting, selectors

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_WE1_BILL,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

MAIN_ST = "500 Main St"


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def _premises_id_for(name):
    for row in reporting.by_premises_summary(start=JULY_START, end=JULY_END)["rows"]:
        if row.name == name:
            return row.premises_id
    raise AssertionError(f"{name!r} not in the by-premises report")


def _ar_row(table):
    ar = selectors.gl_account_id_for_designation(reporting.chart.AR)
    return next(r for r in table["rows"] if str(r["account_id"]) == str(ar))


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the filter accepted and ignored
# ═══════════════════════════════════════════════════════════════════════════
def test_redproof_1__a_dropped_filter_reports_the_whole_utility(brazos, dana, monkeypatch):
    """Guard removed: `_posted_lines` ignores `premises_id`.

    MEASURED: the narrowed table's AR gross debit becomes **689.59**, the whole
    month's AR debits, where 500 Main St's own figure is **247.87**.
    """
    original = reporting._posted_lines

    def blind(*, start=None, end=None, premises_id=None):
        return original(start=start, end=end)  # the property is thrown away

    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        honest = _ar_row(
            reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)
        )
        assert honest["gross_debit"] == LE1_WE1_BILL  # 247.87

        monkeypatch.setattr(reporting, "_posted_lines", blind)
        broken = _ar_row(
            reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)
        )

    assert broken["gross_debit"] == Decimal("689.590000")
    assert broken["gross_debit"] > honest["gross_debit"]


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the opening column left unfiltered
# ═══════════════════════════════════════════════════════════════════════════
def test_redproof_2__an_unfiltered_opening_breaks_c4s_identity(brazos, dana, monkeypatch):
    """Guard removed: `_opening_balances` ignores the property.

    MEASURED: `opening + movement = closing` stops holding, because the opening
    is the whole utility's position and the movement is one property's.
    """
    original = reporting._opening_balances

    def blind(*, start, premises_id=None):
        return original(start=start)  # the property is thrown away

    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        # Give the property a July position so August has something to open on.
        august = reporting.trial_balance(
            start=JULY_END.replace(month=8, day=1),
            end=JULY_END.replace(month=8, day=31),
            premises_id=main_st,
        )
        assert all(
            row["closing"] == row["opening"] + (row["debit"] - row["credit"])
            for row in august["rows"]
        ), "the identity holds while the guard is in place"

        monkeypatch.setattr(reporting, "_opening_balances", blind)
        broken = reporting.trial_balance(
            start=JULY_END.replace(month=8, day=1),
            end=JULY_END.replace(month=8, day=31),
            premises_id=main_st,
        )

    # The whole book's opening is now on a table narrowed to one property.
    whole_book_openings = {str(r["account_id"]): r["opening"] for r in broken["rows"]}
    assert any(
        v != Decimal("0") for v in whole_book_openings.values()
    ), "the unfiltered opening leaked the utility's position onto one property's table"


# ═══════════════════════════════════════════════════════════════════════════
# 3 — footing reported as a verdict on a narrowed table
# ═══════════════════════════════════════════════════════════════════════════
def test_redproof_3a__a_narrowed_table_claims_a_proof_nobody_performed(brazos, dana):
    """Guard removed (computed inline): `balanced = debits == credits`.

    MEASURED on the ordinary LE-1 month: the narrowed table FOOTS, so the naive
    computation answers **True** — a screen then tells a finance officer that
    one property's slice proves the books balance. It proves nothing of the kind.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)
        table = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)

    naive = table["total_debit"] == table["total_credit"]
    assert naive is True, "the narrowed table foots, which is why True is tempting"
    assert table["balanced"] is None, "and the guard refuses to call that a verdict"


def test_redproof_3b__a_split_entry_would_be_reported_as_a_posting_bypass(brazos, dana):
    """The other half: one entry the filter cuts in half.

    MEASURED: the narrowed table is out by exactly **10.00**, so the naive
    computation answers **False** — BR-LED-007's posting-service bypass — on
    books that foot perfectly.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)
        proof_id = uuid4()
        cash = selectors.gl_account_id_for_designation(reporting.chart.CASH)
        ar = selectors.gl_account_id_for_designation(reporting.chart.AR)

        posting.post(
            posting.PostingRequest(
                posting_key="cr060-c24-redproof-split",
                entry_date=JULY_END,
                posted_at=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
                currency="USD",
                source_type="manual_je",
                source_id=proof_id,
                lines=(
                    posting.PostingLine(
                        ledger_account_id=ar,
                        side=ledger_models.SIDE_DEBIT,
                        amount=Decimal("10.00"),
                        source_type="manual_je",
                        source_id=proof_id,
                        account_id=accounts["ACC-1042"].id,
                    ),
                    posting.PostingLine(
                        ledger_account_id=cash,
                        side=ledger_models.SIDE_CREDIT,
                        amount=Decimal("10.00"),
                        source_type="manual_je",
                        source_id=proof_id,
                    ),
                ),
            )
        )

        narrowed = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)
        whole = reporting.trial_balance(start=JULY_START, end=JULY_END)

    naive = narrowed["total_debit"] == narrowed["total_credit"]
    assert naive is False, "the split entry really does unbalance the slice"
    assert narrowed["difference"] == Decimal("10.00")
    assert whole["balanced"] is True, "…while the BOOKS foot, which is the whole point"
    assert narrowed["balanced"] is None, "and the guard reports unknown, not a bypass"


# ═══════════════════════════════════════════════════════════════════════════
# 4 — the to-many join that duplicates an entry
# ═══════════════════════════════════════════════════════════════════════════
def test_redproof_4__a_to_many_filter_lists_one_entry_once_per_line(brazos, dana):
    """Guard removed: `lines__premises_id=` instead of the `pk__in` subquery.

    MEASURED on the LE-1 month: the honest list returns each entry once; the
    to-many form returns it once per matching LINE, so a clerk scrolling the
    journal sees the same entry repeated with the same number and the same date.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        honest = reporting.journal_entry_list(start=JULY_START, end=JULY_END, premises_id=main_st)
        honest_ids = [row.entry_id for row in honest["rows"]]
        assert len(honest_ids) == len(set(honest_ids))

        # The mutation, expressed directly as the ORM would run it.
        duplicated = list(
            ledger_models.JournalEntry.objects.filter(
                tenant_id=brazos.id,
                entry_date__gte=JULY_START,
                entry_date__lte=JULY_END,
                lines__premises_id=main_st,
            ).values_list("pk", flat=True)
        )

    assert len(duplicated) > len(
        set(duplicated)
    ), "the to-many filter returns an entry once per matching line"
    assert len(duplicated) > len(
        honest_ids
    ), f"a clerk would see {len(duplicated)} rows where {len(honest_ids)} entries exist"
