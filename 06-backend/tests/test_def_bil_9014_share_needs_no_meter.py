# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9014 — a service priced as a PERCENT of another service was
#          charged once PER METER: water at 38% of electric on an account with
#          two water meters billed $1,691.64 against $860.82 charged once.
# Ruling:  PO 2026-10-02 (decision log, "WATER AT 38% OF ELECTRIC ON TWO WATER
#          METERS IS NOT A VALID CASE"), verbatim: *"this is not valid case …
#          you give me real example"*. The real case is sewer priced as a share
#          of water, and sewer has no meter of its own.
# Rules:   BR-TEN-1180 (billing_basis: metered · share · capacity, the
#          tenant's own declaration) · BR-RAT-015 / BR-RAT-1015 (a share of
#          another service) · mirrors DEF-RAT-9015
# ───────────────────────────────────────────────────────
"""The save refuses a share-of-another-service schedule on a service the
utility reads from its OWN meter.

The double charge of `DEF-BIL-9014` can only arise when the service being
priced as a share itself has meters, so that is where it is stopped: at the
save, where a clerk can still act on it.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2): an "allowed" case
that is refused for some OTHER reason would still say *our* key is absent. So
the allowed cases call `_validate_structure` directly and assert it raised
NOTHING at all, and the switch case uses the SAME sewer payload on the same
tenant, so the tenant's declaration is the only thing that changes.
"""

from __future__ import annotations

import pytest

from apps.rating import services
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

KEY = "rating.schedules.share_needs_no_meter"


def _declare(env, service, basis, *, enabled=True):
    tenancy_models.TenantService.objects.filter(
        tenant=env.tenant, service__code=service
    ).update(billing_basis=basis, enabled=enabled)


def _water_as_share_of_electric():
    """The walk's case: water at 38% of electric's charges."""
    return {
        "name": "Water at 38% of electric · DEF-BIL-9014",
        "service": "water",
        "model": "percent_of_service",
        "uom": "kgal",
        "structure": {"percent": "38", "basis_service": "electric", "percent_basis": "charge"},
    }


def _sewer_as_share_of_water():
    """The real case: sewer at 90% of the water usage at $5.00 per kgal."""
    return {
        "name": "Sewer at 90% of water · DEF-BIL-9014",
        "service": "sewer",
        "model": "percent_of_service",
        "uom": "kgal",
        "structure": {
            "percent": "90",
            "basis_service": "water",
            "percent_basis": "usage",
            "unit_price": "5.00",
        },
    }


def _keys(exc):
    return [row["message_key"] for row in exc.field_errors]


def _structure_errors(payload):
    fe: list[dict] = []
    services._validate_structure(
        payload["model"], payload, fe, service_code=payload["service"]
    )
    return fe


def test_def_bil_9014__water_as_a_share_of_electric_is_refused_at_save(env):
    _declare(env, "water", "metered")
    _declare(env, "electric", "metered")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_rate_schedule(env.admin, _water_as_share_of_electric())
    assert any(
        row["field"] == "model" and row["message_key"] == KEY
        for row in caught.value.field_errors
    ), _keys(caught.value)


def test_def_bil_9014__sewer_as_a_share_of_water_is_allowed(env):
    _declare(env, "water", "metered")
    _declare(env, "sewer", "share")
    with tenant_ctx(env.tenant):
        assert _structure_errors(_sewer_as_share_of_water()) == []
        try:
            services.create_rate_schedule(env.admin, _sewer_as_share_of_water())
        except errors.ValidationError as exc:  # another rule's refusal is not this one
            assert KEY not in _keys(exc)


def test_def_bil_9014__sewer_is_refused_once_the_utility_reads_it_from_a_meter(env):
    _declare(env, "water", "metered")
    _declare(env, "sewer", "share")
    with tenant_ctx(env.tenant):
        assert _structure_errors(_sewer_as_share_of_water()) == []
    _declare(env, "sewer", "metered")
    with tenant_ctx(env.tenant):
        fe = _structure_errors(_sewer_as_share_of_water())
        assert [(row["field"], row["message_key"]) for row in fe] == [("model", KEY)]
        with pytest.raises(errors.ValidationError) as caught:
            services.create_rate_schedule(env.admin, _sewer_as_share_of_water())
    assert KEY in _keys(caught.value)


def test_def_bil_9014__a_counted_service_may_still_be_priced_as_a_share(env):
    """The rule is about METERS, not about sewer: a utility that counts its
    storm water may still price it as a share of water."""
    _declare(env, "water", "metered")
    _declare(env, "storm_water", "capacity")
    payload = {**_sewer_as_share_of_water(), "service": "storm_water"}
    with tenant_ctx(env.tenant):
        assert KEY not in [row["message_key"] for row in _structure_errors(payload)]


def test_def_bil_9014__flat_on_a_metered_service_is_unaffected(env):
    _declare(env, "water", "metered")
    payload = {
        "name": "Water flat · DEF-BIL-9014",
        "service": "water",
        "model": "flat",
        "uom": "kgal",
        "structure": {"unit_price": "4.00"},
    }
    with tenant_ctx(env.tenant):
        assert _structure_errors(payload) == []
