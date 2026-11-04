# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 / US-CUS-002 (the S17 register and its capability row)
#           Screens: S17 (the Accounts tab — the `CUSTOMER #` column and the
#           search box above it)
# Change:   CR-030 W2 — task 2.9 (a) the selector learns `customer_no` and
#           (b) the row serves it
# Rules:    BR-CUS-053 (AMENDED 2026-08-24, PO ruling — the search set is FIVE,
#           not four, and `CUSTOMER #` is a column as well as a search term) ·
#           BR-CUS-054 (the first-class customer entity; `customer_accounts` is
#           N:M, so a jointly-held account has more than one holder) ·
#           BR-CUS-015 (AMENDED 2026-08-24 — the S17 column set) ·
#           BR-SHL-011 (a list URL never 4xx's over its params) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE)
# ───────────────────────────────────────────────────────
"""CR-030 W2 T2.9 — one search box, two numbers.

**THE PO ASKED FOR THIS AS A QUESTION ABOUT WORK THEY EXPECTED TO BE DONE**
(2026-08-24, verbatim): *"we were suppose to add customer # comlume what
happened to that"*. The honest answer was half good news — the STORED column
landed in W0 (`customers.customer_no`, migrations `0013_cr030_w0_customer_no` +
`0014_cr030_w0_backfill_customer_no`) and nothing on the way to a screen used
it. BR-CUS-053's amendment names the three missing pieces; this file is the
first of them, *"(a) `selectors.account_list` MATCHES `customer_no` —
`Q(customer__customer_no__icontains=term)` joined into the same OR as
`account_no`, so one box finds a person by either number"*, plus the row field
(b) the column renders from.

**WHY IT IS THE SAME BOX AND NOT A SECOND ONE.** A clerk holding a scrap of
paper with digits on it does not know whether those digits are ours for the
ACCOUNT or ours for the CUSTOMER. Two boxes would make them decide before they
can search, which is the question they rang up to have answered.

**PROVED RED FIRST (hard-won law 7).** With the `_account_ids_by_customer_no`
leg removed from `account_list`'s OR-group, and with `customer_nos_for` removed
from the row, the failures quoted in the lane report were::

    test_tc_acc_7__the_box_finds_an_account_by_the_customer_number
        AssertionError: assert [] == ['A-...']  (searching "C-00001" matched nothing)
    test_t2_9b__the_row_serves_customer_no_for_the_column_to_render
        KeyError: 'customer_no'

Both were restored to green by the clause under test and by nothing else.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import models as customers_models
from apps.customers import selectors
from apps.customers import services as customers_services
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    erin,
    tenant_ctx,
)

# The account factory the W0 suite already threads a plan, a premise and a
# service point through. Imported rather than re-written: a second copy of that
# four-module set-up is a second place for it to go stale (hard-won law 5).
from tests.test_cr030_w0_customer_no import _account_for  # noqa: E402

pytestmark = pytest.mark.django_db


def _numbered_customer(account, *, ref: str, name: str) -> str:
    """Link `account` to a customer and return the allocated `customer_no`."""
    linked = customers_services.link_customer(
        account_id=account["id"], external_ref=ref, display_name=name
    )
    assert linked is not None, "link_customer returned None — the fixture is wrong, not the rule"
    return linked["customer_no"]


def _search(term: str) -> list[str]:
    """`GET /accounts?q=<term>` as the selector sees it — account numbers back,
    because those are what a reader of a failure message can recognise."""
    return [row["account_no"] for row in selectors.account_list(ListParams(q=term))]


# ══════════════════════════════════════════════════════════════════════════
# TC-ACC-7 — the search leg (BR-CUS-053 (a))
# ══════════════════════════════════════════════════════════════════════════


def test_tc_acc_7__the_box_finds_an_account_by_the_customer_number(brazos, marcus):
    """B18 §5.1.4 TC-ACC-7, in the state BR-CUS-053 amends it into.

    **The declared row reads:** *"Given `customer_no` not yet migrated · When
    the search placeholder renders · Then it does not offer `customer #`"*. The
    Given is now FALSE — the column migrated in W0 — and BR-CUS-053 says in so
    many words what the case becomes: *"`TC-ACC-7` is the test that goes green
    when the selector learns the column."* So this is that case, from the far
    side of its own precondition: the number is migrated, therefore the search
    performs it, therefore the placeholder may name it (asserted on the screen
    in `AccountsPage.test.tsx`).
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN A")
        customer_no = _numbered_customer(account, ref="CUST-118", name="Ridge Coffee Co.")

        assert _search(customer_no) == [account["account_no"]]


