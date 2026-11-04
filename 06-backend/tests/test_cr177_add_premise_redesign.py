# ── Trace ──────────────────────────────────────────────
# Change:   CR-177-BRC10 round A — the server half of the Add a premise
#           redesign (PO GO 2026-10-09, decision log *"PO GO — BUILD THE
#           ADD-A-PREMISE REDESIGN"* and *"PO RULINGS — ADD-A-PREMISE REDESIGN,
#           CONTINUED"*). Defect DEF-MET-10034.
# Rules:    BR-MET-1190 (an address is unique in the utility; Open it / Add it
#           anyway) · BR-MET-1191 (the City map is asked only on Check address)
#           · BR-MET-1194 (required custom fields before save) · BR-MET-1195
#           (the owner is an existing master account found and linked; this
#           screen opens no account) · hard rule 1 (tenant scoping) · hard rule
#           8 (the address lives on premises) · hard-won law 14 (PostgreSQL)
# ───────────────────────────────────────────────────────
"""The server half of Add a premise, as the PO ruled it on 2026-10-09.

⚠ **RUN THIS FILE ON POSTGRESQL TOO** (`--ds=config.settings.pgtest`): the
duplicate refusal is raised inside a request whose transaction must still be
usable for the next read, and the owner search pages a lazy queryset through
two modules — both are the shapes SQLite cannot be trusted on (law 14).

⚠ **NO REAL CITY IS EVER DIALLED.** Every City here is a recorded `.example`
host in `apps/integrations/gis_fixtures.py`.
"""

from __future__ import annotations

import pytest

from apps.customers import models as cus
from apps.integrations import gis, gis_fixtures, runtime
from apps.integrations import api as integrations_api
from apps.integrations import models as int_models
from apps.integrations import services as integration_services
from apps.metering import address_match, models, services
from apps.metering import api as metering_api
from apps.tenancy import services as tenancy_services
from core import errors
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

SAME = "metering.premises.same_address_exists"
TWO_HOMES = [{"label": "Unit 1"}, {"label": "Unit 2"}]


@pytest.fixture(autouse=True)
def _clear_caps():
    runtime.reset_caps()
    yield
    runtime.reset_caps()


def _add(actor, **payload):
    """Add a premise exactly as the screen's own door does (`S16`)."""
    return services.create_premises(actor, payload, custom_fields_screen="S16")


# ── task 1 · the same address ──────────────────────────────────────────────


def test_an_exact_duplicate_ignoring_capitals_spaces_and_punctuation_is_refused_naming_it(
    brazos, dana
):
    with tenant_ctx(brazos):
        first = _add(dana, address_line="101 Silver Creek Rd", city="Silver Creek", state="TX", postal_code="78611")
        with pytest.raises(errors.BizError) as caught:
            _add(dana, address_line="101 silver  creek rd.", city="silver creek", state="tx", postal_code="78611")
        # …and the transaction is still usable afterwards (law 14).
        assert models.Premises.objects.filter(address_line__istartswith="101").count() == 1
    refusal = caught.value
    assert refusal.message_key == SAME
    assert refusal.params["premise_no"] == first["premise_no"]
    assert refusal.params["address"] == "101 Silver Creek Rd, Silver Creek, TX 78611"
    assert [one["field"] for one in refusal.field_errors] == ["address_line"]


def test_add_it_anyway_saves_the_second_one(brazos, dana):
    with tenant_ctx(brazos):
        _add(dana, address_line="5 Elm St", city="Katy", state="TX", postal_code="77494")
        second = _add(dana, address_line="5 ELM ST", city="Katy", state="TX", postal_code="77494", add_anyway=True)
        assert models.Premises.objects.filter(address_line__iexact="5 elm st").count() == 2
    assert "add_anyway" not in second  # never a column


