# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-039 (EP-WRK-05) TC-1..TC-12 — the five flows raise their
#           jobs.  US-WRK-017 (the shared proposal engine) · US-WRK-006.
# Rules:    BR-WRK-055 (a flow completes whether or not the visit could be
#           raised; Customers writes nothing to `work_orders`) ·
#           BR-WRK-024 (every order carries its source) · BR-WRK-006 (an order
#           stands on an anchor) · BR-WRK-016 (the offer is the utility's own
#           PUBLISHED templates) · B19 §12.3 (a request closes when the job it
#           created finishes) · CLAUDE.md hard rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""US-WRK-039 — the five flows raise their jobs, and none of them waits.

⚠ **THE CASE THIS FILE EXISTS FOR IS `test_def_wrk_3725_...`, AND IT WAS PROVED
RED FIRST.** The wave plan put the move-out's field-visit control on wizard step
4. Step 4 is the SHORTFALL step and renders greyed and *skipped* whenever the
account settles — the common case — so a control placed there is invisible on
the very move-outs that need it. The regression case here asserts the control's
host by STEP ID rather than by ordinal, on a move-out that settles cleanly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.customers import disconnects, models as customers_models, moves
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work import from_flows
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

REPO = Path(__file__).resolve().parents[2]

MOVE_OUT_DAY = "2026-03-28"


# ── helpers ─────────────────────────────────────────────────────────────────
def _plan(tenant, name="Residential Standard", service_code="electric"):
    """A PUBLISHED rate plan the unit can be put on — `BR-MET-040` requires one
    at activation, so an account cannot be made ACTIVE without it. Lifted from
    `test_us_cus_004_005_move_in_out.py`, whose docstring records why the plan
    is created directly: what matters here is only that `units.rate_plan_id` is
    non-null."""
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit_with_plan(actor, tenant, *, label="Unit A", address_line="221 Oak Ave"):
    premises = make_premises(actor, address_line=address_line)
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    for code in ("electric", "water"):
        metering_services.ensure_service_point(unit["id"], code)
    return premises, unit


def _occupant(actor, unit, *, name="Sarah Miller", phone="+1 (281) 555-0155"):
    """An ACTIVE account holding the unit — the state a move-out starts from."""
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-01-05",
            "contact": {"full_name": name},
            "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
        },
    )


def _published_template(actor, *, name, service="electric", sequence=0):
    """One of the utility's OWN templates, authored and published.

    ⚠ **`sequence=0` IS THE POINT FOR FOUR OF THE FIVE FLOWS.** A template with
    a place in the connection sequence is a job that BUILDS a service, and New
    Connect and an approved service request propose those. A final read, a
    turn-on or a changeover read is work on a service that already exists, and
    that is what `sequence` 0 means here.
    """
    header = w6.create_work_order_template(
        actor, {"name": name, "service": service, "sequence": sequence}
    )
    w6.publish_work_order_template(actor, header["id"])
    return header


def _move_out(actor, account_id, *, template_ids=None):
    payload = {"moved_out_on": MOVE_OUT_DAY}
    if template_ids is not None:
        payload["field_visit"] = {"template_ids": template_ids}
    return customers_services.move_out(actor, account_id, payload)


# ── TC-1 · a move-out raises the final read, on the right anchor ────────────
@pytest.mark.django_db
def test_tc1_a_move_out_raises_the_final_read_on_the_account_it_closes(dana, brazos):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _published_template(dana, name="Final read & deactivate")

        result = _move_out(dana, account["id"], template_ids=[template["id"]])

        assert result["work_orders"], "the ticked job was not raised"
        order = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"])
        # BR-WRK-006 — the anchor it already had, and no new column.
        assert str(order.account_id) == str(account["id"])
        # BR-WRK-024 — why it exists, and which record asked.
        assert order.source == "move_out"
        assert order.source_ref == result["move_no"]
        assert order.source_ref is not None and order.source_ref.startswith("MVO-")