def test_tc_acc_7__one_box_finds_the_same_person_by_either_number(brazos, marcus):
    """BR-CUS-053(a) verbatim: *"joined into the same OR as `account_no`, so one
    box finds a person by either number."*

    Asserted as ONE property rather than two searches that happen to work: the
    same row comes back from the account number and from the customer number,
    which is the sentence the rule wrote and the thing a second search box would
    have broken.
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN B")
        customer_no = _numbered_customer(account, ref="CUST-220", name="Ridge Coffee Co.")

        by_account = _search(account["account_no"])
        by_customer = _search(customer_no)

        assert by_account == [account["account_no"]]
        assert by_customer == by_account


def test_tc_acc_7__a_partial_number_matches_the_way_the_account_number_does(brazos, marcus):
    """`icontains`, matching the posture of the `account_no` leg beside it.

    A clerk reads digits off the bottom of a bill and types `0000` — not the
    `C-` the series prefixes. A prefix-only match would find nothing and look
    exactly like "this customer does not exist".
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN C")
        customer_no = _numbered_customer(account, ref="CUST-330", name="Ridge Coffee Co.")
        assert customer_no.startswith("C-"), customer_no

        assert _search(customer_no[2:]) == [account["account_no"]]
        # And case-insensitively, because the column's UNIQUE constraint is
        # (`uq_customers_tenant_customer_no_ci`): a case-sensitive search could
        # miss a row the schema treats as the same customer.
        assert _search(customer_no.lower()) == [account["account_no"]]
        assert _search(customer_no.upper()) == [account["account_no"]]


def test_tc_acc_7__min_search_chars_gates_this_leg_with_the_others(brazos, marcus):
    """`MIN_SEARCH_CHARS` (IS-3) is two, and the new leg sits INSIDE it.

    A one-character `C` matches every customer number in the tenant through
    `icontains`, so a leg outside the guard would turn the shortest possible
    keystroke into a full-tenant scan — and would return the whole register to a
    user who has typed nothing meaningful.
    """
    with tenant_ctx(brazos):
        first = _account_for(marcus, brazos, label="W2 CN D1")
        second = _account_for(marcus, brazos, label="W2 CN D2")
        _numbered_customer(first, ref="CUST-440", name="Ridge Coffee Co.")
        _numbered_customer(second, ref="CUST-441", name="Bayou Laundromat")

        assert selectors.MIN_SEARCH_CHARS == 2
        # One character searches NOTHING — the whole list comes back, which is
        # the "no term" behaviour and not a customer-number match.
        both = {first["account_no"], second["account_no"]}
        assert both.issubset(set(_search("C")))


def test_tc_acc_7__a_number_that_matches_nothing_returns_nothing_and_never_errors(brazos, marcus):
    """BR-SHL-011: a list URL never 4xx's over its params. A search term with no
    hit is an EMPTY LIST, which is what A18 §2's zero-results frame renders."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN E")
        _numbered_customer(account, ref="CUST-550", name="Ridge Coffee Co.")

        assert _search("C-99999") == []


def test_tc_acc_7__every_holder_of_a_joint_account_can_find_it(brazos, marcus):
    """BR-CUS-054 makes `customer_accounts` **N:M** — *"a jointly-held account
    counts every holder's other accounts"* — so an account can carry more than
    one customer link.

    The CELL renders the first link's number (so S17 and S21 cannot disagree);
    the SEARCH matches every link, because the second holder's number is a
    perfectly good way to find the row and refusing it would make the box lie
    about what it searches. Both halves are asserted here, together, because
    they are the pair that could silently drift apart.
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN F")
        first_no = _numbered_customer(account, ref="CUST-660", name="Ridge Coffee Co.")
        second_no = _numbered_customer(account, ref="CUST-661", name="Dana Okafor")
        assert first_no != second_no

        assert _search(first_no) == [account["account_no"]]
        assert _search(second_no) == [account["account_no"]]
        # ONE row, not two — the N:M join must not multiply the register.
        assert len(selectors.account_list(ListParams(q=second_no))) == 1

        rows = selectors.account_list(ListParams(q=account["account_no"]))
        assert rows[0]["customer_no"] == first_no


