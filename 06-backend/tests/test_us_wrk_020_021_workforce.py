# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-020 (crews, technicians and their skills — a profile beside
#           an identity, never a second identity) · US-WRK-021 (the crews
#           screen, the technician detail, the skills wizard and the
#           certification watch) · US-WRK-022 (who may accept) ·
#           US-WRK-023 (a Field technician's login is web-blocked)
# Rules:    BR-WRK-028 · BR-WRK-029 · BR-WRK-030 (ruled per-tenant 2026-09-04,
#           OQ-WRK-1493) · BR-WRK-043 (OQ-WRK-1494, ruled option (a)) ·
#           BR-WRK-044 (OQ-WRK-1492, ruled — a clerk may accept) ·
#           CLAUDE.md hard rule 1 (tenant isolation) · hard rule 7 (audit)
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-020 · 021 · 022 · 023 — the workforce and the two access rulings.

⚠ **THE THREE QUESTIONS THIS WAVE WAS PLANNED TO STUB WERE ALL RULED ON
2026-09-04, THE DAY AFTER THE PLAN WAS WRITTEN.** `10-execution-plan.md`'s
wave F still says *"each to its boundary"* and names three
`NotImplementedError` stubs; the register says `OQ-WRK-1492`, `1493` and
`1494` are CLOSED. r11 step 0 is what caught it, and the behaviour asserted
below is the RULED behaviour rather than the stub.

⚠ **THE RLS HALF IS NOT HERE AND CANNOT BE.** `config/settings/test.py`
hardcodes in-memory SQLite, which has no row-level security at all, so an RLS
assertion here would pass by vacuum (hard-won law 14, one rule along). The
isolation cases below are the APPLICATION-layer proof; the DATABASE-layer proof
is `tests/test_us_wrk_rls_pg.py` on real PostgreSQL 16.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from apps.identity import models as identity_models
from apps.identity import selectors as identity_selectors
from apps.identity import services as identity_services
from apps.tenancy import models as tenancy_models
from apps.work import models as work_models
from apps.work import workforce
from apps.work.seams import identity_seam as work_identity_seam
from core import errors

# ⚠ THE WILDCARD BRINGS A PYTEST FIXTURE CALLED `identity_seam`, WHICH SHADOWS
# THE MODULE OF THE SAME NAME — the seam is imported above under an alias for
# exactly that reason. Without it, `identity_seam.may(...)` reads the fixture
# and raises `'FixtureFunctionDefinition' object has no attribute 'may'`.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def real_audit_trail():
    """Put audit's REAL sink back for one test.

    ⚠ **`tests/test_us_met_helpers.py` installs an autouse sink that CAPTURES
    audit rows into a list**, so no test in this family writes `audit_log` at
    all — which is right for every other case here and exactly wrong for the
    one that asks whether hard rule 7 is met. Without this the table is empty
    and an assertion phrased the other way round (*"no forbidden action
    appears"*) would be green over a product that writes no trail.

    Copied rather than shared because the fixture lives in
    `test_w6_connection_detail.py` and is not exported by the helpers module;
    moving it is a change to a file two other lanes are in today.
    """
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)



def _user(tenant, email, name, *, role="billing_clerk", scope="both"):
    """A real `identity.User` + membership — `technicians.user_id` is a reviewed
    cross-module FK, so a synthetic uuid would not be lawful (B2 §2)."""
    role_row = identity_models.Role.objects.get(code=role)
    user = identity_models.User.objects.create(
        tenant=tenant, email=email, full_name=name, surface_scope=scope
    )
    identity_models.TenantMembership.objects.create(
        tenant=tenant, user=user, role=role_row, status="active"
    )
    return user


def _skill(tenant, code, name):
    return work_models.WorkSkill.objects.create(tenant=tenant, code=code, name=name)


def _cert_type(tenant, code, name):
    return tenancy_models.CertificationType.objects.create(tenant=tenant, code=code, name=name)


def _technician(tenant, actor, user, **over):
    payload = {
        "user_id": str(user.id),
        "role_label": "Field technician",
        "shift_start": "07:00",
        "shift_end": "16:00",
        **over,
    }
    return workforce.create_technician(actor, payload)


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-020 — a profile beside an identity, never a second identity
# ══════════════════════════════════════════════════════════════════════════


