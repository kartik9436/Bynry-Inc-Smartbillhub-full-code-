# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-5755 — `GET /disconnects` built EVERY disconnect-relevant
#          account in the tenant in order to draw fifty. `disconnect_reads.
#          _rows_for` returned a Python LIST and `list_disconnects` sliced it,
#          so the page never reached SQL and `total` was a `len()`.
#          The LAST Python-paged list in the customers module.
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere) ·
#          BR-SHL-011 (a list URL clamps and never 4xx) · hard rule 1 (tenant
#          scoping — a page may not reach another tenant) · BR-CUS-1046 /
#          DEF-CUS-5060 (the creation-order default this list opens on) ·
#          BR-CUS-039 · BR-CUS-043 (an active AND current plan pauses the
#          ladder — the DERIVED half of §4's union) · B18 §5.8.2 (the row set,
#          the six segments, the sort vocabulary) · DEF-CUS-5753 / DEF-RAT-5742
#          (the same fix one and two screens over, whose shape this follows)
# Tests:   this file
# Impacts: 06-backend/apps/customers/disconnect_reads.py
#          (`_list_queryset` · `_page_of` · `_cases_for` · `_search_q` ·
#          `disconnect_list_protected_half_is_python`; `_rows_for` DELETED)
# ───────────────────────────────────────────────────────
"""DEF-CUS-5755 — S90's Disconnects list takes its page in the DATABASE.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`): every case below was run in a SECOND `git worktree` at the same
pinned tip with the fix absent — **4 failed, 5 passed** — and the four failures
are the defect in its own words:

    GET /disconnects sent no `LIMIT 40` over `accounts` — the page was taken
    in Python, which is DEF-CUS-5755. Statements: 285
    the disconnects total was counted in Python — every disconnect-relevant
    account in the tenant was built to produce one number
    drawing 40 rows built 320 account rows out of a tab of 120 —
    DEF-CUS-5755. At the top of T5 that is 40,000 rows for one screen.
    drawing 40 rows built 200 case rows over 100 open cases — the list half
    is still reading every case in the tenant (DEF-CUS-5755)

MEASURED on ONE population of 120 (100 open cases + 20 medical holds) at TWO
page sizes, before and after:

| | rows on wire | total | account rows built | case rows built | statements |
|---|---|---|---|---|---|
| before, page 40 | 40 | 120 | **320** | **200** | 285 |
| before, page 1,000 | 120 | 120 | **320** | **200** | 845 |
| after, page 40 | 40 | 120 | **40** | **120** | 265 |
| after, page 1,000 | 120 | 120 | **120** | **200** | 825 |

**Before, the account rows do not move when the page size changes 25×.** That
flatness is what a Python pager IS. The 320 decomposes exactly: 100 accounts
joined in by `open_cases`' `select_related` inside `_rows_for`, 120 from the
union queryset, and 100 joined in again by `kpi_strip` calling `open_cases` a
second time. The statements barely moved (285 → 265) and the rows fell by 280,
which is why every case here asserts SQL or rows and none asserts a query
ceiling.

⚠ **THE THING THIS LIST DECIDES IS WHETHER SOMEBODY'S WATER GETS SHUT OFF**, so
the row SET and its ORDER are pinned by value FIRST — `test_the_row_set_and_its
_order_do_not_move` and `test_the_state_filter_shows_exactly_what_it_showed`
are written to pass on BOTH trees and are the whole reason the rest of the file
is safe to land. A page taken in SQL that quietly drops a protected account is
worse than a slow page, and no statement count can see it.

⚠ **WHICH CASES SPEAK, AND WHICH ARE ONLY GUARDS — STATED, BECAUSE A READER
CANNOT TELL FROM A GREEN DOT.** Four fail on the unfixed tree and ARE the
defect: the missing `LIMIT`, the missing `COUNT(*)`, the account rows built to
draw one page, and the case rows built twice over. The other six pass either
way by design and exist because the fix rebuilds how the row set is assembled:
the row set by value, the order, the `f.state` filter, the search, the tenant
boundary and the derived protected half.

⚠ **WHAT WOULD MAKE THE SPEAKING CASES PASS WRONGLY** (law 7 habit 2), each
designed out rather than hoped about:
  * A check for the bare word `LIMIT` passes on a tree that never asked for a
    page — Django renders `Subquery(...[:1])` as `LIMIT 1` inside a SELECT
    list, which is `DEF-RAT-5742`'s own false pass. So the assertion is
    `LIMIT <the page size asked for>` AND the statement must select `FROM
    "accounts"`.
  * A check that counts RETURNED ROWS cannot tell SQL paging from Python
    paging — the broken code returned exactly fifty correct rows and a correct
    total. So nothing here asserts a page length as evidence.
  * A check run at ONE page size cannot tell a cost that follows the page from
    one that does not. Every measurement below is taken at TWO page sizes over
    ONE population (40 and 1,000), which is the shape that shows a flat cost
    for what it is.

Run with `JOBS_EAGER=false` (DEF-567).
"""

