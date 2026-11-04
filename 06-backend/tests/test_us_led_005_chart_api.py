# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (the chart of accounts, over HTTP — TC-2 a typed row,
#           TC-3 the rename, TC-4 deactivate-first, TC-5 the referenced row
#           that never deletes) · US-LED-006 (the export codes on the mapping
#           page) · US-LED-017 (TC-5 — no surface presents an unsigned code as
#           finance-signed)
#           Screens: S56 · S73
# Rules:    BR-LED-014 · BR-LED-015 · BR-LED-037 · BR-LED-038 · BR-BIL-010 ·
#           BR-BIL-069 · BR-TEN-003 / HR-1 (cross-tenant reads as absent) ·
#           CLAUDE.md rule 1 · rule 4 · rule 7
# ───────────────────────────────────────────────────────
"""The chart of accounts is REACHABLE, and the four things it refuses.

WHY THIS FILE EXISTS. The chart is tenant-customizable by design — US-LED-005
§1 says *"add accounts, edit names"* — and until 2026-08-16 no human could add,
rename, re-point or retire one line of it: `apps/ledger/services.py`'s own
docstring said *"WHAT IS NOT: the S56 chart CRUD"*, and `apps/ledger/api.py`
listed `GET /ledger/accounts` and both gl-mapping routes under NOT SERVED.

**THE FIRST TWO CASES ARE ABOUT PLUMBING AND THEY ARE THE ONES THAT MATTER**
(the precedent is `tests/test_us_led_ledger_api.py`): an `api.py` exporting
`urlpatterns` is not an endpoint until `config/urls.py` includes it, and a route
the URLconf knows is not reachable until a real request survives the middleware,
the authentication and the permission class. 401 means the route exists and
asked for a sign-in; **404 means there is no route at all**, which is what every
path below answered before this lane.
"""

import uuid
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace

import pytest

from apps.ledger import chart, chart_api, models, selectors
from core import errors

from tests.ledger_le_fixtures import make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=dt_timezone.utc)


def signed_in(role):
    """A user the WHOLE stack can read a role off — both halves, deliberately.

    `apps/identity/auth.py` attaches BOTH `request.tenant_role` (which BE-04's
    permission classes read) and `user.role` (which the service layer's
    `@require_role` reads). A test user carrying only one of them would pass the
    endpoint gate and be refused by the service, or the reverse — and the two
    gates exist precisely so that neither is the only one.
    """
    return SimpleNamespace(id=uuid.uuid4(), pk=uuid.uuid4(), role=role, is_authenticated=True)


def call(view, tenant, method="get", *, role="system_admin", data=None, query=None, **kwargs):
    return api_call(
        view,
        method,
        user=signed_in(role),
        role=role,
        tenant=tenant,
        data=data,
        query=query,
        **kwargs,
    )


def refused(response, code: str) -> None:
    """A catalog refusal read off the BE-02 envelope, status included.

    `@api_view` routes every `core.errors` exception through the DRF handler, so
    a refusing view RETURNS the envelope rather than raising. Asserting
    `pytest.raises` would pass on a view that crashed and fail on one that
    refused correctly, which is exactly backwards.
    """
    assert response.status_code == errors.HTTP_STATUS_BY_CODE[code], (
        f"expected {code} ({errors.HTTP_STATUS_BY_CODE[code]}), got "
        f"{response.status_code} {getattr(response, 'data', None)!r}"
    )
    assert response.data["code"] == code


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO CASES THAT MATTER MOST — the routes exist, and can be reached
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_005_tc0__the_chart_routes_are_actually_mounted(brazos):
    """Hard-won law 2 at the routing layer. Resolved through the REAL URLconf."""
    from django.urls import resolve

    slug = brazos.subdomain
    account_id = uuid.uuid4()
    assert resolve(f"/api/{slug}/ledger/accounts").func is chart_api.accounts
    assert resolve(f"/api/{slug}/ledger/gl-mappings").func is chart_api.gl_mappings
    assert resolve(f"/api/{slug}/ledger/accounts/{account_id}").func is chart_api.account_item
    assert (
        resolve(f"/api/{slug}/ledger/accounts/{account_id}/deactivate").func
        is chart_api.account_deactivate
    )
    assert (
        resolve(f"/api/{slug}/ledger/accounts/{account_id}/reactivate").func
        is chart_api.account_reactivate
    )


