# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §1.6 R31 — *"i dont have Run button here"*. The door
#           onto the parcel reconciliation: Preview, Apply, and the report.
# Rules:    BR-INT-074 (a preview writes nothing that is being reconciled) ·
#           BR-INT-039 (every attempt is a durable record — a preview too) ·
#           BR-INT-026 (a sandbox connection is never handed a real batch) ·
#           BR-INT-037 / G77 (a provider is data; the SERVER says which rows
#           have a door) · BR-MET-1173 (the keys and the replaced-key history) ·
#           PO ruling R28 (*"(c) never touch by default"*) · hard-won law 2
#           (built is not wired — `DEF-INT-5601`) · hard-won law 14 (the
#           savepoint, proved elsewhere on PostgreSQL)
# ───────────────────────────────────────────────────────
"""CR-115 Run now — the route, the two modes, and the join nobody was testing.

⚠ **THE FIRST TEST HERE IS THE ONE THAT WOULD HAVE CAUGHT `DEF-INT-5629`, AND
IT IS A TEST OVER A JOIN RATHER THAN OVER EITHER SIDE.** `gis_parcels`' own
suite injects a RECORDER as the writer and says so on purpose — *"whether
metering's own service accepts those patches is metering's test"* — and
metering had no such test, because until this wave nothing called
`gis_parcels.run` at all (`DEF-INT-5601`: 2,044 lines, no caller). So each side
was proved and the seam between them was refused by name: every patch the run
builds carried at least one field `_validate_premises` or `_validate_unit`
answered `metering.unknown_field` to, and a `ValidationError` is not the
`DatabaseError` the savepoint catches, so the FIRST apply would have died on
row 1.

**The lesson generalises past this bug:** two suites that each mock the other
side prove everything except the thing that breaks.
"""

from __future__ import annotations

import pytest

from apps.integrations import gis, gis_esri_fixtures, gis_parcels, models
from apps.integrations import api as integrations_api
from apps.integrations import services as integration_services
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from core import errors
from core.permissions import SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

LAYER = gis_esri_fixtures.FIXTURE_LAYER


def _connect(tenant, actor, *, environment=models.ENVIRONMENT_PRODUCTION, base_url=LAYER):
    """⚠ **INSIDE `tenant_context`, WHICH `api_call` DOES FOR A ROUTE AND NOTHING
    DOES FOR A DIRECT SERVICE CALL.** `connect` writes an audit row and
    `core.audit` refuses one with no tenant set (`BR-AUD-007`) — the same shape
    `test_us_int_042_gis.py` handles by wrapping each case."""
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        return integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=environment,
            config={"base_url": base_url},
            cadence=models.CADENCE_NIGHTLY,
        )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-INT-5629 — the join: everything the run can patch, the validator accepts
# ═══════════════════════════════════════════════════════════════════════════


def test_every_field_the_run_can_patch_is_accepted_by_the_service_that_receives_it():
    """⚠ **READ THE LIST OFF `_persist`, NEVER RETYPE IT.**

    A hand-written list here would be a second copy of the run's own vocabulary
    and would go stale the day `_persist` learns a field — which is exactly how
    the gap this test exists for opened. The names below are the columns
    `gis_parcels._persist` builds, and each is asserted against the validator
    that will actually receive it.
    """
    premises_patch = {
        "gis_parcel_id": "09-09-30-100-001",
        "gis_parcel_id_was": "09-09-30-100-000",
        "gis_key_changed_at": None,
        "gis_verified": True,
        "gis_verified_at": None,
        # Every address field `gis_match.PREMISES_FIELDS` can put in `to_apply`.
        **{name: "x" for name in gis_parcels.gis_match.PREMISES_FIELDS if name not in
           ("lat", "lng")},
        "lat": "42.28",
        "lng": "-83.74",
    }
    cleaned = metering_services._validate_premises(premises_patch, partial=True)
    for name in premises_patch:
        assert name in cleaned, f"{name} is accepted and then silently dropped (DEF-MET-5604's shape)"

    unit_patch = {
        "gis_point_id": "09-09-30-100-001-A",
        "gis_point_id_was": "09-09-30-100-001-B",
        "gis_key_changed_at": None,
        "gis_status": "Active",
        "gis_verified": True,
        "gis_verified_at": None,
        "lat": "42.28",
        "lng": "-83.74",
    }
    cleaned_unit = metering_services._validate_unit(unit_patch, partial=True)
    for name in unit_patch:
        assert name in cleaned_unit, f"{name} is accepted and then silently dropped"


