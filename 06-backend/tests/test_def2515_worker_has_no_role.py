# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (bulk account upload) · CR-047
# Defect:   DEF-2515 (critical) — an account import over 5,000 rows dies with an
#           AUTH error in *Insert & update* mode, because the deferred stage runs
#           in a worker that carries NO ROLE by design and
#           `customers.update_from_import` demanded one.
# Rules:    BR-MET-035 (the role gate on the import stages) · BR-MET-098 (the
#           approver bar) · BR-CUS-172 (the account number is the match key) ·
#           BR-SHL-025 (server-side enforcement IS the enforcement)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""DEF-2515 — the role is checked AT THE DOOR, never again in the worker.

⚠ **WHY THIS DEFECT ONLY EXISTS ABOVE 5,000 ROWS, AND WHY THAT IS THE WHOLE
ESCAPE.** `import_runs.ASYNC_ROW_BAR` is 5,000. At or below it the load runs on
the REQUEST, which carries a real actor with a real role, and every test in this
repository passes. Above it the stage is deferred and the worker carries
`import_runs._JobActor` — `__slots__ = ("id",)`, an id and **no role**, by
design and correctly so:

    "Role was checked at enqueue; the worker carries the actor id in the record,
     never a role, so it can grant nothing."

`apps/customers/services.update_from_import` then declared
`@require_role(SYSTEM_ADMIN, BILLING_CLERK)`. `core.permissions.require_role`
reads `getattr(actor, "role", None)`, gets `None`, and raises `AuthError`
AUTH-002 — its own docstring already says *"job callers get the same exception
and their runner records it."* Under the all-or-nothing transaction the whole
run then died with not one row written.

**The PO hit it on 9,000 accounts.** It fires only in *Insert & update* mode, on
rows matching an account already on file — which is what a CORRECTED RE-RUN
uses. So it hits hardest on the second attempt at a migration, after the
operator has already fixed their file.

⚠ **THE FIX IS A DELETION, AND THE ASYMMETRY IS THE EVIDENCE.** The import
door's own CREATOR, `create_from_import`, has never carried a decorator — it is
called by the same loader, from the same worker, for the same reason. Only the
UPDATER got one, copied from the hand-typed doors by `CR-046 C4`, and nobody
re-asked whether the worker could satisfy it. Of the backend's 220 role-guarded
functions, **exactly one** is reachable from the import load path, and it was
this one.

⚠ **THIS IS `DEF-1108` REPEATING IN A DIFFERENT FUNCTION.** That defect moved
the approver check out of the worker and its docstring says *"rebuilding a role
in the worker would be a second, weaker place for that decision to live."* A
second check in the worker is not defence in depth — it is a check that can only
ever produce a FALSE REFUSAL, because the worker is architecturally incapable of
carrying a role.

**So TC-2 is as load-bearing as TC-1.** Removing a role gate is only safe if the
door still holds, and this file proves both halves rather than asserting one.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from apps.customers import services as customers_services
from apps.metering import import_runs
from apps.metering import services as metering_services
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
    make_plan,
    make_premises,
    make_unit,
)

pytestmark = pytest.mark.django_db


def _plan(tenant):
    """The tenant's plan, built by the SHARED fixture helper.

    ⚠ **`DEF-2540` — THIS USED TO BUILD ITS OWN, AND IT HAD DRIFTED TWO WAYS AT
    ONCE.** It called `RatePlan.objects.create(..., service_code="electric")`,
    and `RatePlan` carries no `service_code` — a plan resolves to one rate
    schedule per service through `plan_rate_schedules`, so the field this
    helper passed had never been a column on that model. Every case in this
    file died in SETUP with `TypeError: RatePlan() got unexpected keyword
    arguments: 'service_code'`, which means **the assertion this file exists
    for has not run since the drift**: the file reported FAILED while saying
    nothing at all about the product.

    The second drift is the quieter one and would have bitten next: the local
    helper left `status` at its default `draft`, and `BR-RAT-030` makes only
    PUBLISHED plans assignable. Even with a valid field list, the plan it built
    could not have been assigned to a unit — a fixture failure that reads as an
    unrelated product bug.

    `make_plan` has neither problem: it publishes the plan and creates the
    per-service tariff and schedule rows a plan is meaningless without. A test
    that needs a plan should never build one by hand — that is how a fixture
    outlives the model it copies.
    """
    return make_plan(tenant, name="Residential Standard", code="RES-STD")


