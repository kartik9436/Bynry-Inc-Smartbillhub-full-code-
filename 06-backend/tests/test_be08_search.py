# ── Trace ──────────────────────────────────────────────
# Component: BE-08 tests (core/search.py) — registration, grouping, cap, min-chars,
#            role omission, tenant-context law. Sources are fakes; live selector TCs
#            (incl. the mandatory US-SHL-003/TC-7 isolation probe) land with /search.
# ───────────────────────────────────────────────────────
"""BE-08 unit tests: sources register per entity, results come back grouped in
BR-SHL-005 order capped at 5, a short query runs nothing, role-invisible groups
vanish, and a tenant-less search is refused outright (BR-SHL-006)."""

import uuid

import pytest

from core import errors, permissions, search

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")


@pytest.fixture(autouse=True)
def clean_sources():
    search.clear_search_sources()
    yield
    search.clear_search_sources()


@pytest.fixture()
def in_tenant(monkeypatch):
    monkeypatch.setattr(search, "current_tenant_id", lambda: TENANT)


def rows_source(rows):
    return lambda q, limit: rows


# ── registration ────────────────────────────────────────────────────────────
def test_be08_tc01_sources_register_per_entity_and_replace():
    search.register_search_source("accounts", rows_source([{"id": 1}]))
    search.register_search_source("accounts", rows_source([{"id": 2}]))  # ONE per entity
    assert search.registered_entities() == ("accounts",)


def test_be08_tc02_empty_entity_key_refused():
    with pytest.raises(ValueError):
        search.register_search_source("", rows_source([]))


def test_be08_tc03_serving_order_is_br_shl_005_then_registration():
    """⚠ AMENDED 2026-09-03 — BR-SHL-005 grew from FOUR groups to NINE.

    PO, verbatim: *"Universal search will search premises , unit assets ,
    master, regular account , customer id, bill, payment, requests"*. The order
    asserted here is the PO's own sequence, not alphabetical and not the
    sidebar's, and it is the order a clerk meets the groups in on screen.
    """
    scrambled = (
        "payments",
        "bills",
        "accounts",
        "premises",
        "requests",
        "assets",
        "units",
        "master_accounts",
        "customers",
    )
    for entity in scrambled:
        search.register_search_source(entity, rows_source([{"e": entity}]))
    search.register_search_source("plans", rows_source([{"e": "plans"}]))  # future extra
    assert search.registered_entities() == (
        "premises",
        "units",
        "assets",
        "master_accounts",
        "accounts",
        "customers",
        "bills",
        "payments",
        "requests",
        "plans",  # an entity beyond the canonical set follows in REGISTRATION order
    )


def test_be08_tc03b_group_order_is_the_fifteen_the_po_named():
    """The canonical set itself, asserted as a set as well as a sequence.

    ⚠ This is the guard on the count. The ruling of 2026-09-03 says "eight" in
    its headline and ENUMERATES NINE (`DEF-3460`) — *"unit assets"* is one comma
    in the PO's sentence and two groups in the list. The list is the content and
    the number is a pointer to it, so the thing that runs is what settles it.

    ⚠ **SIX MORE ARRIVED ON 2026-09-05 (`CR-073`) AND APPEND AT 10–15 WITH
    NOTHING RENUMBERED** — PO, *"Extend universal search to include work order ,
    template, parts"*, then *"Don't add reads and finance - add work related
    items"*. Reads and finance were excluded BY NAME; seven further surfaces
    were considered and left out with reasons in `CR-073` §2a. The ORDER is
    asserted end to end in `tests/test_cr073_search_work_rating.py`, on a
    fixture that seeds all fifteen; this case owns the COUNT and the SET.
    """
    assert len(search.GROUP_ORDER) == 15
    assert set(search.GROUP_ORDER) == {
        "premises",
        "units",
        "assets",
        "master_accounts",
        "accounts",
        "customers",
        "bills",
        "payments",
        "requests",
        "work_orders",
        "work_order_templates",
        "parts",
        "workforce",
        "plans",
        "charges",
    }


