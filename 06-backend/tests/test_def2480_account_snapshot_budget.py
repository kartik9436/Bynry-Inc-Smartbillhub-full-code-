# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2480 — an imported account is snapshotted through the WHOLE
#           account-detail payload for its audit row, TWICE, on consecutive
#           lines. Re-measured by this lane on live PostgreSQL: the accounts
#           import LOAD cost 107.6 queries and 128 ms per row before, and 83.6
#           queries and 95 ms per row after — 24 queries a row, on both tiers.
#           1,048 accounts: 128.1 s before, 94.6 s after.
# Rules:    CLAUDE.md hard rule 7 (every money action writes `audit_log`, and
#           opening an account is one) · BR-CUS-047 · BR-MET-085/090/096
# Tests:    this file · 10-scripts/def2487_accounts_bar_benchmark.py (the
#           wall-clock half, which needs live PostgreSQL and a server)
# ───────────────────────────────────────────────────────
"""The per-account snapshot budget — the guard DEF-2480 asked for by name.

**WHY THE COST WAS INVISIBLE FOR AS LONG AS IT EXISTED.** Correctness was never
touched. The snapshot was accurate, the audit row was right, and every assertion
about either passed — so there was nothing for a functional test to catch. Every
import case in the suite walks 1 to 6 rows, where a hundred queries a row is a
few hundred queries and finishes instantly on in-memory SQLite. The same figure
at 1,048 rows is over a hundred thousand queries and two minutes, and it
surfaced only because a gunicorn worker was killed mid-write and the Python
frame at the kill named `account_row -> _ar_positions_for`.

**SO THIS FILE COUNTS RATHER THAN TIMES.** A count is vendor-independent and
runs on the default sqlite tier on every commit, which is the whole point: the
prevention this defect asked for was *"a per-row query budget on the import
loop, asserted at a few rows, [to] make the next regression of this shape fail
on the commit that causes it."* Timing cannot do that — the suite has no server
in front of it and no real engine under it.

TWO ASSERTIONS, AND THE FIRST IS THE ONE THAT MATTERS
────────────────────────────────────────────────────────────────────────────
The first counts how many times ONE account creation builds the detail payload,
and the answer is a hard **1**. That is precise, it is exactly the regression
that happened, and it cannot go red for an unrelated reason.

The second is a total query BUDGET with deliberate headroom. It exists to catch
the shape the first one cannot see — somebody adding a NEW expensive read to the
account-open path — and its number is generous on purpose, because a budget that
tracks the exact current figure goes red on every harmless change and gets
raised without being read.

⛔ **NEITHER OF THESE IS A LICENCE TO THIN THE AUDIT ROW.** Hard rule 7 makes
opening an account a money action that writes `audit_log`, and the after-blob is
the COMPLETE account-detail snapshot — that is the evidence, not the overhead.
What DEF-2480 removed was a second identical build of it on the next line. If a
future change makes this file red, the fix is to stop doing redundant work, never
to record less.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: One account, opened through the ordinary door. MEASURED on this tier, both
#: ways, rather than reasoned about:
#:
#:     before DEF-2480   64 queries
#:     after  DEF-2480   40 queries
#:
#: The same door on live PostgreSQL measures 73 -> 49 — the counts differ because
#: every `tenant_context` there also issues a `set_config` that counts, and the
#: DELTA is 24 on both tiers, which is the duplicate snapshot.
#:
#: The budget is 50 rather than 40: a budget pinned to today's exact figure goes
#: red on every harmless change and gets raised without being read, and a budget
#: with no headroom at all is that same failure with extra steps.
#:
#: ⚠ **IF THIS GOES RED, READ THE OTHER TEST FIRST.** A doubled snapshot shows up
#: there as an exact count and here as a vague overage, and only the first tells
#: you what happened.
ACCOUNT_OPEN_QUERY_BUDGET = 50


def _unit_with_plan(actor, tenant, label="Unit 1", services=("electric",)):
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    plan = rating_models.RatePlan.objects.filter(tenant_id=tenant.id, status="published").first()
    if plan is None:
        plan = rating_models.RatePlan.objects.create(
            tenant=tenant, name="Residential Standard", status="published"
        )
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    return unit


def _payload(unit_id):
    return {
        "unit_id": str(unit_id),
        "account_type": "residential",
        "opened_at": "2026-08-15",
    }


def test_def2480__opening_an_account_builds_the_detail_snapshot_exactly_once(
    brazos, marcus, monkeypatch
):
    """**THE REGRESSION, NAMED.** `_open_account` ended with two calls to
    `selectors.account_detail_dict(account)` on CONSECUTIVE LINES — one for the
    audit after-blob, one for the return value — with nothing mutating the
    account between them. One of the two was pure waste, and it measured at 24
    queries per imported row on live PostgreSQL: at 1,048 accounts that is about
    25,000 queries spent rebuilding a dict that had just been built, and 33.5
    seconds of a load that took 128.1.

    Counting the CALLS rather than the queries is deliberate. It is exact, it
    names the thing that went wrong, and it cannot go red because somebody added
    an index or a column somewhere else.

    ⛔ The audit row still receives the whole snapshot (hard rule 7). This
    asserts that it is BUILT once, never that it is RECORDED less.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)

        calls: list[str] = []
        original = customers_selectors.account_detail_dict

        def counting(account):
            calls.append(str(account.pk))
            return original(account)

        monkeypatch.setattr(customers_selectors, "account_detail_dict", counting)
        created = customers_services.create_account(marcus, _payload(unit["id"]))

    assert len(calls) == 1, (
        f"opening ONE account built the S18 detail payload {len(calls)} times. That payload "
        "is ~26 queries on live PostgreSQL — contacts, addresses, service agreements, meters "
        "through the assets seam, and the ledger's AR position — so a second build costs a "
        "full extra round of them per imported row. Build it once and hand it to both "
        "consumers; do NOT fix this by giving the audit row less (DEF-2480, hard rule 7)."
    )
    assert created["id"], "the account was still created — this guard is about cost, not writes"


def test_def2480__opening_an_account_stays_inside_its_query_budget(brazos, marcus):
    """The blunt half — a per-row budget on the account-open path.

    DEF-2480's own prevention asked for exactly this: *"A per-row query budget on
    the import loop, asserted at a few rows, would make the next regression of
    this shape fail on the commit that causes it."* It catches what the call
    count cannot — a NEW expensive read added to the path — and its headroom is
    deliberate, because a budget pinned to today's exact figure is one that gets
    raised without being read.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        with CaptureQueriesContext(connection) as captured:
            customers_services.create_account(marcus, _payload(unit["id"]))

    count = len(captured.captured_queries)
    assert count <= ACCOUNT_OPEN_QUERY_BUDGET, (
        f"opening ONE account now costs {count} queries, over the budget of "
        f"{ACCOUNT_OPEN_QUERY_BUDGET}. At test size that is invisible; the accounts import "
        f"walks this path once per row, so at 1,048 rows it is {count * 1048:,} queries. "
        "Find the new read before raising this number — and re-measure with "
        "10-scripts/def2487_accounts_bar_benchmark.py, which times it against the wall the "
        "request actually has to clear."
    )
