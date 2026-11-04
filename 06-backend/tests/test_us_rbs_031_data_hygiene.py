# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-031 (EP-RBS-05) — CR-075 wave S, runbook 19.
# Rules:    BR-RBS-002 · BR-RBS-010 · BR-RBS-011 · BR-RBS-019 · BR-RBS-020 ·
#           BR-RBS-021 · BR-RBS-023 · BR-RBS-035 · BR-TEN-056 · BR-CUS-089 ·
#           BR-CUS-1010 · B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half — the real seams over a seeded
#           utility — is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/data_hygiene.py
# ───────────────────────────────────────────────────────
"""Runbook 19, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND TWO BRANCHES CAN BE PROVED NOWHERE ELSE.** On
the seeded utility every one of the 72 accounts is a sample record
(`BR-TEN-056`), so *an account with no contact channel*, *an account that cannot
be texted* and *a master account correctly anchored to a premises* have no real
rows to exercise them. Those live here. The figures the same runbook produces
against the real database are in the lane report and in the PostgreSQL file;
neither number is quoted without the other.
"""

import datetime as dt

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import data_hygiene as dh
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 7)


def _premises(premises_id="p1", label="12 Oak St", meters=(), points=(), is_sample=False, **rest):
    row = {
        "premises_id": premises_id,
        "label": label,
        "address_line": "12 Oak St",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "is_sample": is_sample,
        "unit_ids": ["u1"],
        "unit_labels": {"u1": "1"},
        "service_points": list(points),
        "meters": list(meters),
    }
    row.update(rest)
    return row


def _meter(asset_id="a1", asset_no="WM-01128", status="installed", is_sample=False):
    return {
        "asset_id": asset_id,
        "asset_no": asset_no,
        "category": "meters",
        "type_code": "water_meter",
        "status": status,
        "service_point_id": None,
        "is_sample": is_sample,
    }


