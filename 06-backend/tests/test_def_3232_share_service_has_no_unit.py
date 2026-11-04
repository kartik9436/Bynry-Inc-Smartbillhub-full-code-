# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-3232 (medium, billing-basis lane, 2026-09-02) — sewer is the one
#           service ruled to have NO unit of measure, and both halves of
#           Settings → Services still refuse to save a row without one, so a
#           clerk who opens Sewer and presses Save meets a refusal they cannot
#           satisfy.
# Rules:    BR-TEN-1180 clause (2) — `share` is "a percentage of another
#           service's money; no register, no count, and no unit of its own"
#           (PO ruling 2026-09-02) · BR-TEN-1181 (this lane, 2026-09-02) — the
#           primary unit is required for `metered` and `capacity` and REFUSED
#           for `share` · US-TEN-008 TC-5, narrowed by BR-TEN-1181 ·
#           CLAUDE.md hard rule 3 (a consumption always carries an explicit
#           unit), which is why the metered side must not move
# Story:    US-TEN-008 (S8 Services & UoM)                    Screens: S8 (SET-03)
# ───────────────────────────────────────────────────────
"""THE THREE BASES SAVED THROUGH THE REAL WRITE PATH, AND WHAT A CLERK CAN DO NEXT.

WHY THIS FILE EXISTS, AND IT IS `DEF-3232`'s ESCAPE REASON WORD FOR WORD
------------------------------------------------------------------------
**Neither half was wrong on its own and no test asked the two together.** The
backend suite asserts the primary-required refusal (`US-TEN-008` TC-5) and
asserts the seeded sewer row has no unit (`BR-TEN-1180`) — both pass, because
nothing drove a SAVE of the one service where the two rules meet. The frontend
suite renders the row and its basis and never submits it.

So this file saves each of the three bases through
`services.update_tenant_service` — the function the S8 modal posts to — and
asserts what a clerk can do afterwards.

⚠ **AND IT ASSERTS THE OTHER TWO BASES JUST AS HARD.** A metered service with no
unit is exactly the state CLAUDE.md hard rule 3 exists to prevent, and metering's
own validation errors `unit_missing` on that row. The narrowing is to `share`
alone; `metered` and `capacity` are unmoved, and two of the cases below exist to
prove it stayed that way.

RED PROVED FIRST (hard-won law 7) — MEASURED, NOT IMAGINED
-----------------------------------------------------------
Run against the branch tip before any of this lane's changes,
`3 failed, 2 passed`. The three, verbatim:

  `test_a_share_service_saves_with_no_unit` and
  `test_moving_a_service_to_share_clears_the_unit_it_used_to_carry` —

      field_errors = [{'field': 'primary_uom', 'code': 'VAL-001',
                       'message_key': 'settings.services.primary_required',
                       'params': {}}]
      core.errors.ValidationError: VAL-001 (settings.services.primary_required)

  `test_a_share_service_refuses_a_unit_it_cannot_have` —

      assert 'settings.services.uom_not_for_share' in ['settings.services.uom_unknown']

⚠ **THE THIRD FAILURE IS THE INTERESTING ONE AND IT IS RECORDED RATHER THAN
TIDIED.** The old code did not merely fail to refuse the unit — it refused it for
the WRONG REASON. `kgal` is scoped to water, so a `kgal` on sewer came back
*"we don't recognise the unit"*, which is accurate about the outcome and wrong
about the cause: the unit is real, and the reason it cannot go there is that
sewer has no unit at all. The new check runs in the field-error pass, before
`resolve_uom` is reached, so the refusal a caller meets now names the actual
rule.

The two GREEN cases were green before the change and are green after it, which is
the point of having them here: they are the guard on the guard.
"""

from __future__ import annotations

import pytest

from apps.tenancy import models, selectors, services
from core import errors

# `import *` pulls the autouse fixtures every tenancy test file depends on
# (`growth_plan`, `audit_rows`, …) — pytest resolves a fixture by name in the
# module it is collected from, so importing the names is what registers them.
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db


#: The tenant this file provisions: water is the backbone sewer's percentage is
#: taken of (`BR-RAT-015`), trash is the capacity service, and electric is the
#: metered one. Three services, three bases, one signup.
SERVICES = ["electric", "water", "sewer", "trash"]


