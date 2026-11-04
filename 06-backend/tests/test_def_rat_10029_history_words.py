# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-010 (S9 History) · DEF-RAT-10029
# Rules:    B14 rule 31 (no database id is ever the visible value of a field) ·
#           BR-RAT-037 (append-only log, before/after) · hard rule 2 (money at
#           2 places, a unit price at up to 4)
# ───────────────────────────────────────────────────────
"""`DEF-RAT-10029` — Plans & Rates History showed database ids.

The PO's screenshots (City of Queen West, 2.562.0): WHO read a user uuid, the
CHANGE column read *account_type_id — → 01a0f27b-… and 89 more*, and Change
details dumped the plan as JSON. The plan-version publish stored no `before`,
so every fact read as changed.

These run the real write paths (a plan version that moves the minimum bill,
adds a tax and names customer classes; a rate schedule version that moves tier
1; a charge code reprice) and then read the History rows the screen draws.
"""

import json
import re
from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.rating import models, plan_writes, selectors, seams, services
from core.pagination import ListParams
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: date(2026, 10, 3))


def _world(env):
    env.enable("water")
    env.charge(
        "LATE", "Late payment fee", charge_type="penalty", amount_rule="percent_with_minimum",
        amount=None, percent="0.015", min_amount="5.00",
    )
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    tax = env.tax("State tax", rate="0.06")
    paper = env.charge("PAPER", "Paper bill fee", charge_type="recurring", amount="2.00")
    plan = env.plan(
        "Residential City Plan", "RCP", [{"service": "water", "tariff": schedule["id"]}],
        publish=True, minimum_bill_amount="10.00",
    )
    with tenant_ctx(env.tenant):
        classes = list(customer_models.AccountType.objects.order_by("name").values_list("id", "name")[:2])
        plan_writes.new_version(
            env.admin, plan["id"],
            {
                "effective_from": "2027-01-01", "reason": "Council resolution 14",
                "minimum_bill_amount": "12.00", "taxes": [{"tax": str(tax["id"])}],
                "details": {"customer_classes": [str(one) for one, _ in classes]},
                "publish": True,
            },
        )
        services.create_rate_schedule_version(
            env.admin, schedule["id"],
            {
                "name": "Res Water", "service": "water", "model": "tiered", "uom": "kgal",
                "effective_from": "2027-01-01",
                "structure": {"tiers": [{**RES_WATER_TIERS[0], "unit_price": "3.45"}, *RES_WATER_TIERS[1:]]},
                "reason": "Annual cost-of-service filing",
            },
        )
        services.update_charge(
            env.admin, paper["id"], {"amount": "5.00", "effective_from": "2000-01-01", "reason": "Print costs"}
        )
    return plan, classes


def _rows(env):
    with tenant_ctx(env.tenant):
        rows, _count = selectors.history_page(ListParams(sort="changed_at", dir="desc", page=1, per=50))
    return {row["entity_type"]: row for row in rows}


def _rendered(row):
    """Everything the History list and the Change details dialog print."""
    return json.dumps(
        {
            "who": row["actor"]["name"],
            "what": row["entity_name"],
            "reason": row["reason"],
            "changes": row["changes"],
            "published_by": row["published_by"]["name"],
        }
    )


def test_a_plan_version_publish_records_what_it_replaced(env):
    """RED at the tip: `plan_writes._publish` wrote `before=None`."""
    plan, _ = _world(env)
    with tenant_ctx(env.tenant):
        entry = models.RateChangeLog.objects.get(entity_type="plan", entity_id=plan["id"])
    assert entry.before is not None
    assert entry.before["minimum_bill_amount"] != entry.after["minimum_bill_amount"]


def test_no_database_id_reaches_the_history_words(env):
    """B14 rule 31 — RED at the tip, which served only `actor_user_id` and the
    raw snapshots."""
    _world(env)
    rows = _rows(env)
    assert set(rows) == {"plan", "schedule", "charge"}
    for row in rows.values():
        text = _rendered(row)
        assert not UUID.search(text), text
        assert row["actor"]["name"] == "Dana Whitfield"


def test_each_change_reads_field_by_field_in_a_clerks_words(env):
    _plan, classes = _world(env)
    rows = _rows(env)
    plan = [(c["field"], c["before"], c["after"]) for c in rows["plan"]["changes"]]
    assert ("Minimum bill", "$10.00", "$12.00") in plan
    assert ("Taxes", "None", "State tax") in plan
    assert ("Customer classes", "Every customer class", ", ".join(name for _, name in classes)) in plan
    # The plan's own unchanged facts are NOT listed (the PO's "and 89 more").
    assert len(plan) == 3, plan
    schedule = [(c["field"], c["before"], c["after"]) for c in rows["schedule"]["changes"]]
    assert ("Tier 1 · Rate", "$3.20", "$3.45") in schedule
    charge = [(c["field"], c["before"], c["after"]) for c in rows["charge"]["changes"]]
    assert charge == [("Amount", "$2.00", "$5.00")]


def test_a_row_with_no_before_lists_the_saved_values_and_never_a_uuid(env):
    """Rows already written with `before=None` (every plan publish until this
    fix) say what was saved, against `—` — not ninety changes."""
    plan, _ = _world(env)
    with tenant_ctx(env.tenant):
        entry = models.RateChangeLog.objects.get(entity_type="plan", entity_id=plan["id"])
        models.RateChangeLog.objects.filter(pk=entry.pk).update(before=None)
        # An id this tenant cannot name reads `—`, never the id.
        after = dict(entry.after, account_type_ids=["01a0f27b-3fdb-7000-8000-000000000000"])
        models.RateChangeLog.objects.filter(pk=entry.pk).update(after=after)
    row = _rows(env)["plan"]
    assert row["before_kept"] is False
    assert all(change["before"] == "—" for change in row["changes"])
    fields = [change["field"] for change in row["changes"]]
    assert "Name" in fields and "Minimum bill" in fields
    assert not UUID.search(_rendered(row)), _rendered(row)
