# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 (POST /billing/runs — S31 step 1's exit: one idempotent
#           `bill_runs` row) · US-BIL-002 (GET /billing/runs/{id}/findings —
#           S31.2 "Check what we found") · US-BIL-003
#           (GET /billing/runs/{id}/exceptions + .../exceptions/{caseId}/resolve
#           — S31.3's case tables and the recorded decision)
#           Screens: S31 · S31.2 · S31.3
# Rules:    BR-BIL-005 (a run is idempotent on tenant+cycle+period; a repeat is
#           refused with who/when/link) · BR-BIL-015 (a missing read is a CHOICE
#           — estimate | hold | bill_without_service) · BR-BIL-003 (a late-fee
#           waiver is manual, never bulk) · BR-BIL-040 (a finding is surfaced in
#           the tab that owns its STAGE's inputs — the reason→stage map is the
#           SERVER's) · BR-BIL-050 (the run row is what every later phase hangs
#           off) · BR-BIL-060 (bulk everywhere — N rows, one bulk_action_id) ·
#           BR-BIL-061 (base-only billing is a recorded staff opt-in) ·
#           BR-BIL-024 (the bill date is the CYCLE's — the only one in the
#           schema) · BR-RAT-007 (price on the SERVICE date) · BR-TEN-003 /
#           HR-1 (cross-tenant reads as absent) · BR-TEN-043 (event-time law —
#           no wall clock decides a service date)
# ───────────────────────────────────────────────────────
"""The four `/billing/runs` routes S31 has been calling against a 404.

WHY THIS FILE IS MOSTLY ABOUT KEY NAMES. `07-frontend/src/api/endpoints.ts`
declares `BillRunFindings`, `RunReadyAccount`, `RunServiceReading`,
`RunAccountProblem` and `BillRunExceptionRow` field for field against the
dataclasses in `apps/billing/runs.py` and `apps/billing/contracts.py` — mirrored
by the frontend lane because nothing had ratified a body. A JSON key becomes a
contract the moment a screen reads it, so every response's key set is asserted
EXACTLY here rather than sampled: a rename on either side goes red in this file
instead of in a blank panel on a clerk's screen.

The negative assertions are the ones that matter, as they were for the S30 reads:

  * `totals` on the exceptions envelope is EMPTY, because `prepare_run` returns
    no money at all — and an empty map is the honest "no case has a served Σ",
    which `bulkSelectionSummary` renders as "the total is not served". A zero
    would be a money claim.
  * `customer_name` is null on every case row: the only published customers read
    takes an Account INSTANCE and billing may not import another module's model
    (B1 / G6). Null is "not read", not "no name".
  * a cycle with no bill DAY (OQ-344) REFUSES the findings pass rather than reaching
    for a clock (BR-TEN-043 / G6) or for the period's end.
  * `stage` rides on every finding and is the SERVER's `STAGE_BY_REASON` — the
    frontend deleted its copy of that map when this landed.

The route-mounting cases sit here for the reason the S30 lane put them in its
own file: an `api.py` that exports `urlpatterns` nothing includes is not an
endpoint, and every other test in this file passes while that is true.
"""

import uuid
from datetime import date

import pytest

from apps.billing import api as billing_api
from apps.billing import decisions as billing_decisions
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from core import errors, idempotency

from tests.isolation_helpers import (
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
BILL_DATE = date(2026, 7, 1)


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — one cycle, one billable unit, one blocked unit
# ══════════════════════════════════════════════════════════════════════════
def a_dated_cycle(tenant, code="06-A", bill_date=BILL_DATE, due_days=21):
    """A cycle carrying its BILL DAY — the run's FALLBACK service date.

    ⚠ **AMENDED 2026-08-23 by OQ-344 (RC-W6).** `cycles.bill_date` — a stored
    calendar date — is dropped (metering 0023). The surviving default is the
    bill DAY, and a run with no typed date resolves it as *"the bill day, in the
    month after the period ends"* (PO verbatim: *"I'd say B - these are defualt
    - user can override"*). This helper still TAKES a `bill_date`, because every
    case below is written against one, and stores its DAY: the period here ends
    30 June, so a bill day of 1 resolves to **1 July** — `BILL_DATE` exactly, and
    every expectation in this file is unchanged.

    AMENDED 2026-08-11 by the PO's OQ-122 ruling (BR-BIL-070). This docstring
    used to say *"the only bill date in the schema"*, quoting
    `issue.derive_due_date`; that is no longer true — `bill_runs.bill_date`
    carries the date the CLERK typed on S31 step 1 and is what the run prices
    on. The cycle's date is what a run uses when nobody typed one, which is
    every run in this file except the ones that say otherwise. A run with
    NEITHER cannot be prepared at all.
    """
    from apps.metering import models as metering_models

    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields; `window_start`/`window_end` were dropped
        # columns (metering 0021) and the window is derived from these two.
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        # OQ-344 — the DAY, not the date. `None` means the cycle has no default
        # at all, which is what the refusal case below needs.
        bill_day=bill_date.day if bill_date is not None else None,
        due_days=due_days,
    )


def a_run_world(tenant, actor, *, bill_date=BILL_DATE):
    """The world every test below runs against: a cycle, a plan, one metered
    unit with a committed read, and one unit whose gas has no read at all."""
    cycle = a_dated_cycle(tenant, bill_date=bill_date)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-0001", label="Unit A")
    account = an_account(tenant, unit["id"], "ACC-1042")
    return cycle, plan, account


