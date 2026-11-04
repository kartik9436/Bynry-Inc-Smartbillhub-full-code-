# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-4072 — metering's event-read door IGNORED the `unit` its
#           caller measured in, so a reading taken in kWh on a register priced
#           in kW posted without a word.
# Change:   CR-168-BRC10 (lane FIN-S, final round)
# Rules:    CLAUDE.md hard rule 3 (a consumption always carries an explicit
#           unit; never assume) · BR-MET-143 (the register's own unit,
#           `register_units.register_unit`) · BR-MET-128 (the event-read door)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The door now READS `unit` when a caller sends one, and refuses a row whose
unit is not the register's — naming the row, before anything is staged.

A row with NO unit is unchanged: every existing caller (the move-in, move-out,
transfer and disconnect wizards) sends none, and the register's own unit is
still what lands on the read. The check is about a caller that says what it
measured in and is wrong, which is the one case nothing caught.
"""

import pytest

from apps.metering import models as metering_models
from apps.metering import services as metering_services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import seed_config, tenant_ctx
from tests.test_w9_event_reads import _account_on, _asset_id, _head, _metered_unit

pytestmark = pytest.mark.django_db


def _reads(**row):
    return {"event": "move_in", "reads": [{"meter_no": "M-9101", "read_at": "2026-08-20", **row}]}


def test_def_wrk_4072__a_unit_that_is_not_the_registers_is_refused_and_nothing_posts(brazos, dana):
    """A demand figure typed as kW against an energy register (kWh) is refused
    on `reads[1].unit`, and the read is not written."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Okafor, Ade")

        with pytest.raises(errors.ValidationError) as raised:
            metering_services.commit_event_reads(dana, _reads(value="43566", unit="kW"))
        head = _head(asset_id)

    field = raised.value.field_errors[0]
    assert field["field"] == "reads[1].unit"
    assert field["message_key"] == "metering.event_reads.unit_not_the_registers"
    assert field["params"]["register_unit"] == "kWh"
    assert field["params"]["measured_unit"] == "kW"
    assert head is None
    assert not metering_models.ReadImportBatch.objects.filter(event_context="move_in").exists()


def test_def_wrk_4072__the_registers_own_unit_in_any_case_posts(brazos, dana):
    """`kwh` is `kWh` — the comparison folds case the way BR-MET-143 does, and
    the stored unit is still the register's own spelling."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        asset_id = _asset_id(unit, "M-9101")
        _account_on(dana, unit["id"], name="Lindqvist, Mia")

        answer = metering_services.commit_event_reads(dana, _reads(value="43566", unit="kwh"))
        head = _head(asset_id)

    assert answer["posted_reads"] == 1
    assert head is not None and head.unit == "kWh"


def test_def_wrk_4072__no_unit_is_unchanged(brazos, dana):
    """Every existing caller sends no unit; the door behaves as before."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Sato, Ken")

        answer = metering_services.commit_event_reads(dana, _reads(value="43566"))

    assert answer["posted_reads"] == 1


def test_def_wrk_4072__an_estimate_row_is_checked_too(brazos, dana):
    """An unreadable meter declared in the wrong unit is the same mistake."""
    with tenant_ctx(brazos):
        seed_config()
        unit = _metered_unit(dana, brazos)
        _account_on(dana, unit["id"], name="Haddad, Rami")

        with pytest.raises(errors.ValidationError) as raised:
            metering_services.commit_event_reads(dana, _reads(estimate=True, unit="gal"))

    assert raised.value.field_errors[0]["field"] == "reads[1].unit"
