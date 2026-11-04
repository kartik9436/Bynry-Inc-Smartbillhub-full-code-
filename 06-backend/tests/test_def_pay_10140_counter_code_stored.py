# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10140 — a clerk who opened, closed and re-opened a counter
#           on one day (CTR-261013-BS, 06:24–06:44 then 13:04) could neither
#           open the second one nor have it force-closed: every door named it
#           by a code that matched TWO tills, and the resolver refused.
# Ruling:   decision log 2026-10-14 *"G1–G4 APPROVED"* item 2 (G2) — the code is
#           STORED at open and unique per tenant; a repeat gets `-2`, `-3`;
#           existing clashes are repaired oldest-first.
# Rules:    CLAUDE.md hard rule 1 (per-tenant) · hard-won law 14 (the race is
#           proved on PostgreSQL, where a refused INSERT poisons the
#           transaction) · law 7 (each case was run RED before the fix)
# ───────────────────────────────────────────────────────
"""The counter's code is a STORED fact, and a second till the same day is reachable.

Run on both databases — the race case only means something on PostgreSQL:

    pytest tests/test_def_pay_10140_counter_code_stored.py
    CELERY_BROKER_URL=memory:// JOBS_EAGER=false DATABASE_URL=… \\
        pytest tests/test_def_pay_10140_counter_code_stored.py \\
        --ds=config.settings.pgtest --create-db
"""

from __future__ import annotations

import importlib
import threading
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.utils import timezone

from apps.payments import counters, counters_api
from apps.payments import models as payment_models
from apps.payments.counter_session_models import CounterSession
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import published_content_models as content_models
from core import errors
from core import tenancy as core_tenancy

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · marcus
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call, seeding_ctx

#: The PO's own report: opened 06:24, closed 06:44, opened again 13:04.
FIRST_OPEN = datetime(2026, 10, 13, 6, 24, tzinfo=UTC)
FIRST_CLOSE = datetime(2026, 10, 13, 6, 44, tzinfo=UTC)
SECOND_OPEN = datetime(2026, 10, 13, 13, 4, tzinfo=UTC)
BASE = "CTR-261013-BS"


def _named(actor, full_name):
    """Give a fixture person the initials the case needs (`BS`)."""
    from apps.identity import models as identity_models

    with seeding_ctx(actor.user.tenant):
        identity_models.User.objects.filter(pk=actor.user.pk).update(full_name=full_name)
    actor.user.refresh_from_db()
    return actor


def _centre(tenant, slug="main-office"):
    with seeding_ctx(tenant):
        return content_models.ServiceCentre.objects.create(
            tenant=tenant, slug=slug, name="Main office", address="101 Bend Road"
        )


def _open(actor, centre, opened_at):
    return counters.open_counter(
        actor,
        service_centre_id=centre.slug,
        opening_float=Decimal("200.0000"),
        opened_at=opened_at,
    )


def _close_balanced(actor, session, closed_at):
    return counters.close_counter(
        actor, session_id=session.pk, counted_totals={"cash": "200.00"}, closed_at=closed_at
    )


def _signed_in(actor):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=actor.user.pk, pk=actor.user.pk, is_authenticated=True, role=actor.role
    )


@pytest.fixture()
def bianca(brazos):
    """The clerk in the report — a Billing Clerk whose initials are `BS`."""
    return _named(staff_actor(brazos, "billing_clerk", "bianca@brazosbend.test"), "Bianca Soto")


@pytest.fixture()
def ben(brazos):
    """A second clerk who shares her initials."""
    return _named(staff_actor(brazos, "billing_clerk", "ben@brazosbend.test"), "Ben Sato")


# ════════════════════════════════════════════════════════════════════════════
# THE REPORT, REPRODUCED
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_the_same_person_twice_in_a_day_gets_two_codes_and_both_open(brazos, bianca, dana):
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        first = _open(bianca, centre, FIRST_OPEN)
        _close_balanced(bianca, first.session, FIRST_CLOSE)
        second = _open(bianca, centre, SECOND_OPEN)

        first.session.refresh_from_db()
        second.session.refresh_from_db()
        assert first.session.code == BASE
        assert second.session.code == f"{BASE}-2"

        # The doors: the address (detail by code), and what every row serves.
        assert counters.counter_detail(BASE)["id"] == str(first.session.pk)
        detail = counters.counter_detail(f"{BASE}-2")
        assert detail["id"] == str(second.session.pk)
        assert detail["code"] == f"{BASE}-2"
        # The UUID still resolves (the unambiguous name is still accepted).
        assert counters.counter_detail(str(second.session.pk))["code"] == f"{BASE}-2"

        # Force close BY ITS CODE — the second thing the PO could not do.
        sealed = counters.force_close_counter(
            dana,
            session_id=f"{BASE}-2",
            reason="Shift ended without a count",
            closed_at=datetime(2026, 10, 13, 18, 0, tzinfo=UTC),
        )
    assert sealed.session.pk == second.session.pk
    assert sealed.session.close_kind == payment_models.COUNTER_CLOSE_FORCED


