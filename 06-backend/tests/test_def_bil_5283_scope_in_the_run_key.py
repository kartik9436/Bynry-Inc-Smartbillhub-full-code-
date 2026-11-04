# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5283 (high) — the bill-run idempotency key omits the scope,
#          so a Water-only September run CONSUMES September and the Sewer run
#          behind it is refused as a duplicate. No exclusion rows are written by
#          a refusal, so those accounts never enter the held queue and no
#          catch-up ever bills them: silent under-billing, and the clerk is told
#          "already run", which is true and useless.
# Rules:   BR-BIL-005 (CONFIRMED, PO A-6/r1.3) — *"Sub-run idempotency: key =
#          parent key + scope; the original run's key is never re-used;
#          mechanics 🔒 Eng-Lead"* (EP-BIL-01-bill-run.md:474, and the same
#          sentence in 07-pre-session-model.md, 09-po-input-sheet.md A-3 and
#          04-flows.md) · CLAUDE.md hard rule 6 (idempotency) · 🔒 idempotency
#          keys are a sensitive path
# Impacts: 06-backend/core/idempotency.py · apps/billing/runs.py (create_run) ·
#          apps/billing/selectors.py (scope_resolution's `committable`)
# ───────────────────────────────────────────────────────
"""The scope enters the run key — and an unnarrowed run's key does not move.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY, asked before trusting it
(hard-won law 7, and the reads lane was caught by exactly this shape a day
ago — its new invariant came back green with the bug deliberately restored,
because the fixture made two counts equal by accident).**

  1. **The no-scope test passing over a function that appends nothing at all.**
     Break the scoped branch entirely and `tc1` is still green. So `tc1` and
     `tc2` are a PAIR: the literal is pinned AND a scoped key is asserted to
     differ from it.
  2. **The order test passing because canonicalisation dropped everything.**
     `""` equals `""`. So `tc3` asserts the CANONICAL STRING, never just that
     the two orders agree.
  3. **The end-to-end test passing because the two runs differed in something
     else.** So `tc6` holds the cycle and the period byte-identical and varies
     ONLY the scope — and asserts the two stored keys differ AND that a repeat
     of the SAME scope is still refused, which is the protection the key exists
     to give.
  4. **`committable` passing because every kind returns True.** `tc8` asserts
     BOTH sides: a service narrowing is committable and a route is not.
"""

from datetime import date

import pytest

from apps.billing import models as billing_models, runs, selectors
from core import idempotency

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import a_cycle

pytestmark = pytest.mark.django_db

CYCLE = "018f6f6a-0000-7000-8000-000000000001"
SEP_START = date(2026, 9, 1)
SEP_END = date(2026, 9, 30)


def test_tc1__an_unnarrowed_run_is_keyed_EXACTLY_as_it_is_today():
    """⚠ **THE CONSTRAINT THAT DECIDES THE WHOLE DESIGN.**

    Every run on every tenant was keyed with three inputs. If the full-cycle
    key changed shape, every one of them would stop matching itself and the
    duplicate check would silently stop protecting the runs it was written for
    — a guard that fails OPEN, with no error anywhere to notice.

    The literal is pinned here so a later refactor that "tidies" the separator,
    or appends an empty scope segment unconditionally, goes RED.

    ⚠ **THIS CASE IS GREEN BEFORE AND AFTER THE FIX, AND THAT IS THE WHOLE
    POINT OF IT.** Every other case in this file is red on the pre-fix tip; a
    backwards-compatibility assertion that only starts passing once you change
    the thing is not testing compatibility with anything. Measured against tip
    `755f9769` with none of this change present: this one passes there too.
    """
    assert (
        idempotency.bill_run_key(cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END)
        == "018f6f6a-0000-7000-8000-000000000001|2026-09-01|2026-09-30"
    )


def test_tc2__a_service_scope_is_appended_and_differs_from_the_whole_cycle():
    """BR-BIL-005's *"key = parent key + scope"*, applied to a Scope narrowing.

    Paired with `tc1` deliberately — see this module's docstring, hazard 1.
    """
    whole = idempotency.bill_run_key(cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END)
    water = idempotency.bill_run_key(
        cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END, scope_services=["water"]
    )
    sewer = idempotency.bill_run_key(
        cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END, scope_services=["sewer"]
    )

    assert water == "018f6f6a-0000-7000-8000-000000000001|2026-09-01|2026-09-30|scope|water"
    # The three that must never be equal: the two scopes, and either against the
    # whole cycle. This IS the defect, in three assertions.
    assert water != sewer
    assert water != whole and sewer != whole


def test_tc3__one_scope_in_two_orders_is_ONE_key():
    """⚠ **THE BUG WITH ITS SIGN FLIPPED, AND WORSE.**

    Water+Sewer and Sewer+Water are one scope. Keyed as two, the same run is
    runnable twice — which double-bills where `DEF-BIL-5283` under-bills, and a
    double bill costs a credit note per customer to undo.

    The CANONICAL STRING is asserted, not merely that the two orders agree:
    a canonicalisation that dropped every code would make them agree on `""`
    (this module's docstring, hazard 2).
    """
    forwards = idempotency.bill_run_key(
        cycle_id=CYCLE,
        period_start=SEP_START,
        period_end=SEP_END,
        scope_services=["water", "sewer"],
    )
    backwards = idempotency.bill_run_key(
        cycle_id=CYCLE,
        period_start=SEP_START,
        period_end=SEP_END,
        scope_services=["sewer", "water"],
    )

    assert forwards == backwards
    assert forwards.endswith("|scope|sewer,water")


