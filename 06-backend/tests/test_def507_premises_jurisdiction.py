# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-507 — *"GET /premises AND /premises/{id} DO NOT SERVE
#          inside_city_limits, so the ONE line CR-023 says is fillable today
#          cannot be filled."* Filed 2026-08-21; the column landed with
#          migration 0013 for the RATING engine and no read surface came with it.
# Change:  PO, 2026-08-26, on the deployed PRM-02: *"Why Juridiction is showing
#          the in text it should shown inside city and outside city. keep all
#          chnages are related to CR-36"*
# Story:   US-MET-001 (premises read) · CR-023 §2A.3 (PRM-02 Overview)
# Rules:   BR-RAT-101 / BR-RAT-102 (the outside-city surcharge reads this flag)
# ───────────────────────────────────────────────────────
"""One column, three states, and the third one decides money.

`Premises.inside_city_limits` is `BooleanField(null=True)`. `rating.resolution`
has read all three since the day it landed — `None` takes NO multiplier and says
why — while `metering.selectors` served twenty keys and not this one, so the flag
that decides whether every bill at an address carries the outside-city surcharge
reached the engine and reached no human.

⚠ **AND `None` MUST NOT ARRIVE AS `False`.** That is the same collapse DEF-762
had one field below, with a worse consequence: `False` is the answer *outside the
city*, and outside the city is where the surcharge applies. A serialiser that
defaulted it would put a charge on a customer's bill that nobody at the utility
ever recorded.

⚠ **NOTHING HERE MAKES IT WRITABLE.** `services._validate_premises` does not
accept the field and this suite asserts that it still does not: the PO asked to
SEE the flag, and where an edit control belongs — and whether changing it re-rates
issued bills — is a larger question than this row.
"""

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _served(premises_id):
    return selectors.premises_detail_dict(models.Premises.objects.get(pk=premises_id))


def test_def507__the_selector_serves_the_flag_at_all(brazos, dana):
    """THE DEFECT, in one assertion: the key existed nowhere in the payload."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="41 Jurisdiction Way")
        served = _served(premise["id"])
    assert "inside_city_limits" in served


def test_def507__inside_outside_and_never_recorded_are_three_different_values(brazos, dana):
    """`True` / `False` / `None`, each surviving the read as itself.

    The rows are written through the ORM because no write path accepts the
    field — which is the point of the test below this one.
    """
    with tenant_ctx(brazos):
        inside = make_premises(dana, address_line="43 Jurisdiction Way")
        outside = make_premises(dana, address_line="45 Jurisdiction Way")
        unasked = make_premises(dana, address_line="47 Jurisdiction Way")
        models.Premises.objects.filter(pk=inside["id"]).update(inside_city_limits=True)
        models.Premises.objects.filter(pk=outside["id"]).update(inside_city_limits=False)
        # `unasked` is left exactly as `create_premises` left it.
        assert _served(inside["id"])["inside_city_limits"] is True
        assert _served(outside["id"])["inside_city_limits"] is False
        served_unasked = _served(unasked["id"])
    # ⚠ The assertion the fix exists for. `is None` and NOT `is False`: a falsy
    # check here would pass on both and would be charging the customer.
    assert served_unasked["inside_city_limits"] is None
    assert served_unasked["inside_city_limits"] is not False


def test_def507__a_create_that_never_asked_leaves_the_column_unset(brazos, dana):
    """The same no-backfill posture `services_available` takes: nothing invents
    an answer at write time either, so `None` in the payload is the truth about
    the row and not an artefact of the read."""
    with tenant_ctx(brazos):
        created = services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "49 Jurisdiction Way"})
        row = models.Premises.objects.get(pk=created["id"])
    assert row.inside_city_limits is None


def test_def507__the_field_is_WRITABLE_now__and_this_test_is_where_that_was_decided(brazos, dana):
    """⚠ **THIS TEST WAS THE OPPOSITE ASSERTION UNTIL 2026-08-27, AND IT ASKED
    TO BE THE PLACE THAT NOTICED.**

    It read `test_def507__the_field_is_READ_only__no_write_path_accepts_it` and
    its docstring said, verbatim: *"The PO asked to see the flag, not to edit
    it, and a screen that could set it raises questions this row does not answer
    (where in the wizard; does changing it re-rate issued bills). **If a write
    is added later this test is the place that says the decision was made on
    purpose.**"*

    A write WAS added later — CR-039 wave C task 10, closing `DEF-517` — so this
    is that place, and here are the two questions answered:

      * **Where in the wizard.** `JurisdictionField` is on the S16 guided add's
        single-premise step and on the PRM-01 edit modal, beside every other
        premises fact. One component, both forms.
      * **Does changing it re-rate issued bills.** No — forward only, which is
        what CLAUDE.md hard rule 4 permits and all it permits. Whether a
        correction OWES an adjustment on bills already issued is `OQ-423`, put
        to the PO rather than answered by this lane, and pinned by
        `tests/test_cr039_c10_premises_jurisdiction_write.py::
        test_cr039_c10__oq423_changing_the_flag_touches_no_issued_invoice`.

    The assertion is INVERTED rather than deleted, because *"the flag can be
    set"* is now the load-bearing fact and a removed test says nothing.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="51 Jurisdiction Way")
        services.update_premises(dana, premise["id"], {"inside_city_limits": True})
        row = models.Premises.objects.get(pk=premise["id"])
    assert row.inside_city_limits is True


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-507 (12-governance/10-defect-log.csv) + PO ruling 2026-08-26
#         (verbatim above) + BR-RAT-101/102 + CR-023 §2A.3
# screens: PRM-02 premises detail (Overview → Jurisdiction)
# generated: 2026-08-26 by lane DEFSWEEP
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
