# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — the Templates server: the list
#           paged in SQL (P3.5), a task's instruction text (PO answer 3), a help
#           document (P3.14) or link (ruling 6), a template's history (P3.28), a
#           job's estimate from its template (P3.47); DEF-WRK-9611
# Rules:    NFR-3 · NFR-5 · BR-WRK-008 (copy, never link) · hard rules 1 and 7
# ───────────────────────────────────────────────────────
"""The Templates server, round 4 (SQLite; the migrations and the recorded
answers are proved on PostgreSQL 16 separately)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import models as work_models
from apps.work import selectors
from apps.work import services as work_services
from apps.work import templates_svc
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _reference():
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")


def _template(tenant, name="Meter exchange", service="water", version=1, **over):
    svc = tenancy_models.Service.objects.filter(code=service).first()
    return work_tables.WorkOrderTemplate.objects.create(
        tenant_id=tenant.id, name=name, service=svc, scope="per_unit", version=version, **over
    )


# ── DEF-WRK-9612 ────────────────────────────────────────────────────────────


def test_def_wrk_9612_a_template_naming_no_job_type_is_offered_for_every_type(brazos, dana):
    """`f.job_type` kept only templates whose type matched, so a template that
    names NO type — all 6 of 6 on the demo — was dropped and the raise offered
    nothing. A template naming no type applies to every type, as one naming no
    asset type applies to every asset (`BR-WRK-056`'s shape)."""
    with tenant_ctx(brazos):
        _reference()
        kind = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id, active=True).first()
        other = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id, active=True).exclude(
            pk=kind.id
        ).first()
        _template(brazos, name="Untyped one")
        typed = _template(brazos, name="Typed one")
        work_tables.WorkOrderTemplate.objects.filter(pk=typed.id).update(type_id=kind.id)
        elsewhere = _template(brazos, name="Other type")
        work_tables.WorkOrderTemplate.objects.filter(pk=elsewhere.id).update(type_id=other.id)
        names = {r["name"] for r in selectors.templates_page(job_type=str(kind.id), raisable=True)["rows"]}
    assert names == {"Untyped one", "Typed one"}


# ── P3.5 · the list paged and counted in SQL ────────────────────────────────


