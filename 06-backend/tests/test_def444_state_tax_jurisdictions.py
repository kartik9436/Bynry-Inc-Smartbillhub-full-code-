# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-002 (reference-data seeding) · US-TEN-006 (S8 Regional)
#           Screens: S8 Regional · PLN-03 step 5 · S9 Taxes & fees
# Rules:    BR-TEN-012 (versioned fixtures, per-list idempotent, tenant-touched
#           rows never overwritten) · BR-TEN-013/031 (cross-module writes route
#           through the OWNING module's seeder) · BR-TEN-037 (a tenant's own
#           jurisdictions — there is no global registry) · BR-TEN-058 (a RUN
#           never writes into a reference catalogue) · BR-TEN-067 / OQ-088 (the
#           S111 toggle; discretionary lists are not delivered to a tenant whose
#           answer is unknown) · BR-TEN-010 (a replay writes nothing)
# Tests:    this file
# Impacts:  apps/rating/sample_data.py TAX_AUTHORITIES (whose skip is CORRECT
#           and must keep skipping) · apps/billing tax lines · design §A4
# ───────────────────────────────────────────────────────
"""DEF-444 — the live tenant had NO tax jurisdictions, so nobody could be taxed.

⚠ **THE CAUSE IS NOT WHERE THE SYMPTOM IS.** Plan wizard step 5 read *"No tax
jurisdictions exist yet"* and `apps/rating/sample_data.py` reported that it was
skipping `TX-STATE` and `TX-LOCAL` — both of those are CORRECT behaviour over
missing input (BR-TEN-058: a run never writes into a reference catalogue). The
missing input is upstream, in tenancy, and it has two halves that were each
measured before a line was written:

  1. **`tenants.state` IS OPTIONAL AT SIGN-UP.** `_validate_signup` accepts a
     null `state` and `SignupWizard`'s step-1 validity check does not require the
     field. Provisioned without one, a tenant receives the `ALL` scaffold —
     County · City · Special district — with **no authority and zero `taxes`
     rows**. Measured: `['City', 'County', 'Special district'] taxes=0` against
     `['City', 'County', 'Local', 'Special district', 'Texas Public Utility
     Commission', 'Texas State', 'Texas Water Development Board'] taxes=2` for
     the same payload with `state: "Texas"`.

  2. **AND THE STATE CAN NEVER ARRIVE AFTERWARDS.** `reference_seed_runs` is
     keyed `(tenant, list_code, fixture_version)` and the per-state list depends
     on a THIRD thing the key does not carry. So a tenant that named its state
     on S8 Regional the next day was skipped by every delivery path there is:
     the re-run (`already` ⇒ `continue`), the version sweep (discretionary lists
     are deferred under OQ-088), and the `--tenant` repair door, which is the
     re-run. Measured before the fix: `REPAIR SUMMARY {} {}` and the
     jurisdictions unchanged at the three scaffold rows.

Every case below was run against HEAD before the fix. The two that matter — `a
state recorded later is delivered` and `the repair door delivers it` — fail
with `assert 'Texas State' in ['City', 'County', 'Special district']`, which is
the defect stated as an assertion.
"""

import pytest

from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    audit_actions,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The five authorities the platform catalogue holds for Texas, plus the three
#: `ALL` scaffold levels every tenant gets. Named rather than counted: a count
#: passes when the wrong five arrive.
TX_AUTHORITIES = {
    "Texas State",
    "Local",
    "Texas Public Utility Commission",
    "City",
    "Texas Water Development Board",
}
SCAFFOLD = {"County", "City", "Special district"}


def _jurisdictions(tenant) -> set[str]:
    with tenant_ctx(tenant):
        return set(
            rating_models.TaxJurisdiction.objects.filter(tenant_id=tenant.id).values_list(
                "name", flat=True
            )
        )


def _tax_count(tenant) -> int:
    with tenant_ctx(tenant):
        return rating_models.Tax.objects.filter(tenant_id=tenant.id).count()


def _admin(tenant):
    from types import SimpleNamespace

    owner = tenancy_models.Tenant.objects.get(pk=tenant.pk)
    return SimpleNamespace(id=None, role="system_admin", tenant=owner)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE BASELINE — a tenant that named its state is fine, and always was
