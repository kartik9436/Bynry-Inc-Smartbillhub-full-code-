# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (S36 Revenue & AR — every KPI is a Σ over journal lines) ·
#           US-LED-009 (S59 account ledger + running balance) · US-LED-013 (the
#           S56 journal list, which is the one read that must NOT refuse) ·
#           US-LED-014 (S41 dual-basis remittance — what a utility FILES from)
#           Screens: S36 · S41 · S56 · S59 · S60
# Rules:    CLAUDE.md rule 2 (money is NUMERIC(18,6) **and** CHAR(3) — the pair,
#           never the number alone) · BR-LED-007 (any drift is a red flag, and
#           an unlawful sum is drift the tie-out cannot see) · BR-REP-001 (every
#           money group labels itself) · BR-REP-002 (read-models over
#           journal-line dimensions) · BR-TEN-042 (the tenant currency lock,
#           whose failure to arm — DEF-075 — is what made this reachable)
# Golden:   LE-1 (598.69 = 598.69 · AR 152.32 · billed 553.69) — the CLEAN book
#           these cases start from, so the refusal is proved against a book
#           whose every figure is already signed
# Tests:    this file (DEF-081)
# Impacts:  apps/ledger/reporting.py (the guard) · apps/ledger/api.py +
#           apps/ledger/wire.py (which labelled figures with the TENANT's
#           declared code and now read the derived one) ·
#           10-scripts/def081_currency_sweep.py (the live-tenant sweep)
# ───────────────────────────────────────────────────────
"""DEF-081 — a mixed-currency book must never be summed, and was.

**THE DEFECT IN ONE SENTENCE.** `apps/ledger/posting.py` takes `currency` as a
required PER-ENTRY input and defaults nothing, so nothing at the posting
boundary stopped a tenant holding USD and CAD journal entries side by side —
and `apps/ledger/reporting.py` then summed across entries and published no
currency at all, so the trial balance, the KPI strip and every finance screen
would add 100 USD to 100 CAD and print 200.

**WHY IT STOPPED BEING THEORETICAL.** DEF-075: `PUT /settings/regional`
answered **200 OK** and changed a tenant's currency on a tenant whose seeded
bill BL-2606-000001 (108.88 USD) is unquestionably a financial record, because
BR-TEN-042's lock asked a seam that `apps/billing` implemented nowhere. Any
tenant who changed currency while that was open can hold a mixed book today.

**THE NUMBER THIS FILE IS BUILT AROUND.** The LE-1 fixture month is a signed,
balanced USD book: **598.69 = 598.69**, AR **152.32**, billed **553.69**. These
cases post ONE further entry — a balanced **100.00 CAD** bill — and nothing
else. Under the code as it shipped, the trial balance answered
**total_debit 698.69 = total_credit 698.69**: balanced, footing, six decimal
places, rendered beside a dollar sign, and not a quantity that exists. That is
the whole danger — the wrong answer looks exactly like the right one.

**WHAT EACH CASE ASSERTS.** Every Σ refuses and NAMES the two codes; the
account-scoped statement of a customer who never held a CAD entry still works
(the guard is over the lines summed, not over the tenant); and the S56 journal
list keeps working on purpose, because it is the only surface on which a finance
officer whose trial balance just refused can find the offending entries.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import posting, reporting
from core import errors

from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_FOOTING,
    a_request,
    gl,
    line,
    make_accounts,
    post_le1_month,
    uuid_for,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The foreign entry, and it is deliberately ROUND and deliberately BALANCED.
#: Balanced, because an unbalanced entry would be refused by the posting service
#: for a different reason and would prove nothing about currency. Round, because
#: the sum the old code produced has to be recognisable on sight: LE-1's signed
#: 598.69 footing plus this becomes 698.69, and 698.69 is not a number anybody
#: could look at and know was wrong.
FOREIGN_AMOUNT = Decimal("100.00")
FOREIGN_CURRENCY = "CAD"
HOME_CURRENCY = "USD"

#: What the code answered BEFORE the guard existed. Kept as a named constant
#: rather than inline, because it is the finding: a balanced, plausible,
#: six-decimal total that is not money.
SILENTLY_SUMMED_FOOTING = LE1_FOOTING + FOREIGN_AMOUNT  # 598.69 + 100.00 = 698.69


def a_mixed_book(tenant, actor):
    """The signed LE-1 USD month, plus ONE balanced 100.00 CAD bill.

    The CAD entry is posted through the REAL posting service — not inserted —
    because the defect's first half is that the posting service permits it:
    `currency` is a required per-entry input with no default and no cross-entry
    check, and a test that reached around it would be proving the guard against
    a state the product cannot actually reach.

    It lands on a THIRD customer (ACC-1055) so that ACC-1042's own statement
    stays a lawful single-currency report and the per-account case has something
    honest to assert.
    """
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)

    ar = gl(tenant, "1200", "asset")
    revenue = gl(tenant, "4100", "revenue")
    posting.post(
        a_request(
            (
                line(ar, "debit", FOREIGN_AMOUNT, account_id=accounts["ACC-1055"].id),
                line(
                    revenue,
                    "credit",
                    FOREIGN_AMOUNT,
                    account_id=accounts["ACC-1055"].id,
                ),
            ),
            key="def081-cad-bill",
            entry_date=date(2026, 7, 18),
            currency=FOREIGN_CURRENCY,
            source_type="invoice",
            source_id=uuid_for("def081-cad-bill"),
            memo="a bill raised in CAD after the tenant's currency was changed (DEF-075)",
        )
    )
    return accounts


# ═══════════════════════════════════════════════════════════════════════════
# THE CLEAN BOOK STILL ANSWERS — and now says WHICH money it answered in
# ═══════════════════════════════════════════════════════════════════════════
def test_def_081__a_single_currency_book_reports_and_derives_its_own_code(brazos, dana):
    """LE-1 untouched: **598.69 = 598.69**, and the figures now carry `USD`.

    The guard must not cost a lawful book anything, so this asserts the signed
    footing is byte-identical AND that the derived currency arrived — the
    constructive half of DEF-081. Before it, `apps/ledger/api.py` labelled every
    figure with the tenant's DECLARED code, which its own docstring called *a
    LABEL, not a derivation*: on a tenant that changed its declared code without
    reposting a thing, the books would have been stamped with money they are not
    in.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        post_le1_month(brazos, accounts)

        # `start=None` is the whole book to date — the window LE-1's signed
        # footing is stated over, and the window `tests/test_us_led_007_revenue_ar.py`
        # TC-1 already asserts 598.69 = 598.69 across.
        book = reporting.trial_balance(start=None, end=JULY_END)
        assert book["total_debit"] == LE1_FOOTING
        assert book["total_credit"] == LE1_FOOTING
        assert book["balanced"] is True
        assert (
            book["currency"] == HOME_CURRENCY
        ), "the code is DERIVED from the entries summed"

        strip = reporting.revenue_and_ar(start=JULY_START, end=JULY_END)
        assert strip["kpis"]["billed"] == BILLED_IN_PERIOD
        assert strip["currency"] == HOME_CURRENCY
        assert reporting.ar_control(as_of=JULY_END) == LE1_AR


