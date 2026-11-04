# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections: scope selector, staged idempotent
#           execution, per-bill results)   Screens: S30
# Rules:    BR-BIL-014 (bulk scope by run/cycle/plan/service/date-range;
#           execution = staged background job with progress + per-bill results,
#           idempotent, resumable; same reason → preview → Admin approval →
#           deliver → audit chain) · BR-BIL-046 (the approved set is a PINNED
#           LIST of bills, never a stored query; up-movements and down-movements
#           are shown separately and never netted; warned rows and largest
#           absolute deltas sort first) · BR-BIL-047 (one bill = one transaction
#           = the atomicity unit; NO batch rollback exists; succeeded bills are
#           never reversed; the case stays open while any bill is unresolved) ·
#           BR-BIL-042 (one class per bulk case) · BR-BIL-048 (one open case per
#           chain) · BR-BIL-044 (approval binds the content-hashed artifact) ·
#           BR-BIL-004 (per bill, the mechanics are the single-case ones —
#           originals untouched; the story that ships those test cases is named
#           in the docstring, not here, because G10 reads a Trace US-ID as a
#           claim to ship that story's TCs) · BR-TEN-043 (event time is an argument) · CLAUDE.md
#           rule 1 · rule 2 · rule 4 · rule 6 · rule 7
# Tests:    06-backend/tests/test_us_bil_016_bulk_corrections.py ·
#           06-backend/tests/test_cr101_lane_b_scope_resolve.py (CR-101-BRC03
#           §06 — the step-1 scope table, `scope_table`) ·
#           06-backend/tests/test_cr101_lane_b_discount_panel.py (the batch
#           panel's discounts cell, `_discounts_summary`)
# Impacts:  apps/billing/corrections.py (the per-bill engine) ·
#           apps/billing/correction_models.py · apps/billing/document_correction.py
# ───────────────────────────────────────────────────────
"""Four hundred bills, one reviewed decision — and no undo button anywhere.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 idempotency keys and money movement at
batch scale. AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

The PO asked one question on 2026-08-11 — *"if bill correction is in bulk then
how do we handle it"* — and BR-BIL-046/047 are the answer. Four constraints make
a 240-row case reviewable rather than merely large, and each is a refusal
somewhere in this file:

**1 · THE APPROVED SET IS A LIST, NOT A QUERY.** The scope selector resolves
ONCE, at preview, into `correction_case_bills` rows. Execution iterates those
rows and never re-runs the predicate. A bill issued between approval and
execution does not silently join a set someone already signed off — it is
reported as unaddressed and needs its own case (TC-11).

**2 · THE AGGREGATE NEVER NETS OPPOSING MOVEMENTS.** *"100 bills up $50 and 100
bills down $50 net to $0.00 and are a disaster; a single Σ would hide it, so a
single Σ is not offered alone."* `AggregatePanel.as_dict` always carries the ↑
count and sum and the ↓ count and sum, and there is no accessor anywhere in this
module that returns the net by itself.

**3 · THE PER-BILL TABLE IS THE EVIDENCE AND IT IS SORTED FOR THE READER.**
Warned rows first, then largest absolute delta — because a 240-row preview is
not read in order and a systematic error announces itself in the outlier, not in
the median.

**4 · ONE CLASS PER CASE (BR-BIL-042).** A bulk case may not mix restatements
with document reissues: an approver reading a Σ of money deltas is not reviewing
reprints, and one approval cannot honestly cover both. Refused at SCOPE time,
before a preview exists to be approved.

════════════════════════════════════════════════════════════════════════════
THERE IS NO BATCH ROLLBACK. NOT "NOT YET" — NEVER.
════════════════════════════════════════════════════════════════════════════
BR-BIL-047, and it is the most important sentence in this file. One bill is the
unit of atomicity: its credit note, its rebill and its posting handoff commit
together or not at all. A failed bill leaves ZERO artifacts and stays
correctable. **Succeeded bills are never reversed because a later bill failed** —
a posted ledger pair cannot be un-posted (hard rule 4) and a delivered bill
cannot be un-sent, so an "undo the batch" button would be a lie drawn in the UI.

`explain_no_batch_rollback()` exists so the screen can say WHY, and so a reader
searching this module for `rollback` finds the reason instead of an absence.
The remedy an operator is offered is the honest one: a NEW correction case over
the bills that executed.

Consequences, all of them visible on the case: succeeded bills deliver
immediately (a correct corrected bill should not wait on someone else's lock);
the case stays **open** while any bill is unresolved; resume re-attempts ONLY
the failures; and abandoning a failure is an explicit, reasoned, audited act
rather than a case that quietly reports "done".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.billing import correction_reasons, corrections, models, payments_seam
from apps.billing.correction_models import (
    BILL_ABANDONED,
    BILL_DONE,
    BILL_FAILED,
    BILL_QUEUED,
    CASE_APPROVED,
    CASE_DONE,
    CASE_EXECUTING,
    CASE_OPEN,
    CASE_PENDING_APPROVAL,
    CASE_PREVIEW,
    CLASS_CREDIT_ONLY,
    CLASS_DOCUMENT,
    CLASS_RESTATEMENT,
    DIRECTION_DOWN,
    DIRECTION_UP,
    SCOPE_ACCOUNT,
    SCOPE_CYCLE,
    SCOPE_DATE_RANGE,
    SCOPE_KINDS,
    SCOPE_PLAN,
    SCOPE_PRICE_MISTAKE,
    SCOPE_RUN,
    SCOPE_SERVICE,
    SCOPE_SINGLE,
    CorrectionCase,
    CorrectionCaseBill,
)
from apps.billing.exceptions import BillingRuleError
from core import audit, money
from core import tenancy as core_tenancy

ZERO = Decimal("0")


def _actor_id(actor: Any) -> Any:
    """The acting USER's id, from whatever the caller holds.

    Callers pass an actor object (a session principal, a job's None) rather than
    a `User`, and this module may not import `apps.identity.models` — a
    cross-module model import is a G6 failure and a B8 layering break. Assigning
    by `_id` needs no class, which is why every actor column here is written
    that way.
    """
    return audit.actor_user_id(actor)


def _tenant_id() -> Any:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


@dataclass(frozen=True)
class AggregatePanel:
    """The bulk panel — and the shape is the rule (BR-BIL-046).

    Every figure is a display sum over the per-bill previews. **The bulk layer
    performs no arithmetic of its own** (US-BIL-016 §7 says exactly that), which
    is why `tie_out()` exists: Σ credit − Σ rebill must equal Σ net, and Σ net
    must equal the sum of the per-bill deltas. The same redundancy BR-BIL-032
    uses on the bill payload, for the same reason — drift between a total and
    its parts is otherwise invisible.
    """

    bills: int
    currency: str
    credit_total: Decimal
    rebill_total: Decimal
    net_delta: Decimal
    up_count: int
    up_total: Decimal
    down_count: int
    down_total: Decimal
    ending_in_credit: int
    ending_owing_more: int
    warned: int
    tax_by_authority: tuple[tuple[str, Decimal], ...]
    #: `CR-101-BRC03` §06 — the DISCOUNTS cell of the batch panel (p129, 26.3:
    #: *"Accounts affected"*; 26.2's per-month rows are the per-bill panels on
    #: `bills_detail`). Summed from the per-bill panels and nothing else, the
    #: way every other figure here is. See `_discounts_summary`.
    discounts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """What the panel renders. **The ↑ and ↓ figures are not optional.**

        There is no code path in this module that emits `net_delta` without
        them, and a test proves the refusal RED against a build that showed only
        the net (TC-9). Money as strings — rule 2.
        """
        return {
            "bills": self.bills,
            "currency": self.currency,
            "credit_total": str(self.credit_total),
            "rebill_total": str(self.rebill_total),
            "net_delta": str(self.net_delta),
            "up": {"count": self.up_count, "total": str(self.up_total)},
            "down": {"count": self.down_count, "total": str(self.down_total)},
            "accounts_ending_in_credit": self.ending_in_credit,
            "accounts_owing_more": self.ending_owing_more,
            "warned_rows": self.warned,
            "tax_by_authority": [
                {"authority": name, "delta": str(delta)} for name, delta in self.tax_by_authority
            ],
            # CR-101-BRC03 §06 — drawn on every class, never omitted (p129).
            "discounts": dict(self.discounts),
        }

    def tie_out(self) -> None:
        """Σ credit − Σ rebill = Σ net. Asserted, not assumed."""
        expected = money.finalize(self.credit_total - self.rebill_total)
        if expected != money.finalize(-self.net_delta):
            raise BillingRuleError(
                f"the aggregate does not tie out: Σ credit {self.credit_total} − Σ rebill "
                f"{self.rebill_total} = {expected}, and Σ net is {self.net_delta} "
                "(BR-BIL-046 / BR-BIL-032's redundancy). A panel whose total disagrees "
                "with its parts is the one figure nobody checks.",
                br_ref="BR-BIL-046",
            )


def explain_no_batch_rollback() -> str:
    """TC-12 — what the screen says when someone asks to undo the batch.

    There is no rollback function in this module and none may be added; this is
    the sentence that goes where the button would have been.
    """
    return (
        "There is no way to undo a correction batch, and there never will be. The "
        "corrections that already executed posted balanced journal entries, and a posted "
        "entry cannot be un-posted (hard rule 4); their corrected bills are already queued "
        "for delivery, and a delivered bill cannot be un-sent. A button offering to undo "
        "them would be drawing something the books cannot do. If those corrections were "
        "wrong, the remedy is a NEW correction case over exactly those bills — which is "
        "reviewed and approved like any other."
    )


#: p133's sentence, as a FACT the client renders: *"Only an issued or paid bill
#: can be corrected."* The two statuses `resolve_scope_queryset` admits, named
#: once so the sentence and the filter cannot drift apart.
CORRECTABLE_STATUSES: tuple[str, ...] = (models.INVOICE_ISSUED, models.INVOICE_PAID)


def _selector_or_refuse(kind: str, name: str, value: Any) -> str:
    """The id a scope kind NEEDS, present and uuid-shaped — or a named refusal.

    Before 2026-09-15 a `run` scope with no `bill_run_id` filtered on
    `bill_run_id IS NULL`, matched nothing, and refused one step later as
    *"this scope matches no issued bills"* — true, and the wrong sentence: the
    caller had not named a run. A non-uuid id would have reached the database
    as a `ValidationError` 500. Both are refused here, by name, at the door
    the GET and the POST share.
    """
    if value in (None, ""):
        raise BillingRuleError(
            f"a {kind} scope names the {name} it is about (BR-BIL-014).", br_ref="BR-BIL-014"
        )
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError) as bad:
        raise BillingRuleError(
            f"{name} {value!r} is not an id this product issues.", br_ref="BR-BIL-014"
        ) from bad
    return str(value)


def _resolve(module: str, attribute: str) -> Any:
    """The owning module's published selector, or None — `runs._resolve`'s door.

    Imported inside the function because `runs` reaches this module through
    `corrections` → `single`, and a module-level import would close that ring.
    """
    from apps.billing import runs

    return runs._resolve(module, attribute)


#: The machine-readable reason a bill the selector saw is not in the scope.
#: Codes, never sentences — the words are the eleven catalogues' (B14 rule 35)
#: and no rule id may reach a clerk (rule 32).
EXCLUDED_ACCOUNT_NOT_BILLABLE = "account_is_not_in_the_billable_set"
EXCLUDED_BEFORE_A_GAP = "before_a_gap_in_this_account_s_bills"
EXCLUDED_BEYOND_BACKBILL_CAP = "beyond_the_back_bill_cap"


def _narrow_to_billable_accounts(qs: Any) -> Any:
    """The PO's ruling of 2026-09-15: a bulk correction selects like a bulk RUN.

    Verbatim, asked whether a batch holding one closed account's bill should
    proceed with the rest or refuse them all: *"you will not select the
    bill/account in first place ; our rule to selct account will apply - we do
    this at the time of bulk billing also"* — so the fix is at SELECTION and
    the question of what to do at the refusal was the wrong question
    (`DEF-BIL-5377`).

    **THE RULE IS NOT RESTATED HERE AND MUST NEVER BE.** `BR-CUS-055` gives a
    closed or pending-activation account the `non_billable`/`terminal`
    behaviour class, and customers owns that class set in ONE place, which the
    bill run reaches through `accounts_for_bill_run` and this reaches through
    `billable_accounts`. Billing holds no opinion about billability and no copy
    of the list; it asks, through the seam, by name (B1 — no cross-module model
    import, hard rule 1 — no cross-module queryset of our own).

    **A SUBQUERY, NEVER A LIST OF IDS.** `NFR-5` puts no cap on a tenant and
    the T5 ceiling is 40,000 accounts; `.values("id")` inside an `__in` is one
    SQL statement, and materialising the ids would put back the limit the
    ceiling forbids.

    ⚠ **WHAT HAPPENS WHEN CUSTOMERS HAS NOT PUBLISHED THE SELECTOR: WE REFUSE,
    WE DO NOT PASS THE SCOPE THROUGH.** The alternative — carry on unfiltered —
    is the defect this function exists to fix, silently restored, on the day
    somebody renames a selector. `runs.prepare_run` refuses on the same seam
    for the same reason, in the same words.
    """
    billable = _resolve("customers", "billable_accounts")
    if billable is None:
        raise BillingRuleError(
            "customers has not published billable_accounts, so a bulk correction "
            "cannot resolve who may be corrected. A scope that cannot ask who is "
            "billable is not a scope — it is every bill the query happened to match.",
            br_ref="BR-CUS-055",
        )
    return qs.filter(account_id__in=billable().values("id"))


def _periods_are_consecutive(earlier_end: date, later_start: date, shortest_days: int) -> bool:
    """Do these two of ONE account's billing periods sit next to each other?

    **The hole is measured against the PERIOD, never against the calendar**, and
    that is the whole of the judgment recorded in the decision log of
    2026-09-15. A cycle in this product is Daily · Weekly · Fortnightly ·
    Monthly · Bimonthly · Quarterly · Semiannual or Annual
    (`metering.schedule.FREQUENCIES`), so *"one month"* is not a threshold this
    code may hold: it would read every quarterly account as one long gap and
    refuse corrections nobody asked to refuse.

    So: **the two periods are consecutive when the hole between them is less
    than HALF a billing period.** Worked, on a monthly account billed to 31
    August whose next bill in scope begins 1 October — a 30-day hole against a
    31-day period, more than half, so September is a gap. The same account
    billed to 31 August and again from 1 September has a hole of 0 days and is
    one run. A quarterly account billed to 31 March and again from 1 July has a
    hole of 91 days against a 90-day period and September quarter is a gap.

    Half a period rather than a whole one because a missing bill leaves a hole
    one period MINUS A DAY wide, so a whole-period threshold can never fire;
    half also absorbs the two or three days a move-in or a final bill puts on
    the boundary, which is not a missing bill and must not read as one.
    """
    hole = (later_start - earlier_end).days - 1
    if hole <= 0:
        return True
    return hole * 2 < shortest_days


def _ids_before_a_gap(rows: list[tuple[Any, Any, date, date]]) -> list[Any]:
    """`BR-BIL-1046`: per account, every bill BEFORE the first gap going back.

    PO 2026-09-15, verbatim: *"we take consicative bills ; not like in 24 months
    - latest 12 and then 18 one - 18th is not valid and it will not be taken
    into processing at all"*. The run kept is the one that ends at the account's
    MOST RECENT bill in scope; the walk goes backwards from there and stops at
    the first hole. Everything older is not taken into processing at all — not
    offered, not counted, not silently dropped mid-run.

    `rows` are `(id, account_id, period_start, period_end)` and nothing else:
    four scalars, so a T5 scope costs one narrow read rather than 40,000 model
    instances with their joins (the `CR-060` T14 lesson, one table over).

    Returns the ids to DROP, which on every ordinary scope is an empty list —
    an account billed every month has no hole to find.
    """
    by_account: dict[str, list[tuple[Any, date, date]]] = {}
    for row_id, account_id, period_start, period_end in rows:
        by_account.setdefault(str(account_id), []).append((row_id, period_start, period_end))
    drop: list[Any] = []
    for periods in by_account.values():
        if len(periods) < 2:
            continue
        periods.sort(key=lambda one: (one[1], one[2]))
        cut = 0
        for index in range(len(periods) - 1, 0, -1):
            earlier_id, earlier_start, earlier_end = periods[index - 1]
            later_id, later_start, later_end = periods[index]
            shortest = min(
                (earlier_end - earlier_start).days + 1, (later_end - later_start).days + 1
            )
            if not _periods_are_consecutive(earlier_end, later_start, shortest):
                cut = index
                break
        drop.extend(row_id for row_id, _, _ in periods[:cut])
    return drop


def _narrow_to_the_consecutive_run(qs: Any) -> Any:
    """`BR-BIL-1046` applied to the scope, so step 1 SHOWS what step 2 pins.

    ⚠ **THIS COSTS ONE EXTRA READ OF FOUR SCALAR COLUMNS OVER THE WHOLE SCOPE,
    AND THAT IS A TRADE RATHER THAN AN OVERSIGHT.** Contiguity is not a
    predicate a row can answer about itself — it is a fact about an account's
    other bills — so there is no `WHERE` clause that expresses it and no way to
    page it away. The alternative was to apply it inside `open_case`, which
    already walks every bill; that was rejected because the PO said an excluded
    period is *"not offered"*, and the only place a clerk is offered anything is
    the step-1 table this queryset feeds. A scope table that offers a bill the
    case will then drop is the silent filter the same day's other ruling
    forbids.

    The ids that come back are the GAPPED ones — typically none — so the
    `exclude` carries a short list even where the scope is long.
    """
    rows = list(qs.values_list("id", "account_id", "period_start", "period_end"))
    drop = _ids_before_a_gap(rows)
    if not drop:
        return qs
    return qs.exclude(pk__in=drop)


def resolve_scope_queryset(
    *,
    kind: str,
    bill_run_id: Any = None,
    cycle_id: Any = None,
    plan_id: Any = None,
    service_code: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    invoice_ids: tuple[Any, ...] = (),
    account_id: Any = None,
    wrong_kind: str | None = None,
    wrong_id: Any = None,
    exclude_in_flight: bool = False,
) -> Any:
    """The selector as an ORDERED, tenant-scoped QUERYSET — nothing fetched.

    `CR-101-BRC03` §06 split this out of `resolve_scope` (2026-09-15) so the
    wizard's step 1 can PAGE the bills a scope resolves to and total them in
    SQL (`NFR-3`): a run at T5 is 40,000 bills and the drawing's table is
    fifty of them a page with one totals row over all of them. `open_case`
    still pins every bill, because a case IS its whole bill set; what changed
    is that the screen no longer has to load the set to show it.

    BR-BIL-014 (bulk) names the five selectors — run / cycle / plan / service /
    date-range — and `single` is US-BIL-015's one-bill case entering by the same
    door. Only ISSUED and PAID bills are eligible (`CORRECTABLE_STATUSES`): a
    draft is re-priced rather than corrected, a void was never billed, and a
    `corrected` bill is not the latest in its chain (BR-BIL-048).

    RLS does the tenant half (hard rule 1); the explicit `tenant_id` filter is
    the inner guarantee the same way `documents._lines_of` states it.
    """
    if kind not in SCOPE_KINDS:
        raise BillingRuleError(
            f"unknown correction scope {kind!r}; BR-BIL-014 defines {', '.join(SCOPE_KINDS)}.",
            br_ref="BR-BIL-014",
        )
    qs = models.Invoice.objects.filter(
        tenant_id=_tenant_id(),
        status__in=CORRECTABLE_STATUSES,
    )
    qs = _scope_predicate(
        qs,
        kind=kind,
        bill_run_id=bill_run_id,
        cycle_id=cycle_id,
        plan_id=plan_id,
        service_code=service_code,
        period_start=period_start,
        period_end=period_end,
        invoice_ids=invoice_ids,
        account_id=account_id,
        wrong_kind=wrong_kind,
        wrong_id=wrong_id,
    )
    if exclude_in_flight:
        # `CR-180-BRC10` — a bill already pinned by an UNRESOLVED case is not
        # offered (BR-BIL-048, one open case per bill). It is LISTED by
        # `excluded_from_scope`, never dropped in silence.
        qs = qs.exclude(pk__in=_in_flight_invoice_ids())
    # ── THE TWO SELECTION RULES OF 2026-09-15, AND THEY SKIP `single` ────────
    # A SCOPE sweeps bills up; a clerk who names ONE BILL has picked it on
    # purpose. Both rulings narrow the first and neither touches the second:
    #
    #   * `DEF-BIL-5377` — *"you will not select the bill/account in first
    #     place ; our rule to selct account will apply"*. The PO's own carve-out
    #     is recorded with the ruling: a closed account's issued bill is still
    #     correctable when a clerk picks that bill, because the utility may have
    #     overbilled somebody who has since left, and refusing that for ever
    #     would be wrong.
    #   * `BR-BIL-1046` — the months are a consecutive run. One bill is a run of
    #     one, so the walk would find nothing anyway; it is skipped for cost,
    #     not for meaning.
    #
    # ⚠ `CR-180-BRC10`: **One customer** (`account`) is a clerk naming bills of
    # ONE account by hand — the `single` case widened to several months — so it
    # skips both, for the `single` reason (J-FIX-TWENTY S13: a closed account's
    # final bill is correctable when a clerk picks it).
    #
    # The skip is STATED rather than silent (hard-won law 7: a declared blind
    # spot with no number beside it is indistinguishable from an empty one) —
    # `scope_table` publishes `narrowed_by` so a caller can see which of the two
    # ran over what.
    if kind not in (SCOPE_SINGLE, SCOPE_ACCOUNT):
        qs = _narrow_to_billable_accounts(qs)
        qs = _narrow_to_the_consecutive_run(qs)
    return qs.order_by("invoice_no", "id")


#: `CR-180-BRC10` — what a price mistake can name (contract §1: `wrong_kind`).
WRONG_KINDS: tuple[str, ...] = ("rate", "tax", "charge")


def _in_flight_invoice_ids() -> Any:
    """The bills an UNRESOLVED case holds — a subquery, never a list (NFR-5)."""
    return CorrectionCaseBill.objects.filter(tenant_id=_tenant_id(), status=BILL_QUEUED).values(
        "invoice_id"
    )


def _scope_predicate(
    qs: Any,
    *,
    kind: str,
    bill_run_id: Any,
    cycle_id: Any,
    plan_id: Any,
    service_code: str | None,
    period_start: date | None,
    period_end: date | None,
    invoice_ids: tuple[Any, ...],
    account_id: Any,
    wrong_kind: str | None,
    wrong_id: Any,
) -> Any:
    """The scope's own predicate — WHICH bills, before the narrowing rules.

    Split out of `resolve_scope_queryset` (`CR-180-BRC10`) when two kinds were
    added; every pre-existing branch is unchanged line for line.
    """
    if kind == SCOPE_SINGLE:
        if not invoice_ids:
            raise BillingRuleError(
                "a single-bill correction names the bill it is about.", br_ref="BR-BIL-014"
            )
        qs = qs.filter(pk__in=[_selector_or_refuse(kind, "invoice_id", one) for one in invoice_ids])
    elif kind == SCOPE_RUN:
        qs = qs.filter(bill_run_id=_selector_or_refuse(kind, "bill_run_id", bill_run_id))
    elif kind == SCOPE_CYCLE:
        qs = qs.filter(bill_run__cycle_id=_selector_or_refuse(kind, "cycle_id", cycle_id))
    elif kind == SCOPE_PLAN:
        _selector_or_refuse(kind, "plan_id", plan_id)
        # The plan reaches a bill through its lines' tariff versions and
        # rating's `plan_rate_schedules` — billing holds no plan column, and it
        # traverses the REVIEWED cross-module FK (`invoice_lines.
        # tariff_version_id`, B2 §2) rather than importing rating's models,
        # which G6 forbids and B1 forbids for good reason.
        qs = qs.filter(
            lines__tariff_version__tariff__planrateschedule__rate_plan_id=plan_id
        ).distinct()
    elif kind == SCOPE_SERVICE:
        if not service_code:
            raise BillingRuleError(
                "a service scope names the service it is about (BR-BIL-014).",
                br_ref="BR-BIL-014",
            )
        qs = qs.filter(lines__service__code=service_code).distinct()
    elif kind == SCOPE_DATE_RANGE:
        if period_start is None or period_end is None:
            raise BillingRuleError(
                "a date-range scope needs both ends; one open end would pick up every "
                "bill the utility has ever issued.",
                br_ref="BR-BIL-014",
            )
        qs = qs.filter(period_start__gte=period_start, period_end__lte=period_end)
    elif kind == SCOPE_ACCOUNT:
        # `CR-180-BRC10` B1 — one account, one or many of ITS bills, in ONE
        # case (`DEF-BIL-5348`). A bill of another account named here is not
        # offered (`excluded_from_scope` names it), never corrected under the
        # wrong customer.
        qs = qs.filter(account_id=_selector_or_refuse(kind, "account_id", account_id))
        # Contract A1: `account_id` ALONE is every correctable bill of the
        # account (the Bills step's list); with `invoice_ids`, only those.
        if invoice_ids:
            qs = qs.filter(
                pk__in=[_selector_or_refuse(kind, "invoice_id", one) for one in invoice_ids]
            )
    elif kind == SCOPE_PRICE_MISTAKE:
        # `CR-180-BRC10` B2 — every bill that USED a rate, a tax or a charge
        # code during the window, across runs (decision log 2026-10-12: *"A
        # price mistake (From–To across all runs)"*). "Used during" is a period
        # that OVERLAPS the window: a bill for 25 Jul – 24 Aug carried July's
        # price for a week, and a containment test would leave it wrong.
        if period_start is None or period_end is None:
            raise BillingRuleError(
                "a price mistake needs both dates; one open end would pick up every "
                "bill the utility has ever issued.",
                br_ref="BR-BIL-014",
            )
        if wrong_kind not in WRONG_KINDS:
            raise BillingRuleError(
                f"a price mistake names what was wrong — one of {', '.join(WRONG_KINDS)}.",
                br_ref="BR-BIL-014",
            )
        named = _selector_or_refuse(kind, "wrong_id", wrong_id)
        qs = qs.filter(period_start__lte=period_end, period_end__gte=period_start)
        if wrong_kind == "rate":
            # A SCHEDULE or one of its VERSIONS — both are "the rate" to a clerk.
            from django.db.models import Q

            qs = qs.filter(
                Q(lines__tariff_version_id=named) | Q(lines__tariff_version__tariff_id=named)
            ).distinct()
        elif wrong_kind == "tax":
            qs = qs.filter(lines__tax_id=named).distinct()
        else:
            qs = qs.filter(lines__charge_id=named).distinct()
    # A second selector NARROWS: "run 07-A · service Water · plan Residential
    # Standard" is TC-1's own scope and is three predicates, not three cases.
    if kind != SCOPE_SERVICE and service_code:
        qs = qs.filter(lines__service__code=service_code).distinct()
    if kind != SCOPE_PLAN and plan_id:
        qs = qs.filter(
            lines__tariff_version__tariff__planrateschedule__rate_plan_id=plan_id
        ).distinct()
    return qs


#: `CR-180-BRC10` — why a bill the scope saw is not offered. CODES, never
#: sentences (B14 rules 32/35): the words are the catalogues'. Contract A1
#: names two — `draft` and `open_case`; the other four only arise when a
#: caller NAMES a bill that cannot be corrected, and are stated rather than
#: folded into one of the two.
EXCLUDED_DRAFT = "draft"
EXCLUDED_IN_OPEN_CASE = "open_case"
EXCLUDED_ALREADY_CORRECTED = "already_corrected"
EXCLUDED_VOID = "void_bill"
EXCLUDED_NOT_THIS_ACCOUNT = "not_this_account"
EXCLUDED_NOT_FOUND = "not_found"


def _excluded_row(row: dict[str, Any], code: str) -> dict[str, Any]:
    start, end = row.get("period_start"), row.get("period_end")
    return {
        "invoice_id": str(row["id"]),
        "invoice_no": row.get("invoice_no") or None,
        "period_start": start.isoformat() if start else None,
        "period_end": end.isoformat() if end else None,
        "code": code,
    }


def excluded_from_scope(
    *,
    kind: str,
    account_id: Any = None,
    invoice_ids: tuple[Any, ...] = (),
    **selectors_: Any,
) -> list[dict[str, Any]]:
    """The bills a scope SAW and does not offer, each with a code (A1).

    `{ invoice_id, invoice_no|null, period_start, period_end, code }`. For
    **One customer** with no bills named: the account's drafts and the bills an
    open case holds. With bills named: every named bill that cannot be
    corrected (J-FIX-TWENTY S14: *"Refused at Bills with the reason; nothing
    saved"*). For a run: its drafts and the bills an open case holds. A read.
    """
    tenant_id = _tenant_id()
    in_flight = {
        str(pk)
        for pk in CorrectionCaseBill.objects.filter(
            tenant_id=tenant_id, status=BILL_QUEUED
        ).values_list("invoice_id", flat=True)
    }
    fields = ("id", "invoice_no", "status", "account_id", "period_start", "period_end")
    out: list[dict[str, Any]] = []
    named = [str(value) for value in invoice_ids if value]
    if kind in (SCOPE_ACCOUNT, SCOPE_SINGLE) and named:
        valid: list[str] = []
        for one in named:
            try:
                UUID(one)
            except (ValueError, AttributeError, TypeError):
                out.append(_excluded_row({"id": one}, EXCLUDED_NOT_FOUND))
                continue
            valid.append(one)
        rows = {
            str(row["id"]): row
            for row in models.Invoice.objects.filter(tenant_id=tenant_id, pk__in=valid).values(
                *fields
            )
        }
        for one in valid:
            row = rows.get(one)
            if row is None:
                out.append(_excluded_row({"id": one}, EXCLUDED_NOT_FOUND))
                continue
            if kind == SCOPE_ACCOUNT and account_id and str(row["account_id"]) != str(account_id):
                code = EXCLUDED_NOT_THIS_ACCOUNT
            elif row["status"] == models.INVOICE_DRAFT:
                code = EXCLUDED_DRAFT
            elif row["status"] == models.INVOICE_CORRECTED:
                code = EXCLUDED_ALREADY_CORRECTED
            elif row["status"] == models.INVOICE_VOID:
                code = EXCLUDED_VOID
            elif row["status"] not in CORRECTABLE_STATUSES:
                code = EXCLUDED_NOT_FOUND
            elif one in in_flight:
                code = EXCLUDED_IN_OPEN_CASE
            else:
                continue
            out.append(_excluded_row(row, code))
        return out
    drafts = models.Invoice.objects.none()
    if kind == SCOPE_ACCOUNT and account_id:
        drafts = models.Invoice.objects.filter(
            tenant_id=tenant_id, account_id=account_id, status=models.INVOICE_DRAFT
        )
    elif kind == SCOPE_RUN and selectors_.get("bill_run_id"):
        drafts = models.Invoice.objects.filter(
            tenant_id=tenant_id,
            bill_run_id=selectors_["bill_run_id"],
            status=models.INVOICE_DRAFT,
        )
    out.extend(
        _excluded_row(row, EXCLUDED_DRAFT)
        for row in drafts.order_by("period_start", "id").values(*fields)
    )
    if in_flight:
        held = resolve_scope_queryset(kind=kind, account_id=account_id, **selectors_).filter(
            pk__in=list(in_flight)
        )
        out.extend(_excluded_row(row, EXCLUDED_IN_OPEN_CASE) for row in held.values(*fields))
    return out


def resolve_scope(
    *,
    kind: str,
    bill_run_id: Any = None,
    cycle_id: Any = None,
    plan_id: Any = None,
    service_code: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    invoice_ids: tuple[Any, ...] = (),
    account_id: Any = None,
    wrong_kind: str | None = None,
    wrong_id: Any = None,
    exclude_in_flight: bool = False,
) -> tuple[models.Invoice, ...]:
    """Resolve the selector into CONCRETE issued bills. Once, at preview.

    The whole set, fetched — what `open_case` pins. The paged form the wizard's
    step 1 draws is `resolve_scope_queryset` + `scope_table`; this is that
    queryset materialised, and the two cannot disagree about which bills are
    in scope because there is one filter.
    """
    return tuple(
        resolve_scope_queryset(
            kind=kind,
            bill_run_id=bill_run_id,
            cycle_id=cycle_id,
            plan_id=plan_id,
            service_code=service_code,
            period_start=period_start,
            period_end=period_end,
            invoice_ids=invoice_ids,
            account_id=account_id,
            wrong_kind=wrong_kind,
            wrong_id=wrong_id,
            exclude_in_flight=exclude_in_flight,
        )
    )


# ── The step-1 table: BILL · PERIOD · AMOUNT · PAID · STATE, and its totals ──

#: p133's STATE column, as CODES the client renders: `Paid` / `Part paid` /
#: `Unpaid`. Derived from MONEY — what payments has applied against what the
#: bill asked for — never from `invoices.status`, which is a lifecycle column
#: that says `issued` on a bill paid in full this morning. The lifecycle value
#: travels beside it as `bill_status`, so a reader can see both facts.
STATE_PAID = "paid"
STATE_PART_PAID = "part_paid"
STATE_UNPAID = "unpaid"

#: The scope table's problem code when payments could not be asked.
PAYMENTS_UNREACHABLE = "payments_could_not_be_asked"
#: …and when the bills in scope are not all in one currency, so a totals row
#: would be adding two units (rule 2 — money travels with its CHAR(3)).
MIXED_CURRENCIES = "scope_spans_more_than_one_currency"


def amount_asked_expression() -> Any:
    """`selectors.amount_due_for`, AS SQL — so a scope can be totalled in one query.

    BR-BIL-072 / DEF-2416: a bill is measured at what it ASKS for, which is
    its total for every bill that is not budget-billing and the LEVEL stamped
    in `bill_payload.budget.amount_due` for one that is (❄️ WE-8: issued
    292.87, asks 242.00). `amount_due_for` is the ONE statement of that rule
    and stays so; this is its bulk form, and `tests/test_cr101_lane_b_scope_
    resolve.py` asserts the two agree on a budget bill and an ordinary one,
    which is the only thing that stops them drifting (the `_credit_positions`
    discipline in payments' seam, for the same reason).
    """
    from django.db.models import DecimalField, F
    from django.db.models.fields.json import KeyTextTransform
    from django.db.models.functions import Cast, Coalesce

    level = Cast(
        KeyTextTransform("amount_due", KeyTextTransform("budget", "bill_payload")),
        DecimalField(max_digits=18, decimal_places=6),
    )
    return Coalesce(level, F("total"), output_field=DecimalField(max_digits=18, decimal_places=6))


def paid_state(*, asked: Decimal, paid: Decimal | None) -> str | None:
    """p133's STATE from two figures. `None` when payments could not be asked —
    never `unpaid`, which would be a false fact drawn in the colour of a debt."""
    if paid is None:
        return None
    if paid >= asked:
        return STATE_PAID
    if paid > ZERO:
        return STATE_PART_PAID
    return STATE_UNPAID


#: What `narrowings_for` says when the caller did not name a scope kind. It is
#: NOT an empty list, deliberately — see that function.
NARROWING_NOT_STATED = "the_caller_did_not_say_which_scope"


def narrowings_for(kind: str | None) -> list[str]:
    """Which of the two 2026-09-15 SELECTION rules ran over this scope kind.

    A fact about the code path, not a count of rows — so it costs no query and
    is true by construction. It exists because hard-won law 7's fifth shape is
    a check reporting zero over a scope it silently excludes: a `single` scope
    is deliberately narrowed by NEITHER rule, and a caller reading a table with
    no exclusions in it cannot otherwise tell *"nothing was excluded"* from
    *"exclusion does not run here"*.

    ⚠ **`None` RETURNS A MARKER AND NEVER `[]`, WHICH IS THE WHOLE POINT OF THE
    FUNCTION APPLIED TO ITSELF.** `scope_table`'s `scope_kind` used to default
    to `SCOPE_SINGLE`, so a caller that simply forgot to pass it was told *"no
    narrowing ran"* — a confident, wrong answer, over a queryset
    `resolve_scope_queryset` had in fact narrowed on its own `kind`. Under-
    reporting is the dangerous direction: it asserts that nothing was filtered.
    An unstated kind now reads as unknown, which is what it is.
    """
    if kind is None:
        return [NARROWING_NOT_STATED]
    if kind in (SCOPE_SINGLE, SCOPE_ACCOUNT):
        return []
    return [EXCLUDED_ACCOUNT_NOT_BILLABLE, EXCLUDED_BEFORE_A_GAP]


def scope_table(
    page: tuple[models.Invoice, ...], *, queryset: Any, scope_kind: str | None = None
) -> dict[str, Any]:
    """The rows of ONE PAGE and the totals of the WHOLE scope (p133).

    `CR-101-BRC03` §06, screen 26: *"the bills it resolves to, with what each
    asked and what has been paid"*, one row per bill — `BILL · PERIOD ·
    AMOUNT · PAID · STATE` — and a totals row: *"Six bills · $1,454.10 ·
    $904.50"*. Three reads and no arithmetic of this module's own:

    * **AMOUNT** is what the bill ASKED for (`selectors.amount_due_for`,
      BR-BIL-072), with `total` beside it so a budget bill's two figures both
      show;
    * **PAID** is payments' (`payments_seam.allocated_for_invoices`, one
      statement for the page); **STATE** is `paid_state` over the two;
    * **the totals** are SQL over the queryset — `COUNT`, Σ of
      `amount_asked_expression`, and payments' Σ over the same bills as a
      subquery — never a sum of the page on screen (`NFR-3`).

    `paid` and `state` are `null`, and `totals.paid` is `null`, with a problem
    naming the seam, when payments could not be asked: the seam's own rule,
    *"an unwired seam reports, it never answers zero"*, because a run drawn as
    forty thousand `Unpaid` bills is a false fact on an approval screen.
    """
    from django.db.models import Count, Sum

    from apps.billing import selectors

    problems: list[dict[str, Any]] = []
    ids = [str(invoice.pk) for invoice in page]
    paid_by_id = payments_seam.allocated_for_invoices(ids) if ids else {}
    # `order_by()` — the scope is ordered for the page, and an ORDER BY inside
    # an `IN (subquery)` over a DISTINCT select is refused by PostgreSQL.
    paid_total = payments_seam.allocated_total_for_invoices(queryset.order_by().values("id"))
    if (ids and paid_by_id is None) or paid_total is None:
        problems.append(
            {
                "code": PAYMENTS_UNREACHABLE,
                "br_ref": "BR-PAY-010",
                "detail": "payments has not published the read that says what has been "
                "applied to these bills, so PAID and STATE are empty rather than drawn "
                "as unpaid. The amounts are the bills' own and are unaffected.",
            }
        )
        paid_by_id = None
        paid_total = None

    # `CR-180-BRC10` A1 — each row names its account and customer (the Bills
    # step's account card and run table). ONE read for the page's names
    # (`primary_contact_names_for`); the account number rides the reviewed FK.
    from apps.billing import customers_seam

    account_ids = sorted({str(invoice.account_id) for invoice in page})
    names = (customers_seam.primary_contact_names_for(account_ids) if account_ids else {}) or {}
    account_nos = (
        {
            str(pk): number
            for pk, number in models.Invoice.objects.filter(
                tenant_id=_tenant_id(), pk__in=ids
            ).values_list("account_id", "account__account_no")
        }
        if ids
        else {}
    )
    rows: list[dict[str, Any]] = []
    for invoice in page:
        asked = selectors.amount_due_for(invoice)
        paid = None if paid_by_id is None else paid_by_id.get(str(invoice.pk), ZERO)
        rows.append(
            {
                "invoice_id": str(invoice.pk),
                "invoice_no": invoice.invoice_no,
                "account_id": str(invoice.account_id),
                "account_no": account_nos.get(str(invoice.account_id)),
                "customer_name": names.get(str(invoice.account_id)),
                "period_start": invoice.period_start.isoformat(),
                "period_end": invoice.period_end.isoformat(),
                "amount": str(asked),
                "total": str(invoice.total),
                "paid": None if paid is None else str(paid),
                "state": paid_state(asked=asked, paid=paid),
                "bill_status": invoice.status,
                "currency": invoice.currency,
            }
        )

    totals = queryset.order_by().aggregate(
        bills=Count("id", distinct=True),
        amount=Sum(amount_asked_expression()),
        # `CR-180-BRC10` A1 — how many accounts the scope covers, in SQL.
        accounts=Count("account_id", distinct=True),
    )
    currencies = sorted(
        {code for code in queryset.order_by().values_list("currency", flat=True).distinct()}
    )
    currency = currencies[0] if len(currencies) == 1 else None
    if len(currencies) > 1:
        problems.append(
            {
                "code": MIXED_CURRENCIES,
                "br_ref": "CLAUDE.md rule 2",
                "detail": f"the bills in this scope are billed in {', '.join(currencies)}; "
                "a totals row would add two units, so it carries no currency and the "
                "figures are served per bill.",
            }
        )
    return {
        "rows": rows,
        "totals": {
            "bills": int(totals["bills"] or 0),
            "amount": str(totals["amount"] if totals["amount"] is not None else ZERO),
            "paid": None if paid_total is None else str(paid_total),
            "currency": currency,
            "accounts": int(totals["accounts"] or 0),
        },
        "correctable_statuses": list(CORRECTABLE_STATUSES),
        "narrowed_by": narrowings_for(scope_kind),
        "problems": problems,
    }


def refuse_mixed_class_in_bulk(reason_codes: tuple[str, ...], *, scope_kind: str) -> None:
    """TC-14 — **one class per BULK case** (BR-BIL-042), refused at scope time.

    The rule reads two ways and both are in the epic, so both are implemented
    and the difference is the SCOPE:

    * a **single-bill** case may cite several reasons and takes the strongest
      class present (US-BIL-015 TC-11: "wrong read" + "address" is ONE class-R
      case, and the rebill's snapshot carries the corrected address anyway —
      one document, one approval, no separate reissue);
    * a **bulk** case may not mix them (US-BIL-016 TC-14). An approver reading a
      Σ of money deltas is not reviewing reprints, and one signature cannot
      honestly cover both. The operator is told to raise the document reasons as
      their own case.
    """
    # `CR-180-BRC10`: **One customer** is the single-bill case widened to
    # several months of ONE account, so it takes the strongest class like
    # `single` does (US-BIL-015 TC-11) rather than refusing a mix.
    if scope_kind in (SCOPE_SINGLE, SCOPE_ACCOUNT):
        return
    classes = {correction_reasons.SEEDED_REASON_CLASSES[code] for code in reason_codes}
    if len(classes) > 1:
        raise BillingRuleError(
            f"a bulk correction case carries ONE class and these reasons carry "
            f"{len(classes)} ({', '.join(sorted(classes))}) — BR-BIL-042. Somebody "
            "approving a total of money deltas is not reviewing reprints, and one "
            "approval cannot honestly cover both. Raise the document reasons as their "
            "own case.",
            br_ref="BR-BIL-042",
        )


def _hash_of(impacts: list[dict[str, Any]]) -> str:
    """BR-BIL-044's content hash — what approval binds.

    Over the SORTED, canonically-serialised per-bill impacts, so two previews of
    the same facts hash the same and any input drift changes it. `sort_keys` and
    a stable separator matter: a dict whose key order moved would look like
    drift, and drift that is not drift teaches operators to re-approve reflexively.
    """
    canonical = json.dumps(impacts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def open_case(
    *,
    reason_codes: tuple[str, ...],
    scope_kind: str,
    scope: dict[str, Any] | None = None,
    invoices: tuple[models.Invoice, ...],
    actor: Any = None,
    posting_period: date | None = None,
    goodwill_amount: Decimal | None = None,
    as_of: date,
    backbill_window_months: int = corrections.DEFAULT_BACKBILL_WINDOW_MONTHS,
    theft_exempt: bool = False,
    case_no: str | None = None,
) -> CorrectionCase:
    """Preview N bills as ONE case. **Writes no money** (BR-BIL-014).

    The rows it writes are the case, its pinned bill set and their impacts —
    none of which is money-bearing: no credit note, no invoice, no adjustment,
    no journal line exists until `execute`. A test counts those four tables
    before and after (US-BIL-031 TC-2's method, applied here) rather than
    reading this paragraph.

    Refuses, in this order and all before anything is written: an empty scope ·
    a reason with no class · a MIXED class (BR-BIL-042) · a bill that is not the
    latest in its chain (BR-BIL-048) · a D-class case whose recomputation moves
    money (BR-BIL-043).

    ⚠ **THE BACK-BILL WINDOW IS NO LONGER IN THAT LIST, AND THAT IS THE PO'S
    RULING OF 2026-09-15** — verbatim, on seven months of which one is past the
    cap: *"in such sitution 6 bills only ; 7th is not valid case"*. An upward
    correction beyond `BR-BIL-018`'s window now EXCLUDES that bill and the case
    proceeds with the rest; the excluded bills and their figures travel on
    `preview["excluded"]` so the screen can name the month and say why. Only
    when NOTHING survives does the case refuse, which is the same answer for a
    one-bill case whose one bill is capped. The cap itself did not move.

    ⚠ **`preview_hash` COVERS THE PINNED BILLS AND NOT THE EXCLUSIONS**, which
    is deliberate: `BR-BIL-044` binds an approval to the artifact that will
    EXECUTE, and an excluded bill is not in it. A bill that leaves the scope
    between preview and approval changes the hash, because it was pinned.
    """
    if not invoices:
        raise BillingRuleError(
            "this scope matches no issued bills, so there is nothing to correct. An empty "
            "case would be approved by someone and execute nothing, which reads as "
            "success.",
            br_ref="BR-BIL-014",
        )
    correction_class = correction_reasons.class_for(reason_codes)
    refuse_mixed_class_in_bulk(tuple(reason_codes), scope_kind=scope_kind)

    tenant_id = _tenant_id()
    # G3 (PO 2026-10-14, `DEF-BIL-10147`) — this older path opens the case
    # straight into `pending_approval`, so opening IS its Send: the number is
    # taken here, inside this function's transaction, from the tenant's
    # Correction case series. A caller-supplied `case_no` (none today) wins; a
    # missing series leaves the case unnumbered and the reason on the audit row.
    numbering_gap: str | None = None
    if case_no is None:
        case_no, numbering_gap = corrections.allocate_case_no(as_of)
    case = CorrectionCase.objects.create(
        tenant_id=tenant_id,
        case_no=case_no,
        reason_codes=list(reason_codes),
        correction_class=correction_class,
        scope_kind=scope_kind,
        scope=dict(scope or {}),
        status=CASE_PREVIEW,
        posting_period=posting_period,
        initiated_by_id=_actor_id(actor),
    )

    impacts: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for invoice in invoices:
        corrections.refuse_unless_latest_in_chain(invoice)
        impact = corrections.build_impact(
            invoice,
            reason_codes=reason_codes,
            correction_class=correction_class,
            posting_period=posting_period,
            goodwill_amount=goodwill_amount,
        )
        corrections.refuse_unless_class_matches_money(impact)
        # ── PO 2026-09-15: THE CAPPED MONTH IS EXCLUDED, THE CASE PROCEEDS ───
        # Verbatim, on seven months of which one is past the cap and would
        # charge more: *"in such sitution 6 bills only ; 7th is not valid
        # case"*. This RAISED until today, so a clerk correcting seven months
        # got nothing — including the six that were lawful (`DEF-BIL-5360`).
        #
        # ⚠ **IT CANNOT BE FILTERED AT SELECTION AND THAT IS NOT AN OVERSIGHT.**
        # Whether a month is capped depends on whether its NEW price is higher,
        # which is only known after `build_impact` has re-priced it — which is
        # exactly how this differs from the same day's two selection rules.
        # A downward correction of the same aged bill is untouched at any age.
        beyond = corrections.beyond_backbill_window(
            impact,
            as_of=as_of,
            period_end=invoice.period_end,
            window_months=backbill_window_months,
            theft_exempt=theft_exempt,
        )
        if beyond is not None:
            excluded.append(
                {
                    "invoice_id": str(invoice.pk),
                    "invoice_no": invoice.invoice_no,
                    "account_id": str(invoice.account_id),
                    "period_start": invoice.period_start.isoformat(),
                    "period_end": invoice.period_end.isoformat(),
                    **beyond,
                }
            )
            continue
        try:
            CorrectionCaseBill.objects.create(
                tenant_id=tenant_id,
                case=case,
                invoice=invoice,
                account_id=invoice.account_id,
                impact=impact.as_dict(),
                delta_amount=impact.delta,
                currency=impact.currency,
                direction=impact.direction,
                warnings=[dict(warning) for warning in impact.warnings],
                status=BILL_QUEUED,
            )
        except IntegrityError as clash:
            # BR-BIL-048 from the other side: another case already holds this
            # bill in flight. The partial unique index is the arbiter, because
            # a SELECT-then-INSERT check loses the race that matters.
            raise BillingRuleError(
                f"bill {invoice.invoice_no or invoice.pk} is already inside an unresolved "
                "correction case (BR-BIL-048 — one open case per chain). Finish or "
                "abandon that case first; two cases correcting one bill would credit it "
                "twice.",
                br_ref="BR-BIL-048",
            ) from clash
        impacts.append(impact.as_dict())

    if not impacts:
        # EVERY bill was capped, so there is no case — and this is the ONE
        # place the single-bill path and the bulk path give the same answer,
        # because a case of one whose only bill is the 7th month IS *"the 7th
        # is not valid case"*. The old sentence is rebuilt here rather than
        # replaced so a clerk correcting one aged bill reads what they always
        # read, and `br_ref` stays `BR-BIL-018` so the API maps it as before.
        oldest = max(excluded, key=lambda one: one["months"])
        raise BillingRuleError(
            f"every bill in this correction adds to a period beyond the tenant's "
            f"{oldest['window_months']}-month back-bill window — the oldest ended "
            f"{oldest['months']} months ago (BR-BIL-018; PO 2026-08-11 closing OQ-104: "
            "the window applies to an UPWARD correction too). There is nothing left to "
            "correct. A DOWNWARD correction of the same bills is unaffected at any age.",
            br_ref="BR-BIL-018",
        )

    case.preview = {
        "bills": impacts,
        "aggregate": aggregate(case).as_dict(),
        # p137's fifth row, *Beyond the 12-month cap · Removed from the set*.
        # It is a LIST and never a count: a clerk told "1 bill was removed"
        # cannot tell which month, and the month is the whole question.
        "excluded": excluded,
    }
    case.preview_hash = _hash_of(impacts)
    case.status = CASE_PENDING_APPROVAL
    case.save(update_fields=["preview", "preview_hash", "status", "updated_at"])

    audit.money_action(
        actor,
        "correction.case_opened",
        "correction_cases",
        str(case.pk),
        after={
            "class": correction_class,
            "reason_codes": list(reason_codes),
            "scope_kind": scope_kind,
            "bills": len(impacts),
            # Rule 7 — every money action writes `audit_log`, and *what the
            # case did NOT take* is part of what an auditor needs. A count with
            # no bill numbers beside it cannot be reconciled afterwards.
            "excluded_bills": len(excluded),
            "excluded": [
                {"invoice_no": one["invoice_no"], "code": one["code"], "months": one["months"]}
                for one in excluded
            ],
            "preview_hash": case.preview_hash,
            "case_no": case.case_no,
            **({"numbering_gap": numbering_gap} if numbering_gap else {}),
            "money_written": "none — nothing money-bearing exists before approval",
        },
    )
    return case


def case_bills(case: CorrectionCase) -> tuple[CorrectionCaseBill, ...]:
    """The pinned rows, SORTED FOR THE READER (BR-BIL-046, TC-10).

    Warned rows first, then largest absolute delta first. Not by invoice number,
    which is the order that hides a systematic error in the middle of page four.
    """
    rows = list(CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case))
    return tuple(sorted(rows, key=lambda row: (0 if row.warnings else 1, -abs(row.delta_amount))))


def aggregate(case: CorrectionCase) -> AggregatePanel:
    """The panel — display sums over the per-bill impacts and nothing else."""
    rows = list(CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case))
    currency = rows[0].currency if rows else "USD"
    credit_total = ZERO
    rebill_total = ZERO
    net = ZERO
    up_count = down_count = 0
    up_total = down_total = ZERO
    ending_in_credit = ending_owing_more = 0
    warned = 0
    taxes: dict[str, Decimal] = {}
    for row in rows:
        impact = row.impact or {}
        credit_total = money.finalize(credit_total + Decimal(impact.get("original_total", "0")))
        rebill_total = money.finalize(rebill_total + Decimal(impact.get("corrected_total", "0")))
        net = money.finalize(net + row.delta_amount)
        if row.direction == DIRECTION_UP:
            up_count += 1
            up_total = money.finalize(up_total + row.delta_amount)
            ending_owing_more += 1
        elif row.direction == DIRECTION_DOWN:
            down_count += 1
            down_total = money.finalize(down_total + row.delta_amount)
            ending_in_credit += 1
        if row.warnings:
            warned += 1
        for entry in impact.get("tax_by_authority", []):
            name = entry.get("authority", "")
            taxes[name] = money.finalize(taxes.get(name, ZERO) + Decimal(entry.get("delta", "0")))
    return AggregatePanel(
        bills=len(rows),
        currency=currency,
        credit_total=credit_total,
        rebill_total=rebill_total,
        net_delta=net,
        up_count=up_count,
        up_total=up_total,
        down_count=down_count,
        down_total=down_total,
        ending_in_credit=ending_in_credit,
        ending_owing_more=ending_owing_more,
        warned=warned,
        tax_by_authority=tuple(sorted(taxes.items())),
        discounts=_discounts_summary(
            rows, correction_class=case.correction_class, currency=currency
        ),
    )


#: The batch panel's discount OUTCOME, one per class — the same three drawn
#: cells as the per-bill panel (`corrections.discount_panel`), at batch grain.
BATCH_DISCOUNTS_REPRICED = "re_priced_on_every_bill"
BATCH_DISCOUNTS_NOT_REPRICED = corrections.DISCOUNTS_NOT_REPRICED
BATCH_DISCOUNTS_UNCHANGED = corrections.DISCOUNTS_UNCHANGED


def _discounts_summary(rows: list[Any], *, correction_class: str, currency: str) -> dict[str, Any]:
    """`CR-101-BRC03` §06 — the DISCOUNTS cell of the batch panel (p129, 26.3).

    *"Accounts affected"*: how many bills in the case carry a reduction on
    either side, how many DISTINCT accounts that is, what those reductions
    sum to on the original bills and on the corrected ones, and the same
    split per programme label. A display sum over the per-bill panels —
    exactly the discipline `aggregate` keeps for every other figure — so the
    batch cell can never disagree with the rows under it. A case whose bills
    carry no reduction at all is `bills: 0` with empty lists, drawn rather
    than omitted.
    """
    bills_with = 0
    accounts: set[str] = set()
    original_total = ZERO
    corrected_total = ZERO
    by_label: dict[str, dict[str, Any]] = {}
    for row in rows:
        panel = (row.impact or {}).get("discounts") or {}
        original = list(panel.get("original") or [])
        corrected = list(panel.get("corrected") or [])
        if not original and not corrected:
            continue
        bills_with += 1
        accounts.add(str(row.account_id))
        original_total = money.finalize(
            original_total + Decimal(panel.get("original_total") or "0")
        )
        corrected_total = money.finalize(
            corrected_total + Decimal(panel.get("corrected_total") or "0")
        )
        for side, entries in (("original_total", original), ("corrected_total", corrected)):
            for entry in entries:
                label = str(entry.get("label") or "")
                cell = by_label.setdefault(
                    label,
                    {
                        "label": label,
                        "code": entry.get("code"),
                        "bills": set(),
                        "original_total": ZERO,
                        "corrected_total": ZERO,
                    },
                )
                cell["bills"].add(str(row.invoice_id))
                cell[side] = money.finalize(cell[side] + Decimal(entry.get("amount") or "0"))
    if correction_class == CLASS_RESTATEMENT:
        outcome = BATCH_DISCOUNTS_REPRICED
    elif correction_class == CLASS_CREDIT_ONLY:
        outcome = BATCH_DISCOUNTS_NOT_REPRICED
    else:
        outcome = BATCH_DISCOUNTS_UNCHANGED
    return {
        "outcome": outcome,
        "bills": bills_with,
        "accounts_affected": len(accounts),
        "original_total": str(original_total),
        "corrected_total": str(corrected_total),
        "delta": str(money.finalize(corrected_total - original_total)),
        "currency": currency,
        "by_label": [
            {
                "label": cell["label"],
                "code": cell["code"],
                "bills": len(cell["bills"]),
                "original_total": str(cell["original_total"]),
                "corrected_total": str(cell["corrected_total"]),
                "delta": str(money.finalize(cell["corrected_total"] - cell["original_total"])),
            }
            for _, cell in sorted(by_label.items())
        ],
    }


def approve(
    case: CorrectionCase, *, approver: Any, on_date: date, preview_hash: str | None = None
) -> CorrectionCase:
    """The gate (BR-BIL-014, v1 System Admin — OQ-072). Binds the ARTIFACT.

    `preview_hash` is what the approver's screen was rendered from. Supplying it
    is how the caller says *"I approved THESE numbers"*; a mismatch refuses here
    rather than at execute, which is earlier and cheaper. The role check itself
    is US-BIL-017's gate record and is server-enforced there — this function
    records the decision, it does not invent the permission.
    """
    if case.status not in (CASE_PREVIEW, CASE_PENDING_APPROVAL):
        raise BillingRuleError(
            f"case {case.case_no or case.pk} is {case.status} and is not awaiting "
            "approval. An approval recorded twice would make it impossible to say which "
            "signature the execution ran under.",
            br_ref="BR-BIL-014",
        )
    if preview_hash is not None and preview_hash != case.preview_hash:
        raise BillingRuleError(
            "the preview on screen is not the preview stored on this case (BR-BIL-044): "
            "approval binds the artifact, not the query. Refresh the preview and approve "
            "the figures you are actually looking at.",
            br_ref="BR-BIL-044",
        )
    case.status = CASE_APPROVED
    case.approved_by_id = _actor_id(approver)
    case.approved_on = on_date
    case.save(update_fields=["status", "approved_by", "approved_on", "updated_at"])
    audit.money_action(
        approver,
        "correction.approved",
        "correction_cases",
        str(case.pk),
        before={"status": CASE_PENDING_APPROVAL},
        after={
            "status": CASE_APPROVED,
            "approved_on": on_date.isoformat(),
            "preview_hash": case.preview_hash,
            "bills": CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case).count(),
        },
    )
    return case


@dataclass(frozen=True)
class ExecutionResult:
    """ "N succeeded · N failed", and the rows behind both numbers."""

    case_id: str
    status: str
    succeeded: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]
    skipped_already_done: tuple[str, ...]

    def summary(self) -> str:
        return f"{len(self.succeeded)} succeeded · {len(self.failed)} failed" + (
            f" · {len(self.skipped_already_done)} already done" if self.skipped_already_done else ""
        )


def execute(
    case: CorrectionCase,
    *,
    issued_at: datetime,
    on_date: date,
    template_id: Any = None,
    template_version: int | None = None,
    actor: Any = None,
    prepared: dict[str, Any] | None = None,
    on_bill: Any = None,
) -> ExecutionResult:
    """The staged job. Per bill, idempotent, resumable, no rollback.

    `prepared` and `on_bill` (DEF-BIL-10091) serve the background
    approve-and-issue: the billing data the approval's check already gathered,
    by invoice id, handed to a case sent with rows so a bill is not gathered
    twice; and `on_bill(done, total)` after every bill, for the progress a
    screen shows. Neither changes what is written.

    Re-entrant BY DESIGN (rule 6): a row already `done` is skipped and reported
    as skipped rather than re-executed, so a retry storm, a double-clicked
    button and a resumed worker all leave exactly one credit note and one rebill
    per bill. `resume` is this function under another name — it is the same
    loop, because a resume that took a different path would be a second
    implementation of the thing that must not double-write.

    A per-bill failure is CAUGHT: its transaction rolled back (zero artifacts),
    its reason recorded on the row, and the loop carries on (BR-BIL-055's shape
    at correction scale). Nothing that already succeeded is touched.
    """
    if case.status not in (CASE_APPROVED, CASE_EXECUTING, CASE_OPEN):
        raise BillingRuleError(
            f"case {case.case_no or case.pk} is {case.status}: nothing executes without a "
            "recorded approval (BR-BIL-014, and the gate is server-side — US-BIL-017 "
            "TC-4). The preview is an artifact, not a permission.",
            br_ref="BR-BIL-014",
        )
    # BR-BIL-044: approval binds the artifact. Re-hash the pinned impacts and
    # refuse on drift — the stale artifact is RETAINED as evidence, never
    # overwritten, so what was approved stays readable.
    # DEF-BIL-10087 — in the order the rows were created (the preview's), so
    # the bills of one account draw on carried credit in the order Check
    # promised; an unordered read is the database's choice, not ours.
    rows = list(
        CorrectionCaseBill.objects.filter(tenant_id=case.tenant_id, case=case).order_by(
            "created_at", "id"
        )
    )
    current = _hash_of([row.impact for row in sorted(rows, key=lambda r: str(r.invoice_id))])
    stored = _hash_of(
        sorted(case.preview.get("bills", []), key=lambda impact: str(impact.get("invoice_id")))
    )
    if current != stored:
        raise BillingRuleError(
            "the inputs moved between preview and execute, so this case no longer "
            "describes what would happen (BR-BIL-044). Execution is refused, the approved "
            "preview is kept as evidence, and a fresh preview is required.",
            br_ref="BR-BIL-044",
        )

    case.status = CASE_EXECUTING
    case.save(update_fields=["status", "updated_at"])

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[str] = []
    for done, row in enumerate(rows, start=1):
        if on_bill is not None and done > 1:
            on_bill(done - 1, len(rows))
        if row.status == BILL_DONE:
            skipped.append(str(row.invoice_id))
            continue
        if row.status == BILL_ABANDONED:
            continue
        try:
            outcome = _execute_one(
                row,
                case=case,
                issued_at=issued_at,
                on_date=on_date,
                template_id=template_id,
                template_version=template_version,
                actor=actor,
                data=(prepared or {}).get(str(row.invoice_id)),
            )
        except (BillingRuleError, NotImplementedError) as failure:
            # ZERO artifacts: `_execute_one` is one transaction and it rolled
            # back. The row stays correctable and the case stays open.
            row.status = BILL_FAILED
            row.failure_reason = str(failure)
            row.save(update_fields=["status", "failure_reason", "updated_at"])
            failed.append((str(row.invoice_id), str(failure)))
            continue
        row.status = BILL_DONE
        row.failure_reason = None
        row.executed_on = on_date
        row.credit_note_id = outcome.credit_note_id
        row.rebill_invoice_id = outcome.rebill_invoice_id
        row.goodwill_adjustment_id = outcome.goodwill_adjustment_id
        row.document_instance_id = outcome.document_instance_id
        row.save(
            update_fields=[
                "status",
                "failure_reason",
                "executed_on",
                "credit_note",
                "rebill_invoice",
                "goodwill_adjustment",
                "document_instance",
                "updated_at",
            ]
        )
        succeeded.append(str(row.invoice_id))

    if on_bill is not None and rows:
        on_bill(len(rows), len(rows))
    unresolved = CorrectionCaseBill.objects.filter(
        tenant_id=case.tenant_id, case=case, status__in=(BILL_QUEUED, BILL_FAILED)
    ).exists()
    case.status = CASE_OPEN if unresolved else CASE_DONE
    case.executed_on = on_date
    case.save(update_fields=["status", "executed_on", "updated_at"])

    audit.money_action(
        actor,
        "correction.executed_batch",
        "correction_cases",
        str(case.pk),
        after={
            "status": case.status,
            "succeeded": len(succeeded),
            "failed": len(failed),
            "already_done": len(skipped),
            # BR-BIL-047 — the RULE stays here in the comment; the payload says
            # what happened in words, because S61 renders it to a clerk (DEF-2377).
            "batch_rollback": "not offered — each bill is corrected on its own",
        },
    )
    return ExecutionResult(
        case_id=str(case.pk),
        status=case.status,
        succeeded=tuple(succeeded),
        failed=tuple(failed),
        skipped_already_done=tuple(skipped),
    )


#: TC-4 — resume re-attempts ONLY the failures, and it is `execute` because a
#: second implementation of a write path is a second chance to double-write.
resume = execute

#: `CR-180-BRC10` — the key on `correction_cases.scope` that says the case was
#: sent with correction rows (`correction_case_items`) and is re-priced from
#: them. On the SCOPE because the scope is the operator's input and is not
#: inside the content hash; its value is the rows' count.
ITEMS_SCOPE_MARKER = "correction_items"


def _execute_one(
    row: CorrectionCaseBill,
    *,
    case: CorrectionCase,
    issued_at: datetime,
    on_date: date,
    template_id: Any,
    template_version: int | None,
    actor: Any,
    data: Any = None,
) -> corrections.ExecutedBill:
    """One bill, one transaction — the class decides which mechanism runs."""
    # ── `CR-180-BRC10` · A CASE SENT WITH CORRECTION ROWS RE-PRICES FROM THEM ─
    # A case opened at Send carries `correction_case_items`, and its bills were
    # previewed from those rows — a plan, a schedule version, a typed reading.
    # Re-pricing it here from "today's inputs" alone would issue a bill the
    # approver never saw, so it is handed to the one executor that reads the
    # rows. Every other case walks the path below exactly as before.
    if case.scope.get(ITEMS_SCOPE_MARKER):
        from apps.billing import correction_items

        return correction_items.execute_bill(
            row,
            case=case,
            issued_at=issued_at,
            on_date=on_date,
            template_id=template_id,
            template_version=template_version,
            actor=actor,
            data=data,
        )
    invoice = models.Invoice.objects.get(tenant_id=case.tenant_id, pk=row.invoice_id)
    impact = corrections.build_impact(
        invoice,
        reason_codes=tuple(case.reason_codes),
        correction_class=case.correction_class,
        posting_period=case.posting_period,
        goodwill_amount=(
            Decimal(str(case.scope.get("goodwill_amount")))
            if case.scope.get("goodwill_amount")
            else None
        ),
    )
    if case.correction_class == CLASS_RESTATEMENT:
        if template_id is None or template_version is None:
            raise BillingRuleError(
                "a rebill is issued with a template version pinned (BR-BIL-026) and none "
                "was supplied. `bill_templates` (r10 #4) does not exist, so the CURRENT "
                "version is the caller's fact — it is not defaulted from the original, "
                "because a bill silently reprinted on a superseded layout is the failure "
                "hard-won law 3 is about.",
                br_ref="BR-BIL-026",
            )
        return corrections.execute_restatement(
            invoice,
            impact=impact,
            reason=", ".join(case.reason_codes),
            issued_at=issued_at,
            on_date=on_date,
            template_id=template_id,
            template_version=template_version,
            actor=actor,
        )
    if case.correction_class == CLASS_CREDIT_ONLY:
        # PO 2026-08-12 (OQ-105/OQ-168): DR the write-off account, CR customer
        # credit. This used to call `refuse_credit_only_execution`, which no
        # longer exists — the debit side it was waiting for is now ruled.
        return corrections.execute_credit_only(
            invoice,
            impact=impact,
            amount=impact.delta.copy_abs(),
            reason=", ".join(case.reason_codes) or "goodwill",
            # `CR-180-BRC10` (found building B10): this passed `on_date`, a
            # `date`, into a parameter typed `datetime` whose first use is
            # `issued_at.date()` (`_allocate_credit_note_no`) — so every class-C
            # case executed through this loop raised `AttributeError` before a
            # row was written. `credit_notes.issued_at` is a DATETIME; the
            # caller's own `issued_at` is the moment the restatement branch
            # already stamps.
            issued_at=issued_at,
            actor=actor,
        )
    if case.correction_class == CLASS_DOCUMENT:
        from apps.billing import document_correction

        return document_correction.execute_document_correction(
            invoice,
            impact=impact,
            case=case,
            corrected_payload=dict(case.scope.get("corrected_payload") or {}),
            master_data_ref=case.scope.get("master_data_ref"),
            on_date=on_date,
            actor=actor,
        )
    raise BillingRuleError(  # pragma: no cover - class_for covers the vocabulary
        f"unknown correction class {case.correction_class!r}.", br_ref="BR-BIL-041"
    )


def abandon(case: CorrectionCase, *, reason: str, actor: Any, on_date: date) -> CorrectionCase:
    """Close a case over unresolved failures — explicitly, with a reason.

    BR-BIL-047: *"abandoning a failure is an explicit, reasoned, audited act
    rather than a case that quietly reports done."* A blank reason is refused,
    because "closed" with no explanation is indistinguishable from "finished".
    """
    if not (reason or "").strip():
        raise BillingRuleError(
            "closing a case over unresolved bills needs a reason (BR-BIL-047). Those "
            "bills are still wrong, and the record has to say why nobody is going to fix "
            "them.",
            br_ref="BR-BIL-047",
        )
    CorrectionCaseBill.objects.filter(
        tenant_id=case.tenant_id, case=case, status__in=(BILL_QUEUED, BILL_FAILED)
    ).update(status=BILL_ABANDONED)
    case.status = CASE_DONE
    case.closed_reason = reason
    case.closed_by_id = _actor_id(actor)
    case.save(update_fields=["status", "closed_reason", "closed_by", "updated_at"])
    audit.money_action(
        actor,
        "correction.abandoned",
        "correction_cases",
        str(case.pk),
        after={"reason": reason, "on_date": on_date.isoformat()},
    )
    return case


def unaddressed_bills(
    case: CorrectionCase, *, invoices: tuple[models.Invoice, ...]
) -> tuple[str, ...]:
    """TC-11 — bills that MATCH the scope but are not in the approved set.

    A bill issued into the same run after approval does not join the case
    (BR-BIL-046); it is REPORTED so the operator knows a second case is needed,
    rather than being silently corrected under someone else's signature or
    silently ignored.
    """
    pinned = {
        str(pk)
        for pk in CorrectionCaseBill.objects.filter(
            tenant_id=case.tenant_id, case=case
        ).values_list("invoice_id", flat=True)
    }
    return tuple(str(invoice.pk) for invoice in invoices if str(invoice.pk) not in pinned)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no S30 correction endpoint exists; the case layer is reachable only from tests today, REPORTED) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim RED transcripts — the per-bill
#         idempotency guard and the never-net-the-aggregate rule were each
#         broken deliberately, RUN, and the measured failure quoted before
#         either was trusted green (hard-won law 7)
# exceptions: (1) THERE IS NO ROLLBACK FUNCTION AND NONE MAY BE ADDED
#         (BR-BIL-047). `explain_no_batch_rollback()` is what the screen says
#         instead.
#         (2) THE APPROVAL ROLE IS NOT CHECKED HERE. US-BIL-017 owns the gate
#         record and the System-Admin rule (OQ-072 v1); this module records the
#         decision and refuses execution without one. The role enforcement has
#         no home yet — REPORTED.
#         (3) BR-BIL-042 IS IMPLEMENTED TWICE BECAUSE THE EPIC STATES IT TWICE:
#         a SINGLE case takes the strongest class present (US-BIL-015 TC-11), a
#         BULK case refuses a mix (US-BIL-016 TC-14). `refuse_mixed_class_in_bulk`
#         is that split and it keys on the scope, not on a preference.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
