# ── Trace ──────────────────────────────────────────────
# Change:   CR-092-BRC01 step 2 wave C lane 2 — `AST-B-14`, the opening read.
#           PO 2026-09-12, verbatim: *"Build it as drawn - move it to step 2,
#           beside the multiplier, register digits and the warning"*, which
#           OVERTURNS the add wizard's own recorded position that no seam let
#           assets write a `meter_reads` row at create time.
# Screens:  S51 / AST-05 step 2 (screen 29)
# Rules:    BR-AST-022's posture, borrowed (a requested read that cannot be
#           captured refuses the WHOLE operation) · BR-MET-015 (an ERROR
#           outcome is resolved by a human, never by a form) · BR-MET-056 (the
#           row stores the math it was computed with) · CLAUDE.md rule 3 (an
#           explicit unit) · rule 7 (the capture is audited) · B1 (assets asks
#           metering; it never writes `meter_reads` itself)
# Impacts:  apps/metering/services.py (`_capture_manual_read` extracted;
#           `capture_opening_read` added) · apps/assets/seams.py ·
#           apps/assets/services.py (`_capture_opening_read`, called inside
#           `create_asset`'s own transaction)
# ───────────────────────────────────────────────────────
"""`AST-B-14` — a clerk booking in a meter records the reading on its dial.

RED-FIRST (r11 step 2d), run in a worktree pinned at `404ae10c0` — **4 of the 6
cases failed there**:

    test_opening_read_lands_on_the_new_meter                        FAILED
    test_an_explicit_read_date_is_honoured_over_the_install_date    FAILED
    test_a_blank_reading_is_a_first_class_answer_and_writes_nothing FAILED
    test_a_reading_with_no_date_anywhere_is_refused_…               FAILED
      → core.errors.ValidationError: VAL-002 (assets.unknown_field)
        field_errors = [{'field': 'opening_read', …},
                        {'field': 'opening_read_date', …}]

`POST /assets` refused both keys by name, which is the honest shape of the old
world: no seam existed, and the wizard drew a DISABLED box saying so.

⚠ **THE OTHER TWO PASSED AT THE TIP AND DO NOT DISCRIMINATE ON THEIR OWN (law 7
habit 2, said rather than glossed over).** `test_a_refused_reading_takes_the_
asset_with_it` and `test_a_device_has_no_register_and_is_refused_by_name` both
assert *a refusal naming `opening_read`, and no asset left behind* — and the old
tree refused `opening_read` as an UNKNOWN FIELD, which satisfies both halves for
entirely the wrong reason. They were therefore proved red a second time against
the FINISHED code, one sabotage at a time, and the two failures are quoted
because they are different in kind:

    · drop the `MEASURING_TYPES` guard in `_capture_opening_read`
      → core.errors.BizError: BIZ-STATE
        (metering.read.opening_read_failed_validation)
      The device case goes red on the EXCEPTION TYPE: without the guard the
      reading reaches metering, which refuses it for its own reason — so the
      clerk meets a sentence about validation instead of *"This asset has no
      register"*, and the refusal names no field the screen has.

    · move the capture OUTSIDE `create_asset`'s `transaction.atomic()`
      → AssertionError: assert 1 == 0   (`_asset_count("M-OPEN-3")`)
      The negative-register case goes red on the thing the consequence box
      promises: the reading was refused and **the meter survived**.

⚠ **THE TRANSACTION CASE IS THE ONE THAT MATTERS AND IT CANNOT BE PROVED ON
SQLITE ALONE.** CLAUDE.md hard-won law 14: a failed statement poisons a whole
PostgreSQL transaction and SQLite has no such state, so a rollback assertion
that passes here is necessary and not sufficient. What IS proved on either
engine is the thing the wizard promises a clerk — that a refused reading leaves
NO asset behind — because the refusal is raised before commit and
`create_asset`'s `transaction.atomic()` is what unwinds it.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    at,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _premise_unit(actor, label="401", address="400 Bayou Bend Dr", service="water"):
    from tests.test_us_met_helpers import make_premises, make_unit

    premise = make_premises(actor, address_line=address, services_available=[service])
    return make_unit(actor, premise["id"], label=label, services=[service])


def _reads_for(asset_id):
    from apps.metering import models

    return list(models.MeterRead.objects.filter(asset_id=asset_id).order_by("read_at"))


def _asset_count(asset_no):
    from apps.assets import models

    return models.Asset.objects.filter(asset_no=asset_no).count()


def _payload(unit_id, **over):
    body = {
        "type": "meter",
        "asset_no": "M-OPEN-1",
        "service": "water",
        "unit": "kgal",
        "read_method": "manual",
        "multiplier": "1",
        "register_digits": 9,
        "unit_id": unit_id,
        "install_date": "2026-09-01",
    }
    body.update(over)
    return body


def test_opening_read_lands_on_the_new_meter(brazos, dana, audit_rows):
    """The whole capability in one case: a typed dial reading becomes the new
    meter's first committed row, dated the install date."""
    with tenant_ctx(brazos):
        unit = _premise_unit(dana)
        asset = asset_services.create_asset(dana, _payload(unit["id"], opening_read="12481"))

        rows = _reads_for(asset["id"])
        assert len(rows) == 1
        row = rows[0]
        assert row.current_value == Decimal("12481.000000")
        # There IS no prior — the asset was created microseconds ago — so the
        # first row stands on nothing and says so rather than inventing a delta.
        assert row.prior_value is None
        assert row.unit == "kgal"  # rule 3 — the ASSET's own UoM, never guessed
        assert row.source == "manual" and row.source_detail == "opening_read"
        assert row.lifecycle == "committed"
        # The drawing's own sentence: *"Defaults to the install date."*
        assert row.read_at == at("2026-09-01")

    # Rule 7 — a read written by a form is audited under its own action name,
    # so the trail says which form took it.
    assert "read.opening_read_captured" in [r["action"] for r in audit_rows]


