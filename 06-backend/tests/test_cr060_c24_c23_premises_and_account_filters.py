# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 C24 (filter the General Ledger by property) · C23 (open a
#           trial-balance line to its entries)
#           Screens: S56 (trial balance · journal list)
# Rules:    BR-LED-001 (the dimension set, stamped AT POSTING) · BR-LED-007
#           (an unbalanced book means a posting-service bypass) · BR-LED-011 ·
#           BR-LED-012 (the journal list) · BR-REP-002 (one derivation, grouped
#           differently — never a side-maintained number) · BR-MET-046 (units
#           never move between premises) · CLAUDE.md rule 1 (tenant scoping)
# Golden:   LE-6 — 500 Main St 247.87 · Oak Grove 16.42 · Marina Bay 289.40,
#           footing to 553.69 (US-LED-010 §7 CONFIRMED)
# Defects:  DEF-127 (unknown is not zero, and here: unknown is not FALSE) ·
#           DEF-2345 (the read model that computes the per-premises figure said
#           in writing that it could not)
# ───────────────────────────────────────────────────────
"""C24 and C23 — narrowing the General Ledger, and what narrowing costs.

⚠ **THE ONE THING TO UNDERSTAND BEFORE CHANGING ANYTHING HERE: A NARROWED TRIAL
BALANCE USUALLY FOOTS, AND THAT IS EXACTLY WHY ITS FOOTING IS NOT A VERDICT.**

**THIS FILE'S FIRST DRAFT ASSERTED THE OPPOSITE AND THE TEST WENT RED, WHICH IS
THE MOST USEFUL THING IN IT.** It claimed *"a filtered trial balance does not
foot"*, reasoning that a receipt's cash leg carries no property so the filter
would strip it and leave the AR leg behind. Measured against the signed LE-1
month, that is false:

    500 Main St   debit 446.37  credit 446.37   foots
    Marina Bay    debit 289.40  credit 289.40   foots
    Oak Grove     debit  16.42  credit  16.42   foots
    …and 0 of the month's 28 journal lines carry no property at all.

`posting._stamped` resolves the chain from the **account**, and both legs of a
receipt name the same customer account, so both legs get the same property. The
wrong version is written down here rather than deleted because it is the version
a reader reconstructs from first principles, and the second-best outcome is that
they meet the correction before they act on it.

**WHAT IS ACTUALLY TRUE.** A narrowed table fails to foot only when the filter
cuts an entry in half, and there are two lawful ways for that to happen: a line
naming NO account is never stamped (a bank fee, a deposit-batch cash leg —
`posting._stamped`), and one entry can legitimately span two properties (a
master-account transfer, per `models.JournalLine`). `test_c24_tc3b` BUILDS the
first of those rather than describing it.

**SO `balanced` IS `None` ON A NARROWED TABLE — AND `True` WOULD BE AS WRONG AS
`False`.** A mismatch there is indistinguishable from BR-LED-007's
posting-service bypass, which is a serious claim; and a match proves nothing
about the books, only about the slice. DEF-127 one column over: a verdict nobody
can compute must not render as one somebody computed.

**WHY THE JOURNAL LIST MAKES THE OPPOSITE CHOICE, AND IT IS NOT AN
INCONSISTENCY.** A trial balance is a table of SUMS, so narrowing it must narrow
the sums. The journal list is a list of ENTRIES, and half an entry is not an
entry: totalling only the matching lines would show `balanced: false` on entries
that balance perfectly. So `f.premises` and `f.ledger_account` SELECT entries by
what their lines carry and then show each entry **in full**.

**HOW EACH ASSERTION HERE WAS PROVED RED FIRST (hard-won law 7).** Every one was
run against a deliberately broken build before being trusted green, by
`monkeypatch` and never by editing a live file (DEF-3101). The four mutations and
what each produced:

  1. `balanced` computed as `debits == credits` on a narrowed table instead of
     `None` → `test_c24_tc3` fails
     `AssertionError: assert True is None` on the ordinary month and
     `assert False is None` on `tc3b`'s split entry. Both are the same defect:
     the first claims a proof nobody performed, the second reports a
     posting-service bypass on books that are correct.
  2. `_opening_balances` called WITHOUT `premises_id` while the movement is
     filtered → `test_c24_tc2` fails
     `AssertionError: opening 0.00 != -247.87` — one property's month opening
     shown against the whole utility's position, breaking C4's identity.
  3. `premises_id` dropped in `_posted_lines` (the filter accepted and ignored)
     → `test_c24_tc1` fails
     `AssertionError: assert Decimal('553.69') == Decimal('247.87')` — the
     report LOOKS filtered and is not, which
     `reporting.GAP_PREMISES_FILTER_NOT_OFFERED` names as the worse failure.
  4. `journal_entry_list` filtering with `lines__premises_id=` instead of the
     `pk__in` subquery → `test_c23_tc2` fails
     `AssertionError: assert 4 == 3` — one entry returned once per matching
     line, so a clerk sees the same journal entry three times.

**AND ONE ASSERTION IS HERE BECAUSE OF WHAT A SIBLING LANE FOUND RATHER THAN
BECAUSE C24 ASKED FOR IT.** A panel on a money screen claimed a built feature was
*"Not built"* and survived because its test asserted each sentence was PRESENT,
never that it was TRUE. So `test_c24_tc5` does not check that a gap notice
renders — it checks that the notice is emitted **only** when it is true, and that
the unfiltered report does not carry it.
"""

