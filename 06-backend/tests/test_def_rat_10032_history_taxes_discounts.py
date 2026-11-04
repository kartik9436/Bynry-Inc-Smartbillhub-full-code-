# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-010 (S9 History) · S10 plan detail (Audit, Versions)
# Defects:  DEF-RAT-10032 (History lists no tax or discount change) ·
#           DEF-RAT-10033 (a plan's Audit tab does not say what a tax or
#           discount it uses changed) · DEF-RAT-10031 (a plan version's stored
#           copy held the terms it replaced)
# Rulings:  PO 2026-10-09 — *"(a) Show them on History too"*; *"but we should
#           show the changes in tax and discount on plan change history"*;
#           *"yes - old changes are not required (b) Fix it going forward only
#           - this is okay"*
# Rules:    B14 rule 31 (no database id on screen) · NFR-3 (one SQL page)
# ───────────────────────────────────────────────────────
"""Taxes and discounts on Plans & Rates History and on a plan's own history.

Every case writes through the product's own services — a tax's new rate from a
date (`new_tax_rate`, the only way a live tax's rate moves), a discount's new
value (`new_discount_value`), a plan's new version (`plan_writes.new_version`)
— and then reads exactly what the screens read. Run on PostgreSQL 16
(`--ds=config.settings.pgtest`): History is a SQL UNION and its count and page
must be taken in the database.
"""

import json
import re
from contextlib import contextmanager
from datetime import date

import pytest

from apps.rating import discount_services, models, plan_reads, plan_versioning, plan_writes, seams, selectors
from core.pagination import ListParams
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx
from tests.test_cr166_discounts_round2 import _discount

pytestmark = pytest.mark.django_db

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
FEE = "City Utility Franchise Fee 2%"


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 10, 3))


@contextmanager
def _real_audit_store():
    """The shared helpers capture audit rows in a list; History reads the STORED
    table in a SQL UNION, so the real store is put back while the world is
    written (the shape `test_cr167_plan_versions_pg` uses)."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    try:
        yield
    finally:
        core_audit.set_audit_sink(previous)


def _world(env):
    with _real_audit_store():
        return _write_world(env)


def _write_world(env):
    """Two published plans that both carry the franchise fee and the senior
    discount; then the fee goes 2% → 6% and the discount 15% → 20%."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    fee = env.tax(FEE, rate="0.02")
    with tenant_ctx(env.tenant):
        senior = _discount(env.admin, "SENIOR", value="15")
    plans = []
    for name, code in (("Municipal City Plan", "MCP"), ("Outside City Plan", "OCP")):
        plans.append(
            env.plan(
                name, code, [{"service": "water", "tariff": schedule["id"]}], publish=True,
                minimum_bill_amount="10.00", tax_rules=[{"tax": str(fee["id"])}],
                discounts=[{"discount": str(senior.id)}],
            )
        )
    with tenant_ctx(env.tenant):
        from apps.rating import services

        services.new_tax_rate(
            env.admin, fee["id"], {"rate": "0.06", "effective_from": "2026-11-01", "reason": "Council resolution 22"}
        )
        discount_services.new_discount_value(
            env.admin, senior.id, {"value": "20", "effective_from": "2026-11-01"}
        )
    return plans, senior


def _history(env, **filters):
    with tenant_ctx(env.tenant):
        return selectors.history_page(ListParams(sort="changed_at", dir="desc", page=1, per=50, filters=filters))


def _said(row):
    return [(c["field"], c["before"], c["after"]) for c in row["changes"]]


def _rendered(row):
    return json.dumps(
        {k: row.get(k) for k in ("actor", "entity_name", "reason", "changes", "published_by", "what")}
    )


def test_a_tax_rate_change_is_on_history_in_words(env):
    """RED at the tip: History read `rate_change_log` only."""
    _world(env)
    rows, count = _history(env, entity_type="tax")
    assert count == 1, rows
    (row,) = rows
    assert row["entity_type"] == "tax"
    assert row["entity_name"] == FEE
    # The figure leads: the list shows only the first change (*Rate: 2.00% → 6.00%*).
    assert _said(row)[0] == ("Rate", "2.00%", "6.00%"), _said(row)
    assert row["before_kept"] is True
    assert row["reason"] == "Council resolution 22"
    assert row["actor"]["name"] == "Dana Whitfield"
    assert not UUID.search(_rendered(row)), _rendered(row)


