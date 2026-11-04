# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — the six server gaps lane CREWS
#           reported (CR §19): member names, a job's completion time, a
#           certificate's proof, the crew on the add-member picker, one atomic
#           *Add a crew*, and badges that count the utility. Images 26, 27, 29,
#           32, 33.
# Rules:    NFR-3 (the picker pages in SQL) · CLAUDE.md hard rules 1 and 7
# ───────────────────────────────────────────────────────
"""What the Crews screens drew and the server did not yet serve."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import technician_figures, workforce
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _login(tenant, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=name)
    role = identity_models.Role.objects.get(code="field_technician")
    identity_models.TenantMembership.objects.create(
        tenant=tenant, user=user, role=role, status="active"
    )
    return user


def _world(tenant):
    a = work_models.Crew.objects.create(tenant=tenant, name="Field crew A", kind="crew")
    ortiz = work_models.Technician.objects.create(
        tenant=tenant, user=_login(tenant, "dortiz@b.test", "D. Ortiz"), crew=a
    )
    patel = work_models.Technician.objects.create(
        tenant=tenant, user=_login(tenant, "rpatel@b.test", "R. Patel"), crew=a
    )
    sam = _login(tenant, "sreyes@b.test", "Sam Reyes")
    return {"a": a, "ortiz": ortiz, "patel": patel, "sam": sam}


# ── gap 1 · a crew row names its members (image 27) ────────────────────────
def test_gap1_a_crew_row_names_its_members(brazos, dana):
    """RED on the tip: ``KeyError: 'member_names'`` — only the count was served."""
    with tenant_ctx(brazos):
        _world(brazos)
        row = workforce.crews_page(view="crews")["rows"][0]
    assert row["members"] == 2
    assert row["member_names"] == ["D. Ortiz", "R. Patel"]


# ── gap 6 · the badges count the utility, not the search (image 25) ────────
def test_gap6_the_badges_count_the_utility_while_a_search_is_typed(brazos, dana):
    """RED on the tip: ``{'crews': 0} != {'crews': 1}`` — while a search was
    typed, the Crews badge read 0 though the utility has a crew."""
    with tenant_ctx(brazos):
        _world(brazos)
        page = workforce.crews_page(view="technicians", q="Ortiz")
    assert page["total"] == 1
    assert page["counts"] == {**page["counts"], "technicians": 2, "crews": 1, "contractors": 0}


# ── gap 2 · a technician's job row carries its completion time (image 32) ──
def test_gap2_a_finished_job_on_a_technicians_list_says_when_it_closed(brazos, dana):
    """RED on the tip: ``KeyError: 'completed_at'``."""
    with tenant_ctx(brazos):
        w = _world(brazos)
        premises = make_premises(dana, address_line="32 Closed Ct")
        done = timezone.now().replace(microsecond=0)
        work_tables.WorkOrder.objects.create(
            tenant=brazos, type="Meter set", order_no="WO-3201", premises_id=premises["id"],
            state=work_tables.WO_COMPLETED, completed_at=done, assignee_technician=w["ortiz"],
        )
        rows = technician_figures.jobs_page(workforce.technician_slug(w["ortiz"]))["rows"]
    assert rows[0]["completed_at"] == done.isoformat()


# ── gap 4 · the add-member picker pages and names each login's crew ────────
def test_gap4_the_picker_pages_in_sql_and_says_which_crew_each_person_is_on(brazos, dana):
    """RED on the tip: ``AttributeError: module 'apps.work.workforce' has no
    attribute 'staff_page'`` — the picker was one unpaged list with no crew."""
    with tenant_ctx(brazos):
        _world(brazos)
        page = workforce.staff_page(q="b.test")
    by_name = {row["full_name"]: row for row in page["rows"]}
    assert by_name["D. Ortiz"]["crew"]["name"] == "Field crew A"
    assert by_name["Sam Reyes"]["crew"] is None
    assert by_name["Sam Reyes"]["has_profile"] is False
    assert page["total"] == 3


# ── gap 5 · *Add a crew* is ONE write: crew, skills and members ────────────
def test_gap5_add_a_crew_writes_the_crew_its_skills_and_its_members_at_once(brazos, dana):
    """RED on the tip: the crew saved with no skills and nobody on it —
    ``assert 0 == 2``."""
    with tenant_ctx(brazos):
        w = _world(brazos)
        water = work_models.WorkSkill.objects.create(tenant=brazos, code="W1", name="Water I")
        answer = workforce.create_crew(
            dana,
            {
                "name": "Field crew C",
                "kind": "crew",
                "skills": [{"skill_id": str(water.id), "proficiency": "certified"}],
                "members": [{"technician_id": str(w["patel"].id)}, {"user_id": str(w["sam"].id)}],
            },
        )
        crew = work_models.Crew.objects.get(name="Field crew C")
        assert answer["members"] == 2
        assert sorted(answer["member_names"]) == ["R. Patel", "Sam Reyes"]
        assert [s["name"] for s in answer["skills"]] == ["Water I"]
        assert {"name": "R. Patel", "from": "Field crew A"} in answer["moved"]
        assert work_models.Technician.objects.get(pk=w["patel"].pk).crew_id == crew.id


def test_gap5_a_bad_member_rolls_the_whole_crew_back(brazos, dana):
    with tenant_ctx(brazos):
        _world(brazos)
        with pytest.raises(errors.ValidationError):
            workforce.create_crew(
                dana,
                {"name": "Field crew D", "kind": "crew",
                 "members": [{"technician_id": "00000000-0000-0000-0000-000000000000"}]},
            )
        assert not work_models.Crew.objects.filter(name="Field crew D").exists()


# ── gap 3 · a certificate's proof (image 33) ───────────────────────────────
def test_gap3_a_certificate_holds_its_proof_and_a_renewal_keeps_it(brazos, dana):
    """RED on the tip: ``ModuleNotFoundError: No module named
    'apps.work.certificate_proof'`` — `evidence_document_id` existed and
    nothing wrote it, so the PROOF column could only draw a dash."""
    from apps.work import certificate_proof
    from apps.work.seams import tenancy_seam

    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        w = _world(brazos)
        tenancy_models.CertificationType.objects.create(
            tenant=brazos, code="FIRSTAID", name="First aid / CPR"
        )
        kind = tenancy_seam.certification_types()[0]
        workforce.set_certifications(
            dana, w["ortiz"].id,
            {"certifications": [{"certification_type_id": kind["id"], "expires_on": "2028-03-16"}]},
        )
        person = workforce.technician_by_slug(workforce.technician_slug(w["ortiz"]))
        upload = SimpleUploadedFile("first-aid.pdf", b"%PDF-1.4 proof", content_type="application/pdf")
        stored = certificate_proof.store(dana, person, kind["id"], upload)
        assert stored["name"] == "first-aid.pdf"
        body, content_type, _name = certificate_proof.content(person, kind["id"])
        assert body == b"%PDF-1.4 proof" and content_type == "application/pdf"
        # Renew the date: the proof stays with the certificate.
        detail = workforce.set_certifications(
            dana, w["ortiz"].id,
            {"certifications": [{"certification_type_id": kind["id"], "expires_on": "2030-03-16"}]},
        )
        row = detail["certifications"][0]
        assert row["expires_on"] == "2030-03-16"
        assert row["proof"]["name"] == "first-aid.pdf"


def test_gap3_another_tenants_technician_reads_as_absent(brazos, lonestar, dana):
    from apps.work import certificate_proof

    with tenant_ctx(brazos):
        w = _world(brazos)
        person = workforce.technician_by_slug(workforce.technician_slug(w["ortiz"]))
    with tenant_ctx(lonestar), pytest.raises(errors.NotFoundError):
        certificate_proof.content(person, "00000000-0000-0000-0000-000000000000")
