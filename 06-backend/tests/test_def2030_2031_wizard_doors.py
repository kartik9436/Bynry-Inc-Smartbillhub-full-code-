# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2031 (every step of the transfer wizard has no door) ·
#           DEF-2030 (the whole disconnect ladder has no door). Both found by
#           G52, both named in `10-scripts/gates/g52_no_door_baseline.txt`.
# Story:    US-CUS-027 (S89 · TRF-02) · CR-030 W7 tasks 7.1–7.11 (S90 · DSC-02)
# Rules:    BR-SHL-019 (ONE transactional commit per wizard) · BR-SHL-025 /
#           BR-IDN-009 (server-enforced RBAC) · BR-CUS-039 (certified mail is
#           REQUIRED on the final tier) · BR-CUS-100 (a tier-3 cut must not be
#           schedulable on an unrecorded service) · BR-TEN-003 / HR-1 (a
#           cross-tenant id is a 404, never a 403) · CLAUDE.md hard rule 1
#           (tenant scoping) · rule 7 (every money action writes `audit_log`)
# Ruling:   decision log 2026-08-28 — "THREE WORKFLOWS GET THEIR DOORS".
# ───────────────────────────────────────────────────────
"""The SERVING half of `TRF-02` and `DSC-02`, and only the serving half.

`apps/customers/transfers.py` (1,368 lines) and `apps/customers/disconnects.py`
(4,068 lines) landed built and tested — `test_w7_transfers.py`,
`test_w7_disconnects.py`, `test_w7_cut_reconnect.py`,
`test_w7_proof_of_service.py` — and **unreachable**. `apps/customers/api.py`
mounted `path("transfers", …)` and `path("disconnects", …)`, two LISTS, so a
clerk could see both queues and act on no row of either. Meanwhile
`TransferWizard.tsx` and `DisconnectWizard.tsx` were finished and mounted in
`App.tsx`, posting to addresses that 404'd. Hard-won law 2, from both ends at
once.

**WHAT THIS FILE ASSERTS, AND WHAT IT DELIBERATELY DOES NOT.** The engines'
arithmetic, their refusals and every worked B18 figure are proved in the four
`test_w7_*` files against the modules. Restating them here would be a second
copy that can drift from the first. What is proved HERE is the five claims only
a ROUTE can make:

  1. **Each path is mounted at the name the SCREEN already uses.**
     `07-frontend/src/features/customers/transferDisconnectEndpoints.ts` names
     exactly six addresses. A route mounted at a name of our own invention is a
     defect no unit test can see, and it is the defect the endpoint file spent
     forty lines predicting.
  2. **The transfer's one door is ONE TRANSACTION** (BR-SHL-019). This is the
     claim the whole design rests on: a failure at any stage leaves ZERO rows,
     so an account is never stranded behind `uq_transfers_open_from` with an
     open transfer no screen can show and nobody can cancel.
  3. **The ladder's refusals reach the wire as SENTENCES, not 500s.**
     `DisconnectRuleError` is not a catalog exception; without the boundary
     translation a clerk meets BR-CUS-100 as a stack trace.
  4. **The ladder is NOT collapsed into one door.** A cut is still refused
     without tier 3 and without a certified receipt, THROUGH THE ROUTE.
  5. **RBAC and tenant isolation hold at the door** — an Executive is refused,
     and a cross-tenant id is 404 and never 403.

RED PROOF (hard-won law 7). Every case below was first run against an untouched
worktree at this lane's starting commit, where the routes do not exist:
**23 of 23 FAIL there**, 18 of them at `AttributeError`/`ImportError` on a
module that is not present. The verbatim transcript is in the lane report.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.customers import disconnects, models as customers_models, transfers
from apps.customers import transfer_disconnect_api as doors
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    audit_actions,
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call
from tests.test_w7_disconnects import _owes  # noqa: F401 — the AR seam stub
# ⚠ `_wire_interest` IS NOT IN `test_w7_transfers` AND NEVER WAS (DEF-2589).
# It lives in `test_w7_worklists`; naming the wrong module here raised
# ImportError at COLLECTION, and pytest aborts the whole run on a collection
# error — so this one line made the ENTIRE backend suite unrunnable, which is
# why every lane has been reduced to scoped runs and no baseline was provable.
from tests.test_w7_transfers import _mover, _unit  # noqa: F401
from tests.test_w7_worklists import _wire_interest  # noqa: F401

pytestmark = pytest.mark.django_db

D = Decimal


# ── fixture plumbing ───────────────────────────────────────────────────────
# Every fixture below is built INSIDE `tenant_ctx`. `api_call` enters its own
# context around the VIEW (that is the BE-01 middleware's job in production)
# and around nothing else, so a row created outside one is refused AUTH-003 —
# hard rule 1 doing exactly what it says.


def _make_mover(actor, tenant, **kw):
    with tenant_ctx(tenant):
        return _mover(actor, tenant, **kw)


def _make_unit(actor, tenant, **kw):
    with tenant_ctx(tenant):
        return _unit(actor, tenant, **kw)


def _make_occupant(actor, tenant, unit, **kw):
    from tests.test_w7_transfers import _occupant

    with tenant_ctx(tenant):
        return _occupant(actor, unit, **kw)



# ══════════════════════════════════════════════════════════════════════════
# 1 · THE SIX ADDRESSES THE SCREEN ALREADY CALLS
# ══════════════════════════════════════════════════════════════════════════
#
# Resolved through `config/urls.py` — the REAL URLconf — rather than by reading
# this module's own `urlpatterns`, which would prove only that a list contains
# what we just put in it. The include is the half that goes missing (it went
# missing for `apps/billing/api.py`, and every S30 screen rendered a 404).

#: `transferDisconnectEndpoints.ts`, verbatim. If one of these strings changes,
#: this list is the thing that has to change with it.
SCREEN_ADDRESSES = [
    ("post", "/api/brazos/transfers/commit", "transfer_commit"),
    ("get", "/api/brazos/transfers/TRF-1/money", "transfer_money"),
    ("post", "/api/brazos/disconnects/schedule", "schedule_cut"),
    ("get", "/api/brazos/accounts/A-1/protections", "account_protections"),
    ("get", "/api/brazos/accounts/A-1/reconnection-terms", "account_reconnection_terms"),
    ("get", "/api/brazos/accounts/A-1/ladder", "account_ladder"),
]


@pytest.mark.parametrize("method,path,view_name", SCREEN_ADDRESSES)
def test_the_six_addresses_the_wizards_call_are_mounted(method, path, view_name):
    """DEF-2030 / DEF-2031 — the whole defect, in one assertion per address.

    Each of these 404'd before this lane. `transferDisconnectEndpoints.ts` says
    so in a forty-line block at the top of the file, address by address.
    """
    match = resolve(path)
    assert match.func.__module__ == doors.__name__, (
        f"{path} resolves into {match.func.__module__}, not the module that serves it"
    )
    # `api_view` WRAPS the function, so `__name__` is "view" on both sides —
    # comparing names would pass on any two routes in this module and prove
    # nothing. Identity is the assertion that actually distinguishes them.
    assert match.func is getattr(doors, view_name), (
        f"{path} resolves to a different view than {view_name}"
    )


def test_every_ladder_act_has_a_door_and_none_shadows_another():
    """All eleven acts, plus the three reads, reachable and distinct.

    A path each act can be reached at is the defect being fixed; DISTINCT views
    is the bug this lane shipped and G52 caught — two `path()` entries on one
    pattern is a route the router can never reach, because Django resolves the
    first match and stops.
    """
    ladder = {
        "/api/brazos/accounts/A-1/disconnect-case": "open_disconnect_case",
        "/api/brazos/accounts/A-1/disconnect-case/advance": "advance_disconnect_case",
        "/api/brazos/accounts/A-1/disconnect-case/notices": "record_disconnect_notice",
        "/api/brazos/accounts/A-1/disconnect-case/cut": "commit_cut",
        "/api/brazos/accounts/A-1/disconnect-case/stop": "stop_by_hand",
        "/api/brazos/accounts/A-1/disconnect-case/reconnecting": "mark_reconnecting",
        "/api/brazos/accounts/A-1/disconnect-case/restore": "restore_service",
        "/api/brazos/disconnect-notices/N-1/proof": "record_proof_of_service",
        "/api/brazos/disconnect-notices/awaiting-proof": "notices_awaiting_proof",
        "/api/brazos/protections/P-1/lift": "lift_protection",
        "/api/brazos/accounts/A-1/protections": "account_protections",
    }
    seen = {}
    for path, view_name in ladder.items():
        match = resolve(path)
        assert match.func.__module__ == doors.__name__, f"{path} is not served here"
        seen[path] = match.func
    assert len(set(id(f) for f in seen.values())) == len(seen), (
        "two paths resolve to the SAME view object — one of them is unreachable"
    )


def test_the_literal_awaiting_proof_is_not_read_as_a_notice_id():
    """Ordering. `disconnect-notices/awaiting-proof` must not be swallowed."""
    assert resolve("/api/brazos/disconnect-notices/awaiting-proof").func.__module__ == doors.__name__
    # and the wildcard still works beside it
    assert resolve("/api/brazos/disconnect-notices/N-1/proof").func.__module__ == doors.__name__


def test_the_two_existing_list_routes_are_not_shadowed_by_the_new_ones():
    """`GET /transfers` and `GET /disconnects` still reach `customers/api.py`.

    A new module included after an existing one can shadow it silently. These
    two lists are what a clerk uses to FIND the row the wizards act on, so
    breaking them while opening the wizards' doors would be a net loss.
    """
    assert resolve("/api/brazos/transfers").func.__module__.endswith("customers.api")
    assert resolve("/api/brazos/disconnects").func.__module__.endswith("customers.api")
    assert resolve("/api/brazos/accounts/A-1").func.__module__.endswith("customers.api")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE TRANSFER'S ONE DOOR IS ONE TRANSACTION (BR-SHL-019)
# ══════════════════════════════════════════════════════════════════════════


def _commit(tenant, plan, *, actor, role="billing_clerk"):
    """`api_call` with a REAL identity user behind it.

    `move_records.performed_by` is an FK into `users`, so a synthetic uuid
    breaks the reviewed cross-module FK set (B2 §2) at commit rather than at
    the call — which is `staff_actor`'s own reason for existing.
    """
    return api_call(
        doors.transfer_commit,
        "post",
        user=actor.user,
        role=role,
        tenant=tenant,
        data=plan,
    )


def test_the_wizards_whole_plan_commits_through_one_door(brazos, marcus, monkeypatch):
    """`TRF-02.5` end to end — the five staged writes, one POST.

    The plan is `TransferCommitPlan` exactly as the screen builds it. Before
    this lane the same call 404'd, which is the entire defect.
    """
    _wire_interest(monkeypatch)
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    target = _make_unit(marcus, brazos, label="22 Marten Row")

    response = _commit(
        brazos,
        {
            "from_account_id": str(account.id),
            "to_unit_id": str(target["id"]),
            "out_date": "2026-09-01",
            "in_date": "2026-09-01",
            "deposit_carry": True,
            "arrears_follow": True,
        },
        actor=marcus,
    )

    assert response.status_code == 201, response.data
    body = response.data
    # TC-TRF-6 — one closes, one opens, and the transfer row links the two.
    assert body["state"] == transfers.Transfer.STATE_DONE
    assert body["from_account_id"] == str(account.id)
    assert body["to_account_id"] is not None
    assert body["committed_at"] is not None
    # The elections the wizard collected are ON the row, not defaulted away.
    assert body["deposit_carry_elected"] is True
    assert body["arrears_follow_elected"] is True
    # TC-TRF-3's signed half: NO money moved, and the engine proves it in-band.
    assert body["not_moved"]["refund_raised"] is False
    assert body["not_moved"]["deposit_recollected"] is False
    assert body["not_moved"]["journal_lines_written"] == 0


def test_a_failure_at_any_stage_leaves_zero_rows_behind(brazos, marcus, monkeypatch):
    """**THE CLAIM THE WHOLE DESIGN RESTS ON.** BR-SHL-019, proved.

    The target unit is already occupied, so stage 2 (`set_target_unit`) refuses
    under BR-CUS-017 — AFTER stage 1 has already created a `Transfer` row.

    Under five separate routes that row would SURVIVE, and
    `uq_transfers_open_from` allows only one open transfer per outgoing account,
    so `A` could never be transferred again — and `US-CUS-027 §8` records that
    no screen shows a transfer in flight, so nobody could find it to cancel.
    Under one transaction the count is zero and the clerk simply goes again.
    """
    _wire_interest(monkeypatch)
    _customer, account, _from_unit = _make_mover(marcus, brazos)
    occupied = _make_unit(marcus, brazos, label="24 Marten Row")
    _make_occupant(marcus, brazos, occupied, name="Sitting, Tenant")

    refused = _commit(
        brazos,
        {
            "from_account_id": str(account.id),
            "to_unit_id": str(occupied["id"]),
            "out_date": "2026-09-01",
            "in_date": "2026-09-01",
            "deposit_carry": True,
            "arrears_follow": True,
        },
        actor=marcus,
    )
    # 409, not 422: BIZ-STATE is a conflict — the unit is taken (B12 §3).
    assert refused.status_code == 409, refused.data
    assert refused.data["br_ref"] == "BR-CUS-017", refused.data

    assert customers_models.Account.objects.filter(id=account.id).exists()
    assert transfers.Transfer.objects.count() == 0, (
        "a half-built transfer survived the refusal — this account is now "
        "permanently un-transferable behind uq_transfers_open_from"
    )
    # And the proof that the strand would have been real: the account can be
    # transferred again immediately, to a unit that IS free.
    free = _make_unit(marcus, brazos, label="26 Marten Row")
    again = _commit(
        brazos,
        {
            "from_account_id": str(account.id),
            "to_unit_id": str(free["id"]),
            "out_date": "2026-09-01",
            "in_date": "2026-09-01",
            "deposit_carry": True,
            "arrears_follow": True,
        },
        actor=marcus,
    )
    assert again.status_code == 201


def test_a_cleared_election_is_not_silently_re_ticked_by_the_server(
    brazos, marcus, monkeypatch
):
    """`elect_money` defaults an ABSENT key to the statement's own reading.

    So the door must pass both elections EXPLICITLY, including `False`. A
    cleared checkbox is a decision, and a server that re-ticked it would record
    that a human elected to carry a deposit they had just declined.
    """
    _wire_interest(monkeypatch)
    _customer, account, _from_unit = _make_mover(marcus, brazos, deposit=D("153.50"))
    target = _make_unit(marcus, brazos, label="28 Marten Row")

    body = _commit(
        brazos,
        {
            "from_account_id": str(account.id),
            "to_unit_id": str(target["id"]),
            "out_date": "2026-09-01",
            "in_date": "2026-09-01",
            "deposit_carry": False,
            "arrears_follow": False,
        },
        actor=marcus,
    ).data
    assert body["deposit_carry_elected"] is False
    assert body["arrears_follow_elected"] is False


def test_the_commit_writes_the_audit_row_and_the_view_does_not_write_a_second(
    brazos, marcus, monkeypatch, audit_rows
):
    """Hard rule 7, and the row is the SERVICE's — never a second one here."""
    _wire_interest(monkeypatch)
    _customer, account, _from_unit = _make_mover(marcus, brazos)
    target = _make_unit(marcus, brazos, label="30 Marten Row")
    _commit(
        brazos,
        {
            "from_account_id": str(account.id),
            "to_unit_id": str(target["id"]),
            "out_date": "2026-09-01",
            "in_date": "2026-09-01",
            "deposit_carry": True,
            "arrears_follow": True,
        },
        actor=marcus,
    )
    actions = audit_actions(audit_rows)
    assert actions.count("transfer.committed") == 1, actions


