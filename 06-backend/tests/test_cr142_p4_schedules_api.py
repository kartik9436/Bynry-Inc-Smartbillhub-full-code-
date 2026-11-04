# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4. The server half of
#          screens `2·3` (schedule a report), `4·1` (the Scheduled tab) and
#          `4·2`. Drawings p34 · p40 · p41, read as IMAGES per B14 rule 42.
# Rules:   BR-REP-020 CONFIRMED (internal staff only) · B14 rule 31 (no
#          database id is the visible value of a field) · CLAUDE.md hard rule 1
#          (tenant scoping) · hard rule 7 (audit_log) · hard-won law 7
# ───────────────────────────────────────────────────────
"""`/reports/schedules` — the five routes, and the ONE that must never exist.

⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7 clause 2):

  · **The routing case.** Asserting that `GET /reports/schedules` answers 200
    would pass if `reports/<str:key>` had swallowed the word and the viewer had
    answered 200 for a report named *schedules* — it does not, it answers
    422 `VAL-005`, but a status-code assertion is the wrong question either
    way. The case asserts the ROUTER resolves the path to THIS view.
  · **The recipients refusal.** A made-up uuid is refused by any lookup. The
    case uses a REAL user of a REAL second tenant, which is the only thing that
    asks whether `BR-REP-020` is enforced rather than whether uuids parse.
  · **The status column.** Asserting *a status was returned* would pass on any
    string. Each case names the value it expects and sets up the ONE condition
    that should produce it.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.reports import schedules as scheduler, schedules_api
from apps.reports.models import ReportDefinition, ReportSchedule
from apps.tenancy import services as tenancy_services
from core import jobs as core_jobs

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import api_call, seeding_ctx, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def wired(tmp_path, settings):
    """The deployment's own wiring. See `test_cr142_p4_schedules.py`'s copy for
    why `JOBS_EAGER` must be assigned here and not set in the environment."""
    settings.JOBS_EAGER = True
    previous_store, previous_dispatcher = core_jobs._store, core_jobs._dispatcher
    core_jobs.set_job_store(tenancy_services.JobStore())
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield tmp_path
    core_jobs.set_job_store(previous_store)
    core_jobs.set_job_dispatcher(previous_dispatcher)


def _staff(actor, tenant):
    """Give `actor` a MEMBERSHIP of `tenant`, which is what makes them staff.

    ⚠ **`staff_actor` CREATES A `users` ROW AND NO MEMBERSHIP, AND THAT IS WHY
    THE FIRST RUN OF EVERY RECIPIENTS CASE FAILED.** `identity.selectors.
    user_list` — the read `BR-REP-020` is enforced through, and the one the
    Settings → Users screen uses — queries `TenantMembership`, not `User`. A
    user row with no membership is somebody who exists and holds no role here,
    and the product is right to leave them out: `P4.10` sends a LINK rather
    than a file precisely so *"recipients get a link that respects their
    permissions"*, and a person with no membership can sign in to nothing.

    ⚠ **SO THE FIXTURE IS FIXED AND THE READ IS NOT.** Making `tenant_staff`
    read `User` directly would have turned every case green while quietly
    widening a signed ruling to people who have no access — the shape
    CLAUDE.md names as a check that passes wrongly, and it is exactly what the
    brief warns about: *"a fixture that lacks something is a false pass — make
    fixtures create what they need."*
    """
    from apps.identity import models as identity_models

    with seeding_ctx(tenant):
        role, _ = identity_models.Role.objects.get_or_create(
            code=actor.role, defaults={"name": actor.role.replace("_", " ").title()}
        )
        identity_models.TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=actor.user,
            defaults={"role": role, "status": identity_models.TenantMembership.STATUS_ACTIVE},
        )
    return actor


def _definition(tenant, key="ar-aging-api-fixture"):
    return ReportDefinition.objects.create(
        tenant=tenant, key=key, name="AR Ageing", dataset="invoices", group_code="finance"
    )


def test_the_router_resolves_schedules_to_its_own_view_and_not_the_viewer():
    """`P0.11`'s guarantee, one segment along.

    ⚠ **THE ROUTER, NOT A STATUS CODE.** `schedules` sits in the same URL
    position as a report key; a catch-all declared first would swallow it and a
    client asking for the list would get a 422 about a report named
    *schedules*. Resolving the PATTERN is the question — a status assertion
    would be answered by the wrong view just as readily.
    """
    from django.urls import resolve

    match = resolve("/api/brazosbend/reports/schedules")
    assert match.func is schedules_api.schedules_collection


def test_a_schedule_is_created_with_its_next_run_computed(brazos, dana):
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _definition(brazos)
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "ar-aging-api-fixture",
            "cadence": "daily",
            "format": "csv",
            "recipients": [str(dana.id)],
            "params": {"resource": "ar_aging", "filters": {}},
        },
    )
    assert response.status_code == 201, getattr(response, "data", response)
    assert response.data["status"] == "on"
    # ⚠ **COMPUTED AT CREATE, NOT LEFT NULL FOR A LATER STATEMENT.** A row saved
    # with no date is, for that instant, a schedule the sweep cannot see — and
    # if the second statement failed it would stay that way for ever, looking
    # enabled.
    assert response.data["next_run_at"] is not None
    assert response.data["next_run_at"] > timezone.now()


def test_BR_REP_020_another_tenants_real_user_is_refused(brazos, dana, lonestar, erin):
    """A REAL person at a REAL second utility — see this file's header."""
    _staff(erin, lonestar)
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _definition(brazos, key="ar-aging-refusal-fixture")
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "ar-aging-refusal-fixture",
            "cadence": "daily",
            "format": "csv",
            "recipients": [str(erin.id)],
            "params": {},
        },
    )
    assert response.status_code == 422
    # ⚠ **THE RATIFIED B12 r1 / 11b §3 G1 ENVELOPE IS FLAT — SIX KEYS, NO
    # `error` WRAPPER** (`core.errors._envelope`). This case read
    # `response.data["error"]["code"]` until `DEF-REP-6916` and raised
    # `KeyError: 'error'`, which is the GOOD outcome: a case asserting an
    # ABSENCE would have passed silently over the same mistake.
    # `test_cr139_p5_8_scan_parse.py` records the identical first draft.
    assert response.data["code"] == "VAL-005"
    # ⚠ **THE KEY MUST RESOLVE IN ALL ELEVEN CATALOGUES OR THIS REFUSAL REACHES
    # A CLERK AS SILENCE** — the click does nothing and no sentence appears.
    # `scheduledTab.dom.test.tsx` asserts the eleven; this asserts the key the
    # server actually sends is the one they hold.
    assert response.data["message_key"] == "reports.schedule.recipient_not_internal"


