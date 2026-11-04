# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 waves W2 + W3, customers lane — the record types the
#           customers module owns (Part 2 rows 1, 3, 4, 5)
# Defects:  DEF-CUS-9159 (New Connection Step 1 dropped the account fields) ·
#           DEF-CUS-9168 (contacts) · DEF-CUS-9169 (mailing addresses) ·
#           DEF-CUS-9170 (service agreements)
# Rules:    BR-TEN-052 as amended 2026-10-02 (required only where typed in;
#           one served slot list) · BR-TEN-048 (never priced) · BR-TEN-046
#           (one utility only) · CLAUDE.md hard rule 8 (mailing address only)
# ───────────────────────────────────────────────────────
"""The server half of each customers record type's custom fields, door by door.

Every door validates through `seams.validate_custom_data` — tenancy's one
validator — and names the slot its form IS, so a required field binds only
where it is typed in. Each case states which screen's door it drives.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors
from tests import identity_fixtures
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan
from tests.test_us_cus_012_017_account_actions import _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, marcus, tenant_ctx  # noqa: F401
from tests.test_w6_commit_orders_and_owner import _premises_with_a_priced_common_area

pytestmark = pytest.mark.django_db


def _field(actor, entity, label, placement, **over):
    payload = {"label": label, "entity": entity, "data_type": "text", **over}
    created = tenancy_services.create_custom_field(actor, payload)
    if placement:
        tenancy_services.save_custom_field_placement(actor, created["id"], placement)
    return created


def _active_payload(unit_id, **over):
    return _create_payload(unit_id, status="active", **over)


def _detail(account_id):
    return customers_selectors.account_detail_dict(customers_selectors.account_or_404(account_id))


def _field_of(caught):
    return [row["field"] for row in caught.value.field_errors]


# ── Contacts (DEF-CUS-9168) — the contact edit on Account detail, S21 ───────
def test_def_cus_9168__the_contact_edit_saves_merges_and_serves_its_fields(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _field(dana, "contacts", "Preferred name", {"S21": "input"})
        _field(dana, "contacts", "Best time", {"S21": "input"})
        unit = _unit_with_plan(marcus, brazos)
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
        customers_services.update_account_contact(
            marcus, created["id"], {"custom_data": {"preferred_name": "Ellie"}}
        )
        edited = customers_services.update_account_contact(
            marcus, created["id"], {"custom_data": {"best_time": "Evenings"}}
        )
        stored = customers_models.Contact.objects.get(account_id=created["id"]).custom_data
    # The answer typed first survives an edit naming only the second.
    assert stored == {"preferred_name": "Ellie", "best_time": "Evenings"}
    assert edited["contacts"][0]["custom_data"] == stored


def test_def_cus_9168__required_binds_on_the_contact_edit_and_counts_a_stored_answer(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _field(dana, "contacts", "Preferred name", {"S21": "input"}, is_required=True)
        unit = _unit_with_plan(marcus, brazos)
        # The wizard's contact block draws no contact field: nothing required there.
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
        # The edit draws it: a phone fix with the field still blank is refused.
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.update_account_contact(marcus, created["id"], {"phone": "555-0101"})
        assert _field_of(caught) == ["custom_data.preferred_name"]
        assert customers_models.Contact.objects.get(account_id=created["id"]).phone != "555-0101"
        customers_services.update_account_contact(
            marcus, created["id"], {"custom_data": {"preferred_name": "Ellie"}}
        )
        # Once stored, it answers the requirement for an edit that names it not.
        edited = customers_services.update_account_contact(
            marcus, created["id"], {"phone": "555-0101"}
        )
    assert edited["contacts"][0]["phone"] == "555-0101"


def test_def_cus_9168__an_unknown_contact_key_is_refused_by_name(brazos, dana, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.update_account_contact(
                marcus, created["id"], {"custom_data": {"made_up": "x"}}
            )
    assert _field_of(caught) == ["custom_data.made_up"]


# ── Mailing addresses (DEF-CUS-9169) — New Account S18 · Account detail S21 ─
def test_def_cus_9169__new_account_writes_the_mailing_rows_fields(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _field(dana, "addresses", "Delivery note", {"S18": "input", "S21": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["addresses"][0]["custom_data"] = {"delivery_note": "Side door"}
        created = customers_services.create_account(marcus, payload)
        detail = _detail(created["id"])
    assert detail["addresses"][0]["custom_data"] == {"delivery_note": "Side door"}


def test_def_cus_9169__required_on_new_account_binds_only_when_a_mailing_row_is_typed(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _field(dana, "addresses", "Delivery note", {"S18": "input"}, is_required=True)
        unit = _unit_with_plan(marcus, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(marcus, _create_payload(unit["id"]))
        assert _field_of(caught) == ["custom_data.delivery_note"]
        assert not customers_models.Account.objects.filter(unit_id=unit["id"]).exists()
        # *Same as service address*: no row, no form, nothing required.
        created = customers_services.create_account(
            marcus, _create_payload(unit["id"], addresses=[])
        )
    assert created["id"]


def test_def_cus_9169__the_mailing_edit_merges_and_a_clear_keeps_no_row(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _field(dana, "addresses", "Delivery note", {"S18": "input", "S21": "input"})
        _field(dana, "addresses", "Attention", {"S21": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])
        payload["addresses"][0]["custom_data"] = {"delivery_note": "Side door"}
        created = customers_services.create_account(marcus, payload)
        edited = customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "PO Box 12", "custom_data": {"attention": "Accounts"}}
        )
        assert edited["addresses"][0]["custom_data"] == {
            "delivery_note": "Side door",
            "attention": "Accounts",
        }
        # A street blanked removes the row; the custom answers go with it.
        cleared = customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": ""}
        )
    assert [a for a in cleared["addresses"] if a["kind"] == "mailing"] == []


def test_def_cus_9169__the_move_in_door_requires_nothing_of_an_address(brazos, dana, marcus):
    """Required binds on the screen it is typed in on: New account (S18) and
    not the import or the move-in, which draw no address field."""
    with tenant_ctx(brazos):
        _field(dana, "addresses", "Delivery note", {"S18": "input"}, is_required=True)
        rows = customers_services._validate_addresses(
            [{"kind": "mailing", "line1": "1 Main St"}], custom_data_screen=None
        )
    assert "custom_data" not in rows[0]


# ── Service agreements (DEF-CUS-9170) — S18 · S23 · S21 ─────────────────────
def test_def_cus_9170__new_account_writes_every_agreement_it_opens(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _field(dana, "service_agreements", "Contract term", {"S18": "input"})
        unit = _unit_with_plan(marcus, brazos)
        payload = _active_payload(unit["id"])
        payload["service_custom_data"] = {"contract_term": "12 months"}
        created = customers_services.create_account(marcus, payload)
        agreements = _detail(created["id"])["service_agreements"]
    assert len(agreements) == 2
    assert [a["custom_data"] for a in agreements] == [{"contract_term": "12 months"}] * 2


def test_def_cus_9170__a_draft_cannot_keep_service_answers_and_requires_none(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _field(dana, "service_agreements", "Contract term", {"S18": "input"}, is_required=True)
        unit = _unit_with_plan(marcus, brazos)
        payload = _create_payload(unit["id"])  # a draft: opens no agreement
        payload["service_custom_data"] = {"contract_term": "12 months"}
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(marcus, payload)
        assert caught.value.field_errors[0]["message_key"] == (
            "customers.account.service_fields_on_draft"
        )
        # Blank on a draft: nothing is being typed in, nothing is required.
        created = customers_services.create_account(marcus, _create_payload(unit["id"]))
    assert created["id"]


def test_def_cus_9170__required_on_new_account_services_blocks_an_active_create(
    brazos, dana, marcus
):
    with tenant_ctx(brazos):
        _field(dana, "service_agreements", "Contract term", {"S18": "input"}, is_required=True)
        unit = _unit_with_plan(marcus, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(marcus, _active_payload(unit["id"]))
        assert _field_of(caught) == ["custom_data.contract_term"]
        assert not customers_models.Account.objects.filter(unit_id=unit["id"]).exists()


def test_def_cus_9170__change_plan_merges_into_every_open_agreement(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _field(dana, "service_agreements", "Contract term", {"S23": "input"})
        _field(dana, "service_agreements", "Meter access", {"S23": "input"})
        world = _world(marcus, brazos)
        rows = customers_models.ServiceAgreement.objects.filter(account_id=world["account_id"])
        rows.update(custom_data={"meter_access": "Back yard"})
        customers_services.change_plan(
            marcus,
            world["account_id"],
            {
                "rate_plan_id": str(world["senior"].id),
                "effective_on": "2026-09-01",
                "notify": False,
                "service_custom_data": {"contract_term": "24 months"},
            },
        )
        stored = [row.custom_data for row in rows.order_by("id")]
    assert stored == [{"meter_access": "Back yard", "contract_term": "24 months"}] * 2


def test_def_cus_9170__required_on_change_plan_refuses_before_the_plan_moves(
    brazos, dana, marcus
):
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        _field(dana, "service_agreements", "Contract term", {"S23": "input"}, is_required=True)
        world = _world(marcus, brazos)
        before = rating_models.UnitPlanAssignment.objects.filter(unit_id=world["unit_id"]).count()
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.change_plan(
                marcus,
                world["account_id"],
                {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01"},
            )
        after = rating_models.UnitPlanAssignment.objects.filter(unit_id=world["unit_id"]).count()
    assert _field_of(caught) == ["custom_data.contract_term"]
    assert before == after


# ── New Connection Step 1 (DEF-CUS-9159) — the owner's account, S18 ─────────
def test_def_cus_9159__the_owner_account_keeps_what_step_one_typed(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "accounts", "Visit window", {"S18": "input"})
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        w6.create_owner_account(
            dana,
            created["id"],
            {
                "name": "Brazos Bend Developments LLC",
                "contact": {"full_name": "Brazos Bend Developments LLC"},
                "customer": identity_fixtures.company_customer("Brazos Bend Developments LLC"),
                "custom_data": {"visit_window": "Mornings"},
            },
        )
        connection = work_tables.Connection.objects.get(pk=created["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
    assert account.custom_data == {"visit_window": "Mornings"}


def test_def_cus_9159__a_required_step_one_field_left_blank_refuses_the_owner_account(
    brazos, dana
):
    with tenant_ctx(brazos):
        _field(dana, "accounts", "Visit window", {"S18": "input"}, is_required=True)
        premises, _ = _premises_with_a_priced_common_area(dana, brazos)
        created = w6.create_connection(dana, {"premises_id": premises["id"]})
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_owner_account(
                dana,
                created["id"],
                {
                    "name": "Brazos Bend Developments LLC",
                    "contact": {"full_name": "Brazos Bend Developments LLC"},
                    "customer": identity_fixtures.company_customer("Brazos Bend Developments LLC"),
                    "custom_data": {},
                },
            )
    assert _field_of(caught) == ["custom_data.visit_window"]


# ── One utility only ─────────────────────────────────────────────────────────
@pytest.mark.isolation
def test_cr161_w3_isolation__another_utility_cannot_write_or_see_these_fields(
    brazos, lonestar, dana, marcus
):
    with tenant_ctx(brazos):
        _field(dana, "contacts", "Preferred name", {"S21": "input"})
        _field(dana, "service_agreements", "Contract term", {"S18": "input", "S21": "view"})
        assert tenancy_selectors.custom_field_registry("contacts", screen="S21", mode="view")
    with tenant_ctx(lonestar):
        for entity in ("contacts", "addresses", "service_agreements"):
            assert tenancy_selectors.custom_field_registry(entity, screen="S21", mode="view") == []
        # Brazos's key is unknown here, so a forged write is refused by name.
        with pytest.raises(errors.ValidationError) as caught:
            customers_services._validate_contact(
                {"full_name": "X", "custom_data": {"preferred_name": "Bo"}},
                custom_data_screen="S21",
            )
    assert _field_of(caught) == ["custom_data.preferred_name"]


# ── A utility with no fields sees every door unchanged ───────────────────────
def test_cr161_w3_zero_fields__every_door_behaves_as_before(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        created = customers_services.create_account(marcus, _active_payload(unit["id"]))
        customers_services.update_account_contact(marcus, created["id"], {"phone": "555-0199"})
        customers_services.update_account_mailing_address(marcus, created["id"], {"city": "Rosenberg"})
        detail = _detail(created["id"])
    assert detail["contacts"][0]["custom_data"] == {}
    assert detail["addresses"][0]["custom_data"] == {}
    assert all(a["custom_data"] == {} for a in detail["service_agreements"])