@pytest.mark.django_db
def test_the_list_row_carries_the_stored_code_not_a_recomposed_one(brazos, bianca):
    """A rename after open must not move the code — the label is a stored fact."""
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        opened = _open(bianca, centre, FIRST_OPEN)
    _named(bianca, "Zoe Quinn")
    with tenant_ctx(brazos):
        opened.session.refresh_from_db()
        row = counters.counter_row(
            CounterSession.objects.select_related("owner").get(pk=opened.session.pk)
        )
        assert row["code"] == BASE
        assert counters.counter_detail(BASE)["id"] == str(opened.session.pk)


@pytest.mark.django_db
def test_two_people_sharing_initials_get_distinct_codes(brazos, bianca, ben):
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        hers = _open(bianca, centre, FIRST_OPEN)
        his = _open(ben, centre, SECOND_OPEN)
        assert hers.session.code == BASE
        assert his.session.code == f"{BASE}-2"
        assert counters.counter_detail(BASE)["owner_name"] == "Bianca Soto"
        assert counters.counter_detail(f"{BASE}-2")["owner_name"] == "Ben Sato"


@pytest.mark.django_db
def test_the_code_is_unique_per_TENANT_and_does_not_cross(brazos, lonestar, bianca):
    """Hard rule 1. Another utility's `BS` on the same day takes the plain base,
    and neither utility can reach the other's till by its code."""
    erin = _named(staff_actor(lonestar, "system_admin", "bs@lsrwater.test"), "Bo Stone")
    brazos_centre = _centre(brazos)
    lonestar_centre = _centre(lonestar)
    with tenant_ctx(brazos):
        ours = _open(bianca, brazos_centre, FIRST_OPEN)
    with tenant_ctx(lonestar):
        theirs = _open(erin, lonestar_centre, FIRST_OPEN)
        assert theirs.session.code == BASE  # no -2: the series is per tenant
        assert counters.counter_detail(BASE)["id"] == str(theirs.session.pk)
        with pytest.raises(PaymentRuleError):
            counters.counter_detail(str(ours.session.pk))
    with tenant_ctx(brazos):
        assert counters.counter_detail(BASE)["id"] == str(ours.session.pk)


@pytest.mark.django_db
def test_the_endpoint_answers_200_for_the_second_counter(brazos, bianca):
    """The exact request in the PO's error report: `GET /counters/<code>`."""
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        first = _open(bianca, centre, FIRST_OPEN)
        _close_balanced(bianca, first.session, FIRST_CLOSE)
        _open(bianca, centre, SECOND_OPEN)
    response = api_call(
        counters_api.counter_detail,
        "get",
        path=f"/api/counters/{BASE}-2",
        user=_signed_in(bianca),
        role=bianca.role,
        tenant=brazos,
        counter_id=f"{BASE}-2",
    )
    assert response.status_code == 200, response.data
    assert response.data["code"] == f"{BASE}-2"
    assert response.data["closed_at"] is None


@pytest.mark.django_db
def test_the_reported_request_no_longer_refuses(brazos, bianca, dana):
    """The PO's error report, verbatim: `GET /counters/CTR-261013-BS` → 422
    `payments.counter.refused`, and Force close refused the same way. Before the
    fix both tills composed that one code and the resolver refused it."""
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        first = _open(bianca, centre, FIRST_OPEN)
        _close_balanced(bianca, first.session, FIRST_CLOSE)
        second = _open(bianca, centre, SECOND_OPEN)
    response = api_call(
        counters_api.counter_detail,
        "get",
        path=f"/api/counters/{BASE}",
        user=_signed_in(bianca),
        role=bianca.role,
        tenant=brazos,
        counter_id=BASE,
    )
    assert response.status_code == 200, response.data
    assert response.data["id"] == str(first.session.pk)
    # And the second till is reachable by the code its own row serves.
    listed = counters.counter_rows(
        [CounterSession.objects.select_related("owner").get(pk=second.session.pk)]
    )[0]["code"]
    assert listed != BASE
    forced = api_call(
        counters_api.counter_force_close,
        "post",
        path=f"/api/counters/{listed}/force-close",
        user=_signed_in(dana),
        role=dana.role,
        tenant=brazos,
        # The door checks the moment against the utility's TODAY, so it is now.
        data={"note": "Shift ended", "closed_at": timezone.now().isoformat()},
        counter_id=listed,
    )
    assert forced.status_code == 200, forced.data
    with tenant_ctx(brazos):
        second.session.refresh_from_db()
    assert second.session.close_kind == payment_models.COUNTER_CLOSE_FORCED


