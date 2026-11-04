# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-010 · US-BIL-011 · US-BIL-012 · US-BIL-013 · US-BIL-014 ·
#           US-BIL-032 · US-BIL-033 · US-BIL-034 (the one-time bill redesign,
#           PO-confirmed 2026-09-30) · Screens: S30
# Contract: 04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md
#           §2 (preview request, refusal, answer) · §4 (draft) · §5 (send)
# Plan:     12-one-time-bill-build-plan.md A2 · A3 · A4 · A6 · A7 · A8 · DB2 · DB3
# Rules:    BR-BIL-005 (idempotent run, who/when/link) · BR-BIL-018 (reason
#           coded) · BR-BIL-020 (lines only from rules and codes) · BR-BIL-024
#           (due = bill date + days) · BR-BIL-036 (paper is the floor) · B14
#           rule 31 (no id on screen) · rule 33 (≤ 6 words) · rule 35 (words in
#           the catalogue) · CLAUDE.md rules 1, 2, 3, 7
# Tests:    06-backend/tests/test_otb_a_one_time_api_contract.py
# Impacts:  apps/billing/api.py (the three one-time routes answer through this)
#           · 07-frontend/src/api/billingOpsEndpoints.ts (typed to the contract)
# ───────────────────────────────────────────────────────
"""THE ONE-TIME BILL'S WIRE — the contract's shapes, built from the engines' answers.

`apps/billing/one_time.py` is the ROUTER to the six engines and it prices
nothing; its payload grew over six weeks for a screen that has since been
redrawn (PO 2026-09-30, *"your drawing is correct now"*). The redrawn screen is
built to `13-one-time-bill-api-contract.md`, and this module is the translation
from what the engines answer to what that contract promises. **It computes no
money.** Every figure below is carried from `runs.price_account`,
`backbill.price_back_bill`, `fee_bill.price_charge_fee` or a drafted invoice's
own lines; nothing is summed except a group's subtotal, which is the sum of the
already-rounded line amounts it prints beside them.

WHY A SEPARATE MODULE AND NOT MORE `one_time.py`
────────────────────────────────────────────────
`one_time.py` is 🔒 (it mints an idempotency key) and its preview body is read
by five test files that assert the engines' own shape line for line. Rewriting
that body would move a reviewed money path to change a SCREEN's vocabulary.
So the engines' answer is left exactly as it was and this module reads it —
`one_time.preview(request, capture=…)` hands over the objects the preview
already built, so nothing is gathered or priced twice (a second gather inside
one payload is how two figures about one customer's money come to disagree on
one screen).

WHAT IS NOT HERE, EACH NAMED ON THE ANSWER'S `unavailable` LIST
───────────────────────────────────────────────────────────────
  * a TYPED reading that has not been saved is echoed on its row and is NOT
    priced — the screen saves it through `/read-batches` before it continues
    (contract §3), and pricing a value nobody committed would be a second path
    for a reading to reach a bill;
  * penalty evidence PHOTOS: the platform store (`tenancy.document_store`)
    constrains `stored_documents.kind` to a closed product vocabulary, and a
    penalty-evidence kind is a tenancy migration, not a billing one — so the
    evidence is TEXT on the bill snapshot only (build plan DB2).

A penalty's approval is RECORDED at Send and never gates it (PO ruling
2026-09-30, closing `OQ-BIL-12781`) — see `one_time_send`.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.billing import (
    backbill,
    bill_warnings,
    counted_service_line,
    day_share,
    final_bill,
    first_bill,
    gather,
    issue,
    models,
    one_time,
    payments_seam,
    posting_seam,
    runs,
    single,
    tenancy_seam,
)
from apps.billing.exceptions import BillingRuleError
from core import errors, idempotency
from core import tenancy as core_tenancy

# ══════════════════════════════════════════════════════════════════════════
# §2 · THE REQUEST, AND EVERY PROBLEM WITH IT AT ONCE (A2, A3)
# ══════════════════════════════════════════════════════════════════════════

#: The delivery choices the Send step offers (contract §5). The CHANNELS each
#: queues are `delivery_seam.DELIVERY_CHOICES`' — this is only the vocabulary.
DELIVERIES = ("email", "paper", "email_and_paper")

#: The final bill's settlement paths a clerk may CHOOSE (contract §2
#: `settlement.paths`). `refund` and `write_off` are never chosen — they are
#: the automatic answers `final_bill.settle` gives by threshold.
CHOSEN_SETTLEMENT_PATHS = ("collect", "payment_plan", "transfer")


def _text(payload: dict[str, Any], name: str) -> str:
    raw = payload.get(name)
    return "" if raw is None else str(raw).strip()


def _date_or_none(raw: Any) -> tuple[date | None, bool]:
    """`(date, present)` — absent/null/"" is `(None, False)`, garbage `(None, True)`."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None, False
    try:
        return date.fromisoformat(str(raw)), True
    except (TypeError, ValueError):
        return None, True


def _window_problems(
    start_raw: Any, end_raw: Any, *, start_field: str, end_field: str
) -> tuple[list[dict[str, Any]], date | None, date | None]:
    """One From/To pair: required, readable, and not ending before it starts."""
    problems: list[dict[str, Any]] = []
    start, _ = _date_or_none(start_raw)
    end, _ = _date_or_none(end_raw)
    if start is None:
        problems.append(
            {
                "field": start_field,
                "code": errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.periodRequired",
            }
        )
    if end is None:
        problems.append(
            {
                "field": end_field,
                "code": errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.periodRequired",
            }
        )
    elif start is not None and end < start:
        problems.append(
            {
                "field": end_field,
                "code": errors.VAL_RANGE,
                "message_key": "billing.oneTime.err.periodEndsBeforeStart",
            }
        )
    return problems, start, end


def _due_days_problem(raw: Any) -> tuple[dict[str, Any] | None, int | None]:
    """Days to pay: REQUIRED on every kind, a whole number, zero or more.

    `0` is lawful (due ON the bill date, BR-MET-009 `due_days ≥ 0`) and is kept
    apart from *nobody typed one* by `is None`, never by truthiness. A bool is
    refused even though Python calls it an int — `true` is not a number of days.
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return (
            {
                "field": "due_days",
                "code": errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.dueDaysRequired",
            },
            None,
        )
    value: int | None = None
    if isinstance(raw, bool):
        value = None
    elif isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
    if value is None or value < 0:
        return (
            {
                "field": "due_days",
                "code": errors.VAL_FORMAT,
                "message_key": "billing.oneTime.err.dueDaysInvalid",
            },
            None,
        )
    return None, value


def problems_in(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """EVERY step-1 problem in one pass, each on its own field (contract §2, A3).

    The order is the screen's, top to bottom, because the screen lists them in
    the order it receives them: account · period(s) · reason · charge · bill
    date · days to pay. The kind is NOT checked here — it is chosen by a card,
    never typed, and `one_time.checked_kind` refuses an unknown one by name.

    ⚠ **THE MOVE-IN CHECK (`notFirstBill`) IS ASKED ONLY WHEN THE WINDOW IS
    OTHERWISE SOUND**, because *"move-in is outside this period"* about a
    period that ends before it starts would name the wrong problem.

    `moveInReadingRequired` is NOT raised here: whether a move-in reading is on
    file is a Meter Reads fact the preview's reading rows state (`previous.
    on_file`), and step 2 is where the clerk types it. The key is the screen's.
    """
    kind = _text(payload, "kind")
    problems: list[dict[str, Any]] = []
    account_id = _text(payload, "account_id")
    if not account_id:
        problems.append(
            {
                "field": "account_id",
                "code": errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.accountRequired",
            }
        )

    window_ok = False
    start: date | None = None
    end: date | None = None
    if kind in one_time.SUB_PERIOD_KINDS:
        rows = payload.get("sub_periods")
        if not isinstance(rows, list) or not rows:
            rows = [{}]
        window_ok = True
        sound: list[tuple[date, date, int]] = []
        for index, row in enumerate(rows):
            row = row if isinstance(row, dict) else {}
            found, row_start, row_end = _window_problems(
                row.get("period_start"),
                row.get("period_end"),
                start_field=f"sub_periods[{index}].period_start",
                end_field=f"sub_periods[{index}].period_end",
            )
            problems.extend(found)
            window_ok = window_ok and not found
            if not found and row_start is not None and row_end is not None:
                sound.append((row_start, row_end, index))
        # ── `DEF-BIL-8322` · TWO PERIODS THAT SHARE A DAY ─────────────────
        # The engine refuses overlapping periods (`backbill._checked_sub_
        # periods`: they bill the same days twice) — as a bare refusal with no
        # field and no key, which reached the clerk as the frame's generic line
        # (PO report, 2.411.4: *Sep 30–Sep 30* and *Aug 30–Sep 30*). So it is
        # found HERE, with the other step-1 problems, on the row that overlaps:
        # periods are taken in date order (the ORDER a clerk typed them in is
        # not a problem — `request_from` sorts them), and each one that starts
        # on or before the previous one's end is named on its own From.
        previous: tuple[date, date, int] | None = None
        for row_start, row_end, index in sorted(sound):
            if previous is not None and row_start <= previous[1]:
                problems.append(
                    {
                        "field": f"sub_periods[{index}].period_start",
                        "code": errors.VAL_RANGE,
                        "message_key": "billing.oneTime.err.periodOverlaps",
                    }
                )
                window_ok = False
            if previous is None or row_end > previous[1]:
                previous = (row_start, row_end, index)
    elif kind not in one_time.CHARGE_CODE_KINDS:
        found, start, end = _window_problems(
            payload.get("period_start"),
            payload.get("period_end"),
            start_field="period_start",
            end_field="period_end",
        )
        problems.extend(found)
        window_ok = not found
        # ── `DEF-BIL-8288` · A FIRST BILL'S TO MUST BE AFTER ITS MOVE-IN ──────
        # On a first bill From IS the move-in date (`one_time.first_bill_move_in`),
        # so To on the same day is a bill for the move-in day alone. The PO's
        # report (2.412.3, AC-2026-00054, move-in and To both 07/01/2026) reached
        # the clerk as the generic *"can't be created as asked"*; it is found
        # here, on To, before anything is priced. An interim bill of one day is
        # untouched — it has no move-in.
        if (
            kind == one_time.KIND_FIRST
            and window_ok
            and start is not None
            and end is not None
            and end <= start
        ):
            problems.append(
                {
                    "field": "period_end",
                    "code": errors.VAL_RANGE,
                    "message_key": "billing.oneTime.err.toNotAfterMoveIn",
                }
            )
            window_ok = False

    # ⚠ **NO `notFirstBill` CHECK FROM 2026-09-30 (PO change, *"Move -date
    # should have date picker cleark will overwrite it"*).** It compared the
    # account's RECORDED move-in date with the window and refused a window that
    # did not contain it — so a clerk correcting the date for this bill was
    # refused for doing what the PO asked. The clerk's date is the window's
    # start (`one_time.first_bill_move_in`), which is inside it by definition.
    # The key stays in the catalogues for the day a rule needs it again.

    if kind in one_time.REASON_CODE_KINDS:
        reason = _text(payload, "reason_code")
        if not reason:
            problems.append(
                {
                    "field": "reason_code",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "billing.oneTime.err.reasonRequired",
                }
            )
        else:
            active = tenancy_seam.active_reason_codes()
            if active is not None and reason.lower() not in {code.lower() for code in active}:
                problems.append(
                    {
                        "field": "reason_code",
                        "code": errors.VAL_UNKNOWN_LOOKUP,
                        "message_key": "billing.oneTime.err.reasonUnknown",
                    }
                )

    if kind in one_time.CHARGE_CODE_KINDS and not _text(payload, "charge_code"):
        problems.append(
            {
                "field": "charge_code",
                "code": errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.chargeRequired",
            }
        )

    bill_date, present = _date_or_none(payload.get("bill_date"))
    if bill_date is None:
        problems.append(
            {
                "field": "bill_date",
                "code": errors.VAL_FORMAT if present else errors.VAL_REQUIRED,
                "message_key": "billing.oneTime.err.billDateRequired",
            }
        )

    # DEF-RAT-8753 — an amount typed for a code priced *entered when used*
    # must be a number; whether the code takes one at all is `fee_bill`'s rule.
    if _entered_amount(payload) is _MALFORMED:
        problems.append(
            {
                "field": "entered_amount",
                "code": errors.VAL_FORMAT,
                "message_key": "billing.oneTime.err.amountRequired",
            }
        )

    due_problem, _ = _due_days_problem(payload.get("due_days"))
    if due_problem is not None:
        problems.append(due_problem)
    return problems


#: `_entered_amount`'s answer for a value that is not a number.
_MALFORMED = object()


