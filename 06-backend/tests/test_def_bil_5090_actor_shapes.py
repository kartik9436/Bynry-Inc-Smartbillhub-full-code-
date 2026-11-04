# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the one-time run) · US-CUS-0xx (the cut) · US-RBS-010
#           (the runbook's one billing port) — DEF-BIL-5090, filed by
#           CR-094-BRC01 step 2 wave B and fixed here.
# Rules:    BR-BIL-005 (a run names WHO ran it) · BR-AUD-019 / BR-RBS-015 (an
#           automation is NAMED and carries no user id) · CLAUDE.md rule 7
#           (every money action writes audit_log) · hard-won law 7 (a check
#           that is structurally incapable of failing)
# Tests:    this file
# Impacts:  core/audit.actor_user_id · apps/billing/one_time.py ·
#           apps/billing/runs.py · apps/billing/pending.py ·
#           apps/billing/decisions.py · apps/billing/release.py
# ───────────────────────────────────────────────────────
"""`DEF-BIL-5090` — the actor shape the API actually builds could not run a bill.

**THE DEFECT, in one line.** `bill_runs.run_by` was filled with
`getattr(run_by, "pk", run_by)`, so an actor with no `pk` put ITSELF into a
UUID column and Django refused the whole request:

    ValidationError: "namespace(id=UUID('…'), role='system_admin')" is not a
    valid UUID.

**TWO LIVE SHAPES REACHED IT, AND NEITHER HAS A `pk`:**

* **the B12 §6a actor every API layer builds** — `SimpleNamespace(id=…,
  role=…)`. `POST /accounts/{id}/disconnect-case/cut` and the reconnection fee
  both travel through `customers/seams.raise_and_issue_cut_bill` into
  `billing/cut_bill` and `billing/fee_bill`, each of which passes the actor
  OBJECT as `run_by`;
* **a runbook's `AutomationActor`** — the `apply_fee` port hands one straight to
  `fee_bill.raise_charge_fee`. It has neither `id` nor `pk`, and the right answer
  is **NULL**: no person ran it, and the runbook's name travels on the audit row
  (`BR-AUD-019`, `apps/billing/runbook_ports.py`'s own docstring).

**WHY EVERY TEST PASSED OVER IT — hard-won law 7's *structurally incapable of
failing*, living in a fixture.** `tests/test_us_met_helpers.staff_actor` returns
`SimpleNamespace(id=…, pk=…, role=…, user=…)`: **wider than anything production
builds.** Every cut test handed billing a `pk` no API layer has, so the resolution
resolved and the suite was green over a path that raised in production.

**SO THE ACTORS BELOW ARE BUILT BY CALLING THE PRODUCTION BUILDERS**
(`customers.api._actor`, `customers.transfer_disconnect_api._actor`) rather than
by hand. A fixture cannot widen out from under this file: if those builders
change shape, these tests change with them.

Every assertion here was driven RED first, in `pytest`, against the unfixed
resolution — the verbatim failures are in the decision-log entry of 2026-09-12.
"""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from apps.billing import cut_bill, fee_bill, one_time
from apps.customers import api as customers_api, transfer_disconnect_api
from core import audit as core_audit
from tests.test_us_bil_001_prepare import a_billed_unit, a_cycle, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


def _an_account(brazos, dana, *, account_no, asset_no, label):
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label=label)
    return an_account(brazos, unit["id"], account_no)


def _api_actor(builder, user):
    """The actor a real request produces, from the production builder itself.

    The request stub carries only what the builder reads: `user` (set by the
    session layer) and `tenant_role` (server-attached by identity, BE-04, and
    never client input).
    """
    return builder(SimpleNamespace(user=user, tenant_role="system_admin"))


# ── the shape half: what the API layer actually hands billing ───────────────


def test_def_bil_5090_tc1__the_api_actor_has_no_pk_and_the_fixture_does(brazos):
    """The escape itself, asserted so it cannot come back.

    This is the test that was missing. It says nothing about billing — it says
    the FIXTURE is wider than PRODUCTION, which is why every cut test passed.
    """
    with tenant_ctx(brazos):
        fixture = staff_actor(brazos, "system_admin", "bil5090-shape@brazos.test")
        production = _api_actor(transfer_disconnect_api._actor, fixture.user)

    assert hasattr(fixture, "pk"), "the fixture actor carries a pk"
    assert not hasattr(production, "pk"), (
        "the B12 actor is (id, role) and must NOT be widened to carry a pk — "
        "widening the namespace would hide DEF-BIL-5090 again instead of fixing it"
    )
    assert production.id == fixture.user.id
    # Both customers builders are restated rather than shared (see their
    # docstrings), so both are checked — one drifting is the whole hazard.
    with tenant_ctx(brazos):
        twin = _api_actor(customers_api._actor, fixture.user)
    assert not hasattr(twin, "pk")
    assert twin.id == production.id


# ── the resolver: one named function, four shapes ───────────────────────────