# ══════════════════════════════════════════════════════════════════════════


def test_a_tenant_that_named_its_state_holds_its_states_authorities(
    growth_plan, identity_seam, audit_rows
):
    """This case PASSED before the fix and is here so the next reader can see
    which half was broken. Texas carries five authorities in the catalogue and
    two of them are the ones DEF-444 named by hand (`TX-STATE`, `TX-LOCAL`)."""
    tenant, _ = provisioned_tenant()
    held = _jurisdictions(tenant)
    assert TX_AUTHORITIES <= held
    assert SCAFFOLD <= held
    # And the rates come with them, so a bill can actually carry a tax line.
    assert _tax_count(tenant) > 0


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE DEFECT — a state recorded AFTER sign-up
# ══════════════════════════════════════════════════════════════════════════


def test_a_stateless_signup_gets_the_scaffold_and_no_tax_at_all(
    growth_plan, identity_seam, audit_rows
):
    """The measured starting condition, asserted so it cannot drift silently.

    Three levels with no authority and no rate is NOT the same thing as "this
    utility levies no tax" — but on screen the two are identical, which is why
    the defect went a day without anyone being able to name it.
    """
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="nostateco"))
    assert _jurisdictions(tenant) == SCAFFOLD
    assert _tax_count(tenant) == 0


def test_recording_the_state_on_s8_regional_delivers_that_states_authorities(
    growth_plan, identity_seam, audit_rows
):
    """⚠ **THE FIX, AND THE CASE THAT WAS RED.** Before: the setting saved and
    nothing else happened, for good. After: the catalogue is applied where the
    state is recorded."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="latestate"))
    assert TX_AUTHORITIES - _jurisdictions(tenant)  # the premise: they are absent

    with tenant_ctx(tenant):
        services.save_regional_settings(_admin(tenant), {"state": "Texas"})

    held = _jurisdictions(tenant)
    assert TX_AUTHORITIES <= held, f"DEF-444: Texas's own authorities never arrived — {held}"
    # And with them the rates, so PLN-03 step 5 has something to offer and a
    # bill can carry a tax line. DEF-273's set-skip prices them only because
    # this tenant held no `taxes` row of its own.
    assert _tax_count(tenant) > 0
    # BR-TEN-016 — the delivery is on the record, not merely in the tables.
    assert "reference.seeded" in audit_actions(audit_rows)


def test_the_repair_door_now_delivers_a_late_recorded_state(growth_plan, identity_seam, audit_rows):
    """`manage.py seed_demo --tenant <sub>` is the operator's door for a tenant
    that already exists. It read the seed-run row and skipped, which is why the
    live tenant could not be repaired by the one tool built for it."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="repairco"))
    tenant.state = "Texas"
    tenant.save(update_fields=["state"])

    with tenant_ctx(tenant):
        summary = services.seed_reference_data_for_tenant(
            tenant, _admin(tenant), structural_only=False
        )

    assert TX_AUTHORITIES <= _jurisdictions(tenant)
    assert summary["seeded"].get("tax_jurisdictions", 0) > 0


