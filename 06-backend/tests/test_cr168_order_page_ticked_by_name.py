# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — the completed job's record
#           (image 06) names who ticked each line: *✓ D. Ortiz · 9:41*.
# Rules:    ruling 15 (the record shows who did each line and when) · B14 rule
#           31 (`ticked_by` is an id and is never drawn — the NAME is served
#           beside it) · hard rule 1
# ───────────────────────────────────────────────────────
"""`GET /work-orders/{id}/checklist` serves `ticked_by_name` beside `ticked_by`.

Appended to CR-168 §7.3 by lane ORDER-PAGE: the contract named the record
(*"who did each line and when"*) and no field carried the WHO as words.
"""

from __future__ import annotations

import pytest

from apps.work import checklist
from apps.work import models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def test_a_ticked_line_carries_the_name_of_who_ticked_it(brazos, dana):
    with tenant_ctx(brazos):
        oid = _raise(dana, brazos, _published_template(dana, brazos))["id"]
        row = work_models.WorkOrderSafety.objects.get(work_order_id=oid, seq=1)
        checklist.tick_safety(dana, oid, row.id)
        answer = checklist.checklist(oid)
        who = work_models.WorkOrderSafety.objects.select_related("ticked_by").get(pk=row.pk).ticked_by
    first, second = answer["safety"][0], answer["safety"][1]
    expected = (who.full_name or who.email).strip()
    assert first["ticked_by_name"] == expected
    assert first["ticked_by_name"] != first["ticked_by"]
    # An unticked line names nobody — never an empty string standing for a person.
    assert second["ticked_by_name"] is None
    for task in answer["tasks"]:
        assert "ticked_by_name" in task


# ══════════════════════════════════════════════════════════════════════════
# DEF-WRK-9594 — the photograph's bytes, same-origin, for the office viewer
# ══════════════════════════════════════════════════════════════════════════
from apps.work import evidence  # noqa: E402
from core import errors  # noqa: E402
from tests.test_us_wrk_047_049_evidence import TINY_PNG, _upload  # noqa: E402


def test_def_wrk_9593_the_photograph_is_served_as_bytes_not_as_a_foreign_link(brazos, dana):
    with tenant_ctx(brazos):
        oid = _raise(dana, brazos, _published_template(dana, brazos))["id"]
        att = _upload(dana, oid, "cr168-bytes")
        payload, content_type = evidence.attachment_bytes(oid, att["id"])
    assert payload == TINY_PNG
    assert content_type.startswith("image/")


def test_def_wrk_9593_another_utility_reads_the_same_404(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        oid = _raise(dana, brazos, _published_template(dana, brazos))["id"]
        att = _upload(dana, oid, "cr168-bytes-x")
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            evidence.attachment_bytes(oid, att["id"])


def test_def_wrk_9593_the_route_is_mounted():
    from django.urls import resolve

    match = resolve(
        "/api/brazosbend/work-orders/01a105bb-b558-73f6-a4d0-3fed0d060e76/attachments/"
        "01a105bb-b558-73f6-a4d0-3fed0d060e77/content"
    )
    assert match.route.endswith("attachments/<uuid:attachment_id>/content")