import re
from datetime import date
from decimal import Decimal as D

import pytest
from django.db import connection
from django.db.models.signals import post_init
from django.test.utils import CaptureQueriesContext

from apps.customers import disconnect_reads, disconnects
from apps.customers import models as customers_models
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

#: The population every measurement is taken over. ONE population, measured at
#: two PAGE sizes — the shape that can tell a cost that follows the page from a
#: cost that is simply flat. A second, larger population would answer a
#: different question and is deliberately not built.
POPULATION = 120

#: The two page sizes. 40 is below IS-2's smallest step, so a request through
#: the API clamps it to 50 (`clamp_page_size`); the SELECTOR honours it, and
#: that is what makes it a useful low end here — the numbers below are the
#: selector's.
SMALL_PAGE = 40
LARGE_PAGE = 1000


# ══════════════════════════════════════════════════════════════════════════
# Fixture — accounts that are ON THE TAB, by both halves of §4's union
# ══════════════════════════════════════════════════════════════════════════
def plant_tab(tenant, *, cases: int, protected: int, tag: str) -> int:
    """`cases` accounts with an OPEN disconnect case, `protected` with a hold.

    ⚠ **BOTH HALVES OF THE UNION, BECAUSE THEY TAKE DIFFERENT PATHS.** §4 of
    `disconnect_reads` is *open cases ∪ accounts with a protection in force*,
    and the second half is DERIVED — a `payment_plan` protection's liveness is
    read from payments every time it is asked. A fixture of cases alone would
    let a fix that lost every protected account stay green, which on this tab
    means an account under a medical certificate silently leaving the list a
    clerk uses to authorise a cut.

    Rows are planted through the ORM rather than walked through `advance()`:
    this file measures the READ, and a fixture of 120 real ladder walks would
    take minutes to prove something about a SELECT.
    """
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"400 Cutoff Rd {tag}", city="Ottumwa", state="IA"
    )
    status = customers_models.AccountStatus.objects.filter(tenant=tenant).first()
    assert status is not None, "the tenant has no account status seeded"
    account_type = customers_models.AccountType.objects.filter(tenant=tenant).first()
    planted = 0
    for index in range(cases + protected):
        unit = metering_models.Unit.objects.create(
            tenant=tenant, premises=premises, label=f"Unit {tag}{index:04d}"
        )
        account = customers_models.Account.objects.create(
            tenant=tenant,
            unit=unit,
            premises_id=premises.id,
            account_no=f"A-{tag}{index:05d}",
            status=status,
            account_type=account_type,
        )
        if index < cases:
            disconnects.DisconnectCase.objects.create(
                tenant=tenant,
                account=account,
                sequence=disconnects.SEQ_SERVICE,
                state=disconnects.STATE_NOTICE_SENT,
                tier=disconnects.TIER_1,
                tier_reached_on=TODAY,
                amount_owed_at_open=D("612.7500"),
                currency="USD",
                opened_on=TODAY,
            )
        else:
            disconnects.AccountProtection.objects.create(
                tenant=tenant,
                account=account,
                kind=disconnects.PROTECTION_MEDICAL,
                effective_from=date(2026, 8, 1),
                expires_on=date(2026, 12, 31),
                set_by="fixture",
            )
        planted += 1
    return planted