def _entered_amount(payload: dict[str, Any]) -> Any:
    """`DEF-RAT-8753` — the clerk's amount for a `per_case` code: a `Decimal`,
    `None` when absent, or `_MALFORMED`. Never a float (hard rule 2)."""
    raw = payload.get("entered_amount")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, float):
        return _MALFORMED
    try:
        value = Decimal(str(raw).strip())
    except Exception:  # noqa: BLE001 — InvalidOperation and friends
        return _MALFORMED
    return value if value.is_finite() else _MALFORMED


def only_days_to_pay_missing(problems: list[dict[str, Any]]) -> bool:
    """True when the ONE problem is an empty *Days to pay*.

    The preview still answers then — with the account block and its cycle's
    days-to-pay in `defaults` — because the screen PREFILLS that field from the
    preview (design §2, *"defaults from the account's cycle"*): refusing the
    preview for the very field whose default it carries would leave the clerk
    typing a number the product already knows. The DRAFT refuses it; nothing is
    written without it (BR-BIL-024).
    """
    return (
        len(problems) == 1 and problems[0]["message_key"] == "billing.oneTime.err.dueDaysRequired"
    )


def account_problems(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Step-1 problems that are FACTS ABOUT THE ACCOUNT, not about what was typed.

    `DEF-BIL-8330` — PO ruling 2026-09-30, option A: *"you have to show the
    message /warning to user - A · Refuse until the account has a cycle"*. A
    FIRST bill for an account on no billing cycle is refused on the ACCOUNT
    field with its own key — *"No billing cycle. Assign one on the account."*
    — and nothing is priced (`one_time.refuse_a_first_bill_with_no_cycle` is
    the engine's own refusal behind this).

    Kept apart from `problems_in`, which reads only the request and touches no
    row: this one asks customers and metering. It is silent where the account
    field has its OWN problem — empty, malformed, or an id no account holds
    (customers answers those as absent, hard rule 1) — so a clerk is never told
    *"no billing cycle"* about an account that is not there.
    """
    # PO 2026-10-01 — the FINAL bill too (*"same as first bill"*).
    if _text(payload, "kind") not in one_time.KINDS_NEEDING_A_CYCLE:
        return []
    account_id = _text(payload, "account_id")
    if not account_id:
        return []
    try:
        has_cycle = one_time.account_has_a_billing_cycle(account_id)
    except errors.NotFoundError:
        return []
    if has_cycle:
        return []
    return [
        {
            "field": "account_id",
            "code": errors.VAL_REQUIRED,
            "message_key": one_time.NO_BILLING_CYCLE_KEY,
        }
    ]


def refuse(problems: list[dict[str, Any]]) -> errors.ValidationError:
    """The 422 carrying every problem. The envelope's own key is the FIRST
    problem's, so the one sentence a screen shows above the form is a real one
    rather than a generic *"something is wrong"*."""
    first = problems[0]["message_key"]
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=first,
        field_errors=[dict(problem) for problem in problems],
    )


def request_from(payload: dict[str, Any]) -> one_time.OneTimeRequest:
    """The dataclass the engines take — built only once `problems_in` found none
    (or only the days-to-pay the preview tolerates).

    ⚠ **STILL NOTHING THAT CAN CARRY AN AMOUNT (BR-BIL-020).** The three members
    this adds are WORDS a clerk chose or typed — a settlement path from a closed
    list, the evidence text and the fee's note — and each lands in the draft's
    snapshot as a record, never in any arithmetic.
    """
    kind = one_time.checked_kind(payload.get("kind"))
    sub_periods: tuple[tuple[date, date], ...] = ()
    start: date | None = None
    end: date | None = None
    if kind in one_time.SUB_PERIOD_KINDS:
        # `DEF-BIL-8322` — in DATE order, whatever order they were typed in:
        # the engine prices them as a sequence and refuses one that starts
        # before the previous one ends.
        sub_periods = tuple(
            sorted(
                (
                    date.fromisoformat(str(row["period_start"])),
                    date.fromisoformat(str(row["period_end"])),
                )
                for row in payload.get("sub_periods") or ()
            )
        )
    elif kind not in one_time.CHARGE_CODE_KINDS:
        start = date.fromisoformat(str(payload.get("period_start")))
        end = date.fromisoformat(str(payload.get("period_end")))
    bill_date, _ = _date_or_none(payload.get("bill_date"))
    _, due_days = _due_days_problem(payload.get("due_days"))
    scope = payload.get("scope_services")
    return one_time.OneTimeRequest(
        account_id=_text(payload, "account_id"),
        kind=kind,
        period_start=start,
        period_end=end,
        bill_date=bill_date,
        due_days=due_days,
        sub_periods=sub_periods,
        reason_code=_text(payload, "reason_code"),
        charge_code=_text(payload, "charge_code"),
        # DEF-RAT-8753 — `per_case` codes only; refused beside any other code
        # by `fee_bill.charge_code_line` (BR-BIL-020).
        entered_amount=(
            None if _entered_amount(payload) in (None, _MALFORMED) else _entered_amount(payload)
        ),
        scope_services=None if scope is None else tuple(str(code) for code in scope),
        settlement_path=_text(payload, "settlement_path"),
        evidence=_text(payload, "evidence"),
        note=_text(payload, "note"),
        readings=tuple(
            dict(row) for row in (payload.get("readings") or ()) if isinstance(row, dict)
        ),
        # 🔒 DEF-BIL-9076 — the services whose in-period rollover the clerk
        # ACCEPTED; any other service whose meter rolled over is held by name.
        accepted_rollovers=tuple(
            str(code) for code in (payload.get("accepted_rollovers") or ()) if code
        ),
    )


def extras_problems(payload: dict[str, Any], *, kind: str) -> list[dict[str, Any]]:
    """The DRAFT's own checks on the three snapshot fields (DB2, DB3).

    Only a settlement path OUTSIDE the closed list is refused here; whether the
    chosen path is available for THIS remainder is `final_bill.settle`'s rule
    and is asked of it at draft time, in its own words.
    """
    path = _text(payload, "settlement_path")
    if kind == one_time.KIND_FINAL and path and path not in CHOSEN_SETTLEMENT_PATHS:
        return [
            {
                "field": "settlement_path",
                "code": errors.VAL_UNKNOWN_LOOKUP,
                "message_key": "billing.oneTime.err.settlementPathUnknown",
            }
        ]
    return []


def _moved_in_on_or_none(account_id: str) -> date | None:
    """The account's move-in date, or None where it cannot be read — the
    engine then refuses by name, which is its job and not this check's."""
    try:
        return one_time._moved_in_on(account_id)
    except BillingRuleError:
        return None


# ══════════════════════════════════════════════════════════════════════════
# A PRICING REFUSAL — ITS OWN SENTENCE, NEVER A GENERIC ONE (A3, DEF-BIL-8287)
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **UNTIL 2026-09-30 A REFUSAL WITH NO RATING KEY FELL BACK TO ONE OF TWO
# GENERIC LINES** — *"Water can't be priced. Check its rates."*
# (`billing.oneTime.err.notPriced`) when it named a service, and *"This one-time
# bill can't be created as asked …"* (`billing.oneTime.refused`) when it did
# not. The engine's own reason travelled only in `params.detail`, which is never
# rendered (BR-SHL-020 r2), so neither the clerk nor support could tell what to
# fix. PO report on 2.412.3 (`DEF-BIL-8287`, `DEF-BIL-8288`) and the PO's ruling
# the same day: *"we have to show the warning or error to user - specific"*.
#
# So every reason the pricing path refuses with has its OWN key below, carrying
# the fact it is about (service, date, size, unit) as params. A reason the
# engine states too many ways for one key (`ENGINE_SENTENCE_REASONS`) is first
# CLASSIFIED against the engine's words, and what no pattern names is shown as
# the engine's own sentence, cleaned of ids and rule codes. The two generic keys
# are no longer reached from here. `test_def_bil_8287_named_pricing_refusals.py`
# scans every `GatherProblem` raise site in billing and fails on a reason with
# no entry — which is the only way a new reason cannot quietly go generic.

#: The engine's own sentence, cleaned (`engine_sentence`), for a refusal no key
#: names. English whatever the catalogue: the server holds no locale.
ENGINE_SENTENCE_KEY = "billing.oneTime.err.engineSaid"

#: reason → the clerk's key. The keys name what is missing and where to fix it.
PRICING_REFUSAL_KEYS: dict[str, str] = {
    gather.GATHER_NO_UNIT: "billing.oneTime.err.noUnit",
    gather.GATHER_NO_PLAN: "billing.oneTime.err.noPlan",
    gather.GATHER_PLAN_UNPUBLISHED: "billing.oneTime.err.planDraft",
    gather.GATHER_NO_TARIFF: "billing.oneTime.err.nothingPriced",
    gather.GATHER_NO_VERSION: "billing.oneTime.err.noRateOnDate",
    gather.GATHER_NO_CURRENCY: "billing.oneTime.err.noCurrency",
    gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE: "billing.oneTime.err.noBaseForType",
    gather.GATHER_SIZE_UNRESOLVED: "billing.oneTime.err.noSize",
    gather.GATHER_JURISDICTION_UNSTATED: "billing.oneTime.err.cityLimits",
    gather.GATHER_COVERAGE_UNRESOLVED: "billing.oneTime.err.coverageUnknown",
    gather.GATHER_COVERAGE_MULTI_PLAN: "billing.oneTime.err.coverageTwoPlans",
    gather.GATHER_COVERAGE_SERVICE_TWICE: "billing.oneTime.err.coverageTwice",
    gather.GATHER_PARTIAL_CUT: "billing.oneTime.err.partialCut",
    gather.GATHER_UNBILLED_UNIT_UNREADABLE: "billing.oneTime.err.emptyUnitsUnknown",
    gather.GATHER_UNBILLED_UNITS_UNPRICEABLE: "billing.oneTime.err.emptyUnitsUnpriced",
    runs.ANCHOR_METER_EXCHANGED: "billing.oneTime.err.meterExchanged",
    runs.ANCHOR_REGISTER_WENT_BACKWARDS: "billing.oneTime.err.readBackwards",
    runs.ANCHOR_MULTIPLIER_UNSTATED: "billing.oneTime.err.multiplierMissing",
    runs.ANCHOR_TOU_UNANCHORABLE: "billing.oneTime.err.touUnanchored",
    runs.POSSIBLE_ROLLOVER: "billing.oneTime.err.rollover",
    # DEF-BIL-8244 — the same fact as the exchange, for a one-time bill.
    runs.METER_SWAPPED: "billing.oneTime.err.meterExchanged",
    runs.READ_HAS_NO_UNIT: "billing.oneTime.err.readNoUnit",
    "reading_has_no_unit": "billing.oneTime.err.readNoUnit",
    runs.RUN_READS_UNAVAILABLE: "billing.oneTime.err.readsUnavailable",
    runs.CALC_UNRESOLVED_READ: "billing.oneTime.err.noReading",
    runs.CALC_ASSET_COUNT_UNAVAILABLE: "billing.oneTime.err.assetCountUnknown",
    runs.CALC_INSTALLED_CAPACITY_UNRESOLVED: "billing.oneTime.err.capacityUnknown",
    single.SINGLE_NOT_BILLABLE: "billing.oneTime.err.notBillable",
    single.SINGLE_HELD_PERIOD: "billing.oneTime.err.held",
    backbill.BACKBILL_NO_REASON_CODE: "billing.oneTime.err.reasonRequired",
    backbill.BACKBILL_OVER_CAP: "billing.oneTime.err.overCap",
    backbill.BACKBILL_NO_SUB_PERIODS: "billing.oneTime.err.periodsRequired",
    backbill.BACKBILL_BAD_SUB_PERIODS: "billing.oneTime.err.periodOverlaps",
    backbill.BACKBILL_SPLIT_BROKEN: "billing.oneTime.err.rateChangesInPeriod",
    backbill.BACKBILL_NO_VERSION: "billing.oneTime.err.noRateInPeriod",
    backbill.BACKBILL_NO_ESTIMATE: "billing.oneTime.err.cannotEstimate",
    backbill.BACKBILL_NO_ESTIMATE_SOURCE: "billing.oneTime.err.pastUsageUnavailable",
    final_bill.FINAL_ACCOUNT_ALREADY_CLOSED: "billing.oneTime.err.alreadyClosed",
    final_bill.FINAL_DEPOSIT_INTEREST_UNAVAILABLE: "billing.oneTime.err.depositInterest",
    final_bill.FINAL_PATH_UNAVAILABLE: "billing.oneTime.err.settlementPath",
}

#: Reasons whose engine states many different faults under one code — the
#: R1–R7 chain's refusals, rating's own pricing refusals and a fee that cannot be
#: raised. Each is CLASSIFIED against the engine's words (`_CLASSIFIED`); what no
#: pattern names is shown as the engine's own sentence.
ENGINE_SENTENCE_REASONS: frozenset[str] = frozenset(
    {gather.GATHER_RULED_PATH_REFUSED, "not_priced", "fee_cannot_be_raised"}
)

#: `GATHER_NO_TARIFF` and `GATHER_NO_BASE_FOR_CUSTOMER_TYPE` raised FOR A
#: SERVICE come from `gather._base_charge_for`, and their sentence is rating's
#: own short clerk sentence about the base charge code (*"2 base charge codes
#: for water. Scope them on Charge codes."*, *"BASE-W has no price for W-58.
#: Price it on the charge code."*). That names the code and the size, which no
#: key here could, so it is shown as it stands.
_RATING_SENTENCE_WHEN_A_SERVICE_IS_NAMED = frozenset(
    {gather.GATHER_NO_TARIFF, gather.GATHER_NO_BASE_FOR_CUSTOMER_TYPE}
)

#: (key, pattern) — tried in order against the engine's sentence. Each pattern
#: names the fact its key carries. ⚠ **A PATTERN READS ENGLISH PROSE THAT RATING
#: OWNS**, so a reworded refusal falls through to the engine's own sentence —
#: specific still, never generic. The durable fix is rating raising these with
#: its own `message_key` (as `DEF-RAT-7991` did for nine sites); `resolution.py`
#: is human-owned, so it is recorded in `DEF-BIL-8287`'s row rather than done here.
_CLASSIFIED: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "billing.oneTime.err.sizeNotPriced",
        re.compile(
            r"connection size '(?P<size>[^']+)' has no row on .*?pricing '(?P<service>[a-z_]+)'"
        ),
    ),
    (
        "billing.oneTime.err.noSize",
        re.compile(
            r"service '(?P<service>[a-z_]+)' has no connection size RECORDED"
            r"|no connection size was resolved for '(?P<service2>[a-z_]+)'"
            r"|'(?P<service3>[a-z_]+)' has no connection size on this meter"
        ),
    ),
    (
        "billing.oneTime.err.noMeter",
        re.compile(r"the plan covers '(?P<service>[a-z_]+)' and the unit has no meter"),
    ),
    (
        "billing.oneTime.err.unitMismatch",
        re.compile(
            r"service '(?P<service>[a-z_]+)': read unit '(?P<read_unit>[^']+)' is not the "
            r"billed unit '(?P<rate_unit>[^']+)'"
        ),
    ),
    (
        "billing.oneTime.err.noTiers",
        re.compile(r"tariff for service '(?P<service>[a-z_]+)' has no tiers"),
    ),
)

