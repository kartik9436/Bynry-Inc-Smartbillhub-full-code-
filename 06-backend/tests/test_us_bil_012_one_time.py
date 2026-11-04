# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the ad-hoc single bill, and this tab's own shape) ·
#           US-BIL-010 (first bill) · US-BIL-011 (final bill) · US-BIL-013
#           (back-bill) · US-BIL-014 (penalty/theft)   Screens: S30 · S31
# Rules:    BR-BIL-020 (free-typed amounts never exist on any bill) ·
#           BR-BIL-023 (computed amounts are NEVER hand-editable) ·
#           BR-BIL-005 (a run is idempotent; a repeat names who/when/link) ·
#           BR-BIL-018 (a back-bill is reason-coded and priced per sub-period) ·
#           BR-BIL-024 (the due date comes from the CYCLE's due-days — OQ-241) ·
#           B4.3 ❄️ (the proration denominator — OQ-242) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money) · rule 7 (audit on money actions)
# ───────────────────────────────────────────────────────
"""The door to the five one-time engines, and the two guarantees it must keep.

Every assertion here was driven RED before it was trusted (hard-won law 7). The
verbatim failures are in the lane report; the two that matter most:

  * `tc4` (no free-typed amounts) failed with
    `AssertionError: one_time.OneTimeRequest accepts 'amount'` when a member
    named `amount` was added to the dataclass — so the guard bites on the shape
    of the code and not on a message.
  * `tc2` (idempotency) failed with `Failed: DID NOT RAISE
    apps.billing.runs.DuplicateRun` when `one_time_run_key` was made to drop the
    bill_type segment — proving the key, not just the unique index.
"""

import inspect
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models, one_time, runs
from apps.billing.exceptions import BillingRuleError
from core import idempotency
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

INTERIM_START = date(2026, 6, 15)
INTERIM_END = date(2026, 6, 30)

#: Parameter and member names that would let a caller put money on a bill by
#: hand. BR-BIL-020 forbids the CONCEPT, not a particular spelling, so the guard
#: is over a set of names an API layer would plausibly bind a request body to.
#: `single.py`'s own tc4 uses the identical set one layer down.
FREE_TYPED = {
    "amount",
    "amounts",
    "line_amount",
    "line_amounts",
    "price",
    "total",
    "totals",
    "lines",
    "description",
    "descriptions",
}


def a_one_time_account(brazos, dana, *, account_no="A-90001", asset_no="M-9501", label="Z"):
    """One billable account on a priced plan with a committed read."""
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=asset_no, label=label)
    return an_account(brazos, unit["id"], account_no)


# ── the run row that could not exist before migration 0021 ──────────────────


def test_us_bil_012_tc7__a_one_time_run_is_lawful_without_a_cycle(brazos, dana):
    """The whole blockage, closed: a `bill_runs` row with NO cycle.

    `single.py` reported it in its own trailer — *"`bill_runs.cycle_id` is NOT
    NULL, so an ad-hoc run has no lawful row yet"* — and every one of the five
    engines requires a run row, so five complete engines had no door.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana)
        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )
        run.refresh_from_db()
        assert run.cycle_id is None, "a one-time bill belongs to no cycle"
        # r10 #7's single-account SCOPE, which had no column at all.
        assert str(run.scope_account_id) == str(account.id)
        assert run.status == "draft"


def test_us_bil_012_tc8__a_run_scoped_to_neither_a_cycle_nor_an_account_is_refused(brazos):
    """`ck_bill_runs_has_a_scope` — the database refuses a scopeless run.

    Making `cycle_id` nullable created a state that has never been legal: a run
    naming no population at all. The guard is in POSTGRES rather than in
    `one_time.py`, because `one_time.py` is not the only writer this table has —
    `runs.create_run` and `pending.create_catch_up_run` write it too, and a
    guarantee that lives in one function lasts until somebody writes a second.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            billing_models.BillRun.objects.create(
                tenant=brazos,
                cycle=None,
                scope_account=None,
                period_start=INTERIM_START,
                period_end=INTERIM_END,
                idempotency_key="scopeless-run",
            )