# ── grouped search (US-SHL-003 shapes) ──────────────────────────────────────
def test_be08_tc04_results_grouped_in_canonical_order(in_tenant):
    search.register_search_source("payments", rows_source([{"confirmation": "PMT-88213"}]))
    search.register_search_source("accounts", rows_source([{"account_no": "A-10432"}]))
    results = search.search("A-104", role=permissions.SYSTEM_ADMIN)
    assert list(results) == ["accounts", "payments"]
    assert results["accounts"] == [{"account_no": "A-10432"}]


def test_be08_tc05_group_capped_at_five_even_when_a_source_over_returns(in_tenant):
    search.register_search_source("bills", rows_source([{"n": i} for i in range(9)]))
    results = search.search("BL-2608", role=permissions.BILLING_CLERK)
    assert len(results["bills"]) == search.GROUP_LIMIT == 5


def test_be08_tc06_limit_is_passed_to_the_source(in_tenant):
    seen = []
    search.register_search_source("accounts", lambda q, limit: seen.append((q, limit)) or [])
    search.search("Cedar", role=permissions.EXECUTIVE)
    assert seen == [("Cedar", 5)]  # sources need not over-fetch


def test_be08_tc07_empty_groups_are_omitted(in_tenant):
    search.register_search_source("accounts", rows_source([]))
    search.register_search_source("premises", rows_source([{"name": "Cedar Ridge Apartments"}]))
    results = search.search("Cedar", role=permissions.SYSTEM_ADMIN)
    assert list(results) == ["premises"]


def test_be08_tc08_zero_total_results_is_an_empty_dict(in_tenant):
    # US-SHL-003 TC-8: "No results for 'zzzz'." is the popover's rendering job.
    search.register_search_source("accounts", rows_source([]))
    assert search.search("zzzz", role=permissions.SYSTEM_ADMIN) == {}


# ── IS-3 minimum query (server-side half) ───────────────────────────────────
def test_be08_tc09_short_query_runs_no_source(in_tenant):
    called = []
    search.register_search_source("accounts", lambda q, limit: called.append(q) or [])
    assert search.search("A", role=permissions.SYSTEM_ADMIN) == {}  # TC-5: min 2 chars
    assert search.search("  ", role=permissions.SYSTEM_ADMIN) == {}
    assert search.search("", role=permissions.SYSTEM_ADMIN) == {}
    assert called == []


# ── role omission (BR-SHL-006) ──────────────────────────────────────────────
def test_be08_tc10_role_invisible_groups_are_omitted_entirely(in_tenant):
    search.register_search_source(
        "bills",
        rows_source([{"invoice_no": "BL-2608-018410"}]),
        visible_to=frozenset({permissions.SYSTEM_ADMIN}),
    )
    search.register_search_source("accounts", rows_source([{"account_no": "A-10432"}]))
    as_clerk = search.search("2608", role=permissions.BILLING_CLERK)
    assert "bills" not in as_clerk and list(as_clerk) == ["accounts"]
    as_admin = search.search("2608", role=permissions.SYSTEM_ADMIN)
    assert list(as_admin) == ["accounts", "bills"]


def test_be08_tc11_default_visibility_is_all_three_roles(in_tenant):
    # A4 addendum v1: every role sees every entity unless a source narrows it.
    search.register_search_source("accounts", rows_source([{"account_no": "A-10432"}]))
    for role in sorted(permissions.ROLES):
        assert search.search("A-104", role=role) != {}


# ── tenant law (BR-SHL-006 — no lawful tenant-less search) ──────────────────
def test_be08_tc12_no_tenant_context_refuses_with_auth_003(monkeypatch):
    monkeypatch.setattr(search, "current_tenant_id", lambda: None)
    search.register_search_source("accounts", rows_source([{"account_no": "A-10432"}]))
    with pytest.raises(errors.AuthError) as exc_info:
        search.search("A-104", role=permissions.SYSTEM_ADMIN)
    assert exc_info.value.code == errors.AUTH_TENANT_UNRESOLVABLE
    assert exc_info.value.br_ref == "BR-SHL-006"


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-08@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 12/12✔ (this file) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (B13 BE-08 row names meters; BR-SHL-005 does not)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