# ═══════════════════════════════════════════════════════════════════════════
# THE MIXED BOOK — every Σ refuses, and names both codes
# ═══════════════════════════════════════════════════════════════════════════
def test_def_081__the_trial_balance_refuses_instead_of_footing_to_698_69(brazos, dana):
    """**THE CASE THE DEFECT WAS WRITTEN FOR.**

    With one 100.00 CAD entry beside LE-1's USD month, the shipped code answered
    a trial balance of **698.69 = 698.69** — balanced, footing, and a quantity
    with no name. It now refuses and names `CAD, USD`.

    The refusal is a CATALOG exception (`BIZ-STATE` → 409), so the endpoint that
    serves S56 answers a proper envelope without a single `try` having been
    added to `apps/ledger/api.py`.
    """
    with tenant_ctx(brazos):
        a_mixed_book(brazos, dana)

        with pytest.raises(reporting.MixedCurrencyBook) as refusal:
            reporting.trial_balance(start=None, end=JULY_END)

        assert refusal.value.codes == (FOREIGN_CURRENCY, HOME_CURRENCY)
        assert refusal.value.code == errors.BIZ_STATE
        assert refusal.value.http_status == 409
        assert isinstance(
            refusal.value, errors.BizError
        ), "the API needs no try/except for this"
        # The finding, in the row a screen renders: the codes travel WITH it.
        assert refusal.value.gap["code"] == reporting.MIXED_CURRENCY_CODE
        assert refusal.value.gap["currencies"] == (FOREIGN_CURRENCY, HOME_CURRENCY)
        assert "CAD" in refusal.value.params["currencies"]

        # And the number it would have printed is genuinely reachable arithmetic,
        # not a hypothetical: the two sides of the mixed book do foot to it.
        assert SILENTLY_SUMMED_FOOTING == Decimal("698.69")