# ── TC-2 · the flow completes when the raise FAILS, and says so ─────────────
@pytest.mark.django_db
def test_tc2_the_account_still_closes_when_the_raise_fails_and_the_answer_says_so(
    dana, brazos, monkeypatch
):
    """`BR-WRK-055` and judgment 7 — the one case the whole design is shaped
    around. A field module able to block a customer's move-out is the failure
    this posture exists to prevent."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _published_template(dana, name="Final read & deactivate")

        def _explode(*_args, **_kwargs):
            raise RuntimeError("work is down")

        monkeypatch.setattr(customers_services.seams, "raise_flow_work_orders", _explode)
        result = _move_out(dana, account["id"], template_ids=[template["id"]])

        # The customer's move-out happened.
        assert result["closed_at"] == MOVE_OUT_DAY or result.get("closed_at") is not None
        assert result["work_orders"] == []
        # And the screen is TOLD which of the two things happened.
        codes = [row["code"] for row in result["warnings"]]
        assert "work_orders_not_raised" in codes


# ── TC-3 · judgment 8 · no resolved premises, no job, no row ────────────────
@pytest.mark.django_db
def test_tc3_a_request_with_no_resolved_address_is_refused_and_writes_nothing(dana, brazos):
    with tenant_ctx(brazos):
        request = customers_models.ServiceRequest.objects.create(
            tenant_id=brazos.id, request_no="SR-26-0001", state="approved"
        )
        before = work_tables.WorkOrder.objects.count()

        offer = from_flows.propose("service_request", request.id)
        assert offer["refusal"] is not None
        assert offer["refusal"]["code"] == "flow_has_no_anchor"
        assert offer["proposed"] == []

        with pytest.raises(from_flows.FlowRaiseRefused):
            from_flows.raise_for("service_request", request.id, ["any"], dana)
        assert work_tables.WorkOrder.objects.count() == before, "a row was written by a refused raise"


# ── TC-4 · B19 §12.3, WITHDRAWN 2026-09-19 · no acceptance closes a request ──
@pytest.mark.django_db
def test_tc4_a_request_with_three_jobs_is_never_closed_by_an_acceptance(dana, brazos):
    """`DEF-WRK-6486` — this case asserted B19 §12.3's promise, *"a request
    closes on its own when the job it created finishes"*, on the THIRD of three
    acceptances. The PO withdrew it on 2026-09-19 — *"once requets is approved
    then in move in or new connect we take all those decision"* (BR-WRK-055,
    amended 2026-10-04) — so `complete` is a retired move and
    `close_if_field_work_done` answers a named no-op on EVERY acceptance rather
    than raising across metering's accept path. The tally it would have read
    still counts 3 of 3, which is what the request's own page shows."""
    from apps.customers import service_request_service as srs

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="14 Palm Court")
        request = customers_models.ServiceRequest.objects.create(
            tenant_id=brazos.id,
            request_no="SR-26-0002",
            state="in_fulfilment",
            resolved_premises_id=premises["id"],
        )
        orders = [
            w6.create_work_order(
                dana,
                None,
                {
                    "premises_id": premises["id"],
                    "type": name,
                    "source": "service_request",
                    "source_ref": "SR-26-0002",
                },
            )
            for name in ("Site inspection", "Tap and service line", "Meter set")
        ]

        for index, order in enumerate(orders):
            row = work_tables.WorkOrder.objects.get(pk=order["id"])
            row.state = work_tables.WO_COMPLETED
            row.accepted_at = "2026-03-20T10:00:00+00:00"
            row.save(update_fields=["state", "accepted_at", "updated_at"])
            answer = srs.close_if_field_work_done(dana, "SR-26-0002")
            assert answer == {"closed": False, "reason": "request_completion_retired"}, (
                f"acceptance {index + 1} of {len(orders)}"
            )

        tally = from_flows.acceptance("service_request", "SR-26-0002")
        assert (tally["accepted"], tally["total"]) == (3, 3)
        request.refresh_from_db()
        assert request.state == "in_fulfilment", "nothing moves a request any more"