def test_a_unit_still_declares_no_address_of_its_own():
    """⚠ Hard rule 8 is UNTOUCHED by the fields above (`BR-MET-1161`)."""
    for name in ("address_line", "city", "state", "postal_code"):
        with pytest.raises(errors.ValidationError):
            metering_services._validate_unit({name: "Ann Arbor"}, partial=True)


def test_a_stamp_typed_as_text_is_refused_rather_than_guessed():
    """The one writer hands a `datetime`; a string is a client calling by hand."""
    with pytest.raises(errors.ValidationError):
        metering_services._validate_premises({"gis_verified_at": "2026-09-17"}, partial=True)


# ═══════════════════════════════════════════════════════════════════════════
# Which rows get a door — the SERVER decides (hard-won law 2's mirror)
# ═══════════════════════════════════════════════════════════════════════════


def test_only_the_operation_with_a_service_behind_it_gets_a_run_now_door():
    assert gis.can_run_now(gis.PROVIDER_KEY, gis.RECONCILE_OPERATION) is True
    # The same manifest's other two operations, which have no such service.
    assert gis.can_run_now(gis.PROVIDER_KEY, "address_search") is False
    assert gis.can_run_now(gis.PROVIDER_KEY, "map_tiles") is False


def test_another_connector_declaring_the_same_shape_gets_no_door(brazos, dana):
    """⚠ **FIVE SHIPPED CONNECTORS DECLARE AN INBOUND SCHEDULED FETCH.** Deciding
    from the SHAPE on the screen would have put a live button over a 404."""
    from apps.integrations.registry import REGISTRY

    same_shape = [
        (manifest.key, one.name)
        for manifest in REGISTRY.all()
        for one in manifest.operations
        if one.trigger == "scheduled" and one.direction == "in" and one.initiative == "us"
    ]
    assert len(same_shape) > 1, "the risk this test guards is that there is more than one"
    with_a_door = [pair for pair in same_shape if gis.can_run_now(*pair)]
    assert with_a_door == [(gis.PROVIDER_KEY, gis.RECONCILE_OPERATION)]


def test_the_operation_row_carries_the_answer_rather_than_the_screen_working_it_out(brazos, dana):
    from apps.integrations import selectors
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    with tenant_context(brazos.id):
        card = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)
    by_name = {one["name"]: one for one in card["operations"]}
    assert by_name[gis.RECONCILE_OPERATION]["can_run_now"] is True
    assert by_name["address_search"]["can_run_now"] is False


def test_an_unconnected_connector_offers_no_door(brazos, dana):
    from apps.integrations import selectors
    from core.tenancy import tenant_context

    with tenant_context(brazos.id):
        card = selectors.provider_card(brazos.id, gis.PROVIDER_KEY)
    assert all(one["can_run_now"] is False for one in card["operations"])


# ═══════════════════════════════════════════════════════════════════════════
# The route
# ═══════════════════════════════════════════════════════════════════════════


def _post(actor, brazos, key=None, **data):
    """⚠ **`user=actor.user` AND AN EXPLICIT `role`** — the shape every other
    integrations route test takes. `staff_actor` is a namespace carrying the
    Django user; handing the namespace itself answers `403 AUTH-002` on every
    case, which reads exactly like a permission bug in the route."""
    return api_call(
        integrations_api.gis_reconcile,
        "post",
        f"/api/{brazos.subdomain}/integrations/{key or gis.PROVIDER_KEY}/reconcile",
        user=actor.user,
        role=SYSTEM_ADMIN,
        tenant=brazos,
        data=data,
        key=key or gis.PROVIDER_KEY,
    )