def _account(account_id="acc1", account_no="A-10432", kind="regular", unit_id="u1", is_sample=False):
    return {
        "id": account_id,
        "account_no": account_no,
        "kind": kind,
        "unit_id": unit_id,
        "premises_id": "p1",
        "is_sample": is_sample,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the six reads runbook 19 makes.

    Everything defaults to a CLEAN utility with one account that can be reached
    every way, so a case that forgets to give the runbook something wrong cannot
    accidentally assert on a finding it never produced.
    """
    state = {
        "duplicates": {
            "groups": [],
            "customers_checked": 3,
            "customers_with_a_phone_token": 3,
            "customers_with_a_tax_id_token": 1,
            "emails_checked": 3,
        },
        "premises": [_premises(meters=[_meter()])],
        "orphans": [],
        "meters_answered": True,
        "accounts": [_account()],
        "channels": {
            "acc1": {
                "email": "e@x.test",
                "text": "555-0100",
                "post": "12 Oak St",
                "channels": ["email", "text", "post"],
            }
        },
        "opted_in": {"acc1": True},
    }
    monkeypatch.setattr(
        dh.customers_seam, "duplicate_customer_groups", lambda: dict(state["duplicates"])
    )
    monkeypatch.setattr(dh.customers_seam, "account_anchors", lambda: list(state["accounts"]))
    monkeypatch.setattr(
        dh.customers_seam,
        "contact_channels_for",
        lambda ids: {str(one): state["channels"].get(str(one), {}) for one in ids},
    )
    monkeypatch.setattr(
        dh.customers_seam,
        "accounts_opted_in_to_text",
        lambda ids: {str(one): bool(state["opted_in"].get(str(one))) for one in ids},
    )
    monkeypatch.setattr(
        dh.metering_seam,
        "premises_meter_census",
        lambda *, include_sample=True: {
            "premises": list(state["premises"]),
            "meters_answered": state["meters_answered"],
            "meters_without_a_service_point": list(state["orphans"]),
        },
    )
    monkeypatch.setattr(dh.tenancy_seam, "today", lambda: TODAY)
    return state


def _run(params=None):
    definition = dh.RUNBOOK
    ctx = executor.build_context(definition, tenant_id="t", run_id=None, params=params or {})
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _groups(result):
    return {
        row["cells"]["group"]["text"]: row["cells"]["items"]["text"]
        for row in _blocks(result)["breakdown"]["rows"]
    }


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_and_holds_no_ports_at_all(seams):
    """`BR-RBS-002` — the capability is ABSENT, not merely unused."""
    assert dh.RUNBOOK.is_check
    assert dh.RUNBOOK.ports == ()
    assert dh.RUNBOOK.writes_nothing()


def test_the_pinned_set_is_the_tenant_once(seams):
    """`BR-RBS-019` — the card's subject row reads *Tenant*."""
    result = _run()
    assert len(result.subjects) == 1
    assert result.subjects[0].subject_type == "tenant"
    # B14 rule 31 — the label a clerk reads is never the tenant's id.
    assert "t" != result.subjects[0].label
    assert "2026-09-07" in result.subjects[0].label


def test_every_step_is_a_set_step_and_there_are_seven(seams):
    """The card's own *Steps 7 · all read* and *Step modes: set*."""
    assert len(dh.RUNBOOK.steps) == 7
    assert {step.mode for step in dh.RUNBOOK.steps} == {"set"}
    assert not any(step.writes for step in dh.RUNBOOK.steps)


# ── step 1 · duplicates ───────────────────────────────────────────────────


def test_a_duplicate_group_is_a_finding_with_both_names(seams):
    seams["duplicates"]["groups"] = [
        {
            "matched_on": "tax_id",
            "count": 2,
            "group_key": "tax_id:1",
            "customers": [
                {"customer_id": "c1", "customer_no": "C-1", "name": "Marsh Farms", "is_sample": False},
                {"customer_id": "c2", "customer_no": "C-2", "name": "Marsh Farms LLC", "is_sample": False},
            ],
        }
    ]
    result = _run()
    assert _groups(result)["Duplicate customers"] == "1"
    item = [one for one in _run().set_results[dh.STEP_DUPLICATES]["items"]][0]
    assert item["label"] == "Marsh Farms · Marsh Farms LLC"
    assert item["detail"] == "Same tax id under 2 names."


def test_a_group_of_sample_customers_only_is_not_this_utilitys_problem(seams):
    """`BR-TEN-056` — the seeded set is deletable demo data, not their records."""
    seams["duplicates"]["groups"] = [
        {
            "matched_on": "tax_id",
            "count": 2,
            "group_key": "tax_id:1",
            "customers": [
                {"customer_id": "c1", "customer_no": "C-1", "name": "Sample Township", "is_sample": True},
                {"customer_id": "c2", "customer_no": "C-2", "name": "Sample Millworks", "is_sample": True},
            ],
        }
    ]
    result = _run()
    assert _groups(result)["Duplicate customers"] == "0"
    assert _checked(result, dh.STEP_DUPLICATES)["groups_that_are_all_sample_records"] == 1
    # ⚠ AND THE GROUP IT FOUND IS STILL COUNTED — a step that reported only the
    # findings would make "nothing here" and "everything here is sample data"
    # the same answer (hard-won law 7).
    assert _checked(result, dh.STEP_DUPLICATES)["groups_found"] == 1


def test_the_blind_spot_carries_its_number(seams):
    """*"0 duplicates"* over a tenant holding no tokens is not a clean result."""
    seams["duplicates"]["customers_with_a_phone_token"] = 0
    checked = _checked(_run(), dh.STEP_DUPLICATES)
    assert checked["customers_with_a_phone_token"] == 0
    assert checked["customers_checked"] == 3
    assert checked["matching_is"] == "equality on a blind index, never similarity"


# ── steps 2 and 3 · the orphans ───────────────────────────────────────────


def test_a_premises_with_a_service_point_and_no_meter_is_named_as_such(seams):
    seams["premises"] = [_premises(points=[{"id": "sp1", "unit_id": "u1", "service": "water"}])]
    result = _run()
    item = result.set_results[dh.STEP_PREMISES_NO_METER]["items"][0]
    assert item["detail"] == "1 service point(s) and no meter."
    assert _checked(result, dh.STEP_PREMISES_NO_METER)["of_those_with_a_service_point"] == 1


def test_a_premises_with_no_service_point_reads_differently(seams):
    """A subdivision under construction is not a connection nobody can read."""
    seams["premises"] = [_premises()]
    item = _run().set_results[dh.STEP_PREMISES_NO_METER]["items"][0]
    assert item["detail"] == "No service point and no meter."


def test_a_meter_in_the_store_room_is_not_a_finding(seams):
    """`BR-AST-005`'s `uninstalled` — a spare meter stands on nothing, lawfully."""
    seams["orphans"] = [
        _meter("a1", "WM-1", status="uninstalled"),
        _meter("a2", "WM-2", status="installed"),
    ]
    result = _run()
    checked = _checked(result, dh.STEP_METERS_NO_PREMISE)
    assert checked["in_stock_and_not_a_finding"] == 1
    assert _groups(result)["Meters with no premise"] == "1"


def test_an_unanswered_meter_census_is_not_read_as_no_meters(seams):
    """`DEF-075`'s shape: `None` read as *this module has nothing*."""
    seams["meters_answered"] = False
    assert _checked(_run(), dh.STEP_PREMISES_NO_METER)["meters_answered"] is False


# ── step 4 · accounts with no unit ────────────────────────────────────────


def test_a_master_account_anchored_to_a_premises_is_not_broken(seams):
    """`BR-CUS-1010` — a Master Account names a premises and NO unit, lawfully.

    ⚠ **THIS CASE IS THE ONE THAT WOULD HAVE GONE WRONG QUIETLY.** A check that
    counted every account without a unit reports every master account in the
    utility as broken, every month — which is how a hygiene report teaches a
    clerk to ignore it, and nothing in the suite would have said so.
    """
    seams["accounts"] = [
        _account("m1", "M-1", kind="master", unit_id=None),
        _account("r1", "A-2", kind="regular", unit_id=None),
    ]
    seams["channels"] = {
        "m1": {"email": "e@x.test", "text": "5", "post": "x", "channels": ["email", "text", "post"]},
        "r1": {"email": "e@x.test", "text": "5", "post": "x", "channels": ["email", "text", "post"]},
    }
    seams["opted_in"] = {"m1": True, "r1": True}
    result = _run()
    checked = _checked(result, dh.STEP_ACCOUNTS_NO_UNIT)
    assert checked["master_accounts_anchored_to_a_premises"] == 1
    assert checked["accounts_with_no_unit"] == 1
    assert _groups(result)["Accounts with no unit"] == "1"


# ── step 5 · who can be reached ───────────────────────────────────────────


def test_no_channel_at_all_and_no_mobile_are_different_groups(seams):
    """Three absences, three fixes — the card keeps the first two apart."""
    seams["accounts"] = [_account("a1", "A-1"), _account("a2", "A-2")]
    seams["channels"] = {
        "a1": {"email": None, "text": None, "post": None, "channels": []},
        "a2": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]},
    }
    seams["opted_in"] = {}
    groups = _groups(_run())
    assert groups["No contact channel at all"] == "1"
    assert groups["No mobile, or not opted in"] == "1"


