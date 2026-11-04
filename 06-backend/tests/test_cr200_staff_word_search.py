# ── Trace ──────────────────────────────────────────────
# Change:   CR-200-BRC10 lane A (S1–S6, T1, T2) — PO 2026-10-29, Question 3 A:
#           *"each typed word may match the address or the unit label, on Units
#           and Premises lists"*, and the code plan *"this is ok"*: the five
#           staff searches share ONE word-by-word matcher.
# Defects:  DEF-MET-10678 (words cannot combine across fields) ·
#           DEF-MET-10679 (top bar: a unit is never found by its street)
# Code:     core/search.py (`search_words`, `matches_every_word`) ·
#           apps/metering/selectors.py (field lists; premises_list,
#           units_queryset, move_in_unit_queryset) · apps/metering/address_picker.py ·
#           apps/metering/search_sources.py
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 8 (the address is
#           on premises; a unit is found by WALKING to it) · NFR-3 (one SQL
#           statement, paged in SQL) · NFR-5 (no cap)
# Run:      also on PostgreSQL (hard-won law 14): --ds=config.settings.pgtest
# ───────────────────────────────────────────────────────
"""Five staff searches, one rule: EVERY typed word must match SOME field.

RED FIRST (law 7): run against tip `91cd9c795` before the matcher existed, the
multi-word cases failed in all five places — "12 Oak 2B" returned nothing on
the Premises list, the Units list, the Move-in picker, the Premises picker and
the top bar, and "12 Oak" in the top bar's unit group returned no unit (see the
CR file §5a for the quoted failures).

⚠ WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a decoy that also
contains every word (then "found" proves nothing) — so each decoy is built to
LACK exactly one word; and a matcher that ORs the words instead of ANDing them
would find the decoy, which the decoy assertions catch.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.metering import address_picker, search_sources, selectors
from core import search as core_search
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _estate(actor, services=("electric", "water")):
    """Two buildings and a decoy, typed the way the PO's examples type them.

    The decoy has an "Apt 2B" too, but is NOT on Oak — so "12 Oak 2B" must
    leave it out, which is the AND half of the rule.
    """
    oak = make_premises(
        actor,
        address_line="12 Oak St",
        city="Ann Arbor",
        state="MI",
        postal_code="48104",
        services_available=list(services),
    )
    oak_1a = make_unit(actor, oak["id"], label="Apt 1A")
    oak_2b = make_unit(actor, oak["id"], label="Apt 2B")
    hemlock = make_premises(
        actor,
        address_line="2155 Hemlock Dr",
        city="Ann Arbor",
        state="MI",
        postal_code="48108",
        services_available=list(services),
    )
    hemlock_a = make_unit(actor, hemlock["id"], label="Unit A")
    decoy = make_premises(
        actor,
        address_line="40 Elm St",
        city="Katy",
        state="TX",
        postal_code="77494",
        services_available=list(services),
    )
    decoy_2b = make_unit(actor, decoy["id"], label="Apt 2B")
    return {
        "oak": oak["id"],
        "oak_1a": oak_1a["id"],
        "oak_2b": oak_2b["id"],
        "hemlock": hemlock["id"],
        "hemlock_a": hemlock_a["id"],
        "decoy": decoy["id"],
        "decoy_2b": decoy_2b["id"],
    }


# ── the five places, each read exactly as its endpoint reads it ────────────
def _premises_list(term):
    return {str(p.id) for p in selectors.premises_list(q=term)}


def _premises_picker(term):
    return {str(p.id) for p in address_picker.search(q=term)}


def _top_bar_premises(term):
    return {row["id"] for row in search_sources.search_premises(term, 50)}


def _units_list(term):
    rows, _total = selectors.units_page(ListParams(q=term, per=100))
    return {row["id"] for row in rows}


def _move_in_units(term):
    return {str(u.id) for u in selectors.move_in_unit_queryset(term)}


def _top_bar_units(term):
    return {row["id"] for row in search_sources.search_units(term, 50)}


PREMISES_SEARCHES = (_premises_list, _premises_picker, _top_bar_premises)
UNIT_SEARCHES = (_units_list, _move_in_units, _top_bar_units)


# ── S1 · the matcher itself ────────────────────────────────────────────────
def test_words_split_on_spaces_and_commas_and_drop_empties():
    assert core_search.search_words("  12 Oak,  2B ") == ["12", "Oak", "2B"]
    assert core_search.search_words("Ann Arbor, MI 48104") == ["Ann", "Arbor", "MI", "48104"]
    assert core_search.search_words("Hemlock") == ["Hemlock"]
    assert core_search.search_words("") == []
    assert core_search.search_words(None) == []


def test_one_word_is_exactly_matches_any():
    fields = ("address_line", "city")
    assert str(core_search.matches_every_word("heml", fields)) == str(
        core_search.matches_any("heml", fields)
    )


# ── T1 · the PO's examples ─────────────────────────────────────────────────
@pytest.mark.parametrize("search", UNIT_SEARCHES, ids=lambda f: f.__name__)
def test_12_oak_2b_finds_apt_2b_at_12_oak_st(brazos, marcus, search):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        found = search("12 Oak 2B")
        assert e["oak_2b"] in found
        assert e["oak_1a"] not in found  # "2B" is not in Apt 1A
        assert e["decoy_2b"] not in found  # the decoy is not on Oak


@pytest.mark.parametrize("search", PREMISES_SEARCHES, ids=lambda f: f.__name__)
def test_12_oak_2b_finds_the_building(brazos, marcus, search):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        found = search("12 Oak 2B")
        assert e["oak"] in found
        assert e["decoy"] not in found and e["hemlock"] not in found


@pytest.mark.parametrize("search", PREMISES_SEARCHES, ids=lambda f: f.__name__)
def test_street_and_town_find_the_premises(brazos, marcus, search):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        found = search("2155 Hemlock Ann Arbor")
        assert e["hemlock"] in found
        assert e["oak"] not in found  # Ann Arbor, but not Hemlock


@pytest.mark.parametrize("search", UNIT_SEARCHES, ids=lambda f: f.__name__)
def test_street_and_town_find_its_unit(brazos, marcus, search):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        found = search("2155 Hemlock Ann Arbor")
        assert e["hemlock_a"] in found
        assert e["oak_2b"] not in found


@pytest.mark.parametrize("search", UNIT_SEARCHES, ids=lambda f: f.__name__)
def test_a_unit_is_found_by_its_buildings_street_and_zip(brazos, marcus, search):
    """DEF-MET-10679: "12 Oak" in the top bar never returned Apt 2B."""
    with tenant_ctx(brazos):
        e = _estate(marcus)
        assert {e["oak_1a"], e["oak_2b"]} <= search("12 Oak")
        assert {e["oak_1a"], e["oak_2b"]} <= search("48104")
        assert e["decoy_2b"] not in search("48104")


@pytest.mark.parametrize("search", PREMISES_SEARCHES + UNIT_SEARCHES, ids=lambda f: f.__name__)
def test_one_word_is_unchanged(brazos, marcus, search):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        found = search("heml")
        assert found, "one partial word still finds"
        assert e["oak"] not in found and e["oak_2b"] not in found


def test_empty_term_is_unchanged(brazos, marcus):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        assert {e["oak"], e["hemlock"], e["decoy"]} <= _premises_list("")
        assert {e["oak"], e["hemlock"], e["decoy"]} <= _premises_picker("")
        assert {e["oak_2b"], e["hemlock_a"], e["decoy_2b"]} <= _units_list("")
        assert {e["oak_2b"], e["hemlock_a"], e["decoy_2b"]} <= _move_in_units("")
        assert search_sources.search_units("", 5) is not None


def test_whole_phrase_matches_still_match(brazos, marcus):
    """Nothing lost: a phrase that sat inside one field still finds it."""
    with tenant_ctx(brazos):
        e = _estate(marcus)
        for search in PREMISES_SEARCHES:
            assert e["oak"] in search("12 Oak St"), search.__name__
        for search in UNIT_SEARCHES:
            assert e["oak_2b"] in search("Apt 2B"), search.__name__


def test_premises_list_keeps_owner_and_parcel_fields(brazos, marcus):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        assert e["oak"] in _premises_list("Whitfield Oak")  # owner + street


# ── paging stays in SQL, one statement, no cap ─────────────────────────────
def test_units_list_pages_a_multi_word_search(brazos, marcus):
    with tenant_ctx(brazos):
        e = _estate(marcus)
        page1, total = selectors.units_page(ListParams(q="Ann Arbor", per=1, page=1))
        page2, _ = selectors.units_page(ListParams(q="Ann Arbor", per=1, page=2))
        page3, _ = selectors.units_page(ListParams(q="Ann Arbor", per=1, page=3))
        assert total == 3
        ids = [r["id"] for r in page1 + page2 + page3]
        assert set(ids) == {e["oak_1a"], e["oak_2b"], e["hemlock_a"]}


def test_each_search_is_one_sql_statement(brazos, marcus):
    with tenant_ctx(brazos):
        _estate(marcus)
        for label, run in (
            ("premises list", lambda: list(selectors.premises_list(q="12 Oak 2B"))),
            ("premises picker", lambda: list(address_picker.search(q="12 Oak 2B"))),
            ("move-in units", lambda: list(selectors.move_in_unit_queryset("12 Oak 2B"))),
            ("top bar premises", lambda: search_sources.search_premises("12 Oak 2B", 5)),
            ("top bar units", lambda: search_sources.search_units("12 Oak 2B", 5)),
        ):
            with CaptureQueriesContext(connection) as ctx:
                run()
            assert len(ctx.captured_queries) == 1, (label, [q["sql"] for q in ctx.captured_queries])


def test_top_bar_ranks_a_multi_word_term_on_its_first_word(brazos, marcus):
    """Ranking judgment (decision log 2026-10-29, lane A): the prefix band is
    decided by the FIRST word, so "12 Oak" puts a 12… premises number first."""
    with tenant_ctx(brazos):
        _estate(marcus)
        rows = search_sources.search_units("12 Oak", 5)
        assert len(rows) == 2


# ── T2 · the five places agree ─────────────────────────────────────────────
@pytest.mark.parametrize("term", ["12 Oak 2B", "2155 Hemlock Ann Arbor", "Ann Arbor 48104", "Oak"])
def test_the_five_places_agree(brazos, marcus, term):
    with tenant_ctx(brazos):
        _estate(marcus)
        premises = [s(term) for s in PREMISES_SEARCHES]
        units = [s(term) for s in UNIT_SEARCHES]
        assert premises[0] == premises[1] == premises[2], term
        assert units[0] == units[1] == units[2], term


# ── tenant isolation (hard rule 1) ─────────────────────────────────────────
def test_another_tenants_12_oak_is_never_found(brazos, marcus, lonestar, erin):
    with tenant_ctx(lonestar):
        theirs = _estate(erin, services=("water",))  # the isolation tenant is Water only
    with tenant_ctx(brazos):
        ours = _estate(marcus)
        for search in PREMISES_SEARCHES:
            found = search("12 Oak 2B")
            assert ours["oak"] in found and theirs["oak"] not in found, search.__name__
        for search in UNIT_SEARCHES:
            found = search("12 Oak 2B")
            assert ours["oak_2b"] in found and theirs["oak_2b"] not in found, search.__name__