def test_us_led_005_tc0b__the_routes_are_reachable_through_the_whole_stack(brazos):
    """A real HTTP request ARRIVES: 401 = the route exists; 404 = it does not."""
    from django.test import Client

    slug = brazos.subdomain
    for path in (f"/api/{slug}/ledger/accounts", f"/api/{slug}/ledger/gl-mappings"):
        response = Client().get(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means the chart is "
            "still unreachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


def test_us_led_005_tc1__the_seeded_chart_is_served_in_code_order(brazos):
    """TC-1's seeded chart, read by a human for the first time.

    The AR and opening-clearing designations (r9 #3) are asserted BY NAME rather
    than by number: `chart.py`'s whole subject is that code reads the
    designation and never the code, and a test that asserted "1200" would be
    the first place that property rotted.
    """
    response = call(chart_api.accounts, brazos)
    assert response.status_code == 200
    rows = response.data["rows"]
    assert rows, "a provisioned tenant has a seeded chart"
    assert [row["code"] for row in rows] == sorted(row["code"] for row in rows)
    designations = {row["designation"] for row in rows if row["designation"]}
    assert chart.AR in designations
    assert chart.OPENING_CLEARING in designations
    # BR-REP-006 — the pickers enumerate the LIVE vocabulary, served rather
    # than retyped by the screen.
    assert set(response.data["types"]) == set(models.LEDGER_ACCOUNT_TYPES)
    assert set(response.data["designations"]) == set(chart.GL_DESIGNATIONS)


def test_def_led_6715__the_SEARCH_narrows_the_chart_and_the_ROLE_filter_is_served(brazos):
    """The two filters the one-table Chart tab depends on, asserted separately.

    ⚠ **THE SEARCH HALF EXISTS BECAUSE IT WAS DELETED BY ACCIDENT AND NOTHING
    WENT RED.** On 2026-09-25 the lane adding the Role filter replaced a text
    anchor that happened to contain `chart_of_accounts`'s four search lines and
    did not put them back. `tsc`, 214 front-end cases and every ledger test
    passed, **because no case in this repository had ever asked this endpoint
    to find a row by name** — so the search box went on returning the whole
    chart, which is indistinguishable from a chart with nothing excluded. It
    was found by typing *cash* into the running product and counting the rows
    (hard-won law 6), and by nothing else.

    **What would make this pass wrongly:** asserting only that the filtered
    list is non-empty, or only that it is shorter. So it asserts the SET — every
    row returned matches, and a row that matches is not missing — which cannot
    be satisfied by a filter that does nothing.
    """
    everything = call(chart_api.accounts, brazos).data["rows"]
    assert len(everything) > 5, "this case needs a seeded chart to narrow"

    hit = call(chart_api.accounts, brazos, query={"q": "cash"}).data["rows"]
    assert hit, "the seeded chart has at least one account named for cash"
    assert len(hit) < len(everything), "a search that narrows nothing is not a search"
    for row in hit:
        assert "cash" in f"{row['code']} {row['name']}".lower()
    # …and nothing that matches was dropped, which is the half a "shorter list"
    # assertion cannot see.
    expected = {
        row["account_id"]
        for row in everything
        if "cash" in f"{row['code']} {row['name']}".lower()
    }
    assert {row["account_id"] for row in hit} == expected

    # BR-BIL-069 / Finance blueprint p025 note 3 — the ROLE filter, which the
    # blueprint marks NOT SERVED and calls "the gap": *"Designation is how 4·1
    # finds the tax accounts."* It is what replaced the deleted Tax authorities
    # panel, so it is the filter that panel's job now rests on.
    by_role = call(
        chart_api.accounts, brazos, query={"f.designation": chart.AR}
    ).data["rows"]
    assert by_role, "the seeded chart carries the receivable role"
    assert {row["designation"] for row in by_role} == {chart.AR}

    # `none` is a REAL value, not an absent one: a tenant's own additions carry
    # no role and a filter that could not name them would leave them unfindable.
    roleless = call(
        chart_api.accounts, brazos, query={"f.designation": "none"}
    ).data["rows"]
    assert all(row["designation"] is None for row in roleless)


def test_def_led_6715__a_role_with_no_live_account_is_SERVED_as_a_warning(brazos):
    """The one thing the deleted roles panel knew that a column cannot carry.

    An unfilled role has NO ACCOUNT ROW — so the screen cannot work this out
    from the rows it was sent. It is served, counted beside the Role filter and
    listed as that filter's last value.

    ⚠ **THIS DOCSTRING CLAIMED A REFUSAL THE ENGINE DOES NOT MAKE, UNTIL
    2026-09-25.** It read *"a posting that needs an unfilled role refuses BY
    NAME (`BR-LED-796`)"*. Measured in `apps/ledger/selectors.py`, and pinned
    by two cases already in this repository:
    `gl_account_for_designation` returns **`None`** for a role with no live
    account (`test_us_led_005_chart_api.py` asserts exactly that, a few cases
    down) and **raises** only for a designation NAME it does not recognise
    (`test_us_led_005_gl_designations.py`). So the gap is not fenced anywhere
    central; `BR-LED-796` is the worked example of one caller that must refuse
    on it. That is the reason this test exists at all — the serving IS the
    warning, so if it stops being served nothing else catches the gap.

    ⚠ **`needs-account` MUST NOT NARROW THE ROWS.** It is a question about
    roles, and a row filter's only honest answer is an empty list — which on
    screen reads as *nothing is wrong*, the exact inversion of what it means.
    """
    payload = call(chart_api.accounts, brazos).data
    served = payload["roles_needing_account"]
    # It is a SUBSET of the closed designation set and never invents a name.
    assert set(served) <= set(chart.GL_DESIGNATIONS)
    # Every name it carries genuinely resolves to no live account…
    with tenant_ctx(brazos):
        resolved = selectors.designation_map()
    for role in served:
        assert resolved[role] is None, f"{role} has an account and is not a gap"
    # …and no gap is missing from it, which is the half that matters: a list
    # that silently dropped one would under-report a month-end failure.
    gaps = {
        name
        for name, account_id in resolved.items()
        if account_id is None and name not in chart.PENDING_FINANCE_RESIGN
    }
    assert set(served) == gaps

    unchanged = call(
        chart_api.accounts, brazos, query={"f.designation": "needs-account"}
    ).data["rows"]
    assert len(unchanged) == len(payload["rows"]), (
        "needs-account asks about ROLES; narrowing rows for it would render an "
        "empty table and read as 'nothing is wrong'"
    )


def test_us_led_017_tc5__the_cost_accounts_are_served_SIGNED_and_the_flag_still_discriminates(
    brazos, monkeypatch
):
    """US-LED-017 TC-5 — *"no surface presents an unsigned code as signed"*.

    It read `test_us_led_017_tc5__the_unsigned_cost_accounts_are_served_MARKED`
    and asserted the eight 5xxx rows are PRESENT (hiding eight real accounts a
    capture can point at is its own defect) and every one of them carries
    `finance_signed: false` plus the named route the signature has to come
    through.

    ⚠ **AMENDED 2026-08-18 — THE EIGHT WERE FINANCE RE-SIGNED, so the first
    assertion INVERTS and the second has no subject left.** The Product Owner —
    the sign-off authority per their own ruling of 2026-08-11 — re-signed the
    eight cost codes and names (with 4180) in the working chat session, shown in
    plain English, with no dollar figure attached to any of them and with B4/B5
    ❄️ FROZEN and un-edited. So S56 must serve them `finance_signed: true`: a
    screen telling a finance reviewer that ratified rows still need attention is
    a defect, and it is the same defect TC-5 forbids, pointed the other way.

    ⚠ **IT WAS EXACTLY THAT DEFECT.** `apps/ledger/services._chart_row` derived
    the flag from `chart.is_cost_of_service_code(...)` — *"is this code in the
    cost section"* — which is a different question from *"did finance sign it"*.
    The two answers agreed until the re-sign and then stopped. Fixed to read the
    two pending registers, and this test is what holds it.

    **The discriminating half is kept alive on a synthetic unsigned code**, so
    the flag cannot rot into the constant `true` now that nothing real is
    unsigned. Precedent: CR-011 item 9 on `test_us_not_005`.
    """
    response = call(chart_api.accounts, brazos)
    rows = {row["code"]: row for row in response.data["rows"]}
    cost_codes = [row.code for row in chart.COST_OF_SERVICE_CHART if row.code in rows]
    assert cost_codes, "the cost section seeds with the tenant's services"
    for code in cost_codes:
        assert rows[code]["finance_signed"] is True, (
            f"{code} was finance re-signed on 2026-08-18 and S56 is telling a reviewer it "
            "still needs their attention"
        )
        # PRESENT, not hidden — the other half of TC-5, unchanged by the ruling.
        assert rows[code]["seeded"] is True
    # ⚠ **AMENDED 2026-09-01 (CR-060 C15 · task T5) — AND THE FIGURE IS PINNED,
    # NOT THE EMPTINESS, for exactly the reason the comment below this one
    # gives about `pending_finance_re_sign`.** The cost vocabulary widened to
    # sixteen categories and the fourteen new accounts seed `signed=False`,
    # awaiting a HUMAN-GUIDE §6 re-sign — B5 line 74 is ❄️ FROZEN and was not
    # edited. `== []` could only ever say *nothing is pending*: it would go red
    # for this correct change and GREEN the day somebody marked all fourteen
    # signed with no ruling behind them. Named, it fails in both directions.
    assert response.data["pending_finance_re_sign_cost"] == [
        row.code for row in chart.WIDENED_COST_CHART
    ], (
        "the fourteen CR-060 C15 cost accounts are seeded unsigned pending a finance "
        "re-sign (HUMAN-GUIDE §6). A code leaving this list is a SIGNATURE, and a signature "
        "is recorded in 12-governance/09-human-review-ledger.md — never by editing this line"
    )
    # ⚠ **AMENDED 2026-08-30 — THIS ASSERTED `== []` AND THE LIST IS `["4300"]`
    # BY DESIGN SINCE 2026-08-28.** The PO ruled the discount designation that
    # day, closing DEF-536, verbatim: *"you will need differnt GL code for these
    # - dont keep them in same, create differnt category as required and keep
    # them in it"* — and `4300 Customer discounts (contra-revenue)` was seeded
    # the way 4160/4170/4180 each were on the day THEY arrived: `signed=False`,
    # listed here, awaiting a finance re-sign through HUMAN-GUIDE §6. B4/B5 stay
    # ❄️ FROZEN and un-edited.
    #
    # **THE FIGURE IS PINNED RATHER THAN THE EMPTINESS, and that is stronger
    # than what it replaces**: `== []` could only ever say *nothing is pending*,
    # so it went red for a correct change and would have gone GREEN the day
    # somebody marked 4300 signed with no ruling behind it. This goes red on
    # both — an unsigned row appearing, and an unsigned row disappearing.
    # ⚠ **AMENDED 2026-09-02 (`DEF-3360`) — THIS PINNED `== ["4760"]` AND HAD
    # BEEN RED SINCE `CR-063` LANDED THAT MORNING.** The list held eleven codes
    # by then — `4155 Fire` and `CR-066`'s nine fee and adjustment accounts had
    # each arrived correctly, seeded `signed=False` exactly as 4760 was, and
    # neither lane could land without this guard going red. It reads as a broken
    # test rather than as an unreviewed signature, and no gate reads a red test.
    #
    # **THE FIX IS THE ONE ITS SIBLING FOUR LINES UP ALREADY HAD: ASK THE
    # QUESTION, DO NOT PIN THE ANSWER.** The served list must equal the chart's
    # own derived register, so a new unsigned row is absorbed and the guard goes
    # on asking whether the surface agrees with `chart.py`; and 4760 must still
    # be IN it, because that is the row whose signature the review ledger is
    # actually holding open. Both directions still fail: an unsigned row served
    # as signed, and 4760 quietly marked signed with no ruling behind it.
    assert response.data["pending_finance_re_sign"] == list(chart.PENDING_FINANCE_RE_SIGN), (
        "the served pending list disagrees with chart.PENDING_FINANCE_RE_SIGN, which is "
        "DERIVED from the rows' own `signed` flags — a disagreement means a surface is "
        "carrying its own copy (hard-won law 1)"
    )
    assert "4760" in response.data["pending_finance_re_sign"], (
        "4760 Customer discounts is seeded unsigned pending a finance re-sign "
        "(HUMAN-GUIDE §6). A row leaving this list is a SIGNATURE, and a "
        "signature is recorded in 12-governance/09-human-review-ledger.md — "
        "never by editing this test."
    )
    # CR-061 statement (1), 2026-09-02 — a THIRD register, for the 67 accounts
    # the PO ruled into existence for the half of a utility's books this product
    # never posts. Same posture, same route, and it is asserted here so that a
    # surface serving one of them as finance-signed is a RED.
    assert response.data["pending_finance_re_sign_books"] == list(
        chart.PENDING_FINANCE_RE_SIGN_BOOKS
    )
    assert len(response.data["pending_finance_re_sign_books"]) == 67
    # The route is still published by name, for the next row that needs it.
    assert "HUMAN-GUIDE §6" in response.data["cost_section_source"]
    assert "HUMAN-GUIDE §6" in response.data["utility_books_source"]

    # ── the flag still DISCRIMINATES, on a code unsigned only in this test ───
    monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN_COST", ("5110",))
    marked = call(chart_api.accounts, brazos)
    marked_rows = {row["code"]: row for row in marked.data["rows"]}
    assert marked_rows["5110"]["finance_signed"] is False
    assert marked_rows["5100"]["finance_signed"] is True
    assert marked.data["pending_finance_re_sign_cost"] == ["5110"]
    # And it is SERVED, never filtered out: hiding a real account and presenting
    # a proposal as law are both failures, in opposite directions.
    assert "5110" in marked_rows


def test_def_260__no_row_the_same_payload_calls_PENDING_comes_back_finance_signed(
    brazos, monkeypatch
):
    """DEF-260 — the property, over the SERVED rows, in ONE assertion.

    The defect: `services._chart_row` answered `finance_signed` from *"is this
    code in the cost section"* (`chart.is_cost_of_service_code`) and had never
    read `chart.PENDING_FINANCE_RE_SIGN`, the register that holds an unsigned
    code OUTSIDE that section. So `GET /ledger/accounts` served **4180 Budget
    billing variance** as `finance_signed: true` in the very same payload whose
    `pending_finance_re_sign` listed `["4180"]`, and no screen marked the one
    account CR-008 was waiting on a signature for.

    ⚠ **THE OLD CODE PASSES the sibling TC-5 test above**, because every code it
    exercises is inside the cost section, where membership and signature happen
    to agree. The discriminating case is a code that is unsigned and NOT a cost
    code — which is why this test monkeypatches `PENDING_FINANCE_RE_SIGN` to
    `("4180",)` rather than asserting today's empty registers, and why it is
    written as a PROPERTY over whatever the response itself calls pending:
    **the next unsigned code is covered without anybody editing this file.**

    Red proof, verbatim, against `finance_signed: not chart.
    is_cost_of_service_code(account.code)`:

        AssertionError: GET /ledger/accounts calls 4180 pending in this very
        payload and serves it finance_signed=True
    """
    monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN", ("4180",))
    response = call(chart_api.accounts, brazos)
    rows = {row["code"]: row for row in response.data["rows"]}
    pending = [
        *response.data["pending_finance_re_sign"],
        *response.data["pending_finance_re_sign_cost"],
    ]
    assert pending, "this test has no subject unless the response reports a pending code"
    for code in pending:
        assert code in rows, f"{code} is named pending and is not served at all"
        assert rows[code]["finance_signed"] is False, (
            f"GET /ledger/accounts calls {code} pending in this very payload and "
            f"serves it finance_signed={rows[code]['finance_signed']}"
        )
    # The converse half, so the flag cannot rot into the constant `false`: a
    # cost code and an ordinary seeded code both stay signed while 4180 is not.
    assert rows["5100"]["finance_signed"] is True
    assert rows["1000"]["finance_signed"] is True
    # And the unsigned row is SERVED, never filtered out (US-LED-017 TC-5).
    assert rows["4180"]["seeded"] is True


def test_us_led_005_tc2__a_typed_account_lands_and_audits(brazos, audit_rows):
    """TC-2 — a utility adds a line of its own. The audit row is rule 7."""
    response = call(
        chart_api.accounts,
        brazos,
        "post",
        data={"code": "1150", "name": "Trade debtors", "type": "asset"},
    )
    assert response.status_code == 201, response.data
    assert response.data["code"] == "1150"
    assert response.data["status"] == "active"
    # A tenant's own row is not a finance-signed chart row and is not marked as
    # one — nobody proposed it on finance's behalf.
    assert response.data["seeded"] is False

    # `audit_rows` captures from the SINK, which is how every audit assertion in
    # this suite reads: the platform sink is replaced for the duration of a test,
    # so a row asserted here is the exact row `core.audit` handed the store.
    assert [
        row
        for row in audit_rows
        if row["action"] == "ledger_account.created"
        and str(row["entity_id"]) == response.data["account_id"]
    ], "BR-LED-015: every chart change audits"


def test_us_led_005_tc2b__a_duplicate_code_is_refused_by_name(brazos):
    """`uq_ledger_accounts_code` is the guarantee; the message is the courtesy."""
    with tenant_ctx(brazos):
        existing = models.LedgerAccount.objects.filter(tenant_id=brazos.id).first()
    response = call(
        chart_api.accounts,
        brazos,
        "post",
        data={"code": existing.code, "name": "Second copy", "type": "asset"},
    )
    refused(response, errors.BIZ_STATE)


def test_us_led_005_tc2c__the_signed_2200_tax_series_may_not_be_hand_typed(brazos):
    """B5 line 74: *"tenant authorities mint their own"*, and the PO ruled the
    code GENERATED (OQ-147). A hand-typed 2200-07 would take a number the
    allocator is about to hand out."""
    response = call(
        chart_api.accounts,
        brazos,
        "post",
        data={"code": "2200-07", "name": "State of Texas", "type": "liability"},
    )
    refused(response, errors.BIZ_STATE)


def test_us_led_005_tc3__a_rename_lands_and_the_designation_still_resolves(brazos):
    """LE-1's own worked rename: `Accounts receivable` → `Trade debtors`.

    The point of the case is the SECOND assertion. Renaming the AR account must
    leave `selectors.gl_account_for_designation(AR)` landing on the same row,
    because every posting in the product resolves it by name — that is the
    property `chart.py` exists to protect and the one a rename could break.
    """
    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.get(tenant_id=brazos.id, designation=chart.AR)
    response = call(
        chart_api.account_item,
        brazos,
        "patch",
        data={"name": "Trade debtors"},
        account_id=account.pk,
    )
    assert response.status_code == 200, response.data
    assert response.data["name"] == "Trade debtors"
    with tenant_ctx(brazos):
        account.refresh_from_db()
        assert account.code == response.data["code"], "a rename never renumbers"
        assert str(selectors.gl_account_for_designation(chart.AR).pk) == str(account.pk)


def test_us_led_005_tc3b__type_is_not_editable_and_a_clerk_may_not_change_the_code(brazos):
    """US-LED-005 §1 freezes TYPE once posted against — so it is not ACCEPTED.

    ⚠ AMENDED 2026-10-29 (`CR-196-BRC10`). This case was
    `…code_and_type_are_not_editable_at_all` and sent `{"code": "9999"}`
    expecting the same refusal as `type`. The PO ruled that a System Admin may
    change the CODE even when the account is used (BR-LED-040 amended for the
    code only), so a code from a System Admin now LANDS — that half is held in
    `tests/test_cr196_chart_code_editable.py`. What stays here: `type` is still
    refused with the field named, and a CLERK's code is still refused.
    """
    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.filter(tenant_id=brazos.id).first()
    response = call(
        chart_api.account_item, brazos, "patch", data={"type": "expense"}, account_id=account.pk
    )
    refused(response, errors.VAL_FORMAT)
    response = call(
        chart_api.account_item,
        brazos,
        "patch",
        role="billing_clerk",
        data={"code": "9999"},
        account_id=account.pk,
    )
    refused(response, errors.AUTH_PERMISSION_DENIED)


def test_us_led_005_tc4__deactivate_frees_the_designation_for_its_replacement(brazos):
    """IS-1 deactivate-first, and the two-step swap it exists to allow.

    `uq_ledger_accounts_designation` is partial on `deleted_at IS NULL`, so
    retiring 1200 frees `accounts_receivable` for the 1150 the tenant just made,
    and `selectors` filters the same way — a deactivated account stops BEING the
    AR account the moment it is retired, with nothing to remember to clear.
    """
    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.get(tenant_id=brazos.id, designation=chart.AR)
    response = call(
        chart_api.account_deactivate,
        brazos,
        "post",
        data={"at": NOW.isoformat()},
        account_id=account.pk,
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == "deactivated"
    # THE HOLE IS REPORTED, NOT HIDDEN: a designation with no live account is a
    # real state and the response says which one went dark.
    assert response.data["designation_now_unresolved"] == chart.AR
    with tenant_ctx(brazos):
        assert selectors.gl_account_for_designation(chart.AR) is None

    replacement = call(
        chart_api.accounts,
        brazos,
        "post",
        data={
            "code": "1150",
            "name": "Trade debtors",
            "type": "asset",
            "designation": chart.AR,
        },
    )
    assert replacement.status_code == 201, replacement.data
    with tenant_ctx(brazos):
        assert (
            str(selectors.gl_account_for_designation(chart.AR).pk) == replacement.data["account_id"]
        )

    # ⚠ **REACTIVATION IS NOT THE MIRROR OF DEACTIVATION**, and the database
    # found that before a human did: bringing 1200 back now would put TWO live
    # accounts on `accounts_receivable`, which `uq_ledger_accounts_designation`
    # refuses with an IntegrityError and a 500. It is refused in the SERVICE
    # instead, and the refusal NAMES the account holding the designation. The
    # two silent repairs were both available and both rejected — clearing
    # 1200's pointer on the way in, or moving 1150's — because each changes
    # WHICH account the posting service calls the AR account, as a side effect
    # of a Reactivate button nobody thought was a money decision.
    blocked = call(
        chart_api.account_reactivate,
        brazos,
        "post",
        data={"at": NOW.isoformat()},
        account_id=account.pk,
    )
    refused(blocked, errors.BIZ_STATE)
    assert blocked.data["params"]["holder"] == "1150"
    with tenant_ctx(brazos):
        assert (
            str(selectors.gl_account_for_designation(chart.AR).pk) == replacement.data["account_id"]
        ), "the refusal left the live pointer exactly where it was"

    # Clearing the retired row's pointer FIRST is the deliberate two-step, and
    # then the account comes back.
    cleared = call(
        chart_api.account_item,
        brazos,
        "patch",
        data={"designation": None},
        account_id=account.pk,
    )
    assert cleared.status_code == 200, cleared.data
    back = call(
        chart_api.account_reactivate,
        brazos,
        "post",
        data={"at": NOW.isoformat()},
        account_id=account.pk,
    )
    assert back.status_code == 200, back.data
    assert back.data["status"] == "active"


def test_us_led_005_tc5__an_account_with_journal_lines_never_deletes(
    brazos, growth_plan, identity_seam
):
    """CLAUDE.md rule 4 through IS-1: a row a journal line points at is part of
    a financial record. LE-1's July is posted and then its AR account is
    attacked with DELETE."""
    actor = signed_in("system_admin")
    with tenant_ctx(brazos):
        accounts = make_accounts(actor, brazos, {})
        post_le1_month(brazos, accounts)
        ar = models.LedgerAccount.objects.get(tenant_id=brazos.id, designation=chart.AR)
        assert models.JournalLine.objects.filter(tenant_id=brazos.id, ledger_account=ar).exists()

    response = call(chart_api.account_item, brazos, "delete", account_id=ar.pk)
    refused(response, errors.BIZ_STATE)
    with tenant_ctx(brazos):
        assert models.LedgerAccount.objects.filter(pk=ar.pk).exists()


def test_us_led_005_tc5b__delete_refuses_when_a_reference_kind_is_UNREADABLE(brazos, monkeypatch):
    """**THE DEF-127 SHAPE, REFUSED.** Two of the four reference kinds are other
    modules' reads and neither publishes a reverse lookup, so the honest answer
    is *"I cannot tell"* — never zero. A brand-new account with no journal lines
    at all still refuses to delete while the answer is unknown, and the refusal
    is the whole point of the case.
    """
    created = call(
        chart_api.accounts,
        brazos,
        "post",
        data={"code": "1155", "name": "Nothing points here", "type": "asset"},
    )
    account_id = created.data["account_id"]
    from apps.ledger import services as ledger_services

    with tenant_ctx(brazos):
        references = ledger_services.account_references(account_id)
    assert references["referenced"] is False, "nothing points at a brand-new account"
    assert references["answerable"] is False, (
        "charge codes and tax authorities publish no reverse lookup — an unanswerable "
        "reference read is not a zero"
    )
    refused(call(chart_api.account_item, brazos, "delete", account_id=account_id), errors.BIZ_STATE)


def test_us_led_006_tc1__the_export_code_gaps_render_as_named_empty_states(brazos):
    """US-LED-006 TC-1 — *"gaps render as visible empty states, not silently"*."""
    with tenant_ctx(brazos):
        account = models.LedgerAccount.objects.filter(tenant_id=brazos.id).first()
    saved = call(
        chart_api.account_item,
        brazos,
        "patch",
        data={"qbo_ref": "79"},
        account_id=account.pk,
    )
    assert saved.status_code == 200, saved.data
    assert saved.data["qbo_ref"] == "79"

    mapping = call(chart_api.gl_mappings, brazos)
    assert mapping.status_code == 200, mapping.data
    row = next(
        r for r in mapping.data["export_codes"]["rows"] if r["account_id"] == str(account.pk)
    )
    assert row["qbo_ref"] == "79"
    # `_UNSET` vs None: typing a QuickBooks ref must not wipe the Xero one.
    assert "xero_ref" in row["gaps"]
    assert account.code in mapping.data["export_codes"]["missing"]["xero_ref"]


def test_us_led_005_tc6__the_gl_map_names_every_designation_and_its_account(brazos, monkeypatch):
    """BR-LED-014's page — and the two states it must keep apart.

    Every one of the twelve designations appears. ⚠ AMENDED 2026-08-18:
    `budget_variance` used to appear with NO account (its account was an
    addition to ❄️ frozen B5 line 74 no agent could write). The PO wrote it on
    2026-08-17 — CR-010 B-8, verbatim *"8 - A ✅ 4180 "Budget billing variance",
    revenue, signed=False (the 4160/4170 precedent)"* — so it resolves to the
    seeded **4180**.

    ⚠ **AMENDED AGAIN THE SAME DAY: `awaiting_finance_re_sign` IS NOW FALSE FOR
    IT.** The Product Owner finance re-signed 4180 on **2026-08-18**, shown its
    code and name in plain English with the eight cost accounts and with no
    dollar figure attached to any of the nine (B4/B5 ❄️ FROZEN, un-edited). A GL
    map still flagging 4180 would send a finance reviewer to a row they had just
    ratified.

    **Both pending states the flag unions are now empty, so the flag is kept
    honest on a synthetic one** — otherwise it could be replaced by the constant
    `false` and every assertion here would still pass. Precedent: CR-011 item 9
    on `test_us_not_005`.
    """
    response = call(chart_api.gl_mappings, brazos)
    assert response.status_code == 200, response.data
    rows = {row["designation"]: row for row in response.data["designations"]}
    assert set(rows) == set(chart.GL_DESIGNATIONS)
    assert rows[chart.AR]["code"], "the AR designation resolves on a seeded chart"
    assert rows[chart.AR]["awaiting_finance_re_sign"] is False
    assert rows[chart.BUDGET_VARIANCE]["code"] == "4180"
    assert rows[chart.BUDGET_VARIANCE]["account_id"] is not None
    assert rows[chart.BUDGET_VARIANCE]["awaiting_finance_re_sign"] is False, (
        "4180 was finance re-signed on 2026-08-18 and the GL map is still asking a reviewer "
        "to look at it"
    )

    # ── the flag still reports BOTH pending states, each on a synthetic one ──
    # (1) a seeded CODE finance has not re-signed.
    monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN", ("4180",))
    flagged = call(chart_api.gl_mappings, brazos)
    flagged_rows = {row["designation"]: row for row in flagged.data["designations"]}
    assert flagged_rows[chart.BUDGET_VARIANCE]["awaiting_finance_re_sign"] is True
    assert flagged_rows[chart.AR]["awaiting_finance_re_sign"] is False
    # (2) a DESIGNATION with no seeded account at all — the other pending state,
    # which is a different question and must not be conflated with the first.
    monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN", ())
    monkeypatch.setattr(chart, "PENDING_FINANCE_RESIGN", (chart.AR,))
    unseeded = call(chart_api.gl_mappings, brazos)
    unseeded_rows = {row["designation"]: row for row in unseeded.data["designations"]}
    assert unseeded_rows[chart.AR]["awaiting_finance_re_sign"] is True
    # The bulk write 11b §2.10 names is NOT served, and the read says so by name
    # rather than leaving it to be discovered as a 404.
    assert "gl_mapping_bulk_write_is_not_served" in {
        gap["code"] for gap in response.data["unavailable"]
    }
    # The other half of the map is tenancy's to write, and the route is named.
    assert response.data["services"]["write_route"] == chart_api.SERVICE_MAPPING_WRITE_ROUTE


def test_us_led_005_tc7__another_tenants_account_is_NOT_FOUND(brazos, lonestar):
    """HR-1 / BR-TEN-003 — cross-tenant is a 404, never a 403. A 403 would
    confirm the row exists somewhere, which is the oracle isolation closes."""
    with tenant_ctx(lonestar):
        theirs = models.LedgerAccount.objects.filter(tenant_id=lonestar.id).first()
    assert theirs is not None
    response = call(
        chart_api.account_item, brazos, "patch", data={"name": "x"}, account_id=theirs.pk
    )
    assert response.status_code == 404
    with tenant_ctx(lonestar):
        theirs.refresh_from_db()
        assert theirs.name != "x"


def test_us_led_005_tc8__an_executive_may_not_edit_the_chart(brazos):
    """A4 gives Executive full on Finance; BR-LED-015's chart edits are a System
    Admin / Billing Clerk act, gated at the endpoint AND again in the service."""
    response = call(
        chart_api.accounts,
        brazos,
        "post",
        role="executive",
        data={"code": "1160", "name": "Nope", "type": "asset"},
    )
    refused(response, errors.AUTH_PERMISSION_DENIED)
    with tenant_ctx(brazos):
        assert not models.LedgerAccount.objects.filter(tenant_id=brazos.id, code="1160").exists()