#: Every key `_CLASSIFIED` can answer — for the catalogue test.
CLASSIFIED_KEYS: tuple[str, ...] = tuple(key for key, _ in _CLASSIFIED)

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_RULE_ID = r"(?:BR|DEF|OQ|CR|US|GT|NFR)-[A-Z0-9/-]+"
_ISO_DAY = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def engine_sentence(raw: Any) -> str:
    """The engine's refusal as ONE plain sentence a clerk can read.

    The engine writes for the record: a step prefix (*"R3: "*), a caller prefix
    (*"rating refused to price this bill (water): "*), database ids, rule codes
    and a paragraph of reasoning. B14 rule 31 keeps ids off a screen and rule 33
    puts rationale at zero words, so what is kept is the FIRST sentence — the
    fact — with every id and rule code removed. It is English: the server holds
    no locale, and a specific English sentence beats a generic translated one.
    """
    text = " ".join(str(raw or "").split())
    text = re.sub(r"^rating refused to price this bill \([^)]*\):\s*", "", text)
    text = re.sub(r"^the ruled path could not price this account:\s*", "", text)
    text = re.sub(r"^R\d+[a-z]?:\s*", "", text)
    text = re.sub(r"^service '?[a-z_]+'?:\s*", "", text)
    text = re.sub(
        r"\b(unit|plan|account|schedule|version|tariff|exclusion)\s+'?"
        + _UUID.pattern
        + r"'?(?:'s)?",
        lambda match: f"this {match.group(1)}",
        text,
        flags=re.I,
    )
    text = _UUID.sub("", text)
    # `DEF-BIL-8831` — THE FIRST SENTENCE IS CUT BEFORE THE RULE CODES GO, NOT
    # AFTER. The split below finds a sentence by the capital letter that starts
    # the next one, and the engine often starts its second sentence WITH a rule
    # code (*"… arrived. BR-RAT-021: reads arrive …"*, *"… arrived. BR-RAT-014's
    # measurement …"*). Stripped first, that capital is gone, nothing splits, and
    # the clerk read *"arrived.'s measurement is a MAX-DEMAND REGISTER READ"*.
    text = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9'\"])", text, maxsplit=1)[0]
    text = re.sub(r"\s*\([^()]*" + _RULE_ID + r"[^()]*\)", "", text)
    text = re.sub(r"\s*" + _RULE_ID + r":?", "", text)
    text = text.replace("`", "")
    first = text.strip()
    first = " ".join(first.split()).strip(" ,;:")
    if not first:
        return ""
    first = first[0].upper() + first[1:]
    return first if first.endswith((".", "!", "?")) else f"{first}."


def _clerk_day(raw: str) -> str:
    """`2026-08-31` → `Aug 31, 2026`. English month names, the same stated limit
    as rating's `clerk_date`: the server holds no locale."""
    day = date.fromisoformat(raw)
    return f"{day.strftime('%b')} {day.day}, {day.year}"


def _classified(detail: str) -> tuple[str, dict[str, Any]] | None:
    for key, pattern in _CLASSIFIED:
        match = pattern.search(detail)
        if match is None:
            continue
        found = {name: value for name, value in match.groupdict().items() if value}
        facts: dict[str, Any] = {}
        service = found.get("service") or found.get("service2") or found.get("service3")
        if service:
            facts["service_code"] = service
            facts["service"] = _service_name(service)
        for name in ("size", "read_unit", "rate_unit"):
            if name in found:
                facts[name] = found[name]
        return key, facts
    return None


def pricing_refusal(gap: dict[str, Any]) -> errors.BizError:
    """A real setup error the engine refused on, as ONE named 422 — ITS cause.

    In order: rating's own clerk key where the refusal carries one
    (`DEF-RAT-7991`); the reason's own key (`PRICING_REFUSAL_KEYS`), with the
    service and the date it is about; a classified engine sentence; and last the
    engine's own sentence, cleaned (`ENGINE_SENTENCE_KEY`). The engine's full
    text still travels in `params.detail` for the audit row and the log.
    """
    service_code = gap.get("service_code")
    reason = gap.get("reason")
    detail = str(gap.get("detail") or "")
    params: dict[str, Any] = {
        "reason": reason,
        "service": _service_name(service_code) if service_code else "",
        "service_code": service_code,
        "detail": gap.get("detail"),
    }
    named = gap.get("message_key")
    if named:
        params.update(gap.get("message_params") or {})
        return errors.BizError(
            errors.BIZ_COMPLETENESS, br_ref="BR-BIL-020", message_key=named, params=params
        )
    key = PRICING_REFUSAL_KEYS.get(str(reason))
    if key is not None and not (
        service_code and reason in _RATING_SENTENCE_WHEN_A_SERVICE_IS_NAMED
    ):
        day = _ISO_DAY.search(detail)
        if day is not None:
            params["date"] = _clerk_day(day.group(1))
        return errors.BizError(
            errors.BIZ_COMPLETENESS, br_ref="BR-BIL-020", message_key=key, params=params
        )
    classified = _classified(detail)
    if classified is not None:
        key, facts = classified
        params.update(facts)
        return errors.BizError(
            errors.BIZ_COMPLETENESS, br_ref="BR-BIL-020", message_key=key, params=params
        )
    return engine_refusal(detail, params=params, br_ref="BR-BIL-020")


def engine_refusal(
    detail: Any, *, params: dict[str, Any] | None = None, br_ref: str = "BR-BIL-020"
) -> errors.BizError:
    """The engine's own sentence as the refusal (`DEF-BIL-8287`/`8288`).

    Used where no key names the cause: a pricing refusal no pattern classifies,
    and a bare rule refusal on the one-time routes (`api._one_time_refusal`). A
    sentence that cleans down to nothing — an id and a rule code and no words —
    still refuses by this key, with the service it is about where there is one,
    so the clerk is never handed the generic line.
    """
    body = dict(params or {})
    body.setdefault("detail", detail)
    sentence = engine_sentence(detail)
    if not sentence:
        service = body.get("service") or ""
        sentence = f"{service} can't be priced.".strip() if service else "The bill can't be priced."
    body["sentence"] = sentence
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key=ENGINE_SENTENCE_KEY,
        params=body,
    )


def _service_name(service_code: Any) -> str:
    return str(tenancy_seam.service_names_by_code().get(str(service_code)) or service_code)


# ══════════════════════════════════════════════════════════════════════════
# §2 · THE ANSWER (A4)
# ══════════════════════════════════════════════════════════════════════════

#: Metering's overlay reason for a typed value it would not price because the
#: usage came out negative (BR-MET-052) — shown on the row as *Below last
#: reading* (`DEF-BIL-8300`, J70 E10).
READ_REFUSED_BELOW_LAST = "read_flagged"

#: The pricing refusals a PREVIEW answers `200` for rather than refusing: a
#: meter still waiting for its reading, which step 2 is where the clerk types
#: (`DEF-BIL-8300`). Every other pricing refusal is a real setup error and is
#: still refused, named and naming its service.
PREVIEW_WAITS_FOR_A_READING = frozenset({"missing_read_undecided_at_calculate"})

#: What the contract's answer cannot carry yet, said on the wire so a screen can
#: never read an absence as a fact. Each is a real limit with its reason.
ANSWER_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "a_typed_reading_is_provisional_until_saved",
        "br_ref": "contract §2–§3 · BR-MET-017 · DEF-BIL-8300",
        "detail": "a reading posted in `readings` prices the PREVIEW as provisional, through "
        "Meter Reads' own overlay, and nothing is written. The DRAFT prices only readings saved "
        "through /read-batches (stage, validate, post), which the screen does on step 2's "
        "Continue before it asks again.",
    },
    {
        "code": "penalty_evidence_is_text_only",
        "br_ref": "build plan DB2",
        "detail": "penalty evidence is kept as TEXT on the bill's snapshot. Photos would need a "
        "new kind in the platform document store (`stored_documents.kind` is a closed "
        "product vocabulary owned by tenancy), which is not a billing migration.",
    },
)


def _money(value: Any) -> str:
    """A money figure on the wire — the 4-decimal string (CLAUDE.md rule 2)."""
    return str(Decimal(str(value)).quantize(Decimal("0.0001")))


def _percent_points(fraction: Any) -> str:
    """A tax rate on the wire in percent POINTS, 6 decimals (CLAUDE.md rule 2):
    the engine's `0.020000` is served as `2.000000` (DEF-BIL-8303)."""
    return str((Decimal(str(fraction)) * 100).quantize(Decimal("0.000001")))


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return text[:10] if text else None


def _account_detail(account_id: str) -> dict[str, Any]:
    read = gather._resolve("customers", "account_detail")
    return dict(read(account_id)) if read is not None else {}


def _cycle_terms(unit_id: Any) -> dict[str, Any] | None:
    read = gather._resolve("metering", "cycle_terms_for_unit")
    if read is None or not unit_id:
        return None
    return read(unit_id)


def _cycle_label(terms: dict[str, Any] | None) -> str | None:
    """The card's Cycle: the cycle's name, or its CODE when it has no name.

    `DEF-BIL-8332` — `cycles.name` is optional (the J70 demo's `J70-MONTHLY`
    has none), and serving the name alone printed *None* for an account that
    IS on a cycle; since `DEF-BIL-8330` the screen reads null as *no cycle* and
    would refuse its first bill. So null means exactly one thing: no cycle.
    """
    if terms is None:
        return None
    return terms.get("name") or terms.get("code") or None


def account_block(
    request: one_time.OneTimeRequest, *, detail: dict[str, Any], data: Any, internal: dict[str, Any]
) -> dict[str, Any]:
    """§2 `account` — who and where, read once the clerk has picked (US-BIL-034 TC-5).

    The ADDRESS is walked from the premises (hard rule 8): customers' own list
    cell (`premise`) beside the unit's LABEL, the same two facts the dropdown's
    option prints. The PLAN is the one the engine priced on
    (`AccountBillingData.rate_plan_name`), never a second read that could name
    another. Days to pay come from the unit's ONE cycle, or null.
    """
    terms = _cycle_terms(detail.get("unit_id"))
    snapshot = getattr(data, "snapshot", None) or {}
    plan = getattr(data, "rate_plan_name", None) or (snapshot.get("plan") or {}).get("name")
    # DEF-BIL-8302 — customers' `premise` cell is ALREADY "1408 Elm St · Unit A"
    # (`selectors._premise_cell` joins the address and the unit's label), so
    # appending `unit_label` printed "… · Unit A · Unit A". The label stands
    # alone only when no premise is served.
    address = detail.get("premise") or detail.get("unit_label")
    return {
        "id": str(request.account_id),
        "account_no": detail.get("account_no") or internal.get("account_no"),
        "name": internal.get("name"),
        "address": address or snapshot.get("service_address"),
        "plan": plan,
        "status_name": detail.get("status_name"),
        "balance": detail.get("balance"),
        "currency": detail.get("balance_currency") or detail.get("currency"),
        "cycle_due_days": None if terms is None else terms.get("due_days"),
        # `DEF-BIL-8329` — the card's Cycle cell printed `cycle_due_days`
        # (*"10 days to pay"*) because no cycle NAME was served. The name, or
        # null for a unit on no cycle, which the card says as *None*.
        "cycle_name": _cycle_label(terms),
        "last_bill_on": _iso(detail.get("last_bill_at")),
        "moved_in_on": _iso(detail.get("opened_at")),
    }