# ── TC-5 · nothing under apps/customers writes work_orders ──────────────────
def test_tc5_apps_customers_writes_no_work_order_row():
    """`A7`'s boundary from the Customers side, as a grep case beside the gate.

    Two checks, and both are needed: no module may import metering's
    `WorkOrder`, and no file may name `work_orders` in a write. The gate
    (`G102`) is the merge-blocking version of this; the case is here so a lane
    that breaks it sees it in its own suite first.
    """
    offenders = []
    for path in (REPO / "06-backend" / "apps" / "customers").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in (
            r"WorkOrder\.objects\.(create|update|delete|bulk_create|bulk_update)",
            r"INSERT\s+INTO\s+work_orders",
            r"UPDATE\s+work_orders",
            r"DELETE\s+FROM\s+work_orders",
        ):
            if re.search(pattern, text):
                offenders.append(f"{path.name}: {pattern}")
    assert offenders == [], f"apps/customers writes work_orders: {offenders}"


# ── TC-6 · one utility's flows raise nothing on another's ───────────────────
@pytest.mark.django_db
def test_tc6_lone_star_flows_raise_nothing_on_brazos_bend(dana, erin, brazos, lonestar):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
    with tenant_ctx(lonestar):
        # Brazos Bend's account id, read from Lone Star's context. HR-1: it must
        # read as ABSENT (a 404-shaped refusal), never as forbidden — existence
        # must not leak — and it must certainly not raise a job on somebody
        # else's account.
        with pytest.raises(Exception) as caught:
            from_flows.propose("move_out", account["id"])
        assert "403" not in str(caught.value), "a cross-tenant id leaked its existence"
        with pytest.raises(Exception):
            from_flows.raise_for("move_out", account["id"], ["anything"], erin)


