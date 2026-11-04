# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.3 *"Print a work order"* and
#           ruling 3's *"a day's pack prints"*.
# Rules:    B14 rule 31 (no database id on paper) · CLAUDE.md hard rule 8 (the
#           premises' address, walked) · rule 3 (a reading carries its unit) ·
#           B14 rule 43 (the product's one PDF writer, reused)
# ───────────────────────────────────────────────────────
"""A work order and a technician's day, printed through the real routes and
read back as PDF bytes. Runs on SQLite and on PostgreSQL 16."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from apps.work import connection_models as work_tables
from apps.work import print_docs, workforce

from tests.test_cr168_srv5_messages import ADDRESS, _assign, _customer_job, _reference, _technician, _window
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template

pytestmark = pytest.mark.django_db

UUID = re.compile(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _texts(pdf: bytes) -> list[str]:
    """Every string the page SHOWS (`(…) Tj`), unescaped — the words on paper."""
    out = []
    for raw in re.findall(rb"\(((?:\\.|[^\\)])*)\) Tj", pdf):
        out.append(re.sub(rb"\\(.)", rb"\1", raw).decode("cp1252"))
    return out


def test_the_two_routes_exist():
    order = resolve("/api/brazosbend/work-orders/01a10711-e839-7fba-a5e0-3762f041dd2e/print")
    pack = resolve("/api/brazosbend/work/print/day-pack")
    from apps.work import api as work_api

    assert order.func is work_api.work_order_print
    assert pack.func is work_api.work_day_pack_print


def test_p6_3_a_work_order_prints_with_its_address_customer_and_copies_and_no_id(brazos, dana, marcus):
    """RED on the tip: ``ModuleNotFoundError: No module named
    'apps.work.print_docs'`` — the blueprint's *work_documents.py has NO PDF
    path at all*."""
    with tenant_ctx(brazos):
        _reference()
        tid = _published_template(dana, brazos)
        job = _customer_job(marcus, brazos, service="electric", template_id=tid)
        _assign(dana, job, _technician(brazos), _window())
        from apps.work import models as work_models

        assert work_models.WorkOrderTask.objects.filter(work_order_id=job.id).count() == 7, (
            job.template_id)
        pdf, name = print_docs.order_pdf(job.id)
        ids = {str(job.id), str(job.unit_id), str(job.premises_id or ""), str(brazos.id)}

    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert name == f"{job.order_no}.pdf"
    words = " | ".join(_texts(pdf))
    assert f"Work order {job.order_no}" in words
    assert ADDRESS in words, "the premises' address, walked (hard rule 8)"
    assert "Elena Rivera" in words
    assert "R. Patel" in words
    assert "[ ] 1. " in words, "tasks print as boxes to tick"
    assert "kWh" in words, "a reading prints with its unit (rule 3)"
    # B14 rule 31 — no database id anywhere in the bytes, shown or not.
    assert not UUID.search(pdf), UUID.search(pdf)
    for value in ids - {""}:
        assert value.encode() not in pdf


def test_p6_3_printing_twice_is_the_same_bytes(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _reference()
        order = _customer_job(marcus, brazos)
        first, _ = print_docs.order_pdf(order.id)
        second, _ = print_docs.order_pdf(order.id)
    assert first == second


def test_p6_3_a_days_pack_lists_the_day_in_order_then_one_sheet_per_job(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _reference()
        patel = _technician(brazos)
        chen = _technician(brazos, email="m.chen@b.test", name="M. Chen")
        late = _customer_job(marcus, brazos, address="9 Late Ln")
        early = _customer_job(marcus, brazos, address="1 Early Rd")
        other = _customer_job(marcus, brazos, address="5 Other St")
        tomorrow = timezone.localtime(timezone.now() + timedelta(days=1)).date()
        _assign(dana, late, patel, _window(start_h=13, end_h=17))
        _assign(dana, early, patel, _window(start_h=8, end_h=10))
        _assign(dana, other, chen, _window(start_h=8, end_h=10))
        slug = workforce.technician_slug(patel)
        day = timezone.localtime(
            work_tables.WorkOrder.objects.get(pk=early.pk).window_start
        ).date()
        pdf, name = print_docs.day_pack_pdf(on=day.isoformat(), technician=slug)
        page_count = int(re.search(rb"/Count (\d+)", pdf).group(1))

    words = _texts(pdf)
    joined = " | ".join(words)
    assert name == f"day-pack-{slug}-{day.isoformat()}.pdf"
    assert "Day pack · R. Patel" in joined
    assert "1 Early Rd" in joined and "9 Late Ln" in joined
    assert "5 Other St" not in joined, "M. Chen's job is not in R. Patel's pack"
    # The cover lists the day IN ORDER: the 08:00 job before the 13:00 one.
    assert joined.index(early.order_no) < joined.index(late.order_no)
    assert page_count >= 3, "a cover, then one sheet per job"
    assert not UUID.search(pdf)
    assert tomorrow  # the window helper books tomorrow; `day` is read back, not assumed


def test_p6_3_an_empty_day_prints_the_cover_saying_so(brazos, dana):
    with tenant_ctx(brazos):
        patel = _technician(brazos)
        pdf, _ = print_docs.day_pack_pdf(on="2030-01-02", technician=workforce.technician_slug(patel))
    assert "No open jobs on this day." in " | ".join(_texts(pdf))


def test_p6_3_another_utilitys_technician_is_not_found(brazos, lonestar, dana):
    from core import errors

    with tenant_ctx(lonestar):
        other = _technician(lonestar, email="x@l.test", name="X. Other")
        slug = workforce.technician_slug(other)
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            print_docs.day_pack_pdf(on="2030-01-02", technician=slug)


def test_p6_3_the_response_is_inline_private_and_typed(brazos, dana, marcus):
    """The route hands the bytes to `core.document_response` — the four
    safety headers every served document carries. (The HTTP round trip through
    the signed-in session is proved in the browser walk,
    `10-scripts/cr168_srv5_walk.mjs`.)"""
    from core.document_response import document_http_response

    with tenant_ctx(brazos):
        _reference()
        order = _customer_job(marcus, brazos)
        payload, name = print_docs.order_pdf(order.id)
    response = document_http_response(payload=payload, content_type="application/pdf",
                                      name=name, inline=True)
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith(f'inline; filename="{order.order_no}.pdf"')
    assert response["Cache-Control"] == "private, no-store"