def test_us_bil_012_tc2__a_repeated_one_time_bill_is_refused_by_name(brazos, dana):
    """BR-BIL-005 at one-time granularity, and it matters most on a move-out.

    A double-clicked *Create bill* would otherwise produce TWO final bills for
    one tenancy — and a final bill is the one nobody looks at again.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana)
        first = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )
        with pytest.raises(runs.DuplicateRun) as refused:
            one_time.create_one_time_run(
                account_id=account.id,
                bill_type="cycle",
                period_start=INTERIM_START,
                period_end=INTERIM_END,
            )
        # The refusal carries the ORIGINAL, which is what the screen links to.
        assert str(refused.value.original.pk) == str(first.pk)


def test_us_bil_012_tc9__the_kind_is_in_the_key_so_three_bills_do_not_block_each_other(
    brazos, dana
):
    """A final bill must not be refused as a duplicate of a back-bill.

    One account, one window, three legitimate documents about three different
    facts: a FINAL bill for the closing period, a BACK-BILL for an unbilled
    span that overlaps it (BR-BIL-018 — an arbitrary past period), and a
    PENALTY bill for theft found in it (BR-BIL-019). Keying without the kind
    would let the first block the other two, and the clerk would be told their
    theft bill was a duplicate of a final bill.
    """
    keys = {
        idempotency.one_time_run_key(
            account_id="018f-aaaa",
            bill_type=bill_type,
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )
        for bill_type in ("final", "backbill", "penalty")
    }
    assert len(keys) == 3, "the bill type must separate the three keys"
    # And a one-time key can never collide with a cycle run's or a catch-up's:
    # each family leads with something the others cannot produce.
    cycle_key = idempotency.bill_run_key(
        cycle_id="018f-cccc", period_start=INTERIM_START, period_end=INTERIM_END
    )
    assert not cycle_key.startswith(idempotency.ONE_TIME_MARKER)
    assert all(key.startswith(idempotency.ONE_TIME_MARKER) for key in keys)


def test_us_bil_012_tc10__a_one_time_key_needs_its_kind(brazos):
    """The key refuses to be composed short rather than colliding silently."""
    with pytest.raises(idempotency.IdempotencyKeyError):
        idempotency.one_time_run_key(
            account_id="018f-aaaa",
            bill_type="",
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )
    with pytest.raises(idempotency.IdempotencyKeyError):
        idempotency.one_time_run_key(
            account_id=None,
            bill_type="final",
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )


# ── BR-BIL-020: the prototype's line editor does not exist here ─────────────


def test_us_bil_012_tc4__nothing_in_the_one_time_door_can_carry_a_typed_amount(brazos):
    """BR-BIL-020, enforced STRUCTURALLY and asserted by introspection.

    The prototype's step 2 (`05-prototype/UtilityBilling.html:3394-3400`)
    renders every line as an editable description input and an editable amount
    input, with a *+ Add line* button beneath. BR-BIL-020 supersedes it in
    writing: *"lines come ONLY from rules and charge codes — free-typed amounts
    never exist on any bill"*.

    This asserts the SHAPE of the module rather than a rejection message,
    because a rejection can be deleted by a refactor and a parameter that does
    not exist cannot be passed. `single.py`'s tc4 does the same one layer down;
    this is the layer an HTTP request body actually binds to.
    """
    members = set(one_time.OneTimeRequest.__dataclass_fields__)
    leaked = members & FREE_TYPED
    assert not leaked, f"one_time.OneTimeRequest accepts {sorted(leaked)}"

    for name, function in inspect.getmembers(one_time, inspect.isfunction):
        if function.__module__ != one_time.__name__:
            continue
        params = set(inspect.signature(function).parameters)
        leaked = params & FREE_TYPED
        assert not leaked, f"one_time.{name} accepts {sorted(leaked)}"


def test_us_bil_012_tc11__the_deposit_invoice_kind_is_not_offered(brazos):
    """Hard-won law 8 — the prototype's fourth kind has no story, so no code.

    It is not silently dropped either: the tab NAMES it as unbuilt, so a clerk
    looking for it learns why rather than concluding the product forgot.
    """
    assert "deposit" not in one_time.ONE_TIME_KINDS
    codes = {row["code"] for row in one_time.ONE_TIME_UNAVAILABLE}
    assert "deposit_invoice_kind_has_no_story" in codes


def test_us_bil_012_tc12__an_unknown_kind_is_refused_and_never_defaulted(brazos):
    """A clerk who asked for a FINAL bill must never silently get an interim one.

    That customer's account closes with an unsettled deposit and nobody
    watching it — which is the failure BR-BIL-013's whole settlement matrix
    exists to prevent.
    """
    for bad in ("", None, "deposit", "Final ", "cycle"):
        with pytest.raises(BillingRuleError):
            one_time.checked_kind(bad)
    assert one_time.checked_kind("final") == "final"


# ── BR-BIL-018: a catch-up takes SUB-PERIODS and never invents a cadence ────


def test_us_bil_012_tc13__a_back_bill_refuses_one_span_and_demands_its_periods(brazos):
    """`backbill.py` will not invent a cadence, and this door will not either.

    The money: 18 kgal of water priced as ONE period puts 13 kgal in the top
    tier (104.50) where six monthly groups put 6 (79.50) — **$25.00** on one
    service on one bill, with the bill footing either way.
    """
    request = one_time.OneTimeRequest(
        account_id="018f-aaaa",
        kind=one_time.KIND_BACKBILL,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 6, 30),
        reason_code="MISSED",
    )
    with pytest.raises(BillingRuleError) as refused:
        one_time.checked_window(request)
    assert "sub-period" in str(refused.value).lower()

    # With the periods stated, the window is DERIVED from them — one source, so
    # the run row and the groups can never disagree about what was billed.
    stated = one_time.OneTimeRequest(
        account_id="018f-aaaa",
        kind=one_time.KIND_BACKBILL,
        sub_periods=(
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ),
        reason_code="MISSED",
    )
    assert one_time.checked_window(stated) == (date(2026, 1, 1), date(2026, 2, 28))


def test_us_bil_012_tc14__a_back_bill_without_a_reason_code_is_refused(brazos):
    """BR-BIL-018 *"reason-coded"*, checked before anything is written.

    Charging a customer for a period they were never billed for is a decision
    somebody made for a reason, and the bill is the only place it survives.
    """
    request = one_time.OneTimeRequest(
        account_id="018f-aaaa",
        kind=one_time.KIND_BACKBILL,
        sub_periods=((date(2026, 1, 1), date(2026, 1, 31)),),
        reason_code="   ",
    )
    with pytest.raises(BillingRuleError) as refused:
        one_time.checked_reason_code(request)
    assert "reason code" in str(refused.value)

    # An interim bill needs none — it is not recovering an unbilled period.
    interim = one_time.OneTimeRequest(
        account_id="018f-aaaa",
        kind=one_time.KIND_INTERIM,
        period_start=INTERIM_START,
        period_end=INTERIM_END,
    )
    assert one_time.checked_reason_code(interim) == ""


# ── the two open questions, asserted so nobody closes them by accident ──────


def test_us_bil_012_tc15__the_money_gaps_are_declared_and_both_questions_are_answered(brazos):
    """⚠ **AMENDED 2026-08-23 — CR-029 D8③ and D8④ answered both questions**,
    and this case was written so that whoever closed them had to come here and
    say which way (*"a later lane which closes either question has to delete the
    row deliberately"*). Deliberately, then:

      * **OQ-241 — CLOSED, RULED.** A one-time bill could not be ISSUED because
        BR-BIL-024 takes the due date from *the cycle's* due-days and a one-time
        run has no cycle. PO, verbatim: *"it will be capture at the time of bulk
        billing - not here"*. The RUN now carries `bill_date` + `due_days`, so
        the limit is gone and its row is REMOVED — a stated absence that is no
        longer true is worse than none (hard-won law 1). With no typed terms the
        derivation still refuses by name; nothing is guessed.
      * **OQ-242 — WITHDRAWN, NOT ANSWERED.** A PARTIAL one-time window still
        charges a full period's base charge, because B4.3's denominator has no
        source on a cycle-less run. PO, verbatim: *"this is not required"*. So
        the row STAYS with its figures — on WE-6's own numbers **$24.51**
        against **$38.00**, the customer paying **$13.49** too much — and what
        changes is that it no longer promises a ruling. No proration rule may be
        added without a new one.
    """
    codes = {row["code"] for row in one_time.ONE_TIME_UNAVAILABLE}
    assert "one_time_bill_cannot_be_issued_yet" not in codes
    assert "partial_window_charges_a_full_base_charge" in codes

    by_code = {row["code"]: row for row in one_time.ONE_TIME_UNAVAILABLE}
    partial = by_code["partial_window_charges_a_full_base_charge"]
    assert "D8④" in partial["br_ref"] and "WITHDRAWN" in partial["br_ref"]
    # The figure is IN the sentence a clerk reads, not only in a docstring.
    assert "13.49" in partial["detail"]


def test_us_bil_012_tc16__every_kind_maps_to_a_lawful_bill_type(brazos):
    """r10 #12's enum is the whole vocabulary; a kind cannot invent a sixth.

    `interim` maps to `cycle` deliberately — an interim bill is an ordinary
    bill over an unusual window and nothing about its LINES differs, so typing
    it otherwise would mislabel a document kept for seven years.
    """
    assert set(one_time.BILL_TYPE_BY_KIND) == set(one_time.ONE_TIME_KINDS)
    for kind, bill_type in one_time.BILL_TYPE_BY_KIND.items():
        assert bill_type in billing_models.BILL_TYPES, f"{kind} → {bill_type}"
    assert one_time.BILL_TYPE_BY_KIND[one_time.KIND_INTERIM] == "cycle"


# ── the bill itself, end to end through the real engines ───────────────────


def test_us_bil_012_tc1__an_interim_bill_drafts_through_the_real_pipeline(brazos, dana):
    """The whole door, exercised: request → run row → ONE draft with money on it.

    Nothing here re-prices anything. The figure comes from
    `runs.calculate_account` — the same seven stages a cycle run uses on the
    same signed rules — which is the property that stops a tenant discovering
    their interim bills round differently from their cycle bills.
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-90010", asset_no="M-9510")
        body = one_time.create(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
            ),
            run_by=dana,
            actor=dana,
        )
        assert body["kind"] == one_time.KIND_INTERIM
        assert body["bill_type"] == "cycle"
        assert body["status"] == "draft"
        # CLAUDE.md rule 2 — a figure never travels without its currency.
        assert body["currency"]
        invoice = billing_models.Invoice.objects.get(pk=body["invoice_id"])
        assert str(invoice.account_id) == str(account.id)
        # The run row it hangs off is the one this lane made lawful.
        assert invoice.bill_run.cycle_id is None
        assert str(invoice.bill_run.scope_account_id) == str(account.id)