def test_a_replay_writes_nothing_and_says_nothing(growth_plan, identity_seam, audit_rows):
    """BR-TEN-010. Re-offering the per-state list on every run is only safe if a
    run that changes nothing LOOKS like a run that changed nothing — otherwise
    the honest report becomes noise and the next lane stops reading it."""
    tenant, _ = provisioned_tenant()
    before = _jurisdictions(tenant)
    with tenant_ctx(tenant):
        summary = services.seed_reference_data_for_tenant(
            tenant, _admin(tenant), structural_only=False
        )
    assert _jurisdictions(tenant) == before
    assert "tax_jurisdictions" not in summary["seeded"]
    # No second run row for the same (tenant, list, version).
    assert (
        tenancy_models.ReferenceSeedRun.objects.filter(
            tenant=tenant, list_code="tax_jurisdictions"
        ).count()
        == 1
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · WHAT THE FIX MUST NOT DO
# ══════════════════════════════════════════════════════════════════════════


def test_a_tenant_that_declined_reference_defaults_is_still_given_nothing(
    growth_plan, identity_seam, audit_rows
):
    """OQ-088 (CLOSED, PO 2026-08-10) — until `reference_defaults_opted_in`
    exists, *"declined"* and *"did not exist yet"* are the same absence, so a
    tenant that turned the S111 toggle off must not receive a discretionary list
    because a field changed. The seed-run row IS the recorded opt-in and this
    tenant has none."""
    tenant, _ = provisioned_tenant(
        brazosbend_payload(load_defaults=False, subdomain="nodefaultsco")
    )
    assert _jurisdictions(tenant) == set()

    with tenant_ctx(tenant):
        result = services.deliver_state_tax_jurisdictions(tenant, _admin(tenant))

    assert result["delivered"] == 0
    assert "opted in" in result["reason"]
    assert _jurisdictions(tenant) == set()


def test_a_tenant_with_no_state_is_told_so_rather_than_given_a_guess(
    growth_plan, identity_seam, audit_rows
):
    """No state means no per-state rows, and it says which. It does NOT pick a
    state — a fixture that invents a jurisdiction is inventing where money is
    remitted (BR-TEN-058's own sentence, applied one layer up)."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="silentco"))
    with tenant_ctx(tenant):
        result = services.deliver_state_tax_jurisdictions(tenant, _admin(tenant))
    assert result["delivered"] == 0
    assert result["reason"] == "the tenant records no US state"


def test_a_tenant_that_priced_its_own_taxes_keeps_them(growth_plan, identity_seam, audit_rows):
    """BR-TEN-012 / DEF-273's set-skip: a tenant holding ANY `taxes` row has
    priced its own and is given no rate by a fixture. The jurisdictions may
    still arrive — they are a vocabulary — but not one figure moves."""
    tenant, _ = provisioned_tenant(brazosbend_payload(state=None, subdomain="ownratesco"))
    with tenant_ctx(tenant):
        jurisdiction = rating_models.TaxJurisdiction.objects.filter(
            tenant_id=tenant.id, name="City"
        ).first()
        rating_models.Tax.objects.create(
            tenant_id=tenant.id,
            name="Our own city fee",
            kind="percent",
            rate="0.030000",
            jurisdiction=jurisdiction,
        )
        services.save_regional_settings(_admin(tenant), {"state": "Texas"})
        ours = rating_models.Tax.objects.filter(tenant_id=tenant.id, name="Our own city fee")
        assert ours.count() == 1
        assert ours.first().rate == __import__("decimal").Decimal("0.030000")
        # Nothing the fixture prices was added on top of the tenant's own set.
        assert rating_models.Tax.objects.filter(tenant_id=tenant.id).count() == 1


def test_the_rating_sample_seeder_still_refuses_to_mint_a_jurisdiction():
    """BR-TEN-058, and DEF-444's own sentence: *"the rating seeder must keep
    skipping — it is right"*. The guard is the SOURCE, because a sample run on a
    tenant that now HAS the jurisdictions would pass a behavioural test while
    the forbidden branch sat there waiting for the next tenant that does not."""
    import inspect

    from apps.rating import sample_data

    source = inspect.getsource(sample_data)
    assert "BR-TEN-058" in source
    assert "a run never writes a" in source


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-444 (12-governance/10-defect-log.csv) + BR-TEN-010/012/013/031/037/
#         058/067 + OQ-088 (CLOSED, PO 2026-08-10) + CR-010's tax ruling (PO
#         2026-08-17, the ALL scaffold) + CLAUDE.md hard rules 1 and 7
# generated: 2026-08-21 by the Wave C lane (DEF-400 · DEF-444)
# checklist: A✔ B✔ C✔ D=deferred(no API half — this is provisioning and the S8
#            Regional save, both already served) E=deferred(no frontend half —
#            the screens that were EMPTY now have input; nothing renders
#            differently by design) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the build report on apps/tenancy/services.py
# exceptions: the sign-up form still does not REQUIRE a state — filed rather
#             than changed here, because making a field mandatory on a public
#             screen is a product change and not a lane's call.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