def _unit_plan_name(unit_id: Any) -> str | None:
    """The unit's plan NAME (BR-CUS-014: the account derives its plan from the
    unit), read through the same two seams `gather` walks — metering's unit row
    for the id, rating's `plan_ref` for the name. None when either is silent."""
    unit_row = gather._resolve("metering", "unit_row")
    plan_ref = gather._resolve("rating", "plan_ref")
    if unit_row is None or plan_ref is None or not unit_id:
        return None
    try:
        unit = unit_row(unit_id)
    except Exception:  # noqa: BLE001 — a unit metering cannot find names no plan
        return None
    plan_id = getattr(unit, "rate_plan_id", None)
    plan = plan_ref(plan_id) if plan_id else None
    return (plan or {}).get("name")


def account_facts(account_id: str) -> dict[str, Any]:
    """Step 1's account card, read from the ACCOUNT — never from a bill.

    ── `DEF-BIL-8281` (PO report on the deployed 2.411.4) ─────────────────
    The card's Plan, Cycle and Last bill, and the Days-to-pay default, were
    read only from the PREVIEW's `account` block; the preview is refused while
    any required field on step 1 is empty, so the card read *"—"* on every
    figure exactly when the clerk was filling it in. These are facts about the
    account, and this answers them the moment it is chosen — the same keys as
    §2's `account`, so the screen reads one shape from either source.

    Writes nothing and prices nothing. The plan is the unit's (BR-CUS-014),
    days to pay the unit's cycle, the move-in date `accounts.opened_at`.
    """
    detail = _account_detail(account_id)
    unit_id = detail.get("unit_id")
    terms = _cycle_terms(unit_id)
    return {
        "id": str(account_id),
        "account_no": detail.get("account_no"),
        "name": one_time._customer_name(account_id),
        "address": detail.get("premise") or detail.get("unit_label"),
        "plan": _unit_plan_name(unit_id),
        "status_name": detail.get("status_name"),
        "balance": detail.get("balance"),
        "currency": detail.get("balance_currency") or detail.get("currency"),
        "cycle_due_days": None if terms is None else terms.get("due_days"),
        # `DEF-BIL-8329` — the card's Cycle cell printed `cycle_due_days`
        # (*"10 days to pay"*) because no cycle NAME was served. The name, or
        # null for a unit on no cycle, which the card says as *None*.
        "cycle_name": _cycle_label(terms),
        "last_bill_on": _iso(detail.get("last_bill_at")),
        "moved_in_on": _iso(detail.get("opened_at")),
    }


def due_date_for(bill_date: date | None, due_days: int | None) -> str | None:
    """BR-BIL-024 through issue's own pure derivation, or null while either half
    is missing — the same date the bill will be stamped with at issue."""
    if bill_date is None or due_days is None:
        return None
    return issue.derive_due_date(bill_date, due_days, cycle_less=True).isoformat()


# ── services, rates, readings ───────────────────────────────────────────────

_RATE_TYPES = {
    "tiered": "tiered",
    "flat": "flat",
    "tou": "time_of_use",
    "time_of_use": "time_of_use",
    "demand": "demand",
    "capacity": "capacity",
    "percent_of_service": "percent_of_service",
}


def _tariffs_of(data: Any) -> tuple[Any, ...]:
    return tuple(getattr(data, "tariffs", ()) or ())


def _service_rank() -> dict[str, int]:
    """`{service code: position}` in the tenant's own CATALOGUE order.

    `DEF-BIL-8316` — the Services and Rates tables and the bill printed their
    services in whatever order the tariffs arrived (alphabetical). The order is
    tenancy's (`services.sort`, the seed order: electric, water, gas, sewer,
    trash, storm water, solar, broadband, thermal/heat, battery, fire), read and
    never typed here — so an eleventh service needs no edit.
    """
    read = gather._resolve("tenancy", "enabled_service_codes")
    codes = tuple(read() or ()) if read is not None else ()
    return {str(code): index for index, code in enumerate(codes)}


def _ranked(code: Any, rank: dict[str, int]) -> tuple[int, str]:
    """Sort key: catalogue position, then the code — an unknown code last, never dropped."""
    return (rank.get(str(code), len(rank)), str(code))


def _unmetered() -> frozenset[str]:
    """BR-RAT-081's declaration: the services priced by COUNT, never read."""
    read = gather._resolve("tenancy", "unmetered_service_codes")
    return frozenset(str(code) for code in (read() or ())) if read is not None else frozenset()


def _asset_label_of(item: Any, assets_by_id: dict[str, dict[str, Any]]) -> str | None:
    label = getattr(item, "asset_label", None)
    if label:
        return str(label)
    asset_id = getattr(item, "asset_id", None)
    if asset_id and str(asset_id) in assets_by_id:
        return assets_by_id[str(asset_id)].get("label")
    return None


def _unit_assets_by_service(unit_id: Any) -> dict[str, list[dict[str, Any]]]:
    """EVERY asset on the unit by service — meters, carts, fire lines."""
    read = gather._resolve("metering", "unit_assets")
    if read is None or not unit_id:
        return {}
    try:
        answer = read(unit_id)
    except Exception:  # noqa: BLE001 — a missing unit is a 404 inside metering
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for group in answer.get("groups") or ():
        for asset in group.get("assets") or ():
            if asset.get("service"):
                out.setdefault(str(asset["service"]), []).append(
                    {"asset_id": str(asset.get("id")), "label": asset.get("asset_no")}
                )
    return out


def _taken_and_unconnected(
    data: Any, detail: dict[str, Any], *, period_start: date, period_end: date
) -> tuple[tuple[str, ...] | None, tuple[str, ...], tuple[str, ...]]:
    """`(taken, unconnected, not_taken)` — gather's OWN answers, called, not restated.

    `unconnected` is the tuple gather already put on the account's data
    (`AccountBillingData.unconnected_services`, BR-BIL-301); `taken` and
    `not_taken` are `gather._services_taken_by_account` and
    `gather._plan_services_not_taken`, the two reads BR-BIL-1048 narrows by.
    Calling them keeps the Services table and the bill from disagreeing about
    which services a customer bought.
    """
    unconnected = tuple(getattr(data, "unconnected_services", ()) or ())
    # The ACCOUNT ROW, through customers' own tenant-scoped read — the same
    # object `single.billable_account` resolves — because
    # `billed_service_codes_for` walks its agreements and service points.
    read = gather._resolve("customers", "account_or_404")
    account = read(detail.get("id")) if read is not None and detail.get("id") else None
    taken = gather._services_taken_by_account(
        account, period_start=period_start, period_end=period_end
    )
    not_taken = gather._plan_services_not_taken(
        detail.get("unit_id"),
        getattr(data, "rate_plan_id", None),
        taken=taken,
        scope_services=None,
        unconnected=unconnected,
    )
    return taken, unconnected, tuple(not_taken)


def services_table(
    data: Any,
    *,
    warnings: tuple[dict[str, Any], ...],
    assets: dict[str, list[dict[str, Any]]],
    taken: tuple[str, ...] | None,
    unconnected: tuple[str, ...],
    not_taken: tuple[str, ...],
) -> list[dict[str, Any]]:
    """§2 `services` — one row per service of the plan, with the ruled status.

    The five statuses are the PO's decision table (design §3, *"this si
    correct"*): `billed` · `billed_base_zero` (a base nobody defined — the bill
    completes at $0.00 and says so) · `follows_basis` (a %-of-service such as
    sewer, with no service point of its own) · `not_in_service` (no connection)
    · `not_taken` (connected, not bought — no line, still shown here).
    """
    base_zero = set(bill_warnings.base_not_set_services(warnings))
    unmetered = _unmetered()
    rows: list[dict[str, Any]] = []
    seen: list[str] = []
    for tariff in _tariffs_of(data):
        code = str(getattr(tariff, "service", "") or "")
        if not code or code in seen:
            continue
        seen.append(code)
        percent = getattr(tariff, "model", None) == "percent_of_service"
        service_assets = [] if percent else list(assets.get(code, ()))
        count = sum(1 for other in _tariffs_of(data) if getattr(other, "service", None) == code)
        count = max(count, len(service_assets))
        if percent:
            status = "follows_basis"
        elif code in base_zero:
            status = "billed_base_zero"
        else:
            status = "billed"
        installed = None if percent else _installed_total(data, code, tariff)
        rows.append(
            {
                "service": code,
                "assets": service_assets,
                # `DEF-BIL-8316` — what one of these assets IS, so the screen
                # says *2 meters* / *1 cart* rather than *2 assets*: a METER for
                # a metered service, the tariff's own billed unit for a service
                # priced by count (BR-RAT-081/090). None for a %-of-service.
                "asset_kind": None if percent else ("count" if code in unmetered else "meter"),
                # ⊕ `DEF-BIL-10221` — NOT for a tariff that SUMS installed
                # capacity: two panels billed as 57.84 kW are not "2 KW", so
                # the count carries no unit and `installed` says the kW.
                "count_unit": (getattr(tariff, "billed_unit", None) or None)
                if code in unmetered and not percent and installed is None
                else None,
                "installed": installed,
                "status": status,
                "basis_service": getattr(tariff, "basis_service", None) if percent else None,
                "count": 0 if percent else count,
                "on_bill": (
                    "percent_line"
                    if percent
                    else ("per_asset_lines" if count > 1 else "usage_and_base")
                ),
            }
        )
    for code in unconnected:
        if code not in seen:
            seen.append(code)
            rows.append(
                {
                    "service": code,
                    "assets": [],
                    "asset_kind": None,
                    "count_unit": None,
                    "status": "not_in_service",
                    "basis_service": None,
                    "count": 0,
                    "on_bill": "no_line",
                }
            )
    for code in not_taken:
        if code not in seen:
            seen.append(code)
            rows.append(
                {
                    "service": code,
                    "assets": list(assets.get(code, ())),
                    "asset_kind": "count" if code in unmetered else "meter",
                    "count_unit": None,
                    "status": "not_taken",
                    "basis_service": None,
                    "count": len(assets.get(code, ())),
                    "on_bill": "no_line",
                }
            )
    rank = _service_rank()
    # Stable: a service's own rows keep their order; services take the
    # catalogue's (`DEF-BIL-8316`).
    return sorted(rows, key=lambda row: _ranked(row["service"], rank))


def _installed_total(data: Any, code: str, tariff: Any) -> dict[str, str] | None:
    """`DEF-BIL-10221` — `{quantity, unit}` of the INSTALLED CAPACITY this
    tariff bills, or `None` when it does not bill one.

    The same question the bill asks (`measure_consumption.
    bills_installed_capacity` — does this tariff price per the unit this
    service's sizes sum in?), so the Services row and the bill line can never
    disagree: 47.84 + 10 kW reads *57.84 kW* on both. `None` for a counting
    service (trash's 3 carts), a meter, or a total that could not be stated.
    """
    from apps.billing.stages.measure_consumption import bills_installed_capacity

    reading = next(
        (one for one in (getattr(data, "readings", ()) or ()) if getattr(one, "service_code", None) == code),
        None,
    )
    if reading is None or not bills_installed_capacity(reading, tariff):
        return None
    total = getattr(reading, "installed_capacity", None)
    if total is None:
        return None
    text = format(Decimal(str(total)).normalize(), "f")
    return {"quantity": text, "unit": str(reading.capacity_uom)}


def _usage_rate(tariff: Any) -> dict[str, Any] | None:
    unit = getattr(tariff, "billed_unit", None) or ""
    if getattr(tariff, "model", None) == "percent_of_service":
        percent = getattr(tariff, "percent", None)
        return {
            "percent": None if percent is None else str(percent),
            "basis_service": getattr(tariff, "basis_service", None),
        }
    tiers = tuple(getattr(tariff, "tiers", ()) or ())
    if len(tiers) == 1 and tiers[0].upper is None:
        # `DEF-BIL-8316` — ONE tier with no ceiling is a single price per unit
        # (trash's *$15.00 / cart*), not a ladder; printed as a ladder it read
        # *"$15.0000 / cart above"* beside a rate type of *Tiered*.
        return {"price": str(tiers[0].unit_price), "unit": unit}
    if tiers:
        return {
            "tiers": [
                {
                    "up_to": None if tier.upper is None else str(tier.upper),
                    "unit": unit,
                    "price": str(tier.unit_price),
                }
                for tier in tiers
            ]
        }
    price = getattr(tariff, "unit_price", None)
    if price is not None:
        return {"price": str(price), "unit": unit}
    return None


