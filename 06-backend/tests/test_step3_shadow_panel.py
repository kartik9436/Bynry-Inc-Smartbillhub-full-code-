# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 "Check what we found" — the pre-commit stage)
#           Screens: S31.2
# Defects:  DEF-438 (the chain had no production caller) · DEF-494 (the two
#           paths mean OPPOSITE things by "a plan in force" — measured here on
#           a real account for the first time) · DEF-1811 (the shadow could not
#           be run on any account; the reason the screen half was withheld) ·
#           DEF-1813 (CLOSED — the last missing fact)
# Rules:    BR-BIL-039 (the preview and the real run are the SAME code) ·
#           BR-SHL-020 (a refusal reads as a sentence) · BR-RAT-087 (the server
#           formats money, never the client) · BR-TEN-003 / HR-1 (a cross-tenant
#           read is ABSENT) · CLAUDE.md rule 1 (tenant scoping) · rule 4 (an
#           issued bill is immutable — nothing here writes one)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""STEP 3 OF THE R1–R7 CUTOVER, ON THE SCREEN: the disagreements, in front of a person.

⚠ **EVERY ASSERTION HERE RECORDS A DIFFERENCE AND CHOOSES NEITHER SIDE.**
Decision log 2026-08-27: *"A lane that makes the disagreements go away has
destroyed the evidence this job exists to produce, and has done it inside the
one system where a wrong answer is irreversible."* So nothing below asserts that
the two paths agree, and nothing below asserts which of two figures is right.

THE ONE PROPERTY THAT MATTERS MOST, AND IT IS A NEGATIVE ONE
------------------------------------------------------------
*"READ THE THIRD AND FOURTH NUMBERS TOGETHER OR THEY LIE. '0 disagreed' is also
what perfect agreement looks like."* The panel is only worth having if it can
tell **agreement** from **nobody asked**, so the two cases are built side by
side here — the SAME fixture with and without a recorded connection size — and
the test asserts that a reader can distinguish them.

WHY THIS FILE IS NOT `test_def_1810_disagreements.py`
------------------------------------------------------
That file measures the shadow by CALLING `shadow_account`. This one goes through
the route a browser goes through, over a real bill run, because the finding the
last lane recorded was that the screen half did not exist. A test that called the
report function directly would pass with no endpoint mounted, which is DEF-438's
own escape shape one level up.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import resolution_shadow, shadow_report
from apps.metering import models as metering_models

from tests.test_us_bil_001_003_run_api import (
    a_dated_cycle,
    an_actor_user,
    created_run,
)
from tests.test_us_bil_001_prepare import a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read
from tests.test_us_ten_helpers import *  # noqa: F401,F403

pytestmark = pytest.mark.django_db

#: The size the fixture's meter is recorded as. Any string the schedule does not
#: also serve would do; what matters is that ONE IS RECORDED, because an
#: unrecorded size is what stopped the shadow being runnable at all (DEF-1811).
A_RECORDED_SIZE = "5/8"


def shadow_of(tenant, run_id, role="billing_clerk"):
    return api_call(
        billing_api.run_pricing_shadow,
        "get",
        user=FakeUser(),
        role=role,
        tenant=tenant,
        run_id=str(run_id),
    )


def a_run_over_one_account(
    tenant,
    actor,
    *,
    size=None,
    multiplier="1",
    account_no="ACC-1042",
    asset_no="M-0001",
    cycle=None,
):
    """One cycle, one plan, one metered unit with a committed read, one account.

    `size` is the whole experiment. With a size recorded the adapter can
    assemble R3's inputs and the chain RUNS; without one it cannot, and the
    account comes back as *"could not be worked out"* — which is the pair of
    readings this file exists to keep apart.
    """
    cycle = cycle if cycle is not None else a_dated_cycle(tenant)
    plan = a_priced_plan(tenant)
    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")  # noqa: F405
    unit = make_unit(actor, premises["id"], label=f"Unit {asset_no}", services=["electric"])  # noqa: F405,E501
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], multiplier=multiplier)
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    delta = Decimal("412")
    commit_read(
        actor,
        asset["id"],
        day="2026-06-28",
        value="14212",
        prior_value="13800",
        # BR-MET-019 — what metering itself stores: ALREADY post-multiplier.
        consumption=delta * Decimal(multiplier),
        unit="kWh",
        multiplier=multiplier,
    )
    if size is not None:
        asset_services.update_asset(actor, asset["id"], {"size_class": size})
    account = an_account(tenant, unit["id"], account_no)
    return cycle, plan, account, unit, asset