@pytest.mark.django_db
def test_an_unknown_code_is_refused_with_its_own_key(brazos, bianca):
    """The screen renders the server's KEY, so the key must say what happened."""
    response = api_call(
        counters_api.counter_detail,
        "get",
        path="/api/counters/CTR-261013-ZZ",
        user=_signed_in(bianca),
        role=bianca.role,
        tenant=brazos,
        counter_id="CTR-261013-ZZ",
    )
    assert response.status_code == 422, response.data
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["message_key"] == "payments.counter.not_found"


# ════════════════════════════════════════════════════════════════════════════
# THE BACKFILL — existing clashes, repaired oldest first
# ════════════════════════════════════════════════════════════════════════════
def _backfill_module():
    return importlib.import_module(
        "apps.payments.migrations.0050_def_pay_10140_counter_code_stored"
    )


@pytest.mark.django_db
def test_the_backfill_repairs_a_clash_oldest_first_and_never_moves_a_code(brazos, bianca):
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        first = _open(bianca, centre, FIRST_OPEN)
        _close_balanced(bianca, first.session, FIRST_CLOSE)
        second = _open(bianca, centre, SECOND_OPEN)
        # The state every row was in before the column existed.
        CounterSession.objects.filter(tenant=brazos).update(code=None)

        # And the safety net still refuses the clash BY NAME before the repair.
        with pytest.raises(counters.CounterCodeAmbiguous):
            counters.counter_detail(BASE)

    class _Editor:
        pass

    editor = _Editor()
    editor.connection = connection
    _backfill_module().store_existing_codes(django_apps, editor)
    _backfill_module().store_existing_codes(django_apps, editor)  # idempotent

    with tenant_ctx(brazos):
        first.session.refresh_from_db()
        second.session.refresh_from_db()
        assert first.session.code == BASE  # the 06:24 counter keeps its number
        assert second.session.code == f"{BASE}-2"  # the 13:04 one is repaired
        assert counters.counter_detail(f"{BASE}-2")["id"] == str(second.session.pk)


@pytest.mark.django_db
def test_the_backfill_and_the_service_compose_the_same_base(brazos, bianca):
    """Two spellings of one rule would let the backfill hand out a code the
    service then recomposes differently — the drift this defect is made of."""
    centre = _centre(brazos)
    with tenant_ctx(brazos):
        opened = _open(bianca, centre, FIRST_OPEN)
        row = CounterSession.objects.select_related("owner").get(pk=opened.session.pk)
        frozen = _backfill_module()._compose_base(
            row.opened_at, row.owner.full_name, row.owner.email
        )
        assert frozen == counters.composed_code_base(row) == BASE


# ════════════════════════════════════════════════════════════════════════════
# THE RACE — two people with one base pressing Start at once (PostgreSQL only)
# ════════════════════════════════════════════════════════════════════════════
@requires_postgres
@pytest.mark.django_db(transaction=True)
def test_two_opens_at_once_both_succeed_with_distinct_codes(brazos, bianca, ben, monkeypatch):
    """Both terminals compute the SAME free code, then both INSERT.

    The barrier holds each thread after it has chosen a code and before it
    writes, so the collision is forced rather than hoped for. On PostgreSQL the
    loser's INSERT waits on the winner's index entry, fails once the winner
    commits, and — because the INSERT is inside a SAVEPOINT — retries on a
    still-usable transaction. Without the savepoint the retry would meet
    `InFailedSqlTransaction` (hard-won law 14); without the retry the loser's
    clerk would read a constraint error.
    """
    centre = _centre(brazos)
    real = counters._next_free_code
    barrier = threading.Barrier(2, timeout=20)
    local = threading.local()

    def _held(tenant_id, base):
        code = real(tenant_id, base)
        if not getattr(local, "held", False):
            local.held = True
            barrier.wait()
        return code

    monkeypatch.setattr(counters, "_next_free_code", _held)
    results: dict[str, object] = {}

    def _terminal(actor, label, moment):
        try:
            with core_tenancy.tenant_context(brazos.id):
                results[label] = _open(actor, centre, moment).session.code
        except BaseException as exc:  # noqa: BLE001 — reported, asserted below
            results[label] = exc
        finally:
            connection.close()

    threads = [
        threading.Thread(target=_terminal, args=(bianca, "bianca", FIRST_OPEN)),
        threading.Thread(target=_terminal, args=(ben, "ben", SECOND_OPEN)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert not any(isinstance(value, BaseException) for value in results.values()), results
    assert sorted(results.values()) == [BASE, f"{BASE}-2"]
    with tenant_ctx(brazos):
        assert CounterSession.objects.filter(tenant=brazos, code__startswith=BASE).count() == 2