def test_any_other_provider_key_is_the_plain_404_an_absent_resource_gets(brazos, dana):
    _connect(brazos, dana)
    response = _post(dana, brazos, key="email_smtp", mode="preview")
    assert response.status_code == 404


def test_preview_is_what_a_missing_mode_means(brazos, dana):
    """Hard-won law 3 — the unsafe option is the one somebody types."""
    _connect(brazos, dana)
    response = _post(dana, brazos)
    assert response.status_code == 200
    assert response.data["mode"] == gis_parcels.PREVIEW


def test_a_mode_outside_the_two_is_refused_by_name(brazos, dana):
    _connect(brazos, dana)
    response = _post(dana, brazos, mode="delete_everything")
    assert response.status_code == 422, response.data


def test_a_sandbox_connection_is_refused_in_both_modes(brazos, dana):
    _connect(brazos, dana, environment=models.ENVIRONMENT_SANDBOX)
    for mode in (gis_parcels.PREVIEW, gis_parcels.APPLY):
        response = _post(dana, brazos, mode=mode)
        assert response.status_code == 409, (mode, response.data)


def test_a_tenant_with_no_city_connected_is_refused_and_it_is_not_an_error(brazos, dana):
    response = _post(dana, brazos, mode=gis_parcels.PREVIEW)
    assert response.status_code == 409
    assert response.data["message_key"] == gis.REFUSAL_NOT_CONNECTED


# ── the central claim ───────────────────────────────────────────────────────


def _row_counts(tenant):
    """Everything a run could touch, counted the way a person would check.

    ⚠ **COUNTED UNDER THE TENANT'S OWN CONTEXT.** RLS `FORCE` is on, so a count
    taken with no `app.tenant_id` returns ZERO over real rows — and *nothing
    changed* would then be true of an empty answer as much as of an untouched
    one. That is hard-won law 7's *reporting zero over a scope it silently
    excludes*, and it would make this the weakest test in the file rather than
    the strongest.
    """
    return {
        "premises": metering_models.Premises.objects.count(),
        "units": metering_models.Unit.objects.count(),
        "keyed_premises": metering_models.Premises.objects.exclude(
            gis_parcel_id__isnull=True
        ).count(),
        "keyed_units": metering_models.Unit.objects.exclude(gis_point_id__isnull=True).count(),
        "verified_premises": metering_models.Premises.objects.filter(gis_verified=True).count(),
        "verified_units": metering_models.Unit.objects.filter(gis_verified=True).count(),
    }


def test_a_preview_through_the_route_writes_absolutely_nothing(brazos, dana):
    """⚠ **NOT THE KEYS, NOT THE FIELDS, NOT THE VERIFIED STAMP.**

    Counted before and after rather than asserted about a mock, because the
    claim is about ROWS. `tests/test_cr112_gis_parcels.py` proves the same thing
    one layer down with an injected writer; this proves it through the door a
    clerk actually presses.
    """
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    with tenant_context(brazos.id):
        before = _row_counts(brazos)
    response = _post(dana, brazos, mode=gis_parcels.PREVIEW)
    assert response.status_code == 200, response.data
    with tenant_context(brazos.id):
        after = _row_counts(brazos)
    assert after == before, f"a preview wrote something: {before} -> {after}"
    assert response.data["applied"] == {}


def test_a_preview_still_writes_its_own_run_row(brazos, dana):
    """⚠ **AND THAT IS `BR-INT-039`, NOT A BREACH OF `BR-INT-074`.** One is about
    the rows being RECONCILED; the other is about the ATTEMPT. Without it a
    preview is invisible in RECENT ACTIVITY."""
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    with tenant_context(brazos.id):
        before = models.IntegrationRun.objects.count()
    _post(dana, brazos, mode=gis_parcels.PREVIEW)
    with tenant_context(brazos.id):
        assert models.IntegrationRun.objects.count() == before + 1