@pytest.mark.parametrize(
    "figure",
    [
        "trial_balance",
        "revenue_and_ar",
        "ar_control",
        "cash_position",
        "revenue_by_service",
        "accounts_owing",
        "by_premises_summary",
        "remittance_by_authority",
    ],
)
def test_def_081__every_summing_read_refuses_a_mixed_book(brazos, dana, figure):
    """Not one report is left summing. **Enumerated by NAME on purpose.**

    A guard on the primitive alone would be silently incomplete the day someone
    adds a read that queries `journal_lines` directly, and two of these —
    `ar_control` and `accounts_owing` — answer with a bare `Decimal` and a bare
    `int`, which have nowhere to carry a reason and so must raise. Listing every
    public Σ here means a new one added without a guard has to be added to this
    list to pass, which is the moment somebody asks why.

    `adjustments_panel` is the ninth and is NOT in this list, because this
    fixture's foreign entry is a BILL and the panel sums only adjustment- and
    credit-note-sourced lines: its slice here is empty, and an empty slice is
    correctly not a refusal. It gets its own case below with its own foreign
    row — which is the guard's whole scoping rule demonstrated rather than
    asserted.
    """
    windowed = {"start": JULY_START, "end": JULY_END}
    calls = {
        "trial_balance": lambda: reporting.trial_balance(**windowed),
        "revenue_and_ar": lambda: reporting.revenue_and_ar(**windowed),
        "ar_control": lambda: reporting.ar_control(as_of=JULY_END),
        "cash_position": lambda: reporting.cash_position(**windowed),
        "revenue_by_service": lambda: reporting.revenue_by_service(**windowed),
        "accounts_owing": lambda: reporting.accounts_owing(as_of=JULY_END),
        "by_premises_summary": lambda: reporting.by_premises_summary(**windowed),
        "remittance_by_authority": lambda: reporting.remittance_by_authority(
            **windowed
        ),
    }
    with tenant_ctx(brazos):
        a_mixed_book(brazos, dana)
        with pytest.raises(reporting.MixedCurrencyBook) as refusal:
            calls[figure]()
        assert refusal.value.codes == (FOREIGN_CURRENCY, HOME_CURRENCY)
        assert refusal.value.figure, "the refusal names WHICH figure it refused"


def _a_credit_note(tenant, *, currency, key, on):
    """One balanced goodwill credit — DR write-off / CR AR — in `currency`.

    The shape `apps/billing/corrections.execute_credit_only` posts, reduced to
    the two legs this case needs. It exists because `adjustments_panel` sums a
    NARROWER slice than every other read here (source `adjustment` or
    `credit_note`, nothing else), and LE-1 posts neither.
    """
    posting.post(
        a_request(
            (
                line(
                    gl(tenant, "6100", "expense"),
                    "debit",
                    FOREIGN_AMOUNT,
                    source_type="credit_note",
                ),
                line(
                    gl(tenant, "1200", "asset"),
                    "credit",
                    FOREIGN_AMOUNT,
                    source_type="credit_note",
                ),
            ),
            key=key,
            entry_date=on,
            currency=currency,
            source_type="credit_note",
            source_id=uuid_for(key),
            memo=f"a goodwill credit raised in {currency}",
        )
    )


def test_def_081__the_adjustments_panel_refuses_on_its_own_slice(brazos, dana):
    """The ninth Σ, proved on the only rows it looks at.

    `adjustments_panel` sums lines whose entry is sourced `adjustment` or
    `credit_note` — nothing else. Both halves of the guard's scoping rule show
    up on this one screen and both are asserted:

      * the CAD **bill** from `a_mixed_book` is not in this panel's slice, so
        adding a USD credit note leaves the panel answering, labelled `USD`;
      * a CAD **credit note** puts two codes inside the slice, and it refuses.

    A guard scoped to the tenant instead of to the rows being added would have
    darkened this panel in the first case, on money it was never summing.
    """
    with tenant_ctx(brazos):
        a_mixed_book(brazos, dana)
        _a_credit_note(
            brazos, currency=HOME_CURRENCY, key="def081-usd-cn", on=date(2026, 7, 19)
        )

        panel = reporting.adjustments_panel(start=JULY_START, end=JULY_END)
        assert (
            panel["credits_issued"] == FOREIGN_AMOUNT
        ), "the USD credit note, and only it"
        assert panel["currency"] == HOME_CURRENCY

        _a_credit_note(
            brazos, currency=FOREIGN_CURRENCY, key="def081-cad-cn", on=date(2026, 7, 20)
        )

        with pytest.raises(reporting.MixedCurrencyBook) as refusal:
            reporting.adjustments_panel(start=JULY_START, end=JULY_END)
        assert refusal.value.codes == (FOREIGN_CURRENCY, HOME_CURRENCY)


