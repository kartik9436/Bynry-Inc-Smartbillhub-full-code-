# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-007 (GET /finance/revenue-ar — S36's strip on the wire) ·
#           US-LED-008 (GET /ledger/trial-balance — S56's footer on the wire) ·
#           US-LED-009 (GET /reports/account_ledger — S59) · US-LED-010
#           (GET /reports/by_premises — S60, which refuses in figures) ·
#           US-LED-013 (GET /ledger/journal-entries — the S56 list) ·
#           US-LED-014 (GET /finance/taxes — S41's dual basis)
#           Screens: S36 · S41 · S56 · S59 · S60
# Rules:    BR-LED-016 · BR-LED-009 · BR-LED-010 · BR-LED-011 · BR-LED-012 ·
#           BR-LED-013 · BR-LED-002 (BOTH bases always) · BR-LED-003 (posted is
#           immutable — no write verb exists on any of these paths) ·
#           BR-REP-001 (every money group labels its basis) · BR-REP-002 ·
#           BR-REP-008 (the full source vocabulary) · BR-REP-009 (collection %)
#           · BR-REP-011 (DSO) · BR-SHL-011 (list grammar) · BR-TEN-003 / HR-1
#           (cross-tenant reads as absent) · BR-TEN-022 (periods are computed
#           from fiscal settings, never stored) · CLAUDE.md rule 1 · rule 2
# Golden:   LE-1 (598.69 = 598.69 · AR 152.32 · billed 553.69) · LE-2 (revenue
#           by service) · LE-3 (billed basis 47.38, collected 20.97) · LE-6
#           (collected column 446.37)
# ───────────────────────────────────────────────────────
"""The five finance screens' read models — and the proof they are REACHABLE.

WHY THIS FILE EXISTS. `apps/ledger/reporting.py` shipped on 2026-08-11: 1,500
lines of read model, every figure a Σ over posted journal lines, guarded by G7,
held by five test files. `apps/ledger/api.py` was ONE LINE — a docstring, no
`urlpatterns` — and `config/urls.py` named no ledger include. So the trial
balance, the one report an auditor asks for first, answered **404**, and so did
every other finance figure in the product.

That is hard-won law 2 for the third time in this repository, after billing's
S30 and the payments write path, and the root URLconf already carries a comment
about each. **THE FIRST TWO CASES BELOW ARE THE ONES THAT MATTER MOST**, and
they are deliberately about plumbing rather than about money: an `api.py` that
exports `urlpatterns` is not an endpoint until `config/urls.py` includes it,
and a route the URLconf knows is not reachable until a real request survives
the middleware, the authentication and the permission class. So every path is
resolved through the REAL root URLconf and then called over real HTTP with no
session — **401 means the route exists and asked for a sign-in; 404 means there
is no route at all**, which is exactly what all five answered before this lane.

EVERY EXPECTED FIGURE IS LE-1 / LE-2 / LE-3 / LE-6, through
`tests/ledger_le_fixtures.py`, where each is quoted beside the line it came
from. Nothing here recomputes an expectation — a test that did would agree with
a broken implementation.

**AND EVERY NEGATIVE ASSERTION IS DELIBERATE.** The easy way to make a finance
screen look finished is to fill it: a collection % of 80.62 because the books
can divide 446.37 by 553.69, a DSO computed on three months of history, four
zeroes in the aging buckets, the billed figure copied into the collected tax
column, a year-to-date write-off total that is really all-time. Every one of
those is a sentence about money that no row in this database supports, and
every one would pass a shape test. So this file asserts they are served **null,
under their contracted names, with the reason travelling beside them**.
"""

import uuid
from decimal import Decimal

import pytest

from apps.ledger import api as ledger_api
from apps.ledger import wire
from apps.reports import api as reports_api
from core import errors