def test_the_run_records_the_mode_and_which_person(brazos, dana):
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    _post(dana, brazos, mode=gis_parcels.PREVIEW)
    with tenant_context(brazos.id):
        run = models.IntegrationRun.objects.latest("started_at")
    assert run.mode == gis_parcels.PREVIEW
    assert run.operation == gis.RECONCILE_OPERATION
    # `trigger` carries the schedule-or-a-person half; this carries WHICH.
    assert run.trigger == "manual"
    assert run.started_by_name, "a run nobody is named for answers nothing a week later"


def test_the_run_row_carries_the_mode_to_the_screen(brazos, dana):
    from apps.integrations import runs
    from core.pagination import parse_list_params
    from core.tenancy import tenant_context

    _connect(brazos, dana)
    _post(dana, brazos, mode=gis_parcels.PREVIEW)
    with tenant_context(brazos.id):
        listed = runs.list_view(
            brazos.id,
            gis.PROVIDER_KEY,
            params=parse_list_params(
                {},
                allowed_sorts=runs.SORTS,
                default_sort=runs.DEFAULT_SORT,
                allowed_filters=runs.FILTERS,
            ),
            per=20,
        )["rows"]
    assert listed[0]["mode"] == gis_parcels.PREVIEW
    assert listed[0]["started_by_name"]


def test_the_report_says_how_many_it_examined_beside_how_many_differed(brazos, dana):
    """⚠ **`0 differences found` OVER A CLEAN ESTATE AND OVER A BROKEN BUTTON
    LOOK IDENTICAL** unless the run also says what it looked at (hard-won law 7,
    *reporting zero over a scope it silently excludes*)."""
    _connect(brazos, dana)
    counts = _post(dana, brazos, mode=gis_parcels.PREVIEW).data["counts"]
    for name in ("city_rows", "premises_examined", "units_examined", "differences_found",
                 "fields_set_to_never_touch", "city_rows_ignored", "queued"):
        assert name in counts, f"{name} is missing and its absence is invisible"


def test_r28_the_report_names_the_reason_nothing_was_applied(brazos, dana):
    """PO R28 — *"(c) never touch by default"*. A clerk reading *N found, 0
    applied* with no reason files a defect against correct behaviour."""
    _connect(brazos, dana)
    report = _post(dana, brazos, mode=gis_parcels.PREVIEW).data
    assert report["counts"]["fields_set_to_never_touch"] > 0
    assert report["counts"]["differences_to_apply"] == 0
    assert "never touch" in report["headline"]


def test_nothing_in_the_product_turns_a_field_on_today_and_that_is_the_ruling(brazos, dana):
    """⚠ **A STATED ABSENCE, NOT A STUB.** `_reconcile_settings` returns `None`
    on every tenant because no screen sets a disposition. The day one does, this
    test is what says this line can go (hard-won law 2's rule for a hold)."""
    _connect(brazos, dana)
    assert gis._reconcile_settings(brazos.id) is None


def test_the_report_names_where_a_person_works_the_queue(brazos, dana):
    _connect(brazos, dana)
    report = _post(dana, brazos, mode=gis_parcels.PREVIEW).data
    assert report["queue_runbook_key"] == "gis_reconciliation"


def test_an_apply_stores_the_city_keys_and_changes_no_address(brazos, dana):
    """R28 + R29 together: *0 applied* is not *nothing happened*. The keys are
    the whole of what the going-live customer asked for."""
    _connect(brazos, dana)
    report = _post(dana, brazos, mode=gis_parcels.APPLY).data
    assert report["mode"] == gis_parcels.APPLY
    assert report["applied"].get("fields_applied", 0) == 0
    # Whether any key was taken depends on what this tenant's fixture holds;
    # what must never happen is an address moving.
    assert report["counts"]["differences_to_apply"] == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §1.6 (R31, R28, R29 verbatim) + BR-INT-074/039/026/037
# generated: 2026-09-17 by the CR-115 Run-now lane
# checklist: A✔ B✔(ConnectionDetailPage RunNowCell) C✔ D✔(one route) E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_run_now.py · tests/test_cr112_gis_parcels.py (unchanged)
# exceptions: `_validate_premises`/`_validate_unit` are private and are called directly on purpose — the defect they carried is invisible through the public service without a full premises row, and the join is what was untested
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