def rates_table(
    data: Any,
    *,
    warnings: tuple[dict[str, Any], ...],
    lines: tuple[Any, ...],
    assets_by_id: dict[str, dict[str, Any]],
    version_labels: dict[str, str],
) -> list[dict[str, Any]]:
    """§2 `rates` — one row per priced configuration (a meter, or a service).

    Each row is the `TariffConfig` the engine priced with. `amount` is the sum
    of the priced lines of that service (and meter, where the line names one) —
    already-rounded line amounts, added, which is how the bill itself foots.
    A base nobody defined reads `set: false` at `0.0000`, the ruled default.
    """
    base_zero = set(bill_warnings.base_not_set_services(warnings))
    version_from = _version_from(
        sorted({str(t.version_id) for t in _tariffs_of(data) if getattr(t, "version_id", None)})
    )
    unmetered = _unmetered()
    rows: list[dict[str, Any]] = []
    for tariff in _tariffs_of(data):
        code = str(getattr(tariff, "service", "") or "")
        asset_id = getattr(tariff, "asset_id", None)
        label = _asset_label_of(tariff, assets_by_id)
        own = [
            line
            for line in lines
            if getattr(line, "service", None) == code
            and getattr(line, "kind", None) in ("usage", "base", "minimum_adjustment")
            and (asset_id is None or getattr(line, "asset_id", asset_id) == asset_id)
        ]
        base = getattr(tariff, "base_charge", None)
        version_id = getattr(tariff, "version_id", None)
        model = str(getattr(tariff, "model", "") or "")
        rate_type = _RATE_TYPES.get(model, model or None)
        if rate_type == "flat" and getattr(tariff, "per_size_line", False):
            rate_type = "per_asset"
        if code in unmetered and rate_type in ("tiered", "flat"):
            # `DEF-BIL-8316` — a service priced by COUNT (BR-RAT-090) is a
            # per-asset rate whatever ladder shape stores its one price.
            rate_type = "per_asset"
        rows.append(
            {
                "service": code,
                "asset_id": None if asset_id is None else str(asset_id),
                "asset_label": label,
                "rate_type": rate_type,
                "usage_rate": _usage_rate(tariff),
                "base_charge": (
                    None
                    if base is None and code not in base_zero
                    else {
                        "amount": _money(base or 0),
                        "code": getattr(tariff, "base_charge_code", None),
                        "set": code not in base_zero,
                        "per_asset": bool(getattr(tariff, "per_size_line", False)),
                        "prorated": None,
                    }
                ),
                "minimum": (
                    None
                    if getattr(tariff, "minimum_amount", None) is None
                    else _money(tariff.minimum_amount)
                ),
                "versions": (
                    [
                        {
                            "label": version_labels.get(str(version_id), ""),
                            # `DEF-BIL-8316` — the day it took effect, so the
                            # screen can print the drawing's short cell.
                            "from": version_from.get(str(version_id)),
                        }
                    ]
                    if version_id
                    else []
                ),
                "amount": _money(sum((Decimal(str(line.amount)) for line in own), Decimal("0"))),
            }
        )
    parts = _split_parts(data, lines)
    for row in rows:
        own = parts.get((row["service"], row["asset_id"]), [])
        row["parts"] = own
        if own:
            # The versions the PARTS were priced on, oldest first — the screen
            # draws *"Water · from Sep 1 → Water · from Sep 15"* and its split
            # pill from these, never from the one version at the service date.
            seen: list[dict[str, Any]] = []
            for item in own:
                version = {"label": item["version_label"], "from": item["version_from"]}
                if version not in seen:
                    seen.append(version)
            row["versions"] = seen
    rank = _service_rank()
    return sorted(rows, key=lambda row: _ranked(row["service"], rank))


def _split_parts(data: Any, lines: tuple[Any, ...]) -> dict[tuple[str, Any], list[dict[str, Any]]]:
    """`DEF-BIL-10067` (PO 2026-10-12) — the Rates table's two lines per CHANGED
    service: each part's dates, its rate, its share of the usage and its amount.

    PO: *"two lines per changed service with dates, rate, usage share and
    amount, sewer following water"* (*"this is okay"*). Read off the split the
    bill was priced on (`data.split_segments`) and the priced lines themselves —
    a part's lines are the ones wearing its date stamp (`midperiod.
    _segment_label`) — so the table cannot say anything the bill does not. A
    service that was not cut (trash beside a water change) has no parts and
    keeps its one row. Nothing here prices or rounds: the quantity is the
    part's own (day-weighted or read) and the amount is Σ of its rounded lines.
    """
    from apps.billing import midperiod

    segments = tuple(getattr(data, "split_segments", ()) or ())
    if not segments:
        return {}
    whole = (getattr(data, "period_start", None), getattr(data, "period_end", None))
    version_ids = sorted(
        {
            str(getattr(tariff, "version_id", None))
            for segment in segments
            for tariff in getattr(segment.data, "tariffs", ()) or ()
            if getattr(tariff, "version_id", None)
        }
    )
    starts = _version_from(version_ids)
    labels = _version_labels(version_ids)
    out: dict[tuple[str, Any], list[dict[str, Any]]] = {}
    for segment in sorted(segments, key=lambda s: s.period_start):
        if (segment.period_start, segment.period_end) == whole:
            continue
        stamp = midperiod._segment_label(segment.period_start, segment.period_end)
        for tariff in getattr(segment.data, "tariffs", ()) or ():
            code = str(getattr(tariff, "service", "") or "")
            asset_id = getattr(tariff, "asset_id", None)
            asset_key = None if asset_id is None else str(asset_id)
            own = [
                line
                for line in lines
                if getattr(line, "service", None) == code
                and getattr(line, "kind", None) == "usage"
                and str(getattr(line, "description", "") or "").endswith(stamp)
                and (asset_id is None or getattr(line, "asset_id", asset_id) == asset_id)
            ]
            reading = next(
                (
                    r
                    for r in getattr(segment.data, "readings", ()) or ()
                    if r.service_code == code
                    and (asset_id is None or getattr(r, "asset_id", None) in (None, asset_id))
                ),
                None,
            )
            consumption = getattr(reading, "consumption", None)
            if consumption is not None:
                quantity, unit = consumption.amount, consumption.unit
            else:
                measured = [line for line in own if getattr(line, "quantity", None) is not None]
                quantity = (
                    sum((Decimal(str(line.quantity)) for line in measured), Decimal("0"))
                    if measured
                    else None
                )
                unit = getattr(measured[0], "unit", None) if measured else None
            version_id = getattr(tariff, "version_id", None)
            out.setdefault((code, asset_key), []).append(
                {
                    "period_start": segment.period_start.isoformat(),
                    "period_end": segment.period_end.isoformat(),
                    "days": segment.days,
                    "usage_rate": _usage_rate(tariff),
                    "quantity": None if quantity is None else str(quantity),
                    "unit": unit,
                    "amount": _money(
                        sum((Decimal(str(line.amount)) for line in own), Decimal("0"))
                    ),
                    "version_label": labels.get(str(version_id), "") if version_id else "",
                    "version_from": starts.get(str(version_id)) if version_id else None,
                }
            )
    return {key: value for key, value in out.items() if len(value) > 1}


_NEEDED = {
    one_time.KIND_INTERIM: "every_meter",
    one_time.KIND_FIRST: "move_in_and_new",
    one_time.KIND_FINAL: "final",
    one_time.KIND_BACKBILL: "last_period",
    one_time.KIND_PENALTY: "none",
}


def _read_positions(
    unit_id: Any, start: date, end: date, *, kind: str | None = None
) -> list[dict[str, Any]]:
    read = gather._resolve("metering", "one_time_read_positions")
    if read is None or not unit_id:
        return []
    if kind == one_time.KIND_FIRST and end > start:
        # `DEF-BIL-8563` — on a first bill the move-in day's own reading is the
        # PREVIOUS reading (the start), so the closing reading is looked for from
        # the day after — the same window the engine prices on.
        start = first_bill.first_reading_day(start)
    return list(read(unit_id, period_start=start, period_end=end))


def _priced_read(group: dict[str, Any] | None, position: dict[str, Any]) -> dict[str, Any] | None:
    """The read a catch-up GROUP is priced on for this meter (`DEF-BIL-8328`).

    Matched by the meter where metering split a point per meter, else by the
    service (one meter per point). None when the group states no reads — a
    preview from before this field existed — and the row keeps its old basis.
    """
    reads = (group or {}).get("reads")
    if not reads:
        return None
    asset_id = str(position.get("asset_id") or "")
    for read in reads:
        if read.get("asset_id") and str(read["asset_id"]) == asset_id:
            return read
    service = str(position.get("service") or "")
    for read in reads:
        if not read.get("asset_id") and str(read.get("service")) == service:
            return read
    return None


def _reading_row(
    position: dict[str, Any],
    *,
    kind: str,
    window_end: date,
    typed: dict[str, dict[str, Any]],
    period_index: int | None,
    estimated_services: set[str],
    provisional: dict[str, Any] | None = None,
    priced: dict[str, Any] | None = None,
    clerk_estimate: Any = None,
) -> dict[str, Any]:
    previous = position.get("previous") or None
    current = position.get("current") or None
    typed_row = typed.get(str(position["asset_id"]))
    # `DEF-BIL-8300` — what metering's overlay made of the value typed for this
    # meter: priced (`accepted`, provisionally) or refused on the row, e.g. a
    # reading below the last one (BR-MET-052). None when nothing was typed.
    # 🔒 `DEF-BIL-10067` — ⚠ this read *"or a committed read in the period
    # won"* and looked only where no reading was on file (`current is None`).
    # The typed reading now WINS over a committed one on this bill
    # (`one_time.provisional_reads`), so the row states the reading the bill is
    # priced on — typed 4.6 and 1.7 kgal, not the 8.0 on file and 5.1.
    typed_reading = None
    if provisional is not None and typed_row is not None:
        typed_reading = provisional.get(str(position["asset_id"])) or provisional.get(
            str(position.get("service") or "")
        )
    typed_usage = None
    if current is not None and typed_reading is not None:
        if getattr(typed_reading, "consumption", None) is not None:
            # The typed reading replaces the one on file for this bill.
            current = None
            typed_usage = format(typed_reading.consumption.amount.normalize(), "f")
        elif getattr(typed_reading, "absent_reason", None) != READ_REFUSED_BELOW_LAST:
            # The overlay kept the committed read: it still speaks for the row.
            typed_reading = None
    if current is not None:
        status = "estimated" if current.get("estimated") else "accepted"
        if kind == one_time.KIND_PENALTY:
            status = "assessed"
        elif kind == one_time.KIND_BACKBILL:
            status = "estimated" if current.get("estimated") else "actual"
    elif kind == one_time.KIND_PENALTY:
        status = "assessed"
    elif kind == one_time.KIND_BACKBILL and str(position.get("service")) in estimated_services:
        status = "estimated"
    else:
        status = "waiting"
    refusal_key = None
    if typed_reading is not None:
        if getattr(typed_reading, "consumption", None) is not None:
            status = "accepted"
        elif getattr(typed_reading, "absent_reason", None) == READ_REFUSED_BELOW_LAST:
            status = "refused"
            refusal_key = "billing.oneTimeBill.readings.status.belowLast"
    usage = typed_usage if typed_usage is not None else position.get("consumption")
    if usage is None and typed_row is not None and previous and previous.get("value"):
        try:
            usage = str(Decimal(str(typed_row["value"])) - Decimal(str(previous["value"])))
        except (ArithmeticError, ValueError):
            usage = None
    if current is None and clerk_estimate is not None:
        # 🔒 `DEF-BIL-8562` — the clerk asked for this meter's own estimate on
        # step 2 and metering answered: the row is ESTIMATED, at metering's
        # quantity. (Asked and NOT answered, it stays WAITING above.)
        consumption = getattr(clerk_estimate, "consumption", None)
        if consumption is not None:
            status = "estimated"
            usage = str(consumption.amount)
    if kind == one_time.KIND_BACKBILL and priced is not None and typed_reading is None:
        # `DEF-BIL-8328` — a catch-up row states the read its PERIOD is priced
        # on: the day-share of a read that measured several periods, or the
        # meter's estimate, or nothing yet. The raw read of the window printed
        # *Actual 700 kWh* on a row the price used 361.3 of.
        if priced.get("quantity") is None:
            status = "waiting"
            usage = None
        else:
            status = "estimated" if priced.get("estimated") else "actual"
            usage = priced["quantity"]
    return {
        "asset_id": str(position["asset_id"]),
        "label": position.get("label"),
        "unit": position.get("unit"),
        "previous": {
            "value": None if previous is None else previous.get("value"),
            "read_at": None if previous is None else previous.get("read_at"),
            "on_file": previous is not None,
        },
        "current": {
            "value": (
                current.get("value") if current is not None else (typed_row or {}).get("value")
            ),
            "read_at": (
                current.get("read_at")
                if current is not None
                else ((typed_row or {}).get("read_at") or window_end.isoformat())
            ),
            # A final bill's reading is taken ON the move-out day (design §4).
            "fixed_date": kind == one_time.KIND_FINAL,
        },
        "usage": usage,
        "status": status,
        "refusal_key": refusal_key,
        "period_index": period_index,
    }