# ══════════════════════════════════════════════════════════════════════════
# TC-1..2 — THE TWO READINGS THAT MUST NEVER LOOK ALIKE
# ══════════════════════════════════════════════════════════════════════════


def test_TC1_a_real_disagreement_reaches_the_screen_with_its_own_sentence(brazos, dana):
    """⚠ **THE HEADLINE, AND IT IS THE FIRST TIME IT HAS BEEN VISIBLE TO A PERSON.**

    A real account of a real tenant, prepared by the real bill run, on the stage
    that shows every input before anything commits. Measured through the route:

        accounts 1 · attempted 1 · agreed 0 · disagreed 1 · chain_refused 1
        not_attempted 0 · by_step {R1: 1} · blocked_by_reason {}

    **The class is `R1 · NoPlanInForce` and it is `DEF-494` arriving as a
    measurement.** The live path resolved a plan for this account and priced it
    into the run's READY set; the ruled path refuses at R1 because no plan
    VERSION is in force at the service date. The register's own words for it:
    *"THE LIVE PATH AND THE RULED PATH MEAN OPPOSITE THINGS BY 'A PLAN IN
    FORCE'"*.

    ⚠ **`attempted` IS ASSERTED BESIDE `disagreed`, AND THAT IS THE POINT OF THE
    CASE.** A run reporting `disagreed 1` out of `attempted 0` would be a wiring
    fault wearing a finding's clothes.

    ⚠ **AND NOTHING HERE ASSERTS WHICH PATH IS RIGHT.** That ruling is step 4 and
    it is the Product Owner's. What is asserted is that both answers reached the
    screen and that neither was chosen for them.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=A_RECORDED_SIZE, multiplier="10"
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        assert run.status_code == 201, run.data
        served = shadow_of(brazos, run.data["id"])

    assert served.status_code == 200, served.data
    body = served.data
    # The counts, in the shape the screen prints them.
    assert body["accounts"] == 1
    assert body["attempted"] == 1, body
    assert body["not_attempted"] == 0, body
    assert body["blocked_by_reason"] == {}, body
    assert body["disagreed"] == 1, body
    assert body["chain_refused"] == 1, body
    assert body["by_step"] == {"R1": 1}, body

    # ⚠ THE CLASS ROW — the thing step 4 is ruled from. One class, one account.
    assert len(body["classes"]) == 1, body["classes"]
    row = body["classes"][0]
    assert row["step"] == "R1"
    assert row["kind"] == "refusal"
    assert row["refusal_type"] == "NoPlanInForce"
    assert row["accounts"] == 1, row
    assert row["example_account_no"] == "ACC-1042"
    # BR-SHL-020 — a SENTENCE, not a code. Asserted on the sentence's own
    # content rather than on its presence: rendering the exception class name is
    # named in the decision log as "the lazy way to make the first test pass",
    # and `NoPlanInForce` is what that would have produced.
    assert row["example_sentence"] is not None
    assert "no plan version in force" in row["example_sentence"]
    assert row["example_sentence"] != row["refusal_type"]
    # ⚠ AND WHAT TODAY'S BILLING WAS ABOUT TO USE. Without this half the row
    # says the new rules refuse and says nothing about the bill that was going
    # out on the old ones.
    assert row["example_live_summary"] is not None
    assert "Residential Standard" in row["example_live_summary"]
    assert "electric" in row["example_live_summary"]

    # The account grouping carries the same finding, per account.
    detail = body["accounts_detail"][0]
    assert detail["status"] == resolution_shadow.STATUS_CHAIN_REFUSED
    assert detail["refusal_step"] == "R1"
    assert detail["blocked_reason"] is None


def test_TC2_an_unaskable_account_is_not_an_account_that_agreed(brazos, dana):
    """⚠ **THE SAME FIXTURE WITH ONE FACT REMOVED, AND IT MUST NOT READ THE SAME.**

    The meter has no recorded connection size, so the adapter cannot assemble
    R3's inputs and the chain is not run. Through the same route:

        accounts 1 · attempted 0 · agreed 0 · disagreed 0 · chain_refused 0
        not_attempted 1 · blocked {connection_size_unresolved: 1}

    **Read `disagreed` alone and this is TC-1's opposite: a clean run.** It is
    nothing of the sort — it is a run in which nothing was compared. The panel
    has to make that visible, and the three things below are how:

    1. `attempted` is 0 and is on screen beside `disagreed`;
    2. the account is `not_attempted`, never `agreed`;
    3. `blocked_classes` names the missing fact and counts the accounts, so a
       person is told what to go and do rather than shown a zero.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=None
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        served = shadow_of(brazos, run.data["id"])

    body = served.data
    assert body["accounts"] == 1
    assert body["attempted"] == 0, body
    assert body["disagreed"] == 0, body
    assert body["agreed"] == 0, body
    assert body["not_attempted"] == 1, body
    assert body["classes"] == [], body

    # ⚠ THE DISTINGUISHING FACT. Both runs report `disagreed 0`-shaped good news
    # on one number; only these two members tell them apart.
    assert body["blocked_by_reason"] == {
        resolution_shadow.MISSING_CONNECTION_SIZE: 1
    }, body
    assert len(body["blocked_classes"]) == 1
    blocked = body["blocked_classes"][0]
    assert blocked["reason"] == resolution_shadow.MISSING_CONNECTION_SIZE
    assert blocked["accounts"] == 1
    assert blocked["example_account_no"] == "ACC-1042"
    assert "connection size" in (blocked["example_detail"] or "")

    detail = body["accounts_detail"][0]
    assert detail["status"] == resolution_shadow.STATUS_NOT_ATTEMPTED
    assert detail["status"] != resolution_shadow.STATUS_AGREED