def test_a_mobile_with_no_opt_in_is_named_as_an_opt_in_problem(seams):
    """`accounts.sms_reminders` is an election, and its own sentence says so."""
    seams["opted_in"] = {"acc1": False}
    result = _run()
    item = result.set_results[dh.STEP_NO_CHANNEL]["items"][0]
    assert item["detail"] == "Mobile on file · not opted in to texts."
    assert _checked(result, dh.STEP_NO_CHANNEL)["reachable_by_text"] == 0


def test_reachable_by_text_needs_both_a_mobile_and_an_opt_in(seams):
    assert _checked(_run(), dh.STEP_NO_CHANNEL)["reachable_by_text"] == 1
    tiles = {one["id"]: one["value"]["text"] for one in _blocks(_run())["kpis"]["tiles"]}
    assert tiles["reachable_by_text"] == "1 of 1"


def test_a_utility_with_no_records_of_its_own_never_reads_zero_of_zero(seams):
    """⚠ **THIS SHIPPED FOR ONE RUN AND THE REAL DATABASE CAUGHT IT.**

    On the seeded utility every account is a sample record, so the verdict read
    *"0 of 0 accounts cannot be reached by text"* — arithmetically true, and it
    reads as a fault where the fact is that there is nothing of the utility's
    own to look at. A ratio needs a denominator.
    """
    seams["accounts"] = []
    seams["channels"] = {}
    blocks = _blocks(_run())
    assert "0 of 0" not in blocks["verdict"]["detail"]
    assert blocks["verdict"]["detail"].startswith("No accounts of this utility's own to check yet.")
    tiles = {one["id"]: one for one in blocks["kpis"]["tiles"]}
    assert tiles["reachable_by_text"]["value"]["text"] == "—"
    assert tiles["reachable_by_text"]["detail"] == "No accounts of this utility's own yet"