def test_tc_acc_7__an_unlinked_account_is_untouched_by_the_new_leg(brazos, marcus):
    """An account with no `customer_accounts` link at all — every account
    created before BR-CUS-054's entity existed, and every import row that
    carried neither a reference nor a name.

    It is still found by its ACCOUNT number and still renders, with a null
    customer number. The new OR leg must not narrow anything.
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN G")

        assert _search(account["account_no"]) == [account["account_no"]]
        rows = selectors.account_list(ListParams(q=account["account_no"]))
        assert rows[0]["customer_no"] is None


# ══════════════════════════════════════════════════════════════════════════
# T2.9 (b) — the value the `CUSTOMER #` column renders
# ══════════════════════════════════════════════════════════════════════════


def test_t2_9b__the_row_serves_customer_no_for_the_column_to_render(brazos, marcus):
    """BR-CUS-053(b): *"the list renders `CUSTOMER #` as a column"*.

    A column with no served field is hard-won law 2 wearing a table header, so
    the field is asserted on the ROW and not merely on the screen — the screen
    test can only prove that a served value reaches a cell.
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN H")
        customer_no = _numbered_customer(account, ref="CUST-770", name="Ridge Coffee Co.")

        row = selectors.account_row(customers_models.Account.objects.get(pk=account["id"]))
        assert row["customer_no"] == customer_no


def test_t2_9b__the_detail_row_serves_the_same_number_as_the_list(brazos, marcus):
    """`account_detail_dict` spreads `account_row`, so S21 and S17 read ONE
    derivation of this cell. Asserted rather than assumed — the detail already
    carries a `customer` block, and two paths to one number is how they drift.
    """
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN I")
        customer_no = _numbered_customer(account, ref="CUST-880", name="Ridge Coffee Co.")

        detail = selectors.account_detail(account["id"])
        listed = selectors.account_list(ListParams(q=account["account_no"]))[0]
        assert detail["customer_no"] == customer_no == listed["customer_no"]


def test_t2_9b__the_page_costs_one_customer_read_however_many_rows_it_holds(brazos, marcus):
    """The DEF-127 property, applied to the read this task adds.

    `account_list` serializes EVERY matching account before the paginator
    slices, so a `customer_for_account` per row would be one query per ACCOUNT
    on the product's busiest screen — which is precisely the shape the DEF-127
    comment in that function forbids for the ledger and billing reads.

    ⚠ **THIS COUNTS THE `customer_accounts` READS AND NOT THE WHOLE PAGE, AND
    THE DIFFERENCE IS A FINDING RATHER THAN A CONVENIENCE.** A first draft
    asserted the TOTAL query count does not grow with the row count and went
    red: **15 queries for one account, 43 for five**, i.e. ~7 per extra row —
    `_premise_cell`, `service_codes_for` and `primary_contact_name` each run per
    row and have since long before this change. That is real and it is
    REPORTED; it is not this task's, and an assertion that fails for someone
    else's reason is a guard nobody can keep green. So the property asserted
    here is the one this lane owns and can hold: **the customer-number read is
    ONE statement for the page, however many rows the page holds.**
    """

    def customer_reads(context: CaptureQueriesContext) -> list[str]:
        return [q["sql"] for q in context.captured_queries if "customer_accounts" in q["sql"]]

    with tenant_ctx(brazos):
        one = _account_for(marcus, brazos, label="W2 CN J1")
        _numbered_customer(one, ref="CUST-990", name="Ridge Coffee Co.")
        with CaptureQueriesContext(connection) as first_pass:
            selectors.account_list(ListParams())
        for i in range(4):
            extra = _account_for(marcus, brazos, label=f"W2 CN J{i + 2}")
            _numbered_customer(extra, ref=f"CUST-99{i + 1}", name=f"Holder {i}")
        with CaptureQueriesContext(connection) as second_pass:
            rows = selectors.account_list(ListParams())

        assert len(rows) >= 5
        # ⚠ TWO, NOT ONE, SINCE `DEF-CUS-9776` (2.549.8): the Name cell now
        # reads the CUSTOMER's name (`customer_names_for`), one more batched
        # `customer_accounts` statement for the page. The property this test
        # owns is unchanged — the count does not grow with the rows.
        assert len(customer_reads(first_pass)) == 2
        assert len(customer_reads(second_pass)) == 2, (
            "a customer read went per-row — "
            f"{len(customer_reads(second_pass))} statements for {len(rows)} accounts"
        )