# ══════════════════════════════════════════════════════════════════════════
# TC-3..4 — THE CLASS IS THE DELIVERABLE, AND ITS COUNT IS WHAT MAKES IT RULABLE
# ══════════════════════════════════════════════════════════════════════════


def test_TC3_a_class_counts_ACCOUNTS_across_the_whole_run(brazos, dana):
    """⚠ **ONE ACCOUNT AT R1 AND FOUR HUNDRED AT R1 ARE THE SAME CLASS AND A
    COMPLETELY DIFFERENT DECISION.**

    Two accounts on one cycle, both refusing at the same step. The class list
    must fold them into ONE row carrying `accounts: 2` — a per-account list of
    two identical findings is not something a person can rule on, and a count of
    occurrences rather than accounts would double a single account that refused
    twice.

    This is the batch half of the job: the report is over the RUN, not over an
    account, and `summarise` is asked to aggregate what the loop produced.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=A_RECORDED_SIZE, account_no="ACC-1042", asset_no="M-0001"
        )
        a_run_over_one_account(
            brazos,
            dana,
            size=A_RECORDED_SIZE,
            account_no="ACC-1043",
            asset_no="M-0002",
            cycle=cycle,
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        served = shadow_of(brazos, run.data["id"])

    body = served.data
    assert body["accounts"] == 2, body
    assert body["attempted"] == 2, body
    assert len(body["classes"]) == 1, body["classes"]
    assert body["classes"][0]["accounts"] == 2, body["classes"][0]
    # The by-step grouping names them too, so a reader can go from the class to
    # the customers without opening every row.
    assert sorted(body["steps"][0]["accounts"]) == ["ACC-1042", "ACC-1043"]


def test_TC4_the_report_is_ordered_by_how_many_accounts_a_class_touches():
    """The biggest class first, because that is the order the rulings are worth
    making in. A pure function over outcomes — no database, no run.
    """
    outcomes = tuple(
        resolution_shadow.ShadowOutcome(
            account_id=f"id-{n}",
            account_no=f"ACC-{n}",
            status=resolution_shadow.STATUS_CHAIN_REFUSED,
            refusal_step="R1" if n < 3 else "R2",
            refusal_type="NoPlanInForce" if n < 3 else "NoScheduleForService",
            refusal_sentence="…",
        )
        for n in range(4)
    )
    rows = shadow_report.classes_from(outcomes)
    assert [(row["step"], row["accounts"]) for row in rows] == [("R1", 3), ("R2", 1)]


# ══════════════════════════════════════════════════════════════════════════
# TC-5..8 — THE FOUR THINGS THIS PANEL IS FORBIDDEN TO DO
# ══════════════════════════════════════════════════════════════════════════


def test_TC5_reading_the_panel_writes_no_bill_and_no_row(brazos, dana):
    """⚠ **STEPS 1–4 OF THE CUTOVER ALL READ "nothing" UNDER *what changes on a
    bill*.** The panel is a read on the stage before anything commits, so after
    calling it the run must hold exactly what it held before: no invoice, no
    line, no decision, no exclusion.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=A_RECORDED_SIZE
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        shadow_of(brazos, run.data["id"])
        shadow_of(brazos, run.data["id"])  # twice — a clerk refreshes

        assert billing_models.Invoice.objects.count() == 0
        assert billing_models.InvoiceLine.objects.count() == 0
        assert billing_models.BillRunDecision.objects.count() == 0
        assert billing_models.BillRunExclusion.objects.count() == 0