def readings_block(
    request: one_time.OneTimeRequest,
    *,
    kind: str,
    unit_id: Any,
    windows: list[tuple[date, date]],
    estimated_by_period: list[set[str]],
    data: Any = None,
    groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """§2 `readings` — one row per METER (per period for catch-up and penalty).

    A service with no meter, a counted service and a %-of-service get NO row
    (design §4, *"no reading row for a service with no meter, a counted service
    or sewer"*): `one_time_read_positions` answers meters only.
    """
    typed = {
        str(row.get("asset_id")): dict(row)
        for row in (getattr(request, "readings", ()) or ())
        if isinstance(row, dict)
        and row.get("asset_id")
        and str(row.get("role") or "") != one_time.ROLE_ESTIMATE
    }
    # 🔒 `DEF-BIL-8562` — the meters the clerk asked to estimate, and what the
    # pricing pass made of each (an estimated reading with no read behind it).
    asked = {row["asset_id"]: row["service"] for row in one_time.clerk_estimates(request)}
    clerk_estimated: dict[str, Any] = {}
    for reading in getattr(data, "readings", ()) or ():
        if not getattr(reading, "estimated", False) or getattr(reading, "read_id", None):
            continue
        own = getattr(reading, "asset_id", None)
        for asset_id, service in asked.items():
            if (own and str(own) == asset_id) or (not own and reading.service_code == service):
                clerk_estimated[asset_id] = reading
    # The overlay's answer for each typed meter, keyed by meter (a point with
    # two meters) or by service (a point with one) — `DEF-BIL-8300`.
    provisional: dict[str, Any] = {}
    for reading in getattr(data, "readings", ()) or ():
        if not getattr(reading, "provisional", False):
            continue
        provisional[str(getattr(reading, "asset_id", None) or reading.service_code)] = reading
    rows: list[dict[str, Any]] = []
    many = len(windows) > 1 or kind in one_time.SUB_PERIOD_KINDS
    for index, (start, end) in enumerate(windows):
        for position in _read_positions(unit_id, start, end, kind=kind):
            rows.append(
                _reading_row(
                    position,
                    kind=kind,
                    window_end=end,
                    typed=typed if index == len(windows) - 1 else {},
                    period_index=index if many else None,
                    estimated_services=estimated_by_period[index] if estimated_by_period else set(),
                    provisional=provisional if index == len(windows) - 1 else None,
                    priced=(
                        _priced_read(groups[index], position)
                        if groups and index < len(groups)
                        else None
                    ),
                    clerk_estimate=clerk_estimated.get(str(position["asset_id"])),
                )
            )
    return {"needed": _NEEDED.get(kind, "none"), "rows": rows}


# ── the bill as it will print ───────────────────────────────────────────────

_CHARGE_BY_KIND = {
    "usage": "usage",
    "base": "base",
    "fee": "fee",
    "deposit": "deposit",
    "minimum_adjustment": "minimum",
    "minimum": "minimum",
    "discount": "discount",
    "adjustment": "discount",
}


def _line_service(line: Any) -> str:
    service = getattr(line, "service", None)
    if service is None:
        return ""
    return str(getattr(service, "code", service))


def bill_line(
    line: Any,
    *,
    percent_services: set[str],
    tiered_services: set[str],
    estimated_services: set[str],
    base_zero: set[str],
    assets_by_id: dict[str, dict[str, Any]],
    counted_services: frozenset[str] = frozenset(),
    charge_codes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One printed line in the contract's shape — the engine's line, relabelled.

    A COUNTED service's one line (`counted_service_line`, `DEF-BIL-8151`) is
    the contract's `per_asset` charge: its quantity is the count and it
    carries that service's base inside it (PO 2026-09-30, *"per service"*).

    A deposit or a fee line names its CHARGE in `service` (the screen prints it
    in the Service column without a colour square), because it belongs to no
    service. The quantity never travels without its unit (rule 3); a
    %-of-service line's rate is its percent.
    """
    kind = str(getattr(line, "kind", ""))
    service = _line_service(line)
    charge = _CHARGE_BY_KIND.get(kind, kind)
    if charge == "usage" and service in percent_services:
        charge = "percent"
    elif charge == "usage" and service in counted_services:
        charge = "per_asset"
    flags: list[str] = []
    if charge in ("usage", "percent") and service in estimated_services:
        flags.append("estimated")
    if charge == "base" and service in base_zero:
        flags.append("base_not_set")
    unit_price = getattr(line, "unit_price", None)
    if charge == "usage" and service in tiered_services:
        rate: str | None = "tiered"
    else:
        rate = None if unit_price is None else str(unit_price)
    quantity = getattr(line, "quantity", None)
    if charge == "base" and "base_not_set" not in flags:
        # `DEF-BIL-8315` — a base line prints its quantity and its rate
        # (*1 · $8.00*), as drawn and as US-BIL-012 TC-12 reads it. The engine
        # states neither on a base line; one base per connection is 1, and the
        # rate is the line's own figure — the amount it charged for that one.
        if quantity is None:
            quantity = Decimal("1")
        if rate is None:
            rate = _money(getattr(line, "amount", 0))
    code = None
    if charge in ("deposit", "fee"):
        # `DEF-BIL-8312` — a fee line names its CHARGE CODE (US-BIL-032 TC-3,
        # *"Fee · RECON · Reconnection fee · 1 · $75.00"*), matched by the
        # line's own `charge_id`, never assumed; one fee is quantity 1 at its
        # own amount.
        code = (
            getattr(line, "charge_code", None)
            or (charge_codes or {}).get(str(getattr(line, "charge_id", None) or ""))
            or None
        )
        if charge == "fee":
            if quantity is None:
                quantity = Decimal("1")
            if rate is None:
                rate = _money(getattr(line, "amount", 0))
    return {
        "service": getattr(line, "description", "") if charge in ("deposit", "fee") else service,
        "asset_label": _asset_label_of(line, assets_by_id),
        "charge": charge,
        "code": code,
        "quantity": None if quantity is None else str(quantity),
        "unit": getattr(line, "unit", None),
        "rate": rate,
        "amount": _money(getattr(line, "amount", 0)),
        "flags": flags,
        # `DEF-BIL-8315` — set on the lines of a service priced by COUNT: the
        # unit one is counted in (*cart*), so the screen prints *Per cart* and
        # *Base · per cart*.
        "per_unit": None,
        # The engine's own unit price, kept only until `bill_document` has
        # decided the rate cell of a per-asset line; never served.
        "_price": None if unit_price is None else str(unit_price),
    }


#: Within one meter, the order the drawing prints a service's lines in.
_CHARGE_ORDER = {"usage": 0, "per_asset": 0, "percent": 0, "minimum": 1, "base": 2, "discount": 3}


def _one_line_per_meter(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`DEF-BIL-8315` — ONE usage line per METER, not one per price tier.

    The engine prices a tiered meter as one line per tier (*5 kgal $16.25*,
    *1.1 kgal $4.95*) and the saved bill keeps them so (its lines are the
    audit trail). What the clerk reviews — and what J70 E1.7 and the drawing
    print — is the meter's usage: **6.1 kgal · Tiered · $21.20**. So the usage
    lines of one service on one meter are summed here: the amounts are the
    already-rounded line amounts, added, which is how the bill foots, so the
    group subtotal and the total cannot move. Lines in different units are
    never summed (rule 3).
    """
    merged: list[dict[str, Any]] = []
    index: dict[tuple[Any, Any, Any], int] = {}
    for line in lines:
        key = (line["service"], line["asset_label"], line["unit"])
        if line["charge"] != "usage" or key not in index:
            if line["charge"] == "usage":
                index[key] = len(merged)
            merged.append(dict(line))
            continue
        into = merged[index[key]]
        into["amount"] = _money(Decimal(into["amount"]) + Decimal(line["amount"]))
        if into["quantity"] is not None and line["quantity"] is not None:
            into["quantity"] = str(Decimal(into["quantity"]) + Decimal(line["quantity"]))
        if into["rate"] != line["rate"]:
            into["rate"] = "tiered"
        into["flags"] = sorted(set(into["flags"]) | set(line["flags"]))
        if into.get("day_share") != line.get("day_share"):
            into["day_share"] = None  # DEF-BIL-8744 — no one share for a sum
    return merged


def size_breakdown(line: Any, data: Any = None) -> list[dict[str, Any]]:
    """PO ruling 2026-10-01 — the size × count × base a capacity line was
    priced from, for the review step and the sent bill: *"billing -> account ->
    unit -> plan -> rate schedule -> base charge -> size and amount"*.

    Read off the DRAFTED line's own `pricing_trace` (`billing/0039`) where it
    has one, else off the preview's gathered `data.pricing_trace`, so the
    review step and the saved bill print the same rows. Only the lines that
    carry the base — a `base` line, or a counted service's joined `usage` line
    — and only sizes with a COUNT (a metered service's one base has none), so
    every other line answers `[]`. Worked: two 96-gallon carts →
    `[{size: CART-96, size_label: "Trash 96-gallon cart", count: 2,
    base_each: "3.0000", price_each: "15.0000", base_priced: true}]`.
    """
    kind = str(getattr(line, "kind", "") or "")
    if kind not in ("base", "usage"):
        return []
    trace = getattr(line, "pricing_trace", None)
    service = getattr(line, "service", None)
    service_code = getattr(service, "code", service)
    if not trace and data is not None:
        trace = (getattr(data, "pricing_trace", None) or {}).get(str(service_code or ""))
    rows = [row for row in (trace or {}).get("sizes") or () if row.get("count") is not None]
    if not rows:
        return []
    if kind == "usage" and not any(row.get("price_each") for row in rows):
        return []  # a summing service's usage is priced on the total, not per size
    return [
        {
            "size": row.get("size"),
            "size_label": row.get("size_label"),
            "count": row.get("count"),
            "base_each": row.get("base_each"),
            "price_each": row.get("price_each"),
            "base_priced": bool(row.get("base_priced", True)),
        }
        for row in rows
    ]


def bill_document(
    lines: tuple[Any, ...],
    *,
    kind: str,
    period_start: date,
    period_end: date,
    currency: str,
    subtotal: Any,
    total: Any,
    data: Any = None,
    warnings: tuple[dict[str, Any], ...] = (),
    estimated_services: set[str] | None = None,
    assets_by_id: dict[str, dict[str, Any]] | None = None,
    charge_codes: dict[str, str] | None = None,
    line_windows: Any = None,
) -> dict[str, Any]:
    """§2 `bill` — the lines grouped as they print (design §1 step 3).

    ⚠ **ONE GROUP PER MONTH ON A CATCH-UP OR PENALTY — `DEF-BIL-8561`
    (2026-09-30, J74).** Service lines are grouped by the month each one bills:
    `line_windows` from the preview's pricing pass (aligned with `lines`), or
    each drafted line's own `period_start`/`period_end`. A bill with one window
    — every other kind — prints one group exactly as before.

    ⚠ **THE FOOTER ADDS UP — `DEF-BIL-8565`.** Where a bill carries one-time
    charges beside its services (a first bill's deposit and connection charge,
    a penalty's tamper charge), `subtotal` is the SERVICE lines and
    `one_time_charges` is a footer line of its own, so *Subtotal + Tax +
    One-time charges = Total* on the page. A fee bill's charge IS the bill, so
    it stays in the subtotal and `one_time_charges` is null.

    Service lines form the period's group; a first bill's deposit and
    connection charge form their own *Move-in charges* group; a fee bill's one
    line forms *Charges*; any other fee (a penalty's tamper charge, a recurring
    code) forms *Other charges*. Tax lines leave the groups and become `tax`.
    `label` is a stable CODE for a group with no dates — the screen prints its
    dates where it has them and translates the code where it does not.
    """
    tariffs = _tariffs_of(data)
    percent_services = {
        str(t.service) for t in tariffs if getattr(t, "model", None) == "percent_of_service"
    }
    tiered_services = {str(t.service) for t in tariffs if getattr(t, "tiers", ())}
    base_zero = set(bill_warnings.base_not_set_services(warnings))
    shaped = []
    taxes = []
    windows = tuple(line_windows or ())
    for position, line in enumerate(lines):
        if str(getattr(line, "kind", "")) == "tax":
            rate = getattr(line, "unit_price", None)
            # DEF-BIL-8303 — the engine's tax line carries the rate as a
            # FRACTION (0.020000 for 2%); contract §2 serves percent POINTS
            # (`"rate": "2.000000"`), which is what the screen formats. Served
            # as a fraction it printed "0.02%" over a 2% tax.
            taxes.append(
                {
                    "label": getattr(line, "description", ""),
                    "rate": None if rate is None else _percent_points(rate),
                    "amount": _money(line.amount),
                }
            )
            continue
        shaped.append(
            bill_line(
                line,
                percent_services=percent_services,
                tiered_services=tiered_services,
                estimated_services=estimated_services or set(),
                base_zero=base_zero,
                assets_by_id=assets_by_id or {},
                counted_services=counted_service_line.counted_services(tariffs),
                charge_codes=charge_codes,
            )
        )
        shaped[-1]["_window"] = _line_window(line, windows, position, (period_start, period_end))
        shaped[-1]["breakdown"] = size_breakdown(line, data)
        shaped[-1]["_days"] = _days_priced_on(line, data)
    # `DEF-BIL-8315` — a service priced by COUNT (BR-RAT-081/090: trash, fire)
    # prints *Per cart* and *Base · per cart*: its usage line is the per-asset
    # charge, and both lines carry the unit the assets are counted in. Read off
    # tenancy's declaration so the draft (which has no tariffs in hand) prints
    # the same words as the preview.
    unmetered = _unmetered()
    count_unit = {
        line["service"]: line["unit"]
        for line in shaped
        if line["service"] in unmetered and line["charge"] in ("usage", "per_asset") and line["unit"]
    }
    for line in shaped:
        if line["service"] in count_unit and line["charge"] in ("usage", "per_asset", "base"):
            if line["charge"] == "usage":
                line["charge"] = "per_asset"
                # One price per asset (*$15.00*), never *Tiered*.
                line["rate"] = line["_price"]
            line["per_unit"] = count_unit[line["service"]]
    for line in shaped:
        line.pop("_price", None)
        # `DEF-BIL-8744` — a line cut down by days says by how many, so
        # quantity × rate × days ÷ cycle days is the amount beside it
        # (*6 kW · $14.00 · 19/30 days · $53.20*). Display only.
        days = line.pop("_days")
        line["day_share"] = day_share.day_share(
            kind="usage" if line["charge"] in ("usage", "per_asset") else line["charge"],
            quantity=line["quantity"],
            rate=line["rate"],
            amount=line["amount"],
            service_days=days[0],
            cycle_days=days[1],
        )
    rank = _service_rank()
    by_window: dict[tuple[date, date], list[dict[str, Any]]] = {}
    for line in shaped:
        window = line.pop("_window")
        if line["charge"] not in ("deposit", "fee"):
            by_window.setdefault(window, []).append(line)
    charge_lines = [line for line in shaped if line["charge"] in ("deposit", "fee")]
    groups: list[dict[str, Any]] = []
    service_total = Decimal("0")
    for (start, end), in_window in sorted(by_window.items()):
        service_lines = _one_line_per_meter(in_window)
        service_lines.sort(
            key=lambda line: (
                _ranked(line["service"], rank),
                line["asset_label"] or "",
                _CHARGE_ORDER.get(line["charge"], 9),
            )
        )
        group = _group("period", service_lines, start=start, end=end)
        service_total += Decimal(group["subtotal"])
        groups.append(group)
    one_time_charges: str | None = None
    if charge_lines and kind != one_time.KIND_FEE:
        one_time_charges = _money(
            sum((Decimal(line["amount"]) for line in charge_lines), Decimal("0"))
        )
    if charge_lines:
        if kind == one_time.KIND_FEE:
            label = "charges"
        elif kind == one_time.KIND_FIRST:
            label = "move_in_charges"
        else:
            label = "other_charges"
        groups.append(_group(label, charge_lines))
    if kind == one_time.KIND_FEE and charge_lines:
        # `DEF-BIL-8734` — a fee bill's charge IS the bill, so it is the
        # subtotal whether or not its code is taxable. The engine's subtotal is
        # the TAXABLE one ($0.00 for an untaxed RECON), which printed Subtotal
        # $0.00 over a Total of $75.00.
        subtotal = service_total + sum(
            (Decimal(line["amount"]) for line in charge_lines), Decimal("0")
        )
    return {
        "groups": groups,
        # `DEF-BIL-8565` — the service lines' sum where the bill carries
        # one-time charges beside them, so the footer foots; otherwise the
        # engine's own subtotal, unchanged.
        "subtotal": _money(service_total) if one_time_charges is not None else _money(subtotal),
        "tax": taxes,
        "one_time_charges": one_time_charges,
        "total": _money(total),
        "currency": currency,
    }


def _days_priced_on(line: Any, data: Any) -> tuple[Any, Any]:
    """`DEF-BIL-8744` — the (service days, cycle days) a line was priced on:
    the saved line's own `pricing_trace` (`billing/0039`), else the gathered
    `AccountBillingData` of a preview not yet saved. Read, never recomputed."""
    trace = getattr(line, "pricing_trace", None) or {}
    if trace.get("cycle_days"):
        return (trace.get("service_days"), trace.get("cycle_days"))
    return (getattr(data, "service_days", None), getattr(data, "cycle_days", None))


def _line_window(
    line: Any, windows: tuple[Any, ...], position: int, bill: tuple[date, date]
) -> tuple[date, date]:
    """`DEF-BIL-8561` — the month one line bills: the pricing pass's own answer
    where it gave one, a drafted line's stored dates, else the bill's window."""
    if position < len(windows) and windows[position]:
        start, end = windows[position]
        return (start, end)
    start = getattr(line, "period_start", None)
    end = getattr(line, "period_end", None)
    if isinstance(start, date) and isinstance(end, date):
        return (start, end)
    return bill


def _group(
    label: str, lines: list[dict[str, Any]], *, start: date | None = None, end: date | None = None
) -> dict[str, Any]:
    return {
        "label": label,
        "period_start": None if start is None else start.isoformat(),
        "period_end": None if end is None else end.isoformat(),
        "subtotal": _money(sum((Decimal(line["amount"]) for line in lines), Decimal("0"))),
        "lines": lines,
    }


# ── duplicate (A8) ──────────────────────────────────────────────────────────


def duplicate_params(run: models.BillRun) -> dict[str, Any]:
    """§4's `409` params — who billed this period already, and the bill to open.

    `invoice_no` is the run's one bill's number (null while it is a draft
    whose number is not yet spent); `invoice_id` is carried for the link and is
    never the visible value of anything (B14 rule 31). `ran_by_name` is the
    user's own name, null while they have not set one.
    """
    invoice = (
        models.Invoice.objects.filter(tenant_id=run.tenant_id, bill_run=run)
        .order_by("created_at")
        .first()
    )
    ran_by = getattr(run, "run_by", None)
    return {
        "run_id": str(run.pk),
        "invoice_id": None if invoice is None else str(invoice.pk),
        "invoice_no": None if invoice is None else invoice.invoice_no,
        "ran_by": None if run.run_by_id is None else str(run.run_by_id),
        "ran_by_name": (getattr(ran_by, "full_name", None) or None) if ran_by else None,
        "ran_at": run.created_at.isoformat() if run.created_at else None,
        # `DEF-BIL-10068` (PO 2026-10-12, *"Do all three"*) — a DRAFT for the
        # period is not a bill that went out: step 1 offers *Open the draft* or
        # *Discard it and start again*, where an ISSUED one is still refused
        # and changed only through Fix a bill. The run's own status when it
        # holds no bill at all.
        "status": (invoice.status if invoice is not None else run.status),
    }


def is_draft_duplicate(params: dict[str, Any]) -> bool:
    """`DEF-BIL-10068` — the colliding run holds a DRAFT, not an issued bill."""
    return params.get("status") == models.INVOICE_DRAFT


def period_check(payload: dict[str, Any]) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10068` / `DEF-BIL-10069` — the two
    things step 1 must say the moment the period is picked, read without
    writing and without pricing.

    PO 2026-10-12: the duplicate check *"moves to step 1"* with *"Draft already
    exists for this period."* and Open / Discard, an issued bill still refused;
    and a closed month posts forward, said on step 1 as *"August is closed.
    Posts to October."* (*"Okay"*). Both were met only at the LAST step before:
    the duplicate as a refusal on Save, the closed month as a refusal at Send.

    * `duplicate` — `duplicate_params` of the run this request would collide
      with (BR-BIL-005, the same key `create_one_time_run` mints), or None.
    * `closed_month` — `{requested_period, posted_period}` when the bill's
      service date falls in a closed fiscal period: the books take the entry on
      the first day of the earliest open one (`posting_seam.forward_for`, the
      same read the issue posts with). None when it is open.

    An incomplete step 1 (no account, no window yet) answers both as None —
    there is nothing to collide with — rather than refusing: the form's own
    checks name the missing fields.
    """
    empty: dict[str, Any] = {"duplicate": None, "closed_month": None}
    try:
        request = request_from(payload)
        _start, end = one_time.checked_window(request)
    except (BillingRuleError, KeyError, TypeError, ValueError):
        return empty
    existing = existing_run_for(request)
    answer = dict(empty)
    if existing is not None:
        answer["duplicate"] = duplicate_params(existing)
    close_error = posting_seam._resolve("ledger", "CloseError", "close")
    try:
        _landing, note = posting_seam.forward_for(end)
    except Exception as refusal:  # noqa: BLE001 — narrowed just below
        if close_error is None or not isinstance(refusal, close_error):
            raise
        note = None
    if note is not None:
        answer["closed_month"] = {
            "requested_period": list(note.get("requested_period") or ()),
            "posted_period": list(note.get("posted_period") or ()),
        }
    return answer


def existing_run_for(request: one_time.OneTimeRequest) -> models.BillRun | None:
    """The run this request would collide with (BR-BIL-005), read WITHOUT writing.

    The same key `create_one_time_run` mints — `idempotency.one_time_run_key`
    over the account, the bill type and the window — so the preview can show
    the *Already billed* banner on step 2 where it is drawn, rather than the
    clerk meeting it as a refusal on step 3.
    """
    kind = request.kind
    try:
        start, end = one_time.checked_window(request)
    except BillingRuleError:
        return None
    key = idempotency.one_time_run_key(
        account_id=request.account_id,
        bill_type=one_time.BILL_TYPE_BY_KIND[kind],
        period_start=start,
        period_end=end,
    )
    return (
        models.BillRun.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), idempotency_key=key
        )
        .select_related("run_by")
        .first()
    )


# ── the whole preview answer ────────────────────────────────────────────────


def _lines_of(priced_pass: Any) -> tuple[Any, ...]:
    priced = getattr(priced_pass, "priced", priced_pass)
    return tuple(getattr(priced, "lines", ()) or ())


def _periods(
    internal: dict[str, Any], version_labels: dict[str, str], kind: str
) -> list[dict[str, Any]]:
    estimated_periods = {
        (row.get("period_start"), row.get("service_code") or row.get("service"))
        for row in internal.get("estimates") or ()
    }
    out = []
    for group in internal.get("groups") or ():
        ids = [str(value) for value in (group.get("tariff_version_ids") or {}).values() if value]
        # `DEF-BIL-8328` — the GROUP's own facts decide: a meter still waiting
        # makes the period *Waiting* (it read *Actual* with nothing typed), and
        # a day-shared read is an estimate in every period it is shared into.
        estimated = any(start == group["period_start"] for start, _ in estimated_periods) or any(
            read.get("estimated") for read in group.get("reads") or ()
        )
        if kind == one_time.KIND_PENALTY:
            reading = "assessed"
        elif group.get("waiting"):
            reading = "waiting"
        else:
            reading = "estimated" if estimated else "actual"
        out.append(
            {
                "period_start": group["period_start"],
                "period_end": group["period_end"],
                "days": group.get("days"),
                "versions": [version_labels.get(i, "") for i in ids if version_labels.get(i)],
                "reading": reading,
                "split_on": None,
            }
        )
    return out


def _version_from(ids: list[str]) -> dict[str, str]:
    read = gather._resolve("rating", "tariff_version_effective_from")
    if read is None or not ids:
        return {}
    return {str(key): str(value) for key, value in (read(ids) or {}).items()}


def _version_labels(ids: list[str]) -> dict[str, str]:
    read = gather._resolve("rating", "tariff_version_labels")
    if read is None or not ids:
        return {}
    return {str(key): str(value) for key, value in (read(ids) or {}).items()}


def _settlement(internal: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any] | None:
    row = internal.get("settlement") or {}
    deposit = internal.get("deposit") or {}
    if not row.get("available"):
        return None
    automatic = row.get("automatic")
    return {
        "this_bill": internal.get("total"),
        "prior_balance": detail.get("balance"),
        "deposit": deposit.get("principal") if deposit.get("available") else "0.0000",
        "interest": deposit.get("interest") if deposit.get("available") else "0.0000",
        "remainder": row.get("remainder"),
        "automatic": row.get("path") if automatic else None,
        "paths": [
            path for path in row.get("available_paths") or () if path in CHOSEN_SETTLEMENT_PATHS
        ],
    }


def _move_in_charges(
    request: one_time.OneTimeRequest, lines: tuple[Any, ...], moved_in_on: str | None
) -> dict[str, Any] | None:
    deposit_lines = [line for line in lines if getattr(line, "kind", None) == "deposit"]
    fee_lines = [line for line in lines if getattr(line, "kind", None) == "fee"]
    paid = payments_seam.deposit_paid_for_account(request.account_id)
    owed = sum((Decimal(str(line.amount)) for line in deposit_lines), Decimal("0"))
    paid_value = paid if paid is not None else Decimal("0")
    return {
        "moved_in_on": moved_in_on,
        "deposit_asked": _money(owed + paid_value) if deposit_lines else _money(paid_value),
        "deposit_paid": _money(paid_value),
        "lines": [
            {"kind": "deposit", "label": line.description, "amount": _money(line.amount)}
            for line in deposit_lines
        ]
        + [
            {
                "kind": "fee",
                "code": _fee_line_code(line),
                "label": line.description,
                "amount": _money(line.amount),
            }
            for line in fee_lines
        ],
    }


def _fee_line_code(line: Any) -> str | None:
    """The charge CODE of a move-in fee line (contract §2: `{kind: fee, code: CONN}`).

    DEF-BIL-8314 — a priced `RatedLine` carries `charge_id` and no code, so
    reading `charge_code` off it answered None and the panel printed *Code —*.
    The first bill's one fee is its connection charge
    (`first_bill.DEFAULT_CONNECTION_CHARGE_CODE`), resolved through rating's
    own published read and matched by id, never assumed.
    """
    code = getattr(line, "charge_code", None)
    if code:
        return str(code)
    charge_id = getattr(line, "charge_id", None)
    if charge_id is None:
        return None
    from apps.billing import first_bill

    read = gather._resolve("rating", "charge_by_code")
    row = read(first_bill.DEFAULT_CONNECTION_CHARGE_CODE) if read is not None else None
    if row and str(row.get("id")) == str(charge_id):
        return str(row.get("code"))
    return None


def _charge_codes(request: one_time.OneTimeRequest) -> dict[str, str]:
    """`{charge id: code}` for the codes this bill can carry a fee line for.

    `DEF-BIL-8312` — a priced line and an invoice line both name their charge
    by ID. The codes a one-time bill can put on a fee line are the clerk's
    chosen charge (fee, penalty) and a first bill's connection charge; each is
    read through rating's own `charge_by_code` and matched by id, so a line
    whose id matches none of them names no code rather than a guessed one.
    """
    from apps.billing import first_bill

    read = gather._resolve("rating", "charge_by_code")
    if read is None:
        return {}
    out: dict[str, str] = {}
    for code in (getattr(request, "charge_code", "") or "", first_bill.DEFAULT_CONNECTION_CHARGE_CODE):
        if not code:
            continue
        row = read(code)
        if row and row.get("id") is not None:
            out[str(row["id"])] = str(row.get("code") or code)
    return out


def _charge_block(code: str, entered: Decimal | None = None) -> dict[str, Any] | None:
    if not code:
        return None
    read = gather._resolve("rating", "charge_by_code")
    row = read(code) if read is not None else None
    if row is None:
        return None
    amount = row.get("amount")
    if amount is None and entered is not None and row.get("amount_rule") == "per_case":
        # DEF-RAT-8753 — a code priced *entered when used* shows the figure the
        # clerk entered: it is the figure the draft will carry (`fee_bill`).
        amount = entered
    return {
        "code": row.get("code"),
        "label": row.get("name"),
        "amount": None if amount is None else _money(amount),
        "taxable": bool(row.get("taxable_default")),
    }


def preview_answer(
    request: one_time.OneTimeRequest, *, internal: dict[str, Any], captured: dict[str, Any]
) -> dict[str, Any]:
    """§2's answer, whole. Sections a kind does not have are `null`."""
    kind = request.kind
    detail = _account_detail(request.account_id)
    data = captured.get("data")
    priced_pass = captured.get("priced")
    lines = _lines_of(priced_pass) if priced_pass is not None else ()
    warnings = tuple(internal.get("warnings") or ())
    period_start = date.fromisoformat(internal["period_start"])
    period_end = date.fromisoformat(internal["period_end"])
    unit_id = detail.get("unit_id")

    positions = (
        [] if kind == one_time.KIND_FEE else _read_positions(unit_id, period_start, period_end, kind=kind)
    )
    assets_by_id = {str(p["asset_id"]): p for p in positions}
    version_ids = [
        str(getattr(t, "version_id", None))
        for t in _tariffs_of(data)
        if getattr(t, "version_id", None)
    ]
    for group in internal.get("groups") or ():
        version_ids += [str(v) for v in (group.get("tariff_version_ids") or {}).values() if v]
    labels = _version_labels(sorted(set(version_ids)))

    estimated_services = {
        str(reading.service_code)
        for reading in getattr(data, "readings", ()) or ()
        if getattr(reading, "estimated", False)
    }
    estimated_services |= {
        str(row.get("service_code") or row.get("service"))
        for row in internal.get("estimates") or ()
    }

    answer: dict[str, Any] = {
        "kind": kind,
        "account": account_block(request, detail=detail, data=data, internal=internal),
        "defaults": {
            "bill_date": None if request.bill_date is None else request.bill_date.isoformat(),
            "due_days": None,
        },
        "due_date": due_date_for(request.bill_date, request.due_days),
        "services": None,
        "rates": None,
        "readings": None,
        "periods": None,
        "move_in_charges": None,
        "settlement": None,
        "charge": None,
        "bill": bill_document(
            lines,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            currency=str(internal.get("currency") or detail.get("currency") or ""),
            subtotal=internal.get("subtotal") or 0,
            total=internal.get("total") or 0,
            data=data,
            warnings=warnings,
            estimated_services=estimated_services,
            assets_by_id=assets_by_id,
            charge_codes=_charge_codes(request),
            line_windows=getattr(priced_pass, "line_windows", None),
        ),
        "warnings": [dict(row) for row in warnings],
        "duplicate": None,
        "unavailable": [dict(row) for row in ANSWER_UNAVAILABLE],
    }
    answer["defaults"]["due_days"] = answer["account"]["cycle_due_days"]

    if kind == one_time.KIND_FEE:
        answer["charge"] = _charge_block(request.charge_code, request.entered_amount)
    else:
        assets = _unit_assets_by_service(unit_id)
        taken, unconnected, not_taken = _taken_and_unconnected(
            data, detail, period_start=period_start, period_end=period_end
        )
        # `noAgreements` is NOT added here: since B8 (2026-09-30) gather puts it
        # on the account's own warnings (`contracts.WARN_NO_AGREEMENTS`), so the
        # bill, the draft's snapshot and this answer carry ONE copy of it.
        answer["services"] = services_table(
            data,
            warnings=warnings,
            assets=assets,
            taken=taken,
            unconnected=unconnected,
            not_taken=not_taken,
        )
        answer["rates"] = rates_table(
            data, warnings=warnings, lines=lines, assets_by_id=assets_by_id, version_labels=labels
        ) + [
            # Design §4: a service not in service shows *No rate used*, $0.00 —
            # a row with no rate type, never a price nobody applied.
            {
                "service": row["service"],
                "asset_id": None,
                "asset_label": None,
                "rate_type": None,
                "usage_rate": None,
                "base_charge": None,
                "minimum": None,
                "versions": [],
                "amount": "0.0000",
            }
            for row in answer["services"]
            if row["status"] == "not_in_service"
        ]
        if kind in one_time.SUB_PERIOD_KINDS:
            windows = [
                (date.fromisoformat(g["period_start"]), date.fromisoformat(g["period_end"]))
                for g in internal.get("groups") or ()
            ] or [(period_start, period_end)]
            estimated_by_period = [
                {
                    str(row.get("service_code") or row.get("service"))
                    for row in internal.get("estimates") or ()
                    if row.get("period_start") == start.isoformat()
                }
                for start, _ in windows
            ]
            answer["periods"] = _periods(internal, labels, kind)
            answer["charge"] = (
                _charge_block(request.charge_code) if kind == one_time.KIND_PENALTY else None
            )
        else:
            windows = [(period_start, period_end)]
            estimated_by_period = [estimated_services]
        answer["readings"] = readings_block(
            request,
            kind=kind,
            unit_id=unit_id,
            windows=windows,
            estimated_by_period=estimated_by_period,
            data=data,
            groups=(
                list(internal.get("groups") or ()) if kind in one_time.SUB_PERIOD_KINDS else None
            ),
        )
        estimated_count = sum(
            1 for row in answer["readings"]["rows"] if row["status"] == "estimated"
        )
        if estimated_count and kind != one_time.KIND_PENALTY:
            answer["warnings"] = [
                *answer["warnings"],
                {"key": "billing.oneTime.warn.estimated", "params": {"count": estimated_count}},
            ]
        if kind == one_time.KIND_FIRST:
            answer["move_in_charges"] = _move_in_charges(
                request, lines, internal.get("moved_in_on") or answer["account"]["moved_in_on"]
            )
        if kind == one_time.KIND_FINAL:
            answer["settlement"] = _settlement(internal, detail)

    if internal.get("priced") is False:
        # `DEF-BIL-8300` — the ONE pricing refusal a preview answers rather
        # than refuses: a meter still WAITING for its reading. The services,
        # rates and reading rows above are the clerk's way to type it; the
        # bill carries NO total (not 0.00 — a zero on a bill preview is the
        # claim that the customer owes nothing) and names what it waits for.
        gap = dict(internal.get("priced_unavailable") or {})
        answer["bill"] = {
            "groups": [],
            "subtotal": None,
            "tax": [],
            "one_time_charges": None,
            "total": None,
            "currency": answer["bill"]["currency"],
        }
        answer["waiting_for"] = {
            "reason": gap.get("reason"),
            "service_code": gap.get("service_code"),
        }

    existing = existing_run_for(request)
    if existing is not None:
        answer["duplicate"] = duplicate_params(existing)
    return answer


def draft_answer(created: dict[str, Any], request: one_time.OneTimeRequest) -> dict[str, Any]:
    """§4's `201` — the draft's number, money and due date, plus its bill and warnings.

    The bill is read back off the DRAFTED invoice's own lines, so what step 3
    shows after Save draft is what was written, not what the preview priced.
    """
    invoice = models.Invoice.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=created["invoice_id"]
    ).first()
    lines: tuple[Any, ...] = ()
    if invoice is not None:
        lines = tuple(
            models.InvoiceLine.objects.filter(tenant_id=invoice.tenant_id, invoice=invoice)
            .select_related("service")
            .order_by("created_at", "id")
        )
    warnings = tuple(created.get("warnings") or ())
    start = date.fromisoformat(created["period_start"])
    end = date.fromisoformat(created["period_end"])
    # Each line names its meter since `billing/0031` (`invoice_lines.asset_id`);
    # the meter's NUMBER is Meter Reads', read the same way the preview reads it.
    positions = (
        []
        if request.kind == one_time.KIND_FEE
        else _read_positions(
            _account_detail(request.account_id).get("unit_id"), start, end, kind=request.kind
        )
    )
    return {
        "run_id": created["run_id"],
        "invoice_id": created["invoice_id"],
        "invoice_no": created.get("invoice_no"),
        "total": _money(created.get("total") or 0),
        "currency": created.get("currency"),
        "due_date": due_date_for(request.bill_date, request.due_days),
        "bill": bill_document(
            lines,
            kind=request.kind,
            period_start=start,
            period_end=end,
            currency=str(created.get("currency") or ""),
            subtotal=created.get("subtotal") or 0,
            total=created.get("total") or 0,
            warnings=warnings,
            assets_by_id={str(p["asset_id"]): p for p in positions},
            charge_codes=_charge_codes(request),
        ),
        "warnings": [dict(row) for row in warnings],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-033@2026-09-30 (sources: 13-one-time-bill-api-contract.md ·
#         11-one-time-bill-redesign.md · 12-one-time-bill-build-plan.md A1–A9 ·
#         EP-BIL-03 §AMENDED 2026-09-30; co-packets US-BIL-010..014, 032, 034)
# generated: 2026-09-30 by the one-time bill API lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see tests/test_otb_a_one_time_api_contract.py
# exceptions: the four rows of ANSWER_UNAVAILABLE above, each with its reason
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
