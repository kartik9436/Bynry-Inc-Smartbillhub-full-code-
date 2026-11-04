# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 task W2-T4
#           (a cycle-less one-time bill takes its due date FROM THE RUN) and
#           the RC-W1 handover: `POST /billing/runs` opens to `due_days`.
#           Screens: S31 step 1 (bill run wizard) · S33 (One-time tab)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7
# Rules:    D8③ — *"③ what due date a cycle-less one-time bill gets - it will
#           be capture at the time of bulk billing - not here"* (closes OQ-241)
#           · D8④ — *"④ its proration denominator … this is not required"*
#           (WITHDRAWN; OQ-242 closes unbuilt) · D9 — the cycle carries the
#           defaults, the run overrides · BR-BIL-024 (due = bill date +
#           due-days) · BR-MET-009 (`due_days ≥ 0`) · CLAUDE.md rule 4
#           (financial immutability — nothing already issued moves)
# ───────────────────────────────────────────────────────
"""RC-W2-T4 — the due date is captured on the RUN, and 0 is a lawful answer.

WHAT WAS BLOCKED, AND WHAT UNBLOCKS IT
--------------------------------------
A one-time bill (interim · first · final · back-bill · penalty) has **no
cycle** — that is the point of it — and BR-BIL-024 derives the due date from
*"the cycle's due-days"*. `cycles.due_days` was the only due-days in the schema,
so `issue.derive_due_date` refused by name and the One-time tab could draft a
bill and never send it. **OQ-241 asked where a cycle-less bill's due-days come
from, and D8③ answers: from the bulk-billing run.**

The column that answers it already exists — `bill_runs.due_days`, RC-W1's D9
override — so W2-T4 is not new schema. It is: the one-time writer accepting the
value, the create endpoint accepting it, and the refusal for a bad one.

⚠ **`is None`, NEVER TRUTHINESS.** `due_days = 0` is a lawful arrangement — due
on the bill date — so a falsy test would silently replace a typed 0 with the
cycle's 21 and give every customer in the run three more weeks than the clerk
chose. Pinned in its own case, both on the cycle run and on the one-time run.

⚠ **D8④ IS A WITHDRAWAL, NOT A RULE.** *"its proration denominator … this is
not required"*, so a one-time bill over a partial window still charges a full
base charge and **no proration rule is built**. What changes is the register:
the stated absence stops citing an open question that is now withdrawn. The
figures in it are unchanged and are asserted here so a later lane cannot quietly
"fix" the arithmetic without a ruling.
"""

from datetime import date

import pytest

from apps.billing import issue as billing_issue
from apps.billing import models as billing_models
from apps.billing import one_time
from apps.billing import runs as billing_runs
from apps.metering import models as metering_models

from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD = (date(2026, 6, 1), date(2026, 6, 30))
BILL_DATE = date(2026, 7, 1)


def _cycle(tenant, code="06-A", *, due_days=21):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # ⚠ OQ-344 (RC-W6): `cycles.bill_date` is dropped (metering 0023) and
        # the surviving default is the bill DAY. The period below ends 30 June,
        # so a bill day of 1 resolves to **1 July** — `BILL_DATE` exactly, and
        # every figure in this file is unchanged.
        bill_day=BILL_DATE.day,
        due_days=due_days,
        start_day=1,
        days_to_complete=3,
        first_run_date=date(2026, 6, 1),
    )


def _one_time_account(tenant, actor, *, account_no, asset_no):
    """One billable account with no cycle in sight — the One-time tab's world.

    The unit is put on a cycle only because `a_billed_unit` stamps the service
    point through one; the RUN below carries no cycle, which is the case D8③
    rules on.
    """
    cycle = _cycle(tenant, code=f"CY-{account_no}")
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(actor, tenant, cycle, plan, asset_no=asset_no, label=asset_no[-2:])
    return an_account(tenant, unit["id"], account_no)