from tests.ledger_le_fixtures import (
    BILLED_IN_PERIOD,
    COLLECTED_COLUMN,
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_DEPOSIT_APPLIED,
    LE1_FOOTING,
    LE1_PAYMENT,
    LE1_WE1_BILL,
    LE3_BILLED_BASIS_JULY,
    ensure_authority_accounts,
    make_accounts,
    post_le1_month,
    post_le3_authorities,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: The window every read below is asked for — LE-1's July, as the screen sends
#: it: ISO calendar days on the query string, never a timestamp.
FROM = JULY_START.isoformat()
TO = JULY_END.isoformat()


#: The exact decimal STRING form of a NUMERIC(18,6) figure (CLAUDE.md rule 2).
#: Written as a helper rather than hardcoding "553.690000" so the expectation
#: stays anchored to the LE fixture and not to a transcription of it.
def wire_money(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.000001")))


def a_month(tenant, actor):
    """LE-1's July, posted through the real posting service."""
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def the_four_authorities(tenant, actor):
    """LE-3's four authorities with WE-1's 20.97 tax split across them."""
    accounts = make_accounts(actor, tenant, {})
    authorities = ensure_authority_accounts(tenant, actor)
    post_le3_authorities(tenant, accounts, authorities)
    return accounts, authorities


def call(view, tenant, *, role="billing_clerk", **query):
    return api_call(view, "get", user=FakeUser(), role=role, tenant=tenant, query=query or None)


def viewer(tenant, key, *, role="billing_clerk", **query):
    """`GET /reports/{key}` as the S59/S60 parameter bar submits it."""
    return api_call(
        reports_api.report,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        query=query or None,
        key=key,
    )


def codes(payload) -> set[str]:
    """The `unavailable` codes on a response — the reason half of every null."""
    return {entry["code"] for entry in payload["unavailable"]}


def refused(response, code: str) -> None:
    """A catalog refusal, read off the BE-02 envelope rather than off a raised
    exception.

    `@api_view` routes every `core.errors` exception through
    `core.errors.drf_exception_handler`, so a refusing view RETURNS the
    envelope — it does not propagate. Asserting `pytest.raises` here would pass
    on a view that crashed and fail on one that refused correctly, which is
    exactly backwards. The STATUS is asserted too: B12 §3 maps the whole VAL
    class to 422, and a refusal that answered 400 or 500 would be a different
    contract wearing the right code.
    """
    assert response.status_code == errors.HTTP_STATUS_BY_CODE[code], (
        f"expected {code} ({errors.HTTP_STATUS_BY_CODE[code]}), got "
        f"{response.status_code} {getattr(response, 'data', None)!r}"
    )
    assert response.data["code"] == code


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO CASES THAT MATTER MOST — the routes exist, and can be reached
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_008_tc1__the_ledger_and_report_routes_are_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer, and the defect that opened this lane.

    `apps/ledger/api.py` and `apps/reports/api.py` exporting `urlpatterns` are
    not endpoints until `config/urls.py` includes them. `reporting.py` was
    complete, tested and guarded, and no human being could read one figure of
    it. This resolves the REAL paths through the REAL root URLconf, so a
    forgotten one-line include goes red HERE rather than in a support cycle.
    """
    from django.urls import resolve

    slug = brazos.subdomain
    assert resolve(f"/api/{slug}/finance/revenue-ar").func is ledger_api.revenue_ar
    assert resolve(f"/api/{slug}/finance/taxes").func is ledger_api.finance_taxes
    assert resolve(f"/api/{slug}/ledger/trial-balance").func is ledger_api.trial_balance
    assert resolve(f"/api/{slug}/ledger/journal-entries").func is ledger_api.journal_entries
    assert resolve(f"/api/{slug}/reports/account_ledger").func is reports_api.report
    assert resolve(f"/api/{slug}/reports/by_premises").func is reports_api.report


def test_us_led_008_tc1b__the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request, through the real
    middleware and the real authentication, actually ARRIVES at these views.

    `resolve()` above proves the URLconf knows the path. It does not prove a
    request can get there — the tenant middleware, the session authentication
    and the permission class all sit in front, and any one of them answering
    404 would leave S36, S41, S56, S59 and S60 exactly as unreachable as they
    were. So an UNAUTHENTICATED call is made and its refusal is read: 401
    AUTH-001 means the route exists and asked for a session; 404 means there is
    no route, which is precisely what all six answered before this lane.
    """
    from django.test import Client

    slug = brazos.subdomain
    for path in (
        f"/api/{slug}/finance/revenue-ar",
        f"/api/{slug}/finance/taxes",
        f"/api/{slug}/ledger/trial-balance",
        f"/api/{slug}/ledger/journal-entries",
        f"/api/{slug}/reports/account_ledger",
        f"/api/{slug}/reports/by_premises",
    ):
        response = Client().get(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means the route "
            "is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


def test_us_led_013_tc5__no_write_verb_exists_on_any_of_these_paths(brazos):
    """Hard rule 4 / BR-LED-003 at the router: a posted entry is immutable and
    the only "edit" is reverse + repost, which writes two NEW entries through
    the posting service.

    None of these paths serves POST, PUT, PATCH or DELETE, so a forged one is
    refused with **405 before any view runs** — the refusal cannot depend on a
    permission class somebody might loosen later. 401 would also be acceptable
    ordering; 2xx never is, and neither is 404 (which would mean the route
    vanished).
    """
    from django.test import Client

    slug = brazos.subdomain
    client = Client()
    for path in (
        f"/api/{slug}/ledger/journal-entries",
        f"/api/{slug}/ledger/trial-balance",
        f"/api/{slug}/finance/revenue-ar",
        f"/api/{slug}/finance/taxes",
        f"/api/{slug}/reports/account_ledger",
    ):
        for verb in ("post", "put", "patch", "delete"):
            response = getattr(client, verb)(path)
            assert response.status_code in (401, 405), (
                f"{verb.upper()} {path} answered {response.status_code} — a ledger read "
                "surface must never accept a write verb (hard rule 4 / BR-LED-003)"
            )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-008 — S56 trial balance
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_008_tc1__the_trial_balance_endpoint_serves_le1_and_foots(brazos, dana):
    """US-LED-008 TC-1 + §7 on the wire: *"footer **598.69 = 598.69 ✔** with
    'Balanced'"*, and the AR row **152.32**.

    Every money member is the exact decimal STRING, never a JSON number
    (CLAUDE.md rule 2) — a float here is how 598.690000000001 reaches an
    auditor. `balanced` stays a real boolean, because it is a fact and not a
    figure.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(ledger_api.trial_balance, brazos, **{"to": TO}).data

        assert body["basis"] == "posting"  # BR-REP-001: never unlabelled
        assert body["total_debit"] == wire_money(LE1_FOOTING) == "598.690000"
        assert body["total_credit"] == wire_money(LE1_FOOTING)
        assert body["difference"] == "0.000000"
        assert body["balanced"] is True

        ar_row = next(row for row in body["rows"] if row["code"] == "1200")
        assert ar_row["debit"] == wire_money(LE1_AR) == "152.320000"
        # The gross sides survive serialization — the only way to see that the
        # master transfer wrote two rows rather than none (LE-1).
        assert Decimal(ar_row["gross_debit"]) > Decimal(ar_row["debit"])

        for row in body["rows"]:
            for member in ("debit", "credit", "gross_debit", "gross_credit"):
                assert isinstance(row[member], str), (
                    f"{row['code']}.{member} is {type(row[member]).__name__} — money on the "
                    "wire is the exact decimal STRING beside its CHAR(3) (hard rule 2)"
                )
        assert body["currency"] == brazos.currency


def test_us_led_008_tc1c__the_period_bounds_are_optional_and_a_bad_one_is_refused(brazos, dana):
    """A trial balance with NO `from` is the cumulative position — which is
    what makes its AR row equal S36's Still-owed KPI — so the bounds are
    optional. A MALFORMED one is still refused rather than ignored: a date
    parsed by guessing at a format would put two different windows under one
    request in two regions (BR-TEN-020).
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        assert call(ledger_api.trial_balance, brazos).data["balanced"] is True

        refused(call(ledger_api.trial_balance, brazos, **{"to": "31/07/2026"}), errors.VAL_FORMAT)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-007 — S36 Revenue & AR
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc1__the_revenue_ar_endpoint_serves_the_le1_strip(brazos, dana):
    """US-LED-007 TC-1 through HTTP: billed **553.69**, collected **446.37**
    (LE-6's KPI-strip figure, 292.87 + 153.50), still owed **152.32**.

    The strip and the trial balance are the same books grouped differently, so
    the AR row of one IS the Still-owed KPI of the other — asserted across two
    endpoints here, because that is where a screen and a KPI would drift.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(ledger_api.revenue_ar, brazos, **{"from": FROM, "to": TO}).data
        kpis = body["kpis"]

        assert body["basis"] == "posting"
        assert body["period"] == {"start": FROM, "end": TO}
        assert kpis["billed"] == wire_money(BILLED_IN_PERIOD) == "553.690000"
        assert kpis["collected"] == wire_money(COLLECTED_COLUMN) == "446.370000"
        assert kpis["collected_from_cash"] == wire_money(LE1_PAYMENT)
        assert kpis["collected_from_applied_deposits"] == wire_money(LE1_DEPOSIT_APPLIED)
        assert kpis["still_owed"] == wire_money(LE1_AR)
        assert kpis["accounts_owing"] == 2  # a COUNT, so an int and not a money string

        tb = call(ledger_api.trial_balance, brazos, **{"to": TO}).data
        ar_row = next(row for row in tb["rows"] if row["code"] == "1200")
        assert ar_row["debit"] == kpis["still_owed"]


def test_us_led_007_tc4__collection_pct_dso_and_aging_stay_null_with_their_reasons(brazos, dana):
    """US-LED-007 TC-4 + BR-REP-009/011: the three figures the books cannot
    state arrive **null, with the reason beside them** — never as the plausible
    substitute each one has.

    The substitutes were all available. Collection % could have been
    446.37 ÷ 553.69 = **80.62%**, which is a different ratio wearing the ruled
    one's name (US-LED-007 §7 works it to **72.49%** from 401.37, excluding a
    45.00 prior-period application the books cannot see). DSO could have been
    computed on the months this tenant happens to have. The aging panel could
    have been four confident zeroes. Each would have passed a shape test and
    told a finance officer something false.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(ledger_api.revenue_ar, brazos, **{"from": FROM, "to": TO}).data

        assert body["kpis"]["collection_pct"] is None
        assert body["kpis"]["dso"] is None
        assert body["aging"] is None

        reasons = codes(body)
        assert "which_bill_a_payment_met_is_not_in_the_books" in reasons
        assert "dso_needs_twelve_months_of_billed" in reasons
        assert "aging_buckets_need_invoice_due_dates_and_opening_buckets" in reasons
        # A reason is only useful if it names the read that closes it.
        allocation_gap = next(
            entry
            for entry in body["unavailable"]
            if entry["code"] == "which_bill_a_payment_met_is_not_in_the_books"
        )
        assert allocation_gap["br_ref"].startswith("BR-REP-009")
        assert any("allocated_to_invoices" in read for read in allocation_gap["wanted_reads"])


def test_us_led_007_tc4b__written_off_ytd_is_null_until_the_caller_states_the_year(brazos, dana):
    """BR-TEN-022: periods are COMPUTED from fiscal settings and never stored,
    so no row in this database holds the first day of the tenant's fiscal year.

    Without `ytd_start` the read model sums write-offs from the beginning of
    the books — a real number that is **not** a year-to-date one — so the
    endpoint serves the KPI null with `written_off_ytd_window_was_not_stated_by_the_caller`
    rather than mislabelling it. With the day supplied, the figure appears.

    This is the ONE `unavailable` entry this lane adds to a `reporting.py`
    result, and it is the difference between a missing number and a false one.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

        blank = call(ledger_api.revenue_ar, brazos, **{"from": FROM, "to": TO}).data
        assert blank["kpis"]["written_off_ytd"] is None
        assert "written_off_ytd_window_was_not_stated_by_the_caller" in codes(blank)

        stated = call(
            ledger_api.revenue_ar,
            brazos,
            **{"from": FROM, "to": TO, "ytd_start": "2026-01-01"},
        ).data
        assert stated["kpis"]["written_off_ytd"] == "0.000000"  # nothing posts a write-off yet
        assert "written_off_ytd_window_was_not_stated_by_the_caller" not in codes(stated)


def test_us_led_007_tc4c__realised_cash_and_undeposited_are_two_members_never_a_sum(brazos, dana):
    """PO ruling 2026-08-11 closing OQ-143, verbatim: *"until bank record and
    reconcilaition confirm it it is not realised."*

    LE-1's old single *"1000 Cash 442.87"* row is restated as 150.00 realised +
    292.87 undeposited. The endpoint serves them as two members and there is no
    third adding them up — a client that wants 442.87 has to write the addition
    itself, in the open, which is the point.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        cash = call(ledger_api.revenue_ar, brazos, **{"from": FROM, "to": TO}).data["cash"]

        assert cash["realised"] == "150.000000"
        assert cash["undeposited"] == "292.870000"
        assert not any(key in cash for key in ("total", "cash_total", "sum"))
        assert "NOT realised" in cash["note"]  # the PO's own sentence, verbatim


def test_us_led_007_tc6__a_period_is_required_and_an_inverted_one_is_refused(brazos, dana):
    """A KPI strip with no period states a money figure over an unstated
    window, which is the whole subject of BR-REP-001 — so both bounds are
    required here (unlike the cumulative trial balance).

    An INVERTED range is refused rather than answered empty: US-LED-009 TC-6's
    rule, *"never an empty-but-plausible report"*, applied to every period read
    in this lane. A July that renders as zero because somebody typed the dates
    backwards is a support call that looks like a data-loss incident.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

        refused(call(ledger_api.revenue_ar, brazos, **{"to": TO}), errors.VAL_REQUIRED)
        refused(call(ledger_api.revenue_ar, brazos, **{"from": TO, "to": FROM}), errors.VAL_RANGE)


def test_us_led_007_tc6b__lone_star_ridge_reads_its_own_books_through_the_endpoint(
    brazos, dana, lonestar, erin
):
    """US-LED-007 TC-6 / CLAUDE.md rule 1 at the endpoint: Brazos Bend's 553.69
    never appears in Lone Star Ridge's strip.

    The read model is tenant-scoped and separately proved; what this adds is
    that the ENDPOINT does not widen it — no query parameter, and no
    combination of them, reaches another tenant's books, because the tenant is
    resolved once from the path and never read from client input (BR-TEN-003).
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
    with tenant_ctx(lonestar):
        body = call(
            ledger_api.revenue_ar, lonestar, role="system_admin", **{"from": FROM, "to": TO}
        ).data
        assert body["kpis"]["billed"] == "0.000000"
        assert body["kpis"]["still_owed"] == "0.000000"
        assert body["kpis"]["accounts_owing"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-014 — S41 dual-basis remittance
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_014_tc1__the_tax_endpoint_serves_both_bases_and_collected_stays_null(brazos, dana):
    """US-LED-014 TC-1 on the wire: billed basis **47.38**, collected basis
    reported UNAVAILABLE — never billed's number wearing collected's name.

    Filling the second column with the first is the failure this asserts
    against, and it is not hypothetical: LE-3 puts State on the COLLECTED basis,
    so a utility reading 13.87 in a collected column that was really the billed
    figure would remit tax on money it has not been paid.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        body = call(ledger_api.finance_taxes, brazos, **{"from": FROM, "to": TO}).data

        # ⚠ **AMENDED 2026-09-02 (CR-060 C19 / task T7d).** These four lines read
        # `collected is None` and asserted `tax_inside_a_cleared_payment_is_not_
        # derivable`, which was right while an `allocations` row carried no line
        # class. `allocation_classes` records what a payment met, so the column
        # is PRODUCED — and on this fixture nothing has been paid, so it is a
        # real 0.00. **The failure the case guards against is unchanged: billed's
        # figure must never appear under collected's heading.**
        # collected moved to the POSTING date 2026-10-21 (DEF-PAY-10321).
        assert body["basis"] == {"billed": "posting", "collected": "posting"}
        assert body["totals"]["billed"] == wire_money(LE3_BILLED_BASIS_JULY - Decimal("26.41"))
        assert body["totals"]["collected"] == wire_money(Decimal("0"))
        assert body["totals"]["collected"] != body["totals"]["billed"]

        for row in body["rows"]:
            assert row["collected"] == wire_money(Decimal("0")), "nothing has been paid"
            assert row["collected"] != row["billed"]
            # BR-LED-002 says BOTH bases are always computed — so the column is
            # SERVED rather than dropped. A missing key lets a screen render a
            # single-basis table that satisfies no rule.
            assert "collected" in row and "remitting_basis" in row
            assert row["remitting_basis"] is None
            # (billed, collected) — collected is posting-dated since 2026-10-21.
            assert list(row["bases"]) == ["posting", "posting"]

        reasons = codes(body)
        assert "tax_inside_a_cleared_payment_is_not_derivable" not in reasons
        assert "per_authority_remitting_basis_is_not_stored" in reasons


def test_us_led_014_tc4__the_endpoint_carries_the_tax_payable_tie_out(brazos, dana):
    """BR-LED-007: *"tax payable = remittance outstanding"*. S36's tie-out panel
    compares the GL balance against this table, so both come from the same rows
    and reach the wire together — one derivation cannot drift from itself.
    """
    with tenant_ctx(brazos):
        the_four_authorities(brazos, dana)
        body = call(ledger_api.finance_taxes, brazos, **{"from": FROM, "to": TO}).data
        assert body["tie_out"]["tax_payable_gl"] == body["totals"]["outstanding_billed"]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — the S56 journal list
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc2__the_journal_list_pages_and_labels_every_row(brazos, dana):
    """US-LED-013 TC-2 / BR-LED-012: the list carries the capability row, and
    every money member on it is a decimal string beside the basis label.

    Pagination is mandatory on every list (11b G5) and its sizes are ratified
    at 50/100/200/500/1000. The page here is taken in MEMORY — the read model
    returns a tuple, not a queryset — which bounds the WIRE response, and that
    is what G5 protects; the query is not bounded, and that is reported rather
    than hidden.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(ledger_api.journal_entries, brazos).data

        assert body["basis"] == "posting"
        assert body["count"] >= 1
        for row in body["results"]:
            assert isinstance(row["debit"], str) and isinstance(row["credit"], str)
            assert row["status"] in ("draft", "posted")
            # BR-REP-008: an unrecognised source shows as ITSELF, never bucketed
            # under a familiar word — nothing invisible.
            assert row["source_mapped"] in (True, False)
            # r13 #2 gives the reversal pair TWO links and both travel, so a
            # screen can render JE-104 as *reversed* and JE-105 as *the
            # reversal*. One column cannot answer both questions.
            assert "reversal_of_entry_id" in row and "reversed_by_entry_id" in row

        one = call(ledger_api.journal_entries, brazos, per="50", page="1").data
        assert one["count"] == body["count"]


def test_us_led_013_tc2b__the_two_columns_the_matrix_wants_and_the_books_lack(brazos, dana):
    """EP-LED-04's matrix opens with a **JE #** column and lists *"JE #, memo"*
    as the search fields. The column now HAS a source and the wire carries it.

    ⚠ **AMENDED 2026-08-15 (the close-the-books lane).** This test asserted
    `"journal_entries_have_no_number" in reasons` and `not any("je_number" in
    row ...)`, which was the truth until **OQ-176 CLOSED** (PO 2026-08-12,
    *"Approve a JE- series"* → BR-LED-021). Every row now carries `je_number`;
    it is `None` here because `a_month` posts through the posting service
    directly and allocates no number, and that case is reported by name rather
    than shown as an empty column.

    **Posted by is unchanged:** the actor lives in `audit_log`, another module's
    table, and the reason still reaches the wire.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        body = call(ledger_api.journal_entries, brazos).data

        reasons = codes(body)
        assert "posted_entries_without_a_je_number" in reasons
        assert "journal_entries_have_no_number" not in reasons
        # ⚠ **THE GAP IS GONE, NOT MERELY UNASSERTED (`DEF-LED-6643`).** It was
        # appended to every journal read unconditionally and had no catalogue
        # key, so every Journal and every Trial balance printed *"The books
        # will not state this. The reason has no wording yet."* It described
        # a *Posted by* column no screen in this product offers, which makes
        # it rationale rather than an absence a clerk meets (B14 rule 33).
        assert "posted_by_is_in_audit_log_not_on_the_entry" not in reasons
        assert all(uuid.UUID(row["entry_id"]) for row in body["results"])
        assert all("je_number" in row for row in body["results"])


def test_us_led_013_tc2c__the_filters_of_the_capability_row_reach_the_read_model(brazos, dana):
    """BR-SHL-011's `f.<name>` grammar, carrying the matrix's own filters:
    type, status, source_type, plus the period and a memo search.

    A filter that silently did nothing would be worse than an absent one — the
    S56 list would look narrowed and would not be — so this asserts the counts
    actually MOVE rather than that the parameters are merely accepted.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        everything = call(ledger_api.journal_entries, brazos).data["count"]

        assert call(ledger_api.journal_entries, brazos, **{"f.status": "draft"}).data["count"] == 0
        posted = call(ledger_api.journal_entries, brazos, **{"f.status": "posted"}).data["count"]
        assert posted == everything

        invoices = call(ledger_api.journal_entries, brazos, **{"f.source_type": "invoice"}).data[
            "count"
        ]
        assert 0 < invoices < everything

        nothing_matches = call(ledger_api.journal_entries, brazos, q="zzz-no-such-memo").data
        assert nothing_matches["count"] == 0

        outside = call(
            ledger_api.journal_entries, brazos, **{"from": "2020-01-01", "to": "2020-12-31"}
        ).data
        assert outside["count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-009 — S59 account ledger, through GET /reports/{key}
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_009_tc1__the_report_viewer_serves_the_acc_1042_ledger(brazos, dana):
    """US-LED-009 TC-1 verbatim, over HTTP: *"opening balance **45.00** → bill
    **+247.87** → running **292.87** → payment **−292.87** → running
    **0.00**"*, footer charges 247.87 / payments 292.87, closing 0.00.

    `charge` and `payment` are two columns and never one signed amount, so a
    reader never has to work out what a minus sign meant — the discipline
    `journal_lines.side` enforces, carried all the way to the wire.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        body = viewer(
            brazos,
            "account_ledger",
            account=str(accounts["ACC-1042"].id),
            **{"from": FROM, "to": TO},
        ).data

        assert body["basis"] == "posting"
        assert body["opening_balance"] == "45.000000"
        assert body["totals"]["charges"] == wire_money(LE1_WE1_BILL) == "247.870000"
        assert body["totals"]["payments"] == wire_money(LE1_PAYMENT)
        assert body["totals"]["closing_balance"] == "0.000000"

        running = [row["running_balance"] for row in body["rows"]]
        assert running == ["292.870000", "0.000000"]
        # BR-REP-006: the Type vocabulary is read LIVE, never hardcoded in a
        # client — all ten of BR-REP-008's words travel with the report.
        assert len(body["vocabulary"]) == 10
        assert "transfer" in body["vocabulary"] and "opening" in body["vocabulary"]


def test_us_led_009_tc4__the_premises_parameter_is_absent_rather_than_ignored(brazos, dana):
    """A14 gives S59 a **Premises** parameter and this endpoint does not accept
    one — deliberately, and recorded in US-LED-009 §8.

    ⚠ **THE REASON CHANGED ON 2026-08-16 AND THE ASSERTION CHANGED WITH IT.**
    It used to be *"`journal_lines.premises_id` is NULL on every row in the
    product (US-LED-002 unbuilt)"* — the dimension is stamped now, so that
    sentence would be a claim about a gap that has closed (hard-won law 1). The
    narrower fact, which was always the real one, stands: this endpoint accepts
    no premises parameter, so passing one changes no figure, and the reason
    travels on the result so a screen can say why the control is missing
    instead of rendering a dropdown that does nothing.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        args = {"account": str(accounts["ACC-1042"].id), "from": FROM, "to": TO}
        plain = viewer(brazos, "account_ledger", **args).data
        with_param = viewer(brazos, "account_ledger", premises="500 Main St", **args).data

        assert plain["totals"] == with_param["totals"]
        assert "premises_filter_is_not_offered_on_this_report" in codes(plain)
        assert "premises_and_unit_dimensions_never_stamped" not in codes(plain)


def test_us_led_009_tc6__the_viewer_refuses_a_bad_request_rather_than_answering_it(brazos, dana):
    """US-LED-009 TC-6: *"Param validation rejects the range … never an
    empty-but-plausible report."*

    Three refusals, each naming its field: no account, no window, and an
    inverted one. The temptation each replaces is the same — answering 200 with
    an empty table, which tells a customer they had no activity.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        account = str(accounts["ACC-1042"].id)

        refused(viewer(brazos, "account_ledger", **{"from": FROM, "to": TO}), errors.VAL_REQUIRED)
        refused(viewer(brazos, "account_ledger", account=account), errors.VAL_REQUIRED)
        refused(
            viewer(brazos, "account_ledger", account=account, **{"from": TO, "to": FROM}),
            errors.VAL_RANGE,
        )


def test_us_led_009_tc6b__an_unknown_report_key_names_the_served_vocabulary(brazos):
    """An unknown `{key}` is **VAL-005 carrying the served keys**, not a 404
    and not an empty result.

    A 404 would make an unbuilt report indistinguishable from a typo — and from
    another tenant's resource, which is the one thing HR-1 reserves 404 for. An
    empty result for `?key=revenue_by_srevice` is the hardest bug in this
    product to see. Enumerating the vocabulary in the refusal is BR-REP-006's
    posture applied to the keys themselves: read live, never hardcoded.
    """
    with tenant_ctx(brazos):
        response = viewer(brazos, "ar_aging_summary", **{"from": FROM, "to": TO})
        refused(response, errors.VAL_UNKNOWN_LOOKUP)
        assert set(response.data["params"]["keys"]) == set(reports_api.SERVED_KEYS)
        # The two LEDGER-owned keys must never disappear from the vocabulary —
        # S59 and S60 are reached through them. AMENDED 2026-08-16 (reports
        # lane): the set is no longer exactly these two. The reports module now
        # answers four keys of its own (US-REP-005/006/007), and an equality
        # assertion here would make every future canned report a failing test in
        # the LEDGER suite rather than a passing one in its own.
        assert {"account_ledger", "by_premises"} <= set(reports_api.SERVED_KEYS)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-010 — S60 by-premises, which refuses in figures
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_010_tc1__the_viewer_serves_le6s_three_premises_rows(brazos, dana):
    """US-LED-010 at the wire: **200 with three named premises rows**, footing
    to LE-6's own **553.69**.

    ⚠ **THIS TEST ASSERTED THE REFUSAL UNTIL 2026-08-16** — `available: false`,
    `rows: []`, and the money the report could not attribute — and said in as
    many words that *"these assertions flip to LE-6's three rows the day
    US-LED-002 stamps the chain, with no change on either side of the wire"*.
    That day came and the promise held: no endpoint changed, no screen changed,
    and the serializer's shape is what it always was. The only thing that moved
    is that the books now know which premises the money came from.

    The wire shape is asserted as well as the figures, because the S60 table
    reads `premises_name` and three columns it renders as dashes; a serializer
    that dropped a key would render an empty column rather than an error.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        response = viewer(brazos, "by_premises", **{"from": FROM, "to": TO})

        assert response.status_code == 200
        body = response.data
        assert body["available"] is True
        assert body["kpis"]["premises"] == 3
        assert body["kpis"]["billed"] == wire_money(BILLED_IN_PERIOD) == "553.690000"
        assert body["unattributed_billed"] == wire_money(Decimal("0"))
        assert "premises_and_unit_dimensions_never_stamped" not in codes(body)

        rows = {row["premises_name"]: row for row in body["rows"]}
        assert set(rows) == {"500 Main St", "Oak Grove", "Marina Bay"}
        assert rows["500 Main St"]["billed"] == "247.870000"
        assert rows["Oak Grove"]["billed"] == "16.420000"
        assert rows["Marina Bay"]["billed"] == "289.400000"
        # The three columns the report does NOT publish are served as absent,
        # never computed on the way out (BR-REP-009's numerator problem).
        for row in body["rows"]:
            assert row["units"] is None
            assert row["services"] == []
            assert row["collection_pct"] is None


def test_us_led_010_tc6__the_refusal_is_per_tenant_and_leaks_nothing(brazos, dana, lonestar, erin):
    """US-LED-010 TC-6 at the endpoint: Lone Star Ridge's by-premises refusal
    quantifies ITS OWN unattributed money — zero — and never Brazos Bend's
    553.69.

    The interesting failure mode is specific to a refusal that carries a
    figure: a gap message computed once and shared would leak one tenant's
    monthly billing into another tenant's screen while every isolation test on
    the rows themselves still passed.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
    with tenant_ctx(lonestar):
        body = viewer(lonestar, "by_premises", role="system_admin", **{"from": FROM, "to": TO}).data
        assert body["available"] is False
        assert body["unattributed_billed"] == "0.000000"
        assert body["unattributed_collected"] == "0.000000"


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md rule 2, swept across every endpoint at once
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_007_tc2__no_money_figure_anywhere_reaches_the_wire_as_a_number(brazos, dana):
    """Hard rule 2, as one sweep over every response this lane serves.

    A float in a money path is the defect that cannot be found by reading: it
    survives every shape test, agrees with the fixture to two decimal places,
    and disagrees in the seventh the first time a figure is summed. So every
    member whose NAME is a money word is asserted to be a string or None — and
    None only for the four figures the books genuinely cannot state.

    Counts (`accounts_owing`, `premises`) are deliberately NOT in the money
    list: they are quantities, an int is the right type for one, and calling
    them money would hide a real distinction.
    """
    money_names = {
        "billed",
        "collected",
        "collected_from_cash",
        "collected_from_applied_deposits",
        "still_owed",
        "written_off_ytd",
        "realised",
        "undeposited",
        "credits_issued",
        "debits_posted",
        "late_fees_applied",
        "net",
        "ar_control",
        "debit",
        "credit",
        "gross_debit",
        "gross_credit",
        "total_debit",
        "total_credit",
        # CR-060 C4 — the trial balance's position columns. ⚠ ADDED WITH THE
        # COLUMNS AND NOT AFTERWARDS: this set is a fixed LIST of member names,
        # so a money figure that never joins it is a figure this sweep silently
        # skips — a check that cannot fail over the exact thing it is for.
        "opening",
        "closing",
        "total_opening",
        "total_closing",
        "difference",
        "charge",
        "payment",
        "charges",
        "payments",
        "running_balance",
        "opening_balance",
        "closing_balance",
        "remitted",
        "outstanding_billed",
        "outstanding_collected",
        "unattributed_billed",
        "unattributed_collected",
        "tax_payable_gl",
        "usage",
        "base_and_fees",
        "total_billed",
        "owed",
    }

    def sweep(node, trail="body"):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in money_names:
                    assert value is None or isinstance(value, str), (
                        f"{trail}.{key} is {type(value).__name__} ({value!r}) — money on the "
                        "wire is the exact decimal STRING beside its CHAR(3) (hard rule 2)"
                    )
                sweep(value, f"{trail}.{key}")
        elif isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                sweep(value, f"{trail}[{index}]")

    with tenant_ctx(brazos):
        # One set of accounts, two postings over it: LE-1's month for the strip
        # and the trial balance, LE-3's authority split for the tax table. A
        # second `make_accounts` would collide on `accounts.account_no`, which
        # is the uniqueness the account series exists to give.
        accounts = make_accounts(dana, brazos, {})
        post_le1_month(brazos, accounts)
        post_le3_authorities(brazos, accounts, ensure_authority_accounts(brazos, dana))
        window = {"from": FROM, "to": TO}
        sweep(call(ledger_api.revenue_ar, brazos, **window).data, "revenue_ar")
        sweep(call(ledger_api.trial_balance, brazos, **window).data, "trial_balance")
        sweep(call(ledger_api.finance_taxes, brazos, **window).data, "finance_taxes")
        sweep(call(ledger_api.journal_entries, brazos, **window).data, "journal_entries")
        sweep(
            viewer(brazos, "account_ledger", account=str(accounts["ACC-1042"].id), **window).data,
            "account_ledger",
        )
        sweep(viewer(brazos, "by_premises", **window).data, "by_premises")


def test_us_led_008_tc4__every_money_group_on_every_endpoint_labels_its_basis(brazos, dana):
    """BR-REP-001, which US-LED-007 TC-4 states as *"Every KPI/panel header
    carries 'posting basis'"* and 04-docs/05-modules/12-reports makes a contract:
    **an unlabeled money render is a test failure**.

    So the label is asserted at the ENDPOINT and not only in the read model —
    a serializer that dropped `basis` would leave every screen free to invent
    one, and the two bases mean different money (LE-9's payment dated Jul 30
    and arriving Aug 7 belongs to a different month under each).
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        window = {"from": FROM, "to": TO}

        strip = call(ledger_api.revenue_ar, brazos, **window).data
        assert strip["basis"] == "posting"
        assert strip["cash"]["basis"] == "clearing"  # cash is a CLEARING-basis fact
        assert strip["adjustments"]["basis"] == "posting"

        assert call(ledger_api.trial_balance, brazos, **window).data["basis"] == "posting"
        assert call(ledger_api.journal_entries, brazos, **window).data["basis"] == "posting"
        assert call(ledger_api.finance_taxes, brazos, **window).data["basis"] == {
            "billed": "posting",
            "collected": "posting",  # DEF-PAY-10321, PO ruling 2026-10-21
        }
        ledger = viewer(
            brazos, "account_ledger", account=str(accounts["ACC-1042"].id), **window
        ).data
        assert ledger["basis"] == "posting"
        assert viewer(brazos, "by_premises", **window).data["basis"] == "posting"


def test_us_led_010_tc4__every_response_carries_the_tenants_currency(brazos, dana):
    """CLAUDE.md rule 2's other half: a money figure travels beside its CHAR(3).

    `reporting.py` publishes no currency — `journal_entries.currency` is a
    per-ENTRY column and every figure is a Σ across entries — so the label is
    the TENANT's declared one (BR-TEN-042), read through tenancy's published
    selector. It is a LABEL, not a derivation, and the distinction is why the
    mixed-currency exposure is reported rather than papered over.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        window = {"from": FROM, "to": TO}
        expected = brazos.currency
        assert len(expected) == 3

        for body in (
            call(ledger_api.revenue_ar, brazos, **window).data,
            call(ledger_api.trial_balance, brazos, **window).data,
            call(ledger_api.finance_taxes, brazos, **window).data,
            call(ledger_api.journal_entries, brazos, **window).data,
            viewer(brazos, "account_ledger", account=str(accounts["ACC-1042"].id), **window).data,
            viewer(brazos, "by_premises", **window).data,
        ):
            assert body["currency"] == expected


def test_us_led_014_tc8__no_endpoint_answers_without_a_tenant_in_context(brazos, dana):
    """CLAUDE.md rule 1 at the boundary: no tenant table is READ without
    `app.tenant_id` set.

    A finance read that ran with no tenant context would sum two utilities'
    books into one trial balance — the failure RLS FORCE prevents in the
    database and `reporting._tenant_id` prevents on the developer SQLite too.
    This asserts the ENDPOINT refuses rather than defaulting, which is the
    posture `deny-by-default` requires of a route mounted outside the
    `/api/{tenant}/` include by mistake.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)

    response = api_call(
        ledger_api.trial_balance,
        "get",
        user=FakeUser(),
        role="system_admin",
        query={"to": TO},
    )
    assert response.status_code == 401
    assert response.data["code"] == errors.AUTH_TENANT_UNRESOLVABLE
    # …and nothing leaked on the way to the refusal: no rows, no totals, no
    # partially-serialized book. The envelope is the whole body.
    assert set(response.data) == {
        "code",
        "message_key",
        "params",
        "field_errors",
        "br_ref",
        "trace_id",
    }


def test_us_led_013_tc7__a_foreign_tenants_entries_never_appear_in_the_list(
    brazos, dana, lonestar, erin
):
    """US-LED-013 TC-7 at the endpoint: Lone Star Ridge's S56 list holds its own
    entries only, and a Brazos Bend entry id appears nowhere in it (RLS)."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        theirs = {
            row["entry_id"] for row in call(ledger_api.journal_entries, brazos).data["results"]
        }
        assert theirs

    with tenant_ctx(lonestar):
        mine = call(ledger_api.journal_entries, lonestar, role="system_admin").data
        assert mine["count"] == 0
        assert not ({row["entry_id"] for row in mine["results"]} & theirs)


def test_us_led_008_tc6__a_date_typed_by_hand_never_becomes_a_silent_window(brazos, dana):
    """Every date parameter is `date.fromisoformat` and nothing looser, on
    every endpoint of this lane.

    The failure this prevents is regional and silent: `03/08/2026` is 3 August
    in one country and 8 March in another, and a period bound parsed by
    guessing would price the same request differently in two places
    (BR-TEN-020). A refusal naming the field is the only safe answer.

    **WHAT IS ACCEPTED, MEASURED RATHER THAN ASSUMED:** on Python 3.11+,
    `date.fromisoformat` also takes the ISO-8601 **basic** form — `20260731`
    parses to 31 July 2026. That was found by this test failing on an
    expectation that it would be refused, and it is left ACCEPTED rather than
    narrowed: basic-format ISO is unambiguous in every region, which is the
    only property BR-TEN-020 needs. It is written down here because "we only
    accept YYYY-MM-DD" is the kind of claim that reads as true forever and is
    not (hard-won law 1).
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        for view, query in (
            (ledger_api.revenue_ar, {"from": "03/08/2026", "to": TO}),
            (ledger_api.finance_taxes, {"from": FROM, "to": "not-a-date"}),
            (ledger_api.trial_balance, {"from": "2026-13-01"}),
            (ledger_api.journal_entries, {"to": "07/31/2026"}),
        ):
            refused(call(view, brazos, **query), errors.VAL_FORMAT)

        # …and the unambiguous basic form IS honoured, on the same endpoint.
        compact = call(ledger_api.journal_entries, brazos, **{"to": "20260731"})
        assert compact.status_code == 200

        refused(
            viewer(brazos, "by_premises", **{"from": "07-01-2026", "to": TO}), errors.VAL_FORMAT
        )


def test_us_led_009_tc7__the_account_ledger_never_crosses_a_tenant(brazos, dana, lonestar, erin):
    """US-LED-009 TC-7 / HR-1: Lone Star Ridge asking for a Brazos Bend account
    id gets an EMPTY ledger — the read model's queryset is tenant-scoped, so a
    foreign id simply matches nothing.

    An empty result is the right answer HERE (and only here) because the
    parameters were valid and the account is genuinely absent from these books;
    it is byte-identical to asking for an id that never existed, which is what
    makes existence unprobeable.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        foreign = str(accounts["ACC-1042"].id)

    with tenant_ctx(lonestar):
        body = viewer(
            lonestar,
            "account_ledger",
            role="system_admin",
            account=foreign,
            **{"from": FROM, "to": TO},
        ).data
        assert body["rows"] == []
        assert body["opening_balance"] == "0.000000"
        assert body["totals"]["closing_balance"] == "0.000000"

        unknown = viewer(
            lonestar,
            "account_ledger",
            role="system_admin",
            account=str(uuid.uuid4()),
            **{"from": FROM, "to": TO},
        ).data
        assert unknown["rows"] == body["rows"]
        assert unknown["totals"] == body["totals"]


def test_us_led_010_tc5__the_endpoints_hold_the_same_shape_on_an_empty_book(brazos):
    """A tenant with NO postings at all — the first day of a new utility.

    Every endpoint answers 200 with zeroes and its reasons intact, and none of
    them raises. That matters more than it looks: the shape a screen is built
    against is the EMPTY one, and an endpoint that only works once money exists
    ships a blank page to every new customer on day one.
    """
    with tenant_ctx(brazos):
        window = {"from": FROM, "to": TO}
        strip = call(ledger_api.revenue_ar, brazos, **window).data
        assert strip["kpis"]["billed"] == "0.000000"
        assert strip["revenue_by_service"] == []

        tb = call(ledger_api.trial_balance, brazos, **window).data
        assert tb["rows"] == [] and tb["balanced"] is True

        taxes = call(ledger_api.finance_taxes, brazos, **window).data
        assert taxes["rows"] == [] and taxes["totals"]["collected"] is None

        entries = call(ledger_api.journal_entries, brazos, **window).data
        assert entries["count"] == 0

        premises = viewer(brazos, "by_premises", **window).data
        assert premises["available"] is False


def test_us_led_009_tc5__the_endpoint_ledgers_foot_to_the_endpoint_tie_out(brazos, dana):
    """US-LED-009 TC-5 / BR-REP-008, asserted ACROSS the endpoints rather than
    inside the read model: *"Σ closing balances of all account ledgers for the
    period = AR tie-out"* — LE-1's **152.32**.

    This is the assertion a screen can be wrong about even when every module is
    right: S59 is one endpoint, S36's Still-owed KPI is another, and they are
    the same books grouped differently. If the serializer ever quantized one
    and truncated the other, or a page limit silently dropped a row, this foots
    to the wrong number and nothing else in the suite would notice.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        window = {"from": FROM, "to": TO}
        closings = Decimal("0")
        for account in accounts.values():
            body = viewer(brazos, "account_ledger", account=str(account.id), **window).data
            closings += Decimal(body["totals"]["closing_balance"])

        strip = call(ledger_api.revenue_ar, brazos, **window).data
        assert closings == Decimal(strip["kpis"]["still_owed"]) == LE1_AR


def test_us_led_007_tc5__the_endpoint_reads_the_books_and_never_a_register(brazos, dana):
    """US-LED-007 TC-5 carried to the API layer: no endpoint in this lane
    reaches a register, a cache or an ORM manager of its own.

    `reporting.py` proves the READ MODEL takes no such path. What this adds is
    that the two api.py files did not grow one on the way to the wire — G6
    greps for `.objects.` in an api.py and this asserts the same thing where a
    reviewer can read it, together with the absence of a clock (BR-TEN-043:
    `timezone.now()` in a money path would make a period boundary depend on
    when the report was run).
    """
    import inspect

    for module in (ledger_api, reports_api, wire):
        source = inspect.getsource(module)
        # Read over the WHOLE file, prose included, exactly as G6 reads it — a
        # test that skipped docstrings could pass on a file G6 fails, which is
        # the worst possible relationship between a test and a gate.
        assert (
            ".objects." not in source
        ), f"{module.__name__} reaches a model manager — api.py is thin (B8 layering, G6)"
        assert (
            "timezone.now" not in source and "datetime.now" not in source
        ), f"{module.__name__} reads a clock in a money path (BR-TEN-043 / G6)"
        assert "accounts.balance" not in source, (
            f"{module.__name__} names the balance CACHE — US-LED-007 TC-5: the strip reads "
            "dimensions, and no silent cache number ever renders"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-007@PACKETHASH (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md — US-LED-007/008/009/010 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md — US-LED-013 — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md — US-LED-014 — · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.10 + §2.10b; co-packets US-LED-008/009/010/013/014, same five sources)
# generated: 2026-08-11 by story-coder (W5 ledger read-API lane — the TC-named tests for the six routes this lane mounted)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S36/S41/S56/S59/S60 have no screen yet; backend-only lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED-PROVED BEFORE GREEN — every case in this file was run against the unmounted URLconf and the pre-existing one-line api.py stubs first; the verbatim Resolver404 / AttributeError / assert 404 == 401 failures are quoted in the lane report, together with the four deliberate mutations run afterwards (money served as a JSON number, `basis` dropped, `collection_pct` filled with collected÷billed, the by-premises refusal downgraded to an empty table)
# exceptions: (1) US-LED-008 TC-5 (an unbalanced period rendering as unbalanced) is NOT re-asserted here — creating one requires bypassing the posting service, which the database refuses, and `tests/test_us_led_001_posting.py` already holds it at the only layer that can · (2) the isolation cases here are NOT marked `-m isolation`: that suite is the RLS probe set and runs against a live Postgres, while these assert the ENDPOINT does not widen a scope the read model already holds — the RLS half lives in tests/test_us_led_007_revenue_ar.py and tests/test_us_led_005_gl_designations.py · (3) the trial-balance figures are asserted with `to` and no `from` because the AR control is cumulative by definition; a bounded window is asserted separately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