from decimal import Decimal

import pytest

from apps.ledger import models as ledger_models
from apps.ledger import reporting

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_WE1_BILL,
    make_accounts,
    post_le1_month,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: LE-6's first row. 500 Main St is the premises this file narrows to throughout,
#: because it is the one whose bill AND receipt both land inside the LE-1 month —
#: so it exercises the interesting case (an entry whose other leg is filtered
#: out) rather than a property that was only ever billed.
MAIN_ST = "500 Main St"


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def _premises_id_for(name):
    """The premises id behind an LE-6 row name, read from the STAMP.

    Deliberately resolved out of `by_premises_summary` rather than by querying
    metering: this file must narrow on the same id a screen would receive from
    the picker, and that is the id the report already publishes.
    """
    report = reporting.by_premises_summary(start=JULY_START, end=JULY_END)
    for row in report["rows"]:
        if row.name == name:
            return row.premises_id
    raise AssertionError(f"{name!r} is not in the by-premises report")


# ═══════════════════════════════════════════════════════════════════════════
# C24 — the property filter
# ═══════════════════════════════════════════════════════════════════════════
def test_c24_tc1__the_filter_narrows_the_figures_and_does_not_merely_accept_a_value(brazos, dana):
    """A narrowed trial balance shows ONE property's AR, not the whole book's.

    **Proved RED by dropping `premises_id` in `_posted_lines`** — the shape of a
    filter that is accepted and ignored:
        `AssertionError: assert Decimal('553.69') == Decimal('247.87')`
    That is the failure `reporting.GAP_PREMISES_FILTER_NOT_OFFERED` calls the
    worse one: the screen shows a property selected in its dropdown and the
    numbers are the entire utility's. They are real, they foot, and they are
    about the wrong thing.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        whole = reporting.trial_balance(start=JULY_START, end=JULY_END)
        narrowed = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)

        ar = reporting._designated_account_id(reporting.chart.AR)
        whole_ar = next(r for r in whole["rows"] if str(r["account_id"]) == str(ar))
        narrow_ar = next(r for r in narrowed["rows"] if str(r["account_id"]) == str(ar))

        # 500 Main St was billed 247.87 of the month's 553.69.
        assert narrow_ar["gross_debit"] == LE1_WE1_BILL
        assert whole_ar["gross_debit"] > narrow_ar["gross_debit"]

        # The echo exists so a screen renders what it ASKED for, not what it
        # believes it asked for.
        assert narrowed["premises_id"] == str(main_st)
        assert whole["premises_id"] is None


def test_c24_tc2__the_opening_column_is_narrowed_by_the_same_filter(brazos, dana):
    """C4's identity is per account and must survive the filter.

    `opening + movement = closing`, on the narrowed table, using the narrowed
    opening. **Proved RED by calling `_opening_balances` without `premises_id`
    while the movement stayed filtered:**
        `AssertionError: opening 0.00 != -247.87`
    — a property's August opening shown as the whole utility's position, which
    is the one comparison the opening column exists to make honest.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        # A window AFTER the LE-1 month: July's movement is now the opening.
        august = reporting.trial_balance(
            start=JULY_END.replace(day=1).replace(month=8),
            end=JULY_END.replace(day=31).replace(month=8),
            premises_id=main_st,
        )
        july = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)

        # Every row: the identity holds inside the narrowed table.
        for row in july["rows"]:
            assert row["closing"] == row["opening"] + (row["debit"] - row["credit"])

        # And August's opening for this property equals July's closing for it —
        # the tie-out between two months that C4 exists to give a bookkeeper.
        july_closing = {str(r["account_id"]): r["closing"] for r in july["rows"]}
        for row in august["rows"]:
            if str(row["account_id"]) in july_closing:
                assert row["opening"] == july_closing[str(row["account_id"])]


