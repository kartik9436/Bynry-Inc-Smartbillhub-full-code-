# ── Trace ──────────────────────────────────────────────
# Rule:     BR-RAT-090 (PO ruling 2026-08-20, option A — closes OQ-283).
#           CR-019: "in trash you have trash cans. they can be 1 or more at
#           customer locations, they are bill 1 trash can $15 - for example if
#           you have 3 you multiple by 3."
# Shape:    The chain's own TCs (test_cr013_resolution_chain.py) prove the
#           ARITHMETIC on supplied facts. These prove the FACTS are real — that
#           the count comes from assets on the unit and moves when the assets
#           move, which is the whole of option A. Option B (a typed quantity)
#           would pass every chain TC and fail every one of these.
# ───────────────────────────────────────────────────────
"""BR-RAT-090 — the cart count is OBSERVED, through assets' own read."""

from datetime import date

import pytest

from apps.rating import seams

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

JUNE_END = date(2026, 6, 30)


def test_br_rat_090__the_seam_reports_whether_it_is_WIRED_not_just_a_number(env):
    """Hard-won law 1, as a return shape. A bare `0` cannot tell 'this unit has
    no carts' from 'the read does not exist', and BR-RAT-090 bills on the first
    and refuses on the second — so the seam carries both facts."""
    with tenant_ctx(env.tenant):
        answer = seams.active_asset_count("00000000-0000-0000-0000-000000000000", "trash", JUNE_END)
    assert set(answer) == {"wired", "count"}
    # assets publishes the read today, so this is the WIRED branch. If a later
    # refactor moves or renames it, this goes red here rather than silently
    # billing every unmetered customer nothing.
    assert answer["wired"] is True


def test_br_rat_090__a_unit_with_no_assets_counts_zero_and_that_is_an_ANSWER(env):
    """Zero is a real fact: the utility looked and this unit has no carts. It
    is NOT the 'nobody looked' case, which the `wired` half carries."""
    with tenant_ctx(env.tenant):
        answer = seams.active_asset_count("00000000-0000-0000-0000-000000000000", "trash", JUNE_END)
    assert answer == {"wired": True, "count": 0}
