# ── Trace ──────────────────────────────────────────────
# Component: BE-05 tests (core/pagination.py) — clamp semantics, BR-SHL-011 grammar,
#            never-error paging. Uses DRF request factory over plain lists; no DB.
# ───────────────────────────────────────────────────────
"""BE-05 unit tests: the one page-size vocabulary (50/100/200/500/1000, default
50 — PO 2026-08-09) and the fall-back-or-clamp law (BR-SHL-011: a list URL can
never error over its params)."""

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core import pagination


def drf_request(query_string=""):
    return Request(APIRequestFactory().get(f"/api/things?{query_string}"))


# ── per clamps to the set (A11 r2 item 1) ───────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 50),  # absent → default
        ("", 50),
        ("abc", 50),  # non-numeric → default, never an error
        ("50", 50),
        (100, 100),
        (200, 200),
        (500, 500),
        (1000, 1000),  # every member of the set passes through
        (75, 50),  # between steps → clamp DOWN (never more rows than asked)
        (300, 200),
        (999, 500),
        (5000, 1000),  # above the top → top
        (10, 50),  # below the bottom → bottom
        (0, 50),
        (-5, 50),
    ],
)
def test_be05_tc01_per_clamps_to_the_set(raw, expected):
    assert pagination.clamp_page_size(raw) == expected


def test_be05_tc02_the_vocabulary_is_the_po_ruling():
    assert pagination.PAGE_SIZES == (50, 100, 200, 500, 1000)
    assert pagination.DEFAULT_PAGE_SIZE == 50


# ── StandardPagination over a queryset-like list ────────────────────────────
def test_be05_tc03_default_page_is_50_rows():
    paginator = pagination.StandardPagination()
    page = paginator.paginate_queryset(list(range(250)), drf_request())
    assert page == list(range(50))


def test_be05_tc04_per_param_drives_page_size():
    paginator = pagination.StandardPagination()
    page = paginator.paginate_queryset(list(range(250)), drf_request("per=100"))
    assert len(page) == 100
    page = paginator.paginate_queryset(list(range(250)), drf_request("per=999"))
    assert len(page) == 250  # 999 clamped to 500 → the 250 rows fit on one page


def test_be05_tc05_page_param_pages_through():
    paginator = pagination.StandardPagination()
    page = paginator.paginate_queryset(list(range(250)), drf_request("page=2"))
    assert page == list(range(50, 100))


def test_be05_tc06_invalid_or_out_of_range_page_never_errors():
    # BR-SHL-011: fall back or clamp, never error (DRF's default would 404).
    paginator = pagination.StandardPagination()
    assert paginator.paginate_queryset(list(range(120)), drf_request("page=junk"))[0] == 0
    last = pagination.StandardPagination().paginate_queryset(
        list(range(120)), drf_request("page=999")
    )
    assert last == list(range(100, 120))  # clamped to the last page
    first = pagination.StandardPagination().paginate_queryset(
        list(range(120)), drf_request("page=-3")
    )
    assert first[0] == 0


def test_be05_tc07_response_envelope_is_count_next_previous_results():
    paginator = pagination.StandardPagination()
    paginator.paginate_queryset(list(range(120)), drf_request("page=1"))
    body = paginator.get_paginated_response(list(range(50))).data
    assert set(body.keys()) == {"count", "next", "previous", "results"}
    assert body["count"] == 120


# ── parse_list_params (BR-SHL-011 grammar) ──────────────────────────────────
def test_be05_tc08_defaults_when_nothing_supplied():
    params = pagination.parse_list_params({}, allowed_sorts=("name",), default_sort="name")
    assert params == pagination.ListParams(sort="name")


def test_be05_tc09_declared_values_parse_through():
    params = pagination.parse_list_params(
        {
            "q": "  reed ",
            "sort": "balance",
            "dir": "desc",
            "page": "3",
            "per": "200",
            "f.status": "active",
            "f.class": "residential",
        },
        allowed_sorts=("name", "balance"),
        default_sort="name",
        allowed_filters=("status", "class"),
    )
    assert params.q == "reed"  # trimmed
    assert params.sort == "balance" and params.dir == "desc"
    assert params.page == 3 and params.per == 200
    assert params.filters == {"status": "active", "class": "residential"}


def test_be05_tc10_unknown_sort_falls_back_unknown_dir_falls_back():
    params = pagination.parse_list_params(
        {"sort": "password_hash", "dir": "sideways"},
        allowed_sorts=("name",),
        default_sort="name",
    )
    assert params.sort == "name"  # undeclared sort can never reach a query
    assert params.dir == "asc"


def test_be05_tc11_undeclared_filters_are_ignored_never_queried():
    params = pagination.parse_list_params(
        {"f.status": "active", "f.tenant_id": "someone-else", "f.is_admin": "true"},
        allowed_filters=("status",),
    )
    assert params.filters == {"status": "active"}  # client-picked columns dropped


def test_be05_tc12_garbage_page_and_per_fall_back():
    params = pagination.parse_list_params({"page": "zero", "per": "lots"})
    assert (params.page, params.per) == (1, 50)
    params = pagination.parse_list_params({"page": "-9", "per": "5000"})
    assert (params.page, params.per) == (1, 1000)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-05@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest 26/26✔ (this file) · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