def test_tc1_a_technician_is_a_profile_beside_an_existing_login(brazos, dana):
    with tenant_ctx(brazos):
        ortiz = _user(brazos, "dortiz@brazosbendutilities.test", "D. Ortiz")
        detail = _technician(brazos, dana, ortiz)
        assert detail["name"] == "D. Ortiz"
        assert detail["slug"] == "d-ortiz"
        row = work_models.Technician.objects.get(tenant=brazos, user=ortiz)
        assert row.role_label == "Field technician"
        assert row.shift_start == time(7, 0)


def test_tc2_negative_a_technician_for_a_user_that_does_not_exist_is_refused(brazos, dana):
    """⚠ **THE REFUSAL IS THE STORY** (`BR-WRK-028`).

    A second place to create a person would be a second place to invite,
    deactivate, password-reset and audit them — the same argument the Product
    Owner used on 2026-09-04 to keep field technicians in the ONE `users` table
    rather than a table of their own.
    """
    import uuid

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            workforce.create_technician(dana, {"user_id": str(uuid.uuid4())})
        assert caught.value.message_key == "work.technician_needs_login"


def test_tc3_a_crew_and_a_contractor_are_rows_in_the_same_table_as_a_person(brazos, dana):
    """*"Whoever the work is offered to, the skill match is the same test."*"""
    with tenant_ctx(brazos):
        ortiz = _user(brazos, "dortiz@brazosbendutilities.test", "D. Ortiz")
        _technician(brazos, dana, ortiz)
        workforce.create_crew(
            dana, {"name": "Crew B", "kind": "crew", "headcount": 3, "role_label": "Network crew"}
        )
        workforce.create_crew(
            dana,
            {"name": "Apex Utility Svc", "kind": "contractor", "role_label": "Contractor"},
        )
        page = workforce.crews_page()

    assert page["counts"] == {
        "technicians": 1, "crews": 1, "contractors": 1, "rows": 3, "people": 1,
    }
    names = [row["name"] for row in page["rows"]]
    # People first, then crews, then contractors — the drawing's own order.
    # `CR-168-BRC10` P3.44: the bracket is the COUNTED members, and nobody is on
    # Crew B, so the typed headcount of 3 no longer shows.
    assert names == ["D. Ortiz", "Crew B", "Apex Utility Svc"]
    assert page["rows"][1]["members"] == 0
    # A contractor has no shift: `WS-23` writes *by arrangement*, an absence.
    assert page["rows"][2]["shift"] is None


def test_tc4_negative_the_skill_match_offers_only_a_skill_match(brazos, dana):
    """`BR-WRK-029` — offer *Meter exchange* (Meter fitting) and R. Patel, who
    holds Water I and Reads, is not among the candidates."""
    with tenant_ctx(brazos):
        meter_fitting = _skill(brazos, "METERFIT", "Meter fitting")
        water_one = _skill(brazos, "WATER1", "Water I")
        ortiz = _user(brazos, "dortiz@brazosbendutilities.test", "D. Ortiz")
        patel = _user(brazos, "rpatel@brazosbendutilities.test", "R. Patel")
        ortiz_row = _technician(brazos, dana, ortiz)
        patel_row = _technician(brazos, dana, patel)
        workforce.set_skills(
            dana,
            ortiz_row["id"],
            {"skills": [{"skill_id": str(meter_fitting.id), "proficiency": "certified"}]},
        )
        workforce.set_skills(
            dana,
            patel_row["id"],
            {"skills": [{"skill_id": str(water_one.id), "proficiency": "certified"}]},
        )
        match = workforce.skill_match(skill_id=meter_fitting.id)

    assert [row["name"] for row in match["candidates"]] == ["D. Ortiz"]


def test_tc5_set_unavailable_is_what_a_supervisor_gets_instead_of_delete(brazos, dana):
    with tenant_ctx(brazos):
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        row = _technician(brazos, dana, kaur)
        after = workforce.set_unavailable(dana, row["id"], {"reason": "On leave"})
        assert after["status"] == "unavailable"
        assert after["unavailable_reason"] == "On leave"
        # And the way back is the same endpoint, not a second one nobody finds.
        back = workforce.set_unavailable(dana, row["id"], {"status": "on_shift"})
        assert back["status"] == "on_shift"
        assert back["unavailable_reason"] is None
        # The row still exists — nothing was deleted.
        assert work_models.Technician.objects.filter(tenant=brazos, user=kaur).exists()