def test_a_string_false_is_not_an_add_it_anyway(brazos, dana):
    with tenant_ctx(brazos):
        _add(dana, address_line="6 Elm St", city="Katy")
        with pytest.raises(errors.BizError):
            _add(dana, address_line="6 Elm St", city="Katy", add_anyway="false")


def test_exact_means_exact_road_is_not_rd_and_another_zip_is_another_address(brazos, dana):
    with tenant_ctx(brazos):
        _add(dana, address_line="7 Oak Rd", city="Katy", state="TX", postal_code="77494")
        _add(dana, address_line="7 Oak Road", city="Katy", state="TX", postal_code="77494")
        _add(dana, address_line="7 Oak Rd", city="Katy", state="TX", postal_code="77495")
        assert models.Premises.objects.filter(address_line__istartswith="7 Oak").count() == 3


def test_an_import_or_seed_is_not_refused_here(brazos, dana):
    """Only a PERSON's Add a premise form is asked (the import has its own
    duplicate handling; New Connection is refused at Approve)."""
    with tenant_ctx(brazos):
        services.create_premises(dana, {"address_line": "8 Ash St", "city": "Katy"})
        services.create_premises(dana, {"address_line": "8 Ash St", "city": "Katy"})


def test_another_utility_holding_the_same_address_is_never_named(brazos, lonestar, dana, erin):
    with tenant_ctx(lonestar):
        _add(erin, address_line="9 Secret Rd", city="Katy", state="TX", postal_code="77494")
    with tenant_ctx(brazos):
        assert address_match.premises_with_same_address("9 Secret Rd", "Katy", "TX", "77494") is None
        _add(dana, address_line="9 Secret Rd", city="Katy", state="TX", postal_code="77494")


def test_the_screen_check_answers_the_same_as_the_save(brazos, dana):
    with tenant_ctx(brazos):
        first = _add(dana, address_line="3721 S Village Dr", city="Avenel", state="NJ", postal_code="07001")
    hit = api_call(
        metering_api.premises_same_address,
        "get",
        f"/api/{brazos.subdomain}/premises/same-address",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        query={"address_line": "3721 s village dr", "city": "AVENEL", "state": "nj", "postal_code": "07001"},
    )
    miss = api_call(
        metering_api.premises_same_address,
        "get",
        f"/api/{brazos.subdomain}/premises/same-address",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        query={"address_line": "3723 S Village Dr", "city": "Avenel", "state": "NJ", "postal_code": "07001"},
    )
    assert hit.status_code == 200, hit.data
    same = hit.data["same"]
    assert same["premise_no"] == first["premise_no"]
    assert same["address"] == "3721 S Village Dr, Avenel, NJ 07001"
    assert same["status"] == first["status"]
    assert miss.data == {"same": None}


# ── task 5 · no double comma ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "parts,expected",
    [
        (("3721 S Village Dr,", "Avenel", "NJ", "07001"), "3721 S Village Dr, Avenel, NJ 07001"),
        (("3721 S Village Dr", "", "NJ", "07001"), "3721 S Village Dr, NJ 07001"),
        (("3721 S Village Dr", "Avenel", "", ""), "3721 S Village Dr, Avenel"),
        ((" 3721 S Village Dr , ", " , Avenel", None, "07001"), "3721 S Village Dr, Avenel, 07001"),
        (("", "", "", ""), ""),
    ],
)
def test_an_empty_or_comma_ended_part_never_makes_a_double_comma(parts, expected):
    assert services.compose_address(*parts) == expected
    assert ",," not in services.compose_address(*parts)


def test_a_comma_typed_at_the_end_of_the_street_is_not_stored(brazos, dana):
    """Found by the browser walk: the review read right, the ROW kept the comma."""
    with tenant_ctx(brazos):
        made = _add(dana, address_line="3721 S Village Dr, ", city="Avenel ,", state="NJ", postal_code="07001")
        row = models.Premises.objects.get(pk=made["id"])
    assert (row.address_line, row.city) == ("3721 S Village Dr", "Avenel")