def test_an_executive_cannot_commit_a_transfer(brazos, marcus):
    """BR-SHL-025 / A4 — a transfer is never a View action."""
    refused = _commit(brazos, {"from_account_id": "x"}, actor=marcus, role="executive")
    assert refused.status_code == 403, refused.data


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE LADDER — REFUSALS REACH THE WIRE AS SENTENCES
# ══════════════════════════════════════════════════════════════════════════


def _ladder_call(view, tenant, *, actor, method="post", role="billing_clerk", data=None, **kw):
    return api_call(
        view, method, user=actor.user, role=role, tenant=tenant, data=data or {}, **kw
    )


def _detail(response):
    """The service's own sentence, off a rendered catalogue refusal.

    ⚠ **A REFUSAL IS A RESPONSE HERE, NOT AN EXCEPTION.** These are `@api_view`
    functions, so the BE-02 handler renders `BizError` into a 422 body — which
    is exactly what a clerk's browser receives. Asserting `pytest.raises` would
    assert on a shape no user ever meets.
    """
    params = (response.data or {}).get("params") or {}
    return params.get("detail", "") or ""


def test_a_cut_is_still_refused_without_a_certified_receipt_through_the_route(
    brazos, marcus
):
    """**BR-CUS-100 / BR-CUS-039, THROUGH THE DOOR.**

    The ladder is NOT collapsed into one call, and this is what that buys: the
    route cannot manufacture the tier or the postal receipt, so a cut on an
    account with no open case is refused — as a 422 catalogue refusal carrying
    the rule and the service's own sentence, never a 500 and never a success.
    """
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    refused = _ladder_call(
        doors.schedule_cut,
        brazos,
        actor=marcus,
        data={
            "account_id": str(account.id),
            "cut_on": "2026-09-14",
            "services": {"electric": disconnects.TREATMENT_FULL},
        },
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["code"] == errors.BIZ_COMPLETENESS
    assert refused.data["message_key"] == "customers.disconnects.refused"
    detail = _detail(refused)
    assert "no open disconnect case" in detail.lower(), detail
    assert refused.data["params"]["code"] == "no_open_case"


def test_a_disconnect_rule_refusal_is_never_an_unhandled_500(brazos, marcus):
    """`DisconnectRuleError` is NOT a catalog exception.

    Its own docstring names this boundary as the place it becomes one. Without
    the translation every ladder refusal is an unhandled exception and a clerk
    meets the rule as a stack trace.
    """
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    advanced = _ladder_call(
        doors.advance_disconnect_case, brazos, actor=marcus, account_id=str(account.id)
    )
    assert advanced.status_code == 422, advanced.data
    assert advanced.data["message_key"] == "customers.disconnects.refused"
    assert _detail(advanced), "the service's own sentence did not reach the wire"

    cut = _ladder_call(
        doors.commit_cut,
        brazos,
        actor=marcus,
        data={"cut_on": "2026-09-14"},
        account_id=str(account.id),
    )
    assert cut.status_code == 422, cut.data
    assert _detail(cut), "the service's own sentence did not reach the wire"


def test_an_open_case_can_be_started_and_read_back_through_the_doors(
    brazos, marcus, monkeypatch
):
    """`open_case` → `GET /accounts/{id}/ladder`. Two doors, one case.

    The ladder read carries the case, which is what makes the eleven acts
    findable at all: before this lane there was no way to learn a case id.
    """
    # B18 §5.8.6 — Bramble Bakery owes $2,410.00. The figure reaches the ladder
    # through the AR seam (`_balance_for`), NOT through `accounts.balance`: an
    # unreadable AR position stops the ladder and is never read as zero.
    _owes(monkeypatch, D("2410.00"))
    _customer, account, _unit_from = _make_mover(marcus, brazos, arrear=D("2410.00"))
    opened = _ladder_call(
        doors.open_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-14"},
        account_id=str(account.id),
    )
    assert opened.status_code == 200
    assert opened.data["account_id"] == str(account.id)

    read = _ladder_call(
        doors.account_ladder,
        brazos,
        actor=marcus,
        method="get",
        account_id=str(account.id),
    )
    assert read.status_code == 200
    assert read.data["case"] is not None
    assert read.data["case"]["case_id"] == opened.data["case_id"]
    # DEF-320 — nothing advances itself, and the payload says so on every read.
    assert read.data["scheduler"]["advances_on_a_schedule"] is False


def test_the_ladder_payload_carries_the_case_number_at_the_top_level(
    brazos, marcus, monkeypatch
):
    """`DEF-CUS-6052` — **the reference a clerk quotes, where a screen reads it.**

    `DSC-02.1` draws a `Case reference` row. The ladder payload carried the
    number only INSIDE `case`, which `disconnect_reads.list_row` already
    documents as *"an opaque record that no screen reads a field from"* — so
    the row was bound to `sequence` instead and printed the word **service**
    over a real `DSC-26-…` case. Both sides are strings, so `tsc`, eslint and
    every unit test passed over it.

    Two assertions, and the second is the one that could not be made before:

      1. `case_no` is at the TOP LEVEL and equals the case's own reference.
      2. It is the HUMAN reference and **not** `case_id` — B14 rule 31, no
         database id is ever the visible value of a field. A fixture whose
         value would read like a case number either way cannot fail, so this
         asserts the shape (`DSC-`…) AND that it is not the uuid.

    With no open case the payload answers `case_no: None` and states the
    absence once, as `case: None` — never a list-flavoured sentence about a
    protection being in force.
    """
    _owes(monkeypatch, D("2410.00"))
    _customer, account, _unit_from = _make_mover(marcus, brazos, arrear=D("2410.00"))

    before = _ladder_call(
        doors.account_ladder, brazos, actor=marcus, method="get", account_id=str(account.id)
    )
    assert before.status_code == 200
    assert before.data["case"] is None
    assert before.data["case_no"] is None
    assert before.data["case_no_unavailable"] is None

    opened = _ladder_call(
        doors.open_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-14"},
        account_id=str(account.id),
    )
    assert opened.status_code == 200

    read = _ladder_call(
        doors.account_ladder, brazos, actor=marcus, method="get", account_id=str(account.id)
    )
    assert read.status_code == 200
    case_no = read.data["case_no"]
    assert case_no == read.data["case"]["case_no"], "two spellings of one reference"
    assert case_no and case_no.startswith("DSC-"), case_no
    assert case_no != read.data["case"]["case_id"], "B14 rule 31 — that is a uuid"
    assert read.data["case_no_unavailable"] is None
    # And it is NOT the ladder's sequence, which is what the wizard was reading.
    assert case_no != read.data["sequence"]


def test_opening_a_case_twice_returns_the_same_case_rather_than_a_second(
    brazos, marcus, monkeypatch
):
    """An ordinary double-click. `uq_one_open_disconnect_case_per_account`
    already makes a second impossible; the door must not turn that into a 500."""
    # B18 §5.8.6 — Bramble Bakery owes $2,410.00. The figure reaches the ladder
    # through the AR seam (`_balance_for`), NOT through `accounts.balance`: an
    # unreadable AR position stops the ladder and is never read as zero.
    _owes(monkeypatch, D("2410.00"))
    _customer, account, _unit_from = _make_mover(marcus, brazos, arrear=D("2410.00"))
    first = _ladder_call(
        doors.open_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-14"},
        account_id=str(account.id),
    ).data
    second = _ladder_call(
        doors.open_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-14"},
        account_id=str(account.id),
    ).data
    assert first["case_id"] == second["case_id"]


def test_a_protection_is_recorded_and_read_back_on_the_same_resource(brazos, marcus):
    """GET and POST on `accounts/{id}/protections` — two verbs, one view.

    **This is the bug G52 caught in this lane's own code**: the POST was
    documented as mounted and was missing, because two views had been given one
    path. One two-verb view is the fix, and this asserts both halves work.
    """
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    created = _ladder_call(
        doors.account_protections,
        brazos,
        actor=marcus,
        data={
            "kind": disconnects.PROTECTION_MEDICAL,
            "effective_from": "2026-08-14",
            "expires_on": "2026-11-14",
        },
        account_id=str(account.id),
    )
    assert created.status_code == 201, created.data

    checked = _ladder_call(
        doors.account_protections,
        brazos,
        actor=marcus,
        method="get",
        account_id=str(account.id),
    )
    assert checked.status_code == 200
    assert disconnects.PROTECTION_MEDICAL in checked.data["protections_in_force"]
    # The three-valued outcome is served intact — `unavailable` is NOT `pass`.
    assert {row["outcome"] for row in checked.data["checks"]} <= {
        "pass",
        "fail",
        "unavailable",
    }


def test_a_protected_account_cannot_be_advanced_through_the_route(
    brazos, marcus, monkeypatch
):
    """The protection is the thing that stops a cut, and it stops it AT THE DOOR."""
    # B18 §5.8.6 — Bramble Bakery owes $2,410.00. The figure reaches the ladder
    # through the AR seam (`_balance_for`), NOT through `accounts.balance`: an
    # unreadable AR position stops the ladder and is never read as zero.
    _owes(monkeypatch, D("2410.00"))
    _customer, account, _unit_from = _make_mover(marcus, brazos, arrear=D("2410.00"))
    _ladder_call(
        doors.open_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-14"},
        account_id=str(account.id),
    )
    _ladder_call(
        doors.account_protections,
        brazos,
        actor=marcus,
        data={
            "kind": disconnects.PROTECTION_MEDICAL,
            "effective_from": "2026-08-14",
            "expires_on": "2026-11-14",
        },
        account_id=str(account.id),
    )
    refused = _ladder_call(
        doors.advance_disconnect_case,
        brazos,
        actor=marcus,
        data={"as_of": "2026-08-20"},
        account_id=str(account.id),
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["code"] == errors.BIZ_COMPLETENESS
    assert "protect" in _detail(refused).lower(), _detail(refused)


def test_a_date_that_records_an_act_is_never_defaulted_to_the_server_clock(
    brazos, marcus
):
    """Hard rule 7. `on_date`, `served_on` and `cut_on` are the caller's.

    An act dated by the server is an act whose real date nobody can
    reconstruct — and every one of these is evidence in a dispute about somebody
    losing supply.
    """
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    for view, kwargs in (
        (doors.stop_by_hand, {"account_id": str(account.id)}),
        (doors.mark_reconnecting, {"account_id": str(account.id)}),
        (doors.restore_service, {"account_id": str(account.id)}),
        (doors.commit_cut, {"account_id": str(account.id)}),
    ):
        missing = _ladder_call(view, brazos, actor=marcus, data={"reason": "x"}, **kwargs)
        assert missing.status_code == 422, (view.__name__, missing.data)
        assert missing.data["code"] == errors.VAL_REQUIRED, (view.__name__, missing.data)
        assert missing.data["message_key"] == "customers.date_required"


def test_the_reconnection_fee_reaches_the_wire_absent_rather_than_as_a_number(
    brazos, marcus
):
    """`BR-BIL-007` — a door that cannot price must send the fee ABSENT rather
    than substituting a literal, because a quoted price the product cannot
    charge is worse than an honest blank.

    ⚠ **THIS CASE'S PREMISE CHANGED UNDER IT ON 2026-09-21 AND THE CASE DID
    NOT.** It read *"no seed in this repo creates `CC-RECON`, so on every tenant
    here the fee genuinely IS absent"* — true when written, and made false by the
    PO's ruling *"reconnection fee is $75 - fix the code and seed"*, which seeded
    `RECON` at `$75.00`. **Left as it was, this would have become a check that
    could never pass** (hard-won law 7's third shape), and the tempting repair —
    deleting it — would have thrown away a real guard.

    **So the absence is now MADE rather than assumed, and its mirror is asserted
    beside it.** Nothing previously checked that a CONFIGURED fee reaches the
    wire as the TENANT's own number, which is the half that matters now that
    every tenant has one.
    """
    from apps.rating import models as rating_models

    _customer, account, _unit_from = _make_mover(marcus, brazos)

    # ── the absence, made rather than assumed ────────────────────────────
    # ⚠ **INSIDE `tenant_ctx`, AND THE FIRST DRAFT WAS NOT.** `charges` is under
    # RLS FORCE, so this delete outside a tenant context matched ZERO rows,
    # removed nothing, and SAID NOTHING — the case then failed on the fee being
    # present, which reads as the product being wrong rather than the fixture.
    # That is `DEF-BIL-5382`'s shape in a test instead of a migration.
    with tenant_ctx(brazos):
        rating_models.Charge.objects.filter(
            code=disconnects.RECONNECT_CHARGE_CODE
        ).delete()
    terms = _ladder_call(
        doors.account_reconnection_terms,
        brazos,
        actor=marcus,
        method="get",
        account_id=str(account.id),
    ).data
    # ⊕ `OQ-CUS-12518` CLOSED 2026-09-21 — was `"CC-RECON"`, which resolved on
    # no tenant. The constant, not the literal, for the reason above.
    assert terms["charge_code"] == disconnects.RECONNECT_CHARGE_CODE
    # DEF-2131 — `fee` is null AS A WHOLE FIELD, not a pair of null halves. The
    # client typed it `WorklistMoney` (a non-optional object) while its own
    # prose said "fee IS NULLABLE"; the type now carries what the prose claimed.
    assert terms["fee"] is None, terms["fee"]
    assert terms["fee_absence"] is not None
    # …and the reason is a SENTENCE, so a screen can say why rather than dash.
    assert terms["fee_absence"].get("code")

    # ── THE MIRROR, WHICH NOTHING ASSERTED BEFORE ────────────────────────
    # ⚠ **`BR-BIL-007` BOTH WAYS:** the fee is the TENANT's row, so a door that
    # can price must carry THEIR number — not a literal, and not the `75.0000`
    # the PO signed, which is what we SEED and never what we charge. Priced
    # deliberately at a figure that is neither, so a hardcoded default of
    # either would fail here.
    with tenant_ctx(brazos):
        rating_models.Charge.objects.create(
            tenant_id=brazos.id,
            code=disconnects.RECONNECT_CHARGE_CODE,
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("61.5000"),
        )
    priced = _ladder_call(
        doors.account_reconnection_terms,
        brazos,
        actor=marcus,
        method="get",
        account_id=str(account.id),
    ).data
    assert priced["fee"] is not None, "a configured fee must reach the wire"
    assert priced["fee_absence"] is None
    assert Decimal(str(priced["fee"]["stored"])) == Decimal("61.5000"), (
        "the wire carried something other than the tenant's own amount"
    )


def test_an_executive_cannot_act_on_the_ladder(brazos, marcus):
    """BR-SHL-025 — every write on this file is Admin-or-Clerk."""
    for view, kwargs in (
        (doors.schedule_cut, {}),
        (doors.open_disconnect_case, {"account_id": "A-1"}),
        (doors.commit_cut, {"account_id": "A-1"}),
    ):
        refused = _ladder_call(view, brazos, actor=marcus, role="executive", **kwargs)
        assert refused.status_code == 403, (view.__name__, refused.data)


# ══════════════════════════════════════════════════════════════════════════
# 4 · TENANT ISOLATION AT THE DOOR (HR-1)
# ══════════════════════════════════════════════════════════════════════════


def test_a_cross_tenant_account_is_404_and_never_403(brazos, marcus, lonestar, erin):
    """HR-1 — existence must not leak. Asserted on the reads, which are the
    ones a probe would use to enumerate another utility's customers."""
    _customer, account, _unit_from = _make_mover(marcus, brazos)
    for view in (doors.account_ladder, doors.account_protections, doors.account_reconnection_terms):
        probed = api_call(
            view,
            "get",
            user=erin.user,
            role="system_admin",
            tenant=lonestar,
            account_id=str(account.id),
        )
        # **DEF-2130.** Before the fix this answered 200 with `runs: false` and
        # `halt_code: nothing_owed` — a computed answer about a row this tenant
        # cannot see. 404 is the posture: never 403 (existence must not leak),
        # and never 200 (an answer about a foreign row is still an answer).
        assert probed.status_code == 404, (view.__name__, probed.status_code, probed.data)
