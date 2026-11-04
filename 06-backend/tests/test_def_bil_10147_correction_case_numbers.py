# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10147 — a correction case was never numbered; every screen
#           read "No case number yet".
# Ruled:    G3, PO 2026-10-14 (decision log "G1–G4 APPROVED" item 3): a case
#           takes its number at Send from a new tenant series "Correction
#           case", default `CC-{YYYY}-{000}` (e.g. CC-2026-001), editable in
#           Settings → Numbering; existing cases are numbered once, oldest
#           first; a deleted series leaves the case unnumbered and is never
#           blocking (the credit-memo precedent).
# Rules:    BR-TEN-035 · BR-TEN-043 · BR-BIL-014 · CLAUDE.md hard rules 1, 7
# ───────────────────────────────────────────────────────
"""A correction case is numbered at Send — CC-2026-001 on an untouched tenant.

Every figure is the engine's (the Silver Creek water ladder of
`test_cr180_fix_a_bill_revamp`): each July bill is $373.00 and a missed $15.00
RECONNECT charge raises it to $388.00. The business date is 15 August 2026.

PostgreSQL as well (law 14), and the race is `..._pg.py`:

    cd 06-backend && CELERY_BROKER_URL=memory:// JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest -q tests/test_def_bil_10147_correction_case_numbers.py \\
      --ds=config.settings.pgtest --create-db

RED FIRST, on the tree before the fix, verbatim:
  * Send:            `AssertionError: assert None == 'CC-2026-001'`
  * catalogue:       `AttributeError: module 'core.numbering' has no attribute
                     'CORRECTION_CASE'`
  * backfill:        `ModuleNotFoundError: No module named
                     'apps.billing.migrations.0043_def_bil_10147_number_existing_correction_cases'`
"""

from __future__ import annotations

import importlib
from datetime import UTC, date, datetime

import pytest
from django.apps import apps as django_apps
from django.db import connection, transaction

from apps.billing import corrections
from apps.billing.correction_models import CorrectionCase
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import numbering as core_numbering

from tests.test_cr180_fix_a_bill_revamp import (  # noqa: F401 — the autouse template pin
    _one_customer,
    _preview,
    _send,
    _sent_case,
    _the_rebill_template,
    _two_month_world,
    _wrong_read,
)
from tests.test_def_bil_10091_bulk_fix_jobs import ITEMS, _sent, _three_bills
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

BACKFILL = importlib.import_module(
    "apps.billing.migrations.0043_def_bil_10147_number_existing_correction_cases"
)
SEED = importlib.import_module(
    "apps.tenancy.migrations.0063_def_bil_10147_correction_case_series"
)


def _send_one(tenant, actor, world):
    scope = _one_customer(world)
    preview = _preview(tenant, actor, scope, ITEMS)
    assert preview.status_code == 200, preview.data
    sent = _send(tenant, actor, scope, ITEMS, preview.data["preview_hash"])
    assert sent.status_code == 201, sent.data
    return sent.data


def _sent_audit(audit_rows, case_id):
    """The `correction.case_sent` row (hard rule 7), read from the suite's
    BE-03 capture sink — the autouse `audit_rows` fixture replaces the table
    writer, as `test_cr180_fix_a_bill_revamp` records."""
    rows = [
        row
        for row in audit_rows
        if row["action"] == "correction.case_sent" and str(row["entity_id"]) == str(case_id)
    ]
    assert len(rows) == 1, rows
    return rows[0]


# ═══════════════════════════════════════════════════════════════════════════
# The catalogue and provisioning
# ═══════════════════════════════════════════════════════════════════════════
def test_the_series_is_ruled_cc_yyyy_000_and_the_first_case_of_2026_is_cc_2026_001():
    """⚠ THE RATIFIED FIGURE, PINNED SO DRIFT GOES RED (G3)."""
    group, options = core_numbering.SERIES_CATALOG[core_numbering.CORRECTION_CASE]
    assert group == core_numbering.GROUP_BILLING
    assert options[0] == "CC-{YYYY}-{000}"
    assert options[-1] == "{000000}", "CR-005's mandatory bare counter is last"
    for option in options:
        core_numbering.validate_format(option)
    assert tenancy_services.SERIES_DEFAULTS[core_numbering.CORRECTION_CASE] == "CC-{YYYY}-{000}"
    assert core_numbering.render(options[0], 1, date(2026, 10, 14)) == "CC-2026-001"
    # APPENDED — the dict order is the order Settings → Numbering prints.
    assert list(core_numbering.SERIES_CATALOG)[-1] == core_numbering.CORRECTION_CASE