def test_p3_5_the_footer_is_one_aggregate_and_the_page_one_query(brazos, dana):
    """Five templates at 50 a page: the footer counts the whole list
    (3 published, 1 draft, 1 inactive) and CONTENTS arrives with the page —
    no per-row count queries (five per row before)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with tenant_ctx(brazos):
        first = _template(brazos, name="A one")
        for name in ("B two", "C three"):
            _template(brazos, name=name)
        _template(brazos, name="D draft", version=0)
        _template(brazos, name="E off", active=False)
        work_models.WorkOrderTemplateTask.objects.create(
            tenant_id=brazos.id, template_id=first.id, seq=1, title="Isolate", est_minutes=8
        )
        with CaptureQueriesContext(connection) as seen:
            page = selectors.templates_page(per=50)
    assert page["counts"] == {"published": 3, "draft": 1, "inactive": 1}
    assert page["total"] == 5
    row = next(r for r in page["rows"] if r["name"] == "A one")
    assert row["contents"]["tasks"] == 1 and row["contents"]["parts"] == 0
    assert len(seen.captured_queries) <= 4, [q["sql"][:80] for q in seen.captured_queries]


# ── PO answer (3) · a task's instruction text ───────────────────────────────


def test_answer_3_an_instruction_is_written_read_copied_and_on_the_checklist(brazos, dana):
    """*Meter exchange — isolate at the main before touching* travels from the
    builder to the template's page to the job's own copy to the checklist."""
    from apps.work import checklist

    with tenant_ctx(brazos):
        _reference()
        tpl = _template(brazos, name="Meter exchange")
        templates_svc.replace_collection(
            dana, tpl.id, "tasks",
            [
                {"title": "Isolate supply", "est_minutes": 8,
                 "instruction": "Isolate at the main before touching."},
                {"title": "Fit new meter", "est_minutes": 30, "instruction": "  "},
            ],
        )
        read = selectors.template(tpl.id)["bundle"]["tasks"]
        premises = make_premises(dana, address_line="12 Kestrel Park", services_available=["water"])
        raised = w6.create_work_order(
            dana, None,
            {"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
             "template_id": str(tpl.id)},
        )
        work_models.WorkOrderTemplateTask.objects.filter(template_id=tpl.id, seq=1).update(
            instruction="Re-worded later."
        )
        tasks = checklist.checklist(raised["id"])["tasks"]
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
    assert [t["instruction"] for t in read] == ["Isolate at the main before touching.", None]
    # Copied at the raise: the later re-wording does not reach this job.
    assert [t["instruction"] for t in tasks] == ["Isolate at the main before touching.", None]
    # P3.47 — the job's estimate is its template's task minutes: 8 + 30.
    assert order.est_duration == timedelta(minutes=38)


# ── ruling 6 · help as a link or an uploaded document (P3.14, P3.25) ────────


def test_ruling_6_a_help_link_must_be_https(brazos, dana):
    with tenant_ctx(brazos):
        tpl = _template(brazos)
        templates_svc.replace_collection(
            dana, tpl.id, "help",
            [{"kind": "link", "label": "How to fit a meter", "link": "https://www.youtube.com/watch?v=abc"}],
        )
        row = selectors.template(tpl.id)["bundle"]["help"][0]
        with pytest.raises(errors.ValidationError) as caught:
            templates_svc.replace_collection(
                dana, tpl.id, "help", [{"kind": "link", "label": "Bad", "link": "javascript:alert(1)"}]
            )
    assert row["link"] == "https://www.youtube.com/watch?v=abc" and row["url"] is None
    assert caught.value.message_key == "work.template.help_link_https"


def test_p3_14_a_help_document_is_stored_named_by_its_row_and_opened(brazos, dana, lonestar):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.work import template_help

    pdf = b"%PDF-1.4 meter exchange SOP"
    with tenant_ctx(brazos):
        tpl = _template(brazos)
        other = _template(brazos, name="Other template")
        ticket = template_help.upload_ticket(tpl.id, {"filename": "sop.pdf", "content_type": "application/pdf"})
        stored = template_help.store(
            dana, tpl.id, SimpleUploadedFile("sop.pdf", pdf, content_type="application/pdf"), {}
        )
        # Not yet named by a help row: the template answers no such file.
        with pytest.raises(errors.NotFoundError):
            template_help.content(tpl.id, stored["id"])
        templates_svc.replace_collection(
            dana, tpl.id, "help", [{"kind": "document", "label": "Meter exchange SOP", "ref": stored["ref"]}]
        )
        row = selectors.template(tpl.id)["bundle"]["help"][0]
        body, content_type, name = template_help.content(tpl.id, stored["id"])
        # Another template does not open this template's file.
        with pytest.raises(errors.NotFoundError):
            template_help.content(other.id, stored["id"])
        with pytest.raises(errors.ValidationError) as refused:
            template_help.store(
                dana, tpl.id, SimpleUploadedFile("clip.mp4", b"x", content_type="video/mp4"), {}
            )
    assert ticket["max_bytes"] == 10 * 1024 * 1024
    assert row["url"] == f"/work/templates/{tpl.id}/help/documents/{stored['id']}/content"
    assert (body, content_type, name) == (pdf, "application/pdf", "sop.pdf")
    assert refused.value.message_key == "work.template.help_file_type"
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            template_help.content(tpl.id, stored["id"])


# ── P3.28 · a template's change history ─────────────────────────────────────


def test_p3_28_the_audit_tab_lists_who_changed_what_in_words(brazos, dana):
    from apps.audit import services as audit_services
    from apps.work import template_history
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    try:
        with tenant_ctx(brazos):
            tpl = _template(brazos)
            templates_svc.replace_collection(
                dana, tpl.id, "tasks", [{"title": "Isolate supply", "est_minutes": 8}]
            )
            templates_svc.replace_collection(
                dana, tpl.id, "help", [{"kind": "note", "label": "Call the office first"}]
            )
            out = template_history.template_audit(tpl.id)
    finally:
        core_audit.set_audit_sink(previous)
    assert out["total"] == 2
    assert [(r["act"], r["collection"]) for r in out["rows"]] == [("replaced", "help"), ("replaced", "tasks")]
    assert out["rows"][1]["summary"] == {"collection": "tasks", "rows": 1}
    assert all("id" not in r["summary"] for r in out["rows"])
