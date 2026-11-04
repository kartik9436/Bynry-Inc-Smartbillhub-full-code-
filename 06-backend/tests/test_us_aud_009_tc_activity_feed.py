# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-009 ("User activity audit" — the A14 Compliance card served
#           as an IS-11 feed over the S61 dataset; owned by audit, reports
#           dedups R-2)   Screens: S61 · S44
# Rules:    BR-AUD-017 (the feed IS the S61 dataset — S61's ratified columns and
#           filter vocabulary; columns beyond that set stay unratified, R-2) ·
#           BR-AUD-014 (IS-11/BR-SHL-016 pipeline; 50k cap; every generation
#           writes its own audit row) · BR-AUD-007 (tenant-scoped like every
#           audit read) · BR-AUD-009 (System Admin + Executive)
# Journeys: J5 (month-end close — the money/approval evidence file)
# ───────────────────────────────────────────────────────
"""US-AUD-009, test case by test case.

The story's PDF half is NOT satisfied and is not pretended to be: no module in
this codebase renders a PDF, so `feed_definition()` declares `pdf: false` with
the reason and a PDF request is refused. TC-2's CSV half, its filename grammar
and the guards around it are real and are asserted here.
"""

import pytest
from django.test import override_settings

from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403

# Imported AFTER the star import and under explicit names: that import pulls in
# `services`/`selectors` from apps.metering, which would otherwise shadow these.
from apps.audit import exports, services  # noqa: E402  isort:skip
from tests.test_us_met_reads_helpers import staff_actor, tenant_ctx  # noqa: F401


@pytest.fixture()
def alex(brazos):
    """Alex Reed — Brazos Bend System Admin (the S61/feed read role)."""
    return staff_actor(brazos, "system_admin", "alex@brazosbendutilities.test")


# ── TC-1 — the card routes to THIS dataset, with the six S61 columns ────────
@pytest.mark.django_db
def test_us_aud_009_tc1__the_feed_definition_is_the_s61_dataset_and_nothing_more(brazos):
    definition = services.feed_definition()
    assert definition["key"] == "user_activity_audit"
    assert definition["owner"] == "audit"
    # The six S61 columns EXACTLY (A1 S61 addendum) — no more, no fewer.
    assert definition["columns"] == ["when", "actor", "action", "entity", "summary", "source"]
    # Parameters ARE S61's filter vocabulary (BR-AUD-009), not a second one.
    from apps.audit import selectors

    assert definition["parameters"] == list(selectors.AUDIT_FILTERS)
    assert definition["date_basis"] == "event-time"  # no money basis applies
    assert definition["row_cap"] == services.EXPORT_ROW_CAP


# ── TC-2 — the CSV, with the filename the story fixes ───────────────────────
@pytest.mark.django_db
def test_us_aud_009_tc2__the_file_is_named_for_this_report_not_for_s61(brazos):
    """§4's fixture: `brazosbend_user-activity-audit_2026-07_event-time_….csv`.

    The report segment is what makes a compliance evidence file recognisable as
    itself; the rest of the grammar is IS-9's and is shared with every export.
    """
    from datetime import datetime, timezone as tz_module
    from zoneinfo import ZoneInfo

    name = exports.artifact_filename(
        brazos.id,
        {"from": "2026-07-01", "to": "2026-07-31"},
        archive=False,
        now=datetime(2026, 8, 9, 22, 10, tzinfo=tz_module.utc),
        tz=ZoneInfo("America/Chicago"),
        report_slug=services.FEED_SLUG,
    )
    parts = name.removesuffix(".csv").split("_")
    assert parts[1] == "user-activity-audit"
    assert parts[2] == "2026-07"  # a range inside one month reads as that month
    assert parts[3] == "event-time"


@pytest.mark.django_db
@override_settings(JOBS_EAGER=False)
def test_us_aud_009_tc2b__running_the_feed_writes_its_own_audit_row(brazos, alex, audit_rows):
    with tenant_ctx(brazos):
        accepted = services.request_feed(
            actor=alex, tenant_id=brazos.id, filters={"from": "2026-07-01", "to": "2026-07-31"}
        )
    assert "job_id" in accepted
    generated = [row for row in audit_rows if row["action"] == "report.exported"]
    assert len(generated) == 1
    assert generated[0]["after"]["report"] == "user_activity_audit"
    assert generated[0]["after"]["date_basis"] == "event-time"


# ── TC-5 (negative) — nothing beyond the ratified column set ────────────────
@pytest.mark.django_db
def test_us_aud_009_tc5__a_bespoke_column_is_refused_with_the_r2_reference(brazos, alex):
    """ "login duration" is not available and is not invented (BR-AUD-017 —
    column extensions stay unratified, the reports R-2 candidate)."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as raised:
            services.request_feed(
                actor=alex,
                tenant_id=brazos.id,
                columns=["when", "actor", "login_duration"],
            )
    assert raised.value.message_key == "audit.feed.column_unratified"
    assert raised.value.params["columns"] == ["login_duration"]
    assert raised.value.params["reference"] == "R-2"


# ── PDF: declared unavailable, never faked ──────────────────────────────────
@pytest.mark.django_db
def test_us_aud_009__a_pdf_request_is_refused_because_no_renderer_exists(brazos, alex):
    """US-AUD-009 §1 asks for a compliance-class PDF. This deployment has no PDF
    renderer, so the request is REFUSED with that reason — not answered with a
    CSV wearing a .pdf name, and not 202'd for a file nobody can produce."""
    assert services.feed_definition()["formats"]["pdf"] is False
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as raised:
            services.request_feed(actor=alex, tenant_id=brazos.id, fmt="pdf")
    assert raised.value.message_key == "audit.feed.format_unavailable"
    assert "no PDF renderer" in raised.value.params["reason"]


# ── TC-6 (negative) — the 50k guard, shared with the S61 export ─────────────
@pytest.mark.django_db
def test_us_aud_009_tc6__an_oversize_run_is_refused_before_any_file_exists(
    brazos, alex, monkeypatch
):
    class _Big:
        def count(self):
            return 68_000  # the story's own oversize figure

    monkeypatch.setattr(services.selectors, "audit_result_set", lambda *a, **k: _Big())
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as raised:
            services.request_feed(actor=alex, tenant_id=brazos.id)
    assert raised.value.message_key == "audit.export.row_cap_exceeded"
    assert raised.value.params["rows"] == 68_000
    assert raised.value.params["cap"] == 50_000


# ── TC-7 (immutability) — the feed READS; it writes only its own row ────────
@pytest.mark.django_db
def test_us_aud_009_tc7__the_feed_has_no_write_path_into_the_trail(brazos):
    """No edit, no re-write of history, no run-record mutation. The module
    publishes nothing of the kind, and this asserts the absence."""
    for forbidden in ("update_feed_run", "edit_audit_row", "rewrite_feed"):
        assert not hasattr(services, forbidden)


# ── TC-8 (isolation) — the role gate is the S61 gate, no wider ──────────────
@pytest.mark.django_db
def test_us_aud_009_tc8__a_billing_clerk_cannot_run_the_compliance_feed(brazos, marcus):
    """BR-AUD-009: System Admin + Executive. A report over the audit dataset
    grants nothing the dataset itself does not."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError) as raised:
            services.request_feed(actor=marcus, tenant_id=brazos.id)
    assert raised.value.br_ref == "BR-AUD-009"
