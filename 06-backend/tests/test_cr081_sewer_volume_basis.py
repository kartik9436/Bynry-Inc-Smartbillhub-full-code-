# ── Trace ──────────────────────────────────────────────
# Change:   CR-081 — sewer is a percentage of the water VOLUME, priced on a
#           sewer rate schedule of its own. PO ruling 2026-09-07; six ❄️ frozen
#           figures re-signed 2026-09-08 under HUMAN-GUIDE §6.
# Rules:    BR-RAT-1015 (NEW) · BR-RAT-015 ❄️ SUPERSEDED · BR-RAT-010 reopened
#           and answered the other way · BR-RAT-031/032 (a complete structure;
#           one price is ONE 0→∞ tier)
# Golden:   GT-17 ❄️ RE-SIGNED — 8 kgal → 7.2 kgal @ $5.0000 = $36.00
# Tests:    this file (the STORED half) · tests/test_us_rat_012_percent_of_service
#           .py (the ARITHMETIC half, against the engine)
# ───────────────────────────────────────────────────────
"""CR-081 — the half of the ruling that lives in the DATABASE, not the engine.

`tests/test_us_rat_012_percent_of_service.py` proves the arithmetic: 90% of a
metered volume at sewer's own rate. **This file proves the rate can get there
at all**, which is a different question and the one CR-081 actually broke.

Until 2026-09-08 a `percent_of_service` tariff needed no price of its own — it
took a percentage of another service's money — so **no sewer version on any
tenant carries a rate**, `pricing_inputs` published none, and the S11 structure
had nowhere to put one. Three things therefore have to be true together, and
each is asserted below:

  1. a percent version's rate is STORED the way `flat` stores one — a single
     0→∞ `rate_tiers` row (BR-RAT-032), so there is no second column and no
     second way to say "one price";
  2. `pricing_inputs` UNWRAPS it onto `unit_price`, the same field `flat` uses,
     so billing never learns that sewer is special;
  3. a version with a factor and no rate is INCOMPLETE — `BR-RAT-031`'s
     activation gate names `rate` — because half a tariff bills $0.00 for
     sewer on every account that carries it.
"""

from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_us_rat_helpers import *  # noqa: F401,F403
from tests.test_us_rat_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


def _sewer_version(tenant, *, with_rate: bool):
    """A sewer tariff version written straight through the ORM.

    Deliberately NOT through `create_rate_schedule`: this file is about what the
    ENGINE can read back, and going through the service would also drag in
    `BR-RAT-088`'s base-charge-code gate, which is a different rule with its own
    tests. The columns written here are the ones `_write_version` writes.
    """
    water = tenancy_models.Service.objects.get(code="water")
    sewer = tenancy_models.Service.objects.get(code="sewer")
    tariff = models.Tariff.objects.create(
        tenant=tenant, name=f"CR-081 sewer {with_rate}", service=sewer
    )
    version = models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model=services.MODEL_PERCENT,
        currency="USD",
        uom=fixture.WATER_UOM,  # the BASIS service's unit — CR-081
        percent=Decimal(fixture.SEWER_PERCENT_OF_WATER),
        basis_service=water,
        effective_from="2026-06-01",
    )
    if with_rate:
        models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,  # ∞ — BR-RAT-032's single block
            unit_price=Decimal(fixture.SEWER_RATE_PER_UNIT),
        )
    return version


def test_cr081_the_seeded_factor_and_rate_are_the_re_signed_pair():
    """The two figures the PO signed on 2026-09-08, read off the fixture.

    ⚠ `SEWER_PERCENT_OF_WATER` read `"40"` and there was no rate at all until
    that date. The 90 is a RETURN-TO-SEWER FACTOR — the share of metered water
    that physically reaches the sewer — and not the price ratio the 40 was.
    """
    assert fixture.SEWER_PERCENT_OF_WATER == "90"
    assert fixture.SEWER_RATE_PER_UNIT == "5.0000"
    # ❄️ GT-17 as re-signed, worked from the two constants and the meter.
    quantity = Decimal("8") * Decimal(fixture.SEWER_PERCENT_OF_WATER) / Decimal("100")
    assert quantity == Decimal("7.2")
    assert (quantity * Decimal(fixture.SEWER_RATE_PER_UNIT)).quantize(
        Decimal("0.01")
    ) == Decimal("36.00")


def test_cr081_pricing_inputs_unwraps_sewers_rate_onto_unit_price():
    """(1) + (2) — stored as one 0→∞ tier, served as `unit_price`.

    The field matters as much as the number: `unit_price` is what `flat` uses
    and what `gather._tariff_config_for` already copies onto the seam, so
    billing needs to know nothing about sewer. Before this change a percent
    version fell into the tiered branch and published `unit_price=None` — which
    is exactly what the engine now refuses by name.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        version = _sewer_version(tenant, with_rate=True)
        inputs = selectors.pricing_inputs_for_version(version, version.effective_from)

    assert inputs["model"] == "percent_of_service"
    assert inputs["percent"] == Decimal("90")
    assert inputs["basis_service"] == "water"
    assert inputs["unit_price"] == Decimal("5.000000")
    assert inputs["billed_unit"] == fixture.WATER_UOM
    # The rate is ONE block and it is unbounded; a second tier here would be a
    # sewer ladder, which CR-081's answer to question (b) rules out.
    assert inputs["tiers"] == []


def test_cr081_a_factor_with_no_rate_is_an_incomplete_structure():
    """(3) — `BR-RAT-031`'s activation gate names the missing part, and from
    2026-09-08 `rate` is one of the parts it can name.

    ⚠ **PROVED IN BOTH DIRECTIONS ON PURPOSE.** A gate that only ever answers
    `None` is indistinguishable from a gate nobody wired up, and every sewer
    version in this product was rate-less until the CR-081 migration ran — so
    the FAILING case is the one that actually existed.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rateless = _sewer_version(tenant, with_rate=False)
        assert services._missing_structure(rateless) == "rate"
        priced = _sewer_version(tenant, with_rate=True)
        assert services._missing_structure(priced) is None


def test_cr081_the_percent_is_still_reported_before_the_rate():
    """A version missing BOTH says `percent` first: a rate with no basis to
    apply it to is the less useful half to be told about."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        version = _sewer_version(tenant, with_rate=False)
        version.percent = None
        version.save(update_fields=["percent"])
        assert services._missing_structure(version) == "percent"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-081@2026-09-08 (decision log "THE PO RE-SIGNS SIX FROZEN SEWER FIGURES")
# generated: 2026-09-08 by the CR-081 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ · pytest tests/test_cr081_sewer_volume_basis.py✔ · the incomplete-structure case PROVED RED against a version that has a rate
# exceptions: it writes the version through the ORM rather than `create_rate_schedule`, stated in `_sewer_version`'s own docstring — that path carries BR-RAT-088's base-code gate, which is a different rule with its own tests and which is RED on this branch for reasons that predate CR-081 (measured against the pristine tip: the same 14 cases fail there)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