def test_us_bil_012_tc3__the_preview_writes_nothing(brazos, dana):
    """BR-BIL-020's *"preview → …"*: looking must never be a committing action.

    Counted rather than asserted about, because "writes nothing" is a claim
    about the DATABASE and a docstring saying so is not the guarantee (law 1).
    """
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-90020", asset_no="M-9520")
        before_runs = billing_models.BillRun.objects.count()
        before_invoices = billing_models.Invoice.objects.count()

        body = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
            )
        )
        assert body["ready"] == 1
        # ⚠ **THIS ASSERTED `"total" not in body` UNTIL `CR-108` WAVE 1, AND IT
        # PINNED THE WRONG HALF OF ITS OWN REASON.** The comment beside it read
        # *"a prepare pass prices nothing, and a zero standing in for 'not
        # computed' is a money claim on a bill preview"* — the second clause is
        # the RULE and the first was a fact about the code, and the assertion
        # was written against the fact. The preview now runs
        # `runs.price_account`, the run's OWN stages 1–5, extracted by `CR-075`
        # wave F precisely so a figure could be shown without a draft; the total
        # it serves IS the engine's. Amended rather than deleted, because a
        # green fixture pinning behaviour the product has moved past is worse
        # than no fixture (`DEF-705`).
        #
        # **The rule it was protecting is asserted directly instead:** a preview
        # that cannot price serves NO total at all — never `0.00`, which on a
        # bill preview is the claim that this customer owes nothing.
        assert body["priced"] is True, body.get("priced_unavailable")
        assert "total" in body and Decimal(body["total"]) > 0
        refused = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_FEE,
                charge_code="NO-SUCH-CODE-TC3",
                bill_date=PERIOD_END,
            )
        )
        assert refused["priced"] is False and "total" not in refused

        # "Writes nothing" is a claim about the DATABASE, so it is COUNTED — and
        # now counted after PRICING, which is the interesting case.
        assert billing_models.BillRun.objects.count() == before_runs
        assert billing_models.Invoice.objects.count() == before_invoices