# ── task 4 · required custom fields ────────────────────────────────────────


def test_a_required_custom_field_left_blank_is_refused_on_its_own_field(brazos, dana):
    with tenant_ctx(brazos):
        field = tenancy_services.create_custom_field(
            dana, {"label": "Roof Age", "entity": "premises", "data_type": "number", "is_required": True}
        )
        tenancy_services.save_custom_field_placement(dana, field["id"], {"S16": "input"})
        key = field["key"]
        for custom in ({}, {key: ""}):
            with pytest.raises(errors.ValidationError) as caught:
                _add(dana, address_line="12 Roof Rd", city="Katy", custom_data=custom)
            assert f"custom_data.{key}" in [one["field"] for one in caught.value.field_errors]
        made = _add(dana, address_line="12 Roof Rd", city="Katy", custom_data={key: 12})
    assert made["custom_data"][key] in (12, "12", 12.0)


# ── task 10b · the owner is linked, never opened here ──────────────────────


def _bramble(dana):
    """A real master account, opened the way New Connection / the import still
    open one (no screen), owning a property managed by Northside Management."""
    return services.create_premises(
        dana,
        {
            "units": TWO_HOMES,
            "address_line": "1 Bramble Way",
            "owner_manager": "Northside Management",
            "owner_kind": "company",
            "owner_tax_id": "74-3182640",
            "owner_account_type": "commercial",
        },
    )


def _search(brazos, dana, q):
    return api_call(
        metering_api.premises_owner_search,
        "get",
        f"/api/{brazos.subdomain}/premises/owner-search",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        query={"q": q},
    )


def test_the_owner_search_finds_a_master_account_by_number_with_its_card(brazos, dana):
    with tenant_ctx(brazos):
        owned = _bramble(dana)
    number = owned["master_account_no"]
    found = _search(brazos, dana, number)
    assert found.status_code == 200, found.data
    assert found.data["count"] == 1
    row = found.data["results"][0]
    assert row["account_no"] == number
    assert row["party_kind"] == "company"
    assert row["account_type"] == "commercial"
    assert row["account_type_name"]
    assert row["status_name"]
    assert row["managed_by"] == "Northside Management"
    assert set(row) >= {"id", "account_no", "name", "account_type_name", "party_kind", "managed_by", "status_name"}


def test_the_owner_search_says_nothing_found_and_never_offers_an_ordinary_account(brazos, dana):
    with tenant_ctx(brazos):
        _bramble(dana)
        regular = cus.Account.objects.filter(kind="regular").values_list("account_no", flat=True).first()
    missing = _search(brazos, dana, "Zzz Holdings")
    assert missing.data["count"] == 0 and missing.data["results"] == []
    if regular:
        assert _search(brazos, dana, regular).data["count"] == 0
    # One character is a clerk still typing (IS-3) and matches nothing.
    assert _search(brazos, dana, "1").data["count"] == 0


def test_linking_a_found_account_attaches_it_and_opens_nothing(brazos, dana):
    with tenant_ctx(brazos):
        owned = _bramble(dana)
        masters_before = cus.Account.objects.filter(kind="master").count()
        made = _add(dana, address_line="2 Bramble Way", master_account_id=owned["master_account_id"])
        masters_after = cus.Account.objects.filter(kind="master").count()
    assert masters_after == masters_before
    assert made["master_account_id"] == owned["master_account_id"]


def test_without_a_link_add_a_premise_opens_no_account_and_says_nothing_about_one(brazos, dana):
    with tenant_ctx(brazos):
        masters_before = cus.Account.objects.filter(kind="master").count()
        made = _add(dana, address_line="3 Bramble Way", units=TWO_HOMES)
        masters_after = cus.Account.objects.filter(kind="master").count()
    assert masters_after == masters_before
    assert made["owner_master_account"] is None
    assert [w for w in made["warnings"] if w.get("code") == services.OWNER_ACCOUNT_NOT_CREATED] == []