def test_a_discount_value_change_is_on_history_in_words(env):
    _world(env)
    rows, count = _history(env, entity_type="discount")
    said = [(row["entity_name"], change) for row in rows for change in _said(row)]
    assert ("Senior discount", ("Value", "15.00%", "20.00%")) in said, said
    for row in rows:
        assert row["entity_type"] == "discount"
        assert not UUID.search(_rendered(row)), _rendered(row)
    assert count == len(rows)


def test_history_is_one_sql_page_over_both_sources(env):
    """NFR-3 — the count is the whole union's and the page is cut in SQL."""
    _world(env)
    rows, count = _history(env)
    kinds = {row["entity_type"] for row in rows}
    assert {"tax", "discount"} <= kinds, kinds
    with tenant_ctx(env.tenant):
        first, total = selectors.history_page(ListParams(sort="changed_at", dir="desc", page=1, per=1))
        second, _ = selectors.history_page(ListParams(sort="changed_at", dir="desc", page=2, per=1))
    assert total == count and len(first) == 1 and len(second) == 1
    assert first[0]["id"] != second[0]["id"]
    for row in rows:
        assert not UUID.search(_rendered(row)), _rendered(row)


def test_each_plan_using_the_tax_and_discount_shows_their_change(env):
    """RED at the tip: the row said only *Edited*, and the new rate's row (a new
    tax row in the chain) was not this plan's at all."""
    plans, _senior = _world(env)
    for plan in plans:
        with tenant_ctx(env.tenant):
            rows = plan_reads.plan_audit_rows(list(plan_reads.plan_audit_queryset(plan["id"], "underneath")))
        said = [(row["what"]["kind"], row["what"]["name"], change) for row in rows for change in _said(row)]
        assert ("tax", FEE, ("Rate", "2.00%", "6.00%")) in said, said
        assert ("discount", "SENIOR · Senior discount", ("Value", "15.00%", "20.00%")) in said, said
        for row in rows:
            assert not UUID.search(_rendered(row)), _rendered(row)


def _publish_v2(env):
    """Municipal City Plan v1 $10.00 minimum; v2 from 01/01/2027 at $12.00."""
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    plan = env.plan(
        "Municipal City Plan", "MCP", [{"service": "water", "tariff": schedule["id"]}],
        publish=True, minimum_bill_amount="10.00",
    )
    with tenant_ctx(env.tenant):
        plan_writes.new_version(
            env.admin, plan["id"],
            {"effective_from": "2027-01-01", "reason": "Council resolution 14", "minimum_bill_amount": "12.00", "publish": True},
        )
    return plan


def test_v2_stores_its_own_minimum_and_versions_shows_the_change(env):
    """DEF-RAT-10031 — RED at the tip: v2's copy held $10.00."""
    env.enable("water")
    plan = _publish_v2(env)
    with tenant_ctx(env.tenant):
        v2 = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=2)
        assert v2.snapshot["minimum_bill_amount"] in ("12.000000", "12.0000", "12.00")
        assert v2.snapshot[plan_versioning.TERMS_RECORDED_KEY] is True
        windows = {row["version"]: row for row in plan_reads.plan_versions_windows(models.RatePlan.objects.get(pk=plan["id"]))}
    assert windows[2]["terms_recorded"] is True
    assert ("Minimum bill", "$10.00", "$12.00") in _said({"changes": windows[2]["change_words"]})
    assert windows[1]["change_words"] == [] and windows[1]["terms_recorded"] is True
    assert not UUID.search(json.dumps(windows[2]["change_words"]))


def test_an_old_version_copy_is_marked_not_claimed_unchanged(env):
    """A copy written before the fix is NOT rewritten (option (b)); the table
    marks it instead of reporting no change."""
    env.enable("water")
    plan = _publish_v2(env)
    with tenant_ctx(env.tenant):
        v2 = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=2)
        legacy = {k: v for k, v in v2.snapshot.items() if k != plan_versioning.TERMS_RECORDED_KEY}
        legacy["minimum_bill_amount"] = "10.000000"  # what `_publish` stored before the fix
        models.PlanVersion.objects.filter(pk=v2.pk).update(snapshot=legacy)
        windows = {row["version"]: row for row in plan_reads.plan_versions_windows(models.RatePlan.objects.get(pk=plan["id"]))}
        assert models.PlanVersion.objects.get(pk=v2.pk).snapshot == legacy  # the read rewrites nothing
    assert windows[2]["terms_recorded"] is False
    assert windows[2]["change_words"] == []