def test_a_new_tenant_is_seeded_the_series_restarting_yearly(brazos):
    with tenant_ctx(brazos):
        row = tenancy_models.NumberSeries.objects.get(
            tenant=brazos, series=core_numbering.CORRECTION_CASE
        )
    assert (row.format, row.next_number, row.restart_period, row.period_counted) == (
        "CC-{YYYY}-{000}",
        1,
        core_numbering.RESTART_YEARLY,
        "",
    )


def test_settings_numbering_lists_correction_case_last_in_billing_and_payments(brazos):
    with tenant_ctx(brazos):
        rows = tenancy_selectors.number_series_overview()
    billing = [row["series"] for row in rows if row["group"] == core_numbering.GROUP_BILLING]
    assert billing[-1] == core_numbering.CORRECTION_CASE
    assert billing[:-1] == [
        series
        for series, (group, _options) in core_numbering.SERIES_CATALOG.items()
        if group == core_numbering.GROUP_BILLING and series != core_numbering.CORRECTION_CASE
    ], "no shipped billing row moved"
    row = next(row for row in rows if row["series"] == core_numbering.CORRECTION_CASE)
    assert row["format"] == "CC-{YYYY}-{000}" and row["duplicate_prefix"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Send numbers the case
# ═══════════════════════════════════════════════════════════════════════════
def test_a_one_customer_send_numbers_the_case_and_the_next_send_takes_the_next(
    brazos, dana, audit_rows
):
    world = _three_bills(brazos, dana)
    first = _send_one(brazos, dana, world.first)
    assert first["case_no"] == "CC-2026-001"
    second = _send_one(brazos, dana, world.second)
    assert second["case_no"] == "CC-2026-002"
    with tenant_ctx(brazos):
        assert CorrectionCase.objects.get(pk=first["id"]).case_no == "CC-2026-001"
        after = _sent_audit(audit_rows, first["id"])["after"]
        assert after["case_no"] == "CC-2026-001"
        assert "numbering_gap" not in after
        series = tenancy_models.NumberSeries.objects.get(
            tenant=brazos, series=core_numbering.CORRECTION_CASE
        )
        assert (series.next_number, series.period_counted) == (3, "2026")


def test_several_months_of_one_customer_are_one_case_with_one_number(brazos, dana):
    with tenant_ctx(brazos):
        world = _two_month_world(brazos, dana)
    scope = _one_customer(world, world.june, world.july)
    _preview_body, sent = _sent_case(brazos, dana, scope, [_wrong_read(world)])
    assert len(sent["bills_detail"]) == 2, "June and July of ONE account, ONE case"
    assert sent["case_no"] == "CC-2026-001"
    with tenant_ctx(brazos):
        assert list(CorrectionCase.objects.values_list("case_no", flat=True)) == ["CC-2026-001"]


def test_a_bulk_send_numbers_its_case_in_the_background_job(brazos, dana, audit_rows):
    world = _three_bills(brazos, dana)
    _answer, case = _sent(brazos, dana, world)
    assert case["case_no"] == "CC-2026-001"
    with tenant_ctx(brazos):
        stored = CorrectionCase.objects.get(pk=case["id"])
        assert stored.case_no == "CC-2026-001"
        assert _sent_audit(audit_rows, stored.pk)["after"]["case_no"] == "CC-2026-001"


def test_a_refused_send_rolls_its_number_back(brazos, dana):
    """BR-TEN-035 allows gaps; this proves there is none from a figures-moved
    refusal, because the number is taken inside the Send's transaction."""
    world = _three_bills(brazos, dana)
    scope = _one_customer(world.first)
    assert _preview(brazos, dana, scope, ITEMS).status_code == 200
    refused = _send(brazos, dana, scope, ITEMS, "0" * 64)
    assert refused.status_code == 422
    assert _send_one(brazos, dana, world.first)["case_no"] == "CC-2026-001"


# ═══════════════════════════════════════════════════════════════════════════
# Per tenant, per year
# ═══════════════════════════════════════════════════════════════════════════
def test_the_sequence_is_per_tenant_and_starts_again_each_year(brazos, lonestar):
    with tenant_ctx(brazos), transaction.atomic():
        assert corrections.allocate_case_no(date(2026, 3, 1)) == ("CC-2026-001", None)
        assert corrections.allocate_case_no(date(2026, 12, 31)) == ("CC-2026-002", None)
        assert corrections.allocate_case_no(date(2027, 1, 2)) == ("CC-2027-001", None)
    with tenant_ctx(lonestar), transaction.atomic():
        assert corrections.allocate_case_no(date(2026, 3, 1)) == ("CC-2026-001", None)


def test_a_send_dated_into_a_year_already_left_is_unnumbered_and_says_why(brazos):
    with tenant_ctx(brazos), transaction.atomic():
        assert corrections.allocate_case_no(date(2027, 1, 2)) == ("CC-2027-001", None)
        assert corrections.allocate_case_no(date(2026, 12, 30)) == (
            None,
            corrections.CASE_NUMBER_BACKDATED,
        )
        assert corrections.allocate_case_no(None) == (None, corrections.CASE_NUMBER_DATE_MISSING)


# ═══════════════════════════════════════════════════════════════════════════
# A deleted series never blocks
# ═══════════════════════════════════════════════════════════════════════════
def test_a_deleted_series_opens_the_case_unnumbered_and_records_why(brazos, dana, audit_rows):
    world = _three_bills(brazos, dana)
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            series=core_numbering.CORRECTION_CASE
        ).delete()
    sent = _send_one(brazos, dana, world.first)
    assert sent["case_no"] is None
    after = _sent_audit(audit_rows, sent["id"])["after"]
    assert after["case_no"] is None
    assert after["numbering_gap"] == "numbering_series_missing"