def test_an_explicit_read_date_is_honoured_over_the_install_date(brazos, dana):
    """Two different days, both stored — the meter goes in on the 1st and the
    dial was read on the 3rd."""
    with tenant_ctx(brazos):
        unit = _premise_unit(dana, label="402", address="402 Bayou Bend Dr")
        asset = asset_services.create_asset(
            dana,
            _payload(unit["id"], opening_read="900", opening_read_date="2026-09-03"),
        )
        rows = _reads_for(asset["id"])
        assert len(rows) == 1 and rows[0].read_at == at("2026-09-03")
        from apps.assets import models

        assert models.Asset.objects.get(id=asset["id"]).install_date == date(2026, 9, 1)


def test_a_blank_reading_is_a_first_class_answer_and_writes_nothing(brazos, dana):
    """*"Blank starts billing from zero"* — the field is optional and an empty
    one must not leave an empty row behind."""
    with tenant_ctx(brazos):
        unit = _premise_unit(dana, label="403", address="403 Bayou Bend Dr")
        asset = asset_services.create_asset(dana, _payload(unit["id"], opening_read=""))
        assert _reads_for(asset["id"]) == []
        # Sent as nothing at all, which is what the wizard does, reads the same.
        unit2 = _premise_unit(dana, label="404", address="404 Bayou Bend Dr")
        other = asset_services.create_asset(
            dana, _payload(unit2["id"], asset_no="M-OPEN-2")
        )
        assert _reads_for(other["id"]) == []


def test_a_refused_reading_takes_the_asset_with_it(brazos, dana):
    """**THE CONTRACT THE CONSEQUENCE BOX STATES:** *"If it fails, nothing is
    created."*

    A negative register is refused by metering's own validator, and because the
    capture runs inside `create_asset`'s `transaction.atomic()` the asset row
    never survives. The alternative — a meter in service whose baseline nobody
    knows — is the outcome this rule exists to prevent.
    """
    with tenant_ctx(brazos):
        unit = _premise_unit(dana, label="405", address="405 Bayou Bend Dr")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_asset(
                dana, _payload(unit["id"], asset_no="M-OPEN-3", opening_read="-5")
            )
        # The refusal names the field that is ON THE SCREEN. It would have read
        # `final_read_value` if the seam had been reused by label rather than
        # parameterised — a field the add wizard does not have, so the wizard
        # would have highlighted nothing.
        fields = [f["field"] for f in (caught.value.field_errors or [])]
        assert "opening_read" in fields
        assert _asset_count("M-OPEN-3") == 0


def test_a_device_has_no_register_and_is_refused_by_name(brazos, dana):
    """A backflow preventer stores no reading, so there is nothing the number
    could mean. The wizard does not draw the field for a device at all; this is
    the server saying the same thing to a stale form or a direct API call."""
    with tenant_ctx(brazos):
        unit = _premise_unit(dana, label="406", address="406 Bayou Bend Dr")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_asset(
                dana,
                {
                    "type": "backflow",
                    "asset_no": "BF-OPEN-1",
                    "unit_id": unit["id"],
                    "install_date": "2026-09-01",
                    "opening_read": "12",
                },
            )
        fields = [f["field"] for f in (caught.value.field_errors or [])]
        assert "opening_read" in fields
        assert _asset_count("BF-OPEN-1") == 0


def test_a_reading_with_no_date_anywhere_is_refused_rather_than_dated_today(brazos, dana):
    """A reading that cannot be placed in a period cannot be billed from, and
    guessing today would date a meter's first reading to whenever somebody
    happened to type it."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_asset(
                dana,
                {
                    "type": "meter",
                    "asset_no": "M-OPEN-4",
                    "service": "water",
                    "unit": "kgal",
                    "read_method": "manual",
                    "multiplier": "1",
                    "opening_read": "100",
                },
            )
        fields = [f["field"] for f in (caught.value.field_errors or [])]
        assert "opening_read_date" in fields
        assert _asset_count("M-OPEN-4") == 0