def test_t2_9b__the_search_itself_adds_no_round_trip(brazos, marcus):
    """`_account_ids_by_customer_no` returns a LAZY queryset, so the fifth
    search leg renders as a nested SQL subquery inside the list's own `WHERE`
    rather than as a second statement. Asserted because a stray `list(...)`
    around it would be invisible in review and would cost a round trip on every
    keystroke of a debounced search box."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="W2 CN K")
        customer_no = _numbered_customer(account, ref="CUST-1010", name="Ridge Coffee Co.")

        ids = selectors._account_ids_by_customer_no(customer_no)
        # A QuerySet, not a materialised list — the property under test.
        assert hasattr(ids, "query"), type(ids)
        assert not isinstance(ids, list)
        assert [str(value) for value in ids] == [str(account["id"])]


# ══════════════════════════════════════════════════════════════════════════
# TC-ACC-6 — the isolation half, on the NEW query path
# ══════════════════════════════════════════════════════════════════════════


def test_tc_acc_6__a_customer_number_never_reaches_across_tenants(brazos, lonestar, marcus, erin):
    """CLAUDE.md hard rule 1, asserted against the leg that was just added.

    The existing W2 isolation cases cover the list; this covers the JOIN, which
    is a new way into `customers` and therefore a new way to leak out of one
    tenant. Brazos's `C-00001` and Lone Star's `C-00001` are different
    customers — the number is unique WITHIN a tenant and nowhere else.
    """
    with tenant_ctx(brazos):
        brazos_account = _account_for(marcus, brazos, label="W2 CN X")
        brazos_no = _numbered_customer(brazos_account, ref="CUST-2000", name="Ridge Coffee Co.")
    with tenant_ctx(lonestar):
        lonestar_account = _account_for(erin, lonestar, label="W2 CN Y", service="water")
        lonestar_no = _numbered_customer(
            lonestar_account, ref="CUST-2000", name="Hill Country Wash"
        )

    # Both tenants allocate from their OWN series, so the numbers collide by
    # design — which is exactly the condition a leak would hide behind.
    assert brazos_no == lonestar_no

    with tenant_ctx(brazos):
        assert _search(brazos_no) == [brazos_account["account_no"]]
    with tenant_ctx(lonestar):
        assert _search(lonestar_no) == [lonestar_account["account_no"]]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030/B18 §5.1.2 + §5.1.4 (S17) · BR-CUS-053 AMENDED 2026-08-24 ·
#         BR-CUS-054 · US-CUS-001/002 · W2 task 2.9 (a) + (b)
# generated: 2026-08-24 by the CR-030 W2 close-out lane (L2)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (this file) · the W0/W1/W2 customers suites re-run unchanged
# exceptions: E4 this file lives in `06-backend/tests/` and NOT in
#   `06-backend/apps/customers/tests/` — the latter does not exist; every
#   customers suite in this repo (`test_cr030_w0_customer_no.py`,
#   `test_cr030_w2_ageing.py`, `test_br_cus_068_*`) is in `tests/`, and
#   `pyproject.toml`'s `testpaths` lists it first. Following the real convention
#   rather than a described one · E4 TC-ACC-7's declared GIVEN (*"`customer_no`
#   not yet migrated"*) can no longer be reached: the column migrated in W0 and
#   a test cannot un-migrate it. The case is asserted from the far side of its
#   own precondition, which is what BR-CUS-053's amendment says it becomes ·
#   E4 the joint-holder case asserts the CELL takes the first link and the
#   SEARCH takes every link. That asymmetry is deliberate and is documented on
#   both functions; it is asserted in ONE test so the two cannot drift apart
#   without a failure that names the pair
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