# ═══════════════════════════════════════════════════════════════════════════
# The backfill — existing cases numbered once, oldest first
# ═══════════════════════════════════════════════════════════════════════════
def _schema_editor():
    return type("SchemaEditor", (), {"connection": connection})()


def _old_case(tenant, *, at: datetime, case_no: str | None = None) -> CorrectionCase:
    case = CorrectionCase.objects.create(
        tenant=tenant, correction_class="A", case_no=case_no, scope_kind="single"
    )
    CorrectionCase.objects.filter(pk=case.pk).update(created_at=at)
    return case


def test_the_backfill_numbers_existing_cases_once_oldest_first_by_year(brazos, lonestar):
    with tenant_ctx(brazos):
        middle = _old_case(brazos, at=datetime(2026, 2, 3, 10, tzinfo=UTC))
        oldest = _old_case(brazos, at=datetime(2025, 11, 20, 10, tzinfo=UTC))
        newest = _old_case(brazos, at=datetime(2026, 9, 1, 10, tzinfo=UTC))
        kept = _old_case(brazos, at=datetime(2026, 1, 5, 10, tzinfo=UTC), case_no="LEGACY-1")
    with tenant_ctx(lonestar):
        theirs = _old_case(lonestar, at=datetime(2026, 5, 5, 10, tzinfo=UTC))

    with tenant_ctx(brazos):  # the migration sets each tenant itself on PostgreSQL
        BACKFILL.forwards(django_apps, _schema_editor())

    with tenant_ctx(brazos):
        numbers = {
            one.pk: one.case_no for one in CorrectionCase.objects.filter(tenant=brazos)
        }
        series = tenancy_models.NumberSeries.objects.get(
            tenant=brazos, series=core_numbering.CORRECTION_CASE
        )
    assert numbers[oldest.pk] == "CC-2025-001"
    assert numbers[middle.pk] == "CC-2026-001", "a new year starts again at one"
    assert numbers[newest.pk] == "CC-2026-002"
    assert numbers[kept.pk] == "LEGACY-1", "a numbered case is never renumbered"
    assert (series.next_number, series.period_counted) == (3, "2026"), "the counter moved with them"
    with tenant_ctx(lonestar):
        assert CorrectionCase.objects.get(pk=theirs.pk).case_no == "CC-2026-001"

    # ONCE: a second run changes nothing, and the next Send continues the series.
    with tenant_ctx(brazos):
        BACKFILL.forwards(django_apps, _schema_editor())
        assert CorrectionCase.objects.get(pk=newest.pk).case_no == "CC-2026-002"
        with transaction.atomic():
            assert corrections.allocate_case_no(date(2026, 10, 14)) == ("CC-2026-003", None)


def test_the_backfill_leaves_cases_unnumbered_where_the_series_was_deleted(brazos):
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            series=core_numbering.CORRECTION_CASE
        ).delete()
        case = _old_case(brazos, at=datetime(2026, 2, 3, 10, tzinfo=UTC))
        BACKFILL.forwards(django_apps, _schema_editor())
        assert CorrectionCase.objects.get(pk=case.pk).case_no is None


def test_the_seed_migration_gives_an_existing_tenant_the_series_once(brazos):
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            series=core_numbering.CORRECTION_CASE
        ).delete()
        SEED.forwards(django_apps, _schema_editor())
        SEED.forwards(django_apps, _schema_editor())
        rows = list(
            tenancy_models.NumberSeries.objects.filter(series=core_numbering.CORRECTION_CASE)
        )
    assert [(row.format, row.next_number, row.restart_period) for row in rows] == [
        ("CC-{YYYY}-{000}", 1, "yearly")
    ]