def an_unplanned_unit(tenant, actor, cycle, *, asset_no="M-0002", label="Unit B"):
    """A metered unit ON the cycle that no plan was ever assigned to.

    Built without `assign_unit_plan` rather than by deleting the assignment —
    a unit whose plan is missing because nobody set one is the real S31.2 case
    (a new premises billed before Plans & Rates was finished), and it exercises
    the same stage-1 refusal the deletion would.
    """
    from apps.metering import models as metering_models

    from tests.test_us_met_reads_helpers import a_meter

    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")  # noqa: F405
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])  # noqa: F405
    a_meter(actor, asset_no=asset_no, unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    return unit


def a_published_template_id():
    """The tenant's seeded, published fallback template (DEF-123) — a run now
    REQUIRES a published template at Scope (bulk bill run plan B4)."""
    from apps.billing import templates_service

    template = templates_service.tenant_fallback_template()
    if template is None or templates_service.published_version(template) is None:
        templates_service.seed_platform_default(on_date=date(2026, 1, 1))
        template = templates_service.tenant_fallback_template()
    return str(template.pk)


def created_run(tenant, actor_user, cycle, **overrides):
    """⚠ AMENDED 2026-09-30 (bulk bill run plan B3/B4): the body carries a run
    name and a published template, both now REQUIRED, and no longer
    `scope_services` — the PO removed the services filter, so the server no
    longer reads it."""
    with tenant_ctx(tenant):
        template_id = a_published_template_id()
    body = {
        "cycle_id": str(cycle.id),
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "bill_date": BILL_DATE.isoformat(),
        "label": "June 2026 · Brazos",
        "template_id": template_id,
    }
    body.update(overrides)
    return api_call(
        billing_api.bill_runs,
        "post",
        user=actor_user,
        role="billing_clerk",
        tenant=tenant,
        data=body,
    )


def findings_of(tenant, run_id, role="billing_clerk"):
    return api_call(
        billing_api.run_findings,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        run_id=str(run_id),
    )


def exceptions_of(tenant, run_id, role="billing_clerk"):
    return api_call(
        billing_api.run_exceptions,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        run_id=str(run_id),
    )


def resolve_case(tenant, actor_user, run_id, case_id, body, role="billing_clerk"):
    return api_call(
        billing_api.run_exception_resolve,
        "post",
        user=actor_user,
        role=role,
        tenant=tenant,
        run_id=str(run_id),
        case_id=case_id,
        data=body,
    )


def envelope_without_trace(response):
    """The refusal body minus `trace_id`, which is per-REQUEST by design.

    HR-1 asks for two refusals to be indistinguishable to a CALLER; the trace
    id is the one field that legitimately differs between two requests and is
    what a support engineer correlates on. Comparing it would assert the
    opposite of what the rule wants.
    """
    return {key: value for key, value in response.data.items() if key != "trace_id"}


def an_actor_user(tenant, role="billing_clerk"):
    """A FakeUser carrying a REAL `users` row id — `bill_runs.run_by` and
    `bill_run_decisions.decided_by` are FKs into identity (B2 §2), so a
    synthetic uuid would break the reviewed cross-module FK set."""
    actor = staff_actor(tenant, role, f"{role}@run-api.test")
    return FakeUser(user_id=actor.id)


# ══════════════════════════════════════════════════════════════════════════
# The routes exist — hard-won law 2, at the routing layer
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_001_tc1__the_run_routes_are_actually_mounted(brazos):
    """`apps/billing/api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it, and S31 shipped against exactly that gap.
    Resolved through the REAL root URLconf so a lost include goes red here."""
    from django.urls import resolve

    run_id = uuid.uuid4()
    assert resolve("/api/brazosbend/billing/runs").func is billing_api.bill_runs
    assert (
        resolve(f"/api/brazosbend/billing/runs/{run_id}/findings").func is billing_api.run_findings
    )
    assert (
        resolve(f"/api/brazosbend/billing/runs/{run_id}/exceptions").func
        is billing_api.run_exceptions
    )
    assert (
        resolve(f"/api/brazosbend/billing/runs/{run_id}/exceptions/x-y/resolve").func
        is billing_api.run_exception_resolve
    )


def test_us_bil_001_tc1__the_routes_are_reachable_through_the_whole_stack(brazos):
    """The other half of "mounted": a real HTTP request through the real
    middleware, authentication and permission class ARRIVES at the view.

    401 AUTH-001 means the route exists and asked for a session. 404 means
    there is no route — which is what all four answered before this lane, and
    what the wizard's panels were reporting from `runRouteAbsent`.
    """
    from django.test import Client

    run_id = uuid.uuid4()
    paths = (
        (f"/api/{brazos.subdomain}/billing/runs", "post"),
        (f"/api/{brazos.subdomain}/billing/runs/{run_id}/findings", "get"),
        (f"/api/{brazos.subdomain}/billing/runs/{run_id}/exceptions", "get"),
        # The case id the wizard puts in the path is the decision's natural key
        # (case + account + service), `encodeURIComponent`d by the client.
        (
            f"/api/{brazos.subdomain}/billing/runs/{run_id}/exceptions/"
            f"missing_read%7C{uuid.uuid4()}%7C/resolve",
            "post",
        ),
    )
    for path, method in paths:
        response = getattr(Client(), method)(path)
        assert response.status_code == 401, (
            f"{path} answered {response.status_code}: a 404 here means the route "
            "is still not reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-001 — POST /billing/runs
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_001_tc1__creating_a_run_answers_the_shape_billrunidof_tolerates(brazos, dana):
    """11b marks `POST /billing/runs` STALE — A11 promised the run id inline,
    B12 r1 requires 202 + job_id for every ASYNC operation. This one is not
    async: creating the row is a single insert and there is no job runner on
    this deployment (TD-17), so it answers 201 with the id, and `job_id` is
    served NULL under its contracted name rather than invented.

    `billRunIdOf()` reads `id` ?? `run_id` and refuses to guess when neither
    arrives; `id` is served and `run_id` deliberately is not — two names for one
    value is the drift DEF-014 is made of.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        response = created_run(brazos, actor_user, cycle)

    assert response.status_code == 201
    # `warnings` joined on 2026-09-30 (plan A1): the Scope step's warnings.
    assert set(response.data) == {"id", "job_id", "status", "warnings"}
    assert response.data["status"] == "draft"  # BR-BIL-050: status IS the phase
    assert response.data["job_id"] is None
    with tenant_ctx(brazos):
        row = billing_models.BillRun.objects.get(pk=response.data["id"])
    assert row.period_start == PERIOD_START and row.period_end == PERIOD_END
    # ⚠ AMENDED 2026-09-30 (plan B3): the services filter is removed, so a new
    # run records NO service scope — it is the whole cycle.
    assert row.scope_services is None
    assert str(row.run_by_id) == str(actor_user.id)


def test_us_bil_001_tc2__an_identical_run_is_refused_with_who_when_and_a_link(brazos, dana):
    """BR-BIL-005, the whole rule: the second attempt is refused, it names who
    ran the original and when, it carries the original's id so the screen can
    link it, and NO second row is written."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        first = created_run(brazos, actor_user, cycle)
        second = created_run(brazos, an_actor_user(brazos, "system_admin"), cycle)
        rows = billing_models.BillRun.objects.filter(cycle=cycle).count()

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.data["code"] == errors.BIZ_IDEMPOTENT
    assert second.data["br_ref"] == "BR-BIL-005"
    params = second.data["params"]
    assert params["run_id"] == first.data["id"]
    assert params["ran_by"] == str(actor_user.id)
    assert params["ran_at"].startswith("20")
    assert rows == 1, "the refusal must not leave a second bill_runs row"


def test_us_bil_001_tc3__a_different_period_is_a_new_run(brazos, dana):
    """TC-3: same cycle, different period ⇒ a different key ⇒ a new run."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        first = created_run(brazos, actor_user, cycle)
        second = created_run(
            brazos,
            actor_user,
            cycle,
            period_start="2026-07-01",
            period_end="2026-07-31",
            # AMENDED 2026-09-30 (BR-BIL-1050): a bill date before the period
            # ends is refused, so July's run carries a bill date after July.
            bill_date="2026-08-01",
        )

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.data["id"] != second.data["id"]


def test_us_bil_001_tc5__a_backwards_period_and_an_unknown_cycle_write_no_row(brazos, dana):
    """TC-5, both halves. A period that ends before it begins is refused —
    every proration in B4.3 divides by that window. A cycle id from another
    tenant, an unknown one and a malformed one are ONE answer (HR-1): the body
    is identical, so existence cannot be probed."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
    backwards = created_run(
        brazos, actor_user, cycle, period_start="2026-06-30", period_end="2026-06-01"
    )
    unknown = created_run(brazos, actor_user, cycle, cycle_id=str(uuid.uuid4()))
    malformed = created_run(brazos, actor_user, cycle, cycle_id="not-a-uuid")
    with tenant_ctx(brazos):
        rows = billing_models.BillRun.objects.count()

    assert backwards.status_code == 422
    assert backwards.data["code"] == errors.BIZ_COMPLETENESS
    # ⚠ AMENDED 2026-09-30 (plan A1): every Scope refusal comes back at once, so
    # an unknown cycle is a FIELD refusal in a 422 rather than a bare 404. HR-1
    # still holds — unknown and malformed are one identical body, below.
    assert unknown.status_code == 422
    assert malformed.status_code == 422
    assert [item["reason"] for item in unknown.data["field_errors"]] == ["cycle_unknown"]
    assert envelope_without_trace(unknown) == envelope_without_trace(
        malformed
    ), "HR-1: unknown and malformed are one answer"
    assert rows == 0


def test_us_bil_001__an_executive_may_read_the_run_but_never_start_one(brazos, dana):
    """A4 `reads_billing_runs`: system_admin Full · billing_clerk Full ·
    executive VIEW. BR-SHL-025 is server-enforced, not a disabled button."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        started = created_run(brazos, actor_user, cycle)
        refused = api_call(
            billing_api.bill_runs,
            "post",
            user=actor_user,
            role="executive",
            tenant=brazos,
            data={
                "cycle_id": str(cycle.id),
                "period_start": "2026-08-01",
                "period_end": "2026-08-31",
                "bill_date": "2026-09-01",
                "scope_services": ["electric"],
            },
        )
        readable = findings_of(brazos, started.data["id"], role="executive")

    assert refused.status_code == 403
    assert readable.status_code == 200


def test_us_bil_001__the_idempotency_key_is_the_cycle_and_the_period(brazos, dana):
    """🔒 The key MECHANICS (Eng-Lead, CLAUDE.md rule 6), asserted so a change
    of shape goes red rather than silently unlocking a double run.

    The rule is signed: key = (tenant, cycle, period), enforced by
    `UNIQUE (tenant_id, idempotency_key)`. The mechanics are the string: the
    cycle's UUID (never its CODE — renaming a cycle must not unlock a re-run)
    and the two ISO dates, in one fixed order.

    ⚠ **AMENDED 2026-09-14 (`DEF-BIL-5283`) — THE SECOND ASSERTION USED TO PIN
    THE DEFECT.** `created_run` posts `scope_services: ["electric"]`, so the row
    it makes is a SCOPED run, and this test asserted the key of an UNSCOPED one.
    That was only true because the scope was missing from the key — the very
    hole that let a Water-only September run consume September and have the
    Sewer run behind it refused as a duplicate. BR-BIL-005 is signed on this
    (*"key = parent key + scope"*), so the scoped row now keys with its scope.
    **The FIRST assertion is unchanged and is the compatibility guarantee**: a
    run with no narrowing keys exactly as every run already stored does.

    ⚠ **AMENDED AGAIN 2026-09-30 (bulk bill run plan B3).** The PO removed the
    services filter, so `created_run` sends none and a new run's key has no
    `|scope|` segment — the second assertion is the unnarrowed shape again,
    now because there is no narrowing rather than because the key missed one.
    """
    cycle_id = uuid.UUID("018f6f6a-0000-7000-8000-000000000001")
    assert (
        idempotency.bill_run_key(
            cycle_id=cycle_id, period_start=PERIOD_START, period_end=PERIOD_END
        )
        == "018f6f6a-0000-7000-8000-000000000001|2026-06-01|2026-06-30"
    )
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        response = created_run(brazos, an_actor_user(brazos), cycle)
        row = billing_models.BillRun.objects.get(pk=response.data["id"])
    assert row.idempotency_key == f"{cycle.id}|2026-06-01|2026-06-30"


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-002 — GET /billing/runs/{id}/findings
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_002__the_findings_mirror_preparedrun_field_for_field(brazos, dana):
    """`runs.PreparedRun` and `contracts.AccountBillingData` / `ServiceReading`,
    carried over in their own names. Every key here is one the shipped
    `BillRunFindings` type declares — asserted exactly, so a rename on either
    side is a red test rather than an empty tab."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        run = created_run(brazos, an_actor_user(brazos), cycle)
        response = findings_of(brazos, run.data["id"])

    assert response.status_code == 200
    assert set(response.data) == {
        "cycle_id",
        "period_start",
        "period_end",
        "service_date",
        "cycle_days",
        "scope_services",
        "account_count",
        "ready",
        "blocked",
        "decisions",
        # `CR-056` task 20 / `BR-BIL-1025` — the FOURTH list: accounts the run
        # examined and found nothing to charge for. Added to the envelope on
        # 2026-09-01 and added HERE in the same commit, because this assertion
        # is the contract: a key that appears on the wire and not in this set is
        # a key the shipped `BillRunFindings` type does not declare.
        "silent",
    }
    assert response.data["period_start"] == "2026-06-01"
    assert response.data["period_end"] == "2026-06-30"
    # BR-RAT-007 / BR-BIL-024: the pricing pivot is the run's bill date — the
    # clerk's typed one here — and no clock is read to find it (BR-TEN-043).
    assert response.data["service_date"] == BILL_DATE.isoformat()
    assert response.data["cycle_days"] == 30
    # ⚠ AMENDED 2026-09-30 (plan B3): a new run carries no service scope.
    assert response.data["scope_services"] is None
    assert response.data["account_count"] == 1

    ready = response.data["ready"][0]
    assert set(ready) == {
        "account_id",
        "account_no",
        "behavior_class",
        "currency",
        "rate_plan_id",
        "rate_plan_name",
        "rate_plan_version",
        "service_days",
        "cycle_days",
        "readings",
    }
    assert ready["account_no"] == "ACC-1042"
    assert ready["behavior_class"] == "billable"
    reading = ready["readings"][0]
    assert set(reading) == {
        "service_code",
        "service_id",
        "consumption",
        "estimated",
        "absent_reason",
    }
    # CLAUDE.md rule 3: a consumption is {amount, unit}, never a bare number.
    assert reading["consumption"] == {"amount": "412.000000", "unit": "kWh"}
    assert reading["estimated"] is False


def test_us_bil_002__every_finding_carries_the_stage_the_server_computed(brazos, dana):
    """BR-BIL-040 — a finding is surfaced in the tab that owns its STAGE's
    inputs, and the reason→stage map is the SERVER's (`runs.STAGE_BY_REASON`).

    Until this landed, `AccountProblem` carried no stage where `runs.Break`
    does, so S31.2 kept a SECOND copy of that map (`FINDING_TAB_BY_REASON`)
    which would drift the day a reason moved. The frontend deleted its copy
    when this key started arriving.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        # A second unit on the cycle with NO plan ever assigned: stage 1 cannot
        # resolve its subscription, which is the Plans tab's own stage.
        an_account(brazos, an_unplanned_unit(brazos, dana, cycle)["id"], "ACC-1455")
        actor_user = an_actor_user(brazos)
    run = created_run(brazos, actor_user, cycle)
    response = findings_of(brazos, run.data["id"])

    problem = response.data["blocked"][0]
    assert set(problem) == {
        "reason",
        "detail",
        "account_id",
        "account_no",
        "unit_id",
        "service_code",
        "stage",
    }
    assert problem["reason"] == "unit_has_no_plan"
    assert problem["stage"] == "resolve-subscription"
    assert billing_runs.STAGE_BY_REASON["unit_has_no_plan"] == "resolve-subscription"


def test_us_bil_002__a_missing_read_is_a_decision_and_names_its_stage(brazos, dana):
    """BR-BIL-015: a service with no usable read leaves the run as a DECISION —
    estimate, hold, or bill without it — and never as a zero. Its stage is
    measure-consumption, which is what puts it on the Reads tab.

    ⚠ AMENDED 2026-10-01 (`DEF-BIL-8671`, red since `e998f92b1`, 2026-09-01).
    This case and the four US-BIL-003 cases below built a meter that had NEVER
    been read. Since R3 + R4 went live (PO: *"Can you wire them in now - R3 and
    R4"*) such a meter has no multiplier anywhere — metering answers it from the
    newest read — and an absent factor is never 1 (BR-MET-056), so the account
    is held before any decision is raised. Every assertion is unchanged; the
    world is now the one this rule is about: a meter read in May and not in
    June. See `a_billed_unit(read_last_month=...)` for the never-read case.
    """
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0003", label="Unit C", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        an_account(brazos, unit["id"], "ACC-1201")
        run = created_run(brazos, an_actor_user(brazos), cycle)
        response = findings_of(brazos, run.data["id"])

    decisions = response.data["decisions"]
    assert [row["reason"] for row in decisions] == ["missing_read"]
    assert decisions[0]["service_code"] == "electric"
    assert decisions[0]["stage"] == "measure-consumption"


def test_us_bil_002__no_bill_date_anywhere_refuses_instead_of_guessing_one(brazos, dana):
    """BR-TEN-043 / G6: there is no clock in this money path and the period's
    end is not a bill date. A run that cannot resolve a bill date cannot be
    priced (BR-RAT-007), so the pass REFUSES and names the missing datum.

    AMENDED 2026-08-11 by the PO's OQ-122 ruling (BR-BIL-070). This case used to
    read *"a CYCLE with no bill date refuses"* and that is no longer the whole
    truth: the clerk's typed bill date is stored on the run and is what the run
    prices on, so a dateless cycle refuses only when NOBODY TYPED ONE EITHER.
    Both halves are asserted, because the old single assertion would now pass
    for the wrong reason — the helper posts a bill date by default, so the
    refusal it was watching for had quietly become impossible to reach.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana, bill_date=None)
        actor_user = an_actor_user(brazos)
        # Neither date: the cycle has none and the clerk typed none.
        # ⚠ AMENDED 2026-09-30 (BR-BIL-1050, row 16 of the bulk run changes):
        # this refusal MOVED FORWARD from Check to Scope — the run is not
        # created at all, and the refusal sits on the bill-date field.
        response = created_run(brazos, actor_user, cycle, bill_date=None)

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert [e["reason"] for e in response.data["field_errors"]] == ["bill_date_needed"]
    assert response.data["field_errors"][0]["field"] == "bill_date"

    # A TYPED date is enough on its own — the cycle never gains one and the run
    # prices anyway (BR-BIL-070: a typed date is an argument, which is exactly
    # what the event-time law asks for).
    with tenant_ctx(brazos):
        billing_models.BillRun.objects.all().delete()
        typed = created_run(brazos, actor_user, cycle, bill_date="2026-08-03")
        priced = findings_of(brazos, typed.data["id"])

    assert priced.status_code == 200
    assert priced.data["service_date"] == "2026-08-03"


def test_us_bil_002__another_tenants_run_reads_as_absent(brazos, lonestar, dana):
    """HR-1 / BR-TEN-003: an unknown run and another tenant's run are ONE
    answer on every route that takes a run id."""
    with tenant_ctx(brazos):
        cycle, _plan, _account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
    run_id = created_run(brazos, actor_user, cycle).data["id"]

    cross = findings_of(lonestar, run_id)
    unknown = findings_of(lonestar, uuid.uuid4())
    cross_cases = exceptions_of(lonestar, run_id)

    assert cross.status_code == 404
    assert unknown.status_code == 404
    assert envelope_without_trace(cross) == envelope_without_trace(unknown)
    assert cross_cases.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# US-BIL-003 — GET /billing/runs/{id}/exceptions + POST .../resolve
# ══════════════════════════════════════════════════════════════════════════
def test_us_bil_003__the_case_rows_mirror_the_shipped_exception_type(brazos, dana):
    """`BillRunExceptionRow` field for field, and the four money/quantity
    members NULL: `prepare_run` returns no amounts at all, so a figure here
    would be invented. `totals` is empty for the same reason — the bulk dialog
    then shows the count and says the total is not served."""
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0004", label="Unit D", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        account = an_account(brazos, unit["id"], "ACC-1201")
        run = created_run(brazos, an_actor_user(brazos), cycle)
        response = exceptions_of(brazos, run.data["id"])

    assert response.status_code == 200
    # ⚠ AMENDED 2026-08-26 (CR-038 W8). This tripwire is the CONTRACT between
    # this envelope and `BillRunExceptionRow` in 07-frontend/src/api/
    # endpoints.ts, and it went RED on the W8 declaration exactly as it should
    # have — verbatim `AssertionError: assert {'analysis_ga...ws', 'totals'} ==
    # {'counts', 'rows', 'totals'}`. Three ADDITIVE members joined, and each is
    # asserted below on THIS classic row so "additive" is proved rather than
    # asserted: `analysis_gaps` (seams the read analysis could not reach — "no
    # rows" and "could not look" are different facts), `suggested` (the
    # server's rule-grounded chip, null where no signed rule points) and
    # `facts` (the stored figures a read-analysis table draws as columns).
    assert set(response.data) == {"rows", "counts", "totals", "analysis_gaps"}
    row = response.data["rows"][0]
    assert set(row) == {
        "id",
        "case",
        "account_id",
        "account_no",
        "customer_name",
        "service_code",
        "detail",
        "choices",
        "amount",
        "currency",
        "quantity",
        "unit",
        "chosen",
        "suggested",
        "facts",
        # ⚠ AMENDED 2026-10-01 (`DEF-BIL-8671`). Three more ADDITIVE members,
        # each already declared on `BillRunExceptionRow` in endpoints.ts: the
        # recorded decision's figure and its unit (`DEF-2857`, `098405729`,
        # 2026-08-31 — served together or not at all) and the estimate window's
        # `basis` (`DEF-2859`, `2b2b67af5`, the same day). This tripwire went red
        # on the first and nobody read it, because the four cases below were
        # red beside it from 2026-09-01. Each is asserted below on this row.
        "chosen_quantity",
        "chosen_unit",
        "basis",
    }
    assert row["case"] == "missing_read"
    assert row["account_id"] == str(account.id)
    assert row["service_code"] == "electric"
    # BR-BIL-015's three dispositions, from the SERVER's own vocabulary.
    assert row["choices"] == ["estimate", "hold", "bill_without_service"]
    assert row["chosen"] is None, "BR-BIL-015: nothing arrives pre-decided"
    # Nothing decided, so no decided figure; served together or not at all.
    assert (row["chosen_quantity"], row["chosen_unit"]) == (None, None)
    # Metering reports no usage history for this new account (and no gap —
    # `analysis_gaps` is empty below), so no starting figure: null, never a
    # guessed one (`DEF-2859`).
    assert row["basis"] is None
    assert (row["amount"], row["currency"], row["quantity"], row["unit"]) == (
        None,
        None,
        None,
        None,
    )
    assert row["customer_name"] is None  # customers publishes no read taking an id
    assert response.data["counts"] == {"missing_read": 1}
    assert response.data["totals"] == {}
    # A CLASSIC case is untouched by W8: no suggestion, no fact columns — and
    # the analysis reached every seam it asked, so it names no gap.
    assert (row["suggested"], row["facts"]) == (None, None)
    assert response.data["analysis_gaps"] == []


def test_us_bil_003__a_recorded_choice_comes_back_as_chosen(brazos, dana):
    """The decision trail is what the screen renders: a case that has been
    decided says so, and the row that says it is the one nothing superseded."""
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0008", label="Unit H", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        account = an_account(brazos, unit["id"], "ACC-1201")
        actor_user = an_actor_user(brazos)
    run = created_run(brazos, actor_user, cycle)
    before = exceptions_of(brazos, run.data["id"]).data["rows"]
    # Recorded against the row's OWN key — case + account + service. That is
    # what `current_decision` resolves on, so a decision filed under a
    # different service is a different decision and must not show here.
    _case, _account_id, service_id = billing_decisions.split_case_row_id(before[0]["id"])
    with tenant_ctx(brazos):
        bill_run = billing_models.BillRun.objects.get(pk=run.data["id"])
        billing_decisions.record_decision(
            bill_run=bill_run,
            account_id=str(account.id),
            case="missing_read",
            choice="bill_without_service",
            service_id=service_id,
        )
    after = exceptions_of(brazos, run.data["id"]).data["rows"]

    assert [row["chosen"] for row in before] == [None]
    assert [row["chosen"] for row in after] == ["bill_without_service"]


def test_us_bil_003__resolving_one_case_records_one_decision(brazos, dana):
    """US-BIL-003: the choice is RECORDED, with who made it — *"all the
    decisions are made on screen and recorded"*."""
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0005", label="Unit E", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        account = an_account(brazos, unit["id"], "ACC-1201")
        actor_user = an_actor_user(brazos)
    run = created_run(brazos, actor_user, cycle)
    case_row = exceptions_of(brazos, run.data["id"]).data["rows"][0]
    response = resolve_case(
        brazos,
        actor_user,
        run.data["id"],
        case_row["id"],
        {"choice": "hold", "reason": "meter unreachable"},
    )
    with tenant_ctx(brazos):
        rows = list(billing_models.BillRunDecision.objects.filter(account_id=account.id))
    after = exceptions_of(brazos, run.data["id"]).data["rows"][0]

    assert response.status_code == 201
    # ⚠ AMENDED 2026-10-01 (`DEF-BIL-8671`): `repriced` joined on 2026-09-14
    # (`7340d5830`, DEF-BIL-5271 — *a decision reaches the money*): what the
    # decision did to the bills, on the response that records it. Additive;
    # this assertion was hidden behind the never-read fixture's red.
    assert set(response.data) == {"bulk_action_id", "decision_ids", "repriced"}
    # Decided at step 3, before any draft exists, so nothing is re-priced —
    # `api.resolve` asks `runs.has_drafts_for` and re-prices only then.
    assert response.data["repriced"] == {
        "accounts": 0,
        "drafts": 0,
        "background": False,
        "job_id": None,
    }
    assert response.data["bulk_action_id"] is None
    assert len(rows) == 1
    assert (rows[0].case, rows[0].choice, rows[0].reason) == (
        "missing_read",
        "hold",
        "meter unreachable",
    )
    assert str(rows[0].decided_by_id) == str(actor_user.id)
    assert after["chosen"] == "hold"


def test_us_bil_003__a_bulk_choice_is_n_rows_sharing_one_bulk_action_id(brazos, dana):
    """BR-BIL-060 — *"it is impossible for user to do this manually account by
    account"*. Each account still gets its OWN row (its bill changed, so its
    trail must say so); the shared id answers the different question, "was this
    one of a thousand?"."""
    with tenant_ctx(brazos):
        cycle = a_dated_cycle(brazos)
        plan = a_priced_plan(brazos)
        first = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0006", label="Unit F", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        second = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-0007", label="Unit G", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: a meter that missed THIS read
        )
        an_account(brazos, first["id"], "ACC-2001")
        an_account(brazos, second["id"], "ACC-2002")
        actor_user = an_actor_user(brazos)
    run = created_run(brazos, actor_user, cycle)
    rows = exceptions_of(brazos, run.data["id"]).data["rows"]
    ids = [row["id"] for row in rows]
    response = resolve_case(
        brazos,
        actor_user,
        run.data["id"],
        ids[0],
        {"choice": "hold", "reason": "route not walked", "case_ids": ids},
    )
    with tenant_ctx(brazos):
        written = list(billing_models.BillRunDecision.objects.all())

    assert response.status_code == 201
    assert len(ids) == 2
    assert len(written) == 2
    assert len({str(row.bulk_action_id) for row in written}) == 1
    assert written[0].bulk_action_id is not None
    assert response.data["bulk_action_id"] == str(written[0].bulk_action_id)


def test_us_bil_003_tc10__a_bulk_late_fee_waiver_is_refused_by_the_server(brazos, dana):
    """BR-BIL-003 + BR-BIL-060, the one asymmetry the PO made deliberate: bulk
    APPLY is allowed, bulk WAIVE is not. The screen hides the control; the
    server refuses it, because a hidden control is not a rule."""
    with tenant_ctx(brazos):
        cycle, _plan, account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        case_id = billing_decisions.case_row_id("late_fee", str(account.id), None)
    run = created_run(brazos, actor_user, cycle)
    response = resolve_case(
        brazos,
        actor_user,
        run.data["id"],
        case_id,
        {"choice": "waive", "reason": "first time", "case_ids": [case_id, case_id]},
    )
    with tenant_ctx(brazos):
        written = billing_models.BillRunDecision.objects.count()

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["br_ref"] == "BR-BIL-003"
    assert written == 0


def test_us_bil_003__an_unsupported_case_refuses_by_name_instead_of_half_recording(brazos, dana):
    """A case whose INPUTS do not exist refuses by name (`UNSUPPORTED_CASES`).

    ⚠ **THIS CASE USED `extra_charge` AND WENT RED ON 2026-08-31, CORRECTLY —
    CR-051 task 18 SHIPPED THE INPUT IT WAS WAITING FOR.** Its docstring read
    *"`extra_charge` and `overcharge` have no inputs on this deployment"*, and
    the first half stopped being true: the charge-code reader `extra_charge` was
    refused for has existed since BR-BIL-075 landed on 2026-08-26, so the reply
    is now RECORDED and `apply` holds the account at its money boundary instead.

    **Re-pointed at `overcharge` rather than deleted**, because the guarantee
    under test is not about either case — it is that a case the server cannot
    apply refuses BY NAME rather than half-recording a decision whose effect
    nothing can carry out. `overcharge` still needs BR-BIL-029's trailing
    average, which no module computes.

    **And the other direction is asserted too**, because a case that only proved
    the refusal would pass on a lane that emptied `UNSUPPORTED_CASES` and built
    nothing: the same route, the same shape, `extra_charge`, must now answer 201
    and leave a row.
    """
    with tenant_ctx(brazos):
        cycle, _plan, account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        refused_id = billing_decisions.case_row_id("overcharge", str(account.id), None)
        taken_id = billing_decisions.case_row_id("extra_charge", str(account.id), None)
    run = created_run(brazos, actor_user, cycle)
    response = resolve_case(brazos, actor_user, run.data["id"], refused_id, {"choice": "hold"})
    with tenant_ctx(brazos):
        written = billing_models.BillRunDecision.objects.count()

    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert written == 0

    # CR-051 task 18 — the same door, a case that IS supported now.
    taken = resolve_case(brazos, actor_user, run.data["id"], taken_id, {"choice": "apply"})
    with tenant_ctx(brazos):
        stored = billing_models.BillRunDecision.objects.filter(case="extra_charge").count()

    assert taken.status_code == 201, taken.data
    assert stored == 1, "the clerk's reply to *Charges to add* still went nowhere"


def test_us_bil_003__an_executive_may_read_the_cases_but_never_decide_one(brazos, dana):
    """A4 again, on the write half of S31.3."""
    with tenant_ctx(brazos):
        cycle, _plan, account = a_run_world(brazos, dana)
        actor_user = an_actor_user(brazos)
        case_id = billing_decisions.case_row_id("base_only_billing", str(account.id), None)
    run = created_run(brazos, actor_user, cycle)
    refused = resolve_case(
        brazos, actor_user, run.data["id"], case_id, {"choice": "include"}, role="executive"
    )
    with tenant_ctx(brazos):
        written = billing_models.BillRunDecision.objects.count()

    assert refused.status_code == 403
    assert written == 0


# ══════════════════════════════════════════════════════════════════════════
# The database half (G5) — RLS, under a role row-level security applies to
# ══════════════════════════════════════════════════════════════════════════
RUN_TABLES = ("bill_runs", "bill_run_decisions")


def _run_tenant(payload, *, service="electric"):
    """A provisioned tenant with one bill run and one recorded decision.

    Built through `provisioned_tenant` rather than the function-scoped tenant
    fixtures because the session-scoped probe-role fixture cannot be composed
    with them — the same shape the S30 read lane settled on.

    `service` is a parameter for the same reason it is there: the isolation
    tenant (Lone Star Ridge) has only WATER enabled, and BR-TEN-026 refuses a
    service point on a service the tenant never turned on. The two tenants are
    deliberately not identical — which is exactly what makes the RLS probe a
    probe rather than a mirror.
    """
    tenant, _ = provisioned_tenant(payload)
    actor = staff_actor(tenant, "system_admin", f"admin@{tenant.id}.test")
    with live_tenant_context(tenant.id):
        run = billing_models.BillRun.objects.create(
            tenant=tenant,
            cycle=a_dated_cycle(tenant, code=f"C-{str(tenant.id)[:4]}"),
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key=f"{uuid.uuid4()}|2026-06-01|2026-06-30",
        )
        premises = make_premises(  # noqa: F405
            actor, address_line="1 Bluestem Ln", services_available=[service]
        )
        unit = make_unit(actor, premises["id"], label="Unit A", services=[service])  # noqa: F405
        account = an_account(tenant, unit["id"], f"ACC-{str(tenant.id)[:4]}")
        billing_models.BillRunDecision.objects.create(
            tenant=tenant,
            bill_run=run,
            account=account,
            case="base_only_billing",
            choice="include",
        )
    return tenant, run


@pytest.mark.isolation
@requires_postgres
def test_us_bil_001_tc6__a_run_never_crosses_a_tenant_boundary(rls):  # noqa: F811
    """US-BIL-001 TC-6 at the DATABASE, with the app-layer filter deliberately
    out of the path, under a NON-SUPERUSER probe role so the policies are
    genuinely consulted rather than bypassed."""
    from tests.isolation_helpers import assert_no_foreign_rows_anywhere, assert_rls_scoped

    brazos_tenant, bb_run = _run_tenant(brazosbend_payload())
    lsr_tenant, lsr_run = _run_tenant(lonestarridge_payload(), service="water")

    assert_rls_scoped(
        rls, "bill_runs", owner=brazos_tenant, intruder=lsr_tenant, owner_ids={str(bb_run.id)}
    )
    assert_rls_scoped(rls, "bill_run_decisions", owner=brazos_tenant, intruder=lsr_tenant)
    with live_tenant_context(lsr_tenant.id):
        assert rls.count("bill_runs", "id = %s", [str(bb_run.id)]) == 0
        assert rls.ids("bill_runs") == {str(lsr_run.id)}
    assert_no_foreign_rows_anywhere(rls, lsr_tenant, RUN_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_bil_001_tc6__the_run_reads_are_denied_outright_with_no_tenant_context(
    rls,
):  # noqa: F811
    """CLAUDE.md hard rule 1, both halves: the DATABASE refuses with
    `app.tenant_id` unset, and the read layer refuses before a query is built —
    so an endpoint called outside a tenant context cannot lean on RLS being the
    only thing between one utility's run and another's."""
    from apps.billing import selectors as billing_selectors

    from tests.isolation_helpers import assert_denied_without_context

    _run_tenant(brazosbend_payload())
    assert_denied_without_context(rls, *RUN_TABLES)
    with pytest.raises(errors.AuthError) as excinfo:
        billing_selectors.run_or_404(uuid.uuid4())
    assert excinfo.value.code == errors.AUTH_TENANT_UNRESOLVABLE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@990725e (sha1[:7] of the three sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md — US-BIL-001..003 — · 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.8+§2.8b; co-packets US-BIL-002/US-BIL-003, same three sources — matches apps/billing/api.py)
# generated: 2026-08-11 by story-coder (W3 billing run-API lane — the four S31 routes the wizard was calling against a 404)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S31's wizard already ships and already calls all four paths) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the whole file was run against the unbuilt endpoints; verbatim failures in the lane report (AttributeError: module 'apps.billing.api' has no attribute 'bill_runs' · django.urls.exceptions.Resolver404 on /api/brazosbend/billing/runs)
# exceptions: the deviations this suite pins are listed in apps/billing/api.py's trailer — chiefly `job_id` served null, `customer_name` null on every case row, `totals` empty, and the findings pass refusing a cycle with no bill date
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
