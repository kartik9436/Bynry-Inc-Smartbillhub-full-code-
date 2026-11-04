# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9847 (PO GIS review 2026-10-07, gap 6)
# Rules:    BR-MET-1163 (the Parcel box) · BR-MET-1173 / BR-INT-073 (the City's
#           parcel has no unique index; two premises on one lot is real) ·
#           hard rule 1 (tenant scoping) · hard rule 8 (the address is read off
#           `premises`, its one home) · hard-won law 14 (savepoint, on PostgreSQL)
# Impacts:  apps/metering/services.py · apps/metering/selectors.py ·
#           apps/integrations/gis.py · apps/integrations/seams/metering.py
# ───────────────────────────────────────────────────────
"""A parcel number another property already holds is ONE sentence naming that
property — never our 500, never silence.

**RED BEFORE, measured on PostgreSQL 16 at 2.558.3 (2026-10-07):**
  * the race (check passes, index refuses) raised
    `IntegrityError: duplicate key value violates unique constraint
    "uq_premises_tenant_external_ref_ci"` out of `create_premises` — our 500;
  * a typed City parcel already on another property was ACCEPTED, making a
    second property on that parcel with nothing said;
  * the refusals that did exist said *"That Parcel ID is already used."* and
    never which property.

⚠ **RUN THIS FILE ON POSTGRESQL** (`--ds=config.settings.pgtest`). The race
cases read the other property's address AFTER a failed INSERT; on PostgreSQL
that read only works because the write sits in a savepoint, and SQLite — the
default suite — has no aborted-transaction state to prove it against.
"""

from __future__ import annotations

import pytest

from apps.metering import selectors, services
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

KEY = "metering.premises.external_ref_taken"


def _refusal_names(caught, *, field: str, address: str) -> None:
    assert caught.value.message_key == KEY
    assert caught.value.params["address"] == address, caught.value.params
    assert [one["field"] for one in caught.value.field_errors] == [field]


def test_a_typed_city_parcel_already_on_a_property_is_refused_naming_it(brazos, dana):
    with tenant_ctx(brazos):
        services.create_premises(
            dana,
            {"address_line": "10 Deed Row", "city": "Katy", "gis_parcel_id": "P-77"},
            custom_fields_screen="S16",
        )
        with pytest.raises(errors.BizError) as caught:
            services.create_premises(
                dana,
                {"address_line": "12 Deed Row", "city": "Katy", "gis_parcel_id": "p-77"},
                custom_fields_screen="S16",
            )
    _refusal_names(caught, field="gis_parcel_id", address="10 Deed Row, Katy")


def test_an_import_or_a_reconciliation_still_may_put_two_properties_on_one_lot(brazos, dana):
    """`BR-INT-073` — a duplex on one parcel is a City fact. Only a PERSON on a
    form is refused; a caller passing no screen is never refused here."""
    with tenant_ctx(brazos):
        services.create_premises(dana, {"address_line": "1 Lot Ln", "gis_parcel_id": "LOT-1"})
        second = services.create_premises(dana, {"address_line": "1B Lot Ln", "gis_parcel_id": "LOT-1"})
    assert second["gis_parcel_id"] == "LOT-1"


def test_the_edit_form_refusal_names_the_other_property(brazos, dana):
    with tenant_ctx(brazos):
        services.create_premises(dana, {"address_line": "20 Elm St", "city": "Katy", "external_ref": "R-9"})
        mover = services.create_premises(dana, {"address_line": "22 Elm St"})
        with pytest.raises(errors.BizError) as caught:
            services.update_premises(
                dana, str(mover["id"]), {"external_ref": "R-9"}, custom_fields_screen="PREMISE_EDIT"
            )
    _refusal_names(caught, field="external_ref", address="20 Elm St, Katy")


def test_the_race_on_create_is_the_same_sentence_and_not_our_500(brazos, dana, monkeypatch):
    """The check passes (two clerks, a double press) and the INDEX refuses."""
    with tenant_ctx(brazos):
        services.create_premises(dana, {"address_line": "30 Oak St", "city": "Katy", "external_ref": "R-30"})
        monkeypatch.setattr(selectors, "premises_external_ref_taken", lambda *a, **k: False)
        with pytest.raises(errors.BizError) as caught:
            services.create_premises(dana, {"address_line": "32 Oak St", "external_ref": "R-30"})
        # …and the transaction is still usable afterwards (law 14): a read works.
        assert selectors.premises_holding_parcel("R-30") == "30 Oak St, Katy"
    _refusal_names(caught, field="external_ref", address="30 Oak St, Katy")


def test_the_race_on_edit_is_the_same_sentence_and_not_our_500(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        services.create_premises(dana, {"address_line": "40 Ash St", "city": "Katy", "external_ref": "R-40"})
        mover = services.create_premises(dana, {"address_line": "42 Ash St"})
        monkeypatch.setattr(selectors, "premises_external_ref_taken", lambda *a, **k: False)
        with pytest.raises(errors.BizError) as caught:
            services.update_premises(dana, str(mover["id"]), {"external_ref": "r-40"})
    _refusal_names(caught, field="external_ref", address="40 Ash St, Katy")


def test_another_utility_holding_the_same_number_is_never_named(brazos, lonestar, dana, erin):
    """Hard rule 1 — the index is per tenant, so is the question, so is the answer."""
    with tenant_ctx(lonestar):
        services.create_premises(erin, {"address_line": "9 Secret Rd", "external_ref": "SAME-1"})
    with tenant_ctx(brazos):
        assert selectors.premises_holding_parcel("SAME-1") is None
        made = services.create_premises(dana, {"address_line": "9 Open Rd", "external_ref": "SAME-1"})
    assert made["external_ref"] == "SAME-1"


def test_only_the_parcel_index_is_dressed_as_this_refusal():
    """Any OTHER integrity failure is re-raised, never renamed."""

    class Driver(Exception):
        class diag:  # noqa: N801 — psycopg's shape
            constraint_name = "uq_premises_tenant_premise_no"

    other = Exception("wrapped")
    other.__cause__ = Driver("duplicate key")
    assert services._is_parcel_collision(other) is False

    class ParcelDriver(Exception):
        class diag:  # noqa: N801
            constraint_name = "uq_premises_tenant_external_ref_ci"

    ours = Exception("wrapped")
    ours.__cause__ = ParcelDriver("duplicate key")
    assert services._is_parcel_collision(ours) is True


def test_the_city_pick_refusal_names_the_property_too(brazos, dana):
    from apps.integrations import gis, gis_fixtures, models as int_models
    from apps.integrations import services as integration_services
    from apps.integrations import runtime
    from tests.test_us_met_helpers import owner_for

    runtime.reset_caps()
    with tenant_ctx(brazos):
        integration_services.connect(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=gis.PROVIDER_KEY,
            environment=int_models.ENVIRONMENT_PRODUCTION,
            config={"base_url": f"https://{gis_fixtures.FAST_HOST}/addr"},
            cadence=int_models.CADENCE_NIGHTLY,
        )
        typed = {"address_line": "1408 Pec", "premises_type": "single_family",
                 "owner_id": owner_for(dana, "Whitfield Rentals LLC")}
        first = gis.create_premises(dana, brazos.id, parcel="88214", typed=typed)
        with pytest.raises(gis.GisRefusal) as refusal:
            gis.create_premises(dana, brazos.id, parcel="88214", typed=typed)
    runtime.reset_caps()
    assert refusal.value.message_key == gis.REFUSAL_PARCEL_TAKEN
    assert refusal.value.params["address"].startswith(first["address_line"])
