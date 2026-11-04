"""CR-166-BRC10 round 3 task 7 — what the EDIT form's three saves need from the
server that round 2 did not give it.

`DEF-RAT-9313`: *New value from a date* dropped the end date typed for the new
value (image 31 draws an *Ends* box). Reproduced on PostgreSQL 16 before the fix:
`effective_to: 2027-06-30` sent with a 12% value from 01/01/2027 answered 201 and
stored v2 with NO end.

Every case writes through the product's own services, with the tenant's
"today" pinned so the worked dates are the dates the code sees.
"""

from datetime import date

import pytest

from apps.rating import discount_services, seams
from apps.rating import discounts as dm
from core import errors

from tests.test_cr166_discounts_round2 import _discount
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 15)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def test_def_rat_9313_a_new_value_keeps_the_end_date_typed_for_it(brazos, dana):
    """SENIOR 15% from 08/01/2026; 12% from 01/01/2027 to 06/30/2027 → v1 ends
    12/31/2026, v2 runs 01/01/2027–06/30/2027."""
    with tenant_ctx(brazos):
        senior = _discount(dana)
        discount_services.new_discount_value(
            dana,
            senior.id,
            {"value": "12", "effective_from": "2027-01-01", "effective_to": "2027-06-30"},
        )
        v1 = dm.DiscountVersion.objects.get(discount=senior, version_no=1)
        v2 = dm.DiscountVersion.objects.get(discount=senior, version_no=2)
    assert v1.effective_to == date(2026, 12, 31)
    assert (v2.effective_from, v2.effective_to) == (date(2027, 1, 1), date(2027, 6, 30))


def test_def_rat_9313_an_end_before_the_new_start_is_refused_on_the_end_box(brazos, dana):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        with pytest.raises(errors.ValidationError) as refused:
            discount_services.new_discount_value(
                dana,
                senior.id,
                {"value": "12", "effective_from": "2027-01-01", "effective_to": "2026-12-01"},
            )
        versions = dm.DiscountVersion.objects.filter(discount=senior).count()
    assert [fe["field"] for fe in refused.value.field_errors] == ["effective_to"]
    assert refused.value.field_errors[0]["message_key"] == "rating.discounts.window_inverted"
    assert versions == 1  # nothing written


def test_def_rat_9313_no_end_typed_still_means_no_end(brazos, dana):
    """The round-2 behaviour is unchanged when no end is sent."""
    with tenant_ctx(brazos):
        senior = _discount(dana)
        discount_services.new_discount_value(dana, senior.id, {"value": "12", "effective_from": "2027-01-01"})
        v2 = dm.DiscountVersion.objects.get(discount=senior, version_no=2)
    assert v2.effective_to is None


def test_def_rat_9313_an_end_past_the_retire_date_is_refused(brazos, dana):
    """Retiring on 12/31/2027 means nobody gets it after that date (ruling 4):
    a new value may not be typed to run past it."""
    with tenant_ctx(brazos):
        senior = _discount(dana)
        discount_services.retire_discount(dana, senior.id, {"effective_to": "2027-12-31"})
        with pytest.raises(errors.ValidationError) as refused:
            discount_services.new_discount_value(
                dana,
                senior.id,
                {"value": "12", "effective_from": "2027-01-01", "effective_to": "2028-06-30"},
            )
    assert refused.value.field_errors[0]["field"] == "effective_to"
    assert refused.value.field_errors[0]["message_key"] == "rating.discounts.ends_after_retire"


def test_def_rat_9314_a_new_value_on_a_retiring_discount_runs_to_the_retire_date(brazos, dana):
    """SENIOR retiring on 12/31/2027; 12% from 01/01/2027 with no end typed →
    v1 ends 12/31/2026 and v2 runs 01/01/2027–12/31/2027. Refused before the fix
    with `window_overlaps_version` naming v1 — the overlap check ran before v1's
    stated end was moved to the day before."""
    with tenant_ctx(brazos):
        senior = _discount(dana)
        discount_services.retire_discount(dana, senior.id, {"effective_to": "2027-12-31"})
        discount_services.new_discount_value(dana, senior.id, {"value": "12", "effective_from": "2027-01-01"})
        v1 = dm.DiscountVersion.objects.get(discount=senior, version_no=1)
        v2 = dm.DiscountVersion.objects.get(discount=senior, version_no=2)
    assert v1.effective_to == date(2026, 12, 31)
    assert (v2.effective_from, v2.effective_to) == (date(2027, 1, 1), date(2027, 12, 31))