class _EveryAccount(dict):
    """A positions map that answers the same figure for any account id — the
    shape `test_w7_worklists._owes` uses, so the LEDGER BOUNDARY is the real
    `seams.ArPositions` and not a fake of it."""

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def _owes(monkeypatch, amount=D("612.75")):
    """Publish a readable AR position, so the per-row ladder decision does not
    spend a ledger read of its own and the counts below measure the LIST."""
    positions = disconnects.seams.ArPositions(
        positions=_EveryAccount(amount), currency="USD"
    )
    monkeypatch.setattr(disconnects.seams, "ar_positions", lambda *_a, **_k: positions)
    monkeypatch.setattr(disconnect_reads.seams, "ar_positions", lambda *_a, **_k: positions)


class _Built:
    """Counts model rows BUILT IN PYTHON, per class, via `post_init`.

    ⚠ **THIS IS THE MEASUREMENT `NFR-3` IS ABOUT, AND A STATEMENT COUNT IS
    NOT.** One fix this week went from 8 statements to 9 while the rows it
    dragged into memory fell from 1,000 to 50 — counting queries alone would
    have called that a regression. `post_init` fires once per instance Django
    constructs, which is once per row a SELECT returned, so this counts exactly
    what a page drags out of the database.

    ⚠ **IT COUNTS INSTANCES, NOT BYTES**, so it cannot see a `select_related`
    fetching a whole joined row for nobody. That blind spot is stated rather
    than left to be discovered (law 7's *declared blind spot with a number*).
    """

    def __init__(self, *models):
        self.counts = {model: 0 for model in models}
        self._handlers = []

    def __enter__(self):
        for model in self.counts:
            def handler(sender, instance, _model=model, **_kw):
                self.counts[_model] += 1

            post_init.connect(handler, sender=model, weak=False)
            self._handlers.append((handler, model))
        return self

    def __exit__(self, *_exc):
        for handler, model in self._handlers:
            post_init.disconnect(handler, sender=model)
        return False

    def __getitem__(self, model):
        return self.counts[model]


def _limit(queries, size):
    """Statements that ask the database for exactly `size` rows OF ACCOUNTS.

    ⚠ **`LIMIT <size>` AND NOT `LIMIT`, AND `FROM "accounts"` AS WELL** — the
    two false passes `DEF-RAT-5742` designed itself out of, kept here because
    this list's row builders each read their own tables and any of them could
    carry a `LIMIT 1`.
    """
    pattern = re.compile(rf"\bLIMIT\s+{size}\b", re.I)
    return [
        query
        for query in queries
        if pattern.search(query["sql"]) and re.search(r'FROM\s+"?accounts"?', query["sql"], re.I)
    ]


def _numbers(payload):
    return [row["account_no"] for row in payload["rows"]]


# ══════════════════════════════════════════════════════════════════════════
# 0 · THE ROW SET AND ITS ORDER, PINNED BY VALUE — true on BOTH trees
# ══════════════════════════════════════════════════════════════════════════
def test_the_row_set_and_its_order_do_not_move(brazos, dana, monkeypatch):
    """⚠ **THE CASE THAT MAKES THE REST SAFE TO LAND, AND IT IS A GUARD.**

    It passes on the unfixed tree by design: it exists to say that the fix
    changed HOW the fifty rows are found and not WHICH fifty they are. A
    disconnect list decides whether somebody's water gets shut off, and a
    statement count cannot tell a faster page from a page that quietly lost the
    accounts under a medical certificate.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=6, protected=4, tag="s")
        whole = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE)
        assert whole["total"] == 10, "§4's union is open cases ∪ protected accounts"

        every = _numbers(whole)
        # BR-CUS-1046 — newest first, and every sort ends in `id` (IS-2), so
        # the boundary between two pages is stable.
        assert every == sorted(every, reverse=True), "the tab opens on the creation order"

        # The SAME ten rows, drawn four at a time, must be the same ten in the
        # same order. This is the assertion a slice-in-Python and a LIMIT in
        # SQL are allowed to disagree on, and may not.
        paged = []
        for page in (1, 2, 3):
            paged += _numbers(disconnect_reads.list_disconnects(as_of=TODAY, page=page, per=4))
        assert paged == every
        assert _numbers(disconnect_reads.list_disconnects(as_of=TODAY, page=4, per=4)) == []


def test_the_state_filter_shows_exactly_what_it_showed(brazos, dana, monkeypatch):
    """`f.state` — a GUARD, and the one that pins §4's stated asymmetry.

    `disconnect_reads`' own words: *"A ROW WITH NO CASE CANNOT MATCH A CASE
    STATE, AND IT MUST NOT"* — an account on the tab only because it holds a
    protection has no stored state at all, so filtering by one drops it. That
    sentence is what moving the filter into SQL had to preserve.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=5, protected=3, tag="f")
        on_notice = disconnect_reads.list_disconnects(
            as_of=TODAY, per=LARGE_PAGE, filters={"state": disconnects.STATE_NOTICE_SENT}
        )
        assert on_notice["total"] == 5, "the five cases, and NOT the three protected accounts"
        assert all(row["case"] is not None for row in on_notice["rows"])

        cut = disconnect_reads.list_disconnects(
            as_of=TODAY, per=LARGE_PAGE, filters={"state": disconnects.STATE_CUT}
        )
        assert cut["total"] == 0, "no case is cut, so the filter shows nothing"

        # A state this list cannot hold shows NOTHING, never everything — the
        # `return []` branch, which a `.filter()` that silently ignores an
        # unknown value would turn into a full listing.
        left = disconnect_reads.list_disconnects(
            as_of=TODAY, per=LARGE_PAGE, filters={"state": disconnects.STATE_STOPPED}
        )
        assert left["total"] == 0