def test_tc6_tenant_isolation_the_other_utility_sees_none_of_these_rows(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        ortiz = _user(brazos, "dortiz@brazosbendutilities.test", "D. Ortiz")
        _technician(brazos, dana, ortiz)
        assert workforce.crews_page()["counts"]["rows"] == 1
    with tenant_ctx(lonestar):
        assert workforce.crews_page()["counts"]["rows"] == 0
        # And the slug answers None — 404 at the route, identical to an id that
        # does not exist (hard rule 1: never an existence oracle).
        assert workforce.technician_by_slug("d-ortiz") is None


def test_a_second_profile_for_one_login_is_refused(brazos, dana):
    """Two profiles for one login would give a dispatcher two D. Ortizes, each
    with half his skills, and no way to tell which the skill match used."""
    with tenant_ctx(brazos):
        ortiz = _user(brazos, "dortiz@brazosbendutilities.test", "D. Ortiz")
        _technician(brazos, dana, ortiz)
        with pytest.raises(errors.BizError) as caught:
            _technician(brazos, dana, ortiz)
        assert caught.value.br_ref == "BR-WRK-028"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-021 — the watch, the wizard and the *Not held* rows
# ══════════════════════════════════════════════════════════════════════════


def test_tc7_the_not_held_rows_are_derived_and_stored_nowhere(brazos, dana):
    """`WS-24`'s *Water II · Not held* row is the tenant's catalogue MINUS what
    the person holds — so a skill added in Settings appears the same day."""
    with tenant_ctx(brazos):
        water_one = _skill(brazos, "LANEW1", "Lane Water I")
        _skill(brazos, "LANEW2", "Lane Water II")
        patel = _user(brazos, "rpatel@brazosbendutilities.test", "R. Patel")
        row = _technician(brazos, dana, patel)
        detail = workforce.set_skills(
            dana,
            row["id"],
            {"skills": [{"skill_id": str(water_one.id), "proficiency": "certified"}]},
        )

    # ⚠ THE PANEL LISTS THE TENANT'S WHOLE CATALOGUE — a provisioned utility
    # already has a seeded skill list, so the assertion is over the two rows
    # this test made rather than over a count that would move under a seed.
    by_name = {skill["name"]: skill["proficiency"] for skill in detail["skills"]}
    assert by_name["Lane Water I"] == "certified"
    assert by_name["Lane Water II"] == "not_held"
    # Every OTHER skill the utility has is *not held* too, and none of them is
    # a stored row: `not_held` is the ABSENCE of one.
    assert all(
        value == "not_held" for name, value in by_name.items() if name != "Lane Water I"
    )
    assert work_models.TechnicianSkill.objects.count() == 1


def test_not_held_is_refused_by_name_if_a_caller_sends_it_back(brazos, dana):
    """It is an ABSENCE, not a third proficiency. Storing it quietly would give
    the product two ways to answer *does she hold Water II*."""
    with tenant_ctx(brazos):
        water_two = _skill(brazos, "WATER2", "Water II")
        patel = _user(brazos, "rpatel@brazosbendutilities.test", "R. Patel")
        row = _technician(brazos, dana, patel)
        with pytest.raises(errors.ValidationError) as caught:
            workforce.set_skills(
                dana,
                row["id"],
                {"skills": [{"skill_id": str(water_two.id), "proficiency": "not_held"}]},
            )
        assert caught.value.message_key == "work.proficiency_unknown"


def test_tc2_the_watch_names_the_person_the_certification_and_the_date(brazos, dana):
    with tenant_ctx(brazos):
        confined = _cert_type(brazos, "CONFINED", "Confined space")
        hv = _cert_type(brazos, "HV", "HV awareness")
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        chen = _user(brazos, "mchen@brazosbendutilities.test", "M. Chen")
        kaur_row = _technician(brazos, dana, kaur)
        chen_row = _technician(brazos, dana, chen)
        workforce.set_certifications(
            dana,
            kaur_row["id"],
            {
                "certifications": [
                    {"certification_type_id": str(confined.id), "expires_on": "2026-08-20"}
                ]
            },
        )
        workforce.set_certifications(
            dana,
            chen_row["id"],
            {"certifications": [{"certification_type_id": str(hv.id), "expires_on": "2026-09-30"}]},
        )
        watch = workforce.certification_watch(today=date(2026, 8, 1))

    windows = {window["days"]: window["entries"] for window in watch["windows"]}
    assert windows[30][0]["technician"] == "J. Kaur"
    assert windows[30][0]["certification"] == "Confined space"
    assert windows[30][0]["expires_on"] == "2026-08-20"
    assert windows[60][0]["technician"] == "M. Chen"


def test_tc3_the_default_tenant_blocks_nothing_and_says_so(brazos, dana):
    """⚠ **`OQ-WRK-1493` WAS RULED ON 2026-09-04 — option (c), PER-TENANT,
    DEFAULT WARN.** The wave plan says a `NotImplementedError` sits where a
    refusal would; the ruling replaced it with a setting. A tenant that has
    never touched it reads `warn`, and NOTHING is refused.
    """
    with tenant_ctx(brazos):
        confined = _cert_type(brazos, "CONFINED", "Confined space")
        skill = _skill(brazos, "WATER1", "Water I")
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        row = _technician(brazos, dana, kaur)
        workforce.set_skills(
            dana, row["id"], {"skills": [{"skill_id": str(skill.id), "proficiency": "trained"}]}
        )
        workforce.set_certifications(
            dana,
            row["id"],
            {
                "certifications": [
                    {"certification_type_id": str(confined.id), "expires_on": "2026-08-20"}
                ]
            },
        )
        # A tenant with no `work_settings` row reads the seeded default.
        assert workforce.lapse_policy() == "warn"
        assert work_models.WorkSettings.objects.filter(tenant=brazos).exists() is False
        watch = workforce.certification_watch(today=date(2026, 8, 21))
        assert watch["policy"] == "warn"
        assert watch["blocks"] is False
        # 21 August: her certification lapsed YESTERDAY and she is still
        # offered the job — a two-technician utility has to be able to send
        # her.
        match = workforce.skill_match(skill_id=skill.id, on=date(2026, 8, 21))
        assert match["policy"] == "warn"
        assert match["candidates"][0]["eligible"] is True
        assert match["candidates"][0]["lapsed"][0]["certification"] == "Confined space"


def test_tc3_the_other_half_is_RETIRED_a_lapse_only_warns_for_every_tenant(brazos, dana):
    """⚠ **REWRITTEN TO THE RULING, 2026-10-04 (`CR-168-BRC10` P4.5).** This
    case proved the `block` side of `BR-WRK-030`'s per-tenant switch. PO answer
    2 of 2026-10-04, verbatim *"(a) Warn only, the same as skills"*, SUPERSEDES
    it for every tenant: the switch is refused `work.settings.lapse_policy_retired`
    and J. Kaur, whose certificate lapsed the day before, is still offered."""
    with tenant_ctx(brazos):
        confined = _cert_type(brazos, "CONFINED", "Confined space")
        skill = _skill(brazos, "WATER1", "Water I")
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        row = _technician(brazos, dana, kaur)
        workforce.set_skills(
            dana, row["id"], {"skills": [{"skill_id": str(skill.id), "proficiency": "trained"}]}
        )
        workforce.set_certifications(
            dana,
            row["id"],
            {
                "certifications": [
                    {"certification_type_id": str(confined.id), "expires_on": "2026-08-20"}
                ]
            },
        )
        with pytest.raises(errors.ValidationError) as caught:
            workforce.set_lapse_policy(dana, "block")
        assert caught.value.message_key == "work.settings.lapse_policy_retired"
        assert workforce.lapse_policy() == "warn"
        match = workforce.skill_match(skill_id=skill.id, on=date(2026, 8, 21))
        assert match["candidates"][0]["eligible"] is True
        assert match["candidates"][0]["lapsed"]
        assert workforce.certification_watch(today=date(2026, 8, 21))["blocks"] is False


def test_tc5_a_certification_that_already_expired_is_ACCEPTED_at_entry(brazos, dana):
    """Refusing it would lose the record of a lapse, which is the one thing the
    watch exists to show."""
    with tenant_ctx(brazos):
        confined = _cert_type(brazos, "CONFINED", "Confined space")
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        row = _technician(brazos, dana, kaur)
        detail = workforce.set_certifications(
            dana,
            row["id"],
            {
                "certifications": [
                    {"certification_type_id": str(confined.id), "expires_on": "2020-01-01"}
                ]
            },
        )
        assert detail["certifications"][0]["expires_on"] == "2020-01-01"


def test_tc6_tenant_isolation_the_slug_is_per_tenant(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        patel = _user(brazos, "rpatel@brazosbendutilities.test", "R. Patel")
        _technician(brazos, dana, patel)
        assert workforce.technician_by_slug("r-patel") is not None
    with tenant_ctx(lonestar):
        # A DIFFERENT R. Patel at the other utility is a different person, and
        # neither one's slug reaches the other.
        assert workforce.technician_by_slug("r-patel") is None


def test_tc7_a_certification_type_comes_from_tenancy_and_work_keeps_no_second_list(brazos, dana):
    with tenant_ctx(brazos):
        kaur = _user(brazos, "jkaur@brazosbendutilities.test", "J. Kaur")
        row = _technician(brazos, dana, kaur)
        import uuid

        with pytest.raises(errors.ValidationError) as caught:
            workforce.set_certifications(
                dana,
                row["id"],
                {"certifications": [{"certification_type_id": str(uuid.uuid4())}]},
            )
        assert caught.value.message_key == "work.certification_unknown"


def test_every_workforce_write_lands_an_audit_row(brazos, dana, real_audit_trail):
    """CLAUDE.md hard rule 7 — and the skills write carries BOTH sides, so
    *what did she hold before* is answerable.

    ⚠ **IT ASKS FOR `real_audit_trail`, AND WITHOUT IT THIS TEST PASSES OVER
    NOTHING.** The default sink in the suite does not INSERT, so
    `AuditLog.objects` answers an empty set and an assertion phrased as *"no
    forbidden action appears"* would be green on a product that writes no
    trail at all. This one asserts the rows are PRESENT, which is the
    direction that cannot pass by vacuum.
    """
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        skill = _skill(brazos, "WATER1", "Water I")
        patel = _user(brazos, "rpatel@brazosbendutilities.test", "R. Patel")
        row = _technician(brazos, dana, patel)
        workforce.set_skills(
            dana, row["id"], {"skills": [{"skill_id": str(skill.id), "proficiency": "trained"}]}
        )
        actions = set(
            audit_models.AuditLog.objects.filter(tenant_id=brazos.id).values_list(
                "action", flat=True
            )
        )
    assert "work.technician.created" in actions
    assert "work.technician.skills_set" in actions


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-022 — who may accept (OQ-WRK-1492, RULED 2026-09-04)
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_022_the_permission_is_declared_and_the_office_roles_hold_it(brazos):
    """⚠ **TC-2 AND TC-3 BOTH INVERT, AND THE REGISTER SAYS SO.**

    The story as written says the permission is *"declared … and assigned to no
    role"*, and that a test asserting a clerk is refused is marked xfail. The
    Product Owner ruled on 2026-09-04: *"clark can do it sicne it s a day to day
    work"*. So the permission is HELD by the three office roles and the case
    worth asserting is the one below it.
    """
    assert identity_models.Permission.objects.filter(code="work_accept").exists()
    for role in ("system_admin", "billing_clerk", "executive"):
        assert identity_selectors.role_holds(role, "work_accept") is True


def test_us_wrk_022_a_field_technician_does_not_hold_it_and_needs_no_second_check(brazos):
    """`BR-WRK-044`: a technician is excluded by `BR-WRK-043`'s SURFACE SCOPE
    rather than by a rule of its own — the Accept control is on the web app and
    their login does not reach it. What is asserted here is only that the role
    holds nothing, which is the database saying what a comment would otherwise
    claim."""
    assert identity_selectors.role_holds("field_technician", "work_accept") is False
    granted = identity_models.RolePermission.objects.filter(
        role__code="field_technician"
    ).count()
    assert granted == 0


def test_us_wrk_022_may_resolves_from_the_catalogue_and_grants_nothing_itself(brazos):
    from types import SimpleNamespace

    with tenant_ctx(brazos):
        assert work_identity_seam.may(SimpleNamespace(role="billing_clerk"), "work_accept") is True
        assert work_identity_seam.may(SimpleNamespace(role="field_technician"), "work_accept") is False
        # Deny-by-default: an unknown or absent role is a role with NOTHING.
        assert work_identity_seam.may(SimpleNamespace(role=None), "work_accept") is False
        assert work_identity_seam.may(SimpleNamespace(role="nonsense"), "work_accept") is False


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-023 — one login, one surface (OQ-WRK-1494, RULED 2026-09-04)
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_023_the_role_exists_and_holds_no_staff_permission(brazos):
    assert identity_models.Role.objects.filter(code="field_technician").exists()
    matrix = identity_selectors.roles_matrix()
    assert [row["code"] for row in matrix["roles"]][-1] == "field_technician"
    # Nine signed A4 rows, nine dashes. The database saying it, not a comment.
    assert {row["cells"]["field_technician"] for row in matrix["permissions"]} == {"—"}


def test_us_wrk_023_tc1_a_technician_is_invited_into_the_ONE_users_table(brazos):
    """⚠ **THE PO ASKED US A QUESTION BACK AND THE ANSWER IS THIS TABLE.**
    *"will you keep them in user table?"* — yes. A technician is invited,
    deactivated, password-reset and audited exactly like a clerk, and a second
    table would fork all four of those flows for one role."""
    with tenant_ctx(brazos):
        osei = _user(
            brazos,
            "tosei@brazosbendutilities.test",
            "T. Osei",
            role="field_technician",
            scope="mobile",
        )
    assert osei.surface_scope == "mobile"
    assert identity_models.User.objects.filter(pk=osei.pk).exists()


def test_us_wrk_023_tc2_the_web_sign_in_is_REFUSED_with_its_own_six_word_sentence(brazos):
    """⚠ **THIS TEST WAS PLANNED AS AN XFAIL AND IT IS GREEN.** The story says
    *"Lands on the dashboard today"* with a stub raising `OQ-WRK-1494`; that
    question was ruled option (a) on 2026-09-04 and the refusal is real.

    ⚠ **AND THE SENTENCE IS SIX WORDS, NOT r10's SEVEN** — B14 rule 33 caps a
    refusal at five or six, and *"This login is for the field app"* is seven.
    """
    from django.contrib.auth.hashers import make_password

    with tenant_ctx(brazos):
        osei = _user(
            brazos,
            "tosei@brazosbendutilities.test",
            "T. Osei",
            role="field_technician",
            scope="mobile",
        )
        osei.password_hash = make_password("Prairie2026grass")
        osei.save(update_fields=["password_hash"])

        with pytest.raises(errors.AuthError) as caught:
            identity_services.sign_in(
                tenant_id=brazos.id,
                email="tosei@brazosbendutilities.test",
                password="Prairie2026grass",
                surface="web",
            )
        assert caught.value.br_ref == "BR-WRK-043"
        assert caught.value.message_key == "identity.signIn.fieldAppOnly"

        # ⚠ AND THE SAME CREDENTIALS WORK ON THE PHONE. A refusal that also
        # refused the phone would be a lockout, not a scope.
        session = identity_services.sign_in(
            tenant_id=brazos.id,
            email="tosei@brazosbendutilities.test",
            password="Prairie2026grass",
            surface="mobile",
        )
        assert session.user_id == osei.id


def test_us_wrk_023_an_existing_login_is_unaffected_by_the_new_column(brazos):
    """`surface_scope` defaults to `both`, so the column changed NOTHING for
    anybody on the day it landed — which is the whole of its migration story."""
    from django.contrib.auth.hashers import make_password

    with tenant_ctx(brazos):
        priya = _user(brazos, "priya@brazosbendutilities.test", "Priya Menon")
        assert priya.surface_scope == "both"
        priya.password_hash = make_password("Meadow2026sage")
        priya.save(update_fields=["password_hash"])
        for surface in ("web", "mobile"):
            assert (
                identity_services.sign_in(
                    tenant_id=brazos.id,
                    email="priya@brazosbendutilities.test",
                    password="Meadow2026sage",
                    surface=surface,
                ).user_id
                == priya.id
            )


def test_us_wrk_023_tc4_a_field_technician_is_not_a_staff_role_for_any_endpoint(brazos):
    """`core.permissions.ROLES` is the three OFFICE roles, so `_role_of`
    answers None for a technician and every role-gated endpoint refuses.

    ⚠ ADDING THE FOURTH ROLE TO THAT FROZENSET WOULD HAVE GRANTED IT EVERY READ
    SURFACE IN THE PRODUCT IN ONE LINE — `AnyTenantRole` is that same set.
    """
    from core import permissions as core_permissions

    assert "field_technician" not in core_permissions.ROLES
    assert core_permissions.ROLES == {"system_admin", "billing_clerk", "executive"}
