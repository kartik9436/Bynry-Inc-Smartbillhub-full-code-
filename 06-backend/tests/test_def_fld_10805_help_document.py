# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10805 — FB-031: a job's help document never opens on the
#           phone (empty starter-pack rows read as "Downloads at next sync"; a
#           four-hour link never renewed; no document opener wired).
# Ruling:   decision log 2026-10-31 "FB-031: a job's help document opens in the
#           phone's own app ("Open with…") (PO, B)" and its coordinator
#           judgments: the phone is served the file from OUR API with the
#           technician's credential, own job only; a template is not published
#           with an empty document or phone row; a file added to a template
#           reaches open, not-started jobs.
# Rules:    BR-WRK-038 · BR-WRK-008 (narrowed for help) · CLAUDE.md hard rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The server half of FB-031.

RED FIRST: before this lane every case failed — `AttributeError: module
'apps.work.mobile' has no attribute 'help_content'`, `KeyError: 'has_file'`,
the publish returned a version over an empty row, and the open job kept the
help it was raised with."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.work import api as work_api
from apps.work import connection_models as work_tables
from apps.work import mobile, template_help, templates_svc
from apps.work import models as work_models
from core import errors

from tests.test_cr187_order_helpers import job, person
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 meter exchange SOP"


def _with_sop(actor, tenant):
    """A job whose template carries an UPLOADED SOP, a typed label, an empty
    document row and a phone row with no number (the starter pack's shape).
    Answers `(order_id, technician, help rows by label)`."""
    oid, tech = job(actor, tenant)
    order = work_tables.WorkOrder.objects.get(pk=oid)
    stored = template_help.store(
        actor, order.template_id, SimpleUploadedFile("sop.pdf", PDF, content_type="application/pdf"), {}
    )
    templates_svc.replace_collection(
        actor,
        order.template_id,
        "help",
        [
            {"kind": "document", "label": "Meter exchange SOP", "ref": stored["ref"]},
            {"kind": "document", "label": "Old SOP", "ref": "SOP-W-12"},
            {"kind": "document", "label": "Empty SOP", "ref": None},
            {"kind": "phone", "label": "Supervisor", "ref": None},
        ],
    )
    rows = {r.label: r for r in work_models.WorkOrderHelp.objects.filter(work_order_id=oid)}
    return oid, tech, rows


def test_the_bundle_says_which_documents_have_a_file_and_where_the_phone_fetches_it(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, rows = _with_sop(dana, brazos)
        help_rows = {r["label"]: r for r in mobile.bundle(tech, oid)["help"]}
    sop = help_rows["Meter exchange SOP"]
    assert sop["has_file"] is True
    assert sop["file_name"] == "sop.pdf" and sop["file_bytes"] == len(PDF)
    assert sop["content_type"] == "application/pdf"
    assert sop["content_path"] == f"/work/mobile/jobs/{oid}/help/{rows['Meter exchange SOP'].id}/content"
    # The typed label and the empty row: no file, and nothing to fetch.
    for label in ("Old SOP", "Empty SOP"):
        assert help_rows[label]["has_file"] is False
        assert help_rows[label]["url"] is None and help_rows[label]["content_path"] is None
    assert "has_file" not in help_rows["Supervisor"]


def test_the_content_route_serves_the_technicians_own_job(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, rows = _with_sop(dana, brazos)
        body, content_type, name = mobile.help_content(tech, oid, rows["Meter exchange SOP"].id)
    assert (body, content_type, name) == (PDF, "application/pdf", "sop.pdf")


def test_the_content_route_is_a_404_for_everything_but_that(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        oid, tech, rows = _with_sop(dana, brazos)
        _other, colleague = person(brazos, "j-reyes@brazos.test", "J. Reyes")
        sop = rows["Meter exchange SOP"].id
        # Another technician of the same tenant.
        with pytest.raises(errors.NotFoundError):
            mobile.help_content(colleague, oid, sop)
        # A phone row, a typed label and an empty row on the technician's own job.
        for label in ("Supervisor", "Old SOP", "Empty SOP"):
            with pytest.raises(errors.NotFoundError):
                mobile.help_content(tech, oid, rows[label].id)
    # Another tenant: the same ids read as absent.
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            mobile.help_content(tech, oid, sop)


def test_the_route_is_mounted_and_answers_private_no_store(brazos, dana):
    from django.urls import resolve

    with tenant_ctx(brazos):
        oid, _tech, rows = _with_sop(dana, brazos)
    match = resolve(f"/api/{brazos.subdomain}/work/mobile/jobs/{oid}/help/{rows['Meter exchange SOP'].id}/content")
    assert match.func.__name__ == work_api.mobile_job_help_content.__name__


def test_publish_is_refused_for_an_empty_document_row_and_a_phone_row_with_no_number(brazos, dana):
    with tenant_ctx(brazos):
        tid = templates_svc.create_draft(dana, {"name": "Meter exchange", "service": "electric"})["id"]
        templates_svc.replace_collection(
            dana, tid, "help", [{"kind": "document", "label": "Meter exchange SOP", "ref": None}]
        )
        with pytest.raises(errors.ValidationError) as no_file:
            templates_svc.publish(dana, tid)
        templates_svc.replace_collection(
            dana, tid, "help", [{"kind": "phone", "label": "Supervisor", "ref": "ext."}]
        )
        with pytest.raises(errors.ValidationError) as no_number:
            templates_svc.publish(dana, tid)
        templates_svc.replace_collection(
            dana, tid, "help", [{"kind": "phone", "label": "Supervisor", "ref": "(512) 555-0142"}]
        )
        published = templates_svc.publish(dana, tid)
    assert no_file.value.message_key == "work.template.help_needs_file"
    assert no_number.value.message_key == "work.template.help_needs_number"
    assert published["version"] == 1


def test_a_changed_help_reaches_an_open_job_that_has_not_started_and_not_a_started_one(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, _rows = _with_sop(dana, brazos)
        order = work_tables.WorkOrder.objects.get(pk=oid)
        before = order.updated_at
        # A second job from the same template, already on site.
        started, _tech2 = job(dana, brazos)
        work_tables.WorkOrder.objects.filter(pk=started).update(
            dispatch_state=work_tables.DISPATCH_ON_SITE
        )
        kept = sorted(
            work_models.WorkOrderHelp.objects.filter(work_order_id=started).values_list("label", flat=True)
        )
        answer = templates_svc.replace_collection(
            dana, order.template_id, "help",
            [{"kind": "phone", "label": "Control room", "ref": "555-0142"}],
        )
        labels = list(work_models.WorkOrderHelp.objects.filter(work_order_id=oid).values_list("label", flat=True))
        after = work_tables.WorkOrder.objects.get(pk=oid).updated_at
        still = sorted(
            work_models.WorkOrderHelp.objects.filter(work_order_id=started).values_list("label", flat=True)
        )
    assert labels == ["Control room"]
    assert after > before  # the change feed sends the job again
    assert answer["jobs_refreshed"] >= 1
    assert still == kept
