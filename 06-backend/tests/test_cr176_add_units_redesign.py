# ── Trace ──────────────────────────────────────────────
# Change:   CR-176-BRC10 — the Add units redesign, round A (server).
# Defect:   DEF-MET-10035 — "Start numbering at defaults to 1 when Unit 1 is
#           taken"; the building card's unlabelled "Not recorded".
# Ruling:   decision log 2026-10-09, "PO GO — BUILD THE ADD-UNITS REDESIGN",
#           rules (1) next free start, (3) services only from the building,
#           (5) a common area is one unit billed to the owner.
# ───────────────────────────────────────────────────────
"""The server half of the Add units redesign.

Every case STAGES (and where it matters COMMITS) through the same importer the
screen posts to, and reads the database back — a staged dict proves nothing
about the unit that comes out the other end.

**Worked figure, from the ruling:** a building holding Unit 1, 2, 3 and 5;
three units from 1 are refused naming *Unit 1, Unit 2, Unit 3* and offering 6
— not 4, because three units from 4 would make Unit 5 again.
"""

import pytest

from apps.customers import models as cus
from apps.metering import importers, models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _spec(premises, **over):
    spec = {
        "premises_id": str(premises["id"]),
        "floors": 1,
        "units_per_floor": 1,
        "label_pattern": "Unit {seq}",
    }
    spec.update(over)
    return {"kind": "units_pattern", "pattern": spec, "options": {"skip_errors": False}}


def _run(actor, payload):
    staged = importers.stage(payload)
    return importers.commit(actor, payload, staged)


def _building_with_units_1_2_3_and_5(actor):
    premises = make_premises(actor, address_line="123 Main Street")
    for seq in (1, 2, 3, 5):
        services.create_unit(actor, {"premises_id": premises["id"], "label": f"Unit {seq}"})
    return premises


def _premises_row(premises):
    return models.Premises.objects.get(pk=premises["id"])


# ── rule (1) · the first start from which the WHOLE run is free ─────────────
def test_next_free_is_6_for_three_units_when_1_2_3_and_5_are_taken(dana, brazos):
    with tenant_ctx(brazos):
        row = _premises_row(_building_with_units_1_2_3_and_5(dana))
        assert importers.next_free_seq_start(row, label_pattern="Unit {seq}", per_floor=3) == 6
        # One unit fits in the gap at 4; two do not (4 and 5).
        assert importers.next_free_seq_start(row, label_pattern="Unit {seq}", per_floor=1) == 4
        assert importers.next_free_seq_start(row, label_pattern="Unit {seq}", per_floor=2) == 6


def test_next_free_is_1_on_a_building_with_no_units(dana, brazos):
    with tenant_ctx(brazos):
        row = _premises_row(make_premises(dana, address_line="9 Mill Race"))
        assert importers.next_free_seq_start(row, label_pattern="{seq}", per_floor=3) == 1


def test_next_free_reads_the_labels_the_PATTERN_makes_not_bare_numbers(dana, brazos):
    """`Unit 1` is taken; the plain pattern `{seq}` makes `1`, which is free."""
    with tenant_ctx(brazos):
        row = _premises_row(_building_with_units_1_2_3_and_5(dana))
        assert importers.next_free_seq_start(row, label_pattern="{seq}", per_floor=3) == 1


def test_a_pattern_with_no_seq_has_no_next_free_number(dana, brazos):
    with tenant_ctx(brazos):
        row = _premises_row(_building_with_units_1_2_3_and_5(dana))
        assert importers.next_free_seq_start(row, label_pattern="Laundry", per_floor=1) is None


def test_a_run_hitting_taken_labels_is_refused_naming_them_and_the_next_free_start(dana, brazos):
    with tenant_ctx(brazos):
        premises = _building_with_units_1_2_3_and_5(dana)
        with pytest.raises(errors.ValidationError) as caught:
            importers.stage(_spec(premises, units_per_floor=3, seq_start=1))
        exc = caught.value
        assert exc.message_key == "metering.import.pattern_labels_taken"
        assert exc.params["labels"] == "Unit 1, Unit 2, Unit 3"
        assert exc.params["next_free"] == 6
        assert exc.field_errors[0]["field"] == "seq_start"
        # Nothing was written by the refusal.
        assert models.Unit.objects.filter(premises_id=premises["id"]).count() == 4