# ═══════════════════════════════════════════════════════════════════════════
# WHAT MUST KEEP WORKING — the scope of the guard is the lines being SUMMED
# ═══════════════════════════════════════════════════════════════════════════
def test_def_081__a_clean_customers_statement_survives_a_mixed_tenant(brazos, dana):
    """ACC-1042 never held a CAD entry, so its statement is lawful and answers.

    The guard is over exactly the lines each figure adds — never over the
    tenant's whole book. The opposite choice would have been easier to write and
    would punish every customer of a utility for one bad entry on another
    customer's account, which is how a correctness guard turns into an outage.
    """
    with tenant_ctx(brazos):
        accounts = a_mixed_book(brazos, dana)

        statement = reporting.account_ledger(
            accounts["ACC-1042"].id, start=JULY_START, end=JULY_END
        )
        assert statement["currency"] == HOME_CURRENCY
        assert statement["totals"]["closing_balance"] == Decimal(
            "0.00"
        ), "US-LED-009 §7: 45.00 + 247.87 = 292.87; 292.87 − 292.87 = 0.00"

        # …and the customer who DID take the CAD bill is refused, same tenant.
        with pytest.raises(reporting.MixedCurrencyBook):
            reporting.account_ledger(
                accounts["ACC-1055"].id, start=JULY_START, end=JULY_END
            )


def test_def_081__a_clean_window_survives_a_mixed_book(brazos, dana):
    """June is all-USD and still answers; May is empty and answers `None`.

    Two things the guard must not do, on a tenant whose book IS mixed:

      * **refuse a clean PERIOD.** June holds one entry — LE-1's 45.00 cutover
        opening balance, dated 30 June — and it is USD, so June's trial balance
        is a lawful report and is served, labelled USD. A guard scoped to the
        tenant rather than to the window would have taken a finance officer's
        prior-period comparatives away over a July entry.
      * **refuse an EMPTY one.** "Empty" is not "mixed": May posted nothing, has
        no total to get wrong, and answers 0.00 = 0.00 with `currency=None`
        rather than guessing a code. Asserted because treating an empty
        distinct-set as a failure would refuse every report a new tenant ever
        ran, on day one, with no way to tell why.
    """
    with tenant_ctx(brazos):
        a_mixed_book(brazos, dana)

        june = reporting.trial_balance(start=date(2026, 6, 1), end=date(2026, 6, 30))
        assert june["currency"] == HOME_CURRENCY
        assert june["balanced"] is True

        may = reporting.trial_balance(start=date(2026, 5, 1), end=date(2026, 5, 31))
        assert may["currency"] is None
        assert may["total_debit"] == Decimal("0")
        assert may["balanced"] is True


def test_def_081__the_journal_list_stays_open_so_the_book_can_be_fixed(brazos, dana):
    """The S56 list is the DIAGNOSTIC surface and never refuses. By design.

    Every other read in the module is a Σ ACROSS entries. A row here is ONE
    entry — its debit and credit are that entry's own lines in that entry's own
    currency — so nothing on this page can be summed wrongly, and it is the only
    place a finance officer whose trial balance just refused can see WHICH
    entries carry `CAD` and reverse them (hard rule 4: the correction is new
    rows). A guard that darkened every ledger screen at once would leave no way
    to diagnose the state it was complaining about.
    """
    with tenant_ctx(brazos):
        a_mixed_book(brazos, dana)

        listing = reporting.journal_entry_list(start=JULY_START, end=JULY_END)
        assert listing["currencies"] == (FOREIGN_CURRENCY, HOME_CURRENCY)

        foreign = [row for row in listing["rows"] if row.currency == FOREIGN_CURRENCY]
        assert (
            len(foreign) == 1
        ), "exactly one entry carries the foreign code, and it is findable"
        assert foreign[0].debit == FOREIGN_AMOUNT
        assert foreign[0].credit == FOREIGN_AMOUNT
        assert (
            foreign[0].balanced is True
        ), "it is a perfectly valid CAD entry — that is the point"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@e3b0c44 (sources, in order: 12-governance/10-defect-log.csv DEF-081 + DEF-075 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-1 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-007 · CLAUDE.md hard rule 2)
# generated: 2026-08-15 by the money-correctness lane (DEF-081 / DEF-085 / DEF-094)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint needs no change, the refusal is a catalog exception) E=deferred(no-frontend-half — S36/S41/S56/S59 have no screens in this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on live PostgreSQL — with the guard removed,
#         test_def_081__the_trial_balance_refuses_instead_of_footing_to_698_69
#         fails `DID NOT RAISE <class 'apps.ledger.reporting.MixedCurrencyBook'>`
#         and the same book's trial_balance answers total_debit
#         Decimal('698.690000') == total_credit Decimal('698.690000'), balanced
#         True — the summed number, quoted in the human-review row
# exceptions: the foreign entry is posted through the REAL posting service
#         rather than inserted, because the defect's first half is that the
#         posting service PERMITS it (currency is a required per-entry input
#         with no cross-entry check) — a test that reached around it would prove
#         the guard against a state the product cannot reach · the mixed book is
#         built on ACC-1055 so ACC-1042's statement stays lawful and the
#         per-account scope of the guard is provable rather than asserted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
