# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 P1.16 — *See full rates* narrowed to this move-in
#          (image 42) and the three reads of the Billing step; DEF-RAT-9708
#          (unit prices at up to four places). Lane MVI-MONEY.
# Rules:   BR-RAT-108 (class reach) · PO 2026-10-02 (*"Show unit prices with up
#          to 4 decimals and keep every total at 2."*) · OQ-BIL-12788 (a)
# ───────────────────────────────────────────────────────
"""The narrowed read, the three routes, and a unit price at four places."""


from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.urls import resolve

from apps.customers import move_fees, move_in_money_api
from apps.rating import move_in_fees, plan_reads, selectors
from tests.test_cr171_p1_12_move_in_fees import _world
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import FakeUser, api_call, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_p1_16__the_three_routes_resolve_to_this_module():
    for route, view in (
        ("/api/brazosbend/move-ins/fees", move_in_money_api.move_in_fees),
        ("/api/brazosbend/move-ins/fees/quote", move_in_money_api.move_in_fee_quote),
        ("/api/brazosbend/move-ins/pricing", move_in_money_api.move_in_pricing),
    ):
        assert resolve(route).func is view, route


def test_p1_16__the_fees_route_answers_the_locked_rows(brazos, dana):
    with tenant_ctx(brazos):
        unit, _plan, _out = _world(dana, brazos)
        response = api_call(
            move_in_money_api.move_in_fees,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            query={"unit_id": str(unit["id"]), "account_type": "residential"},
        )
    assert response.status_code == 200, response.data
    assert [row["code"] for row in response.data["rows"]] == ["DEPOSIT", "CONN"]
    assert response.data["total"] == "175.0000"


def test_p1_16__a_missing_unit_or_category_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        response = api_call(
            move_in_money_api.move_in_pricing, "get", user=FakeUser(), role="billing_clerk", tenant=brazos, query={}
        )
    assert response.status_code == 422
    fields = [row["field"] for row in response.data["field_errors"]]
    assert fields == ["unit_id", "account_type"]


def test_p1_16__pricing_is_narrowed_to_the_class_and_states_no_fee_is_taxed(brazos, dana):
    """One move-in starting only ELECTRIC narrows the services too."""
    with tenant_ctx(brazos):
        unit, _plan, _out = _world(dana, brazos)
        answer = move_fees.move_in_pricing(unit["id"], "residential")
    assert answer["plan"] is not None
    assert answer["plan"]["narrowed_to"]["customer_class"] == "residential"
    started = answer["services"]
    assert "electric" in started
    assert answer["plan"]["narrowed_to"]["services"] == sorted(started)
    assert all(line["service"] in started for line in answer["plan"]["services"])
    assert [row["code"] for row in answer["fees"]["rows"]] == ["DEPOSIT", "CONN"]
    assert answer["deposit"]["amount"] == "150.0000"
    assert answer["move_in_fees_taxed"] is False
    assert all(tax["move_in_fees_taxed"] is False for tax in answer["plan"]["taxes"])
    assert sorted(row["service"] for row in answer["assets"]) == sorted(started)


def test_p1_16__a_charge_code_for_another_class_is_not_shown(brazos, dana, monkeypatch):
    rows = [
        {"ref": {"id": "a"}, "code": "RES"},
        {"ref": {"id": "b"}, "code": "COM"},
        {"ref": {"id": "c"}, "code": "ALL"},
    ]
    monkeypatch.setattr(
        plan_reads,
        "plan_sections",
        lambda plan_id, as_of=None: {"services": [], "charge_codes": rows, "taxes": []},
    )

    class _Charges:
        def filter(self, **_kw):
            return [
                SimpleNamespace(id="a", applies_to_customer_classes=["residential"]),
                SimpleNamespace(id="b", applies_to_customer_classes=["commercial"]),
                SimpleNamespace(id="c", applies_to_customer_classes=[]),
            ]

    monkeypatch.setattr(move_in_fees.models.Charge, "objects", _Charges())
    with tenant_ctx(brazos):
        narrowed = move_in_fees.narrowed_sections("plan", customer_class="residential")
    assert [row["code"] for row in narrowed["charge_codes"]] == ["RES", "ALL"]


def test_p1_16__the_base_table_keeps_this_connections_size_only(brazos, monkeypatch):
    sections = {
        "services": [
            {
                "service": "water",
                # `state` / `flat_display` as `plan_reads.plan_sections` always
                # serves them — `base_total` is now recomputed over the
                # narrowed lines (DEF-RAT-9738), which reads both.
                "base": {"state": "ok", "flat_display": None, "by_size": [
                    {"size_class": "W-58", "customer_class": None, "amount_display": "12.00"},
                    {"size_class": "W-2", "customer_class": None, "amount_display": "64.00"},
                ]},
                "minimum": {"by_size": []},
            },
            {"service": "gas", "base": {"state": "ok", "flat_display": None, "by_size": []}, "minimum": {"by_size": []}},
        ],
        "charge_codes": [],
        "taxes": [],
    }
    monkeypatch.setattr(plan_reads, "plan_sections", lambda plan_id, as_of=None: sections)
    with tenant_ctx(brazos):
        narrowed = move_in_fees.narrowed_sections(
            "plan", customer_class=None, size_by_service={"water": "W-2"}, services=["water"]
        )
    assert [line["service"] for line in narrowed["services"]] == ["water"]
    assert narrowed["services"][0]["base"]["by_size"] == [
        {"size_class": "W-2", "customer_class": None, "amount_display": "64.00"}
    ]
    # DEF-RAT-9738 — and the Base charge is this connection's, not the plan's.
    assert narrowed["base_total"]["amount_display"] == "64.00"


# ── DEF-RAT-9708 — a unit price reads at up to four places ────────────────
def test_def_rat_9708__a_four_place_tier_price_reads_at_four_places(brazos, monkeypatch):
    """Red first on 2.526.0: `$8.94 per kgal` for an $8.9375 tier."""
    monkeypatch.setattr(
        selectors,
        "version_structure",
        lambda version: {
            "unit": "kgal",
            "tiers": [
                {"from_qty": "0", "to_qty": "5", "from_qty_display": "0", "to_qty_display": "5",
                 "unit_price": Decimal("8.937500")},
                {"from_qty": "5", "to_qty": None, "from_qty_display": "5", "unit_price": Decimal("0.042500")},
            ],
        },
    )
    version = SimpleNamespace(model="tiered", tariff=SimpleNamespace(service=SimpleNamespace(code="water")))
    with tenant_ctx(brazos):
        usage = plan_reads._usage(version)
    assert [row["rate_display"] for row in usage["rows"]] == ["$8.9375 per kgal", "$0.0425 per kgal"]
    assert [row["rate_amount"] for row in usage["rows"]] == ["$8.9375", "$0.0425"]
    # Totals stay at two places — the base is still `_money_words`.
    with tenant_ctx(brazos):
        assert plan_reads._money_words(Decimal("12.5")) == "$12.50"


def test_p1_16__only_the_ticked_services_are_shown(brazos, dana):
    with tenant_ctx(brazos):
        unit, _plan, _out = _world(dana, brazos)
        answer = move_fees.move_in_pricing(unit["id"], "residential", services=["electric"])
    assert answer["services"] == ["electric"]
    assert [row["service"] for row in answer["assets"]] == ["electric"]
    assert answer["plan"]["narrowed_to"]["services"] == ["electric"]