def test_def_bil_5090_tc2__the_resolver_answers_every_actor_shape(brazos):
    """`core.audit.actor_user_id` — the one place this question is answered."""
    with tenant_ctx(brazos):
        fixture = staff_actor(brazos, "system_admin", "bil5090-resolve@brazos.test")
        production = _api_actor(customers_api._actor, fixture.user)

    user_id = fixture.user.id
    assert core_audit.actor_user_id(production) == user_id, "the B12 actor, by id"
    assert core_audit.actor_user_id(fixture) == user_id, "the fixture actor, by id or pk"
    assert core_audit.actor_user_id(fixture.user) == user_id, "a users row"
    assert core_audit.actor_user_id(user_id) == user_id, "an id already in hand"
    assert core_audit.actor_user_id(str(user_id)) == str(user_id), "…even as text"
    assert core_audit.actor_user_id(None) is None, "an unnamed system job"
    assert (
        core_audit.actor_user_id(core_audit.AutomationActor("runbook", "Late fees", "4")) is None
    ), "an automation is NAMED on the audit row and carries NO user id (BR-AUD-019)"
    assert core_audit.actor_user_id(SimpleNamespace(role="clerk")) is None, (
        "nothing that could be a user id resolves to NULL rather than to the object — "
        "writing the object is DEF-BIL-5090"
    )


# ── the run row: the write that could not happen ────────────────────────────


def test_def_bil_5090_tc3__the_api_actor_can_run_a_one_time_bill(brazos, dana):
    """The reproduction. RED before the fix with the ValidationError above."""
    with tenant_ctx(brazos):
        fixture = staff_actor(brazos, "system_admin", "bil5090-run@brazos.test")
        actor = _api_actor(transfer_disconnect_api._actor, fixture.user)
        account = _an_account(brazos, dana, account_no="A-95090", asset_no="M-95090", label="A")

        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type=cut_bill.BILL_TYPE_CUT,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=PERIOD_END,
            due_days=14,
            run_by=actor,
            actor=actor,
        )
        run.refresh_from_db()

    # BR-BIL-005 — the run names WHO ran it, and it is the person, not a shape.
    assert str(run.run_by_id) == str(fixture.user.id)


def test_def_bil_5090_tc4__a_runbook_runs_one_with_no_user_at_all(brazos, dana):
    """An `AutomationActor` writes NULL, not itself. `run_by` is nullable for this."""
    runbook = core_audit.AutomationActor("runbook", "Late fee ladder", "4")
    with tenant_ctx(brazos):
        account = _an_account(brazos, dana, account_no="A-95091", asset_no="M-95091", label="B")

        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type=fee_bill.BILL_TYPE_FEE,
            period_start=PERIOD_START,
            period_end=PERIOD_START,
            bill_date=PERIOD_START,
            due_days=14,
            run_by=runbook,
            actor=runbook,
        )
        run.refresh_from_db()

    assert run.run_by_id is None, "no person ran it; the runbook's name is on the audit row"


def test_def_bil_5090_tc5__an_id_in_hand_still_works(brazos, dana):
    """The regression guard: billing's own API passes a raw id, and always has."""
    with tenant_ctx(brazos):
        fixture = staff_actor(brazos, "system_admin", "bil5090-raw@brazos.test")
        account = _an_account(brazos, dana, account_no="A-95092", asset_no="M-95092", label="C")

        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            run_by=fixture.user.id,
            actor=fixture,
        )
        run.refresh_from_db()

    assert str(run.run_by_id) == str(fixture.user.id)


def test_def_bil_5090_tc6__no_billing_write_resolves_an_actor_by_pk_alone(brazos):
    """The guard over the SHAPE of the code, so the next site cannot be written.

    Six actor columns in this module were filled with `getattr(x, "pk", x)`.
    That expression is what put a namespace in a UUID column, and it reads as
    defensive, which is why it spread. It is now banned by name for ACTORS.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "apps" / "billing"
    names = r"run_by|confirmed_by|decided_by|excluded_by|actor"
    # ① THE DEFECT'S OWN SHAPE: the default is the ACTOR ITSELF, so an object
    #    with no `pk` is written into a UUID column. `bill_run`, `invoice` and
    #    `credit_note` use the same expression lawfully — a model row's `pk`
    #    always resolves — which is why this is keyed on ACTOR names.
    itself = re.compile(rf'getattr\(\s*({names})\s*,\s*"pk"\s*,\s*\1\s*\)')
    # ② THE SILENT HALF: `pk` with no `id` anywhere on the line answers None for
    #    every B12 actor, which loses WHO on a money act instead of raising.
    pk_only = re.compile(rf'getattr\(\s*({names})\s*,\s*"pk"')
    offenders = []
    for path in sorted(root.rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # A comment may RECORD the expression — that is how the defect is
            # explained at each site it was fixed. Only code is banned.
            if line.lstrip().startswith("#"):
                continue
            if itself.search(line) or (pk_only.search(line) and '"id"' not in line):
                offenders.append(f"{path.relative_to(root)}:{n}")
    assert offenders == [], (
        "an actor's user id is resolved by core.audit.actor_user_id and nowhere else — "
        f"DEF-BIL-5090; found {offenders}"
    )