# ── step 6 · addresses ────────────────────────────────────────────────────


def test_an_incomplete_address_is_a_finding_and_names_what_is_missing(seams):
    seams["premises"] = [_premises(meters=[_meter()], city="", postal_code=None)]
    result = _run()
    item = result.set_results[dh.STEP_ADDRESSES]["items"][0]
    assert item["detail"] == "No city, no postal code on the premises."
    assert _groups(result)["Addresses not standardised"] == "1"


def test_nothing_claims_a_standardiser_refused_an_address(seams):
    """`13-selector-inventory.md` **S-8** is ABSENT and the step says so.

    Inventing that verdict would be a check reporting a judgment nobody made.
    """
    checked = _checked(_run(), dh.STEP_ADDRESSES)
    assert checked["addresses_a_standardiser_refused"] == 0
    assert checked["no_address_service_is_connected"] is True


# ── step 7 and the report ─────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_groups_keep_the_cards_order_and_a_clean_group_is_kept(seams):
    """A group that disappears when it is clean is one a clerk cannot see winning."""
    rows = [row["cells"]["group"]["text"] for row in _blocks(_run())["breakdown"]["rows"]]
    assert rows == [dh.GROUP_FACTS[name]["label"] for name in dh.GROUP_ORDER]
    assert len(rows) == 7


def test_the_orphan_tile_and_the_orphan_rows_add_up(seams):
    """`RB-119`: *the tables on the screens add up to them*."""
    seams["premises"] = [_premises()]
    seams["orphans"] = [_meter("a9", "WM-9")]
    seams["accounts"] = [_account("r1", "A-2", unit_id=None)]
    seams["channels"] = {
        "r1": {"email": "e@x.test", "text": "5", "post": "x", "channels": ["email", "text", "post"]}
    }
    seams["opted_in"] = {"r1": True}
    result = _run()
    tiles = {one["id"]: one["value"]["text"] for one in _blocks(result)["kpis"]["tiles"]}
    groups = _groups(result)
    assert tiles["orphans"] == "3"
    assert (
        int(groups["Premises with no meter"])
        + int(groups["Meters with no premise"])
        + int(groups["Accounts with no unit"])
        == 3
    )


def test_the_action_is_disabled_with_its_reason_and_the_reason_is_short(seams):
    """B14 — a control a user may not use is drawn disabled WITH its reason
    (`DEF-SHL-4043`), and rule 33 caps a refusal at five or six words."""
    action = _blocks(_run())["action"]
    assert action["enabled"] is False
    assert action["reason"] == "The work list is not built yet"
    assert len(action["reason"].split()) <= 7


def test_no_rule_id_and_no_database_id_reaches_a_drawn_cell(seams):
    """B14 rules 31 and 32."""
    seams["accounts"] = [_account("01a0-uuid-account", "A-1", unit_id=None)]
    seams["channels"] = {"01a0-uuid-account": {"email": None, "text": None, "post": None, "channels": []}}
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            drawn = " ".join(
                str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
            )
            assert "BR-" not in drawn
            assert "RB-" not in drawn
            assert "01a0-uuid-account" not in drawn


def test_every_finding_names_a_fix_route(seams):
    """`BR-RBS-011` — a failure with no route is a defect in the runbook."""
    for row in _blocks(_run())["breakdown"]["rows"]:
        assert row["cells"]["fix"]["kind"] == "link"
        assert row["cells"]["fix"]["to"]
        assert row["cells"]["fix"]["label"].endswith("→")


def test_the_verdict_says_clean_only_when_there_is_nothing_to_fix(seams):
    assert _blocks(_run())["verdict"]["word"] == "Clean"
    seams["orphans"] = [_meter()]
    assert _blocks(_run())["verdict"]["word"] == "To fix"