def test_us_bil_012_tc5__a_drafted_one_time_bill_writes_an_audit_row(brazos, dana):
    """CLAUDE.md rule 7 — every money action writes `audit_log`.

    TWO rows, and they record different acts: `bill_run.created` (who is billed
    for what window under which rules) and `invoice.drafted` (the figure that
    now exists against a named customer).

    The rows are captured at the SINK rather than read back from `audit_log`,
    because the tier's shared fixtures already replace the sink with a capture
    list — reading the table would assert the fixture's wiring instead of this
    module's writes.
    """
    from core import audit as audit_kernel

    captured: list[dict] = []
    previous = audit_kernel._sink
    audit_kernel.set_audit_sink(captured.append)
    try:
        with tenant_ctx(brazos):
            account = a_one_time_account(brazos, dana, account_no="A-90030", asset_no="M-9530")
            body = one_time.create(
                one_time.OneTimeRequest(
                    account_id=str(account.id),
                    kind=one_time.KIND_INTERIM,
                    period_start=PERIOD_START,
                    period_end=PERIOD_END,
                ),
                run_by=dana,
                actor=dana,
            )
    finally:
        audit_kernel.set_audit_sink(previous)

    actions = [row["action"] for row in captured]
    assert "bill_run.created" in actions
    assert "invoice.drafted" in actions

    drafted = next(row for row in captured if row["action"] == "invoice.drafted")
    assert drafted["entity_id"] == str(body["invoice_id"])
    # CLAUDE.md rule 2 — the trail carries the CURRENCY beside the figure. A
    # money amount with no currency is a number with no name.
    assert drafted["after"]["currency"]
    assert drafted["after"]["total"]
    assert drafted["after"]["one_time_kind"] == one_time.KIND_INTERIM

    run_row = next(row for row in captured if row["action"] == "bill_run.created")
    # The run's trail names WHO was billed — the fact `scope_account_id` exists
    # to record, and the one an inference from the invoice could not give when
    # a run produces no invoice at all.
    assert run_row["after"]["scope_account_id"] == str(account.id)
    assert run_row["after"]["cycle_id"] is None