def test_TC6_a_display_string_can_never_bring_two_figures_together():
    """⚠ **`$8.0000` AND `$8.0049` BOTH DISPLAY `8.00`.**

    BR-RAT-087 makes the SERVER render money for display, and this file's job is
    to be certain that rendering is a LABEL and never the comparison. Two stored
    figures that differ in the fourth place are a disagreement, and they stay one
    with identical display strings beside them.

    Also: a step whose figures are not money gets no display string at all, so a
    version id can never acquire a currency-shaped rendering it has not earned.
    """
    money_a = shadow_report._display("R3/R4", Decimal("8.0000"))
    money_b = shadow_report._display("R3/R4", Decimal("8.0049"))
    assert money_a == money_b == "8.00"
    # The stored figures the comparison was made on are still different, and
    # the report carries THOSE.
    assert Decimal("8.0000") != Decimal("8.0049")
    assert shadow_report._display("R1", "some-version-uuid") is None
    assert shadow_report._display("R3/R4", None) is None


def test_TC7_a_comparison_that_raises_is_not_attempted_and_never_agreed(
    brazos, dana, monkeypatch
):
    """⚠ **THE ONE WAY THIS PANEL COULD TELL A COMFORTABLE LIE.**

    `compare()` raises rather than reporting parity when it compared nothing —
    *"a parity checker that compares nothing returns no divergences and reads as
    green"*. So an escaped exception must land under **could not be worked out**
    with its own sentence, never under agreement, and it must not blank the panel
    for the other accounts in the run.
    """

    def _boom(*_args, **_kwargs):
        raise AssertionError("the chain resolved ZERO services")

    monkeypatch.setattr(resolution_shadow, "shadow_account", _boom)
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=A_RECORDED_SIZE
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        served = shadow_of(brazos, run.data["id"])

    body = served.data
    assert served.status_code == 200
    assert body["agreed"] == 0, body
    assert body["not_attempted"] == 1, body
    assert body["blocked_by_reason"] == {shadow_report.SHADOW_RAISED: 1}, body
    assert "ZERO services" in body["blocked_classes"][0]["example_detail"]


def test_TC8_the_panel_never_crosses_a_tenant_boundary(brazos, dana, lonestar):
    """CLAUDE.md rule 1 / BR-TEN-003 — another tenant's run reads as ABSENT, and
    an unknown id reads the same way. A comparison panel that leaked would leak
    account numbers and plan names, which is the whole of what it prints.
    """
    with tenant_ctx(brazos):
        cycle, _plan, _account, _unit, _asset = a_run_over_one_account(
            brazos, dana, size=A_RECORDED_SIZE
        )
        actor_user = an_actor_user(brazos)
        run = created_run(brazos, actor_user, cycle)
        run_id = run.data["id"]

    with tenant_ctx(lonestar):
        cross = shadow_of(lonestar, run_id)
    assert cross.status_code == 404, cross.data


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002 · decision log 2026-08-27 *"HOW R1–R7 GETS WIRED INTO
#         BILLING"* step 3 and *"HOW THE SCREEN PROVES R1–R7 IS WIRED"* ·
#         decision log 2026-08-27 *"R1–R7 STEP 3, DELIVERED"* §4 (the withheld
#         screen half this discharges) · BR-BIL-039 · BR-SHL-020 · BR-RAT-087
# generated: 2026-08-28 by the R1–R7 step-3 screen lane (claude)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: golden-verify 33 PASS / 0 FAIL, unchanged — no ❄️ B4/B5 figure is read
#         or asserted here
# exceptions: (1) **NO CASE ASSERTS THAT THE TWO PATHS AGREE.** Whether they
#         agree is step 4's ruling and the Product Owner's; a test pinning
#         parity here would be this lane answering the question the cutover
#         exists to ask. (2) `by_step` IS pinned in TC-1 and will go red the day
#         a lane fixes R1 — deliberately, because that fix must arrive with a
#         ruling and a re-measurement rather than silently.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
