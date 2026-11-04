# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T2 / C7 — "Organisation type — column, seed, settings field"
# Story:    US-TEN-005 (S8 Company profile)   Screens: S8
# Rules:    BR-TEN-1050 (MINTED with this change: the type, its three values,
#           its seeded default, and what each type shows) · BR-TEN-024 (the
#           whole tab commits atomically with ONE audit row) · BR-LED-028 (the
#           three customer kinds the PO named)
# Golden:   C7's own proof, in its own words — "Default is `utility` for a new
#           tenant AND for an existing one" and "an unknown value falls back
#           rather than erroring"
# ───────────────────────────────────────────────────────
"""CR-060 T2 — the one field C8 and C9 read, and the three states it survives.

**WHY THE FALLBACK CASES ARE HALF THIS FILE.** The column carries no CHECK
constraint (tenancy 0029 argues that choice out), so *"an unknown value falls
back rather than erroring"* is a promise made by a Python function and not by
the database. A promise like that is exactly the kind hard-won law 1 warns
about — a comment claiming a guarantee is not the guarantee — so it is asserted
here against a row written directly past the service.

WHAT RUNS WHERE. Everything here runs on SQLite and Postgres alike: it is a
column, a vocabulary and a save path, with no aborted-transaction behaviour and
no RLS predicate in play. The MIGRATION's own forward/reverse proof against a
real PostgreSQL 16.13 holding 15 `tenant_settings` rows is recorded in the
migration's `gates:` trailer and in the human-review-ledger row, which is where
a database-shaped claim belongs.
"""

import pytest

