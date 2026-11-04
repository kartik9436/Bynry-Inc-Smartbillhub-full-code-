# ── Trace ──────────────────────────────────────────────
# Question: OQ-306 CLOSED — PO 2026-10-02, verbatim: *"Allow several services at
#           once."* Shown: a clerk reviewing Water and Sewer schedules together.
# Rules:    BR-SHL-011 (`f.<name>` grammar — several values ride as ONE
#           comma-joined value) · IS-4 (OR within a dimension, AND across) ·
#           NFR-3 (the filter is applied in the query, before the page is cut)
# Impacts:  core/pagination.py `filter_values` / `parse_list_params` · every
#           list whose + Filter offers Service (rating plans / schedules /
#           charges / taxes, assets, units, reads, AR ageing, cost register,
#           work templates)
# ───────────────────────────────────────────────────────
"""OQ-306 — the service filter takes several values at once.

The shared filter bar sends `f.service=water,sewer`; the server splits it in ONE
place (`core.pagination.filter_values`) and every list applies `__in`. The
repeatable form `f.service=water&f.service=sewer` (which `billing/api.py` reads
for a run's scope) is folded into the same comma list by `parse_list_params`,
so both spellings mean the same thing.
"""

import pytest
from django.http import QueryDict

from apps.rating import selectors
from core.pagination import ListParams, filter_values, parse_list_params

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx


# ── the one splitter ─────────────────────────────────────────────────────────
def test_filter_values_splits_the_comma_list_in_order():
    assert filter_values("water,sewer") == ["water", "sewer"]
    assert filter_values("water") == ["water"]  # a single value is a list of one


def test_filter_values_reads_no_filter_as_empty_and_drops_blank_pieces():
    assert filter_values(None) == []
    assert filter_values("") == []  # the All chip — NOT "match nothing"
    assert filter_values(" water , ,sewer,water ") == ["water", "sewer"]
    assert filter_values(["water", "sewer,trash"]) == ["water", "sewer", "trash"]


def test_parse_list_params_folds_a_repeated_filter_into_the_comma_list():
    repeated = QueryDict("f.service=water&f.service=sewer&f.status=active")
    params = parse_list_params(repeated, allowed_filters=("service", "status"))
    assert params.filters == {"service": "water,sewer", "status": "active"}

    comma = QueryDict("f.service=water,sewer")
    assert parse_list_params(comma, allowed_filters=("service",)).filters == {
        "service": "water,sewer"
    }
    # A plain mapping (no `getlist`) is taken as it is.
    assert parse_list_params({"f.service": "water"}, allowed_filters=("service",)).filters == {
        "service": "water"
    }


# ── one list, end to end through its selector ───────────────────────────────
@pytest.mark.django_db
def test_charge_list_picking_water_and_sewer_shows_both_and_no_trash(env):
    env.enable("water", "sewer", "trash")
    env.charge("W-CONN", "Water connection", service="water")
    env.charge("S-CONN", "Sewer connection", service="sewer")
    env.charge("T-CART", "Trash cart", service="trash")

    def codes(service):
        params = ListParams(sort="code", dir="asc", filters={"service": service})
        with tenant_ctx(env.tenant):
            return [row["code"] for row in selectors.charge_list(params)]

    both = codes("water,sewer")
    assert "W-CONN" in both and "S-CONN" in both
    assert "T-CART" not in both
    # One value still narrows to one service, exactly as before the ruling.
    single = codes("water")
    assert "W-CONN" in single and "S-CONN" not in single and "T-CART" not in single