def _door_world(tenant, actor, code):
    """⚠ ADDED 2026-09-30 (bulk bill run plan A1/B4): the door now refuses a
    cycle with no units or no accounts, and requires a run name and a published
    template — so a POST that is meant to SUCCEED needs a cycle with one billed
    account on it, and a body carrying the two required fields."""
    from apps.billing import templates_service

    cycle = _cycle(tenant, code=code)
    unit = a_billed_unit(actor, tenant, cycle, a_priced_plan(tenant), asset_no=f"M-{code}", label=code)
    an_account(tenant, unit["id"], f"A-{code}")
    template = templates_service.tenant_fallback_template()
    if template is None or templates_service.published_version(template) is None:
        templates_service.seed_platform_default(on_date=date(2026, 1, 1))
        template = templates_service.tenant_fallback_template()
    return cycle, {"label": f"June 2026 {code}", "template_id": str(template.pk)}


def _due(run):
    bill_date, due_days = billing_issue._due_terms_for(run)
    return billing_issue.derive_due_date(bill_date, due_days)


# ═══════════════════════════════════════════════════════════════════════════
# D9 · THE RUN MAY OVERRIDE — AND THE DOOR IS NOW OPEN AT THE SERVICE
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t4__an_ordinary_run_falls_due_on_the_cycles_terms(brazos, dana):
    """Worked: cycle 06-A bills 1 July with 21 due-days → **22 July**."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        run = billing_runs.create_run(
            cycle_id=cycle.id, period_start=PERIOD[0], period_end=PERIOD[1]
        )
        assert _due(run) == date(2026, 7, 22)


def test_w2_t4__a_run_that_overrides_falls_due_on_its_own_terms(brazos, dana):
    """Worked: the same cycle, a run created with 14 due-days → **15 July**,
    and the CYCLE still says 21 for the next run."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="06-B")
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            due_days=14,
        )
        assert _due(run) == date(2026, 7, 15)
        cycle.refresh_from_db()
        assert cycle.due_days == 21