def _tenant():
    return provisioned_tenant(
        brazosbend_payload(
            subdomain="sharebasis",
            name="Share Basis Utilities",
            services=SERVICES,
            owner={
                "full_name": "Dana Whitfield",
                "email": "dana@sharebasis.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )


def _actor(tenant):
    from tests.test_us_met_helpers import staff_actor

    # A REAL identity row, not a synthetic uuid: `_audit` stamps `actor_user_id`,
    # a reviewed cross-module FK into `users` (B2 §2). DEF-566 / DEF-2395.
    return staff_actor(tenant, "system_admin", "dana@sharebasis.example.invalid")


def _keys(exc: errors.ValidationError) -> list[str | None]:
    return [f.get("message_key") for f in (exc.field_errors or [])]


def test_a_share_service_saves_with_no_unit(growth_plan, settings):
    """**THE DEFECT.** Sewer, exactly as the screen holds it, saved.

    The S8 modal sends every field it holds — the form's own comment says so —
    so this sends what a clerk pressing Save on an untouched sewer row sends:
    the basis it already has and four empty units. Before `BR-TEN-1181` that was
    `settings.services.primary_required`, a refusal with nothing a clerk could
    do about it: sewer HAS no unit, by the PO's own ruling.
    """
    settings.JOBS_EAGER = False  # DEF-567 — no sample plant is needed to save a row
    tenant, _ = _tenant()
    with tenant_ctx(tenant):
        actor = _actor(tenant)
        saved = services.update_tenant_service(
            actor,
            "sewer",
            {
                "billing_basis": "share",
                "primary_uom": None,
                "alt_uom": None,
                "billed_uom": None,
                "conversion_factor": None,
            },
        )
    assert saved["billing_basis"] == "share"
    assert saved["primary_uom"] is None, saved
    assert saved["alt_uom"] is None, saved


def test_a_share_service_refuses_a_unit_it_cannot_have(growth_plan, settings):
    """The other half of the ruling: `share` has no unit, so it may not be given one.

    Optional-and-allowed would leave TWO spellings of one fact — `NULL` and
    `'kgal'` both meaning *sewer has no unit* — and every reader would have to
    know which. That ambiguity one column over is what `DEF-2409` was filed
    about, so it is refused BY NAME rather than accepted and ignored.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _tenant()
    with tenant_ctx(tenant):
        actor = _actor(tenant)
        with pytest.raises(errors.ValidationError) as refused:
            services.update_tenant_service(
                actor, "sewer", {"billing_basis": "share", "primary_uom": "kgal"}
            )
    assert "settings.services.uom_not_for_share" in _keys(refused.value), _keys(refused.value)


def test_a_metered_service_still_cannot_be_saved_without_a_unit(growth_plan, settings):
    """**THE GUARD ON THE GUARD — CLAUDE.md hard rule 3.**

    A metered service with no unit is a register whose readings carry no unit,
    which metering's own validation refuses as `unit_missing`. `US-TEN-008` TC-5
    is narrowed to exclude `share` and to nothing else; electric is untouched.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _tenant()
    with tenant_ctx(tenant):
        actor = _actor(tenant)
        with pytest.raises(errors.ValidationError) as refused:
            services.update_tenant_service(
                actor, "electric", {"billing_basis": "metered", "primary_uom": None}
            )
    assert "settings.services.primary_required" in _keys(refused.value), _keys(refused.value)


def test_a_capacity_service_still_cannot_be_saved_without_a_unit(growth_plan, settings):
    """The second half of the guard, and it is not the same case as the first.

    A capacity service reads no register either, so *"it has no register"* is not
    on its own a reason to drop the unit — its quantity is a COUNT and the count
    is counted in something (`BR-RAT-090`: 3 carts × `$15.00` = `$45.00`, and the
    unit is `cart`). Only `share` has no quantity at all.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _tenant()
    with tenant_ctx(tenant):
        actor = _actor(tenant)
        with pytest.raises(errors.ValidationError) as refused:
            services.update_tenant_service(
                actor, "trash", {"billing_basis": "capacity", "primary_uom": ""}
            )
    assert "settings.services.primary_required" in _keys(refused.value), _keys(refused.value)


def test_moving_a_service_to_share_clears_the_unit_it_used_to_carry(growth_plan, settings):
    """The path that upgrades a tenant provisioned before the ruling.

    Migration `tenancy 0031` moved sewer's BASIS to `share` and deliberately
    moved no unit — a data migration that rewrote a tenant's declared units would
    be doing more than the ruling said. So a tenant provisioned before 2026-09-02
    can hold sewer `share` WITH a `kgal` primary, and this save is how that row is
    corrected: the clerk (or the S8 form, which sends nulls for a share service)
    clears the unit in the same request that states the basis.
    """
    settings.JOBS_EAGER = False
    tenant, _ = _tenant()
    with tenant_ctx(tenant):
        actor = _actor(tenant)
        # Plant the pre-ruling shape the migration leaves behind, directly on the
        # row: there is no supported write path that produces it, which is the
        # whole reason this case exists.
        row = models.TenantService.objects.get(tenant_id=tenant.id, service__code="sewer")
        row.primary_uom = models.Uom.objects.get(tenant_id=tenant.id, code__iexact="kgal")
        row.save(update_fields=["primary_uom", "updated_at"])
        assert selectors.service_row("sewer")["primary_uom"] is not None

        saved = services.update_tenant_service(
            actor,
            "sewer",
            {"billing_basis": "share", "primary_uom": None, "alt_uom": None},
        )
    assert saved["primary_uom"] is None, saved