def _account_on_file(actor, tenant, *, account_no: str) -> dict[str, Any]:
    """One account, created through the SAME import door the worker uses."""
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=f"Unit {account_no}")
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return customers_services.create_from_import(
        actor=actor,
        payload={
            # ⚠ `customer_name` rides in `mapped`, NOT in `account`.
            # `IMPORT_ACCOUNT_FIELDS` is the allow-list for the ACCOUNT row, and
            # a customer's name is not an account fact — it reaches `customers`
            # through `link_customer` (BR-CUS-054: one landlord, one name,
            # fourteen accounts). Putting it in `account` earns
            # `VAL-002 customers.account.unknown_field`, which is the allow-list
            # working. `test_cr047_import_inheritance.py` builds its payload the
            # same way; this helper had simply drifted from it.
            "mapped": {"customer_name": "Alvarez, Maria"},
            "unit_id": str(unit["id"]),
            "account_no": account_no,
            "currency": "USD",
            # ⚠ A DATE IS REQUIRED, and the refusal that taught me is CR-047's
            # own new rule working (BR-CUS-672). An imported account now always
            # inherits its unit's services, and a service agreement needs a
            # `started_on`: the writer ranks `opened_at` -> a terminal row's
            # `closed_at` -> the run's cutover date, and REFUSES with
            # `customers.import.cutover_required` rather than reading a clock on
            # the caller's behalf (BR-TEN-043). A real S68 run always carries one
            # of the three; this helper carried none.
            "cutover_on": date(2026, 8, 31),
            "import_run_id": None,
            "account": {"account_type": "residential"},
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE RED ONE — the worker's own actor must be able to update a row
# ══════════════════════════════════════════════════════════════════════════
def test_def2515_tc1__the_workers_roleless_actor_can_update_an_account(brazos, dana):
    """DEF-2515. Build the EXACT actor the worker carries — not a mock, the
    real `_JobActor` class — and call the function a 9,000-row *Insert &
    update* run calls for every row already on file.

    RED before the fix:
        core.errors.AuthError: AUTH-002 (BR-MET-035)

    That is the PO's *"it gave us Auth error"*, reproduced in one call.
    """
    # ⚠ **THE TENANT CONTEXT IS NOT DECORATION — ITS ABSENCE COST AN HOUR.**
    # Without it `make_premises` raises `AuthError AUTH-003`
    # (AUTH_TENANT_UNRESOLVABLE, BR-TEN-003) from the test's own SETUP — a
    # different auth error from the one under test, in a different layer, for a
    # different reason. It reads as though the fix had failed. Two errors that
    # share the word "auth" and share nothing else (hard rule 1: never touch a
    # tenant table without `app.tenant_id` set — that applies to tests too).
    with tenant_ctx(brazos):
        on_file = _account_on_file(dana, brazos, account_no="A-9001")

        # ⚠ THE REAL CLASS, not a stand-in. A test that invents its own
        # role-less object proves something about the test; this proves
        # something about the worker (law 1 — the guarantee has to be the
        # thing itself).
        worker_actor = import_runs._JobActor(dana.id)
        assert getattr(worker_actor, "role", None) is None, (
            "the worker actor is supposed to carry NO role — if this ever gains "
            "one, the fix below is the wrong fix and DEF-2515 must be re-argued"
        )

        # ⚠ **`bad_address`, NOT `customer_name` — AND THE REFUSAL THAT TAUGHT
        # ME THAT IS THE RULE WORKING.** `IMPORT_UPDATE_FIELDS` deliberately
        # excludes every money field, `unit_id` (BR-CUS-017) and `account_no`
        # (the key we matched on), and it excludes the CUSTOMER's name too —
        # that fact lives on `customers`, not `accounts` (BR-CUS-054). Passing
        # it earned `VAL-002 customers.account.unknown_field`, which is the
        # allow-list refusing an unknown field exactly as it should. Pick a
        # field the import is actually allowed to correct.
        updated = customers_services.update_from_import(
            actor=worker_actor,
            account_no="A-9001",
            changes={"bad_address": True},
        )

        assert updated is not None
        assert str(updated["id"]) == str(on_file["id"])
        assert updated["account_no"] == "A-9001", "the match key must never be rewritten"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE HALF THAT MAKES TC-1 SAFE — the door still refuses
# ══════════════════════════════════════════════════════════════════════════
def test_def2515_tc2__the_stage_door_still_refuses_a_roleless_caller(brazos, dana):
    """Removing a guard is only lawful if the guard it duplicated still holds.

    `BR-MET-035` puts `@require_role` on `transform` / `validate` / `load` —
    the REQUEST that enqueues the stage — and `BR-MET-098` adds the approver
    check in the API layer. Those are the enforcement. This asserts the door is
    still shut, so a reader can see that TC-1 widened nothing.
    """
    with pytest.raises(errors.AuthError):
        import_runs.load(import_runs._JobActor(dana.id), "00000000-0000-0000-0000-000000000000", {})


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · the class, not the instance — nothing on the load path may demand one
# ══════════════════════════════════════════════════════════════════════════
def test_def2515_tc3__no_seam_the_loader_calls_demands_a_role():
    """⚠ **THE ONE THAT STOPS THIS RECURRING**, and it is the reason this file
    exists rather than a one-line diff.

    `DEF-2515` is `DEF-1108` in a different function: a decorator added later,
    to a function the worker calls, by someone who had no reason to think about
    workers. Measured when this was filed: of **220** role-guarded functions in
    the backend, exactly ONE was reachable from the import load path.

    So this walks the seam surface itself. The next lane that decorates a
    customers or assets import writer fails HERE, on the commit that does it,
    instead of in a utility's 9,000-account migration.
    """
    from apps.metering import seams

    offenders = []
    for name in ("create_account_from_import", "update_account_from_import",
                 "create_asset_from_import", "update_asset_from_import",
                 "confirm_opening_changeover", "post_account_opening_batch"):
        seam = getattr(seams, name, None)
        if seam is None:
            continue
        # The seam resolves its implementer by name at call time, so ask it for
        # the real callable rather than re-deriving the module path here.
        impl = _resolved_implementer(seams, name)
        if impl is None:
            continue  # unwired is a different defect (DEF-075's shape), not this one
        if getattr(impl, "__wrapped__", None) is not None and _is_role_guarded(impl):
            offenders.append(f"{impl.__module__}.{impl.__name__}")

    assert offenders == [], (
        "these functions are called by a DEFERRED import stage, and a deferred "
        "stage runs in a worker that carries no role — so a @require_role on any "
        "of them can only ever produce a false refusal (DEF-2515, DEF-1108): "
        f"{offenders}"
    )


def _resolved_implementer(seams: Any, seam_name: str) -> Any:
    """The real callable behind a seam, or None while it is unwired."""
    import inspect
    import re

    source = inspect.getsource(getattr(seams, seam_name))
    match = re.search(r'resolve\(\s*"(\w+)"\s*,\s*"(\w+)"(?:\s*,\s*kind="(\w+)")?', source)
    if match is None:
        return None
    module_name, func_name, kind = match.group(1), match.group(2), match.group(3) or "services"
    import importlib

    try:
        module = importlib.import_module(f"apps.{module_name}.{kind}")
    except ModuleNotFoundError:
        return None
    return getattr(module, func_name, None)


def _is_role_guarded(fn: Any) -> bool:
    """Does `require_role` wrap this callable?

    ⚠ **THE OBVIOUS IMPLEMENTATION IS A FALSE NEGATIVE, AND IT PASSED OVER THE
    LIVE DEFECT.** The first version of this read `inspect.getsource(fn)` and
    looked for the guard body — and it reported CLEAN on `update_from_import`
    while that function was demonstrably role-guarded and TC-1 was failing three
    lines above it. The reason is that `require_role` sets
    `guarded.__wrapped__ = fn`, and **`inspect.getsource` follows `__wrapped__`**
    — so it hands back the DECORATED function's source, never the wrapper's, and
    the guard is invisible to exactly the check written to find it.

    That is hard-won law 7 in miniature: a check whose output cannot distinguish
    pass from fail is worse than no check, because it is trusted. This one was
    caught only because TC-1 was RED in the same run and TC-3 was green — two
    tests disagreeing about one fact.

    `__code__` does NOT unwrap. `require_role`'s wrapper closes over
    `allowed_set`, so its free variables name the guard beyond doubt.
    """
    code = getattr(fn, "__code__", None)
    return code is not None and "allowed_set" in code.co_freevars
