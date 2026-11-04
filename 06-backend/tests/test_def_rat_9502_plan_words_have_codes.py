"""DEF-RAT-9502 — the plan screens' server-composed words carry the CODES behind
them, so each of the eleven catalogues can word them.

CR-167-BRC10 §7.6 had the server send finished English words — the usage
table's heading and rows (*Over 1000 kWh*, *Each month*, *Energy*, *$0.11 per
kWh*), *Everyone* in a price row, *Usage and base charges*, and the Audit
column (*Starts: 01/01/2027*, *Status: draft*). A German clerk read them in
English on every plan screen, and no catalogue check could see it because no
catalogue held them. The English stays (the CSV and older readers use it);
these tests pin the codes a screen needs beside it.

Pure functions only — no database is needed to say what words a row carries.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.rating import plan_reads


def _version(structure: dict, model: str = "tiered", service: str = "electric") -> SimpleNamespace:
    return SimpleNamespace(model=model, structure=structure, tariff=SimpleNamespace(service=SimpleNamespace(code=service)))


@pytest.fixture
def structure_of(monkeypatch):
    def use(structure: dict) -> None:
        monkeypatch.setattr(plan_reads.selectors, "version_structure", lambda version: structure)
        # Size names are reference data read under a tenant; none of these rows has a size.
        monkeypatch.setattr(plan_reads, "_size_names", lambda codes: {})
        monkeypatch.setattr(plan_reads.seams, "tenant_currency", lambda: "USD")

    return use


def test_block_rows_name_over_and_each_month_and_split_the_rate(structure_of):
    structure_of(
        {
            "unit": "kWh",
            "tiers": [
                {"from_qty": "0", "to_qty": "500", "from_qty_display": "0 kWh", "to_qty_display": "500 kWh", "unit_price": "0.11"},
                {"from_qty": "500", "to_qty": None, "from_qty_display": "500 kWh", "unit_price": "0.14"},
            ],
        }
    )
    usage = plan_reads._usage(_version({}))
    first, over = usage["rows"]
    assert first["label_key"] is None  # *0 kWh – 500 kWh* is numbers and units, worded nowhere
    assert first["rate_amount"] == "$0.11" and first["rate_unit"] == "kWh"
    assert over["label"] == "Over 500 kWh"  # the English stays for the CSV
    assert over["label_key"] == "over" and over["label_args"] == {"qty": "500 kWh"}


def test_flat_month_demand_and_share_rows_carry_their_keys(structure_of):
    structure_of({"unit": "kWh", "tiers": [{"from_qty": "0", "to_qty": None, "unit_price": "14.00"}]})
    assert plan_reads._usage(_version({}, model="flat"))["rows"][0]["label_key"] == "eachMonth"

    structure_of({"unit": "kWh", "demand": {"energy_rate_per_kwh": "0.08", "demand_rate_per_kw": "9.50"}})
    energy, demand = plan_reads._usage(_version({}, model="demand"))["rows"]
    assert (energy["label_key"], demand["label_key"]) == ("energy", "demand")
    assert (demand["rate_amount"], demand["rate_unit"]) == ("$9.50", "kW")

    structure_of({"percent": Decimal("40"), "basis_service": "water"})
    share = plan_reads._usage(_version({}, model="percent_of_service", service="sewer"))["rows"][0]
    assert share["label_key"] == "share" and share["label_args"] == {"service": "water"}


def test_audit_facts_name_the_field_and_keep_dates_status_and_yes_no_as_codes():
    before = {"status": "draft", "budget_billing": False, "effective_from": "2026-08-01"}
    after = {"status": "published", "budget_billing": True, "effective_from": "2027-01-01"}
    old, new, more = plan_reads.words_facts(before, after)
    assert more == 0
    assert [fact["key"] for fact in new] == ["budget_billing", "effective_from", "status"]
    by_key = {fact["key"]: fact for fact in new}
    assert by_key["budget_billing"]["kind"] == "bool" and by_key["budget_billing"]["raw"] is True
    assert by_key["effective_from"]["kind"] == "date" and by_key["effective_from"]["raw"] == "2027-01-01"
    assert by_key["status"]["kind"] == "status" and by_key["status"]["raw"] == "published"
    assert {fact["key"]: fact["raw"] for fact in old}["status"] == "draft"


def test_audit_facts_count_what_they_do_not_list():
    _, new, more = plan_reads.words_facts({}, {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"})
    assert len(new) == 3 and more == 2


def test_what_is_taxed_is_served_as_codes():
    tax = SimpleNamespace(base_includes_usage=True, base_includes_base=True)
    assert plan_reads._taxed_codes(tax) == ["usage", "base"]
    assert plan_reads._taxed_codes(SimpleNamespace(base_includes_usage=False, base_includes_base=True)) == ["base"]


def test_audit_facts_read_the_same_view_as_the_english_and_word_an_empty_list():
    """The English (`words_diff`) and the codes (`words_facts`) describe ONE
    change: an empty list is the product's *None* (kind `none`), and both
    sides list the same fields."""
    before = {"discounts": [], "minimum_bill_amount": None}
    after = {"discounts": [{"code": "SENIOR", "name": "Senior"}], "minimum_bill_amount": None}
    old, new, _ = plan_reads.words_facts(before, after)
    assert old[0]["kind"] == "none" and old[0]["key"] == "discounts"
    assert new[0]["kind"] == "text" and new[0]["value"] == "Senior"
    english_before, _ = plan_reads.words_diff(before, after)
    assert english_before.startswith(old[0]["label"])