@pytest.mark.parametrize("key", services.S16_REFUSED_OWNER_KEYS)
def test_the_keys_that_opened_an_account_are_refused_by_name_from_this_screen(brazos, dana, key):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _add(dana, address_line="4 Bramble Way", **{key: "x"})
    assert [one["field"] for one in caught.value.field_errors] == [key]


# ── task 2 · ONE check-address request ─────────────────────────────────────


def _connect(tenant, actor, host):
    with tenant_ctx(tenant):
        return integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=int_models.ENVIRONMENT_PRODUCTION,
            config={"base_url": f"https://{host}/addr"},
            cadence=int_models.CADENCE_NIGHTLY,
        )


def _check(brazos, dana, **body):
    return api_call(
        integrations_api.gis_check_address,
        "post",
        f"/api/{brazos.subdomain}/integrations/{gis.PROVIDER_KEY}/check-address",
        user=dana.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        data=body,
        key=gis.PROVIDER_KEY,
    )


def test_check_address_without_a_city_map_is_not_connected_and_dials_nothing(brazos, dana, monkeypatch):
    def _never(*_a, **_k):
        raise AssertionError("a utility with no City map must dial nothing")

    monkeypatch.setattr(gis, "search", _never)
    answer = _check(brazos, dana, address_line="1408 Pecan St", postal_code="78701")
    assert answer.status_code == 200, answer.data
    assert answer.data["result"] == gis.CHECK_NOT_CONNECTED
    assert answer.data["match"] is None


def test_check_address_with_a_city_map_returns_the_citys_address_parcel_and_point(brazos, dana):
    _connect(brazos, dana, gis_fixtures.FAST_HOST)
    answer = _check(brazos, dana, address_line="1408 Pecan St")
    assert answer.status_code == 200, answer.data
    assert answer.data["result"] == gis.CHECK_MATCH
    match = answer.data["match"]
    assert match["parcel"] == "88214"
    assert match["address_line"].startswith("1408 Pecan St")
    assert match["unit"] in (None, "")  # the building's own row, never a unit's
    assert match["lat"] and match["lng"]
    assert answer.data["session"]


def test_check_address_with_nothing_on_the_city_map_is_no_match(brazos, dana):
    _connect(brazos, dana, gis_fixtures.EMPTY_HOST)
    answer = _check(brazos, dana, address_line="9 Nowhere Rd")
    assert answer.data["result"] == gis.CHECK_NO_MATCH
    assert answer.data["match"] is None


def test_a_city_that_refuses_is_unavailable_with_its_reason(brazos, dana):
    _connect(brazos, dana, gis_fixtures.DOWN_HOST)
    answer = _check(brazos, dana, address_line="1408 Pecan St")
    assert answer.status_code == 200
    assert answer.data["result"] == gis.CHECK_UNAVAILABLE
    assert answer.data["message_key"]


# ── task 3 · Use these details ─────────────────────────────────────────────


def test_use_these_details_saves_the_citys_address_parcel_point_and_checked_date(brazos, dana):
    _connect(brazos, dana, gis_fixtures.FAST_HOST)
    checked = _check(brazos, dana, address_line="1408 Pecan St").data
    match = checked["match"]
    with tenant_ctx(brazos):
        made = gis.create_premises(
            dana,
            brazos.id,
            parcel=match["parcel"],
            point=match.get("point"),
            session_id=checked["session"],
            # The screen puts the City's address into the form on *Use these
            # details*, so the typed payload carries it; the server re-checks.
            typed={"address_line": match["address_line"], "city": "Austin"},
        )
        row = models.Premises.objects.get(pk=made["id"])
    assert row.address_line == match["address_line"]
    assert row.gis_parcel_id == "88214"
    assert row.lat is not None and row.lng is not None
    assert row.gis_unchecked is False
    assert row.gis_checked_at is not None
