"""DEF-RAT-9738 — the move-in's Plan panel *Base charge* is the base of the
services THIS move-in starts, never the whole plan's (CR-171-BRC10, lane
MVI-WIZ-BILL, image 41).

Worked: a plan of Electric $12.00 + Water $8.00 a month. A move-in starting
Water only reads **$8.00 a month**; before the fix it read $20.00, because
`narrowed_sections` narrowed the services and kept the un-narrowed total.
"""

import pytest

from apps.rating import move_in_fees, plan_reads
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _line(service, flat):
    return {
        "service": service,
        "base": {"state": "ok", "flat_display": flat, "by_size": []},
        "minimum": {"by_size": []},
    }


def _sections(_plan_id, _on_date=None):
    services = [_line("electric", "12.00"), _line("water", "8.00")]
    return {
        "services": services,
        "base_total": plan_reads._base_total(services),
        "charge_codes": [],
        "taxes": [],
        "deposits": [],
        "discounts": [],
    }


def test_def_rat_9738__base_total_is_the_started_services_only(brazos, monkeypatch):
    monkeypatch.setattr(plan_reads, "plan_sections", _sections)
    with tenant_ctx(brazos):
        both = move_in_fees.narrowed_sections("plan", customer_class="residential", services=["electric", "water"])
        water = move_in_fees.narrowed_sections("plan", customer_class="residential", services=["water"])
    assert both["base_total"] == {"amount_display": "20.00", "unavailable": None}
    assert [line["service"] for line in water["services"]] == ["water"]
    assert water["base_total"] == {"amount_display": "8.00", "unavailable": None}


def test_signed_2026_10_06__water_only_base_is_8_not_20(brazos, monkeypatch):
    """⚖️ THE HUMAN SIGN-OFF OF 2026-10-06, statement 2's last sentence, asserted
    so drift goes red (PO verbatim: *"Money-file review: approve these six? - all
    good - go ahead"*; decision log *"SIX MOVE-IN MONEY FILES SIGNED"*). Shown:
    *"if a plan charges Electric $12.00 and Water $8.00 and Rosa takes water
    only, her base charge is $8.00 a month, not $20.00."*"""
    monkeypatch.setattr(plan_reads, "plan_sections", _sections)
    with tenant_ctx(brazos):
        water = move_in_fees.narrowed_sections(
            "plan", customer_class="residential", services=["water"]
        )
    assert water["base_total"]["amount_display"] == "8.00"
    assert water["base_total"]["amount_display"] != "20.00"