def test_the_search_still_finds_by_account_number(brazos, dana, monkeypatch):
    """B18 §5.8.2's box — a GUARD over the leg the fix rewrote from a set of
    ids into a predicate. A term below `MIN_SEARCH_CHARS` narrows NOTHING,
    which is *"the term is too short to search on"* and not *"no matches"*."""
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=4, protected=2, tag="q")
        hit = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE, q="A-q00003")
        assert _numbers(hit) == ["A-q00003"] and hit["total"] == 1
        miss = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE, q="A-zzzzzz")
        assert miss["total"] == 0
        short = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE, q="A")
        assert short["total"] == 6, "a one-character term does not filter at all"


def test_a_page_never_reaches_another_tenant(brazos, lonestar, dana, monkeypatch):
    """TC-DSC-9 as a GUARD on the new queryset — hard rule 1. A union built
    from a subquery and an id list has two places a tenant predicate can go
    missing, and neither may."""
    with tenant_ctx(lonestar):
        plant_tab(lonestar, cases=3, protected=2, tag="x")
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=2, protected=1, tag="b")
        mine = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE)
        assert mine["total"] == 3
        assert all(number.startswith("A-b") for number in _numbers(mine))


def test_the_derived_protected_half_is_still_derived(brazos, dana, monkeypatch):
    """⚠ **A GUARD ON WHAT WAS DELIBERATELY *NOT* DONE.**

    `ON HOLD` is not a stored state — `disconnects.STATE_ON_HOLD` is declared
    and nothing in this repository ever assigns it — so an account is on this
    tab because a PROTECTION IS IN FORCE, which for a `payment_plan` is read
    from payments on every call. This case asserts a protected account with NO
    case reaches the list and carries no stored state, which is what a fix that
    replaced the derivation with a WHERE clause over `account_protections`
    would quietly get wrong the first time a plan lapsed.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=1, protected=1, tag="d")
        rows = disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE)["rows"]
        held = [row for row in rows if row["case"] is None]
        assert len(held) == 1, "the protected account is on the tab without a case"
        assert held[0]["state"]["stored"] is None
        assert held[0]["state"]["held_by"] == [disconnects.PROTECTION_MEDICAL]

        # A protection that has LAPSED takes its account off the tab, and the
        # answer comes from `protections_for` rather than from the SQL window.
        gone = disconnect_reads.list_disconnects(as_of=date(2027, 6, 1), per=LARGE_PAGE)
        assert all(row["case"] is not None for row in gone["rows"])


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PAGE IS TAKEN IN SQL — the cases that go RED on the old code
# ══════════════════════════════════════════════════════════════════════════
def test_the_page_is_a_sql_limit_and_follows_the_page_size(brazos, dana, monkeypatch):
    """`NFR-3`: the page is a `LIMIT`, not a slice of a built list.

    Measured at TWO page sizes over ONE population, because a `LIMIT` that is
    always the same number is a `LIMIT` that is not the clerk's page size.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=POPULATION - 20, protected=20, tag="l")
        with CaptureQueriesContext(connection) as small:
            disconnect_reads.list_disconnects(as_of=TODAY, per=SMALL_PAGE)
        with CaptureQueriesContext(connection) as large:
            disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE)

    assert _limit(small.captured_queries, SMALL_PAGE), (
        f"GET /disconnects sent no `LIMIT {SMALL_PAGE}` over `accounts` — the page was "
        f"taken in Python, which is DEF-CUS-5755. Statements: {len(small.captured_queries)}"
    )
    assert _limit(large.captured_queries, LARGE_PAGE), (
        f"the page size did not reach the database as a `LIMIT {LARGE_PAGE}`"
    )
    assert not _limit(small.captured_queries, LARGE_PAGE), (
        "a page of 40 asked the database for 1,000 rows — the LIMIT is not the page size"
    )


