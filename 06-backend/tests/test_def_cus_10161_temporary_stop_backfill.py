# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10161 — pre-2.580 portal stop asks have no temporary-stop row
# Rules:    BR-CUS-1120 · BR-CUS-1121 · BR-CWP-026 · hard rules 1, 7
# ───────────────────────────────────────────────────────
"""A stop ask raised the way 2.575.1 raised it becomes a *Temporary stop*.

The requests are created exactly as the pre-2.580 portal did — ONE
`service_requests` row through `create_from_portal`, carrying the sentence the
portal composes, and no `temporary_stops` row. The two worked examples are the
PO's own from WDMWW Loader Test: `SR-26-0017` (13 Oct → 16 Oct, no reason) and
`SR-26-0022` (14 Oct → 28 Oct, *vacation*).
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from io import StringIO

import pytest
from django.apps import apps as global_apps
from django.core.management import call_command
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as srs
from apps.customers import temporary_stop, temporary_stop_backfill
from apps.customers.temporary_stop_models import TemporaryStop
from apps.portal import services as portal_services
from apps.portal.seams import customers_seam
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

pytestmark = pytest.mark.django_db


def _sentence(account_no, stop_from, start_again=None, reason=None) -> str:
    """The clerk's sentence, composed by the PORTAL's own function."""
    return portal_services._stop_restart_words(
        {
            "account_no": account_no,
            "stop_from": stop_from,
            "start_again": start_again,
            "reason": reason,
        }
    )


def _old_style_request(tenant, said):
    """A request exactly as 2.575.1 wrote it: the row and the sentence, nothing else."""
    with tenant_context(tenant.id):
        return srs.create_from_portal(
            {
                "applicant_kind": "person",
                "applicant_name": "Maria Alvarez",
                "applicant_email": "maria@example.test",
                "applicant_phone": "512-555-0101",
                "address_as_given": "1408 Elm St, Unit A",
                "what_they_said": said,
            }
        )


def _run(dry_run=False) -> str:
    out = StringIO()
    call_command("backfill_temporary_stops", *(["--dry-run"] if dry_run else []), stdout=out)
    return out.getvalue()


@pytest.fixture()
def pine(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    return pine_hill, sarah, elm_street_account(pine_hill, sarah)


# ── the reader matches the writer ───────────────────────────────────────────
def test_the_parse_round_trips_the_portals_own_sentence():
    assert temporary_stop_backfill.STOP_RESTART_MARKER == customers_seam.STOP_RESTART_MARKER
    said = _sentence("AC-2026-00551", "2026-10-13", "2026-10-16")
    assert said == (
        "Asked through the customer portal to stop service on account AC-2026-00551 from "
        "2026-10-13, starting again on 2026-10-16. The account stays open and standing "
        "charges keep running."
    )
    assert temporary_stop_backfill.parse(said) == {
        "account_no": "AC-2026-00551",
        "stop_from": date(2026, 10, 13),
        "restart_on": date(2026, 10, 16),
        "reason": None,
    }
    vacation = temporary_stop_backfill.parse(
        _sentence("AC-2026-00551", "2026-10-14", "2026-10-28", "Going on vacation\nback soon")
    )
    assert vacation["restart_on"] == date(2026, 10, 28)
    assert vacation["reason"] == "Going on vacation\nback soon"
    no_restart = temporary_stop_backfill.parse(_sentence("AC-2026-00551", "2026-10-14"))
    assert no_restart["restart_on"] is None and no_restart["stop_from"] == date(2026, 10, 14)
    # The portal's word for a missing account or date does not parse.
    assert temporary_stop_backfill.parse(_sentence(None, "2026-10-14")) is None
    assert temporary_stop_backfill.parse(_sentence("AC-1", None)) is None
    assert temporary_stop_backfill.parse("Asked through the customer portal: hello") is None


# ── the two worked examples ─────────────────────────────────────────────────
def test_both_example_requests_become_temporary_stops(pine, audit_rows):
    tenant, _sarah, account = pine
    sr17 = _old_style_request(tenant, _sentence(account.account_no, "2026-10-13", "2026-10-16"))
    sr22 = _old_style_request(
        tenant, _sentence(account.account_no, "2026-10-14", "2026-10-28", "Going on vacation")
    )
    with tenant_context(tenant.id):
        # THE DEFECT: before the backfill neither is a temporary stop.
        assert temporary_stop.kind_of(sr17) is None
        assert temporary_stop.kinds_for([sr17.id, sr22.id]) == {}
        assert reads.detail(sr17.id)["temporary_stop"] is None

    out = _run()
    assert "2 portal stop request(s) given a temporary stop" in out

    with tenant_context(tenant.id):
        assert temporary_stop.kinds_for([sr17.id, sr22.id]) == {
            str(sr17.id): "temporary_stop",
            str(sr22.id): "temporary_stop",
        }
        first = TemporaryStop.objects.get(request_id=sr17.id)
        assert (first.account_id, first.stop_from, first.restart_on, first.reason) == (
            account.pk,
            date(2026, 10, 13),
            date(2026, 10, 16),
            None,
        )
        assert (first.status, first.channel) == ("requested", "customer_portal")
        second = TemporaryStop.objects.get(request_id=sr22.id)
        assert (second.stop_from, second.restart_on, second.reason) == (
            date(2026, 10, 14),
            date(2026, 10, 28),
            "Going on vacation",
        )
        assert reads.detail(sr17.id)["header"]["classification"] == "temporary_stop"
        # The request itself and the account did not move (BR-CWP-026).
        assert customers_models.ServiceRequest.objects.get(pk=sr17.id).state == "submitted"
        assert (
            customers_models.Account.objects.select_related("status").get(pk=account.pk).status.code
            == "active"
        )
    # Hard rule 7: the live path's audit row on the stop, and the backfill's on the request.
    assert "temporary_stop.requested" in [
        r["action"] for r in audit_rows if str(r["entity_id"]) == str(first.id)
    ]
    assert "temporary_stop.backfilled" in [
        r["action"] for r in audit_rows if str(r["entity_id"]) == str(sr17.id)
    ]


def test_a_no_restart_sentence_becomes_a_stop_with_no_restart_date(pine):
    tenant, _sarah, account = pine
    request = _old_style_request(tenant, _sentence(account.account_no, "2026-11-01"))
    _run()
    with tenant_context(tenant.id):
        stop = TemporaryStop.objects.get(request_id=request.id)
        assert stop.stop_from == date(2026, 11, 1) and stop.restart_on is None


# ── what it leaves alone, and counts ────────────────────────────────────────
def test_unparseable_and_unknown_account_requests_are_left_alone_and_counted(pine):
    tenant, _sarah, account = pine
    unreadable = _old_style_request(tenant, _sentence(None, "2026-10-20", "2026-11-20"))
    unknown = _old_style_request(tenant, _sentence("AC-9999-99999", "2026-10-20", "2026-11-20"))
    good = _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
    out = _run()
    assert "1 portal stop request(s) given a temporary stop" in out
    assert "1 unreadable, 1 naming no account here, 0 failed" in out
    assert unreadable.request_no in out and unknown.request_no in out
    with tenant_context(tenant.id):
        assert not TemporaryStop.objects.filter(request_id__in=[unreadable.id, unknown.id]).exists()
        assert TemporaryStop.objects.filter(request_id=good.id).exists()
        for request in (unreadable, unknown):
            row = customers_models.ServiceRequest.objects.get(pk=request.id)
            assert (row.state, row.what_they_said) == ("submitted", request.what_they_said)


def test_a_dry_run_counts_and_writes_nothing(pine):
    tenant, _sarah, account = pine
    _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
    assert "DRY RUN" in _run(dry_run=True)
    with tenant_context(tenant.id):
        assert not TemporaryStop.objects.exists()


def test_a_second_run_writes_nothing(pine):
    tenant, _sarah, account = pine
    _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
    assert "1 portal stop request(s)" in _run()
    assert "0 portal stop request(s)" in _run()
    with tenant_context(tenant.id):
        assert TemporaryStop.objects.count() == 1


def test_closed_and_decided_requests_are_not_touched(pine):
    tenant, _sarah, account = pine
    asked = {
        state: _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
        for state in ("refused", "completed", "approved", "withdrawn", "closed")
    }
    with tenant_context(tenant.id):
        for state, request in asked.items():
            customers_models.ServiceRequest.objects.filter(pk=request.id).update(state=state)
    assert "0 portal stop request(s)" in _run()
    with tenant_context(tenant.id):
        assert not TemporaryStop.objects.exists()


def test_each_utility_reads_only_its_own_accounts(pine, oak_ridge):
    tenant, _sarah, account = pine
    # Oak Ridge holds a request naming PINE HILL's account number.
    foreign = _old_style_request(
        oak_ridge, _sentence(account.account_no, "2026-10-20", "2026-11-20")
    )
    own = _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
    out = _run()
    assert "1 portal stop request(s) given a temporary stop" in out
    assert "1 naming no account here" in out and foreign.request_no in out
    # Filtered by tenant as well as RLS-scoped: SQLite has no RLS.
    with tenant_context(oak_ridge.id):
        assert not TemporaryStop.objects.filter(tenant_id=oak_ridge.id).exists()
        assert not TemporaryStop.objects.filter(request_id=foreign.id).exists()
    with tenant_context(tenant.id):
        stop = TemporaryStop.objects.get(tenant_id=tenant.id)
        assert (stop.request_id, stop.tenant_id) == (own.id, tenant.id)


# ── the migration runs the same function ────────────────────────────────────
def test_the_migration_backfills_and_returns_early_when_there_is_nothing(pine, capsys):
    tenant, _sarah, account = pine
    migration = importlib.import_module(
        "apps.customers.migrations.0086_def_cus_10161_temporary_stop_backfill"
    )
    editor = type("Editor", (), {"connection": connection})()
    migration.backfill(global_apps, editor)
    assert capsys.readouterr().out == ""  # nothing to do, nothing printed
    request = _old_style_request(tenant, _sentence(account.account_no, "2026-10-20", "2026-11-20"))
    migration.backfill(global_apps, editor)
    assert "1 portal stop request(s) given a temporary stop" in capsys.readouterr().out
    with tenant_context(tenant.id):
        assert TemporaryStop.objects.filter(request_id=request.id).exists()


# ── SR-26-0017: the clerk can now process it ────────────────────────────────
def test_a_three_day_backfilled_ask_is_refused_then_approved_on_edited_dates(pine):
    tenant, sarah, account = pine
    sr17 = _old_style_request(tenant, _sentence(account.account_no, "2026-10-13", "2026-10-16"))
    _run()
    with tenant_context(tenant.id):
        window = reads.detail(sr17.id)["temporary_stop"]
        assert window["kind"] == "temporary_stop"
        assert window["stop"]["days"] == 3
        assert "too_short" in [p["code"] for p in window["problems"]]
        # The Approve window's own refusal, on the customer's dates.
        with pytest.raises(errors.BizError):
            temporary_stop.approve_request(sarah, sr17.id)
        # New connection / Move-in are not the way to process it.
        with pytest.raises(errors.BizError) as wrong_door:
            srs.approve_and_raise(sarah, sr17.id, outcome="move_in")
        assert wrong_door.value.message_key == temporary_stop.KEY_USE_OWN_APPROVAL
        # The clerk agrees new dates with the customer and approves THOSE.
        today = temporary_stop.today()
        start = today + timedelta(days=2)
        answer = temporary_stop.approve_request(
            sarah,
            sr17.id,
            stop_from=start.isoformat(),
            restart_on=(start + timedelta(days=12)).isoformat(),
        )
        assert answer["stop"]["status"] == "scheduled"
        assert answer["stop"]["days"] == 12
        approved = customers_models.ServiceRequest.objects.get(pk=sr17.id)
        assert (approved.state, approved.outcome) == ("approved", "temporary_stop")
