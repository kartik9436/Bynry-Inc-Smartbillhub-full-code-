# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-9239 — the ACCOUNTS import offered no column for the
#          utility's own Accounts fields, although the PO named accounts among
#          the imports: *"every import includes one column per custom field
#          (premises, units, assets, accounts, readings)"* (CR-161-BRC10 Part 2,
#          PO 2026-10-02). Found by the custom-fields end-to-end walk, phase 5:
#          Brazos Bend's *Contract ref* was not on the MAPS TO list.
# Rules:   the one validator (`tenancy.validate_custom_data_for`, reached from
#          the runner through metering's seam and from the account write through
#          customers' own) · *"A required field never blocks a screen that
#          doesn't show it"* (an import is not a screen) · an update MERGES into
#          the stored answers, as W3b's premises/units/assets imports do.
# ───────────────────────────────────────────────────────
"""The accounts import carries one column per active Accounts field — on the
MAPS TO list, in the sample CSV, judged per row in plain words, written on
create, merged on update."""

import csv
import io

import pytest

from apps.customers import models as customers_models
from apps.metering import import_runs, models
from apps.tenancy import services as tenancy_services

from tests.test_cr030_w1_accounts_import import ALL_OFF, CUTOVER, _two_units
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

CSV = (
    "UNIT_REF,ACCT,NAME,KIND,SSN,TYPE,OPENED,CONTRACT,TIER\n"
    "{u1},A-9301,Ana Diaz,person,123-45-6789,residential,2024-02-12,C-77,Gold\n"
    "{u2},A-9302,Ben Cole,person,987-65-4321,residential,2025-06-01,C-78,Purple\n"
)
MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "KIND": "customer_kind",
    "SSN": "customer_ssn",
    "TYPE": "account_type",
    "OPENED": "opened_at",
    "CONTRACT": "custom_data.contract_ref",
    "TIER": "custom_data.loyalty_tier",
}


def _fields(actor):
    """Brazos Bend's walk fields: Contract ref (text, REQUIRED on New Account)
    and Loyalty tier (Pick one)."""
    contract = tenancy_services.create_custom_field(
        actor,
        {"label": "Contract ref", "entity": "accounts", "data_type": "text", "is_required": True},
    )
    tenancy_services.save_custom_field_placement(actor, contract["id"], {"S18": "input"})
    tier = tenancy_services.create_custom_field(
        actor,
        {
            "label": "Loyalty tier",
            "entity": "accounts",
            "data_type": "select",
            "options": ["Gold", "Silver"],
        },
    )
    tenancy_services.save_custom_field_placement(actor, tier["id"], {"S21": "input"})


def _run(actor, content, mapping=MAPPING):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ACCOUNTS,
            "source_kind": "file",
            "file_name": "accounts_with_own_fields.csv",
            "content": content,
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": mapping, "row_handling": ALL_OFF, "options": {"cutover_on": CUTOVER}},
    )
    import_runs.validate(actor, run["id"])
    return run["id"]


def test_def_met_9239__the_accounts_import_offers_one_column_per_accounts_field(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _fields(dana)
        columns = {c["target"]: c for c in import_runs.target_columns("accounts")}
        _name, body = import_runs.sample_csv("accounts")
    assert columns["custom_data.contract_ref"]["label"] == "Contract ref"
    # An import is not a screen: a required field never blocks the file.
    assert columns["custom_data.contract_ref"]["required"] is False
    assert "custom_data.loyalty_tier" in columns
    header, example = list(csv.reader(io.StringIO(body)))[:2]
    assert "Contract ref" in header and "Loyalty tier" in header
    assert example[header.index("Contract ref")] == ""  # the utility's own values


def test_def_met_9239__another_utility_never_sees_these_columns(brazos, dana, marcus, lonestar):
    with tenant_ctx(brazos):
        _fields(dana)
    with tenant_ctx(lonestar):
        offered = {c["target"] for c in import_runs.target_columns("accounts")}
    assert not any(target.startswith("custom_data.") for target in offered)


def test_def_met_9239__a_good_row_writes_its_answers_and_a_bad_one_is_refused_in_words(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _fields(dana)
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, CSV.format(u1=units[0]["unit_no"], u2=units[1]["unit_no"]))
        rows = {
            row.raw.get("ACCT"): row for row in models.ImportRunRow.objects.filter(run_id=run_id)
        }
        bad = rows["A-9302"].mapped[import_runs.PARSE_PROBLEMS]["parse"]["problem"]
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        ana = customers_models.Account.objects.get(tenant_id=brazos.id, account_no="A-9301")
        ben_exists = customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_no="A-9302"
        ).exists()
    assert bad == "Purple is not one of the choices for Loyalty tier."
    assert receipt["counts"]["created"] == 1
    assert ana.custom_data == {"contract_ref": "C-77", "loyalty_tier": "Gold"}
    assert not ben_exists


def test_def_met_9239__an_update_merges_into_the_stored_answers(brazos, dana, marcus):
    """Insert & update: the file's column is ADDED to what a clerk typed, and a
    blank cell is *"not telling you"*, never a clear."""
    with tenant_ctx(brazos):
        _fields(dana)
        units = _two_units(marcus, brazos)
        first = CSV.format(u1=units[0]["unit_no"], u2=units[1]["unit_no"]).splitlines()[:2]
        run_id = _run(marcus, "\n".join(first).replace(",Gold", ",") + "\n")
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        ana = customers_models.Account.objects.get(tenant_id=brazos.id, account_no="A-9301")
        assert ana.custom_data == {"contract_ref": "C-77"}
        again = "\n".join(first).replace(",C-77,", ",,").replace(",Gold", ",Silver") + "\n"
        run_id = _run(marcus, again)
        receipt = import_runs.load(dana, run_id, {"write_mode": "upsert", "approved": True})
        ana.refresh_from_db()
    assert receipt["counts"]["updated"] == 1
    assert ana.custom_data == {"contract_ref": "C-77", "loyalty_tier": "Silver"}


def test_def_met_9239__a_view_only_accounts_field_is_filled_by_import(brazos, dana):
    """R4's input-route rule: a field shown on Account detail and typed on no
    screen now has a way in — the accounts sheet's column — so Settings saves
    it and calls it *Filled by import* rather than refusing it."""
    with tenant_ctx(brazos):
        note = tenancy_services.create_custom_field(
            dana, {"label": "Legacy route", "entity": "accounts", "data_type": "text"}
        )
        saved = tenancy_services.save_custom_field_placement(dana, note["id"], {"S21": "view"})
    assert saved["input_route"] == "import"