def test_w2_t4__zero_due_days_is_lawful_and_is_not_swallowed(brazos, dana):
    """`due_days = 0` means due ON the bill date (BR-MET-009: `due_days ≥ 0`).
    A truthiness test here would hand the customer the cycle's 21 days."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="06-C")
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            due_days=0,
        )
        assert _due(run) == BILL_DATE


# ═══════════════════════════════════════════════════════════════════════════
# THE ENDPOINT — the RC-W1 handover: `POST /billing/runs` accepts due_days
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t4__the_create_endpoint_stores_the_typed_due_days(brazos, dana):
    from apps.billing import api as billing_api

    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        cycle, required = _door_world(brazos, dana, "06-D")
    response = api_call(
        billing_api.bill_runs,
        "post",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        data={
            **required,
            "cycle_id": str(cycle.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "bill_date": "2026-07-01",
            "due_days": 14,
        },
    )
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
        assert run.due_days == 14
        assert _due(run) == date(2026, 7, 15)


def test_w2_t4__an_omitted_due_days_records_that_nobody_typed_one(brazos, dana):
    from apps.billing import api as billing_api

    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        cycle, required = _door_world(brazos, dana, "06-E")
    response = api_call(
        billing_api.bill_runs,
        "post",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        data={
            **required,
            "cycle_id": str(cycle.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
        },
    )
    assert response.status_code == 201
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
        assert run.due_days is None
        assert _due(run) == date(2026, 7, 22), "the cycle's default still governs"


@pytest.mark.parametrize("bad", ["-1", "two weeks", -3, 1.5])
def test_w2_t4__a_due_days_that_is_not_a_whole_number_of_days_is_refused(brazos, dana, bad):
    """A due date decides when a late fee starts (BR-BIL-001), so a value that
    cannot be read is refused BY NAME rather than dropped — dropping it would
    silently give the customer the cycle's terms while the clerk watched their
    own number disappear."""
    from apps.billing import api as billing_api

    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code=f"06-F{str(bad)[:3]}")
    response = api_call(
        billing_api.bill_runs,
        "post",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        data={
            "cycle_id": str(cycle.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "due_days": bad,
        },
    )
    # 11b §3 G1's flat envelope: the field-level refusal is what the wizard maps
    # onto the control that caused it.
    assert response.status_code == 422
    # ⚠ AMENDED 2026-09-30 (bulk bill run plan A1/B1): the door answers EVERY
    # Scope refusal at once, so this bare body is also missing its run name and
    # template and its cycle has no units — the due-days refusal is one field
    # error among them, on its own field with its own key (row 43).
    due = [error for error in response.data["field_errors"] if error["field"] == "due_days"]
    assert [error["reason"] for error in due] == ["due_days_invalid"]
    assert due[0]["message_key"] == "billing.runScope.refusal.dueDaysInvalid"
    assert response.data["message_key"] == "billing.runScope.refused"
    with tenant_ctx(brazos):
        assert not billing_models.BillRun.objects.filter(cycle_id=cycle.id).exists()


# ═══════════════════════════════════════════════════════════════════════════
# D8③ · THE CYCLE-LESS BILL TAKES ITS DUE DATE FROM THE RUN
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t4__a_one_time_run_carries_its_own_bill_date_and_due_days(brazos, dana):
    """PO, verbatim: *"it will be capture at the time of bulk billing - not
    here"*. So the RUN holds both and the bill can be issued: 1 July + 14 →
    **15 July**, with no cycle anywhere in the derivation."""
    with tenant_ctx(brazos):
        account = _one_time_account(brazos, dana, account_no="A-90101", asset_no="M-9601")
        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            bill_date=BILL_DATE,
            due_days=14,
            run_by=dana,
        )
        assert run.cycle_id is None
        assert run.due_days == 14
        assert _due(run) == date(2026, 7, 15)


def test_w2_t4__a_one_time_run_with_no_due_days_still_refuses_rather_than_guessing(brazos, dana):
    """D8③ says WHERE the answer comes from; it does not invent one when the
    clerk gives none. With no cycle and no typed terms the derivation refuses by
    name — a guessed due date decides when a late fee starts."""
    with tenant_ctx(brazos):
        account = _one_time_account(brazos, dana, account_no="A-90101", asset_no="M-9601")
        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            bill_date=BILL_DATE,
            run_by=dana,
        )
        with pytest.raises(Exception) as refusal:
            _due(run)
    assert "BR-BIL-024" in str(refusal.value)


def test_w2_t4__zero_due_days_on_a_one_time_run_is_lawful_too(brazos, dana):
    with tenant_ctx(brazos):
        account = _one_time_account(brazos, dana, account_no="A-90101", asset_no="M-9601")
        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="final",
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            bill_date=BILL_DATE,
            due_days=0,
            run_by=dana,
        )
        assert _due(run) == BILL_DATE


def test_w2_t4__the_tab_no_longer_says_a_one_time_bill_cannot_be_issued(brazos, dana):
    """The stated absence is REMOVED because the thing it stated is fixed —
    not left standing as a comment claiming a limit that no longer exists
    (hard-won law 1)."""
    codes = [row["code"] for row in one_time.ONE_TIME_UNAVAILABLE]
    assert "one_time_bill_cannot_be_issued_yet" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# D8④ · THE PRORATION DENOMINATOR IS WITHDRAWN — NO RULE IS BUILT
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t4__the_partial_window_absence_stays_and_stops_citing_a_withdrawn_question():
    """*"this is not required"*. The BEHAVIOUR is unchanged — a partial window
    still carries a full base charge, and the register still says so with its
    figures — and what changes is that it no longer promises a Product Owner
    ruling that has been withdrawn."""
    row = next(
        item
        for item in one_time.ONE_TIME_UNAVAILABLE
        if item["code"] == "partial_window_charges_a_full_base_charge"
    )
    assert "OQ-242 asks the Product Owner" not in row["detail"]
    assert "withdrew" in row["detail"].lower() or "withdrawn" in row["detail"].lower()
    # The frozen figures the absence is measured in are untouched (B4.3 ❄️).
    assert "$38.00" in row["detail"] and "$24.51" in row["detail"]


def test_w2_t4__no_proration_denominator_is_invented_for_a_cycle_less_run(brazos, dana):
    """`_cycle_days` still answers None for a run with no cycle, so B4.3's
    factor stays 1. A denominator appearing here would be a money rule nobody
    ruled — and D8④ says none is required."""
    request = one_time.OneTimeRequest(
        account_id="whatever",
        kind=one_time.KIND_INTERIM,
        period_start=PERIOD[0],
        period_end=PERIOD[1],
    )
    assert one_time._cycle_days(request) is None
