# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 · US-CWP-070 · US-CWP-071..074 · US-CWP-016..018 — all
#           built, none of them reachable by a provisioned tenant until the two
#           blocks this file guards existed.
# Rules:    PO ruling 2026-09-07, verbatim: *"before step 29 this - you ahve to
#           set all the self service data in settings -> configure -> Customer
#           portal - {overview, branding, Help & Answer, Tips  + service
#           centers }"* · BR-TEN-056/057 · BR-TEN-060 · BR-TEN-063 (a replay
#           writes nothing) · BR-CWP-029 (a credential attaches to a customer
#           ALREADY on file) · CLAUDE.md hard rule 1 (tenant scoping)
# Impacts:  apps/tenancy/portal_sample.py · apps/tenancy/sample_data.py ·
#           apps/portal/sample_data.py · apps/tenancy/published_content_sample.py
# ───────────────────────────────────────────────────────
"""THE PORTAL'S OWN SAMPLE DATA — and the two properties that would hurt
somebody other than this lane.

⚠ **WHY A TEST FILE FOR A FIXTURE, AGAIN.** Nothing was broken; two finished
seeders were simply never named in `SAMPLE_MODULES`, and no check in the
repository asks whether a module that HAS a seeder is registered as a block.
So the properties pinned here are the ones a later lane could silently undo:

  1. **Both blocks are registered, and the configuration runs BEFORE the
     login.** That order is the ruling, not a preference.
  2. **The login enrols a SAMPLE account or it enrols nothing.** This is the
     safety property that lets `SAMPLE_PORTAL_PASSWORD` be written in the open:
     the string opens an invented account on an invented estate. A lane that
     "improved" the chooser to fall back to any account with an email would
     hand a demo password to a real customer's records, and nothing else in the
     repository would notice.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.portal import credentials, models as portal_models, sample_data as portal_sample_data
from apps.tenancy import portal_sample, sample_data as tenancy_sample, seams
from apps.tenancy import published_content_models as content
from core.permissions import SYSTEM_ADMIN
from core.tenancy import tenant_context

from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — pine_hill · sarah · oak_ridge
from tests.test_us_cwp_helpers import elm_street_account

CONTENT_BLOCK = "tenancy:seed_sample_portal_content"
LOGIN_BLOCK = "tenancy:seed_sample_portal_login"


# ══ 1 · the registry ═══════════════════════════════════════════════════════


def test_both_blocks_are_registered_at_all():
    """RED-PROVED by deleting the two `SampleModule(...)` rows:

        AssertionError: the portal's configuration is not a block of the sample
        set, so a provisioned tenant's portal is empty
    """
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert CONTENT_BLOCK in keys, (
        "the portal's configuration is not a block of the sample set, so a "
        "provisioned tenant's portal is empty"
    )
    assert LOGIN_BLOCK in keys, "no seeded customer can sign in to a provisioned tenant's portal"


def test_the_configuration_is_seeded_before_the_login():
    """The Product Owner's own order, and the reason is on screen: a customer
    who signs in to an unconfigured portal sees branding that is not there, no
    answers, no tips and no counter to walk into."""
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert keys.index(CONTENT_BLOCK) < keys.index(LOGIN_BLOCK)


def test_the_login_runs_after_the_accounts_it_enrols():
    """`create_credential` refuses an account with no customer, so a login block
    above `customers:seed_sample_records` could only ever report zero."""
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert keys.index("customers:seed_sample_records") < keys.index(LOGIN_BLOCK)


def test_both_seams_actually_resolve():
    """BR-TEN-060 — a registered block whose seam does not exist is a NAMED
    not-loaded line and turns `run_summary()` red. The row and the seam land in
    ONE commit or the branch is merge-blocked in between."""
    for key in (CONTENT_BLOCK, LOGIN_BLOCK):
        module, seam = key.split(":")
        assert callable(seams.resolve(module, seam)), f"{key} resolves to nothing"


def test_no_block_label_carries_a_rule_id_or_a_screen_id():
    """B14 rule 32. The Sample data panel renders these server labels verbatim
    (`SettingsSampleData.tsx`), so a `BR-` or an `S62` in one reaches a clerk."""
    import re

    forbidden = re.compile(r"\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-\d+|US-[A-Z]{3}-\d+|CWP-\d+)\b")
    for key in (CONTENT_BLOCK, LOGIN_BLOCK):
        spec = next(s for s in tenancy_sample.SAMPLE_MODULES if s.key == key)
        assert not forbidden.search(spec.label), f"{key}: {spec.label!r}"


# ══ 2 · the configuration block ════════════════════════════════════════════


@pytest.fixture()
def owner(pine_hill):
    """The plant's actor shape: a System Admin with no `name`, because
    `_PlantActor` has none."""
    return SimpleNamespace(id=None, pk=None, role=SYSTEM_ADMIN, is_authenticated=True)


def test_the_configuration_block_switches_the_portal_on_and_brands_it(pine_hill, owner):
    with tenant_context(pine_hill.id):
        seeded = portal_sample.seed_sample_portal_content(owner)
        row = portal_models.PortalSettings.objects.get(tenant_id=pine_hill.id)

    #: 1 settings row + 8 answers + 6 tips + 3 centres.
    assert seeded == 18
    assert row.is_live is True
    assert row.strapline == portal_sample_data.SAMPLE_STRAPLINE
    #: The tenant's OWN services — Pine Hill sells four, so four chips.
    assert len(row.front_page_service_ids) == 4
    assert row.office_hours_text
    assert row.emergency_phone

    with tenant_context(pine_hill.id):
        assert content.HelpAnswer.objects.filter(tenant_id=pine_hill.id).count() == 8
        assert content.Tip.objects.filter(tenant_id=pine_hill.id).count() == 6
        assert content.ServiceCentre.objects.filter(tenant_id=pine_hill.id).count() == 3
        #: A counter with no opening hours is not a counter a person can walk
        #: into — 5 weekday rows + 2 closed for the main office, 7 for each of
        #: the other two.
        assert content.ServiceCentreHour.objects.filter(tenant_id=pine_hill.id).count() == 21


def test_a_replay_writes_nothing_and_reports_the_same_number(pine_hill, owner):
    """BR-TEN-063. Idempotent BY REFUSAL, not by replay: a second call would
    mint a second set of slugs.

    ⚠ **THE COUNT IS WHAT THE TENANT HAS, NOT WHAT THIS RUN WROTE**, which is
    how every other block's number on the Sample data panel reads. This case
    first asserted 0 and was wrong about the product rather than about the
    code: a replay that reported 0 would make the panel line drop from 18 to
    nothing on a run that changed nothing at all.
    """
    with tenant_context(pine_hill.id):
        first = portal_sample.seed_sample_portal_content(owner)
        again = portal_sample.seed_sample_portal_content(owner)
        assert first == again == 18
        assert content.HelpAnswer.objects.filter(tenant_id=pine_hill.id).count() == 8
        assert content.Tip.objects.filter(tenant_id=pine_hill.id).count() == 6
        assert content.ServiceCentre.objects.filter(tenant_id=pine_hill.id).count() == 3


def test_a_utilitys_own_strapline_survives_the_replay(pine_hill, sarah, owner):
    """THE REASON THE BLOCK CHECKS FOR A ROW RATHER THAN UPSERTING.

    `save_settings` is an upsert, and the plant can be re-run per block from the
    Sample data panel at any time. A tenant that has opened Settings →
    Configure → Customer portal once already owns that row.
    """
    from apps.portal import settings_service

    with tenant_context(pine_hill.id):
        settings_service.save_branding(sarah, pine_hill.id, {"strapline": "Water for the valley."})
        seeded = portal_sample.seed_sample_portal_content(owner)
        row = portal_models.PortalSettings.objects.get(tenant_id=pine_hill.id)

    assert row.strapline == "Water for the valley."
    #: The CONTENT still lands, and the number is unchanged because it counts
    #: what the tenant HAS: the settings row exists either way.
    assert seeded == 18


def test_the_answers_are_signed_by_the_sample_run_and_not_by_an_invented_colleague(
    pine_hill, owner
):
    """`last_changed_by` is what `CWP-072` shows a clerk. The demo tenants'
    own fixture signs with `Sarah Miller`; a real utility that just signed up
    has never heard of her."""
    with tenant_context(pine_hill.id):
        portal_sample.seed_sample_portal_content(owner)
        signatures = set(
            content.HelpAnswer.objects.filter(tenant_id=pine_hill.id).values_list(
                "last_changed_by", flat=True
            )
        )
    assert signatures == {tenancy_sample.SAMPLE_ALERT_OPERATION}


def test_the_two_tenants_do_not_see_each_others_content(pine_hill, oak_ridge, owner):
    """CLAUDE.md hard rule 1 — the block seeds inside ONE tenant."""
    with tenant_context(pine_hill.id):
        portal_sample.seed_sample_portal_content(owner)
    with tenant_context(oak_ridge.id):
        assert content.HelpAnswer.objects.filter(tenant_id=oak_ridge.id).count() == 0
        assert portal_models.PortalSettings.objects.filter(tenant_id=oak_ridge.id).count() == 0


# ══ 3 · the login block, and the refusal that makes it safe ════════════════


def _account_with_an_email(tenant, actor, *, is_sample: bool):
    """One account a person could sign in to: linked to a customer and holding
    a primary contact with an email."""
    from apps.customers import models as customers_models

    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        customers_models.Account.objects.filter(pk=account.pk).update(is_sample=is_sample)
        customers_models.Contact.objects.update_or_create(
            tenant_id=tenant.id,
            account_id=account.pk,
            is_primary=True,
            defaults={"full_name": "Maria Alvarez", "email": "maria@example.invalid"},
        )
    return account


def test_the_login_block_refuses_an_account_that_is_not_sample_data(pine_hill, sarah, owner):
    """⚠ **THE SAFETY PROPERTY, AND THE ONE TO READ BEFORE CHANGING THE
    CHOOSER.** `SAMPLE_PORTAL_PASSWORD` is written in the open because the
    account it opens is invented. An account a real customer holds is never
    given a seeded password, on any tenant, in any state.

    RED-PROVED by dropping `is_sample=True` from the filter in
    `_sample_account_to_enrol`: this case then enrolled the real account and
    returned 1.
    """
    _account_with_an_email(pine_hill, sarah, is_sample=False)
    with tenant_context(pine_hill.id):
        assert portal_sample.seed_sample_portal_login(owner) == 0
        assert portal_models.PortalCredential.objects.filter(tenant_id=pine_hill.id).count() == 0


def test_the_login_block_enrols_the_sample_account(pine_hill, sarah, owner):
    _account_with_an_email(pine_hill, sarah, is_sample=True)
    with tenant_context(pine_hill.id):
        assert portal_sample.seed_sample_portal_login(owner) == 1
        row = portal_models.PortalCredential.objects.get(tenant_id=pine_hill.id)
        assert row.email == "maria@example.invalid"
        #: Through the product's OWN door, so the password is hashed the way
        #: the portal hashes one and `sign_in` can read it back.
        assert credentials.credential_by_email(pine_hill.id, "maria@example.invalid") is not None


def test_a_replay_does_not_reset_a_password_somebody_has_changed(pine_hill, sarah, owner):
    _account_with_an_email(pine_hill, sarah, is_sample=True)
    with tenant_context(pine_hill.id):
        portal_sample.seed_sample_portal_login(owner)
        before = portal_models.PortalCredential.objects.get(tenant_id=pine_hill.id).password_hash
        credentials.set_password(
            portal_models.PortalCredential.objects.get(tenant_id=pine_hill.id),
            "Chosen-By-Maria-2026",
        )
        assert portal_sample.seed_sample_portal_login(owner) == 0
        after = portal_models.PortalCredential.objects.get(tenant_id=pine_hill.id).password_hash

    assert after != before, "the test did not actually change the password"


def test_the_block_says_who_can_sign_in_without_saying_the_password(pine_hill, sarah, owner):
    """DEF-3224 — a panel reading *seeded, 1* under *A customer who can sign in*
    tells an operator nothing. The note names the address; it never names the
    password, because a note is rendered on a screen and copied into tickets."""
    _account_with_an_email(pine_hill, sarah, is_sample=True)
    with tenant_context(pine_hill.id):
        portal_sample.seed_sample_portal_login(owner)
        note = portal_sample.seed_sample_portal_login_note()

    assert note and "can sign in to the portal" in note
    assert portal_sample_data.SAMPLE_PORTAL_PASSWORD not in note
    #: Masked, because the panel is a screen — `mask_email` is the portal's own.
    assert "maria@example.invalid" not in note


def test_a_tenant_with_no_sample_account_is_told_so_rather_than_left_blank(pine_hill, owner):
    with tenant_context(pine_hill.id):
        assert portal_sample.seed_sample_portal_login(owner) == 0
        note = portal_sample.seed_sample_portal_login_note()
    assert note and "no sample account" in note.lower()


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 (the portal's self-service data, before the login)
# generated: 2026-09-07 by the portal sample-data lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cwp_sample_portal.py · the browser walkthrough in 10-scripts/cwp_sample_portal_walkthrough.mjs
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