# ── TC-7 · the offer is the utility's own PUBLISHED templates ───────────────
@pytest.mark.django_db
def test_tc7_a_move_out_is_offered_work_on_a_service_that_already_exists(dana, brazos):
    """A move-out is not offered *Meter set*, and a request is."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        _published_template(dana, name="Final read & deactivate", sequence=0)
        _published_template(dana, name="Meter set (build)", sequence=2)

        names = [row["name"] for row in from_flows.propose("move_out", account["id"])["proposed"]]
        assert "Final read & deactivate" in names
        assert "Meter set (build)" not in names, "a move-out was offered a job that BUILDS a service"


# ── TC-8 · a draft template is never raised ─────────────────────────────────
@pytest.mark.django_db
def test_tc8_an_unpublished_template_is_refused_by_name(dana, brazos):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        draft = w6.create_work_order_template(
            dana, {"name": "Never published", "service": "electric", "sequence": 0}
        )
        record = moves.record_move(
            kind=moves.KIND_MOVE_OUT, account_id=account["id"], effective_on=MOVE_OUT_DAY
        )
        with pytest.raises(errors.ValidationError):
            from_flows.raise_for("move_out", record["move_record_id"], [draft["id"]], dana)


# ── TC-9 · the five flow tokens, and the one the database refuses ───────────
@pytest.mark.django_db
def test_tc9_the_flow_sources_are_in_the_vocabulary_and_an_unknown_one_is_refused(dana, brazos):
    """`DEF-WRK-6486` — this asserted the vocabulary was exactly FOURTEEN long.
    Siblings have legitimately grown it since (17 on 2026-10-05: the rule
    processes' labels, `disconnect`, `failed_outcome`), so the count was a
    check that had to be edited every time the thing it guards grew. What this
    story needs is that its five flow tokens are PRESENT and that a word
    outside the vocabulary is refused."""
    for token in ("service_request", "move_in", "move_out", "transfer", "reconnect"):
        assert token in work_tables.WORK_ORDER_SOURCES
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="221 Oak Ave")
        with pytest.raises(errors.ValidationError):
            w6.create_work_order(
                dana, None, {"premises_id": premises["id"], "source": "not_a_real_source"}
            )


# ── TC-10 · the anchor CHECK did not move ───────────────────────────────────
def test_tc10_the_anchor_check_still_has_exactly_four_arms():
    """Judgment 4: adding the flow stamp must not turn a four-way CHECK into a
    nine-way one. The alternative was one nullable FK per flow."""
    check = next(
        c
        for c in work_tables.WorkOrder._meta.constraints
        if getattr(c, "name", "") == "ck_work_orders_has_anchor"
    )
    condition = getattr(check, "condition", None) or getattr(check, "check", None)
    # Four `__isnull` arms, ORed: connection · premises · account · asset. The
    # count is on the repr's own spelling (`('x__isnull', False)`), which is what
    # a nine-way CHECK would change.
    assert str(condition).count("__isnull") == 4, str(condition)
    for anchor in ("connection", "premises", "account", "asset"):
        assert f"{anchor}__isnull" in str(condition)


# ── TC-11 · the reconnect books the visit, and says when it did not ─────────
@pytest.mark.django_db
def test_tc11_a_reconnect_with_no_ticked_job_still_answers_visit_not_scheduled():
    """`VISIT_NOT_SCHEDULED` keeps its name, its code and its place — it rides
    the case it was always about, which is a reconnect where no visit was
    booked. What changed is that there is now a lawful way to book one."""
    assert disconnects.VISIT_NOT_SCHEDULED["code"] == "reconnection_visit_not_scheduled"
    assert "2026-09-05" in disconnects.VISIT_NOT_SCHEDULED["detail"]


# ── TC-12 · DEF-WRK-3725 · the control's host is STEP 2 ─────────────────────
def test_def_wrk_3725_the_move_out_field_visit_is_on_step_2_not_step_4():
    """**PROVED RED FIRST, against the plan's own instruction.**

    The wave plan put this panel on `MoveOutWizard` step 4. `MOVE_OUT_STEPS[3]`
    — the SHORTFALL step — carries `conditional: true` and renders greyed and
    *skipped* whenever the account settles, so a control placed there would be
    invisible on the ordinary move-out.

    ⚠ **THE ASSERTION IS BY STEP ID, NEVER BY ORDINAL**, which is
    `DEF-WRK-3725`'s own wider prevention: *"a plan task that names a wizard
    STEP names the step's id from the shared step list, never its ordinal"*. An
    ordinal is what let one document mean two different steps at once.
    """
    wizard = (REPO / "07-frontend" / "src" / "features" / "customers" / "MoveOutWizard.tsx").read_text(
        encoding="utf-8"
    )
    shared = (REPO / "07-frontend" / "src" / "features" / "customers" / "moveShared.tsx").read_text(
        encoding="utf-8"
    )

    # The step the panel is hosted on is `date`, and `date` is NOT conditional.
    date_block = shared[shared.index('id: "date"') : shared.index('id: "settlement"')]
    assert "conditional" not in date_block, "step 2 became conditional — the panel would vanish"
    shortfall_block = shared[shared.index('id: "shortfall"') : shared.index('id: "impact"')]
    assert "conditional: true" in shortfall_block, "the shortfall step stopped being conditional"

    # The panel is rendered by `DateStep`, which is step `date`'s content, and
    # by nothing else.
    assert "<RaiseFieldWork" in wizard, "the field-visit panel is not rendered at all"
    date_step = wizard[wizard.index("function DateStep(props: {") :]
    date_step = date_step[: date_step.index("function SettlementStep")]
    assert "<RaiseFieldWork" in date_step, "the panel is not on step 2 (`date`)"
    shortfall_step = wizard[wizard.index("function ShortfallStep") :] if "function ShortfallStep" in wizard else ""
    assert "<RaiseFieldWork" not in shortfall_step, "the panel is on the SKIPPED step again"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-039 (EP-WRK-05) · 10-execution-plan.md wave P tasks P1–P5
# generated: 2026-09-05 by the CR-070 wave P build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: G78 · G102 · pytest tests/test_us_wrk_039_from_flows.py
# exceptions: the RECONNECT's screen host is not built (no front-end caller for
#   `mark_reconnecting` exists anywhere) — TC-11 asserts the backend constant
#   rather than a control that does not exist (hard-won law 2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