def test_the_offered_start_is_accepted_and_creates_exactly_the_run(dana, brazos):
    with tenant_ctx(brazos):
        premises = _building_with_units_1_2_3_and_5(dana)
        result = _run(dana, _spec(premises, units_per_floor=3, seq_start=6))
        assert result["summary"] == {"created": 3, "failed": 0}
        labels = sorted(
            models.Unit.objects.filter(premises_id=premises["id"]).values_list("label", flat=True)
        )
        assert labels == ["Unit 1", "Unit 2", "Unit 3", "Unit 5", "Unit 6", "Unit 7", "Unit 8"]


def test_a_removed_unit_still_holds_its_label_because_the_create_says_so(dana, brazos):
    """The taken set is `_check_unit_label_unique`'s scope, a removed unit
    included — offering a start the create then refuses is the bug."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="77 Oak Row")
        made = services.create_unit(dana, {"premises_id": premises["id"], "label": "Unit 1"})
        models.Unit.objects.filter(pk=made["id"]).update(deleted_at="2026-10-01T00:00:00Z")
        row = _premises_row(premises)
        assert importers.next_free_seq_start(row, label_pattern="Unit {seq}") == 2


# ── rule (3) · a unit's services come only from its building ───────────────
def test_a_service_the_building_does_not_offer_is_refused_at_staging(dana, brazos):
    with tenant_ctx(brazos):
        # The fixture building offers electric and water. Gas is not on it.
        premises = make_premises(dana, address_line="12 Ash Ct", services_available=["water"])
        with pytest.raises(errors.ValidationError) as caught:
            importers.stage(_spec(premises, services=["water", "electric"]))
        assert caught.value.message_key == "metering.service_not_at_premises"
        assert caught.value.params["service"] == "electric"
        assert caught.value.field_errors[0]["field"] == "services"


def test_a_subset_of_the_buildings_services_is_accepted_and_carried(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="14 Ash Ct")
        result = _run(dana, _spec(premises, services=["water"]))
        assert result["summary"]["created"] == 1
        unit = models.Unit.objects.get(premises_id=premises["id"])
        codes = sorted(
            models.ServicePoint.objects.filter(unit=unit).values_list("service__code", flat=True)
        )
        assert codes == ["water"]


# ── rule (5) · a common area is ONE unit, billed to the owner ───────────────
def test_a_common_area_is_one_unit_and_a_count_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="16 Ash Ct")
        with pytest.raises(errors.ValidationError) as caught:
            importers.stage(
                _spec(premises, units_per_floor=3, label_pattern="Laundry",
                      unit_type="common_area", is_common_area=True)
            )
        assert caught.value.message_key == "metering.import.common_area_one_unit"
        assert models.Unit.objects.filter(premises_id=premises["id"]).count() == 0


def test_a_common_area_made_here_is_flagged_and_billed_to_the_owner(dana, brazos):
    from apps.metering import unit_account

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="18 Ash Ct")
        result = _run(
            dana,
            _spec(premises, label_pattern="Laundry", unit_type="common_area", is_common_area=True),
        )
        assert result["summary"]["created"] == 1
        unit = models.Unit.objects.get(premises_id=premises["id"])
        assert (unit.label, unit.is_common_area, unit.unit_type) == ("Laundry", True, "common_area")
        # The Account tab's reason is the owner's, never "vacant".
        assert unit_account.unit_account(unit.id)["no_account_reason"] == "common_area"


# ── the building card · the owner is the master account, named ─────────────
def test_lends_names_the_master_account_and_says_none_when_there_is_none(dana, brazos):
    with tenant_ctx(brazos):
        bare = make_premises(dana, address_line="20 Ash Ct")
        lends = selectors.premises_lends_dict(_premises_row(bare))
        assert lends["premises"]["master_account_name"] is None
        assert lends["premises"]["master_account_no"] is None

        created = services.create_premises(
            dana,
            {
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "address_line": "123 Main Street",
                "owner_manager": "Bramble Property Group",
                "owner_kind": "company",
                "owner_tax_id": "74-3182640",
                "owner_account_type": "commercial",
            },
        )
        account = cus.Account.objects.get(pk=created["master_account_id"])
        cus.Contact.objects.update_or_create(
            tenant_id=account.tenant_id,
            account=account,
            defaults={"full_name": "Bramble Property Group", "is_primary": True},
        )
        lends = selectors.premises_lends_dict(models.Premises.objects.get(pk=created["id"]))
        assert lends["premises"]["master_account_name"] == "Bramble Property Group"
        assert lends["premises"]["master_account_no"] == account.account_no