def test_an_email_address_cannot_become_a_recipient(brazos, dana):
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _definition(brazos, key="ar-aging-email-fixture")
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "ar-aging-email-fixture",
            "cadence": "daily",
            "format": "csv",
            "recipients": ["auditor@example.com"],
            "params": {},
        },
    )
    assert response.status_code == 422


def test_a_fifth_cadence_is_refused_above_the_database(brazos, dana):
    """The CHECK constraint alone would surface as a 500 that says nothing."""
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _definition(brazos, key="ar-aging-cadence-fixture")
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "ar-aging-cadence-fixture",
            "cadence": "fortnightly",
            "format": "csv",
            "recipients": [str(dana.id)],
            "params": {},
        },
    )
    assert response.status_code == 422
    assert response.data["message_key"] == "reports.schedule.unknown_cadence"


def test_the_list_names_people_and_serves_no_user_id_as_a_visible_value(brazos, dana):
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        definition = _definition(brazos, key="ar-aging-list-fixture")
        ReportSchedule.objects.create(
            tenant=brazos,
            definition=definition,
            cadence="daily",
            params={},
            recipients=[str(dana.id)],
            next_run_at=timezone.now() + timedelta(days=1),
            enabled=True,
        )
    response = api_call(
        schedules_api.schedules_collection,
        "get",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    assert response.status_code == 200
    row = response.data["rows"][0]
    assert row["report"] == "AR Ageing"
    # B14 rule 31 — the NAME is what a screen draws. The id travels because
    # `4·2` must re-open the picker with the right people ticked.
    assert row["recipient_names"] == [dana.user.full_name]
    # The selects' options travel WITH the page, so the screen types no list
    # out by hand (B14 rule 2's worked case).
    assert response.data["cadences"] == list(scheduler.CADENCES)
    assert {person["id"] for person in response.data["staff"]} >= {str(dana.id)}


def test_pause_clears_the_next_run_and_resume_recomputes_it(brazos, dana):
    """p41 ④, verbatim: *"Pause writes `enabled=false` … and clears
    `next_run_at`; nothing else moves."*

    ⚠ **RESUME DOES NOT RESTORE THE OLD DATE.** A schedule paused in August and
    resumed in October would otherwise be due two months ago and fire
    immediately, which is not what *resume* means to the person pressing it.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        definition = _definition(brazos, key="ar-aging-pause-fixture")
        schedule = ReportSchedule.objects.create(
            tenant=brazos,
            definition=definition,
            cadence="daily",
            params={},
            recipients=[str(dana.id)],
            next_run_at=timezone.now() + timedelta(days=1),
            enabled=True,
        )
    paused = api_call(
        schedules_api.schedule_detail,
        "patch",
        f"/api/reports/schedules/{schedule.pk}",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"enabled": False},
        schedule_id=schedule.pk,
    )
    assert paused.status_code == 200
    assert paused.data["status"] == "paused"
    assert paused.data["next_run_at"] is None

    resumed = api_call(
        schedules_api.schedule_detail,
        "patch",
        f"/api/reports/schedules/{schedule.pk}",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"enabled": True},
        schedule_id=schedule.pk,
    )
    assert resumed.status_code == 200
    assert resumed.data["status"] == "on"
    # ⚠ **A `Response` THAT HAS NOT BEEN RENDERED CARRIES PYTHON OBJECTS, NOT
    # JSON** — `present()` puts `schedule.next_run_at` on the wire as the
    # `datetime` it is, and DRF only stringifies it at render time. Comparing
    # it to `timezone.now().isoformat()` raised `TypeError: '>' not supported
    # between instances of 'datetime.datetime' and 'str'` (`DEF-REP-6916`).
    # `test_a_schedule_is_created_with_its_next_run_computed` above had it
    # right on the same object, four cases earlier.
    assert resumed.data["next_run_at"] > timezone.now()


def test_an_enabled_schedule_with_no_computable_date_reads_failing(brazos, dana):
    """The tenant with no fiscal calendar — see `schedules.py`'s docstring.

    ⚠ **`failing`, NOT `paused`.** It is switched ON and it will never fire,
    and the only honest word for that on a screen is the one that makes
    somebody look.
    """
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        definition = _definition(brazos, key="ar-aging-failing-fixture")
        schedule = ReportSchedule.objects.create(
            tenant=brazos,
            definition=definition,
            cadence="monthly_on_cycle_close",
            params={},
            recipients=[str(dana.id)],
            next_run_at=None,
            enabled=True,
        )
        assert schedules_api.status_of(schedule) == schedules_api.STATUS_FAILING


@pytest.mark.isolation
@requires_postgres
def test_another_tenants_schedule_is_a_plain_404(brazos, dana, lonestar, erin):
    """HR-1 / 11b G4: existence must not leak.

    ⚠ **THE ROW IS REAL AND BELONGS TO SOMEBODY ELSE**, which is the only
    version of this case worth running — a made-up id is refused by any
    lookup.

    ⚠ **AND IT IS `isolation` + `requires_postgres`, WHICH IS THE WHOLE POINT
    OF `DEF-REP-6916`.** `schedules_api._schedules_queryset` says in its own
    words that it adds NO `.filter(tenant_id=…)`: `report_schedules` is RLS
    FORCE (`reports/0005`) and the database is what refuses. **SQLite has no
    row-level security of any kind** (CLAUDE.md law 14), so on the default
    suite this case asserted a guarantee that cannot exist there and answered
    `200` — and a `200` there is consistent BOTH with a real hole AND with an
    application correctly relying on RLS. It proved nothing either way, which
    is law 7's own example (`G5` called 192 skips a pass).

    **THE ANSWER WAS TAKEN ON REAL PostgreSQL 16 INSTEAD, AND THERE IS NO
    LEAK**: `10-scripts/def_rep_6916_schedule_isolation_pg_proof.py`, run as a
    `NOSUPERUSER NOBYPASSRLS` role against a `proof-db.sh` clone, plants a real
    schedule for tenant B, proves tenant B's own context CAN see it (the
    red-first control), and then reads it three ways from tenant A's context —
    unfiltered `SELECT`, by its id, and through THIS handler. **0 rows, 0 rows,
    404.** This case itself was then run on that database and PASSED. So it
    belongs in the suite that runs where the guarantee exists, and `G5` is what
    makes it run there.
    """
    with tenant_ctx(lonestar):
        definition = ReportDefinition.objects.create(
            tenant=lonestar,
            key="ar-aging-foreign-fixture",
            name="AR Ageing",
            dataset="invoices",
            group_code="finance",
        )
        foreign = ReportSchedule.objects.create(
            tenant=lonestar,
            definition=definition,
            cadence="daily",
            params={},
            recipients=[str(erin.id)],
            next_run_at=timezone.now() + timedelta(days=1),
            enabled=True,
        )
    response = api_call(
        schedules_api.schedule_detail,
        "get",
        f"/api/reports/schedules/{foreign.pk}",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        schedule_id=foreign.pk,
    )
    assert response.status_code == 404


def test_creating_a_schedule_writes_an_audit_row(brazos, dana, audit_rows):
    """CLAUDE.md rule 7's posture. A standing instruction to send a utility's
    own financial reports to named people is exactly the kind of act a support
    cycle has to be able to reconstruct; p34 ④ names `audit_log` explicitly."""
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _definition(brazos, key="ar-aging-audit-fixture")
    api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "ar-aging-audit-fixture",
            "cadence": "weekly",
            "format": "csv",
            "recipients": [str(dana.id)],
            "params": {},
        },
    )
    actions = [str(row.get("action")) for row in audit_rows]
    assert "report_schedule.created" in actions


# ═══════════════════════════════════════════════════════════════════════════
# DEF-REP-6923 — THE ROLE FLOOR APPLIES TO THE WRITE PATH TOO
# ═══════════════════════════════════════════════════════════════════════════
#
# `P5.9` gives a report a `min_role` (`BR-REP-023`) and `api.report` refuses a
# RUN of one with 403. This endpoint resolved the same definition and never
# asked — so a Billing Clerk refused `staff-directory` at `2·1` could schedule
# it and have the file delivered to themselves every month. A role floor one
# endpoint enforces and another does not is not a floor, it is a detour.
#
# ⚠ **IT WAS UNREACHABLE FROM THE PRODUCT UNTIL `DEF-REP-6913` HUNG THE DOOR**,
# which is why no walk found it: `AnyTenantRole` is satisfied, and every other
# case in this file schedules an UNRESTRICTED report, so the whole family
# passed over the gap. The pair below is deliberate — the refusal alone would
# also pass on a view that refused everything.


def _restricted(tenant, key="staff-directory-api-fixture"):
    return ReportDefinition.objects.create(
        tenant=tenant,
        key=key,
        name="Staff directory",
        dataset="users",
        group_code="admin",
        min_role="system_admin",
    )


def test_def_rep_6923_a_clerk_cannot_schedule_a_report_their_role_may_not_run(brazos, dana):
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _restricted(brazos)
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="billing_clerk",
        tenant=brazos,
        data={
            "definition_key": "staff-directory-api-fixture",
            "cadence": "daily",
            "format": "csv",
            "recipients": [str(dana.id)],
            "params": {},
        },
    )
    assert response.status_code == 403, getattr(response, "data", response)
    # ⚠ THE SAME SENTENCE THE VIEWER ANSWERS. A second wording for one fact is
    # how a clerk meets two different explanations of the same refusal.
    assert response.data["message_key"] == "reports.viewer.role_refused"
    # ⚠ NOTHING WAS WRITTEN. A 403 that still created the row would be worse
    # than no gate at all, because the file would go out anyway.
    with tenant_ctx(brazos):
        assert ReportSchedule.objects.filter(definition__key="staff-directory-api-fixture").count() == 0


def test_def_rep_6923_the_role_above_the_floor_still_schedules_it(brazos, dana):
    """The other half. A refusal case alone passes on a view that refuses
    EVERYTHING — law 7 clause (2): what would make this check pass wrongly."""
    _staff(dana, brazos)
    with tenant_ctx(brazos):
        _restricted(brazos)
    response = api_call(
        schedules_api.schedules_collection,
        "post",
        "/api/reports/schedules",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "definition_key": "staff-directory-api-fixture",
            "cadence": "daily",
            "format": "csv",
            "recipients": [str(dana.id)],
            "params": {},
        },
    )
    assert response.status_code == 201, getattr(response, "data", response)