def test_tc4__the_scope_is_deduped_case_folded_and_blank_stripped():
    """One scope named three sloppy ways is one key.

    Case-folding is the deliberate half — see `bill_run_key`'s own docstring for
    why the trade lands on this side: two spellings of ONE code kept apart would
    double-bill, while two genuinely different codes folded together cannot
    arise on this product's data.
    """
    tidy = idempotency.bill_run_key(
        cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END, scope_services=["water"]
    )
    messy = idempotency.bill_run_key(
        cycle_id=CYCLE,
        period_start=SEP_START,
        period_end=SEP_END,
        scope_services=["Water", " water ", "water", ""],
    )

    assert messy == tidy


def test_tc5__an_empty_scope_is_a_narrowing_and_not_an_absence():
    """`[]` means *filter to no services* and `None` means *no narrowing*.

    The pipeline already draws that line — `_readings_for` passes
    `service_codes=[]` straight through — so folding the two together here
    would let a bill-nothing run consume the whole cycle's key and refuse the
    real run behind it, which is `DEF-BIL-5283` again by another door.
    """
    nothing = idempotency.bill_run_key(
        cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END, scope_services=[]
    )
    whole = idempotency.bill_run_key(cycle_id=CYCLE, period_start=SEP_START, period_end=SEP_END)

    assert nothing != whole
    assert nothing.endswith("|scope|")


def test_tc6__a_new_run_takes_no_service_scope_and_an_old_scoped_run_still_blocks_its_period(
    brazos, dana
):
    """⚠ SUPERSEDED 2026-09-30 (bulk bill run plan B3). This case read *"two
    scoped runs over one cycle and period BOTH bill"*. The PO then removed the
    services filter — *"which servcies to be billed in unit /account is decied
    at run time -so this filter is of now use"* — so a new run takes no scope at
    all and `create_run` refuses the keyword outright.

    What must NOT be lost is the protection: a September run stored BEFORE the
    ruling as Water-only keeps its `|scope|water` key, so a new whole-cycle
    September run has a DIFFERENT key the unique index cannot see. The Scope
    step's overlap refusal (BR-BIL-1050) is what stops that double bill, and it
    is asserted here beside the key so the two halves cannot drift apart.
    """
    from apps.billing import run_scope

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        with pytest.raises(TypeError):
            runs.create_run(  # type: ignore[call-arg]
                cycle_id=cycle.id,
                period_start=SEP_START,
                period_end=SEP_END,
                scope_services=["water"],
            )
        old_water = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=SEP_START,
            period_end=SEP_END,
            status="issued",
            scope_services=["water"],
            idempotency_key=idempotency.bill_run_key(
                cycle_id=cycle.id,
                period_start=SEP_START,
                period_end=SEP_END,
                scope_services=["water"],
            ),
        )
        whole = idempotency.bill_run_key(
            cycle_id=cycle.id, period_start=SEP_START, period_end=SEP_END
        )
        assert old_water.idempotency_key != whole
        result = run_scope.check_scope(
            cycle_id=str(cycle.id),
            period_start=SEP_START.isoformat(),
            period_end=SEP_END.isoformat(),
            label="September",
            template_id=None,
            with_counts=False,
        )
        overlap = [p for p in result.refusals if p.code == "period_overlap"]
        assert [p.params["run_id"] for p in overlap] == [str(old_water.pk)]


def test_tc7__an_unnarrowed_rerun_is_still_refused(brazos, dana):
    """The guarantee `DEF-BIL-5283`'s fix must not weaken.

    A key that carries a scope is worthless if the unnarrowed case stopped
    refusing — that would turn one silent under-bill into a silent DOUBLE bill
    for every ordinary run in the product.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        first = runs.create_run(
            cycle_id=cycle.id,
            period_start=SEP_START,
            period_end=SEP_END,
            run_by=dana.user,
        )
        with pytest.raises(runs.DuplicateRun) as refused:
            runs.create_run(
                cycle_id=cycle.id,
                period_start=SEP_START,
                period_end=SEP_END,
                run_by=dana.user,
            )
        assert refused.value.original.pk == first.pk
        # ⚠ AMENDED 2026-09-30 (plan B3): the second half — *"an unnarrowed run
        # does NOT block a scoped one"* — is gone with the services filter; a
        # new run cannot be scoped at all.


def test_tc8__a_service_scope_is_committable_and_a_route_is_not(brazos, dana):
    """⚠ **THE HALF-CLOSE, ASSERTED ON BOTH SIDES** (docstring hazard 4).

    A SERVICE narrowing is carried by the key now, so the scope card may call
    it committable. A ROUTE is not — and the reason is a COLUMN rather than a
    key: `bill_runs` persists nothing for a route, an area or a named set, so
    there is nothing for a key to carry. Flipping all four together would have
    re-opened the revenue hole for three of them while the one case anybody
    would test went on billing correctly.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        whole = selectors.scope_resolution(cycle_id=cycle.id)
        by_service = selectors.scope_resolution(cycle_id=cycle.id, scope_services=["water"])
        by_route = selectors.scope_resolution(
            cycle_id=cycle.id, kind=selectors.SCOPE_ROUTE, scope_ids=[str(cycle.id)]
        )

        assert whole["committable"] is True
        # ⚠ AMENDED 2026-09-30 (plan B3): a SERVICE narrowing is no longer
        # committable — `create_run` takes no services, so a card calling it
        # committable would promise a Water-only run and bill the whole cycle.
        assert by_service["committable"] is False
        assert by_route["committable"] is False
        # The refusal names the kinds that are still refused, not "any scope".
        codes = [entry["code"] for entry in by_route["unavailable"]]
        assert selectors.SCOPE_KEY_LIMIT in codes
        assert selectors.SCOPE_KEY_LIMIT not in [
            entry["code"] for entry in by_service["unavailable"]
        ]
