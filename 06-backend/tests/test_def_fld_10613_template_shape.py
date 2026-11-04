# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10613 (beta MQ-034) — Raise > Pick a template showed
#           "{id=01a07f62-…, code=water, name=Water} · 7 steps · …" on every card
# Rules:    B14 rule 31 (no database id on screen) · hard rule 1 (tenant scope)
# Tests:    this file · field-app/tests/sync/def_fld_10613_template_shape.test.tsx
# ───────────────────────────────────────────────────────
"""The SHAPE of one catalogue row (`GET /work/mobile/templates`) is the shape
the handset's template tests are built from.

`field-app/tests/sync/support/serverTemplate.json` is the handset's copy of one
catalogue row. MQ-034 hid because the phone's tests seeded templates with
`service: 'Water'` — plain text — while this server sends `service` (and
`job_type`) as `{id, code, name}` objects; the phone stored the object into a
text column and printed it. This case builds a real published template, reads
the real catalogue, and compares KEY SETS and VALUE TYPES with that file,
recursively, so either side changing without the other turns one test red."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.tenancy import models as tenancy_models
from apps.work import connection_models as work_tables
from apps.work import field_raise
from apps.work import models as work_models

from tests.test_cr187_order_helpers import job, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "field-app"
    / "tests"
    / "sync"
    / "support"
    / "serverTemplate.json"
)


def _shape(value):
    """Keys and JSON types, recursively — never the values themselves."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in value.items()}
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def test_the_catalogue_row_is_the_shape_the_handset_fixture_holds(brazos, dana):
    with tenant_ctx(brazos):
        _oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Meter exchange")
        kind = work_models.WorkOrderType.objects.filter(tenant_id=brazos.id).first()
        if kind is None:
            kind = work_models.WorkOrderType.objects.create(
                tenant_id=brazos.id, code="exchange", name="Exchange"
            )
        water = tenancy_models.Service.objects.get(code="water")
        work_tables.WorkOrderTemplate.objects.filter(pk=tid).update(service=water, type=kind)
        page = field_raise.templates_catalogue(tech, q="Meter exchange")

    row = next(r for r in page["rows"] if r["name"] == "Meter exchange")
    # Through the JSON boundary the handset actually reads.
    row = json.loads(json.dumps(row, default=str))
    fixture = json.loads(FIXTURE.read_text())

    assert _shape(row) == _shape(fixture)
    # The two object-valued fields are objects, with a NAME the phone shows.
    assert row["service"] == {"id": str(water.id), "code": "water", "name": "Water"}
    assert row["job_type"]["name"] == kind.name
    assert (row["steps"], row["safety_checks"], row["readings"]) == (7, 3, 3)