def test_c24_tc3__balanced_is_none_on_a_narrowed_table_even_when_it_foots(brazos, dana):
    """The whole reason this file has a docstring — and the case that corrected it.

    On the signed LE-1 month **every narrowed table foots**, because both legs of
    a receipt name the same customer account and `_stamped` gives them the same
    property. So this test asserts the sums MATCH and the verdict is still
    `None`: a narrowed table that foots has proved something about the slice and
    nothing about the books.

    **Proved RED by computing `balanced` as `debits == credits` when narrowed:**
        `AssertionError: assert True is None`
    which is the version that claims a proof nobody performed. `tc3b` is the
    other half, where the same mutation produces `assert False is None`.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        narrowed = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)
        whole = reporting.trial_balance(start=JULY_START, end=JULY_END)

        # It DOES foot — asserted so the docstring above cannot rot back into
        # its first, wrong version without this going red.
        assert narrowed["total_debit"] == narrowed["total_credit"]
        assert narrowed["difference"] == ZERO
        # …and it is still not a verdict.
        assert narrowed["balanced"] is None

        # The unfiltered book still foots and still SAYS so. The null must not
        # have cost us the real verdict.
        assert whole["balanced"] is True
        assert whole["total_debit"] == whole["total_credit"]


def test_c24_tc3b__an_entry_the_filter_cuts_in_half_does_not_foot_and_is_not_a_bypass(brazos, dana):
    """The case the null actually protects, BUILT rather than described.

    A bank fee is the lawful shape: `posting._stamped` leaves a line naming no
    account alone, because that money *"is about the utility's own bank account,
    not about anyone's premises"*. So an entry pairing a property-stamped line
    with an unstamped one splits under the filter, and the narrowed table shows
    a real difference on books that are perfectly correct.

    **Proved RED by computing `balanced` as `debits == credits` when narrowed:**
        `AssertionError: assert False is None`
    — BR-LED-007's posting-service bypass reported to a finance officer whose
    books have not been bypassed at all.
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    from apps.ledger import posting, selectors

    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)
        account_id = accounts["ACC-1042"].id  # 500 Main St, the property this test narrows to

        proof_id = uuid4()
        cash = selectors.gl_account_id_for_designation(reporting.chart.CASH)
        ar = selectors.gl_account_id_for_designation(reporting.chart.AR)

        # DR AR (carries the account, so it is STAMPED with the property)
        # CR cash (names no account, so it is left undimensioned — the rule).
        posting.post(
            posting.PostingRequest(
                posting_key="cr060-c24-split-entry-proof",
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
                        account_id=account_id,
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

        # The split is real: the AR debit is inside the filter and the cash
        # credit is not, so the narrowed table is out by exactly the 10.00.
        assert narrowed["difference"] == Decimal("10.00")
        assert narrowed["total_debit"] != narrowed["total_credit"]

        # …and it is reported as UNKNOWN, not as a bypass.
        assert narrowed["balanced"] is None
        assert narrowed["balanced"] is not False

        # The books themselves are untouched and still foot. This is the
        # comparison that proves the difference above is the FILTER's and not
        # the ledger's.
        assert whole["balanced"] is True


def test_c24_tc4__a_property_with_no_lines_is_an_empty_report_not_the_whole_book(brazos, dana):
    """The failure mode of a filter that silently stops applying.

    An id that parses and matches nothing is the TRUE answer to *"what did this
    property do?"* for a property with no lines — an empty table. What it must
    never be is the unfiltered book, which is what a dropped filter produces.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        # A well-formed id belonging to no line in this tenant.
        nothing = "00000000-0000-7000-8000-000000000000"

        empty = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=nothing)
        assert empty["rows"] == ()
        assert empty["total_debit"] == ZERO
        assert empty["total_credit"] == ZERO
        assert empty["balanced"] is None


def test_c24_tc6__an_unparseable_property_id_empties_the_report_never_unfilters_it(brazos, dana):
    """The API layer's parse, and the invariant it exists to hold.

    `?premises=not-a-uuid` must NEVER come back as the whole ledger. It comes
    back EMPTY instead — see `api._optional_uuid` for why an empty table rather
    than a refusal (the refusal needs a sentence in eleven catalogues, and G32
    is explicit that a raised key with no entry renders as SILENCE).

    **This is the assertion that would catch the tempting "simplification"** —
    dropping the parse and letting an unparseable value mean *no filter*, which
    is the one outcome the whole parameter must never produce.
    """
    from django.test import RequestFactory

    from apps.ledger import api as ledger_api

    request = RequestFactory().get("/ledger/trial-balance", {"premises": "not-a-uuid"})
    parsed = ledger_api._optional_uuid(request.GET, "premises")

    assert parsed is not None, "an unparseable id must not degrade to 'no filter'"
    assert parsed == ledger_api._MATCHES_NOTHING

    with tenant_ctx(brazos):
        a_month(brazos, dana)
        table = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=parsed)
        whole = reporting.trial_balance(start=JULY_START, end=JULY_END)

        assert table["rows"] == ()
        assert table["total_debit"] == ZERO
        # …and emphatically NOT the unfiltered book.
        assert whole["rows"] != ()
        assert whole["total_debit"] > ZERO

    # An absent or empty value IS "no filter", and stays that way.
    for blank in ({}, {"premises": ""}, {"premises": "   "}):
        blank_request = RequestFactory().get("/ledger/trial-balance", blank)
        assert ledger_api._optional_uuid(blank_request.GET, "premises") is None


def test_c24_tc5__the_gap_notice_is_emitted_only_when_it_is_true(brazos, dana):
    """⚠ This asserts the notice is TRUE, not that it renders.

    A sibling lane found a panel claiming a built feature was *"Not built"*,
    which survived because its test asserted each sentence was PRESENT and never
    that it was true — so no assertion in it could go red when the feature
    shipped. The lesson applied here: the interesting direction is the
    UNFILTERED report, which must NOT carry this notice.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        narrowed = reporting.trial_balance(start=JULY_START, end=JULY_END, premises_id=main_st)
        whole = reporting.trial_balance(start=JULY_START, end=JULY_END)

        codes = {gap["code"] for gap in narrowed["unavailable"]}
        assert reporting.GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT["code"] in codes

        # The half that catches a notice pinned open: an unfiltered report foots
        # and must say nothing of the kind.
        assert whole["unavailable"] == ()


# ═══════════════════════════════════════════════════════════════════════════
# C23 — open a trial-balance line to its entries
# ═══════════════════════════════════════════════════════════════════════════
def test_c23_tc1__the_account_filter_returns_the_entries_that_touched_it(brazos, dana):
    """C23's acceptance: click an account row, see the entries behind it.

    Served as `f.ledger_account` on the journal list rather than as a second
    read model, because the row a clerk clicks IS a chart account and the list
    is already on that screen.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        ar = reporting._designated_account_id(reporting.chart.AR)

        listed = reporting.journal_entry_list(start=JULY_START, end=JULY_END, ledger_account_id=ar)
        everything = reporting.journal_entry_list(start=JULY_START, end=JULY_END)

        assert listed["rows"], "the AR account has entries behind it"
        assert len(listed["rows"]) < len(everything["rows"]), "the filter narrows"

        # Every entry returned really does have a line on that account — read
        # from the rows themselves, not inferred from the count.
        returned = {row.entry_id for row in listed["rows"]}
        touching = {
            str(entry_id)
            for entry_id in ledger_models.JournalLine.objects.filter(
                tenant_id=brazos.id, ledger_account_id=ar
            ).values_list("journal_entry_id", flat=True)
        }
        assert returned <= touching


def test_c23_tc2__an_entry_with_several_matching_lines_appears_ONCE(brazos, dana):
    """The join-shaped bug this filter is deliberately written to avoid.

    **Proved RED with `lines__premises_id=` in place of the `pk__in`
    subquery:**
        `AssertionError: assert 4 == 3`
    A to-many filter duplicates the parent once per matching child, so a clerk
    sees the same journal entry three times because three of its lines named the
    property. The subquery asks the existence question once per entry, which is
    the question being asked.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        listed = reporting.journal_entry_list(start=JULY_START, end=JULY_END, premises_id=main_st)
        ids = [row.entry_id for row in listed["rows"]]
        assert len(ids) == len(set(ids)), "an entry is listed once, however many lines match"


def test_c23_tc3__a_filtered_row_still_shows_the_WHOLE_entry_and_still_balances(brazos, dana):
    """Half an entry is not an entry — the opposite choice to `trial_balance`.

    If this list totalled only the MATCHING lines, a filtered row would read
    `balanced: false` on entries that balance perfectly. That is the same false
    alarm C24 refuses to raise one function up, and it is why the row stays
    whole here while the trial balance's sums are narrowed.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)

        listed = reporting.journal_entry_list(
            start=JULY_START, end=JULY_END, premises_id=main_st, status="posted"
        )
        assert listed["rows"], "the property has posted entries"
        for row in listed["rows"]:
            assert row.balanced is True, "a posted entry balances, filtered or not"
            assert row.debit == row.credit


def test_c23_tc4__the_two_filters_compose(brazos, dana):
    """C24 and C23 together — one property's activity on one account.

    Composition is the case a screen actually produces (a clerk filters the
    General Ledger by property and then clicks an account row), and it is where
    two independently-correct filters most often turn out to overwrite each
    other.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        main_st = _premises_id_for(MAIN_ST)
        ar = reporting._designated_account_id(reporting.chart.AR)

        both = reporting.journal_entry_list(
            start=JULY_START, end=JULY_END, premises_id=main_st, ledger_account_id=ar
        )
        by_premises = reporting.journal_entry_list(
            start=JULY_START, end=JULY_END, premises_id=main_st
        )

        assert {r.entry_id for r in both["rows"]} <= {r.entry_id for r in by_premises["rows"]}
        for row in both["rows"]:
            entry_lines = ledger_models.JournalLine.objects.filter(
                tenant_id=brazos.id, journal_entry_id=row.entry_id
            )
            assert entry_lines.filter(premises_id=main_st).exists()
            assert entry_lines.filter(ledger_account_id=ar).exists()