def test_us_bil_012_tc6__a_one_time_run_is_not_a_cycle_run_and_says_so(brazos, dana):
    """`GET /billing/runs/{id}/findings` on a one-time run refuses by name.

    `prepare_run` scopes on `units_in_cycle`, so asking it for the units of
    cycle NULL would return an EMPTY run rather than an error — a findings
    screen reading "0 accounts ready" for a bill that is really about one named
    customer. That is worse than a refusal, so it refuses.
    """
    from apps.billing import selectors
    from core import errors

    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-90040", asset_no="M-9540")
        run = one_time.create_one_time_run(
            account_id=account.id,
            bill_type="cycle",
            period_start=INTERIM_START,
            period_end=INTERIM_END,
        )
        with pytest.raises(errors.BizError):
            selectors.prepared_for(run)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-012@f0a3c21 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md)
# generated: 2026-08-16 by Eng-Lead (S30 One-time bill tab lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every assertion RED-proved first; verbatim failures in the lane report
# exceptions: (1) NO GOLDEN FIGURE IS ASSERTED HERE. WE-6 (first bill, 287.23),
#         WE-7 (final settlement, 153.50 → 11.20 / 135.90), WE-10 (back-bill,
#         305.18) and WE-11 (penalty, 626.42) are each asserted by the ENGINE's
#         own test file, which is where they belong: this module adds no
#         arithmetic, so a figure re-asserted here would prove the fixture and
#         not the door. What IS asserted is that the door reaches the engine.
#         (2) `tc15` pins OQ-241 and OQ-242 to the screen deliberately, so a
#         later lane closing either has to delete the row on purpose rather
#         than letting a true warning quietly stop being shown (law 1).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