from apps.tenancy import models, selectors, services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── the seed (C7's first proof) ─────────────────────────────────────────────
def test_cr060_t2__a_new_tenant_is_seeded_utility(growth_plan, identity_seam):
    """*"Seed it to `utility` at provisioning rather than leaving it null."*"""
    tenant, _ = provisioned_tenant()
    row = models.TenantSettings.objects.get(tenant_id=tenant.id)
    assert row.organisation_type == "utility"
    with tenant_ctx(tenant):
        assert selectors.organisation_type() == "utility"
        assert selectors.company_profile()["organisation_type"] == "utility"


def test_cr060_t2__the_column_default_covers_a_row_the_seeder_never_touched(
    growth_plan, identity_seam
):
    """Hard-won law 4 — the SECOND half of C7's *"and for an existing one"*.

    `provision_tenant` names the value explicitly, so this asserts the other
    path: a `TenantSettings` row created without mentioning the field at all,
    which is what tenancy 0029's `AddField(default=...)` writes onto every row
    that already existed on a live host.
    """
    tenant, _ = provisioned_tenant(lonestarridge_payload())
    models.TenantSettings.objects.filter(tenant_id=tenant.id).delete()
    bare = models.TenantSettings.objects.create(tenant_id=tenant.id)
    assert bare.organisation_type == "utility"


# ── the three values, and the refusals around them ──────────────────────────
def test_cr060_t2__the_vocabulary_is_exactly_three():
    assert models.ORGANISATION_TYPES == ("utility", "sub_metering", "hoa")


@pytest.mark.parametrize("chosen", ["sub_metering", "hoa"])
def test_cr060_t2__each_value_saves_from_the_company_tab(
    growth_plan, identity_seam, audit_rows, chosen
):
    """C7's placement ruling, exercised: the field is set on Company → Profile,
    beside legal name and DBA, through the tab's own atomic save.

    `utility` is not in the parameters because it is the SEEDED value and would
    be a no-op — its own case is the next test, which is the more interesting
    one anyway.
    """
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    actor = admin_actor()
    with tenant_ctx(tenant):
        result = services.save_company_profile(
            actor, {"legal_name": "Bayou Bend Submetering LLC", "organisation_type": chosen}
        )
    assert result["organisation_type"] == chosen
    assert models.TenantSettings.objects.get(tenant_id=tenant.id).organisation_type == chosen
    # BR-TEN-024 — the whole tab is ONE audit row even though it wrote two rows.
    written = [row for row in audit_rows if row["action"] == "settings.company_profile.updated"]
    assert len(written) == 1
    assert written[0]["after"]["organisation_type"] == chosen
    assert written[0]["before"]["organisation_type"] == "utility"
    assert written[0]["after"]["legal_name"] == "Bayou Bend Submetering LLC"


def test_cr060_t2__re_saving_the_same_type_writes_no_settings_change(
    growth_plan, identity_seam, audit_rows
):
    """BR-TEN-024's audit is the CHANGE, not the payload. Sending `utility` at a
    tenant that already reads `utility` must leave the field out of the trail —
    otherwise every unrelated save on this tab logs a change nobody made."""
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    with tenant_ctx(tenant):
        services.save_company_profile(
            admin_actor(), {"legal_name": "Brazos Bend Utility District No. 1",
                            "organisation_type": "utility"}
        )
    written = [row for row in audit_rows if row["action"] == "settings.company_profile.updated"]
    assert len(written) == 1
    assert "organisation_type" not in written[0]["after"]
    assert models.TenantSettings.objects.get(tenant_id=tenant.id).organisation_type == "utility"


def test_cr060_t2__an_unknown_type_is_refused_by_the_save(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as raised:
            services.save_company_profile(admin_actor(), {"organisation_type": "landlord"})
    assert {fe["field"] for fe in raised.value.field_errors} == {"organisation_type"}
    assert (
        raised.value.field_errors[0]["message_key"]
        == "settings.company.organisationTypeUnknown"
    )
    # The refusal names what IS allowed — B12 §3's shape, and the reason a clerk
    # does not have to guess a fourth spelling.
    assert raised.value.field_errors[0]["params"]["allowed"] == list(models.ORGANISATION_TYPES)
    assert models.TenantSettings.objects.get(tenant_id=tenant.id).organisation_type == "utility"


def test_cr060_t2__it_cannot_be_cleared_to_nothing(growth_plan, identity_seam):
    """Every other field on this tab clears to None. This one refuses, because
    the whole point of the seeded default is that no tenant is ever unknown."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError):
            services.save_company_profile(admin_actor(), {"organisation_type": ""})
    assert models.TenantSettings.objects.get(tenant_id=tenant.id).organisation_type == "utility"


# ── the fallback (C7/C8's second proof) ─────────────────────────────────────
def test_cr060_t2__an_unknown_stored_value_falls_back_and_does_not_error(
    growth_plan, identity_seam
):
    """*"an unknown value falls back rather than erroring"* — CR-060 C7 proof 3.

    Written PAST the service on purpose. The service refuses this value (the
    test above), so the only way a row can hold it is an import, a future
    migration or a fourth type rolled back — and the promise is that a Settings
    page still loads.
    """
    tenant, _ = provisioned_tenant()
    models.TenantSettings.objects.filter(tenant_id=tenant.id).update(
        organisation_type="cooperative"
    )
    with tenant_ctx(tenant):
        assert selectors.organisation_type() == "utility"
        assert selectors.company_profile()["organisation_type"] == "utility"


def test_cr060_t2__no_settings_row_at_all_falls_back_too(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    models.TenantSettings.objects.filter(tenant_id=tenant.id).delete()
    with tenant_ctx(tenant):
        assert selectors.organisation_type() == "utility"


# ── hard rule 1 — the answer is per tenant, never global ────────────────────
def test_cr060_t2__two_tenants_hold_two_different_types(growth_plan, identity_seam):
    utility, _ = provisioned_tenant()
    submeter, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(submeter):
        services.save_company_profile(admin_actor(), {"organisation_type": "sub_metering"})
    with tenant_ctx(utility):
        assert selectors.organisation_type() == "utility"
    with tenant_ctx(submeter):
        assert selectors.organisation_type() == "sub_metering"


# ── the field is on the COMPANY tab and NOT on Regional ─────────────────────
def test_cr060_t2__regional_does_not_accept_it(growth_plan, identity_seam):
    """C7 placed it on Company → Profile. A field accepted on two tabs is two
    save paths that can disagree, so Regional refuses it by name."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError):
            services.save_regional_settings(admin_actor(), {"organisation_type": "hoa"})


# ── §0c FINDING 1 — what this task deliberately did NOT do ──────────────────
def test_cr060_t2__accounting_method_is_still_here(growth_plan, identity_seam):
    """CR-060 §9's table asks C6 to retire `accounting_method` in THIS
    migration. §0c finding 1 shows it has a live reader and a latent defect
    underneath it, and C6 has no task row in §12 — so it stays, and this test
    is the standing record of that decision rather than a comment nobody reads.
    """
    assert hasattr(models.TenantSettings, "accounting_method")
    tenant, _ = provisioned_tenant()
    row = models.TenantSettings.objects.get(tenant_id=tenant.id)
    # CR-008 ruling 1 — still deliberately unset at provisioning, unchanged.
    assert row.accounting_method is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T2@organisation-type (12-governance/11-change-requests.md CR-060 §7 C7 + §9's `tenant_settings` row + §0c finding 1 + the T2 row in §12 · 04-docs/05-modules/01-tenancy/02-business-rules.md BR-TEN-1050/BR-TEN-024 · apps/tenancy/models.py TenantSettings)
# generated: 2026-09-01 by the CR-060 T2/T3/T4 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN, and the failure is quoted AS OBSERVED rather
#         than as predicted (DEF-182). **The COLUMN default removed from the
#         model** (`TextField(null=True, blank=True)`, migration untouched) —
#         `..._the_column_default_covers_a_row_the_seeder_never_touched` fails:
#             `django.db.utils.IntegrityError: NOT NULL constraint failed:
#              tenant_settings.organisation_type`
#         which is the sharper failure than the `assert None == 'utility'` that
#         was predicted: with no model default Django sends NULL and the column
#         the migration declared refuses it outright. The fallback case passed
#         under the same mutation, CORRECTLY — `selectors.organisation_type`
#         does not depend on the model default, and a red there would have meant
#         the two cases were testing one thing.
# exceptions: the migration's own forward/reverse proof on real PostgreSQL is
#         recorded in the migration trailer and the review-ledger row, not here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