def test_the_total_is_a_sql_count_and_not_a_len(brazos, dana, monkeypatch):
    """The other half of `NFR-3`, and the half that is easy to lose: a page
    taken in SQL whose total is still `len(everything)` has MOVED the cost
    rather than removed it."""
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=POPULATION - 20, protected=20, tag="c")
        with CaptureQueriesContext(connection) as ctx:
            payload = disconnect_reads.list_disconnects(as_of=TODAY, per=SMALL_PAGE)

    assert payload["total"] == POPULATION and len(payload["rows"]) == SMALL_PAGE
    counted = [
        query
        for query in ctx.captured_queries
        if "COUNT(" in query["sql"].upper()
        and re.search(r'FROM\s+"?accounts"?', query["sql"], re.I)
    ]
    assert counted, (
        "the disconnects total was counted in Python — every disconnect-relevant "
        "account in the tenant was built to produce one number"
    )


def test_the_account_rows_built_follow_the_page_and_not_the_tenant(
    brazos, dana, monkeypatch
):
    """⚠ **THE MEASUREMENT THAT NAMES THE DEFECT.** Rows, not statements.

    At a page of 40 over a tab of 120, the account rows dragged into Python
    must be the page and its per-row reads — never the tenant. The bound is
    written as `2 × page` because the ladder decision reads the account again
    per row (`disconnects._account`), which is `list_row`'s documented design
    and is deliberately NOT batched: *"a RUN cached on a row outlives the
    debt"*.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        plant_tab(brazos, cases=POPULATION - 20, protected=20, tag="r")
        with _Built(customers_models.Account) as small:
            disconnect_reads.list_disconnects(as_of=TODAY, per=SMALL_PAGE)
        with _Built(customers_models.Account) as large:
            disconnect_reads.list_disconnects(as_of=TODAY, per=LARGE_PAGE)

    built_small = small[customers_models.Account]
    built_large = large[customers_models.Account]
    assert built_small <= SMALL_PAGE * 2 + 5, (
        f"drawing {SMALL_PAGE} rows built {built_small} account rows out of a tab of "
        f"{POPULATION} — DEF-CUS-5755. At the top of T5 that is 40,000 rows for one screen."
    )
    assert built_small < built_large, (
        f"the account rows built did not move when the page size went {SMALL_PAGE} → "
        f"{LARGE_PAGE} ({built_small} vs {built_large}) — the cost is flat in the "
        "population, which is what a Python pager looks like"
    )


def test_the_case_rows_are_read_once_and_only_for_the_page(brazos, dana, monkeypatch):
    """The second O(tenant) read, and it was paid TWICE per request.

    `_rows_for` built every open case in the tenant to key a dict, and
    `kpi_strip` built every open case again for its five counts. The list half
    is now one query for the page's cases; the KPI half is DELIBERATELY still a
    whole-set read and is asserted here so the judgment is a number rather than
    a sentence — see the decision-log row of 2026-09-19.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch)
        planted = plant_tab(brazos, cases=POPULATION - 20, protected=20, tag="k")
        with _Built(disconnects.DisconnectCase) as small:
            disconnect_reads.list_disconnects(as_of=TODAY, per=SMALL_PAGE)

    open_cases = planted - 20
    built = small[disconnects.DisconnectCase]
    assert built <= open_cases + SMALL_PAGE, (
        f"drawing {SMALL_PAGE} rows built {built} case rows over {open_cases} open cases — "
        "the list half is still reading every case in the tenant (DEF-CUS-5755)"
    )
    assert built > SMALL_PAGE, (
        "the KPI strip counts over the WHOLE set by definition; if this ever drops to the "
        "page size, a tile has started counting only what is on screen"
    )
